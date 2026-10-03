"""Génère un post réseaux sociaux à partir de faits réels (traduction de Social\\PostGenerator).

Avec une clé d'IA : texte rédigé dans le ton d'un magazine de classements ; sans clé : modèle de texte, aussi fiable.
Le post est enregistré en brouillon : un humain le relit avant publication.
"""
import glob
import json
import os
import re
import secrets
import time
from datetime import date

from core import clock
from core import conf, db, storage
from core.helpers import country_name
from core.services import ai
from core.services.platforms import log_write
from core.services.social import carousel as PC
from core.services.social import export as PE
from core.services.social import facts as PF
from core.services.social import image as PI

SYSTEM = """Tu es rédacteur en chef social media de Cauri Charts, le classement musical de l'Afrique de l'Ouest (Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal),
dans l'esprit des grands classements musicaux internationaux : accroche forte dès la première ligne, chiffres mis en avant, fierté pour les artistes, ton enthousiaste mais crédible.
Règles absolues :
- Ne cite jamais un autre classement ou média musical (Billboard, etc.) : Cauri Charts est « la référence de la musique ouest-africaine ».
- Utilise UNIQUEMENT les faits fournis. N'invente aucun chiffre, aucune position, aucun record, aucune citation, aucune date de sortie.
- N'attribue aucun genre, ambiance ou style (« gothique », « sombre », « romantique »…) : les faits n'en contiennent pas.
- Recopie les noms d'artistes et de titres EXACTEMENT comme dans les faits (orthographe, majuscules, « feat. »).
- Le titre du visuel reprend le champ "headline" des faits, sans rien y ajouter.
- Cite toujours d'où viennent les chiffres (champ "source"). Si ce ne sont pas des classements Cauri Charts, ne dis pas « classement Cauri Charts » : dis « dans les classements Apple Music / Deezer / YouTube ».
- Français, 2 à 4 emojis maximum, phrases courtes, lisible sur mobile. Termine par une question qui invite à commenter.
- 3 à 5 hashtags pertinents (artistes, pays, genres), sans #CauriCharts (ajouté automatiquement).
Réponds uniquement par un objet JSON :
{"title": "titre du visuel, 45 caractères max", "lines": ["3 à 5 lignes courtes pour le visuel, 42 caractères max chacune"], "caption": "texte du post, 900 caractères max", "hashtags": ["#..."]}"""


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")


# Tics d'écriture des IA (repris du nettoyeur « ig-human ») : remplacés par une tournure simple ou retirés
SLOP = [(r"\s*[—–]\s*", ", "), (r"\bplongeons dans\b", "voici"), (r"\bdans le paysage musical\b", "dans la musique"),
        (r"\bn'est pas seulement\b", "est"), (r"\bsans plus attendre,?\s*", ""), (r"\bincontournable\b", "à écouter"),
        (r"\bvéritable phénomène\b", "succès"), (r"\bfaire vibrer\b", "faire danser"), (r"\ben ces temps\b", "en ce moment")]
INVISIBLE = re.compile("[​-‏⁠-⁯﻿­]")  # espaces de largeur nulle, marques, césures
NARROW = re.compile("[    ]")  # espaces insécables et séparateurs : une espace simple


def humanize(text: str) -> str:
    """Retire les caractères invisibles et les tics d'IA ; garde les retours à la ligne et les emojis."""
    text = NARROW.sub(" ", INVISIBLE.sub("", str(text)))
    for pattern, repl in SLOP:
        text = re.sub(pattern, repl, text, flags=re.I)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r" +([,.])", r"\1", text).strip()


def photo_credits(facts: dict) -> list:
    """Crédits des photos sous licence libre (Wikimedia Commons) des artistes du post."""
    names = {str(e.get("artist") or e.get("artist_name") or "") for e in facts.get("top") or []}
    names.add(str((facts.get("artist") or {}).get("name") or ""))
    names.discard("")
    if not names:
        return []
    rows = db.all(f"""SELECT name, image_credit FROM artists WHERE image_source = 'commons' AND image_credit IS NOT NULL
                       AND name IN ({','.join(['?'] * len(names))})""", list(names))
    return [f"{r['name']}, {r['image_credit'].removeprefix('Photo : ')}" for r in rows]


