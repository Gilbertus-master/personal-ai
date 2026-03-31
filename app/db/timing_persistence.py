"""Persist per-request stage timing data to PostgreSQL."""
from __future__ import annotations
import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("timing_persistence")


def save_timing(
    *,
    request_id: str | None = None,
    question_type: str | None = None,
    analysis_depth: str | None = None,
    used_fallback: bool = False,
    retrieved_count: int | None = None,
    total_ms: int | None = None,
    interpret_ms: int | None = None,
    retrieve_ms: int | None = None,
    answer_ms: int | None = None,
    channel: str | None = None,
    model_used: str | None = None,
) -> None:
    """Save timing data synchronously. Errors are caught and logged as warnings — never re-raised, so callers are not affected by DB failures."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO query_stage_times
                    (request_id, question_type, analysis_depth, used_fallback,
                     retrieved_count, total_ms, interpret_ms, retrieve_ms,
                     answer_ms, channel, model_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    request_id, question_type, analysis_depth, used_fallback,
                    retrieved_count, total_ms, interpret_ms, retrieve_ms,
                    answer_ms, channel, model_used,
                ))
            conn.commit()
    except Exception as e:
        log.warning("timing_persistence.failed", error=str(e), request_id=request_id, exc_info=True)
