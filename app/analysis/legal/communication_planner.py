"""
Communication Planner — planowanie i egzekucja komunikacji compliance.

Workflow:
1. Generuj plan komunikacji z RACI matrix i action_plan
2. Waliduj scope via standing_orders
3. Egzekwuj komunikację przez istniejące kanały (email/Teams/WhatsApp)
4. Trackuj delivery i confirmation
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import date, datetime
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)


# ================================================================
# RACI Management
# ================================================================

def set_raci(
    area_code: str | None = None,
    matter_id: int | None = None,
    person_id: int = 0,
    role: str = "informed",
    notes: str | None = None,
) -> dict[str, Any]:
    """Dodaje wpis RACI. INSERT ... ON CONFLICT DO UPDATE."""
    if role not in ("responsible", "accountable", "consulted", "informed"):
        return {"error": "invalid_role", "hint": "Must be: responsible, accountable, consulted, informed"}
    if not person_id:
        return {"error": "person_id_required"}

    area_id = None
    if area_code:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM compliance_areas WHERE code = %s", (area_code.upper(),))
                row = cur.fetchone()
                if not row:
                    return {"error": "area_not_found", "code": area_code}
                area_id = row[0]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO compliance_raci (area_id, matter_id, obligation_id, person_id, role, notes)
                VALUES (%s, %s, NULL, %s, %s, %s)
                ON CONFLICT (area_id, matter_id, obligation_id, person_id, role)
                DO UPDATE SET notes = EXCLUDED.notes
                RETURNING id
            """, (area_id, matter_id, person_id, role, notes))
            raci_id = cur.fetchone()[0]
        conn.commit()

    log.info("raci_set", raci_id=raci_id, person_id=person_id, role=role,
             area_code=area_code, matter_id=matter_id)
    return {"raci_id": raci_id, "person_id": person_id, "role": role}


def get_raci(
    matter_id: int | None = None,
    area_code: str | None = None,
) -> list[dict[str, Any]]:
    """Pobierz RACI matrix. JOIN z people na imię/nazwisko."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT r.id, r.area_id, a.code AS area_code, r.matter_id,
                       r.person_id, r.role, r.notes,
                       p.full_name AS person_name
                FROM compliance_raci r
                LEFT JOIN compliance_areas a ON a.id = r.area_id
                LEFT JOIN people p ON p.id = r.person_id
                WHERE 1=1
            """
            params: list[Any] = []
            if matter_id is not None:
                sql += " AND r.matter_id = %s"
                params.append(matter_id)
            if area_code:
                sql += " AND a.code = %s"
                params.append(area_code.upper())
            sql += " ORDER BY r.role, p.full_name"
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "area_id": r[1], "area_code": r[2], "matter_id": r[3],
            "person_id": r[4], "role": r[5], "notes": r[6], "person_name": r[7],
        }
        for r in rows
    ]


# ================================================================
# Communication Plan Generation
# ================================================================

