# Gilbertus Albans — Roadmap V2–V4

## Kontekst

V1 = archiwum + retrieval + encje/eventy + summaries + infrastruktura. Działa lokalnie na WSL2/Docker.

V2–V4 rozszerza system z **reaktywnego archiwum** na **proaktywny system kontroli** nad wszystkimi obszarami życia i biznesu.

### Architektura federacyjna: Gilbertus + Omnius

System składa się z trzech niezależnych instancji połączonych protokołem komunikacyjnym:

| Instancja | Lokalizacja | Rola | Dane |
|-----------|-------------|------|------|
| **Gilbertus** | Prywatna infrastruktura Sebastiana | Prywatny mentat — pełen obraz, cross-domain reasoning, decyzje strategiczne | Dane osobiste + read-only mirror danych firmowych |
| **Omnius REH** | Infrastruktura REH | Agent firmowy REH — operacje, CRM, ludzie, procesy | Tylko dane REH |
| **Omnius REF** | Infrastruktura REF | Agent firmowy REF — operacje, CRM, ludzie, procesy | Tylko dane REF |

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRYWATNA INFRASTRUKTURA (serwer Sebastiana)                        │
│                                                                     │
│  ┌───────────────────────────────────────┐                          │
│  │ GILBERTUS (prywatny mentat)           │                          │
│  │ - dane osobiste (email, audio, notes) │                          │
│  │ - dane firmowe (read-only mirror)     │                          │
│  │ - cross-domain correlation            │                          │
│  │ - decision journal                    │                          │
│  │ - morning brief                       │                          │
│  │ - command protocol → Omnius           │                          │
│  └──────────┬──────────────┬─────────────┘                          │
│             │              │                                        │
│     ┌───────┘              └────────┐                               │
│     │ read-only sync                │ read-only sync                │
│     │ + command protocol            │ + command protocol            │
└─────┼───────────────────────────────┼───────────────────────────────┘
      │                               │
┌─────┴─────────────────┐  ┌─────────┴───────────────┐
│ INFRASTRUKTURA REH    │  │ INFRASTRUKTURA REF      │
│                       │  │                         │
│ ┌───────────────────┐ │  │ ┌─────────────────────┐ │
│ │ OMNIUS REH        │ │  │ │ OMNIUS REF          │ │
│ │ - Email/Teams     │ │  │ │ - Email/Teams       │ │
│ │ - CRM/ERP         │ │  │ │ - CRM/ERP           │ │
│ │ - People data     │ │  │ │ - People data       │ │
│ │ - Project mgmt    │ │  │ │ - Project mgmt      │ │
│ │ - Audit log       │ │  │ │ - Audit log         │ │
│ └───────────────────┘ │  │ └─────────────────────┘ │
└───────────────────────┘  └─────────────────────────┘
```

**Przepływ danych:**
- Omnius REH/REF → Gilbertus: read-only sync (dane firmowe do cross-domain analysis)
- Gilbertus → Omnius REH/REF: command protocol (zatwierdzony action item → ticket, email, raport)
- Omnius REH ↛ Omnius REF: zero lateral data flow (separacja spółek)
- Dane osobiste Sebastiana nigdy nie trafiają do instancji Omnius

### Wymogi architektoniczne (obowiązują od V2)

1. **Prywatna infrastruktura** — żadne dane nie trafiają do third-party cloud (poza API calls do LLM)
2. **Separacja danych** — dane osobiste ≠ dane firmowe. Omnius → Gilbertus (read-only). Nigdy odwrotnie (poza command protocol).
3. **Separacja spółek** — dane REH ≠ dane REF. Każda spółka ma własną instancję Omnius.
4. **Compliance** — dostęp do danych firmowych musi mieć podstawę prawną. Pracownicy poinformowani o monitoringu.
5. **Docelowo self-hosted LLM** — eliminacja zależności od OpenAI/Anthropic API dla wrażliwych danych.

---

## V2: Proaktywna inteligencja

**Cel:** Gilbertus mówi Ci co jest ważne zanim zapytasz.

### V2.0 — Plaud Pin S audio transcription
**Problem:** Codzienne spotkania, rozmowy telefoniczne, notatki głosowe nie trafiają do systemu. Tracisz kontekst.

**Urządzenie:** Plaud Pin S — wearable audio recorder z wbudowanym AI transcription.

**Architektura integracji:**
```
┌──────────┐     Bluetooth/     ┌────────────┐    sync/     ┌──────────────┐
│ Plaud    │ ──► USB upload ──► │ Plaud App  │ ──► export ► │ Local dir    │
│ Pin S    │                    │ (telefon)  │              │ ~/plaud/     │
└──────────┘                    └────────────┘              └──────┬───────┘
                                                                  │
                                                    filesystem watcher
                                                                  │
                                                           ┌──────┴───────┐
                                                           │ Gilbertus    │
                                                           │ ingestion    │
                                                           │ pipeline     │
                                                           └──────────────┘
