# D23: Klauzula poufności — aneks do istniejących umów

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Klauzula poufności AI — aneks do umów B2B i cywilnoprawnych',
    matter_type='documentation',
    area_code='CONTRACT',
    description='Klauzula/aneks do istniejących umów B2B, zlecenia, o dzieło — rozszerzający zobowiązanie poufności o dane z systemu AI Omnius. Dla osób które już mają umowy i nie trzeba podpisywać nowej NDA.',
    priority='medium',
    source_regulation='Kodeks Cywilny Art. 353(1), Art. 72(1), Ustawa o zwalczaniu nieuczciwej konkurencji Art. 11'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='policy',
    title='Klauzula poufności — aneks do umowy w związku z wdrożeniem systemu AI',
    template_hint='''Aneks / rider do ISTNIEJĄCYCH umów (B2B, zlecenie, powołanie, kontrakt menedżerski).
Do użycia gdy nie chcemy podpisywać osobnej NDA ale musimy rozszerzyć zakres poufności.

ANEKS NR [___] DO UMOWY [typ] Z DNIA [___]

zawarty pomiędzy:
[Spółka] a [Współpracownik/Zleceniobiorca/Członek Zarządu]

§1 W związku z wdrożeniem systemu AI „Omnius" przez Spółkę, Strony postanawiają rozszerzyć zakres zobowiązania do poufności określonego w §[X] Umowy o następujące postanowienia:

§2 Współpracownik/Zleceniobiorca potwierdza, że został poinformowany o wdrożeniu systemu AI przetwarzającego komunikację korporacyjną w celach organizacyjnych.

§3 Do Informacji Poufnych w rozumieniu Umowy zalicza się dodatkowo:
a) Wszelkie dane, raporty, analizy, rekomendacje generowane przez system AI Omnius
b) Dane osobowe pracowników i współpracowników przetwarzane w systemie
c) Informacje o architekturze, konfiguracji i parametrach systemu
d) Informacje o strategiach biznesowych wynikające z analiz AI

§4 Współpracownik/Zleceniobiorca zobowiązuje się do:
a) Zachowania w tajemnicy informacji uzyskanych z systemu AI
b) Niewykorzystywania informacji do celów innych niż wykonanie Umowy
c) Niezwłocznego zgłaszania incydentów naruszenia poufności
d) Przestrzegania zasad systemu AI określonych w Regulaminie korzystania z systemu Omnius

§5 Zobowiązanie do poufności w zakresie niniejszego aneksu obowiązuje przez okres 3 lat od dnia zakończenia Umowy.

§6 Za naruszenie zobowiązań z niniejszego aneksu Współpracownik/Zleceniobiorca zapłaci karę umowną w wysokości [50.000 PLN] za każde naruszenie, niezależnie od prawa Spółki do dochodzenia odszkodowania na zasadach ogólnych.

§7 Pozostałe postanowienia Umowy nie ulegają zmianie.
§8 Aneks wchodzi w życie z dniem podpisania.
§9 Aneks sporządzono w dwóch jednobrzmiących egzemplarzach.

Podpisy: [Spółka] + [Współpracownik]

Dołącz ZAŁĄCZNIK: Lista dokumentów do zapoznania (Klauzula informacyjna RODO, Regulamin Omnius, Polityka barier informacyjnych).

PO POLSKU. Krótki, konkretny, gotowy do podpisu. Max 2 strony A4.''',
    signers=[
        {'name': '[Przedstawiciel spółki]', 'role': 'Spółka'},
        {'name': '[Współpracownik]', 'role': 'Strona'}
    ]
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
                    with open(f'{path}/23_Klauzula_poufnosci_aneks_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
