"""Probabilistic identity resolution — fuzzy name matching + context boost."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from ..models import PersonCandidate

try:
    from jellyfish import jaro_winkler_similarity
except ImportError:
    # Fallback: simple ratio-based similarity
    def jaro_winkler_similarity(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        common = sum(1 for ca, cb in zip(a, b) if ca == cb)
        return common / max(len(a), len(b))


def resolve_probabilistic(
    candidate: PersonCandidate,
    conn,
    settings: dict,
) -> Optional[tuple[UUID, float]]:
    """Fuzzy match by name + context. Returns (person_id, confidence) or None."""
    if not candidate.full_name:
        return None

    threshold = settings.get("fuzzy_name_threshold", 0.85)
    candidate_name = candidate.full_name.strip().lower()

    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.person_id, p.display_name,
                      pp.company, pp.job_title
               FROM persons p
               LEFT JOIN person_professional pp ON pp.person_id = p.person_id
               WHERE p.gdpr_delete_requested_at IS NULL
               LIMIT 10000""",
        )
        rows = cur.fetchall()

    best_id: Optional[UUID] = None
    best_score = 0.0

    for person_id, display_name, company, job_title in rows:
        if not display_name:
            continue

        name_score = jaro_winkler_similarity(
            candidate_name, display_name.strip().lower()
        )

        if name_score < threshold * 0.8:
            continue

        total_score = name_score

        # Boost if company matches
        if candidate.company and company:
            if (
                candidate.company.lower() in company.lower()
                or company.lower() in candidate.company.lower()
            ):
                total_score = min(total_score + 0.05, 1.0)

        if total_score > best_score:
            best_score = total_score
            best_id = person_id

    if best_id and best_score >= threshold:
        return (best_id, best_score)

    return None
