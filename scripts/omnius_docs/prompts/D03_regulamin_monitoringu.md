# D03: Regulamin monitoringu komunikacji elektronicznej

## Zadanie
Wygeneruj Regulamin monitoringu poczty elektronicznej i komunikacji elektronicznej zgodny z Art. 22(3) KP. Użyj modułu compliance.

## Krok 1: Rejestracja i generacja
```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Regulamin monitoringu komunikacji elektronicznej — Omnius',
    matter_type='new_regulation',
    area_code='LABOR',
    description='Regulamin monitoringu email i innej komunikacji elektronicznej wymagany przez Art. 22(3) KP. System Omnius monitoruje email, Teams, kalendarz korporacyjny.',
    priority='critical',
    source_regulation='Kodeks Pracy Art. 22(2), 22(3)'
)
matter_id = matter['id']
print(f'Matter: {matter_id}')

doc = generate_document(
    matter_id=matter_id,
    doc_type='internal_regulation',
    title='Regulamin monitoringu poczty elektronicznej i komunikacji elektronicznej',
    template_hint='''KOMPLETNY regulamin wewnętrzny zgodny z Art. 22(3) Kodeksu Pracy.

STRUKTURA:
Rozdział 1: POSTANOWIENIA OGÓLNE — definicje (Pracodawca, Pracownik, Monitoring, System AI, Komunikacja elektroniczna, Narzędzia pracy), cel regulaminu, zakres (pracownicy, zleceniobiorcy, stażyści)

Rozdział 2: CEL I ZAKRES MONITORINGU — Art. 22(3) §1 KP: zapewnienie organizacji pracy umożliwiającej pełne wykorzystanie czasu pracy oraz właściwe użytkowanie narzędzi. Kanały: email korporacyjny (@respect-energy.com, @re-fuels.com), Microsoft Teams, kalendarz Microsoft 365. System Omnius = narzędzie automatyzujące analizę komunikacji.

Rozdział 3: SPOSÓB PROWADZENIA MONITORINGU — opis techniczny (bez szczegółów implementacyjnych), automatyczne przetwarzanie AI, jakie informacje generuje (raporty efektywności, alerty terminów, briefy), role z dostępem (CEO, board), logowanie dostępu

Rozdział 4: OCHRONA PRYWATNOŚCI — Art. 22(3) §2 KP: monitoring NIE narusza tajemnicy korespondencji. Procedura oznaczania wiadomości jako prywatne (tag [PRYWATNE]). Wiadomości prywatne nie są analizowane. Wyniki monitoringu NIE są jedyną podstawą oceny pracownika.

Rozdział 5: OKRES PRZECHOWYWANIA — dane z monitoringu: 12 miesięcy, potem automatyczne usunięcie. Wyjątki: postępowanie sądowe, kontrola organów.

Rozdział 6: PRAWA PRACOWNIKA — prawo do informacji, dostępu do danych, sprzeciwu, skargi do IOD/UODO/PIP. Formularz realizacji praw.

Rozdział 7: POSTANOWIENIA KOŃCOWE — wejście w życie 2 tygodnie od ogłoszenia (Art. 22(3) §3 KP), sposób ogłoszenia (email, intranet, obwieszczenie), zmiany regulaminu.

CEL MONITORINGU = TYLKO organizacja pracy. NIE pisz o: ocenie pracowników, analizie sentymentu, monitoringu wellbeing.
Minimum 1500 słów. PO POLSKU. Numeracja §1, §2 itd.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}]
)
doc_id = doc.get('document_id')
print(f'Doc: {doc_id}')

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
                    with open(f'{path}/03_Regulamin_monitoringu_{co}.md', 'w') as f:
                        f.write(content)
                    print(f'Saved: {path}/03_{co}')
"
```

## Krok 2: Weryfikacja
Przeczytaj wygenerowane pliki. Uzupełnij jeśli brakuje rozdziałów. Upewnij się że cel monitoringu jest ŚCIŚLE ograniczony do Art. 22(3) §1 KP.
