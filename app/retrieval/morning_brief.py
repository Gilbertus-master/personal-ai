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

import concurrent.futures
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from anthropic import Anthropic, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.retrieval.alerts import run_alerts_check

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

DEFAULT_LOOKBACK_DAYS = 14


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


def fetch_today_calendar(date: str) -> list[dict[str, Any]]:
    """Fetch today's calendar events with relationship context for each participant."""
    try:
        from app.ingestion.graph_api.calendar_sync import get_today_events
        from app.ingestion.graph_api.auth import get_access_token

        def _fetch() -> list[dict]:
            token = get_access_token()
            return get_today_events(token)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch)
            events = future.result(timeout=15)
    except concurrent.futures.TimeoutError:
        logger.warning("Calendar fetch timed out after 15 s")
        return []
    except Exception as e:
        logger.warning("Calendar fetch failed: %s", e)
        return []

    results = []
    for ev in events:
        subject = ev.get("subject", "(no subject)")
        start = ev.get("start", {}).get("dateTime", "?")[:16]
        end = ev.get("end", {}).get("dateTime", "?")[:16]
        is_cancelled = ev.get("isCancelled", False)

        if is_cancelled:
            continue

        attendees = []
        for att in ev.get("attendees", []):
            email_obj = att.get("emailAddress", {})
            name = email_obj.get("name", email_obj.get("address", "?"))
            attendees.append(name)

        organizer = ev.get("organizer", {}).get("emailAddress", {}).get("name", "?")

        # Get relationship context for each attendee
        participant_context = []
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for att_name in attendees[:5]:  # limit to 5 to keep context manageable
                    # Match attendee to known person via entity bridge
                    cur.execute("""
                        SELECT p.first_name || ' ' || p.last_name as name,
                               r.person_role, r.organization, r.status, r.sentiment,
                               (SELECT COUNT(*) FROM chunk_entities ce WHERE ce.entity_id = p.entity_id) as mentions
                        FROM people p
                        LEFT JOIN relationships r ON r.person_id = p.id
                        WHERE p.entity_id IN (
                            SELECT id FROM entities
                            WHERE entity_type = 'person'
                              AND canonical_name %% %s
                              AND similarity(canonical_name, %s) > 0.5
                        )
                        LIMIT 1
                    """, (att_name, att_name))
                    rows = cur.fetchall()
                    row = rows[0] if rows else None
                    if row:
                        participant_context.append({
                            "name": row[0], "role": row[1], "org": row[2],
                            "status": row[3], "sentiment": row[4], "mentions": row[5],
                        })

                # Get open loops for meeting participants
                for pc in participant_context:
                    try:
                        cur.execute("""
                            SELECT description, status FROM relationship_open_loops
                            WHERE person_id = (SELECT id FROM people WHERE first_name || ' ' || last_name = %s LIMIT 1)
                              AND status = 'open'
                            LIMIT 3
                        """, (pc["name"],))
                        pc["open_loops"] = [{"description": r[0]} for r in cur.fetchall()]
                    except Exception:
                        pc["open_loops"] = []

        results.append({
            "subject": subject,
            "start": start,
            "end": end,
            "organizer": organizer,
            "attendees": attendees,
            "participant_context": participant_context,
        })

    return results


