"""Gilbertus /plugins/* endpoints — cross-tenant plugin management for Sebastian."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
import structlog

from app.api.auth import require_api_key
from app.omnius.client import get_omnius, list_tenants

log = structlog.get_logger(__name__)
router = APIRouter(tags=["plugin-dev"], dependencies=[Depends(require_api_key)])


# ── Models ─────────────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    tenant: str


class RejectRequest(BaseModel):
    tenant: str
    reason: str = ""


# ── GET /plugins/proposals — List all proposals across tenants ─────────────

@router.get("/plugins/proposals")
async def list_all_proposals(request: Request, status: str | None = None,
                             tenant: str | None = None):
    """List plugin proposals across all Omnius tenants."""
    tenants = [tenant] if tenant else list_tenants()
    results = []

    for t in tenants:
        try:
            client = get_omnius(t)
            proposals = client.list_proposals(status=status)
            for p in proposals:
                p["tenant"] = t
            results.extend(proposals)
        except Exception as e:
            log.warning("list_proposals_failed", tenant=t, error=str(e))
            continue

    # Sort by created_at descending
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


# ── GET /plugins/proposals/{id}/review — Get review results ───────────────

@router.get("/plugins/proposals/{proposal_id}/review")
async def get_proposal_review(request: Request, proposal_id: int,
                              tenant: str = "reh"):
    """Get review results for a specific proposal."""
    client = get_omnius(tenant)
    return client.get_proposal_review(proposal_id)


# ── POST /plugins/proposals/{id}/approve — Approve proposal ──────────────

@router.post("/plugins/proposals/{proposal_id}/approve")
async def approve_proposal(request: Request, proposal_id: int,
                           body: ApproveRequest):
    """Approve a plugin proposal via Omnius API."""
    client = get_omnius(body.tenant)
    result = client.approve_proposal(proposal_id)
    log.info("gilbertus_plugin_approved", proposal_id=proposal_id,
             tenant=body.tenant)
    return result


# ── POST /plugins/proposals/{id}/reject — Reject proposal ────────────────

@router.post("/plugins/proposals/{proposal_id}/reject")
async def reject_proposal(request: Request, proposal_id: int,
                          body: RejectRequest):
    """Reject a plugin proposal via Omnius API."""
    client = get_omnius(body.tenant)
    result = client.reject_proposal(proposal_id, body.reason)
    log.info("gilbertus_plugin_rejected", proposal_id=proposal_id,
             tenant=body.tenant, reason=body.reason[:100])
    return result