def generate_communication_plan(matter_id: int) -> dict[str, Any]:
    """Generuje plan komunikacji na bazie RACI matrix, action_plan i area."""

    # 1. Fetch matter
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.title, m.action_plan, a.code AS area_code, a.name_pl AS area_name
                FROM compliance_matters m
                LEFT JOIN compliance_areas a ON a.id = m.area_id
                WHERE m.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    title = row[1]
    action_plan = row[2] or []
    area_code = row[3] or "UNKNOWN"
    area_name = row[4] or area_code

    # 2. Fetch RACI entries
    raci_entries = get_raci(matter_id=matter_id)
    if not raci_entries:
        # Try area-level RACI
        raci_entries = get_raci(area_code=area_code)

    raci_text = "\n".join(
        "- {} ({})".format(r["person_name"] or "person_id={}".format(r["person_id"]), r["role"])
        for r in raci_entries
    ) if raci_entries else "Brak wpisów RACI — wygeneruj na podstawie ról w action_plan."

    action_plan_text = json.dumps(action_plan, ensure_ascii=False, indent=2) if action_plan else "Brak action_plan"

    # 3. Call Claude
    prompt = f"""Na podstawie sprawy compliance i macierzy RACI, wygeneruj plan komunikacji.
Sprawa: {title}
Obszar: {area_name} ({area_code})
RACI:
{raci_text}
Action plan:
{action_plan_text[:3000]}

Dla każdego interesariusza określ:
- Kogo poinformować (imię, rola RACI)
- O czym (treść komunikatu — 2-3 zdania)
- Jakim kanałem (email dla formalnych, Teams dla operacyjnych, WhatsApp dla pilnych)
- Kiedy (data YYYY-MM-DD lub "natychmiast" / "po zatwierdzeniu" / "po szkoleniu")
- Cel (inform/request_action/request_signature/train)

Dzisiejsza data: {date.today().isoformat()}

Zwróć TYLKO JSON array (bez markdown):
[{{"recipient_name": "...", "recipient_role": "responsible|accountable|consulted|informed", "channel": "email|teams|whatsapp", "subject": "...", "content": "...", "when": "YYYY-MM-DD lub opis", "purpose": "inform|request_action|request_signature|train"}}]"""

    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    plan_text = resp.content[0].text.strip()
    log_anthropic_cost(ANTHROPIC_MODEL, "compliance_comm_plan", resp.usage)

    # Parse JSON
    try:
        if plan_text.startswith("```"):
            plan_text = plan_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        communications = json.loads(plan_text)
    except json.JSONDecodeError:
        log.warning("comm_plan_parse_failed", matter_id=matter_id, raw=plan_text[:200])
        communications = []

    if not communications:
        return {"error": "no_communications_generated", "matter_id": matter_id}

    # 4. Resolve person_ids and INSERT
    inserted = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for comm in communications:
                # Try to resolve person_id from name
                person_id = None
                recipient_name = comm.get("recipient_name", "")
                if recipient_name:
                    cur.execute(
                        "SELECT id FROM people WHERE full_name ILIKE %s LIMIT 1",
                        (f"%{recipient_name}%",),
                    )
                    prow = cur.fetchone()
                    if prow:
                        person_id = prow[0]

                # Parse scheduled_date
                when = comm.get("when", "")
                scheduled_date = None
                try:
                    scheduled_date = datetime.strptime(when, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    if "natychmiast" in when.lower() or "immediately" in when.lower():
                        scheduled_date = date.today()

                cur.execute("""
                    INSERT INTO compliance_communications
                    (matter_id, recipient_person_id, recipient_name, recipient_role,
                     channel, subject, content, purpose, scheduled_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'planned')
                    RETURNING id
                """, (
                    matter_id, person_id, recipient_name,
                    comm.get("recipient_role", "informed"),
                    comm.get("channel", "email"),
                    comm.get("subject", title),
                    comm.get("content", ""),
                    comm.get("purpose", "inform"),
                    scheduled_date,
                ))
                cc_id = cur.fetchone()[0]
                inserted.append({
                    "id": cc_id, "recipient": recipient_name,
                    "channel": comm.get("channel"), "purpose": comm.get("purpose"),
                    "scheduled_date": str(scheduled_date) if scheduled_date else when,
                })

            # 5. Update matter communication_plan
            cur.execute("""
                UPDATE compliance_matters
                SET communication_plan = %s::jsonb, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(communications, ensure_ascii=False), matter_id))
        conn.commit()

    log.info("comm_plan_generated", matter_id=matter_id, count=len(inserted))
    return {
        "matter_id": matter_id,
        "communications_planned": len(inserted),
        "details": inserted,
    }


# ================================================================
# Communication Plan Execution
# ================================================================

def execute_communication_plan(matter_id: int) -> dict[str, Any]:
    """Egzekwuje zaplanowaną komunikację."""
    from app.orchestrator.communication import check_scope, send_and_log

    # 1. Fetch planned communications due today or earlier
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, recipient_person_id, recipient_name, channel,
                       subject, content, purpose
                FROM compliance_communications
                WHERE matter_id = %s
                  AND status = 'planned'
                  AND (scheduled_date IS NULL OR scheduled_date <= CURRENT_DATE)
                ORDER BY id
            """, (matter_id,))
            rows = cur.fetchall()

    if not rows:
        return {"matter_id": matter_id, "sent": 0, "pending_approval": 0, "failed": 0,
                "message": "No planned communications due"}

    sent = 0
    pending_approval = 0
    failed = 0

    for row in rows:
        cc_id, person_id, recipient_name, channel, subject, content, purpose = row

        # Resolve recipient address
        recipient = _resolve_recipient(person_id, recipient_name, channel)
        if not recipient:
            log.warning("comm_recipient_unresolved", cc_id=cc_id, name=recipient_name, channel=channel)
            _update_comm_status(cc_id, "failed")
            failed += 1
            continue

        # 2a. Check scope
        scope_result = check_scope(channel, recipient, subject or "compliance")
        if scope_result.get("allowed"):
            # 2b. Send
            try:
                send_result = send_and_log(
                    channel=channel,
                    recipient=recipient,
                    subject=subject,
                    body=content,
                    authorization_type="compliance",
                    standing_order_id=scope_result.get("order_id"),
                )
                comm_id = send_result.get("comm_id")
                _update_comm_status(cc_id, "sent", comm_id=comm_id)
                sent += 1
                log.info("comm_sent", cc_id=cc_id, channel=channel, recipient=recipient_name)
            except Exception as exc:
                log.error("comm_send_failed", cc_id=cc_id, error=str(exc))
                _update_comm_status(cc_id, "failed")
                failed += 1
        else:
            # 2c. No standing order → propose for approval
            try:
                from app.orchestrator.action_pipeline import propose_action
                propose_action(
                    action=f"Wyślij komunikat compliance ({channel}) do {recipient_name}: {subject}",
                    reason=f"Compliance communication for matter #{matter_id}, purpose: {purpose}",
                    authority_level=2,
                    auto_execute=False,
                )
                _update_comm_status(cc_id, "pending_approval")
                pending_approval += 1
                log.info("comm_pending_approval", cc_id=cc_id, reason=scope_result.get("reason"))
            except Exception as exc:
                log.error("comm_propose_failed", cc_id=cc_id, error=str(exc))
                _update_comm_status(cc_id, "failed")
                failed += 1

    log.info("comm_plan_executed", matter_id=matter_id, sent=sent,
             pending_approval=pending_approval, failed=failed)
    return {"matter_id": matter_id, "sent": sent, "pending_approval": pending_approval, "failed": failed}


def _resolve_recipient(person_id: int | None, name: str, channel: str) -> str | None:
    """Resolve person_id/name to channel-specific address."""
    if not person_id:
        return None
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT full_name, email FROM people WHERE id = %s", (person_id,))
            row = cur.fetchone()
    if not row:
        return None
    full_name, email = row[0], row[1]
    if channel == "email" and email:
        return email
    if channel == "teams" and email:
        return email  # Teams uses UPN/email
    if channel == "whatsapp":
        # WhatsApp needs phone — try people metadata or fall back to name
        return full_name
    return email or full_name


def _update_comm_status(cc_id: int, status: str, comm_id: int | None = None) -> None:
    """Update compliance_communications status."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if status == "sent":
                cur.execute("""
                    UPDATE compliance_communications
                    SET status = 'sent', sent_communication_id = %s, sent_at = NOW()
                    WHERE id = %s
                """, (comm_id, cc_id))
            else:
                cur.execute("""
                    UPDATE compliance_communications SET status = %s WHERE id = %s
                """, (status, cc_id))
        conn.commit()
