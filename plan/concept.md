# Core Concept & Philosophy

**Last Updated:** 2026-02-21

---

## The Vision

**The aggregator is the tireless data collector.**

It runs 24/7, pulling job listings from every API and scraping every job board it can reach. It normalises everything into one consistent format, deduplicates aggressively, and feeds it all into the shared database.

The consuming application never has to know where a job came from. It just knows there are fresh, normalised job listings in the database, ready to be scored, evaluated, and acted on.

---

## Why Separate?

### 1. Different lifecycles

The fetchers change when APIs change. A consuming application changes when users request features. These are independent cycles. A broken Indeed integration shouldn't block a dashboard update.

### 2. Different deployment needs

The aggregator runs as a background worker: a CRON job, a systemd service, or a container with no web server. A typical consuming application is a web server with its own UI and browser automation. They don't belong on the same server.

### 3. Different scaling characteristics

Adding 10 more sources means more concurrent HTTP requests and rate limiting logic, not more web routes. The aggregator scales by adding sources; a consuming application scales by adding users.

### 4. Testability

Each fetcher can be tested in isolation with mocked API responses. No Flask context, no Supabase connection needed for unit tests. Integration tests hit real APIs with rate limiting.

---

## Key Principles

### 1. Every source is a plugin

Each data source is a self-contained module with:
- A `fetch()` function that returns raw jobs
- A `normalise()` function that maps to the standard schema
- Configuration (API keys, rate limits, enabled/disabled)
- Health tracking (last success, last failure, error count)

Adding a new source = adding one file and one config entry.

### 2. Normalise everything

No matter how different the APIs are, the output is always the same schema. A consuming application doesn't distinguish between a job from Arbeitsamt and one from ZipRecruiter. Same fields, same format, same quality.

### 3. Deduplicate aggressively

The same job appears on multiple boards. Three layers of dedup:
- **Strict hash:** `hash(title + company + location)` - exact duplicates
- **Fuzzy hash:** `hash(company + location + description_fingerprint)` - near duplicates (same job, slightly different title)
- **External ID:** `source + external_id` - same source re-fetching the same job

### 4. Fail silently, retry intelligently

A single source failing should never block other sources. Each source runs independently with:
- Retry logic (exponential backoff)
- Error logging (not user-facing, there is no user)
- Health status (tracked in DB, visible in a consuming dashboard)
- Circuit breaker (disable source after N consecutive failures)

### 5. Database is the contract

The aggregator's only output is rows in the `jobs` table. That's the contract with anything that consumes this data. No HTTP endpoints, no message queues, no file exports. Just database writes.

### 6. CRON is enough (for now)

No complex job queue needed. A CRON job every hour triggers `python -m aggregator`. When scale demands it, upgrade to a proper task queue (Celery, Redis Queue). But don't over-engineer for 15 sources.

### 7. Small files, single responsibility

**Hard rule: no file exceeds 200 lines.** If it does, split it.

A sibling project learned this the hard way: one file grew past 1,500 lines before being forcibly refactored into a dozen smaller modules. That wasted a full sprint, which is what this rule prevents.

**Line budgets per module:**

| Module | Max Lines | Responsibility |
|--------|-----------|----------------|
| `orchestrator.py` | 150 | Coordinate sources → normalise → sync |
| `sync.py` | 150 | Insert/update jobs in Supabase |
| `health.py` | 100 | Source health tracking + circuit breaker |
| `retry.py` | 60 | Exponential backoff wrapper |
| `lock.py` | 50 | PID-based CRON lock |
| `config.py` | 100 | Env loading + source config |
| `db.py` | 40 | Supabase client singleton |
| `models.py` | 80 | Dataclasses (JobRecord, SyncResult, etc.) |
| `logging_config.py` | 40 | Structlog setup |
| Each source file | 120 | One source: fetch + normalise |
| Each normalisation file | 120 | One parsing concern |

**If a file hits its budget:** split it, don't extend the budget. A 200-line parser means there are two concerns in one file.

**If a new concern appears:** create a new file, don't add to an existing one. The cost of a 30-line file is zero. The cost of debugging a 500-line file is hours.

---

## What This Is NOT

- **Not a web app.** No UI, no dashboard, no routes. The consuming application has a debug page that shows source health; that's enough.
- **Not a scraping framework.** We use Scrapy/BeautifulSoup/Playwright as tools, but the aggregator is not a generic scraper. It's purpose-built for job listings.
- **Not a data warehouse.** We store normalised job listings, not raw API responses. If we need raw data later, we add a `raw_responses` table. Don't store garbage now.
- **Not real-time.** Hourly is fine. Job listings don't change by the second. If a source supports webhooks, we can add that later.

---

**Last Updated:** 2026-02-21

