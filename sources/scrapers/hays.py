"""
sources/scrapers/hays.py - Hays Germany job scraper.

Hays (hays.de) is one of Germany's largest recruitment agencies.
~5,800 job listings across all sectors.

Strategy: Paginate through search results (HTML, 20 per page), parse job
cards from the server-rendered HTML. Uses sortOrder=DATE for newest first.

Card structure (verified Feb 2026):
  <div class="search__result border-radius-10">
    <a class="search__result__link" href="...detail-{slug}-{ref}/1">
    <div class="search__result__prospectnumber">Referenznummer: {ref}</div>
    <h4 class="search__result__header__title">Job Title (m/w/d)</h4>
    <div class="search__result__job__attribute__type">Employment Type</div>
    <div class="search__result__job__attribute__location">City</div>
    <div class="search__result__teaser"><ul><li>Bullet points</li></ul></div>
    Online seit: DD.MM.YY

Run: python -m sources.scrapers.hays
"""

import html as html_mod
import logging
import re
import time

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_BASE_URL = 'https://www.hays.de/jobsuche/stellenangebote-jobs'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; JobAggregator/1.0)',
    'Accept': 'text/html,application/xhtml+xml,*/*',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.5',
}
_RESULTS_PER_PAGE = 20
_CRAWL_DELAY = 2      # seconds between requests
_MAX_PAGES = 300       # ~5,800 jobs / 20 per page ≈ 290


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_search_page(page_html: str) -> list[dict]:
    """Parse job cards from a Hays search results page."""
    jobs = []

    # Split the page into individual card blocks
    # Each card starts with <div class="search__result border-radius-10">
    card_splits = re.split(r'<div[^>]*class="search__result border-radius-10">', page_html)

    for card in card_splits[1:]:  # Skip everything before the first card
        # Truncate at next card or reasonable length
        card = card[:12000]

        # 1. Extract URL from the result link
        link_match = re.search(
            r'<a[^>]*class="search__result__link"[^>]*href="([^"]+)"',
            card,
        )
        if not link_match:
            continue
        url = link_match.group(1).strip()

        # 2. Extract reference number
        ref_match = re.search(
            r'Referenznummer:\s*(\d{5,7}/\d+)',
            card,
        )
        if ref_match:
            ref = ref_match.group(1)
        else:
            # Try from URL slug: ...-{refnr}/1
            slug_ref = re.search(r'-(\d{5,7})/\d*(?:\?|$|")', url)
            ref = slug_ref.group(1) if slug_ref else ''
        if not ref:
            continue

        # 3. Extract title from h4.search__result__header__title
        title_match = re.search(
            r'<h4[^>]*class="search__result__header__title"[^>]*>(.*?)</h4>',
            card, re.DOTALL,
        )
        title = ''
        if title_match:
            title = _strip_html(title_match.group(1))
        if not title:
            continue

        # 4. Extract location from attribute__location
        loc_match = re.search(
            r'attribute__location[^>]*>.*?<div[^>]*class="info-text"[^>]*>\s*(.*?)\s*</div>',
            card, re.DOTALL,
        )
        location = _strip_html(loc_match.group(1)) if loc_match else ''

        # Fallback: extract city from URL slug
        if not location:
            # URL format: ...-detail-{title-slug}-{city}-{ref}/1
            slug_match = re.search(r'detail-.*?-([a-z]+)-\d{5,7}/', url, re.IGNORECASE)
            if slug_match:
                location = slug_match.group(1).title()

        # 5. Extract employment type from attribute__type
        type_match = re.search(
            r'attribute__type[^>]*>.*?<div[^>]*class="info-text"[^>]*>\s*(.*?)\s*</div>',
            card, re.DOTALL,
        )
        emp_type = _strip_html(type_match.group(1)) if type_match else ''

        # 6. Extract teaser description
        teaser_match = re.search(
            r'<div[^>]*class="search__result__teaser"[^>]*>(.*?)</div>',
            card, re.DOTALL,
        )
        teaser = ''
        if teaser_match:
            # Extract the h-text div inside
            htext = re.search(r'<div[^>]*class="h-text"[^>]*>(.*?)</div>', teaser_match.group(1), re.DOTALL)
            if htext:
                teaser = _strip_html(htext.group(1))

        # 7. Extract posted date
        date_match = re.search(r'Online seit:\s*(\d{2}\.\d{2}\.\d{2,4})', card)
        posted = date_match.group(1) if date_match else ''

        # Build description
        desc_parts = []
        if emp_type:
            desc_parts.append(emp_type)
        if teaser:
            desc_parts.append(teaser)
        description = '\n'.join(desc_parts)

        # Ensure full URL
        if not url.startswith('http'):
            url = f"https://www.hays.de{url}"

        jobs.append({
            'id': f"hays_{ref.replace('/', '_')}",
            'url': url,
            'title': title,
            'company': 'Hays',  # Hays is the recruiter; actual client often undisclosed
            'location': location or 'Germany',
            'description': description,
            'salary': '',
            'posted_at': posted,
        })

    return jobs


class HaysSource(BaseSource):
    name = "hays"
    display_name = "Hays Germany"
    source_type = "scraper"
    auth_type = "none"
    rate_limit = 30
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Hays Germany...")
        all_jobs = []
        empty_pages = 0

        for page in range(1, _MAX_PAGES + 1):
            try:
                if page == 1:
                    url = f"{_BASE_URL}?q=&r=Deutschland&sortOrder=DATE"
                else:
                    url = f"{_BASE_URL}/p/{page}/?q=&r=Deutschland&sortOrder=DATE"

                resp = requests.get(url, headers=_HEADERS, timeout=30)
                if resp.status_code != 200:
                    log.warning(f"  Hays page {page}: HTTP {resp.status_code}")
                    empty_pages += 1
                    if empty_pages >= 3:
                        break
                    continue

                page_jobs = _parse_search_page(resp.text)
                if not page_jobs:
                    empty_pages += 1
                    if empty_pages >= 3:
                        log.info(f"  Hays: {empty_pages} consecutive empty pages at page {page}")
                        break
                    continue

                empty_pages = 0
                all_jobs.extend(page_jobs)

                if page % 50 == 0:
                    log.info(f"  Hays: page {page}, {len(all_jobs)} jobs so far")

                time.sleep(_CRAWL_DELAY)

            except Exception as e:
                log.warning(f"  Hays page {page}: {e}")
                empty_pages += 1
                if empty_pages >= 5:
                    break

        # Dedup by ID
        seen = set()
        unique = [j for j in all_jobs if not (j['id'] in seen or seen.add(j['id']))]
        log.info(f"Hays: {len(unique)} unique jobs from {len(all_jobs)} raw")
        return unique

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    source = HaysSource()
    print("Testing Hays scraper (first 3 pages)...")
    import sources.scrapers.hays as _mod
    _mod._MAX_PAGES = 3
    jobs = source.fetch()
    print(f"\nFetched {len(jobs)} jobs")
    for j in jobs[:10]:
        print(f"  {j['title'][:60]:60s}  {j['location']:20s}  {j['id']}")
