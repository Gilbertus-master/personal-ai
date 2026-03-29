"""
Extraction Watchdog — stall detection + auto-restart for extraction pipeline.

Runs every 30 minutes via cron. Monitors:
1. Entity extraction backlog (chunks without entities or checked marker)
2. Event extraction backlog (chunks without events or checked marker)
3. Embedding backlog (chunks without embedding_id)
4. Worker process count and health
5. Backlog trend (growing = problem)

Actions:
- WARNING: log + alert
- CRITICAL: auto-restart workers (with flock protection)
- STALL (4h no progress despite workers): restart with smaller batch, then alert

Cron (UTC, = co 30 min):
  */30 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.extraction_watchdog >> logs/extraction_watchdog.log 2>&1
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger("extraction_watchdog")

from app.db.postgres import get_pg_connection

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_DIR / "logs"
STATE_FILE = PROJECT_DIR / ".extraction_watchdog_state.json"
LOCKFILE = Path("/tmp/extraction_watchdog_restart.lock")

MAX_TOTAL_WORKERS = 24  # 12 entity + 12 event
STALL_WINDOW_HOURS = 4  # hours without progress = stall
DEFAULT_BATCH = 3000
REDUCED_BATCH = 1000
DEFAULT_WORKERS = 12
ZOMBIE_AGE_MINUTES = 60

THRESHOLDS = {
    "embedding_backlog": {"warning": 200, "critical": 1000},
    "entity_backlog": {"warning": 500, "critical": 2000},
    "event_backlog": {"warning": 500, "critical": 2000},
}

# ---------------------------------------------------------------------------
# State persistence (for trend detection)
# ---------------------------------------------------------------------------


def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ---------------------------------------------------------------------------
# Backlog queries
# ---------------------------------------------------------------------------


def get_backlogs() -> dict[str, int]:
    """Query current extraction backlogs from DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Entity backlog (matches turbo_extract.sh query)
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
                LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
                WHERE ce.id IS NULL AND cec.chunk_id IS NULL
            """)
            entity_backlog = cur.fetchone()[0]

            # Event backlog
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN events e ON e.chunk_id = c.id
                LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                WHERE e.id IS NULL AND cec.chunk_id IS NULL
            """)
            event_backlog = cur.fetchone()[0]

            # Embedding backlog
            cur.execute("""
                SELECT COUNT(*) FROM chunks
                WHERE (embedding_id IS NULL OR embedding_id = '')
                AND COALESCE(embedding_status, 'pending') = 'pending'
            """)
            embedding_backlog = cur.fetchone()[0]

    return {
        "entity_backlog": entity_backlog,
        "event_backlog": event_backlog,
        "embedding_backlog": embedding_backlog,
    }


# ---------------------------------------------------------------------------
# Worker process management
# ---------------------------------------------------------------------------


def get_extraction_workers() -> list[dict[str, Any]]:
    """Find running extraction worker processes."""
    workers = []
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if re.search(r"app\.extraction\.(entities|events)", line) and "grep" not in line:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    pid = int(parts[1])
                    # Get process start time for age calculation
                    try:
                        stat = Path(f"/proc/{pid}").stat()
                        age_seconds = time.time() - stat.st_mtime
                    except (OSError, ValueError):
                        age_seconds = 0
                    workers.append({
                        "pid": pid,
                        "type": "entity" if "entities" in line else "event",
                        "age_seconds": age_seconds,
                        "cmd": parts[10] if len(parts) > 10 else "",
                    })
    except (subprocess.TimeoutExpired, OSError) as e:
        log.error("ps_failed", error=str(e))
    return workers


def get_embedding_workers() -> list[int]:
    """Find running embedding worker PIDs."""
    pids = []
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "index_chunks" in line and "grep" not in line and "python" in line:
                parts = line.split(None, 10)
                if len(parts) >= 2:
                    pids.append(int(parts[1]))
    except (subprocess.TimeoutExpired, OSError):
        pass
    return pids


