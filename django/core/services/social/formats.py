"""Formats récurrents inspirés des grands médias rap (RapTV…), sur NOS données réelles uniquement :

  - versus      : deux artistes face à face, leurs vrais chiffres (Spotify via Kworb, YouTube, Deezer, classements Cauri) ;
  - top10       : « Ses 10 titres les plus écoutés, classés » (compteurs publics de Spotify, via Kworb) ;
  - qui_est     : « Qui est X ? » — une révélation de nos classements (bio Wikipédia si elle existe, chiffres Cauri) ;
  - promo       : « La promo Cauri » — les talents émergents du mois (rubrique Révélations) ;
  - power       : le classement mensuel des artistes (Top artistes Cauri), le 1er du mois.

Chaque post finit par une question au public. Rendu : couverture choc sur vraies photos (monde.couverture_choc).
Les posts sont enregistrés avec leur heure (« due ») et partent un par un via la file d'attente (monde.publie_file).
Calendrier (heure de Lomé) : lundi 21 h top10, mardi et samedi 21 h citation, mercredi 21 h versus, jeudi et dimanche
21 h histoire, vendredi 21 h qui_est, 1er du mois 12 h power,
1er lundi du mois 12 h promo ; chaque jour 12 h anecdote (« Le saviez-vous ? », 13 h les jours de power ou promo) ; lundi et mercredi 18 h punchline (1 à 2 lignes de paroles, LRCLIB)."""
import json
import re
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from core import db, repos
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


def _post(theme: str, jour: date, due: datetime, titre: str, pages: list, legende: str, hashtags: str, cle: str,
          couverture=None, illustration_ia: bool = False) -> dict:
    """pages : [(fiche, kicker, diapo)] → images 4:5 et 9:16, post enregistré avec son heure de départ.
    couverture(fmt) : image de la 1re page dessinée à part (modèles « Pour toi »), fmt = « feed » ou « story »."""
    from core.services.social import editorial as E
    from core.services.social import image as PI
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{jour.isoformat()}-{theme}-{datetime.now(timezone.utc):%H%M%S}"
    M.STYLE_GRAINE = nom   # un même style (police, couleurs, mise en page) sur toutes les images du post
    fichiers = []
    for n, (f, kk, dp) in enumerate(pages):
        if n == 0 and couverture:
            a = PI.save_jpeg(couverture("feed"), PI.DIR / f"{nom}-{n}.jpg")
            b = PI.save_jpeg(couverture("story"), PI.DIR / f"{nom}-{n}-916.jpg")
            fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": titre})
            continue
        a = PI.save_jpeg(M.couverture_choc(f, kk, False, "feed", dp), PI.DIR / f"{nom}-{n}.jpg")
        b = PI.save_jpeg(M.couverture_choc(f, kk, False, "tiktok", dp), PI.DIR / f"{nom}-{n}-916.jpg")
        fichiers.append({"file": Path(a).name, "tiktok": Path(b).name, "label": (dp or {}).get("titre") or f.get("une") or titre})
    faits = {"cle": cle, "due": due.isoformat(), "kind": theme}
    if illustration_ia:
        from core.services.social.illustration import mention
        legende = mention(legende)
        faits["illustration_ia"] = True
    return E.save_post(theme, jour.isoformat(), titre, legende, hashtags, fichiers, faits)


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


# ---------------------------------------------------------------- 6. citation choc

_GUILLEMETS = re.compile(r"[«“\"]\s*([^»”\"]{25,170}?)\s*[»”\"]")


