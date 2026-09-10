"""
discovery/google_dork.py - Discover companies via Google site: searches.

Uses Serper.dev API ($50/50K queries) to run site: searches for ATS platforms
and extract company slugs from the result URLs.

Run: python -m discovery.google_dork
Requires: SERPER_API_KEY in environment/.env
"""

import logging
import re
import time

import requests

from aggregator import config
from sources.ats._registry import upsert_company

log = logging.getLogger(__name__)

_SERPER_URL = 'https://google.serper.dev/search'

# Dork queries and URL extraction patterns per ATS
ATS_DORKS = {
    'greenhouse': {
        'queries': [
            'site:boards.greenhouse.io',
            'site:boards.greenhouse.io Berlin',
            'site:boards.greenhouse.io Germany',
            'site:boards.greenhouse.io München',
            'site:boards.greenhouse.io Hamburg',
            'site:boards.greenhouse.io remote',
        ],
        'pattern': re.compile(r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    },
    'lever': {
        'queries': [
            'site:jobs.lever.co',
            'site:jobs.lever.co Germany',
            'site:jobs.lever.co Berlin',
            'site:jobs.lever.co remote',
        ],
        'pattern': re.compile(r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    },
    'ashby': {
        'queries': [
            'site:jobs.ashbyhq.com',
            'site:jobs.ashbyhq.com Germany',
            'site:jobs.ashbyhq.com remote',
        ],
        'pattern': re.compile(r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    },
    'personio': {
        'queries': [
            'site:jobs.personio.de',
            'site:jobs.personio.com',
        ],
        'pattern': re.compile(r'([a-zA-Z0-9_-]+)\.jobs\.personio\.(?:de|com)', re.IGNORECASE),
    },
    'smartrecruiters': {
        'queries': [
            'site:jobs.smartrecruiters.com',
            'site:jobs.smartrecruiters.com Germany',
            'site:jobs.smartrecruiters.com Berlin',
        ],
        'pattern': re.compile(r'jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    },
    'workable': {
        'queries': [
            'site:apply.workable.com',
            'site:apply.workable.com Germany',
            'site:apply.workable.com Berlin',
        ],
        'pattern': re.compile(r'apply\.workable\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    },
    'recruitee': {
        'queries': [
            'site:recruitee.com',
            'site:recruitee.com Germany',
            'site:recruitee.com Berlin',
        ],
        'pattern': re.compile(r'([a-zA-Z0-9_-]+)\.recruitee\.com', re.IGNORECASE),
    },
    'dvinci': {
        'queries': [
            'site:dvinci-hr.com',
            'site:dvinci-hr.com Germany',
        ],
        'pattern': re.compile(r'([a-zA-Z0-9_-]+)\.dvinci-hr\.com', re.IGNORECASE),
    },
    'pinpoint': {
        'queries': [
            'site:pinpointhq.com',
            'site:pinpointhq.com Germany',
        ],
        'pattern': re.compile(r'([a-zA-Z0-9_-]+)\.pinpointhq\.com', re.IGNORECASE),
    },
    'workday': {
        'queries': [
            'site:myworkdayjobs.com Germany',
            'site:myworkdayjobs.com Deutschland',
            'site:myworkdayjobs.com Berlin',
            'site:myworkdayjobs.com Hamburg',
            'site:myworkdayjobs.com Frankfurt',
        ],
        'pattern': re.compile(r'([a-zA-Z0-9_-]+)\.wd\d+\.myworkdayjobs\.com', re.IGNORECASE),
    },
}

_IGNORE_SLUGS = {
    'embed', 'api', 'www', 'app', 'job', 'jobs', 'career', 'careers',
    'internal', 'test', 'demo', 'example', 'postings', 'search',
}


def _search_serper(query: str, num: int = 10) -> list[dict]:
    """Run a Google search via Serper.dev API."""
    api_key = getattr(config, 'SERPER_API_KEY', None)
    if not api_key:
        log.error("SERPER_API_KEY not set")
        return []

    try:
        resp = requests.post(
            _SERPER_URL,
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': query, 'num': num},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get('organic', [])
    except Exception as e:
        log.warning(f"Serper search failed for '{query}': {e}")
        return []


def discover_for_ats(ats_type: str) -> int:
    """Run all dork queries for an ATS type and register discovered companies."""
    if ats_type not in ATS_DORKS:
        log.warning(f"Unknown ATS type: {ats_type}")
        return 0

    ats_config = ATS_DORKS[ats_type]
    pattern = ats_config['pattern']
    seen_slugs = set()
    count = 0

    for query in ats_config['queries']:
        results = _search_serper(query)
        log.info(f"  '{query}': {len(results)} results")

        for result in results:
            link = result.get('link', '')
            match = pattern.search(link)
            if not match:
                continue

            slug = match.group(1).lower().strip()
            if slug in seen_slugs or slug in _IGNORE_SLUGS or len(slug) < 2:
                continue
            seen_slugs.add(slug)

            # Try to extract company name from result title
            title = result.get('title', '')
            # Most Greenhouse pages: "Company Name - Job Title"
            company_name = title.split(' - ')[0].split(' | ')[0].strip() or slug

            upsert_company(
                ats_type=ats_type,
                ats_slug=slug,
                company_name=company_name,
                discovered_via='google_dork',
            )
            count += 1

        time.sleep(1)  # Be polite between queries

    log.info(f"Google dork: discovered {count} {ats_type} companies")
    return count


def discover_all() -> dict[str, int]:
    """Run discovery for all ATS types."""
    results = {}
    for ats_type in ATS_DORKS:
        results[ats_type] = discover_for_ats(ats_type)
    return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    api_key = getattr(config, 'SERPER_API_KEY', None)
    if not api_key:
        print("Error: SERPER_API_KEY not set in environment/.env")
        print("Get a key at https://serper.dev (free tier: 2,500 searches)")
        exit(1)

    print("Running Google dork discovery for all ATS platforms...")
    result = discover_all()
    total = sum(result.values())
    print(f"\nDone. Discovered {total} companies:")
    for ats, count in sorted(result.items()):
        print(f"  {ats}: {count}")
