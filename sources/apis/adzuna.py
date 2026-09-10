"""
sources/apis/adzuna.py - Adzuna

API: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Auth: app_id + app_key as query params
Rate: 250 calls/MONTH free tier - budget: 60 calls/run × 4 runs/month = 240 calls
Strategy: DE only, capped at 60 API calls/run, dedup by id.
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from search_terms import get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)

_BASE_URL = 'https://api.adzuna.com/v1/api/jobs/{country}/search/{page}'
_COUNTRIES = ['de']
_MAX_PAGES = 1       # 1 page per term/country combo
_PAGE_SIZE = 50      # max per call
_MAX_CALLS_PER_RUN = 60  # 250/month ÷ 4 runs/month ≈ 60


def _parse(j: dict, country: str) -> dict:
    currency = 'GBP' if country == 'gb' else 'EUR'
    return {
        'id': f"adzuna_{j.get('id')}",
        'url': j.get('redirect_url'),
        'title': j.get('title'),
        'company': j.get('company', {}).get('display_name'),
        'location': j.get('location', {}).get('display_name'),
        'description': j.get('description', ''),
        'posted_at': j.get('created'),
        'salary_min': int(j['salary_min']) if j.get('salary_min') is not None else None,
        'salary_max': int(j['salary_max']) if j.get('salary_max') is not None else None,
        'salary_currency': currency,
        'salary_period': 'year',
    }


class AdzunaSource(BaseSource):
    name = "adzuna"
    display_name = "Adzuna"
    source_type = "api"
    auth_type = "api_key"
    rate_limit = 10
    enabled = True
    min_interval_hours = 168  # weekly - 4 runs/month × 60 calls = 240 ≤ 250 free tier

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Adzuna...")
        app_id = config.ADZUNA_APP_ID
        app_key = config.ADZUNA_APP_KEY
        if not app_id or not app_key:
            log.error("Adzuna: ADZUNA_APP_ID or ADZUNA_APP_KEY not set")
            return []

        terms = search_terms or get_terms(tier=1)
        all_jobs = []
        seen_ids = set()
        api_calls = 0

        for country in _COUNTRIES:
            for term in terms:
                if api_calls >= _MAX_CALLS_PER_RUN:
                    log.info(f"Adzuna: hit {_MAX_CALLS_PER_RUN} call budget, stopping early")
                    break
                for page in range(1, _MAX_PAGES + 1):
                    if api_calls >= _MAX_CALLS_PER_RUN:
                        break
                    try:
                        url = _BASE_URL.format(country=country, page=page)
                        params = {
                            'app_id': app_id,
                            'app_key': app_key,
                            'what': term,
                            'results_per_page': _PAGE_SIZE,
                            'sort_by': 'date',
                            'content-type': 'application/json',
                        }
                        resp = requests.get(url, params=params, timeout=30)
                        api_calls += 1
                        resp.raise_for_status()
                        results = resp.json().get('results', [])
                        if not results:
                            break
                        for j in results:
                            jid = f"adzuna_{j.get('id')}"
                            if jid not in seen_ids:
                                seen_ids.add(jid)
                                all_jobs.append(_parse(j, country))
                        log.debug(f"  Adzuna '{term}' {country} p{page}: {len(results)} jobs ({api_calls}/{_MAX_CALLS_PER_RUN} calls)")
                        if len(results) < _PAGE_SIZE:
                            break
                    except Exception as e:
                        log.warning(f"  Adzuna '{term}' {country} p{page}: {e}")
                        break
            else:
                continue
            break

        log.info(f"Adzuna: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
