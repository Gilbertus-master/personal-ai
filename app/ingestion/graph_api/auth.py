"""
Microsoft Graph API authentication.

Uses device code flow for initial auth, then token refresh for subsequent calls.
Tokens are stored in a local file (never committed to git).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID", "common")
CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID", "")
SCOPES = os.getenv("MS_GRAPH_SCOPES", "Mail.Read Chat.Read Calendars.Read offline_access")

TOKEN_FILE = Path(__file__).resolve().parents[3] / ".ms_graph_token.json"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"


def _save_token(token_data: dict[str, Any]) -> None:
    """Save token to local file."""
    token_data["saved_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    TOKEN_FILE.chmod(0o600)


def _load_token() -> dict[str, Any] | None:
    """Load token from local file."""
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _refresh_token(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token."""
    resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


def device_code_login() -> dict[str, Any]:
    """
    Interactive device code login flow.
    Prints a URL and code for the user to authenticate in browser.
    """
    if not CLIENT_ID:
        raise RuntimeError(
            "MS_GRAPH_CLIENT_ID not set in .env. "
            "Register an app at https://portal.azure.com → App registrations → "
            "New registration → Mobile/desktop (public client) → "
            "Add permissions: Mail.Read, Chat.Read, Calendars.Read"
        )

    # Step 1: Request device code
    resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/devicecode",
        data={
            "client_id": CLIENT_ID,
            "scope": SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    device_data = resp.json()

    print("\n" + "=" * 60)
    print("MICROSOFT GRAPH — DEVICE CODE LOGIN")
    print("=" * 60)
    print(f"\n1. Otwórz: {device_data['verification_uri']}")
    print(f"2. Wpisz kod: {device_data['user_code']}")
    print(f"\nCzekam na autoryzację (max {device_data['expires_in']}s)...\n")

    # Step 2: Poll for token
    interval = device_data.get("interval", 5)
    expires_at = time.time() + device_data["expires_in"]

    while time.time() < expires_at:
        time.sleep(interval)
        token_resp = requests.post(
            f"{AUTHORITY}/oauth2/v2.0/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_data["device_code"],
            },
            timeout=30,
        )

        token_data = token_resp.json()
        if "access_token" in token_data:
            _save_token(token_data)
            print("Autoryzacja udana! Token zapisany.\n")
            return token_data

        error = token_data.get("error")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
        else:
            raise RuntimeError(f"Auth error: {error} — {token_data.get('error_description')}")

    raise RuntimeError("Device code flow timed out")


def get_access_token() -> str:
    """Get a valid access token, refreshing if needed."""
    token_data = _load_token()

    if not token_data:
        raise RuntimeError(
            "No Microsoft Graph token found. Run: "
            "python -m app.ingestion.graph_api.auth"
        )

    # Check if token is expired (with 5 min buffer)
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 3600)
    if time.time() > saved_at + expires_in - 300:
        refresh = token_data.get("refresh_token")
        if not refresh:
            raise RuntimeError("Token expired and no refresh token. Re-run auth.")
        token_data = _refresh_token(refresh)

    return token_data["access_token"]


def main() -> None:
    """Run interactive device code login."""
    device_code_login()


if __name__ == "__main__":
    main()
