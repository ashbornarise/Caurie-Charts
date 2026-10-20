"""Le site (Vercel) n'a pas numpy : les modules utilisés par les pages du studio doivent se charger sans lui
(« No module named 'numpy' » à l'enregistrement des photos, 20/10/2026)."""
import subprocess
import sys

CODE = """
import sys, importlib
class Bloque:
    def find_spec(self, nom, *a, **k):
        if nom == "numpy" or nom.startswith("numpy."):
            raise ImportError("numpy absent sur Vercel")
sys.meta_path.insert(0, Bloque())
import django; django.setup()
for m in ("core.studio", "core.services.social.plans", "core.services.social.studio_photos",
          "core.services.social.studio_montage", "core.services.social.couverture2026", "core.services.buffer"):
    importlib.import_module(m)
print("ok")
"""


def test_modules_du_studio_sans_numpy():
    r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, timeout=120,
                       env={**__import__("os").environ, "DJANGO_SETTINGS_MODULE": "cauri.settings"})
    assert r.stdout.strip().endswith("ok"), r.stderr[-500:]
