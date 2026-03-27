"""
Calendar Manager — active calendar management via Graph API.

Capabilities:
1. Block time (deep work, family, review sessions)
2. Suggest meetings based on relationship data
3. Detect conflicts
4. Optimize calendar (meeting density, deep work ratio)

Uses Graph API Calendar.ReadWrite (auth already exists in app/ingestion/graph_api/auth.py).

Cron: every 30 min (8-20) — check conflicts, suggest blocks
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MS_GRAPH_USER_ID = os.getenv("MS_GRAPH_USER_ID")

# Work hours (CET)
WORK_START_HOUR = 8
WORK_END_HOUR = 20
LUNCH_START_HOUR = 12
LUNCH_END_HOUR = 13
MEETING_OVERLOAD_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Graph API helpers
# ---------------------------------------------------------------------------

def _get_user_path() -> str:
    return f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"


def _graph_get(url: str, token: str, params: dict | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _graph_post(url: str, token: str, payload: dict) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _send_whatsapp(message: str) -> None:
    """Send WhatsApp notification via OpenClaw."""
    try:
        subprocess.run(
            [OPENCLAW_BIN, "send", WA_TARGET, message],
            capture_output=True, text=True, timeout=30,
        )
        log.info("whatsapp_sent", target=WA_TARGET)
    except Exception as exc:
        log.warning("whatsapp_send_failed", error=str(exc))


def _parse_event_dt(dt_obj: dict) -> datetime | None:
    """Parse Graph API dateTime object to datetime."""
    raw = dt_obj.get("dateTime", "")
    if not raw:
        return None
    try:
        # Graph returns naive datetime strings; treat as UTC for comparison
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 1. Get calendar events
# ---------------------------------------------------------------------------

def get_calendar_events(days_ahead: int = 7) -> list[dict]:
    """Fetch events from Graph API for the next N days."""
    from app.ingestion.graph_api.auth import get_access_token

    try:
        token = get_access_token()
    except Exception as exc:
        log.error("graph_token_failed", error=str(exc))
        return []

    user_path = _get_user_path()
    start = datetime.now(timezone.utc).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

    try:
        url = f"{GRAPH_BASE}/{user_path}/calendarView"
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$orderby": "start/dateTime",
            "$top": "100",
            "$select": "id,subject,start,end,organizer,attendees,isCancelled,showAs,isAllDay",
        }

        events: list[dict] = []
        while url:
            data = _graph_get(url, token, params if not events else None)
            events.extend(data.get("value", []))
            url = data.get("@odata.nextLink")

        log.info("calendar_events_fetched", count=len(events), days_ahead=days_ahead)

        result = []
        for ev in events:
            organizer = ev.get("organizer", {}).get("emailAddress", {})
            attendees_list = []
            for att in ev.get("attendees", []):
                email_obj = att.get("emailAddress", {})
                attendees_list.append({
                    "name": email_obj.get("name", ""),
                    "email": email_obj.get("address", ""),
                    "response": att.get("status", {}).get("response", "none"),
                })

            result.append({
                "id": ev.get("id"),
                "subject": ev.get("subject", "(no subject)"),
                "start": ev.get("start", {}),
                "end": ev.get("end", {}),
                "organizer": organizer.get("name", organizer.get("address", "?")),
                "attendees": attendees_list,
                "isCancelled": ev.get("isCancelled", False),
                "showAs": ev.get("showAs", "busy"),
                "isAllDay": ev.get("isAllDay", False),
            })

        return result
    except Exception as exc:
        log.error("calendar_fetch_failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# 2. Create calendar event
# ---------------------------------------------------------------------------

def create_event(
    subject: str,
    start: str,
    end: str,
    attendees: list[str] | None = None,
    body: str = "",
) -> dict:
    """Create a calendar event via Graph API.

    Args:
        subject: Event title.
        start: Start datetime in ISO format (e.g. '2026-03-28T09:00:00').
        end: End datetime in ISO format.
        attendees: List of email addresses.
        body: Optional event body text.
    """
    from app.ingestion.graph_api.auth import get_access_token

    try:
        token = get_access_token()
    except Exception as exc:
        log.error("graph_token_failed", error=str(exc))
        return {"error": str(exc)}

    user_path = _get_user_path()

    event_payload: dict[str, Any] = {
        "subject": subject,
        "start": {"dateTime": start, "timeZone": "Europe/Warsaw"},
        "end": {"dateTime": end, "timeZone": "Europe/Warsaw"},
        "body": {"contentType": "Text", "content": body},
    }
    if attendees:
        event_payload["attendees"] = [
            {"emailAddress": {"address": a}, "type": "required"}
            for a in attendees
        ]

    try:
        result = _graph_post(
            f"{GRAPH_BASE}/{user_path}/events",
            token,
            event_payload,
        )
        log.info("calendar_event_created", subject=subject, start=start, end=end)
        return {"status": "created", "id": result.get("id"), "subject": subject}
    except Exception as exc:
        log.error("calendar_event_create_failed", error=str(exc), subject=subject)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 3. Block deep work
# ---------------------------------------------------------------------------

def block_deep_work(
    date: str | None = None,
    start_hour: int = 9,
    end_hour: int = 11,
) -> dict:
    """Create a 'Deep Work' calendar block.

    Checks if the slot is free first. If occupied, finds the next available
    slot of the same duration within work hours.
    """
    if date is None:
        # Next working day
        target = datetime.now(timezone.utc) + timedelta(days=1)
        while target.weekday() >= 5:  # skip weekend
            target += timedelta(days=1)
        date = target.strftime("%Y-%m-%d")

    duration_hours = end_hour - start_hour

    # Fetch events for that day
    events = get_calendar_events(days_ahead=14)
    day_events = [
        e for e in events
        if not e.get("isCancelled")
        and e.get("start", {}).get("dateTime", "").startswith(date)
    ]

    # Check if desired slot is free
    desired_start = f"{date}T{start_hour:02d}:00:00"
    desired_end = f"{date}T{end_hour:02d}:00:00"

    slot_free = True
    for ev in day_events:
        ev_start = _parse_event_dt(ev["start"])
        ev_end = _parse_event_dt(ev["end"])
        ds = datetime.fromisoformat(desired_start).replace(tzinfo=timezone.utc)
        de = datetime.fromisoformat(desired_end).replace(tzinfo=timezone.utc)
        if ev_start and ev_end and ev_start < de and ev_end > ds:
            slot_free = False
            break

    if not slot_free:
        # Find next available slot
        log.info("deep_work_slot_occupied", date=date, start_hour=start_hour)
        for hour in range(WORK_START_HOUR, WORK_END_HOUR - duration_hours + 1):
            if hour == start_hour:
                continue
            candidate_start = f"{date}T{hour:02d}:00:00"
            candidate_end = f"{date}T{hour + duration_hours:02d}:00:00"
            cs = datetime.fromisoformat(candidate_start).replace(tzinfo=timezone.utc)
            ce = datetime.fromisoformat(candidate_end).replace(tzinfo=timezone.utc)

            conflict = False
            for ev in day_events:
                ev_start = _parse_event_dt(ev["start"])
                ev_end = _parse_event_dt(ev["end"])
                if ev_start and ev_end and ev_start < ce and ev_end > cs:
                    conflict = True
                    break

            if not conflict:
                desired_start = candidate_start
                desired_end = candidate_end
                log.info("deep_work_alternative_slot", start=desired_start)
                break
        else:
            return {
                "status": "no_slot_available",
                "date": date,
                "message": f"Brak wolnego slotu {duration_hours}h na {date}.",
            }

    # Create the deep work block
    from app.ingestion.graph_api.auth import get_access_token
    try:
        token = get_access_token()
    except Exception as exc:
        log.error("graph_token_failed", error=str(exc))
        return {"error": str(exc)}

    user_path = _get_user_path()
    event_payload = {
        "subject": "🔒 Deep Work",
        "start": {"dateTime": desired_start, "timeZone": "Europe/Warsaw"},
        "end": {"dateTime": desired_end, "timeZone": "Europe/Warsaw"},
        "showAs": "busy",
        "body": {"contentType": "Text", "content": "Blok deep work — nie planować spotkań."},
        "isReminderOn": True,
        "reminderMinutesBeforeStart": 15,
    }

    try:
        result = _graph_post(f"{GRAPH_BASE}/{user_path}/events", token, event_payload)
        log.info("deep_work_blocked", date=date, start=desired_start, end=desired_end)
        return {
            "status": "created",
            "id": result.get("id"),
            "date": date,
            "start": desired_start,
            "end": desired_end,
        }
    except Exception as exc:
        log.error("deep_work_create_failed", error=str(exc))
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 4. Detect conflicts
# ---------------------------------------------------------------------------

def detect_conflicts(days_ahead: int = 3) -> list[dict]:
    """Scan calendar for conflicts and issues.

    Checks for:
    - Overlapping events
    - >5 meetings in one day (meeting overload)
    - No lunch break (12-13)
    - Meetings during deep work blocks
    """
    events = get_calendar_events(days_ahead=days_ahead)
    if not events:
        return []

    # Filter out cancelled and all-day events
    active = [e for e in events if not e.get("isCancelled") and not e.get("isAllDay")]

    conflicts: list[dict] = []

    # Parse all events into (start, end, subject) tuples
    parsed: list[tuple[datetime, datetime, str]] = []
    for ev in active:
        s = _parse_event_dt(ev["start"])
        e = _parse_event_dt(ev["end"])
        if s and e:
            parsed.append((s, e, ev.get("subject", "?")))

    parsed.sort(key=lambda x: x[0])

    # Check overlaps
    for i in range(len(parsed)):
        for j in range(i + 1, len(parsed)):
            s1, e1, subj1 = parsed[i]
            s2, e2, subj2 = parsed[j]
            if s2 < e1:  # overlap
                conflicts.append({
                    "type": "overlap",
                    "severity": "high",
                    "events": [subj1, subj2],
                    "time": f"{s1.isoformat()} — {e1.isoformat()} vs {s2.isoformat()} — {e2.isoformat()}",
                    "suggestion": f"Przenieś jedno ze spotkań: '{subj1}' lub '{subj2}'.",
                })
            else:
                break  # sorted, no more overlaps for this event

    # Group by day
    from collections import defaultdict
    days: dict[str, list[tuple[datetime, datetime, str]]] = defaultdict(list)
    for s, e, subj in parsed:
        day_key = s.strftime("%Y-%m-%d")
        days[day_key].append((s, e, subj))

    for day_key, day_events in days.items():
        # Meeting overload
        if len(day_events) > MEETING_OVERLOAD_THRESHOLD:
            conflicts.append({
                "type": "overload",
                "severity": "medium",
                "date": day_key,
                "meeting_count": len(day_events),
                "suggestion": f"{len(day_events)} spotkań na {day_key} — rozważ przeniesienie części na inny dzień.",
            })

        # No lunch break
        has_lunch_free = True
        for s, e, subj in day_events:
            # Check if event overlaps 12:00-13:00
            lunch_start = s.replace(hour=LUNCH_START_HOUR, minute=0, second=0)
            lunch_end = s.replace(hour=LUNCH_END_HOUR, minute=0, second=0)
            if s < lunch_end and e > lunch_start:
                has_lunch_free = False
                break

        if not has_lunch_free:
            conflicts.append({
                "type": "no_lunch",
                "severity": "medium",
                "date": day_key,
                "suggestion": f"Brak przerwy obiadowej (12-13) na {day_key} — zablokuj czas na lunch.",
            })

        # Meetings during deep work
        for s, e, subj in day_events:
            if "deep work" in subj.lower():
                # Check if any other meeting overlaps this deep work block
                for s2, e2, subj2 in day_events:
                    if subj2 == subj:
                        continue
                    if s2 < e and e2 > s:
                        conflicts.append({
                            "type": "deep_work_violation",
                            "severity": "high",
                            "date": day_key,
                            "deep_work_block": subj,
                            "conflicting_meeting": subj2,
                            "suggestion": f"'{subj2}' koliduje z blokiem deep work — przenieś spotkanie.",
                        })

    log.info("conflicts_detected", count=len(conflicts), days_ahead=days_ahead)
    return conflicts


# ---------------------------------------------------------------------------
# 5. Suggest meetings
# ---------------------------------------------------------------------------

def suggest_meetings() -> list[dict]:
    """Suggest meetings based on relationship data.

    Finds people Sebastian hasn't interacted with in >10 days
    but has open loops with, and suggests 30-min meetings.
    """
    suggestions: list[dict] = []

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Check if required tables exist
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'entities'
                    )
                """)
                if not cur.fetchone()[0]:
                    log.info("suggest_meetings_skipped", reason="entities table missing")
                    return []

                # Find people with stale interactions and open events
                cur.execute("""
                    SELECT
                        e.name,
                        MAX(ev.event_time) as last_interaction,
                        COUNT(DISTINCT ev.id) as event_count
                    FROM entities e
                    LEFT JOIN event_entities ee ON ee.entity_id = e.id
                    LEFT JOIN events ev ON ev.id = ee.event_id
                    WHERE e.entity_type = 'person'
                      AND e.name NOT ILIKE '%%sebastian%%'
                      AND e.name NOT ILIKE '%%jabłoński%%'
                    GROUP BY e.id, e.name
                    HAVING MAX(ev.event_time) < NOW() - INTERVAL '10 days'
                       AND COUNT(DISTINCT ev.id) > 2
                    ORDER BY MAX(ev.event_time) ASC
                    LIMIT 5
                """)
                rows = cur.fetchall()
    except Exception as exc:
        log.error("suggest_meetings_db_failed", error=str(exc))
        return []

    if not rows:
        log.info("suggest_meetings_none", reason="no stale contacts found")
        return []

    for row in rows:
        name = row[0]
        last_interaction = row[1]
        event_count = row[2]

        days_since = None
        if last_interaction:
            days_since = (datetime.now(timezone.utc) - last_interaction.replace(tzinfo=timezone.utc)).days

        suggestions.append({
            "person": name,
            "last_interaction": str(last_interaction) if last_interaction else "unknown",
            "days_since_contact": days_since,
            "total_interactions": event_count,
            "suggested_duration_min": 30,
            "reason": f"Brak kontaktu od {days_since} dni, {event_count} wcześniejszych interakcji.",
        })

    log.info("meeting_suggestions_generated", count=len(suggestions))
    return suggestions


