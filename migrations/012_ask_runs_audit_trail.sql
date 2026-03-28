-- H5: Audit trail z tożsamością
-- Dodaje caller_ip i channel_key do ask_runs
ALTER TABLE ask_runs
  ADD COLUMN IF NOT EXISTS caller_ip TEXT,
  ADD COLUMN IF NOT EXISTS channel_key TEXT;

CREATE INDEX IF NOT EXISTS idx_ask_runs_channel ON ask_runs (channel_key);
