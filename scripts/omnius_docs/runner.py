#!/usr/bin/env python3
"""
Omnius Deployment Documentation Orchestrator.

Generates complete compliance documentation package for deploying Omnius AI
in REH (Respect Energy Holding) and REF (Respect Energy Fuels).

Each task:
1. Creates compliance matters/obligations in the legal module DB
2. Generates documents via document_generator.py (Claude AI)
3. Saves final documents to desktop folders (REH + REF)

Usage:
    python3 runner.py              # run all pending tasks
    python3 runner.py --dry-run    # show what would be done
    python3 runner.py --task D01   # run specific task
    python3 runner.py --status     # show queue status
    python3 runner.py --reset D01  # reset task to pending
    python3 runner.py --reset-all  # reset all tasks
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
MAX_TIMEOUT = 900  # 15 min per doc (longer than audit fixer — doc generation is heavier)

OUTPUT_REH = Path("/mnt/c/Users/jablo/Desktop/Omnius_REH")
OUTPUT_REF = Path("/mnt/c/Users/jablo/Desktop/Omnius_REF")


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

    print(f"\n{'='*70}")
    print("  Omnius Deployment Documentation — Status")
    print(f"{'='*70}")
    print(f"  Total: {total}  |  Done: {done}  |  Failed: {failed}  |  Pending: {pending}  |  Running: {running}")
    print(f"  Output REH: {OUTPUT_REH}")
    print(f"  Output REF: {OUTPUT_REF}")
    print(f"{'='*70}\n")

    for t in tasks:
        icon = {
            "done": "[OK]", "failed": "[!!]", "pending": "[..]", "in_progress": "[>>]",
        }.get(t["status"], "[??]")
        level = t.get("level", "")
        print(f"  {icon} [{t['id']:3}] {level:8} {t['title'][:50]}")
    print()


def run_task(task: dict, dry_run: bool = False) -> bool:
    prompt_file = PROMPTS_DIR / f"{task['file']}.md"

    if not prompt_file.exists():
        print(f"  [FAIL] Prompt file not found: {prompt_file}")
        return False

    prompt = prompt_file.read_text()
    log_file = LOGS_DIR / f"{task['id']}_{task['file']}.log"

    print(f"\n{'='*70}")
    print(f"  [>>] {task['id']}: {task['title']}")
    print(f"  Level: {task.get('level', 'N/A')}  |  Prompt: {prompt_file.name}")
    print(f"{'='*70}\n")

    if dry_run:
        print("  [DRY RUN]")
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
            log_fh.write(f"{'='*70}\n\n")

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

        # Check output files exist
        reh_files = list(OUTPUT_REH.glob(f"{task['id'][-2:]}*"))
        ref_files = list(OUTPUT_REF.glob(f"{task['id'][-2:]}*"))

        print(f"  {'[OK]' if success else '[!!]'} {task['id']} — {elapsed}s "
              f"(exit={result.returncode}, REH={len(reh_files)} files, REF={len(ref_files)} files)")

        return success

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {task['id']} — exceeded {MAX_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"  [ERROR] {task['id']}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Omnius Deployment Documentation Orchestrator")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--task", type=str, help="Run specific task (e.g. D01)")
    parser.add_argument("--reset", type=str)
    parser.add_argument("--reset-all", action="store_true")
    args = parser.parse_args()

    # Ensure output dirs exist
    OUTPUT_REH.mkdir(parents=True, exist_ok=True)
    OUTPUT_REF.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

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
            print(f"[OK] Reset: {args.reset}")
        else:
            print(f"[FAIL] Not found: {args.reset}")
        return

    if args.reset_all:
        for t in queue["tasks"]:
            t["status"] = "pending"
            t["started_at"] = None
            t["completed_at"] = None
            t["session_cost_usd"] = None
        save_queue(queue)
        print("[OK] All tasks reset")
        return

    if args.task:
        task = get_task(queue, args.task.upper())
        if not task:
            print(f"[FAIL] Not found: {args.task}")
            sys.exit(1)
        tasks_to_run = [task]
    else:
        tasks_to_run = [t for t in queue["tasks"] if t["status"] == "pending"]

    if not tasks_to_run:
        print("[OK] All documents generated!")
        print_status(queue)
        return

    print(f"\nOmnius Documentation Orchestrator — {len(tasks_to_run)} tasks")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print_status(queue)

    for i, task in enumerate(tasks_to_run, 1):
        print(f"\n[{i}/{len(tasks_to_run)}] {task['id']}: {task['title']}")

        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        success = run_task(task, dry_run=args.dry_run)

        task["status"] = "done" if success else "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        if not success:
            print(f"  [WARN] {task['id']} failed — see {LOGS_DIR}/{task['id']}_{task['file']}.log")

        if i < len(tasks_to_run) and not args.dry_run:
            print("  Pause 15s...")
            time.sleep(15)

    print(f"\n{'='*70}")
    print("  Documentation generation complete!")
    print(f"{'='*70}")
    print_status(load_queue())

    # Summary of generated files
    print("\nGenerated files:")
    for d, label in [(OUTPUT_REH, "REH"), (OUTPUT_REF, "REF")]:
        files = sorted(d.glob("*.md"))
        print(f"\n  {label} ({len(files)} documents):")
        for f in files:
            print(f"    {f.name}")


if __name__ == "__main__":
    main()
