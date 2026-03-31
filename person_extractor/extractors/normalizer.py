"""Normalization and cleaning of PersonCandidate data."""

from __future__ import annotations

import re
from typing import Optional

from ..models import PersonCandidate
from .structured import normalize_email, normalize_phone


# Common patterns to skip
_SKIP_EMAIL_PATTERNS = (
    "noreply", "no-reply", "donotreply", "notifications@",
    "newsletter@", "marketing@", "mailer-daemon", "postmaster@",
    "bounce@", "unsubscribe@",
)

_SKIP_NAME_PATTERNS = (
    "bot", "system", "automated", "notification", "admin",
)


def normalize_candidate(candidate: PersonCandidate) -> Optional[PersonCandidate]:
    """Normalize and validate a candidate. Returns None if invalid."""
    # Normalize identifiers
    candidate.email = normalize_email(candidate.email)
    candidate.phone = normalize_phone(candidate.phone)

    if candidate.full_name:
        candidate.full_name = _normalize_name(candidate.full_name)

    if candidate.username:
        candidate.username = candidate.username.strip().lstrip("@")

    # Skip obvious non-persons
    if candidate.email and any(p in candidate.email for p in _SKIP_EMAIL_PATTERNS):
        return None

    if candidate.full_name and any(
        p in candidate.full_name.lower() for p in _SKIP_NAME_PATTERNS
    ):
        return None

    # Must have at least one usable identifier
    if not any([candidate.email, candidate.phone, candidate.username, candidate.full_name]):
        return None

    # Infer channel if missing
    if not candidate.channel:
        if candidate.email:
            candidate.channel = "email"
        elif candidate.phone:
            candidate.channel = "phone"

    return candidate


def _normalize_name(name: str) -> Optional[str]:
    """Clean and normalize a person's name."""
    name = name.strip()

    # Remove quotes, brackets
    name = re.sub(r'["\'\[\]<>]', "", name)

    # Skip if it looks like an email
    if "@" in name:
        return None

    # Skip if too short or too long
    if len(name) < 2 or len(name) > 100:
        return None

    # Skip if mostly digits
    digits = sum(c.isdigit() for c in name)
    if digits > len(name) / 2:
        return None

    # Title case if all upper or all lower
    if name.isupper() or name.islower():
        name = name.title()

    return name
