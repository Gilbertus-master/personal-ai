"""
Cron Health Checker — skanuje logi pod kątem ERROR/FAILED i sprawdza freshness.

Tier 2 alert via AlertManager jeśli problemy wykryte.
"""
from __future__ import annotations

import time
from pathlib import Path

import structlog

from app.guardian.alert_manager import AlertManager

log = structlog.get_logger("cron_health_checker")

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_DIR / "logs"

# Key log files and their max allowed age in seconds
CRITICAL_LOGS = {
    "extraction_entities.log": 3600,      # 1h — entities extraction
    "extraction_events.log": 3600,        # 1h — events extraction
    "ingestion.log": 600,                 # 10min — ingestion sync
    "daily_brief.log": 86400,             # 24h — daily brief
    "qc_daily.log": 86400,                # 24h — quality checks
    "backup.log": 14400 + 1800,           # 4h + 30min buffer — backup
}

# Patterns indicating errors in logs
ERROR_PATTERNS = ["ERROR", "FAILED", "CRITICAL", "Traceback", "Exception"]


_alert_mgr: AlertManager | None = None


def _get_alert_mgr() -> AlertManager:
    global _alert_mgr
    if _alert_mgr is None:
        _alert_mgr = AlertManager()
    return _alert_mgr


def check_cron_health() -> dict:
    """Scan logs/*.log for ERROR/FAILED patterns.

    Returns: {healthy: bool, errors_found: int, details: [...]}
    """
    if not LOGS_DIR.exists():
        log.warning("logs_dir_missing", path=str(LOGS_DIR))
        return {"healthy": True, "errors_found": 0, "details": [], "note": "logs dir not found"}

    errors_found = 0
    details = []

    log_files = [LOGS_DIR / log_name for log_name in CRITICAL_LOGS]
    for log_file in log_files:
        if not log_file.exists():
            continue
        try:
            # Only check last 100 lines
            content = log_file.read_text(errors="replace")
            lines = content.strip().split("\n")
            recent_lines = lines[-100:] if len(lines) > 100 else lines

            file_errors = []
            for i, line in enumerate(recent_lines):
                for pattern in ERROR_PATTERNS:
                    if pattern in line:
                        file_errors.append({
                            "line_num": len(lines) - len(recent_lines) + i + 1,
                            "pattern": pattern,
                            "text": line[:200],
                        })
                        break

            if file_errors:
                errors_found += len(file_errors)
                details.append({
                    "file": log_file.name,
                    "error_count": len(file_errors),
                    "recent_errors": file_errors[-3:],  # last 3
                })
        except Exception as e:
            log.error("log_file_read_error", file=log_file.name, error=str(e))

    healthy = errors_found == 0

    if not healthy:
        error_summary = "; ".join(
            f"{d['file']}:{d['error_count']} errors" for d in details[:5]
        )
        _get_alert_mgr().send(
            tier=2,
            category="cron_health",
            title="Cron log errors detected",
            message=f"Found {errors_found} errors in logs: {error_summary}",
        )

    log.info("cron_health_check_done", healthy=healthy, errors_found=errors_found)

    return {
        "healthy": healthy,
        "errors_found": errors_found,
        "details": details,
    }


def check_cron_freshness() -> dict:
    """Check timestamps of key log files — alert if stale.

    Returns: {healthy: bool, stale_count: int, details: [...]}
    """
    if not LOGS_DIR.exists():
        return {"healthy": True, "stale_count": 0, "details": [], "note": "logs dir not found"}

    now = time.time()
    stale_count = 0
    details = []

    for log_name, max_age_seconds in CRITICAL_LOGS.items():
        log_path = LOGS_DIR / log_name
        if not log_path.exists():
            details.append({
                "file": log_name,
                "status": "missing",
                "max_age_seconds": max_age_seconds,
            })
            stale_count += 1
            continue

        mtime = log_path.stat().st_mtime
        age_seconds = now - mtime
        is_stale = age_seconds > max_age_seconds

        if is_stale:
            stale_count += 1
            details.append({
                "file": log_name,
                "status": "stale",
                "age_seconds": int(age_seconds),
                "max_age_seconds": max_age_seconds,
                "age_human": f"{int(age_seconds / 3600)}h {int((age_seconds % 3600) / 60)}m",
            })

    healthy = stale_count == 0

    if not healthy:
        stale_summary = "; ".join(
            f"{d['file']}({d.get('age_human', 'missing')})" for d in details[:5]
        )
        _get_alert_mgr().send(
            tier=2,
            category="cron_freshness",
            title="Stale cron logs detected",
            message=f"{stale_count} stale log(s): {stale_summary}",
        )

    log.info("cron_freshness_check_done", healthy=healthy, stale_count=stale_count)

    return {
        "healthy": healthy,
        "stale_count": stale_count,
        "details": details,
    }


if __name__ == "__main__":
    import json
    print("=== Cron Health Check ===")
    result = check_cron_health()
    print(json.dumps(result, indent=2, default=str))

    print("\n=== Cron Freshness Check ===")
    result = check_cron_freshness()
    print(json.dumps(result, indent=2, default=str))
