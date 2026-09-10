"""
aggregator/orchestrator.py - Source runner & coordinator.

Delegates to: sync.py (DB), health.py (tracking), search_terms.py (profile terms).
This file is ONLY the coordination loop. Max 150 lines.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from aggregator import health as source_health
from aggregator import run_log
from aggregator.logging_config import get_logger
from aggregator.models import SyncResult
from aggregator.search_terms import get_search_terms_all_users
from aggregator.sync import sync_to_db
from sources import get_enabled_sources, get_source

log = get_logger(__name__)


def _run_source(source, search_terms: list, locations: list, dry_run: bool = False) -> SyncResult:
    """Run a single source: fetch → normalise → sync. Returns SyncResult."""
    start = time.time()
    error_msg = None
    success = False
    try:
        raw_jobs = source.fetch(search_terms=search_terms, locations=locations)
        normalised = source.normalise(raw_jobs)
        result = sync_to_db(normalised, source.name, dry_run=dry_run)
        result.fetched = len(raw_jobs)
        success = result.errors == 0
    except Exception as exc:
        log.error(f"[{source.name}] Failed: {exc}")
        result = SyncResult(source=source.name, errors=1)
        error_msg = str(exc)
    result.duration_seconds = round(time.time() - start, 2)

    if not dry_run:
        source_health.update_health(
            source.name,
            success=success,
            fetched=result.fetched,
            new=result.new,
            error=error_msg,
        )
    return result


def run_all(dry_run: bool = False) -> dict[str, SyncResult]:
    """Run all enabled sources. Per-source errors don't stop other sources."""
    sources = get_enabled_sources()
    if not sources:
        log.warning("No enabled sources found")
        return {}

    terms = get_search_terms_all_users()
    search_terms = terms["search_terms"]
    locations = terms["locations"]

    log.info(f"Running {len(sources)} source(s): {[s.name for s in sources]}")
    run_log.start_run(is_dry_run=dry_run, source_names=[s.name for s in sources])

    results: dict[str, SyncResult] = {}

    # Pre-filter: skip circuit-open and throttled sources before submitting to pool
    runnable = []
    for source in sources:
        if source_health.is_circuit_open(source.name):
            health = source_health.get_health(source.name)
            failures = health.get("consecutive_failures", 0) if health else 0
            log.warning(f"[{source.name}] Skipping - circuit open ({failures} consecutive failures)")
            run_log.log_source_skipped(source.name, f"circuit open ({failures} failures)")
            continue

        if getattr(source, 'min_interval_hours', 0) > 0:
            health = source_health.get_health(source.name)
            last_run = health.get('last_run_at') if health else None
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                    hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                    if hours_since < source.min_interval_hours:
                        next_in = source.min_interval_hours - hours_since
                        log.info(f"[{source.name}] Skipping - ran {hours_since:.1f}h ago (min interval {source.min_interval_hours}h, next in {next_in:.1f}h)")
                        run_log.log_source_skipped(source.name, f"min interval not reached ({next_in:.1f}h remaining)")
                        continue
                except (ValueError, TypeError):
                    pass

        runnable.append(source)

    # Run sources concurrently (I/O-bound HTTP fetches)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_run_source, source, search_terms, locations, dry_run): source
            for source in runnable
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                log.error(f"[{source.name}] Thread failed: {exc}")
                result = SyncResult(source=source.name, errors=1)
            results[source.name] = result
            run_log.log_source_done(source.name, result)
            log.info(
                f"[{source.name}] Done - fetched={result.fetched} "
                f"new={result.new} updated={result.updated} "
                f"linked={result.linked} errors={result.errors} "
                f"({result.duration_seconds}s)"
            )

    log_run_summary(results, dry_run=dry_run)
    summary = {
        'total_fetched': sum(r.fetched for r in results.values()),
        'total_new': sum(r.new for r in results.values()),
        'total_updated': sum(r.updated for r in results.values()),
        'total_linked': sum(r.linked for r in results.values()),
        'total_errors': sum(r.errors for r in results.values()),
    }
    run_log.finish_run(
        status='failed' if summary['total_errors'] > max(len(results) // 2, 1) else 'completed',
        summary=summary,
    )

    # Auto-discovery: scan newly ingested job URLs for ATS slugs (free, fast)
    if not dry_run:
        try:
            from discovery.self_discover import discover_from_existing_jobs
            disc = discover_from_existing_jobs()
            total_disc = sum(disc.values())
            if total_disc:
                log.info(f"Auto-discovery: registered {total_disc} new companies - {disc}")
        except Exception as e:
            log.warning(f"Auto-discovery failed (non-fatal): {e}")

        # Write last-run timestamp for Docker health check
        try:
            import os
            lock_dir = os.path.dirname(os.environ.get("LOCK_FILE", "/tmp/aggregator.lock"))
            with open(os.path.join(lock_dir, "aggregator.last_run"), "w") as f:
                f.write(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass

    return results


def run_single(source_name: str, dry_run: bool = False) -> dict[str, SyncResult]:
    """Run a single source by name (bypasses circuit breaker)."""
    source = get_source(source_name)
    terms = get_search_terms_all_users()
    run_log.start_run(is_dry_run=dry_run, source_names=[source.name])
    log.info(f"[{source.name}] Starting (single-source run)...")
    run_log.log_source_start(source.name)
    result = _run_source(source, terms["search_terms"], terms["locations"], dry_run=dry_run)
    run_log.log_source_done(source.name, result)
    results = {source.name: result}
    log_run_summary(results, dry_run=dry_run)
    run_log.finish_run(
        status='failed' if result.errors > 0 else 'completed',
        summary={'total_fetched': result.fetched, 'total_new': result.new,
                 'total_updated': result.updated, 'total_linked': result.linked,
                 'total_errors': result.errors},
    )
    return results


def log_run_summary(results: dict[str, SyncResult], dry_run: bool = False) -> None:
    """Print a summary table of all source results."""
    mode = " [DRY RUN]" if dry_run else ""
    print(f"\n{'='*60}")
    print(f"  Job Aggregator - Run Summary{mode}")
    print(f"{'='*60}")
    print(f"  {'Source':<20} {'Fetched':>8} {'New':>6} {'Updated':>8} {'Linked':>7} {'Errors':>7} {'Time':>6}")
    print(f"  {'-'*65}")
    total_fetched = total_new = total_updated = total_linked = total_errors = 0
    for name, r in results.items():
        print(f"  {name:<20} {r.fetched:>8} {r.new:>6} {r.updated:>8} {r.linked:>7} {r.errors:>7} {r.duration_seconds:>5.1f}s")
        total_fetched += r.fetched
        total_new += r.new
        total_updated += r.updated
        total_linked += r.linked
        total_errors += r.errors
    print(f"  {'-'*65}")
    print(f"  {'TOTAL':<20} {total_fetched:>8} {total_new:>6} {total_updated:>8} {total_linked:>7} {total_errors:>7}")
    print(f"{'='*60}\n")
