"""
aggregator/retry.py - Exponential backoff retry wrapper.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


def with_retry(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Call func with exponential backoff on exception.

    Raises the last exception after exhausting retries.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = base_delay * (2 ** attempt)
            log.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s - {exc}")
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]
