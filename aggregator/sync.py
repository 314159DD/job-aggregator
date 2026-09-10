"""
aggregator/sync.py - Database sync with 3-layer deduplication.

Batch variant: all hash lookups are pre-fetched in 3 bulk IN queries,
then dedup is resolved entirely in Python memory. This cuts HTTP round
trips from O(3N) to O(3 + a few writes) regardless of batch size.

  Layer 1: external_id match       → UPDATE last_seen_at (same-source re-fetch)
  Layer 2: canonical_hash_strict   → UPDATE last_seen_at + track source (cross-source exact dupe)
  Layer 3: canonical_hash_fuzzy    → INSERT with duplicate_of set (near-dupe linked to canonical)
  No match                         → INSERT as new canonical record
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from aggregator.db import get_supabase, reset_client
from aggregator.models import JobRecord, SyncResult
from aggregator.translate import translate_titles

log = logging.getLogger(__name__)

_CHUNK_SIZE = 200  # max items per Supabase IN query (reduced from 500 to avoid 400s on large payloads)
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF = 2  # seconds, doubles each attempt


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunks(lst: list, size: int):
    """Yield successive chunks of `size` from lst."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def _load_excluded_companies() -> set:
    """Load excluded company names (lowercase) from Supabase."""
    try:
        sb = get_supabase()
        result = sb.table('excluded_companies').select('company_name').execute()
        return {r['company_name'].lower() for r in (result.data or [])}
    except Exception as e:
        log.warning(f"Could not load excluded_companies: {e}")
        return set()


def _job_to_row(job: JobRecord, now: str, triage_status: str) -> dict:
    """Convert JobRecord to Supabase jobs row dict."""
    return {
        'external_id': job.external_id,
        'url': job.url,
        'title': job.title,
        'company': job.company,
        'location': job.location,
        'description': job.description,
        'source': job.source,
        'fetched_at': now,
        'first_seen_at': now,
        'last_seen_at': now,
        'posted_at': job.posted_at,
        'is_active': True,
        'triage_status': triage_status,
        'remote_type': job.remote_type,
        'location_city': job.location_city,
        'location_country': job.location_country,
        'seniority': job.seniority,
        'employment_type': job.employment_type,
        'salary': job.salary,
        'salary_raw': job.salary_raw,
        'salary_min': job.salary_min,
        'salary_max': job.salary_max,
        'salary_currency': job.salary_currency,
        'salary_period': job.salary_period,
        'salary_confidence': job.salary_confidence,
        'canonical_hash_strict': job.canonical_hash_strict,
        'canonical_hash_fuzzy': job.canonical_hash_fuzzy,
        'description_fingerprint': job.description_fingerprint,
        'source_job_id': job.source_job_id,
        'title_de': job.title_de,
    }


def _bulk_fetch(sb, column: str, values: list, select_cols: str) -> dict:
    """Fetch rows matching any of `values` in `column`. Returns dict keyed by column value."""
    result: dict = {}
    for chunk in _chunks(values, _CHUNK_SIZE):
        rows = sb.table('jobs').select(select_cols).in_(column, chunk).execute()
        for r in (rows.data or []):
            result[r[column]] = r
    return result


def _update_canonical_sources(sb, canonical_source_merged: dict[int, list[str]], now: str) -> None:
    """Write pre-computed seen_on_sources to canonical rows.

    canonical_source_merged: {canonical_job_id: sorted_merged_sources_list}
    Sources are already merged during resolution - no extra fetch needed.
    """
    if not canonical_source_merged:
        return

    for canonical_id, merged_sources in canonical_source_merged.items():
        try:
            sb.table('jobs').update({
                'source_count': len(merged_sources),
                'seen_on_sources': merged_sources,
                'last_seen_at': now,
                'is_active': True,
            }).eq('id', canonical_id).execute()
        except Exception as e:
            log.warning(f"Could not update canonical #{canonical_id} source metadata: {e}")


