"""
Cluster manager — groups code_review_findings into clusters and assigns tiers.

Tier 1: deterministic fixes (ruff, regex) — no LLM needed
Tier 2: requires LLM (claude -p) with enriched context

Title normalization collapses similar findings into larger clusters.
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

# Tier 1 patterns: category-agnostic regex matching on title
TIER1_PATTERNS: list[re.Pattern] = [
    re.compile(r"unused.*(import|variable)", re.IGNORECASE),
    # print→structlog: only for Python files where print() is directly replaceable
    re.compile(r"print\(\).*instead of structlog|print\(\) used.*structlog|print.*should.*structlog", re.IGNORECASE),
    re.compile(r"\$\(date\)(?!\s*\+)", re.IGNORECASE),  # bare $(date) in shell scripts
    re.compile(r"redundant.*import|duplicate.*import", re.IGNORECASE),
    # Note: "no structlog", "no logging", "silent swallowing" → tier-2 (need LLM to add logging)
    # Note: dead code/unreachable → tier-2 (structural removal needs LLM)
]

# Normalization rules: strip file-specific details from titles for better clustering
_TITLE_NORM_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\(lines? \d+[-\u2013]\d+\)"), ""),
    (re.compile(r"on line \d+"), ""),
    (re.compile(r"line \d+"), ""),
    (re.compile(r"[`'\"][\w.]+[`'\"]"), "\u00abname\u00bb"),
    (re.compile(r"\b[\w/]+\.py\b"), "\u00abfile\u00bb"),
    (re.compile(r"\b[\w/]+\.sh\b"), "\u00abfile\u00bb"),
    (re.compile(r"\s+"), " "),
]


def _normalize_title(title: str) -> str:
    """Normalize title for clustering — strip file-specific info."""
    result = title
    for pattern, replacement in _TITLE_NORM_RULES:
        result = pattern.sub(replacement, result)
    return result.strip()


def _assign_tier(category: str, title: str) -> int:
    """Assign tier based on title pattern (category-agnostic)."""
    for pat_re in TIER1_PATTERNS:
        if pat_re.search(title):
            return 1
    return 2


def _make_cluster_id(category: str, title: str) -> str:
    """Generate a stable cluster ID from category + normalized title."""
    norm = _normalize_title(title)
    raw = f"{category}__{norm}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", norm.lower())[:40]
    return f"{category}__{slug}__{short_hash}"


def build_clusters(exclude_files: list[str] | None = None) -> list[dict]:
    """Build clusters from open findings, assign tiers, write back to DB.

    Returns list of cluster dicts sorted by: tier ASC, severity ASC, count DESC.
    """
    exclude = exclude_files or []
    max_total = MAX_ATTEMPTS_PER_ROUND * MAX_ROUNDS

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if exclude:
                placeholders = ",".join(["%s"] * len(exclude))
                where_excl = f"AND file_path NOT IN ({placeholders})"
                params: tuple = (max_total,) + tuple(exclude)
            else:
                where_excl = ""
                params = (max_total,)

            cur.execute(f"""
                SELECT id, file_path, severity, category, title, description,
                       line_start, line_end, suggested_fix, fix_attempt_count, tier
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

    # Group by (category, normalized_title) for better clustering
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        finding = {
            "id": r[0], "file_path": r[1], "severity": r[2],
            "category": r[3], "title": r[4], "description": r[5],
            "line_start": r[6], "line_end": r[7], "suggested_fix": r[8],
            "fix_attempt_count": r[9], "tier": r[10],
        }
        norm_title = _normalize_title(r[4])
        groups[(r[3], norm_title)].append(finding)

    # Build clusters (split large groups)
    clusters: list[dict] = []
    for (category, title), findings in groups.items():
        # Prefer stored DB tier (set during initial dry-run); recompute only if NULL
        db_tier = findings[0].get("tier")
        tier = db_tier if db_tier is not None else _assign_tier(category, title)
        cluster_id = _make_cluster_id(category, title)

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
                "severity": chunk[0]["severity"],
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
