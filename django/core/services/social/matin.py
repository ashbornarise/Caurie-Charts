"""Cauri Matin : le journal du lundi, du mercredi et du vendredi, à 7 h (heure de Lomé).

Un numéro = un carrousel sur les réseaux, le même numéro en article dans Actualités, un envoi Telegram.
Tout vient des relevés et des médias importés (aucune IA, aucun chiffre inventé) :
  une          : l'artiste n°1 du Top 20 Afrique de l'Ouest ce matin ;
  ça bouge     : les plus fortes progressions depuis le numéro précédent (sinon : sur une semaine) ;
  nouveaux     : les titres entrés dans le Top 50 depuis le numéro précédent ;
  l'actu       : trois actualités de la région, avec leur média ;
  à écouter    : la sortie récente la mieux classée ;
  ce soir      : le post de 18 h du jour.
Seuls les artistes au pays confirmé apparaissent ; les rangs restent ceux du classement du site.
"""
import json
from datetime import date

from core import db
from core.helpers import country_name, slugify
from core.repos import now_utc
from core.services import live_chart


def _who(r: dict) -> str:
    return r["artist_name"] + (f" · {country_name(r['artist_country'])}" if r.get("artist_country") else "")


def previous() -> dict | None:
    row = db.one("SELECT facts FROM social_posts WHERE theme = 'matin' AND slot_date < CURRENT_DATE ORDER BY slot_date DESC LIMIT 1")
    try:
        return json.loads(row["facts"]) if row else None
    except ValueError:
        return None


def facts(day: date) -> dict:
    top = [r for r in live_chart.build(None, None, 50, "prime", 20, "latest")["rows"] if not r.get("is_artist")]
    ok = [r for r in top if r.get("status") == "active"]
    prev = previous()
    before = {int(k): v for k, v in ((prev or {}).get("ranks") or {}).items()}
    if before:
        moves = sorted(((before[int(r["track_id"])] - int(r["rank"]), r) for r in ok if int(r["track_id"]) in before),
                       key=lambda m: -m[0])
        movers = [dict(r, gain=g) for g, r in moves if g > 0][:4]
        entries = [r for r in ok if int(r["track_id"]) not in before][:4]
        since = prev.get("day")
    else:
        buzz = [r for r in live_chart.build(None, None, 20, "buzz", 20, "week")["rows"] if r.get("status") == "active"]
        movers, entries, since = [dict(r, gain=None) for r in buzz[:4]], [], None
    fresh = [r for r in live_chart.build(None, None, 20, "fresh", 20, "latest")["rows"] if r.get("status") == "active"]
    # Seulement l'actualité d'un des 16 pays (les flux généralistes parlent aussi d'autres régions)
    from core.services.news import is_about_music
    news = [x for x in db.all("""SELECT title, summary, source_name FROM news WHERE status = 'published' AND origin = 'feed'
                                 AND country_id IS NOT NULL AND published_at >= LOCALTIMESTAMP - INTERVAL '3 days'
                                 ORDER BY published_at DESC LIMIT 15""")
            if is_about_music(x["title"].lower())][:3]  # le titre doit parler de musique (pas seulement le résumé)
    tonight = db.one("SELECT title FROM social_posts WHERE slot_date = ? AND theme NOT IN ('matin', 'hebdo', 'presentation') ORDER BY id DESC LIMIT 1",
                     [day.isoformat()])
    number = int(db.value("SELECT COUNT(*) FROM social_posts WHERE theme = 'matin' AND slot_date < ?", [day.isoformat()]) or 0) + 1
    return {"day": day.isoformat(), "number": number, "since": since, "one": ok[0] if ok else None, "movers": movers,
            "entries": entries, "fresh": fresh[0] if fresh else None, "news": news, "tonight": tonight["title"] if tonight else None,
            "ranks": {int(r["track_id"]): int(r["rank"]) for r in top}}


