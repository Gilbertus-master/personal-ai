# Part 8: Settings, Admin & Omnius Bridge

## Settings (all users)
- Profile: name, email, language (PL/EN), theme (dark/light), notification preferences
- API keys: view/rotate own key
- Session info: role, permissions, last login

## Admin (gilbertus_admin + operator)
- **User Management**: CRUD users, assign roles, permissions
- **Cron Manager**: lista 42 cronów, status, enable/disable, last run, next run
- **System Status**: DB stats, container health, backup status, disk usage
- **API Costs**: per-model, per-module, budget management
- **Code Review**: findings dashboard, resolution rate
- **Audit Log**: access log, who queried what when (Omnius)

## Omnius Bridge (gilbertus_admin ONLY — Sebastian)
- **Cross-tenant dashboard**: REH + REF overview side by side
- **Search across tenants**: query both Omnius instances
- **Audit across tenants**: who accessed what in each company
- **Operator tasks**: manage tasks for Michał across both companies
- **Config push**: push config/prompts from Gilbertus to Omnius instances
- **Sync trigger**: trigger data sync for specific tenants

## API Endpoints
Settings: user profile CRUD (may need new endpoints)
Admin: `/crons/*`, `/status`, `/costs/*`, `/code-fixes/*`
Omnius: `omnius_ask`, `omnius_command`, `omnius_status`, `omnius_bridge` (MCP tools → API calls)

## RBAC
- Settings: all users
- Admin: gilbertus_admin + operator
- Omnius Bridge: gilbertus_admin ONLY
