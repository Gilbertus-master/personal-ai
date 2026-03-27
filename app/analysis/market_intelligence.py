"""
Market Intelligence — energy market monitoring for REH/REF.

Two-layer approach:
1. Internal: semantic search in existing chunks for market mentions
2. External: RSS feeds from TGE, URE, PSE, BiznesAlert, CIRE

Cron: 0 6 * * 1-5 (morning 6:00 UTC / 7:00 CET) + 0 15 * * 1-5 (afternoon)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
import hashlib
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

FETCH_TIMEOUT = 15  # seconds

MARKET_ANALYSIS_PROMPT = """Jesteś analitykiem rynku energetycznego pracującym dla Respect Energy Holding (REH) i Respect Energy Fuels (REF).
REH zajmuje się tradingiem energii i OZE. REF to obrót paliwami.

Przeanalizuj poniższe wiadomości rynkowe i dla każdej wyodrębnij insight:
- insight_type: price_change | regulation | tender | trend | risk
- title: krótki tytuł (po polsku, max 80 znaków)
- description: 1-2 zdania opisu i kontekstu
- impact_assessment: jak to wpływa na REH/REF (1 zdanie)
- relevance_score: 0-100 (100 = krytyczne dla REH/REF)
- companies_affected: lista firm których dotyczy (["REH", "REF"] lub inne)

Ignoruj wiadomości nieistotne dla sektora energetycznego.
Zwróć TYLKO JSON array:
[{"insight_type": "...", "title": "...", "description": "...", "impact_assessment": "...", "relevance_score": 75, "companies_affected": ["REH"], "source_item_ids": [1,2]}]

Jeśli żadna wiadomość nie jest istotna, zwróć pustą tablicę: []"""

# Default RSS sources for Polish energy market
DEFAULT_SOURCES = [
    {"name": "BiznesAlert.pl", "source_type": "rss",
     "url": "https://biznesalert.pl/feed/", "fetch_config": {}},
    {"name": "CIRE.pl - Energetyka", "source_type": "rss",
     "url": "https://www.cire.pl/rss/energetyka.xml", "fetch_config": {}},
    {"name": "CIRE.pl - OZE", "source_type": "rss",
     "url": "https://www.cire.pl/rss/oze.xml", "fetch_config": {}},
    {"name": "URE - Komunikaty", "source_type": "rss",
     "url": "https://www.ure.gov.pl/pl/rss/aktualnosci.xml", "fetch_config": {}},
    {"name": "Wysokie Napięcie", "source_type": "rss",
     "url": "https://wysokienapiecie.pl/feed/", "fetch_config": {}},
    {"name": "Gramwzielone.pl", "source_type": "rss",
     "url": "https://www.gramwzielone.pl/feed", "fetch_config": {}},
]


# ================================================================
# Schema
# ================================================================

def _ensure_tables() -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_sources (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'rss'
                        CHECK (source_type IN ('rss', 'api', 'web')),
                    url TEXT NOT NULL,
                    fetch_config JSONB DEFAULT '{}',
                    last_fetched TIMESTAMPTZ,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(url)
                );

                CREATE TABLE IF NOT EXISTS market_items (
                    id BIGSERIAL PRIMARY KEY,
                    source_id BIGINT REFERENCES market_sources(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT,
                    url_hash TEXT,
                    published_at TIMESTAMPTZ,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    processed BOOLEAN NOT NULL DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS market_insights (
                    id BIGSERIAL PRIMARY KEY,
                    item_ids JSONB DEFAULT '[]',
                    insight_type TEXT NOT NULL
                        CHECK (insight_type IN ('price_change', 'regulation', 'tender', 'trend', 'risk')),
                    title TEXT NOT NULL,
                    description TEXT,
                    impact_assessment TEXT,
                    relevance_score INTEGER DEFAULT 50 CHECK (relevance_score >= 0 AND relevance_score <= 100),
                    companies_affected JSONB DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS market_alerts (
                    id BIGSERIAL PRIMARY KEY,
                    insight_id BIGINT REFERENCES market_insights(id) ON DELETE CASCADE,
                    alert_level TEXT NOT NULL DEFAULT 'info'
                        CHECK (alert_level IN ('info', 'warning', 'critical')),
                    message TEXT NOT NULL,
                    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_market_items_processed
                    ON market_items(processed) WHERE NOT processed;
                CREATE INDEX IF NOT EXISTS idx_market_items_url_hash
                    ON market_items(url_hash);
                CREATE INDEX IF NOT EXISTS idx_market_insights_type
                    ON market_insights(insight_type);
                CREATE INDEX IF NOT EXISTS idx_market_insights_relevance
                    ON market_insights(relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_market_alerts_ack
                    ON market_alerts(acknowledged) WHERE NOT acknowledged;
            """)
            conn.commit()
    log.info("market_intelligence.tables_ensured")


