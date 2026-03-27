"""
Weekly Executive Synthesis — strategic weekly report for Sebastian.

Generated Sunday evening. Covers:
1. Top 5 events of the week (by impact)
2. Relationship changes (sentiment deltas)
3. Commitments: fulfilled vs broken
4. Opportunities found and acted on
5. Wellbeing signals
6. Next week forecast (calendar + predicted issues)
7. Key metrics delta

Cron: 0 20 * * 0 (Sunday 20:00 CET = 19:00 UTC)

Usage:
    python -m app.retrieval.weekly_synthesis
    python -m app.retrieval.weekly_synthesis --date 2026-03-22
    python -m app.retrieval.weekly_synthesis --force
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from anthropic import Anthropic, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)


# ============================================================
# Helper: safe query for tables that may not exist yet
# ============================================================

def _safe_query(query: str, params: tuple = (), default: list | None = None) -> list:
    """Execute a query, returning default on table-not-found errors."""
    if default is None:
        default = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        err_msg = str(e).lower()
        if "does not exist" in err_msg or "relation" in err_msg:
            logger.warning("Table not found for query, returning empty: %s", err_msg[:120])
            return default
        raise


# ============================================================
# Database queries
# ============================================================

def _fetch_events(week_start: str, week_end: str) -> tuple[list[dict], dict]:
    """Fetch all events from the week, grouped by type with counts."""
    query = """
    SELECT
        e.id,
        e.event_type,
        e.event_time,
        e.summary,
        e.confidence,
        COALESCE(
            string_agg(DISTINCT en.canonical_name, ', '
                ORDER BY en.canonical_name),
            ''
        ) AS entities
    FROM events e
    LEFT JOIN event_entities ee ON ee.event_id = e.id
    LEFT JOIN entities en ON en.id = ee.entity_id
    WHERE e.event_time >= %s::timestamptz
      AND e.event_time < %s::timestamptz
    GROUP BY e.id, e.event_type, e.event_time, e.summary, e.confidence
    ORDER BY e.event_time DESC
    LIMIT 500
    """
    rows = _safe_query(query, (week_start, week_end))

    events = [
        {
            "event_id": row[0],
            "event_type": row[1],
            "event_time": row[2].isoformat() if row[2] else None,
            "summary": row[3],
            "confidence": row[4],
            "entities": row[5],
        }
        for row in rows
    ]

    # Count per event type
    event_counts: dict[str, int] = {}
    for ev in events:
        t = ev["event_type"] or "unknown"
        event_counts[t] = event_counts.get(t, 0) + 1

    return events, event_counts


def _fetch_commitments(week_start: str, week_end: str) -> dict:
    """Fetch commitment status from commitments table (may not exist)."""
    result: dict[str, list] = {"fulfilled": [], "broken": [], "overdue": [], "new": []}

    # New commitments created this week
    rows = _safe_query(
        """
        SELECT person_name, description, due_date, status
        FROM commitments
        WHERE created_at >= %s::timestamptz AND created_at < %s::timestamptz
        ORDER BY due_date
        """,
        (week_start, week_end),
    )
    for row in rows:
        entry = {"person": row[0], "description": row[1], "due_date": str(row[2]) if row[2] else None, "status": row[3]}
        result["new"].append(entry)
        if row[3] == "fulfilled":
            result["fulfilled"].append(entry)
        elif row[3] == "broken":
            result["broken"].append(entry)
        elif row[3] == "overdue":
            result["overdue"].append(entry)

    # Also check for commitments resolved this week (created earlier)
    rows = _safe_query(
        """
        SELECT person_name, description, due_date, status
        FROM commitments
        WHERE updated_at >= %s::timestamptz AND updated_at < %s::timestamptz
          AND created_at < %s::timestamptz
          AND status IN ('fulfilled', 'broken')
        ORDER BY updated_at
        """,
        (week_start, week_end, week_start),
    )
    for row in rows:
        entry = {"person": row[0], "description": row[1], "due_date": str(row[2]) if row[2] else None, "status": row[3]}
        if row[3] == "fulfilled":
            result["fulfilled"].append(entry)
        elif row[3] == "broken":
            result["broken"].append(entry)

    return result


def _fetch_opportunities(week_start: str, week_end: str) -> list[dict]:
    """Fetch opportunities detected this week."""
    rows = _safe_query(
        """
        SELECT opportunity_type, description, estimated_value_pln, status, detected_at
        FROM opportunities
        WHERE detected_at >= %s::timestamptz AND detected_at < %s::timestamptz
        ORDER BY estimated_value_pln DESC NULLS LAST
        """,
        (week_start, week_end),
    )
    return [
        {
            "type": row[0],
            "description": row[1],
            "value_pln": float(row[2]) if row[2] else None,
            "status": row[3],
            "detected_at": row[4].isoformat() if row[4] else None,
        }
        for row in rows
    ]


def _fetch_sentiment_changes(week_start: str, week_end: str) -> list[dict]:
    """Fetch sentiment score changes from sentiment_scores table."""
    rows = _safe_query(
        """
        SELECT person_name, score, previous_score, delta, measured_at
        FROM sentiment_scores
        WHERE measured_at >= %s::timestamptz AND measured_at < %s::timestamptz
        ORDER BY ABS(delta) DESC NULLS LAST
        LIMIT 20
        """,
        (week_start, week_end),
    )
    return [
        {
            "person": row[0],
            "score": float(row[1]) if row[1] else None,
            "previous": float(row[2]) if row[2] else None,
            "delta": float(row[3]) if row[3] else None,
            "measured_at": row[4].isoformat() if row[4] else None,
        }
        for row in rows
    ]


def _fetch_wellbeing(week_start: str, week_end: str) -> dict:
    """Fetch wellbeing scores from wellbeing_scores table."""
    rows = _safe_query(
        """
        SELECT indicator, score, notes, measured_at
        FROM wellbeing_scores
        WHERE measured_at >= %s::timestamptz AND measured_at < %s::timestamptz
        ORDER BY measured_at DESC
        """,
        (week_start, week_end),
    )
    return {
        "scores": [
            {
                "indicator": row[0],
                "score": float(row[1]) if row[1] else None,
                "notes": row[2],
                "measured_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]
    }


def _fetch_calendar_next_week(week_end: str) -> list[dict]:
    """Fetch next week's calendar events via Graph API."""
    try:
        from app.ingestion.graph_api.calendar_sync import get_week_events
        from app.ingestion.graph_api.auth import get_access_token
        token = get_access_token()
        next_week_end = (datetime.fromisoformat(week_end) + timedelta(days=7)).strftime("%Y-%m-%d")
        events = get_week_events(token, week_end, next_week_end)
    except Exception as e:
        logger.warning("Calendar fetch for next week failed: %s", e)
        # Fallback: try fetching from events table
        try:
            rows = _safe_query(
                """
                SELECT event_type, event_time, summary
                FROM events
                WHERE event_type = 'meeting'
                  AND event_time >= %s::timestamptz
                  AND event_time < %s::timestamptz
                ORDER BY event_time
                LIMIT 30
                """,
                (week_end, (datetime.fromisoformat(week_end) + timedelta(days=7)).strftime("%Y-%m-%d")),
            )
            return [
                {"subject": row[2], "start": row[1].isoformat() if row[1] else "?", "end": None}
                for row in rows
            ]
        except Exception:
            return []

    results = []
    for ev in events:
        if ev.get("isCancelled"):
            continue
        results.append({
            "subject": ev.get("subject", "(no subject)"),
            "start": ev.get("start", {}).get("dateTime", "?")[:16],
            "end": ev.get("end", {}).get("dateTime", "?")[:16],
            "attendees": [
                att.get("emailAddress", {}).get("name", "?")
                for att in ev.get("attendees", [])
            ],
        })
    return results


