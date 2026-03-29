"""Plugin-specific governance — duplicate detection, cost estimation,
two-stage evaluation for plugin proposals.

Uses existing governance.validate_value() for value assessment
and extends it with feasibility checks, duplicate detection,
and cost estimation via LLM.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import structlog

from omnius.db.postgres import get_pg_connection
from omnius.core.governance import validate_value

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("OMNIUS_LLM_MODEL", "claude-haiku-4-5")


def check_feature_inventory(proposal: str) -> dict:
    """Check if a proposal duplicates any existing plugin.

    Queries omnius_plugins for all existing plugins and uses Claude
    to assess similarity.

    Returns: {is_duplicate, similar_plugin, similarity_score, reasoning}
    """
    # Get existing plugins
    existing_plugins = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, description
                    FROM omnius_plugins
                    ORDER BY name
                """)
                existing_plugins = [
                    {"name": row[0], "description": row[1] or ""}
                    for row in cur.fetchall()
                ]
    except Exception as e:
        log.warning("feature_inventory_db_failed", error=str(e))

    if not existing_plugins:
        return {
            "is_duplicate": False,
            "similar_plugin": None,
            "similarity_score": 0.0,
            "reasoning": "No existing plugins to compare against.",
        }

    # Use LLM to check for duplicates
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("duplicate_check_skipped", reason="no ANTHROPIC_API_KEY")
        return {
            "is_duplicate": False,
            "similar_plugin": None,
            "similarity_score": 0.0,
            "reasoning": "LLM not available for duplicate check.",
        }

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        plugins_list = "\n".join(
            f"- {p['name']}: {p['description']}" for p in existing_plugins
        )

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=(
                "You check if a plugin proposal duplicates existing plugins. "
                "Respond ONLY in JSON format: "
                '{"is_duplicate": true/false, "similar_plugin": "name"|null, '
                '"similarity_score": 0.0-1.0, "reasoning": "brief explanation"}'
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Existing plugins:\n{plugins_list}\n\n"
                    f"New proposal:\n{proposal}"
                ),
            }],
        )

        result_text = response.content[0].text.strip()
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*"is_duplicate"[^{}]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return {
                    "is_duplicate": False,
                    "similar_plugin": None,
                    "similarity_score": 0.0,
                    "reasoning": "Could not parse LLM response for duplicate check.",
                }

        return {
            "is_duplicate": bool(result.get("is_duplicate", False)),
            "similar_plugin": result.get("similar_plugin"),
            "similarity_score": float(result.get("similarity_score", 0.0)),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        log.warning("duplicate_check_failed", error=str(e))
        return {
            "is_duplicate": False,
            "similar_plugin": None,
            "similarity_score": 0.0,
            "reasoning": f"Duplicate check failed: {e}",
        }


def estimate_cost(proposal: str) -> dict:
    """Use Claude to estimate development and operational costs.

    Returns: {development_time_hours, api_cost_per_invocation_usd,
              maintenance_hours_per_month, complexity, reasoning}
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("cost_estimate_skipped", reason="no ANTHROPIC_API_KEY")
        return {
            "development_time_hours": 0.0,
            "api_cost_per_invocation_usd": 0.0,
            "maintenance_hours_per_month": 0.0,
            "complexity": "unknown",
            "reasoning": "LLM not available for cost estimation.",
        }

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=(
                "You estimate costs for Omnius plugin development. "
                "Omnius is a corporate AI system. Plugins use a Python SDK "
                "with PluginContext (query_data, create_task, send_notification, etc). "
                "Respond ONLY in JSON: "
                '{"development_time_hours": float, '
                '"api_cost_per_invocation_usd": float, '
                '"maintenance_hours_per_month": float, '
                '"complexity": "low"|"medium"|"high", '
                '"reasoning": "brief explanation"}'
            ),
            messages=[{
                "role": "user",
                "content": f"Estimate cost for this plugin proposal:\n\n{proposal}",
            }],
        )

        result_text = response.content[0].text.strip()
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*"complexity"[^{}]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return {
                    "development_time_hours": 0.0,
                    "api_cost_per_invocation_usd": 0.0,
                    "maintenance_hours_per_month": 0.0,
                    "complexity": "unknown",
                    "reasoning": "Could not parse LLM cost estimation.",
                }

        return {
            "development_time_hours": float(result.get("development_time_hours", 0)),
            "api_cost_per_invocation_usd": float(result.get("api_cost_per_invocation_usd", 0)),
            "maintenance_hours_per_month": float(result.get("maintenance_hours_per_month", 0)),
            "complexity": result.get("complexity", "unknown"),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        log.warning("cost_estimate_failed", error=str(e))
        return {
            "development_time_hours": 0.0,
            "api_cost_per_invocation_usd": 0.0,
            "maintenance_hours_per_month": 0.0,
            "complexity": "unknown",
            "reasoning": f"Cost estimation failed: {e}",
        }


def two_stage_evaluation(proposal: str, user: dict[str, Any]) -> dict:
    """Two-stage plugin proposal evaluation.

    Stage 1: Feasibility — can the Plugin SDK support this?
    Stage 2: Value — call existing validate_value() from governance.py

    Plus: cost estimation and duplicate detection.

    Returns: {feasibility, value, cost_estimate, duplicate_check,
              overall_approved, overall_score}
    """
    # Stage 1: Feasibility check
    feasibility = _check_feasibility(proposal)

    # Stage 2: Value check (reuse existing governance)
    value_result = validate_value(proposal, user)

    # Additional checks
    cost = estimate_cost(proposal)
    duplicates = check_feature_inventory(proposal)

    # Overall decision
    feasibility_ok = feasibility.get("possible", False)
    value_ok = value_result.get("approved", False)
    not_duplicate = not duplicates.get("is_duplicate", False)

    overall_approved = feasibility_ok and value_ok and not_duplicate

    # Combined score: weighted average
    feasibility_score = feasibility.get("score", 0.0)
    value_score = value_result.get("value_score", 0.0)
    overall_score = round(
        feasibility_score * 0.3 + value_score * 0.7, 2
    )
    if duplicates.get("is_duplicate"):
        overall_score = max(0.0, overall_score - 0.5)

    result = {
        "feasibility": {
            "possible": feasibility_ok,
            "reasoning": feasibility.get("reasoning", ""),
            "score": feasibility_score,
        },
        "value": {
            "approved": value_ok,
            "value_score": value_score,
            "reasoning": value_result.get("reasoning", ""),
        },
        "cost_estimate": cost,
        "duplicate_check": duplicates,
        "overall_approved": overall_approved,
        "overall_score": overall_score,
    }

    log.info("two_stage_evaluation_complete",
             user=user.get("email", user.get("api_key_name")),
             approved=overall_approved,
             score=overall_score,
             feasible=feasibility_ok,
             valuable=value_ok,
             duplicate=duplicates.get("is_duplicate", False))

    return result


def _check_feasibility(proposal: str) -> dict:
    """Stage 1: Check if the Plugin SDK can support this proposal.

    Evaluates whether required data access, integrations, and
    capabilities are available through PluginContext.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("feasibility_check_skipped", reason="no ANTHROPIC_API_KEY")
        return {
            "possible": True,
            "score": 0.5,
            "reasoning": "LLM not available — assuming feasible pending manual review.",
        }

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=(
                "You assess if an Omnius plugin proposal is technically feasible. "
                "The Plugin SDK provides these methods via PluginContext:\n"
                "- query_data(query, classification_max) — semantic search over data\n"
                "- create_task(title, description, assignee) — create operator tasks\n"
                "- send_notification(user_email, message) — log notifications\n"
                "- get_config(key) — read plugin config\n"
                "- log(level, message, **kwargs) — structured logging\n\n"
                "Plugins run in sandboxed containers with NO network access, "
                "NO file system access, NO raw DB access.\n\n"
                "Respond ONLY in JSON: "
                '{"possible": true/false, "score": 0.0-1.0, '
                '"reasoning": "brief explanation"}'
            ),
            messages=[{
                "role": "user",
                "content": f"Is this plugin feasible?\n\n{proposal}",
            }],
        )

        result_text = response.content[0].text.strip()
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*"possible"[^{}]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return {
                    "possible": True,
                    "score": 0.5,
                    "reasoning": "Could not parse feasibility response.",
                }

        return {
            "possible": bool(result.get("possible", True)),
            "score": float(result.get("score", 0.5)),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        log.warning("feasibility_check_failed", error=str(e))
        return {
            "possible": True,
            "score": 0.5,
            "reasoning": f"Feasibility check failed: {e}",
        }
