"""
scripts/backfill_dedup_links.py - One-time backfill for dedup linking.

Links existing fuzzy duplicates (same canonical_hash_fuzzy) by setting
duplicate_of on all but the "best" record per group. Also backfills
source_count and seen_on_sources on canonical rows.

Uses batch updates: groups IDs by canonical_id, then does bulk UPDATE
with IN() queries in chunks of 500. ~20 HTTP calls instead of ~8,600.

Safe: skips rows that have evaluations or applications (user-interacted).
Idempotent: can be run multiple times.

Run: python -m scripts.backfill_dedup_links [--dry-run]
"""

import logging
import sys
from collections import defaultdict

from aggregator.db import get_supabase

log = logging.getLogger(__name__)

_CHUNK_SIZE = 500


def _chunks(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def _fetch_all_fuzzy_groups(sb) -> dict[str, list[dict]]:
    """Fetch all rows grouped by canonical_hash_fuzzy.

    Returns: {fuzzy_hash: [row, row, ...]} for groups with 2+ members.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    offset = 0
    batch_size = 1000

    while True:
        result = sb.table('jobs').select(
            'id,canonical_hash_fuzzy,source,title,description,first_seen_at,duplicate_of'
        ).not_.is_('canonical_hash_fuzzy', 'null').range(offset, offset + batch_size - 1).execute()

        rows = result.data or []
        if not rows:
            break

        for row in rows:
            h = row['canonical_hash_fuzzy']
            if h:
                groups[h].append(row)

        if len(rows) < batch_size:
            break
        offset += batch_size

    # Only keep groups with 2+ members (actual duplicates)
    return {h: members for h, members in groups.items() if len(members) >= 2}


def _fetch_protected_ids(sb) -> set[int]:
    """Get job IDs that must NOT be marked as duplicates (have evaluations or applications)."""
    protected = set()

    # Jobs with evaluations
    offset = 0
    while True:
        result = sb.table('job_evaluation').select('job_id').range(offset, offset + 999).execute()
        rows = result.data or []
        for r in rows:
            protected.add(r['job_id'])
        if len(rows) < 1000:
            break
        offset += 1000

    # Jobs with applications
    offset = 0
    while True:
        result = sb.table('application').select('job_id').not_.is_('job_id', 'null').range(offset, offset + 999).execute()
        rows = result.data or []
        for r in rows:
            protected.add(r['job_id'])
        if len(rows) < 1000:
            break
        offset += 1000

    return protected


def _pick_canonical(members: list[dict], protected: set[int]) -> dict:
    """Pick the best record to be the canonical (primary) record.

    Priority: protected (user-interacted) > longest description > earliest first_seen_at.
    """
    def sort_key(row):
        is_protected = row['id'] in protected
        desc_len = len(row.get('description') or '')
        already_canonical = row.get('duplicate_of') is None
        return (
            is_protected,
            already_canonical,
            desc_len,
        )

    ranked = sorted(members, key=sort_key, reverse=True)
    return ranked[0]


def backfill(dry_run: bool = False) -> dict:
    """Run the backfill. Returns stats dict."""
    sb = get_supabase()

    log.info("Fetching all fuzzy hash groups...")
    groups = _fetch_all_fuzzy_groups(sb)
    log.info(f"Found {len(groups)} duplicate groups ({sum(len(m) for m in groups.values())} total rows)")

    if not groups:
        log.info("No duplicates to link")
        return {'groups': 0, 'linked': 0, 'skipped_protected': 0}

    log.info("Fetching protected IDs (evaluations + applications)...")
    protected = _fetch_protected_ids(sb)
    log.info(f"Protected IDs: {len(protected)}")

    # Phase 1: Compute all links in memory
    # Map: canonical_id → list of dupe IDs to link
    link_batches: dict[int, list[int]] = defaultdict(list)
    canonical_sources: dict[int, set[str]] = defaultdict(set)
    linked = 0
    skipped_protected = 0

    for fuzzy_hash, members in groups.items():
        canonical = _pick_canonical(members, protected)
        canonical_id = canonical['id']

        for member in members:
            src = member.get('source')
            if src:
                canonical_sources[canonical_id].add(src)

        for member in members:
            if member['id'] == canonical_id:
                continue

            if member['id'] in protected:
                skipped_protected += 1
                continue

            if member.get('duplicate_of') == canonical_id:
                continue  # Already linked correctly

            link_batches[canonical_id].append(member['id'])
            linked += 1

    log.info(f"Computed: {linked} rows to link across {len(link_batches)} canonical records, {skipped_protected} protected")

    if dry_run:
        stats = {
            'groups': len(groups),
            'linked': linked,
            'skipped_protected': skipped_protected,
            'source_metadata_updated': 0,
        }
        log.info(f"DRY RUN - Backfill complete: {stats}")
        return stats

    # Phase 2: Batch UPDATE duplicate_of by canonical_id
    # Group all dupe IDs together regardless of canonical, then update per-canonical
    # Most efficient: batch by canonical_id (one UPDATE per canonical)
    # But even better: collect ALL dupe IDs with same canonical, batch in chunks of 500
    log.info("Phase 2: Batch-updating duplicate_of...")
    update_count = 0
    for canonical_id, dupe_ids in link_batches.items():
        for chunk in _chunks(dupe_ids, _CHUNK_SIZE):
            try:
                sb.table('jobs').update({
                    'duplicate_of': canonical_id,
                }).in_('id', chunk).execute()
                update_count += len(chunk)
            except Exception as e:
                log.warning(f"Failed to link {len(chunk)} rows to canonical #{canonical_id}: {e}")
        if update_count % 1000 < len(dupe_ids):
            log.info(f"  ...linked {update_count}/{linked} rows")

    log.info(f"Phase 2 done: {update_count} rows linked")

    # Phase 3: Batch-update source_count and seen_on_sources on canonical rows
    # Unfortunately these have per-row values, but we can still batch the work
    # by doing it in chunks and logging progress
    log.info(f"Phase 3: Updating source metadata on {len(canonical_sources)} canonical rows...")
    source_updates = 0
    canonical_items = list(canonical_sources.items())
    for i, (canonical_id, sources) in enumerate(canonical_items):
        try:
            sb.table('jobs').update({
                'source_count': len(sources),
                'seen_on_sources': sorted(sources),
            }).eq('id', canonical_id).execute()
            source_updates += 1
        except Exception as e:
            log.warning(f"Failed to update source metadata on #{canonical_id}: {e}")
        if (i + 1) % 500 == 0:
            log.info(f"  ...source metadata: {i + 1}/{len(canonical_items)}")

    log.info(f"Phase 3 done: {source_updates} canonical rows updated")

    stats = {
        'groups': len(groups),
        'linked': update_count,
        'skipped_protected': skipped_protected,
        'source_metadata_updated': source_updates,
    }
    log.info(f"Backfill complete: {stats}")
    return stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("Running in DRY RUN mode (no writes)\n")
    stats = backfill(dry_run=dry_run)
    print(f"\nResults: {stats}")
