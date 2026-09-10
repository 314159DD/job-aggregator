-- =============================================================================
-- Migration: Create aggregator_runs table
-- Run this in the Supabase SQL Editor.
--
-- Written by: aggregator/run_log.py (live progress tracking)
-- Read by:    a consuming application's /api/debug/aggregator/runs endpoint (Run Log section)
-- =============================================================================

CREATE TABLE IF NOT EXISTS aggregator_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT UNIQUE NOT NULL,

    -- Timing
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    -- Run metadata
    is_dry_run      BOOLEAN DEFAULT FALSE,
    status          TEXT DEFAULT 'running',   -- running | completed | failed

    -- Progress (updated live during run)
    sources_total   INTEGER DEFAULT 0,
    sources_done    INTEGER DEFAULT 0,
    current_source  TEXT,

    -- Results per source  { "adzuna": { fetched, new, updated, errors, duration, status } }
    results         JSONB DEFAULT '{}',

    -- Final summary      { total_fetched, total_new, total_updated, total_errors }
    summary         JSONB
);

CREATE INDEX IF NOT EXISTS idx_aggregator_runs_started ON aggregator_runs(started_at DESC);
