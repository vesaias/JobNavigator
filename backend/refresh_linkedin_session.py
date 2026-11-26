"""Sign one of the two LinkedIn sessions in (direct-links plan, Task 8). Password login is gated
behind an email-PIN checkpoint that needs a human to relay the code, so it runs apart from the
scrapers and saves the cookies for them:

- `mock`: the mock account (linkedin_mock_email / _password), saved to the extension jar
  (/root/.linkedin_api/li_cookies.json) that the LinkedIn import and the employer-link lookup use.
- `main`: the user's own account (linkedin_email / _password), saved to the LinkedIn Personal jar.

Each jar gets a `<jar>.account` record of whose session it holds; the lookup reads it."""
import asyncio
import json
import os
import sys

from backend.accounts import credentials as _cred

MOCK = "mock"
MAIN = "main"
SESSIONS = (MOCK, MAIN)

# Phase of the current sign-in per session (idle | running | awaiting_pin | ok | failed), read by
# GET /api/linkedin/session so the Settings row can prompt for the PIN. STATES is the owner's; a
# member's live in _MEMBER_STATES (MT-16: sessions, PIN drops and phases are per account).
STATES = {MOCK: {"phase": "idle", "detail": ""}, MAIN: {"phase": "idle", "detail": ""}}
_MEMBER_STATES: dict = {}


def state(which: str = MOCK) -> dict:
    """The phase dict of the current account's sign-in of one session."""
    member = _cred.session_member()
    if member is None:
        return STATES[which]
    return _MEMBER_STATES.setdefault((member, which), {"phase": "idle", "detail": ""})


def jar(which: str = MOCK) -> str:
    """The current account's cookie jar of one session."""
    return _cred.linkedin_extension_cookies() if which == MOCK else _cred.linkedin_personal_cookies()


def pin_file(which: str = MOCK) -> str:
    base = _cred.linkedin_pin_file()
    return base if which == MOCK else base + ".main"


def _record_path(which: str) -> str:
    return jar(which) + ".account"


def record_sign_in(which: str, email: str) -> None:
    """Note whose session the jar holds (the lookup runs only on a jar the mock account signed)."""
    path = _record_path(which)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump({"account": which, "email": email}, f)


