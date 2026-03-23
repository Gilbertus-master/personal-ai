from __future__ import annotations

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from app.api.schemas import InterpretedQuery

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)


def build_fallback_interpretation(
    *,
    query: str,
    source_types: list[str] | None,
    source_names: list[str] | None,
    date_from: str | None,
    date_to: str | None,
) -> InterpretedQuery:
    normalized_query = " ".join(query.strip().split())
    return InterpretedQuery(
        normalized_query=normalized_query,
        date_from=date_from,
        date_to=date_to,
        source_types=source_types,
        source_names=source_names,
        question_type="retrieval",
        analysis_depth="normal",
    )


def strip_json_fence(raw: str) -> str:
    text = raw.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def interpret_query(
    query: str,
    source_types: list[str] | None = None,
    source_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    mode: str | None = "auto",
) -> InterpretedQuery:
    system_prompt = """
Jesteś modułem interpretacji zapytań dla systemu retrieval.

Masz zamienić pytanie użytkownika na ustrukturyzowany JSON.

Zwracaj wyłącznie poprawny JSON.
Nie dodawaj markdownu, komentarza ani objaśnień.

Zwróć pola:
- normalized_query: główny temat wyszukiwania semantycznego
- date_from: YYYY-MM-DD lub null
- date_to: YYYY-MM-DD lub null
- source_types: lista lub null
- source_names: lista lub null
- question_type: jedno z ["retrieval", "chronology", "summary", "analysis"]
- analysis_depth: jedno z ["low", "normal", "high"]

Zasady:
- Jeśli użytkownik podał jawne filtry wejściowe, są nadrzędne.
- Jeśli zakres czasu nie jest wystarczająco jasny, ustaw null zamiast zgadywać.
- Jeśli pytanie zawiera okres typu "w lutym 2026", przekształć go na konkretny zakres dat.
- normalized_query ma usuwać określenia czasu i formę pytania pomocniczą, zostawiając rdzeń semantyczny.
- Jeśli pytanie jest o "kiedy pierwszy raz", "od kiedy", "co było najpierw", ustaw question_type="chronology".
- Jeśli pytanie jest o "co mówiłem", "co pisałem", "jak opisywałem", zwykle ustaw "summary", chyba że użytkownik wyraźnie chce ocenę lub diagnozę.
- Jeśli pytanie zawiera słowa typu "oceń", "przeanalizuj", "jakie były wątpliwości", "jakie ryzyka", "co z tego wynika", "zarekomenduj", ustaw question_type="analysis".
- Jeśli pytanie jest szerokie, przekrojowe lub ewaluacyjne, ustaw analysis_depth="high".
- Jeśli pytanie jest krótkie i faktograficzne, ustaw analysis_depth="low" albo "normal".

Przykłady:
- "co mówiłem o Zosi w lutym 2026?" -> normalized_query: "mówiłem o Zosi", question_type: "summary"
- "kiedy pierwszy raz pisałem o ASD?" -> normalized_query: "ASD", question_type: "chronology"
- "jakie miałem wątpliwości co do projektu B2C?" -> normalized_query: "projekt B2C sprzedaży energii do gospodarstw domowych", question_type: "analysis"
"""

    payload = {
        "user_query": query,
        "mode": mode,
        "explicit_filters": {
            "source_types": source_types,
            "source_names": source_names,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            ],
        )
    except Exception as exc:
        print(f"[query_interpreter] WARNING: Anthropic call failed: {exc}")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    raw = "\n".join(parts).strip()

    if not raw:
        print("[query_interpreter] WARNING: empty model response, using fallback")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )

    raw = strip_json_fence(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[query_interpreter] WARNING: invalid JSON response, using fallback: {raw[:500]}")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )

    if not isinstance(data, dict):
        print(f"[query_interpreter] WARNING: parsed JSON is not an object, using fallback: {type(data)}")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )

    try:
        return InterpretedQuery(
            normalized_query=data.get("normalized_query") or query,
            date_from=data.get("date_from"),
            date_to=data.get("date_to"),
            source_types=data.get("source_types") if data.get("source_types") is not None else source_types,
            source_names=data.get("source_names") if data.get("source_names") is not None else source_names,
            question_type=data.get("question_type") or "retrieval",
            analysis_depth=data.get("analysis_depth") or "normal",
        )
    except Exception as exc:
        print(f"[query_interpreter] WARNING: invalid interpreted payload, using fallback: {exc}; payload={data}")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )
    