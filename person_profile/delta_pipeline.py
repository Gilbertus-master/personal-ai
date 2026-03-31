"""Weekly delta update pipeline.

Run once a week (e.g. Sunday 03:00 CET).
Processes ONLY data from the last 7 days + overlap for late arrivals.

Steps (order matters — respect dependencies):
 1. Update person_identities (new aliases, channel changes)
 2. Update person_demographics & person_professional
 3. Update person_behavioral (aggregates from new interactions)
 4. Recompute person_relationships (tie_strength) for active pairs
 5. Update person_relationship_trajectory (delta scores)
 6. Recompute person_network_position (degree, influence, clusters)
 7. Extract AI open_loops from new messages (optional, requires NLP)
 8. Update person_shared_context (new entities from messages)
 9. Generate/update person_next_actions
10. Mark stale briefings as is_stale = true
11. Save watermarks to pipeline_state
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from app.db.postgres import get_pg_connection

from . import config as cfg
from .repository import (
    acquire_pipeline_lock,
    get_watermark,
    save_watermark,
    upsert_behavioral,
    upsert_network_position,
    upsert_trajectory,
)
from .models import (
    PersonBehavioral,
    PersonNetworkPosition,
    PersonRelationshipTrajectory,
)
from .tie_strength import recompute_active_pairs
from .next_actions import generate_all_next_actions

log = structlog.get_logger("person_profile.delta_pipeline")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _watermark_since(conn: psycopg.Connection, source: str) -> datetime:
    wm = get_watermark(conn, source)
    if wm:
        return wm - timedelta(hours=cfg.WATERMARK_OVERLAP_HOURS)
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


# ─── Step 3: Behavioral aggregates ───────────────────────────────────

def _step_behavioral(conn: psycopg.Connection, since: datetime) -> dict:
    """Recompute behavioral aggregates for persons with recent activity."""
    conn.row_factory = dict_row
    stats = {"processed": 0, "new": 0, "updated": 0}

    # Find persons with activity since watermark
    rows = conn.execute(
        """SELECT DISTINCT person_id_from AS pid FROM person_relationships
           WHERE last_contact_at >= %s
           UNION
           SELECT DISTINCT person_id_to AS pid FROM person_relationships
           WHERE last_contact_at >= %s""",
        (since, since),
    ).fetchall()

    person_ids = {r["pid"] for r in rows}
    log.info("behavioral_candidates", count=len(person_ids))

    for pid in person_ids:
        agg = conn.execute(
            """SELECT
                   COALESCE(SUM(interaction_count), 0) AS total,
                   COALESCE(SUM(CASE WHEN last_contact_at > now() - INTERVAL '30 days'
                                     THEN interaction_count ELSE 0 END), 0) AS last_30d,
                   COALESCE(SUM(CASE WHEN last_contact_at > now() - INTERVAL '7 days'
                                     THEN interaction_count ELSE 0 END), 0) AS last_7d,
                   COUNT(DISTINCT dominant_channel) AS channels,
                   MIN(first_contact_at) AS first_at,
                   MAX(last_contact_at) AS last_at
               FROM person_relationships
               WHERE person_id_from = %s OR person_id_to = %s""",
            (str(pid), str(pid)),
        ).fetchone()

        if not agg:
            continue

        days_since = None
        if agg["last_at"]:
            delta = _now() - agg["last_at"].replace(tzinfo=timezone.utc)
            days_since = int(delta.total_seconds() / 86400)

        # Simple engagement score: weighted sum of recency + frequency
        freq_norm = min(agg["total"] / 100, 1.0) if agg["total"] else 0
        rec_norm = max(0, 1 - (days_since or 365) / 365) if days_since is not None else 0
        engagement = round(0.5 * freq_norm + 0.5 * rec_norm, 4)

        upsert_behavioral(
            conn,
            PersonBehavioral(
                person_id=pid,
                total_interactions=agg["total"],
                interactions_last_30d=agg["last_30d"],
                interactions_last_7d=agg["last_7d"],
                active_channels_count=agg["channels"],
                rfm_recency_days=days_since,
                rfm_frequency_score=round(freq_norm, 4),
                engagement_score=engagement,
                first_interaction_at=agg["first_at"],
                last_interaction_at=agg["last_at"],
            ),
        )
        stats["processed"] += 1
        stats["updated"] += 1

    return stats


# ─── Step 5: Trajectory ──────────────────────────────────────────────

def _step_trajectory(conn: psycopg.Connection) -> dict:
    """Update trajectory for all relationships."""
    stats = {"processed": 0, "new": 0, "updated": 0}
    conn.row_factory = dict_row

    rows = conn.execute(
        """SELECT person_id_from, person_id_to, tie_strength, last_contact_at
           FROM person_relationships"""
    ).fetchall()

    for rel in rows:
        pid_from = rel["person_id_from"]
        pid_to = rel["person_id_to"]
        current = rel["tie_strength"]

        # Get previous trajectory
        prev = conn.execute(
            """SELECT current_tie_strength, history_snapshots, peak_tie_strength
               FROM person_relationship_trajectory
               WHERE person_id = %s AND person_id_to = %s""",
            (str(pid_from), str(pid_to)),
        ).fetchone()

        # Compute deltas
        prev_strength = prev["current_tie_strength"] if prev else 0
        delta_7d = round(current - prev_strength, 4)

        # Snapshots (keep last 52 weeks)
        snapshots = (prev["history_snapshots"] or []) if prev else []
        snapshots.append({
            "date": _now().strftime("%Y-%m-%d"),
            "score": round(current, 4),
        })
        snapshots = snapshots[-52:]

        # Compute delta_30d, delta_90d from snapshots
        delta_30d = _delta_from_snapshots(snapshots, 30, current)
        delta_90d = _delta_from_snapshots(snapshots, 90, current)

        # Determine trajectory status
        days_since = None
        if rel["last_contact_at"]:
            days_since = int(
                (_now() - rel["last_contact_at"].replace(tzinfo=timezone.utc)).total_seconds() / 86400
            )

        status = _classify_trajectory(
            current, prev_strength, delta_30d, days_since, prev is None
        )

        peak = max(
            current, prev["peak_tie_strength"] or 0 if prev else 0
        )

        upsert_trajectory(
            conn,
            PersonRelationshipTrajectory(
                person_id=pid_from,
                person_id_to=pid_to,
                current_tie_strength=current,
                peak_tie_strength=peak,
                delta_7d=delta_7d,
                delta_30d=delta_30d,
                delta_90d=delta_90d,
                trajectory_status=status,
                days_since_last_contact=days_since,
                history_snapshots=snapshots,
            ),
        )
        stats["processed"] += 1
        stats["updated"] += 1

    return stats


def _delta_from_snapshots(
    snapshots: list[dict], days_ago: int, current: float
) -> float | None:
    """Find snapshot closest to N days ago and compute delta."""
    if not snapshots:
        return None

    target = _now().date() - timedelta(days=days_ago)
    closest = None
    closest_dist = float("inf")

    for snap in snapshots:
        try:
            snap_date = datetime.strptime(snap["date"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        dist = abs((snap_date - target).days)
        if dist < closest_dist:
            closest_dist = dist
            closest = snap

    if closest and closest_dist < days_ago // 2:
        return round(current - closest["score"], 4)
    return None


def _classify_trajectory(
    current: float,
    previous: float,
    delta_30d: float | None,
    days_since: int | None,
    is_new: bool,
) -> str:
    if is_new:
        return "new"
    if days_since is not None and days_since > 180:
        if delta_30d and delta_30d > 0.05:
            return "revived"
        return "dormant"
    if delta_30d is not None:
        if delta_30d > 0.05:
            return "growing"
        if delta_30d < -0.05:
            return "cooling"
    return "stable"


# ─── Step 6: Network position ────────────────────────────────────────

def _step_network_position(conn: psycopg.Connection) -> dict:
    """Recompute network position metrics for all persons."""
    stats = {"processed": 0, "new": 0, "updated": 0}
    conn.row_factory = dict_row

    persons = conn.execute(
        "SELECT person_id FROM persons WHERE gdpr_delete_requested_at IS NULL"
    ).fetchall()

    # Build adjacency for influence approximation
    all_rels = conn.execute(
        """SELECT person_id_from, person_id_to, tie_strength
           FROM person_relationships WHERE tie_strength > 0.1"""
    ).fetchall()

    # Neighbor map
    neighbors: dict[str, set[str]] = {}
    for r in all_rels:
        pf, pt = str(r["person_id_from"]), str(r["person_id_to"])
        neighbors.setdefault(pf, set()).add(pt)
        neighbors.setdefault(pt, set()).add(pf)

    # Simplified PageRank approximation (1 iteration)
    n_persons = len(persons) or 1
    base_rank = 1.0 / n_persons
    influence: dict[str, float] = {}
    for p in persons:
        pid = str(p["person_id"])
        nbrs = neighbors.get(pid, set())
        # Sum of neighbor contributions
        rank = base_rank
        for nbr in nbrs:
            nbr_degree = len(neighbors.get(nbr, set())) or 1
            rank += base_rank / nbr_degree
        influence[pid] = rank

    # Normalize influence to [0, 1]
    max_inf = max(influence.values()) if influence else 1
    for k in influence:
        influence[k] = round(influence[k] / max_inf, 4)

    for p in persons:
        pid = str(p["person_id"])
        nbrs = neighbors.get(pid, set())

        # Count strong/weak ties
        strong = 0
        weak = 0
        for r in all_rels:
            if str(r["person_id_from"]) == pid or str(r["person_id_to"]) == pid:
                if r["tie_strength"] > cfg.STRENGTH_STRONG:
                    strong += 1
                elif r["tie_strength"] > cfg.STRENGTH_WEAK:
                    weak += 1

        # Broker detection: connects groups that don't connect to each other
        is_broker = False
        broker_score = 0.0
        if len(nbrs) >= 3:
            # Simple betweenness proxy: what fraction of neighbor pairs are connected?
            pairs_connected = 0
            total_pairs = 0
            nbr_list = list(nbrs)
            for i in range(len(nbr_list)):
                for j in range(i + 1, len(nbr_list)):
                    total_pairs += 1
                    if nbr_list[j] in neighbors.get(nbr_list[i], set()):
                        pairs_connected += 1
            if total_pairs > 0:
                connectivity = pairs_connected / total_pairs
                broker_score = round(1.0 - connectivity, 4)
                is_broker = broker_score > 0.6

        # Best introducers: top 3 neighbors by influence
        best_intros = sorted(nbrs, key=lambda x: influence.get(x, 0), reverse=True)[:3]

        upsert_network_position(
            conn,
            PersonNetworkPosition(
                person_id=UUID(pid),
                degree_centrality=len(nbrs),
                strong_ties_count=strong,
                weak_ties_count=weak,
                influence_score=influence.get(pid, 0),
                is_broker=is_broker,
                broker_score=broker_score,
                best_introducers=[UUID(x) for x in best_intros] if best_intros else None,
            ),
        )
        stats["processed"] += 1
        stats["updated"] += 1

    return stats


# ─── Step 10: Mark stale briefings ───────────────────────────────────

def _step_mark_stale_briefings(conn: psycopg.Connection) -> int:
    """Mark briefings as stale where underlying data changed significantly."""
    cur = conn.execute(
        """UPDATE person_briefings SET is_stale = true
           WHERE is_stale = false AND (
               expires_at < now()
               OR person_id IN (
                   SELECT DISTINCT person_id_to FROM person_relationship_trajectory
                   WHERE ABS(delta_7d) > %s
               )
               OR person_id IN (
                   SELECT person_id FROM person_open_loops
                   WHERE status = 'open' AND created_at > (
                       SELECT COALESCE(MAX(generated_at), '2000-01-01')
                       FROM person_briefings pb2
                       WHERE pb2.person_id = person_open_loops.person_id
                         AND pb2.is_stale = false
                   )
               )
               OR person_id IN (
                   SELECT person_id FROM person_professional
                   WHERE job_change_detected_at > now() - INTERVAL '7 days'
               )
           )"""
    , (cfg.BRIEFING_STALE_TIE_DELTA,))
    return cur.rowcount


# ─── Main pipeline ───────────────────────────────────────────────────

def run_delta_pipeline(full_rebuild: bool = False) -> dict[str, Any]:
    """Execute the full delta update pipeline.

    Args:
        full_rebuild: If True, ignore watermarks and reprocess everything.

    Returns:
        Dict with per-step stats.
    """
    pipeline_name = "person_profile_delta"
    results: dict[str, Any] = {}
    t0 = time.monotonic()

    with get_pg_connection() as conn:
        # Acquire lock
        if not acquire_pipeline_lock(conn, pipeline_name):
            log.warning("pipeline_already_running", pipeline=pipeline_name)
            return {"error": "already_running"}
        conn.commit()

        try:
            since = (
                datetime(2000, 1, 1, tzinfo=timezone.utc)
                if full_rebuild
                else _watermark_since(conn, pipeline_name)
            )
            log.info("delta_pipeline_start", since=since, full_rebuild=full_rebuild)

            # Step 3: Behavioral aggregates
            log.info("step_3_behavioral")
            results["behavioral"] = _step_behavioral(conn, since)
            conn.commit()

            # Step 4: Tie-strength recomputation
            log.info("step_4_tie_strength")
            since_str = since.isoformat() if not full_rebuild else None
            updated_pairs = recompute_active_pairs(conn, since_str)
            results["tie_strength"] = {"updated_pairs": updated_pairs}
            conn.commit()

            # Step 5: Trajectory
            log.info("step_5_trajectory")
            results["trajectory"] = _step_trajectory(conn)
            conn.commit()

            # Step 6: Network position
            log.info("step_6_network_position")
            results["network_position"] = _step_network_position(conn)
            conn.commit()

            # Step 9: Next best actions
            log.info("step_9_next_actions")
            actions_count = generate_all_next_actions(conn)
            results["next_actions"] = {"generated": actions_count}
            conn.commit()

            # Step 10: Mark stale briefings
            log.info("step_10_stale_briefings")
            stale_count = _step_mark_stale_briefings(conn)
            results["stale_briefings"] = stale_count
            conn.commit()

            # Step 11: Save watermark
            duration_ms = int((time.monotonic() - t0) * 1000)
            total_processed = sum(
                s.get("processed", 0) for s in results.values() if isinstance(s, dict)
            )
            save_watermark(
                conn,
                pipeline_name,
                {"processed": total_processed, "new": 0, "updated": total_processed},
                status="success",
                run_duration_ms=duration_ms,
            )
            conn.commit()

            log.info(
                "delta_pipeline_complete",
                duration_ms=duration_ms,
                results=results,
            )

        except Exception:
            conn.rollback()
            save_watermark(
                conn, pipeline_name,
                {"processed": 0, "new": 0, "updated": 0},
                status="failed",
                error_message=str(Exception),
            )
            conn.commit()
            log.exception("delta_pipeline_failed")
            raise

    return results


if __name__ == "__main__":
    import sys

    full = "--full" in sys.argv
    result = run_delta_pipeline(full_rebuild=full)
    print(result)
