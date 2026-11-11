"""Répétition générale avant la publication du vendredi (11/11/2026 : « quoi qu'il arrive, ce vendredi tout doit se
passer sans interruption ni bug »).

--avant (jeudi soir, vendredi midi) : tout ce dont la publication a besoin est vérifié, sans rien publier ; verdict
GO / NO-GO par e-mail, Telegram (message privé) et notification du Studio, avec ce qui cloche.
--apres (vendredi soir) : les classements de la semaine sont-ils publiés, les posts partis ? Sinon, alerte.
Ne lève jamais d'exception : chaque contrôle donne (critique, ok, message)."""
import os
import re
import smtplib
import time
from datetime import timedelta
from pathlib import Path

import requests
from django.core.management.base import BaseCommand

from core import clock, db, env


def _ok(critique: bool, ok: bool, msg: str) -> tuple:
    return critique, ok, msg


def _controle(nom, f, critique=True):
    try:
        ok, msg = f()
    except Exception as exc:  # noqa: BLE001
        ok, msg = False, f"{exc.__class__.__name__} : {str(exc)[:200]}"
    return _ok(critique, ok, f"{nom} : {msg}")


# ---------------------------------------------------------------- contrôles « avant »

def c_base():
    return db.value("SELECT 1") == 1, "joignable"


def c_donnees():
    d = db.value("SELECT MAX(captured_on) FROM snapshots")
    age = (clock.today() - (d if hasattr(d, "year") else __import__("datetime").date.fromisoformat(str(d)[:10]))).days
    return age <= 1, f"derniers relevés du {d} ({age} jour(s))"


def c_nuit():
    r = db.one("SELECT ran_at AS created_at, failed, steps FROM pipeline_runs ORDER BY id DESC LIMIT 1")
    if not r:
        return False, "aucune nuit enregistrée"
    import json
    ko = [s[0] for s in json.loads(r["steps"] or "[]") if not s[1]]
    vieux = (clock.now() - r["created_at"]).total_seconds() > 36 * 3600 if hasattr(r["created_at"], "year") else False
    return not vieux and len(ko) <= 2, f"dernière nuit {str(r['created_at'])[:16]}, {len(ko)} étape(s) en échec" + (f" : {', '.join(ko)}" if ko else "")


def c_semaine():
    from core.services.charts import Period
    vendredi = clock.today() + timedelta(days=(4 - clock.today().weekday()) % 7)
    p = Period.last_completed_week(vendredi.isoformat())
    return p.publication_day() == vendredi.isoformat(), f"vendredi {vendredi:%d/%m} : semaine {p.key} ({p.start} → {p.end}), publication le {p.publication_day()}"


def c_blob():
    from core import storage
    nom = f"relais/repetition-{int(time.time())}.txt"
    url = storage.blob_put(nom, b"ok", "text/plain")
    lu = requests.get(url, timeout=20).text
    try:
        storage.blob_delete([url])
    except Exception:  # noqa: BLE001
        pass
    return lu == "ok", "écriture et lecture OK" if lu == "ok" else f"lecture inattendue : {lu[:40]!r}"


def c_buffer():
    from core.services import buffer
    cap = buffer.capacity()
    if not cap:
        return False, "API injoignable ou clé refusée"
    return True, f"{cap[1]} post(s) programmé(s) pour une limite de {cap[0]}"


def c_jetons():
    from core.services import jetons
    lignes = jetons.verifier(alerter=False)
    urgent = [l for l in lignes if "impossible" in l or re.search(r"expire dans [0-2] jour", l)]
    return not urgent, " ; ".join(lignes)


def c_meta():
    tok, ig = env.get("META_ACCESS_TOKEN", ""), env.get("META_IG_ID", "")
    if not tok or not ig:
        return False, "jeton ou compte Instagram absent"
    d = requests.get(f"https://graph.facebook.com/v21.0/{ig}", params={"fields": "username", "access_token": tok}, timeout=20).json()
    return "username" in d, f"compte @{d['username']}" if "username" in d else str(d.get("error", {}).get("message", d))[:160]


def c_ia():
    res = []
    if env.get("GEMINI_API_KEY", ""):
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": env.get("GEMINI_API_KEY"), "pageSize": 1}, timeout=20)
        res.append(("Gemini", r.status_code == 200))
    if env.get("GROQ_API_KEY", ""):
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {env.get('GROQ_API_KEY')}"}, timeout=20)
        res.append(("Groq", r.status_code == 200))
    if env.get("OPENROUTER_API_KEY", ""):
        r = requests.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {env.get('OPENROUTER_API_KEY')}"}, timeout=20)
        res.append(("OpenRouter", r.status_code == 200))
    return any(ok for _n, ok in res), ", ".join(f"{n} {'OK' if ok else 'refusé'}" for n, ok in res) or "aucune clé"


def c_smtp():
    hote = env.get("SMTP_HOST", "")
    if not hote:
        return False, "SMTP non configuré"
    port = int(env.get("SMTP_PORT", "587") or 587)
    s = smtplib.SMTP_SSL(hote, port, timeout=20) if port == 465 else smtplib.SMTP(hote, port, timeout=20)
    if port != 465:
        s.starttls()
    s.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
    s.quit()
    return True, "connexion et identifiants OK"


def c_telegram():
    tok = env.get("TELEGRAM_BOT_TOKEN", "")
    if not tok:
        return False, "jeton absent"
    d = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=20).json()
    return bool(d.get("ok")), f"bot @{d['result']['username']}" if d.get("ok") else str(d)[:120]


