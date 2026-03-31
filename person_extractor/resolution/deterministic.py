"""Deterministic identity resolution — exact match on email/phone/username."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from ..models import PersonCandidate


def resolve_deterministic(
    candidate: PersonCandidate, conn
) -> Optional[UUID]:
    """Check person_identities for exact match. Returns person_id or None.

    Priority: email > phone > username.
    """
    checks: list[tuple[str, str]] = []

    if candidate.email:
        checks.append(("email", candidate.email))
    if candidate.phone:
        checks.append(("phone", candidate.phone))
        checks.append(("sms", candidate.phone))
        checks.append(("whatsapp", candidate.phone))
    if candidate.username and candidate.channel:
        checks.append((candidate.channel, candidate.username))

    if not checks:
        return None

    with conn.cursor() as cur:
        for channel, identifier in checks:
            cur.execute(
                """SELECT person_id FROM person_identities
                   WHERE channel = %s AND identifier = %s
                     AND is_active = true AND is_shared = false
                   LIMIT 1""",
                (channel, identifier),
            )
            row = cur.fetchone()
            if row:
                return row[0]

    return None


def check_shared_identifier(identifier: str, channel: str, conn) -> bool:
    """Check if an identifier is shared by multiple persons."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(DISTINCT person_id) FROM person_identities
               WHERE channel = %s AND identifier = %s AND is_active = true""",
            (channel, identifier),
        )
        count = cur.fetchone()[0]
    return count > 1
