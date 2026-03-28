-- 010_ask_runs_observability.sql — enriched ask_runs for tracing
-- 2026-03-28

ALTER TABLE ask_runs
  ADD COLUMN IF NOT EXISTS model_used       TEXT,
  ADD COLUMN IF NOT EXISTS input_tokens     INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS output_tokens    INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_usd         NUMERIC(10,6),
  ADD COLUMN IF NOT EXISTS error_flag       BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS error_message    TEXT,
  ADD COLUMN IF NOT EXISTS stage_ms         JSONB,
  ADD COLUMN IF NOT EXISTS cache_hit        BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_ask_runs_error    ON ask_runs (error_flag) WHERE error_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_ask_runs_slow     ON ask_runs (latency_ms) WHERE latency_ms > 30000;
CREATE INDEX IF NOT EXISTS idx_ask_runs_model    ON ask_runs (model_used);