def post(day: date) -> dict | None:
    from core.services.social import editorial as E
    from core.services.social.generator import own_image
    f = facts(day)
    if not f["one"]:
        return None
    one, n = f["one"], f["number"]
    when = f"depuis le {date.fromisoformat(f['since']):%d/%m}" if f["since"] else "sur une semaine"
    slides = []
    if f["movers"]:
        slides.append({"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": f"ÇA BOUGE · {when.upper()}", "big": "LES PLUS FORTES MONTÉES",
                       "rows": [(f"+{m['gain']}" if m["gain"] else i + 1, m["title"],
                                 _who(m) + (f" · n°{m['rank']} ce matin" if m["gain"] else " · en forte hausse cette semaine"))
                                for i, m in enumerate(f["movers"])]})
    if f["entries"]:
        slides.append({"bg": E.VIOLET, "fg": E.WHITE, "acc": E.GOLD, "tag": "ILS ENTRENT", "big": "NOUVEAUX DANS LE TOP 50",
                       "rows": [(f"N°{e['rank']}", e["title"], _who(e)) for e in f["entries"]]})
    if f["news"]:
        slides.append({"bg": E.CREAM, "fg": E.INK, "acc": E.VIOLET, "tag": "L'ACTU DE LA RÉGION", "big": "À LIRE CE MATIN",
                       "rows": [(i + 1, x["title"][:90], x["source_name"] or "") for i, x in enumerate(f["news"])]})
    if f["fresh"]:
        x = f["fresh"]
        slides.append({"bg": E.GOLD, "fg": E.INK, "acc": E.INK, "tag": "À ÉCOUTER", "big": x["title"].upper(),
                       "body": f"{_who(x)}. La sortie récente la mieux classée ce matin : n°{x['rank']} du classement des nouveautés."})
    slides.append({"bg": E.INK, "fg": E.WHITE, "acc": E.GOLD, "tag": "CE SOIR · 18 H", "big": (f["tonight"] or "LE CLASSEMENT EN DIRECT").upper(),
                   "body": "Le classement complet, en direct, sur cauricharts.com. Prochain numéro de Cauri Matin : "
                           + ("mercredi" if day.isoweekday() == 1 else "vendredi" if day.isoweekday() == 3 else "lundi") + " à 7 h.",
                   "cta": "S'ABONNER"})
    name = f"{day.isoformat()}-matin-{n}"
    cover = {"kicker": f"Cauri Matin n°{n} · {day:%d/%m}", "headline": one["artist_name"],
             "subtitle": f"« {one['title']} » · n°{one['rank']} Afrique de l'Ouest",
             "photo": one.get("artist_image") or own_image(one) or one.get("cover_url")}
    files = E.render(name, slides, cover)
    from core.services.magazine import de
    lines = [f"Cauri Matin n°{n}, {day:%d/%m/%Y}. « {one['title']} » {de(one['artist_name'])} est n°{one['rank']} du Top 20 Afrique de l'Ouest ce matin."]
    if f["movers"] and f["movers"][0]["gain"]:
        m = f["movers"][0]
        lines.append(f"Plus forte montée {when} : « {m['title']} » {de(m['artist_name'])}, +{m['gain']} places.")
    if f["entries"]:
        lines.append("Nouveaux dans le Top 50 : " + ", ".join(f"« {e['title']} » ({e['artist_name']})" for e in f["entries"][:3]) + ".")
    if f["news"]:
        lines.append("À lire : " + " ; ".join(f"{x['title']} ({x['source_name']})" for x in f["news"]) + ".")
    if f["tonight"]:
        lines.append(f"Ce soir à 18 h : {f['tonight']}.")
    lines.append("Classement en direct : lien en bio.")
    caption = "\n\n".join(lines)
    post = E.save_post("matin", day.isoformat(), f"Cauri Matin n°{n}", caption,
                       "#CauriMatin #CauriCharts #AfriqueDeLOuest #Afrobeats #Top20", files, f)
    _article(f, caption, files)
    return post


def _article(f: dict, caption: str, files: list) -> None:
    """Le même numéro dans Actualités (une seule fois par jour)."""
    guid = f"cauri-matin-{f['day']}"
    if db.value("SELECT 1 FROM news WHERE external_guid = ?", [guid]):
        return
    from core.services.magazine import de
    title = f"Cauri Matin n°{f['number']} : « {f['one']['title']} » {de(f['one']['artist_name'])}, n°{f['one']['rank']} ce matin"
    body = caption.replace("Classement en direct : lien en bio.", "Classement complet et méthode sur cauricharts.com.")
    db.insert("news", {"title": title[:200], "slug": slugify(title)[:180] + "-" + f["day"], "summary": caption.split("\n\n")[0][:400],
                       "body": body, "category": "classement", "country_id": None, "source_name": "Cauri Charts", "source_url": None,
                       "image_path": None, "origin": "manual", "external_guid": guid, "status": "published", "published_at": now_utc()})
