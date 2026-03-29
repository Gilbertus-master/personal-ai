# D08: Procedura realizacji praw podmiotów danych

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Procedura realizacji praw podmiotów danych — Omnius',
    matter_type='documentation',
    area_code='RODO',
    description='Procedura obsługi żądań Art. 15-22 RODO: dostęp, sprostowanie, usunięcie, ograniczenie, przenoszenie, sprzeciw, automatyczne decyzje.',
    priority='high',
    source_regulation='EU 2016/679 Art. 12-22'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='procedure',
    title='Procedura realizacji praw podmiotów danych w systemie Omnius',
    template_hint='''Procedura obsługi żądań podmiotów danych (DSR) zgodna z Art. 12-22 RODO.

STRUKTURA:
§1 Cel i zakres
§2 Definicje (podmiot danych, żądanie, IOD, administrator)
§3 Kanały składania żądań: email IOD, formularz, pismo
§4 Weryfikacja tożsamości: dokument ze zdjęciem, weryfikacja emailowa
§5 Termin realizacji: 1 miesiąc, przedłużenie do 3 mies z uzasadnieniem (Art. 12(3))

§6 Katalog praw i sposób realizacji:
a) Prawo dostępu (Art. 15) — eksport danych z tabel: chunks, entities, events, commitments, insights. Format: PDF lub JSON. Technicznie: SQL SELECT WHERE podmiot = %s
b) Sprostowanie (Art. 16) — korekta encji (entities), zdarzeń (events). Logowanie zmian.
c) Usunięcie (Art. 17) — DELETE z chunks, entities, events, embeddings (Qdrant), commitments. Cascade. Logowanie.
d) Ograniczenie przetwarzania (Art. 18) — oznaczenie chunków flagą restricted=true, wykluczenie z ekstrakcji i wyszukiwania
e) Przenoszenie (Art. 20) — eksport w formacie JSON/CSV: dane źródłowe + ekstrakcje
f) Sprzeciw (Art. 21) — wobec przetwarzania na podst. Art. 6(1)(f), wobec profilowania. Procedura zaprzestania.
g) Automatyczne decyzje (Art. 22) — prawo do interwencji człowieka, wyrażenia stanowiska, zakwestionowania. Procedura human review.

§7 Wzór formularza żądania (do wypełnienia)
§8 Rejestr żądań: data, typ, status, termin, realizacja
§9 Odmowa: kiedy (Art. 12(5) nadużycie, Art. 17(3) wyjątki), uzasadnienie pisemne
§10 Role: IOD (nadzór), IT (realizacja techniczna), kadry (weryfikacja)
§11 Archiwizacja żądań: 5 lat od realizacji

PO POLSKU. Minimum 1000 słów.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}, {'name': 'IOD', 'role': 'Inspektor Ochrony Danych'}]
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
                    with open(f'{path}/08_Procedura_praw_podmiotow_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
