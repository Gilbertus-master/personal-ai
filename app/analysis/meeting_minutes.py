"""
Meeting Minutes Generator — automatyczne notatki ze spotkań.

Po zaimportowaniu nagrania Plaud, generuje strukturalne minutki:
- Uczestnicy
- Tematy omówione
- Decyzje podjęte
- Action items (jako commitments)
- Follow-upy

Cron: co 30 min (po imporcie audio)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)
OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

MINUTES_PROMPT = """\
Jesteś asystentem Sebastiana Jabłońskiego (CEO REH/REF). Na podstawie transkrypcji spotkania wygeneruj strukturalne notatki.

Odpowiedź MUSI być w formacie JSON (i TYLKO JSON, bez markdown):
{
  "title": "Krótki tytuł spotkania",
  "participants": ["Imię Nazwisko", ...],
  "topics": [
    {"topic": "Temat 1", "discussion": "Co omówiono..."}
  ],
  "decisions": [
    {"decision": "Podjęta decyzja", "context": "Kontekst decyzji"}
  ],
  "action_items": [
    {"person": "Imię Nazwisko", "task": "Co ma zrobić", "deadline": "YYYY-MM-DD lub null"}
  ],
  "summary": "2-3 zdania podsumowujące spotkanie"
}

Zasady:
- Uczestnicy: wymień wszystkie osoby, które aktywnie brały udział w rozmowie
- Tematy: grupuj w logiczne bloki tematyczne
- Decyzje: tylko konkretne, podjęte decyzje — nie luźne pomysły
- Action items: konkretne zadania z przypisanymi osobami
- Summary: zwięźle, po polsku, bez ogólników
- Jeśli z transkrypcji nie da się wyciągnąć danej sekcji — zwróć pustą listę []
"""


_tables_ensured = False
def _ensure_tables() -> None:
    """Create meeting_minutes table if not exists."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meeting_minutes (
                    id BIGSERIAL PRIMARY KEY,
                    document_id BIGINT REFERENCES documents(id) UNIQUE,
                    title TEXT,
                    meeting_date TIMESTAMPTZ,
                    participants JSONB,
                    topics JSONB,
                    decisions JSONB,
                    action_items JSONB,
                    summary TEXT,
                    raw_minutes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()
    log.info("meeting_minutes_table_ensured")
    _tables_ensured = True


def _get_unprocessed_recordings() -> list[dict[str, Any]]:
    """Find audio_transcript documents without generated minutes."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.raw_path, d.imported_at
                FROM documents d
                LEFT JOIN meeting_minutes mm ON mm.document_id = d.id
                WHERE d.source_type = 'audio_transcript'
                  AND mm.id IS NULL
                ORDER BY d.imported_at DESC
                LIMIT 10
            """)
            rows = cur.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "raw_path": row[2],
                    "imported_at": row[3],
                }
                for row in rows
            ]


def _get_document_chunks(document_id: int) -> list[str]:
    """Fetch all chunk texts for a document, ordered."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content
                   FROM chunks
                   WHERE document_id = %s
                   ORDER BY chunk_index ASC""",
                (document_id,),
            )
            return [row[0] for row in cur.fetchall()]


def generate_minutes_for_recording(document_id: int) -> dict[str, Any]:
    """Generate structured meeting minutes from a recording's chunks."""
    chunks = _get_document_chunks(document_id)

    if not chunks:
        log.warning("no_chunks_for_document", document_id=document_id)
        return {"error": "No chunks found for document"}

    transcript = "\n\n---\n\n".join(chunks)

    # Truncate if extremely long (keep within context window)
    max_chars = 150_000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[... transkrypcja skrócona ...]"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            system=[{"type": "text", "text": MINUTES_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": f"Transkrypcja spotkania:\n\n{transcript}",
            }],
        )

        log_anthropic_cost(ANTHROPIC_MODEL, "meeting_minutes", response.usage)

        raw_text = response.content[0].text

        # Parse JSON from response
        try:
            minutes = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
            if json_match:
                minutes = json.loads(json_match.group(1))
            else:
                log.error("failed_to_parse_minutes_json", document_id=document_id)
                return {"error": "Failed to parse LLM response as JSON", "raw": raw_text}

        return {
            "minutes": minutes,
            "raw_text": raw_text,
        }

    except Exception as e:
        log.error("minutes_generation_failed", document_id=document_id, error=str(e))
        return {"error": str(e)}


