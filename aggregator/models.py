"""
aggregator/models.py - Data models.

JobRecord matches the Supabase jobs table schema exactly.
SyncResult carries per-source sync statistics.
"""

from dataclasses import dataclass


@dataclass
class JobRecord:
    external_id: str
    source: str
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None
    description: str | None = None
    posted_at: str | None = None
    remote_type: str | None = None
    location_city: str | None = None
    location_country: str | None = None
    seniority: str | None = None
    employment_type: str | None = None
    salary: str | None = None
    salary_raw: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_confidence: float | None = None
    canonical_hash_strict: str | None = None
    canonical_hash_fuzzy: str | None = None
    description_fingerprint: str | None = None
    source_job_id: str | None = None
    title_de: str | None = None


@dataclass
class SyncResult:
    source: str
    fetched: int = 0
    new: int = 0
    updated: int = 0
    linked: int = 0       # fuzzy dupes linked to canonical record
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
