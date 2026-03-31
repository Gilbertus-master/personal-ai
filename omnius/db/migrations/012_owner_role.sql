-- Migration 012: Add owner role (level 100) for system owner
-- Owner has full control over everything — above gilbertus_admin (99)

INSERT INTO omnius_roles (name, level, description)
VALUES ('owner', 100, 'System owner — full control over all modules, data, and configuration')
ON CONFLICT (name) DO UPDATE SET level = 100, description = EXCLUDED.description;

-- Assign Sebastian's user to owner role
UPDATE omnius_users
SET role_id = (SELECT id FROM omnius_roles WHERE name = 'owner')
WHERE email = 'sebastian@gilbertus.local';

-- Update existing API keys that were gilbertus_admin to owner (for Sebastian)
UPDATE omnius_api_keys
SET role_id = (SELECT id FROM omnius_roles WHERE name = 'owner')
WHERE role_id = (SELECT id FROM omnius_roles WHERE name = 'gilbertus_admin');