# ---------------------------------------------------------------------------
# 6. Calendar analytics
# ---------------------------------------------------------------------------

def get_calendar_analytics(days: int = 30) -> dict:
    """Analyze past calendar usage over the last N days."""
    # For past events, fetch via Graph API directly
    from app.ingestion.graph_api.auth import get_access_token
    try:
        token = get_access_token()
    except Exception as exc:
        log.error("graph_token_failed", error=str(exc))
        return {"error": str(exc)}

    user_path = _get_user_path()
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    end = datetime.now(timezone.utc).isoformat()

    try:
        url = f"{GRAPH_BASE}/{user_path}/calendarView"
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$orderby": "start/dateTime",
            "$top": "200",
            "$select": "id,subject,start,end,attendees,isCancelled,isAllDay,showAs",
        }

        all_events: list[dict] = []
        while url:
            data = _graph_get(url, token, params if not all_events else None)
            all_events.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
    except Exception as exc:
        log.error("calendar_analytics_fetch_failed", error=str(exc))
        return {"error": str(exc)}

    # Filter active, non-all-day meetings
    meetings = [
        e for e in all_events
        if not e.get("isCancelled") and not e.get("isAllDay")
    ]

    if not meetings:
        return {
            "total_meetings": 0,
            "period_days": days,
            "message": "Brak spotkań w analizowanym okresie.",
        }

    total_hours = 0.0
    from collections import Counter, defaultdict
    day_counts: Counter = Counter()
    weekday_hours: defaultdict[str, float] = defaultdict(float)
    person_counts: Counter = Counter()
    durations: list[float] = []
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for ev in meetings:
        s = _parse_event_dt(ev.get("start", {}))
        e = _parse_event_dt(ev.get("end", {}))
        if not s or not e:
            continue

        duration_h = (e - s).total_seconds() / 3600.0
        total_hours += duration_h
        durations.append(duration_h * 60)  # in minutes

        day_key = s.strftime("%Y-%m-%d")
        day_counts[day_key] += 1

        weekday = weekday_names[s.weekday()]
        weekday_hours[weekday] += duration_h

        for att in ev.get("attendees", []):
            name = att.get("emailAddress", {}).get("name", "")
            if name:
                person_counts[name] += 1

    work_hours_total = days * 10  # 10h work day assumption
    meeting_pct = (total_hours / work_hours_total * 100) if work_hours_total > 0 else 0

    # Deep work blocks
    deep_work_events = [
        e for e in all_events
        if "deep work" in e.get("subject", "").lower() and not e.get("isCancelled")
    ]
    deep_work_hours = 0.0
    for ev in deep_work_events:
        s = _parse_event_dt(ev.get("start", {}))
        e = _parse_event_dt(ev.get("end", {}))
        if s and e:
            deep_work_hours += (e - s).total_seconds() / 3600.0

    deep_work_pct = (deep_work_hours / work_hours_total * 100) if work_hours_total > 0 else 0

    # Busiest / quietest day
    busiest_day = max(weekday_hours, key=weekday_hours.get) if weekday_hours else "N/A"
    quietest_day = min(weekday_hours, key=weekday_hours.get) if weekday_hours else "N/A"

    most_met = person_counts.most_common(1)[0][0] if person_counts else "N/A"

    avg_meetings_per_day = len(meetings) / days if days > 0 else 0
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Recommendations
    recommendations: list[str] = []
    if meeting_pct > 50:
        recommendations.append(
            f"{meeting_pct:.0f}% czasu na spotkania — cel <50%. Rozważ async status updates."
        )
    if deep_work_pct < 10:
        recommendations.append(
            f"Deep work to tylko {deep_work_pct:.1f}% czasu. Zaplanuj bloki 2h rano."
        )
    if avg_meetings_per_day > 5:
        recommendations.append(
            f"Średnio {avg_meetings_per_day:.1f} spotkań/dzień — rozważ meeting-free afternoons."
        )

    result = {
        "period_days": days,
        "total_meetings": len(meetings),
        "total_hours_in_meetings": round(total_hours, 1),
        "avg_meetings_per_day": round(avg_meetings_per_day, 1),
        "meeting_time_pct": round(meeting_pct, 1),
        "deep_work_pct": round(deep_work_pct, 1),
        "busiest_day": busiest_day,
        "quietest_day": quietest_day,
        "avg_meeting_duration_min": round(avg_duration, 0),
        "most_met_person": most_met,
        "recommendations": recommendations,
    }

    log.info("calendar_analytics_generated", period_days=days, total_meetings=len(meetings))
    return result


