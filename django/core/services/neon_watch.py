"""Surveillance de la base Neon (offre gratuite : 5 Go de transfert par mois et par projet).

  usage()       : transfert consommé depuis le début de la période, via l'API Neon (NEON_API_KEY) ;
  report_line() : ligne du rapport du matin, avec « [alerte] » à 70 % puis 90 % ;
  blocked()     : la base refuse les connexions pour dépassement de quota ? (e-mail immédiat, page de maintenance).
Si la base est bloquée : console.neon.tech > Upgrade > Launch, elle repart en quelques secondes, sans déménagement.
"""
import time
from urllib.parse import urlparse

from core import env

LIMIT_GB = 5.0
UPGRADE_URL = "https://console.neon.tech/app/billing"
_last_alert = 0.0


def _endpoint() -> str:
    host = urlparse(env.get("DATABASE_URL", "")).hostname or ""
    return host.split(".")[0].replace("-pooler", "")  # ep-curly-mud-b2nbpcqk


def usage() -> dict | None:
    """{gb, pct, project} ou None (pas de clé, API injoignable, champ absent)."""
    key = env.get("NEON_API_KEY", "")
    if not key:
        return None
    try:
        import requests
        h = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        projects = requests.get("https://console.neon.tech/api/v2/projects", headers=h, timeout=20).json().get("projects") or []
        ep = _endpoint()
        for p in projects:
            eps = requests.get(f"https://console.neon.tech/api/v2/projects/{p['id']}/endpoints", headers=h, timeout=20).json().get("endpoints") or []
            if any(e.get("id") == ep for e in eps):
                full = requests.get(f"https://console.neon.tech/api/v2/projects/{p['id']}", headers=h, timeout=20).json().get("project") or {}
                b = full.get("data_transfer_bytes")
                if b is None:
                    return None
                gb = int(b) / 1e9
                return {"gb": gb, "pct": round(gb / LIMIT_GB * 100), "project": p.get("name")}
    except Exception:  # noqa: BLE001 — la surveillance ne doit jamais casser la nuit
        return None
    return None


def report_line() -> str | None:
    u = usage()
    if not u:
        return None
    line = f"Base Neon « {u['project']} » : {u['gb']:.2f} Go de transfert sur {LIMIT_GB:.0f} Go ce mois-ci ({u['pct']} %)"
    if u["pct"] >= 90:
        return f"[alerte] {line}. Blocage imminent : passer en Launch ({UPGRADE_URL}) ou réduire le trafic."
    if u["pct"] >= 70:
        return f"[alerte] {line}. À surveiller."
    return line


def blocked(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "exceeded the quota" in msg or "data transfer quota" in msg or ("quota" in msg and "neon" in msg)


def alert_blocked(exc: BaseException) -> None:
    """E-mail immédiat (au plus une fois par heure et par instance) quand la base est bloquée."""
    global _last_alert
    if time.time() - _last_alert < 3600:
        return
    _last_alert = time.time()
    try:
        from core import mail
        mail.notify_admin("SITE EN PANNE : base Neon bloquée (quota dépassé)",
                          "La base de données refuse les connexions : le transfert mensuel de l'offre gratuite est épuisé.\n\n"
                          f"Pour rétablir le site tout de suite : {UPGRADE_URL} > Upgrade > Launch (quelques secondes, "
                          "sans déménagement ni perte de données).\n\nMessage de Neon : " + str(exc)[:300])
    except Exception:  # noqa: BLE001
        pass
