"""LLM-based classification of discovered process candidates."""
from __future__ import annotations

import json
import os
from typing import Any

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.cost_tracker import log_anthropic_cost
from process_discovery.models import ProcessCandidate

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=90.0
        )
    return _client


SYSTEM_PROMPT = (
    "You are a business process analyst. Given state transition sequences "
    "and statistics from an energy trading company, identify and name the "
    "business processes. Respond ONLY with valid JSON — an array of objects, "
    "one per pattern."
)

USER_PROMPT_TEMPLATE = """Classify these state-transition patterns into business processes.

For each pattern, provide:
- name: short process name (max 60 chars)
- description: 2-3 sentence description of this process
- type: one of: engineering, sales, customer_service, finance, operations
- metrics: list of exactly 3 key metrics to track for this process
- confidence: float 0-1, how confident you are this is a real recurring process

Patterns:
{patterns_json}

Respond with a JSON array, one object per pattern, in the same order."""


def classify_candidates(
    candidates: list[ProcessCandidate],
) -> list[ProcessCandidate]:
    """
    Enrich candidates with LLM-suggested names, descriptions, types.
    Processes in batches of up to 10 candidates per API call.
    Returns the same candidates list with suggested_* fields populated.
    """
    if not candidates:
        return candidates

    client = _get_client()
    batch_size = 10

    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start : batch_start + batch_size]

        patterns_data = []
        for i, c in enumerate(batch):
            patterns_data.append(
                {
                    "index": i,
                    "sequence": c.sequence,
                    "source": c.source,
                    "entity_type": c.entity_type,
                    "occurrences_count": c.occurrences_count,
                    "occurrences_per_week": c.occurrences_per_week,
                    "avg_duration_h": c.avg_duration_h,
                    "unique_actors": c.unique_actors_count,
                    "project_keys": c.project_keys[:5],  # limit context
                }
            )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            patterns_json=json.dumps(patterns_data, indent=2)
        )

        try:
            response = client.messages.create(
                model=ANTHROPIC_FAST,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            log_anthropic_cost(
                model=ANTHROPIC_FAST,
                module="process_discovery.llm_classifier",
                usage=response.usage,
            )

            raw_text = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[: raw_text.rfind("```")]
                raw_text = raw_text.strip()

            classifications: list[dict[str, Any]] = json.loads(raw_text)

            for i, cls in enumerate(classifications):
                if i >= len(batch):
                    break
                candidate = batch[i]
                candidate.suggested_name = cls.get("name")
                candidate.suggested_description = cls.get("description")
                candidate.suggested_type = cls.get("type")

                metrics = cls.get("metrics")
                if isinstance(metrics, list):
                    candidate.suggested_metrics = {"metrics": metrics}

                confidence = cls.get("confidence")
                if confidence is not None:
                    candidate.llm_confidence = float(confidence)

            log.info(
                "llm_classify_batch_done",
                batch_start=batch_start,
                batch_size=len(batch),
                classified=len(classifications),
            )

        except json.JSONDecodeError as exc:
            log.error(
                "llm_classify_json_error",
                batch_start=batch_start,
                error=str(exc),
            )
        except Exception as exc:
            log.error(
                "llm_classify_api_error",
                batch_start=batch_start,
                error=str(exc),
            )

    return candidates
