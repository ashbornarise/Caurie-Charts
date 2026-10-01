"""Clients YouTube et Spotify (traduction de tests/PlatformsTest.php)."""
import json

import pytest

from conftest import FakeHttp, youtube_responder
from core.services.platforms import MemoryQuotaStore, PlatformException, QuotaExceededException, SpotifyClient, YouTubeClient


def today():
    return "2026-09-28"


def test_youtube_statistiques():
    yt = YouTubeClient("cle", FakeHttp(youtube_responder), MemoryQuotaStore(), 10000, today)
    assert yt.fetch_track_stats("abc") == {"plays": 1000, "likes": 40, "comments": 3, "popularity": None}


def test_youtube_paquets_de_50():
    http, quota = FakeHttp(youtube_responder), MemoryQuotaStore()
    stats = YouTubeClient("cle", http, quota, 10000, today).fetch_many([f"v{i}" for i in range(1, 121)])
    assert len(stats) == 120
    assert len(http.calls) == 3, "120 vidéos = 3 appels"
    assert quota.used("youtube", "2026-09-28") == 3
    assert "part=statistics" in http.calls[0]["url"]


def test_youtube_quota_epuise_resultats_partiels():
    quota = MemoryQuotaStore()
    quota.add("youtube", "2026-09-28", 9998)
    with pytest.raises(QuotaExceededException) as exc:
        YouTubeClient("cle", FakeHttp(youtube_responder), quota, 10000, today).fetch_many([f"v{i}" for i in range(1, 201)])
    assert len(exc.value.partial) == 100, "2 appels possibles avant épuisement"


def test_youtube_recherche_exige_100_unites():
    quota = MemoryQuotaStore()
    quota.add("youtube", "2026-09-28", 9950)
    with pytest.raises(QuotaExceededException):
        YouTubeClient("cle", FakeHttp(youtube_responder), quota, 10000, today).search_track("test")


def test_youtube_sans_cle_pas_d_appel():
    http = FakeHttp(youtube_responder)
    yt = YouTubeClient("", http, MemoryQuotaStore(), 10000, today)
    assert yt.is_available() is False
    with pytest.raises(PlatformException):
        yt.fetch_track_stats("x")
    assert len(http.calls) == 0


def test_youtube_quota_refuse_par_google():
    http = FakeHttp(lambda *a: {"status": 403, "body": json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}})})
    with pytest.raises(QuotaExceededException):
        YouTubeClient("cle", http, MemoryQuotaStore(), 10000, today).fetch_track_stats("x")


def test_spotify_metadonnees_seulement():
    def responder(method, url, headers, body):
        if "accounts.spotify.com" in url:
            return {"status": 200, "body": json.dumps({"access_token": "tok", "expires_in": 3600})}
        return {"status": 200, "body": json.dumps({"name": "Titre", "popularity": 42, "album": {"images": [{"url": "https://i.scdn.co/x.jpg"}]}})}
    http = FakeHttp(responder)
    s = SpotifyClient("id", "secret", http).fetch_track_stats("abc")
    assert s["plays"] == 0
    assert s["popularity"] == 42
    assert http.calls[1]["headers"]["Authorization"] == "Bearer tok"


def test_ia_groq_prend_le_relais_quand_gemini_est_a_court_de_quota():
    from core.services.ai import FallbackClient, GeminiClient, GroqClient

    def responder(method, url, headers, body):
        if "googleapis" in url:
            return {"status": 429, "body": json.dumps({"error": {"message": "quota"}})}
        return {"status": 200, "body": json.dumps({"choices": [{"message": {"content": "<think>…</think>{\"ok\": 1}"}}]})}

    http = FakeHttp(responder)
    client = FallbackClient([GeminiClient(http, "g"), GroqClient(http, "q", "openai/gpt-oss-120b")])
    assert client.ask("système", "question")["text"] == '{"ok": 1}'
    groq = [c for c in http.calls if "groq" in c["url"]][0]
    assert groq["headers"]["Authorization"] == "Bearer q"
    assert json.loads(groq["body"])["model"] == "openai/gpt-oss-120b"


def test_ia_sans_cle_groq_reste_sur_gemini_seul():
    from core.services.ai import FallbackClient, GeminiClient, GroqClient
    http = FakeHttp(lambda *a: {"status": 200, "body": "{}"})
    assert len(FallbackClient([GeminiClient(http, "g"), GroqClient(http, "")]).clients) == 1


def test_telegram_message_du_classement_cite_sa_source_et_echappe_le_html():
    from core.services.telegram import chart_message
    data = {"code": "wa", "name": "Afrique de l’Ouest", "official": False, "since": "2026-09-24", "until": "2026-09-30",
            "rows": [{"rank": 1, "title": "Bra <3", "artist": "Kweku Smoke", "track_slug": "kweku-smoke-bra"}]}
    text = chart_message(data)
    assert "Tendances de la semaine" in text and "Classement officiel" not in text
    assert "Bra &lt;3" in text and "titre/kweku-smoke-bra" in text
    assert "Apple Music, Deezer, Shazam et YouTube" in text


def test_telegram_appel_api_avec_le_jeton(monkeypatch):
    from core.services import telegram
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    http = FakeHttp(lambda *a: {"status": 200, "body": json.dumps({"ok": True, "result": {"username": "cauri_bot"}})})
    assert telegram.call("getMe", {}, http)["username"] == "cauri_bot"
    assert http.calls[0]["url"] == "https://api.telegram.org/bot123:abc/getMe"
