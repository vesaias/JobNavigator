"""newui — the 2.0 upgrade announcements (App.jsx / v2/NewUiModal.jsx /
classic/WhatsNewBanner.jsx).

Three facts, all keyed off localStorage, all checked in throwaway contexts so the
user's own storage is never involved:

  1. An EXISTING user (a profile carrying `jobnavigator_welcomed`, or any legacy
     key) sees "Welcome to the new JobNavigator" once. Closing it — by Escape,
     the scrim, the ✕ or "Got it", all one `onClose` — writes
     `jobnavigator_newui_seen = '2.0.0'` and the next load is clean.
  2. A GENUINELY FRESH profile sees the first-run tour instead — and the upgrade
     modal is NOT marked seen, so it is still owed on the visit after the tour.
  3. The two announcements never overlap: the modal is gated to the 2.0 shell
     (and spends nothing on a /classic visit), while the classic shell's banner
     announces 2.0 at /classic, dismisses to
     `jobnavigator_whatsnew_dismissed = '2.0.0'`, and never shows in the 2.0 shell.

`run.sh` copies this file into the backend container and runs it there; the
frontend it drives is whatever the last `docker compose build frontend` produced,
so the orchestrator must BUILD the frontend before this case means anything.
"""
from _suite import case
import _common as C
import h

NEWUI_TITLE = 'Welcome to the new JobNavigator'
TOUR_TITLE = 'Welcome to JobNavigator'
BANNER_HEAD = 'JobNavigator 2.0 — the new dashboard is here'
BANNER_LINE = 'Rebuilt interface, five themes, Persona import, cron helper and more.'

SEEN_KEY = 'jobnavigator_newui_seen'
DISMISS_KEY = 'jobnavigator_whatsnew_dismissed'
VERSION = '2.0.0'

# The tour's own title is a PREFIX of the upgrade modal's, so "is the tour up?"
# can never be asked with a plain substring test — it is true either way.
def _tour_only(pg):
    return C.body_has(pg, TOUR_TITLE) and not C.body_has(pg, NEWUI_TITLE)


