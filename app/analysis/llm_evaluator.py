"""
LLM Evaluator — framework for evaluating self-hosted LLM candidates.

Tests LLM models on Gilbertus-specific tasks:
1. Entity extraction quality (vs Claude Haiku baseline)
2. Event extraction quality
3. Polish language understanding
4. JSON output reliability
5. Latency and cost comparison

Usage:
    python -m app.analysis.llm_evaluator --model ollama/mistral
    python -m app.analysis.llm_evaluator --model anthropic/claude-haiku-4-5 --baseline
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
import os
import time
from typing import Any

from app.db.postgres import get_pg_connection

# ================================================================
# Test cases — representative Gilbertus tasks
# ================================================================

EVAL_CASES = [
    {
        "id": "entity_extraction",
        "name": "Entity extraction from email",
        "prompt": """Extract entities from this email. Return JSON array:
[{"name": "...", "type": "person|company|product|location|concept"}]

Email: "Cześć Sebastian, rozmawiałem z Markiem z Taurona o kontrakcie PPA na farmę wiatrową w Darłowie.
Spotkanie z URE w piątek o 10:00 w Warszawie. Enea przesłała nową ofertę - 350 PLN/MWh na BASE Q2 2026."
""",
        "expected_entities": ["Sebastian", "Marek", "Tauron", "Darłowo", "URE", "Warszawa", "Enea"],
        "eval_fn": "entity_recall",
    },
    {
        "id": "event_extraction",
        "name": "Event extraction from conversation",
        "prompt": """Extract events from this conversation. Return JSON array:
[{"event_type": "...", "summary": "...", "entities": ["..."]}]
Types: decision, commitment, meeting, trade, conflict, deadline

Text: "Zdecydowaliśmy z Krystianem że podniesiemy cenę ON o 5 gr/l od poniedziałku.
Roch obiecał dostarczyć raport do piątku. Spotkanie z audytorami przesunięte na 15 kwietnia."
""",
        "expected_events": 3,
        "eval_fn": "event_count",
    },
    {
        "id": "json_reliability",
        "name": "JSON output reliability",
        "prompt": """Analyze this market news. Respond ONLY with JSON:
{"insight_type": "regulation|price_change|trend", "title": "max 80 chars", "relevance_score": 0-100}

News: "URE zatwierdziło nową taryfę za energię dla gospodarstw domowych — wzrost o 12% od lipca 2026.
Taryfa G11 z 0.72 na 0.81 PLN/kWh."
""",
        "expected_keys": ["insight_type", "title", "relevance_score"],
        "eval_fn": "json_keys",
    },
    {
        "id": "polish_understanding",
        "name": "Polish business context",
        "prompt": """Odpowiedz po polsku w 2-3 zdaniach: Jakie ryzyko niesie dla tradera energetycznego
wzrost cen gazu na TGE o 15% w ciągu tygodnia, przy jednoczesnym spadku produkcji z farm wiatrowych?""",
        "eval_fn": "polish_quality",
    },
    {
        "id": "summarization",
        "name": "Meeting summary",
        "prompt": """Podsumuj spotkanie w 3 punktach (po polsku):

