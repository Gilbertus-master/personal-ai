#!/usr/bin/env bash
# archive_claude_sessions.sh — Archives ALL Claude Code sessions to Gilbertus DB.
# Imports FULL conversation text (every word), not just summaries.
# Runs before session restart or on demand.
set -euo pipefail
cd "$(dirname "$0")/.."

CLAUDE_DIR="$HOME/.claude/projects/-home-sebastian-personal-ai"

echo "[$(date '+%F %T')] Archiving Claude Code sessions..."

# 1. Backup raw session files to project
ARCHIVE_DIR="data/raw/claude_sessions/$(date +%F_%H%M)"
mkdir -p "$ARCHIVE_DIR"
cp -r "$CLAUDE_DIR/"*.jsonl "$ARCHIVE_DIR/" 2>/dev/null || true

# Copy subagent sessions
for SESSION_DIR in "$CLAUDE_DIR"/*/subagents; do
    if [ -d "$SESSION_DIR" ]; then
        SESSION_ID=$(basename "$(dirname "$SESSION_DIR")")
        mkdir -p "$ARCHIVE_DIR/subagents_${SESSION_ID}"
        cp "$SESSION_DIR/"*.jsonl "$ARCHIVE_DIR/subagents_${SESSION_ID}/" 2>/dev/null || true
    fi
done

echo "  Raw files backed up to: $ARCHIVE_DIR"

# 2. Import full conversations to DB
.venv/bin/python -c "
import json, os, sys
from datetime import datetime
from pathlib import Path
from app.ingestion.common.db import (
    document_exists_by_raw_path, insert_chunk, insert_document, insert_source,
)

CLAUDE_DIR = Path(os.path.expanduser('~/.claude/projects/-home-sebastian-personal-ai'))

source_id = insert_source(conn=None, source_type='claude_code_full', source_name='claude_code_sessions')

imported = 0
chunks_total = 0

# Process each session JSONL
for jsonl in sorted(CLAUDE_DIR.glob('*.jsonl')):
    session_id = jsonl.stem
    raw_path = f'claudecode://full/{session_id}'

    if document_exists_by_raw_path(raw_path):
        continue

    # Extract FULL conversation text
    lines = []
    session_start = None

    with open(jsonl) as f:
        for raw_line in f:
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if entry.get('type') == 'session' and not session_start:
                session_start = entry.get('timestamp')

            if entry.get('type') not in ('user', 'assistant'):
                continue

            msg = entry.get('message', {})
            role = msg.get('role', '')
            content = msg.get('content', '')

            if isinstance(content, list):
                texts = []
                for c in content:
                    if isinstance(c, dict):
                        if c.get('type') == 'text':
                            texts.append(c.get('text', ''))
                        elif c.get('type') == 'tool_use':
                            texts.append(f'[Tool: {c.get(\"name\",\"?\")}]')
                        elif c.get('type') == 'tool_result':
                            result = c.get('content', '')
                            if isinstance(result, list):
                                result = ' '.join(r.get('text','') for r in result if isinstance(r,dict))
                            texts.append(f'[Result: {str(result)[:500]}]')
                text = '\n'.join(texts)
            else:
                text = str(content)

            if not text.strip():
                continue

            speaker = 'Sebastian' if role == 'user' else 'Gilbertus'
            lines.append(f'{speaker}: {text}')

    if not lines:
        continue

    full_text = '\n\n'.join(lines)

    recorded_at = None
    if session_start:
        try:
            recorded_at = datetime.fromisoformat(session_start.replace('Z', '+00:00'))
        except:
            recorded_at = datetime.fromtimestamp(jsonl.stat().st_mtime)
    else:
        recorded_at = datetime.fromtimestamp(jsonl.stat().st_mtime)

    doc_id = insert_document(
        conn=None, source_id=source_id,
        title=f'Claude Code session {session_id[:12]}',
        created_at=recorded_at, author='Sebastian',
        participants=['Sebastian', 'Gilbertus'],
        raw_path=raw_path,
    )

    # Chunk full text
    chunks = []
    start = 0
    while start < len(full_text):
        end = min(start + 3000, len(full_text))
        chunk = full_text[start:end].strip()
        if chunk:
            # Clean null bytes
            chunk = chunk.replace('\x00', '')
            chunks.append(chunk)
        if end >= len(full_text):
            break
        start = max(end - 300, start + 1)

    for ci, chunk in enumerate(chunks):
        insert_chunk(conn=None, document_id=doc_id, chunk_index=ci, text=chunk,
            timestamp_start=recorded_at, timestamp_end=recorded_at, embedding_id=None)

    imported += 1
    chunks_total += len(chunks)
    print(f'  Imported: {session_id[:12]} → {len(chunks)} chunks ({len(full_text)} chars)')

# Process subagent sessions too
for session_dir in sorted(CLAUDE_DIR.glob('*/subagents')):
    for jsonl in sorted(session_dir.glob('*.jsonl')):
        agent_id = jsonl.stem
        raw_path = f'claudecode://subagent/{agent_id}'

        if document_exists_by_raw_path(raw_path):
            continue

        lines = []
        with open(jsonl) as f:
            for raw_line in f:
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if entry.get('type') not in ('user', 'assistant'):
                    continue
                msg = entry.get('message', {})
                role = msg.get('role', '')
                content = msg.get('content', '')
                if isinstance(content, list):
                    text = '\n'.join(c.get('text','') for c in content if isinstance(c,dict) and c.get('type')=='text')
                else:
                    text = str(content)
                if text.strip():
                    speaker = 'Task' if role == 'user' else 'Agent'
                    lines.append(f'{speaker}: {text[:2000]}')

        if len(lines) < 2:
            continue

        full_text = '\n\n'.join(lines)
        if len(full_text) < 100:
            continue

        doc_id = insert_document(
            conn=None, source_id=source_id,
            title=f'Agent {agent_id[:12]}',
            created_at=datetime.fromtimestamp(jsonl.stat().st_mtime),
            author='Agent', participants=['Agent', 'Gilbertus'],
            raw_path=raw_path,
        )

        chunks = []
        start = 0
        while start < len(full_text):
            end = min(start + 3000, len(full_text))
            chunk = full_text[start:end].strip().replace('\x00', '')
            if chunk: chunks.append(chunk)
            if end >= len(full_text): break
            start = max(end - 300, start + 1)

        for ci, chunk in enumerate(chunks):
            insert_chunk(conn=None, document_id=doc_id, chunk_index=ci, text=chunk,
                timestamp_start=None, timestamp_end=None, embedding_id=None)

        imported += 1
        chunks_total += len(chunks)

print(f'\nTotal: {imported} sessions → {chunks_total} chunks')
"

echo "[$(date '+%F %T')] Archive complete"
