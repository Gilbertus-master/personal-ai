# Gilbertus Albans — Pełna lista zdolności

## Dla Sebastiana (owner)

### Dane (11 źródeł, live)
- Email (Graph API) — sync co godzinę
- Teams (Graph API) — sync co godzinę
- WhatsApp (OpenClaw) — sync co 5 min
- Kalendarz (Graph API) — sync co godzinę
- Plaud audio — sync co 15 min, Whisper STT
- Dokumenty / SharePoint
- Spreadsheets
- ChatGPT exports
- Claude Code sessions
- Email attachments
- WhatsApp live (incoming messages)

### Intelligence (31 modułów)
**Core:** search + answer, timeline, summaries, morning brief, alerts
**People:** sentiment, wellbeing, delegation, network, blind spots
**Business:** commitments, contracts, opportunities, inefficiency, correlation
**Strategy:** strategic goals, org health, financial framework, cost estimator
**Market:** market intelligence (12 RSS sources), competitor intelligence (7 competitors), scenario analyzer
**Automation:** cron registry, self-improving rules (529), authority framework, delegation chain

### Delivery (proaktywne)
- **Morning brief** (7:00 CET) — kalendarz, market, competitors, focus, open loops, ludzie, anomalie
- **Weekly synthesis** (niedziela 20:00) — podsumowanie tygodnia z market/competitor/scenarios
- **Smart alerts** (8-22 CET, max 5/dzień) — market critical, competitor high, predictive
- **Response drafter** (co 15 min 8-20) — drafty odpowiedzi na emaile/Teams

### Komendy WhatsApp
```
brief           — poranny brief
market          — dashboard rynkowy (3 dni)
competitors     — przegląd konkurencji
scenarios       — lista scenariuszy "co jeśli?"
alerts          — aktywne alerty
status          — stan systemu
decision: X     — zapisz decyzję
gtd: X          — zapisz myśl/task
Gilbertusie task: X  — wykonaj zadanie
authorize: X    — utwórz standing order
```

### Voice (Etap 4)
- STT: Whisper (local)
- Komendy głosowe: te same co WhatsApp
- TTS: edge-tts (po instalacji)
- API: POST /voice/ask, POST /voice/command

### MCP Tools (39)
Dostępne w Claude Code jako narzędzia:
- gilbertus_ask, timeline, summary, brief, alerts, status, db_stats
- gilbertus_decide, people, lessons, costs
- gilbertus_evaluate, propose_action, pending_actions, self_rules
- gilbertus_opportunities, inefficiency, correlate
- gilbertus_commitments, meeting_prep, sentiment, wellbeing
- gilbertus_delegation, network, crons, authority
- gilbertus_decision_patterns, delegation_chain, response_stats
- gilbertus_finance, calendar, goals, org_health
- gilbertus_scenarios, market, competitors
- omnius_ask, omnius_command, omnius_status

### Cron jobs (30+)
Automatyczne: backup, ingestion, extraction, intelligence, communication, QC
