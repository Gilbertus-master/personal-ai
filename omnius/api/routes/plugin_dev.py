"""Omnius /plugin-dev/* endpoints — plugin proposal, sandbox dev, review pipeline."""
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from omnius.api.rbac import require_permission, audit_log
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/plugin-dev", tags=["plugin-dev"])


# ── Models ─────────────────────────────────────────────────────────────────

class ProposeRequest(BaseModel):
    title: str
    description: str
    expected_value: str


class ApproveRejectRequest(BaseModel):
    reason: str = ""


# ── POST /propose — Submit plugin proposal ─────────────────────────────────

@router.post("/propose")
@require_permission("plugins:propose")
async def propose_plugin(request: Request, body: ProposeRequest, user: dict = None):
    """Submit a plugin proposal. Runs two-stage governance evaluation."""
    from omnius.core.plugin_governance import two_stage_evaluation

    proposal_text = (
        f"Tytul: {body.title}\n"
        f"Opis: {body.description}\n"
        f"Oczekiwana wartosc: {body.expected_value}"
    )

    governance_result = two_stage_evaluation(proposal_text, user)

    overall_approved = governance_result.get("overall_approved", False)
    value_score = governance_result.get("overall_score", 0.0)

    # Determine status
    if overall_approved:
        status = "approved"
    elif 0.5 <= value_score <= 0.7:
        status = "pending"
    else:
        status = "rejected"

    # Store proposal in DB
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_plugin_proposals
                    (title, description, expected_value, proposed_by,
                     proposed_by_email, status, value_score, governance_result)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                body.title,
                body.description,
                body.expected_value,
                user.get("user_id"),
                user.get("email", user.get("api_key_name", "unknown")),
                status,
                value_score,
                json.dumps(governance_result),
            ))
            row = cur.fetchone()
            proposal_id = row[0]
            created_at = row[1]
        conn.commit()

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_propose", resource=f"proposal:{proposal_id}",
              request_summary={"title": body.title, "status": status},
              ip_address=ip)

    log.info("plugin_proposed", id=proposal_id, title=body.title,
             status=status, score=value_score,
             by=user.get("email", user.get("api_key_name")))

    return {
        "id": proposal_id,
        "title": body.title,
        "status": status,
        "governance_result": governance_result,
        "value_score": value_score,
        "created_at": str(created_at),
    }


# ── GET /proposals — List proposals ────────────────────────────────────────

@router.get("/proposals")
@require_permission("plugins:propose")
async def list_proposals(request: Request, status: str | None = None, user: dict = None):
    """List plugin proposals. Scope depends on role level."""
    role_level = user.get("role_level", 0)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if role_level >= 99:
                # gilbertus_admin: all proposals
                if status:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        WHERE status = %s
                        ORDER BY created_at DESC
                    """, (status,))
                else:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        ORDER BY created_at DESC
                    """)
            elif role_level >= 60:
                # ceo: all proposals for this tenant
                if status:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        WHERE status = %s
                        ORDER BY created_at DESC
                    """, (status,))
                else:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        ORDER BY created_at DESC
                    """)
            else:
                # regular user: only own proposals
                user_email = user.get("email", "")
                if status:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        WHERE proposed_by_email = %s AND status = %s
                        ORDER BY created_at DESC
                    """, (user_email, status))
                else:
                    cur.execute("""
                        SELECT id, title, status, value_score, proposed_by_email, created_at
                        FROM omnius_plugin_proposals
                        WHERE proposed_by_email = %s
                        ORDER BY created_at DESC
                    """, (user_email,))

            return [
                {
                    "id": r[0], "title": r[1], "status": r[2],
                    "value_score": float(r[3]) if r[3] is not None else None,
                    "proposed_by": r[4], "created_at": str(r[5]),
                }
                for r in cur.fetchall()
            ]


# ── GET /proposals/{id} — Proposal details ─────────────────────────────────

@router.get("/proposals/{proposal_id}")
@require_permission("plugins:propose")
async def get_proposal(request: Request, proposal_id: int, user: dict = None):
    """Get full proposal details including governance result."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, description, expected_value,
                       proposed_by_email, status, value_score,
                       governance_result, sandbox_session_id,
                       review_result, created_at
                FROM omnius_plugin_proposals
                WHERE id = %s
            """, (proposal_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "error": "Proposal not found"}

            return {
                "id": row[0], "title": row[1], "description": row[2],
                "expected_value": row[3], "proposed_by": row[4],
                "status": row[5],
                "value_score": float(row[6]) if row[6] is not None else None,
                "governance_result": row[7],
                "sandbox_session_id": row[8],
                "review_result": row[9],
                "created_at": str(row[10]),
            }


# ── POST /proposals/{id}/approve — Approve proposal (Gilbertus/CEO) ───────

@router.post("/proposals/{proposal_id}/approve")
@require_permission("plugins:propose")
async def approve_proposal(request: Request, proposal_id: int, user: dict = None):
    """Approve a pending proposal. Requires role_level >= 60."""
    role_level = user.get("role_level", 0)
    if role_level < 60:
        return {"status": "error", "error": "Insufficient permissions to approve"}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE omnius_plugin_proposals
                SET status = 'approved'
                WHERE id = %s AND status = 'pending'
                RETURNING id
            """, (proposal_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "error": "Proposal not found or not pending"}
        conn.commit()

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_approve", resource=f"proposal:{proposal_id}",
              ip_address=ip)

    log.info("plugin_approved", id=proposal_id,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "approved", "proposal_id": proposal_id}


