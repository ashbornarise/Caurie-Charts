"""Relevés de contrôle du 21/11/2026 : Top Spotify Nigeria quotidien (kworb), TurnTable, accord de rang de Spearman."""
import json

from core.services.controle_externe import spearman
from core.services.imports.sources import SpotifyPaysChartSource, TurnTableChartSource


def test_spotify_pays_lecture_kworb():
    ligne = ('<tr><td class="np">{p}</td>\n<td class="np">=</td>\n<td class="text mp"><div><a href="../artist/5ywjxFhmhHGQBsK3DundNf.html">'
             'Peruzzi</a> - <a href="../track/3FCIOA44iYIDsjDNeXthc1.html">INFERNO</a> (w/ <a href="../artist/4mSWNal2Ixxf1zrXSTLoep.html">'
             'Zlatan</a>, <a href="../artist/23R4AtMwVv0pbJYB1joioW.html">Shoday</a>)</div></td><td>1</td></tr>')
    page = "<h1>Daily Chart - Nigeria - 2026/11/19 | </h1>" + "".join(ligne.format(p=p) for p in range(1, 61))
    s = SpotifyPaysChartSource.parse(page)
    assert s["observed_on"] == "2026-11-19" and len(s["rows"]) == 60
    assert s["rows"][0] == {"position": 1, "artist": "Peruzzi, Zlatan, Shoday", "title": "INFERNO",
                            "external_id": "3FCIOA44iYIDsjDNeXthc1", "url": "https://open.spotify.com/track/3FCIOA44iYIDsjDNeXthc1"}
    assert SpotifyPaysChartSource(None).fetch("CI") is None   # pas de classement Spotify hors du Nigeria


def test_turntable_lecture():
    data = {"props": {"chart": [{"rank": k, "title": "INFERNO" if k == 1 else f"T{k}", "artiste": "Peruzzi, Zlatan & Shoday"}
                                for k in range(1, 61)]}}
    page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    s = TurnTableChartSource.parse(page)
    assert len(s["rows"]) == 60 and s["rows"][0] == {"position": 1, "title": "INFERNO", "artist": "Peruzzi, Zlatan & Shoday"}


def test_spearman():
    assert spearman({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}) == 1.0
    assert round(spearman({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}), 6) == -1.0
    assert spearman({1: 1}, {2: 1}) is None
    r = spearman({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, {1: 1, 2: 2, 3: 3, 9: 4, 8: 5})   # 2 titres de chaque côté absents de l'autre
    assert 0 < r < 1


def test_turntable_date_de_sa_semaine():
    data = {"props": {"pageProps": {"chartData": {"dateCreated": "2026-11-12T00:00:00",
                                                  "chartItems": [{"rank": k, "title": f"T{k}", "artiste": "A"} for k in range(1, 61)]}}}}
    page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    assert TurnTableChartSource.parse(page)["observed_on"] == "2026-11-12"
