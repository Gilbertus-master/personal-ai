"""ROI Activity Tracker — auto-detects value-generating activities from existing tables."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from app.db.postgres import get_pg_connection
from app.analysis.roi.hierarchy import get_owner_entity
from app.analysis.roi.value_mapper import map_activity_value, get_domain_for_activity

log = structlog.get_logger(__name__)


def scan_and_record_activities(since: datetime | None = None) -> dict:
    """
    Scan existing tables for new activities and record them in roi_activities.
    Skips already-recorded activities (by source_table + source_id).

    Returns: {"total_new": int, "by_type": {type: count}}
    """
    owner = get_owner_entity()
    if not owner:
        log.error("roi_no_owner", msg="No owner entity in roi_hierarchy — run migration first")
        return {"total_new": 0, "by_type": {}}

    if since is None:
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)

    stats: dict[str, int] = {}

    scanners = [
        _scan_ask_runs,
        _scan_decisions,
        _scan_action_items,
        _scan_code_review_findings,
        _scan_documents,
        _scan_meeting_minutes,
        _scan_communications,
    ]

    for scanner in scanners:
        try:
            count = scanner(owner, since)
            if count > 0:
                stats[scanner.__name__.replace("_scan_", "")] = count
        except Exception:
            log.exception("roi_scan_error", scanner=scanner.__name__)

    total = sum(stats.values())
    log.info("roi_scan_complete", total_new=total, by_type=stats)
    return {"total_new": total, "by_type": stats}


def _already_recorded(cur, source_table: str, source_id: int) -> bool:
    cur.execute(
        "SELECT 1 FROM roi_activities WHERE source_table = %s AND source_id = %s LIMIT 1",
        (source_table, source_id),
    )
    return cur.fetchone() is not None


def _insert_activity(
    cur,
    entity_id: int,
    activity_type: str,
    domain: str,
    value_pln: float,
    time_saved_min: int,
    description: str,
    source_table: str,
    source_id: int,
    created_at: datetime | None = None,
) -> None:
    cur.execute(
        "INSERT INTO roi_activities "
        "(entity_id, activity_type, domain, value_pln, time_saved_min, description, source_table, source_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (entity_id, activity_type, domain, value_pln, time_saved_min, description, source_table, source_id,
         created_at or datetime.now(timezone.utc)),
    )


def _run_scanner(
    owner: dict,
    since: datetime,
    sql: str,
    source_table: str,
    activity_type: str,
    extract_row,
    domain: str,
    table_to_check: str | None = None,
) -> int:
    """Generic scanner: query rows, dedup, insert, commit. Returns count of new activities."""
    count = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if table_to_check:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=%s)",
                    (table_to_check,),
                )
                if not cur.fetchall()[0][0]:
                    return 0
            cur.execute(sql, (since,))
            for row in cur.fetchall():
                rid, desc_text, created_at, value_kwargs = extract_row(row)
                if _already_recorded(cur, source_table, rid):
                    continue
                value_pln, time_min = map_activity_value(activity_type, owner, **value_kwargs)
                _insert_activity(cur, owner["id"], activity_type, domain, value_pln, time_min, (desc_text or "")[:200], source_table, rid, created_at)
                count += 1
            conn.commit()
    return count


def _scan_ask_runs(owner: dict, since: datetime) -> int:
    """Each ask_run = query answered."""
    return _run_scanner(
        owner, since,
        "SELECT id, query_text, created_at FROM ask_runs WHERE created_at >= %s ORDER BY id",
        "ask_runs", "query_answered",
        lambda row: (row[0], row[1], row[2], {}),
        get_domain_for_activity("query_answered", owner),
    )


def _scan_decisions(owner: dict, since: datetime) -> int:
    """Each decision = management ROI."""
    return _run_scanner(
        owner, since,
        "SELECT id, decision_text, created_at FROM decisions WHERE created_at >= %s ORDER BY id",
        "decisions", "decision_made",
        lambda row: (row[0], row[1], row[2], {}),
        get_domain_for_activity("decision_made", owner),
    )


def _scan_action_items(owner: dict, since: datetime) -> int:
    """Executed action items = management ROI."""
    return _run_scanner(
        owner, since,
        "SELECT id, description, executed_at FROM action_items "
        "WHERE status = 'executed' AND executed_at IS NOT NULL AND proposed_at >= %s ORDER BY id",
        "action_items", "action_executed",
        lambda row: (row[0], row[1], row[2], {}),
        get_domain_for_activity("action_executed", owner),
    )


def _scan_code_review_findings(owner: dict, since: datetime) -> int:
    """Resolved code findings = builder ROI."""
    return _run_scanner(
        owner, since,
        "SELECT id, description, severity, resolved_at FROM code_review_findings "
        "WHERE status = 'resolved' AND resolved_at >= %s ORDER BY id",
        "code_review_findings", "code_fix",
        lambda row: (row[0], row[1], row[3], {"severity": row[2]}),
        "builder",
        table_to_check="code_review_findings",
    )


def _scan_documents(owner: dict, since: datetime) -> int:
    """New documents ingested = builder ROI (knowledge base growth)."""
    return _run_scanner(
        owner, since,
        "SELECT id, title, created_at FROM documents WHERE created_at >= %s ORDER BY id",
        "documents", "knowledge_added",
        lambda row: (row[0], row[1], row[2], {}),
        "builder",
    )


def _scan_meeting_minutes(owner: dict, since: datetime) -> int:
    """Productive meetings (with ROI score) = management ROI."""
    return _run_scanner(
        owner, since,
        "SELECT id, title, meeting_roi_score, created_at FROM meeting_minutes "
        "WHERE meeting_roi_score IS NOT NULL AND created_at >= %s ORDER BY id",
        "meeting_minutes", "meeting_productive",
        lambda row: (row[0], row[1], row[3], {"meeting_roi_score": float(row[2])}),
        "management",
    )


def _scan_communications(owner: dict, since: datetime) -> int:
    """Sent communications = management ROI."""
    return _run_scanner(
        owner, since,
        "SELECT id, subject, sent_at FROM sent_communications WHERE sent_at >= %s ORDER BY id",
        "sent_communications", "communication_sent",
        lambda row: (row[0], row[1], row[2], {}),
        "management",
        table_to_check="sent_communications",
    )
