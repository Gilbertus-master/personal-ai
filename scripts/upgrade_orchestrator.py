#!/usr/bin/env python3
"""
Gilbertus Quality Upgrade Orchestrator
=======================================
Manages 19 upgrade tasks across 6 waves.
Parallel within each wave, sequential between waves (dependency order).

Usage:
    python scripts/upgrade_orchestrator.py [--dry-run] [--wave N] [--task TX]

Options:
    --dry-run       Show what would run without executing
    --wave N        Start from wave N (1-6)
    --task TX       Run only task TX (e.g. T8)
    --resume        Skip already-done tasks (default: true)
"""

import subprocess
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# ─── Config ──────────────────────────────────────────────────────────────────

PROJECT_DIR = Path("/home/sebastian/personal-ai")
PROMPTS_DIR = PROJECT_DIR / "scripts/upgrade_prompts"
STATUS_DIR  = Path("/tmp/gilbertus_upgrade/status")
LOG_DIR     = Path("/tmp/gilbertus_upgrade/logs")
ORCH_LOG    = PROJECT_DIR / "logs/upgrade_orchestrator.log"
CLAUDE_BIN  = os.path.expanduser("~/.npm-global/bin/claude")

STATUS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Task Definitions ─────────────────────────────────────────────────────────

# Map task ID → prompt file (None = inline prompt below)
TASK_PROMPTS = {
    "T1":  "T1_tool_routing.md",
    "T2":  "T2_log_rotation.md",
    "T3":  "T3_pgbouncer.md",
    "T4":  "T4_qdrant_drift.md",
    "T5":  "T5_credit_alert.md",
    "T6":  "T6_stage_timing.md",
    "T7":  "T7_interp_cache.md",
    "T8":  "T8_hybrid_search.md",
    "T9":  "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T9 section
    "T10": "T10_topk_reranking.md",
    "T11": "T11_coverage_dashboard.md",
    "T12": "T12_feedback_loop.md",
    "T13": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T13 section
    "T14": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T14 section
    "T15": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T15 section
    "T16": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T16 section
    "T17": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T17 section
    "T18": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T18 section
    "T19": "T13_T9_T16_T14_T15_T17_T18_T19.md",   # T19 section
}

TASK_NAMES = {
    "T1":  "ENABLE_TOOL_ROUTING",
    "T2":  "Log rotation",
    "T3":  "PgBouncer setup",
    "T4":  "Qdrant drift fix",
    "T5":  "Credit alert",
    "T6":  "Per-stage timing → PG",
    "T7":  "Interpretation cache → PG",
    "T8":  "Hybrid search BM25+RRF",
    "T9":  "Email backfill",
    "T10": "Top-k + reranking",
    "T11": "Coverage dashboard",
    "T12": "User feedback loop",
    "T13": "Answer cache TTL",
    "T14": "Progressive context",
    "T15": "Retrieval quality alerts",
    "T16": "Entity linking",
    "T17": "Weekly quality review",
    "T18": "Chunking optimization",
    "T19": "PG tuning",
}

# Timeouts per task (seconds)
TASK_TIMEOUTS = {
    "T1": 180,    "T2": 120,    "T3": 600,    "T4": 600,
    "T5": 300,    "T6": 900,    "T7": 900,    "T8": 2400,
    "T9": 900,    "T10": 900,   "T11": 1800,  "T12": 2400,
    "T13": 300,   "T14": 1200,  "T15": 600,   "T16": 900,
    "T17": 1800,  "T18": 2400,  "T19": 600,
}

# Wave definitions: list of task sets (each set runs in parallel)
# Dependencies: Wave N starts only after Wave N-1 fully completes
WAVES = [
    # Wave 0: All independent tasks
    ["T1", "T2", "T4", "T5", "T6", "T9", "T13"],

    # Wave 1: PgBouncer (critical blocker)
    ["T3"],

    # Wave 2: After PgBouncer — cache, hybrid search, dashboard, entity linking
    ["T7", "T8", "T11", "T16"],

    # Wave 3: After hybrid search + timing — reranking, feedback, alerts
    ["T10", "T12", "T15"],

    # Wave 4: After reranking — progressive context + PG tuning
    ["T14", "T19"],

    # Wave 5: After feedback+timing — weekly review
    ["T17"],

    # Wave 6: After hybrid+reranking — chunking optimization
    ["T18"],
]

# ─── Logging ─────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(ORCH_LOG, "a") as f:
        f.write(line + "\n")

# ─── Status tracking ─────────────────────────────────────────────────────────

def is_done(task_id: str) -> bool:
    return (STATUS_DIR / f"{task_id}.done").exists()

