# Stage 3 brief — per-screen verification (read fully before starting)

You are verifying ONE screen of the v2 redesign of JobNavigator (repo `V:\JTrakProject`, branch `v2-redesign`). Read `frontend/src/v2/HANDOVER.md` sections "Verification bar", "Traps in the harness itself" and "Conventions" first. Do not repeat its mistakes.

## Inputs
- Your screen's JSX under `frontend/src/v2/`, its inventory under `v2-testing/inventory/` (every control is a checkbox), its design board under `v2-testing/design/*.dc.html`, and the v1 counterpart under `frontend/src/components/` for behaviour reference.
- **Read the design `.dc.html` in full** — the `<script type="text/x-dc">` block at the bottom holds section lists, labels, state colours and every `style-hover`. Never work from a screenshot or a summary. Design colour → token map: `#e2ddd0`→`--line`, `#eeeae0`→`--line-soft`, `#8a826e`→`--edge`, `#f3f0e8`→`--surface-2`, `#faf8f3`→`--bg`, `#fdfcf9`→`--recessed`, `#3f6b52`→`--accent`, `#9c3b30`→`--bad`, `#c9c3b4`→`--line-strong`.

## Environment
- Stack is up. **The backend does NOT hot-reload** (uvicorn runs without `--reload`): a backend edit is live only after `docker compose restart backend`. Do not restart it yourself while other agents run — SendMessage `main` with "backend restart needed: <file>" and continue with other checks; I restart between waves and reply. Frontend is a static bundle built in Docker — **do NOT run `docker compose build`** (other agents share the stack; I rebuild once after the wave). JSX fixes are therefore "fixed in source, unverified — rebuild pending".
- Docker from Git Bash: `DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"; export MSYS_NO_PATHCONV=1; "$DOCKER" compose exec -T backend python /tmp/v2t/<script>.py`
- **Playwright runs INSIDE the backend container** against `http://caddy`. API key `pick-a-password`. From the host, `curl -H "X-API-Key: pick-a-password" http://localhost/api/...` works.
- Harness at `/tmp/v2t/h.py` in the container (read its docstring first: `"$DOCKER" compose exec -T backend sed -n 1,40p /tmp/v2t/h.py`). It gives `browser()`, `page(b, theme)`, `go`, `rect`, `style`, `hover_delta`, `assert_int_tops`, `snap`, `px_stats`, `report`, and `get/post/patch/delete` API helpers. Import with `import sys; sys.path.insert(0,'/tmp/v2t'); from h import *`.
- Write every script locally to `C:\Users\Viktor\AppData\Local\Temp\claude\V--JTrakProject\f8561639-bab8-4916-b542-79cea1ae0ae5\scratchpad\<screen>_<n>.py` with the Write tool (unique `<screen>_` prefix — the scratchpad is shared), then `"$DOCKER" compose cp <local path> backend:/tmp/v2t/` and run it. **Never inline a script in a bash heredoc** (backticks, `%`, `\n` and quotes break). Screenshots go to `/tmp/v2t/shots/` and can be copied out with `"$DOCKER" compose cp backend:/tmp/v2t/shots/<f>.png v2-testing/artifacts/<screen>/`.
- Headless Linux: overlay scrollbars (width 0), no platform fonts, no PDF viewer (blob loads abort — not a defect). Auth needs the warm-up the harness does. Scope locators to the row; loose `get_by_text` matches values elsewhere.

## Data rules (this is the user's real database, backed up)
- Create scratch rows with the prefix `ZZTEST` in their name/title and **delete every one of them before you finish**. Never delete or mutate rows you did not create, except reversible single-field edits you restore immediately (record before/after).
- Never fire global triggers: `/scrape/run-all`, `/db/cleanup`, `/auto-reject/run`, `/email/check-now`, `/telegram/digest`, `/db/backup`, `/h1b/refresh`, `/jobs/backfill-descriptions`, `/companies/refresh-h1b`. Those are Stage 5.
- No LinkedIn Personal / Jobright / JobSpy / freehire runs. Company test-scrape only against a public Greenhouse / Lever / Ashby board URL.
- Real LLM calls: at most 2 per screen, only where the flow cannot be exercised otherwise. For failure paths use Playwright route interception (`page.route('**/api/...', lambda r: r.fulfill(status=500, body='{"detail":"boom"}'))`) and 401 (`status=401`).

