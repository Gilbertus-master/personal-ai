"""
Competitor Intelligence — track competitors via KRS, media, internal archives.

Monitors: Tauron, PGE, Enea, Energa, Orlen + custom competitors.
Generates SWOT analysis per competitor, collects signals, builds landscape.

Cron: 0 19 * * 5 (Friday 19:00 UTC / 20:00 CET) — weekly scan
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone
from typing import Any

import feedparser
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

FETCH_TIMEOUT = 15

SWOT_PROMPT = """Jesteś strategicznym analitykiem konkurencji dla Respect Energy Holding (REH) — firmy tradingowej z sektora energetycznego i OZE w Polsce.

Na podstawie zebranych sygnałów o konkurencie, przygotuj analizę SWOT:
- strengths: silne strony konkurenta (max 5, po polsku)
- weaknesses: słabe strony (max 5)
- threats: zagrożenia dla REH wynikające z działań konkurenta (max 5)
- opportunities: szanse dla REH (max 5)
- summary: 2-3 zdania podsumowania (po polsku)

Respond ONLY with JSON:
{"strengths": ["..."], "weaknesses": ["..."], "threats": ["..."], "opportunities": ["..."], "summary": "..."}"""

SIGNAL_ANALYSIS_PROMPT = """Jesteś analitykiem competitive intelligence. Przeanalizuj poniższe wiadomości
medialne i wyodrębnij sygnały konkurencyjne istotne dla Respect Energy Holding (REH).

Dla każdego istotnego sygnału podaj:
- competitor_name: nazwa firmy
- signal_type: krs_change | hiring | media | tender | financial
- title: krótki tytuł (po polsku, max 80 znaków)
- description: 1-2 zdania
- severity: low | medium | high

Ignoruj wiadomości nieistotne konkurencyjnie.
Respond ONLY with JSON array:
[{"competitor_name": "...", "signal_type": "...", "title": "...", "description": "...", "severity": "..."}]

Pusta tablica jeśli brak istotnych sygnałów: []"""

# Default competitors in Polish energy market
DEFAULT_COMPETITORS = [
    {"name": "Tauron Polska Energia", "krs_number": "0000271562", "industry": "energia", "watch_level": "active"},
    {"name": "PGE Polska Grupa Energetyczna", "krs_number": "0000059307", "industry": "energia", "watch_level": "active"},
    {"name": "Enea", "krs_number": "0000012483", "industry": "energia", "watch_level": "active"},
    {"name": "Energa", "krs_number": "0000271591", "industry": "energia", "watch_level": "active"},
    {"name": "PKN Orlen", "krs_number": "0000028860", "industry": "paliwa/energia", "watch_level": "passive"},
    {"name": "Polenergia", "krs_number": "0000026545", "industry": "OZE", "watch_level": "active"},
    {"name": "Columbus Energy", "krs_number": "0000576685", "industry": "OZE", "watch_level": "passive"},
]


# ================================================================
# Schema
# ================================================================

def _ensure_tables() -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS competitors (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    krs_number TEXT,
                    industry TEXT,
                    notes TEXT,
                    watch_level TEXT NOT NULL DEFAULT 'passive'
                        CHECK (watch_level IN ('active', 'passive', 'archived')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS competitor_signals (
                    id BIGSERIAL PRIMARY KEY,
                    competitor_id BIGINT REFERENCES competitors(id) ON DELETE CASCADE,
                    signal_type TEXT NOT NULL
                        CHECK (signal_type IN ('krs_change', 'hiring', 'media', 'tender', 'financial')),
                    title TEXT NOT NULL,
                    description TEXT,
                    source_url TEXT,
                    signal_date TIMESTAMPTZ DEFAULT NOW(),
                    severity TEXT NOT NULL DEFAULT 'low'
                        CHECK (severity IN ('low', 'medium', 'high')),
                    processed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS competitor_analysis (
                    id BIGSERIAL PRIMARY KEY,
                    competitor_id BIGINT NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
                    analysis_period TEXT,
                    strengths JSONB DEFAULT '[]',
                    weaknesses JSONB DEFAULT '[]',
                    threats JSONB DEFAULT '[]',
                    opportunities JSONB DEFAULT '[]',
                    summary TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_competitors_watch
                    ON competitors(watch_level);
                CREATE INDEX IF NOT EXISTS idx_competitor_signals_competitor
                    ON competitor_signals(competitor_id);
                CREATE INDEX IF NOT EXISTS idx_competitor_signals_type
                    ON competitor_signals(signal_type);
                CREATE INDEX IF NOT EXISTS idx_competitor_analysis_competitor
                    ON competitor_analysis(competitor_id);
            """)
            conn.commit()
    log.info("competitor_intelligence.tables_ensured")


