"""Tests for sources/linkedin_personal.py — LinkedIn /jobs/collections/ scraper."""
import pytest


def test_sources_linkedin_personal_exposes_entry_points():
    from backend.scraper.sources import linkedin_personal
    assert hasattr(linkedin_personal, "run")
    assert hasattr(linkedin_personal, "preview")


def test_run_is_async():
    import asyncio
    from backend.scraper.sources import linkedin_personal
    assert asyncio.iscoroutinefunction(linkedin_personal.run)


def test_preview_is_async():
    import asyncio
    from backend.scraper.sources import linkedin_personal
    assert asyncio.iscoroutinefunction(linkedin_personal.preview)


class _FakeLocator:
    def __init__(self, selector, calls):
        self._selector = selector
        self._calls = calls
        self.first = self

    async def fill(self, value, **kwargs):
        self._calls.append(("fill", self._selector, value))

    async def press(self, key):
        self._calls.append(("press", self._selector, key))


class _FakePage:
    """Records locator use and fails the legacy `page.fill('#username')` path."""

    def __init__(self):
        self.calls = []

    def locator(self, selector):
        return _FakeLocator(selector, self.calls)

    async def fill(self, selector, value):
        raise AssertionError(f"page.fill({selector!r}) — the login page has no such id")

    async def click(self, selector):
        raise AssertionError(f"page.click({selector!r}) — the login page has no submit button")


@pytest.mark.asyncio
async def test_fill_login_form_uses_autocomplete_selectors(monkeypatch):
    import asyncio as _asyncio
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)
    page = _FakePage()
    await lp._fill_login_form(page, "user@example.com", "secret")

    assert page.calls == [
        ("fill", 'input[autocomplete="username"]:visible', "user@example.com"),
        ("fill", 'input[autocomplete="current-password"]:visible', "secret"),
        ("press", 'input[autocomplete="current-password"]:visible', "Enter"),
    ]
    assert _asyncio.iscoroutinefunction(lp._fill_login_form)


class _SessionPage:
    """A page whose voyager /me answer and url the test controls."""

    def __init__(self, url="https://www.linkedin.com/feed/", status=200, raises=False):
        self.url = url
        self._status = status
        self._raises = raises

    async def evaluate(self, _script):
        if self._raises:
            raise RuntimeError("page closed")
        return self._status

    async def goto(self, url, **_kw):
        self.url = url

    def locator(self, selector):
        raise AssertionError(f"locator({selector!r}) — the feed DOM is not a login signal")


class _FakeContext:
    def __init__(self, cookies=None):
        self._cookies = cookies or []

    async def cookies(self):
        return self._cookies


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page,expected",
    [
        (_SessionPage(status=200), True),
        (_SessionPage(status=401), False),
        (_SessionPage(status=0), False),
        (_SessionPage(raises=True), False),
        (_SessionPage(url="https://www.linkedin.com/login", status=200), False),
        (_SessionPage(url="https://www.linkedin.com/checkpoint/ch/login", status=200), False),
    ],
)
async def test_is_logged_in_trusts_voyager_not_the_dom(page, expected):
    from backend.scraper.sources import linkedin_personal as lp
    assert await lp._is_logged_in(page) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,status,has_cookie,expected",
    [
        # /me refuses, but the feed loaded with the auth cookie — a live session.
        ("https://www.linkedin.com/feed/", 401, True, True),
        ("https://www.linkedin.com/jobs/", 0, True, True),
        # No `li_at`: an anonymous visit, however the URL reads.
        ("https://www.linkedin.com/feed/", 401, False, False),
        # A signed-out URL wins even with the cookie still set.
        ("https://www.linkedin.com/login", 401, True, False),
        ("https://www.linkedin.com/uas/login?session_redirect=%2Ffeed%2F", 0, True, False),
        ("https://www.linkedin.com/authwall?trk=x", 0, True, False),
        # /me 200 is definitive regardless of surface or cookie.
        ("https://www.linkedin.com/feed/", 200, False, True),
    ],
)
async def test_is_logged_in_falls_back_to_the_auth_cookie_on_a_signed_in_surface(url, status, has_cookie, expected):
    from backend.scraper.sources import linkedin_personal as lp
    page = _SessionPage(url=url, status=status)
    ctx = _FakeContext([{"name": "li_at", "value": "x"}] if has_cookie
                       else [{"name": "JSESSIONID", "value": "y"}])
    assert await lp._is_logged_in(page, ctx) is expected


