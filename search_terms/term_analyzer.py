"""
search_terms/term_analyzer.py - Self-improving term list from DB analysis.

Fetches existing job titles from the jobs table, analyzes term frequency,
and identifies high-value terms NOT in our current search term list.

This closes the feedback loop: we crawl jobs → analyze what we found →
discover terms we're missing → add them to improve coverage.

Run: python -m search_terms.term_analyzer
"""

import logging
import re
from collections import Counter

from aggregator.db import get_supabase
from search_terms.german_job_titles import SECTORS, get_terms

log = logging.getLogger(__name__)

# Terms that appear in titles but aren't useful as search terms
_STOPWORDS = {
    # German
    'und', 'oder', 'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine',
    'einer', 'einem', 'einen', 'für', 'mit', 'bei', 'von', 'zum', 'zur',
    'als', 'auf', 'aus', 'nach', 'über', 'unter', 'vor', 'zwischen',
    'ist', 'sind', 'wird', 'werden', 'hat', 'haben', 'kann', 'können',
    'ab', 'an', 'am', 'im', 'in', 'um', 'bis', 'zu', 'auch', 'noch',
    'nicht', 'nur', 'sehr', 'alle', 'jetzt', 'hier', 'dort', 'gerne',
    'sofort', 'dringend', 'gesucht', 'wir', 'suchen', 'sie', 'ihre',
    # English
    'and', 'or', 'the', 'for', 'with', 'at', 'from', 'to', 'of', 'on', 'by', 'is', 'are', 'we', 'our', 'you', 'your',
    # Generic job posting terms (not useful as search terms)
    'm/w/d', 'w/m/d', 'm/f/d', 'w/m', 'm/w', 'gn', 'mwd', 'wmd',
    'd/m/w', 'all', 'genders', 'gender', 'divers',
    'vollzeit', 'teilzeit', 'minijob', 'remote', 'hybrid', 'onsite',
    'unbefristet', 'befristet', 'festanstellung',
    'junior', 'senior', 'lead', 'head', 'chief', 'director', 'vice',
    'intern', 'trainee', 'werkstudent', 'praktikant', 'auszubildende',
    'standort', 'region', 'bereich', 'abteilung', 'team',
}

# Minimum occurrences to be considered a candidate term
_MIN_FREQUENCY = 5

# Maximum number of suggestions to return
_MAX_SUGGESTIONS = 100


def _clean_title(title: str) -> str:
    """Normalize a job title for analysis."""
    title = title.lower().strip()
    # Remove gender markers: (m/w/d), (w/m/d), etc.
    title = re.sub(r'\(m/w/d\)|\(w/m/d\)|\(m/f/d\)|\(d/m/w\)|\(gn\)', '', title)
    # Remove special chars but keep hyphens and slashes (compound words)
    title = re.sub(r'[^\w\s/\-äöüß]', ' ', title)
    return title.strip()


def _extract_ngrams(title: str, max_n: int = 3) -> list[str]:
    """Extract meaningful unigrams, bigrams, and trigrams from a title."""
    words = title.split()
    # Filter out stopwords and very short tokens
    words = [w for w in words if w not in _STOPWORDS and len(w) >= 2]

    ngrams = []
    # Unigrams - only keep longer ones (short ones are usually generic)
    for w in words:
        if len(w) >= 4:
            ngrams.append(w)
    # Bigrams
    for i in range(len(words) - 1):
        ngrams.append(f"{words[i]} {words[i+1]}")
    # Trigrams
    if max_n >= 3:
        for i in range(len(words) - 2):
            ngrams.append(f"{words[i]} {words[i+1]} {words[i+2]}")

    return ngrams


def fetch_job_titles(limit: int = 50000) -> list[str]:
    """Fetch unique job titles from the DB."""
    try:
        sb = get_supabase()
        result = sb.table('jobs').select('title').not_.is_(
            'title', 'null'
        ).order('first_seen_at', desc=True).limit(limit).execute()

        titles = [row['title'] for row in (result.data or []) if row.get('title')]
        log.info(f"Fetched {len(titles)} job titles from DB")
        return titles
    except Exception as e:
        log.error(f"Failed to fetch job titles: {e}")
        return []


