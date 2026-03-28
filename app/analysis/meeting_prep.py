"""
Meeting Prep Brief — automatyczne przygotowanie do spotkań.

30 minut przed każdym spotkaniem z kalendarza generuje brief:
- Scorecardy uczestników (people, entities)
- Otwarte tematy i commitments z uczestnikami
- Ostatnie eventy (30 dni)
- Sugerowane punkty do omówienia
- Red flags (konflikty, przeterminowane zobowiązania)

Cron: */15 * * * * (co 15 min, sprawdza spotkania w oknie 30-60 min)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

STATE_FILE = Path("/home/sebastian/personal-ai/.meeting_prep_state.json")

MEETING_PREP_PROMPT = """\
Jesteś asystentem Sebastiana Jabłońskiego (CEO REH/REF). Przygotuj zwięzły brief przed spotkaniem.

Na podstawie dostarczonych danych wygeneruj brief w formacie:

## Spotkanie: {subject}
**Czas:** {start} - {end}

### Uczestnicy
Dla każdego uczestnika: rola, organizacja, nastrój/sentiment, ostatnie interakcje (max 2-3 zdania).

### Otwarte tematy
Otwarte kwestie i zobowiązania z uczestnikami — co nie zostało domknięte.

### Kontekst
Ostatnie zdarzenia, decyzje związane z tematem spotkania lub uczestnikami (max 5 bullet points).

### Sugerowane punkty do omówienia
Konkretne punkty do poruszenia na spotkaniu, bazujące na kontekście.

### Red flags
Konflikty, przeterminowane zobowiązania, ryzyka. Jeśli brak — napisz "Brak".

Pisz po polsku, zwięźle, konkretnie. Bez ogólników. Jeśli brakuje danych o osobie — napisz to wprost.
"""


def _load_state() -> dict[str, Any]:
    """Load meeting prep state from file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {"prepped": {}}
    return {"prepped": {}}


def _save_state(state: dict[str, Any]) -> None:
    """Save meeting prep state to file."""
    try:
        STATE_FILE.write_text(json.dumps(state, default=str))
    except OSError as e:
        log.error("failed_to_save_state", error=str(e))


def _cleanup_old_entries(state: dict[str, Any]) -> dict[str, Any]:
    """Remove state entries older than 24 hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    prepped = state.get("prepped", {})
    state["prepped"] = {
        k: v for k, v in prepped.items()
        if v.get("timestamp", "") > cutoff
    }
    return state


def get_upcoming_meetings(within_minutes: int = 60) -> list[dict[str, Any]]:
    """Return meetings starting within the next N minutes."""
    from app.ingestion.graph_api.calendar_sync import get_today_events

    try:
        events = get_today_events()
    except Exception as e:
        log.error("calendar_fetch_failed", error=str(e))
        return []

    now = datetime.now(timezone.utc)
    window_start = now + timedelta(minutes=30)
    window_end = now + timedelta(minutes=within_minutes)

    upcoming = []
    for event in events:
        if event.get("isCancelled"):
            continue
        if event.get("isAllDay"):
            continue

        start_str = event.get("start", {}).get("dateTime", "")
        if not start_str:
            continue

        try:
            # Graph API returns datetime without timezone info but in UTC
            event_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if window_start <= event_start <= window_end:
            upcoming.append(event)

    log.info("upcoming_meetings_found", count=len(upcoming), within_minutes=within_minutes)
    return upcoming


def _extract_attendee_emails(meeting: dict[str, Any]) -> list[str]:
    """Extract attendee email addresses from a meeting event."""
    emails = []
    for attendee in meeting.get("attendees", []):
        email = attendee.get("emailAddress", {}).get("address", "")
        if email:
            emails.append(email.lower())

    organizer_email = meeting.get("organizer", {}).get("emailAddress", {}).get("address", "")
    if organizer_email and organizer_email.lower() not in emails:
        emails.append(organizer_email.lower())

    return emails


def gather_attendee_context(attendees: list[str]) -> dict[str, Any]:
    """Gather DB context for each attendee: people, entities, events, commitments."""
    context: dict[str, Any] = {
        "people": [],
        "entities": [],
        "recent_events": [],
        "commitments": [],
    }

    if not attendees:
        return context

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # People records
            for email in attendees:
                cur.execute(
                    """SELECT name, role, organization, email, sentiment_score,
                              last_interaction, notes
                       FROM people
                       WHERE LOWER(email) = %s
                       LIMIT 1""",
                    (email,),
                )
                row = cur.fetchone()
                if row:
                    context["people"].append({
                        "name": row[0],
                        "role": row[1],
                        "organization": row[2],
                        "email": row[3],
                        "sentiment_score": row[4],
                        "last_interaction": row[5],
                        "notes": row[6],
                    })

            # Entities related to attendees
            name_patterns = []
            for email in attendees:
                local = email.split("@")[0]
                name_patterns.append(f"%{local}%")

            if name_patterns:
                placeholders = " OR ".join(
                    ["LOWER(e.name) LIKE %s"] * len(name_patterns)
                )
                cur.execute(
                    f"""SELECT e.name, e.entity_type, e.metadata, e.created_at
                        FROM entities e
                        WHERE ({placeholders})
                        ORDER BY e.created_at DESC
                        LIMIT 20""",
                    [p.lower() for p in name_patterns],
                )
                for row in cur.fetchall():
                    context["entities"].append({
                        "name": row[0],
                        "type": row[1],
                        "metadata": row[2],
                        "created_at": row[3],
                    })

            # Recent events involving attendees (last 30 days)
            cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            for email in attendees:
                local = email.split("@")[0]
                cur.execute(
                    """SELECT ev.event_type, ev.description, ev.event_date,
                              ev.participants, ev.metadata
                       FROM events ev
                       WHERE (LOWER(ev.description) LIKE %s
                              OR LOWER(COALESCE(ev.participants::text, '')) LIKE %s)
                         AND ev.created_at >= %s
                       ORDER BY ev.event_date DESC
                       LIMIT 10""",
                    (f"%{local.lower()}%", f"%{local.lower()}%", cutoff_30d),
                )
                for row in cur.fetchall():
                    context["recent_events"].append({
                        "type": row[0],
                        "description": row[1],
                        "date": row[2],
                        "participants": row[3],
                        "metadata": row[4],
                    })

            # Commitments involving attendees
            for email in attendees:
                local = email.split("@")[0]
                cur.execute(
                    """SELECT ev.event_type, ev.description, ev.event_date,
                              ev.participants, ev.metadata
                       FROM events ev
                       WHERE ev.event_type IN ('commitment', 'decision', 'action_item')
                         AND (LOWER(ev.description) LIKE %s
                              OR LOWER(COALESCE(ev.participants::text, '')) LIKE %s)
                       ORDER BY ev.event_date DESC
                       LIMIT 10""",
                    (f"%{local.lower()}%", f"%{local.lower()}%"),
                )
                for row in cur.fetchall():
                    context["commitments"].append({
                        "type": row[0],
                        "description": row[1],
                        "date": row[2],
                        "participants": row[3],
                        "metadata": row[4],
                    })

    return context


def generate_meeting_brief(meeting: dict[str, Any], context: dict[str, Any]) -> str:
    """Use Claude to generate a meeting prep brief."""
    subject = meeting.get("subject", "Bez tytułu")
    start = meeting.get("start", {}).get("dateTime", "?")
    end = meeting.get("end", {}).get("dateTime", "?")

    user_message = f"""Spotkanie: {subject}
