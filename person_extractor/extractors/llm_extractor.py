"""LLM-based extraction of persons and commitments from message text."""

from __future__ import annotations

import json
from typing import Any

import structlog
from anthropic import Anthropic

from app.db.cost_tracker import log_anthropic_cost

from ..models import PersonCandidate, RawRecord, ExtractionStats

log = structlog.get_logger("person_extractor.llm")

SYSTEM_PROMPT = """\
Analizujesz fragmenty wiadomości/emaili i wyciągasz z nich ustrukturyzowane dane.
Odpowiadaj WYŁĄCZNIE poprawnym JSON bez żadnych komentarzy, markdown ani dodatkowego tekstu.

Wyciągaj TYLKO osoby rzeczywiście wspomniane z imienia lub wyraźnego identyfikatora.
NIE wymyślaj osób ani danych. Jeśli nie ma żadnej osoby — zwróć pustą tablicę persons.

Dla "commitments" (otwartych pętli) szukaj fraz: "prześlę", "dam znać", "zadzwonię",
"obiecuję", "do piątku", "sprawdzę", "przygotuję", "masz przysłać", "czekamy na"."""

USER_PROMPT_TEMPLATE = """\
Przeanalizuj poniższe wiadomości i wyciągnij dane według schematu.

Schema odpowiedzi (JSON array, jeden element per rekord):
[{{
  "record_id": "...",
  "persons": [{{
    "full_name": "...",
    "email": "...",
    "phone": "...",
    "role": "sender|recipient|mentioned",
    "job_title": "...",
    "company": "..."
  }}],
  "commitments": [{{
    "direction": "i_owe_them|they_owe_me",
    "description": "...",
    "person_name": "..."
  }}],
  "topics": ["..."]
}}]

Wiadomości do analizy:
{messages_block}"""


class LLMExtractor:

    def __init__(self, settings: dict):
        self.client = Anthropic()
        self.batch_size = settings.get("llm_batch_size", 10)
        self.max_tokens = settings.get("llm_max_tokens", 1024)
        self.model = "claude-haiku-4-5-20251001"

    def extract_batch(
        self, records: list[RawRecord], stats: ExtractionStats
    ) -> dict[str, dict]:
        """Send batch of records to LLM. Returns {record_id: result_dict}."""
        if not records:
            return {}

        messages_block = "\n\n---\n\n".join(
            f"[record_id: {r.source_record_id}]\n{r.text_content or ''}"
            for r in records
            if r.text_content
        )

        if not messages_block.strip():
            return {}

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(messages_block=messages_block),
                }],
            )
            stats.llm_calls += 1

            if hasattr(response, "usage"):
                log_anthropic_cost(self.model, "person_extractor", response.usage)

            raw_text = response.content[0].text.strip()
            # Strip markdown fences
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            results = json.loads(raw_text)
            return {item["record_id"]: item for item in results}

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            log.warning("llm_extraction_failed", error=str(e))
            stats.errors += 1
            return {}

    def candidates_from_llm_result(
        self, record: RawRecord, llm_result: dict
    ) -> list[PersonCandidate]:
        """Convert LLM result to PersonCandidate list."""
        candidates = []
        for person_data in llm_result.get("persons", []):
            if not any([
                person_data.get("full_name"),
                person_data.get("email"),
                person_data.get("phone"),
            ]):
                continue

            candidates.append(
                PersonCandidate(
                    source_record=record,
                    role_in_record=person_data.get("role", "mentioned"),
                    full_name=person_data.get("full_name"),
                    email=person_data.get("email"),
                    phone=person_data.get("phone"),
                    job_title=person_data.get("job_title"),
                    company=person_data.get("company"),
                    extraction_method="llm",
                    extraction_confidence=0.8,
                )
            )
        return candidates

    def commitments_from_llm_result(
        self, record: RawRecord, llm_result: dict
    ) -> list[dict[str, Any]]:
        """Return commitment dicts for saving as open_loops."""
        return [
            {
                **c,
                "source_record_id": record.source_record_id,
                "source_name": record.source_name,
                "detected_by": "ai_extracted",
                "reviewed_by_user": False,
            }
            for c in llm_result.get("commitments", [])
        ]
