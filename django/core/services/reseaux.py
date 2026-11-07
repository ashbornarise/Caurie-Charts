"""Réseaux officiels des artistes (YouTube, Instagram, TikTok) par Gemini avec la recherche Google, par lots
(07/11/2026, demande du fondateur : « envoyer les noms des artistes à Gemini qui demande à Google les réseaux de
l'artiste, à chaque tâche »). Constat du jour : 868 artistes actifs sur 1 250 sans chaîne YouTube reliée, alors que la
recherche YouTube coûte 100 unités de quota par artiste.

Garde-fous :
- une vraie recherche Google doit avoir eu lieu (sources renvoyées), sinon rien n'est enregistré ;
- certitude « haute » seulement ; jamais une chaîne « - Topic », un fan, un média ou un label multi-artistes ;
- la chaîne YouTube est vérifiée sur YouTube (1 à 2 unités) : nom identique à l'artiste, ou une de ses vidéos porte
  un titre de son catalogue ; une chaîne déjà reliée à un autre artiste est écartée ;
- Instagram et TikTok : seulement si la fiche n'en a pas, et jamais par-dessus une saisie manuelle du fondateur.
"""
import json
import re

from core import db, env
from core.services.platforms import HttpClient, PlatformException, YouTubeQuota, log_write

TAILLE = 15
CHAINE = re.compile(r"(UC[A-Za-z0-9_-]{22})")
HANDLE = re.compile(r"youtube\.com/@([A-Za-z0-9._-]{2,60})|^@([A-Za-z0-9._-]{2,60})$")
PAS_OFFICIEL = re.compile(r"topic|fan|\bfc\b|news|media|\btv\b|lyrics|paroles|records|music\s*page", re.I)


def colonnes() -> None:
    db.run("ALTER TABLE artists ADD COLUMN IF NOT EXISTS reseaux_le TIMESTAMPTZ NULL")


def a_chercher(limite: int) -> list:
    """Artistes actifs sans chaîne YouTube, jamais passés ou passés il y a plus de 30 jours ; ceux des classements d'abord."""
    return db.all(f"""SELECT a.id, a.name, a.instagram, a.tiktok, a.comptes_source, c.code AS pays,
                             (SELECT t.title FROM tracks t LEFT JOIN chart_observations o ON o.track_id = t.id
                               WHERE t.artist_id = a.id GROUP BY t.id, t.title ORDER BY COUNT(o.id) DESC, t.id LIMIT 1) AS titre
                      FROM artists a JOIN countries c ON c.id = a.submission_country_id
                      WHERE a.status = 'active' AND a.youtube_channel_id IS NULL
                        AND (a.reseaux_le IS NULL OR a.reseaux_le < NOW() - INTERVAL '30 days')
                      ORDER BY EXISTS (SELECT 1 FROM tracks t JOIN chart_observations o ON o.track_id = t.id
                                       WHERE t.artist_id = a.id AND o.observed_on >= CURRENT_DATE - 14) DESC,
                               a.reseaux_le NULLS FIRST, a.id
                      LIMIT {int(limite)}""")


def _demande(lot: list, http: HttpClient) -> dict:
    from core.helpers import country_name
    from core.services.social.comptes import _gemini
    lignes = "\n".join(f"{i + 1}. {a['name']} ({country_name(a['pays'])})" + (f", titre connu : « {a['titre']} »" if a.get("titre") else "")
                       for i, a in enumerate(lot))
    # Question en langage naturel : avec « réponds seulement en JSON », Gemini saute la recherche Google
    prompt = ("Recherche sur Google les réseaux officiels de chacun de ces artistes musicaux d'Afrique de l'Ouest : sa chaîne "
              "YouTube officielle (lien youtube.com/@... ou youtube.com/channel/UC...), son compte Instagram et son compte TikTok. "
              "Appuie-toi sur ses liens officiels (bio Spotify, Apple Music, Audiomack, site, presse, Wikidata). Jamais une chaîne "
              "« - Topic », un fan club, un média ou une chaîne de label qui publie pour plusieurs artistes.\n" + lignes +
              "\n\nPour chaque artiste et chaque réseau, donne ta certitude : « haute » seulement si une source fiable le confirme, "
              "sinon « moyenne » ou « basse ». N'invente rien : en cas de doute, mets null. Termine ta réponse par un bloc JSON : "
              '[{"n": numéro, "youtube": "lien ou null", "certitude_youtube": "haute|moyenne|basse", "instagram": "nom sans @ ou null", '
              '"certitude_instagram": "...", "tiktok": "nom sans @ ou null", "certitude_tiktok": "..."}]')
    try:
        texte, meta = _gemini(prompt, http, "low", 0.5)   # tâche secondaire : la moitié du budget du jour au plus
        if not meta.get("groundingChunks"):
            return {}
    except PlatformException:
        # Budget Gemini du jour atteint : OpenRouter avec sa recherche web (07/11/2026, demande du fondateur). Sans
        # recherche, ses modèles inventent (essai : « @PhilipayneOfficiel » n'existe pas) : on exige des sources citées.
        texte = _openrouter(prompt)
        if not texte:
            return {}
    blocs = re.findall(r"\[\s*\{.*?\}\s*\]", texte, re.S)
    try:
        liste = json.loads(blocs[-1]) if blocs else []
    except ValueError:
        liste = []
    return {int(x["n"]): x for x in liste if isinstance(x, dict) and str(x.get("n", "")).isdigit()}


