#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker exec -i gilbertus-postgres psql -v ON_ERROR_STOP=1 -U gilbertus -d gilbertus <<'SQL'
TRUNCATE event_candidate_chunks;

INSERT INTO event_candidate_chunks (chunk_id, reason, priority)
SELECT DISTINCT
  c.id,
  CASE
    WHEN c.text ILIKE '%zdecydowałem%' OR c.text ILIKE '%zdecydował%' OR c.text ILIKE '%postanowiłem%' OR c.text ILIKE '%postanowił%' OR c.text ILIKE '%podjąłem decyzję%' OR c.text ILIKE '%podjął decyzję%' THEN 'text_decision_strong'
    WHEN c.text ILIKE '%silent treatment%' OR c.text ILIKE '%kłótn%' OR c.text ILIKE '%pokłóciliśmy%' OR c.text ILIKE '%pokłóciliśmy się%' OR c.text ILIKE '%konflikt z%' OR c.text ILIKE '%spór z%' THEN 'text_conflict_strong'
    WHEN c.text ILIKE '%diagnoza asd%' OR c.text ILIKE '%asperger%' OR c.text ILIKE '%autyzm%' OR c.text ILIKE '%zdiagnozowano%' THEN 'text_health_strong'
    WHEN c.text ILIKE '%wojtek%' OR c.text ILIKE '%adaś%' OR c.text ILIKE '%mój syn%' OR c.text ILIKE '%moje dzieci%' THEN 'text_family_strong'
    WHEN s.source_type IN ('whatsapp', 'email') THEN 'source_personal'
    WHEN s.source_type = 'chatgpt' THEN 'source_chatgpt'
    WHEN d.author IS NOT NULL AND btrim(d.author) <> '' THEN 'author'
    WHEN jsonb_array_length(d.participants) > 0 THEN 'participants'
    ELSE 'fallback'
  END AS reason,
  CASE
    WHEN c.text ILIKE '%zdecydowałem%' OR c.text ILIKE '%zdecydował%' OR c.text ILIKE '%postanowiłem%' OR c.text ILIKE '%postanowił%' OR c.text ILIKE '%podjąłem decyzję%' OR c.text ILIKE '%podjął decyzję%' THEN 100
    WHEN c.text ILIKE '%silent treatment%' OR c.text ILIKE '%kłótn%' OR c.text ILIKE '%pokłóciliśmy%' OR c.text ILIKE '%pokłóciliśmy się%' OR c.text ILIKE '%konflikt z%' OR c.text ILIKE '%spór z%' THEN 95
    WHEN c.text ILIKE '%diagnoza asd%' OR c.text ILIKE '%asperger%' OR c.text ILIKE '%autyzm%' OR c.text ILIKE '%zdiagnozowano%' THEN 90
    WHEN c.text ILIKE '%wojtek%' OR c.text ILIKE '%adaś%' OR c.text ILIKE '%mój syn%' OR c.text ILIKE '%moje dzieci%' THEN 85
    WHEN s.source_type IN ('whatsapp', 'email') THEN 60
    WHEN s.source_type = 'chatgpt' THEN 25
    WHEN d.author IS NOT NULL AND btrim(d.author) <> '' THEN 15
    WHEN jsonb_array_length(d.participants) > 0 THEN 10
    ELSE 0
  END AS priority
FROM chunks c
JOIN documents d ON d.id = c.document_id
JOIN sources s ON s.id = d.source_id
WHERE
    c.text ILIKE '%zdecydowałem%'
 OR c.text ILIKE '%zdecydował%'
 OR c.text ILIKE '%postanowiłem%'
 OR c.text ILIKE '%postanowił%'
 OR c.text ILIKE '%podjąłem decyzję%'
 OR c.text ILIKE '%podjął decyzję%'
 OR c.text ILIKE '%silent treatment%'
 OR c.text ILIKE '%kłótn%'
 OR c.text ILIKE '%pokłóciliśmy%'
 OR c.text ILIKE '%pokłóciliśmy się%'
 OR c.text ILIKE '%konflikt z%'
 OR c.text ILIKE '%spór z%'
 OR c.text ILIKE '%diagnoza asd%'
 OR c.text ILIKE '%asperger%'
 OR c.text ILIKE '%autyzm%'
 OR c.text ILIKE '%zdiagnozowano%'
 OR c.text ILIKE '%wojtek%'
 OR c.text ILIKE '%adaś%'
 OR c.text ILIKE '%mój syn%'
 OR c.text ILIKE '%moje dzieci%'
 OR s.source_type IN ('whatsapp', 'email', 'chatgpt')
 OR (d.author IS NOT NULL AND btrim(d.author) <> '')
 OR jsonb_array_length(d.participants) > 0;

DELETE FROM event_candidate_chunks
WHERE priority = 0;

SQL
