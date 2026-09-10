#!/bin/sh
# Job Aggregator - Docker entrypoint
#
# AGGREGATOR_MODE=cron  (default) - run supercronic daemon with docker/crontab
# AGGREGATOR_MODE=once              - run aggregator once and exit
# AGGREGATOR_MODE=discover          - run full discovery suite and exit
# AGGREGATOR_MODE=freshness         - run freshness check and exit
# AGGREGATOR_MODE=health            - print health report and exit
# AGGREGATOR_MODE=snapshot          - run skill snapshot and exit

set -e

MODE="${AGGREGATOR_MODE:-cron}"

case "$MODE" in
    cron)
        echo "[entrypoint] Starting supercronic daemon..."
        exec supercronic /app/docker/crontab
        ;;
    once)
        echo "[entrypoint] Running aggregator once..."
        exec python -m aggregator "$@"
        ;;
    discover)
        echo "[entrypoint] Running full discovery suite..."
        exec python -m aggregator --discover
        ;;
    freshness)
        echo "[entrypoint] Running freshness check..."
        exec python -m aggregator --freshness-check
        ;;
    health)
        echo "[entrypoint] Running health report..."
        exec python -m aggregator --health-report
        ;;
    snapshot)
        echo "[entrypoint] Running skill snapshot..."
        exec python -m aggregator --skill-snapshot
        ;;
    *)
        echo "[entrypoint] Unknown AGGREGATOR_MODE='$MODE'. Valid: cron, once, discover, freshness, health, snapshot" >&2
        exit 1
        ;;
esac
