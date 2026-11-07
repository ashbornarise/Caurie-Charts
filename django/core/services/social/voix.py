"""La voix de Cauri Charts (06/11/2026) : celle d'un créateur de contenu média musique, pas d'une rédaction neutre.

Constat sur les 100 derniers posts TikTok (Buffer, 07/10 → 06/11/2026) : la moitié n'a fait aucune vue. Les titres qui
marchent donnent l'info tout de suite (« Didi B et Khaid s'associent sur le titre Malade » 984 vues ; « C'est confirmé,
Toofan… » 709 ; « Ninho revient sur une agression terrifiante subie à 14 ans » 524) ; ceux qui font zéro sont des
étiquettes de rubrique (« Cauri Monde · 30/10 · 8 h », « Cauri Matin n°12 », « Plus fortes progressions », « Portrait :
Wizkid »). D'où :
- VOIX : le guide de style donné à toutes les IA qui écrivent pour les réseaux ;
- accroche(post) : la première ligne de chaque post (français et anglais), une vraie info directe, écrite une fois et
  gardée dans les faits du post ; les posts du Studio gardent l'accroche choisie par le fondateur.
"""
import json
import re

from core import db

VOIX = """Tu écris pour Cauri Charts, « la référence de la musique ouest-africaine », comme un créateur de contenu média
musique suivi par des centaines de milliers de fans à Lomé, Abidjan, Lagos, Accra, Dakar ou Paris : celui qui annonce
la news en premier, avec ses mots, sans langue de bois, et qui sait pourquoi elle compte.

RÈGLES DU TITRE (la première ligne, la seule que la plupart des gens liront) :
- C'est l'INFORMATION elle-même, directe : qui, quoi, le fait qui surprend. Les noms des artistes d'abord.
- Verbe au présent, phrase courte : 80 caractères au plus.
- Si c'est fort et vrai, dis-le fort : record, première, chiffre, clash, annonce, surprise. Jamais d'exagération ni de
  fait inventé : seulement ce qui est dans les informations fournies.
- Interdit : les noms de rubrique (« Cauri Matin », « Cauri Monde », « Portrait : », « L'actu de la semaine »,
  « Plus fortes progressions »), les dates, les numéros d'édition, les formules creuses (« découvrez », « retour sur »,
  « voici », « incroyable »), les points d'exclamation en série. Un émoji au plus, seulement s'il ajoute du sens.
- Exemples du bon ton : « Didi B et Khaid s'associent sur Malade », « Toofan confirme le concert réclamé par les
  Togolais », « Ayra Starr N°1 au Nigeria pour la 4e semaine », « Ninho raconte l'agression qu'il a subie à 14 ans ».

RÈGLES DU TEXTE : deux ou trois phrases courtes qui apportent le contexte et un chiffre si on l'a, sans répéter le
titre ; puis une vraie question au public (avis, pronostic, souvenir), pas « qu'en pensez-vous ? »."""

INTERDITS = re.compile(r"cauri (matin|monde|hebdo)|portrait\s*:|l.actu de la semaine|plus fortes progressions|"
                       r"\b\d{1,2}/\d{1,2}\b|n°\s*\d+\s*·", re.I)


def _faits(post: dict) -> dict:
    try:
        return json.loads(post.get("facts") or "{}") or {}
    except (ValueError, TypeError):
        return {}


def valide(titre: str) -> bool:
    t = (titre or "").strip()
    return 12 <= len(t) <= 90 and not INTERDITS.search(t)


def accroche(post: dict) -> dict | None:
    """{"fr", "en"} : la première ligne du post. None : on garde le titre du post tel quel."""
    faits = _faits(post)
    if faits.get("accroche") and valide(faits["accroche"].get("fr", "")):
        return faits["accroche"]
    if str(post.get("theme") or "").startswith("format-studio"):
        return None   # le Studio garde l'accroche choisie par le fondateur
    from core import env
    if env.get("VOIX_IA", "1") == "0":
        return None   # tests : jamais d'appel à l'IA
    from core.services import ai
    client = ai.make()
    if not client:
        return None
    infos = f"Titre interne : {post.get('title')}\nTexte du post :\n{str(post.get('caption') or '')[:1500]}"
    try:
        r = client.ask(VOIX, infos + "\n\nÉcris le TITRE de ce post selon les règles, en français et en anglais. "
                       'Réponds seulement en JSON : {"fr": "...", "en": "..."}', max_tokens=300)
        texte = r.get("text") if isinstance(r, dict) else str(r)
        d = ai.extract_json(texte or "") or {}
    except Exception:  # noqa: BLE001 — sans IA, le titre du post reste
        return None
    fr, en = str(d.get("fr") or "").strip().strip("«»\" "), str(d.get("en") or "").strip().strip("\" ")
    if not valide(fr):
        return None
    resultat = {"fr": fr, "en": en if 8 <= len(en) <= 100 else ""}
    if post.get("id"):
        db.run("UPDATE social_posts SET facts = ? WHERE id = ?",
               [json.dumps({**faits, "accroche": resultat}, ensure_ascii=False, default=str), post["id"]])
    return resultat
