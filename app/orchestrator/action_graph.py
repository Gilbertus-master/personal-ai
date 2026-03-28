"""
LangGraph StateGraph for Action Pipeline.

States and transitions:
  START → propose → (interrupt) → route_human → execute | reject_node
  execute → route_result → notify_success | notify_failure | escalate
  notify_failure → execute  (retry loop)
  reject_node → END
  notify_success → END
  escalate → END

Checkpointing: every state change persisted to Postgres.
Recovery: after API restart, graph resumes from last checkpoint.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Literal

import structlog
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.postgres import PostgresSaver

from app.orchestrator.state_schema import ActionState
from app.db.postgres import get_pg_connection

load_dotenv()
log = structlog.get_logger("action_graph")

MAX_RETRIES = 3


# ================================================================
# Node functions — wrap existing action_pipeline logic
# ================================================================

def node_propose(state: ActionState) -> dict:
    """Insert into DB and send WhatsApp notification."""
    from app.orchestrator.action_pipeline import _notify_proposal, _ensure_table

    _ensure_table()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # --- DEDUP CHECK ---
            from app.orchestrator.action_pipeline import _find_duplicate_action
            existing_id = _find_duplicate_action(cur, state["action_type"], state["description"])
            if existing_id is not None:
                log.info(
                    "action_graph_dedup_skipped",
                    existing_id=existing_id,
                    action_type=state["action_type"],
                    description=state["description"][:80],
                )
                return {
                    "action_id": existing_id,
                    "status": "pending",
                    "proposed_at": datetime.now(timezone.utc).isoformat(),
                }

            cur.execute(
                """INSERT INTO action_items
                   (action_type, description, draft_params, source, status)
                   VALUES (%s, %s, %s::jsonb, %s, 'pending')
                   RETURNING id""",
                (
                    state["action_type"],
                    state["description"],
                    json.dumps(state["draft_params"], default=str),
                    state["source"],
                ),
            )
            rows = cur.fetchall()
            row = rows[0] if rows else None
        conn.commit()

    if not row:
        raise RuntimeError(f"INSERT action_items returned no row for action_type={state['action_type']}")
    action_id = row[0]

    _notify_proposal(action_id, state["action_type"], state["description"], state["draft_params"])

    log.info("action_proposed", action_id=action_id, type=state["action_type"])

    return {
        "action_id": action_id,
        "status": "pending",
        "proposed_at": datetime.now(timezone.utc).isoformat(),
    }


def node_wait_for_human(state: ActionState) -> dict:
    """HITL node — graph is interrupted before this node.

    When Sebastian responds on WhatsApp, external code calls
    graph.update_state() to inject human_decision, then graph.invoke(None)
    to resume from here.
    """
    log.info("waiting_for_human", action_id=state["action_id"])
    return {}


def node_execute(state: ActionState) -> dict:
    """Execute approved action using existing logic."""
    from app.orchestrator.action_pipeline import _execute_action

    log.info("executing_action",
             action_id=state["action_id"],
             attempt=state.get("retry_count", 0) + 1)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE action_items SET status='approved', decided_at=NOW() WHERE id=%s",
                (state["action_id"],),
            )
        conn.commit()

    result = _execute_action(
        state["action_id"],
        state["action_type"],
        state.get("edit_text") or state["description"],
        state["draft_params"],
    )

    if result.get("status") == "executed":
        return {
            "status": "executed",
            "execution_result": result,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        return {
            "status": "failed",
            "error": result.get("error", "Unknown error"),
            "retry_count": state.get("retry_count", 0) + 1,
        }


def node_reject(state: ActionState) -> dict:
    """Reject action."""
    from app.orchestrator.action_pipeline import reject_action
    reject_action(state["action_id"])
    log.info("action_rejected", action_id=state["action_id"])
    return {"status": "rejected", "decided_at": datetime.now(timezone.utc).isoformat()}


def node_notify_success(state: ActionState) -> dict:
    """Notify about successful execution."""
    from app.orchestrator.action_pipeline import _send_whatsapp
    _send_whatsapp(f"✅ Akcja #{state['action_id']} wykonana pomyślnie.")
    return {"status": "executed"}


def node_notify_failure(state: ActionState) -> dict:
    """Notify about failure, prepare retry."""
    from app.orchestrator.action_pipeline import _send_whatsapp
    attempt = state.get("retry_count", 1)
    _send_whatsapp(
        f"⚠️ Akcja #{state['action_id']} — błąd (próba {attempt}/{MAX_RETRIES}).\n"
        f"Error: {state.get('error', '?')[:200]}\n"
        f"Ponawianie automatycznie..."
    )
    return {}


def node_escalate(state: ActionState) -> dict:
    """Escalate after MAX_RETRIES failed attempts."""
    from app.orchestrator.action_pipeline import _send_whatsapp
    _send_whatsapp(
        f"🔴 Akcja #{state['action_id']} wymaga ręcznej interwencji.\n"
        f"Wszystkie {MAX_RETRIES} próby nieudane.\n"
        f"Ostatni błąd: {state.get('error', '?')[:300]}"
    )
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE action_items SET status='failed' WHERE id=%s",
                (state["action_id"],),
            )
        conn.commit()
    return {"status": "failed"}


# ================================================================
# Conditional routing
# ================================================================

def route_after_human(state: ActionState) -> Literal["execute", "reject_node"]:
    decision = state.get("human_decision", "")
    if decision in ("approve", "edit"):
        return "execute"
    return "reject_node"


def route_after_execute(state: ActionState) -> Literal["notify_success", "notify_failure", "escalate"]:
    if state.get("status") == "executed":
        return "notify_success"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "escalate"
    return "notify_failure"


# ================================================================
# Graph builder
# ================================================================

def build_action_graph(checkpointer=None):
    """Build and compile the Action Pipeline StateGraph."""
    graph = StateGraph(ActionState)

    graph.add_node("propose", node_propose)
    graph.add_node("wait_for_human", node_wait_for_human)
    graph.add_node("execute", node_execute)
    graph.add_node("reject_node", node_reject)
    graph.add_node("notify_success", node_notify_success)
    graph.add_node("notify_failure", node_notify_failure)
    graph.add_node("escalate", node_escalate)

    graph.add_edge(START, "propose")
    graph.add_edge("propose", "wait_for_human")

    graph.add_conditional_edges(
        "wait_for_human",
        route_after_human,
        {"execute": "execute", "reject_node": "reject_node"},
    )

    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "notify_success": "notify_success",
            "notify_failure": "notify_failure",
            "escalate": "escalate",
        },
    )

    # Retry loop
    graph.add_edge("notify_failure", "execute")

    # Terminal nodes
    graph.add_edge("reject_node", END)
    graph.add_edge("notify_success", END)
    graph.add_edge("escalate", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["wait_for_human"],
    )


# ================================================================
# Checkpointed singleton
# ================================================================

_checkpointer_cm = None  # context manager
_checkpointer = None
_graph = None


def _get_db_url() -> str:
    """Build DATABASE_URL from env vars (same as app/db/postgres.py)."""
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "gilbertus")
    user = os.getenv("POSTGRES_USER", "gilbertus")
    password = os.getenv("POSTGRES_PASSWORD", "gilbertus")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_action_graph():
    """Returns compiled ActionGraph with Postgres checkpointer (singleton)."""
    global _checkpointer_cm, _checkpointer, _graph
    if _graph is None:
        db_url = _get_db_url()
        _checkpointer_cm = PostgresSaver.from_conn_string(db_url)
        _checkpointer = _checkpointer_cm.__enter__()
        # Tables created via manual migration (psycopg-binary compat issue with setup())
        # _checkpointer.setup()
        _graph = build_action_graph(checkpointer=_checkpointer)
    return _graph


# ================================================================
# Public API
# ================================================================

def graph_propose_action(
    action_type: str,
    description: str,
    draft_params: dict | None = None,
    source: str = "gilbertus",
) -> dict:
    """Start Action Pipeline via StateGraph. Replaces action_pipeline.propose_action()."""
    import uuid

    graph = get_action_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: ActionState = {
        "action_id": 0,
        "action_type": action_type,
        "description": description,
        "draft_params": draft_params or {},
        "source": source,
        "status": "pending",
        "human_decision": None,
        "edit_text": None,
        "execution_result": None,
        "error": None,
        "proposed_at": None,
        "decided_at": None,
        "executed_at": None,
        "retry_count": 0,
    }

    # Graph runs until interrupt_before wait_for_human
    result = graph.invoke(initial_state, config)
    action_id = result.get("action_id", 0)

    log.info("graph_action_proposed", action_id=action_id, thread_id=thread_id)

    # Store thread_id in DB for later resume
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE action_items SET result = %s WHERE id = %s AND result IS NULL",
                    (json.dumps({"graph_thread_id": thread_id}), action_id),
                )
            conn.commit()
    except Exception as exc:
        log.error("thread_id_store_failed", action_id=action_id, thread_id=thread_id, error=str(exc))

    return {"action_id": action_id, "thread_id": thread_id, "status": "pending"}


def graph_resume_action(action_id: int, decision: str, edit_text: str | None = None) -> dict:
    """Resume graph after Sebastian's decision. Replaces approve_action()/reject_action()."""
    graph = get_action_graph()

    # Get thread_id from DB
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT result FROM action_items WHERE id = %s", (action_id,))
            rows = cur.fetchall()
            row = rows[0] if rows else None

    if not row or not row[0]:
        log.warning("no_thread_id", action_id=action_id)
        return _legacy_fallback(action_id, decision, edit_text)

    try:
        result_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        thread_id = result_data.get("graph_thread_id")
    except Exception:
        thread_id = None

    if not thread_id:
        log.warning("no_thread_id_in_result", action_id=action_id)
        return _legacy_fallback(action_id, decision, edit_text)

    config = {"configurable": {"thread_id": thread_id}}

    # Inject human decision into state
    graph.update_state(
        config,
        {"human_decision": decision, "edit_text": edit_text},
        as_node="wait_for_human",
    )

    # Resume graph
    result = graph.invoke(None, config)

    log.info("graph_action_resumed",
             action_id=action_id,
             decision=decision,
             final_status=result.get("status"))

    return {"action_id": action_id, "status": result.get("status"), "result": result}


def _legacy_fallback(action_id: int, decision: str, edit_text: str | None = None) -> dict:
    """Fallback to legacy pipeline for actions not created via graph."""
    from app.orchestrator.action_pipeline import approve_action, reject_action
    if decision == "reject":
        return reject_action(action_id)
    return approve_action(action_id, edit_text)
