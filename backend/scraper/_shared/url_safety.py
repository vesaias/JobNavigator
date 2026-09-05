"""URL safety checks to prevent SSRF: anyone who can submit a job URL could otherwise
make the backend fetch cloud metadata, internal services, or LAN peers, including via redirect/DNS rebinding."""
import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("jobnavigator.url_safety")

MAX_REDIRECTS = 3


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF validation."""


# RFC 6598 carrier-grade NAT: Python's ipaddress does NOT flag this as private,
# but Tailscale and some self-hosting overlay nets live here, so it's off-limits.
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


def _is_public_ip(ip: str) -> bool:
    """True iff ip is a globally routable public address (rejects private, loopback, link-local/cloud-metadata, multicast, reserved, and RFC 6598 CGNAT)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return False
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return False
    if isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT_NET:
        return False
    return True


def assert_public_http_url(url: str) -> None:
    """Raise UnsafeURLError if url is not a safe public http(s) URL; requires ALL resolved A/AAAA records to be public, rejecting classic DNS-rebinding payloads."""
    if not url:
        raise UnsafeURLError("Empty URL")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Scheme must be http or https, got {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("Missing host")

    # If the host is a literal IP, validate directly (no DNS lookup needed).
    try:
        ipaddress.ip_address(host)
        if not _is_public_ip(host):
            raise UnsafeURLError(f"Host {host!r} is a non-public IP")
        return
    except ValueError:
        pass  # Hostname, not an IP — fall through to DNS resolution.

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"DNS resolution failed for {host!r}: {e}") from e

    if not infos:
        raise UnsafeURLError(f"No DNS records for {host!r}")

    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeURLError(f"{host!r} resolves to non-public address {ip}")


async def _assert_public_http_url_async(url: str) -> None:
    """Async wrapper — runs DNS lookup on a worker thread."""
    await asyncio.to_thread(assert_public_http_url, url)


async def safe_get(
    url: str,
    *,
    timeout: float = 15.0,
    headers: dict | None = None,
) -> httpx.Response:
    """httpx.get with SSRF protection: walks up to MAX_REDIRECTS hops manually, re-validating each Location target, and raises UnsafeURLError on any unsafe URL in the chain."""
    current = url
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _assert_public_http_url_async(current)
            resp = await client.get(current, headers=headers or {})
            if resp.is_redirect:
                loc = resp.headers.get("location")
                if not loc:
                    return resp
                current = urljoin(current, loc)
                continue
            return resp
        raise UnsafeURLError(f"Too many redirects (>{MAX_REDIRECTS}) starting at {url!r}")
