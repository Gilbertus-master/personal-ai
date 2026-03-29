# D06: Rejestr czynności przetwarzania (Art. 30 RODO)

## Zadanie
Wygeneruj Rejestr Czynności Przetwarzania. Użyj modułu compliance + uzupełnij ręcznie bo to formularz tabelaryczny.

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Rejestr czynności przetwarzania danych — system Omnius',
    matter_type='documentation',
    area_code='RODO',
    description='Rejestr czynności przetwarzania Art. 30(1) RODO. 18 operacji przetwarzania w systemie Omnius.',
    priority='high',
    source_regulation='EU 2016/679 Art. 30'
)
matter_id = matter['id']

doc = generate_document(
    matter_id=matter_id,
    doc_type='form',
    title='Rejestr czynności przetwarzania danych osobowych — System Omnius',
    template_hint='''Rejestr Art. 30(1) RODO w formacie tabelarycznym. Dla KAŻDEJ z 18 operacji:

| Lp | Nazwa czynności | Cel | Podstawa prawna | Kategorie osób | Kategorie danych | Odbiorcy | Transfer do państw trzecich | Termin usunięcia | Środki bezpieczeństwa |

18 OPERACJI:
1. Indeksowanie poczty email korporacyjnej — Art.6(1)(f) — pracownicy, kontrahenci — treść, nadawca, odbiorca — Anthropic(USA,SCC), Hetzner(DE) — 3 lata — szyfrowanie TLS, RBAC
2. Indeksowanie wiadomości Teams — Art.6(1)(f) — pracownicy — treść czatów, kanałów — j.w. — 3 lata
3. Indeksowanie kalendarza — Art.6(1)(f) — pracownicy — spotkania, uczestnicy — Hetzner — 2 lata
4. Przetwarzanie WhatsApp biznesowego — Art.6(1)(a) zgoda / Art.6(1)(f) — pracownicy — wiadomości — Hetzner — 1 rok
5. Transkrypcja nagrań audio (Plaud) — Art.6(1)(a) zgoda — uczestnicy spotkań — audio, transkrypcje — Whisper(local), Hetzner — audio 6 mies, transkrypcje 2 lata
6. Indeksowanie dokumentów — Art.6(1)(f) — pracownicy — umowy, prezentacje — Hetzner — zgodnie z IKD
7. Ekstrakcja encji (NER) — Art.6(1)(f) — osoby wymienione w komunikacji — imiona, firmy, projekty — Anthropic(SCC) — 3 lata
8. Ekstrakcja zdarzeń biznesowych — Art.6(1)(f) — osoby w zdarzeniach — typ zdarzenia, data, uczestnicy — Anthropic(SCC) — 3 lata
9. Generowanie embeddings wektorowych — Art.6(1)(f) — pochodna — fragmenty tekstu — OpenAI(USA,SCC) — wraz ze źródłem
10. Analiza efektywności komunikacji org. — Art.6(1)(f) — pracownicy — metryki komunikacji — Anthropic — 12 mies rolling
11. Śledzenie zobowiązań biznesowych — Art.6(1)(f) — osoby zobowiązane — treść, termin, status — Anthropic — 3 lata
12. Generowanie raportów zarządczych — Art.6(1)(f) — pracownicy — dane zagregowane — Anthropic — 12 mies
13. Przygotowanie do spotkań — Art.6(1)(f) — uczestnicy — historia komunikacji, kontekst — Anthropic — 3 mies
14. Generowanie alertów biznesowych — Art.6(1)(f) — pracownicy — zdarzenia krytyczne — WhatsApp(CEO) — 6 mies
15. Ocena efektywności organizacyjnej — Art.6(1)(f) — pracownicy — metryki pracy — Anthropic — czas zatrudnienia + 3 lata
16. Mapowanie sieci relacji — Art.6(1)(f) — pracownicy, kontrahenci — graf relacji — Hetzner — 12 mies
17. Archiwizacja i backup — Art.6(1)(c)(f) — wszyscy — pełny backup DB — Hetzner — 30 dni rotacja
18. Logowanie dostępu i audyt — Art.6(1)(c)(f) — użytkownicy systemu — IP, czas, akcja — Hetzner — 5 lat

Spółki: REH = Respect Energy Holding S.A., ul. Podskarbińska 2, 03-833 Warszawa. REF = Respect Energy Fuels sp. z o.o.
PO POLSKU. Format tabelaryczny gotowy do wydruku.''',
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
                    with open(f'{path}/06_Rejestr_czynnosci_przetwarzania_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```

Weryfikuj kompletność tabeli — 18 wierszy, każdy z WSZYSTKIMI kolumnami.
