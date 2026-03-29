# Relationship Module — Research

**Data: 2026-03-30**

## Istniejące tabele w DB

### Biznesowe tabele `relationships*` (NIE używamy)
Tabele `relationships`, `relationship_roles_history`, `relationship_timeline`, `relationship_open_loops` służą do śledzenia relacji biznesowych (person_id → contacts). Zawierają pola jak `organization`, `person_role`, `can_contact_directly` — zupełnie inny kontekst.

**Decyzja:** Tworzymy osobne tabele z prefiksem `rel_` — zero kolizji z biznesowymi.

### Tabela `contacts`
Kolumny: id, canonical_name, whatsapp_jid, whatsapp_phone, whatsapp_push_name, email_address, teams_upn, teams_display_name, notes, created_at, updated_at.

**Decyzja:** `rel_partners` NIE linkuje do `contacts` — pełna izolacja danych prywatnych.

## Istniejące moduły analysis/
- 50+ modułów w `app/analysis/`
- Subpackages: `legal/`, `autofixer/`, `roi/`, `perf_improver/`
- Pattern: każdy subpackage ma `__init__.py`, moduły używają `get_pg_connection()`, structlog

## Migracje
- `scripts/migrations/` — numerowane (015_autofixer_v2.sql)
- `app/db/migrations/` — osobny katalog (001-019)
- Używamy `scripts/migrations/017_relationship_private.sql`

## Wnioski
1. Prefix `rel_` bezpieczny — brak kolizji
2. Pełna izolacja od biznesowych tabel relationships
3. Pattern subpackage (jak `legal/`) sprawdzony — kopiujemy
4. Brak structlog dla wrażliwych treści — tylko metryki
