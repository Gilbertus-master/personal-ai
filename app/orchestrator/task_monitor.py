"""
WhatsApp Task Orchestrator for Gilbertus Albans.

Monitors WhatsApp messages in real-time. When Sebastian sends a message
that implies a task (not just a question), creates a task, executes it,
and reports back on WhatsApp.

Runs as daemon via cron every 2 minutes.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
OPENCLAW_BIN = os.path.expanduser("~/.npm-global/bin/openclaw")
SESSIONS_DIR = Path(os.path.expanduser("~/.openclaw/agents/main/sessions"))
STATE_FILE = Path("/home/sebastian/personal-ai/.task_monitor_state.json")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_processed_line": 0, "last_session": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_latest_session() -> Path | None:
    """Find the most recent OpenClaw session file."""
    if not SESSIONS_DIR.exists():
        return None
    sessions = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0] if sessions else None


def get_new_messages(session_file: Path, last_line: int) -> list[dict]:
    """Read new user messages from session JSONL."""
    messages = []
    with open(session_file) as f:
        for i, line in enumerate(f):
            if i <= last_line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") != "message":
                continue

            msg = entry.get("message", {})
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                text = "\n".join(texts)
            else:
                text = str(content)

            # Extract actual message from WhatsApp metadata
            if "self):" in text:
                try:
                    text = text.split("self):", 1)[1].strip()
                except Exception:
                    pass

            if text.strip():
                messages.append({"line": i, "text": text.strip(), "timestamp": entry.get("timestamp")})

    return messages


def classify_message(text: str) -> dict:
    """Classify message. Tasks require explicit keyword 'Gilbertusie task:'."""
    text_lower = text.lower().strip()

    # Explicit keywords:
    # "Gilbertusie task:" / "gilbertus task:" — new task to execute
    # "gtd:" — task discovery / doprecyzowanie / przemyślenie do zapisania
    # "decision:" / "decyzja:" — log decision to decision journal
    TASK_KEYWORDS = ["gilbertusie task:", "gilbertus task:"]
    GTD_KEYWORDS = ["gtd:"]
    DECISION_KEYWORDS = ["decision:", "decyzja:"]

    # Quick query commands — return data instantly, no AI needed
    QUERY_COMMANDS = {
        "brief": "brief", "poranny brief": "brief", "morning brief": "brief",
        "market": "market", "rynek": "market", "energia": "market",
        "competitors": "competitors", "konkurencja": "competitors", "konkurenci": "competitors",
        "status": "status", "stan systemu": "status", "gilbertus status": "status",
        "scenarios": "scenarios", "scenariusze": "scenarios",
        "alerts": "alerts", "alerty": "alerts",
    }
    for cmd_prefix, cmd_type in QUERY_COMMANDS.items():
        if text_lower == cmd_prefix or text_lower.startswith(cmd_prefix + " "):
            return {"type": "query_command", "command": cmd_type, "text": text}

    # Communication commands: authorize, revoke, list orders, digest
    COMM_COMMANDS = ["authorize:", "revoke #", "list orders", "lista zlecen", "standing orders", "digest", "raport", "co wyslales", "authority ", "outcome #", "skip #", "remind #", "cancel #", "extend #"]
    is_comm = any(text_lower.startswith(c) for c in COMM_COMMANDS)
    if is_comm:
        return {"type": "communication_command", "text": text}

    # Action approval keywords
    APPROVAL_PATTERNS = ["tak #", "nie #", "approve #", "reject #", "yes #", "no #", "edit #", "zmien #"]
    is_approval = any(text_lower.startswith(p) for p in APPROVAL_PATTERNS)

    # Feedback keywords: "+1", "-1", "👍", "👎"
    POSITIVE_FEEDBACK = ["+1", "\U0001f44d", "super", "dobrze", "ok gilbertus"]
    NEGATIVE_FEEDBACK = ["-1", "\U0001f44e", "zle", "źle", "nie to", "blad"]
    is_positive = any(text_lower.startswith(p) or text_lower == p for p in POSITIVE_FEEDBACK)
    is_negative = any(text_lower.startswith(p) or text_lower == p for p in NEGATIVE_FEEDBACK)
    if is_positive or is_negative:
        return {"type": "feedback_rating", "rating": 1 if is_positive else -1, "text": text}

    is_task = any(kw in text_lower for kw in TASK_KEYWORDS)
    is_gtd = any(kw in text_lower for kw in GTD_KEYWORDS)
    is_decision = any(kw in text_lower for kw in DECISION_KEYWORDS)

    if is_approval:
        return {"type": "approval", "text": text}

    if is_decision:
        for keyword in DECISION_KEYWORDS:
            if keyword in text_lower:
                idx = text_lower.index(keyword)
                decision_text = text[idx + len(keyword):].strip()
                break

        # Use AI to extract context and area
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=200,
            temperature=0,
            system=[{"type": "text", "text": 'Przeanalizuj decyzję. Odpowiedz JSON: {"area": "business/trading/relationships/wellbeing/general", "context": "dlaczego ta decyzja została podjęta (1 zdanie)", "expected_outcome": "oczekiwany rezultat (1 zdanie)", "confidence": 0.5}', "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": decision_text[:500]}],
        )
        from app.db.cost_tracker import log_anthropic_cost
        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "orchestrator.task_monitor", response.usage)

        try:
            meta = json.loads(response.content[0].text.strip())
        except Exception:
            meta = {"area": "general", "context": "", "expected_outcome": "", "confidence": 0.5}

        return {
            "type": "decision",
            "decision_text": decision_text,
            "area": meta.get("area", "general"),
            "context": meta.get("context", ""),
            "expected_outcome": meta.get("expected_outcome", ""),
            "confidence": meta.get("confidence", 0.5),
        }

    if is_task or is_gtd:
        # Extract description after keyword
        all_keywords = TASK_KEYWORDS + GTD_KEYWORDS
        for keyword in all_keywords:
            if keyword in text_lower:
                idx = text_lower.index(keyword)
                task_desc = text[idx + len(keyword):].strip()
                break

        # Use AI only to classify priority and area
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=100,
            temperature=0,
            system=[{"type": "text", "text": 'Klasyfikuj zadanie. Odpowiedz JSON: {"priority": "high/medium/low", "area": "business/trading/technical/general"}', "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": task_desc[:300]}],
        )
        from app.db.cost_tracker import log_anthropic_cost
        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "orchestrator.task_monitor", response.usage)

        try:
            meta = json.loads(response.content[0].text.strip())
        except Exception:
            meta = {"priority": "medium", "area": "general"}

        return {
            "type": "task" if is_task else "gtd",
            "task_description": task_desc,
            "priority": meta.get("priority", "medium"),
            "area": meta.get("area", "general"),
        }

    # Everything else — not a task, skip (Gilbertus on WhatsApp handles questions directly)
    return {"type": "chat"}



def create_task_in_db(description: str, priority: str, area: str, source_text: str) -> int:
    """Create a task record in the database."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Create tasks table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wa_tasks (
                    id BIGSERIAL PRIMARY KEY,
                    description TEXT NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    area TEXT DEFAULT 'general',
                    source_text TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)
            cur.execute(
                """INSERT INTO wa_tasks (description, priority, area, source_text, status)
                   VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
                (description, priority, area, source_text),
            )
            rows = cur.fetchall()
        conn.commit()
    return rows[0][0]


def execute_task(task_id: int, description: str, area: str) -> str:
    """Execute a task using Gilbertus API or direct action."""
    import requests

    API = os.getenv("GILBERTUS_API_URL", "http://127.0.0.1:8000")

    # Most tasks = ask Gilbertus to analyze/search
    try:
        r = requests.post(
            f"{API}/ask",
            json={"query": description, "answer_length": "medium"},
            timeout=90,
        )
        if r.status_code == 200:
            answer = r.json().get("answer", "Brak odpowiedzi")
            return answer[:1500]
    except Exception:
        pass

    return "Nie udało się wykonać zadania automatycznie. Wymaga ręcznej interwencji."


def send_whatsapp(message: str):
    """Send message to Sebastian via WhatsApp."""
    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", os.getenv("WA_TARGET", "+48505441635"), "--message", message],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


def update_task_status(task_id: int, status: str, result: str):
    """Update task in DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE wa_tasks SET status = %s, result = %s, completed_at = NOW()
                   WHERE id = %s""",
                (status, result, task_id),
            )
        conn.commit()


def _handle_approval_with_graph(text: str) -> dict | None:
    """Try LangGraph resume first, fallback to legacy pipeline."""
    import re
    text_lower = text.lower().strip()

    # Parse approval patterns
    match = re.match(r"(?:tak|approve|yes)\s+#?(\d+)", text_lower)
    if match:
        action_id = int(match.group(1))
        try:
            from app.orchestrator.action_graph import graph_resume_action
            return graph_resume_action(action_id, "approve")
        except Exception as e:
            log.warning("graph_resume_failed", error=str(e), fallback=True)
            from app.orchestrator.action_pipeline import approve_action
            return approve_action(action_id)

    match = re.match(r"(?:nie|reject|no)\s+#?(\d+)", text_lower)
    if match:
        action_id = int(match.group(1))
        try:
            from app.orchestrator.action_graph import graph_resume_action
            return graph_resume_action(action_id, "reject")
        except Exception:
            from app.orchestrator.action_pipeline import reject_action
            return reject_action(action_id)

    match = re.match(r"(?:edit|zmien|zmień)\s+#?(\d+):\s*(.+)", text_lower, re.DOTALL)
    if match:
        action_id, edit_text = int(match.group(1)), match.group(2).strip()
        try:
            from app.orchestrator.action_graph import graph_resume_action
            return graph_resume_action(action_id, "edit", edit_text)
        except Exception:
            from app.orchestrator.action_pipeline import approve_action
            return approve_action(action_id, edit_text)

    # Fallback to legacy parser
    from app.orchestrator.action_pipeline import handle_approval_message
    return handle_approval_message(text)


def process_new_messages():
    """Main loop: check for new messages, classify, execute tasks."""
    state = load_state()
    session = get_latest_session()

    if not session:
        return

    session_id = session.stem
    last_line = state.get("last_processed_line", 0) if state.get("last_session") == session_id else 0

    messages = get_new_messages(session, last_line)
    if not messages:
        return

    log.info("{len(messages)} new messages")

    for msg in messages:
        text = msg["text"]
        classification = classify_message(text)
        msg_type = classification.get("type", "chat")

        log.info("[{msg_type}] {text[:60]}...")

        if msg_type == "task":
            desc = classification.get("task_description", text)
            priority = classification.get("priority", "medium")
            area = classification.get("area", "general")

            # Dedup: check if identical task was created in last hour
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM wa_tasks WHERE description = %s AND created_at > NOW() - INTERVAL '1 hour'",
                        (desc,),
                    )
                    existing = cur.fetchall()
            if existing:
                log.info("Skipping duplicate task: {desc[:50]}")
                continue

            # Create task
            task_id = create_task_in_db(desc, priority, area, text)
            log.info("Created task #{task_id}: {desc[:50]}")

            # Notify Sebastian
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "📋")
            send_whatsapp(f"{emoji} *Task #{task_id} utworzony*\n{desc}\n\nWykonuję...")

            # Execute
            result = execute_task(task_id, desc, area)
            update_task_status(task_id, "completed", result)

            # Report back
            send_whatsapp(f"✅ *Task #{task_id} wykonany*\n\n{result[:800]}")
            log.info("Task #{task_id} completed")

        elif msg_type == "decision":
            decision_text = classification.get("decision_text", text)
            area = classification.get("area", "general")
            context = classification.get("context", "")
            expected = classification.get("expected_outcome", "")
            confidence = classification.get("confidence", 0.5)

            # Save to decisions table
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO decisions (decision_text, context, expected_outcome, area, confidence)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (decision_text, context, expected, area, confidence),
                    )
                    decision_id = cur.fetchall()[0][0]
                conn.commit()

            send_whatsapp(
                f"📋 *Decyzja #{decision_id} zapisana*\n"
                f"Obszar: {area}\n"
                f"{decision_text[:300]}\n\n"
                f"_Przypomnę o sprawdzeniu wyniku za 7 dni._"
            )
            log.info("Decision #{decision_id} saved ({area})")

        elif msg_type == "gtd":
            desc = classification.get("task_description", text)
            area = classification.get("area", "general")

            # GTD = save thought/refinement, don't execute yet
            # Check if there's a recent pending task in same area to append to
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id, description FROM wa_tasks
                           WHERE area = %s AND status = 'pending'
                           AND created_at > NOW() - INTERVAL '24 hours'
                           ORDER BY created_at DESC LIMIT 1""",
                        (area,),
                    )
                    recent = cur.fetchall()

            if recent:
                # Append to existing task
                task_id = recent[0][0]
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE wa_tasks SET description = description || E'\\n\\n[GTD update]: ' || %s WHERE id = %s",
                            (desc, task_id),
                        )
                    conn.commit()
                send_whatsapp(f"📝 Doprecyzowanie dopisane do task #{task_id}")
                log.info("GTD appended to task #{task_id}")
            else:
                # Create new GTD note (pending, not auto-executed)
                task_id = create_task_in_db(desc, "medium", area, text)
                send_whatsapp(f"📝 *GTD #{task_id} zapisane*\n{desc[:300]}\n\n_Nie wykonuję automatycznie — czekam na 'Gilbertusie task:' jeśli chcesz uruchomić._")
                log.info("GTD #{task_id} saved (not executed)")

        elif msg_type == "communication_command":
            text_cmd = classification["text"]
            text_cmd_lower = text_cmd.lower().strip()

            # Authority commands
            if text_cmd_lower.startswith("authority "):
                from app.orchestrator.authority import handle_authority_command
                result = handle_authority_command(text_cmd)
                if result:
                    send_whatsapp(json.dumps(result, ensure_ascii=False, default=str))
                    log.info("Authority command processed")
            # Decision outcome commands
            elif text_cmd_lower.startswith("outcome #") or text_cmd_lower.startswith("skip #"):
                from app.analysis.decision_intelligence import handle_decision_outcome
                result = handle_decision_outcome(text_cmd)
                if result:
                    send_whatsapp(result.get("response", json.dumps(result, ensure_ascii=False, default=str)))
                    log.info("Decision outcome recorded")
            # Delegation commands
            elif any(text_cmd_lower.startswith(p) for p in ["remind #", "cancel #", "extend #"]):
                from app.orchestrator.delegation_chain import handle_delegation_command
                result = handle_delegation_command(text_cmd)
                if result:
                    send_whatsapp(result.get("response", json.dumps(result, ensure_ascii=False, default=str)))
                    log.info("Delegation command processed")
            else:
                from app.orchestrator.communication import handle_communication_command
                result = handle_communication_command(text_cmd)
                if result:
                    send_whatsapp(result["response"])
                    log.info("Communication: {result['type']}")

        elif msg_type == "query_command":
            cmd = classification.get("command", "")
            log.info("query_command", command=cmd)
            try:
                if cmd == "brief":
                    from app.retrieval.morning_brief import generate_morning_brief
                    result = generate_morning_brief(force=True)
                    brief_text = result.get("text", "Nie udało się wygenerować briefu.")
                    # Truncate for WhatsApp (max ~4000 chars)
                    if len(brief_text) > 3500:
                        brief_text = brief_text[:3500] + "\n\n_...skrócone_"
                    send_whatsapp(f"📋 *Poranny Brief*\n\n{brief_text}")

                elif cmd == "market":
                    from app.analysis.market_intelligence import get_market_dashboard
                    dashboard = get_market_dashboard(days=3)
                    lines = ["📈 *Rynek energii (3 dni)*\n"]
                    for ins in dashboard.get("insights", [])[:5]:
                        lines.append(f"• [{ins['type']}] {ins['title']} (rel: {ins['relevance']})")
                        if ins.get("impact"):
                            lines.append(f"  _{ins['impact']}_")
                    if dashboard.get("alerts"):
                        lines.append(f"\n⚡ Aktywne alerty: {len(dashboard['alerts'])}")
                    send_whatsapp("\n".join(lines) if len(lines) > 1 else "📈 Brak nowych insightów rynkowych.")

                elif cmd == "competitors":
                    from app.analysis.competitor_intelligence import get_competitive_landscape
                    landscape = get_competitive_landscape()
                    lines = ["🏢 *Konkurencja*\n"]
                    for comp in landscape.get("competitors", [])[:7]:
                        sig = comp.get("recent_signals_30d", 0)
                        line = f"• {comp['name']}: {sig} sygnałów"
                        if comp.get("high_severity"):
                            line += f" ({comp['high_severity']} ⚠️)"
                        lines.append(line)
                        if comp.get("latest_analysis"):
                            lines.append(f"  _{comp['latest_analysis'][:120]}_")
                    send_whatsapp("\n".join(lines))

                elif cmd == "scenarios":
                    from app.analysis.scenario_analyzer import list_scenarios
                    scenarios = list_scenarios(limit=5)
                    lines = ["🔮 *Scenariusze*\n"]
                    for sc in scenarios:
                        impact = f"{sc['total_impact_pln']:,.0f} PLN" if sc.get("total_impact_pln") else "brak"
                        lines.append(f"• [{sc['type']}] {sc['title']} — {impact} ({sc['status']})")
                    send_whatsapp("\n".join(lines) if len(lines) > 1 else "🔮 Brak scenariuszy.")

                elif cmd == "alerts":
                    from app.analysis.market_intelligence import get_market_alerts
                    market_alerts = get_market_alerts()
                    lines = ["🚨 *Aktywne alerty*\n"]
                    for ma in market_alerts[:5]:
                        lines.append(f"• [{ma['level']}] {ma['message'][:150]}")
                    send_whatsapp("\n".join(lines) if len(lines) > 1 else "🚨 Brak aktywnych alertów.")

                elif cmd == "status":
                    from app.db.postgres import get_pg_connection as _gc
                    with _gc() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT COUNT(*) FROM chunks")
                            chunks = cur.fetchone()[0]
                            cur.execute("SELECT COUNT(*) FROM events")
                            events = cur.fetchone()[0]
                            cur.execute("SELECT COUNT(*) FROM entities")
                            entities = cur.fetchone()[0]
                    send_whatsapp(
                        f"⚙️ *Gilbertus Status*\n\n"
                        f"Chunks: {chunks:,}\n"
                        f"Events: {events:,}\n"
                        f"Entities: {entities:,}\n"
                        f"MCP tools: 39\n"
                        f"Crons: 30+\n"
                        f"DB tables: 73"
                    )
            except Exception as e:
                log.error("query_command_failed", command=cmd, error=str(e))
                send_whatsapp(f"❌ Błąd: {str(e)[:200]}")

        elif msg_type == "approval":
            result = _handle_approval_with_graph(classification["text"])
            if result:
                log.info("action_approval", status=result.get("status", result.get("error", "?")))
            else:
                log.info("approval_parse_failed", text=text[:50])

        elif msg_type == "feedback_rating":
            rating = classification.get("rating", 0)
            # Find last ask_run to link feedback to
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM ask_runs ORDER BY created_at DESC LIMIT 1")
                    rows = cur.fetchall()
                    run_id = rows[0][0] if rows else None
                    if run_id:
                        cur.execute(
                            "INSERT INTO response_feedback (ask_run_id, rating, comment) VALUES (%s, %s, %s)",
                            (run_id, rating, classification.get("text", "")),
                        )
                conn.commit()
            emoji = "\U0001f44d" if rating > 0 else "\U0001f44e"
            log.info("Feedback {emoji} recorded (run_id={run_id})")

        elif msg_type == "feedback":
            log.info("Feedback recorded")

    # Save state
    state["last_processed_line"] = messages[-1]["line"]
    state["last_session"] = session_id
    save_state(state)


if __name__ == "__main__":
    process_new_messages()
