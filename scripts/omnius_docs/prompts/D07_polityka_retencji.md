# D07: Polityka retencji i usuwania danych

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Polityka retencji i usuwania danych — Omnius',
    matter_type='policy_update',
    area_code='RODO',
    description='Polityka retencji Art. 5(1)(e) RODO. Okresy przechowywania per typ danych, procedura usuwania, automatyczne purge.',
    priority='high',
    source_regulation='EU 2016/679 Art. 5(1)(e), Kodeks Pracy Art. 94, Ordynacja podatkowa Art. 70, REMIT Art. 8'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='policy',
    title='Polityka retencji i usuwania danych osobowych — System Omnius',
    template_hint='''Polityka retencji zgodna z Art. 5(1)(e) RODO (ograniczenie przechowywania).

STRUKTURA:
§1 Postanowienia ogólne: cel, zakres, definicje, podstawa prawna
§2 Okresy retencji (TABELA dla KAŻDEGO typu danych):
- Email treść: 3 lata (Art. 118 KC przedawnienie)
- Email metadane: 3 lata
- Teams wiadomości: 3 lata
- WhatsApp: 1 rok (minimalizacja)
- Kalendarz: 2 lata
- Nagrania audio oryginał: 6 miesięcy (usunąć po transkrypcji)
- Transkrypcje audio: 2 lata
- Dokumenty korporacyjne: wg IKD spółki
- Ekstrakcje AI (entities/events): 3 lata (nie dłużej niż źródło)
- Embeddings: wraz z danymi źródłowymi
- Analiza efektywności komunikacji: 12 mies rolling
- Oceny pracownicze AI: czas zatrudnienia + 3 lata (Art. 291 KP)
- Zobowiązania: 3 lata (przedawnienie)
- Logi audytu: 5 lat (Art. 74 Ordynacji podatkowej)
- Komunikacja handlowa energią: 5 lat (REMIT)
- Dane tradera: 5-7 lat (REMIT Art. 8)
§3 Procedura automatycznego usuwania: cron job, opis mechanizmu, logowanie operacji
§4 Usuwanie na żądanie (Art. 17 RODO): procedura, termin, logowanie
§5 Wyjątki: litigation hold, kontrola organu, postępowanie karne
§6 Backup: rotacja 30 dni, usuwanie z backupów
§7 Przegląd polityki: co 12 miesięcy, odpowiedzialność
§8 Role: administrator, IOD, IT, dział prawny

PO POLSKU. Minimum 1200 słów.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}]
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
                    with open(f'{path}/07_Polityka_retencji_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
