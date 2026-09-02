# Stage 3 — Companies

Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (HEAD 438d27a), themes light+dark, viewport 1440×900 (+ one narrow 1024×700 pass)
Design: `v2-testing/design/Companies Ops.dc.html`   Inventory: `v2-testing/inventory/v2-companies.md`
v1 reference: `frontend/src/components/CompanyManager.jsx`   Backend: `backend/api/routes_companies.py`
Scripts: `comp_1.py` (geometry/tokens/contrast), `comp_2.py` (hovers/sort/filters/menus), `comp_3.py`+`comp_3b.py` (drawer), `comp_4.py` (health-cell variants via real `scrape_log` rows), `comp_5.py`+`comp_5b.py` (failure paths, save round-trip, staleness), `comp_6.py` (Add modal, detectAts), `comp_7.py` (test scrape, bulk, z-order), `comp_8.py` (narrow, dark, stale drawer, feed link), `comp_9.py` (counts, delete)

**Line numbers** are those of `Companies.jsx` as read at the start of this run. The two fixes applied at the end (COMP-14, COMP-15) add 5 lines, so refs below line 262 are unaffected and refs after it now sit 3–5 lines lower.

**Bundle caveat.** The served bundle still contains `eightfold.ai` and not `search-jobs/results`, i.e. it predates both JSX fixes carried into this run. Every JSX-level measurement below is against the pre-fix bundle; the `detectAts` and TestModal-summary fixes were verified by evaluating the post-fix source directly (see "Fixed in source").

---

## Findings

### COMP-01 · P1 · Drawer `Save changes` closes before the PATCH resolves — a failed save loses the edit silently
**Where** `Companies.jsx:454` (`onSave(company.id, payload); setState(null)`) + `:201` (`patchCompany` → `catch → console.error`), route `/v2/companies`
**Repro** Open a company drawer, edit `Display name`, intercept `PATCH /api/companies/*` with a 1.6 s delay + `500 {"detail":"boom"}`, click `Save changes`.
**Expected + why** v1 `CompanyManager.jsx` keeps the edit modal open until the request settles. The v2 toast taxonomy has an `error` kind with `TTL.error = null` precisely so a failure cannot evaporate (`Toast.jsx:19,21`) — but `Toast.jsx` is never imported here.
**Actual** measured: drawer already gone at **t+0.30 s** while the PATCH was still in flight; at t+2.5 s (after the 500) there is **no toast, no banner, no text matching /boom|failed|error/ anywhere in the document** — only two console errors. Server value unchanged (`name` still `ZZTEST Alpha`), and the row still shows the old name. The user has no way to know the edit was discarded.
**Proposed fix** `await onSave(...)` and only `setState(null)` on success; show a pending state on the button (`Saving…`) and an `error` toast on failure. Requires `patchCompany` to rethrow (or return a status) instead of swallowing.
**Status** fixed + verified after rebuild (drawer stays open on PATCH 500, inline "Save failed — nothing was changed", error toast; Drawer `save` awaits `patchCompany`, which now returns true/false)

### COMP-02 · P2 · Drawer's `company` object is never refreshed, so the banner / tuning note / subtitle go stale while the drawer is open
**Where** `Companies.jsx:560` (footer toggle calls `onSave` → `fetchCompanies()`), `:415` (`drawer.company` captured once at `openDrawer` `:241`)
**Repro** Open the drawer for a company. Insert a `scrape_log` row with an `error` for it. Click the footer `Make inactive` (this PATCHes and refetches `/companies` immediately, independent of Save).
**Expected + why** The refetch updates `companies`; the drawer renders from `state.company`, which `fetchCompanies` never touches. The design's drawer reads live company state (`d = COMPANIES[S.open]`, `.dc.html:559`).
**Actual** measured: after the refetch the **drawer banner is still absent** and the tuning note still reads `customised`, while the row behind gains `▲` and health `error · …`. Closing and reopening the drawer shows the banner. Same staleness applies to `application_count`, `last_error`, `last_run_at` and the subtitle.
**Proposed fix** key the drawer off `companies.find(c => c.id === drawer.id)` rather than a snapshot; keep only `draft` in drawer state.
**Status** fixed in source (rebuild pending) — `Companies.jsx:490-496`: the drawer is now rendered from `companies.find(c => c.id === drawer.company.id)` (falling back to the snapshot if the row disappears), and `downReason` is read off the same live row. `draft` stays the only state the drawer owns.

### COMP-03 · P2 · The list has no loading and no error branch — a failed `GET /companies` renders as "you have no companies matching your search"
**Where** `Companies.jsx:125` (`useState([])`), `:142` (`catch → console.error`), `:193` (`countLine`), `:406-412` (zero-results branch)
**Repro** Intercept `GET /api/companies` → 500, load `/v2/companies`.
**Expected + why** Inventory §4 flags both branches as missing; HANDOVER ranks error paths #2. The design has only an empty branch, but it is reached from a *successful* empty response, not a failure.
**Actual** measured: header `0 tracked · 0 active · 0 need attention`; all four tier chips read `0`; both bulk buttons vanish; the body shows **`No companies match` / `Nothing matches "ZZTEST Alpha" in names, aliases, URLs or ATS.` / `Clear filters`** — the stale query is read back from `localStorage`, so a server outage is presented as a filter miss and `Clear filters` "fixes" nothing. No toast, no retry. Same rendering for the whole window between mount and the first response (no skeleton).
**Actual (401)** handled correctly one level up: the shell's `LoginModal` appears (`/api key/i` matched), so 401 is not a Companies defect.
**Proposed fix** track `loading` / `loadErr`; render a skeleton while loading and a "Couldn't load companies — Retry" panel on failure, distinct from the filter-miss copy.
**Status** fixed in source (rebuild pending) — `Companies.jsx:144-145,160-165,466-486`: `loading` / `loadErr` state (the pattern already in `Searches.jsx:321,577-587`), a spinner row while the first response is outstanding, a “Couldn’t load companies · <detail> · Try again” panel on failure, and the filter-miss copy suppressed while that error shows.

