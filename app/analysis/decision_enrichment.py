"""
Decision Journal Enrichment — auto-enrich decisions with context.

When Sebastian logs a decision, auto-add:
- Market context (relevant insights at decision time)
- Competitor context (relevant signals)
- Goal alignment (which goals this impacts)
- Outcome tracking at 30/60/90 days

Cron: 0 22 * * * (daily 23:00 CET — enrich today's decisions)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
from datetime import timedelta
from typing import Any

from app.db.postgres import get_pg_connection


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS decision_context (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                    market_context JSONB DEFAULT '[]',
                    competitor_context JSONB DEFAULT '[]',
                    goal_alignment JSONB DEFAULT '[]',
                    enriched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(decision_id)
                );

                CREATE TABLE IF NOT EXISTS decision_outcome_checks (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
                    check_days INTEGER NOT NULL,
                    check_date DATE NOT NULL,
                    checked BOOLEAN DEFAULT FALSE,
                    outcome_notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()


def enrich_decision(decision_id: int) -> dict[str, Any]:
    """Enrich a decision with market/competitor/goal context."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, decision_text, area, created_at FROM decisions WHERE id = %s", (decision_id,))
            rows = cur.fetchall()
            if not rows:
                return {"error": f"Decision {decision_id} not found"}
            did, text, area, created = rows[0]

    # Market context at decision time
    market = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT insight_type, title, relevance_score
                FROM market_insights
                WHERE created_at BETWEEN %s - INTERVAL '48 hours' AND %s + INTERVAL '24 hours'
                ORDER BY relevance_score DESC LIMIT 5
            """, (created, created))
            market = [{"type": r[0], "title": r[1], "relevance": r[2]} for r in cur.fetchall()]

    # Competitor context
    competitors = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.name, cs.title, cs.severity
                FROM competitor_signals cs JOIN competitors c ON c.id = cs.competitor_id
                WHERE cs.created_at BETWEEN %s - INTERVAL '7 days' AND %s + INTERVAL '1 day'
                AND cs.severity IN ('medium', 'high')
                ORDER BY cs.created_at DESC LIMIT 5
            """, (created, created))
            competitors = [{"competitor": r[0], "signal": r[1], "severity": r[2]} for r in cur.fetchall()]

    # Goal alignment
    goals = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, company, status FROM strategic_goals
                WHERE status NOT IN ('cancelled', 'achieved')
            """)
            for r in cur.fetchall():
                # Simple keyword matching
                if any(word.lower() in text.lower() for word in r[0].split()[:3] if len(word) > 3):
                    goals.append({"goal": r[0], "company": r[1], "status": r[2]})

    # Store enrichment
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO decision_context (decision_id, market_context, competitor_context, goal_alignment)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (decision_id) DO UPDATE SET
                    market_context = EXCLUDED.market_context,
                    competitor_context = EXCLUDED.competitor_context,
                    goal_alignment = EXCLUDED.goal_alignment,
                    enriched_at = NOW()
            """, (decision_id, json.dumps(market), json.dumps(competitors), json.dumps(goals)))
            conn.commit()

    # Schedule outcome checks (30/60/90 days)
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for days in [30, 60, 90]:
                check_date = (created + timedelta(days=days)).strftime("%Y-%m-%d")
                cur.execute("""
                    INSERT INTO decision_outcome_checks (decision_id, check_days, check_date)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (decision_id, days, check_date))
            conn.commit()

    log.info("decision_enriched", id=decision_id, market=len(market),
             competitors=len(competitors), goals=len(goals))

    return {
        "decision_id": decision_id,
        "market_context": market,
        "competitor_context": competitors,
        "goal_alignment": goals,
        "outcome_checks_scheduled": [30, 60, 90],
    }


def enrich_recent_decisions(hours: int = 24) -> dict[str, Any]:
    """Enrich all decisions from last N hours."""
    _ensure_tables()
    enriched = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id FROM decisions d
                LEFT JOIN decision_context dc ON dc.decision_id = d.id
                WHERE d.created_at > NOW() - INTERVAL '%s hours'
                AND dc.id IS NULL
            """, (hours,))
            for r in cur.fetchall():
                result = enrich_decision(r[0])
                enriched.append(result)

    return {"enriched": len(enriched), "details": enriched}


def check_due_outcomes() -> list[dict[str, Any]]:
    """Find decisions due for outcome check."""
    _ensure_tables()
    due = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT doc.id, doc.decision_id, doc.check_days, d.decision_text
                FROM decision_outcome_checks doc
                JOIN decisions d ON d.id = doc.decision_id
                WHERE doc.check_date <= CURRENT_DATE AND NOT doc.checked
                ORDER BY doc.check_date
            """)
            for r in cur.fetchall():
                due.append({
                    "check_id": r[0], "decision_id": r[1],
                    "check_days": r[2], "decision": r[3][:200],
                })
    return due
