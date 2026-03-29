# D14: Oświadczenie pracownika o zapoznaniu się z systemem AI

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Oświadczenie pracownika — zapoznanie z systemem AI Omnius', matter_type='documentation', area_code='LABOR', description='Formularz oświadczenia pracownika o zapoznaniu się z: regulaminem monitoringu, klauzulą informacyjną RODO, regulaminem AI. Art. 22(3) §5 KP, Art. 26(7) AI Act.', priority='high', source_regulation='Kodeks Pracy Art. 22(3) §5, EU 2024/1689 Art. 26(7)')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='form', title='Oświadczenie pracownika o zapoznaniu się z zasadami systemu AI Omnius', template_hint='''Formularz oświadczenia do podpisu przez KAŻDEGO pracownika.

NAGŁÓWEK: [Logo spółki], Oświadczenie pracownika

TREŚĆ:
Ja, niżej podpisany/a [imię i nazwisko], zatrudniony/a na stanowisku [stanowisko] w [nazwa spółki], oświadczam że:

1. ☐ Zapoznałem/am się z Regulaminem monitoringu komunikacji elektronicznej z dnia [___]
2. ☐ Zapoznałem/am się z Klauzulą informacyjną o przetwarzaniu danych osobowych w systemie Omnius
3. ☐ Zapoznałem/am się z Aneksem do Regulaminu Pracy dot. systemu AI
4. ☐ Zapoznałem/am się z Regulaminem korzystania z systemu Omnius
5. ☐ Zostałem/am poinformowany/a o przysługujących mi prawach wynikających z RODO (Art. 15-22)
6. ☐ Zostałem/am poinformowany/a o prawie do zakwestionowania rekomendacji systemu AI
7. ☐ Zostałem/am poinformowany/a o sposobie kontaktu z IOD

Jednocześnie potwierdzam, że:
- Rozumiem cel i zakres monitoringu komunikacji elektronicznej
- Zostałem/am poinformowany/a, że system AI NIE podejmuje autonomicznych decyzji kadrowych
- Wiem, jak realizować swoje prawa jako podmiot danych

Dane pracownika: imię, nazwisko, stanowisko, dział, numer pracowniczy
Data: [___]
Podpis pracownika: ________________
Podpis pracodawcy/HR: ________________

UWAGA: Art. 22(3) §5 KP — nowy pracownik musi otrzymać informację o monitoringu PRZED rozpoczęciem pracy.

PO POLSKU. Format A4, gotowy do druku.''', signers=[])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/14_Oswiadczenie_pracownika_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
