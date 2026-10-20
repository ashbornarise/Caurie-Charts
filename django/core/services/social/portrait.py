"""Portrait d'artiste : un carrousel par grand artiste, uniquement avec des faits sourcés.

  bio       : résumé de l'article Wikipédia (français, sinon anglais), licence CC BY-SA, source citée ;
  palmarès  : récompenses de Wikidata (propriété P166) avec leur année, sinon ses meilleures places chez Cauri Charts ;
  chiffres  : chaîne YouTube officielle (abonnés, vues totales), fans Deezer, meilleure place, classements de la semaine ;
  titres    : ses titres présents dans les classements des 7 derniers jours.
L'artiste est choisi parmi les confirmés les plus présents dans les classements, jamais deux fois en 8 semaines.
"""
import json
import re
from datetime import date
from urllib.parse import quote

from core import conf, db
from core.helpers import country_name
from core.services.imports import normalizer as N
from core.services.platforms import HttpClient

UA = {"User-Agent": "CauriCharts/1.0 (https://cauricharts.com ; contact@cauricharts.com)"}


def _json(url: str):
    r = HttpClient(20).request("GET", url, UA)
    try:
        return json.loads(r["body"]) if r["status"] == 200 else None
    except ValueError:
        return None


def artiste(artist_id: int) -> dict | None:
    return db.one("""SELECT a.*, c.code AS country FROM artists a JOIN countries c ON c.id = a.submission_country_id
                     WHERE a.id = ?""", [artist_id])


def pick(day: date) -> dict | None:
    """L'artiste confirmé le plus présent dans les classements de la semaine, pas encore portraituré depuis 8 semaines."""
    done = []
    for r in db.all("SELECT facts FROM social_posts WHERE theme = 'portrait' AND slot_date >= CURRENT_DATE - 56"):
        try:
            done.append(int(json.loads(r["facts"]).get("artist_id")))
        except (ValueError, TypeError):
            pass
    return db.one(f"""SELECT a.*, c.code AS country FROM artists a JOIN countries c ON c.id = a.submission_country_id
                      WHERE a.status = 'active' AND a.image_url IS NOT NULL {"AND a.id NOT IN (" + ",".join(map(str, done)) + ")" if done else ""}
                      ORDER BY (SELECT COUNT(DISTINCT o.source || o.country_id) FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                                WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 7) DESC,
                               COALESCE(a.youtube_subscribers, 0) + COALESCE(a.fans, 0) DESC LIMIT 1""")


