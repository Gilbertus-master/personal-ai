"""Parse extracted text into structured process definitions via Claude API."""

from __future__ import annotations

import json

import structlog
from anthropic import Anthropic

from app.db.cost_tracker import log_anthropic_cost

log = structlog.get_logger("process_discovery.importers.llm_parser")

SYSTEM_PROMPT = """\
Jesteś analitykiem procesów biznesowych. Parsuj opisy procesów z różnych
dokumentów i zwracaj ustrukturyzowane dane.

Wyciągaj TYLKO procesy biznesowe — powtarzalne sekwencje działań z
zdefiniowanym celem i uczestnikami. Ignoruj: opisy ogólne firmy,
cele strategiczne, struktury organizacyjne (chyba że opisują przepływ pracy).

Jeśli dokument zawiera diagramy BPMN, swimlane, flowcharts — traktuj
każdy lane/pool jako oddzielny proces lub podproces.

Odpowiadaj WYŁĄCZNIE poprawnym JSON. Bez markdown, bez komentarzy."""

USER_PROMPT = """\
Przetwórz poniższy dokument i wyciągnij z niego wszystkie procesy biznesowe.

Dokument (format: {format}, źródło: {filename}):
---
{content}
---

Zwróć JSON array. Dla każdego procesu:
{{
  "name": "Nazwa procesu (krótka, opisowa)",
  "description": "Co ten proces realizuje (1-2 zdania)",
  "process_type": "engineering|sales|customer_service|finance|operations|hr|other",
  "steps": ["krok 1", "krok 2", "krok 3"],
  "owner_role": "Rola właściciela procesu lub null",
  "participants": ["rola 1", "rola 2"],
  "inputs": ["wejście 1"],
  "outputs": ["wyjście 1"],
  "estimated_duration": "np. '2-3 dni' lub null",
  "systems_used": ["Jira", "Salesforce"],
  "sla_or_target": "np. 'zamknięcie w 24h' lub null",
  "confidence": 0.85,
  "notes": "Dodatkowe uwagi lub null",
  "parent_process_name": "Nazwa procesu nadrzędnego lub null"
}}

Jeśli dokument jest słabej jakości lub nie zawiera procesów — zwróć []."""

MODEL = "claude-sonnet-4-6"
MAX_CHUNK_SIZE = 40000
CHUNK_OVERLAP = 2000


def parse_processes(
    extracted_text: str,
    filename: str,
    file_format: str,
) -> list[dict]:
    """Send extracted text to Claude and get structured process list.

    For texts > 50k chars, splits into chunks with overlap and deduplicates.
    """
    if not extracted_text or not extracted_text.strip():
        return []

    if len(extracted_text) > 50000:
        return _parse_chunked(extracted_text, filename, file_format)

    return _parse_single(extracted_text, filename, file_format)


def _parse_single(text: str, filename: str, file_format: str) -> list[dict]:
    """Parse a single chunk of text."""
    # Truncate to safe limit
    content = text[:80000]

    client = Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": USER_PROMPT.format(
                    format=file_format,
                    filename=filename,
                    content=content,
                ),
            }],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(MODEL, "process_import_parse", response.usage)

        raw = response.content[0].text.strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]

        result = json.loads(raw.strip())
        if not isinstance(result, list):
            log.warning("llm_returned_non_list", type=type(result).__name__)
            return []

        log.info("processes_parsed", count=len(result), filename=filename)
        return result

    except json.JSONDecodeError as e:
        log.warning("llm_json_parse_error", error=str(e), filename=filename)
        return []
    except Exception as e:
        log.error("llm_parse_failed", error=str(e), filename=filename)
        return []


def _parse_chunked(text: str, filename: str, file_format: str) -> list[dict]:
    """Split large text into chunks, parse each, deduplicate by name."""
    chunks: list[str] = []
    pos = 0
    while pos < len(text):
        end = pos + MAX_CHUNK_SIZE
        chunks.append(text[pos:end])
        pos = end - CHUNK_OVERLAP

    log.info("parsing_chunked", chunks=len(chunks), total_chars=len(text))

    all_processes: list[dict] = []
    seen_names: set[str] = set()

    for i, chunk in enumerate(chunks):
        chunk_filename = f"{filename} [chunk {i + 1}/{len(chunks)}]"
        results = _parse_single(chunk, chunk_filename, file_format)
        for proc in results:
            name_key = (proc.get("name") or "").strip().lower()
            if name_key and name_key not in seen_names:
                seen_names.add(name_key)
                all_processes.append(proc)

    log.info("chunked_parse_complete", total_unique=len(all_processes))
    return all_processes
