"""Tests for deduplication hash functions."""
from aggregator.normalisation.dedup import (
    calculate_canonical_hash_fuzzy,
    calculate_canonical_hash_strict,
    calculate_description_fingerprint,
)


class TestCalculateCanonicalHashStrict:
    def test_same_input_produces_same_hash(self):
        h1 = calculate_canonical_hash_strict("Software Engineer", "Acme Corp", "Berlin")
        h2 = calculate_canonical_hash_strict("Software Engineer", "Acme Corp", "Berlin")
        assert h1 == h2

    def test_different_title_produces_different_hash(self):
        h1 = calculate_canonical_hash_strict("Software Engineer", "Acme Corp", "Berlin")
        h2 = calculate_canonical_hash_strict("Senior Engineer", "Acme Corp", "Berlin")
        assert h1 != h2

    def test_case_insensitive(self):
        h1 = calculate_canonical_hash_strict("software engineer", "acme corp", "berlin")
        h2 = calculate_canonical_hash_strict("Software Engineer", "Acme Corp", "Berlin")
        assert h1 == h2

    def test_returns_hex_string(self):
        h = calculate_canonical_hash_strict("Dev", "Co", "NYC")
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest

    def test_special_chars_stripped(self):
        # Punctuation should be stripped, so these should produce the same hash
        h1 = calculate_canonical_hash_strict("Full-Stack Dev", "Acme, Inc.", "Berlin")
        h2 = calculate_canonical_hash_strict("FullStack Dev", "Acme Inc", "Berlin")
        assert h1 == h2

    def test_empty_strings_dont_raise(self):
        h = calculate_canonical_hash_strict("", "", "")
        assert isinstance(h, str)


class TestCalculateDescriptionFingerprint:
    def test_same_text_same_fingerprint(self):
        desc = "We are looking for a talented engineer to join our team."
        f1 = calculate_description_fingerprint(desc)
        f2 = calculate_description_fingerprint(desc)
        assert f1 == f2

    def test_different_text_different_fingerprint(self):
        f1 = calculate_description_fingerprint("We need a Python developer.")
        f2 = calculate_description_fingerprint("Looking for a Java developer.")
        assert f1 != f2

    def test_none_returns_none(self):
        assert calculate_description_fingerprint(None) is None

    def test_empty_string_returns_none(self):
        assert calculate_description_fingerprint("") is None

    def test_strips_html_tags(self):
        plain = "We need a Python developer"
        html = "<p>We need a <strong>Python</strong> developer</p>"
        assert calculate_description_fingerprint(plain) == calculate_description_fingerprint(html)

    def test_returns_16_char_hex(self):
        f = calculate_description_fingerprint("Some job description text here.")
        assert isinstance(f, str)
        assert len(f) == 16

    def test_case_insensitive(self):
        f1 = calculate_description_fingerprint("python developer remote")
        f2 = calculate_description_fingerprint("PYTHON DEVELOPER REMOTE")
        assert f1 == f2


class TestCalculateCanonicalHashFuzzy:
    def test_same_input_same_hash(self):
        fp = calculate_description_fingerprint("We are hiring a great engineer.")
        h1 = calculate_canonical_hash_fuzzy("Acme Corp", "Berlin", fp)
        h2 = calculate_canonical_hash_fuzzy("Acme Corp", "Berlin", fp)
        assert h1 == h2

    def test_different_company_different_hash(self):
        fp = calculate_description_fingerprint("Same job description everywhere.")
        h1 = calculate_canonical_hash_fuzzy("Company A", "Berlin", fp)
        h2 = calculate_canonical_hash_fuzzy("Company B", "Berlin", fp)
        assert h1 != h2

    def test_none_fingerprint_still_works(self):
        h = calculate_canonical_hash_fuzzy("Acme", "Berlin", None)
        assert isinstance(h, str)
        assert len(h) == 32

    def test_cross_source_dedup(self):
        """Two jobs from different sources with same company/location/description → same fuzzy hash."""
        desc = "Build and maintain scalable distributed systems."
        fp = calculate_description_fingerprint(desc)
        h1 = calculate_canonical_hash_fuzzy("Tech Corp", "Remote", fp)
        h2 = calculate_canonical_hash_fuzzy("Tech Corp", "Remote", fp)
        assert h1 == h2
