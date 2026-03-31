"""Centralny moduł non-regression dla Gilbertus + Omnius.

ZASADA ZERO: Nowe developmenty NIE MOGĄ pogorszyć dotychczasowych osiągnięć.

4 gate'y:
1. Pre-commit  — blokuje commit jeśli baseline spadnie
2. Pre-deploy  — blokuje deploy jeśli baseline spadnie
3. Post-deploy — auto-rollback jeśli health/baseline fail
4. Continuous  — cron co 10 min alertuje natychmiast

Usage:
    # Check baseline
    python3 scripts/non_regression_gate.py check

    # Save snapshot (before deploy)
    python3 scripts/non_regression_gate.py snapshot pre_deploy

    # Compare (after deploy)
    python3 scripts/non_regression_gate.py compare pre_deploy

    # Import as module
    from scripts.non_regression_gate import check_gilbertus_baseline
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BASELINE_FILE = PROJECT_DIR / "logs" / ".qc_baseline.json"
SNAPSHOT_DIR = PROJECT_DIR / "logs" / "snapshots"


def _run(cmd: str, timeout: int = 15) -> str:
    """Run shell command, return stdout. Empty string on failure."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception:
        return ""


def _pg(query: str) -> str:
    """Run PostgreSQL query against Gilbertus DB."""
    return _run(f'docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc "{query}"')


