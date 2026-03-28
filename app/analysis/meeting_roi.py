"""
Meeting ROI Tracker — measures which meetings are productive.

After meeting minutes are generated, scores the meeting:
- decisions_count: how many decisions were made
- action_items_count: how many action items created
- commitment_count: how many commitments extracted
- duration_actual vs planned
- roi_score: weighted score 1-5

Aggregates by meeting type/participant for pattern analysis.

Cron: runs after meeting minutes generation (same cron, or separate daily)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json

from app.db.postgres import get_pg_connection

from dotenv import load_dotenv
load_dotenv()

# ROI scoring weights
WEIGHT_DECISIONS = 3
WEIGHT_ACTION_ITEMS = 2
WEIGHT_COMMITMENTS = 1
MAX_ITEMS_FOR_SCALE = 5  # normalisation: 5 decisions = max score contribution


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _ensure_tables() -> None:
    """Add ROI columns to meeting_minutes if they don't exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE meeting_minutes
                    ADD COLUMN IF NOT EXISTS decisions_count INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS action_items_count INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS commitments_count INT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS duration_planned_min INT,
                    ADD COLUMN IF NOT EXISTS duration_actual_min INT,
                    ADD COLUMN IF NOT EXISTS meeting_roi_score NUMERIC(3,1),
                    ADD COLUMN IF NOT EXISTS meeting_type TEXT
            """)
            conn.commit()
    log.info("meeting_roi_tables_ensured")


# ---------------------------------------------------------------------------
# 1. Score a single meeting
# ---------------------------------------------------------------------------

def score_meeting(minutes_id: int) -> dict:
    """Calculate ROI score for a meeting_minutes record.

    Score formula: (decisions*3 + action_items*2 + commitments*1) / max_possible * 5
    Capped at 5.0.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, document_id, decisions, action_items, summary, title
                FROM meeting_minutes
                WHERE id = %s
            """, (minutes_id,))
            rows = cur.fetchall()
            row = rows[0] if rows else None

            if not row:
                log.warning("meeting_not_found", minutes_id=minutes_id)
                return {"error": f"Meeting minutes {minutes_id} not found"}

            mm_id, document_id, decisions_json, action_items_json, summary, title = row

            # Count decisions
            decisions_count = 0
            if decisions_json:
                try:
                    decisions_data = decisions_json if isinstance(decisions_json, list) else json.loads(decisions_json)
                    decisions_count = len(decisions_data)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Count action items
            action_items_count = 0
            if action_items_json:
                try:
                    ai_data = action_items_json if isinstance(action_items_json, list) else json.loads(action_items_json)
                    action_items_count = len(ai_data)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Count commitments linked to this document
            commitments_count = 0
            if document_id:
                cur.execute("""
                    SELECT COUNT(*) FROM events
                    WHERE chunk_id IN (
                        SELECT id FROM chunks WHERE document_id = %s
                    )
                    AND event_type = 'commitment'
                """, (document_id,))
                res_rows = cur.fetchall()
                commitments_count = res_rows[0][0] if res_rows else 0

            # Calculate ROI score
            raw_score = (
                decisions_count * WEIGHT_DECISIONS
                + action_items_count * WEIGHT_ACTION_ITEMS
                + commitments_count * WEIGHT_COMMITMENTS
            )
            max_possible = MAX_ITEMS_FOR_SCALE * (WEIGHT_DECISIONS + WEIGHT_ACTION_ITEMS + WEIGHT_COMMITMENTS)
            roi_score = min(5.0, (raw_score / max_possible) * 5) if max_possible > 0 else 0.0
            roi_score = round(roi_score, 1)

            # Infer meeting type from title
            meeting_type = _infer_meeting_type(title or "")

            # Update the record
            cur.execute("""
                UPDATE meeting_minutes
                SET decisions_count = %s,
                    action_items_count = %s,
                    commitments_count = %s,
                    meeting_roi_score = %s,
                    meeting_type = %s
                WHERE id = %s
            """, (decisions_count, action_items_count, commitments_count,
                  roi_score, meeting_type, mm_id))
            conn.commit()

    result = {
        "minutes_id": mm_id,
        "title": title,
        "decisions_count": decisions_count,
        "action_items_count": action_items_count,
        "commitments_count": commitments_count,
        "meeting_roi_score": roi_score,
        "meeting_type": meeting_type,
    }

    log.info("meeting_scored", **result)
    return result


def _infer_meeting_type(title: str) -> str:
    """Infer meeting type from title keywords."""
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["1:1", "one on one", "1-on-1"]):
        return "1:1"
    if any(kw in title_lower for kw in ["status", "standup", "stand-up", "daily"]):
        return "status"
    if any(kw in title_lower for kw in ["review", "przegląd"]):
        return "review"
    if any(kw in title_lower for kw in ["planning", "planowanie", "sprint"]):
        return "planning"
    if any(kw in title_lower for kw in ["board", "zarząd"]):
        return "board"
    if any(kw in title_lower for kw in ["negocjacj", "negotiat"]):
        return "negotiation"
    if any(kw in title_lower for kw in ["kick-off", "kickoff"]):
        return "kickoff"
    return "general"


# ---------------------------------------------------------------------------
# 2. Score unscored meetings
# ---------------------------------------------------------------------------

def score_unscored_meetings() -> list[dict]:
    """Find meeting_minutes without roi_score and score each."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM meeting_minutes
                WHERE meeting_roi_score IS NULL
                ORDER BY id
            """)
            rows = cur.fetchall()

    if not rows:
        log.info("no_unscored_meetings")
        return []

    results = []
    for (mm_id,) in rows:
        try:
            result = score_meeting(mm_id)
            results.append(result)
        except Exception as exc:
            log.error("score_meeting_failed", minutes_id=mm_id, error=str(exc))
            results.append({"minutes_id": mm_id, "error": str(exc)})

    log.info("unscored_meetings_processed", count=len(results))
    return results


# ---------------------------------------------------------------------------
# 3. Meeting type analysis
# ---------------------------------------------------------------------------

def get_meeting_type_analysis() -> dict:
    """Analyze meeting patterns by participant and type.

    Returns aggregate stats and identifies low-ROI / high-ROI patterns.
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # By meeting type
            cur.execute("""
                SELECT meeting_type,
                       COUNT(*) as meetings,
                       ROUND(AVG(meeting_roi_score), 1) as avg_roi,
                       ROUND(AVG(decisions_count), 1) as avg_decisions,
                       ROUND(AVG(action_items_count), 1) as avg_action_items
                FROM meeting_minutes
                WHERE meeting_roi_score IS NOT NULL
                GROUP BY meeting_type
                ORDER BY avg_roi DESC
            """)
            type_rows = cur.fetchall()

            # By participant (from meeting_minutes.participants JSON)
            cur.execute("""
                SELECT p.value as participant,
                       COUNT(*) as meetings,
                       ROUND(AVG(mm.meeting_roi_score), 1) as avg_roi,
                       ROUND(AVG(mm.decisions_count), 1) as avg_decisions
                FROM meeting_minutes mm,
                     jsonb_array_elements_text(mm.participants) p
                WHERE mm.meeting_roi_score IS NOT NULL
                GROUP BY p.value
                HAVING COUNT(*) >= 2
                ORDER BY avg_roi DESC
            """)
            participant_rows = cur.fetchall()

    # Format results
    by_type: dict[str, dict] = {}
    for row in type_rows:
        by_type[row[0] or "unknown"] = {
            "meetings": row[1],
            "avg_roi": float(row[2]) if row[2] else 0,
            "avg_decisions": float(row[3]) if row[3] else 0,
            "avg_action_items": float(row[4]) if row[4] else 0,
        }

    by_participant: dict[str, dict] = {}
    for row in participant_rows:
        by_participant[row[0]] = {
            "meetings": row[1],
            "avg_roi": float(row[2]) if row[2] else 0,
            "avg_decisions": float(row[3]) if row[3] else 0,
        }

    # Identify patterns
    low_roi_patterns = []
    high_roi_patterns = []

    for mtype, stats in by_type.items():
        if stats["avg_roi"] < 2.0 and stats["meetings"] >= 3:
            recommendation = "Zastąp weekly email digest" if "status" in mtype else "Rozważ async format"
            low_roi_patterns.append({
                "pattern": mtype,
                "avg_roi": stats["avg_roi"],
                "meetings": stats["meetings"],
                "recommendation": recommendation,
            })
        elif stats["avg_roi"] >= 3.5 and stats["meetings"] >= 2:
            high_roi_patterns.append({
                "pattern": mtype,
                "avg_roi": stats["avg_roi"],
                "meetings": stats["meetings"],
            })

    result = {
        "by_type": by_type,
        "by_participant": by_participant,
        "low_roi_patterns": low_roi_patterns,
        "high_roi_patterns": high_roi_patterns,
        "total_scored_meetings": sum(s["meetings"] for s in by_type.values()),
    }

    log.info("meeting_type_analysis_completed",
             types=len(by_type), participants=len(by_participant))
    return result


# ---------------------------------------------------------------------------
# 4. Main pipeline
# ---------------------------------------------------------------------------

def run_meeting_roi_analysis() -> dict:
    """Main pipeline: score unscored meetings, analyze patterns, return summary."""
    log.info("meeting_roi_analysis_started")

    scored = score_unscored_meetings()
    analysis = get_meeting_type_analysis()

    result = {
        "newly_scored": len(scored),
        "scored_details": scored,
        "analysis": analysis,
    }

    log.info("meeting_roi_analysis_completed",
             newly_scored=len(scored),
             total=analysis.get("total_scored_meetings", 0))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_meeting_roi_analysis()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
