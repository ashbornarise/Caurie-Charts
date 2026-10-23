"""Chaîne de nuit : les protections ajoutées après la nuit du 5 octobre 2026 (article Cauri Matin refusé,
post perdu sur une panne du Blob, publication bloquée par une étape annexe, file Buffer pleine)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from core import storage
from core.services import buffer, catchup, pipeline
from core.services.social import matin
from conftest import FakeHttp

SCHEMA = (Path(__file__).resolve().parent.parent / "sql" / "schema.pg.sql").read_text(encoding="utf-8")


def not_null_columns(table: str) -> set:
    """Colonnes NOT NULL sans valeur par défaut : celles qu'un INSERT doit toujours remplir."""
    body = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", SCHEMA, re.S).group(1)
    cols = set()
    for line in body.splitlines():
        m = re.match(r"\s+([a-z_]+)\s+[A-Z]", line)
        if m and "NOT NULL" in line and "DEFAULT" not in line and "IDENTITY" not in line:
            cols.add(m.group(1))
    return cols


def matin_post():
    facts = {"day": "2026-10-05", "number": 1, "one": {"title": "Gratitude", "artist_name": "Asake", "rank": 1}}
    caption = "Cauri Matin n°1, 05/10/2026. « Gratitude » d'Asake est n°1.\n\nClassement en direct : lien en bio."
    return {"id": 88, "theme": "matin", "title": "Cauri Matin n°1", "caption": caption, "facts": json.dumps(facts),
            "carousel": "[]", "video": None}


def test_article_cauri_matin_remplit_toutes_les_colonnes_obligatoires(monkeypatch):
    inserted = {}
    monkeypatch.setattr(matin.db, "value", lambda *a, **k: None)
    monkeypatch.setattr(matin.db, "insert", lambda table, data: inserted.update(table=table, data=data) or 1)
    assert matin.article(matin_post()) == "article publié dans Actualités"
    data = inserted["data"]
    missing = [c for c in not_null_columns("news") if data.get(c) in (None, "")]
    assert inserted["table"] == "news" and not missing, f"colonnes obligatoires vides : {missing}"
    assert len(data["summary"]) <= 400 and len(data["title"]) <= 200


def test_article_cauri_matin_une_seule_fois(monkeypatch):
    monkeypatch.setattr(matin.db, "value", lambda *a, **k: 1)
    monkeypatch.setattr(matin.db, "insert", lambda *a, **k: pytest.fail("article écrit deux fois"))
    assert matin.article(matin_post()) == "article déjà publié"


class FakeResponse:
    def __init__(self, status):
        self.status_code, self.reason, self.url = status, "x", "https://blob.vercel-storage.com/a.jpg"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return {"url": "https://blob/a.jpg"}


def test_blob_reessaie_une_panne_passagere(monkeypatch):
    answers = iter([FakeResponse(503), FakeResponse(503), FakeResponse(200)])
    waits = []
    monkeypatch.setattr(storage.requests, "put", lambda *a, **k: next(answers))
    monkeypatch.setattr(storage, "_sleep", waits.append)
    assert storage._blob_put("media/social/a.jpg", b"x", "image/jpeg") == "https://blob/a.jpg"
    assert waits == [2, 5]


def test_blob_abandonne_apres_trois_essais_et_ne_reessaie_pas_un_refus(monkeypatch):
    monkeypatch.setattr(storage, "_sleep", lambda s: None)
    monkeypatch.setattr(storage.requests, "put", lambda *a, **k: FakeResponse(503))
    with pytest.raises(requests.HTTPError):
        storage._blob_put("media/social/a.jpg", b"x", "image/jpeg")
    calls = []
    monkeypatch.setattr(storage.requests, "put", lambda *a, **k: calls.append(1) or FakeResponse(403))
    with pytest.raises(requests.HTTPError):
        storage._blob_put("media/social/a.jpg", b"x", "image/jpeg")
    assert len(calls) == 1  # un refus (jeton, droits) n'est pas une panne : pas de nouvel essai


def buffer_http(limit=10, used=0):
    """Faux Buffer : 3 comptes reliés, une file de `limit` places dont `used` prises ; chaque post créé est accepté."""
    created = []

    def responder(method, url, headers, body):
        q = json.loads(body)
        query = q["query"]
        if "limits" in query:
            data = {"account": {"organizations": [{"id": "o1", "limits": {"scheduledPosts": limit}}]}}
        elif "organizations { id }" in query:
            data = {"account": {"organizations": [{"id": "o1"}]}}
        elif "channels(" in query:
            data = {"channels": [{"id": s, "name": s, "service": s, "isDisconnected": False, "isLocked": False}
                                 for s in ("instagram", "facebook", "tiktok")]}
        elif "posts(" in query:
            data = {"posts": {"edges": [{"node": {"id": str(i)}} for i in range(used)]}}
        else:
            created.append(q["variables"]["input"])
            data = {"createPost": {"post": {"id": f"b{len(created)}", "dueAt": "2026-10-05T18:00:00.000Z"}}}
        return {"status": 200, "body": json.dumps({"data": data})}
    http = FakeHttp(responder)
    http.created = created
    return http


