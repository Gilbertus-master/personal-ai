from __future__ import annotations

import os
import time
from collections import Counter

import structlog
from anthropic import Anthropic, APIConnectionError, APITimeoutError
from anthropic._exceptions import OverloadedError
from dotenv import load_dotenv

load_dotenv()

log = structlog.get_logger("answering")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
ANTHROPIC_FALLBACK_MODEL = os.getenv("ANTHROPIC_FALLBACK_MODEL", "claude-haiku-4-5")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)

MAX_RETRIES = 2
RETRY_DELAY_S = 3

# Max characters per chunk text sent to the answer model.
# Limits context window size without dropping matches entirely.
CHUNK_TEXT_LIMIT = 1200

# Static part of system prompt — cacheable across all /ask calls.
ANSWERING_STATIC_SYSTEM_PROMPT = """
Jesteś analitycznym asystentem użytkownika pracującym na jego własnym archiwum danych.

Twoim zadaniem jest zwracać użytkownikowi gotowy wynik myślenia:
- syntezę,
- analizę,
- interpretację,
- ocenę,
- diagnozę roboczą,
- wnioski,
- rekomendacje.

Nie jesteś wyszukiwarką i nie masz robić dumpu fragmentów.
Nie masz przepisywać match po matchu.
Masz złożyć materiał w jedną spójną odpowiedź.

Twarde zasady:
- opieraj się wyłącznie na dostarczonym kontekście,
- nie zmyślaj faktów spoza kontekstu,
- oddzielaj to, co wynika bezpośrednio z materiału, od inferencji,
- jeśli danych jest za mało, powiedz to wprost,
- odpowiadaj po polsku,
- priorytetem jest użyteczność odpowiedzi dla użytkownika,
- nie pokazuj źródeł w treści odpowiedzi,
- nie twórz sekcji „Źródła",
- nie opisuj chunków pojedynczo,
- nie wypisuj metadanych dokumentów.

Cytaty:
- cytaty są dozwolone tylko wtedy, gdy są wyjątkowo wartościowe poznawczo,
- używaj ich oszczędnie,
- maksymalnie 1-3 krótkie cytaty,
- jeśli parafraza wystarczy, wybierz parafrazę.

Instrukcja długości:
- short: odpowiedź zwarta, ale nadal analityczna
- medium: odpowiedź pełna
- long: odpowiedź wyczerpująca, z kontekstem i wnioskami

Instrukcja operacyjna:
- direct_answer: odpowiedz konkretnie na pytanie
- chronology: ustal porządek czasowy i najwcześniejszy wiarygodny ślad
- synthesis: połącz materiał w spójne podsumowanie
- analysis: pokaż obserwacje, interpretację i wnioski
- deep_analysis: pokaż obserwacje, mechanizmy, napięcia, ryzyka, implikacje i praktyczny wniosek

Pisz odpowiedź tak, jakby użytkownik chciał dostać gotową analizę, a nie materiał do dalszego ręcznego składania.
""".strip()


def get_answer_profile(
    *,
    question_type: str,
    analysis_depth: str,
    answer_style: str | None = "auto",
) -> str:
    if answer_style and answer_style != "auto":
        return answer_style

    if question_type == "chronology":
        return "chronology"

    if question_type == "summary":
        return "synthesis"

    if question_type == "analysis":
        if analysis_depth == "high":
            return "deep_analysis"
        return "analysis"

    if question_type == "retrieval":
        return "direct_answer"

    return "analysis"


def summarize_match_set(matches: list[dict]) -> str:
    if not matches:
        return "Brak dopasowań."

    by_source_type = Counter(m.get("source_type") or "unknown" for m in matches)
    by_source_name = Counter(m.get("source_name") or "unknown" for m in matches)
    by_title = Counter(m.get("title") or "unknown" for m in matches)

    top_source_types = ", ".join(
        f"{name}: {count}" for name, count in by_source_type.most_common(5)
    )
    top_source_names = ", ".join(
        f"{name}: {count}" for name, count in by_source_name.most_common(5)
    )
    top_titles = ", ".join(
        f"{name}: {count}" for name, count in by_title.most_common(8)
    )

    return "\n".join(
        [
            f"Liczba dopasowań: {len(matches)}",
            f"Typy źródeł: {top_source_types}",
            f"Najczęstsze zbiory: {top_source_names}",
            f"Najczęstsze dokumenty: {top_titles}",
        ]
    )


