"""
sources/apis/themuse.py - TheMuse

API: https://www.themuse.com/api/public/jobs
Auth: None (500 req/hour unauthenticated)
Strategy: fetch first _MAX_PAGES pages only. The API reports ~22k total pages
(all jobs globally); fetching all would take hours and exhaust the rate limit.
Stop immediately on 429 - retrying rate-limited pages just makes it worse.
"""

import logging
import time

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://www.themuse.com/api/public/jobs'
_MAX_PAGES = 10   # ~200 jobs; increase only if TheMuse becomes filterable by location
_PAGE_DELAY = 0.2  # seconds between requests to stay within 500 req/hour


def _parse(j: dict) -> dict:
    return {
        'id': f"muse_{j.get('id')}",
        'url': j.get('refs', {}).get('landing_page'),
        'title': j.get('name'),
        'company': j.get('company', {}).get('name'),
        'location': (j.get('locations') or [{}])[0].get('name'),
        'description': j.get('contents'),
    }


class TheMuseSource(BaseSource):
    name = "themuse"
    display_name = "TheMuse"
    source_type = "api"
    auth_type = "none"
    rate_limit = 30
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from TheMuse (first %d pages)...", _MAX_PAGES)
        all_jobs = []
        try:
            # Page 0: get first batch
            resp = requests.get(_API_URL, params={'page': 0}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            page_count = int(data.get('page_count') or 1)
            for j in data.get('results', []):
                all_jobs.append(_parse(j))
            log.debug(f"  TheMuse: {page_count} total pages in API (capped at {_MAX_PAGES})")

            # Fetch remaining pages up to _MAX_PAGES
            for page in range(1, min(page_count, _MAX_PAGES)):
                time.sleep(_PAGE_DELAY)
                try:
                    r = requests.get(_API_URL, params={'page': page}, timeout=30)
                    if r.status_code == 429:
                        log.warning(f"  TheMuse rate-limited at page {page}, stopping early")
                        break
                    r.raise_for_status()
                    jobs = r.json().get('results', [])
                    if not jobs:
                        break
                    for j in jobs:
                        all_jobs.append(_parse(j))
                    log.debug(f"  Page {page}: {len(jobs)} jobs")
                except Exception as e:
                    log.warning(f"  Page {page} error: {e}")
                    break  # any error past page 0 → stop, don't keep hammering

        except Exception as e:
            log.error(f"TheMuse error: {e}")

        log.info(f"TheMuse: {len(all_jobs)} total jobs fetched")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
