"""
Scenario Analyzer — "co jeśli?" impact simulation.

Create scenarios, analyze impact on 5 dimensions (revenue, costs, people,
operations, reputation), compare outcomes, auto-generate from risk signals.

Cron: 0 17 * * 0 (Sunday 17:00 UTC / 18:00 CET) — auto-scenario scan
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
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

DIMENSIONS = ["revenue", "costs", "people", "operations", "reputation"]

SCENARIO_ANALYSIS_PROMPT = """Jesteś strategicznym analitykiem biznesowym dla firmy z sektora energetycznego.
Firma: Respect Energy Holding (REH) + Respect Energy Fuels (REF) — trading energetyczny, OZE.

Przeanalizuj podany scenariusz i oceń jego wpływ na 5 wymiarów. Dla każdego wymiaru podaj:
- impact_description: krótki opis wpływu (1-2 zdania, po polsku)
- impact_value_pln: szacunkowy wpływ finansowy w PLN (pozytywny = szansa, negatywny = strata). 0 jeśli nie dotyczy.
- probability: prawdopodobieństwo (0.0-1.0)
- time_horizon: "1m" / "3m" / "6m" / "1y" / "3y"
- mitigation: zalecane działanie zapobiegawcze/korzystające (1 zdanie)

Respond ONLY with a JSON array of 5 objects:
[{"dimension": "revenue", "impact_description": "...", "impact_value_pln": -5000000, "probability": 0.6, "time_horizon": "6m", "mitigation": "..."},
 {"dimension": "costs", ...},
 {"dimension": "people", ...},
 {"dimension": "operations", ...},
 {"dimension": "reputation", ...}]"""


# ================================================================
# Schema
# ================================================================

def _ensure_tables() -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    scenario_type TEXT NOT NULL DEFAULT 'risk'
                        CHECK (scenario_type IN ('risk', 'opportunity', 'strategic')),
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'analyzed', 'archived')),
                    trigger_event TEXT,
                    created_by TEXT DEFAULT 'system',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    analyzed_at TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS scenario_outcomes (
                    id BIGSERIAL PRIMARY KEY,
                    scenario_id BIGINT NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    dimension TEXT NOT NULL
                        CHECK (dimension IN ('revenue', 'costs', 'people', 'operations', 'reputation')),
                    impact_description TEXT,
                    impact_value_pln NUMERIC,
                    probability NUMERIC(3,2) CHECK (probability >= 0 AND probability <= 1),
                    time_horizon TEXT,
                    mitigation TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_scenarios_status
                    ON scenarios(status);
                CREATE INDEX IF NOT EXISTS idx_scenario_outcomes_scenario
                    ON scenario_outcomes(scenario_id);
            """)
            conn.commit()
    log.info("scenario_analyzer.tables_ensured")


# ================================================================
# CRUD
# ================================================================

