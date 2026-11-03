"""Veille des pages d'actu sur X et Instagram (03/11/2026, demande du fondateur : « des pages comme oriiinfos, actulome
et Twitter pourraient nous apporter beaucoup d'actu »).

Par Apify, une lecture par jour au plus (gardée en base pour l'édition du soir) :
  X         : kaitoeasyapi (0,00025 $ le tweet), recherche « from:compte since:hier »
  Instagram : apify/instagram-post-scraper (0,0017 $ le post)
Coût visé : ~1,20 $ par mois, dans le plafond Apify commun (spotify_apify.PLAFOND_MOIS). Les posts deviennent des
articles candidats pour Cauri Monde (monde.collecte), qui garde la musique et rédige un titre choc et vrai.
"""
import json
from datetime import datetime, timedelta, timezone

from core import conf, db

X_ACTEUR = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
IG_ACTEUR = "apify~instagram-post-scraper"
PRIX_TWEET, PRIX_POST = 0.00025, 0.0017
COMPTES = {
    "x": ["notjustok", "AmeyawDebrah", "PulseNigeria247", "instablog9ja"],
    "instagram": ["notjustok", "pulsenigeria247", "instablog9ja"],
}


def comptes() -> dict:
    return conf.get("veille") or COMPTES


def _table() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS veille_posts (id SERIAL PRIMARY KEY, plateforme VARCHAR(12) NOT NULL, compte VARCHAR(80) NOT NULL,
              ext_id VARCHAR(80) NOT NULL, texte TEXT, url VARCHAR(500), image VARCHAR(500), publie_le TIMESTAMPTZ,
              releve_le TIMESTAMPTZ DEFAULT NOW(), UNIQUE (plateforme, ext_id))""")


def _date(v):
    if not v:
        return None
    for f in ("%a %b %d %H:%M:%S %z %Y",):
        try:
            return datetime.strptime(str(v), f)
        except ValueError:
            pass
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def releve(force: bool = False) -> list:
    """Lit les comptes suivis (une fois par jour au plus) et garde les posts en base."""
    from core.services import spotify_apify as A
    _table()
    if not force and db.value("SELECT 1 FROM veille_posts WHERE releve_le > NOW() - INTERVAL '20 hours' LIMIT 1"):
        return ["veille réseaux : déjà relevée aujourd'hui"]
    c, lignes, n = comptes(), [], 0
    hier = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    if c.get("x"):
        try:
            res = A._lance(X_ACTEUR, {"searchTerms": [f"from:{x} since:{hier}" for x in c["x"]], "maxItems": 20 * len(c["x"]),
                                      "queryType": "Latest"}, PRIX_TWEET * 20 * len(c["x"]))
            for t in res or []:
                if not t.get("id") or (t.get("retweetedTweet") or str(t.get("text", "")).startswith("RT @")):
                    continue
                auteur = (t.get("author") or {}).get("userName") or ""
                media = ((t.get("extendedEntities") or {}).get("media") or [{}])[0].get("media_url_https")
                n += db.run("""INSERT INTO veille_posts (plateforme, compte, ext_id, texte, url, image, publie_le) VALUES ('x', ?, ?, ?, ?, ?, ?)
                               ON CONFLICT DO NOTHING""",
                            [auteur[:80], str(t["id"])[:80], t.get("text") or "", (t.get("url") or f"https://x.com/{auteur}/status/{t['id']}")[:500],
                             (media or "")[:500] or None, _date(t.get("createdAt"))]) or 0
            lignes.append(f"X : {len(res or [])} tweets lus")
        except Exception as exc:  # noqa: BLE001 — une source en panne ne bloque pas l'édition
            lignes.append(f"X : {str(exc)[:120]}")
    if c.get("instagram"):
        try:
            res = A._lance(IG_ACTEUR, {"username": c["instagram"], "resultsLimit": 4, "onlyPostsNewerThan": "2 days"},
                           PRIX_POST * 4 * len(c["instagram"]))
            for p in res or []:
                if not p.get("id"):
                    continue
                n += db.run("""INSERT INTO veille_posts (plateforme, compte, ext_id, texte, url, image, publie_le) VALUES ('instagram', ?, ?, ?, ?, ?, ?)
                               ON CONFLICT DO NOTHING""",
                            [(p.get("ownerUsername") or "")[:80], str(p["id"])[:80], p.get("caption") or "", (p.get("url") or "")[:500],
                             (p.get("displayUrl") or "")[:500] or None, _date(p.get("timestamp"))]) or 0
            lignes.append(f"Instagram : {len(res or [])} posts lus")
        except Exception as exc:  # noqa: BLE001
            lignes.append(f"Instagram : {str(exc)[:120]}")
    lignes.insert(0, f"veille réseaux : {n} post(s) nouveaux · Apify {A.depense():.2f} $ ce mois")
    return lignes


def items(heures: int = 36) -> list:
    """Posts récents au format des articles de Cauri Monde (titre, résumé, lien, date, source)."""
    try:
        _table()
        lignes = db.all("""SELECT plateforme, compte, texte, url, image, publie_le FROM veille_posts
                           WHERE COALESCE(publie_le, releve_le) > NOW() - make_interval(hours => ?) ORDER BY publie_le DESC LIMIT 200""",
                        [heures])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for r in lignes:
        texte = " ".join(str(r["texte"] or "").split())
        if len(texte) < 25:
            continue   # un emoji, une vidéo sans légende : rien à raconter
        titre = texte.split(". ")[0][:160]
        out.append({"title": titre, "summary": texte[:600], "url": r["url"], "image": r["image"],
                    "published_at": str(r["publie_le"]) if r["publie_le"] else None,
                    "source": f"@{r['compte']} sur {'X' if r['plateforme'] == 'x' else 'Instagram'}", "poids": 2, "afrique": True})
    return out
