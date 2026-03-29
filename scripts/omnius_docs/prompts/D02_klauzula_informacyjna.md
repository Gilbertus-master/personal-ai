# D02: Klauzula informacyjna dla pracowników (RODO Art. 13/14)

## Zadanie
Wygeneruj KOMPLETNĄ klauzulę informacyjną dla pracowników o przetwarzaniu ich danych przez system AI "Omnius". Użyj modułu compliance do rejestracji w DB.

## Krok 1: Rejestracja w module compliance
```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

# 1. Utwórz obowiązek w module compliance
matter = create_matter(
    title='Klauzula informacyjna RODO — system Omnius',
    matter_type='documentation',
    area_code='RODO',
    description='Obowiązek informacyjny z Art. 13/14 RODO wobec pracowników, których dane przetwarza system AI Omnius. Dotyczy: email, Teams, WhatsApp, kalendarz, audio, dokumenty.',
    priority='critical',
    source_regulation='EU 2016/679 Art. 13, Art. 14'
)
matter_id = matter['id']
print(f'Matter: {matter_id}')

# 2. Generuj dokument
doc = generate_document(
    matter_id=matter_id,
    doc_type='communication',
    title='Klauzula informacyjna o przetwarzaniu danych osobowych w systemie Omnius',
    template_hint='''KOMPLETNA klauzula informacyjna Art. 13/14 RODO. MUSI zawierać ALL poniższe sekcje:

1. ADMINISTRATOR DANYCH: [nazwa spółki], [adres], KRS, kontakt, IOD
2. CELE PRZETWARZANIA I PODSTAWY PRAWNE (dla KAŻDEGO celu OSOBNO):
   - Organizacja pracy (Art. 6(1)(f) + Art. 22(3) KP)
   - Zarządzanie zasobami ludzkimi (Art. 6(1)(b))
   - Bezpieczeństwo informacji (Art. 6(1)(f))
   - Realizacja obowiązków prawnych (Art. 6(1)(c) — REMIT, archiwizacja)
   - Test równowagi (balancing test) dla Art. 6(1)(f)
3. KATEGORIE DANYCH: email treść/metadane, Teams wiadomości, kalendarz, dokumenty
4. ŹRÓDŁA DANYCH: Microsoft 365 Graph API, Plaud (audio), dokumenty korporacyjne
5. ODBIORCY: Anthropic PBC (USA), OpenAI Inc (USA), Microsoft, Hetzner Online GmbH (DE)
6. TRANSFER DO PAŃSTW TRZECICH: USA — Standard Contractual Clauses, opis zabezpieczeń
7. OKRES PRZECHOWYWANIA: per kategoria (email 3 lata, audio 6 mies, analityka 12 mies, logi 5 lat)
8. PRAWA OSOBY: dostęp (Art. 15), sprostowanie (16), usunięcie (17), ograniczenie (18), przenoszenie (20), sprzeciw (21), prawo do niepodlegania automatycznym decyzjom (22), skarga do UODO
9. INFORMACJA O ZAUTOMATYZOWANYM PRZETWARZANIU (Art. 13(2)(f)):
   - System AI analizuje treść komunikacji w celu generowania informacji zarządczych
   - System NIE podejmuje autonomicznych decyzji kadrowych
   - Każda rekomendacja AI jest weryfikowana przez człowieka
   - Logika: NLP, ekstrakcja encji/zdarzeń, wyszukiwanie semantyczne
   - Prawo do interwencji człowieka, wyrażenia stanowiska, zakwestionowania
10. OBOWIĄZEK PODANIA DANYCH: wynika z regulaminu pracy i Art. 22(3) KP

NIE używaj: „analiza sentymentu", „monitoring wellbeing", „rozpoznawanie emocji"
ZAMIAST TEGO: „analiza efektywności komunikacji organizacyjnej", „wsparcie organizacji pracy"

Minimum 1200 słów. Język przystępny ale precyzyjny prawnicznie. PO POLSKU.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}]
)
print(f'Doc: {doc}')
doc_id = doc.get('document_id')

if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH', '/mnt/c/Users/jablo/Desktop/Omnius_REH'), ('REF', '/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    content = row[0]
                    if co == 'REF':
                        content = content.replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.')
                        content = content.replace('KRS: 0000935926', 'KRS: [uzupełnić]')
                    with open(f'{path}/02_Klauzula_informacyjna_RODO_{co}.md', 'w') as f:
                        f.write(content)
                    print(f'Saved: {path}/02_Klauzula_informacyjna_RODO_{co}.md')
"
```

## Krok 2: Weryfikacja i uzupełnienie
Przeczytaj wygenerowane pliki. Jeśli brakuje którejś z 10 wymaganych sekcji, UZUPEŁNIJ ręcznie używając Write tool.
Upewnij się że dokument REF ma poprawną nazwę spółki (Respect Energy Fuels sp. z o.o.).
