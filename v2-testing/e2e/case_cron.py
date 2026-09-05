"""cron — the Settings cron helper line, driven in the browser.

Settings' CronBox publishes its LIVE typed value (TextBox's `onLocal`), so the
plain-English line and the next-fire text can be read without ever saving. The
field is restored to its original text before the only blur of the run, and
TextBox.commit() returns early when `local === value`, so no PATCH is issued —
which the case then proves by re-reading GET /api/settings.

Expectations come from the checked table at the bottom of frontend/src/v2/time.js.
"""
from _suite import case
import _common as C
import h

ROW = 'DB backup · cron'
SETTING = 'backup_cron'

# expr -> (expected description prefix, expects a "next …" clause)
EXPECT = [
    ('0 * * * *',          'hourly at :00',                            True),
    ('*/30 * * * *',       'every 30 minutes',                         True),
    ('0 3 * * *',          'daily at 03:00',                           True),
    ('0 9 * * mon-fri',    'weekdays at 09:00',                        True),
    ('0 9 * * 1-5',        'every Tue, Wed, Thu, Fri, Sat at 09:00',   True),
    ('0 8 1 * *',          'monthly on the 1st at 08:00',              True),
    ('0 0 30 2 *',         'at 00:00 on day 30 in Feb',                False),   # never fires
    ('0 3 last * *',       '0 3 last * *',                             False),   # APScheduler extension, echoed
    ('99 3 * * *',         'invalid expression',                       False),
    ('0 3 * *',            'invalid expression',                       False),   # four fields
    ('',                   'off',                                      False),
]

LINE_JS = """(label) => {
  const inp = document.querySelector(`input[aria-label="${label}"]`);
  if (!inp) return null;
  const col = inp.closest('span').parentElement.parentElement;
  return (col.lastElementChild.textContent || '').trim();
}"""


@case('cron')
def _cron(c):
    st, settings = h.get('/settings')
    c.check('GET /settings', st == 200, st)
    before = None
    if isinstance(settings, list):
        before = next((s.get('value') for s in settings if s.get('key') == SETTING), None)
    elif isinstance(settings, dict):
        before = settings.get(SETTING)
    c.check(f'{SETTING} readable before the run', before is not None, repr(before))
    original = before or ''

    with h.browser() as b:
        pg = C.mpage(b)
        try:
            C.go(pg, '/v2/settings')
            sel = f'input[aria-label="{ROW}"]'
            if pg.locator(sel).count() == 0:
                c.skip(f'no cron field labelled {ROW!r} on /v2/settings')
            pg.locator(sel).scroll_into_view_if_needed()
            live0 = pg.evaluate(LINE_JS, ROW)
            c.check('helper line renders before typing', bool(live0), live0)

            for expr, want, wants_next in EXPECT:
                pg.fill(sel, expr)
                pg.wait_for_timeout(120)
                line = pg.evaluate(LINE_JS, ROW) or ''
                c.check(f'{expr!r} → {want!r}', line.startswith(want), f'line={line!r}')
                has_next = '· next ' in line
                c.check(f'{expr!r} next-fire clause {"present" if wants_next else "absent"}',
                        has_next == wants_next, f'line={line!r}')
                if expr == '0 0 30 2 *':
                    c.check('31-Feb-shaped expression is called out as never firing',
                            'never fires' in line, f'line={line!r}')
                if expr == '0 3 last * *':
                    c.check('APScheduler extension is echoed, not called dead',
                            'never fires' not in line, f'line={line!r}')

            # restore, then the run's only blur — commit() must no-op
            pg.fill(sel, original)
            pg.wait_for_timeout(100)
            pg.locator('main').click(position={'x': 40, 'y': 14})
            pg.wait_for_timeout(600)
        finally:
            pg.context.close()

    st, settings2 = h.get('/settings')
    after = None
    if isinstance(settings2, list):
        after = next((s.get('value') for s in settings2 if s.get('key') == SETTING), None)
    elif isinstance(settings2, dict):
        after = settings2.get(SETTING)
    c.eq(f'{SETTING} untouched by the run', after, before)
