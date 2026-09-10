-- =============================================================================
-- Migration: Create skill_snapshots table
-- Run this in the Supabase SQL Editor.
--
-- Written by: aggregator/snapshot.py (weekly skill snapshot pipeline)
-- Read by:    a consuming application's /api/debug/market-signals endpoint (future)
-- =============================================================================

CREATE TABLE IF NOT EXISTS skill_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    jobs_analyzed   INTEGER NOT NULL DEFAULT 0,

    -- Aggregated JSONB columns
    skill_frequencies       JSONB DEFAULT '{}',   -- {"python": 342, "javascript": 280, ...}
    role_type_counts        JSONB DEFAULT '{}',   -- {"senior": 150, "mid": 200, "junior": 80}
    salary_ranges           JSONB DEFAULT '{}',   -- {"min": 30000, "max": 150000, "median": 65000, ...}
    location_distribution   JSONB DEFAULT '{}',   -- {"Berlin": 200, "Munich": 150, ...}
    remote_type_counts      JSONB DEFAULT '{}',   -- {"remote": 300, "onsite": 400, "hybrid": 200}
    employment_type_counts  JSONB DEFAULT '{}',   -- {"full-time": 800, "part-time": 50}
    source_counts           JSONB DEFAULT '{}',   -- {"arbeitsamt": 500, "greenhouse": 200}

    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_snapshot_date UNIQUE (snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_skill_snapshots_date ON skill_snapshots(snapshot_date DESC);
