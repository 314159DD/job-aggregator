# Job Aggregator - Makefile

.PHONY: run run-source dry-run test lint health clean \
        docker-build docker-run docker-once docker-discover docker-health docker-logs docker-stop

# Run all enabled sources
run:
	python -m aggregator

# Run a single source
run-source:
	python -m aggregator --source $(SOURCE)

# Dry run (fetch without DB writes)
dry-run:
	python -m aggregator --dry-run

# Run freshness check
freshness:
	python -m aggregator --freshness-check

# Print source health report
health:
	python scripts/health_report.py

# Test a single source
test-source:
	python scripts/test_source.py $(SOURCE)

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=aggregator --cov=sources --cov-report=html

# Lint
lint:
	python -m py_compile aggregator/__main__.py
	python -m py_compile aggregator/orchestrator.py

# Setup
setup:
	python -m venv venv
	./venv/bin/pip install -r requirements.txt
	cp -n .env.example .env || true

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name '*.pyc' -delete
	rm -rf .pytest_cache htmlcov .coverage

# ── Docker targets ──────────────────────────────────────────────────
# Build the Docker image
docker-build:
	docker compose build

# Start cron daemon in background
docker-run:
	docker compose up -d

# One-off run (fetch all sources once and exit)
docker-once:
	docker compose run --rm -e AGGREGATOR_MODE=once job-aggregator

# Full discovery suite (one-off)
docker-discover:
	docker compose run --rm -e AGGREGATOR_MODE=discover job-aggregator

# Print health report (one-off)
docker-health:
	docker compose run --rm -e AGGREGATOR_MODE=health job-aggregator

# Follow live logs from cron daemon
docker-logs:
	docker compose logs -f job-aggregator

# Stop and remove the cron daemon container
docker-stop:
	docker compose down
