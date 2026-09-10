"""
Job Aggregator - Standalone data acquisition service.

Fetches job listings from APIs, scrapers, and feeds,
normalises them, and syncs to Supabase.

Usage:
    python -m aggregator              # Run all enabled sources
    python -m aggregator --source X   # Run single source
    python -m aggregator --dry-run    # Fetch without DB writes
"""
