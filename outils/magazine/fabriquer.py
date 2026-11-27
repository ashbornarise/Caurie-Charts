"""Fabrique un numéro complet du Cauri Charts Magazine et le prépare pour le site (28/11/2026).

    python outils/magazine/fabriquer.py 2026-W48

1. données de la semaine (classements publiés) -> outils/magazine/donnees/s48.json
2. mise en page riche (fabrique.py -> gen2.py) -> outils/magazine/magazine.html
3. PDF A3 paysage -> public/documents/cauri-charts-magazine-n48.pdf
4. aperçus de chaque page (1600 px) -> public/documents/apercus/cauri-charts-magazine-n48/page-XX.jpg
5. fiche du numéro pour la page Documents -> django/core/data/magazines/cauri-charts-magazine-n48.json
"""
import io
import json
import os
import subprocess
import sys

from PIL import Image

ICI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ICI, "..", ".."))
PY = sys.executable
SEMAINE = sys.argv[1]
NUM = int(SEMAINE.split("W")[1])
FICHIER = f"cauri-charts-magazine-n{NUM}"
JSON = os.path.join(ICI, "donnees", f"s{NUM}.json")

subprocess.run([PY, os.path.join(ICI, "donnees.py"), SEMAINE], check=True)
subprocess.run([PY, os.path.join(ICI, "fabrique.py")], check=True)
subprocess.run([PY, os.path.join(ICI, "gen2.py"), JSON], check=True, cwd=ICI)
D = json.load(open(JSON, encoding="utf-8"))

pdf = os.path.join(REPO, "public", "documents", FICHIER + ".pdf")
apercus = os.path.join(REPO, "public", "documents", "apercus", FICHIER)
os.makedirs(apercus, exist_ok=True)
for f in os.listdir(apercus):
    os.remove(os.path.join(apercus, f))
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    b = p.chromium.launch(args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1588, "height": 1123}, device_scale_factor=1.4)
    pg.goto("file:///" + os.path.join(ICI, "magazine.html").replace("\\", "/"), wait_until="networkidle", timeout=180000)
    pg.wait_for_timeout(2000)
    casses = pg.evaluate("[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)")
    print("images cassées :", len(casses), casses[:5])
    pg.pdf(path=pdf, width="420mm", height="297mm", print_background=True, prefer_css_page_size=True)
    pages = pg.query_selector_all("section.page")
    for i, el in enumerate(pages):
        im = Image.open(io.BytesIO(el.screenshot())).convert("RGB")
        im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS).save(
            os.path.join(apercus, f"page-{i + 1:02d}.jpg"), quality=82, optimize=True, progressive=True)
    b.close()
nb = len(pages)
print("PDF :", pdf, round(os.path.getsize(pdf) / 1e6, 1), "Mo |", nb, "pages")

# ---- fiche pour le site (django/core/documents.py la lit) : textes indexables, légendes, chapitres
import re  # noqa: E402

def propre(t):
    t = re.sub(r"\s*[\(\[][^)\]]*(clip|officiel|official|video|vid[ée]o|lyrics?|audio|visuali[sz]er)[^)\]]*[\)\]]?\s*$", "", str(t or ""), flags=re.I)
    return re.sub(r"[\s\-–|·]+$", "", t).strip()

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
from datetime import date  # noqa: E402
d0, d1 = date.fromisoformat(D["debut"]), date.fromisoformat(D["fin"])
periode = (f"du {d0.day} au {d1.day} {MOIS[d1.month]} {d1.year}" if d0.month == d1.month
           else f"du {d0.day} {MOIS[d0.month]} au {d1.day} {MOIS[d1.month]} {d1.year}")
ORDRE = ["TG", "NG", "CI", "GH", "SN", "BJ", "BF", "ML", "GN", "SL", "CV", "GW", "MR"]
PAYS = sorted(D["pays"], key=lambda q: (ORDRE.index(q["code"]) if q["code"] in ORDRE else 99, q["nom"]))
n1 = D["wa"][0]
qui = lambda x: f"{propre(x['title'])} ({x['artist_name']})"
legendes = [f"Couverture : {qui(n1)}", "Les N°1 de la semaine", "Ouverture : Afrique de l'Ouest", "Top 20 Afrique de l'Ouest"]
chapitres = [["Couverture", f"{propre(n1['title'])} · {n1['artist_name']}", 1, 1, ""], ["Les N°1 de la semaine", "un titre par pays", 2, 2, ""],
             ["Top 20 Afrique de l'Ouest", "tous les pays ensemble", 3, 4, ""]]
for k, q in enumerate(PAYS):
    legendes += [f"Ouverture : {q['nom']}", f"Top {q['nom']}"]
    x = q["prime"][0]
    chapitres.append([f"Top {q['nom']}", f"{propre(x['title'])} · {x['artist_name']}", 5 + 2 * k, 6 + 2 * k, q["code"].lower()])
g0 = 5 + 2 * len(PAYS)
legendes += ["Ouverture : par genre", "Classements par genre", "Comment on calcule et prochain numéro"]
chapitres += [["Par genre", ", ".join(g["nom"].replace("Top ", "") for g in D["genres"][:3]) + "…", g0, g0 + 1, ""],
              ["Comment on calcule", "et le prochain numéro", g0 + 2, g0 + 2, ""]]
sections = [["Top 20 Afrique de l'Ouest (les 10 premiers)", ", ".join(f"{x['position']}. {qui(x)}" for x in D["wa"][:10])]]
sections += [[f"Top {q['nom']}", ", ".join(f"{x['position']}. {qui(x)}" for x in q["prime"][:5])] for q in PAYS]
sections.append(["Classements par genre", ", ".join(g["nom"] for g in D["genres"]) + ", sur toute l'Afrique de l'Ouest."])
fiche = {
    "slug": FICHIER, "categorie": "Magazines", "fichier": FICHIER, "date": str(date.fromordinal(d1.toordinal() + 1)),  # le vendredi de publication
    "pages": nb, "titre": f"Cauri Charts Magazine N°{NUM}", "sous_titre": f"Tous les classements officiels de la semaine {periode}",
    "description": (f"Le Cauri Charts Magazine N°{NUM} : le Top 20 Afrique de l'Ouest (N°1 : {qui(n1)}), les classements complets de "
                    f"{len(PAYS)} pays avec les N°1, les entrées et les mouvements, les {len(D['genres'])} classements par genre, et comment "
                    "nous calculons."),
    "format": f"PDF · A3 paysage · {nb} pages", "legendes": legendes, "sections": sections,
    "plus": {"taille": f"{round(os.path.getsize(pdf) / 1e6)} Mo", "coupe": ["Cauri Charts", f"Magazine N°{NUM}"],
             "badge": "Le magazine de la semaine", "accroche": ["N°1 Afrique de l'Ouest", f"{propre(n1['title'])} · {n1['artist_name']}"],
             "tuiles": [["trophee", "Top 20", "Afrique de l'Ouest"], ["globe", f"{len(PAYS)} pays", "classés cette semaine"],
                        ["note", f"{len(D['genres'])} genres", "du rap au coupé-décalé"], ["calc", "Indice 0-100", "comment on calcule"]],
             "chapitres": chapitres},
}
os.makedirs(os.path.join(REPO, "django", "core", "data", "magazines"), exist_ok=True)
json.dump(fiche, open(os.path.join(REPO, "django", "core", "data", "magazines", FICHIER + ".json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("fiche du site écrite :", FICHIER + ".json")
