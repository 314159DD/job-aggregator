"""
sources/scrapers/lehrstellen_radar.py - HWK Lehrstellen-Radar (apprenticeships)

URL: https://www.lehrstellen-radar.de/5100,90,lsrlist.html
Auth: None
Format: Server-rendered HTML, paginated (15 results/page).
Strategy: Iterate over major PLZ regions, paginate, parse listings + inline detail divs.
Yields: Apprenticeship + internship listings from 53 HWKs (Handwerkskammern).
"""

import hashlib
import logging
import re
import time
from html import unescape

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_BASE_URL = 'https://www.lehrstellen-radar.de'
_SEARCH_URL = f'{_BASE_URL}/5100,90,lsrlist.html'
_ITEMS_PER_PAGE = 15
_MAX_PAGES_PER_REGION = 100  # Safety cap per PLZ region
_REQUEST_DELAY = 0.5

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; JobAggregator/1.0)',
    'Accept': 'text/html,application/xhtml+xml',
}

# Major PLZ prefixes covering all of Germany (10xxx through 99xxx)
# Using central PLZ per region with large radius to cover the whole country
_SEARCH_REGIONS = [
    ('10115', 100),  # Berlin / Brandenburg / MV
    ('20095', 100),  # Hamburg / SH / Niedersachsen Nord
    ('30159', 100),  # Hannover / Niedersachsen Süd
    ('40210', 100),  # Düsseldorf / NRW West
    ('44135', 100),  # Dortmund / NRW Ost
    ('50667', 100),  # Köln / NRW Süd / Rheinland
    ('60311', 100),  # Frankfurt / Hessen
    ('70173', 100),  # Stuttgart / BaWü Nord
    ('79098', 100),  # Freiburg / BaWü Süd
    ('80331', 100),  # München / Bayern Süd
    ('90402', 100),  # Nürnberg / Bayern Nord / Franken
    ('01067', 100),  # Dresden / Sachsen
    ('04109', 100),  # Leipzig / Sachsen-Anhalt / Thüringen
    ('66111', 100),  # Saarbrücken / Saarland / Pfalz
    ('54290', 100),  # Trier / Rheinland-Pfalz
    ('28195', 100),  # Bremen
]

_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def _clean(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = _TAG_RE.sub(' ', html)
    text = unescape(text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def _make_id(result_id: str) -> str:
    return f"hwk_{hashlib.md5(result_id.encode()).hexdigest()[:12]}"


def _parse_listings(html: str) -> list[dict]:
    """Parse all listings from a search results page."""
    jobs = []

    # Find all list items: <a class="list-group-item" data-resultid="91_2579">
    item_pattern = re.compile(
        r'<a\s+class="list-group-item"[^>]*data-resultid="(\d+_\d+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    # Find corresponding detail divs (nested structure, grab everything up to next detail or end)
    detail_pattern = re.compile(
        r'<div\s+id="detail_(\d+_\d+)"[^>]*class="[^"]*lsrdetail[^"]*"[^>]*>(.*?)(?=<div\s+id="detail_|<div\s+class="[^"]*text-center[^"]*")',
        re.DOTALL,
    )

    # Parse detail blocks into a dict keyed by result_id
    details = {}
    for result_id, detail_html in detail_pattern.findall(html):
        details[result_id] = detail_html

    # Parse each listing
    for result_id, item_html in item_pattern.findall(html):
        try:
            # Extract title from <strong>
            title_match = re.search(r'<strong>(.*?)</strong>', item_html)
            title = _clean(title_match.group(1)) if title_match else ''
            if not title:
                continue

            # Extract location from list-group-item-text
            loc_match = re.search(r'class="list-group-item-text">(.*?)</p>', item_html, re.DOTALL)
            location = ''
            if loc_match:
                location = _clean(loc_match.group(1)).split('\n')[0].strip()

            # Parse the detail div for company and contact info
            company = ''
            detail_html = details.get(result_id, '')
            if detail_html:
                # Structure: <p><strong>Firma</strong></p><span>Company Name</span>
                firma_match = re.search(
                    r'<strong>Firma</strong>\s*</p>\s*<span[^>]*>(.*?)</span>',
                    detail_html, re.DOTALL | re.IGNORECASE,
                )
                if firma_match:
                    company = _clean(firma_match.group(1))

            # Build URL - use the HWK detail link if available
            hwk_link_match = re.search(r'href="(https?://[^"]*hwk[^"]*)"', detail_html) if detail_html else None
            url = hwk_link_match.group(1) if hwk_link_match else ''

            # Fallback URL
            if not url:
                parts = result_id.split('_')
                if len(parts) == 2:
                    hwk_id, listing_id = parts
                    url = f"https://www.lehrstellen-radar.de/5100,0,jpguestdetail.html?id={listing_id}"

            # Description from detail
            desc_parts = []
            fachrichtung_match = re.search(r'Fachrichtung:\s*(.*?)(?:</p>|<br)', detail_html or '', re.IGNORECASE)
            if fachrichtung_match:
                desc_parts.append(f"Fachrichtung: {_clean(fachrichtung_match.group(1))}")

            vorbildung_match = re.search(r'Vorbildungen?:?\s*</(?:strong|p)>\s*<ul>(.*?)</ul>', detail_html or '', re.DOTALL | re.IGNORECASE)
            if vorbildung_match:
                items = re.findall(r'<li>(.*?)</li>', vorbildung_match.group(1))
                if items:
                    desc_parts.append(f"Vorbildung: {', '.join(_clean(i) for i in items)}")

            job = {
                'id': _make_id(result_id),
                'url': url,
                'title': title,
                'company': company or None,
                'location': location or 'Germany',
                'description': ' | '.join(desc_parts),
                'salary': '',
            }
            jobs.append(job)

        except Exception as e:
            log.warning(f"  HWK listing parse error ({result_id}): {e}")

    return jobs


class LehrstellenRadarSource(BaseSource):
    name = "lehrstellen_radar"
    display_name = "HWK Lehrstellen-Radar (Apprenticeships)"
    source_type = "scraper"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from HWK Lehrstellen-Radar...")
        session = requests.Session()
        all_jobs = []
        seen_ids = set()

        for plz, radius in _SEARCH_REGIONS:
            for page in range(1, _MAX_PAGES_PER_REGION + 1):
                try:
                    params = {
                        'search-fromsearchform': '1',
                        'search-ls': '1',    # Lehrstellen
                        'search-pr': '1',    # Praktika
                        'search-plz': plz,
                        'search-radius': str(radius),
                        'page': str(page),
                    }

                    resp = session.get(
                        _SEARCH_URL, params=params,
                        headers=_HEADERS, timeout=30,
                    )

                    if resp.status_code != 200:
                        log.debug(f"  PLZ {plz} page {page}: HTTP {resp.status_code}, stopping")
                        break

                    jobs = _parse_listings(resp.text)
                    if not jobs:
                        break

                    new_count = 0
                    for job in jobs:
                        if job['id'] not in seen_ids:
                            seen_ids.add(job['id'])
                            all_jobs.append(job)
                            new_count += 1

                    if new_count == 0:
                        # All jobs on this page were already seen (overlap from other regions)
                        break

                    if len(jobs) < _ITEMS_PER_PAGE:
                        break

                    time.sleep(_REQUEST_DELAY)

                except Exception as e:
                    log.warning(f"  HWK PLZ {plz} page {page}: {e}")
                    break

            log.debug(f"  HWK PLZ {plz}: {len(all_jobs)} total jobs so far")

        log.info(f"Lehrstellen-Radar: {len(all_jobs)} unique apprenticeship listings")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
