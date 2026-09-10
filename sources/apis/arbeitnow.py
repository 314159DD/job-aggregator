"""
sources/apis/arbeitnow.py - Arbeitnow

API: https://www.arbeitnow.com/api/job-board-api
Auth: None - Pagination: page 1-10

"""

import logging

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://www.arbeitnow.com/api/job-board-api'


class ArbeitnowSource(BaseSource):
    name = "arbeitnow"
    display_name = "Arbeitnow"
    source_type = "api"
    auth_type = "none"
    rate_limit = 30
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Arbeitnow...")
        all_jobs = []
        try:
            resp = requests.get(_API_URL, timeout=30)
            data = resp.json()
            total_pages = data.get('meta', {}).get('last_page', 1)
            pages_to_fetch = min(total_pages, 10)

            for page in range(1, pages_to_fetch + 1):
                try:
                    resp = requests.get(f"{_API_URL}?page={page}", timeout=30)
                    page_data = resp.json().get('data', [])
                    for j in page_data:
                        all_jobs.append({
                            'id': j.get('slug'),
                            'url': j.get('url'),
                            'title': j.get('title'),
                            'company': j.get('company_name'),
                            'location': j.get('location'),
                            'description': j.get('description'),
                        })
                    log.debug(f"  Page {page}/{pages_to_fetch}: {len(page_data)} jobs")
                except Exception as e:
                    log.warning(f"  Page {page} error: {e}")
                    continue
        except Exception as e:
            log.error(f"Arbeitnow error: {e}")
        log.info(f"Arbeitnow: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
