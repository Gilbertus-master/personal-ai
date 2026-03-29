-- Contacts: cross-source person identity linking
-- Created: 2026-03-29

CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    whatsapp_jid TEXT,
    whatsapp_phone TEXT,
    whatsapp_push_name TEXT,
    email_address TEXT,
    teams_upn TEXT,
    teams_display_name TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_wa_jid ON contacts(whatsapp_jid) WHERE whatsapp_jid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_email ON contacts(email_address) WHERE email_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_canonical_name ON contacts(canonical_name);
CREATE INDEX IF NOT EXISTS idx_contacts_wa_phone ON contacts(whatsapp_phone) WHERE whatsapp_phone IS NOT NULL;

-- Document-contact relationship for cross-source linking
CREATE TABLE IF NOT EXISTS document_contacts (
    document_id BIGINT REFERENCES documents(id),
    contact_id INTEGER REFERENCES contacts(id),
    role TEXT,  -- 'sender', 'recipient', 'participant'
    PRIMARY KEY (document_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_contacts_contact ON document_contacts(contact_id);

-- Contact linking audit log
CREATE TABLE IF NOT EXISTS contact_link_log (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES contacts(id),
    source_type TEXT NOT NULL,
    matched_field TEXT NOT NULL,  -- 'phone', 'name_fuzzy', 'email'
    matched_value TEXT,
    confidence REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
