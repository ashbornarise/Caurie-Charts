"""« Médias » du Studio (27/11/2026) : règles pures, sans base ni réseau."""
from core.services.social import studio_medias as M


def test_genre_selon_extension():
    assert M.genre_de("JPG") == "photo"
    assert M.genre_de(".mp4") == "video"
    assert M.genre_de("m4a") == "son"
    assert M.genre_de("exe") == "fichier"


def test_extension_nettoyee_et_refusee_si_inconnue():
    assert M.ext_propre("MoV") == "mov"
    assert M.ext_propre("j.p/g") == "jpg"
    assert M.ext_propre("exe") == "bin"
    assert M.ext_propre(None) == "bin"


def test_cle_de_dossier():
    assert M.dossier_cle("creations") == ("creations", None)
    assert M.dossier_cle("d12") == ("dossier", 12)
    assert M.dossier_cle("a34") == ("artiste", 34)
    assert M.dossier_cle("x1") == ("", None)
    assert M.dossier_cle("d1; DROP TABLE") == ("", None)


def test_lien_de_telechargement_direct():
    assert M.telecharger("https://b.example/x.mp4") == "https://b.example/x.mp4?download=1"
    assert M.telecharger("https://b.example/x.mp4?v=2") == "https://b.example/x.mp4?v=2&download=1"
    assert M.telecharger("") == ""


def test_credit_du_compte():
    assert M._credit({"uploader_id": "@sethloofficiel", "extractor_key": "Youtube"}) == "@sethloofficiel (Youtube)"
    assert M._credit({"extractor_key": "TikTok"}) == "TikTok"
