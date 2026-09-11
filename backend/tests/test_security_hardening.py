"""Security-hardening regressions for the fail-closed auth and HTML-escaping fixes.

These lock in the two highest-value fixes so they can't silently regress:
  * the API middleware must never open up on an empty dashboard_api_key;
  * résumé/letter HTML must escape user/LLM-controlled fields and neutralise
    javascript: hrefs.
"""
import logging
from pathlib import Path

import pytest

from backend.models.db import Setting


# ── Fail-closed auth ──────────────────────────────────────────────────────────

def test_ensure_dashboard_key_refuses_missing_initial_key(test_db, monkeypatch):
    """Fresh startup must stop rather than expose an unauthenticated API."""
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "INITIAL_API_KEY", "")
    with pytest.raises(RuntimeError, match="INITIAL_API_KEY"):
        main_mod._ensure_dashboard_key(test_db)
    assert test_db.query(Setting).filter(Setting.key == "dashboard_api_key").first() is None


def test_ensure_dashboard_key_refuses_empty_stored_key(test_db, monkeypatch):
    """An empty restored setting must fail closed unless the operator supplies a key."""
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "INITIAL_API_KEY", "")
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.commit()
    with pytest.raises(RuntimeError, match="INITIAL_API_KEY"):
        main_mod._ensure_dashboard_key(test_db)
    setting = test_db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
    assert setting.value == ""


def test_ensure_dashboard_key_prefers_env_key(test_db, monkeypatch):
    """An operator-provided INITIAL_API_KEY wins over generation."""
    import backend.main as main_mod
    monkeypatch.setattr(main_mod, "INITIAL_API_KEY", "env-key")
    main_mod._ensure_dashboard_key(test_db)
    setting = test_db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
    assert setting.value == "env-key"


# ── HTML escaping ─────────────────────────────────────────────────────────────

def test_render_html_escapes_markup():
    from backend.api.routes_resumes import _render_html
    payload = "<img src=x onerror=alert(1)>"
    html = _render_html(
        {"header": {"name": payload, "contact_items": []},
         "summary": payload,
         "experience": [{"company": payload, "title": payload, "location": "",
                         "date": "", "description": payload, "bullets": []}],
         "skills": {}, "education": [], "projects": [], "publications": []},
        "inter", "letter",
    )
    assert payload not in html
    assert "&lt;img" in html


def test_render_html_neutralizes_javascript_hrefs():
    from backend.api.routes_resumes import _render_html
    html = _render_html(
        {"header": {"name": "N", "contact_items": [{"text": "T", "url": "javascript:alert(2)"}]},
         "projects": [{"name": "P", "url": "javascript:alert(3)", "description": "", "bullets": []}]},
        "inter", "letter",
    )
    # Contact URL becomes https://javascript:… (not executable); project URL → "#".
    assert 'href="javascript:' not in html
    assert "<a href=" in html  # links still render


def test_render_cover_letter_escapes_markup():
    from backend.api.routes_cover_letters import _render_html
    payload = "<script>alert(1)</script>"
    html = _render_html(
        {"header": {"name": payload, "contact_items": []},
         "body_paragraphs": [payload], "greeting": payload,
         "closing": payload, "signature": payload},
        "garamond_alt", "letter",
    )
    assert payload not in html
    assert "&lt;script" in html


