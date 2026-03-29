# D17: Procedura reagowania na incydenty (breach notification)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Procedura reagowania na incydenty ochrony danych — Omnius', matter_type='documentation', area_code='RODO', description='Procedura breach notification Art. 33-34 RODO: wykrywanie, klasyfikacja, zgłoszenie do UODO 72h, powiadomienie osób, dokumentowanie.', priority='high', source_regulation='EU 2016/679 Art. 33, Art. 34')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='procedure', title='Procedura reagowania na incydenty naruszenia ochrony danych osobowych', template_hint='''Procedura breach notification Art. 33-34 RODO.

§1 Cel: szybkie wykrycie, klasyfikacja i zgłoszenie naruszeń ochrony danych
§2 Definicje: naruszenie (Art. 4(12) RODO), incydent bezpieczeństwa, organ nadzorczy (UODO)
§3 Wykrywanie incydentów:
  - Automatyczne: monitoring anomalii, alerty bezpieczeństwa, QC checks
  - Manualne: zgłoszenie pracownika, informacja od podmiotu przetwarzającego
  - Kanały zgłoszenia: email IOD, formularz, telefon
§4 Klasyfikacja (w ciągu 4h od wykrycia):
  - Poziom 1 (niski): brak ryzyka dla osób — dokumentacja wewnętrzna
  - Poziom 2 (średni): ryzyko dla osób — zgłoszenie do UODO (72h)
  - Poziom 3 (wysoki): wysokie ryzyko — zgłoszenie UODO + powiadomienie osób
§5 Zgłoszenie do UODO (Art. 33) — w ciągu 72h:
  - Formularz UODO online
  - Treść: charakter naruszenia, kategorie osób/danych, liczba, IOD kontakt, konsekwencje, środki podjęte
  - Jeśli nie w 72h: uzasadnienie opóźnienia
§6 Powiadomienie osób (Art. 34) — bez zbędnej zwłoki:
  - Kiedy: wysokie ryzyko naruszenia praw i wolności
  - Treść: opis naruszenia, IOD kontakt, konsekwencje, środki podjęte
  - Kanał: email, indywidualne pismo
  - Wyjątki: Art. 34(3) — środki techniczne uniemożliwiające odczyt, środki eliminujące ryzyko
§7 Działania naprawcze: isolation, containment, eradication, recovery
§8 Dokumentowanie (Art. 33(5)): rejestr incydentów, fakty, skutki, podjęte działania
§9 Analiza post-mortem: root cause, lessons learned (zapis w DB lessons_learned)
§10 Szkolenia: informowanie pracowników o procedurze, symulacje incydentów
§11 Role: IOD (koordynacja), IT (techniczne), Zarząd (decyzje), PR (komunikacja zewnętrzna)

Specyficzne scenariusze dla Omnius:
- Wyciek danych przez API AI (Anthropic/OpenAI): natychmiastowe zatrzymanie wywołań, audit logów
- Nieuprawniony dostęp do systemu: blokada konta, reset credentials, audit trail
- Błąd AI ujawniający dane osobowe: usunięcie z cache, korekta promptów

PO POLSKU. Minimum 1000 słów.''', signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}, {'name': 'IOD', 'role': 'Inspektor Ochrony Danych'}])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/17_Procedura_incydentow_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
