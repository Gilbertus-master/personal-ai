"""
Cron Registry — centralne repozytorium cronów z per-user control.

Każdy cron job jest zdefiniowany w DB z metadanymi:
- schedule (cron expression)
- command (co uruchomić)
- owner (sebastian / roch / krystian / system)
- enabled per user
- category (ingestion, extraction, analysis, backup, intelligence, communication)
- description

Pozwala:
- Centralnie zarządzać wszystkimi cronami
- Per-user enable/disable
- Generować crontab file z aktywnych cronów
- Audytować kto ma co aktywne
- MCP tool: gilbertus_crons

Usage:
    python -m app.orchestrator.cron_registry --list
    python -m app.orchestrator.cron_registry --generate [user]
    python -m app.orchestrator.cron_registry --enable JOB_NAME [user]
    python -m app.orchestrator.cron_registry --disable JOB_NAME [user]
    python -m app.orchestrator.cron_registry --seed
"""
from __future__ import annotations

import json
import sys
from typing import Any

import structlog
from psycopg.errors import ForeignKeyViolation
from app.config.timezone import APP_TIMEZONE_NAME
from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

# ================================================================
# DB Setup
# ================================================================

_tables_ensured = False
def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cron_registry (
                    id BIGSERIAL PRIMARY KEY,
                    job_name TEXT NOT NULL UNIQUE,
                    schedule TEXT NOT NULL,
                    command TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL DEFAULT 'general',
                    log_file TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS cron_user_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    job_name TEXT NOT NULL REFERENCES cron_registry(job_name) ON DELETE CASCADE,
                    username TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(job_name, username)
                );

                CREATE INDEX IF NOT EXISTS idx_cron_user ON cron_user_assignments(username);
            """)
        conn.commit()
    log.debug("cron_registry_tables_ensured")
    _tables_ensured = True


# ================================================================
# CRUD
# ================================================================

def register_job(
    job_name: str,
    schedule: str,
    command: str,
    description: str = "",
    category: str = "general",
    log_file: str | None = None,
    default_users: list[str] | None = None,
) -> dict[str, Any]:
    """Register or update a cron job in the registry."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cron_registry (job_name, schedule, command, description, category, log_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_name) DO UPDATE SET
                    schedule = EXCLUDED.schedule,
                    command = EXCLUDED.command,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    log_file = EXCLUDED.log_file,
                    updated_at = NOW()
                RETURNING id
            """, (job_name, schedule, command, description, category, log_file))
            job_id = cur.fetchall()[0][0]

            # Assign to default users
            if default_users:
                for user in default_users:
                    cur.execute("""
                        INSERT INTO cron_user_assignments (job_name, username, enabled)
                        VALUES (%s, %s, TRUE)
                        ON CONFLICT (job_name, username) DO NOTHING
                    """, (job_name, user))
        conn.commit()

    return {"job_id": job_id, "job_name": job_name, "users": default_users or []}


def enable_job(job_name: str, username: str) -> dict[str, Any]:
    """Enable a cron job for a specific user."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO cron_user_assignments (job_name, username, enabled)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (job_name, username) DO UPDATE SET enabled = TRUE
                """, (job_name, username))
            except ForeignKeyViolation:
                conn.rollback()
                return {"error": f"Job '{job_name}' not found in registry"}
        conn.commit()
    return {"job_name": job_name, "username": username, "enabled": True}


def disable_job(job_name: str, username: str) -> dict[str, Any]:
    """Disable a cron job for a specific user."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE cron_user_assignments SET enabled = FALSE
                WHERE job_name = %s AND username = %s
            """, (job_name, username))
            if cur.rowcount == 0:
                return {"error": f"Assignment not found: {job_name} / {username}"}
        conn.commit()
    return {"job_name": job_name, "username": username, "enabled": False}


def list_jobs(username: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """List all cron jobs with user assignment status."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if username:
                cur.execute("""
                    SELECT cr.job_name, cr.schedule, cr.command, cr.description, cr.category,
                           cr.log_file, cua.enabled, cua.username
                    FROM cron_registry cr
                    LEFT JOIN cron_user_assignments cua
                        ON cua.job_name = cr.job_name AND cua.username = %s
                    WHERE (%s IS NULL OR cr.category = %s)
                    ORDER BY cr.category, cr.job_name
                """, (username, category, category))
            else:
                cur.execute("""
                    SELECT cr.job_name, cr.schedule, cr.command, cr.description, cr.category,
                           cr.log_file,
                           (SELECT string_agg(
                               cua.username || ':' || CASE WHEN cua.enabled THEN 'on' ELSE 'off' END,
                               ', '
                           ) FROM cron_user_assignments cua WHERE cua.job_name = cr.job_name) as users
                    FROM cron_registry cr
                    WHERE (%s IS NULL OR cr.category = %s)
                    ORDER BY cr.category, cr.job_name
                """, (category, category))

            rows = cur.fetchall()

    if username:
        return [
            {"job_name": r[0], "schedule": r[1], "command": r[2], "description": r[3],
             "category": r[4], "log_file": r[5],
             "enabled": r[6] if r[6] is not None else False,
             "username": username}
            for r in rows
        ]
    else:
        return [
            {"job_name": r[0], "schedule": r[1], "command": r[2], "description": r[3],
             "category": r[4], "log_file": r[5], "users": r[6] or "none"}
            for r in rows
        ]


