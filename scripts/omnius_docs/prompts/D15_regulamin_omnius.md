# D15: Regulamin korzystania z systemu Omnius

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Regulamin korzystania z systemu Omnius', matter_type='new_regulation', area_code='INTERNAL_AUDIT', description='Regulamin wewnętrzny określający zasady korzystania z systemu AI Omnius: role, uprawnienia, zakazy, odpowiedzialność, procedura dostępu.', priority='medium', source_regulation='Kodeks Pracy Art. 104, EU 2024/1689 Art. 13')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='internal_regulation', title='Regulamin korzystania z systemu Omnius', template_hint='''Regulamin wewnętrzny systemu AI Omnius.

§1 Postanowienia ogólne: cel, zakres, definicje
§2 Przeznaczenie systemu: wspomaganie zarządzania organizacją pracy, generowanie raportów, briefów, alertów. System NIE podejmuje decyzji.
§3 Role użytkowników (RBAC):
  - CEO (poziom 60): pełny dostęp do raportów, rekomendacji, danych (z wyjątkiem personal)
  - Board (50): dostęp do raportów internal, confidential
  - Director (40): internal, public
  - Manager (30): internal, public
  - Specialist (20): public
  - Operator (70): zarządzanie infrastrukturą, ZERO dostępu do danych biznesowych
  - gilbertus_admin (99): konto systemowe
§4 Dostęp: jak uzyskać (wniosek do IT/CEO), aktywacja konta, szkolenie wstępne
§5 Zasady korzystania:
  a) Rekomendacje AI służą WYŁĄCZNIE jako wsparcie decyzyjne
  b) Zabrania się podejmowania decyzji kadrowych wyłącznie na podstawie AI
  c) Zabrania się udostępniania dostępu osobom nieupoważnionym
  d) Zabrania się wykorzystywania systemu do celów osobistych
  e) Zabrania się prób manipulowania wynikami AI
§6 Obowiązki użytkownika: zgłaszanie błędów, ochrona danych, aktualizacja wiedzy
§7 Dane źródłowe: co system przetwarza, skąd, jakie ograniczenia
§8 Ograniczenia systemu: AI może się mylić, hallucynacje, bias, nie zastępuje ludzkiego osądu
§9 Odpowiedzialność: za decyzje podjęte na podstawie AI odpowiada CZŁOWIEK, nie system
§10 Postanowienia końcowe: wejście w życie, zmiany, interpretacja

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
                    with open(f'{path}/15_Regulamin_Omnius_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
