"""
sources/ats/pinpoint.py - Pinpoint ATS feed drain.

API: https://{slug}.pinpointhq.com/postings.json
Auth: None (explicitly documented as unauthenticated, CORS-friendly)
Returns all published postings. Includes compensation data.

UK-founded, Europe-first. Used across manufacturing, finance, healthcare.
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


def _parse_posting(posting: dict, slug: str, company_name: str) -> dict:
    """Convert Pinpoint posting JSON to raw job dict."""
    # Location from nested object
    loc = posting.get('location', {}) or {}
    location = loc.get('name') if isinstance(loc, dict) else str(loc) if loc else None

    # Build description from multiple fields
    parts = []
    for field in ('description', 'key_responsibilities', 'skills_knowledge_expertise', 'benefits'):
        text = posting.get(field, '')
        if text and text.strip():
            parts.append(text.strip())
    description = '\n\n'.join(parts)

    # Compensation
    salary_raw = ''
    comp_min = posting.get('compensation_minimum')
    comp_max = posting.get('compensation_maximum')
    if comp_min or comp_max:
        currency = posting.get('compensation_currency', '')
        freq = posting.get('compensation_frequency', '')
        salary_raw = f"{currency} {comp_min or '?'}-{comp_max or '?'} {freq}".strip()

    posting_id = posting.get('id', '')

    return {
        'id': f"pinpoint_{slug}_{posting_id}",
        'url': posting.get('url') or f"https://{slug}.pinpointhq.com{posting.get('path', '')}",
        'title': posting.get('title', 'Untitled'),
        'company': company_name or slug,
        'location': location,
        'description': description,
        'posted_at': None,  # Pinpoint doesn't expose published_at in listing
        'source_job_id': str(posting_id),
        '_employment_type': posting.get('employment_type', ''),
        '_workplace_type': posting.get('workplace_type', ''),
        '_salary_raw': salary_raw,
    }


class PinpointSource(BaseSource):
    name = "pinpoint"
    display_name = "Pinpoint (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Pinpoint companies."""
        companies = get_companies('pinpoint')
        if not companies:
            log.info("Pinpoint: no companies in registry")
            return []

        log.info(f"Pinpoint: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                url = f"https://{slug}.pinpointhq.com/postings.json"
                resp = requests.get(url, timeout=_TIMEOUT)

                if resp.status_code == 404:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: 404")
                    record_failure('pinpoint', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()
                postings = data.get('data', [])

                job_count = 0
                for posting in postings:
                    raw = _parse_posting(posting, slug, name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('pinpoint', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('pinpoint', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('pinpoint', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Pinpoint: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
