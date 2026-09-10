"""Tests for salary parsing and normalisation helpers."""
import pytest

from aggregator.normalisation.salary import parse_salary


class TestParseSalary:
    def test_none_input(self):
        min_s, max_s, currency, period, confidence = parse_salary(None)
        assert min_s is None
        assert max_s is None
        assert confidence == 0.0

    def test_not_specified_string(self):
        min_s, max_s, currency, period, confidence = parse_salary("Not specified")
        assert min_s is None
        assert confidence == 0.0

    def test_range_eur(self):
        min_s, max_s, currency, period, confidence = parse_salary("60000 - 80000 EUR")
        assert min_s == 60000
        assert max_s == 80000
        assert currency == "EUR"
        assert confidence == pytest.approx(0.9)

    def test_range_k_notation(self):
        min_s, max_s, currency, period, confidence = parse_salary("60k - 80k")
        assert min_s == 60000
        assert max_s == 80000
        assert confidence == pytest.approx(0.9)

    def test_single_value(self):
        min_s, max_s, currency, period, confidence = parse_salary("70000 EUR")
        assert min_s == 70000
        assert max_s == 70000
        assert confidence == pytest.approx(0.7)

    def test_usd_currency(self):
        _, _, currency, _, _ = parse_salary("$100,000 - $120,000")
        assert currency == "USD"

    def test_gbp_currency(self):
        _, _, currency, _, _ = parse_salary("£50,000 - £60,000")
        assert currency == "GBP"

    def test_hourly_period(self):
        _, _, _, period, _ = parse_salary("30 - 40 EUR/hour")
        assert period == "hour"

    def test_monthly_period(self):
        _, _, _, period, _ = parse_salary("5000 - 6000 EUR/month")
        assert period == "month"

    def test_annual_period_default(self):
        _, _, _, period, _ = parse_salary("60000 - 80000 EUR")
        assert period == "year"

    def test_min_max_swap_if_reversed(self):
        # Input has max before min - should be swapped
        min_s, max_s, _, _, _ = parse_salary("80000 - 60000 EUR")
        assert min_s == 60000
        assert max_s == 80000

    def test_suspicious_range_reduces_confidence(self):
        # max is more than 2x min → confidence penalty
        min_s, max_s, _, _, confidence = parse_salary("30000 - 100000 EUR")
        assert confidence < 0.9

    def test_no_numbers_returns_no_values(self):
        min_s, max_s, _, _, confidence = parse_salary("competitive salary")
        assert min_s is None
        assert max_s is None
        assert confidence == 0.0
