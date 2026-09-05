"""flows — the non-spending regression checks distilled from
v2-testing/round-design/flows-A-final.md and flows-B-final.md.

Everything here works on rows this suite created itself, all named with the ZZE
prefix, all deleted again at the end of their case. Anything that scrapes, calls
an LLM, or reaches a third party is behind JN_E2E_LIVE=1.

Covered by default:
  · search CRUD through the API — create, read the JSON shape back, edit, delete
  · the pause/resume status pill (PATCH route-mocked: the pill's contract, not a write)
  · the destructive ConfirmDialog, Escape-cancels, and the delete it guards
  · the rail badge following a delete (`jn:counts-changed`)
  · the undo toast on a résumé section removal, and that Undo really restores
  · the /monitor/active + /monitor/history polling shapes the spinners rely on

Behind JN_E2E_LIVE=1:
  · company CRUD — POST /api/companies forces active=True and fires a MyVisaJobs
    H-1B lookup in a background task, i.e. a real outbound request
  · the company test-scrape, the search run and any scoring depth above `off`
"""
import json, re, time

from _suite import case
import _common as C
import h

SEARCH_BODY = {
    'name': 'ZZE Search (e2e)',
    'active': False,                       # never on the scheduler, so it can never run
    'search_mode': 'keyword',
    'search_term': 'zze e2e placeholder',
    'location': 'United States',
    'sources': ['indeed'],
    'hours_old': 1,
    'results_wanted': 1,
    'title_exclude_keywords': ['intern'],
    'auto_scoring_depth': 'off',           # no LLM, ever
    'run_interval_minutes': 0,
}

SHAPE = ['id', 'name', 'active', 'search_mode', 'search_term', 'location', 'sources',
         'hours_old', 'results_wanted', 'title_exclude_keywords', 'auto_scoring_depth',
         'run_interval_minutes']


def _mk_search(name=None):
    body = dict(SEARCH_BODY)
    if name:
        body['name'] = name
    st, d = h.post('/searches', body)
    if st < 300 and isinstance(d, dict) and d.get('id'):
        C.track('searches', d['id'])
    return st, d


def _searches():
    st, d = h.get('/searches')
    return d if st == 200 and isinstance(d, list) else []


# ── 1. CRUD through the API ─────────────────────────────────────────────────
@case('flows-search-crud')
def _search_crud(c):
    st, made = _mk_search()
    c.check('POST /api/searches', st in (200, 201) and isinstance(made, dict), f'{st} {str(made)[:120]}')
    if not (isinstance(made, dict) and made.get('id')):
        return
    sid = made['id']
    missing = [k for k in SHAPE if k not in made]
    c.check('created row carries the documented shape', not missing, f'missing {missing}')
    c.eq('name round-trips', made.get('name'), SEARCH_BODY['name'])
    c.eq('active:false is honoured (never scheduled)', made.get('active'), False)
    c.eq('auto_scoring_depth stays off', made.get('auto_scoring_depth'), 'off')
    c.eq('sources round-trip', made.get('sources'), ['indeed'])

    listed = next((s for s in _searches() if s.get('id') == sid), None)
    c.check('the row is in GET /api/searches', listed is not None)
    c.eq('…with the same term', (listed or {}).get('search_term'), SEARCH_BODY['search_term'])

    st, upd = h.patch(f'/searches/{sid}', {'run_interval_minutes': 120, 'results_wanted': 3})
    c.check('PATCH /api/searches/{id}', st == 200, st)
    c.eq('interval saved', (upd or {}).get('run_interval_minutes'), 120)
    c.eq('results_wanted saved', (upd or {}).get('results_wanted'), 3)

    st, _ = h.delete(f'/searches/{sid}')
    c.check('DELETE /api/searches/{id}', st in (200, 204), st)
    C.untrack('searches', sid)
    c.check('the row is gone', not any(s.get('id') == sid for s in _searches()))


