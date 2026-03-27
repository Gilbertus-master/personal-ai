-- Omnius RBAC: roles, users, permissions, API keys, audit log

CREATE TABLE IF NOT EXISTS omnius_roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    level INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS omnius_users (
    id BIGSERIAL PRIMARY KEY,
    azure_ad_oid TEXT UNIQUE,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role_id INTEGER NOT NULL REFERENCES omnius_roles(id),
    department TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS omnius_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES omnius_roles(id),
    permission TEXT NOT NULL,
    UNIQUE(role_id, permission)
);

CREATE TABLE IF NOT EXISTS omnius_api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role_id INTEGER NOT NULL REFERENCES omnius_roles(id),
    user_id BIGINT REFERENCES omnius_users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS omnius_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES omnius_users(id),
    api_key_id BIGINT REFERENCES omnius_api_keys(id),
    action TEXT NOT NULL,
    resource TEXT,
    request_summary JSONB,
    result_status TEXT NOT NULL DEFAULT 'ok',
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON omnius_audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON omnius_audit_log(action, created_at);

CREATE TABLE IF NOT EXISTS omnius_operator_tasks (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    source TEXT DEFAULT 'gilbertus',
    assigned_to BIGINT REFERENCES omnius_users(id),
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'done', 'blocked')),
    result TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_operator_tasks_status ON omnius_operator_tasks(status);
