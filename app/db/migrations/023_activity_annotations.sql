-- Universal Interaction Layer: activity log + item annotations
-- 2026-03-31

CREATE TABLE IF NOT EXISTS user_activity_log (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL DEFAULT 'sebastian',
  action_type TEXT NOT NULL,
  item_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  item_title TEXT,
  item_context TEXT,
  payload JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_user_created
  ON user_activity_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_item
  ON user_activity_log (item_type, item_id);

CREATE TABLE IF NOT EXISTS item_annotations (
  id BIGSERIAL PRIMARY KEY,
  item_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  user_id TEXT DEFAULT 'sebastian',
  annotation_type TEXT NOT NULL,
  content TEXT,
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  is_false_positive BOOLEAN DEFAULT FALSE,
  research_result TEXT,
  forward_to TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_annotations_item
  ON item_annotations (item_type, item_id);
