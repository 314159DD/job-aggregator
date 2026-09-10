"""
sources/ats/ashby.py - Ashby ATS feed drain.

API: https://api.ashbyhq.com/posting-api/job-board/{company}
Auth: None (public)

Returns {jobs: [...]} with all published postings for a company.
Growing ATS popular with startups and scale-ups.
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_BASE = 'https://api.ashbyhq.com/posting-api/job-board'
_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job(job: dict, slug: str, company_name: str) -> dict:
    """Convert Ashby job JSON to raw job dict."""
    location = job.get('location') or ''
    if isinstance(location, dict):
        location = location.get('name', '')

    # Secondary location from locationName
    if not location:
        location = job.get('locationName') or ''

    team = job.get('team') or ''
    if isinstance(team, dict):
        team = team.get('name', '')

    # Normalise employment type from API value
    raw_emp = (job.get('employmentType') or '').lower()
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
        'id': f"ashby_{slug}_{job.get('id')}",
        'url': job.get('applyUrl') or job.get('jobUrl') or f"https://jobs.ashbyhq.com/{slug}/{job.get('id')}",
        'title': job.get('title', 'Untitled'),
        'company': company_name or slug,
        'location': location or None,
        'description': job.get('descriptionHtml') or job.get('descriptionPlain') or '',
        'posted_at': job.get('publishedDate') or job.get('publishedAt') or None,
        'source_job_id': str(job.get('id', '')),
        'employment_type': emp_type,
    }


class AshbySource(BaseSource):
    name = "ashby"
    display_name = "Ashby (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Ashby companies."""
        companies = get_companies('ashby')
        if not companies:
            log.info("Ashby: no companies in registry")
            return []

        log.info(f"Ashby: crawling {len(companies)} companies...")
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
                    record_failure('ashby', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()
                jobs = data.get('jobs', [])

                job_count = 0
                for job in jobs:
                    raw = _parse_job(job, slug, name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('ashby', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('ashby', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('ashby', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Ashby: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