def _seed_default_sources() -> int:
    """Seed default RSS sources if table is empty."""
    added = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM market_sources")
            if cur.fetchone()[0] > 0:
                return 0
            for src in DEFAULT_SOURCES:
                cur.execute(
                    """INSERT INTO market_sources (name, source_type, url, fetch_config)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (url) DO NOTHING""",
                    (src["name"], src["source_type"], src["url"],
                     json.dumps(src["fetch_config"])),
                )
                added += cur.rowcount
            conn.commit()
    log.info("market_sources_seeded", count=added)
    return added


# ================================================================
# Data fetching
# ================================================================

def _fetch_rss(url: str) -> list[dict[str, Any]]:
    """Parse RSS feed and return list of items."""
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:20]:  # max 20 per feed
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "description"):
                content = entry.description

            items.append({
                "title": getattr(entry, "title", ""),
                "content": content[:2000],  # truncate
                "url": getattr(entry, "link", ""),
                "published_at": pub_date,
            })
        return items
    except Exception as e:
        log.warning("rss_fetch_failed", url=url, error=str(e))
        return []


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def fetch_market_data() -> dict[str, Any]:
    """Fetch new items from all active market sources."""
    _ensure_tables()
    _seed_default_sources()

    total_new = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, source_type, url, fetch_config FROM market_sources WHERE active = TRUE")
            sources = cur.fetchall()

    for src_id, name, stype, url, _config in sources:
        if stype == "rss":
            items = _fetch_rss(url)
        else:
            log.info("market_source_skipped", name=name, type=stype)
            continue

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for item in items:
                    uh = _url_hash(item.get("url", "") or item["title"])
                    # Dedup by url_hash
                    cur.execute("SELECT EXISTS(SELECT 1 FROM market_items WHERE url_hash = %s)", (uh,))
                    if cur.fetchone()[0]:
                        continue

                    cur.execute(
                        """INSERT INTO market_items (source_id, title, content, url, url_hash, published_at)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (src_id, item["title"], item["content"], item.get("url"),
                         uh, item.get("published_at")),
                    )
                    total_new += 1

                # Update last_fetched
                cur.execute("UPDATE market_sources SET last_fetched = NOW() WHERE id = %s", (src_id,))
                conn.commit()

        log.info("market_source_fetched", name=name, new_items=total_new)

    return {"sources_checked": len(sources), "new_items": total_new}


# ================================================================
# Analysis
# ================================================================

def analyze_market_items(batch_size: int = 20) -> dict[str, Any]:
    """Analyze unprocessed market items using LLM."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content, url, published_at
                FROM market_items WHERE NOT processed
                ORDER BY published_at DESC NULLS LAST
                LIMIT %s
            """, (batch_size,))
            items = cur.fetchall()

    if not items:
        return {"insights_created": 0, "alerts_created": 0, "message": "No new items to analyze"}

    # Build context for LLM
    items_text = []
    item_ids = []
    for i, (mid, title, content, url, pub) in enumerate(items, 1):
        items_text.append(f"[{mid}] {title}\n{content[:500]}\nURL: {url}\nData: {pub}")
        item_ids.append(mid)

    user_msg = f"""Przeanalizuj {len(items)} wiadomości rynkowych:

{"---".join(items_text)}"""

    response = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=3000,
        temperature=0.1,
        system=[{"type": "text", "text": MARKET_ANALYSIS_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "market_intelligence", response.usage)

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    try:
        insights_data = json.loads(raw_text)
    except json.JSONDecodeError:
        log.warning("market_analysis.json_parse_failed", raw=raw_text[:200])
        insights_data = []

    insights_created = 0
    alerts_created = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for ins in insights_data:
                cur.execute(
                    """INSERT INTO market_insights
                       (item_ids, insight_type, title, description,
                        impact_assessment, relevance_score, companies_affected)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        json.dumps(ins.get("source_item_ids", [])),
                        ins.get("insight_type", "trend"),
                        ins.get("title", "")[:200],
                        ins.get("description", ""),
                        ins.get("impact_assessment", ""),
                        ins.get("relevance_score", 50),
                        json.dumps(ins.get("companies_affected", [])),
                    ),
                )
                insight_id = cur.fetchone()[0]
                insights_created += 1

                # Create alert for high-relevance insights
                relevance = ins.get("relevance_score", 50)
                if relevance >= 80:
                    alert_level = "critical" if relevance >= 90 else "warning"
                    cur.execute(
                        """INSERT INTO market_alerts (insight_id, alert_level, message)
                           VALUES (%s, %s, %s)""",
                        (insight_id, alert_level,
                         f"[{ins.get('insight_type', 'trend')}] {ins.get('title', '')}: {ins.get('impact_assessment', '')}"),
                    )
                    alerts_created += 1

            # Mark items as processed
            cur.execute(
                "UPDATE market_items SET processed = TRUE WHERE id = ANY(%s)",
                (item_ids,),
            )
            conn.commit()

    log.info("market_analysis_done", insights=insights_created, alerts=alerts_created)
    return {"insights_created": insights_created, "alerts_created": alerts_created}


# ================================================================
# Queries
# ================================================================

