"""Abstract base class for source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator

from ..models import RawRecord


class BaseAdapter(ABC):
    """Each data source implements this interface."""

    def __init__(self, config: dict, conn):
        self.config = config
        self.conn = conn
        self.source_name = config["name"]
        self.table = config["table"]
        self.watermark_column = config["watermark_column"]

    @abstractmethod
    def extract(self, since: datetime) -> Iterator[RawRecord]:
        """Yield records changed since `since`. Use server-side cursor."""
        ...

    def build_watermark_query(self, extra_where: str = "") -> str:
        """Helper: build SELECT with watermark filter."""
        where = f"WHERE {self.watermark_column} > %(since)s"
        if extra_where:
            where += f" AND {extra_where}"
        return f"SELECT * FROM {self.table} {where} ORDER BY {self.watermark_column} ASC"
