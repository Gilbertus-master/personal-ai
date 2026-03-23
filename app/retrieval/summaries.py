"""
Summary generation pipeline for Gilbertus Albans.
Generates daily/weekly summaries by area (general, relationships, business, trading, wellbeing).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from anthropic import Anthropic, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=90.0)

SUMMARY_TYPES = ["daily", "weekly"]
AREAS = ["general", "relationships", "business", "trading", "wellbeing"]

AREA_KEYWORDS = {
    "relationships": [
        "Zosia", "mama", "tata", "rodzina", "family", "relacja", "kłótnia", "wsparcie",
        "miłość", "konflikt", "rozmowa", "partner", "żona", "mąż", "dziecko",
    ],
    "business": [
        "projekt", "firma", "klient", "sprzedaż", "B2C", "B2B", "energy", "energia",
        "spotkanie", "meeting", "deadline", "budżet", "umowa", "kontrakt", "biznes",
    ],
    "trading": [
        "trading", "giełda", "akcje", "futures", "opcje", "portfolio", "pozycja",
        "stop loss", "take profit", "analiza techniczna", "rynek", "S&P", "NASDAQ",
    ],
    "wellbeing": [
        "zdrowie", "health", "ASD", "ADHD", "terapia", "psycholog", "diagnoza",
        "sen", "stres", "medytacja", "ćwiczenia", "leki", "samopoczucie",
    ],
}


def fetch_chunks_for_period(
    date_from: str,
    date_to: str,
    area: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch chunks from a given time period, optionally filtered by area keywords."""
    base_query = """
    SELECT c.id, c.text, d.title, s.source_type, s.source_name, d.created_at
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    JOIN sources s ON d.source_id = s.id
    WHERE d.created_at >= %s::timestamptz
      AND d.created_at < %s::timestamptz
      AND length(c.text) > 50
    ORDER BY d.created_at, c.chunk_index
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(base_query, (date_from, date_to))
            rows = cur.fetchall()

    chunks = []
    for row in rows:
        chunk = {
            "chunk_id": row[0],
            "text": row[1],
            "title": row[2],
            "source_type": row[3],
            "source_name": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
        }
        chunks.append(chunk)

    if area and area != "general" and area in AREA_KEYWORDS:
        keywords = AREA_KEYWORDS[area]
        filtered = []
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            if any(kw.lower() in text_lower for kw in keywords):
                filtered.append(chunk)
        chunks = filtered

    return chunks[:limit]


def fetch_events_for_period(
    date_from: str,
    date_to: str,
) -> list[dict[str, Any]]:
    """Fetch extracted events from a given time period."""
    query = """
    SELECT e.event_type, e.event_time, e.summary,
           COALESCE(string_agg(DISTINCT en.canonical_name, ', '), '') as entities
    FROM events e
    LEFT JOIN event_entities ee ON ee.event_id = e.id
    LEFT JOIN entities en ON en.id = ee.entity_id
    WHERE e.event_time >= %s::timestamptz
      AND e.event_time < %s::timestamptz
    GROUP BY e.id, e.event_type, e.event_time, e.summary
    ORDER BY e.event_time
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (date_from, date_to))
            rows = cur.fetchall()

    return [
        {
            "event_type": row[0],
            "event_time": row[1].isoformat() if row[1] else None,
            "summary": row[2],
            "entities": row[3],
        }
        for row in rows
    ]


def build_summary_context(
    chunks: list[dict[str, Any]],
    events: list[dict[str, Any]],
    max_chars: int = 30000,
) -> str:
    """Build context string for LLM summary generation."""
    parts = []

    if events:
        parts.append("=== WYEKSTRAHOWANE WYDARZENIA ===")
        for e in events[:50]:
            parts.append(f"[{e['event_type']}] {e['event_time'] or '?'}: {e['summary']}")
            if e["entities"]:
                parts.append(f"  Osoby/encje: {e['entities']}")
        parts.append("")

    parts.append("=== FRAGMENTY ŹRÓDŁOWE ===")
    total_chars = sum(len(p) for p in parts)

    for chunk in chunks:
        entry = f"\n[{chunk['source_type']}/{chunk['source_name']}] {chunk['created_at'] or ''}\n{chunk['text'][:500]}"
        if total_chars + len(entry) > max_chars:
            break
        parts.append(entry)
        total_chars += len(entry)

    return "\n".join(parts)


