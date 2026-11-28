"""Formule v7 (audit des tops S47 par les IA, 21/11/2026) : Spotify du pays (top quotidien) au lieu des compteurs mondiaux,
source trop maigre ignorée, titres signalés hors du classement, date de sortie cherchée pour les titres sans date."""
from core.services import chart_service as CS
from core.services import dates_sortie
from core.services.charts import Period
from core.services.imports.sources import SpotifyPaysChartSource, TurnTableChartSource

F7 = {"normalisation": {"youtube": 0.5, "streaming": 0.5, "min_titres_source": 5}}


def _item(tid, yt=0, sp=0, boom=0):
    b = {}
    if yt:
        b["youtube"] = {"delta": yt}
    if sp:
        b["chart:spotify"] = {"delta": sp}
    if boom:
        b["chart:boomplay"] = {"delta": boom}
    return {"track_id": tid, "score": yt * 0.5, "prev_score": 0, "breakdown": b}


def _calcule(items, monkeypatch, f=F7):
    monkeypatch.setattr(CS.db, "all", lambda *a, **k: [])
    monkeypatch.setattr(CS.db, "run", lambda *a, **k: None)
    CS.ChartService.__new__(CS.ChartService)._normalise(items, f, 4, Period.week_of("2026-11-20"))
    return {i["track_id"]: i for i in items}


def test_source_maigre_ignoree(monkeypatch):
    # Togo S47 : 3 titres seulement avec des écoutes -> la source ne compte pas, YouTube et Boomplay décident
    items = [_item(1, yt=8571, sp=3088, boom=47), _item(2, yt=252294, boom=93)] + \
            [_item(10 + k, yt=1000 * k, boom=10) for k in range(1, 6)]
    r = _calcule(items, monkeypatch)
    assert "spotify" not in r[1]["breakdown"]["_v4"]["poids"]
    assert r[2]["score"] > r[1]["score"]


def test_source_assez_large_compte(monkeypatch):
    items = [_item(k, yt=1000, sp=100 - k) for k in range(1, 7)]
    r = _calcule(items, monkeypatch)
    assert set(r[1]["breakdown"]["_v4"]["poids"]) == {"youtube", "spotify"}


def test_signales_hors_du_classement():
    items = [{"track_id": 1, "review_status": "pending", "score": 9}, {"track_id": 2, "review_status": "ok", "score": 5},
             {"track_id": 3, "review_status": "validated", "score": 4}]
    garde = CS.ChartService._v7_avant_classement(items, {"exclure_signales": True}, 10)
    assert [i["track_id"] for i in garde] == [2, 3]
    assert len(CS.ChartService._v7_avant_classement(items, {}, 10)) == 3   # semaines d'avant la v7 : inchangées


def test_date_itunes_meme_artiste_et_plus_ancienne():
    class Http:
        def request(self, *a, **k):
            import json
            return {"status": 200, "body": json.dumps({"results": [
                {"artistName": "Rema & Selena Gomez", "trackName": "Calm Down", "releaseDate": "2022-08-25T07:00:00Z"},
                {"artistName": "Rema", "trackName": "Calm Down", "releaseDate": "2022-02-11T08:00:00Z"},
                {"artistName": "KIDZ BOP Kids", "trackName": "Calm Down", "releaseDate": "2021-01-01T08:00:00Z"},
                {"artistName": "Rema", "trackName": "Calm Down (Sped Up)", "releaseDate": "2020-01-01T08:00:00Z"}]})}
    assert dates_sortie.date_itunes("Calm Down", "Rema", Http()) == "2022-02-11"


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
    import json
    data = {"props": {"chart": [{"rank": k, "title": "INFERNO" if k == 1 else f"T{k}", "artiste": "Peruzzi, Zlatan & Shoday"}
                                for k in range(1, 61)]}}
    page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    s = TurnTableChartSource.parse(page)
    assert len(s["rows"]) == 60 and s["rows"][0] == {"position": 1, "title": "INFERNO", "artist": "Peruzzi, Zlatan & Shoday"}


