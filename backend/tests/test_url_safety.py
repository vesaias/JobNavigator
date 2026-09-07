"""Tests for SSRF defense in scraper/_shared/url_safety.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.scraper._shared.url_safety import (
    UnsafeURLError,
    _is_public_ip,
    assert_public_http_url,
    resolve_public_http_url,
    safe_get,
)


# ── _is_public_ip ────────────────────────────────────────────────────────────

class TestIsPublicIP:
    def test_public_ipv4(self):
        assert _is_public_ip("8.8.8.8") is True
        assert _is_public_ip("1.1.1.1") is True

    def test_private_ranges_rejected(self):
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            assert _is_public_ip(ip) is False, f"{ip} should be rejected"

    def test_loopback_rejected(self):
        assert _is_public_ip("127.0.0.1") is False
        assert _is_public_ip("::1") is False

    def test_cloud_metadata_rejected(self):
        """AWS/GCP/Azure metadata at 169.254.169.254 is link-local."""
        assert _is_public_ip("169.254.169.254") is False

    def test_cgnat_rejected(self):
        """100.64/10 is carrier-grade NAT / Tailscale — reserved."""
        assert _is_public_ip("100.64.0.1") is False

    def test_multicast_rejected(self):
        assert _is_public_ip("224.0.0.1") is False

    def test_unspecified_rejected(self):
        assert _is_public_ip("0.0.0.0") is False

    def test_malformed_rejected(self):
        assert _is_public_ip("not-an-ip") is False
        assert _is_public_ip("") is False

    @pytest.mark.parametrize("ip", [
        "::ffff:127.0.0.1",        # IPv4-mapped loopback
        "::ffff:169.254.169.254",  # IPv4-mapped cloud metadata
        "::ffff:10.0.0.1",
        "2002:7f00:0001::",        # 6to4 wrapping 127.0.0.1
        "2002:a9fe:a9fe::",        # 6to4 wrapping 169.254.169.254
        "64:ff9b::7f00:1",         # NAT64 wrapping 127.0.0.1
        "64:ff9b::a00:1",          # NAT64 wrapping 10.0.0.1
        "fd00::1",                 # unique-local
        "fe80::1",                 # link-local
        "fec0::1",                 # site-local
        "::",                      # unspecified
    ])
    def test_ipv6_forms_that_reach_private_space_are_rejected(self, ip):
        assert _is_public_ip(ip) is False, f"{ip} should be rejected"

    def test_public_ipv6_still_accepted(self):
        assert _is_public_ip("2001:4860:4860::8888") is True
        assert _is_public_ip("2002:0808:0808::") is True  # 6to4 wrapping 8.8.8.8


# ── assert_public_http_url ───────────────────────────────────────────────────

class TestAssertPublicURL:
    def test_rejects_empty(self):
        with pytest.raises(UnsafeURLError):
            assert_public_http_url("")

    def test_rejects_wrong_scheme(self):
        for url in (
            "file:///etc/passwd",
            "gopher://localhost/",
            "ftp://internal/",
            "javascript:alert(1)",
        ):
            with pytest.raises(UnsafeURLError, match="Scheme"):
                assert_public_http_url(url)

    def test_rejects_literal_private_ip(self):
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://192.168.1.1:8080/",
            "http://169.254.169.254/latest/meta-data/",
        ):
            with pytest.raises(UnsafeURLError):
                assert_public_http_url(url)

    def test_rejects_ipv6_loopback(self):
        with pytest.raises(UnsafeURLError):
            assert_public_http_url("http://[::1]/")

    def test_rejects_private_hostname(self, monkeypatch):
        """Attacker sets `evil.com` A record to 10.0.0.1 → rejected."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("10.0.0.1", 0))],
        )
        with pytest.raises(UnsafeURLError, match="non-public"):
            assert_public_http_url("http://evil.com/")

    def test_rejects_any_private_resolution(self, monkeypatch):
        """If host resolves to mixed records, ONE private record → reject.
        Prevents DNS-rebinding where attacker serves one public + one private."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("127.0.0.1", 0)),
            ],
        )
        with pytest.raises(UnsafeURLError):
            assert_public_http_url("http://mixed.example/")

    def test_accepts_public_hostname(self, monkeypatch):
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        assert_public_http_url("https://jobs.lever.co/acme/abc-123")

    def test_rejects_unresolvable_host(self, monkeypatch):
        import socket as _socket
        def raiser(host, port):
            raise _socket.gaierror("Name or service not known")
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo", raiser,
        )
        with pytest.raises(UnsafeURLError, match="DNS resolution"):
            assert_public_http_url("http://nonexistent.example/")

    def test_missing_host(self):
        with pytest.raises(UnsafeURLError, match="host"):
            assert_public_http_url("http:///just-a-path")

    @pytest.mark.parametrize("url", [
        "http://2130706433/",          # decimal 127.0.0.1
        "http://0x7f000001/",          # hex 127.0.0.1
        "http://0177.0.0.1/",          # octal first octet
        "http://127.1/",               # short form
        "http://2852039166/",          # decimal 169.254.169.254
        "http://0/",                   # 0.0.0.0
    ])
    def test_rejects_legacy_numeric_ip_spellings(self, url, monkeypatch):
        """These never reach DNS: `ipaddress` refuses them but the C resolver would route them to loopback."""
        def boom(*a, **kw):
            raise AssertionError("must not hit DNS — the host is a numeric IP form")
        monkeypatch.setattr("backend.scraper._shared.url_safety.socket.getaddrinfo", boom)
        with pytest.raises(UnsafeURLError, match="non-public"):
            assert_public_http_url(url)

    @pytest.mark.parametrize("url", [
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:169.254.169.254]/",
        "http://[fd00::1]/",
        "http://[fe80::1]/",
        "http://[2002:7f00:1::]/",
    ])
    def test_rejects_ipv6_wrappers_around_private_space(self, url):
        with pytest.raises(UnsafeURLError):
            assert_public_http_url(url)

    def test_rejects_a_malformed_port(self):
        with pytest.raises(UnsafeURLError):
            assert_public_http_url("http://example.com:notaport/x")

    def test_userinfo_does_not_smuggle_a_host(self):
        """`http://good.example@127.0.0.1/` targets 127.0.0.1, not good.example."""
        with pytest.raises(UnsafeURLError, match="non-public"):
            assert_public_http_url("http://good.example@127.0.0.1/")


# ── resolve_public_http_url · the pinned target ──────────────────────────────

class TestResolvedURL:
    def test_pins_the_request_to_the_resolved_ip(self, monkeypatch):
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        target = resolve_public_http_url("https://jobs.lever.co/acme/abc?x=1#frag")
        assert target.request_url == "https://8.8.8.8/acme/abc?x=1"
        assert target.host_header == "jobs.lever.co"
        assert target.sni_hostname == "jobs.lever.co"
        assert target.ip == "8.8.8.8"
        assert target.logical_url == "https://jobs.lever.co/acme/abc?x=1#frag"

    def test_keeps_a_non_default_port(self, monkeypatch):
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        target = resolve_public_http_url("http://boards.example:8080/")
        assert target.request_url == "http://8.8.8.8:8080/"
        assert target.host_header == "boards.example:8080"

    def test_ipv6_literal_is_bracketed(self):
        target = resolve_public_http_url("https://[2001:4860:4860::8888]/x")
        assert target.request_url == "https://[2001:4860:4860::8888]/x"

    def test_ipv4_is_preferred_and_every_answer_is_kept(self, monkeypatch):
        """A v4-only container must not stall on the AAAA answer, but the AAAA stays as a fallback."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [
                (None, None, None, None, ("2001:4860:4860::8888", 0)),
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("8.8.4.4", 0)),
            ],
        )
        target = resolve_public_http_url("https://a.example/")
        assert target.ips == ("8.8.8.8", "8.8.4.4", "2001:4860:4860::8888")
        assert target.request_url == "https://8.8.8.8/"

    def test_empty_path_becomes_root(self, monkeypatch):
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        assert resolve_public_http_url("https://a.example").request_url == "https://8.8.8.8/"


