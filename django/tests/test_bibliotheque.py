"""Bibliothèque Cauri Charts (18/11/2026) : catégories des posts et titres des épisodes."""
from core import bibliotheque as B


def test_categories_des_themes():
    assert B.categorie("monde-soir-2") == "monde"
    assert B.categorie("flash-1621") == "flash"
    assert B.categorie("format-studio-416") == "studio"
    assert B.categorie("format-clip-1") == "studio"
    assert B.categorie("portrait") == "portraits"
    assert B.categorie("top_ci") == "classements"
    assert B.categorie("format-top10") == "classements"
    assert B.categorie("format-anecdote") == "magazine"
    assert B.categorie("annonce") == "autres"


def test_titre_episode_garde_les_noms():
    assert B._titre_episode({"haut": "COMMENT", "nom": "SHATTA WALE", "bas": "EST TOMBÉ"}) == "Comment Shatta Wale est tombé"


def test_legende_francaise_seule():
    assert B._legende("Bonjour 🐚\n\n🇬🇧 Hello\n#tag") == "Bonjour 🐚"


def test_date_fr():
    assert B.date_fr("2026-11-18") == "18 nov. 2026"


def test_resume():
    els = [{"cat": "monde", "type": "visuel", "date": "2026-11-01", "pays": "", "artiste": ""},
           {"cat": "raconte", "type": "video", "date": "2026-10-01", "pays": "GH", "artiste": "Shatta Wale"}]
    r = B.resume(els)
    assert (r["total"], r["videos"], r["visuels"], r["pays"], r["artistes"]) == (2, 1, 1, 1, 1)
    assert [c["code"] for c in r["categories"]] == ["raconte", "monde"]


def test_titre_des_actus():
    leg = ("🌍 Cauri Monde · X\n\n▪️ DAVIDO NOMMÉ ROI DE L'AFROBEATS PAR LE GOUVERNEUR D'OSUN\n"
           "Le gouverneur d'Osun, Adeleke, a déclaré Davido roi de l'Afrobeats.")
    assert B._titre_post("Cauri Monde · 18/11 · 21 h 30", leg) == "Davido nommé roi de l'Afrobeats par le gouverneur d'Osun"
    assert B._titre_post("Portrait : Himra", "x") == "Portrait : Himra"
    assert B._source("He eh eh\n\n🎥 Source : Himra sur Facebook") == "Himra"
