# Rebuild re-verification list (generated)

## stage3\applications.md: 3 fixed-in-source lines, 1 findings marked fixed-in-source
- `frontend/src/v2/Applications.jsx:222` — count-line span given `lineHeight:'20px'` (was 19.5 px from the inherited 1.5), which put the whole list pane on `top 135.5`.
- `frontend/src/v2/Applications.jsx:293` — stage-group header given `lineHeight:'16px'` (was 15.75 px → 32.75 px header, the source of every `x.25` row top).
- `frontend/src/v2/Applications.jsx:249` — company-popover item given `lineHeight:'18px'` (92 of 122 items were fractional).
- [APPS-08] P3 Every list row lands on a fractional pixel — **fixed in source** — fixed in source (rebuild pending) — `Applications.jsx:222, :
## stage3\companies.md: 5 fixed-in-source lines, 3 findings marked fixed-in-source
- `backend/api/routes_companies.py:75,204-205` — `create_company` now accepts and persists `aliases` and `auto_scoring_depth`. **Fixed + verified (backend)**: after the 13:20 restart, `POST /companies {aliases:["ZZT Alias One","ZZT Alias Two"], auto_scoring_depth:"full"}` returned them intact, and the Add modal's own success path round-tripped `aliases: ["ZZG One","ZZG Two"]`, `auto_scoring_depth: "full"`.
- `frontend/src/v2/Companies.jsx:37-54` — `detectAts` realigned to the backend `detect_scrape_type`. **Verified against the post-fix source**: evaluated the new function over 18 URLs (all 11 ATS families, `POST|`, a bare URL and a non-URL) and compared each against `detect_scrape_type` in-process — **18/18 agree**. The pre-fix bundle mismatched on 3 (`jobs.eu.lever.co` → Lever vs Generic, `jobs.eightfold.ai` → Eightfold vs Generic, `/search-jobs/results?` → Generic vs TalentBrew). Rebuild pending.
- `frontend/src/v2/Companies.jsx:686` — test-modal summary arithmetic (`found - kept` keyword-filtered, `found + rejected` extracted). Verified arithmetically against the backend's `total_found`/`total_rejected` contract; not observable on an API board (see "Couldn't test"). Rebuild pending.
- `frontend/src/v2/Companies.jsx:262` — **new**: integer `lineHeight: '20px'` on the header subtitle, removing the half-pixel origin that put all 126 rows on `x.5` (COMP-14). Rebuild pending.
- `frontend/src/v2/Companies.jsx:308` — **new**: dropped the inline `background: 'transparent'` on unselected sort options so `.v2-menuitem:hover` can apply (COMP-15). Rebuild pending.
- [COMP-11] P2 The alias badge under-reports by one, and a company with exactly one a — fixed in source? no — logged; one-line change but it silentl
- [COMP-14] P3 Every row lands on a half pixel (fractional `getBoundingClientRect().t — fixed in source (rebuild pending)
- [COMP-15] P3 The sort menu's hover never fires — an inline `background: 'transparen — fixed in source (rebuild pending)
## stage3\cover-letters.md: 0 fixed-in-source lines, 6 findings marked fixed-in-source
- [CL-01] P2 Editor autosave silently drops a patch of a different kind — the templ — fixed in source (rebuild pending) — `pendingPatch` ref, `{..
- [CL-02] P2 Editor gets permanently stuck in "Regenerating…" if the post-run reloa — fixed in source (rebuild pending).
- [CL-03] P2 Regenerate poll waits for *every* cover-letter run in the system, not  — fixed in source (rebuild pending).
- [CL-04] P2 `?job=` deep-link silently loses its selection for any job outside the — fixed in source (rebuild pending) — shared `mergeKeep` helpe
- [CL-09] P3 Pending row is 46.75 px tall, so every letter row below it lands on a  — fixed in source (rebuild pending).
- [CL-10] P3 Editor: the `text · link · stub` hint is 15.75 px tall and pushes the  — fixed in source (rebuild pending).
## stage3\feed.md: 5 fixed-in-source lines, 3 findings marked fixed-in-source
- `frontend/src/v2/JobFeed.jsx:601` — header subline `lineHeight: '20px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:770` — status badge `lineHeight: '14px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:777` — salary/visa/age row `lineHeight: '13px'` (FEED-02)
- `frontend/src/v2/JobFeed.jsx:609` — filter bar `flexWrap:'wrap', rowGap:8` (FEED-03)
- `frontend/src/v2/JobFeed.jsx:685` — sort item background only when current, so `.v2-menuitem:hover` fires (FEED-04)
- [FEED-02] P3 Every list row lands on a half pixel; 1px borders drop on alternating  — fixed in source (rebuild pending)
- [FEED-03] P2 The filter bar does not wrap; at 1024 px the Sort control is off-scree — fixed in source (rebuild pending)
- [FEED-04] P2 Sort-menu items have a dead hover — fixed in source (rebuild pending)
## stage3\persona-stats.md: 2 fixed-in-source lines, 1 findings marked fixed-in-source
- `backend/api/routes_persona.py:63-69` — `flag_modified(p, k)` in `update_persona`'s loop, so an order-only node write is actually persisted (PERS-02). **Verified live after the restart.**
- `frontend/src/v2/ResumeSections.jsx:213` — explicit `lineHeight: '18px'` on the Experience entry header, removing five fractional row tops (PERS-11). **Rebuild pending.**
- [PERS-11] P3 Experience entry headers are 36.75 px tall, putting five rows on a hal — fixed in source (rebuild pending) — `ResumeSections.jsx:213`
## stage3\resumes.md: 7 fixed-in-source lines, 3 findings marked fixed-in-source
- `backend/api/routes_resumes.py:14,973-978` — `flag_modified(resume, "json_data")` so a key-order-only PATCH persists (RES-02). **Fixed + verified after the restart.**
- `frontend/src/v2/Resumes.jsx:109` — header subtitle `lineHeight: '20px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:128-129` — search-result row `lineHeight: '20px'` + badge `lineHeight: '16px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:143-144` — archived row + badge, same (RES-10).
- `frontend/src/v2/Resumes.jsx:158,193` — Persona and base card header rows `lineHeight: '28px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:253-268` — `importPdf` reuses the row `/resumes/import-pdf` already created (renaming it when the user typed a name) instead of creating a second one (RES-03).
- `frontend/src/v2/ResumeEditor.jsx:424,436` — template/paper menu items drop the inline `background:'transparent'` that killed `.v2-menuitem:hover` (RES-12).
- [RES-03] P2 "Import PDF" creates **two** base résumés — fixed in source (rebuild pending) — `Resumes.jsx:253-268`
- [RES-10] P3 Shelf: every other card and row landed on a half pixel — **fixed** — fixed in source (rebuild pending) — `Resumes.jsx:109,128-129
- [RES-12] P3 The Template and Paper dropdown items had no hover at all — **fixed** — fixed in source (rebuild pending) — `ResumeEditor.jsx:424,43
## stage3\searches.md: 9 fixed-in-source lines, 7 findings marked fixed-in-source
- `:4` — import `useToasts` / `ToastStack`.
- `:29-38` — new `errText(e, fallback)` helper: unpacks a string `detail`, joins `.msg` over a 422 array detail (SRCH-03).
- `:321-334` — `loading` / `loadErr` state; `load()` sets both and pushes an error toast (SRCH-04, SRCH-05).
- `:380-405` — `fail()` helper; `save`, `create`, `toggleActive`, `remove`, `duplicate` all surface an error toast; `window.alert` removed from the three sites (SRCH-04). `runNow` keeps the spinner on 409 and shows a `progress` toast (SRCH-06).
- `:418-438` — `settle(data)` in `runTest` routes a 200-with-`error` payload to the modal's error branch, on both the sync and the poll path (SRCH-02); the catch uses `errText`.
- `:503`, `:506` — integer `lineHeight` on the card name (23px) and summary (17px) (SRCH-07).
- `:574-591` — loading spinner row and a `Couldn’t load your searches` + `Try again` row; the real empty state now requires `!loading && !loadErr` (SRCH-05).
- `:599` — `<ToastStack>` mounted.
- `:612-615` — `bySource` reads `source_breakdown` first (SRCH-01).
- [SRCH-01] P2 Test-modal source chips never render — the modal reads `by_source`, ev — fixed in source (rebuild pending)
- [SRCH-02] P2 A preview that fails with HTTP 200 + `{"error": …}` is rendered as “No — fixed in source (rebuild pending)
- [SRCH-03] P2 A 422 from `POST /searches` alerts “[object Object]” — fixed in source (rebuild pending)
- [SRCH-04] P2 `Toast.jsx` was never imported — toggleActive, runNow, delete and dupl — fixed in source (rebuild pending)
- [SRCH-05] P2 No loading and no error state for the list — a failed GET renders “No  — fixed in source (rebuild pending)
- [SRCH-06] P2 A 409 from Run clears the spinner although the run really is in flight — fixed in source (rebuild pending)
- [SRCH-07] P3 Every card in the list lands on a half pixel — fixed in source (rebuild pending)
## stage3\settings.md: 8 fixed-in-source lines, 9 findings marked fixed-in-source
- `frontend/src/v2/Settings.jsx:66-100` — `TextBox`: an unset secret no longer renders the mask, show/hide is hidden when there is nothing to show, revealing clears the mask instead of leaving it editable, and `commit()` refuses to save a bare mask or to wipe a stored secret with an empty box (SET-01, SET-02).
- `frontend/src/v2/Settings.jsx:131,155-162` — a single `flashTimer` ref, so back-to-back flashes each get their full 2.2 s (SET-09).
- `frontend/src/v2/Settings.jsx:165-169` — `save()` returns whether the PATCH landed.
- `frontend/src/v2/Settings.jsx:590-594` — `ApiKeyRow` bails out before writing `localStorage` / refreshing the cookie when the PATCH failed (SET-03).
- `frontend/src/v2/Settings.jsx:311-314` — register-webhook failures flash as `bad` and fall back to `data.error` (SET-07).
- `frontend/src/v2/Settings.jsx:299,343` — `dedup` and `advanced` section subtitles restored from the design (SET-19).
- `frontend/src/v2/Settings.jsx:672-683` — `EditModal` reset parses a JSON seed string for `list`/`json` rows, and refuses to reset at all when the key has no default (SET-04, SET-05).
- `frontend/src/v2/Settings.jsx:625-631` — `Submit PIN` wrapped in try/catch (SET-10).
- [SET-01] P1 Typing after a revealed secret mask saves `••••••<typed>` and destroys — fixed in source (rebuild pending) — `Settings.jsx:66-100`
- [SET-02] P2 An unset secret renders as six bullets, identical to a set one — fixed in source (rebuild pending) — `Settings.jsx:76,96`
- [SET-03] P1 "Save key" writes the new API key locally and refreshes the session co — fixed in source (rebuild pending) — `Settings.jsx:165-169`, 
- [SET-04] P2 "Reset to default" on a list editor saves a one-element list containin — fixed in source (rebuild pending) — `Settings.jsx:672-683`
- [SET-05] P2 "Reset to default" wipes a prompt to `""` when `GET /settings/defaults — fixed in source (rebuild pending) — `Settings.jsx:676`
- [SET-07] P3 A failed webhook registration flashes in accent green, reading as succ — fixed in source (rebuild pending) — `Settings.jsx:311-314`
- [SET-09] P4 Two saves inside 2.2 s: the first flash's timer clears the second mess — fixed in source (rebuild pending) — `Settings.jsx:155-162`
- [SET-10] P3 "Submit PIN" has no catch — a 401/500/network error is an unhandled re — fixed in source (rebuild pending) — `Settings.jsx:625-631`. 
- [SET-19] P4 Two section headers rendered with no subtitle — fixed in source (rebuild pending) — `Settings.jsx:299,343`
## stage3\shell.md: 3 fixed-in-source lines, 2 findings marked fixed-in-source
- `theme.css:31` — `--rail-hover` token; `theme.css:136-137` — `!important` on `.v2-navdark:hover`, new `.v2-themebtn:hover`
- `V2App.jsx` footer ◐ — `className="v2-navdark v2-themebtn"`
- `WelcomeModal.jsx:56` — desc line-height 17 px
- [SHELL-01] P3 Every rail hover is dead (inline colour beats `.v2-navdark:hover`) — fixed in source (rebuild pending) — `theme.css:31,136-137`, 
- [SHELL-03] P4 Welcome step rows land on half pixels — fixed in source (rebuild pending): `lineHeight: '17px'`.

## Results after rebuild (bundle index-ClAeCNUL.js, 2026-09-02) — `artifacts/reverify_1.json`
CONFIRMED: SHELL-01 (nav/collapse/theme-button hovers fire), SHELL-03 (welcome tops integer), F-001 (✦ → /v2/resumes/{id}), F-002 (?company= → Company · 1), SRCH-05 (500 → "Couldn't load / Try again" + toast; "No searches yet" gone), COMP-01 (PATCH 500 → drawer stays open, inline "Save failed", toast), COMP-14 (0 fractional), COMP load-500 toast, APPS load-500 toast, RES-10 (0 fractional), RES template-menu hover, RES-01 (autosave 500 → error toast, no "saved" label), SET-01 (typing after the mask sends no PATCH; mask never in a body), SET rows 0 fractional, PERS-01 (dict qa_bank renders, 0 page errors), PERS load-500 toast, STAT load-500 toast.
NOT CONFIRMED / RESIDUAL: FEED-02 (7 fractional in the detail band), SRCH-07 (24 — card top 105.5, offset from above the list), APPS-08 (37 rows at x.5), CL-09 (9 in the generate panel), PERS-11 (34 in the résumé-content editor) → consolidated as F-009. FEED-04 / COMP-15 / FEED-03 re-measured in `reverify_2.py` (see below).