# ── POST /proposals/{id}/reject — Reject proposal ─────────────────────────

@router.post("/proposals/{proposal_id}/reject")
@require_permission("plugins:propose")
async def reject_proposal(request: Request, proposal_id: int,
                          body: ApproveRejectRequest, user: dict = None):
    """Reject a proposal. Requires role_level >= 60."""
    role_level = user.get("role_level", 0)
    if role_level < 60:
        return {"status": "error", "error": "Insufficient permissions to reject"}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE omnius_plugin_proposals
                SET status = 'rejected',
                    governance_result = COALESCE(governance_result, '{}'::jsonb) ||
                        jsonb_build_object('rejection_reason', %s)
                WHERE id = %s AND status IN ('pending', 'approved')
                RETURNING id
            """, (body.reason, proposal_id))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "error": "Proposal not found or already processed"}
        conn.commit()

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_reject", resource=f"proposal:{proposal_id}",
              request_summary={"reason": body.reason}, ip_address=ip)

    log.info("plugin_rejected", id=proposal_id, reason=body.reason,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "rejected", "proposal_id": proposal_id}


# ── POST /proposals/{id}/start-dev — Create sandbox ───────────────────────

@router.post("/proposals/{proposal_id}/start-dev")
@require_permission("plugins:propose")
async def start_dev(request: Request, proposal_id: int, user: dict = None):
    """Create a sandbox and start plugin development."""
    from omnius.core.sandbox import SandboxManager

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, status FROM omnius_plugin_proposals
                WHERE id = %s
            """, (proposal_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "error": "Proposal not found"}
            if row[2] != "approved":
                return {"status": "error", "error": f"Proposal status is '{row[2]}', must be 'approved'"}

            title = row[1]

    session_id = str(uuid.uuid4())[:12]
    plugin_name = title.lower().replace(" ", "_")[:30]

    sandbox_mgr = SandboxManager()
    sandbox_info = sandbox_mgr.create_sandbox(session_id, plugin_name)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE omnius_plugin_proposals
                SET status = 'developing', sandbox_session_id = %s
                WHERE id = %s
            """, (session_id, proposal_id))
        conn.commit()

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_start_dev", resource=f"proposal:{proposal_id}",
              request_summary={"session_id": session_id}, ip_address=ip)

    log.info("plugin_dev_started", proposal_id=proposal_id,
             session_id=session_id, plugin_name=plugin_name,
             by=user.get("email", user.get("api_key_name")))

    return {
        "status": "developing",
        "proposal_id": proposal_id,
        "sandbox": sandbox_info,
    }


# ── POST /proposals/{id}/submit — Submit for review ───────────────────────

@router.post("/proposals/{proposal_id}/submit")
@require_permission("plugins:propose")
async def submit_for_review(request: Request, proposal_id: int, user: dict = None):
    """Collect sandbox output, run review, and submit for human approval."""
    from omnius.core.sandbox import SandboxManager
    from omnius.core.plugin_review import review_plugin
    from pathlib import Path
    import tarfile
    import io
    import tempfile

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, status, sandbox_session_id
                FROM omnius_plugin_proposals
                WHERE id = %s
            """, (proposal_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "error", "error": "Proposal not found"}
            if row[2] != "developing":
                return {"status": "error", "error": f"Proposal status is '{row[2]}', must be 'developing'"}
            session_id = row[3]
            if not session_id:
                return {"status": "error", "error": "No sandbox session associated"}

    sandbox_mgr = SandboxManager()

    # Collect output
    archive_bytes = sandbox_mgr.collect_output(session_id)
    if not archive_bytes:
        return {"status": "error", "error": "No output from sandbox"}

    # Extract to temp dir and run review
    review_result_data: dict[str, Any] = {}
    review_passed = False

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            buf = io.BytesIO(archive_bytes)
            with tarfile.open(fileobj=buf, mode="r:*") as tar:
                tar.extractall(path=str(tmpdir_path), filter="data")

            # review_plugin expects the plugin directory
            plugin_dir = tmpdir_path
            # If output/ subdirectory exists, use that
            if (tmpdir_path / "output").is_dir():
                plugin_dir = tmpdir_path / "output"

            result = review_plugin(plugin_dir)
            review_passed = result.passed
            review_result_data = {
                "passed": result.passed,
                "security_score": result.security_score,
                "quality_score": result.quality_score,
                "tests_passed": result.tests_passed,
                "tests_total": result.tests_total,
                "findings": [
                    {
                        "severity": f.severity,
                        "category": f.category,
                        "title": f.title,
                        "description": f.description,
                        "file": f.file,
                        "line": f.line,
                    }
                    for f in result.findings
                ],
            }
    except Exception as e:
        log.error("plugin_review_failed", error=str(e), proposal_id=proposal_id)
        review_result_data = {"passed": False, "error": str(e), "findings": []}

    new_status = "reviewing" if review_passed else "developing"

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE omnius_plugin_proposals
                SET status = %s, review_result = %s
                WHERE id = %s
            """, (new_status, json.dumps(review_result_data), proposal_id))
        conn.commit()

    # Destroy sandbox and notify if review passed
    if review_passed:
        try:
            sandbox_mgr.destroy_sandbox(session_id)
        except Exception as e:
            log.warning("sandbox_destroy_after_review_failed", error=str(e))

        # Notify Sebastian via operator task
        try:
            import os
            from omnius.core.plugin_notifications import notify_plugin_ready_for_review
            await notify_plugin_ready_for_review(
                plugin_name=row[1],  # title used as plugin name
                proposed_by=user.get("email", user.get("api_key_name", "unknown")),
                review_score=review_result_data.get("quality_score", 0.0),
                tenant=os.getenv("OMNIUS_TENANT", "unknown"),
            )
        except Exception as e:
            log.warning("plugin_review_notify_failed", error=str(e))

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_submit_review", resource=f"proposal:{proposal_id}",
              request_summary={"passed": review_passed}, ip_address=ip)

    log.info("plugin_submitted", proposal_id=proposal_id,
             passed=review_passed, status=new_status,
             by=user.get("email", user.get("api_key_name")))

    return {
        "status": new_status,
        "review_result": review_result_data,
    }


# ── WebSocket /ws/{session_id} — Stream sandbox I/O ──────────────────────

@router.websocket("/ws/{session_id}")
async def sandbox_ws(websocket: WebSocket, session_id: str):
    """WebSocket for interactive sandbox communication."""
    from omnius.core.sandbox import SandboxManager

    await websocket.accept()

    # Authenticate via query param or first message
    from omnius.api.auth import _auth_api_key

    api_key = websocket.query_params.get("api_key")
    if not api_key:
        try:
            first_msg = await websocket.receive_text()
            data = json.loads(first_msg)
            api_key = data.get("api_key", "")
        except Exception:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return

    try:
        _auth_api_key(api_key)
    except Exception:
        await websocket.send_json({"error": "Invalid API key"})
        await websocket.close()
        return

    # Verify session belongs to user
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM omnius_plugin_proposals
                WHERE sandbox_session_id = %s
            """, (session_id,))
            if not cur.fetchone():
                await websocket.send_json({"error": "Session not found"})
                await websocket.close()
                return

    sandbox_mgr = SandboxManager()
    await websocket.send_json({"status": "connected", "session_id": session_id})

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                command = data.get("command", "")
            except json.JSONDecodeError:
                command = msg

            if not command:
                await websocket.send_json({"error": "Empty command"})
                continue

            # Stream output
            output_parts = []
            async for chunk in sandbox_mgr.exec_in_sandbox(session_id, command):
                output_parts.append(chunk)
                await websocket.send_json({"type": "output", "data": chunk})

            await websocket.send_json({
                "type": "done",
                "command": command,
                "output": "".join(output_parts),
            })

    except WebSocketDisconnect:
        log.info("sandbox_ws_disconnected", session_id=session_id)
    except Exception as e:
        log.error("sandbox_ws_error", error=str(e), session_id=session_id)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