def _seed_default_competitors() -> int:
    """Seed default competitors if table is empty."""
    added = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM competitors")
            if cur.fetchall()[0][0] > 0:
                return 0
            for comp in DEFAULT_COMPETITORS:
                cur.execute(
                    """INSERT INTO competitors (name, krs_number, industry, watch_level)
                       VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING""",
                    (comp["name"], comp["krs_number"], comp["industry"], comp["watch_level"]),
                )
                added += cur.rowcount
            conn.commit()
    log.info("competitors_seeded", count=added)
    return added


# ================================================================
# Signal collection
# ================================================================

def _scan_media_rss(competitor_name: str) -> list[dict[str, Any]]:
    """Search Google News RSS for competitor mentions."""
    query = competitor_name.replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={query}+energia&hl=pl&gl=PL&ceid=PL:pl"
    try:
        feed = feedparser.parse(url)
        signals = []
        for entry in feed.entries[:10]:
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            signals.append({
                "signal_type": "media",
                "title": getattr(entry, "title", "")[:200],
                "description": getattr(entry, "summary", "")[:500],
                "source_url": getattr(entry, "link", ""),
                "signal_date": pub_date,
                "severity": "low",
            })
        return signals
    except Exception as e:
        log.warning("media_scan_failed", competitor=competitor_name, error=str(e))
        return []


def _scan_internal(competitor_name: str) -> list[dict[str, Any]]:
    """Search internal archive (chunks) for competitor mentions."""
    signals = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Search recent events mentioning competitor
            cur.execute("""
                SELECT e.event_type, e.summary, e.event_time
                FROM events e
                WHERE e.summary ILIKE %s
                AND e.event_time > NOW() - INTERVAL '30 days'
                ORDER BY e.event_time DESC LIMIT 10
            """, (f"%{competitor_name.split()[0]}%",))
            for r in cur.fetchall():
                signals.append({
                    "signal_type": "media",
                    "title": f"[Internal] {r[0]}: {r[1][:80]}",
                    "description": r[1][:500],
                    "source_url": "internal_archive",
                    "signal_date": r[2],
                    "severity": "low",
                })

            # Search entities
            cur.execute("""
                SELECT e.name, e.entity_type, COUNT(ce.id) as mentions
                FROM entities e
                JOIN chunk_entities ce ON ce.entity_id = e.id
                JOIN chunks c ON c.id = ce.chunk_id
                WHERE e.name ILIKE %s
                AND c.timestamp_start > NOW() - INTERVAL '30 days'
                GROUP BY e.id LIMIT 5
            """, (f"%{competitor_name.split()[0]}%",))
            for r in cur.fetchall():
                if r[2] >= 3:
                    signals.append({
                        "signal_type": "media",
                        "title": f"[Internal] {r[0]} — {r[2]} wzmianek (30 dni)",
                        "description": f"Encja '{r[0]}' (typ: {r[1]}) pojawiła się {r[2]} razy w ostatnich 30 dniach.",
                        "source_url": "internal_archive",
                        "signal_date": datetime.now(tz=timezone.utc),
                        "severity": "medium" if r[2] >= 5 else "low",
                    })

    return signals


