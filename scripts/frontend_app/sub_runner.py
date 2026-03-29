#!/usr/bin/env python3
"""
Sub-orchestrator for a single Part (module) of the frontend app.

Architecture per module:
1. ARCHITECT — reads API, RBAC, existing code → designs component tree, writes plan + tasks
2. ORCHESTRATOR — manages task queue, assigns to developers, runs non-regression gates
3. DEVELOPERS — N parallel Claude sessions, each working on isolated files/worktrees

Phases:
1. Discovery (Architect) — read existing code, API surface → discovery.md
2. Plan (Architect) — design components, create task list → plan.md + tasks.json
3. Execute (Dev Team) — parallel execution of tasks, merge, gate

Usage:
    python3 sub_runner.py --part 0               # run all 3 phases
    python3 sub_runner.py --part 1 --phase plan   # run only plan phase
    python3 sub_runner.py --part 2 --status       # show status
    python3 sub_runner.py --part 0 --workers 3    # parallel devs (default: 2)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = Path("/home/sebastian/personal-ai")
FRONTEND_DIR = REPO_DIR / "frontend"
CLAUDE_BIN = Path(os.getenv("CLAUDE_BIN", "/home/sebastian/.npm-global/bin/claude"))
MAX_TIMEOUT_ARCHITECT = 600   # 10 min for discovery/plan
MAX_TIMEOUT_DEV = 1200        # 20 min per dev task
DEFAULT_WORKERS = 2           # parallel devs (conservative to avoid API limits)


def get_part_dir(part_id: int) -> Path:
    return SCRIPT_DIR / "parts" / f"part{part_id}"


def run_claude(prompt: str, log_file: Path, timeout: int = 600, label: str = "") -> bool:
    """Run a Claude Code session."""
    cmd = [
        str(CLAUDE_BIN),
        "--permission-mode", "bypassPermissions",
        "--print",
        prompt,
    ]

    started = datetime.now(timezone.utc).isoformat()
    t_start = time.time()
    prefix = f"[{label}] " if label else ""

    try:
        with open(log_file, "w") as log_fh:
            log_fh.write(f"{prefix}Started: {started}\n{'='*70}\n\n")
            result = subprocess.run(
                cmd, capture_output=False,
                stdout=log_fh, stderr=log_fh,
                timeout=timeout, cwd=str(REPO_DIR),
            )

        elapsed = int(time.time() - t_start)
        ok = result.returncode == 0
        print(f"  {prefix}{'[OK]' if ok else '[!!]'} {elapsed}s")
        return ok

    except subprocess.TimeoutExpired:
        print(f"  {prefix}[TIMEOUT] {timeout}s")
        return False
    except Exception as e:
        print(f"  {prefix}[ERROR] {e}")
        return False


def run_build_gate() -> bool:
    """Non-regression gate: pnpm build."""
    if not (FRONTEND_DIR / "apps" / "web" / "package.json").exists():
        return True  # No app yet

    print("  [GATE] Building...")
    try:
        r = subprocess.run(
            ["pnpm", "--filter", "web", "build"],
            capture_output=True, text=True, timeout=120,
            cwd=str(FRONTEND_DIR),
        )
        if r.returncode == 0:
            print("  [GATE] OK")
            return True
        print(f"  [GATE] FAIL: {r.stderr[-300:]}")
        return False
    except Exception as e:
        print(f"  [GATE] ERROR: {e}")
        return False


# ---------------------------------------------------------------------------
# Phase 1: ARCHITECT — Discovery
# ---------------------------------------------------------------------------

def phase_discovery(part_id: int, master_prompt: str) -> bool:
    part_dir = get_part_dir(part_id)
    log_file = part_dir / "discovery.log"

    existing = f"\nExisting frontend: {FRONTEND_DIR}" if FRONTEND_DIR.exists() else ""

    prompt = f"""# ARCHITECT: Discovery Phase — Part {part_id}

