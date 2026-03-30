from __future__ import annotations

import re
from typing import Any


SENSITIVE_LINE_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"hasło", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"api[\s_-]*key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"private[\s_-]*key", re.IGNORECASE),
    re.compile(r"my old password is", re.IGNORECASE),
]

# Bardzo prosty wzorzec do przypadków typu:
# "My old password is XYZ"
INLINE_SECRET_PATTERNS = [
    re.compile(r"(my old password is\s*)(.+)", re.IGNORECASE),
    re.compile(r"(hasło\s*[:=]\s*)(.+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)(.+)", re.IGNORECASE),
    re.compile(r"(api[\s_-]*key\s*[:=]\s*)(.+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)(.+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)(.+)", re.IGNORECASE),
]


def _line_is_sensitive(line: str) -> bool:
    return any(pattern.search(line) for pattern in SENSITIVE_LINE_PATTERNS)


def redact_text(text: str | None) -> tuple[str | None, int]:
    """
    Redaguje tekst linia po linii.
    Zwraca:
    - zredagowany tekst
    - liczbę redakcji
    """
    if text is None:
        return None, 0

    lines = str(text).splitlines()
    redacted_count = 0
    output_lines: list[str] = []

    for line in lines:
        original_line = line

        # Najpierw próbujemy redakcji inline typu "password: xyz"
        for pattern in INLINE_SECRET_PATTERNS:
            if pattern.search(line):
                line = pattern.sub(r"\1[REDACTED SENSITIVE VALUE]", line)
                redacted_count += 1

        # Jeśli linia nadal wygląda na wrażliwą, ukrywamy całą linię
        if _line_is_sensitive(line):
            if line == original_line:
                line = "[REDACTED SENSITIVE CONTENT]"
                redacted_count += 1

        output_lines.append(line)

    return "\n".join(output_lines), redacted_count


def redact_match(match: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """
    Zwraca kopię matcha z zredagowanym polem text/chunk_text/excerpt.
    """
    redacted = dict(match)
    total_redactions = 0

    if "text" in redacted:
        new_text, count = redact_text(redacted["text"])
        redacted["text"] = new_text
        total_redactions += count

    if "chunk_text" in redacted:
        new_text, count = redact_text(redacted["chunk_text"])
        redacted["chunk_text"] = new_text
        total_redactions += count

    if "excerpt" in redacted:
        new_text, count = redact_text(redacted["excerpt"])
        redacted["excerpt"] = new_text
        total_redactions += count

    metadata = redacted.get("metadata")
    if isinstance(metadata, dict):
        metadata_copy = dict(metadata)
        if "text" in metadata_copy:
            new_text, count = redact_text(metadata_copy["text"])
            metadata_copy["text"] = new_text
            total_redactions += count
        redacted["metadata"] = metadata_copy

    return redacted, total_redactions


def redact_matches(matches: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """
    Redaguje całą listę matchy.
    """
    output: list[dict[str, Any]] = []
    total_redactions = 0

    for match in matches:
        redacted_match, count = redact_match(match)
        output.append(redacted_match)
        total_redactions += count

    return output, total_redactions
