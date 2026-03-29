# D16: Polityka bezpieczeństwa danych systemu Omnius

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Polityka bezpieczeństwa danych — Omnius', matter_type='policy_update', area_code='RODO', description='Polityka bezpieczeństwa Art. 32 RODO + Art. 15 AI Act: środki techniczne i organizacyjne.', priority='high', source_regulation='EU 2016/679 Art. 32, EU 2024/1689 Art. 15')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='policy', title='Polityka bezpieczeństwa danych systemu Omnius', template_hint='''Polityka bezpieczeństwa Art. 32 RODO + Art. 15 AI Act.

§1 Cel i zakres
§2 Środki TECHNICZNE:
  a) Szyfrowanie: TLS 1.3 in-transit, encryption at-rest (PostgreSQL), Qdrant API key auth
  b) Kontrola dostępu: RBAC 7 poziomów, klasyfikacja danych (5 poziomów: public→personal)
  c) Pseudonimizacja: dane w chunks bez bezpośrednich identyfikatorów (encje linkowane)
  d) Integralność: checksummy backupów, WAL replication ready
  e) Dostępność: auto-restore @reboot, backup 5x/day, 30-day rotation
  f) Odporność: Docker containers, health checks, auto-restart
  g) Sieć: CORS policy, security headers (X-Frame-Options, CSP, HSTS), localhost binding (127.0.0.1)
  h) Monitoring: non-regression co 10 min, QC daily, security scan weekly
  i) CI/CD security: gitleaks pre-commit, pip-audit weekly, container hardening (non-root)
  j) Logowanie: structured logging (structlog), API cost tracking, audit trail RBAC

§3 Środki ORGANIZACYJNE:
  a) Zasada least privilege: każdy użytkownik minimum niezbędnych uprawnień
  b) Governance: FORBIDDEN_ACTIONS (nie można usunąć feature, reduce data scope, modify RBAC)
  c) Operator zero-access: Michał Schulte ma dostęp do infra, ZERO do danych biznesowych
  d) Szkolenia: obowiązkowe przed dostępem
  e) Incydenty: procedura reagowania (D17)
  f) Przegląd uprawnień: kwartalny

§4 Testowanie skuteczności: security scan (pip-audit), code review automated, penetration test roczny
§5 Transfer międzynarodowy: SCC dla Anthropic/OpenAI, Hetzner EU-only
§6 Zarządzanie kluczami: API keys w .env, NIGDY w kodzie, rotacja kwartalna
§7 Backup i odtwarzanie: RPO 4h, RTO 30 min, procedura restore
§8 Przegląd polityki: co 6 miesięcy lub po incydencie

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
                    with open(f'{path}/16_Polityka_bezpieczenstwa_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
