"""
search_terms/ - Shared search term intelligence layer.

Provides sector-diverse German job titles for all search-term-based sources.
Replaces the hardcoded _DEFAULT_TERMS in each API source.

Usage:
    from search_terms import get_terms, get_german_cities

    terms = get_terms(tier=1)                # High-volume titles only
    terms = get_terms(tier=2)                # Tier 1 + 2
    terms = get_terms(sectors=["it", "engineering"])  # Specific sectors
    cities = get_german_cities(tier=1)       # Top 15 cities
"""

from search_terms.german_job_titles import (
    SECTOR_NAMES,
    get_german_cities,
    get_terms,
    get_terms_for_source,
)
