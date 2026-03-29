# D12: System zarządzania ryzykiem AI (Art. 9 AI Act)

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='System zarządzania ryzykiem AI — Omnius', matter_type='policy_update', area_code='INTERNAL_AUDIT', description='System zarządzania ryzykiem Art. 9 AI Act. Ciągła identyfikacja, analiza, ocena i mitygacja ryzyk systemu AI high-risk.', priority='high', source_regulation='EU 2024/1689 Art. 9')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='policy', title='System zarządzania ryzykiem systemu AI Omnius', template_hint='''Polityka zarządzania ryzykiem AI zgodna z Art. 9 AI Act.

§1 Cel: ustanowienie ciągłego systemu zarządzania ryzykiem AI
§2 Zakres: system Omnius, wszystkie moduły, cały cykl życia
§3 Identyfikacja ryzyk: kategoryzacja (techniczne, prawne, etyczne, operacyjne), metodyka, częstotliwość (kwartalna + ad hoc)
§4 Analiza ryzyk: matryca 5x5 (prawdopodobieństwo × wpływ), klasyfikacja (akceptowalne, tolerowane, nieakceptowalne)
§5 Środki mitygujące: per kategoria ryzyka, KPI skuteczności
§6 Monitoring ciągły: QC daily (06:00), non-regression co 10 min, code review co 30 min, security scan weekly
§7 Testowanie: extraction accuracy, API response time, data freshness, compliance checks
§8 Ryzyka zidentyfikowane: bias algorytmiczny, wyciek danych, nadmierny nadzór, niedostępność, błędne ekstrakcje, nieuprawniony dostęp, naruszenie RODO
§9 Eskalacja: progi eskalacji, kto decyduje, kill switch
§10 Dokumentowanie: rejestr ryzyk (compliance_risk_assessments DB), historia zmian, raporty kwartalne
§11 Przegląd: co 6 miesięcy lub przy istotnej zmianie systemu
§12 Role: Risk Owner (CEO), Risk Manager (IOD), Technical (IT)

PO POLSKU. Minimum 1000 słów.''', signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/12_System_zarzadzania_ryzykiem_AI_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