def citation(jour: date, due: datetime) -> dict | None:
    """La phrase choc d'une star, tirée MOT POUR MOT d'un article (jamais réécrite par l'IA) : l'auteur doit être nommé
    dans le titre de l'article ; propos insultants ou sensibles écartés ; une citation étrangère est traduite avec la
    mention « traduit de l'anglais » et l'original est donné dans la légende."""
    from core.services import ai
    from core.services.social import medias, pourtoi
    cands = []
    for it in M.collecte(48):
        texte = f"{it['title']} {it.get('summary') or ''}"
        for q in dict.fromkeys(_GUILLEMETS.findall(texte)):
            if len(q.split()) >= 5 and not _deja("format-citation", q[:60], 26):
                cands.append({"i": len(cands), "titre": it["title"][:200], "resume": (it.get("summary") or "")[:300],
                              "citation": q, "source": it.get("source"), "url": it.get("url")})
    if not cands:
        log_write("social", "info", "citation : aucune citation dans les articles des 48 dernières heures")
        return None
    consigne = ("Voici des citations relevées dans des articles musicaux. Pour chacune, rends un objet JSON :\n"
                '{"i": n, "auteur": "nom exact de la personne qui parle, tel qu\'écrit dans le titre", "musique": true si c\'est un '
                'artiste ou une figure de la musique, "force": 0-100 (phrase qui fait réagir : ambition, argent, clash, '
                'confidence, prise de position), "sensible": true si insulte, propos sexiste ou raciste, accusation, santé, '
                'décès, justice, "langue": "fr" ou "en" ou autre, "francais": "traduction française fidèle si la citation '
                'n\'est pas en français, sinon recopie-la", "contexte": "8 mots max, tirés du titre ou du résumé, qui situent la '
                'phrase"}\nRends une liste JSON, rien d\'autre.\n\n' + json.dumps(cands[:40], ensure_ascii=False))
    try:
        r = ai.make().ask(M.SYSTEME, consigne, max_tokens=5000)
        texte = r["text"]
        notes = json.loads(texte[texte.find("["): texte.rfind("]") + 1])
    except Exception as exc:  # noqa: BLE001
        log_write("social", "error", f"citation : {exc}")
        return None
    bonnes = []
    for n in notes:
        try:
            c = cands[int(n["i"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        auteur = (n.get("auteur") or "").strip()
        # garde-fous : l'auteur est nommé dans le titre, pas de propos sensible, figure de la musique
        if not auteur or M._sans_accents(auteur).lower() not in M._sans_accents(c["titre"]).lower():
            continue
        if n.get("sensible") or not n.get("musique"):
            continue
        bonnes.append({**c, **n, "note_finale": int(n.get("force") or 0) + min(30, M.fans(auteur) // 200000)})
    if not bonnes:
        log_write("social", "info", f"citation : {len(cands)} candidates, aucune retenue (auteur absent du titre, sensible ou hors musique)",
                  {"notes": [{k: n.get(k) for k in ("i", "auteur", "musique", "sensible")} for n in notes[:12]]})
        return None
    b = max(bonnes, key=lambda x: x["note_finale"])
    etrangere = (b.get("langue") or "fr") != "fr"
    phrase = (b.get("francais") or b["citation"]).strip() if etrangere else b["citation"]
    photo = medias.choisit(b["auteur"], M._photo_portrait(b["auteur"]))
    note = "Traduit de l'anglais" if b.get("langue") == "en" else ("Traduit" if etrangere else "")
    illustration = None
    if not photo:
        from core.services.social.illustration import genere
        illustration = genere(f"citation musique {b.get('contexte') or ''}", "citation")
        photo = illustration
    couverture = lambda fmt: pourtoi.citation(photo, phrase, b["auteur"], b.get("contexte") or "", fmt, note=note)  # noqa: E731
    legende = (f"🗣️ {b['auteur']} : « {phrase} »\n\n"
               + (f"Version originale : « {b['citation']} »\n\n" if etrangere else "")
               + f"{b.get('contexte') or ''}\n(Source : {b.get('source') or 'presse'})\n\n"
               + "Vous êtes d'accord ⁉️ Dites-le en commentaire ‼️"
               + (f"\n\n{medias.credits([photo])}" if medias.credits([photo]) else ""))
    tags = "#CauriCharts #Citation #" + "".join(ch for ch in b["auteur"] if ch.isalnum()) + " #Musique"
    return _post("format-citation", jour, due, f"{b['auteur']} : « {phrase[:80]} »", [(_fiche(b["auteur"], "", "", [], b["citation"][:60]), "", None)],
                 legende, tags, b["citation"][:60], couverture=couverture, illustration_ia=bool(illustration))


# ---------------------------------------------------------------- 7. les projets qui ont marqué l'histoire

# (artiste, projet, langue Wikipédia, page) : des projets ouest-africains dont l'histoire est documentée
HISTOIRE = [
    ("Wizkid", "Made in Lagos", "en", "Made_in_Lagos"), ("Burna Boy", "African Giant", "en", "African_Giant"),
    ("Burna Boy", "Twice as Tall", "en", "Twice_as_Tall"), ("Burna Boy", "Love, Damini", "en", "Love,_Damini"),
    ("Davido", "Timeless", "en", "Timeless_(Davido_album)"), ("Rema", "Rave & Roses", "en", "Rave_%26_Roses"),
    ("Ayra Starr", "19 & Dangerous", "en", "19_%26_Dangerous"), ("Asake", "Work of Art", "en", "Work_of_Art_(Asake_album)"),
    ("Rema", "Calm Down", "en", "Calm_Down_(Rema_song)"), ("CKay", "Love Nwantiti", "en", "Love_Nwantiti"),
    ("Wizkid", "Essence", "en", "Essence_(Wizkid_song)"), ("Burna Boy", "Last Last", "en", "Last_Last"),
    ("Davido", "Fall", "en", "Fall_(Davido_song)"), ("Wizkid", "Ojuelegba", "en", "Ojuelegba_(song)"),
    ("Magic System", "Premier Gaou", "fr", "Premier_Gaou"), ("Youssou N'Dour", "7 Seconds", "en", "7_Seconds_(song)"),
    ("Tems", "Free Mind", "en", "Free_Mind_(song)"), ("Kizz Daniel", "Buga", "en", "Buga_(song)"),
]


def histoire(jour: date, due: datetime) -> dict | None:
    """« Le projet qui a changé l'histoire » : 3 faits tirés de Wikipédia (chaque chiffre doit figurer dans le texte source)."""
    from core.services import ai
    from core.services.news import http_get
    from core.services.social import medias, pourtoi
    for artiste, projet, lang, page in HISTOIRE:
        cle = f"{artiste}|{projet}"
        if _deja("format-histoire", cle, 52):
            continue
        try:
            d = json.loads(http_get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{page}") or "{}")
        except Exception:  # noqa: BLE001
            continue
        texte = d.get("extract") or ""
        if len(texte) < 300:
            continue
        consigne = ("Voici le résumé Wikipédia d'un projet musical. Rends un objet JSON :\n"
                    '{"titre": "6 à 9 mots, en français, qui disent pourquoi ce projet a marqué l\'histoire", "accent": "le mot ou '
                    'chiffre à mettre en couleur, recopié du titre", "faits": ["3 faits marquants en français, un par phrase de '
                    '20 mots max, chacun présent dans le texte (chiffres recopiés exactement)"], "question": "une question au public '
                    'terminée par ⁉️"}\nN\'ajoute rien qui ne soit pas dans le texte.\n\n' + texte)
        try:
            r = ai.make().ask(M.SYSTEME, consigne, max_tokens=1500)
            o = json.loads(r["text"][r["text"].find("{"): r["text"].rfind("}") + 1])
        except Exception as exc:  # noqa: BLE001
            log_write("social", "error", f"histoire {projet} : {exc}")
            continue
        chiffres_source = set(re.findall(r"\d+", texte.replace(",", "").replace(" ", "")))
        faits = [f for f in o.get("faits") or [] if all(c in chiffres_source for c in re.findall(r"\d+", f.replace(" ", "").replace(",", "")))]
        if len(faits) < 2 or not o.get("titre"):
            continue
        # Photo de scène libre ou portrait de l'artiste — jamais le plan d'un autre clip que le projet raconté
        libres = medias.scenes_libres(artiste)
        libres = [x for x in libres if medias.lisible(x["url"])]
        photo = libres[0]["url"] if libres else M._photo_portrait(artiste)
        if libres:
            medias.CREDITS[photo] = libres[0]["credit"]
        illustration = None
        if not photo:
            from core.services.social.illustration import genere
            illustration = genere(f"histoire musicale {projet}", "histoire")
            photo = illustration
        couverture = lambda fmt, t=o["titre"], a=o.get("accent"): pourtoi.une(photo, t, a, fmt, surtitre="Ça a changé l'histoire")  # noqa: E731
        pages = [(_fiche(artiste, "", "", [], cle), "", None)]
        for k, f in enumerate(faits[:3]):
            pages.append((_fiche(artiste, "", "", ["Wikipédia"], cle), f"{k + 2} / {len(faits[:3]) + 2}",
                          _diapo(projet.upper(), (VIOLET, BLEU, ROUGE)[k % 3], f"FAIT N°{k + 1}", f, f"h{k}")))
        pages.append(_fin(o.get("question") or "Vous l'écoutez encore ⁉️", cle))
        legende = (f"📀 {o['titre']} — « {projet} » de {artiste}\n\n" + "\n".join(f"▪️ {f}" for f in faits[:3])
                   + f"\n\n{o.get('question') or ''} Dites-le en commentaire ‼️\n\nSource : Wikipédia ({lang}.wikipedia.org/wiki/{page})"
                   + (f"\n{medias.credits([photo])}" if medias.credits([photo]) else ""))
        tags = "#CauriCharts #Histoire #" + "".join(ch for ch in artiste if ch.isalnum()) + " #Afrobeats"
        return _post("format-histoire", jour, due, f"{projet} ({artiste}) : {o['titre']}", pages, legende, tags, cle, couverture=couverture, illustration_ia=bool(illustration))
    return None


# ---------------------------------------------------------------- 8. le saviez-vous ? (anecdotes et histoires)

# Angles d'anecdote que l'IA peut choisir — l'ANGLE est inventé, les FAITS viennent tous du texte Wikipédia
ANGLES = ["le premier artiste africain à…", "l'histoire derrière un de ses tubes", "pourquoi il ou elle porte ce nom",
          "la folle histoire de ses débuts", "le jour où tout a basculé", "le record que personne n'attendait",
          "ce que peu de gens savent sur son enfance", "la rencontre qui a changé sa carrière"]
MUSICIEN = re.compile(r"singer|rapper|musician|songwriter|record producer|disc jockey|chanteu|rappeu|musicien|auteur-compositeur|"
                      r"artiste|afrobeats|highlife|coupé-décalé|hip hop|hip-hop", re.I)


def chiffres(texte: str) -> set:
    """Tous les nombres d'un texte, séparateurs de milliers retirés (« 1 200 000 » et « 1,200,000 » → {"1200000"} ;
    « 1,2 » et « 1.2 » → {"1", "2"}). Dans le doute, le garde-fou rejette (jamais l'inverse)."""
    t = re.sub(r"(?<=\d)[   ,](?=\d{3}\b)", "", texte or "")
    return set(re.findall(r"\d+", t))


def chiffres_verifies(texte: str, source: str) -> bool:
    """Garde-fou des anecdotes (comme histoire()) : chaque chiffre ou date du texte final figure dans le texte source."""
    return chiffres(texte) <= chiffres(source)


def preuve_trouvee(preuve: str, source: str) -> bool:
    """La phrase citée en preuve est-elle dans le texte source ? (au moins 80 % de ses mots de 4 lettres et plus)."""
    mots = [m for m in re.findall(r"\w{4,}", M._sans_accents(preuve).lower())]
    if not mots:
        return False
    s = M._sans_accents(source).lower()
    return sum(m in s for m in mots) / len(mots) >= .8


def _wiki(nom: str, lang: str) -> dict | None:
    """Page Wikipédia d'un musicien : {titre, texte, url}. Le nom exact (avec redirections), sinon la recherche ;
    pages d'homonymie et pages qui ne parlent pas de musique écartées."""
    from urllib.parse import quote
    from core.services.news import http_get
    base = f"https://{lang}.wikipedia.org/w/api.php?format=json&formatversion=2&"

    def page(titre: str):
        d = json.loads(http_get(base + "action=query&prop=extracts|pageprops&explaintext=1&redirects=1&titles=" + quote(titre)) or "{}")
        p = ((d.get("query") or {}).get("pages") or [{}])[0]
        texte = p.get("extract") or ""
        if p.get("missing") or "disambiguation" in (p.get("pageprops") or {}) or not MUSICIEN.search(texte[:800]):
            return None
        if M._sans_accents(nom).lower() not in M._sans_accents(texte[:1500]).lower():
            return None
        return {"titre": p["title"], "texte": texte, "lang": lang,
                "url": f"https://{lang}.wikipedia.org/wiki/{quote(p['title'].replace(' ', '_'))}"}
    try:
        p = page(nom)
        if p:
            return p
        d = json.loads(http_get(base + "action=query&list=search&srlimit=3&srsearch=" + quote(f'"{nom}" ' + ("musician" if lang == "en" else "musique"))) or "{}")
        for r in (d.get("query") or {}).get("search") or []:
            if M._sans_accents(nom).lower() in M._sans_accents(r["title"]).lower():
                p = page(r["title"])
                if p:
                    return p
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"anecdote wikipédia {nom} ({lang}) : {exc}")
    return None


def _candidats_anecdote() -> list:
    """Artistes ouest-africains et africains d'abord : les plus suivis de nos classements, puis les stars africaines."""
    noms = []
    try:
        for r in db.all("""SELECT name FROM artists WHERE status = 'active'
                           ORDER BY COALESCE(youtube_subscribers, 0) + COALESCE(fans, 0) DESC LIMIT 40"""):
            noms.append(r["name"])
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"anecdote : artistes en base illisibles ({exc})")
    afr = [n for n in M.CHERCHES if M._sans_accents(n).lower() in M.AFRICAINS]
    vus, out = set(), []
    for n in noms + afr:
        k = M._sans_accents(n).lower()
        if k not in vus:
            vus.add(k); out.append(n)
    return out


def credit_photo(url: str) -> str:
    """Crédit de la photo : celui des médias libres ou des clips, sinon la provenance du portrait."""
    from core.services.social import medias
    c = medias.credits([url])
    if c or not url:
        return c
    return "Photo : Deezer (photo d'artiste)" if "dzcdn" in str(url) else "Photo : portrait officiel de l'artiste"


def _sans_emoji(s: str) -> str:
    """Le texte posé sur une image : jamais d'émoji (⁉️ ‼️ → ? !)."""
    s = (s or "").replace("⁉️", " ?").replace("⁉", " ?").replace("‼️", " !").replace("‼", " !")
    return re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", s).replace("  ", " ").strip()


def anecdote(jour: date, due: datetime, essais: int = 6) -> dict | None:
    """« Le saviez-vous ? » : l'IA choisit l'ANGLE (le premier à…, l'histoire derrière un tube, l'origine d'un nom…) à
    partir de la page Wikipédia de l'artiste ; chaque fait doit venir de ce texte, et chaque chiffre ou date du post
    (titre compris) doit y figurer mot pour mot (garde-fou chiffres_verifies). Couverture « Pour toi », 2 ou 3
    diapositives de faits, une question finale ; source Wikipédia et crédit photo en légende."""
    from core.services import ai
    from core.services.social import medias, pourtoi
    cands = [n for n in _candidats_anecdote() if not _deja("format-anecdote", n, 8)]
    if not cands:
        return None
    depart = jour.toordinal() % len(cands)   # un artiste différent chaque jour, dans l'ordre de notoriété
    for nom in (cands[depart:] + cands[:depart])[:essais]:
        pages_wiki = [p for p in (_wiki(nom, "fr"), _wiki(nom, "en")) if p and len(p["texte"]) >= 1200]
        if not pages_wiki:
            continue
        w = max(pages_wiki, key=lambda p: len(p["texte"]))   # la page la plus fournie (souvent l'anglaise pour le Nigeria)
        texte = w["texte"][:9000]
        consigne = (
            f"Voici la page Wikipédia de l'artiste {nom}. Trouve l'ANECDOTE la plus étonnante qu'elle raconte, sous un de "
            f"ces angles (ou un angle du même genre) : {', '.join(ANGLES)}.\nRends un objet JSON :\n"
            '{"angle": "l\'angle choisi", "titre": "6 à 9 mots en français, qui donnent envie de lire (ex. « Le vrai nom '
            'derrière WIZKID va vous surprendre »), sans chiffre absent du texte", "accent": "LE mot ou chiffre du titre à mettre '
            'en couleur, recopié tel quel", "faits": ["2 ou 3 faits en français, 25 mots max chacun, qui racontent '
            'l\'anecdote dans l\'ordre ; chaque fait est présent dans le texte, chiffres et dates recopiés EXACTEMENT, en chiffres"], '
            '"preuves": ["pour chaque fait, la phrase du texte qui le prouve, recopiée mot pour mot"], "question": "une question '
            'au public, courte, qui pousse à commenter, terminée par ⁉️"}\n'
            "N'ajoute RIEN qui ne soit pas dans le texte : pas de superlatif inventé, pas de « premier » si le texte ne le dit pas. "
            "Si le texte ne contient aucune anecdote solide, rends {\"faits\": []}.\n\n" + texte)
        try:
            r = ai.make().ask(M.SYSTEME, consigne, max_tokens=1800)
            o = json.loads(r["text"][r["text"].find("{"): r["text"].rfind("}") + 1])
        except Exception as exc:  # noqa: BLE001
            log_write("social", "error", f"anecdote {nom} : {exc}")
            continue
        titre = M.coupe(o.get("titre") or "", 70).rstrip("…")
        bruts, preuves = o.get("faits") or [], o.get("preuves") or []
        faits = []
        for i, f in enumerate(bruts):
            if not isinstance(f, str) or not f.strip() or not chiffres_verifies(f, texte):
                continue
            # la phrase-preuve doit vraiment venir du texte (sinon le fait est sans doute inventé)
            if len(preuves) == len(bruts) and not preuve_trouvee(str(preuves[i]), texte):
                continue
            faits.append(M.coupe(f, 220))
        faits = faits[:3]
        if len(faits) < 2 or not (6 <= len(titre.split()) <= 9) or not chiffres_verifies(titre, texte):
            log_write("social", "info", f"anecdote {nom} : écartée (faits vérifiés : {len(faits)}, titre « {titre} »)")
            continue
        # Photo : scène sous licence libre, sinon portrait de notre base ou de Deezer (comme histoire())
        libres = [x for x in medias.scenes_libres(nom) if medias.lisible(x["url"])]
        photo = libres[0]["url"] if libres else M._photo_portrait(nom)
        if not photo:
            continue
        if libres:
            medias.CREDITS[photo] = libres[0]["credit"]
        question = M.coupe(o.get("question") or f"Vous le saviez sur {nom} ⁉️", 110)
        illustration = None
        if not photo:
            from core.services.social.illustration import genere
            illustration = genere(f"anecdote musicale {titre}", "anecdote")
            photo = illustration
        couverture = lambda fmt, t=titre, a=o.get("accent"): pourtoi.une(photo, t, a, fmt, surtitre="Le saviez-vous ?")  # noqa: E731
        n = len(faits) + 2
        pages = [(_fiche(nom, "", "", [], nom), "", None)]
        for k, f in enumerate(faits):
            pages.append((_fiche(nom, "", "", ["Wikipédia"], nom), f"{k + 2} / {n}",
                          _diapo("LE SAVIEZ-VOUS ?", (VIOLET, BLEU, ROUGE)[k % 3], nom.upper() if k == 0 else f"ANECDOTE · {k + 1}", f, f"a{k}")))
        pages.append((_fiche("", "", "", [], nom), "À vous",
                       _diapo("CAURI CHARTS", NUIT, _sans_emoji(question), "Répondez en commentaire. Cauri Charts, la référence de la musique ouest-africaine.", "fin")))
        credit = credit_photo(photo)
        legende = (f"💡 Le saviez-vous ? {titre}\n\n" + "\n".join(f"▪️ {f}" for f in faits)
                   + f"\n\n{question} Dites-le en commentaire ‼️\n\nSource : Wikipédia ({w['url']}), texte sous licence CC BY-SA"
                   + (f"\n{credit}" if credit else ""))
        tags = "#CauriCharts #LeSaviezVous #" + "".join(ch for ch in nom if ch.isalnum()) + " #MusiqueAfricaine"
        return _post("format-anecdote", jour, due, f"Le saviez-vous ? {titre}", pages, legende, tags, nom, couverture=couverture, illustration_ia=bool(illustration))
    return None


# ---------------------------------------------------------------- 9. punchline (1 à 2 lignes de paroles)

LANGUES = {"en": "de l'anglais", "pcm": "du pidgin", "yo": "du yoruba", "ig": "de l'igbo", "ha": "du haoussa", "tw": "du twi",
           "ln": "du lingala", "wo": "du wolof", "sw": "du swahili", "zu": "du zoulou", "es": "de l'espagnol", "pt": "du portugais",
           "ee": "de l'éwé", "fon": "du fon", "nouchi": "du nouchi", "dyu": "du dioula"}


def _norme(s: str) -> str:
    """Pour comparer des paroles : apostrophes et guillemets unifiés, espaces réduits, minuscules."""
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def ligne_dans_paroles(ligne: str, paroles: str) -> str | None:
    """La ligne choisie (1 ou 2 vers, séparés par « / » ou un retour à la ligne) figure-t-elle MOT POUR MOT dans les
    paroles, en vers consécutifs ? Rend la ligne telle qu'écrite dans les paroles (vers joints par « / »), sinon None."""
    morceaux = [m for m in re.split(r"\s*/\s*|\n", ligne or "") if m.strip()]
    vers = [v for v in (paroles or "").split("\n") if v.strip()]
    if not 1 <= len(morceaux) <= 2 or len(" ".join(morceaux)) > 170:
        return None
    for i in range(len(vers) - len(morceaux) + 1):
        if all(_norme(m) in _norme(vers[i + k]) for k, m in enumerate(morceaux)):
            if any(len(_norme(m)) < 8 for m in morceaux):
                return None   # bout de vers trop court : ce n'est pas une punchline
            return " / ".join(m.strip() for m in morceaux)
    return None


def _paroles(artiste: str, titre: str) -> str | None:
    """Paroles LRCLIB (API libre, sans clé) : le titre exact d'abord, sinon la recherche (même artiste)."""
    from urllib.parse import urlencode
    from core.services.news import http_get
    try:
        d = json.loads(http_get("https://lrclib.net/api/get?" + urlencode({"artist_name": artiste, "track_name": titre})) or "{}")
        if d.get("plainLyrics") and not d.get("instrumental"):
            return d["plainLyrics"]
        for r in json.loads(http_get("https://lrclib.net/api/search?" + urlencode({"artist_name": artiste, "track_name": titre})) or "[]")[:10]:
            if r.get("plainLyrics") and M._sans_accents(artiste).lower() in M._sans_accents(r.get("artistName") or "").lower():
                return r["plainLyrics"]
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"punchline paroles {artiste} – {titre} : {exc}")
    return None


def _titres_punchline() -> list:
    """(artiste, titre) : les titres de nos classements d'abord, puis le titre le plus écouté (Deezer) des stars africaines."""
    out = []
    try:
        from core.services import live_chart
        out += [(r["artist_name"], r["title"]) for r in live_chart.build(None, limit=30)["rows"] if r.get("title")]
    except Exception as exc:  # noqa: BLE001
        log_write("social", "warning", f"punchline : classement illisible ({exc})")
    from core.services.news import http_get
    for nom in [n for n in M.STARS if M._sans_accents(n).lower() in M.AFRICAINS][:20]:
        try:
            a = M._deezer_artiste(nom)
            if not a:
                continue
            top = json.loads(http_get(f"https://api.deezer.com/artist/{a['id']}/top?limit=3") or "{}").get("data") or []
            # titres en solo seulement : dans un duo, la ligne choisie pourrait être celle de l'invité (Tems sur « Raindance »
            # de Dave, essai du 18/10/2026)
            out += [(nom, t["title"]) for t in top if len(t.get("contributors") or [1]) == 1 and not re.search(r"feat|ft\.|with", t["title"], re.I)][:2]
        except Exception:  # noqa: BLE001
            continue
    return list(dict.fromkeys(out))


def punchline(jour: date, due: datetime, essais: int = 8) -> dict | None:
    """« Punchline » : 1 à 2 lignes des paroles d'un titre (LRCLIB), jamais un couplet. L'IA choisit la ligne la plus
    forte, mais elle n'est publiée que si elle figure MOT POUR MOT dans les paroles (ligne_dans_paroles) ; une ligne
    étrangère est traduite, avec la mention « Traduit de… » et l'original en légende."""
    from core.services import ai
    from core.services.social import medias, pourtoi
    cands = [c for c in _titres_punchline() if not _deja("format-punchline", f"{c[0]}|{c[1]}", 26)]
    if not cands:
        return None
    depart = jour.toordinal() % len(cands)
    for artiste, titre in (cands[depart:] + cands[:depart])[:essais]:
        paroles = _paroles(artiste, titre)
        if not paroles or len(paroles) < 200:
            continue
        consigne = (f"Voici les paroles de « {titre} » de {artiste}. Choisis LA punchline : la ligne la plus forte et la plus "
                    "partageable (phrase culte, ambition, fierté, sagesse, image forte, amour sans sous-entendu), 1 ou 2 vers "
                    f"consécutifs MAXIMUM, jamais un couplet, chantés par {artiste} (pas par un invité). Rends un objet JSON :\n"
                    '{"ligne": "le ou les 2 vers recopiés EXACTEMENT, caractère pour caractère, séparés par « / »", '
                    '"langue": "code de la langue de la ligne : fr, en, pcm (pidgin), yo, ig, tw, ln, wo, sw…", '
                    '"francais": "traduction française fidèle si la ligne n\'est pas en français, sinon recopie-la", '
                    '"sensible": true si insulte, allusion sexuelle (même légère), violence, arme, drogue, alcool, "question": "question courte au public, '
                    'terminée par ⁉️"}\n\n' + paroles[:3500])
        try:
            r = ai.make().ask(M.SYSTEME, consigne, max_tokens=800)
            o = json.loads(r["text"][r["text"].find("{"): r["text"].rfind("}") + 1])
        except Exception as exc:  # noqa: BLE001
            log_write("social", "error", f"punchline {artiste} – {titre} : {exc}")
            continue
        ligne = ligne_dans_paroles(o.get("ligne") or "", paroles)
        if not ligne or o.get("sensible"):
            log_write("social", "info", f"punchline {artiste} – {titre} : écartée (ligne absente des paroles ou sensible)")
            continue
        langue = (o.get("langue") or "fr").lower()
        etrangere = langue != "fr"
        phrase = M.coupe((o.get("francais") or "").strip() or ligne, 170) if etrangere else ligne
        note = ("Traduit " + LANGUES[langue]) if etrangere and langue in LANGUES else ("Traduit" if etrangere else "")
        photo = medias.choisit(artiste, M._photo_portrait(artiste))
        if not photo:
            continue
        auteur = f"{artiste} — {titre}"
        couverture = lambda fmt, p=phrase, a=auteur, n=note: pourtoi.citation(photo, p, a, "", fmt, note=n)  # noqa: E731
        question = M.coupe(o.get("question") or "Elle vous parle, cette phrase ⁉️", 110)
        credit = credit_photo(photo)
        legende = (f"🎤 « {phrase} »\n\n" + (f"Version originale : « {ligne} » ({note.lower()})\n\n" if etrangere else "")
                   + f"Paroles : {artiste} – {titre}\n\n{question} Dites-le en commentaire ‼️"
                   + (f"\n\n{credit}" if credit else ""))
        tags = "#CauriCharts #Punchline #" + "".join(ch for ch in artiste if ch.isalnum()) + " #Paroles"
        cle = f"{artiste}|{titre}"
        return _post("format-punchline", jour, due, f"Punchline : {artiste} – {titre}", [(_fiche(artiste, "", "", [], cle), "", None)],
                     legende, tags, cle, couverture=couverture)
    return None


# ---------------------------------------------------------------- événements (galas, festivals, remises de prix)

_EVENEMENTS: dict = {}


def _evenement(jour: date):
    """L'événement ouest-africain de la semaine le plus couvert (≥ 2 médias), cherché une fois par jour et par exécution."""
    if jour not in _EVENEMENTS:
        from core.services.social import evenements as EV
        try:
            _EVENEMENTS[jour] = EV.du_jour(jour)
        except Exception as exc:  # noqa: BLE001
            log_write("social", "error", f"événements : {exc}")
            _EVENEMENTS[jour] = None
    return _EVENEMENTS[jour]


def evenement_photos(jour: date, due: datetime) -> dict | None:
    """« Retour en images » : couverture + 3 à 6 photos des articles, chacune créditée à son média."""
    from core.services.social import editorial as E
    from core.services.social import evenements as EV
    from core.services.social import image as PI
    e = _evenement(jour)
    if not e or _deja("format-evenement", e["nom"][:60], 2):
        return None
    nom = f"{jour.isoformat()}-evenement-{datetime.now(timezone.utc):%H%M%S}"
    r = EV.fabrique_photos(e, PI.DIR, nom)
    if not r:
        return None
    fichiers = [{"file": Path(f).name, "tiktok": Path(f).name, "label": r["titre"]} for f in [r["couverture"], *r["photos"]]]
    return E.save_post("format-evenement", jour.isoformat(), r["titre"], EV.legende(e),
                       "#CauriCharts #Evenement #AfriqueDeLOuest #Culture", fichiers,
                       {"cle": e["nom"][:60], "due": due.isoformat(), "kind": "format-evenement"})


def evenement_video(jour: date, due: datetime) -> dict | None:
    """« Les moments forts » : le passage le plus fort d'une vidéo de l'événement, sous-titré, avec son (publié tel quel)."""
    from core import storage
    from core.services.social import evenements as EV
    from core.services.social import image as PI
    from core.services.social import refrain as R
    e = _evenement(jour)
    if not e or _deja("format-evenement-video", e["nom"][:60], 2):
        return None
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{jour.isoformat()}-evenement-video-{datetime.now(timezone.utc):%H%M%S}"
    video = PI.DIR / f"{nom}.mp4"
    res = EV.moment_video(e, str(video))
    if not res:
        return None
    vignette = PI.DIR / f"{nom}.jpg"
    R.vignette(str(video), str(vignette))
    storage.publish_media_files("social", [video.name, vignette.name])
    titre = f"Les moments forts : {e['nom']}"[:160]
    legende = EV.legende(e) + f"\n\n{res['credit']} · {res['source']}"
    pid = db.insert("social_posts", {"slot_date": jour.isoformat(), "theme": "format-evenement-video", "title": titre,
                                     "caption": legende, "hashtags": "#CauriCharts #Evenement #MomentsForts",
                                     "image_square": vignette.name, "image_story": vignette.name, "carousel": "[]",
                                     "video": video.name, "status": "approved",
                                     "facts": json.dumps({"kind": "format-clip", "cle": e["nom"][:60], "due": due.isoformat(),
                                                          "source": res["source"]}, ensure_ascii=False)})
    return db.one("SELECT * FROM social_posts WHERE id = ?", [pid])


# ---------------------------------------------------------------- calendrier

def bandeaux(jour: date, due: datetime) -> dict | None:
    """Quatre artistes ouest-africains, classés par abonnés YouTube ou auditeurs Spotify vérifiés."""
    from core.services import kworb
    from core.services.social import pourtoi
    spotify = jour.isocalendar().week % 2 == 0
    if spotify:
        chiffres = kworb.auditeurs()
        rows = db.all("""SELECT a.*, COALESCE(a.base_country, gc.code) AS country FROM artists a
                         LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                         WHERE a.status = 'active' AND a.spotify_id IS NOT NULL AND a.spotify_id <> ''
                         AND COALESCE(a.base_country, gc.code) IN ('BJ','BF','CV','CI','GM','GH','GN','GW','LR','ML','MR','NE','NG','SN','SL','TG')""")
        mesures = [(r, chiffres[r['spotify_id']][0]) for r in rows if r['spotify_id'] in chiffres]
        label, source = "auditeurs mensuels Spotify", "Spotify (compteurs publics relevés par Kworb)"
    else:
        rows = db.all("""SELECT a.*, COALESCE(a.base_country, gc.code) AS country FROM artists a
                         LEFT JOIN countries gc ON gc.id = a.guessed_country_id
                         WHERE a.status = 'active' AND a.youtube_subscribers IS NOT NULL AND a.youtube_subscribers > 0
                         AND COALESCE(a.base_country, gc.code) IN ('BJ','BF','CV','CI','GM','GH','GN','GW','LR','ML','MR','NE','NG','SN','SL','TG')""")
        mesures = [(r, int(r['youtube_subscribers'])) for r in rows]
        label, source = "abonnés YouTube", "YouTube (compteurs publics enregistrés dans Cauri Charts)"
    candidats = []
    for artiste, nombre in sorted(mesures, key=lambda x: -x[1]):
        photo = M.photo(artiste['name'])
        if photo:
            candidats.append((artiste, nombre, photo))
        if len(candidats) == 4:
            break
    if len(candidats) < 4:
        return None
    personnes = [{"photo": p, "nom": a['name'], "chiffre": f"{n:,}".replace(',', ' ')} for a, n, p in candidats]
    cle = f"{'spotify' if spotify else 'youtube'}-{jour:%G-%V}"
    titre = f"LES PLUS SUIVIS SUR {'SPOTIFY' if spotify else 'YOUTUBE'}"
    couverture = lambda fmt: pourtoi.bandeaux(personnes, titre, fmt=fmt, couleur=BLEU if spotify else ROUGE)
    pages = [(_fiche(candidats[0][0]['name'], titre, f"Les artistes ouest-africains les plus suivis · {label}.", [source], cle), "Top 4", None)]
    legende = (f"📊 Les artistes ouest-africains les plus suivis sur {'Spotify' if spotify else 'YouTube'} ({label}) :\n\n"
               + "\n".join(f"▪️ {a['name']} — {n:,}".replace(',', ' ') for a, n, _ in candidats)
               + f"\n\nSource : {source}.\n\nQui manque à ce classement ?")
    return _post("format-bandeaux", jour, due, titre, pages, legende, "#CauriCharts #AfriqueDeLOuest #YouTube #Spotify", cle, couverture=couverture)


def _record_clip_semaine():
    """Le clip officiel qui a pris le plus de vues en 7 jours (relevés YouTube de Cauri Charts), hors n°1 des classements
    officiels de la semaine (déjà en couverture du mardi)."""
    pris = {t["rows"][0]["artist_name"].lower() for t in repos.official_tops(16) if t.get("rows")}
    for r in db.all("""WITH der AS (SELECT track_platform_id, MAX(captured_on) AS d FROM snapshots
                                    WHERE captured_on >= CURRENT_DATE - 3 GROUP BY 1)
                       SELECT t.title, a.name, a.id AS aid, s1.plays - s0.plays AS gain FROM der
                       JOIN snapshots s1 ON s1.track_platform_id = der.track_platform_id AND s1.captured_on = der.d
                       JOIN snapshots s0 ON s0.track_platform_id = der.track_platform_id AND s0.captured_on = der.d - 7
                       JOIN track_platform_ids p ON p.id = der.track_platform_id JOIN tracks t ON t.id = p.track_id
                       JOIN artists a ON a.id = t.artist_id
                       WHERE p.platform = 'youtube' AND p.kind = 'clip' AND p.is_official = 1 AND a.status = 'active'
                       ORDER BY gain DESC LIMIT 5"""):
        if r["name"].lower() not in pris and int(r["gain"] or 0) > 0:
            return r
    return None


def _record_clips_10m():
    """L'artiste suivi qui a le plus de clips officiels au-delà de 10 millions de vues, jamais le même avant 12 semaines."""
    for r in db.all("""SELECT a.id, a.name, COUNT(DISTINCT p.id) AS clips FROM artists a
                       JOIN tracks t ON t.artist_id = a.id
                       JOIN track_platform_ids p ON p.track_id = t.id
                       JOIN snapshots s ON s.track_platform_id = p.id
                       WHERE a.status = 'active' AND p.platform = 'youtube' AND p.kind = 'clip' AND p.is_official = 1
                       AND s.captured_on = (SELECT MAX(s2.captured_on) FROM snapshots s2 WHERE s2.track_platform_id = p.id)
                       AND s.plays > 10000000
                       GROUP BY a.id, a.name ORDER BY clips DESC, a.name LIMIT 10"""):
        if not _deja("format-record", f"10m-{r['id']}"):
            return r
    return None


def _millions(n: int) -> str:
    return (f"{n / 1e6:.1f}".replace(".", ",").replace(",0", "") + " M") if n >= 1_000_000 else f"{n:,}".replace(",", " ")


def record(jour: date, due: datetime) -> dict | None:
    """Record du jeudi au style 2026 (lockup façon ChartFR), une semaine sur deux : le clip le plus vu des 7 derniers
    jours, ou l'artiste aux plus de clips au-delà de 10 millions. Toujours nos propres relevés, jamais inventé."""
    from core.services.social import couverture2026 as C
    from core.services.social import editorial as E
    from core.services.social import image as PI
    from core.services.social import plans as PL
    semaine = jour.isocalendar()[1]
    r, genre = (_record_clip_semaine(), "semaine") if semaine % 2 == 0 else (_record_clips_10m(), "10m")
    if not r:
        r, genre = (_record_clips_10m(), "10m") if genre == "semaine" else (_record_clip_semaine(), "semaine")
    if not r:
        return None
    nom_artiste = r["name"]
    a_id = r.get("aid") or r.get("id")
    if genre == "semaine":
        cle = f"semaine-{jour.isocalendar()[0]}-{semaine}"
        vues = _millions(int(r["gain"]))
        lignes = [("RECORD DE LA SEMAINE :", "petit"), (r["title"].split(" (")[0].upper(), "or"), (f"de {nom_artiste} est", "petit"),
                  ("LE CLIP LE PLUS VU", "moyen"), (f"+{vues} VUES", "grand"), ("en 7 jours parmi les artistes suivis", "petit")]
        phrase = f"« {r['title']} » de {nom_artiste} : +{vues} vues en 7 jours, le clip le plus vu de la semaine"
        corps = (f"Sur les 7 derniers jours, « {r['title']} » a gagné {int(r['gain']):,} vues sur YouTube".replace(",", " ")
                 + ". C'est le plus gros gain parmi tous les clips officiels des artistes suivis par Cauri Charts.")
    else:
        cle = f"10m-{a_id}"
        n = int(r["clips"])
        lignes = [("RECORD CAURI CHARTS :", "petit"), (nom_artiste.upper(), "or"), ("est l'artiste suivi qui a", "petit"),
                  ("LE PLUS DE CLIPS", "moyen"), (f"{n} CLIPS", "grand"), ("au-delà de 10 millions de vues", "petit")]
        phrase = f"{nom_artiste} : {n} clips officiels au-delà de 10 millions de vues"
        corps = (f"{nom_artiste} compte {n} clips officiels au-delà de 10 millions de vues sur YouTube : le record parmi "
                 "les artistes suivis par Cauri Charts, recalculé depuis le dernier relevé de chaque clip.")
    if _deja("format-record", cle):
        return None
    photo = (PL.photo_large(a_id, detourable=True) if a_id else None) or M._photo_portrait(nom_artiste)
    fond_ia = None
    if not photo:
        from core.services.social.illustration import genere
        fond_ia = genere("record musical trophée", "record")
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"{jour.isoformat()}-record-{datetime.now(timezone.utc):%H%M%S}"
    source = "Source : YouTube, relevés quotidiens Cauri Charts"
    for fmt, suf in (("feed", ""), ("story", "-916")):
        PI.save_jpeg(C.lockup(photo, lignes, fmt, fond_ia=fond_ia), PI.DIR / f"{nom}-0{suf}.jpg")
        PI.save_jpeg(C.texte("RECORD", phrase, corps, source, photo or fond_ia, fmt), PI.DIR / f"{nom}-1{suf}.jpg")
    fichiers = [{"file": f"{nom}-0.jpg", "tiktok": f"{nom}-0-916.jpg", "label": "Record"},
                {"file": f"{nom}-1.jpg", "tiktok": f"{nom}-1-916.jpg", "label": phrase}]
    legende = f"🏆 {phrase}.\n\n{corps}\n\n{source}."
    if fond_ia:
        from core.services.social.illustration import mention
        legende = mention(legende)
    return E.save_post("format-record", jour.isoformat(), f"Record : {nom_artiste}", legende,
                       "#CauriCharts #Record #YouTube #Afrobeats", fichiers,
                       {"cle": cle, "due": due.isoformat(), "kind": "format-record", "illustration_ia": bool(fond_ia)})


def du_jour(jour: date) -> list:
    """Les formats prévus aujourd'hui (appelé par la chaîne de nuit) ; chacun part à son heure via la file d'attente."""
    a_heure = lambda h: datetime(jour.year, jour.month, jour.day, h, 0, tzinfo=timezone.utc)
    prevus = []
    if jour.day == 1:
        prevus.append((power, a_heure(12)))
    if jour.isoweekday() == 1 and jour.day <= 7:
        prevus.append((promo, a_heure(12) + timedelta(minutes=30 if jour.day == 1 else 0)))
    if jour.isoweekday() == 6:
        prevus.append((bandeaux, a_heure(12)))
    prevus.append({1: (top10, a_heure(21)), 2: (citation, a_heure(21)), 3: (versus, a_heure(21)), 4: (histoire, a_heure(21)),
                   5: (qui_est, a_heure(21)), 6: (citation, a_heure(21)), 7: (histoire, a_heure(21))}.get(jour.isoweekday()))
    # « Le saviez-vous ? » chaque jour à 12 h ; les jours où power ou promo occupent déjà midi, il passe à 13 h
    midi_pris = any(p and p[1].hour == 12 for p in prevus)
    if jour.isoweekday() != 6:
        prevus.append((anecdote, a_heure(13 if midi_pris else 12)))
    if jour.isoweekday() in (1, 3):   # lundi et mercredi 18 h : la punchline
        prevus.append((punchline, a_heure(18)))
    if jour.isoweekday() == 4:
        prevus.append((record, a_heure(18)))
    if jour.isoweekday() == 2:   # mardi 17 h : le classement officiel, s'il est déjà publié (sinon le guetteur des flashs le fera)
        from core.services.social import officiel
        prevus.append((officiel.post, a_heure(17)))
    # Événements de la semaine (galas, festivals, remises de prix) : photos à 15 h, moments forts en vidéo à 19 h
    prevus.append((evenement_photos, a_heure(15)))
    prevus.append((evenement_video, a_heure(19)))
    lignes = []
    for p in filter(None, prevus):
        fn, due = p
        try:
            post = fn(jour, due)
            if isinstance(post, dict):
                lignes.append(f"{post['theme']} : {post['title']} → {due:%H:%M} UTC (à blanc, non enregistré)")
            else:
                lignes.append(f"{fn.__name__} : " + (post["title"] if post else "pas assez de données"))
        except Exception as exc:  # noqa: BLE001 — un format raté ne bloque pas les autres
            log_write("social", "error", f"format {fn.__name__} : {exc}")
            lignes.append(f"{fn.__name__} : échec ({exc})")
    return lignes
