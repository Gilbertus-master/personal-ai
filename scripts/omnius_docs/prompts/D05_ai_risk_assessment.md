# D05: Ocena ryzyka AI — Fundamental Rights Impact Assessment

## Zadanie
Wygeneruj FRIA (Art. 27 AI Act) dla systemu Omnius. Użyj modułu compliance do rejestracji ryzyk.

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.risk_assessor import create_risk_assessment
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(
    title='Ocena wpływu AI na prawa podstawowe (FRIA) — Omnius',
    matter_type='risk_assessment',
    area_code='RODO',
    description='Fundamental Rights Impact Assessment Art. 27 AI Act. Omnius = high-risk AI (Annex III pkt 4). Ocena wpływu na: godność (Art.1), prywatność (Art.7), dane (Art.8), wolność wypowiedzi (Art.11), niedyskryminację (Art.21), warunki pracy (Art.31).',
    priority='critical',
    source_regulation='EU 2024/1689 Art. 27 (AI Act)'
)
matter_id = matter['id']

# Ryzyka praw podstawowych
fria_risks = [
    ('Naruszenie godności ludzkiej (Art. 1 KPP)', 'Profilowanie i redukcja pracownika do metryki AI', 'medium', 'major'),
    ('Naruszenie prywatności (Art. 7 KPP)', 'Masowe przetwarzanie komunikacji prywatnej i zawodowej', 'high', 'major'),
    ('Naruszenie ochrony danych (Art. 8 KPP)', 'Przetwarzanie danych przez AI bez pełnej kontroli', 'medium', 'moderate'),
    ('Ograniczenie wolności wypowiedzi (Art. 11 KPP)', 'Chilling effect — autocenzura z powodu monitoringu AI', 'high', 'major'),
    ('Naruszenie wolności zgromadzania (Art. 12 KPP)', 'Monitoring rozmów grupowych w Teams', 'low', 'moderate'),
    ('Wpływ na wolność wyboru zawodu (Art. 15 KPP)', 'Rekomendacje AI wpływające na ścieżkę kariery', 'medium', 'major'),
    ('Naruszenie zasady niedyskryminacji (Art. 21 KPP)', 'Bias algorytmiczny w ocenach i delegowaniu', 'medium', 'catastrophic'),
    ('Naruszenie prawa do warunków pracy (Art. 31 KPP)', 'Stres i presja wynikająca z ciągłego nadzoru AI', 'high', 'major'),
    ('Naruszenie prawa do środka odwoławczego (Art. 47 KPP)', 'Brak formalnej procedury kwestionowania decyzji AI', 'medium', 'major'),
    ('Naruszenie zakazu rozpoznawania emocji (Art. 5(1)(f) AI Act)', 'Sentiment/wellbeing = de facto emotion recognition', 'medium', 'catastrophic'),
]
for title, desc, l, i in fria_risks:
    create_risk_assessment(area_code='RODO', matter_id=matter_id, risk_title=title, risk_description=desc, likelihood=l, impact=i)
    print(f'Risk: {title}')

doc = generate_document(
    matter_id=matter_id,
    doc_type='risk_assessment',
    title='Ocena wpływu systemu AI Omnius na prawa podstawowe (FRIA)',
    template_hint='''FRIA zgodna z Art. 27 AI Act (EU 2024/1689). ODRĘBNA od DPIA.

STRUKTURA:
1. Identyfikacja systemu AI: Omnius, High-Risk (Annex III, pkt 4(a)(b)), deployer: REH/REF
2. Opis procesów: email ingestion, entity extraction, event extraction, communication analysis, briefing, meeting prep, delegation recommendations, commitment tracking
3. Kategorie osób dotkniętych: pracownicy (120+), kontrahenci, osoby trzecie
4. Ocena wpływu na KAŻDE prawo z Karty Praw Podstawowych UE:
   Art.1 Godność, Art.7 Prywatność, Art.8 Dane, Art.11 Wolność wypowiedzi, Art.12 Zgromadzenia, Art.15 Zawód, Art.20 Równość, Art.21 Niedyskryminacja, Art.31 Warunki pracy, Art.47 Środek odwoławczy
   Dla KAŻDEGO: opis wpływu, ocena (brak/niski/średni/wysoki/krytyczny), środki zaradcze
5. Środki ograniczające: RBAC, human oversight, audit logging, prawo sprzeciwu, procedura odwoławcza
6. Plan monitorowania: metryki, częstotliwość przeglądu
7. Konsultacje z pracownikami: plan konsultacji z przedstawicielami
8. Wnioski: warunki wdrożenia, zalecenia modyfikacji

DEADLINE: AI Act high-risk provisions obowiązują od 2 sierpnia 2026.
Minimum 1500 słów. PO POLSKU.''',
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
                    with open(f'{path}/05_Ocena_ryzyka_AI_FRIA_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {path}/05_{co}')
"
```

Weryfikuj kompletność i uzupełnij brakujące sekcje.
