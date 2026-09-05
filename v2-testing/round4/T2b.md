# Round 4 — T2 part B: frontend state matrix (Résumés, Cover Letters, Persona, Stats, Settings, shell)

Tested 2026-09-05, branch `v2-redesign` @ `81df231`, bundle `index-D2u_A578.js`. Playwright ran inside `jtrakproject-backend-1` against `http://caddy` via `v2-testing/tools/h.py`; API key `pick-a-password`. Scripts: `scratchpad/{c,s1_states,s2_overlays,s2b,s3_settings_flake,s4_theme,s5_widths_zoom,s6_nav,s7_pdf,s8_soak,s9_runs,s9b_runs,s10_misc,s11_loading,s12_forms,s13_flake2,s14_shell,s14b_login}.py`, copied to `backend:/tmp/v2t/r4b/`. Screenshots and raw JSON: `v2-testing/artifacts/round4/t2b/` (247 files).

Live DB, read-mostly. Scratch rows `ZZR4-Base` (base résumé), its LLM-produced copy `ZZR4-Base (tailored)`, `ZZR4-Letter`, `ZZR4-TwoTab` — all created and deleted inside this pass; `backups/round4_t2b_pre_20260905.dump` taken first. The Persona was never written to: every autosave test route-mocked `PATCH /api/persona` to 200. Real LLM calls: **3** (one freeform tailor, one cover-letter regenerate, one light score), the budget ceiling. No API 529s were seen.

Findings are numbered `R4-T2B-NN`.

---

## Findings

### R4-T2B-01 · P2 · Settings' narrow-layout ResizeObserver silently fails to attach on ~1 load in 7, leaving the controls clipped at ≤1150 px
**Where** `frontend/src/v2/Settings.jsx:210-219` — the `ResizeObserver` effect's only dependency is `[!!S]` — against `Settings.jsx:480-490`, the `if (!ready || !S) return …` early return, which is the reason `scrollRef.current` is `null` until **both** `S` and `ready` are set.
**Repro** Open `/v2/settings` at 1024×820 (or any width where the rows pane lands under 720 px: 1024 and 900 both qualify with the rail expanded) and reload repeatedly.
**Actual** The section rows resolve to the wrong layout on a minority of loads, non-deterministically. Two independent loops:
- 20 cold loads at 1024×820 (`s3_flake.json`): **17 narrow (`flex-direction: column`, row height 97 px) / 3 wide (`row`, 55 px)** — same URL, same viewport, same data.
- 15 loads with `ResizeObserver.prototype.observe` instrumented (`s13_flake2.json`): **13 column / 2 row**, and in **both** row runs the counter read `{constructed: 0, observed: []}` — the observer was never even constructed, so the pane is unobserved for the whole life of the page. Shrinking the viewport to 860×820 afterwards (pane 358 px, far below the 720 px threshold) left those runs at `row` too, while all 13 good runs flipped to `column` immediately.

Mechanism: `load()` (inside `useSettled`) calls `setS`, and `useSettled`'s own `setDone` (which flips `ready`) resolves one microtask later. When React commits those as **two** renders instead of one, the `[!!S]` effect fires on the first render — while the component is still returning the `!ready` placeholder and `scrollRef.current` is `null` — hits the `if (!el …) return` guard, and never re-runs, because `!!S` never changes again.

**Impact** `flake-1024-row.png` vs `flake-1024-column.png`: in the wide-by-mistake state at 1024 the six LLM rows' **Override switches are cut off by the viewport's right edge**, the provider/model `Select`s collapse to `Cl… ▾` / `clau… ▾`, the Email-classification override's two model boxes shrink to ~20 px empty stubs, and the model-catalog summary truncates to `44 mod…`. That is exactly the damage the `narrow` mode exists to prevent — the code's own comment at `Settings.jsx:208-209` describes it.
**Expected** Deterministic. Add `ready` to the effect's dependency list (or attach the observer from a callback ref on the scroller, which cannot miss the mount).
**Screenshots** `flake-1024-row.png`, `flake-1024-column.png`, `settings-1024-load{0,1,2}-column.png`
**Status**: needs decision