def collect_competitor_signals() -> dict[str, Any]:
    """Collect signals for all active competitors."""
    _ensure_tables()
    _seed_default_competitors()

    total_signals = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, krs_number FROM competitors WHERE watch_level = 'active'")
            competitors = cur.fetchall()

    for comp_id, name, krs in competitors:
        signals = []

        # Media scan
        media_signals = _scan_media_rss(name)
        signals.extend(media_signals)

        # Internal archive scan
        internal_signals = _scan_internal(name)
        signals.extend(internal_signals)

        # Store new signals
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for s in signals:
                    # Dedup: same title in last 7 days
                    cur.execute("""
                        SELECT EXISTS(SELECT 1 FROM competitor_signals
                        WHERE competitor_id = %s AND title = %s
                        AND created_at > NOW() - INTERVAL '7 days')
                    """, (comp_id, s["title"][:200]))
                    if cur.fetchall()[0][0]:
                        continue

                    cur.execute(
                        """INSERT INTO competitor_signals
                           (competitor_id, signal_type, title, description,
                            source_url, signal_date, severity)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (comp_id, s["signal_type"], s["title"][:200],
                         s.get("description", ""), s.get("source_url", ""),
                         s.get("signal_date"), s.get("severity", "low")),
                    )
                    total_signals += 1
                conn.commit()

        log.info("competitor_signals_collected", competitor=name, signals=len(signals))

    return {"competitors_scanned": len(competitors), "new_signals": total_signals}


# ================================================================
# LLM Analysis
# ================================================================

def _analyze_signals_batch(signals_text: str) -> list[dict[str, Any]]:
    """Use LLM to analyze a batch of raw media signals."""
    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=2000,
        temperature=0.1,
        system=[{"type": "text", "text": SIGNAL_ANALYSIS_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": signals_text}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "competitor_intelligence", response.usage)
    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        log.warning("signal_analysis.json_parse_failed")
        return []


def analyze_competitor(competitor_id: int) -> dict[str, Any]:
    """Generate SWOT analysis for a competitor based on collected signals."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM competitors WHERE id = %s", (competitor_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"Competitor {competitor_id} not found"}

            comp_name = row[1]

            # Gather recent signals
            cur.execute("""
                SELECT signal_type, title, description, severity, signal_date
                FROM competitor_signals
                WHERE competitor_id = %s
                ORDER BY signal_date DESC NULLS LAST LIMIT 30
            """, (competitor_id,))
            signals = cur.fetchall()

    if not signals:
        return {"competitor": comp_name, "message": "No signals collected yet. Run scan first."}

    signals_text = "\n".join(
        f"[{s[0]}] {s[1]} ({s[3]}) — {s[2][:200]}"
        for s in signals
    )

    user_msg = f"""KONKURENT: {comp_name}

ZEBRANE SYGNAŁY ({len(signals)}):
{signals_text}

Przygotuj analizę SWOT tego konkurenta z perspektywy REH."""

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=2000,
        temperature=0.2,
        system=[{"type": "text", "text": SWOT_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "competitor_intelligence", response.usage)

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
    try:
        swot = json.loads(raw_text)
    except json.JSONDecodeError:
        log.warning("swot.json_parse_failed")
        swot = {"strengths": [], "weaknesses": [], "threats": [], "opportunities": [], "summary": "Parse error"}

    # Store analysis
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO competitor_analysis
                   (competitor_id, analysis_period, strengths, weaknesses,
                    threats, opportunities, summary)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    competitor_id,
                    f"30d ending {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}",
                    json.dumps(swot.get("strengths", []), ensure_ascii=False),
                    json.dumps(swot.get("weaknesses", []), ensure_ascii=False),
                    json.dumps(swot.get("threats", []), ensure_ascii=False),
                    json.dumps(swot.get("opportunities", []), ensure_ascii=False),
                    swot.get("summary", ""),
                ),
            )
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("competitor_analyzed", competitor=comp_name, latency_ms=latency_ms)

    return {
        "competitor": comp_name,
        "swot": swot,
        "signals_count": len(signals),
        "latency_ms": latency_ms,
    }


# ================================================================
# Queries
# ================================================================

