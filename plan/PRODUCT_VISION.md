# Job Aggregator - Product Vision & Feature Specifications

**Version:** 1.0
**Date:** 2026-02-21
**Status:** Vision Document - Planning Phase

---

## The Big Picture

The Job Aggregator is a **headless data acquisition service**. Its sole purpose is to populate the shared Postgres database with job listings from every available source: APIs, scrapers, and RSS feeds, in a normalised, deduplicated format.

The consuming application never calls an API. It never scrapes a page. It reads from the database. The aggregator is the only thing that writes.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCHEDULER (CRON / systemd)                  │
│  Triggers aggregator every hour                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                                │
│  Loads enabled sources → runs each → collects results → logs   │
└──────────┬──────────────────┬──────────────────┬────────────────┘
           ↓                  ↓                  ↓
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  API FETCHERS    │ │  SCRAPERS        │ │  FEED PARSERS    │
│  (REST/GraphQL)  │ │  (Playwright/BS) │ │  (RSS/XML/JSON)  │
│                  │ │                  │ │                  │
│  Arbeitsamt      │ │  Google Jobs     │ │  DevITjobs (XML) │
│  TheMuse         │ │  LinkedIn        │ │  Future feeds    │
│  Arbeitnow       │ │  Indeed (direct) │ │                  │
│  Jobicy          │ │  Glassdoor       │ │                  │
│  SerpAPI         │ │  Career pages    │ │                  │
│  Adzuna          │ │                  │ │                  │
│  Reed            │ │                  │ │                  │
│  Findwork        │ │                  │ │                  │
│  Jooble          │ │                  │ │                  │
│  etc.            │ │                  │ │                  │
└──────────┬───────┘ └──────────┬───────┘ └──────────┬───────┘
           │                    │                    │
           └────────────────────┼────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     NORMALISATION PIPELINE                      │
│  Raw data → Standard schema → Parse fields → Hash → Dedup      │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     DATABASE SYNC                               │
│  Insert new → Update existing (last_seen_at) → Log stats        │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
                    Supabase PostgreSQL
                    (shared with the consuming application)
```

---

## Feature Specifications

### 1. Source Plugin System

Every data source is a self-contained module that implements a standard interface.

**Interface:**
```python
class BaseSource:
    name: str                    # e.g. "arbeitsamt"
    display_name: str            # e.g. "Arbeitsamt (German Federal Employment Agency)"
    source_type: str             # "api" | "scraper" | "feed"
    auth_type: str               # "none" | "api_key" | "oauth" | "credentials"
    rate_limit: int              # requests per minute
    enabled: bool                # can be toggled without code changes

    def fetch(self, search_terms=None, locations=None) -> list[dict]:
        """Fetch raw job data from source. Returns list of raw dicts."""

    def normalise(self, raw_jobs: list[dict]) -> list[JobRecord]:
        """Convert raw dicts to standard JobRecord format."""

    def health_check(self) -> SourceHealth:
        """Quick connectivity test. Returns status + latency."""
```

**Adding a new source:** Create one file in `sources/apis/` or `sources/scrapers/`, implement the interface, register in `sources/__init__.py`.

---

### 2. Normalisation Pipeline

All raw data flows through a single normalisation pipeline before database insertion.

**Pipeline stages:**

```
Raw API response
       ↓
1. Field extraction (source-specific mapping)
       ↓
2. Text cleaning (HTML strip, whitespace normalise)
       ↓
3. Location parsing → (city, country, remote_type)
       ↓
4. Salary parsing → (min, max, currency, period, confidence)
       ↓
5. Seniority detection → (junior/mid/senior/lead/executive)
       ↓
6. Employment type → (full-time/part-time/contract/freelance/internship)
       ↓
7. Hash generation (strict + fuzzy + description fingerprint)
       ↓
8. Deduplication check
       ↓
9. Database insert/update
```

**The normalisation functions build on the same field-parsing logic used elsewhere in the stack:**
- `parse_remote_type()`
- `parse_location()`
- `parse_seniority()`
- `parse_employment_type()`
- `parse_salary()`
- `calculate_canonical_hash_strict()`
- `calculate_canonical_hash_fuzzy()`
- `calculate_description_fingerprint()`

These will be migrated to this repo as-is.

---

### 3. Deduplication Strategy

Three-layer deduplication to handle cross-source overlap:

| Layer | Hash Input | Catches |
|-------|-----------|---------|
| **External ID** | `source + external_id` | Same source re-fetching same job |
| **Strict hash** | `title + company + location` | Exact duplicates across sources |
| **Fuzzy hash** | `company + location + description_fingerprint` | Near-duplicates (slightly different titles) |

**Behaviour:**
- **Exact match (external_id):** Update `last_seen_at`, keep everything else
- **Strict hash match:** Skip insert, update `last_seen_at` on existing
- **Fuzzy hash match:** Log as potential duplicate, keep both (manual review in dashboard)
- **No match:** Insert as new job

---

### 4. CRON / Scheduler

**Default schedule:**

| Schedule | What | Why |
|----------|------|-----|
| Every hour | Run all enabled API sources | Keep data fresh |
| Every 6 hours | Run all scrapers | Scrapers are heavier / rate-limited |
| Daily (midnight) | Freshness check: mark stale jobs as inactive | `is_active = false` if not seen in 7 days |
| Daily (00:30) | Source health report | Log success/failure rates per source |

**Implementation options:**
1. **System CRON** - simplest, most reliable, `crontab -e`
2. **systemd timer** - more control, journald logging
3. **APScheduler** - in-process (if we want a long-running daemon)
4. **Docker + CRON** - containerised, portable

Phase 1 uses system CRON. Phase 2 may switch to a long-running daemon with APScheduler if we need finer control (e.g., per-source scheduling, health monitoring).

---

### 5. Source Health Monitoring

Each source tracks:

```python
{
    "source": "arbeitsamt",
    "last_run_at": "2026-02-21T03:00:00Z",
    "last_success_at": "2026-02-21T03:00:00Z",
    "last_failure_at": null,
    "last_error": null,
    "jobs_fetched_last_run": 142,
    "jobs_new_last_run": 23,
    "consecutive_failures": 0,
    "total_jobs_contributed": 4521,
    "avg_jobs_per_run": 130,
    "is_healthy": true
}
```

**Circuit breaker:**
- After 3 consecutive failures → disable source
- Log alert
- Re-enable manually or after 24h cooldown

**Visibility:**
- Health data stored in `source_health` table (Supabase)
- A consuming application's dashboard reads from this table for its Debug page
- No UI in the aggregator itself

---

### 6. Configuration

All source configuration lives in environment variables and a config file:

```python
# .env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx

