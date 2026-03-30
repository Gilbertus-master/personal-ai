"""
Strategic Radar — cross-domain situational awareness for CEO.

Aggregates market intelligence, competitor signals, strategic goals,
commitments, and anomalies into a single radar view. Uses LLM to
detect cross-domain patterns and generate actionable recommendations.

Two-layer approach:
1. run_strategic_radar() — collect data from all domains
2. detect_cross_domain_patterns() — LLM finds cross-domain correlations
3. generate_strategic_recommendations() — LLM generates concrete actions
4. save_radar_snapshot() — persist to DB

Cron: 0 22 * * * (daily 22:00 UTC / 23:00 CET)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

CROSS_DOMAIN_PROMPT = """Jesteś strategicznym analitykiem dla CEO firmy energetycznej (REH/REF).
Otrzymujesz dane z wielu źródeł: rynek energii, konkurencja, cele strategiczne, zobowiązania, anomalie komunikacyjne.

Twoim zadaniem jest znalezienie KORELACJI I WZORCÓW MIĘDZYDOMENOWYCH — rzeczy których nie widać patrząc na każde źródło osobno.

Przykłady wzorców:
- Konkurent ogłasza nowy produkt OZE + nasz cel OZE jest at_risk → zagrożenie strategiczne
- Zmiana regulacji URE + przeterminowane zobowiązanie compliance → pilny risk
- Anomalia komunikacyjna osoby + cel za który odpowiada jest behind → problem kadrowy
- Wzrost cen gazu + cel przychodowy on_track → szansa na lepszy wynik

Dla każdego wykrytego wzorca podaj:
- pattern: opis wzorca (po polsku, max 150 znaków)
- sources: lista źródeł danych ["market", "competitor", "goal", "commitment", "anomaly"]
- confidence: 0.0-1.0
- recommended_action: konkretne działanie (po polsku)
- urgency: low | medium | high | critical

Respond ONLY with JSON array. Pusta tablica jeśli brak istotnych wzorców: []"""

RECOMMENDATIONS_PROMPT = """Jesteś doradcą strategicznym CEO firmy energetycznej (REH/REF).

Na podstawie danych radarowych i wykrytych wzorców, zaproponuj KONKRETNE DZIAŁANIA.
Każde działanie musi być:
- Możliwe do wykonania w ciągu 1-7 dni
- Przypisane do konkretnej osoby lub obszaru
- Z jasnym uzasadnieniem biznesowym

Dla każdego działania:
- action: co zrobić (po polsku, max 150 znaków)
- rationale: dlaczego (po polsku, max 200 znaków)
- priority: 1 (najwyższy) - 5 (najniższy)
- deadline_suggestion: YYYY-MM-DD lub "natychmiast"

Respond ONLY with JSON array. Max 5 rekomendacji, posortowanych wg priority."""

RADAR_PROMPT = """Jesteś Gilbertus Albans — strategicznym mentatem Sebastiana Jabłońskiego (REH + REF, sektor energetyczny).

Na podstawie dostarczonych danych z wielu domen wygeneruj "Strategic Radar" — ujednolicony obraz strategiczny.

Format (JSON):
{
  "correlations": [
    {
      "title": "krótki tytuł korelacji (po polsku)",
      "domains": ["market", "competitor", "goal", "calendar"],
      "description": "co łączy te sygnały (2-3 zdania)",
      "impact": "wpływ na REH/REF (1 zdanie)",
      "urgency": "immediate|this_week|this_month|watch",
      "suggested_action": "konkretne działanie (1 zdanie)"
    }
  ],
  "blind_spots": ["czego NIE widzimy — potencjalne luki w danych (max 3)"],
  "strategic_summary": "2-3 zdania: kluczowy obraz dnia z perspektywy Sun Tzu"
}