def _save_minutes(document_id: int, minutes: dict[str, Any], raw_text: str) -> int | None:
    """Save generated minutes to DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO meeting_minutes
                       (document_id, title, meeting_date, participants, topics,
                        decisions, action_items, summary, raw_minutes)
                   VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (document_id) DO NOTHING
                   RETURNING id""",
                (
                    document_id,
                    minutes.get("title", "Bez tytułu"),
                    json.dumps(minutes.get("participants", []), ensure_ascii=False),
                    json.dumps(minutes.get("topics", []), ensure_ascii=False),
                    json.dumps(minutes.get("decisions", []), ensure_ascii=False),
                    json.dumps(minutes.get("action_items", []), ensure_ascii=False),
                    minutes.get("summary", ""),
                    raw_text,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None


def _extract_commitments(document_id: int, action_items: list[dict[str, Any]]) -> int:
    """Insert action items as commitment events into the events table."""
    count = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for item in action_items:
                person = item.get("person", "nieznany")
                task = item.get("task", "")
                deadline = item.get("deadline")

                if not task:
                    continue

                description = f"[Meeting Minutes] {person}: {task}"
                if deadline and deadline != "null":
                    description += f" (deadline: {deadline})"

                cur.execute(
                    """INSERT INTO events
                           (event_type, description, participants, metadata,
                            event_date, chunk_id, created_at)
                       VALUES (%s, %s, %s, %s, NOW(), NULL, NOW())""",
                    (
                        "commitment",
                        description,
                        json.dumps([person], ensure_ascii=False),
                        json.dumps({
                            "source": "meeting_minutes",
                            "document_id": document_id,
                            "deadline": deadline,
                            "task": task,
                        }, ensure_ascii=False),
                    ),
                )
                count += 1

            conn.commit()

    log.info("commitments_extracted", document_id=document_id, count=count)
    return count


def _send_whatsapp(message: str) -> bool:
    """Send message via WhatsApp using openclaw."""
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.warning("whatsapp_send_failed", stderr=result.stderr)
            return False
        return True
    except Exception as e:
        log.error("whatsapp_send_error", error=str(e))
        return False


def run_minutes_generation(notify: bool = True) -> dict[str, Any]:
    """Find unprocessed recordings and generate minutes for each."""
    result: dict[str, Any] = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "recordings_found": 0,
        "minutes_generated": 0,
        "commitments_extracted": 0,
        "errors": [],
    }

    _ensure_tables()

    recordings = _get_unprocessed_recordings()
    result["recordings_found"] = len(recordings)

    if not recordings:
        log.info("no_unprocessed_recordings")
        return result

    for rec in recordings:
        doc_id = rec["id"]
        title = rec.get("title", "Bez tytułu")
        log.info("processing_recording", document_id=doc_id, title=title)

        try:
            gen_result = generate_minutes_for_recording(doc_id)

            if "error" in gen_result:
                result["errors"].append({
                    "document_id": doc_id,
                    "title": title,
                    "error": gen_result["error"],
                })
                continue

            minutes = gen_result["minutes"]
            raw_text = gen_result["raw_text"]

            # Save to DB
            minutes_id = _save_minutes(doc_id, minutes, raw_text)
            if minutes_id:
                result["minutes_generated"] += 1

                # Extract commitments from action items
                action_items = minutes.get("action_items", [])
                if action_items:
                    count = _extract_commitments(doc_id, action_items)
                    result["commitments_extracted"] += count

                # Notify via WhatsApp
                if notify:
                    summary = minutes.get("summary", "")
                    n_actions = len(action_items)
                    n_decisions = len(minutes.get("decisions", []))
                    msg = (
                        f"📝 *Minutki: {minutes.get('title', title)}*\n\n"
                        f"{summary}\n\n"
                        f"📌 Decyzje: {n_decisions}\n"
                        f"✅ Action items: {n_actions}"
                    )
                    _send_whatsapp(msg)

            log.info("minutes_saved", document_id=doc_id, minutes_id=minutes_id)

        except Exception as e:
            log.error("minutes_processing_failed", document_id=doc_id, error=str(e))
            result["errors"].append({
                "document_id": doc_id,
                "title": title,
                "error": str(e),
            })

    log.info("minutes_generation_complete", **result)
    return result


if __name__ == "__main__":
    import json as _json
    r = run_minutes_generation()
    print(_json.dumps(r, ensure_ascii=False, indent=2, default=str))
