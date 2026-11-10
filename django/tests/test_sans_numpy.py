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
          "core.services.social.studio_montage", "core.services.social.couverture2026", "core.services.buffer",
          "core.services.social.studio_sequences", "core.services.social.studio_couvertures", "core.services.social.top_titres"):
    importlib.import_module(m)
# aperçus du Studio rendus par le site : début, fin, couvertures (10/11/2026 : « No module named 'numpy' » à la validation)
from PIL import Image
from core.services.social import studio_sequences as SQ, studio_couvertures as SC
from core.studio import _habillage_valide
assert _habillage_valide({"debut": "rideau~123", "fin": "iris", "son": "henri", "couverture": "pochette"})["couverture"] == "pochette"
fond = Image.new("RGB", (540, 960), (90, 60, 40))
ctx = {"etiquette": "Nouveau son", "accroche": "Un titre", "artiste": "Didi B", "titre": "PARTY", "pays": "ci", "photo": fond, "cover": fond}
for s, d in (("debut", SQ.DEBUTS), ("fin", SQ.FINS)):
    for n in d:
        SQ.image_cle(s, n, (270, 480), ctx, fond)
for m in SC.MODELES:
    SC.rendu(m, "story", photo=fond, cover=fond, titre="PARTY", artistes="Didi B", pays="ci", etiquette="Nouveau son")
print("ok")
"""


def test_modules_du_studio_sans_numpy():
    from pathlib import Path
    r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, timeout=120,
                       cwd=str(Path(__file__).resolve().parent.parent),   # dossier django : « cauri » importable (GitHub)
                       env={**__import__("os").environ, "DJANGO_SETTINGS_MODULE": "cauri.settings"})
    assert r.stdout.strip().endswith("ok"), r.stderr[-500:]
