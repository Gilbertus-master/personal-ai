"""
Strategic Radar — cross-domain correlation engine.

Connects: market + competitors + calendar + goals + events into one strategic view.
Generates daily "Strategic Radar" — unified intelligence picture for Sebastian.

Cron: 0 6 * * * (6:00 UTC / 7:00 CET — before morning brief)
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

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=90.0)

RADAR_PROMPT = """Jesteś Gilbertus Albans — strategicznym mentatem Sebastiana Jabłońskiego (REH + REF, sektor energetyczny).

Na podstawie dostarczonych danych z wielu domen wygeneruj "Strategic Radar" — ujednolicony obraz strategiczny.

Format (JSON):
{
  "correlations": [
    {
      "title": "krótki tytuł korelacji (po polsku)",
      "domains": ["market", "competitor", "goal", "calendar"],
      "description": "co łączy te sygnały (2-3 zdania)",
      "impact": "wpływ na REH/REF (1 zdanie)",
      "urgency": "immediate|this_week|this_month|watch",
      "suggested_action": "konkretne działanie (1 zdanie)"
    }
  ],
  "blind_spots": ["czego NIE widzimy — potencjalne luki w danych (max 3)"],
  "strategic_summary": "2-3 zdania: kluczowy obraz dnia z perspektywy Sun Tzu"
}

Szukaj POŁĄCZEŃ między domenami — to jest wartość radaru.
Np.: zmiana cen TGE + spotkanie z Tauron + cel revenue = szansa renegocjacji.
Respond ONLY with JSON."""


# ================================================================
# Schema
# ================================================================

def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS strategic_radar (
                    id BIGSERIAL PRIMARY KEY,
                    radar_date DATE NOT NULL,
                    correlations JSONB DEFAULT '[]',
                    blind_spots JSONB DEFAULT '[]',
                    strategic_summary TEXT,
                    context_used JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(radar_date)
                );
            """)
            conn.commit()


# ================================================================
# Context gathering — cross-domain
# ================================================================

