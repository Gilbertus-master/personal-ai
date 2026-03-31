"""Abstract base adapter for process metric collection."""

from __future__ import annotations

import abc
from datetime import date
from typing import Any

import psycopg
import structlog

logger = structlog.get_logger(__name__)


class BaseProcessAdapter(abc.ABC):
    """Base class for all process-data adapters.

    Adapters are config-driven: the source definition YAML provides
    ``column_mapping`` (adapter-native column -> ProcessMetric field)
    and ``query_config`` (adapter-specific query parameters).
    """

    def __init__(self, source_config: dict[str, Any]) -> None:
        self.source_config = source_config
        self.column_mapping: dict[str, str] = source_config.get("column_mapping", {})
        self.query_config: dict[str, Any] = source_config.get("query_config", {})
        self.adapter_name: str = source_config.get("adapter", self.__class__.__name__)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        """Collect raw metrics for one process and one week.

        Returns a dict whose keys are ProcessMetric field names
        (after applying column_mapping).
        """

    @abc.abstractmethod
    def collect_participations(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> list[dict[str, Any]]:
        """Collect participation records for one process and one week.

        Each dict should have at least: person_id, role_in_process,
        plus any of the numeric participation fields.
        """

    # ------------------------------------------------------------------
    # Helpers available to all adapters
    # ------------------------------------------------------------------

    def _apply_column_mapping(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map adapter-native column names to ProcessMetric field names.

        ``column_mapping`` in config maps *ProcessMetric field* -> *adapter column*.
        We invert that to convert raw adapter data -> ProcessMetric dict.
        """
        # Invert: metric_field -> adapter_col  =>  adapter_col -> metric_field
        inverted = {v: k for k, v in self.column_mapping.items()}
        mapped: dict[str, Any] = {}
        for col, value in raw.items():
            target = inverted.get(col, col)
            mapped[target] = value
        return mapped

    def _safe_query(
        self,
        conn: psycopg.Connection,
        query: str,
        params: dict[str, Any] | tuple | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a query and return rows as list[dict].

        Handles missing tables gracefully by returning empty list.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description is None:
                    return []
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except psycopg.errors.UndefinedTable as exc:
            logger.warning(
                "process_collector.adapter.missing_table",
                adapter=self.adapter_name,
                error=str(exc),
            )
            conn.rollback()
            return []
        except psycopg.errors.UndefinedColumn as exc:
            logger.warning(
                "process_collector.adapter.missing_column",
                adapter=self.adapter_name,
                error=str(exc),
            )
            conn.rollback()
            return []

    def _table_exists(self, conn: psycopg.Connection, table_name: str) -> bool:
        """Check whether a table exists in the current database."""
        rows = self._safe_query(
            conn,
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %(t)s)",
            {"t": table_name},
        )
        if rows:
            return list(rows[0].values())[0]
        return False
