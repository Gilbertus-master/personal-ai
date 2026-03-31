"""Generic SQL adapter — runs arbitrary parameterized queries from config."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import structlog

from process_collector.adapters.base import BaseProcessAdapter

logger = structlog.get_logger(__name__)


class GenericSQLAdapter(BaseProcessAdapter):
    """Runs user-defined SQL queries from the source config.

    Expects ``query_config`` to contain:
      - ``metrics_query``: SQL with ``%(week_start)s`` parameter
      - ``participation_query`` (optional): SQL with ``%(week_start)s``
      - ``metrics_table`` (optional): table to check existence before querying
    """

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        metrics_query = self.query_config.get("metrics_query")
        if not metrics_query:
            logger.warning(
                "process_collector.generic_sql.no_metrics_query",
                process_id=process_id,
            )
            return {}

        check_table = self.query_config.get("metrics_table")
        if check_table and not self._table_exists(conn, check_table):
            logger.warning(
                "process_collector.generic_sql.no_table",
                table=check_table,
            )
            return {}

        rows = self._safe_query(
            conn,
            metrics_query,
            {"week_start": week_start},
        )
        if not rows:
            return {}

        mapped = self._apply_column_mapping(rows[0])
        logger.info(
            "process_collector.generic_sql.collected",
            process_id=process_id,
            week_start=str(week_start),
            fields=len(mapped),
        )
        return mapped

    def collect_participations(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> list[dict[str, Any]]:
        participation_query = self.query_config.get("participation_query")
        if not participation_query:
            return []

        check_table = self.query_config.get("metrics_table")
        if check_table and not self._table_exists(conn, check_table):
            return []

        rows = self._safe_query(
            conn,
            participation_query,
            {"week_start": week_start},
        )
        logger.info(
            "process_collector.generic_sql.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
