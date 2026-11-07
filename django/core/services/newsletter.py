"""Newsletter Cauri Charts (06/11/2026) : inscription en double confirmation, lettre du vendredi après le classement.

- inscrire() : adresse enregistrée « en attente », e-mail de confirmation avec un lien unique ; rien n'est envoyé ensuite
  tant que la personne n'a pas cliqué (preuve du consentement, exigée par la loi et par les messageries).
- confirmer() / desinscrire() : par le jeton de l'abonné, un clic suffit ; chaque lettre porte le lien de désinscription.
- lettre() : les N°1 officiels de la semaine publiée, pays par pays, et le Top 5 Afrique de l'Ouest, en français ou en
  anglais selon la langue d'inscription. Envoi par le SMTP du site, une adresse à la fois.
"""
import hashlib
import re
import secrets
import time

from core import conf, db, mail

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$", re.I)


def table() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS newsletter (id SERIAL PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
              langue VARCHAR(2) NOT NULL DEFAULT 'fr', statut VARCHAR(12) NOT NULL DEFAULT 'attente', jeton VARCHAR(64) NOT NULL,
              source VARCHAR(40) NULL, ip_hash VARCHAR(64) NULL, cree_le TIMESTAMPTZ DEFAULT NOW(), confirme_le TIMESTAMPTZ NULL,
              desinscrit_le TIMESTAMPTZ NULL, derniere_lettre DATE NULL)""")


def _base() -> str:
    return conf.get("app.url")


def inscrire(email: str, langue: str = "fr", source: str = "site", ip: str = "") -> str:
    """'ok' (e-mail de confirmation envoyé), 'deja' (déjà abonné), 'invalide' ou 'trop' (trop d'essais)."""
    table()
    email = (email or "").strip().lower()
    if not EMAIL.match(email):
        return "invalide"
    langue = "en" if langue == "en" else "fr"
    ip_hash = hashlib.sha256(("cauri:" + (ip or "")).encode()).hexdigest() if ip else None
    if ip_hash and int(db.value("SELECT COUNT(*) FROM newsletter WHERE ip_hash = ? AND cree_le > NOW() - INTERVAL '1 hour'", [ip_hash]) or 0) >= 5:
        return "trop"
    ligne = db.one("SELECT * FROM newsletter WHERE email = ?", [email])
    if ligne and ligne["statut"] == "actif":
        return "deja"
    jeton = secrets.token_urlsafe(32)
    if ligne:
        db.run("UPDATE newsletter SET statut = 'attente', jeton = ?, langue = ?, desinscrit_le = NULL WHERE id = ?", [jeton, langue, ligne["id"]])
    else:
        db.run("INSERT INTO newsletter (email, langue, jeton, source, ip_hash) VALUES (?, ?, ?, ?, ?)", [email, langue, jeton, source[:40], ip_hash])
    lien = f"{_base()}{'/en' if langue == 'en' else ''}/newsletter/confirmer/{jeton}"
    if langue == "en":
        sujet, texte = "Confirm your Cauri Charts newsletter", (
            "Hello,\n\nPlease confirm your subscription to the Cauri Charts newsletter: every Friday, the official No. 1 "
            f"in each West African country and the West Africa Top 5.\n\nConfirm: {lien}\n\n"
            "If you did not ask for it, ignore this email: nothing will be sent.")
    else:
        sujet, texte = "Confirmez votre inscription à la newsletter Cauri Charts", (
            "Bonjour,\n\nConfirmez votre inscription à la newsletter Cauri Charts : chaque vendredi, les N°1 officiels de "
            f"chaque pays d'Afrique de l'Ouest et le Top 5 de la région.\n\nConfirmer : {lien}\n\n"
            "Si vous n'avez rien demandé, ignorez ce message : rien ne vous sera envoyé.")
    mail.send(email, sujet, texte)
    return "ok"


def confirmer(jeton: str) -> dict | None:
    table()
    ligne = db.one("SELECT * FROM newsletter WHERE jeton = ?", [jeton or ""])
    if not ligne:
        return None
    if ligne["statut"] != "actif":
        db.run("UPDATE newsletter SET statut = 'actif', confirme_le = NOW() WHERE id = ?", [ligne["id"]])
    return ligne


def desinscrire(jeton: str) -> dict | None:
    table()
    ligne = db.one("SELECT * FROM newsletter WHERE jeton = ?", [jeton or ""])
    if ligne and ligne["statut"] != "desinscrit":
        db.run("UPDATE newsletter SET statut = 'desinscrit', desinscrit_le = NOW() WHERE id = ?", [ligne["id"]])
    return ligne


def _contenu(langue: str) -> tuple[str, str, str] | None:
    """(sujet, texte, html) de la dernière semaine publiée, ou None s'il n'y a rien de publié."""
    from core import repos  # noqa: F401  (chargement des pays)
    semaine = db.value("""SELECT r.period_key FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code = 'prime'
                          WHERE r.status = 'published' AND r.period_type = 'week' ORDER BY r.period_start DESC LIMIT 1""")
    if not semaine:
        return None
    n1 = db.all("""SELECT c.code, c.name_fr, c.name_en, t.title, a.name AS artiste, t.slug
                   FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id AND ct.code = 'prime'
                   JOIN countries c ON c.id = r.country_id JOIN chart_entries e ON e.chart_run_id = r.id AND e.position = 1
                   JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
                   WHERE r.status = 'published' AND r.period_key = ? ORDER BY c.sort_order""", [semaine])
    top = db.all("""SELECT e.position, t.title, a.name AS artiste FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
                    AND ct.code = 'prime-wa' JOIN chart_entries e ON e.chart_run_id = r.id JOIN tracks t ON t.id = e.track_id
                    JOIN artists a ON a.id = t.artist_id WHERE r.status = 'published' AND r.period_key = ? AND e.position <= 5
                    ORDER BY e.position""", [semaine])
    base, en = _base(), langue == "en"
    lien = base + ("/en" if en else "") + "/classements/afrique-de-l-ouest"
    sujet = (f"The No. 1s of West Africa · {semaine}" if en else f"Les N°1 de l'Afrique de l'Ouest · {semaine}")
    lignes_n1 = [f"{(x['name_en'] if en else x['name_fr'])} : {x['title']} — {x['artiste']}" for x in n1]
    lignes_top = [f"{x['position']}. {x['title']} — {x['artiste']}" for x in top]
    titre_n1, titre_top = ("No. 1 in each country", "West Africa Top 5") if en else ("Le N°1 de chaque pays", "Top 5 Afrique de l'Ouest")
    texte = "\n".join([sujet, "", titre_top, *lignes_top, "", titre_n1, *lignes_n1, "", lien])
    from markupsafe import escape as e
    li = lambda xs: "".join(f'<li style="margin:4px 0">{e(x)}</li>' for x in xs)  # noqa: E731
    html = f"""<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:auto;color:#14112B">
<div style="background:linear-gradient(135deg,#1B1150,#5B2BD6);color:#fff;padding:26px;border-radius:18px">
<p style="margin:0;font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.8">Cauri Charts · {e(semaine)}</p>
<h1 style="margin:8px 0 0;font-size:24px">{e(sujet)}</h1></div>
<h2 style="font-size:16px;margin:22px 0 6px">{e(titre_top)}</h2><ol style="padding-left:18px;margin:0">{"".join(f'<li style="margin:4px 0">{e(x["title"])} — {e(x["artiste"])}</li>' for x in top)}</ol>
<h2 style="font-size:16px;margin:22px 0 6px">{e(titre_n1)}</h2><ul style="padding-left:18px;margin:0">{li(lignes_n1)}</ul>
<p style="margin:24px 0"><a href="{e(lien)}" style="background:#7A3CF5;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">{"See the full charts" if en else "Voir tous les classements"}</a></p>
</div>"""
    return sujet, texte, html


def envoyer(limite: int = 500) -> list:
    """Lettre de la semaine à chaque abonné confirmé qui ne l'a pas encore reçue aujourd'hui."""
    table()
    abonnes = db.all("""SELECT id, email, langue, jeton FROM newsletter WHERE statut = 'actif'
                        AND (derniere_lettre IS NULL OR derniere_lettre < CURRENT_DATE) ORDER BY id LIMIT ?""", [limite])
    contenus, envoyes = {}, 0
    for a in abonnes:
        if a["langue"] not in contenus:
            contenus[a["langue"]] = _contenu(a["langue"])
        c = contenus[a["langue"]]
        if not c:
            return ["Newsletter : aucun classement publié"]
        sujet, texte, html = c
        stop = f"{_base()}{'/en' if a['langue'] == 'en' else ''}/newsletter/desinscription/{a['jeton']}"
        pied = ("Unsubscribe" if a["langue"] == "en" else "Se désinscrire") + " : " + stop
        html_a = html + f'<p style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#777;text-align:center"><a href="{stop}" style="color:#777">{pied.split(" : ")[0]}</a></p>'
        if mail.send_html(a["email"], sujet, texte + "\n\n" + pied, html_a, desinscription=stop):
            db.run("UPDATE newsletter SET derniere_lettre = CURRENT_DATE WHERE id = ?", [a["id"]])
            envoyes += 1
        time.sleep(1)   # le SMTP de l'hébergeur limite le débit
    return [f"Newsletter : {envoyes} lettre(s) envoyée(s) sur {len(abonnes)} abonné(s)"]


def chiffres() -> dict:
    table()
    return {r["statut"]: int(r["n"]) for r in db.all("SELECT statut, COUNT(*) n FROM newsletter GROUP BY statut")}
