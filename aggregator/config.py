"""
aggregator/config.py - Configuration management.

Loads from .env and exposes settings + per-source config.
"""

import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SERPAPI_KEY: str | None = os.environ.get("SERPAPI_KEY") or None
OXYLABS_USERNAME: str | None = os.environ.get("OXYLABS_USERNAME") or None
OXYLABS_PASSWORD: str | None = os.environ.get("OXYLABS_PASSWORD") or None
INDEED_PUBLISHER_ID: str | None = os.environ.get("INDEED_PUBLISHER_ID") or None
FINDWORK_API_KEY: str | None = os.environ.get("FINDWORK_API_KEY") or None
REED_API_KEY: str | None = os.environ.get("REED_API_KEY") or None
ADZUNA_APP_ID: str | None = os.environ.get("ADZUNA_APP_ID") or None
ADZUNA_APP_KEY: str | None = os.environ.get("ADZUNA_APP_KEY") or None
SERPER_API_KEY: str | None = os.environ.get("SERPER_API_KEY") or None
OPENROUTER_API_KEY: str | None = os.environ.get("OPENROUTER_API_KEY") or None
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
DRY_RUN: bool = os.environ.get("DRY_RUN", "false").lower() == "true"
LOCK_FILE: str = os.environ.get("LOCK_FILE", "/tmp/aggregator.lock")
LOG_FILE: str | None = os.environ.get("LOG_FILE") or None

# ATS drain settings
ATS_REQUEST_DELAY: float = float(os.environ.get("ATS_REQUEST_DELAY", "0.5"))
ATS_DEACTIVATE_AFTER_FAILURES: int = int(os.environ.get("ATS_DEACTIVATE_AFTER_FAILURES", "3"))

SOURCES: dict = {
    # Existing API/feed sources
    "arbeitsamt": {"enabled": True,  "rate_limit": 60},
    "themuse":    {"enabled": True,  "rate_limit": 30},
    "arbeitnow":  {"enabled": True,  "rate_limit": 30},
    "jobicy":     {"enabled": True,  "rate_limit": 30},
    "serpapi":    {"enabled": False, "rate_limit": 10},  # Paid API - disabled until needed
    "oxylabs":    {"enabled": False, "rate_limit": 5},   # Paid API - disabled until needed
    "indeed":     {"enabled": False, "rate_limit": 30},
    "findwork":   {"enabled": True,  "rate_limit": 60},
    "reed":       {"enabled": True,  "rate_limit": 30},
    "devitjobs":      {"enabled": True,  "rate_limit": 10},
    "adzuna":         {"enabled": True,  "rate_limit": 10},  # 250 calls/day free - keep runs lean
    "praktischarzt":  {"enabled": True,  "rate_limit": 120},  # Paginated RSS - ~560 pages
    # Scraper/drain sources (no API keys needed)
    "randstad":           {"enabled": False, "rate_limit": 60},  # off by default: undocumented internal endpoint, see README caveats   # POST API - ~12K jobs
    "interamt":           {"enabled": True, "rate_limit": 60},   # HTML scraper - ~12K public sector jobs
    "lehrstellen_radar":  {"enabled": True,  "rate_limit": 60},  # HTML scraper - apprenticeship listings from HWK
    "hays":               {"enabled": True, "rate_limit": 30},   # HTML scraper - ~5.8K recruitment jobs
    # ATS feed drain sources (no API keys needed)
    "greenhouse":      {"enabled": True, "rate_limit": 120},
    "personio":        {"enabled": True, "rate_limit": 60},
    "lever":           {"enabled": True, "rate_limit": 60},
    "ashby":           {"enabled": True, "rate_limit": 60},
    "smartrecruiters": {"enabled": True, "rate_limit": 60},
    "workable":        {"enabled": True, "rate_limit": 60},
    "recruitee":       {"enabled": True, "rate_limit": 60},
    "dvinci":          {"enabled": True, "rate_limit": 60},
    "pinpoint":        {"enabled": True, "rate_limit": 60},
    "workday":         {"enabled": True, "rate_limit": 120},  # Paginated - many requests per company
}


def get_source_config(name: str) -> dict:
    """Return config dict for a source (or empty dict if unknown)."""
    return SOURCES.get(name, {})


def is_source_enabled(name: str) -> bool:
    """Check if a source is enabled."""
    return SOURCES.get(name, {}).get("enabled", False)


def validate() -> None:
    """Raise ValueError if required config is missing."""
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL is not set in environment / .env")
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is not set in environment / .env")
