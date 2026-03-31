"""Source adapters for person extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseAdapter

_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {}


def register_adapter(name: str):
    """Decorator to register an adapter class by name."""
    def wrapper(cls):
        _ADAPTER_REGISTRY[name] = cls
        return cls
    return wrapper


def get_adapter_class(name: str) -> type[BaseAdapter]:
    """Get adapter class by name from config."""
    # Lazy imports to populate registry
    if not _ADAPTER_REGISTRY:
        from . import contacts, emails, messages, calendar, generic_sql  # noqa: F401

    if name not in _ADAPTER_REGISTRY:
        raise ValueError(
            f"Unknown adapter '{name}'. Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return _ADAPTER_REGISTRY[name]
