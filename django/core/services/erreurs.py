"""Journal des erreurs (10/11/2026, audit avant l'ouverture au partenaire) : sur Vercel les erreurs n'allaient que dans la
sortie du serveur, jamais conservée. Chaque erreur est rangée en base (table journal_erreurs), regroupée par « empreinte »
(le message sans ses nombres) avec son nombre d'occurrences, et signalée au fondateur à sa première apparition :
e-mail (MAIL_ADMIN) et message privé Telegram (TELEGRAM_ADMIN_CHAT_ID, jamais la chaîne publique).
Une même erreur n'est re-signalée qu'après 6 h ; 20 alertes par jour au plus. Ne lève jamais d'exception."""
import hashlib
import json
import re
import threading

ALERTE_APRES_H = 6
ALERTES_PAR_JOUR = 20
_local = threading.local()


def creer_table() -> None:
    from core import db
    db.run("""CREATE TABLE IF NOT EXISTS journal_erreurs (
        id BIGSERIAL PRIMARY KEY, premiere TIMESTAMPTZ NOT NULL DEFAULT NOW(), derniere TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        canal VARCHAR(40) NOT NULL, niveau VARCHAR(12) NOT NULL, empreinte VARCHAR(40) NOT NULL, message TEXT NOT NULL,
        contexte TEXT, occurrences INTEGER NOT NULL DEFAULT 1, alerte_le TIMESTAMPTZ, resolue BOOLEAN NOT NULL DEFAULT FALSE)""")
    db.run("CREATE INDEX IF NOT EXISTS journal_erreurs_empreinte ON journal_erreurs (empreinte, derniere DESC)")


def empreinte(canal: str, message: str) -> str:
    """Même erreur = même empreinte, quels que soient les nombres, identifiants et adresses qu'elle contient."""
    base = re.sub(r"https?://\S+", "<url>", message or "")
    base = re.sub(r"\d+", "#", base)[:300]
    return hashlib.sha1(f"{canal}|{base}".encode()).hexdigest()[:40]


def note(canal: str, niveau: str, message: str, contexte: dict | None = None) -> None:
    if getattr(_local, "occupe", False):     # une erreur pendant l'écriture du journal : jamais de boucle
        return
    _local.occupe = True
    try:
        _note(canal, niveau, message, contexte)
    except Exception:  # noqa: BLE001 — le journal ne doit jamais casser ce qu'il observe
        pass
    finally:
        _local.occupe = False


def _note(canal, niveau, message, contexte):
    from core import db
    creer_table()
    e = empreinte(canal, message)
    ctx = json.dumps(contexte, ensure_ascii=False, default=str)[:6000] if contexte else None
    ligne = db.one("""SELECT id, alerte_le FROM journal_erreurs WHERE empreinte = ? AND NOT resolue
                      AND derniere >= NOW() - interval '7 days' ORDER BY derniere DESC LIMIT 1""", [e])
    if ligne:
        db.run("UPDATE journal_erreurs SET occurrences = occurrences + 1, derniere = NOW(), contexte = COALESCE(?, contexte) WHERE id = ?",
               [ctx, ligne["id"]])
        jid, deja = ligne["id"], ligne["alerte_le"]
    else:
        jid = db.insert("journal_erreurs", {"canal": canal[:40], "niveau": niveau[:12], "empreinte": e, "message": (message or "")[:4000],
                                            "contexte": ctx})
        deja = None
    recente = db.value("SELECT 1 FROM journal_erreurs WHERE id = ? AND alerte_le >= NOW() - (? * interval '1 hour')", [jid, ALERTE_APRES_H])
    du_jour = int(db.value("SELECT COUNT(*) FROM journal_erreurs WHERE alerte_le >= date_trunc('day', NOW())") or 0)
    if recente or du_jour >= ALERTES_PAR_JOUR:
        return
    db.run("UPDATE journal_erreurs SET alerte_le = NOW() WHERE id = ?", [jid])
    alerte(canal, niveau, message, contexte, nouvelle=deja is None)


def alerte(canal: str, niveau: str, message: str, contexte: dict | None, nouvelle: bool = True) -> None:
    from core import env, mail
    titre = f"{'Nouvelle erreur' if nouvelle else 'Erreur répétée'} · {canal}"
    texte = f"{titre}\n\n{message[:1500]}"
    if contexte:
        texte += "\n\n" + "\n".join(f"{k} : {str(v)[:600]}" for k, v in list(contexte.items())[:6])
    texte += "\n\nJournal complet : admin du site > Journal des erreurs."
    try:
        if mail.configured():
            mail.notify_admin(titre, texte)
    except Exception:  # noqa: BLE001
        pass
    chat = env.get("TELEGRAM_ADMIN_CHAT_ID", "")
    jeton = env.get("TELEGRAM_FILES_BOT_TOKEN", "") or env.get("TELEGRAM_BOT_TOKEN", "")
    if chat and jeton:
        try:
            import requests
            requests.post(f"https://api.telegram.org/bot{jeton}/sendMessage", timeout=10,
                          json={"chat_id": chat, "text": "⚠️ " + texte[:3900], "disable_web_page_preview": True})
        except Exception:  # noqa: BLE001
            pass


class JournalHandler:
    """Gestionnaire de logging Django : les plantages des pages (django.request, niveau ERROR) vont au journal."""

    def __new__(cls, *a, **k):
        import logging

        class _H(logging.Handler):
            def emit(self, record):
                try:
                    req = getattr(record, "request", None)
                    trace = ""
                    if record.exc_info:
                        import traceback
                        trace = "".join(traceback.format_exception(*record.exc_info))[-3000:]
                    msg = record.getMessage()
                    if record.exc_info and record.exc_info[1] is not None:
                        msg = f"{type(record.exc_info[1]).__name__} : {record.exc_info[1]} ({msg})"
                    note("site", "error", msg, {"page": getattr(req, "path", ""), "methode": getattr(req, "method", ""),
                                                "trace": trace})
                except Exception:  # noqa: BLE001
                    pass
        h = _H()
        h.setLevel(logging.ERROR)
        return h
