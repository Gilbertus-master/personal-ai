"""
Microsoft Graph API authentication.

Supports three flows, selected automatically based on configuration:

1. **Authorization code flow with client secret** (confidential client)
   — For initial user authentication. Opens browser, user logs in, redirect
   back to localhost:8400, app exchanges code for token using client secret.

2. **Client credentials flow** (confidential client, daemon/background)
   — No user interaction. App authenticates directly with client secret.
   Uses application permissions (not delegated). No refresh token.

3. **Device code flow** (public client, legacy fallback)
   — Used when MS_GRAPH_CLIENT_SECRET is not configured.

Selection logic:
- If MS_GRAPH_CLIENT_SECRET is set → confidential client flows (1 & 2).
- If MS_GRAPH_CLIENT_SECRET is absent → device code flow (3).

Tokens are stored in .ms_graph_token.json (never committed to git).
"""
from __future__ import annotations

import json
import os
import time
import threading
import webbrowser
import secrets
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID", "common")
CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET", "")
SCOPES = os.getenv("MS_GRAPH_SCOPES", "Mail.Read Chat.Read Calendars.Read offline_access")

TOKEN_FILE = Path(__file__).resolve().parents[3] / ".ms_graph_token.json"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8400
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}"


def _is_confidential() -> bool:
    """Return True if client secret is configured (confidential client)."""
    return bool(CLIENT_SECRET)


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def _refresh_token(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token (works for both public and confidential)."""
    data: dict[str, str] = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": SCOPES,
    }
    if _is_confidential():
        data["client_secret"] = CLIENT_SECRET

    resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/token",
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


# ---------------------------------------------------------------------------
# Flow 1: Authorization code flow with client secret (confidential, user)
# ---------------------------------------------------------------------------

class _AuthCodeHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the authorization code from the redirect."""

    auth_code: str | None = None
    state_received: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "error" in params:
            _AuthCodeHandler.error = params["error"][0]
            desc = params.get("error_description", [""])[0]
            body = f"<h2>Authentication failed</h2><p>{_AuthCodeHandler.error}: {desc}</p>"
            self._respond(400, body)
            return

        if "code" in params:
            _AuthCodeHandler.auth_code = params["code"][0]
            _AuthCodeHandler.state_received = params.get("state", [None])[0]
            body = (
                "<h2>Authentication successful</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
            )
            self._respond(200, body)
            return

        self._respond(404, "<h2>Not found</h2>")

    def _respond(self, status: int, body_html: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>MS Graph Auth</title></head><body>"
            f"{body_html}</body></html>"
        )
        self.wfile.write(page.encode())

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress default stderr logging from BaseHTTPRequestHandler."""
        pass


def authorization_code_login() -> dict[str, Any]:
    """
    Interactive authorization code login with client secret.

    Opens the user's browser to the Microsoft login page. After login,
    Microsoft redirects to http://localhost:8400 with the auth code.
    A temporary local HTTP server captures it and exchanges it for tokens.
    """
    _validate_client_id()

    state = secrets.token_urlsafe(32)

    authorize_url = (
        f"{AUTHORITY}/oauth2/v2.0/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
            "response_mode": "query",
        })
    )

    # Reset handler state
    _AuthCodeHandler.auth_code = None
    _AuthCodeHandler.state_received = None
    _AuthCodeHandler.error = None

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _AuthCodeHandler)
    server.timeout = 120  # 2 minutes max wait

    print("\n" + "=" * 60)
    print("MICROSOFT GRAPH — AUTHORIZATION CODE LOGIN")
    print("=" * 60)
    print(f"\nOpening browser for login...")
    print(f"If the browser does not open, visit:\n{authorize_url}\n")
    print(f"Waiting for redirect on {REDIRECT_URI} (max 120s)...\n")

    webbrowser.open(authorize_url)

    # Serve a single request (the redirect)
    server.handle_request()
    server.server_close()

    if _AuthCodeHandler.error:
        raise RuntimeError(
            f"Authorization failed: {_AuthCodeHandler.error}"
        )

    if not _AuthCodeHandler.auth_code:
        raise RuntimeError("No authorization code received — timed out or invalid redirect.")

    if _AuthCodeHandler.state_received != state:
        raise RuntimeError(
            "State mismatch — possible CSRF attack. "
            f"Expected {state!r}, got {_AuthCodeHandler.state_received!r}"
        )

    # Exchange authorization code for tokens
    resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": _AuthCodeHandler.auth_code,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    print("Authorization successful! Token saved.\n")
    return token_data


# ---------------------------------------------------------------------------
# Flow 2: Client credentials flow (confidential, daemon / no user)
# ---------------------------------------------------------------------------

def client_credentials_login() -> dict[str, Any]:
    """
    Client credentials flow — no user interaction.

    Authenticates the application itself (not a user). Uses application
    permissions configured in Azure AD. Does NOT return a refresh token;
    tokens are short-lived and must be re-acquired on expiry.

    Scopes must be in the format https://graph.microsoft.com/.default
    (application permissions, not delegated).
    """
    _validate_client_id()

    resp = requests.post(
        f"{AUTHORITY}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    # Mark as client_credentials so get_access_token knows the flow type
    token_data["_flow"] = "client_credentials"
    _save_token(token_data)
    print("Client credentials authentication successful! Token saved.\n")
    return token_data


# ---------------------------------------------------------------------------
# Flow 3: Device code flow (public client, legacy fallback)
# ---------------------------------------------------------------------------

def device_code_login() -> dict[str, Any]:
    """
    Interactive device code login flow (public client).
    Prints a URL and code for the user to authenticate in browser.
    Used as fallback when MS_GRAPH_CLIENT_SECRET is not set.
    """
    _validate_client_id()

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


# ---------------------------------------------------------------------------
# Unified entry points
# ---------------------------------------------------------------------------

def _validate_client_id() -> None:
    if not CLIENT_ID:
        raise RuntimeError(
            "MS_GRAPH_CLIENT_ID not set in .env. "
            "Register an app at https://portal.azure.com → App registrations."
        )


def login(*, daemon: bool = False) -> dict[str, Any]:
    """
    Authenticate with Microsoft Graph using the best available flow.

    Args:
        daemon: If True and client secret is configured, use client credentials
                flow (no user interaction). Otherwise use authorization code flow.

    Flow selection:
        - client secret set + daemon=True  → client credentials flow
        - client secret set + daemon=False → authorization code flow
        - no client secret                 → device code flow (legacy)
    """
    if _is_confidential():
        if daemon:
            return client_credentials_login()
        return authorization_code_login()
    return device_code_login()


def get_access_token(*, daemon: bool = False) -> str:
    """
    Get a valid access token, refreshing or re-acquiring if needed.

    Args:
        daemon: If True, use client credentials flow for token acquisition
                (only relevant when no cached token exists or token is expired
                without a refresh token).
    """
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
        if refresh:
            token_data = _refresh_token(refresh)
        elif _is_confidential() and token_data.get("_flow") == "client_credentials":
            # Client credentials tokens have no refresh token — re-acquire
            token_data = client_credentials_login()
        else:
            raise RuntimeError(
                "Token expired and no refresh token available. Re-run auth: "
                "python -m app.ingestion.graph_api.auth"
            )

    return token_data["access_token"]


def main() -> None:
    """CLI entry point — run interactive login."""
    import argparse

    parser = argparse.ArgumentParser(description="Microsoft Graph API authentication")
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Use client credentials flow (no user interaction, requires client secret)",
    )
    args = parser.parse_args()

    login(daemon=args.daemon)


if __name__ == "__main__":
    main()