def c_site():
    pages = {"/": 200, "/classements/afrique-de-l-ouest": 200, "/espace/nec-ultra": 200}
    base = (env.get("APP_URL", "") or "").rstrip("/")
    if not base.startswith("https://") or "localhost" in base:
        base = "https://www.cauricharts.com"
    ko = []
    for chemin, attendu in pages.items():
        r = requests.get(base + chemin, timeout=30, allow_redirects=True)
        if r.status_code != attendu:
            ko.append(f"{chemin} HTTP {r.status_code}")
    return not ko, "pages OK" if not ko else ", ".join(ko)


def c_polices():
    """Toutes les polices nommées dans le code existent (10/11/2026 : « cannot open resource », polices jamais envoyées)."""
    racine = Path(__file__).resolve().parents[3]
    fonts = racine.parent / "resources" / "fonts"
    noms = set()
    for f in (racine / "core").rglob("*.py"):
        noms |= set(re.findall(r'["\']([A-Za-z0-9_-]+\.(?:ttf|otf))["\']', f.read_text(encoding="utf-8", errors="ignore")))
    secours = {"arial.ttf", "sans.ttf", "sans-bold.ttf", "serif-bold.ttf"}   # noms de repli, toujours avec une solution de rechange
    manquent = sorted(n for n in noms - secours if not (fonts / n).exists())
    return not manquent, f"{len(noms)} polices, toutes présentes" if not manquent else "MANQUANTES : " + ", ".join(manquent)


def c_modules():
    """Les modules de la publication se chargent (dépendances installées)."""
    import importlib
    for m in ("core.services.social.officiel", "core.services.social.formats", "core.services.buffer", "core.services.meta",
              "core.services.chart_service"):
        importlib.import_module(m)
    return True, "modules de publication chargés"


AVANT = [("Base de données", c_base, True), ("Relevés de la nuit", c_donnees, True), ("Chaîne de nuit", c_nuit, False),
         ("Semaine à publier", c_semaine, True), ("Stockage (Blob)", c_blob, True), ("Buffer", c_buffer, True),
         ("Jetons", c_jetons, True), ("Meta (Instagram, Facebook)", c_meta, True), ("IA", c_ia, False),
         ("E-mail", c_smtp, False), ("Telegram", c_telegram, False), ("Site", c_site, True), ("Polices", c_polices, True),
         ("Modules", c_modules, True)]


# ---------------------------------------------------------------- contrôles « après »

def c_publie():
    from core.services.charts import Period
    p = Period.last_completed_week(clock.today().isoformat())
    n = int(db.value("SELECT COUNT(*) FROM chart_runs WHERE period_type = 'week' AND period_key = ? AND status = 'published'", [p.key]) or 0)
    return n > 0, f"semaine {p.key} : {n} classement(s) publié(s)"


def c_posts():
    n = int(db.value("""SELECT COUNT(*) FROM audit_log WHERE action = 'buffer.post' AND created_at >= CURRENT_DATE""") or 0)
    return n > 0, f"{n} envoi(s) vers les réseaux aujourd'hui"


APRES = [("Classements publiés", c_publie, True), ("Posts envoyés", c_posts, True), ("Site", c_site, True)]


class Command(BaseCommand):
    help = "Répétition générale de la publication du vendredi (--avant) ou contrôle après publication (--apres)."

    def add_arguments(self, p):
        p.add_argument("--apres", action="store_true")
        p.add_argument("--sans-alerte", action="store_true", help="afficher seulement (essai)")

    def handle(self, *args, **o):
        liste = APRES if o["apres"] else AVANT
        res = [_controle(n, f, c) for n, f, c in liste]
        bloquants = [m for c, ok, m in res if c and not ok]
        avert = [m for c, ok, m in res if not c and not ok]
        verdict = "NO-GO" if bloquants else "GO"
        titre = (f"Publication du vendredi : {verdict}" if not o["apres"]
                 else f"Après publication : {'tout est parti' if not bloquants else 'PROBLÈME'}")
        texte = "\n".join(("✅ " if ok else ("❌ " if c else "⚠️ ")) + m for c, ok, m in res)
        if bloquants:
            texte += "\n\nÀ régler avant 19 h (UTC) : " + " | ".join(bloquants) if not o["apres"] else "\n\nÀ regarder tout de suite : " + " | ".join(bloquants)
        self.stdout.write(titre + "\n" + texte)
        if o["sans_alerte"]:
            return
        try:
            from core import mail
            if mail.configured():
                mail.notify_admin(titre, texte)
        except Exception:  # noqa: BLE001
            pass
        chat, jeton = env.get("TELEGRAM_ADMIN_CHAT_ID", ""), env.get("TELEGRAM_FILES_BOT_TOKEN", "") or env.get("TELEGRAM_BOT_TOKEN", "")
        if chat and jeton:   # message privé au fondateur, jamais la chaîne publique
            try:
                requests.post(f"https://api.telegram.org/bot{jeton}/sendMessage", timeout=15, json={"chat_id": chat, "text": titre + "\n\n" + texte})
            except Exception:  # noqa: BLE001
                pass
        try:
            from core.services import notif
            notif.envoie(titre, (" | ".join(bloquants) or "Tout est prêt.")[:240], etiquette="repetition")
        except Exception:  # noqa: BLE001
            pass
        if bloquants and o["apres"]:
            raise SystemExit(2)
