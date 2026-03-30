"""
Decision Outcome Detector — automatically detects outcomes for pending decisions.

1. detect_outcomes_for_pending_decisions(): query pending decisions, gather evidence, LLM suggest outcome
2. link_decisions_to_actions(decision_id): find action_items ±48h, keyword match
3. cascade_confidence_adjustment(area): adjust confidence based on bias per area

Cron: daily at 9:00 (after decision intelligence at 8:00)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

OUTCOME_DETECT_PROMPT = """You detect whether a business decision has had a visible outcome based on evidence.

Decision:
- Text: {decision_text}
- Area: {area}
- Expected outcome: {expected_outcome}
- Decided at: {decided_at}

Given the evidence below (events, communications, actions), determine:
1. Has this decision produced a visible outcome?
2. What is the outcome? (success / partial / negative / inconclusive)
3. What evidence supports this?
4. Suggested rating (1-5): 1=very bad, 3=neutral, 5=excellent

Return ONLY JSON:
{{"has_outcome": true/false, "outcome": "success"|"partial"|"negative"|"inconclusive", "evidence_summary": "...", "suggested_rating": 1-5, "confidence": 0.0-1.0}}"""


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def ensure_detector_schema() -> None:
    """Create tables for outcome suggestions and decision-action links."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS decision_outcome_suggestions (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                    suggested_outcome TEXT NOT NULL,
                    suggested_rating INTEGER CHECK (suggested_rating BETWEEN 1 AND 5),
                    evidence_summary TEXT,
                    confidence NUMERIC(3,2) DEFAULT 0.5,
                    accepted BOOLEAN,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(decision_id)
                );
                CREATE INDEX IF NOT EXISTS idx_decision_outcome_sugg_decision
                ON decision_outcome_suggestions(decision_id);

                CREATE TABLE IF NOT EXISTS decision_action_links (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                    action_item_id BIGINT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
                    link_type TEXT DEFAULT 'keyword',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(decision_id, action_item_id)
                );
                CREATE INDEX IF NOT EXISTS idx_decision_action_links_decision
                ON decision_action_links(decision_id);
                CREATE INDEX IF NOT EXISTS idx_decision_action_links_action
                ON decision_action_links(action_item_id);
            """)
        conn.commit()
    log.info("decision_outcome_detector_schema_ensured")


# ---------------------------------------------------------------------------
# 1. Detect outcomes for pending decisions
# ---------------------------------------------------------------------------

def detect_outcomes_for_pending_decisions(
    min_age_days: int = 7,
    max_age_days: int = 90,
    limit: int = 10,
) -> list[dict]:
    """Query decisions pending review, gather evidence, LLM suggest outcome."""
    ensure_detector_schema()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.decision_text, d.area, d.expected_outcome,
                       d.decided_at, d.confidence
                FROM decisions d
                WHERE d.review_status IN ('pending', 'reminded')
                  AND d.decided_at < NOW() - (%s * INTERVAL '1 day')
                  AND d.decided_at > NOW() - (%s * INTERVAL '1 day')
                  AND NOT EXISTS (
                      SELECT 1 FROM decision_outcome_suggestions dos
                      WHERE dos.decision_id = d.id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM decision_outcomes do
                      WHERE do.decision_id = d.id
                  )
                ORDER BY d.decided_at ASC
                LIMIT %s
            """, (min_age_days, max_age_days, limit))
            rows = cur.fetchall()

    if not rows:
        log.info("no_pending_decisions_for_detection",
                 min_age_days=min_age_days, max_age_days=max_age_days)
        return []

    suggestions: list[dict] = []

    for decision_id, text, area, expected, decided_at, confidence in rows:
        evidence = _gather_evidence(decision_id, text, decided_at)
        if not evidence:
            log.debug("no_evidence_for_decision", decision_id=decision_id)
            continue

        suggestion = _llm_detect_outcome(
            decision_text=text,
            area=area or "general",
            expected_outcome=expected or "",
            decided_at=decided_at.strftime('%Y-%m-%d %H:%M:%S') if decided_at else "unknown",
            evidence=evidence,
        )
        if suggestion is None:
            continue

        if not suggestion.get("has_outcome", False):
            continue

        # Save suggestion
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO decision_outcome_suggestions
                        (decision_id, suggested_outcome, suggested_rating,
                         evidence_summary, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (decision_id) DO UPDATE SET
                        suggested_outcome = EXCLUDED.suggested_outcome,
                        suggested_rating = EXCLUDED.suggested_rating,
                        evidence_summary = EXCLUDED.evidence_summary,
                        confidence = EXCLUDED.confidence,
                        created_at = NOW()
                    RETURNING id
                """, (
                    decision_id,
                    suggestion.get("outcome", "inconclusive"),
                    suggestion.get("suggested_rating"),
                    suggestion.get("evidence_summary", "")[:1000],
                    suggestion.get("confidence", 0.5),
                ))
                sugg_id = cur.fetchall()[0][0]
            conn.commit()

        record = {
            "suggestion_id": sugg_id,
            "decision_id": decision_id,
            "decision_text": text[:200] if text else "",
            "suggested_outcome": suggestion.get("outcome"),
            "suggested_rating": suggestion.get("suggested_rating"),
            "confidence": suggestion.get("confidence"),
        }
        suggestions.append(record)
        log.info("outcome_suggestion_created",
                 decision_id=decision_id, outcome=suggestion.get("outcome"))

    return suggestions


def _gather_evidence(decision_id: int, text: str, decided_at: datetime) -> str:
    """Gather events, chunks, action outcomes around a decision for evidence."""
    parts: list[str] = []
    keywords = [w.lower() for w in (text or "").split() if len(w) > 4][:10]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Related events after decision
            cur.execute("""
                SELECT e.event_type, e.summary, e.event_time
                FROM events e
                WHERE e.created_at > %s
                  AND e.created_at < %s + INTERVAL '60 days'
                ORDER BY e.created_at DESC
                LIMIT 50
            """, (decided_at, decided_at))
            events = cur.fetchall()

            # Filter events by keyword relevance
            relevant_events = []
            for etype, summary, etime in events:
                summary_lower = (summary or "").lower()
                if any(kw in summary_lower for kw in keywords):
                    relevant_events.append((etype, summary, etime))
                if len(relevant_events) >= 10:
                    break

            if relevant_events:
                parts.append("=== RELEVANT EVENTS ===")
                for etype, summary, etime in relevant_events:
                    parts.append(f"[{etype}] {etime}: {summary[:300]}")

            # Linked action items
            cur.execute("""
                SELECT ai.action_type, ai.description, ai.status,
                       ao.outcome, ao.evidence
                FROM action_items ai
                LEFT JOIN action_outcomes ao ON ao.action_item_id = ai.id
                WHERE ai.created_at > %s - INTERVAL '2 days'
                  AND ai.created_at < %s + INTERVAL '60 days'
                LIMIT 20
            """, (decided_at, decided_at))
            actions = cur.fetchall()

            relevant_actions = []
            for atype, desc, status, outcome, evidence in actions:
                desc_lower = (desc or "").lower()
                if any(kw in desc_lower for kw in keywords):
                    relevant_actions.append((atype, desc, status, outcome, evidence))
                if len(relevant_actions) >= 5:
                    break

            if relevant_actions:
                parts.append("\n=== RELATED ACTIONS ===")
                for atype, desc, status, outcome, evidence in relevant_actions:
                    parts.append(f"[{atype}] {desc[:200]} | status={status} outcome={outcome}")

    return "\n".join(parts) if parts else ""


def _llm_detect_outcome(
    decision_text: str,
    area: str,
    expected_outcome: str,
    decided_at: str,
    evidence: str,
) -> dict | None:
    """Use Haiku to analyze evidence and suggest outcome."""
    try:
        prompt = OUTCOME_DETECT_PROMPT.format(
            decision_text=decision_text[:500],
            area=area,
            expected_outcome=expected_outcome[:300],
            decided_at=decided_at,
        )

        evidence_truncated = evidence[:8000] if len(evidence) > 8000 else evidence

        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=400,
            temperature=0.1,
            system=[{"type": "text", "text": prompt,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": evidence_truncated}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST,
                               "analysis.decision_outcome_detector", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)

        # Validate
        valid_outcomes = {"success", "partial", "negative", "inconclusive"}
        if result.get("outcome") not in valid_outcomes:
            result["outcome"] = "inconclusive"
        if result.get("suggested_rating") is not None:
            result["suggested_rating"] = max(1, min(5, int(result["suggested_rating"])))

        return result
    except Exception as e:
        log.error("outcome_detection_llm_failed", error=str(e))
        return None


# ---------------------------------------------------------------------------
# 2. Link decisions to action items
# ---------------------------------------------------------------------------

def link_decisions_to_actions(decision_id: int) -> list[dict]:
    """Find action_items ±48h of a decision, keyword match, create links."""
    ensure_detector_schema()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, decision_text, decided_at FROM decisions WHERE id = %s
            """, (decision_id,))
            row = cur.fetchone()
            if not row:
                return []
            _, text, decided_at = row

    if not decided_at or not text:
        return []

    keywords = [w.lower() for w in text.split() if len(w) > 4][:15]
    if not keywords:
        return []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ai.id, ai.action_type, ai.description, ai.created_at
                FROM action_items ai
                WHERE ai.created_at BETWEEN %s - INTERVAL '48 hours'
                                        AND %s + INTERVAL '48 hours'
                ORDER BY ai.created_at
            """, (decided_at, decided_at))
            candidates = cur.fetchall()

    links: list[dict] = []
    for action_id, atype, desc, created in candidates:
        desc_lower = (desc or "").lower()
        match_count = sum(1 for kw in keywords if kw in desc_lower)
        if match_count < 2:
            continue

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO decision_action_links (decision_id, action_item_id, link_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (decision_id, action_item_id) DO NOTHING
                    RETURNING id
                """, (decision_id, action_id, "keyword"))
                link_row = cur.fetchone()
            conn.commit()

        if link_row:
            links.append({
                "link_id": link_row[0],
                "decision_id": decision_id,
                "action_item_id": action_id,
                "action_type": atype,
                "description": desc[:200] if desc else "",
            })
            log.info("decision_action_linked",
                     decision_id=decision_id, action_id=action_id)

    return links


