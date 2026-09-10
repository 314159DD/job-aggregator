"""
sources/ats/personio.py - Personio ATS feed drain.

API: https://{slug}.jobs.personio.de/search.json (preferred - always valid JSON)
Fallback: https://{slug}.jobs.personio.de/xml (some feeds have malformed XML)
Auth: None (public)

Very popular in DACH market (Germany, Austria, Switzerland).
"""

import logging

import requests

from aggregator import config
from aggregator.normalisation import normalise_job
from aggregator.rate_limiter import RateLimiter
from sources.ats._registry import get_companies, record_failure, update_crawl_result
from sources.base import BaseSource

log = logging.getLogger(__name__)

_TIMEOUT = 20
_DELAY = float(getattr(config, 'ATS_REQUEST_DELAY', 0.5))
_limiter = RateLimiter()


def _parse_job_json(job: dict, slug: str) -> dict:
    """Convert Personio JSON job to raw job dict."""
    company = job.get('subcompany') or job.get('company') or slug

    # Build location from office(s)
    offices = job.get('offices')
    if isinstance(offices, list) and offices:
        location = ', '.join(offices)
    else:
        location = job.get('office') or None

    # Map employment type
    emp_raw = job.get('employment_type', '')
    emp_type = emp_raw  # normalisation layer handles mapping

    # Map seniority
    seniority_raw = job.get('seniority', '')

    # Build description from the description field
    description = job.get('description') or ''

    url = f"https://{slug}.jobs.personio.de/job/{job.get('id')}"

    return {
        'id': f"personio_{slug}_{job.get('id')}",
        'url': url,
        'title': job.get('name', 'Untitled'),
        'company': company,
        'location': location,
        'description': description,
        'posted_at': job.get('createdAt') or None,
        'source_job_id': str(job.get('id', '')),
        '_department': job.get('department') or job.get('category') or '',
        '_schedule': job.get('schedule', ''),
        '_seniority': seniority_raw,
        '_employment_type': emp_type,
        '_keywords': job.get('keywords', ''),
    }


def _parse_job_xml(position, slug: str) -> dict | None:
    """Convert Personio XML <position> element to raw job dict."""
    try:

        def _text(tag: str) -> str:
            el = position.find(tag)
            return el.text.strip() if el is not None and el.text else ''

        pid = _text('id')
        if not pid:
            return None

        # Gather description sections
        desc_parts = []
        for jd in position.findall('.//jobDescription'):
            name = jd.findtext('name', '').strip()
            value = jd.findtext('value', '').strip()
            if name and value:
                desc_parts.append(f"<h3>{name}</h3>\n{value}")
            elif value:
                desc_parts.append(value)

        company = _text('subcompany') or slug
        url = f"https://{slug}.jobs.personio.de/job/{pid}"

        return {
            'id': f"personio_{slug}_{pid}",
            'url': url,
            'title': _text('name') or 'Untitled',
            'company': company,
            'location': _text('office') or None,
            'description': '\n\n'.join(desc_parts),
            'posted_at': _text('createdAt') or None,
            'source_job_id': pid,
        }
    except Exception as e:
        log.debug(f"XML parse error for position in {slug}: {e}")
        return None


class PersonioSource(BaseSource):
    name = "personio"
    display_name = "Personio (ATS)"
    source_type = "ats"
    auth_type = "none"
    rate_limit = 60
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        """Drain all jobs from all registered Personio companies."""
        companies = get_companies('personio')
        if not companies:
            log.info("Personio: no companies in registry")
            return []

        log.info(f"Personio: crawling {len(companies)} companies...")
        all_jobs = []
        seen_ids = set()

        for i, company in enumerate(companies, 1):
            slug = company['ats_slug']

            try:
                jobs = self._fetch_json(slug)
                if jobs is None:
                    jobs = self._fetch_xml(slug)
                if jobs is None:
                    log.debug(f"  [{i}/{len(companies)}] {slug}: no data (deactivating)")
                    record_failure('personio', slug)
                    continue

                job_count = 0
                for raw in jobs:
                    if raw['id'] not in seen_ids:
                        seen_ids.add(raw['id'])
                        all_jobs.append(raw)
                        job_count += 1

                update_crawl_result('personio', slug, job_count)
                log.debug(f"  [{i}/{len(companies)}] {slug}: {job_count} jobs")

            except Exception as e:
                log.warning(f"  [{i}/{len(companies)}] {slug}: {e}")
                record_failure('personio', slug)

            if i < len(companies):
                _limiter.wait(self.name, self.rate_limit)

        log.info(f"Personio: {len(all_jobs)} total jobs from {len(companies)} companies")
        return all_jobs

    def _fetch_json(self, slug: str) -> list[dict] | None:
        """Try the JSON endpoint first."""
        url = f"https://{slug}.jobs.personio.de/search.json"
        try:
            resp = requests.get(url, timeout=_TIMEOUT, allow_redirects=False)
            # 301 redirect to personio.de homepage means slug is dead
            if resp.status_code in (301, 302):
                return None
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not isinstance(data, list):
                return None
            return [_parse_job_json(j, slug) for j in data if j.get('id')]
        except (requests.RequestException, ValueError):
            return None

    def _fetch_xml(self, slug: str) -> list[dict] | None:
        """Fallback to XML feed with lenient parsing."""
        url = f"https://{slug}.jobs.personio.de/xml"
        try:
            resp = requests.get(url, timeout=_TIMEOUT, allow_redirects=False)
            if resp.status_code in (301, 302) or resp.status_code != 200:
                return None

            # Try lenient XML parsing
            try:
                from lxml import etree
                root = etree.fromstring(resp.content, parser=etree.XMLParser(
                    recover=True, resolve_entities=False, no_network=True, huge_tree=False,
                ))
            except ImportError:
                import defusedxml.ElementTree as _ET
                root = _ET.fromstring(resp.content)

            positions = root.findall('.//position')
            if not positions:
                return None

            jobs = []
            for pos in positions:
                parsed = _parse_job_xml(pos, slug)
                if parsed:
                    jobs.append(parsed)
            return jobs if jobs else None
        except Exception:
            return None

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
