"""Légendes bilingues : chaque post part en français puis en anglais (🇫🇷 / 🇬🇧), pour le public anglophone
(Nigeria, Ghana, diaspora, international) sans quitter nos comptes.

La version anglaise est une traduction fidèle de la légende française (l'IA traduit, elle n'ajoute rien) : noms
d'artistes, titres de chansons et d'albums, chiffres et noms de rubriques restent tels quels. Elle est gardée dans
les faits du post (clé « en ») : un même post envoyé à plusieurs réseaux n'est traduit qu'une fois.
Sans IA disponible, le post part en français seulement (jamais bloqué)."""
import json

from core import db
from core.services.platforms import log_write

DRAPEAU_EN = "🇬🇧"
LIEN = "Lien en bio · Link in bio : cauricharts.com"

# 20 messages d'appel à l'abonnement : un différent à chaque post, déterministe (même post = même message)
_CTA = [
    "👉 Abonne-toi pour ne rien rater · Follow for more",
    "👉 Du contenu musical frais chaque jour — abonne-toi · Fresh music daily — follow us",
    "👉 Si tu aimes la musique, tu es chez toi — abonne-toi · Love music? You're home — follow",
    "👉 Découvre des artistes que tu ne connaissais pas · Discover artists you didn't know — follow",
    "👉 Le classement officiel, chaque mardi — abonne-toi · Official charts every Tuesday — follow",
    "👉 600+ artistes suivis dans 16 pays — abonne-toi · 600+ artists across 16 countries — follow",
    "👉 Tu veux t'éduquer sur la musique de ta région ? Abonne-toi · Learn about your region's music — follow",
    "👉 Pas convaincu ? Reviens dans une semaine · Not convinced? Come back in a week",
    "👉 On poste tous les jours, 365 jours par an — abonne-toi · We post every single day — follow",
    "👉 Soutiens la musique ouest-africaine — abonne-toi · Support West African music — follow",
    "👉 Si tu as scrollé jusqu'ici, abonne-toi · If you scrolled this far, follow us",
    "👉 Tu connais l'artiste, mais connais-tu son classement ? Abonne-toi · Know your fave's rank? Follow",
    "👉 Des clips, des chiffres, des histoires — abonne-toi · Clips, numbers, stories — follow",
    "👉 La référence de la musique ouest-africaine · The reference for West African music — follow",
    "👉 Rejoins des milliers de mélomanes — abonne-toi · Join thousands of music lovers — follow",
    "👉 Active la cloche pour ne pas manquer les classements · Turn on notifications for charts",
    "👉 Partage avec un ami qui aime la musique · Share with a friend who loves music",
    "👉 Tu vas apprendre quelque chose — abonne-toi · You'll learn something new — follow",
    "👉 3 posts par jour, 7 jours sur 7 — abonne-toi · 3 posts a day, 7 days a week — follow",
    "👉 Tu ne trouveras pas ça ailleurs — abonne-toi · You won't find this anywhere else — follow",
]
# longueur max pour le calcul de place dans la légende
_CTA_MAX = max(len(m) for m in _CTA)

SYSTEME = ("You translate French music-news social media captions into natural, punchy English for an international "
           "audience. You translate faithfully: never add facts, numbers, opinions or sources that are not in the French text.")


def _consigne(titre: str, legende: str, budget: int) -> str:
    return (
        "Translate this Cauri Charts post into English. Rules:\n"
        "- Keep EXACTLY as written: artist names, song and album titles (even when they are French words), "
        "festival/award names, media names, and the brand names Cauri Charts, Cauri Monde, Cauri Matin, Cauri Hebdo, "
        "The Monthly Show.\n"
        "- Numbers in English format: « 7,4 M » -> 7.4M, « 1 200 000 » -> 1,200,000, « 162 k » -> 162K.\n"
        "- « la référence de la musique ouest-africaine » -> « the reference for West African music ».\n"
        "- Keep emojis and the ⁉️ ‼️ marks; keep line breaks and the list layout (N°1 -> No.1).\n"
        "- Do NOT include hashtags, links or « lien en bio » lines: they are added separately.\n"
        f"- The English caption must be at most {budget} characters: condense if needed, keeping every key fact.\n"
        'Answer with JSON only: {"title": "...", "caption": "..."}\n\n'
        f"TITRE : {titre}\n\nLÉGENDE :\n{legende}")


