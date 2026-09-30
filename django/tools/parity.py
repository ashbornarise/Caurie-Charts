"""Compare le HTML du site PHP (référence, :8000) et du site Django (:8001), page par page.

Normalisation : espaces, entités HTML, jetons CSRF. Affiche les premières différences par page.
Usage : python tools/parity.py [chemin ...]
"""
import difflib
import html
import re
import sys

import requests

PHP, DJ = "http://localhost:8000", "http://127.0.0.1:8001"
PAGES = [
    "/", "/?pays=tg", "/?pays=gh&periode=mois", "/?periode=tout",
    "/classements/afrique-de-l-ouest", "/classements/afrique-de-l-ouest?classement=buzz",
    "/classements/afrique-de-l-ouest?classement=icon", "/classements/afrique-de-l-ouest?classement=legend",
    "/classements/afrique-de-l-ouest?classement=fresh", "/classements/afrique-de-l-ouest/mois?vue=direct",
    "/classements/tg/prime/semaine", "/classements/tg/prime/semaine?vue=deezer", "/classements/ci/prime/semaine?vue=direct&periode=tout",
    "/classements/bj/buzz/semaine", "/classements/sn/fresh/semaine", "/classements/gh/icon/semaine", "/classements/tg/legend/semaine",
    "/methodologie", "/a-propos", "/contact", "/contact?type=contestation", "/declarer",
    "/mentions-legales", "/confidentialite", "/cookies", "/conditions",
    "/actualites", "/actualites?page=2", "/partenaires", "/robots.txt", "/sitemap.xml",
    "/artiste/inconnu-xyz", "/classements/zz/prime",
]


def _sort_sources(m: re.Match) -> str:
    # Pastilles à égalité de position : MariaDB les rend dans un ordre arbitraire (requête sans ORDER BY)
    items = re.findall(r"<li class=\"source .*?</li>", m.group(2), flags=re.S)
    key = lambda li: (int((re.search(r"#(\d+)<", li) or [0, 0])[1]), li)  # noqa: E731
    rest = re.sub(r"<li class=\"source .*?</li>", "", m.group(2), flags=re.S)
    return m.group(1) + "".join(sorted(items, key=key)) + rest + "</ul>"


def norm(text: str) -> list[str]:
    text = re.sub(r'(<ul class="sources"[^>]*>)(.*?)</ul>', _sort_sources, text, flags=re.S)
    text = re.sub(r'name="(_csrf|csrfmiddlewaretoken)" value="[^"]*"', 'name="CSRF" value=""', text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r">\s*<", ">\n<", text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def compare(p: str, show: int = 12) -> bool:
    a = requests.get(PHP + p, timeout=60, allow_redirects=False)
    b = requests.get(DJ + p, timeout=60, allow_redirects=False)
    la, lb = norm(a.text), norm(b.text)
    ok = a.status_code == b.status_code and la == lb
    print(f"{'OK ' if ok else 'DIF'} {p}  [{a.status_code}/{b.status_code}]  {len(la)}/{len(lb)} lignes")
    if not ok:
        n = 0
        for line in difflib.unified_diff(la, lb, "php", "django", n=0, lineterm=""):
            if line.startswith(("---", "+++", "@@")):
                continue
            print("    " + line[:220])
            n += 1
            if n >= show:
                break
    return ok


if __name__ == "__main__":
    pages = sys.argv[1:] or PAGES
    results = [compare(p) for p in pages]
    print(f"\n{sum(results)}/{len(results)} pages identiques")
