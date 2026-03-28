"""
Risk Assessor — ocena ryzyk compliance z matrycą 5×5.

Likelihood: very_low(1), low(2), medium(3), high(4), very_high(5)
Impact: negligible(1), minor(2), moderate(3), major(4), catastrophic(5)
Risk score = likelihood × impact / 25 (normalized 0-1)

Kolory: 0-0.2 green, 0.2-0.4 yellow, 0.4-0.6 orange, 0.6-0.8 red, 0.8-1.0 critical
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
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

LIKELIHOOD_MAP = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
IMPACT_MAP = {"negligible": 1, "minor": 2, "moderate": 3, "major": 4, "catastrophic": 5}

RISK_COLOR_MAP = [
    (0.2, "green"),
    (0.4, "yellow"),
    (0.6, "orange"),
    (0.8, "red"),
    (1.0, "critical"),
]


def _risk_color(score: float) -> str:
    """Return color label for risk score."""
    for threshold, color in RISK_COLOR_MAP:
        if score <= threshold:
            return color
    return "critical"


def assess_risk_for_matter(matter_id: int) -> list[dict[str, Any]]:
    """AI-powered risk assessment dla sprawy compliance.

    1. Pobierz matter detail (title, description, legal_analysis, area)
    2. Wywołaj Claude Sonnet z promptem identyfikacji ryzyk
    3. Oblicz risk_score = LIKELIHOOD_MAP[l] * IMPACT_MAP[i] / 25.0
    4. INSERT INTO compliance_risk_assessments
    5. Zaktualizuj matter.risk_analysis (JSONB) z summary

    Zwraca listę stworzonych risk assessments.
    """
    # 1. Fetch matter detail
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.title, cm.description, cm.legal_analysis,
                       ca.code as area_code, ca.name_pl as area_name, cm.area_id
                FROM compliance_matters cm
                LEFT JOIN compliance_areas ca ON ca.id = cm.area_id
                WHERE cm.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return [{"error": "matter_not_found", "matter_id": matter_id}]

    m_id, title, description, legal_analysis, area_code, area_name, area_id = row

    context_parts = [f"Tytuł: {title}"]
    if description:
        context_parts.append(f"Opis: {description}")
    if legal_analysis:
        context_parts.append(f"Analiza prawna:\n{legal_analysis[:3000]}")
    context = "\n\n".join(context_parts)

    # 2. AI risk identification
    prompt = (
        "Jesteś ekspertem od ryzyk prawnych w polskiej spółce energetycznej (trading energetyczny, "
        "koncesje URE, CSRD/ESG, AML, RODO).\n\n"
        f"Obszar compliance: {area_name or area_code or 'ogólny'}\n\n"
        f"SPRAWA:\n{context}\n\n"
        "Zidentyfikuj 3-7 ryzyk compliance związanych z tą sprawą. "
        "Dla każdego ryzyka podaj:\n"
        '- risk_title: krótki tytuł\n'
        '- risk_description: opis ryzyka (2-3 zdania)\n'
        '- likelihood: very_low | low | medium | high | very_high\n'
        '- impact: negligible | minor | moderate | major | catastrophic\n'
        '- current_controls: jakie kontrole mogą istnieć (1 zdanie)\n'
        '- mitigation_plan: co zrobić żeby zminimalizować ryzyko (1-2 zdania)\n\n'
        "Zwróć WYŁĄCZNIE JSON array (bez markdown):\n"
        '[{"risk_title": "...", "risk_description": "...", "likelihood": "...", '
        '"impact": "...", "current_controls": "...", "mitigation_plan": "..."}]'
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "risk_assessor", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        risks = json.loads(raw)
    except (json.JSONDecodeError, IndexError) as e:
        log.error("risk_assessor_parse_error", error=str(e), matter_id=matter_id)
        return [{"error": "ai_parse_error", "detail": str(e)}]
    except Exception as e:
        log.error("risk_assessor_ai_error", error=str(e), matter_id=matter_id)
        return [{"error": "ai_error", "detail": str(e)}]

    if not isinstance(risks, list):
        return [{"error": "unexpected_ai_response"}]

    # 3-4. Calculate scores and insert
    created = []
    now = datetime.now(timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for risk in risks:
                likelihood = risk.get("likelihood", "medium")
                impact = risk.get("impact", "moderate")

                l_val = LIKELIHOOD_MAP.get(likelihood, 3)
                i_val = IMPACT_MAP.get(impact, 3)
                risk_score = round(l_val * i_val / 25.0, 2)

                cur.execute("""
                    INSERT INTO compliance_risk_assessments
                        (area_id, matter_id, risk_title, risk_description,
                         likelihood, impact, risk_score,
                         current_controls, mitigation_plan,
                         status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s)
                    RETURNING id
                """, (
                    area_id, matter_id,
                    risk.get("risk_title", "Ryzyko"),
                    risk.get("risk_description", ""),
                    likelihood, impact, risk_score,
                    risk.get("current_controls", ""),
                    risk.get("mitigation_plan", ""),
                    now, now,
                ))
                risk_id = cur.fetchone()[0]

                created.append({
                    "id": risk_id,
                    "risk_title": risk.get("risk_title"),
                    "likelihood": likelihood,
                    "impact": impact,
                    "risk_score": risk_score,
                    "color": _risk_color(risk_score),
                    "mitigation_plan": risk.get("mitigation_plan"),
                })

            # 5. Update matter.risk_analysis with summary
            risk_summary = {
                "assessed_at": now.isoformat(),
                "total_risks": len(created),
                "max_score": max((r["risk_score"] for r in created), default=0),
                "avg_score": round(sum(r["risk_score"] for r in created) / len(created), 2) if created else 0,
                "critical_count": sum(1 for r in created if r["risk_score"] >= 0.8),
                "high_count": sum(1 for r in created if 0.6 <= r["risk_score"] < 0.8),
                "risks": [
                    {"id": r["id"], "title": r["risk_title"],
                     "score": r["risk_score"], "color": r["color"]}
                    for r in created
                ],
            }

            cur.execute(
                "UPDATE compliance_matters SET risk_analysis = %s, updated_at = %s WHERE id = %s",
                (json.dumps(risk_summary, default=str), now, matter_id),
            )
        conn.commit()

    log.info("risk_assessment_completed",
             matter_id=matter_id, risks_created=len(created))
    return created


def get_risk_heatmap() -> dict[str, Any]:
    """Agreguj ryzyka per area_code. Zwraca:
    {areas: [{code, name, risk_count, avg_score, max_score, critical_count}],
     total_risks: N, overall_avg: 0.XX}
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ca.code, ca.name_pl,
                       COUNT(cr.id) as risk_count,
                       COALESCE(AVG(cr.risk_score), 0) as avg_score,
                       COALESCE(MAX(cr.risk_score), 0) as max_score,
                       COUNT(cr.id) FILTER (WHERE cr.risk_score >= 0.8) as critical_count
                FROM compliance_areas ca
                LEFT JOIN compliance_risk_assessments cr
                    ON cr.area_id = ca.id AND cr.status = 'open'
                GROUP BY ca.code, ca.name_pl
                ORDER BY max_score DESC, avg_score DESC
            """)
            areas = [
                {
                    "code": r[0], "name": r[1], "risk_count": r[2],
                    "avg_score": round(float(r[3]), 2),
                    "max_score": round(float(r[4]), 2),
                    "critical_count": r[5],
                    "color": _risk_color(float(r[4])),
                }
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT COUNT(*), COALESCE(AVG(risk_score), 0)
                FROM compliance_risk_assessments
                WHERE status = 'open'
            """)
            total_row = cur.fetchone()

    return {
        "areas": areas,
        "total_risks": total_row[0],
        "overall_avg": round(float(total_row[1]), 2),
    }


