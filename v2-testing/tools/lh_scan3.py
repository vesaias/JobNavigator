import sys, json
sys.path.insert(0, '/tmp/v2t')
from h import *

JS = r"""
() => {
  const root = document.querySelector('.jn-v2 main') || document.querySelector('.jn-v2');
  if (!root) return {error: 'no root'};
  const isFrac = v => Math.abs(v - Math.round(v)) > 0.01;
  const rc = new Map();
  const R = el => { let v = rc.get(el); if (!v) { v = el.getBoundingClientRect(); rc.set(el, v); } return v; };
  const desc = el => {
    const cs = getComputedStyle(el);
    const r = R(el);
    let p = [], n = el;
    while (n && n !== root && p.length < 8) {
      let s = n.tagName.toLowerCase();
      const c = (typeof n.className === 'string') ? n.className.trim() : '';
      if (c) s += '.' + c.split(/\s+/).slice(0, 3).join('.');
      p.unshift(s); n = n.parentElement;
    }
    return {tag: el.tagName.toLowerCase(), cls: (typeof el.className === 'string' ? el.className : ''),
            sty: (el.getAttribute('style') || '').slice(0, 200),
            text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 44),
            fs: cs.fontSize, lh: cs.lineHeight,
            h: Math.round(r.height * 1000) / 1000, w: Math.round(r.width * 100) / 100,
            top: Math.round(r.top * 1000) / 1000, path: p.join(' > ')};
  };
  // fractional-height leaves inside a culprit
  const leaves = el => {
    const out = [];
    const walk = n => {
      let deeper = false;
      for (const c of n.children) { const r = R(c); if ((r.width || r.height) && isFrac(r.height)) { deeper = true; walk(c); } }
      if (!deeper && n !== el) out.push(desc(n));
      if (!deeper && n === el) out.push(desc(n));
    };
    walk(el);
    return out;
  };
  // affected blocks: wide, sensible height, fractional top
  const blocks = [];
  for (const el of root.querySelectorAll('*')) {
    const r = R(el);
    if (r.width < 280) continue;
    if (r.height < 12 || r.height > 400) continue;
    if (!isFrac(r.top) && !isFrac(r.height)) continue;
    const cs = getComputedStyle(el);
    const hasBorder = ['borderTopWidth','borderBottomWidth','borderLeftWidth','borderRightWidth'].some(p => parseFloat(cs[p]) > 0);
    blocks.push({el: el, hasBorder: hasBorder, r: r});
  }
  // culprit search
  const culprits = new Map();
  for (const b of blocks) {
    if (!isFrac(b.r.top)) continue;
    let cur = b.el, guard = 0;
    while (cur && cur !== root && guard++ < 30) {
      let found = false;
      let s = cur.previousElementSibling;
      while (s) {
        const sr = R(s);
        if ((sr.width || sr.height) && isFrac(sr.height)) {
          if (!culprits.has(s)) culprits.set(s, {n: 0, bordered: 0});
          const c = culprits.get(s); c.n++; if (b.hasBorder) c.bordered++;
          found = true;
        }
        s = s.previousElementSibling;
      }
      if (found) break;
      cur = cur.parentElement;
      if (cur && !isFrac(R(cur).top)) break;
    }
  }
  const res = {blocks_frac_top: blocks.filter(b => isFrac(b.r.top)).length,
               blocks_frac_top_bordered: blocks.filter(b => isFrac(b.r.top) && b.hasBorder).length,
               blocks_frac_h: blocks.filter(b => isFrac(b.r.height)).length,
               culprits: []};
  for (const [el, c] of culprits) {
    res.culprits.push({affects: c.n, affects_bordered: c.bordered, self: desc(el), leaves: leaves(el).slice(0, 8)});
  }
  res.culprits.sort((a, b) => b.affects - a.affects);
  // also: wide blocks with fractional own height (they break their own border)
  res.self_frac = blocks.filter(b => isFrac(b.r.height)).slice(0, 12).map(b => ({d: desc(b.el), bordered: b.hasBorder, leaves: leaves(b.el).slice(0, 10)}));
  return res;
}
"""

st, cls = get('/cover-letters')
cl_id = cls[0].get('id') if isinstance(cls, list) and cls else None

ROUTES = [
    ('feed', '/v2/feed', 'click_job'),
    ('searches', '/v2/searches', None),
    ('companies', '/v2/companies', None),
    ('applications', '/v2/applications', None),
    ('resumes', '/v2/resumes', None),
    ('resume-editor', '/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a', 'expand'),
    ('cover-letters', '/v2/cover-letters', None),
    ('persona', '/v2/persona', 'persona'),
    ('stats', '/v2/stats', None),
    ('settings', '/v2/settings', None),
]
if cl_id:
    ROUTES.insert(7, ('cover-letter-editor', '/v2/cover-letters/' + str(cl_id), None))

results = {}
with browser() as b:
    pg = page(b, theme='light')
    for name, route, action in ROUTES:
        try:
            go(pg, route, settle=1400)
        except Exception as e:
            results[name] = {'error': str(e)[:160]}; continue
        try:
            if action == 'click_job':
                try:
                    pg.locator('.v2-row').first.click(timeout=4000)
                except Exception:
                    pg.locator('main li, main [role="button"]').first.click(timeout=4000)
                pg.wait_for_timeout(1000)
            elif action == 'expand':
                for label in ['Experience', 'Skills', 'Education', 'Summary', 'Projects']:
                    try:
                        pg.locator('main').get_by_text(label, exact=True).first.click(timeout=2000)
                        pg.wait_for_timeout(350)
                    except Exception:
                        pass
            elif action == 'persona':
                for label in ['Experience', 'Résumé content', 'Resume content']:
                    try:
                        pg.locator('main').get_by_text(label, exact=True).first.click(timeout=2000)
                        pg.wait_for_timeout(450)
                    except Exception:
                        pass
        except Exception:
            pass
        pg.wait_for_timeout(500)
        try:
            results[name] = pg.evaluate(JS)
        except Exception as e:
            results[name] = {'error': str(e)[:200]}
        r = results[name]
        print('%-20s frac_top_blocks=%s bordered=%s frac_h=%s culprits=%s' % (
            name, r.get('blocks_frac_top'), r.get('blocks_frac_top_bordered'), r.get('blocks_frac_h'),
            len(r.get('culprits', []))))

with open('/tmp/v2t/lh_scan3.json', 'w') as f:
    json.dump(results, f, indent=1)
print('WROTE')
