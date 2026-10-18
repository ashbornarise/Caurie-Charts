"""Moments d'interview : le passage choisi par l'IA est contrôlé (bornes réelles, durée, aucun chiffre inventé)."""
from core.services.social import interviews as I

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.210 align:start position:0%

I<00:00:00.500><c> sold</c><00:00:00.900><c> out</c><00:00:01.300><c> the</c><00:00:01.600><c> stadium</c>

00:00:02.210 --> 00:00:02.220 align:start position:0%
I sold out the stadium


00:00:02.220 --> 00:00:04.000 align:start position:0%
I sold out the stadium
in<00:00:02.600><c> two</c><00:00:03.000><c> days</c>
"""


def _phrases():
    # 10 lignes de 5 s : 0, 5, 10… 45 s ; la ligne 4 contient un vrai chiffre
    out = []
    for k in range(10):
        texte = "we sold 80,000 tickets in Lagos" if k == 4 else f"ligne {chr(97 + k)} de la transcription"
        out.append({"debut": 5.0 * k, "fin": 5.0 * k + 5.0, "texte": texte})
    return out


def test_mots_horodates_sans_doublons():
    mots = I.mots_vtt(VTT)
    assert [w for _, w in mots] == ["I", "sold", "out", "the", "stadium", "in", "two", "days"]
    assert mots[1] == (0.5, "sold") and mots[-1] == (3.0, "days")


def test_passage_valable_recale_sur_la_transcription():
    c = I.verifie({"debut": 10.3, "fin": 44.8, "accroche": "Il a vendu 80 000 billets à Lagos", "resume": "r"}, _phrases())
    assert c and c["debut"] == 10.0 and c["fin"] == 45.0
    assert "80,000" in c["texte"]


def test_fin_donnee_comme_debut_de_la_ligne_suivante():
    c = I.verifie({"debut": 5, "fin": 40, "accroche": "Un concert complet à Lagos, raconté par lui"}, _phrases())
    assert c and c["fin"] == 40.0


def test_bornes_absentes_de_la_transcription_refusees():
    assert I.verifie({"debut": 12.5, "fin": 45, "accroche": "Une phrase de six mots ici"}, _phrases()) is None
    assert I.verifie({"debut": 10, "fin": 120, "accroche": "Une phrase de six mots ici"}, _phrases()) is None


def test_duree_hors_limites_refusee():
    assert I.verifie({"debut": 10, "fin": 30, "accroche": "Une phrase de six mots ici"}, _phrases()) is None   # 20 s
    assert I.verifie({"debut": 0, "fin": 50, "accroche": "Une phrase de six mots ici"}, _phrases()) is not None


def test_passage_trop_court_prolonge_puis_verifie():
    o = I.etend({"debut": 10, "fin": 15, "accroche": "Il a vendu 80 000 billets à Lagos"}, _phrases())
    assert o["fin"] == 40.0
    assert I.verifie(o, _phrases())["fin"] == 40.0
    assert I.etend({"debut": 10, "fin": 45}, _phrases())["fin"] == 45   # déjà assez long : inchangé


def test_chiffre_invente_refuse():
    base = {"debut": 10, "fin": 45, "resume": "r"}
    assert I.verifie({**base, "accroche": "Il a vendu 90 000 billets à Lagos"}, _phrases()) is None
    assert I.verifie({**base, "accroche": "Il a rempli le stade en 2 jours"}, _phrases()) is None
    assert I.verifie({**base, "accroche": "Trop court"}, _phrases()) is None
    assert I.verifie({**base, "accroche": "Il a vendu tous les billets à Lagos", "parle": False}, _phrases()) is None


def test_titres_filtres():
    assert I.titre_valable("Burna Boy: The 'I Told Them...' Interview | Apple Music", "Burna Boy")
    assert not I.titre_valable("Burna Boy - Last Last (Official Music Video)", "Burna Boy")
    assert not I.titre_valable("Burna Boy Live Performance at Glastonbury", "Burna Boy")
    assert not I.titre_valable("Davido talks about Burna Boy", "Burna Boy")
    assert not I.titre_valable("Burnaboy fans react", "Burna Boy")
    assert not I.titre_valable("Rema - Calm Down (Lyrics)", "Rema")
