"""
Tool Router — smart source-group mapping for /ask queries.

When the interpreter doesn't return explicit source_types, this module
infers the best source group based on question_type + keyword patterns.

Enable via ENABLE_TOOL_ROUTING=true in .env (default: false).
"""
from __future__ import annotations

import re

import structlog

log = structlog.get_logger("tool_router")

# ---------------------------------------------------------------------------
# Source groups
# ---------------------------------------------------------------------------

SOURCE_GROUPS: dict[str, list[str]] = {
    "personal_comms": ["whatsapp", "whatsapp_live"],
    "business_comms": ["email", "teams", "audio_transcript", "calendar"],
    "trading": ["document", "spreadsheet", "email", "pdf"],
    "knowledge": ["document", "chatgpt", "audio_transcript", "pdf"],
    "all": [],  # empty = no filter
}

# ---------------------------------------------------------------------------
# Keyword patterns → group mapping
# ---------------------------------------------------------------------------

_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(whatsapp|wiadomoś[ćc]|sms|czat)\b", re.IGNORECASE), "personal_comms"),
    (re.compile(r"\b(spotkani[eua]|teams|call|zoom|rozmow[aę]|audio|nagranie|transkrypc)\b", re.IGNORECASE), "business_comms"),
    (re.compile(r"\b(mail|email|e-mail|korespondencj[aę])\b", re.IGNORECASE), "business_comms"),
    (re.compile(r"\b(kalendarz|calendar|termin)\b", re.IGNORECASE), "business_comms"),
    (re.compile(r"\b(trad(?:ing|e)|cen[aęy]|PPA|kontrakt|umow[aęy]|faktur|ofert[aęy]|przetarg)\b", re.IGNORECASE), "trading"),
    (re.compile(r"\b(dokument|raport|analiz[aę]|notatk|pdf|arkusz|excel)\b", re.IGNORECASE), "knowledge"),
    (re.compile(r"\b(chatgpt|gpt|ai|claude)\b", re.IGNORECASE), "knowledge"),
]

# question_type → default group when no keywords match
_QUESTION_TYPE_DEFAULTS: dict[str, str] = {
    "retrieval": "all",
    "chronology": "all",
    "analysis": "knowledge",
    "summary": "all",
}


def route_tools(
    query: str,
    question_type: str | None = None,
    source_types: list[str] | None = None,
) -> list[str] | None:
    """
    Determine which source_types to query.

    Returns:
        list[str] of source types to filter on, or None for no filter (query all).
    """
    # If interpreter already provided explicit source_types, respect them
    if source_types is not None:
        log.debug("tool_router_passthrough", source_types=source_types)
        return source_types

    # Try keyword matching
    matched_group = _match_keywords(query)

    # Fall back to question_type default
    if not matched_group:
        matched_group = _QUESTION_TYPE_DEFAULTS.get(question_type or "", "all")

    sources = SOURCE_GROUPS.get(matched_group, [])

    if not sources:
        log.info("tool_router_all", group=matched_group, query=query[:80])
        return None  # no filter

    log.info("tool_router_matched", group=matched_group, sources=sources, query=query[:80])
    return sources


def _match_keywords(query: str) -> str | None:
    """Match query against keyword patterns, return group name or None."""
    scores: dict[str, int] = {}
    for pattern, group in _KEYWORD_PATTERNS:
        if pattern.search(query):
            scores[group] = scores.get(group, 0) + 1

    if not scores:
        return None

    # Return group with most matches
    return max(scores, key=lambda k: scores[k])
