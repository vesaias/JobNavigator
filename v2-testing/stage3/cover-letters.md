# Stage 3 — Cover Letters
Tested: 2026-09-02, bundle index-Dnrx3n0f.js (HEAD 3819fe8), themes light+dark, viewport 1440×900 (+ a narrow 1024×700 pass on both screens)
Design: `v2-testing/design/Cover Letters Ops.dc.html`   Inventory: `v2-testing/inventory/v2-cover-letters.md`
Screens: list `frontend/src/v2/CoverLetters.jsx` (`/v2/cover-letters`), editor `frontend/src/v2/CoverLetterEditor.jsx` (`/v2/cover-letters/:id`)
Scripts (scratchpad, copied to `/tmp/v2t/`): `cl_01_recon`, `cl_02_list`, `cl_03_dark_inter`, `cl_04_pickers`, `cl_05_empty`, `cl_06_deeplink`, `cl_07_jobrace`, `cl_08_create`, `cl_09_editor`, `cl_10_fields`, `cl_11_debounce`, `cl_12_actions`, `cl_13_dl_regen`, `cl_14_ids_poll`, `cl_15_realgen`, `cl_16_regen_delete`, `cl_17_dark_misc`, `cl_18_frac`, `cl_19_cleanup`, `cl_20_a11y`
Screenshots: `v2-testing/artifacts/cover-letters/` (14 PNGs)
LLM budget used: 2 real calls (one generation from the list, one regenerate from the editor). Both results deleted.

---

## Findings

### CL-01 · P2 · Editor autosave silently drops a patch of a different kind — the template you picked is never saved and the header says "saved"
**Where** `frontend/src/v2/CoverLetterEditor.jsx:126-133` (`persist`), route `/v2/cover-letters/:id`
**Repro** (script `cl_11_debounce.py`)
1. Pick **Template → Traditional Block**, then type one character in any field within 500 ms.
2. Wait 2 s, read the server row.
**Expected + why** Both edits reach the server. `persist()` is the single save path for `{json_data}` (ED:139), `{template}` (ED:164) and `{page_format}` (ED:165); the header claims `autosaves` (ED:260).
**Actual** One timer holds ONE `patch` object and the second call **replaces** it:

| order | PATCH actually sent | lost | UI afterwards |
|---|---|---|---|
| type → pick template | `{"template":"helvetica"}` | the keystroke | input shows `ZZTEST CoXZ`, server has `ZZTEST CoX`, header "saved just now" |
| pick template → type | `{"json_data":{…}}` | the template | control shows "Traditional Block", server has `helvetica`, header "saved just now"; **after reload the control reverts** |

Two `json_data` edits in the same window are safe (both land — `update()` deep-clones the current state), so the damage is confined to cross-kind patches. The `json_data` loss self-heals on the next keystroke; the **template / page_format loss is permanent** until the user re-picks, and meanwhile the PDF preview and the download render with the old template while the UI shows the new one.
**Proposed fix** Merge pending patches into a ref instead of replacing them.
**Status** fixed in source (rebuild pending) — `pendingPatch` ref, `{...pendingPatch.current, ...patch}`, flushed and cleared inside the timer.

### CL-02 · P2 · Editor gets permanently stuck in "Regenerating…" if the post-run reload fails
**Where** `CoverLetterEditor.jsx:204-223` (regenerate poll)
**Repro** (script `cl_13_dl_regen.py`) Start a regenerate, then make `GET /api/cover-letters/{id}` fail (route intercept 500) while `/monitor/active` returns `[]`.
**Expected + why** The poll should retry, or surface an error. The modal's Cancel and scrim both refuse while `regening` (ED:462, 487).
**Actual** `clearInterval(iv)` runs **before** the reload `GET` (ED:212-213); the GET throws, the `catch` swallows it (ED:220), and the interval is already gone — so `regening` stays `true` for ever:
- modal locked: Cancel → still open, scrim click → still open (measured);
- only Escape closes it (ED:227) and the ↻ pill keeps spinning after that;
- restoring the network does **not** recover — there is no interval left. Measured after 6 s of failure and again after un-routing: `{'modal': True, 'btnText': 'Regenerating…', 'btnOpacity': '0.6', 'spin': 1}`, pill spinner still present. Only a page reload clears it.
**Proposed fix** Do the reload first and `clearInterval` only after it succeeds, so a failed GET is simply retried on the next tick.
**Status** fixed in source (rebuild pending).

### CL-03 · P2 · Regenerate poll waits for *every* cover-letter run in the system, not this letter's
**Where** `CoverLetterEditor.jsx:210`
**Repro** (script `cl_14_ids_poll.py`) Intercept `/api/monitor/active` with a single run `{"job_type":"generate_cover_letter","scope_key":"cl:some-other-letter"}` and start a regenerate here.
**Expected + why** The backend keys a regenerate as `cl:{cover_letter_id}` (`routes_cover_letters.py:341`), so the poll can scope precisely.
**Actual** After 7 s the modal is still open with the button reading `Regenerating…` although this letter's own run finished — a generation started on the list (or from another tab) holds this editor hostage.
**Proposed fix** `r.job_type === 'generate_cover_letter' && r.scope_key === \`cl:${id}\``.
**Status** fixed in source (rebuild pending).