def _fetch_communication_stats(week_start: str, week_end: str) -> dict:
    """Fetch communication statistics for the week."""
    stats: dict[str, Any] = {}

    # Documents processed
    rows = _safe_query(
        """
        SELECT source_type, COUNT(*) as cnt
        FROM sources
        WHERE imported_at >= %s::timestamptz AND imported_at < %s::timestamptz
        GROUP BY source_type
        ORDER BY cnt DESC
        """,
        (week_start, week_end),
    )
    stats["documents_by_source"] = {row[0]: row[1] for row in rows}
    stats["total_documents"] = sum(row[1] for row in rows)

    # Chunks processed
    rows = _safe_query(
        """
        SELECT COUNT(*) FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.created_at >= %s::timestamptz AND d.created_at < %s::timestamptz
        """,
        (week_start, week_end),
    )
    stats["chunks_processed"] = rows[0][0] if rows else 0

    # Communication edges (may not exist)
    rows = _safe_query(
        """
        SELECT direction, COUNT(*) as cnt
        FROM communication_edges
        WHERE timestamp >= %s::timestamptz AND timestamp < %s::timestamptz
        GROUP BY direction
        """,
        (week_start, week_end),
    )
    stats["communication_edges"] = {row[0]: row[1] for row in rows}

    return stats


