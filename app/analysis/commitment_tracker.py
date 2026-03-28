"""
Commitment Tracker — monitors commitment status, detects overdue items,
and uses LLM to find evidence of fulfillment.

Functions:
- check_overdue_commitments(): marks open commitments past deadline as 'overdue'
- check_fulfilled_commitments(): uses LLM to find fulfillment evidence in recent data
- get_commitment_summary(): returns per-person stats
- get_open_commitments(): returns open commitments ordered by deadline
- run_commitment_check(): full pipeline
"""
from __future__ import annotations

import json
import os
from typing import Any

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)


FULFILLMENT_PROMPT = """You check whether commitments have been fulfilled based on recent communications.

For each commitment, analyze the recent events/chunks and determine:
- "fulfilled": clear evidence the commitment was completed
- "likely_fulfilled": strong indication but not 100% confirmed
- "no_evidence": no evidence of fulfillment found

Return JSON array:
[{"commitment_id": N, "status": "fulfilled|likely_fulfilled|no_evidence", "evidence": "brief description of evidence or null"}]

Be strict — only mark as fulfilled if there is concrete evidence. Respond ONLY with JSON array."""


def check_overdue_commitments() -> int:
    """Find open commitments past deadline, mark as 'overdue'. Returns count updated."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE commitments
                SET status = 'overdue', updated_at = NOW()
                WHERE status = 'open'
                  AND deadline IS NOT NULL
                  AND deadline < NOW()
                RETURNING id
            """)
            updated_ids = [r[0] for r in cur.fetchall()]
        conn.commit()

    if updated_ids:
        log.info("overdue_commitments_marked", count=len(updated_ids), ids=updated_ids)
    return len(updated_ids)


def check_fulfilled_commitments(hours: int = 24) -> list[dict[str, Any]]:
    """Use LLM to check if open commitments have been fulfilled based on recent data."""
    # Fetch open commitments
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, person_name, commitment_text, deadline, status
                FROM commitments
                WHERE status IN ('open', 'overdue')
                ORDER BY deadline ASC NULLS LAST
                LIMIT 30
            """)
            commitments = [
                {
                    "id": r[0],
                    "person_name": r[1],
                    "commitment_text": r[2],
                    "deadline": str(r[3]) if r[3] else None,
                    "status": r[4],
                }
                for r in cur.fetchall()
            ]

    if not commitments:
        return []

    # Fetch recent events and chunks for context
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.event_type, e.summary, e.event_time
                FROM events e
                WHERE e.created_at > NOW() - INTERVAL '%s hours'
                   OR e.event_time > NOW() - INTERVAL '%s hours'
                ORDER BY e.created_at DESC
                LIMIT 80
            """, (hours, hours))
            events = [
                {"event_id": r[0], "type": r[1], "summary": r[2], "time": str(r[3]) if r[3] else None}
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT c.id, LEFT(c.text, 400)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.created_at > NOW() - INTERVAL '%s hours'
                  AND length(c.text) > 100
                ORDER BY d.created_at DESC
                LIMIT 40
            """, (hours,))
            chunks = [{"chunk_id": r[0], "text": r[1]} for r in cur.fetchall()]

    if not events and not chunks:
        log.info("no_recent_data_for_fulfillment_check")
        return []

    # Build context for LLM
    ctx_parts = ["=== OPEN COMMITMENTS ==="]
    for c in commitments:
        ctx_parts.append(
            f"[#{c['id']}] {c['person_name']}: {c['commitment_text']} "
            f"(deadline: {c['deadline'] or 'none'}, status: {c['status']})"
        )

    ctx_parts.append("\n=== RECENT EVENTS ===")
    for ev in events[:50]:
        ctx_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    ctx_parts.append("\n=== RECENT COMMUNICATIONS ===")
    for ch in chunks[:25]:
        ctx_parts.append(f"[chunk {ch['chunk_id']}] {ch['text'][:300]}")

    context = "\n".join(ctx_parts)
    if len(context) > 15000:
        context = context[:15000] + "\n[truncated]"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.1,
            system=[{"type": "text", "text": FULFILLMENT_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.commitment_tracker", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        results = json.loads(text)
    except Exception as e:
        log.error("fulfillment_check_error", error=str(e))
        return []

    # Update fulfilled commitments
    fulfilled = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for item in results:
                if item.get("status") == "fulfilled":
                    cur.execute(
                        """
                        UPDATE commitments
                        SET status = 'fulfilled', fulfilled_evidence = %s, updated_at = NOW()
                        WHERE id = %s AND status IN ('open', 'overdue')
                        """,
                        (item.get("evidence", "LLM-detected fulfillment"), item["commitment_id"]),
                    )
                    fulfilled.append(item)
        conn.commit()

    if fulfilled:
        log.info("commitments_fulfilled", count=len(fulfilled))
    return fulfilled


def get_commitment_summary(person_name: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    """Return commitment stats per person. Optionally filter by person name and/or status."""
    where_clauses = []
    params: list = []
    if person_name:
        where_clauses.append("LOWER(person_name) = LOWER(%s)")
        params.append(person_name)
    if status:
        where_clauses.append("status = %s")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"""
        SELECT person_name,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE status = 'open') as open,
               COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled,
               COUNT(*) FILTER (WHERE status = 'broken') as broken,
               COUNT(*) FILTER (WHERE status = 'overdue') as overdue,
               COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled
        FROM commitments
        {where_sql}
        GROUP BY person_name
        ORDER BY total DESC
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "person_name": r[0],
            "total": r[1],
            "open": r[2],
            "fulfilled": r[3],
            "broken": r[4],
            "overdue": r[5],
            "cancelled": r[6],
        }
        for r in rows
    ]


def get_open_commitments(limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
    """Return commitments ordered by deadline (soonest first). Defaults to open+overdue."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute("""
                    SELECT id, person_name, commitment_text, deadline, status, created_at
                    FROM commitments
                    WHERE status = %s
                    ORDER BY deadline ASC NULLS LAST, created_at ASC
                    LIMIT %s
                """, (status, limit))
            else:
                cur.execute("""
                    SELECT id, person_name, commitment_text, deadline, status, created_at
                    FROM commitments
                    WHERE status IN ('open', 'overdue')
                    ORDER BY deadline ASC NULLS LAST, created_at ASC
                    LIMIT %s
                """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "person_name": r[1],
            "commitment_text": r[2],
            "deadline": str(r[3]) if r[3] else None,
            "status": r[4],
            "created_at": str(r[5]),
        }
        for r in rows
    ]


def run_commitment_check(hours: int = 24) -> dict[str, Any]:
    """Full commitment check pipeline: overdue detection + fulfillment check + summary."""
    log.info("commitment_check_start", hours=hours)

    overdue_count = check_overdue_commitments()
    fulfilled = check_fulfilled_commitments(hours=hours)
    summary = get_commitment_summary()
    open_commitments = get_open_commitments(limit=10)

    result = {
        "status": "ok",
        "overdue_marked": overdue_count,
        "fulfilled_detected": len(fulfilled),
        "summary_by_person": summary,
        "top_open_commitments": open_commitments,
    }

    log.info("commitment_check_complete", overdue=overdue_count, fulfilled=len(fulfilled))
    return result


if __name__ == "__main__":
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    result = run_commitment_check(hours=hours)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
