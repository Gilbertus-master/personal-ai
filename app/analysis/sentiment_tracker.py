"""
Sentiment Trend Monitor — Weekly per-person sentiment tracking.

Tracks communication tone via events and chunks, scores 1-5 per person per week.
Detects trends: falling, rising, stable. Alerts on significant changes.

Cron: 0 20 * * 0 (Sunday 20:00 CET — weekly with other analysis)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

SENTIMENT_PROMPT = """You are analyzing communication tone for a specific person in a business context.

Given events and communications involving this person, provide:
1. **sentiment_score** (1-5): 1=very negative/hostile, 2=negative/frustrated, 3=neutral, 4=positive/constructive, 5=very positive/enthusiastic
2. **analysis** (1-2 sentences): Brief assessment of communication tone and relationship quality
3. **red_flags** (list of strings): Any concerning patterns (empty list if none)

Consider:
- Tone of emails and messages (aggressive, passive-aggressive, constructive, warm)
- Conflict frequency and severity
- Responsiveness and engagement level
- Positive signals (praise, gratitude, collaboration)

Respond ONLY with JSON:
{"sentiment_score": N.N, "analysis": "...", "red_flags": ["...", ...]}"""


_tables_ensured = False
def _ensure_tables() -> None:
    """Create sentiment_scores table if not exists."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_scores (
                    id BIGSERIAL PRIMARY KEY,
                    person_name TEXT NOT NULL,
                    person_id BIGINT REFERENCES people(id),
                    week_start DATE NOT NULL,
                    score NUMERIC(3,1) NOT NULL CHECK (score >= 1 AND score <= 5),
                    analysis TEXT,
                    event_count INT DEFAULT 0,
                    chunk_count INT DEFAULT 0,
                    red_flags TEXT[],
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(person_name, week_start)
                );

                CREATE INDEX IF NOT EXISTS idx_sentiment_person
                    ON sentiment_scores(person_name);
                CREATE INDEX IF NOT EXISTS idx_sentiment_week
                    ON sentiment_scores(week_start);
            """)
            conn.commit()
    log.info("sentiment_tracker.tables_ensured")
    _tables_ensured = True


def _gather_person_data(person_name: str, week_start: str) -> dict[str, Any]:
    """Gather events and chunks involving a person for a given week."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Events involving this person (via entities)
            cur.execute("""
                SELECT e.id, e.event_type, e.summary, e.event_time
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                JOIN entities en ON en.id = ee.entity_id
                WHERE en.canonical_name ILIKE %s
                  AND e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                ORDER BY e.event_time
                LIMIT 50
            """, (f"%{person_name}%", week_start, week_start))
            events = [
                {"id": r[0], "type": r[1], "summary": r[2],
                 "time": str(r[3]) if r[3] else None}
                for r in cur.fetchall()
            ]

            # Chunks mentioning this person
            cur.execute("""
                SELECT c.id, LEFT(c.text, 400), s.source_type
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE c.text ILIKE %s
                  AND d.created_at >= %s::date
                  AND d.created_at < %s::date + INTERVAL '7 days'
                  AND s.source_type IN ('email', 'email_attachment', 'teams', 'audio_transcript')
                ORDER BY d.created_at DESC
                LIMIT 30
            """, (f"%{person_name}%", week_start, week_start))
            chunks = [
                {"id": r[0], "text": r[1], "source": r[2]}
                for r in cur.fetchall()
            ]

            # Get person_id if exists
            cur.execute("""
                SELECT id FROM people
                WHERE canonical_name ILIKE %s
                LIMIT 1
            """, (f"%{person_name}%",))
            row = cur.fetchone()
            person_id = row[0] if row else None

    return {
        "events": events,
        "chunks": chunks,
        "event_count": len(events),
        "chunk_count": len(chunks),
        "person_id": person_id,
    }


