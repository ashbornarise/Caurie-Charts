"""Automatismes : classement des artistes, IA, SSRF, scène, posts (traduction de tests/AutomationTest.php)."""
from core.services import ai
from core.services.imports.channel_sync import YouTubeChannelSync
from core.services.imports.classifier import ArtistClassifier
from core.services.imports.matching import SceneSignals
from core.services.imports.sources import DeezerPopularitySource
from core.services.imports.watch import WikidataLookup
from core.services.news import http_get, is_public_host
from core.services.social.generator import PostGenerator

COVERED = ["TG", "BJ", "GH", "CI", "SN"]


def test_carriere_dans_un_pays_couvert():
    assert ArtistClassifier.decide({"nationality": "GH", "base_country": "GH", "confidence": 0.9}, COVERED, 0.85) == "active"


def test_artiste_etranger():
    assert ArtistClassifier.decide({"nationality": "CA", "base_country": "CA", "confidence": 0.9}, COVERED, 0.85) == "out_of_scope"


def test_diaspora_decision_humaine():
    assert ArtistClassifier.decide({"nationality": "SN", "base_country": "FR", "confidence": 0.95}, COVERED, 0.85) == "pending"


def test_confiance_insuffisante_ou_inconnu():
    assert ArtistClassifier.decide({"nationality": "CI", "base_country": "CI", "confidence": 0.6}, COVERED, 0.85) == "pending"
    assert ArtistClassifier.decide({"nationality": None, "base_country": None, "confidence": 0.9}, COVERED, 0.85) == "pending"
    assert ArtistClassifier.decide(None, COVERED, 0.85) == "pending"


def test_musicbrainz_et_wikidata_en_desaccord():
    mb = {"nationality": "GH", "base_country": "GH", "confidence": 0.9, "source": "musicbrainz", "note": "mb"}
    wd = {"nationality": "NG", "base_country": "NG", "confidence": 0.9, "source": "wikidata", "note": "wd"}
    assert ArtistClassifier.decide(ArtistClassifier.combine(mb, wd), COVERED, 0.85) == "pending"
    assert ArtistClassifier.combine(mb, mb)["confidence"] == 0.95
    assert ArtistClassifier.decide(ArtistClassifier.combine(None, wd), COVERED, 0.85) == "out_of_scope"


def test_ia_non_recoupee_plafonnee():
    v = {"nationality": "SN", "base_country": "SN", "confidence": 0.95, "source": "ia", "note": ""}
    assert ArtistClassifier.decide(ArtistClassifier.corroborate(v, None, ""), COVERED, 0.85) == "pending"
    assert ArtistClassifier.decide(ArtistClassifier.corroborate(v, "SN", ""), COVERED, 0.85) == "active"
    assert ArtistClassifier.decide(ArtistClassifier.corroborate(v, None, "chanteur sénégalais de mbalax"), COVERED, 0.85) == "active"
    assert ArtistClassifier.decide(ArtistClassifier.corroborate(v, "FR", ""), COVERED, 0.85) == "pending"


def test_ssrf_adresses_locales_ou_privees():
    for host in ("localhost", "127.0.0.1", "192.168.1.10", "169.254.169.254"):
        assert is_public_host(host) is False
    assert http_get("http://127.0.0.1:8000/") is None


def test_scene_marqueurs_locaux():
    assert SceneSignals.dominant(SceneSignals.score("Nouveau clip tourné à Lomé 228 ! Togo to the world, en éwé")) == "TG"
    assert SceneSignals.dominant(SceneSignals.score("Paris, New York, London")) is None


def test_chaine_youtube_rattachement():
    tracks = [{"id": 1, "title": "Bra"}, {"id": 2, "title": "Bra (Remix)"}, {"id": 3, "title": "Bombele"}]

    def m(t):
        return YouTubeChannelSync.match_track(t, tracks)
    assert m("Kweku Smoke - Bombele (Official Music Video)") == 3
    assert m("Kweku Smoke - Bra (Audio Visualizer)") == 1
    assert m("Kweku Smoke - Bombele (Teaser)") is None
    assert m("Kweku Smoke live at Afrochella") is None
    assert m("Brazil vlog") is None


def test_popularite_deezer():
    r = DeezerPopularitySource.rank([{"rank_score": 100, "title": "B", "artist": "X"}, {"rank_score": 900, "title": "A", "artist": "Y"}], 10)
    assert r["rows"][0]["title"] == "A"
    assert r["rows"][1]["position"] == 2
    assert "rank_score" not in r["rows"][0]


def test_wikidata_gentile():
    assert WikidataLookup.demonym("rappeur ivoirien") == "CI"
    assert WikidataLookup.demonym("Ghanaian rapper and songwriter") == "GH"
    assert WikidataLookup.demonym("village in Belarus") is None


def test_ia_extraction_json():
    j = ai.extract_json('Voici :\n```json\n{"base_country": "SN", "confidence": 0.92, "x": {"a": 1}}\n```')
    assert j["base_country"] == "SN"
    assert j["x"]["a"] == 1


