FROM python:3.12-slim

WORKDIR /app

# Install supercronic (cron for containers - no setuid, logs to stdout)
# https://github.com/aptible/supercronic
ARG SUPERCRONIC_VERSION=0.2.33
ARG SUPERCRONIC_SHA1SUM=e0f0c06ebc5627e43b25475711e694450489ab00
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /usr/local/bin/supercronic \
       "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
    && echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum -c - \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r aggregator && useradd -r -g aggregator aggregator

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && chown -R aggregator:aggregator /app

USER aggregator

ENV PYTHONPATH=/app

# Health check: verify the aggregator ran recently (checks /tmp/aggregator.last_run)
# Falls back to a simple import check if timestamp file doesn't exist yet.
HEALTHCHECK --interval=5m --timeout=30s --start-period=120s --retries=3 \
    CMD python /app/docker/healthcheck.py || exit 1

# Default: run cron daemon. Set AGGREGATOR_MODE=once for a one-off run.
ENTRYPOINT ["/entrypoint.sh"]
