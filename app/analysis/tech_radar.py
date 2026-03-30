"""
Tech Radar — Technology Discovery & Development Roadmap.

Based on app inventory (F1), employee automation analysis (F2), discovered processes,
and strategic goals: identifies technology solutions to build/buy/extend,
creates dependency graph, priority ranking, and quarterly roadmap.

Cron: monthly (2nd of month, 5:00 CET — after F2 runs on 1st)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=180.0)

DISCOVERY_PROMPT = """Jesteś architektem systemów AI dla polskiej firmy energetycznej (REH/REF).
Firma ma system AI "Gilbertus" (prywatny mentat CEO) i "Omnius" (agent firmowy dla pracowników).

Na podstawie danych o:
- Aplikacjach vendorskich (koszty, użycie, zastępowalność)
- Profilach pracy pracowników (co można zautomatyzować)
- Odkrytych procesach biznesowych (automation potential)
- Celach strategicznych firmy

Zidentyfikuj KONKRETNE ROZWIĄZANIA TECHNOLOGICZNE do wydewelopowania.

Dla każdego rozwiązania zwróć:
{
  "name": "nazwa rozwiązania",
  "description": "co robi (2-3 zdania)",
  "solution_type": "build|buy|extend",
  "target_module": "istniejący moduł do rozszerzenia LUB nazwa nowego",
  "capability_description": "jaką zdolność dodaje do systemu",
  "problems_solved": [{"problem": "...", "source": "process|app|employee", "source_id": "nazwa"}],
  "estimated_dev_hours": N,
  "estimated_cost_pln": N,
  "estimated_annual_savings_pln": N,
  "roi_ratio": N,
  "payback_months": N,
  "strategic_alignment_score": 0-100,
  "dependencies": ["nazwa innego rozwiązania które musi być zrobione wcześniej"],
  "risk_notes": "ryzyka i ograniczenia"
}

Zasady:
- Dev hour = 200 PLN (Gilbertus + Claude Code dev), buy = rzeczywista cena rynkowa
- ROI = annual_savings / (dev_hours * 200)
- DEDUPLIKUJ: jeśli ten sam moduł pojawia się w wielu źródłach, połącz w jedno rozwiązanie
- Priorytetyzuj: najpierw to co ma najwyższy ROI i jest komplementarne z istniejącym systemem
- Nie proponuj rozwiązań które duplikują istniejące moduły Gilbertus
- Bądź realistyczny w estymacjach — nie zawyżaj savings
- Każde rozwiązanie musi być KONKRETNE i WDROŻYCIALNE