def _fetch_predictive_alerts(week_start: str, week_end: str) -> list[dict]:
    """Fetch active predictive alerts."""
    rows = _safe_query(
        """
        SELECT severity, title, description, detected_at, status
        FROM alerts
        WHERE detected_at >= %s::timestamptz AND detected_at < %s::timestamptz
        ORDER BY
            CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
            detected_at DESC
        LIMIT 20
        """,
        (week_start, week_end),
    )
    return [
        {
            "severity": row[0],
            "title": row[1],
            "description": row[2],
            "detected_at": row[3].isoformat() if row[3] else None,
            "status": row[4],
        }
        for row in rows
    ]


def _fetch_delegation_scores(week_start: str, week_end: str) -> list[dict]:
    """Fetch delegation effectiveness per person."""
    rows = _safe_query(
        """
        SELECT person_name, score, tasks_completed, tasks_total, measured_at
        FROM delegation_scores
        WHERE measured_at >= %s::timestamptz AND measured_at < %s::timestamptz
        ORDER BY score ASC
        LIMIT 20
        """,
        (week_start, week_end),
    )
    return [
        {
            "person": row[0],
            "score": float(row[1]) if row[1] else None,
            "completed": row[2],
            "total": row[3],
            "measured_at": row[4].isoformat() if row[4] else None,
        }
        for row in rows
    ]


def _fetch_blind_spots(week_start: str, week_end: str) -> list[dict]:
    """Fetch blind spots detected this week."""
    rows = _safe_query(
        """
        SELECT area, description, severity, detected_at
        FROM blind_spots
        WHERE detected_at >= %s::timestamptz AND detected_at < %s::timestamptz
        ORDER BY
            CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
        LIMIT 10
        """,
        (week_start, week_end),
    )
    return [
        {
            "area": row[0],
            "description": row[1],
            "severity": row[2],
            "detected_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]


# ============================================================
# Data fetcher
# ============================================================

def fetch_week_data(week_start: str) -> dict:
    """Gather all data for the week.

    Args:
        week_start: Monday of the target week (YYYY-MM-DD).

    Returns:
        Dict with all week data sections.
    """
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=7)).strftime("%Y-%m-%d")
    logger.info("Fetching week data: %s to %s", week_start, week_end)

    events, event_counts = _fetch_events(week_start, week_end)

    return {
        "events": events,
        "event_counts": event_counts,
        "commitments": _fetch_commitments(week_start, week_end),
        "opportunities": _fetch_opportunities(week_start, week_end),
        "sentiment_changes": _fetch_sentiment_changes(week_start, week_end),
        "wellbeing": _fetch_wellbeing(week_start, week_end),
        "calendar_next_week": _fetch_calendar_next_week(week_end),
        "communication_stats": _fetch_communication_stats(week_start, week_end),
        "predictive_alerts": _fetch_predictive_alerts(week_start, week_end),
        "delegation_scores": _fetch_delegation_scores(week_start, week_end),
        "blind_spots": _fetch_blind_spots(week_start, week_end),
    }


# ============================================================
# Context builder
# ============================================================

