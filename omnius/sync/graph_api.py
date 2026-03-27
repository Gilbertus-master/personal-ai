"""Omnius M365 sync — Graph API auth and sync orchestrator for a company tenant.

Uses client credentials flow (application permissions) to sync
Teams messages, SharePoint documents, and calendar events.

All HTTP calls use httpx (async-safe). Sync functions use httpx sync client
for cron/background usage. Token cache is thread-safe.
"""
from __future__ import annotations

import os
import threading
import time

import httpx
import structlog
from dotenv import load_dotenv

load_dotenv()
log = structlog.get_logger(__name__)

TENANT_ID = os.getenv("OMNIUS_AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("OMNIUS_GRAPH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("OMNIUS_GRAPH_CLIENT_SECRET", "")

_token_cache: dict = {"access_token": None, "expires_at": 0.0}
_token_lock = threading.Lock()


def get_graph_token() -> str:
    """Get or refresh Microsoft Graph API token (client credentials). Thread-safe."""
    now = time.time()
    with _token_lock:
        if _token_cache["access_token"] and _token_cache["expires_at"] > now + 300:
            return _token_cache["access_token"]

        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError("OMNIUS_GRAPH_CLIENT_ID and OMNIUS_GRAPH_CLIENT_SECRET required")

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
        resp.raise_for_status()
        data = resp.json()

        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 3600)

        return data["access_token"]


def graph_get(path: str, params: dict | None = None) -> dict:
    """GET request to Microsoft Graph API."""
    token = get_graph_token()
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"https://graph.microsoft.com/v1.0{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
    resp.raise_for_status()
    return resp.json()


def graph_get_all(path: str, params: dict | None = None, max_pages: int = 50) -> list[dict]:
    """GET with pagination — follows @odata.nextLink."""
    results = []
    url = f"https://graph.microsoft.com/v1.0{path}"
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    page = 0

    with httpx.Client(timeout=30.0) as client:
        while url and page < max_pages:
            resp = client.get(url, headers=headers, params=params if page == 0 else None)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            page += 1

    return results
