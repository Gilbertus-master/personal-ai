from __future__ import annotations

import re
from typing import Any


POLISH_STOPWORDS = {
    "i", "oraz", "a", "ale", "że", "to", "na", "w", "z", "do", "o", "od",
    "jak", "jakie", "jaka", "jaką", "co", "czy", "się", "mi", "mnie",
    "moje", "moją", "moich", "były", "było", "była", "dla", "po", "pod",
    "nad", "przy", "jest", "są", "być", "miałem", "mam", "masz", "mój",
    "twoje", "wszystkiego", "wiesz", "wszystko", "ten", "ta",
    "te", "tych", "jaki", "jakiego", "jakaś", "jakas",
    "bylo", "byla", "glowne", "główne",
}


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []

    tokens = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_-]+", text.lower())
    output: list[str] = []

    for token in tokens:
        if len(token) < 3:
            continue
        if token in POLISH_STOPWORDS:
            continue
        output.append(token)

    return output


def get_match_text(match: dict[str, Any]) -> str:
    return str(match.get("text") or match.get("chunk_text") or match.get("excerpt") or "")


def overlap_count(query_tokens: list[str], haystack: str) -> int:
    if not query_tokens or not haystack:
        return 0

    return len(set(query_tokens) & set(tokenize(haystack)))
