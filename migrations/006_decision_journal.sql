BEGIN;

CREATE TABLE IF NOT EXISTS decisions (
  id BIGSERIAL PRIMARY KEY,
  decision_text TEXT NOT NULL,
  context TEXT,
  expected_outcome TEXT,
  area TEXT NOT NULL DEFAULT 'general'
    CHECK (area IN ('business', 'trading', 'relationships', 'wellbeing', 'general')),
  confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.5
    CHECK (confidence >= 0 AND confidence <= 1),
  decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_outcomes (
  id BIGSERIAL PRIMARY KEY,
  decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
  actual_outcome TEXT NOT NULL,
  rating SMALLINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
  outcome_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_area ON decisions(area);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_at ON decisions(decided_at);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_decision_id ON decision_outcomes(decision_id);

COMMIT;
