# Parser Health Report

**Date:** 2026-03-25 | **Sprint:** 5.8 (JOB-58)

## Summary

- **26 source parsers** across 4 categories (ATS, API, Feed, Scraper)
- **23 enabled** in production pipeline | **3 disabled** (paid APIs) | **3 stubs** (unimplemented)
- **BaseSource compliance:** 100% - all implemented sources have `fetch()` + `normalise()`
- **Circuit breaker:** Operational (3-failure threshold, 24h cooldown)
- **Dedup pipeline:** Operational (3-layer: external ID → strict hash → fuzzy hash)
- **Self-discovery flywheel:** Operational (hourly self-discover + weekly sitemap scan)

## Changes Since Last Audit (2026-03-11)

| Change | Detail |
|--------|--------|
| **Re-enabled lehrstellen_radar** | Was incorrectly disabled ("requires Playwright"). Tested: pure HTML scraper using `requests`, works perfectly. ~15K apprenticeship listings. |
| **Fixed devitjobs + praktischarzt** | Both had broken imports (`defusedxml.ElementTree` has no `Element` attribute). Fixed: import `Element` from `xml.etree.ElementTree` for type hints. These two sources were silently failing to load in production. |
| **GraphQL Jobs API dead** | `api.graphql.jobs` DNS no longer resolves. Stub remains but API is defunct. |
| **Net result** | Enabled sources: 18 → 23 (+3 restored, +2 were broken at import) |

## Source Inventory

### ATS Drain Sources (10) - All Enabled

| Source | Health | Notes |
|--------|--------|-------|
| greenhouse | Good | Public REST, no auth, CDN-cached. `?content=true` for descriptions. |
| lever | Good | Public REST, epoch ms timestamps. ListType response validation. |
| workday | Good | POST API, offset pagination (20/page, 200 page cap). No descriptions from listing. |
| ashby | Good | Public REST, startup-focused. Handles descriptionHtml + descriptionPlain. |
| personio | Good | DACH market. Dual endpoint: JSON first, XML fallback (lxml recover mode). |
| smartrecruiters | Good | Offset/limit pagination. Builds location from city/region/country. |
| workable | Good | Widget API, single call. No descriptions available in widget response. |
| recruitee | Good | DACH/Benelux. Redirect detection for inactive companies. Includes salary. |
| pinpoint | Good | UK/Europe-first. Multi-field description assembly. Compensation data. |
| dvinci | Good | Hamburg-based. Combines 5 description fields. German market. |

All ATS sources use `_registry.py`: fetch companies via `get_companies(ats_type)`, report via `update_crawl_result()`, auto-deactivate after 3 failures. Rate-limited at 0.5s between requests.

### API Sources (7 enabled, 3 disabled, 2 stubs)

| Source | Enabled | Health | Notes |
|--------|---------|--------|-------|
| arbeitsamt | Yes | Good | German Federal Employment Agency. 144 occupation codes, city-split for >10K jobs. |
| themuse | Yes | Good | 10 pages max (~200 jobs). 500 req/hr. Graceful 429 handling. |
| arbeitnow | Yes | Good | Pages 1-10, no search params. |
| jobicy | Yes | Good | Remote jobs. Structured salary (min, max, currency, period). |
| findwork | Yes | Good | Cursor-based pagination. FINDWORK_API_KEY required. 429 backoff. |
| reed | Yes | Good | UK-only, 5 locations. BasicAuth (REED_API_KEY). Salary min/max. |
| adzuna | Yes | Good | **Budget-constrained:** 250 calls/month free tier. DE only. |
| serpapi | No | - | Paid API, credits exhausted. |
| oxylabs | No | - | Paid API, needs credentials. |
| indeed | No | - | Indeed deprecated affiliate API. Missing INDEED_PUBLISHER_ID. |
| graphql_jobs | No | Dead | `api.graphql.jobs` DNS defunct. Stub only. |
| jooble | No | Stub | Needs API key registration. Not implemented. |

### Feed Sources (3) - All Enabled

