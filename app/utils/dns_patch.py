"""
DNS patch for WSL2 environments where api.openai.com DNS resolution fails.
Resolves via DNS-over-HTTPS (Cloudflare) and patches socket.getaddrinfo.
"""
from __future__ import annotations
import socket
import json
import urllib.request
import structlog

log = structlog.get_logger(__name__)

_OVERRIDES: dict[str, str] = {}

def _resolve_via_doh(hostname: str) -> str | None:
    """Resolve hostname via Cloudflare DoH."""
    try:
        req = urllib.request.Request(
            f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A",
            headers={"Accept": "application/dns-json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:
                    return ans["data"]
    except Exception as e:
        log.warning("doh_resolve_failed", hostname=hostname, error=str(e))
    return None

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, str) and host in _OVERRIDES:
        host = _OVERRIDES[host]
    return _original_getaddrinfo(host, port, family, type, proto, flags)

_original_getaddrinfo = socket.getaddrinfo

def apply_dns_patch(hostnames: list[str] | None = None) -> None:
    """Apply DNS patch for given hostnames (or api.openai.com by default)."""
    targets = hostnames or ["api.openai.com"]
    patched = False
    for hostname in targets:
        # Test if DNS works natively first
        try:
            socket.getaddrinfo(hostname, 443)
            continue  # DNS works, no patch needed
        except socket.gaierror:
            pass
        # Resolve via DoH
        ip = _resolve_via_doh(hostname)
        if ip:
            _OVERRIDES[hostname] = ip
            log.info("dns_patch_applied", hostname=hostname, ip=ip)
            patched = True
        else:
            log.warning("dns_patch_failed", hostname=hostname)

    if patched and _patched_getaddrinfo is not socket.getaddrinfo:
        socket.getaddrinfo = _patched_getaddrinfo
    elif patched:
        socket.getaddrinfo = _patched_getaddrinfo
