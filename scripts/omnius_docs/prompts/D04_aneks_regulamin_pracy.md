# D04: Aneks do regulaminu pracy — wdrożenie AI i monitoringu

## Zadanie
Wygeneruj aneks do Regulaminu Pracy. Użyj modułu compliance.

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Aneks do Regulaminu Pracy — wdrożenie systemu AI Omnius',
    matter_type='policy_update',
    area_code='LABOR',
    description='Zmiana regulaminu pracy wprowadzająca postanowienia dot. systemu AI i monitoringu komunikacji. Art. 104(1) §1 KP, Art. 22(2) §6 KP, Art. 22(3) §3 KP, Art. 26(7) AI Act.',
    priority='critical'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='internal_regulation',
    title='Aneks nr [__] do Regulaminu Pracy — wdrożenie systemu sztucznej inteligencji',
    template_hint='''Aneks do Regulaminu Pracy na podstawie Art. 104(2) KP w zw. z Art. 22(2) §6 i Art. 22(3) §3 KP.

STRUKTURA:
Preambuła: Na podstawie Art. 104(2) KP, Pracodawca wprowadza następujące zmiany.

§1 — Nowy Rozdział: Wykorzystanie systemów sztucznej inteligencji
1. Pracodawca wdraża system AI „Omnius" wspierający zarządzanie organizacją pracy.
2. System AI jest narzędziem WSPOMAGAJĄCYM — nie podejmuje autonomicznych decyzji kadrowych.
3. Decyzje dot. pracowników podejmuje wyłącznie człowiek po weryfikacji.
4. Pracownik ma prawo do informacji o objęciu systemem AI (Art. 26(7) AI Act).
5. Pracownik ma prawo zakwestionować rekomendację systemu AI.
6. Zakres danych przetwarzanych: komunikacja korporacyjna, dokumenty, kalendarz.

§2 — Nowy Rozdział: Monitoring komunikacji elektronicznej
1. Wprowadzenie monitoringu na podstawie Art. 22(3) KP
2. Cel: organizacja pracy, wykorzystanie czasu pracy, właściwe użytkowanie narzędzi
3. Zakres: email korporacyjny, Microsoft Teams, kalendarz Microsoft 365
4. Szczegółowe zasady: odesłanie do Regulaminu monitoringu (dokument D03)

§3 — Obowiązki pracownika
1. Zapoznanie się z zasadami korzystania z systemu AI
2. Nieudostępnianie danych dostępowych
3. Zgłaszanie nieprawidłowości

§4 — Obowiązki Pracodawcy
1. Ochrona danych osobowych, regularne audyty, informowanie o zmianach, kontakt IOD

§5 — Wejście w życie
Aneks wchodzi po 2 tygodniach od podania do wiadomości (Art. 22(3) §3 KP).
Ogłoszenie: email do wszystkich pracowników + obwieszczenie na tablicy ogłoszeń.

PO POLSKU. Formalny język prawniczy.''',
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
                    with open(f'{path}/04_Aneks_regulamin_pracy_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {path}/04_{co}')
"
```

Weryfikuj i uzupełnij jeśli potrzeba.