### CL-04 · P2 · `?job=` deep-link silently loses its selection for any job outside the saved/applied window
**Where** `CoverLetters.jsx:140-141` vs `:152-170`
**Repro** (scripts `cl_06_deeplink.py`, `cl_07_jobrace.py`) Open `/v2/cover-letters?job={id of a job with status new or skip}`.
**Expected + why** CL:158-160 exists precisely to make an out-of-window job pickable ("make sure the target is pickable even if it's outside the fetched window").
**Actual** Race. The single-job `GET /api/jobs/{id}` finishes first (observed response order: `/api/jobs/261e…` → `/api/jobs?status=saved,applied&limit=200`), then the 200-row list response calls `setJobs(data.jobs || [])`, **replacing** the array and wiping the prepended row. Result:
- Target job control reads the placeholder `Select a saved or applied job…`
- but `genJob` is still set, so **Generate is enabled** (`title` = "Write the letter — you can start others while it runs", opacity 1) and will generate for an invisible job.
Confirmed causally: fulfilling the list route instantly (so it lands first) makes the prepend survive and the control reads `Youtube — YouTube`. In-window saved/applied jobs are unaffected. The same race exists for `?resume=` but the résumé list is small enough to usually land first.
**Proposed fix** Merge instead of replace in both list loaders.
**Status** fixed in source (rebuild pending) — shared `mergeKeep` helper applied to `/resumes` and `/jobs`.

### CL-05 · P2 · A failed list load is rendered as "No cover letters yet"
**Where** `CoverLetters.jsx:130-132, 356-359`
**Repro** (`cl_05_empty.py`) Route `GET /api/cover-letters` → 500.
**Actual** `countLine` = `0 letters · 0 live applications`, gutter `0`, body copy `No cover letters yet — generate one on the left.` — identical to a genuinely empty account. Console-only `console.error`; no toast, no retry. A user with 16 letters is told they have none and invited to generate a duplicate.
**Proposed fix** A `loadErr` state → "Couldn't load your letters." + retry, distinct from the empty copy. (Also removes the flash of the empty copy before the first response — there is no loading state at all.)
**Status** fixed in source (rebuild pending) — `CoverLetters.jsx:131` `loadErr` state, set in `load()`’s catch (`:135-142`, cleared on every success) and rendered at `:378-387` as “Couldn’t load your letters · <status> · Try again” instead of the empty copy. Same shape as `Searches.jsx:582-587`. Adopting `Toast.jsx` across this screen (CL-18) is still open — this branch is the load path only, and the empty-copy flash before the first response is untouched (no loading state added).

### CL-06 · P2 · A background generation that fails looks exactly like one that succeeded
**Where** `CoverLetters.jsx:173-189` (poll), `:183`
**Repro** Any `_generate_impl` failure (LLM error, `job missing at execution time`).
**Expected + why** HANDOVER risk area 3: background job lifecycle. The run row leaves `/monitor/active` whether it completed or failed.
**Actual** The dashed row disappears, `load()` runs, no new letter appears, and nothing is said. `/api/monitor/history` is never consulted. The user's only signal is "the row went away and nothing arrived". Same hole on the editor's regenerate path (ED:211-218): the poll reloads the unchanged letter and closes the modal silently.
**Proposed fix** On disappearance, look the run up in `/api/monitor/history` and surface `status === 'failed'` + `error` inline (or as an error toast).
**Status** fixed in source (rebuild pending) — `CoverLetters.jsx:198-208`: when one or more runs leave `/monitor/active`, the poll reloads the list *and* fetches `/monitor/history?job_type=generate_cover_letter&limit=20`; any disappeared run whose history row is `status === 'failed'` sets `err` to “Generation failed — <error>” in the generate panel (`:324`). One extra request only on the tick where a run finishes. The editor’s regenerate path (ED:207-225) is **not** covered — it polls a different scope and shows errors in the top bar (CL-14); left as a separate decision.

### CL-07 · P2 · An open Picker popover covers the other Picker's control; clicking the second control picks an option from the first
**Where** `CoverLetters.jsx:36-69` (`Picker`), wrapper `stopPropagation` at `:46`, document-close at `:38-43`
**Repro** (`cl_04_pickers.py`) Open **Your résumé**, then click the **Target job** control.
**Expected + why** Clicking outside a popover closes it (that is what the document listener is for; clicking the `h1` does close it — verified).
**Actual** The wrapper's `stopPropagation` means a click inside the *other* Picker never reaches the document handler, so popover A stays open — and it physically overlaps control B (measured: résumé popover `top 200.3 → bottom 380`, job control `top 247.3`). Playwright reports the click intercepted by `<div>PM</div>`: the user aiming at "Target job" selects the résumé "PM" instead. Both popovers can also be open at once (z-index tie at 40).
**Proposed fix** Lift the open state out of `Picker` (one `openPicker` id in the parent), or close on `mousedown` at the capture phase.
**Status** fixed in source (rebuild pending) — `CoverLetters.jsx:53-58`: the open `Picker` now renders a transparent full-viewport scrim (`position:fixed; inset:0; zIndex:39`) under its popover (`zIndex:40`). A click aimed at the control the popover overlaps hits the scrim, which closes the popover and swallows the click, so it can no longer land on an option of the *other* picker; the popover’s own items stay clickable. Chosen over lifting the open state to the parent: the scrim is 2 lines, lives inside `Picker`, and also fixes the “both open at once” tie without touching either call site (`CoverLetters.jsx:322,328`, `CoverLetterEditor.jsx:487`). `Persona.jsx` has its own local `Picker` and is unaffected.