# API Keys
SERPAPI_KEY=xxx
ADZUNA_APP_ID=xxx
ADZUNA_API_KEY=xxx
REED_API_KEY=xxx
FINDWORK_API_KEY=xxx
JOOBLE_API_KEY=xxx
INDEED_PUBLISHER_ID=xxx
OXYLABS_USERNAME=xxx
OXYLABS_PASSWORD=xxx

# Schedule
CRON_INTERVAL_MINUTES=60
SCRAPER_INTERVAL_HOURS=6

# Feature flags
ENABLE_SCRAPERS=false    # Start with APIs only
LOG_LEVEL=INFO
```

```python
# config.py
SOURCES = {
    "arbeitsamt":       {"enabled": True,  "type": "api",     "rate_limit": 60},
    "themuse":          {"enabled": True,  "type": "api",     "rate_limit": 30},
    "arbeitnow":        {"enabled": True,  "type": "api",     "rate_limit": 30},
    "jobicy":           {"enabled": True,  "type": "api",     "rate_limit": 30},
    "serpapi":          {"enabled": True,  "type": "api",     "rate_limit": 10},
    "adzuna":           {"enabled": False, "type": "api",     "rate_limit": 30},
    "reed":             {"enabled": False, "type": "api",     "rate_limit": 30},
    "findwork":         {"enabled": False, "type": "api",     "rate_limit": 30},
    "jooble":           {"enabled": False, "type": "api",     "rate_limit": 30},
    "indeed":           {"enabled": False, "type": "api",     "rate_limit": 30},
    "oxylabs":          {"enabled": False, "type": "scraper", "rate_limit": 5},
    "google_scraper":   {"enabled": False, "type": "scraper", "rate_limit": 5},
}
```

---

### 7. Search Terms & Locations (Profile-Driven)

The aggregator can receive search parameters from the consuming application via the database:

**`match_criteria` table (already exists in Supabase):**
- `title_terms_json` - search terms expanded from a user's target titles
- `target_locations_json` - locations from a user's profile

Sources that support search queries (Arbeitsamt, SerpAPI, Reed, Indeed) use these terms instead of hardcoded keyword lists. Sources that don't support queries (Arbeitnow, Jobicy) fetch everything and let a downstream pre-filter handle relevance.

---

The aggregator's only output is rows in the `jobs` table matching this schema
(source of truth: the shared `jobs` table schema):

```sql
-- Every field the aggregator writes
external_id             TEXT UNIQUE,
url                     TEXT,
title                   TEXT,
company                 TEXT,
location                TEXT,
salary                  TEXT,           -- Legacy column (same as salary_raw)
salary_raw              TEXT,           -- Original salary string
description             TEXT,
source                  TEXT NOT NULL,
fetched_at              TIMESTAMPTZ,
first_seen_at           TIMESTAMPTZ,
last_seen_at            TIMESTAMPTZ,
posted_at               TIMESTAMPTZ,    -- If source provides a published date
is_active               BOOLEAN DEFAULT TRUE,
triage_status           TEXT DEFAULT 'queued',  -- 'queued' | 'excluded'
remote_type             TEXT,           -- 'remote' | 'hybrid' | 'onsite' | 'unknown'
location_city           TEXT,
location_country        TEXT,
seniority               TEXT,           -- 'junior' | 'mid' | 'senior' | 'lead' | 'executive'
employment_type         TEXT,           -- 'full-time' | 'part-time' | 'contract' | 'freelance'
salary_min              INTEGER,
salary_max              INTEGER,
salary_currency         TEXT DEFAULT 'EUR',
salary_period           TEXT,           -- 'yearly' | 'monthly' | 'hourly'
salary_confidence       REAL,           -- 'exact' | 'estimated' | 'inferred'
canonical_hash_strict   TEXT,
canonical_hash_fuzzy    TEXT,
description_fingerprint TEXT,
source_job_id           TEXT            -- Alternative source-specific job ID
```

**The aggregator NEVER writes to:**
- `score`, `reasoning`, `evaluated_at` (evaluation, owned by the consuming application)
- `applied_at`, `ignored_at`, `closed_at` (pipeline state, owned by the consuming application)
- `apply_url` (application engine, owned by the consuming application)
- `title_tsv` (auto-generated TSVECTOR column, PostgreSQL handles this)
- `job_evaluation` table (per-user scoring, owned by the consuming application)
- `application` table (tracking, owned by the consuming application)

---

**Last Updated:** 2026-02-21
