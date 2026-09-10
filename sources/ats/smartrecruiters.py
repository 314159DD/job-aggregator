"""
sources/ats/smartrecruiters.py - SmartRecruiters ATS feed drain.

API: https://api.smartrecruiters.com/v1/companies/{slug}/postings
Auth: None for public postings
Pagination: offset-based (?offset=0&limit=100)
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_BASE = 'https://api.smartrecruiters.com/v1/companies'
_PAGE_SIZE = 100
_MAX_PAGES = 50
_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job(job: dict, slug: str, company_name: str) -> dict:
    """Convert SmartRecruiters posting JSON to raw job dict."""
    loc = job.get('location', {})
    location_parts = []
    if loc.get('city'):
        location_parts.append(loc['city'])
    if loc.get('region'):
        location_parts.append(loc['region'])
    if loc.get('country'):
        location_parts.append(loc['country'])
    location = ', '.join(location_parts) if location_parts else None

    # Remote type from location or typeOfWorkplace
    remote_type = job.get('typeOfWorkplace', '')

    dept = job.get('department', {})
    dept_name = dept.get('label', '') if isinstance(dept, dict) else str(dept)

    # Description from company/job description
    description = job.get('jobDescription', '') or ''
    company_desc = job.get('companyDescription', '')
    if company_desc:
        description = f"{description}\n\n{company_desc}"

    ref_number = job.get('refNumber', '')
    apply_url = job.get('applyUrl') or f"https://jobs.smartrecruiters.com/{slug}/{job.get('id')}"

    return {
        'id': f"smartrecruiters_{slug}_{job.get('id')}",
        'url': apply_url,
        'title': job.get('name', 'Untitled'),
        'company': company_name or slug,
        'location': location,
        'description': description,
        'posted_at': job.get('releasedDate') or job.get('createdOn') or None,
        'source_job_id': ref_number or str(job.get('id', '')),
        '_department': dept_name,
        '_remote_type': remote_type,
    }


class SmartRecruitersSource(BaseSource):
    name = "smartrecruiters"
    display_name = "SmartRecruiters (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered SmartRecruiters companies."""
        companies = get_companies('smartrecruiters')
        if not companies:
            log.info("SmartRecruiters: no companies in registry")
            return []

        log.info(f"SmartRecruiters: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug

            try:
                company_jobs = self._fetch_all_pages(slug, name)

                job_count = 0
                for raw in company_jobs:
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('smartrecruiters', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('smartrecruiters', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('smartrecruiters', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"SmartRecruiters: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def _fetch_all_pages(self, slug: str, company_name: str) -> list[dict]:
        """Paginate through all postings for a company."""
        jobs = []
        offset = 0

        for _ in range(_MAX_PAGES):
            url = f"{_API_BASE}/{slug}/postings"
            params = {'offset': offset, 'limit': _PAGE_SIZE}
            resp = requests.get(url, params=params, timeout=_TIMEOUT)

            if resp.status_code == 404:
                record_failure('smartrecruiters', slug)
                return []

            resp.raise_for_status()
            data = resp.json()
            content = data.get('content', [])

            if not content:
                break

            for posting in content:
                jobs.append(_parse_job(posting, slug, company_name))

            # Check if there are more pages
            total = data.get('totalFound', 0)
            offset += len(content)
            if offset >= total:
                break

        return jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