### CL-08 · P3 · `.v2-menuitem` hover is dead in every popover that sets an inline background — the two Pickers, the Template list and the Paper list
**Where** `theme.css:148` vs `CoverLetters.jsx:60`, `CoverLetterEditor.jsx:430, 445`
**Repro** `hover_delta` on a Picker option and on a Template option.
**Expected + why** HANDOVER: "Inline styles beat class `:hover` … needs `!important` or it silently does nothing." The class is applied deliberately at all four sites.
**Actual** Picker option: `{'before': {'backgroundColor': 'rgba(0,0,0,0)'}, 'after': {'backgroundColor': 'rgba(0,0,0,0)'}, 'changed': []}`. Template option: identical. The same class **does** work on the editor's ⋯ menu items (ED:288/294/300 set no inline background) — measured `rgba(0,0,0,0) → rgb(246,244,238)`. So three of five call sites are silently inert.
**Proposed fix** Either drop the inline `background: 'transparent'` on the unselected branch (keep only the selected `--accent-soft`), or make the rule `background: var(--surface-2) !important`.
**Status** fixed + verified: `.v2-menuitem:hover` hardened with `!important` in theme.css (tree-wide); picker/template/paper options now wash on hover

### CL-09 · P3 · Pending row is 46.75 px tall, so every letter row below it lands on a half pixel
**Where** `CoverLetters.jsx:331-338` (label at `:334`)
**Repro** (`cl_17_dark_misc.py`) Intercept `/monitor/active` with one `generate_cover_letter` run, then `assert_int_tops(pg, 'div.v2-bd')`.
**Expected + why** HANDOVER: "Half-pixel rows drop their 1px borders … fix with explicit integer line-heights. After list or card work, assert zero fractional tops."
**Actual** `{'count': 6, 'fractional': 6, 'samples': [194.75, 270.75, 346.75, 422.75, 498.75]}`. Pending-row height `46.75` (12.5 px label × inherited 1.5 = 18.75 + 26 px padding). Letter rows are a clean 69 px each, so the whole list is offset by .75 while a generation runs. With no pending row: 0 fractional (verified for 5 and for 16 rows, light and dark).
**Proposed fix** `lineHeight: '20px'` on the pending label.
**Status** fixed in source (rebuild pending).

### CL-10 · P3 · Editor: the `text · link · stub` hint is 15.75 px tall and pushes the Recipient and Letter cards onto half pixels
**Where** `CoverLetterEditor.jsx:326`
**Repro** (`cl_18_frac.py`) Open the Header card, then walk the left column for fractional heights.
**Actual** With the Header card open: card tops `[111, 371.75, 563.75]`, inputs `{'count': 13, 'fractional': 12}`. The single fractional leaf is `SPAN "text · link · stub"` — `fontSize 10.5px`, `lineHeight 15.75px` — which makes its flex row 15.75 and the whole Header card 250.75. (The `✕` remove glyphs are 16.5 px but sit inside 29 px rows, so they are harmless.) Every card in this editor carries a 1 px border, which is what the convention exists to protect.
**Proposed fix** `lineHeight: '16px'` on the hint.
**Status** fixed in source (rebuild pending).

### CL-11 · P3 · The Download PDF button is pushed off-screen below ~1090 px viewport width
**Where** `CoverLetterEditor.jsx:417-451` (preview toolbar), `:451`
**Repro** (`cl_18_frac.py`) 1024×700, measure the toolbar.
**Actual** Toolbar `clientWidth 434`, `scrollWidth 467`, `overflow: visible`, and the Download control sits at `x 932.3 → right 1057.4` against a viewport right edge of `1024` — the page itself does not scroll horizontally (`overflow: hidden` upstream), so **the control is unreachable**. Fine at 1280 (`scroll 569 = client 569`) and at 1440. The toolbar is a single non-wrapping flex row with three fixed-width children plus a `margin-left: auto` button.
**Proposed fix** `flexWrap: 'wrap'` on the toolbar, or shrink the Template control (`minWidth: 0` + ellipsis on the template name — "Garamond Classic" alone is 140.5 px).
**Status** fixed + verified after rebuild: preview toolbar wraps; Download sits at right 1004 inside a 1024 px viewport

### CL-12 · P3 · The generate panel's explanatory line from the design is missing
**Where** design `.dc.html:99` vs `CoverLetters.jsx:315-320`
**Expected** After the Generate button the design puts a 10.5 px muted line: `Takes about 30 seconds — the letter appears in the list when it's done, drafted for your review.`
**Actual** Nothing follows the button except the (usually empty) inline `err` span. Nothing on this screen tells a first-time user that generation is asynchronous, or that the result is a draft — the `~30s` copy only appears once the pending row exists. Measured real runs: 10 s (concise) and 26 s (detailed regenerate), so the copy is accurate.
**Proposed fix** Restore the line under the button.
**Status** decided 2026-09-02: keep (no explanatory line)