OPENROUTER_MODELES = ("nvidia/nemotron-3-ultra-550b-a55b:free", "google/gemma-4-31b-it:free")


def _openrouter(prompt: str) -> str:
    """Réponse d'un modèle gratuit d'OpenRouter avec recherche web (quelques millièmes de dollar), seulement si des
    sources sont citées ; chaîne vide sinon."""
    import requests
    cle = env.get("OPENROUTER_API_KEY", "")
    if not cle:
        return ""
    for modele in OPENROUTER_MODELES:
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer " + cle},
                              json={"model": modele, "messages": [{"role": "user", "content": prompt}],
                                    "plugins": [{"id": "web", "max_results": 8}]}, timeout=180)
            msg = ((r.json().get("choices") or [{}])[0]).get("message") or {}
        except (requests.RequestException, ValueError):
            continue
        if r.status_code == 200 and msg.get("annotations") and msg.get("content"):
            return msg["content"]
    return ""


def _chaine(lien: str, key: str, http_get) -> tuple[str | None, str]:
    """Identifiant UC… et nom de la chaîne à partir d'un lien ou d'un @nom (1 unité de quota)."""
    lien = str(lien or "").strip()
    m = CHAINE.search(lien)
    h = HANDLE.search(lien)
    if not (m or h) or not YouTubeQuota.spend(1):
        return None, ""
    params = {"part": "snippet", "key": key}
    if m:
        params["id"] = m.group(1)
    else:
        params["forHandle"] = "@" + (h.group(1) or h.group(2))
    items = (http_get("https://www.googleapis.com/youtube/v3/channels", params) or {}).get("items") or []
    return (items[0]["id"], (items[0].get("snippet") or {}).get("title") or "") if items else (None, "")


def chercher(lots: int = 4, taille: int = TAILLE, http: HttpClient | None = None) -> list:
    import requests

    from core.services import ia_budget
    from core.services.imports.channel_sync import YouTubeChannelSync
    from core.services.social.comptes import NOM, PAS_ARTISTE
    colonnes()
    key = env.get("YOUTUBE_API_KEY", "")
    http = http or HttpClient(120)
    sync = YouTubeChannelSync(HttpClient(30))
    get = lambda url, params: requests.get(url, params=params, timeout=20).json()
    lignes, chaines, comptes = [], 0, 0
    for _ in range(lots):
        lot = a_chercher(taille)
        if not lot:
            lignes.append("tous les artistes actifs ont été passés")
            break
        try:
            reponses = _demande(lot, http)
        except PlatformException as exc:
            lignes.append(str(exc))
            break
        if not reponses:
            lignes.append("aucune réponse sourcée pour ce lot : la suite au prochain passage")
            break
        for i, a in enumerate(lot):
            r = reponses.get(i + 1) or {}
            db.run("UPDATE artists SET reseaux_le = NOW() WHERE id = ?", [a["id"]])
            # YouTube : vérifié sur YouTube avant d'être relié
            if key and r.get("certitude_youtube") == "haute" and r.get("youtube") and not PAS_OFFICIEL.search(str(r["youtube"])):
                cid, titre = _chaine(r["youtube"], key, get)
                deja = cid and db.value("SELECT name FROM artists WHERE (youtube_channel_id = ? OR youtube_channel_2 = ?) AND id <> ?",
                                        [cid, cid, a["id"]])
                if cid and not deja and not PAS_OFFICIEL.search(titre) and (sync.same_name(titre, a["name"]) or sync.confirms(cid, a["id"], key)):
                    db.run("UPDATE artists SET youtube_channel_id = ?, channel_checked_at = NOW() WHERE id = ? AND youtube_channel_id IS NULL", [cid, a["id"]])
                    if YouTubeQuota.spend(2):
                        try:
                            sync._sync_channel(int(a["id"]), a["name"], cid, int(db.value("SELECT submission_country_id FROM artists WHERE id = ?", [a["id"]])), key, 2)
                        except Exception as exc:  # noqa: BLE001
                            log_write("reseaux", "warning", f"{a['name']} : clips non relus ({exc})")
                    chaines += 1
                    lignes.append(f"{a['name']} : YouTube {titre} ({cid})")
                elif cid:
                    log_write("reseaux", "info", f"{a['name']} : chaîne {titre} ({cid}) écartée" + (f", déjà à {deja}" if deja else ""))
            # Instagram et TikTok : seulement si la fiche est vide, jamais par-dessus une saisie manuelle
            if a.get("comptes_source") == "manuel":
                continue
            for site in ("instagram", "tiktok"):
                v = str(r.get(site) or "").strip().lstrip("@")
                if a.get(site) or r.get(f"certitude_{site}") != "haute" or not NOM.fullmatch(v) or PAS_ARTISTE.search(v):
                    continue
                if db.value(f"SELECT 1 FROM artists WHERE lower({site}) = lower(?) AND id <> ?", [v, a["id"]]):
                    continue
                db.run(f"UPDATE artists SET {site} = ?, comptes_source = COALESCE(comptes_source, 'ia-google'), comptes_le = NOW() WHERE id = ?", [v, a["id"]])
                comptes += 1
    lignes.insert(0, f"Réseaux des artistes (Gemini + Google, ou OpenRouter + web) : {chaines} chaîne(s) YouTube reliée(s), {comptes} compte(s) "
                     f"Instagram/TikTok · {ia_budget.bilan()}")
    return lignes
