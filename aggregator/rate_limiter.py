"""
aggregator/rate_limiter.py - Simple per-source request rate limiter.

Enforces a minimum interval between requests for each source, derived
from the source's configured requests_per_minute limit.

The orchestrator is single-threaded, so a plain dict of last-call
timestamps is sufficient - no threading locks needed.

Usage:
    from aggregator.rate_limiter import RateLimiter

    _limiter = RateLimiter()          # module-level, persists across fetch loop

    for i, item in enumerate(items):
        # ... fetch item ...
        if i < len(items) - 1:
            _limiter.wait(self.name, self.rate_limit)
"""

import logging
import time

log = logging.getLogger(__name__)


class RateLimiter:
    """Enforces a minimum interval between requests for a named source.

    The interval is derived from requests_per_minute:
        min_interval_seconds = 60 / requests_per_minute

    First call always passes through immediately (no prior timestamp).
    """

    def __init__(self) -> None:
        self._last_call: dict[str, float] = {}

    def wait(self, source_name: str, requests_per_minute: int) -> None:
        """Sleep if needed to respect the source's rate limit.

        Args:
            source_name: Identifier for this source (used as throttle key).
            requests_per_minute: Max requests allowed per minute. 0 or
                negative disables throttling.
        """
        if not requests_per_minute or requests_per_minute <= 0:
            return

        min_interval = 60.0 / requests_per_minute
        now = time.monotonic()
        elapsed = now - self._last_call.get(source_name, 0.0)

        if elapsed < min_interval:
            sleep_for = min_interval - elapsed
            log.debug('[%s] rate limiter: sleeping %.3fs', source_name, sleep_for)
            time.sleep(sleep_for)

        self._last_call[source_name] = time.monotonic()
