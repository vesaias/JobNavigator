"""D0/D4 computed-style baseline. Run inside the backend container:
python /tmp/v2t/stylecrawl.py <stage>  →  /tmp/v2t/shots/<stage>/styles.json
For every visible element on every v2 route (light and dark, 1440×900): a stable key
(route, theme, DOM path with classes, text head) → rest tuple + hover tuple (for elements with cursor:pointer or a v2-* class).
"""
import sys, os, json
sys.path.insert(0, '/tmp/v2t')
from h import *
stage = sys.argv[1] if len(sys.argv) > 1 else 'D0'
THEME = sys.argv[sys.argv.index('--theme') + 1] if '--theme' in sys.argv else None  # e.g. --theme alt (sets localStorage jobnavigator_theme before load)
OUT = f'/tmp/v2t/shots/{stage}'; os.makedirs(OUT, exist_ok=True)
PROPS = ['backgroundColor', 'color', 'borderTopWidth', 'borderTopColor', 'borderBottomColor', 'borderTopStyle', 'borderRadius', 'boxShadow', 'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'paddingTop', 'paddingLeft', 'height', 'letterSpacing', 'textTransform', 'opacity', 'cursor']
JS_REST = """(props) => {
  const out = {};
  const path = (e) => { const p = []; while (e && e.nodeType === 1 && !e.classList.contains('jn-v2')) { let s = e.tagName.toLowerCase(); if (e.className && typeof e.className === 'string') s += '.' + e.className.trim().split(/\\s+/).join('.'); const sib = [...e.parentElement.children].filter(x => x.tagName === e.tagName); if (sib.length > 1) s += ':' + sib.indexOf(e); p.unshift(s); e = e.parentElement; } return p.join('>'); };
  window.__jnPath = path;
  window.__jnEls = new Map();
  for (const e of document.querySelectorAll('.jn-v2 *')) {
    const r = e.getBoundingClientRect(); if (e.getClientRects().length === 0 || r.width < 1 || r.height < 4 || r.bottom < 0 || r.top > innerHeight) continue;
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const t = {}; for (const p of props) t[p] = cs[p];
    const txt = (e.childNodes.length && e.childNodes[0].nodeType === 3) ? e.childNodes[0].textContent.trim().slice(0, 24) : '';
    const hoverable = cs.cursor === 'pointer' || /\\bv2-/.test(e.className || '');
    const ep = path(e);
    const key = ep + (txt ? '|' + txt : '');
    window.__jnEls.set(key, e);
    out[key] = { rest: t, hoverable, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + Math.min(r.height / 2, 12)), path: ep };
  }
  return out;
}"""
JS_HOVER = """([x, y, key, path0, props]) => {
  const e2 = document.elementFromPoint(x, y);
  if (!e2) return null;
  const pathFn = window.__jnPath;
  const path2 = pathFn ? pathFn(e2) : null;
  const matched = path2 === path0;
  const target = matched ? e2 : (window.__jnEls && window.__jnEls.get(key));
  if (!target) return null;
  const cs = getComputedStyle(target);
  const t = {}; for (const p of props) t[p] = cs[p];
  return { style: t, matched };
}"""
def unwrap(d): return d if isinstance(d, list) else (d.get('resumes') or d.get('items') or [])
st, bases = get('/resumes?is_base=true'); bases = unwrap(bases)
st, copies = get('/resumes?is_base=false'); copies = unwrap(copies)
st, cls = get('/cover-letters'); cls = cls if isinstance(cls, list) else cls.get('cover_letters', cls.get('items', []))
withjob = next((c for c in copies if c.get('job_id')), None)
ROUTES = ['/v2/feed', '/v2/searches', '/v2/companies', '/v2/applications', '/v2/resumes', '/v2/cover-letters', '/v2/persona', '/v2/stats', '/v2/settings']
if bases: ROUTES.append(f"/v2/resumes/{bases[0]['id']}")
if withjob: ROUTES.append(f"/v2/resumes/{withjob['id']}")
if cls: ROUTES.append(f"/v2/cover-letters/{cls[0]['id']}")
data = {}
hover_total = 0
hover_match = 0
with browser() as b:
    for th in ('light', 'dark'):
        for r in ROUTES:
            pg = page(b, th)
            if THEME: pg.add_init_script(f"localStorage.setItem('jobnavigator_theme', '{THEME}')")
            try: pg.clock.set_fixed_time('2026-09-04T12:00:00Z')
            except Exception: pass
            go(pg, r); pg.add_style_tag(content='*, *::before, *::after { transition: none !important; animation: none !important; }'); pg.mouse.move(0, 0); pg.wait_for_timeout(300)
            els = pg.evaluate(JS_REST, PROPS)
            # hover pass: at most 400 hoverable elements per route, sampled in DOM order
            hov = [k for k, v in els.items() if v['hoverable']][:400]
            for k in hov:
                v = els[k]
                try:
                    pg.mouse.move(v['x'], v['y']); pg.wait_for_timeout(30)
                    res = pg.evaluate(JS_HOVER, [v['x'], v['y'], k, v['path'], PROPS])
                except Exception: res = None
                if res:
                    v['hover'] = res['style']
                    hover_total += 1
                    if res['matched']: hover_match += 1
                else:
                    v['hover'] = None
            pg.mouse.move(0, 0)
            for k, v in els.items(): data[f'{th}|{r}|{k}'] = {'rest': v['rest'], 'hover': v.get('hover')}
            pg.context.close()
json.dump(data, open(f'{OUT}/styles.json', 'w'))
print(f'{len(data)} elements, hover {hover_match}/{hover_total} matched keyed path → {OUT}/styles.json')