# ── 2. monitor polling shape ────────────────────────────────────────────────
@case('flows-monitor')
def _monitor(c):
    st, act = h.get('/monitor/active')
    c.check('GET /api/monitor/active is a list', st == 200 and isinstance(act, list), f'{st} {type(act).__name__}')
    if isinstance(act, list):
        keys = {'run_id', 'job_type', 'trigger', 'started_at', 'elapsed_seconds',
                'scope_key', 'target_job_id', 'company_id'}
        bad = [e for e in act if not keys.issubset(e)]
        c.check('every active entry carries the scope-key fields the spinners poll on',
                not bad, f'{len(bad)} of {len(act)} short: {str(bad[:1])[:160]}')
        c.note(f'{len(act)} run(s) active right now')

    st, hist = h.get('/monitor/history?limit=3')
    c.check('GET /api/monitor/history is a list', st == 200 and isinstance(hist, list), st)
    if isinstance(hist, list) and hist:
        need = {'id', 'job_type', 'trigger', 'status', 'started_at'}
        c.check('history rows carry id/job_type/trigger/status/started_at',
                need.issubset(hist[0]), sorted(set(need) - set(hist[0])))

    st, infl = h.get('/monitor/in-flight')
    c.check('GET /api/monitor/in-flight is a map', st == 200 and isinstance(infl, dict), st)


# ── 3. pause / resume pill (PATCH route-mocked — the contract, not a write) ──
@case('flows-pause-pill')
def _pause_pill(c):
    st, made = _mk_search('ZZE Pause Pill (e2e)')
    if not (isinstance(made, dict) and made.get('id')):
        c.check('created the scratch search', False, st)
        return
    sid = made['id']
    seen = []
    flags_before = {s['id']: s.get('active') for s in _searches() if s.get('id') != sid}
    try:
        with h.browser() as b:
            pg = C.mpage(b)
            try:
                def mock_patch(route):
                    if route.request.method != 'PATCH':
                        return route.fallback()
                    try:
                        seen.append(json.loads(route.request.post_data or '{}'))
                    except ValueError:
                        seen.append({'unparsed': route.request.post_data})
                    body = dict(made)
                    body['active'] = not made['active']
                    route.fulfill(status=200, content_type='application/json', body=json.dumps(body))

                pg.route(re.compile(rf'/api/searches/{re.escape(sid)}(\?|$)'), mock_patch)
                C.go(pg, '/v2/searches')

                others = [s['name'] for s in _searches() if s.get('id') != sid]
                # only the status pill carries "schedule" in its tooltip
                sel = '[aria-pressed][title*="schedule"]'
                hit = C.row_index(pg, sel, made['name'], others)
                c.check('the ZZE row is uniquely identifiable', hit is not None,
                        C.row_index_debug(pg, sel, made['name'], others))
                if not hit:
                    return
                loc = pg.locator(sel).nth(hit['i'])
                info = loc.evaluate("""(el) => ({ t: (el.textContent || '').trim(),
                  title: el.getAttribute('title'), pressed: el.getAttribute('aria-pressed') })""")
                c.eq('a paused search reads "Paused"', info['t'], 'Paused')
                c.eq('…with aria-pressed=false', info['pressed'], 'false')
                c.check('…and a Resume tooltip', 'Resume' in (info['title'] or ''), info['title'])
                if info['t'] != 'Paused':
                    return                     # refuse to click a control we cannot identify

                loc.click()
                pg.wait_for_timeout(900)
                c.check('clicking it PATCHes exactly once', len(seen) == 1, seen)
                c.check('…with {active: true}', bool(seen) and seen[0].get('active') is True, seen)
            finally:
                pg.unroute_all(behavior='ignoreErrors')
                pg.context.close()
    finally:
        st, _ = h.delete(f'/searches/{sid}')
        C.untrack('searches', sid)
        c.check('scratch search cleaned up', st in (200, 204, 404), st)
        rest = _searches()
        after = next((s for s in rest if s.get('id') == sid), None)
        c.check('the mocked PATCH never reached the database', after is None, after)
        flags_after = {s['id']: s.get('active') for s in rest}
        moved = {k: (v, flags_after.get(k)) for k, v in flags_before.items() if flags_after.get(k) != v}
        c.check('no other search had its active flag touched', not moved, moved)


