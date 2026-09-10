-- =============================================================================
-- Migration: Create source_health table
-- Run this in the Supabase SQL Editor.
-- =============================================================================

CREATE TABLE IF NOT EXISTS source_health (
    id              SERIAL PRIMARY KEY,
    source_name     TEXT NOT NULL UNIQUE,

    -- Run stats
    last_run_at             TIMESTAMPTZ,
    last_success_at         TIMESTAMPTZ,
    last_failure_at         TIMESTAMPTZ,
    jobs_fetched_last_run   INTEGER DEFAULT 0,
    jobs_new_last_run       INTEGER DEFAULT 0,
    total_jobs_contributed  INTEGER DEFAULT 0,

    -- Circuit breaker
    consecutive_failures    INTEGER DEFAULT 0,
    is_healthy              BOOLEAN DEFAULT TRUE,
    is_enabled              BOOLEAN DEFAULT TRUE,
    last_error              TEXT,

    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_health_name ON source_health(source_name);
