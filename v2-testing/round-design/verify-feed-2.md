# Feed round 2 — six-bug + metadata-collapse verification

Branch `v2-redesign` @ HEAD `41d6b98`. Frontend was rebuilding when this pass started; confirmed live
by bundle hash: `curl -s http://localhost/v2/feed | grep -o 'index-[A-Za-z0-9_-]*\.js'` returned
`index-BK6JUgyS.js`, which matches none of the hashes recorded anywhere else in `v2-testing/`
(latest prior recorded: `index-9F1Ab3ny.js`/`index-DynVv4lS.js` in `round-design/smoke-final.md`) —
a genuinely new bundle. `docker compose ps` also showed the `frontend` container recreated 23s before
the first request and `backend` recreated 3 min before (the `main.py`/`orchestrator.py`/
`company_pages.py` restart F2 needs), both consistent with a fresh `up --build`.

Backend container Playwright vs `http://caddy`, API key `pick-a-password`, harness at
`/tmp/v2t/h.py` (already present, unmodified). Scripts written locally to the scratchpad, copied in
via `docker compose cp`, run via `docker compose exec -T backend python /tmp/v2t/<name>.py`.
No commits, no builds, no source edits. No LLM calls were made directly: F6's score trigger had its
`POST /api/analyze/{id}` intercepted and fulfilled 202 without reaching the backend, and its
`GET /api/monitor/in-flight` intercepted to hold the job "running" forever so the busy state could be
measured. F2's real `POST /api/scrape/run-all` was explicitly authorized by the task and does invoke
`analyze_unscored_jobs()` server-side after the scrape — that's the system's own designed behavior for
an authorized real run, not a script-initiated score call, so it was left alone (no unscored jobs were
newly created by companies that matter to F2's own claim; the run summary shows `+4 new`, all now
`status=new` in the feed, unscored and inert until the user acts on them).

Status PATCHes: F3 (skip via row ✕) and F5 (bulk skip of 3 rows) both used the in-app Undo, and both
were confirmed restored via `GET /api/jobs` diffed against a pre-test snapshot (`jobs_before_f3.json`
vs `jobs_after_f5.json`) — **0 diffs**, all 12 originally-`saved` jobs still `saved` after both tests.
No manual PATCH revert was needed. The regression pass's keyboard `s`/`x` PATCHes were intercepted
(never reached the backend) and confirmed unchanged in the real DB afterward.

## Results

