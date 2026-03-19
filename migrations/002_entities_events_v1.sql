BEGIN;

-- 1) entities: minimalne rozszerzenie
ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS canonical_name TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_canonical_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);

CREATE UNIQUE INDEX IF NOT EXISTS uq_entities_canonical_type
  ON entities ((COALESCE(canonical_name, name)), entity_type);

-- 2) events: minimalne rozszerzenie
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS chunk_id BIGINT,
  ADD COLUMN IF NOT EXISTS confidence REAL,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_events_chunk'
  ) THEN
    ALTER TABLE events
      ADD CONSTRAINT fk_events_chunk
      FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_events_document_id ON events(document_id);
CREATE INDEX IF NOT EXISTS idx_events_chunk_id ON events(chunk_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time);

-- 3) chunk_entities
CREATE TABLE IF NOT EXISTS chunk_entities (
  id BIGSERIAL PRIMARY KEY,
  chunk_id BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  mention_text TEXT,
  confidence REAL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_entities_chunk_id ON chunk_entities(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_entities_entity_id ON chunk_entities(entity_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chunk_entities_unique_mention
  ON chunk_entities (chunk_id, entity_id, COALESCE(mention_text, ''));

-- 4) event_entities
CREATE TABLE IF NOT EXISTS event_entities (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  role TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_entities_event_id ON event_entities(event_id);
CREATE INDEX IF NOT EXISTS idx_event_entities_entity_id ON event_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_event_entities_role ON event_entities(role);

CREATE UNIQUE INDEX IF NOT EXISTS uq_event_entities_unique_role
  ON event_entities (event_id, entity_id, COALESCE(role, ''));

COMMIT;