### COMP-04 · P2 · `Toast.jsx` is never imported — nine of eleven failure paths and every success path are silent
**Where** `Companies.jsx` (no `Toast` import); silent sites: `:142` list load, `:201` status pill + drawer save, `:204` bulk (per-item `.catch(() => {})`), `:209` Run, `:220` Delete, `:146-149` résumés/persona/health/monitor
**Repro** For each: intercept the call with a 500 and act; then repeat the success path.
**Expected + why** The toast system exists and is used by other v2 screens; inventory §3 legend says every "OK toast" on this screen is `none`.
**Actual** measured `0` fixed-position elements with `z-index ≥ 70` after: a failed drawer Save, a failed status-pill PATCH (pill stayed `Active`), a successful Save, a successful Add, a successful Delete, and bulk activate/inactivate. Only the Test modal (own error variant) and the Add modal (native `window.alert`) surface anything.
**Proposed fix** mount `useToasts()` and push `success` on Save/Add/Delete/bulk and `error` (non-dismissing) on every catch.
**Status** fixed by toast wiring (rebuild pending) — verified in source: `Companies.jsx:2` imports `useToasts`/`ToastStack`, `:146` mounts it, `:500` renders `<ToastStack>`; error toasts on list load (`:162`), `patchCompany` (`:241` — covers the status pill and the drawer Save), `bulkSet` (`:247-248`, error plus success), `runScrape` (`:259`), `deleteCompany` (`:272`) and the Add modal (`pushToast` prop, `:498`). Only `runTest` is still silent, and it has its own in-modal error variant by design.

### COMP-05 · P2 · `Run` uses a fixed 2600 ms timer instead of `/monitor/active`; the UI reports "done" while the scrape is still going
**Where** `Companies.jsx:207-211`
**Repro** Click `↻ Run` on a company; poll `GET /api/monitor/active`.
**Expected + why** The screen already knows about `/monitor/active` (`:149`); the Résumés/Cover-Letter flows poll it for exactly this reason (CLAUDE.md, "Background score-resume").
**Actual** measured: at t+0.4 s health = `scraping now…`, label `Running`, spinner present. At **t+3.0 s** the row reverts to `healthy · scraped never` and `Run` — while `/monitor/active` still reported the same `company_scrape` run with `elapsed_seconds: 3.0`, and it was **still running at 30 s** (the real Greenhouse scrape took ≈40 s and wrote 486 jobs). A 409 duplicate (`main.py:672-677`) is also swallowed to `console.error` while the spinner runs its full 2.6 s.
**Proposed fix** poll `/monitor/active` (2 s) while any company has a live run; clear per company when its `scope_key` disappears, then refetch. Surface the 409 as an info toast.
**Status** fixed in source (rebuild pending) — `Companies.jsx:173-186,251-262`: the 2600 ms timer is gone; a 3 s `/monitor/active` poll runs while any company is marked running and calls `fetchCompanies()` (which now also refetches health) the moment a `scope_key` disappears. The poll map is filtered to `job_type === 'company_scrape'`, so scoring and search runs no longer light up a company row. A 409 keeps the spinner and pushes a `progress` toast (“That company is already being scraped”), matching `Searches.jsx:399-401`.

### COMP-06 · P2 · `/health/entities` and `/monitor/active` are fetched once on mount and never refreshed
**Where** `Companies.jsx:148-149`; no interval anywhere (`:27` of the inventory)
**Repro** Load the screen while a `company_scrape` is running; leave the tab open.
**Expected + why** `downMap` drives the header count, the `▲` glyph, the health text, the drawer banner and the `Needs attention` sort; `scraping` drives the health/`Running` state.
**Actual** measured: a company whose scrape had finished still rendered `scraping now…` on a later page load because `/monitor/active` was read at mount and there is no clearing path other than the 2.6 s timer (which only fires for a run *started in this session*). Conversely, running a scrape that fixes a "down" company leaves the `▲` and the header count wrong until a manual reload; `fetchCompanies()` after Run/Save/bulk/Delete refreshes `/companies` only.
**Proposed fix** refetch `/health/entities` alongside `/companies` in `fetchCompanies`, and poll `/monitor/active` while anything is running.
**Status** fixed in source (rebuild pending) — `Companies.jsx:154-165`: `fetchHealth()` now runs at the end of every `fetchCompanies()`, so Run / Save / the status pill / bulk / Delete / the poll all refresh `downMap` together with the list. `/monitor/active` is polled while anything runs (COMP-05), and its mount read is filtered to `company_scrape`, which also clears the stale “scraping now…” seen on a later page load.

### COMP-07 · P2 · `Needs attention` sort and the header count ignore `last_error`, which the row `▲`, health text and drawer banner all honour
**Where** sort `Companies.jsx:181`, count `:192`; row `▲` `:345`, health `:233`, drawer banner `:468`
**Repro** Insert one `scrape_log` row with an `error` for an active company (one bad run — not enough for `/health/entities`, which needs 3).
**Expected + why** `/health/entities` deliberately requires three bad runs (`main.py:1156-1163`); `last_error` is the *most recent* run's error (`routes_companies.py:157-183`) and was added so Health surfaces a failure "right away". The two readers must agree.
**Actual** measured, one error run: row shows `▲` in `var(--bad)` + `error · ZZTEST boom — HTTP 503 …`, drawer shows the red banner and `needs attention` — but the header still read **`1 need attention`** (unchanged) and the row sorted to **index 61** (plain alphabetical), not to the top. After a third bad run the count went to 2 and the row jumped to index 1. So a freshly broken company is neither counted nor surfaced by the sort that exists to surface it.
**Proposed fix** `const down = (c) => !!downMap[c.id] || !!c.last_error` for both the comparator (`:179`) and `downCount` (`:192`). (Note this then diverges from the rail badge, which reads `/health/entities` only — decide which number is canonical.)
**Status** fixed in source (rebuild pending) — `Companies.jsx:215-217,230`: promoted. `down = (c) => !!downMap[c.id] || !!c.last_error` now backs both the `health` comparator and `downCount`, so the header count, the sort, the row `▲`, the health text and the drawer banner all read one predicate. **It still diverges from the rail badge**, which reads `/health/entities` only — that badge is cross-screen and stays the coordinator’s call.

