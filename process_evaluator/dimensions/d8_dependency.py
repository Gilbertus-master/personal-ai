"""D8: Dependency — THE MOST IMPORTANT DIMENSION.

Measures human dependency risk: knowledge concentration, bus factor,
flight risk weighted by ownership, and upstream process risk.
"""

from __future__ import annotations

from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d8_dependency")


def compute_d8(
    process_id: UUID,
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute dependency dimension.

    4 sub-scores:
    1. knowledge_concentration: MAX(ownership_pct) — higher = worse
    2. bus_factor: min persons needed for 80% coverage — lower = worse
    3. flight_risk_weighted: weighted avg of flight_risk by ownership
    4. upstream_risk: MAX(failure_risk) from parent processes

    Composite: 0.40*(1-kc) + 0.30*normalize(bf,1,5) + 0.20*(1-frw) + 0.10*(1-ur)
    """
    # ── 1. Knowledge concentration + bus factor from participations ──
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT pp.person_id, pp.ownership_pct,
                      ecs.flight_risk_score
               FROM process_participations pp
               LEFT JOIN LATERAL (
                   SELECT flight_risk_score
                   FROM employee_competency_scores
                   WHERE person_id = pp.person_id
                   ORDER BY scored_at DESC
                   LIMIT 1
               ) ecs ON TRUE
               WHERE pp.process_id = %s
                 AND pp.active_since >= CURRENT_DATE - INTERVAL '90 days'
               ORDER BY pp.ownership_pct DESC""",
            (str(process_id),),
        )
        participants = cur.fetchall()

    # If no participation data, try without date filter
    if not participants:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT pp.person_id, pp.ownership_pct,
                          ecs.flight_risk_score
                   FROM process_participations pp
                   LEFT JOIN LATERAL (
                       SELECT flight_risk_score
                       FROM employee_competency_scores
                       WHERE person_id = pp.person_id
                       ORDER BY scored_at DESC
                       LIMIT 1
                   ) ecs ON TRUE
                   WHERE pp.process_id = %s
                   ORDER BY pp.ownership_pct DESC""",
                (str(process_id),),
            )
            participants = cur.fetchall()

    if not participants:
        return DimensionScore(
            name="dependency",
            score=None,
            confidence=0.1,
            evidence={"reason": "no participation data found"},
        )

    # Knowledge concentration = MAX ownership_pct
    ownership_pcts = [p["ownership_pct"] or 0.0 for p in participants]
    knowledge_concentration = max(ownership_pcts) if ownership_pcts else 0.0

    # Bus factor = how many persons needed for 80% cumulative ownership
    sorted_pcts = sorted(ownership_pcts, reverse=True)
    cumsum = 0.0
    bus_factor = 0
    for pct in sorted_pcts:
        cumsum += pct
        bus_factor += 1
        if cumsum >= 0.8:
            break
    if bus_factor == 0:
        bus_factor = len(sorted_pcts)  # all needed

    # ── 2. Flight risk weighted ─────────────────────────────────────
    total_ownership = sum(ownership_pcts) or 1.0
    weighted_risk_sum = 0.0
    risk_count = 0
    for p in participants:
        fr = p.get("flight_risk_score")
        own = p.get("ownership_pct") or 0.0
        if fr is not None:
            weighted_risk_sum += fr * own
            risk_count += 1

    flight_risk_weighted = (
        weighted_risk_sum / total_ownership
        if total_ownership > 0 and risk_count > 0
        else 0.0
    )

    # ── 3. Critical person IDs ──────────────────────────────────────
    critical_person_ids: list[UUID] = []
    for p in participants:
        own = p.get("ownership_pct") or 0.0
        fr = p.get("flight_risk_score") or 0.0
        if own > 0.4 and fr > 0.6:
            critical_person_ids.append(p["person_id"])

    # ── 4. Upstream risk ────────────────────────────────────────────
    upstream_risk = 0.0
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT pcs.failure_risk_score
               FROM processes p
               JOIN LATERAL (
                   SELECT failure_risk_score
                   FROM process_competency_scores
                   WHERE process_id = p.parent_process_id
                   ORDER BY computed_at DESC
                   LIMIT 1
               ) pcs ON TRUE
               WHERE p.process_id = %s
                 AND p.parent_process_id IS NOT NULL""",
            (str(process_id),),
        )
        upstream_row = cur.fetchone()

    if upstream_row and upstream_row.get("failure_risk_score") is not None:
        upstream_risk = upstream_row["failure_risk_score"]

    # ── Composite score ─────────────────────────────────────────────
    # Normalize bus_factor to [0,1]: bf=1 -> 0.0, bf=5+ -> 1.0
    bf_normalized = min(1.0, max(0.0, (bus_factor - 1) / 4.0))

    raw = (
        0.40 * (1.0 - knowledge_concentration)
        + 0.30 * bf_normalized
        + 0.20 * (1.0 - flight_risk_weighted)
        + 0.10 * (1.0 - upstream_risk)
    )
    final_score = round(1.0 + max(0.0, min(1.0, raw)) * 4.0, 2)

    # Confidence
    if len(participants) >= 3 and risk_count >= 2:
        confidence = 0.9
    elif len(participants) >= 2:
        confidence = 0.7
    elif len(participants) >= 1:
        confidence = 0.5
    else:
        confidence = 0.2

    evidence = {
        "participants_count": len(participants),
        "knowledge_concentration": round(knowledge_concentration, 3),
        "bus_factor": bus_factor,
        "flight_risk_weighted": round(flight_risk_weighted, 3),
        "upstream_risk": round(upstream_risk, 3),
        "critical_person_count": len(critical_person_ids),
        "critical_person_ids": [str(pid) for pid in critical_person_ids],
    }

    log.info(
        "d8_computed",
        process_id=str(process_id),
        score=final_score,
        bus_factor=bus_factor,
        knowledge_concentration=round(knowledge_concentration, 3),
        flight_risk_weighted=round(flight_risk_weighted, 3),
        critical_persons=len(critical_person_ids),
    )

    return DimensionScore(
        name="dependency",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={
            "knowledge_concentration": round(knowledge_concentration, 3),
            "bus_factor_normalized": round(bf_normalized, 3),
            "flight_risk_weighted": round(flight_risk_weighted, 3),
            "upstream_risk": round(upstream_risk, 3),
        },
    )
