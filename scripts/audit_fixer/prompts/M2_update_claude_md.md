# M2: Update CLAUDE.md — endpoints count and tools categorization

## Problem
CLAUDE.md says "116 endpoints" but the API actually has 179.
Also Omnius is listed as 3 tools but there are 4 (omnius_bridge missing).
Several wave-4 tools not documented.

## Task
1. Get actual endpoint count: `curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(sum(len(v) for v in d.get('paths',{}).values()))"`
2. Get actual MCP tool names: `grep -oP "name=\"\K[^\"]+|name='\K[^']+" /home/sebastian/personal-ai/mcp_gilbertus/server.py | sort`
3. Read current CLAUDE.md: `/home/sebastian/personal-ai/CLAUDE.md`
4. Update:
   a. Change "116 endpointow" to the actual count
   b. Add `omnius_bridge` to Omnius tools (4 not 3)
   c. Add missing wave-4 tools to appropriate categories:
      - gilbertus_router, gilbertus_calendar, gilbertus_authority
      - gilbertus_finance, gilbertus_goals, gilbertus_org_health
      - gilbertus_decision_patterns, gilbertus_delegation_chain
      - gilbertus_response_stats, gilbertus_competitors
      - gilbertus_market, gilbertus_scenarios
5. Update the total MCP tools count if it changed

## Constraints
- Only update the numbers and tool lists — don't rewrite other sections
- Keep the existing formatting style
- Project at /home/sebastian/personal-ai
