import time

from core import live


def test_jeu_trop_long_revele_en_mode_auto():
    vieux = int(time.time() * 1000) - 120_000
    e = {"pilote": True, "jeu": {"type": "mot", "phase": "jeu", "t": vieux}}
    live._jeu_trop_long(e)
    assert e["jeu"]["phase"] == "fin"


def test_jeu_recent_ou_sans_mode_auto_reste_ouvert():
    e = {"pilote": True, "jeu": {"type": "mot", "phase": "jeu", "t": int(time.time() * 1000)}}
    live._jeu_trop_long(e)
    assert e["jeu"]["phase"] == "jeu"
    e = {"pilote": False, "naissanceOn": False, "jeu": {"type": "mot", "phase": "jeu", "t": 1}}
    live._jeu_trop_long(e)
    assert e["jeu"]["phase"] == "jeu"
