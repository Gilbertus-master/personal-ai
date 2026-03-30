

from __future__ import annotations

import re
from typing import Any


POLISH_STOPWORDS = {
    "i", "oraz", "a", "ale", "że", "to", "na", "w", "z", "do", "o", "od",
    "jak", "jakie", "jaka", "jaką", "co", "czy", "się", "mi", "mnie",
    "moje", "moją", "moich", "były", "było", "była", "dla", "po", "pod",
    "nad", "przy", "jest", "są", "być", "miałem", "mam", "masz", "mój",
    "twoje", "wszystkiego", "wiesz", "wszystko", "oraz", "ten", "ta",
    "te", "tych", "to", "jaki", "jaka", "jakiego", "jakaś", "jakas",
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


def get_match_title(match: dict[str, Any]) -> str:
    return str(match.get("title") or "")


def get_source_type(match: dict[str, Any]) -> str:
    return str(match.get("source_type") or "")


def overlap_count(query_tokens: list[str], haystack: str) -> int:
    if not query_tokens or not haystack:
        return 0

    haystack_tokens = set(tokenize(haystack))
    return len(set(query_tokens) & haystack_tokens)


def domain_score_delta(query_tokens: list[str], match: dict[str, Any]) -> float:
    """
    Bardzo lekki bonus/punishment zależny od domeny pytania.
    Zwraca wartość dodatnią (bonus) lub ujemną (kara).

    Wagi dobrane empirycznie na podstawie jakości rankingu:
      +1.2  — dopasowanie tytułu do domeny relacji/partnera
      +0.4  — bonus źródłowy WhatsApp dla zapytań o relacje (rozmowy prywatne)
      +1.5  — dopasowanie tytułu do domeny Gilbertus/projekt
      -0.5  — kara dla chunków BEZ pasującego tytułu w domenie Gilbertus;
              INTENTIONAL: zapytania o architekturę/projekt preferują dokumenty
              z jawnym tytułem projektowym. Kara może pominąć legitymne wyniki
              z nieopatrzonych tytułem źródeł (np. surowe e-maile) — jest to
              akceptowalny kompromis dla tej domeny.
      +1.2  — dopasowanie tytułu do domeny trading/energia

    TODO: rozważyć eksternalizację reguł do tabeli DB `domain_boost_rules`
    lub pliku TOML, aby umożliwić zmianę wag bez redeploy.
    """
    title = get_match_title(match).lower()
    source_type = get_source_type(match).lower()
    query_blob = " ".join(query_tokens)

    delta = 0.0

    # Relacje / Zosia / partnerka
    if any(token in query_blob for token in ["zosia", "zosią", "partnerka", "relacji", "związek", "zwiazek"]):
        if "zosia" in title or "zwią" in title or "zwia" in title or "partner" in title:
            delta += 1.2
        if source_type == "whatsapp":
            delta += 0.4

    # Gilbertus / projekt / architektura
    if any(token in query_blob for token in ["gilbertus", "architektura", "ingestion", "projekt"]):
        if any(word in title for word in ["gilbertus", "projekt", "faza", "plan", "setup", "architektur"]):
            delta += 1.5
        else:
            delta -= 0.5

    # trading / rynek / energia
    if any(token in query_blob for token in ["trading", "rynek", "energia", "energii", "trader"]):
        if any(word in title for word in ["trading", "energia", "market", "rynek", "trader"]):
            delta += 1.2

    return delta


def compute_relevance_score(match: dict[str, Any], normalized_query: str) -> float:
    query_tokens = tokenize(normalized_query)
    text = get_match_text(match)
    title = get_match_title(match)

    text_overlap = overlap_count(query_tokens, text)
    title_overlap = overlap_count(query_tokens, title)

    try:
        semantic_score = float(match.get("score", 0.0))
    except Exception:
        semantic_score = 0.0

    # Wagi:
    # semantyka nadal ważna, ale title i lexical mają realny wpływ
    score = (
        semantic_score * 10.0
        + text_overlap * 0.8
        + title_overlap * 2.0
        + domain_score_delta(query_tokens, match)
    )

    return score


def rerank_matches_by_relevance(
    matches: list[dict[str, Any]],
    *,
    normalized_query: str,
) -> list[dict[str, Any]]:
    rescored: list[tuple[float, dict[str, Any]]] = []

    for match in matches:
        relevance_score = compute_relevance_score(match, normalized_query)
        enriched = dict(match)
        enriched["_relevance_score"] = relevance_score
        rescored.append((relevance_score, enriched))

    rescored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in rescored]
