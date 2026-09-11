"""URL safety checks to prevent SSRF: anyone who can submit a job URL could otherwise
make the backend fetch cloud metadata, internal services, or LAN peers, including via redirect/DNS rebinding.

The guard resolves the host once and hands back a `ResolvedURL` whose request target is
the *resolved IP literal* — the original hostname only survives as the `Host` header and
the TLS SNI/certificate name. Nothing re-resolves between the check and the connection,
so a DNS record that flips to 127.0.0.1 after validation (classic rebinding) can no
longer be reached, and the URL the HTTP client is given is built from resolver output
rather than from the user's string.
"""
import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger("jobnavigator.url_safety")

MAX_REDIRECTS = 3


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF validation."""


# RFC 6598 carrier-grade NAT: Python's ipaddress does NOT flag this as private,
# but Tailscale and some self-hosting overlay nets live here, so it's off-limits.
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
# RFC 6052 NAT64 well-known prefix: 64:ff9b::/96 embeds an IPv4 address in the low 32 bits.
_NAT64_NET = ipaddress.ip_network("64:ff9b::/96")


def _addr_is_public(addr) -> bool:
    """True iff a parsed ipaddress object is globally routable (no embedded-IPv4 unwrapping)."""
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return False
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return False
    if isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT_NET:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.is_site_local:
        return False
    return True


def _embedded_ipv4s(addr: ipaddress.IPv6Address):
    """Yield every IPv4 address an IPv6 address carries inside it (v4-mapped, 6to4, Teredo, NAT64).

    `::ffff:127.0.0.1`, `2002:7f00:1::` and `64:ff9b::7f00:1` are all IPv6 addresses that
    Python does not consider private but that a dual-stack host will happily route to 127.0.0.1.
    """
    for candidate in (addr.ipv4_mapped, addr.sixtofour):
        if candidate is not None:
            yield candidate
    teredo = addr.teredo
    if teredo is not None:
        yield from teredo
    if addr in _NAT64_NET:
        yield ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)


def _is_public_ip(ip: str) -> bool:
    """True iff ip is a globally routable public address (rejects private, loopback, link-local/cloud-metadata, multicast, reserved, RFC 6598 CGNAT, and any IPv6 form embedding a non-public IPv4)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if not _addr_is_public(addr):
        return False
    if isinstance(addr, ipaddress.IPv6Address):
        for v4 in _embedded_ipv4s(addr):
            if not _addr_is_public(v4):
                return False
    return True


def _inet_aton_ipv4(host: str):
    """Parse the legacy `inet_aton` IPv4 spellings the C resolver still accepts, or None.

    `http://2130706433/`, `http://0x7f000001/`, `http://0177.0.0.1/` and `http://127.1/`
    all reach 127.0.0.1 through glibc even though `ipaddress.ip_address()` rejects them.
    """
    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    values = []
    for part in parts:
        if not part:
            return None
        try:
            if part.lower().startswith("0x"):
                value = int(part, 16)
            elif part.startswith("0") and len(part) > 1:
                value = int(part, 8)
            elif part.isdigit():
                value = int(part, 10)
            else:
                return None
        except ValueError:
            return None
        if value < 0:
            return None
        values.append(value)
    if any(v > 0xFF for v in values[:-1]):
        return None
    # The final part absorbs all remaining bytes (127.1 == 127.0.0.1).
    if values[-1] >= 256 ** (4 - (len(values) - 1)):
        return None
    number = values[-1]
    for i, value in enumerate(values[:-1]):
        number += value << (8 * (3 - i))
    try:
        return ipaddress.IPv4Address(number)
    except ValueError:
        return None


