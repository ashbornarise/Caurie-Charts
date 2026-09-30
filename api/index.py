"""Point d'entrée Vercel : l'application Django (WSGI) du dossier django/."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "django"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cauri.settings")
os.environ.setdefault("VERCEL", "1")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