# ---------------------------------------------------------------------------
# 3. Cascade confidence adjustment
# ---------------------------------------------------------------------------

def cascade_confidence_adjustment(area: str) -> dict:
    """Analyze bias for a given area and return adjustment recommendation.

    Returns: {area, bias, adjustment, sample_size}
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.confidence, do.rating
                FROM decisions d
                JOIN decision_outcomes do ON do.decision_id = d.id
                WHERE d.area = %s
                  AND d.decided_at > NOW() - INTERVAL '6 months'
            """, (area,))
            rows = cur.fetchall()

    if len(rows) < 3:
        return {
            "area": area,
            "bias": "insufficient_data",
            "adjustment": 0.0,
            "sample_size": len(rows),
        }

    confidences = [float(r[0]) if r[0] else 0.5 for r in rows]
    ratings = [int(r[1]) for r in rows if r[1] is not None]

    if not ratings:
        return {
            "area": area,
            "bias": "insufficient_data",
            "adjustment": 0.0,
            "sample_size": len(rows),
        }

    avg_confidence = sum(confidences) / len(confidences)
    avg_rating = sum(ratings) / len(ratings)

    # Perfect calibration: confidence * 5 == rating
    expected_rating = avg_confidence * 5.0
    deviation = avg_rating - expected_rating

    if abs(deviation) < 0.3:
        bias = "well_calibrated"
        adjustment = 0.0
    elif deviation > 0:
        bias = "under_confident"
        adjustment = round(deviation / 5.0, 3)
    else:
        bias = "overconfident"
        adjustment = round(deviation / 5.0, 3)

    return {
        "area": area,
        "bias": bias,
        "adjustment": adjustment,
        "sample_size": len(rows),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_outcome_detection() -> dict:
    """Main pipeline for outcome detection."""
    result: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Detect outcomes
    try:
        suggestions = detect_outcomes_for_pending_decisions()
        result["suggestions"] = len(suggestions)
        result["suggestion_details"] = suggestions
    except Exception as e:
        log.error("outcome_detection_failed", error=str(e))
        result["suggestions"] = 0
        result["detection_error"] = str(e)

    # 2. Link recent decisions to actions
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM decisions
                    WHERE decided_at > NOW() - INTERVAL '7 days'
                      AND NOT EXISTS (
                          SELECT 1 FROM decision_action_links dal
                          WHERE dal.decision_id = decisions.id
                      )
                    LIMIT 20
                """)
                recent_ids = [r[0] for r in cur.fetchall()]

        total_links = 0
        for did in recent_ids:
            links = link_decisions_to_actions(did)
            total_links += len(links)
        result["action_links_created"] = total_links
    except Exception as e:
        log.error("action_linking_failed", error=str(e))
        result["action_links_created"] = 0
        result["linking_error"] = str(e)

    # 3. Cascade confidence check per area
    try:
        areas = ["business", "trading", "relationships", "wellbeing", "general"]
        adjustments = {}
        for a in areas:
            adj = cascade_confidence_adjustment(a)
            if adj["sample_size"] >= 3:
                adjustments[a] = adj
        result["confidence_adjustments"] = adjustments
    except Exception as e:
        log.error("cascade_adjustment_failed", error=str(e))
        result["confidence_adjustments"] = {}

    log.info("outcome_detection_complete",
             suggestions=result.get("suggestions", 0),
             links=result.get("action_links_created", 0))

    return result


if __name__ == "__main__":
    res = run_outcome_detection()
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
