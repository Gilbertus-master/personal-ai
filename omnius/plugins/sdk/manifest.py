"""Plugin manifest validation using jsonschema."""
from __future__ import annotations

import structlog
from jsonschema import ValidationError, validate

log = structlog.get_logger(__name__)

HOOK_SCHEMA = {
    "type": "object",
    "required": ["type", "handler"],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["scheduled_task", "ui_widget", "command_handler", "post_answer_hook"],
        },
        "handler": {"type": "string"},
        "action": {"type": "string"},
        "schedule": {"type": "string"},
    },
    "additionalProperties": False,
}

MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["name", "version", "description", "author", "hooks"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 64,
                 "pattern": "^[a-z0-9][a-z0-9_-]*$"},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "description": {"type": "string", "minLength": 1, "maxLength": 500},
        "author": {"type": "string", "minLength": 1},
        "hooks": {
            "type": "array",
            "minItems": 1,
            "items": HOOK_SCHEMA,
        },
        "permissions_required": {
            "type": "array",
            "items": {"type": "string"},
        },
        "config_schema": {"type": "object"},
    },
    "additionalProperties": False,
}


def validate_manifest(manifest: dict) -> dict:
    """Validate a plugin manifest dict.

    Returns: {"valid": True} or {"valid": False, "error": str}
    """
    try:
        validate(instance=manifest, schema=MANIFEST_SCHEMA)
        return {"valid": True}
    except ValidationError as e:
        log.warning("manifest_validation_failed", error=str(e.message)[:200])
        return {"valid": False, "error": e.message}
