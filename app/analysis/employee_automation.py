"""
Employee Automation Analysis — "Pracownik vs Robot"

For each employee: maps work activities, categorizes them (routine/judgment/relationship/
creative/supervisory), assesses automation potential, calculates cost/savings, generates
per-role automation roadmap.

CEO-ONLY module. Not exposed through Omnius bridge.

Cron: monthly (1st of month, 3:00 CET)
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

WORK_PROFILE_PROMPT = """Jesteś ekspertem od automatyzacji procesów i analizy pracy w polskiej firmie energetycznej (REH/REF).

Na podstawie danych o aktywności pracownika stwórz PROFIL PRACY i oceń potencjał automatyzacji.

Każdą aktywność zaklasyfikuj do jednej z 5 kategorii:
- routine: powtarzalne, proceduralnie, nie wymagające decyzji (np. raportowanie, wprowadzanie danych, forwarding maili)
- judgment: wymagające oceny sytuacji i decyzji (np. wycena ryzyka, negocjacje cenowe, ocena kontrahenta)
- relationship: zależne od relacji interpersonalnych (np. budowanie zaufania klienta, zarządzanie konfliktem, networking)
- creative: twórcze, innowacyjne (np. strategia, nowy produkt, optymalizacja procesu)
- supervisory: nadzorcze, kontrolne (np. review pracy zespołu, audyt, approval)

Zwróć JSON (użyj tool_choice):
{
  "work_activities": [
    {
      "activity": "nazwa aktywności",
      "category": "routine|judgment|relationship|creative|supervisory",
      "frequency": "daily|weekly|monthly",
      "hours_per_week": N,
      "automation_potential": 0-100,
      "automation_notes": "co konkretnie Gilbertus/Omnius mógłby robić zamiast",
      "gilbertus_module": "istniejący moduł lub 'new: opis'"
    }
  ],
  "category_hours": {
    "routine": N, "judgment": N, "relationship": N, "creative": N, "supervisory": N
  },
  "total_hours_weekly": N,
  "automatable_pct": 0-100,
  "replaceability_score": 0-100,
  "replaceability_breakdown": {
    "routine_auto": 0-100, "judgment_auto": 0-100,
    "relationship_auto": 0-100, "creative_auto": 0-100, "supervisory_auto": 0-100
  },
  "unique_value_notes": "co ta osoba robi, czego technologia NIE zastąpi (2-3 zdania)",
  "automation_roadmap": [
    {
      "task": "co zautomatyzować",
      "gilbertus_module": "moduł",
      "dev_hours": N,
      "savings_monthly_pln": N,
      "priority": 1-100
    }
  ],
  "estimated_monthly_cost_pln": N,
  "potential_savings_monthly_pln": N
}

