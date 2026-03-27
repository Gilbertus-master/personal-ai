-- B1.1: Standing Orders + Sent Communications
-- Autoryzacja zakresu komunikacji w imieniu Sebastiana

CREATE TABLE IF NOT EXISTS standing_orders (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL DEFAULT 'email'
        CHECK (channel IN ('email', 'teams', 'whatsapp')),
    recipient_pattern TEXT NOT NULL DEFAULT '*',
    topic_scope TEXT NOT NULL DEFAULT 'ogólna komunikacja',
    forbidden_topics TEXT,
    max_per_day INTEGER NOT NULL DEFAULT 3,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- B1.7: Audit trail dla komunikacji wysyłanej w imieniu Sebastiana
CREATE TABLE IF NOT EXISTS sent_communications (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    standing_order_id BIGINT REFERENCES standing_orders(id),
    action_item_id BIGINT,
    authorization_type TEXT NOT NULL DEFAULT 'action_approval'
        CHECK (authorization_type IN ('standing_order', 'action_approval')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index: dzienne limity per standing order
CREATE INDEX IF NOT EXISTS idx_sent_comm_order_date
    ON sent_communications (standing_order_id, sent_at);

-- Index: daily digest query
CREATE INDEX IF NOT EXISTS idx_sent_comm_sent_at
    ON sent_communications (sent_at);

-- Index: aktywne standing orders
CREATE INDEX IF NOT EXISTS idx_standing_orders_active
    ON standing_orders (active) WHERE active = TRUE;
