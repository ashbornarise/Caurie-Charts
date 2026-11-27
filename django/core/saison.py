"""Logos de saison (27/11/2026, demande du fondateur : « on change partout ») : le monogramme coiffé d'un bonnet de
Noël s'affiche du 27 novembre au 6 janvier inclus, puis le logo officiel revient tout seul le 7 janvier.

Chaque logo de saison est un fichier à part, à côté de l'officiel, avec « -noel » avant l'extension
(favicon-32.png -> favicon-32-noel.png) : rien n'est remplacé, l'officiel reste intact.
"""
from datetime import date
from pathlib import Path


def noel(jour: date | None = None) -> bool:
    d = jour or date.today()
    return (d.month == 11 and d.day >= 27) or d.month == 12 or (d.month == 1 and d.day <= 6)


def nom(fichier: str, jour: date | None = None) -> str:
    """« favicon-32.png » -> « favicon-32-noel.png » pendant la saison, sinon le nom officiel."""
    if not noel(jour):
        return fichier
    p = Path(fichier)
    return str(p.with_name(p.stem + "-noel" + p.suffix)).replace("\\", "/")


def monogramme_blanc(marque: Path, jour: date | None = None):
    """Le monogramme blanc carré (fond transparent) des disques et icônes : le C officiel découpé dans logo-blanc.png
    (le C fait toute la hauteur du logo, d'où le carré pris à gauche) ; pendant la saison, le C coiffé du bonnet."""
    from PIL import Image
    noel_png = marque / "monogramme-blanc-noel.png"
    if noel(jour) and noel_png.is_file():
        return Image.open(noel_png).convert("RGBA")
    lg = Image.open(marque / "logo-blanc.png").convert("RGBA")
    lg = lg.crop(lg.getbbox())
    return lg.crop((0, 0, lg.height, lg.height))


def chemin(dossier: Path, fichier: str, jour: date | None = None) -> Path:
    """Le fichier de saison s'il existe dans le dossier, sinon l'officiel (jamais d'image manquante)."""
    saison = dossier / nom(fichier, jour)
    return saison if saison.is_file() else dossier / fichier