### COMP-08 · P2 · `Apps` is name-only while `Open`, `+7d` and `Ø Fit` are alias-summed; and the column means *all* applications
**Where** `routes_companies.py:177` (`app_counts.get(c.name.lower()…)`) vs `:146-154` (`_aggregates` sums over `name + aliases`); header tooltip `Companies.jsx:329` "Open applications"; drawer subtitle `:432` "open application(s)"
**Repro** Compare the row against the DB for a company with applications recorded under an alias.
**Actual** measured on real data: `Amazon` has aliases including `Prime Video & Amazon MGM Studios`; the UNION of `Application.job_id` and `Job.status='applied'` gives `amazon → 15` and `primevideo&amazonmgmstudios → 1`. The row shows **15**; alias-summed (consistent with the neighbouring columns) it is **16**. Cross-checked the other columns on a scratch company: `Open 5 +8`, `Apps 1` matched the DB exactly (`new 4 + saved 1 = 5`; 8 discovered in 7 d; 1 applied).
Separately, `application_count` counts every application in any state, so both "Open applications" (header) and "{n} open application(s)" (drawer) are wrong words for the number.
**Proposed fix** sum `app_counts` over `[name] + aliases` in `_aggregates`; change both labels to "Applications".
**Status** fixed in source, restart pending (backend) — `routes_companies.py:149-161,178,182`: `_aggregates` now also returns `apps = sum(app_counts.get(k, 0) for k in keys)` and `application_count` is taken from it, so Apps is alias-summed exactly like Open / +7d / Ø Fit (`Amazon` moves 15 → 16). **Needs `docker compose restart backend`.** The wording half is JSX (rebuild pending): header tooltip `Companies.jsx:389` “Open applications” → “Applications recorded for this company”, drawer subtitle `:515` “{n} open application(s)” → “{n} application(s)”.

### COMP-09 · P2 · `⋯ → View jobs in feed` is a raw `<a href>` that full-page-reloads into an *unfiltered* feed
**Where** `Companies.jsx:398`; `JobFeed.jsx` reads only `?job=` and `?search=`
**Repro** Open the row menu, click `View jobs in feed`.
**Actual** measured: `href = /v2/feed?company=ZZTEST%20Alpha`; the click produced **3 document navigations** (full SPA reload, losing all screen state) and landed on `/v2/feed?company=ZZTEST+Alpha&job=817d67df-…` — the Feed rewrote the query, **ignored `company`**, and auto-opened an unrelated job. The feed header read `19438 open roles`, i.e. no filter applied.
**Proposed fix** either make `JobFeed` read `?company=` (preferred — the tooltip on `Open · 7d` already promises "in the Job Feed") or drop the menu item. Use React Router `Link` either way.
**Status** fixed in source (rebuild pending) — `JobFeed.jsx:113-114` now seeds its company filter from `?company=` (fixed in the Feed pass), so the link only had to stop reloading: `Companies.jsx:458` keeps the `href` (middle-click, ⌘/ctrl-click and open-in-new-tab still work — modified clicks fall through untouched) but a plain left click `preventDefault()`s and calls `navigate('/v2/feed?company=…')`, the same shape as `Searches.jsx:544`.

### COMP-10 · P2 · At 1024 px the toolbar overflows and the `Sort` control is pushed off-screen with no way to reach it
**Where** `Companies.jsx:270` (toolbar, no wrap / no overflow), `:296` (`marginLeft: auto` sort group)
**Repro** 1024×700 viewport, `/v2/companies`.
**Actual** measured: toolbar `scrollWidth 1030` vs `width 818`. Right edges relative to the container's right edge: `Make 66 active` **−65**, `Make 64 inactive` **+67**, `Sort Needs attention ▾` **+212** — i.e. the inactivate button is half clipped and the whole sort control is outside the box. `document.scrollWidth > innerWidth` is `false` (nothing scrolls), so sorting is unreachable below ≈1240 px. The row area itself does scroll (`scrollWidth 1100` in an `overflow:auto` container) so the columns survive; the sticky header scrolls with them.
**Proposed fix** `flexWrap: 'wrap'` on the toolbar (or move the tier chips to a second line under ~1200 px).
**Status** fixed in source (rebuild pending) — `Companies.jsx:328`: `flexWrap: 'wrap'` on the toolbar (the fix the Feed took). Below ≈1240 px the bulk buttons and the `marginLeft: auto` sort group drop to a second row instead of overflowing; nothing is clipped and Sort is reachable again.

### COMP-11 · P2 · The alias badge under-reports by one, and a company with exactly one alias shows no badge at all
**Where** `Companies.jsx:347` (`aliases.length > 1` → `+{aliases.length - 1}`)
**Repro** Compare a company with 1 alias, 2 aliases and 6 aliases.
**Expected + why** The design assumed `aliases[0]` is the company's own name (`.dc.html:640`, `aliasHint` uses `c.aliases.slice(1)`, and its fixtures store `aliases: ["Stripe", "Stripe Inc."]`). The real DB stores aliases as **additional** names only: `Microsoft → ["Microsoft AI"]`, `Amazon → ["Amazon Music","AWS", …]` (6). `find_company_by_name` checks name *then* aliases, confirming they are extra.
**Actual** measured: Microsoft (1 alias) renders **no badge**; a scratch company with 2 aliases renders **`+1`**; Amazon (6) renders `+5`. The tooltip, meanwhile, lists **all** aliases (`aliases.join(', ')`), so badge and tooltip disagree.
**Proposed fix** `aliases.length > 0` → `+{aliases.length}`, tooltip unchanged.
**Status** fixed in source? no — logged; one-line change but it silently shifts every row, so: needs decision.

### COMP-12 · P2 · `Pages to read` and `Scrape interval` accept any integer — the `min`/`max` are HTML-only
**Where** `Companies.jsx:545` (`min={1} max={20}`), save `:451` (`parseInt(draft.max_pages) || 5`), `:449` (`parseInt || null`)
**Repro** Type `999` into both, Save, read back.
**Actual** measured round-trip: `max_pages: 999`, `scrape_interval_minutes: 999` persisted. `0` becomes `5` and `null` respectively (the `|| ` fallbacks); negatives pass through. Typing is not the only path — a paste bypasses the spinner constraints entirely, and `<input type=number>` never blocks out-of-range typing anyway.
**Proposed fix** clamp on save: `Math.min(20, Math.max(1, parseInt(x) || 5))`.
**Status** fixed in source (rebuild pending) — `Companies.jsx:536-540`: `max_pages: Math.min(20, Math.max(1, parseInt(x) || 5))`, the bounds the input’s own `min`/`max` declare, and `scrape_interval_minutes` now takes a positive integer or `null` (= use the global interval), which also closes the negative-value hole. An existing out-of-range value is rewritten to the bound the next time that company is saved — deliberate, and the only behaviour consistent with the control.