def sync_to_db(jobs: list[JobRecord], source_name: str, dry_run: bool = False) -> SyncResult:
    """Insert new jobs, update existing ones. 3-layer dedup (batch variant).

    Pre-fetches all relevant hashes in 3 bulk queries, then resolves
    dedup entirely in Python - no per-job HTTP calls.
    """
    result = SyncResult(source=source_name, fetched=len(jobs))
    if not jobs:
        return result

    excluded = _load_excluded_companies()
    sb = get_supabase()
    now = _now()

    # ── Collect candidate values ──────────────────────────────────────────────
    ext_ids      = [j.external_id           for j in jobs if j.external_id]
    strict_hashes = [j.canonical_hash_strict for j in jobs if j.canonical_hash_strict]
    fuzzy_hashes  = [j.canonical_hash_fuzzy  for j in jobs if j.canonical_hash_fuzzy]

    # ── Bulk pre-fetch existing records (3 queries, with retry) ──────────────
    existing_by_ext_id: dict = {}
    existing_by_strict: dict = {}
    existing_by_fuzzy: dict  = {}
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            if ext_ids:
                existing_by_ext_id = _bulk_fetch(sb, 'external_id', ext_ids, 'id,external_id')
            if strict_hashes:
                existing_by_strict = _bulk_fetch(sb, 'canonical_hash_strict', strict_hashes,
                                                 'id,source,canonical_hash_strict,seen_on_sources')
            if fuzzy_hashes:
                existing_by_fuzzy = _bulk_fetch(sb, 'canonical_hash_fuzzy', fuzzy_hashes,
                                                'id,title,source,canonical_hash_fuzzy,duplicate_of,seen_on_sources')
            break  # success
        except Exception as e:
            log.warning(f"[{source_name}] Pre-fetch attempt {attempt}/{_RETRY_ATTEMPTS} failed: {e}")
            if attempt == _RETRY_ATTEMPTS:
                log.error(f"[{source_name}] Batch pre-fetch failed after {_RETRY_ATTEMPTS} attempts")
                raise
            wait = _RETRY_BACKOFF * (2 ** (attempt - 1))
            log.info(f"[{source_name}] Retrying in {wait}s with fresh connection...")
            time.sleep(wait)
            reset_client()
            sb = get_supabase()

    log.debug(
        f"[{source_name}] Pre-fetch complete: "
        f"{len(existing_by_ext_id)} ext_id hits, "
        f"{len(existing_by_strict)} strict hits, "
        f"{len(existing_by_fuzzy)} fuzzy hits"
    )

    # ── Translate job titles to German (batch, non-blocking) ──────────────────
    # Only translate jobs that are likely new (not already matched by ext_id)
    new_candidates = [j for j in jobs if j.external_id not in existing_by_ext_id]
    if new_candidates:
        translate_titles(new_candidates, source_name)

    # ── Resolve dedup in memory ───────────────────────────────────────────────
    ext_ids_to_bump:          list[str] = []
    strict_hashes_to_bump:    list[str] = []
    rows_to_insert:           list[dict] = []
    canonical_source_merged:  dict[int, list[str]] = {}  # canonical_id → merged sources list

    for job in jobs:
        try:
            # Layer 1: same external_id → just refresh last_seen_at
            if job.external_id in existing_by_ext_id:
                ext_ids_to_bump.append(job.external_id)
                result.updated += 1
                continue

            # Layer 2: same strict hash → cross-source exact dupe
            if job.canonical_hash_strict and job.canonical_hash_strict in existing_by_strict:
                existing_row = existing_by_strict[job.canonical_hash_strict]
                existing_source = existing_row.get('source', '?')
                log.info(
                    f"Cross-source dupe: '{job.title}' from {source_name} "
                    f"matches existing from {existing_source}"
                )
                strict_hashes_to_bump.append(job.canonical_hash_strict)
                # Merge seen_on_sources inline (no extra fetch needed)
                canonical_id = existing_row['id']
                current = set(existing_row.get('seen_on_sources') or [])
                if existing_source and existing_source != '?':
                    current.add(existing_source)
                current.add(source_name)
                canonical_source_merged[canonical_id] = sorted(current)
                result.updated += 1
                continue

            # Layer 3: fuzzy match → INSERT with duplicate_of linking
            if job.canonical_hash_fuzzy and job.canonical_hash_fuzzy in existing_by_fuzzy:
                existing_row = existing_by_fuzzy[job.canonical_hash_fuzzy]
                # Follow the chain: if existing is itself a dupe, point to its canonical
                canonical_id = existing_row.get('duplicate_of') or existing_row['id']
                existing_title = existing_row.get('title', '?')
                log.info(
                    f"Near-dupe linked: '{job.title}' from {source_name} "
                    f"→ canonical #{canonical_id} ('{existing_title}')"
                )
                triage_status = 'excluded' if (job.company or '').lower() in excluded else 'queued'
                row = _job_to_row(job, now, triage_status)
                row['duplicate_of'] = canonical_id
                rows_to_insert.append(row)
                # Merge seen_on_sources on canonical row
                current = set(existing_row.get('seen_on_sources') or [])
                existing_source = existing_row.get('source')
                if existing_source:
                    current.add(existing_source)
                current.add(source_name)
                canonical_source_merged[canonical_id] = sorted(current)
                result.linked += 1
                continue

            # No match → new canonical record
            triage_status = 'excluded' if (job.company or '').lower() in excluded else 'queued'
            row = _job_to_row(job, now, triage_status)
            row['seen_on_sources'] = [source_name]
            row['source_count'] = 1
            rows_to_insert.append(row)

        except Exception as e:
            log.error(f"Error resolving job '{job.external_id}': {e}")
            result.errors += 1

    if dry_run:
        result.new = len(rows_to_insert) - result.linked
        log.info(
            f"[{source_name}] DRY RUN - would insert {result.new} new + "
            f"{result.linked} linked, update {result.updated}, "
            f"skip {result.errors} errors"
        )
        return result

    # ── Batch writes ──────────────────────────────────────────────────────────
    # Layer 1 bumps
    for chunk in _chunks(ext_ids_to_bump, _CHUNK_SIZE):
        try:
            sb.table('jobs').update({'last_seen_at': now, 'is_active': True})\
              .in_('external_id', chunk).execute()
        except Exception as e:
            log.error(f"[{source_name}] Batch update (ext_id) error: {e}")

    # Layer 2 bumps
    for chunk in _chunks(strict_hashes_to_bump, _CHUNK_SIZE):
        try:
            sb.table('jobs').update({'last_seen_at': now, 'is_active': True})\
              .in_('canonical_hash_strict', chunk).execute()
        except Exception as e:
            log.error(f"[{source_name}] Batch update (strict_hash) error: {e}")

    # New job inserts (includes both canonical and linked-duplicate rows)
    for chunk in _chunks(rows_to_insert, _CHUNK_SIZE):
        try:
            sb.table('jobs').insert(chunk).execute()
            # Count new canonicals vs linked dupes
            new_in_chunk = sum(1 for r in chunk if r.get('duplicate_of') is None)
            result.new += new_in_chunk
        except Exception as e:
            log.error(f"[{source_name}] Batch insert error: {e}")
            result.errors += len(chunk)

    # Update source metadata on canonical rows
    _update_canonical_sources(sb, canonical_source_merged, now)

    return result


def mark_stale_jobs_inactive(days_threshold: int = 7) -> int:
    """Mark jobs not seen in the last N days as inactive. Returns count."""
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_threshold)).isoformat()
    try:
        result = sb.table('jobs').update({'is_active': False})\
            .lt('last_seen_at', cutoff).eq('is_active', True).execute()
        count = len(result.data or [])
        log.info(f"Marked {count} stale jobs inactive (not seen in {days_threshold}d)")
        return count
    except Exception as e:
        log.error(f"mark_stale_jobs_inactive error: {e}")
        return 0
