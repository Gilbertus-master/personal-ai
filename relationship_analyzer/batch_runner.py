"""Batch runner for relationship analysis.

Analyzes all relationship pairs above a tie-strength threshold.
Priority: new (never analyzed) > stale > strong ties > rest.
Commits every 50 pairs to avoid long transactions.
"""

from __future__ import annotations

import time

import psycopg
import structlog
from psycopg.rows import dict_row

from .analyzer import analyze_relationship

log = structlog.get_logger("relationship_analyzer.batch_runner")

COMMIT_BATCH_SIZE = 50


def run_batch(
    conn: psycopg.Connection,
    min_tie_strength: float = 0.2,
    generate_ai_for_strong: bool = True,
    limit: int | None = None,
) -> dict:
    """Run batch analysis for all pairs above threshold.

    Priority order:
      1. New pairs (never analyzed in relationship_analyses)
      2. Stale pairs (is_stale = true)
      3. Strong ties (tie_strength >= 0.5)
      4. Rest (above min_tie_strength)

    Args:
        conn: Database connection.
        min_tie_strength: Minimum tie_strength to include.
        generate_ai_for_strong: Generate AI narrative only for strong ties (>=0.5).
        limit: Max pairs to analyze (None = unlimited).

    Returns:
        dict with stats: analyzed, errors, duration_s.
    """
    t_start = time.monotonic()

    # Fetch prioritized pairs
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH pairs AS (
                SELECT
                    pr.person_id_from AS person_id_a,
                    pr.person_id_to AS person_id_b,
                    pr.tie_strength,
                    pr.last_contact_at,
                    ra.computed_at AS last_analyzed_at,
                    ra.is_stale,
                    CASE
                        WHEN ra.analysis_id IS NULL THEN 1  -- never analyzed
                        WHEN ra.is_stale = true THEN 2      -- stale
                        WHEN pr.tie_strength >= 0.5 THEN 3  -- strong
                        ELSE 4                                -- rest
                    END AS priority
                FROM person_relationships pr
                JOIN persons pa ON pa.person_id = pr.person_id_from AND pa.gdpr_delete_requested_at IS NULL
                JOIN persons pb ON pb.person_id = pr.person_id_to AND pb.gdpr_delete_requested_at IS NULL
                LEFT JOIN relationship_analyses ra
                    ON ra.person_id_a = pr.person_id_from
                    AND ra.person_id_b = pr.person_id_to
                    AND ra.perspective = 'dyadic'
                WHERE pr.tie_strength >= %s
            )
            SELECT person_id_a, person_id_b, tie_strength, priority
            FROM pairs
            ORDER BY priority ASC, tie_strength DESC
            """,
            (min_tie_strength,),
        )
        pairs = cur.fetchall()

    if limit:
        pairs = pairs[:limit]

    total = len(pairs)
    analyzed = 0
    errors = 0

    log.info("batch_start", total_pairs=total, min_tie_strength=min_tie_strength)

    for i, pair in enumerate(pairs):
        person_id_a = pair["person_id_a"]
        person_id_b = pair["person_id_b"]
        ts = pair["tie_strength"]

        # AI only for strong ties (cost control)
        use_ai = generate_ai_for_strong and ts >= 0.5

        try:
            analyze_relationship(
                person_id_a,
                person_id_b,
                conn,
                data_window_days=365,
                generate_ai=use_ai,
            )
            analyzed += 1
        except Exception:
            log.exception(
                "batch_pair_failed",
                person_a=str(person_id_a),
                person_b=str(person_id_b),
            )
            errors += 1
            # Rollback failed transaction so we can continue
            conn.rollback()

        # Commit every N pairs
        if (i + 1) % COMMIT_BATCH_SIZE == 0:
            try:
                conn.commit()
                log.info("batch_checkpoint", processed=i + 1, total=total)
            except Exception:
                log.exception("batch_commit_failed", at_pair=i + 1)
                conn.rollback()

    # Final commit
    try:
        conn.commit()
    except Exception:
        log.exception("batch_final_commit_failed")
        conn.rollback()

    duration_s = round(time.monotonic() - t_start, 1)

    stats = {
        "total_pairs": total,
        "analyzed": analyzed,
        "errors": errors,
        "duration_s": duration_s,
        "pairs_per_second": round(analyzed / max(duration_s, 0.1), 1),
    }

    log.info("batch_complete", **stats)
    return stats
