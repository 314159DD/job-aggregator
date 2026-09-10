"""
aggregator/normalisation/dedup.py - Deduplication hash functions.


Three-layer deduplication:
  1. External ID: same source re-fetch (handled in sync.py)
  2. Strict hash: hash(title + company + location) - exact cross-source dupes
  3. Fuzzy hash:  hash(company + location + desc_fingerprint) - near-dupes
"""

import hashlib
import re


def calculate_canonical_hash_strict(title, company, location):
    """MD5 of normalised title+company+location for exact duplicate detection."""
    normalized = f"{title}|{company}|{location}".lower()
    normalized = re.sub(r'[^\w\s|]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def calculate_description_fingerprint(description):
    """SHA-256 fingerprint of cleaned description text (first 16 hex chars)."""
    if not description:
        return None
    cleaned = description.lower()
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()[:1000]
    return hashlib.sha256(cleaned.encode()).hexdigest()[:16]


def calculate_canonical_hash_fuzzy(company, location, description_fingerprint):
    """MD5 of company+location+description_fingerprint for near-duplicate detection."""
    normalized = f"{company}|{location}|{description_fingerprint or ''}".lower()
    normalized = re.sub(r'[^\w\s|]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return hashlib.md5(normalized.encode()).hexdigest()
