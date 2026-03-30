-- Migration: Create wa_tasks table for WhatsApp task tracking
-- Created: 2026-03-30
-- Description: One-time DDL moved from create_task_in_db() to avoid per-call table lock

CREATE TABLE IF NOT EXISTS wa_tasks (
    id BIGSERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'medium',
    area TEXT DEFAULT 'general',
    source_text TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