### CL-13 · P3 · No "no voice presets" state — an invisible 0 px gap, and `voice: ""` is posted
**Where** `CoverLetters.jsx:72-86` (`VoicePicker`), `:307`; same component in the editor modal (ED:478)
**Repro** (`cl_05_empty.py`) Route `/api/settings` → `{"cover_letter_voice_presets":"[]", "cover_letter_default_voice":""}`, or → 500.
**Actual** The `VOICE` label renders above a flex row measured `{h: 0, kids: 0}` — a labelled void. `genVoice` stays `''` and is sent to `POST /generate`. Same on a settings 500 (0 chips). A first-run user who has not configured presets sees a broken-looking form with no explanation.
**Proposed fix** Empty copy, e.g. "No voice presets — add them in Settings → AI", and hide the label when the list is empty.
**Status** fixed + verified after rebuild: with no presets the voice row reads "No voice presets — add them in Settings → AI."

### CL-14 · P3 · Regenerate failures are reported in the top bar, behind the modal's scrim
**Where** `CoverLetterEditor.jsx:198-199` → `:259-260`, modal scrim `:462` (`zIndex 60`)
**Repro** (`cl_13_dl_regen.py`) Intercept `POST /cover-letters/generate` → 500 / 409, click Regenerate.
**Actual** The message ("regen boom", "generate_cover_letter is already running for this pair") is written into the top-bar `err` slot, which the still-open scrim dims. The modal itself shows no change other than the button reverting to `Regenerate`. Screenshot `cl-editor-regen-500.png`.
**Proposed fix** Render `err` inside the modal footer while `regenOpen`.
**Status** fixed + verified after rebuild: a regenerate failure toasts (above the scrim) and replaces the modal footer's "~30 seconds" with the message

### CL-15 · P3 · Load-error page has no back link, no retry, and no distinction between 404, 500 and offline
**Where** `CoverLetterEditor.jsx:106, 237-239`
**Repro** `/v2/cover-letters/11111111-2222-3333-4444-555555555555` (404) and `/v2/cover-letters/abc` (500).
**Actual** Both render a centred `Could not load this letter.` with nothing else — the rail is the only way out (`.v2-ctl:has-text("Cover Letters")` count = 0, i.e. the ‹ Cover Letters back link is inside the top bar, which is not rendered in this branch). The tab title stays "Cover Letters · JobNavigator". A just-deleted id lands in the same place (verified after a UI delete).
**Proposed fix** Keep the top bar (or add a "‹ Back to cover letters" link) in the error branch; distinguish 404 ("This letter no longer exists.") from 5xx ("Couldn't load this letter — try again.").
**Status** fixed + verified after rebuild: 404 → "This letter no longer exists." + ‹ Back to cover letters; other failures → "Couldn’t load this letter — try again." + Back + Try again

### CL-16 · P3 · Backend: a non-UUID cover-letter id returns 500 instead of 404
**Where** `backend/api/routes_cover_letters.py:185` (and `:193, 234, 249, 210` — same `filter(CoverLetter.id == cl_id)` shape)
**Repro** `GET /api/cover-letters/abc` → `(500, 'Internal Server Error')`; `GET /api/cover-letters/<valid uuid>` → 404 correctly.
**Expected** A malformed id is a client error; Postgres raises on the uuid cast and the exception escapes.
**Proposed fix** Parse with `uuid.UUID(cl_id)` at the top of each handler and raise 404 on `ValueError` (or a shared `_get_or_404` helper).
**Status** fixed by F-007 (DataError→404 handler), verified live

### CL-17 · P3 · Rail badge `Cover Letters · N` never refreshes after a generate or a delete
**Where** `frontend/src/v2/V2App.jsx:63` (fetched once at shell mount)
**Actual** Measured both directions in one session: after a real generation the rail read `Cover Letters18` while the list header read `19 letters` and the gutter `19`; after deleting a letter through the editor the rail read `Cover Letters19` while the list read `18 letters`. Drift persists until a full page load.
**Proposed fix** Shell-level refresh (event or a light poll) after mutations. Cross-screen — the same badge is fed by every list.
**Status** fixed in source: the list dispatches `jn:counts-changed` when a generation finishes, the editor after a delete; the shell re-reads the rail counts on that event (APPS-19)

### CL-18 · P3 · Neither screen imports `Toast.jsx`; every success is silent and every failure is inline text
**Where** `CoverLetters.jsx`, `CoverLetterEditor.jsx` (no `useToasts`/`ToastStack` import)
**Expected + why** HANDOVER risk area 2: the `error` toast kind deliberately never auto-dismisses and should be wired "at every failure site".
**Actual** Verified: generation 409/500/network → inline red text under the Generate button (`rgb(156,59,48)` = `--bad`), persists (still present after 6 s) and is cleared only by the next Generate click; save failure → red top-bar text, persists, cleared by the next successful save; download failure → same slot; delete/download/save/regenerate **success** → nothing at all; delete has no undo. `[class*=toast]` count = 0 in every case.
**Proposed fix** Route the four editor failures and the list generate failure through the toast system; add an `ok` toast for delete.
**Status** fixed + verified after rebuild: both screens mount the toast system — generate 409/500/failed-run, save, download, delete and regenerate failures toast (error kind persists), a finished generation toasts success