```

**Pipeline:**
1. **Filesystem watcher** — `inotifywait` na katalogu `~/plaud/` (nowe pliki .wav/.m4a/.txt)
2. **Transcription** — jeśli Plaud eksportuje tekst, użyj bezpośrednio; jeśli audio → Whisper (local lub API)
3. **Speaker diarization** — rozpoznanie kto mówi (Sebastian vs. rozmówcy); pyannote.audio lub Plaud built-in
4. **Chunking** — podział transkrypcji na semantyczne segmenty (per temat/speaker turn)
5. **Entity/event extraction** — standardowy pipeline V1 (encje, eventy, embedding)
6. **Source type** — `audio_transcript` z metadanymi: duration, participants, location (jeśli dostępne)

**Deliverables:**
- [ ] Filesystem watcher daemon na `~/plaud/`
- [ ] Audio transcription pipeline (Whisper local → fallback API)
- [ ] Speaker diarization integration
- [ ] Nowy source_type `audio_transcript` w schemacie
- [ ] Metadata extraction: czas trwania, uczestnicy, data nagrania
- [ ] Test end-to-end: nagranie → transkrypt → chunks → encje/eventy → retrieval

### V2.1 — Corporate email + Teams (Sebastian's comms)
**Problem:** Email firmowy i Teams to główne kanały komunikacji w REH/REF. Bez nich Gilbertus nie widzi 80% kontekstu biznesowego.

**Zakres:** Wyłącznie skrzynka mailowa Sebastiana i jego czaty w Teams — jego własna komunikacja jako członka zarządu. Nie dane innych pracowników.

| Źródło | Metoda | Priorytet |
|--------|--------|-----------|
| Email firmowy (Outlook) | Microsoft Graph API — polling nowych emaili z mailboxa Sebastiana | 🔴 Wysoki |
| Teams (czaty/kanały) | Microsoft Graph API — wiadomości z czatów Sebastiana | 🔴 Wysoki |
| Kalendarz firmowy | Microsoft Graph API — eventy z kalendarza Sebastiana | 🔴 Wysoki |

**Mechanizm:**
- Microsoft Graph API z delegated permissions (scope: `Mail.Read`, `Chat.Read`, `Calendars.Read`)
- OAuth2 authorization code flow — Sebastian loguje się swoim kontem
- Oddzielny source_type: `company_email`, `company_teams`, `company_calendar`
- Dane tagowane company_id (REH/REF) na podstawie tenant
- Inkrementalny sync co 15 min (delta query)

**Deliverables:**
- [ ] OAuth2 flow do Microsoft Graph (per tenant: REH, REF)
- [ ] Inkrementalny sync emaili (delta query → parser → chunks → embed)
- [ ] Teams chat sync (Sebastian's 1:1 i group chats)
- [ ] Calendar sync — eventy firmowe w timeline
- [ ] Filtr w /ask: `company_id` parameter

### V2.2 — Morning brief
**Problem:** Musisz sam pamiętać o co pytać. Gilbertus powinien sam powiedzieć.

**Mechanizm:**
1. Codziennie o zadanej godzinie (cron) Gilbertus generuje brief:
   - Otwarte pętle z ostatniego tygodnia (events bez closure)
   - Spotkania z kalendarza na dziś + kontekst (ostatnie interakcje z tymi osobami)
   - Anomalie z wczoraj (nietypowe wzorce w danych)
   - Nowe transkrypcje audio z ostatnich 24h — kluczowe punkty
   - Top 3 rzeczy wymagające uwagi
2. Brief dostarczany jako: plik markdown, email do siebie, lub endpoint API

**Deliverables:**
- [ ] `scripts/generate_morning_brief.sh` + cron
- [ ] Endpoint `GET /brief/today`
- [ ] Template briefu z sekcjami: Focus, Otwarte pętle, Spotkania, Audio highlights, Anomalie

### V2.3 — Decision journal
**Problem:** Podejmujesz decyzje ale nie śledzisz outcomes. Nie uczysz się z patterns.

**Mechanizm:**
1. Nowa tabela `decisions`: decision_text, context, expected_outcome, area, decided_at
2. Nowa tabela `decision_outcomes`: decision_id, actual_outcome, outcome_date, rating
3. Endpoint `POST /decision` — loguj decyzję
4. Endpoint `POST /decision/{id}/outcome` — loguj wynik
5. Cron: co tydzień/miesiąc raport: "Twoje decyzje pod presją czasu mają X% gorszy outcome" / "Decyzje w obszarze Y konsekwentnie dobre"

**Deliverables:**
- [ ] Migracja SQL: decisions + decision_outcomes
- [ ] Endpointy CRUD
- [ ] Raport decision patterns (per area, per warunki)

### V2.4 — Cross-domain correlation engine
**Problem:** Nie widzisz jak stres wpływa na trading, jak konflikty wpływają na decyzje biznesowe.

**Mechanizm:**
1. Event timeline enrichment — tagowanie eventów z wieloma domenami
2. Correlation queries: "pokaż mi tygodnie z konfliktem relacyjnym i ich trading performance"
3. Periodic report: korelacje między obszarami
4. Wymaga danych z audio (V2.0) + calendar (V2.1) + decision journal (V2.3) + istniejące eventy

**Deliverables:**
- [ ] Endpoint `POST /correlate` z parametrami area_a, area_b, metric, period
- [ ] Wizualizacja (opcjonalnie: generowanie wykresu, eksport CSV)

### V2.5 — Self-hosted LLM (opcjonalnie, równolegle)
**Problem:** Wrażliwe dane osobiste i firmowe przechodzą przez API OpenAI/Anthropic.

**Opcje:**
- Llama 3.1 70B / Mistral Large na prywatnym GPU (RTX 4090 lub wynajmowany dedykowany serwer)
- Hybrid: self-hosted dla embeddingów i ekstrakcji, cloud API dla complex reasoning
- Szacunkowy koszt: jednorazowo ~$2-5k (GPU) vs. ongoing API costs

**Deliverables:**
- [ ] Benchmarki: porównanie jakości odpowiedzi self-hosted vs. API
- [ ] Konfiguracja `EMBEDDING_MODEL` i `ANTHROPIC_MODEL` na self-hosted endpoints
- [ ] Dokumentacja: kiedy używać local vs. API

---

## V3: Omnius — agenci firmowi

**Cel:** Omnius jako autonomiczny system nerwowy spółek REH i REF. Pełna widoczność bez micromanagementu. Dane firmowe pozostają w infrastrukturze firmowej.

### V3.0 — Compliance i infrastruktura
**Przed jakimkolwiek deploymentem Omnius.**

**Checklist prawny:**
- [ ] Audyt z prawnikiem: podstawa prawna przetwarzania danych firmowych (art. 6.1.f RODO — prawnie uzasadniony interes + art. 6.1.b wykonanie umowy)
- [ ] Jeśli people analytics: polityka monitoringu, informacja dla pracowników, analiza proporcjonalności
- [ ] Data processing agreement (DPA) — regulacja przepływu danych Omnius → Gilbertus
- [ ] Polityka retencji: jak długo dane żyją w każdej instancji
- [ ] Szyfrowanie: at rest (LUKS/dm-crypt) + in transit (mTLS między instancjami)
- [ ] Access control: Omnius REH/REF — zarząd spółki; Gilbertus — tylko Sebastian
- [ ] Audit log: każdy dostęp do danych firmowych logowany, każda komenda Gilbertus→Omnius logowana

**Deliverables:**
- [ ] Opinia prawna (zewnętrzna)
- [ ] Dokument architektury federacyjnej (Gilbertus + Omnius REH + Omnius REF)
- [ ] DPA template per spółka
- [ ] Szyfrowanie dysków/wolumenów per instancja
- [ ] Audit log w Postgres (per instancja)
- [ ] mTLS setup dla komunikacji między instancjami

### V3.1 — Omnius REH setup
**Pierwsza instancja firmowa — REH (energia).**

**Mechanizm:**
- Dedykowany serwer/VM w infrastrukturze REH
- Własna baza PostgreSQL, własny vector store
- Microsoft Graph API connector (Exchange + Teams + SharePoint) — dane całej organizacji REH
- Ingestion pipeline: email → chunks → entities/events → embeddings
- Read-only sync do Gilbertusa (scheduled export, dane zanonimizowane gdzie wymagane)

**Deliverables:**
- [ ] Deployment Omnius REH na infrastrukturze firmowej
- [ ] Microsoft Graph integration (organization-wide, z admin consent)
- [ ] Ingestion pipeline per source type
- [ ] Read-only sync endpoint → Gilbertus
- [ ] Audit log aktywny od dnia 1

### V3.2 — Omnius REF setup
**Druga instancja firmowa — REF (energia).**

**Mechanizm:** Identyczny jak V3.1, osobna infrastruktura, osobne dane.

**Deliverables:**
- [ ] Deployment Omnius REF na infrastrukturze firmowej
- [ ] Microsoft Graph integration (organization-wide)
- [ ] Ingestion pipeline per source type
- [ ] Read-only sync endpoint → Gilbertus
- [ ] Audit log aktywny od dnia 1

### V3.3 — CRM/ERP integration via Omnius
**Problem:** Nie widzisz statusu projektów, pipeline'u klientów, finansów.

**Źródła:** CRM (HubSpot/Pipedrive/Salesforce), ERP, PM (Jira/Asana/Linear) — per spółka.

**Mechanizm:**
- Connectory w Omnius REH/REF per narzędzie (plugin architecture)
- API polling: nowe/zmienione deals, tickets, tasks, faktury
- Mapowanie na encje: client → entity, project → entity, employee → entity
- Status tracking: deadline approaching, overdue, blocked
- Dane syncowane do Gilbertusa (read-only, z entity linking)

**Deliverables:**
- [ ] Plugin architecture w Omnius dla connectorów
- [ ] CRM connector (per spółka)
- [ ] ERP connector (per spółka)
- [ ] Entity linking: firmowe encje ↔ prywatne encje w Gilbertusie
- [ ] Dashboard query: "pokaż mi wszystkie opóźnione projekty w REH"

### V3.4 — People analytics via Omnius
**Problem:** Nie wiesz kto dostarcza, kto blokuje, gdzie są komunikacyjne bottlenecki.

**Wymaga compliance V3.0 — polityka monitoringu, informacja dla pracowników.**

**Mechanizm:**
- Analiza w Omnius (dane nie opuszczają infrastruktury firmowej)
- Communication patterns: kto z kim, jak często, czas odpowiedzi
- Task completion rate per osoba
- Sentiment analysis na komunikacji (health procesu, nie ocena człowieka)
- Bottleneck detection: "ta osoba jest na ścieżce krytycznej 5 projektów"
- Do Gilbertusa trafiają tylko zagregowane raporty (nie surowe dane pracowników)

**Deliverables:**
- [ ] Raport per osoba: communication volume, task completion, response time
- [ ] Raport per zespół: flow, blockers, overload
- [ ] Alert: "X nie odpowiada na critical path emails od 3 dni"
- [ ] Zagregowany sync do Gilbertusa (raporty, nie raw data)

### V3.5 — Automation radar
**Problem:** Nie wiesz co można zautomatyzować.

**Mechanizm:**
- Pattern detection w Omnius na task/email/chat data: powtarzające się czynności
- Cost estimation: "ta czynność kosztuje ~Xh/msc, automatyzacja kosztuje ~Y"
- Recommendation engine: "top 5 procesów do automatyzacji w tym kwartale"
- Rekomendacje syncowane do Gilbertusa → cross-company comparison

**Deliverables:**
- [ ] Raport: repetitive tasks, estimated savings, suggested automation
- [ ] Tracking: po wdrożeniu automatyzacji, mierz faktyczne savings
- [ ] Cross-company view w Gilbertusie: "REH zautomatyzował X, REF może zrobić to samo"

---

## V4: Orkiestracja i agenci

**Cel:** Gilbertus nie tylko analizuje — działa w Twoim imieniu po zatwierdzeniu, delegując wykonanie do instancji Omnius.

### V4.1 — Gilbertus → Omnius command protocol
**Problem:** Gilbertus widzi cross-domain insights, ale nie może na nie reagować w systemach firmowych.

**Mechanizm:**
```
Gilbertus                         Omnius REH/REF
    │                                  │
    │  POST /command                   │
    │  { type: "create_ticket",        │
    │    payload: {...},               │
    │    approved_by: "sebastian",     │
    │    approval_timestamp: "...",    │
    │    signature: "..." }            │
    │ ──────────────────────────────►  │
    │                                  │  validate signature
    │                                  │  execute action
    │  { status: "executed",           │  log to audit
    │    result: {...} }               │
    │ ◄──────────────────────────────  │
    │                                  │
