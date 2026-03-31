"""Tests for candidate normalizer."""

from __future__ import annotations

from datetime import datetime


from person_extractor.extractors.normalizer import normalize_candidate
from person_extractor.models import PersonCandidate, RawRecord


def _raw():
    return RawRecord(
        source_name="test", source_table="t", source_record_id="1",
        record_type="contact", occurred_at=datetime.now(), raw_data={},
    )


def _candidate(**kwargs):
    defaults = {"source_record": _raw(), "role_in_record": "contact"}
    defaults.update(kwargs)
    return PersonCandidate(**defaults)


class TestNormalizeCandidate:
    def test_valid_email_candidate(self):
        c = _candidate(email="Jan@Firma.PL")
        result = normalize_candidate(c)
        assert result is not None
        assert result.email == "jan@firma.pl"
        assert result.channel == "email"

    def test_noreply_filtered(self):
        c = _candidate(email="noreply@firma.pl")
        assert normalize_candidate(c) is None

    def test_bot_name_filtered(self):
        c = _candidate(full_name="GitHub Bot", email="bot@github.com")
        assert normalize_candidate(c) is None

    def test_empty_candidate_filtered(self):
        c = _candidate()
        assert normalize_candidate(c) is None

    def test_name_normalization(self):
        c = _candidate(full_name="JAN KOWALSKI", email="jan@firma.pl")
        result = normalize_candidate(c)
        assert result.full_name == "Jan Kowalski"

    def test_phone_candidate(self):
        c = _candidate(phone="+48 601 234 567")
        result = normalize_candidate(c)
        assert result is not None
        assert result.phone == "+48601234567"
        assert result.channel == "phone"

    def test_username_stripping(self):
        c = _candidate(username="@jkowalski", channel="telegram")
        result = normalize_candidate(c)
        assert result.username == "jkowalski"

    def test_email_in_name_rejected(self):
        c = _candidate(full_name="jan@firma.pl", email="jan@firma.pl")
        result = normalize_candidate(c)
        assert result is not None
        assert result.full_name is None  # email-looking name rejected

    def test_digit_name_rejected(self):
        c = _candidate(full_name="12345678", email="test@test.pl")
        result = normalize_candidate(c)
        assert result is not None
        assert result.full_name is None