### COMP-13 · P2 · Résumés cell claims "Selected" while the drawer says "Nothing selected" when the résumé list is unavailable or the ids dangle
**Where** `Companies.jsx:224-230` (`resumeNames`), `:359` (cell), `:436` (`resumeHelp`)
**Repro** Intercept `GET /api/resumes?is_base=true` → 500, load the screen, open a company that has `selected_resume_ids`.
**Actual** measured: row cell reads **`Selected`** with `title="Selected"`; the drawer's help line reads **"Nothing selected, so new jobs use your default résumé from Settings."**; the résumé chips disappear entirely (no "No résumés yet" copy, inventory §4). The two statements contradict each other, and both are wrong — ids *are* selected. The same happens for real dangling ids (deleted résumés), where `resumeNames` silently drops the unresolvable ones and only falls back to `Selected` when *none* resolve.
**Proposed fix** distinguish "not loaded" from "not selected": show `{n} selected` (and a chip placeholder) when `resumes` is empty but ids exist.
**Status** fixed in source (rebuild pending) — `Companies.jsx:276-285`: `resumeNames` returns `{ids.length} selected` when no id resolves, so the cell states the count instead of the bare “Selected” and stops contradicting the drawer’s “Nothing selected”, which is now reached only when the id list is genuinely empty. The drawer’s missing chip placeholder is left alone — that is the separate “no résumés” gap in inventory §4.

### COMP-14 · P3 · Every row lands on a half pixel (fractional `getBoundingClientRect().top`)
**Where** `Companies.jsx:262` (header subtitle)
**Repro** `assert_int_tops(pg, 'div.v2-crow')`.
**Expected + why** HANDOVER, "Half-pixel rows drop their 1px borders" — the tree inherits Tailwind preflight's `line-height: 1.5`.
**Actual** measured before the fix: **126/126 rows fractional** (`164.5, 210.5, 256.5, …`), in both themes and at 1024 px. Traced to the header: `h1` 30 px (`lineHeight: 1`), subtitle 13 px × 1.5 = **19.5 px**, so `header.height = 22 + 30 + 3 + 19.5 + 16 = 90.5` and the whole list inherits the .5. Rows themselves are an exact 46 px.
**Proposed fix** explicit integer `lineHeight: '20px'` on the subtitle → header 91, column header 135, first row 165.
**Status** fixed in source (rebuild pending)

### COMP-15 · P3 · The sort menu's hover never fires — an inline `background: 'transparent'` beats `.v2-menuitem:hover`
**Where** `Companies.jsx:308`; rule `theme.css:149` (`.v2-menuitem:hover { background:var(--surface-2) }`, no `!important`)
**Repro** `hover_delta` on a sort option vs on a row-menu item.
**Expected + why** design `.dc.html:74` puts `style-hover="background:#f3f0e8"` on every sort option; HANDOVER, "Inline styles beat class `:hover`".
**Actual** measured: sort option → `changed: []`, background stays `rgba(0,0,0,0)`. The row `⋯` menu items (no inline background) → `changed: ['backgroundColor']`, `rgb(246,244,238)`. So the identical class works one place and is dead in the other.
**Proposed fix** drop the `: 'transparent'` arm so the class can apply (selected items keep their `--accent-soft` and stay hover-inert).
**Status** fixed in source (rebuild pending)

### COMP-16 · P3 · `.v2-hover-accent`'s colour half has never fired on this screen (drawer ✕, test-modal ✕)
**Where** `Companies.jsx:464`, `:703` (inline `color: 'var(--muted)'`); rule `theme.css:129` (`.v2-hover-accent:hover { background:var(--surface-2); color:var(--text); }`, no `!important`)
**Repro** `hover_delta` on both ✕ buttons.
**Expected + why** design `.dc.html:159` and `:262`: `style-hover="background:#f3f0e8;color:#1b1a16"` — *both* properties.
**Actual** measured on both: `changed: ['backgroundColor']` only; colour stays `rgb(109,104,98)` (`--muted`) instead of going to `--text`. Identical to the `.v2-hover-accent-text` bug HANDOVER records as "had never fired anywhere until it was caught by measurement".
**Proposed fix** `theme.css:129` → `color: var(--text) !important;`. **Not applied**: `theme.css` is shared by all nine screens and other agents are measuring hovers against it in this wave — this one belongs to the coordinator.
**Status** fixed + verified: `.v2-hover-accent` colour half hardened tree-wide; the drawer's active toggle and both Close buttons (drawer error panel, test modal) now carry the pill hover (`v2-bdc`) — measured border+colour change

### COMP-17 · P3 · Hover taxonomy differs from the design on six controls
**Where** `Companies.jsx:289` (`Make n active`), `:381` (Run), `:388` (Test), `:392` (`⋯`), `:561` (drawer `Test scrape`) — all `.v2-act`; `:87` (URL ✕) `.v2-hover-bad`; `:92` (`+ Add another career page`) `.v2-dashadd`; `:104` (Seg) and `:280` (tier chips) `.v2-bd`
**Actual** measured (light):

| control | design `style-hover` | measured |
|---|---|---|
| Run / Test / drawer Test scrape | `border-color:#3f6b52;color:#3f6b52` | border→accent **+ background `#f4f8f5`**, colour unchanged |
| `⋯` | `border-color:#3f6b52` | border→accent **+ background** |
| `Make n active` | `border-color:#3f6b52` | border→accent **+ background** |
| `Make n inactive` | `border-color:#9a5b28` | border→warn only ✔ |
| URL row ✕ | `color:#9c3b30` | **background `--bad-soft`**, colour unchanged |
| `+ Add another career page` | `border-color:#3f6b52;color:#3f6b52` | border + colour ✔ **+ background** |
| tier filter chips | *(none in the design)* | border→accent (extra) |
| depth / tier Seg options | *(none in the design)* | border→accent (extra) |
| status pill, row, menu items, delete item, sort trigger, `+ Add company`, `Save changes`, `Cancel`, tuning header, `Show screenshots`, `Close` | as designed | ✔ |

**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision: keep code (unified accent hovers across v2) or match the design?

### COMP-18 · P3 · A never-scraped active company reads `healthy · scraped never` with a **green** dot
**Where** `Companies.jsx:235` + `ago(null) → 'never'` (`:7`)
**Repro** Create a company, don't scrape it, load the screen.
**Actual** measured on a fresh company: dot `rgb(63,107,82)` (`--good`), text `healthy · scraped never`, title identical. Nothing distinguishes "confirmed healthy" from "never ran". 24 real companies are in this state (`last_scraped_at IS NULL`).
**Proposed fix** a fifth branch before the `active` one: `not scraped yet` with the `--edge` (or `--muted`) dot.
**Status** fixed + verified after rebuild: active company with no `last_scraped_at` reads "not scraped yet" with an `--edge` dot

