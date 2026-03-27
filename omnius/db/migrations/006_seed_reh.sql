-- Seed data for Omnius REH (Respect Energy Holding)
-- Run this on the REH instance instead of 003_seed.sql

-- Roles are identical (same migration 001_rbac.sql)
-- Only users differ

INSERT INTO omnius_users (email, display_name, role_id, department) VALUES
    ('roch@respect.energy', 'Roch Baranowski',
        (SELECT id FROM omnius_roles WHERE name = 'ceo'), NULL),
    ('diana.skotnicka@respect.energy', 'Diana Skotnicka',
        (SELECT id FROM omnius_roles WHERE name = 'board'), 'finance')
ON CONFLICT (email) DO NOTHING;

-- Same operator for both REH and REF (Michał supports both)
INSERT INTO omnius_users (email, display_name, role_id) VALUES
    ('michal.schulta@re-fuels.com', 'Michał Schulte',
        (SELECT id FROM omnius_roles WHERE name = 'operator'))
ON CONFLICT (email) DO NOTHING;
