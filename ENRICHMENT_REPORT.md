# Job Data Enrichment Report

**Sprint:** 7.1 - Enrich Job Data with Metadata
**Date:** 2026-03-18
**Issue:** JOB-75

## Summary

Enriched 5 parsers to populate metadata fields (`posted_at`, `remote_type`, `employment_type`) that already exist in the `jobs` table schema and `JobRecord` model but were not being filled by source parsers. Updated the normalisation pipeline to prefer source-provided structured data over text inference.

## Existing Schema

The `jobs` table already contains all requested metadata columns:

| Requested Field | Existing Column | Status |
|----------------|----------------|--------|
| `posted_at` | `posted_at` | Already exists |
| `salary_text` | `salary` / `salary_raw` | Already exists |
| `work_mode` | `remote_type` | Already exists |
| `seniority_level` | `seniority` | Already exists |
| `application_deadline` | N/A | Not added (no source provides this data) |

**Note:** The issue referenced `candidate_jobs` but the actual table is `jobs`. No schema migration was needed.

## Changes Made

### 1. Normalisation Pipeline (`aggregator/normalisation/parser.py`)

Updated `normalise_job()` to prefer source-provided values for `remote_type`, `seniority`, and `employment_type` over text-inferred values. Previously, all sources relied entirely on regex-based text inference from title/description, even when the API provided structured metadata.

### 2. Reed (`sources/apis/reed.py`)

| Field | Before | After |
|-------|--------|-------|
| `posted_at` | Not extracted | Extracted from `date` / `datePosted` API fields |
| `employment_type` | Text inference only | Extracted from `partTime` boolean and `contractType` field |

### 3. Findwork (`sources/apis/findwork.py`)

| Field | Before | After |
|-------|--------|-------|
| `remote_type` | Only set location to "Remote" | Explicitly passes `remote_type: 'remote'` from `remote` boolean |
| `employment_type` | Text inference only | Extracted from `employment_type` API field if available |

### 4. Lever (`sources/ats/lever.py`)

| Field | Before | After |
|-------|--------|-------|
| `employment_type` | Stored as `_commitment` (unused) | Normalised from `categories.commitment` (Full-time, Part-time, Contract, Internship) |

### 5. Workable (`sources/ats/workable.py`)

| Field | Before | After |
|-------|--------|-------|
| `remote_type` | Stored as `_remote_type` (unused) | Passes `remote_type: 'remote'` from `telecommuting` boolean |
| `employment_type` | Stored as `_employment_type` (unused) | Normalised from `employment_type` API field |

### 6. Ashby (`sources/ats/ashby.py`)

| Field | Before | After |
|-------|--------|-------|
| `employment_type` | Stored as `_employment_type` (unused) | Normalised from `employmentType` API field |

## Field Coverage After Enrichment

| Source | posted_at | salary | remote_type | employment_type | seniority |
|--------|-----------|--------|-------------|-----------------|-----------|
| Adzuna | structured | structured | text inference | text inference | text inference |
| Reed | **NEW: API** | structured | text inference | **NEW: API** | text inference |
| Findwork | API | none | **NEW: API** | **NEW: API** | text inference |
| Greenhouse | API | none | text inference | text inference | text inference |
| Lever | API (epoch) | none | text inference | **NEW: API** | text inference |
| Workable | API | none | **NEW: API** | **NEW: API** | text inference |
| Ashby | API | none | text inference | **NEW: API** | text inference |
| DevITjobs | RSS | raw string | text inference | text inference | text inference |
| Arbeitsamt | none | raw string | text inference | text inference | text inference |
| Arbeitnow | none | none | text inference | text inference | text inference |

## Not Implemented

- **`application_deadline`**: No source API provides deadline data. Would require HTML scraping of individual job detail pages, which is not cost-effective at scale.
- **Backfill**: Existing jobs in the database cannot be retroactively enriched without re-fetching from source APIs. New enrichment applies to all future crawls automatically.
- **Seniority from API**: No source provides structured seniority data. Text inference from title/description remains the only option.

## Tests

All 61 existing tests pass with no regressions.
