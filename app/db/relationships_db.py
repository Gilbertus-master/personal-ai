"""
Relationships DB — migration, seed data, and SQL helper functions.
"""
from __future__ import annotations

import logging
from datetime import date

from app.db.postgres import get_pg_connection

logger = logging.getLogger(__name__)

# ── Migration ──────────────────────────────────────────────────────

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS people (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    aliases TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    person_role VARCHAR(200),
    organization VARCHAR(200),
    status VARCHAR(50) DEFAULT 'active',
    contact_channel VARCHAR(200),
    can_contact_directly BOOLEAN DEFAULT TRUE,
    sentiment VARCHAR(50) DEFAULT 'neutral',
    last_contact_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(person_id)
);

CREATE TABLE IF NOT EXISTS relationship_roles_history (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    role VARCHAR(200) NOT NULL,
    organization VARCHAR(200),
    date_from DATE,
    date_to DATE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS relationship_timeline (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    event_date DATE NOT NULL,
    event_type VARCHAR(100),
    description TEXT NOT NULL,
    source VARCHAR(100) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relationship_open_loops (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);
"""

# ── Seed data ──────────────────────────────────────────────────────

SEED_PEOPLE = [
    # (slug, first_name, last_name, rel_type, current_role, organization, status, contact_channel, can_contact_directly, sentiment)
    ("roch-baranowski",     "Roch",      "Baranowski", "business", "CEO REH",                 "Respect Energy Holding",   "active",     "bezpośredni 2x/tydzień",   True,  "positive"),
    ("krystian-juchacz",    "Krystian",  "Juchacz",    "business", "CEO REF",                 "RE-Fuels Sp. z o.o.",      "active",     "bezpośredni",              True,  "positive"),
    ("diana-skotnicka",     "Diana",     "Skotnicka",  "business", "CFO",                     "Respect Energy Holding",   "active",     "przez Rocha",              False, "neutral"),
    ("agata-morska",        "Agata",     "Morska",     "business", "Asystentka/Admin",         "SJ Sp.k.",                 "active",     "bezpośredni (prośby)",     True,  "neutral"),
    ("milosz-awedyk",       "Miłosz",    "Awedyk",     "business", "Prawnik",                  "PCS Legal (Paruch)",       "active",     "bezpośredni",              True,  "neutral"),
    ("maciej-rebajn",       "Maciej",    "Rebajn",     "business", "Koordynator BESS",         "Respect Energy Holding",   "active",     "przez Rocha",              False, "neutral"),
    ("pawel-makaruk",       "Paweł",     "Makaruk",    "business", "Manager projektów",        "Respect Energy Holding",   "active",     "przez Rocha",              False, "neutral"),
    ("krzysztof-kuzminski", "Krzysztof", "Kuźmiński",  "business", "Head of Trading",          "Respect Energy Holding",   "active",     "przez Rocha",              False, "neutral"),
    ("marcin-kulpa",        "Marcin",    "Kulpa",      "business", "Head of Wholesale",        "Respect Energy Holding",   "active",     "przez Rocha",              False, "positive"),
    ("arkadiusz-blacha",    "Arkadiusz", "Blacha",     "personal", "Znajomy",                  None,                       "active",     "bezpośredni",              True,  "positive"),
    ("ewa-jablonska",       "Ewa",       "Jabłońska",  "family",   "Była żona",                None,                       "dormant",    "w sprawach dzieci",        True,  "complex"),
    ("wojtek-jablonski",    "Wojtek",    "Jabłoński",  "family",   "Syn ur. ~2016",            "Thames British School",    "active",     "bezpośredni",              True,  "positive"),
    ("adam-jablonski",      "Adam",      "Jabłoński",  "family",   "Syn ur. sierpień 2020",    None,                       "active",     "bezpośredni",              True,  "positive"),
    ("szczepan-jablonski",  "Szczepan",  "Jabłoński",  "family",   "Ojciec",                   None,                       "terminated", "brak kontaktu ~3 lata",    False, "negative"),
    ("zofia-godula",        "Zofia",     "Godula",     "personal", "Była partnerka",            None,                       "terminated", "rozstanie 20.03.2026",     False, "complex"),
]

SEED_OPEN_LOOPS = {
    "roch-baranowski": [
        "Buyback akcji od Darka Blizniaka - Roch odpowiedzialny",
        "GoldenPeaks bank guarantee - update do 7 kwi",
    ],
    "krystian-juchacz": [
        "LTI/STI Krystiana - czeka na plik z założeniami od Sebastiana, potem mail do Miłosza Awedyka",
        "Cotygodniowy update sprzedaży stacji regazyfikacji 12.2M PLN",
    ],
}


def run_migration() -> None:
    """Create tables and insert seed data (idempotent)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Create tables
            cur.execute(MIGRATION_SQL)

            # Check if already seeded
            cur.execute("SELECT count(*) FROM people")
            count = cur.fetchone()[0]
            if count > 0:
                logger.info("Seed data already present (%d people), skipping.", count)
                conn.commit()
                return

            # Insert people + relationships
            for (slug, first_name, last_name, rel_type, current_role, org, status,
                 channel, can_contact, sentiment) in SEED_PEOPLE:
                cur.execute(
                    """
                    INSERT INTO people (slug, first_name, last_name)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (slug, first_name, last_name),
                )
                person_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO relationships
                        (person_id, relationship_type, person_role, organization,
                         status, contact_channel, can_contact_directly, sentiment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (person_id, rel_type, current_role, org, status,
                     channel, can_contact, sentiment),
                )

                # Open loops for specific people
                for description in SEED_OPEN_LOOPS.get(slug, []):
                    cur.execute(
                        "INSERT INTO relationship_open_loops (person_id, description) VALUES (%s, %s)",
                        (person_id, description),
                    )

            conn.commit()
            logger.info("Seed data inserted: %d people.", len(SEED_PEOPLE))


# ── SQL helpers ────────────────────────────────────────────────────

def get_person_by_slug(cur, slug: str) -> dict | None:
    cur.execute(
        """
        SELECT p.id, p.slug, p.first_name, p.last_name, p.aliases,
               p.created_at, p.updated_at,
               r.id AS rel_id, r.relationship_type, r.person_role, r.organization,
               r.status, r.contact_channel, r.can_contact_directly, r.sentiment,
               r.last_contact_date, r.notes,
               r.created_at AS rel_created_at, r.updated_at AS rel_updated_at
        FROM people p
        LEFT JOIN relationships r ON r.person_id = p.id
        WHERE p.slug = %s
        """,
        (slug,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return _person_row_to_dict(row)


def get_person_full_profile(cur, person_id: int) -> dict:
    """Load roles history, timeline, open loops for a person."""
    cur.execute(
        """
        SELECT id, role, organization, date_from, date_to, notes
        FROM relationship_roles_history
        WHERE person_id = %s
        ORDER BY date_from DESC NULLS LAST
        """,
        (person_id,),
    )
    roles = [
        {
            "id": r[0], "role": r[1], "organization": r[2],
            "date_from": str(r[3]) if r[3] else None,
            "date_to": str(r[4]) if r[4] else None,
            "notes": r[5],
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, event_date, event_type, description, source, created_at
        FROM relationship_timeline
        WHERE person_id = %s
        ORDER BY event_date DESC
        """,
        (person_id,),
    )
    timeline = [
        {
            "id": r[0], "event_date": str(r[1]), "event_type": r[2],
            "description": r[3], "source": r[4], "created_at": str(r[5]),
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, description, status, created_at, closed_at
        FROM relationship_open_loops
        WHERE person_id = %s
        ORDER BY created_at DESC
        """,
        (person_id,),
    )
    loops = [
        {
            "id": r[0], "description": r[1], "status": r[2],
            "created_at": str(r[3]),
            "closed_at": str(r[4]) if r[4] else None,
        }
        for r in cur.fetchall()
    ]

    return {"roles_history": roles, "timeline": timeline, "open_loops": loops}


def _person_row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "slug": row[1],
        "first_name": row[2],
        "last_name": row[3],
        "aliases": list(row[4]) if row[4] else [],
        "created_at": str(row[5]),
        "updated_at": str(row[6]),
        "relationship": {
            "id": row[7],
            "relationship_type": row[8],
            "current_role": row[9],
            "organization": row[10],
            "status": row[11],
            "contact_channel": row[12],
            "can_contact_directly": row[13],
            "sentiment": row[14],
            "last_contact_date": str(row[15]) if row[15] else None,
            "notes": row[16],
            "created_at": str(row[17]) if row[17] else None,
            "updated_at": str(row[18]) if row[18] else None,
        } if row[7] is not None else None,
    }
