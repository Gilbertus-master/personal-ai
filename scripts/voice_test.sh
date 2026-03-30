#!/usr/bin/env bash
# voice_test.sh — Test voice pipeline: record → STT → Gilbertus → response
# Usage:
#   bash scripts/voice_test.sh                    # interactive: record from mic
#   bash scripts/voice_test.sh path/to/audio.wav  # from file
#   bash scripts/voice_test.sh --text "brief"     # skip STT, test command directly
set -euo pipefail
cd "$(dirname "$0")/.."

API_URL="${GILBERTUS_API_URL:-http://127.0.0.1:8000}"

if [ "${1:-}" = "--text" ]; then
    # Direct text command (skip STT)
    TEXT="${2:?Usage: voice_test.sh --text 'command'}"
    echo "=== Text command: $TEXT ==="

    .venv/bin/python -c "
from app.orchestrator.task_monitor import classify_message
from app.api.voice import _execute_query_command
import json

classification = classify_message('$TEXT')
cmd_type = classification.get('type', 'chat')
print(f'Classified as: {cmd_type}')

if cmd_type == 'query_command':
    result = _execute_query_command(classification['command'])
    print(f'\nResponse:\n{result}')
elif cmd_type == 'chat':
    import requests
    r = requests.post('$API_URL/ask', json={'query': '$TEXT', 'answer_length': 'medium'}, timeout=60)
    print(f'\nResponse:\n{r.json().get(\"answer\", \"No answer\")}')
else:
    print(f'Command type: {cmd_type}, text: $TEXT')
"
    exit 0
fi

AUDIO="${1:-}"

if [ -z "$AUDIO" ]; then
    echo "=== Voice Pipeline Test ==="
    echo "No audio file provided."
    echo ""
    echo "Usage:"
    echo "  bash scripts/voice_test.sh audio.wav          # from file"
    echo "  bash scripts/voice_test.sh --text 'brief'     # text command"
    echo "  bash scripts/voice_test.sh --text 'market'    # market dashboard"
    echo "  bash scripts/voice_test.sh --text 'status'    # system status"
    echo ""
    echo "Testing API health..."
    curl -s "$API_URL/voice/health" 2>/dev/null | .venv/bin/python -m json.tool 2>/dev/null || echo "API not reachable"
    exit 0
fi

echo "=== Voice Pipeline: $AUDIO ==="

# Step 1: Transcribe
echo "Step 1: Transcribing..."
RESULT=$(curl -s -X POST "$API_URL/voice/ask" \
    -F "audio=@$AUDIO" \
    -F "language=pl" 2>/dev/null)

TRANSCRIPT=$(echo "$RESULT" | .venv/bin/python -c "import sys,json; d=json.load(sys.stdin); print(d.get('transcript',''))" 2>/dev/null)
ANSWER=$(echo "$RESULT" | .venv/bin/python -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer',''))" 2>/dev/null)

echo "Transcript: $TRANSCRIPT"
echo ""
echo "Answer: $ANSWER"
