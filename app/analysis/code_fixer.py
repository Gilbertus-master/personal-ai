"""
Automated code fixer v2 — tiering, clustering, internal pattern research.

Picks unresolved findings from code_review_findings, groups them into clusters,
assigns tiers (1=deterministic, 2=LLM), and fixes them with enriched context.

Cron: every 10 min during work hours (8-22 CET), 8 workers.
CLI: python -m app.analysis.code_fixer [--parallel N] [--dry-run] [--tier1-only] [--tier2-only]
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from app.analysis.autofixer.cluster_manager import build_clusters
from app.analysis.autofixer.context_gatherer import gather_cluster_context
from app.analysis.autofixer.prompt_builder import build_fix_prompt
from app.analysis.autofixer.tier1_executor import execute_tier1
from app.analysis.autofixer.tier2_executor import execute_tier2


def _ensure_schema() -> None:
    """Ensure all required columns exist (backward compat)."""
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for col_sql in [
                "ADD COLUMN IF NOT EXISTS fix_attempted_at TIMESTAMPTZ",
                "ADD COLUMN IF NOT EXISTS fix_attempt_count INTEGER NOT NULL DEFAULT 0",
                "ADD COLUMN IF NOT EXISTS manual_review BOOLEAN NOT NULL DEFAULT FALSE",
                "ADD COLUMN IF NOT EXISTS cluster_id TEXT",
                "ADD COLUMN IF NOT EXISTS tier INTEGER",
            ]:
                cur.execute(f"ALTER TABLE code_review_findings {col_sql}")
        conn.commit()


def run_dry(tier_filter: int | None = None) -> list[dict]:
    """Show clusters without fixing anything."""
    _ensure_schema()
    clusters = build_clusters()

    if tier_filter:
        clusters = [c for c in clusters if c["tier"] == tier_filter]

    for c in clusters:
        tier_label = "T1-deterministic" if c["tier"] == 1 else "T2-llm"
        log.info("cluster",
                 id=c["cluster_id"],
                 tier=tier_label,
                 category=c["category"],
                 title=c["title"][:60],
                 severity=c["severity"],
                 files=len(c["file_paths"]),
                 findings=c["size"])

    tier1 = [c for c in clusters if c["tier"] == 1]
    tier2 = [c for c in clusters if c["tier"] == 2]
    log.info("dry_run_summary",
             total_clusters=len(clusters),
             tier1_clusters=len(tier1),
             tier2_clusters=len(tier2),
             tier1_findings=sum(c["size"] for c in tier1),
             tier2_findings=sum(c["size"] for c in tier2))

    return clusters


def _process_cluster(cluster: dict, lock: threading.Lock) -> dict:
    """Process a single cluster (thread-safe)."""
    if cluster["tier"] == 1:
        result = execute_tier1(cluster)
    else:
        context = gather_cluster_context(cluster)
        prompt = build_fix_prompt(cluster, context)
        result = execute_tier2(cluster, context, prompt)

    result["cluster_id"] = cluster["cluster_id"]
    result["tier"] = cluster["tier"]
    result["category"] = cluster["category"]
    result["title"] = cluster["title"]
    result["cluster_size"] = cluster["size"]
    return result


def run_parallel(workers: int = 8, tier_filter: int | None = None) -> list[dict]:
    """Run fix workers in parallel on clusters.

    Tier 1 clusters are processed first (fast, no LLM).
    Tier 2 clusters get enriched context and LLM sessions.
    """
    _ensure_schema()
    clusters = build_clusters()

    if tier_filter:
        clusters = [c for c in clusters if c["tier"] == tier_filter]

    if not clusters:
        log.info("no_clusters_to_fix")
        return [{"status": "idle", "fixed": False}]

    # Limit to workers count
    clusters = clusters[:workers * 2]

    log.info("parallel_start",
             workers=workers,
             clusters=len(clusters),
             tier1=sum(1 for c in clusters if c["tier"] == 1),
             tier2=sum(1 for c in clusters if c["tier"] == 2))

    results = []
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_cluster, c, lock): c
            for c in clusters
        }
        for future in as_completed(futures):
            cluster = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log.error("worker_crashed",
                          cluster_id=cluster["cluster_id"],
                          error=str(e))
                results.append({
                    "status": "error", "fixed": False,
                    "cluster_id": cluster["cluster_id"],
                    "error": str(e),
                })

    fixed = sum(1 for r in results if r.get("fixed"))
    total_findings = sum(r.get("cluster_size", 1) for r in results if r.get("fixed"))
    log.info("parallel_complete",
             total_clusters=len(results),
             fixed_clusters=fixed,
             fixed_findings=total_findings)

    return results


def run() -> dict:
    """Single-cluster fix mode (backward compat)."""
    results = run_parallel(workers=1)
    return results[0] if results else {"status": "idle", "fixed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autofixer v2 — tiering + clustering")
    parser.add_argument("--parallel", "--workers", type=int, default=0,
                        help="Run N workers in parallel (0 = single mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show clusters without fixing")
    parser.add_argument("--tier1-only", action="store_true",
                        help="Only process tier-1 (deterministic) fixes")
    parser.add_argument("--tier2-only", action="store_true",
                        help="Only process tier-2 (LLM) fixes")
    args = parser.parse_args()

    tier_filter = None
    if args.tier1_only:
        tier_filter = 1
    elif args.tier2_only:
        tier_filter = 2

    if args.dry_run:
        clusters = run_dry(tier_filter=tier_filter)
        for c in clusters:
            print(json.dumps({
                "cluster_id": c["cluster_id"],
                "tier": c["tier"],
                "category": c["category"],
                "title": c["title"],
                "severity": c["severity"],
                "files": len(c["file_paths"]),
                "findings": c["size"],
            }, ensure_ascii=False, indent=2, default=str))
    elif args.parallel > 0:
        results = run_parallel(workers=args.parallel, tier_filter=tier_filter)
        for r in results:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        result = run()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