# ── safe_get ─────────────────────────────────────────────────────────────────

class TestSafeGet:
    def _make_resp(self, *, status=200, is_redirect=False, location=None, text=""):
        resp = MagicMock()
        resp.status_code = status
        resp.is_redirect = is_redirect
        resp.text = text
        resp.headers = {"location": location} if location else {}
        return resp

    @pytest.mark.asyncio
    async def test_blocks_literal_private_ip(self):
        with pytest.raises(UnsafeURLError):
            await safe_get("http://127.0.0.1/")

    @pytest.mark.asyncio
    async def test_blocks_cloud_metadata(self):
        with pytest.raises(UnsafeURLError):
            await safe_get("http://169.254.169.254/latest/meta-data/")

    @pytest.mark.asyncio
    async def test_successful_fetch(self, monkeypatch):
        """Happy path: public host, 200 response, no redirects."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        resp = self._make_resp(status=200, text="ok")
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        out = await safe_get("https://jobs.lever.co/acme/abc")
        assert out.status_code == 200
        assert out.text == "ok"

    @pytest.mark.asyncio
    async def test_rejects_redirect_to_private(self, monkeypatch):
        """A 302 from public.com → http://10.0.0.1/ must be rejected on the
        second hop even though the first hop was safe."""
        call_count = {"n": 0}

        def fake_resolve(host, port):
            call_count["n"] += 1
            if host == "10.0.0.1":
                return [(None, None, None, None, ("10.0.0.1", 0))]
            # Literal IPs short-circuit on ipaddress.ip_address before getaddrinfo is called.
            return [(None, None, None, None, ("8.8.8.8", 0))]

        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo", fake_resolve,
        )

        redirect_resp = self._make_resp(
            status=302, is_redirect=True, location="http://10.0.0.1/secret",
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=redirect_resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        with pytest.raises(UnsafeURLError, match="non-public"):
            await safe_get("https://safe.example/")

    @pytest.mark.asyncio
    async def test_follows_safe_redirect_chain(self, monkeypatch):
        """Redirect from public A → public B → public C with final 200."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )

        responses = [
            self._make_resp(status=302, is_redirect=True, location="https://b.example/"),
            self._make_resp(status=302, is_redirect=True, location="https://c.example/"),
            self._make_resp(status=200, text="final"),
        ]
        client = MagicMock()
        client.get = AsyncMock(side_effect=responses)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        resp = await safe_get("https://a.example/")
        assert resp.text == "final"

    @pytest.mark.asyncio
    async def test_caps_redirect_chain(self, monkeypatch):
        """Infinite redirects are capped at MAX_REDIRECTS + 1 hops."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        infinite = self._make_resp(status=302, is_redirect=True, location="https://loop.example/")
        client = MagicMock()
        client.get = AsyncMock(return_value=infinite)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        with pytest.raises(UnsafeURLError, match="Too many redirects"):
            await safe_get("https://start.example/")

    @pytest.mark.asyncio
    async def test_connects_to_the_resolved_ip_not_the_hostname(self, monkeypatch):
        """The request target is the resolved IP: a record that flips to 127.0.0.1 after
        validation (DNS rebinding) is never looked up a second time."""
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        resp = self._make_resp(status=200, text="ok")
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        await safe_get("https://jobs.lever.co/acme/abc", headers={"User-Agent": "x"})
        args, kwargs = client.get.call_args
        assert args[0] == "https://8.8.8.8/acme/abc"
        assert kwargs["headers"]["Host"] == "jobs.lever.co"
        assert kwargs["headers"]["User-Agent"] == "x"
        assert kwargs["extensions"]["sni_hostname"] == "jobs.lever.co"

    @pytest.mark.asyncio
    async def test_every_hop_is_pinned_and_revalidated(self, monkeypatch):
        """The second hop resolves on its own; a rebind on hop 2 is caught before the fetch."""
        resolutions = {"a.example": "8.8.8.8", "b.example": "10.0.0.7"}
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, (resolutions[host], 0))],
        )
        client = MagicMock()
        client.get = AsyncMock(return_value=self._make_resp(
            status=302, is_redirect=True, location="https://b.example/next"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        with pytest.raises(UnsafeURLError, match="non-public"):
            await safe_get("https://a.example/")
        assert client.get.call_count == 1
        assert client.get.call_args[0][0] == "https://8.8.8.8/"

    @pytest.mark.asyncio
    async def test_falls_back_to_the_next_validated_address(self, monkeypatch):
        """An unreachable first address (no IPv6 route, dead A record) tries the next one."""
        import httpx as _httpx

        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("8.8.4.4", 0)),
            ],
        )
        ok = self._make_resp(status=200, text="second")
        client = MagicMock()
        client.get = AsyncMock(side_effect=[_httpx.ConnectError("no route"), ok])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        out = await safe_get("https://a.example/")
        assert out.text == "second"
        assert [c[0][0] for c in client.get.call_args_list] == [
            "https://8.8.8.8/", "https://8.8.4.4/",
        ]

    @pytest.mark.asyncio
    async def test_connect_error_on_every_address_propagates(self, monkeypatch):
        import httpx as _httpx

        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        client = MagicMock()
        client.get = AsyncMock(side_effect=_httpx.ConnectError("no route"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        with pytest.raises(_httpx.ConnectError):
            await safe_get("https://a.example/")

    @pytest.mark.asyncio
    async def test_response_url_reports_the_hostname_url(self, monkeypatch):
        """Callers rewrite relative links against resp.url — it must be the site URL, not the pinned IP."""
        import httpx as _httpx

        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.socket.getaddrinfo",
            lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
        )
        real = _httpx.Response(200, text="ok",
                               request=_httpx.Request("GET", "https://8.8.8.8/acme"))
        client = MagicMock()
        client.get = AsyncMock(return_value=real)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "backend.scraper._shared.url_safety.httpx.AsyncClient",
            lambda **kw: client,
        )

        out = await safe_get("https://jobs.lever.co/acme")
        assert str(out.url) == "https://jobs.lever.co/acme"
