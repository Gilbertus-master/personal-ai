# M1: live_ingest + plaud UniqueViolation — ON CONFLICT

## Problem
`live_ingest` and `plaud_pipeline` throw `UniqueViolation` on the `uq_sources_type_name` constraint.
They try to INSERT a source row that already exists. Non-fatal but noisy and wasteful.

## Task
1. Find where sources are inserted:
   `grep -rn "INSERT.*sources\|insert_source" /home/sebastian/personal-ai/app/ --include="*.py" | head -20`
   `grep -rn "INSERT.*sources\|insert_source" /home/sebastian/personal-ai/scripts/ --include="*.py" --include="*.sh" | head -20`
2. Read the relevant function(s)
3. Add `ON CONFLICT (source_type, name) DO NOTHING` or `DO UPDATE SET imported_at = EXCLUDED.imported_at` as appropriate
4. Make sure ALL callers are fixed, not just one
5. Test by running: `docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT source_type, name FROM sources WHERE source_type IN ('whatsapp_live', 'audio_transcript') LIMIT 5;"`

## Constraints
- Parameterized SQL only
- Use connection pool
- Project at /home/sebastian/personal-ai
