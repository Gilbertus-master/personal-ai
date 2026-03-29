# D18: Matryca ról i uprawnień RBAC

```bash
cd /home/sebastian/personal-ai && .venv/bin/python3 -c "
from app.analysis.legal_compliance import create_matter
from app.analysis.legal.document_generator import generate_document
from app.db.postgres import get_pg_connection

matter = create_matter(title='Matryca RBAC — Omnius', matter_type='documentation', area_code='INTERNAL_AUDIT', description='Matryca ról i uprawnień systemu Omnius: 7 ról, 5 klasyfikacji danych, 44 narzędzi MCP, governance rules.', priority='medium')
matter_id = matter['id']

doc = generate_document(matter_id=matter_id, doc_type='form', title='Matryca ról i uprawnień (RBAC) — System Omnius', template_hint='''Matryca RBAC w formacie tabelarycznym.

TABELA 1: Role i poziomy dostępu
| Rola | Poziom | Kto | Klasyfikacja danych | Opis |
|------|--------|-----|---------------------|------|
| gilbertus_admin | 99 | Konto systemowe | public, internal, confidential, ceo_only, personal | Pełny dostęp systemowy |
| operator | 70 | Michał Schulte | BRAK danych biznesowych | Zarządzanie infrastrukturą, taski |
| ceo | 60 | Krystian Juchacz (REF) / Sebastian Jabłoński (REH) | public, internal, confidential, ceo_only, personal | Pełny dostęp biznesowy |
| board | 50 | Edgar Mikołajek, Witold Pawłowski | public, internal, confidential, personal | Raporty i analizy zarządcze |
| director | 40 | TBD | public, internal, personal | Raporty operacyjne |
| manager | 30 | TBD | public, internal, personal | Dane zespołu |
| specialist | 20 | TBD | public, personal | Dane własne |

TABELA 2: Klasyfikacja danych
| Poziom | Opis | Przykłady | Kto ma dostęp |
|--------|------|-----------|---------------|
| public | Ogólnodostępne | Struktura organizacyjna | Wszyscy |
| internal | Wewnętrzne firmowe | Komunikacja Teams, email | specialist+ |
| confidential | Poufne | Warunki umów, finanse | board+ |
| ceo_only | Wyłącznie CEO | Strategie, negocjacje | ceo |
| personal | Dane osobiste pracownika | Dane HR, oceny | ceo (cudze), specialist (własne) |

TABELA 3: Matryca dostępu do modułów
| Moduł | specialist | manager | director | board | ceo | operator | admin |
|-------|-----------|---------|----------|-------|-----|----------|-------|
| ask (zapytania) | ✓ ogr. | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| briefy i raporty | ✗ | ogr. | ✓ | ✓ | ✓ | ✗ | ✓ |
| alerty | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| oceny pracowników | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| delegowanie | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| analiza komunikacji | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| compliance | ✗ | ✗ | ogr. | ✓ | ✓ | ✗ | ✓ |
| infrastruktura | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| cron management | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |

TABELA 4: Governance — operacje ZAKAZANE
| Operacja | Czy dozwolona | Kto mógłby zezwolić |
|----------|---------------|---------------------|
| delete_feature | ZABRONIONA | Nikt (governance lock) |
| remove_data_source | ZABRONIONA | Nikt |
| reduce_data_scope | ZABRONIONA | Nikt |
| delete_role | ZABRONIONA | Nikt |
| downgrade_role | ZABRONIONA | Nikt |
| disable_sync | ZABRONIONA | Nikt |
| modify_rbac | ZABRONIONA | gilbertus_admin only (system) |

PO POLSKU. Format tabelaryczny, gotowy do wydruku.''', signers=[{'name': 'Sebastian Jabłoński', 'role': 'Prezes Zarządu'}])
doc_id = doc.get('document_id')
if doc_id:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT content FROM compliance_documents WHERE id = %s', (doc_id,))
            row = cur.fetchone()
            if row and row[0]:
                for co, path in [('REH','/mnt/c/Users/jablo/Desktop/Omnius_REH'),('REF','/mnt/c/Users/jablo/Desktop/Omnius_REF')]:
                    c = row[0].replace('Respect Energy Holding S.A.', 'Respect Energy Fuels sp. z o.o.') if co=='REF' else row[0]
                    with open(f'{path}/18_Matryca_RBAC_{co}.md','w') as f: f.write(c)
                    print(f'Saved: {co}')
"
```
