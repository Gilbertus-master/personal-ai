BEGIN;

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  evidence TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);

COMMIT;
