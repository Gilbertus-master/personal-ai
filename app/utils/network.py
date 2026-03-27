"""
WSL2 SSL-safe networking utilities.

Root cause: WSL2 default MTU (1500) can cause TLS record fragmentation
that trips up the virtual network adapter, producing:
    ssl.SSLError: [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC]

This only affects large HTTPS transfers (>1 MB) because small responses
fit inside single TLS records that don't get fragmented.

Fix: lower MTU to 1400 so IP packets stay under the Hyper-V vSwitch
internal MTU, eliminating mid-record fragmentation.

This module provides:
- ensure_wsl2_mtu()       -- one-shot MTU fix for the current session
- ssl_safe_download()     -- download with chunked streaming + retry
- ssl_safe_get()          -- GET with retry for JSON API responses
"""
from __future__ import annotations

import logging
import shutil
import ssl
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MTU fix
# ---------------------------------------------------------------------------

_WSL2_SAFE_MTU = 1400
_MTU_FIXED = False


def is_wsl2() -> bool:
    """Detect if running inside WSL2."""
    try:
        release = Path("/proc/version").read_text()
        return "microsoft" in release.lower() or "wsl" in release.lower()
    except OSError:
        return False


def get_current_mtu(iface: str = "eth0") -> int | None:
    """Read current MTU for a network interface."""
    try:
        out = subprocess.check_output(
            ["ip", "link", "show", iface],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for token in out.split():
            if token.isdigit():
                val = int(token)
                if 500 <= val <= 9000:  # plausible MTU range
                    return val
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # Parse from sysfs as fallback
    try:
        return int(Path(f"/sys/class/net/{iface}/mtu").read_text().strip())
    except (OSError, ValueError):
        return None


def ensure_wsl2_mtu(target: int = _WSL2_SAFE_MTU) -> bool:
    """
    Lower MTU on eth0 if running on WSL2 and current MTU > target.

    Requires sudo without password (typical WSL2 default) or being run as root.
    Returns True if MTU was changed or already correct, False on failure.
    """
    global _MTU_FIXED
    if _MTU_FIXED:
        return True

    if not is_wsl2():
        log.debug("Not WSL2 -- skipping MTU fix")
        _MTU_FIXED = True
        return True

    current = get_current_mtu()
    if current is not None and current <= target:
        log.debug("MTU already %d (<= %d) -- OK", current, target)
        _MTU_FIXED = True
        return True

    log.info("WSL2 detected with MTU=%s. Lowering to %d to prevent SSL fragmentation errors.",
             current, target)

    try:
        subprocess.check_call(
            ["sudo", "-n", "ip", "link", "set", "dev", "eth0", "mtu", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _MTU_FIXED = True
        log.info("MTU set to %d", target)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.warning(
            "Could not set MTU (need passwordless sudo). "
            "Run manually: sudo ip link set dev eth0 mtu %d\n"
            "Error: %s", target, e,
        )
        return False


# ---------------------------------------------------------------------------
# SSL-resilient HTTP session
# ---------------------------------------------------------------------------

# Retry on these specific errors (SSL bad-record-mac manifests as ConnectionError
# or ssl.SSLError wrapped in urllib3.exceptions.MaxRetryError)
_RETRYABLE_EXCEPTIONS = (
    requests.ConnectionError,
    requests.Timeout,
    ssl.SSLError,
    ConnectionResetError,
    urllib3.exceptions.ProtocolError,
)

_DEFAULT_MAX_RETRIES = 4
_DEFAULT_BACKOFF_BASE = 2  # seconds -- exponential: 2, 4, 8, 16


def _make_session(
    max_retries: int = _DEFAULT_MAX_RETRIES,
    pool_connections: int = 4,
    pool_maxsize: int = 4,
) -> requests.Session:
    """Build a requests.Session with connection pooling and retries."""
    session = requests.Session()

    # urllib3 built-in retry for transport-level errors
    retry = urllib3.util.Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ssl_safe_download(
    url: str,
    output_path: str | Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 300,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    chunk_size: int = 64 * 1024,  # 64 KB -- small chunks to avoid SSL record issues
) -> Path:
    """
    Download a large file with resilience against WSL2 SSL fragmentation errors.

    Strategy:
    1. Fix MTU on first call (one-shot, idempotent).
    2. Stream in small chunks (64 KB) so partial data is saved.
    3. Retry the full download on SSL/connection errors with exponential backoff.
    4. Write to a temp file first, then rename on success.

    Returns the output Path on success; raises on exhausted retries.
    """
    ensure_wsl2_mtu()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    session = _make_session(max_retries=0)  # we handle retry ourselves for streaming

    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            log.debug("ssl_safe_download attempt %d/%d: %s", attempt, max_retries, url)

            with session.get(
                url,
                headers=headers or {},
                timeout=timeout,
                stream=True,
            ) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)

            # Success -- rename
            shutil.move(str(tmp_path), str(output_path))
            log.info("Downloaded %s (%d bytes)", output_path.name, output_path.stat().st_size)
            return output_path

        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            backoff = _DEFAULT_BACKOFF_BASE ** attempt
            log.warning(
                "ssl_safe_download attempt %d/%d failed (%s: %s). Retrying in %ds...",
                attempt, max_retries, type(exc).__name__, exc, backoff,
            )
            # Clean up partial file
            tmp_path.unlink(missing_ok=True)
            time.sleep(backoff)

        except requests.HTTPError:
            # Non-retryable HTTP error (4xx)
            tmp_path.unlink(missing_ok=True)
            raise

    # Exhausted retries -- fall back to curl -k (works reliably in WSL2 with MTU issues)
    log.warning("ssl_safe_download: Python requests exhausted, falling back to curl -k")
    tmp_path.unlink(missing_ok=True)
    try:
        header_args: list[str] = []
        for k, v in (headers or {}).items():
            header_args += ["-H", f"{k}: {v}"]
        result = subprocess.run(
            ["curl", "-k", "-L", "-s", "-o", str(output_path)] + header_args + [url],
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            log.info("curl fallback succeeded: %s (%d bytes)", output_path.name, output_path.stat().st_size)
            return output_path
        else:
            log.error("curl fallback failed: %s", result.stderr.decode()[:200])
    except Exception as curl_exc:
        log.error("curl fallback exception: %s", curl_exc)

    raise ConnectionError(
        f"ssl_safe_download failed after {max_retries} attempts + curl fallback for {url}"
    ) from last_exc


def ssl_safe_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 120,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> requests.Response:
    """
    Make a GET request with SSL retry resilience.

    Suitable for JSON API calls that might transfer large payloads
    (e.g., base64-encoded email attachments via Graph API).
    """
    ensure_wsl2_mtu()

    session = _make_session(max_retries=0)
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, headers=headers, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            backoff = _DEFAULT_BACKOFF_BASE ** attempt
            log.warning(
                "ssl_safe_get attempt %d/%d failed (%s: %s). Retrying in %ds...",
                attempt, max_retries, type(exc).__name__, exc, backoff,
            )
            time.sleep(backoff)
        except requests.HTTPError:
            raise

    raise ConnectionError(
        f"ssl_safe_get failed after {max_retries} attempts for {url}"
    ) from last_exc
