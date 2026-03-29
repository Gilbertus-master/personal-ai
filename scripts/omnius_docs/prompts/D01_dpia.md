# D01: DPIA — Ocena skutków dla ochrony danych osobowych

## Zadanie
Wygeneruj KOMPLETNĄ Ocenę Skutków dla Ochrony Danych (DPIA) dla systemu AI "Omnius" wdrażanego w REH i REF. MUSISZ użyć istniejącego modułu compliance do rejestracji w DB ORAZ wygenerować pełne dokumenty na pulpit.

## Krok 1: Rejestracja w module compliance (Python)
Uruchom poniższy skrypt Python aby utworzyć sprawy i ryzyka w DB:

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter, advance_matter_phase, research_matter
from app.analysis.legal.risk_assessor import create_risk_assessment
from app.analysis.legal.document_generator import generate_document

# 1. Utwórz sprawę DPIA w module compliance
matter = create_matter(
    title='DPIA — Wdrożenie systemu AI Omnius (REH + REF)',
    matter_type='policy_update',
    area_code='RODO',
    description='Ocena skutków dla ochrony danych Art. 35 RODO — system Omnius przetwarza dane pracowników z email, Teams, WhatsApp, audio, dokumentów. Ekstrakcja encji/zdarzeń, analiza komunikacji, briefy zarządcze.',
    priority='critical',
    source_regulation='EU 2016/679 Art. 35 (RODO), EU 2024/1689 Art. 27 (AI Act)'
)
print(f'Matter created: id={matter[\"id\"]}')
matter_id = matter['id']

# 2. Uruchom research prawny
research = research_matter(matter_id)
print(f'Research: {research.get(\"status\", \"done\")}')

# 3. Utwórz ryzyka compliance
risks = [
    ('Naruszenie prywatności korespondencji', 'Monitoring email/Teams wykracza poza cel z Art. 22(3) KP', 'high', 'major'),
    ('Przetwarzanie danych szczególnych kategorii', 'Wellbeing = dane o zdrowiu (Art. 9 RODO) bez podstawy prawnej', 'high', 'catastrophic'),
    ('Rozpoznawanie emocji w miejscu pracy', 'Sentiment analysis może naruszać Art. 5(1)(f) AI Act — ZAKAZ', 'medium', 'catastrophic'),
    ('Automatyczne decyzje kadrowe', 'Oceny AI bez human review naruszają Art. 22 RODO', 'high', 'major'),
    ('Transfer danych do USA', 'Anthropic/OpenAI — ryzyko dostępu władz USA (FISA 702)', 'medium', 'major'),
    ('WhatsApp — brak podstawy prawnej', 'Przetwarzanie komunikacji z prywatnych urządzeń', 'high', 'major'),
    ('Wyciek danych do AI providera', 'Dane w promptach mogą zostać zalogowane przez Anthropic/OpenAI', 'low', 'catastrophic'),
    ('Chilling effect — zastraszenie pracowników', 'Monitoring AI ogranicza swobodę komunikacji', 'medium', 'moderate'),
    ('Dyskryminacja algorytmiczna', 'AI może faworyzować/dyskryminować na podstawie stylu komunikacji', 'medium', 'major'),
    ('Brak retencji — przechowywanie w nieskończoność', 'Chunks table bez TTL narusza Art. 5(1)(e) RODO', 'high', 'moderate'),
]
for title, desc, likelihood, impact in risks:
    r = create_risk_assessment(area_code='RODO', matter_id=matter_id, risk_title=title, risk_description=desc, likelihood=likelihood, impact=impact)
    print(f'Risk: {title} -> {r}')

