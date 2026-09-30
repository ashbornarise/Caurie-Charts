"""Traductions (lang/fr.json, lang/en.json, exportées des fichiers PHP). Repli sur le français, puis sur la clé."""
import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "lang"
_locale: ContextVar[str] = ContextVar("locale", default="fr")


@lru_cache(maxsize=4)
def _lines(locale: str) -> dict:
    f = _DIR / f"{locale}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def set_locale(locale: str) -> None:
    _locale.set(locale)


def locale() -> str:
    return _locale.get()


def t(key: str, params: dict | None = None, **kwargs) -> str:
    text = _lines(locale()).get(key) or _lines("fr").get(key) or key
    for name, value in {**(params or {}), **kwargs}.items():
        text = text.replace(":" + name, str(value))
    return text
