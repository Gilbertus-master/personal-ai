"""Data models for the person extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class RawRecord:
    """Single raw record from any source."""
    source_name: str
    source_table: str
    source_record_id: str
    record_type: str  # 'contact', 'message', 'email', 'calendar_event'
    occurred_at: datetime
    raw_data: dict
    text_content: Optional[str] = None


@dataclass
class PersonCandidate:
    """Detected person from a single source record."""
    source_record: RawRecord
    role_in_record: str  # 'sender', 'recipient', 'attendee', 'contact', 'mentioned'

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    channel: Optional[str] = None

    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

    extraction_method: str = "structured"
    extraction_confidence: float = 1.0


@dataclass
class ResolvedPerson:
    """Result of identity resolution — candidate linked to a profile."""
    candidate: PersonCandidate
    person_id: Optional[UUID]
    resolution_type: str  # 'new', 'deterministic', 'probabilistic', 'manual'
    resolution_confidence: float = 1.0
    matched_by: Optional[str] = None


@dataclass
class ExtractionStats:
    """Stats for a single pipeline run."""
    source_name: str
    records_scanned: int = 0
    candidates_extracted: int = 0
    persons_new: int = 0
    persons_updated: int = 0
    persons_merged: int = 0
    identities_new: int = 0
    errors: int = 0
    llm_calls: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
