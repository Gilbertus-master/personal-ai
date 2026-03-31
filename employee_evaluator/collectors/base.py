"""Base collector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import psycopg


class BaseCollector(ABC):
    """Base class for data collectors."""

    @abstractmethod
    def collect(self, person_id: UUID, conn: psycopg.Connection) -> dict[str, Any]:
        """Collect data for a person. Returns dict of collected data."""
        ...