@pytest.mark.asyncio
async def test_ensure_logged_in_skips_credential_login_on_a_live_feed(monkeypatch):
    """/me 401 on a live session must not trigger a credential login: /login redirects an
    authenticated browser to the feed, so the login form's username field never renders and
    the fill times out (the reported failure)."""
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)

    page = _SessionPage(status=401)      # goto() lands on /feed/, /me still refuses
    ctx = _FakeContext([{"name": "li_at", "value": "x"}])
    called = {}

    async def fake_login(*_a, **_k):
        called["login"] = True
    monkeypatch.setattr(lp, "_login", fake_login)

    await lp._ensure_logged_in(page, ctx, "user@example.com", "secret")
    assert "login" not in called


@pytest.mark.asyncio
async def test_login_treats_a_fill_timeout_on_a_signed_in_page_as_success(monkeypatch):
    """The reported failure: /login is redirecting to the feed, so the username field never
    renders and the fill times out — on a session that is in fact signed in. That is a login."""
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)

    page = _SessionPage(url="https://www.linkedin.com/login", status=401)
    ctx = _FakeContext([{"name": "li_at", "value": "x"}])

    states = iter([False, True])          # guard sees the login page; after the failed fill, /feed
    async def fake_is_logged_in(_page, _context=None):
        return next(states)
    monkeypatch.setattr(lp, "_is_logged_in", fake_is_logged_in)

    async def fake_fill(*_a, **_k):
        raise RuntimeError("Locator.fill: Timeout 30000ms exceeded")
    monkeypatch.setattr(lp, "_fill_login_form", fake_fill)

    saved = []
    async def fake_save(_c):
        saved.append(True)
    monkeypatch.setattr(lp, "_save_cookies", fake_save)

    await lp._login(page, ctx, "user@example.com", "secret")
    assert saved == [True]


@pytest.mark.asyncio
async def test_login_reraises_a_fill_failure_when_not_signed_in(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)

    page = _SessionPage(url="https://www.linkedin.com/login", status=401)
    ctx = _FakeContext([{"name": "li_at", "value": "x"}])

    async def fake_is_logged_in(_page, _context=None):
        return False
    monkeypatch.setattr(lp, "_is_logged_in", fake_is_logged_in)

    async def fake_fill(*_a, **_k):
        raise RuntimeError("Locator.fill: Timeout 30000ms exceeded")
    monkeypatch.setattr(lp, "_fill_login_form", fake_fill)

    with pytest.raises(RuntimeError, match="Timeout"):
        await lp._login(page, ctx, "user@example.com", "secret")


@pytest.mark.asyncio
async def test_login_skips_the_form_when_login_redirects_to_the_feed(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)

    page = _SessionPage(url="https://www.linkedin.com/login", status=401)

    async def _goto(_url, **_kw):
        page.url = "https://www.linkedin.com/feed/"   # LinkedIn redirects a live session
    page.goto = _goto

    ctx = _FakeContext([{"name": "li_at", "value": "x"}])
    filled, saved = [], []

    async def fake_fill(*_a, **_k):
        filled.append(True)

    async def fake_save(_c):
        saved.append(True)

    monkeypatch.setattr(lp, "_fill_login_form", fake_fill)
    monkeypatch.setattr(lp, "_save_cookies", fake_save)

    await lp._login(page, ctx, "user@example.com", "secret")
    assert filled == [] and saved == [True]


