"""
sources/ats/_registry.py - Company registry queries for ATS sources.

All ATS sources use this module to look up which companies to crawl,
and to report back crawl results (job counts, failures).
"""

import logging
from datetime import datetime, timezone

from aggregator.db import get_supabase

log = logging.getLogger(__name__)


def get_companies(ats_type: str) -> list[dict]:
    """Fetch all active companies for an ATS type from company_registry.

    Returns:
        List of dicts with keys: id, ats_slug, company_name, domain,
        career_url, last_crawled_at, last_job_count, consecutive_failures
    """
    try:
        sb = get_supabase()
        result = sb.table('company_registry').select(
            'id, ats_slug, company_name, domain, career_url, '
            'last_crawled_at, last_job_count, consecutive_failures'
        ).eq('ats_type', ats_type).eq('is_active', True).execute()
        return result.data or []
    except Exception as e:
        log.error(f"Failed to fetch companies for {ats_type}: {e}")
        return []


def update_crawl_result(ats_type: str, ats_slug: str, job_count: int) -> None:
    """Update last_crawled_at and last_job_count after a successful crawl."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb = get_supabase()
        sb.table('company_registry').update({
            'last_crawled_at': now,
            'last_job_count': job_count,
            'consecutive_failures': 0,
            'updated_at': now,
        }).eq('ats_type', ats_type).eq('ats_slug', ats_slug).execute()
    except Exception as e:
        log.warning(f"Failed to update crawl result for {ats_type}/{ats_slug}: {e}")


def record_failure(ats_type: str, ats_slug: str, max_failures: int = 3) -> None:
    """Increment consecutive_failures. Deactivate if threshold exceeded."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb = get_supabase()
        # Fetch current failure count
        row = sb.table('company_registry').select('consecutive_failures').eq(
            'ats_type', ats_type
        ).eq('ats_slug', ats_slug).execute()

        if not row.data:
            log.warning(f"No registry row for {ats_type}/{ats_slug}, skipping failure record")
            return
        failures = (row.data[0].get('consecutive_failures') or 0) + 1
        update = {
            'consecutive_failures': failures,
            'updated_at': now,
        }
        if failures >= max_failures:
            update['is_active'] = False
            log.warning(
                f"Deactivating {ats_type}/{ats_slug} after {failures} consecutive failures"
            )

        sb.table('company_registry').update(update).eq(
            'ats_type', ats_type
        ).eq('ats_slug', ats_slug).execute()
    except Exception as e:
        log.warning(f"Failed to record failure for {ats_type}/{ats_slug}: {e}")


def upsert_company(
    ats_type: str,
    ats_slug: str,
    company_name: str,
    discovered_via: str = 'manual',
    domain: str | None = None,
    career_url: str | None = None,
    country: str | None = None,
) -> None:
    """Insert or update a company in the registry (idempotent)."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb = get_supabase()
        sb.table('company_registry').upsert({
            'ats_type': ats_type,
            'ats_slug': ats_slug,
            'company_name': company_name,
            'domain': domain,
            'career_url': career_url,
            'discovered_via': discovered_via,
            'country': country,
            'is_active': True,
            'created_at': now,
            'updated_at': now,
        }, on_conflict='ats_type,ats_slug').execute()
    except Exception as e:
        log.warning(f"Failed to upsert {ats_type}/{ats_slug}: {e}")