Czas: {start} - {end}
Lokalizacja: {meeting.get('location', {}).get('displayName', 'brak')}
Opis: {meeting.get('bodyPreview', 'brak')}

Dane o uczestnikach:
{json.dumps(context.get('people', []), ensure_ascii=False, default=str, indent=2)}

Powiązane encje:
{json.dumps(context.get('entities', []), ensure_ascii=False, default=str, indent=2)}

Ostatnie zdarzenia z uczestnikami (30 dni):
{json.dumps(context.get('recent_events', []), ensure_ascii=False, default=str, indent=2)}

Zobowiązania i decyzje:
{json.dumps(context.get('commitments', []), ensure_ascii=False, default=str, indent=2)}
"""

    system_prompt = MEETING_PREP_PROMPT.format(
        subject=subject,
        start=start,
        end=end,
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )

        log_anthropic_cost(ANTHROPIC_MODEL, "meeting_prep", response.usage)

        return response.content[0].text
    except Exception as e:
        log.error("llm_generation_failed", error=str(e))
        return f"❌ Nie udało się wygenerować briefu: {e}"


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


def run_meeting_prep() -> dict[str, Any]:
    """Main pipeline: check calendar → find upcoming → generate brief → send via WhatsApp."""
    result: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "meetings_found": 0,
        "briefs_generated": 0,
        "briefs_sent": 0,
        "skipped": 0,
        "errors": [],
    }

    # Load and clean state
    state = _load_state()
    state = _cleanup_old_entries(state)

    # Find upcoming meetings
    meetings = get_upcoming_meetings(within_minutes=60)
    result["meetings_found"] = len(meetings)

    if not meetings:
        log.info("no_upcoming_meetings")
        _save_state(state)
        return result

    for meeting in meetings:
        meeting_id = meeting.get("id", "")
        subject = meeting.get("subject", "Bez tytułu")

        # Skip already-prepped meetings
        if meeting_id in state.get("prepped", {}):
            log.info("meeting_already_prepped", meeting_id=meeting_id, subject=subject)
            result["skipped"] += 1
            continue

        log.info("preparing_meeting_brief", subject=subject, meeting_id=meeting_id)

        try:
            # Gather context
            attendees = _extract_attendee_emails(meeting)
            context = gather_attendee_context(attendees)

            # Generate brief
            brief = generate_meeting_brief(meeting, context)
            result["briefs_generated"] += 1

            # Send via WhatsApp
            header = "📋 *Meeting Prep Brief*\n\n"
            full_message = header + brief

            # Truncate if too long for WhatsApp
            if len(full_message) > 4000:
                full_message = full_message[:3950] + "\n\n... (skrócono)"

            sent = _send_whatsapp(full_message)
            if sent:
                result["briefs_sent"] += 1

            # Mark as prepped
            state.setdefault("prepped", {})[meeting_id] = {
                "subject": subject,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sent": sent,
            }

        except Exception as e:
            log.error("meeting_prep_failed", subject=subject, error=str(e))
            result["errors"].append({"meeting": subject, "error": str(e)})

    _save_state(state)
    log.info("meeting_prep_complete", **result)
    return result


if __name__ == "__main__":
    import json as _json
    r = run_meeting_prep()
    print(_json.dumps(r, ensure_ascii=False, indent=2, default=str))
