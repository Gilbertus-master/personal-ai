# D21: Umowa o zachowaniu poufności (NDA) — dostęp do systemu Omnius

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='NDA — Umowa o zachowaniu poufności dla użytkowników Omnius',
    matter_type='documentation',
    area_code='CONTRACT',
    description='Umowa o zachowaniu poufności dla osób z dostępem do systemu Omnius: członkowie zarządu, operatorzy, konsultanci IT, współpracownicy B2B. Obejmuje dane z systemu AI, dane osobowe pracowników, dane handlowe, inside information.',
    priority='high',
    source_regulation='Kodeks Cywilny Art. 72(1), Ustawa o zwalczaniu nieuczciwej konkurencji Art. 11, REMIT Art. 3-4'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='policy',
    title='Umowa o zachowaniu poufności — System Omnius',
    template_hint='''Umowa NDA dla osób z dostępem do systemu AI Omnius. SZABLON do podpisania indywidualnie.

STRONY:
- Ujawniający: [Respect Energy Holding S.A. / Respect Energy Fuels sp. z o.o.]
- Otrzymujący: [imię nazwisko, stanowisko/rola, PESEL/NIP]

§1 DEFINICJE:
- Informacje Poufne: WSZYSTKIE informacje uzyskane z systemu Omnius lub w związku z dostępem do niego, w szczególności:
  a) Dane osobowe pracowników i współpracowników (imiona, stanowiska, oceny, komunikacja)
  b) Dane handlowe i transakcyjne (ceny, wolumeny, kontrahenci, warunki umów)
  c) Informacje wewnętrzne w rozumieniu REMIT (informacje cenotwórcze dot. rynku energii)
  d) Raporty, briefy, alerty i rekomendacje generowane przez system AI
  e) Architektura, konfiguracja i parametry systemu Omnius
  f) Strategie biznesowe, plany, prognozy
- System Omnius: korporacyjny system AI przetwarzający komunikację i dane
- Okres poufności: 3 lata od zakończenia dostępu (5 lat dla informacji REMIT)

§2 ZOBOWIĄZANIE DO POUFNOŚCI:
1. Otrzymujący zobowiązuje się do zachowania w tajemnicy WSZYSTKICH Informacji Poufnych
2. Otrzymujący nie ujawni Informacji Poufnych osobom trzecim bez pisemnej zgody Ujawniającego
3. Otrzymujący wykorzysta Informacje Poufne WYŁĄCZNIE w celu wykonywania obowiązków służbowych
4. Otrzymujący zastosuje co najmniej takie same środki ochrony jak dla własnych informacji poufnych, nie mniejsze niż rozsądne środki ochrony

§3 SZCZEGÓLNE ZOBOWIĄZANIA DOT. DANYCH OSOBOWYCH:
1. Otrzymujący NIE będzie kopiował, zapisywał, przesyłał danych osobowych poza system Omnius
2. Otrzymujący NIE będzie wykorzystywał danych osobowych do celów prywatnych
3. Otrzymujący NIE będzie ujawniał treści raportów AI osobom nieuprawnionym
4. Otrzymujący zobowiązuje się do niezwłocznego zgłaszania incydentów naruszenia poufności
5. Otrzymujący potwierdza, że został poinformowany o odpowiedzialności z Art. 107 Ustawy o ochronie danych osobowych (grzywna, ograniczenie/pozbawienie wolności do lat 2)

§4 SZCZEGÓLNE ZOBOWIĄZANIA DOT. INFORMACJI RYNKOWYCH (REMIT):
1. Otrzymujący NIE wykorzysta informacji z systemu Omnius do transakcji na rynku energii
2. Otrzymujący NIE ujawni informacji cenotwórczych osobom nieupoważnionym
3. Naruszenie stanowi potencjalne naruszenie Art. 3 REMIT (insider trading)

§5 WYJĄTKI OD POUFNOŚCI:
a) Informacje publicznie dostępne (nie z winy Otrzymującego)
b) Informacje uzyskane legalnie z innego źródła
c) Informacje ujawnione na podstawie nakazu sądowego lub organu (po powiadomieniu Ujawniającego)
d) Informacje opracowane niezależnie (udowodnione)

§6 OKRES OBOWIĄZYWANIA:
- Umowa wchodzi w życie z dniem podpisania
- Obowiązek poufności: 3 lata od dnia ustania dostępu do systemu (5 lat dla REMIT)
- Cofnięcie dostępu: na żądanie Ujawniającego, natychmiastowo

§7 ZWROT / ZNISZCZENIE:
Po zakończeniu dostępu Otrzymujący zwróci lub zniszczy WSZELKIE kopie Informacji Poufnych w ciągu 14 dni i potwierdzi to na piśmie.

§8 KARA UMOWNA:
Za KAŻDE naruszenie: [50.000 PLN / 100.000 PLN] kary umownej. Nie wyłącza dochodzenia odszkodowania przewyższającego karę na zasadach ogólnych (Art. 484 §1 KC).

§9 ODPOWIEDZIALNOŚĆ:
- Cywilna: odszkodowanie z Art. 471 KC, kara umowna §8
- Karna: Art. 267 KK (naruszenie tajemnicy), Art. 107 UODO (dane osobowe), Art. 11 UZNK (tajemnica przedsiębiorstwa)
- Regulacyjna: REMIT (kary URE/ACER)

§10 POSTANOWIENIA KOŃCOWE:
- Prawo polskie
- Sąd właściwy: Warszawa
- Zmiany: forma pisemna pod rygorem nieważności
- Podpisy obu stron

WARIANTY (3 wersje w jednym dokumencie):
A) Dla członków zarządu / rady nadzorczej
B) Dla współpracowników B2B / konsultantów
C) Dla operatorów IT z dostępem do infrastruktury

PO POLSKU. Profesjonalny język prawniczy. Gotowe do podpisu.''',
    signers=[
        {'name': '[Przedstawiciel spółki]', 'role': 'Ujawniający'},
        {'name': '[Osoba zobowiązana]', 'role': 'Otrzymujący'}
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
                    with open(f'{path}/21_NDA_Umowa_poufnosci_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
