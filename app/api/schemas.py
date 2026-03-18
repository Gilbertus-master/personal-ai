from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    source_types: list[str] | None = None
    source_names: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    mode: str | None = "auto"
    include_sources: bool = False

    answer_style: str | None = "auto"
    answer_length: str | None = "long"
    allow_quotes: bool = True
    debug: bool = False


class InterpretedQuery(BaseModel):
    normalized_query: str
    date_from: str | None = None
    date_to: str | None = None
    source_types: list[str] | None = None
    source_names: list[str] | None = None
    question_type: str = "retrieval"
    analysis_depth: str = "normal"


class MatchItem(BaseModel):
    chunk_id: int | None = None
    document_id: int | None = None
    score: float
    source_type: str | None = None
    source_name: str | None = None
    title: str | None = None
    created_at: str | None = None
    text: str


class SourceItem(BaseModel):
    document_id: int | None = None
    title: str | None = None
    source_type: str | None = None
    source_name: str | None = None
    created_at: str | None = None


from typing import Any


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem] | None = None
    matches: list[MatchItem] | None = None
    meta: dict[str, Any] | None = None
    run_id: int | None = None