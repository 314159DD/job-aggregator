"""
discovery/sitemap_scan.py - Discover ATS companies by scanning sitemaps.

Fetches sitemap.xml from known company domains, parses all URLs,
and runs them through ATS URL pattern matching. Any new companies
found are registered in the company_registry.

This is the 4th discovery mechanism alongside:
  1. seed_lists.py (hardcoded)
  2. google_dork.py (Google search)
  3. self_discover.py (scan existing job URLs)

Seed domains come from:
  - company_registry (domains of already-registered companies)
  - job URLs in the DB (extract domains from job links)

Run: python -m discovery.sitemap_scan
"""

import gzip
import logging
import time
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
import requests

from aggregator.db import get_supabase
from discovery.self_discover import _extract_ats_slugs
from sources.ats._registry import upsert_company
from sources.base import safe_get

log = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; JobAggregator/1.0)',
    'Accept': 'application/xml, text/xml, */*',
}
_REQUEST_TIMEOUT = 15
_REQUEST_DELAY = 0.5
_MAX_URLS_PER_SITEMAP = 50000  # Safety cap per sitemap file

# XML namespace used by sitemap protocol
_NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def _fetch_robots_txt(domain: str) -> str | None:
    """Fetch robots.txt and return its contents, or None on failure."""
    try:
        resp = requests.get(
            f'https://{domain}/robots.txt',
            headers=_HEADERS, timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200 and 'text' in resp.headers.get('content-type', ''):
            return resp.text
    except Exception:
        pass
    return None


def _find_sitemap_urls(robots_txt: str) -> list[str]:
    """Extract Sitemap: directives from robots.txt."""
    urls = []
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith('sitemap:'):
            url = line.split(':', 1)[1].strip()
            if url:
                urls.append(url)
    return urls


def _fetch_sitemap(url: str) -> list[str]:
    """Fetch and parse a sitemap XML, returning all <loc> URLs.

    Handles:
    - Regular sitemap.xml
    - Gzipped sitemaps (.xml.gz)
    - Sitemap index files (recursively fetches child sitemaps)
    """
    all_urls = []
    try:
        resp = safe_get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)

        # Handle gzipped content
        content = resp.content
        if url.endswith('.gz') or resp.headers.get('content-encoding') == 'gzip':
            try:
                content = gzip.decompress(content)
            except Exception:
                pass  # May not actually be gzipped

        root = ET.fromstring(content)
        tag = root.tag.lower()

        # Sitemap index: <sitemapindex> → recurse into child sitemaps
        if 'sitemapindex' in tag:
            child_locs = root.findall('.//sm:sitemap/sm:loc', _NS)
            # Also try without namespace (some sitemaps don't use it)
            if not child_locs:
                child_locs = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if not child_locs:
                child_locs = [el for el in root.iter() if el.tag.endswith('}loc') or el.tag == 'loc']

            for loc_el in child_locs[:20]:  # Cap child sitemaps
                child_url = loc_el.text.strip() if loc_el.text else ''
                if child_url:
                    time.sleep(_REQUEST_DELAY)
                    all_urls.extend(_fetch_sitemap(child_url))
        else:
            # Regular sitemap: extract <url><loc> entries
            loc_elements = root.findall('.//sm:url/sm:loc', _NS)
            if not loc_elements:
                loc_elements = [el for el in root.iter() if el.tag.endswith('}loc') or el.tag == 'loc']

            for loc_el in loc_elements[:_MAX_URLS_PER_SITEMAP]:
                url_text = loc_el.text.strip() if loc_el.text else ''
                if url_text:
                    all_urls.append(url_text)

    except ET.ParseError:
        log.debug(f"  sitemap XML parse error: {url}")
    except Exception as e:
        log.debug(f"  sitemap fetch error for {url}: {e}")

    return all_urls


def _extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace('www.', '')
    except Exception:
        return ''


def _get_registry_domains() -> set[str]:
    """Fetch unique domains from company_registry."""
    domains = set()
    try:
        sb = get_supabase()
        result = sb.table('company_registry').select('domain').not_.is_('domain', 'null').execute()
        for row in (result.data or []):
            d = row.get('domain', '')
            if d:
                domains.add(d.lower().replace('www.', ''))
    except Exception as e:
        log.warning(f"Failed to fetch registry domains: {e}")
    return domains


