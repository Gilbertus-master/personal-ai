"""
Compliance Manager AI — Employee communication and culture analysis.

Weekly per person:
1. Analyze communication style (professionalism, clarity, feedback response)
2. Culture fit scoring (values, engagement, collaboration)
3. Responsiveness (response time, follow-up on commitments)
4. Red flags (toxicity, lack of improvement, escalation patterns)
5. Compare with baseline → improvement or regression

Cron: 0 21 * * 5 (Friday 21:00 — weekly report before Monday brief)
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

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

COMPLIANCE_PROMPT = """You are an HR analytics expert analyzing employee communication patterns.

Given a person's recent communications (emails, Teams messages, meeting transcripts),
evaluate them on these dimensions (score 1-5):

1. **Professionalism** — language quality, tone, respect
2. **Clarity** — clear communication, specific requests, no ambiguity
3. **Responsiveness** — timely responses, follow-up on commitments
4. **Initiative** — proactive communication, suggestions, problem-solving
5. **Collaboration** — team orientation, helping others, sharing knowledge
6. **Culture fit** — alignment with company values, positive attitude

Also flag:
- **Red flags**: toxicity, passive-aggression, blame-shifting, consistent non-response
- **Improvement areas**: specific suggestions for development
- **Trend**: improving / stable / declining (vs previous assessment if available)

Return JSON:
{
  "scores": {"professionalism": N, "clarity": N, "responsiveness": N, "initiative": N, "collaboration": N, "culture_fit": N},
  "overall_score": N.N,
  "red_flags": ["..."],
  "improvement_areas": ["..."],
  "trend": "improving|stable|declining",
  "summary": "2-3 sentence assessment in Polish"
}"""


def analyze_person_compliance(
    person_name: str,
    entity_id: int | None = None,
    weeks: int = 1,
) -> dict[str, Any]:
    """Analyze a person's communication compliance for the last N weeks."""

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find entity ID if not provided
            if not entity_id:
                cur.execute("""
                    SELECT p.entity_id FROM people p
                    WHERE p.first_name || ' ' || p.last_name ILIKE %s
                    LIMIT 1
                """, (f"%{person_name}%",))
                rows = cur.fetchall()
                entity_id = rows[0][0] if rows else None

            if not entity_id:
                return {"error": f"Person not found: {person_name}"}

            # Get recent chunks mentioning this person
            cur.execute("""
                SELECT LEFT(c.text, 400), s.source_type, d.created_at
                FROM chunks c
                JOIN chunk_entities ce ON ce.chunk_id = c.id
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE ce.entity_id = %s
                  AND d.created_at > NOW() - INTERVAL '%s weeks'
                  AND s.source_type IN ('teams', 'email', 'audio_transcript')
                ORDER BY d.created_at DESC
                LIMIT 50
            """, (entity_id, weeks))
            chunks = [{"text": r[0], "source": r[1], "date": str(r[2])} for r in cur.fetchall()]

            # Get recent events
            cur.execute("""
                SELECT e.event_type, e.summary, e.event_time
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE ee.entity_id = %s
                  AND e.event_time > NOW() - INTERVAL '%s weeks'
                ORDER BY e.event_time DESC
                LIMIT 30
            """, (entity_id, weeks))
            events = [{"type": r[0], "summary": r[1], "time": str(r[2]) if r[2] else None} for r in cur.fetchall()]

    if not chunks and not events:
        return {"person": person_name, "status": "no_data", "message": "No communication data for this period"}

    # Build context
    ctx = [f"Person: {person_name}", f"Period: last {weeks} week(s)", f"Data: {len(chunks)} chunks, {len(events)} events", ""]
    ctx.append("=== COMMUNICATIONS ===")
    for ch in chunks[:30]:
        ctx.append(f"[{ch['source']}] {ch['date']}: {ch['text']}")
    ctx.append("\n=== EVENTS ===")
    for ev in events[:20]:
        ctx.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    context = "\n".join(ctx)
    if len(context) > 20000:
        context = context[:20000] + "\n[truncated]"

    # Analyze via Claude
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            temperature=0.1,
            system=[{"type": "text", "text": COMPLIANCE_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.compliance_manager", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)
        result["person"] = person_name
        result["entity_id"] = entity_id
        result["period_weeks"] = weeks
        result["data_volume"] = {"chunks": len(chunks), "events": len(events)}
        return result

    except Exception as e:
        return {"person": person_name, "error": str(e)}


def run_weekly_compliance(weeks: int = 1) -> list[dict[str, Any]]:
    """Run compliance analysis for all active business people."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.first_name || ' ' || p.last_name, p.entity_id
                FROM people p
                JOIN relationships r ON r.person_id = p.id
                WHERE r.status = 'active' AND r.relationship_type = 'business'
            """)
            people = [(r[0], r[1]) for r in cur.fetchall()]

    results = []
    for name, eid in people:
        log.info("Analyzing: {name}...")
        result = analyze_person_compliance(name, entity_id=eid, weeks=weeks)
        results.append(result)

    # Save as insight
    scored = [r for r in results if "scores" in r]
    if scored:
        summary_lines = []
        for r in sorted(scored, key=lambda x: x.get("overall_score", 0)):
            flags = f" \u26a0\ufe0f {', '.join(r.get('red_flags', []))}" if r.get("red_flags") else ""
            summary_lines.append(f"{r['person']}: {r.get('overall_score', '?')}/5 ({r.get('trend', '?')}){flags}")

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO insights (insight_type, area, title, description, confidence)
                    VALUES ('compliance_report', 'business', %s, %s, 0.7)
                """, (
                    f"Compliance Report ({datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')})",
                    "\n".join(summary_lines),
                ))
            conn.commit()

    return results


if __name__ == "__main__":
    import sys
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    results = run_weekly_compliance(weeks)
    for r in results:
        if "scores" in r:
            log.info("{r['person']}: {r.get('overall_score', '?')}/5 — {r.get('summary', '')[:100]}")
        else:
            log.info("{r['person']}: {r.get('status', r.get('error', '?'))}")