Zwróć JSON array z rozwiązaniami, posortowany od najwyższego ROI.
Odpowiedz TYLKO JSON array."""

SOLUTION_TOOL = {
    "name": "return_solutions",
    "description": "Return discovered technology solutions with ROI analysis",
    "input_schema": {
        "type": "object",
        "properties": {
            "solutions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "solution_type": {"type": "string", "enum": ["build", "buy", "extend"]},
                        "target_module": {"type": "string"},
                        "capability_description": {"type": "string"},
                        "problems_solved": {"type": "array"},
                        "estimated_dev_hours": {"type": "number"},
                        "estimated_cost_pln": {"type": "number"},
                        "estimated_annual_savings_pln": {"type": "number"},
                        "roi_ratio": {"type": "number"},
                        "payback_months": {"type": "number"},
                        "strategic_alignment_score": {"type": "integer"},
                        "dependencies": {"type": "array"},
                        "risk_notes": {"type": "string"},
                    },
                    "required": ["name", "description", "solution_type", "estimated_dev_hours",
                                 "estimated_annual_savings_pln", "roi_ratio"],
                },
            },
        },
        "required": ["solutions"],
    },
}


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tech_solutions (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    solution_type TEXT DEFAULT 'build'
                        CHECK (solution_type IN ('build', 'buy', 'extend')),
                    target_module TEXT,
                    capability_description TEXT,
                    problems_solved JSONB DEFAULT '[]',
                    estimated_dev_hours NUMERIC DEFAULT 0,
                    estimated_cost_pln NUMERIC DEFAULT 0,
                    estimated_annual_savings_pln NUMERIC DEFAULT 0,
                    roi_ratio NUMERIC DEFAULT 0,
                    payback_months NUMERIC DEFAULT 0,
                    strategic_alignment_score INTEGER DEFAULT 50
                        CHECK (strategic_alignment_score >= 0 AND strategic_alignment_score <= 100),
                    strategic_goal_ids JSONB DEFAULT '[]',
                    priority_score INTEGER DEFAULT 50
                        CHECK (priority_score >= 0 AND priority_score <= 100),
                    status TEXT DEFAULT 'proposed'
                        CHECK (status IN ('proposed', 'approved', 'in_development', 'deployed', 'rejected')),
                    risk_notes TEXT,
                    confidence NUMERIC DEFAULT 0.5,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_ts_priority ON tech_solutions(priority_score DESC);
                CREATE INDEX IF NOT EXISTS idx_ts_status ON tech_solutions(status);
                CREATE INDEX IF NOT EXISTS idx_ts_type ON tech_solutions(solution_type);

                CREATE TABLE IF NOT EXISTS tech_dependencies (
                    id BIGSERIAL PRIMARY KEY,
                    solution_id BIGINT NOT NULL REFERENCES tech_solutions(id) ON DELETE CASCADE,
                    depends_on_id BIGINT REFERENCES tech_solutions(id) ON DELETE SET NULL,
                    depends_on_name TEXT NOT NULL,
                    dependency_type TEXT DEFAULT 'blocks'
                        CHECK (dependency_type IN ('blocks', 'enhances', 'data_source')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_td_solution ON tech_dependencies(solution_id);
                CREATE INDEX IF NOT EXISTS idx_td_depends ON tech_dependencies(depends_on_id);

                CREATE TABLE IF NOT EXISTS tech_roadmap_snapshots (
                    id BIGSERIAL PRIMARY KEY,
                    snapshot_date DATE NOT NULL UNIQUE,
                    roadmap JSONB NOT NULL,
                    total_solutions INTEGER DEFAULT 0,
                    total_dev_hours NUMERIC DEFAULT 0,
                    total_savings_pln NUMERIC DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()


# ---------------------------------------------------------------------------
# Gather inputs from F1, F2, existing modules
# ---------------------------------------------------------------------------

def _gather_technology_inputs() -> str:
    """Collect context from all feeder sources for solution discovery."""
    parts = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # F1: High-cost/replaceable apps
            cur.execute("""
                SELECT name, category, vendor, cost_yearly_pln, replacement_feasibility,
                       replacement_plan, user_details
                FROM app_inventory
                WHERE cost_yearly_pln > 0 OR replacement_feasibility > 30
                ORDER BY COALESCE(cost_yearly_pln, 0) * COALESCE(replacement_feasibility, 0) DESC
                LIMIT 20
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("=== APLIKACJE VENDORSKIE (koszty + zastępowalność) ===")
                for r in rows:
                    plan = r[5] if isinstance(r[5], dict) else json.loads(r[5]) if r[5] else {}
                    users = r[6] if isinstance(r[6], list) else json.loads(r[6]) if r[6] else []
                    parts.append(
                        f"  {r[0]} ({r[1]}): vendor={r[2]}, koszt={r[3]} PLN/rok, "
                        f"feasibility={r[4]}%, users={len(users)}, "
                        f"plan={plan.get('gilbertus_module', '?')}"
                    )

            # F2: Employee automation opportunities
            cur.execute("""
                SELECT person_name, person_role, organization,
                       replaceability_score, automatable_pct,
                       potential_savings_monthly_pln, automation_roadmap
                FROM employee_work_profiles
                WHERE status != 'archived'
                ORDER BY replaceability_score DESC
                LIMIT 15
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("\n=== PROFILY PRACY PRACOWNIKÓW (potencjał automatyzacji) ===")
                for r in rows:
                    roadmap = r[6] if isinstance(r[6], list) else json.loads(r[6]) if r[6] else []
                    top_tasks = [t.get("task", "?") for t in roadmap[:3]]
                    parts.append(
                        f"  {r[0]} ({r[1]}, {r[2]}): replaceability={r[3]}%, "
                        f"automatable={r[4]}%, savings={r[5]} PLN/msc, "
                        f"top_tasks={top_tasks}"
                    )

            # Discovered processes with high automation potential
            cur.execute("""
                SELECT name, process_type, frequency, automation_potential, automation_notes, tools_used
                FROM discovered_processes
                WHERE automation_potential >= 50
                ORDER BY automation_potential DESC
                LIMIT 15
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("\n=== PROCESY O WYSOKIM POTENCJALE AUTOMATYZACJI ===")
                for r in rows:
                    tools = r[5] if isinstance(r[5], list) else json.loads(r[5]) if r[5] else []
                    parts.append(
                        f"  {r[0]} ({r[1]}, {r[2]}): potential={r[3]}%, "
                        f"notes={r[4]}, tools={tools}"
                    )

            # Optimization plans not yet implemented
            cur.execute("""
                SELECT target_process, current_state, target_state,
                       time_savings_hours, cost_savings_pln, implementation_effort, priority_score
                FROM optimization_plans
                WHERE status IN ('planned', 'proposed')
                ORDER BY priority_score DESC
                LIMIT 10
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("\n=== NIEZREALIZOWANE PLANY OPTYMALIZACJI ===")
                for r in rows:
                    parts.append(
                        f"  {r[0]}: {r[1]} → {r[2]}, savings={r[3]}h/{r[4]} PLN, "
                        f"effort={r[5]}, priority={r[6]}"
                    )

            # Strategic goals
            cur.execute("""
                SELECT name, area, company, target, progress_pct, status
                FROM strategic_goals
                WHERE status NOT IN ('completed', 'abandoned')
                ORDER BY priority DESC NULLS LAST
                LIMIT 10
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("\n=== CELE STRATEGICZNE ===")
                for r in rows:
                    parts.append(
                        f"  [{r[2]}] {r[0]} ({r[1]}): target={r[3]}, progress={r[4]}%, status={r[5]}"
                    )

            # Data flows with bottlenecks
            cur.execute("""
                SELECT flow_description, sender, receiver, channel, automation_status, bottleneck_risk
                FROM data_flows
                WHERE bottleneck_risk IN ('medium', 'high') OR automation_status = 'manual'
                ORDER BY bottleneck_risk DESC NULLS LAST
                LIMIT 10
            """)
            rows = cur.fetchall()
            if rows:
                parts.append("\n=== PRZEPŁYWY DANYCH Z BOTTLENECKAMI ===")
                for r in rows:
                    parts.append(
                        f"  {r[0]}: {r[1]}→{r[2]} via {r[3]}, auto={r[4]}, risk={r[5]}"
                    )

    # Existing Gilbertus modules
    parts.append("\n=== ISTNIEJĄCE MODUŁY GILBERTUS (nie duplikuj) ===")
    parts.append(
        "commitment_tracker, meeting_prep, meeting_minutes, smart_response_drafter, "
        "weekly_synthesis, sentiment_tracker, wellbeing_monitor, contract_tracker, "
        "delegation_tracker, blind_spot_detector, network_analyzer, predictive_alerts, "
        "market_intelligence (12 RSS), competitor_intelligence (7 competitors), "
        "scenario_analyzer, decision_intelligence, action_pipeline, calendar_manager, "
        "strategic_goals, financial_framework, cost_estimator, app_inventory, "
        "process_mining, data_flow_mapper, optimization_planner, employee_automation, "
        "morning_brief, smart_alerts, voice_pipeline (STT+TTS), whatsapp_commands, "
        "org_health_score, llm_evaluator, cron_registry, health_monitor"
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Solution Discovery
# ---------------------------------------------------------------------------

def discover_solutions(force: bool = False) -> dict[str, Any]:
    """Main discovery: identify tech solutions from all inputs."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    # Check if we already have recent solutions
    if not force:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM tech_solutions
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)
                if cur.fetchall()[0][0] > 0:
                    return {"message": "Recent solutions exist. Use force=True to re-discover.", "skipped": True}

    context = _gather_technology_inputs()
    if len(context) < 200:
        return {"error": "Insufficient data for solution discovery. Run F1 and F2 first."}

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=6000,
            temperature=0.1,
            system=[{"type": "text", "text": DISCOVERY_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
            tools=[SOLUTION_TOOL],
            tool_choice={"type": "tool", "name": "return_solutions"},
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "tech_radar.discover", response.usage)
    except Exception as e:
        log.error("tech_discovery_llm_failed", error=str(e))
        return {"error": str(e)}

    solutions = []
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            solutions = block.input.get("solutions", [])
            break

    if not solutions:
        return {"error": "LLM returned no solutions"}

    # Store solutions
    stored = 0
    solution_ids = {}  # name -> id for dependency linking
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Archive old solutions
            cur.execute("UPDATE tech_solutions SET status = 'rejected' WHERE status = 'proposed' AND created_at < NOW() - INTERVAL '30 days'")

            for sol in solutions:
                name = sol.get("name", "")
                if not name:
                    continue

                cur.execute("""
                    INSERT INTO tech_solutions (
                        name, description, solution_type, target_module,
                        capability_description, problems_solved,
                        estimated_dev_hours, estimated_cost_pln,
                        estimated_annual_savings_pln, roi_ratio, payback_months,
                        strategic_alignment_score, risk_notes, confidence
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    name,
                    sol.get("description", ""),
                    sol.get("solution_type", "build"),
                    sol.get("target_module", ""),
                    sol.get("capability_description", ""),
                    json.dumps(sol.get("problems_solved", []), ensure_ascii=False, default=str),
                    sol.get("estimated_dev_hours", 0),
                    sol.get("estimated_cost_pln", sol.get("estimated_dev_hours", 0) * 200),
                    sol.get("estimated_annual_savings_pln", 0),
                    sol.get("roi_ratio", 0),
                    sol.get("payback_months", 0),
                    sol.get("strategic_alignment_score", 50),
                    sol.get("risk_notes", ""),
                    0.6,
                ))
                row = cur.fetchone()
                if row:
                    solution_ids[name] = row[0]
                    stored += 1

            conn.commit()

            # Store dependencies
            for sol in solutions:
                name = sol.get("name", "")
                sol_id = solution_ids.get(name)
                if not sol_id:
                    continue

                for dep_name in sol.get("dependencies", []):
                    dep_id = solution_ids.get(dep_name)
                    cur.execute("""
                        INSERT INTO tech_dependencies (solution_id, depends_on_id, depends_on_name, dependency_type)
                        VALUES (%s, %s, %s, 'blocks')
                    """, (sol_id, dep_id, dep_name))

            conn.commit()

    # Calculate priority scores
    calculate_priority_scores()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("tech_discovery_done", solutions=stored, latency_ms=latency_ms)
    return {"solutions_discovered": stored, "solutions": solutions, "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# Priority Scoring
# ---------------------------------------------------------------------------

def calculate_priority_scores():
    """Calculate composite priority for all proposed solutions."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, roi_ratio, strategic_alignment_score, estimated_dev_hours
                FROM tech_solutions WHERE status IN ('proposed', 'approved')
            """)
            solutions = cur.fetchall()

            if not solutions:
                return

            # Normalize ROI (0-100)
            max_roi = max(float(s[1] or 0) for s in solutions) or 1.0

            for sol_id, roi, alignment, dev_hours in solutions:
                # Check dependency readiness
                cur.execute("""
                    SELECT COUNT(*), SUM(CASE WHEN ts.status = 'deployed' THEN 1 ELSE 0 END)
                    FROM tech_dependencies td
                    LEFT JOIN tech_solutions ts ON ts.id = td.depends_on_id
                    WHERE td.solution_id = %s AND td.dependency_type = 'blocks'
                """, (sol_id,))
                dep_rows = cur.fetchall()
                dep_row = dep_rows[0] if dep_rows else None
                total_deps = dep_row[0] or 0 if dep_row else 0
                deployed_deps = dep_row[1] or 0 if dep_row else 0
                dep_readiness = 100 if total_deps == 0 else int((deployed_deps / total_deps) * 100)

                # Risk based on dev hours (higher = more risk)
                risk = min(int(float(dev_hours or 0) / 2), 100)

                # Composite score
                normalized_roi = min(float(roi or 0) / max_roi * 100, 100)
                priority = int(
                    0.4 * normalized_roi +
                    0.3 * float(alignment or 50) +
                    0.2 * dep_readiness +
                    0.1 * (100 - risk)
                )
                priority = max(0, min(100, priority))

                cur.execute(
                    "UPDATE tech_solutions SET priority_score = %s, updated_at = NOW() WHERE id = %s",
                    (priority, sol_id),
                )

            conn.commit()

    log.info("priority_scores_calculated", count=len(solutions))


# ---------------------------------------------------------------------------
# Strategic Goal Linking
# ---------------------------------------------------------------------------

def link_to_strategic_goals():
    """Cross-reference solutions with strategic_goals table."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, description, capability_description FROM tech_solutions WHERE status IN ('proposed', 'approved')")
            solutions = cur.fetchall()

            cur.execute("SELECT id, name, area, company FROM strategic_goals WHERE status NOT IN ('completed', 'abandoned')")
            goals = cur.fetchall()

            for sol_id, sol_name, sol_desc, sol_cap in solutions:
                matching_goals = []
                sol_text = f"{sol_name} {sol_desc or ''} {sol_cap or ''}".lower()

                for goal_id, goal_name, goal_area, goal_company in goals:
                    goal_text = f"{goal_name} {goal_area or ''}".lower()
                    # Simple keyword overlap scoring
                    sol_words = set(sol_text.split())
                    goal_words = set(goal_text.split())
                    overlap = len(sol_words & goal_words)
                    if overlap >= 2 or any(w in sol_text for w in goal_text.split() if len(w) > 4):
                        matching_goals.append(goal_id)

                if matching_goals:
                    cur.execute(
                        "UPDATE tech_solutions SET strategic_goal_ids = %s WHERE id = %s",
                        (json.dumps(matching_goals), sol_id),
                    )

            conn.commit()

    log.info("strategic_goals_linked")


# ---------------------------------------------------------------------------
# Roadmap Generation
# ---------------------------------------------------------------------------

def generate_roadmap() -> dict[str, Any]:
    """Create ordered development roadmap using topological sort + priority."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, solution_type, target_module,
                       estimated_dev_hours, estimated_cost_pln,
                       estimated_annual_savings_pln, roi_ratio, payback_months,
                       priority_score, status, strategic_alignment_score
                FROM tech_solutions
                WHERE status IN ('proposed', 'approved', 'in_development')
                ORDER BY priority_score DESC
            """)
            cols = [d[0] for d in cur.description]
            solutions = [dict(zip(cols, r)) for r in cur.fetchall()]

            # Get dependencies
            cur.execute("""
                SELECT solution_id, depends_on_id, depends_on_name
                FROM tech_dependencies WHERE dependency_type = 'blocks'
            """)
            deps = cur.fetchall()

    if not solutions:
        return {"roadmap": [], "summary": {"total_solutions": 0}}

    # Build adjacency for topological sort
    dep_map: dict[int, list[int]] = {}
    for sol_id, dep_id, dep_name in deps:
        dep_map.setdefault(sol_id, []).append(dep_id)

    # Topological sort (Kahn's algorithm)
    in_degree: dict[int, int] = {s["id"]: 0 for s in solutions}
    for sol_id, dep_ids in dep_map.items():
        if sol_id in in_degree:
            in_degree[sol_id] = len([d for d in dep_ids if d and d in in_degree])

    # Group into tiers
    tiers: list[list[dict]] = []
    remaining = {s["id"]: s for s in solutions}

    while remaining:
        # Find solutions with no unresolved dependencies
        tier = []
        for sol_id, sol in list(remaining.items()):
            if in_degree.get(sol_id, 0) == 0:
                tier.append(sol)

        if not tier:
            # Circular dependency — add all remaining
            tier = list(remaining.values())
            remaining = {}
        else:
            # Remove from remaining, update in-degrees
            for sol in tier:
                del remaining[sol["id"]]
                # Reduce in-degree for dependents
                for other_id in remaining:
                    if sol["id"] in dep_map.get(other_id, []):
                        in_degree[other_id] = max(0, in_degree.get(other_id, 0) - 1)

        # Sort within tier by priority
        tier.sort(key=lambda x: -(x.get("priority_score") or 0))
        tiers.append(tier)

    # Build roadmap with quarters
    roadmap = []
    cumulative_hours = 0
    cumulative_savings = 0
    quarter_labels = ["Q2 2026", "Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027"]

    for tier_idx, tier in enumerate(tiers):
        quarter = quarter_labels[min(tier_idx, len(quarter_labels) - 1)]
        for sol in tier:
            hours = float(sol.get("estimated_dev_hours") or 0)
            savings = float(sol.get("estimated_annual_savings_pln") or 0)
            cumulative_hours += hours
            cumulative_savings += savings

            roadmap.append({
                "tier": tier_idx + 1,
                "quarter": quarter,
                "id": sol["id"],
                "name": sol["name"],
                "type": sol["solution_type"],
                "target_module": sol.get("target_module"),
                "dev_hours": hours,
                "cost_pln": float(sol.get("estimated_cost_pln") or hours * 200),
                "annual_savings_pln": savings,
                "roi_ratio": float(sol.get("roi_ratio") or 0),
                "priority_score": sol.get("priority_score", 0),
                "status": sol["status"],
                "cumulative_hours": cumulative_hours,
                "cumulative_savings": cumulative_savings,
            })

    # Save snapshot
    total_hours = sum(float(s.get("estimated_dev_hours") or 0) for s in solutions)
    total_savings = sum(float(s.get("estimated_annual_savings_pln") or 0) for s in solutions)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tech_roadmap_snapshots (snapshot_date, roadmap, total_solutions, total_dev_hours, total_savings_pln)
                VALUES (CURRENT_DATE, %s, %s, %s, %s)
                ON CONFLICT (snapshot_date) DO UPDATE SET
                    roadmap = EXCLUDED.roadmap,
                    total_solutions = EXCLUDED.total_solutions,
                    total_dev_hours = EXCLUDED.total_dev_hours,
                    total_savings_pln = EXCLUDED.total_savings_pln
            """, (
                json.dumps(roadmap, ensure_ascii=False, default=str),
                len(solutions),
                total_hours,
                total_savings,
            ))
            conn.commit()

    log.info("roadmap_generated", tiers=len(tiers), solutions=len(roadmap))

    return {
        "roadmap": roadmap,
        "tiers": len(tiers),
        "summary": {
            "total_solutions": len(solutions),
            "total_dev_hours": round(total_hours, 1),
            "total_dev_cost_pln": round(total_hours * 200, 2),
            "total_annual_savings_pln": round(total_savings, 2),
            "overall_roi": round(total_savings / max(total_hours * 200, 1), 2),
            "estimated_payback_months": round(
                (total_hours * 200) / max(total_savings / 12, 1), 1
            ),
        },
    }


# ---------------------------------------------------------------------------
# Dashboard & Detail Views
# ---------------------------------------------------------------------------

def get_tech_radar_dashboard() -> dict:
    """Full dashboard: solutions by type/status, top 10, total savings, current roadmap."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Solutions by type
            cur.execute("""
                SELECT solution_type, COUNT(*), SUM(estimated_annual_savings_pln)
                FROM tech_solutions WHERE status != 'rejected'
                GROUP BY solution_type
            """)
            by_type = {r[0]: {"count": r[1], "total_savings": float(r[2] or 0)} for r in cur.fetchall()}

            # Solutions by status
            cur.execute("""
                SELECT status, COUNT(*) FROM tech_solutions
                GROUP BY status
            """)
            by_status = {r[0]: r[1] for r in cur.fetchall()}

            # Top 10 by priority
            cur.execute("""
                SELECT id, name, solution_type, target_module, estimated_dev_hours,
                       estimated_annual_savings_pln, roi_ratio, priority_score, status
                FROM tech_solutions
                WHERE status NOT IN ('rejected', 'deployed')
                ORDER BY priority_score DESC
                LIMIT 10
            """)
            cols = [d[0] for d in cur.description]
            top10 = [dict(zip(cols, r)) for r in cur.fetchall()]

            # Totals
            cur.execute("""
                SELECT COUNT(*), SUM(estimated_dev_hours), SUM(estimated_annual_savings_pln)
                FROM tech_solutions WHERE status NOT IN ('rejected')
            """)
            totals = cur.fetchone()

            # Latest roadmap snapshot
            cur.execute("""
                SELECT snapshot_date, total_solutions, total_dev_hours, total_savings_pln
                FROM tech_roadmap_snapshots ORDER BY snapshot_date DESC LIMIT 1
            """)
            snapshot = cur.fetchone()

    return {
        "by_type": by_type,
        "by_status": by_status,
        "top_10": top10,
        "totals": {
            "solutions": totals[0] if totals else 0,
            "dev_hours": float(totals[1] or 0) if totals else 0,
            "annual_savings_pln": float(totals[2] or 0) if totals else 0,
        },
        "latest_snapshot": {
            "date": str(snapshot[0]) if snapshot else None,
            "solutions": snapshot[1] if snapshot else 0,
            "dev_hours": float(snapshot[2] or 0) if snapshot else 0,
            "savings_pln": float(snapshot[3] or 0) if snapshot else 0,
        } if snapshot else None,
    }


def get_solution_detail(solution_id: int) -> dict | None:
    """Single solution with dependencies, linked goals."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tech_solutions WHERE id = %s", (solution_id,))
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            if not row:
                return None

            solution = dict(zip(cols, row))

            # Parse JSONB
            for field in ["problems_solved", "strategic_goal_ids"]:
                val = solution.get(field)
                if isinstance(val, str):
                    try:
                        solution[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Dependencies
            cur.execute("""
                SELECT td.depends_on_name, td.dependency_type, ts.status as dep_status
                FROM tech_dependencies td
                LEFT JOIN tech_solutions ts ON ts.id = td.depends_on_id
                WHERE td.solution_id = %s
            """, (solution_id,))
            solution["dependencies"] = [
                {"name": r[0], "type": r[1], "status": r[2]}
                for r in cur.fetchall()
            ]

            # Dependents (who depends on this)
            cur.execute("""
                SELECT ts.name, ts.status
                FROM tech_dependencies td
                JOIN tech_solutions ts ON ts.id = td.solution_id
                WHERE td.depends_on_id = %s
            """, (solution_id,))
            solution["dependents"] = [{"name": r[0], "status": r[1]} for r in cur.fetchall()]

            # Linked strategic goals
            goal_ids = solution.get("strategic_goal_ids", [])
            if goal_ids:
                placeholders = ",".join(["%s"] * len(goal_ids))
                cur.execute(f"""
                    SELECT id, name, area, company, progress_pct
                    FROM strategic_goals WHERE id IN ({placeholders})
                """, goal_ids)
                solution["linked_goals"] = [
                    {"id": r[0], "name": r[1], "area": r[2], "company": r[3], "progress": r[4]}
                    for r in cur.fetchall()
                ]

    return solution


def update_solution_status(solution_id: int, status: str) -> dict:
    """Update solution status (proposed→approved→in_development→deployed or rejected)."""
    valid = ("proposed", "approved", "in_development", "deployed", "rejected")
    if status not in valid:
        return {"error": f"Invalid status. Must be one of: {valid}"}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tech_solutions SET status = %s, updated_at = NOW() WHERE id = %s RETURNING name",
                (status, solution_id),
            )
            row = cur.fetchone()
            conn.commit()

    if not row:
        return {"error": f"Solution {solution_id} not found"}

    log.info("solution_status_updated", solution=row[0], status=status)
    return {"solution_id": solution_id, "name": row[0], "status": status}


