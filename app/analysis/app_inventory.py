"""
Application Inventory — discover apps/tools used across the organization.

Scans chunks/documents for mentions of applications, platforms, file formats.
Tracks: who uses what, how often, in which processes.
Deep analysis: costs, TCO, replacement feasibility, priority ranking.

Cron: part of process_discovery (Sunday weekly)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

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

# Extended patterns for deep discovery
EMAIL_SIGNATURE_PATTERNS = {
    "Zoom": r"(?i)zoom\.us|join\.zoom",
    "WebEx": r"(?i)webex\.com|cisco webex",
    "Google Meet": r"(?i)meet\.google\.com",
    "Calendly": r"(?i)calendly\.com",
    "HubSpot": r"(?i)hubspot",
    "Salesforce": r"(?i)salesforce",
    "Monday.com": r"(?i)monday\.com",
    "Asana": r"(?i)asana\.com",
    "Trello": r"(?i)trello\.com",
    "Notion": r"(?i)notion\.so|notion\.com",
    "Miro": r"(?i)miro\.com",
    "Figma": r"(?i)figma\.com",
    "1Password": r"(?i)1password",
    "LastPass": r"(?i)lastpass",
    "Dropbox": r"(?i)dropbox\.com",
    "Google Drive": r"(?i)drive\.google\.com|docs\.google",
    "OneDrive": r"(?i)onedrive|sharepoint",
    "Zapier": r"(?i)zapier\.com",
    "Power Automate": r"(?i)power automate|flow\.microsoft",
    "Xero": r"(?i)\bxero\b",
    "Symfonia": r"(?i)\bsymfonia\b",
    "Comarch ERP": r"(?i)comarch.{0,5}erp|comarch.{0,5}optima",
    "enova365": r"(?i)\benova\b",
    "XTRF": r"(?i)\bxtrf\b",
    "PGE Online": r"(?i)pge.{0,5}online",
}

# File format → app inference
FILE_FORMAT_APP_MAP = {
    ".docx": "Microsoft Word",
    ".pptx": "Microsoft PowerPoint",
    ".pdf": "Adobe Acrobat",
    ".vsdx": "Microsoft Visio",
    ".mpp": "Microsoft Project",
}

COST_ANALYSIS_PROMPT = """Jesteś analitykiem IT w polskiej firmie energetycznej (REH/REF, ~50 pracowników).
Na podstawie listy aplikacji oszacuj koszty i zastępowalność.

Dla każdej aplikacji zwróć JSON:
{
  "app_name": "...",
  "vendor": "firma dostarczająca",
  "cost_monthly_pln": N,
  "cost_yearly_pln": N,
  "cost_breakdown": {
    "license_pln": N,
    "integration_monthly_pln": N,
    "human_time_hours_monthly": N,
    "human_time_cost_pln": N
  },
  "replacement_feasibility": 0-100,
  "replacement_plan": {
    "gilbertus_module": "nazwa modułu lub 'new: opis'",
    "dev_hours": N,
    "description": "co dokładnie moduł zastępuje",
    "limitations": "czego nie zastąpi"
  },
  "tco_analysis": {
    "annual_total_pln": N,
    "switching_cost_pln": N,
    "risk_notes": "..."
  }
}

Zasady:
- Polskie ceny rynkowe (licencja per user ~50 PLN/msc, enterprise ~200-500 PLN/msc)
- Human time at 150 PLN/h (specialist), 200 PLN/h (developer)
- Bądź realistyczny z feasibility — 0 = nie da się zastąpić, 100 = trywialne
- Uwzględnij: lock-in, migrację danych, szkolenia, risk
- Odpowiedz TYLKO JSON array, bez dodatkowego tekstu."""


DEEP_DISCOVERY_PROMPT = """Na podstawie fragmentów komunikacji z firmy energetycznej, zidentyfikuj APLIKACJE, PLATFORMY i NARZĘDZIA ZEWNĘTRZNE, które są używane.

Szukaj:
- Nazw produktów/platform/SaaS
- Linków do narzędzi (np. app.example.com)
- Podpisów email z nazwami narzędzi
- Powiadomień z aplikacji ("Notification from...")
- Formatów plików sugerujących aplikacje (.vsdx = Visio, .mpp = Project)
- Wzmianek o systemach wewnętrznych

Zwróć JSON array:
[{"name": "AppName", "source": "skąd wykryto", "context": "krótki cytat"}]