def _safe_query(query: str, params: tuple = ()) -> list:
    """Execute query safely — return empty list on error."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        log.warning("radar_query_failed", error=str(e))
        return []


def _gather_radar_context() -> dict[str, Any]:
    """Gather data from all domains for correlation."""
    context = {}

    # Market insights (last 48h)
    context["market"] = [
        {"type": r[0], "title": r[1], "description": r[2], "impact": r[3], "relevance": r[4]}
        for r in _safe_query("""
            SELECT insight_type, title, description, impact_assessment, relevance_score
            FROM market_insights WHERE created_at > NOW() - INTERVAL '48 hours'
            ORDER BY relevance_score DESC LIMIT 10
        """)
    ]

    # Competitor signals (last 7 days)
    context["competitors"] = [
        {"competitor": r[0], "type": r[1], "title": r[2], "description": r[3], "severity": r[4]}
        for r in _safe_query("""
            SELECT c.name, cs.signal_type, cs.title, cs.description, cs.severity
            FROM competitor_signals cs JOIN competitors c ON c.id = cs.competitor_id
            WHERE cs.created_at > NOW() - INTERVAL '7 days'
            ORDER BY CASE cs.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
            LIMIT 10
        """)
    ]

    # Strategic goals (active)
    context["goals"] = [
        {"title": r[0], "current": r[1], "target": r[2], "unit": r[3],
         "status": r[4], "deadline": str(r[5]) if r[5] else None, "company": r[6]}
        for r in _safe_query("""
            SELECT title, current_value, target_value, unit, status, deadline, company
            FROM strategic_goals WHERE status NOT IN ('cancelled', 'achieved')
            ORDER BY CASE status WHEN 'behind' THEN 0 WHEN 'at_risk' THEN 1 ELSE 2 END
            LIMIT 10
        """)
    ]

    # Recent key events (last 48h)
    context["events"] = [
        {"type": r[0], "summary": r[1], "time": str(r[2]) if r[2] else None}
        for r in _safe_query("""
            SELECT event_type, summary, event_time FROM events
            WHERE event_time > NOW() - INTERVAL '48 hours'
            AND event_type IN ('decision', 'commitment', 'conflict', 'trade', 'deadline', 'escalation')
            ORDER BY event_time DESC LIMIT 15
        """)
    ]

    # Active scenarios
    context["scenarios"] = [
        {"title": r[0], "type": r[1], "total_impact": float(r[2]) if r[2] else 0}
        for r in _safe_query("""
            SELECT s.title, s.scenario_type, COALESCE(SUM(o.impact_value_pln), 0)
            FROM scenarios s LEFT JOIN scenario_outcomes o ON o.scenario_id = s.id
            WHERE s.status = 'analyzed'
            GROUP BY s.id, s.title, s.scenario_type
            ORDER BY COALESCE(SUM(o.impact_value_pln), 0) LIMIT 5
        """)
    ]

    return context


# ================================================================
# Radar generation
# ================================================================

def generate_strategic_radar(force: bool = False) -> dict[str, Any]:
    """Generate today's Strategic Radar."""
    _ensure_tables()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    if not force:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM strategic_radar WHERE radar_date = %s", (today,))
                if cur.fetchall():
                    return {"status": "exists", "date": today}

    started = datetime.now(tz=timezone.utc)
    context = _gather_radar_context()

    # Check if enough data
    total_signals = sum(len(v) for v in context.values() if isinstance(v, list))
    if total_signals < 3:
        return {"status": "insufficient_data", "signals": total_signals}

    # Build prompt
    context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    user_msg = f"Data: {today}\n\nDane ze wszystkich domen:\n{context_text}"

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=2000,
        temperature=0.2,
        system=[{"type": "text", "text": RADAR_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "strategic_radar", response.usage)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        radar = json.loads(raw)
    except json.JSONDecodeError:
        # Try fixing common issues: single quotes, trailing commas
        try:
            import re
            fixed = re.sub(r',\s*}', '}', re.sub(r',\s*]', ']', raw))
            radar = json.loads(fixed)
        except json.JSONDecodeError:
            log.warning("radar.json_parse_failed", raw=raw[:200])
            # Extract what we can
            radar = {"correlations": [], "blind_spots": [], "strategic_summary": raw[:500]}

    # Store
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO strategic_radar (radar_date, correlations, blind_spots,
                    strategic_summary, context_used)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (radar_date) DO UPDATE SET
                    correlations = EXCLUDED.correlations,
                    blind_spots = EXCLUDED.blind_spots,
                    strategic_summary = EXCLUDED.strategic_summary,
                    context_used = EXCLUDED.context_used,
                    created_at = NOW()
            """, (
                today,
                json.dumps(radar.get("correlations", []), ensure_ascii=False),
                json.dumps(radar.get("blind_spots", []), ensure_ascii=False),
                radar.get("strategic_summary", ""),
                json.dumps({"signals_per_domain": {k: len(v) for k, v in context.items() if isinstance(v, list)}}),
            ))
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("strategic_radar_generated", correlations=len(radar.get("correlations", [])), latency_ms=latency_ms)

    return {
        "status": "generated",
        "date": today,
        "correlations": radar.get("correlations", []),
        "blind_spots": radar.get("blind_spots", []),
        "strategic_summary": radar.get("strategic_summary", ""),
        "latency_ms": latency_ms,
    }


def get_todays_radar() -> dict[str, Any] | None:
    """Retrieve today's radar."""
    _ensure_tables()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT radar_date, correlations, blind_spots, strategic_summary
                FROM strategic_radar WHERE radar_date = %s
            """, (today,))
            rows = cur.fetchall()
            if rows:
                r = rows[0]
                return {
                    "date": str(r[0]),
                    "correlations": r[1] if isinstance(r[1], list) else json.loads(r[1]),
                    "blind_spots": r[2] if isinstance(r[2], list) else json.loads(r[2]),
                    "summary": r[3],
                }
    return None
