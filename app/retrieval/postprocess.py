from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from app.retrieval.relevance import rerank_matches_by_relevance


POLISH_STOPWORDS = {
    "i", "oraz", "a", "ale", "że", "to", "na", "w", "z", "do", "o", "od",
    "jak", "jakie", "jaka", "jaką", "jak", "co", "czy", "się", "mi", "mnie",
    "moje", "moją", "moich", "były", "było", "była", "dla", "po", "pod",
    "nad", "przy", "jest", "są", "być", "miałem", "mam", "masz", "mój",
    "twoje", "wszystkiego", "wiesz", "na podstawie", "wszystko",
}


def normalize_text_for_dedup(text: str | None, max_chars: int = 220) -> str:
    if not text:
        return ""
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip()
    return normalized[:max_chars]


def tokenize_query(text: str | None) -> list[str]:
    if not text:
        return []

    tokens = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_-]+", text.lower())
    filtered: list[str] = []

    for token in tokens:
        if len(token) < 3:
            continue
        if token in POLISH_STOPWORDS:
            continue
        filtered.append(token)

    return filtered


def get_match_text(match: dict[str, Any]) -> str:
    return (
        str(match.get("text") or "")
        or str(match.get("chunk_text") or "")
        or str(match.get("excerpt") or "")
    )


def lexical_overlap_score(query_tokens: list[str], text: str) -> int:
    if not query_tokens:
        return 0

    haystack = text.lower()
    score = 0
    for token in query_tokens:
        if token in haystack:
            score += 1
    return score


_JUNK_PATTERNS: list[re.Pattern[str]] = [
    # Teams meeting invite boilerplate
    re.compile(r"teams\.microsoft\.com/l/meetup-join", re.IGNORECASE),
    re.compile(r"Click here to join the meeting", re.IGNORECASE),
    re.compile(r"Meeting ID:\s*\d", re.IGNORECASE),
    # Chunks that are only numbers, dates, pipes, commas, whitespace (spreadsheet rows)
    re.compile(r"^[\d|,.\s/:;-]+$"),
]

MIN_CHUNK_LENGTH = 50


def _is_junk_chunk(text: str) -> bool:
    """Return True if *text* is low-quality boilerplate or noise."""
    if len(text.strip()) < MIN_CHUNK_LENGTH:
        return True
    for pattern in _JUNK_PATTERNS:
        if pattern.search(text):
            return True
    return False


def cleanup_matches(
    matches: list[dict[str, Any]],
    *,
    normalized_query: str,
    top_k: int,
    max_per_document: int = 2,
    min_score: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Lekki cleanup wyników retrieval:
    - junk chunk filter (short / boilerplate / numeric-only)
    - dedup po podobnym tekście
    - limit wyników z jednego dokumentu
    - opcjonalny score floor
    - lekki lexical sort boost
    """

    stats = {
        "input_count": len(matches),
        "junk_filtered_out": 0,
        "score_filtered_out": 0,
        "dedup_filtered_out": 0,
        "document_capped_out": 0,
        "output_count": 0,
    }

    if not matches:
        return [], stats


    # 0) junk chunk filter — remove short / boilerplate / numeric-only chunks
    non_junk: list[dict[str, Any]] = []
    for match in matches:
        text = get_match_text(match)
        if _is_junk_chunk(text):
            stats["junk_filtered_out"] += 1
            continue
        non_junk.append(match)

    # 1) score filter
    filtered: list[dict[str, Any]] = []
    for match in non_junk:
        score = match.get("score")
        if min_score is not None and score is not None:
            try:
                if float(score) < float(min_score):
                    stats["score_filtered_out"] += 1
                    continue
            except Exception:
                pass
        filtered.append(match)

    # 2) relevance reranking
    sorted_matches = rerank_matches_by_relevance(
        filtered,
        normalized_query=normalized_query,
    )

    # 3) dedup po podobnym początku tekstu
    deduped: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    for match in sorted_matches:
        signature = normalize_text_for_dedup(get_match_text(match))
        if signature and signature in seen_signatures:
            stats["dedup_filtered_out"] += 1
            continue
        if signature:
            seen_signatures.add(signature)
        deduped.append(match)

    # 4) limit chunków z jednego dokumentu
    per_document_counts: dict[Any, int] = defaultdict(int)
    capped: list[dict[str, Any]] = []

    for match in deduped:
        document_id = match.get("document_id")
        key = document_id if document_id is not None else f"title::{match.get('title')}"

        if per_document_counts[key] >= max_per_document:
            stats["document_capped_out"] += 1
            continue

        per_document_counts[key] += 1
        capped.append(match)

    final_matches = capped[:top_k]
    stats["output_count"] = len(final_matches)

    return final_matches, stats