# 4. Wygeneruj dokument przez document_generator
doc = generate_document(
    matter_id=matter_id,
    doc_type='risk_assessment',
    title='DPIA — Ocena skutków dla ochrony danych — System Omnius',
    template_hint='''To jest DPIA zgodna z Art. 35(7) RODO. MUSI zawierać:
1. Opis systematyczny operacji przetwarzania (email, Teams, WhatsApp, audio, dokumenty)
2. Cele: organizacja pracy, zarządzanie, compliance, bezpieczeństwo informacji
3. Podstawy prawne: Art. 6(1)(b)(c)(f) RODO, Art. 22(3) KP
4. Ocena niezbędności i proporcjonalności (test dla każdej funkcji)
5. Matryca ryzyka 10 ryzyk z prawdopodobieństwem i wpływem
6. Środki zaradcze (RBAC, human oversight, audit logging, retencja, szyfrowanie)
7. Art. 5(1)(f) AI Act: sentiment analysis MUSI być przeramowany jako analiza efektywności organizacyjnej
8. Plan przeglądów co 12 miesięcy
9. Decyzja: przetwarzanie dozwolone pod warunkami
Spółki: REH = Respect Energy Holding S.A., Podskarbińska 2, 03-833 Warszawa, KRS 0000935926. REF = Respect Energy Fuels sp. z o.o.
Podmioty przetwarzające: Anthropic PBC (USA, SCC), OpenAI Inc. (USA, SCC), Hetzner Online GmbH (DE), Microsoft (M365).
Minimum 2000 słów. Profesjonalny język prawniczy polski.''',
    signers=[
        {'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'},
        {'name': 'Inspektor Ochrony Danych', 'role': 'IOD'}
    ]
)
print(f'Document generated: id={doc.get(\"document_id\")}, status={doc.get(\"status\")}')
doc_id = doc.get('document_id')

# 5. Pobierz treść dokumentu z DB
if doc_id:
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                content = row[0]
                # Zapisz na pulpit
                for company, path in [('REH', '/mnt/c/Users/jablo/Desktop/Omnius_REH'), ('REF', '/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    output = content.replace('Respect Energy Holding S.A.', f'Respect Energy Holding S.A.' if company == 'REH' else 'Respect Energy Fuels sp. z o.o.')
                    fname = f'{path}/01_DPIA_Omnius_{company}.md'
                    with open(fname, 'w') as f:
                        f.write(output)
                    print(f'Saved: {fname}')
"
```

## Krok 2: Uzupełnienie dokumentu
Jeśli wygenerowany dokument jest zbyt krótki (< 500 linii), UZUPEŁNIJ go ręcznie używając narzędzia Write, dodając:
- Pełną matrycę ryzyk (tabela)
- Szczegółowy opis każdej operacji przetwarzania
- Test proporcjonalności dla: email, Teams, WhatsApp, audio, sentiment, wellbeing, employee evaluation
- Środki zaradcze per ryzyko
- Plan przeglądów
- Sekcję podpisów

Zapisz FINALNE wersje:
1. `/mnt/c/Users/jablo/Desktop/Omnius_REH/01_DPIA_Omnius_REH.md`
2. `/mnt/c/Users/jablo/Desktop/Omnius_REF/01_DPIA_Omnius_REF.md`

REH: Respect Energy Holding S.A., ul. Podskarbińska 2, 03-833 Warszawa, KRS: 0000935926, NIP: 5252929079
REF: Respect Energy Fuels sp. z o.o. (spółka zależna REH)

Dokument PO POLSKU, minimum 800 linii, profesjonalny język prawniczy.

## WAŻNE regulacje do uwzględnienia:
- Art. 35(7) RODO — wymagane elementy DPIA
- Art. 5(1)(f) AI Act — ZAKAZ rozpoznawania emocji w miejscu pracy (sentiment → „analiza efektywności komunikacji")
- Art. 22 RODO — zautomatyzowane decyzje indywidualne
- Art. 9 RODO — dane szczególnych kategorii (wellbeing → zdrowie)
- Art. 22(3) KP — cel monitoringu (organizacja pracy, NIE ocena pracowników)
- Art. 267 KK — nagrywanie rozmów (Plaud)
- Schrems II — transfer USA (SCC + TIA)
