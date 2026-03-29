# D09: Zgoda na nagrywanie i przetwarzanie rozmów (Plaud)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Dokumentacja nagrywania rozmów — Plaud + Omnius',
    matter_type='documentation',
    area_code='RODO',
    description='Komplet dokumentów: zgoda na nagrywanie (Art. 7 RODO), informacja o nagrywaniu, klauzula dla zewnętrznych, procedura zarządzania zgodami. Plaud Pin S → transkrypcja → Omnius.',
    priority='high',
    source_regulation='EU 2016/679 Art. 7, Kodeks Karny Art. 267'
)
matter_id = matter['id']

# Dokument A: Formularz zgody
doc_a = generate_document(
    matter_id=matter_id,
    doc_type='form',
    title='Formularz zgody na nagrywanie i przetwarzanie rozmów',
    template_hint='''Formularz zgody Art. 7 RODO na nagrywanie i przetwarzanie nagrań audio.

OSOBNE CHECKBOXY na:
☐ Wyrażam zgodę na nagrywanie spotkań z moim udziałem
☐ Wyrażam zgodę na transkrypcję nagrań przez system AI
☐ Wyrażam zgodę na przetwarzanie transkrypcji w systemie Omnius

Informacja o: celu (dokumentacja spotkań, generowanie notatek), okresie (audio 6 mies, transkrypcje 2 lata), odbiorcach (Whisper local, Anthropic SCC), prawach (cofnięcie zgody Art. 7(3), dostęp, usunięcie).

UWAGA: Zgoda musi być DOBROWOLNA — odmowa nie może skutkować negatywnymi konsekwencjami.
Dane: imię, nazwisko, stanowisko, data, podpis, podpis pracodawcy.

PO POLSKU. Gotowy do druku.''',
    signers=[{'name': 'Pracownik', 'role': 'Osoba wyrażająca zgodę'}]
)

# Dokument B: Informacja o nagrywaniu
doc_b = generate_document(
    matter_id=matter_id,
    doc_type='communication',
    title='Informacja o nagrywaniu spotkań',
    template_hint='''Informacja do wywieszenia w salach konferencyjnych i przekazania na początku spotkań.

TREŚĆ: W tym pomieszczeniu / Podczas tego spotkania mogą być prowadzone nagrania audio za pomocą urządzenia Plaud Pin S. Nagrania służą dokumentacji spotkań i generowaniu notatek. Transkrypcje przetwarzane w systemie AI Omnius. Retencja: audio 6 mies, transkrypcje 2 lata. Administrator: [spółka]. Prawo sprzeciwu: proszę poinformować organizatora spotkania.

Krótki format — tabliczka / plakat A4. PO POLSKU.''',
    signers=[]
)

# Dokument C: Klauzula dla zewnętrznych
doc_c = generate_document(
    matter_id=matter_id,
    doc_type='communication',
    title='Klauzula informacyjna o nagrywaniu — osoby zewnętrzne',
    template_hint='''Tekst do przekazania kontrahentom przed nagranym spotkaniem (email lub ustnie).

TREŚĆ: Informujemy, że spotkanie może być nagrywane w celu dokumentacji ustaleń. Nagranie będzie przetwarzane przez system AI w celu generowania notatek. Administrator: [spółka]. Okres przechowywania: audio 6 mies, notatki 2 lata. Przysługuje Pani/Panu prawo dostępu, sprostowania, usunięcia (Art. 15-17 RODO). Kontakt: [IOD email]. Jeśli nie wyraża Pan/Pani zgody, proszę o informację przed rozpoczęciem spotkania.

Zgodny z Art. 267 KK (nagrywanie za wiedzą). PO POLSKU.''',
    signers=[]
)

# Dokument D: Procedura zarządzania zgodami
doc_d = generate_document(
    matter_id=matter_id,
    doc_type='procedure',
    title='Procedura zarządzania zgodami na nagrywanie',
    template_hint='''Procedura: zbieranie, przechowywanie, cofanie zgód na nagrywanie.

§1 Cel: zarządzanie zgodami Art. 7 RODO
§2 Rejestr zgód: tabela (imię, data zgody, zakres, data cofnięcia)
§3 Zbieranie: przed pierwszym nagraniem, formularz papierowy lub elektroniczny
§4 Cofnięcie zgody: pisemne/email do IOD, skutek natychmiastowy, dane dotychczasowe: usunięcie na żądanie
§5 Dane po cofnięciu: nagrania audio usunięte w 14 dni, transkrypcje anonimizowane lub usunięte
§6 Odpowiedzialność: IOD (rejestr), organizator spotkania (informowanie), IT (usuwanie)
§7 Archiwizacja: zgody przechowywane 5 lat od cofnięcia

PO POLSKU.''',
    signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}]
)

# Zapisz wszystkie na pulpit
for doc_info, prefix in [(doc_a,'09a_Zgoda_formularz'),(doc_b,'09b_Informacja_nagrywanie'),(doc_c,'09c_Klauzula_zewnetrzni'),(doc_d,'09d_Procedura_zgod')]:
    doc_id = doc_info.get('document_id')
    if doc_id:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
                row = cur.fetchone()
                if row and row[0]:
                    for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                        c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                        with open(f'{path}/{prefix}_{co}.md','w') as f: f.write(c)
                        print(f'Saved: {prefix}_{co}')
"
```
