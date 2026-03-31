"""Collection pipeline — orchestrates adapters, aggregator, and persistence."""

from __future__ import annotations

import json
import time
import uuid
from datetime import date, timedelta
from typing import Any

import psycopg
import structlog

from process_collector.adapters import ADAPTER_REGISTRY
from process_collector.aggregator import calculate_process_health_score
from process_collector.config import get_enabled_sources, load_config
from process_collector.models import CollectionStats

logger = structlog.get_logger(__name__)


def _current_week_start() -> date:
    """Return Monday of the current ISO week."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def _ensure_process(
    conn: psycopg.Connection,
    source_name: str,
    source_cfg: dict[str, Any],
) -> str:
    """Ensure a row exists in ``processes`` for this source. Return process_id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT process_id FROM processes WHERE process_name = %(name)s",
            {"name": source_cfg["process_name"]},
        )
        row = cur.fetchone()
        if row:
            return str(row[0])

        pid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO processes (process_id, process_name, process_type, process_category)
            VALUES (%(pid)s, %(name)s, %(ptype)s, %(pcat)s)
            """,
            {
                "pid": pid,
                "name": source_cfg["process_name"],
                "ptype": source_cfg["process_type"],
                "pcat": source_cfg.get("process_category"),
            },
        )
        conn.commit()
        logger.info(
            "process_collector.pipeline.process_created",
            process_id=pid,
            name=source_cfg["process_name"],
        )
        return pid


def _upsert_metrics(
    conn: psycopg.Connection,
    process_id: str,
    week_start: date,
    metrics: dict[str, Any],
    health_score: float,
    health_trend: float | None,
    anomaly_flags: list[str],
    sources_collected: list[str],
    collection_errors: dict | None,
) -> None:
    """UPSERT a row into process_metrics."""
    # Build dynamic SET clause from non-None metric values
    metric_fields = [
        "throughput", "avg_cycle_time_h", "p90_cycle_time_h", "overdue_count",
        "overdue_rate", "error_rate", "rework_rate",
        "velocity_points", "velocity_vs_plan", "bugs_introduced", "blockers_count",
        "wip_count", "lead_time_days", "flow_efficiency",
        "revenue_pln", "deals_closed", "deals_lost", "conversion_rate",
        "avg_deal_size_pln", "avg_sales_cycle_days", "pipeline_value_pln", "quota_attainment",
        "tickets_resolved", "avg_first_response_h", "avg_resolution_h", "escalation_rate",
        "csat_score", "nps_score", "first_contact_resolution_rate",
        "deployments_count", "deployment_failures", "change_failure_rate",
        "mttr_hours", "code_coverage_pct", "critical_bugs_open", "tech_debt_hours",
        "cost_actual_pln", "cost_budget_pln", "budget_variance_pct", "margin_pct", "cost_per_unit",
    ]

    params: dict[str, Any] = {
        "metric_id": str(uuid.uuid4()),
        "process_id": process_id,
        "week_start": week_start,
        "process_health_score": health_score,
        "health_trend": health_trend,
        "anomaly_flags": anomaly_flags,
        "sources_collected": sources_collected,
        "collection_errors": json.dumps(collection_errors) if collection_errors else None,
    }

    # Collect only fields that have values
    active_fields: list[str] = []
    for f in metric_fields:
        val = metrics.get(f)
        if val is not None:
            active_fields.append(f)
            params[f] = val

    all_columns = (
        ["metric_id", "process_id", "week_start"]
        + active_fields
        + ["process_health_score", "health_trend", "anomaly_flags",
           "sources_collected", "collection_errors"]
    )

    col_list = ", ".join(all_columns)
    val_list = ", ".join(f"%({c})s" for c in all_columns)

    # ON CONFLICT update all active fields + health columns
    update_fields = active_fields + [
        "process_health_score", "health_trend", "anomaly_flags",
        "sources_collected", "collection_errors",
    ]
    update_clause = ", ".join(f"{f} = EXCLUDED.{f}" for f in update_fields)
    update_clause += ", collected_at = now()"

    sql = f"""
        INSERT INTO process_metrics ({col_list})
        VALUES ({val_list})
        ON CONFLICT (process_id, week_start)
        DO UPDATE SET {update_clause}
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


