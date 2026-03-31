"""
Optimization Planner — generate Gilbertus replacement plans per process.

For each discovered process: current state → target state → migration steps → ROI.
Prioritized by ROI / effort ratio.

Cron: part of process_discovery (Sunday weekly, after mining)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

OPTIMIZATION_PROMPT = """Jesteś konsultantem automatyzacji procesów dla firmy energetycznej.
Firma ma system AI "Gilbertus Albans" który potrafi: search archiwum, send email, create ticket,
schedule meeting, track commitments, analyze sentiment, monitor market, track competitors,
generate briefs, auto-propose actions, voice interface.

Dla każdego procesu zaproponuj plan optymalizacji:
- current_state: jak proces działa teraz (1-2 zdania)
- target_state: jak powinien działać z Gilbertusem (1-2 zdania)
- steps: konkretne kroki migracji (max 5, po polsku)
- time_savings_hours_monthly: szacunek oszczędności czasu (godziny/miesiąc)
- cost_savings_pln_monthly: szacunek oszczędności (PLN/miesiąc, 0 jeśli tylko czas)
- implementation_effort: low|medium|high
- risk: główne ryzyko (1 zdanie)
- priority_score: 1-100 (100 = rób natychmiast)

Respond ONLY with JSON array."""


_tables_ensured = False
_ensure_tables_lock = threading.Lock()

def _ensure_tables():
    global _tables_ensured
    with _ensure_tables_lock:
        if _tables_ensured:
            return
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS optimization_plans (
                        id BIGSERIAL PRIMARY KEY,
                        process_id BIGINT REFERENCES discovered_processes(id) ON DELETE CASCADE,
                        process_name TEXT,
                        current_state TEXT,
                        target_state TEXT,
                        steps JSONB DEFAULT '[]',
                        time_savings_hours NUMERIC DEFAULT 0,
                        cost_savings_pln NUMERIC DEFAULT 0,
                        implementation_effort TEXT DEFAULT 'medium',
                        risk TEXT,
                        priority_score INTEGER DEFAULT 50 CHECK (priority_score >= 0 AND priority_score <= 100),
                        status TEXT DEFAULT 'planned'
                            CHECK (status IN ('planned', 'in_progress', 'done', 'rejected')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_op_priority ON optimization_plans(priority_score DESC);
                """)
                conn.commit()
        _tables_ensured = True


def generate_plans() -> dict[str, Any]:
    """Generate optimization plans for discovered processes."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    # Get unplanned processes
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dp.id, dp.name, dp.description, dp.process_type, dp.frequency,
                       dp.participants, dp.steps, dp.tools_used, dp.automation_potential
                FROM discovered_processes dp
                LEFT JOIN optimization_plans op ON op.process_id = dp.id
                WHERE op.id IS NULL AND dp.status != 'archived'
                ORDER BY dp.automation_potential DESC
                LIMIT 10
            """)
            processes = cur.fetchall()

    if not processes:
        return {"message": "No unplanned processes found. Run process mining first."}

    # Build context
    process_text = []
    for p in processes:
        process_text.append(f"""
Process #{p[0]}: {p[1]}
Type: {p[3]}, Frequency: {p[4]}
Description: {p[2]}
Participants: {json.dumps(p[5]) if p[5] else 'unknown'}
Steps: {json.dumps(p[6]) if p[6] else 'unknown'}
Tools: {json.dumps(p[7]) if p[7] else 'unknown'}
Automation potential: {p[8]}%""")

    user_msg = f"Zaplanuj optymalizację dla {len(processes)} procesów:\n{'---'.join(process_text)}"

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        temperature=0.2,
        system=[{"type": "text", "text": OPTIMIZATION_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_MODEL, "optimization_planner", response.usage)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        plans = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("optimization.json_parse_failed")
        plans = []

    stored = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for i, plan in enumerate(plans):
                pid = processes[i][0] if i < len(processes) else None
                pname = processes[i][1] if i < len(processes) else plan.get("process_name", "")
                cur.execute("""
                    INSERT INTO optimization_plans
                    (process_id, process_name, current_state, target_state, steps,
                     time_savings_hours, cost_savings_pln, implementation_effort,
                     risk, priority_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    pid, pname,
                    plan.get("current_state", ""),
                    plan.get("target_state", ""),
                    json.dumps(plan.get("steps", [])),
                    plan.get("time_savings_hours_monthly", 0),
                    plan.get("cost_savings_pln_monthly", 0),
                    plan.get("implementation_effort", "medium"),
                    plan.get("risk", ""),
                    plan.get("priority_score", 50),
                ))
                stored += 1
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("optimization_plans_generated", count=stored, latency_ms=latency_ms)
    return {"plans_created": stored, "plans": plans, "latency_ms": latency_ms}


def get_optimization_dashboard() -> dict[str, Any]:
    """Get prioritized optimization plans."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT process_name, current_state, target_state, steps,
                       time_savings_hours, cost_savings_pln, implementation_effort,
                       risk, priority_score, status
                FROM optimization_plans
                ORDER BY priority_score DESC
            """)
            plans = [
                {"process": r[0], "current": r[1], "target": r[2],
                 "steps": r[3] if isinstance(r[3], list) else json.loads(r[3]) if r[3] else [],
                 "time_savings_h": float(r[4]) if r[4] else 0,
                 "cost_savings_pln": float(r[5]) if r[5] else 0,
                 "effort": r[6], "risk": r[7], "priority": r[8], "status": r[9]}
                for r in cur.fetchall()
            ]

            total_time = sum(p["time_savings_h"] for p in plans)
            total_cost = sum(p["cost_savings_pln"] for p in plans)

    return {
        "plans": plans,
        "total_plans": len(plans),
        "total_time_savings_hours": total_time,
        "total_cost_savings_pln": total_cost,
        "high_priority": [p for p in plans if p["priority"] >= 70],
    }
