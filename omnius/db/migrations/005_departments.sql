-- Department structure for REF
-- Directors/managers/specialists are scoped to departments

-- Standard departments for energy trading company
-- Users can be assigned via UPDATE omnius_users SET department = 'trading' WHERE ...

-- Add department column to documents for scoped access
-- (already exists from 002_content.sql but ensure index)
CREATE INDEX IF NOT EXISTS idx_documents_department ON omnius_documents(department);

-- Example: Add directors/managers when ready
-- INSERT INTO omnius_users (email, display_name, role_id, department) VALUES
--   ('jan.kowalski@re-fuels.com', 'Jan Kowalski',
--    (SELECT id FROM omnius_roles WHERE name = 'director'), 'trading');
