"""
aggregator/normalisation/job_fields.py - Job field parsing.

"""

import re
from datetime import datetime, timedelta


def parse_remote_type(title, location, description):
    """Parse remote work type from job data."""
    text = f"{title} {location} {description}".lower()
    if any(word in text for word in ['remote', '100% remote', 'fully remote', 'work from home']):
        if any(word in text for word in ['hybrid', 'office days', 'days in office']):
            return 'hybrid'
        return 'remote'
    elif any(word in text for word in ['on-site', 'onsite', 'in office', 'office-based']):
        return 'onsite'
    return 'unknown'


def parse_location(location_str):
    """Parse location into (city, country) tuple."""
    if not location_str:
        return None, None
    location_str = location_str.strip()
    if ',' in location_str:
        parts = [p.strip() for p in location_str.split(',')]
        return parts[0], parts[-1] if len(parts) > 1 else None
    if location_str.lower() == 'remote':
        return None, None
    return location_str, None


def parse_seniority(title, description):
    """Parse seniority level from title and description."""
    text = f"{title} {description}".lower()
    if any(word in text for word in ['senior', 'sr.', 'lead', 'principal', 'staff']):
        if 'lead' in text or 'principal' in text or 'staff' in text:
            return 'lead'
        return 'senior'
    elif any(word in text for word in ['junior', 'jr.', 'entry', 'graduate']):
        return 'junior'
    elif any(word in text for word in ['mid-level', 'intermediate', 'experienced']):
        return 'mid'
    return 'unknown'


def parse_employment_type(title, description):
    """Parse employment type from title and description."""
    text = f"{title} {description}".lower()
    if any(word in text for word in ['contract', 'contractor', 'freelance']):
        return 'contract'
    elif any(word in text for word in ['part-time', 'part time']):
        return 'part-time'
    elif any(word in text for word in ['full-time', 'full time', 'permanent']):
        return 'full-time'
    return 'full-time'


def parse_posted_date(date_str):
    """Parse various date formats to ISO string."""
    if not date_str:
        return None
    if 'ago' in str(date_str).lower():
        match = re.match(r'(\d+)\s+(day|week|month)s?\s+ago', str(date_str).lower())
        if match:
            count = int(match.group(1))
            unit = match.group(2)
            if unit == 'day':
                return (datetime.now() - timedelta(days=count)).isoformat()
            elif unit == 'week':
                return (datetime.now() - timedelta(weeks=count)).isoformat()
            elif unit == 'month':
                return (datetime.now() - timedelta(days=count * 30)).isoformat()
    # German date formats: DD.MM.YY or DD.MM.YYYY (e.g. "27.02.26", "27.02.2026")
    dot_match = re.match(r'^(\d{2})\.(\d{2})\.(\d{2,4})$', str(date_str).strip())
    if dot_match:
        try:
            fmt = '%d.%m.%y' if len(dot_match.group(3)) == 2 else '%d.%m.%Y'
            return datetime.strptime(str(date_str).strip(), fmt).isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(str(date_str)).isoformat()
    except Exception:
        pass
    return None