### CL-19 · P3 · A failed PDF render is invisible
**Where** `CoverLetterEditor.jsx:145-162` (`:157` console-only)
**Repro** (`cl_12_actions.py`) Route `**/pdf` → 500 and touch a field.
**Actual** The previous preview stays on screen with no indication it is stale; on a fresh letter the copy `Rendering the preview…` would remain for ever. Only `console.error` + an Axios error in the console. (The spinner at ED:419 also re-fires on every keystroke — it flickers continuously while typing.)
**Proposed fix** A "Preview failed — showing the last render" line in the toolbar.
**Status** fixed + verified after rebuild: a failed render shows "Preview failed — showing the last render · Retry" in the toolbar; Retry re-requests the PDF

### CL-20 · P3 · A Regenerate started in the editor shows on the list as an unlabelled pending row and inflates the gutter count
**Where** `CoverLetters.jsx:178` (filter is `job_type` only), `:246-251` (`rowLabel`), `:327`
**Repro** (`cl_14_ids_poll.py`) Intercept `/monitor/active` with a run whose `scope_key` is `cl:some-other-letter`.
**Actual** A dashed row appears reading `Generating — a cover letter` `~30s`, and the gutter number goes `18 → 19`. When that run finishes no new letter arrives (a regenerate rewrites in place), so the count silently drops back — the list appears to have lost a letter.
**Proposed fix** Ignore runs whose `scope_key` is not of the `cl:{resume}:{job}` shape, or have the backend tag the run kind.
**Status** fixed + verified after rebuild: the list only shows pending rows for pair runs (`cl:{resume}:{job}`); a regenerate (`cl:{id}`) no longer appears or bumps the count

