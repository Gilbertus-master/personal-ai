"""
Self-improving rules engine — Gilbertus creates rules from Sebastian's voice.

From recordings: "Z całych moich wypowiedzi musisz tworzyć zasady dla siebie."

Pipeline:
1. Scan new audio transcripts
2. Extract rules/principles/instructions directed at Gilbertus
3. Save to `self_rules` table
4. Apply rules in morning brief, evaluations, actions

Cron: runs after Plaud import (every 15 min, but only processes new transcripts)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

RULE_EXTRACTION_PROMPT = """You extract rules, principles, and instructions that Sebastian directs at Gilbertus (his AI mentat) from voice transcripts.

Look for:
- Direct instructions: "Gilbertusie, musisz...", "chcę żebyś...", "pamiętaj że..."
- Principles: "najważniejsze jest...", "zawsze powinno...", "nigdy nie..."
- Preferences: "wolę...", "lepiej żeby...", "nie chcę..."
- Corrections: "to było źle...", "następnym razem...", "popraw..."
- Goals: "cel to...", "dążymy do...", "priorytet..."

For each rule found, return:
{
  "rules": [
    {
      "rule_text": "the rule in Polish, as Sebastian stated it",
      "category": "instruction|principle|preference|correction|goal",
      "importance": "critical|high|medium|low",
      "context": "brief context of when/why Sebastian said this"
    }
  ]
}

If no rules found, return {"rules": []}.
Only extract CLEAR, ACTIONABLE rules. Skip vague statements or off-topic chat.
Return ONLY JSON."""


def scan_new_transcripts(hours: int = 1) -> list[dict[str, Any]]:
    """Get audio transcripts not yet processed for rules."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS self_rules (
                    id BIGSERIAL PRIMARY KEY,
                    rule_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    importance TEXT DEFAULT 'medium',
                    context TEXT,
                    source_chunk_id BIGINT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS self_rules_processed_chunks (
                    chunk_id BIGINT PRIMARY KEY
                )
            """)
            conn.commit()

            # Get unprocessed audio chunks
            cur.execute("""
                SELECT c.id, c.text
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                LEFT JOIN self_rules_processed_chunks p ON p.chunk_id = c.id
                WHERE s.source_type = 'audio_transcript'
                  AND p.chunk_id IS NULL
                  AND length(c.text) > 200
                ORDER BY d.created_at DESC
                LIMIT 20
            """)
            return [{"chunk_id": r[0], "text": r[1]} for r in cur.fetchall()]


def extract_rules_from_chunk(text: str) -> list[dict[str, Any]]:
    """Use LLM to extract rules from a transcript chunk."""
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0.1,
            system=[{"type": "text", "text": RULE_EXTRACTION_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:4000]}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "orchestrator.self_improving", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return data.get("rules", [])
    except Exception:
        return []


def save_rules(rules: list[dict], chunk_id: int) -> int:
    """Save extracted rules and mark chunk as processed."""
    saved = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for rule in rules:
                # Dedup: skip if very similar rule exists
                cur.execute("""
                    SELECT id FROM self_rules
                    WHERE rule_text = %s AND active = TRUE
                    LIMIT 1
                """, (rule.get("rule_text", ""),))
                if cur.fetchall():
                    continue

                cur.execute("""
                    INSERT INTO self_rules (rule_text, category, importance, context, source_chunk_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    rule.get("rule_text", ""),
                    rule.get("category", "instruction"),
                    rule.get("importance", "medium"),
                    rule.get("context", ""),
                    chunk_id,
                ))
                saved += 1

            # Mark chunk as processed
            cur.execute(
                "INSERT INTO self_rules_processed_chunks (chunk_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (chunk_id,),
            )
        conn.commit()
    return saved


def get_active_rules(category: str | None = None, importance: str | None = None) -> list[dict[str, Any]]:
    """Get active self-rules for application in other modules."""
    where = ["active = TRUE"]
    params = []
    if category:
        where.append("category = %s")
        params.append(category)
    if importance:
        where.append("importance = %s")
        params.append(importance)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, rule_text, category, importance, context, created_at
                FROM self_rules
                WHERE {' AND '.join(where)}
                ORDER BY
                    CASE importance WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    created_at DESC
            """, params)
            return [
                {"id": r[0], "rule": r[1], "category": r[2], "importance": r[3],
                 "context": r[4], "created": str(r[5])}
                for r in cur.fetchall()
            ]


def run_self_improvement() -> dict[str, Any]:
    """Full pipeline: scan → extract → save."""
    chunks = scan_new_transcripts(hours=24)
    if not chunks:
        return {"status": "no_new_transcripts", "processed": 0, "rules_found": 0}

    total_rules = 0
    processed = 0
    for chunk in chunks:
        rules = extract_rules_from_chunk(chunk["text"])
        if rules:
            saved = save_rules(rules, chunk["chunk_id"])
            total_rules += saved
        else:
            # Mark as processed even if no rules found
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO self_rules_processed_chunks (chunk_id) VALUES (%s) ON CONFLICT DO NOTHING",
                        (chunk["chunk_id"],),
                    )
                conn.commit()
        processed += 1

    return {"status": "ok", "processed": processed, "rules_found": total_rules}


if __name__ == "__main__":
    result = run_self_improvement()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    rules = get_active_rules()
    if rules:
        log.info("active_self_rules", count=len(rules))
        for r in rules:
            log.info("self_rule", importance=r['importance'], category=r['category'], rule=r['rule'])