### COMP-19 · P3 · `last_run_warning` is returned but never rendered — one zero-result run looks perfectly healthy
**Where** serialiser `routes_companies.py:626`; no reader in `Companies.jsx`
**Repro** Insert one `scrape_log` row with `is_warning=true, error=null`.
**Actual** measured: row unchanged — dot `--good`, text `healthy · …`, no `▲`, header count unchanged, drawer banner absent. The company only becomes visible after three consecutive bad runs promote it into `/health/entities`. `Oracle` is in exactly this state in the real data (`last_run_warning: true`).
**Proposed fix** a `--warn` dot with `last run found nothing` between the `last_error` and `downMap` branches.
**Status** fixed + verified after rebuild: `last_run_warning` renders "last run found nothing · {ago}" with a `--warn` dot, between the error and the 3-run-down branches

### COMP-20 · P3 · Drawer is 720 px; the design draws 520 px
**Where** `Companies.jsx:458` (`width: 720`); design `.dc.html:150` (`width:520px`)
**Actual** measured `w: 720, x: 720` at 1440 (50 % of the viewport, vs 36 % designed) and `w: 720, x: 304` at 1024 (**70 %** of the viewport). Every other drawer measurement matches the design exactly: header padding `16px 22px 13px`, body `15px 22px 20px` gap 15, footer `12px 22px`, title 20 px Newsreader, field boxes 32 px / radius 7, banner `11px 13px` radius 9 with `--bad`/`--bad-soft`.
**Status** decided 2026-09-02: keep 720 px

### COMP-21 · P3 · Column widths diverge from the design; `Company` is the column that pays
**Where** header `Companies.jsx:323-332`, rows `:344-380`
**Actual** measured vs design:

| column | design | code | measured @1440 | measured @1024 |
|---|---|---|---|---|
| Company | `0 0 206px` | `flex 1, min 118` | **149** | **118** |
| Tier | `0 0 62px` | same | 62 | 62 |
| Health | `flex 1, min 190` | `flex 1.9, min 210` | **283** | 210 |
| Résumés | `0 0 104px` | `0 0 132px` | 132 | 132 |
| ATS | `0 0 84px` | `0 0 108px` | 108 | 108 |
| Open · 7d / Apps / Ø Fit / Status | 74 / 46 / 48 / 88 | same | same | same |
| actions | `0 0 168px` | `0 0 190px` | 190 | 190 |

A 200-character company name ellipsises correctly (cell 142 px, `scrollWidth` 1270, row does not overflow), but at 1024 px `Company` is down to 118 px while `Health` still holds 210.
**Status** decided 2026-09-02: keep

### COMP-22 · P3 · The design's "{n} of {N} shown" counter is not built
**Where** design `.dc.html:75` + `:588-589` (`shownLine` / `shownDisplay`, shown only while filtered); no equivalent in `Companies.jsx`
**Actual** measured: no element matching `/^\d+ of \d+ shown$/` in any state. With a filter applied the only feedback is the row count itself; the header keeps showing the unfiltered `126 tracked`.
**Status** decided 2026-09-02: keep (no counter)

### COMP-23 · P3 · The test modal computes per-state row tints and never applies them
**Where** `Companies.jsx:691-693` (`jobState` returns `bg`), `:748` (row `<div>` has no `background`)
**Expected + why** design `.dc.html:325` `background:{{ j.bg }}` with `#fff` / `#fdf8f7` (out) / `#fdfaf5` (drop).
**Actual** measured on a real 577-row result: every row `backgroundColor: rgba(0,0,0,0)`. `bg` is dead code in all three branches.
**Proposed fix** either apply `st.bg` (mapped to `--surface` / `--bad-faint` / `--recessed`) or delete the field.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-24 · P3 · Globally-excluded rows are indistinguishable from per-company exclusions, and the two "after filter" numbers are never shown
**Where** `Companies.jsx:690-693` (only `[Validation]` and `kept` are special-cased); backend returns `passes_company_filter`, `global_excluded_by`, `after_company_filter`, `global_exclude_keyword_count` (`routes_companies.py:559-584`)
**Repro** Test-scrape a company whose titles hit the global `title_exclude_global` list.
**Actual** measured on the real Anthropic Greenhouse board (577 postings): `after_company_filter: 22`, `after_filter: 12`, `global_exclude_keyword_count: 84` — **10 rows were dropped by the global list**, each rendered as a plain red `Out` whose reason string happens to start with `[Global] Excluded by: …`. Nothing tells the user those 10 were not their company rule, and the "22 passed your filters, 12 will actually save" distinction is discarded.
**Proposed fix** a third tag (`Global`) or a `[Global]` prefix strip + warn tint, and add "22 pass this company's filters · 10 removed by the global list" to the summary.
**Status** fixed + verified after rebuild: rows dropped by the global list get a `Global` tag (warn tint) with the `[Global]` prefix stripped; the summary adds "N pass this company's filters · M removed by the global list" when they differ

### COMP-25 · P3 · The column-header rule is in the wrong place and the wrong weight
**Where** `Companies.jsx:322` (`borderTop: 1px var(--line)` + `borderBottom: 1px var(--line)`); design: toolbar carries `border-bottom:1px solid #e2ddd0` (`.dc.html:60`) and the header row carries **only** `border-bottom:1px solid #c9c3b4` = `--line-strong` (`.dc.html:83`)
**Actual** measured: header `borderTop 1px rgb(226,221,208)`, `borderBottom 1px rgb(226,221,208)`; toolbar `border-bottom-width: 0px`. So the header reads as a boxed strip with two equal hairlines instead of a toolbar rule plus a stronger column rule.
**Status** fixed + verified after rebuild: toolbar carries the 1 px `--line` hairline, the column header has no top border and a 1 px `--line-strong` bottom rule

### COMP-26 · P3 · No in-progress state for the test scrape, and the result table renders every row
**Where** `Companies.jsx:388` (row spinner), `:561` (footer spinner); no overlay
**Actual** measured: while the synchronous `POST /companies/{id}/test-scrape` runs, the only feedback is a 9 px spinner in the `Test` pill — no overlay, no dimming, and the rest of the screen stays fully interactive (a second click re-enters `runTest`). This board answered in 1.6 s via the Greenhouse API; a Playwright board with `max_pages` up to 20 takes tens of seconds. The result modal then rendered **577 rows** unvirtualised in one pass (row tops are all integers, so no half-pixel problem there).
**Status** needs decision