def test_score_affiche_jamais_au_dessus_du_titre_precedent():
    from core.services.charts import ChartRanker
    e = [{"score": 727.42, "details": {}}, {"score": 541.7, "details": {}}, {"score": 2131.18, "details": {"x": 1}}, {"score": 273.5, "details": {}}]
    r = ChartRanker.scores_ordonnes(e)
    assert [x["score"] for x in r] == [727.42, 541.7, 541.7, 273.5]
    assert r[2]["details"] == {"x": 1, "score_avant_plafond": 2131.18}


def test_youtube_30_pourcent_au_nigeria(monkeypatch):
    monkeypatch.setattr(CS.db, "value", lambda *a, **k: "NG")
    f = {"normalisation": {"youtube": 0.5, "streaming": 0.5, "youtube_pays": {"NG": 0.3}}}
    items = [_item(1, yt=3540089, sp=10), _item(2, yt=468302, sp=190)]
    r = _calcule(items, monkeypatch, f)
    assert r[1]["breakdown"]["_v4"]["poids"] == {"youtube": 0.3, "spotify": 0.7}
    assert r[2]["score"] > r[1]["score"]   # le N°1 du Spotify du pays passe devant le champion des vues mondiales


# ---------------------------------------------------------------- formule v7 complète (core/services/formule_v7.py)
import math as _m

from core.services import formule_v7 as F7


def test_zipf_parts_somment_a_un():
    z = F7.Zipf(0.5, 2.25)
    assert abs(sum(z.part(r, 100) for r in range(1, 101)) - 1) < 1e-9
    assert z.part(1, 100) > z.part(2, 100) > z.part(100, 100)


def test_absence_censuree_jamais_zero():
    z = F7.Zipf(0.5, 2.25)
    obs = [(1, "apple_music", "2026-11-13", 1), (1, "apple_music", "2026-11-14", 1), (9, "apple_music", "2026-11-13", 2),
           (9, "apple_music", "2026-11-14", 100)]
    x, infos = F7.parts_classements(obs, {1, 2}, z)
    cens = z.part(101, 101)
    assert x[2]["apple_music"] == cens                      # titre suivi jamais classé : valeur censurée, pas zéro
    assert x[1]["apple_music"] == z.part(1, 100)            # présent les 2 jours relevés
    assert infos["apple_music"] == {"N": 100, "jours": 2, "n": 1}   # le titre étranger (9) compte dans N, pas dans n


def test_jour_absent_compte_censure():
    z = F7.Zipf(0.5, 2.25)
    obs = [(1, "deezer", "2026-11-13", 5), (7, "deezer", "2026-11-14", 100)]
    x, _ = F7.parts_classements(obs, {1}, z)
    assert abs(x[1]["deezer"] - (z.part(5, 100) + z.part(101, 101)) / 2) < 1e-15


def test_youtube_compresse_et_sans_clip_absent():
    y = F7.parts_youtube({1: 3_540_089, 2: 468_302, 3: 0, 4: 900}, {1, 2, 3}, 0.5)
    assert 4 not in y                                       # pas de clip officiel : YouTube absent du titre
    assert abs(y[1] / y[2] - _m.sqrt(3_540_089 / 468_302)) < 1e-9   # 2,7 fois et non 7,6 fois
    assert 0 < y[3] < y[2]                                  # clip sans vue : plancher, jamais ln 0


def test_moyenne_geometrique_present_partout_bat_fort_sur_une_seule():
    infos = {"apple_music": {"N": 100, "jours": 7, "n": 50}, "boomplay": {"N": 100, "jours": 1, "n": 50}}
    z = F7.Zipf(0.5, 2.25)
    c = z.part(101, 101)
    x = {1: {"apple_music": z.part(1, 100), "boomplay": c},            # N°1 Apple, absent de Boomplay
         2: {"apple_music": z.part(8, 100), "boomplay": z.part(8, 100)}}   # 8e partout
    d, pays = F7.scores([1, 2], x, infos, {}, set(), {"kappa": 5, "pi_max": 0.5, "lambda": 0.8})
    assert d[2]["score"] > d[1]["score"]
    assert abs(d[1]["score"] + d[2]["score"] - 10000) < 1e-6
    assert pays["fiabilite"] == round((50 / 55 * 2) / (1 + 50 / 55 * 2), 4)


