# Gilbertus Albans — Available Commands

Commands available via WhatsApp and the API.

## /ask

Ask Gilbertus a question against the knowledge base.

**API:** `POST /ask`
**Example:** `/ask What did I discuss with Tomek last week?`

## /timeline

Query the event timeline with optional filters.

**API:** `POST /timeline`
**Example:** `/timeline date_from=2026-03-01`

## /brief

Get today's morning brief (auto-generated summary of recent activity).

**API:** `GET /brief/today`
**Example:** `/brief` or `/brief force=true days=14`

## /alerts

View proactive alerts (missed follow-ups, conflicts, health patterns).

**API:** `GET /alerts`
**Example:** `/alerts` or `/alerts refresh=true`

## /summary

Generate or query summaries (daily/weekly, by area).

**API:** `POST /summary/generate` | `POST /summary/query`
**Example:** `/summary generate date=2026-03-20` or `/summary query area=health`

## /decisions

Manage the decision journal.

**API:** see `/docs` for full schema
**Example:** `/decisions list` or `/decisions add ...`

## /insights

View extracted insights.

**API:** see `/docs` for full schema

## /status

System status dashboard — database stats, embedding progress, source breakdown, last backup, service health, and cron jobs.

**API:** `GET /status`
**Example:** `/status`

Returns:
- **db** — row counts for documents, chunks, entities, events, insights, summaries, alerts
- **embeddings** — total / done / pending
- **sources** — documents per source_type with newest date
- **last_backup** — timestamp of most recent database backup
- **services** — health of Postgres, Qdrant, Whisper
- **cron_jobs** — all scheduled background jobs