# ── 4. ConfirmDialog + delete + rail badge refresh ──────────────────────────
@case('flows-confirm-delete')
def _confirm_delete(c):
    st, made = _mk_search('ZZE Confirm (e2e)')
    if not (isinstance(made, dict) and made.get('id')):
        c.check('created the scratch search', False, st)
        return
    sid, name = made['id'], made['name']
    ok = False
    try:
        with h.browser() as b:
            pg = C.mpage(b)
            try:
                C.go(pg, '/v2/searches')
                r, _ = C.rail_counts_within(pg)
                before = (r or {}).get('counts', {}).get('/v2/searches')
                c.check('rail searches badge agrees with the API before the delete',
                        str(before) == str(len(_searches())), f'rail={before} api={len(_searches())}')

                others = [s['name'] for s in _searches() if s.get('id') != sid]

                def open_menu():
                    hit = C.row_index(pg, '[title="More actions"]', name, others)
                    if not hit:
                        return False
                    pg.locator('[title="More actions"]').nth(hit['i']).click()
                    pg.wait_for_timeout(400)
                    return True

                def dialog_text():
                    return pg.evaluate("""() => { const d = document.querySelector('[role="dialog"]');
                      return d ? (d.innerText || '').trim().slice(0, 200) : null; }""")

                if not c.check('the ZZE row is uniquely identifiable and has a ⋯ menu', open_menu(),
                               C.row_index_debug(pg, '[title="More actions"]', name, others)):
                    return
                c.check('the menu offers Delete search', C.body_has(pg, 'Delete search'))
                pg.locator('text="Delete search"').first.click()
                pg.wait_for_timeout(450)

                dlg = dialog_text()
                c.check('a ConfirmDialog is raised, not window.confirm', dlg is not None, dlg)
                c.check('…naming the row it will delete', bool(dlg) and name in dlg, dlg)
                c.check('…offering Cancel and Delete',
                        bool(dlg) and 'Cancel' in dlg and 'Delete' in dlg, dlg)

                pg.keyboard.press('Escape')
                pg.wait_for_timeout(400)
                c.check('Escape cancels the dialog', pg.locator('[role="dialog"]').count() == 0)
                c.check('…and the row still exists', any(s.get('id') == sid for s in _searches()))

                open_menu()
                pg.locator('text="Delete search"').first.click()
                pg.wait_for_timeout(400)
                # HARD GUARD: never confirm a destructive dialog that is not about
                # our own ZZE row. This suite runs against the user's real database.
                dlg = dialog_text()
                if not dlg or name not in dlg:
                    pg.keyboard.press('Escape')
                    c.check('the confirm dialog targets our ZZE row (guard)', False,
                            f'refused to confirm: {dlg!r}')
                    return
                pg.locator('[role="dialog"]').locator('text="Delete"').last.click()
                pg.wait_for_timeout(1400)

                gone = not any(s.get('id') == sid for s in _searches())
                c.check('confirming deletes the row', gone)
                ok = gone
                # (the name is still on screen for ~4s — inside the success toast —
                #  so ask whether the ROW is gone, not whether the text is)
                c.check('the row leaves the list',
                        C.row_index(pg, '[title="More actions"]', name, others) is None)
                c.check('a success toast confirms the delete', C.body_has(pg, 'deleted'))

                # the rail is re-read on jn:counts-changed — assert it agrees with
                # the API again rather than doing count arithmetic, since other
                # agents may be creating/deleting rows at the same time
                agreed = False
                for _ in range(20):
                    rr = C.rail(pg)
                    if str((rr or {}).get('counts', {}).get('/v2/searches')) == str(len(_searches())):
                        agreed = True
                        break
                    pg.wait_for_timeout(150)
                c.check('the rail badge refreshes after the delete (jn:counts-changed)', agreed,
                        f'rail={(C.rail(pg) or {}).get("counts", {}).get("/v2/searches")} api={len(_searches())}')
            finally:
                pg.context.close()
    finally:
        if ok:
            C.untrack('searches', sid)
        else:
            st, _ = h.delete(f'/searches/{sid}')
            C.untrack('searches', sid)


