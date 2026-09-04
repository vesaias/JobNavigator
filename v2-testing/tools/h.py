"""Shared Playwright harness for the v2 verification pass. Lives at /tmp/v2t/h.py in the backend container.

Usage inside a test script:
    import sys; sys.path.insert(0, '/tmp/v2t'); from h import *
    with browser() as b:
        pg = page(b, appearance='dark')           # authed context, warmed up
        go(pg, '/v2/feed')
        r = rect(pg, 'text=Jobs')            # {'x','y','w','h','top','bottom'}
        cs = style(pg, '.v2-card >> nth=0', ['borderColor','backgroundColor'])
        assert_int_tops(pg, '[data-row]')    # fails on fractional getBoundingClientRect().top
        hov = hover_delta(pg, '.v2-card >> nth=0', ['borderColor','backgroundColor','color'])
        snap(pg, 'feed-dark')                # /tmp/v2t/shots/feed-dark.png
"""
import json, os, contextlib, urllib.request, urllib.error, time
from playwright.sync_api import sync_playwright

BASE = os.environ.get("JN_BASE", "http://caddy")
KEY = os.environ.get("JN_KEY", "pick-a-password")
OUT = "/tmp/v2t"
os.makedirs(f"{OUT}/shots", exist_ok=True)


# ── API ──────────────────────────────────────────────────────────────────
def api(method, path, body=None, key=KEY, raw=False, timeout=120):
    """Call the backend. Returns (status, json_or_text). Never raises on HTTP errors."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + "/api" + path, data=data, method=method,
                                 headers={"X-API-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            st = r.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace"); st = e.code
    if raw:
        return st, txt
    try:
        return st, json.loads(txt) if txt else None
    except ValueError:
        return st, txt


def get(path, **kw): return api("GET", path, **kw)
def post(path, body=None, **kw): return api("POST", path, body, **kw)
def patch(path, body=None, **kw): return api("PATCH", path, body, **kw)
def delete(path, **kw): return api("DELETE", path, **kw)


# ── browser ──────────────────────────────────────────────────────────────
@contextlib.contextmanager
def browser(headless=True):
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless)
        try:
            yield b
        finally:
            b.close()


def context(b, appearance="light", width=1440, height=900, dsf=1, key=KEY, extra_ls=None):
    ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=dsf)
    ls = {"jobnavigator_api_key": key, "jobnavigator_dark_mode": "true" if appearance == "dark" else "false",
          "jobnavigator_welcome_seen": "true", "jobnavigator_v2_welcome_seen": "true"}
    ls.update(extra_ls or {})
    ctx.add_init_script("try{" + "".join(f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in ls.items()) + "}catch(e){}")
    # warm-up: lets App.jsx sync the cookie session so /api hrefs work
    w = ctx.new_page(); w.goto(BASE + "/v2/feed", wait_until="networkidle"); w.wait_for_timeout(500); w.close()
    return ctx


def page(b, appearance="light", **kw):
    """Fresh page with console/network capture attached at pg.jn_log."""
    ctx = context(b, appearance=appearance, **kw)
    pg = ctx.new_page()
    attach_log(pg)
    return pg


def attach_log(pg):
    log = {"console": [], "pageerrors": [], "http": [], "reqfailed": []}
    pg.on("console", lambda m: log["console"].append({"type": m.type, "text": m.text[:400]}) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: log["pageerrors"].append(str(e)[:400]))
    pg.on("response", lambda r: log["http"].append({"status": r.status, "url": r.url[-140:], "method": r.request.method}) if r.status >= 400 else None)
    pg.on("requestfailed", lambda r: log["reqfailed"].append({"url": r.url[-140:], "err": (r.failure or "")[:100]}) if "favicon" not in r.url and not r.url.startswith("blob:") else None)
    pg.jn_log = log
    return log


def go(pg, route, settle=800, wait="networkidle", timeout=45000):
    pg.goto(BASE + route, wait_until=wait, timeout=timeout)
    pg.wait_for_timeout(settle)
    return pg


def set_appearance(pg, appearance):
    pg.evaluate(f"localStorage.setItem('jobnavigator_dark_mode', '{'true' if appearance == 'dark' else 'false'}')")
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(600)


# ── measurement ──────────────────────────────────────────────────────────
def rect(pg, sel):
    return pg.evaluate("""(sel) => { const el = typeof sel === 'string' ? document.querySelector(sel) : sel; if (!el) return null;
        const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, top: r.top, bottom: r.bottom, left: r.left, right: r.right}; }""", sel) if not hasattr(sel, "evaluate") else sel.evaluate("el => { const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, top: r.top, bottom: r.bottom, left: r.left, right: r.right}; }")


def style(pg_or_loc, sel_or_props, props=None):
    """style(pg, css_selector, [props]) or style(locator, [props])."""
    js = "(el, props) => { const cs = getComputedStyle(el); const o = {}; for (const p of props) o[p] = cs[p]; return o; }"
    if props is None:
        loc, props = pg_or_loc, sel_or_props
        return loc.evaluate(js, props)
    return pg_or_loc.locator(sel_or_props).first.evaluate(js, props)


def hover_delta(pg, sel, props, settle=250):
    """Computed style before vs after hover for the first match of sel. Returns {'before':{},'after':{},'changed':[...]}"""
    loc = pg.locator(sel).first
    before = style(loc, props)
    loc.hover(); pg.wait_for_timeout(settle)
    after = style(loc, props)
    pg.mouse.move(0, 0); pg.wait_for_timeout(120)
    return {"before": before, "after": after, "changed": [p for p in props if before[p] != after[p]]}


def tops(pg, sel):
    return pg.evaluate("(sel) => [...document.querySelectorAll(sel)].map(e => e.getBoundingClientRect().top)", sel)


def assert_int_tops(pg, sel):
    ts = tops(pg, sel)
    frac = [t for t in ts if abs(t - round(t)) > 0.01]
    return {"count": len(ts), "fractional": len(frac), "samples": frac[:5]}


def text(pg, sel):
    return pg.locator(sel).first.inner_text()


def snap(pg, name, full=False, clip_sel=None, dsf=None):
    path = f"{OUT}/shots/{name}.png"
    if clip_sel:
        pg.locator(clip_sel).first.screenshot(path=path)
    else:
        pg.screenshot(path=path, full_page=full)
    return path


def px_stats(path):
    """Mean RGB + count of distinct colours of a PNG (needs PIL; falls back to None)."""
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB"); px = list(im.getdata())
        n = len(px); mean = tuple(sum(c[i] for c in px) // n for i in range(3))
        return {"mean": mean, "distinct": len(set(px)), "size": im.size}
    except Exception as e:
        return {"error": str(e)[:100]}


def report(pg):
    """Console/network log summary for the page."""
    l = pg.jn_log
    return {k: len(v) for k, v in l.items()} | {"detail": l}