def test_posts_texte_modele_factuel():
    facts = {"kind": "artist", "headline": "Artiste de la semaine", "source": "Classements Deezer",
             "artist": {"name": "Himra", "country": "CI", "deezer_fans": 52534, "profile": "/artiste/himra"},
             "tracks": [{"title": "PLUS DE LOVE", "seen": [{"platform": "Deezer", "country": "CI", "position": 4}]}]}
    post = PostGenerator.template(facts)
    assert post["title"] == "Himra"
    assert "Deezer CI n°4" in post["caption"]
    assert "52 534 fans" in post["caption"]
    assert "Source : Classements Deezer" in post["caption"]


def test_youtube_handles_and_channel_names():
    from core.services.imports.channel_sync import YouTubeChannelSync as S
    assert S.handles("Burna Boy") == ["burnaboy", "burnaboyofficiel", "burnaboyofficial"]
    assert S.handles("Aya Nakamura")[0] == "ayanakamura"
    assert S.same_name("Burna Boy - Topic", "Burna Boy")
    assert S.same_name("BurnaBoyVEVO", "Burna Boy")
    assert not S.same_name("Burna Boy Fans", "Burna Boy")
    assert not S.same_name("", "")


def test_mail_without_smtp_is_silent(monkeypatch):
    from core import mail
    monkeypatch.setattr(mail.env, "get", lambda key, default=None: default)
    assert mail.configured() is False
    assert mail.send("a@b.co", "s", "t") is False


def test_reliability_levels(monkeypatch):
    from datetime import date
    from core.services import reliability
    monkeypatch.setattr(reliability.db, "one", lambda *a, **k: {"sources": 4, "days": 7, "last": date.today().isoformat()})
    monkeypatch.setattr(reliability.clock, "today", lambda: date.today())
    rows = [{"seen": [{"source": "deezer"}, {"source": "shazam"}]}] * 20
    assert reliability.measure(1, rows)["score"] == 100
    assert reliability.measure(1, rows)["level"] == "élevée"
    monkeypatch.setattr(reliability.db, "one", lambda *a, **k: {"sources": 0, "days": 7, "last": date.today().isoformat()})
    assert reliability.measure(1, rows)["score"] == 30  # que des sources calculées : indicatif


def test_magazine_article_uses_only_given_facts():
    from collections import Counter
    from core.services import magazine
    row = lambda i, c="NG": {"title": f"Titre {i}", "artist_name": "Ayra Starr" if i == 1 else f"Artiste {i}", "artist_country": c,
                             "track_id": i, "seen": [{"source": "deezer"}, {"source": "deezer_popularity"}]}
    f = {"top": [row(i) for i in range(1, 21)], "buzz": [], "fresh": [row(1)], "leaders": [], "countries": Counter({"NG": 20})}
    art = magazine.write(f, "41")
    assert "d'Ayra Starr" in art["title"]
    assert "Popularité" not in art["body"]          # source calculée : jamais présentée comme une plateforme
    assert "nouveautés" not in art["body"]           # nouveauté déjà dans le Top 10 : pas répétée
    assert magazine.write({**f, "top": f["top"][:5]}, "41") is None


def test_humanize_caption():
    from core.services.social.generator import humanize
    assert humanize("Le n°1 — Rema​, véritable phénomène !") == "Le n°1, Rema, succès !"
    assert humanize("Ligne 1\nLigne 2 🔥") == "Ligne 1\nLigne 2 🔥"


def test_nightly_report_flags_failures(monkeypatch):
    from core.services import health
    monkeypatch.setattr(health.db, "value", lambda *a, **k: 0)
    title, text = health.summary([{"step": "1. Import", "ok": True, "seconds": 2, "lines": ["deezer NG : ERREUR HTTP 500"]},
                                  {"step": "8. Posts", "ok": False, "seconds": 1, "lines": ["ERREUR : IA"]}], crash=None)
    assert title == "2 problèmes cette nuit"          # une étape en échec + aucun relevé aujourd'hui
    assert "AUCUN RELEVÉ" in text and "[ÉCHEC] 8. Posts" in text and "deezer NG" in text
    monkeypatch.setattr(health.db, "value", lambda *a, **k: 500)
    assert health.summary([{"step": "1. Import", "ok": True, "seconds": 2, "lines": ["ok"]}])[0] == "nuit OK"


def test_best_photo_choice():
    from core.services.imports.photos import best, sized
    cands = [{"source": "deezer", "side": 1000}, {"source": "apple", "side": 2400}, {"source": "commons", "side": 3840}]
    assert best(cands)["source"] == "apple"            # photo officielle de studio d'abord
    assert best([{"source": "apple", "side": 400}, {"source": "deezer", "side": 1000}])["source"] == "deezer"
    assert best([{"source": "youtube", "side": 300}]) is None
    assert sized("https://is1-ssl.mzstatic.com/a/b/file.png/1200x630cw.png", 2400).endswith("/2400x2400bb.jpg")
