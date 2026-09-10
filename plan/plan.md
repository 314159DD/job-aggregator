# Implementation Plan - Job Aggregator

**Last Updated:** 2026-02-21
**Version:** 1.0

The core service loop is: **CRON -> Fetch all sources -> Normalise -> Deduplicate -> Sync to DB.**

This plan delivers that loop first, then expands sources, then adds scrapers.

Full roadmap: [ROADMAP.md](ROADMAP.md)
Feature specs: [PRODUCT_VISION.md](PRODUCT_VISION.md)
Architecture principles: [concept.md](concept.md)

---

## Phase 1 - Extract & Automate (COMPLETE)

**Goal:** Aggregator runs independently on CRON, with zero manual intervention.

---

### Step 1: Project Setup

Scaffold the project, set up the environment, establish the source plugin pattern.

**Folder structure:**

```
job-aggregator/
├── aggregator/                  # Main package
│   ├── __init__.py              # Package init
│   ├── __main__.py              # Entry point: python -m aggregator
│   ├── orchestrator.py          # Runs all enabled sources, collects results
│   ├── config.py                # Configuration (loads from .env)
│   ├── db.py                    # Supabase client setup
│   ├── models.py                # JobRecord dataclass, SourceHealth model
│   └── normalisation/           # Parsing & normalisation pipeline
│       ├── __init__.py
│       ├── parser.py            # parse_location, parse_salary, etc.
│       ├── dedup.py             # Hash generation, dedup checks
│       └── cleaner.py           # HTML strip, text normalisation
│
├── sources/                     # All data source modules
│   ├── __init__.py              # Source registry
│   ├── base.py                  # BaseSource interface
│   ├── apis/                    # REST/GraphQL API sources
│   ├── ats/                     # ATS career-page feed drains
│   ├── scrapers/                # HTML/Playwright scrapers
│   └── feeds/                   # RSS/XML/JSON feeds
│
├── scripts/                     # Utility scripts
│   ├── run_once.py              # Manual single run
│   ├── test_source.py           # Test a single source
│   └── health_report.py         # Print source health summary
│
├── tests/                       # Test suite
│
├── plan/                        # Project documentation (this folder)
│
├── .env.example                 # Template for environment variables
├── .gitignore
├── requirements.txt
├── Makefile                     # Common commands (run, test, lint)
├── Dockerfile                   # For containerised deployment
└── cron.conf                    # CRON configuration
```

---

### Step 2: Source Plugin Pattern

Every source implements `BaseSource.fetch()` and `BaseSource.normalise()`. New sources are added one file at a time (see [concept.md](concept.md) for the full plugin contract).

**Migration strategy (initial buildout):**
1. Implement each source against the `BaseSource` interface
2. Test the aggregator end to end for that source
3. Enable it in config once validated

---

### Step 3: Normalisation Pipeline

The normalisation pipeline wraps parsing functions into a single `normalise_job()` call.

**`aggregator/normalisation/parser.py`:**
```python
def normalise_job(raw: dict, source: str) -> JobRecord:
    """Convert raw API dict to normalised JobRecord."""
    title = raw.get('title', '')
    company = raw.get('company', '')
    location_raw = raw.get('location', '')
    description = raw.get('description', '')
    salary_raw = raw.get('salary', '')

    return JobRecord(
        external_id=raw.get('id'),
        url=raw.get('url'),
        title=title,
        company=company,
        location=location_raw,
        description=clean_html(description),
        source=source,
        remote_type=parse_remote_type(title, location_raw, description),
        location_city=parse_location(location_raw)[0],
        location_country=parse_location(location_raw)[1],
        seniority=parse_seniority(title, description),
        employment_type=parse_employment_type(title, description),
        salary_raw=salary_raw,
        salary_min=parse_salary(salary_raw)[0],
        salary_max=parse_salary(salary_raw)[1],
        salary_currency=parse_salary(salary_raw)[2],
        salary_period=parse_salary(salary_raw)[3],
        salary_confidence=parse_salary(salary_raw)[4],
        canonical_hash_strict=calculate_canonical_hash_strict(title, company, location_raw),
        canonical_hash_fuzzy=calculate_canonical_hash_fuzzy(company, location_raw,
            calculate_description_fingerprint(description)),
        description_fingerprint=calculate_description_fingerprint(description),
    )
```