def generate_summary(
    period_label: str,
    area: str,
    context: str,
    summary_type: str = "daily",
) -> str:
    """Generate a summary using Claude."""
    area_instruction = {
        "general": "Zrób ogólne podsumowanie — najważniejsze tematy, wydarzenia, obserwacje.",
        "relationships": "Skup się na relacjach międzyludzkich — rozmowy, konflikty, wsparcie, dynamika.",
        "business": "Skup się na pracy i biznesie — projekty, decyzje, spotkania, postępy.",
        "trading": "Skup się na tradingu i inwestycjach — pozycje, analizy, decyzje, wyniki.",
        "wellbeing": "Skup się na zdrowiu i samopoczuciu — zdrowie psychiczne, fizyczne, terapia, rutyny.",
    }.get(area, "Zrób ogólne podsumowanie.")

    length_instruction = "3-5 punktów" if summary_type == "daily" else "5-10 punktów"

    system_prompt = f"""
Jesteś analitycznym asystentem pracującym na prywatnym archiwum danych użytkownika.

Twoje zadanie: wygeneruj {summary_type} podsumowanie za okres: {period_label}.
Obszar: {area}.

{area_instruction}

Zasady:
- Opieraj się wyłącznie na dostarczonym kontekście.
- Nie zmyślaj faktów.
- Pisz po polsku.
- Bądź konkretny — podawaj nazwiska, daty, szczegóły.
- Wyodrębnij {length_instruction} najważniejszych obserwacji.
- Na końcu dodaj sekcję "Otwarte pętle" — rzeczy, które wymagają uwagi lub kontynuacji.
- Format: markdown z nagłówkami ##.
"""

    user_prompt = f"Materiał źródłowy za okres {period_label}:\n\n{context}"

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except (APIConnectionError, APITimeoutError) as e:
        return f"Błąd generowania podsumowania: {e}"
    except Exception as e:
        return f"Błąd generowania podsumowania: {e}"

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "\n".join(parts).strip()


def save_summary(
    summary_type: str,
    period_start: str,
    period_end: str,
    text: str,
    area: str = "general",
) -> int:
    """Save a summary to the database."""
    full_type = f"{summary_type}_{area}"

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Upsert: replace if same type + period exists
            cur.execute(
                """
                DELETE FROM summaries
                WHERE summary_type = %s AND period_start = %s AND period_end = %s
                """,
                (full_type, period_start, period_end),
            )
            cur.execute(
                """
                INSERT INTO summaries (summary_type, period_start, period_end, text)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (full_type, period_start, period_end, text),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def generate_period_summary(
    date_from: str,
    date_to: str,
    summary_type: str = "daily",
    area: str = "general",
) -> dict[str, Any]:
    """Full pipeline: fetch data → generate summary → save."""
    chunks = fetch_chunks_for_period(date_from, date_to, area=area)
    events = fetch_events_for_period(date_from, date_to)

    if not chunks and not events:
        return {
            "summary_type": summary_type,
            "area": area,
            "period": f"{date_from} → {date_to}",
            "status": "no_data",
            "text": None,
        }

    period_label = f"{date_from} do {date_to}"
    context = build_summary_context(chunks, events)
    text = generate_summary(period_label, area, context, summary_type)
    summary_id = save_summary(summary_type, date_from, date_to, text, area)

    return {
        "summary_id": summary_id,
        "summary_type": summary_type,
        "area": area,
        "period": f"{date_from} → {date_to}",
        "status": "generated",
        "chunks_used": len(chunks),
        "events_used": len(events),
        "text": text,
    }


def generate_daily_summaries(date: str, areas: list[str] | None = None) -> list[dict[str, Any]]:
    """Generate daily summaries for a given date across all areas."""
    areas = areas or AREAS
    date_from = date
    date_to_dt = datetime.fromisoformat(date) + timedelta(days=1)
    date_to = date_to_dt.strftime("%Y-%m-%d")

    results = []
    for area in areas:
        result = generate_period_summary(date_from, date_to, "daily", area)
        results.append(result)
    return results


def generate_weekly_summaries(week_start: str, areas: list[str] | None = None) -> list[dict[str, Any]]:
    """Generate weekly summaries starting from a given Monday."""
    areas = areas or AREAS
    start_dt = datetime.fromisoformat(week_start)
    end_dt = start_dt + timedelta(days=7)
    date_to = end_dt.strftime("%Y-%m-%d")

    results = []
    for area in areas:
        result = generate_period_summary(week_start, date_to, "weekly", area)
        results.append(result)
    return results


def get_summaries(
    summary_type: str | None = None,
    area: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query existing summaries from the database."""
    where_clauses = []
    params: list[Any] = []

    if summary_type and area:
        where_clauses.append("summary_type = %s")
        params.append(f"{summary_type}_{area}")
    elif summary_type:
        where_clauses.append("summary_type LIKE %s")
        params.append(f"{summary_type}_%")
    elif area:
        where_clauses.append("summary_type LIKE %s")
        params.append(f"%_{area}")

    if date_from:
        where_clauses.append("period_start >= %s::timestamptz")
        params.append(date_from)

    if date_to:
        where_clauses.append("period_end <= %s::timestamptz")
        params.append(date_to)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    params.append(limit)

    query = f"""
    SELECT id, summary_type, period_start, period_end, text
    FROM summaries
    {where_sql}
    ORDER BY period_start DESC
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [
        {
            "summary_id": row[0],
            "summary_type": row[1],
            "period_start": row[2].isoformat() if row[2] else None,
            "period_end": row[3].isoformat() if row[3] else None,
            "text": row[4],
        }
        for row in rows
    ]
