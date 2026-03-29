#!/usr/bin/env python3
"""
Data Guardian Orchestrator — fixes all issues found during Gilbertus audit.

Based on the legal_roadmap runner pattern. Runs Claude Code sessions sequentially
to fix each identified problem.

Usage:
    python3 runner.py              # run all pending tasks
    python3 runner.py --dry-run    # show what would be done
    python3 runner.py --task C1    # run specific task
    python3 runner.py --status     # show queue status
    python3 runner.py --reset C1   # reset task to pending
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUEUE_FILE = SCRIPT_DIR / "queue.json"
PROMPTS_DIR = SCRIPT_DIR / "prompts"
LOGS_DIR = SCRIPT_DIR / "logs"
REPO_DIR = Path("/home/sebastian/personal-ai")
CLAUDE_BIN = Path(os.getenv("CLAUDE_BIN", "/home/sebastian/.npm-global/bin/claude"))
MAX_TIMEOUT = 900  # seconds per task


def load_queue() -> dict:
    with open(QUEUE_FILE) as f:
        return json.load(f)


def save_queue(queue: dict):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def get_task(queue: dict, task_id: str) -> dict | None:
    for t in queue["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def print_status(queue: dict):
    tasks = queue["tasks"]
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "done")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    pending = sum(1 for t in tasks if t["status"] == "pending")
    running = sum(1 for t in tasks if t["status"] == "in_progress")

    print(f"\n{'='*60}")
    print("  Data Guardian — Status")
    print(f"{'='*60}")
    print(f"  Total:   {total}")
    print(f"  Done:    {done}")
    print(f"  Failed:  {failed}")
    print(f"  Pending: {pending}")
    print(f"  Running: {running}")
    print(f"{'='*60}\n")

    for t in tasks:
        icon = {
            "done": "[OK]",
            "failed": "[FAIL]",
            "pending": "[..]",
            "in_progress": "[>>]",
        }.get(t["status"], "[??]")
        cost = f"${t['session_cost_usd']:.4f}" if t.get("session_cost_usd") else ""
        level = t.get("level", "")
        print(f"  {icon} [{t['id']:3}] {level:8} {t['title'][:42]:42} {cost}")
    print()


def run_task(task: dict, dry_run: bool = False) -> bool:
    prompt_file = PROMPTS_DIR / f"{task['file']}.md"

    if not prompt_file.exists():
        print(f"  [FAIL] Prompt file not found: {prompt_file}")
        return False

    prompt = prompt_file.read_text()
    log_file = LOGS_DIR / f"{task['id']}_{task['file']}.log"

    print(f"\n{'='*60}")
    print(f"  [>>] Running: [{task['id']}] {task['title']}")
    print(f"  Level: {task.get('level', 'N/A')}")
    print(f"  Prompt: {prompt_file.name}")
    print(f"  Log: {log_file.name}")
    print(f"{'='*60}\n")

    if dry_run:
        print("  [DRY RUN — not launching Claude Code]")
        return True

    cmd = [
        str(CLAUDE_BIN),
        "--permission-mode", "bypassPermissions",
        "--print",
        prompt,
    ]

    started = datetime.now(timezone.utc).isoformat()
    t_start = time.time()

    try:
        with open(log_file, "w") as log_fh:
            log_fh.write(f"Task: {task['id']} — {task['title']}\n")
            log_fh.write(f"Level: {task.get('level', 'N/A')}\n")
            log_fh.write(f"Started: {started}\n")
            log_fh.write(f"{'='*60}\n\n")

            result = subprocess.run(
                cmd,
                capture_output=False,
                stdout=log_fh,
                stderr=log_fh,
                timeout=MAX_TIMEOUT,
                cwd=str(REPO_DIR),
            )

        elapsed = int(time.time() - t_start)
        success = result.returncode == 0

        print(
            f"\n  {'[OK] Done' if success else '[FAIL] Failed'} [{task['id']}] "
            f"in {elapsed}s (exit={result.returncode})"
        )

        # Check log for non-regression signals
        log_content = log_file.read_text() if log_file.exists() else ""
        if "non_regression" in log_content.lower() or "non-regression" in log_content.lower():
            gate_ok = "passed" in log_content.lower() or "ok" in log_content.lower()
            print(f"  Non-regression gate: {'[OK]' if gate_ok else '[WARN]'}")

        return success

    except subprocess.TimeoutExpired:
        print(f"\n  [TIMEOUT] [{task['id']}] — exceeded {MAX_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"\n  [ERROR] [{task['id']}]: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Data Guardian Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--status", action="store_true", help="Show queue status")
    parser.add_argument("--task", type=str, help="Run specific task (e.g. C1)")
    parser.add_argument("--reset", type=str, help="Reset task to pending")
    parser.add_argument("--reset-all", action="store_true", help="Reset all tasks to pending")
    args = parser.parse_args()

    queue = load_queue()

    if args.status:
        print_status(queue)
        return

    if args.reset:
        task = get_task(queue, args.reset.upper())
        if task:
            task["status"] = "pending"
            task["started_at"] = None
            task["completed_at"] = None
            task["session_cost_usd"] = None
            save_queue(queue)
            print(f"[OK] Reset: {args.reset} -> pending")
        else:
            print(f"[FAIL] Task not found: {args.reset}")
        return

    if args.reset_all:
        for t in queue["tasks"]:
            t["status"] = "pending"
            t["started_at"] = None
            t["completed_at"] = None
            t["session_cost_usd"] = None
        save_queue(queue)
        print("[OK] All tasks reset to pending")
        return

    # Select tasks to run
    if args.task:
        task = get_task(queue, args.task.upper())
        if not task:
            print(f"[FAIL] Task not found: {args.task}")
            sys.exit(1)
        tasks_to_run = [task]
    else:
        tasks_to_run = [t for t in queue["tasks"] if t["status"] == "pending"]

    if not tasks_to_run:
        print("[OK] All tasks completed!")
        print_status(queue)
        return

    print("\nData Guardian Orchestrator")
    print(f"  Tasks to run: {len(tasks_to_run)}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print_status(queue)

    # Execute sequentially
    for i, task in enumerate(tasks_to_run, 1):
        print(f"\n[{i}/{len(tasks_to_run)}] Starting: {task['id']} — {task['title']}")

        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        success = run_task(task, dry_run=args.dry_run)

        task["status"] = "done" if success else "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        if not success:
            print(f"\n[WARN] Task {task['id']} failed.")
            print(f"  Log: {LOGS_DIR}/{task['id']}_{task['file']}.log")
            print("  Continuing to next task...\n")

        # Pause between tasks
        if i < len(tasks_to_run) and not args.dry_run:
            print("\n  Pause 10s before next task...")
            time.sleep(10)

    print(f"\n{'='*60}")
    print("  Data Guardian — Complete!")
    print(f"{'='*60}")
    print_status(load_queue())


if __name__ == "__main__":
    main()
