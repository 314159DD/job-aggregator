"""
discovery/self_discover.py - Extract ATS slugs from existing jobs in the database.

Scans job URLs for known ATS patterns and adds newly discovered companies
to the registry. This creates a self-reinforcing discovery loop:
  jobs from any source → URLs contain ATS links → new companies added → more jobs

Run: python -m discovery.self_discover
"""

import logging
import re

from aggregator.db import get_supabase
from sources.ats._registry import upsert_company

log = logging.getLogger(__name__)

# Regex patterns to extract company slugs from URLs
ATS_URL_PATTERNS = {
    'greenhouse': [
        re.compile(r'boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)', re.IGNORECASE),
        re.compile(r'boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ],
    'lever': [
        re.compile(r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ],
    'ashby': [
        re.compile(r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ],
    'personio': [
        re.compile(r'([a-zA-Z0-9_-]+)\.jobs\.personio\.(?:de|com)', re.IGNORECASE),
    ],
    'smartrecruiters': [
        re.compile(r'jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ],
    'workable': [
        re.compile(r'apply\.workable\.com/([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ],
    'recruitee': [
        re.compile(r'([a-zA-Z0-9_-]+)\.recruitee\.com', re.IGNORECASE),
    ],
    'dvinci': [
        re.compile(r'([a-zA-Z0-9_-]+)\.dvinci-hr\.com', re.IGNORECASE),
    ],
    'pinpoint': [
        re.compile(r'([a-zA-Z0-9_-]+)\.pinpointhq\.com', re.IGNORECASE),
    ],
    'workday': [
        re.compile(r'([a-zA-Z0-9_-]+)\.wd\d+\.myworkdayjobs\.com', re.IGNORECASE),
    ],
}

# Slugs to ignore (not actual companies)
_IGNORE_SLUGS = {'embed', 'api', 'www', 'app', 'job', 'jobs', 'career', 'careers'}


def _extract_ats_slugs(url: str) -> list[tuple[str, str]]:
    """Extract (ats_type, slug) pairs from a URL. Returns empty list if no match."""
    if not url:
        return []
    results = []
    for ats_type, patterns in ATS_URL_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(url)
            if match:
                slug = match.group(1).lower().strip()
                if slug and slug not in _IGNORE_SLUGS and len(slug) > 1:
                    results.append((ats_type, slug))
    return results


def discover_from_existing_jobs(limit: int = 5000) -> dict[str, int]:
    """Scan recent jobs for ATS URLs and register newly discovered companies.

    Args:
        limit: Max number of recent jobs to scan.

    Returns:
        Dict of ats_type → count of newly discovered companies.
    """
    sb = get_supabase()
    discovered = {}

    try:
        # Fetch recent jobs with URLs
        result = sb.table('jobs').select('url, company').not_.is_('url', 'null').order(
            'first_seen_at', desc=True
        ).limit(limit).execute()

        if not result.data:
            log.info("self_discover: no jobs with URLs found")
            return discovered

        # Track what we find
        seen = set()
        for row in result.data:
            url = row.get('url', '')
            company_name = row.get('company', '')

            for ats_type, slug in _extract_ats_slugs(url):
                key = (ats_type, slug)
                if key in seen:
                    continue
                seen.add(key)

                upsert_company(
                    ats_type=ats_type,
                    ats_slug=slug,
                    company_name=company_name or slug,
                    discovered_via='self_discovery',
                )
                discovered.setdefault(ats_type, 0)
                discovered[ats_type] += 1

    except Exception as e:
        log.error(f"self_discover failed: {e}")

    total = sum(discovered.values())
    if total:
        log.info(f"self_discover: found {total} companies - {discovered}")
    else:
        log.info("self_discover: no new companies found")

    return discovered


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print("Scanning existing jobs for ATS URLs...")
    result = discover_from_existing_jobs()
    total = sum(result.values())
    print(f"\nDone. Discovered {total} companies:")
    for ats, count in sorted(result.items()):
        print(f"  {ats}: {count}")
