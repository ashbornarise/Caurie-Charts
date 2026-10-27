"""Comité de rédaction de Cauri Charts : des agents DeepSeek qui vérifient, notent et font progresser nos contenus
(demande du fondateur, 27/10/2026 : « montrer que nous sommes un média qui représente des valeurs »).

Agents de base (table redaction_agents, modifiables sans toucher au code) :
  verite     : chaque affirmation est-elle dans les sources ? Sinon on corrige ou on bloque.
  fraicheur  : l'info est-elle récente (articles du jour, fait principal de moins de 30 jours) ?
  qualite    : français, clarté, accroche honnête (pas de piège à clics), respect des artistes, charte.
  analyste   : chaque semaine, ce qui marche (vues, interactions par format, sujet, heure) → leçons chiffrées.
  directeur  : chaque semaine, relit le travail des agents, retire les inutiles, crée un agent « à l'essai » s'il manque
               un contrôle ; un agent à l'essai donne son avis sans rien bloquer, il est promu s'il s'est montré utile.
Les leçons actives sont ajoutées aux consignes des rédacteurs IA (consignes()) : la rédaction s'améliore seule.
Chaque avis est gardé (redaction_avis) et repris dans Admin > Contrôles et le rapport du matin.
"""
import json
from datetime import datetime, timedelta, timezone

from core import db
from core.services.platforms import HttpClient, PlatformException, log_write

CHARTE = (
    "Charte de Cauri Charts, la référence de la musique ouest-africaine :\n"
    "1. Vérité : rien n'est affirmé qui ne soit dans nos sources ; un chiffre a toujours une source ; la rumeur reste une rumeur.\n"
    "2. Fraîcheur : on parle de ce qui se passe maintenant ; un fait ancien est présenté comme tel.\n"
    "3. Respect : des artistes, de leur travail, de leur vie privée ; pas de moquerie, pas d'acharnement, prudence sur "
    "les décès, la santé, la justice.\n"
    "4. Équité : tous les pays et tous les artistes ont la même règle ; le classement ne s'achète pas.\n"
    "5. Clarté : un français impeccable, des titres qui disent exactement ce qui s'est passé, jamais de piège à clics.\n"
    "6. Fierté africaine : on met en valeur la musique d'Afrique de l'Ouest, sans dénigrer les autres.")

BASE = [
    ("verite", "Vérificateur des faits",
     "Compare le TEXTE aux SOURCES. Liste chaque affirmation du texte qui n'est pas dans les sources (chiffre, date, record, "
     "citation, lieu, nom). Si une correction simple suffit, propose le texte corrigé. « bloquer » seulement si le cœur de "
     "l'info est faux ou invérifiable."),
    ("fraicheur", "Contrôleur de fraîcheur",
     "Dis si l'info est fraîche : les sources datent-elles des dernières 48 h, et le fait principal de moins de 30 jours ? "
     "Un fait ancien présenté comme nouveau est « corriger » (préciser la date) ou « bloquer » s'il n'apporte rien de neuf."),
    ("qualite", "Secrétaire de rédaction",
     "Note la qualité de 0 à 10 : français impeccable, titre exact et accrocheur sans mentir, phrases complètes, respect "
     "de la charte. Propose un texte amélioré seulement si la note est sous 7."),
]
PROMPT_AVIS = ('Réponds seulement en JSON : {"verdict": "ok|corriger|bloquer", "note": 0-10, '
               '"remarques": ["courtes, factuelles"], "texte_corrige": "ou null"}')


def tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS redaction_agents (id SERIAL PRIMARY KEY, nom VARCHAR(40) UNIQUE NOT NULL,
              role VARCHAR(120) NOT NULL, consigne TEXT NOT NULL, mode VARCHAR(10) NOT NULL DEFAULT 'actif',
              cree_par VARCHAR(20) NOT NULL DEFAULT 'fondateur', utiles INTEGER NOT NULL DEFAULT 0,
              avis INTEGER NOT NULL DEFAULT 0, cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    db.run("""CREATE TABLE IF NOT EXISTS redaction_avis (id SERIAL PRIMARY KEY, post_id INTEGER NULL, sujet VARCHAR(160) NOT NULL,
              agent VARCHAR(40) NOT NULL, verdict VARCHAR(10) NOT NULL, note INTEGER NULL, remarques TEXT NULL,
              applique BOOLEAN NOT NULL DEFAULT FALSE, cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    db.run("""CREATE TABLE IF NOT EXISTS redaction_lecons (id SERIAL PRIMARY KEY, sujet VARCHAR(20) NOT NULL, texte TEXT NOT NULL,
              preuve TEXT NULL, source VARCHAR(40) NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE,
              cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    for nom, role, consigne in BASE:
        db.run("INSERT INTO redaction_agents (nom, role, consigne) VALUES (?, ?, ?) ON CONFLICT (nom) DO NOTHING", [nom, role, consigne])


def client():
    """DeepSeek d'abord (rapide, peu coûteux) ; solde épuisé ou panne : la chaîne d'IA habituelle (Gemini, Groq…)."""
    from core.services import ai
    chaine = [c for c in (ai.DeepSeekClient(HttpClient(90)), ai.make()) if c and c.is_available()]
    return ai.FallbackClient(chaine) if chaine else None


def agents(modes=("actif", "essai")) -> list:
    return db.all(f"SELECT * FROM redaction_agents WHERE mode IN ({', '.join('?' for _ in modes)}) ORDER BY id", list(modes))


def consignes(sujet: str) -> str:
    """Leçons actives à ajouter aux consignes d'un rédacteur IA (« monde », « studio », « classement » ou « tous »)."""
    try:
        lecons = db.all("SELECT texte FROM redaction_lecons WHERE active AND sujet IN (?, 'tous') ORDER BY id DESC LIMIT 8", [sujet])
    except Exception:  # noqa: BLE001 — tables pas encore créées
        return ""
    return ("\n\nLeçons de notre rédaction (ce qui marche chez nous) :\n" + "\n".join(f"- {x['texte']}" for x in lecons)) if lecons else ""


def _avis(ia, agent: dict, texte: str, sources: str, contexte: str) -> dict:
    r = ia.ask(CHARTE + f"\n\nTu es « {agent['role']} ». {agent['consigne']}\n{PROMPT_AVIS}",
               f"CONTEXTE : {contexte}\nDate du jour : {datetime.now(timezone.utc):%d/%m/%Y}\n\nTEXTE :\n{texte[:3000]}\n\n"
               f"SOURCES :\n{sources[:6000] or '(aucune source fournie)'}", 700)
    from core.services import ai
    d = ai.extract_json(r["text"]) or {}
    v = d.get("verdict") if d.get("verdict") in ("ok", "corriger", "bloquer") else "ok"
    return {"verdict": v, "note": d.get("note") if isinstance(d.get("note"), int) else None,
            "remarques": [str(x)[:300] for x in (d.get("remarques") or [])][:5],
            "texte_corrige": d.get("texte_corrige") if isinstance(d.get("texte_corrige"), str) else None}


def relire(texte: str, sources: str, sujet: str, contexte: str = "", post_id: int | None = None) -> dict:
    """Passe un texte devant tous les agents. Renvoie {"verdict", "texte", "avis": [...]} :
    un « bloquer » d'un agent actif bloque ; « corriger » remplace le texte par la version corrigée (agents actifs)."""
    tables()
    ia = client()
    final, verdict, tous = texte, "ok", []
    if not ia:
        return {"verdict": "ok", "texte": texte, "avis": []}
    for a in agents():
        try:
            x = _avis(ia, a, final, sources, contexte)
        except (PlatformException, Exception) as exc:  # noqa: BLE001 — un agent en panne ne bloque pas la publication
            log_write("redaction", "warning", f"{a['nom']} : {exc}")
            continue
        actif = a["mode"] == "actif"
        applique = False
        if actif and x["verdict"] == "bloquer":
            verdict = "bloquer"
        elif actif and x["verdict"] == "corriger" and x["texte_corrige"] and len(x["texte_corrige"]) > 20:
            final, applique = x["texte_corrige"], True
            verdict = "corriger" if verdict == "ok" else verdict
        db.insert("redaction_avis", {"post_id": post_id, "sujet": sujet[:160], "agent": a["nom"], "verdict": x["verdict"],
                                     "note": x["note"], "remarques": json.dumps(x["remarques"], ensure_ascii=False),
                                     "applique": applique})
        db.run("UPDATE redaction_agents SET avis = avis + 1, utiles = utiles + ? WHERE id = ?",
               [1 if x["verdict"] != "ok" and x["remarques"] else 0, a["id"]])
        tous.append({"agent": a["nom"], "mode": a["mode"], **x})
    return {"verdict": verdict, "texte": final, "avis": tous}


def fiche_monde(f: dict) -> dict | None:
    """Garde-fou de Cauri Monde : la fiche (titre + résumé) face à ses articles. None = bloquée, sinon la fiche corrigée."""
    sources = "\n".join(f"- {it.get('source', '')} ({str(it.get('date', ''))[:16]}) : {it.get('title', '')} — "
                        f"{str(it.get('summary') or it.get('description') or '')[:400]}" for it in (f.get("items") or [])[:6])
    texte = f"TITRE : {f.get('titre', '')}\nRÉSUMÉ : {f.get('resume', '')}"
    r = relire(texte, sources, f"monde : {f.get('titre', '')}", "post Cauri Monde (actu musicale mondiale)")
    if r["verdict"] == "bloquer":
        log_write("redaction", "warning", f"Cauri Monde bloqué : {f.get('titre')} — " +
                  " ; ".join(m for a in r["avis"] for m in a["remarques"])[:400])
        return None
    if r["texte"] != texte and "RÉSUMÉ :" in r["texte"]:
        titre, _, resume = r["texte"].partition("RÉSUMÉ :")
        f = {**f, "titre": titre.replace("TITRE :", "").strip() or f["titre"], "resume": resume.strip() or f["resume"]}
    return f


# ---------------------------------------------------------------- la boucle d'amélioration (chaque semaine)

def _performances(jours: int = 28) -> list:
    """Vues et interactions moyennes par famille de post (thème sans numéro), réseau, heure de publication."""
    lignes = db.all("""SELECT p.theme, m.channel, m.sent_at, m.metrics FROM post_metrics m
                       JOIN audit_log a ON a.action = 'buffer.post' AND a.data LIKE '%' || m.buffer_post_id || '%'
                       JOIN social_posts p ON a.entity_id = CAST(p.id AS TEXT)
                       WHERE m.sent_at >= ?""", [datetime.now(timezone.utc) - timedelta(days=jours)])
    familles = {}
    for x in lignes:
        try:
            m = json.loads(x["metrics"] or "{}")
        except ValueError:
            continue
        fam = "-".join(p for p in str(x["theme"] or "?").split("-") if not p.isdigit())[:30]
        cle = (fam, x["channel"], (x["sent_at"].hour if hasattr(x["sent_at"], "hour") else None))
        f = familles.setdefault(cle, {"posts": 0, "vues": 0, "interactions": 0})
        f["posts"] += 1
        f["vues"] += int(m.get("impressions") or m.get("views") or m.get("reach") or 0)
        f["interactions"] += sum(int(m.get(k) or 0) for k in ("reactions", "likes", "comments", "shares", "saves"))
    return sorted(({"famille": k[0], "reseau": k[1], "heure": k[2], **v} for k, v in familles.items() if v["posts"] >= 2),
                  key=lambda r: -r["vues"] / r["posts"])[:60]


def analyste() -> list:
    """Ce qui marche : 3 à 5 leçons chiffrées, ajoutées aux consignes des rédacteurs (les anciennes sont remplacées)."""
    tables()
    perf, ia = _performances(), client()
    if not perf or not ia:
        return ["analyste : pas assez de statistiques"]
    from core.services import ai
    r = ia.ask(CHARTE + "\n\nTu es l'analyste d'audience. À partir des chiffres, tire 3 à 5 leçons concrètes et applicables "
               "par nos rédacteurs (format, sujet, heure, réseau). Chaque leçon cite ses chiffres. Jamais de leçon qui irait "
               'contre la charte. JSON : {"lecons": [{"sujet": "monde|studio|classement|tous", "texte": "...", "preuve": "..."}]}',
               json.dumps(perf, ensure_ascii=False, default=str), 1200)
    lecons = (ai.extract_json(r["text"]) or {}).get("lecons") or []
    if lecons:
        db.run("UPDATE redaction_lecons SET active = FALSE WHERE source = 'analyste'")
    for l in lecons[:5]:
        if l.get("texte"):
            db.insert("redaction_lecons", {"sujet": l.get("sujet") if l.get("sujet") in ("monde", "studio", "classement") else "tous",
                                           "texte": str(l["texte"])[:400], "preuve": str(l.get("preuve") or "")[:400],
                                           "source": "analyste"})
    return [f"analyste : {len(lecons)} leçon(s)"] + [f"  - {l.get('texte')}" for l in lecons[:5]]


def directeur() -> list:
    """Relit le travail des agents de la semaine : promeut ou retire les agents à l'essai, en crée un s'il manque un contrôle."""
    tables()
    ia = client()
    if not ia:
        return []
    from core.services import ai
    bilan = db.all("""SELECT a.nom, a.role, a.mode, a.cree_par, a.avis, a.utiles, a.cree_le,
                             (SELECT string_agg(left(v.remarques, 160), ' | ') FROM (SELECT remarques FROM redaction_avis
                              WHERE agent = a.nom AND verdict <> 'ok' ORDER BY id DESC LIMIT 5) v) AS exemples
                      FROM redaction_agents a WHERE a.mode <> 'retire'""")
    bloques = db.all("SELECT sujet, agent, remarques FROM redaction_avis WHERE verdict = 'bloquer' AND cree_le > ? LIMIT 15",
                     [datetime.now(timezone.utc) - timedelta(days=7)])
    r = ia.ask(CHARTE + "\n\nTu es le directeur de la rédaction. Tu relis le travail de tes agents. Décide : promouvoir "
               "(essai → actif) un agent utile depuis 2 semaines, retirer un agent qui ne trouve rien d'utile, et créer AU PLUS "
               "un nouvel agent si un contrôle manque (il commencera à l'essai, sans rien bloquer). Les agents de base "
               "(verite, fraicheur, qualite) ne se retirent jamais. "
               'JSON : {"promouvoir": ["nom"], "retirer": ["nom"], "nouvel_agent": {"nom": "court_sans_espace", "role": "...", '
               '"consigne": "..."} ou null, "mot": "une phrase pour le fondateur"}',
               json.dumps({"agents": bilan, "bloques_semaine": bloques}, ensure_ascii=False, default=str)[:12000], 900)
    d = ai.extract_json(r["text"]) or {}
    out = []
    base = {n for n, _, _ in BASE}
    for nom in d.get("promouvoir") or []:
        if db.run("UPDATE redaction_agents SET mode = 'actif' WHERE nom = ? AND mode = 'essai' AND cree_le < ?",
                  [nom, datetime.now(timezone.utc) - timedelta(days=14)]):
            out.append(f"directeur : {nom} promu (actif)")
    for nom in d.get("retirer") or []:
        if nom not in base and db.run("UPDATE redaction_agents SET mode = 'retire' WHERE nom = ? AND mode <> 'retire'", [nom]):
            out.append(f"directeur : {nom} retiré")
    n = d.get("nouvel_agent") or {}
    if n.get("nom") and n.get("consigne") and len(agents(("essai",))) < 3:
        nom = "".join(c for c in str(n["nom"]).lower() if c.isalnum() or c == "_")[:40]
        if nom and db.run("INSERT INTO redaction_agents (nom, role, consigne, mode, cree_par) VALUES (?, ?, ?, 'essai', 'directeur') "
                          "ON CONFLICT (nom) DO NOTHING", [nom, str(n.get("role") or nom)[:120], str(n["consigne"])[:1500]]):
            out.append(f"directeur : nouvel agent à l'essai « {nom} » — {n.get('role')}")
    if d.get("mot"):
        out.append(f"directeur : {d['mot']}")
    return out or ["directeur : rien à changer"]


def relecture_du_jour() -> list:
    """Chaque matin : les posts des dernières 24 h et ceux à venir passent devant le comité (avis, sans bloquer après coup)."""
    tables()
    out = []
    for p in db.all("""SELECT id, title, caption, facts FROM social_posts WHERE created_at >= ? AND status IN ('approved', 'draft')
                       AND id NOT IN (SELECT post_id FROM redaction_avis WHERE post_id IS NOT NULL) ORDER BY id DESC LIMIT 12""",
                    [datetime.now(timezone.utc) - timedelta(days=1)]):
        try:
            faits = json.loads(p["facts"] or "{}")
        except ValueError:
            faits = {}
        sources = json.dumps({k: v for k, v in faits.items() if k not in ("en", "ranks")}, ensure_ascii=False, default=str)
        r = relire(f"{p['title']}\n\n{p['caption']}", sources, p["title"] or "post", "post publié par Cauri Charts", p["id"])
        notes = [a["note"] for a in r["avis"] if a.get("note") is not None]
        out.append(f"post {p['id']} « {(p['title'] or '')[:50]} » : {r['verdict']}" + (f", note {min(notes)}/10" if notes else ""))
    return out
