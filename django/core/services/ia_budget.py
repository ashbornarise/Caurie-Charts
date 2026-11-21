"""Budget des IA payantes (Gemini, DeepSeek) : les crédits doivent durer au moins 30 jours (fondateur, 27/10/2026).

Chaque appel est compté en dollars estimés (table api_quota, en micro-dollars par jour UTC). Le plafond du jour est
crédit / 30 (CREDIT_GEMINI_USD, CREDIT_DEEPSEEK_USD). Au-delà, l'IA payante est refusée : la chaîne de secours passe
aux IA gratuites (Groq, OpenRouter). Les tâches secondaires (comptes d'artistes, hashtags) s'arrêtent dès la moitié.
Prix estimés par million de jetons, réglables (PRIX_*) si la grille change.
"""
from datetime import datetime, timezone

from core import db, env

JOURS = 30
DEFAUT_CREDIT = {"gemini": 5.0, "deepseek": 5.0}   # rechargés le 27/10/2026
# $ par million de jetons (entrée, sortie) et $ par requête avec recherche Google
PRIX = {"gemini": (0.30, 2.50), "deepseek": (1.32, 3.96)}   # DeepSeek V4 Pro au tarif des heures pleines (grille du 21/11/2026) : jamais sous-compté
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


# ---------------------------------------------------------------- appels « à la main » (scripts de recherche)
# 21/11/2026 : des scripts de recherche (sources de Fela, légendes, audit des tops, formule v7) appelaient Gemini en direct,
# hors de ce compteur ; ils ont fait dépasser le plafond mensuel de 5 € fixé dans Google AI Studio. Décision du fondateur :
# TOUT appel passe par ici (budget vérifié avant, dépense comptée après), y compris les essais lancés à la main.

def gemini(prompt: str, recherche: bool = True, reflexion: str = "low", part: float = 1.0, timeout: int = 600) -> tuple[str, list]:
    """Appel Gemini compté : (texte, sources [{titre, url}]). Refusé si le budget du jour est atteint."""
    import json as _json
    from core.services.platforms import HttpClient, PlatformException
    if not peut("gemini", part):
        raise PlatformException(f"Gemini : budget du jour atteint ({bilan()})")
    corps = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
             "generationConfig": {"thinkingConfig": {"thinkingLevel": reflexion}}}
    if recherche:
        corps["tools"] = [{"google_search": {}}]
    modele = env.get("GEMINI_MODEL") or "gemini-3.8-flash"
    r = HttpClient(timeout).request("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
                                    {"x-goog-api-key": env.get("GEMINI_API_KEY", ""), "Content-Type": "application/json"},
                                    _json.dumps(corps, ensure_ascii=False).encode())
    try:
        d = _json.loads(r["body"])
    except ValueError:
        d = {}
    c = (d.get("candidates") or [None])[0]
    if r["status"] != 200 or not c:
        raise PlatformException("Gemini : " + ((d.get("error") or {}).get("message") or f"HTTP {r['status']}"))
    gemini_usage(d)
    texte = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts") or [])
    sources = [{"titre": (x.get("web") or {}).get("title"), "url": (x.get("web") or {}).get("uri")}
               for x in (c.get("groundingMetadata") or {}).get("groundingChunks") or []]
    return texte, sources


def deepseek(prompt: str, modele: str = "deepseek-v4-pro", max_tokens: int = 32000, part: float = 1.0, timeout: int = 1800) -> str:
    """Appel DeepSeek compté (même règle que gemini()). Refusé si le budget du jour est atteint."""
    import json as _json
    from core.services.platforms import HttpClient, PlatformException
    if not peut("deepseek", part):
        raise PlatformException(f"DeepSeek : budget du jour atteint ({bilan()})")
    r = HttpClient(timeout).request("POST", "https://api.deepseek.com/chat/completions",
                                    {"Authorization": "Bearer " + env.get("DEEPSEEK_API_KEY", ""), "Content-Type": "application/json"},
                                    _json.dumps({"model": modele, "messages": [{"role": "user", "content": prompt}],
                                                 "max_tokens": max_tokens}, ensure_ascii=False).encode())
    try:
        d = _json.loads(r["body"])
    except ValueError:
        d = {}
    if r["status"] != 200 or not d.get("choices"):
        raise PlatformException("DeepSeek : " + str((d.get("error") or {}).get("message") or f"HTTP {r['status']}"))
    u = d.get("usage") or {}
    compte("deepseek", u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    return d["choices"][0]["message"].get("content") or ""
