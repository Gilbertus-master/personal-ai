"""
Business Line Discovery — auto-detect business lines from data.

Scans entities, events, and documents to cluster activity into business lines.
Dynamic — no hardcoded lines, discovers from patterns.

Cron: 0 16 * * 0 (Sunday 16:00 UTC / 17:00 CET)
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

DISCOVERY_PROMPT = """Jesteś analitykiem biznesowym. Na podstawie danych z firmy energetycznej (encje, zdarzenia, wzorce komunikacji) zidentyfikuj LINIE BIZNESOWE.

Linia biznesowa = odrębny strumień działalności z własnymi uczestnikami, procesami, narzędziami i przychodami.

Dla każdej linii podaj:
- name: krótka nazwa (po polsku, max 40 znaków)
- description: 2-3 zdania co to jest, kto jest zaangażowany, jak generuje wartość
- key_entities: główne osoby/firmy/produkty w tej linii
- estimated_importance: low/medium/high/critical
- signals_count: ile sygnałów wskazuje na tę linię

Respond ONLY with JSON array:
[{"name": "...", "description": "...", "key_entities": ["..."], "estimated_importance": "high", "signals_count": 15}]

Nie hardcoduj — bazuj WYŁĄCZNIE na dostarczonych danych. Szukaj klastrów: te same osoby + te same tematy = linia biznesowa."""


_tables_ensured = False
def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS business_lines (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    key_entities JSONB DEFAULT '[]',
                    importance TEXT DEFAULT 'medium'
                        CHECK (importance IN ('low', 'medium', 'high', 'critical')),
                    signals_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                        CHECK (status IN ('active', 'archived', 'merged')),
                    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS business_line_signals (
                    id BIGSERIAL PRIMARY KEY,
                    business_line_id BIGINT REFERENCES business_lines(id) ON DELETE CASCADE,
                    signal_source TEXT NOT NULL,
                    signal_ref_id BIGINT,
                    signal_text TEXT,
                    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_bl_status ON business_lines(status);
                CREATE INDEX IF NOT EXISTS idx_bls_bl ON business_line_signals(business_line_id);
            """)
            conn.commit()
    _tables_ensured = True