---

### Step 4: Orchestrator

The orchestrator runs all enabled sources and handles the full pipeline.

**`aggregator/orchestrator.py`:**
```python
def run_all():
    """Main entry point. Run all enabled sources, sync results to DB."""
    sources = get_enabled_sources()
    results = {}

    for source in sources:
        try:
            log.info(f"Running {source.display_name}...")
            raw_jobs = source.fetch()
            normalised = [normalise_job(j, source.name) for j in raw_jobs]
            new, updated = sync_to_db(normalised)
            update_health(source.name, success=True, fetched=len(raw_jobs), new=new)
            results[source.name] = {"fetched": len(raw_jobs), "new": new, "updated": updated}
        except Exception as e:
            log.error(f"{source.display_name} failed: {e}")
            update_health(source.name, success=False, error=str(e))
            results[source.name] = {"error": str(e)}

    log_run_summary(results)
    return results
```

---

### Step 5: CRON Setup

**`cron.conf`:**
```cron
# Job Aggregator - Hourly job fetch
0 * * * * cd /path/to/job-aggregator && /path/to/venv/bin/python -m aggregator >> /var/log/aggregator.log 2>&1

# Daily freshness check (midnight)
0 0 * * * cd /path/to/job-aggregator && /path/to/venv/bin/python -m aggregator --freshness-check >> /var/log/aggregator.log 2>&1
```

**`aggregator/__main__.py`:**
```python
"""Entry point: python -m aggregator"""
import argparse
from aggregator.orchestrator import run_all, run_freshness_check

parser = argparse.ArgumentParser(description='Job Aggregator')
parser.add_argument('--freshness-check', action='store_true', help='Mark stale jobs as inactive')
parser.add_argument('--source', type=str, help='Run a single source only')
parser.add_argument('--dry-run', action='store_true', help="Fetch but don't write to DB")

args = parser.parse_args()

if args.freshness_check:
    run_freshness_check()
elif args.source:
    run_single(args.source, dry_run=args.dry_run)
else:
    run_all(dry_run=args.dry_run)
```

---

### Step 6: Source Health

**`source_health` table (Supabase / Postgres):**
```sql
CREATE TABLE IF NOT EXISTS source_health (
    id SERIAL PRIMARY KEY,
    source_name TEXT UNIQUE NOT NULL,
    last_run_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,
    last_error TEXT,
    jobs_fetched_last_run INTEGER DEFAULT 0,
    jobs_new_last_run INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    total_jobs_contributed INTEGER DEFAULT 0,
    is_healthy BOOLEAN DEFAULT TRUE,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

### Phase 1 Complete When:

- [x] `python -m aggregator` fetches from all active sources
- [x] CRON runs hourly without manual intervention
- [x] New jobs land in the database, existing rows updated with `last_seen_at`
- [x] 3-layer dedup works (no duplicate rows)
- [x] Source health tracked in `source_health` table
- [x] Excluded companies filtered at ingest
- [x] Profile-driven search terms used (from `match_criteria`)
- [x] Logs generated at `/var/log/aggregator.log`

---

## Phase 2 - Expand Sources

**Goal:** Add several new API sources.

Each new source follows the same pattern:
1. Create `sources/apis/source_name.py`
2. Implement `BaseSource.fetch()` and `BaseSource.normalise()`
3. Add to source registry
4. Add API key to `.env`
5. Test with `python scripts/test_source.py source_name`
6. Enable in config
7. Done. CRON picks it up automatically on the next run.

---

## Phase 3 - Scrapers

**Goal:** Direct scraping for sources without a public API or feed.

Scrapers are complex. They need:
- A browser runtime (Playwright) for JS-rendered targets
- Slower rate limits (seconds between requests, not milliseconds)
- Fragile selectors that break when the target site changes
- Careful ToS/robots.txt review per target (see the source classification in the project README)

That's why they're a later phase. APIs and public feeds first.

---

## Technical Debt Tracking

| Item | Priority | Notes |
|------|----------|-------|
| Add retry logic to all sources | High | Exponential backoff |
| Add structured logging (JSON logs for parsing) | Medium | Uses `structlog` |
| Unit tests for normalisation | High | Parsing functions are critical |
| Integration tests for each source | Medium | Mock API responses |
