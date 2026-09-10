"""
aggregator/run_log.py - Live run progress tracking via Supabase.

Writes to `aggregator_runs` table so a consuming application's debug dashboard
can display live progress without needing terminal access.

All writes are best-effort: failures are logged but never raise.

Table required (create once in Supabase SQL editor):

    CREATE TABLE IF NOT EXISTS aggregator_runs (
        id          BIGSERIAL PRIMARY KEY,
        run_id      TEXT UNIQUE NOT NULL,
        started_at  TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        is_dry_run  BOOLEAN DEFAULT FALSE,
        status      TEXT DEFAULT 'running',
        sources_total   INTEGER DEFAULT 0,
        sources_done    INTEGER DEFAULT 0,
        current_source  TEXT,
        results     JSONB DEFAULT '{}',
        summary     JSONB,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
"""

import threading
import uuid
from datetime import datetime, timezone

from aggregator.logging_config import get_logger

log = get_logger(__name__)

_run_id: str | None = None
_results: dict = {}
_lock = threading.Lock()


def start_run(is_dry_run: bool, source_names: list) -> str:
    """Create a new run record in Supabase. Returns the run_id."""
    global _run_id, _results
    _run_id = str(uuid.uuid4())[:12]
    _results = {}
    try:
        from aggregator.db import get_supabase
        get_supabase().table('aggregator_runs').insert({
            'run_id': _run_id,
            'started_at': _now(),
            'is_dry_run': is_dry_run,
            'status': 'running',
            'sources_total': len(source_names),
            'sources_done': 0,
            'current_source': source_names[0] if source_names else None,
            'results': {},
        }).execute()
    except Exception as e:
        log.warning(f"run_log.start_run failed (table may not exist yet): {e}")
    return _run_id


def log_source_start(source_name: str) -> None:
    """Mark a source as currently processing."""
    if not _run_id:
        return
    _update({'current_source': source_name})


def log_source_done(source_name: str, result) -> None:
    """Record a completed source result."""
    if not _run_id:
        return
    with _lock:
        _results[source_name] = {
            'fetched': result.fetched,
            'new': result.new,
            'updated': result.updated,
            'linked': result.linked,
            'errors': result.errors,
            'duration': result.duration_seconds,
            'status': 'error' if result.errors > 0 else 'ok',
        }
        snapshot = {
            'sources_done': len(_results),
            'current_source': None,
            'results': dict(_results),
        }
    _update(snapshot)


def log_source_skipped(source_name: str, reason: str) -> None:
    """Record a skipped source (circuit open, disabled, etc.)."""
    if not _run_id:
        return
    with _lock:
        _results[source_name] = {'status': 'skipped', 'reason': reason}
        snapshot = {
            'sources_done': len(_results),
            'results': dict(_results),
        }
    _update(snapshot)


def finish_run(status: str = 'completed', summary: dict | None = None) -> None:
    """Mark the run as finished with final summary."""
    if not _run_id:
        return
    _update({
        'status': status,
        'completed_at': _now(),
        'current_source': None,
        'results': _results,
        'summary': summary,
    })


def _update(data: dict) -> None:
    """Write a partial update to the current run record."""
    if not _run_id:
        return
    try:
        from aggregator.db import get_supabase
        get_supabase().table('aggregator_runs').update(data).eq('run_id', _run_id).execute()
    except Exception as e:
        log.warning(f"run_log._update failed: {e}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