def mark_failed(task_id: str, reason: str):
    with open(STATUS_DIR / f"{task_id}.failed", "w") as f:
        f.write(reason)

def is_failed(task_id: str) -> bool:
    return (STATUS_DIR / f"{task_id}.failed").exists()

# ─── Task execution ──────────────────────────────────────────────────────────

def build_prompt_for_task(task_id: str) -> str:
    """Load the prompt for a task from its file."""
    prompt_file = TASK_PROMPTS.get(task_id)
    if not prompt_file:
        return f"Task {task_id}: no prompt defined"
    
    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        return f"ERROR: prompt file not found: {prompt_path}"
    
    content = prompt_path.read_text()
    
    # For combined files, extract just the section for this task
    if task_id in ["T9", "T13", "T14", "T15", "T16", "T17", "T18", "T19"]:
        lines = content.split("\n")
        in_section = False
        section_lines = []
        for line in lines:
            if line.startswith(f"## {task_id}:"):
                in_section = True
            elif in_section and line.startswith("## T") and not line.startswith(f"## {task_id}:"):
                break
            if in_section:
                section_lines.append(line)
        if section_lines:
            content = "\n".join(section_lines)
    
    return content

def run_task_agent(task_id: str, dry_run: bool = False) -> subprocess.Popen | None:
    """Launch a Claude Code agent for a task. Returns the process."""
    if is_done(task_id):
        log(f"  {task_id} already done, skipping")
        return None
    
    name = TASK_NAMES.get(task_id, task_id)
    prompt = build_prompt_for_task(task_id)
    task_log = LOG_DIR / f"{task_id}.log"
    
    if dry_run:
        log(f"  [DRY-RUN] Would launch agent for {task_id}: {name}")
        return None
    
    log(f"  🚀 Launching agent for {task_id}: {name}")
    
    # Full prompt with context prefix
    full_prompt = f"""You are a Python/infrastructure engineer implementing upgrades for the Gilbertus AI system.
Project directory: /home/sebastian/personal-ai
Work carefully, test each step, and handle errors gracefully.
When done, write to status file as instructed.

{prompt}
"""
    
    cmd = [
        CLAUDE_BIN,
        "--permission-mode", "bypassPermissions",
        "--print",
        full_prompt,
    ]
    
    log_file = open(task_log, "w")
    log_file.write(f"=== {task_id}: {name} ===\nStarted: {datetime.now()}\n\n")
    log_file.flush()
    
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT_DIR),
    )
    
    return proc

# ─── Wave execution ──────────────────────────────────────────────────────────

def run_wave(wave_num: int, tasks: list[str], dry_run: bool = False, auto_yes: bool = False) -> dict:
    """Run all tasks in a wave in parallel. Returns {task_id: 'done'|'failed'|'skipped'}."""
    
    log(f"\n{'='*60}")
    log(f"WAVE {wave_num}: {[TASK_NAMES[t] for t in tasks]}")
    log(f"{'='*60}")
    
    # Skip already done
    to_run = [t for t in tasks if not is_done(t)]
    skipped = [t for t in tasks if is_done(t)]
    
    if skipped:
        log(f"  Already done (skipping): {skipped}")
    
    if not to_run:
        log(f"  All tasks in wave {wave_num} already complete")
        return {t: "done" for t in tasks}
    
    # Launch all tasks in parallel
    processes: dict[str, tuple[subprocess.Popen, float]] = {}
    for task_id in to_run:
        proc = run_task_agent(task_id, dry_run=dry_run)
        if proc:
            processes[task_id] = (proc, time.time())
    
    if dry_run:
        return {t: "dry-run" for t in tasks}
    
    # Wait for all to complete
    results = {t: "done" for t in skipped}
    timeouts = {tid: TASK_TIMEOUTS.get(tid, 1800) for tid in to_run}
    
    pending = dict(processes)
    poll_interval = 30  # seconds between status checks
    
    while pending:
        time.sleep(poll_interval)
        
        completed_now = []
        for task_id, (proc, start_time) in pending.items():
            retcode = proc.poll()
            elapsed = time.time() - start_time
            
            if retcode is not None:
                # Process finished
                completed_now.append(task_id)
                if is_done(task_id):
                    log(f"  ✅ {task_id} ({TASK_NAMES[task_id]}) DONE in {elapsed:.0f}s")
                    results[task_id] = "done"
                else:
                    log(f"  ❌ {task_id} ({TASK_NAMES[task_id]}) FAILED (exit {retcode}) in {elapsed:.0f}s", "ERROR")
                    log(f"     Check log: {LOG_DIR / (task_id + '.log')}", "ERROR")
                    mark_failed(task_id, f"exit code {retcode}")
                    results[task_id] = "failed"
            
            elif elapsed > timeouts[task_id]:
                # Timeout
                completed_now.append(task_id)
                log(f"  ⏱️  {task_id} ({TASK_NAMES[task_id]}) TIMEOUT after {elapsed:.0f}s", "WARN")
                proc.kill()
                mark_failed(task_id, f"timeout after {elapsed:.0f}s")
                results[task_id] = "timeout"
            
            else:
                log(f"  ⏳ {task_id} running ({elapsed:.0f}s / {timeouts[task_id]}s)...")
        
        for task_id in completed_now:
            del pending[task_id]
    
    return results

