#!/usr/bin/env python3
"""
Backfill Contacts — Bootstrap and link contacts across sources.

Steps:
1. Bootstrap contacts from WA historical exports (data/raw/whatsapp/)
2. Bootstrap contacts from WA live messages (JSONL)
3. Cross-source link all contacts (email, Teams, WA)
4. Enrich documents with contact links

Non-destructive: does not overwrite manually set data.
Idempotent: safe to run multiple times.

Usage:
    cd /home/sebastian/personal-ai
    source .venv/bin/activate
    python scripts/backfill_contacts.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.contact_resolver import (
    bootstrap_contacts_from_wa_export,
    enrich_all_documents,
    link_all_contacts,
    resolve_wa_jid,
)
from app.db.postgres import get_pg_connection


def bootstrap_from_wa_live() -> dict:
    """Bootstrap contacts from WA live JSONL file."""
    stats = {"messages_scanned": 0, "contacts_resolved": 0}

    jsonl_path = Path.home() / ".gilbertus" / "whatsapp_listener" / "messages.jsonl"
    if not jsonl_path.exists():
        print("  No messages.jsonl found")
        return stats

    # Collect unique (chatJid, pushName) pairs
    jid_names: dict[str, str] = {}

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            stats["messages_scanned"] += 1

            chat_jid = msg.get("chatJid", "")
            push_name = msg.get("senderName")
            chat_name = msg.get("chatName")
            from_me = msg.get("fromMe", False)

            if from_me:
                continue

            # For non-group chats, use the chatJid as the person's JID
            if not msg.get("isGroup") and chat_jid:
                best_name = push_name or chat_name
                if best_name and chat_jid not in jid_names:
                    jid_names[chat_jid] = best_name

    print(f"  Found {len(jid_names)} unique non-group chat JIDs")

    for jid, name in jid_names.items():
        contact_id = resolve_wa_jid(jid, push_name=name, chat_name=name)
        if contact_id:
            stats["contacts_resolved"] += 1

    return stats


def print_summary() -> None:
    """Print summary of contacts table."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM contacts")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM contacts WHERE whatsapp_jid IS NOT NULL")
            with_jid = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM contacts WHERE email_address IS NOT NULL")
            with_email = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM contacts WHERE teams_display_name IS NOT NULL")
            with_teams = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM document_contacts")
            doc_links = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM contact_link_log")
            link_logs = cur.fetchone()[0]

    print(f"\n{'='*50}")
    print("  CONTACTS SUMMARY")
    print(f"{'='*50}")
    print(f"  Total contacts:        {total}")
    print(f"  With WhatsApp JID:     {with_jid}")
    print(f"  With email:            {with_email}")
    print(f"  With Teams:            {with_teams}")
    print(f"  Document-contact links: {doc_links}")
    print(f"  Cross-source link logs: {link_logs}")
    print(f"{'='*50}\n")


def main() -> None:
    start = datetime.now(tz=timezone.utc)
    print(f"[{start.strftime('%H:%M:%S')}] Starting contact backfill...\n")

    # Step 1: Bootstrap from WA historical exports
    print("Step 1: Bootstrapping contacts from WA historical exports...")
    wa_hist_stats = bootstrap_contacts_from_wa_export()
    print(f"  Files scanned: {wa_hist_stats['files_scanned']}")
    print(f"  Contacts created: {wa_hist_stats['contacts_created']}")
    print(f"  Already existing: {wa_hist_stats['contacts_existing']}")

    # Step 2: Bootstrap from WA live messages
    print("\nStep 2: Bootstrapping contacts from WA live messages...")
    wa_live_stats = bootstrap_from_wa_live()
    print(f"  Messages scanned: {wa_live_stats['messages_scanned']}")
    print(f"  Contacts resolved: {wa_live_stats['contacts_resolved']}")

    # Step 3: Cross-source linking
    print("\nStep 3: Cross-source linking (email, Teams)...")
    link_stats = link_all_contacts()
    print(f"  Total contacts: {link_stats['total']}")
    print(f"  Newly linked: {link_stats['linked']}")

    # Step 4: Enrich documents with contact links
    print("\nStep 4: Enriching documents with contact links...")
    for st in ["whatsapp_live", "whatsapp"]:
        print(f"  Source type: {st}")
        enrich_stats = enrich_all_documents(source_type=st)
        print(f"    Documents: {enrich_stats['total']}")
        print(f"    Enriched: {enrich_stats['enriched']}")
        print(f"    Links created: {enrich_stats['links_created']}")

    # Summary
    print_summary()

    elapsed = (datetime.now(tz=timezone.utc) - start).total_seconds()
    print(f"Backfill completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