| id | status | measured |
|---|---|---|
| F1 | ✔ | Job `56ccec75` (Camunda, `cv_scores {"PM":63}`, `scoring_report {}`) opened with `v2_feed_ui={reportOpen:true}` pre-set: band renders `"63 PM Score at full depth to see the report [Full report]"` (1 **Full report** button), no report body. The posting container (`.v2-scroll` wrapper around the iframe/fallback panel) measured `762×568`, `top:332 → bottom:900` (full remaining pane, `display:flex`, not squashed to 0) — this host (`jobs.ashbyhq.com`) is itself frame-blocked, so the mounted content is the "This posting refuses to be framed" panel rather than a live iframe, but the container sizing is what F1 is about and it is correct either way. Job `41d350aa` (Visa, has a report): on load, `reportOpen` persisted `true` + `hasReport` true → `reportShown` true automatically, posting container `display:none`. Clicked the band header once → posting container `display:flex` (report collapsed); clicked again → `display:none` (report re-expanded) — band is a working toggle. 1 console error on the Visa page (`Refused to display '…myworkdayjobs.com/' … X-Frame-Options … deny` + matching `net::ERR_BLOCKED_BY_RESPONSE`) — the same known optimistic-iframe-attempt artifact prior rounds logged against blocked hosts, not a defect. 0 page errors throughout. |
| F2 | ✔ | Triggered a real `POST /api/scrape/run-all` (started `2026-09-04T13:53:01Z`) → polled `/api/monitor/active` until empty (**finished 14:04:31Z**, 690.7s). `/api/monitor/history` row: `result_summary = "63 sources - +4 new - 1 failed"` — no `"N skipped: …"` clause, and that's correct: `GET /api/scrape-log?limit=200` shows **61 distinct `playwright_<company>` rows** dated after the run start, matching the doc's own count of "61 active companies with non-empty `scrape_urls`" exactly — 0 companies skipped this run, so the summary omitting a skip clause is the expected "(or none)" case, not a gap. All **six** named companies now have fresh rows strictly newer than the run start: Anthropic `14:03:39` (33/0), Arize `13:58:42` (5/0), Scale `13:58:03` (20/0), Sierra `14:00:38` (18/0), Snorkelai `13:58:45` (5/0), Airtable `14:01:29` (4/0) — all `is_warning:false`, `error:null`. The "1 failed" in the summary is an unrelated pre-existing `jobright` search error (`"A string literal cannot contain NUL (0x00) characters"`), not a company-scrape failure and out of scope for this fix. |
| F3 | ✔ | `/v2/feed` (default filter, 12 rows), clicked row 0 (Meta, "Product Manager") to select, then clicked its rail ✕ (`title="Skip (x)"`). Row count 12→11 and the panel's title/URL/iframe all updated to the next job (Nomura, "Product Manager- Electronic Trading") in **54 ms** (well under 300 ms) — `?job=` became `b82d1d80…`, `<iframe src>` became the Nomura URL. Clicked the toast's **Undo** → row count back to 12; `GET /api/jobs/{id}` on the skipped job confirmed `status:"saved", saved:true` — its exact pre-skip value, no manual PATCH needed. |
| F4 | ✔ | Three different-host jobs (Visa/`myworkdayjobs.com`, PayPal/`eightfold.ai`, OpenAI/`jobs.ashbyhq.com` — all confirmed `embeddable:false` via `/api/jobs/{id}/frame-check`), each clicked in its own **fresh** browser context (empty `v2_feed_frameable` cache): iframe `src` set in **34 ms / 41 ms / 32 ms** respectively — all ≤150 ms, confirming the probe no longer blocks first paint. Known-blocked-host revisit: in one context, clicked the first of two same-host Microsoft rows, waited 2.5s for the background probe, then read `localStorage['v2_feed_frameable']` = `{"www.metacareers.com":0,"apply.careers.microsoft.com":0}` (the metacareers entry came from the feed's own default row-0 auto-select probe, expected) — confirming the host was cached blocked. Clicking the **second** Microsoft row then showed the "This posting refuses to be framed" fallback in **27 ms** — effectively immediate, vs. the pre-fix 1877/928/812 ms wait the finding documented for a first-seen blocking host. |
| F5 | ✔ | Ctrl-clicked rows 0/1/2 (`"3 selected"` floating bar) → clicked bulk **Skip**. Row count 12→9 in **33 ms** (< 50 ms threshold), no `"Loading…"` text observed in a 5 ms-interval poll across the whole transition. Toast with **Undo** present → clicked it → row count back to 12, and a before/after full `GET /api/jobs?status=new,saved` diff showed **0 differences** across all 12 job ids' `status`/`saved` fields — fully restored, no PATCH needed. |
| F6 | ✔ | Used an unscored job (Sierra, `cv_scores {}`) isolated to row 0 via the title search box, so the row itself also renders the busy ring (the `nsc>0` branch would otherwise show a value ring regardless of `running`). `POST /api/analyze/{id}` intercepted → fulfilled 202 without reaching the backend; `GET /api/monitor/in-flight` intercepted → always reports the job busy, so the running state never resolved to "finished" during measurement. Opened the rescore modal (`r`), résumé pre-selected (`"1 selected"`), clicked **Run scoring**. Measured via `viewBox`/`r`/`stroke-width` attributes + computed style width (not raw `getBoundingClientRect`, which is skewed by the `.v2-spin` rotation transform mid-animation): **row** busy ring — box **44px**, outer arc diameter **37.5px** (`viewBox 0 0 88 88`); **band** busy ring — box **34px**, outer arc diameter **32.7px** (`viewBox 0 0 78 78`). Cross-checked against the *idle* (non-busy) rings on a separately-loaded scored row/band using the same formula: idle row **44 / 37.5px**, idle band **34 / 32.7px** — byte-identical to the busy measurements in both places. |
| Metadata collapse | ✔ | Job `41d350aa` (Visa — has salary/location/H-1B for the tooltip check), header caret located by its `title` (`"Hide job details"`/`"Show job details"`, not a generic `[role="button"][aria-expanded]` selector — that also matches the toolbar filter-dropdown triggers and gave false readings on a first pass). Open: header row height **143px** (doc's own figure is 142px inclusive of the 1px `HeaderRow` rule; the 1px gap is measurement-boundary rounding, not a discrepancy), `aria-expanded="true"`. Clicked caret → **48px** exactly, `aria-expanded="false"`, only the title line remains (`<h2>` `textContent` = title only), and its `title` attribute (tooltip) = `"Visa Direct Product & Client Solutions Manager — Visa · $146K - $234K · H-1B Likely · Direct · 2h ago"` — company · salary · location · H-1B · source · age, exactly as `collapsedMeta` derives it. `localStorage['jobnavigator_v2_feed_meta']` = `'0'`. Reloaded the page → still collapsed (**48px**, `aria-expanded="false"`) — persists. Clicked again → back to **143px**, `aria-expanded="true"`. Keyboard: focused the caret, **Enter** → collapsed (48px, `aria-expanded="false"`); **Space** → expanded again (143px, `aria-expanded="true"`) — `aria-expanded` tracked the state at every step. 0 console/page errors. |
| Regression | ✔ | `/v2/feed`, light+dark × 1440/1024 (4 combinations): **0 console errors, 0 page errors, no horizontal overflow** in all four (`document.documentElement.scrollWidth === window.innerWidth` and `document.body.scrollWidth === window.innerWidth` in every case). Keyboard with `PATCH /api/jobs/{id}` intercepted (fulfilled 200, never reaching the backend): selected row 0 (Meta) → **j** advanced to row 1 (Nomura, title changed) → **k** returned to row 0 (title matched the pre-`j` value exactly) → **s** fired a captured `PATCH {saved:false,status:"new"}` on the Meta job (unsave) → **x** fired a captured `PATCH {status:"skip"}` on the Nomura job — both captured client-side only; `GET /api/jobs/{id}` on both afterward confirmed the real DB rows unchanged (`saved:true,status:"saved"` on both), i.e. the intercept held and no real mutation occurred. 0 console/page errors during the keyboard pass. |

## Summary

**8 of 8 ✔ — every item in `fixes-feed-2.md` (F1–F6, Metadata collapse) plus the regression pass
verified working live on the rebuilt bundle.** No regressions found.

## UNEXPECTED

- None. The only anomalies encountered during scripting were harness-selector mistakes on my end
  (a `div.v2-act` locator matching the row-menu trigger instead of the modal's résumé-choice card in
  an early F6 draft; a `[role="button"][aria-expanded]` locator matching a filter-dropdown trigger
  instead of the header caret in an early metadata-collapse draft; measuring the busy ring's
  `getBoundingClientRect()` instead of its `viewBox`/attribute geometry, which is skewed by the
  `.v2-spin` rotation transform) — all corrected before the numbers above were taken, none reflect
  application behavior.
- The two X-Frame-Options console errors seen while optimistically loading blocked-host iframes
  (Camunda in F1, implicitly others in F4) are the same pre-existing browser-level artifact prior
  rounds logged and explicitly ruled a non-defect (F4's whole point is that the app *tries* the live
  frame first) — noted, not counted as a finding.

## Data note

F2's real run-all added **4 new jobs** (summary `+4 new`) now sitting at `status:"new"`, unscored —
expected, normal product behavior for an authorized real scrape, not reverted (nothing in the task
asked for scrape results to be rolled back, only status PATCHes made *by this pass's own scripts*,
all of which were confirmed restored — see the "Status PATCHes" note above).
