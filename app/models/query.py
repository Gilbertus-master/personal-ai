from __future__ import annotations

from pydantic import BaseModel


class InterpretedQuery(BaseModel):
    normalized_query: str
    date_from: str | None = None
    date_to: str | None = None
    source_types: list[str] | None = None
    source_names: list[str] | None = None
    question_type: str = "retrieval"
    analysis_depth: str = "normal"
