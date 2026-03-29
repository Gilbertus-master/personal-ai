#!/bin/bash
set -euo pipefail
LOG=/home/sebastian/personal-ai/logs/pip_audit.log
REPO=/home/sebastian/personal-ai

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pip-audit scan..." >> "$LOG"
cd "$REPO"
source .venv/bin/activate

RESULT=$(pip-audit -r requirements.txt --format=json 2>/dev/null || echo '{"vulnerabilities":[]}')
VULN_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('vulnerabilities',[])))")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Vulnerabilities found: $VULN_COUNT" >> "$LOG"

if [ "$VULN_COUNT" -gt "0" ]; then
    DETAILS=$(echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for v in d['vulnerabilities'][:5]:
    print(f\" - {v.get('name','?')} {v.get('version','?')}: {v.get('description','?')[:80]}\")
")
    MSG="⚠️ *Gilbertus Security Scan*\n$VULN_COUNT podatnych bibliotek:\n$DETAILS\n\nUruchom: pip-audit -r requirements.txt"
    ~/.npm-global/bin/openclaw message send --channel whatsapp \
        --target "${WA_TARGET:-}" --message "$MSG" 2>/dev/null || true
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] pip-audit scan complete" >> "$LOG"
