"""
aggregator/db.py - Supabase client singleton.

Mirrors a standard Supabase client singleton pattern.
"""

from supabase import Client, create_client

from aggregator import config

_client: Client | None = None


def get_supabase() -> Client:
    """Return cached Supabase client, creating it on first call."""
    global _client
    if _client is None:
        if not config.SUPABASE_URL:
            raise ValueError("SUPABASE_URL is not set")
        if not config.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is not set")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def reset_client() -> None:
    """Discard cached client so next get_supabase() creates a fresh connection."""
    global _client
    _client = None
