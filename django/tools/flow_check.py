"""Parcours avec session : langue anglaise et formulaire de contact (erreurs puis envoi), PHP vs Django."""
import re
import sys

import requests

sys.path.insert(0, "tools")
from parity import norm  # noqa: E402

SITES = {"php": "http://localhost:8000", "django": "http://127.0.0.1:8001"}


def token(html: str):
    m = re.search(r'name="(_csrf|csrfmiddlewaretoken)" value="([^"]+)"', html)
    return m.group(1), m.group(2)


out = {}
for name, base in SITES.items():
    s = requests.Session()
    s.get(base + "/langue/en?retour=/methodologie", allow_redirects=False)
    en = s.get(base + "/classements/tg/prime/semaine").text
    form = s.get(base + "/contact").text
    field, tok = token(form)
    bad = s.post(base + "/contact", data={field: tok, "name": "Test", "email": "pas-un-mail", "subject": "", "message": "court"}, allow_redirects=False)
    out[name] = {"en": norm(en), "bad": (bad.status_code, norm(bad.text))}

print("anglais identique :", out["php"]["en"] == out["django"]["en"])
pb, db_ = out["php"]["bad"], out["django"]["bad"]
print("erreurs contact :", pb[0], db_[0], "identiques" if pb[1] == db_[1] else "DIFFÉRENTES")
import difflib  # noqa: E402
for k, (a, b) in {"en": (out["php"]["en"], out["django"]["en"]), "bad": (pb[1], db_[1])}.items():
    for line in list(difflib.unified_diff(a, b, n=0, lineterm=""))[2:14]:
        print("   ", k, line[:200])