```

**Supported commands:**
- `create_ticket` — utwórz ticket w Jira/Asana
- `send_email` — wyślij email z konta firmowego
- `schedule_meeting` — dodaj event do kalendarza
- `create_report` — wygeneruj raport w Omnius i wyślij

**Deliverables:**
- [ ] Command protocol spec (JSON schema, auth, signing)
- [ ] Command endpoint w Omnius REH/REF
- [ ] Command client w Gilbertusie
- [ ] Approval flow: Gilbertus proponuje → Sebastian zatwierdza → Omnius wykonuje
- [ ] Audit trail per command (obie strony)

### V4.2 — Action items i delegowanie
- Gilbertus identyfikuje co trzeba zrobić (z morning brief, anomalii, raportów, transkrypcji audio)
- Proponuje action item z assignee, deadline, kontekstem
- Po zatwierdzeniu: wysyła command do odpowiedniej instancji Omnius
- Omnius wykonuje: tworzy ticket, wysyła email, dodaje do kalendarza
- Gilbertus śledzi execution: czy zrobione na czas (via read-only sync)

### V4.3 — Automated reporting
- Cotygodniowy board report per spółka (generowany przez Omnius, syncowany do Gilbertusa)
- Miesięczny "state of the empire" — cross-company summary (generowany przez Gilbertusa z danych obu Omniusów)
- Trading journal: automatyczny wpis po każdej zamkniętej pozycji z kontekstem (co myślałeś, co się stało)

### V4.4 — Continuous improvement engine
- Kwartalny raport: co poprawić, kogo zmienić, jakie procesy zrestrukturyzować
- Benchmarking: porównanie REH vs. REF (procesy, velocity, efficiency)
- Feedback loop: rekomendacja → command do Omnius → pomiar efektu → aktualizacja modelu

### V4.5 — Multi-agent orchestration (LangGraph)
- Gilbertus jako orchestrator z sub-agentami per domena
- Omnius REH/REF jako remote agents (command protocol)
- Specjalizowani agenci wewnątrz Gilbertusa: TradingAgent, RelationshipAgent, WellbeingAgent
- Specjalizowani agenci wewnątrz Omnius: HRAgent, FinanceAgent, ProjectAgent
- Human-in-the-loop: krytyczne decyzje wymagają zatwierdzenia Sebastiana

---

## Harmonogram orientacyjny

| Wersja | Zakres | Szacunkowy czas | Zależności |
|--------|--------|-----------------|------------|
| **V1** | Archiwum, retrieval, ekstrakcja, summaries | ✅ Ukończone | — |
| **V2.0** | Plaud Pin S audio transcription | 1-2 tyg | Plaud Pin S (arriving) |
| **V2.1** | Corporate email/Teams (Sebastian's comms) | 2-3 tyg | Microsoft Graph OAuth |
| **V2.2** | Morning brief | 1 tyg | V2.0 + V2.1 |
| **V2.3** | Decision journal | 1 tyg | — |
| **V2.4** | Cross-domain correlation | 2 tyg | V2.3 + events |
| **V2.5** | Self-hosted LLM | 2-4 tyg | Hardware (GPU) |
| **V3.0** | Compliance + architektura federacyjna | 2-4 tyg | Prawnik |
| **V3.1** | Omnius REH setup | 3-4 tyg | V3.0 + infra REH |
| **V3.2** | Omnius REF setup | 2-3 tyg | V3.0 + infra REF |
| **V3.3** | CRM/ERP via Omnius | 3-4 tyg | V3.1/V3.2 + API access |
| **V3.4** | People analytics via Omnius | 3-4 tyg | V3.1/V3.2 + compliance |
| **V3.5** | Automation radar | 2-3 tyg | V3.3 |
| **V4.1** | Gilbertus→Omnius command protocol | 2-3 tyg | V3.1/V3.2 |
| **V4.2** | Action items + delegowanie | 3-4 tyg | V4.1 |
| **V4.3** | Automated reporting | 2 tyg | V3.3 |
| **V4.4** | Continuous improvement | 2-3 tyg | V4.3 + 3 msc danych |
| **V4.5** | Multi-agent orchestration | 4-8 tyg | Wszystko powyżej |

**Sugerowana kolejność startu po V1:**
1. **V2.0 (Plaud Pin S)** — natychmiast, urządzenie dostępne
2. V2.1 (corporate email/Teams) + V2.3 (decision journal) — równolegle
3. V2.2 (morning brief) — gdy mamy audio + email feeds
4. V3.0 (compliance) — równolegle z V2
5. V2.4 (korelacje) — gdy mamy decision journal + live data
6. V3.1 (Omnius REH) → V3.2 (Omnius REF) — po compliance
7. V4.1 (command protocol) — gdy Omnius działa
8. Dalej iteracyjnie

---

## Szczegóły integracji: Plaud Pin S

### Specyfikacja urządzenia
- Wearable audio recorder z magnetycznym klipsem
- Nagrywanie: spotkania, rozmowy telefoniczne, notatki głosowe
- Eksport: via Plaud app → pliki audio (.m4a/.wav) + transkrypcje (.txt)
- Diarization: wbudowane rozpoznawanie mówców (Plaud AI)

### Filesystem watcher — architektura
```bash
# Watcher daemon (systemd unit)
inotifywait -m -r -e create,moved_to ~/plaud/ |
while read dir action file; do
    case "$file" in
        *.txt)  # Plaud transcript
            python3 -m app.ingestion.audio_transcript "$dir$file"
            ;;
        *.m4a|*.wav)  # Raw audio — transcribe first
            python3 -m app.ingestion.audio_whisper "$dir$file"
            ;;
    esac