# ─── Main orchestration ───────────────────────────────────────────────────────

def summarize_results(all_results: dict):
    done = [t for t, s in all_results.items() if s == "done"]
    failed = [t for t, s in all_results.items() if s in ("failed", "timeout")]
    skipped = [t for t, s in all_results.items() if s == "skipped"]
    
    log("\n" + "="*60)
    log("FINAL SUMMARY")
    log("="*60)
    log(f"✅ Done ({len(done)}): {done}")
    if failed:
        log(f"❌ Failed ({len(failed)}): {failed}", "ERROR")
        for t in failed:
            log_path = LOG_DIR / f"{t}.log"
            if log_path.exists():
                log(f"   {t} log: {log_path}", "ERROR")
    if skipped:
        log(f"⏭️  Skipped: {skipped}")
    
    # Notify Sebastian
    if failed:
        msg = f"🔧 Gilbertus upgrade: {len(done)}/19 done, ❌ {len(failed)} failed: {failed}"
    else:
        msg = f"✅ Gilbertus upgrade complete: {len(done)}/19 tasks done!"
    
    try:
        subprocess.run(["openclaw", "system", "event", "--text", msg, "--mode", "now"], timeout=10)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Gilbertus Quality Upgrade Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--wave", type=int, help="Start from wave N (0-6)")
    parser.add_argument("--task", type=str, help="Run only specific task (e.g. T8)")
    parser.add_argument("--no-resume", action="store_true", help="Re-run all tasks even if done")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm wave failures and continue")
    args = parser.parse_args()
    
    if args.no_resume:
        # Clear all status files
        for f in STATUS_DIR.glob("*.done"):
            f.unlink()
    
    log("="*60)
    log("Gilbertus Quality Upgrade Orchestrator Starting")
    log(f"Project: {PROJECT_DIR}")
    log(f"Waves: {len(WAVES)}, Total tasks: {sum(len(w) for w in WAVES)}")
    log(f"Dry-run: {args.dry_run}")
    log("="*60)
    
    all_results = {}
    
    # Single task mode
    if args.task:
        tid = args.task.upper()
        if tid not in TASK_NAMES:
            log(f"Unknown task: {tid}", "ERROR")
            sys.exit(1)
        results = run_wave(99, [tid], dry_run=args.dry_run, auto_yes=args.yes)
        all_results.update(results)
        summarize_results(all_results)
        return
    
    start_wave = args.wave or 0
    
    for wave_num, wave_tasks in enumerate(WAVES):
        if wave_num < start_wave:
            log(f"Skipping wave {wave_num} (starting from {start_wave})")
            continue
        
        results = run_wave(wave_num, wave_tasks, dry_run=args.dry_run, auto_yes=args.yes)
        all_results.update(results)
        
        # Check if critical tasks failed before proceeding
        critical_failures = [t for t in wave_tasks if results.get(t) in ("failed", "timeout")]
        if critical_failures:
            log(f"\n⚠️  Wave {wave_num} had failures: {critical_failures}", "WARN")
            
            # T3 failure blocks waves 2+ (T7, T8 need PgBouncer)
            if "T3" in critical_failures and wave_num == 1:
                log("T3 (PgBouncer) failed. Waves 2+ depend on it. Stopping.", "ERROR")
                break
            
            # T8 failure blocks waves 3+ (T10 needs hybrid search)
            if "T8" in critical_failures and wave_num == 2:
                log("T8 (hybrid search) failed. T10, T14, T18 depend on it.", "WARN")
                log("Continuing with independent tasks in waves 3+.", "WARN")
            
            if args.yes:
                log("Auto-continuing despite failures (--yes flag).", "WARN")
            else:
                user_input = input(f"\nWave {wave_num} had failures. Continue anyway? [y/N]: ")
                if user_input.lower() != "y":
                    log("Stopping due to failures.")
                    break
        
        if wave_num < len(WAVES) - 1:
            log(f"\nWave {wave_num} complete. Pausing 10s before wave {wave_num + 1}...")
            if not args.dry_run:
                time.sleep(10)
    
    summarize_results(all_results)

if __name__ == "__main__":
    main()
