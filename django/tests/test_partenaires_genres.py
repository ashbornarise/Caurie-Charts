"""Classements ajoutés le 09/11/2026 (Top Artistes de la saison, genres) et dossier des partenaires média."""
import io
import zipfile

from core.services import genres
from core.services import partenaires as P


def ligne(rang, prec, titre="T", artiste="A", semaines=2):
    return {"rang": rang, "precedent": prec, "meilleur": rang, "semaines": semaines, "titre": titre, "artiste": artiste,
            "feat": "", "pays": "CI", "score": 100.0 - rang, "titres": None, "image": ""}


def test_genres_apple():
    assert genres.depuis_apple("Hip-Hop/Rap") == "rap"
    assert genres.depuis_apple("Afro-Pop") == "afrobeats"
    assert genres.depuis_apple("Christian & Gospel") == "gospel"
    assert genres.depuis_apple("R&B/Soul") == "rnb"
    assert genres.depuis_apple("Worldwide") is None       # Apple ne tranche pas : vérification Google
    assert genres.depuis_apple(None) is None


def test_titre_retrouve_chez_apple():
    chansons = {"plus de love": "Afro-Pop", "bara bara": "Hip-Hop/Rap", "*": "Afro-Pop"}
    assert genres._du_titre(chansons, "BARA BARA (feat. X)") == "Hip-Hop/Rap"
    assert genres._du_titre(chansons, "Inconnu") == "Afro-Pop"    # genre le plus fréquent de l'artiste


def test_faits_marquants():
    top = [ligne(1, 2, "PLUS DE LOVE", "Himra"), ligne(2, 3, "BARA BARA", "Himra"), ligne(3, None, "Vedette", "Azazou", 1),
           ligne(4, 9, "X", "Y")]
    f = P.faits([{"code": "prime", "nom": "Top", "artistes": False, "lignes": top}])
    assert f[0] == "Nouveau n°1 : « PLUS DE LOVE » de Himra, qui était 2e la semaine passée."
    assert "de la 9e à la 4e place (+5)" in f[1]          # le n°1 n'est pas compté comme progression
    assert f[2] == "Meilleure entrée : « Vedette » de Azazou, directement 3e."


def test_mouvements():
    assert P._mouvement(ligne(3, 5)) == "+2"
    assert P._mouvement(ligne(5, 3)) == "-2"
    assert P._mouvement(ligne(4, 4)) == "="
    assert P._mouvement(ligne(4, None, semaines=1)) == "NOUVEAU"
    assert P._mouvement(ligne(4, None, semaines=3)) == "RETOUR"


def test_excel_et_pdf():
    d = {"semaine": "2026-W44", "periode": ("2026-10-26", "2026-11-01"), "perimetres": [
        {"code": "CI", "nom": "Côte d'Ivoire", "faits": ["Fait"], "classements": [
            {"code": "prime", "nom": "Top des titres", "artistes": False, "lignes": [ligne(1, 2), ligne(2, None)]},
            {"code": "icon", "nom": "Top Artistes", "artistes": True,
             "lignes": [{**ligne(1, 1, None, "Himra"), "titres": 12}]}]}]}
    x = P.excel(d)
    assert zipfile.ZipFile(io.BytesIO(x)).namelist()        # un vrai .xlsx
    assert P.pdf(d, "Nec+Ultra Media")[:4] == b"%PDF"
    assert P._date_fr("2026-11-01") == "1er novembre 2026"


def test_jeton_refuse():
    assert P.par_jeton("../etc") is None
    assert P.par_jeton("court") is None
