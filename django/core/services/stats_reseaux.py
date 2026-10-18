"""Collecte protégée des statistiques des réseaux sociaux."""
import json
from datetime import date, timedelta

import requests

from core import db, env
from core.services import telegram

META = "https://graph.facebook.com/v21.0"
INDISPONIBLE = "non disponible"


def _get(url: str, params: dict | None = None) -> dict:
    """Effectue un GET HTTP sans laisser une erreur externe interrompre la collecte."""
    try:
        response = requests.get(url, params=params or {}, timeout=12)
        response.raise_for_status()
        contenu = response.json()
        return contenu if isinstance(contenu, dict) else {}
    except Exception:
        return {}


def _nombre(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return INDISPONIBLE


def _insights(url: str, token: str, names: list[str], depuis: str, jusqua: str) -> dict:
    resultat = {nom: INDISPONIBLE for nom in names}
    data = _get(url, {"metric": ",".join(names), "metric_type": "total_value", "period": "day", "since": depuis,
                      "until": jusqua, "access_token": token}).get("data", [])
    for item in data if isinstance(data, list) else []:
        nom = item.get("name")
        try:
            valeur = item.get("total_value", {}).get("value", INDISPONIBLE)
            resultat[nom] = _nombre(valeur) if valeur != INDISPONIBLE else INDISPONIBLE
        except (AttributeError, TypeError):
            pass
    return resultat


def _instagram(token: str, identifiant: str, debut: date, fin: date) -> dict:
    stats = {"followers_count": INDISPONIBLE, "media_count": INDISPONIBLE}
    profil = _get(f"{META}/{identifiant}", {"fields": "followers_count,media_count", "access_token": token})
    for cle in stats:
        stats[cle] = _nombre(profil.get(cle))
    stats["insights"] = _insights(f"{META}/{identifiant}/insights", token,
                                   ["reach", "profile_views", "accounts_engaged", "total_interactions"],
                                   debut.isoformat(), fin.isoformat())
    stats["medias"] = []
    media = _get(f"{META}/{identifiant}/media", {"fields": "id,caption,timestamp,media_type", "since": debut.isoformat(),
                    "until": fin.isoformat(), "limit": 100, "access_token": token}).get("data", [])
    for item in media if isinstance(media, list) else []:
        valeurs = {"reach": INDISPONIBLE, "likes": INDISPONIBLE, "comments": INDISPONIBLE,
                   "shares": INDISPONIBLE, "saved": INDISPONIBLE}
        if item.get("media_type") == "VIDEO":
            valeurs["views"] = INDISPONIBLE
        insights = _get(f"{META}/{item.get('id')}/insights", {"metric": ",".join(valeurs),
                            "access_token": token}).get("data", [])
        for insight in insights if isinstance(insights, list) else []:
            try:
                nom = insight.get("name")
                raw = insight.get("values", [{}])[0].get("value")
                if nom in valeurs:
                    valeurs[nom] = _nombre(raw)
            except (AttributeError, IndexError, TypeError):
                continue
        stats["medias"].append({"id": item.get("id"), "titre": item.get("caption") or "Publication", **valeurs})
    return stats


def _facebook(token: str, identifiant: str, debut: date, fin: date) -> dict:
    page = _get(f"{META}/{identifiant}", {"fields": "access_token,followers_count,fan_count", "access_token": token})
    page_token = page.get("access_token") or token
    stats = {k: _nombre(page.get(k)) for k in ("followers_count", "fan_count")}
    stats["insights"] = _insights(f"{META}/{identifiant}/insights", page_token,
                                   ["page_impressions_unique", "page_post_engagements"],
                                   debut.isoformat(), fin.isoformat())
    return stats


def collecter(aujourdhui: date | None = None) -> dict:
    """Collecte, historise, puis compare avec la dernière semaine disponible."""
    fin = aujourdhui or date.today()
    debut = fin - timedelta(days=6)
    debut_iso, fin_iso = debut.isoformat(), fin.isoformat()
    token, page_id, ig_id = (env.get(k, "") for k in ("META_ACCESS_TOKEN", "META_PAGE_ID", "META_IG_ID"))
    instagram = _instagram(token, ig_id, debut, fin) if token and ig_id else {
        "followers_count": INDISPONIBLE, "media_count": INDISPONIBLE, "insights": {}, "medias": []}
    facebook = _facebook(token, page_id, debut, fin) if token and page_id else {
        "followers_count": INDISPONIBLE, "fan_count": INDISPONIBLE, "insights": {}}
    try:
        telegram_count = _nombre(telegram.call("getChatMemberCount", {"chat_id": env.get("TELEGRAM_CHAT_ID", "")}))
    except Exception:
        telegram_count = INDISPONIBLE
    try:
        from core.services import tiktok
        tiktok_stats = tiktok.stats(debut, fin)
    except Exception:
        tiktok_stats = {"follower_count": INDISPONIBLE, "following_count": INDISPONIBLE,
                        "likes_count": INDISPONIBLE, "video_count": INDISPONIBLE, "videos": []}
    valeurs = {"instagram.followers_count": instagram["followers_count"], "instagram.media_count": instagram["media_count"],
               "facebook.followers_count": facebook["followers_count"], "facebook.fan_count": facebook["fan_count"],
               "telegram.member_count": telegram_count,
               "tiktok.follower_count": tiktok_stats.get("follower_count", INDISPONIBLE),
               "tiktok.following_count": tiktok_stats.get("following_count", INDISPONIBLE),
               "tiktok.likes_count": tiktok_stats.get("likes_count", INDISPONIBLE),
               "tiktok.video_count": tiktok_stats.get("video_count", INDISPONIBLE)}
    for video in tiktok_stats.get("videos", []):
        identifiant = str(video.get("id", ""))
        if identifiant and identifiant.isalnum():
            valeurs[f"tiktok.video_{identifiant}_title"] = video.get("title") or "Publication"
            for metrique in ("view_count", "like_count", "comment_count", "share_count"):
                if metrique in video:
                    valeurs[f"tiktok.video_{identifiant}_{metrique}"] = video[metrique]
    for reseau, bloc in (("instagram", instagram.get("insights", {})), ("facebook", facebook.get("insights", {}))):
        valeurs.update({f"{reseau}.{cle}": val for cle, val in bloc.items()})
    try:
        db.run("CREATE TABLE IF NOT EXISTS stats_reseaux (date DATE NOT NULL, reseau TEXT NOT NULL, cle TEXT NOT NULL, valeur TEXT NOT NULL, PRIMARY KEY(date, reseau, cle))")
        precedentes = db.all("SELECT reseau, cle, valeur FROM stats_reseaux WHERE date < ? ORDER BY date DESC LIMIT 100", [fin_iso])
        precedent = {}
        for ligne in precedentes:
            precedent.setdefault(f"{ligne['reseau']}.{ligne['cle']}", ligne["valeur"])
        for cle, valeur in valeurs.items():
            reseau, nom = cle.split(".", 1)
            db.run("INSERT INTO stats_reseaux(date, reseau, cle, valeur) VALUES (?, ?, ?, ?) ON CONFLICT(date, reseau, cle) DO UPDATE SET valeur=EXCLUDED.valeur",
                   [fin_iso, reseau, nom, str(valeur)])
    except Exception:
        precedent = {}
    evolution = {}
    for cle, valeur in valeurs.items():
        ancien = precedent.get(cle)
        try:
            evolution[cle] = int(valeur) - int(ancien) if ancien is not None and valeur != INDISPONIBLE else INDISPONIBLE
        except (TypeError, ValueError):
            evolution[cle] = INDISPONIBLE
    objectifs = {}
    for reseau, cle in (("instagram", "instagram.followers_count"), ("facebook", "facebook.followers_count"),
                        ("telegram", "telegram.member_count"), ("tiktok", "tiktok.follower_count")):
        valeur = valeurs[cle]
        objectifs[reseau] = {"objectif": 10000, "abonnes": valeur,
                              "progression_pct": round(int(valeur) * 100 / 10000, 2) if valeur != INDISPONIBLE else INDISPONIBLE,
                              "date_objectif": "2026-12-31"}
    return {"periode": {"debut": debut_iso, "fin": fin_iso}, "instagram": instagram, "facebook": facebook,
            "telegram": {"member_count": telegram_count}, "tiktok": tiktok_stats,
            "evolution_semaine": evolution, "objectifs": objectifs}
