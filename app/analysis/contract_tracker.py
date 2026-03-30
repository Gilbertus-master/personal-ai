"""
Contract & Deadline Intelligence — extracts contracts from documents/emails,
tracks expiry dates, sends alerts before deadlines.

Functions:
- scan_for_contracts(hours): scan recent chunks for contract info using LLM
- check_expiring_contracts(days_ahead): find contracts expiring within N days
- run_contract_check(): main pipeline: scan + check expirations + alerts
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
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


CONTRACT_PROMPT = """You analyze text chunks for contract/agreement information.

For each contract or agreement found, extract:
- title: short descriptive title
- parties: list of parties involved
- contract_type: one of [supply, service, employment, lease, NDA, partnership, trade, other]
- value_pln: estimated value in PLN (null if unknown)
- start_date: YYYY-MM-DD or null
- end_date: YYYY-MM-DD or null
- renewal_date: YYYY-MM-DD or null (auto-renewal date if mentioned)
- payment_terms: brief summary of payment terms or null
- key_terms: brief summary of key terms/conditions

Return JSON array of contracts found. If no contracts found, return [].
Respond ONLY with JSON array. Be precise with dates — only extract if explicitly stated."""


_tables_ensured = False
def _ensure_tables() -> None:
    """Create contracts table if it doesn't exist."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contracts (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    parties TEXT[] NOT NULL,
                    contract_type TEXT,
                    value_pln NUMERIC,
                    start_date DATE,
                    end_date DATE,
                    renewal_date DATE,
                    payment_terms TEXT,
                    key_terms TEXT,
                    source_chunk_ids BIGINT[],
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'expiring', 'expired', 'renewed')),
                    alert_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_contracts_end_date
                    ON contracts(end_date) WHERE status = 'active';
                CREATE INDEX IF NOT EXISTS idx_contracts_status
                    ON contracts(status);
            """)
        conn.commit()
    log.debug("contracts_table_ensured")
    _tables_ensured = True


def scan_for_contracts(hours: int = 24) -> list[dict[str, Any]]:
    """Scan recent chunks for contract-related content using LLM."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find chunks that mention contract-related keywords
            cur.execute("""
                SELECT c.id, LEFT(c.text, 800)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.created_at > NOW() - INTERVAL '%s hours'
                  AND length(c.text) > 100
                  AND (
                      c.text ILIKE '%%umow%%'
                      OR c.text ILIKE '%%kontrak%%'
                      OR c.text ILIKE '%%agreement%%'
                      OR c.text ILIKE '%%contract%%'
                      OR c.text ILIKE '%%termin%%płat%%'
                      OR c.text ILIKE '%%wygasa%%'
                      OR c.text ILIKE '%%obowiązuje do%%'
                      OR c.text ILIKE '%%ważn%%do%%'
                      OR c.text ILIKE '%%expir%%'
                      OR c.text ILIKE '%%renewal%%'
                  )
                ORDER BY d.created_at DESC
                LIMIT 40
            """, (hours,))
            chunks = [{"chunk_id": r[0], "text": r[1]} for r in cur.fetchall()]

    if not chunks:
        log.info("no_contract_chunks_found", hours=hours)
        return []

    # Build context for LLM
    ctx_parts = ["=== CHUNKS TO ANALYZE FOR CONTRACTS ==="]
    for ch in chunks:
        ctx_parts.append(f"[chunk {ch['chunk_id']}] {ch['text']}")

    context = "\n\n".join(ctx_parts)
    if len(context) > 15000:
        context = context[:15000] + "\n[truncated]"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=3000,
            temperature=0.1,
            system=[{"type": "text", "text": CONTRACT_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.contract_tracker", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        contracts = json.loads(text)
    except Exception as e:
        log.error("contract_scan_llm_error", error=str(e))
        return []

    # Store discovered contracts
    stored = []
    chunk_ids = [ch["chunk_id"] for ch in chunks]
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for c in contracts:
                parties = c.get("parties", [])
                if not parties or not c.get("title"):
                    continue

                # Check for duplicate by title + parties overlap
                cur.execute("""
                    SELECT id FROM contracts
                    WHERE LOWER(title) = LOWER(%s)
                      AND parties && %s
                    LIMIT 1
                """, (c["title"], parties))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO contracts (
                        title, parties, contract_type, value_pln,
                        start_date, end_date, renewal_date,
                        payment_terms, key_terms, source_chunk_ids
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    c["title"],
                    parties,
                    c.get("contract_type"),
                    c.get("value_pln"),
                    c.get("start_date"),
                    c.get("end_date"),
                    c.get("renewal_date"),
                    c.get("payment_terms"),
                    c.get("key_terms"),
                    chunk_ids,
                ))
                row = cur.fetchone()
                if row:
                    c["id"] = row[0]
                    stored.append(c)
        conn.commit()

    log.info("contracts_scanned", chunks_analyzed=len(chunks), contracts_found=len(stored))
    return stored


def check_expiring_contracts(days_ahead: int = 30) -> list[dict[str, Any]]:
    """Find contracts expiring within N days."""
    _ensure_tables()

    threshold = date.today() + timedelta(days=days_ahead)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Mark expired contracts
            cur.execute("""
                UPDATE contracts
                SET status = 'expired', updated_at = NOW()
                WHERE status = 'active'
                  AND end_date IS NOT NULL
                  AND end_date < CURRENT_DATE
                RETURNING id
            """)
            expired_ids = [r[0] for r in cur.fetchall()]
            if expired_ids:
                log.info("contracts_marked_expired", count=len(expired_ids))

            # Mark expiring contracts
            cur.execute("""
                UPDATE contracts
                SET status = 'expiring', updated_at = NOW()
                WHERE status = 'active'
                  AND end_date IS NOT NULL
                  AND end_date <= %s
                  AND end_date >= CURRENT_DATE
                RETURNING id
            """, (threshold,))
            expiring_ids = [r[0] for r in cur.fetchall()]
            if expiring_ids:
                log.info("contracts_marked_expiring", count=len(expiring_ids))

            # Fetch expiring contracts for alerts
            cur.execute("""
                SELECT id, title, parties, contract_type, value_pln,
                       end_date, renewal_date, key_terms, status
                FROM contracts
                WHERE status IN ('expiring', 'active')
                  AND end_date IS NOT NULL
                  AND end_date <= %s
                  AND end_date >= CURRENT_DATE
                ORDER BY end_date ASC
            """, (threshold,))
            rows = cur.fetchall()
        conn.commit()

    return [
        {
            "id": r[0],
            "title": r[1],
            "parties": r[2],
            "contract_type": r[3],
            "value_pln": float(r[4]) if r[4] else None,
            "end_date": str(r[5]) if r[5] else None,
            "renewal_date": str(r[6]) if r[6] else None,
            "key_terms": r[7],
            "status": r[8],
            "days_until_expiry": (r[5] - date.today()).days if r[5] else None,
        }
        for r in rows
    ]


def _send_contract_alerts(expiring: list[dict[str, Any]]) -> int:
    """Send WhatsApp alerts for contracts at 30, 14, and 7 day thresholds."""
    alert_thresholds = [30, 14, 7]
    alerts_sent = 0

    for contract in expiring:
        days_left = contract.get("days_until_expiry")
        if days_left is None:
            continue

        # Check if this threshold warrants an alert
        should_alert = any(
            days_left <= threshold and days_left > (threshold - 3)
            for threshold in alert_thresholds
        )
        if not should_alert:
            continue

        # Check if alert already sent
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alert_sent FROM contracts WHERE id = %s",
                    (contract["id"],)
                )
                row = cur.fetchone()
                if row and row[0]:
                    continue

        # Build alert message
        value_str = f" ({contract['value_pln']:,.0f} PLN)" if contract.get("value_pln") else ""
        msg = (
            f"[KONTRAKT] {contract['title']}{value_str} "
            f"wygasa za {days_left} dni ({contract['end_date']}). "
            f"Strony: {', '.join(contract.get('parties', []))}."
        )

        try:
            from app.orchestrator.communication import _send_whatsapp_to
            _send_whatsapp_to("sebastian", msg)
            alerts_sent += 1

            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE contracts SET alert_sent = TRUE, updated_at = NOW() WHERE id = %s",
                        (contract["id"],)
                    )
                conn.commit()
        except Exception as e:
            log.warning("contract_alert_send_failed", contract_id=contract["id"], error=str(e))

    return alerts_sent


def run_contract_check(hours: int = 24, days_ahead: int = 30) -> dict[str, Any]:
    """Main pipeline: scan new data + check expirations + send alerts."""
    log.info("contract_check_start", hours=hours, days_ahead=days_ahead)

    new_contracts = scan_for_contracts(hours=hours)
    expiring = check_expiring_contracts(days_ahead=days_ahead)
    alerts_sent = _send_contract_alerts(expiring)

    # Summary stats
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*)
                FROM contracts
                GROUP BY status
                ORDER BY status
            """)
            status_counts = {r[0]: r[1] for r in cur.fetchall()}

    result = {
        "status": "ok",
        "new_contracts_found": len(new_contracts),
        "expiring_contracts": len(expiring),
        "alerts_sent": alerts_sent,
        "status_counts": status_counts,
        "expiring_details": expiring[:10],
    }

    log.info("contract_check_complete",
             new=len(new_contracts), expiring=len(expiring), alerts=alerts_sent)
    return result


if __name__ == "__main__":
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    result = run_contract_check(hours=hours)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
