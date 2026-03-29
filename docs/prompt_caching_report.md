# Prompt Caching Report — 2026-03-29

## Pliki zaktualizowane

| Plik | Przed | Po | Cache breakpoint |
|------|-------|----|------------------|
| `app/retrieval/orchestrator.py` | `system=` plain string | `system=[{..., cache_control}]` | Statyczny system prompt syntezy (1 blok) |
| `app/api/insights.py` | Brak system, instrukcje w user msg | System z cache_control + czysty user msg z danymi | Instrukcje executive summary (1 blok) |
| `app/api/decisions.py` | Brak system, instrukcje w user msg | System z cache_control + czysty user msg z danymi | Instrukcje analizy wzorców decyzji (1 blok) |
| `app/analysis/legal_compliance.py` (research) | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Instrukcje prawnika + struktura odpowiedzi (1 blok) |
| `app/analysis/legal_compliance.py` (report) | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Struktura raportu compliance (1 blok) |
| `app/analysis/legal_compliance.py` (planning) | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Format action_plan JSON (1 blok) |
| `app/analysis/legal/regulatory_scanner.py` | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Instrukcje klasyfikacji regulacyjnej (1 blok) |
| `app/analysis/legal/communication_planner.py` | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Format planu komunikacji JSON (1 blok) |
| `app/analysis/legal/risk_assessor.py` | Brak system, mieszany prompt | System z cache_control + dynamiczny user | Instrukcje eksperta ryzyk + format JSON (1 blok) |
| `app/analysis/legal/document_generator.py` | `system=` plain string | `system=[{static, cache_control}, {dynamic}]` | Statyczna rola prawnika (1 blok), dynamiczny kontekst sprawy (bez cache) |

## Pliki pominiete (dynamiczne prompty)

| Plik | Powod |
|------|-------|
| `app/analysis/llm_evaluator.py` | Kazdy eval case ma unikatowy prompt testowy. Brak statycznego system prompt — prompty SA testem (entity extraction, event extraction, JSON reliability, etc.). Cache nie przyniesie oszczednosci. |

## Szacowane oszczednosci

### Koszty wejsciowe (input tokens z cache read = 90% rabatu)

| Modul | ~Tokeny statyczne | Wywolan/dzien | Oszczednosc/dzien (USD) |
|-------|-------------------|---------------|------------------------|
| orchestrator (synteza) | ~80 | ~20 | ~$0.005 |
| insights summary | ~120 | ~5 | ~$0.002 |
| decisions patterns | ~120 | ~3 | ~$0.001 |
| legal_compliance (3 calls) | ~200-400 | ~10 | ~$0.010 |
| regulatory_scanner | ~180 | ~50 (scan co 6h) | ~$0.025 |
| communication_planner | ~200 | ~5 | ~$0.003 |
| risk_assessor | ~200 | ~5 | ~$0.003 |
| document_generator | ~50+dynamic | ~3 | ~$0.001 |
| **TOTAL** | | | **~$0.05/dzien** |

Glowna wartosc: **zmniejszenie latency** (cache read = natychmiastowy, bez re-processingu tokenow systemowych) + **konsystencja kosztow** przy skalowaniu wolumenu.

### Laczny status prompt caching w projekcie

| Kategoria | Pliki z cache | Pliki bez | Coverage |
|-----------|--------------|-----------|----------|
| Retrieval (hot path) | 5 | 0 | 100% |
| API endpoints | 2 | 0 | 100% |
| Analityka | 32+1 | 1 (llm_evaluator) | 97% |
| Legal | 5 | 0 | 100% |
| **TOTAL** | **45** | **1** | **98%** |

## Weryfikacja

- [x] Wszystkie importy OK (8/8 modulow)
- [x] Non-regression gate: OK (15 metrics checked)
- [x] API health: OK
- [x] Ruff: brak nowych bledow (E402 pre-existing w legal/*)
