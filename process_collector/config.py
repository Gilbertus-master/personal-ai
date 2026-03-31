"""Configuration loader for process_collector sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)

CONFIG_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "process_sources.yaml"

# Default source definitions shipped with the module
_DEFAULT_SOURCES: dict[str, Any] = {
    "sources": {
        "sprint_delivery": {
            "enabled": True,
            "adapter": "jira",
            "process_name": "Sprint Delivery",
            "process_type": "engineering",
            "process_category": "software_development",
            "description": "Jira sprint metrics — velocity, cycle time, bugs, blockers",
            "column_mapping": {
                "throughput": "issues_completed",
                "velocity_points": "story_points_completed",
                "velocity_vs_plan": "velocity_vs_commitment",
                "bugs_introduced": "bugs_created",
                "blockers_count": "blockers_active",
                "wip_count": "issues_in_progress",
                "lead_time_days": "avg_lead_time_days",
                "flow_efficiency": "flow_efficiency_pct",
                "avg_cycle_time_h": "avg_cycle_time_hours",
                "p90_cycle_time_h": "p90_cycle_time_hours",
                "overdue_count": "overdue_issues",
                "rework_rate": "reopened_rate",
            },
            "query_config": {
                "project_keys": [],
                "board_ids": [],
                "issue_types": ["Story", "Bug", "Task"],
            },
        },
        "sales_pipeline": {
            "enabled": True,
            "adapter": "crm",
            "process_name": "Sales Pipeline",
            "process_type": "sales",
            "process_category": "revenue",
            "description": "CRM pipeline — deals, revenue, conversion, cycle time",
            "column_mapping": {
                "revenue_pln": "total_revenue",
                "deals_closed": "deals_won",
                "deals_lost": "deals_lost",
                "conversion_rate": "win_rate",
                "avg_deal_size_pln": "avg_deal_value",
                "avg_sales_cycle_days": "avg_cycle_days",
                "pipeline_value_pln": "pipeline_total",
                "quota_attainment": "quota_pct",
                "throughput": "total_activities",
            },
            "query_config": {
                "pipeline_ids": [],
                "stages": [],
            },
        },
        "customer_support": {
            "enabled": True,
            "adapter": "helpdesk",
            "process_name": "Customer Support",
            "process_type": "customer_service",
            "process_category": "support",
            "description": "Helpdesk tickets — resolution time, CSAT, escalations",
            "column_mapping": {
                "tickets_resolved": "resolved_count",
                "avg_first_response_h": "avg_first_response_hours",
                "avg_resolution_h": "avg_resolution_hours",
                "escalation_rate": "escalation_pct",
                "csat_score": "csat_avg",
                "nps_score": "nps_avg",
                "first_contact_resolution_rate": "fcr_rate",
                "throughput": "tickets_created",
                "overdue_count": "sla_breaches",
            },
            "query_config": {
                "queue_ids": [],
                "priority_filter": [],
            },
        },
        "software_delivery": {
            "enabled": True,
            "adapter": "github_cicd",
            "process_name": "Software Delivery",
            "process_type": "engineering",
            "process_category": "devops",
            "description": "CI/CD metrics — deployments, failure rate, MTTR, coverage",
            "column_mapping": {
                "deployments_count": "total_deployments",
                "deployment_failures": "failed_deployments",
                "change_failure_rate": "failure_rate_pct",
                "mttr_hours": "mean_time_to_restore_h",
                "code_coverage_pct": "coverage_pct",
                "critical_bugs_open": "critical_open",
                "tech_debt_hours": "debt_estimate_hours",
                "throughput": "prs_merged",
                "avg_cycle_time_h": "avg_pr_cycle_hours",
            },
            "query_config": {
                "repos": [],
                "environments": ["production"],
            },
        },
        "department_financials": {
            "enabled": True,
            "adapter": "finance",
            "process_name": "Department Financials",
            "process_type": "finance",
            "process_category": "budgeting",
            "description": "Finance — actuals vs budget, margins, cost per unit",
            "column_mapping": {
                "cost_actual_pln": "actual_cost",
                "cost_budget_pln": "budget_cost",
                "budget_variance_pct": "variance_pct",
                "margin_pct": "gross_margin_pct",
                "cost_per_unit": "unit_cost",
                "revenue_pln": "revenue",
            },
            "query_config": {
                "cost_centers": [],
                "gl_accounts": [],
            },
        },
    }
}


def _ensure_default_config(path: Path) -> None:
    """Write the default YAML config if it does not exist."""
    if path.exists():
        return
    logger.info("process_collector.config.creating_default", path=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.dump(_DEFAULT_SOURCES, fh, default_flow_style=False, sort_keys=False)


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load source definitions from YAML.

    Falls back to the default config bundled with the module.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    env_override = os.getenv("PROCESS_COLLECTOR_CONFIG")
    if env_override:
        path = Path(env_override)

    _ensure_default_config(path)

    with open(path) as fh:
        data = yaml.safe_load(fh) or {}

    sources = data.get("sources", {})
    logger.info(
        "process_collector.config.loaded",
        path=str(path),
        source_count=len(sources),
        enabled=[k for k, v in sources.items() if v.get("enabled", False)],
    )
    return data


def get_enabled_sources(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return only enabled source definitions."""
    return {
        name: src
        for name, src in config.get("sources", {}).items()
        if src.get("enabled", False)
    }
