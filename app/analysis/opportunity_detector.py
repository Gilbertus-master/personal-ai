"""
Opportunity Detector — Continuous Intelligence Engine.

Scans new events/chunks every 2h and classifies them:
- OPTIMIZATION (cost reduction, process improvement)
- OPPORTUNITY (revenue, new client, new deal)
- RISK (escalation, conflict, blocker, deadline miss)
- NEW_BUSINESS (new market, product, partner)

For each: estimates PLN value + effort hours + confidence.
Ranks by ROI. Auto-drafts actions. Notifies Sebastian.

Cron: */120 * * * * (every 2h)
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

DETECTOR_PROMPT = """You analyze business events and communications to find actionable opportunities.

For each item, classify as ONE of:
- optimization: cost reduction or process improvement
- opportunity: revenue generation, new client, deal expansion
- risk: escalation, conflict, blocker, missed deadline, compliance issue
- new_business: new market, product, partnership, acquisition target
- none: no actionable insight

For non-none items, estimate:
- value_pln: estimated annual value in PLN (cost saved or revenue generated)
- effort_hours: estimated hours to implement/address
- confidence: 0.0-1.0

Return JSON array:
[{"type": "optimization|opportunity|risk|new_business|none", "description": "...", "value_pln": N, "effort_hours": N, "confidence": 0.X, "event_ids": [...], "chunk_ids": [...]}]

Be specific. Use real numbers. If unsure, set confidence low. Skip items with no clear business value.
Respond ONLY with JSON array."""


def scan_recent_data(hours: int = 2) -> list[dict[str, Any]]:
    """Fetch recent events and chunks for analysis."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Recent events with entities
            cur.execute("""
                SELECT e.id, e.event_type, e.summary, e.event_time,
                       COALESCE(string_agg(DISTINCT en.canonical_name, ', '), '') as entities
                FROM events e
                LEFT JOIN event_entities ee ON ee.event_id = e.id
                LEFT JOIN entities en ON en.id = ee.entity_id
                WHERE (e.created_at > NOW() - INTERVAL '%s hours'
                       OR e.event_time > NOW() - INTERVAL '%s hours')
                GROUP BY e.id, e.event_type, e.summary, e.event_time
                ORDER BY e.created_at DESC
                LIMIT 100
            """, (hours, hours))
            events = [
                {"event_id": r[0], "type": r[1], "summary": r[2],
                 "time": str(r[3]) if r[3] else None, "entities": r[4]}
                for r in cur.fetchall()
            ]

            # Recent high-value chunks (emails, Teams with business content)
            cur.execute("""
                SELECT c.id, LEFT(c.text, 500), s.source_type
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE d.created_at > NOW() - INTERVAL '%s hours'
                  AND s.source_type IN ('email', 'email_attachment', 'teams', 'audio_transcript')
                  AND length(c.text) > 200
                ORDER BY d.created_at DESC
                LIMIT 50
            """, (hours,))
            chunks = [
                {"chunk_id": r[0], "text": r[1], "source": r[2]}
                for r in cur.fetchall()
            ]

    return events, chunks


