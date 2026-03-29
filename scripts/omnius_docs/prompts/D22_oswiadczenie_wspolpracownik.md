# D22: Oświadczenie współpracownika (B2B/zlecenie) + klauzula informacyjna

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Dokumentacja współpracowników B2B — Omnius',
    matter_type='documentation',
    area_code='RODO',
    description='Oświadczenia i klauzule dla osób niebędących pracownikami: współpracownicy B2B, zleceniobiorcy, członkowie zarządu, rada nadzorcza. Art. 22(3) KP NIE dotyczy tych osób — potrzebna odrębna podstawa prawna.',
    priority='high',
    source_regulation='EU 2016/679 Art. 6(1)(f), Art. 13-14'
)
matter_id = matter['id']

# Dokument A: Oświadczenie współpracownika B2B
doc_a = generate_document(
    matter_id=matter_id,
    doc_type='form',
    title='Oświadczenie współpracownika o zapoznaniu się z zasadami systemu AI Omnius',
    template_hint='''Formularz dla WSPÓŁPRACOWNIKÓW (B2B, zlecenie, dzieło) — INNA podstawa prawna niż dla pracowników!

NAGŁÓWEK: Oświadczenie współpracownika / osoby współpracującej

RÓŻNICE vs D14 (pracownik):
- Podstawa prawna: Art. 6(1)(f) RODO (uzasadniony interes), NIE Art. 22(3) KP
- Nie ma obowiązku z regulaminu pracy (bo nie pracownik)
- Przetwarzanie na podstawie umowy współpracy + uzasadniony interes

Ja, niżej podpisany/a [imię nazwisko], współpracujący/a z [spółka] na podstawie [umowa B2B / zlecenie / powołanie], oświadczam że:

1. ☐ Zapoznałem/am się z Klauzulą informacyjną o przetwarzaniu danych osobowych w systemie Omnius
2. ☐ Zostałem/am poinformowany/a, że komunikacja prowadzona za pośrednictwem narzędzi korporacyjnych (email, Teams) może być przetwarzana przez system AI w celu wsparcia zarządzania organizacją
3. ☐ Zostałem/am poinformowany/a o przysługujących mi prawach (Art. 15-22 RODO)
4. ☐ Zostałem/am poinformowany/a o prawie do sprzeciwu wobec przetwarzania (Art. 21 RODO)
5. ☐ Zostałem/am poinformowany/a, że system AI NIE podejmuje autonomicznych decyzji
6. ☐ Zapoznałem/am się z Umową o zachowaniu poufności i zobowiązuję się do jej przestrzegania

Dane: imię, nazwisko, firma/NIP, rola, numer umowy
Data: [___]
Podpis: ________________

PO POLSKU. Format A4, gotowy do druku.''',
    signers=[]
)

# Dokument B: Klauzula informacyjna RODO dla współpracowników B2B
doc_b = generate_document(
    matter_id=matter_id,
    doc_type='communication',
    title='Klauzula informacyjna RODO — współpracownicy i osoby niebędące pracownikami',
    template_hint='''Klauzula informacyjna Art. 13/14 RODO dla osób NIEBĘDĄCYCH pracownikami:
- Współpracownicy B2B
- Zleceniobiorcy
- Członkowie zarządu (z powołania)
- Członkowie rady nadzorczej
- Konsultanci zewnętrzni

RÓŻNICE vs klauzula dla pracowników (D02):
1. PODSTAWA PRAWNA: Art. 6(1)(f) — prawnie uzasadniony interes administratora (organizacja pracy, bezpieczeństwo informacji, realizacja umowy), NIE Art. 22(3) KP
2. CEL: przetwarzanie komunikacji korporacyjnej prowadzonej za pośrednictwem narzędzi udostępnionych przez administratora
3. PRAWO SPRZECIWU: szczególne podkreślenie prawa z Art. 21 RODO — współpracownik może w każdej chwili zgłosić sprzeciw wobec przetwarzania na podstawie Art. 6(1)(f)
4. KONSEKWENCJE SPRZECIWU: administrator oceni czy istnieją ważne prawnie uzasadnione podstawy nadrzędne

Reszta analogicznie jak D02: administrator, cele, odbiorcy, transfer USA/SCC, retencja, prawa, automatyczne przetwarzanie.

PO POLSKU. Przystępny język.''',
    signers=[]
)

# Dokument C: Oświadczenie członka zarządu / rady nadzorczej
doc_c = generate_document(
    matter_id=matter_id,
    doc_type='form',
    title='Oświadczenie członka organu spółki o zapoznaniu się z systemem AI Omnius',
    template_hint='''Formularz dla CZŁONKÓW ZARZĄDU i RADY NADZORCZEJ.

Specyfika: osoby w organach spółki mogą nie być pracownikami (powołanie na podstawie KSH).
Jako osoby z najwyższym dostępem (rola CEO/board) mają szczególną odpowiedzialność za dane.

Ja, [imię nazwisko], pełniący/a funkcję [Członka Zarządu / Członka Rady Nadzorczej / Prezesa Zarządu] [spółki], powołany/a uchwałą [nr] z dnia [data], oświadczam że:

1. ☐ Zapoznałem/am się z dokumentacją systemu AI Omnius
2. ☐ Zapoznałem/am się z Klauzulą informacyjną RODO
3. ☐ Zapoznałem/am się z Polityką bezpieczeństwa danych
4. ☐ Zapoznałem/am się z Polityką barier informacyjnych (REMIT)
5. ☐ Podpisałem/am Umowę o zachowaniu poufności
6. ☐ Rozumiem, że jako osoba z dostępem do danych poufnych i informacji wewnętrznych ponoszę szczególną odpowiedzialność za ich ochronę
7. ☐ Zobowiązuję się do przestrzegania procedury nadzoru ludzkiego — weryfikacji rekomendacji AI przed podjęciem decyzji kadrowych/biznesowych
8. ☐ Zobowiązuję się do niezwłocznego raportowania incydentów naruszenia danych

Data: [___]
Podpis: ________________

PO POLSKU. Format formalny.''',
    signers=[]
)

# Zapisz
for doc_info, prefix in [(doc_a,'22a_Oswiadczenie_wspolpracownik'),(doc_b,'22b_Klauzula_RODO_B2B'),(doc_c,'22c_Oswiadczenie_czlonek_organu')]:
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
