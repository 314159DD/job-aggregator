# Job Aggregator

A headless data-acquisition service. It pulls job listings from 26 sources on an hourly CRON schedule, normalises every listing into one schema, runs it through three layers of deduplication, and upserts the result into Postgres.

[![Tests](https://github.com/314159DD/job-aggregator/actions/workflows/test.yml/badge.svg)](https://github.com/314159DD/job-aggregator/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)

There is no web server, no UI, and no user-facing state. It reads nothing back from its own database; it only writes. Anything that wants job data reads the `jobs` table directly.

---

## How it works

```
 REST/GraphQL APIs ─┐
 ATS career-page    │
   feed APIs ────────┼─► Normalise ─► Dedup L1 ─► Dedup L2 ─► Dedup L3 ─► Upsert ─┐
 RSS/XML feeds      │    (schema,      (external    (title +    (company +        │
 HTML scrapers ─────┘     salary,        id per       company +   location +      │
                           location,      source)      location)   description     │
                           seniority)                              fingerprint)    │
                                                                                    ▼
                                                                          Postgres (Supabase)
                                                                                    │
                                                          weekly ──────────────────►┤
                                                                          Skill / market snapshots
```

Every source, regardless of format, is normalised into the same record: title, company, location (parsed into city/country/remote type), salary (parsed into min/max/currency/period with a confidence score), seniority, employment type, and content hashes for dedup. A CRON trigger runs the full pipeline hourly; daily and weekly jobs handle freshness checks, health reporting, and demand-snapshot aggregation.

## Deduplication

Three layers catch overlap both within a source and across sources:

| Layer | Hash input | Catches |
|-------|-----------|---------|
| External ID | `source + external_id` | Same source re-fetching a job it already has |
| Strict hash | `title + company + location` | Exact duplicates posted to more than one board |
| Fuzzy hash | `company + location + description fingerprint` | Near-duplicates with a slightly different title |

An external-ID or strict-hash match updates `last_seen_at` on the existing row instead of inserting. A fuzzy match is logged for review but both rows are kept, since it isn't certain enough to auto-merge.

## Sources

26 implemented source adapters (plus 3 unimplemented stubs: `jooble`, `graphql_jobs`, `google_jobs`) across four categories. Every adapter classified by how it accesses the target:

| Category | Type | What it means |
|---|---|---|
| **Official API** | `api` | A documented, intended-for-third-parties API, with or without a key |
| **ATS feed API** | `ats` | The public, unauthenticated postings API an Applicant Tracking System exposes for its customers' career pages |
| **Public feed** | `feed` | A syndication format (RSS/XML) published for consumption |
| **HTML scraper** | `scraper` | Parses server-rendered HTML from a site with no public API for this data |

| Source | Category | Notes |
|---|---|---|
| Arbeitsamt (German Federal Employment Agency) | Official API | Public API key, no registration |
| TheMuse | Official API | Unauthenticated |
| Arbeitnow | Official API | Unauthenticated |
| Jobicy | Official API | Unauthenticated |
| Findwork | Official API | Requires a free API key |
| Reed | Official API | Requires a free API key |
| Adzuna | Official API | Requires a free API key, budget-limited |
| SerpAPI | Official API | Paid, disabled by default |
| Oxylabs | Official API | Paid, disabled by default |
| Indeed | Official API | Publisher program, disabled (deprecated affiliate API) |
| Jooble | Official API | Stub, not implemented |
| GraphQL Jobs | Official API | Stub, not implemented; upstream service is defunct |
| Greenhouse | ATS feed API | Public, unauthenticated |
| Lever | ATS feed API | Public, unauthenticated |
| Workday | ATS feed API | Public, unauthenticated |
| Ashby | ATS feed API | Public, unauthenticated |
| Personio | ATS feed API | Public, unauthenticated |
| SmartRecruiters | ATS feed API | Public, unauthenticated |
| Workable | ATS feed API | Public widget API |
| Recruitee | ATS feed API | Public Careers Site API |
| Pinpoint | ATS feed API | Public, documented unauthenticated |
| d.vinci | ATS feed API | Public since ATS version 2022.11 |
| DevITjobs UK | Public feed | RSS 2.0 |
| praktischArzt | Public feed | WordPress RSS, paginated |
| Randstad | HTML/internal API | Calls the site's internal search endpoint directly (not a documented public API); see Known caveats below |
| Hays | HTML scraper | Server-rendered search results |
| Interamt | HTML scraper | Server-rendered detail pages, session cookie |
| Lehrstellen-Radar | HTML scraper | Server-rendered, paginated by postal code |
| Google Jobs | HTML scraper | Stub, not implemented |

**Cadence:** everything enabled runs on the hourly `python -m aggregator` pass. Freshness checks run daily, full discovery and demand snapshots run weekly. See `docker/crontab`.

### Known caveats (for anyone deploying this)

- `sources/apis/indeed.py` sends a hardcoded `userip: '1.2.3.4'` and a generic `useragent: 'Mozilla/5.0'` string as required fields on the (deprecated) Indeed affiliate API. This is dead code today (the source is disabled and the API is deprecated) but should not be copied into a live integration without a real client IP.
- `sources/feeds/randstad.py` (disabled by default in `aggregator/config.py`) calls `randstad.de`'s internal search endpoint (`/api/search/search-results`) rather than a published public API. Confirm the target's `robots.txt` and terms before enabling this in production.
- `hays.py`, `interamt.py`, `lehrstellen_radar.py`, `randstad.py`, and `discovery/sitemap_scan.py` scrape or call undocumented endpoints on sites with no public API for job data. They send an honest, self-identifying `User-Agent` (`Mozilla/5.0 (compatible; JobAggregator/1.0)`, the same pattern used by well-behaved crawlers like Googlebot) rather than impersonating a browser, but scraping these targets may still be against their terms of service. Review before use.

## Quick start

```bash
git clone <this-repo>
cd job-aggregator
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY at minimum

python -m aggregator --dry-run       # fetch everything, write nothing
python -m aggregator                 # fetch and sync to the database
python -m aggregator --source reed   # run a single source
python -m aggregator --list-sources  # see what's registered and enabled
```

## Configuration

All configuration is environment variables, loaded from `.env` (see [`.env.example`](.env.example) for the full list with comments).

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | Yes | Postgres/Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service-role key for writes |
| `FINDWORK_API_KEY` | No | Enables the Findwork source |
| `REED_API_KEY` | No | Enables the Reed source |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | No | Enables the Adzuna source |
| `SERPAPI_KEY` | No | Enables SerpAPI (Google Jobs via SerpAPI), paid |
| `OXYLABS_USERNAME`, `OXYLABS_PASSWORD` | No | Enables Oxylabs, paid |
| `INDEED_PUBLISHER_ID` | No | Enables the Indeed source |
| `SERPER_API_KEY` | No | Google dorking during `--discover`, optional |
| `OPENROUTER_API_KEY` | No | LLM-assisted title translation/classification |
| `SENTRY_DSN` | No | Error tracking; disabled if unset |
| `CIRCUIT_BREAKER_THRESHOLD` | No | Consecutive failures before a source is disabled (default 3) |
| `CIRCUIT_BREAKER_COOLDOWN_HOURS` | No | Hours before an auto-reset (default 24) |
| `ATS_REQUEST_DELAY` | No | Seconds between ATS requests (default 0.5) |
| `ENABLE_SCRAPERS` | No | Feature flag for HTML scraper sources |
| `LOG_LEVEL` | No | Default `INFO` |
| `DRY_RUN` | No | Fetch without writing, default `false` |

## Testing

61 tests covering normalisation, deduplication, the orchestrator, rate limiting, and the snapshot pipeline.

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All 61 pass against mocked external services; no live API keys are required to run the suite.

## Deploy

**Docker + CRON (recommended):** `Dockerfile` runs [supercronic](https://github.com/aptible/supercronic) against `docker/crontab`. Build and run with `docker compose up -d`, or one-off with `docker compose run --rm -e AGGREGATOR_MODE=once job-aggregator`. `docker/healthcheck.py` backs the container `HEALTHCHECK`.

**Railway:** `railway.toml` points at the `Dockerfile` and configures the service as a worker (no HTTP port). Point a Railway service at this repo and set the environment variables above.

**Plain CRON:** `cron.conf` is a `crontab`-ready schedule for a non-Docker deployment; `Makefile` has shortcuts for local runs (`make run`, `make dry-run`, `make health`).

## Project structure

```
aggregator/          Orchestrator, config, DB client, models, normalisation pipeline
  normalisation/      Field parsing, salary/location/seniority inference, hashing
sources/              One file per data source, grouped by category
  apis/               REST/GraphQL API sources
  ats/                ATS career-page feed drains (Greenhouse, Lever, Workday, ...)
  feeds/              RSS/XML feed sources
  scrapers/           HTML scrapers
  base.py             BaseSource interface every source implements
discovery/            Self-discovery, sitemap scanning, Google dorking, seed lists
search_terms/         Shared search-term intelligence (German job title taxonomy)
scripts/              Health report, single-source test runner, DB migrations
tests/                61 tests, mocked external services
plan/                 Architecture notes, roadmap, implementation plan
docker/               Entrypoint, crontab, healthcheck for the container image
```

## License

MIT. See [LICENSE](LICENSE).
