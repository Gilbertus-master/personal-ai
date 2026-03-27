-- Seed roles + permissions + REF users

-- 7 roles
INSERT INTO omnius_roles (name, level, description) VALUES
    ('gilbertus_admin', 99, 'Gilbertus system account — full control'),
    ('operator', 70, 'IT operator — human executor, infra, imports, dev tasks'),
    ('ceo', 60, 'CEO — full company access + user management'),
    ('board', 50, 'Board member — company data, manage directors'),
    ('director', 40, 'Director — department scope'),
    ('manager', 30, 'Manager — team scope'),
    ('specialist', 20, 'Specialist — own tasks')
ON CONFLICT (name) DO NOTHING;

-- Permissions per role
-- gilbertus_admin: everything (implicit — level 99 bypasses checks)

-- operator (infra/dev only — NO access to business data, analytics, or communications content)
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('config:write:system'), ('sync:manage'),
            ('sync:credentials'), ('infra:manage'), ('dev:execute'),
            ('commands:task')) AS p(perm)
WHERE r.name = 'operator'
ON CONFLICT DO NOTHING;

-- ceo
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('data:read:all'), ('financials:read'), ('evaluations:read:all'),
            ('communications:read:all'), ('config:write:system'),
            ('users:manage:all'), ('queries:create'), ('prompts:manage'),
            ('rbac:manage'), ('commands:email'), ('commands:ticket'),
            ('commands:meeting'), ('commands:task'), ('commands:sync'),
            ('views:configure:own')) AS p(perm)
WHERE r.name = 'ceo'
ON CONFLICT DO NOTHING;

-- board
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('data:read:all'), ('financials:read'), ('evaluations:read:reports'),
            ('config:write:system'), ('users:manage:below'), ('queries:create'),
            ('commands:email'), ('commands:ticket'), ('commands:meeting'),
            ('commands:task'), ('views:configure:own')) AS p(perm)
WHERE r.name = 'board'
ON CONFLICT DO NOTHING;

-- director
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('data:read:department'), ('evaluations:read:reports'),
            ('communications:read:department'), ('config:write:department'),
            ('queries:create'), ('commands:email'), ('commands:ticket'),
            ('commands:meeting'), ('commands:task'), ('views:configure:own')) AS p(perm)
WHERE r.name = 'director'
ON CONFLICT DO NOTHING;

-- manager
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('data:read:team'), ('config:write:own'), ('queries:create:department'),
            ('commands:ticket'), ('commands:meeting'), ('commands:task'),
            ('views:configure:own')) AS p(perm)
WHERE r.name = 'manager'
ON CONFLICT DO NOTHING;

-- specialist
INSERT INTO omnius_permissions (role_id, permission)
SELECT r.id, p.perm FROM omnius_roles r,
    (VALUES ('data:read:own'), ('config:write:own'), ('commands:task'),
            ('views:configure:own')) AS p(perm)
WHERE r.name = 'specialist'
ON CONFLICT DO NOTHING;

-- REF users
INSERT INTO omnius_users (email, display_name, role_id) VALUES
    ('krystian@re-fuels.com', 'Krystian Juchacz',
        (SELECT id FROM omnius_roles WHERE name = 'ceo')),
    ('edgar.mikolajek@re-fuels.com', 'Edgar Mikołajek',
        (SELECT id FROM omnius_roles WHERE name = 'board')),
    ('witold.pawlowski@re-fuels.com', 'Witold Pawłowski',
        (SELECT id FROM omnius_roles WHERE name = 'board')),
    ('michal.schulta@re-fuels.com', 'Michał Schulte',
        (SELECT id FROM omnius_roles WHERE name = 'operator'))
ON CONFLICT (email) DO NOTHING;
