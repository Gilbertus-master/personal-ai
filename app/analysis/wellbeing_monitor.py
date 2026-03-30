"""
Wellbeing Monitor — Tracks Sebastian's personal wellbeing signals.

Gathers indicators from communication patterns, work hours, conflicts,
family events, and meeting density. LLM scores overall wellbeing 1-10.

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

WELLBEING_PROMPT = """You are a personal wellbeing analyst for a CEO/business owner.

Given weekly indicators about work patterns, conflicts, family time, health, and communication habits,
assess the person's overall wellbeing.

Provide:
1. **overall_score** (1-10): 1=burnout/crisis, 5=moderate stress, 10=thriving
2. **stress_score** (1-10): 1=extreme stress, 10=very relaxed
3. **family_score** (1-10): 1=no family time/family problems, 10=great family engagement
4. **health_score** (1-10): 1=health concerns, 10=healthy indicators
5. **work_life_balance** (1-10): 1=all work no life, 10=excellent balance
6. **analysis** (2-3 sentences): Key observations about wellbeing this week
7. **suggestions** (list of 2-3 strings): Actionable improvement suggestions

Consider:
- Late-night work is a stress signal
- Weekend activity should be low (indicates overwork)
- High conflict count increases stress
- Family events (positive) improve wellbeing
- High meeting density reduces deep work time

Respond ONLY with JSON:
{"overall_score": N.N, "stress_score": N.N, "family_score": N.N, "health_score": N.N, "work_life_balance": N.N, "analysis": "...", "suggestions": ["...", ...]}"""


def _ensure_tables() -> None:
    """Create wellbeing_scores table if not exists."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wellbeing_scores (
                    id BIGSERIAL PRIMARY KEY,
                    week_start DATE NOT NULL UNIQUE,
                    overall_score NUMERIC(3,1) NOT NULL CHECK (overall_score >= 1 AND overall_score <= 10),
                    stress_score NUMERIC(3,1),
                    family_score NUMERIC(3,1),
                    health_score NUMERIC(3,1),
                    work_life_balance NUMERIC(3,1),
                    indicators JSONB,
                    analysis TEXT,
                    suggestions TEXT[],
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()
    log.info("wellbeing_monitor.tables_ensured")


def gather_wellbeing_indicators(week_start: str) -> dict[str, Any]:
    """Gather wellbeing indicators for a given week.

    Indicators:
    - late_night_count: emails/Teams after 22:00 CET
    - conflict_count: conflict events
    - family_positive_count: positive family events
    - family_negative_count: negative family events
    - health_event_count: health-related events
    - meeting_count: meeting/call events
    - weekend_event_count: events on Saturday/Sunday
    - total_event_count: all events in the week
    """
    indicators = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Late-night communications (after 22:00 CET = 21:00 UTC in winter, 20:00 UTC in summer)
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND EXTRACT(HOUR FROM e.event_time AT TIME ZONE 'Europe/Warsaw') >= 22
                  AND e.event_type IN ('email_sent', 'email_received', 'teams_message',
                                       'meeting', 'decision', 'commitment')
            """, (week_start, week_start))
            indicators["late_night_count"] = cur.fetchall()[0][0]

            # Conflict events
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type IN ('conflict', 'escalation', 'blocker')
            """, (week_start, week_start))
            indicators["conflict_count"] = cur.fetchall()[0][0]

            # Family events (positive)
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type = 'family'
                  AND (e.summary NOT ILIKE '%%problem%%'
                       AND e.summary NOT ILIKE '%%conflict%%'
                       AND e.summary NOT ILIKE '%%argument%%')
            """, (week_start, week_start))
            indicators["family_positive_count"] = cur.fetchall()[0][0]

            # Family events (negative)
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type = 'family'
                  AND (e.summary ILIKE '%%problem%%'
                       OR e.summary ILIKE '%%conflict%%'
                       OR e.summary ILIKE '%%argument%%')
            """, (week_start, week_start))
            indicators["family_negative_count"] = cur.fetchall()[0][0]

            # Health events
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type = 'health'
            """, (week_start, week_start))
            indicators["health_event_count"] = cur.fetchall()[0][0]

            # Meeting density
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type IN ('meeting', 'call')
            """, (week_start, week_start))
            indicators["meeting_count"] = cur.fetchall()[0][0]

            # Weekend activity
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND EXTRACT(DOW FROM e.event_time) IN (0, 6)
            """, (week_start, week_start))
            indicators["weekend_event_count"] = cur.fetchall()[0][0]

            # Total events
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
            """, (week_start, week_start))
            indicators["total_event_count"] = cur.fetchall()[0][0]

            # Recent communication summaries for context
            cur.execute("""
                SELECT e.event_type, e.summary
                FROM events e
                WHERE e.event_time >= %s::date
                  AND e.event_time < %s::date + INTERVAL '7 days'
                  AND e.event_type IN ('family', 'health', 'conflict', 'escalation',
                                       'personal', 'decision')
                ORDER BY e.event_time DESC
                LIMIT 20
            """, (week_start, week_start))
            indicators["notable_events"] = [
                {"type": r[0], "summary": r[1]} for r in cur.fetchall()
            ]

    log.info("wellbeing_monitor.indicators_gathered", week=week_start, indicators={
        k: v for k, v in indicators.items() if k != "notable_events"
    })
    return indicators


