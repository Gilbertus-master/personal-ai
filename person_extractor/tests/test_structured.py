"""Tests for structured extraction functions."""

from __future__ import annotations

from datetime import datetime


from person_extractor.extractors.structured import (
    extract_from_record,
    normalize_email,
    normalize_phone,
    parse_email_list,
)
from person_extractor.models import RawRecord


# ─── normalize_email ──────────────────────────────────────────────────

class TestNormalizeEmail:
    def test_basic(self):
        assert normalize_email("Jan@Firma.PL") == "jan@firma.pl"

    def test_whitespace(self):
        assert normalize_email("  jan@firma.pl  ") == "jan@firma.pl"

    def test_none(self):
        assert normalize_email(None) is None

    def test_empty(self):
        assert normalize_email("") is None


# ─── normalize_phone ─────────────────────────────────────────────────

class TestNormalizePhone:
    def test_basic(self):
        assert normalize_phone("+48 601 234 567") == "+48601234567"

    def test_dashes(self):
        assert normalize_phone("601-234-567") == "601234567"

    def test_parens(self):
        assert normalize_phone("(48) 601 234 567") == "48601234567"

    def test_too_short(self):
        assert normalize_phone("123") is None

    def test_none(self):
        assert normalize_phone(None) is None


# ─── parse_email_list ─────────────────────────────────────────────────

class TestParseEmailList:
    def test_csv(self):
        result = parse_email_list("a@b.com, c@d.com")
        assert result == ["a@b.com", "c@d.com"]

    def test_semicolon(self):
        result = parse_email_list("a@b.com; c@d.com")
        assert result == ["a@b.com", "c@d.com"]

    def test_json_array(self):
        result = parse_email_list('["a@b.com", "c@d.com"]')
        assert result == ["a@b.com", "c@d.com"]

    def test_json_objects(self):
        result = parse_email_list('[{"email": "a@b.com"}, {"email": "c@d.com"}]')
        assert result == ["a@b.com", "c@d.com"]

    def test_none(self):
        assert parse_email_list(None) == []

    def test_empty(self):
        assert parse_email_list("") == []

    def test_single(self):
        assert parse_email_list("a@b.com") == ["a@b.com"]

    def test_filters_non_emails(self):
        result = parse_email_list("Jan Kowalski, a@b.com")
        assert result == ["a@b.com"]


# ─── extract_from_record ─────────────────────────────────────────────

def _make_raw(record_type: str, data: dict) -> RawRecord:
    return RawRecord(
        source_name="test",
        source_table="test_table",
        source_record_id="1",
        record_type=record_type,
        occurred_at=datetime.now(),
        raw_data=data,
    )


class TestExtractFromRecord:
    def test_contact(self):
        record = _make_raw("contact", {
            "full_name": "Jan Kowalski",
            "email": "jan@firma.pl",
            "phone": "+48601234567",
        })
        config = {
            "columns": {"full_name": "full_name", "email": "email", "phone": "phone"},
            "channel": "email",
        }
        candidates = extract_from_record(record, config)
        assert len(candidates) == 1
        assert candidates[0].full_name == "Jan Kowalski"
        assert candidates[0].email == "jan@firma.pl"
        assert candidates[0].role_in_record == "contact"

    def test_email_with_recipients(self):
        record = _make_raw("email", {
            "from_name": "Jan",
            "from_email": "jan@firma.pl",
            "to_emails": "anna@firma.pl, marek@firma.pl",
            "cc_emails": "boss@firma.pl",
        })
        config = {
            "columns": {
                "from_name": "from_name",
                "from_email": "from_email",
                "to_emails": "to_emails",
                "cc_emails": "cc_emails",
            },
            "channel": "email",
        }
        candidates = extract_from_record(record, config)
        assert len(candidates) == 4  # sender + 2 to + 1 cc
        roles = [c.role_in_record for c in candidates]
        assert "sender" in roles
        assert "recipient" in roles
        assert "recipient_cc" in roles

    def test_message(self):
        record = _make_raw("message", {
            "sender_name": "Jan Kowalski",
            "sender_username": "jkowalski",
            "text": "Hello world",
        })
        config = {
            "columns": {
                "sender_name": "sender_name",
                "sender_username": "sender_username",
            },
            "channel": "telegram",
        }
        candidates = extract_from_record(record, config)
        assert len(candidates) == 1
        assert candidates[0].username == "jkowalski"
        assert candidates[0].channel == "telegram"

    def test_empty_record_yields_nothing(self):
        record = _make_raw("contact", {})
        config = {"columns": {}, "channel": "email"}
        candidates = extract_from_record(record, config)
        assert len(candidates) == 0

    def test_calendar_event(self):
        record = _make_raw("calendar_event", {
            "organizer_email": "jan@firma.pl",
            "attendees_json": '[{"email": "anna@firma.pl", "name": "Anna"}]',
        })
        config = {
            "columns": {
                "organizer_email": "organizer_email",
                "attendee_emails": "attendees_json",
            },
            "channel": "email",
        }
        candidates = extract_from_record(record, config)
        assert len(candidates) == 2
        assert candidates[0].role_in_record == "sender"
        assert candidates[1].role_in_record == "attendee"
        assert candidates[1].full_name == "Anna"
