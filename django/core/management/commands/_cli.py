"""Outils communs aux commandes (équivalent de bin/cli.php) : options --cle=valeur, journal cron."""
import sys
import time

from core.services.platforms import log_write


def run(name: str, task) -> None:
    """Exécute une tâche en journalisant toute erreur dans storage/logs/cron-AAAA-MM.log."""
    started = time.time()
    try:
        task()
        log_write("cron", "info", f"{name} terminé", {"secondes": round(time.time() - started, 2)})
    except Exception as exc:  # noqa: BLE001
        log_write("cron", "error", str(exc))
        sys.stderr.write(f"ERREUR ({name}) : {exc}\n")
        raise SystemExit(1)


def out(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()
