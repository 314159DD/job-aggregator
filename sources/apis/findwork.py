"""
sources/apis/findwork.py - Findwork

API: https://findwork.dev/api/jobs/
Auth: Token header (FINDWORK_API_KEY)
Strategy: fetch all pages, then search each term; dedup by id.
Rate: 60 req/min
"""

import logging
import time

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://findwork.dev/api/jobs/'
_MAX_PAGES = 20


def _parse(j: dict) -> dict:
    loc = j.get('location') or ''
    is_remote = j.get('remote', False)
    if not loc and is_remote:
        loc = 'Remote'
    return {
        'id': f"findwork_{j.get('id')}",
        'url': j.get('url'),
        'title': j.get('role'),
        'company': j.get('company_name'),
        'location': loc,
        'description': j.get('text', ''),
        'posted_at': j.get('date_posted'),
        'remote_type': 'remote' if is_remote else None,
        'employment_type': j.get('employment_type') or None,
    }


def _fetch_pages(headers: dict, params: dict) -> list:
    """Paginate a single query until next=null or max pages."""
    jobs = []
    url = _API_URL
    for _ in range(_MAX_PAGES):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 429:
                log.warning("  Findwork: rate limited - waiting 10s")
                time.sleep(10)
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for j in data.get('results', []):
                jobs.append(_parse(j))
            url = data.get('next')
            params = {}  # next URL already contains all params
            if not url:
                break
        except Exception as e:
            log.warning(f"  Findwork page error: {e}")
            break
    return jobs


class FindworkSource(BaseSource):
    name = "findwork"
    display_name = "Findwork"
    source_type = "api"
    auth_type = "api_key"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Findwork...")
        api_key = config.FINDWORK_API_KEY
        if not api_key:
            log.error("Findwork: FINDWORK_API_KEY not set")
            return []

        headers = {'Authorization': f'Token {api_key}'}
        all_jobs = []
        seen_ids = set()

        # Broad fetch (no filter) - catches everything
        for j in _fetch_pages(headers, {'sort_by': 'date'}):
            if j['id'] not in seen_ids:
                seen_ids.add(j['id'])
                all_jobs.append(j)
        log.debug(f"  Findwork: {len(all_jobs)} after broad fetch")

        # Keyword searches for better coverage
        terms = search_terms or []
        for term in terms:
            for j in _fetch_pages(headers, {'search': term, 'sort_by': 'date'}):
                if j['id'] not in seen_ids:
                    seen_ids.add(j['id'])
                    all_jobs.append(j)

        log.info(f"Findwork: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
