"""
Health Monitor — non-regression automation + self-healing.

Checks: cron execution, extraction coverage, API costs, DB baseline,
service health. Alerts via WhatsApp on failures.

Cron: 0 6,12,18 * * * (3x/day: 7:00, 13:00, 19:00 CET)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection

# Baseline — update after each major deploy
BASELINE = {
    "min_mcp_tools": 40,
    "min_tables": 76,
    "min_cron_jobs": 31,
    "min_chunks": 90000,
    "min_events": 90000,
    "min_entities": 35000,
    "max_api_cost_daily_usd": 20.0,
    "min_extraction_coverage_pct": 95.0,
}


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS health_checks (
                    id BIGSERIAL PRIMARY KEY,
                    check_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    status TEXT NOT NULL CHECK (status IN ('healthy', 'degraded', 'critical')),
                    checks JSONB NOT NULL,
                    alerts_sent INTEGER DEFAULT 0,
                    summary TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_health_checks_time
                    ON health_checks(check_time DESC);
            """)
            conn.commit()


def _send_alert(message: str) -> bool:
    """Send critical alert via WhatsApp."""
    try:
        path = os.path.expanduser("~/.npm-global/bin") + ":" + os.environ.get("PATH", "")
        result = subprocess.run(
            ["openclaw", "message", "send", "--channel", "whatsapp",
             "--target", "+48505441635", "--message", message],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PATH": path},
        )
        return result.returncode == 0
    except Exception:
        return False


def check_db_counts() -> dict[str, Any]:
    """Check core table counts against baseline."""
    issues = []
    counts = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for table, min_count in [
                ("chunks", BASELINE["min_chunks"]),
                ("events", BASELINE["min_events"]),
                ("entities", BASELINE["min_entities"]),
            ]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # safe: table from hardcoded list above
                count = cur.fetchone()[0]
                counts[table] = count
                if count < min_count:
                    issues.append(f"{table}: {count} < baseline {min_count}")

            # Table count
            cur.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
            table_count = cur.fetchone()[0]
            counts["tables"] = table_count
            if table_count < BASELINE["min_tables"]:
                issues.append(f"tables: {table_count} < baseline {BASELINE['min_tables']}")

    return {"status": "ok" if not issues else "degraded", "counts": counts, "issues": issues}


def check_extraction_coverage() -> dict[str, Any]:
    """Check extraction coverage percentage."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks")
            total = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN events e ON e.chunk_id = c.id
                LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                WHERE e.id IS NULL AND cec.chunk_id IS NULL
            """)
            remaining = cur.fetchone()[0]

    coverage = round(100.0 * (1 - remaining / max(total, 1)), 1) if total > 0 else 0
    ok = coverage >= BASELINE["min_extraction_coverage_pct"]
    return {
        "status": "ok" if ok else "degraded",
        "coverage_pct": coverage,
        "remaining": remaining,
        "total": total,
    }


def check_api_costs() -> dict[str, Any]:
    """Check today's API costs."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(cost_usd), 0)
                FROM api_costs WHERE created_at >= CURRENT_DATE
            """)
            today_cost = float(cur.fetchone()[0])

    ok = today_cost <= BASELINE["max_api_cost_daily_usd"]
    return {
        "status": "ok" if ok else "warning",
        "today_usd": round(today_cost, 4),
        "limit_usd": BASELINE["max_api_cost_daily_usd"],
    }


def check_cron_health() -> dict[str, Any]:
    """Check cron health by looking at data freshness (proxy for cron execution)."""
    issues = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check data freshness as proxy for cron health
            freshness_checks = {
                "ingestion": ("SELECT MAX(imported_at) FROM sources", 120),  # 2h
                "extraction": ("SELECT MAX(created_at) FROM events", 120),
                "insights": ("SELECT MAX(created_at) FROM insights", 1500),  # 25h
            }
            for name, (query, max_minutes) in freshness_checks.items():
                try:
                    cur.execute(query)
                    last = cur.fetchone()[0]
                    if last:
                        age_min = (datetime.now(tz=timezone.utc) - last).total_seconds() / 60
                        if age_min > max_minutes:
                            issues.append(f"{name}: data {int(age_min)} min stale (limit: {max_minutes})")
                except Exception:
                    pass

            # Count registered jobs
            cur.execute("SELECT COUNT(*) FROM cron_registry")
            job_count = cur.fetchone()[0]
            if job_count < BASELINE["min_cron_jobs"]:
                issues.append(f"cron_jobs: {job_count} < baseline {BASELINE['min_cron_jobs']}")

    return {"status": "ok" if not issues else "degraded", "issues": issues, "job_count": job_count}


def check_services() -> dict[str, Any]:
    """Check if critical services are responding."""
    import requests as req
    services = {}

    for name, url in [
        ("api", "http://127.0.0.1:8000/health"),
        ("qdrant", "http://127.0.0.1:6333/healthz"),
        ("whisper", "http://127.0.0.1:9090/health"),
    ]:
        try:
            resp = req.get(url, timeout=5)
            services[name] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
        except Exception:
            services[name] = "down"

    issues = [f"{k}: {v}" for k, v in services.items() if v != "ok"]
    return {"status": "ok" if not issues else "critical", "services": services, "issues": issues}


def run_health_check(send_alerts: bool = True) -> dict[str, Any]:
    """Full health check — run all checks, store results, alert on issues."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    checks = {
        "db_counts": check_db_counts(),
        "extraction": check_extraction_coverage(),
        "api_costs": check_api_costs(),
        "crons": check_cron_health(),
        "services": check_services(),
    }

    # Determine overall status
    statuses = [c["status"] for c in checks.values()]
    if "critical" in statuses:
        overall = "critical"
    elif "degraded" in statuses or "warning" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    # Collect all issues
    all_issues = []
    for name, check in checks.items():
        for issue in check.get("issues", []):
            all_issues.append(f"[{name}] {issue}")

    summary = f"Status: {overall}. {len(all_issues)} issues." if all_issues else "All systems healthy."

    # Store
    alerts_sent = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO health_checks (status, checks, summary)
                   VALUES (%s, %s, %s)""",
                (overall, json.dumps(checks, default=str), summary),
            )
            conn.commit()

    # Alert on critical/degraded
    if send_alerts and overall != "healthy" and all_issues:
        emoji = "🚨" if overall == "critical" else "⚠️"
        msg = f"{emoji} *Gilbertus Health: {overall.upper()}*\n\n"
        for issue in all_issues[:5]:
            msg += f"• {issue}\n"
        if _send_alert(msg):
            alerts_sent = 1

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("health_check", status=overall, issues=len(all_issues), latency_ms=latency_ms)

    return {
        "status": overall,
        "checks": checks,
        "issues": all_issues,
        "alerts_sent": alerts_sent,
        "latency_ms": latency_ms,
    }


def get_health_trend(days: int = 7) -> list[dict[str, Any]]:
    """Get health check trend over past N days."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT check_time, status, summary, alerts_sent
                FROM health_checks
                WHERE check_time > NOW() - INTERVAL '%s days'
                ORDER BY check_time DESC LIMIT 50
            """, (days,))
            return [
                {"time": str(r[0]), "status": r[1], "summary": r[2], "alerts": r[3]}
                for r in cur.fetchall()
            ]
