-- Plugin system tables

CREATE TABLE IF NOT EXISTS omnius_plugins (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    author TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'disabled', 'rejected')),
    current_version TEXT,
    permissions_required TEXT[],
    config_schema JSONB,
    created_by BIGINT REFERENCES omnius_users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS omnius_plugin_versions (
    id BIGSERIAL PRIMARY KEY,
    plugin_id BIGINT NOT NULL REFERENCES omnius_plugins(id),
    version TEXT NOT NULL,
    manifest JSONB NOT NULL,
    code_archive BYTEA,
    code_hash TEXT NOT NULL,
    review_status TEXT DEFAULT 'pending' CHECK (review_status IN ('pending', 'reviewing', 'approved', 'rejected')),
    review_result JSONB,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plugin_id, version)
);

CREATE INDEX IF NOT EXISTS idx_plugins_status ON omnius_plugins(status);
CREATE INDEX IF NOT EXISTS idx_plugin_versions_review ON omnius_plugin_versions(review_status);

-- Add plugin permissions to existing roles
INSERT INTO omnius_permissions (role_id, permission) VALUES
    ((SELECT id FROM omnius_roles WHERE name = 'gilbertus_admin'), 'plugins:manage'),
    ((SELECT id FROM omnius_roles WHERE name = 'gilbertus_admin'), 'plugins:use'),
    ((SELECT id FROM omnius_roles WHERE name = 'ceo'), 'plugins:use'),
    ((SELECT id FROM omnius_roles WHERE name = 'ceo'), 'plugins:propose'),
    ((SELECT id FROM omnius_roles WHERE name = 'board'), 'plugins:use'),
    ((SELECT id FROM omnius_roles WHERE name = 'board'), 'plugins:propose'),
    ((SELECT id FROM omnius_roles WHERE name = 'operator'), 'plugins:propose')
ON CONFLICT DO NOTHING;
