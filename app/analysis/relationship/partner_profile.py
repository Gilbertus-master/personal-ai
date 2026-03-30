# PRIVATE — nie eksponować w Omnius ani publicznym API
from __future__ import annotations

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("rel.partner")


def get_partner(partner_id: int = 1) -> dict | None:
    """Pobierz profil partnera."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, phone, birth_date, birth_time,
                          attachment_style, love_languages, communication_style,
                          needs, boundaries, notes, created_at
                   FROM rel_partners WHERE id = %s""",
                (partner_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            result = dict(zip(cols, row))
            # Serialize dates
            for k in ("birth_date", "birth_time", "created_at"):
                if result.get(k):
                    result[k] = str(result[k])
            log.info("rel.partner.fetched", partner_id=partner_id)
            return result


def update_partner(partner_id: int, **fields) -> bool:
    """Aktualizuj profil partnera. Dozwolone pola: attachment_style, love_languages,
    communication_style, needs, boundaries, notes, phone, birth_date, birth_time."""
    allowed = {
        "attachment_style", "love_languages", "communication_style",
        "needs", "boundaries", "notes", "phone", "birth_date", "birth_time",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [partner_id]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE rel_partners SET {set_clause} WHERE id = %s",
                values,
            )
            conn.commit()
            log.info("rel.partner.updated", partner_id=partner_id, fields=list(updates.keys()))
            return cur.rowcount > 0


def create_partner(name: str, **fields) -> int:
    """Utwórz nowego partnera. Zwraca id."""
    allowed = {
        "phone", "birth_date", "birth_time", "attachment_style",
        "love_languages", "communication_style", "needs", "boundaries", "notes",
    }
    data = {k: v for k, v in fields.items() if k in allowed}
    data["name"] = name

    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO rel_partners ({cols}) VALUES ({placeholders}) RETURNING id",
                list(data.values()),
            )
            partner_id = cur.fetchall()[0][0]
            conn.commit()
            log.info("rel.partner.created", partner_id=partner_id)
            return partner_id
