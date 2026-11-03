"""Jetons qui expirent sans prévenir (03/11/2026) : Meta (Facebook et Instagram directs), GitHub (lancement du Studio et
des publications), TikTok (jeton de renouvellement). Chaque nuit, une alerte par e-mail 10 jours avant la fin ; le jour
où l'un expire, les envois s'arrêteraient en silence.
"""
from datetime import datetime, timezone

import requests

from core import db, env

SEUIL_JOURS = 10


def _jours(fin) -> int | None:
    if not fin:
        return None
    if isinstance(fin, str):
        fin = datetime.fromisoformat(fin.replace("Z", "+00:00").replace(" UTC", "+00:00"))
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    return (fin - datetime.now(timezone.utc)).days


def meta() -> tuple:
    """(fin, jours restants) du jeton Meta ; jeton sans fin (jeton de page permanent) : (None, None)."""
    jeton = (env.get("META_ACCESS_TOKEN", "") or "").strip().strip('"')
    if not jeton:
        return None, None
    d = requests.get("https://graph.facebook.com/v21.0/debug_token", params={"input_token": jeton, "access_token": jeton},
                     timeout=30).json().get("data") or {}
    fin = d.get("data_access_expires_at") if not d.get("expires_at") else d.get("expires_at")
    if not fin:
        return None, None
    quand = datetime.fromtimestamp(int(fin), timezone.utc)
    return quand, _jours(quand)


def github() -> tuple:
    jeton = env.get("GH_DISPATCH_TOKEN", "")
    if not jeton:
        return None, None
    r = requests.get("https://api.github.com/rate_limit", headers={"Authorization": f"Bearer {jeton}"}, timeout=30)
    fin = r.headers.get("github-authentication-token-expiration")   # ex. « 2027-01-05 10:00:00 UTC » ; absent = sans fin
    return (fin, _jours(fin)) if fin else (None, None)


def tiktok() -> tuple:
    try:
        fin = db.value("SELECT refresh_expire FROM tiktok_auth WHERE access_token IS NOT NULL ORDER BY id DESC LIMIT 1")
    except Exception:  # noqa: BLE001
        return None, None
    return (fin, _jours(fin)) if fin else (None, None)


def verifier(alerter: bool = True) -> list:
    """Une ligne par jeton ; e-mail d'alerte si l'un expire dans moins de SEUIL_JOURS jours."""
    lignes, urgents = [], []
    for nom, f in (("Meta (Facebook, Instagram)", meta), ("GitHub (Studio, publications)", github), ("TikTok", tiktok)):
        try:
            fin, jours = f()
        except Exception as exc:  # noqa: BLE001
            lignes.append(f"{nom} : vérification impossible ({str(exc)[:80]})")
            continue
        if jours is None:
            lignes.append(f"{nom} : pas de date de fin connue")
            continue
        lignes.append(f"{nom} : expire dans {jours} jour(s) ({str(fin)[:10]})")
        if jours < SEUIL_JOURS:
            urgents.append(f"{nom} : expire dans {jours} jour(s), le {str(fin)[:10]}")
    if urgents and alerter:
        from core import mail
        mail.notify_admin("jeton bientôt expiré", "À renouveler avant la date, sinon les envois s'arrêtent :\n\n"
                          + "\n".join(urgents))
    return lignes
