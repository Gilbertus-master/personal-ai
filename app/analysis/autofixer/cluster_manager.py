"""
Cluster manager — groups code_review_findings into clusters and assigns tiers.

Tier 1: deterministic fixes (ruff, regex) — no LLM needed
Tier 2: requires LLM (claude -p) with enriched context
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

MAX_CLUSTER_SIZE = 10
MAX_ATTEMPTS_PER_ROUND = 3
MAX_ROUNDS = 2

# Patterns that can be fixed deterministically (Tier 1)
TIER1_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("convention", re.compile(r"unused.*(import|variable)", re.IGNORECASE)),
    ("convention", re.compile(r"(print\(\)|print statement|structlog)", re.IGNORECASE)),
    ("quality", re.compile(r"unused.*(import|variable)", re.IGNORECASE)),
]


def _assign_tier(category: str, title: str) -> int:
    """Assign tier based on category and title pattern."""
    for pat_category, pat_re in TIER1_PATTERNS:
        if category == pat_category and pat_re.search(title):
            return 1
    return 2


def _make_cluster_id(category: str, title: str) -> str:
    """Generate a stable cluster ID from category + title."""
    raw = f"{category}__{title}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:40]
    return f"{category}__{slug}__{short_hash}"


def build_clusters(exclude_files: list[str] | None = None) -> list[dict]:
    """Build clusters from open findings, assign tiers, write back to DB.

    Returns list of cluster dicts sorted by: tier ASC, severity ASC, count DESC.
    """
    exclude = exclude_files or []
    max_total = MAX_ATTEMPTS_PER_ROUND * MAX_ROUNDS

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Fetch all eligible findings
            if exclude:
                placeholders = ",".join(["%s"] * len(exclude))
                where_excl = f"AND file_path NOT IN ({placeholders})"
                params: tuple = (max_total,) + tuple(exclude)
            else:
                where_excl = ""
                params = (max_total,)

            cur.execute(f"""
                SELECT id, file_path, severity, category, title, description,
                       line_start, line_end, suggested_fix, fix_attempt_count
                FROM code_review_findings
                WHERE resolved = FALSE
                  AND manual_review = FALSE
                  AND severity IN ('critical', 'high', 'medium', 'low')
                  AND fix_attempt_count < %s
                  AND (fix_attempted_at IS NULL
                       OR fix_attempted_at < NOW() - INTERVAL '2 hours')
                  {where_excl}
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 99
                    END,
                    created_at ASC
            """, params)

            rows = cur.fetchall()

    if not rows:
        log.info("no_eligible_findings")
        return []

    # Group by (category, title)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        finding = {
            "id": r[0], "file_path": r[1], "severity": r[2],
            "category": r[3], "title": r[4], "description": r[5],
            "line_start": r[6], "line_end": r[7], "suggested_fix": r[8],
            "fix_attempt_count": r[9],
        }
        groups[(r[3], r[4])].append(finding)

    # Build clusters (split large groups)
    clusters: list[dict] = []
    for (category, title), findings in groups.items():
        tier = _assign_tier(category, title)
        cluster_id = _make_cluster_id(category, title)

        # Split into chunks of MAX_CLUSTER_SIZE
        for i in range(0, len(findings), MAX_CLUSTER_SIZE):
            chunk = findings[i:i + MAX_CLUSTER_SIZE]
            part = i // MAX_CLUSTER_SIZE
            cid = f"{cluster_id}__{part}" if part > 0 else cluster_id

            clusters.append({
                "cluster_id": cid,
                "category": category,
                "title": title,
                "tier": tier,
                "findings": chunk,
                "file_paths": list({f["file_path"] for f in chunk}),
                "severity": chunk[0]["severity"],  # highest in group (pre-sorted)
                "size": len(chunk),
            })

    # Sort: tier 1 first, then by severity, then by size desc
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    clusters.sort(key=lambda c: (
        c["tier"],
        severity_order.get(c["severity"], 99),
        -c["size"],
    ))

    # Write cluster_id and tier back to DB
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for cluster in clusters:
                finding_ids = [f["id"] for f in cluster["findings"]]
                placeholders = ",".join(["%s"] * len(finding_ids))
                cur.execute(f"""
                    UPDATE code_review_findings
                    SET cluster_id = %s, tier = %s
                    WHERE id IN ({placeholders})
                """, (cluster["cluster_id"], cluster["tier"], *finding_ids))
        conn.commit()

    tier1_count = sum(1 for c in clusters if c["tier"] == 1)
    tier2_count = sum(1 for c in clusters if c["tier"] == 2)
    log.info("clusters_built",
             total=len(clusters),
             tier1=tier1_count,
             tier2=tier2_count,
             total_findings=len(rows))

    return clusters
