"""Post hebdomadaire du classement officiel (mardi 17 h), au style 2026 validé le 19/10/2026.

Pour chaque pays publié cette semaine : une couverture « lockup » du n°1 (façon ChartFR) puis la liste du classement.
Photo du n°1 : un plan large VALIDÉ (artist_photos), sinon le portrait officiel ; jamais une miniature YouTube.
"""
from datetime import date, datetime, timezone

from core import db, repos
from core.helpers import country_name

PREPOSITION = {"CI": "en Côte d'Ivoire", "GN": "en Guinée", "GW": "en Guinée-Bissau", "SL": "en Sierra Leone",
               "GM": "en Gambie", "MR": "en Mauritanie"}   # sinon « au » (au Togo, au Ghana, au Nigeria, au Sénégal…)


def _au(code: str) -> str:
    return PREPOSITION.get(code, "au " + country_name(code))


def _vues(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}".replace(".", ",").replace(",0", "") + " millions de vues cette semaine"
    return f"{n:,}".replace(",", " ") + " vues cette semaine"


def _photo(top: dict):
    from core.services.social import plans
    a_id = db.value("SELECT id FROM artists WHERE slug = ?", [top.get("artist_slug")])
    return (plans.photo_large(a_id) if a_id else None) or top.get("image")


def post(jour: date, due: datetime, essai: bool = False) -> dict | None:
    from core.services.social import couverture2026 as C
    from core.services.social import editorial as E
    from core.services.social import image as PI
    tops = [t for t in repos.official_tops(16) if t.get("rows")]
    if not tops:
        return None
    semaine = tops[0]["period_key"]
    if not essai and (jour - date.fromisoformat(str(tops[0]["period_end"])[:10])).days > 3:
        return None   # la semaine écoulée n'est pas encore publiée : jamais republier une ancienne semaine
    if not essai and db.value("SELECT 1 FROM social_posts WHERE theme = 'format-officiel' AND title LIKE ?", [f"%{semaine}%"]):
        return None   # déjà publié pour cette semaine
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{jour.isoformat()}-officiel-{datetime.now(timezone.utc):%H%M%S}"
    fichiers, lignes_legende = [], []
    for k, t in enumerate(tops[:4]):   # 4 pays au plus : 8 diapositives
        n1 = t["rows"][0]
        vues = _vues(int(n1.get("views") or 0))
        lignes = [(f"CLASSEMENT OFFICIEL · {country_name(t['code']).upper()} :", "petit"),
                  (n1["title"].split(" (")[0].upper(), "or"), (f"de {n1['artist_name']} est", "petit"),
                  ("LE TITRE LE PLUS VU", "moyen"), (_au(t["code"]).upper(), "grand"), (vues, "petit")]
        photo = _photo(n1)
        debut, fin = t["period_start"], t["period_end"]
        sous = f"Classement officiel Cauri Charts · {debut[8:10]}/{debut[5:7]} – {fin[8:10]}/{fin[5:7]}"
        for fmt, suffixe in (("feed", ""), ("story", "-916")):
            PI.save_jpeg(C.lockup(photo, lignes, fmt), PI.DIR / f"{nom}-{k}a{suffixe}.jpg")
            PI.save_jpeg(C.classement(t["rows"], f"Top {country_name(t['code'])}", sous, fmt), PI.DIR / f"{nom}-{k}b{suffixe}.jpg")
        fichiers += [{"file": f"{nom}-{k}a.jpg", "tiktok": f"{nom}-{k}a-916.jpg", "label": f"N°1 {country_name(t['code'])}"},
                     {"file": f"{nom}-{k}b.jpg", "tiktok": f"{nom}-{k}b-916.jpg", "label": f"Top {country_name(t['code'])}"}]
        lignes_legende.append(f"🥇 {country_name(t['code'])} : « {n1['title']} » de {n1['artist_name']} ({vues})")
    if essai:
        return {"fichiers": [str(PI.DIR / f["file"]) for f in fichiers]}
    legende = (f"🏆 Le classement officiel Cauri Charts de la semaine ({semaine}).\n\n" + "\n".join(lignes_legende)
               + "\n\nVues YouTube des clips officiels sur la semaine, contrôles anti-fraude appliqués. "
                 "Le top complet de chaque pays sur cauricharts.com.")
    return E.save_post("format-officiel", jour.isoformat(), f"Classement officiel {semaine}", legende,
                       "#CauriCharts #ClassementOfficiel #Afrobeats #MusiqueAfricaine", fichiers,
                       {"cle": semaine, "due": due.isoformat(), "kind": "format-officiel"})
