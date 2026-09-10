"""
sources/ats/dvinci.py - d.vinci ATS feed drain.

API: https://{slug}.dvinci-hr.com/jobPublication/list.json
Auth: None (public since ATS version 2022.11)
Returns all published jobs as a flat JSON array.

Hamburg-based ATS, specifically serves the German market.
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _build_description(job: dict) -> str:
    """Combine d.vinci's structured description fields into one text."""
    parts = []
    for field in ('introduction', 'tasks', 'profile', 'weOffer', 'closingText'):
        text = job.get(field, '')
        if text and text.strip():
            parts.append(text.strip())
    return '\n\n'.join(parts)


def _parse_job(job: dict, slug: str, company_name: str) -> dict:
    """Convert d.vinci job JSON to raw job dict."""
    # d.vinci doesn't have a separate location field - it may be in subtitle or jobOpening
    opening = job.get('jobOpening', {}) or {}
    location = None
    if isinstance(opening, dict):
        loc_parts = []
        if opening.get('city'):
            loc_parts.append(opening['city'])
        if opening.get('country'):
            loc_parts.append(opening['country'])
        location = ', '.join(loc_parts) if loc_parts else None

    description = _build_description(job)
    job_id = job.get('id', '')

    return {
        'id': f"dvinci_{slug}_{job_id}",
        'url': job.get('jobPublicationURL') or f"https://{slug}.dvinci-hr.com/de/jobs/{job_id}",
        'title': job.get('position') or job.get('pageTitle') or 'Untitled',
        'company': company_name or slug,
        'location': location,
        'description': description,
        'posted_at': job.get('startDate') or None,
        'source_job_id': str(job_id),
        '_language': job.get('language', ''),
    }


class DvinciSource(BaseSource):
    name = "dvinci"
    display_name = "d.vinci (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered d.vinci companies."""
        companies = get_companies('dvinci')
        if not companies:
            log.info("d.vinci: no companies in registry")
            return []

        log.info(f"d.vinci: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                url = f"https://{slug}.dvinci-hr.com/jobPublication/list.json"
                resp = requests.get(url, timeout=_TIMEOUT)

                if resp.status_code == 404:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: 404")
                    record_failure('dvinci', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if not isinstance(data, list):
                    log.debug(f"  [{i}/{len(companies)}] {slug}: unexpected response type")
                    record_failure('dvinci', slug)
                    continue

                job_count = 0
                for job in data:
                    raw = _parse_job(job, slug, name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('dvinci', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('dvinci', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('dvinci', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"d.vinci: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
