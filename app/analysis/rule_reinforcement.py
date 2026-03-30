"""
Self-Rule Reinforcement — measures and improves extracted rules.

Currently self_rules are append-only: extracted from audio -> saved -> applied.
This module adds:
1. Track when each rule is applied (in morning brief, evaluations, actions)
2. Track outcomes when rule is applied
3. Calculate effectiveness score per rule
4. Detect conflicting rules
5. Flag stale rules (never applied in 30+ days)
6. Suggest rule pruning or modification

Cron: weekly (Sunday 19:00, before weekly synthesis)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

CONFLICT_DETECTION_PROMPT = """You analyze a set of self-rules (principles, instructions, preferences) and find pairs that CONTRADICT each other.

Two rules conflict when following one would violate or prevent following the other.
Do NOT flag rules that are merely different — they must actually be contradictory or mutually exclusive.

Rules:
{rules_json}

Return JSON array of conflicts found:
[{{"rule_a_id": N, "rule_b_id": N, "conflict": "brief explanation of the contradiction in Polish"}}]

If no conflicts found, return [].
Respond ONLY with JSON array."""


_tables_ensured = False
def _ensure_tables() -> None:
    """Ensure rule reinforcement schema exists."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Add tracking columns to self_rules
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS applied_count INT DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS positive_outcomes INT DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS negative_outcomes INT DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS effectiveness NUMERIC(3,2)
            """)
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS last_applied TIMESTAMPTZ
            """)
            cur.execute("""
                ALTER TABLE self_rules ADD COLUMN IF NOT EXISTS conflicts_with BIGINT[]
            """)
            # status column with CHECK constraint — use DO block to avoid duplicate constraint error
            cur.execute("""
                DO $$
                BEGIN
                    ALTER TABLE self_rules ADD COLUMN status TEXT DEFAULT 'active';
                EXCEPTION WHEN duplicate_column THEN
                    NULL;
                END $$
            """)
            cur.execute("""
                DO $$
                BEGIN
                    ALTER TABLE self_rules ADD CONSTRAINT self_rules_status_check
                        CHECK (status IN ('active', 'review', 'stale', 'deprecated'));
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END $$
            """)

            # Rule application log
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rule_applications (
                    id BIGSERIAL PRIMARY KEY,
                    rule_id BIGINT NOT NULL REFERENCES self_rules(id),
                    context TEXT NOT NULL,
                    applied_in TEXT NOT NULL,
                    outcome TEXT,
                    outcome_evidence TEXT,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rule_apps_rule ON rule_applications(rule_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rule_apps_applied ON rule_applications(applied_at)
            """)
        conn.commit()
    log.info("rule_reinforcement.tables_ensured")
    _tables_ensured = True


def log_rule_application(rule_id: int, context: str, applied_in: str) -> int:
    """Log that a rule was applied. Returns application_id.

    Call this whenever a rule is used in morning_brief, evaluation,
    action_decision, opportunity, or draft contexts.
    """
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO rule_applications (rule_id, context, applied_in)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (rule_id, context, applied_in))
            app_id = cur.fetchall()[0][0]

            cur.execute("""
                UPDATE self_rules
                SET applied_count = COALESCE(applied_count, 0) + 1,
                    last_applied = NOW()
                WHERE id = %s
            """, (rule_id,))
        conn.commit()

    log.info("rule_reinforcement.application_logged",
             rule_id=rule_id, applied_in=applied_in, application_id=app_id)
    return app_id


def log_rule_outcome(application_id: int, outcome: str, evidence: str = "") -> None:
    """Log outcome of a rule application and recalculate effectiveness.

    outcome: 'positive', 'negative', 'neutral', 'unknown'
    """
    if outcome not in ("positive", "negative", "neutral", "unknown"):
        log.warning("rule_reinforcement.invalid_outcome", outcome=outcome)
        return

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Update the application record
            cur.execute("""
                UPDATE rule_applications
                SET outcome = %s, outcome_evidence = %s
                WHERE id = %s
                RETURNING rule_id
            """, (outcome, evidence, application_id))
            rows = cur.fetchall()
            if not rows:
                log.warning("rule_reinforcement.application_not_found", application_id=application_id)
                return
            rule_id = rows[0][0]

            # Update outcome counts on self_rules
            if outcome == "positive":
                cur.execute("""
                    UPDATE self_rules
                    SET positive_outcomes = COALESCE(positive_outcomes, 0) + 1
                    WHERE id = %s
                """, (rule_id,))
            elif outcome == "negative":
                cur.execute("""
                    UPDATE self_rules
                    SET negative_outcomes = COALESCE(negative_outcomes, 0) + 1
                    WHERE id = %s
                """, (rule_id,))

            # Recalculate effectiveness
            cur.execute("""
                UPDATE self_rules
                SET effectiveness = CASE
                    WHEN COALESCE(positive_outcomes, 0) + COALESCE(negative_outcomes, 0) = 0 THEN NULL
                    ELSE ROUND(
                        COALESCE(positive_outcomes, 0)::numeric /
                        (COALESCE(positive_outcomes, 0) + COALESCE(negative_outcomes, 0)),
                        2
                    )
                END
                WHERE id = %s
            """, (rule_id,))
        conn.commit()

    log.info("rule_reinforcement.outcome_logged",
             application_id=application_id, rule_id=rule_id, outcome=outcome)


def detect_conflicts() -> list[dict[str, Any]]:
    """Use LLM to find pairs of active rules that contradict each other."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, rule_text, category, importance
                FROM self_rules
                WHERE active = TRUE AND (status IS NULL OR status = 'active')
                ORDER BY id
            """)
            rules = [
                {"id": r[0], "rule_text": r[1], "category": r[2], "importance": r[3]}
                for r in cur.fetchall()
            ]

    if len(rules) < 2:
        log.info("rule_reinforcement.conflict_detection_skipped", reason="less_than_2_rules")
        return []

    prompt = CONFLICT_DETECTION_PROMPT.format(rules_json=json.dumps(rules, ensure_ascii=False, indent=2))

    try:
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=1000,
            temperature=0.1,
            system=[{"type": "text", "text": "You detect contradictions between rules. Respond only with JSON.",
                      "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "analysis.rule_reinforcement", response.usage)

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        conflicts = json.loads(raw)

    except Exception as e:
        log.error("rule_reinforcement.conflict_detection_error", error=str(e))
        return []

    # Update conflicts_with arrays on conflicting rules
    if conflicts:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for conflict in conflicts:
                    a_id = conflict.get("rule_a_id")
                    b_id = conflict.get("rule_b_id")
                    if a_id and b_id:
                        cur.execute("""
                            UPDATE self_rules
                            SET conflicts_with = array_append(
                                COALESCE(conflicts_with, ARRAY[]::BIGINT[]), %s
                            )
                            WHERE id = %s AND NOT (%s = ANY(COALESCE(conflicts_with, ARRAY[]::BIGINT[])))
                        """, (b_id, a_id, b_id))
                        cur.execute("""
                            UPDATE self_rules
                            SET conflicts_with = array_append(
                                COALESCE(conflicts_with, ARRAY[]::BIGINT[]), %s
                            )
                            WHERE id = %s AND NOT (%s = ANY(COALESCE(conflicts_with, ARRAY[]::BIGINT[])))
                        """, (a_id, b_id, a_id))
            conn.commit()

    log.info("rule_reinforcement.conflicts_detected", count=len(conflicts))
    return conflicts


def detect_stale_rules() -> list[dict[str, Any]]:
    """Find active rules that haven't been applied in 30+ days."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, rule_text, category, importance, last_applied, created_at,
                       EXTRACT(EPOCH FROM (NOW() - COALESCE(last_applied, created_at))) / 86400 AS days_inactive
                FROM self_rules
                WHERE active = TRUE
                  AND (status IS NULL OR status = 'active')
                  AND created_at < NOW() - INTERVAL '14 days'
                  AND (last_applied IS NULL OR last_applied < NOW() - INTERVAL '30 days')
                ORDER BY days_inactive DESC
            """)
            stale = []
            for r in cur.fetchall():
                days = round(r[6])
                stale.append({
                    "id": r[0],
                    "rule_text": r[1],
                    "category": r[2],
                    "importance": r[3],
                    "last_applied": str(r[4]) if r[4] else None,
                    "created_at": str(r[5]),
                    "days_since_applied": days,
                    "suggestion": f"Rule #{r[0]} hasn't been applied in {days} days. Consider deprecating.",
                })

            # Mark stale rules
            if stale:
                stale_ids = [s["id"] for s in stale]
                cur.execute("""
                    UPDATE self_rules SET status = 'stale'
                    WHERE id = ANY(%s) AND (status IS NULL OR status = 'active')
                """, (stale_ids,))
                conn.commit()

    log.info("rule_reinforcement.stale_rules_detected", count=len(stale))
    return stale


def detect_ineffective_rules() -> list[dict[str, Any]]:
    """Find rules with enough data but low effectiveness."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, rule_text, category, importance, applied_count,
                       effectiveness, positive_outcomes, negative_outcomes
                FROM self_rules
                WHERE active = TRUE
                  AND (status IS NULL OR status IN ('active', 'stale'))
                  AND COALESCE(applied_count, 0) >= 5
                  AND effectiveness IS NOT NULL
                  AND effectiveness < 0.3
                ORDER BY effectiveness ASC
            """)
            ineffective = []
            for r in cur.fetchall():
                ineffective.append({
                    "id": r[0],
                    "rule_text": r[1],
                    "category": r[2],
                    "importance": r[3],
                    "applied_count": r[4],
                    "effectiveness": float(r[5]),
                    "positive_outcomes": r[6],
                    "negative_outcomes": r[7],
                    "recommendation": f"Rule #{r[0]} has {float(r[5])*100:.0f}% effectiveness over {r[4]} applications. Review or deprecate.",
                })

            # Mark for review
            if ineffective:
                review_ids = [i["id"] for i in ineffective]
                cur.execute("""
                    UPDATE self_rules SET status = 'review'
                    WHERE id = ANY(%s) AND (status IS NULL OR status = 'active')
                """, (review_ids,))
                conn.commit()

    log.info("rule_reinforcement.ineffective_rules_detected", count=len(ineffective))
    return ineffective


def get_rule_effectiveness_report() -> dict[str, Any]:
    """Generate comprehensive rule effectiveness report."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Totals by status
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status IS NULL OR status = 'active') AS active,
                    COUNT(*) FILTER (WHERE status = 'stale') AS stale,
                    COUNT(*) FILTER (WHERE status = 'deprecated') AS deprecated,
                    COUNT(*) FILTER (WHERE status = 'review') AS review,
                    ROUND(AVG(effectiveness) FILTER (WHERE effectiveness IS NOT NULL), 2) AS avg_effectiveness
                FROM self_rules
                WHERE active = TRUE
            """)
            row = cur.fetchone()
            total, active, stale, deprecated, review, avg_eff = row

            # Top rules (highest effectiveness with enough applications)
            cur.execute("""
                SELECT id, rule_text, effectiveness, applied_count
                FROM self_rules
                WHERE active = TRUE
                  AND effectiveness IS NOT NULL
                  AND COALESCE(applied_count, 0) >= 3
                ORDER BY effectiveness DESC, applied_count DESC
                LIMIT 5
            """)
            top_rules = [
                {"id": r[0], "text": r[1], "effectiveness": float(r[2]), "applied": r[3]}
                for r in cur.fetchall()
            ]

            # Worst rules
            cur.execute("""
                SELECT id, rule_text, effectiveness, applied_count
                FROM self_rules
                WHERE active = TRUE
                  AND effectiveness IS NOT NULL
                  AND COALESCE(applied_count, 0) >= 3
                ORDER BY effectiveness ASC, applied_count DESC
                LIMIT 5
            """)
            worst_rules = [
                {"id": r[0], "text": r[1], "effectiveness": float(r[2]), "applied": r[3]}
                for r in cur.fetchall()
            ]

            # Conflicts
            cur.execute("""
                SELECT id, rule_text, conflicts_with
                FROM self_rules
                WHERE active = TRUE
                  AND conflicts_with IS NOT NULL
                  AND array_length(conflicts_with, 1) > 0
            """)
            conflict_rules = {r[0]: {"text": r[1], "conflicts": r[2]} for r in cur.fetchall()}
            conflicts = []
            seen_pairs = set()
            for rule_id, info in conflict_rules.items():
                for other_id in info["conflicts"]:
                    pair = tuple(sorted([rule_id, other_id]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        other_text = conflict_rules.get(other_id, {}).get("text", f"Rule #{other_id}")
                        conflicts.append({
                            "rule_a": f"#{rule_id}: {info['text']}",
                            "rule_b": f"#{other_id}: {other_text}",
                        })

            # Stale rules
            cur.execute("""
                SELECT id, rule_text,
                       EXTRACT(EPOCH FROM (NOW() - COALESCE(last_applied, created_at))) / 86400 AS days
                FROM self_rules
                WHERE active = TRUE AND status = 'stale'
                ORDER BY days DESC
                LIMIT 10
            """)
            stale_rules = [
                {"id": r[0], "text": r[1], "days_since_applied": round(r[2])}
                for r in cur.fetchall()
            ]

    # Build recommendations
    recommendations = []
    for w in worst_rules:
        if w["effectiveness"] < 0.2 and w["applied"] >= 5:
            recommendations.append(
                f"Deprecate rule #{w['id']} (effectiveness {w['effectiveness']*100:.0f}%, applied {w['applied']}x)"
            )
    for s in stale_rules:
        recommendations.append(
            f"Review stale rule #{s['id']} (unused {s['days_since_applied']} days): {s['text'][:60]}..."
        )
    for c in conflicts:
        recommendations.append(f"Resolve conflict: {c['rule_a'][:40]} vs {c['rule_b'][:40]}")

    report = {
        "total_rules": total,
        "active": active,
        "stale": stale,
        "deprecated": deprecated,
        "in_review": review,
        "avg_effectiveness": float(avg_eff) if avg_eff is not None else None,
        "top_rules": top_rules,
        "worst_rules": worst_rules,
        "conflicts": conflicts,
        "stale_rules": stale_rules,
        "recommendations": recommendations,
    }

    log.info("rule_reinforcement.report_generated",
             total=total, active=active, stale=stale, deprecated=deprecated)
    return report


def auto_deprecate_rules(min_applications: int = 10, max_effectiveness: float = 0.15) -> list[dict[str, Any]]:
    """Automatically deprecate clearly ineffective rules.

    Only deprecates rules with enough data (min_applications) and
    very low effectiveness (max_effectiveness).
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, rule_text, effectiveness, applied_count
                FROM self_rules
                WHERE active = TRUE
                  AND COALESCE(applied_count, 0) >= %s
                  AND effectiveness IS NOT NULL
                  AND effectiveness <= %s
                ORDER BY effectiveness ASC
            """, (min_applications, max_effectiveness))
            to_deprecate = [
                {"id": r[0], "rule_text": r[1], "effectiveness": float(r[2]), "applied_count": r[3]}
                for r in cur.fetchall()
            ]

            if to_deprecate:
                dep_ids = [d["id"] for d in to_deprecate]
                cur.execute("""
                    UPDATE self_rules
                    SET status = 'deprecated', active = FALSE
                    WHERE id = ANY(%s)
                """, (dep_ids,))
                conn.commit()

    for d in to_deprecate:
        log.info("rule_reinforcement.auto_deprecated",
                 rule_id=d["id"], effectiveness=d["effectiveness"],
                 applied_count=d["applied_count"])

    log.info("rule_reinforcement.auto_deprecate_complete", count=len(to_deprecate))
    return to_deprecate


def run_rule_reinforcement() -> dict[str, Any]:
    """Main pipeline: detect conflicts, stale, ineffective; auto-deprecate; report."""
    _ensure_tables()

    log.info("rule_reinforcement.pipeline_started")

    # 1. Detect conflicts
    conflicts = detect_conflicts()

    # 2. Detect stale rules
    stale = detect_stale_rules()

    # 3. Detect ineffective rules
    ineffective = detect_ineffective_rules()

    # 4. Auto-deprecate worst rules
    deprecated = auto_deprecate_rules()

    # 5. Generate report
    report = get_rule_effectiveness_report()

    summary = {
        "status": "ok",
        "conflicts_found": len(conflicts),
        "stale_found": len(stale),
        "ineffective_found": len(ineffective),
        "auto_deprecated": len(deprecated),
        "report": report,
    }

    log.info("rule_reinforcement.pipeline_complete",
             conflicts=len(conflicts), stale=len(stale),
             ineffective=len(ineffective), deprecated=len(deprecated))

    return summary


if __name__ == "__main__":
    result = run_rule_reinforcement()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