def kill_zombie_workers(workers: list[dict[str, Any]]) -> int:
    """Kill extraction workers older than ZOMBIE_AGE_MINUTES. Returns count killed."""
    killed = 0
    for w in workers:
        if w["age_seconds"] > ZOMBIE_AGE_MINUTES * 60:
            log.warning("killing_zombie_worker", pid=w["pid"], type=w["type"],
                        age_minutes=round(w["age_seconds"] / 60, 1))
            try:
                os.kill(w["pid"], signal.SIGTERM)
                time.sleep(2)
                # Force kill if still alive
                try:
                    os.kill(w["pid"], 0)  # check if alive
                    os.kill(w["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
                killed += 1
            except (ProcessLookupError, PermissionError) as e:
                log.warning("kill_failed", pid=w["pid"], error=str(e))
    return killed


# ---------------------------------------------------------------------------
# Auto-restart (with flock protection)
# ---------------------------------------------------------------------------


def _acquire_restart_lock() -> int | None:
    """Try to acquire restart lock. Returns fd or None."""
    try:
        import fcntl
        fd = os.open(str(LOCKFILE), os.O_WRONLY | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (OSError, BlockingIOError):
        log.info("restart_lock_held", msg="Another restart in progress, skipping")
        return None


def _release_restart_lock(fd: int) -> None:
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass


def restart_extraction(batch: int = DEFAULT_BATCH, workers: int = DEFAULT_WORKERS) -> bool:
    """Restart turbo_extract.sh if no extraction workers are running. Returns True if started."""
    existing = get_extraction_workers()
    if existing:
        log.info("skip_restart_workers_exist", count=len(existing))
        return False

    fd = _acquire_restart_lock()
    if fd is None:
        return False

    try:
        cmd = f"cd {PROJECT_DIR} && nohup bash scripts/turbo_extract.sh {batch} {workers} claude-haiku-4-5-20251001"
        log.info("restarting_extraction", batch=batch, workers=workers)
        subprocess.Popen(
            cmd, shell=True,
            stdout=open(LOGS_DIR / "extraction_watchdog_restart.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return True
    except OSError as e:
        log.error("restart_failed", error=str(e))
        return False
    finally:
        _release_restart_lock(fd)


def restart_embeddings() -> bool:
    """Restart embedding indexer if not already running."""
    if get_embedding_workers():
        log.info("skip_restart_embeddings_running")
        return False

    fd = _acquire_restart_lock()
    if fd is None:
        return False

    try:
        cmd = f"cd {PROJECT_DIR} && nohup .venv/bin/python3 -m app.retrieval.index_chunks --batch-size 50"
        log.info("restarting_embeddings")
        subprocess.Popen(
            cmd, shell=True,
            stdout=open(LOGS_DIR / "embedding_restart.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return True
    except OSError as e:
        log.error("embedding_restart_failed", error=str(e))
        return False
    finally:
        _release_restart_lock(fd)


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------


def send_alert(message: str) -> None:
    """Save alert to DB and log it."""
    log.warning("extraction_alert", message=message)
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO alerts (source, severity, message, created_at)
                    VALUES (%s, %s, %s, %s)
                """, ("extraction_watchdog", "critical", message, datetime.now(timezone.utc)))
            conn.commit()
    except Exception as e:
        log.error("alert_save_failed", error=str(e))


# ---------------------------------------------------------------------------
# Stall detection
# ---------------------------------------------------------------------------


def detect_stall(backlogs: dict[str, int], state: dict[str, Any]) -> dict[str, Any]:
    """Check if backlogs are stalled (not decreasing over STALL_WINDOW_HOURS)."""
    now = datetime.now(timezone.utc).isoformat()
    history = state.get("backlog_history", [])

    # Add current reading
    history.append({"ts": now, **backlogs})

    # Keep only last 24h of readings (48 readings at 30-min intervals)
    if len(history) > 48:
        history = history[-48:]

    state["backlog_history"] = history

    result = {"stalled": False, "growing": False, "details": {}}

    if len(history) < 2:
        return result

    # Check if backlog is growing (compare with previous reading)
    prev = history[-2]
    for key in ["entity_backlog", "event_backlog", "embedding_backlog"]:
        curr_val = backlogs.get(key, 0)
        prev_val = prev.get(key, 0)
        if curr_val > prev_val and curr_val > 0:
            result["growing"] = True
            result["details"][key] = {"direction": "growing", "delta": curr_val - prev_val}

    # Check for stall: backlog not decreasing over STALL_WINDOW_HOURS
    stall_readings = STALL_WINDOW_HOURS * 2  # readings needed (every 30 min)
    if len(history) >= stall_readings:
        window = history[-stall_readings:]
        for key in ["entity_backlog", "event_backlog"]:
            values = [r.get(key, 0) for r in window]
            # Stall = backlog > 0 and hasn't decreased by more than 5%
            if all(v > 100 for v in values):
                first, last = values[0], values[-1]
                if last >= first * 0.95:
                    result["stalled"] = True
                    result["details"][key] = {
                        "direction": "stalled",
                        "hours": STALL_WINDOW_HOURS,
                        "backlog": last,
                    }

    return result


# ---------------------------------------------------------------------------
# Main watchdog loop
# ---------------------------------------------------------------------------


def run_watchdog() -> dict[str, Any]:
    """Run one watchdog check cycle. Returns status report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info("watchdog_start", ts=now_str)

    # 1. Get current backlogs
    backlogs = get_backlogs()
    log.info("backlogs", **backlogs)

    # 2. Get worker status
    extraction_workers = get_extraction_workers()
    embedding_workers = get_embedding_workers()
    entity_workers = [w for w in extraction_workers if w["type"] == "entity"]
    event_workers = [w for w in extraction_workers if w["type"] == "event"]

    log.info("workers",
             entity_workers=len(entity_workers),
             event_workers=len(event_workers),
             embedding_workers=len(embedding_workers))

    # 3. Load state and check trends
    state = load_state()
    stall_info = detect_stall(backlogs, state)

    actions_taken = []

    # 4. Kill zombies
    zombies_killed = kill_zombie_workers(extraction_workers)
    if zombies_killed:
        actions_taken.append(f"killed {zombies_killed} zombie workers")

    # 5. Check thresholds and act
    for key, thresholds in THRESHOLDS.items():
        val = backlogs.get(key, 0)
        if val >= thresholds["critical"]:
            log.warning("critical_backlog", metric=key, value=val, threshold=thresholds["critical"])
            if key == "embedding_backlog":
                if restart_embeddings():
                    actions_taken.append(f"restarted embeddings (backlog={val})")
            else:
                if restart_extraction():
                    actions_taken.append(f"restarted extraction (backlog={val})")
        elif val >= thresholds["warning"]:
            log.warning("warning_backlog", metric=key, value=val, threshold=thresholds["warning"])

    # 6. Zero workers with backlog → start workers
    total_backlog = backlogs["entity_backlog"] + backlogs["event_backlog"]
    if total_backlog > 100 and not extraction_workers:
        log.warning("zero_workers_with_backlog", backlog=total_backlog)
        if restart_extraction():
            actions_taken.append(f"started workers (zero workers, backlog={total_backlog})")

    if backlogs["embedding_backlog"] > 50 and not embedding_workers:
        if restart_embeddings():
            actions_taken.append(f"started embeddings (backlog={backlogs['embedding_backlog']})")

    # 7. Backlog growing alert
    if stall_info["growing"]:
        details = stall_info["details"]
        log.warning("backlog_growing", details=details)

    # 8. Stall detection → escalate
    if stall_info["stalled"]:
        stall_details = {k: v for k, v in stall_info["details"].items() if v.get("direction") == "stalled"}
        log.error("extraction_stalled", details=stall_details)

        # First try: restart with reduced batch
        prev_stall_action = state.get("last_stall_action")
        if prev_stall_action:
            # Already tried reduced batch — alert human
            msg = (
                f"Extraction stalled for {STALL_WINDOW_HOURS}h despite restart. "
                f"Backlogs: entity={backlogs['entity_backlog']}, "
                f"event={backlogs['event_backlog']}. "
                f"Check: Anthropic API limits, circuit breaker, extraction logs."
            )
            send_alert(msg)
            actions_taken.append("ALERT: persistent stall")
        else:
            # Try restart with smaller batch
            kill_zombie_workers(extraction_workers)
            time.sleep(3)
            if restart_extraction(batch=REDUCED_BATCH, workers=DEFAULT_WORKERS):
                state["last_stall_action"] = now_str
                actions_taken.append(f"stall detected — restarted with reduced batch ({REDUCED_BATCH})")
    else:
        # Clear stall state if backlog is progressing
        state.pop("last_stall_action", None)

    # 9. Save state
    state["last_check"] = now_str
    state["last_backlogs"] = backlogs
    state["last_workers"] = {
        "entity": len(entity_workers),
        "event": len(event_workers),
        "embedding": len(embedding_workers),
    }
    save_state(state)

    report = {
        "ts": now_str,
        "backlogs": backlogs,
        "workers": {
            "entity": len(entity_workers),
            "event": len(event_workers),
            "embedding": len(embedding_workers),
        },
        "stall": stall_info["stalled"],
        "growing": stall_info["growing"],
        "actions": actions_taken,
    }

    if actions_taken:
        log.info("watchdog_actions", actions=actions_taken)
    else:
        log.info("watchdog_ok", status="healthy")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report = run_watchdog()
    print(json.dumps(report, indent=2, default=str))
