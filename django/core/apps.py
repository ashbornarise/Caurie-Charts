from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _session_timezone(sender, connection, **kwargs):
    """CURRENT_DATE et NOW() au fuseau de l'application (Lomé), comme CURDATE() sur le site PHP."""
    from core import env
    with connection.cursor() as c:
        c.execute("SELECT set_config('TimeZone', %s, false)", [env.get("APP_TIMEZONE", "Africa/Lome") or "Africa/Lome"])


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        connection_created.connect(_session_timezone)
