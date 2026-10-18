"""Illustrations abstraites de secours pour les couvertures sans photo."""
import base64
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image
from io import BytesIO

from core import db, env, storage, clock
from core.services.platforms import log_write

FAMILLES = {"monde", "histoire", "anecdote", "record", "citation", "punchline", "evenement"}
STYLE = ("Premium 3D product photography, predominantly white background, sky-blue glass and violet glass or polymer, "
         "soft studio lighting, refined minimal composition. Create abstract objects and atmosphere only.")
INTERDIT = "No text, no letters, no logos, no people, no faces, no hands"
OBJETS = {
    "musique": "a translucent sound wave sculpture, tiny abstract music notes as shapes (not glyphs)",
    "album": "a blank white jewel case, translucent discs and floating geometric sound waves",
    "record": "a glossy translucent vinyl record, a small trophy shaped from blue glass",
    "histoire": "a blank archival sleeve, a translucent vinyl record and a violet glass timeline made of dots",
    "anecdote": "a curious glass magnifying lens above a small music object",
    "citation": "a blank glass speech bubble beside a translucent vinyl record",
    "evenement": "abstract stage lights represented as glass beams, with no stage or audience",
    "punchline": "a sculptural microphone made from sky-blue glass and violet polymer",
    "monde": "a glass globe, translucent music objects and soft blue-violet reflections",
    "recording": "a blank studio microphone, glass sound waves and a translucent disc",
}


def _ensure_table():
    db.run("""CREATE TABLE IF NOT EXISTS illustrations (
        id BIGSERIAL PRIMARY KEY, famille VARCHAR(24) NOT NULL, sujet_hash VARCHAR(64) NOT NULL,
        fichier VARCHAR(240) NOT NULL, cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        utilise_le TIMESTAMP NULL)""")


def _prompt(sujet: str, famille: str) -> str:
    tokens = re.findall(r"[a-zà-ÿ]+", (sujet or "").lower())
    concepts = [OBJETS[t] for t in tokens if t in OBJETS]
    concept = "; ".join(dict.fromkeys(concepts)) or OBJETS.get(famille, OBJETS["musique"])
    return f"{STYLE}\nOBJETS/AMBIANCE: {concept}.\n{INTERDIT}."


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
            image.convert("RGB").save(out, format="PNG", optimize=True)
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
