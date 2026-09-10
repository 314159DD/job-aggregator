"""
aggregator/search_terms.py - Profile-driven search terms from match_criteria table.

Falls back to hardcoded defaults if the table is empty or unreachable.
"""

from aggregator.db import get_supabase
from aggregator.logging_config import get_logger

log = get_logger(__name__)

_DEFAULT_SEARCH_TERMS = [
    "Software Engineer", "Developer", "Technical PM",
    "Project Manager", "Product Manager", "DevOps Engineer",
    "Solutions Engineer", "Tech Lead",
]

_DEFAULT_LOCATIONS = [
    ("Berlin", 100), ("Munich", 100), ("Hamburg", 100),
    ("Frankfurt", 100), ("Remote", 200),
]


def get_search_terms_all_users() -> dict:
    """
    Union title_terms and locations from ALL active match_criteria rows.

    Multi-user aware: collects terms for every user so the aggregator fetches
    jobs relevant to all users in a single CRON pass. Deduplicates terms
    (case-insensitive) and locations (by city name).

    Falls back to hardcoded defaults if the table is empty or unreachable.
    """
    try:
        result = get_supabase().table("match_criteria").select(
            "title_terms_json,target_locations_json"
        ).eq("status", "active").execute()

        if not result.data:
            log.debug("match_criteria empty - using defaults")
            return {"search_terms": _DEFAULT_SEARCH_TERMS, "locations": _DEFAULT_LOCATIONS}

        all_terms: list = []
        all_locations: list = []
        seen_terms: set = set()
        seen_locs: set = set()

        for row in result.data:
            for term in (row.get("title_terms_json") or []):
                key = str(term).lower().strip()
                if key and key not in seen_terms:
                    seen_terms.add(key)
                    all_terms.append(term)

            for loc in (row.get("target_locations_json") or []):
                if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                    key = str(loc[0]).lower().strip()
                    if key not in seen_locs:
                        seen_locs.add(key)
                        all_locations.append((str(loc[0]), int(loc[1])))
                elif isinstance(loc, str):
                    key = loc.lower().strip()
                    if key not in seen_locs:
                        seen_locs.add(key)
                        all_locations.append((loc, 100))

        log.info(
            f"get_search_terms_all_users: {len(result.data)} user(s) → "
            f"{len(all_terms)} terms, {len(all_locations)} locations"
        )
        return {
            "search_terms": all_terms or _DEFAULT_SEARCH_TERMS,
            "locations": all_locations or _DEFAULT_LOCATIONS,
        }
    except Exception as e:
        log.warning(f"Could not read match_criteria (using defaults): {e}")
        return {"search_terms": _DEFAULT_SEARCH_TERMS, "locations": _DEFAULT_LOCATIONS}


def get_search_terms(user_id: int = 1) -> dict:
    """Read search terms and locations from match_criteria table.

    Returns:
        {"search_terms": [...str], "locations": [...(city, radius) tuples]}
    """
    try:
        result = get_supabase().table("match_criteria").select("title_terms_json,target_locations_json").eq("user_id", user_id).execute()
        if not result.data:
            log.debug("match_criteria empty - using defaults")
            return {"search_terms": _DEFAULT_SEARCH_TERMS, "locations": _DEFAULT_LOCATIONS}

        row = result.data[0]
        terms = row.get("title_terms_json") or []
        raw_locs = row.get("target_locations_json") or []

        # Normalise locations to (city, radius) tuples
        locations = []
        for loc in raw_locs:
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                locations.append((str(loc[0]), int(loc[1])))
            elif isinstance(loc, str):
                locations.append((loc, 100))

        return {
            "search_terms": terms or _DEFAULT_SEARCH_TERMS,
            "locations": locations or _DEFAULT_LOCATIONS,
        }
    except Exception as e:
        log.warning(f"Could not read match_criteria (using defaults): {e}")
        return {"search_terms": _DEFAULT_SEARCH_TERMS, "locations": _DEFAULT_LOCATIONS}
