-- Fix duplicate sources rows created on every cron run
-- Add unique constraint so insert_source() can upsert safely

-- First deduplicate: keep the lowest id for each (source_type, source_name) pair,
-- re-point documents to the surviving row, then delete the duplicates.
DO $$
DECLARE
    dup RECORD;
    survivor_id BIGINT;
BEGIN
    FOR dup IN
        SELECT source_type, source_name
        FROM sources
        GROUP BY source_type, source_name
        HAVING COUNT(*) > 1
    LOOP
        SELECT MIN(id) INTO survivor_id
        FROM sources
        WHERE source_type = dup.source_type AND source_name = dup.source_name;

        UPDATE documents
        SET source_id = survivor_id
        WHERE source_id IN (
            SELECT id FROM sources
            WHERE source_type = dup.source_type
              AND source_name = dup.source_name
              AND id <> survivor_id
        );

        DELETE FROM sources
        WHERE source_type = dup.source_type
          AND source_name = dup.source_name
          AND id <> survivor_id;
    END LOOP;
END $$;

ALTER TABLE sources
    ADD CONSTRAINT uq_sources_type_name UNIQUE (source_type, source_name);
