"""TikTok réservé à l'Afrique (23/10/2026) : sujets africains, pas de vidéo reprise, 3 par jour, heures de pointe."""
import json
from datetime import datetime, timezone

from core.services import buffer


def _post(theme="matin", caption="N°1 au Bénin cette semaine", fiches=None):
    return {"id": 1, "theme": theme, "caption": caption, "facts": json.dumps({"fiches": fiches} if fiches is not None else {})}


def test_video_reprise_refusee(monkeypatch):
    monkeypatch.setattr(buffer.db, "value", lambda *a, **k: 0)
    assert "reprise" in buffer.tiktok_refus(_post("format-studio-9", "Source : @santrinos_raphael sur TikTok"))


def test_sujet_mondial_refuse_sujet_africain_garde(monkeypatch):
    monkeypatch.setattr(buffer.db, "value", lambda *a, **k: 0)
    assert "mondial" in buffer.tiktok_refus(_post("monde-soir-2", "Céline Dion", [{"artiste": "Céline Dion"}]))
    assert buffer.tiktok_refus(_post("monde-soir-2", "Burna Boy", [{"artiste": "Burna Boy"}])) is None
    assert buffer.tiktok_refus(_post()) is None


def test_trois_par_jour(monkeypatch):
    monkeypatch.setattr(buffer.db, "value", lambda *a, **k: 3)
    assert "3 posts" in buffer.tiktok_refus(_post())


def test_heures_de_pointe_africaines():
    nuit = datetime(2026, 10, 23, 4, 44, tzinfo=timezone.utc)
    assert buffer.heure_tiktok(nuit) == datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    apres_midi = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
    assert buffer.heure_tiktok(apres_midi).hour == 18
    tard = datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    assert buffer.heure_tiktok(tard) == datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    soir = datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc)
    assert buffer.heure_tiktok(soir) == soir


def test_hashtags_pays():
    assert "#Benin #229" in buffer.hashtags_pays("N°1 au Bénin cette semaine")
    assert buffer.hashtags_pays("#Togo déjà là, Togo").count("#Togo") == 1
