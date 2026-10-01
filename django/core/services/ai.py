"""Fournisseur d'IA interchangeable (traduction de Services\\AI).

Par défaut Gemini (offre gratuite de Google AI Studio), avec Groq (offre gratuite) en secours si GROQ_API_KEY est
fournie ; Claude si AI_PROVIDER=claude et une clé Anthropic est fournie. Sur les offres gratuites, on n'envoie
que des données publiques.
"""
import json
import re
from urllib.parse import quote

from core import env
from core.services.platforms import HttpClient, PlatformException


class ClaudeClient:
    """API Claude (Messages) ; option : recherche web côté serveur d'Anthropic, sources citées."""
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, http: HttpClient, api_key: str | None = None, model: str | None = None):
        self.http = http
        self.api_key = api_key if api_key is not None else env.get("ANTHROPIC_API_KEY", "")
        self.model = model or env.get("ANTHROPIC_MODEL", "claude-opus-5-5")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def ask(self, system: str, prompt: str, max_tokens: int = 1500, web_searches: int = 0) -> dict:
        if not self.is_available():
            raise PlatformException("ANTHROPIC_API_KEY absente")
        body = {"model": self.model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": prompt}]}
        if web_searches > 0:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": web_searches}]
        resp = self.http.request("POST", self.URL, {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                                                    "content-type": "application/json"}, json.dumps(body, ensure_ascii=False).encode())
        try:
            data = json.loads(resp["body"])
        except ValueError:
            data = {}
        if resp["status"] != 200 or "content" not in data:
            raise PlatformException("Claude : " + ((data.get("error") or {}).get("message") or f"HTTP {resp['status']}"))
        text, sources = "", []
        for block in data["content"]:
            if block.get("type") == "text":
                text += block["text"]
                sources += [c["url"] for c in block.get("citations") or [] if c.get("url")]
            elif block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
                sources += [r["url"] for r in block["content"] if r.get("url")]
        return {"text": text.strip(), "sources": list(dict.fromkeys(sources))}


class GeminiClient:
    """API Gemini (offre gratuite) ; modèle suivant de la liste en cas de 404/429/500/503."""
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

    def __init__(self, http: HttpClient, api_key: str | None = None, model: str | None = None):
        self.http = http
        self.api_key = api_key if api_key is not None else env.get("GEMINI_API_KEY", "")
        self.models = list(dict.fromkeys(m for m in [model or env.get("GEMINI_MODEL", "gemini-3.5-flash"),
                                                     "gemini-flash-lite-latest", "gemini-3.8-flash"] if m))

    def is_available(self) -> bool:
        return bool(self.api_key)

    def ask(self, system: str, prompt: str, max_tokens: int = 1500, web_searches: int = 0) -> dict:
        if not self.is_available():
            raise PlatformException("GEMINI_API_KEY absente")
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max(max_tokens, 2048), "temperature": 0.1 if web_searches > 0 else 0.8}}
        if web_searches > 0 and env.bool("GEMINI_GROUNDING"):
            body["tools"] = [{"google_search": {}}]
        last = "aucun modèle disponible"
        for model in self.models:
            resp = self.http.request("POST", self.URL.format(quote(model, safe="-_.~")),
                                     {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                                     json.dumps(body, ensure_ascii=False).encode())
            try:
                data = json.loads(resp["body"])
            except ValueError:
                data = {}
            if resp["status"] == 200 and (data.get("candidates") or [None])[0]:
                return self._read(data["candidates"][0])
            last = (data.get("error") or {}).get("message") or f"HTTP {resp['status']}"
            if resp["status"] not in (404, 429, 500, 503):
                break  # erreur de requête ou de clé : inutile d'essayer un autre modèle
        raise PlatformException("Gemini : " + last)

    @staticmethod
    def _read(candidate: dict) -> dict:
        text = "".join(p.get("text", "") for p in (candidate.get("content") or {}).get("parts") or [])
        sources = [c["web"]["uri"] for c in (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
                   if (c.get("web") or {}).get("uri")]
        return {"text": text.strip(), "sources": list(dict.fromkeys(sources))}


class GroqClient:
    """API Groq (offre gratuite, format OpenAI) ; modèle suivant de la liste en cas de 404/429/500/503.
    Pas de recherche web : web_searches est ignoré (le classement des artistes s'appuie alors sur les faits fournis)."""
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, http: HttpClient, api_key: str | None = None, model: str | None = None):
        self.http = http
        self.api_key = api_key if api_key is not None else env.get("GROQ_API_KEY", "")
        self.models = list(dict.fromkeys(m for m in [model or env.get("GROQ_MODEL", ""), "openai/gpt-oss-120b",
                                                     "llama-3.3-70b-versatile", "qwen/qwen3-32b"] if m))

    def is_available(self) -> bool:
        return bool(self.api_key)

    def ask(self, system: str, prompt: str, max_tokens: int = 1500, web_searches: int = 0) -> dict:
        if not self.is_available():
            raise PlatformException("GROQ_API_KEY absente")
        last = "aucun modèle disponible"
        for model in self.models:
            body = {"model": model, "max_tokens": max(max_tokens, 2048), "temperature": 0.1 if web_searches > 0 else 0.8,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
            resp = self.http.request("POST", self.URL, {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                                     json.dumps(body, ensure_ascii=False).encode())
            try:
                data = json.loads(resp["body"])
            except ValueError:
                data = {}
            if resp["status"] == 200 and (data.get("choices") or [None])[0]:
                text = ((data["choices"][0].get("message") or {}).get("content") or "")
                return {"text": re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip(), "sources": []}
            last = (data.get("error") or {}).get("message") or f"HTTP {resp['status']}"
            if resp["status"] not in (404, 429, 500, 503):
                break
        raise PlatformException("Groq : " + last)


class FallbackClient:
    """Essaie chaque fournisseur dans l'ordre : quota épuisé ou panne chez l'un, l'autre prend le relais."""

    def __init__(self, clients: list):
        self.clients = [c for c in clients if c.is_available()]

    def is_available(self) -> bool:
        return bool(self.clients)

    def ask(self, system: str, prompt: str, max_tokens: int = 1500, web_searches: int = 0) -> dict:
        errors = []
        for c in self.clients:
            try:
                return c.ask(system, prompt, max_tokens, web_searches)
            except PlatformException as exc:
                errors.append(str(exc))
        raise PlatformException(" ; ".join(errors) or "aucun fournisseur d'IA")


def make():
    """Client configuré, ou None si aucune clé n'est renseignée (les automatismes restent sans IA).
    AI_PROVIDER : gemini (défaut, Groq en secours), groq (Gemini en secours) ou claude."""
    http = HttpClient(120)
    provider = (env.get("AI_PROVIDER", "gemini") or "gemini").lower()
    if provider == "claude":
        client = ClaudeClient(http)
    else:
        pair = [GeminiClient(http), GroqClient(http)]
        client = FallbackClient(pair[::-1] if provider == "groq" else pair)
    return client if client.is_available() else None


def extract_json(text: str):
    """Premier objet JSON équilibré d'une réponse (le modèle peut l'entourer de texte)."""
    for start, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                    except ValueError:
                        return None
                    return data if isinstance(data, dict) else None
    return None
