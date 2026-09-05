"""smoke — the per-route checks distilled from v2-testing/round-design/smoke-final.md.

Read-only. For every v2 route, at 1440x900 and 1024x700:
  heading present · 0 console errors · 0 pageerrors · no horizontal overflow ·
  rail counts populated within ~1s · health dot present.
Nothing is written and no endpoint that costs money or scrapes is touched.
"""
import re

from _suite import case
import _common as C
import h

ROUTES = [
    # heading text as the app ships it today (the Feed's PageTitle was "The Feed"
    # when smoke-final.md was written and reads "Jobs" now)
    ('/v2/feed', 'Jobs'),
    ('/v2/searches', 'Searches'),
    ('/v2/companies', 'Companies'),
    ('/v2/applications', 'Applications'),
    ('/v2/resumes', 'Résumés'),
    ('/v2/cover-letters', None),      # heading text varies with the shelf state
    ('/v2/persona', 'Persona'),
    ('/v2/stats', 'Stats'),
    ('/v2/settings', 'Settings'),
]

SIZES = [(1440, 900), (1024, 700)]


@case('smoke')
def _smoke(c):
    with h.browser() as b:
        for w, ht in SIZES:
            pg = C.mpage(b, appearance='light', theme='default', width=w, height=ht)
            try:
                for route, want_head in ROUTES:
                    tag = f'{route} @{w}'
                    C.clear_log(pg)
                    C.go(pg, route)
                    head = C.heading(pg)
                    if want_head:
                        c.check(f'{tag} heading', head == want_head, f'got {head!r}')
                    else:
                        c.check(f'{tag} heading', bool(head), f'got {head!r}')

                    errs, perrs = C.console_errors(pg)
                    c.check(f'{tag} console errors', not errs, '; '.join(errs[:2]))
                    c.check(f'{tag} pageerrors', not perrs, '; '.join(perrs[:2]))

                    o = C.overflow(pg)
                    c.check(f'{tag} no h-overflow', o['sw'] <= o['iw'] and o['right'] <= o['iw'] + 1,
                            f"sw={o['sw']} iw={o['iw']} right={o['right']} worst={o['worst']}")

                    r, ms = C.rail_counts_within(pg)
                    populated = bool(r and r['counts']) and all(v not in ('', None) for v in (r or {}).get('counts', {}).values())
                    c.check(f'{tag} rail counts <1.2s', populated, f'{ms}ms {r and r["counts"]}')
                    c.check(f'{tag} health dot', bool(r and r['dot'] and r['health']), r and r['health'])
            finally:
                pg.context.close()


@case('smoke-error-state')
def _error_state(c):
    """A stubbed 500 on each screen's own list endpoint must render a visible,
    non-blank error state rather than a white screen (smoke-final's check)."""
    # regexes, not globs — Playwright's URL glob does not treat `?` as a wildcard
    stubs = [
        ('/v2/feed', re.compile(r'/api/jobs(\?|$)')),
        ('/v2/searches', re.compile(r'/api/searches(\?|$)')),
        ('/v2/companies', re.compile(r'/api/companies(\?|$)')),
        ('/v2/applications', re.compile(r'/api/applications(\?|$)')),
        ('/v2/persona', re.compile(r'/api/persona(\?|$)')),
        ('/v2/settings', re.compile(r'/api/settings(\?|$)')),
    ]
    with h.browser() as b:
        pg = C.mpage(b)
        try:
            for route, pattern in stubs:
                pg.unroute_all(behavior='ignoreErrors')
                pg.route(pattern, lambda r: r.fulfill(status=500, content_type='application/json',
                                                      body='{"detail":"e2e stub"}'))
                C.clear_log(pg)
                C.go(pg, route)
                info = pg.evaluate("""() => {
                  const m = document.querySelector('main');
                  const t = (m ? m.innerText : '') || '';
                  return { n: t.replace(/\\s/g, '').length,
                           err: /could not|couldn|failed|error|try again|unavailable/i.test(t) };
                }""")
                _, perrs = C.console_errors(pg)
                c.check(f'{route} stubbed-500 renders an error state',
                        info['n'] > 20 and info['err'] and not perrs,
                        f"nonblank={info['n']} err_text={info['err']} pageerrors={len(perrs)}")
        finally:
            pg.unroute_all(behavior='ignoreErrors')
            pg.context.close()