def build_synthesis_context(data: dict) -> str:
    """Build a structured context string for Claude synthesis."""
    parts: list[str] = []

    # Events grouped by type
    parts.append("=== WYDARZENIA TYGODNIA ===")
    if data["events"]:
        parts.append(f"Lacznie wydarzen: {len(data['events'])}")
        for etype, count in sorted(data["event_counts"].items(), key=lambda x: -x[1]):
            parts.append(f"  {etype}: {count}")
        parts.append("")
        for ev in data["events"][:100]:  # Top 100 for context
            line = f"[{ev['event_type']}] {ev['event_time'] or '?'}: {ev['summary']}"
            if ev.get("entities"):
                line += f" (osoby: {ev['entities']})"
            parts.append(line)
    else:
        parts.append("Brak wydarzen w tym tygodniu.")
    parts.append("")

    # Commitments
    parts.append("=== COMMITMENTS ===")
    commitments = data["commitments"]
    if any(commitments.values()):
        parts.append(f"Nowe: {len(commitments['new'])}, Fulfilled: {len(commitments['fulfilled'])}, "
                     f"Broken: {len(commitments['broken'])}, Overdue: {len(commitments['overdue'])}")
        for status_key in ("fulfilled", "broken", "overdue", "new"):
            for c in commitments[status_key]:
                parts.append(f"  [{status_key.upper()}] {c['person']}: {c['description']} (termin: {c['due_date']})")
    else:
        parts.append("Brak danych o commitmentach.")
    parts.append("")

    # Opportunities
    parts.append("=== SZANSE I RYZYKA ===")
    if data["opportunities"]:
        for opp in data["opportunities"]:
            value_str = f"{opp['value_pln']:,.0f} PLN" if opp.get("value_pln") else "brak wyceny"
            parts.append(f"  [{opp['type']}] {opp['description']} — {value_str} — status: {opp['status']}")
    else:
        parts.append("Brak danych o szansach.")
    parts.append("")

    # People — sentiment changes
    parts.append("=== LUDZIE — ZMIANY SENTYMENTU ===")
    if data["sentiment_changes"]:
        for sc in data["sentiment_changes"]:
            delta_str = f"{sc['delta']:+.1f}" if sc.get("delta") is not None else "?"
            parts.append(f"  {sc['person']}: {sc.get('previous', '?')} -> {sc.get('score', '?')} (delta: {delta_str})")
    else:
        parts.append("Brak danych o zmianach sentymentu.")
    parts.append("")

    # Delegation scores
    if data["delegation_scores"]:
        parts.append("=== DELEGACJA — EFEKTYWNOSC ===")
        for ds in data["delegation_scores"]:
            parts.append(f"  {ds['person']}: score {ds.get('score', '?')}, "
                        f"{ds.get('completed', '?')}/{ds.get('total', '?')} zadan")
        parts.append("")

    # Wellbeing
    parts.append("=== WELLBEING ===")
    if data["wellbeing"].get("scores"):
        for wb in data["wellbeing"]["scores"]:
            parts.append(f"  {wb['indicator']}: {wb.get('score', '?')} — {wb.get('notes', '')}")
    else:
        parts.append("Brak danych wellbeing.")
    parts.append("")

    # Calendar next week
    parts.append("=== KALENDARZ PRZYSZLY TYDZIEN ===")
    if data["calendar_next_week"]:
        for cal in data["calendar_next_week"]:
            line = f"  {cal.get('start', '?')}: {cal.get('subject', '?')}"
            if cal.get("attendees"):
                line += f" (uczestnicy: {', '.join(cal['attendees'][:5])})"
            parts.append(line)
    else:
        parts.append("Brak danych kalendarza.")
    parts.append("")

    # Predictive alerts
    parts.append("=== PREDICTIVE ALERTS ===")
    if data["predictive_alerts"]:
        for alert in data["predictive_alerts"]:
            parts.append(f"  [{alert['severity'].upper()}] {alert['title']}: {alert['description']}")
    else:
        parts.append("Brak alertow predykcyjnych.")
    parts.append("")

    # Blind spots
    parts.append("=== BLIND SPOTS ===")
    if data["blind_spots"]:
        for bs in data["blind_spots"]:
            parts.append(f"  [{bs.get('severity', '?')}] {bs['area']}: {bs['description']}")
    else:
        parts.append("Brak wykrytych blind spotow.")
    parts.append("")

    # Communication stats
    parts.append("=== STATYSTYKI KOMUNIKACJI ===")
    stats = data["communication_stats"]
    parts.append(f"Dokumenty przetworzone: {stats.get('total_documents', 0)}")
    if stats.get("documents_by_source"):
        for src, cnt in stats["documents_by_source"].items():
            parts.append(f"  {src}: {cnt}")
    parts.append(f"Chunki przetworzone: {stats.get('chunks_processed', 0)}")
    if stats.get("communication_edges"):
        for direction, cnt in stats["communication_edges"].items():
            parts.append(f"  {direction}: {cnt}")
    parts.append("")

    return "\n".join(parts)


# ============================================================
# Synthesis generation via Claude
# ============================================================

