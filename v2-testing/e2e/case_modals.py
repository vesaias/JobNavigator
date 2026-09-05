"""modals — six real overlays across the app: each opens, closes on Escape, and
closes on an outside/scrim click.

Three modals (`role=dialog`) and three menus, on five screens, chosen against the
per-route modal/menu inventories in v2-testing/round-design/smoke-final.md.

Nothing is created: every overlay is opened and dismissed, never submitted. The
Model-catalog modal fetches the provider's live catalog on mount, so that one
request is route-mocked to an empty list — the case must not reach out to a
third-party API.

Outside-click uses a point inside <main> (the page-title strip), not the (3,3)
viewport corner round 3 used: that corner lands on the nav rail, which sits above
a drawer's own scrim and swallows the click (smoke-final DS-S-01).
"""
import re

from _suite import case
import _common as C
import h

SPECS = [
    dict(label='Feed · keyboard shortcuts', route='/v2/feed',
         trigger='[title="Keyboard shortcuts"]',
         panel='[role="group"][aria-label="Keyboard shortcuts"]'),
    dict(label='Feed · Source filter menu', route='/v2/feed',
         trigger='[aria-haspopup="menu"]:has-text("Source")', panel='[role="menu"]'),
    dict(label='Companies · Add company modal', route='/v2/companies',
         trigger='text="+ Add company"', panel='[role="dialog"]', expect='Add company'),
    dict(label='Searches · row ⋯ menu', route='/v2/searches',
         trigger='[title="More actions"]', panel='[role="menu"]'),
    dict(label='Résumés · New résumé modal', route='/v2/resumes',
         trigger='text="+ New résumé"', panel='[role="dialog"]'),
    dict(label='Settings · Model catalog modal', route='/v2/settings',
         trigger='[aria-label="Model catalog — manage"]', panel='[role="dialog"]'),
]


def _visible(pg, sel):
    loc = pg.locator(sel)
    return loc.count() > 0 and loc.first.is_visible()


def _open(pg, spec):
    t = pg.locator(spec['trigger']).first
    if t.count() == 0:
        return False
    t.scroll_into_view_if_needed()
    t.click()
    pg.wait_for_timeout(450)
    return True


@case('modals')
def _modals(c):
    with h.browser() as b:
        pg = C.mpage(b)
        pg.route(re.compile(r'/api/llm/models'),
                 lambda r: r.fulfill(status=200, content_type='application/json', body='[]'))
        try:
            for spec in SPECS:
                lab = spec['label']
                C.go(pg, spec['route'])
                base = C.overlay_count(pg)

                if not _open(pg, spec):
                    c.check(f'{lab} · trigger present', False, f"no match for {spec['trigger']}")
                    continue
                opened = _visible(pg, spec['panel']) and C.overlay_count(pg) > base
                c.check(f'{lab} · opens', opened,
                        f"panel={_visible(pg, spec['panel'])} overlays {base}→{C.overlay_count(pg)}")
                if spec.get('expect'):
                    c.check(f'{lab} · shows {spec["expect"]!r}', C.body_has(pg, spec['expect']))
                if not opened:
                    pg.keyboard.press('Escape')
                    continue

                pg.keyboard.press('Escape')
                pg.wait_for_timeout(420)
                c.check(f'{lab} · Escape closes it', not _visible(pg, spec['panel']))

                # reopen for the outside-click half
                if not _open(pg, spec) or not _visible(pg, spec['panel']):
                    c.check(f'{lab} · reopens for the scrim check', False)
                    continue
                x, y = C.outside_point(pg)
                pg.mouse.click(x, y)
                pg.wait_for_timeout(450)
                c.check(f'{lab} · outside/scrim click closes it', not _visible(pg, spec['panel']),
                        f'clicked ({x},{y})')

                # leave nothing open behind us
                pg.keyboard.press('Escape')
                pg.wait_for_timeout(150)

            errs, perrs = C.console_errors(pg)
            c.check('no pageerrors across all six overlays', not perrs, '; '.join(perrs[:2]))
        finally:
            pg.unroute_all(behavior='ignoreErrors')
            pg.context.close()
