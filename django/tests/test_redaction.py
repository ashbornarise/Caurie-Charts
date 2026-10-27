"""Comité de rédaction (27/10/2026) : un agent actif bloque ou corrige, un agent à l'essai ne fait que donner son avis."""
import json

from core import db
from core.services import redaction


class FausseIA:
    def __init__(self, reponses):
        self.reponses = reponses

    def is_available(self):
        return True

    def ask(self, system, prompt, max_tokens=1500, web_searches=0):
        for nom, rep in self.reponses.items():
            if nom in system:
                return {"text": json.dumps(rep), "sources": []}
        return {"text": '{"verdict": "ok", "note": 9, "remarques": []}', "sources": []}


def _prepare(monkeypatch, reponses):
    redaction.tables()
    monkeypatch.setattr(redaction, "client", lambda: FausseIA(reponses))


def test_un_fait_invente_bloque_l_info(monkeypatch):
    _prepare(monkeypatch, {"Vérificateur des faits": {"verdict": "bloquer", "note": 2, "remarques": ["record absent des sources"]}})
    f = {"titre": "X bat un record", "resume": "Record historique.", "items": [{"title": "X sort un album", "source": "RFI"}]}
    assert redaction.fiche_monde(f) is None


def test_correction_appliquee(monkeypatch):
    _prepare(monkeypatch, {"Secrétaire de rédaction": {"verdict": "corriger", "note": 6, "remarques": ["faute"],
                                                       "texte_corrige": "TITRE : Davido annonce un album\nRÉSUMÉ : Davido annonce son album."}})
    f = redaction.fiche_monde({"titre": "Davido anonce un album", "resume": "Davido anonce son album.", "items": []})
    assert f["titre"] == "Davido annonce un album" and f["resume"] == "Davido annonce son album."


def test_agent_a_l_essai_ne_bloque_pas(monkeypatch):
    _prepare(monkeypatch, {"Testeur": {"verdict": "bloquer", "note": 1, "remarques": ["avis"]}})
    db.run("INSERT INTO redaction_agents (nom, role, consigne, mode, cree_par) VALUES ('testeur', 'Testeur', 'x', 'essai', 'directeur') "
           "ON CONFLICT (nom) DO NOTHING")
    r = redaction.relire("Un texte exact.", "sources", "essai")
    assert r["verdict"] == "ok" and any(a["agent"] == "testeur" and a["verdict"] == "bloquer" for a in r["avis"])


def test_lecons_dans_les_consignes(monkeypatch):
    redaction.tables()
    db.insert("redaction_lecons", {"sujet": "monde", "texte": "Les posts du soir font 2 fois plus de vues", "source": "analyste"})
    assert "2 fois plus de vues" in redaction.consignes("monde")
