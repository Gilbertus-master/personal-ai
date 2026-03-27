"""Authentication for Omnius — API key + Azure AD JWT."""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, Request

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

# Azure AD config (REF tenant)
AZURE_TENANT_ID = os.getenv("OMNIUS_AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("OMNIUS_AZURE_CLIENT_ID", "")

# JWKS cache
_jwks_cache: dict[str, Any] = {"keys": [], "fetched_at": 0.0}
_JWKS_TTL = 3600  # 1 hour


def _hash_key(api_key: str) -> str:
    """SHA-256 hash for API key lookup."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def authenticate(request: Request) -> dict[str, Any]:
    """Authenticate request. Returns user dict with role info and permissions.

    Tries in order:
    1. X-API-Key header → lookup in omnius_api_keys
    2. Authorization: Bearer <jwt> → validate Azure AD token
    3. X-User-Email header (dev mode only, when OMNIUS_DEV_AUTH=1)
    """
    # 1. API key auth
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return _auth_api_key(api_key)

    # 2. Azure AD JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return await _auth_azure_ad(token)

    # 3. Dev mode: trust X-User-Email header — ONLY from localhost
    if os.getenv("OMNIUS_DEV_AUTH") == "1":
        client_ip = request.client.host if request.client else ""
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            email = request.headers.get("X-User-Email")
            if email:
                log.warning("dev_auth_used", email=email, ip=client_ip)
                return _auth_dev_email(email)
        else:
            log.warning("dev_auth_rejected_non_localhost", ip=client_ip)

    # Log failed auth attempt
    log.warning("auth_failed", ip=request.client.host if request.client else "unknown",
                has_api_key=bool(api_key), has_bearer=auth_header.startswith("Bearer "))
    raise HTTPException(status_code=401, detail="Authentication required")


def _auth_api_key(api_key: str) -> dict[str, Any]:
    """Authenticate via API key."""
    key_hash = _hash_key(api_key)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ak.id, ak.name, ak.user_id, r.name, r.level
                FROM omnius_api_keys ak
                JOIN omnius_roles r ON r.id = ak.role_id
                WHERE ak.key_hash = %s AND ak.is_active = TRUE
            """, (key_hash,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Invalid API key")

            # Update last_used_at
            cur.execute("UPDATE omnius_api_keys SET last_used_at = NOW() WHERE id = %s", (row[0],))
            conn.commit()

            permissions = _load_permissions_for_role(cur, row[3])

            return {
                "auth_type": "api_key",
                "api_key_id": row[0],
                "api_key_name": row[1],
                "user_id": row[2],
                "role_name": row[3],
                "role_level": row[4],
                "permissions": permissions,
            }


async def _auth_azure_ad(token: str) -> dict[str, Any]:
    """Validate Azure AD JWT and return user info."""
    try:
        import jwt as pyjwt

        # Fetch JWKS if needed
        jwks = await _get_jwks()

        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")

        # Find matching key
        public_key = None
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                break

        if not public_key:
            raise HTTPException(status_code=401, detail="Unknown signing key")

        # Verify token
        claims = pyjwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=AZURE_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0",
        )

        email = claims.get("preferred_username", claims.get("upn", claims.get("email", "")))
        oid = claims.get("oid", "")

        if not email:
            raise HTTPException(status_code=401, detail="No email in token")

        return _lookup_user(email, oid)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Azure AD auth failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


async def _get_jwks() -> dict:
    """Fetch Azure AD JWKS (cached)."""
    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL:
        return _jwks_cache

    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    _jwks_cache["keys"] = data.get("keys", [])
    _jwks_cache["fetched_at"] = now
    return data


def _lookup_user(email: str, oid: str = "") -> dict[str, Any]:
    """Lookup user by email, return user dict with permissions."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.email, u.display_name, r.name, r.level
                FROM omnius_users u
                JOIN omnius_roles r ON r.id = u.role_id
                WHERE u.email = %s AND u.is_active = TRUE
            """, (email,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=403, detail=f"User {email} not registered in Omnius")

            # Update azure_ad_oid on first login
            if oid:
                cur.execute("UPDATE omnius_users SET azure_ad_oid = %s WHERE id = %s AND azure_ad_oid IS NULL",
                            (oid, row[0]))
                conn.commit()

            permissions = _load_permissions_for_role(cur, row[3])

            return {
                "auth_type": "azure_ad",
                "user_id": row[0],
                "email": row[1],
                "display_name": row[2],
                "role_name": row[3],
                "role_level": row[4],
                "permissions": permissions,
            }


def _auth_dev_email(email: str) -> dict[str, Any]:
    """Dev mode: lookup user by email without token validation."""
    return _lookup_user(email)


def _load_permissions_for_role(cur, role_name: str) -> set[str]:
    """Load all permissions for a role."""
    cur.execute("""
        SELECT p.permission FROM omnius_permissions p
        JOIN omnius_roles r ON r.id = p.role_id
        WHERE r.name = %s
    """, (role_name,))
    return {row[0] for row in cur.fetchall()}
