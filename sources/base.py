"""
sources/base.py - BaseSource abstract interface.

Every data source must implement this interface.

class BaseSource(ABC):
    name: str                    # e.g. "arbeitsamt"
    display_name: str            # e.g. "Arbeitsamt (German Federal Employment Agency)"
    source_type: str             # "api" | "scraper" | "feed"
    auth_type: str               # "none" | "api_key" | "oauth" | "credentials"
    rate_limit: int              # max requests per minute
    enabled: bool                # can be toggled via config

    @abstractmethod
    def fetch(self, search_terms=None, locations=None) -> list[dict]:
        '''Fetch raw job data from source.'''

    @abstractmethod
    def normalise(self, raw_jobs: list[dict]) -> list[JobRecord]:
        '''Convert raw dicts to standard JobRecord format.'''

    def health_check(self) -> dict:
        '''Quick connectivity test. Returns {status, latency_ms}.'''
"""

import logging
from abc import ABC, abstractmethod

import requests as _requests

_log = logging.getLogger(__name__)

# SEC-08: Cap response body size to prevent OOM from malicious/misconfigured feeds
MAX_RESPONSE_BYTES = 50 * 1024 * 1024  # 50 MB


def safe_get(url: str, **kwargs) -> _requests.Response:
    """requests.get() wrapper that enforces a response size limit via streaming."""
    kwargs.setdefault('timeout', 30)
    kwargs['stream'] = True
    resp = _requests.get(url, **kwargs)
    resp.raise_for_status()
    content_length = resp.headers.get('content-length')
    if content_length and int(content_length) > MAX_RESPONSE_BYTES:
        resp.close()
        raise ValueError(f"Response too large: {content_length} bytes (limit {MAX_RESPONSE_BYTES})")
    # Read up to limit + 1 byte to detect oversized responses
    data = resp.raw.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Response exceeded {MAX_RESPONSE_BYTES} bytes")
    resp._content = data
    resp.close()
    return resp


class BaseSource(ABC):
    """Abstract base class for all job data sources."""

    name: str = ""
    display_name: str = ""
    source_type: str = "api"       # "api" | "scraper" | "feed"
    auth_type: str = "none"        # "none" | "api_key" | "oauth" | "credentials"
    rate_limit: int = 30           # requests per minute
    enabled: bool = True
    min_interval_hours: int = 0    # 0 = run every time; >0 = skip if ran within N hours

    @abstractmethod
    def fetch(self, search_terms=None, locations=None) -> list:
        """Fetch raw job data from the source.

        Args:
            search_terms: Optional list of search keywords
            locations: Optional list of (location, radius) tuples

        Returns:
            List of raw job dicts (source-specific format)
        """

    @abstractmethod
    def normalise(self, raw_jobs: list) -> list:
        """Convert raw source dicts to standard JobRecord format.

        Args:
            raw_jobs: List of raw dicts from fetch()

        Returns:
            List of normalised JobRecord instances
        """

    def health_check(self) -> dict:
        """Quick connectivity test.

        Returns:
            Dict with 'status' (ok/error) and 'latency_ms'
        """
        # Default: try a minimal fetch
        import time
        try:
            start = time.time()
            self.fetch(search_terms=["test"], locations=None)
            latency = int((time.time() - start) * 1000)
            return {"status": "ok", "latency_ms": latency}
        except Exception as e:
            return {"status": "error", "error": str(e)}
