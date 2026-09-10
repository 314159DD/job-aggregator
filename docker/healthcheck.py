"""
docker/healthcheck.py - Docker HEALTHCHECK script.

Checks:
1. Python environment and aggregator module can be imported.
2. If running in cron mode and SUPABASE_URL is set, verifies config is valid.
3. If /tmp/aggregator.last_run exists, checks it was written within 2 hours.

Exit 0 = healthy, exit 1 = unhealthy.
"""

import os
import sys
import time

# 1. Basic import check
try:
    from aggregator import config
except Exception as e:
    print(f"UNHEALTHY: import failed - {e}", file=sys.stderr)
    sys.exit(1)

# 2. In cron mode, verify config if SUPABASE_URL is present
if os.environ.get("SUPABASE_URL") and os.environ.get("AGGREGATOR_MODE", "cron") == "cron":
    try:
        config.validate()
    except ValueError as e:
        print(f"UNHEALTHY: config invalid - {e}", file=sys.stderr)
        sys.exit(1)

# 3. Check last-run timestamp if available
LAST_RUN_FILE = "/tmp/aggregator.last_run"
MAX_AGE_SECONDS = 7200  # 2 hours (cron runs hourly)

if os.path.exists(LAST_RUN_FILE):
    try:
        mtime = os.path.getmtime(LAST_RUN_FILE)
        age = time.time() - mtime
        if age > MAX_AGE_SECONDS:
            print(
                f"UNHEALTHY: last run was {int(age / 60)} min ago (threshold: {MAX_AGE_SECONDS // 60} min)",
                file=sys.stderr,
            )
            sys.exit(1)
    except OSError:
        pass  # File disappeared between exists() and getmtime() - race condition, ignore

print("OK")
sys.exit(0)
