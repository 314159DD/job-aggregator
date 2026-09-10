"""
scripts/health_report.py - Print source health summary from Supabase.

Usage:
    python scripts/health_report.py
    python -m aggregator --health-report

Exit code: 0 if all enabled sources are healthy, 1 if any are unhealthy or missing.
"""

import sys

from dotenv import load_dotenv

load_dotenv()


def print_health_report() -> int:
    """Print formatted source health table. Returns 0 (all OK) or 1 (issues found)."""
    from aggregator import config
    from aggregator.health import get_all_health

    try:
        config.validate()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    records = get_all_health()
    if not records:
        print("No health data found. Run the aggregator first to populate records.")
        return 1

    health_by_name = {r["source_name"]: r for r in records}

    # All configured sources + any extras in DB
    all_names = sorted(set(config.SOURCES.keys()) | set(health_by_name.keys()))

    def fmt_time(ts: str | None) -> str:
        if not ts:
            return "-"
        try:
            return ts[:16].replace("T", " ")
        except Exception:
            return "-"

    print(f"\n{'Source':<16} {'Status':<14} {'Last Run':<17} {'Fetched':>7}  {'New':>5}  {'Failures':>8}")
    print("─" * 72)

    all_healthy = True
    for name in all_names:
        h = health_by_name.get(name)
        cfg = config.SOURCES.get(name, {})
        cfg_enabled = cfg.get("enabled", True)

        if h is None:
            status = "⏸ Never run" if cfg_enabled else "⏸ Disabled"
            print(f"{name:<16} {status:<14} {'-':<17} {'-':>7}  {'-':>5}  {'-':>8}")
            if cfg_enabled:
                all_healthy = False
            continue

        db_enabled = h.get("is_enabled", True)
        is_healthy = h.get("is_healthy", True)
        failures = h.get("consecutive_failures", 0)

        if not db_enabled:
            status = "⏸ Disabled"
        elif not cfg_enabled:
            status = "⏸ Cfg off"
        elif failures >= 3:
            status = "🔴 Circuit"
            all_healthy = False
        elif not is_healthy:
            status = "🟡 Degraded"
            all_healthy = False
        else:
            status = "✅ OK"

        last_run = fmt_time(h.get("last_run_at"))
        fetched = h.get("jobs_fetched_last_run", 0)
        new = h.get("jobs_new_last_run", 0)

        print(f"{name:<16} {status:<14} {last_run:<17} {fetched:>7}  {new:>5}  {failures:>8}")

    print()

    # Discovery / Registry stats
    try:
        from aggregator.db import get_supabase
        sb = get_supabase()
        reg = sb.table('company_registry').select('ats_type, is_active').execute()
        if reg.data:
            by_ats: dict[str, dict] = {}
            for row in reg.data:
                ats = row.get('ats_type', '?')
                active = row.get('is_active', True)
                if ats not in by_ats:
                    by_ats[ats] = {'active': 0, 'inactive': 0}
                by_ats[ats]['active' if active else 'inactive'] += 1

            total_active = sum(v['active'] for v in by_ats.values())
            total_inactive = sum(v['inactive'] for v in by_ats.values())
            total = total_active + total_inactive

            print(f"{'ATS Registry':<16} {'Active':>7}  {'Inactive':>8}  {'Total':>6}")
            print("─" * 42)
            for ats in sorted(by_ats.keys()):
                v = by_ats[ats]
                print(f"  {ats:<14} {v['active']:>7}  {v['inactive']:>8}  {v['active']+v['inactive']:>6}")
            print(f"  {'TOTAL':<14} {total_active:>7}  {total_inactive:>8}  {total:>6}")
            print()
    except Exception:
        pass  # Non-fatal - registry stats are informational

    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(print_health_report())
