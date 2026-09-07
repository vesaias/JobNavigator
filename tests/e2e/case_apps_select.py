"""apps-select — the Applications screen's stage-PATCH selection race.

Regression for: clicking Rejected on application A's stage stepper, then quickly
selecting application B in the list, used to snap the detail pane back to A once
A's PATCH response landed — the reload it triggered forced `sel` back to A's id
regardless of what the user had since clicked. `patch()` in
frontend/src/screens/Applications.jsx now merges the PATCH response into A's row
only and never touches `sel`.

Entirely route-mocked: GET /api/applications and the PATCH on one fabricated ZZE
row are answered by the test itself, so nothing is created, changed, or left
behind in the real database (an application can't be cleaned up through the API —
there is no DELETE /api/jobs/{id} — so a real write here would leave a stray job
forever; mocking the whole exchange avoids that entirely).
"""
import json
import re

from _suite import case
import _common as C
import h

TS = '2026-08-01T12:00:00+00:00'


def _app(id_, title, status='applied'):
    return {
        'id': id_, 'job_id': f'zze-job-{id_}', 'status': status, 'applied_at': TS,
        'cv_version_used': None, 'notes': '', 'next_action': None, 'next_action_date': None,
        'last_email_received': None, 'last_email_snippet': None,
        'status_transitions': [{'from': None, 'to': status, 'at': TS, 'source': 'ui'}],
        'updated_at': TS, 'company': f'ZZE Co {id_[-1].upper()}', 'company_canonical': f'ZZE Co {id_[-1].upper()}',
        'title': title, 'url': f'https://example.com/{id_}', 'best_cv': None, 'short_id': id_[-4:],
        'location': 'Remote', 'salary_min': None, 'salary_max': None, 'source': 'manual',
        'has_cached_page': False, 'discovered_at': TS,
        'tailored_resume_id': None, 'tailored_resume_name': None, 'has_cover_letter': False,
        'interviews': [],
    }


APP_A = _app('zzeselracea', 'ZZE Selection Race Role A')
APP_B = _app('zzeselraceb', 'ZZE Selection Race Role B')


def _detail_text(pg):
    """InnerText of whatever sits beside the list column (the detail pane, or the
    empty-state placeholder) — the sibling of the scroller that holds `.v2-arow` rows."""
    return pg.evaluate("""() => {
      const anyRow = document.querySelector('.v2-arow');
      const scroller = anyRow && anyRow.closest('.v2-scroll');
      const detail = scroller && scroller.nextElementSibling;
      return detail ? (detail.innerText || '').trim().slice(0, 400) : null;
    }""")


@case('apps-select-race')
def _apps_select_race(c):
    seen_patch = []
    with h.browser() as b:
        pg = C.mpage(b)
        try:
            def mock_list(route):
                if route.request.method != 'GET':
                    return route.fallback()
                route.fulfill(status=200, content_type='application/json',
                               body=json.dumps({'total': 2, 'applications': [APP_A, APP_B]}))

            def mock_patch_a(route):
                if route.request.method != 'PATCH':
                    return route.fallback()
                try:
                    seen_patch.append(json.loads(route.request.post_data or '{}'))
                except ValueError:
                    seen_patch.append({'unparsed': route.request.post_data})
                pg.wait_for_timeout(1500)   # slow response — gives the user time to click B first
                body = dict(APP_A)
                body['status'] = 'rejected'
                body['status_transitions'] = APP_A['status_transitions'] + [
                    {'from': 'applied', 'to': 'rejected', 'at': TS, 'source': 'ui'}]
                route.fulfill(status=200, content_type='application/json', body=json.dumps(body))

            pg.route(re.compile(r'/api/applications(\?|$)'), mock_list)
            pg.route(re.compile(rf'/api/applications/{re.escape(APP_A["id"])}(\?|$)'), mock_patch_a)

            C.go(pg, '/applications')
            c.check('both ZZE rows render', C.body_has(pg, 'ZZE Selection Race Role A')
                    and C.body_has(pg, 'ZZE Selection Race Role B'))

            row_a = pg.locator('.v2-arow', has_text='ZZE Selection Race Role A').first
            row_b = pg.locator('.v2-arow', has_text='ZZE Selection Race Role B').first
            c.check('row A is present in the list', row_a.count() > 0)
            c.check('row B is present in the list', row_b.count() > 0)
            if row_a.count() == 0 or row_b.count() == 0:
                return

            row_a.click()
            pg.wait_for_timeout(300)
            c.check('A opens in the detail pane', 'ZZE Selection Race Role A' in (_detail_text(pg) or ''))

            stepper = pg.locator('[role="radiogroup"][aria-label="Application stage"]')
            c.check('the stage stepper is present', stepper.count() > 0)
            rejected_cell = stepper.locator('[role="radio"]', has_text='Rejected').first
            c.check('the stepper offers a Rejected cell', rejected_cell.count() > 0)
            if stepper.count() == 0 or rejected_cell.count() == 0:
                return

            rejected_cell.click()             # fires the mocked, 1500ms-delayed PATCH on A
            pg.wait_for_timeout(300)          # well inside the delay
            row_b.click()                     # the user has already moved on to B

            pg.wait_for_timeout(2000)         # long enough for A's delayed PATCH response to land
            c.check('exactly one PATCH reached the mock', len(seen_patch) == 1, seen_patch)
            c.check('…requesting the rejected status', seen_patch and seen_patch[0].get('status') == 'rejected', seen_patch)

            detail = _detail_text(pg) or ''
            c.check('the detail pane shows B, not A, after A\'s slow response lands',
                    'ZZE Selection Race Role B' in detail and 'ZZE Selection Race Role A' not in detail,
                    detail[:200])
            # A's optimistic status flip moves it straight into the (collapsed-by-default)
            # Rejected group, so only B's row is asserted here — A may no longer be mounted.
            c.check('row B still reads as selected (aria-current)',
                    row_b.count() > 0 and row_b.get_attribute('aria-current') == 'true',
                    row_b.count() and row_b.get_attribute('aria-current'))
        finally:
            pg.unroute_all(behavior='ignoreErrors')
            pg.context.close()