### R4-T2B-02 · P2 · Reloading during a cover-letter regenerate loses every trace of the run, and the letter then rewrites itself with no notice
**Where** `frontend/src/v2/CoverLetterEditor.jsx:206-220` (`regenerate()` sets the local `regening` flag) and `:223-257` (the `/monitor/active` poller is gated on `if (!regening) return`). Nothing re-derives an in-flight `cl:{id}` run from the server on mount.
**Repro** Open a letter → `Regenerate…` → `Regenerate` → reload the page while the run is still live.
**Actual** Measured live against a real run (`s9b_runs.json`): before the reload, `Regenerating…` spinner present (1) and the modal correctly refuses Escape (still open — deliberate, and right). After the reload: `{modal: 0, spinner: 0}` — no modal, no spinner, no toast, no banner; the editor looks completely idle while an LLM call is rewriting the document. The run finished 10 s later; with the page still open the textareas still read the pre-run text (`["First ZZR4 paragraph.", "Second ZZR4 paragraph."]`), and only a second manual reload showed the rewritten letter (`["Google's Merchant API work sits at the intersection of techn…", …]`). `GET /monitor/history` confirms `generate_cover_letter / completed / "Regenerated letter for Google — Senior Product Manager, Merchant API"`.

The pattern the rest of v2 uses is available and works: the Résumés shelf re-derives in-flight tailors from `/monitor/active` on every mount, so its `tailoring…` chip survives a refresh — verified with a mocked run, **1 before the reload, 1 after** (`s9b_runs.json → inflight/shelf`).
**Expected** On mount, ask `/monitor/active` whether a `generate_cover_letter` run with `scope_key === 'cl:'+id` is live; if so, re-enter the regenerating state (spinner + reload-on-finish), the way the shelf does for `tailor_resume`.
**Screenshots** `run2-regen-running.png`, `run2-regen-after-reload.png`, `run2-regen-done.png`
**Status**: needs decision

### R4-T2B-03 · P2 · A failed load poisons the warm-start cache, so the *next* visit opens by asserting "0 bases · 0 tailored copies"
**Where** `frontend/src/v2/hooks.js:86-98` — `useWarm` writes `localStorage` whenever `ready && live != null`, with no notion of the load having failed — plus its three call sites, which all pass `ready ? {…} : null` and compute the numbers straight from the (empty) state: `Resumes.jsx:88`, `CoverLetters.jsx:246`, `Stats.jsx:378-381`.
**Repro** Load `/v2/resumes` once (cache fills), then reload with `GET /api/resumes/shelf` → 500, then reload again on a healthy but slow backend.
**Actual** Measured (`s10_misc.json`):

| screen | cache after a good load | cache after one 500 |
|---|---|---|
| Résumés | `{"b":5,"c":50,"a":299}` | `{"b":0,"c":0,"a":0}` |
| Cover Letters | `{"n":19,"live":2}` | `{"n":0,"live":0}` |
| Stats | `{"has":true,"status":"completed","at":"2026-09-04T14:04:31Z",…}` | `{"has":false,"status":null,"at":null,…}` |

The third visit then paints `Résumés · 0 bases · 0 tailored copies, listed under their jobs` from the poisoned cache before the real data lands — a confident, wrong number where the whole point of the warm start is that it "matches the pre-refresh frame".