@pytest.fixture
def buffer_ready(monkeypatch):
    monkeypatch.setattr(buffer, "configured", lambda: True)
    monkeypatch.setattr(buffer.env, "get", lambda k, d=None: "cle" if k == "BUFFER_API_KEY" else d)
    monkeypatch.setattr(buffer.db, "value", lambda *a, **k: None)  # jamais programmé
    monkeypatch.setattr(buffer.audit, "log", lambda *a, **k: None)
    monkeypatch.setattr(buffer, "payload", lambda post, ch, when, reel=False: {"channelId": ch["id"], "reel": reel})


POST = {"id": 87, "theme": "format-officiel", "title": "Top Ghana", "caption": "…", "carousel": "[]", "video": "top.mp4"}
DUE = datetime(2026, 10, 5, 18, tzinfo=timezone.utc)


def test_buffer_programme_tout_quand_la_file_a_de_la_place(buffer_ready):
    http = buffer_http(limit=10, used=0)
    result = buffer.schedule(POST, DUE, http=http)
    assert len(http.created) == 5  # carrousel x 3 + vidéo Instagram et TikTok
    assert not buffer.failed(result)


def test_buffer_sacrifie_la_video_avant_le_carrousel(buffer_ready):
    http = buffer_http(limit=10, used=6)  # 4 places : le carrousel (3) passe, pas la vidéo (2)
    result = buffer.schedule(POST, DUE, http=http)
    assert len(http.created) == 3 and not any(c["reel"] for c in http.created)
    assert "vidéo non programmée" in result and buffer.failed(result)  # signalé dans le rapport


def test_buffer_ne_publie_jamais_un_carrousel_sur_un_seul_reseau(buffer_ready):
    http = buffer_http(limit=10, used=9)  # 1 place : rien plutôt qu'Instagram seul
    result = buffer.schedule(POST, DUE, http=http)
    assert http.created == [] and result.startswith("file Buffer pleine") and buffer.failed(result)


def test_instagram_reserve_aux_meilleurs_posts(buffer_ready):
    """Rubrique ordinaire : Facebook et TikTok seulement ; Instagram garde ses 4 places du jour pour les meilleurs posts."""
    http = buffer_http(limit=10, used=0)
    afrique = json.dumps({"fiches": [{"artiste": "Burna Boy"}]})   # TikTok : sujets africains seulement (23/10/2026)
    result = buffer.schedule({**POST, "theme": "monde-matin-3", "video": None, "facts": afrique}, DUE, http=http)
    assert sorted(c["channelId"] for c in http.created) == ["facebook", "tiktok"]
    assert "instagram : réservé aux meilleurs posts du jour" in result


def test_compte_rendu_buffer():
    assert not buffer.failed("tiktok programmé, facebook programmé, instagram déjà programmé")
    assert buffer.failed("tiktok programmé, facebook : Buffer : HTTP 500")
    assert buffer.failed("aucun compte relié à Buffer")


def test_etape_en_partie_faite_echoue_sans_perdre_son_compte_rendu():
    p = pipeline.DailyPipeline()

    def step():
        raise pipeline.StepFailed(["Cauri Matin n°1", "Buffer : tiktok programmé"], "Article : refusé")
    p._step("8 a. Cauri Matin", step)
    r = p.report[0]
    assert r["ok"] is False and "Buffer : tiktok programmé" in r["lines"] and r["lines"][-1] == "ERREUR : Article : refusé"


def test_publication_refusee_fait_echouer_l_etape(monkeypatch):
    monkeypatch.setattr(pipeline.buffer, "configured", lambda: True)
    monkeypatch.setattr(pipeline.buffer, "schedule", lambda post, due: "file Buffer pleine : 9/10 posts programmés")
    with pytest.raises(pipeline.StepFailed):
        pipeline.publish(POST, DUE)


def test_rattrapage_horaires(monkeypatch):
    monkeypatch.setattr(catchup.clock, "today", lambda: DUE.date())
    early = datetime(2026, 10, 5, 5, tzinfo=timezone.utc)
    assert catchup.due_for({"theme": "matin"}, early) == datetime(2026, 10, 5, 7, tzinfo=timezone.utc)
    assert catchup.due_for({"theme": "matin"}, datetime(2026, 10, 5, 9, tzinfo=timezone.utc)).hour == 9  # dès que possible
    assert catchup.due_for({"theme": "matin"}, datetime(2026, 10, 5, 12, tzinfo=timezone.utc)) is None  # trop tard
    assert catchup.due_for({"theme": "top_gh"}, early) == DUE
    assert catchup.due_for({"theme": "top_gh"}, datetime(2026, 10, 5, 17, 50, tzinfo=timezone.utc)) is None


def test_rattrapage_ne_touche_pas_aux_posts_faits_a_la_main():
    assert catchup._automatic("matin") and catchup._automatic("top_gh") and catchup._automatic("hebdo")
    assert not any(catchup._automatic(t) for t in ("presentation", "annonce", "demande-e2a75f", "distinction"))


def test_visuel_9_16_recompose_depuis_le_carre():
    import io
    from PIL import Image
    square = io.BytesIO()
    Image.new("RGB", (1080, 1350), (200, 30, 30)).save(square, "JPEG")
    story = Image.open(io.BytesIO(catchup.story_from_square(square.getvalue(), (1080, 1920))))
    assert story.size == (1080, 1920)
