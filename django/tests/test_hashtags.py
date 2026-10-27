"""Hashtags contextuels (27/10/2026) et choix des réseaux du Studio."""
import json

from core.services import buffer
from core.services.social import hashtags as H


def test_hashtags_du_sujet_cinq_en_minuscules():
    t = H.choisir("Burna Boy fait une entrée remarquée au Ballon d'Or", "La cérémonie du Ballon d'Or", "Burna Boy",
                  "TAPIS ROUGE", ia=False).split()
    assert t[:3] == ["#cauricharts", "#burnaboy", "#ballondor"]
    assert len(t) == 5 and all(x == x.lower() for x in t)


def test_showbiz_n_est_pas_un_concert():
    t = H.choisir("Je suis un point fort du showbiz togolais", "Moment d'interview", "", "INTERVIEW", ia=False)
    assert "#interview" in t and "#togo" in t and "#concert" not in t


def test_aucun_reseau_choisi_ne_veut_pas_dire_tous():
    assert buffer.reseaux({"facts": json.dumps({"reseaux": []})}) == set()
    assert buffer.reseaux({"facts": json.dumps({"reseaux": None})}) is None


def test_preparer_ne_touche_pas_aux_posts_ecrits_a_la_main():
    post = {"title": "Top 20", "caption": "x", "hashtags": "#CauriHebdo", "facts": json.dumps({"kind": "top"})}
    assert H.preparer(post)["hashtags"] == "#CauriHebdo"
