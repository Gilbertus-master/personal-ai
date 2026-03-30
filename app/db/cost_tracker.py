"""Centralized API cost tracking. Fire-and-forget — never breaks callers."""
from __future__ import annotations

import time
import threading
import structlog

log = structlog.get_logger()

# Pricing per 1M tokens (USD)
ANTHROPIC_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_create": 1.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_create": 18.75},
}

OPENAI_PRICING = {
    "text-embedding-3-large": {"input": 0.13},
    "text-embedding-3-small": {"input": 0.02},
}


def log_anthropic_cost(model: str, module: str, usage) -> None:
    """Log Anthropic API cost to DB. usage = response.usage object."""
    try:
        from app.db.postgres import get_pg_connection

        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0

        prices = ANTHROPIC_PRICING.get(model, {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_create": 3.75})
        fresh_input = max(0, input_tokens - cache_read - cache_create)
        cost = (
            fresh_input * prices["input"] / 1_000_000
            + output_tokens * prices["output"] / 1_000_000
            + cache_read * prices.get("cache_read", 0) / 1_000_000
            + cache_create * prices.get("cache_create", 0) / 1_000_000
        )

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_costs (provider, model, module, input_tokens, output_tokens,
                       cache_read_tokens, cache_creation_tokens, cost_usd)
                       VALUES ('anthropic', %s, %s, %s, %s, %s, %s, %s)""",
                    (model, module, input_tokens, output_tokens, cache_read, cache_create, cost),
                )
            conn.commit()
    except Exception:
        pass


def log_openai_cost(model: str, module: str, token_count: int) -> None:
    """Log OpenAI embedding cost to DB."""
    try:
        from app.db.postgres import get_pg_connection

        prices = OPENAI_PRICING.get(model, {"input": 0.13})
        cost = token_count * prices["input"] / 1_000_000

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_costs (provider, model, module, input_tokens, output_tokens,
                       cache_read_tokens, cache_creation_tokens, cost_usd)
                       VALUES ('openai', %s, %s, %s, 0, 0, 0, %s)""",
                    (model, module, token_count, cost),
                )
            conn.commit()
    except Exception:
        pass


# ================================================================
# Budget checks & alerts — fail-CLOSED: ok=False on any error
# ================================================================

_BUDGET_CHECK_TIMEOUT_S = 2.0


def check_budget(module: str) -> dict:
    """Check if module or daily total budget is exceeded.

    Returns dict: {ok: bool, reason: str|None, daily_total: float, daily_limit: float}
    NEVER raises — returns ok=False on error (fail-closed).
    """
    try:
        from app.db.postgres import get_pg_connection

        t_start = time.monotonic()
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Fetch all data in single round-trip: daily total, module total, and budget limits
                cur.execute("""
                    WITH daily_spend AS (
                        SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_costs WHERE created_at >= CURRENT_DATE
                    ),
                    module_spend AS (
                        SELECT COALESCE(SUM(cost_usd), 0) as total FROM api_costs WHERE created_at >= CURRENT_DATE AND module LIKE %s
                    )
                    SELECT 'daily' as type, (SELECT total FROM daily_spend) as amount, NULL::text as scope, NULL::float as limit_usd, NULL::integer as alert_pct, NULL::boolean as hard_limit
                    UNION ALL
                    SELECT 'module' as type, (SELECT total FROM module_spend) as amount, NULL::text as scope, NULL::float as limit_usd, NULL::integer as alert_pct, NULL::boolean as hard_limit
                    UNION ALL
                    SELECT 'budget' as type, NULL::float as amount, scope, limit_usd, alert_threshold_pct, hard_limit FROM cost_budgets
                """, (f"{module}%",))

                rows = cur.fetchall()
                daily_total = 0.0
                module_total = 0.0
                budgets = {}

                for row in rows:
                    row_type = row[0]
                    if row_type == 'daily':
                        daily_total = float(row[1])
                    elif row_type == 'module':
                        module_total = float(row[1])
                    elif row_type == 'budget':
                        scope, limit_usd, alert_pct, hard = row[2], row[3], row[4], row[5]
                        budgets[scope] = {"limit": float(limit_usd), "alert_pct": alert_pct, "hard": hard}

        elapsed = time.monotonic() - t_start
        if elapsed > _BUDGET_CHECK_TIMEOUT_S:
            log.error("budget_check_timeout", elapsed_s=round(elapsed, 2))
            return {"ok": False, "reason": "budget check timeout", "daily_total": 0.0, "daily_limit": 0.0}

        result = {"ok": True, "reason": None, "daily_total": daily_total, "daily_limit": 0.0}

        # Check daily total
        dt = budgets.get("daily_total")
        if dt:
            result["daily_limit"] = dt["limit"]
            pct = (daily_total / dt["limit"] * 100) if dt["limit"] > 0 else 0

            if pct >= 100 and dt["hard"]:
                result["ok"] = False
                result["reason"] = f"Daily budget exceeded: ${daily_total:.2f} / ${dt['limit']:.2f}"
                _send_cost_alert(result["reason"], "hard_limit", scope="daily_total")
                return result

            if pct >= dt["alert_pct"]:
                _send_cost_alert(
                    f"Daily spend at {pct:.0f}%: ${daily_total:.2f} / ${dt['limit']:.2f}",
                    "warning", scope="daily_total"
                )

        # Check module budget
        module_prefix = module.split(".")[0] if "." in module else module
        mb = budgets.get(f"module:{module_prefix}")
        if mb:
            pct = (module_total / mb["limit"] * 100) if mb["limit"] > 0 else 0
            if pct >= 100 and mb["hard"]:
                result["ok"] = False
                result["reason"] = f"Module {module_prefix} budget exceeded: ${module_total:.2f} / ${mb['limit']:.2f}"
                _send_cost_alert(result["reason"], "hard_limit", scope=f"module:{module_prefix}")
                return result

            if pct >= mb["alert_pct"]:
                _send_cost_alert(
                    f"Module {module_prefix} at {pct:.0f}%: ${module_total:.2f} / ${mb['limit']:.2f}",
                    "warning", scope=f"module:{module_prefix}"
                )

        return result

    except Exception as e:
        log.error("budget_check_db_error", error=str(e))
        return {"ok": False, "reason": f"budget check failed: {str(e)[:50]}", "daily_total": 0.0, "daily_limit": 0.0}


def get_budget_status() -> dict:
    """Return current budget status for all scopes. For /costs/budget endpoint."""
    try:
        from app.db.postgres import get_pg_connection

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM api_costs WHERE created_at >= CURRENT_DATE")
                daily_total = float(cur.fetchall()[0][0])

                cur.execute("""
                    SELECT module, COALESCE(SUM(cost_usd), 0)
                    FROM api_costs WHERE created_at >= CURRENT_DATE
                    GROUP BY module ORDER BY 2 DESC
                """)
                module_costs = {row[0]: float(row[1]) for row in cur.fetchall()}

                cur.execute("SELECT scope, limit_usd, alert_threshold_pct, hard_limit FROM cost_budgets ORDER BY scope")
                budgets = []
                for row in cur.fetchall():
                    scope, limit_usd, alert_pct, hard = row[0], float(row[1]), row[2], row[3]
                    if scope == "daily_total":
                        spent = daily_total
                    elif scope.startswith("module:"):
                        prefix = scope.replace("module:", "")
                        spent = sum(v for k, v in module_costs.items() if k.startswith(prefix))
                    else:
                        spent = 0.0
                    pct = (spent / limit_usd * 100) if limit_usd > 0 else 0
                    budgets.append({
                        "scope": scope,
                        "limit_usd": limit_usd,
                        "spent_usd": round(spent, 4),
                        "pct": round(pct, 1),
                        "hard_limit": hard,
                        "status": "exceeded" if pct >= 100 else "warning" if pct >= alert_pct else "ok"
                    })

                # Recent alerts
                cur.execute("""
                    SELECT scope, alert_type, message, created_at
                    FROM cost_alert_log WHERE created_at >= CURRENT_DATE
                    ORDER BY created_at DESC LIMIT 10
                """)
                alerts = [{"scope": r[0], "type": r[1], "message": r[2], "at": str(r[3])} for r in cur.fetchall()]

        return {"daily_total_usd": round(daily_total, 4), "budgets": budgets, "alerts_today": alerts}

    except Exception as e:
        return {"error": str(e)}


def _send_cost_alert(message: str, alert_type: str, scope: str = "daily_total") -> None:
    """Fire-and-forget alert: log to DB + send WhatsApp. Runs in background thread."""
    def _do():
        try:
            from app.db.postgres import get_pg_connection

            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    # Dedup: don't re-alert same scope+type within 1 hour
                    cur.execute("""
                        SELECT 1 FROM cost_alert_log
                        WHERE scope = %s AND alert_type = %s
                          AND created_at > NOW() - INTERVAL '1 hour'
                        LIMIT 1
                    """, (scope, alert_type))
                    if cur.fetchone():
                        return

                    cur.execute(
                        "INSERT INTO cost_alert_log (scope, alert_type, message) VALUES (%s, %s, %s)",
                        (scope, alert_type, message)
                    )
                conn.commit()

            # Send WhatsApp alert
            import os
            import subprocess
            openclaw = os.getenv("OPENCLAW_BIN", "/home/sebastian/personal-ai/app/ingestion/whatsapp_live/openclaw")
            wa_target = os.getenv("WA_TARGET", "")
            if not wa_target:
                log.warning("whatsapp_skipped", reason="WA_TARGET not configured")
                return
            prefix = "\U0001f6a8" if alert_type == "hard_limit" else "\u26a0\ufe0f"
            subprocess.run(
                [openclaw, "message", "send", "--channel", "whatsapp",
                 "--target", wa_target, "--message", f"{prefix} Gilbertus Cost Alert: {message}"],
                capture_output=True, text=True, timeout=30,
            )
        except Exception as e:
            log.warning("cost_alert_failed", error=str(e))

    threading.Thread(target=_do, daemon=True).start()


def is_budget_check_healthy() -> bool:
    """Quick DB connectivity check for /health endpoint."""
    try:
        from app.db.postgres import get_pg_connection

        t_start = time.monotonic()
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return (time.monotonic() - t_start) <= _BUDGET_CHECK_TIMEOUT_S
    except Exception:
        return False
