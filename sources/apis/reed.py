"""
sources/apis/reed.py - Reed

API: https://www.reed.co.uk/api/1.0/search
Auth: BasicAuth(REED_API_KEY, "")
Strategy: search each term × [London, Remote, UK]; paginate via resultsToSkip.
Rate: ~4,000 calls/month (free tier)
"""

import logging

import requests
from requests.auth import HTTPBasicAuth

from aggregator import config
from aggregator.normalisation import normalise_job
from search_terms import get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://www.reed.co.uk/api/1.0/search'
_PAGE_SIZE = 100
_MAX_PAGES = 10
_LOCATIONS = ['London', 'Remote', 'Manchester', 'Edinburgh', 'Bristol']


def _parse(j: dict) -> dict:
    sal_min = j.get('minimumSalary')
    sal_max = j.get('maximumSalary')
    return {
        'id': f"reed_{j.get('jobId')}",
        'url': j.get('jobUrl'),
        'title': j.get('jobTitle'),
        'company': j.get('employerName'),
        'location': j.get('locationName'),
        'description': j.get('jobDescription', ''),
        'posted_at': j.get('date') or j.get('datePosted') or None,
        'salary_min': int(sal_min) if sal_min else None,
        'salary_max': int(sal_max) if sal_max else None,
        'salary_currency': j.get('currency') or 'GBP',
        'salary_period': 'year',
        'employment_type': j.get('partTime') and 'part-time' or j.get('contractType') or None,
    }


class ReedSource(BaseSource):
    name = "reed"
    display_name = "Reed"
    source_type = "api"
    auth_type = "api_key"
    rate_limit = 30
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Reed...")
        api_key = config.REED_API_KEY
        if not api_key:
            log.error("Reed: REED_API_KEY not set")
            return []

        auth = HTTPBasicAuth(api_key, '')
        # Reed is UK-only - English terms, tier 1
        terms = search_terms or get_terms(tier=1, language="en")
        all_jobs = []
        seen_ids = set()

        for term in terms:
            for loc in _LOCATIONS:
                skip = 0
                for _ in range(_MAX_PAGES):
                    try:
                        params = {
                            'keywords': term,
                            'locationName': loc,
                            'distanceFromLocation': 50,
                            'resultsToTake': _PAGE_SIZE,
                            'resultsToSkip': skip,
                        }
                        resp = requests.get(_API_URL, auth=auth, params=params, timeout=30)
                        resp.raise_for_status()
                        results = resp.json().get('results', [])
                        if not results:
                            break
                        for j in results:
                            jid = f"reed_{j.get('jobId')}"
                            if jid not in seen_ids:
                                seen_ids.add(jid)
                                all_jobs.append(_parse(j))
                        log.debug(f"  Reed '{term}' in {loc} skip={skip}: {len(results)} jobs")
                        if len(results) < _PAGE_SIZE:
                            break
                        skip += _PAGE_SIZE
                    except Exception as e:
                        log.warning(f"  Reed '{term}' in {loc} skip={skip}: {e}")
                        break

        log.info(f"Reed: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
