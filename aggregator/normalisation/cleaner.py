"""
aggregator/normalisation/cleaner.py - Text cleaning utilities.
"""

import re
from html import unescape


def clean_html(text: str | None) -> str:
    """Strip HTML tags, decode entities, normalise whitespace."""
    if not text:
        return ''
    text = unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate_description(text: str | None, max_length: int = 10000) -> str:
    """Truncate description to max_length characters."""
    if not text:
        return ''
    return text[:max_length]