def own_image(e: dict):
    """Photo de l'artiste de cette ligne, sinon pochette de son titre ; None plutôt qu'une photo d'un autre artiste."""
    if e.get("track_id"):
        return db.value("""SELECT COALESCE(NULLIF(a.image_url, ''), NULLIF(t.cover_url, '')) FROM tracks t JOIN artists a ON a.id = t.artist_id
                           WHERE t.id = ?""", [int(e["track_id"])])
    if e.get("artist_id"):
        return db.value("SELECT NULLIF(image_url, '') FROM artists WHERE id = ?", [int(e["artist_id"])])
    return None


class PostGenerator:
    def __init__(self, ai_client=None):
        self.ai = ai_client

    def generate(self, theme: str, day: str | None = None, facts: dict | None = None):
        """facts fournis : post « sur demande » (custom.py) ; sinon faits de la rubrique."""
        day = day or clock.today().isoformat()
        facts = facts or PF.for_theme(theme)
        if not facts:
            return None
        text = None
        if self.ai and self.ai.is_available():
            try:
                text = self._write(facts)
            except Exception as exc:  # noqa: BLE001
                log_write("social", "error", str(exc))
        text = text or self.template(facts)
        if facts.get("request"):
            text["title"] = facts["headline"]  # post sur demande : titre construit par le site, jamais par l'IA
        text["hashtags"] = list(dict.fromkeys(list(conf.get("ai.social.hashtags_base")) + list(text.get("hashtags") or [])))
        text["title"], text["caption"] = humanize(text["title"]), humanize(text["caption"])
        credits = photo_credits(facts)
        if credits:
            text["caption"] += "\n\nPhotos : " + " ; ".join(credits)  # licence libre de Wikimedia Commons : crédit obligatoire

        name = f"{day}-{theme}-{secrets.token_hex(4)[:6]}"
        look = PI.style(name)
        facts["style"] = look["name"] if look else None  # habillage tiré pour ce post (polices, couleurs, filtre)
        images = PI.render(facts, text, name)
        cover = self._cover(facts)
        items = self._carousel_items(facts)
        car = PC.render(facts, cover, items, name)
        # Chaque diapositive porte un libellé : couverture, puis « N°1 - Artiste - Titre »… (noms des fichiers exportés)
        shift = 1 if car.get("cover", True) else 0  # Top 20 : pas de couverture, la 1re diapositive est le n°1
        labels = [f"Couverture - {cover['kicker']} {cover['headline']}"] * shift + [f"N°{it['rank']} - {it['artist']} - {it['title']}" for it in items]
        slides = []
        for i, file in enumerate(car["slides"]):
            item = items[i - shift] if i >= shift and i - shift < len(items) else None
            # « file » : diapositive 4:5 (Instagram, Facebook) ; « tiktok » : la même en 9:16
            slides.append({"file": file, "tiktok": car["slides_916"][i] if i < len(car["slides_916"]) else None,
                           "label": labels[i] if i < len(labels) else "",
                           "clip": (PC.find_clip(item) is not None) if item else None,
                           "youtube": item.get("youtube_url") if item else None,
                           "expect": f"{item['artist']} - {item['title']}.mp4" if item else None})
        row = {"slot_date": day, "theme": theme, "title": text["title"][:160], "caption": text["caption"],
               "hashtags": " ".join(text["hashtags"][:8])[:300], "facts": json.dumps(facts, ensure_ascii=False),
               # image_square : visuel du fil, désormais en 4:5 (nom de colonne historique)
               "image_square": images.get("post"), "image_story": images.get("story"),
               "carousel": json.dumps(slides, ensure_ascii=False), "video": car["video"], "status": "draft"}
        # Brouillon remplacé : ses fichiers (visuels, carrousel, calques, vidéo) sont supprimés avec lui
        for old in db.all("SELECT * FROM social_posts WHERE slot_date = ? AND theme = ? AND status = 'draft'", [day, theme]):
            delete_files(old)
        db.run("DELETE FROM social_posts WHERE slot_date = ? AND theme = ? AND status = 'draft'", [day, theme])
        row["id"] = db.insert("social_posts", row)
        # Serveur sans disque durable (GitHub Actions) : visuels et vidéo publiés sur Vercel Blob
        storage.publish_media_files("social", [images.get("post"), images.get("story"), car["video"]] + car["slides"] + car["slides_916"])
        row["folder"] = PE.export(row)
        return row

    def generate_next(self, day: str | None = None):
        """Rotation : la rubrique publiée depuis le plus longtemps qui a des données réelles."""
        from core.services.social import themes
        for theme in themes.rotation():
            post = self.generate(theme, day)
            if post:
                return post
        return None

    def _write(self, facts: dict) -> dict:
        # La phrase de la demande et l'explication interne ne sont pas des faits : l'IA ne les voit pas
        shown = {k: v for k, v in facts.items() if k not in ("request", "explanation", "measure", "unsupported", "style")}
        answer = self.ai.ask(SYSTEM, "Faits (JSON) :\n" + json.dumps(shown, ensure_ascii=False, indent=4, default=str), 1500)
        j = ai.extract_json(answer["text"])
        if not j or not j.get("title") or not j.get("caption"):
            raise RuntimeError("Réponse IA inexploitable")
        # Les hashtags vont dans leur champ : on retire ceux que le modèle a laissés en fin de texte
        caption = re.sub(r"(\s*#[^\W]+)+\s*$", "", str(j["caption"])).strip()
        lines = j.get("lines") or []
        tags = j.get("hashtags") or []
        return {"title": str(j["title"]), "lines": [str(x) for x in (lines if isinstance(lines, list) else [lines])][:5], "caption": caption,
                "hashtags": [str(h) for h in (tags if isinstance(tags, list) else [tags]) if str(h).startswith("#")]}

    @staticmethod
    def _cover(facts: dict) -> dict:
        if facts.get("cover"):
            return facts["cover"]
        k = facts["kind"]
        if k == "artist":
            fans = facts["artist"]["deezer_fans"]
            return {"kicker": "Artiste de la semaine", "headline": facts["artist"]["name"],
                    "subtitle": f"{_fmt(fans)} fans sur Deezer" if fans else "en Afrique de l’Ouest"}
        if k == "cauri_chart":
            return {"kicker": "Prime Chart", "headline": "Afrique de l’Ouest", "subtitle": "Le Top de la semaine"}
        if k == "platform_trends":
            return {"kicker": "Les titres qui dominent", "headline": "les plateformes", "subtitle": "en Afrique de l’Ouest cette semaine"}
        return {"kicker": "Ce que l’Afrique de l’Ouest", "headline": "écoute ce week-end", "subtitle": "Les nouvelles entrées des classements"}

    @staticmethod
    def _carousel_items(facts: dict) -> list:
        """Une diapositive par performance, avec un chiffre exact (vues YouTube, sinon meilleure position)."""
        if facts["kind"] == "artist":
            # Photo de l'artiste plutôt que la pochette (souvent couverte de texte)
            rows = [{**t, "artist": facts["artist"]["name"], "image": facts.get("image") or t.get("image_url")} for t in facts["tracks"]]
        else:
            # Chaque diapositive porte la photo de SON artiste (ou la pochette de son titre) : jamais celle du n°1 en remplacement
            rows = [{**e, "image": e.get("image_url") or own_image(e)} for e in facts["top"]]
        items = []
        for i, r in enumerate(rows[:20]):
            if "figure_value" in r or not r.get("track_id"):
                # Rubrique qui fournit son chiffre exact (vues, fans, n°1…), ou entrée sans titre (artiste, actualité)
                items.append({"rank": i + 1, "title": r["title"], "artist": r["artist"], "image": r.get("image"),
                              "figure_value": r.get("figure_value") or "", "figure_label": r.get("figure_label") or "",
                              "youtube_url": db.value("""SELECT url FROM track_platform_ids WHERE track_id = ? AND platform = 'youtube'
                                                         ORDER BY kind = 'clip' DESC, id LIMIT 1""", [int(r["track_id"])]) if r.get("track_id") else None})
                continue
            views = db.value("""SELECT SUM((SELECT s.plays FROM snapshots s WHERE s.track_platform_id = p.id ORDER BY s.captured_on DESC LIMIT 1))
                                FROM track_platform_ids p WHERE p.track_id = ? AND p.platform = 'youtube'""", [int(r["track_id"])]) if r.get("track_id") else None
            best = (r.get("seen") or [None])[0]
            if views:
                value, label = _fmt(views), "vues YouTube"
            elif best:
                value, label = f"N°{best['position']}", f"{best['platform']} {country_name(best['country'])}"
            else:
                value, label = "", ""
            items.append({"rank": int(r.get("position") or i + 1), "title": r["title"], "artist": r["artist"], "image": r.get("image"),
                          "figure_value": value, "figure_label": label,
                          # Clip officiel : lien YouTube de référence (pour le demander à l'artiste ou au label)
                          "youtube_url": db.value("""SELECT url FROM track_platform_ids WHERE track_id = ? AND platform = 'youtube'
                                                     ORDER BY kind = 'clip' DESC, id LIMIT 1""", [int(r["track_id"])]) if r.get("track_id") else None})
        return items

    @staticmethod
    def template(facts: dict) -> dict:
        """Texte sans IA, construit uniquement à partir des faits."""
        def pos(seen):
            return " · ".join(f"{s['platform']} {s['country']} n°{s['position']}" for s in seen[:2])
        lines, body = [], []
        k = facts["kind"]
        if k == "ranking":
            # Rubriques du registre (themes.py) : accroche, une ligne par entrée avec son détail chiffré, question
            for i, e in enumerate(facts["top"]):
                line = e.get("line") or f"{e['title']} — {e['artist']}" + (f" ({e['detail']})" if e.get("detail") else "")
                lines.append(f"{i + 1}. {e.get('row_title') or e['title']}")
                body.append(f"{i + 1}. {line}")
            body.insert(0, facts["intro"])
            body.append(facts["question"])
        elif k == "cauri_chart":
            lines = [f"{e['position']}. {e['title']} — {e['artist']}" for e in facts["top"]]
            one = facts["top"][0]
            body.append(f"🏆 {one['artist']} est n°1 du Prime Chart Afrique de l’Ouest avec « {one['title']} ».")
            if facts.get("climber"):
                c = facts["climber"]
                body.append(f"📈 Plus forte montée : « {c['title']} » de {c['artist']} (+{c['gain']} places).")
            body.append("Le Top 5 de la semaine :")
            body += lines
            body.append("Classement complet sur notre site. Votre n°1 à vous, c’est lequel ?")
        elif k == "platform_trends":
            for i, e in enumerate(facts["top"]):
                lines.append(f"{i + 1}. {e['title']} — {e['artist']}")
                body.append(f"{i + 1}. « {e['title']} » de {e['artist']} ({pos(e['seen'])})")
            body.insert(0, "🔥 Les titres qui dominent les plateformes en Afrique de l’Ouest cette semaine :")
            body.append("D’après les classements Apple Music, Deezer et YouTube. Lequel tourne en boucle chez vous ?")
        elif k == "artist":
            a = facts["artist"]
            lines = [f"{t['title']} — {pos(t['seen'])}" for t in facts["tracks"]]
            body += [f"⭐ Artiste de la semaine : {a['name']}.", "Présent cette semaine dans les classements :"]
            body += [f"• « {t['title']} » : {pos(t['seen'])}" for t in facts["tracks"]]
            if a["deezer_fans"]:
                body.append(f"{_fmt(a['deezer_fans'])} fans sur Deezer.")
            body.append(f"Votre titre préféré de {a['name']} ?")
        else:  # weekend
            lines = [f"{e['title']} — {e['artist']}" for e in facts["top"]]
            body.append("🎧 Nouveaux dans les classements cette semaine :")
            body += [f"• « {e['title']} » de {e['artist']} ({pos(e['seen'])})" for e in facts["top"]]
            if facts.get("news"):
                body.append(f"📰 À lire : {facts['news'][0]['title']} ({facts['news'][0]['source_name']})")
            body.append("Qu’est-ce qui passe dans vos écouteurs ce week-end ?")
        body.append(f"Source : {facts['source']}.")
        return {"title": facts["artist"]["name"] if k == "artist" else facts["headline"], "lines": lines[:5],
                "caption": "\n".join(body), "hashtags": []}