def fetch_market_insights(limit: int = 5) -> list[dict[str, Any]]:
    """Fetch recent high-relevance market insights for morning brief."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT insight_type, title, description, impact_assessment,
                           relevance_score, created_at
                    FROM market_insights
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    AND relevance_score >= 50
                    ORDER BY relevance_score DESC
                    LIMIT %s
                """, (limit,))
                return [
                    {"type": r[0], "title": r[1], "description": r[2],
                     "impact": r[3], "relevance": r[4], "created_at": str(r[5])}
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.warning("Market insights fetch failed: %s", e)
        return []


def fetch_competitor_signals(limit: int = 5) -> list[dict[str, Any]]:
    """Fetch recent competitor signals for morning brief."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.name, cs.signal_type, cs.title, cs.description, cs.severity
                    FROM competitor_signals cs
                    JOIN competitors c ON c.id = cs.competitor_id
                    WHERE cs.created_at > NOW() - INTERVAL '48 hours'
                    ORDER BY
                        CASE cs.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                        cs.created_at DESC
                    LIMIT %s
                """, (limit,))
                return [
                    {"competitor": r[0], "type": r[1], "title": r[2],
                     "description": r[3], "severity": r[4]}
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.warning("Competitor signals fetch failed: %s", e)
        return []


def fetch_predictive_alerts(limit: int = 5) -> list[dict[str, Any]]:
    """Fetch active predictive alerts for morning brief."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT alert_type, prediction, probability, suggested_action
                    FROM predictive_alerts
                    WHERE status = 'active' AND probability >= 0.5
                    ORDER BY probability DESC
                    LIMIT %s
                """, (limit,))
                return [
                    {"type": r[0], "prediction": r[1], "probability": float(r[2]),
                     "action": r[3]}
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.warning("Predictive alerts fetch failed: %s", e)
        return []


def fetch_compliance_status() -> dict[str, Any]:
    """Fetch compliance data for morning brief."""
    try:
        from app.analysis.legal_compliance import get_compliance_dashboard
        return get_compliance_dashboard()
    except Exception as e:
        logger.warning("Compliance dashboard fetch failed: %s", e)
        return {}


def fetch_strategic_radar() -> dict[str, Any] | None:
    """Fetch latest strategic radar snapshot for morning brief."""
    try:
        from app.analysis.strategic_radar import get_radar_history
        history = get_radar_history(days=1)
        if history:
            latest = history[0]
            return {
                "patterns": latest.get("patterns", []),
                "recommendations": latest.get("recommendations", []),
                "radar_summary": latest.get("radar_data", {}).get("summary", {}),
                "created_at": latest.get("created_at"),
            }
    except Exception as e:
        logger.warning("Strategic radar fetch failed: %s", e)
    return None


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

def _render_calendar_section(calendar: list[dict[str, Any]], max_chars: int) -> tuple[list[str], int]:
    """Render calendar section for brief context."""
    parts = ["=== DZISIEJSZY KALENDARZ ==="]
    chars = 0
    for cal in calendar:
        line = f"{cal['start']}-{cal['end']}: {cal['subject']}"
        if cal.get("attendees"):
            line += f" (uczestnicy: {', '.join(cal['attendees'][:5])})"
        parts.append(line)
        for pc in cal.get("participant_context", []):
            ctx = f"  \u2192 {pc['name']}: {pc.get('role', '?')} @ {pc.get('org', '?')}, {pc.get('mentions', 0)} wzmianek"
            if pc.get("sentiment"):
                ctx += f", sentiment: {pc['sentiment']}"
            parts.append(ctx)
            for ol in pc.get("open_loops", []):
                parts.append(f"    \u26a1 Open loop: {ol['description']}")
        chars += len(line) * 2
        if chars > max_chars * 0.2:
            break
    parts.append("")
    return parts, chars


def _render_items_section(title: str, items: list[dict[str, Any]], format_fn, max_chars_pct: float, total_chars: int, max_chars: int) -> tuple[list[str], int]:
    """Generic renderer for brief sections."""
    if not items:
        return [], total_chars
    parts = [f"=== {title} ==="]
    for item in items:
        line = format_fn(item)
        parts.append(line)
        total_chars += len(line)
        if total_chars > max_chars * max_chars_pct:
            break
    parts.append("")
    return parts, total_chars


def build_brief_context(
    events: list[dict[str, Any]],
    open_loops: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    max_chars: int = 40000,
    alerts: list[dict[str, Any]] | None = None,
    calendar: list[dict[str, Any]] | None = None,
    market_insights: list[dict[str, Any]] | None = None,
    competitor_signals: list[dict[str, Any]] | None = None,
    predictive_alerts: list[dict[str, Any]] | None = None,
    compliance_status: dict[str, Any] | None = None,
    strategic_radar: dict[str, Any] | None = None,
) -> str:
    """Assemble all data into a single context string for Claude."""
    all_parts: list[str] = []
    total_chars = 0

    # Calendar (highest priority)
    if calendar:
        parts, total_chars = _render_calendar_section(calendar, max_chars)
        all_parts.extend(parts)

    # Market Intelligence (high priority — actionable for trader)
    if market_insights:
        parts, total_chars = _render_items_section(
            "RYNEK ENERGII (ostatnie 24h)", market_insights,
            lambda m: f"[{m['type']}] {m['title']} (relevance: {m['relevance']}/100)\n  {m['description']}\n  Wpływ na REH/REF: {m['impact']}",
            0.12, total_chars, max_chars)
        all_parts.extend(parts)

    # Competitor signals
    if competitor_signals:
        parts, total_chars = _render_items_section(
            "KONKURENCJA (ostatnie 48h)", competitor_signals,
            lambda c: f"[{c['severity'].upper()}] {c['competitor']}: {c['title']}\n  {c['description'][:200]}",
            0.08, total_chars, max_chars)
        all_parts.extend(parts)

    # Predictive alerts
    if predictive_alerts:
        parts, total_chars = _render_items_section(
            "PREDYKCJE I RYZYKA", predictive_alerts,
            lambda p: f"[{p['type']}] {p['prediction']} (prawdop. {p['probability']:.0%})\n  Zalecenie: {p['action']}",
            0.08, total_chars, max_chars)
        all_parts.extend(parts)

    # Compliance
    if compliance_status:
        overdue = compliance_status.get("overdue_count", 0)
        upcoming = compliance_status.get("upcoming_deadlines", 0)
        open_matters = compliance_status.get("open_matters", 0)
        if overdue or upcoming or open_matters:
            all_parts.append("=== COMPLIANCE ===")
            if overdue:
                all_parts.append(f"OVERDUE terminów: {overdue}")
            if upcoming:
                all_parts.append(f"Nadchodzące terminy (7d): {upcoming}")
            if open_matters:
                all_parts.append(f"Otwarte sprawy: {open_matters}")
            all_parts.append("")

    # Strategic Radar
    if strategic_radar:
        radar_patterns = strategic_radar.get("patterns", [])
        radar_recs = strategic_radar.get("recommendations", [])
        radar_summary = strategic_radar.get("radar_summary", {})
        if radar_patterns or radar_recs:
            all_parts.append("=== STRATEGICZNY RADAR ===")
            if radar_summary:
                all_parts.append(f"Sygnały: rynek {radar_summary.get('market_count', 0)}, "
                                 f"konkurencja {radar_summary.get('competitor_count', 0)}, "
                                 f"cele zagrożone {radar_summary.get('goals_at_risk_count', 0)}, "
                                 f"zobowiązania przeterminowane {radar_summary.get('overdue_commitments_count', 0)}")
            for p in radar_patterns[:5]:
                urgency = p.get("urgency", "?")
                all_parts.append(f"[WZORZEC {urgency.upper()}] {p.get('pattern', '?')}")
                all_parts.append(f"  Źródła: {', '.join(p.get('sources', []))}")
                all_parts.append(f"  Działanie: {p.get('recommended_action', '?')}")
            for rec in radar_recs[:3]:
                all_parts.append(f"[REKOMENDACJA P{rec.get('priority', '?')}] {rec.get('action', '?')}")
                all_parts.append(f"  Uzasadnienie: {rec.get('rationale', '?')}")
                all_parts.append(f"  Termin: {rec.get('deadline_suggestion', '?')}")
            all_parts.append("")

    # Alerts
    if alerts:
        parts, total_chars = _render_items_section(
            "ALERTY PROAKTYWNE", alerts,
            lambda a: f"[{a['severity'].upper()}] {a['title']}: {a['description']}",
            0.15, total_chars, max_chars)
        all_parts.extend(parts)

    # Events
    def _fmt_event(e):
        line = f"[{e['event_type']}] {e['event_time'] or '?'}: {e['summary']}"
        if e.get("entities"):
            line += f" (osoby: {e['entities']})"
        return line

    parts, total_chars = _render_items_section("WYDARZENIA Z OSTATNICH DNI", events, _fmt_event, 0.35, total_chars, max_chars)
    all_parts.extend(parts)

    # Open loops
    def _fmt_loop(ol):
        line = f"[{ol['event_type']}] {ol['event_time'] or '?'}: {ol['summary']}"
        if ol.get("entities"):
            line += f" (dotyczy: {ol['entities']})"
        return line

    parts, total_chars = _render_items_section("OTWARTE PETLA / NIEROZWIAZANE SPRAWY", open_loops, _fmt_loop, 0.6, total_chars, max_chars)
    all_parts.extend(parts)

    # Entities
    def _fmt_entity(ent):
        line = f"{ent['name']} ({ent['entity_type']}): {ent['event_count']} wydarzen, {ent['chunk_count']} wzmianek"
        if ent.get("context"):
            line += f"\n  Kontekst: {ent['context'][:300]}"
        return line

    parts, total_chars = _render_items_section("AKTYWNE OSOBY / ORGANIZACJE", entities, _fmt_entity, 0.8, total_chars, max_chars)
    all_parts.extend(parts)

    # Summaries
    if summaries:
        all_parts.append("=== ISTNIEJACE PODSUMOWANIA ===")
        for s in summaries:
            header = f"[{s['summary_type']}] {s['period_start']} - {s['period_end']}"
            text = s["text"] or ""
            remaining = max_chars - total_chars - len(header) - 10
            if remaining < 100:
                break
            text_trimmed = text[:min(len(text), remaining)]
            all_parts.append(f"{header}\n{text_trimmed}")
            total_chars += len(header) + len(text_trimmed)
        all_parts.append("")

    return "\n".join(all_parts)


# ============================================================
# Brief generation via Claude
# ============================================================

BRIEF_SYSTEM_PROMPT = """
Jestes Gilbertus Albans — prywatnym mentatem Sebastiana Jablonskiego (wlasciciel REH i REF, trader energetyczny).
Twoje zadanie: wygenerowac poranny brief na podstawie dostarczonych danych.

Brief musi zawierac dokladnie 7 sekcji w formacie markdown:

## Rynek i konkurencja
Najwazniejsze sygnaly rynkowe i ruchy konkurencji z ostatnich 24-48h.
- Zmiany cen energii, nowe regulacje, przetargi
- Ruchy konkurentow (Tauron, PGE, Enea, Energa, Orlen, Polenergia)
- Wplyw na REH/REF — co Sebastian powinien wiedziec
Jezeli brak danych, napisz "Brak nowych sygnalow rynkowych."

## Kalendarz dzis
Spotkania z dzisiejszego kalendarza. Dla kazdego:
- Godzina + temat + uczestnicy
- Kontekst relacji z uczestnikami (rola, organizacja, ostatnie interakcje)
- Open loopy dotyczace uczestnikow (jesli sa)
- Sugerowane przygotowanie do spotkania
Jezeli brak spotkan, napisz "Brak spotkan w kalendarzu."

## Focus dzis
Top 3 sprawy wymagajace uwagi dzisiaj. Priorytetyzuj: deadliny > konflikty > decyzje > rutynowe.
Kazdy punkt: konkretna sprawa + dlaczego wymaga uwagi + sugerowane nastepne dzialanie.
Uwzglednij spotkania z kalendarza jesli wymagaja przygotowania.

## Otwarte petle
Nierozwiazane sprawy z ostatniego tygodnia. Dla kazdej:
- Co to za sprawa
- Kiedy sie pojawila
- Kto jest zaangazowany
- Co powinno byc nastepnym krokiem

## Ludzie
Kto byl aktywny w zyciu Sebastiana ostatnio. Dla kazdej osoby:
- W jakim kontekscie sie pojawila
- Jaki jest stan relacji (rola, organizacja, sentiment jesli dostepny)
- Czy cos wymaga reakcji

## Ryzyka i predykcje
Zidentyfikowane zagrozenia i predykcje z systemow wczesnego ostrzegania:
- Eskalacje, luki komunikacyjne, zagrozenia deadlinow
- Scenariusze ryzyka (jezeli wygenerowane)
Jezeli brak, napisz "Brak aktywnych ryzyk."

## Anomalie
Nietypowe wzorce, zmiany, odstepstwa od normy. Np.:
- Ktos, kto zwykle sie nie odzywa, nagle jest aktywny
- Temat, ktory wraca wielokrotnie
- Zmiana tonu w komunikacji
- Nietypowe godziny aktywnosci

## Compliance
Jezeli sa dane compliance — overdue terminy, nadchodzace obowiazki, otwarte sprawy.
- Zaleglosci wymagajace natychmiastowej uwagi
- Najblizsze terminy (7 dni)
- Otwarte sprawy compliance (URE, RODO, AML, ESG, etc.)
Jezeli brak danych, pomin ta sekcje.

Zasady:
- Opieraj sie WYLACZNIE na dostarczonym kontekscie. Nie zmyslaj.
- Pisz po polsku.
- Badz konkretny — nazwiska, daty, szczegoly.
- Przy osobach uwzgledniaj kontekst relacji (rola, firma, sentiment, open loops).
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
            system=[{"type": "text", "text": BRIEF_SYSTEM_PROMPT.strip(), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error("Anthropic API error: %s", e)
        return f"Blad generowania briefu: {e}"
    except Exception as e:
        logger.error("Unexpected error calling Anthropic: %s", e)
        return f"Blad generowania briefu: {e}"

    from app.db.cost_tracker import log_anthropic_cost
    if hasattr(response, "usage"):
        log_anthropic_cost(ANTHROPIC_MODEL, "retrieval.morning_brief", response.usage)

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
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

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
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

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

    # Run proactive alerts check
    try:
        alerts_result = run_alerts_check(date=date)
        logger.info(
            "Alerts check: %d detected, %d new",
            alerts_result["total_detected"],
            alerts_result["new_saved"],
        )
    except Exception:
        logger.exception("Alerts check failed — continuing without alerts")
        alerts_result = None

    # Fetch all data
    events = fetch_recent_events(date_from, date_to)
    open_loops = fetch_open_loops(date_from, date_to)
    entities = fetch_active_entities(date_from, date_to)
    summaries = fetch_recent_summaries(date_from, date_to)
    calendar = fetch_today_calendar(date)
    market = fetch_market_insights()
    competitors = fetch_competitor_signals()
    predictions = fetch_predictive_alerts()
    compliance = fetch_compliance_status()
    radar = fetch_strategic_radar()

    total_data = len(events) + len(open_loops) + len(entities) + len(summaries) + len(calendar) + len(market) + len(competitors)

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
    active_alerts = (
        alerts_result["alerts"] if alerts_result else []
    )
    context = build_brief_context(
        events, open_loops, entities, summaries,
        alerts=active_alerts, calendar=calendar,
        market_insights=market, competitor_signals=competitors,
        predictive_alerts=predictions, compliance_status=compliance,
        strategic_radar=radar,
    )
    date_label = datetime.fromisoformat(date).strftime("%A, %d %B %Y")
    brief_text = generate_brief_text(context, date_label)

    # Save
    summary_id = save_brief(date_from, date_to, brief_text)

    logger.info(
        "Morning brief generated: id=%s, events=%d, open_loops=%d, entities=%d, calendar=%d",
        summary_id, len(events), len(open_loops), len(entities), len(calendar),
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
        "calendar_count": len(calendar),
        "market_count": len(market),
        "competitor_count": len(competitors),
        "predictions_count": len(predictions),
        "alerts_count": alerts_result["total_detected"] if alerts_result else 0,
        "radar_patterns": len(radar.get("patterns", [])) if radar else 0,
        "compliance_overdue": compliance.get("overdue_count", 0) if compliance else 0,
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
