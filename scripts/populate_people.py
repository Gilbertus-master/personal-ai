#!/usr/bin/env python3
"""Populate people table with aliases for key personnel."""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

KEY_PEOPLE = [
    {
        "slug": "roch-baranowski",
        "aliases": ["Roch", "Baranowski", "prezes REH"],
    },
    {
        "slug": "krystian-juchacz",
        "aliases": ["Krystian", "Juchacz", "prezes REF"],
    },
    {
        "slug": "diana-skotnicka",
        "aliases": ["Diana", "Skotnicka", "CFO"],
    },
    {
        "slug": "pawel-makaruk",
        "aliases": ["Makaruk", "Paweł M.", "Origination"],
    },
    {
        "slug": "agata-morska",
        "aliases": ["Agata", "Morska"],
    },
    {
        "slug": "milosz-awedyk",
        "aliases": ["Miłosz", "Awedyk"],
    },
    {
        "slug": "maciej-rebajn",
        "aliases": ["Maciej", "Rebajn"],
    },
    {
        "slug": "krzysztof-kuzminski",
        "aliases": ["Krzysztof", "Kuźmiński", "Kuzminski"],
    },
    {
        "slug": "marcin-kulpa",
        "aliases": ["Marcin", "Kulpa"],
    },
    {
        "slug": "arkadiusz-blacha",
        "aliases": ["Arek", "Blacha", "Arkadiusz"],
    },
    {
        "slug": "ewa-jablonska",
        "aliases": ["Ewa", "Jabłońska", "mama"],
    },
    {
        "slug": "wojtek-jablonski",
        "aliases": ["Wojtek", "Jabłoński"],
    },
    {
        "slug": "adam-jablonski",
        "aliases": ["Adam", "Jabłoński", "tata"],
    },
    {
        "slug": "szczepan-jablonski",
        "aliases": ["Szczepan", "Jabłoński"],
    },
    {
        "slug": "zofia-godula",
        "aliases": ["Zofia", "Godula", "Zosia"],
    },
    {
        "slug": "andrzej-jablonski-wujek",
        "aliases": ["Wujek Andrzej", "Andrzej Jabłoński"],
    },
]

# New people to insert if missing
NEW_PEOPLE = [
    {
        "slug": "lukasz-jankowski",
        "first_name": "Łukasz",
        "last_name": "Jankowski",
        "aliases": ["Łukasz", "Jankowski", "Head of Origination"],
    },
    {
        "slug": "natalka-jastrzebska",
        "first_name": "Natalka",
        "last_name": "Jastrzębska",
        "aliases": ["Natalka", "Natalka J", "Jastrzębska", "księgowość"],
    },
]


def main(force=False):
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Update aliases for existing people
                updated = 0
                for person in KEY_PEOPLE:
                    if force:
                        cur.execute(
                            """UPDATE people SET aliases = %s, updated_at = NOW()
                               WHERE slug = %s""",
                            (person["aliases"], person["slug"]),
                        )
                    else:
                        cur.execute(
                            """UPDATE people SET aliases = %s, updated_at = NOW()
                               WHERE slug = %s AND (aliases IS NULL OR aliases = '{}')""",
                            (person["aliases"], person["slug"]),
                        )
                    if cur.rowcount > 0:
                        updated += 1
                        log.info('people.updated', slug=person['slug'], aliases=person['aliases'])
                    else:
                        log.warning('people.slug_not_found_skipped', slug=person['slug'])

                # Insert new people if missing
                inserted = 0
                for person in NEW_PEOPLE:
                    cur.execute("SELECT id FROM people WHERE slug = %s", (person["slug"],))
                    rows = cur.fetchall()
                    if not rows:
                        cur.execute(
                            """INSERT INTO people (slug, first_name, last_name, aliases)
                               VALUES (%s, %s, %s, %s)""",
                            (person["slug"], person["first_name"], person["last_name"], person["aliases"]),
                        )
                        inserted += 1
                        log.info('people.inserted', slug=person['slug'], aliases=person['aliases'])
                    else:
                        # Update aliases if empty (or if force=True)
                        if force:
                            cur.execute(
                                """UPDATE people SET aliases = %s, updated_at = NOW()
                                   WHERE slug = %s""",
                                (person["aliases"], person["slug"]),
                            )
                        else:
                            cur.execute(
                                """UPDATE people SET aliases = %s, updated_at = NOW()
                                   WHERE slug = %s AND (aliases IS NULL OR aliases = '{}')""",
                                (person["aliases"], person["slug"]),
                            )
                        if cur.rowcount > 0:
                            updated += 1
                            log.info('people.updated', slug=person['slug'], aliases=person['aliases'])

                conn.commit()
                log.info('people.sync_complete', updated=updated, inserted=inserted)

                # Show results
                cur.execute("SELECT slug, first_name, last_name, aliases FROM people ORDER BY id")
                rows = cur.fetchall()
                log.info('people.count', total=len(rows))
                for slug, fn, ln, aliases in rows:
                    log.info('people.entry', slug=slug, first_name=fn, last_name=ln, aliases=aliases)
    except Exception as e:
        log.error('populate_people.failed', error=str(e))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate people table with aliases for key personnel.")
    parser.add_argument("--force", action="store_true", help="Force update of already-populated aliases")
    args = parser.parse_args()
    main(force=args.force)