You are the ARCHITECT for this frontend module. Your job is to thoroughly understand the API surface, RBAC rules, and existing code patterns before designing anything.
{existing}

## Module context
{master_prompt}

## Discovery tasks
1. Read relevant API endpoints from `/home/sebastian/personal-ai/app/api/main.py` (and route files)
   Focus ONLY on endpoints relevant to this module.
2. For each endpoint: note method, path, query params, request body, response format
3. Read RBAC: `/home/sebastian/personal-ai/omnius/core/permissions.py`
4. If frontend exists at `/home/sebastian/personal-ai/frontend/`, read existing:
   - Component patterns (shadcn/ui usage, naming conventions)
   - API client pattern (how other modules call the backend)
   - State management pattern (Zustand stores)
   - Layout/routing pattern (App Router structure)
5. Read relevant data models from backend code
6. Check the OpenAPI spec for exact types:
   `curl -s http://127.0.0.1:8000/openapi.json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'{{m.upper():6}} {{p}}  {{d[\"paths\"][p][m].get(\"summary\",\"\")}}') for p in sorted(d.get('paths',{{}})) for m in d['paths'][p] if m in ('get','post','put','delete')]" 2>/dev/null | head -200`

## Output
Write discovery report to: `{part_dir}/discovery.md`

Include:
- API endpoint inventory for this module (method, path, params, response shape)
- RBAC rules: which roles see what
- Existing patterns to follow
- Data types/interfaces needed
- Backend gaps (missing endpoints, need for SSE, etc.)
- Complexity estimate (simple/medium/complex per feature)
"""

    print(f"\n  [ARCHITECT] Discovery — Part {part_id}")
    return run_claude(prompt, log_file, MAX_TIMEOUT_ARCHITECT, "ARCHITECT")


# ---------------------------------------------------------------------------
# Phase 2: ARCHITECT — Plan
# ---------------------------------------------------------------------------

def phase_plan(part_id: int, master_prompt: str) -> bool:
    part_dir = get_part_dir(part_id)
    log_file = part_dir / "plan.log"

    discovery = (part_dir / "discovery.md").read_text() if (part_dir / "discovery.md").exists() else ""

    prompt = f"""# ARCHITECT: Plan Phase — Part {part_id}

You are the ARCHITECT. Based on your discovery, design the implementation and create tasks for the dev team.

## Discovery results
{discovery}

## Module context
{master_prompt}

