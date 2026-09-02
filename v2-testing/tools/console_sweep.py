"""Console/network sweep: every v1+v2 route, light+dark. Runs inside the backend container.
Output: /tmp/v2t/console.json + /tmp/v2t/shots/*.png
"""
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://caddy"
KEY = "pick-a-password"
OUT = "/tmp/v2t"
os.makedirs(f"{OUT}/shots", exist_ok=True)

def api(path):
    req = urllib.request.Request(BASE + "/api" + path, headers={"X-API-Key": KEY})
    return json.load(urllib.request.urlopen(req, timeout=60))

resumes = api("/resumes?is_base=true")
rid = resumes[0]["id"] if resumes else None
cls = api("/cover-letters")
clid = cls[0]["id"] if cls else None
jobs = api("/jobs?limit=1")
jid = (jobs.get("jobs") or jobs.get("items") or [None])[0]
jid = jid["id"] if isinstance(jid, dict) else None

ROUTES = [
    ("v2-feed", "/v2/feed"), ("v2-feed-job", f"/v2/feed?job={jid}"),
    ("v2-searches", "/v2/searches"), ("v2-companies", "/v2/companies"),
    ("v2-applications", "/v2/applications"), ("v2-resumes", "/v2/resumes"),
    ("v2-resume-editor", f"/v2/resumes/{rid}"), ("v2-cover-letters", "/v2/cover-letters"),
    ("v2-cover-letter-editor", f"/v2/cover-letters/{clid}"), ("v2-persona", "/v2/persona"),
    ("v2-stats", "/v2/stats"), ("v2-settings", "/v2/settings"), ("v2-toasts", "/v2/toasts"),
    ("v2-root", "/v2"),
    ("v1-feed", "/"), ("v1-applications", "/applications"), ("v1-companies", "/companies"),
    ("v1-searches", "/searches"), ("v1-settings", "/settings"), ("v1-resumes", "/resumes"),
    ("v1-cover-letters", "/cover-letters"), ("v1-persona", "/persona"), ("v1-stats", "/stats"),
]
IGNORE_SUBSTR = ["favicon", "Download the React DevTools"]

results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        ctx.add_init_script(f"""
            try {{
              localStorage.setItem('jobnavigator_api_key', '{KEY}');
              localStorage.setItem('jobnavigator_dark_mode', '{'true' if theme == 'dark' else 'false'}');
              localStorage.setItem('jobnavigator_welcome_seen', 'true');
              localStorage.setItem('jobnavigator_v2_welcome_seen', 'true');
            }} catch (e) {{}}
        """)
        warm = ctx.new_page(); warm.goto(BASE + "/v2/feed", wait_until="networkidle"); warm.wait_for_timeout(800); warm.close()
        for name, route in ROUTES:
            page = ctx.new_page()
            rec = {"name": name, "route": route, "theme": theme, "console": [], "pageerrors": [], "http": [], "reqfailed": []}
            page.on("console", lambda m, rec=rec: rec["console"].append({"type": m.type, "text": m.text[:400], "loc": (m.location or {}).get("url", "")[-80:]}) if m.type in ("error", "warning") and not any(s in m.text for s in IGNORE_SUBSTR) else None)
            page.on("pageerror", lambda e, rec=rec: rec["pageerrors"].append(str(e)[:400]))
            page.on("response", lambda r, rec=rec: rec["http"].append({"status": r.status, "url": r.url[-120:]}) if r.status >= 400 else None)
            page.on("requestfailed", lambda r, rec=rec: rec["reqfailed"].append({"url": r.url[-120:], "err": (r.failure or "")[:120]}) if "favicon" not in r.url else None)
            t0 = time.time()
            try:
                page.goto(BASE + route, wait_until="networkidle", timeout=45000)
            except Exception as e:
                rec["goto_error"] = str(e)[:300]
            page.wait_for_timeout(1500)
            rec["ms"] = int((time.time() - t0) * 1000)
            rec["final_url"] = page.url
            rec["title"] = page.title()
            try:
                rec["v2_theme_attr"] = page.eval_on_selector(".jn-v2", "el => el.getAttribute('data-theme')")
            except Exception:
                rec["v2_theme_attr"] = None
            try:
                rec["html_dark_class"] = page.evaluate("document.documentElement.classList.contains('dark')")
            except Exception:
                rec["html_dark_class"] = None
            rec["body_text_len"] = page.evaluate("document.body.innerText.length")
            rec["bg"] = page.evaluate("getComputedStyle(document.querySelector('.jn-v2') || document.body).backgroundColor")
            page.screenshot(path=f"{OUT}/shots/{name}_{theme}.png", full_page=False)
            results.append(rec)
            page.close()
        ctx.close()
    browser.close()

json.dump({"ids": {"resume": rid, "cover_letter": clid, "job": jid}, "results": results}, open(f"{OUT}/console.json", "w"), indent=1)
for r in results:
    flag = "!!" if (r["console"] or r["pageerrors"] or r["http"] or r["reqfailed"] or r.get("goto_error")) else "ok"
    print(f"{flag:2} {r['theme']:5} {r['name']:24} {r['ms']:5}ms text={r['body_text_len']:6} theme={r['v2_theme_attr']} dark={r['html_dark_class']} con={len(r['console'])} err={len(r['pageerrors'])} http={len(r['http'])} rf={len(r['reqfailed'])}")
