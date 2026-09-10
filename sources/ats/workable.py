"""
sources/ats/workable.py - Workable ATS feed drain.

API: https://apply.workable.com/api/v1/widget/accounts/{slug}
Auth: None (public widget API)
Returns all published jobs in a single response (no pagination).
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_BASE = 'https://apply.workable.com/api/v1/widget/accounts'
_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job(job: dict, slug: str, company_name: str) -> dict:
    """Convert Workable job JSON to raw job dict."""
    # Build location from city/state/country + locations array
    parts = []
    if job.get('city'):
        parts.append(job['city'])
    if job.get('state'):
        parts.append(job['state'])
    if job.get('country'):
        parts.append(job['country'])
    location = ', '.join(parts) if parts else None

    shortcode = job.get('shortcode', '')

    # Normalise employment_type from API value
    raw_emp = (job.get('employment_type') or '').lower()
    emp_type = None
    if 'full' in raw_emp:
        emp_type = 'full-time'
    elif 'part' in raw_emp:
        emp_type = 'part-time'
    elif 'contract' in raw_emp or 'freelance' in raw_emp:
        emp_type = 'contract'
    elif 'intern' in raw_emp:
        emp_type = 'internship'

    return {
        'id': f"workable_{slug}_{shortcode}",
        'url': job.get('url') or job.get('shortlink') or f"https://apply.workable.com/{slug}/j/{shortcode}",
        'title': job.get('title', 'Untitled'),
        'company': company_name or slug,
        'location': location,
        'description': '',  # Widget API doesn't include descriptions
        'posted_at': job.get('published_on') or job.get('created_at') or None,
        'source_job_id': shortcode,
        'remote_type': 'remote' if job.get('telecommuting') else None,
        'employment_type': emp_type,
    }


class WorkableSource(BaseSource):
    name = "workable"
    display_name = "Workable (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Workable companies."""
        companies = get_companies('workable')
        if not companies:
            log.info("Workable: no companies in registry")
            return []

        log.info(f"Workable: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                url = f"{_API_BASE}/{slug}"
                resp = requests.get(url, timeout=_TIMEOUT)

                if resp.status_code == 404:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: 404")
                    record_failure('workable', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()
                jobs = data.get('jobs', [])

                # Use company name from API if available
                api_name = data.get('name', '')
                display_name = api_name or name

                job_count = 0
                for job in jobs:
                    raw = _parse_job(job, slug, display_name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('workable', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('workable', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('workable', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Workable: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
