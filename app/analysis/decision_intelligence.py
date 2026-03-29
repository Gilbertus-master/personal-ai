"""
Decision Intelligence — learns from Sebastian's decision patterns.

1. Auto-capture decisions from events (type='decision', 'approval')
2. Remind about pending outcome reviews (7/30/90 days)
3. Confidence calibration: compare predicted confidence vs actual outcome
4. Pattern analysis: which decision areas succeed/fail
5. Bias detection: systematic over/under-confidence
6. Weekly decision digest

Cron: daily at 8:00 (after morning brief)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

OPENCLAW_BIN = "openclaw"
WA_TARGET = "+48505441635"

DECISION_EXTRACT_PROMPT = """You extract structured decision metadata from event summaries.

Given an event summary about a decision or approval, extract:
- area: one of "business", "trading", "relationships", "wellbeing", "general"
- context: 1-2 sentence context of the decision
- expected_outcome: what was the expected result

Respond ONLY with a JSON object:
{"area": "...", "context": "...", "expected_outcome": "..."}"""

PATTERN_ANALYSIS_PROMPT = """You analyze decision patterns for a business leader.

Given structured data about past decisions with their outcomes, identify:
1. Success rate patterns by area, time, entities involved
2. Systematic biases (over/under-confidence)
3. Actionable recommendations

Be concise and specific. Focus on patterns with statistical support (at least 3+ data points).
Write in Polish. Return a JSON array of pattern strings.

