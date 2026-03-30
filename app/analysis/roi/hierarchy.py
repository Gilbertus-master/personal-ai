"""ROI Hierarchy — organizational tree for value aggregation."""
from __future__ import annotations

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


_tables_ensured = False
def _ensure_tables() -> None:
    """Run migration inline if tables don't exist yet."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'roi_hierarchy'
                )
            """)
            if not cur.fetchall()[0][0]:
                log.warning("roi_hierarchy table missing — run migrations/019_roi.sql")
    _tables_ensured = True


def get_entity(entity_id: int) -> dict | None:
    """Get a single hierarchy entity by ID."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at "
                "FROM roi_hierarchy WHERE id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_dict(row)


def get_entity_by_name(name: str) -> dict | None:
    """Find entity by name (case-insensitive partial match)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at "
                "FROM roi_hierarchy WHERE LOWER(name) LIKE LOWER(%s) LIMIT 1",
                (f"%{name}%",),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_dict(row)


def get_owner_entity() -> dict | None:
    """Get the owner (Sebastian) entity."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at "
                "FROM roi_hierarchy WHERE type = 'owner' LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_dict(row)


def get_children(parent_id: int) -> list[dict]:
    """Get direct children of an entity."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at "
                "FROM roi_hierarchy WHERE parent_id = %s ORDER BY name",
                (parent_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_hierarchy_tree() -> list[dict]:
    """Return full hierarchy as flat list with depth info."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH RECURSIVE tree AS (
                    SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at, 0 AS depth
                    FROM roi_hierarchy WHERE parent_id IS NULL
                    UNION ALL
                    SELECT h.id, h.name, h.type, h.parent_id, h.hourly_rate_pln, h.metadata, h.created_at, t.depth + 1
                    FROM roi_hierarchy h JOIN tree t ON h.parent_id = t.id
                )
                SELECT id, name, type, parent_id, hourly_rate_pln, metadata, created_at, depth
                FROM tree ORDER BY depth, name
            """)
            results = []
            for row in cur.fetchall():
                d = _row_to_dict(row[:7])
                d["depth"] = row[7]
                results.append(d)
            return results


def create_entity(
    name: str,
    entity_type: str,
    parent_id: int | None = None,
    hourly_rate_pln: float = 0,
    metadata: dict | None = None,
) -> dict:
    """Create a new hierarchy entity."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO roi_hierarchy (name, type, parent_id, hourly_rate_pln, metadata) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id, name, type, parent_id, hourly_rate_pln, metadata, created_at",
                (name, entity_type, parent_id, hourly_rate_pln, metadata or {}),
            )
            row = cur.fetchone()
            log.info("roi_hierarchy_created", name=name, type=entity_type, id=row[0])
            return _row_to_dict(row)


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "type": row[2],
        "parent_id": row[3],
        "hourly_rate_pln": float(row[4]) if row[4] else 0,
        "metadata": row[5] or {},
        "created_at": str(row[6]),
    }
