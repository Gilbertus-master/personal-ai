#!/usr/bin/env python3
"""
MCP server that exposes Gilbertus Albans API as tools for OpenClaw.
Claude can call search_archive(), query_timeline(), generate_summary() directly.
"""
import json
import sys
import requests

GILBERTUS_API = "http://127.0.0.1:8000"


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "gilbertus-api", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "search_archive",
                        "description": "Search Sebastian's personal archive (30k+ documents: emails, WhatsApp, ChatGPT, Teams, audio transcriptions, documents). ALWAYS use this when Sebastian asks about his past, data, conversations, people, events, meetings.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Question in Polish or English"},
                                "answer_length": {"type": "string", "enum": ["short", "medium", "long"], "default": "long"},
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "query_timeline",
                        "description": "Query timeline of events from Sebastian's life. Types: conflict, support, decision, meeting, trade, health, family.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "event_type": {"type": "string", "description": "Event type filter"},
                                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                                "limit": {"type": "integer", "default": 10},
                            },
                        },
                    },
                    {
                        "name": "generate_summary",
                        "description": "Generate a daily or weekly summary of Sebastian's data by area (general, relationships, business, trading, wellbeing).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "description": "YYYY-MM-DD"},
                                "summary_type": {"type": "string", "enum": ["daily", "weekly"], "default": "daily"},
                                "areas": {"type": "array", "items": {"type": "string"}, "default": ["general"]},
                            },
                            "required": ["date"],
                        },
                    },
                ],
            },
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "search_archive":
                resp = requests.post(
                    f"{GILBERTUS_API}/ask",
                    json={"query": args["query"], "answer_length": args.get("answer_length", "long")},
                    timeout=60,
                )
                data = resp.json()
                text = data.get("answer", "No answer")
                meta = data.get("meta", {})
                result_text = f"{text}\n\n[Matches: {meta.get('retrieved_count', '?')}, Type: {meta.get('question_type', '?')}]"

            elif tool_name == "query_timeline":
                resp = requests.post(
                    f"{GILBERTUS_API}/timeline",
                    json={k: v for k, v in args.items() if v is not None},
                    timeout=30,
                )
                data = resp.json()
                events = data.get("events", [])
                lines = [f"Found {len(events)} events:"]
                for e in events:
                    lines.append(f"[{e['event_type']}] {e.get('event_time', '?')}: {e['summary']}")
                result_text = "\n".join(lines)

            elif tool_name == "generate_summary":
                resp = requests.post(
                    f"{GILBERTUS_API}/summary/generate",
                    json=args,
                    timeout=120,
                )
                data = resp.json()
                results = data.get("results", [])
                lines = []
                for r in results:
                    if r.get("text"):
                        lines.append(f"## {r.get('area', '?')}\n{r['text']}")
                result_text = "\n\n".join(lines) if lines else "No summary generated"

            else:
                result_text = f"Unknown tool: {tool_name}"

        except Exception as e:
            result_text = f"Error calling Gilbertus API: {e}"

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            },
        }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """MCP stdio transport."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
