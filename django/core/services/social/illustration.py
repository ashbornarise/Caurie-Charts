"""Illustrations abstraites de secours pour les couvertures sans photo."""
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageEnhance
from io import BytesIO

from core import db, env, storage, clock
from core.services.platforms import log_write

FAMILLES = {"monde", "histoire", "anecdote", "record", "citation", "punchline", "evenement"}
# Style « colors room » (décision du 19/10/2026) : une pièce d'une seule couleur unie, contrastes forts, color blocking
COULEURS = ["electric violet", "electric sky blue", "neon orange", "candy red", "sunflower yellow", "vivid emerald green",
            "hot pink", "electric cobalt blue"]
STYLE = ("Glossy high-end music studio session in the style of a colors room: seamless backdrop, walls and floor painted in ONE "
         "solid, ultra-saturated, vivid {couleur} color (bold, rich, intense, never muted or matte), strong color blocking. "
         "Bright high-key beauty lighting, luminous and polished: glowing radiant skin, smooth sleek glossy fabrics and surfaces, "
         "crisp highlights, clean soft shadows, vibrant pop colors, ultra sharp, premium fashion advertising look, 8k.")
# Des personnes, oui, mais anonymes : jamais un visage reconnaissable, jamais une célébrité (décision du 19/10/2026)
INTERDIT = ("The person is anonymous: face NOT visible (seen from behind, silhouette, face hidden by a hat brim "
            "or shadow, or cropped below the eyes). No recognizable person, no celebrity, no text, no letters, no logos, no watermark")
SCENES = {
    "histoire": ["A man in a wide-brim hat seen from behind holding an old vinyl sleeve, a vintage record player on a stool.",
                 "A musician seen from behind playing a kora, sitting on a single wooden chair.",
                 "Hands holding a stack of old highlife vinyl records, cropped at the chest, matching monochrome outfit."],
    "monde": ["A singer with braids seen from behind facing a vintage microphone on a stand.",
              "A man in a bucket hat, head down so the face is hidden, headphones around the neck, arms crossed.",
              "A woman in a wax-print dress walking out of frame, face turned away, one hand raised."],
    "anecdote": ["Close-up of hands on a drum machine and a small synthesizer on a table, face out of frame.",
                 "A guitarist cropped below the eyes playing an electric guitar, contrasting outfit color.",
                 "A producer seen from behind at a laptop and mixing controller, big headphones."],
    "record": ["A dancer mid-movement in a contrasting color outfit, face hidden by a hat and motion.",
               "A silhouette holding a golden trophy high, face in shadow, confetti falling.",
               "A man in a tailored suit seen from behind standing next to a giant golden vinyl record."],
    "citation": ["A young woman seen from behind wearing headphones, sitting on a single stool.",
                 "A man in a fedora sitting, face in shadow, writing lyrics in a notebook."],
    "punchline": ["A rapper cropped below the eyes holding a microphone close, gold chain, strong side light.",
                  "A silhouette with a microphone, one arm raised, backlit, face unreadable."],
    "evenement": ["Two elegant silhouettes in evening wear seen from behind on a single spotlight circle.",
                  "A microphone stand alone under a spotlight, a guest in evening wear walking out of frame."],
}


def _ensure_table():
    db.run("""CREATE TABLE IF NOT EXISTS illustrations (
        id BIGSERIAL PRIMARY KEY, famille VARCHAR(24) NOT NULL, sujet_hash VARCHAR(64) NOT NULL,
        fichier VARCHAR(240) NOT NULL, cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        utilise_le TIMESTAMP NULL)""")


