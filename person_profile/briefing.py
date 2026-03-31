"""AI Briefing Card generator using Anthropic API.

Generates a 5-7 sentence brief in Polish preparing the user for a conversation
with a given person. Cached in person_briefings with 24h TTL.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from anthropic import Anthropic

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

from . import config as cfg
from .models import PersonBriefing
from .repository import (
    get_fresh_briefing,
    get_full_profile,
    get_open_loops,
    get_relationship_pair,
    get_me,
    insert_briefing,
    mark_briefings_stale,
)

log = structlog.get_logger("person_profile.briefing")

SYSTEM_PROMPT = """\
Jesteś asystentem pomagającym zrozumieć relacje z ludźmi.
Na podstawie danych profilu wygeneruj krótki brief w języku polskim,
który przygotuje użytkownika do rozmowy z tą osobą.
Brief powinien zawierać 5-7 zdań w naturalnym języku i skupiać się na:
1. Bieżącym kontekście relacji (ostatni kontakt, co było omawiane)
2. Otwartych pętlach do zamknięcia
3. Ważnych sygnałach (zmiany zawodowe, życiowe)
4. Najlepszym kanale i czasie kontaktu
5. Konkretnej sugestii działania

Odpowiadaj WYŁĄCZNIE treścią briefu — bez nagłówków, markdown, ani meta-komentarzy.
Pisz zwięźle i konkretnie.
"""


def _profile_hash(data: dict) -> str:
    """MD5 hash of key profile fields to detect changes."""
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def _build_profile_payload(
    conn, person_id: UUID, me_id: UUID | None
) -> dict[str, Any]:
    """Build JSON payload for the LLM prompt."""
    from psycopg.rows import dict_row
    conn.row_factory = dict_row

    profile = get_full_profile(conn, person_id) or {}
    open_loops = get_open_loops(conn, person_id, status="open")

    relationship = None
    if me_id:
        relationship = get_relationship_pair(conn, me_id, person_id)

    # Communication pattern
    comm = conn.execute(
        "SELECT * FROM person_communication_pattern WHERE person_id = %s",
        (str(person_id),),
    ).fetchone()

    payload = {
        "display_name": profile.get("display_name"),
        "job_title": profile.get("job_title"),
        "company": profile.get("company"),
        "industry": profile.get("industry"),
        "seniority": profile.get("seniority"),
        "city": profile.get("city"),
        "tags": profile.get("tags"),
    }

    if relationship:
        payload["relationship"] = {
            "tie_strength": relationship.get("tie_strength"),
            "dominant_channel": relationship.get("dominant_channel"),
            "last_contact_at": str(relationship.get("last_contact_at")),
            "interaction_count": relationship.get("interaction_count"),
            "trajectory_status": profile.get("trajectory_status"),
        }

    if comm:
        payload["communication"] = {
            "preferred_hours": comm.get("preferred_hours"),
            "preferred_channel": comm.get("preferred_channel"),
            "avg_response_time_min": comm.get("avg_response_time_min"),
        }

    if open_loops:
        payload["open_loops"] = [
            {
                "direction": ol["direction"],
                "description": ol["description"],
                "due_date": str(ol.get("due_date")),
                "context_channel": ol.get("context_channel"),
            }
            for ol in open_loops[:5]
        ]

    # Job change signal
    if profile.get("job_change_detected_at"):
        payload["job_change_detected_at"] = str(profile["job_change_detected_at"])

    return payload


def generate_briefing(
    person_id: UUID,
    trigger: str = "on_demand",
    force: bool = False,
) -> PersonBriefing:
    """Generate or return cached briefing for a person.

    Args:
        person_id: Target person.
        trigger: 'on_demand', 'scheduled', or 'event_driven'.
        force: If True, regenerate even if cache is fresh.

    Returns:
        PersonBriefing with summary_text, key_points, action_hints.
    """
    with get_pg_connection() as conn:
        # Check cache first
        if not force:
            cached = get_fresh_briefing(conn, person_id)
            if cached:
                log.debug("briefing_cache_hit", person_id=str(person_id))
                return PersonBriefing(**cached)

        me = get_me(conn)
        me_id = me["person_id"] if me else None

        payload = _build_profile_payload(conn, person_id, me_id)
        phash = _profile_hash(payload)

        # Call Anthropic
        client = Anthropic()
        user_content = (
            f"Dane profilu:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        response = client.messages.create(
            model=cfg.ANTHROPIC_MODEL,
            max_tokens=cfg.ANTHROPIC_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(cfg.ANTHROPIC_MODEL, "person_briefing", response.usage)

        summary_text = response.content[0].text.strip()

        # Parse key points and action hints from text (simple heuristic)
        lines = [line.strip() for line in summary_text.split(".") if line.strip()]
        key_points = lines[:3] if len(lines) >= 3 else lines
        action_hints = lines[-2:] if len(lines) >= 2 else lines

        briefing = PersonBriefing(
            person_id=person_id,
            perspective_id=me_id,
            summary_text=summary_text,
            key_points=key_points,
            action_hints=action_hints,
            trigger=trigger,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=cfg.BRIEFING_TTL_HOURS),
            profile_hash=phash,
        )

        # Mark old briefings stale and insert new one
        mark_briefings_stale(conn, person_id)
        insert_briefing(conn, briefing)
        conn.commit()

        log.info(
            "briefing_generated",
            person_id=str(person_id),
            trigger=trigger,
            text_length=len(summary_text),
        )

    return briefing


def regenerate_stale_briefings(limit: int = 20) -> int:
    """Regenerate briefings that are marked stale. Returns count."""
    with get_pg_connection() as conn:
        from psycopg.rows import dict_row
        conn.row_factory = dict_row

        stale = conn.execute(
            """SELECT DISTINCT person_id FROM person_briefings
               WHERE is_stale = true
               ORDER BY person_id LIMIT %s""",
            (limit,),
        ).fetchall()

    count = 0
    for row in stale:
        try:
            generate_briefing(row["person_id"], trigger="scheduled", force=True)
            count += 1
        except Exception:
            log.exception("briefing_regen_failed", person_id=str(row["person_id"]))

    return count
