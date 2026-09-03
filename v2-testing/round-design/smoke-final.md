# Final smoke test — post design-consistency pass

Read-only pass, no data mutations, no LLM calls, no rebuilds, no restarts. Repo v2-redesign branch, HEAD d23817c (D6-fixup, theme store + alt skin landed). Bundle `index-DynVv4lS.js`.

Playwright inside the backend container against `http://caddy`, API key `pick-a-password`, harness `/tmp/v2t/h.py`. Theme driven by localStorage `jobnavigator_theme` (`light|dark|system`) and skin by `jobnavigator_skin` (`default|alt`); legacy `jobnavigator_dark_mode` boolean is migrated on boot and no longer authoritative.

Matrix: 4 combinations per route — light/default, dark/default, light/alt, dark/alt — at 1440×900 (all 4) and 1024×700 (default skin only, 2 of the 4). Table columns: `light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt`.

Per route/combination: heading present; console errors + pageerrors (X-Frame-Options iframe noise ignored); primary controls present and not dimmed; no horizontal overflow; rail counts within 1s and health dot (skipped on `/v2/ui` and `/v2/toasts` — both rail-less by design); stubbed-500 error state; Escape closes an open menu/modal; Tab×3 focus targets.

Once per route (light/default only): every modal/drawer/menu opened and closed, methodology matching round 3 (`v2-testing/round3/smoke.md`).

Other agents run flows in parallel using row prefixes `ZZA`/`ZZB` — those rows were ignored and left untouched wherever encountered.

Issue IDs: `DS-S-NN`. Severity: P1 broken/data-loss · P2 functional · P3 design deviation (incl. deliberate cross-screen consistency choices — logged as needs-decision, not assumed defects) · P4 nit.

---

# Batch A smoke — theme/skin matrix (Feed, Searches, Companies, Applications)

Read-only pass, no data mutations, no LLM calls, no rebuilds, no restarts. Repo v2-redesign branch, HEAD d23817c.
Playwright inside the backend container against `http://caddy`, API key `pick-a-password`, harness `/tmp/v2t/h.py` + `/tmp/v2t/battA_common.py` (adapted from round3's `common3.py`).

Theme driven by localStorage `jobnavigator_theme` (`light|dark|system`) and skin by `jobnavigator_skin` (`default|alt`); legacy `jobnavigator_dark_mode` boolean is migrated on boot and no longer authoritative — set both consistently per the harness note.

Matrix: 6 combinations per route — light/default @1440×900, dark/default @1440×900, light/default @1024×700, dark/default @1024×700, light/alt @1440×900, dark/alt @1440×900 (alt skin is 1440-only). X-Frame-Options/CSP iframe console noise ignored (expected noise from cached-page iframes elsewhere in the app).

"Primary controls" auto-detected as the top ~6 clickable elements in `main` near the top of the screen, deduped by label. "Not dimmed" (new this round): computed `opacity` not < 1 and no unexpected `disabled`/`aria-disabled` on those controls — flagged inline as `DIMMED:[(label, opacity, disabled), ...]` when found.

Once per route (light/default only): every modal/drawer/menu opened and closed, methodology matching round 3 (`v2-testing/round3/smoke.md`) — trigger click counts `position:fixed`/`absolute` elements with `zIndex` in `[25,80)` before/after, Escape then scrim-click (far-corner mouse click) tested separately, each trigger probed on its own fresh browser context.

Scratch data note: `ZZA`/`ZZB` rows from parallel flow agents may appear in list snapshots — left untouched.

---

## V2 Feed
`/v2/feed`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | The Feed | The Feed | The Feed | The Feed | The Feed | The Feed |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Pick résumés + depth, then s, Search job titles, Source ▾, Company ▾, H-1B ▾, Score ≥ ▾] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | none dimmed on any combo — auto-probe found a different top-of-screen control set than round 3 (filter-bar dropdowns rather than row action buttons); page/data shape, not a theme/skin effect |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 |  |
| rail counts (<1s) | ✔ feed=22 searches=7 companies=127 applications=377 resumes=6 cover-letters=16 | ✔ same | ✔ same | ✔ feed=25 searches=7 companies=127 applications=377 resumes=6 cover-letters=16 | ✔ feed=25 same | ✔ feed=25 same | feed count moved 22→25 mid-run (live background scrape activity elsewhere in the system, not a stale/error value) |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=273 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Tab×3 focus targets | DIV[Company▾] > DIV[H-1B▾] > DIV[Score ≥▾] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |

### Feed — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Source filter menu | ✔ | ✔ | ✔ |  |
| Sort menu | ✔ | ✔ | ✔ |  |
| Keyboard shortcuts modal | ✔ | ✔ | ✔ |  |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Tailor/Create-copy picker modal (from detail head) | ✔ | ✔ | ✔ |  |

---

## V2 Searches
`/v2/searches`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | Searches | Searches | Searches | Searches | Searches | Searches |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [+ New search, Resume the schedule, More actions, Pause — leaves the schedule, JobSpy "product manag..., JobSpy] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | none dimmed on any combo |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 |  |
| rail counts (<1s) | ✔ feed=25 searches=7 companies=127 applications=377 resumes=6 cover-letters=16 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | stable across all 6 combos |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=124 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Tab×3 focus targets | DIV[Pause — leaves the schedule] > DIV[Resume the schedule] > DIV[Pause — leaves the schedule] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | toggle controls rendered as `div[role=button]` rather than `<button>` — focus order consistent across all 6 combos, not a skin/theme issue |

### Searches — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + New search inline panel | ✔ | ✔ | — | inline panel, no scrim to click |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Test (dry-run) modal — request stubbed | ✔ | ✔ | ✔ |  |

---

## V2 Companies
`/v2/companies`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | Companies | Companies | Companies | Companies | Companies | Companies |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [+ Add company, Search companies, Add/remove from filter · mul, Applies to all 127 companies, ▲ Oracle T3 …, Click to pause scraping] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | none dimmed on any combo |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | **R3-S-01 still clean this round** — the 1024px column-shedding fix (8804ae3) holds; no recurrence at 1024×700 in either theme |
| rail counts (<1s) | ✔ feed=25 searches=7 companies=127 applications=377 resumes=6 cover-letters=16 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=284 err_text=True pageerrors=0 | ✔ same | ✔ nonblank=261 err_text=True pageerrors=0 | ✔ same | ✔ nonblank=284 err_text=True pageerrors=0 | ✔ same |  |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Tab×3 focus targets | DIV[▲ Oracle T3 No results…] > DIV[Click to pause scraping] > DIV[Addepar T3 healthy·scraped…] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |

### Companies — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + Add company modal | ✔ | ✔ | ✔ |  |
| Row click -> edit config drawer | ✔ | ✔ | ✔ | initial automated pass (generic corner-click proxy at (3,3)) reported ✖ — that coordinate lands on the nav rail, which sits above this drawer's z-index:29 scrim and swallows the click. Re-probed at (400,400) (confirmed the actual scrim element via `elementFromPoint`, matching round 3's own verification coordinate) → closes correctly. **R3-S-02 fix (8804ae3) confirmed still in place**, not a regression — first-pass ✖ was a probe artifact, corrected here. |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Sort menu | ✔ | ✔ | ✔ |  |
| Test (dry-run) modal — request stubbed | ✔ | ✔ | ✔ |  |

---

## V2 Applications
`/v2/applications`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | Applications | Applications | Applications | Applications | Applications | Applications |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [+ Log application, Search title or company…, Company ▾, APPLIED 30 ⌄, Sr PMT Customer Experience…, Snapshot of the posting from] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | none dimmed on any combo |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 |  |
| rail counts (<1s) | ✔ feed=25 searches=7 companies=127 applications=377 resumes=6 cover-letters=16 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=293 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| Tab×3 focus targets | DIV[APPLIED 30 ⌄] > DIV[Sr PMT, Customer Experience…] > DIV[Sr. Product Manager ✉ Docusign] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |

### Applications — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + Log application modal | ✔ | ✔ | ✔ |  |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Prep pack modal (real GET, no LLM) | ✔ | ✔ | ✔ |  |

---

## Issues

No P1/P2 defects found across the four routes × 6 combos. Design-consistency pass (theme/skin system) held up cleanly: 0 console errors, 0 pageerrors, 0 h-overflow, all rail counts populated and self-consistent, health dot present, all stubbed-500s produced a visible non-blank error state, all generic-menu-trigger Escape probes opened+closed cleanly, and no primary control was found dimmed (opacity < 1 or disabled/aria-disabled) on any of the 24 combo/route cells checked.

### DS-S-01 · P4 · Generic scrim-click probe gives a false negative on Companies' edit drawer (probe artifact, not a product defect)
**Where** test methodology only — `frontend/src/v2/Companies.jsx` `Drawer`'s scrim (`position:absolute; inset:0; z-index:29`), `/v2/companies`, light/default 1440×900
**Repro** Run the generic `open_close_probe` (round 3's `common3.py` / this round's `battA_common.py`), which tests "closed on scrim click" via `pg.mouse.click(3, 3)` (viewport top-left corner) as a stand-in for "click outside the overlay."
**Actual** First pass reported `closed_scrim=✖` for "Row click → edit config drawer." Root cause: at (3,3) `document.elementFromPoint` returns the nav rail (a `position:relative` element inside a higher-stacking-context ancestor), not the drawer's z-index:29 scrim — the rail visually and hit-test-wise sits in that corner. Re-probed at (400,400), confirmed via `elementFromPoint` to be the actual scrim `div[style*="z-index: 29"]`: click closes the drawer correctly (`closed_scrim=✔`), matching round 3's own verification (`round3/verify.md` item 10) of the `8804ae3` fix for R3-S-02.
**Expected** No product change needed — the drawer's scrim-click-to-close behavior is confirmed working. Logged only so a future automated pass doesn't repeat the (3,3) corner-click assumption against this specific trigger; the generic probe should use a coordinate inside the content area (e.g. viewport center) rather than a fixed corner when a screen has a full-height nav rail docked at that corner.
**Status** logged (test-methodology note, not a code defect)

