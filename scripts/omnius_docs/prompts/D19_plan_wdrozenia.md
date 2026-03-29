# D19: Plan wdrożenia Omnius — harmonogram i checklist

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Plan wdrożenia systemu Omnius — REH + REF', matter_type='documentation', area_code='INTERNAL_AUDIT', description='Harmonogram wdrożenia Omnius: fazy, checklist compliance, timeline, odpowiedzialności. Deadline: AI Act high-risk od 2 sierpnia 2026.', priority='medium')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='report', title='Plan wdrożenia systemu Omnius — harmonogram i checklist', template_hint='''Plan wdrożenia z harmonogramem, fazami i checklistą.

FAZA 0 — PRZYGOTOWANIE PRAWNE (kwiecień 2026):
☐ Zatwierdzenie DPIA (D01)
☐ Zatwierdzenie FRIA (D05)
☐ Podpisanie DPA z Anthropic, OpenAI, Hetzner (D10)
☐ Aktualizacja regulaminu pracy — aneks (D04)
☐ Ogłoszenie regulaminu monitoringu (D03) — start 2-tygodniowego okresu
☐ Powołanie / wyznaczenie IOD (rekomendacja)
☐ Rejestracja czynności przetwarzania (D06)

FAZA 1 — INFORMOWANIE PRACOWNIKÓW (maj 2026):
☐ Dystrybucja klauzuli informacyjnej (D02) — email do wszystkich pracowników
☐ Zbieranie oświadczeń pracowników (D14) — podpisy
☐ Zbieranie zgód na nagrywanie (D09) — formularze
☐ Szkolenie użytkowników (CEO, board) z systemu Omnius
☐ Szkolenie RODO/AI dla pracowników (awareness)
☐ Ogłoszenie regulaminu Omnius (D15)

FAZA 2 — DEPLOY TECHNICZNY (maj-czerwiec 2026):
☐ Deploy Omnius REF na infrastrukturze Azure REF
☐ Deploy Omnius REH na infrastrukturze REH
☐ Konfiguracja RBAC per spółka
☐ Test integracji: email sync, Teams sync, kalendarz
☐ Test security: penetration test, vulnerability scan
☐ Konfiguracja retencji danych (D07) — implementacja cron jobs
☐ Konfiguracja logowania i auditu

FAZA 3 — PILOT (czerwiec-lipiec 2026):
☐ Pilot REF: Krystian Juchacz (CEO), Edgar Mikołajek, Witold Pawłowski (board)
☐ Pilot REH: Sebastian Jabłoński (CEO)
☐ Zbieranie feedbacku, tuning
☐ Weryfikacja: czy rekomendacje AI są użyteczne i nieszkodliwe
☐ Przegląd DPIA po pilocie (aktualizacja jeśli potrzeba)

FAZA 4 — PEŁNE WDROŻENIE (lipiec 2026):
☐ Rozszerzenie na directors, managers (jeśli applicable)
☐ Rejestracja w EU AI Database (przed 2 sierpnia 2026!)
☐ Wewnętrzna ocena zgodności (conformity assessment)
☐ Finalna weryfikacja compliance checklist

FAZA 5 — MONITORING CIĄGŁY (od sierpnia 2026):
☐ Przegląd DPIA co 12 miesięcy
☐ Przegląd FRIA co 12 miesięcy
☐ Kwartalny przegląd ryzyk
☐ Roczny audit bezpieczeństwa
☐ Szkolenia odświeżające

CHECKLIST COMPLIANCE (musi być 100% przed Fazą 4):
☐ DPIA zatwierdzona
☐ FRIA zatwierdzona
☐ DPA podpisane (4x)
☐ Rejestr czynności kompletny
☐ Regulamin pracy zaktualizowany
☐ Regulamin monitoringu ogłoszony (2 tyg. przed)
☐ Klauzula informacyjna doręczona WSZYSTKIM
☐ Oświadczenia podpisane (100% pracowników)
☐ Zgody na nagrywanie zebrane
☐ Polityka retencji wdrożona technicznie
☐ Procedura praw podmiotów gotowa
☐ Procedura incydentów gotowa
☐ Human oversight udokumentowany
☐ System zarządzania ryzykiem aktywny
☐ Rejestracja EU AI Database

DEADLINE: AI Act high-risk = 2 sierpnia 2026 (4 miesiące)
PO POLSKU.''', signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/19_Plan_wdrozenia_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