def classify_opportunities(events: list, chunks: list) -> list[dict[str, Any]]:
    """Use LLM to classify events/chunks into opportunity types."""
    if not events and not chunks:
        return []

    # Build context
    ctx_parts = ["=== RECENT EVENTS ==="]
    for ev in events[:50]:
        ctx_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']} (entities: {ev['entities']})")

    ctx_parts.append("\n=== RECENT COMMUNICATIONS ===")
    for ch in chunks[:30]:
        ctx_parts.append(f"[{ch['source']}] {ch['text'][:300]}")

    context = "\n".join(ctx_parts)
    if len(context) > 15000:
        context = context[:15000] + "\n[truncated]"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.1,
            system=[{"type": "text", "text": DETECTOR_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.opportunity_detector", response.usage)

        text = response.content[0].text.strip()
        # Parse JSON
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        log.info("Classification error: {e}")
        return []


def save_opportunities(items: list[dict[str, Any]]) -> list[int]:
    """Save classified opportunities to DB."""
    saved_ids = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                if item.get("type") == "none":
                    continue

                # Dedup: skip if similar opportunity exists in last 24h
                cur.execute("""
                    SELECT id FROM opportunities
                    WHERE opportunity_type = %s
                      AND description = %s
                      AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, (item["type"], item.get("description", "")))
                if cur.fetchall():
                    continue

                cur.execute("""
                    INSERT INTO opportunities (opportunity_type, description, estimated_value_pln,
                        estimated_effort_hours, confidence, source_event_ids, source_chunk_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """, (
                    item["type"],
                    item.get("description", ""),
                    item.get("value_pln", 0),
                    item.get("effort_hours", 0),
                    item.get("confidence", 0.5),
                    [int(x) for x in item.get("event_ids", []) if str(x).isdigit()],
                    [int(x) for x in item.get("chunk_ids", []) if str(x).isdigit()],
                ))
                saved_ids.append(cur.fetchall()[0][0])
        conn.commit()
    return saved_ids


def notify_top_opportunities(limit: int = 5) -> str:
    """Get top new opportunities for WhatsApp notification."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, opportunity_type, description, estimated_value_pln,
                       estimated_effort_hours, roi_score, confidence
                FROM opportunities
                WHERE status = 'new' AND created_at > NOW() - INTERVAL '4 hours'
                ORDER BY roi_score DESC NULLS LAST
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    if not rows:
        return ""

    total_value = sum(r[3] or 0 for r in rows)
    lines = [f"\U0001f4a1 Znalaz\u0142em {len(rows)} nowych szans (warto\u015b\u0107: ~{total_value:,.0f} PLN/rok):"]
    for r in rows:
        oid, otype, desc, value, effort, roi, conf = r
        emoji = {"optimization": "\u2699\ufe0f", "opportunity": "\U0001f4b0", "risk": "\u26a0\ufe0f", "new_business": "\U0001f680"}.get(otype, "\U0001f4a1")
        lines.append(f"\n{emoji} #{oid} [{otype}] {desc[:150]}")
        lines.append(f"   Warto\u015b\u0107: ~{value:,.0f} PLN | Effort: {effort:.0f}h | ROI: {roi:,.0f} PLN/h | Conf: {conf:.0%}")

    lines.append(f"\nOdpowiedz: 'tak #{rows[0][0]}' aby zatwierdzi\u0107 najlepsz\u0105 opcj\u0119.")
    return "\n".join(lines)


def run_opportunity_scan(hours: int = 2, notify: bool = True) -> dict[str, Any]:
    """Full scan pipeline: fetch → classify → save → notify."""
    log.info("Opportunity scan (last {hours}h)...")

    events, chunks = scan_recent_data(hours)
    log.info("Data: {len(events)} events, {len(chunks)} chunks")

    if not events and not chunks:
        return {"status": "no_data", "events": 0, "chunks": 0}

    items = classify_opportunities(events, chunks)
    actionable = [i for i in items if i.get("type") != "none"]
    log.info("Classified: {len(items)} total, {len(actionable)} actionable")

    saved_ids = save_opportunities(actionable)
    log.info("Saved: {len(saved_ids)} new opportunities")

    notification = ""
    # Auto-draft actions for top opportunities
    if saved_ids:
        try:
            from app.orchestrator.auto_draft import run_auto_drafts
            drafts = run_auto_drafts()
            log.info("auto_drafted", count=len(drafts))
        except Exception:
            log.info("Auto-draft failed: {e}")

    if notify and saved_ids:
        notification = notify_top_opportunities()
        if notification:
            try:
                import subprocess
                subprocess.run(
                    [os.getenv("OPENCLAW_BIN", "openclaw"), "message", "send",
                     "--channel", "whatsapp", "--target", os.getenv("WA_TARGET", "+48505441635"),
                     "--message", notification],
                    capture_output=True, text=True, timeout=30,
                )
                log.info("WhatsApp notification sent")
            except Exception:
                log.info("WhatsApp send failed")

    return {
        "status": "ok",
        "events_scanned": len(events),
        "chunks_scanned": len(chunks),
        "opportunities_found": len(actionable),
        "opportunities_saved": len(saved_ids),
        "notification": notification[:200] if notification else None,
    }


if __name__ == "__main__":
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    result = run_opportunity_scan(hours=hours)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
