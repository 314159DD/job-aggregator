"""
sources/ats/lever.py - Lever ATS feed drain.

API: https://api.lever.co/v0/postings/{company}
Auth: None (public)

Returns a JSON array of all published postings for a company.
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_BASE = 'https://api.lever.co/v0/postings'
_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job(job: dict, slug: str, company_name: str = '') -> dict:
    """Convert Lever posting JSON to raw job dict."""
    categories = job.get('categories', {})
    location = categories.get('location') or categories.get('allLocations', [''])[0] if isinstance(categories.get('allLocations'), list) else categories.get('location', '')
    team = categories.get('team', '')
    commitment = categories.get('commitment', '')  # e.g. "Full-time"

    # Build description from descriptionPlain or lists
    description = job.get('descriptionPlain') or ''
    lists = job.get('lists', [])
    if lists:
        parts = [description] if description else []
        for lst in lists:
            heading = lst.get('text', '')
            content = lst.get('content', '')
            if heading and content:
                parts.append(f"<h3>{heading}</h3>\n{content}")
        description = '\n\n'.join(parts)

    apply_url = job.get('applyUrl') or job.get('hostedUrl') or ''

    # Normalise commitment to standard employment_type values
    emp_type = None
    if commitment:
        cl = commitment.lower()
        if 'full' in cl:
            emp_type = 'full-time'
        elif 'part' in cl:
            emp_type = 'part-time'
        elif 'contract' in cl or 'freelance' in cl:
            emp_type = 'contract'
        elif 'intern' in cl:
            emp_type = 'internship'

    return {
        'id': f"lever_{slug}_{job.get('id')}",
        'url': apply_url or f"{_API_BASE}/{slug}/{job.get('id')}",
        'title': job.get('text', 'Untitled'),
        'company': company_name or job.get('company', slug),
        'location': location or None,
        'description': description,
        'posted_at': None,  # Lever uses createdAt as epoch ms
        'source_job_id': str(job.get('id', '')),
        'employment_type': emp_type,
    }


def _parse_epoch(epoch_ms) -> str | None:
    """Convert Lever's epoch ms timestamp to ISO format."""
    if not epoch_ms:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return None


class LeverSource(BaseSource):
    name = "lever"
    display_name = "Lever (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Lever companies."""
        companies = get_companies('lever')
        if not companies:
            log.info("Lever: no companies in registry")
            return []

        log.info(f"Lever: crawling {len(companies)} companies...")
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
                    record_failure('lever', slug)
                    continue

                resp.raise_for_status()
                postings = resp.json()

                if not isinstance(postings, list):
                    log.debug(f"  [{i}/{len(companies)}] {slug}: unexpected response type")
                    record_failure('lever', slug)
                    continue

                job_count = 0
                for posting in postings:
                    raw = _parse_job(posting, slug, name)
                    # Parse epoch timestamps
                    raw['posted_at'] = _parse_epoch(posting.get('createdAt'))
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('lever', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('lever', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('lever', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Lever: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
