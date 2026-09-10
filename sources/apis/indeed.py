"""
sources/apis/indeed.py - Indeed

API: http://api.indeed.com/ads/apisearch
Auth: Publisher ID (INDEED_PUBLISHER_ID)
Status: Code ready, needs Publisher ID - disabled by default.

"""

import logging
import time

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from search_terms import get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)


class IndeedSource(BaseSource):
    name = "indeed"
    display_name = "Indeed"
    source_type = "api"
    auth_type = "api_key"
    rate_limit = 30
    enabled = False  # Disabled by default - needs Publisher ID

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Indeed...")
        if not config.INDEED_PUBLISHER_ID:
            log.warning("Indeed: No Publisher ID configured, skipping")
            return []
        # Build queries from shared intelligence - append "Germany" to each term
        _queries = [f"{t} Germany" for t in get_terms(tier=1)[:20]]

        all_jobs = []
        for query in _queries:
            try:
                params = {
                    'publisher': config.INDEED_PUBLISHER_ID,
                    'q': query, 'l': 'Germany', 'format': 'json',
                    'limit': 25, 'v': '2',
                    'userip': '1.2.3.4', 'useragent': 'Mozilla/5.0',
                }
                resp = requests.get('http://api.indeed.com/ads/apisearch', params=params, timeout=60)
                results = resp.json().get('results', [])
                for j in results:
                    all_jobs.append({
                        'id': f"indeed_{j.get('jobkey','')}",
                        'url': j.get('url', ''),
                        'title': j.get('jobtitle', 'Untitled'),
                        'company': j.get('company', 'Unknown'),
                        'location': j.get('formattedLocation', 'Germany'),
                        'description': j.get('snippet', ''),
                        'salary': '',
                    })
                log.debug(f"  '{query}': {len(results)} jobs")
                time.sleep(1)
            except Exception as e:
                log.warning(f"  '{query}' error: {e}")
                continue
        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"Indeed: {len(unique)} unique jobs")
        return unique

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
