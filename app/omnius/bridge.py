"""
Gilbertus ↔ Omnius Bridge — cross-tenant operations.

Sebastian sees both REH and REF through one interface.
Bridge provides: cross-tenant search, aggregated reports, unified dashboard.

Security: Gilbertus (admin level 99) has full read access. Omnius tenants
cannot read each other — only Gilbertus aggregates.
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

from datetime import datetime, timezone
from typing import Any

from app.omnius.client import get_omnius, list_tenants


def cross_tenant_search(query: str, answer_length: str = "medium") -> dict[str, Any]:
    """Search across all Omnius tenants and merge results."""
    tenants = list_tenants()
    if not tenants:
        return {"error": "No Omnius tenants configured. Set OMNIUS_*_URL in .env"}

    results = {}
    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            result = client.ask(query, answer_length)
            results[tenant] = {
                "answer": result.get("answer", ""),
                "sources_count": len(result.get("sources", [])),
                "status": "ok",
            }
        except Exception as e:
            results[tenant] = {"answer": "", "status": "error", "error": str(e)}

    # Merge answers
    combined_answers = []
    for tenant, r in results.items():
        if r["status"] == "ok" and r["answer"]:
            combined_answers.append(f"**{tenant.upper()}:** {r['answer']}")

    return {
        "query": query,
        "tenants": results,
        "combined_answer": "\n\n".join(combined_answers) if combined_answers else "Brak wyników z żadnego tenanta.",
        "tenants_queried": len(tenants),
    }


def aggregated_dashboard() -> dict[str, Any]:
    """Unified dashboard across all Omnius tenants."""
    tenants = list_tenants()
    dashboard = {"tenants": {}, "total_documents": 0, "total_users": 0}

    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            health = client.health()
            status = client.status() if health.get("status") == "ok" else {}

            dashboard["tenants"][tenant] = {
                "status": health.get("status", "unknown"),
                "documents": status.get("documents", 0),
                "chunks": status.get("chunks", 0),
                "users": status.get("users", 0),
            }
            dashboard["total_documents"] += status.get("documents", 0)
            dashboard["total_users"] += status.get("users", 0)
        except Exception as e:
            dashboard["tenants"][tenant] = {"status": "error", "error": str(e)}

    return dashboard


def cross_tenant_audit(limit: int = 50) -> dict[str, Any]:
    """Aggregated audit log across all tenants."""
    tenants = list_tenants()
    all_entries = []

    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            audit = client.get_audit_log(limit=limit)
            for entry in (audit if isinstance(audit, list) else audit.get("entries", [])):
                entry["tenant"] = tenant
                all_entries.append(entry)
        except Exception as e:
            log.warning("audit_fetch_failed", tenant=tenant, error=str(e))

    # Sort by timestamp
    all_entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)

    return {"entries": all_entries[:limit], "total": len(all_entries)}


def cross_tenant_operator_tasks() -> dict[str, Any]:
    """All pending operator tasks across tenants."""
    tenants = list_tenants()
    all_tasks = []

    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            tasks = client.list_operator_tasks("pending")
            for task in (tasks if isinstance(tasks, list) else tasks.get("tasks", [])):
                task["tenant"] = tenant
                all_tasks.append(task)
        except Exception as e:
            log.warning("tasks_fetch_failed", tenant=tenant, error=str(e))

    return {"tasks": all_tasks, "total": len(all_tasks)}


def sync_all_tenants() -> dict[str, Any]:
    """Trigger sync on all tenants."""
    tenants = list_tenants()
    results = {}

    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            result = client.trigger_sync("all")
            results[tenant] = {"status": "triggered", "result": result}
        except Exception as e:
            results[tenant] = {"status": "error", "error": str(e)}

    return results


def get_cross_company_insights() -> dict[str, Any]:
    """Generate cross-company insights for Sebastian's morning brief."""
    tenants = list_tenants()
    insights = []

    for tenant in tenants:
        try:
            client = get_omnius(tenant)
            # Get nightly report if available
            report = client.get_nightly_report()
            if report and not isinstance(report, dict) or not report.get("error"):
                insights.append({
                    "tenant": tenant,
                    "report": report if isinstance(report, dict) else {"summary": str(report)},
                })
        except Exception:
            pass

    return {
        "insights": insights,
        "tenants_reporting": len(insights),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
