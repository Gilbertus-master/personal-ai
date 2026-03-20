#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker exec -i gilbertus-postgres psql -v ON_ERROR_STOP=1 -U gilbertus -d gilbertus <<'SQL'
TRUNCATE event_candidate_chunks;

INSERT INTO event_candidate_chunks (chunk_id, reason)
SELECT DISTINCT
  c.id,
  CASE
    WHEN s.source_type IN ('whatsapp', 'email', 'chatgpt') THEN 'source_type'
    WHEN d.author IS NOT NULL AND btrim(d.author) <> '' THEN 'author'
    WHEN jsonb_array_length(d.participants) > 0 THEN 'participants'
    WHEN c.timestamp_start IS NOT NULL THEN 'timestamp'
    WHEN d.raw_path ILIKE '%whatsapp%' THEN 'raw_path_whatsapp'
    WHEN d.raw_path ILIKE '%email%' THEN 'raw_path_email'
    WHEN d.raw_path ILIKE '%chatgpt%' THEN 'raw_path_chatgpt'
    WHEN d.title ILIKE '%zosi%' OR d.title ILIKE '%zosią%' OR d.title ILIKE '%ewa%' THEN 'title_relationship'
    WHEN c.text ILIKE '%zosia%' OR c.text ILIKE '%ewa%' OR c.text ILIKE '%wojtek%' OR c.text ILIKE '%adaś%' THEN 'text_family'
    WHEN c.text ILIKE '%diagnoz%' OR c.text ILIKE '%asperger%' OR c.text ILIKE '%autyzm%' THEN 'text_health'
    WHEN c.text ILIKE '%zdecydowa%' OR c.text ILIKE '%postanowi%' OR c.text ILIKE '%podjąłem decyzję%' THEN 'text_decision'
    WHEN c.text ILIKE '%silent treatment%' OR c.text ILIKE '%konflikt%' OR c.text ILIKE '%kłótn%' THEN 'text_conflict'
    ELSE 'fallback'
  END AS reason
FROM chunks c
JOIN documents d ON d.id = c.document_id
JOIN sources s ON s.id = d.source_id
WHERE
    s.source_type IN ('whatsapp', 'email', 'chatgpt')
 OR (d.author IS NOT NULL AND btrim(d.author) <> '')
 OR jsonb_array_length(d.participants) > 0
 OR c.timestamp_start IS NOT NULL
 OR d.raw_path ILIKE '%whatsapp%'
 OR d.raw_path ILIKE '%email%'
 OR d.raw_path ILIKE '%chatgpt%'
 OR d.title ILIKE '%zosi%'
 OR d.title ILIKE '%ewa%'
 OR c.text ILIKE '%zosia%'
 OR c.text ILIKE '%ewa%'
 OR c.text ILIKE '%wojtek%'
 OR c.text ILIKE '%adaś%'
 OR c.text ILIKE '%diagnoz%'
 OR c.text ILIKE '%asperger%'
 OR c.text ILIKE '%autyzm%'
 OR c.text ILIKE '%zdecydowa%'
 OR c.text ILIKE '%postanowi%'
 OR c.text ILIKE '%podjąłem decyzję%'
 OR c.text ILIKE '%silent treatment%'
 OR c.text ILIKE '%konflikt%'
 OR c.text ILIKE '%kłótn%';

SQL
