"""feed-collapse — the Feed's analysis fold survives a reload.

JobFeed.jsx keeps the grab-line fold in its own localStorage key,
`jn_feed_analysis_collapsed` ('1' | '0'), deliberately outside `v2_feed_ui` so it
survives both a reload and a change of selected job. The control is the
`.v2-grab` strip above the detail header (aria-expanded = NOT collapsed).

Read-only against the database: everything here is per-browser UI state in a
throwaway context.
"""
from _suite import case
import _common as C
import h

KEY = 'jn_feed_analysis_collapsed'
GRAB = '.v2-grab'


def _state(pg):
    return pg.evaluate("""(sel) => {
      const el = document.querySelector(sel);
      return el ? { expanded: el.getAttribute('aria-expanded'), title: el.getAttribute('title') } : null;
    }""", GRAB)


@case('feed-collapse')
def _feed_collapse(c):
    with h.browser() as b:
        # seeded_page, not mpage: this case reloads, and h.py's own init script
        # would re-seed the key on every navigation and mask the real behaviour
        pg = C.seeded_page(b, extra={KEY: '0'})
        try:
            C.go(pg, '/v2/feed')
            if pg.locator(GRAB).count() == 0:
                # the fold lives in the detail pane — a job has to be selected first
                rows = pg.locator('.v2-crow, [data-row]')
                if rows.count() == 0:
                    c.skip('the Feed has no job rows in this database — nothing to fold')
                rows.first.click()
                pg.wait_for_timeout(900)
            if pg.locator(GRAB).count() == 0:
                c.skip('no .v2-grab fold control on the Feed detail pane')

            s0 = _state(pg)
            c.eq('starts expanded (seeded 0)', s0 and s0['expanded'], 'true')
            c.check('the grab-line names what it hides', 'analysis' in (s0['title'] or '').lower(), s0)

            pg.locator(GRAB).first.click()
            pg.wait_for_timeout(500)
            c.eq('a click collapses it', (_state(pg) or {}).get('expanded'), 'false')
            c.eq('…and writes the key', C.ls_get(pg, KEY), '1')

            pg.reload(wait_until='networkidle')
            pg.wait_for_timeout(1200)
            if pg.locator(GRAB).count() == 0:
                rows = pg.locator('.v2-crow, [data-row]')
                if rows.count():
                    rows.first.click()
                    pg.wait_for_timeout(900)
            c.eq('still collapsed after a reload', (_state(pg) or {}).get('expanded'), 'false')
            c.eq('key survives the reload', C.ls_get(pg, KEY), '1')

            pg.locator(GRAB).first.click()
            pg.wait_for_timeout(500)
            c.eq('toggling back expands it', (_state(pg) or {}).get('expanded'), 'true')
            c.eq('…and clears the key', C.ls_get(pg, KEY), '0')

            errs, perrs = C.console_errors(pg)
            c.check('no console errors while folding', not errs and not perrs,
                    '; '.join((errs + perrs)[:2]))
        finally:
            pg.context.close()
