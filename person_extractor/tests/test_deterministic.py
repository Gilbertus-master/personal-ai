"""Tests for deterministic identity resolution."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4


from person_extractor.models import PersonCandidate, RawRecord
from person_extractor.resolution.deterministic import resolve_deterministic


def _raw():
    return RawRecord(
        source_name="test", source_table="t", source_record_id="1",
        record_type="contact", occurred_at=None, raw_data={},
    )


def _candidate(**kwargs):
    defaults = {"source_record": _raw(), "role_in_record": "contact"}
    defaults.update(kwargs)
    return PersonCandidate(**defaults)


def _mock_conn(return_value=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone = MagicMock(return_value=return_value)
    conn.cursor = MagicMock(return_value=cursor)
    return conn, cursor


class TestDeterministicResolution:
    def test_email_match(self):
        pid = uuid4()
        conn, cursor = _mock_conn(return_value=(pid,))
        candidate = _candidate(email="jan@firma.pl", channel="email")

        result = resolve_deterministic(candidate, conn)

        assert result == pid
        cursor.execute.assert_called()

    def test_no_match(self):
        conn, cursor = _mock_conn(return_value=None)
        candidate = _candidate(email="unknown@test.com", channel="email")

        result = resolve_deterministic(candidate, conn)

        assert result is None

    def test_phone_match(self):
        pid = uuid4()
        conn, cursor = _mock_conn(return_value=(pid,))
        candidate = _candidate(phone="+48601234567", channel="phone")

        result = resolve_deterministic(candidate, conn)

        assert result == pid

    def test_no_identifiers(self):
        conn, _ = _mock_conn()
        candidate = _candidate(full_name="Jan Kowalski")

        result = resolve_deterministic(candidate, conn)

        assert result is None

    def test_username_match(self):
        pid = uuid4()
        conn, cursor = _mock_conn(return_value=(pid,))
        candidate = _candidate(username="jkowalski", channel="telegram")

        result = resolve_deterministic(candidate, conn)

        assert result == pid