## What "verified" means (per inventory checkbox)
1. **Every control works** — click it, assert the API call happened (intercept or check the response), assert the state/DOM changed, assert the toast (kind) appeared where the inventory says it should. Success paths AND the 500/401 path.
2. **States**: empty (0 rows, via filters or a scratch account of data), one, many, a 200-character title/name, a null field (e.g. `cv_scores=null`, no company, no url). Empty-DB rendering is a separate later pass — skip it.
3. **Light AND dark**: measure computed `color`/`background-color`/`border-color` of the key elements in both themes; confirm they differ and that no light-only value survives in dark (compare against theme.css). Screenshot both for the record.
4. **Hovers**: list every `style-hover` in the design first; for each, `hover_delta` the built element and compare the changed properties. Extra hovers not in the design are defects too (P3).
5. **Geometry**: where the design gives numbers (paddings, heights, widths, font sizes), measure with `rect`/`style` and print design-vs-measured. Run `assert_int_tops` on every list/table — fractional tops are a P3.
6. **Console**: `report(pg)` must be clean apart from expected iframe/PDF noise.
7. **Deep links / ids**: the routes and params in the inventory, including a missing/deleted id.

Measure, don't eyeball. A screenshot is a record, never evidence.

## Fixing vs logging
- Fix in source only if **unambiguous and contained (< 50 lines, one obviously correct answer)**. Backend fixes: mark "restart pending" and verify after I confirm the restart. JSX fixes: note "fixed in source, rebuild pending". Never widen scope.
- Everything else: log. No cap on the list; long is good.

## Output — `v2-testing/stage3/<screen>.md` (Write early, Edit to append as you go, so progress survives a cut-off)
```
# Stage 3 — <Screen>
Tested: <date>, bundle index-Dnrx3n0f.js (HEAD 9ed8963), themes light+dark, viewport 1440×900 (+ one narrow 1024×700 pass)
Design: <file>   Inventory: <file>   Scripts: <list>

## Findings
### <SCREEN>-01 · P{1-4} · <title>
**Where** file:line + route
**Repro** steps
**Expected + why** cite the .dc.html line/prop or v1 code line
**Actual** measured value(s)
**Proposed fix**
**Status** fixed in source (rebuild pending) | fixed + verified (backend) | needs decision: <the exact question>

## Fixed in source
- file:line — one line each

## Couldn't test
- item — why

## Scratch data
- created … / deleted … (must end empty)
```
Severity: P1 broken/data-loss · P2 functional · P3 design deviation · P4 nit.
Also tick the inventory file as you go: `- [x]` verified OK, `- [!]` failed (append the finding id), `- [~]` untestable (say why).

Finish with a summary: boxes verified / failed / untestable, findings by severity, fixes applied, scratch rows remaining (must be 0).

## Addenda (2026-09-02 13:00)
- **Design deviations are decisions, not defects.** The user deliberately changed some things in code for cross-screen consistency (unified accent hovers, green tailored badge, lifted rail-dim, etc.). Log a design difference as P3/P4 with status `needs decision: keep code (consistency) or match design?` — unless it is clearly accidental (dead hover, missing state, wrong token, half-pixel rows).
- Your `v2-testing/stage3/<screen>.md` may already exist with only a header from an earlier cut-off run — overwrite it.
- Companies: three fixes are already in source from the earlier run (backend `create_company` was patched to persist `aliases` + `auto_scoring_depth` but a live POST still returns aliases=[] and depth=off — NOT verified, investigate; `detectAts` aligned to the backend; test-modal summary arithmetic). Verify, don't redo.
- Budget: you are on Opus. Be economical — one recon script per area, batch measurements, avoid re-reading large files. Write output incrementally.
