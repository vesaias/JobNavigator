"""persona-import — the Persona import path with the backend ROUTE-MOCKED.

POST /api/persona/import replaces the persona's `contact` and `resume_content`
nodes on the real singleton row, so the real request is never allowed out: the
page's own POST is intercepted and answered with the persona exactly as it was
just read, plus a summary the toast has to render. The résumé list the modal
fetches is mocked too, so the case does not depend on the user having base
résumés and no real id is ever sent anywhere.

The persona row is re-read from the API afterwards and compared byte for byte.
"""
import json, re

from _suite import case
import _common as C
import h

FAKE_BASE = {'id': 'zze-e2e-fake-base', 'name': 'ZZE Fake Base', 'is_base': True,
             'updated_at': '2026-01-01T00:00:00+00:00', 'json_data': {}}
SUMMARY = {'roles': 7, 'bullets': 21, 'skill_groups': 3}
TOAST = 'Imported 7 roles · 21 bullets · 3 skill groups from ZZE Fake Base'


@case('persona-import')
def _persona_import(c):
    st, persona = h.get('/persona')
    c.check('GET /persona', st == 200 and isinstance(persona, dict), st)
    if st != 200:
        return
    # the two nodes a real import would replace — compared, not the whole row,
    # so a concurrent editor touching `updated_at` cannot fake a failure here
    nodes = lambda p: json.dumps({k: (p or {}).get(k) for k in ('contact', 'resume_content')}, sort_keys=True)
    before = nodes(persona)
    hits = {'import': 0, 'resumes': 0}

    with h.browser() as b:
        pg = C.mpage(b)
        try:
            def mock_import(route):
                hits['import'] += 1
                route.fulfill(status=200, content_type='application/json',
                              body=json.dumps({'persona': persona, 'summary': SUMMARY}))

            def mock_resumes(route):
                hits['resumes'] += 1
                route.fulfill(status=200, content_type='application/json',
                              body=json.dumps([FAKE_BASE]))

            # regexes, not globs: Playwright's URL glob does not treat `?` as a wildcard
            pg.route(re.compile(r'/api/resumes(\?|$)'), mock_resumes)
            pg.route(re.compile(r'/api/persona/import'), mock_import)

            C.go(pg, '/v2/persona')
            trigger = pg.locator('button:has-text("Import"), [role="button"]:has-text("Import")').first
            if trigger.count() == 0:
                c.skip('no Import control on /v2/persona')
            trigger.click()
            pg.wait_for_timeout(600)
            c.check('import modal opens', C.body_has(pg, 'Import persona content'))
            c.check('the résumé list request was intercepted', hits['resumes'] >= 1, hits)

            row = pg.locator('text=ZZE Fake Base').first
            c.check('the mocked base résumé renders as a source', row.count() > 0)
            if row.count():
                row.click()
                pg.wait_for_timeout(200)

            act = pg.locator('[role="button"]:has-text("Replace"), button:has-text("Replace")').first
            c.check('the Replace action is offered', act.count() > 0)
            if act.count():
                act.click()
                pg.wait_for_timeout(1200)

            c.check('the real POST never left the browser', hits['import'] == 1, hits)
            c.check('success toast names the parsed counts', C.body_has(pg, TOAST),
                    (pg.inner_text('body') or '')[-260:].replace('\n', ' | '))
            c.check('the modal closes on success', not C.body_has(pg, 'Import persona content'))

            errs, perrs = C.console_errors(pg)
            c.check('no console errors on the import path', not errs and not perrs,
                    '; '.join((errs + perrs)[:2]))
        finally:
            pg.unroute_all(behavior='ignoreErrors')
            pg.context.close()

    st, persona2 = h.get('/persona')
    c.check('the real persona contact/resume_content are unchanged afterwards',
            st == 200 and nodes(persona2) == before, st)