def _literal_ip(host: str):
    """Return the IP a host string *is* (textual or legacy numeric form), or None if it is a name."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    return _inet_aton_ipv4(host)


@dataclass(frozen=True)
class ResolvedURL:
    """A URL that passed SSRF validation, pinned to the public IPs it resolved to.

    The request target is assembled from `ips` (resolver output) plus literals — the
    user's URL only contributes the path and query. `host_header` and `sni_hostname`
    carry the original name so virtual hosting and TLS certificate verification still
    work. `ips` keeps every validated answer, IPv4 first, so a host whose AAAA record is
    unreachable from this container still connects over IPv4 (httpx used to do that walk
    itself; pinning takes it over).
    """

    logical_url: str
    tls: bool
    ips: tuple
    port: object
    host_header: str
    sni_hostname: str
    path_and_query: str

    @property
    def ip(self) -> str:
        return self.ips[0]

    def authority(self, ip: str) -> str:
        """`ip[:port]`, bracketed for IPv6 — built only from resolver output."""
        host = f"[{ip}]" if ":" in ip else ip
        return f"{host}:{self.port}" if self.port else host

    @property
    def request_url(self) -> str:
        return ("https://" if self.tls else "http://") + self.authority(self.ip) + self.path_and_query

    def __str__(self) -> str:  # logs should show the human URL, not the pinned one
        return self.logical_url


def _ascii_host(host: str) -> str:
    """IDNA-encode a hostname so it is safe to put in a Host header."""
    try:
        return host.encode("idna").decode("ascii")
    except Exception:
        return host


def _pin(scheme: str, ips: list, port, host: str, path: str, query: str, logical: str) -> ResolvedURL:
    """Assemble the pinned target from resolver output; the user URL contributes path + query only."""
    ascii_host = _ascii_host(host)
    port_part = f":{port}" if port else ""
    return ResolvedURL(
        logical_url=logical,
        # A literal choice, not the parsed scheme, so the request target is never wholly user text.
        tls=(scheme == "https"),
        # IPv4 first: a v4-only container must not stall on an AAAA answer.
        ips=tuple(sorted(ips, key=lambda ip: ":" in ip)),
        port=port,
        host_header=ascii_host + port_part,
        sni_hostname=ascii_host,
        path_and_query=(path or "/") + (("?" + query) if query else ""),
    )


def resolve_public_http_url(url: str) -> ResolvedURL:
    """Validate `url` and pin it to one resolved public IP; raise UnsafeURLError otherwise.

    Every A/AAAA record must be public — a host that mixes one public and one private
    answer is refused outright rather than raced.
    """
    if not url:
        raise UnsafeURLError("Empty URL")
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise UnsafeURLError(f"Scheme must be http or https, got {parsed.scheme!r}")
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError as e:  # a bogus port, e.g. http://host:notaport/
        raise UnsafeURLError(f"Malformed authority in URL: {e}") from e
    if not host:
        raise UnsafeURLError("Missing host")

    literal = _literal_ip(host)
    if literal is not None:
        if not _is_public_ip(str(literal)):
            raise UnsafeURLError(f"Host {host!r} is a non-public IP")
        return _pin(scheme, [str(literal)], port, host, parsed.path, parsed.query, url)

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"DNS resolution failed for {host!r}: {e}") from e

    if not infos:
        raise UnsafeURLError(f"No DNS records for {host!r}")

    ips = []
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeURLError(f"{host!r} resolves to non-public address {ip}")
        if ip not in ips:
            ips.append(ip)

    if not ips:
        raise UnsafeURLError(f"No usable address for {host!r}")
    return _pin(scheme, ips, port, host, parsed.path, parsed.query, url)


def assert_public_http_url(url: str) -> None:
    """Raise UnsafeURLError if url is not a safe public http(s) URL; requires ALL resolved A/AAAA records to be public, rejecting classic DNS-rebinding payloads."""
    resolve_public_http_url(url)


async def _resolve_public_http_url_async(url: str) -> ResolvedURL:
    """Async wrapper — runs DNS lookup on a worker thread."""
    return await asyncio.to_thread(resolve_public_http_url, url)


async def safe_request_once(
    url: str,
    *,
    method: str = "GET",
    timeout: float = 15.0,
    headers: dict | None = None,
    content: bytes | None = None,
    json: object = None,
) -> httpx.Response:
    """Perform one DNS-pinned HTTP request without following redirects.

    The caller must re-submit any redirect target through this function. This is
    useful for browser routing, where Chromium must observe the redirect while
    every hop is still independently pinned and validated.
    """
    target = await _resolve_public_http_url_async(url)
    request_headers = dict(headers or {})
    # These are recomputed by httpx and can become invalid when Playwright's body
    # or httpx's decompressed response is relayed.
    for name in ("host", "content-length", "transfer-encoding", "connection", "accept-encoding"):
        request_headers.pop(name, None)
        request_headers.pop(name.title(), None)
    request_headers["Host"] = target.host_header
    request_headers["Accept-Encoding"] = "identity"
    prefix = "https://" if target.tls else "http://"
    connect_error = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for ip in target.ips:
            try:
                response = await client.request(
                    method,
                    prefix + target.authority(ip) + target.path_and_query,
                    headers=request_headers,
                    content=content,
                    json=json,
                    extensions={"sni_hostname": target.sni_hostname},
                )
                _relabel(response, url)
                return response
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                connect_error = exc
    raise connect_error


async def safe_get(
    url: str,
    *,
    timeout: float = 15.0,
    headers: dict | None = None,
) -> httpx.Response:
    """httpx.get with SSRF protection.

    Each hop is resolved once and fetched from the resolved IP (Host header + TLS SNI keep
    the site working), so nothing can rebind between check and connect. Up to
    MAX_REDIRECTS Location targets are re-validated the same way; anything unsafe in the
    chain raises UnsafeURLError.
    """
    logical = url
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            target = await _resolve_public_http_url_async(logical)
            request_headers = dict(headers or {})
            request_headers["Host"] = target.host_header
            # Built here from resolver output and string literals — the URL the client
            # receives is never the caller's string.
            prefix = "https://" if target.tls else "http://"
            resp = None
            connect_error = None
            for ip in target.ips:
                try:
                    resp = await client.get(
                        prefix + target.authority(ip) + target.path_and_query,
                        headers=request_headers,
                        extensions={"sni_hostname": target.sni_hostname},
                    )
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    connect_error = e  # try the next validated address (v6 → v4)
            if resp is None:
                raise connect_error
            if resp.is_redirect:
                loc = resp.headers.get("location")
                if not loc:
                    _relabel(resp, logical)
                    return resp
                logical = urljoin(logical, loc)
                continue
            _relabel(resp, logical)
            return resp
        raise UnsafeURLError(f"Too many redirects (>{MAX_REDIRECTS}) starting at {url!r}")


async def safe_post(
    url: str,
    *,
    json: object = None,
    timeout: float = 30.0,
    headers: dict | None = None,
) -> httpx.Response:
    """JSON POST with SSRF protection and per-hop redirect revalidation.

    Same pinning as ``safe_get`` (resolve once, connect to the validated IP), but
    every redirect hop re-issues the POST with the same body after revalidating
    the target, so a public entry URL cannot redirect into a private/metadata
    address.
    """
    logical = url
    for _ in range(MAX_REDIRECTS + 1):
        response = await safe_request_once(
            logical, method="POST", json=json, timeout=timeout, headers=headers
        )
        if response.is_redirect:
            loc = response.headers.get("location")
            if not loc:
                return response
            logical = urljoin(logical, loc)
            continue
        return response
    raise UnsafeURLError(f"Too many redirects (>{MAX_REDIRECTS}) starting at {url!r}")


# ── Playwright SSRF guard ─────────────────────────────────────────────────────
# `page.goto()` is not covered by `safe_get`: it resolves and follows redirects
# inside Chromium, so a public entry URL can still land on a private address. This
# route block aborts any request whose destination fails the public-IP check,
# covering navigation, redirects and subresources alike. DNS is intentionally
# re-checked for every request so a previously public host cannot rely on a stale
# positive cache after rebinding.
async def is_public_http_url(url: str) -> bool:
    """True iff ``url`` currently resolves only to public http(s) addresses.

    Deliberately do not cache positive DNS answers: re-check every request so a
    hostname cannot pass once and later rebind to a private address.
    """
    try:
        await _resolve_public_http_url_async(url)
        return True
    except (UnsafeURLError, ValueError):
        return False


async def setup_ssrf_route_block(page) -> None:
    """Proxy every Playwright HTTP request through the DNS-pinned client.

    Merely validating DNS and then calling ``route.continue_()`` is unsafe because
    Chromium resolves the host again, leaving a classic DNS-rebinding TOCTOU. The
    response is therefore fetched from the validated IP and fulfilled into the
    page. Redirect responses are not followed here: Chromium emits the next hop,
    which comes through this same handler and is pinned independently.
    """
    async def _handler(route):
        request = route.request
        url = request.url
        scheme = urlsplit(url).scheme.lower()
        if scheme in ("data", "blob", "about"):
            await route.continue_()
            return
        if scheme not in ("http", "https"):
            logger.warning("SSRF block: aborted non-web request to %s", url)
            await route.abort()
            return
        try:
            body = request.post_data_buffer
            if body is not None and len(body) > 2_000_000:
                raise UnsafeURLError("Browser request body exceeds 2 MB")
            response = await safe_request_once(
                url,
                method=request.method,
                headers=await request.all_headers(),
                content=body,
                timeout=30.0,
            )
            content = response.content
            if len(content) > 20_000_000:
                raise UnsafeURLError("Browser response exceeds 20 MB")
            response_headers = dict(response.headers)
            for name in ("content-encoding", "content-length", "transfer-encoding", "connection"):
                response_headers.pop(name, None)
            await route.fulfill(
                status=response.status_code,
                headers=response_headers,
                body=content,
            )
        except (UnsafeURLError, httpx.HTTPError, ValueError) as exc:
            logger.warning("SSRF block: aborted request to %s (%s)", url, exc)
            await route.abort()

    # Prevent script-created sockets from bypassing HTTP request routing.
    await page.add_init_script(
        """
        (() => {
          const blocked = function () { throw new DOMException('Network socket blocked'); };
          Object.defineProperty(window, 'WebSocket', { value: blocked, configurable: false });
          if ('WebTransport' in window) {
            Object.defineProperty(window, 'WebTransport', { value: blocked, configurable: false });
          }
        })();
        """
    )
    await page.route("**/*", _handler)


def _relabel(resp, logical: str) -> None:
    """Point `resp.url` back at the hostname URL — callers use it to resolve relative asset links, and the pinned IP URL would send those to the wrong origin."""
    try:
        resp.request.url = httpx.URL(logical)
    except Exception:  # a mock, or a response without a request attached
        pass
