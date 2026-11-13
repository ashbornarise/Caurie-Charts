"""« Cauri raconte » dans le Studio (13/11/2026) : la voix dit les nombres en entier et les noms en phonétique, les
sous-titres gardent l'orthographe, « Billboard » n'est jamais dit, le récit relu est nettoyé."""
from core.services.social import studio_raconte as R


def test_chiffres_dits_en_entier():
    assert R._chiffres_dits("4,66 MD d'écoutes, 5,4 M par jour, 12 k vues") == "4,66 milliards d'écoutes, 5,4 millions par jour, 12 mille vues"
    assert R._chiffres_dits("MOMENT 2026") == "MOMENT 2026"   # pas de faux positif


def test_phonetique_pour_la_voix_orthographe_a_l_ecran():
    assert R._phonetique("Asake à Lagos avec Burna Boy") == "Achaké à Légosse avec Beurna Boï"
    assert R._ecrit_juste("Sur Spotifaï, Achaké") == "Sur Spotify, Asake"


def test_jamais_billboard_ni_markdown():
    assert R._propre("**66e** au Billboard 200 et au Billboard") == "66e au classement américain des albums et au classement américain"


def test_sous_titres_cales_sur_la_voix():
    dits = [{"m": "Comment", "d": 0.1, "f": 0.4}, {"m": "Achaké", "d": 0.45, "f": 0.9}]
    assert [m["m"] for m in R._sous_titres("Comment Asake", dits, 2.0, 1.0)] == ["Comment", "Asake"]
    assert R._sous_titres("Comment Asake", dits, 2.0, 1.0)[1]["d"] == 2.45
    # comptes différents : réparti au prorata, dans l'ordre, sans dépasser la phrase
    l = R._sous_titres("Comment Asake est passé", dits, 0, 1.0)
    assert [m["m"] for m in l] == ["Comment", "Asake", "est", "passé"] and l[-1]["f"] <= 0.9 and l[0]["d"] == 0.1


def test_recit_relu_nettoye():
    r = R.recit_valide({"titre": {"haut": "COMMENT", "nom": "ASAKE", "bas": "?"}, "phrases": [
        {"texte": "Une Asake", "voix": "", "carte": {"grand": "", "petit": "x"}},
        {"texte": "  ", "voix": "rien"},
        {"texte": "Deux", "voix": "Deux", "carte": {"grand": "4,66 MD", "petit": "écoutes", "or": 1}},
        {"texte": "Trois"}]})
    assert [p["texte"] for p in r["phrases"]] == ["Une Asake", "Deux", "Trois"]
    assert r["phrases"][0]["voix"] == "Une Achaké" and r["phrases"][0]["carte"] is None
    assert r["phrases"][1]["carte"] == {"grand": "4,66 MD", "petit": "écoutes", "or": True}
    assert R.recit_valide({"phrases": [{"texte": "seule"}]}) is None
