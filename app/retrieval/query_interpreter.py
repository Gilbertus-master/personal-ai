from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date

from anthropic import Anthropic
from dotenv import load_dotenv

from app.api.schemas import InterpretedQuery

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
INTERPRETATION_CACHE_TTL = int(os.getenv("INTERPRETATION_CACHE_TTL", "300"))  # 5 min

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)

# ---- In-memory interpretation cache ----
_interp_cache: dict[str, tuple[float, InterpretedQuery]] = {}
_CACHE_MAX_SIZE = 200


def _cache_key(
    query: str,
    source_types: list[str] | None,
    source_names: list[str] | None,
    date_from: str | None,
    date_to: str | None,
    mode: str | None,
) -> str:
    raw = json.dumps(
        [query.strip().lower(), source_types, source_names, date_from, date_to, mode],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str) -> InterpretedQuery | None:
    entry = _interp_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > INTERPRETATION_CACHE_TTL:
        _interp_cache.pop(key, None)
        return None
    return result


def _cache_put(key: str, result: InterpretedQuery) -> None:
    if len(_interp_cache) >= _CACHE_MAX_SIZE:
        oldest_key = min(_interp_cache, key=lambda k: _interp_cache[k][0])
        _interp_cache.pop(oldest_key, None)
    _interp_cache[key] = (time.time(), result)


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
    # --- cache lookup ---
    ck = _cache_key(query, source_types, source_names, date_from, date_to, mode)
    cached = _cache_get(ck)
    if cached is not None:
        print(f"[query_interpreter] cache HIT for query: {query[:80]}")
        return cached

    today = date.today().isoformat()

    system_prompt = f"""
Jesteś modułem interpretacji zapytań dla systemu retrieval.

Dzisiejsza data: {today}

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
- Jeśli pytanie zawiera JAKIEKOLWIEK wyrażenie czasowe — względne lub bezwzględne — ZAWSZE przelicz je na konkretny zakres dat (date_from / date_to) względem dzisiejszej daty ({today}).
- Ustaw null TYLKO gdy pytanie naprawdę nie zawiera żadnego określenia czasu.
- Wyrażenia względne w języku polskim — przeliczaj je tak:
  - "ostatni kwartał" = 3 miesiące wstecz od dziś
  - "ostatni miesiąc" = 1 miesiąc wstecz od dziś
  - "ostatni tydzień" / "w zeszłym tygodniu" = 7 dni wstecz od dziś
  - "w tym roku" = od 1 stycznia bieżącego roku do dziś
  - "w zeszłym roku" = od 1 stycznia do 31 grudnia poprzedniego roku
  - "od stycznia" / "od marca" = od 1. dnia tego miesiąca bieżącego roku do dziś
  - "w marcu" / "w lutym" (bez roku) = miesiąc bieżącego roku (od 1. do ostatniego dnia)
  - "w lutym 2026" = konkretny miesiąc danego roku
  - "ostatnie pół roku" = 6 miesięcy wstecz od dziś
  - "ostatnio" / "niedawno" = 30 dni wstecz od dziś
- normalized_query ma usuwać określenia czasu i formę pytania pomocniczą, zostawiając rdzeń semantyczny.
- Jeśli pytanie jest o "kiedy pierwszy raz", "od kiedy", "co było najpierw", ustaw question_type="chronology".
- Jeśli pytanie jest o "co mówiłem", "co pisałem", "jak opisywałem", zwykle ustaw "summary", chyba że użytkownik wyraźnie chce ocenę lub diagnozę.
- Jeśli pytanie zawiera słowa typu "oceń", "przeanalizuj", "jakie były wątpliwości", "jakie ryzyka", "co z tego wynika", "zarekomenduj", ustaw question_type="analysis".
- Jeśli question_type="chronology", ZAWSZE ustaw analysis_depth="high" (potrzebny szeroki zakres danych).
- Jeśli pytanie jest szerokie, przekrojowe lub ewaluacyjne, ustaw analysis_depth="high".
- Jeśli pytanie jest krótkie i faktograficzne, ustaw analysis_depth="low" albo "normal".

Przykłady (zakładając dzisiejszą datę {today}):
- "co mówiłem o Zosi w lutym 2026?" -> normalized_query: "mówiłem o Zosi", date_from: "2026-02-01", date_to: "2026-02-28", question_type: "summary"
- "kiedy pierwszy raz pisałem o ASD?" -> normalized_query: "ASD", date_from: null, date_to: null, question_type: "chronology", analysis_depth: "high"
- "jakie miałem wątpliwości co do projektu B2C?" -> normalized_query: "projekt B2C sprzedaży energii do gospodarstw domowych", question_type: "analysis"
- "Pokaż mi moje decyzje tradingowe z ostatniego kwartału" -> normalized_query: "decyzje tradingowe", date_from: (3 miesiące wstecz), date_to: "{today}", question_type: "retrieval"
- "co się działo w zeszłym tygodniu?" -> normalized_query: "co się działo", date_from: (7 dni wstecz), date_to: "{today}", question_type: "summary"
- "notatki od stycznia" -> normalized_query: "notatki", date_from: (1 stycznia br.), date_to: "{today}", question_type: "retrieval"
- "jak zmieniało się moje podejście do inwestowania?" -> normalized_query: "podejście do inwestowania", question_type: "chronology", analysis_depth: "high"
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
        result = InterpretedQuery(
            normalized_query=data.get("normalized_query") or query,
            date_from=data.get("date_from"),
            date_to=data.get("date_to"),
            source_types=data.get("source_types") if data.get("source_types") is not None else source_types,
            source_names=data.get("source_names") if data.get("source_names") is not None else source_names,
            question_type=data.get("question_type") or "retrieval",
            analysis_depth=data.get("analysis_depth") or "normal",
        )
        _cache_put(ck, result)
        return result
    except Exception as exc:
        print(f"[query_interpreter] WARNING: invalid interpreted payload, using fallback: {exc}; payload={data}")
        return build_fallback_interpretation(
            query=query,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )
    