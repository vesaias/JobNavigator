"""theme — the appearance/theme storage migration, proven in a real browser.

frontend/src/v2/theme.js keeps two axes in localStorage:
    jobnavigator_appearance   light|dark|system
    jobnavigator_theme        the palette
and migrates three older shapes on boot (index.html's boot script does the same
steps before React mounts):
    jobnavigator_dark_mode    legacy boolean          → appearance
    jobnavigator_skin         old name for the theme  → theme, old key removed
    jobnavigator_theme        holding a light|dark    → appearance (read first)
An unknown palette name falls back to `default`.

Each sub-test gets its own throwaway context seeded with ONLY the legacy keys.
"""
from _suite import case
import _common as C
import h


def _boot(b, seed):
    pg = C.raw_page(b, ls=dict(seed, jobnavigator_welcomed='1'))
    C.go(pg, '/v2/feed', settle=700)
    return pg


@case('theme')
def _theme(c):
    with h.browser() as b:
        # 1 — legacy boolean only
        pg = _boot(b, {'jobnavigator_dark_mode': 'true'})
        try:
            a = C.html_attrs(pg)
            c.eq('legacy dark_mode=true → <html data-appearance>', a['appearance'], 'dark')
            c.check('legacy dark_mode=true → .dark on <html>', a['dark'])
            c.eq('legacy dark_mode=true → appearance key written',
                 C.ls_get(pg, 'jobnavigator_appearance'), 'dark')
        finally:
            pg.context.close()

        # 2 — legacy skin key moves to the theme key and is removed
        pg = _boot(b, {'jobnavigator_skin': 'cobalt'})
        try:
            a = C.html_attrs(pg)
            c.eq('legacy skin=cobalt → jobnavigator_theme', C.ls_get(pg, 'jobnavigator_theme'), 'cobalt')
            c.eq('legacy skin key removed', C.ls_get(pg, 'jobnavigator_skin'), None)
            c.eq('legacy skin=cobalt → <html data-theme>', a['theme'], 'cobalt')
        finally:
            pg.context.close()

        # 3 — a light|dark value parked in the THEME key lands in appearance,
        #     while the skin value still wins for the palette (read order matters)
        pg = _boot(b, {'jobnavigator_theme': 'dark', 'jobnavigator_skin': 'saas'})
        try:
            a = C.html_attrs(pg)
            c.eq('legacy theme="dark" → appearance', C.ls_get(pg, 'jobnavigator_appearance'), 'dark')
            c.eq('…and <html data-appearance>', a['appearance'], 'dark')
            c.eq('skin value still wins for the palette', a['theme'], 'saas')
            c.eq('theme key now holds the palette', C.ls_get(pg, 'jobnavigator_theme'), 'saas')
        finally:
            pg.context.close()

        # 4 — an unknown stored palette falls back to default (it must still paint)
        pg = _boot(b, {'jobnavigator_theme': 'not-a-real-theme'})
        try:
            a = C.html_attrs(pg)
            c.eq('unknown theme → data-theme=default', a['theme'], 'default')
            c.check('unknown theme still paints an appearance', a['appearance'] in ('light', 'dark'), a['appearance'])
            _, perrs = C.console_errors(pg)
            c.check('unknown theme raises no pageerror', not perrs, '; '.join(perrs[:2]))
        finally:
            pg.context.close()

        # 5 — the modern keys are honoured as-is, both axes at once
        pg = _boot(b, {'jobnavigator_appearance': 'dark', 'jobnavigator_theme': 'board'})
        try:
            a = C.html_attrs(pg)
            c.eq('modern keys → data-appearance', a['appearance'], 'dark')
            c.eq('modern keys → data-theme', a['theme'], 'board')
            mirrored = pg.evaluate("""() => {
              const r = document.querySelector('.jn-v2');
              return r ? { a: r.getAttribute('data-appearance'), t: r.getAttribute('data-theme') } : null;
            }""")
            c.check('.jn-v2 root mirrors both attributes',
                    mirrored == {'a': 'dark', 't': 'board'}, mirrored)
        finally:
            pg.context.close()
