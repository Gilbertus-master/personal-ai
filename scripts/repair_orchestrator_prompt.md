# Repair Process Orchestrator — Improvement Plan

## Context

You are improving the 3-layer automated repair system for the Gilbertus project.
The system has **1,406 findings** total, **85% resolved**, but **208 open findings are stuck**.

## Current Architecture

### Layer 1: Webapp AutoFix (`scripts/webapp_autofix.sh`)
- **Cron:** `*/2 * * * *` (every 2 min, 24/7)
- **Purpose:** Monitor Next.js dev server health, TypeScript errors, HTTP 500s, user-reported errors
- **Fix method:** `claude --print` with 120s timeout
- **State:** `logs/webapp_autofix_state.json`

### Layer 2: Code Fix Parallel (`scripts/code_fix_parallel.sh`)
- **Cron:** `*/10 * * * *` (every 10 min)
- **Purpose:** Fix code review findings from DB (tier 1 = ruff/regex, tier 2 = claude -p)
- **Key files:**
  - `app/analysis/code_fixer.py` — orchestrator
  - `app/analysis/autofixer/cluster_manager.py` — groups findings, assigns tiers
  - `app/analysis/autofixer/tier1_executor.py` — deterministic fixes (ruff, regex)
  - `app/analysis/autofixer/tier2_executor.py` — LLM fixes (claude -p)
  - `app/analysis/autofixer/context_gatherer.py` — enriches context
  - `app/analysis/autofixer/prompt_builder.py` — builds prompts
- **DB table:** `code_review_findings`

### Layer 3: Deep Fix (`scripts/deep_fix.sh`)
- **Cron:** `0 */2 * * *` (every 2h)
- **Purpose:** Fix findings that tier 2 gave up on (manual_review=TRUE)
- **Key file:** `app/analysis/autofixer/tier3_deep_fixer.py`
- **Budget:** $2 per bug, max 2 per run

## Diagnosed Problems

### PROBLEM 1: Verification blocks valid fixes (CRITICAL)
**File:** `app/analysis/autofixer/tier2_executor.py`, function `_verify_fix()` (line 104)

**Current logic:**
```python
ruff = subprocess.run([".venv/bin/ruff", "check", fp], ...)
errors = [ln for ln in ruff.stdout.splitlines()
          if ln.strip() and not ln.startswith("Found") and "E402" not in ln]
if len(errors) > 5:
    return False, f"ruff: {len(errors)} errors in {fp}"
```

**Bug:** It counts ALL ruff errors in the file (pre-existing + new). Files like `app/api/main.py` have 122 pre-existing errors, so ANY fix to those files always fails verification.

**Fix:** Compare ruff errors BEFORE and AFTER the fix. Only fail if the fix INCREASED errors.

**Implementation:**
```python
def _verify_fix(file_paths: list[str]) -> tuple[bool, str]:
    """Verify fix didn't introduce new errors."""
    # 1. Check git diff — ensure something changed
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat"], capture_output=True, text=True,
            timeout=10, cwd=str(PROJECT_DIR),
        )
        if not diff.stdout.strip():
            return False, "no changes detected"
    except Exception as e:
        return False, f"git diff failed: {e}"

    # 2. For each modified Python file, compare ruff errors before vs after
    for fp in file_paths:
        if not fp.endswith(".py"):
            continue

        # Get CURRENT error count (with fix applied)
        after_errors = _count_ruff_errors(fp)

        # Get BASELINE error count (before fix)
        try:
            subprocess.run(
                ["git", "stash", "--quiet"],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
            before_errors = _count_ruff_errors(fp)
            subprocess.run(
                ["git", "stash", "pop", "--quiet"],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
        except Exception as e:
            # If stash fails, try to recover
            subprocess.run(["git", "stash", "pop", "--quiet"],
                          capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR))
            return False, f"baseline check failed: {e}"

        new_errors = after_errors - before_errors
        if new_errors > 0:
            return False, f"ruff: fix introduced {new_errors} new errors in {fp} ({before_errors}→{after_errors})"

    return True, diff.stdout.strip()


def _count_ruff_errors(fp: str) -> int:
    """Count ruff errors in a file, excluding E402 (import order)."""
    try:
        ruff = subprocess.run(
            [".venv/bin/ruff", "check", fp],
            capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR),
        )
        errors = [ln for ln in ruff.stdout.splitlines()
                  if ln.strip() and not ln.startswith("Found") and "E402" not in ln]
        return len(errors)
    except Exception:
        return 0
```

### PROBLEM 2: Hotspot files block entire pipeline
**Stats:** Top 15 files have 100+ open findings. These files have high ruff baselines:
- `app/analysis/app_inventory.py` — 12 open, 75 ruff errors
- `app/analysis/tech_radar.py` — 9 open, 66 ruff errors
- `app/api/main.py` — 9 open, 122 ruff errors
- `app/analysis/strategic_goals.py` — 9 open, 66 ruff errors

**Fix:** Add a "file sanitizer" pre-pass that runs `ruff check --fix` on hotspot files BEFORE attempting tier 2 fixes. This reduces the baseline and prevents the fix-verification loop.

