"""
Performance Improvement Agent — orchestrates the daily loop:
  analyze → detect bottleneck → plan fix → apply → verify → commit/revert → log
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import date

import structlog

from app.analysis.perf_improver.bottleneck_detector import Bottleneck, detect
from app.analysis.perf_improver.fix_planner import FixPlan, plan_fix
from app.analysis.perf_improver.query_analyzer import AskRunsStats, fetch_24h_stats
from app.db.postgres import get_pg_connection

log = structlog.get_logger("perf_improver.agent")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

TEST_QUERIES = [
    {"query": "test latency short", "answer_length": "short"},
    {"query": "co robił Sebastian wczoraj?", "answer_length": "short"},
    {"query": "podsumuj ostatnie spotkania", "answer_length": "medium"},
]


def _log_to_journal(
    bottleneck: Bottleneck,
    fix: FixPlan | None,
    latency_before: int,
    latency_after: int | None,
    committed: bool,
    reverted: bool,
    notes: str,
) -> None:
    """Write result to perf_improvement_journal table."""
    improvement = 0.0
    if latency_after and latency_before > 0:
        improvement = round(100.0 * (latency_before - latency_after) / latency_before, 1)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO perf_improvement_journal
                    (run_date, bottleneck_type, fix_applied, param_changed,
                     old_value, new_value, latency_before_ms, latency_after_ms,
                     improvement_pct, committed, reverted, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    date.today(),
                    bottleneck.kind,
                    fix.action if fix else "none",
                    fix.param_name if fix else None,
                    fix.old_value if fix else None,
                    fix.new_value if fix else None,
                    latency_before,
                    latency_after,
                    improvement if latency_after else None,
                    committed,
                    reverted,
                    notes,
                ),
            )
            conn.commit()


def _apply_env_change(param: str, value: str) -> str | None:
    """Apply an env var change to .env file. Returns old line or None."""
    if not os.path.exists(ENV_FILE):
        log.warning("env_file_missing", path=ENV_FILE)
        return None

    with open(ENV_FILE) as f:
        lines = f.readlines()

    old_line = None
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{param}=") or stripped.startswith(f"# {param}="):
            old_line = line
            new_lines.append(f"{param}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{param}={value}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)

    log.info("env_changed", param=param, value=value)
    return old_line


def _revert_env_change(param: str, old_line: str | None) -> None:
    """Revert an env var change by restoring the original line exactly."""
    if not os.path.exists(ENV_FILE):
        log.warning("env_file_missing", path=ENV_FILE)
        return

    with open(ENV_FILE) as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{param}=") or stripped.startswith(f"# {param}="):
            if old_line is not None:
                new_lines.append(old_line)
            # old_line is None means param was newly appended — drop it on revert
        else:
            new_lines.append(line)

    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)

    log.info("env_reverted", param=param)


def _measure_latency() -> int | None:
    """Run test queries and return average latency in ms."""
    latencies = []
    for q in TEST_QUERIES:
        payload = json.dumps(q).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/ask",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            start = time.time()
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp.read()
            elapsed_ms = int((time.time() - start) * 1000)
            latencies.append(elapsed_ms)
            log.info("test_query", query=q["query"][:30], latency_ms=elapsed_ms)
        except Exception as exc:
            log.warning("test_query_failed", query=q["query"][:30], error=str(exc))

    if not latencies:
        return None
    return int(sum(latencies) / len(latencies))


def _git_commit(fix: FixPlan) -> bool:
    """Commit the .env change."""
    try:
        subprocess.run(
            ["git", "add", ".env"],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"perf: auto-optimize {fix.param_name}={fix.new_value} (perf_improver)"],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True,
        )
        log.info("git_committed", param=fix.param_name, value=fix.new_value)
        return True
    except subprocess.CalledProcessError as exc:
        log.warning("git_commit_failed", error=exc.stderr.decode() if exc.stderr else str(exc))
        return False


def run(dry_run: bool = False) -> dict:
    """Main entry point. Returns summary dict."""
    log.info("perf_improvement_start", dry_run=dry_run)

    # Step 1: Analyze
    stats: AskRunsStats = fetch_24h_stats(hours=24)
    if stats.total_runs < 3:
        msg = f"Only {stats.total_runs} queries in 24h — skipping (need >=3)"
        log.info("skipped_low_volume", total=stats.total_runs)
        _log_to_journal(
            Bottleneck("insufficient_data", "none", msg),
            None, stats.avg_latency_ms, None, False, False, msg,
        )
        return {"status": "skipped", "reason": msg}

    # Step 2: Detect bottleneck
    bottleneck: Bottleneck = detect(stats)
    log.info("bottleneck_detected", type=bottleneck.kind, severity=bottleneck.severity, detail=bottleneck.detail)

    if bottleneck.kind == "none":
        msg = f"No bottleneck detected — avg={stats.avg_latency_ms}ms, p95={stats.p95_ms}ms"
        _log_to_journal(bottleneck, None, stats.avg_latency_ms, None, False, False, msg)
        return {"status": "ok", "reason": msg}

    # Step 3: Plan fix
    fix: FixPlan | None = plan_fix(bottleneck)
    if not fix:
        msg = f"Bottleneck '{bottleneck.kind}' detected but no applicable fix"
        _log_to_journal(bottleneck, None, stats.avg_latency_ms, None, False, False, msg)
        return {"status": "no_fix", "bottleneck": bottleneck.kind, "reason": msg}

    if dry_run:
        msg = f"DRY RUN — would apply: {fix.action} ({fix.param_name}: {fix.old_value} → {fix.new_value})"
        log.info("dry_run_result", msg=msg)
        _log_to_journal(bottleneck, fix, stats.avg_latency_ms, None, False, False, f"dry_run: {msg}")
        return {
            "status": "dry_run",
            "bottleneck": bottleneck.kind,
            "fix": fix.action,
            "param": fix.param_name,
            "old": fix.old_value,
            "new": fix.new_value,
            "baseline_ms": stats.avg_latency_ms,
        }

    # Step 4: Apply fix
    log.info("applying_fix", action=fix.action)
    old_env_line: str | None = None
    if fix.change_type == "env":
        old_env_line = _apply_env_change(fix.param_name, fix.new_value)
    else:
        log.warning("unsupported_change_type", type=fix.change_type)
        _log_to_journal(bottleneck, fix, stats.avg_latency_ms, None, False, False, "unsupported change_type")
        return {"status": "error", "reason": f"Unsupported change_type: {fix.change_type}"}

    # Step 5: Verify
    log.info("verifying_fix")
    latency_after = _measure_latency()

    if latency_after is None:
        log.warning("verification_failed_no_response")
        _revert_env_change(fix.param_name, old_env_line)
        _log_to_journal(bottleneck, fix, stats.avg_latency_ms, None, False, True, "verification failed: no response")
        return {"status": "reverted", "reason": "Could not measure latency after fix"}

    improvement_pct = round(100.0 * (stats.avg_latency_ms - latency_after) / max(stats.avg_latency_ms, 1), 1)
    log.info("verification_result", before=stats.avg_latency_ms, after=latency_after, improvement_pct=improvement_pct)

    # Step 6: Commit or revert
    if improvement_pct >= 10.0:
        committed = _git_commit(fix)
        _log_to_journal(bottleneck, fix, stats.avg_latency_ms, latency_after, committed, False,
                        f"improvement {improvement_pct}% — committed={committed}")
        return {
            "status": "improved",
            "improvement_pct": improvement_pct,
            "before_ms": stats.avg_latency_ms,
            "after_ms": latency_after,
            "committed": committed,
        }
    else:
        _revert_env_change(fix.param_name, old_env_line)
        _log_to_journal(bottleneck, fix, stats.avg_latency_ms, latency_after, False, True,
                        f"improvement only {improvement_pct}% (<10%) — reverted")
        return {
            "status": "reverted",
            "improvement_pct": improvement_pct,
            "before_ms": stats.avg_latency_ms,
            "after_ms": latency_after,
            "reason": f"Improvement {improvement_pct}% below 10% threshold",
        }


def main():
    parser = argparse.ArgumentParser(description="Performance Improvement Loop Agent")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and plan but don't apply changes")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run)
    log.info("perf_improvement_done", **result)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
