"""
Auto-Action Proposals — Gilbertus proactively proposes actions based on signals.

Triggers:
- Market alert (relevance >= 85) → email/meeting proposal
- Competitor signal (high) → scenario trigger
- Goal at_risk → delegation proposal
- Overdue commitment → reminder proposal

All proposals go through approval pipeline — Sebastian approves via WhatsApp.

Cron: */30 8-20 * * * (every 30 min during business hours)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection
from app.orchestrator.action_confidence import score_signal_confidence


def _propose_action(action_type: str, description: str, params: dict) -> int | None:
    """Create action proposal for Sebastian's approval."""
    try:
        from app.orchestrator.action_pipeline import propose_action
        return propose_action(action_type=action_type, description=description, draft_params=params)
    except Exception as e:
        log.warning("propose_action_failed", error=str(e))
        return None


def check_market_triggers() -> list[dict[str, Any]]:
    """High-relevance market insights → action proposals."""
    proposals = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Market insights with relevance >= 85, not yet acted on
            cur.execute("""
                SELECT mi.id, mi.title, mi.impact_assessment, mi.relevance_score, mi.insight_type
                FROM market_insights mi
                WHERE mi.relevance_score >= 85
                AND mi.created_at > NOW() - INTERVAL '24 hours'
                AND NOT EXISTS (
                    SELECT 1 FROM action_proposals ap
                    WHERE ap.source_ref = 'market_insight:' || mi.id::text
                    AND ap.created_at > NOW() - INTERVAL '48 hours'
                )
                ORDER BY mi.relevance_score DESC LIMIT 3
            """)
            for r in cur.fetchall():
                mid, title, impact, relevance, itype = r
                confidence = score_signal_confidence("market_insight", {
                    "relevance_score": relevance, "action_type": "create_ticket",
                    "severity": "high" if relevance >= 90 else "medium",
                })
                if confidence["confidence"] < 0.3:
                    log.info("auto_actions.market_skip_low_confidence",
                             insight_id=mid, confidence=confidence["confidence"])
                    continue
                if itype == "regulation":
                    desc = f"Nowa regulacja: {title}. {impact}. Sugeruję sprawdzić wpływ na kontrakty."
                    action_type = "send_email"
                    params = {"subject": f"[Gilbertus] Regulacja: {title}", "body": desc,
                              "to": "sebastian@respect.energy", "source_ref": f"market_insight:{mid}"}
                elif itype == "price_change":
                    desc = f"Zmiana cenowa: {title}. {impact}. Rozważ korektę pozycji."
                    action_type = "create_ticket"
                    params = {"title": f"Trading alert: {title}", "description": desc,
                              "source_ref": f"market_insight:{mid}"}
                else:
                    desc = f"Market signal: {title} (relevance {relevance}). {impact}"
                    action_type = "create_ticket"
                    params = {"title": title, "description": desc,
                              "source_ref": f"market_insight:{mid}"}

                aid = _propose_action(action_type, desc, params)
                if aid:
                    proposals.append({"source": "market", "insight_id": mid, "action_id": aid, "title": title})

    return proposals