WAŻNE: Nie zwracaj oczywistych (email, przeglądarka). Szukaj SPECJALISTYCZNYCH narzędzi.
Odpowiedz TYLKO JSON array."""


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
            # Add new columns for deep analysis (idempotent ALTERs)
            for col_sql in [
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS vendor TEXT",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS discovery_sources JSONB DEFAULT '[]'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS supported_processes JSONB DEFAULT '[]'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS user_details JSONB DEFAULT '[]'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS data_flow_types JSONB DEFAULT '[]'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS cost_monthly_pln NUMERIC DEFAULT 0",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS cost_yearly_pln NUMERIC DEFAULT 0",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS cost_breakdown JSONB DEFAULT '{}'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS replacement_feasibility INTEGER DEFAULT 0",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS replacement_plan JSONB DEFAULT '{}'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS tco_analysis JSONB DEFAULT '{}'",
                "ALTER TABLE app_inventory ADD COLUMN IF NOT EXISTS replacement_priority_rank INTEGER",
            ]:
                cur.execute(col_sql)

            # Cost history table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_cost_history (
                    id BIGSERIAL PRIMARY KEY,
                    app_id BIGINT NOT NULL REFERENCES app_inventory(id) ON DELETE CASCADE,
                    month DATE NOT NULL,
                    license_cost_pln NUMERIC DEFAULT 0,
                    integration_cost_pln NUMERIC DEFAULT 0,
                    human_time_hours NUMERIC DEFAULT 0,
                    human_time_cost_pln NUMERIC DEFAULT 0,
                    total_cost_pln NUMERIC DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(app_id, month)
                );
                CREATE INDEX IF NOT EXISTS idx_ach_app ON app_cost_history(app_id);
            """)
            conn.commit()


# ---------------------------------------------------------------------------
# Original scan (preserved for non-regression)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# F1: Deep Application Discovery
# ---------------------------------------------------------------------------

