"""Imports : normalisation, sources, CSV, rapprochement YouTube (traduction de tests/ImportTest.php)."""
import copy

import pytest

from conftest import FakeHttp
from core import conf
from core.services.charts import ScoreCalculator
from core.services.imports import chart_importer
from core.services.imports import normalizer as N
from core.services.imports.matching import YouTubeMatcher
from core.services.imports.sources import AppleMusicChartSource, DeezerChartSource, ShazamChartSource, YouTubeTrendingSource


def formula():
    return copy.deepcopy(conf.get("formula"))


def test_normalisation_accents_casse_ponctuation():
    assert N.text("Mélo Décalé !") == "melo decale"
    assert N.text("cœur De Pirate") == "coeur de pirate"


def test_invites_ne_changent_pas_la_cle():
    a, b = N.track_key("Best (feat. Rema)", "Tiakola & Rema"), N.track_key("Best", "Tiakola")
    assert a == b == "tiakola|best"


def test_artiste_principal_et_invites():
    assert N.primary_artist("AMADEUS & Aida Samb") == "AMADEUS"
    assert N.featuring("AMADEUS & Aida Samb") == "Aida Samb"
    assert N.primary_artist("Kweku Smoke, Lasmid") == "Kweku Smoke"
    assert N.featuring("Tiakola") is None


def test_apple_music_flux_et_pochette_600():
    snap = AppleMusicChartSource.parse({"feed": {"updated": "2026-09-29T20:53:59Z", "results": [
        {"id": "111", "name": "Caméléon", "artistName": "Tiakola", "url": "https://music.apple.com/x",
         "artworkUrl100": "https://is1.mzstatic.com/a/100x100bb.jpg", "releaseDate": "2026-09-25"},
        {"id": "222", "name": "Dugi-dugi", "artistName": "AMADEUS & Aida Samb"}]}})
    assert snap["observed_on"] == "2026-09-29"
    assert len(snap["rows"]) == 2
    assert snap["rows"][1]["position"] == 2
    assert snap["rows"][0]["image"] == "https://is1.mzstatic.com/a/600x600bb.jpg"


def test_apple_music_pays_non_couvert():
    http = FakeHttp(lambda *a: {"status": 500, "body": ""})
    assert AppleMusicChartSource(http).fetch("TG") is None


def test_csv_avec_ou_sans_position():
    rows = chart_importer.parse_csv("1;GTA;Seyi Vibez\n2\tBaba\tHotkeed feat. Zlatan\n\nMigbo;Sethlo")
    assert len(rows) == 3
    assert rows[1]["artist"] == "Hotkeed feat. Zlatan"
    assert rows[2]["position"] == 3, "sans position : ordre des lignes"


def test_csv_ligne_illisible():
    with pytest.raises(ValueError):
        chart_importer.parse_csv("1;GTA;Seyi Vibez\nligne sans séparateur")


def test_youtube_clip_officiel_prefere():
    results = [{"external_id": "lyr", "title": "Tiakola - Caméléon (Lyrics)", "artist": "Lyrics Channel", "url": "", "published_at": None},
               {"external_id": "off", "title": "Tiakola - Caméléon (Clip officiel)", "artist": "Tiakola", "url": "", "published_at": None}]
    assert YouTubeMatcher.best(results, "Caméléon", "Tiakola")["external_id"] == "off"


def test_youtube_aucun_resultat_convaincant():
    results = [{"external_id": "x", "title": "Compilation afro 2026", "artist": "Mix TV", "url": "", "published_at": None}]
    assert YouTubeMatcher.best(results, "Caméléon", "Tiakola") is None


def test_positions_sans_poids_en_v11():
    r = ScoreCalculator(formula()).score({"deltas": {"youtube": 1000}, "chart_points": {"apple_music": 80}}, "BJ")
    assert r["score"] == 500.0
    assert r["sources_count"] == 1


def test_position_en_v12():
    f = formula()
    f["chart_weights"]["apple_music"] = 150
    r = ScoreCalculator(f).score({"deltas": {"youtube": 1000}, "chart_points": {"apple_music": 80}}, "BJ")
    assert r["score"] == 500.0 + 80 * 150
    assert r["sources_count"] == 2
    assert "chart:apple_music" in r["breakdown"]


def test_meme_plateforme_une_seule_source():
    f = formula()
    f["chart_weights"]["audiomack"] = 150
    assert ScoreCalculator(f).score({"deltas": {"audiomack": 2000}, "chart_points": {"audiomack": 10}}, "TG")["sources_count"] == 1


def test_position_recoupe_une_declaration():
    f = formula()
    f["chart_weights"]["apple_music"] = 150
    r = ScoreCalculator(f).score({"chart_points": {"apple_music": 10}, "declarations": [{"platform": "spotify", "streams": 900}]}, "CI")
    assert r["score"] == 1500.0 + 900


def test_shazam_csv():
    snap = ShazamChartSource.parse('﻿\n"Wednesday, 30 September 2026 [performance over the past 7 days]"\nRank,Artist,Title\n1,"AMADEUS","Namm nama la"\n2,"Wally B. Seck","Bayil"\n')
    assert len(snap["rows"]) == 2
    assert snap["rows"][0]["artist"] == "AMADEUS"
    assert snap["rows"][1]["position"] == 2


def test_deezer_playlist():
    snap = DeezerChartSource.parse({"data": [
        {"id": 99, "title": "Caméléon", "link": "https://www.deezer.com/track/99", "artist": {"name": "Tiakola"}, "album": {"cover_xl": "https://cdn/x.jpg"}},
        {"id": 100, "title": "", "artist": {"name": "Vide"}}]})
    assert len(snap["rows"]) == 1
    assert snap["rows"][0]["artist"] == "Tiakola"
    assert snap["rows"][0]["external_id"] == "99"


def test_youtube_tendances_split():
    assert YouTubeTrendingSource.split("Kweku Smoke - Bombele (Official Music Video)", "KwekuSmoke") == ("Kweku Smoke", "Bombele")
    assert YouTubeTrendingSource.split("Momo Dieng - RAAY (Clip Officiel)", "Prince Arts") == ("Momo Dieng", "RAAY")
    assert YouTubeTrendingSource.split("Naataango", "AMADEUS - Topic") == ("AMADEUS", "Naataango")


def test_youtube_tendances_identifiant_clip():
    snap = YouTubeTrendingSource.parse({"items": [{"id": "abc123", "snippet": {
        "title": "Kweku Smoke x Lasmid - Faith ( Official Video )", "channelTitle": "KwekuSmoke", "publishedAt": "2026-09-20T10:00:00Z"}}]})
    row = snap["rows"][0]
    assert (row["platform"], row["kind"], row["artist"], row["title"]) == ("youtube", "clip", "Kweku Smoke x Lasmid", "Faith")