SYNTHESIS_SYSTEM_PROMPT = """
Jestes Gilbertus Albans — prywatnym mentatem Sebastiana Jablonskiego.
Generujesz tygodniowa synteze wykonawcza — strategiczny przeglad tygodnia.

Format (markdown):

## Podsumowanie tygodnia {week_label}
2-3 zdania: najwazniejsze co sie wydarzylo, ton tygodnia.

## Top 5 wydarzen
Najwazniejsze wydarzenia tygodnia rankowane po wplywie na biznes/zycie.
Dla kazdego: co, kiedy, kto, jaki wplyw, co dalej.

## Relacje — zmiany
Kto sie poprawil, kto pogorszyl (sentiment delta).
Nowe kontakty, zerwane kontakty.
Ludzie wymagajacy uwagi.

## Commitments
Tabela: osoba | obiecane | termin | status (fulfilled/broken/overdue)
Podsumowanie: completion rate ogolny i per osoba.

## Szanse i ryzyka
Wykryte w tym tygodniu: typ, wartosc PLN, status.
Zrealizowane vs pominiete.

## Wellbeing
Score tygodnia (1-10). Trend vs poprzedni tydzien.
Sygnaly: nocna praca, konflikty, family time, zdrowie.
Sugestie na przyszly tydzien.

## Prognoza: przyszly tydzien
Kalendarz: kluczowe spotkania.
Ryzyka: predictive alerts.
Sugestie: na co zwrocic uwage.

## Metryki
- Dokumenty przetworzone: X
- Emaili wyslanych w imieniu Sebastiana: X
- Commitments: X nowych, X fulfilled, X broken
- Opportunities: X znalezionych, ~X PLN wartosci
- Standing orders: X aktywnych

Zasady:
- Opieraj sie WYLACZNIE na dostarczonych danych
- Badz konkretny — nazwiska, daty, liczby
- Pisz po polsku
- Jesli brak danych na sekcje, napisz "Brak danych"
- Format: czysty markdown
""".strip()


def generate_synthesis(context: str, week_label: str) -> str:
    """Call Claude Sonnet to generate the weekly synthesis."""
    system_prompt = SYNTHESIS_SYSTEM_PROMPT.replace("{week_label}", week_label)

    user_prompt = (
        f"Tydzien: {week_label}\n\n"
        f"Dane zrodlowe z calego tygodnia:\n\n{context}"
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error("Anthropic API error: %s", e)
        return f"Blad generowania syntezy: {e}"
    except Exception as e:
        logger.error("Unexpected error calling Anthropic: %s", e)
        return f"Blad generowania syntezy: {e}"

    from app.db.cost_tracker import log_anthropic_cost
    if hasattr(response, "usage"):
        log_anthropic_cost(ANTHROPIC_MODEL, "retrieval.weekly_synthesis", response.usage)

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "\n".join(parts).strip()


# ============================================================
# Save to database
# ============================================================

def save_synthesis(week_start: str, text: str) -> int:
    """Save weekly synthesis to summaries table. Upserts by type + period."""
    summary_type = "weekly_synthesis"
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=7)).strftime("%Y-%m-%d")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM summaries
                WHERE summary_type = %s AND period_start = %s AND period_end = %s
                """,
                (summary_type, week_start, week_end),
            )
            cur.execute(
                """
                INSERT INTO summaries (summary_type, period_start, period_end, text)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (summary_type, week_start, week_end, text),
            )
            row = cur.fetchone()
        conn.commit()

    return row[0]


# ============================================================
# WhatsApp notification
# ============================================================

