"""
Live ingestion daemon — continuously imports new data from:
1. WhatsApp (via OpenClaw session logs)
2. ChatGPT exports (filesystem watcher)
3. Claude Code sessions (filesystem watcher)
4. Plaud Pin S (via Plaud API sync)

Runs as cron every 5 minutes.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)

OPENCLAW_SESSIONS = Path("/home/sebastian/.openclaw/agents/main/sessions")
CHATGPT_EXPORT_DIR = Path("/mnt/c/Users/jablo/Documents/Klon AI/chat GPT")
CLAUDE_CODE_SESSIONS = Path("/home/sebastian/.claude/projects")

CHUNK_TARGET = 3000
CHUNK_OVERLAP = 300

# Track what we've already imported
STATE_FILE = Path("/home/sebastian/personal-ai/.live_ingest_state.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_TARGET, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


# ── WhatsApp via OpenClaw ──

def ingest_whatsapp_sessions() -> tuple[int, int]:
    """Parse OpenClaw session JSONL files and import WhatsApp conversations."""
    if not OPENCLAW_SESSIONS.exists():
        return 0, 0

    state = load_state()
    processed_sessions = set(state.get("whatsapp_sessions", []))

    source_id = None
    imported = 0
    chunks_total = 0

    for jsonl_file in OPENCLAW_SESSIONS.glob("*.jsonl"):
        session_id = jsonl_file.stem

        # Check file modification time vs last processed
        mtime = jsonl_file.stat().st_mtime
        last_mtime = state.get(f"wa_mtime_{session_id}", 0)
        if mtime <= last_mtime:
            continue

        messages = []
        session_ts = None

        with open(jsonl_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "session":
                    session_ts = entry.get("timestamp")

                if entry.get("type") != "message":
                    continue

                msg = entry.get("message", {})
                role = msg.get("role", "")
                content = msg.get("content", "")

                if isinstance(content, list):
                    texts = [c.get("text", "") for c in content
                             if isinstance(c, dict) and c.get("type") == "text"]
                    text = "\n".join(texts)
                else:
                    text = str(content)

                if not text.strip():
                    continue

                # Extract WhatsApp sender from user messages
                sender = "Gilbertus" if role == "assistant" else "Sebastian"
                messages.append({"role": role, "sender": sender, "text": text.strip()})

        if not messages:
            continue

        raw_path = f"openclaw://whatsapp/{session_id}"
        if document_exists_by_raw_path(raw_path):
            state[f"wa_mtime_{session_id}"] = mtime
            continue

        if source_id is None:
            source_id = insert_source(conn=None, source_type="whatsapp_live", source_name="openclaw_gilbertus")

        # Build conversation text
        lines = [f"WhatsApp konwersacja z Gilbertusem"]
        if session_ts:
            lines.append(f"Data: {session_ts}")
        lines.append("")

        for msg in messages:
            # Skip tool calls and system messages
            if msg["role"] not in ("user", "assistant"):
                continue
            # Clean WhatsApp metadata from user messages
            text = msg["text"]
            if text.startswith("Conversation info"):
                # Extract actual message from metadata
                try:
                    meta_end = text.index("\n\n")
                    text = text[meta_end:].strip()
                except ValueError:
                    pass
            lines.append(f"{msg['sender']}: {text[:500]}")

        full_text = "\n".join(lines)
        if len(full_text) < 50:
            continue

        recorded_at = None
        if session_ts:
            try:
                recorded_at = datetime.fromisoformat(session_ts.replace("Z", "+00:00"))
            except:
                pass

        document_id = insert_document(
            conn=None, source_id=source_id, title=f"WhatsApp Gilbertus {session_ts or session_id[:12]}",
            created_at=recorded_at, author="Sebastian", participants=["Sebastian", "Gilbertus"],
            raw_path=raw_path,
        )

        chunks = chunk_text(full_text)
        for ci, chunk in enumerate(chunks):
            insert_chunk(conn=None, document_id=document_id, chunk_index=ci,
                         text=chunk, timestamp_start=recorded_at, timestamp_end=recorded_at,
                         embedding_id=None)

        imported += 1
        chunks_total += len(chunks)
        state[f"wa_mtime_{session_id}"] = mtime

    save_state(state)
    return imported, chunks_total


# ── ChatGPT exports ──

def ingest_chatgpt_exports() -> tuple[int, int]:
    """Check for new ChatGPT export files and import them."""
    if not CHATGPT_EXPORT_DIR.exists():
        return 0, 0

    state = load_state()
    processed = set(state.get("chatgpt_files", []))

    source_id = None
    imported = 0
    chunks_total = 0

    for f in CHATGPT_EXPORT_DIR.glob("*.json"):
        if f.name in processed:
            continue

        raw_path = f"chatgpt://export/{f.name}"
        if document_exists_by_raw_path(raw_path):
            processed.add(f.name)
            continue

        try:
            from app.ingestion.chatgpt.parser import parse_chatgpt_export_file
            from app.ingestion.chatgpt.importer import chunk_text as chatgpt_chunk

            convs = parse_chatgpt_export_file(f)

            if source_id is None:
                source_id = insert_source(conn=None, source_type="chatgpt", source_name="chatgpt_live")

            for conv in convs:
                conv_raw = f"chatgpt://live/{conv.conversation_id}"
                if document_exists_by_raw_path(conv_raw):
                    continue

                text = "\n".join(f"{m.author}: {m.text}" for m in conv.messages)
                if len(text) < 50:
                    continue

                doc_id = insert_document(
                    conn=None, source_id=source_id, title=conv.title,
                    created_at=conv.created_at, author="Sebastian",
                    participants=list({m.author for m in conv.messages}),
                    raw_path=conv_raw,
                )

                chunks = chunk_text(text)
                for ci, chunk in enumerate(chunks):
                    insert_chunk(conn=None, document_id=doc_id, chunk_index=ci,
                                 text=chunk, timestamp_start=conv.created_at,
                                 timestamp_end=conv.created_at, embedding_id=None)
                imported += 1
                chunks_total += len(chunks)

        except Exception as e:
            print(f"  Error processing {f.name}: {e}")

        processed.add(f.name)

    state["chatgpt_files"] = list(processed)
    save_state(state)
    return imported, chunks_total


# ── Claude Code sessions ──

def ingest_claude_code_sessions() -> tuple[int, int]:
    """Import Claude Code session logs into Gilbertus."""
    state = load_state()
    processed = set(state.get("claude_sessions", []))

    source_id = None
    imported = 0
    chunks_total = 0

    # Claude Code stores sessions as JSONL
    for sessions_dir in CLAUDE_CODE_SESSIONS.rglob("*.jsonl"):
        fname = str(sessions_dir)
        if fname in processed:
            continue

        raw_path = f"claudecode://{sessions_dir.name}"
        if document_exists_by_raw_path(raw_path):
            processed.add(fname)
            continue

        try:
            messages = []
            with open(sessions_dir) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") == "message":
                        msg = entry.get("message", {})
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            texts = [c.get("text", "") for c in content
                                     if isinstance(c, dict) and c.get("type") == "text"]
                            text = "\n".join(texts)
                        else:
                            text = str(content)
                        if text.strip() and role in ("user", "assistant"):
                            messages.append(f"{'Sebastian' if role == 'user' else 'Claude'}: {text[:1000]}")

            if len(messages) < 2:
                processed.add(fname)
                continue

            if source_id is None:
                source_id = insert_source(conn=None, source_type="claude_code", source_name="claude_code_sessions")

            full_text = f"Claude Code sesja\n\n" + "\n\n".join(messages)

            doc_id = insert_document(
                conn=None, source_id=source_id, title=f"Claude Code {sessions_dir.name[:20]}",
                created_at=datetime.fromtimestamp(sessions_dir.stat().st_mtime),
                author="Sebastian", participants=["Sebastian", "Claude"],
                raw_path=raw_path,
            )

            chunks = chunk_text(full_text)
            for ci, chunk in enumerate(chunks):
                insert_chunk(conn=None, document_id=doc_id, chunk_index=ci,
                             text=chunk, timestamp_start=None, timestamp_end=None,
                             embedding_id=None)

            imported += 1
            chunks_total += len(chunks)

        except Exception as e:
            print(f"  Error: {sessions_dir}: {e}")

        processed.add(fname)

    state["claude_sessions"] = list(processed)
    save_state(state)
    return imported, chunks_total


# ── Main ──

def run_all():
    print(f"[{datetime.now().strftime('%H:%M')}] Live ingest starting...")

    wa_docs, wa_chunks = ingest_whatsapp_sessions()
    if wa_docs:
        print(f"  WhatsApp: {wa_docs} conversations, {wa_chunks} chunks")

    gpt_docs, gpt_chunks = ingest_chatgpt_exports()
    if gpt_docs:
        print(f"  ChatGPT: {gpt_docs} conversations, {gpt_chunks} chunks")

    cc_docs, cc_chunks = ingest_claude_code_sessions()
    if cc_docs:
        print(f"  Claude Code: {cc_docs} sessions, {cc_chunks} chunks")

    total = wa_docs + gpt_docs + cc_docs
    if total == 0:
        print(f"  No new data")
    else:
        print(f"  Total: {total} documents imported")


def main():
    run_all()


if __name__ == "__main__":
    main()