def signed_in_as(which: str):
    """{"account", "email"} of the last sign-in that saved this jar, or None."""
    try:
        with open(_record_path(which)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("account") in SESSIONS else None
    except (OSError, ValueError):
        return None


def _phase(phase: str, detail: str = "", which: str = MOCK) -> None:
    st = state(which)
    st["phase"] = phase
    st["detail"] = detail


def _creds(which: str = MOCK):
    """(email, password, missing-message) of the account one session signs in with."""
    from backend.models.db import SessionLocal
    from backend.accounts.settings import get_setting
    db = SessionLocal()
    try:
        def g(k):
            return (get_setting(db, k) or "").strip()
        if which == MOCK:
            return (g("linkedin_mock_email"), g("linkedin_mock_password"),
                    "Mock account email/password are not set.")
        return (g("linkedin_email"), g("linkedin_password"), "Main account email/password are not set.")
    finally:
        db.close()


async def _login_and_save(email, password, which: str = MOCK) -> int:
    """Sign `which` in and save its jar. The mock sign-in starts from an empty jar: the helper
    loads the main account's cookies, and /login would otherwise redirect to that feed and save
    the main session as the mock's. The main sign-in may reuse them."""
    fresh = which == MOCK
    from backend.scraper.sources import linkedin_personal as lp
    pw = browser = None
    try:
        pw, browser, context, page = await lp._get_linkedin_browser()
        if fresh:
            await context.clear_cookies()
        await page.goto("https://www.linkedin.com/login",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # An authenticated session redirects /login to the feed, so the username field never
        # renders. The redirect can still be in flight when we look, so check the session
        # itself and, if the fill then races the redirect, take a signed-in page as a login
        # instead of waiting out the field (the same guard linkedin_personal._login uses).
        # A fresh sign-in has no session to redirect, so it keeps the longer wait.
        if not await lp._is_logged_in(page, context):
            try:
                await lp._fill_login_form(page, email, password,
                                          timeout=30000 if fresh else 10000)
            except Exception:
                if not await lp._is_logged_in(page, context):
                    raise
            try:
                await page.wait_for_url(
                    lambda u: "/feed" in u or "/jobs" in u or "/checkpoint" in u,
                    timeout=30000)
            except Exception:
                pass
            if "/checkpoint" in page.url or "/challenge" in page.url:
                if not await _solve_pin(page, which):
                    return 1
            elif "/login" in page.url and not await lp._is_logged_in(page, context):
                print("Still on login page — wrong credentials?")
                return 1

        # Verify against Voyager before saving (csrf-token header is required).
        me = await lp._voyager_me_status(page)
        if me != 200:
            print(f"Session check failed (voyager /me = {me}); not saving.")
            return 1

        cookies = await context.cookies()
        cookies = [c for c in cookies if "linkedin" in c.get("domain", "")]
        path = jar(which)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(cookies, f)
        record_sign_in(which, email)
        print(f"Session OK (voyager /me=200). Saved {len(cookies)} cookies -> {path}")
        return 0
    finally:
        try:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass


async def _solve_pin(page, which: str = MOCK) -> bool:
    """Handle the email-PIN checkpoint by polling the account's PIN file (up to 300s)."""
    pin_box = page.locator("#input__email_verification_pin")
    try:
        await pin_box.wait_for(timeout=8000)
    except Exception:
        print(f"Checkpoint is not an email-PIN type (url={page.url}).")
        return False
    PIN_FILE = pin_file(which)
    if os.path.exists(PIN_FILE):
        os.remove(PIN_FILE)
    print(f"CHECKPOINT: LinkedIn emailed a PIN to the account. Drop the 6 "
          f"digits into {PIN_FILE} (waiting up to 300s)...", flush=True)
    _phase("awaiting_pin", "LinkedIn emailed a PIN to the account's inbox.", which)
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
    _phase("running", "Submitting the PIN…", which)
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


async def run_refresh(which: str = MOCK) -> int:
    """Entry point for a Settings session row: same flow as the CLI, but keeps the session's
    phase updated so the UI can follow along."""
    email, password, missing = _creds(which)
    if not email or not password:
        _phase("failed", missing, which)
        return 2
    _phase("running", "Signing in as " + email, which)
    try:
        code = await _login_and_save(email, password, which)
    except Exception as e:  # noqa: BLE001 - surfaced to the UI verbatim
        _phase("failed", str(e)[:200], which)
        return 1
    _phase("ok" if code == 0 else "failed",
           "Signed in." if code == 0 else "Login did not complete — see backend logs.", which)
    return code


def _run(which: str = MOCK) -> int:
    email, password, missing = _creds(which)
    if not email or not password:
        print(missing)
        return 2
    print(f"Signing the {which} session in as {email} via Playwright...", flush=True)
    return asyncio.run(_login_and_save(email, password, which))


def resolve_account(ref: str):
    """(account id, name, note) for `--account <name|id>`, or None when no single account
    matches. The note explains which session a member on 'inherit' refreshes."""
    from backend.models.db import SessionLocal
    from backend.scripts.cli_login import find_account
    from backend.accounts.context import use_account
    db = SessionLocal()
    try:
        acc = find_account(db, ref)
        if acc is None:
            return None
        note = ""
        if acc.role != "owner":
            with use_account(acc.id):
                if _cred.linkedin_shared_from_owner(db):
                    note = (f"{acc.name}'s LinkedIn section inherits the owner's, so this refreshes "
                            "the owner's session.")
        return acc.id, acc.name, note
    finally:
        db.close()


def main(argv=None) -> int:
    """`python -m backend.refresh_linkedin_session [--account <name|id>]` (QA F8 / R5-09):
    without --account the owner's session, as before; with it, that account's session
    (its own jar when its LinkedIn section is 'own', else the owner's)."""
    import argparse
    parser = argparse.ArgumentParser(description="Refresh a logged-in LinkedIn browser session.")
    parser.add_argument("--account", help="account name (case-insensitive) or id; default: the owner")
    parser.add_argument("--session", choices=SESSIONS, default=MOCK,
                        help="mock (the extension import and the lookup, default) or main (LinkedIn Personal)")
    args = parser.parse_args(argv)
    if not args.account:
        return _run(args.session)
    found = resolve_account(args.account)
    if found is None:
        print(f"No single account named or with id {args.account!r}.", file=sys.stderr)
        return 1
    account_id, name, note = found
    from backend.accounts.context import use_account
    print(f"Refreshing the LinkedIn session of {name}.", flush=True)
    if note:
        print(note, flush=True)
    with use_account(account_id):
        return _run(args.session)


if __name__ == "__main__":
    sys.exit(main())
