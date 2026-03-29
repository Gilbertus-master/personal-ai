# D13: Procedura nadzoru ludzkiego nad AI (Art. 14 AI Act)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Procedura nadzoru ludzkiego nad AI — Omnius', matter_type='documentation', area_code='LABOR', description='Human oversight Art. 14 AI Act. Procedura weryfikacji rekomendacji AI, interwencji, zatrzymania systemu.', priority='high', source_regulation='EU 2024/1689 Art. 14')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='procedure', title='Procedura nadzoru ludzkiego nad systemem AI Omnius', template_hint='''Procedura human oversight zgodna z Art. 14 AI Act.

§1 Cel: zapewnienie skutecznego nadzoru człowieka nad systemem AI
§2 Zasada naczelna: System AI jest narzędziem WSPOMAGAJĄCYM. ŻADNA decyzja kadrowa, personalna, biznesowa nie jest podejmowana autonomicznie przez AI.
§3 Osoby nadzorujące: CEO (pełny dostęp), Board (dostęp do raportów), IOD (nadzór RODO)
§4 Kompetencje osób nadzorujących: szkolenie z obsługi systemu, rozumienie ograniczeń AI, rozumienie ryzyk
§5 Procedura weryfikacji rekomendacji AI:
  a) Oceny pracownicze AI: ZAWSZE weryfikowane przez CEO przed podjęciem jakichkolwiek działań
  b) Delegowanie zadań: rekomendacja AI → przegląd CEO → decyzja ludzka
  c) Alerty i briefy: informacyjne, nie decyzyjne
  d) Zobowiązania: trackowane przez AI, weryfikowane przez człowieka przed eskalacją
§6 Prawo interwencji:
  a) CEO może wyłączyć DOWOLNY moduł systemu (kill switch)
  b) CEO może nadpisać KAŻDĄ rekomendację AI
  c) Pracownik ma prawo zakwestionować rekomendację AI dotyczącą jego osoby
§7 Procedura zatrzymania systemu:
  a) Natychmiastowe: wyłączenie cronów, zatrzymanie API
  b) Częściowe: wyłączenie konkretnych modułów (sentiment, evaluation)
  c) Kto może: CEO, operator (Michał Schulte)
§8 Logowanie nadzoru: każda weryfikacja/nadpisanie rekomendacji AI logowana
§9 Raportowanie: miesięczny raport z nadzoru (ile rekomendacji zaakceptowanych/odrzuconych)
§10 Szkolenie: obowiązkowe przed uzyskaniem dostępu do systemu

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
                    with open(f'{path}/13_Procedura_nadzoru_ludzkiego_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
