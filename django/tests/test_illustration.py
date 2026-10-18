import base64
from datetime import date
from io import BytesIO

from PIL import Image

from core.services.social import illustration as I


class FakeDB:
    def __init__(self, count=0, bank=None):
        self.count, self.bank, self.inserted, self.updated = count, bank, [], []

    def run(self, sql, params=None):
        if sql.startswith("UPDATE illustrations"):
            self.updated.append(params)
        return 1

    def value(self, sql, params=None):
        return self.count

    def one(self, sql, params=None):
        return self.bank

    def insert(self, table, data):
        self.inserted.append(data)
        return 1


def _png():
    out = BytesIO()
    Image.new("RGB", (16, 20), "white").save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


class Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"inlineData": {"data": _png(), "mimeType": "image/png"}}]}}]}


def test_prompt_impose_anonymat_et_n_envoie_pas_le_nom(monkeypatch):
    prompt = I._prompt("Burna Boy, concert afrobeats", "monde")
    assert "face NOT visible" in prompt and "No recognizable person, no celebrity, no text" in prompt
    assert "Burna" not in prompt and "Boy" not in prompt and "concert afrobeats" not in prompt


def test_plafond_quotidien_reutilise_la_banque(monkeypatch, tmp_path):
    bankfile = tmp_path / "bank.png"
    bankfile.write_bytes(b"png")
    monkeypatch.setattr(I, "db", FakeDB(count=5, bank={"id": 9, "fichier": "bank.png"}))
    monkeypatch.setattr(I.storage, "MEDIA", tmp_path)
    monkeypatch.setattr(I, "_ensure_table", lambda: None)
    monkeypatch.setattr(I, "_path", lambda f: tmp_path / f)
    assert I.genere("record", "record") == str(bankfile)
    assert I.db.updated


def test_generation_api_et_stockage(monkeypatch, tmp_path):
    fake = FakeDB()
    monkeypatch.setattr(I, "db", fake)
    monkeypatch.setattr(I, "_ensure_table", lambda: None)
    monkeypatch.setattr(I.clock, "today", lambda: date(2026, 10, 19))
    monkeypatch.setattr(I.env, "get", lambda k, d="": {"ILLUSTRATIONS_PAR_JOUR": "5", "GEMINI_API_KEY": "secret"}.get(k, d))
    monkeypatch.setattr(I.requests, "post", lambda *a, **kw: Response())
    monkeypatch.setattr(I.storage, "store_media", lambda folder, filename, data, content_type: (tmp_path / filename).write_bytes(data))
    monkeypatch.setattr(I.storage, "MEDIA", tmp_path)
    path = I.genere("citation musique", "citation")
    assert path and path.endswith(".png")
    assert fake.inserted[0]["famille"] == "citation"


def test_erreur_retourne_none_et_ne_journalise_pas_cle(monkeypatch):
    monkeypatch.setattr(I, "db", FakeDB())
    monkeypatch.setattr(I, "_ensure_table", lambda: None)
    monkeypatch.setattr(I.env, "get", lambda k, d="": "secret-key" if k == "GEMINI_API_KEY" else d)
    monkeypatch.setattr(I.requests, "post", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("failed")))
    logs = []
    monkeypatch.setattr(I, "log_write", lambda *a: logs.append(a))
    assert I.genere("musique", "monde") is None
    assert "secret-key" not in repr(logs)


def test_mention_fr_et_en():
    assert I.mention("Une légende") == "Une légende\n\nIllustration générée par IA"
    assert I.mention("Caption", "en") == "Caption\n\nAI-generated illustration"