def get_competitive_landscape() -> dict[str, Any]:
    """Dashboard: all competitors with latest analysis and signal counts."""
    _ensure_tables()
    _seed_default_competitors()

    competitors = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.krs_number, c.industry, c.watch_level,
                       (SELECT COUNT(*) FROM competitor_signals cs
                        WHERE cs.competitor_id = c.id
                        AND cs.created_at > NOW() - INTERVAL '30 days') as recent_signals,
                       (SELECT COUNT(*) FROM competitor_signals cs
                        WHERE cs.competitor_id = c.id AND cs.severity = 'high'
                        AND cs.created_at > NOW() - INTERVAL '30 days') as high_severity,
                       (SELECT summary FROM competitor_analysis ca
                        WHERE ca.competitor_id = c.id ORDER BY ca.created_at DESC LIMIT 1) as latest_summary,
                       (SELECT created_at FROM competitor_analysis ca
                        WHERE ca.competitor_id = c.id ORDER BY ca.created_at DESC LIMIT 1) as analysis_date
                FROM competitors c
                WHERE c.watch_level != 'archived'
                ORDER BY recent_signals DESC
            """)
            for r in cur.fetchall():
                comp = {
                    "id": r[0], "name": r[1], "krs": r[2], "industry": r[3],
                    "watch_level": r[4], "recent_signals_30d": r[5], "high_severity": r[6],
                }
                if r[7]:
                    comp["latest_analysis"] = r[7]
                    comp["analysis_date"] = str(r[8]) if r[8] else None

                competitors.append(comp)

    return {
        "competitors": competitors,
        "total": len(competitors),
        "active_count": sum(1 for c in competitors if c["watch_level"] == "active"),
    }


def add_competitor(
    name: str,
    krs_number: str | None = None,
    industry: str = "energia",
    watch_level: str = "active",
    notes: str | None = None,
) -> dict[str, Any]:
    """Add or update a competitor."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO competitors (name, krs_number, industry, watch_level, notes)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (name) DO UPDATE
                   SET krs_number = COALESCE(EXCLUDED.krs_number, competitors.krs_number),
                       watch_level = EXCLUDED.watch_level,
                       notes = COALESCE(EXCLUDED.notes, competitors.notes)
                   RETURNING id""",
                (name, krs_number, industry, watch_level, notes),
            )
            cid = cur.fetchall()[0][0]
            conn.commit()
    return {"id": cid, "name": name, "watch_level": watch_level}


def get_competitor_signals(
    competitor_id: int | None = None,
    signal_type: str | None = None,
    days: int = 30,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Get recent competitor signals."""
    _ensure_tables()

    clauses = [f"cs.created_at > NOW() - INTERVAL '{days} days'"]
    params: list[Any] = []
    if competitor_id:
        clauses.append("cs.competitor_id = %s")
        params.append(competitor_id)
    if signal_type:
        clauses.append("cs.signal_type = %s")
        params.append(signal_type)
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT cs.id, c.name, cs.signal_type, cs.title, cs.description,
                       cs.severity, cs.signal_date, cs.source_url
                FROM competitor_signals cs
                JOIN competitors c ON c.id = cs.competitor_id
                WHERE {' AND '.join(clauses)}
                ORDER BY cs.signal_date DESC NULLS LAST
                LIMIT %s
            """, params)
            return [
                {
                    "id": r[0], "competitor": r[1], "type": r[2], "title": r[3],
                    "description": r[4], "severity": r[5],
                    "date": str(r[6]) if r[6] else None, "source_url": r[7],
                }
                for r in cur.fetchall()
            ]


# ================================================================
# Main pipeline
# ================================================================

def run_competitor_scan() -> dict[str, Any]:
    """Main pipeline: collect signals → analyze active competitors → landscape."""
    _ensure_tables()
    _seed_default_competitors()
    started = datetime.now(tz=timezone.utc)

    # Collect signals
    collect_result = collect_competitor_signals()

    # Analyze active competitors with enough signals
    analyzed = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name,
                       (SELECT COUNT(*) FROM competitor_signals cs
                        WHERE cs.competitor_id = c.id) as signal_count
                FROM competitors c
                WHERE c.watch_level = 'active'
            """)
            for comp_id, name, sig_count in cur.fetchall():
                if sig_count >= 3:
                    result = analyze_competitor(comp_id)
                    analyzed.append({"name": name, "swot_summary": result.get("swot", {}).get("summary", "")})

    landscape = get_competitive_landscape()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("competitor_scan_done", latency_ms=latency_ms)

    return {
        "success": True,
        "signals_collected": collect_result,
        "competitors_analyzed": len(analyzed),
        "analysis_summaries": analyzed,
        "landscape": landscape,
        "latency_ms": latency_ms,
    }
