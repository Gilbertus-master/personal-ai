"""
Decision Cost Estimator — estimates financial impact of proposed actions.

For action proposals at authority level 3-4, auto-generates cost estimate.
Uses LLM with financial context to estimate: direct cost, opportunity cost,
expected value, ROI, payback period.

Integrates with: authority.py (auto-attach to proposals), action_pipeline.py
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

COST_PROMPT = """You are a financial analyst for Respect Energy Holding (REH) and Respect Energy Fuels (REF).
Given an action proposal and financial context, estimate the costs and value.

Return JSON:
{
  "direct_cost_pln": N,
  "direct_cost_breakdown": [{"item": "...", "amount": N, "period": "monthly/one-time/annual"}],
  "opportunity_cost_pln": N,
  "opportunity_cost_note": "...",
  "expected_value_pln": N,
  "expected_value_note": "...",
  "roi_ratio": N,
  "payback_months": N,
  "risk_factors": ["..."],
  "recommendation": "proceed/review/reject",
  "confidence": 0.X,
  "summary": "1-2 sentence summary in Polish"
}

Be realistic. Use Polish market rates. If unsure, state confidence low.
All amounts in PLN unless stated otherwise."""


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_cost(
    action_description: str,
    action_type: str = "",
    params: dict | None = None,
) -> dict:
    """Use Claude to estimate financial impact of a proposed action."""
    from app.analysis.financial_framework import get_financial_context_for_decision

    financial_context = get_financial_context_for_decision(action_description)

    user_message = f"""Action proposal: {action_description}"""
    if action_type:
        user_message += f"\nAction type: {action_type}"
    if params:
        user_message += f"\nParameters: {json.dumps(params, ensure_ascii=False, default=str)}"
    user_message += f"\n\nFinancial context:\n{financial_context}"

    log.info("cost_estimation_start", description=action_description[:100])

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=COST_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "cost_estimator", response.usage)

        raw = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in raw:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            raw = raw[start:end]

        estimate = json.loads(raw)
        log.info(
            "cost_estimation_done",
            direct_cost=estimate.get("direct_cost_pln"),
            recommendation=estimate.get("recommendation"),
        )
        return estimate

    except json.JSONDecodeError:
        log.error("cost_estimation_json_parse_error", raw=raw[:200])
        return {"error": "Failed to parse LLM response", "raw": raw[:500]}
    except Exception as e:
        log.error("cost_estimation_failed", error=str(e))
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Enrich existing action proposals
# ---------------------------------------------------------------------------

def enrich_action_proposal(action_id: int) -> dict:
    """For an existing action proposal, generate cost estimate and attach it."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT description, action_type, draft_params
                   FROM action_items
                   WHERE id = %s""",
                (action_id,),
            )
            row = cur.fetchone()

    if not row:
        log.warning("action_not_found", action_id=action_id)
        return {"error": f"action_item {action_id} not found"}

    description = row[0]
    action_type = row[1] or ""
    existing_params = row[2] if row[2] else {}
    if isinstance(existing_params, str):
        existing_params = json.loads(existing_params)

    estimate = estimate_cost(description, action_type, existing_params)

    if "error" not in estimate:
        existing_params["cost_estimate"] = estimate
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE action_items
                       SET draft_params = %s
                       WHERE id = %s""",
                    (json.dumps(existing_params, ensure_ascii=False, default=str), action_id),
                )
            conn.commit()
        log.info("action_enriched_with_cost", action_id=action_id)

    return {"action_id": action_id, "cost_estimate": estimate}


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def get_estimation_history(limit: int = 20) -> list[dict]:
    """Query past cost estimations from action_items where draft_params has cost_estimate."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, description, action_type, draft_params, created_at
                   FROM action_items
                   WHERE draft_params::text LIKE %s
                   ORDER BY created_at DESC
                   LIMIT %s""",
                ("%cost_estimate%", limit),
            )
            rows = cur.fetchall()

    results = []
    for row in rows:
        params = row[3] if row[3] else {}
        if isinstance(params, str):
            params = json.loads(params)
        results.append({
            "action_id": row[0],
            "description": row[1],
            "action_type": row[2],
            "cost_estimate": params.get("cost_estimate", {}),
            "created_at": str(row[4]),
        })

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Zatrudnij junior developera do Omnius"
    result = estimate_cost(desc)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