def get_current_metrics() -> dict:
    """Collect current system metrics."""
    metrics = {}

    # MCP tools (count Tool() definitions in server.py)
    mcp_file = PROJECT_DIR / "mcp_gilbertus" / "server.py"
    if mcp_file.exists():
        content = mcp_file.read_text()
        metrics["mcp"] = content.count("Tool(name=")

    # Cron jobs
    cron_output = _run("crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | wc -l")
    metrics["cron"] = int(cron_output) if cron_output.isdigit() else 0

    # DB tables
    tables = _pg("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    metrics["tables"] = int(tables) if tables.isdigit() else 0

    # Lessons learned
    lessons = _pg("SELECT COUNT(*) FROM lessons_learned")
    metrics["lessons"] = int(lessons) if lessons.isdigit() else 0

    # Data counts
    for table in ["chunks", "events", "entities", "documents", "insights", "people"]:
        count = _pg(f"SELECT COUNT(*) FROM {table}")
        metrics[table] = int(count) if count.isdigit() else 0

    # Extraction coverage percentage
    coverage_remaining = _pg(
        "SELECT COUNT(*) FROM chunks c "
        "LEFT JOIN events e ON e.chunk_id=c.id "
        "LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id "
        "WHERE e.id IS NULL AND cec.chunk_id IS NULL"
    )
    total_chunks = _pg("SELECT COUNT(*) FROM chunks")
    if total_chunks.isdigit() and int(total_chunks) > 0 and coverage_remaining.isdigit():
        covered = int(total_chunks) - int(coverage_remaining)
        metrics["extraction_coverage_pct"] = round((covered / int(total_chunks)) * 100, 2)
    else:
        metrics["extraction_coverage_pct"] = 0.0

    # App modules
    app_dir = PROJECT_DIR / "app"
    if app_dir.exists():
        metrics["app_modules"] = sum(1 for _ in app_dir.rglob("*.py"))

    # Scripts
    scripts_dir = PROJECT_DIR / "scripts"
    if scripts_dir.exists():
        metrics["scripts"] = sum(1 for _ in scripts_dir.glob("*.sh")) + sum(1 for _ in scripts_dir.glob("*.py"))

    # Services health
    api_health = _run("curl -sf --max-time 5 http://localhost:8000/health 2>/dev/null")
    metrics["api_healthy"] = 1 if "ok" in api_health.lower() else 0

    qdrant_health = _run("curl -sf --max-time 5 http://localhost:6333/healthz 2>/dev/null")
    metrics["qdrant_healthy"] = 1 if qdrant_health else 0

    from app.config.timezone import now as tz_now
    metrics["timestamp"] = tz_now().strftime("%Y-%m-%d %H:%M:%S CET")

    return metrics


def load_baseline() -> dict:
    """Load baseline from .qc_baseline.json."""
    if not BASELINE_FILE.exists():
        return {}
    try:
        return json.loads(BASELINE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def check_gilbertus_baseline() -> dict:
    """Check current metrics against baseline. Returns {passed, violations, metrics}."""
    baseline = load_baseline()
    if not baseline:
        return {"passed": True, "violations": [], "reason": "No baseline found — first run"}

    current = get_current_metrics()
    violations = []

    # Count-based metrics — must not decrease
    count_metrics = ["mcp", "cron", "tables", "lessons", "chunks", "events",
                     "entities", "app_modules", "scripts"]

    for metric in count_metrics:
        base_val = baseline.get(metric, 0)
        curr_val = current.get(metric, 0)
        if isinstance(base_val, (int, float)) and isinstance(curr_val, (int, float)):
            if curr_val < base_val:
                violations.append(
                    f"{metric}: {curr_val} < baseline {base_val} (dropped by {base_val - curr_val})"
                )

    # Extraction coverage — must not drop more than 5%
    base_coverage = baseline.get("extraction_coverage_pct", 0)
    curr_coverage = current.get("extraction_coverage_pct", 0)
    if isinstance(base_coverage, (int, float)) and isinstance(curr_coverage, (int, float)):
        if base_coverage > 0 and (base_coverage - curr_coverage) > 5.0:
            violations.append(
                f"extraction_coverage_pct: {curr_coverage}% < baseline {base_coverage}% "
                f"(dropped by {round(base_coverage - curr_coverage, 2)}%)"
            )

    # Health metrics — must be healthy
    if current.get("api_healthy") == 0 and baseline.get("api_healthy") == 1:
        violations.append("API health: was healthy, now unhealthy")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "metrics": current,
        "baseline": baseline,
    }


def save_snapshot(name: str) -> dict:
    """Save current metrics as named snapshot (e.g. pre_deploy)."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = get_current_metrics()
    snapshot_file = SNAPSHOT_DIR / f"{name}.json"
    snapshot_file.write_text(json.dumps(metrics, indent=2))
    return metrics


def load_snapshot(name: str) -> dict:
    """Load a named snapshot."""
    snapshot_file = SNAPSHOT_DIR / f"{name}.json"
    if not snapshot_file.exists():
        return {}
    try:
        return json.loads(snapshot_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def compare_snapshots(before_name: str, after: dict | None = None) -> dict:
    """Compare a saved snapshot against current state (or another snapshot)."""
    before = load_snapshot(before_name)
    if not before:
        return {"passed": True, "violations": [], "reason": f"No snapshot '{before_name}' found"}

    if after is None:
        after = get_current_metrics()

    violations = []
    count_metrics = ["mcp", "cron", "tables", "lessons", "chunks", "events",
                     "entities", "app_modules", "scripts"]

    for metric in count_metrics:
        before_val = before.get(metric, 0)
        after_val = after.get(metric, 0)
        if isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
            if after_val < before_val:
                violations.append(
                    f"{metric}: {after_val} < pre-deploy {before_val} (regression)"
                )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "before": before,
        "after": after,
    }


def update_baseline():
    """Update baseline with current metrics (called after successful QC)."""
    metrics = get_current_metrics()
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(metrics, indent=2))
    return metrics


def check_omnius_baseline(tenant: str) -> dict:
    """Check Omnius tenant baseline via API."""
    url = os.getenv(f"OMNIUS_{tenant.upper()}_URL", "")
    api_key = os.getenv(f"OMNIUS_{tenant.upper()}_ADMIN_KEY", "")

    if not url:
        return {"passed": True, "reason": f"No Omnius {tenant} configured"}

    status_output = _run(
        f'curl -sf --max-time 10 -H "X-API-Key: {api_key}" {url}/api/v1/status'
    )
    if not status_output:
        return {"passed": False, "violations": [f"Omnius {tenant} unreachable"]}

    try:
        status = json.loads(status_output)
        return {"passed": True, "metrics": status}
    except json.JSONDecodeError:
        return {"passed": False, "violations": [f"Omnius {tenant} returned invalid JSON"]}


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 non_regression_gate.py [check|snapshot|compare|update|metrics]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        result = check_gilbertus_baseline()
        if result["passed"]:
            print(f"✅ Non-regression OK ({len(result.get('metrics', {}))} metrics checked)")
        else:
            print("❌ NON-REGRESSION FAILED:")
            for v in result["violations"]:
                print(f"  - {v}")
            sys.exit(1)

    elif cmd == "snapshot":
        name = sys.argv[2] if len(sys.argv) > 2 else "manual"
        metrics = save_snapshot(name)
        print(f"Snapshot '{name}' saved ({len(metrics)} metrics)")

    elif cmd == "compare":
        name = sys.argv[2] if len(sys.argv) > 2 else "pre_deploy"
        result = compare_snapshots(name)
        if result["passed"]:
            print(f"✅ No regression vs '{name}' snapshot")
        else:
            print(f"❌ REGRESSION vs '{name}':")
            for v in result["violations"]:
                print(f"  - {v}")
            sys.exit(1)

    elif cmd == "update":
        metrics = update_baseline()
        print(f"Baseline updated ({len(metrics)} metrics)")

    elif cmd == "metrics":
        metrics = get_current_metrics()
        print(json.dumps(metrics, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
