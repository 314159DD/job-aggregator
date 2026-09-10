"""
sources/apis/jobicy.py - Jobicy

API: https://jobicy.com/api/v2/remote-jobs
Auth: None - Pagination: fetches all pages until empty response.
Notable: returns structured salary fields directly.

"""

import logging

import requests

from aggregator.normalisation import normalise_job
from sources.base import BaseSource

log = logging.getLogger(__name__)

_API_URL = 'https://jobicy.com/api/v2/remote-jobs'


class JobicySource(BaseSource):
    name = "jobicy"
    display_name = "Jobicy"
    source_type = "api"
    auth_type = "none"
    rate_limit = 30
    enabled = True

    def fetch(self, search_terms=None, locations=None) -> list:
        log.info("Fetching from Jobicy...")
        all_jobs = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            page = 1
            while True:
                try:
                    url = f"{_API_URL}?page={page}" if page > 1 else _API_URL
                    resp = requests.get(url, headers=headers, timeout=30)
                    resp.raise_for_status()
                    jobs = resp.json().get('jobs', [])
                    if not jobs:
                        break
                    for j in jobs:
                        sal_min = j.get('salaryMin')
                        sal_max = j.get('salaryMax')
                        cur = j.get('salaryCurrency', '')
                        per = j.get('salaryPeriod', '')
                        salary_str = f"{sal_min}-{sal_max} {cur}/{per}" if sal_min and sal_max else ''
                        all_jobs.append({
                            'id': f"jobicy_{j.get('id')}",
                            'url': j.get('url'),
                            'title': j.get('jobTitle'),
                            'company': j.get('companyName'),
                            'location': j.get('jobGeo') or 'Remote',
                            'description': j.get('jobExcerpt', ''),
                            'salary': salary_str,
                            'salary_min': int(sal_min) if sal_min else None,
                            'salary_max': int(sal_max) if sal_max else None,
                            'salary_currency': cur or None,
                            'salary_period': per or None,
                        })
                    log.debug(f"  Page {page}: {len(jobs)} jobs")
                    page += 1
                except Exception as e:
                    log.warning(f"  Page {page} error: {e}")
                    break
        except Exception as e:
            log.error(f"Jobicy error: {e}")
        log.info(f"Jobicy: {len(all_jobs)} total jobs")
        return all_jobs

    def normalise(self, raw_jobs: list) -> list:
        return [normalise_job(j, self.name) for j in raw_jobs]
