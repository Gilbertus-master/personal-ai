"""
Answer Self-Evaluation Gate (Evaluator-Optimizer pattern).

Fast Haiku call that scores an answer on 3 axes:
1. relevance — does it answer the actual question?
2. grounding — is it based on provided sources, not hallucinated?
3. depth — is the detail level appropriate for the question_type?

If score < threshold, returns feedback for regeneration.
"""
from __future__ import annotations

import json
import os

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

log = structlog.get_logger("answer_evaluator")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
EVAL_THRESHOLD = float(os.getenv("ANSWER_EVAL_THRESHOLD", "0.6"))

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)

EVAL_SYSTEM_PROMPT = """Jesteś ewaluatorem odpowiedzi systemu RAG.

Oceń odpowiedź na 3 osiach (każda 0.0-1.0):
- relevance: czy odpowiedź BEZPOŚREDNIO adresuje pytanie użytkownika (nie inny temat)
- grounding: czy odpowiedź brzmi jak oparta na konkretnych źródłach (nie ogólnikowa/hallucynowana)
- depth: czy poziom szczegółowości pasuje do typu pytania

Zwróć WYŁĄCZNIE JSON (bez markdown):
{
  "relevance": 0.0-1.0,
  "grounding": 0.0-1.0,
  "depth": 0.0-1.0,
  "avg_score": 0.0-1.0,
  "feedback": "krótki feedback co poprawić" lub null jeśli ok
}

Bądź surowy ale sprawiedliwy. Jeśli odpowiedź jest dobra, daj wysokie noty."""


class EvalResult:
    __slots__ = ("relevance", "grounding", "depth", "avg_score", "feedback", "should_retry")

    def __init__(self, relevance: float, grounding: float, depth: float,
                 avg_score: float, feedback: str | None, threshold: float):
        self.relevance = relevance
        self.grounding = grounding
        self.depth = depth
        self.avg_score = avg_score
        self.feedback = feedback
        self.should_retry = avg_score < threshold


def evaluate_answer(
    query: str,
    answer: str,
    question_type: str = "retrieval",
) -> EvalResult | None:
    """
    Evaluate an answer with Haiku. Returns EvalResult or None on failure.
    Fail-open: if evaluation fails, returns None (caller should proceed with original answer).
    """
    try:
        from app.db.cost_tracker import check_budget
        budget = check_budget("retrieval.answer_evaluator")
        if not budget["ok"]:
            log.warning("eval_budget_exceeded", reason=budget["reason"])
            return None

        user_prompt = (
            f"Pytanie użytkownika: {query}\n"
            f"Typ pytania: {question_type}\n\n"
            f"Odpowiedź do oceny:\n{answer[:2000]}"
        )

        response = client.messages.create(
            model=ANTHROPIC_FAST_MODEL,
            max_tokens=200,
            temperature=0,
            system=[{"type": "text", "text": EVAL_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )

        from app.db.cost_tracker import log_anthropic_cost
        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST_MODEL, "retrieval.answer_evaluator", response.usage)

        raw = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw += block.text

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)

        return EvalResult(
            relevance=float(data.get("relevance", 0.5)),
            grounding=float(data.get("grounding", 0.5)),
            depth=float(data.get("depth", 0.5)),
            avg_score=float(data.get("avg_score", 0.5)),
            feedback=data.get("feedback"),
            threshold=EVAL_THRESHOLD,
        )

    except Exception as e:
        log.warning("evaluation_failed", error=str(e))
        return None
