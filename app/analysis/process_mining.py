"""
Process Mining — discover recurring processes from communication patterns.

Identifies: decision flows, approval chains, reporting cycles, trading workflows.
Dynamic — discovers patterns, doesn't hardcode processes.

Cron: part of process_discovery (Sunday weekly)
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

PROCESS_PROMPT = """Jesteś ekspertem process mining. Na podstawie wzorców komunikacji i zdarzeń z firmy energetycznej zidentyfikuj POWTARZALNE PROCESY BIZNESOWE.

Proces = sekwencja kroków wykonywanych regularnie, angażujących konkretne osoby i narzędzia.

Dla każdego procesu:
- name: nazwa procesu (po polsku, max 50 znaków)
- description: co ten proces robi (2-3 zdania)
- process_type: decision|approval|reporting|trading|compliance|communication|operational
- frequency: daily|weekly|monthly|quarterly|ad_hoc
- participants: kto jest zaangażowany (role, nie nazwiska jeśli się powtarza)
- steps: lista kroków procesu (max 5)
- tools_used: jakie narzędzia/aplikacje są używane
- automation_potential: 0-100 (100 = w pełni automatyzowalny przez AI)
- automation_notes: co konkretnie można zautomatyzować

Respond ONLY with JSON array. Szukaj WZORCÓW, nie pojedynczych zdarzeń."""


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS discovered_processes (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    business_line_id BIGINT REFERENCES business_lines(id) ON DELETE SET NULL,
                    process_type TEXT,
                    frequency TEXT,
                    participants JSONB DEFAULT '[]',
                    steps JSONB DEFAULT '[]',
                    tools_used JSONB DEFAULT '[]',
                    automation_potential INTEGER DEFAULT 50 CHECK (automation_potential >= 0 AND automation_potential <= 100),
                    automation_notes TEXT,
                    status TEXT DEFAULT 'discovered' CHECK (status IN ('discovered', 'confirmed', 'automated', 'archived')),
                    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_dp_type ON discovered_processes(process_type);
                CREATE INDEX IF NOT EXISTS idx_dp_automation ON discovered_processes(automation_potential DESC);
            """)
            conn.commit()


def _gather_process_data() -> str:
    """Gather patterns for process mining."""
    parts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Recurring meeting patterns
            cur.execute("""
                SELECT LEFT(summary, 100), COUNT(*) as occurrences,
                       COUNT(DISTINCT DATE(event_time)) as distinct_days
                FROM events
                WHERE event_type = 'meeting' AND event_time > NOW() - INTERVAL '90 days'
                GROUP BY LEFT(summary, 100)
                HAVING COUNT(*) >= 2
                ORDER BY occurrences DESC LIMIT 20
            """)
            parts.append("POWTARZAJĄCE SIĘ SPOTKANIA:")
            for r in cur.fetchall():
                parts.append(f"  ({r[1]}x, {r[2]} dni): {r[0]}")

            # Decision→commitment→deadline chains
            cur.execute("""
                SELECT e1.event_type || ' → ' || e2.event_type as chain,
                       COUNT(*) as occurrences
                FROM events e1
                JOIN events e2 ON e2.event_time > e1.event_time
                    AND e2.event_time < e1.event_time + INTERVAL '7 days'
                JOIN event_entities ee1 ON ee1.event_id = e1.id
                JOIN event_entities ee2 ON ee2.event_id = e2.id AND ee2.entity_id = ee1.entity_id
                WHERE e1.event_type IN ('decision', 'commitment', 'meeting')
                AND e2.event_type IN ('commitment', 'deadline', 'task_assignment', 'approval')
                AND e1.event_time > NOW() - INTERVAL '90 days'
                GROUP BY chain
                HAVING COUNT(*) >= 3
                ORDER BY occurrences DESC LIMIT 15
            """)
            parts.append("\nŁAŃCUCHY ZDARZEŃ (A→B w 7 dni, same osoby, ≥3x):")
            for r in cur.fetchall():
                parts.append(f"  {r[0]}: {r[1]}x")

            # Communication patterns by person pairs
            cur.execute("""
                SELECT e1.canonical_name || ' → ' || e2.canonical_name as pair,
                       COUNT(DISTINCT ee1.event_id) as interactions
                FROM event_entities ee1
                JOIN event_entities ee2 ON ee1.event_id = ee2.event_id AND ee1.entity_id < ee2.entity_id
                JOIN entities e1 ON e1.id = ee1.entity_id AND e1.entity_type = 'person'
                JOIN entities e2 ON e2.id = ee2.entity_id AND e2.entity_type = 'person'
                JOIN events ev ON ev.id = ee1.event_id AND ev.event_time > NOW() - INTERVAL '30 days'
                GROUP BY pair
                HAVING COUNT(DISTINCT ee1.event_id) >= 5
                ORDER BY interactions DESC LIMIT 15
            """)
            parts.append("\nNAJCZĘSTSZE PARY KOMUNIKACYJNE (30 dni, ≥5 interakcji):")
            for r in cur.fetchall():
                parts.append(f"  {r[0]}: {r[1]} interakcji")

            # Document flow patterns (email subjects with similar patterns)
            cur.execute("""
                SELECT LEFT(d.title, 60), COUNT(*) as cnt
                FROM documents d JOIN sources s ON d.source_id = s.id
                WHERE s.source_type = 'email' AND d.created_at > NOW() - INTERVAL '30 days'
                GROUP BY LEFT(d.title, 60)
                HAVING COUNT(*) >= 3
                ORDER BY cnt DESC LIMIT 15
            """)
            parts.append("\nPOWTARZAJĄCE SIĘ EMAILE (30 dni, ≥3x):")
            for r in cur.fetchall():
                parts.append(f"  ({r[1]}x) {r[0]}")

    return "\n".join(parts)


def mine_processes(force: bool = False) -> dict[str, Any]:
    """Run process mining on communication/event patterns."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    data = _gather_process_data()
    if len(data) < 200:
        return {"error": "Insufficient data for process mining"}

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=3000,
        temperature=0.2,
        system=[{"type": "text", "text": PROCESS_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": data}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "process_mining", response.usage)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        processes = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("process_mining.json_parse_failed")
        processes = []

    stored = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for p in processes:
                cur.execute("""
                    INSERT INTO discovered_processes
                    (name, description, process_type, frequency, participants, steps,
                     tools_used, automation_potential, automation_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    p.get("name", ""),
                    p.get("description", ""),
                    p.get("process_type", "operational"),
                    p.get("frequency", "ad_hoc"),
                    json.dumps(p.get("participants", [])),
                    json.dumps(p.get("steps", [])),
                    json.dumps(p.get("tools_used", [])),
                    p.get("automation_potential", 50),
                    p.get("automation_notes", ""),
                ))
                stored += 1
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("processes_mined", count=stored, latency_ms=latency_ms)
    return {"processes_discovered": stored, "processes": processes, "latency_ms": latency_ms}


def get_processes(process_type: str | None = None) -> list[dict]:
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if process_type:
                cur.execute("SELECT * FROM discovered_processes WHERE process_type = %s ORDER BY automation_potential DESC", (process_type,))
            else:
                cur.execute("SELECT * FROM discovered_processes ORDER BY automation_potential DESC")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