# ---------------------------------------------------------------------------
# 7. Run calendar check (main pipeline)
# ---------------------------------------------------------------------------

def run_calendar_check() -> dict:
    """Main pipeline: detect conflicts, suggest meetings, analytics snapshot.

    Sends WhatsApp notification if conflicts are found.
    """
    log.info("calendar_check_started")

    conflicts = detect_conflicts(days_ahead=3)
    suggestions = suggest_meetings()

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "meeting_suggestions": suggestions,
        "suggestion_count": len(suggestions),
    }

    # Send WhatsApp if there are high-severity conflicts
    high_severity = [c for c in conflicts if c.get("severity") == "high"]
    if high_severity:
        msg_lines = [f"⚠️ Gilbertus Calendar: {len(high_severity)} konfliktów w kalendarzu"]
        for c in high_severity[:3]:
            if c["type"] == "overlap":
                msg_lines.append(f"• Nakładające się: {', '.join(c['events'])}")
            elif c["type"] == "deep_work_violation":
                msg_lines.append(f"• Deep work naruszony przez: {c['conflicting_meeting']}")
        _send_whatsapp("\n".join(msg_lines))

    log.info("calendar_check_completed", conflicts=len(conflicts), suggestions=len(suggestions))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--conflicts" in sys.argv:
        result = detect_conflicts()
    elif "--suggest" in sys.argv:
        result = suggest_meetings()
    elif "--analytics" in sys.argv:
        result = get_calendar_analytics()
    elif "--block" in sys.argv:
        result = block_deep_work()
    else:
        result = run_calendar_check()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