# ── 5. undo toast ───────────────────────────────────────────────────────────
RESUME_BODY = {
    'name': 'ZZE Undo (e2e)',
    # deliberately NOT a base résumé: a base would be scored against every job
    # anything else in the system saves while this case is running (an LLM call).
    'is_base': False,
    'json_data': {
        'header': {'name': 'ZZE E2E', 'contact_items': []},
        'summary': '',
        'experience': [{'company': 'ZZE Company', 'title': 'ZZE Role', 'location': '',
                        'date': '2020', 'description': '', 'bullets': ['ZZE bullet one', 'ZZE bullet two']}],
        'skills': {}, 'education': [], 'projects': [], 'publications': [],
    },
}


def _exp_len(rid):
    st, d = h.get(f'/resumes/{rid}')
    if st != 200 or not isinstance(d, dict):
        return None
    jd = d.get('json_data') or {}
    return len(jd.get('experience') or [])


@case('flows-undo-toast')
def _undo_toast(c):
    st, made = h.post('/resumes', RESUME_BODY)
    c.check('POST /api/resumes (non-base scratch row)', st in (200, 201) and isinstance(made, dict), st)
    if not (isinstance(made, dict) and made.get('id')):
        return
    rid = C.track('resumes', made['id'])
    try:
        with h.browser() as b:
            pg = C.mpage(b, extra={'jobnavigator_v2_resume_sections': json.dumps(['Experience'])})
            try:
                C.go(pg, f'/v2/resumes/{rid}')
                c.check('the scratch résumé opens in the editor', C.body_has(pg, 'ZZE Role'),
                        (C.heading(pg) or '')[:60])
                # the experience entry is a SectionHead (aria-expanded); a single
                # entry opens expanded, so only click it when it is not
                heads = lambda: pg.evaluate("""() => [...document.querySelectorAll('[aria-expanded]')]
                  .map((e, i) => ({ i, x: e.getAttribute('aria-expanded'),
                                    t: (e.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60) }))""")
                entry = next((x for x in heads() if 'ZZE Role' in x['t']), None)
                c.check('the experience entry renders a head', entry is not None, entry)
                if entry and entry['x'] != 'true':
                    pg.locator('[aria-expanded]').nth(entry['i']).click()
                    pg.wait_for_timeout(700)
                    entry = next((x for x in heads() if 'ZZE Role' in x['t']), None)
                c.eq('the entry is expanded', entry and entry['x'], 'true')
                rem = pg.locator('text="Remove role"').first
                c.check('the entry offers "Remove role"', rem.count() > 0,
                        (pg.inner_text('main') or '')[:200].replace('\n', ' | '))
                if rem.count() == 0:
                    return
                rem.click()
                pg.wait_for_timeout(700)

                c.check('an undo toast appears', C.body_has(pg, 'Removed role'))
                undo = pg.locator('text="Undo"').first
                c.check('…with an Undo action', undo.count() > 0)
                c.check('the role really left the editor', not C.body_has(pg, 'ZZE Company'))
                if undo.count() == 0:
                    return
                undo.click()
                pg.wait_for_timeout(1000)
                c.check('Undo puts the role back on screen', C.body_has(pg, 'ZZE Company'))

                n = None
                for _ in range(20):
                    n = _exp_len(rid)
                    if n == 1:
                        break
                    pg.wait_for_timeout(250)
                c.eq('…and the autosaved json_data holds it again', n, 1)
            finally:
                pg.context.close()
    finally:
        st, _ = h.delete(f'/resumes/{rid}')
        C.untrack('resumes', rid)
        c.check('scratch résumé cleaned up', st in (200, 204, 404), st)


