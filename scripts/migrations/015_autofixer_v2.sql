-- 015_autofixer_v2.sql — Add cluster_id and tier to code_review_findings
-- 2026-03-29

ALTER TABLE code_review_findings ADD COLUMN IF NOT EXISTS cluster_id TEXT;
ALTER TABLE code_review_findings ADD COLUMN IF NOT EXISTS tier INTEGER;

CREATE INDEX IF NOT EXISTS idx_crf_cluster_id ON code_review_findings(cluster_id) WHERE cluster_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_crf_tier ON code_review_findings(tier) WHERE tier IS NOT NULL;
