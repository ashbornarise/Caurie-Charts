"""Budget des IA payantes (Gemini, DeepSeek) : les crédits doivent durer au moins 30 jours (fondateur, 27/10/2026).

Chaque appel est compté en dollars estimés (table api_quota, en micro-dollars par jour UTC). Le plafond du jour est
crédit / 30 (CREDIT_GEMINI_USD, CREDIT_DEEPSEEK_USD). Au-delà, l'IA payante est refusée : la chaîne de secours passe
aux IA gratuites (Groq, OpenRouter). Les tâches secondaires (comptes d'artistes, hashtags) s'arrêtent dès la moitié.
Prix estimés par million de jetons, réglables (PRIX_*) si la grille change.
"""
from datetime import datetime, timezone

from core import db, env

JOURS = 30
DEFAUT_CREDIT = {"gemini": 10.0, "deepseek": 5.0}
# $ par million de jetons (entrée, sortie) et $ par requête avec recherche Google
PRIX = {"gemini": (0.30, 2.50), "deepseek": (0.28, 0.42)}
PRIX_RECHERCHE = 0.035


def _jour() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _num(cle: str, defaut: float) -> float:
    try:
        return float(env.get(cle, "") or defaut)
    except ValueError:
        return defaut


def plafond(f: str) -> float:
    """Dépense permise aujourd'hui, en dollars."""
    return _num(f"CREDIT_{f.upper()}_USD", DEFAUT_CREDIT.get(f, 5.0)) / JOURS


def depense(f: str) -> float:
    try:
        return int(db.value("SELECT units_used FROM api_quota WHERE api = ? AND day = ?", [f"cout-{f}", _jour()]) or 0) / 1e6
    except Exception:  # noqa: BLE001 — base indisponible : on ne bloque pas
        return 0.0


def peut(f: str, part: float = 1.0) -> bool:
    """Vrai s'il reste du budget aujourd'hui ; part=0.5 pour une tâche secondaire (s'arrête à mi-budget)."""
    return depense(f) < plafond(f) * part


def compte(f: str, entree: int, sortie: int, recherches: int = 0) -> None:
    import os
    if os.environ.get("PYTEST_CURRENT_TEST"):   # les tests ne comptent pas dans le budget réel
        return
    pe, ps = PRIX.get(f, (1.0, 1.0))
    pe, ps = _num(f"PRIX_{f.upper()}_ENTREE", pe), _num(f"PRIX_{f.upper()}_SORTIE", ps)
    cout = (entree or 0) * pe / 1e6 + (sortie or 0) * ps / 1e6 + recherches * _num("PRIX_RECHERCHE", PRIX_RECHERCHE)
    try:
        db.run("""INSERT INTO api_quota (api, day, units_used) VALUES (?, ?, ?)
                  ON CONFLICT (api, day) DO UPDATE SET units_used = api_quota.units_used + EXCLUDED.units_used""",
               [f"cout-{f}", _jour(), int(cout * 1e6)])
    except Exception:  # noqa: BLE001
        pass


def gemini_usage(data: dict) -> None:
    """Compte un appel Gemini à partir de sa réponse (usageMetadata, recherche Google éventuelle)."""
    u = data.get("usageMetadata") or {}
    cand = (data.get("candidates") or [{}])[0] or {}
    recherche = 1 if (cand.get("groundingMetadata") or {}).get("webSearchQueries") else 0
    compte("gemini", u.get("promptTokenCount", 0), (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0),
           recherche)


def bilan() -> str:
    return " · ".join(f"{f} {depense(f):.2f} $ / {plafond(f):.2f} $ aujourd'hui" for f in PRIX)