def _get_job_url_domains(limit: int = 2000) -> set[str]:
    """Extract unique domains from recent job URLs in the DB."""
    domains = set()
    try:
        sb = get_supabase()
        result = sb.table('jobs').select('url').not_.is_('url', 'null').order(
            'first_seen_at', desc=True
        ).limit(limit).execute()

        for row in (result.data or []):
            url = row.get('url', '')
            domain = _extract_domain(url)
            # Filter out ATS domains (we want company domains, not ATS platforms)
            ats_domains = {
                'greenhouse.io', 'lever.co', 'ashbyhq.com', 'personio.de',
                'personio.com', 'smartrecruiters.com', 'workable.com',
                'recruitee.com', 'dvinci-hr.com', 'pinpointhq.com',
                'myworkdayjobs.com', 'arbeitsagentur.de', 'randstad.de',
                'interamt.de', 'lehrstellen-radar.de', 'praktischarzt.de',
            }
            if domain and not any(domain.endswith(ad) for ad in ats_domains):
                domains.add(domain)
    except Exception as e:
        log.warning(f"Failed to fetch job URL domains: {e}")
    return domains


def scan_domain(domain: str) -> list[tuple[str, str]]:
    """Scan a single domain's sitemap for ATS URL patterns.

    Returns:
        List of (ats_type, slug) tuples found.
    """
    discovered = []

    # Step 1: Find sitemap URLs via robots.txt
    sitemap_urls = []
    robots = _fetch_robots_txt(domain)
    if robots:
        sitemap_urls = _find_sitemap_urls(robots)

    # Step 2: Fallback to standard sitemap locations
    if not sitemap_urls:
        sitemap_urls = [
            f'https://{domain}/sitemap.xml',
            f'https://{domain}/sitemap_index.xml',
        ]

    # Step 3: Fetch and parse sitemaps
    all_page_urls = []
    for sm_url in sitemap_urls[:5]:  # Cap at 5 sitemap URLs per domain
        urls = _fetch_sitemap(sm_url)
        all_page_urls.extend(urls)
        if urls:
            break  # Found a working sitemap, don't try alternatives
        time.sleep(_REQUEST_DELAY)

    if not all_page_urls:
        return []

    # Step 4: Scan all URLs for ATS patterns
    seen = set()
    for url in all_page_urls:
        for ats_type, slug in _extract_ats_slugs(url):
            key = (ats_type, slug)
            if key not in seen:
                seen.add(key)
                discovered.append((ats_type, slug))

    return discovered


def discover_from_sitemaps(
    max_domains: int = 500,
    include_job_urls: bool = True,
) -> dict[str, int]:
    """Scan sitemaps of known domains and register any new ATS companies.

    Args:
        max_domains: Maximum number of domains to scan.
        include_job_urls: Also extract domains from job URLs in the DB.

    Returns:
        Dict of ats_type → count of newly discovered companies.
    """
    # Collect seed domains
    domains = _get_registry_domains()
    log.info(f"sitemap_scan: {len(domains)} domains from registry")

    if include_job_urls:
        job_domains = _get_job_url_domains()
        log.info(f"sitemap_scan: {len(job_domains)} domains from job URLs")
        domains |= job_domains

    log.info(f"sitemap_scan: scanning {min(len(domains), max_domains)} of {len(domains)} total domains")

    discovered = {}
    scanned = 0
    for domain in sorted(domains)[:max_domains]:
        try:
            results = scan_domain(domain)
            if results:
                for ats_type, slug in results:
                    upsert_company(
                        ats_type=ats_type,
                        ats_slug=slug,
                        company_name=slug,  # Will be updated later by self_discover
                        domain=domain,
                        discovered_via='sitemap_scan',
                    )
                    discovered.setdefault(ats_type, 0)
                    discovered[ats_type] += 1
                log.debug(f"  {domain}: found {len(results)} ATS links")

            scanned += 1
            if scanned % 50 == 0:
                total = sum(discovered.values())
                log.info(f"  sitemap_scan: {scanned} domains scanned, {total} companies found so far")

            time.sleep(_REQUEST_DELAY)

        except Exception as e:
            log.debug(f"  {domain}: error - {e}")

    total = sum(discovered.values())
    if total:
        log.info(f"sitemap_scan: discovered {total} companies from {scanned} domains - {discovered}")
    else:
        log.info(f"sitemap_scan: no new companies found after scanning {scanned} domains")

    return discovered


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print("Scanning sitemaps for ATS URL patterns...")
    result = discover_from_sitemaps()
    total = sum(result.values())
    print(f"\nDone. Discovered {total} companies:")
    for ats, count in sorted(result.items()):
        print(f"  {ats}: {count}")
