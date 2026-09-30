"""Date et heure de l'application (fuseau APP_TIMEZONE, Lomé par défaut), quel que soit le fuseau de la machine."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from core import env


def now() -> datetime:
    return datetime.now(ZoneInfo(env.get("APP_TIMEZONE", "Africa/Lome") or "Africa/Lome")).replace(tzinfo=None)


def today() -> date:
    return now().date()
