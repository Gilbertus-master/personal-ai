# Data model v1

Minimal metadata model for Gilbertus Albans.

## Tables

### sources
- id
- source_type
- source_name
- imported_at

### documents
- id
- source_id
- title
- created_at
- author
- participants
- raw_path

### chunks
- id
- document_id
- chunk_index
- text
- timestamp_start
- timestamp_end
- embedding_id

### entities
- id
- name
- entity_type

### events
- id
- document_id
- event_type
- event_time
- summary

### summaries
- id
- summary_type
- period_start
- period_end
- text