def get_user_jobs(username: str) -> list[dict[str, Any]]:
    """Get only enabled jobs for a specific user."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cr.job_name, cr.schedule, cr.command, cr.description,
                       cr.category, cr.log_file
                FROM cron_registry cr
                JOIN cron_user_assignments cua ON cua.job_name = cr.job_name
                WHERE cua.username = %s AND cua.enabled = TRUE
                ORDER BY cr.category, cr.job_name
            """, (username,))
            return [
                {"job_name": r[0], "schedule": r[1], "command": r[2],
                 "description": r[3], "category": r[4], "log_file": r[5]}
                for r in cur.fetchall()
            ]


# ================================================================
# Crontab Generation
# ================================================================

def generate_crontab(username: str) -> str:
    """Generate a crontab file from enabled jobs for a user."""
    jobs = get_user_jobs(username)
    if not jobs:
        return f"# No cron jobs enabled for {username}\n"

    lines = [
        f"TZ={APP_TIMEZONE_NAME}",
        f"# === Gilbertus Albans — crontab for {username} ===",
        f"# Auto-generated from cron_registry. {len(jobs)} jobs enabled.",
        "# Do NOT edit manually — use: python -m app.orchestrator.cron_registry",
        "",
    ]

    current_category = None
    for job in jobs:
        if job["category"] != current_category:
            current_category = job["category"]
            lines.append(f"# --- {current_category} ---")

        log_path = job["log_file"] or f"/home/sebastian/personal-ai/logs/{job['job_name']}.log"
        comment = f"  # {job['description']}" if job["description"] else ""
        lines.append(f"{job['schedule']} {job['command']} >> {log_path} 2>&1{comment}")

    lines.append("")
    return "\n".join(lines)


# ================================================================
# Seed — populate registry from existing crontab
# ================================================================