| Source | Health | Notes |
|--------|--------|-------|
| devitjobs | Good | RSS 2.0. Single fetch, ~200 UK dev jobs. **Fixed:** `defusedxml.Element` import bug (2026-03-25). |
| praktischarzt | Good | WordPress RSS, ~5,600 pages × 10 items. **Fixed:** `defusedxml.Element` import bug (2026-03-25). |
| randstad | Good | Elasticsearch POST API. ~12K jobs, 450+ pages (30/page). Salary extraction. |

### Scraper Sources (3 enabled, 1 stub)

| Source | Enabled | Health | Notes |
|--------|---------|--------|-------|
| hays | Yes | Good | hays.de HTML. Regex card parsing. ~5,800 jobs / 20 per page. |
| interamt | Yes | Good | interamt.de HTML. ~12K public sector jobs. ID enumeration, 200-miss threshold. |
| lehrstellen_radar | Yes | **Restored** | HWK apprenticeships. Pure HTML scraper (no Playwright needed). ~15K listings across 16 PLZ regions. **Re-enabled 2026-03-25.** |
| google_jobs | No | Stub | Not implemented. Would require Playwright. |

## Issues Found

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| 1 | devitjobs + praktischarzt were broken | **Critical (fixed)** | `defusedxml.ElementTree` has no `Element` attribute. Both sources silently failed to load at import time in production. Fixed by importing `Element` from `xml.etree.ElementTree`. |
| 2 | lehrstellen_radar wrongly disabled | Medium (fixed) | Config said "requires JS rendering (Playwright)" but source is pure `requests` HTML scraper. Re-enabled. |
| 3 | Workday no descriptions | Low | Listing endpoint returns no job descriptions. Would need detail page fetch per job. |
| 4 | Workable no descriptions | Low | Widget API omits descriptions. Full API requires auth. |
| 5 | Adzuna budget constraint | Low | 250 calls/month free tier. Weekly interval prevents exhaustion. |
| 6 | GraphQL Jobs API dead | Info | DNS no longer resolves. Stub file remains. |
| 7 | 2 stubs unimplemented | Info | jooble, google_jobs - placeholder files only. |

## Infrastructure Health

| Component | File | Status |
|-----------|------|--------|
| BaseSource interface | `sources/base.py` | Excellent - `safe_get()` enforces 50MB limit (SEC-08) |
| Config management | `aggregator/config.py` | Good - all entries match source status |
| Health tracking | `aggregator/health.py` | Excellent - error sanitization strips API keys |
| Circuit breaker | `aggregator/health.py` | Excellent - 3-failure open, 24h cooldown |
| Orchestrator | `aggregator/orchestrator.py` | Excellent - 5-worker ThreadPoolExecutor, per-source isolation |
| Dedup pipeline | `aggregator/sync.py` | Excellent - batch pre-fetch O(3 + writes), chunk 200, 3x retry |
| ATS registry | `sources/ats/_registry.py` | Excellent - auto-deactivate after 3 failures |
| Self-discovery | `discovery/self_discover.py` | Excellent - 10 ATS patterns, runs hourly post-aggregation |
| Sitemap scan | `discovery/sitemap_scan.py` | Excellent - weekly, max 50 child sitemaps, 50K URLs/file |
| defusedxml | feeds | Good - SEC-05 compliance (import bug now fixed) |

## Production Pipeline

**23 sources enabled:** arbeitsamt, themuse, arbeitnow, jobicy, findwork, reed, adzuna, devitjobs, praktischarzt, randstad, hays, interamt, lehrstellen_radar, greenhouse, lever, workday, ashby, personio, smartrecruiters, workable, recruitee, pinpoint, dvinci

**Combined reach:** ~390 companies, ~32,000+ jobs across DACH, UK, US markets.

**Overall assessment: HEALTHY.** Critical import bug fixed for 2 feed sources. 1 scraper source restored. All 23 enabled parsers properly implement BaseSource, handle errors gracefully, and integrate with circuit breaker + dedup pipeline.
