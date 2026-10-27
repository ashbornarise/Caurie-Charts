"""Hashtags contextuels choisis juste avant la publication (demande du fondateur, 27/10/2026).

On lit le sujet du post (titre, légende, étiquette, artiste) et on garde 5 hashtags : #cauricharts, l'artiste, puis
les tags les plus utilisés du sujet (événement ou format, pays, genre). Chaque liste ci-dessous est rangée du tag le
plus utilisé au moins utilisé sur Instagram et TikTok. L'IA gratuite (Gemini) peut ajouter le tag précis d'un
événement (#ballondor, #grammys…) ; sans clé ou en cas d'échec, les règles seules suffisent.
Toujours en minuscules (règle du 26/10/2026).
"""
import json
import re
import unicodedata

from core import db, env

MAX_TAGS = 5

# (motif cherché dans le texte, tags du plus utilisé au moins utilisé)
EVENEMENTS = [   # motifs sans accents : le texte est comparé sans accents
    (r"ballon d.or", ["#ballondor"]),
    (r"grammy", ["#grammys", "#grammy"]),
    (r"\bbet awards|\bbet 20", ["#betawards"]),
    (r"headies", ["#headies"]),
    (r"\bvgma\b|ghana music awards", ["#vgma"]),
    (r"tapis rouge|red carpet", ["#redcarpet", "#tapisrouge"]),
    (r"\binterview|\bdebrief|\btalk\b|podcast|\bse confie|\braconte", ["#interview"]),
    (r"\bconcert|\bsur scene|\blive\b|festival|\btournee\b|\bshowcase", ["#concert", "#live"]),
    (r"\bclash|\bbeef\b|\brepond|polemique|comparaison", ["#clash"]),
    (r"challenge|\bdanse\b|\bdance\b|choregraph", ["#dance", "#challenge"]),
    (r"freestyle", ["#freestyle"]),
    (r"nouveau (son|single|clip|titre)|new (music|song|single)|vient de sortir|clip officiel", ["#newmusic", "#nouveauclip"]),
    (r"\bnouvel album|\bnew album|\bson album|\bl.album\b", ["#newalbum"]),
    (r"\bmariage|\bbebe\b|\ben couple", ["#people"]),
    (r"\btenue|\bcostume|\bfashion|\bdefile", ["#fashion"]),
    (r"football|\bstade\b|\bmatch\b", ["#football"]),
    (r"\ben studio|\benregistre", ["#studio"]),
]
PAYS = {
    "TG": ["#togo", "#lome", "#228"], "GH": ["#ghana", "#accra", "#ghanamusic"], "NG": ["#naija", "#nigeria", "#lagos"],
    "CI": ["#abidjan", "#cotedivoire", "#225"], "BJ": ["#benin", "#cotonou", "#229"], "SN": ["#senegal", "#dakar"],
    "CM": ["#cameroun", "#237"], "ML": ["#mali", "#bamako"], "BF": ["#burkinafaso"], "NE": ["#niger"],
}
PAYS_MOTS = [(r"\btogo|\blome\b", "TG"), (r"ghana|\baccra", "GH"), (r"nigeria|\bnaija|\blagos", "NG"),
             (r"cote d.ivoire|abidjan|ivoirien", "CI"), (r"\bbenin|cotonou", "BJ"), (r"senegal|\bdakar", "SN"),
             (r"cameroun", "CM"), (r"\bmali\b|bamako", "ML"), (r"burkina", "BF"), (r"\bniger\b|niamey", "NE")]
GENRES = [(r"amapiano", ["#amapiano"]), (r"coupe.decale", ["#coupedecale"]), (r"zouglou", ["#zouglou"]),
          (r"\bdrill\b", ["#drill"]), (r"gospel", ["#gospel"]), (r"highlife", ["#highlife"]), (r"dancehall", ["#dancehall"]),
          (r"\brap\b|rappeur", ["#rap"]), (r"afrobeat", ["#afrobeats"])]
GENRE_PAYS = {"CI": "#coupedecale", "GH": "#afrobeats", "NG": "#afrobeats", "TG": "#afrobeats", "BJ": "#afrobeats"}
LARGE = ["#afrobeats", "#musiqueafricaine"]


