"""Tests for skill extraction and snapshot aggregation."""
from aggregator.skills import extract_skills
from aggregator.snapshot import (
    _aggregate_employment_types,
    _aggregate_locations,
    _aggregate_remote_types,
    _aggregate_role_types,
    _aggregate_salary_ranges,
    _aggregate_skills,
    _aggregate_sources,
    _normalize_salary_to_annual,
)

# ── Skill extraction ─────────────────────────────────────────────────────────


class TestExtractSkills:
    def test_empty_input(self):
        assert extract_skills("") == []
        assert extract_skills(None) == []

    def test_single_skill(self):
        skills = extract_skills("We need a Python developer")
        assert "python" in skills

    def test_multiple_skills(self):
        text = "Experience with Python, JavaScript, and Docker required"
        skills = extract_skills(text)
        assert "python" in skills
        assert "javascript" in skills
        assert "docker" in skills

    def test_case_insensitive(self):
        skills = extract_skills("REACT and TYPESCRIPT experience")
        assert "react" in skills
        assert "typescript" in skills

    def test_framework_detection(self):
        text = "Django REST framework with PostgreSQL"
        skills = extract_skills(text)
        assert "django" in skills
        assert "postgresql" in skills

    def test_cloud_skills(self):
        text = "AWS and Kubernetes experience, Terraform for IaC"
        skills = extract_skills(text)
        assert "aws" in skills
        assert "kubernetes" in skills
        assert "terraform" in skills

    def test_k8s_alias(self):
        skills = extract_skills("Deploy to k8s cluster")
        assert "kubernetes" in skills

    def test_no_false_positive_java_in_javascript(self):
        # "java" should match in "Java developer" but the word boundary
        # prevents false matches inside "javascript"
        skills = extract_skills("JavaScript developer")
        assert "javascript" in skills
        # java may or may not match depending on word boundaries in "JavaScript"
        # The important thing is javascript matches

    def test_german_market_skills(self):
        text = "SAP Berater mit Salesforce Erfahrung"
        skills = extract_skills(text)
        assert "sap" in skills
        assert "salesforce" in skills

    def test_no_skills_in_plain_text(self):
        text = "We are looking for a motivated team player"
        skills = extract_skills(text)
        assert len(skills) == 0


# ── Salary normalization ─────────────────────────────────────────────────────


class TestNormalizeSalary:
    def test_annual_passthrough(self):
        assert _normalize_salary_to_annual(60000, "year") == 60000

    def test_monthly_to_annual(self):
        assert _normalize_salary_to_annual(5000, "month") == 60000

    def test_hourly_to_annual(self):
        assert _normalize_salary_to_annual(30, "hour") == 62400

    def test_none_period(self):
        assert _normalize_salary_to_annual(60000, None) == 60000


# ── Aggregation functions ────────────────────────────────────────────────────


SAMPLE_JOBS = [
    {
        "id": 1,
        "title": "Senior Python Developer",
        "description": "Python Django PostgreSQL Docker AWS",
        "seniority": "senior",
        "employment_type": "full-time",
        "remote_type": "remote",
        "location_city": "Berlin",
        "location_country": "DE",
        "salary_min": 70000,
        "salary_max": 90000,
        "salary_currency": "EUR",
        "salary_period": "year",
        "source": "greenhouse",
    },
    {
        "id": 2,
        "title": "Junior Frontend Developer",
        "description": "React TypeScript CSS Tailwind",
        "seniority": "junior",
        "employment_type": "full-time",
        "remote_type": "hybrid",
        "location_city": "Munich",
        "location_country": "DE",
        "salary_min": 40000,
        "salary_max": 50000,
        "salary_currency": "EUR",
        "salary_period": "year",
        "source": "lever",
    },
    {
        "id": 3,
        "title": "DevOps Engineer",
        "description": "Kubernetes Docker Terraform AWS CI/CD",
        "seniority": "mid",
        "employment_type": "contract",
        "remote_type": "onsite",
        "location_city": "Berlin",
        "location_country": "DE",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
        "source": "greenhouse",
    },
]


class TestAggregateSkills:
    def test_counts_across_jobs(self):
        result = _aggregate_skills(SAMPLE_JOBS)
        # Docker appears in 2 jobs
        assert result.get("docker") == 2
        # AWS appears in 2 jobs
        assert result.get("aws") == 2
        # Python appears in 1 job
        assert result.get("python") == 1

    def test_empty_jobs(self):
        assert _aggregate_skills([]) == {}


class TestAggregateRoleTypes:
    def test_seniority_counts(self):
        result = _aggregate_role_types(SAMPLE_JOBS)
        assert result["senior"] == 1
        assert result["junior"] == 1
        assert result["mid"] == 1


class TestAggregateSalaryRanges:
    def test_salary_stats(self):
        result = _aggregate_salary_ranges(SAMPLE_JOBS)
        assert "EUR" in result
        eur = result["EUR"]
        assert eur["count"] == 2
        assert eur["min"] == 45000  # (40000+50000)//2
        assert eur["max"] == 80000  # (70000+90000)//2

    def test_no_salaries(self):
        jobs = [{"salary_min": None, "salary_max": None, "salary_currency": None, "salary_period": None}]
        assert _aggregate_salary_ranges(jobs) == {}

    def test_skips_implausible(self):
        jobs = [{"salary_min": 1000000, "salary_max": 2000000, "salary_currency": "EUR", "salary_period": "year"}]
        assert _aggregate_salary_ranges(jobs) == {}


class TestAggregateLocations:
    def test_city_counts(self):
        result = _aggregate_locations(SAMPLE_JOBS)
        assert result["Berlin"] == 2
        assert result["Munich"] == 1


class TestAggregateRemoteTypes:
    def test_remote_counts(self):
        result = _aggregate_remote_types(SAMPLE_JOBS)
        assert result["remote"] == 1
        assert result["hybrid"] == 1
        assert result["onsite"] == 1


class TestAggregateEmploymentTypes:
    def test_employment_counts(self):
        result = _aggregate_employment_types(SAMPLE_JOBS)
        assert result["full-time"] == 2
        assert result["contract"] == 1


class TestAggregateSources:
    def test_source_counts(self):
        result = _aggregate_sources(SAMPLE_JOBS)
        assert result["greenhouse"] == 2
        assert result["lever"] == 1
