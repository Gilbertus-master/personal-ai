"""
Speaker resolver — maps "Speaker 1", "Speaker 2" etc. to known people.

Uses context from the transcript + known people database to identify speakers.
Plaud already does diarization (Speaker N labels). We just need to resolve WHO.

Also handles meeting boundary detection (C4):
- Detects topic shifts in transcripts
- Marks meeting start/end boundaries
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

SPEAKER_PROMPT = """You identify speakers in meeting transcripts. Given:
1. A transcript with Speaker labels (Speaker 1, Speaker 2, Sebastian, etc.)
2. A list of known people with their roles

Map each Speaker to a known person based on:
- Content they discuss (role-specific topics)
- How others address them
- Meeting context (title, attendees if known)

Return JSON:
{
  "speakers": {"Speaker 1": "Name or Unknown", "Speaker 2": "Name or Unknown"},
  "confidence": 0.0-1.0,
  "meeting_topic": "brief description of what the meeting is about"
}

If you can't identify a speaker, use "Unknown". Be conservative — only identify if confident."""

BOUNDARY_PROMPT = """Analyze this transcript segment and detect meeting boundaries.

Is this:
1. A CONTINUATION of the same meeting/conversation?
2. A NEW meeting/conversation starting?
3. The END of a meeting (people saying goodbye, wrapping up)?
4. TRANSITION between topics within the same meeting?

Return JSON:
{"boundary_type": "continuation|new_meeting|end_meeting|topic_transition", "confidence": 0.0-1.0, "topic": "current topic"}"""


def resolve_speakers(document_id: int) -> dict[str, Any]:
    """Resolve Speaker labels to known people for a transcript document."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Get transcript
            cur.execute("""
                SELECT d.title, c.text, c.chunk_index
                FROM documents d
                JOIN chunks c ON c.document_id = d.id
                WHERE d.id = %s ORDER BY c.chunk_index LIMIT 5
            """, (document_id,))
            rows = cur.fetchall()
            if not rows:
                return {"error": "Document not found"}

            title = rows[0][0]
            text = "\n".join(r[1] for r in rows)

            # Get known people with roles
            cur.execute("""
                SELECT p.first_name || ' ' || p.last_name, r.person_role, r.organization
                FROM people p
                LEFT JOIN relationships r ON r.person_id = p.id
                WHERE r.status = 'active'
            """)
            people = [f"{r[0]} ({r[1] or '?'} @ {r[2] or '?'})" for r in cur.fetchall()]

    # Extract unique speaker labels
    speakers = set(re.findall(r'(Speaker \d+|Sebastian)', text[:5000]))
    if not speakers:
        return {"document_id": document_id, "speakers": {}, "note": "No speaker labels found"}

    context = f"Title: {title}\n\nKnown people:\n" + "\n".join(f"- {p}" for p in people)
    context += f"\n\nTranscript (first 3000 chars):\n{text[:3000]}"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            temperature=0.1,
            system=[{"type": "text", "text": SPEAKER_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.speaker_resolver", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        result["document_id"] = document_id
        result["title"] = title
        return result
    except Exception as e:
        return {"document_id": document_id, "error": str(e)}


def detect_meeting_boundaries(text: str) -> dict[str, Any]:
    """Detect if text represents a meeting boundary (new/end/continuation)."""
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=100,
            temperature=0.1,
            system=[{"type": "text", "text": BOUNDARY_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text[:2000]}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.meeting_boundary", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"boundary_type": "continuation", "confidence": 0, "error": str(e)}


def resolve_all_unresolved(limit: int = 10) -> list[dict[str, Any]]:
    """Resolve speakers for recent audio transcripts that haven't been resolved yet."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT d.id
                FROM documents d
                JOIN chunks c ON c.document_id = d.id
                JOIN sources s ON s.id = d.source_id
                WHERE s.source_type = 'audio_transcript'
                  AND c.text LIKE '%Speaker %'
                ORDER BY d.created_at DESC
                LIMIT %s
            """, (limit,))
            doc_ids = [r[0] for r in cur.fetchall()]

    results = []
    for did in doc_ids:
        result = resolve_speakers(did)
        results.append(result)
        if result.get("speakers"):
            print(f"  {result.get('title', '?')[:60]}: {result['speakers']}")

    return results


if __name__ == "__main__":
    results = resolve_all_unresolved()
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