### COMP-27 · P3 · Add-modal `Save` stays live while `saving` — a double click double-POSTs
**Where** `Companies.jsx:591-604` (no re-entry guard), `:660` (only `cursor`/`opacity` change)
**Actual** verified by code + the 409 path: the second POST returns `409 Company already exists`, which surfaces as a native `alert` and leaves the modal open. Confirmed live that a 409 produces exactly `alert('Company already exists')` and resets the label to `Save`.
**Proposed fix** `if (saving) return` at the top of `save`.
**Status** fixed in source: `if (saving) return` guard at the top of the Add modal's save

### COMP-28 · P3 · Native `confirm`/`alert` on a screen with no other native dialogs
**Where** `Companies.jsx:219` (delete confirm), `:592` (name required), `:603` (server error)
**Actual** measured messages: `Delete ZZTEST Gamma? Jobs already found are kept.` (dismiss → no DELETE, row kept; accept → DELETE, row gone, **no toast**), `Company name is required`, `Company already exists`. The design has no dialog for any of these; the rest of v2 uses modals and toasts.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-29 · P3 · No first-run empty state, and the tier-empty copy doesn't name the tiers
**Where** `Companies.jsx:406-412`
**Expected + why** design `.dc.html:594-595`: `emptyHint` for a tier filter is `"No companies in " + tiers.map(…).join(", ") + "."` — it names them.
**Actual** code always prints the generic `No companies in the selected tiers.`, and a genuinely empty database falls into the same "No companies match" + `Clear filters` branch, which does nothing useful. (Not directly reproducible on this data set: all four tiers have rows, so the tier-only empty branch could not be triggered — see "Couldn't test".)
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-30 · P4 · `Ø Fit` uses U+00D8 (Latin O with stroke); the design uses U+2300 `⌀` (diameter sign)
**Where** `Companies.jsx:330`; design `.dc.html:90`
**Actual** measured header text: `Ø Fit`.
**Status** decided 2026-09-02: keep Ø

### COMP-31 · P4 · Tier chip count is bare, and the tooltip doesn't say what the click will do
**Where** `Companies.jsx:281,283`; design `.dc.html:597-600`: `count: "(" + n + ")"` and `hint: (on ? "Remove from filter" : "Add to filter") + " · multi-select, remembered per browser"`
**Actual** measured labels `Tier 1 5`, `Tier 2 21`, `Tier 3 35`, `Untiered 65` (no parentheses); tooltip is the static `Add/remove from filter · multi-select, remembered per browser` on all four regardless of state. Counts themselves are correct: 5+21+35+65 = 126 = header `tracked` = rail badge `126`. ✔
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-32 · P4 · Drawer subtitle is not pluralised
**Where** `Companies.jsx:432`; design `.dc.html:715-716` pluralises both nouns
**Actual** measured: `Tier 1 · 1 career URL(s) · 1 open application(s)`.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-33 · P4 · Row tooltips drop the information the design put in them
**Where** `Companies.jsx:346` (name), `:362` (ATS), `:356` (health), `:359` (résumés)
**Actual** measured vs design:
- name `title` = the name itself; design: `"{name} · {n} H-1B filings on record, {rate}% approved — feeds the verdict on each job"` (`.dc.html:672-674`). The company's LCA data is fetched (`h1b_lca_count` is on every row) and shown only inside the drawer.
- ATS `title` = `urls.join('\n')`; design: `"{ATS} · {url}"` per line **plus** `"H-1B slug · {slug|auto-detected}"` (`.dc.html:657-658`).
- health `title` = the same string as the visible text; design: `c.down || (active ? "Last successful run …" : "Inactive — jobs already found are kept")` (`.dc.html:645`).
- résumés `title` = the names again; design: `"New jobs are scored against …"` / `"None selected — falls back to your default résumé from Settings"` (`.dc.html:652`).
- alias `title` lists **all** aliases; design lists `slice(1)`. (See COMP-11.)
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-34 · P4 · Add-modal control radii/heights differ from the design
**Where** `Companies.jsx:618,625,629,639` (inputs, `monoBox`/`inputBox` radius 7), `:635` (tier `Seg`, height 32)
**Actual** measured: inputs `h 33 / radius 7px` (design `33 / 8px`); tier segs `h 32 / radius 7` (design `33 / 8`); depth chips `h 26 / radius 99` ✔; résumé chips `h 27 / radius 99` ✔; card `520 × 555.75`, radius 12, border `--line`, scrim `rgba(20,19,15,0.42)` ✔.
Also: the card's height is fractional (555.75) — content-driven, harmless, but it puts the modal on a half pixel.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

### COMP-35 · P4 · Dead code
**Where** `Companies.jsx:1` (`useRef` imported, unused), `:16` (`norm`, unused — the row filter re-lowercases inline at `:176`), `:98` (`Seg` prop `big`, never passed), `:415`/`:423` (`onDelete` passed and destructured, no control uses it — the drawer has no delete), `:691-693` (`jobState().bg`, see COMP-23).
**Status** fixed in source: unused `norm` helper and the never-passed `Seg` `big` prop removed (`useRef` is used once, kept)

### COMP-36 · P4 · The sort menu has six options; the design has five
**Where** `Companies.jsx:56-63`; design `.dc.html:572-577`
**Actual** measured menu: `Needs attention ✓ / Company name / Priority tier / Open roles / Average fit / Last scrape`. `Priority tier` is additive. Menu geometry: `172 px` wide, `margin-top 5px`, `padding 8px`, `z-index 45`; design `190 px`, `margin-top 8px`, `padding 6px`, `z-index 40`.
All six comparators verified against the data: name `a16z, Addepar, Adobe`; tier `T1` block first; open `2, 1, 1`; fit `87, 85, 84`; run — never-scraped first; health — `downMap` first, then active, then name. ✔
**Status** decided 2026-09-02: keep six options

### COMP-37 · P4 · `Escape` discards an edited draft with no confirmation, and clicking another row silently replaces it
**Where** `Companies.jsx:158` (one Escape handler closes sort menu + row menu + drawer + add modal + test modal), `:341` → `:241`
**Actual** measured: typed `ZZTEST Alpha EDITED` into the drawer (title mirrors the draft live), pressed Escape → drawer gone, nothing saved, no prompt. Clicking a second row while a dirty draft is open replaces the draft outright (verified: title changed to the second company). Escape also closes the Add modal mid-entry.
**Status** awaiting the user's call (explained in chat 2026-09-02): needs decision

---

## Verified working (no finding)