Zasady:
- Koszt pracownika: brutto + ZUS + overhead ≈ rola × mnożnik (junior ~8k, mid ~15k, senior ~25k, director ~35k PLN/msc)
- Savings = automatable_hours * (monthly_cost / total_hours / 4.33)
- Bądź realistyczny — relacje i judgment trudno zastąpić
- replaceability_score uwzględnia: ile pracy jest routine + jak dojrzałe są moduły Gilbertusa
- Nie spekuluj — opieraj się na danych. Jeśli mało danych, zaznacz niską confidence.
"""

WORK_PROFILE_TOOL = {
    "name": "return_work_profile",
    "description": "Return structured employee work profile with automation assessment",
    "input_schema": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "object",
                "properties": {
                    "work_activities": {"type": "array"},
                    "category_hours": {"type": "object"},
                    "total_hours_weekly": {"type": "number"},
                    "automatable_pct": {"type": "integer"},
                    "replaceability_score": {"type": "integer"},
                    "replaceability_breakdown": {"type": "object"},
                    "unique_value_notes": {"type": "string"},
                    "automation_roadmap": {"type": "array"},
                    "estimated_monthly_cost_pln": {"type": "number"},
                    "potential_savings_monthly_pln": {"type": "number"},
                },
                "required": [
                    "work_activities", "category_hours", "total_hours_weekly",
                    "automatable_pct", "replaceability_score", "replaceability_breakdown",
                    "unique_value_notes", "automation_roadmap",
                    "estimated_monthly_cost_pln", "potential_savings_monthly_pln",
                ],
            },
        },
        "required": ["profile"],
    },
}


_tables_ensured = False
def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS employee_work_profiles (
                    id BIGSERIAL PRIMARY KEY,
                    person_id INTEGER,
                    entity_id BIGINT,
                    person_name TEXT NOT NULL,
                    person_role TEXT,
                    organization TEXT,
                    analysis_period_from DATE,
                    analysis_period_to DATE,

                    work_activities JSONB DEFAULT '[]',

                    routine_hours_weekly NUMERIC DEFAULT 0,
                    judgment_hours_weekly NUMERIC DEFAULT 0,
                    relationship_hours_weekly NUMERIC DEFAULT 0,
                    creative_hours_weekly NUMERIC DEFAULT 0,
                    supervisory_hours_weekly NUMERIC DEFAULT 0,
                    total_hours_weekly NUMERIC DEFAULT 0,

                    automatable_pct INTEGER DEFAULT 0
                        CHECK (automatable_pct >= 0 AND automatable_pct <= 100),
                    replaceability_score INTEGER DEFAULT 0
                        CHECK (replaceability_score >= 0 AND replaceability_score <= 100),
                    replaceability_breakdown JSONB DEFAULT '{}',

                    estimated_monthly_cost_pln NUMERIC DEFAULT 0,
                    potential_savings_monthly_pln NUMERIC DEFAULT 0,

                    automation_roadmap JSONB DEFAULT '[]',
                    unique_value_notes TEXT,

                    confidence NUMERIC DEFAULT 0.5,
                    status TEXT DEFAULT 'draft'
                        CHECK (status IN ('draft', 'analyzed', 'reviewed', 'archived')),
                    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_ewp_person ON employee_work_profiles(person_id);
                CREATE INDEX IF NOT EXISTS idx_ewp_score ON employee_work_profiles(replaceability_score DESC);
                CREATE INDEX IF NOT EXISTS idx_ewp_status ON employee_work_profiles(status);
                CREATE INDEX IF NOT EXISTS idx_ewp_org ON employee_work_profiles(organization);
            """)
            conn.commit()
    _tables_ensured = True


# ---------------------------------------------------------------------------
# Data collection (reuses evaluation.data_collector + extends)
# ---------------------------------------------------------------------------