def list_risks(
    area_code: str | None = None,
    status: str = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista ryzyk z filtrami."""
    conditions = ["cr.status = %s"]
    params: list[Any] = [status]

    if area_code:
        conditions.append("ca.code = %s")
        params.append(area_code.upper())

    where = "WHERE " + " AND ".join(conditions)
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT cr.id, cr.risk_title, cr.risk_description,
                       cr.likelihood, cr.impact, cr.risk_score,
                       cr.current_controls, cr.mitigation_plan,
                       cr.status, cr.matter_id,
                       ca.code as area_code, ca.name_pl as area_name,
                       cm.title as matter_title,
                       cr.created_at
                FROM compliance_risk_assessments cr
                LEFT JOIN compliance_areas ca ON ca.id = cr.area_id
                LEFT JOIN compliance_matters cm ON cm.id = cr.matter_id
                {where}
                ORDER BY cr.risk_score DESC NULLS LAST
                LIMIT %s
            """, params)
            return [
                {
                    "id": r[0], "risk_title": r[1], "risk_description": r[2],
                    "likelihood": r[3], "impact": r[4],
                    "risk_score": round(float(r[5]), 2) if r[5] else None,
                    "color": _risk_color(float(r[5])) if r[5] else "green",
                    "current_controls": r[6], "mitigation_plan": r[7],
                    "status": r[8], "matter_id": r[9],
                    "area_code": r[10], "area_name": r[11],
                    "matter_title": r[12],
                    "created_at": str(r[13]),
                }
                for r in cur.fetchall()
            ]