def _sans_lien(legende: str) -> str:
    """La légende sans les lignes « Lien en bio » (le lien bilingue est ajouté une seule fois, à la fin)."""
    return "\n".join(l for l in (legende or "").split("\n") if not l.lower().startswith("lien en bio")).strip()


def mention_illustration(legende: str, langue: str = "fr") -> str:
    """Ajoute le crédit d'illustration dans la langue demandée, sans le dupliquer."""
    texte = "AI-generated illustration" if langue.lower().startswith("en") else "Illustration générée par IA"
    return legende if texte in (legende or "") else f"{(legende or '').rstrip()}\n\n{texte}"


def en(post: dict, budget: int) -> dict | None:
    """Version anglaise {title, caption} du post (≤ budget caractères), traduite une fois puis gardée dans ses faits."""
    try:
        faits = json.loads(post.get("facts") or "{}") or {}
    except ValueError:
        faits = {}
    deja = faits.get("en")
    if deja and deja.get("caption") and len(deja["caption"]) <= budget:
        return deja
    from core.services import ai
    client = ai.make()
    if not client or budget < 120:
        return None
    try:
        r = client.ask(SYSTEME, _consigne(post["title"], _sans_lien(post.get("caption")), budget), max_tokens=2500)
        out = ai.extract_json(r["text"]) or {}
    except Exception as exc:  # noqa: BLE001 — sans traduction, le post part en français
        log_write("social", "error", f"traduction anglaise du post {post.get('id')} : {exc}")
        return None
    titre, legende = str(out.get("title") or "").strip(), str(out.get("caption") or "").strip()
    if not titre or not legende:
        return None
    if len(legende) > budget:
        legende = legende[:budget - 1].rsplit("\n", 1)[0].rstrip() + "…"
    trad = {"title": titre[:160], "caption": legende}
    if post.get("id"):
        faits["en"] = trad
        db.run("UPDATE social_posts SET facts = ? WHERE id = ?", [json.dumps(faits, ensure_ascii=False, default=str), post["id"]])
        post["facts"] = json.dumps(faits, ensure_ascii=False, default=str)
    return trad


def cta(post: dict | None = None) -> str:
    """Message d'appel à l'abonnement tournant : chaque post a le sien, stable (même post = même message)."""
    if not post:
        return _CTA[0]
    graine = post.get("id") or hash(f"{post.get('slot_date', '')}{post.get('theme', '')}")
    return _CTA[int(graine) % len(_CTA)]


def legende(post: dict, lien: str | None = None, limite: int = 2200) -> str:
    """Légende complète : français, puis anglais, puis lien et hashtags (limite Instagram/TikTok : 2 200 caractères)."""
    lien = lien or LIEN
    tags = (post.get("hashtags") or "").strip()
    appel = cta(post)
    fr = f"{post['title']}\n\n{_sans_lien(post.get('caption'))}".strip()
    try:
        faits = json.loads(post.get("facts") or "{}") or {}
    except (ValueError, TypeError):
        faits = {}
    if faits.get("illustration_ia"):
        fr = f"{post['title']}\n\n{mention_illustration(_sans_lien(post.get('caption')))}"
    place = limite - len(lien) - len(tags) - _CTA_MAX - 42          # séparateurs, drapeau, appel à s'abonner et marge
    if len(fr) > place // 2:
        coupe = fr[: place // 2]
        fr = (coupe.rsplit("\n", 1)[0] if "\n" in coupe else coupe).rstrip()
    anglais = en(post, place - len(fr) - len(post["title"]) - 4)
    caption_en = mention_illustration(anglais["caption"], "en") if anglais and faits.get("illustration_ia") else (anglais or {}).get("caption", "")
    texte_en = f"{DRAPEAU_EN} {anglais['title']}\n\n{caption_en}" if anglais else ""
    trop = len("\n\n".join(p for p in (fr, texte_en, appel, lien, tags) if p)) - limite
    if texte_en and trop > 0:
        texte_en = texte_en[: len(texte_en) - trop - 1].rsplit("\n", 1)[0].rstrip() + "…"
    return "\n\n".join(p for p in (fr, texte_en, appel, lien, tags) if p)
