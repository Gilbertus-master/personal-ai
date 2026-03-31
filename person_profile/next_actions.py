"""Next Best Action generator.

Scans signals from open_loops, trajectory, professional changes,
and relationship scores to generate prioritized action suggestions.

Run at the end of each delta update (step 9).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from . import config as cfg
from .models import PersonNextAction
from .repository import (
    get_me,
    has_pending_action,
    insert_next_action,
)

log = structlog.get_logger("person_profile.next_actions")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expire_high() -> datetime:
    return _now() + timedelta(days=cfg.NBA_EXPIRE_HIGH_PRIORITY_DAYS)


def _expire_low() -> datetime:
    return _now() + timedelta(days=cfg.NBA_EXPIRE_LOW_PRIORITY_DAYS)


# ─── Signal detectors ────────────────────────────────────────────────

def _detect_critical_open_loops(conn: psycopg.Connection) -> list[PersonNextAction]:
    """Priority 1: Open loops I owe them, due within 3 days or overdue > 14 days."""
    conn.row_factory = dict_row
    actions = []

    # Due soon
    rows = conn.execute(
        """SELECT pol.*, p.display_name
           FROM person_open_loops pol
           JOIN persons p ON p.person_id = pol.person_id
           WHERE pol.status = 'open'
             AND pol.direction = 'i_owe_them'
             AND pol.due_date IS NOT NULL
             AND pol.due_date < (CURRENT_DATE + %s)
             AND p.gdpr_delete_requested_at IS NULL""",
        (cfg.NBA_OPEN_LOOP_CRITICAL_DAYS,),
    ).fetchall()

    for row in rows:
        pid = row["person_id"]
        if has_pending_action(conn, pid, "close_loop", within_days=3):
            continue
        actions.append(PersonNextAction(
            person_id=pid,
            priority=1,
            action_type="close_loop",
            title=f"Zamknij obietnicę wobec {row['display_name']} (termin: {row['due_date']})",
            description=row["description"],
            signal_source="open_loop",
            signal_data={"loop_id": str(row["loop_id"]), "due_date": str(row["due_date"])},
            suggested_channel=row.get("context_channel"),
            expires_at=_expire_high(),
        ))

    # Overdue (no due_date but old)
    rows = conn.execute(
        """SELECT pol.*, p.display_name
           FROM person_open_loops pol
           JOIN persons p ON p.person_id = pol.person_id
           WHERE pol.status = 'open'
             AND pol.direction = 'i_owe_them'
             AND pol.created_at < now() - make_interval(days => %s)
             AND p.gdpr_delete_requested_at IS NULL""",
        (cfg.NBA_OPEN_LOOP_OVERDUE_DAYS,),
    ).fetchall()

    for row in rows:
        pid = row["person_id"]
        if has_pending_action(conn, pid, "close_loop", within_days=14):
            continue
        actions.append(PersonNextAction(
            person_id=pid,
            priority=1,
            action_type="close_loop",
            title=f"Zaległa obietnica wobec {row['display_name']} (od {row['created_at'].strftime('%d.%m')})",
            description=row["description"],
            signal_source="open_loop_overdue",
            signal_data={"loop_id": str(row["loop_id"])},
            suggested_channel=row.get("context_channel"),
            expires_at=_expire_high(),
        ))

    return actions


def _detect_job_changes(conn: psycopg.Connection) -> list[PersonNextAction]:
    """Priority 2: Recent job change detected — congratulate."""
    conn.row_factory = dict_row
    actions = []

    rows = conn.execute(
        """SELECT pp.person_id, p.display_name, pp.job_title, pp.company
           FROM person_professional pp
           JOIN persons p ON p.person_id = pp.person_id
           WHERE pp.job_change_detected_at > now() - make_interval(days => %s)
             AND p.gdpr_delete_requested_at IS NULL""",
        (cfg.NBA_JOB_CHANGE_WINDOW_DAYS,),
    ).fetchall()

    for row in rows:
        pid = row["person_id"]
        if has_pending_action(conn, pid, "congratulate", within_days=14):
            continue
        actions.append(PersonNextAction(
            person_id=pid,
            priority=2,
            action_type="congratulate",
            title=f"Pogratuluj {row['display_name']} nowej roli: {row.get('job_title', '?')} @ {row.get('company', '?')}",
            signal_source="job_change",
            signal_data={"job_title": row.get("job_title"), "company": row.get("company")},
            expires_at=_expire_high(),
        ))

    return actions


def _detect_cooling_relationships(
    conn: psycopg.Connection, me_id: UUID
) -> list[PersonNextAction]:
    """Priority 2: Cooling trajectory with previously stable/growing relationships."""
    conn.row_factory = dict_row
    actions = []

    rows = conn.execute(
        """SELECT prt.person_id_to, prt.trajectory_status,
                  prt.days_since_last_contact, prt.delta_30d,
                  p.display_name
           FROM person_relationship_trajectory prt
           JOIN persons p ON p.person_id = prt.person_id_to
           WHERE prt.person_id = %s
             AND prt.trajectory_status = 'cooling'
             AND prt.days_since_last_contact > %s
             AND p.gdpr_delete_requested_at IS NULL""",
        (str(me_id), cfg.NBA_COOLING_MIN_DAYS),
    ).fetchall()

    for row in rows:
        pid = row["person_id_to"]
        if has_pending_action(conn, pid, "reengage", within_days=14):
            continue
        actions.append(PersonNextAction(
            person_id=pid,
            priority=2,
            action_type="reengage",
            title=f"Relacja z {row['display_name']} słabnie — {row['days_since_last_contact']} dni bez kontaktu",
            description=f"Delta 30d: {row.get('delta_30d', '?')}",
            signal_source="trajectory_cooling",
            signal_data={"delta_30d": row.get("delta_30d"), "days": row.get("days_since_last_contact")},
            expires_at=_expire_high(),
        ))

    return actions


def _detect_no_contact(
    conn: psycopg.Connection, me_id: UUID
) -> list[PersonNextAction]:
    """Priority 3: Important relationship with no contact > 45 days."""
    conn.row_factory = dict_row
    actions = []

    rows = conn.execute(
        """SELECT pr.person_id_to, pr.tie_strength, pr.last_contact_at,
                  pr.dominant_channel, p.display_name
           FROM person_relationships pr
           JOIN persons p ON p.person_id = pr.person_id_to
           WHERE pr.person_id_from = %s
             AND pr.tie_strength > %s
             AND pr.last_contact_at < now() - make_interval(days => %s)
             AND p.gdpr_delete_requested_at IS NULL""",
        (str(me_id), cfg.NBA_NO_CONTACT_MIN_TIE, cfg.NBA_NO_CONTACT_DAYS),
    ).fetchall()

    for row in rows:
        pid = row["person_id_to"]
        if has_pending_action(conn, pid, "follow_up", within_days=14):
            continue
        days = 0
        if row["last_contact_at"]:
            days = (_now() - row["last_contact_at"].replace(tzinfo=timezone.utc)).days
        actions.append(PersonNextAction(
            person_id=pid,
            priority=3,
            action_type="follow_up",
            title=f"Odezwij się do {row['display_name']} — {days} dni bez kontaktu",
            suggested_channel=row.get("dominant_channel"),
            signal_source="no_contact_threshold",
            signal_data={"days": days, "tie_strength": row["tie_strength"]},
            expires_at=_expire_low(),
        ))

    return actions


def _detect_shared_interest(
    conn: psycopg.Connection, me_id: UUID
) -> list[PersonNextAction]:
    """Priority 4: Growing relationship with new shared context."""
    conn.row_factory = dict_row
    actions = []

    rows = conn.execute(
        """SELECT prt.person_id_to, p.display_name,
                  psc.entity_type, psc.entity_value
           FROM person_relationship_trajectory prt
           JOIN persons p ON p.person_id = prt.person_id_to
           JOIN person_shared_context psc ON psc.person_id = prt.person_id_to
           WHERE prt.person_id = %s
             AND prt.trajectory_status = 'growing'
             AND psc.last_seen_at > now() - INTERVAL '7 days'
             AND p.gdpr_delete_requested_at IS NULL
           LIMIT 20""",
        (str(me_id),),
    ).fetchall()

    seen_persons: set[UUID] = set()
    for row in rows:
        pid = row["person_id_to"]
        if pid in seen_persons:
            continue
        seen_persons.add(pid)
        if has_pending_action(conn, pid, "share_content", within_days=14):
            continue
        actions.append(PersonNextAction(
            person_id=pid,
            priority=4,
            action_type="share_content",
            title=f"Podziel się z {row['display_name']} — wspólny temat: {row['entity_value']}",
            signal_source="shared_interest",
            signal_data={"entity_type": row["entity_type"], "entity_value": row["entity_value"]},
            expires_at=_expire_low(),
        ))

    return actions


# ─── Main entry point ────────────────────────────────────────────────

def generate_all_next_actions(conn: psycopg.Connection) -> int:
    """Generate next best actions from all signal sources.

    Returns count of new actions created.
    """
    me = get_me(conn)
    me_id = me["person_id"] if me else None

    all_actions: list[PersonNextAction] = []

    # Priority 1: Critical open loops
    all_actions.extend(_detect_critical_open_loops(conn))

    if me_id:
        # Priority 2: Job changes
        all_actions.extend(_detect_job_changes(conn))

        # Priority 2: Cooling relationships
        all_actions.extend(_detect_cooling_relationships(conn, me_id))

        # Priority 3: No contact threshold
        all_actions.extend(_detect_no_contact(conn, me_id))

        # Priority 4: Shared interests
        all_actions.extend(_detect_shared_interest(conn, me_id))

    # Expire old pending actions
    conn.execute(
        """UPDATE person_next_actions SET status = 'expired'
           WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < now()"""
    )

    # Insert new actions
    count = 0
    for action in all_actions:
        try:
            insert_next_action(conn, action)
            count += 1
        except Exception:
            log.exception(
                "next_action_insert_failed",
                person_id=str(action.person_id),
                action_type=action.action_type,
            )

    log.info("next_actions_generated", total=count, by_priority={
        1: sum(1 for a in all_actions if a.priority == 1),
        2: sum(1 for a in all_actions if a.priority == 2),
        3: sum(1 for a in all_actions if a.priority == 3),
        4: sum(1 for a in all_actions if a.priority == 4),
    })

    return count
