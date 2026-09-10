"""
sources/feeds/devitjobs.py - DevITjobs UK

Feed: https://devitjobs.uk/job_feed.xml
Auth: None
Format: RSS 2.0 XML
Strategy: fetch full feed, parse all <item> elements, no pagination needed.
"""

import hashlib
import logging
import re
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

from aggregator.normalisation import normalise_job
from sources.base import BaseSource, safe_get

log = logging.getLogger(__name__)

_FEED_URL = 'https://devitjobs.uk/job_feed.xml'


def _text(item: Element, tag: str) -> str:
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ''


def _make_id(url: str) -> str:
    return f"devitjobs_{hashlib.md5(url.encode()).hexdigest()[:12]}"


def _parse_date(date_str: str) -> str | None:
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return None


def _clean_author(raw: str) -> str:
    """Strip email addresses from author strings like 'jobs@example.com (Company Name)'."""
    cleaned = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]+', '', raw)
    cleaned = re.sub(r'[()]', '', cleaned)
    return cleaned.strip()


def _parse(item: Element) -> dict:
    url = _text(item, 'link')
    raw_author = _text(item, 'author') or _text(item, 'company') or ''
    company = _clean_author(raw_author) if raw_author else ''
    return {
        'id': _make_id(url),
        'url': url,
        'title': _text(item, 'title'),
        'company': company or None,
        'location': _text(item, 'location') or None,
        'description': _text(item, 'description'),
        'salary': _text(item, 'salary') or None,
        'posted_at': _parse_date(_text(item, 'pubDate')),
    }


class DevITjobsSource(BaseSource):
    name = "devitjobs"
    display_name = "DevITjobs UK"
    source_type = "feed"
    auth_type = "none"
    rate_limit = 10
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from DevITjobs UK...")
        all_jobs = []
        try:
            resp = safe_get(_FEED_URL, timeout=30)
            root = ET.fromstring(resp.content)
            items = root.findall('.//item')
            log.debug(f"  DevITjobs: {len(items)} items in feed")
            for item in items:
                try:
                    job = _parse(item)
                    if job['url']:
                        all_jobs.append(job)
                except Exception as e:
                    log.warning(f"  DevITjobs item parse error: {e}")
        except Exception as e:
            log.error(f"DevITjobs error: {e}")
        log.info(f"DevITjobs: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
