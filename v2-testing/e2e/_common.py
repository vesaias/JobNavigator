"""Shared helpers for the v2 e2e suite: browser contexts that speak the CURRENT
storage keys, page probes lifted from the round-3 / round-design smoke passes,
and the ZZE scratch-row bookkeeping.

`h.py` (the verification harness) seeds LEGACY localStorage keys — the app now
reads `jobnavigator_appearance` + `jobnavigator_theme` (frontend/src/v2/theme.js).
h.py is not edited; every context here sets the modern keys through `extra_ls`,
and `raw_ctx()` builds a context with NOTHING seeded but what it is handed, which
is what the theme-migration and welcome-modal cases need.
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h  # noqa: E402  the harness, copied in beside these files

BASE = h.BASE
KEY = h.KEY
LIVE = os.environ.get('JN_E2E_LIVE') == '1'
PREFIX = 'ZZE'

# X-Frame-Options / CSP iframe noise from the Feed's cached-page preview is
# expected and ignored, exactly as every previous smoke pass did.
NOISE = re.compile(
    r'X-Frame-Options|Content Security Policy|frame-ancestors|Refused to display|'
    r'Refused to frame|ERR_BLOCKED_BY_RESPONSE|ERR_BLOCKED_BY_CLIENT', re.I)


def live_only(ctx, what):
    """Skip the calling case unless JN_E2E_LIVE=1."""
    if not LIVE:
        ctx.skip(f'needs JN_E2E_LIVE=1 — {what}')


# ── contexts ────────────────────────────────────────────────────────────────
_SEED_GUARD = '__jn_e2e_seeded'


def raw_ctx(b, ls=None, width=1440, height=900, api_key=True):
    """A context with ONLY the keys given (plus the API key unless api_key=False).

    The seed runs once per context, not once per navigation, so a reload sees
    whatever the app itself wrote — which is the whole point of the migration case.
    """
    store = dict(ls or {})
    if api_key:
        store['jobnavigator_api_key'] = KEY
    ctx = b.new_context(viewport={'width': width, 'height': height})
    sets = ''.join(f'localStorage.setItem({json.dumps(k)},{json.dumps(v)});' for k, v in store.items())
    ctx.add_init_script(
        f"try{{if(!localStorage.getItem({json.dumps(_SEED_GUARD)})){{"
        f"localStorage.setItem({json.dumps(_SEED_GUARD)},'1');{sets}}}}}catch(e){{}}")
    return ctx


def raw_page(b, **kw):
    pg = raw_ctx(b, **kw).new_page()
    h.attach_log(pg)
    return pg


def mpage(b, appearance='light', theme='default', width=1440, height=900, extra=None):
    """Authed, warmed-up page using the CURRENT appearance/theme keys."""
    ls = {'jobnavigator_appearance': appearance, 'jobnavigator_theme': theme,
          'jobnavigator_welcomed': '1'}
    ls.update(extra or {})
    return h.page(b, appearance=appearance, width=width, height=height, extra_ls=ls)


def seeded_page(b, extra=None, appearance='light', theme='default', width=1440, height=900):
    """Like mpage, but the seed runs ONCE per context (raw_ctx's guard) instead of
    on every navigation — required by any case that reloads and expects the app's
    own writes to survive. h.context's init script re-seeds on each navigation."""
    ls = {'jobnavigator_appearance': appearance, 'jobnavigator_theme': theme,
          'jobnavigator_welcomed': '1'}
    ls.update(extra or {})
    return raw_page(b, ls=ls, width=width, height=height)


def go(pg, route, settle=900):
    return h.go(pg, route, settle=settle)


# ── page probes ─────────────────────────────────────────────────────────────
def console_errors(pg):
    log = pg.jn_log
    errs = [c['text'] for c in log['console'] if c['type'] == 'error' and not NOISE.search(c['text'])]
    perrs = [e for e in log['pageerrors'] if not NOISE.search(e)]
    return errs, perrs


def clear_log(pg):
    for k in pg.jn_log:
        pg.jn_log[k].clear()


# Content that scrolls sideways inside its own `overflow-x: auto` box is the
# documented pattern for wide tables/diagrams, so anything under such a box is
# excluded; everything else that reaches past the viewport is real overflow —
# this is the measurement that found DS-S-11 / DS-S-12 in the round-design smoke.
OVERFLOW_JS = """() => {
  const de = document.documentElement;
  const root = document.querySelector('main') || document.body;
  const scroller = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll') return true;
    }
    return false;
  };
  let maxRight = 0, worst = null;
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    if (r.right <= maxRight) continue;
    if (scroller(el)) continue;
    maxRight = r.right;
    worst = el.tagName + (el.getAttribute('class') ? '.' + el.getAttribute('class') : '')
          + ' «' + (el.textContent || '').trim().slice(0, 34) + '»';
  }
  return { sw: de.scrollWidth, iw: window.innerWidth, right: Math.round(maxRight), worst };
}"""


def overflow(pg):
    return pg.evaluate(OVERFLOW_JS)


# only the six rail items that actually carry a badge (V2App's countKey set)
RAIL_JS = """() => {
  const WANT = ['/v2/feed', '/v2/searches', '/v2/companies', '/v2/applications',
                '/v2/resumes', '/v2/cover-letters'];
  const a = document.querySelector('aside');
  if (!a) return null;
  const counts = {};
  for (const link of a.querySelectorAll('nav a[href^="/v2/"]')) {
    const href = link.getAttribute('href');
    if (!WANT.includes(href)) continue;
    const spans = [...link.querySelectorAll('span')];
    counts[href] = spans.length ? (spans[spans.length - 1].textContent || '').trim() : '';
  }
  const txt = a.innerText || '';
  const m = txt.match(/Scraper (?:healthy|run failed)[^\\n]*|No scrape recorded yet|Backend unreachable|\\d+ sources? needs? attention/);
  const dot = [...a.querySelectorAll('span')].some((s) => {
    const st = getComputedStyle(s);
    return st.width === '7px' && st.height === '7px';
  });
  return { counts, health: m ? m[0] : null, dot };
}"""


def rail(pg):
    return pg.evaluate(RAIL_JS)


def rail_counts_within(pg, ms=1200):
    """Poll the rail until every badge carries a number, or ms elapses."""
    t0 = time.time()
    last = None
    while (time.time() - t0) * 1000 < ms:
        last = rail(pg)
        if last and last['counts'] and all(v not in ('', None) for v in last['counts'].values()):
            return last, int((time.time() - t0) * 1000)
        pg.wait_for_timeout(80)
    return last, int((time.time() - t0) * 1000)


def heading(pg):
    """The screen's PageTitle text — first heading-ish node inside <main>."""
    return pg.evaluate("""() => {
      const m = document.querySelector('main'); if (!m) return null;
      const t = (m.innerText || '').trim().split('\\n').filter((l) => l.trim())[0];
      return t ? t.trim() : null;
    }""")


def ls_get(pg, key):
    return pg.evaluate('(k) => { try { return localStorage.getItem(k) } catch (e) { return "ERR" } }', key)


def html_attrs(pg):
    return pg.evaluate("""() => ({
      appearance: document.documentElement.getAttribute('data-appearance'),
      theme: document.documentElement.getAttribute('data-theme'),
      dark: document.documentElement.classList.contains('dark'),
    })""")


def body_has(pg, text):
    return pg.evaluate('(t) => (document.body.innerText || "").includes(t)', text)


# ── overlays (modal / menu open-close probing) ──────────────────────────────
def overlay_count(pg):
    """Round-3's methodology: visible positioned overlays with z-index in [20, 100)."""
    return pg.evaluate("""() => [...document.querySelectorAll('body *')].filter((el) => {
      const cs = getComputedStyle(el);
      if (cs.position !== 'fixed' && cs.position !== 'absolute') return false;
      const z = parseInt(cs.zIndex, 10);
      if (!(z >= 20 && z < 100)) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }).length""")


def outside_point(pg):
    """A click target that is guaranteed outside any panel and inert.

    The far corner (3,3) that round 3 used lands on the nav RAIL, which sits
    above a Drawer's own scrim (see smoke-final DS-S-01) — this uses the page
    title strip inside <main> instead.
    """
    r = h.rect(pg, 'main')
    return (int(r['left'] + 40), int(r['top'] + 14))


# ── row targeting ───────────────────────────────────────────────────────────
# A naive "walk up until an ancestor mentions my row's name" lands on the whole
# LIST once the name is far enough up the tree, and then index 0 of the control
# is somebody ELSE's row. Every lookup here therefore has to prove the ancestor
# it settled on mentions our marker and NONE of the other rows' names.
ROW_INDEX_JS = """([sel, marker, others]) => {
  const ctrls = [...document.querySelectorAll(sel)];
  const seen = [];
  for (let i = 0; i < ctrls.length; i++) {
    let el = ctrls[i];
    for (let k = 0; k < 10 && el; k++) {
      el = el.parentElement;
      if (!el) break;
      const t = el.innerText || '';
      if (!t.includes(marker)) continue;
      // first ancestor that mentions us — it must mention nobody else
      const clash = others.filter((o) => t.includes(o));
      if (!clash.length) return { i, text: t.replace(/\\s+/g, ' ').slice(0, 120) };
      seen.push({ i, clash, text: t.replace(/\\s+/g, ' ').slice(0, 120) });
      break;
    }
  }
  return { none: true, controls: ctrls.length, tried: seen.slice(0, 3) };
}"""


def row_index(pg, sel, marker, others):
    """Index into `sel` for the control belonging to the row named `marker`.

    Returns a dict with `i` on success, or one carrying `none: True` plus what it
    rejected. Callers MUST treat the failure form as a failure and click NOTHING —
    guessing here once deleted a real user row.
    """
    r = pg.evaluate(ROW_INDEX_JS, [sel, marker, list(others)])
    return None if (not r or r.get('none')) else r


def row_index_debug(pg, sel, marker, others):
    return pg.evaluate(ROW_INDEX_JS, [sel, marker, list(others)])


# ── ZZE scratch rows ────────────────────────────────────────────────────────
_TRASH = []


def track(kind, rid):
    _TRASH.append((kind, rid))
    return rid


def untrack(kind, rid):
    if (kind, rid) in _TRASH:
        _TRASH.remove((kind, rid))


def sweep():
    """Delete every ZZE row this run created, and report anything left behind."""
    left = []
    for kind, rid in list(_TRASH):
        st, _ = h.delete(f'/{kind}/{rid}')
        if st not in (200, 204, 404):
            left.append((kind, rid, st))
        else:
            untrack(kind, rid)
    return left


def stray_zze():
    """ZZE rows visible through the API — never touches anything else."""
    out = {}
    for kind, field in (('searches', 'name'), ('companies', 'name'), ('resumes', 'name')):
        st, d = h.get(f'/{kind}')
        if st == 200 and isinstance(d, list):
            out[kind] = [r.get('id') for r in d if str(r.get(field) or '').startswith(PREFIX)]
    return out


def api_ok(st):
    return 200 <= st < 300
