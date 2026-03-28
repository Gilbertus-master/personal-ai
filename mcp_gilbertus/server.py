#!/usr/bin/env python3
"""
MCP server exposing Gilbertus Albans API as tools for Claude Code.

11 tools: ask, timeline, summary, brief, alerts, status, db_stats,
          decide, people, lessons, costs.

Uses official mcp Python SDK with stdio transport.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

GILBERTUS_API = os.getenv("GILBERTUS_API_URL", "http://127.0.0.1:8000")
API_TIMEOUT = 60

server = Server("gilbertus")


def _api(method: str, path: str, data: dict | None = None) -> str:
    try:
        url = f"{GILBERTUS_API}{path}"
        if method == "GET":
            resp = requests.get(url, params=data, timeout=API_TIMEOUT)
        else:
            resp = requests.post(url, json=data, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, indent=2)
    except requests.ConnectionError:
        return "ERROR: Gilbertus API not running. Start with: bash scripts/run_api.sh"
    except Exception as e:
        return f"ERROR: {e}"


def _sql(query: str) -> str:
    try:
        from app.db.postgres import get_pg_connection
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
        if not rows:
            return "No results."
        lines = [" | ".join(cols)]
        lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))
        return "\n".join(lines)
    except Exception as e:
        return f"DB Error: {e}"


@server.list_tools()
async def list_tools():
    return [
        Tool(name="gilbertus_ask",
             description="Search Sebastian's archive (31k+ docs) and get AI answer. Use for any question about past events, conversations, people, decisions.",
             inputSchema={"type": "object", "properties": {
                 "query": {"type": "string", "description": "Question in Polish or English"},
                 "answer_length": {"type": "string", "enum": ["short", "medium", "long"], "default": "long"},
             }, "required": ["query"]}),
        Tool(name="gilbertus_timeline",
             description="Query events timeline. Types: conflict, support, decision, meeting, trade, health, family, milestone, deadline, commitment, escalation, blocker, task_assignment, approval, rejection.",
             inputSchema={"type": "object", "properties": {
                 "event_type": {"type": "string"}, "date_from": {"type": "string"}, "date_to": {"type": "string"}, "limit": {"type": "integer", "default": 10},
             }}),
        Tool(name="gilbertus_summary",
             description="Generate daily/weekly summary by area (general, relationships, business, trading, wellbeing).",
             inputSchema={"type": "object", "properties": {
                 "date": {"type": "string"}, "summary_type": {"type": "string", "enum": ["daily", "weekly"], "default": "daily"},
                 "areas": {"type": "array", "items": {"type": "string"}, "default": ["general"]},
             }, "required": ["date"]}),
        Tool(name="gilbertus_brief", description="Today's morning brief.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_alerts", description="Proactive alerts: stale decisions, conflict spikes, silent contacts.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_status", description="System dashboard: DB stats, services, cron.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_db_stats", description="Quick DB stats: chunks, entities, events, extraction coverage. Direct DB, no API needed.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_decide", description="Log a decision to the journal.",
             inputSchema={"type": "object", "properties": {
                 "decision_text": {"type": "string"}, "context": {"type": "string"}, "expected_outcome": {"type": "string"},
                 "area": {"type": "string", "enum": ["business", "trading", "relationships", "wellbeing", "general"], "default": "general"},
                 "confidence": {"type": "number", "default": 0.5},
             }, "required": ["decision_text"]}),
        Tool(name="gilbertus_people", description="List people with roles, orgs, chunk/event counts.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_lessons", description="Query lessons learned DB. Check before writing extraction/ingestion code.",
             inputSchema={"type": "object", "properties": {
                 "category": {"type": "string", "description": "bug_pattern, architecture_decision, process_improvement, security, performance"},
                 "module": {"type": "string", "description": "Filter by module path"},
             }}),
        Tool(name="gilbertus_costs", description="API cost report by provider, model, module, day.",
             inputSchema={"type": "object", "properties": {"days": {"type": "integer", "default": 7}}}),
        Tool(name="gilbertus_evaluate",
             description="Generate structured employee evaluation. Returns WHAT/HOW/WEAK POINTS/SCORES for a person.",
             inputSchema={"type": "object", "properties": {
                 "person_slug": {"type": "string", "description": "Person name as 'first-last' (e.g. 'marcin-kulpa')"},
                 "date_from": {"type": "string", "description": "YYYY-MM-DD (optional)"},
                 "date_to": {"type": "string", "description": "YYYY-MM-DD (optional)"},
             }, "required": ["person_slug"]}),
        Tool(name="gilbertus_propose_action",
             description="Propose an action for Sebastian's approval via WhatsApp. Types: send_email, create_ticket, schedule_meeting, send_whatsapp, omnius_command.",
             inputSchema={"type": "object", "properties": {
                 "action_type": {"type": "string", "enum": ["send_email", "create_ticket", "schedule_meeting", "send_whatsapp", "omnius_command"]},
                 "description": {"type": "string", "description": "What this action does (shown to Sebastian)"},
                 "params": {"type": "object", "description": "Action parameters (to, subject, body, title, assignee, etc.)"},
             }, "required": ["action_type", "description", "params"]}),
        Tool(name="gilbertus_pending_actions",
             description="List pending action proposals waiting for Sebastian's approval.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="omnius_ask",
             description="Ask an Omnius tenant (corporate AI). Searches corporate docs, shared Teams, reports.",
             inputSchema={"type": "object", "properties": {
                 "tenant": {"type": "string", "description": "reh or ref", "default": "reh"},
                 "query": {"type": "string", "description": "Question about corporate data"},
                 "answer_length": {"type": "string", "enum": ["short", "medium", "long"], "default": "long"},
             }, "required": ["query"]}),
        Tool(name="omnius_command",
             description="Execute command on Omnius tenant: create_ticket, send_email, schedule_meeting, assign_task, trigger_sync, create_user, create_operator_task, list_operator_tasks, get_audit_log, push_config, push_prompt, create_api_key.",
             inputSchema={"type": "object", "properties": {
                 "tenant": {"type": "string", "default": "ref"},
                 "command": {"type": "string", "enum": ["create_ticket", "send_email", "schedule_meeting", "assign_task", "trigger_sync", "create_user", "create_operator_task", "list_operator_tasks", "get_audit_log", "push_config", "push_prompt", "create_api_key", "deploy"]},
                 "params": {"type": "object", "description": "Command parameters (title, to, subject, body, assignee, email, display_name, role, etc.)"},
             }, "required": ["command", "params"]}),
        Tool(name="omnius_status",
             description="Check status of all Omnius tenants.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="omnius_bridge",
             description="Cross-tenant Omnius operations: search both REH+REF at once, aggregated dashboard, cross-company audit, operator tasks, sync all. Sebastian's god-view across all companies.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["search", "dashboard", "audit", "tasks", "sync", "insights"], "default": "dashboard"},
                 "query": {"type": "string", "description": "Search query (for search action)"},
             }}),
        Tool(name="gilbertus_self_rules",
             description="List active self-rules that Gilbertus extracted from Sebastian's voice recordings. These are instructions/principles/preferences to follow.",
             inputSchema={"type": "object", "properties": {
                 "category": {"type": "string", "enum": ["instruction", "principle", "preference", "correction", "goal"]},
                 "importance": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
             }}),
        Tool(name="gilbertus_opportunities",
             description="List top opportunities found by Continuous Intelligence: optimizations, revenue chances, risks, new business. Ranked by ROI.",
             inputSchema={"type": "object", "properties": {
                 "status": {"type": "string", "default": "new", "enum": ["new", "proposed", "approved", "in_progress"]},
                 "limit": {"type": "integer", "default": 10},
             }}),
        Tool(name="gilbertus_inefficiency",
             description="Detect process inefficiencies: repeating tasks, escalation bottlenecks, meeting overload. Shows automation potential.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_correlate", description="Cross-domain correlation: temporal (event_a vs event_b), person profile, communication anomalies, or full report.",
             inputSchema={"type": "object", "properties": {
                 "correlation_type": {"type": "string", "enum": ["temporal", "person", "anomaly", "report"], "default": "report"},
                 "event_type_a": {"type": "string"}, "event_type_b": {"type": "string"},
                 "person": {"type": "string"},
             }}),
        Tool(name="gilbertus_commitments",
             description="Track commitments/promises. Shows open, overdue, fulfilled commitments per person. Check who delivered and who didn't.",
             inputSchema={"type": "object", "properties": {
                 "person": {"type": "string", "description": "Filter by person name (optional)"},
                 "status": {"type": "string", "enum": ["open", "fulfilled", "broken", "overdue"], "default": "open"},
                 "limit": {"type": "integer", "default": 20},
             }}),
        Tool(name="gilbertus_meeting_prep",
             description="Get prep brief for upcoming meetings: attendee context, open loops, talking points, red flags.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_sentiment",
             description="Sentiment trend for a person over past weeks. Detects falling/rising sentiment, red flags.",
             inputSchema={"type": "object", "properties": {
                 "person": {"type": "string", "description": "Person name"},
                 "weeks": {"type": "integer", "default": 8},
             }, "required": ["person"]}),
        Tool(name="gilbertus_wellbeing",
             description="Sebastian's wellbeing monitor: stress, family, health, work-life balance scores and trends.",
             inputSchema={"type": "object", "properties": {
                 "weeks": {"type": "integer", "default": 8},
             }}),
        Tool(name="gilbertus_delegation",
             description="Delegation effectiveness: who delivers on commitments, completion rates, on-time performance.",
             inputSchema={"type": "object", "properties": {
                 "person": {"type": "string", "description": "Person name (optional, shows ranking if omitted)"},
             }}),
        Tool(name="gilbertus_network",
             description="Communication network analysis: who talks to whom, silos, bottlenecks, missing connections.",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="gilbertus_crons",
             description="Cron registry: list, enable, disable cron jobs per user. Categories: backup, ingestion, extraction, intelligence, communication, qc.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["list", "summary", "enable", "disable", "generate"], "default": "summary"},
                 "user": {"type": "string", "default": "sebastian", "description": "Username (sebastian, roch, krystian)"},
                 "job_name": {"type": "string", "description": "Job name (for enable/disable)"},
                 "category": {"type": "string", "description": "Filter by category"},
             }}),
        Tool(name="gilbertus_authority",
             description="Authority framework: list levels, check approval stats, change authority for action categories. Levels: 0=inform, 1=execute+report, 2=quick approval, 3=full proposal, 4=never alone.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["list", "stats", "set"], "default": "list"},
                 "category": {"type": "string", "description": "Action category (for set)"},
                 "level": {"type": "integer", "description": "New level 0-4 (for set)"},
                 "days": {"type": "integer", "default": 90},
             }}),
        Tool(name="gilbertus_decision_patterns",
             description="Decision intelligence: confidence calibration, success patterns by area, bias detection. Shows how well Sebastian's decision confidence predicts actual outcomes.",
             inputSchema={"type": "object", "properties": {
                 "months": {"type": "integer", "default": 6},
             }}),
        Tool(name="gilbertus_delegation_chain",
             description="Delegation tasks: dashboard, delegate to people, check status. Track who has what assigned, overdue tasks, escalations.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["dashboard", "delegate", "check"], "default": "dashboard"},
                 "assignee": {"type": "string", "description": "Person to delegate to (for delegate action)"},
                 "title": {"type": "string", "description": "Task title (for delegate action)"},
                 "deadline": {"type": "string", "description": "YYYY-MM-DD deadline (for delegate action)"},
             }}),
        Tool(name="gilbertus_response_stats",
             description="Communication response tracking: who responds, how fast, which channels work. Shows response rates per person and channel.",
             inputSchema={"type": "object", "properties": {
                 "days": {"type": "integer", "default": 30},
             }}),
        Tool(name="gilbertus_finance",
             description="Financial dashboard: company metrics (revenue, costs, cash), budget utilization, API costs, alerts. Record metrics and budgets.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["dashboard", "api_costs", "record_metric", "set_budget", "estimate_cost"], "default": "dashboard"},
                 "company": {"type": "string", "description": "Company name (REH/REF)"},
                 "metric_type": {"type": "string"},
                 "value": {"type": "number"},
                 "period_start": {"type": "string"},
                 "period_end": {"type": "string"},
                 "description": {"type": "string", "description": "Action description for cost estimation"},
             }}),
        Tool(name="gilbertus_calendar",
             description="Calendar management: view events, detect conflicts, suggest meetings, block deep work, analytics.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["events", "conflicts", "suggest", "analytics", "block_deep_work"], "default": "events"},
                 "days": {"type": "integer", "default": 7},
             }}),
        Tool(name="gilbertus_goals",
             description="Strategic goal tracking: create goals, update progress, view goal tree, analyze risks. Links strategy to operations.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["summary", "tree", "create", "update", "risks"], "default": "summary"},
                 "goal_id": {"type": "integer"},
                 "title": {"type": "string"},
                 "target_value": {"type": "number"},
                 "value": {"type": "number", "description": "Progress value (for update)"},
                 "unit": {"type": "string", "default": "PLN"},
                 "deadline": {"type": "string"},
                 "company": {"type": "string"},
             }}),
        Tool(name="gilbertus_org_health",
             description="Organizational health score (1-100): commitment rate, sentiment, communication, delegation, decisions, deep work, blind spots, alerts. Weekly trend.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["assess", "trend"], "default": "trend"},
                 "weeks": {"type": "integer", "default": 8},
             }}),
        Tool(name="gilbertus_scenarios",
             description="Scenario analyzer: 'co jeśli?' impact simulation on 5 dimensions (revenue, costs, people, operations, reputation). Create, analyze, compare scenarios.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["list", "create", "analyze", "compare", "auto_scan"], "default": "list"},
                 "title": {"type": "string", "description": "Scenario title (for create)"},
                 "description": {"type": "string", "description": "Scenario description (for create)"},
                 "scenario_type": {"type": "string", "enum": ["risk", "opportunity", "strategic"], "default": "risk"},
                 "scenario_id": {"type": "integer", "description": "Scenario ID (for analyze)"},
                 "ids": {"type": "string", "description": "Comma-separated IDs (for compare)"},
                 "status": {"type": "string", "description": "Filter by status (draft/analyzed/archived)"},
             }}),
        Tool(name="gilbertus_market",
             description="Market intelligence: energy market monitoring (TGE, URE, PSE, BiznesAlert, CIRE). RSS feeds, price changes, regulations, tenders, trends. Dashboard, scan, alerts.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["dashboard", "scan", "insights", "sources", "add_source", "alerts"], "default": "dashboard"},
                 "days": {"type": "integer", "default": 7},
                 "insight_type": {"type": "string", "enum": ["price_change", "regulation", "tender", "trend", "risk"]},
                 "min_relevance": {"type": "integer", "default": 0},
                 "name": {"type": "string", "description": "Source name (for add_source)"},
                 "url": {"type": "string", "description": "Source URL (for add_source)"},
             }}),
        Tool(name="gilbertus_competitors",
             description="Competitor intelligence: track Tauron, PGE, Enea, Energa, Orlen + custom. KRS changes, media, signals, SWOT analysis. Weekly landscape.",
             inputSchema={"type": "object", "properties": {
                 "action": {"type": "string", "enum": ["landscape", "add", "scan", "analyze", "signals"], "default": "landscape"},
                 "name": {"type": "string", "description": "Competitor name (for add)"},
                 "krs_number": {"type": "string", "description": "KRS number (for add)"},
                 "competitor_id": {"type": "integer", "description": "Competitor ID (for analyze/signals)"},
                 "signal_type": {"type": "string", "enum": ["krs_change", "hiring", "media", "tender", "financial"]},
                 "days": {"type": "integer", "default": 30},
             }}),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "gilbertus_ask":
        r = _api("POST", "/ask", {"query": arguments["query"], "answer_length": arguments.get("answer_length", "long")})
    elif name == "gilbertus_timeline":
        r = _api("POST", "/timeline", {k: v for k, v in arguments.items() if v is not None})
    elif name == "gilbertus_summary":
        r = _api("POST", "/summary/generate", arguments)
    elif name == "gilbertus_brief":
        r = _api("GET", "/brief/today")
    elif name == "gilbertus_alerts":
        r = _api("GET", "/alerts")
    elif name == "gilbertus_status":
        r = _api("GET", "/status")
    elif name == "gilbertus_db_stats":
        r = _sql("""
            SELECT 'chunks' as metric, COUNT(*)::text as value FROM chunks
            UNION ALL SELECT 'documents', COUNT(*)::text FROM documents
            UNION ALL SELECT 'entities', COUNT(*)::text FROM entities
            UNION ALL SELECT 'events', COUNT(*)::text FROM events
            UNION ALL SELECT 'insights', COUNT(*)::text FROM insights
            UNION ALL SELECT 'decisions', COUNT(*)::text FROM decisions
            UNION ALL SELECT 'people', COUNT(*)::text FROM people
            UNION ALL SELECT 'event_coverage',
                ROUND(100.0*(1-(SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL)::numeric/GREATEST(COUNT(*),1)),1)::text||'%' FROM chunks
            UNION ALL SELECT 'entity_coverage',
                ROUND(100.0*(1-(SELECT COUNT(*) FROM chunks c LEFT JOIN chunk_entities ce ON ce.chunk_id=c.id LEFT JOIN chunks_entity_checked cec ON cec.chunk_id=c.id WHERE ce.id IS NULL AND cec.chunk_id IS NULL)::numeric/GREATEST(COUNT(*),1)),1)::text||'%' FROM chunks
            ORDER BY 1""")
    elif name == "gilbertus_decide":
        r = _api("POST", "/decision", {
            "decision_text": arguments["decision_text"], "context": arguments.get("context", ""),
            "expected_outcome": arguments.get("expected_outcome", ""), "area": arguments.get("area", "general"),
            "confidence": arguments.get("confidence", 0.5)})
    elif name == "gilbertus_people":
        r = _sql("""SELECT p.first_name||' '||p.last_name as name, r.person_role as role, r.organization as org, r.status,
            (SELECT COUNT(*) FROM chunk_entities ce WHERE ce.entity_id=p.entity_id) as chunks,
            (SELECT COUNT(*) FROM event_entities ee WHERE ee.entity_id=p.entity_id) as events
            FROM people p LEFT JOIN relationships r ON r.person_id=p.id ORDER BY chunks DESC NULLS LAST""")
    elif name == "gilbertus_lessons":
        w = ["1=1"]
        if arguments.get("category"):
            w.append(f"category='{arguments['category']}'")
        if arguments.get("module"):
            w.append(f"module LIKE '%{arguments['module']}%'")
        r = _sql(f"SELECT category, LEFT(description,80) as lesson, prevention_rule FROM lessons_learned WHERE {' AND '.join(w)} ORDER BY id DESC LIMIT 20")
    elif name == "gilbertus_costs":
        d = arguments.get("days", 7)
        r = _sql(f"SELECT DATE(created_at) as day, provider, model, module, COUNT(*) as calls, ROUND(SUM(cost_usd)::numeric,4) as cost_usd FROM api_costs WHERE created_at>NOW()-INTERVAL '{d} days' GROUP BY 1,2,3,4 ORDER BY 1 DESC, 6 DESC")
    elif name == "gilbertus_evaluate":
        from app.evaluation.data_collector import collect_person_data
        from app.evaluation.evaluator import evaluate_person
        _json = __import__("json")
        data = collect_person_data(
            person_slug=arguments["person_slug"],
            date_from=arguments.get("date_from"),
            date_to=arguments.get("date_to"))
        if "error" in data:
            r = data["error"]
        else:
            result = evaluate_person(data)
            r = _json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_self_rules":
        from app.orchestrator.self_improving import get_active_rules
        rules = get_active_rules(
            category=arguments.get("category"),
            importance=arguments.get("importance"))
        r = json.dumps(rules, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_opportunities":
        status = arguments.get("status", "new")
        limit = arguments.get("limit", 10)
        r = _sql(f"""
            SELECT id, opportunity_type, LEFT(description, 100), estimated_value_pln,
                   estimated_effort_hours, roi_score, confidence, status
            FROM opportunities WHERE status = '{status}'
            ORDER BY roi_score DESC NULLS LAST LIMIT {limit}
        """)
    elif name == "gilbertus_inefficiency":
        from app.analysis.inefficiency import generate_inefficiency_report
        r = json.dumps(generate_inefficiency_report(), ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_correlate":
        from app.analysis.correlation import run_correlation
        result = run_correlation(
            arguments.get("correlation_type", "report"),
            arguments.get("event_type_a"), arguments.get("event_type_b"),
            arguments.get("person"))
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_propose_action":
        from app.orchestrator.action_pipeline import propose_action
        action_id = propose_action(
            action_type=arguments["action_type"],
            description=arguments["description"],
            draft_params=arguments.get("params", {}),
        )
        r = json.dumps({"action_id": action_id, "status": "proposed", "message": f"Action #{action_id} sent to Sebastian for approval"})
    elif name == "gilbertus_pending_actions":
        from app.orchestrator.action_pipeline import get_pending_actions
        r = json.dumps(get_pending_actions(), ensure_ascii=False, indent=2, default=str)
    elif name == "omnius_ask":
        from app.omnius.client import get_omnius
        tenant = arguments.get("tenant", "reh")
        try:
            client = get_omnius(tenant)
            result = client.ask(arguments["query"], arguments.get("answer_length", "long"))
            r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            r = f"Omnius {tenant} error: {e}"
    elif name == "omnius_command":
        from app.omnius.client import get_omnius
        tenant = arguments.get("tenant", "reh")
        command = arguments.get("command", "")
        params = arguments.get("params", {})
        try:
            client = get_omnius(tenant)
            if command == "create_ticket":
                result = client.create_ticket(**params)
            elif command == "send_email":
                result = client.send_email(**params)
            elif command == "schedule_meeting":
                result = client.schedule_meeting(**params)
            elif command == "assign_task":
                result = client.assign_task(**params)
            elif command == "trigger_sync":
                result = client.trigger_sync(params.get("source", "all"))
            elif command == "create_user":
                result = client.create_user(**params)
            elif command == "create_operator_task":
                result = client.create_operator_task(**params)
            elif command == "list_operator_tasks":
                result = client.list_operator_tasks(params.get("status", "pending"))
            elif command == "get_audit_log":
                result = client.get_audit_log(params.get("limit", 50))
            elif command == "push_config":
                result = client.update_config(params.get("key", ""), params.get("value", ""))
            elif command == "push_prompt":
                result = client.push_prompt(params.get("prompt_name", ""), params.get("prompt_text", ""))
            elif command == "create_api_key":
                result = client.create_api_key(**params)
            elif command == "deploy":
                result = client.deploy()
            else:
                result = {"error": f"Unknown command: {command}"}
            r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            r = f"Omnius {tenant} command error: {e}"
    elif name == "omnius_status":
        from app.omnius.client import get_omnius, list_tenants
        tenants = list_tenants()
        results = {}
        for t in tenants:
            try:
                results[t] = get_omnius(t).health()
            except Exception as e:
                results[t] = {"error": str(e)}
        r = json.dumps(results, ensure_ascii=False, indent=2, default=str) if tenants else "No Omnius tenants configured. Set OMNIUS_REH_URL and OMNIUS_REH_ADMIN_KEY in .env"
    elif name == "gilbertus_commitments":
        from app.analysis.commitment_tracker import get_open_commitments, get_commitment_summary
        if arguments.get("person"):
            result = get_commitment_summary(person_name=arguments["person"])
        else:
            result = get_open_commitments(limit=arguments.get("limit", 20))
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_meeting_prep":
        from app.analysis.meeting_prep import run_meeting_prep
        r = json.dumps(run_meeting_prep(), ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_sentiment":
        from app.analysis.sentiment_tracker import detect_sentiment_trends
        result = detect_sentiment_trends(arguments["person"], weeks=arguments.get("weeks", 8))
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_wellbeing":
        from app.analysis.wellbeing_monitor import get_wellbeing_trend
        r = json.dumps(get_wellbeing_trend(weeks=arguments.get("weeks", 8)), ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_delegation":
        if arguments.get("person"):
            from app.analysis.delegation_tracker import calculate_delegation_score
            result = calculate_delegation_score(arguments["person"])
        else:
            from app.analysis.delegation_tracker import run_delegation_report
            result = run_delegation_report()
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_network":
        from app.analysis.network_graph import run_network_analysis
        r = json.dumps(run_network_analysis(), ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_crons":
        from app.orchestrator.cron_registry import list_jobs, get_registry_summary, enable_job, disable_job, generate_crontab
        action = arguments.get("action", "summary")
        user = arguments.get("user", "sebastian")
        if action == "summary":
            result = get_registry_summary()
        elif action == "list":
            result = list_jobs(username=user, category=arguments.get("category"))
        elif action == "enable" and arguments.get("job_name"):
            result = enable_job(arguments["job_name"], user)
        elif action == "disable" and arguments.get("job_name"):
            result = disable_job(arguments["job_name"], user)
        elif action == "generate":
            r = generate_crontab(user)
            return [TextContent(type="text", text=r)]
        else:
            result = {"error": "Specify action: list, summary, enable, disable, generate"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_authority":
        from app.orchestrator.authority import list_authority_levels, get_approval_stats, update_authority_level
        action = arguments.get("action", "list")
        if action == "list":
            result = list_authority_levels()
        elif action == "stats":
            result = get_approval_stats(days=arguments.get("days", 90))
        elif action == "set" and arguments.get("category") and arguments.get("level") is not None:
            result = update_authority_level(arguments["category"], arguments["level"])
        else:
            result = {"error": "Specify action: list, stats, or set with category+level"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_decision_patterns":
        from app.analysis.decision_intelligence import analyze_decision_patterns, analyze_confidence_calibration
        patterns = analyze_decision_patterns(months=arguments.get("months", 6))
        calibration = analyze_confidence_calibration(months=arguments.get("months", 6))
        result = {"patterns": patterns, "calibration": calibration}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_delegation_chain":
        action = arguments.get("action", "dashboard")
        if action == "dashboard":
            from app.orchestrator.delegation_chain import get_delegation_dashboard
            result = get_delegation_dashboard()
        elif action == "delegate" and arguments.get("assignee") and arguments.get("title"):
            from app.orchestrator.delegation_chain import delegate_task
            result = delegate_task(
                assignee=arguments["assignee"], title=arguments["title"],
                deadline=arguments.get("deadline"), priority=arguments.get("priority", "medium"))
        elif action == "check":
            from app.orchestrator.delegation_chain import check_delegation_status
            result = check_delegation_status()
        else:
            result = {"error": "Specify action: dashboard, delegate (with assignee+title), or check"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_response_stats":
        from app.analysis.response_tracker import get_response_stats
        r = json.dumps(get_response_stats(days=arguments.get("days", 30)), ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_finance":
        action = arguments.get("action", "dashboard")
        if action == "dashboard":
            from app.analysis.financial_framework import get_financial_dashboard
            result = get_financial_dashboard(company=arguments.get("company"))
        elif action == "api_costs":
            from app.analysis.financial_framework import get_api_cost_summary
            result = get_api_cost_summary()
        elif action == "record_metric" and arguments.get("company") and arguments.get("metric_type"):
            from app.analysis.financial_framework import record_metric
            result = record_metric(arguments["company"], arguments["metric_type"],
                                   arguments.get("value", 0), arguments.get("period_start", ""),
                                   arguments.get("period_end", ""))
        elif action == "set_budget" and arguments.get("company"):
            from app.analysis.financial_framework import record_budget
            result = record_budget(arguments["company"], arguments.get("metric_type", "general"),
                                   arguments.get("value", 0), arguments.get("period_start", ""),
                                   arguments.get("period_end", ""))
        elif action == "estimate_cost" and arguments.get("description"):
            from app.analysis.cost_estimator import estimate_cost
            result = estimate_cost(arguments["description"])
        else:
            result = {"error": "Specify action: dashboard, api_costs, record_metric, set_budget, estimate_cost"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_calendar":
        action = arguments.get("action", "events")
        if action == "events":
            from app.orchestrator.calendar_manager import get_calendar_events
            result = get_calendar_events(days_ahead=arguments.get("days", 7))
        elif action == "conflicts":
            from app.orchestrator.calendar_manager import detect_conflicts
            result = detect_conflicts(days_ahead=arguments.get("days", 3))
        elif action == "suggest":
            from app.orchestrator.calendar_manager import suggest_meetings
            result = suggest_meetings()
        elif action == "analytics":
            from app.orchestrator.calendar_manager import get_calendar_analytics
            result = get_calendar_analytics(days=arguments.get("days", 30))
        elif action == "block_deep_work":
            from app.orchestrator.calendar_manager import block_deep_work
            result = block_deep_work()
        else:
            result = {"error": "Specify action: events, conflicts, suggest, analytics, block_deep_work"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_goals":
        action = arguments.get("action", "summary")
        if action == "summary":
            from app.analysis.strategic_goals import get_goals_summary
            result = get_goals_summary()
        elif action == "tree":
            from app.analysis.strategic_goals import get_goal_tree
            result = get_goal_tree(goal_id=arguments.get("goal_id"))
        elif action == "create" and arguments.get("title"):
            from app.analysis.strategic_goals import create_goal
            result = create_goal(title=arguments["title"], target_value=arguments.get("target_value", 0),
                                 unit=arguments.get("unit", "PLN"), deadline=arguments.get("deadline"),
                                 company=arguments.get("company"))
        elif action == "update" and arguments.get("goal_id") and arguments.get("value") is not None:
            from app.analysis.strategic_goals import update_goal_progress
            result = update_goal_progress(arguments["goal_id"], arguments["value"])
        elif action == "risks":
            from app.analysis.strategic_goals import analyze_goal_risks
            result = analyze_goal_risks()
        else:
            result = {"error": "Specify action: summary, tree, create (title+target), update (goal_id+value), risks"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_org_health":
        action = arguments.get("action", "trend")
        if action == "assess":
            from app.analysis.org_health import run_health_assessment
            result = run_health_assessment()
        else:
            from app.analysis.org_health import get_health_trend
            result = get_health_trend(weeks=arguments.get("weeks", 8))
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "omnius_bridge":
        action = arguments.get("action", "dashboard")
        from app.omnius.bridge import (
            cross_tenant_search, aggregated_dashboard, cross_tenant_audit,
            cross_tenant_operator_tasks, sync_all_tenants, get_cross_company_insights
        )
        if action == "search" and arguments.get("query"):
            result = cross_tenant_search(arguments["query"])
        elif action == "dashboard":
            result = aggregated_dashboard()
        elif action == "audit":
            result = cross_tenant_audit()
        elif action == "tasks":
            result = cross_tenant_operator_tasks()
        elif action == "sync":
            result = sync_all_tenants()
        elif action == "insights":
            result = get_cross_company_insights()
        else:
            result = {"error": "Specify action: search (query), dashboard, audit, tasks, sync, insights"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_scenarios":
        action = arguments.get("action", "list")
        if action == "list":
            from app.analysis.scenario_analyzer import list_scenarios
            result = list_scenarios(status=arguments.get("status"))
        elif action == "create" and arguments.get("title"):
            from app.analysis.scenario_analyzer import create_scenario
            result = create_scenario(
                title=arguments["title"],
                description=arguments.get("description", ""),
                scenario_type=arguments.get("scenario_type", "risk"))
        elif action == "analyze" and arguments.get("scenario_id"):
            from app.analysis.scenario_analyzer import analyze_scenario
            result = analyze_scenario(arguments["scenario_id"])
        elif action == "compare" and arguments.get("ids"):
            from app.analysis.scenario_analyzer import compare_scenarios
            id_list = [int(x.strip()) for x in arguments["ids"].split(",") if x.strip().isdigit()]
            result = compare_scenarios(id_list)
        elif action == "auto_scan":
            from app.analysis.scenario_analyzer import run_auto_scenarios
            result = run_auto_scenarios()
        else:
            result = {"error": "Specify action: list, create (title), analyze (scenario_id), compare (ids), auto_scan"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_market":
        action = arguments.get("action", "dashboard")
        if action == "dashboard":
            from app.analysis.market_intelligence import get_market_dashboard
            result = get_market_dashboard(days=arguments.get("days", 7))
        elif action == "scan":
            from app.analysis.market_intelligence import run_market_scan
            result = run_market_scan()
        elif action == "insights":
            from app.analysis.market_intelligence import get_market_insights
            result = get_market_insights(
                insight_type=arguments.get("insight_type"),
                min_relevance=arguments.get("min_relevance", 0))
        elif action == "sources":
            from app.analysis.market_intelligence import get_market_dashboard
            result = get_market_dashboard(days=1)
            result = {"sources": result.get("sources", [])}
        elif action == "add_source" and arguments.get("name") and arguments.get("url"):
            from app.analysis.market_intelligence import add_market_source
            result = add_market_source(arguments["name"], arguments["url"])
        elif action == "alerts":
            from app.analysis.market_intelligence import get_market_alerts
            result = get_market_alerts()
        else:
            result = {"error": "Specify action: dashboard, scan, insights, sources, add_source (name+url), alerts"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    elif name == "gilbertus_competitors":
        action = arguments.get("action", "landscape")
        if action == "landscape":
            from app.analysis.competitor_intelligence import get_competitive_landscape
            result = get_competitive_landscape()
        elif action == "add" and arguments.get("name"):
            from app.analysis.competitor_intelligence import add_competitor
            result = add_competitor(
                name=arguments["name"],
                krs_number=arguments.get("krs_number"),
                watch_level=arguments.get("watch_level", "active"))
        elif action == "scan":
            from app.analysis.competitor_intelligence import run_competitor_scan
            result = run_competitor_scan()
        elif action == "analyze" and arguments.get("competitor_id"):
            from app.analysis.competitor_intelligence import analyze_competitor
            result = analyze_competitor(arguments["competitor_id"])
        elif action == "signals":
            from app.analysis.competitor_intelligence import get_competitor_signals
            result = get_competitor_signals(
                competitor_id=arguments.get("competitor_id"),
                signal_type=arguments.get("signal_type"),
                days=arguments.get("days", 30))
        else:
            result = {"error": "Specify action: landscape, add (name), scan, analyze (competitor_id), signals"}
        r = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    else:
        r = f"Unknown tool: {name}"
    return [TextContent(type="text", text=r)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