def _collect_work_signals(person_slug: str, days: int = 90) -> dict[str, Any]:
    """Gather work activity signals for a person. Reuses data_collector + adds process/flow data."""
    from app.evaluation.data_collector import collect_person_data

    # Core data from existing collector
    person_data = collect_person_data(person_slug=person_slug, max_chunks=300, max_events=500)
    if "error" in person_data:
        return person_data

    person = person_data["person"]
    entity_id = person.get("entity_id")

    # Additional signals: calendar patterns
    calendar_data = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if entity_id:
                # Meeting frequency and types
                cur.execute("""
                    SELECT e.event_type, COUNT(*) as cnt,
                           AVG(EXTRACT(EPOCH FROM COALESCE(
                               (e.metadata->>'duration')::interval, INTERVAL '1 hour'
                           )) / 3600) as avg_hours
                    FROM events e
                    JOIN event_entities ee ON ee.event_id = e.id
                    WHERE ee.entity_id = %s
                    AND e.event_time > NOW() - INTERVAL '%s days'
                    GROUP BY e.event_type
                    ORDER BY cnt DESC
                """, (entity_id, days))
                calendar_data["event_types"] = [
                    {"type": r[0], "count": r[1], "avg_hours": round(float(r[2] or 1), 1)}
                    for r in cur.fetchall()
                ]

                # Communication volume (emails sent/received)
                cur.execute("""
                    SELECT s.source_type, COUNT(DISTINCT c.id) as chunk_count
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    JOIN sources s ON s.id = d.source_id
                    JOIN chunk_entities ce ON ce.chunk_id = c.id
                    WHERE ce.entity_id = %s
                    AND d.created_at > NOW() - INTERVAL '%s days'
                    GROUP BY s.source_type
                """, (entity_id, days))
                calendar_data["source_volumes"] = {r[0]: r[1] for r in cur.fetchall()}

    # Process participation
    process_data = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person_name = person.get("name", "")
            cur.execute("""
                SELECT name, process_type, frequency, automation_potential, participants
                FROM discovered_processes
                WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(participants) elem WHERE elem ILIKE %s)
                ORDER BY automation_potential DESC
            """, (f"%{person_name.split()[0] if person_name else '???'}%",))
            process_data = [
                {"name": r[0], "type": r[1], "frequency": r[2],
                 "automation_potential": r[3]}
                for r in cur.fetchall()
            ]

    # Data flow involvement
    flow_data = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT flow_description, channel, frequency, automation_status, bottleneck_risk
                FROM data_flows
                WHERE sender ILIKE %s OR receiver ILIKE %s
                ORDER BY bottleneck_risk DESC NULLS LAST
            """, (f"%{person_name.split()[-1] if person_name else '???'}%",
                  f"%{person_name.split()[-1] if person_name else '???'}%"))
            flow_data = [
                {"description": r[0], "channel": r[1], "frequency": r[2],
                 "automation_status": r[3], "bottleneck_risk": r[4]}
                for r in cur.fetchall()
            ]

    # Commitment patterns
    commitment_data = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT status, COUNT(*) FROM commitments
                    WHERE assignee ILIKE %s
                    AND created_at > NOW() - INTERVAL '%s days'
                    GROUP BY status
                """, (f"%{person_name.split()[-1] if person_name else '???'}%", days))
                commitment_data = {r[0]: r[1] for r in cur.fetchall()}
            except Exception:
                pass

    person_data["calendar"] = calendar_data
    person_data["processes"] = process_data
    person_data["data_flows"] = flow_data
    person_data["commitments"] = commitment_data

    return person_data


# ---------------------------------------------------------------------------
# Work profile analysis
# ---------------------------------------------------------------------------

