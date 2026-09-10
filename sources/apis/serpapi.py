"""
sources/apis/serpapi.py - SerpAPI (Google Jobs)

API: https://serpapi.com/search.json
Auth: API Key (SERPAPI_KEY)
Free tier: 250 searches/month

"""

import logging
import time

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from search_terms import get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://serpapi.com/search.json'


class SerpAPISource(BaseSource):
    name = "serpapi"
    display_name = "SerpAPI (Google Jobs)"
    source_type = "api"
    auth_type = "api_key"
    rate_limit = 10
    enabled = False  # Paid API - disabled by default

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from SerpAPI Google Jobs...")
        if not config.SERPAPI_KEY:
            log.warning("SerpAPI: No API key configured, skipping")
            return []
        all_jobs = []
        # Build queries: use shared terms, append "Germany", cap at 20 to stay within free tier
        _terms = search_terms[:10] if search_terms else get_terms(tier=1)[:20]
        queries = [f"{t} Germany" for t in _terms]
        for query in queries:
            try:
                page = 1
                next_token = None
                while page <= 10:
                    params = {
                        'engine': 'google_jobs', 'q': query, 'hl': 'en',
                        'gl': 'de', 'api_key': config.SERPAPI_KEY,
                    }
                    if next_token:
                        params['next_page_token'] = next_token
                    resp = requests.get(_API_URL, params=params, timeout=60)
                    data = resp.json()
                    if 'error' in data:
                        log.warning(f"SerpAPI error for '{query}': {data['error']}")
                        break
                    jobs = data.get('jobs_results', [])
                    if not jobs:
                        break
                    for j in jobs:
                        url = (j.get('apply_options') or [{}])[0].get('link', '') or j.get('share_link', '')
                        all_jobs.append({
                            'id': f"google_{j.get('job_id','')}",
                            'url': url,
                            'title': j.get('title', 'Untitled'),
                            'company': j.get('company_name', 'Unknown'),
                            'location': j.get('location', 'Germany'),
                            'description': j.get('description', ''),
                            'salary': j.get('detected_extensions', {}).get('salary', ''),
                        })
                    log.debug(f"  '{query}' page {page}: {len(jobs)} jobs")
                    next_token = data.get('serpapi_pagination', {}).get('next_page_token')
                    if not next_token:
                        break
                    page += 1
                    time.sleep(1)
                time.sleep(1)
            except Exception as e:
                log.warning(f"  '{query}' error: {e}")
                continue
        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"SerpAPI: {len(unique)} unique jobs")
        return unique

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
