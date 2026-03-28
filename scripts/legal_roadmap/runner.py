#!/usr/bin/env python3
"""
Legal Compliance Roadmap Runner — autonomiczny orchestrator wdrożeń security.

Algorytm:
1. Wczytaj queue.json
2. Znajdź pierwsze zadanie ze status="pending"
3. Uruchom Claude Code z promptem z pliku prompts/{task.file}.md
4. Poczekaj na zakończenie (timeout 600s)
5. Zapisz wynik do queue.json (status: done/failed)
6. Przejdź do następnego zadania
7. Powtarzaj aż queue pusta lub --single-task

Użycie:
    python3 runner.py              # uruchom wszystkie pending
    python3 runner.py --dry-run    # pokaż co będzie robione
    python3 runner.py --task H1    # uruchom konkretne zadanie
    python3 runner.py --status     # pokaż stan kolejki
    python3 runner.py --reset H1   # zresetuj zadanie do pending
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
MAX_TIMEOUT = 600  # sekund per zadanie


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
    print("  Legal Compliance Roadmap — Status")
    print(f"{'='*60}")
    print(f"  Total:   {total}")
    print(f"  Done:    {done}")
    print(f"  Failed:  {failed}")
    print(f"  Pending: {pending}")
    print(f"  Running: {running}")
    print(f"{'='*60}\n")

    for t in tasks:
        icon = {"done": "[OK]", "failed": "[FAIL]", "pending": "[..]", "in_progress": "[>>]"}.get(t["status"], "[??]")
        cost = f"${t['session_cost_usd']:.4f}" if t.get("session_cost_usd") else ""
        level = t.get('level', '')
        print(f"  {icon} [{t['id']:3}] {level:6} {t['title'][:45]:45} {cost}")
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
    print(f"  Prompt: {prompt_file.name}")
    print(f"  Log: {log_file.name}")
    print(f"{'='*60}\n")

    if dry_run:
        print("  [DRY RUN — nie uruchamiam Claude Code]")
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

        print(f"\n  {'[OK] Done' if success else '[FAIL] Failed'} [{task['id']}] "
              f"in {elapsed}s (exit={result.returncode})")

        # Wczytaj log żeby sprawdzić czy NON-REGRESSION przeszedł
        log_content = log_file.read_text() if log_file.exists() else ""
        if "non_regression_gate" in log_content.lower():
            gate_ok = "ok" in log_content.lower() or "passed" in log_content.lower()
            print(f"  Non-regression gate: {'[OK]' if gate_ok else '[WARN]'}")

        return success

    except subprocess.TimeoutExpired:
        print(f"\n  [TIMEOUT] [{task['id']}] — przekroczono {MAX_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"\n  [ERROR] [{task['id']}]: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Legal Compliance Roadmap Runner")
    parser.add_argument("--dry-run", action="store_true", help="Pokaż co będzie robione bez wykonania")
    parser.add_argument("--status", action="store_true", help="Pokaż stan kolejki")
    parser.add_argument("--task", type=str, help="Uruchom konkretne zadanie (np. H1)")
    parser.add_argument("--reset", type=str, help="Zresetuj zadanie do pending")
    parser.add_argument("--all", action="store_true", help="Uruchom wszystkie pending (domyślnie)")
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

    # Wybierz zadania do uruchomienia
    if args.task:
        task = get_task(queue, args.task.upper())
        if not task:
            print(f"[FAIL] Task not found: {args.task}")
            sys.exit(1)
        tasks_to_run = [task]
    else:
        tasks_to_run = [t for t in queue["tasks"] if t["status"] == "pending"]

    if not tasks_to_run:
        print("[OK] Wszystkie zadania wykonane!")
        print_status(queue)
        return

    print("\nLegal Compliance Roadmap Runner")
    print(f"  Zadania do uruchomienia: {len(tasks_to_run)}")
    print(f"  Tryb: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print_status(queue)

    # Wykonuj kolejno
    for i, task in enumerate(tasks_to_run, 1):
        print(f"\n[{i}/{len(tasks_to_run)}] Zaczynam: {task['id']} — {task['title']}")

        # Oznacz jako in_progress
        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        # Uruchom
        success = run_task(task, dry_run=args.dry_run)

        # Zapisz wynik
        task["status"] = "done" if success else "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        if not success:
            print(f"\n[WARN] Zadanie {task['id']} nieudane.")
            print(f"  Log: {LOGS_DIR}/{task['id']}_{task['file']}.log")
            print("  Kontynuuję do następnego zadania...\n")

        # Krótka przerwa między zadaniami
        if i < len(tasks_to_run) and not args.dry_run:
            print("\n  Pauza 10s przed następnym zadaniem...")
            time.sleep(10)

    print(f"\n{'='*60}")
    print("  Roadmap completed!")
    print(f"{'='*60}")
    print_status(load_queue())


if __name__ == "__main__":
    main()