@case('newui')
def _newui(c):
    with h.browser() as b:
        # ── 1. existing user: shown once ────────────────────────────────────
        # raw_page seeds the API key too, but `jobnavigator_welcomed` is what
        # settles it: the tour is suppressed, so the upgrade modal is the one
        # overlay left that can appear.
        pg = C.raw_page(b, ls={'jobnavigator_welcomed': '1'})
        try:
            C.go(pg, '/feed', settle=900)
            c.check('an existing profile has no seen-mark yet', C.ls_get(pg, SEEN_KEY) is None)
            shown = C.body_has(pg, NEWUI_TITLE)
            c.check('existing user sees the new-UI modal', shown)
            c.check('the first-run tour does not double up', not _tour_only(pg))
            if shown:
                bullets = pg.evaluate("""() => {
                  const t = (document.querySelector('[role="dialog"]')?.innerText || '');
                  return [/Everything you know, rebuilt/, /extension, redesigned/, /Pick a look in Settings/,
                          /Persona import from a r/, /classic dashboard is still at \\/classic/]
                         .filter((re) => re.test(t)).length;
                }""")
                c.check('all five bullets render', bullets == 5, bullets)
                notes = pg.evaluate(
                    """() => { const a = [...document.querySelectorAll('[role="dialog"] a')]
                        .find((x) => /Read the release notes/.test(x.textContent || ''));
                      return a ? { href: a.getAttribute('href'), target: a.getAttribute('target') } : null; }""")
                c.check('release-notes link points at CHANGELOG.md on GitHub in a new tab',
                        bool(notes) and notes['href'].endswith('/blob/main/CHANGELOG.md')
                        and notes['target'] == '_blank', notes)

                # Escape is a REAL dismissal, not a peek: it runs the panel's
                # `onClose`, which is the same handler "Got it" runs, so it writes
                # the mark too. That is the contract on purpose — an announcement
                # nobody asked for must not come back because it was waved away
                # with the keyboard instead of the button. The listener is
                # capture-phase, so it wins over the Feed, which owns Escape itself.
                pg.keyboard.press('Escape')
                pg.wait_for_timeout(450)
                c.check('Escape closes it', not C.body_has(pg, NEWUI_TITLE))
                c.eq('Escape marks it seen', C.ls_get(pg, SEEN_KEY), VERSION)

                C.clear_log(pg)
                C.go(pg, '/feed', settle=900)
                c.check('a load after Escape does not replay it', not C.body_has(pg, NEWUI_TITLE))

                # Clear the mark and come back, to exercise the button on a panel
                # raised the same way the real upgrade raises it.
                pg.evaluate('(k) => { try { localStorage.removeItem(k) } catch (e) {} }', SEEN_KEY)
                C.go(pg, '/feed', settle=900)
                c.check('clearing the mark raises it again', C.body_has(pg, NEWUI_TITLE))

                got = pg.locator('[role="dialog"]').first.get_by_text('Got it', exact=True)
                got.first.click()
                pg.wait_for_timeout(450)
                c.check('"Got it" closes it', not C.body_has(pg, NEWUI_TITLE))
                c.eq('"Got it" writes the versioned seen-mark', C.ls_get(pg, SEEN_KEY), VERSION)

                C.clear_log(pg)
                C.go(pg, '/feed', settle=900)
                c.check('a second load does not replay it', not C.body_has(pg, NEWUI_TITLE))
                errs, perrs = C.console_errors(pg)
                c.check('no console errors around the overlay', not errs and not perrs,
                        '; '.join((errs + perrs)[:2]))
        finally:
            pg.context.close()

        # ── 2. fresh profile: the tour wins, and the upgrade stays owed ──────
        pg = C.raw_page(b)                      # nothing seeded but the API key
        try:
            C.go(pg, '/feed', settle=900)
            c.check('a fresh profile gets the first-run tour', _tour_only(pg))
            c.check('the upgrade modal is not marked seen behind it',
                    C.ls_get(pg, SEEN_KEY) is None, C.ls_get(pg, SEEN_KEY))
            pg.locator('[aria-label="Close"]').first.click()
            pg.wait_for_timeout(450)
            c.eq('dismissing the tour writes jobnavigator_welcomed',
                 C.ls_get(pg, 'jobnavigator_welcomed'), '1')

            # the visit AFTER the tour: no longer new, still unannounced
            C.clear_log(pg)
            C.go(pg, '/feed', settle=900)
            c.check('the upgrade modal is owed on the next visit', C.body_has(pg, NEWUI_TITLE))
        finally:
            pg.context.close()

        # ── 2b. the modal never reaches the classic shell ───────────────────
        # An existing profile that is OWED the announcement (no seen-mark) but
        # lands under /classic gets the banner, not the modal — and the visit
        # must not spend the announcement, so the mark stays unwritten and the
        # modal is still there on the next visit to the 2.0 shell.
        pg = C.raw_page(b, ls={'jobnavigator_welcomed': '1'})
        try:
            C.go(pg, '/classic', settle=900)
            c.check('no new-UI modal in the classic shell', not C.body_has(pg, NEWUI_TITLE))
            c.check('the classic shell shows the banner instead', C.body_has(pg, BANNER_HEAD))
            c.check('a classic visit does not mark it seen',
                    C.ls_get(pg, SEEN_KEY) is None, C.ls_get(pg, SEEN_KEY))
            c.check('no dialog is mounted over the classic shell at all',
                    pg.locator('[role="dialog"]').count() == 0)

            C.go(pg, '/feed', settle=900)
            c.check('the same profile still gets it in the 2.0 shell', C.body_has(pg, NEWUI_TITLE))
        finally:
            pg.context.close()

        # ── 3. the classic banner ───────────────────────────────────────────
        # newui_seen is pre-set here so the modal is out of the way and the
        # banner is the only thing under test.
        pg = C.raw_page(b, ls={'jobnavigator_welcomed': '1', SEEN_KEY: VERSION})
        try:
            C.go(pg, '/classic', settle=900)
            c.check('an undismissed profile sees the 2.0 banner at /classic',
                    C.body_has(pg, BANNER_HEAD))
            c.check('the banner carries the one-line summary', C.body_has(pg, BANNER_LINE))
            link = pg.evaluate(
                """() => { const a = [...document.querySelectorAll('main a')]
                    .find((x) => /Open the new UI/.test(x.textContent || ''));
                  return a ? { href: a.getAttribute('href'), target: a.getAttribute('target') } : null; }""")
            c.check('"Open the new UI" targets / in the same tab',
                    bool(link) and link['href'] == '/' and not link['target'], link)

            # ClassicShell is the only mount point — the 2.0 shell never shows it
            C.go(pg, '/feed', settle=900)
            c.check('the banner does not appear in the 2.0 shell', not C.body_has(pg, BANNER_HEAD))

            C.go(pg, '/classic', settle=900)
            pg.get_by_text('Later', exact=True).first.click()
            pg.wait_for_timeout(300)
            c.check('"Later" dismisses it', not C.body_has(pg, BANNER_HEAD))
            c.eq('dismissal is version-scoped', C.ls_get(pg, DISMISS_KEY), VERSION)

            C.clear_log(pg)
            C.go(pg, '/classic', settle=900)
            c.check('a dismissed banner stays gone', not C.body_has(pg, BANNER_HEAD))
            errs, perrs = C.console_errors(pg)
            c.check('no console errors around the banner', not errs and not perrs,
                    '; '.join((errs + perrs)[:2]))
        finally:
            pg.context.close()

        # a profile that dismissed the 1.1.0 banner wrote a DIFFERENT key, so the
        # 2.0 announcement is still owed to it
        pg = C.raw_page(b, ls={'jobnavigator_welcomed': '1', SEEN_KEY: VERSION,
                               'jn:whatsnew:v1.1.0': '1'})
        try:
            C.go(pg, '/classic', settle=900)
            c.check('dismissing the 1.1.0 banner does not suppress the 2.0 one',
                    C.body_has(pg, BANNER_HEAD))
        finally:
            pg.context.close()
