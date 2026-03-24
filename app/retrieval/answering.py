from __future__ import annotations

import os
from collections import Counter

from anthropic import Anthropic, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)

# Max characters per chunk text sent to the answer model.
# Limits context window size without dropping matches entirely.
CHUNK_TEXT_LIMIT = 1200


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

    system_prompt = f"""
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
- nie twórz sekcji „Źródła”,
- nie opisuj chunków pojedynczo,
- nie wypisuj metadanych dokumentów.

Cytaty:
- cytaty są dozwolone tylko wtedy, gdy są wyjątkowo wartościowe poznawczo,
- używaj ich oszczędnie,
- maksymalnie 1-3 krótkie cytaty,
- jeśli parafraza wystarczy, wybierz parafrazę.
allow_quotes={allow_quotes}

Parametry:
- question_type={question_type}
- analysis_depth={analysis_depth}
- answer_profile={answer_profile}
- answer_length={answer_length}
- include_sources={include_sources}

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

{structure_instruction}

Pisz odpowiedź tak, jakby użytkownik chciał dostać gotową analizę, a nie materiał do dalszego ręcznego składania.
"""

    user_prompt = f"""
Pytanie użytkownika:
{query}

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

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.2,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )
    except (APIConnectionError, APITimeoutError) as e:
        print(f"[answering] ERROR: Claude API connection/timeout error: {e}")
        return "Błąd połączenia z modelem AI. Spróbuj ponownie za chwilę."
    except Exception as e:
        print(f"[answering] ERROR: Claude API call failed: {e}")
        return "Wystąpił błąd podczas generowania odpowiedzi. Spróbuj ponownie."

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "\n".join(parts).strip()
