"""Newsletter (06/11/2026) : double confirmation, désinscription, adresses refusées."""
import uuid

from core import db
from core.services import newsletter as N


def test_inscription_confirmation_desinscription(monkeypatch):
    envoyes = []
    monkeypatch.setattr(N.mail, "send", lambda to, sujet, texte, **k: envoyes.append((to, texte)) or True)
    email = f"test-{uuid.uuid4().hex[:8]}@exemple.org"
    try:
        assert N.inscrire(email, "en") == "ok"
        assert envoyes and "/en/newsletter/confirmer/" in envoyes[0][1]   # lien dans la langue de l'abonné
        jeton = db.value("SELECT jeton FROM newsletter WHERE email = ?", [email])
        assert db.value("SELECT statut FROM newsletter WHERE email = ?", [email]) == "attente"
        assert N.confirmer(jeton) and db.value("SELECT statut FROM newsletter WHERE email = ?", [email]) == "actif"
        assert N.inscrire(email) == "deja"
        N.desinscrire(jeton)
        assert db.value("SELECT statut FROM newsletter WHERE email = ?", [email]) == "desinscrit"
    finally:
        db.run("DELETE FROM newsletter WHERE email = ?", [email])


def test_adresse_invalide():
    assert N.inscrire("pas-une-adresse") == "invalide"
    assert N.confirmer("jeton-inconnu") is None
