"""
sources/apis/arbeitsamt.py - Arbeitsamt (German Federal Employment Agency)

API: https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs
Auth: Public API key (no registration needed)

Two strategies:
  1. berufsfeld (default): Iterate all 144 occupation-field codes for
     categorical, systematic drain. No keywords needed - every job in the
     BA database is tagged with exactly one berufsfeld.
  2. keyword: Legacy keyword × city matrix, kept as fallback.

The API has a hard cap of 10,000 results per query (100 pages × 100).
For berufselds with >10K jobs, we split by city to get complete coverage.
"""

import logging
import time

import requests

from aggregator.normalisation import normalise_job
from search_terms import get_german_cities, get_terms
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs'
_HEADERS = {'X-API-Key': 'jobboerse-jobsuche', 'Accept': 'application/json'}
_MAX_PAGES = 100            # API hard cap: page 100 × 100 = 10,000 results
_CITY_SPLIT_THRESHOLD = 10000  # Use city-level queries for berufselds above this
_DELAY_BETWEEN_REQUESTS = 0    # seconds; set >0 if rate-limited

# Default strategy
_STRATEGY = 'berufsfeld'    # 'berufsfeld' or 'keyword'


def _parse_raw(j: dict) -> dict:
    ao = j.get('arbeitsort', {})
    loc = f"{ao.get('plz', '')} {ao.get('ort', '')}".strip()
    desc = '\n\n'.join(filter(None, [
        f"Beruf: {j.get('beruf', 'N/A')}",
        j.get('stellenbeschreibung', ''),
    ]))
    ref = j.get('refnr', '')
    return {
        'id': f"arbeitsamt_{ref}",
        'url': f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
        'title': j.get('titel') or j.get('beruf', 'Untitled'),
        'company': j.get('arbeitgeber', 'Unknown'),
        'location': loc or 'Germany',
        'description': desc,
        'salary': j.get('verguetung', ''),
    }


def _paginate(params: dict, label: str, max_pages: int = _MAX_PAGES) -> list[dict]:
    """Fetch a single query with full pagination. Returns raw parsed dicts."""
    jobs = []
    try:
        params = {**params, 'size': 100, 'page': 1}
        resp = requests.get(_API_URL, headers=_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        page_jobs = data.get('stellenangebote', [])
        if not page_jobs:
            return []

        for j in page_jobs:
            if j.get('refnr'):
                jobs.append(_parse_raw(j))

        max_results = int(data.get('maxErgebnisse') or 0)
        total_pages = min(-(-max_results // 100), max_pages)
        log.debug(f"  {label}: {max_results} total, paginating {total_pages} pages")

        for page in range(2, total_pages + 1):
            if _DELAY_BETWEEN_REQUESTS:
                time.sleep(_DELAY_BETWEEN_REQUESTS)
            try:
                params['page'] = page
                r = requests.get(_API_URL, headers=_HEADERS, params=params, timeout=30)
                r.raise_for_status()
                pj = r.json().get('stellenangebote', [])
                if not pj:
                    break
                for j in pj:
                    if j.get('refnr'):
                        jobs.append(_parse_raw(j))
            except Exception as e:
                log.warning(f"  {label} page {page}: {e}")
                break

    except Exception as e:
        log.warning(f"  {label}: {e}")

    return jobs


def _discover_berufsfeld_codes() -> list[tuple[str, int]]:
    """One API call to discover all berufsfeld values and their job counts.

    Returns list of (berufsfeld_name, job_count) sorted by count descending.
    """
    try:
        resp = requests.get(
            _API_URL, headers=_HEADERS, timeout=30,
            params={'angebotsart': 1, 'size': 1, 'page': 1},
        )
        resp.raise_for_status()
        data = resp.json()
        counts = data.get('facetten', {}).get('berufsfeld', {}).get('counts', {})
        result = [(name, count) for name, count in counts.items()]
        result.sort(key=lambda x: x[1], reverse=True)
        log.info(f"Discovered {len(result)} berufsfeld codes, {sum(c for _, c in result):,} total jobs")
        return result
    except Exception as e:
        log.error(f"Failed to discover berufsfeld codes: {e}")
        return []


class ArbeitsamtSource(BaseSource):
    name = "arbeitsamt"
    display_name = "Arbeitsamt (German Federal Employment Agency)"
    source_type = "api"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None, strategy=None) -> list:
        strategy = strategy or _STRATEGY

        if strategy == 'berufsfeld' and not search_terms:
            return self._fetch_by_berufsfeld(locations)
        else:
            return self._fetch_by_keyword(search_terms, locations)

    def _fetch_by_berufsfeld(self, locations=None) -> list:
        """Systematic drain: iterate all 144 occupation-field codes.

        For berufselds with ≤10K jobs: single national query (no city filter).
        For berufselds with >10K jobs: additional city-level queries to capture
        the overflow beyond the API's 10K hard cap.
        """
        log.info("Arbeitsamt: berufsfeld strategy - discovering occupation codes...")
        berufsfelds = _discover_berufsfeld_codes()
        if not berufsfelds:
            log.warning("No berufsfeld codes found, falling back to keyword strategy")
            return self._fetch_by_keyword(None, locations)

        # Cities for large-berufsfeld splitting
        cities = locations or get_german_cities(tier=1)
        all_jobs = []
        api_calls = 0

        for i, (bf_name, bf_count) in enumerate(berufsfelds):
            base_params = {'angebotsart': 1, 'berufsfeld': bf_name}

            # National query (no city filter) - catches up to 10K
            national_jobs = _paginate(base_params, f"[{i+1}/{len(berufsfelds)}] {bf_name}")
            all_jobs.extend(national_jobs)
            api_calls += min(-(-min(bf_count, 10000) // 100), _MAX_PAGES)

            # For large berufselds, also query per city to get overflow
            if bf_count > _CITY_SPLIT_THRESHOLD:
                for city, radius in cities:
                    city_params = {**base_params, 'wo': city, 'umkreis': radius}
                    city_jobs = _paginate(city_params, f"  {bf_name} → {city}")
                    all_jobs.extend(city_jobs)

            if (i + 1) % 20 == 0:
                log.info(f"  berufsfeld progress: {i+1}/{len(berufsfelds)}, {len(all_jobs)} raw jobs collected")

        # Dedup by refnr
        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"Arbeitsamt berufsfeld: {len(unique)} unique jobs from {len(all_jobs)} raw ({len(berufsfelds)} occupation fields)")
        return unique

    def _fetch_by_keyword(self, search_terms=None, locations=None) -> list:
        """Legacy keyword × city matrix strategy."""
        log.info("Arbeitsamt: keyword strategy...")
        all_jobs = []
        terms = search_terms or get_terms(tier=2, language="de")
        locs = locations or get_german_cities(tier=2)

        for loc, radius in locs:
            for term in terms:
                params = {
                    'was': term, 'wo': loc, 'umkreis': radius,
                    'arbeitszeit': 'vz;tz;ho;schw;mj',
                    'angebotsart': 1,
                }
                jobs = _paginate(params, f"'{term}' in {loc}", max_pages=20)
                all_jobs.extend(jobs)

        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"Arbeitsamt keyword: {len(unique)} unique jobs")
        return unique

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
