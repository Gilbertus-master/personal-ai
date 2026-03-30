"""
Financial Data Framework — gives Gilbertus financial awareness.

Phase 1 (now): Manual KPI input per company, budget tracking, API cost summary.
Phase 2 (after Omnius): Auto-import from accounting via Omnius.

Tables: financial_metrics, budget_items, financial_alerts
Cron: daily check for budget alerts, monthly summary
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_tables_ensured = False
def _ensure_tables() -> None:
    """Create financial tables if they don't exist."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS financial_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    company TEXT NOT NULL,
                    metric_type TEXT NOT NULL CHECK (metric_type IN (
                        'revenue_monthly', 'costs_monthly', 'cash_position',
                        'receivables', 'payables', 'ebitda', 'headcount',
                        'api_costs', 'infrastructure_costs', 'legal_costs'
                    )),
                    value NUMERIC NOT NULL,
                    currency TEXT DEFAULT 'PLN',
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    source TEXT DEFAULT 'manual',
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(company, metric_type, period_start)
                );

                CREATE TABLE IF NOT EXISTS budget_items (
                    id BIGSERIAL PRIMARY KEY,
                    company TEXT NOT NULL,
                    category TEXT NOT NULL,
                    planned_amount NUMERIC NOT NULL,
                    actual_amount NUMERIC DEFAULT 0,
                    currency TEXT DEFAULT 'PLN',
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    alert_threshold NUMERIC DEFAULT 1.1,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(company, category, period_start)
                );

                CREATE TABLE IF NOT EXISTS financial_alerts (
                    id BIGSERIAL PRIMARY KEY,
                    alert_type TEXT NOT NULL CHECK (alert_type IN (
                        'budget_exceeded', 'budget_warning', 'cash_low',
                        'receivables_overdue', 'cost_spike', 'revenue_drop'
                    )),
                    company TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                    metric_value NUMERIC,
                    threshold_value NUMERIC,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ
                );

                CREATE INDEX IF NOT EXISTS idx_fin_metrics_company
                    ON financial_metrics(company, metric_type);
                CREATE INDEX IF NOT EXISTS idx_fin_metrics_period
                    ON financial_metrics(period_start);
                CREATE INDEX IF NOT EXISTS idx_budget_company
                    ON budget_items(company, period_start);
                CREATE INDEX IF NOT EXISTS idx_fin_alerts_active
                    ON financial_alerts(is_active) WHERE is_active = TRUE;
            """)
        conn.commit()
    log.info("financial_tables_ensured")
    _tables_ensured = True


# ---------------------------------------------------------------------------
# Metric recording
# ---------------------------------------------------------------------------

def record_metric(
    company: str,
    metric_type: str,
    value: float,
    period_start: str,
    period_end: str,
    source: str = "manual",
    notes: str | None = None,
) -> dict:
    """Insert or upsert a financial metric."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO financial_metrics
                       (company, metric_type, value, period_start, period_end, source, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company, metric_type, period_start)
                   DO UPDATE SET value = EXCLUDED.value,
                                 notes = EXCLUDED.notes,
                                 source = EXCLUDED.source
                   RETURNING id""",
                (company, metric_type, value, period_start, period_end, source, notes),
            )
            rows = cur.fetchall()
            row = rows[0] if rows else None
        conn.commit()
    metric_id = row[0] if row else None
    log.info("metric_recorded", company=company, metric_type=metric_type, value=value, id=metric_id)
    return {"id": metric_id, "company": company, "metric_type": metric_type, "value": value}


# ---------------------------------------------------------------------------
# Budget management
# ---------------------------------------------------------------------------

def record_budget(
    company: str,
    category: str,
    planned_amount: float,
    period_start: str,
    period_end: str,
    actual_amount: float = 0,
) -> dict:
    """Insert or upsert a budget item."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO budget_items
                       (company, category, planned_amount, actual_amount, period_start, period_end)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company, category, period_start)
                   DO UPDATE SET planned_amount = EXCLUDED.planned_amount,
                                 actual_amount = EXCLUDED.actual_amount,
                                 updated_at = NOW()
                   RETURNING id""",
                (company, category, planned_amount, actual_amount, period_start, period_end),
            )
            rows = cur.fetchall()
            row = rows[0] if rows else None
        conn.commit()
    budget_id = row[0] if row else None
    log.info("budget_recorded", company=company, category=category, planned=planned_amount, id=budget_id)
    return {"id": budget_id, "company": company, "category": category, "planned_amount": planned_amount}


def update_budget_actual(company: str, category: str, period_start: str, actual_amount: float) -> dict:
    """Update actual_amount for a budget item."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE budget_items
                   SET actual_amount = %s, updated_at = NOW()
                   WHERE company = %s AND category = %s AND period_start = %s
                   RETURNING id, planned_amount""",
                (actual_amount, company, category, period_start),
            )
            rows = cur.fetchall()
            row = rows[0] if rows else None
        conn.commit()

    if not row:
        log.warning("budget_item_not_found", company=company, category=category, period_start=period_start)
        return {"error": "budget item not found"}

    log.info("budget_actual_updated", company=company, category=category, actual=actual_amount)
    return {
        "id": row[0],
        "company": company,
        "category": category,
        "planned_amount": float(row[1]),
        "actual_amount": actual_amount,
        "utilization_pct": round(actual_amount / float(row[1]) * 100, 1) if float(row[1]) > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Budget alerts
# ---------------------------------------------------------------------------

def check_budget_alerts() -> list[dict]:
    """Check all budget items for threshold breaches and create alerts."""
    _ensure_tables()
    alerts_created: list[dict] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Get all budget items with their utilization
            cur.execute(
                """SELECT id, company, category, planned_amount, actual_amount,
                          alert_threshold, period_start
                   FROM budget_items
                   WHERE period_end >= CURRENT_DATE"""
            )
            items = cur.fetchall()

            for item in items:
                item_id, company, category, planned, actual, threshold, period_start = item
                planned_f = float(planned)
                actual_f = float(actual)
                threshold_f = float(threshold)

                if planned_f <= 0:
                    continue

                ratio = actual_f / planned_f

                alert_type = None
                severity = None

                if ratio >= threshold_f:
                    alert_type = "budget_exceeded"
                    severity = "high"
                elif ratio >= 0.8:
                    alert_type = "budget_warning"
                    severity = "medium"

                if not alert_type:
                    continue

                # Dedup: don't re-create same alert within 7 days
                cur.execute(
                    """SELECT id FROM financial_alerts
                       WHERE alert_type = %s AND company = %s
                             AND description LIKE %s
                             AND created_at > NOW() - INTERVAL '7 days'
                             AND is_active = TRUE""",
                    (alert_type, company, f"%{category}%"),
                )
                rows = cur.fetchall()
                if rows:
                    continue

                description = (
                    f"{category}: {actual_f:,.0f} / {planned_f:,.0f} PLN "
                    f"({ratio * 100:.0f}% wykorzystania)"
                )
                cur.execute(
                    """INSERT INTO financial_alerts
                           (alert_type, company, description, severity, metric_value, threshold_value)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (alert_type, company, description, severity, actual_f, planned_f * threshold_f),
                )
                alert_rows = cur.fetchall()
                alert_row = alert_rows[0] if alert_rows else None
                alert_id = alert_row[0] if alert_row else None
                alerts_created.append({
                    "id": alert_id,
                    "alert_type": alert_type,
                    "company": company,
                    "category": category,
                    "severity": severity,
                    "description": description,
                })
                log.info("budget_alert_created", alert_type=alert_type, company=company, category=category)

        conn.commit()

    return alerts_created


