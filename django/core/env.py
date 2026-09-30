"""Lecteur minimal de fichier .env (même format que le site PHP) ; les variables d'environnement priment."""
import os
from pathlib import Path

_values: dict[str, str] = {}


def load(path: Path) -> None:
    if not path or not Path(path).is_file():
        return
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        _values[key] = value


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, _values.get(key, default))


def bool(key: str, default: bool = False) -> bool:  # noqa: A001 (même nom que Env::bool en PHP)
    return get(key, "true" if default else "false").lower() in ("1", "true", "yes", "on")