def _send_whatsapp(message: str) -> None:
    """Send abbreviated synthesis to Sebastian via WhatsApp."""
    openclaw_bin = os.getenv("OPENCLAW_BIN", "/usr/local/bin/openclaw")
    target = os.getenv("WA_TARGET", "+48505441635")
    try:
        subprocess.run(
            [openclaw_bin, "message", "send", "--channel", "whatsapp",
             "--target", target, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        logger.warning("WhatsApp send failed: %s", e)


# ============================================================
# Existing synthesis check
# ============================================================

def get_existing_synthesis(week_start: str) -> dict[str, Any] | None:
    """Retrieve an already-generated synthesis for a given week."""
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=7)).strftime("%Y-%m-%d")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, summary_type, period_start, period_end, text
                FROM summaries
                WHERE summary_type = 'weekly_synthesis'
                  AND period_start = %s::timestamptz
                  AND period_end = %s::timestamptz
                ORDER BY id DESC
                LIMIT 1
                """,
                (week_start, week_end),
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "summary_id": row[0],
        "summary_type": row[1],
        "period_start": row[2].isoformat() if row[2] else None,
        "period_end": row[3].isoformat() if row[3] else None,
        "text": row[4],
    }


# ============================================================
# Main pipeline
# ============================================================

def _calculate_week_start(date: str | None) -> str:
    """Calculate Monday of the week containing the given date."""
    if date is None:
        dt = datetime.now(tz=timezone.utc)
    else:
        dt = datetime.fromisoformat(date)

    # Go back to Monday
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def generate_weekly_synthesis(
    date: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Full pipeline: calculate week -> query DB -> build context -> generate via Claude -> save -> notify.

    Args:
        date: Any date in the target week (YYYY-MM-DD). Defaults to current week.
        force: If True, regenerate even if synthesis already exists.

    Returns:
        Dict with synthesis metadata and text.
    """
    week_start = _calculate_week_start(date)
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=7)).strftime("%Y-%m-%d")
    week_label = f"{week_start} — {week_end}"

    logger.info("Weekly synthesis for week: %s", week_label)

    # Check for existing synthesis unless forced
    if not force:
        existing = get_existing_synthesis(week_start)
        if existing:
            logger.info("Synthesis for week %s already exists (id=%s)", week_start, existing["summary_id"])
            return {
                "status": "exists",
                "week_start": week_start,
                "week_end": week_end,
                **existing,
            }

    # Fetch all week data
    data = fetch_week_data(week_start)

    # Check if we have any meaningful data
    total_data = (
        len(data["events"])
        + len(data["commitments"].get("new", []))
        + len(data["opportunities"])
        + len(data["sentiment_changes"])
        + len(data["calendar_next_week"])
        + len(data["predictive_alerts"])
    )

    if total_data == 0:
        logger.warning("No data found for weekly synthesis (%s)", week_label)
        return {
            "status": "no_data",
            "week_start": week_start,
            "week_end": week_end,
            "events_count": 0,
            "text": None,
        }

    # Build context and generate
    context = build_synthesis_context(data)
    synthesis_text = generate_synthesis(context, week_label)

    # Save
    summary_id = save_synthesis(week_start, synthesis_text)

    logger.info(
        "Weekly synthesis generated: id=%s, events=%d, commitments=%d, opportunities=%d",
        summary_id, len(data["events"]),
        len(data["commitments"].get("new", [])),
        len(data["opportunities"]),
    )

    # Send abbreviated version to WhatsApp
    if synthesis_text and not synthesis_text.startswith("Blad"):
        wa_text = f"Tygodniowa synteza ({week_label}):\n\n{synthesis_text[:1500]}"
        if len(synthesis_text) > 1500:
            wa_text += "\n\n[...skrocone — pelna wersja w systemie]"
        _send_whatsapp(wa_text)

    return {
        "status": "generated",
        "summary_id": summary_id,
        "week_start": week_start,
        "week_end": week_end,
        "events_count": len(data["events"]),
        "event_counts": data["event_counts"],
        "commitments_count": sum(len(v) for v in data["commitments"].values()),
        "opportunities_count": len(data["opportunities"]),
        "sentiment_changes_count": len(data["sentiment_changes"]),
        "calendar_next_week_count": len(data["calendar_next_week"]),
        "alerts_count": len(data["predictive_alerts"]),
        "blind_spots_count": len(data["blind_spots"]),
        "text": synthesis_text,
    }


# ============================================================
# CLI
# ============================================================

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = {"date": None, "force": False}
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--date":
            args["date"] = sys.argv[i + 1]
            i += 2
        elif arg == "--force":
            args["force"] = True
            i += 1
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            raise ValueError(f"Unknown argument: {arg}")

    result = generate_weekly_synthesis(date=args["date"], force=args["force"])

    if result["status"] == "no_data":
        print("Brak danych do wygenerowania syntezy tygodniowej.")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    if result["status"] == "exists":
        print(f"Synteza na ten tydzien juz istnieje (id={result['summary_id']}).")
        print("Uzyj --force aby wygenerowac ponownie.\n")

    if result.get("text"):
        print(result["text"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