def analyze_person_sentiment(person_name: str, week_start: str) -> dict[str, Any]:
    """Analyze sentiment for one person for one week."""
    _ensure_tables()

    data = _gather_person_data(person_name, week_start)

    if data["event_count"] == 0 and data["chunk_count"] == 0:
        log.info("sentiment_tracker.no_data", person=person_name, week=week_start)
        return {
            "person_name": person_name,
            "week_start": week_start,
            "status": "no_data",
            "message": "No events or communications found for this person/week",
        }

    # Build context for LLM
    ctx_parts = [f"Person: {person_name}", f"Week: {week_start}", ""]
    if data["events"]:
        ctx_parts.append("=== EVENTS ===")
        for ev in data["events"]:
            ctx_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    if data["chunks"]:
        ctx_parts.append("\n=== COMMUNICATIONS ===")
        for ch in data["chunks"]:
            ctx_parts.append(f"[{ch['source']}] {ch['text']}")

    context = "\n".join(ctx_parts)
    if len(context) > 12000:
        context = context[:12000] + "\n[truncated]"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0.1,
            system=[{"type": "text", "text": SENTIMENT_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.sentiment_tracker", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
    except Exception as e:
        log.error("sentiment_tracker.llm_error", person=person_name, error=str(e))
        return {
            "person_name": person_name,
            "week_start": week_start,
            "status": "error",
            "error": str(e),
        }

    score = max(1.0, min(5.0, float(result.get("sentiment_score", 3.0))))
    analysis = result.get("analysis", "")
    red_flags = result.get("red_flags", [])

    # Save to DB
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sentiment_scores
                    (person_name, person_id, week_start, score, analysis,
                     event_count, chunk_count, red_flags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (person_name, week_start)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    analysis = EXCLUDED.analysis,
                    event_count = EXCLUDED.event_count,
                    chunk_count = EXCLUDED.chunk_count,
                    red_flags = EXCLUDED.red_flags,
                    created_at = NOW()
                RETURNING id
            """, (
                person_name, data["person_id"], week_start, score,
                analysis, data["event_count"], data["chunk_count"],
                red_flags if red_flags else None,
            ))
            record_id = cur.fetchall()[0][0]
            conn.commit()

    log.info("sentiment_tracker.scored",
             person=person_name, week=week_start, score=score,
             events=data["event_count"], chunks=data["chunk_count"])

    return {
        "id": record_id,
        "person_name": person_name,
        "week_start": week_start,
        "score": float(score),
        "analysis": analysis,
        "red_flags": red_flags,
        "event_count": data["event_count"],
        "chunk_count": data["chunk_count"],
        "status": "ok",
    }


def detect_sentiment_trends(person_name: str, weeks: int = 8) -> dict[str, Any]:
    """Detect sentiment trends for a person over recent weeks."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT week_start, score, analysis, red_flags
                FROM sentiment_scores
                WHERE person_name = %s
                ORDER BY week_start DESC
                LIMIT %s
            """, (person_name, weeks))
            rows = cur.fetchall()

    if len(rows) < 2:
        return {
            "person_name": person_name,
            "status": "insufficient_data",
            "message": f"Only {len(rows)} weeks of data (need 2+)",
        }

    scores = [{"week": str(r[0]), "score": float(r[1]), "analysis": r[2],
               "red_flags": r[3] or []} for r in rows]
    scores.reverse()  # chronological order

    # Compute trend
    recent_scores = [s["score"] for s in scores]
    if len(recent_scores) >= 3:
        last_3_avg = sum(recent_scores[-3:]) / 3
        first_3_avg = sum(recent_scores[:3]) / 3
        diff = last_3_avg - first_3_avg
        if diff <= -0.5:
            trend = "falling"
        elif diff >= 0.5:
            trend = "rising"
        else:
            trend = "stable"
    else:
        diff = recent_scores[-1] - recent_scores[0]
        trend = "falling" if diff <= -0.5 else ("rising" if diff >= 0.5 else "stable")

    current_score = recent_scores[-1]
    avg_score = sum(recent_scores) / len(recent_scores)

    return {
        "person_name": person_name,
        "trend": trend,
        "current_score": current_score,
        "average_score": round(avg_score, 1),
        "diff": round(diff, 1),
        "weeks_analyzed": len(scores),
        "history": scores,
        "status": "ok",
    }


def run_weekly_sentiment_scan() -> dict[str, Any]:
    """Scan all active people for current week sentiment."""
    _ensure_tables()

    # Get current week start (Monday)
    now = datetime.now(timezone.utc)
    week_start = (now - __import__("datetime").timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    # Get active people (those with recent events)
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT en.canonical_name
                FROM entities en
                JOIN event_entities ee ON ee.entity_id = en.id
                JOIN events e ON e.id = ee.event_id
                WHERE en.entity_type = 'person'
                  AND e.event_time > NOW() - INTERVAL '14 days'
                  AND en.canonical_name IS NOT NULL
                  AND en.canonical_name != ''
                ORDER BY en.canonical_name
            """)
            people = [r[0] for r in cur.fetchall()]

    log.info("sentiment_tracker.scan_start", people_count=len(people), week=week_start)

    results = []
    errors = []
    for person in people:
        try:
            result = analyze_person_sentiment(person, week_start)
            results.append(result)
        except Exception as e:
            log.error("sentiment_tracker.scan_error", person=person, error=str(e))
            errors.append({"person": person, "error": str(e)})

    scored = [r for r in results if r.get("status") == "ok"]
    log.info("sentiment_tracker.scan_complete",
             total=len(people), scored=len(scored), errors=len(errors))

    return {
        "week_start": week_start,
        "people_scanned": len(people),
        "scored": len(scored),
        "skipped_no_data": len([r for r in results if r.get("status") == "no_data"]),
        "errors": len(errors),
        "results": results,
        "error_details": errors if errors else None,
    }


def get_sentiment_alerts() -> list[dict[str, Any]]:
    """Return people with significant sentiment changes.

    Alerts on:
    - Score drop >= 1.0 week-over-week
    - 3+ consecutive weeks of decline
    - Current score <= 2.0
    """
    _ensure_tables()
    alerts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Get latest 4 weeks per person
            cur.execute("""
                WITH ranked AS (
                    SELECT person_name, week_start, score,
                           ROW_NUMBER() OVER (PARTITION BY person_name ORDER BY week_start DESC) as rn
                    FROM sentiment_scores
                )
                SELECT person_name, week_start, score, rn
                FROM ranked
                WHERE rn <= 4
                ORDER BY person_name, rn
            """)
            rows = cur.fetchall()

    # Group by person
    person_data: dict[str, list] = {}
    for name, week, score, rn in rows:
        person_data.setdefault(name, []).append({
            "week": str(week),
            "score": float(score),
            "rn": rn,
        })

    for person, weeks in person_data.items():
        weeks.sort(key=lambda w: w["rn"])  # most recent first

        # Alert: current score very low
        if weeks[0]["score"] <= 2.0:
            alerts.append({
                "person": person,
                "alert_type": "low_score",
                "current_score": weeks[0]["score"],
                "week": weeks[0]["week"],
                "message": f"{person}: sentiment score critically low ({weeks[0]['score']})",
            })

        # Alert: large drop week-over-week
        if len(weeks) >= 2:
            drop = weeks[1]["score"] - weeks[0]["score"]
            if drop >= 1.0:
                alerts.append({
                    "person": person,
                    "alert_type": "large_drop",
                    "drop": round(drop, 1),
                    "from_score": weeks[1]["score"],
                    "to_score": weeks[0]["score"],
                    "week": weeks[0]["week"],
                    "message": f"{person}: sentiment dropped by {drop:.1f} ({weeks[1]['score']} → {weeks[0]['score']})",
                })

        # Alert: 3+ consecutive weeks of decline
        if len(weeks) >= 3:
            declining = all(
                weeks[i]["score"] < weeks[i + 1]["score"]
                for i in range(min(3, len(weeks)) - 1)
            )
            if declining:
                alerts.append({
                    "person": person,
                    "alert_type": "sustained_decline",
                    "weeks_declining": min(3, len(weeks)),
                    "scores": [w["score"] for w in weeks[:3]],
                    "message": f"{person}: sentiment declining for 3+ consecutive weeks",
                })

    log.info("sentiment_tracker.alerts", count=len(alerts))
    return alerts