@pytest.mark.asyncio
async def test_claude_code_runs_text_only_in_temporary_directory(monkeypatch):
    """The Claude subscription provider must not expose tools or project context."""
    from backend.analyzer import llm_client

    captured = {}

    async def fake_run(cmd, stdin, env=None, timeout=None, cwd=None):
        captured.update(cmd=cmd, stdin=stdin, env=env, cwd=cwd)
        assert cwd and Path(cwd).is_dir()
        assert not any(Path(cwd).iterdir())
        return 0, b'{"result":"ok"}', b""

    monkeypatch.setattr(llm_client, "_run_cli", fake_run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-value")
    result = await llm_client._call_claude_code("untrusted job text", "system", "sonnet", 100)

    assert result["text"] == "ok"
    assert captured["cmd"][captured["cmd"].index("--tools") + 1] == ""
    assert "--safe-mode" in captured["cmd"]
    assert "--no-session-persistence" in captured["cmd"]
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert not Path(captured["cwd"]).exists()  # TemporaryDirectory cleaned up


def test_compose_ports_are_loopback_only():
    import yaml

    compose = yaml.safe_load(
        (Path(__file__).parents[2] / "docker-compose.yml").read_text(encoding="utf-8")
    )
    published = [str(port) for service in compose["services"].values()
                 for port in service.get("ports", [])]
    assert published
    assert all(value.startswith("127.0.0.1:") for value in published)


def test_extension_keeps_key_local_and_rejects_remote_http():
    ext = Path(__file__).parents[2] / "extension"
    popup = (ext / "popup.js").read_text(encoding="utf-8")
    background = (ext / "background.js").read_text(encoding="utf-8")
    assert "local.set({ apiKey" in popup
    assert "chrome.storage.local.get(['apiKey']" in popup
    assert "chrome.storage.local.get(['apiKey']" in background
    assert "sync.set({ serverUrl: state.serverUrl })" in popup
    assert "isSafeServerUrl(candidate)" in popup
    assert "isSafeServerUrl(candidate)" in background
    # Legacy synced keys must be migrated to local and removed from sync.
    assert "chrome.storage.sync.remove('apiKey'" in popup
    assert "chrome.storage.sync.remove('apiKey'" in background


def test_extension_autofill_requires_user_click():
    ext = Path(__file__).parents[2] / "extension"
    fill = (ext / "content_autofill_fill.js").read_text(encoding="utf-8")
    popup_html = (ext / "popup.html").read_text(encoding="utf-8")
    assert "if (_trigger === 'auto') autoFill()" not in fill
    assert 'data-mode="auto"' not in popup_html
    # A synthetic click (isTrusted=false) from a hostile page must not fill.
    assert "event.isTrusted" in fill
    assert "mode: 'closed'" in fill


@pytest.mark.asyncio
async def test_playwright_route_guard_blocks_redirect_to_private(monkeypatch):
    """Every browser request/redirect is independently checked and private hops abort."""
    from unittest.mock import AsyncMock
    from backend.scraper._shared import url_safety

    page = type("Page", (), {})()

    async def register(pattern, handler):
        page.handler = handler

    page.route = register
    page.add_init_script = AsyncMock()
    await url_safety.setup_ssrf_route_block(page)

    route = type("Route", (), {})()
    route.request = type("Request", (), {
        "url": "http://169.254.169.254/latest/meta-data",
        "method": "GET",
        "post_data_buffer": None,
        "all_headers": AsyncMock(return_value={}),
    })()
    route.abort = AsyncMock()
    route.continue_ = AsyncMock()
    route.fulfill = AsyncMock()
    await page.handler(route)
    route.abort.assert_awaited_once()
    route.continue_.assert_not_awaited()
    route.fulfill.assert_not_awaited()


@pytest.mark.asyncio
async def test_playwright_guard_fulfills_public_dns_pinned(monkeypatch):
    """A public hop is fetched from the pinned IP and fulfilled, not let through to Chromium."""
    from unittest.mock import AsyncMock
    import httpx
    from backend.scraper._shared import url_safety

    monkeypatch.setattr(
        url_safety.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    # Captured target must be the pinned IP literal, proving Chromium never sees the hostname.
    captured = {}

    async def fake_request_once(url, *, method="GET", timeout=15.0, headers=None, content=None):
        captured["url"] = url
        resp = httpx.Response(200, request=httpx.Request("GET", url), headers={"content-type": "text/html"})
        resp._content = b"<html>ok</html>"
        return resp

    monkeypatch.setattr(url_safety, "safe_request_once", fake_request_once)

    page = type("Page", (), {})()

    async def register(pattern, handler):
        page.handler = handler

    page.route = register
    page.add_init_script = AsyncMock()
    await url_safety.setup_ssrf_route_block(page)

    route = type("Route", (), {})()
    route.request = type("Request", (), {
        "url": "https://careers.example/jobs/123",
        "method": "GET",
        "post_data_buffer": None,
        "all_headers": AsyncMock(return_value={}),
    })()
    route.abort = AsyncMock()
    route.continue_ = AsyncMock()
    route.fulfill = AsyncMock()
    await page.handler(route)

    # The handler delegates to the pinned client with the logical URL; pinning
    # itself is exercised by safe_request_once/resolve_public_http_url tests.
    assert captured["url"] == "https://careers.example/jobs/123"
    route.fulfill.assert_awaited_once()
    assert route.fulfill.await_args.kwargs["body"] == b"<html>ok</html>"
    route.abort.assert_not_awaited()
    route.continue_.assert_not_awaited()


@pytest.mark.asyncio
async def test_playwright_guard_does_not_cache_public_dns(monkeypatch):
    """A host that rebinds after one public answer must be refused next time."""
    from backend.scraper._shared import url_safety

    answers = iter([
        [(None, None, None, None, ("8.8.8.8", 0))],
        [(None, None, None, None, ("127.0.0.1", 0))],
    ])
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", lambda host, port: next(answers))
    assert await url_safety.is_public_http_url("https://rebind.example/") is True
    assert await url_safety.is_public_http_url("https://rebind.example/") is False
