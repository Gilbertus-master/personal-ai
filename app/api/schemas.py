from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


from app.models.query import InterpretedQuery  # noqa: F401 — re-export for backward compat

ALLOWED_SOURCE_TYPES = {"email", "teams", "whatsapp", "chatgpt", "plaud", "document", "calendar", "whatsapp_live", "pdf"}
ALLOWED_ANSWER_LENGTHS = {"short", "medium", "long", "auto"}


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000,
                       description="Max 4000 znaków")
    top_k: int = Field(default=8, ge=1, le=50)
    source_types: list[str] | None = Field(default=None,
        description="Allowed: email, teams, whatsapp, chatgpt, plaud, document, calendar, whatsapp_live, pdf")
    source_names: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    mode: str | None = "auto"
    include_sources: bool = False

    answer_style: str | None = "auto"
    answer_length: str | None = "long"
    allow_quotes: bool = True
    debug: bool = False
    channel: str | None = None  # "whatsapp", "api", etc. — affects defaults
    session_id: str | None = None  # conversation session key, e.g. "+48505441635"
    model_preference: str | None = None  # 'cheap' | 'balanced' | 'best' — auto-routes to cheapest suitable model

    @field_validator("source_types")
    @classmethod
    def validate_source_types(cls, v):
        if v is None:
            return v
        invalid = set(v) - ALLOWED_SOURCE_TYPES
        if invalid:
            raise ValueError(f"Invalid source_types: {invalid}. Allowed: {ALLOWED_SOURCE_TYPES}")
        return v

    @field_validator("answer_length")
    @classmethod
    def validate_answer_length(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_ANSWER_LENGTHS:
            raise ValueError(f"Invalid answer_length: {v}. Allowed: {ALLOWED_ANSWER_LENGTHS}")
        return v




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