def _upsert_participations(
    conn: psycopg.Connection,
    process_id: str,
    week_start: date,
    participations: list[dict[str, Any]],
) -> int:
    """UPSERT rows into process_participations. Return count."""
    if not participations:
        return 0

    count = 0
    for p in participations:
        person_id = p.get("person_id")
        role = p.get("role_in_process", "contributor")
        if not person_id:
            continue

        params = {
            "participation_id": str(uuid.uuid4()),
            "process_id": process_id,
            "person_id": str(person_id),
            "week_start": week_start,
            "role_in_process": role,
            "tasks_owned": p.get("tasks_owned", 0),
            "tasks_contributed": p.get("tasks_contributed", 0),
            "reviews_done": p.get("reviews_done", 0),
            "escalations_caused": p.get("escalations_caused", 0),
            "blockers_caused": p.get("blockers_caused", 0),
            "avg_response_time_h": p.get("avg_response_time_h"),
            "tasks_overdue_owned": p.get("tasks_overdue_owned", 0),
            "ownership_pct": p.get("ownership_pct"),
        }

        sql = """
            INSERT INTO process_participations (
                participation_id, process_id, person_id, week_start,
                role_in_process, tasks_owned, tasks_contributed, reviews_done,
                escalations_caused, blockers_caused, avg_response_time_h,
                tasks_overdue_owned, ownership_pct
            ) VALUES (
                %(participation_id)s, %(process_id)s, %(person_id)s, %(week_start)s,
                %(role_in_process)s, %(tasks_owned)s, %(tasks_contributed)s, %(reviews_done)s,
                %(escalations_caused)s, %(blockers_caused)s, %(avg_response_time_h)s,
                %(tasks_overdue_owned)s, %(ownership_pct)s
            )
            ON CONFLICT (process_id, person_id, week_start)
            DO UPDATE SET
                role_in_process = EXCLUDED.role_in_process,
                tasks_owned = EXCLUDED.tasks_owned,
                tasks_contributed = EXCLUDED.tasks_contributed,
                reviews_done = EXCLUDED.reviews_done,
                escalations_caused = EXCLUDED.escalations_caused,
                blockers_caused = EXCLUDED.blockers_caused,
                avg_response_time_h = EXCLUDED.avg_response_time_h,
                tasks_overdue_owned = EXCLUDED.tasks_overdue_owned,
                ownership_pct = EXCLUDED.ownership_pct
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
        count += 1

    conn.commit()
    return count


def _compute_health_trend(
    conn: psycopg.Connection,
    process_id: str,
    current_score: float,
) -> float | None:
    """Compute trend as difference from previous week's score."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT process_health_score FROM process_metrics
                WHERE process_id = %(pid)s AND process_health_score IS NOT NULL
                ORDER BY week_start DESC LIMIT 1
                """,
                {"pid": process_id},
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return round(current_score - row[0], 2)
    except Exception as exc:
        logger.warning("process_collector.pipeline.trend_error", error=str(exc))
    return None


def _save_watermark(
    conn: psycopg.Connection,
    source_name: str,
    week_start: date,
) -> None:
    """Save collection watermark to pipeline_state."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_state (pipeline_name, last_value, updated_at)
                VALUES (%(name)s, %(val)s, now())
                ON CONFLICT (pipeline_name)
                DO UPDATE SET last_value = EXCLUDED.last_value, updated_at = now()
                """,
                {
                    "name": f"process_collector:{source_name}",
                    "val": str(week_start),
                },
            )
        conn.commit()
    except Exception as exc:
        logger.warning(
            "process_collector.pipeline.watermark_error",
            source=source_name,
            error=str(exc),
        )


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

def run_collection(
    conn: psycopg.Connection,
    source_names: list[str] | None = None,
    config_path: str | None = None,
    dry_run: bool = False,
    week_start: date | None = None,
) -> list[CollectionStats]:
    """Run the full collection pipeline.

    Args:
        conn: database connection.
        source_names: optional list of source names to collect. None = all enabled.
        config_path: path to YAML config. None = default.
        dry_run: if True, collect but do not persist.
        week_start: override week start date (default: current Monday).

    Returns:
        list of CollectionStats for each source processed.
    """
    config = load_config(config_path)
    enabled = get_enabled_sources(config)

    if source_names:
        enabled = {k: v for k, v in enabled.items() if k in source_names}

    if not enabled:
        logger.warning("process_collector.pipeline.no_sources")
        return []

    ws = week_start or _current_week_start()
    results: list[CollectionStats] = []

    for source_name, source_cfg in enabled.items():
        t0 = time.monotonic()
        adapter_type = source_cfg.get("adapter", "generic_sql")
        adapter_cls = ADAPTER_REGISTRY.get(adapter_type)

        if adapter_cls is None:
            logger.error(
                "process_collector.pipeline.unknown_adapter",
                adapter=adapter_type,
                source=source_name,
            )
            results.append(
                CollectionStats(
                    source_name=source_name,
                    process_id=uuid.UUID(int=0),
                    week_start=ws,
                    errors=[f"Unknown adapter: {adapter_type}"],
                )
            )
            continue

        stats = CollectionStats(
            source_name=source_name,
            process_id=uuid.UUID(int=0),
            week_start=ws,
        )

        try:
            # Ensure process row
            process_id = _ensure_process(conn, source_name, source_cfg)
            stats.process_id = uuid.UUID(process_id)

            # Instantiate adapter
            adapter = adapter_cls(source_cfg)

            # Collect metrics
            metrics = adapter.collect_metrics(process_id, ws, conn)
            stats.metrics_collected = len([v for v in metrics.values() if v is not None])

            # Collect participations
            participations = adapter.collect_participations(process_id, ws, conn)
            stats.participations_collected = len(participations)

            # Health score
            health_score, anomaly_flags = calculate_process_health_score(
                metrics,
                source_cfg["process_type"],
                conn,
                process_id=process_id,
            )
            stats.health_score = health_score
            stats.anomaly_flags = anomaly_flags

            if not dry_run:
                # Health trend
                trend = _compute_health_trend(conn, process_id, health_score)

                # Persist
                _upsert_metrics(
                    conn, process_id, ws, metrics,
                    health_score, trend, anomaly_flags,
                    sources_collected=[source_name],
                    collection_errors=None,
                )
                _upsert_participations(conn, process_id, ws, participations)
                _save_watermark(conn, source_name, ws)

                logger.info(
                    "process_collector.pipeline.source_done",
                    source=source_name,
                    process_id=process_id,
                    metrics=stats.metrics_collected,
                    participations=stats.participations_collected,
                    health=round(health_score, 2),
                    anomalies=anomaly_flags,
                )
            else:
                logger.info(
                    "process_collector.pipeline.dry_run",
                    source=source_name,
                    metrics=stats.metrics_collected,
                    participations=stats.participations_collected,
                    health=round(health_score, 2),
                )

        except Exception as exc:
            stats.errors.append(str(exc))
            logger.error(
                "process_collector.pipeline.source_error",
                source=source_name,
                error=str(exc),
                exc_info=True,
            )

        stats.duration_seconds = round(time.monotonic() - t0, 3)
        results.append(stats)

    return results
