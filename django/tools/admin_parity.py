"""Compare l'admin PHP (:8002) et Django (:8003) sur les copies de base, connecté avec le compte de test."""
import difflib
import re
import sys

import requests

sys.path.insert(0, "tools")
from parity import norm  # noqa: E402

SITES = {"php": "http://localhost:8002", "django": "http://127.0.0.1:8003"}
PAGES = ["/admin", "/admin/classements", "/admin/declarations", "/admin/declarations?statut=validated", "/admin/import",
         "/admin/releves", "/admin/catalogue", "/admin/catalogue?q=toofan", "/admin/artistes/1", "/admin/artistes/nouveau",
         "/admin/titres/5", "/admin/titres/nouveau", "/admin/actualites", "/admin/actualites/1", "/admin/actualites/nouveau",
         "/admin/posts", "/admin/partenaires", "/admin/partenaires/nouveau", "/admin/formule", "/admin/journal", "/admin/messages"]


def login(base):
    s = requests.Session()
    html = s.get(base + "/admin/connexion").text
    field, tok = re.search(r'name="(_csrf|csrfmiddlewaretoken)" value="([^"]+)"', html).groups()
    r = s.post(base + "/admin/connexion", data={field: tok, "email": "parite@test.local", "password": "Test-Parite-2026!"}, allow_redirects=False)
    assert r.status_code in (302, 303), (base, r.status_code, r.text[:300])
    return s


def clean(lines):
    # Horodatages et jetons variables d'une exécution à l'autre
    return [re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "DATE", l) for l in lines]


if __name__ == "__main__":
    sessions = {k: login(v) for k, v in SITES.items()}
    ok = 0
    pages = sys.argv[1:] or PAGES
    for p in pages:
        a = sessions["php"].get(SITES["php"] + p, allow_redirects=False)
        b = sessions["django"].get(SITES["django"] + p, allow_redirects=False)
        la, lb = clean(norm(a.text)), clean(norm(b.text))
        same = a.status_code == b.status_code and la == lb
        ok += same
        print(f"{'OK ' if same else 'DIF'} {p} [{a.status_code}/{b.status_code}] {len(la)}/{len(lb)}")
        if not same:
            for line in list(difflib.unified_diff(la, lb, n=0, lineterm=""))[2:14]:
                if not line.startswith("@@"):
                    print("    " + line[:200])
    print(f"\n{ok}/{len(pages)} pages identiques")