def test_poids_youtube_baisse_avec_les_sources_d_ecoute():
    p = {"kappa": 5, "pi_max": 0.5, "lambda": 0.8}
    riche = {s: {"N": 100, "jours": 7, "n": 500} for s in ("apple_music", "boomplay", "shazam", "deezer", "spotify")}
    pauvre = {"boomplay": {"N": 100, "jours": 1, "n": 64}}
    x = {1: {s: 0.01 for s in riche}}
    _, a = F7.scores([1], x, riche, {1: 0.5}, set(), p)
    _, b = F7.scores([1], {1: {"boomplay": 0.01}}, pauvre, {1: 0.5}, set(), p)
    assert round(a["pi_yt"], 2) == 0.10 and round(b["pi_yt"], 2) == 0.29


def test_loi_beta_et_chi2():
    assert abs(F7.beta_cdf(0.5, 2, 2) - 0.5) < 1e-9
    assert abs(F7.beta_cdf(0.3, 1, 1) - 0.3) < 1e-9
    assert abs(F7.beta_cdf(0.2, 2, 5) - 0.34464) < 1e-4      # valeur de référence I_0.2(2,5)
    assert abs(F7.chi2_4_queue(9.4877) - 0.05) < 1e-4        # quantile 95 % du χ² à 4 degrés


def test_fraude_pic_et_engagement():
    import random
    random.seed(1)
    vues = {t: 100_000 for t in range(60)}
    likes = {t: int(100_000 * random.uniform(0.03, 0.05)) for t in range(60)}
    histo = {t: [100_000 * random.uniform(0.9, 1.1) for _ in range(8)] for t in range(60)}
    vues[99], likes[99], histo[99] = 5_000_000, 2_000, [100_000 * random.uniform(0.9, 1.1) for _ in range(8)]   # pic ×50, presque aucun j'aime
    s = F7.fraude(vues, likes, histo)
    assert list(s) == [99]


def test_fraude_pas_de_faux_suspects():
    import random
    random.seed(2)
    vues = {t: 100_000 for t in range(60)}
    likes = {t: int(100_000 * random.uniform(0.003, 0.05)) for t in range(60)}
    histo = {t: [100_000 * random.uniform(0.97, 1.03) for _ in range(8)] for t in range(60)}
    vues[1], likes[1] = 200_000, 6_000                    # un tube qui double (Oh No de Rema, S47) : pas une fraude
    histo[2] = [2_000_000, 7_000, 9_000, 11_000, 13_000, 5_000]   # clip remplacé par le bon clip officiel la semaine d'avant
    vues[2], likes[2] = 3_200_000, 64_000   # j'aime à 2 %, dans la norme
    assert F7.fraude(vues, likes, histo) == {}


def test_fraude_nouveau_clip_officiel():
    """DJOROBITE (Himra), S48 : nouveau clip le 21/11, 33 000 -> 2,6 millions de vues avec des j'aime normaux. Pic levé ;
    un nouveau clip SANS j'aime reste suspect (le test des j'aime / vues tient toujours)."""
    import random
    random.seed(3)
    vues = {t: 100_000 for t in range(60)}
    likes = {t: int(100_000 * random.uniform(0.03, 0.05)) for t in range(60)}
    histo = {t: [100_000 * random.uniform(0.9, 1.1) for _ in range(8)] for t in range(60)}
    vues[7], likes[7], histo[7] = 2_600_000, 100_000, [33_000, 30_000, 31_000, 29_000, 28_000]
    assert 7 in F7.fraude(vues, likes, histo)
    assert 7 not in F7.fraude(vues, likes, histo, nouveaux={7})
    likes[7] = 500
    assert 7 in F7.fraude(vues, likes, histo, nouveaux={7})
