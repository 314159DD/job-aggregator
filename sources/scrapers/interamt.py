"""
sources/scrapers/interamt.py - Interamt (German public sector job portal)

URL: https://interamt.de/koop/app/stelle?id={id}
Auth: None (requires JSESSIONID cookie)
Format: Server-rendered HTML (Apache Wicket), dt/dd structured fields.
Strategy: Fetch search result page for recent IDs, then fetch detail pages.
Yields: ~12,000+ government/public sector jobs in Germany.
"""

import logging
import re
import time
from html import unescape

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_BASE_URL = 'https://interamt.de'
_SEARCH_URL = f'{_BASE_URL}/koop/app/trefferliste'
_DETAIL_URL = f'{_BASE_URL}/koop/app/stelle'
_REQUEST_DELAY = 0.5
_MAX_LISTINGS = 15000  # Safety cap

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; JobAggregator/1.0)',
    'Accept': 'text/html,application/xhtml+xml',
}

# Regex patterns for detail page parsing
_OG_DESC_RE = re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.IGNORECASE)
_DT_DD_RE = re.compile(
    r'<dt[^>]*>\s*(.*?)\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',
    re.DOTALL,
)
_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def _clean(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = _TAG_RE.sub(' ', html)
    text = unescape(text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def _extract_ids_from_search(session: requests.Session) -> list[int]:
    """Fetch the search results page and extract job IDs from data-field attributes."""
    all_ids = []

    try:
        # Initial request to get session cookie
        resp = session.get(_SEARCH_URL, headers=_HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            log.warning(f"  interamt search page: HTTP {resp.status_code}")
            return []

        # Extract IDs from the search results table
        # HTML structure: <td data-field="StellenangebotId" ...><a ...><span>ID</span></a></td>
        id_pattern = re.compile(
            r'data-field="StellenangebotId"[^>]*>.*?<span>(\d+)</span>',
            re.IGNORECASE | re.DOTALL,
        )
        ids = [int(m) for m in id_pattern.findall(resp.text)]
        all_ids.extend(ids)

        if ids:
            log.debug(f"  interamt search: found {len(ids)} IDs, range {min(ids)}-{max(ids)}")

    except Exception as e:
        log.warning(f"  interamt search page error: {e}")

    return all_ids


def _parse_detail(html: str, job_id: int) -> dict | None:
    """Parse an interamt job detail page into a job dict."""
    # Check if this is a valid listing (not expired/empty)
    og_match = _OG_DESC_RE.search(html)
    if og_match:
        og_desc = og_match.group(1)
        if og_desc == 'INTERAMT-Stellenangebot':
            return None  # Generic description = expired/invalid listing

    # Extract all dt/dd pairs into a dict
    fields = {}
    for dt_html, dd_html in _DT_DD_RE.findall(html):
        key = _clean(dt_html)
        val = _clean(dd_html)
        if key and val:
            fields[key] = val

    title = fields.get('Stellenbezeichnung', '')
    if not title:
        return None

    employer = fields.get('Behörde', fields.get('Behorde', ''))
    plz_ort = fields.get('Einsatzort PLZ / Ort', '')
    street = fields.get('Einsatzort Straße', fields.get('Einsatzort Strasse', ''))
    location = plz_ort or 'Germany'

    # Build salary from Besoldung/Entgelt fields
    besoldung = fields.get('Besoldung / Entgelt', '')
    salary = besoldung

    # Build description
    desc_parts = []
    if fields.get('Dienstverhältnis'):
        desc_parts.append(f"Dienstverhältnis: {fields['Dienstverhältnis']}")
    if fields.get('Teilzeit / Vollzeit'):
        desc_parts.append(f"Arbeitszeit: {fields['Teilzeit / Vollzeit']}")
    if fields.get('Wochenarbeitszeit'):
        desc_parts.append(f"Wochenarbeitszeit: {fields['Wochenarbeitszeit']}")
    if fields.get('Dienstort'):
        desc_parts.append(f"Dienstort: {fields['Dienstort']}")
    if besoldung:
        desc_parts.append(f"Besoldung/Entgelt: {besoldung}")

    return {
        'id': f"interamt_{job_id}",
        'url': f"{_DETAIL_URL}?id={job_id}",
        'title': title,
        'company': employer or None,
        'location': location,
        'description': ' | '.join(desc_parts),
        'salary': salary,
    }


class InteramtSource(BaseSource):
    name = "interamt"
    display_name = "Interamt (German Public Sector)"
    source_type = "scraper"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Interamt (public sector jobs)...")
        session = requests.Session()
        all_jobs = []
        seen_ids = set()

        # Step 1: Get recent IDs from search page to find the current ID range
        search_ids = _extract_ids_from_search(session)
        if not search_ids:
            log.warning("  interamt: could not discover IDs from search, using fallback range")
            # Fallback: try a reasonable recent range
            max_id = 1420000
        else:
            max_id = max(search_ids) + 100  # Buffer above the highest known

        # Step 2: Enumerate IDs downward from the max
        # We go backwards (newest first) and stop after enough consecutive misses
        consecutive_misses = 0
        max_consecutive_misses = 200  # Stop after 200 consecutive expired/invalid
        fetched = 0

        for job_id in range(max_id, max(max_id - _MAX_LISTINGS, 0), -1):
            try:
                resp = session.get(
                    f"{_DETAIL_URL}?id={job_id}",
                    headers=_HEADERS,
                    timeout=30,
                )

                if resp.status_code != 200:
                    consecutive_misses += 1
                    if consecutive_misses >= max_consecutive_misses:
                        log.debug(f"  interamt: {max_consecutive_misses} consecutive misses at ID {job_id}, stopping")
                        break
                    continue

                job = _parse_detail(resp.text, job_id)
                if job and job['id'] not in seen_ids:
                    seen_ids.add(job['id'])
                    all_jobs.append(job)
                    consecutive_misses = 0
                    fetched += 1
                else:
                    consecutive_misses += 1

                if consecutive_misses >= max_consecutive_misses:
                    log.debug(f"  interamt: {max_consecutive_misses} consecutive misses at ID {job_id}, stopping")
                    break

                if fetched % 100 == 0 and fetched > 0:
                    log.debug(f"  interamt: {fetched} valid jobs found so far (ID {job_id})")

                time.sleep(_REQUEST_DELAY)

            except Exception as e:
                log.warning(f"  interamt ID {job_id}: {e}")
                consecutive_misses += 1
                if consecutive_misses >= max_consecutive_misses:
                    break

        log.info(f"Interamt: {len(all_jobs)} unique public sector jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