## Design guidelines
- Next.js 15 App Router: `/frontend/apps/web/app/(app)/[module]/page.tsx`
- Components in: `/frontend/packages/ui/src/components/[module]/`
- Hooks in: `/frontend/apps/web/lib/hooks/`
- API calls via: `@gilbertus/api-client` package (generated from OpenAPI)
- RBAC via: `<RbacGate permission="...">` and `usePermissions()` from `@gilbertus/rbac`
- i18n via: `useTranslations()` from `@gilbertus/i18n` — Polish default
- Styling: Tailwind CSS + shadcn/ui, dark theme (--bg: #0f1117, --surface: #1a1d27, --accent: #6366f1)
- State: Zustand stores in `apps/web/lib/stores/`

## Your output — TWO files:

### 1. `{part_dir}/plan.md`
Detailed architecture:
- Component tree (visual hierarchy)
- File tree (every file path)
- API integration map (component → endpoint)
- RBAC per view/component
- State management (Zustand store shape)
- UX flows (user actions → system responses)

### 2. `{part_dir}/tasks.json`
Dev team tasks. IMPORTANT: design tasks so files DON'T OVERLAP between tasks (enables parallel execution).

```json
{{
  "tasks": [
    {{
      "id": "P{part_id}T1",
      "title": "Short title",
      "description": "Detailed: what to build, which endpoints, which components. Include ALL context a dev needs.",
      "files": ["exact/file/paths/to/create.tsx"],
      "parallel_group": 1,
      "status": "pending"
    }}
  ]
}}
```

Rules for task design:
- Tasks in the SAME `parallel_group` CAN run simultaneously (no file overlap!)
- Tasks in group N+1 depend on group N completing
- Each task: 1 page OR 2-3 components OR 1 hook+store — small enough for one session
- Include ALL context in description (don't rely on dev reading other files)
- 4-8 tasks per module, 2-3 parallel groups
"""

    print(f"\n  [ARCHITECT] Plan — Part {part_id}")
    return run_claude(prompt, log_file, MAX_TIMEOUT_ARCHITECT, "ARCHITECT")


# ---------------------------------------------------------------------------
# Phase 3: DEV TEAM — Execute (parallel within groups)
# ---------------------------------------------------------------------------

def _run_dev_task(task: dict, part_id: int, master_prompt: str, plan: str, discovery: str) -> bool:
    """Run a single dev task."""
    part_dir = get_part_dir(part_id)
    task_id = task["id"]
    log_file = part_dir / f"{task_id}.log"

    prompt = f"""# DEVELOPER: {task_id} — {task['title']}

You are a DEVELOPER on the frontend team. The ARCHITECT designed the plan, your job is to IMPLEMENT your assigned task.

## Project structure
- Monorepo at: /home/sebastian/personal-ai/frontend
- Backend API: http://127.0.0.1:8000
- Packages: @gilbertus/ui, @gilbertus/api-client, @gilbertus/rbac, @gilbertus/i18n

## Architect's plan (summary)
{plan[:2000]}

## API endpoints (from discovery)
{discovery[:2000]}

## YOUR TASK
{task['description']}

## Files to create/modify
{json.dumps(task.get('files', []), indent=2)}

## Rules
1. ONLY touch the files listed above — other devs are working on other files in parallel
2. TypeScript strict mode
3. Polish UI strings via i18n: `const t = useTranslations('moduleName')`
4. Dark theme: use Tailwind classes (bg-[--bg], text-[--text])
5. shadcn/ui components: import from @gilbertus/ui
6. API calls: import from @gilbertus/api-client
7. RBAC guards: `<RbacGate permission="...">` wraps restricted content
8. After writing ALL code, verify: `cd /home/sebastian/personal-ai/frontend && pnpm --filter web build`
9. If build fails, FIX IT before finishing
"""

    return run_claude(prompt, log_file, MAX_TIMEOUT_DEV, f"DEV:{task_id}")


def phase_execute(part_id: int, master_prompt: str, workers: int = DEFAULT_WORKERS) -> bool:
    part_dir = get_part_dir(part_id)
    tasks_file = part_dir / "tasks.json"

    if not tasks_file.exists():
        print(f"  [FAIL] No tasks.json for Part {part_id}")
        return False

    with open(tasks_file) as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    plan = (part_dir / "plan.md").read_text() if (part_dir / "plan.md").exists() else ""
    discovery = (part_dir / "discovery.md").read_text() if (part_dir / "discovery.md").exists() else ""

    # Group tasks by parallel_group
    groups: dict[int, list] = {}
    for t in tasks:
        g = t.get("parallel_group", 0)
        groups.setdefault(g, []).append(t)

    print(f"\n  [TEAM] Part {part_id} — {len(tasks)} tasks, {len(groups)} groups, {workers} workers")

    for group_id in sorted(groups.keys()):
        group_tasks = [t for t in groups[group_id] if t["status"] != "done"]
        if not group_tasks:
            continue

        print(f"\n  [GROUP {group_id}] {len(group_tasks)} tasks" +
              (f" (parallel, {min(workers, len(group_tasks))} workers)" if len(group_tasks) > 1 else ""))

        # Mark all as in_progress
        for t in group_tasks:
            t["status"] = "in_progress"
        with open(tasks_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if len(group_tasks) == 1 or workers == 1:
            # Sequential
            for t in group_tasks:
                ok = _run_dev_task(t, part_id, master_prompt, plan, discovery)
                t["status"] = "done" if ok else "failed"
                with open(tasks_file, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            # Parallel execution
            results = {}
            with ThreadPoolExecutor(max_workers=min(workers, len(group_tasks))) as pool:
                futures = {
                    pool.submit(_run_dev_task, t, part_id, master_prompt, plan, discovery): t
                    for t in group_tasks
                }
                for future in as_completed(futures):
                    t = futures[future]
                    try:
                        ok = future.result()
                        t["status"] = "done" if ok else "failed"
                    except Exception as e:
                        print(f"  [DEV:{t['id']}] EXCEPTION: {e}")
                        t["status"] = "failed"
                    results[t["id"]] = t["status"]

            with open(tasks_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            for tid, status in results.items():
                print(f"  {tid}: {status}")

        # Non-regression gate after each group
        if not run_build_gate():
            print(f"  [WARN] Build failed after group {group_id}")
            # Don't stop — next group may fix it

        time.sleep(5)

    done = sum(1 for t in tasks if t["status"] == "done")
    print(f"\n  Part {part_id}: {done}/{len(tasks)} tasks done")
    return done == len(tasks)


# ---------------------------------------------------------------------------
# Part runner
# ---------------------------------------------------------------------------

def run_part(part_id: int, phase: str | None = None, workers: int = DEFAULT_WORKERS) -> bool:
    """Run all phases (or specific) for a Part."""
    queue = json.load(open(SCRIPT_DIR / "queue.json"))
    task = next((t for t in queue["tasks"] if t["id"] == f"P{part_id}"), None)
    if not task:
        print(f"[FAIL] Part {part_id} not found in queue")
        return False

    prompt_file = SCRIPT_DIR / "prompts" / f"{task['file']}.md"
    if not prompt_file.exists():
        print(f"[FAIL] Prompt not found: {prompt_file}")
        return False

    master_prompt = prompt_file.read_text()
    phases = ["discovery", "plan", "execute"] if phase is None else [phase]

    for p in phases:
        print(f"\n{'='*70}")
        print(f"  Part {part_id} — {p.upper()}")
        print(f"{'='*70}")

        if p == "discovery":
            ok = phase_discovery(part_id, master_prompt)
        elif p == "plan":
            ok = phase_plan(part_id, master_prompt)
        elif p == "execute":
            ok = phase_execute(part_id, master_prompt, workers)
        else:
            return False

        if not ok and p != "execute":
            print(f"  [RETRY] {p}...")
            time.sleep(10)
            if p == "discovery":
                ok = phase_discovery(part_id, master_prompt)
            elif p == "plan":
                ok = phase_plan(part_id, master_prompt)
            if not ok:
                return False

        time.sleep(5)

    return True


def show_status(part_id: int):
    part_dir = get_part_dir(part_id)
    print(f"\n  Part {part_id}:")
    print(f"    Discovery: {'OK' if (part_dir / 'discovery.md').exists() else '--'}")
    print(f"    Plan:      {'OK' if (part_dir / 'plan.md').exists() else '--'}")

    tf = part_dir / "tasks.json"
    if tf.exists():
        data = json.load(open(tf))
        tasks = data.get("tasks", [])
        for t in tasks:
            icon = {"done": "OK", "failed": "!!", "pending": "..", "in_progress": ">>"}.get(t["status"], "??")
            grp = t.get("parallel_group", "?")
            print(f"    [{icon}] {t['id']} (g{grp}): {t['title']}")
    else:
        print("    Tasks: not planned yet")


def main():
    parser = argparse.ArgumentParser(description="Sub-orchestrator for frontend Part")
    parser.add_argument("--part", type=int, required=True)
    parser.add_argument("--phase", choices=["discovery", "plan", "execute"])
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel dev workers")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        show_status(args.part)
        return

    success = run_part(args.part, args.phase, args.workers)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