def wikidata_id(name: str, country: str) -> str | None:
    """Identifiant Wikidata de l'artiste : même nom ET nationalité du pays attendu (pas d'homonyme)."""
    qid = (conf.get("discovery") or {}).get("wikidata_countries", {}).get(country)
    for lang in ("fr", "en"):
        found = _json(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&language={lang}&type=item&limit=5&format=json&search={quote(name)}") or {}
        for item in found.get("search") or []:
            if N.artist_key(item.get("label", "")) != N.artist_key(name):
                continue
            claims = ((_json(f"https://www.wikidata.org/wiki/Special:EntityData/{item['id']}.json") or {}).get("entities", {})
                      .get(item["id"], {}).get("claims", {}))
            nat = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P27", [])}
            if qid in nat:
                return item["id"]
    return None


def awards(qid: str) -> list:
    """Récompenses (P166) avec l'année quand elle est connue, les plus récentes d'abord."""
    q = ("SELECT ?awardLabel ?year WHERE { wd:" + qid + " p:P166 ?st . ?st ps:P166 ?award . "
         "OPTIONAL { ?st pq:P585 ?d . BIND(YEAR(?d) AS ?year) } "
         'SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". } }')
    data = _json("https://query.wikidata.org/sparql?format=json&query=" + quote(q)) or {}
    out = []
    for b in (data.get("results") or {}).get("bindings") or []:
        label = (b.get("awardLabel") or {}).get("value", "")
        if label and not re.fullmatch(r"Q\d+", label):
            out.append({"award": label, "year": int(b["year"]["value"]) if b.get("year") else None})
    out = list({(a["award"], a["year"]): a for a in out}.values())
    return sorted(out, key=lambda a: -(a["year"] or 0))


def bio(name: str, qid: str | None) -> dict | None:
    """Résumé Wikipédia (titre exact donné par Wikidata), coupé à la fin d'une phrase."""
    titles = {}
    if qid:
        ent = (_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json") or {}).get("entities", {}).get(qid, {})
        titles = {k[:2]: v["title"] for k, v in (ent.get("sitelinks") or {}).items() if k in ("frwiki", "enwiki")}
    for lang in ("fr", "en"):
        title = titles.get(lang)
        if not title:
            continue
        s = _json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}") or {}
        text = str(s.get("extract") or "").strip()
        # Graphies spéciales (« stylisé REMΛ ») : absentes des polices des visuels, et sans intérêt pour le lecteur
        text = re.sub(r",?\s*(stylisé|stylised|stylized)[^,.;]*", "", text)
        text = re.sub("[^\u0000-\u024F\u2018-\u201F\u2026\u00ab\u00bb\u2013\u2014]", "", text).strip()
        if len(text) < 60:
            continue
        cut, out = 420, ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if len(out) + len(sentence) > cut and out:
                break
            out = (out + " " + sentence).strip()
        return {"text": out, "lang": lang, "url": f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"}
    return None


def facts(a: dict) -> dict:
    qid = wikidata_id(a["name"], a["country"])
    tracks = db.all("""SELECT t.title, MIN(o.position) AS best, COUNT(DISTINCT o.source || o.country_id) AS charts
                       FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                       WHERE t.artist_id = ? AND o.observed_on >= CURRENT_DATE - 7 GROUP BY t.id, t.title ORDER BY charts DESC, best LIMIT 5""", [a["id"]])
    best = db.one("""SELECT o.position, o.source, c.code, t.title FROM chart_observations o JOIN tracks t ON t.id = o.track_id
                     JOIN countries c ON c.id = o.country_id WHERE t.artist_id = ?
                     AND o.source NOT IN ('deezer_popularity', 'youtube_views')
                     ORDER BY o.position, o.observed_on DESC LIMIT 1""", [a["id"]])
    return {"artist_id": a["id"], "name": a["name"], "slug": a["slug"], "country": a["country"], "qid": qid,
            "awards": awards(qid)[:6] if qid else [], "bio": bio(a["name"], qid), "tracks": tracks, "best": best,
            "youtube_subscribers": a.get("youtube_subscribers"), "youtube_views_total": a.get("youtube_views_total"),
            "fans": a.get("fans"), "photo": a.get("image_hd_url") or a.get("image_url"), "credit": a.get("image_credit"),
            "spotify": _spotify(a.get("spotify_id"))}


def _spotify(spotify_id) -> dict | None:
    """Compteurs publics de Spotify (Kworb) ; None si l'artiste n'est pas suivi ou si Kworb ne répond pas."""
    try:
        from core.services import kworb
        return kworb.chiffres(spotify_id)
    except Exception:  # noqa: BLE001 — le portrait se fait sans ce bloc
        return None


def _n(v) -> str:
    return f"{int(v):,}".replace(",", " ")


def _bio_fr(bio: dict | None) -> dict | None:
    """La biographie en français : traduite fidèlement si Wikipédia n'a que l'anglais (jamais d'anglais dans une
    légende française, 20/10/2026) ; None si la traduction échoue (le portrait se fait sans)."""
    if not bio or bio.get("lang") == "fr":
        return bio
    try:
        from core.services import ai
        client = ai.make()
        r = client.ask("Tu traduis fidèlement de l'anglais vers le français, sans rien ajouter ni retirer, "
                       "noms propres et titres d'œuvres inchangés. Réponds uniquement par la traduction.",
                       bio["text"], max_tokens=1200)
        texte = (r.get("text") or "").strip().strip('"')
        return {**bio, "text": texte, "traduit": True} if len(texte) > 20 else None
    except Exception:  # noqa: BLE001
        return None


def _bio_courte(texte: str) -> str:
    """Biographie de magazine : 3 phrases, 45 mots au plus, français naturel, fidèle aux faits (Awa, 20/10/2026)."""
    try:
        from core.services import ai
        r = ai.make().ask("Tu es rédacteur d'un magazine musical. Résume fidèlement en français naturel, en 3 phrases "
                          "et 45 mots au maximum, sans rien inventer ni ajouter, sans formule lourde (« connu "
                          "professionnellement »). Noms propres et titres inchangés. Réponds uniquement par le résumé.",
                          texte, max_tokens=400)
        court = re.sub(r"[*_#`]+", "", (r.get("text") or "")).strip().strip('"')   # pas de mise en forme Markdown
        if 15 <= len(court.split()) <= 60:
            return court
    except Exception:  # noqa: BLE001
        pass
    return " ".join(texte.split(". ")[:2]).rstrip(".") + "."


def rendu_2026(name: str, f: dict, slides: list, country: str) -> list:
    """Portrait au style 2026 (20/10/2026) : couverture = sa meilleure photo de la banque en plein cadre (garde-fou
    visage), diapositives de lecture sur ses autres photos floutées ; 4:5 et 9:16."""
    from core import storage
    from core.services.social import couverture2026 as C, plans
    from core.services.social import image as PI
    lignes = db.all("SELECT id, fichier FROM artist_photos WHERE artist_id = ? ORDER BY COALESCE(score, 0.5) DESC, id LIMIT 12",
                    [f["artist_id"]])
    base = f"{storage.blob_public_url()}/media/artists/plans/"
    une = plans._premiere_valable(lignes)
    photo_une = base + une["fichier"] if une else f.get("photo")
    fonds = [base + r["fichier"] for r in lignes if not une or r["id"] != une["id"]] or [photo_une]
    nettes = [base + r["fichier"] for r in lignes if r is not une and plans._premiere_valable([r]) is r and (not une or r["id"] != une["id"])][:6] or [photo_une]

    def bas_du_visage(url):    # les cartes de verre couvrent le bas : visage le plus haut d'abord (jamais sous la carte)
        try:
            im = C._image(url)
            v = C._visages(C.cadrer(im, 1080, 1350)[0]) if im is not None else None
            return v[0][1] + v[0][3] if v else 1.0
        except Exception:  # noqa: BLE001
            return 1.0
    nettes = sorted(nettes, key=bas_du_visage)
    if une:
        db.run("UPDATE artist_photos SET utilise_le = NOW() WHERE id = ?", [une["id"]])
    PI.DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for fmt, suffixe in (("feed", ""), ("story", "-916")):
        images = [C.lockup(photo_une, [("Portrait", "petit"), (f["name"], "or"), (f"Artiste · {country}", "petit")], fmt)]
        n_verre = 0
        for k, s_ in enumerate(slides):
            titre = s_["big"][:1] + s_["big"][1:].lower()       # « Ses titres classés », pas de capitales partout
            titre = titre.replace(f["name"].lower(), f["name"])
            fond = fonds[k % len(fonds)]
            if s_.get("cta"):
                images.append(C.actu(nettes[(n_verre + 1) % len(nettes)], "SA FICHE", f"Tout sur {f['name']} : classements, titres et clips",
                                     [f["name"]], f"cauricharts.com/artiste/{f['slug']}", fmt, variante="voile"))
                continue
            if s_.get("rows"):
                lignes_c = []
                for a_, b_, c_ in s_["rows"]:
                    if isinstance(a_, int):                     # simple numéro d'ordre : la valeur est dans b
                        lignes_c.append((b_, c_ or ""))
                    elif s_["tag"] == "EN CE MOMENT" and len(b_) <= 18:   # « N°3  SLICK », puis « dans 17 classements »
                        lignes_c.append((f"{a_}  {b_}", c_ or ""))
                    else:                                        # « N°4 » ou « 2021 », puis le libellé
                        lignes_c.append((str(a_), b_ + (f" · {c_}" if c_ and s_["tag"] == "EN CE MOMENT" else "")))
                verre = s_["tag"] in ("EN CHIFFRES", "EN CE MOMENT")      # vraie photo nette + carte de verre
                images.append(C.chiffres(s_["tag"], titre, lignes_c, photo=nettes[n_verre % len(nettes)] if verre else fond, fmt=fmt, verre=verre))
                n_verre += 1 if verre else 0
            else:
                images.append(C.texte(s_["tag"], titre, s_.get("body") or "", s_.get("pied", ""), photo=fond, fmt=fmt))
        for i, im in enumerate(images):
            chemin = PI.save_jpeg(im.convert("RGB"), PI.DIR / f"{name}-{i + 1}{suffixe}.jpg")
            if fmt == "feed":
                out.append({"file": chemin.name if hasattr(chemin, "name") else str(chemin).split("/")[-1].split("\\")[-1],
                            "label": f["name"] if i == 0 else slides[i - 1]["big"]})
            else:
                out[i]["tiktok"] = chemin.name if hasattr(chemin, "name") else str(chemin).split("/")[-1].split("\\")[-1]
    return out


def post(day: date, artist_id: int | None = None, remplace: int | None = None) -> dict | None:
    """Le portrait du jour ; artist_id + remplace : refait un portrait déjà créé (même ligne, nouvelles images)."""
    from core.services import live_chart
    from core.services.social import editorial as E
    a = artiste(artist_id) if artist_id else pick(day)
    if not a:
        return None
    f = facts(a)
    f["bio"] = _bio_fr(f["bio"])
    f["bio_court"] = _bio_courte(f["bio"]["text"]) if f["bio"] else ""
    country = country_name(f["country"])
    stats = []
    if f["youtube_views_total"]:
        stats.append((1, _n(f["youtube_views_total"]) + " vues", "chaîne YouTube officielle, au total"))
    # abonnés incohérents avec les vues (autre chaîne relevée par erreur : 1 020 abonnés pour 68 M de vues) : écartés
    if f["youtube_subscribers"] and not (f["youtube_views_total"] and f["youtube_subscribers"] * 2000 < f["youtube_views_total"]):
        stats.append((2, _n(f["youtube_subscribers"]) + " abonnés", "sur YouTube"))
    if f["fans"]:
        stats.append((3, _n(f["fans"]) + " fans", "sur Deezer"))
    if f["best"]:
        b = f["best"]
        stats.append((4, f"N°{b['position']}", f"« {b['title']} », {live_chart.SOURCES.get(b['source'], b['source'])} {country_name(b['code'])} : sa meilleure place"))
    slides = [{"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "EN CHIFFRES", "big": f["name"].upper(),
               "rows": [(i + 1, v, d) for i, (_, v, d) in enumerate(stats)]}] if stats else []
    # Palmarès : récompenses (Wikidata), complétées par ses n°1 et meilleures places chez Cauri Charts
    # ses meilleures places (top 10 seulement), avec le titre du morceau ; une ligne par classement
    records = db.all("""SELECT DISTINCT ON (o.source, c.code) o.source, c.code, o.position AS best, t.title
                        FROM chart_observations o JOIN tracks t ON t.id = o.track_id JOIN countries c ON c.id = o.country_id
                        WHERE t.artist_id = ? AND o.source NOT IN ('deezer_popularity', 'youtube_views') AND o.position <= 10
                        ORDER BY o.source, c.code, o.position, o.observed_on DESC""", [f["artist_id"]])
    records = sorted(records, key=lambda r: (r["best"], r["source"]))[:4]
    rows = [(a_["year"] or "—", a_["award"], "") for a_ in f["awards"][:4]]
    rows += [(f"N°{r['best']}", f"« {r['title']} » · {live_chart.SOURCES.get(r['source'], r['source'])} {country_name(r['code'])}", "")
             for r in records][: max(0, 4 - len(rows))]
    if rows:
        slides.append({"bg": E.GOLD, "fg": E.INK, "acc": E.INK, "tag": "PALMARÈS",
                       "big": "SES RÉCOMPENSES" if f["awards"] else "SES MEILLEURES PLACES", "rows": rows})
    # Spotify en chiffres (compteurs publics relevés par Kworb), seulement pour les artistes qu'il suit
    sp = f.get("spotify")
    if sp:
        from core.services.kworb import volume
        rows = [(1, volume(sp["total"]) + " de streams", "sur Spotify, au total")]
        if sp["jour"] >= 1e5:
            rows.append((2, volume(sp["jour"]) + " par jour", "le rythme d'écoute en ce moment"))
        if sp["auditeurs"]:
            rows.append((3, volume(sp["auditeurs"]) + " d'auditeurs", "chaque mois" + (f" (record : {volume(sp['record_auditeurs'])})" if sp["record_auditeurs"] and sp["record_auditeurs"] > sp["auditeurs"] * 1.05 else "")))
        if sp["titres"]:
            t = sp["titres"][0]
            rows.append((4, volume(t["streams"]), f"« {t['titre']} »{' (en featuring)' if t['feat'] else ''}, son titre le plus écouté"))
        if sp["jours_cap"] is not None and sp["jours_cap"] <= 60:
            rows.append((5, volume(sp["cap"]), f"le prochain cap, d'ici {sp['jours_cap']} jour{'s' if sp['jours_cap'] > 1 else ''} à ce rythme"))
        slides.append({"bg": E.VIOLET, "fg": E.WHITE, "acc": E.GOLD, "tag": "SPOTIFY EN CHIFFRES", "big": "SES STREAMS", "rows": rows})
    if f["bio"]:
        src = "Wikipédia" + ("" if f["bio"]["lang"] == "fr" else ", traduit de l'anglais")
        slides.append({"bg": E.CREAM, "fg": E.INK, "acc": E.VIOLET, "tag": "BIOGRAPHIE", "big": "SON HISTOIRE",
                       "body": f["bio_court"], "pied": f"Source : {src} (CC BY-SA)"})
    titres = sorted([t for t in f["tracks"] if t["best"] <= 20], key=lambda t: t["best"])[:4]
    if titres:
        slides.append({"bg": E.VIOLET, "fg": E.WHITE, "acc": E.GOLD, "tag": "EN CE MOMENT", "big": "SES TITRES CLASSÉS",
                       "rows": [(f"N°{t['best']}", t["title"], f"meilleure place cette semaine · dans {t['charts']} classement{'s' if t['charts'] > 1 else ''}")
                                for t in titres]})
    if len(slides) < 2:
        return None  # trop peu de faits pour un vrai portrait
    slides.append({"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "SA FICHE", "big": "TOUT SUR " + f["name"].upper(),
                   "body": f"Classements, titres, chiffres et clips : cauricharts.com/artiste/{f['slug']}", "cta": "SUIVRE CAURI"})
    year, week, _ = day.isocalendar()
    name = f"{day.isoformat()}-portrait-{f['slug']}"[:80]
    files = rendu_2026(name, f, slides, country)
    bits = [f"Portrait : {f['name']} ({country})."]
    if f["bio"]:
        bits.append(f["bio_court"])
    if stats:
        bits.append("En chiffres : " + " ; ".join(f"{v} {d}" for _, v, d in stats[:3]) + ".")
    if sp:
        bits.append(f"Sur Spotify : {volume(sp['total'])} de streams au total"
                    + (f", {volume(sp['auditeurs'])} d'auditeurs chaque mois" if sp["auditeurs"] else "")
                    + (f" ; son titre le plus écouté, « {sp['titres'][0]['titre']} », dépasse les {volume(sp['titres'][0]['streams'])}" if sp["titres"] else "") + ".")
    if f["awards"]:
        bits.append("Palmarès : " + " ; ".join(f"{a_['award']}" + (f" ({a_['year']})" if a_["year"] else "") for a_ in f["awards"][:3]) + ".")
    bits.append("Sa fiche complète : lien en bio.")
    if f["bio"]:
        bits.append("Bio : Wikipédia" + (", traduite de l'anglais" if f["bio"].get("traduit") else "")
                    + " (CC BY-SA). Données : Cauri Charts, YouTube, Deezer, Wikidata" + (", Spotify (compteurs publics, via Kworb)." if sp else "."))
    if f["credit"]:
        bits.append(f["credit"])
    tag = "#" + re.sub(r"[^A-Za-z0-9]", "", f["name"])
    if remplace:
        from core import storage
        storage.publish_media_files("social", [x["file"] for x in files] + [x["tiktok"] for x in files])
        faits = {"kind": "portrait", "artist_id": f["artist_id"], "qid": f["qid"], "week": week}
        db.update("social_posts", {"caption": "\n\n".join(bits), "carousel": json.dumps(files, ensure_ascii=False),
                                   "image_square": files[0]["file"], "image_story": files[0]["tiktok"],
                                   "facts": json.dumps(faits, ensure_ascii=False, default=str)}, "id = :id", {"id": remplace})
        return db.one("SELECT * FROM social_posts WHERE id = ?", [remplace])
    return E.save_post("portrait", day.isoformat(), f"Portrait : {f['name']}", "\n\n".join(bits),
                       f"#CauriCharts #Portrait {tag} #{re.sub(r'[^A-Za-z]', '', country)} #AfriqueDeLOuest",
                       files, {"kind": "portrait", "artist_id": f["artist_id"], "qid": f["qid"], "week": week})