**Implementation:** Add to `code_fixer.py`:
```python
def sanitize_hotspot_files():
    """Run ruff --fix on files with most open findings to reduce baseline errors."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT file_path, COUNT(*) as cnt
                FROM code_review_findings
                WHERE NOT resolved AND fix_attempt_count >= 2
                GROUP BY file_path
                HAVING COUNT(*) >= 5
                ORDER BY cnt DESC LIMIT 10
            """)
            hotspots = cur.fetchall()

    for file_path, count in hotspots:
        full_path = PROJECT_DIR / file_path
        if not full_path.exists():
            continue

        # Run ruff --fix (safe auto-fixes only)
        result = subprocess.run(
            [".venv/bin/ruff", "check", "--fix", str(full_path)],
            capture_output=True, text=True, timeout=30, cwd=str(PROJECT_DIR),
        )

        # Check if anything changed
        diff = subprocess.run(
            ["git", "diff", "--stat", str(full_path)],
            capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
        )
        if diff.stdout.strip():
            log.info("hotspot_sanitized", file=file_path, findings=count)
            # Commit the cleanup
            subprocess.run(
                ["git", "add", str(full_path)],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
            subprocess.run(
                ["git", "commit", "-m", f"fix(autofixer): ruff cleanup for {file_path}"],
                capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
            )
```

### PROBLEM 3: Tier 3 underutilized — promotion threshold too high
**Stats:** 208 open findings, only 1 reached tier 3.
- `fix_attempt_count >= 3` promotes to `manual_review = TRUE`
- Then tier 3 picks from `manual_review = TRUE AND tier3_attempted = FALSE`
- But most findings have `fix_attempt_count = 2` (tier 2 does max 2 attempts per run)
- The counter only increments once per CLUSTER run, not per individual attempt

**Fix:** Lower promotion threshold from 3 to 2. Also reset `fix_attempted_at` cooldown for manual_review items so tier 3 can pick them up faster.

**In `tier3_deep_fixer.py`:**
```python
MIN_ATTEMPTS_FOR_PROMOTION = 2  # was 3
```

### PROBLEM 4: Webapp autofix wastes cycles on dead server
**Logs show:** Dev server dies repeatedly, autofix restarts it every 2 min, then skips the actual check cycle.

**Fix:**
1. Separate server health monitoring from code fixing
2. Add a "consecutive_failures" counter — after 5 failures, increase check interval to 10 min
3. After successful restart, wait for warmup before checking routes

### PROBLEM 5: No feedback loop between layers
Currently the 3 layers operate independently. No layer knows what the others are doing.

**Fix:** Add a shared status table `repair_status` that tracks:
- Which files are currently being worked on (lock mechanism)
- Last successful fix per file (to avoid re-reviewing freshly fixed code)
- Escalation path: webapp_autofix → code_review → tier1 → tier2 → tier3

### PROBLEM 6: Improvement category almost never fixed (17.6%)
**Stats:** 68 findings, 12 resolved, 56 open.

**Root cause:** "Improvement" findings are suggestions, not bugs. Tier 2 LLM tries to fix them but often fails because they require broader refactoring.

**Fix:** Mark `improvement` category findings as `manual_review = TRUE` by default and exclude them from automatic tier 2. They should be surfaced in code review digests for human action.

## Implementation Priority

1. **FIX `_verify_fix()` baseline comparison** — this alone will unblock ~80% of stuck tier 2 fixes
2. **Add hotspot file sanitizer** — reduces ruff baselines on problematic files
3. **Lower tier 3 promotion threshold** — gets stuck findings to deep fix faster
4. **Exclude improvement category from auto-fix** — reduces noise
5. **Add consecutive failure tracking to webapp_autofix** — stops wasting cycles
6. **Add file locking between layers** — prevents conflicts

## Files to Modify

1. `app/analysis/autofixer/tier2_executor.py` — replace `_verify_fix()` with baseline comparison
2. `app/analysis/autofixer/tier3_deep_fixer.py` — lower `MIN_ATTEMPTS_FOR_PROMOTION` to 2
3. `app/analysis/code_fixer.py` — add `sanitize_hotspot_files()` pre-pass
4. `app/analysis/autofixer/cluster_manager.py` — exclude `improvement` category from auto-fix
5. `scripts/webapp_autofix.sh` — add consecutive failure tracking and adaptive interval

## Verification

After implementing changes, verify:
1. `_verify_fix()` passes on files with pre-existing ruff errors
2. Hotspot files have reduced ruff baselines
3. Tier 3 picks up stuck findings faster
4. `improvement` findings are no longer auto-fixed
5. Webapp autofix doesn't restart dead server every 2 min

Run this to check progress:
```sql
-- Open findings trend
SELECT DATE(fix_attempted_at) as day, COUNT(*) as attempts,
  SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as fixed
FROM code_review_findings
WHERE fix_attempted_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(fix_attempted_at) ORDER BY day;

-- Stuck findings by file
SELECT file_path, COUNT(*) as stuck
FROM code_review_findings
WHERE NOT resolved AND fix_attempt_count >= 2
GROUP BY file_path ORDER BY stuck DESC LIMIT 10;
```
