"""Configuration loader for person_extractor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_SOURCES_PATH = Path(__file__).parent / "sources.yaml"


def load_config(sources_yaml: str | Path | None = None) -> dict[str, Any]:
    """Load sources.yaml configuration."""
    path = Path(sources_yaml) if sources_yaml else DEFAULT_SOURCES_PATH
    if not path.exists():
        return {"sources": [], "settings": _default_settings()}

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Merge defaults for missing settings
    settings = _default_settings()
    settings.update(config.get("settings", {}))
    config["settings"] = settings

    return config


def _default_settings() -> dict[str, Any]:
    return {
        "watermark_overlap_hours": 1,
        "llm_batch_size": 10,
        "llm_max_tokens": 1024,
        "min_confidence_for_auto_merge": 0.90,
        "fuzzy_name_threshold": 0.85,
        "log_level": "INFO",
    }
