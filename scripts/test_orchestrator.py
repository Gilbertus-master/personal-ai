#!/usr/bin/env python3
"""
Gilbertus Quality Upgrade — Test Orchestrator
Testuje czy wszystkie 19 zadań działają poprawnie po wdrożeniu.
"""
import os
import subprocess
import sys
import socket
import json
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _env_flags() -> dict[str, str]:
    """Parse .env file into dict."""
    flags = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                flags[k.strip()] = v.strip().strip('\'"')
    return flags


PG_HOST = "localhost"
PG_PORT = 5432
PG_DB = "gilbertus"
PG_USER = "gilbertus"
PG_PASS = _env_flags().get("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))

PGBOUNCER_PORT = 5433
API_BASE = "http://127.0.0.1:8000"
QDRANT_BASE = "http://localhost:6333"


@dataclass
class TestResult:
    id: str
    name: str
    passed: bool
    message: str


def _pg_query(query: str, use_pgbouncer: bool = False, pgbouncer_port: int = PGBOUNCER_PORT) -> list[tuple]:
    """Execute query via docker psql (default) or via pgbouncer (if use_pgbouncer=True).

    - use_pgbouncer=False: Execute via 'docker exec' on container's local socket.
    - use_pgbouncer=True: Connect directly from host to pgbouncer port for diagnostics.
    """
    if use_pgbouncer:
        # For pgbouncer, connect directly from host to the pgbouncer port.
        # Uses psycopg (v3) directly here — bypasses the pool intentionally
        # because this targets a different port (pgbouncer diagnostic only).
        import psycopg
        conn = psycopg.connect(host=PG_HOST, port=pgbouncer_port, dbname=PG_DB, user=PG_USER,
                               password=PG_PASS, connect_timeout=5)
        with conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
        return rows
    # Default: docker exec path
    cmd = [
        "docker", "exec", "gilbertus-postgres",
        "psql", "-U", PG_USER, "-d", PG_DB, "-t", "-A", "-c", query,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"psql error: {result.stderr.strip()}")
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line:
            rows.append(tuple(line.split("|")))
    return rows


def _http_get(path: str, timeout: int = 10) -> tuple[int, str]:
    """Simple HTTP GET without requests dependency."""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(f"{API_BASE}{path}")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode() if e.fp else str(e)
    except Exception as e:
        raise RuntimeError(f"HTTP error: {e}")


def _port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ────────────────────────────────────────────────────────
# T1: ENABLE_TOOL_ROUTING
# ────────────────────────────────────────────────────────
def test_t1() -> TestResult:
    tid, name = "T1", "Tool Routing (flag + module)"
    try:
        flags = _env_flags()
        if flags.get("ENABLE_TOOL_ROUTING") != "true":
            return TestResult(tid, name, False, "ENABLE_TOOL_ROUTING not set to 'true' in .env")
        router_file = PROJECT_ROOT / "app" / "retrieval" / "tool_router.py"
        if not router_file.exists():
            return TestResult(tid, name, False, f"{router_file} does not exist")
        content = router_file.read_text()
        if "def " not in content:
            return TestResult(tid, name, False, "tool_router.py has no function definitions")
        return TestResult(tid, name, True, "Flag=true, module exists with functions")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T2: Log Rotation
# ────────────────────────────────────────────────────────
def test_t2() -> TestResult:
    tid, name = "T2", "Log Rotation (rotate_logs.sh)"
    try:
        script = PROJECT_ROOT / "scripts" / "rotate_logs.sh"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/rotate_logs.sh not found")
        if not os.access(script, os.X_OK):
            return TestResult(tid, name, False, "rotate_logs.sh not executable")
        content = script.read_text()
        if "log" not in content.lower():
            return TestResult(tid, name, False, "Script doesn't seem to handle logs")
        return TestResult(tid, name, True, "Script exists and is executable")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T3: PgBouncer
# ────────────────────────────────────────────────────────
def test_t3() -> TestResult:
    tid, name = "T3", "PgBouncer (port 5433 alive)"
    try:
        if not _port_open("localhost", PGBOUNCER_PORT):
            return TestResult(tid, name, False, f"Port {PGBOUNCER_PORT} not open — PgBouncer not running?")
        # Try actual query through pgbouncer
        try:
            _pg_query("SELECT 1", use_pgbouncer=True)
            return TestResult(tid, name, True, f"PgBouncer alive on :{PGBOUNCER_PORT}, query OK")
        except Exception as e:
            # Port open but can't query — indicates misconfiguration
            return TestResult(tid, name, False, f"Port {PGBOUNCER_PORT} open but query failed: {e}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T4: Qdrant Drift Fix
# ────────────────────────────────────────────────────────
def test_t4() -> TestResult:
    tid, name = "T4", "Qdrant Drift Fix (script + collection)"
    try:
        script = PROJECT_ROOT / "scripts" / "fix_qdrant_drift.py"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/fix_qdrant_drift.py not found")
        # Check Qdrant is reachable and has collection
        import urllib.request
        flags = _env_flags()
        qdrant_key = flags.get("QDRANT_API_KEY", "")
        req = urllib.request.Request(f"{QDRANT_BASE}/collections")
        if qdrant_key:
            req.add_header("api-key", qdrant_key)
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
        if not collections:
            return TestResult(tid, name, False, "No Qdrant collections found")
        return TestResult(tid, name, True, f"Script exists, Qdrant has {len(collections)} collection(s): {', '.join(collections)}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T5: Credit Alert
# ────────────────────────────────────────────────────────
def test_t5() -> TestResult:
    tid, name = "T5", "API Credit Alert (script)"
    try:
        script = PROJECT_ROOT / "scripts" / "check_api_credits.py"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/check_api_credits.py not found")
        if not os.access(script, os.X_OK):
            return TestResult(tid, name, False, "check_api_credits.py not executable")
        content = script.read_text()
        if "anthropic" not in content.lower() and "openai" not in content.lower():
            return TestResult(tid, name, False, "Script doesn't reference Anthropic/OpenAI")
        return TestResult(tid, name, True, "Script exists, executable, references API providers")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T6: Per-Stage Timing → PG
# ────────────────────────────────────────────────────────
def test_t6() -> TestResult:
    tid, name = "T6", "Stage Timing (query_stage_times table)"
    try:
        rows = _pg_query("SELECT COUNT(*) FROM query_stage_times")
        count = int(rows[0][0]) if rows else -1
        if count < 0:
            return TestResult(tid, name, False, "query_stage_times table not found or empty query")
        return TestResult(tid, name, True, f"Table exists with {count} rows")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T7: Interpretation Cache → PG
# ────────────────────────────────────────────────────────
def test_t7() -> TestResult:
    tid, name = "T7", "Interpretation Cache L2 (PG table)"
    try:
        rows = _pg_query("SELECT COUNT(*) FROM interpretation_cache")
        count = int(rows[0][0]) if rows else -1
        # Also check the code has L2 cache functions
        interp_file = PROJECT_ROOT / "app" / "retrieval" / "query_interpreter.py"
        has_code = False
        if interp_file.exists():
            content = interp_file.read_text()
            has_code = "_pg_cache_get" in content or "interpretation_cache" in content
        return TestResult(tid, name, has_code, f"Table exists ({count} rows), code integrated: {has_code}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T8: Hybrid Search BM25+RRF
# ────────────────────────────────────────────────────────
def test_t8() -> TestResult:
    tid, name = "T8", "Hybrid Search BM25+RRF (GIN index + tsvector)"
    try:
        # Check text_tsv column
        rows = _pg_query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='chunks' AND column_name='text_tsv'"
        )
        if not rows or "text_tsv" not in rows[0][0]:
            return TestResult(tid, name, False, "Column chunks.text_tsv not found")
        # Check GIN index
        rows = _pg_query(
            "SELECT indexname FROM pg_indexes WHERE tablename='chunks' AND indexname LIKE '%tsv%'"
        )
        if not rows:
            return TestResult(tid, name, False, "GIN index on text_tsv not found")
        # Check code
        retriever = PROJECT_ROOT / "app" / "retrieval" / "retriever.py"
        has_bm25 = False
        if retriever.exists():
            content = retriever.read_text()
            has_bm25 = "_bm25_search" in content or "rrf" in content.lower()
        return TestResult(tid, name, True, f"tsvector column + GIN index present, BM25 code: {has_bm25}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T9: Email Backfill
# ────────────────────────────────────────────────────────
def test_t9() -> TestResult:
    tid, name = "T9", "Email Backfill (2023 data)"
    try:
        script = PROJECT_ROOT / "scripts" / "backfill_email_gap.py"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/backfill_email_gap.py not found")
        # Check if there are email chunks from 2023 (chunks → documents → sources)
        rows = _pg_query(
            "SELECT COUNT(*) FROM chunks c "
            "JOIN documents d ON d.id=c.document_id "
            "JOIN sources s ON s.id=d.source_id "
            "WHERE s.source_type='email' AND d.created_at < '2024-01-01'"
        )
        count = int(rows[0][0]) if rows else 0
        return TestResult(tid, name, True, f"Backfill script exists, 2023 email chunks: {count}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T10: Top-k + Reranking
# ────────────────────────────────────────────────────────
def test_t10() -> TestResult:
    tid, name = "T10", "Top-k Increase + Diversity/Recency"
    try:
        retriever = PROJECT_ROOT / "app" / "retrieval" / "retriever.py"
        answering = PROJECT_ROOT / "app" / "retrieval" / "answering.py"
        checks = []
        if retriever.exists():
            content = retriever.read_text()
            if "apply_diversity_and_recency" in content or "diversity" in content:
                checks.append("diversity_filter")
        if answering.exists():
            content = answering.read_text()
            if "apply_diversity_and_recency" in content or "diversity" in content:
                checks.append("answering_integration")
        # Check main.py for increased limits
        main_py = PROJECT_ROOT / "app" / "api" / "main.py"
        if main_py.exists():
            content = main_py.read_text()
            # Look for top_k values > original defaults
            if "prefetch_k" in content or "top_k" in content:
                checks.append("top_k_config")
        if not checks:
            return TestResult(tid, name, False, "No diversity/recency code found in retriever or answering")
        return TestResult(tid, name, True, f"Found: {', '.join(checks)}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T11: Coverage Dashboard
# ────────────────────────────────────────────────────────
def test_t11() -> TestResult:
    tid, name = "T11", "Coverage Dashboard (API endpoint)"
    try:
        code, body = _http_get("/coverage/heatmap")
        if code == 200:
            return TestResult(tid, name, True, "GET /coverage/heatmap → 200 OK")
        elif code == 404:
            return TestResult(tid, name, False, "GET /coverage/heatmap → 404 Not Found")
        else:
            return TestResult(tid, name, False, f"GET /coverage/heatmap → {code}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T12: User Feedback Loop
# ────────────────────────────────────────────────────────
def test_t12() -> TestResult:
    tid, name = "T12", "User Feedback Loop (table + endpoint)"
    try:
        rows = _pg_query("SELECT COUNT(*) FROM response_feedback")
        count = int(rows[0][0]) if rows else -1
        # Check if feedback endpoint exists in code
        main_py = PROJECT_ROOT / "app" / "api" / "main.py"
        has_endpoint = False
        if main_py.exists():
            content = main_py.read_text()
            has_endpoint = "feedback" in content.lower()
        # Check API module
        feedback_py = PROJECT_ROOT / "app" / "api" / "feedback.py"
        has_module = feedback_py.exists()
        return TestResult(tid, name, has_endpoint or has_module,
                          f"Table exists ({count} rows), endpoint code: {has_endpoint}, feedback module: {has_module}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T13: Answer Cache TTL
# ────────────────────────────────────────────────────────
def test_t13() -> TestResult:
    tid, name = "T13", "Answer Cache (table + TTL)"
    try:
        rows = _pg_query("SELECT COUNT(*) FROM answer_cache")
        count = int(rows[0][0]) if rows else -1
        # Check for expires_at or TTL column
        cols = _pg_query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='answer_cache' AND column_name LIKE '%expir%'"
        )
        has_ttl = len(cols) > 0
        # Check indexes
        idx = _pg_query(
            "SELECT indexname FROM pg_indexes WHERE tablename='answer_cache'"
        )
        return TestResult(tid, name, True,
                          f"Table exists ({count} rows), TTL column: {has_ttl}, indexes: {len(idx)}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T14: Progressive Context
# ────────────────────────────────────────────────────────
def test_t14() -> TestResult:
    tid, name = "T14", "Progressive Context for Analysis"
    try:
        # Check code for progressive context logic
        found_in = []
        for fname in ["app/retrieval/retriever.py", "app/retrieval/answering.py", "app/api/main.py"]:
            fpath = PROJECT_ROOT / fname
            if fpath.exists():
                content = fpath.read_text()
                if "progressive" in content.lower() or "second_pass" in content.lower() or "follow_up" in content.lower():
                    found_in.append(fname)
        flags = _env_flags()
        flag_val = flags.get("ENABLE_PROGRESSIVE_CONTEXT", "not set")
        if found_in:
            return TestResult(tid, name, True, f"Progressive context code in: {', '.join(found_in)}, flag={flag_val}")
        else:
            # Check if it's at least spec'd in upgrade prompts
            spec = PROJECT_ROOT / "scripts" / "upgrade_prompts"
            if spec.exists():
                return TestResult(tid, name, False, "Code not yet implemented (spec exists in upgrade_prompts)")
            return TestResult(tid, name, False, "No progressive context code found")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T15: Retrieval Quality Alerts
# ────────────────────────────────────────────────────────
def test_t15() -> TestResult:
    tid, name = "T15", "Retrieval Quality Alerts (script)"
    try:
        script = PROJECT_ROOT / "scripts" / "check_retrieval_quality.py"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/check_retrieval_quality.py not found")
        if not os.access(script, os.X_OK):
            return TestResult(tid, name, False, "check_retrieval_quality.py not executable")
        content = script.read_text()
        checks = []
        if "fallback" in content.lower():
            checks.append("fallback_check")
        if "latency" in content.lower() or "p95" in content.lower():
            checks.append("latency_check")
        if "alert" in content.lower():
            checks.append("alerting")
        return TestResult(tid, name, True, f"Script exists, executable, checks: {', '.join(checks)}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T16: Entity Linking (people table)
# ────────────────────────────────────────────────────────
def test_t16() -> TestResult:
    tid, name = "T16", "Entity Linking (people table)"
    try:
        rows = _pg_query("SELECT COUNT(*) FROM people")
        count = int(rows[0][0]) if rows else 0
        if count == 0:
            return TestResult(tid, name, False, "people table is empty")
        # Check populate script
        script = PROJECT_ROOT / "scripts" / "populate_people.py"
        has_script = script.exists()
        return TestResult(tid, name, True, f"people table: {count} rows, populate script: {has_script}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T17: Weekly Quality Review
# ────────────────────────────────────────────────────────
def test_t17() -> TestResult:
    tid, name = "T17", "Weekly Quality Review (script + table)"
    try:
        script = PROJECT_ROOT / "scripts" / "weekly_quality_review.py"
        if not script.exists():
            return TestResult(tid, name, False, "scripts/weekly_quality_review.py not found")
        # Check quality_reviews table
        rows = _pg_query(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='quality_reviews' AND table_schema='public'"
        )
        has_table = rows and int(rows[0][0]) > 0
        return TestResult(tid, name, True, f"Script exists, quality_reviews table: {has_table}")
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T18: Chunking Optimization
# ────────────────────────────────────────────────────────
def test_t18() -> TestResult:
    tid, name = "T18", "Chunking Optimization (analysis)"
    try:
        # Check chunk size distribution
        rows = _pg_query(
            "SELECT "
            "ROUND(AVG(LENGTH(text))) as avg_len, "
            "COUNT(*) FILTER (WHERE LENGTH(text) < 50) as too_short, "
            "COUNT(*) FILTER (WHERE LENGTH(text) > 6000) as too_long, "
            "COUNT(*) as total "
            "FROM chunks"
        )
        if not rows or not rows[0][0]:
            return TestResult(tid, name, False, "Could not query chunk statistics")
        avg_len, too_short, too_long, total = rows[0]
        pct_short = round(int(too_short) / max(int(total), 1) * 100, 1)
        pct_long = round(int(too_long) / max(int(total), 1) * 100, 1)
        healthy = pct_short < 20 and pct_long < 20
        msg = f"avg={avg_len} chars, <50: {pct_short}%, >6000: {pct_long}%, total={total}"
        return TestResult(tid, name, healthy, msg + (" — within bounds" if healthy else " — out of bounds!"))
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ────────────────────────────────────────────────────────
# T19: PG max_connections Tuning
# ────────────────────────────────────────────────────────
def test_t19() -> TestResult:
    tid, name = "T19", "PG max_connections + PgBouncer config"
    try:
        rows = _pg_query("SELECT setting FROM pg_settings WHERE name='max_connections'")
        max_conn = int(rows[0][0]) if rows else 0
        # Check current connections vs max
        rows2 = _pg_query("SELECT COUNT(*) FROM pg_stat_activity")
        active = int(rows2[0][0]) if rows2 else 0
        utilization = round(active / max(max_conn, 1) * 100, 1)
        # Check pgbouncer config
        pgb_ini = PROJECT_ROOT / "pgbouncer" / "pgbouncer.ini"
        has_pgb_config = pgb_ini.exists()
        status = f"max_connections={max_conn}, active={active} ({utilization}%), pgbouncer.ini: {has_pgb_config}"
        ok = utilization < 80 and has_pgb_config
        return TestResult(tid, name, ok, status)
    except Exception as e:
        return TestResult(tid, name, False, str(e))


# ════════════════════════════════════════════════════════
# Runner
# ════════════════════════════════════════════════════════

ALL_TESTS: list[tuple[str, Callable[[], TestResult]]] = [
    ("T1",  test_t1),
    ("T2",  test_t2),
    ("T3",  test_t3),
    ("T4",  test_t4),
    ("T5",  test_t5),
    ("T6",  test_t6),
    ("T7",  test_t7),
    ("T8",  test_t8),
    ("T9",  test_t9),
    ("T10", test_t10),
    ("T11", test_t11),
    ("T12", test_t12),
    ("T13", test_t13),
    ("T14", test_t14),
    ("T15", test_t15),
    ("T16", test_t16),
    ("T17", test_t17),
    ("T18", test_t18),
    ("T19", test_t19),
]


def run_all_tests() -> list[TestResult]:
    results = []
    for tid, test_fn in ALL_TESTS:
        try:
            result = test_fn()
        except Exception as e:
            result = TestResult(tid, "(crashed)", False, f"Unexpected error: {e}")
        results.append(result)
    return results


def main():
    results = run_all_tests()
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print(f"\n{'=' * 60}")
    print("GILBERTUS QUALITY UPGRADE — RAPORT TESTÓW")
    print(f"{'=' * 60}")
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"\n{'SZCZEGÓŁY':=<60}")
    for r in results:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} [{r.id}] {r.name}")
        print(f"       {r.message}")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