def _gather_discovery_data() -> str:
    """Gather entity clusters, event patterns, document topics for discovery."""
    parts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Top entities by mentions (last 90 days)
            cur.execute("""
                SELECT en.canonical_name, en.entity_type, COUNT(DISTINCT ee.event_id) as events,
                       COUNT(DISTINCT ce.chunk_id) as chunks
                FROM entities en
                LEFT JOIN event_entities ee ON ee.entity_id = en.id
                LEFT JOIN chunk_entities ce ON ce.entity_id = en.id
                WHERE en.entity_type IN ('person', 'company', 'product', 'concept')
                GROUP BY en.id, en.canonical_name, en.entity_type
                HAVING COUNT(DISTINCT ee.event_id) + COUNT(DISTINCT ce.chunk_id) >= 5
                ORDER BY COUNT(DISTINCT ee.event_id) + COUNT(DISTINCT ce.chunk_id) DESC LIMIT 50
            """)
            entities = cur.fetchall()
            parts.append("TOP ENCJE (≥5 wzmianek):")
            for e in entities:
                parts.append(f"  {e[0]} ({e[1]}): {e[2]} eventów, {e[3]} chunków")

            # Event type distribution (last 90 days)
            cur.execute("""
                SELECT event_type, COUNT(*) as cnt
                FROM events WHERE event_time > NOW() - INTERVAL '90 days'
                GROUP BY event_type ORDER BY cnt DESC
            """)
            parts.append("\nROZKŁAD EVENTÓW (90 dni):")
            for r in cur.fetchall():
                parts.append(f"  {r[0]}: {r[1]}")

            # Co-occurrence: which entities appear together in events
            cur.execute("""
                SELECT e1.canonical_name, e2.canonical_name, COUNT(*) as co_events
                FROM event_entities ee1
                JOIN event_entities ee2 ON ee1.event_id = ee2.event_id AND ee1.entity_id < ee2.entity_id
                JOIN entities e1 ON e1.id = ee1.entity_id
                JOIN entities e2 ON e2.id = ee2.entity_id
                WHERE e1.entity_type IN ('person', 'company')
                AND e2.entity_type IN ('person', 'company')
                GROUP BY e1.canonical_name, e2.canonical_name
                HAVING COUNT(*) >= 3
                ORDER BY co_events DESC LIMIT 30
            """)
            pairs = cur.fetchall()
            parts.append("\nCO-OCCURRENCE (osoby/firmy razem w eventach ≥3x):")
            for p in pairs:
                parts.append(f"  {p[0]} ↔ {p[1]}: {p[2]} wspólnych eventów")

            # Document source distribution
            cur.execute("""
                SELECT s.source_type, COUNT(d.id) as docs
                FROM documents d JOIN sources s ON d.source_id = s.id
                WHERE d.created_at > NOW() - INTERVAL '90 days'
                GROUP BY s.source_type ORDER BY docs DESC
            """)
            parts.append("\nŹRÓDŁA DOKUMENTÓW (90 dni):")
            for r in cur.fetchall():
                parts.append(f"  {r[0]}: {r[1]}")

            # Trade/business events with summaries
            cur.execute("""
                SELECT event_type, LEFT(summary, 150) as summary
                FROM events
                WHERE event_type IN ('trade', 'decision', 'commitment', 'meeting', 'deadline')
                AND event_time > NOW() - INTERVAL '30 days'
                ORDER BY event_time DESC LIMIT 30
            """)
            parts.append("\nOSTATNIE WYDARZENIA BIZNESOWE (30 dni):")
            for r in cur.fetchall():
                parts.append(f"  [{r[0]}] {r[1]}")

    return "\n".join(parts)


def discover_business_lines(force: bool = False) -> dict[str, Any]:
    """Run business line discovery from data patterns."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    if not force:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM business_lines WHERE status = 'active' AND updated_at > NOW() - INTERVAL '7 days'")
                if cur.fetchall()[0][0] > 0:
                    return get_business_lines()

    data = _gather_discovery_data()
    if len(data) < 200:
        return {"error": "Insufficient data for business line discovery"}

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=3000,
        temperature=0.2,
        system=[{"type": "text", "text": DISCOVERY_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": data}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "business_lines", response.usage)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        lines = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("business_lines.json_parse_failed")
        lines = []

    # Store discovered lines
    stored = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for bl in lines:
                cur.execute("""
                    INSERT INTO business_lines (name, description, key_entities, importance, signals_count)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (
                    bl.get("name", "Unknown"),
                    bl.get("description", ""),
                    json.dumps(bl.get("key_entities", [])),
                    bl.get("estimated_importance", "medium"),
                    bl.get("signals_count", 0),
                ))
                row = cur.fetchone()
                if row:
                    stored.append({"id": row[0], "name": bl["name"]})
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("business_lines_discovered", count=len(stored), latency_ms=latency_ms)

    return {"discovered": len(stored), "lines": stored + [{"name": bl["name"]} for bl in lines if bl["name"] not in [s["name"] for s in stored]], "latency_ms": latency_ms}


def get_business_lines(status: str = "active") -> dict[str, Any]:
    """Get discovered business lines."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, description, key_entities, importance, signals_count, status, discovered_at
                FROM business_lines WHERE status = %s
                ORDER BY CASE importance WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
            """, (status,))
            return {
                "business_lines": [
                    {"id": r[0], "name": r[1], "description": r[2],
                     "key_entities": r[3] if isinstance(r[3], list) else json.loads(r[3]) if r[3] else [],
                     "importance": r[4], "signals": r[5], "status": r[6],
                     "discovered_at": str(r[7])}
                    for r in cur.fetchall()
                ]
            }