### CL-21 · P3 · Neither screen is keyboard-operable and no control shows focus
**Where** both files — every control is a `div`/`span` with `onClick`; no `role`, `tabIndex`, `aria-expanded`, or key handlers.
**Actual** Measured tab order on the list: 10 rail links → the search `<input>` → `body`. On the editor: 10 rail links, then nothing (the ⋯ menu's `Open job posting` anchor is the only focusable control and it only exists while the menu is open). `aria-expanded` count 0, `role=button` count 0. Focus rings: search input `outline: none, boxShadow: none`; text inputs and the paragraph textarea likewise (`CELL`/`INPUT`/`:397` all set `outline: 'none'` with no replacement) — a keyboard user cannot see where focus is even in the fields that do take it.
**Proposed fix** At minimum a visible focus style on inputs/textarea (`:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--ring-accent) }`), then `tabIndex`/`role`/Enter handlers on the row and button divs.
**Status** fixed + verified after rebuild: every v2 input/textarea/select shows an accent focus ring (`:focus-visible`, theme.css); letter rows are `role=button tabIndex=0` and open on Enter; the ring shows on them too

### CL-22 · P4 · Regenerate keeps no lineage — the previous draft is unrecoverable
**Where** `routes_cover_letters.py:445-461`; `parent_id` is exposed at `:97` and never written or read
**Repro** Real regenerate measured end to end: name/`resume_id`/`from_persona`/`json_data`/`voice`/`length` all replaced in place; `template` and `page_format` correctly preserved (`palatino`/`a4` survived); **`parent_id` before `None`, after `None`**; the previous three paragraphs are gone.
**Expected + why** `CoverLetter.parent_id` exists for regeneration lineage (CLAUDE.md: "`parent_id` for regeneration lineage"), and the modal copy only warns "your edits to this draft are replaced" (ED:467).
**Proposed fix** Either write `parent_id` and keep the superseded row, or drop the column from the API dict so nothing implies history is kept.
**Status** fixed (backend, restarted): `parent_id` removed from the API dict and the create body — nothing implies a history is kept (column left in place; user: remove history)

### CL-23 · P4 · Header/gutter counts and the archive-band count disagree while a search is typed
**Where** `CoverLetters.jsx:216, 327` (unfiltered `letters`) vs `:347` (filtered `visible`)
**Actual** With the query `Jane`: header `16 letters · 1 live application`, gutter `16`, band `Archived · 1 letter from rejected applications & skipped jobs`, 2 rows shown. With `Runpod`: band `Archived · 2 letters`. Also, while a query is active the band reads `hide ⌄` regardless of the stored preference, and clicking it flips the stored preference with no visible effect (verified: `v2_cl_archive_open` toggles `0`↔`1` while the rows stay visible).
**Proposed fix** Show `N of M` in the header while filtering, and drive the band's chevron from `archOpen` with the search override made explicit.
**Status** fixed + verified after rebuild: header reads "N of M letters match" while searching; the archive band is inert while a query is active (title explains) and the chevron says "shown while searching"

### CL-24 · P4 · Design deviations (deliberate-looking; listed for the record)
**Where** design `.dc.html` vs both files. Everything measured matched the design unless listed here.
| item | design | code |
|---|---|---|
| count line | `4 letters · 2 linked to applications · Garamond, US Letter defaults` (`:396`) | `16 letters · 1 live application` |
| archive rule | drafts *and* rejected sink to archive (`:422`) | drafts whose job is new/saved/applied stay active (CL:206-213, commented) |
| archive band copy | `… from drafts & rejected applications` (`:126`) | `… from rejected applications & skipped jobs` |
| contact "Display text" cell | `flex: 0 0 118px` (`:196`) | `flex: '0 0 170px'` (ED:339) — measured 170 |
| card chevron | text glyph `›`/`⌄` (`:180`) | rotating 8×8 SVG (ED:43-46) |
| paragraph line-height | `1.55` (`:240`) | `19px` (integer, per the HANDOVER convention) |
| PDF preview | 540 px paper mock with a drop shadow, centred in a 20 px padded scroller (`:266-279`) | full-bleed `<iframe>` of the real server PDF |
| ⋯ menu | View application / Open job posting / Delete (`:167-169`) | + `View job in feed` (ED:294) |
| template control tooltip | lists every template id (`:262`) | `Cover letter template` |
Everything else matched exactly, including: header `22px 30px 16px` + `h1` 30 px Newsreader `line-height 1`; search 280×36 with a `--line-strong` bottom rule; panel `flex 0 0 340px` + `16px 26px 20px 30px`; picker 33 px / radius 8 / `--edge`; voice chips 27 px radius 99; length segments 31 px radius 8 with `fontWeight 600` when on; Generate 36 px radius 99 on `--accent`; gutter head `13px 30px 9px`; rows `13px 15px` radius 10 (69 px tall, integer tops); pending row dashed `--accent` on `--recessed`; editor top bar `10px 24px` on `--surface` with a `--line-soft` rule; context band `9px 24px` on `--surface-2`; Regenerate pill 36 px / `0 19px`; ⋯ 36×36 (accent border + `--accent-soft` when open — measured); left column `flex 0 0 47%` = 579.97 px; cards radius 9, head `10px 14px`, body `2px 14px 14px`; inputs 32 px radius 6; contact cells 29 px; dashed adders 28 px; template/paper controls 24 px; Download 29 px / `0 15px`; modal 460 px radius 12 with `--shadow-modal`, Cancel 33 px / `0 14px`, Regenerate 33 px / `0 17px`, `~30 seconds` footer on `--bg`.
**Status** fixed (d) + decided 2026-09-02: keep all except (d); contact rows in the cover-letter, résumé and persona editors now split 45/55 — controls + Display text on the left, URL + stub (+ ✕) on the right, controls and stub at their previous widths (measured 226/277 in both résumé editors, 251/307 on Persona)

### CL-25 · P4 · Escape closes the Regenerate modal mid-run while Cancel and the scrim refuse
**Where** `CoverLetterEditor.jsx:227` vs `:462, 487`
**Actual** Measured during a live regenerate: Cancel → modal stays (correct), scrim click → modal stays (correct), Escape → modal closes. The run still completes and the poll still reloads, but the user loses the only progress indicator except the ↻ pill spinner.
**Proposed fix** `if (e.key === 'Escape') { onDoc(); if (!regening) setRegenOpen(false) }`.
**Status** fixed + verified after rebuild: Escape ignores a running regenerate (ref-backed check); the modal stays until the run ends

### CL-26 · P4 · The two screens format the same timestamp differently
**Where** `CoverLetters.jsx:7-14` vs `CoverLetterEditor.jsx:17-24`
**Actual** List row: `edited 1d ago` in the sub-line and a bare `1d` in the right column, minimum `1m`, no "just now". Editor: `saved just now · autosaves`, then `5m ago`. Navigating list → editor on a letter saved seconds ago shows `1m` on the list and `just now` in the editor.
**Proposed fix** One shared helper.
**Status** fixed + verified after rebuild: one shared helper (`v2/time.js`: `ago` / `agoShort`) — list sub-line "edited 22m ago", column "22m", editor "saved 23m ago"; "just now" / "now" under a minute on both

### CL-27 · P4 · `POST /cover-letters` returns a context-free row
**Where** `routes_cover_letters.py:180` — `_to_dict(cl, include_json_data=True)` with no `ctx`
**Actual** A create that supplies `job_id` and `resume_id` still comes back with `source_name: null, company: null, title: null, job_url: null, job_status: null, stage: null, has_application: false`, unlike `GET /{id}` which builds the ctx. v2 never creates letters this way, so it is latent; any client that renders the POST response would show a letter with no context.
**Proposed fix** `ctx=_build_ctx([cl], db).get(cl.id)` as in the other handlers.
**Status** fixed + verified (backend, restarted): `POST /cover-letters` returns the same context fields as GET (company/title/source_name)

### CL-28 · P4 · One shared `err` slot in the editor, cleared only by a successful save
**Where** `CoverLetterEditor.jsx:259-260`; set at `:106, 131, 179, 186, 199`
**Actual** Verified with a download 500: `Could not download the PDF.` sits in the top bar indefinitely (a download failure never triggers a save), and it is only cleared by the next successful `PATCH` or by starting a regenerate (`:191`). The string is unbounded and has no ellipsis, so a long backend detail pushes the letter name out of the bar.
**Proposed fix** Per-action messages, or clear on a timer for the non-save ones.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

### CL-29 · P4 · Disabled arrows still take their hover (matches the design — logged so it is not re-found)
**Where** contact ▲▼ (ED:334, 336, `.v2-hover-accent-text`) and paragraph ↑↓ (ED:389, 391, `.v2-parabtn`)
**Actual** The first ▲ at `opacity .35` still turns `--accent` on hover; the first ↑ (colour `--line-strong`, `cursor: default`) still takes the `--surface-2` background. The design applies its `style-hover` to both arrows unconditionally too (`:195`, `:236-237`), so this is a faithful reproduction rather than a defect.
**Status** fixed + verified after rebuild: disabled ▲▼ / ↑↓ arrows no longer take a hover (user: no hover needed)

---

## Verified OK (highlights)

- **Real generation, end to end.** List → pick PM + a saved Scale job + Concise → 202 → optimistic dashed row `Generating — Scale — Senior AI Product Manager, Finance Agents · Professional & direct · Concise` + `~30s`, job picker cleared, gutter `18 → 19`; completed in ~10 s; poll cleared the row, `load()` ran, the new letter appeared first in the list with `PM · Professional & direct · Concise · edited 1m ago`; DB row carries `voice=professional, length=concise, template=garamond, page_format=letter`.
- **Real regenerate, end to end.** Modal preselects the letter's own source/voice/length (`PM` / `Storytelling` / `Detailed` — measured); switching to Formal + Detailed and regenerating took 26 s, kept the user's `palatino`/`a4`, rewrote the body (text differs), and the context band, save status, and template/paper labels all updated together when the modal auto-closed.
- **Every editor field round-trips** through `PATCH → GET`: `header.name`, contact `text`/`url`/`stub`, `recipient.company/manager/address`, `date`, `greeting`, `body_paragraphs[i]`, `closing`, `signature`. Paragraph ↑ ↓ ✕ + add, and contact ▲ ▼ ✕ + add, all persist correctly; the end arrows are genuinely inert; the note updates `3 paragraphs → 2 → 3 → 0 paragraphs`; the stub cell appears exactly when the URL is non-empty and not `mailto:` (measured 1 → 2 → 1).
- **PDF.** `GET /{id}/pdf` returns `application/pdf` for every template/format pair tested (`garamond/letter` 77 461 B, `traditional/a4` 16 480 B, 0-paragraph letter 69 617 B, all `%PDF-`). Download goes through axios with the API key and lands as `ZZTESTPerson_Google_CoverLetter_20240.pdf` (server `Content-Disposition` honoured), 72 550 B, `%PDF-`.
- **Delete.** `window.confirm('Delete "…"? This cannot be undone.')`; dismissing leaves the row (API still 200); accepting deletes it (API 404), navigates to `/v2/cover-letters`, the list count drops, and the letter's tracer links go with it (checked for orphans afterwards: none).
- **Links.** Source-résumé chip → `/v2/resumes/{id}`; `View job in feed` → `/v2/feed?job={id}`; `Open job posting` is a real `<a target="_blank" rel="noopener noreferrer">` to the Greenhouse URL; `View application` → `/v2/applications`; the menu shows only `Delete letter` when the letter has no job/application/url.
- **Empty states.** 0 letters → `No cover letters yet — generate one on the left.` with `0 letters · 0 live applications`; 0 résumés + empty persona → `Nothing to pick yet.` and Generate dimmed with `Pick a résumé and a job first`; 0 jobs → same popover copy; 0 search hits → `Nothing matches that search.`
- **Bad ids.** Random UUID → 404 → error copy; just-deleted id → same; `?job=<dead id>` → Generate posts and gets the backend's `Job not found` inline; `?resume=persona` selects `Persona (full profile)` and the swallowed `GET /api/resumes/persona` 500 has no visible effect.
- **Hostile data.** A 207-character letter name ellipsises at exactly `max-width: 420px` with the full string in the `title`; no horizontal overflow (`scrollWidth == clientWidth == 1440`); a letter with `json_data = {}` renders the client-side defaults (`Dear Hiring Team,` / `Sincerely,` / one empty paragraph) without persisting them (server still `{}` — confirmed).
- **Light vs dark.** Every measured colour differs between themes with no light-only value surviving: rows `#fff/​#e2ddd0` → `rgb(40,37,27)/rgb(62,59,50)`; panel `--bg` `#fcfbf7` → `rgb(30,28,23)`; accent `#3f6b52` → `rgb(141,187,159)` with `--accent-ink` flipping to `rgb(21,20,15)`; stage chip `cc-smartrecruiters` `#e8eef6/#3a5a86` → `rgb(35,47,63)/rgb(163,190,221)`; scrim `rgba(20,19,15,.42)` → `rgba(0,0,0,.58)`; placeholders resolve to `--muted` in both. All ten hovers were re-measured in dark and behave identically.
- **Working hovers** (measured `before → after`): letter row and archived row `--line/--line-soft → --accent` border only (matches design `border-color:#3f6b52`); archive band `--line → --edge` (design `#8a826e`); `.v2-clhead` → `--bg` (design `#faf8f3`); `.v2-dashadd` → accent border + `--hover-soft` (design `#3f6b52` + `#f4f8f5`); `.v2-parabtn` → `--surface-2` (design `#f3f0e8`); `.v2-parabtn-bad` → `--bad-soft` + `--bad` (design `#f7ecea` + `#9c3b30`); `.v2-hover-accent-text` → `--accent`; `.v2-hover-bad-text` → `--bad`; `.v2-bd` on Template/Paper → `--accent` border (design `#3f6b52`); `.v2-menuitem`/`.v2-hover-bad` in the ⋯ menu. No unauthored hovers found: the Generate button, voice chips, length segments, Picker control, search input, Cancel, the scrim and the source-résumé link all measured `changed: []`.
- **Geometry / integer tops.** `assert_int_tops` on the list: 0 fractional at 5 rows, at 16 rows (archive expanded), in dark, and at 1024×700 — the only failure is CL-09. Editor cards/inputs are integer once CL-10 is fixed.
- **Console.** Clean on both screens in both themes for every non-error path (`console: [] pageerrors: [] http4xx: [] reqfailed: []`). The only console noise is the deliberate 4xx/5xx interceptions and one Axios error object from the PDF-500 test.
- **localStorage.** `v2_cl_archive_open` written `'0'` on mount and toggled `'1'`/`'0'` by the band; `v2_cl_sections` written on every card toggle and correctly restored after navigating away and back (`{"headOpen":false,"recipOpen":true,"letterOpen":false}` → Letter card collapsed on return).
- **Voice preset wiring.** `cover_letter_default_voice = "professional"` preselects `Professional & direct` on both the list panel and the Regenerate modal (the modal prefers the letter's own `voice` when it has one — verified with `storytelling`); chip `title` carries the preset `instruction` verbatim; length defaults to `Standard`; all five presets render with the correct on/off tokens.

## Fixed in source (rebuild pending)

- `frontend/src/v2/CoverLetterEditor.jsx:91,126-138` — `pendingPatch` ref; debounced patches now merge instead of replacing (CL-01).
- `frontend/src/v2/CoverLetterEditor.jsx:207-225` — regenerate poll scoped to `cl:{id}` and `clearInterval` moved after a successful reload (CL-02, CL-03).
- `frontend/src/v2/CoverLetterEditor.jsx:328` — integer `lineHeight: '16px'` on the `text · link · stub` hint (CL-10).
- `frontend/src/v2/CoverLetters.jsx:136-145` — `mergeKeep` on the `/resumes` and `/jobs` loaders so a deep-linked row survives (CL-04).
- `frontend/src/v2/CoverLetters.jsx:334-337` — integer `lineHeight: '20px'` on the pending-row label (CL-09).

None of these are verified in the browser — the frontend bundle is not rebuilt (per the brief, `docker compose build` is the wave owner's job). The five changes are all local to these two files.

## P2 triage (2026-09-02)

| id | action | note |
|---|---|---|
| CL-05 | fixed (JSX, rebuild pending) | `loadErr` state + “Couldn’t load your letters · Try again” card; no loading state added, so the empty-copy flash before the first response remains (P3-ish, logged here). |
| CL-06 | fixed (JSX, rebuild pending) | on a run leaving `/monitor/active`, `/monitor/history` is consulted and a `failed` run surfaces its `error` in the generate panel. Editor regenerate path deliberately out of scope. |
| CL-07 | fixed (JSX, rebuild pending) | scrim under the open popover (z 39 vs 40) — the misclick onto the other picker’s option is gone; smaller than lifting the open state to the parent. |

## Couldn't test

- **PDF viewer chrome** (zoom / print / in-viewer download, and the dark-mode seam around the rendered page) — headless Linux has no PDF plug-in; the `<iframe>` is created with a valid blob URL but renders nothing, so the design's paper-vs-`--surface-2` seam could not be judged.
- **`ago()` with a null `updated_at`** (would render `edited  ago` with a double space) — `CoverLetter.updated_at` is server-defaulted and non-null; no way to produce the row without direct SQL.
- **Rail-badge agreement with `/v2/applications` and the Stats KPIs** — cross-screen; only the value produced by this screen's endpoints was checked.
- **Scrollbar-gutter behaviour** of `.v2-gutter`/`.v2-gutter-head` — overlay scrollbars are 0 px wide in this container (HANDOVER).
- **`generate` 400 branches** `Persona has no resume_content` and `cover_letter_prompt setting is empty` — both would require mutating real settings/persona rows; the sibling 400 (`Job has no description` path via a dead job id → `Job not found`) and the 409/500/network branches were exercised instead, and they share the same rendering code (`CL:241` → `CL:320`).

## Scratch data

- Created: cover letter `a31ff294-…` "ZZTEST Cover Letter" (+2 tracer links from its PDF exports), cover letter `2df9031c-…` "ZZTEST LongName…" (207 chars), and one real generation `bd8367bf-…` "Scale — Senior AI Product Manager, Finance Agents" (later regenerated once).
- Deleted: all three — `bd8367bf` through the editor's Delete (which is what verified the delete path), the two ZZTEST rows by API.
- Verified empty: `GET /cover-letters` → 16 rows (the pre-test count), 0 rows matching `ZZTEST`, 0 orphaned `TracerLink` rows, all 8 remaining cover-letter tracer links belong to the user's own letters.
- Reversible edits on rows I did not create: **none**. No global triggers fired. Real LLM calls: 2 (budget 2).

## Summary

- Inventory boxes: **230 total — 176 verified OK `- [x]`, 49 failed `- [!]` (finding id appended), 5 untestable `- [~]`.** (49 boxes, not 49 defects: most findings touch several catalogued lines.)
- Findings: **29** — P1 0 · P2 7 (CL-01…CL-07) · P3 14 (CL-08…CL-21) · P4 8 (CL-22…CL-29).
- Fixes applied in source: **5** (all JSX, rebuild pending) covering CL-01, CL-02, CL-03, CL-04, CL-09, CL-10.
- Backend fixes: none applied (CL-16 and CL-27 both want a cross-cutting change plus a restart — logged as decisions).
- Scratch rows remaining: **0**.
