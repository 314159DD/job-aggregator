"""
sources/feeds/praktischarzt.py - praktischArzt (German healthcare job board)

Feed: https://www.praktischarzt.de/feed/?paged={page}
Auth: None
Format: WordPress RSS 2.0, paginated (10 items/page, ~560 pages)
Strategy: Paginate through all RSS pages, parse job items.
Yields: ~5,000+ medical/healthcare jobs in Germany.
"""

import hashlib
import logging
import re
import time
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

from aggregator.normalisation import normalise_job
from sources.base import BaseSource, safe_get

log = logging.getLogger(__name__)

_FEED_URL = 'https://www.praktischarzt.de/feed/'
_ITEMS_PER_PAGE = 10
_MAX_PAGES = 600  # Safety cap (~6,000 jobs max)
_REQUEST_DELAY = 0.3  # Be respectful

# Namespace map for dc:creator
_NS = {'dc': 'http://purl.org/dc/elements/1.1/'}


def _text(item: Element, tag: str, ns: dict | None = None) -> str:
    el = item.find(tag, ns or {})
    return el.text.strip() if el is not None and el.text else ''


def _make_id(guid: str) -> str:
    return f"praktischarzt_{hashlib.md5(guid.encode()).hexdigest()[:12]}"


def _parse_date(date_str: str) -> str | None:
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return None


def _extract_location(desc_html: str) -> str:
    """Extract location from description HTML like '<b>Standort</b>: 59519 Möhnesee'."""
    match = re.search(r'Standort</b>:\s*(.+?)(?:</p>|<br)', desc_html)
    if match:
        return match.group(1).strip()
    return 'Germany'


def _extract_stellenart(desc_html: str) -> str:
    """Extract job type from description HTML like '<b>Stellenart</b>: Assistenzarzt'."""
    match = re.search(r'Stellenart</b>:\s*(.+?)(?:</p>|<br)', desc_html)
    if match:
        return match.group(1).strip()
    return ''


def _parse(item: Element) -> dict:
    url = _text(item, 'link')
    guid = _text(item, 'guid') or url
    company = _text(item, 'dc:creator', _NS)
    desc_html = _text(item, 'description')
    location = _extract_location(desc_html)
    stellenart = _extract_stellenart(desc_html)
    title = _text(item, 'title')

    description = f"Stellenart: {stellenart}" if stellenart else ''

    return {
        'id': _make_id(guid),
        'url': url,
        'title': title,
        'company': company or None,
        'location': location,
        'description': description,
        'salary': '',
        'posted_at': _parse_date(_text(item, 'pubDate')),
    }


class PraktischArztSource(BaseSource):
    name = "praktischarzt"
    display_name = "praktischArzt (Healthcare Jobs Germany)"
    source_type = "feed"
    auth_type = "none"
    rate_limit = 120
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from praktischArzt RSS feed...")
        all_jobs = []
        seen_ids = set()

        for page in range(1, _MAX_PAGES + 1):
            try:
                url = f"{_FEED_URL}?paged={page}"
                resp = safe_get(url, timeout=30)
                root = ET.fromstring(resp.content)
                items = root.findall('.//item')

                if not items:
                    log.debug(f"  Page {page}: no items, stopping")
                    break

                for item in items:
                    try:
                        job = _parse(item)
                        if job['url'] and job['id'] not in seen_ids:
                            seen_ids.add(job['id'])
                            all_jobs.append(job)
                    except Exception as e:
                        log.warning(f"  praktischArzt item parse error: {e}")

                if len(items) < _ITEMS_PER_PAGE:
                    log.debug(f"  Page {page}: partial page ({len(items)} items), stopping")
                    break

                if page % 50 == 0:
                    log.debug(f"  praktischArzt: {len(all_jobs)} jobs after {page} pages")

                time.sleep(_REQUEST_DELAY)

            except ET.ParseError:
                log.debug(f"  Page {page}: XML parse error, stopping")
                break
            except Exception as e:
                log.warning(f"  praktischArzt page {page} error: {e}")
                break

        log.info(f"praktischArzt: {len(all_jobs)} unique jobs from {page} pages")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