def _slide_files(post: dict) -> list:
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    files = []
    for s in slides:
        files += [s.get("file"), s.get("tiktok")] if isinstance(s, dict) else [s]
    return [f for f in files if f]


def delete_files(post: dict) -> None:
    """Supprime les fichiers générés d'un post (public/media/social), calques de clips compris."""
    for f in [post.get("image_square"), post.get("image_story"), post.get("video")] + _slide_files(post):
        if f and (PI.DIR / os.path.basename(f)).is_file():
            (PI.DIR / os.path.basename(f)).unlink()
    if post.get("video"):
        prefix = os.path.splitext(os.path.basename(post["video"]))[0]
        for f in glob.glob(str(PI.DIR / f"{glob.escape(prefix)}-*-calque.png")):
            os.unlink(f)


BLOB_KEEP_DAYS = 7  # 7 jours après la date de publication (Buffer et les réseaux gardent leur copie) ; Blob gratuit : 1 Go


def purge_blob(keep_days: int = BLOB_KEEP_DAYS) -> str:
    """Ménage du Blob : visuels et vidéos des posts de plus de keep_days jours, et fichiers qu'aucun post n'utilise
    (essais, posts régénérés) après un jour. Les vignettes d'actualités et les autres dossiers ne sont pas touchés."""
    from datetime import datetime, timedelta, timezone
    from core import storage
    if not storage.blob_token():
        return "Blob non configuré"
    recent = set()
    for p in db.all("SELECT image_square, image_story, video, carousel FROM social_posts WHERE slot_date >= CURRENT_DATE - ?", [keep_days]):
        recent.update(os.path.basename(x) for x in [p["image_square"], p["image_story"], p["video"]] + _slide_files(p) if x)
    recent |= {f.rsplit(".", 1)[0] + "-tt.jpg" for f in recent}  # copies TikTok 1080 × 1920
    now = datetime.now(timezone.utc)
    old, size = [], 0
    for b in storage.blob_list("media/social/"):
        name = b["pathname"].rsplit("/", 1)[-1]
        age = now - datetime.fromisoformat(b["uploadedAt"].replace("Z", "+00:00"))
        if name not in recent and age > timedelta(days=1):
            old.append(b["url"])
            size += int(b.get("size") or 0)
    storage.blob_delete(old)
    return f"Blob : {len(old)} fichiers anciens supprimés ({size / 1e6:.0f} Mo libérés)"


def purge_orphans() -> int:
    """Supprime les fichiers de public/media/social qu'aucun post n'utilise plus (plus d'une heure)."""
    used = set()
    for p in db.all("SELECT image_square, image_story, video, carousel FROM social_posts"):
        used.update(x for x in [p["image_square"], p["image_story"], p["video"]] + _slide_files(p) if x)
        if p["video"]:
            prefix = os.path.splitext(os.path.basename(p["video"]))[0]
            used.update(os.path.basename(c) for c in glob.glob(str(PI.DIR / f"{glob.escape(prefix)}-*-calque.png")))
    used = {os.path.basename(u) for u in used}
    n = 0
    for ext in ("png", "jpg", "mp4"):
        for file in glob.glob(str(PI.DIR / f"*.{ext}")):
            if os.path.basename(file) not in used and os.path.getmtime(file) < time.time() - 3600:
                os.unlink(file)
                n += 1
    return n
