"""Configuration de l'application (traduction de config/*.php), lue avec la notation « fichier.clé.sous_clé »."""
from functools import lru_cache

from core import env


@lru_cache(maxsize=1)
def _all() -> dict:
    return {
        "app": {
            "name": env.get("APP_NAME", "Cauri Charts"),
            "url": env.get("APP_URL", "http://localhost:8000").rstrip("/"),
            "env": env.get("APP_ENV", "production"),
            "debug": env.bool("APP_DEBUG", False),
            "locale": env.get("APP_LOCALE", "fr"),
            "locales": ["fr", "en"],
            "timezone": env.get("APP_TIMEZONE", "Africa/Lome"),
            "key": env.get("APP_KEY", ""),
            "contact_email": env.get("CONTACT_EMAIL", ""),
            "pilot_country": env.get("PILOT_COUNTRY", "TG").upper(),
            "methodology_version": "1.1",
            "group_label": {"code": "novaluz", "name": "Nova Luz"},
            "security": {"login_max_attempts": 5, "login_window_minutes": 15, "session_lifetime": 7200,
                         "upload_max_bytes": 5 * 1024 * 1024},
            "legal": {
                "publisher": env.get("LEGAL_PUBLISHER", ""),
                "status": env.get("LEGAL_STATUS", ""),
                "registration": env.get("LEGAL_REGISTRATION", ""),
                "address": env.get("LEGAL_ADDRESS", ""),
                "director": env.get("LEGAL_DIRECTOR", ""),
                "privacy_email": env.get("PRIVACY_EMAIL", env.get("CONTACT_EMAIL", "")),
                "host_name": env.get("HOST_NAME", "Vercel Inc."),
                "host_address": env.get("HOST_ADDRESS", "440 N Barranca Ave #4133, Covina, CA 91723, États-Unis"),
                "host_contact": env.get("HOST_CONTACT", "https://vercel.com"),
                "updated": "2026-10-01",
            },
            "tracking": {
                "ga_id": env.get("GA_MEASUREMENT_ID", ""),
                "meta_pixel_id": env.get("META_PIXEL_ID", ""),
                "youtube_embeds": env.bool("YOUTUBE_EMBEDS", True),
                "spotify_playlist": env.get("SPOTIFY_PLAYLIST_ID", ""),
                "consent_months": 6,
            },
            "retention": {"login_attempts": 6, "audit_ip": 12, "screenshots": 12, "submission_contact": 24,
                          "contact_messages": 24},
            "share": {"font_serif": env.get("SHARE_FONT_SERIF", ""), "font_sans": env.get("SHARE_FONT_SANS", "")},
        },
        "charts": {
            "prime": {"name": "Prime Chart", "kind": "tracks", "public": True, "computed": True, "size": None, "periods": ["week", "month", "year"]},
            "buzz": {"name": "Buzz Chart", "kind": "tracks", "public": True, "computed": True, "size": 10, "periods": ["week"]},
            "fresh": {"name": "Fresh Chart", "kind": "tracks", "public": True, "computed": True, "size": 10, "periods": ["week"]},
            "icon": {"name": "Icon Chart", "kind": "artists", "public": True, "computed": True, "size": 10, "periods": ["week"]},
            "legend": {"name": "Legend Chart", "kind": "tracks", "public": True, "computed": True, "size": None, "periods": ["week"]},
            "vintage": {"name": "Vintage Chart", "kind": "tracks", "public": False, "computed": False, "size": None, "periods": ["year"]},
            "prime-wa": {"name": "Prime Chart Afrique de l'Ouest", "kind": "tracks", "public": True, "computed": True, "size": 20,
                         "periods": ["week", "month", "year"], "regional": True},
        },
        "formula": {
            "version": 1,
            "weights": {"audio": 1.0, "youtube": 0.5, "declaration": 1.0},
            "country_weights": {},
            "chart_depth": 100,
            "chart_weights": {"apple_music": 0, "audiomack": 0, "boomplay": 0},
            "diversity": {"top": 5, "min_sources": 2},
            "anti_fraud": {"spike_factor": 5.0, "spike_history_weeks": 4, "spike_min_history": 2,
                           "declaration_tolerance": 0.30, "youtube_min_views": 10000,
                           "youtube_min_likes_per_1000": 1.0, "youtube_max_likes_per_1000": 250.0},
            "buzz": {"min_growth_pct": 50.0, "min_score": 2000.0},
            "fresh": {"max_age_days": 56},
        },
        "news": {
            "feeds": [
                {"name": "RFI Musique", "url": "https://www.rfi.fr/fr/musique/rss", "lang": "fr"},
                {"name": "NotJustOk", "url": "https://notjustok.com/category/news/feed/", "lang": "en", "music_only": True},
                {"name": "AmeyawDebrah", "url": "https://www.ameyawdebrah.com/feed/", "lang": "en", "music_only": True},
            ],
            "per_feed": 10, "max_age_days": 21, "keep": 90,
            "image": {"width": 720, "height": 405, "max_bytes": 6_000_000},
        },
        "ai": {
            "classify": {"threshold": 0.85, "max_ai_calls": 40},
            # Lundi, mercredi, vendredi : une rubrique en rotation parmi celles de core/services/social/themes.py
            "social": {"days": {1: "rotation", 3: "rotation", 5: "rotation"}, "handle": "@cauricharts",
                       "clip_seconds": 30, "clip_start": 30, "hashtags_base": ["#CauriCharts", "#AfriqueDeLOuest"]},
        },
        "discovery": {
            "wikidata_countries": {"TG": "Q945", "BJ": "Q962", "GH": "Q117", "CI": "Q1008", "SN": "Q1041"},
            "min_deezer_fans": 300, "min_youtube_subs": 5000, "seeds_per_run": 25, "max_new_per_run": 200,
            "priority": ["TG", "BJ"],
        },
        "watchlist": {
            "artists": {"Paki Chenzu": "TG", "Joachin Migos": None, "Wantché": None, "døpelym": None},
            "channels": {},
            "channel_names": {"UNIVERSAL MUSIC TOGO": "TG"},
        },
    }


def get(path: str, default=None):
    value = _all()
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, dict) and part.isdigit() and int(part) in value:
            value = value[int(part)]
        else:
            return default
    return value
