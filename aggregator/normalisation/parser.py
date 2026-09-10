"""
aggregator/normalisation/parser.py - Main normalisation entry point.

Coordinates all sub-parsers and returns a complete JobRecord.
This file is ONLY the coordinator - logic lives in sub-modules.
"""

from aggregator.models import JobRecord

from .cleaner import clean_html, truncate_description
from .dedup import (
    calculate_canonical_hash_fuzzy,
    calculate_canonical_hash_strict,
    calculate_description_fingerprint,
)
from .job_fields import (
    parse_employment_type,
    parse_location,
    parse_posted_date,
    parse_remote_type,
    parse_seniority,
)
from .salary import parse_salary


def normalise_job(raw: dict, source: str) -> JobRecord:
    """Convert a raw source dict to a normalised JobRecord.

    Args:
        raw: Dict with keys: id, title, company, location, description,
             url, salary (and optionally: salary_min, salary_max,
             salary_currency, salary_period, posted_at, source_job_id)
        source: Source name string (e.g. 'arbeitsamt')

    Returns:
        Fully populated JobRecord
    """
    title = (raw.get('title') or '').strip()
    company = (raw.get('company') or '').strip()
    location_raw = (raw.get('location') or '').strip()
    description_raw = raw.get('description') or ''

    description = truncate_description(clean_html(description_raw))

    # Prefer source-provided hints over text inference
    remote_type = raw.get('remote_type') or parse_remote_type(title, location_raw, description)
    location_city, location_country = parse_location(location_raw)
    seniority = raw.get('seniority') or parse_seniority(title, description)
    employment_type = raw.get('employment_type') or parse_employment_type(title, description)

    # Salary - source may provide structured fields directly
    salary_raw_str = raw.get('salary') or ''
    if raw.get('salary_min') is not None:
        sal_min = raw.get('salary_min')
        sal_max = raw.get('salary_max')
        sal_cur = raw.get('salary_currency')
        sal_per = raw.get('salary_period')
        sal_conf = 0.9
    else:
        sal_min, sal_max, sal_cur, sal_per, sal_conf = parse_salary(salary_raw_str)

    desc_fp = calculate_description_fingerprint(description)
    hash_strict = calculate_canonical_hash_strict(title, company, location_raw)
    hash_fuzzy = calculate_canonical_hash_fuzzy(company, location_raw, desc_fp)

    return JobRecord(
        external_id=str(raw.get('id') or ''),
        source=source,
        title=title,
        company=company or None,
        location=location_raw or None,
        url=raw.get('url') or None,
        description=description or None,
        posted_at=parse_posted_date(raw.get('posted_at')) or None,
        remote_type=remote_type,
        location_city=location_city,
        location_country=location_country,
        seniority=seniority,
        employment_type=employment_type,
        salary=salary_raw_str or None,
        salary_raw=salary_raw_str or None,
        salary_min=sal_min,
        salary_max=sal_max,
        salary_currency=sal_cur,
        salary_period=sal_per,
        salary_confidence=sal_conf if sal_conf else None,
        canonical_hash_strict=hash_strict,
        canonical_hash_fuzzy=hash_fuzzy,
        description_fingerprint=desc_fp,
        source_job_id=raw.get('source_job_id') or None,
    )
