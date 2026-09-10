"""
aggregator/normalisation/salary.py - Salary string parsing.

"""

import re


def parse_salary(salary_str):
    """
    Parse salary string into (min, max, currency, period, confidence).

    Returns:
        tuple: (salary_min, salary_max, currency, period, confidence)
    """
    if not salary_str or salary_str == 'Not specified':
        return None, None, None, None, 0.0

    salary_str_clean = salary_str.replace(',', '').replace(' ', '')

    currency = 'EUR'
    if '$' in salary_str_clean:
        currency = 'USD'
    elif '£' in salary_str_clean:
        currency = 'GBP'
    elif '€' in salary_str_clean or 'EUR' in salary_str_clean.upper():
        currency = 'EUR'

    numbers = re.findall(r'(\d+)k?', salary_str_clean.lower())

    confidence = 0.0
    if len(numbers) >= 2:
        min_sal = int(numbers[0]) * (1000 if 'k' in salary_str_clean.lower() else 1)
        max_sal = int(numbers[1]) * (1000 if 'k' in salary_str_clean.lower() else 1)
        confidence = 0.9
    elif len(numbers) == 1:
        min_sal = int(numbers[0]) * (1000 if 'k' in salary_str_clean.lower() else 1)
        max_sal = min_sal
        confidence = 0.7
    else:
        return None, None, currency, None, 0.0

    if min_sal > max_sal:
        min_sal, max_sal = max_sal, min_sal

    if max_sal > min_sal * 2:
        confidence *= 0.7

    period = 'year'
    if any(word in salary_str.lower() for word in ['hour', 'hr', '/h']):
        period = 'hour'
    elif any(word in salary_str.lower() for word in ['month', '/m', 'monthly']):
        period = 'month'

    return min_sal, max_sal, currency, period, confidence
