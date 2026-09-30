"""Normalisation des noms pour rapprocher un titre vu sur plusieurs plateformes (traduction d'Import\\Normalizer).

« Mélo Décalé (feat. X) » de « Tiakola & Rema » et « melo decale » de « Tiakola » donnent la même clé.
Les expressions sans drapeau /u en PHP travaillent octet par octet : re.ASCII reproduit leurs \\b.
"""
import re

_MAP = {
    "à": "a", "â": "a", "ä": "a", "á": "a", "ã": "a", "ç": "c", "é": "e", "è": "e", "ê": "e", "ë": "e",
    "î": "i", "ï": "i", "í": "i", "ô": "o", "ö": "o", "ó": "o", "õ": "o", "ù": "u", "û": "u", "ü": "u", "ú": "u",
    "ñ": "n", "ɔ": "o", "ɛ": "e", "œ": "oe", "æ": "ae", "’": "'", "&": " and ",
}
_MAP_RE = re.compile("|".join(map(re.escape, sorted(_MAP, key=len, reverse=True))))
_SPLIT = re.compile(r"\s*(?:,|&|\bx\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b|\bwith\b|\bet\b)\s*", re.I | re.A)


def text(s: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples."""
    s = str(s).strip().lower()
    s = _MAP_RE.sub(lambda m: _MAP[m.group(0)], s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title(t: str) -> str:
    """Titre sans mention d'invité ni version entre parenthèses non distinctive."""
    t = re.sub(r"[\(\[]\s*(feat|ft|featuring|with|prod)\b[^\)\]]*[\)\]]", "", str(t), flags=re.I | re.A)
    t = re.sub(r"\s[-–]\s*(feat|ft)\b.*$", "", t, flags=re.I | re.A)
    t = re.sub(r"\b(feat|ft|featuring)\.?\s.*$", "", t, flags=re.I | re.A)
    t = re.sub(r"[\(\[]\s*(official|clip|video|audio|lyrics?|visualizer)[^\)\]]*[\)\]]", "", t, flags=re.I | re.A)
    return text(t)


def primary_artist(artist: str) -> str:
    """Artiste principal : premier nom avant « & », « , », « x », « feat »."""
    parts = _SPLIT.split(str(artist).strip(), maxsplit=1)
    return parts[0].strip() if parts else str(artist)


def featuring(artist: str) -> str | None:
    parts = _SPLIT.split(str(artist).strip(), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 and parts[1].strip() else None


def artist_key(artist: str) -> str:
    return text(primary_artist(artist))


def track_key(t: str, artist: str) -> str:
    return artist_key(artist) + "|" + title(t)
