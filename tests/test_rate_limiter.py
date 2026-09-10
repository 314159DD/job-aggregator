"""Tests for aggregator/rate_limiter.py"""
import time

from aggregator.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_first_call_passes_immediately(self):
        lim = RateLimiter()
        t = time.monotonic()
        lim.wait('src', 60)
        assert time.monotonic() - t < 0.1

    def test_enforces_min_interval(self):
        lim = RateLimiter()
        lim.wait('src', 120)          # first call - no wait; min_interval = 0.5s
        t = time.monotonic()
        lim.wait('src', 120)          # should sleep ~0.5s
        elapsed = time.monotonic() - t
        assert elapsed >= 0.45, f"Expected ≥0.45s, got {elapsed:.3f}s"

    def test_no_sleep_when_enough_time_has_passed(self):
        lim = RateLimiter()
        lim.wait('src', 120)          # record timestamp
        time.sleep(0.6)               # wait longer than the 0.5s interval
        t = time.monotonic()
        lim.wait('src', 120)          # should not sleep again
        assert time.monotonic() - t < 0.1

    def test_zero_rpm_disables_throttling(self):
        lim = RateLimiter()
        lim.wait('src', 60)           # first call
        t = time.monotonic()
        lim.wait('src', 0)            # 0 rpm → should return immediately
        assert time.monotonic() - t < 0.1

    def test_negative_rpm_disables_throttling(self):
        lim = RateLimiter()
        lim.wait('src', 60)
        t = time.monotonic()
        lim.wait('src', -1)
        assert time.monotonic() - t < 0.1

    def test_independent_keys_dont_block_each_other(self):
        lim = RateLimiter()
        lim.wait('source_a', 60)      # record timestamp for a
        t = time.monotonic()
        lim.wait('source_b', 60)      # different key - no prior call → no wait
        assert time.monotonic() - t < 0.1

    def test_interval_derived_from_rpm(self):
        """60 rpm → 1s interval; second call should sleep ~1s."""
        lim = RateLimiter()
        lim.wait('src', 60)
        t = time.monotonic()
        lim.wait('src', 60)
        elapsed = time.monotonic() - t
        assert elapsed >= 0.9, f"Expected ≥0.9s for 60rpm, got {elapsed:.3f}s"
