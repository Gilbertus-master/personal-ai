#!/usr/bin/env python3
"""
Master Orchestrator — Gilbertus/Omnius Frontend Application.

PARALLEL execution model:
  Wave 1: P0 (foundation) — must be first
  Wave 2: P1 (chat) — depends on P0
  Wave 3: P2, P3, P4, P5, P6, P7, P8 — ALL IN PARALLEL (depend on P0+P1)
  Wave 4: P9 (polish) — depends on all

Within each Part: dev team runs with N parallel workers.

Usage:
    python3 master.py              # run all (parallel waves)
    python3 master.py --part 3     # run specific part
    python3 master.py --status     # show status
    python3 master.py --workers 3  # parallel devs per part (default: 2)
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUEUE_FILE = SCRIPT_DIR / "queue.json"

# Dependency graph: which parts can run in parallel
WAVES = [
    [0],                          # Wave 1: foundation (solo)
    [1],                          # Wave 2: chat (depends on P0)
    [2, 3, 4, 5, 6, 7, 8],       # Wave 3: ALL modules in parallel
    [9],                          # Wave 4: polish (depends on all)
]


def load_queue() -> dict:
    with open(QUEUE_FILE) as f:
        return json.load(f)


def save_queue(queue: dict):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def get_task(queue: dict, part_id: str) -> dict | None:
    for t in queue["tasks"]:
        if t["id"] == part_id:
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
    print("  Gilbertus/Omnius Frontend — Master Orchestrator")
    print(f"{'='*70}")
    print(f"  Total: {total}  |  Done: {done}  |  Failed: {failed}  |  Pending: {pending}  |  Running: {running}")
    print(f"{'='*70}")
    print("  Execution model: 4 waves (P0 → P1 → P2-P8 parallel → P9)")
    print(f"{'='*70}\n")

    for wave_idx, wave in enumerate(WAVES):
        parts_str = ", ".join(f"P{p}" for p in wave)
        parallel = " [PARALLEL]" if len(wave) > 1 else ""
        print(f"  Wave {wave_idx + 1}: {parts_str}{parallel}")
        for p in wave:
            task = get_task(queue, f"P{p}")
            if task:
                icon = {"done": "[OK]", "failed": "[!!]", "pending": "[..]", "in_progress": "[>>]"}.get(task["status"], "[??]")
                print(f"    {icon} [{task['id']:3}] {task['level']:8} {task['title'][:55]}")

                # Show sub-task progress
                part_dir = SCRIPT_DIR / "parts" / f"part{p}"
                tasks_file = part_dir / "tasks.json"
                if tasks_file.exists():
                    data = json.load(open(tasks_file))
                    sub = data.get("tasks", [])
                    sub_done = sum(1 for s in sub if s["status"] == "done")
                    if sub:
                        print(f"         sub-tasks: {sub_done}/{len(sub)}")
        print()


def run_part(part_id: int, workers: int = 2) -> bool:
    """Run a part via sub_runner.py."""
    import subprocess
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "sub_runner.py"),
        "--part", str(part_id),
        "--workers", str(workers),
    ]

    print(f"\n  [START] Part {part_id} (workers={workers})")
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    ok = result.returncode == 0
    print(f"  [{'OK' if ok else 'FAIL'}] Part {part_id}")
    return ok


def run_wave(wave: list[int], queue: dict, workers: int = 2) -> dict[int, bool]:
    """Run all parts in a wave. If >1 part, run in parallel."""
    results = {}

    # Filter to pending/failed only
    parts_to_run = []
    for p in wave:
        task = get_task(queue, f"P{p}")
        if task and task["status"] not in ("done",):
            parts_to_run.append(p)

    if not parts_to_run:
        print(f"  [SKIP] Wave {wave} — all done")
        return {p: True for p in wave}

    if len(parts_to_run) == 1:
        # Sequential
        p = parts_to_run[0]
        task = get_task(queue, f"P{p}")
        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        ok = run_part(p, workers)

        task["status"] = "done" if ok else "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)
        results[p] = ok
    else:
        # PARALLEL execution
        print(f"\n{'='*70}")
        print(f"  PARALLEL WAVE: {len(parts_to_run)} parts simultaneously")
        print(f"  Parts: {', '.join(f'P{p}' for p in parts_to_run)}")
        print(f"  Workers per part: {workers}")
        print(f"  Total concurrent agents: ~{len(parts_to_run) * workers}")
        print(f"{'='*70}")

        # Mark all as in_progress
        for p in parts_to_run:
            task = get_task(queue, f"P{p}")
            task["status"] = "in_progress"
            task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)

        # Run in parallel
        with ThreadPoolExecutor(max_workers=len(parts_to_run)) as pool:
            futures = {
                pool.submit(run_part, p, workers): p
                for p in parts_to_run
            }
            for future in as_completed(futures):
                p = futures[future]
                try:
                    ok = future.result()
                except Exception as e:
                    print(f"  [ERROR] Part {p}: {e}")
                    ok = False

                task = get_task(queue, f"P{p}")
                task["status"] = "done" if ok else "failed"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()
                save_queue(queue)
                results[p] = ok
                print(f"  [{'OK' if ok else 'FAIL'}] Part {p} finished")

    return results


def main():
    parser = argparse.ArgumentParser(description="Frontend App Master Orchestrator")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--part", type=int, help="Run specific part (0-9)")
    parser.add_argument("--workers", type=int, default=3, help="Parallel dev workers per part (default: 3)")
    parser.add_argument("--reset", type=int, help="Reset part to pending")
    parser.add_argument("--reset-all", action="store_true")
    args = parser.parse_args()

    queue = load_queue()

    if args.status:
        print_status(queue)
        return

    if args.reset is not None:
        task = get_task(queue, f"P{args.reset}")
        if task:
            task["status"] = "pending"
            task["started_at"] = None
            task["completed_at"] = None
            save_queue(queue)
            print(f"[OK] Reset P{args.reset}")
        return

    if args.reset_all:
        for t in queue["tasks"]:
            t["status"] = "pending"
            t["started_at"] = None
            t["completed_at"] = None
        save_queue(queue)
        print("[OK] All parts reset")
        return

    if args.part is not None:
        # Single part
        task = get_task(queue, f"P{args.part}")
        if not task:
            print(f"[FAIL] Part {args.part} not found")
            sys.exit(1)
        task["status"] = "in_progress"
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)
        ok = run_part(args.part, args.workers)
        task["status"] = "done" if ok else "failed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(queue)
        sys.exit(0 if ok else 1)

    # Full run: execute waves
    print("\nFrontend App Master — Parallel Wave Execution")
    print(f"Workers per part: {args.workers}")
    print_status(queue)

    for wave_idx, wave in enumerate(WAVES):
        print(f"\n{'#'*70}")
        print(f"  WAVE {wave_idx + 1}/{len(WAVES)}: Parts {', '.join(f'P{p}' for p in wave)}")
        print(f"{'#'*70}")

        results = run_wave(wave, queue, args.workers)

        # Check if any critical failures
        failures = [p for p, ok in results.items() if not ok]
        if failures and wave_idx < len(WAVES) - 1:
            print(f"\n  [WARN] Parts {failures} failed in wave {wave_idx + 1}")
            print("  Continuing to next wave (failed parts may cause issues)...")

        if wave_idx < len(WAVES) - 1:
            print("\n  Pause 15s before next wave...")
            time.sleep(15)

    print(f"\n{'='*70}")
    print("  Frontend build complete!")
    print(f"{'='*70}")
    print_status(load_queue())


if __name__ == "__main__":
    main()
