#!/usr/bin/env python
"""Print extraction stats (entity/event counts and pending chunks).

Usage: python scripts/extraction_stats.py [before|after]
"""
import sys

from app.db.postgres import get_pg_connection

if __name__ == "__main__":
    label = sys.argv[1].capitalize() if len(sys.argv) > 1 else "Stats"

    try:
        with get_pg_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM entities")
            rows = cur.fetchall()
            ent = rows[0][0] if len(rows) > 0 else 0

            cur.execute("SELECT COUNT(*) FROM events")
            rows = cur.fetchall()
            ev = rows[0][0] if len(rows) > 0 else 0

            cur.execute(
                "SELECT COUNT(*) FROM chunks c "
                "LEFT JOIN chunk_entities ce ON ce.chunk_id=c.id "
                "LEFT JOIN chunks_entity_checked cec ON cec.chunk_id=c.id "
                "WHERE ce.id IS NULL AND cec.chunk_id IS NULL"
            )
            rows = cur.fetchall()
            need_ent = rows[0][0] if len(rows) > 0 else 0

            cur.execute(
                "SELECT COUNT(*) FROM chunks c "
                "LEFT JOIN events e ON e.chunk_id=c.id "
                "LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id "
                "WHERE e.id IS NULL AND cec.chunk_id IS NULL"
            )
            rows = cur.fetchall()
            need_ev = rows[0][0] if len(rows) > 0 else 0
    except Exception as e:
        print(f"ERROR: could not fetch stats: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{label}: {ent} entities, {ev} events | Remaining: {need_ent} entity, {need_ev} event chunks")
