# Gilbertus Albans — Architecture Decisions

## Purpose
Gilbertus Albans is my personal AI assistant for working on my own data archive first, and only later on higher-level analysis.
The goal of v1 is not to build agents, dashboards, or advanced life analytics.
The goal of v1 is to create a safe local environment, ingest my source data, index it semantically, and make it queryable through a simple Q&A backend.

## Principles
- build foundations first
- do not start from agents
- do not build UI before retrieval works
- keep v1 minimal and usable
- every imported record must preserve source and time context
- raw source files are stored separately from metadata and vectors
- no raw private data goes to Git

## Runtime
- Windows 11 host
- Ubuntu WSL2
- Docker Desktop WSL2 backend

## Project location
- main project folder: ~/personal-ai
- code runs from WSL filesystem, not from /mnt/c
- editor: VS Code on Windows connected to WSL

## Scope v1
- WhatsApp export ingestion
- ChatGPT export ingestion
- Teams export ingestion
- email export ingestion
- txt/docx/pdf ingestion
- Postgres for relational metadata
- Qdrant for semantic search
- FastAPI backend
- simple Q&A interface
- filtering by source
- filtering by time

## Scope v2
- entity extraction
- event extraction
- timeline queries
- weekly and monthly summaries
- better answer synthesis with citations
- richer filtering and views
- operational helper workflows

## Not now
- autonomous agents
- relationship analysis modules
- trading analysis modules
- dashboard BI layer
- OCR-heavy pipelines
- live email sync
- automatic alerts
- LangGraph orchestration before core retrieval is stable

## Core stack
- Python
- FastAPI
- Postgres
- Qdrant
- LlamaIndex
- Docker
- Claude Code
- OpenClaw / clawdbot
- LangGraph later

## Storage model
Three-layer storage model:
1. raw files
2. relational metadata
3. vector index

### Raw files
Stored under:
- data/raw/whatsapp
- data/raw/chatgpt
- data/raw/teams
- data/raw/email
- data/raw/docs

Raw files are treated as source-of-truth imports and are never edited manually after import.

### Relational metadata
Stored in Postgres.
Main logical objects:
- sources
- documents
- chunks
- entities
- events
- summaries

Minimum metadata expected for documents and chunks:
- source type
- source name
- title
- created_at or equivalent time field
- author
- participants
- raw_path
- chunk index
- chunk timestamps when available

### Vector index
Stored in Qdrant.
Each chunk gets:
- embedding vector
- chunk_id
- source metadata
- time metadata
- document reference

Qdrant metadata must support filtering by source and time.

## Ingestion order
The initial ingestion priority is:
1. WhatsApp
2. ChatGPT export
3. text documents (txt/docx/pdf)

Only after these are working well:
4. Teams
5. email

## Chunking
Initial chunking approach:
- 500–1000 tokens
- 10–15% overlap
- preserve timestamps and participant context whenever possible

## Retrieval
Initial retrieval design:
- semantic top-k search from Qdrant
- optional filters by source
- optional filters by time
- backend answer generated from retrieved chunks
- answer must expose source references

## Embeddings
- OpenAI text-embedding-3-large

## Security
- BitLocker on system drive
- encrypted backups
- no raw data in Git
- secrets in .env only
- use local storage for raw exports
- keep backup manifests in backups/manifests

## Git rules
- commit code and configs
- do not commit raw personal data
- do not commit .env
- do not commit exports, backups, or generated private archives

## Success criteria for v1
v1 is considered done when:
- I can import WhatsApp, ChatGPT exports, and documents
- chunks are stored with metadata in Postgres
- embeddings are indexed in Qdrant
- FastAPI can answer questions over my own archive
- I can filter answers by source and time
- the system is usable locally on my laptop

## Decision freeze
For v1 I do not change:
- runtime
- core databases
- embedding model
- backend framework
unless there is a hard technical blocker.