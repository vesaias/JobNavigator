"""Establish/refresh the logged-in LinkedIn browser session used by the Chrome-extension import
(`scraper/sources/linkedin_extension.enrich`), separately from the import since password login is
gated behind an email-PIN checkpoint that needs a human to relay the code; persists cookies to
/root/.linkedin_api/li_cookies.json so the import can load them headlessly until they expire."""
import asyncio
import json
import os
import sys

from backend.scraper.sources.linkedin_extension import _SESSION_PATH

PIN_FILE = "/tmp/li_pin.txt"

# Phase of the current refresh (idle | running | awaiting_pin | ok | failed), read by
# GET /api/linkedin/session so the Settings row can prompt for the PIN.
STATE = {"phase": "idle", "detail": ""}


def _phase(phase: str, detail: str = "") -> None:
    STATE["phase"] = phase
    STATE["detail"] = detail


def _creds():
    from backend.models.db import SessionLocal, Setting
    db = SessionLocal()
    try:
        def g(k):
            r = db.query(Setting).filter(Setting.key == k).first()
            return (r.value if r else "") or ""
        return g("linkedin_mock_email").strip(), g("linkedin_mock_password").strip()
    finally:
        db.close()


async def _login_and_save(email, password) -> int:
    from backend.scraper.sources import linkedin_personal as lp
    pw = browser = None
    try:
        pw, browser, context, page = await lp._get_linkedin_browser()
        await page.goto("https://www.linkedin.com/login",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        if "/feed" not in page.url and "/jobs" not in page.url:
            # Login form fields expose only autocomplete=username/current-password (no <form>,
            # localized submit button) — fill by autocomplete attr and submit with Enter.
            await page.locator('input[autocomplete="username"]:visible').first.fill(email)
            await asyncio.sleep(0.4)
            await page.locator('input[autocomplete="current-password"]:visible').first.fill(password)
            await asyncio.sleep(0.4)
            await page.locator('input[autocomplete="current-password"]:visible').first.press("Enter")
            try:
                await page.wait_for_url(
                    lambda u: "/feed" in u or "/jobs" in u or "/checkpoint" in u,
                    timeout=30000)
            except Exception:
                pass
            if "/checkpoint" in page.url or "/challenge" in page.url:
                if not await _solve_pin(page):
                    return 1
            elif "/login" in page.url:
                print("Still on login page — wrong credentials?")
                return 1

        # Verify against Voyager before saving (csrf-token header is required).
        me = await page.evaluate(
            "async () => {"
            "  const csrf=(document.cookie.match(/JSESSIONID=\"?([^;\"]+)/)||[])[1]||'';"
            "  return (await fetch('https://www.linkedin.com/voyager/api/me',"
            "    {credentials:'include', headers:{'csrf-token':csrf}})).status;"
            "}")
        if me != 200:
            print(f"Session check failed (voyager /me = {me}); not saving.")
            return 1

        cookies = await context.cookies()
        cookies = [c for c in cookies if "linkedin" in c.get("domain", "")]
        os.makedirs(os.path.dirname(_SESSION_PATH), exist_ok=True)
        with open(_SESSION_PATH, "w") as f:
            json.dump(cookies, f)
        print(f"Session OK (voyager /me=200). Saved {len(cookies)} cookies -> {_SESSION_PATH}")
        return 0
    finally:
        try:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass


async def _solve_pin(page) -> bool:
    """Handle the email-PIN checkpoint by polling PIN_FILE (up to 300s)."""
    pin_box = page.locator("#input__email_verification_pin")
    try:
        await pin_box.wait_for(timeout=8000)
    except Exception:
        print(f"Checkpoint is not an email-PIN type (url={page.url}).")
        return False
    if os.path.exists(PIN_FILE):
        os.remove(PIN_FILE)
    print(f"CHECKPOINT: LinkedIn emailed a PIN to the mock account. Drop the 6 "
          f"digits into {PIN_FILE} (waiting up to 300s)...", flush=True)
    _phase("awaiting_pin", "LinkedIn emailed a PIN to the mock account.")
    pin = None
    for _ in range(100):
        if os.path.exists(PIN_FILE):
            pin = "".join(c for c in open(PIN_FILE).read() if c.isdigit())
            if pin:
                break
        await asyncio.sleep(3)
    if not pin:
        print("No PIN provided within 300s.")
        return False
    print(f"Got PIN ({len(pin)} digits), submitting...", flush=True)
    _phase("running", "Submitting the PIN…")
    await pin_box.fill(pin)
    await page.locator("#email-pin-submit-button").click()
    try:
        await page.wait_for_url(lambda u: "/feed" in u or "/jobs" in u, timeout=30000)
    except Exception:
        if "/checkpoint" in page.url or "/challenge" in page.url:
            print("PIN rejected or a second challenge followed.")
            return False
    try:
        os.remove(PIN_FILE)
    except OSError:
        pass
    return True


async def run_refresh() -> int:
    """Entry point for the Settings row: same flow as the CLI, but keeps STATE updated so the UI can follow along."""
    email, password = _creds()
    if not email or not password:
        _phase("failed", "Mock account email/password are not set.")
        return 2
    _phase("running", "Signing in as " + email)
    try:
        code = await _login_and_save(email, password)
    except Exception as e:  # noqa: BLE001 - surfaced to the UI verbatim
        _phase("failed", str(e)[:200])
        return 1
    _phase("ok" if code == 0 else "failed",
           "Session refreshed." if code == 0 else "Login did not complete — see backend logs.")
    return code


def main() -> int:
    email, password = _creds()
    if not email or not password:
        print("linkedin_mock_email / linkedin_mock_password not set.")
        return 2
    print(f"Logging in as {email} via Playwright...", flush=True)
    return asyncio.run(_login_and_save(email, password))


if __name__ == "__main__":
    sys.exit(main())
