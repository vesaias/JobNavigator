"""welcome — the first-run onboarding overlay (App.jsx `jobnavigator_welcomed`).

A browser profile with no welcome mark is a first visit and must see the modal;
dismissing it writes the durable mark; the next load must not replay it. Runs in
throwaway contexts so the user's own storage is never involved.

The Escape half is checked on two routes on purpose. WelcomeModal is a ModalPanel,
so `useEscape` should close it wherever it is raised — but the screen BEHIND it
mounts first, and a screen that registers an unconditional Escape handler wins the
event and calls preventDefault(), which makes the overlay's own handler bail.
"""
from _suite import case
import _common as C
import h

TITLE = 'Welcome to JobNavigator'
KEYS = ['jobnavigator_welcomed', 'jobnavigator_v2_welcome_seen', 'jobnavigator_welcome_seen']
CLOSE = '[aria-label="Close"]'


def _first_visit(b, route='/v2/feed'):
    pg = C.raw_page(b)                        # nothing seeded but the API key
    C.go(pg, route, settle=900)
    return pg


@case('welcome')
def _welcome(c):
    with h.browser() as b:
        pg = _first_visit(b)
        try:
            seeded = {k: C.ls_get(pg, k) for k in KEYS}
            c.check('context really is a first visit',
                    all(v is None for v in seeded.values()), seeded)
            shown = C.body_has(pg, TITLE)
            c.check('first visit shows the welcome modal', shown)
            if not shown:
                return
            steps = pg.evaluate("""() => [...document.querySelectorAll('[role="dialog"] div')]
              .map((d) => (d.textContent || '').trim())
              .filter((t) => /Set up AI scoring|Build your résumé|Activate a company|Configure a search/.test(t)).length""")
            c.check('the four setup steps render', steps >= 4, steps)

            pg.keyboard.press('Escape')
            pg.wait_for_timeout(450)
            c.check('Escape dismisses it over the Feed', not C.body_has(pg, TITLE))

            if C.body_has(pg, TITLE):
                pg.locator(CLOSE).first.click()
                pg.wait_for_timeout(450)
            c.check('the ✕ dismisses it', not C.body_has(pg, TITLE))
            c.eq('dismissal writes jobnavigator_welcomed', C.ls_get(pg, 'jobnavigator_welcomed'), '1')

            C.clear_log(pg)
            C.go(pg, '/v2/feed', settle=900)
            c.check('a second load does not replay it', not C.body_has(pg, TITLE))
            errs, perrs = C.console_errors(pg)
            c.check('no console errors around the overlay', not errs and not perrs,
                    '; '.join((errs + perrs)[:2]))
        finally:
            pg.context.close()

        # control: a screen that does not own Escape unconditionally
        pg = _first_visit(b, '/v2/stats')
        try:
            c.check('first visit shows it on /v2/stats too', C.body_has(pg, TITLE))
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(450)
            c.check('Escape dismisses it over Stats', not C.body_has(pg, TITLE))
        finally:
            pg.context.close()

        # a profile that already carries either legacy mark never sees it
        pg = C.raw_page(b, ls={'jobnavigator_welcome_seen': 'true'})
        try:
            C.go(pg, '/v2/feed', settle=900)
            c.check('a legacy welcome mark also suppresses it', not C.body_has(pg, TITLE))
        finally:
            pg.context.close()
