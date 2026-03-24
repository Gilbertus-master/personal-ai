"""
Morning brief generator for Gilbertus Albans.

Generates a daily morning brief for Sebastian by querying events, entities,
open loops, and recent summaries — then synthesizing them via Claude.

Usage:
    python -m app.retrieval.morning_brief
    python -m app.retrieval.morning_brief --date 2026-03-20
    python -m app.retrieval.morning_brief --days 14
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

from anthropic import Anthropic, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

DEFAULT_LOOKBACK_DAYS = 7


# ============================================================
# Database queries
# ============================================================

def fetch_recent_events(
    date_from: str,
    date_to: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch events from the last N days with linked entities."""
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
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (date_from, date_to, limit))
            rows = cur.fetchall()

    return [
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


def fetch_open_loops(
    date_from: str,
    date_to: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Find events that look like open loops: decisions, commitments, tasks,
    questions — that don't have a follow-up event with similar entities
    in the subsequent days.
    """
    query = """
    WITH recent_events AS (
        SELECT
            e.id,
            e.event_type,
            e.event_time,
            e.summary,
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
          AND e.event_type IN (
              'decision', 'commitment', 'task', 'question',
              'plan', 'request', 'deadline', 'follow_up',
              'conflict', 'problem', 'goal'
          )
        GROUP BY e.id, e.event_type, e.event_time, e.summary
        ORDER BY e.event_time DESC
    )
    SELECT id, event_type, event_time, summary, entities
    FROM recent_events
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (date_from, date_to, limit))
            rows = cur.fetchall()

    return [
        {
            "event_id": row[0],
            "event_type": row[1],
            "event_time": row[2].isoformat() if row[2] else None,
            "summary": row[3],
            "entities": row[4],
        }
        for row in rows
    ]


def fetch_active_entities(
    date_from: str,
    date_to: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """
    Find entities (people, organizations) most active in recent events
    and chunk mentions.
    """
    query = """
    WITH entity_event_counts AS (
        SELECT
            en.id,
            en.canonical_name,
            en.entity_type,
            COUNT(DISTINCT ee.event_id) AS event_count,
            COALESCE(
                string_agg(
                    DISTINCT LEFT(e.summary, 120), ' | '
                    ORDER BY LEFT(e.summary, 120)
                ),
                ''
            ) AS event_summaries
        FROM entities en
        JOIN event_entities ee ON ee.entity_id = en.id
        JOIN events e ON e.id = ee.event_id
        WHERE e.event_time >= %s::timestamptz
          AND e.event_time < %s::timestamptz
          AND en.entity_type IN ('person', 'organization')
        GROUP BY en.id, en.canonical_name, en.entity_type
    ),
    entity_chunk_counts AS (
        SELECT
            en.id,
            COUNT(DISTINCT ce.chunk_id) AS chunk_count
        FROM entities en
        JOIN chunk_entities ce ON ce.entity_id = en.id
        JOIN chunks c ON c.id = ce.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE d.created_at >= %s::timestamptz
          AND d.created_at < %s::timestamptz
          AND en.entity_type IN ('person', 'organization')
        GROUP BY en.id
    )
    SELECT
        eec.canonical_name,
        eec.entity_type,
        eec.event_count,
        COALESCE(ecc.chunk_count, 0) AS chunk_count,
        eec.event_summaries
    FROM entity_event_counts eec
    LEFT JOIN entity_chunk_counts ecc ON ecc.id = eec.id
    ORDER BY eec.event_count + COALESCE(ecc.chunk_count, 0) DESC
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (date_from, date_to, date_from, date_to, limit))
            rows = cur.fetchall()

    return [
        {
            "name": row[0],
            "entity_type": row[1],
            "event_count": row[2],
            "chunk_count": row[3],
            "context": row[4],
        }
        for row in rows
    ]


def fetch_recent_summaries(
    date_from: str,
    date_to: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent generated summaries (daily/weekly) for extra context."""
    query = """
    SELECT summary_type, period_start, period_end, text
    FROM summaries
    WHERE period_start >= %s::timestamptz
      AND period_end <= %s::timestamptz
      AND summary_type NOT LIKE 'morning_brief%%'
    ORDER BY period_start DESC
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (date_from, date_to, limit))
            rows = cur.fetchall()

    return [
        {
            "summary_type": row[0],
            "period_start": row[1].isoformat() if row[1] else None,
            "period_end": row[2].isoformat() if row[2] else None,
            "text": row[3],
        }
        for row in rows
    ]


# ============================================================
# Context builder
# ============================================================

def build_brief_context(
    events: list[dict[str, Any]],
    open_loops: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    max_chars: int = 40000,
) -> str:
    """Assemble all data into a single context string for Claude."""
    parts: list[str] = []
    total_chars = 0

    # Events
    if events:
        parts.append("=== WYDARZENIA Z OSTATNICH DNI ===")
        for e in events:
            line = f"[{e['event_type']}] {e['event_time'] or '?'}: {e['summary']}"
            if e.get("entities"):
                line += f" (osoby: {e['entities']})"
            parts.append(line)
            total_chars += len(line)
            if total_chars > max_chars * 0.35:
                break
        parts.append("")

    # Open loops
    if open_loops:
        parts.append("=== OTWARTE PETLA / NIEROZWIAZANE SPRAWY ===")
        for ol in open_loops:
            line = f"[{ol['event_type']}] {ol['event_time'] or '?'}: {ol['summary']}"
            if ol.get("entities"):
                line += f" (dotyczy: {ol['entities']})"
            parts.append(line)
            total_chars += len(line)
            if total_chars > max_chars * 0.6:
                break
        parts.append("")

    # Entities
    if entities:
        parts.append("=== AKTYWNE OSOBY / ORGANIZACJE ===")
        for ent in entities:
            line = (
                f"{ent['name']} ({ent['entity_type']}): "
                f"{ent['event_count']} wydarzen, {ent['chunk_count']} wzmianek"
            )
            if ent.get("context"):
                line += f"\n  Kontekst: {ent['context'][:300]}"
            parts.append(line)
            total_chars += len(line)
            if total_chars > max_chars * 0.8:
                break
        parts.append("")

    # Summaries
    if summaries:
        parts.append("=== ISTNIEJACE PODSUMOWANIA ===")
        for s in summaries:
            header = f"[{s['summary_type']}] {s['period_start']} - {s['period_end']}"
            text = s["text"] or ""
            remaining = max_chars - total_chars - len(header) - 10
            if remaining < 100:
                break
            text_trimmed = text[:min(len(text), remaining)]
            parts.append(f"{header}\n{text_trimmed}")
            total_chars += len(header) + len(text_trimmed)
        parts.append("")

    return "\n".join(parts)


# ============================================================
# Brief generation via Claude
# ============================================================

BRIEF_SYSTEM_PROMPT = """
Jestes Gilbertus Albans — prywatnym asystentem analitycznym Sebastiana.
Twoje zadanie: wygenerowac poranny brief na podstawie dostarczonych danych.

Brief musi zawierac dokladnie 4 sekcje w formacie markdown:

## Focus dzis
Top 3 sprawy wymagajace uwagi dzisiaj. Priorytetyzuj: deadliny > konflikty > decyzje > rutynowe.
Kazdy punkt: konkretna sprawa + dlaczego wymaga uwagi + sugerowane nastepne dzialanie.

## Otwarte petle
Nierozwiazane sprawy z ostatniego tygodnia. Dla kazdej:
- Co to za sprawa
- Kiedy sie pojawila
- Kto jest zaangazowany
- Co powinno byc nastepnym krokiem

## Ludzie
Kto byl aktywny w zyciu Sebastiana ostatnio. Dla kazdej osoby:
- W jakim kontekscie sie pojawila
- Jaki jest stan relacji / interakcji
- Czy cos wymaga reakcji

## Anomalie
Nietypowe wzorce, zmiany, odstepstwa od normy. Np.:
- Ktos, kto zwykle sie nie odzywa, nagle jest aktywny
- Temat, ktory wraca wielokrotnie
- Zmiana tonu w komunikacji
- Nietypowe godziny aktywnosci

Zasady:
- Opieraj sie WYLACZNIE na dostarczonym kontekscie. Nie zmyslaj.
- Pisz po polsku.
- Badz konkretny — nazwiska, daty, szczegoly.
- Jezeli brak danych na ktoras sekcje, napisz "Brak danych za ten okres."
- Jezeli danych jest malo, skroc brief — nie lej wody.
- Format: czysty markdown.
"""


def generate_brief_text(
    context: str,
    date_label: str,
) -> str:
    """Call Claude to generate the morning brief text."""
    user_prompt = (
        f"Dzisiaj jest: {date_label}.\n\n"
        f"Dane zrodlowe z ostatnich dni:\n\n{context}"
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=3000,
            temperature=0.2,
            system=BRIEF_SYSTEM_PROMPT.strip(),
            messages=[{"role": "user", "content": user_prompt}],
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error("Anthropic API error: %s", e)
        return f"Blad generowania briefu: {e}"
    except Exception as e:
        logger.error("Unexpected error calling Anthropic: %s", e)
        return f"Blad generowania briefu: {e}"

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "\n".join(parts).strip()


# ============================================================
# Save to database
# ============================================================

def save_brief(
    period_start: str,
    period_end: str,
    text: str,
) -> int:
    """Save morning brief to summaries table. Upserts by type + period."""
    summary_type = "morning_brief"

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM summaries
                WHERE summary_type = %s AND period_start = %s AND period_end = %s
                """,
                (summary_type, period_start, period_end),
            )
            cur.execute(
                """
                INSERT INTO summaries (summary_type, period_start, period_end, text)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (summary_type, period_start, period_end, text),
            )
            row = cur.fetchone()
        conn.commit()

    return row[0]


# ============================================================
# Fetch existing brief
# ============================================================

def get_todays_brief(date: str | None = None) -> dict[str, Any] | None:
    """Retrieve an already-generated brief for a given date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    date_start = date
    date_end = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, summary_type, period_start, period_end, text
                FROM summaries
                WHERE summary_type = 'morning_brief'
                  AND period_end = %s::timestamptz
                ORDER BY period_start DESC
                LIMIT 1
                """,
                (date_end,),
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

def generate_morning_brief(
    date: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    force: bool = False,
) -> dict[str, Any]:
    """
    Full pipeline: query DB -> build context -> generate via Claude -> save.

    Args:
        date: Target date (YYYY-MM-DD). Defaults to today.
        lookback_days: How many days back to look for data.
        force: If True, regenerate even if brief already exists.

    Returns:
        Dict with brief metadata and text.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    date_to = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")
    date_from = (
        datetime.fromisoformat(date) - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    # Check for existing brief unless forced
    if not force:
        existing = get_todays_brief(date)
        if existing:
            logger.info("Brief for %s already exists (id=%s)", date, existing["summary_id"])
            return {
                "status": "exists",
                "date": date,
                **existing,
            }

    logger.info(
        "Generating morning brief for %s (lookback: %s - %s)",
        date, date_from, date_to,
    )

    # Fetch all data
    events = fetch_recent_events(date_from, date_to)
    open_loops = fetch_open_loops(date_from, date_to)
    entities = fetch_active_entities(date_from, date_to)
    summaries = fetch_recent_summaries(date_from, date_to)

    total_data = len(events) + len(open_loops) + len(entities) + len(summaries)

    if total_data == 0:
        logger.warning("No data found for morning brief (%s - %s)", date_from, date_to)
        return {
            "status": "no_data",
            "date": date,
            "period_start": date_from,
            "period_end": date_to,
            "events_count": 0,
            "open_loops_count": 0,
            "entities_count": 0,
            "summaries_count": 0,
            "text": None,
        }

    # Build context and generate
    context = build_brief_context(events, open_loops, entities, summaries)
    date_label = datetime.fromisoformat(date).strftime("%A, %d %B %Y")
    brief_text = generate_brief_text(context, date_label)

    # Save
    summary_id = save_brief(date_from, date_to, brief_text)

    logger.info(
        "Morning brief generated: id=%s, events=%d, open_loops=%d, entities=%d",
        summary_id, len(events), len(open_loops), len(entities),
    )

    return {
        "status": "generated",
        "summary_id": summary_id,
        "date": date,
        "period_start": date_from,
        "period_end": date_to,
        "events_count": len(events),
        "open_loops_count": len(open_loops),
        "entities_count": len(entities),
        "summaries_count": len(summaries),
        "text": brief_text,
    }


# ============================================================
# CLI
# ============================================================

def parse_cli_args() -> dict[str, Any]:
    """Parse CLI arguments."""
    args: dict[str, Any] = {
        "date": None,
        "days": DEFAULT_LOOKBACK_DAYS,
        "force": False,
    }

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--date":
            args["date"] = sys.argv[i + 1]
            i += 2
        elif arg == "--days":
            args["days"] = int(sys.argv[i + 1])
            i += 2
        elif arg == "--force":
            args["force"] = True
            i += 1
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            raise ValueError(f"Unknown argument: {arg}")

    return args


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = parse_cli_args()
    result = generate_morning_brief(
        date=args["date"],
        lookback_days=args["days"],
        force=args["force"],
    )

    if result["status"] == "no_data":
        print("Brak danych do wygenerowania briefu.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    if result["status"] == "exists":
        print(f"Brief na dzis juz istnieje (id={result['summary_id']}).")
        print("Uzyj --force aby wygenerowac ponownie.\n")

    if result.get("text"):
        print(result["text"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
