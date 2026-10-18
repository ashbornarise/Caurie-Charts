"""Connexion et statistiques TikTok. Toute erreur externe devient « non disponible »."""
from datetime import date, datetime, timedelta, timezone

import requests

from core import db, env

CLIENT_KEY_DEFAUT = "sbaw3djgyo5jo3pra7"
REDIRECT_URI = "https://www.cauricharts.com/tiktok/retour"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
API = "https://open.tiktokapis.com/v2"
INDISPONIBLE = "non disponible"


def creer_table():
    """Crée la table requise sur les environnements déjà déployés."""
    db.run("""CREATE TABLE IF NOT EXISTS tiktok_auth (
        id BIGSERIAL PRIMARY KEY, code TEXT, state TEXT, recu_le TIMESTAMPTZ,
        access_token TEXT, refresh_token TEXT, access_expire TIMESTAMPTZ,
        refresh_expire TIMESTAMPTZ, open_id TEXT, maj_le TIMESTAMPTZ
    )""")


def _ligne_active():
    creer_table()
    return db.one("SELECT * FROM tiktok_auth WHERE access_token IS NOT NULL ORDER BY id DESC LIMIT 1")


def echange_code(code=None):
    """Échange un code d'autorisation et stocke les jetons sans les journaliser."""
    try:
        creer_table()
        ligne = db.one("SELECT id, code FROM tiktok_auth WHERE code IS NOT NULL AND recu_le >= NOW() - INTERVAL '10 minutes' ORDER BY recu_le DESC, id DESC LIMIT 1") if code is None else None
        code = code or (ligne or {}).get("code")
        if not code:
            return False
        reponse = requests.post(TOKEN_URL, data={"client_key": env.get("TIKTOK_CLIENT_KEY", CLIENT_KEY_DEFAUT),
            "client_secret": env.get("TIKTOK_CLIENT_SECRET", ""), "code": code,
            "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI}, timeout=15)
        reponse.raise_for_status()
        data = reponse.json().get("data", {})
        if not data.get("access_token") or not data.get("refresh_token"):
            return False
        expiry = datetime.now(timezone.utc)
        db.run("""UPDATE tiktok_auth SET code = NULL, access_token = ?, refresh_token = ?,
            access_expire = ?, refresh_expire = ?, open_id = ?, maj_le = NOW() WHERE id = ?""",
            [data["access_token"], data["refresh_token"], expiry + timedelta(seconds=int(data.get("expires_in", 0))),
             expiry + timedelta(seconds=int(data.get("refresh_expires_in", 0))), data.get("open_id"), ligne["id"]])
        return True
    except Exception:
        return False


def rafraichit(ligne=None):
    """Renouvelle le jeton si son échéance est à moins d'une heure."""
    try:
        ligne = ligne or _ligne_active()
        if not ligne:
            return None
        expire = ligne.get("access_expire")
        if isinstance(expire, str):
            expire = datetime.fromisoformat(expire.replace("Z", "+00:00"))
        if expire and expire > datetime.now(timezone.utc) + timedelta(hours=1):
            return ligne.get("access_token")
        reponse = requests.post(TOKEN_URL, data={"client_key": env.get("TIKTOK_CLIENT_KEY", CLIENT_KEY_DEFAUT),
            "client_secret": env.get("TIKTOK_CLIENT_SECRET", ""), "grant_type": "refresh_token",
            "refresh_token": ligne["refresh_token"]}, timeout=15)
        reponse.raise_for_status()
        data = reponse.json().get("data", {})
        if not data.get("access_token"):
            return None
        now = datetime.now(timezone.utc)
        db.run("""UPDATE tiktok_auth SET access_token = ?, refresh_token = ?, access_expire = ?,
            refresh_expire = ?, maj_le = NOW() WHERE id = ?""",
            [data["access_token"], data.get("refresh_token", ligne["refresh_token"]),
             now + timedelta(seconds=int(data.get("expires_in", 0))),
             now + timedelta(seconds=int(data.get("refresh_expires_in", 0))), ligne["id"]])
        return data["access_token"]
    except Exception:
        return None


def stats(debut, fin):
    """Récupère profil et vidéos de la période ; protège chaque appel externe."""
    vide = {"followers_count": INDISPONIBLE, "following_count": INDISPONIBLE,
            "likes_count": INDISPONIBLE, "video_count": INDISPONIBLE, "videos": []}
    try:
        ligne = _ligne_active()
        token = rafraichit(ligne)
        if not token:
            return vide
        headers = {"Authorization": f"Bearer {token}"}
        profil = requests.get(f"{API}/user/info/", headers=headers,
            params={"fields": "open_id,display_name,follower_count,following_count,likes_count,video_count"}, timeout=15)
        profil.raise_for_status()
        info = profil.json().get("data", {}).get("user", {})
        videos, cursor, has_more = [], 0, True
        while has_more:
            rep = requests.post(f"{API}/video/list/?fields=id,title,create_time,view_count,like_count,comment_count,share_count",
                headers=headers, json={"max_count": 20, "cursor": cursor}, timeout=15)
            rep.raise_for_status()
            page = rep.json().get("data", {})
            for video in page.get("videos", []):
                cree = datetime.fromtimestamp(int(video["create_time"]), timezone.utc).date()
                if date.fromisoformat(str(debut)[:10]) <= cree <= date.fromisoformat(str(fin)[:10]):
                    videos.append(video)
            has_more, cursor = page.get("has_more", False), page.get("cursor", 0)
        return {**{k: info.get(k, INDISPONIBLE) for k in ("follower_count", "following_count", "likes_count", "video_count")},
                "open_id": info.get("open_id"), "display_name": info.get("display_name"), "videos": videos}
    except Exception:
        return vide
