# C3: QC baseline — fix MCP tools count regression 21→8

## Problem
The daily quality check (06:00) reported: `[ERROR] REGRESSION: MCP tools dropped from 21 to 8`.
This is a false positive — the actual MCP server has 44 tools. The QC baseline file has a stale/wrong count.

## Task
1. Find the QC baseline file: `find /home/sebastian/personal-ai -name "*qc*baseline*" -o -name "*quality*baseline*" 2>/dev/null`
2. Also check: `grep -rn "MCP tools" /home/sebastian/personal-ai/scripts/ --include="*.py" --include="*.sh" --include="*.json" | head -20`
3. Find the QC check script that produces this error: `grep -rn "REGRESSION.*MCP\|MCP.*dropped" /home/sebastian/personal-ai/scripts/ | head -10`
4. Understand how it counts MCP tools — likely `curl` to an endpoint or `grep` in server.py
5. Update the baseline to match reality (44 tools) or fix the counting method
6. Run the QC check to verify it passes: execute the relevant script

## Constraints
- Don't change MCP server code — only fix the QC check/baseline
- Project at /home/sebastian/personal-ai
