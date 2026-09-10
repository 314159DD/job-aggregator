"""
aggregator/snapshot.py - Weekly skill snapshot pipeline.

Scans jobs ingested in the past 7 days and aggregates:
  - Skill frequencies (extracted from descriptions)
  - Role type counts (seniority breakdown)
  - Salary ranges (min, max, median, p25, p75 per currency)
  - Location distribution (city-level counts)
  - Remote type counts
  - Employment type counts
  - Source counts

Results are stored in the skill_snapshots table (one row per week).
"""

import logging
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone

from aggregator.db import get_supabase
from aggregator.skills import extract_skills

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1000  # rows per page when fetching jobs
_SELECT_COLS = (
    "id,title,description,seniority,employment_type,remote_type,"
    "location_city,location_country,salary_min,salary_max,"
    "salary_currency,salary_period,source"
)


def _fetch_recent_jobs(period_start: str, period_end: str) -> list[dict]:
    """Fetch canonical (non-duplicate) jobs seen within the period."""
    sb = get_supabase()
    all_rows: list[dict] = []
    offset = 0

    while True:
        result = (
            sb.table("jobs")
            .select(_SELECT_COLS)
            .gte("last_seen_at", period_start)
            .lte("last_seen_at", period_end)
            .is_("duplicate_of", "null")
            .eq("is_active", True)
            .order("id")
            .range(offset, offset + _CHUNK_SIZE - 1)
            .execute()
        )
        rows = result.data or []
        all_rows.extend(rows)
        if len(rows) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE

    log.info(f"Fetched {len(all_rows)} canonical jobs for snapshot period")
    return all_rows


def _aggregate_skills(jobs: list[dict]) -> dict[str, int]:
    """Extract and count skills across all job descriptions."""
    counter: Counter = Counter()
    for job in jobs:
        skills = extract_skills(job.get("description") or "")
        counter.update(skills)
    # Return top 200 skills sorted by frequency
    return dict(counter.most_common(200))


def _aggregate_role_types(jobs: list[dict]) -> dict[str, int]:
    """Count seniority levels."""
    counter: Counter = Counter()
    for job in jobs:
        seniority = job.get("seniority") or "unknown"
        counter[seniority] += 1
    return dict(counter.most_common())


def _normalize_salary_to_annual(salary: int, period: str | None) -> int | None:
    """Convert salary to annual equivalent for comparable aggregation."""
    if not period or period == "year":
        return salary
    if period == "month":
        return salary * 12
    if period == "hour":
        return salary * 2080  # 40h/week * 52 weeks
    return salary


def _aggregate_salary_ranges(jobs: list[dict]) -> dict:
    """Compute salary statistics grouped by currency."""
    by_currency: dict[str, list[int]] = {}

    for job in jobs:
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        currency = job.get("salary_currency") or "EUR"
        period = job.get("salary_period")

        if salary_min is None and salary_max is None:
            continue

        # Use midpoint if both available, otherwise whichever exists
        if salary_min and salary_max:
            mid = (salary_min + salary_max) // 2
        else:
            mid = salary_min or salary_max

        annual = _normalize_salary_to_annual(mid, period)
        if annual is None or annual <= 0 or annual > 500000:
            continue  # skip implausible values

        by_currency.setdefault(currency, []).append(annual)

    result: dict = {}
    for currency, salaries in by_currency.items():
        salaries.sort()
        n = len(salaries)
        result[currency] = {
            "count": n,
            "min": salaries[0],
            "max": salaries[-1],
            "median": int(statistics.median(salaries)),
            "p25": salaries[n // 4] if n >= 4 else salaries[0],
            "p75": salaries[(3 * n) // 4] if n >= 4 else salaries[-1],
            "mean": int(statistics.mean(salaries)),
        }
    return result


def _aggregate_locations(jobs: list[dict]) -> dict[str, int]:
    """Count jobs by city (top 100)."""
    counter: Counter = Counter()
    for job in jobs:
        city = job.get("location_city")
        if city:
            counter[city] += 1
    return dict(counter.most_common(100))


def _aggregate_remote_types(jobs: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for job in jobs:
        remote = job.get("remote_type") or "unknown"
        counter[remote] += 1
    return dict(counter.most_common())


def _aggregate_employment_types(jobs: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for job in jobs:
        emp = job.get("employment_type") or "unknown"
        counter[emp] += 1
    return dict(counter.most_common())


def _aggregate_sources(jobs: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for job in jobs:
        source = job.get("source") or "unknown"
        counter[source] += 1
    return dict(counter.most_common())


def run_snapshot(dry_run: bool = False) -> dict:
    """Run the weekly skill snapshot pipeline.

    Scans jobs from the past 7 days, aggregates metrics, and writes
    a single row to the skill_snapshots table.

    Returns the snapshot dict (for logging / testing).
    """
    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)
    snapshot_date = now.date().isoformat()

    log.info(
        f"Running skill snapshot for {period_start.date()} to {period_end.date()}"
    )

    jobs = _fetch_recent_jobs(period_start.isoformat(), period_end.isoformat())

    if not jobs:
        log.warning("No jobs found for snapshot period - skipping")
        return {"jobs_analyzed": 0, "snapshot_date": snapshot_date}

    log.info(f"Aggregating metrics from {len(jobs)} jobs...")

    snapshot = {
        "snapshot_date": snapshot_date,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "jobs_analyzed": len(jobs),
        "skill_frequencies": _aggregate_skills(jobs),
        "role_type_counts": _aggregate_role_types(jobs),
        "salary_ranges": _aggregate_salary_ranges(jobs),
        "location_distribution": _aggregate_locations(jobs),
        "remote_type_counts": _aggregate_remote_types(jobs),
        "employment_type_counts": _aggregate_employment_types(jobs),
        "source_counts": _aggregate_sources(jobs),
    }

    # Log summary
    n_skills = len(snapshot["skill_frequencies"])
    top_skills = list(snapshot["skill_frequencies"].items())[:5]
    log.info(f"Extracted {n_skills} unique skills. Top 5: {top_skills}")
    log.info(f"Role types: {snapshot['role_type_counts']}")
    log.info(f"Remote types: {snapshot['remote_type_counts']}")

    if dry_run:
        log.info("DRY RUN - snapshot not written to DB")
        return snapshot

    # Upsert to skill_snapshots (unique on snapshot_date)
    sb = get_supabase()
    try:
        sb.table("skill_snapshots").upsert(
            snapshot, on_conflict="snapshot_date"
        ).execute()
        log.info(f"Snapshot written for {snapshot_date}")
    except Exception as e:
        log.error(f"Failed to write snapshot: {e}")
        raise

    return snapshot
