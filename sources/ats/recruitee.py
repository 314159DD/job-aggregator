"""
sources/ats/recruitee.py - Recruitee (Tellent) ATS feed drain.

API: https://{slug}.recruitee.com/api/offers/
Auth: None (public Careers Site API)
Returns all published offers in a single response.

Strong in DACH/Benelux. Includes salary data when available.
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


def _parse_offer(offer: dict, slug: str, fallback_name: str) -> dict:
    """Convert Recruitee offer JSON to raw job dict."""
    # Location from city/state/country
    parts = []
    if offer.get('city'):
        parts.append(offer['city'])
    if offer.get('state_name'):
        parts.append(offer['state_name'])
    if offer.get('country'):
        parts.append(offer['country'])
    location = ', '.join(parts) if parts else None

    # Remote type
    remote_type = ''
    if offer.get('remote'):
        remote_type = 'remote'
    elif offer.get('hybrid'):
        remote_type = 'hybrid'

    # Description + requirements
    desc = offer.get('description', '') or ''
    reqs = offer.get('requirements', '') or ''
    description = f"{desc}\n\n{reqs}".strip() if reqs else desc

    # Salary
    salary_info = offer.get('salary', {}) or {}
    salary_raw = ''
    if salary_info.get('min') or salary_info.get('max'):
        currency = salary_info.get('currency', '')
        period = salary_info.get('period', '')
        sal_min = salary_info.get('min', '')
        sal_max = salary_info.get('max', '')
        salary_raw = f"{currency} {sal_min}-{sal_max} {period}".strip()

    company = offer.get('company_name') or fallback_name or slug

    return {
        'id': f"recruitee_{slug}_{offer.get('id')}",
        'url': offer.get('careers_url') or offer.get('careers_apply_url') or f"https://{slug}.recruitee.com/o/{offer.get('slug', '')}",
        'title': offer.get('title', 'Untitled'),
        'company': company,
        'location': location,
        'description': description,
        'posted_at': offer.get('published_at') or offer.get('created_at') or None,
        'source_job_id': str(offer.get('id', '')),
        '_department': offer.get('department', ''),
        '_employment_type': offer.get('employment_type_code', ''),
        '_remote_type': remote_type,
        '_salary_raw': salary_raw,
    }


class RecruiteeSource(BaseSource):
    name = "recruitee"
    display_name = "Recruitee (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Recruitee companies."""
        companies = get_companies('recruitee')
        if not companies:
            log.info("Recruitee: no companies in registry")
            return []

        log.info(f"Recruitee: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                url = f"https://{slug}.recruitee.com/api/offers/"
                resp = requests.get(url, timeout=_TIMEOUT)

                if resp.status_code == 404:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: 404")
                    record_failure('recruitee', slug)
                    continue

                # Some slugs redirect - treat as inactive
                if resp.history and resp.url and slug not in resp.url:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: redirected, skipping")
                    record_failure('recruitee', slug)
                    continue

                resp.raise_for_status()
                data = resp.json()
                offers = data.get('offers', [])

                job_count = 0
                for offer in offers:
                    raw = _parse_offer(offer, slug, name)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('recruitee', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('recruitee', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('recruitee', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Recruitee: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
