-- Migration 011: Plugin per-tenant configuration
-- Tracks which plugins are enabled for which tenants

CREATE TABLE IF NOT EXISTS omnius_plugin_config (
    id BIGSERIAL PRIMARY KEY,
    plugin_id BIGINT NOT NULL REFERENCES omnius_plugins(id),
    tenant TEXT NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    config JSONB DEFAULT '{}',
    installed_version TEXT,
    installed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plugin_id, tenant)
);

CREATE INDEX IF NOT EXISTS idx_plugin_config_tenant ON omnius_plugin_config(tenant, enabled);