Respond ONLY with JSON array: ["pattern 1", "pattern 2", ...]"""


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def ensure_schema() -> None:
    """Add columns to decisions table if missing."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE decisions
                ADD COLUMN IF NOT EXISTS source_event_id BIGINT REFERENCES events(id)
            """)
            cur.execute("""
                ALTER TABLE decisions
                ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending'
            """)
            cur.execute("""
                ALTER TABLE decisions
                ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMPTZ
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_review
                ON decisions(review_status, next_review_at)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_source_event
                ON decisions(source_event_id)
            """)
        conn.commit()
    log.info("decision_intelligence_schema_ensured")


# ---------------------------------------------------------------------------
# 1. Auto-capture decisions from events
# ---------------------------------------------------------------------------

def auto_capture_decisions(hours: int = 24) -> list[dict]:
    """Scan recent events of type 'decision'/'approval' not yet in decisions table."""
    ensure_schema()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.summary, e.event_time, e.confidence,
                       COALESCE(string_agg(DISTINCT en.canonical_name, ', '), '') as entities
                FROM events e
                LEFT JOIN event_entities ee ON ee.event_id = e.id
                LEFT JOIN entities en ON en.id = ee.entity_id
                WHERE e.event_type IN ('decision', 'approval')
                  AND e.created_at > NOW() - INTERVAL '%s hours'
                  AND NOT EXISTS (
                      SELECT 1 FROM decisions d
                      WHERE d.source_event_id = e.id
                  )
                GROUP BY e.id, e.summary, e.event_time, e.confidence
                ORDER BY e.event_time DESC
            """, (hours,))
            rows = cur.fetchall()

    if not rows:
        log.info("no_new_decision_events", hours=hours)
        return []

    captured: list[dict] = []

    for event_id, summary, event_time, confidence, entities in rows:
        # Use Haiku to extract structured info
        meta = _extract_decision_metadata(summary, entities)
        if meta is None:
            continue

        confidence_val = float(confidence) if confidence else 0.5
        decided_at = event_time or datetime.now(timezone.utc)
        next_review = decided_at + timedelta(days=7)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO decisions
                        (decision_text, context, expected_outcome, area, confidence,
                         decided_at, source_event_id, review_status, next_review_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                    RETURNING id
                """, (
                    summary[:500],
                    meta.get("context", "")[:500],
                    meta.get("expected_outcome", "")[:500],
                    meta.get("area", "general"),
                    confidence_val,
                    decided_at,
                    event_id,
                    next_review,
                ))
                decision_id = cur.fetchone()[0]
            conn.commit()

        record = {
            "id": decision_id,
            "decision_text": summary[:200],
            "area": meta.get("area", "general"),
            "confidence": confidence_val,
            "source_event_id": event_id,
        }
        captured.append(record)
        log.info("decision_captured", decision_id=decision_id, event_id=event_id,
                 area=meta.get("area"))

    return captured


def _extract_decision_metadata(summary: str, entities: str) -> dict | None:
    """Use Haiku to extract area/context/expected_outcome from event summary."""
    try:
        user_text = f"Event summary: {summary}\nEntities involved: {entities}"
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=300,
            temperature=0.0,
            system=[{"type": "text", "text": DECISION_EXTRACT_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_text}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "analysis.decision_intelligence", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        meta = json.loads(text)

        # Validate area
        valid_areas = {"business", "trading", "relationships", "wellbeing", "general"}
        if meta.get("area") not in valid_areas:
            meta["area"] = "general"

        return meta
    except Exception as e:
        log.error("decision_metadata_extraction_failed", error=str(e))
        return None


# ---------------------------------------------------------------------------
# 2. Review reminders
# ---------------------------------------------------------------------------

def send_review_reminders() -> list[dict]:
    """Find decisions where next_review_at < NOW() and review_status = 'pending'.
    Send WhatsApp reminders and advance review schedule."""
    ensure_schema()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, decision_text, area, decided_at, confidence, expected_outcome
                FROM decisions
                WHERE review_status IN ('pending', 'reminded')
                  AND next_review_at IS NOT NULL
                  AND next_review_at < NOW()
                ORDER BY next_review_at ASC
                LIMIT 10
            """)
            rows = cur.fetchall()

    if not rows:
        log.info("no_pending_review_reminders")
        return []

    reminders: list[dict] = []

    for did, text, area, decided_at, confidence, expected_outcome in rows:
        days_ago = (datetime.now(timezone.utc) - decided_at).days if decided_at else 0
        conf_str = f"{float(confidence):.0%}" if confidence else "?"
        expected = expected_outcome[:150] if expected_outcome else "brak"

        message = (
            f"\U0001f4cb *Decyzja #{did} wymaga oceny*\n"
            f"\"{text[:200]}\"\n"
            f"Podjeta: {decided_at.strftime('%Y-%m-%d') if decided_at else '?'} "
            f"({days_ago}d temu) | Obszar: {area} | Confidence: {conf_str}\n"
            f"Oczekiwany wynik: \"{expected}\"\n\n"
            f"Ocen: outcome #{did}: [opis wyniku] rating: [1-5]\n"
            f"Lub: skip #{did}"
        )

        sent = _send_whatsapp(message)

        # Advance to next review window
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE decisions
                    SET review_status = 'reminded',
                        next_review_at = next_review_at + INTERVAL '7 days'
                    WHERE id = %s
                """, (did,))
            conn.commit()

        reminders.append({
            "decision_id": did,
            "days_ago": days_ago,
            "area": area,
            "sent": sent,
        })
        log.info("review_reminder_sent", decision_id=did, days_ago=days_ago)

    return reminders


# ---------------------------------------------------------------------------
# 3. Confidence calibration
# ---------------------------------------------------------------------------

def analyze_confidence_calibration(months: int = 6) -> dict:
    """Compare confidence at decision time vs actual rating."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.area, d.confidence, do.rating
                FROM decisions d
                JOIN decision_outcomes do ON do.decision_id = d.id
                WHERE d.decided_at > NOW() - make_interval(months => %s)
            """, (months,))
            rows = cur.fetchall()

    if not rows:
        return {
            "total_decisions_with_outcome": 0,
            "calibration_score": None,
            "by_area": {},
            "bias": "insufficient_data",
            "recommendation": "Zbyt malo danych do analizy. Potrzeba min. 5 decyzji z wynikami.",
        }

    # Group by area
    by_area: dict[str, list[tuple[float, int]]] = {}
    all_pairs: list[tuple[float, int]] = []
    for _did, area, confidence, rating in rows:
        conf = float(confidence) if confidence else 0.5
        pair = (conf, int(rating))
        all_pairs.append(pair)
        by_area.setdefault(area, []).append(pair)

    # Calibration: perfect calibration means confidence * 5 == avg rating
    def _calibration(pairs: list[tuple[float, int]]) -> dict:
        avg_conf = sum(c for c, _ in pairs) / len(pairs)
        avg_rating = sum(r for _, r in pairs) / len(pairs)
        expected_rating = avg_conf * 5.0
        deviation = avg_rating - expected_rating
        if abs(deviation) < 0.3:
            label = "well_calibrated"
        elif deviation > 0:
            label = "under_confident"
        else:
            label = "overconfident" if abs(deviation) > 0.8 else "slightly_overconfident"
        return {
            "count": len(pairs),
            "avg_confidence": round(avg_conf, 2),
            "avg_rating": round(avg_rating, 1),
            "expected_rating": round(expected_rating, 1),
            "deviation": round(deviation, 2),
            "calibration": label,
        }

    overall = _calibration(all_pairs)
    areas_result = {area: _calibration(pairs) for area, pairs in by_area.items()}

    # Calibration score: 1.0 = perfect, lower = worse
    max_dev = max(abs(overall["deviation"]), 0.01)
    cal_score = round(max(0.0, 1.0 - max_dev / 2.5), 2)

    # Detect bias
    worst_area = None
    worst_dev = 0.0
    for area, data in areas_result.items():
        if abs(data["deviation"]) > abs(worst_dev) and data["count"] >= 3:
            worst_dev = data["deviation"]
            worst_area = area

    if worst_area and abs(worst_dev) > 0.5:
        direction = "overconfident" if worst_dev < 0 else "under_confident"
        bias = f"{direction}_in_{worst_area}"
        adj = abs(round(worst_dev / 5.0 * 100))
        if worst_dev < 0:
            recommendation = f"Zmniejsz confidence o ~{adj}% dla decyzji {worst_area}"
        else:
            recommendation = f"Mozesz zwiekszyc confidence o ~{adj}% dla decyzji {worst_area}"
    else:
        bias = "no_significant_bias"
        recommendation = "Kalibracja w normie."

    return {
        "total_decisions_with_outcome": len(all_pairs),
        "calibration_score": cal_score,
        "by_area": areas_result,
        "bias": bias,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# 4. Pattern analysis
# ---------------------------------------------------------------------------

def analyze_decision_patterns(months: int = 6) -> dict:
    """Analyze decision patterns: success/failure by area, timing, entities."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # All decisions with optional outcomes
            cur.execute("""
                SELECT d.id, d.decision_text, d.area, d.confidence, d.decided_at,
                       d.context, d.expected_outcome,
                       do.rating, do.actual_outcome,
                       COALESCE(string_agg(DISTINCT en.canonical_name, ', '), '') as entities
                FROM decisions d
                LEFT JOIN decision_outcomes do ON do.decision_id = d.id
                LEFT JOIN events e ON e.id = d.source_event_id
                LEFT JOIN event_entities ee ON ee.event_id = e.id
                LEFT JOIN entities en ON en.id = ee.entity_id
                WHERE d.decided_at > NOW() - make_interval(months => %s)
                GROUP BY d.id, d.decision_text, d.area, d.confidence, d.decided_at,
                         d.context, d.expected_outcome, do.rating, do.actual_outcome
                ORDER BY d.decided_at DESC
            """, (months,))
            rows = cur.fetchall()

    if not rows:
        return {"total_decisions": 0, "message": "Brak decyzji w podanym okresie."}

    total = len(rows)
    by_area: dict[str, int] = {}
    rated_by_area: dict[str, list[int]] = {}
    best: list[dict] = []
    worst: list[dict] = []

    decision_data_for_llm: list[dict] = []

    for (did, text, area, confidence, decided_at, context, expected,
         rating, actual_outcome, entities) in rows:
        by_area[area] = by_area.get(area, 0) + 1

        record = {
            "id": did,
            "text": text[:200] if text else "",
            "area": area,
            "confidence": float(confidence) if confidence else None,
            "decided_at": str(decided_at) if decided_at else None,
            "hour": decided_at.hour if decided_at else None,
            "entities": entities,
            "rating": int(rating) if rating else None,
            "actual_outcome": actual_outcome[:200] if actual_outcome else None,
        }
        decision_data_for_llm.append(record)

        if rating is not None:
            r = int(rating)
            rated_by_area.setdefault(area, []).append(r)
            if r >= 4:
                best.append({"id": did, "text": text[:200], "rating": r, "area": area})
            if r <= 2:
                worst.append({"id": did, "text": text[:200], "rating": r, "area": area})

    # Success rate by area (rating >= 3 = success)
    success_rate = {}
    for area, ratings in rated_by_area.items():
        successes = sum(1 for r in ratings if r >= 3)
        success_rate[area] = round(successes / len(ratings), 2) if ratings else None

    # LLM pattern analysis (only if enough data)
    patterns: list[str] = []
    if len([r for r in decision_data_for_llm if r["rating"] is not None]) >= 5:
        patterns = _llm_pattern_analysis(decision_data_for_llm)

    return {
        "total_decisions": total,
        "by_area": by_area,
        "success_rate_by_area": success_rate,
        "best_decisions": sorted(best, key=lambda x: x["rating"], reverse=True)[:5],
        "worst_decisions": sorted(worst, key=lambda x: x["rating"])[:5],
        "patterns": patterns,
    }


