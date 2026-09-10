"""
aggregator/health.py - Source health tracking + circuit breaker.

Functions:
    update_health(source_name, success, fetched=0, new=0, error=None)
    get_health(source_name) -> dict | None
    get_all_health() -> list[dict]
    is_circuit_open(source_name) -> bool
    reset_circuit(source_name)
"""

import os
import re
from datetime import datetime, timedelta, timezone

from aggregator.db import get_supabase
from aggregator.logging_config import get_logger

log = get_logger(__name__)

CIRCUIT_BREAKER_THRESHOLD: int = int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", "3"))
CIRCUIT_BREAKER_COOLDOWN_HOURS: int = int(os.environ.get("CIRCUIT_BREAKER_COOLDOWN_HOURS", "24"))

# SEC-04: Strip potential API keys/tokens from error messages before DB storage
_SECRET_PATTERN = re.compile(
    r'(key|token|password|apikey|secret|authorization)[=:\s]+\S+',
    re.IGNORECASE,
)


def _sanitize_error(msg: str) -> str:
    return _SECRET_PATTERN.sub(r'\1=***', msg)


def update_health(
    source_name: str,
    success: bool,
    fetched: int = 0,
    new: int = 0,
    error: str | None = None,
) -> None:
    """Update source health record after a run. Upsert pattern."""
    now = datetime.now(timezone.utc).isoformat()
    current = get_health(source_name)
    total_contributed = (current.get("total_jobs_contributed") or 0) + new if current else new
    consecutive_failures = 0 if success else ((current.get("consecutive_failures") or 0) + 1 if current else 1)

    record: dict = {
        "source_name": source_name,
        "last_run_at": now,
        "jobs_fetched_last_run": fetched,
        "jobs_new_last_run": new,
        "consecutive_failures": consecutive_failures,
        "total_jobs_contributed": total_contributed,
        "is_healthy": success,
        "updated_at": now,
    }
    if success:
        record["last_success_at"] = now
        record["last_error"] = None
    else:
        record["last_failure_at"] = now
        record["last_error"] = _sanitize_error(str(error))[:500] if error else None

    try:
        get_supabase().table("source_health").upsert(record, on_conflict="source_name").execute()
    except Exception as e:
        log.error(f"Failed to update health for {source_name}: {e}")


def get_health(source_name: str) -> dict | None:
    """Read health record for a single source."""
    try:
        result = get_supabase().table("source_health").select("*").eq("source_name", source_name).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        log.error(f"Failed to get health for {source_name}: {e}")
        return None


def get_all_health() -> list[dict]:
    """Read all source health records, ordered by source name."""
    try:
        result = get_supabase().table("source_health").select("*").order("source_name").execute()
        return result.data or []
    except Exception as e:
        log.error(f"Failed to get all health records: {e}")
        return []


def is_circuit_open(source_name: str) -> bool:
    """Return True if source should be skipped (too many failures or disabled)."""
    health = get_health(source_name)
    if not health:
        return False  # No record = first run, allow through

    if not health.get("is_enabled", True):
        return True  # Manually disabled via DB

    failures = health.get("consecutive_failures", 0)
    if failures < CIRCUIT_BREAKER_THRESHOLD:
        return False

    # Auto-reset after cooldown: if last failure was > 24h ago, try once more
    last_failure = health.get("last_failure_at")
    if last_failure:
        try:
            dt = datetime.fromisoformat(last_failure.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - dt > timedelta(hours=CIRCUIT_BREAKER_COOLDOWN_HOURS):
                log.info(f"[{source_name}] Circuit auto-resetting after {CIRCUIT_BREAKER_COOLDOWN_HOURS}h cooldown")
                reset_circuit(source_name)
                return False
        except (ValueError, TypeError):
            pass

    return True  # Circuit open


def reset_circuit(source_name: str) -> None:
    """Reset circuit breaker - clear failures and mark healthy."""
    try:
        get_supabase().table("source_health").update({
            "consecutive_failures": 0,
            "is_healthy": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("source_name", source_name).execute()
    except Exception as e:
        log.error(f"Failed to reset circuit for {source_name}: {e}")