def create_scenario(
    title: str,
    description: str = "",
    scenario_type: str = "risk",
    trigger_event: str | None = None,
    created_by: str = "user",
) -> dict[str, Any]:
    """Create a new scenario for analysis."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scenarios (title, description, scenario_type, trigger_event, created_by)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (title, description, scenario_type, trigger_event, created_by),
            )
            sid = cur.fetchone()[0]
            conn.commit()
    log.info("scenario_created", id=sid, title=title)
    return {"id": sid, "title": title, "status": "draft"}


def list_scenarios(status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List scenarios with their outcome summaries."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            where = "WHERE s.status = %s" if status else "WHERE 1=1"
            params: list = [status] if status else []
            params.append(limit)
            cur.execute(f"""
                SELECT s.id, s.title, s.description, s.scenario_type, s.status,
                       s.trigger_event, s.created_by, s.created_at, s.analyzed_at,
                       COALESCE(SUM(o.impact_value_pln), 0) as total_impact,
                       COUNT(o.id) as outcome_count
                FROM scenarios s
                LEFT JOIN scenario_outcomes o ON o.scenario_id = s.id
                {where}
                GROUP BY s.id
                ORDER BY s.created_at DESC
                LIMIT %s
            """, params)
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "title": r[1], "description": r[2], "type": r[3],
            "status": r[4], "trigger": r[5], "created_by": r[6],
            "created_at": str(r[7]), "analyzed_at": str(r[8]) if r[8] else None,
            "total_impact_pln": float(r[9]) if r[9] else 0,
            "outcome_count": r[10],
        }
        for r in rows
    ]


# ================================================================
# Context gathering
# ================================================================

def _gather_context(scenario_title: str, scenario_description: str) -> str:
    """Gather relevant business context from DB for scenario analysis."""
    context_parts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Strategic goals
            cur.execute("""
                SELECT title, current_value, target_value, unit, status, deadline
                FROM strategic_goals WHERE status NOT IN ('cancelled', 'achieved')
                ORDER BY created_at DESC LIMIT 10
            """)
            goals = cur.fetchall()
            if goals:
                context_parts.append("CELE STRATEGICZNE:")
                for g in goals:
                    context_parts.append(
                        f"  - {g[0]}: {g[1]}/{g[2]} {g[3]} ({g[4]}) deadline: {g[5]}"
                    )

            # Financial metrics (last 3 months)
            cur.execute("""
                SELECT company, metric_type, value, period_start, period_end
                FROM financial_metrics
                WHERE period_end > NOW() - INTERVAL '3 months'
                ORDER BY period_end DESC LIMIT 15
            """)
            metrics = cur.fetchall()
            if metrics:
                context_parts.append("\nMETRYKI FINANSOWE (3 msc):")
                for m in metrics:
                    context_parts.append(f"  - {m[0]} {m[1]}: {m[2]} ({m[3]} — {m[4]})")

            # Active commitments count
            cur.execute("""
                SELECT status, COUNT(*) FROM commitments
                WHERE status IN ('open', 'overdue')
                GROUP BY status
            """)
            commits = cur.fetchall()
            if commits:
                context_parts.append("\nZOBOWIĄZANIA:")
                for c in commits:
                    context_parts.append(f"  - {c[0]}: {c[1]}")

            # Recent events related to scenario keywords
            keywords = (scenario_title + " " + scenario_description).split()[:5]
            if keywords:
                pattern = "|".join(k for k in keywords if len(k) > 3)
                if pattern:
                    cur.execute("""
                        SELECT event_type, summary, event_time
                        FROM events
                        WHERE summary ~* %s
                        AND event_time > NOW() - INTERVAL '30 days'
                        ORDER BY event_time DESC LIMIT 10
                    """, (pattern,))
                    evts = cur.fetchall()
                    if evts:
                        context_parts.append("\nOSTATNIE POWIĄZANE ZDARZENIA (30 dni):")
                        for e in evts:
                            context_parts.append(f"  - [{e[0]}] {e[1]} ({e[2]})")

    return "\n".join(context_parts) if context_parts else "Brak dodatkowego kontekstu w DB."


# ================================================================
# Analysis
# ================================================================

def analyze_scenario(scenario_id: int) -> dict[str, Any]:
    """Run LLM analysis on a scenario — produces 5-dimension outcomes."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, description, scenario_type FROM scenarios WHERE id = %s", (scenario_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"Scenario {scenario_id} not found"}

    sid, title, description, stype = row

    # Gather context
    context = _gather_context(title, description or "")

    user_msg = f"""SCENARIUSZ: {title}
TYP: {stype}
OPIS: {description or 'brak'}

KONTEKST BIZNESOWY:
{context}

Przeanalizuj wpływ tego scenariusza na 5 wymiarów."""

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=2000,
        temperature=0.2,
        system=[{"type": "text", "text": SCENARIO_ANALYSIS_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "scenario_analyzer", response.usage)

    raw_text = response.content[0].text.strip()
    # Strip markdown code blocks if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    try:
        outcomes = json.loads(raw_text)
    except json.JSONDecodeError:
        log.warning("scenario_analyzer.json_parse_failed", raw=raw_text[:200])
        return {"error": "LLM response was not valid JSON"}

    # Store outcomes
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Clear old outcomes
            cur.execute("DELETE FROM scenario_outcomes WHERE scenario_id = %s", (scenario_id,))

            for o in outcomes:
                cur.execute(
                    """INSERT INTO scenario_outcomes
                       (scenario_id, dimension, impact_description, impact_value_pln,
                        probability, time_horizon, mitigation)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        scenario_id,
                        o.get("dimension", "revenue"),
                        o.get("impact_description", ""),
                        o.get("impact_value_pln", 0),
                        o.get("probability", 0.5),
                        o.get("time_horizon", "6m"),
                        o.get("mitigation", ""),
                    ),
                )

            cur.execute(
                "UPDATE scenarios SET status = 'analyzed', analyzed_at = NOW() WHERE id = %s",
                (scenario_id,),
            )
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("scenario_analyzed", id=scenario_id, latency_ms=latency_ms)

    return {
        "scenario_id": scenario_id,
        "title": title,
        "outcomes": outcomes,
        "total_impact_pln": sum(o.get("impact_value_pln", 0) for o in outcomes),
        "latency_ms": latency_ms,
    }


def compare_scenarios(scenario_ids: list[int]) -> dict[str, Any]:
    """Compare multiple analyzed scenarios side-by-side."""
    _ensure_tables()
    results = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for sid in scenario_ids[:5]:  # max 5
                cur.execute(
                    "SELECT id, title, scenario_type, status FROM scenarios WHERE id = %s",
                    (sid,),
                )
                s = cur.fetchone()
                if not s:
                    continue

                cur.execute(
                    """SELECT dimension, impact_description, impact_value_pln,
                              probability, time_horizon, mitigation
                       FROM scenario_outcomes WHERE scenario_id = %s
                       ORDER BY dimension""",
                    (sid,),
                )
                outcomes = [
                    {
                        "dimension": r[0], "impact": r[1],
                        "value_pln": float(r[2]) if r[2] else 0,
                        "probability": float(r[3]) if r[3] else 0,
                        "horizon": r[4], "mitigation": r[5],
                    }
                    for r in cur.fetchall()
                ]

                total = sum(o["value_pln"] for o in outcomes)
                results.append({
                    "id": s[0], "title": s[1], "type": s[2], "status": s[3],
                    "outcomes": outcomes, "total_impact_pln": total,
                })

    # Rank by total impact
    results.sort(key=lambda r: r["total_impact_pln"])

    return {"scenarios": results, "count": len(results)}


# ================================================================
# Auto-scan: generate scenarios from risk signals
# ================================================================

def run_auto_scenarios() -> dict[str, Any]:
    """Cron entry: find new risks and auto-create + analyze scenarios."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)
    created = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Active predictive alerts not yet turned into scenarios
            cur.execute("""
                SELECT pa.id, pa.alert_type, pa.prediction, pa.probability
                FROM predictive_alerts pa
                WHERE pa.status = 'active'
                AND NOT EXISTS (
                    SELECT 1 FROM scenarios s
                    WHERE s.trigger_event = 'predictive_alert:' || pa.id::text
                )
                ORDER BY pa.probability DESC LIMIT 5
            """)
            alerts = cur.fetchall()

            for a in alerts:
                result = create_scenario(
                    title=f"[Auto] {a[1]}: {a[2][:80]}",
                    description=a[2],
                    scenario_type="risk",
                    trigger_event=f"predictive_alert:{a[0]}",
                    created_by="auto_scan",
                )
                analysis = analyze_scenario(result["id"])
                created.append({"source": "predictive_alert", "scenario_id": result["id"],
                                "title": result["title"], "total_impact": analysis.get("total_impact_pln", 0)})

            # 2. Goal risks (at_risk or behind goals)
            cur.execute("""
                SELECT id, title, status
                FROM strategic_goals
                WHERE status IN ('at_risk', 'behind')
                AND NOT EXISTS (
                    SELECT 1 FROM scenarios s
                    WHERE s.trigger_event = 'goal_risk:' || strategic_goals.id::text
                    AND s.created_at > NOW() - INTERVAL '7 days'
                )
                LIMIT 3
            """)
            goals = cur.fetchall()

            for g in goals:
                result = create_scenario(
                    title=f"[Auto] Cel zagrożony: {g[1][:60]}",
                    description=f"Cel strategiczny '{g[1]}' ma status '{g[2]}'. Analiza wpływu na biznes.",
                    scenario_type="risk",
                    trigger_event=f"goal_risk:{g[0]}",
                    created_by="auto_scan",
                )
                analysis = analyze_scenario(result["id"])
                created.append({"source": "goal_risk", "scenario_id": result["id"],
                                "title": result["title"], "total_impact": analysis.get("total_impact_pln", 0)})

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("auto_scenarios_done", created=len(created), latency_ms=latency_ms)

    return {"success": True, "scenarios_created": len(created), "details": created, "latency_ms": latency_ms}