def _truncate_text(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text
    return text[:limit] + "\n[...obcięto]"


def build_context(matches: list[dict], *, text_limit: int = CHUNK_TEXT_LIMIT) -> str:
    blocks = []
    for i, m in enumerate(matches, start=1):
        text = _truncate_text(m.get("text") or "", text_limit)
        blocks.append(
            f"""[MATCH {i}]
source_type: {m.get("source_type")}
source_name: {m.get("source_name")}
title: {m.get("title")}
created_at: {m.get("created_at")}
chunk_id: {m.get("chunk_id")}
document_id: {m.get("document_id")}
score: {m.get("score")}

text:
{text}
"""
        )
    return "\n\n".join(blocks)


def get_structure_instruction(profile: str) -> str:
    structure_map = {
        "direct_answer": """
Struktura odpowiedzi:
1. Krótka odpowiedź na pytanie
2. Najważniejsze ustalenia
3. Jeśli potrzebne: doprecyzowanie lub zastrzeżenie
""",
        "chronology": """
Struktura odpowiedzi:
1. Najwcześniejszy / właściwy punkt w czasie
2. Krótkie uzasadnienie
3. Poziom pewności
4. Jeśli trzeba: istotne alternatywy lub zastrzeżenia
""",
        "synthesis": """
Struktura odpowiedzi:
1. Teza główna
2. Główne motywy / wzorce
3. Co z tego wynika
4. Jeśli trzeba: luki lub niepewności
""",
        "analysis": """
Struktura odpowiedzi:
1. Teza główna
2. Najważniejsze obserwacje z materiału
3. Interpretacja
4. Wnioski praktyczne
5. Jeśli trzeba: niepewności / ograniczenia
""",
        "deep_analysis": """
Struktura odpowiedzi:
1. Teza główna
2. Najważniejsze obserwacje z materiału
3. Głębsza interpretacja i mechanizmy
4. Napięcia, ryzyka lub sprzeczności
5. Wnioski praktyczne / rekomendacja
6. Niepewności / czego brakuje
""",
    }

    return structure_map.get(profile, structure_map["analysis"])


def _select_model(question_type: str, analysis_depth: str, answer_length: str | None) -> str:
    """Use fast model for simple retrieval queries with short/medium answers."""
    if (
        question_type == "retrieval"
        and analysis_depth in ("low", "normal")
        and answer_length in ("short", "medium")
    ):
        print(f"[answering] using fast model ({ANTHROPIC_FAST_MODEL}) for simple query")
        return ANTHROPIC_FAST_MODEL
    return ANTHROPIC_MODEL


def answer_question(
    query: str,
    matches: list[dict],
    question_type: str = "retrieval",
    analysis_depth: str = "normal",
    include_sources: bool = False,
    answer_style: str | None = "auto",
    answer_length: str | None = "long",
    allow_quotes: bool = True,
    conversation_context: str = "",
) -> str:
    # Shorter text limit for short answers to further reduce context
    text_limit = 800 if answer_length == "short" else CHUNK_TEXT_LIMIT
    context = build_context(matches, text_limit=text_limit)
    match_summary = summarize_match_set(matches)
    answer_profile = get_answer_profile(
        question_type=question_type,
        analysis_depth=analysis_depth,
        answer_style=answer_style,
    )
    structure_instruction = get_structure_instruction(answer_profile)

    dynamic_part = (
        f"Parametry bieżącego wywołania:\n"
        f"- allow_quotes={allow_quotes}\n"
        f"- question_type={question_type}\n"
        f"- analysis_depth={analysis_depth}\n"
        f"- answer_profile={answer_profile}\n"
        f"- answer_length={answer_length}\n"
        f"- include_sources={include_sources}\n\n"
        f"{structure_instruction}"
    )

    conversation_section = ""
    if conversation_context and conversation_context.strip():
        conversation_section = f"\n{conversation_context}\n"

    user_prompt = f"""
Pytanie użytkownika:
{query}
{conversation_section}
Podsumowanie zestawu dopasowań:
{match_summary}

Materiał źródłowy:
{context}
"""

    max_tokens_map = {
        "short": 600,
        "medium": 1200,
        "long": 2600,
    }
    max_tokens = max_tokens_map.get(answer_length or "long", 2600)

    model = _select_model(question_type, analysis_depth, answer_length)

    # Budget circuit breaker — fail-open
    from app.db.cost_tracker import check_budget
    budget = check_budget("retrieval.answering")
    if not budget["ok"]:
        log.warning("budget_exceeded", reason=budget["reason"])
        return f"⚠️ Budget przekroczony — odpowiedź wstrzymana. {budget['reason']}"

    system = [
        {"type": "text", "text": ANSWERING_STATIC_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_part.strip()},
    ]

    response = _call_with_fallback(
        model=model,
        max_tokens=max_tokens,
        temperature=0.2,
        system=system,
        user_prompt=user_prompt,
    )
    if response is None:
        return "Wystąpił błąd podczas generowania odpowiedzi. Spróbuj ponownie."

    from app.db.cost_tracker import log_anthropic_cost
    actual_model = getattr(response, "model", model)
    if hasattr(response, "usage"):
        log_anthropic_cost(actual_model, "retrieval.answering", response.usage)
        log.info("cache_stats",
                 cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                 cache_read=getattr(response.usage, "cache_read_input_tokens", 0))

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "\n".join(parts).strip()


def _call_with_fallback(
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    system: str | list[dict],
    user_prompt: str,
):
    """Call Anthropic API with retry + fallback to ANTHROPIC_FALLBACK_MODEL on overload."""
    models_to_try = [model]
    if ANTHROPIC_FALLBACK_MODEL and ANTHROPIC_FALLBACK_MODEL != model:
        models_to_try.append(ANTHROPIC_FALLBACK_MODEL)

    for current_model in models_to_try:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = client.messages.create(
                    model=current_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                if current_model != model:
                    log.info("answered_with_fallback", primary=model, fallback=current_model)
                return response
            except OverloadedError:
                log.warning(
                    "model_overloaded",
                    model=current_model,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_S * (attempt + 1))
                # After max retries, fall through to next model
            except (APIConnectionError, APITimeoutError) as e:
                log.error("api_connection_error", model=current_model, error=str(e))
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_S)
            except Exception as e:
                log.error("api_call_failed", model=current_model, error=str(e))
                return None

    log.error("all_models_exhausted", models=models_to_try)
    return None