def _login_until_wait(monkeypatch, lp, page_url, wait_raises=True):
    """Shared setup for the credential-login outcome tests: fill succeeds (or not), then
    wait_for_url either passes or raises, leaving the page on `page_url`."""
    page = _SessionPage(url=page_url, status=401)
    ctx = _FakeContext([{"name": "li_at", "value": "x"}])

    async def _goto(_url, **_kw):
        page.url = page_url          # where the browser actually ends up after goto
    page.goto = _goto

    async def not_logged_in(*_a, **_k):
        return False
    monkeypatch.setattr(lp, "_is_logged_in", not_logged_in)

    async def fake_fill(*_a, **_k):
        return None

    async def fake_wait(*_a, **_k):
        if wait_raises:
            raise RuntimeError("wait_for_url timed out")

    page.wait_for_url = fake_wait
    monkeypatch.setattr(lp, "_fill_login_form", fake_fill)

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)
    return page, ctx


@pytest.mark.asyncio
async def test_login_fills_the_form_and_saves_cookies(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    page, ctx = _login_until_wait(monkeypatch, lp, "https://www.linkedin.com/login", wait_raises=False)
    saved = []

    async def fake_save(_c):
        saved.append(True)
    monkeypatch.setattr(lp, "_save_cookies", fake_save)

    await lp._login(page, ctx, "user@example.com", "secret")
    assert saved == [True]


@pytest.mark.asyncio
async def test_login_reports_a_security_challenge(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    page, ctx = _login_until_wait(monkeypatch, lp, "https://www.linkedin.com/checkpoint/challenge")
    with pytest.raises(RuntimeError, match="security challenge"):
        await lp._login(page, ctx, "user@example.com", "secret")


@pytest.mark.asyncio
async def test_login_reports_still_on_the_login_page(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    page, ctx = _login_until_wait(monkeypatch, lp, "https://www.linkedin.com/login")
    with pytest.raises(RuntimeError, match="Check credentials"):
        await lp._login(page, ctx, "user@example.com", "secret")


@pytest.mark.asyncio
async def test_login_reports_an_unexpected_landing(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp
    page, ctx = _login_until_wait(monkeypatch, lp, "https://www.linkedin.com/somewhere-else")
    with pytest.raises(RuntimeError, match="unexpected page"):
        await lp._login(page, ctx, "user@example.com", "secret")


@pytest.mark.asyncio
async def test_ensure_logged_in_without_credentials_asks_for_them(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp

    async def not_logged_in(*_a, **_k):
        return False
    monkeypatch.setattr(lp, "_is_logged_in", not_logged_in)

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)

    page = _SessionPage(url="https://www.linkedin.com/login", status=401)
    with pytest.raises(RuntimeError, match="no credentials configured"):
        await lp._ensure_logged_in(page, _FakeContext([]), "", "")


@pytest.mark.asyncio
async def test_ensure_logged_in_returns_on_a_live_session(monkeypatch):
    from backend.scraper.sources import linkedin_personal as lp

    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(lp.asyncio, "sleep", _no_sleep)
    called = []

    async def fake_login(*_a, **_k):
        called.append(True)
    monkeypatch.setattr(lp, "_login", fake_login)

    page = _SessionPage(status=200)          # /me answers 200 → live session
    await lp._ensure_logged_in(page, _FakeContext([]), "user@example.com", "secret")
    assert called == []


@pytest.mark.asyncio
async def test_has_auth_cookie_is_false_when_cookies_raise():
    from backend.scraper.sources import linkedin_personal as lp

    class _Boom:
        async def cookies(self):
            raise RuntimeError("no browser context")

    assert await lp._has_auth_cookie(_Boom()) is False


@pytest.mark.asyncio
async def test_is_logged_in_is_false_when_the_url_is_unreadable():
    from backend.scraper.sources import linkedin_personal as lp

    class _Boom:
        @property
        def url(self):
            raise RuntimeError("target closed")

        async def evaluate(self, _script):
            return 200

    assert await lp._is_logged_in(_Boom()) is False