## Summary
- 4 routes × 6 combos = 24 combo/route cells, all clean: heading present, 0 console errors, 0 pageerrors, no dimmed primary controls, no horizontal overflow, rail counts populated within budget and internally consistent (feed's live count moved 22→25 mid-run from background scrape activity — not a stale/error value), health dot present, stubbed-500 produced a visible error state with 0 pageerrors, generic Escape-menu probe opened+closed cleanly, Tab×3 focus sequence identical across all 6 combos for each route (theme/skin does not affect DOM order or focusability).
- Alt skin (`light/alt`, `dark/alt`) showed no regressions distinct from default skin on any of the 10 checks across all 4 routes.
- Modal/menu inventory (light/default): 16 triggers probed across the 4 routes (Feed 5, Searches 3, Companies 5, Applications 3) — all opened, all closed on Escape, all closed on scrim/outside click once probed at a coordinate that actually lands on the scrim (see DS-S-01). R3-S-01 (Companies 1024px overflow) and R3-S-02 (Companies drawer scrim) both confirmed still fixed and holding on this round's HEAD (d23817c).
- File complete: all 4 routes covered, 6/6 combos each, modal inventories done, no P1/P2 found.


---

# Batch B smoke test — theme/skin pass

Read-only pass, no data mutations, no LLM calls, no rebuilds, no restarts. Repo v2-redesign branch, HEAD d23817c.
Scope: 4 routes — Résumés shelf, Résumé Editor (base "PM"), Résumé Editor (tailored copy), Cover Letters shelf.

Playwright inside the backend container against `http://caddy`, API key `pick-a-password`, harness `/tmp/v2t/h.py` + `/tmp/v2t/battB_common.py`. Theme via localStorage `jobnavigator_theme` (`light|dark`) and skin via `jobnavigator_skin` (`default|alt`) — legacy `jobnavigator_dark_mode` boolean set consistently alongside for the harness warm-up.

Matrix: 6 combinations per route — light/def 1440×900, dark/def 1440×900, light/def 1024×700, dark/def 1024×700, light/alt 1440×900, dark/alt 1440×900 (alt skin is 1440-only).

X-Frame-Options/CSP iframe-framing console noise ignored per instructions. Primary controls are auto-detected (top ~6 clickable elements in `main` near the top of the screen, deduped by label, capped to 5 in the printed list to match round3's display) — same algorithm as round3, extended this round with a "not dimmed" check (computed `opacity` ≥ 0.99, no `disabled`/`aria-disabled=true`, `pointer-events` ≠ none). Escape/Tab×3 are measured **per combination** this round (round3 measured them once at light-1440 only). Stubbed-500 endpoints: shelf routes use the actual list-fetching endpoint confirmed by request tracing (`/api/resumes/shelf` for the Résumés shelf — note this differs from the bare `/api/resumes` assumed in the task brief; `/api/cover-letters` bare, confirmed correct, for the Cover Letters shelf); editor routes use an exact per-id substring match.

---

## V2 Résumés (shelf)
`/v2/resumes`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | Résumés | Résumés | Résumés | Résumés | Résumés | Résumés | |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| primary controls (not dimmed) | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | ✔ [Search résumés, + New résumé, Persona · Decagon · Senior A, Persona · Brex · Staff Produ, Persona your full profile · ] | |
| no h-overflow | ✖ sw=1440 iw=1440 right=1532 | ✖ sw=1440 iw=1440 right=1532 | ✖ sw=1024 iw=1024 right=1116 | ✖ sw=1024 iw=1024 right=1116 | ✖ sw=1440 iw=1440 right=1532 | ✖ sw=1440 iw=1440 right=1514 | |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | |
| health dot | present | present | present | present | present | present | |
| stubbed-500 error state | ✔ nonblank=135 err_text=True pageerrors=0 | ✔ nonblank=135 err_text=True pageerrors=0 | ✔ nonblank=135 err_text=True pageerrors=0 | ✔ nonblank=135 err_text=True pageerrors=0 | ✔ nonblank=135 err_text=True pageerrors=0 | ✔ nonblank=135 err_text=True pageerrors=0 | |
| Escape closes menu/modal | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | |
| Tab×3 focus targets | A[Jobs 22] > A[Searches 7] > A[Companies 127] | A[Jobs 22] > A[Searches 7] > A[Companies 127] | A[Jobs 22] > A[Searches 7] > A[Companies 127] | A[Jobs 22] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | |

## V2 Résumé Editor (base: PM)
`/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | PM | PM | PM | PM | PM | PM | |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| primary controls (not dimmed) | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | ✔ [✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)] | |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | |
| rail counts (<1s) | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | |
| health dot | present | present | present | present | present | present | |
| stubbed-500 error state | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | |
| Escape closes menu/modal | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | |
| Tab×3 focus targets | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | DIV[› Header] > DIV[› Summary] > DIV[⌄ Experience (3)] | |

## V2 Résumé Editor (tailored copy)
`/v2/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager | |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| primary controls (not dimmed) | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | ✔ [The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b] | |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | |
| rail counts (<1s) | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | |
| health dot | present | present | present | present | present | present | |
| stubbed-500 error state | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | ✔ nonblank=1020 err_text=True pageerrors=0 | |
| Escape closes menu/modal | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | ✔ opened=True closed_esc=True | |
| Tab×3 focus targets | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | DIV[› Header] > DIV[› Summary ● changed by tailori] > DIV[⌄ Experience (3) ● changed by ] | |

## V2 Cover Letters (shelf)
`/v2/cover-letters`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | Cover Letters | Cover Letters | Cover Letters | Cover Letters | Cover Letters | Cover Letters | |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | |
| primary controls (not dimmed) | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search cover letters, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | |
| no h-overflow | ✖ sw=1440 iw=1440 right=1512 | ✖ sw=1440 iw=1440 right=1512 | ✖ sw=1024 iw=1024 right=1096 | ✖ sw=1024 iw=1024 right=1096 | ✖ sw=1440 iw=1440 right=1512 | ✖ sw=1440 iw=1440 right=1494 | |
| rail counts (<1s) | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '25', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | |
| health dot | present | present | present | present | present | present | |
| stubbed-500 error state | ✔ nonblank=400 err_text=True pageerrors=0 | ✔ nonblank=400 err_text=True pageerrors=0 | ✔ nonblank=400 err_text=True pageerrors=0 | ✔ nonblank=400 err_text=True pageerrors=0 | ✔ nonblank=400 err_text=True pageerrors=0 | ✔ nonblank=400 err_text=True pageerrors=0 | |
| Escape closes menu/modal | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | no modal/menu trigger on this screen (confirmed round3 — "Generate new" is an inline panel, not an overlay) | |
| Tab×3 focus targets | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | A[Jobs 25] > A[Searches 7] > A[Companies 127] | |

### V2 Résumés (shelf) — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + New résumé modal | ✔ | ✔ | ✔ | |

### V2 Résumé Editor (base) — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Tailor for a job… modal (standalone button) | ✔ | ✔ | ✔ | |
| ⋯ head menu (base) | ✔ | ✔ | ✔ | round3 (R3-S-03) had this NOT closing on Escape — now closes. Fix in 8804ae3 verified. |

### V2 Résumé Editor (tailored copy) — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| ⋯ head menu (tailored copy) | ✔ | ✔ | ✔ | round3 also had this NOT closing on Escape — now closes. Fix in 8804ae3 verified. |
| Re-tailor modal (via ⋯ menu > Re-tailor…) | ✔ | ✔ | ✔ | |
| Review changes modal (via ⋯ menu > Review changes) | ✔ | ✔ | ✔ | |

### V2 Cover Letters (shelf) — modal/menu inventory (light/default)

Confirmed still true: no modal/drawer/menu trigger on this screen. Menu-trigger probe (`[title="More actions"], [aria-haspopup="listbox"][role="button"]`) near the top of the page found 0 matches; "Generate new" remains an always-open inline panel (`CoverLetters.jsx`), not an overlay — nothing to open/close.

---

## Issues

### DS-S-11 · P1 · "+ New résumé" primary CTA button is horizontally clipped on the Résumés shelf
**Where** `frontend/src/v2/` Résumés shelf header toolbar (grep `frontend/src/v2/` for `New résumé` to find the component) — route `/v2/resumes`
**Repro** Load `/v2/resumes` at 1440×900 (either skin, either theme; also reproduces at 1024×700 scaled). Screenshot the header row (x:0-1440, y:0-100).
**Actual** The `.v2-ctl` div containing "+ New résumé" renders with `left=1405, right=1532` (127px wide) against a 1440px-wide `<main>` with `overflow-x:hidden`. Only the leftmost ~35px ("+ N") is visible before the ancestor's clip boundary; the rest of the label ("ew résumé") is silently clipped and invisible. Confirmed via screenshot (`battB_resumes_top.png`/`battB_resumes_full.png`): the button reads "+ N" on screen. `document.documentElement.scrollWidth` stays at 1440 (no page-level scrollbar reveals the clipped content) — automated `no h-overflow` check fails for all 6 combinations: `right=1532` (1440-wide combos, def+alt) / `right=1116` (1024-wide, def) / `right=1514` (dark/alt, 1440). Reproduces identically in dark, and in both default and alt skin, so it is not skin-specific — it's a base toolbar-layout regression.
**Expected** The button's full label should be visible and not clipped by its container, matching round3 (HEAD 69d36b1), where this exact check (`no h-overflow`, same methodology) passed clean (`✔ sw=1440 iw=1440 right=1440`) for this route at all 4 old combos. This is a regression introduced between round3 and the current HEAD (d23817c), most likely in the toolbar/header layout touched by this round's theme/skin design-consistency pass — not a deliberate design choice (a half-hidden primary CTA serves no design intent).
**Status** needs decision: is this a known regression from the header-layout changes in this round's pass, or did the search-input width change (see DS-S-12) push the button out of its flex budget? Either way this should be fixed before landing — it visibly breaks the primary "create résumé" action.

### DS-S-12 · P2 · Cover Letters shelf search `<input>` renders 72–102px wider than its container, spilling past the viewport (currently invisible to users but a real overflow)
**Where** `frontend/src/v2/` Cover Letters shelf header search box (grep `frontend/src/v2/` for `Search letters, companies` or the shared search-input component) — route `/v2/cover-letters`
**Repro** Load `/v2/cover-letters` at 1440×900 (either skin/theme). Inspect the `<input placeholder="Search letters, companies…">` box model: it sits inside a 178px-wide container (`left=1232, right=1410`) but the `<input>` itself computes to 280px wide (`left=1232, right=1512`), overflowing its own container by 102px and the 1440px viewport by 72px. A further ancestor (`overflow-x:hidden`, `position:relative`) clips the excess before it reaches `<main>`, so `document.documentElement.scrollWidth` stays at 1440 and nothing looks visually broken in a screenshot (placeholder text renders fully inside the visible 178px box; `battB_coverletters_top.png`/`_full.png` show no glitch).
**Actual** Automated `no h-overflow` check fails for all 6 combinations: `right=1512` (1440-wide, def+alt) / `right=1096` (1024-wide) / `right=1494` (dark/alt, 1440) — vs. round3's clean `✔ sw=1440 iw=1440 right=1440` for this same route.
**Expected** The `<input>`'s own box should not exceed its container's allocated width; even though currently invisible, an element quietly overflowing by 70-100px is latent breakage (a longer placeholder/value, a font-metric change under a different locale, or a future skin without the clipping ancestor could make it visible, and it silently defeats the container's intended width constraint). Given DS-S-11 shows a sibling toolbar item on a neighboring shelf route IS visibly broken by what looks like the same class of container/content-width mismatch, this is likely the same regression, just not manifesting visually here because an intermediate ancestor happens to clip it before the viewport edge.
**Status** needs decision: fix the input's width source (likely a hardcoded `width` on a shared search-input component that no longer matches its flex container after this round's header changes) — same root cause as DS-S-11 is worth checking first.

### DS-S-13 · P4 · "not dimmed" primary-controls check is clean across all 4 routes × 6 combos — no findings
**Where** N/A (negative finding, logged per instructions to record this round's new check ran and passed)
**Repro** N/A
**Actual** For every route × combo, all auto-detected top controls had `opacity` = 1 (no value `<0.99`), `pointer-events` ≠ `none`, `disabled` = false, and `aria-disabled` unset. No dimmed/disabled primary controls found anywhere in this batch.
**Expected** N/A — recorded for completeness since this was flagged as a new check this round.
**Status** logged (no action needed)

### DS-S-14 · P3 · Résumé Editor head menus gained a new leading control this round ("✦ Tailor for a job…" / "The one next step") — deliberate addition, not a defect
**Where** `frontend/src/v2/` Résumé Editor toolbar (base and tailored variants) — routes `/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a` and `/v2/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e`
**Repro** Compare round3's `primary controls` list (base: `[More, › Header, › Summary, ⌄ Experience (3), Résumé template]`; tailored: `[⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template]`) against this round's auto-detected list (base: `[✦ Tailor for a job…, More, › Header, › Summary, ⌄ Experience (3)]`; tailored: `[The one next step, More, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b]`).
**Actual** A new control appears first in both editors this round, and the "⋯" head-menu trigger now carries an explicit `title="More"` (previously just glyph text "⋯" with no accessible label detected by the earlier round). Both are present, clickable, and not dimmed in all 6 combos.
**Expected** This looks like a deliberate addition from the design-consistency pass (a "next step" prompt banner + a properly labeled menu trigger), consistent across every theme/skin/viewport combo tested — not a regression. Flagged per the "design deviations are decisions" rule for whoever reconciles round3 vs. this round's control lists.
**Status** needs decision: confirm intentional (looks correct) — no functional issue found.

### DS-S-15 · P4 · Two previously-logged Escape-close bugs (R3-S-03 and its tailored-copy counterpart) are now fixed and verified across all 6 combos
**Where** Résumé Editor "⋯"/"More" head menu — both base (`/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a`) and tailored copy (`/v2/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e`)
**Repro** Open the head menu, press Escape, confirm it closes. Tested once per combo (6×2 routes) plus the light/default modal-inventory pass.
**Actual** All 12 per-combo Escape checks report `opened=True closed_esc=True`; the light/default modal-inventory pass also shows `closed_esc=✔` for both. Round3 recorded `closed_esc=✖` for both menus (R3-S-03 and its tailored analogue).
**Expected** Escape should close an open menu — now does, in every combination tested, confirming the fix landed in 8804ae3 holds under the new theme/skin system too.
**Status** logged (verified fixed, no action needed)

### DS-S-16 · P4 · Rail counts, health dot, console/pageerrors clean across the full 6-combo matrix — no findings
**Where** N/A (negative finding)
**Repro** N/A
**Actual** All 4 routes × 6 combos: 0 console errors, 0 pageerrors, rail badge counts always non-empty/numeric (values legitimately drift between combos due to concurrent live background activity from another agent's parallel batch — not a bug), health dot present. Tab×3 focus order identical across all 6 combos per route (no skin/theme-dependent focus-order regressions).
**Expected** N/A — recorded for completeness.
**Status** logged (no action needed)

---

# Round-design smoke test — Batch C

Read-only pass, no data mutations, no LLM calls, no rebuilds, no restarts. Repo `v2-redesign`, HEAD d23817c.
Playwright inside the backend container against `http://caddy`, API key `pick-a-password`, harness `/tmp/v2t/h.py` + this batch's `/tmp/v2t/common_c.py`.
Theme/skin driven by localStorage `jobnavigator_theme` (`light|dark|system`) and `jobnavigator_skin` (`default|alt`); each combo's context is created with both the legacy `jobnavigator_dark_mode` key (via harness `theme=`) and the two new keys set explicitly (`extra_ls`).

Matrix: 6 combos — light/def 1440, dark/def 1440, light/def 1024, dark/def 1024, light/alt 1440, dark/alt 1440 (alt skin is 1440-only). Primary controls: top ~6 clickable elements in `main` within 420px of the top, deduped by label (auto-detected, same spirit as round 3's methodology, not a hand-curated list). "Not dimmed" (new this round) = computed `opacity` not `< 1` and no unexpected `disabled`/`aria-disabled` on those controls.

Routes covered: Cover Letter Editor (`/v2/cover-letters/ce44e1d4-2763-4088-99a4-2f71f8e68115`), Persona (`/v2/persona`), Stats (`/v2/stats`), Settings (`/v2/settings`).

---

## V2 Cover Letter Editor
`/v2/cover-letters/ce44e1d4-2763-4088-99a4-2f71f8e68115`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Scale — Senior AI Product Manager, Finance Agents" | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, More actions, ↓ Download PDF, Header, Recipient Scale · August 31,] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | identical label set across all 6 combos |
| controls not dimmed | ✔ all opacity 1, disabled=false, aria-disabled=null | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ same | ✔ sw=1024 iw=1024 right=1024 | ✔ same | ✔ sw=1440 iw=1440 right=1440 | ✔ same |  |
| rail counts (<1s) | ✔ 1ms — {'/v2/feed':'25','/v2/searches':'7','/v2/companies':'127','/v2/applications':'377','/v2/resumes':'6','/v2/cover-letters':'16'} | ✔ 2ms same | ✔ ~1ms same | ✔ ~1ms same | ✔ ~1ms same | ✔ ~1ms same | counts stable across combos |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=72 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | stubbed `**/api/cover-letters/ce44e1d4-...*` |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True (⋯ "More actions" menu) | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| Tab×3 focus targets | A[Jobs 19] > A[Searches 7] > A[Companies 127] | same | same | same | same | same | from a genuinely untouched fresh page load, the first 3 tab stops are the nav rail links (DOM-order-first); see note below |

### Cover Letter Editor — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Regenerate letter modal | ✔ | ✔ | ✔ |  |
| ⋯ head menu | ✔ | ✔ | ✔ |  |

## V2 Persona
`/v2/persona`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Persona" | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [› Header, ⌄ Contact / basics complete, › Summary, First name, Last name, ⌄ Experience (3)] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | identical across all 6 combos; "Contact / basics" renders pre-expanded so its `First name`/`Last name` inputs are within the top-6 window |
| controls not dimmed | ✔ all opacity 1, disabled=false, aria-disabled=null | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ same | ✔ sw=1024 iw=1024 right=1024 | ✔ same | ✔ sw=1440 iw=1440 right=1440 | ✔ same |  |
| rail counts (<1s) | ✔ 2ms — populated | ✔ 2ms | ✔ 2ms | ✔ 2ms | ✔ 2ms | ✔ 2ms | `/v2/feed` count drifted 22→19 across the run (other agents' parallel test data, per instructions) — not a defect |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=76 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | stubbed `**/api/persona*` |
| Escape closes menu/modal | ✖ opened=True closed_on_esc=False (enum Picker/Select, e.g. "Work authorization type") — closes on outside click instead | same | same | same | same | same | see DS-S-21 |
| Tab×3 focus targets | A[Jobs 22] > A[Searches 7] > A[Companies 127] | same pattern | same | same | same | same | nav rail links, matches round 3's pattern for other list screens |

### Persona — modal/menu inventory (light/default)

No dedicated modal/drawer/menu trigger — confirms round 3's finding that every section is an inline accordion with no overlay controls of that kind. However, this round's per-combo Escape check (above) surfaces that Persona's field-level **enum Pickers** (a thin wrapper over `ui.jsx`'s generic `Select`, used for every enum field — e.g. "Work authorization type", "Age range", "Disability status") *are* real `position:absolute` overlay dropdowns (zIndex 40), just not modals/menus in round 3's original sense:

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Enum Picker (Select) — "Work authorization type" | ✔ | ✖ | ✔ | generic `ui.jsx` `Select`: closes only via its own `document.addEventListener('click', ...)`, no `useEscape` |

**Note on Tab×3 vs round 3:** round 3 recorded `INPUT[] > TEXTAREA[] > TEXTAREA[]` for this screen. This run measures Tab×3 from a page that has had zero prior interaction (first script draft accidentally ran the Escape/menu probe *before* Tab×3 on the same page, which left the clicked "More actions" button holding DOM focus even after the menu closed — Tab from there landed mid-content; reordering to test Tab×3 first, before anything is clicked, corrected it) and gets the nav rail links, matching the pattern every other v2 list/shelf screen shows in round 3 (Feed, Searches, Companies, etc. all recorded `A[Jobs] > A[Searches] > A[Companies]`). Not logged as a numbered issue — consistent across all 6 combos (rules out a theme/skin regression) and consistent with the rest of the app; the round-3 divergence looks like that run's script also started from a non-neutral focus state on this screen and the Résumé Editor, not a real product difference.

## V2 Stats
`/v2/stats`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Stats" | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Reload every figure on this , Funnel, Flow] | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | only 3 clickable elements fall inside the top-420px auto-detect window this round (Refresh link + the funnel/score-distribution chart-kind toggles); consistent with round 3's smaller `[Reload every figure on this , ↻]` set |
| controls not dimmed | ✔ all opacity 1, disabled=false, aria-disabled=null | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ same | ✔ sw=1024 iw=1024 right=1024 | ✔ same | ✔ sw=1440 iw=1440 right=1440 | ✔ same |  |
| rail counts (<1s) | ✔ 2ms — populated | ✔ 2ms | ✔ 2ms | ✔ 2ms | ✔ 2ms | ✔ 2ms |  |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ (base `/api/stats` only) nonblank=4371 err_text=True pageerrors=0 | ✔ same | ✔ nonblank=4233 err_text=True pageerrors=0 | ✔ same | ✔ nonblank=4366 err_text=True pageerrors=0 | ✔ same | see full-failure note below |
| Escape closes menu/modal | ✖ opened=True closed_on_esc=False ("Type ▾" activity-log filter menu) — closes on outside click instead | same | same | same | same | same | see DS-S-22 |
| Tab×3 focus targets | A[Jobs 19] > A[Searches 7] > A[Companies 127] | same | same | same | same | same |  |

**Stubbing all 4 `/api/stats*` endpoints** (`/api/stats`, `/api/stats/timeline`, `/api/stats/score-distribution`, `/api/stats/sankey`), light/default 1440 only: `nonblank=4215 err_text=True pageerrors=0` — still a fully coherent, non-blank error banner state (KPI tiles show "—", charts marked unavailable, the `coreErr` red band with "Try again" appears), no white screen, no crash. **Finding**: stubbing only the base `/api/stats` path (as round 3 did, and as this round's per-combo rows above do) leaves `/api/stats/timeline`, `/score-distribution` and `/sankey` succeeding — the page still renders 3 of its 4 core data sources, so that narrower stub is a weaker test of the error path than it looks; the `err_text=True` in both cases comes from the same `coreErr` banner (triggered by `/api/stats` alone failing — `Stats.jsx`'s `get()` wrapper sets `anyFailed=true` per-endpoint and ORs them into one banner), not from a full-blackout state. Both scenarios render correctly either way — not a defect, just a note that a single-endpoint stub doesn't exercise a "everything failed" render path distinctly from a "one thing failed" one on this screen.

### Stats `#runs` deep link
- light/def 1440: `#runs` card found, top=92px, in view: ✔
- light/def 1024: `#runs` card found, top=92px, in view: ✔

### Stats — modal/menu inventory (light/default)

Round 3 recorded no modal/menu trigger for Stats ("read-only charts/tables plus a ↻ reload button"). **Not confirmed still true this round** — the Activity log tab (Run history / Activity log toggle on the `#runs` card) has a "Type ▾" filter `Menu` (`Stats.jsx` ~line 674-686) that round 3's top-of-screen probe never reached because it requires switching tabs first:

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Activity log "Type ▾" filter menu | ✔ | ✖ | ✔ | see DS-S-22 |

## V2 Settings
`/v2/settings`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Settings" | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search settings…, Jump to Appearance, Theme, Jump to Models, Jump to Scoring behavior, Skin] | ✔ same | ✔ [Search settings…, Jump to Appearance, Theme, Jump to Models, Jump to Scoring behavior, Jump to Tailoring] | ✔ same | ✔ same as 1440/def | ✔ same as 1440/def | the new "Appearance" section (Theme/Skin selects) is first, per D6 — at 1024px the section-nav sidebar reflows and the 6th auto-detected item is "Jump to Tailoring" instead of "Skin"; both are real, present controls, not a defect |
| controls not dimmed | ✔ all opacity 1, disabled=false, aria-disabled=null | ✔ | ✔ | ✔ | ✔ | ✔ |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ same | ✔ sw=1024 iw=1024 right=1024 | ✔ same | ✔ sw=1440 iw=1440 right=1440 | ✔ same |  |
| rail counts (<1s) | ✔ 2ms — populated | ✔ 2ms | ✔ 2ms | ✔ 1ms | ✔ 2ms | ✔ 2ms |  |
| health dot | present | present | present | present | present | present |  |
| stubbed-500 error state | ✔ nonblank=42 err_text=True pageerrors=0 | ✔ same | ✔ same | ✔ same | ✔ same | ✔ same | stubbed `**/api/settings*` |
| Escape closes menu/modal | ✔ opened=True closed_on_esc=True (Model catalog modal) | ✔ | ✔ | ✔ | ✔ | ✔ | R3-S-04 (Model catalog didn't close on Escape) — confirmed fixed live this round, all 6 combos |
| Tab×3 focus targets | A[Jobs 19] > A[Searches 7] > A[Companies 128] | same | same | same | same | same |  |

### Settings — modal/menu inventory (light/default)

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Settings Edit modal (Scoring rubric — first "kind: edit" row) | ✔ | ✔ | ✔ | round 3's "first row" was literally row 1; this build's Appearance section (Theme/Skin) is now first (D6), so the first *Edit-modal* row is "Scoring rubric" under Models |
| Model catalog modal | ✔ | ✔ | ✔ | R3-S-04 fix (8804ae3) verified live |

## Issues

### DS-S-21 · P3 · Persona's generic `Select` (enum Pickers) doesn't close on Escape
**Where** `frontend/src/v2/ui.jsx` `Select` (~line 301-341) — closes only via `document.addEventListener('click', ...)`, no `useEscape`; used throughout Persona's enum fields (`Persona.jsx`'s `Picker` wrapper, e.g. "Work authorization type", "Age range", "Disability status", "Sexual orientation", "Transgender?") and Settings' Theme/Skin/pair/llm rows, all via the same component. Route: `/v2/persona`.
**Repro** `/v2/persona` → expand "Work authorization" → click "Work authorization type" to open its dropdown → press Escape.
**Actual** Dropdown stays open (confirmed all 6 combos, light/dark × default/alt × both viewports where applicable). Clicking anywhere outside it does close it.
**Expected** Unclear whether this is a deliberate simplicity choice (a lightweight inline picker relying on click-outside, distinct from the app's modals/menus which all use `useEscape`) or an oversight — CoverLetterEditor's own custom "Cover letter template"/"Paper size" dropdowns (not built on this shared `Select`) DO close on Escape via that screen's local keydown handler, so the app is inconsistent on this point depending on which dropdown implementation a given screen happens to use. Not new to this round's skin work — `Select` predates the D6 theme/skin pass — but this is the first smoke pass to exercise it as an Escape-check target, since round 3 found no menu/modal trigger on Persona at all.
**Status** needs decision: should the shared `ui.jsx` `Select` gain Escape-to-close (bringing it in line with every modal/menu in the app), or is outside-click-only the intended behavior for this specific control type?

### DS-S-22 · P3 · Stats' Activity-log "Type ▾" filter menu doesn't close on Escape
**Where** `frontend/src/v2/Stats.jsx` ~line 674-686 — the `typeOpen` dropdown (a `Menu`/`MenuItem` list, same components used for menus elsewhere in the app that DO close on Escape) has only a `position:fixed` click-catching backdrop (`onClick={() => setTypeOpen(false)}`), no keydown listener. Route: `/v2/stats`.
**Repro** `/v2/stats` → Run history / Activity log card → click "Activity log" tab → click the "Type ▾" pill → press Escape.
**Actual** Menu stays open (confirmed all 6 combos). Clicking the backdrop closes it.
**Expected** Every other `Menu`-based dropdown found across v2 (Feed's Source/Sort menus, Companies'/Searches'/Applications' row menus, this Cover Letter Editor's "⋯" head menu) closes on Escape via a screen-level or component-level handler; this one is the exception. Same shape as round 3's R3-S-02/03/04 findings (all since fixed) — likely just missed rather than deliberate, but flagged needs-decision per instructions rather than assumed.
**Status** needs decision: should this menu's Escape-to-close be added for consistency with the rest of the app's `Menu` usages, or is a plain backdrop-only close intentional here?

### DS-S-23 · P4 · Round 3's "no modal/menu trigger" note for Stats was incomplete, not stale
**Where** `frontend/src/v2/Stats.jsx` — the Activity-log "Type ▾" filter menu (same trigger as DS-S-22).
**Repro** N/A — documentation note, not a UI defect.
**Actual** Round 3's `smoke.md` states "Stats — modal/menu inventory: No modal/drawer/menu trigger found — the screen is read-only charts/tables plus a ↻ reload button; no overlay controls." This round found one real overlay-control trigger (DS-S-22) that predates this round's skin work — it was reachable only after switching the `#runs` card to its "Activity log" tab, which round 3's top-of-screen auto-probe never did.
**Expected** No code change implied; noting for the test record so a future pass doesn't re-report "confirmed still true" without re-checking the Activity log tab specifically.
**Status** logged, informational only.



---

# Batch D — Toast Lab, UI Gallery, theme/skin cross-cutting verification

Repo `V:\JTrakProject`, branch `v2-redesign`, HEAD d23817c. Playwright inside the
`backend` container against `http://caddy`, API key `pick-a-password`. Reused
`v2-testing/tools`-style shared harness already deployed for this round at
`/tmp/v2t/battB_common.py` (6-combo matrix, `toolbar_controls`/dimmed detection,
`overflow_check`, `escape_only_probe`, `tab_three`) for methodology parity with
sibling batches A/B. Scripts used: `/tmp/v2t/battD_1.py` (Part 1 matrix),
`battD_2a.py` (gallery switcher), `battD_2b.py` (rail cycle + persistence),
`battD_2c.py`/`battD_2c2.py` (Settings Appearance live switching),
`battD_2d.py` (v1-follows-v2 no-reload proof), plus ad-hoc `battD_dbg*.py`
CSSOM-inspection scripts used to chase down DS-S-31 below.

Legend: check rows are per column light/def 1440 / dark/def 1440 / light/def 1024
/ dark/def 1024 / light/alt 1440 / dark/alt 1440. X-Frame-Options/CSP iframe
console noise ignored per instructions. Both routes are rail-less by design —
rail-count and health-dot rows are omitted per the task scope.

## V2 Toast Lab
`/v2/toasts`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Toast lab" | ✔ "Toast lab" | ✔ "Toast lab" | ✔ "Toast lab" | ✔ "Toast lab" | ✔ "Toast lab" | h1, from ToastLab.jsx |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Primitives ›, Theme: Light, paper card + spinner · 2.5s, same plural form, green tint + ✓ roundel, success with an action] | ✔ [Primitives ›, Theme: Dark, …] | ✔ [same] | ✔ [same] | ✔ [same, Theme: Light] | ✔ [same, Theme: Dark] | none dimmed (opacity 1, no disabled/aria-disabled) in any combo |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 |  |
| stubbed-500 error state | N/A (no API dependency) confirmed via source — `grep -n "fetch(\|axios\|api\.\|useEffect\|import.*api"` on `ToastLab.jsx` returns nothing; the page only calls the in-memory `useToasts()` hook | | | | | | |
| Escape closes menu/modal | N/A — no modal/menu/Menu/Select on this route, confirmed via source (ToastLab.jsx renders only toast-sample `<div onClick>` cards, a theme-cycle `<div>`, and the `ToastStack`; no `Menu`/`ModalPanel`/`Drawer`/`Select` import) | | | | | | |
| Tab×3 focus targets | A[Primitives ›] › BODY › A[Primitives ›] (identical in all 6 combos) | | | | | | See DS-S-33: only the "Primitives ›" `<a>` is a real tab stop on this page — the theme-cycle div and every toast-sample/Fire-all/Clear div are plain `onClick` without `kb()`/tabIndex, so Tab wraps straight back to it |

## V2 UI Gallery
`/v2/ui`

| check | light/def 1440 | dark/def 1440 | light/def 1024 | dark/def 1024 | light/alt | dark/alt | note |
|---|---|---|---|---|---|---|---|
| heading present | ✔ "Primitives" | ✔ "Primitives" | ✔ "Primitives" | ✔ "Primitives" | ✔ "Primitives" | ✔ "Primitives" | h1 via `PageTitle` |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Skin: default, Skin: alt, Theme: Light, Theme: Dark, System — currently light, Toast lab ›] | ✔ [same, System — currently dark] | ✔ [same] | ✔ [same] | ✔ [same] | ✔ [same] | none dimmed in any combo |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 |  |
| stubbed-500 error state | N/A (no API dependency) confirmed via source — same grep on `UiGallery.jsx` returns nothing; the page is 100% local React state (`useState`) driving static primitive samples | | | | | | |
| Escape closes menu/modal | ✔ opened=True closed_esc=True (all 6 combos) | | | | | | Tested the live `ModalPanel` ("Open modal" button, `useEscape`). Also separately confirmed the `Drawer` ("Open drawer") closes on Escape: opened=True closed_esc=True. By contrast the page's live `Select` dropdowns (e.g. the "Provider" sample) do **not** close on Escape — only outside click (`document.addEventListener('click', …)` in `ui.jsx` `Select`, no `useEscape`) — see DS-S-32. The gallery's static `Menu`/`MenuItem` blocks are inert, always-rendered swatches, not popovers, so they were excluded from this check as instructed |
| Tab×3 focus targets | SPAN[Toast lab ›] › DIV[Skin: default] › DIV[Skin: alt] (identical in all 6 combos) | | | | | | Real tab order confirmed clean (ran a 15-deep debug pass): NavLink → Skin pills → Theme pills → Button role samples → … Ordering is normal; the shorter 3-deep table above matches this |

Gallery card count (2a first bullet, folded in here since it's the same route):
19 `<section>` blocks (the `Role()` wrapper is the per-primitive "card" unit on
this page — there is no `v2-card` class in `UiGallery.jsx`, contra the generic
`v2-card` name used elsewhere in the app), 0 console errors, 0 pageerrors.

## Theme/skin cross-cutting verification

### /v2/ui gallery + switcher

Primitive render count: **19** `Role()` sections rendered, 0 console/pageerrors
— every primitive block in `ui.jsx`'s import list has a corresponding block in
`UiGallery.jsx` (Button, Pill, IconButton, Input·Textarea, SearchInput, Select,
Row, Card·Band, DashedAdd, Menu·MenuItem, SectionHead, Chip, Tag·Dot,
Link·NavLink, RemoveLink·RemoveX·MoveArrows, HeaderRow, ModalPanel·Drawer,
Label·Helper·Heading·PageTitle, Spinner·ShowMore = 19 `Role` calls in source,
matching the DOM count exactly).

Cycled the switcher **by clicking its own Pills** (not localStorage) through
light/default → dark/default → dark/alt → light/alt → back to light/default:

| step (click) | html `data-theme` | html `data-skin` | `.jn-v2` root `data-theme`/`data-skin` | console/pageerrors | Button bg | Pill bg |
|---|---|---|---|---|---|---|
| initial (light/default) | light | default | light / default | 0 / 0 | `rgb(63,107,82)` | `rgb(255,255,255)` |
| Theme: Dark → dark/default | dark | default | dark / default | 0 / 0 | `rgb(141,187,159)` | `rgb(40,37,27)` |
| Skin: alt → dark/alt | dark | alt | dark / alt | 0 / 0 | `rgb(154,171,238)` | `rgb(29,34,43)` |
| Theme: Light → **light/alt** | light | alt | light / alt | 0 / 0 | **`rgb(63,107,82)`** (unchanged) | **`rgb(255,255,255)`** (unchanged) |
| Skin: default → light/default | light | default | light / default | 0 / 0 | `rgb(63,107,82)` | `rgb(255,255,255)` |

(a) no page/console error at any step — confirmed clean throughout.
(b) `<html>` and the `.jn-v2` root attrs tracked each other exactly at every
step (no divergence between the boot copy and the React-mirrored copy).
(c) sampled computed colors differ between combos **except** light/alt, which
is pixel-identical to light/default for both the sampled Button and Pill —
traced to a real bug, **DS-S-31** below (this is the P1 headline finding of
this batch).

### Rail ◐ cycle + persistence

`/v2/feed`, fresh page, light/default, 1440×900. Rail was in its default
"expanded" state (`.v2-themebtn` visible). Clicked the ◐ control 3×:

| click | icon | title | html `data-theme` |
|---|---|---|---|
| (initial) | ◐ | Theme: Light — click to switch | light |
| 1 | ◑ | Theme: Dark — click to switch | dark |
| 2 | ◒ | Theme: System — click to switch | light *(resolved — headless Chromium has no `prefers-color-scheme: dark`, so System correctly resolves to light here)* |
| 3 | ◐ | Theme: Light — click to switch | light |

Sequence confirmed **Light → Dark → System → Light**, icon and tooltip both
updating in lock-step at every click, matching `cycleMode()`'s documented order
and `themeTitle()`'s exact string format. ✔ no deviation.

**Persistence**: clicked ◑ once (Light → Dark), then `pg.reload()`.
`localStorage.getItem('jobnavigator_theme')` was `dark` immediately after the
click and **still `dark` after reload**; the rail button read "Theme: Dark"
and `data-theme="dark"` post-reload. ✔ persists correctly.

*(Methodology note: the first pass of this check used the shared harness's
`get_page()` helper, whose `extra_ls` is injected via Playwright
`addInitScript` — which re-runs on **every** navigation including `reload()`.
That produced a false "reverts to light on reload" reading, because the test
harness itself was re-stamping `jobnavigator_theme` back to its start value
before `index.html`'s boot script ran. Re-ran with the harness's plain,
un-parameterized `page()` — which only seeds the legacy `jobnavigator_dark_mode`
key, not `jobnavigator_theme` — so the real app code path was what got
exercised across the reload. Flagging this so anyone re-running this batch's
persistence check doesn't reuse `get_page()`+`reload()` and mistake a
harness artifact for a real regression.)*

### /v2/settings Appearance — live switching

`/v2/settings`, light/default, 1440×900. Found the Appearance section (`GENERAL`
group, "theme and skin — remembered in this browser, not in the database"),
`Select`s with `aria-label="Theme"` / `aria-label="Skin"`.

**Theme select** (Light ⇄ Dark), via UI clicks only, no reload:

| pick | html `data-theme` | `<h1>` computed color | console/pageerrors |
|---|---|---|---|
| Dark | dark | `rgb(217,215,208)` | 0 / 0 |
| Light | light | `rgb(27,26,22)` | — |

Applies immediately, no reload needed. ✔

**Skin select** (Default ⇄ Alt), in **light** mode:

| pick | html `data-skin` | `<h1>` computed color | console/pageerrors |
|---|---|---|---|
| Alt | alt | `rgb(27,26,22)` (**unchanged** from Default) | 0 / 0 |
| Default | default | `rgb(27,26,22)` | — |

The `data-skin` attribute updates correctly and instantly (no reload), but the
visible color is unchanged in light mode — the same DS-S-31 bug reproduced on
a second, unrelated screen and a second token (`--text`, not just `--accent`).

**Confirmed the skin select DOES work correctly in dark mode** (isolating the
bug to light+alt specifically, not to the Settings Select control): same
picker, dark/default → dark/alt, `<h1>` color `rgb(217,215,208)` →
`rgb(214,218,226)` — a real, visible change. ✔ for dark; ✖ for light (DS-S-31).

### v1 pages follow the v2 theme toggle

Used the **live toggle** path end-to-end, and proved zero full-page reload
occurred anywhere in the flow by planting `window.__jn_no_reload_marker` right
after the first load and reading it back at every step (a real document reload
wipes the JS heap and the marker would vanish — it never did):

1. Loaded v1 `/` fresh, light/default. `main` bg `rgb(249,250,251)` (light),
   `<html>` has no `.dark` class.
2. Clicked the real `<NavLink to="/v2/feed">` "Try v2 (beta)" in the v1
   sidebar (client-side React Router nav, not a plain `<a>` — confirmed no
   reload via the marker).
3. On `/v2/feed`, clicked the rail's ◐ theme-cycle control once (live click,
   light → dark).
4. `pg.go_back()` (browser back — since the v1→v2 hop was a client-side
   `pushState`, back navigation stays client-side too) landed back on v1 `/`
   **without a reload** (marker intact) — and it was already dark:
   `html.classList.contains('dark') === true`, `data-theme="dark"`,
   `main` bg `rgb(17,24,39)`.
5. Clicked the v1 Settings `NavLink` (`a[href="/settings"]`, client-side) —
   v1 `/settings` was also dark: same `.dark` class, same dark `main` bg.
6. Clicked v1's own "Light Mode" toggle button (the classic shell's own
   `useTheme()`-backed toggle, per `App.jsx`) — flipped instantly back to
   light, no reload, still on `/settings`.
7. Clicked the v1 "Jobs" `NavLink` back to `/` — light there too.

✔ **Confirmed**: one click in the v2 rail moved the v1 classic shell's `.dark`
class and computed background instantly on both v1 `/` and v1 `/settings`,
with no reload anywhere in the round trip (the `__jn_no_reload_marker` value
`"set-at-v1-start"` was still present at every single step) — exactly the
SHELL-02/SHELL-06 contract `theme.js` documents. Flipping back to light via
v1's own toggle propagated correctly too. This is the one check in this batch
that came back **fully clean** with no caveats.

## Issues

### DS-S-31 · P1 · light+alt skin renders pixel-identical to light+default — the `.jn-v2[data-skin="alt"]` CSS rule is missing from the built stylesheet
**Where** `frontend/src/v2/theme.css:328` (source rule `.jn-v2[data-skin="alt"] { --bg:#f7f8fa; …; --accent:#3f52a8; … }`); manifests on every `.jn-v2` route, reproduced concretely on `/v2/ui` and `/v2/settings`. Served bundle: `http://caddy/assets/index-4NrmD17B.css`.
**Repro**
1. Load any v2 route in light mode, default skin.
2. Switch skin to Alt while staying in light mode (via `/v2/ui`'s Skin pills, or `/v2/settings` → Appearance → Skin select — both reproduce it).
3. Observe: `data-skin="alt"` is correctly applied to both `<html>` and the `.jn-v2` root (the JS/React side of D6 is 100% correct), but every sampled computed color is unchanged from light+default.
4. Switch to dark mode and repeat: skin Alt *does* change colors correctly (`.jn-v2[data-skin="alt"][data-theme="dark"]` works).
5. Root cause, confirmed by direct CSSOM inspection (`document.styleSheets[…].cssRules`): the raw served CSS file bytes *do* contain the correct, syntactically-clean `.jn-v2[data-skin="alt"]{...}` rule (verified via `curl`/`urllib` fetch of the asset, byte-inspected around offset 13187 — no stray characters, balanced braces, straight ASCII quotes), but the **browser's parsed stylesheet has no such rule at all** — `sheet.cssRules` goes straight from `.jn-v2[data-theme="dark"]` (index 1) to `.jn-v2[data-skin="alt"][data-theme="dark"]` (index 2), skipping the plain `.jn-v2[data-skin="alt"]` rule entirely. This smells like a CSS build/minification step (Vite's CSS pipeline) dropping or de-duplicating the rule — possibly mistaking it for redundant against the more specific `[data-skin="alt"][data-theme="dark"]` rule that immediately follows it in source — rather than a source-code typo, since the source file on disk is correct.
**Actual** Light+alt: `--accent` stays `#3f6b52` (default green) instead of `#3f52a8` (alt indigo); Settings `<h1>` color stays `rgb(27,26,22)` instead of the alt light `--text` (`#161a21` → `rgb(22,26,33)`); sampled Button/Pill backgrounds on `/v2/ui` identical between light/default and light/alt. Dark+alt is unaffected and correct.
**Expected** Per `theme.js`'s own header comment and the D6 gate doc it cites (`v2-testing/round-design/expected-D6.md`): "switching data-skin may change colour and font family and nothing else" — for **both** resolved themes. Right now switching to Alt while in Light mode is a complete no-op visually; a user who tries the Alt skin while in light mode (the default mode) will conclude the whole feature does nothing.
**Status** needs decision: this is a build-pipeline defect (missing/dropped CSS rule), not a design deviation — recommend someone with a local Node toolchain diff the built CSS against a fresh `docker compose build frontend` (out of scope for this read-only pass — no rebuilds performed) to confirm whether re-building fixes it, and if so treat it as a stale-artifact issue for this deployed instance rather than a source bug; if a rebuild reproduces it too, look at whichever CSS minifier/optimizer Vite is configured with for `mergeRules`/duplicate-selector logic.

### DS-S-32 · P4 · `Select` dropdown (ui.jsx) doesn't close on Escape, unlike ModalPanel/Drawer
**Where** `frontend/src/v2/ui.jsx:301-360` (`Select` component — closes only via a `document.addEventListener('click', …)` outside-click handler, no `useEscape`); observed on `/v2/ui`'s "Provider" sample select, and applies to every `Select` in the app including the Settings Appearance Theme/Skin pickers used above.
**Repro** On `/v2/ui`, click the "Provider" select to open its listbox (a real `position:absolute` popover, confirmed via the same overlay-detection z-index/position heuristic used for the ModalPanel/Drawer checks — `opened=True`), then press Escape.
**Actual** `closed_on_escape=False` — the listbox stays open; only clicking outside closes it. `ModalPanel`/`Drawer` on the same page both close correctly on Escape (`useEscape`, confirmed `opened=True closed_esc=True` in all 6 combos).
**Expected** Not a D6/theme-specific contract, but the gallery's own text calls out keyboard operability ("Tab into a sample; fields turn their border accent… other controls take the `[tabindex]` ring"), and every other dismissible overlay on this page (Modal, Drawer) is Escape-closeable. Worth deciding whether `Select` should gain the same `useEscape` treatment for consistency — it's a pre-existing gap, not something D6 introduced or touched.
**Status** needs decision: should `Select`'s popover close on Escape like `ModalPanel`/`Drawer` do?

### DS-S-33 · P4 · ToastLab.jsx's own controls aren't keyboard/Tab reachable
**Where** `frontend/src/v2/ToastLab.jsx` — the theme-cycle `<div onClick={theme.cycle} …>` (no `kb()`/tabIndex spread), the 8 per-sample toast trigger `<div onClick={...}>`s, and the "Fire all"/"Clear" `<div onClick={...}>`s all use a bare `onClick` without the `act()`/`kb()` helper that the rest of `ui.jsx`'s primitives use to get `tabIndex=0` + keyboard activation.
**Repro** On `/v2/toasts`, focus the document body and press Tab 3×.
**Actual** Tab sequence is `A[Primitives ›] → BODY → A[Primitives ›]` in all 6 combos — the only real tab stop on the entire page is the "Primitives ›" navlink (an actual `<a>`); every other control on the page is mouse-only.
**Expected** Every other page in this app builds its clickable controls from `ui.jsx` primitives (which all carry `kb()`), so this is an outlier. However, `ToastLab.jsx`'s own header comment says: "TEMPORARY debug page… delete this file and its route when the taxonomy is signed off" — it was never meant to be a finished, accessible screen.
**Status** needs decision: low priority given the page's explicitly-temporary status — worth a `kb()` pass only if the page survives longer than planned, otherwise moot once it's deleted.

---

## Cross-batch notes

- **DS-S-21 (Batch C, Persona) and DS-S-32 (Batch D, /v2/ui gallery)** are the same underlying defect found independently on two different screens: the shared `Select` primitive (`ui.jsx`) doesn't close its popover on Escape, unlike `ModalPanel`/`Drawer` (`useEscape`). Treat as one fix, two confirmations.
- **DS-S-11 (Batch B) and DS-S-31 (Batch D)** were independently re-verified by the orchestrating session after both batches reported them (see below) — both are real, not test-harness artifacts.

## Independent verification (orchestrator, post-batch)

Two P1 findings were spot-checked directly against the live stack before accepting them into this report:

- **DS-S-11** — confirmed via a standalone script: the "+ New résumé" control is a `DIV` at `left=1405, right=1532` inside a 1440px-wide, `overflow-x:hidden` ancestor whose own row only extends to `right=1410`; a screenshot (`/v2/resumes`, light/default, 1440×900) shows the button rendering as "+ N" with the rest of the label clipped off-screen.
- **DS-S-31** — confirmed via direct `document.styleSheets` inspection: `getComputedStyle(.jn-v2)['--accent']` returns `#3f6b52` (default skin's green) in light+alt instead of `#3f52a8` (alt skin's blue, present verbatim in the served CSS text at byte offset ~13180 of `index-*.css`). Scanning parsed CSSOM rules matching `.jn-v2` + `data-skin="alt"` found only the combined `.jn-v2[data-skin="alt"][data-theme="dark"]` rule — the standalone `.jn-v2[data-skin="alt"]` rule exists in the raw served CSS bytes but is absent from the browser's parsed stylesheet, despite `.jn-v2{}` (specificity 0,1,0, unconditional light default) appearing earlier in the same file and no `.jn-v2[data-theme="light"]` override existing to explain it by cascade order. Root cause not diagnosed further (out of scope for a smoke pass) — looks like a CSS minifier/bundler dropping a rule during the build, not a source-level typo, since the correct text is present in the shipped bytes.

## Overall summary

- **Coverage:** 14 route/variant sections (13 v2 screens per the brief's count — Feed, Searches, Companies, Applications, Résumés shelf, Résumé Editor ×2 (base + tailored), Cover Letters shelf, Cover Letter Editor, Persona, Stats, Settings, Toast Lab — plus `/v2/ui`, new this round), each across the 6-combo matrix (light/dark × default/alt skin, 1440×900 + 1024×700 for default, 1440-only for alt) = up to 84 combo-cells per route, 10 checks per cell on data-bearing routes.
- **Console/pageerrors:** 0 across every route, every combo, both the normal-load and stubbed-500 passes.
- **Horizontal overflow:** clean everywhere except the two DS-S-11/DS-S-12 findings on the Résumés shelf and Cover Letters shelf (both P1/P2, both reproduce identically across all 6 combos — not skin/theme-specific, a base layout regression since round 3).
- **"Not dimmed" (new this round):** clean on every route in every combo — no washed-out/disabled-looking interactive controls found.
- **Alt skin:** correctly applies in **dark** mode everywhere tested; **completely inert in light mode** (DS-S-31, P1) — light+alt renders identical to light+default because the browser drops the standalone `.jn-v2[data-skin="alt"]` CSS rule from its parsed stylesheet, even though the byte-correct rule ships in the served CSS. This is the single most important finding of this round, since it undermines the "alt skin" launch as currently built for exactly half its matrix (light+alt).
- **Theme system (D6) correctness — otherwise solid:** rail ◐ cycles Light→Dark→System→Light with matching icon/tooltip at every step and persists across reload; `/v2/settings` Appearance section switches mode and (dark-mode) skin live with no reload; `/v2/ui`'s own switcher cycles all 4 combinations without a page error and its gallery renders every primitive sample (count > 0, 0 errors); v1 `/` and `/settings` both provably follow a v2 theme toggle with zero reload (SHELL-02/SHELL-06 confirmed by a JS-heap marker surviving the round trip).
- **Regressions vs. round 3, confirmed fixed:** R3-S-01 (Companies 1024px overflow), R3-S-02 (Companies drawer scrim-click), R3-S-03 ×2 (Résumé Editor head menu Escape, base + tailored), R3-S-04 (Settings Model catalog Escape) — all verified fixed live on this round's HEAD across all 6 combos where applicable.
- **New regressions vs. round 3 (not skin/theme-caused, but discovered by this pass):** DS-S-11 (P1, Résumés shelf CTA clipped) and DS-S-12 (P2, Cover Letters shelf search input latent overflow) — both routes were clean on this exact check in round 3, so these are base layout regressions introduced since HEAD 69d36b1, independent of the theme/skin work itself.
- **Findings by severity:** P1 ×2 (DS-S-11, DS-S-31) · P2 ×1 (DS-S-12) · P3 ×3 (DS-S-14 needs-decision, DS-S-21, DS-S-22) · P4 ×7 (DS-S-01, DS-S-13, DS-S-15, DS-S-16, DS-S-23, DS-S-32, DS-S-33). 13 issues total, DS-S-01 through DS-S-33 (ranges reserved per batch: A 01-10, B 11-20, C 21-30, D 31-40; not all reserved numbers were used).
- **Scratch data:** none created by this pass (read-only). `ZZA`/`ZZB` rows from parallel flow agents were visible in list snapshots on several routes and left untouched, per instructions.
- **Don't-fix reminder:** per the task brief this was a verification-only pass — nothing above was fixed in source.

---

## Fixes (source, unbuilt)

Source-only pass on the findings above. No rebuild, no restart, no commit — the
built bundle still carries the old code, so every claim below is verified against
the *source* (esbuild parse/minify, `stylelint.py`, brace balance) plus live DOM
experiments that patched the running page to prove the layout fix before it was
written. Fixed on branch `v2-redesign`, working tree only.

| DS id | file:line | change |
|---|---|---|
| DS-S-31 (P1) | `frontend/src/v2/theme.css:318` (plus a new guard note at `:324`) | The alt-skin block's header comment said `Deliberately NOT re-skinned: --cc-*/--sm-* …`. The `*` of the `--cc-*` glob and the `/` before `--sm-*` spell a literal comment terminator, which **closed the comment 15 lines early**. The surviving prose then parsed as a selector prelude that swallowed the `.jn-v2[data-skin="alt"]` selector and its whole block. Rewrote the two globs as prose (`the --cc- and --sm- families`) and added a note saying why it must never be re-globbed. |
| DS-S-11 (P1) + DS-S-12 (P2) | `frontend/src/v2/ui.jsx:295` (`SearchInput`; comment at `:287`) | Wrapper `<span>` went from `flex: width ? '0 0 <width>' : '0 1 226px'` to `width: width || 226, flex: '0 1 auto'` (`minWidth: 0` kept). One shared-component change fixes both shelves. |
| DS-S-21 (P3) + DS-S-32 (P4) | `frontend/src/v2/ui.jsx:311-336` (`Select`) | The open-listbox effect now also registers a **capture-phase** `keydown` on `document` that, on Escape, calls `preventDefault()` + `stopPropagation()` and closes the listbox. Closed, nothing is registered and Escape falls through to a parent modal. |
| DS-S-01, DS-S-13, DS-S-14, DS-S-15, DS-S-16, DS-S-23 | — | No code change. DS-S-01/13/15/16/23 are negative or test-methodology findings; DS-S-14 is a confirmed-deliberate addition. |
| DS-S-22 (P3) | `frontend/src/v2/Stats.jsx` ~674-686 | **Not fixed** — outside this pass's scope (a P3 needs-decision in a screen file, not `ui.jsx`). It is a one-liner once someone decides: `useEscape(() => setTypeOpen(false), typeOpen)`. |
| DS-S-33 (P4) | `frontend/src/v2/ToastLab.jsx` | **Not fixed** — not a `ui.jsx` one-liner (it needs a `kb()`/`act()` pass over ~11 separate `<div onClick>`s), and the file's own header marks the page as temporary. Left as logged. |

### DS-S-31 — root cause, precisely

Not a minifier bug and not a stale artifact. `theme.css:318` read:

```
   Deliberately NOT re-skinned: --cc-*/--sm-* (the ATS and search-mode badge
```

The `*` ending the `--cc-*` glob and the `/` that followed it form a comment
terminator, so the block comment that opened at `theme.css:302`
(`/* -- Skin: alt (design pass D6) ---`) **ended there** instead of 15 lines
later. Everything after it — `--sm-* (the ATS … leak a light colour into the dark
skin. */ .jn-v2[data-skin="alt"]` — became one unparseable selector prelude, and
the browser discarded that prelude *together with the `{…}` block it introduced*.
That block was the alt light palette. The next rule,
`.jn-v2[data-skin="alt"][data-theme="dark"]`, starts a fresh prelude and parses
normally — which is exactly why alt worked in dark and was inert in light.

This also resolves the report's puzzle that the correct bytes ship in the served
CSS while the parsed `cssRules` has no such rule: the *text* is present and
byte-clean, but it is not the start of the rule — the dead comment tail in front
of it is, and that is what the parser choked on. Nothing was dropped, merged or
de-duplicated by the build.

Reproduced and verified with the command the task names:

```
npx esbuild@0.21.5 frontend/src/v2/theme.css --minify --loader:.css=css
```

- **Before:** esbuild emits `▲ [WARNING] Unexpected "*" [css-syntax-error] theme.css:318:44`, and the minified output contains
  `…--focus-ring:var(--ring-accent)}--sm-* (the ATS … */ .jn-v2[data-skin="alt"]{--bg:#f7f8fa;…}` — the comment prose is *inside* the selector.
- **After:** 0 warnings, no prose in the output, and the four rules appear in this order with this specificity:

| # | selector | specificity |
|---|---|---|
| 0 | `.jn-v2` (light default) | 0,1,0 |
| 1 | `.jn-v2[data-theme=dark]` | 0,2,0 |
| 2 | `.jn-v2[data-skin=alt]` | 0,2,0 |
| 3 | `.jn-v2[data-skin=alt][data-theme=dark]` | 0,3,0 |

Alt-light (2) beats base-light (0) on specificity; alt-dark (3) beats both
base-dark (1) and alt-light (2). Rule 2 sits *after* rule 1 at equal specificity,
so in dark+alt any token rule 2 sets that rule 3 forgets would leak a light
colour — the hazard the source comment already warns about, and which was latent
for as long as the rule was being dropped. Re-checked: **both alt blocks declare
an identical set of 57 custom properties**, no light-only or dark-only names, so
nothing leaks.

### DS-S-11 / DS-S-12 — root cause, precisely

One defect in the shared `SearchInput`, surfacing twice. `ui.jsx` sized the
wrapper `<span>` with `flex: 0 0 <width>` — a flex-*basis*, with no `width`
property. A flex item's **intrinsic contribution** to its parent's `max-content`
size is measured from its *content*, not from its flex-basis, and the content
here is a bare `<input>` whose default intrinsic width is ~178px. So:

- **Résumés** — the actions group (`flex: 0 1 auto`, basis `auto` → max-content)
  measured `178 (span) + 10 (gap) + 127 (Button) = 315px` and was laid out 315px
  wide, right-aligned to the header's 1410px content edge. Inside it the span
  then took its inflexible 300px basis and overflowed by 122px, pushing the
  Button — already correctly `flex: 0 0 auto; whiteSpace: nowrap` — out to
  `left=1405, right=1532`, past `<main>`'s `overflow-x:hidden`. Measured live:
  group `width=315` but `scrollWidth=437`. The 315px was **not** a space
  shortage — the header had 477px of free space at 1440. Setting the group to
  `flex: 0 0 auto` changed nothing, which is what ruled out a shrink problem and
  pointed at intrinsic sizing.
- **Cover Letters** — the same arithmetic with no Button: group = `178px`, the
  span inside laid out at its 280px basis, overflowing by exactly the 102px the
  report measured. Nothing was visibly clipped only because an ancestor clips it
  first.

Giving the wrapper a real `width` makes its contribution equal the declared
width, so the group measures the full `300 + 10 + 127 = 437`; `flex: 0 1 auto` +
`minWidth: 0` then keeps the *field* (never the button) as the thing that yields
when the header genuinely runs out of room.

Validated by patching the live DOM on the running (pre-fix) bundle — read-only,
no rebuild — applying exactly this style change and re-measuring the furthest
right edge under `main`:

| route | viewport | before | after |
|---|---|---|---|
| `/v2/resumes` | 1440 | 1532 | **1440** |
| `/v2/resumes` | 1024 | 1116 | **1024** |
| `/v2/cover-letters` | 1440 | 1512 | **1440** |
| `/v2/cover-letters` | 1024 | 1096 | **1024** |
| `/v2/feed` | 1440 / 1024 | 1440 / 1024 | 1440 / 1024 (unchanged) |
| `/v2/companies` | 1440 / 1024 | 1440 / 1024 | 1440 / 1024 (unchanged) |

On `/v2/resumes` the button lands whole at `1283–1410` (1440) and `867–994`
(1024) with the search field keeping its full 300px, and it still holds at 860px.
Field widths on Feed and Companies are unchanged at 226px, so the two boxed
filter-bar users are unaffected.

**Other screen headers checked for the same pattern** — Companies
(`Companies.jsx:397/411`), Applications (`Applications.jsx:330/345`), Searches
(`Searches.jsx:560`) and Feed (`JobFeed.jsx:722/733`) do **not** pair a search
with a button in one header row: each puts its `+ …` Button alone in the title
`HeaderRow` and its search in a separate toolbar row. Applications' toolbar uses
its own `v2-fieldwrap` (`flex: 0 1 210px` + `minWidth: 0` — already shrinkable,
not `SearchInput`). All measured clean at 1440 and 1024 both before and after, so
no changes were made to those files.

### Select Escape — behaviour

Matches the Settings model-catalog typeahead
(`Settings.jsx:1057` — `if (e.key === 'Escape' && showSug) { e.preventDefault(); setSugOpen(false); return }`),
but at document level, because a `Select`'s popover has no single focused input
to hang the handler on. Capture phase is required rather than incidental:
`useEscape` (`hooks.js:18`) listens on `document` in the **bubble** phase and a
parent modal registers *before* the popover opens, so the "child effects register
first" ordering `useEscape` documents does not apply here — a capture listener
always runs first. Confirmed in a headless DOM test:

- listbox open → `['select-closed']` only; the modal handler never runs and the
  focused input never sees the key;
- listbox closed (listener removed) → `['input-saw-Escape', 'modal-closed']`.

### Gates

- `py v2-testing/tools/stylelint.py` → `0 findings ({}), 109 allowed, 0 css`, **exit 0**
- `npx esbuild@0.21.5 --loader:.jsx=jsx frontend/src/v2/ui.jsx` → parses clean
- `npx esbuild@0.21.5 frontend/src/v2/theme.css --minify --loader:.css=css` → **0 warnings** (was 1); `frontend/src/index.css` also checked, clean
- Brace balance — `ui.jsx` 508 `{` / 508 `}` (HEAD 507/507; +1 balanced pair from the new listener-cleanup block); `theme.css` 86/86, identical to HEAD
- Alt-block token parity — 57 names in each of the two alt blocks, no light-only or dark-only name

### Still needs a rebuild to confirm

Nothing here is live. `docker compose build frontend` plus a repeat of the four
affected checks — light+alt colour sampling on `/v2/ui` and `/v2/settings`;
`no h-overflow` on `/v2/resumes` and `/v2/cover-letters`; Escape on Persona's
enum Picker and `/v2/ui`'s Provider select — is the confirmation pass.

### Addendum — two items from `flows-A-final.md`

Same source-only pass, same rules (no rebuild, no restart, no commit). The
backend file needs a container restart to take effect; the two frontend files
need a rebuild.

| DS id | file:line | change |
|---|---|---|
| DS-A-03 (P2) | `frontend/src/v2/Applications.jsx:158` and `:489` | Escape no longer routes to `closeLog()` unless the Log modal is actually open, and a successful save now clears the dirty flag. |
| DS-A-02 (P2) | `backend/api/routes_searches.py:370-394`, `:466-469`, `:497`, `:515-519`, `:312-314`; `frontend/src/v2/Searches.jsx:745-750`, `:884-890`, `:866` | The Searches test preview now applies `title_exclude_global` as its own layer, labels the rows it drops, and counts them in the footer. Three tests added in `backend/tests/test_routes_searches.py`. |

#### DS-A-03 — Applications Escape after a save

Two independent changes, both of the ones the finding proposed:

- `:489` — `onSaved` was `setLogOpen(false)`, which unmounts the form but leaves
  `logDirty.current` true. It is now `dropLog()`, the existing helper that clears
  the flag *and* closes. The draft itself is `LogModal`'s own `useState`
  (`:742` onwards) and dies with the unmount, so there is nothing else to reset.
- `:158` — `useEscape(() => { closeAll(); setPrep(null); setEditIv(null); closeLog() }, !confirm)`
  became `… if (logOpen) closeLog() …`. This is the real fix: unguarded,
  `closeLog()` ran on **every** Escape anywhere on the screen, so a stale dirty
  flag from any path could raise the discard confirm — and, since the design pass
  swapped `window.confirm` for the DOM `ConfirmDialog`, its full-viewport
  `z-index:70` scrim then blocked every click until a second Escape.

`logOpen` is the `useState` at `:102`, and `useEscape` holds its callback in a
ref (`hooks.js:19-20`) that is refreshed on every render, so the guard reads the
current value even though the listener itself is registered once.

#### DS-A-02 — Searches preview vs. the global title-exclude list

Backend, `test_search` in `routes_searches.py`:

- After the per-search title layers and the company filter/exclude, and **before**
  the body scan (the run's order — `sources/jobspy.py:285` merges the global list
  into the title filter, which runs before anything else), the preview now reads
  `title_exclude_global` through the same `get_global_title_exclude(db)` helper
  the Companies preview uses, and word-boundary-matches it case-insensitively —
  identical regex to `routes_companies.py:603`.
- `after_search_filter` is snapshotted *before* that layer, so the response says
  both how many rows passed this search's own filters and how many the global
  list then removed.
- Per row: `global_excluded_by` (the matched keywords, or `[]`) and
  `reason = "[Global] Excluded by: <kw>"` — the same string the Companies preview
  emits. The reason chain places it after the per-search and company reasons and
  before the body-exclusion one, so a row dropped by this search's own list keeps
  its own label rather than being relabelled `[Global]`.
- Response gains `after_search_filter`, `global_excluded_count`,
  `global_exclude_keyword_count`; the empty-result early return carries the same
  three keys at 0 so the payload shape does not change with the result count.

Frontend, `Searches.jsx` `TestModal`:

- Footer: `nTitleFiltered` now subtracts the global drops too (they were being
  counted as title-filtered), and a `· N removed by the global list
  (M pass this search's filters)` term appears when there are any — the same
  arithmetic the Companies footer prints (`Companies.jsx:903-906`).
- Row status badge: a global drop reads `GLOBAL` rather than a bare `OUT`, since
  the row did pass this search's own filters; its `reason` line already renders
  under the title.

Tests — `backend/tests/test_routes_searches.py`, three added, all stubbing
`jobspy.scrape_jobs` (the handler imports it at call time, so patching the module
attribute is enough):

- `test_preview_applies_global_title_exclude` — 3 rows, global list
  `["intern", "marketing"]`: `after_filter == 1`, `after_search_filter == 3`,
  `global_excluded_count == 2`, and the two dropped rows carry the right
  `global_excluded_by` and `[Global] Excluded by: …` reason. This is the exact
  shape of the finding's measured repro (`Intern, Design Engineering` and
  `Staff Technical Product Marketing Manager` kept by the preview, `ignored` by
  the run).
- `test_preview_global_exclude_is_word_bounded_and_optional` — `Internal
  Communications Manager` is **not** dropped by a global `intern`, matching the
  run's word-bounded filter.
- `test_preview_per_search_exclude_still_wins_its_own_label` — a per-search
  exclude keeps `Excluded by: senior`, is not relabelled `[Global]`, and does not
  count toward `global_excluded_count`.

The helper blanks `Search.title_exclude_keywords` by default, because the model
seeds it with `["intern", "junior", "associate"]` (`models/db.py:62`) — without
that, the per-search layer swallows the row before the global layer is reached
and the test measures the wrong thing.

#### Gates (addendum)

- `python -m pytest backend/tests -q` **in the running backend container** → **861 passed**, 3 pre-existing warnings (the full suite, not just the new file; the new tests are 3 of the 10 in `test_routes_searches.py`)
- `npx esbuild@0.21.5 --loader:.jsx=jsx` on `ui.jsx`, `Applications.jsx`, `Searches.jsx` → all parse clean
- `ast.parse` on `routes_searches.py` and `test_routes_searches.py` → clean
- `py v2-testing/tools/stylelint.py` → 0 findings, exit 0
- Brace balance vs HEAD — `Applications.jsx` 734/734 (HEAD 733/733, +1 pair: the new JSX comment), `Searches.jsx` 766/766 (HEAD 756/756, +10 pairs: the new footer terms and consts), `ui.jsx` 508/508, `theme.css` 86/86

#### Restart / rebuild needed

- `backend/api/routes_searches.py` — **backend container restart** (uvicorn runs without `--reload`). Handing this to the coordinator rather than restarting it here, since flow agents are live.
- `frontend/src/v2/Applications.jsx`, `Searches.jsx`, `ui.jsx`, `theme.css` — frontend rebuild.
