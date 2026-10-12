"""Formats récurrents inspirés des grands médias rap (RapTV…), sur NOS données réelles uniquement :

  - versus      : deux artistes face à face, leurs vrais chiffres (Spotify via Kworb, YouTube, Deezer, classements Cauri) ;
  - top10       : « Ses 10 titres les plus écoutés, classés » (compteurs publics de Spotify, via Kworb) ;
  - qui_est     : « Qui est X ? » — une révélation de nos classements (bio Wikipédia si elle existe, chiffres Cauri) ;
  - promo       : « La promo Cauri » — les talents émergents du mois (rubrique Révélations) ;
  - power       : le classement mensuel des artistes (Top artistes Cauri), le 1er du mois.

Chaque post finit par une question au public. Rendu : couverture choc sur vraies photos (monde.couverture_choc).
Les posts sont enregistrés avec leur heure (« due ») et partent un par un via la file d'attente (monde.publie_file).
Calendrier (heure de Lomé) : lundi 21 h top10, mercredi 21 h versus, vendredi 21 h qui_est, 1er du mois 12 h power,
1er lundi du mois 12 h promo."""
import json
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from core import db
from core.helpers import country_name
from core.services.platforms import log_write
from core.services.social import monde as M

VIOLET, BLEU, ROUGE, OR, NUIT = (139, 82, 255), (20, 120, 210), (229, 33, 59), (255, 190, 40), (20, 20, 30)
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _deja(theme: str, cle: str, semaines: int = 12) -> bool:
    """Ce sujet (artiste, duo…) a-t-il déjà eu ce format ces dernières semaines ?"""
    for r in db.all("SELECT facts FROM social_posts WHERE theme = ? AND slot_date >= CURRENT_DATE - ?", [theme, semaines * 7]):
        try:
            if json.loads(r["facts"]).get("cle") == cle:
                return True
        except (ValueError, TypeError):
            pass
    return False


def _post(theme: str, jour: date, due: datetime, titre: str, pages: list, legende: str, hashtags: str, cle: str) -> dict:
    """pages : [(fiche, kicker, diapo)] → images 4:5 et 9:16, post enregistré avec son heure de départ."""
    from core.services.social import editorial as E
    from core.services.social import image as PI
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{jour.isoformat()}-{theme}-{datetime.now(timezone.utc):%H%M%S}"
    M.STYLE_GRAINE = nom   # un même style (police, couleurs, mise en page) sur toutes les images du post
    fichiers = []
    for n, (f, kk, dp) in enumerate(pages):
        a = PI.save_jpeg(M.couverture_choc(f, kk, False, "feed", dp), PI.DIR / f"{nom}-{n}.jpg")
        b = PI.save_jpeg(M.couverture_choc(f, kk, False, "tiktok", dp), PI.DIR / f"{nom}-{n}-916.jpg")
        fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": (dp or {}).get("titre") or f.get("une") or titre})
    return E.save_post(theme, jour.isoformat(), titre, legende, hashtags, fichiers, {"cle": cle, "due": due.isoformat(), "kind": theme})


def _fiche(artiste: str, une: str, titre: str, sources: list, cle: str) -> dict:
    return {"artiste": artiste, "une": une, "titre": titre, "sources": sources, "cle": cle}


def _diapo(etiquette, couleur, titre, texte, graine, fond=None) -> dict:
    return {"etiquette": etiquette, "couleur": couleur, "titre": titre, "texte": texte, "graine": graine, "fond": fond}


def _fin(question: str, graine: str) -> tuple:
    return (_fiche("", "", "", [], graine), "À vous ‼️", _diapo("CAURI CHARTS", NUIT, question, "Répondez en commentaire. Cauri Charts, la référence de la musique ouest-africaine.", "fin"))