def _plat(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()


def tag(nom: str) -> str:
    """« Burna Boy » → « #burnaboy »."""
    return "#" + re.sub(r"[^a-z0-9]", "", _plat(nom)) if re.sub(r"[^a-z0-9]", "", _plat(nom)) else ""


def _pays_artiste(artiste: str) -> str | None:
    if not artiste:
        return None
    try:
        r = db.one("SELECT origin_country, base_country FROM artists WHERE lower(name) = lower(?) LIMIT 1", [artiste])
    except Exception:  # noqa: BLE001 — base indisponible : on s'en passe
        return None
    code = str((r or {}).get("origin_country") or (r or {}).get("base_country") or "").upper()[:2]
    return code if code in PAYS else None


def _ia(sujet: str, deja: list) -> list:
    """Un ou deux tags d'événement précis proposés par l'IA gratuite (jamais de tag inventé ou générique)."""
    if env.get("HASHTAGS_IA", "1") in ("0", "non"):
        return []
    from core.services import ai
    client = ai.make()
    if not client:
        return []
    try:
        rep = client.ask("Tu choisis des hashtags Instagram/TikTok. Réponds seulement en JSON.",
                         "Sujet du post :\n" + sujet[:800] + "\n\nHashtags déjà pris : " + " ".join(deja) +
                         "\n\nDonne au plus 2 hashtags supplémentaires, très utilisés et propres à CE sujet "
                         "(événement, émission, tendance), et seulement des tags qui existent déjà avec des centaines de milliers de "
                         "publications. Jamais de tag inventé ni générique (#music, #fyp, #viral). Liste vide si aucun. "
                         'Format : {"hashtags": ["#..."]}', max_tokens=200)
        data = ai.extract_json(rep.get("text") or "") or {}
    except Exception:  # noqa: BLE001
        return []
    return [t for t in (tag(str(h).lstrip("#")) for h in data.get("hashtags") or []) if 2 < len(t) <= 30][:2]


def choisir(titre: str, legende: str = "", artiste: str = "", etiquette: str = "", ia: bool = True) -> str:
    """Les 5 hashtags du post, du plus important au moins important."""
    sujet = " ".join(x for x in (etiquette, titre, legende) if x)
    plat = _plat(sujet)
    tags = ["#cauricharts"]
    if tag(artiste):
        tags.append(tag(artiste))
    evts = [t for rx, ts in EVENEMENTS if re.search(rx, plat) for t in ts]
    pays = _pays_artiste(artiste) or next((c for rx, c in PAYS_MOTS if re.search(rx, plat)), None)
    genres = [t for rx, ts in GENRES if re.search(rx, plat) for t in ts]
    extra = _ia(sujet, tags + evts[:1]) if ia else []
    # un précis (événement), un local (pays), celui de l'IA, un de genre, puis le reste par ordre d'usage
    ordre = evts[:1] + (PAYS[pays][:1] if pays else []) + extra[:1] + (genres[:1] or [GENRE_PAYS.get(pays, LARGE[0])]) \
        + evts[1:] + extra[1:] + (PAYS[pays][1:] if pays else []) + LARGE
    for t in ordre:
        if len(tags) >= MAX_TAGS:
            break
        if t not in tags:
            tags.append(t)
    return " ".join(tags)


def preparer(post: dict) -> dict:
    """Fixe une fois pour toutes les hashtags contextuels d'un post vidéo du Studio, des clips ou des interviews
    (facts « tags_auto ») avant son premier envoi ; les autres posts gardent leurs hashtags écrits à la main."""
    if post.get("id"):   # déjà fait par un autre canal (Buffer puis Telegram) : on reprend ce qui est en base
        try:
            frais = db.one("SELECT hashtags, facts FROM social_posts WHERE id = ?", [post["id"]])
        except Exception:  # noqa: BLE001
            frais = None
        if frais and '"tags_auto": true' in str(frais.get("facts") or ""):
            return {**post, "hashtags": frais["hashtags"], "facts": frais["facts"]}
    try:
        faits = json.loads(post.get("facts") or "{}")
    except ValueError:
        return post
    if faits.get("tags_auto") or faits.get("kind") not in ("format-clip", "format-video"):
        return post
    texte = post.get("caption") or ""
    # IA seulement pour les posts du Studio (actu chaude) ; clips et interviews : les règles suffisent (économie)
    tags = choisir(post.get("title") or "", texte, faits.get("artiste") or "", faits.get("etiquette") or "",
                   ia=str(post.get("theme") or "").startswith("format-studio"))
    faits["tags_auto"] = True
    post = {**post, "hashtags": tags, "facts": json.dumps(faits, ensure_ascii=False)}
    if post.get("id"):
        try:
            db.run("UPDATE social_posts SET hashtags = ?, facts = ? WHERE id = ?", [tags, post["facts"], post["id"]])
        except Exception:  # noqa: BLE001
            pass
    return post
