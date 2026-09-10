# Job Aggregator - Product Roadmap

**Last Updated:** 2026-03-10
**Version:** 2.0

---

## Phase Structure

```
Phase 1 (DONE)             Phase 2 (DONE)             Phase 3 (DONE)             Phase 4 (DONE)
────────────────           ────────────────           ────────────────           ────────────────
Extract & Automate         Expand Sources             ATS Drain System           Discovery Automation
────────────────           ────────────────           ────────────────           ────────────────
Migrate fetchers           Findwork API               10 ATS parsers             Auto self-discovery
Normalisation pipeline     Reed API                   390 companies              Sitemap scanning
CRON scheduler             Careerjet (no keys)        3 scrapers (Hays,          Weekly full discovery
Source health tracking     DevITjobs UK                 Interamt, Google)        Skill snapshots
DB sync (Supabase)         Adzuna API                 3 feeds (DevIT,            Health report +
Dedup (3-layer)            Post-launch fixes            Praktischarzt, Randstad)   registry stats
Config & env setup         Pipeline alignment         Company registry           CRON automation
Circuit breaker                                       Google dorking
Profile-driven search                                 Seed lists (158)
                                                       Security hardening
```

---

## Current State (2026-03-10)

**18 sources** active across 4 categories:
- 8 REST/GraphQL APIs (arbeitsamt, themuse, arbeitnow, jobicy, serpapi, findwork, reed, adzuna)
- 10 ATS drains (greenhouse, lever, workday, ashby, personio, smartrecruiters, workable, recruitee, pinpoint, dvinci)
- 3 feeds (devitjobs, praktischarzt, randstad)
- 3 scrapers (hays, interamt, google_jobs)

**390 registered companies** across 10 ATS types. ~27K jobs in pool.

**Automated schedule:**

| Schedule | What runs |
|---|---|
| Hourly | All sources + auto self-discovery |
| Daily midnight | Freshness check (mark stale jobs inactive) |
| Daily 00:30 | Health report + ATS registry stats |
| Weekly Sunday 02:00 | Full discovery (self-discover + sitemap scan + optional dork) |
| Weekly Sunday 03:00 | Skill snapshot (market demand aggregation) |

**Discovery flywheel:** Self-discovery runs automatically after every hourly aggregator pass. It scans ingested job URLs for ATS slugs and registers new companies. Those companies get drained on the next hourly run. Sitemap scanning runs weekly for deeper coverage.

---

## Phase 1 - Extract & Automate - COMPLETE (2026-02-21)

Built the initial fetcher set. 7 API sources, orchestrator, CRON, health tracking, 3-layer dedup, circuit breaker.

---

## Phase 2 - Expand Sources - COMPLETE (2026-02-21)

Added Findwork, Reed, DevITjobs UK, Adzuna. Batch dedup optimisation (3N HTTP calls collapsed to 3). Pipeline alignment with downstream consumer schema.

---

## Phase 3 - ATS Drain System - COMPLETE (2026-02-27)

The biggest expansion. Instead of keyword-based API searches, pull every job from registered company career pages via their public ATS APIs.

### What got built

- **10 ATS parsers:** Greenhouse, Lever, Workday, Ashby, Personio, SmartRecruiters, Workable, Recruitee, Pinpoint, d.vinci
- **Company registry:** `company_registry` table with ats_type, slug, domain, crawl stats, circuit breaker
- **4 discovery mechanisms:**
  1. Seed lists - 158 hardcoded companies (`discovery/seed_lists.py`)
  2. Google dorking - Serper.dev API, site: searches (`discovery/google_dork.py`)
  3. Self-discovery - scan job URLs for ATS patterns (`discovery/self_discover.py`)
  4. Sitemap scanning - crawl company sitemaps (`discovery/sitemap_scan.py`)
- **3 scrapers:** Hays (BeautifulSoup), Interamt (HTML), Google Jobs (stub, Playwright planned)
- **3 feeds:** DevITjobs UK (RSS), Praktischarzt (RSS), Randstad (Elasticsearch)
- **Skill extraction:** 120+ skill taxonomy, regex-based
- **German title translation:** Batch LLM translation via OpenRouter
- **Multi-source search terms:** Aggregates search criteria across configured profiles
- **Security hardening:** Sanitised error messages, rate limiting, circuit breakers

### Registry growth

| Method | Companies found | Notes |
|---|---|---|
| Seed lists | 158 | One-time manual curation |
| Google dorking | 232 | Serper API credits largely spent |
| Self-discovery | Ongoing | Runs after every hourly aggregator pass |
| Sitemap scanning | Ongoing | Runs weekly |
| **Total** | **390** | Growing passively via flywheel |

---

## Phase 4 - Discovery Automation - COMPLETE (2026-03-10)

Automated all discovery mechanisms so the registry grows without manual intervention.

### What changed

1. **Auto self-discovery in `orchestrator.py`.** After every `run_all()`, the pipeline automatically scans newly ingested job URLs for ATS slugs and registers new companies. Non-fatal: the aggregator run succeeds even if discovery fails.

2. **`--discover` CLI flag.** Full 3-phase discovery suite:
   - Phase 1: Self-discovery (scan existing job URLs, fast, free)
   - Phase 2: Sitemap scanning (crawl company sitemaps, slower, free)
   - Phase 3: Google dorking (only if SERPER_API_KEY set and credits remain)

3. **CRON schedule updated.** Weekly full discovery (Sunday 02:00) plus weekly skill snapshot (Sunday 03:00). Both were previously manual-only.

4. **Health report enhanced.** Now shows ATS registry breakdown (active/inactive per ATS type and totals) alongside source health.

### Files changed

| File | Change |
|---|---|
| `aggregator/orchestrator.py` | Auto self-discovery after `run_all()` |
| `aggregator/__main__.py` | New `--discover` flag |
| `cron.conf` | Weekly discovery + skill snapshot schedules |
| `scripts/health_report.py` | ATS registry stats section |

---

## Future Considerations (No Timeline)

These are noted for reference, not planned:

- **More ATS registrations** - the flywheel handles this passively; monitor via health report.
- **Company metadata enrichment** - industry, size, logo. Would need a new `companies` table and an enrichment API. Not currently needed.
- **Additional source integrations** - the legal free/cheap space is largely exhausted. Sources without a public API or feed require scraping infrastructure that is fragile and carries ToS risk (see the source classification in the project README).
- **Google dorking credits** - largely spent; sitemap scanning and self-discovery cover most of the same ground for free.

---

## Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-02-21 | Python, not Node/Go | Consistency with the rest of the stack |
| 2026-02-21 | Supabase direct, no API relay | The aggregator writes directly to Postgres |
| 2026-02-21 | CRON over APScheduler | System CRON is simpler, more reliable |
| 2026-02-21 | Source plugin architecture | Adding a source means adding one file |
| 2026-02-21 | Skip USAJOBS, Jooble, WhatJobs, ZipRecruiter | USA-only, not free, or OAuth-only |
| 2026-02-27 | ATS drain over scraping | Public APIs, no auth, no anti-detection needed |
| 2026-03-10 | Auto-discovery in CRON | Registry should grow passively, not require manual runs |
| 2026-03-10 | Deprecate Google dorking as primary discovery | Credits exhausted, sitemap + self-discovery sufficient |