def check_competitor_triggers() -> list[dict[str, Any]]:
    """High-severity competitor signals ��� scenario proposals."""
    proposals = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cs.id, c.name, cs.title, cs.description
                FROM competitor_signals cs
                JOIN competitors c ON c.id = cs.competitor_id
                WHERE cs.severity = 'high'
                AND cs.created_at > NOW() - INTERVAL '48 hours'
                AND NOT EXISTS (
                    SELECT 1 FROM scenarios s
                    WHERE s.trigger_event = 'competitor_signal:' || cs.id::text
                )
                LIMIT 3
            """)
            for r in cur.fetchall():
                sid, comp_name, title, description = r
                confidence = score_signal_confidence("competitor_signal", {
                    "severity": "high", "action_type": "create_ticket",
                })
                if confidence["confidence"] < 0.3:
                    log.info("auto_actions.competitor_skip_low_confidence",
                             signal_id=sid, confidence=confidence["confidence"])
                    continue
                from app.analysis.scenario_analyzer import create_scenario, analyze_scenario
                scenario = create_scenario(
                    title=f"[Auto] {comp_name}: {title[:60]}",
                    description=f"Sygnał konkurencyjny: {description[:300]}",
                    scenario_type="risk",
                    trigger_event=f"competitor_signal:{sid}",
                    created_by="auto_actions",
                )
                analyze_scenario(scenario["id"])
                proposals.append({"source": "competitor", "signal_id": sid,
                                  "scenario_id": scenario["id"], "competitor": comp_name})

    return proposals


def check_goal_triggers() -> list[dict[str, Any]]:
    """At-risk goals → delegation proposals."""
    proposals = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, company, status, deadline
                FROM strategic_goals
                WHERE status IN ('at_risk', 'behind')
                AND deadline IS NOT NULL AND deadline < NOW() + INTERVAL '30 days'
            """)
            for r in cur.fetchall():
                gid, title, company, status, deadline = r
                confidence = score_signal_confidence("goal_at_risk", {
                    "severity": "high" if status == "behind" else "medium",
                    "action_type": "create_ticket",
                })
                if confidence["confidence"] < 0.3:
                    log.info("auto_actions.goal_skip_low_confidence",
                             goal_id=gid, confidence=confidence["confidence"])
                    continue
                desc = f"Cel '{title}' ({company}) jest {status}. Deadline: {deadline}. Sugeruję delegację sprawdzenia statusu."
                aid = _propose_action("create_ticket", desc, {
                    "title": f"Goal at risk: {title}",
                    "description": desc,
                    "source_ref": f"goal:{gid}",
                })
                if aid:
                    proposals.append({"source": "goal", "goal_id": gid, "action_id": aid, "title": title})

    return proposals


def check_commitment_triggers() -> list[dict[str, Any]]:
    """Overdue commitments → reminder proposals."""
    proposals = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, person_name, description, due_date
                    FROM commitments
                    WHERE status = 'open' AND due_date < NOW()
                    AND NOT EXISTS (
                        SELECT 1 FROM action_proposals ap
                        WHERE ap.source_ref = 'commitment:' || commitments.id::text
                        AND ap.created_at > NOW() - INTERVAL '7 days'
                    )
                    LIMIT 5
                """)
                for r in cur.fetchall():
                    cid, person, desc_text, due = r
                    confidence = score_signal_confidence("overdue_commitment", {
                        "action_type": "send_whatsapp", "recipient": person or "",
                    })
                    if confidence["confidence"] < 0.3:
                        log.info("auto_actions.commitment_skip_low_confidence",
                                 commitment_id=cid, confidence=confidence["confidence"])
                        continue
                    desc = f"Przeterminowane zobowiązanie: {person} miał(a) '{desc_text}' do {due}."
                    aid = _propose_action("send_whatsapp", desc, {
                        "target": person,
                        "message": f"Przypomnienie: {desc_text} (termin: {due})",
                        "source_ref": f"commitment:{cid}",
                    })
                    if aid:
                        proposals.append({"source": "commitment", "id": cid, "person": person})
    except Exception:
        pass  # Commitments table may be empty

    return proposals


def run_auto_actions() -> dict[str, Any]:
    """Main pipeline: check all triggers, generate proposals."""
    started = datetime.now(tz=timezone.utc)

    market_proposals = check_market_triggers()
    competitor_proposals = check_competitor_triggers()
    goal_proposals = check_goal_triggers()
    commitment_proposals = check_commitment_triggers()

    total = len(market_proposals) + len(competitor_proposals) + len(goal_proposals) + len(commitment_proposals)
    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)

    log.info("auto_actions_done", total=total, market=len(market_proposals),
             competitor=len(competitor_proposals), goal=len(goal_proposals),
             commitment=len(commitment_proposals), latency_ms=latency_ms)

    return {
        "total_proposals": total,
        "market": market_proposals,
        "competitor": competitor_proposals,
        "goal": goal_proposals,
        "commitment": commitment_proposals,
        "latency_ms": latency_ms,
    }