Szukaj POŁĄCZEŃ między domenami — to jest wartość radaru.
Np.: zmiana cen TGE + spotkanie z Tauron + cel revenue = szansa renegocjacji.
Respond ONLY with JSON."""


# ================================================================
# Schema
# ================================================================

def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS strategic_radar (
                    id BIGSERIAL PRIMARY KEY,
                    radar_date DATE NOT NULL,
                    correlations JSONB DEFAULT '[]',
                    blind_spots JSONB DEFAULT '[]',
                    strategic_summary TEXT,
                    context_used JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(radar_date)
                );

                CREATE TABLE IF NOT EXISTS strategic_radar_snapshots (
                    id BIGSERIAL PRIMARY KEY,
                    radar_data JSONB NOT NULL,
                    patterns JSONB NOT NULL DEFAULT '[]',
                    recommendations JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_radar_snapshots_created
                    ON strategic_radar_snapshots(created_at DESC);
            """)
            conn.commit()


# ================================================================
# Data collection helpers
# ================================================================

def _safe_query(query: str, params: tuple = ()) -> list:
    """Execute query safely — return empty list on error."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        log.warning("radar_query_failed", error=str(e))
        return []


def _fetch_market_insights(hours: int = 24, min_relevance: int = 60) -> list[dict[str, Any]]:
    """Fetch recent high-relevance market insights."""
    rows = _safe_query("""
        SELECT id, insight_type, title, description, impact_assessment,
               relevance_score, companies_affected, created_at
        FROM market_insights
        WHERE created_at > NOW() - make_interval(hours => %s)
        AND relevance_score >= %s
        ORDER BY relevance_score DESC
        LIMIT 10
    """, (hours, min_relevance))
    return [
        {"id": r[0], "type": r[1], "title": r[2], "description": r[3],
         "impact": r[4], "relevance": r[5],
         "companies": r[6] if isinstance(r[6], list) else json.loads(r[6]) if r[6] else [],
         "created_at": str(r[7])}
        for r in rows
    ]


def _fetch_competitor_signals(hours: int = 48, min_severity: str = "medium") -> list[dict[str, Any]]:
    """Fetch recent competitor signals of medium/high severity."""
    rows = _safe_query("""
        SELECT cs.id, c.name, cs.signal_type, cs.title, cs.description,
               cs.severity, cs.signal_date
        FROM competitor_signals cs
        JOIN competitors c ON c.id = cs.competitor_id
        WHERE cs.created_at > NOW() - make_interval(hours => %s)
        AND cs.severity IN ('medium', 'high')
        ORDER BY
            CASE cs.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            cs.created_at DESC
        LIMIT 10
    """, (hours,))
    return [
        {"id": r[0], "competitor": r[1], "type": r[2], "title": r[3],
         "description": r[4], "severity": r[5],
         "date": str(r[6]) if r[6] else None}
        for r in rows
    ]


def _fetch_at_risk_goals() -> list[dict[str, Any]]:
    """Fetch strategic goals that are at_risk or behind."""
    rows = _safe_query("""
        SELECT id, title, company, status, deadline,
               current_value, target_value, unit, risk_factors
        FROM strategic_goals
        WHERE status IN ('at_risk', 'behind')
        ORDER BY deadline ASC NULLS LAST
        LIMIT 10
    """)
    return [
        {"id": r[0], "title": r[1], "company": r[2], "status": r[3],
         "deadline": str(r[4]) if r[4] else None,
         "current_value": float(r[5]) if r[5] is not None else None,
         "target_value": float(r[6]) if r[6] is not None else None,
         "unit": r[7], "risk_factors": r[8]}
        for r in rows
    ]


def _fetch_overdue_commitments() -> list[dict[str, Any]]:
    """Fetch overdue commitments."""
    rows = _safe_query("""
        SELECT id, person_name, description, due_date, status
        FROM commitments
        WHERE status = 'open' AND due_date < NOW()
        ORDER BY due_date ASC
        LIMIT 10
    """)
    return [
        {"id": r[0], "person": r[1], "description": r[2],
         "due_date": str(r[3]) if r[3] else None, "status": r[4]}
        for r in rows
    ]


def _fetch_anomalies() -> list[dict[str, Any]]:
    """Fetch communication anomalies."""
    try:
        from app.analysis.correlation import detect_communication_anomalies
        anomalies = detect_communication_anomalies(weeks_baseline=8, threshold_stddev=2.0)
        return anomalies[:10]
    except Exception as e:
        log.warning("radar.anomalies_fetch_failed", error=str(e))
        return []


def _gather_radar_context() -> dict[str, Any]:
    """Gather data from all domains for legacy radar (correlations view)."""
    context: dict[str, Any] = {}

    # Market insights (last 48h)
    context["market"] = [
        {"type": r[0], "title": r[1], "description": r[2], "impact": r[3], "relevance": r[4]}
        for r in _safe_query("""
            SELECT insight_type, title, description, impact_assessment, relevance_score
            FROM market_insights WHERE created_at > NOW() - INTERVAL '48 hours'
            ORDER BY relevance_score DESC LIMIT 10
        """)
    ]

    # Competitor signals (last 7 days)
    context["competitors"] = [
        {"competitor": r[0], "type": r[1], "title": r[2], "description": r[3], "severity": r[4]}
        for r in _safe_query("""
            SELECT c.name, cs.signal_type, cs.title, cs.description, cs.severity
            FROM competitor_signals cs JOIN competitors c ON c.id = cs.competitor_id
            WHERE cs.created_at > NOW() - INTERVAL '7 days'
            ORDER BY CASE cs.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
            LIMIT 10
        """)
    ]

    # Strategic goals (active)
    context["goals"] = [
        {"title": r[0], "current": r[1], "target": r[2], "unit": r[3],
         "status": r[4], "deadline": str(r[5]) if r[5] else None, "company": r[6]}
        for r in _safe_query("""
            SELECT title, current_value, target_value, unit, status, deadline, company
            FROM strategic_goals WHERE status NOT IN ('cancelled', 'achieved')
            ORDER BY CASE status WHEN 'behind' THEN 0 WHEN 'at_risk' THEN 1 ELSE 2 END
            LIMIT 10
        """)
    ]

    # Recent key events (last 48h)
    context["events"] = [
        {"type": r[0], "summary": r[1], "time": str(r[2]) if r[2] else None}
        for r in _safe_query("""
            SELECT event_type, summary, event_time FROM events
            WHERE event_time > NOW() - INTERVAL '48 hours'
            AND event_type IN ('decision', 'commitment', 'conflict', 'trade', 'deadline', 'escalation')
            ORDER BY event_time DESC LIMIT 15
        """)
    ]

    # Active scenarios
    context["scenarios"] = [
        {"title": r[0], "type": r[1], "total_impact": float(r[2]) if r[2] else 0}
        for r in _safe_query("""
            SELECT s.title, s.scenario_type, COALESCE(SUM(o.impact_value_pln), 0)
            FROM scenarios s LEFT JOIN scenario_outcomes o ON o.scenario_id = s.id
            WHERE s.status = 'analyzed'
            GROUP BY s.id, s.title, s.scenario_type
            ORDER BY COALESCE(SUM(o.impact_value_pln), 0) LIMIT 5
        """)
    ]

    return context


# ================================================================
# Core functions
# ================================================================

def run_strategic_radar() -> dict[str, Any]:
    """Collect all radar data from multiple domains.

    Returns dict with: market_insights, competitor_signals, goals_at_risk,
    overdue_commitments, anomalies, summary stats.
    """
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    market = _fetch_market_insights(hours=24, min_relevance=60)
    competitors = _fetch_competitor_signals(hours=48, min_severity="medium")
    goals = _fetch_at_risk_goals()
    commitments = _fetch_overdue_commitments()
    anomalies = _fetch_anomalies()

    radar_data = {
        "market_insights": market,
        "competitor_signals": competitors,
        "goals_at_risk": goals,
        "overdue_commitments": commitments,
        "anomalies": anomalies,
        "summary": {
            "market_count": len(market),
            "competitor_count": len(competitors),
            "goals_at_risk_count": len(goals),
            "overdue_commitments_count": len(commitments),
            "anomalies_count": len(anomalies),
            "total_signals": len(market) + len(competitors) + len(goals) + len(commitments) + len(anomalies),
        },
        "collected_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    radar_data["collection_latency_ms"] = latency_ms
    log.info("strategic_radar.collected", **radar_data["summary"], latency_ms=latency_ms)

    return radar_data


def detect_cross_domain_patterns(radar_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Use LLM (Sonnet) to find cross-domain correlations.

    Returns list of patterns: [{pattern, sources, confidence, recommended_action, urgency}]
    """
    total_signals = radar_data.get("summary", {}).get("total_signals", 0)
    if total_signals == 0:
        log.info("strategic_radar.no_signals_for_patterns")
        return []

    context_parts = []

    if radar_data.get("market_insights"):
        context_parts.append("=== RYNEK ENERGII (24h) ===")
        for m in radar_data["market_insights"]:
            context_parts.append(f"[{m['type']}] {m['title']} (relevance: {m['relevance']})")
            context_parts.append(f"  Wpływ: {m.get('impact', 'brak')}")

    if radar_data.get("competitor_signals"):
        context_parts.append("\n=== KONKURENCJA (48h) ===")
        for c in radar_data["competitor_signals"]:
            context_parts.append(f"[{c['severity'].upper()}] {c['competitor']}: {c['title']}")
            if c.get("description"):
                context_parts.append(f"  {c['description'][:200]}")

    if radar_data.get("goals_at_risk"):
        context_parts.append("\n=== CELE STRATEGICZNE AT RISK ===")
        for g in radar_data["goals_at_risk"]:
            pct = ""
            if g.get("target_value") and g["target_value"] > 0 and g.get("current_value") is not None:
                pct = f" ({round(g['current_value'] / g['target_value'] * 100, 1)}%)"
            context_parts.append(f"[{g['status']}] {g['title']}{pct} — deadline: {g.get('deadline', '?')}")
            if g.get("risk_factors"):
                context_parts.append(f"  Ryzyka: {', '.join(g['risk_factors'][:3])}")

    if radar_data.get("overdue_commitments"):
        context_parts.append("\n=== PRZETERMINOWANE ZOBOWIĄZANIA ===")
        for c in radar_data["overdue_commitments"]:
            context_parts.append(f"{c['person']}: {c['description'][:100]} (termin: {c.get('due_date', '?')})")

    if radar_data.get("anomalies"):
        context_parts.append("\n=== ANOMALIE KOMUNIKACYJNE ===")
        for a in radar_data["anomalies"]:
            context_parts.append(f"{a.get('person', '?')}: {a.get('interpretation', a.get('direction', '?'))}")

    context = "\n".join(context_parts)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        temperature=0.2,
        system=[{"type": "text", "text": CROSS_DOMAIN_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Dane radarowe:\n\n{context}"}],
    )
    log_anthropic_cost(ANTHROPIC_MODEL, "strategic_radar.patterns", response.usage)

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    try:
        patterns = json.loads(raw_text)
        if not isinstance(patterns, list):
            patterns = []
    except json.JSONDecodeError:
        log.warning("strategic_radar.patterns_parse_failed", raw=raw_text[:200])
        patterns = []

    log.info("strategic_radar.patterns_detected", count=len(patterns))
    return patterns


def generate_strategic_recommendations(
    radar_data: dict[str, Any],
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate concrete action recommendations based on radar data and patterns.

    Returns list: [{action, rationale, priority, deadline_suggestion}]
    """
    total_signals = radar_data.get("summary", {}).get("total_signals", 0)
    if total_signals == 0 and not patterns:
        return []

    context_parts = ["=== PODSUMOWANIE RADARU ==="]
    summary = radar_data.get("summary", {})
    context_parts.append(f"Sygnały rynkowe: {summary.get('market_count', 0)}")
    context_parts.append(f"Sygnały konkurencji: {summary.get('competitor_count', 0)}")
    context_parts.append(f"Cele zagrożone: {summary.get('goals_at_risk_count', 0)}")
    context_parts.append(f"Przeterminowane zobowiązania: {summary.get('overdue_commitments_count', 0)}")
    context_parts.append(f"Anomalie: {summary.get('anomalies_count', 0)}")

    if patterns:
        context_parts.append("\n=== WYKRYTE WZORCE ===")
        for p in patterns:
            context_parts.append(f"[{p.get('urgency', '?')}] {p.get('pattern', '?')}")
            context_parts.append(f"  Źródła: {', '.join(p.get('sources', []))}")
            context_parts.append(f"  Confidence: {p.get('confidence', '?')}")
            context_parts.append(f"  Sugestia: {p.get('recommended_action', '?')}")

    if radar_data.get("goals_at_risk"):
        context_parts.append("\n=== CELE AT RISK ===")
        for g in radar_data["goals_at_risk"][:5]:
            context_parts.append(f"- {g['title']} ({g['status']}, deadline: {g.get('deadline', '?')})")

    if radar_data.get("overdue_commitments"):
        context_parts.append("\n=== TOP PRZETERMINOWANE ===")
        for c in radar_data["overdue_commitments"][:5]:
            context_parts.append(f"- {c['person']}: {c['description'][:80]}")

    context = "\n".join(context_parts)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500,
        temperature=0.2,
        system=[{"type": "text", "text": RECOMMENDATIONS_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Dane do rekomendacji:\n\n{context}"}],
    )
    log_anthropic_cost(ANTHROPIC_MODEL, "strategic_radar.recommendations", response.usage)

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    try:
        recommendations = json.loads(raw_text)
        if not isinstance(recommendations, list):
            recommendations = []
    except json.JSONDecodeError:
        log.warning("strategic_radar.recommendations_parse_failed", raw=raw_text[:200])
        recommendations = []

    log.info("strategic_radar.recommendations_generated", count=len(recommendations))
    return recommendations


# ================================================================
# Persistence
# ================================================================

def save_radar_snapshot(
    data: dict[str, Any],
    patterns: list[dict[str, Any]],
    recs: list[dict[str, Any]],
) -> int:
    """Save a radar snapshot to the database. Returns snapshot ID."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO strategic_radar_snapshots (radar_data, patterns, recommendations)
                   VALUES (%s::jsonb, %s::jsonb, %s::jsonb) RETURNING id""",
                (
                    json.dumps(data, ensure_ascii=False, default=str),
                    json.dumps(patterns, ensure_ascii=False, default=str),
                    json.dumps(recs, ensure_ascii=False, default=str),
                ),
            )
            snapshot_id = cur.fetchall()[0][0]
        conn.commit()

    log.info("strategic_radar.snapshot_saved", snapshot_id=snapshot_id)
    return snapshot_id


def get_radar_history(days: int = 7) -> list[dict[str, Any]]:
    """Get radar snapshot history for the last N days."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, radar_data, patterns, recommendations, created_at
                FROM strategic_radar_snapshots
                WHERE created_at > NOW() - make_interval(days => %s)
                ORDER BY created_at DESC
                LIMIT 30
            """, (days,))
            return [
                {
                    "id": r[0],
                    "radar_data": r[1],
                    "patterns": r[2],
                    "recommendations": r[3],
                    "created_at": str(r[4]),
                }
                for r in cur.fetchall()
            ]


# ================================================================
# Legacy radar generation (daily correlations view)
# ================================================================

def generate_strategic_radar(force: bool = False) -> dict[str, Any]:
    """Generate today's Strategic Radar (legacy correlations view)."""
    _ensure_tables()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    if not force:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM strategic_radar WHERE radar_date = %s", (today,))
                if cur.fetchall():
                    return {"status": "exists", "date": today}

    started = datetime.now(tz=timezone.utc)
    context = _gather_radar_context()

    total_signals = sum(len(v) for v in context.values() if isinstance(v, list))
    if total_signals < 3:
        return {"status": "insufficient_data", "signals": total_signals}

    context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    user_msg = f"Data: {today}\n\nDane ze wszystkich domen:\n{context_text}"

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=2000,
        temperature=0.2,
        system=[{"type": "text", "text": RADAR_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "strategic_radar", response.usage)

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        radar = json.loads(raw)
    except json.JSONDecodeError:
        import re
        try:
            fixed = re.sub(r',\s*}', '}', re.sub(r',\s*]', ']', raw))
            radar = json.loads(fixed)
        except json.JSONDecodeError:
            log.warning("radar.json_parse_failed", raw=raw[:200])
            radar = {"correlations": [], "blind_spots": [], "strategic_summary": raw[:500]}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO strategic_radar (radar_date, correlations, blind_spots,
                    strategic_summary, context_used)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (radar_date) DO UPDATE SET
                    correlations = EXCLUDED.correlations,
                    blind_spots = EXCLUDED.blind_spots,
                    strategic_summary = EXCLUDED.strategic_summary,
                    context_used = EXCLUDED.context_used,
                    created_at = NOW()
            """, (
                today,
                json.dumps(radar.get("correlations", []), ensure_ascii=False),
                json.dumps(radar.get("blind_spots", []), ensure_ascii=False),
                radar.get("strategic_summary", ""),
                json.dumps({"signals_per_domain": {k: len(v) for k, v in context.items() if isinstance(v, list)}}),
            ))
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("strategic_radar_generated", correlations=len(radar.get("correlations", [])), latency_ms=latency_ms)

    return {
        "status": "generated",
        "date": today,
        "correlations": radar.get("correlations", []),
        "blind_spots": radar.get("blind_spots", []),
        "strategic_summary": radar.get("strategic_summary", ""),
        "latency_ms": latency_ms,
    }


def get_todays_radar() -> dict[str, Any] | None:
    """Retrieve today's radar."""
    _ensure_tables()
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT radar_date, correlations, blind_spots, strategic_summary
                FROM strategic_radar WHERE radar_date = %s
            """, (today,))
            rows = cur.fetchall()
            if rows:
                r = rows[0]
                return {
                    "date": str(r[0]),
                    "correlations": r[1] if isinstance(r[1], list) else json.loads(r[1]),
                    "blind_spots": r[2] if isinstance(r[2], list) else json.loads(r[2]),
                    "summary": r[3],
                }
    return None


# ================================================================
# Full pipeline
# ================================================================

def run_full_radar() -> dict[str, Any]:
    """Full pipeline: collect -> detect patterns -> recommend -> save.

    Called by cron and API.
    """
    started = datetime.now(tz=timezone.utc)

    # 1. Collect radar data
    radar_data = run_strategic_radar()

    # 2. Detect cross-domain patterns
    patterns = detect_cross_domain_patterns(radar_data)

    # 3. Generate recommendations
    recommendations = generate_strategic_recommendations(radar_data, patterns)

    # 4. Save snapshot
    snapshot_id = save_radar_snapshot(radar_data, patterns, recommendations)

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)

    result = {
        "snapshot_id": snapshot_id,
        "radar_data": radar_data,
        "patterns": patterns,
        "recommendations": recommendations,
        "latency_ms": latency_ms,
    }

    log.info("strategic_radar.full_pipeline_done",
             snapshot_id=snapshot_id,
             patterns_count=len(patterns),
             recommendations_count=len(recommendations),
             latency_ms=latency_ms)

    return result


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys

    if "--history" in sys.argv:
        days = 7
        idx = sys.argv.index("--history")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
            days = int(sys.argv[idx + 1])
        result = get_radar_history(days)
    elif "--legacy" in sys.argv:
        result = generate_strategic_radar(force="--force" in sys.argv)
    else:
        result = run_full_radar()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