"Sebastian: Musimy zamknąć pozycję na BASE Q2 przed końcem tygodnia, rynek idzie w dół.
Marek: Mamy 50 MW otwartych, mogę zacząć jutro rano. Ale spread jest ciasny.
Sebastian: Zrób to w 3 transzach po ~15-17 MW. Pierwszą jutro przed 10.
Krystian: A co z REF? Mamy 200 ton ON do kupienia.
Sebastian: Poczekaj do środy, ceny powinny spaść po raporcie IEA."
""",
        "expected_points": 3,
        "eval_fn": "summary_quality",
    },
]


# ================================================================
# Evaluation functions
# ================================================================

def _eval_entity_recall(response: str, case: dict) -> dict:
    """Check how many expected entities were found."""
    expected = case.get("expected_entities", [])
    found = sum(1 for e in expected if e.lower() in response.lower())
    return {"score": found / len(expected) if expected else 0, "found": found, "total": len(expected)}


def _eval_event_count(response: str, case: dict) -> dict:
    """Check if correct number of events extracted."""
    try:
        events = json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())
        return {"score": 1.0 if len(events) == case["expected_events"] else len(events) / case["expected_events"],
                "extracted": len(events), "expected": case["expected_events"]}
    except Exception:
        return {"score": 0, "error": "JSON parse failed"}


def _eval_json_keys(response: str, case: dict) -> dict:
    """Check if response is valid JSON with expected keys."""
    try:
        clean = response.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(clean)
        expected = case.get("expected_keys", [])
        found = sum(1 for k in expected if k in data)
        return {"score": found / len(expected) if expected else 0, "found_keys": found, "total_keys": len(expected)}
    except Exception:
        return {"score": 0, "error": "JSON parse failed"}


def _eval_polish_quality(response: str, case: dict) -> dict:
    """Basic check: response is in Polish and has substance."""
    polish_words = ["ryzyko", "wzrost", "spadek", "cena", "gaz", "energi", "farm", "wiatr", "trad"]
    found = sum(1 for w in polish_words if w in response.lower())
    has_length = len(response) > 50
    return {"score": min(1.0, found / 4) if has_length else 0, "polish_terms": found, "length": len(response)}


def _eval_summary_quality(response: str, case: dict) -> dict:
    """Check summary has expected number of points."""
    lines = [line.strip() for line in response.split("\n") if line.strip() and (line.strip().startswith(("-", "•", "1", "2", "3")))]
    expected = case.get("expected_points", 3)
    return {"score": min(1.0, len(lines) / expected), "points_found": len(lines), "expected": expected}


EVAL_FNS = {
    "entity_recall": _eval_entity_recall,
    "event_count": _eval_event_count,
    "json_keys": _eval_json_keys,
    "polish_quality": _eval_polish_quality,
    "summary_quality": _eval_summary_quality,
}


# ================================================================
# Schema
# ================================================================

def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS llm_evaluations (
                    id BIGSERIAL PRIMARY KEY,
                    model TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    case_name TEXT,
                    score NUMERIC(4,3),
                    details JSONB,
                    latency_ms INTEGER,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_llm_eval_model
                    ON llm_evaluations(model);
            """)
            conn.commit()


# ================================================================
# Runner
# ================================================================

def evaluate_model(model: str, provider: str = "anthropic") -> dict[str, Any]:
    """Run all eval cases against a model and store results."""
    _ensure_tables()
    results = []

    for case in EVAL_CASES:
        started = time.time()

        if provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)
            resp = client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=0.1,
                messages=[{"role": "user", "content": case["prompt"]}],
            )
            response_text = resp.content[0].text
            tokens_in = resp.usage.input_tokens
            tokens_out = resp.usage.output_tokens

            from app.db.cost_tracker import log_anthropic_cost
            log_anthropic_cost(model, "llm_evaluator", resp.usage)
        else:
            # Placeholder for ollama/local models
            response_text = "[Not implemented for provider: " + provider + "]"
            tokens_in = tokens_out = 0

        latency = int((time.time() - started) * 1000)

        # Evaluate
        eval_fn = EVAL_FNS.get(case.get("eval_fn", ""), lambda r, c: {"score": 0})
        eval_result = eval_fn(response_text, case)

        result = {
            "case_id": case["id"],
            "case_name": case["name"],
            "score": eval_result.get("score", 0),
            "details": eval_result,
            "latency_ms": latency,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        results.append(result)

        # Store
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO llm_evaluations (model, case_id, case_name, score, details, latency_ms, tokens_in, tokens_out)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (model, case["id"], case["name"], eval_result.get("score", 0),
                     json.dumps(eval_result), latency, tokens_in, tokens_out),
                )
                conn.commit()

        log.info("llm_eval", model=model, case=case["id"], score=eval_result.get("score", 0), latency_ms=latency)

    # Summary
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0
    total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in results)

    return {
        "model": model,
        "avg_score": round(avg_score, 3),
        "avg_latency_ms": int(avg_latency),
        "total_tokens": total_tokens,
        "cases": results,
    }


def compare_models() -> dict[str, Any]:
    """Compare all evaluated models."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT model,
                       ROUND(AVG(score)::numeric, 3) as avg_score,
                       ROUND(AVG(latency_ms)::numeric) as avg_latency,
                       COUNT(*) as evals,
                       MAX(created_at) as last_eval
                FROM llm_evaluations
                GROUP BY model
                ORDER BY avg_score DESC
            """)
            return {
                "models": [
                    {"model": r[0], "avg_score": float(r[1]), "avg_latency_ms": int(r[2]),
                     "evaluations": r[3], "last_eval": str(r[4])}
                    for r in cur.fetchall()
                ]
            }
