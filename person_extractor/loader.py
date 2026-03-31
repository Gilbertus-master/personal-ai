"""Profile loader — upserts ResolvedPerson into person_profile tables."""

from __future__ import annotations

from uuid import UUID

from .models import RawRecord, ResolvedPerson


def upsert_person(resolved: ResolvedPerson, conn) -> UUID:
    """Create or update a person profile. Returns person_id."""
    c = resolved.candidate
    rec = c.source_record

    if resolved.person_id is None:
        display_name = (
            c.full_name or c.email or c.username or c.phone or "Nieznana osoba"
        )
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO persons (display_name, created_at, updated_at)
                   VALUES (%s, now(), now()) RETURNING person_id""",
                (display_name,),
            )
            person_id = cur.fetchone()[0]
    else:
        person_id = resolved.person_id
        # Upgrade display_name if we now have a real name
        if c.full_name and len(c.full_name) > 3:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE persons SET
                           display_name = CASE
                               WHEN display_name LIKE '%%@%%' THEN %s
                               WHEN display_name ~ '^\\+?[0-9 -]+$' THEN %s
                               ELSE display_name
                           END,
                           updated_at = now()
                       WHERE person_id = %s""",
                    (c.full_name, c.full_name, str(person_id)),
                )

    _upsert_identity(person_id, c, resolved, rec, conn)

    if c.job_title or c.company:
        _upsert_professional(person_id, c, conn)

    return person_id


def _upsert_identity(person_id, c, resolved, rec, conn):
    """Create or update person_identities record."""
    identifier = c.email or c.phone or c.username
    if not identifier:
        return

    channel = c.channel or ("email" if c.email else "phone" if c.phone else "other")

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO person_identities (
                   person_id, channel, identifier, display_name,
                   match_type, confidence, source_db, source_record_id,
                   first_seen_at, last_active_at, created_at, updated_at
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
               ON CONFLICT (channel, identifier) DO UPDATE SET
                   display_name = COALESCE(
                       NULLIF(EXCLUDED.display_name, ''),
                       person_identities.display_name
                   ),
                   confidence = GREATEST(
                       person_identities.confidence, EXCLUDED.confidence
                   ),
                   last_active_at = GREATEST(
                       person_identities.last_active_at, EXCLUDED.last_active_at
                   ),
                   updated_at = now()""",
            (
                str(person_id), channel, identifier, c.full_name,
                resolved.resolution_type, resolved.resolution_confidence,
                rec.source_table, rec.source_record_id,
                rec.occurred_at, rec.occurred_at,
            ),
        )


def _upsert_professional(person_id, c, conn):
    """Update professional info if we have new data."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO person_professional (person_id, job_title, company, source)
               VALUES (%s, %s, %s, 'extracted')
               ON CONFLICT (person_id) DO UPDATE SET
                   job_title = COALESCE(EXCLUDED.job_title, person_professional.job_title),
                   company = COALESCE(EXCLUDED.company, person_professional.company),
                   updated_at = now()""",
            (str(person_id), c.job_title, c.company),
        )


def upsert_interaction(
    person_id_from: UUID,
    person_id_to: UUID,
    record: RawRecord,
    role: str,
    conn,
):
    """Update interaction count between two persons."""
    if str(person_id_from) == str(person_id_to):
        return

    channel = record.source_name.split("_")[0]
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO person_relationships (
                   person_id_from, person_id_to,
                   interaction_count, initiated_by_from,
                   dominant_channel, first_contact_at, last_contact_at, computed_at
               ) VALUES (%s, %s, 1, %s, %s, %s, %s, now())
               ON CONFLICT (person_id_from, person_id_to) DO UPDATE SET
                   interaction_count = person_relationships.interaction_count + 1,
                   initiated_by_from = person_relationships.initiated_by_from + %s,
                   last_contact_at = GREATEST(
                       person_relationships.last_contact_at, EXCLUDED.last_contact_at
                   ),
                   computed_at = now()""",
            (
                str(person_id_from), str(person_id_to),
                1 if role == "sender" else 0,
                channel, record.occurred_at, record.occurred_at,
                1 if role == "sender" else 0,
            ),
        )
