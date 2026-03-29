"""ROI Reporter — generates and persists ROI summaries."""
from __future__ import annotations

from datetime import date, timedelta

import structlog
from app.db.postgres import get_pg_connection
from app.analysis.roi.synergy_calculator import calculate_synergy

log = structlog.get_logger(__name__)


def generate_roi_summary(
    entity_id: int,
    period_start: date,
    period_end: date,
    domain: str | None = None,
) -> dict:
    """
    Generate (or refresh) an ROI summary for an entity over a period.
    Persists to roi_summaries via upsert.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Activities breakdown
            domain_filter = "AND domain = %s" if domain else ""
            params: list = [entity_id, str(period_start), str(period_end)]
            if domain:
                params.append(domain)

            cur.execute(
                f"""
                SELECT domain, activity_type,
                       COUNT(*) as count,
                       SUM(value_pln) as total_value,
                       SUM(time_saved_min) as total_minutes
                FROM roi_activities
                WHERE entity_id = %s
                  AND created_at >= %s AND created_at < %s
                  {domain_filter}
                GROUP BY domain, activity_type
                ORDER BY total_value DESC
                """,
                params,
            )
            rows = cur.fetchall()

            breakdown = {}
            total_value = 0.0
            total_minutes = 0

            for d, atype, count, val, minutes in rows:
                if d not in breakdown:
                    breakdown[d] = {"activities": [], "subtotal_pln": 0, "subtotal_minutes": 0}
                breakdown[d]["activities"].append({
                    "type": atype,
                    "count": count,
                    "value_pln": float(val or 0),
                    "time_saved_min": int(minutes or 0),
                })
                breakdown[d]["subtotal_pln"] += float(val or 0)
                breakdown[d]["subtotal_minutes"] += int(minutes or 0)
                total_value += float(val or 0)
                total_minutes += int(minutes or 0)

            # Round subtotals
            for d in breakdown:
                breakdown[d]["subtotal_pln"] = round(breakdown[d]["subtotal_pln"], 2)

            # Synergy
            synergy = calculate_synergy(str(period_start), str(period_end))
            synergy_bonus = synergy["total_bonus_pln"]

            # Upsert summary
            cur.execute(
                """
                INSERT INTO roi_summaries (entity_id, period_start, period_end, domain, total_value_pln, synergy_bonus_pln, breakdown)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (entity_id, period_start, period_end, domain)
                DO UPDATE SET total_value_pln = EXCLUDED.total_value_pln,
                              synergy_bonus_pln = EXCLUDED.synergy_bonus_pln,
                              breakdown = EXCLUDED.breakdown,
                              created_at = NOW()
                RETURNING id
                """,
                (entity_id, period_start, period_end, domain,
                 round(total_value, 2), round(synergy_bonus, 2),
                 _to_json(breakdown)),
            )
            summary_id = cur.fetchone()[0]
            conn.commit()

    result = {
        "id": summary_id,
        "entity_id": entity_id,
        "period_start": str(period_start),
        "period_end": str(period_end),
        "domain": domain,
        "total_value_pln": round(total_value, 2),
        "synergy_bonus_pln": round(synergy_bonus, 2),
        "grand_total_pln": round(total_value + synergy_bonus, 2),
        "total_time_saved_min": total_minutes,
        "total_time_saved_hours": round(total_minutes / 60, 1),
        "breakdown": breakdown,
        "synergy_details": synergy["details"],
    }

    log.info(
        "roi_summary_generated",
        entity_id=entity_id,
        period=f"{period_start}/{period_end}",
        total_pln=result["grand_total_pln"],
    )
    return result


def get_roi_report(
    entity_id: int | None = None,
    domain: str | None = None,
    period: str = "week",
) -> dict:
    """
    Get ROI report. If entity_id is None, returns owner's report.
    period: 'week', 'month', or 'quarter'
    """
    today = date.today()

    if period == "week":
        period_start = today - timedelta(days=today.weekday())  # Monday
        period_end = period_start + timedelta(days=7)
    elif period == "month":
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1)
    elif period == "quarter":
        q = (today.month - 1) // 3
        period_start = today.replace(month=q * 3 + 1, day=1)
        period_end = today.replace(month=q * 3 + 4, day=1) if q < 3 else today.replace(year=today.year + 1, month=1, day=1)
    else:
        period_start = today - timedelta(days=7)
        period_end = today

    if entity_id is None:
        from app.analysis.roi.hierarchy import get_owner_entity
        owner = get_owner_entity()
        if not owner:
            return {"error": "No owner entity found"}
        entity_id = owner["id"]

    return generate_roi_summary(entity_id, period_start, period_end, domain)


def get_leaderboard(period: str = "week", limit: int = 10) -> list[dict]:
    """Rank all entities by ROI value for a period."""
    today = date.today()
    if period == "week":
        period_start = today - timedelta(days=today.weekday())
        period_end = period_start + timedelta(days=7)
    else:
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.id, h.name, h.type,
                       COALESCE(SUM(a.value_pln), 0) as total_value,
                       COALESCE(SUM(a.time_saved_min), 0) as total_minutes,
                       COUNT(a.id) as activity_count
                FROM roi_hierarchy h
                LEFT JOIN roi_activities a ON a.entity_id = h.id
                  AND a.created_at >= %s AND a.created_at < %s
                GROUP BY h.id, h.name, h.type
                ORDER BY total_value DESC
                LIMIT %s
                """,
                (str(period_start), str(period_end), limit),
            )
            results = []
            for row in cur.fetchall():
                results.append({
                    "entity_id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "total_value_pln": float(row[3]),
                    "total_time_saved_min": int(row[4]),
                    "activity_count": row[5],
                })
            return results


def _to_json(obj: dict) -> str:
    import json
    return json.dumps(obj, default=str, ensure_ascii=False)
