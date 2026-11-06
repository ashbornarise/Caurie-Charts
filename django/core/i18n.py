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


@lru_cache(maxsize=1)
def _phrases() -> dict:
    f = _DIR / "en_phrases.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def tr(texte, **params):
    """Texte écrit en français dans un gabarit, ou produit par le code (06/11/2026) : sa traduction anglaise sur la
    version /en (lang/en_phrases.json, clé = la phrase française ; « __motifs__ » : expressions régulières pour les
    textes avec chiffres). Variables : tr("Vous êtes :nom", nom=x). Renvoyé sans échappement : nos propres textes,
    les variables, elles, sont échappées."""
    import re as _re
    from markupsafe import Markup, escape
    texte = "" if texte is None else str(texte)
    if locale() == "en":
        trouve = _phrases().get(texte)
        if trouve is None:
            for motif, rempl in _phrases().get("__motifs__", []):
                nouveau = _re.sub(motif, rempl, texte)
                if nouveau != texte:
                    trouve = nouveau
                    break
        texte = trouve or texte
    for k, v in params.items():
        texte = texte.replace(":" + k, str(escape(v)))
    return Markup(texte)


def tr_filtre(valeur):
    """{{ x|tr }} : texte produit par le code ou venu des données (titre, résumé) : traduit puis échappé, jamais
    injecté tel quel dans la page."""
    from markupsafe import Markup, escape
    if isinstance(valeur, Markup):
        return tr(valeur)
    return escape(str(tr(valeur)))