def _llm_pattern_analysis(decisions: list[dict]) -> list[str]:
    """Use Sonnet to detect patterns in decision data."""
    try:
        data_str = json.dumps(decisions, ensure_ascii=False, default=str)
        if len(data_str) > 12000:
            data_str = data_str[:12000] + "\n[truncated]"

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            temperature=0.2,
            system=[{"type": "text", "text": PATTERN_ANALYSIS_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": data_str}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.decision_intelligence", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        return json.loads(text)
    except Exception as e:
        log.error("pattern_analysis_failed", error=str(e))
        return []


# ---------------------------------------------------------------------------
# 5. Decision digest
# ---------------------------------------------------------------------------

def generate_decision_digest() -> str:
    """Weekly digest of decision activity."""
    now = datetime.now(timezone.utc)
    week_num = now.isocalendar()[1]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # New decisions this week
            cur.execute("""
                SELECT area, COUNT(*)
                FROM decisions
                WHERE decided_at > NOW() - INTERVAL '7 days'
                GROUP BY area
            """)
            new_by_area = {r[0]: r[1] for r in cur.fetchall()}
            total_new = sum(new_by_area.values())

            # Pending reviews
            cur.execute("""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE next_review_at < NOW())
                FROM decisions
                WHERE review_status IN ('pending', 'reminded')
            """)
            pending_row = cur.fetchone()
            pending_total = pending_row[0] if pending_row else 0
            pending_overdue = pending_row[1] if pending_row else 0

            # Reviewed this week
            cur.execute("""
                SELECT COUNT(*), AVG(do.rating)
                FROM decision_outcomes do
                WHERE do.created_at > NOW() - INTERVAL '7 days'
            """)
            reviewed_row = cur.fetchone()
            reviewed_count = reviewed_row[0] if reviewed_row else 0
            avg_rating = round(float(reviewed_row[1]), 1) if reviewed_row and reviewed_row[1] else None

    # Calibration summary
    cal = analyze_confidence_calibration(months=3)

    # Build digest
    lines = [f"\U0001f4ca *Decision Digest (tydzien {week_num})*"]

    area_detail = ", ".join(f"{c} {a}" for a, c in new_by_area.items()) if new_by_area else "brak"
    lines.append(f"- Nowe decyzje: {total_new} ({area_detail})")
    lines.append(f"- Pending review: {pending_total} ({pending_overdue} overdue)")

    if reviewed_count > 0:
        rating_str = f" (avg rating {avg_rating}/5)" if avg_rating else ""
        lines.append(f"- Reviewed: {reviewed_count}{rating_str}")
    else:
        lines.append("- Reviewed: 0")

    if cal.get("bias") and cal["bias"] != "insufficient_data" and cal["bias"] != "no_significant_bias":
        lines.append(f"- Calibration bias: {cal['bias']}")
        lines.append(f"- Recommendation: {cal['recommendation']}")
    elif cal.get("calibration_score") is not None:
        lines.append(f"- Calibration score: {cal['calibration_score']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. WhatsApp command handler
# ---------------------------------------------------------------------------

def handle_decision_outcome(text: str) -> dict | None:
    """Parse 'outcome #ID: [description] rating: [1-5]' or 'skip #ID' from WhatsApp.

    Returns dict with result or None if text doesn't match.
    """
    # Pattern: outcome #12: some description rating: 4
    outcome_match = re.match(
        r"outcome\s+#?(\d+)\s*:\s*(.+?)\s+rating\s*:\s*([1-5])",
        text.strip(),
        re.IGNORECASE,
    )
    if outcome_match:
        decision_id = int(outcome_match.group(1))
        description = outcome_match.group(2).strip()
        rating = int(outcome_match.group(3))

        return _record_outcome(decision_id, description, rating)

    # Pattern: skip #12
    skip_match = re.match(r"skip\s+#?(\d+)", text.strip(), re.IGNORECASE)
    if skip_match:
        decision_id = int(skip_match.group(1))
        return _skip_decision(decision_id)

    return None


def _record_outcome(decision_id: int, description: str, rating: int) -> dict:
    """Insert outcome and update decision review_status."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Verify decision exists
                cur.execute("SELECT id FROM decisions WHERE id = %s", (decision_id,))
                if not cur.fetchone():
                    return {"error": f"Decyzja #{decision_id} nie istnieje."}

                # Check for duplicate outcome
                cur.execute(
                    "SELECT id FROM decision_outcomes WHERE decision_id = %s",
                    (decision_id,),
                )
                if cur.fetchone():
                    return {"error": f"Decyzja #{decision_id} ma juz wynik."}

                cur.execute("""
                    INSERT INTO decision_outcomes (decision_id, actual_outcome, rating)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (decision_id, description, rating))
                outcome_id = cur.fetchone()[0]

                cur.execute("""
                    UPDATE decisions
                    SET review_status = 'reviewed'
                    WHERE id = %s
                """, (decision_id,))
            conn.commit()

        log.info("decision_outcome_recorded",
                 decision_id=decision_id, outcome_id=outcome_id, rating=rating)
        return {
            "status": "recorded",
            "decision_id": decision_id,
            "outcome_id": outcome_id,
            "rating": rating,
        }
    except Exception as e:
        log.error("decision_outcome_record_failed", error=str(e), decision_id=decision_id)
        return {"error": str(e)}


def _skip_decision(decision_id: int) -> dict:
    """Mark a decision review as skipped."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM decisions WHERE id = %s", (decision_id,))
                if not cur.fetchone():
                    return {"error": f"Decyzja #{decision_id} nie istnieje."}

                cur.execute("""
                    UPDATE decisions
                    SET review_status = 'skipped'
                    WHERE id = %s
                """, (decision_id,))
            conn.commit()

        log.info("decision_skipped", decision_id=decision_id)
        return {"status": "skipped", "decision_id": decision_id}
    except Exception as e:
        log.error("decision_skip_failed", error=str(e), decision_id=decision_id)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# WhatsApp helper
# ---------------------------------------------------------------------------

def _send_whatsapp(message: str) -> bool:
    """Send message via WhatsApp using openclaw."""
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.warning("whatsapp_send_failed", stderr=result.stderr)
            return False
        return True
    except Exception as e:
        log.error("whatsapp_send_error", error=str(e))
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_decision_intelligence() -> dict:
    """Main pipeline:
    1. Auto-capture new decisions from events
    2. Send review reminders for pending
    3. Analyze patterns (if enough data)
    4. Return summary
    """
    result: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Auto-capture
    try:
        captured = auto_capture_decisions(hours=24)
        result["captured"] = len(captured)
        result["captured_decisions"] = captured
    except Exception as e:
        log.error("auto_capture_failed", error=str(e))
        result["captured"] = 0
        result["capture_error"] = str(e)

    # 2. Reminders
    try:
        reminders = send_review_reminders()
        result["reminders_sent"] = len(reminders)
    except Exception as e:
        log.error("reminders_failed", error=str(e))
        result["reminders_sent"] = 0
        result["reminder_error"] = str(e)

    # 3. Calibration
    try:
        cal = analyze_confidence_calibration(months=6)
        result["calibration"] = cal
    except Exception as e:
        log.error("calibration_failed", error=str(e))
        result["calibration"] = {"error": str(e)}

    # 4. Patterns (only if we have reviewed decisions)
    try:
        patterns = analyze_decision_patterns(months=6)
        result["patterns"] = patterns
    except Exception as e:
        log.error("patterns_failed", error=str(e))
        result["patterns"] = {"error": str(e)}

    # 5. Digest
    try:
        result["digest"] = generate_decision_digest()
    except Exception as e:
        log.error("digest_failed", error=str(e))
        result["digest"] = None

    log.info("decision_intelligence_complete",
             captured=result.get("captured", 0),
             reminders=result.get("reminders_sent", 0))

    return result


if __name__ == "__main__":
    result = run_decision_intelligence()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