def _get_existing_terms_set() -> set[str]:
    """Get all current search terms as a lowercase set."""
    all_terms = get_terms(tier=3)  # All tiers, all sectors
    return {t.lower() for t in all_terms}


def analyze_titles(titles: list[str]) -> list[dict]:
    """Analyze job titles and return suggested new terms.

    Returns list of dicts:
        [{'term': str, 'count': int, 'sample_titles': list[str]}, ...]
    sorted by frequency descending.
    """
    existing = _get_existing_terms_set()
    ngram_counts = Counter()
    ngram_samples: dict[str, list[str]] = {}

    for raw_title in titles:
        title = _clean_title(raw_title)
        if not title:
            continue

        for ngram in _extract_ngrams(title):
            ngram_counts[ngram] += 1
            if ngram not in ngram_samples:
                ngram_samples[ngram] = []
            if len(ngram_samples[ngram]) < 3:
                ngram_samples[ngram].append(raw_title[:120])

    # Filter: frequent, not already in our list, not a stopword
    suggestions = []
    for term, count in ngram_counts.most_common():
        if count < _MIN_FREQUENCY:
            break  # Counter is sorted, so we can stop early
        if term in existing:
            continue
        # Skip pure numbers
        if re.match(r'^\d+$', term):
            continue
        suggestions.append({
            'term': term,
            'count': count,
            'sample_titles': ngram_samples.get(term, []),
        })

    return suggestions[:_MAX_SUGGESTIONS]


def analyze_source_coverage(titles: list[str]) -> dict[str, int]:
    """Check how many titles match each sector's terms.

    Returns dict of sector_name → match_count.
    """
    sector_hits = {}
    for sector_name, tiers in SECTORS.items():
        terms_lower = set()
        for tier_terms in tiers.values():
            for t in tier_terms:
                terms_lower.add(t.lower())

        hits = 0
        for raw in titles:
            title_lower = raw.lower()
            if any(t in title_lower for t in terms_lower):
                hits += 1
        sector_hits[sector_name] = hits

    return sector_hits


def run_analysis() -> dict:
    """Run full analysis and return results.

    Returns:
        {
            'total_titles': int,
            'coverage_pct': float,
            'sector_coverage': {sector: hits},
            'suggestions': [{'term', 'count', 'sample_titles'}],
        }
    """
    titles = fetch_job_titles()
    if not titles:
        log.warning("No titles to analyze")
        return {'total_titles': 0, 'coverage_pct': 0, 'sector_coverage': {}, 'suggestions': []}

    existing = _get_existing_terms_set()

    # Coverage check: how many titles contain at least one of our terms?
    covered = 0
    for raw in titles:
        tl = raw.lower()
        if any(t in tl for t in existing):
            covered += 1
    coverage_pct = round(100 * covered / len(titles), 1)

    sector_cov = analyze_source_coverage(titles)
    suggestions = analyze_titles(titles)

    log.info(f"Analysis: {len(titles)} titles, {coverage_pct}% covered, {len(suggestions)} new term suggestions")
    return {
        'total_titles': len(titles),
        'coverage_pct': coverage_pct,
        'sector_coverage': sector_cov,
        'suggestions': suggestions,
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    result = run_analysis()

    print(f"\n{'='*60}")
    print("SEARCH TERM ANALYSIS")
    print(f"{'='*60}")
    print(f"Total titles analyzed: {result['total_titles']}")
    print(f"Coverage (titles matching ≥1 term): {result['coverage_pct']}%")

    print("\nSector coverage (titles matching sector terms):")
    for sector, hits in sorted(result['sector_coverage'].items(), key=lambda x: x[1], reverse=True):
        pct = round(100 * hits / max(result['total_titles'], 1), 1)
        print(f"  {sector:25s}  {hits:>6,} ({pct}%)")

    suggestions = result['suggestions']
    if suggestions:
        print(f"\nTop {min(50, len(suggestions))} suggested new terms:")
        for s in suggestions[:50]:
            print(f"  {s['count']:>5}×  {s['term']}")
            for sample in s['sample_titles'][:1]:
                print(f"         └─ {sample}")
    else:
        print("\nNo new term suggestions (our list already covers the data well)")