def get_market_dashboard(days: int = 7) -> dict[str, Any]:
    """Market intelligence dashboard: recent insights + active alerts."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Recent insights
            cur.execute("""
                SELECT id, insight_type, title, description, impact_assessment,
                       relevance_score, companies_affected, created_at
                FROM market_insights
                WHERE created_at > NOW() - INTERVAL '%s days'
                ORDER BY relevance_score DESC, created_at DESC
                LIMIT 20
            """, (days,))
            insights = [
                {
                    "id": r[0], "type": r[1], "title": r[2], "description": r[3],
                    "impact": r[4], "relevance": r[5],
                    "companies": r[6] if isinstance(r[6], list) else json.loads(r[6]) if r[6] else [],
                    "created_at": str(r[7]),
                }
                for r in cur.fetchall()
            ]

            # Active alerts
            cur.execute("""
                SELECT ma.id, ma.alert_level, ma.message, ma.created_at,
                       mi.title, mi.relevance_score
                FROM market_alerts ma
                JOIN market_insights mi ON mi.id = ma.insight_id
                WHERE NOT ma.acknowledged
                ORDER BY ma.created_at DESC
                LIMIT 10
            """)
            alerts = [
                {
                    "id": r[0], "level": r[1], "message": r[2], "created_at": str(r[3]),
                    "insight_title": r[4], "relevance": r[5],
                }
                for r in cur.fetchall()
            ]

            # Stats
            cur.execute("""
                SELECT insight_type, COUNT(*) as cnt
                FROM market_insights
                WHERE created_at > NOW() - INTERVAL '%s days'
                GROUP BY insight_type ORDER BY cnt DESC
            """, (days,))
            by_type = {r[0]: r[1] for r in cur.fetchall()}

            # Sources status
            cur.execute("""
                SELECT name, last_fetched, active
                FROM market_sources ORDER BY last_fetched DESC NULLS LAST
            """)
            sources = [
                {"name": r[0], "last_fetched": str(r[1]) if r[1] else None, "active": r[2]}
                for r in cur.fetchall()
            ]

    return {
        "insights": insights,
        "alerts": alerts,
        "stats": {"by_type": by_type, "total_insights": len(insights), "active_alerts": len(alerts)},
        "sources": sources,
    }


def get_market_insights(
    insight_type: str | None = None,
    min_relevance: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get filtered market insights."""
    _ensure_tables()

    clauses = ["1=1"]
    params: list[Any] = []
    if insight_type:
        clauses.append("insight_type = %s")
        params.append(insight_type)
    if min_relevance > 0:
        clauses.append("relevance_score >= %s")
        params.append(min_relevance)
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, insight_type, title, description, impact_assessment,
                       relevance_score, companies_affected, created_at
                FROM market_insights
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT %s
            """, params)
            return [
                {
                    "id": r[0], "type": r[1], "title": r[2], "description": r[3],
                    "impact": r[4], "relevance": r[5],
                    "companies": r[6] if isinstance(r[6], list) else json.loads(r[6]) if r[6] else [],
                    "created_at": str(r[7]),
                }
                for r in cur.fetchall()
            ]


def add_market_source(name: str, url: str, source_type: str = "rss") -> dict[str, Any]:
    """Add a new market data source."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO market_sources (name, source_type, url)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (url) DO UPDATE SET name = EXCLUDED.name, active = TRUE
                   RETURNING id""",
                (name, source_type, url),
            )
            sid = cur.fetchone()[0]
            conn.commit()
    return {"id": sid, "name": name, "url": url, "source_type": source_type}


def get_market_alerts(acknowledged: bool = False) -> list[dict[str, Any]]:
    """Get market alerts."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ma.id, ma.alert_level, ma.message, ma.acknowledged, ma.created_at,
                       mi.title, mi.insight_type, mi.relevance_score
                FROM market_alerts ma
                JOIN market_insights mi ON mi.id = ma.insight_id
                WHERE ma.acknowledged = %s
                ORDER BY ma.created_at DESC LIMIT 20
            """, (acknowledged,))
            return [
                {
                    "id": r[0], "level": r[1], "message": r[2], "acknowledged": r[3],
                    "created_at": str(r[4]), "insight_title": r[5],
                    "insight_type": r[6], "relevance": r[7],
                }
                for r in cur.fetchall()
            ]


# ================================================================
# Main pipeline
# ================================================================

def run_market_scan() -> dict[str, Any]:
    """Main pipeline: fetch → analyze → return dashboard. Called by cron."""
    _ensure_tables()
    _seed_default_sources()
    started = datetime.now(tz=timezone.utc)

    fetch_result = fetch_market_data()
    analysis_result = analyze_market_items()
    dashboard = get_market_dashboard(days=1)

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("market_scan_done", latency_ms=latency_ms)

    return {
        "success": True,
        "fetch": fetch_result,
        "analysis": analysis_result,
        "dashboard_summary": {
            "total_insights": dashboard["stats"]["total_insights"],
            "active_alerts": dashboard["stats"]["active_alerts"],
        },
        "latency_ms": latency_ms,
    }
