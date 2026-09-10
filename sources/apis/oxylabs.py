"""
sources/apis/oxylabs.py - Oxylabs (Google Jobs scraper API)

API: https://realtime.oxylabs.io/v1/queries
Auth: Username + Password
Status: Not fully tested - disabled by default.

"""

import hashlib
import logging
import time

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from search_terms import get_german_cities, get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://realtime.oxylabs.io/v1/queries'


class OxylabsSource(BaseSource):
    name = "oxylabs"
    display_name = "Oxylabs (Google Jobs)"
    source_type = "api"
    auth_type = "credentials"
    rate_limit = 5
    enabled = False  # Disabled by default - needs testing

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Oxylabs Google Jobs...")
        if not config.OXYLABS_USERNAME or not config.OXYLABS_PASSWORD:
            log.warning("Oxylabs: No credentials configured, skipping")
            return []
        # Build term×city matrix from shared intelligence (cap to keep costs down)
        _terms = get_terms(tier=1)[:10]
        _cities = get_german_cities(tier=1)[:5]
        _queries = [(t, f"{c},Germany") for c, _ in _cities for t in _terms[:2]]  # 10 combos

        all_jobs = []
        for query, location in _queries:
            try:
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}+jobs&hl=en&gl=de"
                payload = {
                    'source': 'google', 'url': url,
                    'geo_location': location, 'user_agent_type': 'desktop',
                    'render': 'html', 'parse': False,
                }
                resp = requests.post(
                    _API_URL,
                    auth=(config.OXYLABS_USERNAME, config.OXYLABS_PASSWORD),
                    json=payload, timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get('results', [{}])[0].get('content', {}).get('jobs', [])
                for j in results:
                    all_jobs.append({
                        'id': "oxylabs_" + hashlib.md5(
                            (j.get('title', '') + j.get('company', '')).encode()
                        ).hexdigest(),
                        'url': j.get('url', ''),
                        'title': j.get('title', 'Untitled'),
                        'company': j.get('company', 'Unknown'),
                        'location': j.get('location', location),
                        'description': '',
                        'salary': '',
                    })
                log.debug(f"  '{query}' in {location}: {len(results)} jobs")
                time.sleep(2)
            except Exception as e:
                log.warning(f"  '{query}' in {location} error: {e}")
                continue
        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"Oxylabs: {len(unique)} unique jobs")
        return unique

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