# ── 6. company CRUD — JN_E2E_LIVE only ──────────────────────────────────────
@case('flows-company-crud')
def _company_crud(c):
    C.live_only(c, 'POST /api/companies forces active=True and fires a real MyVisaJobs H-1B lookup')
    body = {'name': 'ZZE Vercel Co (e2e)', 'tier': 2, 'scrape_urls': [],
            'aliases': [], 'selected_resume_ids': [], 'auto_scoring_depth': 'off'}
    st, made = h.post('/companies', body)
    c.check('POST /api/companies', st in (200, 201) and isinstance(made, dict), st)
    if not (isinstance(made, dict) and made.get('id')):
        return
    cid = C.track('companies', made['id'])
    try:
        for k in ('scrape_urls', 'tier', 'active', 'auto_scoring_depth', 'aliases',
                  'selected_resume_ids', 'scrape_interval_minutes'):
            c.check(f'created company carries {k}', k in made, sorted(made))
        st, upd = h.patch(f'/companies/{cid}', {'tier': 3, 'active': False})
        c.check('PATCH /api/companies/{id}', st == 200, st)
        c.eq('tier saved', (upd or {}).get('tier'), 3)
        st, d = h.get('/companies')
        c.check('the row is listed', isinstance(d, list) and any(x.get('id') == cid for x in d))
    finally:
        st, _ = h.delete(f'/companies/{cid}')
        C.untrack('companies', cid)
        c.check('scratch company cleaned up', st in (200, 204, 404), st)


# ── 7. real scrape / scoring — JN_E2E_LIVE only ─────────────────────────────
@case('flows-live-run')
def _live_run(c):
    C.live_only(c, 'runs a real test scrape and a real search run against live job boards')
    st, made = _mk_search('ZZE Live Run (e2e)')
    if not (isinstance(made, dict) and made.get('id')):
        c.check('created the scratch search', False, st)
        return
    sid = made['id']
    try:
        st, prev = h.post(f'/searches/{sid}/test', {})
        c.check('POST /api/searches/{id}/test returns a preview', st in (200, 202), st)
        c.check('the preview saves nothing', isinstance(prev, dict), type(prev).__name__)

        st, run = h.post(f'/searches/{sid}/run', {})
        c.check('POST /api/searches/{id}/run is accepted', st in (200, 202), st)
        scope = None
        for _ in range(60):
            _, act = h.get('/monitor/active')
            hit = [a for a in (act or []) if a.get('scope_key') == sid]
            if hit:
                scope = hit[0]
                break
            time.sleep(0.5)
        c.check('the run appears on /monitor/active under its scope key', scope is not None, scope)
        if scope:
            c.eq('…tagged search_run', scope.get('job_type'), 'search_run')
            c.eq('…triggered manually', scope.get('trigger'), 'manual')
        for _ in range(120):
            _, act = h.get('/monitor/active')
            if not [a for a in (act or []) if a.get('scope_key') == sid]:
                break
            time.sleep(0.5)
        _, hist = h.get(f'/monitor/history?limit=10&job_type=search_run')
        c.check('the run lands in /monitor/history', isinstance(hist, list) and bool(hist))
    finally:
        h.delete(f'/searches/{sid}')
        C.untrack('searches', sid)


# ── 8. nothing left behind ──────────────────────────────────────────────────
@case('flows-sweep')
def _sweep(c):
    left = C.sweep()
    c.check('every row this run created was deleted', not left, left)
    stray = C.stray_zze()
    n = sum(len(v) for v in stray.values())
    c.check('no ZZE rows remain anywhere', n == 0, stray)
