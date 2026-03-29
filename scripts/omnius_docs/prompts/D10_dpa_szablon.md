# D10: Umowa powierzenia przetwarzania danych (DPA)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='DPA — Umowy powierzenia przetwarzania danych (Anthropic, OpenAI, Hetzner)',
    matter_type='documentation',
    area_code='RODO',
    description='Szablon DPA Art. 28 RODO + załączniki per podmiot przetwarzający: Anthropic PBC (USA), OpenAI Inc (USA), Hetzner Online GmbH (DE), Microsoft (M365). Wymagane SCC dla transferów USA.',
    priority='high',
    source_regulation='EU 2016/679 Art. 28, Art. 46(2)(c) SCC'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='policy',
    title='Umowa powierzenia przetwarzania danych osobowych — szablon',
    template_hint='''Szablon DPA zgodny z Art. 28(3) RODO. MUSI zawierać ALL elementy Art. 28(3)(a-h).

STRUKTURA:
§1 PRZEDMIOT: zakres, charakter, cel przetwarzania, rodzaj danych, kategorie osób, czas
§2 OBOWIĄZKI PODMIOTU PRZETWARZAJĄCEGO:
  a) Przetwarzanie WYŁĄCZNIE na udokumentowane polecenie administratora
  b) Poufność osób upoważnionych (zobowiązanie pisemne lub ustawowe)
  c) Środki bezpieczeństwa Art. 32 (szyfrowanie, pseudonimizacja, integralność, dostępność, odporność, testowanie)
  d) Sub-processors: lista zatwierdzonych, procedura autoryzacji nowych (zgoda ogólna z prawem sprzeciwu 14 dni), kaskadowe zobowiązania
  e) Pomoc w realizacji praw Art. 15-22 (termin: bez zbędnej zwłoki, max 5 dni roboczych)
  f) Pomoc przy DPIA i konsultacjach z organem (Art. 35-36)
  g) Po zakończeniu: usunięcie lub zwrot WSZYSTKICH danych (wybór administratora), potwierdzenie pisemne
  h) Audyty i inspekcje: udostępnienie informacji, prawo audytu z 14-dniowym wyprzedzeniem

§3 SUB-PROCESSORS: lista, procedura, kaskada
§4 TRANSFER DO PAŃSTW TRZECICH: SCC moduły 2+3, TIA, dodatkowe środki (szyfrowanie in-transit i at-rest)
§5 BEZPIECZEŃSTWO Art. 32: środki techniczne i organizacyjne
§6 NARUSZENIE Art. 33: powiadomienie 24h, wymagane informacje, współpraca
§7 AUDYTY: prawo, procedura, koszty, raporty
§8 ODPOWIEDZIALNOŚĆ: odszkodowania, ograniczenia
§9 CZAS TRWANIA: powiązany z umową główną
§10 POSTANOWIENIA KOŃCOWE: prawo polskie, sąd Warszawa

ZAŁĄCZNIKI (po szablonie głównym):
ZAŁĄCZNIK A — Anthropic PBC: dane=treść komunikacji, cel=NLP/ekstrakcja, zero-retention API policy, SCC
ZAŁĄCZNIK B — OpenAI Inc: dane=fragmenty tekstu, cel=embeddings, zero-retention API, SCC
ZAŁĄCZNIK C — Microsoft: dane=email/Teams/kalendarz, cel=hosting M365, istniejąca DPA Enterprise Agreement
ZAŁĄCZNIK D — Hetzner: dane=pełna baza Omnius, cel=hosting, EU-only (DE/FI), DPA na stronie Hetzner

WAŻNE: Dla USA (Anthropic, OpenAI) wymagane:
- Standard Contractual Clauses (decyzja KE 2021/914)
- Transfer Impact Assessment: FISA 702 risk, środki: szyfrowanie, pseudonimizacja, zero-retention
- Dodatkowe klauzule: zobowiązanie do powiadomienia o żądaniu władz USA

PO POLSKU. Profesjonalny język prawniczy. Gotowe do podpisu.''',
    signers=[
        {'name': 'Sebastian Jabłoński', 'role': 'Administrator danych'},
        {'name': '[Podmiot przetwarzający]', 'role': 'Procesor'}
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
                    with open(f'{path}/10_DPA_Umowa_powierzenia_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