def scan_applications_deep(days: int = 90) -> dict[str, Any]:
    """Enhanced app discovery: email signatures, calendar, doc metadata, notifications + LLM."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    # Step 1: Run basic scan first (preserves existing behavior)
    basic = scan_applications(days=days)

    # Step 2: Extended pattern scan (signatures, URLs, notifications)
    extended_found = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for app_name, pattern in EMAIL_SIGNATURE_PATTERNS.items():
                cur.execute("""
                    SELECT COUNT(DISTINCT c.id)
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.text ~* %s
                    AND d.created_at > NOW() - INTERVAL '%s days'
                """, (pattern, days))
                count = cur.fetchone()[0]
                if count > 0:
                    extended_found[app_name] = count

    # Step 3: File format inference
    format_found = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for ext, app_name in FILE_FORMAT_APP_MAP.items():
                cur.execute("""
                    SELECT COUNT(*)
                    FROM documents d
                    WHERE d.title ILIKE %s
                    AND d.created_at > NOW() - INTERVAL '%s days'
                """, (f"%{ext}", days))
                count = cur.fetchone()[0]
                if count > 0:
                    format_found[app_name] = count

    # Step 4: LLM deep discovery from sample chunks
    llm_found = _llm_discover_apps(days)

    # Step 5: Merge all discoveries and store
    all_apps = {}
    for name, count in basic.get("details", {}).items():
        all_apps.setdefault(name, {"count": 0, "sources": []})
        all_apps[name]["count"] += count
        all_apps[name]["sources"].append("text_mention")

    for name, count in extended_found.items():
        all_apps.setdefault(name, {"count": 0, "sources": []})
        all_apps[name]["count"] += count
        all_apps[name]["sources"].append("email_signature_or_url")

    for name, count in format_found.items():
        all_apps.setdefault(name, {"count": 0, "sources": []})
        all_apps[name]["count"] += count
        all_apps[name]["sources"].append("file_format")

    for item in llm_found:
        name = item.get("name", "")
        if not name:
            continue
        all_apps.setdefault(name, {"count": 0, "sources": []})
        all_apps[name]["count"] += 1
        all_apps[name]["sources"].append(f"llm_discovery:{item.get('source', '?')}")

    # Step 6: Store/update with discovery_sources
    stored = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for app_name, info in sorted(all_apps.items(), key=lambda x: -x[1]["count"]):
                sources_json = json.dumps(list(set(info["sources"])))
                cur.execute("""
                    INSERT INTO app_inventory (name, mention_count, discovery_sources, last_seen)
                    VALUES (%s, %s, %s::jsonb, NOW())
                    ON CONFLICT (name) DO UPDATE SET
                        mention_count = GREATEST(app_inventory.mention_count, EXCLUDED.mention_count),
                        discovery_sources = EXCLUDED.discovery_sources,
                        last_seen = NOW()
                """, (app_name, info["count"], sources_json))
                stored += 1
            conn.commit()

    # Step 7: Enrich user_details from entity co-occurrence
    _enrich_user_details(days)

    # Step 8: Link to discovered processes
    _link_to_processes()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("deep_app_scan_done", apps=stored, latency_ms=latency_ms)
    return {
        "apps_found": stored,
        "basic_scan": len(basic.get("details", {})),
        "extended_patterns": len(extended_found),
        "file_formats": len(format_found),
        "llm_discovered": len(llm_found),
        "latency_ms": latency_ms,
    }


def _llm_discover_apps(days: int) -> list[dict]:
    """Use LLM to discover apps from sample chunks (email signatures, notifications)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Sample chunks from emails (signatures often mention tools)
            cur.execute("""
                SELECT LEFT(c.text, 500)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE s.source_type IN ('email', 'teams')
                AND d.created_at > NOW() - INTERVAL '%s days'
                AND (c.text ~* 'sent from|powered by|notification|unsubscribe|app\\..*\\.com|manage\\..*\\.com')
                ORDER BY RANDOM()
                LIMIT 50
            """, (days,))
            samples = [r[0] for r in cur.fetchall()]

    if not samples:
        return []

    sample_text = "\n---\n".join(samples[:30])
    try:
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=1500,
            temperature=0,
            system=[{"type": "text", "text": DEEP_DISCOVERY_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": sample_text}],
        )
        log_anthropic_cost(ANTHROPIC_FAST, "app_inventory.deep_discovery", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        log.warning("llm_app_discovery_failed", error=str(e))
        return []


def _enrich_user_details(days: int):
    """For each app, find which people use it (from entity co-occurrence in chunks)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM app_inventory")
            apps = cur.fetchall()

    for app_id, app_name in apps:
        pattern = KNOWN_APP_PATTERNS.get(app_name) or EMAIL_SIGNATURE_PATTERNS.get(app_name)
        if not pattern:
            pattern = re.escape(app_name)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.canonical_name, COUNT(DISTINCT c.id) as usage_count,
                           MAX(d.created_at) as last_used
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    JOIN chunk_entities ce ON ce.chunk_id = c.id
                    JOIN entities e ON e.id = ce.entity_id AND e.entity_type = 'person'
                    WHERE c.text ~* %s
                    AND d.created_at > NOW() - INTERVAL '%s days'
                    GROUP BY e.canonical_name
                    ORDER BY usage_count DESC
                    LIMIT 20
                """, (pattern, days))
                users = [
                    {"person": r[0], "usage_count": r[1], "last_used": r[2].isoformat() if r[2] else None}
                    for r in cur.fetchall()
                ]

        if users:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE app_inventory SET user_details = %s WHERE id = %s",
                        (json.dumps(users, ensure_ascii=False, default=str), app_id),
                    )
                    conn.commit()


