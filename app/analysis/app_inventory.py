"""
Application Inventory — discover apps/tools used across the organization.

Scans chunks/documents for mentions of applications, platforms, file formats.
Tracks: who uses what, how often, in which processes.

Cron: part of process_discovery (Sunday weekly)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

# Known application patterns (regex) — bootstrapping, but LLM adds unknown ones
KNOWN_APP_PATTERNS = {
    "TGE": r"\bTGE\b|Towarowa Giełda|towarowa giełda",
    "EEX": r"\bEEX\b|European Energy Exchange",
    "Bloomberg": r"\bBloomberg\b|BBERG",
    "Excel": r"\bExcel\b|\.xlsx?\b|arkusz",
    "SAP": r"\bSAP\b",
    "Teams": r"\bTeams\b|Microsoft Teams",
    "SharePoint": r"\bSharePoint\b",
    "Outlook": r"\bOutlook\b",
    "Power BI": r"\bPower BI\b|PowerBI",
    "Calamari": r"\bCalamari\b",
    "Plaud": r"\bPlaud\b",
    "Whisper": r"\bWhisper\b",
    "Claude": r"\bClaude\b|Anthropic",
    "ChatGPT": r"\bChatGPT\b|OpenAI",
    "Qdrant": r"\bQdrant\b",
    "DocuSign": r"\bDocuSign\b|Docusign",
    "Slack": r"\bSlack\b",
    "Jira": r"\bJira\b|Atlassian",
    "Confluence": r"\bConfluence\b",
    "KRS": r"\bKRS\b|rejestr.io",
    "CEIDG": r"\bCEIDG\b",
}


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_inventory (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT DEFAULT 'other',
                    mention_count INTEGER DEFAULT 0,
                    users JSONB DEFAULT '[]',
                    processes JSONB DEFAULT '[]',
                    gilbertus_replacement TEXT,
                    replacement_status TEXT DEFAULT 'not_planned'
                        CHECK (replacement_status IN ('not_planned', 'planned', 'partial', 'replaced', 'not_replaceable')),
                    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()


def scan_applications(days: int = 90) -> dict[str, Any]:
    """Scan chunks for application mentions."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)
    results = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for app_name, pattern in KNOWN_APP_PATTERNS.items():
                cur.execute("""
                    SELECT COUNT(DISTINCT c.id)
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.text ~* %s
                    AND d.created_at > NOW() - INTERVAL '%s days'
                """, (pattern, days))
                count = cur.fetchone()[0]
                if count > 0:
                    results[app_name] = count

    # Store/update inventory
    stored = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for app_name, count in sorted(results.items(), key=lambda x: -x[1]):
                cur.execute("""
                    INSERT INTO app_inventory (name, mention_count, last_seen)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (name) DO UPDATE SET
                        mention_count = EXCLUDED.mention_count,
                        last_seen = NOW()
                """, (app_name, count))
                stored += 1
            conn.commit()

    # LLM categorization for uncategorized apps
    uncategorized = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, mention_count FROM app_inventory WHERE category = 'other' ORDER BY mention_count DESC")
            uncategorized = [(r[0], r[1]) for r in cur.fetchall()]

    if uncategorized:
        app_list = ", ".join(f"{a[0]} ({a[1]} mentions)" for a in uncategorized[:20])
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": f"Categorize these apps used in an energy trading company. Return JSON: {{\"AppName\": \"category\"}}. Categories: trading, finance, hr, communication, document, development, analytics, compliance, other.\n\nApps: {app_list}"}],
        )
        log_anthropic_cost(ANTHROPIC_FAST, "app_inventory", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        try:
            categories = json.loads(raw)
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    for app_name, cat in categories.items():
                        cur.execute("UPDATE app_inventory SET category = %s WHERE name = %s", (cat, app_name))
                    conn.commit()
        except json.JSONDecodeError:
            pass

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("app_scan_done", apps=stored, latency_ms=latency_ms)
    return {"apps_found": stored, "details": results, "latency_ms": latency_ms}


def get_app_inventory() -> list[dict]:
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, category, mention_count, gilbertus_replacement, replacement_status FROM app_inventory ORDER BY mention_count DESC")
            return [{"name": r[0], "category": r[1], "mentions": r[2], "replacement": r[3], "status": r[4]} for r in cur.fetchall()]
