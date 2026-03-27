"""RBAC permission constants and helpers for Omnius."""
from __future__ import annotations

from typing import Any

# Classification levels — what each role can see
CLASSIFICATION_ACCESS: dict[str, list[str]] = {
    "gilbertus_admin": ["public", "internal", "confidential", "ceo_only"],
    "operator": [],  # No access to business data — infra/dev role only
    "ceo": ["public", "internal", "confidential", "ceo_only"],
    "board": ["public", "internal", "confidential"],
    "director": ["public", "internal"],
    "manager": ["public", "internal"],
    "specialist": ["public"],
}

# Admin bypass level — gilbertus_admin skips all permission checks
ADMIN_BYPASS_LEVEL = 99


def has_permission(user: dict[str, Any], permission: str) -> bool:
    """Check if user has a specific permission."""
    if user.get("role_level", 0) >= ADMIN_BYPASS_LEVEL:
        return True
    return permission in user.get("permissions", set())


def allowed_classifications(role_name: str) -> list[str]:
    """Return document classification levels visible to this role."""
    return CLASSIFICATION_ACCESS.get(role_name, ["public"])


def can_manage_user(manager: dict[str, Any], target_role_level: int) -> bool:
    """Check if manager can create/edit users at target_role_level."""
    if manager.get("role_level", 0) >= ADMIN_BYPASS_LEVEL:
        return True
    if has_permission(manager, "users:manage:all"):
        return True
    if has_permission(manager, "users:manage:below"):
        return manager.get("role_level", 0) > target_role_level
    return False
