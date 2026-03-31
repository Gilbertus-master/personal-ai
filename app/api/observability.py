"""Observability dashboard & alert endpoint — self-hosted tracing for Gilbertus."""
from __future__ import annotations

import json
import os
import subprocess
import threading

from fastapi import APIRouter, HTTPException

from app.db.postgres import get_pg_connection

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/dashboard")
def observability_dashboard(hours: int = 24):
    """Latency percentiles, error rate, cost, stage breakdown, slowest queries."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Latency percentiles & counts
            cur.execute("""
                SELECT
                    COUNT(*)                                                      AS total_runs,
                    ROUND(AVG(latency_ms))                                        AS avg_ms,
                    PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY latency_ms)::int AS p50_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)::int AS p95_ms,
                    MAX(latency_ms)                                               AS max_ms,
                    SUM(CASE WHEN error_flag THEN 1 ELSE 0 END)                   AS errors,
                    SUM(CASE WHEN cache_hit  THEN 1 ELSE 0 END)                   AS cache_hits,
                    SUM(CASE WHEN used_fallback THEN 1 ELSE 0 END)                AS fallbacks
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s)
            """, (hours,))
            row = cur.fetchone()
            total = row[0] or 0
            stats = {
                "period_hours": hours,
                "total_runs": total,
                "avg_latency_ms": row[1],
                "p50_ms": row[2],
                "p95_ms": row[3],
                "max_latency_ms": row[4],
                "error_count": row[5] or 0,
                "error_rate_pct": round(100 * (row[5] or 0) / max(total, 1), 1),
                "cache_hit_count": row[6] or 0,
                "cache_hit_rate_pct": round(100 * (row[6] or 0) / max(total, 1), 1),
                "fallback_count": row[7] or 0,
            }

            # 2. Stage breakdown (avg ms per stage)
            cur.execute("""
                SELECT
                    AVG((stage_ms->>'interpret')::int)  AS avg_interpret,
                    AVG((stage_ms->>'retrieve')::int)   AS avg_retrieve,
                    AVG((stage_ms->>'answer')::int)     AS avg_answer
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s)
                  AND stage_ms IS NOT NULL
            """, (hours,))
            row = cur.fetchone()
            stages = {
                "avg_interpret_ms": int(row[0] or 0),
                "avg_retrieve_ms":  int(row[1] or 0),
                "avg_answer_ms":    int(row[2] or 0),
            }
            if any(stages.values()):
                total_stage = sum(stages.values())
                bottleneck = max(stages, key=stages.get)
                stages["bottleneck"] = bottleneck
                stages["bottleneck_pct"] = round(100 * stages[bottleneck] / max(total_stage, 1), 1)

            # 3. Cost summary from ask_runs
            cur.execute("""
                SELECT
                    COUNT(*)                                AS calls,
                    COALESCE(SUM(input_tokens), 0)          AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0)         AS total_output_tokens,
                    ROUND(COALESCE(SUM(cost_usd), 0)::numeric, 4) AS total_cost_usd
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s)
                  AND cost_usd IS NOT NULL
            """, (hours,))
            row = cur.fetchone()
            cost = {
                "runs_with_cost": row[0] or 0,
                "total_input_tokens": row[1] or 0,
                "total_output_tokens": row[2] or 0,
                "total_cost_usd": float(row[3] or 0),
            }

            # 4. Top 5 slowest runs
            cur.execute("""
                SELECT id, created_at, query_text, latency_ms,
                       model_used, error_flag, stage_ms
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s)
                ORDER BY latency_ms DESC NULLS LAST LIMIT 5
            """, (hours,))
            slowest = [
                {
                    "run_id": r[0],
                    "at": str(r[1]),
                    "query": (r[2] or "")[:80],
                    "latency_ms": r[3],
                    "model": r[4],
                    "error": r[5],
                    "stages": r[6],
                }
                for r in cur.fetchall()
            ]

            # 5. Error runs
            cur.execute("""
                SELECT id, created_at, query_text, latency_ms, error_message
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s) AND error_flag = TRUE
                ORDER BY created_at DESC LIMIT 10
            """, (hours,))
            errors = [
                {
                    "run_id": r[0],
                    "at": str(r[1]),
                    "query": (r[2] or "")[:80],
                    "latency_ms": r[3],
                    "error_message": r[4],
                }
                for r in cur.fetchall()
            ]

            # 6. Model distribution
            cur.execute("""
                SELECT model_used, COUNT(*) as runs,
                       ROUND(AVG(latency_ms)) as avg_ms,
                       ROUND(COALESCE(SUM(cost_usd), 0)::numeric, 4) as cost_usd
                FROM ask_runs
                WHERE created_at > NOW() - make_interval(hours => %s) AND model_used IS NOT NULL
                GROUP BY model_used ORDER BY runs DESC
            """, (hours,))
            models = [
                {"model": r[0], "runs": r[1], "avg_ms": r[2], "cost_usd": float(r[3] or 0)}
                for r in cur.fetchall()
            ]

    return {
        "stats": stats,
        "stages": stages,
        "cost": cost,
        "slowest_runs": slowest,
        "recent_errors": errors,
        "model_breakdown": models,
    }


@router.get("/alert-check")
def run_alert_check():
    """Check for anomalies and send WhatsApp alert if needed. Run via cron every 30 min."""
    alerts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Slow runs in last 30 min
            cur.execute("""
                SELECT COUNT(*), MAX(latency_ms)
                FROM ask_runs
                WHERE created_at > NOW() - INTERVAL '30 minutes'
                  AND latency_ms > 45000
            """)
            row = cur.fetchone()
            slow_count, max_ms = row[0] or 0, row[1] or 0
            if slow_count >= 3:
                alerts.append(f"⏱ {slow_count} requestów >45s w ostatnich 30 min (max {int(max_ms/1000)}s)")

            # Errors in last hour
            cur.execute("""
                SELECT COUNT(*) FROM ask_runs
                WHERE created_at > NOW() - INTERVAL '1 hour' AND error_flag = TRUE
            """)
            err_count = cur.fetchall()[0][0] or 0
            if err_count >= 2:
                alerts.append(f"🔴 {err_count} błędów w ostatniej godzinie")

            # High error rate
            cur.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN error_flag THEN 1 ELSE 0 END)
                FROM ask_runs
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            row = cur.fetchone()
            total_h, err_h = row[0] or 0, row[1] or 0
            if total_h >= 5 and (err_h / total_h) > 0.20:
                alerts.append(f"🔴 Error rate {round(100*err_h/total_h)}% w ostatniej godzinie ({err_h}/{total_h})")

    if alerts:
        msg = "⚡ *Gilbertus Observability Alert*\n\n" + "\n".join(alerts)
        msg += "\n\nSzczegóły: curl http://127.0.0.1:8000/observability/dashboard"

        def _send():
            try:
                openclaw = os.getenv("OPENCLAW_BIN", "openclaw")
                wa_target = os.getenv("WA_TARGET", "+48505441635")
                subprocess.run(
                    [openclaw, "message", "send", "--channel", "whatsapp",
                     "--target", wa_target, "--message", msg],
                    capture_output=True, text=True, timeout=15,
                )
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()

    return {"alerts_sent": len(alerts), "alerts": alerts}


@router.get("/trace/{run_id}")
def get_trace(run_id: int):
    """Full waterfall trace for a single /ask run."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, query_text, normalized_query,
                       question_type, analysis_depth, source_types,
                       latency_ms, stage_ms, model_used,
                       input_tokens, output_tokens, cost_usd,
                       error_flag, error_message, cache_hit,
                       used_fallback, match_count,
                       caller_ip, channel_key
                FROM ask_runs WHERE id = %s
            """, (run_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    stage_ms = row[8] or {}
    total_ms = row[7] or 0
    waterfall = {}
    for stage, ms in stage_ms.items():
        if ms and total_ms:
            waterfall[stage] = {"ms": ms, "pct": round(100 * ms / max(total_ms, 1), 1)}
        elif ms:
            waterfall[stage] = {"ms": ms, "pct": None}
    matches = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rank_index, score, source_type, source_name, title, excerpt
                FROM ask_run_matches WHERE ask_run_id = %s ORDER BY rank_index
            """, (run_id,))
            for m in cur.fetchall():
                matches.append({"rank": m[0], "score": float(m[1]) if m[1] else None,
                                "source_type": m[2], "source_name": m[3],
                                "title": m[4], "excerpt": (m[5] or "")[:200]})
    return {
        "run_id": row[0], "created_at": str(row[1]),
        "query": row[2], "normalized_query": row[3],
        "question_type": row[4], "analysis_depth": row[5],
        "source_types": row[6], "latency_ms": total_ms,
        "waterfall": waterfall,
        "bottleneck": max(stage_ms, key=stage_ms.get) if stage_ms else None,
        "model_used": row[9], "input_tokens": row[10], "output_tokens": row[11],
        "cost_usd": float(row[12]) if row[12] else None,
        "error_flag": row[13], "error_message": row[14],
        "cache_hit": row[15], "used_fallback": row[16],
        "match_count": row[17] or len(matches), "matches": matches,
        "caller_ip": row[18], "channel_key": row[19],
    }


