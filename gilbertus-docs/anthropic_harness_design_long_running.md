# Harness Design for Long-Running Application Development
Source: https://www.anthropic.com/engineering/harness-design-long-running-apps
Date: 2026-03-24
Author: Prithvi Rajasekaran (Anthropic Labs)
Indexed by Gilbertus: 2026-03-27

## Kluczowe insighty (dla Omniusa i Gilbertusa)

### 1. Context Anxiety
Modele wykazują "context anxiety" — gdy zbliżają się do limitu kontekstu, zaczynają przedwcześnie kończyć pracę i raportować sukces, nawet jeśli zadanie nie jest ukończone. Claude Sonnet 4.5 wykazywał ten problem silnie. Rozwiązanie: **context resets** (nie compaction) — świeży agent z artifact handoff.

### 2. Context Reset vs Compaction
- **Compaction** = skrócenie historii in-place. Zachowuje ciągłość, ale nie eliminuje context anxiety.
- **Context Reset** = nowy agent ze structured handoff. Daje clean slate. Używać gdy model wykazuje context anxiety.
- Opus 4.5 wymagał resetów. Opus 4.6 nie — może działać w jednej ciągłej sesji z compaction.

### 3. Self-Evaluation Problem
Agenci oceniający własną pracę są zbyt pobłażliwi — wychwalają nawet mediocre output. Rozwiązanie: **oddzielny agent-ewaluator** (GAN-inspired). Ewaluator jest łatwiejszy do "skalibrowania na surowość" niż generator do samokrytyki.

### 4. Architektura 3-agentowa (Planner → Generator → Evaluator)
- **Planner**: rozszerza krótki prompt w pełny product spec. Nie specyfikuje implementacji — tylko deliverables.
- **Generator**: buduje w sprintach (lub ciągłe przy Opus 4.6), samoocena po każdym sprincie.
- **Evaluator**: QA przez Playwright MCP, testuje live aplikację jak użytkownik, granular criteria.

### 5. Sprint Contracts
Przed każdym sprintem generator i ewaluator negocjują "sprint contract" — co dokładnie ma być zbudowane i jak będzie testowane. Mostek między high-level spec a testowalną implementacją.

### 6. Zasada minimalizacji harnessu
"Every component in a harness encodes an assumption about what the model can't do on its own." Przy nowym modelu: usuwaj komponenty jeden po jednym i sprawdzaj co jest load-bearing. Nie zakładaj że stary harness jest nadal potrzebny.

### 7. Komunikacja przez pliki
Agenci komunikują się przez pliki (jeden pisze, drugi czyta). Prosta, niezawodna metoda handoff między sesjami.

### 8. Koszty i czas
- Solo agent: 20 min, $9
- Full harness (Opus 4.5): 6h, $200
- Uproszczony harness (Opus 4.6): ~4h, $124
Jakość output nieproporcjonalnie wyższa przy harness.

## Implikacje dla Omniusa

1. Zbudować oddzielny ewaluator-agent dla krytycznych zadań (np. weryfikacja decyzji, cashflow alerts)
2. Context resets dla długich zadań (>30 min) — nie compaction
3. Pliki jako transport między agentami — nie shared memory
4. Przy każdej aktualizacji modelu: review czy wszystkie komponenty harnessa są nadal potrzebne
5. Sprint contracts = equivalent "task contracts" dla Omnius tasks (co ma być zrobione + jak zweryfikowane)
6. Baza danych jako source of truth — nigdy self-report agenta

## Pełna treść artykułu

Harness design is key to performance at the frontier of agentic coding. Here's how we pushed Claude further in frontend design and long-running autonomous software engineering.

[...pełna treść dostępna pod URL źródłowym]
