"""Structured extraction — parse known fields from RawRecord."""

from __future__ import annotations

import json
import re
from typing import Optional

from ..models import PersonCandidate, RawRecord


def extract_from_record(record: RawRecord, config: dict) -> list[PersonCandidate]:
    """Extract PersonCandidates from a RawRecord using column mapping."""
    candidates: list[PersonCandidate] = []
    col_map = config.get("columns", {})
    channel = config.get("channel", "email")
    row = record.raw_data

    if record.record_type == "contact":
        candidate = PersonCandidate(
            source_record=record,
            role_in_record="contact",
            full_name=_get(row, col_map, "full_name"),
            email=normalize_email(_get(row, col_map, "email")),
            phone=normalize_phone(_get(row, col_map, "phone")),
            job_title=_get(row, col_map, "job_title"),
            company=_get(row, col_map, "company"),
            channel=channel,
            extraction_method="structured",
            extraction_confidence=1.0,
        )
        if _has_identifier(candidate):
            candidates.append(candidate)

    elif record.record_type == "email":
        from_name = _get(row, col_map, "from_name")
        from_email = normalize_email(_get(row, col_map, "from_email"))

        if from_email:
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="sender",
                    full_name=from_name,
                    email=from_email,
                    channel="email",
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

        for email in parse_email_list(_get(row, col_map, "to_emails")):
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="recipient",
                    email=normalize_email(email),
                    channel="email",
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

        for email in parse_email_list(_get(row, col_map, "cc_emails")):
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="recipient_cc",
                    email=normalize_email(email),
                    channel="email",
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

    elif record.record_type == "message":
        sender_name = _get(row, col_map, "sender_name")
        sender_username = _get(row, col_map, "sender_username")
        sender_phone = _get(row, col_map, "sender_phone")

        if sender_name or sender_username or sender_phone:
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="sender",
                    full_name=sender_name,
                    username=sender_username,
                    phone=normalize_phone(sender_phone),
                    channel=channel,
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

        recipient_name = _get(row, col_map, "recipient_name")
        if recipient_name:
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="recipient",
                    full_name=recipient_name,
                    channel=channel,
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

    elif record.record_type == "calendar_event":
        organizer_email = normalize_email(_get(row, col_map, "organizer_email"))
        if organizer_email:
            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record="sender",
                    email=organizer_email,
                    channel="email",
                    extraction_method="structured",
                    extraction_confidence=1.0,
                )
            )

        attendees_raw = _get(row, col_map, "attendee_emails")
        if attendees_raw:
            for att in _parse_attendees(attendees_raw):
                candidates.append(
                    PersonCandidate(
                        source_record=record,
                        role_in_record="attendee",
                        full_name=att.get("name"),
                        email=normalize_email(att.get("email")),
                        channel="email",
                        extraction_method="structured",
                        extraction_confidence=1.0,
                    )
                )

    return [c for c in candidates if _has_identifier(c)]


# ─── Helpers (public — used in tests) ────────────────────────────────

def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    normalized = re.sub(r"[\s\-\(\)\.]+", "", phone)
    return normalized if len(normalized) >= 7 else None


def parse_email_list(value: Optional[str]) -> list[str]:
    """Parse emails from CSV, JSON array, or single string."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [
                (item if isinstance(item, str) else item.get("email", ""))
                for item in parsed
                if item
            ]
    except (json.JSONDecodeError, TypeError):
        pass
    return [e.strip() for e in re.split(r"[,;]", value) if "@" in e]


def _has_identifier(c: PersonCandidate) -> bool:
    return any([c.email, c.phone, c.username, c.full_name])


def _get(row: dict, col_map: dict, field: str) -> Optional[str]:
    col = col_map.get(field)
    if not col:
        return None
    val = row.get(col)
    return str(val).strip() if val else None


def _parse_attendees(raw: str) -> list[dict]:
    """Parse attendee list from JSON string."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []
