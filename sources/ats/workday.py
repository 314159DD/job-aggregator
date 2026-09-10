"""
sources/ats/workday.py - Workday ATS feed drain.

API: POST https://{co}.{wdN}.myworkdayjobs.com/wday/cxs/{co}/{site}/jobs
Auth: None (public, unauthenticated)
Pagination: limit=20 (max), offset-based.

Used by DAX/Fortune 500 companies (Deutsche Bank, etc.).
URL pattern is company-specific and unpredictable - stored in career_url.

Detail endpoint (optional):
  GET  .../{site}/job/{externalPath}
  Returns full HTML description. Skipped by default for speed.
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_PAGE_SIZE = 20  # Workday max
_MAX_PAGES = 200  # Safety cap: 200 * 20 = 4,000 jobs max per company
_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _extract_req_id(bullet_fields: list) -> str:
    """Extract the requisition ID from bulletFields (usually first element)."""
    if bullet_fields and isinstance(bullet_fields, list):
        return str(bullet_fields[0])
    return ''


def _parse_job(job: dict, slug: str, company_name: str, base_url: str) -> dict:
    """Convert Workday listing JSON to raw job dict."""
    req_id = _extract_req_id(job.get('bulletFields', []))
    external_path = job.get('externalPath', '')

    # Build public URL from the base (remove /wday/cxs/{co}/{site} to get the career page base)
    # e.g., https://db.wd3.myworkdayjobs.com/DBWebsite/job/...
    career_base = base_url.split('/wday/cxs/')[0] if '/wday/cxs/' in base_url else base_url
    site = base_url.rstrip('/').split('/')[-1] if base_url else ''
    job_url = f"{career_base}/{site}{external_path}" if external_path else ''

    # Parse "Posted Today", "Posted 2 Days Ago", "Posted 30+ Days Ago" etc.
    posted_text = job.get('postedOn', '')

    return {
        'id': f"workday_{slug}_{req_id}" if req_id else f"workday_{slug}_{external_path}",
        'url': job_url,
        'title': job.get('title', 'Untitled'),
        'company': company_name or slug,
        'location': job.get('locationsText') or None,
        'description': '',  # Listing endpoint doesn't include descriptions
        'posted_at': None,  # Workday uses relative text ("Posted Today"), not ISO dates
        'source_job_id': req_id or external_path,
        '_posted_text': posted_text,
    }


def _fetch_all_jobs(base_url: str) -> tuple[list[dict], int]:
    """Paginate through all jobs for a Workday company. Returns (postings, total)."""
    api_url = f"{base_url}/jobs"
    all_postings = []
    known_total = None  # Only the first page returns the real total

    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        body = {
            'limit': _PAGE_SIZE,
            'offset': offset,
            'searchText': '',
            'appliedFacets': {},
        }

        resp = requests.post(
            api_url,
            json=body,
            headers={'Content-Type': 'application/json'},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        postings = data.get('jobPostings', [])

        # Workday only returns the real total on the first page (offset=0)
        if page == 0:
            known_total = data.get('total', 0) or 0

        all_postings.extend(postings)

        # Stop if we got fewer than a full page (last page)
        if len(postings) < _PAGE_SIZE:
            break
        # Stop if we've collected everything
        if known_total and len(all_postings) >= known_total:
            break

        _limiter.wait('workday', 120)

    return all_postings, known_total or len(all_postings)


class WorkdaySource(BaseSource):
    name = "workday"
    display_name = "Workday (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 120
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Workday companies."""
        companies = get_companies('workday')
        if not companies:
            log.info("Workday: no companies in registry")
            return []

        log.info(f"Workday: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']
            name = company.get('company_name') or slug
            base_url = company.get('career_url', '')

            if not base_url:
                log.warning(f"  [{i}/{len(companies)}] {slug}: no career_url set, skipping")
                continue

            # Ensure base_url doesn't end with /jobs
            base_url = base_url.rstrip('/')
            base_url = base_url.removesuffix('/jobs')

            try:
                postings, total = _fetch_all_jobs(base_url)

                job_count = 0
                for posting in postings:
                    raw = _parse_job(posting, slug, name, base_url)
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('workday', slug, job_count)
                log.info(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except requests.Timeout:
                log.warning(f"  [{i}/{len(companies)}] {slug}: timeout")
                record_failure('workday', slug)
            except requests.HTTPError as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: HTTP {e.response.status_code}")
                record_failure('workday', slug)
            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('workday', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Workday: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