# ---------------------------------------------------------------------------
# API cost summary
# ---------------------------------------------------------------------------

def get_api_cost_summary(months: int = 3) -> dict:
    """Query api_costs table for monthly summary with trend analysis."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DATE_TRUNC('month', created_at) as month,
                          SUM(cost_usd) as total_usd,
                          COUNT(*) as api_calls
                   FROM api_costs
                   WHERE created_at > NOW() - (%s * INTERVAL '1 month')
                   GROUP BY 1 ORDER BY 1 DESC""",
                (months,),
            )
            rows = cur.fetchall()

    monthly: list[dict] = []
    totals: list[float] = []
    for row in rows:
        month_val = float(row[1]) if row[1] else 0.0
        totals.append(month_val)
        monthly.append({
            "month": str(row[0].date()) if row[0] else None,
            "total_usd": round(month_val, 2),
            "api_calls": row[2],
        })

    avg_monthly = round(sum(totals) / len(totals), 2) if totals else 0
    trend = "stable"
    if len(totals) >= 2:
        if totals[0] > totals[1] * 1.15:
            trend = "increasing"
        elif totals[0] < totals[1] * 0.85:
            trend = "decreasing"

    # Forecast current month based on days elapsed
    current_month_cost = totals[0] if totals else 0
    now = datetime.now(timezone.utc)
    days_in_month = 30
    days_elapsed = now.day
    forecast = round(current_month_cost / max(days_elapsed, 1) * days_in_month, 2) if current_month_cost else 0

    return {
        "monthly": monthly,
        "avg_monthly_usd": avg_monthly,
        "trend": trend,
        "current_month_forecast_usd": forecast,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_financial_dashboard(company: str | None = None) -> dict:
    """Comprehensive financial dashboard across companies."""
    _ensure_tables()
    companies_filter = [company] if company else ["REH", "REF"]
    dashboard: dict[str, Any] = {"companies": {}, "active_alerts": 0}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for comp in companies_filter:
                # Latest metrics
                cur.execute(
                    """SELECT DISTINCT ON (metric_type)
                              metric_type, value, currency, period_start, source
                       FROM financial_metrics
                       WHERE company = %s
                       ORDER BY metric_type, period_start DESC""",
                    (comp,),
                )
                metrics = {}
                for row in cur.fetchall():
                    metrics[row[0]] = {
                        "value": float(row[1]),
                        "currency": row[2],
                        "period_start": str(row[3]),
                        "source": row[4],
                    }

                # Budget utilization
                cur.execute(
                    """SELECT category, planned_amount, actual_amount, currency
                       FROM budget_items
                       WHERE company = %s AND period_end >= CURRENT_DATE
                       ORDER BY category""",
                    (comp,),
                )
                budgets = []
                for row in cur.fetchall():
                    planned_f = float(row[1])
                    actual_f = float(row[2])
                    budgets.append({
                        "category": row[0],
                        "planned": planned_f,
                        "actual": actual_f,
                        "pct": round(actual_f / planned_f * 100, 1) if planned_f > 0 else 0,
                        "currency": row[3],
                    })

                # Active alerts
                cur.execute(
                    """SELECT alert_type, description, severity, created_at
                       FROM financial_alerts
                       WHERE company = %s AND is_active = TRUE
                       ORDER BY created_at DESC""",
                    (comp,),
                )
                alerts = [
                    {
                        "alert_type": row[0],
                        "description": row[1],
                        "severity": row[2],
                        "created_at": str(row[3]),
                    }
                    for row in cur.fetchall()
                ]

                dashboard["companies"][comp] = {
                    "latest_metrics": metrics,
                    "budget_utilization": budgets,
                    "alerts": alerts,
                }

            # Total active alerts
            cur.execute("SELECT COUNT(*) FROM financial_alerts WHERE is_active = TRUE")
            rows = cur.fetchall()
            row = rows[0] if rows else None
            dashboard["active_alerts"] = row[0] if row else 0

    # API costs
    dashboard["api_costs"] = get_api_cost_summary()

    # Total budget utilization
    total_planned = 0.0
    total_actual = 0.0
    for comp_data in dashboard["companies"].values():
        for b in comp_data["budget_utilization"]:
            total_planned += b["planned"]
            total_actual += b["actual"]
    dashboard["total_budget_utilization"] = (
        round(total_actual / total_planned * 100, 1) if total_planned > 0 else 0
    )

    return dashboard


# ---------------------------------------------------------------------------
# Financial context for decisions
# ---------------------------------------------------------------------------

def get_financial_context_for_decision(description: str = "") -> str:
    """Return formatted financial context string for use by Decision Cost Estimator."""
    _ensure_tables()
    parts: list[str] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Latest metrics per company
            for comp in ["REH", "REF"]:
                cur.execute(
                    """SELECT DISTINCT ON (metric_type)
                              metric_type, value, currency, period_start
                       FROM financial_metrics
                       WHERE company = %s
                       ORDER BY metric_type, period_start DESC""",
                    (comp,),
                )
                rows = cur.fetchall()
                if rows:
                    lines = [f"\n{comp} (latest):"]
                    for row in rows:
                        lines.append(f"  {row[0]}: {float(row[1]):,.0f} {row[2]} (od {row[3]})")
                    parts.append("\n".join(lines))

            # Budget remaining
            cur.execute(
                """SELECT company, category, planned_amount - actual_amount as remaining, currency
                   FROM budget_items
                   WHERE period_end >= CURRENT_DATE
                   ORDER BY company, category"""
            )
            budget_rows = cur.fetchall()
            if budget_rows:
                parts.append("\nBudget remaining:")
                for row in budget_rows:
                    parts.append(f"  {row[0]}/{row[1]}: {float(row[2]):,.0f} {row[3]}")

    # API costs trend
    api_summary = get_api_cost_summary(months=2)
    parts.append(
        f"\nAPI costs: avg {api_summary['avg_monthly_usd']:.2f} USD/month, "
        f"trend: {api_summary['trend']}, "
        f"forecast this month: {api_summary['current_month_forecast_usd']:.2f} USD"
    )

    return "\n".join(parts) if parts else "No financial data available yet."


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_financial_check() -> dict:
    """Main pipeline: check budget alerts, API cost summary, return dashboard."""
    _ensure_tables()
    log.info("financial_check_start")

    alerts = check_budget_alerts()
    log.info("budget_alerts_checked", new_alerts=len(alerts))

    dashboard = get_financial_dashboard()
    dashboard["new_alerts"] = alerts

    log.info("financial_check_done", active_alerts=dashboard["active_alerts"])
    return dashboard


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--dashboard":
        result = get_financial_dashboard()
    elif len(sys.argv) > 1 and sys.argv[1] == "--api-costs":
        result = get_api_cost_summary()
    else:
        result = run_financial_check()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
