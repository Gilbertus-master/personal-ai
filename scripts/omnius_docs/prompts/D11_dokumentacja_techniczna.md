# D11: Dokumentacja techniczna systemu AI (Art. 11 AI Act)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Dokumentacja techniczna systemu AI Omnius (Art. 11 AI Act)',
    matter_type='documentation',
    area_code='INTERNAL_AUDIT',
    description='Dokumentacja techniczna wymagana przez Art. 11 + Annex IV AI Act dla systemu high-risk. Opis architektury, modeli AI, danych, monitoringu, zarządzania ryzykiem.',
    priority='high',
    source_regulation='EU 2024/1689 Art. 11, Annex IV'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='report',
    title='Dokumentacja techniczna systemu AI Omnius — Art. 11 AI Act',
    template_hint='''Dokumentacja techniczna zgodna z Art. 11 i Annex IV Rozporządzenia AI Act (EU 2024/1689).

STRUKTURA (Annex IV):
1. OPIS OGÓLNY SYSTEMU AI
   - Nazwa: Omnius, wersja: 1.0
   - Przeznaczenie: korporacyjny asystent AI wspierający zarządzanie organizacją pracy
   - Klasyfikacja: High-Risk (Annex III, pkt 4(a)(b))
   - Deployer: REH S.A. / REF sp. z o.o.
   - Provider: development wewnętrzny, modele AI: Claude (Anthropic), OpenAI Embeddings

2. ARCHITEKTURA SYSTEMU
   - Stack: Python, FastAPI, PostgreSQL 16, Qdrant, Docker
   - Źródła danych: 11 typów (email, Teams, WhatsApp, kalendarz, audio, dokumenty, ...)
   - Pipeline: Ingestion → Chunking → Extraction (entities 5 typów, events 15 typów) → Embedding → Retrieval → Generation
   - 179 API endpoints, 42 cron jobs, 44 MCP tools
   - Infrastruktura: Hetzner (EU), Docker containers

3. MODELE AI I ALGORYTMY
   - Claude Sonnet/Haiku (Anthropic) — NLP, ekstrakcja, generacja
   - OpenAI text-embedding-3-small — wektoryzacja semantyczna
   - Whisper (local) — transkrypcja audio
   - Brak fine-tuningu, prompt-based approach
   - Temperature, max_tokens, system prompts

4. DANE TRENINGOWE I WALIDACYJNE
   - System NIE jest trenowany na danych — używa modeli pre-trained
   - Dane wejściowe: 99,905 chunks, 33,617 dokumentów z 11 źródeł
   - Walidacja: QC daily checks, non-regression monitoring

5. METRYKI WYDAJNOŚCI
   - Extraction coverage: 98.7%
   - API uptime: 99.9% (mierzone przez health checks co 30 min)
   - Response latency: <2s (ask endpoint)
   - Embedding coverage: chunks z embeddings / total chunks

6. SYSTEM ZARZĄDZANIA RYZYKIEM (Art. 9)
   - Odesłanie do dokumentu D12
   - Ciągły monitoring via 42 cronów
   - Non-regression gate

7. LOGOWANIE I TRACEABILITY (Art. 12)
   - Structured logging (structlog)
   - API cost tracking per request
   - Audit logging w RBAC (każdy dostęp logowany)
   - Retention logów: 5 lat

8. NADZÓR LUDZKI (Art. 14)
   - Odesłanie do dokumentu D13
   - RBAC 7 poziomów, human-in-the-loop dla decyzji kadrowych
   - Kill switch: CEO/admin może wyłączyć dowolny moduł

9. CYBERBEZPIECZEŃSTWO (Art. 15)
   - TLS in-transit, encryption at-rest (PostgreSQL)
   - Qdrant z autentykacją API key
   - CORS policy, security headers
   - Gitleaks pre-commit, pip-audit weekly
   - Container hardening (non-root, read-only fs)

10. ZARZĄDZANIE ZMIANAMI
    - Git version control, 83+ commits
    - Automated code review + auto-fixer
    - Non-regression testing per deploy

PO POLSKU. Dokument techniczny ale czytelny dla regulatora. Minimum 1500 słów.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu / CTO'}]
)
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/11_Dokumentacja_techniczna_AI_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
