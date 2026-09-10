"""
sources/feeds/randstad.py - Randstad Germany (major recruiting agency)

API: POST https://www.randstad.de/api/search/search-results
Auth: None
Format: Elasticsearch JSON via POST API, 30 jobs per page, ~12K total jobs.
Strategy: Paginate through all pages, extract full job data from ES _source.
Yields: ~12,000+ jobs across all sectors in Germany.
"""

import logging
import time

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://www.randstad.de/api/search/search-results'
_JOBS_PER_PAGE = 30
_MAX_PAGES = 450  # Safety cap (~13,500 jobs max)
_REQUEST_DELAY = 0.5  # Be respectful

_HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (compatible; JobAggregator/1.0)',
    'Referer': 'https://www.randstad.de/jobs/',
    'Accept': 'application/json',
}


def _parse_hit(hit: dict) -> dict | None:
    """Parse a single Elasticsearch hit into a job dict."""
    src = hit.get('_source', {})
    if not src:
        return None

    job_info = src.get('JobInformation', {})
    job_loc = src.get('JobLocation', {})
    salary = src.get('Salary', {})
    identity = src.get('JobIdentity', {})
    client = src.get('BlueXClientInformation', {})
    dates = src.get('JobDates', {})

    job_id = src.get('JobId', '')
    if not job_id:
        return None

    title = job_info.get('Title', '')
    details_url = job_info.get('DetailsUrl', '')
    url = f"https://www.randstad.de{details_url}" if details_url else ''

    # Prefer client (actual employer) over Randstad as company
    company = client.get('ClientName') or identity.get('CompanyName') or 'Randstad'

    city = job_loc.get('City', '')
    region = job_loc.get('Region', '')
    postcode = job_loc.get('Postcode', '')
    location = f"{postcode} {city}".strip() if city else region or 'Germany'

    # Build salary string
    sal_min = salary.get('SalaryMin')
    sal_max = salary.get('SalaryMax')
    sal_type = salary.get('CompensationType', '')

    # Build description from available fields
    desc_parts = []
    if job_info.get('JobType'):
        desc_parts.append(f"Art: {job_info['JobType']}")
    if job_info.get('Hours'):
        desc_parts.append(f"Arbeitszeit: {job_info['Hours']}")
    if job_info.get('Duration'):
        desc_parts.append(f"Dauer: {job_info['Duration']}")
    if job_info.get('Industry'):
        desc_parts.append(f"Branche: {job_info['Industry']}")

    return {
        'id': f"randstad_{job_id}",
        'url': url,
        'title': title,
        'company': company,
        'location': location,
        'description': ' | '.join(desc_parts),
        'salary_min': int(float(sal_min)) if sal_min else None,
        'salary_max': int(float(sal_max)) if sal_max else None,
        'salary_currency': 'EUR',
        'salary_period': 'year' if 'Jahr' in sal_type else 'hour' if 'Stunde' in sal_type else '',
        'posted_at': dates.get('DateCreatedTime') or dates.get('DateCreated'),
    }


class RandstadSource(BaseSource):
    name = "randstad"
    display_name = "Randstad Germany"
    source_type = "feed"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Randstad Germany POST API...")
        all_jobs = []
        seen_ids = set()

        for page in range(1, _MAX_PAGES + 1):
            try:
                payload = {
                    "data": {
                        "currentRoute": {"url": "/jobs/", "routeName": "search"},
                        "currentLanguage": "de",
                        "searchParams": {"page": str(page)},
                    }
                }

                resp = requests.post(
                    _API_URL, json=payload, headers=_HEADERS, timeout=30,
                )

                if resp.status_code != 200:
                    log.debug(f"  Page {page}: HTTP {resp.status_code}, stopping")
                    break

                data = resp.json()

                # Navigate to Elasticsearch hits (top-level searchResults)
                hits = (
                    data.get('searchResults', {})
                    .get('hits', {})
                    .get('hits', [])
                )

                if not hits:
                    log.debug(f"  Page {page}: no hits, stopping")
                    break

                for hit in hits:
                    try:
                        job = _parse_hit(hit)
                        if job and job['url'] and job['id'] not in seen_ids:
                            seen_ids.add(job['id'])
                            all_jobs.append(job)
                    except Exception as e:
                        log.warning(f"  Randstad hit parse error: {e}")

                if len(hits) < _JOBS_PER_PAGE:
                    log.debug(f"  Page {page}: partial page ({len(hits)} hits), stopping")
                    break

                if page % 50 == 0:
                    log.debug(f"  Randstad: {len(all_jobs)} jobs after {page} pages")

                time.sleep(_REQUEST_DELAY)

            except Exception as e:
                log.warning(f"  Randstad page {page} error: {e}")
                break

        log.info(f"Randstad: {len(all_jobs)} unique jobs from {page} pages")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
