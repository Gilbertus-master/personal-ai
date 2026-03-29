"""PluginContext — sandboxed context passed to every plugin handler.

Provides controlled access to Omnius data and services without
exposing raw DB connections or internal APIs to plugin code.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


class PluginContext:
    """Sandboxed execution context for a plugin.

    Created once per plugin at load time, reused across requests.
    All DB operations go through get_pg_connection() pool.
    """

    def __init__(self, tenant: str, user_id: int, plugin_name: str):
        self.tenant = tenant
        self.user_id = user_id
        self.plugin_name = plugin_name
        self._log = log.bind(plugin=plugin_name, tenant=tenant)

    def query_data(self, query: str, classification_max: str = "internal") -> list[dict]:
        """Semantic search over Omnius data, respecting classification limits.

        Uses the same vector search as /ask, but capped at the given
        classification level (default: internal — no confidential/ceo_only).
        """
        try:
            from omnius.sync.embeddings import search_vectors

            # Derive allowed classifications up to classification_max
            all_levels = ["public", "internal", "confidential", "ceo_only"]
            max_idx = all_levels.index(classification_max) if classification_max in all_levels else 1
            classifications = all_levels[: max_idx + 1]

            results = search_vectors(query, classifications=classifications, limit=10)
            self._log.info("plugin_query_data", query=query[:80], results=len(results))
            return results
        except Exception as e:
            self._log.error("plugin_query_data_failed", error=str(e))
            return []

    def create_task(self, title: str, description: str, assignee: str | None = None) -> dict:
        """Create an operator task in omnius_operator_tasks."""
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    if assignee:
                        cur.execute("""
                            INSERT INTO omnius_operator_tasks
                                (title, description, source, assigned_to)
                            VALUES (%s, %s, %s,
                                    (SELECT id FROM omnius_users WHERE email = %s))
                            RETURNING id
                        """, (title, description, f"plugin:{self.plugin_name}", assignee))
                    else:
                        cur.execute("""
                            INSERT INTO omnius_operator_tasks
                                (title, description, source)
                            VALUES (%s, %s, %s)
                            RETURNING id
                        """, (title, description, f"plugin:{self.plugin_name}"))
                    task_id = cur.fetchone()[0]
                conn.commit()

            self._log.info("plugin_task_created", task_id=task_id, title=title[:80])
            return {"status": "created", "task_id": task_id}
        except Exception as e:
            self._log.error("plugin_create_task_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    def send_notification(self, user_email: str, message: str) -> dict:
        """Log a notification intent. Actual delivery is outside plugin scope."""
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO omnius_audit_log
                            (user_id, action, resource, request_summary, result_status)
                        VALUES (%s, %s, %s, %s, 'ok')
                    """, (
                        self.user_id,
                        f"plugin:{self.plugin_name}:notification",
                        user_email,
                        json.dumps({"message": message[:500]}),
                    ))
                conn.commit()

            self._log.info("plugin_notification_logged",
                           target=user_email, message=message[:80])
            return {"status": "logged", "target": user_email}
        except Exception as e:
            self._log.error("plugin_notification_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    def get_config(self, key: str) -> Any:
        """Read a value from omnius_config table."""
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM omnius_config WHERE key = %s",
                        (f"plugin:{self.plugin_name}:{key}",),
                    )
                    row = cur.fetchone()
                    if row:
                        return json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    return None
        except Exception as e:
            self._log.error("plugin_get_config_failed", key=key, error=str(e))
            return None

    def log(self, level: str, message: str, **kwargs) -> None:
        """Structured logging with plugin context automatically attached."""
        logger = self._log.bind(**kwargs)
        log_fn = getattr(logger, level, logger.info)
        log_fn(message)
