"""
Strategic Goal Tracker — links operations to strategy.

Define strategic goals -> KPI -> auto-track progress -> risks -> dependencies.

Example:
  Goal: "REH przychod > 50M PLN do Q4 2026"
  KPI: revenue_monthly from financial_metrics
  Current: 38M (76%)
  Trend: +2.1M/msc (on track)
  Risk: "utrata Tauron = -8M/rok"
  Sub-goals: NOFAR (w toku), 2 nowi klienci OZE (1/2)

Integrates with: morning brief, weekly synthesis, financial framework
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

RISK_ANALYSIS_PROMPT = """You analyze strategic goal risks for a business leader.

Given a goal with its progress data, dependencies, and recent events, identify:
1. Key risks that could prevent achieving this goal
2. Impact severity (high/medium/low)
3. Suggested mitigation actions

Be concise and specific. Write in Polish.
Respond ONLY with a JSON array:
[{"risk": "...", "impact": "high|medium|low", "mitigation": "..."}]"""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _ensure_tables() -> None:
    """Create strategic goal tables if they don't exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS strategic_goals (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    company TEXT,
                    area TEXT DEFAULT 'business'
                        CHECK (area IN ('business', 'trading', 'operations', 'people', 'technology', 'wellbeing')),
                    target_value NUMERIC,
                    current_value NUMERIC DEFAULT 0,
                    unit TEXT DEFAULT 'PLN',
                    deadline DATE,
                    status TEXT DEFAULT 'on_track'
                        CHECK (status IN ('on_track', 'at_risk', 'behind', 'achieved', 'cancelled')),
                    parent_goal_id BIGINT REFERENCES strategic_goals(id),
                    metric_source TEXT,
                    risk_factors TEXT[],
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS goal_progress (
                    id BIGSERIAL PRIMARY KEY,
                    goal_id BIGINT NOT NULL REFERENCES strategic_goals(id),
                    date DATE NOT NULL,
                    value NUMERIC NOT NULL,
                    note TEXT,
                    auto_detected BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(goal_id, date)
                );

                CREATE TABLE IF NOT EXISTS goal_dependencies (
                    id BIGSERIAL PRIMARY KEY,
                    goal_id BIGINT NOT NULL REFERENCES strategic_goals(id),
                    dependency_type TEXT NOT NULL
                        CHECK (dependency_type IN ('commitment', 'contract', 'person', 'goal', 'milestone')),
                    dependency_description TEXT NOT NULL,
                    dependency_ref_id BIGINT,
                    status TEXT DEFAULT 'pending'
                        CHECK (status IN ('pending', 'met', 'blocked', 'at_risk')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_goals_status ON strategic_goals(status);
                CREATE INDEX IF NOT EXISTS idx_goals_company ON strategic_goals(company);
                CREATE INDEX IF NOT EXISTS idx_goal_progress_goal ON goal_progress(goal_id);
                CREATE INDEX IF NOT EXISTS idx_goal_deps_goal ON goal_dependencies(goal_id);
            """)
        conn.commit()
    log.info("strategic_goals.tables_ensured")


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def create_goal(
    title: str,
    target_value: float,
    unit: str = "PLN",
    deadline: str | None = None,
    company: str | None = None,
    area: str = "business",
    description: str | None = None,
    parent_goal_id: int | None = None,
    metric_source: str | None = None,
) -> dict:
    """Create a strategic goal. Returns goal dict with ID."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategic_goals
                    (title, description, company, area, target_value, unit, deadline,
                     parent_goal_id, metric_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, target_value, unit, deadline, status, created_at
                """,
                (title, description, company, area, target_value, unit, deadline,
                 parent_goal_id, metric_source),
            )
            row = cur.fetchone()
        conn.commit()

    result = {
        "id": row[0],
        "title": row[1],
        "target_value": float(row[2]) if row[2] else None,
        "unit": row[3],
        "deadline": str(row[4]) if row[4] else None,
        "status": row[5],
        "created_at": str(row[6]),
    }
    log.info("strategic_goal.created", goal_id=result["id"], title=title)
    return result


def update_goal_progress(
    goal_id: int, value: float, note: str | None = None, auto_detected: bool = False
) -> dict:
    """Record progress for a goal. Update current_value and recalculate status."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Upsert progress entry
            cur.execute(
                """
                INSERT INTO goal_progress (goal_id, date, value, note, auto_detected)
                VALUES (%s, CURRENT_DATE, %s, %s, %s)
                ON CONFLICT (goal_id, date) DO UPDATE
                    SET value = EXCLUDED.value, note = EXCLUDED.note,
                        auto_detected = EXCLUDED.auto_detected
                RETURNING id, date
                """,
                (goal_id, value, note, auto_detected),
            )
            progress_row = cur.fetchone()

            # Update current_value on the goal
            cur.execute(
                "UPDATE strategic_goals SET current_value = %s, updated_at = NOW() WHERE id = %s",
                (value, goal_id),
            )

            # Get goal details for status calculation
            cur.execute(
                """
                SELECT target_value, deadline, status, created_at
                FROM strategic_goals WHERE id = %s
                """,
                (goal_id,),
            )
            goal = cur.fetchone()
            if not goal:
                conn.rollback()
                return {"error": f"Goal {goal_id} not found"}

            target_value, deadline, old_status, created_at = goal

            # Recalculate status
            new_status = _calculate_status(
                cur, goal_id, value, float(target_value) if target_value else 0,
                deadline, created_at,
            )

            if new_status != old_status:
                cur.execute(
                    "UPDATE strategic_goals SET status = %s, updated_at = NOW() WHERE id = %s",
                    (new_status, goal_id),
                )
        conn.commit()

    result = {
        "goal_id": goal_id,
        "progress_id": progress_row[0],
        "date": str(progress_row[1]),
        "value": value,
        "status": new_status,
        "status_changed": new_status != old_status,
    }
    log.info("strategic_goal.progress_updated", **result)
    return result


def _calculate_status(
    cur, goal_id: int, current: float, target: float, deadline, created_at
) -> str:
    """Calculate goal status based on progress trend."""
    if target and current >= target:
        return "achieved"

    if not target or not deadline:
        return "on_track"

    # Get progress history for trend analysis
    cur.execute(
        """
        SELECT date, value FROM goal_progress
        WHERE goal_id = %s ORDER BY date ASC
        """,
        (goal_id,),
    )
    history = cur.fetchall()

    if len(history) < 2:
        return "on_track"

    # Simple linear projection
    first_date, first_val = history[0]
    last_date, last_val = history[-1]
    days_elapsed = (last_date - first_date).days
    if days_elapsed <= 0:
        return "on_track"

    daily_rate = (float(last_val) - float(first_val)) / days_elapsed
    today = datetime.now(timezone.utc).date()
    days_remaining = (deadline - today).days

    if days_remaining <= 0:
        return "behind" if current < target else "achieved"

    projected = float(current) + daily_rate * days_remaining
    completion_pct = projected / target if target else 0

    if completion_pct >= 1.0:
        return "on_track"
    elif completion_pct >= 0.8:
        return "at_risk"
    else:
        return "behind"


def auto_update_from_metrics() -> list[dict]:
    """For goals with metric_source, auto-pull values from known sources."""
    _ensure_tables()
    updates = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, metric_source, company
                FROM strategic_goals
                WHERE metric_source IS NOT NULL
                  AND status NOT IN ('achieved', 'cancelled')
                """
            )
            goals = cur.fetchall()

    for goal_id, title, metric_source, company in goals:
        try:
            value = _fetch_metric_value(metric_source, company)
            if value is not None:
                result = update_goal_progress(
                    goal_id, value,
                    note=f"Auto-updated from {metric_source}",
                    auto_detected=True,
                )
                updates.append(result)
        except Exception:
            log.warning("strategic_goal.auto_update_failed",
                        goal_id=goal_id, metric_source=metric_source, exc_info=True)

    log.info("strategic_goals.auto_update_complete", updated=len(updates))
    return updates


def _fetch_metric_value(metric_source: str, company: str | None) -> float | None:
    """Fetch latest metric value from various sources."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # financial_metrics: e.g. "financial_metrics:revenue_monthly"
            if metric_source.startswith("financial_metrics:"):
                metric_type = metric_source.split(":", 1)[1]
                params: list[Any] = [metric_type]
                sql = """
                    SELECT value FROM financial_metrics
                    WHERE metric_type = %s
                """
                if company:
                    sql += " AND company = %s"
                    params.append(company)
                sql += " ORDER BY period_end DESC LIMIT 1"
                cur.execute(sql, params)

            # DB counts: e.g. "db_count:chunks" or "db_count:entities"
            elif metric_source.startswith("db_count:"):
                table_name = metric_source.split(":", 1)[1]
                # Whitelist allowed tables to prevent SQL injection
                allowed = {"chunks", "entities", "events", "insights", "commitments", "decisions"}
                if table_name not in allowed:
                    return None
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608 — table is whitelisted

            # Commitment completion rate
            elif metric_source == "commitment_rate":
                cur.execute("""
                    SELECT
                        CASE WHEN COUNT(*) = 0 THEN 0
                        ELSE COUNT(*) FILTER (WHERE status = 'fulfilled')::NUMERIC / COUNT(*)
                        END
                    FROM commitments
                    WHERE updated_at > NOW() - INTERVAL '30 days'
                """)

            else:
                log.warning("strategic_goal.unknown_metric_source", source=metric_source)
                return None

            row = cur.fetchone()
            return float(row[0]) if row and row[0] is not None else None


def get_goal_tree(goal_id: int | None = None) -> dict | list[dict]:
    """Return goal(s) with sub-goals, dependencies, and progress history.
    If goal_id is None, return all top-level goals."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if goal_id:
                cur.execute(
                    """
                    SELECT id, title, description, company, area, target_value,
                           current_value, unit, deadline, status, parent_goal_id,
                           metric_source, risk_factors, created_at, updated_at
                    FROM strategic_goals WHERE id = %s
                    """,
                    (goal_id,),
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT id, title, description, company, area, target_value,
                           current_value, unit, deadline, status, parent_goal_id,
                           metric_source, risk_factors, created_at, updated_at
                    FROM strategic_goals WHERE parent_goal_id IS NULL
                    ORDER BY deadline ASC NULLS LAST
                    """
                )
                rows = cur.fetchall()

            goals = []
            for r in rows:
                g = _row_to_goal_dict(r)

                # Sub-goals
                cur.execute(
                    """
                    SELECT id, title, description, company, area, target_value,
                           current_value, unit, deadline, status, parent_goal_id,
                           metric_source, risk_factors, created_at, updated_at
                    FROM strategic_goals WHERE parent_goal_id = %s
                    ORDER BY deadline ASC NULLS LAST
                    """,
                    (g["id"],),
                )
                g["sub_goals"] = [_row_to_goal_dict(sr) for sr in cur.fetchall()]

                # Dependencies
                cur.execute(
                    """
                    SELECT id, dependency_type, dependency_description,
                           dependency_ref_id, status
                    FROM goal_dependencies WHERE goal_id = %s
                    """,
                    (g["id"],),
                )
                g["dependencies"] = [
                    {
                        "id": d[0], "type": d[1], "description": d[2],
                        "ref_id": d[3], "status": d[4],
                    }
                    for d in cur.fetchall()
                ]

                # Progress history (last 30 entries)
                cur.execute(
                    """
                    SELECT date, value, note, auto_detected
                    FROM goal_progress WHERE goal_id = %s
                    ORDER BY date DESC LIMIT 30
                    """,
                    (g["id"],),
                )
                g["progress"] = [
                    {"date": str(p[0]), "value": float(p[1]), "note": p[2], "auto": p[3]}
                    for p in cur.fetchall()
                ]

                # Completion percentage
                if g["target_value"] and g["target_value"] > 0:
                    g["pct_complete"] = round(
                        (float(g["current_value"] or 0) / float(g["target_value"])) * 100, 1
                    )
                else:
                    g["pct_complete"] = None

                goals.append(g)

    if goal_id:
        return goals[0] if goals else {"error": f"Goal {goal_id} not found"}
    return goals


def _row_to_goal_dict(r) -> dict:
    """Convert a goal row tuple to dict."""
    return {
        "id": r[0],
        "title": r[1],
        "description": r[2],
        "company": r[3],
        "area": r[4],
        "target_value": float(r[5]) if r[5] is not None else None,
        "current_value": float(r[6]) if r[6] is not None else None,
        "unit": r[7],
        "deadline": str(r[8]) if r[8] else None,
        "status": r[9],
        "parent_goal_id": r[10],
        "metric_source": r[11],
        "risk_factors": r[12],
        "created_at": str(r[13]),
        "updated_at": str(r[14]),
    }


def analyze_goal_risks() -> list[dict]:
    """For each active goal, analyze risks from dependencies, trends, and events."""
    _ensure_tables()
    results = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, description, company, target_value, current_value,
                       unit, deadline, status
                FROM strategic_goals
                WHERE status NOT IN ('achieved', 'cancelled')
                ORDER BY deadline ASC NULLS LAST
                """
            )
            goals = cur.fetchall()

    for goal_row in goals:
        goal_id = goal_row[0]
        goal_title = goal_row[1]
        goal_risks = []

        # Check blocked dependencies
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT dependency_description, status
                        FROM goal_dependencies
                        WHERE goal_id = %s AND status IN ('blocked', 'at_risk')
                        """,
                        (goal_id,),
                    )
                    blocked = cur.fetchall()
                    for dep_desc, dep_status in blocked:
                        goal_risks.append({
                            "risk": f"Zablokowana zaleznosc: {dep_desc}",
                            "impact": "high",
                            "source": "dependency",
                        })
        except Exception:
            log.warning("goal_risk.dependency_check_failed", goal_id=goal_id, exc_info=True)

        # Check overdue commitments related to goal company
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    company = goal_row[3]
                    if company:
                        cur.execute(
                            """
                            SELECT COUNT(*) FROM commitments
                            WHERE status = 'overdue'
                              AND commitment_text ILIKE %s
                            """,
                            (f"%{company}%",),
                        )
                        overdue = cur.fetchone()[0]
                        if overdue > 0:
                            goal_risks.append({
                                "risk": f"{overdue} przeterminowanych zobowiazan dla {company}",
                                "impact": "medium",
                                "source": "commitments",
                            })
        except Exception:
            log.warning("goal_risk.commitment_check_failed", goal_id=goal_id, exc_info=True)

        # LLM risk analysis for goals with enough context
        if goal_row[4] and goal_row[5]:  # target and current values exist
            try:
                llm_risks = _llm_risk_analysis(goal_row)
                goal_risks.extend(llm_risks)
            except Exception:
                log.warning("goal_risk.llm_analysis_failed", goal_id=goal_id, exc_info=True)

        results.append({
            "goal_id": goal_id,
            "goal_title": goal_title,
            "status": goal_row[8],
            "risks": goal_risks,
            "risk_count": len(goal_risks),
        })

    log.info("strategic_goals.risk_analysis_complete", goals=len(results),
             total_risks=sum(r["risk_count"] for r in results))
    return results


def _llm_risk_analysis(goal_row) -> list[dict]:
    """Use LLM to analyze risks for a specific goal."""
    goal_id, title, description, company, target, current, unit, deadline, status = goal_row
    pct = round((float(current) / float(target)) * 100, 1) if target else 0

    # Get recent events related to goal company
    recent_events = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                if company:
                    cur.execute(
                        """
                        SELECT event_type, summary, event_date
                        FROM events
                        WHERE summary ILIKE %s
                          AND created_at > NOW() - INTERVAL '14 days'
                        ORDER BY event_date DESC LIMIT 10
                        """,
                        (f"%{company}%",),
                    )
                    recent_events = [
                        {"type": r[0], "summary": r[1], "date": str(r[2])}
                        for r in cur.fetchall()
                    ]
    except Exception:
        pass

    prompt = f"""Cel: {title}
Opis: {description or 'brak'}
Firma: {company or 'brak'}
Postep: {current}/{target} {unit} ({pct}%)
Deadline: {deadline}
Status: {status}

Ostatnie zdarzenia:
{json.dumps(recent_events, ensure_ascii=False, indent=2) if recent_events else 'brak danych'}

Zidentyfikuj 1-3 kluczowe ryzyka."""

    resp = client.messages.create(
        model=ANTHROPIC_FAST,
        max_tokens=500,
        system=RISK_ANALYSIS_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    log_anthropic_cost(ANTHROPIC_FAST, "strategic_goals", resp.usage)

    text = resp.content[0].text.strip()
    try:
        risks = json.loads(text)
        if isinstance(risks, list):
            for r in risks:
                r["source"] = "llm"
            return risks
    except (json.JSONDecodeError, ValueError):
        log.warning("goal_risk.llm_parse_failed", goal_id=goal_id, response=text[:200])
    return []


def get_goals_summary() -> dict:
    """Return overall goals summary for briefs and dashboards."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total and by status
            cur.execute(
                """
                SELECT status, COUNT(*) FROM strategic_goals
                WHERE status != 'cancelled'
                GROUP BY status
                """
            )
            by_status = {r[0]: r[1] for r in cur.fetchall()}
            total = sum(by_status.values())

            # By area
            cur.execute(
                """
                SELECT area, COUNT(*) FROM strategic_goals
                WHERE status NOT IN ('achieved', 'cancelled')
                GROUP BY area
                """
            )
            by_area = {r[0]: r[1] for r in cur.fetchall()}

            # Recently achieved (last 30 days)
            cur.execute(
                """
                SELECT title, updated_at::date
                FROM strategic_goals
                WHERE status = 'achieved'
                  AND updated_at > NOW() - INTERVAL '30 days'
                ORDER BY updated_at DESC
                """
            )
            recently_achieved = [
                {"goal": r[0], "achieved_date": str(r[1])} for r in cur.fetchall()
            ]

            # Upcoming deadlines (next 30 days)
            cur.execute(
                """
                SELECT title, deadline, current_value, target_value
                FROM strategic_goals
                WHERE status NOT IN ('achieved', 'cancelled')
                  AND deadline IS NOT NULL
                  AND deadline BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
                ORDER BY deadline ASC
                """
            )
            upcoming = []
            for r in cur.fetchall():
                pct = round((float(r[2] or 0) / float(r[3])) * 100, 1) if r[3] else None
                upcoming.append({
                    "goal": r[0],
                    "deadline": str(r[1]),
                    "pct_complete": pct,
                })

            # Top risks (at_risk and behind goals)
            cur.execute(
                """
                SELECT title, status, risk_factors, deadline
                FROM strategic_goals
                WHERE status IN ('at_risk', 'behind')
                ORDER BY deadline ASC NULLS LAST
                LIMIT 5
                """
            )
            top_risks = [
                {
                    "goal": r[0],
                    "status": r[1],
                    "risk": r[2][0] if r[2] else "trend negatywny",
                    "deadline": str(r[3]) if r[3] else None,
                }
                for r in cur.fetchall()
            ]

    return {
        "total_goals": total,
        "by_status": by_status,
        "by_area": by_area,
        "top_risks": top_risks,
        "recently_achieved": recently_achieved,
        "upcoming_deadlines": upcoming,
    }


def run_goal_tracking() -> dict:
    """Main pipeline: auto-update from metrics -> analyze risks -> summary."""
    _ensure_tables()
    log.info("strategic_goals.tracking_start")

    auto_updates = auto_update_from_metrics()
    risks = analyze_goal_risks()
    summary = get_goals_summary()

    # Update risk_factors on goals that have risks
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for r in risks:
                    if r["risks"]:
                        risk_texts = [risk["risk"] for risk in r["risks"][:5]]
                        cur.execute(
                            """
                            UPDATE strategic_goals
                            SET risk_factors = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (risk_texts, r["goal_id"]),
                        )
            conn.commit()
    except Exception:
        log.warning("strategic_goals.risk_update_failed", exc_info=True)

    result = {
        "auto_updates": len(auto_updates),
        "goals_with_risks": sum(1 for r in risks if r["risks"]),
        "total_risks": sum(r["risk_count"] for r in risks),
        "summary": summary,
        "risk_details": risks,
    }
    log.info("strategic_goals.tracking_complete", **{k: v for k, v in result.items() if k != "risk_details"})
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--create" in sys.argv:
        args: dict[str, Any] = {}
        for i, a in enumerate(sys.argv):
            if a == "--create":
                args["title"] = sys.argv[i + 1]
            elif a == "--target":
                args["target_value"] = float(sys.argv[i + 1])
            elif a == "--unit":
                args["unit"] = sys.argv[i + 1]
            elif a == "--deadline":
                args["deadline"] = sys.argv[i + 1]
            elif a == "--company":
                args["company"] = sys.argv[i + 1]
            elif a == "--area":
                args["area"] = sys.argv[i + 1]
        result = create_goal(**args)
    elif "--risks" in sys.argv:
        result = analyze_goal_risks()
    elif "--summary" in sys.argv:
        result = get_goals_summary()
    elif "--tree" in sys.argv:
        gid = None
        idx = sys.argv.index("--tree")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
            gid = int(sys.argv[idx + 1])
        result = get_goal_tree(gid)
    else:
        result = run_goal_tracking()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
