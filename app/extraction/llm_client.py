import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from anthropic import Anthropic, APIConnectionError, APITimeoutError


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class LLMExtractionClient:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("ANTHROPIC_EXTRACTION_MODEL")

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        if not model:
            raise RuntimeError("ANTHROPIC_EXTRACTION_MODEL is not set in .env")

        self.model = model
        self.client = Anthropic(api_key=api_key, timeout=45.0)

    def extract_object(
        self,
        system_prompt: str,
        user_payload: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_payload,
                    }
                ],
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": input_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except (APIConnectionError, APITimeoutError) as e:
            raise RuntimeError(f"Anthropic extraction API connection/timeout error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Anthropic extraction API call failed: {e}") from e

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
                if isinstance(block.input, dict):
                    return block.input
                raise RuntimeError("Anthropic tool_use input is not a dict")

        raise RuntimeError("Anthropic response did not return the expected tool_use payload")