@router.get("/graph/action/{action_id}")
def get_action_graph_state(action_id: int):
    """Inspect current state of an action in the LangGraph pipeline."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, result, proposed_at, decided_at, executed_at "
                    "FROM action_items WHERE id = %s",
                    (action_id,),
                )
                row = cur.fetchone()
        if not row:
            return {"error": f"Action #{action_id} not found"}

        status, result_raw, proposed_at, decided_at, executed_at = row
        result_data = {}
        try:
            result_data = json.loads(result_raw) if result_raw else {}
        except Exception:
            pass

        thread_id = result_data.get("graph_thread_id")

        graph_state = {}
        if thread_id:
            try:
                from app.orchestrator.action_graph import get_action_graph
                graph = get_action_graph()
                config = {"configurable": {"thread_id": thread_id}}
                snapshot = graph.get_state(config)
                graph_state = {
                    "current_node": snapshot.next,
                    "values": {k: v for k, v in snapshot.values.items()
                               if k not in ("execution_result",)},
                    "checkpoints": len(list(graph.get_state_history(config))),
                }
            except Exception as e:
                graph_state = {"error": str(e)}

        return {
            "action_id": action_id,
            "db_status": status,
            "thread_id": thread_id,
            "proposed_at": str(proposed_at) if proposed_at else None,
            "decided_at": str(decided_at) if decided_at else None,
            "executed_at": str(executed_at) if executed_at else None,
            "graph_state": graph_state,
        }
    except Exception as e:
        return {"error": str(e)}
