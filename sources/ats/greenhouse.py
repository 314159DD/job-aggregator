"""
sources/ats/greenhouse.py - Greenhouse ATS feed drain.

API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
Auth: None (public, unauthenticated)
Rate limit: No headers observed; CDN-cached. Be polite with 0.5s delays.

Returns all jobs for a company in a single response (no pagination).
Without ?content=true: ~0.6KB/job (lightweight).
With ?content=true: ~10KB/job (full HTML descriptions).
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_BASE = 'https://boards-api.greenhouse.io/v1/boards'
_TIMEOUT = 30
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job(job: dict, slug: str, company_name: str) -> dict:
    """Convert Greenhouse job JSON to raw job dict for normalisation."""
    loc = job.get('location', {})
    location_str = loc.get('name', '') if isinstance(loc, dict) else str(loc)

    departments = job.get('departments', [])
    dept_name = departments[0].get('name', '') if departments else ''

    offices = job.get('offices', [])
    office_name = offices[0].get('name', '') if offices else ''

    # Use absolute_url (company career page) if available, fall back to Greenhouse URL
    url = job.get('absolute_url') or f"{_API_BASE}/{slug}/jobs/{job.get('id')}"

    # Combine location sources
    if not location_str and office_name:
        location_str = office_name

    return {
        'id': f"greenhouse_{slug}_{job.get('id')}",
        'url': url,
        'title': job.get('title', 'Untitled'),
        'company': company_name or slug,
        'location': location_str or None,
        'description': job.get('content', ''),
        'posted_at': job.get('first_published') or job.get('updated_at'),
        'source_job_id': str(job.get('id', '')),
        '_department': dept_name,
    }


class GreenhouseSource(BaseSource):
    name = "greenhouse"
    display_name = "Greenhouse (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 120
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Greenhouse companies."""
        companies = get_companies('greenhouse')
        if not companies:
            log.info("Greenhouse: no companies in registry")
            return []

        log.info(f"Greenhouse: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                # Fetch with content for full descriptions
                url = f"{_API_BASE}/{slug}/jobs"
                params = {'content': 'true'}
                resp = requests.get(url, params=params, timeout=_TIMEOUT)

                if resp.status_code == 404:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: 404 (not found)")
                    record_failure('greenhouse', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()
                jobs = data.get('jobs', [])

                # Extract company name from board metadata if available
                meta = data.get('meta', {})
                if meta.get('name'):
                    name = meta['name']

                job_count = 0
                for job in jobs:
                    raw = _parse_job(job, slug, name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('greenhouse', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('greenhouse', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('greenhouse', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Greenhouse: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
