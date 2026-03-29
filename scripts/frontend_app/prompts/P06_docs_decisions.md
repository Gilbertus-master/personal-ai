# Part 6: Documents, Decisions & Calendar

## Documents
- Upload zone: drag-and-drop (PDF, DOCX, XLSX, TXT, images)
- Upload progress indicator + backend ingestion status
- Search: full-text across all documents
- Browse: by source type (email, teams, whatsapp, document...)
- Document viewer: chunk highlights, metadata
- RBAC: upload = director+, browse = classification-filtered

## Decisions
- Journal: lista decisions z area, confidence, outcome rating
- Create: form z area, context, expected outcome, confidence slider
- Outcome tracker: add actual outcome + 1-5 star rating
- AI analysis: decision patterns (`/decision-intelligence`), trends
- Weekly synthesis: auto-generated

## Calendar
- Week view: events z Microsoft 365
- Conflict detection: highlighted overlaps
- Meeting prep: auto-generated brief per meeting
- Deep work blocks: schedule via UI
- Meeting ROI: analysis of meeting effectiveness
- Analytics: time distribution (meetings vs focus vs admin)

## API Endpoints
Documents: upload (new endpoint needed), search via `/ask`
Decisions: `/decision`, `/decisions`, `/decisions/patterns`, `/decision-intelligence`
Calendar: `/calendar/*`, `/meeting-prep`, `/meeting-minutes/*`

## RBAC
- Documents: director+ upload, classification-based browse
- Decisions: ceo+
- Calendar: manager+