def analyze_work_profile(person_slug: str, days: int = 90) -> dict[str, Any]:
    """Analyze a person's work profile for automation potential."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)
    log.info("work_profile_analysis_start", person=person_slug, access="ceo_only")

    signals = _collect_work_signals(person_slug, days)
    if "error" in signals:
        return signals

    person = signals["person"]
    stats = signals["stats"]

    # Build context for LLM
    context_parts = [
        f"PRACOWNIK: {person['name']}",
        f"Stanowisko: {person.get('role', '?')}",
        f"Organizacja: {person.get('organization', '?')}",
        f"Okres analizy: ostatnie {days} dni",
        "",
        f"STATYSTYKI: {stats['total_events']} wydarzeń, {stats['total_chunks']} wzmianek",
        f"Typy wydarzeń: {json.dumps(stats['event_type_breakdown'], ensure_ascii=False)}",
        f"Aktywność miesięczna: {json.dumps(stats['monthly_activity'], ensure_ascii=False)}",
    ]

    # Calendar data
    cal = signals.get("calendar", {})
    if cal.get("event_types"):
        context_parts.append(f"\nKALENDARZ (typy zdarzeń): {json.dumps(cal['event_types'], ensure_ascii=False)}")
    if cal.get("source_volumes"):
        context_parts.append(f"Wolumen komunikacji: {json.dumps(cal['source_volumes'], ensure_ascii=False)}")

    # Process involvement
    if signals.get("processes"):
        context_parts.append(f"\nPROCESY (udział): {json.dumps(signals['processes'][:10], ensure_ascii=False)}")

    # Data flows
    if signals.get("data_flows"):
        context_parts.append(f"\nPRZEPŁYWY DANYCH: {json.dumps(signals['data_flows'][:10], ensure_ascii=False)}")

    # Commitments
    if signals.get("commitments"):
        context_parts.append(f"\nZOBOWIĄZANIA (status): {json.dumps(signals['commitments'], ensure_ascii=False)}")

    # Events sample
    context_parts.append("\n=== WYDARZENIA (próbka) ===")
    for ev in signals["events"][:200]:
        context_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    # Chunks sample
    context_parts.append("\n=== KOMUNIKACJA (próbka) ===")
    for ch in signals["chunks"][:80]:
        context_parts.append(f"[{ch['source']}] {ch['date'] or '?'}: {ch['text'][:250]}")

    # Available Gilbertus modules for reference
    context_parts.append("\n=== DOSTĘPNE MODUŁY GILBERTUS/OMNIUS ===")
    context_parts.append(
        "commitment_tracker, meeting_prep, meeting_minutes, smart_response_drafter, "
        "weekly_synthesis, sentiment_tracker, wellbeing_monitor, contract_tracker, "
        "delegation_tracker, blind_spot_detector, network_analyzer, predictive_alerts, "
        "market_intelligence, competitor_intelligence, scenario_analyzer, "
        "decision_intelligence, action_pipeline, calendar_manager, strategic_goals, "
        "financial_framework, cost_estimator, app_inventory, process_mining, "
        "data_flow_mapper, optimization_planner, morning_brief, smart_alerts, "
        "voice_pipeline (STT+TTS), whatsapp_commands"
    )

    context = "\n".join(context_parts)
    if len(context) > 80000:
        context = context[:80000] + "\n\n[...truncated...]"

    # Call Claude Sonnet for analysis
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            temperature=0.1,
            system=[{"type": "text", "text": WORK_PROFILE_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
            tools=[WORK_PROFILE_TOOL],
            tool_choice={"type": "tool", "name": "return_work_profile"},
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "employee_automation", response.usage)
    except Exception as e:
        log.error("work_profile_llm_failed", person=person_slug, error=str(e))
        return {"error": str(e)}

    # Extract profile
    profile = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            profile = block.input.get("profile", block.input)
            break

    if not profile:
        return {"error": "LLM returned no structured profile"}

    # Calculate confidence
    data_score = min(stats["total_events"] / 50, 1.0) * 0.4 + min(stats["total_chunks"] / 100, 1.0) * 0.3
    process_score = min(len(signals.get("processes", [])) / 3, 1.0) * 0.3
    confidence = round(min(data_score + process_score, 0.9), 2)

    # Store profile
    category_hours = profile.get("category_hours", {})
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Upsert: replace existing profile for same person
            cur.execute("""
                INSERT INTO employee_work_profiles (
                    person_id, entity_id, person_name, person_role, organization,
                    analysis_period_from, analysis_period_to,
                    work_activities,
                    routine_hours_weekly, judgment_hours_weekly, relationship_hours_weekly,
                    creative_hours_weekly, supervisory_hours_weekly, total_hours_weekly,
                    automatable_pct, replaceability_score, replaceability_breakdown,
                    estimated_monthly_cost_pln, potential_savings_monthly_pln,
                    automation_roadmap, unique_value_notes,
                    confidence, status, analyzed_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    (NOW() - INTERVAL '%s days')::date, NOW()::date,
                    %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, 'analyzed', NOW(), NOW()
                )
                ON CONFLICT (id) DO NOTHING
            """, (
                person.get("person_id") if "person_id" in person else None,
                person.get("entity_id"),
                person["name"],
                person.get("role"),
                person.get("organization"),
                days,
                json.dumps(profile.get("work_activities", []), ensure_ascii=False, default=str),
                category_hours.get("routine", 0),
                category_hours.get("judgment", 0),
                category_hours.get("relationship", 0),
                category_hours.get("creative", 0),
                category_hours.get("supervisory", 0),
                profile.get("total_hours_weekly", 40),
                profile.get("automatable_pct", 0),
                profile.get("replaceability_score", 0),
                json.dumps(profile.get("replaceability_breakdown", {}), ensure_ascii=False),
                profile.get("estimated_monthly_cost_pln", 0),
                profile.get("potential_savings_monthly_pln", 0),
                json.dumps(profile.get("automation_roadmap", []), ensure_ascii=False, default=str),
                profile.get("unique_value_notes", ""),
                confidence,
            ))

            # Delete old profiles for same person (keep latest)
            cur.execute("""
                DELETE FROM employee_work_profiles
                WHERE person_name = %s AND id NOT IN (
                    SELECT id FROM employee_work_profiles
                    WHERE person_name = %s
                    ORDER BY analyzed_at DESC LIMIT 1
                )
            """, (person["name"], person["name"]))

            conn.commit()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("work_profile_done", person=person_slug,
             replaceability=profile.get("replaceability_score"),
             latency_ms=latency_ms)

    return {
        "person": person,
        "profile": profile,
        "confidence": confidence,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Batch analysis
# ---------------------------------------------------------------------------

def analyze_all_employees(organization: str | None = None) -> dict[str, Any]:
    """Batch analysis for all known employees."""
    _ensure_tables()
    started = datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if organization:
                cur.execute("""
                    SELECT p.slug, p.first_name, p.last_name, r.person_role, r.organization
                    FROM people p
                    JOIN relationships r ON r.person_id = p.id
                    WHERE r.organization ILIKE %s AND r.status = 'active'
                    ORDER BY p.last_name
                """, (f"%{organization}%",))
            else:
                cur.execute("""
                    SELECT p.slug, p.first_name, p.last_name, r.person_role, r.organization
                    FROM people p
                    JOIN relationships r ON r.person_id = p.id
                    WHERE r.status = 'active'
                    ORDER BY p.last_name
                """)
            employees = cur.fetchall()

    results = []
    errors = []
    for slug, first, last, role, org in employees:
        log.info("analyzing_employee", name=f"{first} {last}", slug=slug)
        try:
            result = analyze_work_profile(slug)
            if "error" in result:
                errors.append({"person": f"{first} {last}", "error": result["error"]})
            else:
                results.append({
                    "person": f"{first} {last}",
                    "role": role,
                    "organization": org,
                    "replaceability_score": result["profile"].get("replaceability_score", 0),
                    "automatable_pct": result["profile"].get("automatable_pct", 0),
                    "savings_monthly": result["profile"].get("potential_savings_monthly_pln", 0),
                })
        except Exception as e:
            errors.append({"person": f"{first} {last}", "error": str(e)})

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    log.info("batch_analysis_done", analyzed=len(results), errors=len(errors), latency_ms=latency_ms)

    return {
        "analyzed": len(results),
        "errors": len(errors),
        "results": sorted(results, key=lambda x: -x["replaceability_score"]),
        "error_details": errors,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Reports / Dashboard
# ---------------------------------------------------------------------------

def get_work_profile(person_slug: str) -> dict | None:
    """Retrieve stored work profile for a person."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM employee_work_profiles
                WHERE person_name ILIKE %s
                ORDER BY analyzed_at DESC LIMIT 1
            """, (f"%{person_slug.replace('-', ' ')}%",))
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            if not row:
                return None

            result = dict(zip(cols, row))
            # Parse JSONB
            for field in ["work_activities", "replaceability_breakdown", "automation_roadmap"]:
                val = result.get(field)
                if isinstance(val, str):
                    try:
                        result[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            return result


def get_automation_overview() -> dict:
    """Dashboard: all employees sorted by replaceability, total savings."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT person_name, person_role, organization,
                       replaceability_score, automatable_pct,
                       estimated_monthly_cost_pln, potential_savings_monthly_pln,
                       routine_hours_weekly, judgment_hours_weekly,
                       relationship_hours_weekly, creative_hours_weekly,
                       supervisory_hours_weekly, total_hours_weekly,
                       confidence, status, analyzed_at
                FROM employee_work_profiles
                WHERE status != 'archived'
                ORDER BY replaceability_score DESC
            """)
            cols = [d[0] for d in cur.description]
            profiles = [dict(zip(cols, r)) for r in cur.fetchall()]

    total_monthly_cost = sum(float(p.get("estimated_monthly_cost_pln") or 0) for p in profiles)
    total_savings = sum(float(p.get("potential_savings_monthly_pln") or 0) for p in profiles)
    total_routine = sum(float(p.get("routine_hours_weekly") or 0) for p in profiles)
    total_hours = sum(float(p.get("total_hours_weekly") or 0) for p in profiles)

    return {
        "profiles": profiles,
        "summary": {
            "total_employees": len(profiles),
            "total_monthly_cost_pln": round(total_monthly_cost, 2),
            "total_potential_savings_monthly_pln": round(total_savings, 2),
            "total_potential_savings_yearly_pln": round(total_savings * 12, 2),
            "avg_replaceability_score": round(
                sum(p.get("replaceability_score", 0) for p in profiles) / max(len(profiles), 1), 1
            ),
            "total_routine_hours_weekly": round(total_routine, 1),
            "total_hours_weekly": round(total_hours, 1),
            "routine_pct_of_total": round(total_routine / max(total_hours, 1) * 100, 1),
        },
    }


def get_automation_roadmap() -> dict:
    """Cross-employee roadmap: merge all individual roadmaps, deduplicate modules, sort by ROI."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT person_name, automation_roadmap
                FROM employee_work_profiles
                WHERE status != 'archived' AND automation_roadmap IS NOT NULL
            """)
            rows = cur.fetchall()

    # Merge roadmaps, aggregate by module
    module_map: dict[str, dict] = {}
    for person_name, roadmap_raw in rows:
        roadmap = roadmap_raw if isinstance(roadmap_raw, list) else json.loads(roadmap_raw) if roadmap_raw else []
        for item in roadmap:
            module = item.get("gilbertus_module", item.get("task", "unknown"))
            if module not in module_map:
                module_map[module] = {
                    "module": module,
                    "tasks": [],
                    "affected_employees": [],
                    "total_dev_hours": 0,
                    "total_savings_monthly_pln": 0,
                    "max_priority": 0,
                }
            entry = module_map[module]
            entry["tasks"].append(item.get("task", "?"))
            if person_name not in entry["affected_employees"]:
                entry["affected_employees"].append(person_name)
            # Dev hours: take max (same module, don't multiply)
            entry["total_dev_hours"] = max(entry["total_dev_hours"], item.get("dev_hours", 0))
            # Savings: sum across employees
            entry["total_savings_monthly_pln"] += item.get("savings_monthly_pln", 0)
            entry["max_priority"] = max(entry["max_priority"], item.get("priority", 0))

    # Calculate ROI and sort
    roadmap_items = list(module_map.values())
    for item in roadmap_items:
        dev_cost = item["total_dev_hours"] * 200  # 200 PLN/h
        annual_savings = item["total_savings_monthly_pln"] * 12
        item["roi_ratio"] = round(annual_savings / max(dev_cost, 1), 2)
        item["payback_months"] = round(dev_cost / max(item["total_savings_monthly_pln"], 1), 1)
        item["tasks"] = list(set(item["tasks"]))[:5]  # deduplicate, limit

    roadmap_items.sort(key=lambda x: (-x["roi_ratio"], -x["max_priority"]))

    total_savings = sum(i["total_savings_monthly_pln"] for i in roadmap_items)
    total_dev = sum(i["total_dev_hours"] for i in roadmap_items)

    return {
        "roadmap": roadmap_items,
        "summary": {
            "total_modules": len(roadmap_items),
            "total_dev_hours": total_dev,
            "total_dev_cost_pln": total_dev * 200,
            "total_savings_monthly_pln": round(total_savings, 2),
            "total_savings_yearly_pln": round(total_savings * 12, 2),
            "overall_roi": round((total_savings * 12) / max(total_dev * 200, 1), 2),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "overview"
    if cmd == "analyze" and len(sys.argv) > 2:
        print(json.dumps(analyze_work_profile(sys.argv[2]), ensure_ascii=False, indent=2, default=str))
    elif cmd == "all":
        org = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(analyze_all_employees(org), ensure_ascii=False, indent=2, default=str))
    elif cmd == "overview":
        print(json.dumps(get_automation_overview(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "roadmap":
        print(json.dumps(get_automation_roadmap(), ensure_ascii=False, indent=2, default=str))
    elif cmd == "profile" and len(sys.argv) > 2:
        print(json.dumps(get_work_profile(sys.argv[2]), ensure_ascii=False, indent=2, default=str))
    else:
        print("Usage: python -m app.analysis.employee_automation [analyze <slug>|all [org]|overview|roadmap|profile <slug>]")