def analyze_wellbeing(indicators: dict[str, Any]) -> dict[str, Any]:
    """Use LLM to analyze wellbeing from indicators."""
    # Build context
    ctx_parts = ["=== WEEKLY INDICATORS ==="]
    for key, value in indicators.items():
        if key == "notable_events":
            continue
        ctx_parts.append(f"- {key}: {value}")

    if indicators.get("notable_events"):
        ctx_parts.append("\n=== NOTABLE EVENTS ===")
        for ev in indicators["notable_events"]:
            ctx_parts.append(f"[{ev['type']}] {ev['summary']}")

    context = "\n".join(ctx_parts)

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=600,
            temperature=0.1,
            system=[{"type": "text", "text": WELLBEING_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.wellbeing_monitor", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
    except Exception as e:
        log.error("wellbeing_monitor.llm_error", error=str(e))
        return {"status": "error", "error": str(e)}

    # Clamp scores
    for key in ("overall_score", "stress_score", "family_score", "health_score", "work_life_balance"):
        if key in result:
            result[key] = max(1.0, min(10.0, float(result[key])))

    return result


def run_wellbeing_check() -> dict[str, Any]:
    """Run weekly wellbeing pipeline: gather + analyze + store."""
    _ensure_tables()

    # Current week start (Monday)
    now = datetime.now(timezone.utc)
    week_start = (now - __import__("datetime").timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    indicators = gather_wellbeing_indicators(week_start)
    analysis = analyze_wellbeing(indicators)

    if analysis.get("status") == "error":
        return {"week_start": week_start, "status": "error", "error": analysis["error"]}

    overall = analysis.get("overall_score", 5.0)
    stress = analysis.get("stress_score")
    family = analysis.get("family_score")
    health = analysis.get("health_score")
    wlb = analysis.get("work_life_balance")
    text_analysis = analysis.get("analysis", "")
    suggestions = analysis.get("suggestions", [])

    # Remove notable_events from stored indicators (too verbose)
    stored_indicators = {k: v for k, v in indicators.items() if k != "notable_events"}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wellbeing_scores
                    (week_start, overall_score, stress_score, family_score,
                     health_score, work_life_balance, indicators, analysis, suggestions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (week_start)
                DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    stress_score = EXCLUDED.stress_score,
                    family_score = EXCLUDED.family_score,
                    health_score = EXCLUDED.health_score,
                    work_life_balance = EXCLUDED.work_life_balance,
                    indicators = EXCLUDED.indicators,
                    analysis = EXCLUDED.analysis,
                    suggestions = EXCLUDED.suggestions,
                    created_at = NOW()
                RETURNING id
            """, (
                week_start, overall, stress, family, health, wlb,
                json.dumps(stored_indicators), text_analysis,
                suggestions if suggestions else None,
            ))
            record_id = cur.fetchall()[0][0]
            conn.commit()

    log.info("wellbeing_monitor.check_complete",
             week=week_start, overall=overall, stress=stress)

    return {
        "id": record_id,
        "week_start": week_start,
        "overall_score": float(overall),
        "stress_score": float(stress) if stress else None,
        "family_score": float(family) if family else None,
        "health_score": float(health) if health else None,
        "work_life_balance": float(wlb) if wlb else None,
        "analysis": text_analysis,
        "suggestions": suggestions,
        "indicators": stored_indicators,
        "status": "ok",
    }


def get_wellbeing_trend(weeks: int = 8) -> dict[str, Any]:
    """Get wellbeing trend over recent weeks."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT week_start, overall_score, stress_score, family_score,
                       health_score, work_life_balance, analysis, suggestions
                FROM wellbeing_scores
                ORDER BY week_start DESC
                LIMIT %s
            """, (weeks,))
            rows = cur.fetchall()

    if not rows:
        return {"status": "no_data", "message": "No wellbeing data recorded yet"}

    history = []
    for r in rows:
        history.append({
            "week": str(r[0]),
            "overall": float(r[1]),
            "stress": float(r[2]) if r[2] else None,
            "family": float(r[3]) if r[3] else None,
            "health": float(r[4]) if r[4] else None,
            "work_life_balance": float(r[5]) if r[5] else None,
            "analysis": r[6],
            "suggestions": r[7] or [],
        })

    history.reverse()  # chronological

    # Compute trend
    scores = [h["overall"] for h in history]
    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        early_avg = sum(scores[:3]) / 3
        diff = recent_avg - early_avg
        if diff <= -1.0:
            trend = "declining"
        elif diff >= 1.0:
            trend = "improving"
        else:
            trend = "stable"
    elif len(scores) == 2:
        diff = scores[-1] - scores[0]
        trend = "declining" if diff <= -1.0 else ("improving" if diff >= 1.0 else "stable")
    else:
        diff = 0.0
        trend = "insufficient_data"

    current = history[-1]

    return {
        "trend": trend,
        "current_score": current["overall"],
        "diff": round(diff, 1),
        "weeks_analyzed": len(history),
        "history": history,
        "status": "ok",
    }
