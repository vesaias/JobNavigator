"""D0/D4 pixel baseline: full-page screenshots of every v2 route, both themes, two viewports.

Run inside the backend container: python /tmp/v2t/shots.py <stage>  →  /tmp/v2t/shots/<stage>/<route>__<theme>__<w>.png
Copy out with: docker compose cp backend:/tmp/v2t/shots/<stage> v2-testing/artifacts/design/<stage>
Animations/transitions are disabled, the caret hidden, and hover state neutralised (mouse parked at 0,0).
"""
import sys, os, json
sys.path.insert(0, '/tmp/v2t')
from h import *

stage = sys.argv[1] if len(sys.argv) > 1 else 'D0'
SKIN = sys.argv[sys.argv.index('--skin') + 1] if '--skin' in sys.argv else None  # e.g. --skin alt (sets localStorage jobnavigator_skin before load)
OUT = f'/tmp/v2t/shots/{stage}'; os.makedirs(OUT, exist_ok=True)
CSS = "*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; } html { scroll-behavior: auto !important; }"

def unwrap(d): return d if isinstance(d, list) else (d.get('resumes') or d.get('items') or [])
st, bases = get('/resumes?is_base=true'); bases = unwrap(bases)
st, copies = get('/resumes?is_base=false'); copies = unwrap(copies)
st, cls = get('/cover-letters'); cls = cls if isinstance(cls, list) else cls.get('cover_letters', cls.get('items', []))
withjob = next((c for c in copies if c.get('job_id')), None)
ROUTES = ['/v2/feed', '/v2/searches', '/v2/companies', '/v2/applications', '/v2/resumes', '/v2/cover-letters', '/v2/persona', '/v2/stats', '/v2/settings', '/v2/toasts']
if bases: ROUTES.append(f"/v2/resumes/{bases[0]['id']}")
if withjob: ROUTES.append(f"/v2/resumes/{withjob['id']}")
if cls: ROUTES.append(f"/v2/cover-letters/{cls[0]['id']}")
index = {}
with browser() as b:
    for th in ('light', 'dark'):
        for w, hgt in ((1440, 900), (1024, 700)):
            for r in ROUTES:
                pg = page(b, th); pg.set_viewport_size({'width': w, 'height': hgt})
                if SKIN: pg.add_init_script(f"localStorage.setItem('jobnavigator_skin', '{SKIN}')")
                try: pg.clock.set_fixed_time('2026-09-04T12:00:00Z')  # freeze 'N min ago' strings
                except Exception: pass
                go(pg, r); pg.add_style_tag(content=CSS); pg.mouse.move(0, 0); pg.wait_for_timeout(400)
                name = r.strip('/').replace('/', '_')[:60] + f'__{th}__{w}.png'
                pg.screenshot(path=f'{OUT}/{name}', full_page=False)
                txt = pg.evaluate("(document.querySelector('.jn-v2 main')||document.body).innerText.length")
                index[name] = {'route': r, 'theme': th, 'width': w, 'errors': pg.jn_log['pageerrors'][:1], 'main_text': txt}
                pg.context.close()
json.dump(index, open(f'{OUT}/index.json', 'w'), indent=1)
bad = [(n, v['errors'], v['main_text']) for n, v in index.items() if v['errors'] or v['main_text'] < 40]
print(f'{len(index)} screenshots → {OUT}' + (f' · BLANK/ERROR routes: {bad}' if bad else ' · all routes rendered'))