The same bug has a second face **during** the failing load: the header reads `0 bases · 0 tailored copies` while the body directly below reads `Couldn't load your résumés. Retry, or check that the backend is running.`, and the rail badge next to it still shows the cached `5`. Cover Letters is identical (`0 letters · 0 live applications` + `Couldn't load your letters` + rail badge `19`, and the list header count reads `ALL LETTERS 0`).
**Expected** Only write the warm cache when the load actually succeeded (thread the screen's existing `loadErr`/`coreErr` flag into `useWarm`, or pass `null` as `live` on failure), and render the subtitle as `—`/NBSP rather than zeros when the load failed.
**Screenshots** `resumes-err500.png`, `coverletters-err500.png`, `warm-resumes-poisoned-early.png`
**Status**: needs decision

### R4-T2B-04 · P3 · Stats does not hold together at 900 px: the LLM-cost period pills overflow their card and the cost table collapses to ellipses
**Where** `frontend/src/v2/Stats.jsx:558-601` — the LLM-costs card is a fixed `height: 300` grid cell with a `1.4fr / 1fr` split and a non-wrapping header row (`Heading` + "how priced?" + the four period pills), and its table head at `:581-585` gives `Purpose`/`Model` `flex:1.1`/`1.4` with no `padding-right`. Also `:439-457`, the five-tile KPI strip, which has no reflow at all.
**Repro** `/v2/stats` at 900×900. (1440 and 1024 are both fine.)
**Actual** Two elements measurably escape the viewport (`s5_widths.json → w900/stats`): the period-pill group and the `all` pill both end at `right: 907` against `innerWidth: 900`. In the same frame the KPI strip clips its last tile's label (`BEST OPEN SCORE` runs into the card edge) and its three sub-values ellipsise to `-4…`, `29 …`, `JPMo…`; the cost table renders `sc… cla… 503 $0.00 —` with the `Purpose` and `Model` columns cut to 2–3 characters and the head reading `COST CAC`. The `Purpose`/`Model` head labels also run together as `PURPOSEMODEL` at both 900 and 1024. Every other screen at 900 px is clean (0 offenders, no horizontal page scroll), as is every screen at browser zoom 75 / 90 / 110 %.
**Expected** Let the pill row wrap (or drop to an icon/`Select` under a threshold), give the two text columns a right pad the way the body rows already have, and let the KPI strip wrap or scroll below ~1000 px.
**Screenshots** `zw-w900-stats.png` (compare `zw-w1024-stats.png`, `zw-w1440-stats.png`)
**Status**: needs decision

### R4-T2B-05 · P3 · The résumé editor's ⋯ menu advertises keyboard shortcuts (`c`, `e`, `a`) that nothing implements
**Where** `frontend/src/v2/ResumeEditor.jsx:554-556` — `<MenuItem icon="✉" hint="c">Cover letter</MenuItem>`, `hint="e"` on "Open in feed", `hint="a"` on "Mark applied" — against `ui.jsx:671` which documents `hint` as "the trailing shortcut/count", and `JobFeed.jsx`, which really does bind single-letter keys (`f/j/s/x/e/o`), so the idiom is established in this app.
**Repro** Open any tailored copy, note the hints in the ⋯ menu, close the menu, press `c`, `e`, `a`.
**Actual** Nothing happens for any of the three (`s10_misc.json → shortcuts/resume-editor`: `url_changed: false` for all three). The screen's only key handlers are Escape (`ResumeEditor.jsx:196`, `:111`) and Ctrl/⌘+B for bold inside a bullet (`ResumeSections.jsx:47,79`). Sibling items in the same menu use the same slot for prose (`adds a copy`, `score only`, `with report`, `3 to review`), so the single letters read as a promise the screen doesn't keep.
**Expected** Either bind the three keys (they are unambiguous — the editor has no other single-key handler) or drop the hints.
**Screenshot** `misc-resume-menu-hints.png`
**Status**: needs decision

### R4-T2B-06 · P3 · Persona and Settings show nothing but the nav rail while loading; the other three screens hold their chrome
**Where** `frontend/src/v2/Settings.jsx:480-490` and `Persona.jsx:298-308` — both return a bare centred `<div/>` until `ready`, so no `<h1>`, no header row, no page title exists at all during the wait. Contrast `Stats.jsx:398-407` (renders its real header, warm subtitle included, while the cards wait) and `Resumes.jsx:156-159` / `CoverLetters.jsx:369-372` (header and shell always mounted; only the list contents wait).
**Repro** Hold every `/api/**` request open (non-blocking route capture — a `time.sleep()` in the handler blocks the whole harness and measures nothing) and sample the DOM at 250 ms and 1750 ms.
**Actual** (`s11_loading.json`) Persona and Settings both report `{h1: null, header: null, bodyLen: 163}` at 250 ms **and** at 1750 ms, on the cold and the warm pass alike; the settled frame then has `h1` at top 22 and a 92 px header. Résumés / Cover Letters / Stats report their `h1`, header and (on the warm pass) the correct cached subtitle from the first sampled frame, and `header`/`aside` rects are byte-identical early vs settled — no jump, no flash on any of the five. So the shell is right on three screens and absent on two; on a slow link Persona and Settings are indistinguishable from a broken route for as long as the request takes.
**Expected** Give Persona and Settings the same treatment as Stats: paint the header row and page title immediately, let only the body wait.
**Screenshots** `load-settings-cold-250ms.png`, `load-persona-cold-250ms.png` (vs `load-stats-cold-250ms.png`, `load-resumes-cold-250ms.png`)
**Status**: needs decision

### R4-T2B-07 · P3 · Keyboard focus is effectively invisible on the dark nav rail
**Where** `frontend/src/v2/theme.css:1126` — `.jn-v2 [tabindex="0"]:focus-visible { outline:var(--focus-outline); box-shadow:var(--focus-shadow) }` only matches elements that carry an explicit `tabindex="0"`. The rail's items are real `<NavLink>` anchors (`V2App.jsx:215`, `:213`, `:221`), which are natively focusable and therefore never match that rule.
**Repro** Load any `/v2` screen, press Tab once.
**Actual** (`s12_forms.json`) The first rail link focuses with the UA default `outline: rgb(16, 16, 16) auto 1px` and `box-shadow: none`, against a rail background of `rgb(34, 33, 28)` — roughly 1.1:1, and visually a hairline you have to hunt for (`focus-rail.png`). All ten first Tab stops are identical — the nine nav items plus `← Classic UI`, every one `auto 1px rgb(16,16,16)` with no box-shadow. The first `[tabindex="0"]` control in the content area, `+ New résumé`, gets the intended treatment: `box-shadow: rgba(63,107,82,0.22) 0 0 0 2px`. So the entire primary navigation — the first ten Tab stops on every screen — has no usable focus indicator, while everything after it does.
**Expected** Extend the focus-visible rule to the rail's anchors with a rail-appropriate ring token (the rail already has `--rail-accent` / `--rail-dim` to draw on).
**Screenshot** `focus-rail.png` (compare `focus-content.png`)
**Status**: needs decision

### R4-T2B-08 · P3 · The cover-letter preview's failure line claims "Showing the previous version" when there is no previous version
**Where** `frontend/src/v2/CoverLetterEditor.jsx:519` — the `pdfErr` branch always reads `Preview failed. Showing the previous version · Retry`, because `setPdfUrl` is only ever assigned on success and is simply left alone on failure (`:168`).
**Repro** Open a letter with `GET /api/cover-letters/{id}/pdf` stubbed to 500.
**Actual** The toolbar says the previous version is on screen while the pane below it says `Rendering the preview…` — i.e. nothing is shown at all, because the first render is the one that failed (`pdf-cleditor-failed.png`). The résumé editor gets the same situation right: it clears the stale blob (`ResumeEditor.jsx:411-414`) and says `Preview failed — the PDF could not be rendered.` with a Retry pill. Both editors recover correctly once the route is unstubbed and Retry is clicked (`s7_pdf.json`: iframe back with a fresh `blob:` src in both).
**Expected** Only claim a previous version when `pdfUrl` is non-null; otherwise say the preview could not be rendered, as the résumé editor does.
**Screenshots** `pdf-cleditor-failed.png`, `pdf-cleditor-retried.png`
**Status**: needs decision

### R4-T2B-09 · P3 · A cover letter with no linked job is filed under "Archived · from rejected applications & skipped jobs"
**Where** `frontend/src/v2/CoverLetters.jsx:238-241` — `isActive = (c) => (c.stage ? c.stage !== 'rejected' : LIVE_JOB.includes(c.job_status))`. With no application **and** no job, `c.job_status` is `undefined`, which is not in `['new','saved','applied']`, so the letter falls to the archived group.
**Repro** `POST /api/cover-letters {"name":"ZZR4-Letter", …}` with no `job_id` (the endpoint accepts it — `routes_cover_letters.py:154`), then open `/v2/cover-letters`.
**Actual** The brand-new draft is invisible in the default list (`letters/zzr4-visible-active: 0`) and only appears after clicking `browse ›` on the archived band, under the label "18 letters from rejected applications & skipped jobs" — which is untrue of a draft created five seconds ago. The same fallback catches any letter whose job row was later removed by the `job_cleanup` scheduler, silently demoting live work.
**Expected** Treat "no job and no application" as a draft (the row already renders a `Draft` tag for exactly that case at `:302-305`), and reserve the archive for `stage === 'rejected'` or a job status that is genuinely dead.
**Screenshot** `zw-w900-coverletters.png` (the band), `coverletters-one.png`
**Status**: needs decision

### R4-T2B-10 · P3 · Stats' empty state leaves two cards blank with no line of explanation
**Where** `frontend/src/v2/Stats.jsx:527-534` (`buckets.map(...)` with no fallback) and `:613-651` (the Schedules `TableHead` + `ordered.map(...)`, whose only non-row branch is `schedErr`).
**Repro** `/v2/stats` with `/api/stats/score-distribution` → `{buckets: [], scored_count: 0}` and `/api/scheduler/jobs` → `[]`.
**Actual** Score distribution renders a titled card with an entirely blank body; Schedules renders its column header over nothing. The two cards beside them do the right thing in the same frame — LLM costs says `No LLM calls in this period.`, Run history says `No runs yet.`, Activity log distinguishes "No activity recorded yet." from "No activity matches these filters." A brand-new install (0 scored jobs) and a scheduler that returned an empty list both land here.
**Expected** One line each, matching the neighbours ("No scored jobs yet.", "No scheduled jobs.").
**Screenshot** `stats-empty.png`
**Status**: needs decision

### R4-T2B-11 · P4 · A tailor started from the résumé editor becomes invisible if you reload that editor
**Where** `frontend/src/v2/ResumeEditor.jsx:105` (`pendingRef`, in-memory only) and `:117-156` — the watcher only inspects runs it put in `pendingRef` itself, so a reload empties the list and the poll immediately returns at `if (!pendingRef.current.length) return`.
**Repro** Tailor from a base résumé, stay on the editor, reload while the run is live.
**Actual** With a `tailor_resume` run live on `/monitor/active`, the editor shows nothing about it (`s9b_runs.json → inflight/shelf.editor_shows: false`), and because the watcher's queue is gone it never fires the "Tailored copy for X is ready · Open ↗" toast either — the copy just appears on the shelf later. Lesser sibling of R4-T2B-02: the shelf re-derives correctly, the editor doesn't.
**Expected** Seed `pendingRef` from `/monitor/active` on mount (filter `job_type === 'tailor_resume'`), the way the shelf does.
**Status**: needs decision

### R4-T2B-12 · P4 · Rail badge counts never refresh in a second tab
**Where** `frontend/src/v2/V2App.jsx:137` — counts reload on mount and on the same-document `jn:counts-changed` event only. `theme.js:140-142` already listens to `window.storage` for the look, so the cross-tab channel exists and is used for one axis but not the other.
**Repro** Open two tabs on `/v2/*`; create a cover letter (or delete a company) from tab A.
**Actual** (`s6_nav.json → twotabs/rail-counts`) Tab B's `Cover Letters` badge stayed at `19` for the rest of the session after a row was created; tab A read `20` on its next reload. The badge is not merely stale for a moment — nothing ever refreshes it while that tab stays mounted. The theme axis behaves correctly in the same test: switching to Cobalt/Dark in tab A moved tab B live (`{t: 'cobalt', a: 'dark', bg: '#0f1115'}` in both).
**Expected** Either mirror `jn:counts-changed` through a `localStorage` ping so other tabs re-`loadCounts`, or accept the divergence explicitly (it is only a badge).
**Screenshot** `nav-twotabs-B.png`
**Status**: needs decision

### R4-T2B-13 · P4 · The theme-key migration leaves an invalid value in `jobnavigator_theme` for ever
**Where** `frontend/src/v2/theme.js:55-61` (`migrateKeys`) and the matching boot block in `frontend/index.html:23-35`. The old light/dark value is copied out of `THEME_KEY` into `APPEARANCE_KEY`, but `THEME_KEY` is only overwritten when a legacy `jobnavigator_skin` also exists.
**Repro** Seed `localStorage` with `jobnavigator_theme='dark'` and no `jobnavigator_skin`, then load `/v2/feed`.
**Actual** (`s4_theme.json → migration`) `data-appearance="dark"` ✔, `data-theme="default"` ✔ (both `readTheme()` and the boot script validate against `THEMES` and fall back) — but storage keeps `{app: 'dark', theme: 'dark', skin: null}`, i.e. a permanently invalid palette value that is re-read and re-rejected on every load and is never repaired. Same shape for a junk skin: seeding `skin='bogus'` leaves `theme: 'bogus'`. Harmless today; it becomes a real bug the day a palette is named `dark`, `light` or `system`.
**Expected** Repair on read — when `readTheme()` rejects the stored value, write the fallback back.
**Status**: needs decision

---

## What was checked and found correct

**Theme / appearance.** All **15** combinations (Default · Board · Cobalt · SaaS · Win98 × light · dark · system) switch at runtime from the Settings pickers with **no reload**, and stamp `data-theme`/`data-appearance` on `<html>` *and* on the `.jn-v2` root, toggle `html.dark`, and move `--bg`/`--rail`/`--accent` together (`s4_theme.json → settings_switch`, e.g. win98/light `--bg:#008080 --rail:#c0c0c0`, cobalt/dark `--bg:#0f1115 --rail:#090c12`). The rail `◐` cycles Light → Dark → System → Light and writes `jobnavigator_appearance` on each step; when the rail is collapsed the glyph takes the health dot's slot and still cycles. A reload keeps both axes. **No flash on reload in any of the 10 theme × light/dark pairs**: an init-script probe recorded `getComputedStyle(document.documentElement).backgroundColor` at `readystatechange`, at the first and second `requestAnimationFrame`, and at 1.5 s — the correct ground was already painted at the *first* sampled frame every time (e.g. win98/light `rgb(0,128,128)` at `rs:interactive` t=7 ms), and `framenavigated` screenshots agree. **Old-key migration** works for all six seeded shapes: `theme=dark + skin=cobalt` → appearance `dark` / theme `cobalt` / skin removed; `skin=win98 + dark_mode=true` → `dark`/`win98`; `theme=system + skin=saas` → `system`/`saas`; `theme=light + skin=alt` → `light`/`alt` (a picker-hidden palette still paints, as designed) — each with no flash (see R4-T2B-13 for the one loose end).

**Shell.** Login overlay: appears on a 401 with the theme root attached, refuses Escape and scrim clicks, distinguishes a wrong key (`Invalid API key`) from a network failure, reveals/hides the key, and on the correct key writes `jobnavigator_api_key`, sets `sessionStorage['jn:welcome']` and drops straight into the dashboard. Welcome overlay then appears, Escape closes it, and its steps navigate (`Build your résumé + Persona` → `/v2/resumes`, overlay closed). Rail collapse persists across reload (206 → 50 → 50, `jobnavigator_v2_rail: 'collapsed'`).

**Toasts.** Four consecutive failing saves produced **3** error toasts (`MAX = 3` honoured) and all three were still on screen 6 s later (errors never auto-dismiss). Undo toasts work and expire: Persona Q&A remove → `Removed answer` → Undo restores the row (18 → 19 → 18 → 19); cover-letter paragraph delete → `Removed paragraph` → Undo restores (3 → 2 → 3), and a second delete's toast was gone at 6.5 s (5 s TTL).

**Overlays.** Every modal, menu and popover on the five screens opens, closes on Escape, and closes on an outside click: Résumés add-modal; résumé editor ⋯ menu / template / paper / Tailor modal / delete `ConfirmDialog`; cover-letter pickers (résumé, job); letter editor ⋯ menu / template / paper / Regenerate modal; Persona import `ChoiceModal` and group toggles; Stats type filter, tab switch, period pills, Funnel↔Flow, Load more; Settings edit modal, model catalog, cron preset menu, info panels, anchor jumps, search. **Layer peeling is correct**: inside the Regenerate modal the source `Picker`'s Escape closes only the listbox (`listbox 1→0, modal 1→1`), the second closes the modal; the model catalog's typeahead behaves the same (`sug 1→0, modal 1→1`); the catalog's remove-`ConfirmDialog` takes its own Escape and leaves the catalog open. A regenerate in flight correctly refuses Escape and scrim dismissal.

**Forms.** Settings: a good `PATCH` flashes `Saved`; a 400 shows the server's own `detail` and rolls the optimistic value back (`9` → `7`); the integer rows strip non-digits (`abc12x` → `12`); a 3-field cron is refused client-side (`Cron needs 5 fields`, **0** PATCHes sent); a set secret renders as `••••••` and clearing the box sends **no** PATCH. Persona autosave debounces **per node** — editing `preferences.notice_period` then `contact.city` sent two PATCHes with disjoint bodies (`['preferences']`, `['contact']`) — and flashes `Saved ✓`. Résumés add-modal disables Create while the name is empty (`aria-disabled=true`) and Enter submits.

**PDF preview** (both editors): iframe mounts with a `blob:` src at 654×757, every `/pdf` request returned **200**, the Template picker lists 8 layouts and switching one re-renders and persists across a reload (`Template Garamond Modern`), Paper → A4 likewise, and a forced 500 shows the failure line and recovers on Retry. *Note:* headless Chromium does not paint the PDF plug-in, so the pages themselves are blank in every screenshot on both editors — pixel-level PDF rendering is out of reach for this harness and belongs to T3.

**States.** empty / one row / many (60 bases × 8 chips = 480 copies; 500 letters) / 500 / 401 / backend down / slow-3G, on all five screens: no page errors anywhere, correct error copy with a working retry on each, and a 401 raises the login overlay on every screen. 500 letters and 60 base cards render without pagination and without visible cost.

**Navigation.** Back/forward across shelf → editor works on both Résumés and Cover Letters (screen state such as a search query is not restored, which is consistent with the rest of v2). A bad résumé id redirects to the shelf with a flash toast; a bad letter id shows "This letter no longer exists." with Back/Try-again links. `/v2/stats#runs` scrolls the Run-history card to the top (`scrollTop 1021`, card top 92).

**Widths and zoom.** 1440 / 1024 / 900 and browser zoom 75 / 90 / 110 % (emulated as viewport ÷ zoom with a matching device-scale factor) over all five screens plus both editors: **no page-level horizontal scroll anywhere**, and zero elements past the viewport edge in 41 of the 42 cells — the exception is `w900/stats` (R4-T2B-04).

**Soak (20 min, 11 samples, both pollers live).** `/v2/feed` and `/v2/stats` held open in one context with `setInterval`/`setTimeout` monkey-patched and `performance.memory` sampled every 2 min (Chromium launched with `--enable-precise-memory-info`). Live timer counts never grew: Feed steady at **1 interval / 0 timeouts** for the whole 20 min (2 timers ever created); Stats at **0 intervals / 1 timeout**, with `toMade` climbing exactly 12 per 2 min (4 → 124) — its self-rescheduling 10 s poll, always exactly one live timer, never a second one stacking. DOM nodes flat at every sample (307 / 704). Heap: Feed `9.5 → 7.5 → 7.7 MB`, flat; Stats sawtooths `10.1 → 17 MB` and drops back to 11.2 MB on GC three times over, with no rising floor. Four backend runs landed inside the window and were picked up by the Stats poller (`tailor_resume`, `generate_cover_letter`, `score_resume`, plus a manually triggered `email_check` — all `completed`). No leak signal on either screen. *Caveat:* 20 minutes, not 8 hours, and the only scheduler job naturally due in the window was `email_check` (the next scrape was two days out), so it was triggered by hand.

---

## Coverage

| screen | empty | one | many | 500 | 401 | loading | down | throttled | modals/menus | shortcuts | undo | refresh mid-run | back/fwd | 2 tabs | 1440/1024/900 | zoom 75/90/110 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Résumés shelf | ✔ | ✔ | ✔ 60×8 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | n/a | — | ✔ | ✔ | ✔ | ✔ | ✔ |
| Résumé editor | — | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | — | ✔ | **T2B-05** | ✔ | **T2B-11** | ✔ | — | ✔ | ✔ |
| Cover Letters | ✔ | ✔ | ✔ 500 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | n/a | — | ✔ | ✔ | — | ✔ | ✔ |
| Letter editor | — | ✔ | — | ✔ | ✔ | ✔ | ✔ | — | ✔ | n/a | ✔ | **T2B-02** | ✔ | — | ✔ | ✔ |
| Persona | ✔ | ✔ | ✔ (18 Q&A) | ✔ | ✔ | **T2B-06** | ✔ | ✔ | ✔ | n/a | ✔ | n/a | ✔ | — | ✔ | ✔ |
| Stats | ✔ **T2B-10** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | n/a | — | ✔ | ✔ | ✔ | **T2B-04** | ✔ |
| Settings | n/a | n/a | n/a | ✔ | ✔ | **T2B-06** | ✔ | ✔ | ✔ | n/a | — | n/a | ✔ | ✔ | **T2B-01** | ✔ |
| Shell (rail, login, welcome, toasts, theme) | ✔ | — | — | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | Esc/Enter ✔ | ✔ | — | ✔ | ✔ **T2B-12** | ✔ | ✔ |

`T2B-NN` = finding `R4-T2B-NN` filed for that cell. Extras: Settings 1024 flake (R4-T2B-01, 35 loads across two loops), 20-minute soak, appearance/theme matrix (15 runtime combinations + 10 no-flash reloads + 6 migration shapes), PDF preview in both editors.

## Notes on method
- A `time.sleep()` inside a Playwright route handler blocks the single dispatcher thread, so the page cannot be sampled while it sleeps — the first pass at the loading state measured post-hang state only and was thrown away. The working pattern (used for R4-T2B-06 and R4-T2B-03) is to capture the `route` object and return without fulfilling, sample from the main thread, then release the held routes.
- `ToolbarTrigger` sets `aria-label={ariaLabel || title}` (`ui.jsx:482`), so a trigger whose `title` matches its menu's `ariaLabel` (résumé Template/Paper, letter Template) makes `[aria-label="…"]` match both the trigger and the menu — three overlay probes read as "Escape didn't close" until the marker was switched to `[role="listbox"]`. Worth knowing for future scripts; also a mild a11y smell (a button and a listbox sharing one accessible name), not filed.
- `text=Model catalog` matches the Settings row label as well as the modal title; same class of false positive.
- `page(b, …)` from `h.py` warms up with a `networkidle` load of `/v2/feed`, which times out under concurrent load; `c.py`'s `mkpage()` skips it (the API key in `localStorage` is enough for XHR — only the résumé editor's plain `<a href>` download link needs the session cookie).

## Cleanup
`ZZR4-Base` deleted (its LLM-tailored copy `ZZR4-Base (tailored)` cascades with it), `ZZR4-Letter` deleted, `ZZR4-TwoTab` deleted in-run. Verified: `GET /api/resumes?is_base=true` and `GET /api/cover-letters` carry no `ZZR4` rows. No real row was created, edited or deleted; the Persona singleton was never written (every autosave test mocked its PATCH). One setting was PATCHed only against a mocked endpoint, never the server.
