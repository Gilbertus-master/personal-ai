"""Secrets management — Azure Key Vault with .env fallback.

In production (Azure), secrets are loaded from Key Vault.
In dev, secrets come from .env files as usual.

Usage:
    from omnius.core.secrets import get_secret
    api_key = get_secret("ANTHROPIC_API_KEY")
"""
from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)

_vault_client = None
_cache: dict[str, str] = {}

VAULT_URL = os.getenv("OMNIUS_KEYVAULT_URL", "")  # e.g. https://omnius-ref.vault.azure.net/


def _get_vault_client():
    """Lazy-init Azure Key Vault client."""
    global _vault_client
    if _vault_client is not None:
        return _vault_client

    if not VAULT_URL:
        return None

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        _vault_client = SecretClient(vault_url=VAULT_URL, credential=credential)
        log.info("keyvault_connected", url=VAULT_URL)
        return _vault_client
    except ImportError:
        log.debug("azure_sdk_not_installed_using_env")
        return None
    except Exception as e:
        log.warning("keyvault_connection_failed", error=str(e))
        return None


def get_secret(name: str, default: str = "") -> str:
    """Get secret value. Tries Azure Key Vault first, falls back to env var.

    Key Vault secret names use dashes (ANTHROPIC-API-KEY),
    env vars use underscores (ANTHROPIC_API_KEY).
    """
    # Check cache
    if name in _cache:
        return _cache[name]

    # Try Key Vault
    vault = _get_vault_client()
    if vault:
        try:
            # Convert env var name to Key Vault format (underscores → dashes)
            vault_name = name.replace("_", "-").lower()
            secret = vault.get_secret(vault_name)
            value = secret.value or default
            _cache[name] = value
            return value
        except Exception:
            pass  # Fall through to env var

    # Fallback to env var
    value = os.getenv(name, default)
    _cache[name] = value
    return value


def clear_cache():
    """Clear secrets cache (e.g. after rotation)."""
    _cache.clear()
