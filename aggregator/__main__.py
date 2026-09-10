"""
aggregator/__main__.py - CLI entry point.

Usage:
    python -m aggregator                         # Run all enabled sources
    python -m aggregator --source arbeitsamt     # Run single source
    python -m aggregator --dry-run               # Fetch but don't write to DB
    python -m aggregator --freshness-check       # Mark stale jobs inactive
    python -m aggregator --verbose               # Set log level to DEBUG
    python -m aggregator --skill-snapshot        # Run weekly skill snapshot pipeline
    python -m aggregator --discover              # Run full discovery suite (self-discover + sitemap + optional dork)
    python -m aggregator --health-report         # Print source health table and exit
    python -m aggregator --list-sources          # List all registered sources and exit
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import sentry_sdk

sentry_dsn = os.environ.get('SENTRY_DSN')
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.environ.get('APP_ENV', 'development'),
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

from aggregator import config
from aggregator.logging_config import get_logger, setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="aggregator",
        description="Job Aggregator - fetch, normalise, and sync job listings",
    )
    parser.add_argument("--source", metavar="NAME", help="Run a single source by name")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't write to DB")
    parser.add_argument("--freshness-check", action="store_true", help="Mark stale jobs as inactive")
    parser.add_argument("--verbose", action="store_true", help="Set log level to DEBUG")
    parser.add_argument("--health-report", action="store_true", help="Print source health table and exit")
    parser.add_argument("--list-sources", action="store_true", help="List all registered sources and exit")
    parser.add_argument("--skill-snapshot", action="store_true", help="Run weekly skill snapshot pipeline and exit")
    parser.add_argument("--discover", action="store_true", help="Run full discovery suite (self-discover + sitemap scan) and exit")
    parser.add_argument("--market-snapshot", action="store_true", help="Run weekly market snapshot pipeline and exit")
    parser.add_argument("--market-snapshot-backfill", action="store_true", help="Force backfill last 12 weeks of market snapshots")
    args = parser.parse_args()

    dry_run = args.dry_run or config.DRY_RUN
    setup_logging(level="DEBUG" if args.verbose else None)
    log = get_logger("aggregator.__main__")

    # --list-sources: no DB needed
    if args.list_sources:
        from sources import get_all_sources
        sources = sorted(get_all_sources(), key=lambda s: s.name)
        print(f"\n{'Name':<20} {'Type':<10} {'Auth':<12} {'Rate/min':>8}  {'Enabled'}")
        print("-" * 60)
        for src in sources:
            cfg = config.get_source_config(src.name)
            enabled = "✓" if cfg.get("enabled", src.enabled) else "✗"
            rate = cfg.get("rate_limit", src.rate_limit)
            print(f"{src.name:<20} {src.source_type:<10} {src.auth_type:<12} {rate:>8}  {enabled}")
        print()
        return 0

    try:
        config.validate()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # --health-report: DB needed but no run
    if args.health_report:
        from scripts.health_report import print_health_report
        return print_health_report()

    # --skill-snapshot: run weekly skill snapshot pipeline then exit
    if args.skill_snapshot:
        from aggregator.snapshot import run_snapshot
        snapshot = run_snapshot(dry_run=dry_run)
        log.info(f"Skill snapshot complete: {snapshot.get('jobs_analyzed', 0)} jobs analyzed")
        return 0

    # --market-snapshot: run weekly market snapshot pipeline then exit
    if args.market_snapshot or args.market_snapshot_backfill:
        from aggregator.market_snapshot import run_market_snapshot
        force = args.market_snapshot_backfill
        snapshots = run_market_snapshot(dry_run=dry_run, force=force)
        log.info(f"Market snapshot complete: {len(snapshots)} weeks computed")
        return 0

    # --discover: run full discovery suite then exit
    if args.discover:
        from discovery.self_discover import discover_from_existing_jobs
        from discovery.sitemap_scan import discover_from_sitemaps

        log.info("Running full discovery suite...")

        # Phase 1: Self-discovery (scan existing job URLs - fast, free)
        log.info("Phase 1: Self-discovery from existing job URLs")
        self_disc = discover_from_existing_jobs()
        self_total = sum(self_disc.values())
        log.info(f"  Self-discovery: {self_total} companies - {self_disc}")

        # Phase 2: Sitemap scanning (crawl company sitemaps - slower, free)
        log.info("Phase 2: Sitemap scanning")
        sitemap_disc = discover_from_sitemaps()
        sitemap_total = sum(sitemap_disc.values())
        log.info(f"  Sitemap scan: {sitemap_total} companies - {sitemap_disc}")

        # Phase 3: Google dorking (only if Serper key available and credits remain)
        try:
            from aggregator.config import SERPER_API_KEY
            if SERPER_API_KEY:
                log.info("Phase 3: Google dorking (Serper API)")
                from discovery.google_dork import discover_all as dork_all
                dork_disc = dork_all()
                dork_total = sum(dork_disc.values())
                log.info(f"  Google dork: {dork_total} companies - {dork_disc}")
            else:
                log.info("Phase 3: Skipped (no SERPER_API_KEY)")
        except (ImportError, AttributeError):
            log.info("Phase 3: Skipped (no SERPER_API_KEY)")

        grand_total = self_total + sitemap_total
        log.info(f"Discovery complete: {grand_total} companies registered")
        return 0

    # --freshness-check: mark stale jobs inactive then exit
    if args.freshness_check:
        from aggregator.sync import mark_stale_jobs_inactive
        count = mark_stale_jobs_inactive()
        log.info(f"Marked {count} stale jobs as inactive")
        return 0

    # Normal run: acquire lock first
    from aggregator.lock import acquire_lock, release_lock
    if not acquire_lock():
        try:
            with open(config.LOCK_FILE) as f:
                pid = f.read().strip()
        except Exception:
            pid = "unknown"
        print(f"Another aggregator run is in progress (PID {pid}). Exiting.")
        return 0

    from aggregator.orchestrator import run_all, run_single
    try:
        if args.source:
            run_single(args.source, dry_run=dry_run)
        else:
            run_all(dry_run=dry_run)
        return 0
    except KeyError as e:
        print(f"ERROR: Unknown source {e}", file=sys.stderr)
        return 1
    except Exception as e:
        log.error(f"Aggregator run failed: {e}", exc_info=True)
        return 1
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
