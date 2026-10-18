"""Format « Le saviez-vous ? » et priorité à l'actu africaine (Cauri Monde)."""
from datetime import date

from core.services.social import formats as F
from core.services.social import monde as M

SOURCE = ("Ayodeji Ibrahim Balogun (born 16 July 1990), known professionally as Wizkid, is a Nigerian singer. "
          "Made in Lagos was released on 30 October 2020 and sold 1,200,000 units.")


def test_garde_fou_chiffres_anecdote():
    # chiffres et dates présents dans la source : accepté (séparateurs de milliers à la française ou à l'anglaise)
    assert F.chiffres_verifies("Né le 16 juillet 1990, Wizkid s'appelle en réalité Ayodeji Balogun.", SOURCE)
    assert F.chiffres_verifies("L'album s'est vendu à 1 200 000 exemplaires.", SOURCE)
    assert F.chiffres_verifies("Un fait sans aucun chiffre.", SOURCE)
    # un chiffre inventé (ou une date qui n'est pas dans le texte) : rejeté
    assert not F.chiffres_verifies("Né en 1991, il a sorti son album en 2020.", SOURCE)
    assert not F.chiffres_verifies("L'album s'est vendu à 2 000 000 exemplaires.", SOURCE)


def test_preuve_doit_venir_du_texte():
    assert F.preuve_trouvee("Made in Lagos was released on 30 October 2020", SOURCE)
    assert not F.preuve_trouvee("He won three Grammy awards for Essence in Atlanta", SOURCE)


def test_pas_d_emoji_sur_les_images():
    assert F._sans_emoji("Vous le saviez ⁉️") == "Vous le saviez ?"


def test_au_moins_une_info_africaine(monkeypatch):
    monkeypatch.setattr(M, "nos_artistes", lambda: set())
    tries = [{"artiste": n} for n in ["Taylor Swift", "Drake", "Adele", "Coldplay", "Burna Boy"]]
    choix = M.au_moins_un_africain(tries, 4)
    assert [f["artiste"] for f in choix] == ["Taylor Swift", "Drake", "Adele", "Burna Boy"]
    # déjà une info africaine, ou aucune disponible : rien ne change
    assert M.au_moins_un_africain(tries[:4], 4) == tries[:4]


PAROLES = "Omo, I don't wanna lie\nI need some money for my pocket\nI no fit stay for one place\n\nCalm down, calm down"


def test_punchline_mot_pour_mot():
    assert F.ligne_dans_paroles("I need some money for my pocket", PAROLES) == "I need some money for my pocket"
    # 2 vers consécutifs, apostrophe typographique tolérée
    assert F.ligne_dans_paroles("Omo, I don’t wanna lie / I need some money for my pocket", PAROLES)
    # ligne réécrite, vers non consécutifs, ou plus de 2 vers : refusé
    assert F.ligne_dans_paroles("I need money in my pocket", PAROLES) is None
    assert F.ligne_dans_paroles("Omo, I don't wanna lie / I no fit stay for one place", PAROLES) is None
    assert F.ligne_dans_paroles("Omo, I don't wanna lie / I need some money for my pocket / I no fit stay for one place", PAROLES) is None


def test_stars_sans_doublon():
    assert len(M.CHERCHES) == len(set(M.CHERCHES))
    assert {"Diamond Platnumz", "Koffi Olomide", "Werenoi"} <= set(M.STARS)


def test_anecdote_chaque_jour_a_midi(monkeypatch):
    vus = []
    for nom in ("power", "promo", "top10", "citation", "versus", "histoire", "qui_est", "anecdote", "punchline", "bandeaux", "record"):
        fn = (lambda n: (lambda jour, due: vus.append((n, due.hour)) or None))(nom)
        fn.__name__ = nom
        monkeypatch.setattr(F, nom, fn)
    F.du_jour(date(2026, 10, 20))            # un mardi ordinaire
    assert ("anecdote", 12) in vus and ("citation", 21) in vus and not any(n == "punchline" for n, _ in vus)
    vus.clear()
    F.du_jour(date(2026, 10, 19))            # un lundi : punchline à 18 h
    assert ("punchline", 18) in vus and ("top10", 21) in vus
    vus.clear()
    F.du_jour(date(2026, 10, 1))             # le 1er du mois : power à midi, l'anecdote passe à 13 h
    assert ("power", 12) in vus and ("anecdote", 13) in vus
    vus.clear()
    F.du_jour(date(2026, 10, 24))            # samedi : bandeaux à midi, pas d'anecdote
    assert ("bandeaux", 12) in vus and not any(n == "anecdote" for n, _ in vus)
    vus.clear()
    F.du_jour(date(2026, 10, 22))            # jeudi : record à 18 h
    assert ("record", 18) in vus


def test_pourtoi_bandeaux_et_record_dimensions():
    from PIL import Image
    from core.services.social import pourtoi as P
    personnes = [{"photo": Image.new("RGB", (100, 100), (i * 30, 50, 80)), "nom": f"Artiste {i}", "chiffre": str(1000 + i)} for i in range(4)]
    assert P.bandeaux(personnes, "LES PLUS SUIVIS").size == P.FORMATS["feed"]
    assert P.record(Image.new("RGB", (100, 100)), "RECORD OFFICIEL", "4").size == P.FORMATS["feed"]
