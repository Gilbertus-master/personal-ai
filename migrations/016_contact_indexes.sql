-- Migration 016: Contact indexes + document wa_message_ids for dedup
-- Date: 2026-03-29

-- Unique indexes for contact matching
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_whatsapp_jid ON contacts(whatsapp_jid) WHERE whatsapp_jid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_whatsapp_phone ON contacts(whatsapp_phone) WHERE whatsapp_phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_canonical_name ON contacts(canonical_name);

-- Track WA message IDs per document for dedup
ALTER TABLE documents ADD COLUMN IF NOT EXISTS wa_message_ids jsonb;