done
```

### Pipeline przetwarzania
```
Audio file (.m4a/.wav)
    │
    ├── [jeśli brak transkrypcji z Plaud]
    │   └── Whisper (local) → transkrypt .txt
    │
    ▼
Transkrypt (.txt)
    │
    ├── Speaker diarization (jeśli nie z Plaud)
    │   └── pyannote.audio → speaker labels
    │
    ├── Metadata extraction
    │   ├── data nagrania (z filename/EXIF)
    │   ├── czas trwania
    │   └── uczestnicy (z diarization)
    │
    ├── Chunking
    │   └── split per speaker turn / temat
    │
    ├── Entity extraction (V1 pipeline)
    │
    ├── Event extraction (V1 pipeline)
    │
    └── Embedding + storage
        └── source_type = 'audio_transcript'
```

### Schemat danych
```sql
-- Nowe pola w chunks / sources
source_type = 'audio_transcript'
metadata = {
    "device": "plaud_pin_s",
    "duration_seconds": 3600,
    "participants": ["Sebastian", "Jan Kowalski"],
    "recording_date": "2026-03-23",
    "diarization": true,
    "language": "pl"
}
```

---

## Pryncypia architektoniczne (obowiązują przez cały lifecycle)

1. **Privacy first** — dane osobiste nigdy nie opuszczają prywatnej infrastruktury Gilbertusa
2. **Federacja** — każda spółka ma własną instancję Omnius w swojej infrastrukturze
3. **Separacja danych** — Omnius → Gilbertus (read-only). Gilbertus → Omnius (command protocol, zatwierdzone akcje). Nigdy surowe dane osobiste → Omnius.
4. **Separacja spółek** — Omnius REH ↛ Omnius REF. Zero lateral data flow.
5. **Compliance by design** — audit log, retencja, podstawa prawna przed wdrożeniem
6. **Incremental value** — każdy krok daje wartość sam w sobie, nie wymaga kolejnych
7. **Grounded** — odpowiedzi oparte na źródłach, nie halucynacje
8. **Auditable** — każda odpowiedź, decyzja, rekomendacja, komenda do prześledzenia
9. **Human-in-the-loop** — Gilbertus proponuje, Sebastian zatwierdza (krytyczne akcje i komendy do Omnius)
