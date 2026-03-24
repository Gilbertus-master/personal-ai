"""
WhatsApp Live message scraper — entry point.

Imports ALL WhatsApp messages (from all chats, not just self-chat) into
the Gilbertus database.

Architecture:
  1. Node.js Baileys listener (app/ingestion/whatsapp_live/listener.js)
     connects to WhatsApp Web as a separate linked device and writes
     ALL incoming messages to ~/.gilbertus/whatsapp_listener/messages.jsonl

  2. This Python script reads that JSONL file and imports new messages
     into the DB with source_type='whatsapp_live'.

Run via cron every 5 minutes:
    python -m app.ingestion.whatsapp_live.importer

Or directly:
    python app/ingestion/whatsapp_live.py

Setup (one-time):
    bash app/ingestion/whatsapp_live/setup.sh
"""

from app.ingestion.whatsapp_live.importer import main

if __name__ == "__main__":
    main()