SEED_JOBS = [
    # Backup & Recovery
    {"job_name": "backup_db", "schedule": "0 3 * * *",
     "command": "cd /home/sebastian/personal-ai && /bin/bash ./scripts/backup_db.sh",
     "description": "Full database backup (nightly)", "category": "backup",
     "log_file": "/home/sebastian/personal-ai/backups/backup.log",
     "users": ["sebastian"]},
    {"job_name": "backup_db_daytime", "schedule": "0 7,11,15,19,23 * * *",
     "command": "cd /home/sebastian/personal-ai && /bin/bash ./scripts/backup_db.sh",
     "description": "Database backup (daytime, every 4h)", "category": "backup",
     "log_file": "/home/sebastian/personal-ai/backups/backup.log",
     "users": ["sebastian"]},
    {"job_name": "prune_backups", "schedule": "20 3 * * *",
     "command": "cd /home/sebastian/personal-ai && /bin/bash ./scripts/prune_backups.sh",
     "description": "Prune old database backups", "category": "backup",
     "log_file": "/home/sebastian/personal-ai/backups/backup.log",
     "users": ["sebastian"]},
    {"job_name": "pg_auto_restore", "schedule": "@reboot",
     "command": "sleep 30 && cd /home/sebastian/personal-ai && /bin/bash ./scripts/pg_auto_restore.sh",
     "description": "Auto-restore Postgres on boot", "category": "backup",
     "log_file": "/home/sebastian/personal-ai/backups/auto_restore.log",
     "users": ["sebastian"]},

    # Ingestion
    {"job_name": "index_chunks", "schedule": "*/5 * * * *",
     "command": "cd /home/sebastian/personal-ai && TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache .venv/bin/python -m app.retrieval.index_chunks --batch-size 50 --limit 50",
     "description": "Auto-embed new chunks to Qdrant", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/auto_embed.log",
     "users": ["sebastian"]},
    {"job_name": "live_ingest", "schedule": "*/5 * * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -m app.ingestion.live_ingest",
     "description": "WhatsApp + Claude session live ingest", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/live_ingest.log",
     "users": ["sebastian"]},
    {"job_name": "plaud_monitor", "schedule": "*/15 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/plaud_monitor.sh",
     "description": "Plaud audio sync + transcription", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/plaud_monitor.log",
     "users": ["sebastian"]},
    {"job_name": "sync_corporate_data", "schedule": "15 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/sync_corporate_data.sh",
     "description": "Corporate email + Teams sync (Graph API)", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/sync_corporate_data.log",
     "users": ["sebastian"]},
    {"job_name": "archive_claude_sessions", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/archive_claude_sessions.sh",
     "description": "Archive Claude Code sessions to DB", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/claude_archive.log",
     "users": ["sebastian"]},

    # Extraction
    {"job_name": "turbo_extract", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/turbo_extract.sh 3000 12 claude-haiku-4-5-20251001",
     "description": "Entity + event extraction (12 workers)", "category": "extraction",
     "log_file": "/home/sebastian/personal-ai/logs/turbo_extract_cron.log",
     "users": ["sebastian"]},
    {"job_name": "extract_commitments", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/extract_commitments.sh 500 4 claude-haiku-4-5-20251001",
     "description": "Commitment extraction from chunks (4 workers)", "category": "extraction",
     "log_file": "/home/sebastian/personal-ai/logs/commitment_extract.log",
     "users": ["sebastian"]},

    # Intelligence
    {"job_name": "morning_brief", "schedule": "0 7 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/morning_brief.sh",
     "description": "Generate daily morning brief", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/morning_brief.log",
     "users": ["sebastian"]},
    {"job_name": "check_commitments", "schedule": "30 */2 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/check_commitments.sh",
     "description": "Commitment overdue + fulfillment check", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/commitment_check.log",
     "users": ["sebastian"]},
    {"job_name": "continuous_improvement", "schedule": "15 */2 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/continuous_improvement.sh",
     "description": "Self-improving rules extraction from audio", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/continuous_improvement.log",
     "users": ["sebastian"]},
    {"job_name": "intelligence_scan", "schedule": "0 22 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/intelligence_scan.sh",
     "description": "Contracts + delegation + blind spots + network (daily)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/intelligence_scan.log",
     "users": ["sebastian"]},
    {"job_name": "weekly_analysis", "schedule": "0 21 * * 5",
     "command": "cd /home/sebastian/personal-ai && bash scripts/weekly_analysis.sh",
     "description": "Sentiment + wellbeing + predictions (Friday 21:00)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/weekly_analysis.log",
     "users": ["sebastian"]},
    {"job_name": "weekly_synthesis", "schedule": "0 20 * * 0",
     "command": "cd /home/sebastian/personal-ai && bash scripts/weekly_synthesis.sh",
     "description": "Weekly executive synthesis (Sunday 20:00)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/weekly_synthesis.log",
     "users": ["sebastian"]},

    # Communication
    {"job_name": "meeting_prep", "schedule": "*/15 8-20 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/meeting_prep.sh",
     "description": "Meeting prep brief 30 min before meetings", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/meeting_prep.log",
     "users": ["sebastian"]},
    {"job_name": "response_drafter", "schedule": "*/15 8-20 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/response_drafter.sh 30",
     "description": "Auto-draft responses to incoming email/Teams", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/response_drafter.log",
     "users": ["sebastian"]},
    {"job_name": "generate_minutes", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/generate_minutes.sh",
     "description": "Generate meeting minutes from Plaud recordings", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/meeting_minutes.log",
     "users": ["sebastian"]},
    {"job_name": "send_insights", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/send_insights_to_whatsapp.sh",
     "description": "Smart insight delivery to WhatsApp", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/insight_delivery.log",
     "users": ["sebastian"]},
    {"job_name": "task_monitor", "schedule": "*/2 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/task_monitor.sh",
     "description": "WhatsApp task/approval monitor", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/task_monitor.log",
     "users": ["sebastian"]},

    # QC
    {"job_name": "code_quality_check", "schedule": "0 6 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/code_quality_check.sh",
     "description": "Code quality + non-regression check (daily 6:00)", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/code_quality.log",
     "users": ["sebastian"]},
    {"job_name": "verify_data_quality", "schedule": "45 7,11,15,19,23 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/verify_data_quality.sh",
     "description": "Data quality verification (5x/day)", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/data_quality.log",
     "users": ["sebastian"]},
    {"job_name": "generate_session_context", "schedule": "*/30 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/generate_session_context.sh",
     "description": "Regenerate SESSION_CONTEXT.md inventory", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/session_context.log",
     "users": ["sebastian"]},
    {"job_name": "quarterly_eval", "schedule": "0 8 1 1,4,7,10 *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/quarterly_eval.sh",
     "description": "Quarterly employee evaluations", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/quarterly_eval.log",
     "users": ["sebastian"]},
    # Wave 4: Proactive Command
    {"job_name": "scenario_auto_scan", "schedule": "0 17 * * 0",
     "command": "cd /home/sebastian/personal-ai && bash scripts/scenario_scan.sh",
     "description": "Auto-generate scenarios from risk signals (Sunday 18:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/scenario_scan.log",
     "users": ["sebastian"]},
    {"job_name": "market_scan_morning", "schedule": "0 6 * * 1-5",
     "command": "cd /home/sebastian/personal-ai && bash scripts/market_scan.sh",
     "description": "Market intelligence morning scan (7:00 CET weekdays)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/market_scan.log",
     "users": ["sebastian"]},
    {"job_name": "market_scan_afternoon", "schedule": "0 15 * * 1-5",
     "command": "cd /home/sebastian/personal-ai && bash scripts/market_scan.sh",
     "description": "Market intelligence afternoon update (16:00 CET weekdays)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/market_scan.log",
     "users": ["sebastian"]},
    {"job_name": "competitor_scan", "schedule": "0 19 * * 5",
     "command": "cd /home/sebastian/personal-ai && bash scripts/competitor_scan.sh",
     "description": "Competitor intelligence weekly scan (Friday 20:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/competitor_scan.log",
     "users": ["sebastian"]},
    # Etap 1: Smart Alert Delivery
    # Process Intelligence
    {"job_name": "process_discovery", "schedule": "0 16 * * 0",
     "command": "cd /home/sebastian/personal-ai && bash scripts/process_discovery.sh",
     "description": "Process Intelligence: full discovery cycle (Sunday 17:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/process_discovery.log",
     "users": ["sebastian"]},
    {"job_name": "health_check_deep", "schedule": "0 6,12,18 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.health_monitor import run_health_check; run_health_check()\"",
     "description": "Deep health check with WhatsApp alerts (3x/day)", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/health_check_deep.log",
     "users": ["sebastian"]},
    {"job_name": "strategic_radar", "schedule": "55 5 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.strategic_radar import generate_strategic_radar; generate_strategic_radar()\"",
     "description": "Strategic Radar: cross-domain correlation (6:55 UTC / 7:55 CET, before brief)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/strategic_radar.log",
     "users": ["sebastian"]},
    {"job_name": "auto_actions", "schedule": "*/30 8-20 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.orchestrator.auto_actions import run_auto_actions; run_auto_actions()\"",
     "description": "Auto-action proposals from market/competitor/goal signals", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/auto_actions.log",
     "users": ["sebastian"]},
    {"job_name": "decision_enrichment", "schedule": "0 22 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.decision_enrichment import enrich_recent_decisions; enrich_recent_decisions()\"",
     "description": "Enrich decisions with market/competitor/goal context (daily)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/decision_enrichment.log",
     "users": ["sebastian"]},
    {"job_name": "feedback_calibration", "schedule": "0 22 * * 0",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.feedback_calibration import run_calibration_cycle; run_calibration_cycle()\"",
     "description": "Weekly feedback calibration: adjust thresholds from engagement (Sunday)", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/feedback_calibration.log",
     "users": ["sebastian"]},
    {"job_name": "smart_alert_delivery", "schedule": "*/30 8-21 * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/smart_alert_delivery.sh",
     "description": "Smart alert delivery: market/competitor/predictive (every 30min 8-22 CET)", "category": "communication",
     "log_file": "/home/sebastian/personal-ai/logs/smart_alert_delivery.log",
     "users": ["sebastian"]},
    # Data Quality Calibrator (daily 5:30 CET / 4:30 UTC, before morning brief)
    {"job_name": "data_quality_calibrator", "schedule": "30 4 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.data_quality_calibrator import run_calibration; import json; print(json.dumps(run_calibration(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Data Quality Calibrator: auto-fix timestamps, orphans, dupes + alert on stale sources", "category": "qc",
     "log_file": "/home/sebastian/personal-ai/logs/data_quality_calibrator.log",
     "users": ["sebastian"]},
    # Plaud audio sync (every 15 min)
    {"job_name": "plaud_sync", "schedule": "*/15 * * * *",
     "command": "cd /home/sebastian/personal-ai && bash scripts/plaud_sync.sh",
     "description": "Plaud Pin S audio sync: pull latest recordings (every 15 min)", "category": "ingestion",
     "log_file": "/home/sebastian/personal-ai/logs/plaud_sync.log",
     "users": ["sebastian"]},
    # F2: Monthly Workforce Automation Analysis (CEO-only, 1st of month 3:00 CET / 2:00 UTC)
    {"job_name": "workforce_analysis", "schedule": "0 2 1 * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.employee_automation import analyze_all_employees; import json; print(json.dumps(analyze_all_employees(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Monthly workforce automation analysis: employee work profiles + replaceability scores (CEO-only)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/workforce_analysis.log",
     "users": ["sebastian"]},
    # F3: Monthly Tech Radar Discovery (2nd of month 5:00 CET / 4:00 UTC — after F2)
    {"job_name": "tech_radar_discovery", "schedule": "0 4 2 * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.tech_radar import discover_solutions, calculate_priority_scores, generate_roadmap, link_to_strategic_goals; discover_solutions(force=True); calculate_priority_scores(); link_to_strategic_goals(); import json; print(json.dumps(generate_roadmap(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Monthly Tech Radar: discover solutions, rank by ROI, generate roadmap (after workforce analysis)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/tech_radar.log",
     "users": ["sebastian"]},

    # === People Intelligence (daily/weekly) ===
    {"job_name": "sentiment_daily", "schedule": "0 21 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.sentiment_tracker import run_weekly_sentiment_scan; import json; print(json.dumps(run_weekly_sentiment_scan(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Daily sentiment analysis for top contacts (21:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/sentiment_daily.log",
     "users": ["sebastian"]},
    {"job_name": "delegation_analysis", "schedule": "0 7 * * 1",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.delegation_tracker import run_delegation_report; import json; print(json.dumps(run_delegation_report(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Weekly delegation effectiveness report (Monday 7:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/delegation_analysis.log",
     "users": ["sebastian"]},
    {"job_name": "network_analysis", "schedule": "0 19 * * 0",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.network_graph import run_network_analysis; import json; print(json.dumps(run_network_analysis(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Weekly communication network/silo detection (Sunday 19:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/network_analysis.log",
     "users": ["sebastian"]},
    {"job_name": "response_tracking", "schedule": "0 20 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.response_tracker import run_response_tracking; import json; print(json.dumps(run_response_tracking(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Daily response time tracking by person/channel (20:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/response_tracking.log",
     "users": ["sebastian"]},
    {"job_name": "blind_spot_scan", "schedule": "0 18 * * 3",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -m app.analysis.blind_spot_detector",
     "description": "Weekly blind spot detection (Wednesday 18:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/blind_spot_scan.log",
     "users": ["sebastian"]},

    # === Business Intelligence (daily/weekly) ===
    {"job_name": "opportunity_scan", "schedule": "0 */4 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.opportunity_detector import run_opportunity_scan; import json; print(json.dumps(run_opportunity_scan(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Opportunity scan every 4 hours", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/opportunity_scan.log",
     "users": ["sebastian"]},
    {"job_name": "org_health_daily", "schedule": "0 6 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.org_health import run_health_assessment; import json; print(json.dumps(run_health_assessment(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Daily org health score assessment (6:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/org_health_daily.log",
     "users": ["sebastian"]},
    {"job_name": "correlation_scan", "schedule": "30 22 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.correlation import run_correlation; import json; print(json.dumps(run_correlation(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Daily cross-domain pattern detection (22:30 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/correlation_scan.log",
     "users": ["sebastian"]},
    {"job_name": "strategic_goals_update", "schedule": "0 6 * * 1",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.strategic_goals import run_goal_tracking; import json; print(json.dumps(run_goal_tracking(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Weekly strategic goals progress update (Monday 6:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/strategic_goals_update.log",
     "users": ["sebastian"]},
    {"job_name": "data_flow_validation", "schedule": "0 4 * * *",
     "command": "cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.data_flow_mapper import map_data_flows; import json; print(json.dumps(map_data_flows(), ensure_ascii=False, indent=2, default=str))\"",
     "description": "Daily data flow validation (4:00 CET)", "category": "intelligence",
     "log_file": "/home/sebastian/personal-ai/logs/data_flow_validation.log",
     "users": ["sebastian"]},
]


def seed_registry() -> dict[str, Any]:
    """Populate registry from SEED_JOBS definition."""
    _ensure_tables()
    results = []
    for job in SEED_JOBS:
        r = register_job(
            job_name=job["job_name"],
            schedule=job["schedule"],
            command=job["command"],
            description=job.get("description", ""),
            category=job.get("category", "general"),
            log_file=job.get("log_file"),
            default_users=job.get("users", ["sebastian"]),
        )
        results.append(r)
        log.info("registered_cron", job_name=job["job_name"], users=job.get("users"))

    return {"registered": len(results), "jobs": [r["job_name"] for r in results]}


# ================================================================
# Summary
# ================================================================

def get_registry_summary() -> dict[str, Any]:
    """Get summary of all registered cron jobs."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cron_registry")
            total = cur.fetchall()[0][0]

            cur.execute("""
                SELECT cr.category, COUNT(*) as job_count,
                       COUNT(DISTINCT cua.username) FILTER (WHERE cua.enabled) as active_users
                FROM cron_registry cr
                LEFT JOIN cron_user_assignments cua ON cua.job_name = cr.job_name
                GROUP BY cr.category ORDER BY cr.category
            """)
            categories = [{"category": r[0], "jobs": r[1], "active_users": r[2]} for r in cur.fetchall()]

            cur.execute("""
                SELECT username, COUNT(*) FILTER (WHERE enabled) as enabled,
                       COUNT(*) FILTER (WHERE NOT enabled) as disabled
                FROM cron_user_assignments
                GROUP BY username ORDER BY username
            """)
            users = [{"user": r[0], "enabled": r[1], "disabled": r[2]} for r in cur.fetchall()]

    return {"total_jobs": total, "by_category": categories, "by_user": users}


# ================================================================
# CLI
# ================================================================

def main():
    args = sys.argv[1:]

    if not args or "--help" in args:
        print(__doc__)
        sys.exit(0)

    if "--seed" in args:
        result = seed_registry()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "--list" in args:
        username = None
        category = None
        for i, a in enumerate(args):
            if a == "--user" and i + 1 < len(args):
                username = args[i + 1]
            if a == "--category" and i + 1 < len(args):
                category = args[i + 1]
        jobs = list_jobs(username=username, category=category)
        print(json.dumps(jobs, ensure_ascii=False, indent=2, default=str))
        return

    if "--generate" in args:
        idx = args.index("--generate")
        username = args[idx + 1] if idx + 1 < len(args) else "sebastian"
        print(generate_crontab(username))
        return

    if "--enable" in args:
        idx = args.index("--enable")
        job_name = args[idx + 1] if idx + 1 < len(args) else None
        username = args[idx + 2] if idx + 2 < len(args) else "sebastian"
        if job_name:
            result = enable_job(job_name, username)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "--disable" in args:
        idx = args.index("--disable")
        job_name = args[idx + 1] if idx + 1 < len(args) else None
        username = args[idx + 2] if idx + 2 < len(args) else "sebastian"
        if job_name:
            result = disable_job(job_name, username)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if "--summary" in args:
        result = get_registry_summary()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    print("Unknown command. Use --help for usage.")


if __name__ == "__main__":
    main()