def _nos_artistes_spotify() -> list:
    """Nos artistes suivis par Kworb, classés par auditeurs mensuels : [(ligne artiste, auditeurs)]."""
    from core.services import kworb
    aud = kworb.auditeurs()
    rows = db.all("""SELECT a.*, COALESCE(a.base_country, gc.code) AS country FROM artists a
                     LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                     WHERE a.status = 'active' AND a.spotify_id IS NOT NULL AND a.spotify_id <> ''""")
    return sorted(((r, aud[r["spotify_id"]][0]) for r in rows if r["spotify_id"] in aud), key=lambda x: -x[1])


def _meilleure_place(artist_id: int) -> str | None:
    from core.services import live_chart
    b = db.one("""SELECT o.position, o.source, c.code FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                  JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 30
                  AND o.source NOT IN ('deezer_popularity', 'youtube_views') ORDER BY o.position LIMIT 1""", [artist_id])
    return f"N°{b['position']} {live_chart.SOURCES.get(b['source'], b['source'])} {country_name(b['code'])}" if b else None


def _duo_photo(nom_a: str, nom_b: str, graine: str):
    """Les deux visages côte à côte (photos Deezer), pour la couverture du versus."""
    from PIL import Image
    from core.services.news import http_get
    from core.services.social import image as PI
    moities = []
    for n in (nom_a, nom_b):
        url = M.photo(n)
        if not url:
            return None
        im = Image.open(BytesIO(http_get(url, binary=True))).convert("RGB")
        c = min(im.width, im.height)
        moities.append(im.crop(((im.width - c) // 2, 0, (im.width + c) // 2, c)))
    # aux proportions du cadre photo de la couverture (2160 × 78 % de 2700) : les deux visages entiers, côte à côte
    W, H = 2160, 2106
    out = Image.new("RGB", (W, H))
    for k, im in enumerate(moities):
        r = max((W // 2) / im.width, H / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)))
        x0 = (im.width - W // 2) // 2
        out.paste(im.crop((x0, 0, x0 + W // 2, H)), (k * (W // 2), 0))
    f = PI.DIR / f"duo-{graine}.jpg"
    PI.DIR.mkdir(parents=True, exist_ok=True)
    out.save(f, quality=90)
    return f


# ---------------------------------------------------------------- 1. versus

def versus(jour: date, due: datetime) -> dict | None:
    from core.services import kworb
    liste = _nos_artistes_spotify()
    paires = [(liste[i], liste[i + 1]) for i in range(len(liste) - 1)]
    paires = [p for p in paires if not _deja("format-versus", f"{p[0][0]['id']}-{p[1][0]['id']}")]
    if not paires:
        return None
    (a, la), (b, lb) = paires[jour.isocalendar()[1] % len(paires)]
    ca, cb = kworb.chiffres(a["spotify_id"]), kworb.chiffres(b["spotify_id"])
    lignes = [("AUDITEURS PAR MOIS", la, lb, kworb.volume)]
    if ca and cb:
        lignes += [("STREAMS AU TOTAL", ca["total"], cb["total"], kworb.volume), ("STREAMS PAR JOUR", ca["jour"], cb["jour"], kworb.volume)]
    if a.get("youtube_subscribers") and b.get("youtube_subscribers"):
        lignes.append(("ABONNÉS YOUTUBE", a["youtube_subscribers"], b["youtube_subscribers"], kworb.volume))
    if a.get("fans") and b.get("fans"):
        lignes.append(("FANS DEEZER", a["fans"], b["fans"], kworb.volume))
    cle = f"{a['id']}-{b['id']}"
    duo = _duo_photo(a["name"], b["name"], cle)
    une = f"{a['name']} VS {b['name']}"
    pages = [(_fiche(a["name"], une, f"Qui pèse le plus ? Les vrais chiffres de {a['name']} et {b['name']}.", ["Spotify", "YouTube", "Deezer"], cle),
              f"Versus · {jour:%d/%m}", _diapo("VERSUS", ROUGE, une, f"Qui pèse le plus ? Les vrais chiffres de {a['name']} et {b['name']}.", "c", duo))]
    for i, (label, va, vb, fmt) in enumerate(lignes):
        gagnant = a["name"] if va >= vb else b["name"]
        pages.append((_fiche(gagnant, "", "", ["Spotify (via Kworb)" if "STREAM" in label or "AUDITEURS" in label else label.split()[-1].title()], cle),
                      f"{i + 2} / {len(lignes) + 2}",
                      _diapo(label, (VIOLET, BLEU)[i % 2], f"{a['name']} {fmt(va)} — {b['name']} {fmt(vb)}",
                             f"Avantage {gagnant}.", f"v{i}", duo if i % 2 else None)))
    question = f"Team {a['name']} ou team {b['name']} ⁉️"
    pages.append(_fin(question, cle))
    legende = (f"🥊 {a['name']} vs {b['name']} : les vrais chiffres.\n\n"
               + "\n".join(f"▪️ {lab.capitalize()} : {a['name']} {f(va)} · {b['name']} {f(vb)}" for lab, va, vb, f in lignes)
               + f"\n\n{question} Votez en commentaire ‼️\n\nSources : Spotify (compteurs publics via Kworb), YouTube, Deezer.")
    return _post("format-versus", jour, due, f"Versus : {a['name']} vs {b['name']}", pages, legende,
                 f"#CauriCharts #Versus #{a['name'].replace(' ', '')} #{b['name'].replace(' ', '')}", cle)


# ---------------------------------------------------------------- 2. ses 10 titres les plus écoutés

def top10(jour: date, due: datetime) -> dict | None:
    from core.services import kworb
    for a, _ in _nos_artistes_spotify():
        if _deja("format-top10", str(a["id"]), 26):
            continue
        c = kworb.chiffres(a["spotify_id"], n_titres=10)
        if not c or len(c["titres"]) < 6:
            continue
        t = c["titres"]
        lignes = [f"N°{i + 1}  {x['titre']} · {kworb.volume(x['streams'])}" for i, x in enumerate(t)]
        cle = str(a["id"])
        une = f"LES {len(t)} TITRES LES PLUS ÉCOUTÉS DE {a['name']}"
        pages = [(_fiche(a["name"], une, f"Classés par streams sur Spotify : {kworb.volume(c['total'])} au total.", ["Spotify (via Kworb)"], cle),
                  f"Classés · {jour:%d/%m}", None)]
        bas, haut = lignes[5:][::-1], lignes[:5][::-1]
        if bas:
            pages.append((_fiche(a["name"], "", "", ["Spotify (via Kworb)"], cle), "2 / 4",
                          _diapo("CLASSÉS", VIOLET, f"N°{len(t)} À N°6", "\n".join(bas), "b", M.objet({"titre": "album", "resume": "", "rubrique": "sorties"}, cle))))
        pages.append((_fiche(a["name"], "", "", ["Spotify (via Kworb)"], cle), "3 / 4", _diapo("CLASSÉS", BLEU, "LE TOP 5", "\n".join(haut), "h")))
        pages.append(_fin(f"Votre préféré dans la liste ⁉️", cle))
        legende = (f"🎧 Les {len(t)} titres de {a['name']} les plus écoutés sur Spotify :\n\n" + "\n".join(lignes)
                   + "\n\nVotre préféré ⁉️ Dites-le en commentaire ‼️\n\nSource : Spotify (compteurs publics relevés par Kworb).")
        return _post("format-top10", jour, due, f"Les 10 titres les plus écoutés de {a['name']}", pages, legende,
                     f"#CauriCharts #{a['name'].replace(' ', '')} #Classement #Spotify", cle)
    return None


# ---------------------------------------------------------------- 3. qui est X ?

def qui_est(jour: date, due: datetime) -> dict | None:
    from core.services.social import portrait as P
    from core.services.social import themes as T
    for e in T.revelations():
        a = db.one("""SELECT a.*, COALESCE(a.base_country, gc.code) AS country FROM artists a
                      LEFT JOIN countries gc ON gc.id = a.guessed_country_id WHERE a.name = ? AND a.status = 'active'""", [e["artist"]])
        if not a or _deja("format-qui-est", str(a["id"]), 52):
            continue
        pays = country_name(a["country"]) if a["country"] else "Afrique de l’Ouest"
        bio = None
        try:
            bio = P.bio(a["name"], P.wikidata_id(a["name"], a["country"]))
            if bio and bio.get("lang") != "fr":
                bio = None   # posts en français : pas de bio en anglais, nos chiffres suffisent
        except Exception:  # noqa: BLE001
            pass
        place = _meilleure_place(a["id"])
        cle = str(a["id"])
        une = f"QUI EST {a['name']} ?"
        du = "du " if pays in ("Togo", "Bénin", "Ghana", "Sénégal", "Nigeria", "Niger", "Mali", "Burkina Faso", "Cap-Vert", "Liberia") else "de "
        texte_bio = (bio["text"][:330] + ("…" if len(bio["text"]) > 330 else "")) if bio else f"Artiste {du}{pays}, en pleine ascension dans nos classements."
        pages = [(_fiche(a["name"], une, f"La révélation qui monte en ce moment ({pays}).", ["Cauri Charts"], cle), f"Révélation · {jour:%d/%m}", None),
                 (_fiche(a["name"], "", "", ["Wikipédia (CC BY-SA)"] if bio else ["Cauri Charts"], cle), "2 / 4",
                  _diapo("SON HISTOIRE", VIOLET, f"{a['name']} · {pays}", texte_bio, "b"))]
        chiffres = [f"Son titre du moment : « {e['title']} »"] + ([f"Sa meilleure place ce mois-ci : {place}"] if place else [])
        if a.get("fans"):
            chiffres.append(f"{int(a['fans']):,} fans sur Deezer".replace(",", " "))
        if a.get("youtube_subscribers"):
            chiffres.append(f"{int(a['youtube_subscribers']):,} abonnés YouTube".replace(",", " "))
        pages.append((_fiche(a["name"], "", "", ["Cauri Charts", "Deezer", "YouTube"], cle), "3 / 4",
                      _diapo("SES CHIFFRES", BLEU, "POURQUOI ON EN PARLE", "\n".join(chiffres), "c", M.objet({"titre": "live micro", "resume": "", "rubrique": ""}, cle))))
        pages.append(_fin(f"Vous connaissiez déjà {a['name']} ⁉️", cle))
        legende = (f"👀 Qui est {a['name']} ? La révélation {('du ' if pays in ('Togo', 'Bénin', 'Ghana', 'Sénégal', 'Nigeria', 'Niger', 'Mali', 'Burkina Faso') else 'de ')}{pays} qui monte dans nos classements.\n\n"
                    + (texte_bio + "\n\n" if bio else "") + "\n".join("▪️ " + c for c in chiffres)
                    + f"\n\nVous le connaissiez déjà ⁉️ ‼️" + ("\n\nBio : Wikipédia (CC BY-SA)." if bio else ""))
        return _post("format-qui-est", jour, due, f"Qui est {a['name']} ?", pages, legende,
                     f"#CauriCharts #Révélation #{a['name'].replace(' ', '')} #AfriqueDeLOuest", cle)
    return None


# ---------------------------------------------------------------- 4. la promo Cauri (talents du mois)

def promo(jour: date, due: datetime) -> dict | None:
    from core.services.social import themes as T
    vus, talents = set(), []
    for e in T.revelations():
        if e["artist"] in vus:
            continue
        vus.add(e["artist"]); talents.append(e)
    talents = talents[:6]
    if len(talents) < 3:
        return None
    mois = MOIS[jour.month - 1]
    cle = f"{jour:%Y-%m}"
    if _deja("format-promo", cle, 5):
        return None
    pages = [({**_fiche(talents[0]["artist"], f"LA PROMO CAURI · {mois.upper()}", f"Les {len(talents)} talents à suivre ce mois-ci, déjà dans nos classements.", ["Cauri Charts"], cle), "photo_ok": True},
              f"Promo · {jour.year}", None)]
    for i, e in enumerate(talents):
        pages.append((_fiche(e["artist"], "", "", ["Cauri Charts"], cle), f"{i + 2} / {len(talents) + 2}",
                      _diapo("À SUIVRE", (VIOLET, BLEU, ROUGE)[i % 3], e["artist"], f"« {e['title']} » · {e['detail']}", f"t{i}")))
    pages.append(_fin("Qui sera la prochaine star ⁉️", cle))
    legende = (f"🌱 La promo Cauri de {mois} : les talents à suivre, déjà dans les classements.\n\n"
               + "\n".join(f"▪️ {e['artist']} — « {e['title']} » ({e['detail']})" for e in talents)
               + "\n\nQui sera la prochaine star ⁉️ ‼️")
    return _post("format-promo", jour, due, f"La promo Cauri · {mois}", pages, legende, "#CauriCharts #Révélations #AfriqueDeLOuest #NewGen", cle)


# ---------------------------------------------------------------- 5. le classement mensuel des artistes

def power(jour: date, due: datetime) -> dict | None:
    from core.services import live_chart
    rows = live_chart.build(None, mode="icon", limit=10)["rows"]
    if len(rows) < 5:
        return None
    mois = MOIS[(jour.month - 2) % 12]          # le 1er du mois : le classement arrêté à la fin du mois écoulé
    cle = f"{jour:%Y-%m}"
    if _deja("format-power", cle, 5):
        return None
    un = rows[0]
    lignes = [f"N°{r['rank']}  {r['artist_name']} ({country_name(r['artist_country']) if r.get('artist_country') else '—'})" for r in rows]
    pages = [(_fiche(un["artist_name"], f"{un['artist_name']} : N°1 DES ARTISTES", f"Le classement des artistes d’Afrique de l’Ouest, arrêté fin {mois}.", ["Cauri Charts"], cle),
              f"Classement · {mois}", None),
             (_fiche("", "", "", ["Cauri Charts"], cle), "2 / 4", _diapo("TOP ARTISTES", VIOLET, f"N°{len(rows)} À N°4", "\n".join(lignes[3:][::-1]), "b")),
             (_fiche(rows[1]["artist_name"], "", "", ["Cauri Charts"], cle), "3 / 4", _diapo("LE PODIUM", BLEU, "N°3 · N°2 · N°1", "\n".join(lignes[:3][::-1]), "p")),
             _fin("Qui méritait la 1re place ⁉️", cle)]
    legende = (f"🏆 Le classement des artistes d’Afrique de l’Ouest · {mois} :\n\n" + "\n".join(lignes)
               + "\n\nQui méritait la 1re place ⁉️ ‼️\n\nMéthode publique : cauricharts.com/methodologie")
    return _post("format-power", jour, due, f"Classement des artistes · {mois}", pages, legende, "#CauriCharts #TopArtistes #AfriqueDeLOuest", cle)


# ---------------------------------------------------------------- calendrier

def du_jour(jour: date) -> list:
    """Les formats prévus aujourd'hui (appelé par la chaîne de nuit) ; chacun part à son heure via la file d'attente."""
    a_heure = lambda h: datetime(jour.year, jour.month, jour.day, h, 0, tzinfo=timezone.utc)
    prevus = []
    if jour.day == 1:
        prevus.append((power, a_heure(12)))
    if jour.isoweekday() == 1 and jour.day <= 7:
        prevus.append((promo, a_heure(12) + timedelta(minutes=30 if jour.day == 1 else 0)))
    prevus.append({1: (top10, a_heure(21)), 3: (versus, a_heure(21)), 5: (qui_est, a_heure(21))}.get(jour.isoweekday()))
    lignes = []
    for p in filter(None, prevus):
        fn, due = p
        try:
            post = fn(jour, due)
            lignes.append(f"{fn.__name__} : " + (post["title"] if post else "pas assez de données"))
        except Exception as exc:  # noqa: BLE001 — un format raté ne bloque pas les autres
            log_write("social", "error", f"format {fn.__name__} : {exc}")
            lignes.append(f"{fn.__name__} : échec ({exc})")
    return lignes