- **Console is clean** — `0` console errors, `0` page errors, `0` HTTP ≥ 400, `0` failed requests on a normal light *and* dark load. The only console noise in the whole pass came from the deliberate 500 interceptions.
- **`.cc-*` chip contrast passes AA in both themes.** Measured `color` vs `background-color` and computed WCAG ratios: light **5.01–6.76** (min `cc-workday`/`cc-eightfold` 5.01), dark **5.92–8.50** (min `cc-generic` 5.92). All 13 ATS chips and all 4 tier chips ≥ 4.5:1.
- **Dark mode carries no light-only value.** Header `--bg #1e1c17`, header text `--muted #a8a49d`, row border `--line-soft #2c2a20`, row hover `--hover-soft #2e2b20` (the warm one), active pill `#8dbb9f` on `#243029`, drawer `--surface #28251b` with `--line` border, warn/bad/good all resolve to their dark tokens. `Ø Fit` colour scale verified across three buckets (`39` → warn, `76` → text-2, `–` → muted).
- **Health cell — all seven variants produced and measured** by inserting real `scrape_log` rows: `scraping now…` (accent dot/accent text), `error · …` (`--bad`), down/`No results in the last 3 scrapes` (`--warn`), `healthy · scraped {ago}` (`--good` dot, `--text-2`), `inactive · last run …` (`--edge` dot, `--muted`), never-scraped (COMP-18), last-run-warning (COMP-19). Precedence is exactly the code's order — `error` beats `down`, and `down` only ever applies to active companies (confirmed: making the company inactive removed it from `/health/entities` and the header count).
- **Save round-trip.** Every drawer field written and read back through the API: `name`, `aliases` (3), `scrape_urls`, `title_include_expr`, `title_exclude_keywords`, `auto_scoring_depth`, `selected_resume_ids`, `tier`, `scrape_interval_minutes`, `wait_for_selector`, `max_pages`, `h1b_slug` — all persisted; `active` correctly **not** sent by Save (`true` preserved across a save that toggled nothing).
- **Add modal.** Live ATS chip, three `atsNote` variants (with the unknown-ATS one in `--warn`), empty-URL `—` chip, both `scoreNote` variants, tier/interval/aliases/résumé/depth controls, validation `alert`, 409 `alert` (modal stays open, label resets), success → row created with aliases + depth persisted, scrim click and Escape both close.
- **Test modal.** Real dry run against `boards.greenhouse.io/anthropic`: 840 × 660 card, `URLs scraped · 1` + the backend's descriptive URL line, `Include`/`Exclude` chips, sticky `# / Title / Status / Reason / Link` header, 577 rows with `Out` tags, strike-through titles and `--muted` text on non-kept rows, footer summary, `↗` links, close by ✕ / footer `Close` / scrim / Escape. Zero fractional row tops. Error variant (`No scrape URLs configured`) renders the 520 px card with the message in `--bad`.
- **Test-modal summary arithmetic** (the pre-existing fix): backend gives `total_found = len(all_jobs)` *excluding* rejects and `rows = total_found + total_rejected`. On this board `total_rejected = 0`, so both the old and new formulas print `12 kept · 565 keyword-filtered · 0 validation-rejected · 577 extracted` — the fix is correct but not *observable* without a Playwright board that produces `[Validation]` rejects (see "Couldn't test").
- **Bulk activate / inactivate.** Buttons appear/hide on their own counts (`Make 1 active` + `Make 3 inactive` over a 4-row filter), the tooltip reports the filter size, every target is PATCHed, the list refetches, and the button set flips to a single `Make 4 active`.
- **Filters, search and persistence.** Tier chips multi-select (`tier 1` → 5 rows; `+ Untiered` → 70 = 5 + 65), search matches name, alias (`Microsoft AI` → Microsoft) and ATS (`greenhouse` → 23), `Clear filters` resets both, and `company_query` / `company_filter_tiers` / `company_sort` / `company_tuning_open` all round-trip through `localStorage`.
- **Delete.** Native confirm names the company and the "jobs are kept" consequence; dismiss makes no request and keeps the row; accept DELETEs, closes the menu and the drawer, and refetches.
- **Counts agree.** Header `130 tracked` == rail badge `130` == sum of the four tier chips (`5+21+37+67`). `Open`/`+7d`/`Apps` cross-checked against the DB for a scratch company: `new 4 + saved 1 = 5` open, 8 discovered in 7 days, 1 applied — all matched exactly. (`Apps` alias divergence is COMP-08.)
- **Menu z-order is not actually reachable as a conflict.** The `⋯` menu (z 40) and sort menu (z 45) both close on the document click that opens a drawer (z 30), so neither can paint over it; verified live.
- **Long strings.** A 200-character company name ellipsises in a 142 px cell without widening the row (`row.scrollWidth == row.width`); the drawer title ellipsises; `—` renders for a company with no URLs, `·` for zero apps, `–` for a null `avg_fit`.

---

## Fixed in source

- `backend/api/routes_companies.py:75,204-205` — `create_company` now accepts and persists `aliases` and `auto_scoring_depth`. **Fixed + verified (backend)**: after the 13:20 restart, `POST /companies {aliases:["ZZT Alias One","ZZT Alias Two"], auto_scoring_depth:"full"}` returned them intact, and the Add modal's own success path round-tripped `aliases: ["ZZG One","ZZG Two"]`, `auto_scoring_depth: "full"`.
- `frontend/src/v2/Companies.jsx:37-54` — `detectAts` realigned to the backend `detect_scrape_type`. **Verified against the post-fix source**: evaluated the new function over 18 URLs (all 11 ATS families, `POST|`, a bare URL and a non-URL) and compared each against `detect_scrape_type` in-process — **18/18 agree**. The pre-fix bundle mismatched on 3 (`jobs.eu.lever.co` → Lever vs Generic, `jobs.eightfold.ai` → Eightfold vs Generic, `/search-jobs/results?` → Generic vs TalentBrew). Rebuild pending.
- `frontend/src/v2/Companies.jsx:686` — test-modal summary arithmetic (`found - kept` keyword-filtered, `found + rejected` extracted). Verified arithmetically against the backend's `total_found`/`total_rejected` contract; not observable on an API board (see "Couldn't test"). Rebuild pending.
- `frontend/src/v2/Companies.jsx:262` — **new**: integer `lineHeight: '20px'` on the header subtitle, removing the half-pixel origin that put all 126 rows on `x.5` (COMP-14). Rebuild pending.
- `frontend/src/v2/Companies.jsx:308` — **new**: dropped the inline `background: 'transparent'` on unselected sort options so `.v2-menuitem:hover` can apply (COMP-15). Rebuild pending.

