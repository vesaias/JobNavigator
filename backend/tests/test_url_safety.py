"""Tests for SSRF defense in scraper/_shared/url_safety.py (#4)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.scraper._shared.url_safety import (
    UnsafeURLError,
    _is_public_ip,
    assert_public_http_url,
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
        # Should NOT raise
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
            # Treat literal IPs transparently — the validator short-circuits
            # on ipaddress.ip_address before calling getaddrinfo for them.
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
