-- Migration 025: add deadline + context fields to opportunities
ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS action_required_by TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS urgency TEXT DEFAULT 'normal' CHECK (urgency IN ('immediate', 'this_week', 'this_month', 'normal'));

CREATE INDEX IF NOT EXISTS idx_opportunities_deadline ON opportunities(deadline) WHERE deadline IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_opportunities_action_required ON opportunities(action_required_by) WHERE action_required_by IS NOT NULL;
