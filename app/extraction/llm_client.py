import os
import time
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from anthropic import Anthropic, APIConnectionError, APITimeoutError
from anthropic._exceptions import OverloadedError


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

from app.db.cost_tracker import log_anthropic_cost  # noqa: E402

log = structlog.get_logger("llm_client")

MAX_RETRIES = 3
RETRY_DELAY_S = 2


class LLMExtractionClient:
    def __init__(self, model_override: str | None = None, module: str = "extraction") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = model_override or os.getenv("ANTHROPIC_EXTRACTION_MODEL")
        self.fallback_model = os.getenv("ANTHROPIC_EXTRACTION_FALLBACK_MODEL", "")

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        if not model:
            raise RuntimeError("ANTHROPIC_EXTRACTION_MODEL is not set in .env")

        self.model = model
        self.module = module
        self.client = Anthropic(api_key=api_key, timeout=45.0)

    def extract_object(
        self,
        system_prompt: str,
        user_payload: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
    ) -> dict[str, Any]:
        models_to_try = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models_to_try.append(self.fallback_model)

        last_error = None
        for current_model in models_to_try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = self.client.messages.create(
                        model=current_model,
                        max_tokens=1200,
                        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                        messages=[{"role": "user", "content": user_payload}],
                        tools=[{"name": tool_name, "description": tool_description, "input_schema": input_schema}],
                        tool_choice={"type": "tool", "name": tool_name},
                    )

                    if hasattr(response, "usage"):
                        log_anthropic_cost(current_model, self.module, response.usage)

                    if current_model != self.model:
                        log.info("extraction_fallback_used", primary=self.model, fallback=current_model)

                    for block in response.content:
                        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
                            if isinstance(block.input, dict):
                                return block.input
                            raise RuntimeError("Anthropic tool_use input is not a dict")

                    raise RuntimeError("Anthropic response did not return the expected tool_use payload")

                except OverloadedError:
                    log.warning("model_overloaded", model=current_model, attempt=attempt + 1)
                    last_error = RuntimeError(f"Model {current_model} overloaded after {attempt + 1} attempts")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY_S * (attempt + 1))
                except (APIConnectionError, APITimeoutError) as e:
                    last_error = RuntimeError(f"Anthropic extraction API connection/timeout error: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY_S)
                    else:
                        break
                except RuntimeError:
                    raise
                except Exception as e:
                    raise RuntimeError(f"Anthropic extraction API call failed: {e}") from e

        log.error("all_models_exhausted", models=models_to_try, module=self.module)
        raise last_error or RuntimeError("All models exhausted")