def get_tech_strategic_alignment() -> dict:
    """Show alignment between solutions and strategic goals."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ts.id, ts.name, ts.strategic_alignment_score, ts.strategic_goal_ids,
                       ts.estimated_annual_savings_pln, ts.priority_score
                FROM tech_solutions ts
                WHERE ts.status NOT IN ('rejected')
                ORDER BY ts.strategic_alignment_score DESC
            """)
            cols = [d[0] for d in cur.description]
            solutions = [dict(zip(cols, r)) for r in cur.fetchall()]

    for sol in solutions:
        val = sol.get("strategic_goal_ids")
        if isinstance(val, str):
            try:
                sol["strategic_goal_ids"] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                sol["strategic_goal_ids"] = []

    return {
        "solutions": solutions,
        "summary": {
            "total": len(solutions),
            "avg_alignment": round(
                sum(s.get("strategic_alignment_score", 0) for s in solutions) / max(len(solutions), 1), 1
            ),
            "aligned_count": sum(1 for s in solutions if (s.get("strategic_goal_ids") or [])),
            "unaligned_count": sum(1 for s in solutions if not (s.get("strategic_goal_ids") or [])),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    if cmd == "discover":
        print(json.dumps(discover_solutions(force=True), ensure_ascii=False, indent=2, default=str))
    elif cmd == "roadmap":
        print(json.dumps(generate_roadmap(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "dashboard":
        print(json.dumps(get_tech_radar_dashboard(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "detail" and len(sys.argv) > 2:
        print(json.dumps(get_solution_detail(int(sys.argv[2])), ensure_ascii=False, indent=2, default=str))
    elif cmd == "alignment":
        print(json.dumps(get_tech_strategic_alignment(), ensure_ascii=False, indent=2, default=str))
    else:
        print("Usage: python -m app.analysis.tech_radar [discover|roadmap|dashboard|detail <id>|alignment]")
