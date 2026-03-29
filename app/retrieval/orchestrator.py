"""
Sub-Question Decomposition (Orchestrator-Workers pattern).

For complex multi-entity/multi-topic queries with analysis_depth=high,
decomposes into 2-4 sub-questions, retrieves+answers each independently,
then synthesizes into a single comprehensive response.

Example:
  "Porównaj podejście Rocha i Krystiana do sprzedaży" →
  Sub-Q1: "podejście Rocha do sprzedaży"
  Sub-Q2: "podejście Krystiana do sprzedaży"
  → Final synthesis comparing both
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.retrieval.answering import answer_question
from app.retrieval.retriever import search_chunks

load_dotenv()

log = structlog.get_logger("orchestrator")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)


def decompose_and_synthesize(
    query: str,
    sub_questions: list[str],
    *,
    source_types: list[str] | None = None,
    source_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    question_type: str = "analysis",
    analysis_depth: str = "high",
    answer_length: str | None = "long",
    conversation_context: str = "",
) -> str:
    """
    Run sub-questions through retrieve+answer in parallel,
    then synthesize all sub-answers into one coherent response.
    """
    from app.db.cost_tracker import check_budget
    budget = check_budget("retrieval.answering")
    if not budget["ok"]:
        log.warning("orchestrator_budget_exceeded", reason=budget["reason"])
        return f"⚠️ Budget przekroczony — orchestrator wstrzymany. {budget['reason']}"

    sub_answers = {}

    def _process_sub_question(sq: str) -> tuple[str, str]:
        matches = search_chunks(
            query=sq,
            top_k=10,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
            prefetch_k=30,
            question_type=question_type,
        )
        if not matches:
            return sq, f"Brak wyników dla: {sq}"

        from app.retrieval.postprocess import cleanup_matches, redact_matches
        cleaned, _ = cleanup_matches(matches, normalized_query=sq, top_k=8, max_per_document=2, min_score=None)
        redacted, _ = redact_matches(cleaned)

        answer = answer_question(
            query=sq,
            matches=redacted,
            question_type=question_type,
            analysis_depth=analysis_depth,
            answer_length="medium",
            allow_quotes=True,
        )
        return sq, answer

    # Fan-out: parallel sub-question processing
    with ThreadPoolExecutor(max_workers=min(4, len(sub_questions))) as executor:
        futures = {executor.submit(_process_sub_question, sq): sq for sq in sub_questions}
        for future in as_completed(futures):
            try:
                sq, answer = future.result()
                sub_answers[sq] = answer
            except Exception as e:
                sq = futures[future]
                log.warning("sub_question_failed", question=sq[:80], error=str(e))
                sub_answers[sq] = f"[błąd przetwarzania: {e}]"

    log.info("orchestrator_complete",
             sub_questions=len(sub_questions),
             sub_answers=len(sub_answers))

    # Synthesis: combine sub-answers into one coherent response
    return _synthesize(query, sub_answers, conversation_context, answer_length)


def _synthesize(
    original_query: str,
    sub_answers: dict[str, str],
    conversation_context: str,
    answer_length: str | None,
) -> str:
    """Synthesize sub-answers into a single comprehensive response."""
    sub_sections = []
    for sq, answer in sub_answers.items():
        sub_sections.append(f"### Sub-pytanie: {sq}\n{answer}")

    sub_content = "\n\n---\n\n".join(sub_sections)

    conv_section = ""
    if conversation_context:
        conv_section = f"\n{conversation_context}\n"

    user_prompt = f"""Oryginalne pytanie użytkownika:
{original_query}
{conv_section}
Poniżej odpowiedzi na rozbite sub-pytania. Zsyntetyzuj je w JEDNĄ spójną,
wyczerpującą odpowiedź na oryginalne pytanie. Nie powtarzaj się.
Porównuj, kontrastuj, wyciągaj wnioski.

{sub_content}"""

    max_tokens_map = {"short": 800, "medium": 1500, "long": 3000}
    max_tokens = max_tokens_map.get(answer_length or "long", 3000)

    _SYSTEM = (
        "Jesteś analitykiem Gilbertus. Syntetyzujesz wiele sub-odpowiedzi "
        "w jedną spójną całość. Pisz po polsku, konkretnie, z wnioskami."
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=0.2,
            system=[
                {"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )

        from app.db.cost_tracker import log_anthropic_cost
        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "retrieval.orchestrator", response.usage)
            log.info("cache_stats",
                     cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                     cache_read=getattr(response.usage, "cache_read_input_tokens", 0))

        return "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()

    except Exception as e:
        log.error("synthesis_failed", error=str(e))
        # Fallback: return sub-answers concatenated
        return f"## Odpowiedzi cząstkowe\n\n{sub_content}"
