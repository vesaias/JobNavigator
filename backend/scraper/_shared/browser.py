"""Playwright lifecycle + stealth constants shared across all scraper modules."""
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger("jobnavigator.scraper.browser")

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-first-run",
    "--no-default-browser-check",
]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


async def _get_browser():
    """Start Playwright and launch a browser with stealth settings.

    `start()` spawns a node driver process; if the chromium launch then fails
    (which is exactly what happens once the box is short on memory) that driver
    used to be left running, because callers only stop what they were handed.
    Each failed attempt leaked a process, so memory pressure fed on itself.
    """
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(
            headless=True,
            args=_STEALTH_ARGS,
        )
    except BaseException:
        try:
            await pw.stop()
        except Exception:
            logger.warning("Playwright driver failed to stop after a failed launch")
        raise
    return pw, browser


async def _new_page(browser, viewport=None):
    """Create a new page with stealth settings applied."""
    ctx = await browser.new_context(
        user_agent=_USER_AGENT,
        viewport=viewport or {"width": 1280, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = await ctx.new_page()
    # Hide webdriver flag
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    # Stash context ref so page.close() can also close context
    page._stealth_ctx = ctx
    return page


async def _close_page(page):
    """Close a stealth page and its context."""
    try:
        ctx = getattr(page, '_stealth_ctx', None)
        await page.close()
        if ctx:
            await ctx.close()
    except Exception:
        pass