def _link_to_processes():
    """Link apps to discovered processes via tools_used field."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM app_inventory")
            apps = cur.fetchall()

            for app_id, app_name in apps:
                cur.execute("""
                    SELECT id, name FROM discovered_processes
                    WHERE tools_used::text ILIKE %s
                """, (f"%{app_name}%",))
                linked = [{"process_id": r[0], "process_name": r[1]} for r in cur.fetchall()]

                if linked:
                    cur.execute(
                        "UPDATE app_inventory SET supported_processes = %s WHERE id = %s",
                        (json.dumps(linked, ensure_ascii=False), app_id),
                    )
            conn.commit()


# ---------------------------------------------------------------------------
# F1: Cost Analysis
# ---------------------------------------------------------------------------

def analyze_app_costs(app_id: int | None = None) -> dict[str, Any]:
    """LLM-powered cost analysis for apps in inventory."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if app_id:
                cur.execute("""
                    SELECT id, name, category, mention_count, user_details, supported_processes
                    FROM app_inventory WHERE id = %s
                """, (app_id,))
            else:
                cur.execute("""
                    SELECT id, name, category, mention_count, user_details, supported_processes
                    FROM app_inventory WHERE cost_monthly_pln = 0 OR cost_monthly_pln IS NULL
                    ORDER BY mention_count DESC
                """)
            apps = cur.fetchall()

    if not apps:
        return {"message": "No apps to analyze", "analyzed": 0}

    # Build context for LLM
    app_list = []
    for row in apps:
        users = row[4] if isinstance(row[4], list) else json.loads(row[4]) if row[4] else []
        processes = row[5] if isinstance(row[5], list) else json.loads(row[5]) if row[5] else []
        app_list.append({
            "name": row[1],
            "category": row[2],
            "mentions": row[3],
            "users_count": len(users),
            "top_users": [u.get("person", "?") for u in users[:5]],
            "processes": [p.get("process_name", "?") for p in processes[:5]],
        })

    # Batch in groups of 10
    analyzed = 0
    all_results = []
    for i in range(0, len(app_list), 10):
        batch = app_list[i:i + 10]
        batch_json = json.dumps(batch, ensure_ascii=False, default=str)

        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4000,
                temperature=0,
                system=[{"type": "text", "text": COST_ANALYSIS_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": f"Przeanalizuj koszty i zastępowalność:\n{batch_json}"}],
            )
            log_anthropic_cost(ANTHROPIC_MODEL, "app_inventory.cost_analysis", response.usage)

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3].strip()

            results = json.loads(raw)
            if isinstance(results, dict):
                results = [results]
            all_results.extend(results)

        except (json.JSONDecodeError, Exception) as e:
            log.warning("cost_analysis_batch_failed", batch_start=i, error=str(e))
            continue

    # Store results
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for result in all_results:
                app_name = result.get("app_name", "")
                if not app_name:
                    continue

                cost_breakdown = result.get("cost_breakdown", {})
                replacement_plan = result.get("replacement_plan", {})
                tco = result.get("tco_analysis", {})

                cur.execute("""
                    UPDATE app_inventory SET
                        vendor = %s,
                        cost_monthly_pln = %s,
                        cost_yearly_pln = %s,
                        cost_breakdown = %s,
                        replacement_feasibility = %s,
                        replacement_plan = %s,
                        tco_analysis = %s
                    WHERE name = %s
                """, (
                    result.get("vendor", ""),
                    result.get("cost_monthly_pln", 0),
                    result.get("cost_yearly_pln", 0),
                    json.dumps(cost_breakdown, ensure_ascii=False, default=str),
                    result.get("replacement_feasibility", 0),
                    json.dumps(replacement_plan, ensure_ascii=False, default=str),
                    json.dumps(tco, ensure_ascii=False, default=str),
                    app_name,
                ))
                analyzed += 1

                # Record cost history
                cur.execute("""
                    INSERT INTO app_cost_history (app_id, month, license_cost_pln, integration_cost_pln,
                        human_time_hours, human_time_cost_pln, total_cost_pln)
                    SELECT id, DATE_TRUNC('month', NOW())::date,
                        %s, %s, %s, %s, %s
                    FROM app_inventory WHERE name = %s
                    ON CONFLICT (app_id, month) DO UPDATE SET
                        license_cost_pln = EXCLUDED.license_cost_pln,
                        total_cost_pln = EXCLUDED.total_cost_pln
                """, (
                    cost_breakdown.get("license_pln", 0),
                    cost_breakdown.get("integration_monthly_pln", 0),
                    cost_breakdown.get("human_time_hours_monthly", 0),
                    cost_breakdown.get("human_time_cost_pln", 0),
                    result.get("cost_monthly_pln", 0),
                    app_name,
                ))
            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("app_cost_analysis_done", analyzed=analyzed, latency_ms=latency_ms)
    return {"analyzed": analyzed, "results": all_results, "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# F1: Replacement Feasibility Assessment
# ---------------------------------------------------------------------------

def assess_replacement_feasibility(app_id: int | None = None) -> dict[str, Any]:
    """Score replacement feasibility and generate replacement plans."""
    _ensure_tables()

    # If costs not yet analyzed, run cost analysis first
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if app_id:
                cur.execute("SELECT COUNT(*) FROM app_inventory WHERE id = %s AND (cost_monthly_pln = 0 OR cost_monthly_pln IS NULL)", (app_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM app_inventory WHERE replacement_feasibility = 0 AND cost_monthly_pln > 0")
            needs_analysis = cur.fetchone()[0]

    if needs_analysis == 0 and not app_id:
        # Run cost analysis for apps without cost data
        analyze_app_costs(app_id)

    return analyze_app_costs(app_id)


# ---------------------------------------------------------------------------
# F1: Priority Ranking
# ---------------------------------------------------------------------------

def rank_replacement_priority() -> list[dict]:
    """Rank apps by replacement priority: (annual_cost * feasibility) / dev_hours."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, cost_yearly_pln, replacement_feasibility,
                       replacement_plan, tco_analysis, vendor, mention_count
                FROM app_inventory
                WHERE replacement_feasibility > 0
                ORDER BY replacement_feasibility DESC
            """)
            apps = cur.fetchall()

    ranked = []
    for row in apps:
        app_id, name, category, yearly_cost, feasibility, plan, tco, vendor, mentions = row
        plan = plan if isinstance(plan, dict) else json.loads(plan) if plan else {}
        tco = tco if isinstance(tco, dict) else json.loads(tco) if tco else {}

        dev_hours = plan.get("dev_hours", 100)  # default 100h if unknown
        yearly_cost = float(yearly_cost or 0)

        # Priority score: higher = replace sooner
        if dev_hours > 0 and yearly_cost > 0:
            priority = (yearly_cost * (feasibility / 100)) / (dev_hours * 200)  # 200 PLN/h dev cost
        else:
            priority = feasibility / 100

        ranked.append({
            "app_id": app_id,
            "name": name,
            "category": category,
            "vendor": vendor,
            "yearly_cost_pln": yearly_cost,
            "replacement_feasibility": feasibility,
            "dev_hours": dev_hours,
            "priority_score": round(priority, 3),
            "roi_ratio": round(yearly_cost / max(dev_hours * 200, 1), 2),
            "mentions": mentions,
        })

    ranked.sort(key=lambda x: -x["priority_score"])

    # Store ranks
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for rank, app in enumerate(ranked, 1):
                cur.execute(
                    "UPDATE app_inventory SET replacement_priority_rank = %s WHERE id = %s",
                    (rank, app["app_id"]),
                )
            conn.commit()

    log.info("replacement_ranking_done", total=len(ranked))
    return ranked


# ---------------------------------------------------------------------------
# F1: Full Deep Analysis Report
# ---------------------------------------------------------------------------

def get_app_deep_analysis(app_id: int | None = None) -> dict | list[dict]:
    """Full analysis report for one or all apps."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if app_id:
                cur.execute("SELECT * FROM app_inventory WHERE id = %s", (app_id,))
            else:
                cur.execute("SELECT * FROM app_inventory ORDER BY COALESCE(replacement_priority_rank, 9999), mention_count DESC")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Parse JSONB fields
    jsonb_fields = ["users", "processes", "discovery_sources", "user_details",
                    "supported_processes", "data_flow_types", "cost_breakdown",
                    "replacement_plan", "tco_analysis"]
    for row in rows:
        for field in jsonb_fields:
            val = row.get(field)
            if isinstance(val, str):
                try:
                    row[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass

    if app_id:
        return rows[0] if rows else {"error": f"App {app_id} not found"}
    return rows


def get_app_replacement_ranking() -> dict:
    """Get replacement ranking with summary stats."""
    ranking = rank_replacement_priority()

    total_yearly_cost = sum(a["yearly_cost_pln"] for a in ranking)
    total_replaceable_cost = sum(
        a["yearly_cost_pln"] * a["replacement_feasibility"] / 100
        for a in ranking
    )
    total_dev_hours = sum(a["dev_hours"] for a in ranking if a["replacement_feasibility"] > 30)

    return {
        "ranking": ranking,
        "summary": {
            "total_apps": len(ranking),
            "total_yearly_cost_pln": round(total_yearly_cost, 2),
            "total_replaceable_savings_pln": round(total_replaceable_cost, 2),
            "total_dev_hours_needed": total_dev_hours,
            "avg_roi_ratio": round(
                sum(a["roi_ratio"] for a in ranking) / max(len(ranking), 1), 2
            ),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        print(json.dumps(scan_applications(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "deep":
        print(json.dumps(scan_applications_deep(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "costs":
        print(json.dumps(analyze_app_costs(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "rank":
        print(json.dumps(rank_replacement_priority(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "report":
        print(json.dumps(get_app_deep_analysis(), ensure_ascii=False, indent=2, default=str))
    else:
        print("Usage: python -m app.analysis.app_inventory [scan|deep|costs|rank|report]")
