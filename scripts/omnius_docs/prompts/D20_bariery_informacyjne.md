# D20: Polityka barier informacyjnych (REMIT compliance)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Polityka barier informacyjnych — REMIT + Omnius', matter_type='policy_update', area_code='URE', description='Polityka Chinese Walls / Information Barriers dla systemu AI Omnius w kontekście handlu energią. REMIT Art. 3-5: zakaz insider trading, manipulacji, obowiązek ujawnienia.', priority='medium', source_regulation='EU 1227/2011 (REMIT) Art. 3, 4, 5')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='policy', title='Polityka barier informacyjnych — REMIT compliance w systemie Omnius', template_hint='''Polityka Chinese Walls / Information Barriers dla AI w kontekście REMIT.

§1 Cel: zapewnienie że system AI Omnius NIE tworzy niedozwolonej asymetrii informacyjnej na rynku energii
§2 Definicje: informacja wewnętrzna (inside information, Art. 2(1) REMIT), manipulacja rynkowa (Art. 2(2-3)), bariery informacyjne, Chinese Wall
§3 Klasyfikacja danych w kontekście REMIT:
  - Dane handlowe (trade events): transakcje, ceny, wolumeny — MARKET_SENSITIVE
  - Dane operacyjne: produkcja, awarie, maintenance — MARKET_SENSITIVE jeśli wpływa na podaż
  - Dane korporacyjne: HR, finanse, compliance — NON_SENSITIVE

§4 Bariery w systemie Omnius:
  a) RBAC: dane trade events dostępne TYLKO dla CEO i autoryzowanych traderów
  b) Dane z różnych jednostek biznesowych NIE są łączone w jednym raporcie jeśli zawierają inside information
  c) Briefy zarządcze: filtrowane z market-sensitive data chyba że odbiorca jest autoryzowany
  d) AI NIE generuje rekomendacji handlowych (trading signals) — tylko raportuje zdarzenia
  e) Alerty dotyczące transakcji idą WYŁĄCZNIE do CEO

§5 Obowiązki:
  a) Zakaz wykorzystywania informacji wewnętrznej z Omnius do handlu (Art. 3 REMIT)
  b) Zakaz manipulacji rynkowej z użyciem danych AI (Art. 5 REMIT)
  c) Obowiązek ujawnienia informacji wewnętrznej (Art. 4 REMIT) — system Omnius NIE zwalnia z tego obowiązku

§6 Kontrola dostępu do danych handlowych:
  - Logowanie KAŻDEGO dostępu do trade events
  - Kwartalny przegląd logów przez compliance
  - Alert przy nietypowym wzorcu dostępu

§7 Retencja danych handlowych: 5-7 lat (zgodnie z REMIT/MiFID II)
§8 Raportowanie: kwartalny raport zgodności REMIT
§9 Szkolenie: obowiązkowe dla osób z dostępem do danych handlowych
§10 Naruszenia: procedura eskalacji, konsekwencje, zgłoszenie do URE

PO POLSKU. Minimum 800 słów.''', signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/20_Polityka_barier_informacyjnych_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