---

## Couldn't test

- **`total_rejected > 0` in the test modal** — `[Validation]` rejects only come from the Playwright DOM extractor (`_extract_all_pages`), not from the ATS API paths. The only companies wired to a generic Playwright board are the user's real ones, and pointing a scratch company at a third-party HTML careers page for a multi-page render was out of scope for a dry run. The summary fix is verified against the backend's contract instead.
- **Tier-only empty state** (`No companies in the selected tiers.`) — all four tier buckets have rows in this database (5 / 21 / 35 / 65), and any search term routes the copy to the query variant instead. Verified by code path only.
- **Empty-database rendering** — out of scope per the brief (separate later pass).
- **`.v2-hover-accent` colour fix** — the correct fix is a one-line `!important` in the shared `theme.css`, which nine screens and several concurrently-running agents are measuring against. Left to the coordinator (COMP-16).
- **Scrollbar-driven layout** — headless Linux uses overlay scrollbars (width 0), so the `.v2-scroll` gutter behaviour on the rows container and the drawer body could not be reproduced (HANDOVER, "Traps in the harness itself").
- **`h1b_approval_rate` scale** — the drawer only prints `{rate}% approved` when the value is truthy, and every company in this database stores either `0.0` or a 0–100 percentage, so a 0–1 fraction (which would print `0.95% approved`) never appeared. Unverified, as the inventory suspected.

---

## Scratch data

Created, all via `ZZTEST`-prefixed names:
- companies: `ZZTEST Alpha`, `ZZTEST Gamma` (created through the Add modal), `ZZTEST Bundesdruckerei … Gm` (200-char name) — **all three deleted through the UI's own delete flow.**
- `scrape_log` rows: 7 synthetic rows against `ZZTEST Alpha` for the health-cell variants — **all deleted** (`delete … where company_id = …`, run three times; final count 0).
- jobs: one authorised `POST /scrape/company/{id}` against the public `boards.greenhouse.io/anthropic` board wrote **486** rows under `company = 'ZZTEST Alpha'` — **all 486 deleted** (`delete from jobs where company='ZZTEST Alpha'`; verified 0 applications and 0 tracer links referenced them first).

**Remaining ZZTEST rows: 0 of mine.** `ZZTESTFEED Alpha` (1 company + 8 jobs) belongs to another agent and was left in place.

Reversible edits to rows I did not create, all restored:
- `ZZTESTFEED Alpha` was caught by my `ZZTEST` search during the bulk-activate test and flipped `active: false → true`; **restored to `false`** immediately (`PATCH /companies/dd20e71e-… {"active": false}` → 200).
- No other company was mutated.

---

## Summary

- **Inventory boxes: 206.** Verified OK **126** · failed / finding attached **73** · untestable **7**. (The 73 includes every §7 "Suspicious" line, each of which was confirmed against the running app rather than left as a hypothesis, and the six hover rows that diverge from the design.)
- **Findings: 37** — **P1 1** · **P2 12** · **P3 16** · **P4 8**.
- **Fixes applied: 5** — 1 backend (verified live after the coordinator's restart), 4 frontend (2 carried in from the earlier cut-off run, 2 new this run; all rebuild-pending).
- **Scratch rows remaining: 0.**

The headline is COMP-01: the drawer's Save is fire-and-forget, so a rejected PATCH discards the user's edits with no signal of any kind — and COMP-04 explains why nothing catches it, since `Toast.jsx` is never imported and nine failure paths end in `console.error`. COMP-02, COMP-05 and COMP-06 are the same shape one level down: the screen fetches state once and then guesses (a 2.6 s timer for a 40 s scrape, a drawer snapshot that never refreshes, health and monitor data read exactly once). The design deviations are mostly consistent and deliberate-looking (unified `.v2-act` hovers, the 720 px drawer, the widened Résumés/ATS columns) and are flagged as decisions; the two that read as accidents — half-pixel rows and a hover that never fired — are fixed.

---

## P2 triage (2026-09-02)

Second pass over the open P2 findings. Contained, single-answer fixes were applied in source; nothing here changes a data model. Frontend edits are **rebuild pending** (the bundle is built in Docker by the coordinator); the one backend edit is **restart pending** (uvicorn runs without `--reload`).

| id | action | note |
|---|---|---|
| COMP-02 | fixed (JSX) | drawer renders from `companies.find(c => c.id === …)`, not the open-time snapshot; `downReason` reads the same live row |
| COMP-03 | fixed (JSX) | `loading` / `loadErr` state, spinner row, “Couldn’t load companies · Try again” panel; filter-miss copy suppressed on failure (pattern copied from `Searches.jsx`) |
| COMP-04 | fixed by toast wiring | verified in source — `useToasts`/`ToastStack` mounted; error toasts on load, patch, bulk, run, delete and add; only `runTest` stays silent (own in-modal error) |
| COMP-05 | fixed (JSX) | 2600 ms timer replaced by a 3 s `/monitor/active` poll filtered to `job_type === 'company_scrape'`; refetch when a run disappears; 409 keeps the spinner and pushes a `progress` toast |
| COMP-06 | fixed (JSX) | `fetchHealth()` runs at the end of every `fetchCompanies()`; the mount read of `/monitor/active` is scoped to company runs |
| COMP-07 | fixed (JSX) | `last_error` promoted into both the `health` comparator and `downCount`; still diverges from the cross-screen rail badge (coordinator’s call) |
| COMP-08 | fixed (backend + copy) | `_aggregates` alias-sums `app_counts`; header tooltip and drawer subtitle drop the wrong word “open”. **restart pending** — `Amazon` moves 15 → 16 |
| COMP-09 | fixed (JSX) | plain left click `navigate()`s; `href` kept so middle-click / ⌘-click / new-tab still work |
| COMP-10 | fixed (JSX) | `flexWrap: 'wrap'` on the toolbar |
| COMP-12 | fixed (JSX) | clamp on save to the bounds the inputs declare (`max_pages` 1–20; interval positive-or-null) |
| COMP-13 | fixed (JSX) | unresolvable ids render `{n} selected` instead of the bare “Selected” |

**Not in this pass:** COMP-11 (alias badge off-by-one) stays open — a one-line change that silently shifts every row’s badge, so it remains a decision.

Files touched: `frontend/src/v2/Companies.jsx`, `backend/api/routes_companies.py`. Brace / paren / backtick balance of both checked against `git show HEAD:<path>` — unchanged (all zero); `routes_companies.py` additionally `ast.parse`d clean.