def _prompt(sujet: str, famille: str) -> str:
    """Une scène de la famille, choisie selon le sujet (jamais le nom de l'artiste dans le prompt)."""
    scenes = SCENES.get(famille) or SCENES["monde"]
    h = int(hashlib.sha256((sujet or famille).encode("utf-8")).hexdigest(), 16)
    scene = scenes[h % len(scenes)]
    couleur = COULEURS[(h // 7 + clock.today().toordinal()) % len(COULEURS)]   # une couleur différente d'un jour à l'autre
    return f"{scene} {STYLE.format(couleur=couleur)} {INTERDIT}."


def _path(fichier: str) -> Path:
    return storage.MEDIA / "illustrations" / Path(fichier).name


def _banque(famille: str):
    row = db.one("SELECT id, fichier FROM illustrations WHERE famille = ? ORDER BY utilise_le ASC NULLS FIRST, cree_le ASC LIMIT 1", [famille])
    if not row:
        return None
    db.run("UPDATE illustrations SET utilise_le = ? WHERE id = ?", [datetime.now(timezone.utc).replace(tzinfo=None), row["id"]])
    path = _path(row["fichier"])
    if not path.is_file() and storage.blob_public_url():
        # Sur GitHub Actions le disque repart vide : on recharge l'image de la banque depuis le Blob
        try:
            r = requests.get(f"{storage.blob_public_url()}/media/illustrations/{path.name}", timeout=30)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        except Exception:  # noqa: BLE001
            return None
    return str(path) if path.is_file() else None


def genere(sujet: str, famille: str, ratio: str = "4:5") -> str | None:
    """Renvoie le chemin local d'un PNG, avec plafond journalier et rotation de banque."""
    try:
        if famille not in FAMILLES:
            return None
        _ensure_table()
        plafond = max(0, int(env.get("ILLUSTRATIONS_PAR_JOUR", "5")))
        today = clock.today()
        count = int(db.value("SELECT COUNT(*) FROM illustrations WHERE cree_le::date = ?", [today.isoformat()]) or 0)
        if count >= plafond:
            return _banque(famille)
        key = env.get("GEMINI_API_KEY", "")
        if not key:
            return _banque(famille)
        model = env.get("ILLUSTRATION_MODELE", "gemini-2.5-flash-image")
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key}, timeout=90,
            json={"contents": [{"parts": [{"text": _prompt(sujet, famille)}]}],
                  "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ratio}}})
        response.raise_for_status()
        data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        img = next(p["inlineData"] for p in parts if p.get("inlineData", {}).get("data"))
        raw = base64.b64decode(img["data"], validate=True)
        with Image.open(BytesIO(raw)) as image:
            image.load()
            out = BytesIO()
            image = image.convert("RGB")
            image = ImageEnhance.Color(image).enhance(1.18)        # couleurs plus « grasses »
            image = ImageEnhance.Contrast(image).enhance(1.08)
            image = ImageEnhance.Brightness(image).enhance(1.05)    # personnes plus claires
            image = ImageEnhance.Sharpness(image).enhance(1.15)
            image.save(out, format="PNG", optimize=True)
        digest = hashlib.sha256((famille + "|" + (sujet or "")).encode("utf-8")).hexdigest()
        filename = f"{digest[:20]}-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}.png"
        storage.store_media("illustrations", filename, out.getvalue(), "image/png")
        local = _path(filename)  # store_media n'écrit pas sur disque quand le Blob est configuré ; le dessin du post en a besoin
        local.parent.mkdir(parents=True, exist_ok=True)
        if not local.is_file():
            local.write_bytes(out.getvalue())
        db.insert("illustrations", {"famille": famille, "sujet_hash": digest, "fichier": filename,
                                     "cree_le": datetime.now(timezone.utc).replace(tzinfo=None),
                                     "utilise_le": datetime.now(timezone.utc).replace(tzinfo=None)})
        return str(_path(filename))
    except Exception as exc:  # noqa: BLE001 — aucune illustration ne doit bloquer un post
        log_write("social", "warning", f"illustration IA indisponible ({type(exc).__name__})")
        return None


def mention(caption: str, langue: str = "fr") -> str:
    from core.services.social.bilingue import mention_illustration
    return mention_illustration(caption, langue)
