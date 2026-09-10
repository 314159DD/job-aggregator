"""
aggregator/market_snapshot.py - Weekly market snapshot pipeline.

Pre-computes market statistics from raw job data so the Career Radar
market-signals endpoint can serve them without expensive queries.

Produces one row per ISO week in the market_snapshots table:
  - total_jobs_ingested
  - jobs_by_role      (title keyword buckets)
  - jobs_by_location  (city-level counts)
  - top_skills        (with pct_change vs prior week)
  - new_companies     (first seen this week)
  - salary_signals    (avg, median, p75 per currency)

Idempotent: re-running the same week overwrites via UNIQUE(week_start).
First run backfills the last 12 weeks.
"""

import logging
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone

from aggregator.db import get_supabase
from aggregator.skills import extract_skills

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1000
_SELECT_COLS = (
    "id,title,description,company_name,location_city,"
    "salary_min,salary_max,salary_currency,salary_period,"
    "source,created_at"
)
_BACKFILL_WEEKS = 12


def _monday_of(dt: datetime) -> str:
    """Return the ISO Monday (week_start) for a given datetime as YYYY-MM-DD."""
    monday = dt.date() - timedelta(days=dt.weekday())
    return monday.isoformat()


def _fetch_jobs_for_week(week_start: str, week_end: str) -> list[dict]:
    """Fetch canonical jobs created within [week_start, week_end)."""
    sb = get_supabase()
    all_rows: list[dict] = []
    offset = 0

    while True:
        result = (
            sb.table("jobs")
            .select(_SELECT_COLS)
            .gte("created_at", week_start)
            .lt("created_at", week_end)
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

    return all_rows


def _fetch_known_companies_before(week_start: str) -> set[str]:
    """Get distinct company names seen before week_start (for new-company detection)."""
    sb = get_supabase()
    companies: set[str] = set()
    offset = 0

    while True:
        result = (
            sb.table("jobs")
            .select("company_name")
            .lt("created_at", week_start)
            .is_("duplicate_of", "null")
            .order("company_name")
            .range(offset, offset + _CHUNK_SIZE - 1)
            .execute()
        )
        rows = result.data or []
        for row in rows:
            name = row.get("company_name")
            if name:
                companies.add(name)
        if len(rows) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE

    return companies


def _aggregate_roles(jobs: list[dict]) -> dict[str, int]:
    """Bucket jobs by title keywords into role categories."""
    counter: Counter = Counter()
    for job in jobs:
        title = (job.get("title") or "").lower()
        # Simple keyword bucketing
        if any(kw in title for kw in ("backend", "back-end", "back end")):
            counter["Backend"] += 1
        elif any(kw in title for kw in ("frontend", "front-end", "front end")):
            counter["Frontend"] += 1
        elif any(kw in title for kw in ("fullstack", "full-stack", "full stack")):
            counter["Fullstack"] += 1
        elif any(kw in title for kw in ("devops", "sre", "infrastructure", "platform")):
            counter["DevOps/SRE"] += 1
        elif any(kw in title for kw in ("data engineer", "data scientist", "data analyst", "machine learning", "ml engineer", "ai ")):
            counter["Data/ML"] += 1
        elif any(kw in title for kw in ("mobile", "android", "ios")):
            counter["Mobile"] += 1
        elif any(kw in title for kw in ("qa", "test", "quality")):
            counter["QA/Testing"] += 1
        elif any(kw in title for kw in ("security", "cybersecurity", "infosec")):
            counter["Security"] += 1
        elif any(kw in title for kw in ("manager", "lead", "head of", "director", "vp ")):
            counter["Management"] += 1
        elif any(kw in title for kw in ("designer", "ux", "ui")):
            counter["Design"] += 1
        else:
            counter["Other"] += 1
    return dict(counter.most_common())


def _aggregate_locations(jobs: list[dict]) -> dict[str, int]:
    """Count jobs by city (top 50)."""
    counter: Counter = Counter()
    for job in jobs:
        city = job.get("location_city")
        if city:
            counter[city] += 1
    return dict(counter.most_common(50))


def _aggregate_skills(jobs: list[dict]) -> dict[str, int]:
    """Extract and count skills from descriptions."""
    counter: Counter = Counter()
    for job in jobs:
        skills = extract_skills(job.get("description") or "")
        counter.update(skills)
    return dict(counter.most_common(100))


def _normalize_salary_to_annual(salary: int, period: str | None) -> int | None:
    """Convert salary to annual equivalent."""
    if not period or period == "year":
        return salary
    if period == "month":
        return salary * 12
    if period == "hour":
        return salary * 2080
    return salary


def _aggregate_salary_signals(jobs: list[dict]) -> dict:
    """Compute salary statistics grouped by currency."""
    by_currency: dict[str, list[int]] = {}

    for job in jobs:
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        currency = job.get("salary_currency") or "EUR"
        period = job.get("salary_period")

        if salary_min is None and salary_max is None:
            continue

        if salary_min and salary_max:
            mid = (salary_min + salary_max) // 2
        else:
            mid = salary_min or salary_max

        annual = _normalize_salary_to_annual(mid, period)
        if annual is None or annual <= 0 or annual > 500000:
            continue

        by_currency.setdefault(currency, []).append(annual)

    result: dict = {}
    for currency, salaries in by_currency.items():
        salaries.sort()
        n = len(salaries)
        result[currency] = {
            "count": n,
            "avg": int(statistics.mean(salaries)),
            "median": int(statistics.median(salaries)),
            "p75": salaries[(3 * n) // 4] if n >= 4 else salaries[-1],
        }
    return result


def _compute_pct_change(current: dict[str, int], previous: dict[str, int] | None) -> list[dict]:
    """Build top_skills list with pct_change relative to previous week."""
    result = []
    for skill, count in sorted(current.items(), key=lambda x: -x[1]):
        prev_count = (previous or {}).get(skill, 0)
        if prev_count > 0:
            pct_change = round((count - prev_count) / prev_count, 2)
        else:
            pct_change = None  # new skill, no prior data
        result.append({
            "skill": skill,
            "count": count,
            "pct_change": pct_change,
        })
    return result


def _build_snapshot_for_week(
    week_start_date: str,
    previous_skills: dict[str, int] | None = None,
) -> dict | None:
    """Build a single week's market snapshot.

    Returns the snapshot dict or None if no jobs found.
    Also returns raw skill counts for chaining pct_change to next week.
    """
    from datetime import date
    from datetime import timedelta as td

    ws = date.fromisoformat(week_start_date)
    we = ws + td(days=7)
    week_end_date = we.isoformat()

    log.info(f"Building market snapshot for week {week_start_date}")
    jobs = _fetch_jobs_for_week(week_start_date, week_end_date)

    if not jobs:
        log.info(f"  No jobs for week {week_start_date} - skipping")
        return None

    # Aggregations
    roles = _aggregate_roles(jobs)
    locations = _aggregate_locations(jobs)
    raw_skills = _aggregate_skills(jobs)
    salary = _aggregate_salary_signals(jobs)

    # New companies (first seen this week)
    known = _fetch_known_companies_before(week_start_date)
    this_week_companies = {
        job.get("company_name")
        for job in jobs
        if job.get("company_name")
    }
    new_companies = sorted(this_week_companies - known)

    # Skills with pct_change
    top_skills = _compute_pct_change(raw_skills, previous_skills)

    snapshot = {
        "week_start": week_start_date,
        "total_jobs_ingested": len(jobs),
        "jobs_by_role": roles,
        "jobs_by_location": locations,
        "top_skills": top_skills,
        "new_companies": new_companies,
        "salary_signals": salary,
    }

    log.info(
        f"  {len(jobs)} jobs, {len(raw_skills)} skills, "
        f"{len(new_companies)} new companies"
    )
    return snapshot


def _get_existing_week_starts() -> set[str]:
    """Check which weeks already have snapshots."""
    sb = get_supabase()
    try:
        result = sb.table("market_snapshots").select("week_start").execute()
        return {row["week_start"] for row in (result.data or [])}
    except Exception:
        return set()


def run_market_snapshot(dry_run: bool = False, force: bool = False) -> list[dict]:
    """Run the weekly market snapshot pipeline.

    On first run (or with force=True), backfills last 12 weeks.
    Otherwise, computes only the current week.

    Returns list of snapshot dicts produced.
    """
    now = datetime.now(timezone.utc)
    current_monday = _monday_of(now)

    existing = _get_existing_week_starts()
    is_first_run = len(existing) == 0

    # Determine which weeks to compute
    if is_first_run or force:
        log.info(f"Backfilling last {_BACKFILL_WEEKS} weeks of market snapshots")
        weeks = []
        for i in range(_BACKFILL_WEEKS, -1, -1):  # oldest first for pct_change chaining
            monday = _monday_of(now - timedelta(weeks=i))
            weeks.append(monday)
    else:
        weeks = [current_monday]

    # Deduplicate (multiple dates can map to the same Monday)
    seen = set()
    unique_weeks = []
    for w in weeks:
        if w not in seen:
            seen.add(w)
            unique_weeks.append(w)
    weeks = unique_weeks

    snapshots: list[dict] = []
    previous_skills: dict[str, int] | None = None

    for week_start in weeks:
        snapshot = _build_snapshot_for_week(week_start, previous_skills)
        if snapshot is None:
            continue

        # Extract raw skill counts for next week's pct_change
        previous_skills = {
            s["skill"]: s["count"]
            for s in snapshot["top_skills"]
        }

        if not dry_run:
            sb = get_supabase()
            try:
                sb.table("market_snapshots").upsert(
                    snapshot, on_conflict="week_start"
                ).execute()
                log.info(f"  Snapshot written for {week_start}")
            except Exception as e:
                log.error(f"  Failed to write snapshot for {week_start}: {e}")
                raise

        snapshots.append(snapshot)

    log.info(
        f"Market snapshot complete: {len(snapshots)} weeks, "
        f"{sum(s['total_jobs_ingested'] for s in snapshots)} total jobs"
    )
    return snapshots
