"""Budget de temps d'une étape de la chaîne de nuit : les boucles longues s'arrêtent proprement quand il est écoulé
et reprennent la nuit suivante (chaque module mémorise ce qu'il a déjà traité)."""
import time

_deadline: float | None = None


def start(seconds: float) -> None:
    global _deadline
    _deadline = time.time() + seconds


def stop() -> None:
    global _deadline
    _deadline = None


def over() -> bool:
    return _deadline is not None and time.time() > _deadline
