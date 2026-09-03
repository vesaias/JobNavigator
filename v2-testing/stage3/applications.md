# Stage 3 — Applications
Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (HEAD f60ec5e on `v2-redesign`), themes light+dark, viewport 1440×900 (+ a narrow 1024×700 pass)
Design: `v2-testing/design/Applications Ops.dc.html` · Inventory: `v2-testing/inventory/v2-applications.md` · v1 ref: `frontend/src/components/ApplicationBoard.jsx` · Backend: `backend/api/routes_applications.py`
Scripts: `apps_1.py` (render/geometry/hovers/themes/console), `apps_2.py` (Log modal + create ZZTEST), `apps_3.py` (stage stepper, stale reset, notes autosave, interviews + timezone), `apps_4.py` (interview edge cases, prep modal), `apps_5.py` (copy, filters, sort, narrow, 500/401, counts, delete), `apps_6.py` (hostile data + cleanup), `apps_7.py`/`apps_8.py` (dark tokens, email block)
Artifacts: `v2-testing/artifacts/applications/*.png` (20 shots)
DB at start: 377 applications (30 applied · 347 rejected · 0 interview · 0 offer); at end: 377, zero ZZTEST rows of mine.

---

## Findings

### APPS-01 · P2 · No user feedback on any of the nine mutations — 8 console-only failure paths + 1 swallowed catch
**Where** `Applications.jsx` — `Toast.jsx` is never imported. Failure sites: `:98` (load), `:157` (stage PATCH), `:164` (notes PATCH), `:172` (delete), `:182` (add interview), `:185` (delete interview), `:188` (toggle interview), `:561` (extract), plus `:197` (clipboard, swallowed) and `:551` (`GET /resumes` `.catch(()=>{})`).
**Repro** intercept each endpoint with `status=500`; perform the action.
**Expected + why** `frontend/src/v2/Toast.jsx` exists and its `error` kind deliberately never auto-dismisses (`TTL.error = null`); HANDOVER "Error paths" says to confirm it is wired at *every* failure site. Every other v2 screen pushes toasts.
**Actual** measured on the live bundle — every one of these fails silently:
| path | UI after a 500 | evidence |
|---|---|---|
| stage PATCH | pill flips optimistically, then silently reverts | `patch_500`: optimistic `Offer fontWeight 600` → reverted `Applied 600`; `toast:false` |
| notes PATCH | textarea keeps the text; server never got it | `notes_500`: stored `"ZZTEST lost-keystrokes probe"`, textarea `"ZZTEST notes-that-will-fail"`, `any_error_ui:false` |
| add interview | form stays open with values, nothing added | `add_interview_500`: `n_interviews:0`, `any_error_ui:false` |
| extract | fields left blank, no message | `extract_500`: `visible_error_text:false` |
| load | see APPS-02 | |
Console shows only `AxiosError: Request failed with status code 500`.
**Proposed fix** import `useToasts` and `push({kind:'error', …})` at each site (mirroring the other v2 screens); a `success` toast at least for delete and log-application.
**Status** fixed in source (rebuild pending) — fixed by the toast wiring: `Applications.jsx` now imports `useToasts`/`ToastStack` (`:4`, `:96`, `:381`) and pushes an `error` toast at every failure site (load `:107`, stage PATCH `:171`, notes `:179`, delete `:188`, add/delete/toggle interview `:199`/`:203`/`:207`, prep `:216`, clipboard `:228`, log-modal extract/save), plus a `success` toast on delete and a `progress` toast on the 409 duplicate. Only `GET /resumes` in the Log modal is still a silent `.catch(()=>{})` (chip list, non-blocking) — logged, not fixed.

### APPS-02 · P2 · A failed load is indistinguishable from an empty database
**Where** `Applications.jsx:92-100` — `catch { console.error }` then `setLoaded(true)` unconditionally (`:99`); the only zero-row branch is `:322-324`.
**Repro** `page.route('**/api/applications?**', 500)` → `/v2/applications`.
**Expected + why** HANDOVER ranks "first-run / empty database" and "error paths" as risks 1 and 2; a 500 must not read as "you have no applications".
**Actual** measured (`load_500`): header `"0 applications · 0 in interview · 0 offer"`, four group headers all `0`, body copy **"No applications yet — mark a job applied in the Feed, or log one here."**, detail pane "Select an application.". `retry_control:false`, no word "error" anywhere. Screenshot `apps-load500-light.png`.
On 401 the shell's `jn:unauthorized` modal does appear (`load_401.login_modal:true`) — but the same fake empty screen sits behind it.
**Proposed fix** add `const [err,setErr]=useState(null)`; set it in the catch; render an error card with a Retry button in the list pane instead of the empty-state copy.
**Status** fixed in source (rebuild pending) — `Applications.jsx:78-79` `loadErr` state, set in the `load()` catch (`:104-108`, cleared on `:102`), and `:355-364` renders “Couldn’t load your applications · <status> · Try again” in place of the empty-state copy when `loadErr` is set. Same shape as `Searches.jsx:582-587`.

### APPS-03 · P2 · Interview time is stored as UTC and rendered as local — off by the viewer's UTC offset
**Where** `Applications.jsx:459` (`<input type="datetime-local">`) → `:178` sends the zone-less string verbatim → `routes_applications.py:26` `dt.replace(tzinfo=timezone.utc)` → `Applications.jsx:17-22` `toLocaleString`.
**Repro** browser timezone `America/New_York`; add an interview, type `2026-09-09T14:00`; save.
**Expected + why** the picker is a *local* wall-clock control; the card must read back the same 14:00. `_parse_dt`'s docstring even names the case ("`'2026-09-09T14:00'` has no zone") and then chooses UTC.
**Actual** measured (`interview_added`): stored `when_at = "2026-09-09T14:00:00+00:00"`, card rendered **"Wed, Sep 9, 10:00 AM · Zoom"** — 4 h earlier than typed (`browser_offset_min: 240`). For a user in CET this shows 16:00; the prep bundle (`routes_applications.py:550`) repeats the wrong time.
**Proposed fix** send an absolute instant from the client: `when_at: intWhen ? new Date(intWhen).toISOString() : null` (`:178`). One line, no backend change, and `_parse_dt` then sees a zoned string. (Existing rows keep their stored instant; there are none in the real DB — `with interviews: 0`.)
**Status** fixed + verified in source: `Applications.jsx` sends `when_at` as `new Date(intWhen).toISOString()` (an instant), so the server's UTC store round-trips to the viewer's wall clock

### APPS-04 · P2 · `POST /applications` upserts by job — re-logging the same posting silently overwrites the earlier application
**Where** `routes_applications.py:262-272`; client `Applications.jsx:565-576` has no duplicate check.
**Repro** log a posting, then log the same URL+title+company again with different notes and a different stage.
**Expected + why** the modal copy says "For applications made outside the app"; nothing warns that this is an edit.
**Actual** measured (`upsert`): total stayed 378, `rows_with_title:1`, notes replaced (`"ZZTEST note one"` → `"ZZTEST note TWO — overwrote the first"`), status silently reset `interview → applied`, and a spurious `{from:'interview', to:'applied', source:'ui'}` transition was written into the Stats funnel. `warned: []` — no dialog, no toast.
**Proposed fix** backend: return `409` (or a `{"existing_id": …}` payload) when an Application already exists for the job, and have the modal ask "An application for this posting already exists — update it?".
**Status** fixed + verified (backend): `POST /applications` for a job that already has one → 409 `{message, application_id}` (test added); Log modal opens the existing application on 409; extension popup shows "Already logged"

### APPS-05 · P2 · "Copied ✓" is shown even when the clipboard write fails
**Where** `Applications.jsx:196-199` — `catch { /* clipboard blocked */ }` then `setCopied(true)` unconditionally.
**Repro** open the prep modal in a context without clipboard permission; click Copy.
**Expected + why** the button is the only feedback the flow has; a false confirmation loses the whole bundle silently.
**Actual** measured (`copy_feedback`): `clipboard: "blocked: TypeError"` while the button read **"⧉ Copied ✓"** for the full 1.8 s. The button is also clickable while `prep === 'loading'` (copies `''`), and after a 500 it happily copies the error string (`prep_500_copy`).
**Proposed fix** `setCopied(true)` only inside the `try`; in the catch show "Copy failed — select the text" (or push an error toast); guard `onClick` while `prep === 'loading'`.
**Status** fixed in source (rebuild pending) — `Applications.jsx:221-231`: `copyPrep()` returns early while `prep === 'loading'` or `prep.failed`, `setCopied(true)` moved inside the `try` after the `await`, and a clipboard rejection pushes “Could not copy — select the text and copy it manually”. `openPrep()`’s catch now marks `{failed: true}` (`:213-217`) and also pushes an error toast; `PrepModal` dims the Copy button while `busy` (`:553`, `:570`).

### APPS-06 · P2 · The interview draft form is screen-global, not per application
**Where** state lives in the parent `Applications.jsx:82-84`; `Detail` only receives it. Nothing resets it on `sel` change.
**Repro** open "+ Add interview" on row A, type a "What", click row B, click "Add interview".
**Expected + why** a half-filled form belongs to the application it was opened on; posting it against another one is silent data corruption.
**Actual** measured (`draft_leak`): after switching rows the form was still open (`form_still_open:1`) with `value:"ZZTEST draft leak"` while the detail pane showed **"Sr. Product Manager"**. `addInterview` (`:174`) posts to `d.id` — the *new* application.
**Proposed fix** `useEffect(() => { setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep('') }, [sel])` in `Applications`.
**Status** fixed in source (rebuild pending) — `Applications.jsx:112-114`: `useEffect(… , [sel])` closes the form and clears `intWhat/intWhen/intWhere/intPrep` whenever the selection changes, so a draft can no longer be posted against another application. Discard-on-switch (not carry-per-row) chosen deliberately: the alternative keeps a per-id draft map alive with no UI to show it exists.

### APPS-07 · P2 · Clicking the already-active stage, editing notes, or adding an interview bumps `updated_at` and clears the stale indicator
**Where** `routes_applications.py:377` (`app.updated_at = utcnow()` runs for every PATCH), `:473` (add interview); client `Applications.jsx:405` sends the PATCH even when `on === true` (no guard), `:44` `isStale`, `:145` `recent` sort.
**Repro** back-date an application 20 days, click its already-active "Applied" pill.
**Expected + why** the `{N}d` cell and "N waiting >7d" are the screen's only ageing signal; a no-op click must not reset them, and `db.py:242` already declines to record a transition, so the backend agrees nothing happened.
**Actual** measured (`active_pill_bump`): row cell `20d` amber `rgb(154,91,40)` (`--warn`, tooltip "No movement for 20 days") → **`0d` muted** (tooltip "Last activity 0d ago"); `updated_at 2026-08-13 → 2026-09-02`; `status_transitions` unchanged at 6; header `26 waiting >7d → 25 waiting >7d`. The same bump happens on every notes keystroke burst and on every interview add/toggle.
**Proposed fix** client: `onClick={() => { if (d.status !== s.id) onStage(s.id) }}` (`:405`) stops the no-op case. The notes/interview case needs a backend decision — either don't touch `updated_at` for non-status PATCHes, or introduce a separate `last_activity_at` for the ageing signal.
**Status** fixed in source, restart pending (backend) — both halves of the no-op case, no new column: `routes_applications.py:368-386` PATCH now tracks a `changed` flag, drops a `status` equal to the current one (matching `db.py:242`, which already declines the transition) and only assigns `app.updated_at` when something actually changed; `Applications.jsx:445` no longer fires the PATCH for the already-active pill. **Needs `docker compose restart backend`.** Out of scope and still true: a notes edit or an interview add legitimately bumps `updated_at`, so the ageing signal still counts those as movement — splitting `last_activity_at` from `updated_at` remains a separate decision.

### APPS-08 · P3 · Every list row lands on a fractional pixel — **fixed in source**
**Where** `Applications.jsx:222` (count line), `:293` (group header), `:249` (company popover item).
**Actual** measured: `assert_int_tops('.v2-arow')` → **30 of 30 fractional**, tops `174.25, 223.25, 272.25 …`; the whole list pane sat at `top 135.5`; the company popover had **92 of 122** fractional items. Cause is the Tailwind-preflight `line-height:1.5` chain: the header count span is `13 × 1.5 = 19.5px` → header 90.5 → pane 135.5, and the group header's `10.5px` label is `15.75px` → header 32.75.
**Proposed fix** applied — explicit integer line-heights: count span `20px`, group header `16px`, popover item `18px`. Derived: header 22+30+3+20+16 = **91**, toolbar 30+14+1 = **45**, pane top **136**, +6 padding → first group **142**, group header 12+16+5 = **33** → first row **175**, rows 46+3 = 49. All integers.
**Status** fixed in source (rebuild pending) — `Applications.jsx:222, :293, :249`.

### APPS-09 · P3 · The detail body collapses to an unusable 20 px at 1024 px width
**Where** `Applications.jsx:418-419` — content column `flex:1.2, minWidth:0`; history rail `:490` `flex:'0 0 250px'`; list pane `:288` fixed at 472 px.
**Repro** viewport 1024×700 with a row selected.
**Actual** measured (`narrow_detail`): list 472, detail 346 → body columns **`[20, 250]`** — the notes textarea is **26 px** wide, the serif title 97 px (wraps to many lines). No horizontal page overflow, so nothing signals the breakage. Screenshot `apps-narrow-detail.png`.
**Expected + why** HANDOVER risk 8: "Narrow viewports. Almost certainly never tested." The 250 px rail is a hard floor while the list stays fixed.
**Proposed fix** drop the history rail below the content (or hide it) under a width threshold, and/or let the list pane shrink: `flex:'0 1 472px'` + a `minWidth` on the rail's container.
**Status** fixed in source: detail body wraps (`flexWrap`), content `flex: 1.2 1 320px`, history rail `flex: 1 0 250px` drops below the content when the pane is narrow

### APPS-10 · P3 · `.v2-hover-accent`'s colour half never fires (Prep modal ✕) — cross-screen
**Where** `theme.css:129` `.v2-hover-accent:hover { background:var(--surface-2); color:var(--text); }` (no `!important`) vs the inline `color:'var(--muted)'` on `Applications.jsx:519`.
**Expected + why** design line 226: `style-hover="background:#f3f0e8;color:#1b1a16"` — both properties. HANDOVER: "Inline styles beat class `:hover` … needs `!important` or it silently does nothing. This has bitten on five separate screens."
**Actual** measured (`hover_prep_close`): `before {bg: rgba(0,0,0,0), color: rgb(109,104,98)}` → `after {bg: rgb(246,244,238), color: rgb(109,104,98)}` — `changed: ["backgroundColor"]` only.
**Not fixed on purpose**: `.v2-hover-accent` is used by 15 elements across Applications, Companies (×2), JobFeed (×5), ResumeEditor, ResumeSections (×2), Searches, Settings (×2) — most with the same inline `color:var(--muted)`, so the same hover is dead everywhere. Adding `!important` to a shared class while six other agents test those screens is out of scope.
**Status** fixed: `.v2-hover-accent` colour half hardened in theme.css (cross-screen); the Prep modal Close button now carries the pill hover (`v2-bdc`) — user: "Close button has no hover"

### APPS-11 · P3 · Add-interview has no in-flight guard — a double click creates two interviews
**Where** `Applications.jsx:174-183` (`addInterview`), button `:472` has no `disabled`/busy state (unlike the Log modal's `busy ? undefined : save` at `:636`).
**Actual** measured (`double_submit`): two `element.click()` calls in one tick → `n: 2`, `whats: ["ZZTEST double", "ZZTEST double"]`.
**Proposed fix** a `busy` ref/state around the POST, plus `opacity .6` + `onClick={busy?undefined:addInterview}` mirroring `:636`.
**Status** fixed in source: `intBusy` guard around the POST; button inert while busy

### APPS-12 · P3 · A completely blank interview form creates an "Interview / Unscheduled" card
**Where** `Applications.jsx:174-180` — `what` defaults to `'Interview'`, everything else to `null`; no client validation.
**Actual** measured (`blank_form`): opening the form and clicking Add with nothing typed produced `{what:"Interview", when_at:null, where_text:null, prep:null}`, rendered as `Interview | SCHEDULED | ✕ | Unscheduled`.
**Proposed fix** disable "Add interview" while `!intWhat.trim() && !intWhen`.
**Status** fixed in source: Add interview is disabled (opacity .5, no handler) until a title or a time is entered

### APPS-13 · P3 · Interview ✕ deletes with no confirm and no undo
**Where** `Applications.jsx:184-186` / `:442`.
**Actual** measured (`interview_delete`): before 1 → after 0, `confirms: 0`. Contrast `remove()` (`:171`) which does confirm for the application itself, and the design (line 176) which has **no ✕ at all** — the delete affordance is an addition to the design.
**Proposed fix** `window.confirm` (matching `:171`) or an undo toast.
**Status** fixed in source: interview ✕ removes immediately and shows a 5 s undo toast that re-creates the interview (user chose undo over confirm)

### APPS-14 · P3 · A filtered-out application stays open in the detail pane with no indication
**Where** `Applications.jsx:152` — `d` is resolved from `apps`, not `visible`.
**Actual** measured (`filtered_out`): with the search set to `zzzz-no-match` the list read `APPLIED 0 / INTERVIEW 0 / OFFER 0 / REJECTED 0 / "Nothing matches those filters."` and `0 of 378 shown`, while the detail pane still showed **"ZZTEST Staff Engineer"** and all of its controls. Screenshot `apps-nomatch-light.png`.
**Proposed fix** either keep it (defensible — you don't lose your place) but add a hint line, or blank the detail when `!visible.some(a => a.id === sel)`.
**Status** decided 2026-09-02: keep — the open application stays in the detail pane when filtered out

### APPS-15 · P3 · A hand-logged application's history reads "Discovered via a company scrape"
**Where** `Applications.jsx:29-33` maps `direct → 'a company scrape'`; `routes_applications.py:242` stamps `source="direct"` on jobs created *by the Log modal*.
**Actual** measured (`after_save.history`): `["Moved to Interview", "Discovered via a company scrape", "Applied with unknown résumé"]` for a row created seconds earlier through the modal.
**Proposed fix** map `direct → 'the Log application form'` in `srcLabel`, or stamp a distinct `source="manual"` in `create_application` (backend; would need a fallback for existing rows).
**Status** fixed: backend stamps `source="manual"` on jobs created by the Log modal/extension (no other backend code filters on `direct`); UI maps `manual` → "the Log application form", existing `direct` rows unchanged

### APPS-16 · P3 · Design deviations in layout and copy
Grouped; all measured design-vs-built. Per the addendum these are decisions unless noted.
| # | design (`.dc.html` line) | built | measured |
|---|---|---|---|
| a | list pane `flex:0 0 340px` (:89) | `472px` (`:288`) | 472.0 — matches the **Feed's** 472 (`JobFeed.jsx:694`, and the Feed design's own `flex:0 0 472px`), so this reads as deliberate cross-screen consistency |
| b | Cached / Live / ⋯ pills `height:25px; padding:0 10px; font-size:11.5px`, ⋯ `25×25` (:138-140) | `ACT_BTN` 30 px / `0 14px` / 13 px, ⋯ `30×30` (`:58-62`) | 30 / 30×30 / 13px — the code comment says "same metrics as the Feed's Open ↗", again deliberate |
| c | body order **Notes → Last email → Interviews → Cached posting** (:159-198) | **Last email → Interviews → Notes** | `body_labels` = `["Interviews · 0", "Notes · autosaves", "History"]` |
| d | "Cached posting · application day" 140 px preview panel (:195-198) | **absent** — replaced by the header "Cached" link | not rendered |
| e | notes label "Notes · **saves on blur**" (:160) | "Notes · **autosaves**" (`:482`) | the built behaviour really is debounced autosave, so the built label is the correct one |
| f | group label "Rejected · kept for stats" (:416) | "Rejected" (`:42`) | measured `"Rejected347›"` |
| g | prep modal "Prep **bundle**", "paste into the **LLM**", footer "Posting text and résumé content are included in the real export" (:224-232) | "Prep **handover**", "the **AI**", "Edit the closing ask in Settings → AI" | measured verbatim |
| h | prep trigger label "Prep for LLM" (:463) | "Generate prep handover for AI" (`:434`) | 202.6 px wide vs a design pill of ~90 px |
| i | interview form = 3 placeholder-only inputs, no Where (:183-187) | 4 labelled inputs incl. Where + `datetime-local` (`:451-474`) | all four at 29 px ✓ — a functional improvement (and the source of APPS-03) |
| j | copied button fill `#2f6b4a` (:489) | `var(--good)` (`:529`) | `--good` **is** `#3f6b52` = `--accent` in light and `#8dbb9f` = `--accent` in dark, so the fill **does not change** when copied — only the label does. This one looks accidental (P4). |
**Status** decided 2026-09-02: keep all as deliberate consistency changes

### APPS-17 · P3 · The Log modal demands a URL although its own copy says it is for off-app applications
**Where** `Applications.jsx:566` — `if (!title || !company || !url) alert('URL, title and company are all required')`. The design's Save has no validation at all.
**Actual** measured (`validation_alert`): `{type:'alert', msg:'URL, title and company are all required'}`. `create_application` genuinely needs a URL (it is the `external_id` seed, `routes_applications.py:232`), so this is a backend constraint surfacing as a raw `window.alert` — the only `alert()` on the whole screen.
**Proposed fix** either accept a blank URL (synthesise `manual://{company}/{title}` for the external_id) or say so in the field label; replace `window.alert` with inline field errors.
**Status** fixed + decided: URL stays required (it seeds the dedup id); the message now says why and the first empty field is focused instead of a bare alert

### APPS-18 · P4 · "Cached" never appears for a freshly logged application until a later refetch
**Where** page caching is a `BackgroundTask` (`routes_applications.py:314`); `onSaved` → `load(id)` (`:341`) runs immediately.
**Actual** measured: `after_save.has_cached_btn: 0` and `has_cached_page:false`; on the next visit `cached_btn.present: 1`. The footer promises "The posting is cached on save".
**Proposed fix** a single delayed `load()` (~5 s) after a save, or an optimistic "caching…" chip.
**Status** fixed in source: one delayed reload 5 s after a save so the Cached chip appears without a manual refresh

### APPS-19 · P4 · The rail "Applications" badge is never refreshed by this screen
**Where** `V2App.jsx:58-71` fetches counts once on shell mount.
**Actual** measured (`delete_application`): after deleting, the header went `378 → 377` while `rail_after` stayed **`Applications378`**. Same after logging a new one.
**Proposed fix** a `jn:counts-changed` window event the shell listens for, dispatched after log/delete.
**Status** fixed in source: Applications dispatches `jn:counts-changed` after log/delete; the shell re-reads all rail counts on that event

### APPS-20 · P4 · Selected row and hovered row are the same colour
**Where** `:304` `background: sel === a.id ? 'var(--surface-2)' : 'transparent'` vs `theme.css:151` `.v2-arow:hover { background: var(--surface-2) !important }`.
**Actual** measured: hovering an unselected row → `rgb(246,244,238)`; the selected row's background → `rgb(246,244,238)`. Identical.
**Note** the design has the same collision (`style-hover="background:#f3f0e8"` at :100, `bg: i===S.sel ? "#f3f0e8"` at :435), so this is inherited, not introduced.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

### APPS-21 · P4 · "Applied on" is a UTC date sent as UTC midnight
**Where** `:546` `new Date().toISOString().slice(0,10)` (UTC calendar date, not local), `:572` `new Date(when).toISOString()` (parses a date-only string as UTC midnight).
**Actual** measured: `applied_at` came back `"2026-09-02T00:00:00+00:00"` for a row created at 11:10 UTC, so the freshly created row's history immediately reads **"Applied with PM · 11h ago"**. Near local midnight the default date is also off by a day for any non-UTC user (`date_default` and `today_local` agreed only because the test ran at 07:10 EDT).
**Proposed fix** build the default from local parts and send `new Date(when + 'T12:00:00')` (or keep the date-only string and let the backend parse it as a date).
**Status** fixed in source: default date built from local calendar parts; sent as local noon so it never lands on the previous UTC day

### APPS-22 · P4 · Smaller items (grouped)
- `countLine` (`:115`) never pluralises "offer" — measured header `"… · 0 offer"`; would read "2 offer".
- "Recent activity" sorts on **whole days** (`:145` `daysSince`), so every row touched today ties and falls back to alphabetical-by-title — it is not most-recent-first within a day.
- `limit: 2000` (`:94`) is a hard cap and `data.total` (which the API returns) is ignored — past 2000 rows both the list and the header count would silently truncate. Currently 378, so latent.
- The `cv` span (`:370-372`) is rendered in `--accent` + `fontWeight 500` even with no tailored résumé; measured `cursor: default`, `color: rgb(63,107,82)`, tooltip "No tailored résumé for this job" — it looks like a link and is inert.
- Escape (`:106`) closes the Log modal and discards every typed field with no confirm — measured `escape_discards.company_after_reopen: ""`.
- `closeAll` is passed to `Detail` (`:330`) and destructured (`:347`) but never used; `GROUP_LABEL` (`:42`) duplicates `STAGES[].label`. Dead code.
- Legacy statuses `ghosted`/`withdrawn` (referenced in `Stats.jsx:168`) have no group in `STAGES`, so such rows would be invisible in the list while still counted in the header. None exist today (`Counter({'rejected':347,'applied':30})`).
- A notes save does not refresh the row: measured `age_cell_after: "20d"` after the PATCH had already reset `updated_at` server-side. The list and the "N waiting >7d" header stay stale until the next load.
**Status** fixed + verified after rebuild (all eight): "offers" pluralised; Recent/Oldest sort on timestamps; header reads the server total and says "showing the first N" past the 2000-row page; résumé name is plain text unless a tailored copy exists; Escape/close on a dirty Log modal asks "Discard this application?"; `closeAll` prop + `GROUP_LABEL` removed; legacy statuses (ghosted/withdrawn) list under Rejected; a notes save reloads the row so its age and the header follow

### APPS-23 · P4 · The "Cached" link bypasses the API-key header (works only via the session cookie)
**Where** `:376` — a plain `<a href="/api/jobs/{id}/cached-page">`, so the axios `X-API-Key` interceptor (`api.js`) does not apply.
**Actual** measured both ways: server-side request without a key → **401 `{"detail":"API key required"}"`**; the same URL fetched from the authenticated browser → **200**. `main.py:137` sets `jn_session`, so in the real app the link works. It would 401 in a new tab for any deployment where the cookie is absent.
**Status** decided 2026-09-02: ignore (works with the session cookie; only a cookie-less tab would 401)

---

## Verified working (measured, no defect)

- **Stage stepper** — all four transitions fire `PATCH /applications/{id} {status}` and the backend records exactly one transition each with `source:'ui'`: `applied→interview`, `interview→offer`, `offer→rejected`, `rejected→applied`, transition count 2→6. Row moves group; pill tokens correct in both themes (active `--accent`/`--accent-soft`, Rejected `--bad`/`--bad-soft`; dark: `#8dbb9f`/`#243029`).
- **Notes autosave** — 0 PATCHes at 400 ms, 1 at 1100 ms (700 ms debounce ✓); blur flushes immediately ✓; both values round-tripped through the API. The "keystrokes lost on navigate" hypothesis in the inventory did **not** reproduce: clicking any nav element blurs the textarea first, so the flush runs (`notes_lost_on_navigate.stored` = the typed text).
- **Interviews** — add / toggle (`scheduled ⇄ done`, chip `--accent-soft`+`--good` → `--surface-2`+`--text-2`) / delete all work and re-fetch; `Interviews · N` tracks the array.
- **Prep bundle** — `GET /applications/{id}/prep` **makes no LLM call** (assembled server-side from job + résumé + posting + the `prep_ask` setting); `/monitor/history` unchanged before/after. 1096-char bundle rendered in the `<pre>` (mono 11px / 17.6px line-height / `pre-wrap`) ✓; scrim click, ✕ and Escape all close ✓; the label resets after 1.8 s ✓.
- **Log modal** — geometry matches design exactly (card 520 px / radius 12, fields 33 px, URL field mono 11 px, stage chips 33 px); validation alert ✓; résumé chip single-select round-trips (`cv_version_used: "PM"` → meta line "applied with PM") ✓; stage chip binds (`status:"interview"` on save) ✓; `POST /applications/extract` works against a public URL and correctly rejects `http://127.0.0.1:8000/health` with **400 "Unsafe URL: '127.0.0.1' resolves to non-public address"** ✓.
- **Delete** — confirm text `Delete the application for "ZZTEST Staff Engineer"?`; row removed; **linked job flipped `applied → saved`** (`routes_applications.py:391-393`) ✓; header 378→377; detail auto-selects the first remaining row.
- **Filters & sort** — company popover 240×340 with a live/closed split at index 24 (live `--text-2`, closed `--muted`, tooltip "Every application here is rejected") ✓; multi-select stays open on click ✓; pill turns accent and reads "Company · 1" ✓; "1 of 378 shown" ✓; group collapse 31→0 rows with the count retained ✓; all three sorts verified (`oldest`→52d first, `company`→Adobe/Amazon/Amazon, `recent`→0d first).
- **Dismissal** — outside click and Escape close both popovers and the ⋯ menu; clicks inside them do not.
- **Hovers** — every `style-hover` in the design is present and nothing extra: `.v2-arow`→`--surface-2`, `.v2-menuitem`→`--surface-2`, `.v2-bd`→border `--accent` (⋯, stage pills incl. Rejected), `.v2-bdc`→border+colour `--accent` (Cached, Live, Prep, Cancel, + Add interview), `.v2-hover-bad`→`--bad-soft` (Delete). The controls the design gives no hover (Log application, Company pill, Sort trigger, group headers) have none. Only exception: APPS-10.
- **Themes** — every measured element differs between light and dark, no light-only value survives: rows, stage pills, notes, Log button, modal card/scrim/inputs, prep modal, interview form, email quote, history dots (`--stage-applied` `#3a5a86`→`#a3bedd`, `--warn` `#9a5b28`→`#d4a06a`, `--line-strong`), stale amber, ✉ glyph.
- **Email block** — label 9.5 px `--muted`; quote 2 px left border `--accent` (`#3f6b52`→`#8dbb9f`), `--bg` fill, `0 8px 8px 0` radius, italic, `10px 12px` padding — matches design lines 164-165 in both themes.
- **Hostile data** — a 210-char title: row keeps its 46 px height with `text-overflow: ellipsis` (362.6 px visible of 1255 px) and a full 210-char `title` tooltip; the detail header wraps to 4 lines (105.8 px) with no clipping and no body overflow (`scrollH === clientH`); null salary + null location → "No posting details captured"; no company set is not reachable (all 378 rows have one).
- **Deep links** — ⋯ → "View job in feed" navigates to `/v2/feed?job={job_id}` ✓; "Open cover letter" correctly absent when `has_cover_letter` is false; unknown query params (`?app=<random uuid>&job=nope`) are ignored with no console error.
- **Console** — clean (0 errors, 0 page errors, 0 failed requests) on every non-intercepted run, light and dark.
- **Counts all agree** — header `378` = rail badge `378` = `GET /applications.total` `378` = `GET /stats.total_applications` `378`; group counts `31+0+0+347 = 378`; `stats.application_statuses {applied:31, rejected:347}` matches the group headers; company popover `ZZTEST Industries 1` matches the Companies screen's `application_count: 1`.

---

## Fixed in source
- `frontend/src/v2/Applications.jsx:222` — count-line span given `lineHeight:'20px'` (was 19.5 px from the inherited 1.5), which put the whole list pane on `top 135.5`.
- `frontend/src/v2/Applications.jsx:293` — stage-group header given `lineHeight:'16px'` (was 15.75 px → 32.75 px header, the source of every `x.25` row top).
- `frontend/src/v2/Applications.jsx:249` — company-popover item given `lineHeight:'18px'` (92 of 122 items were fractional).
All three are JSX → **fixed in source, rebuild pending** (unverified until the frontend image is rebuilt). Derived post-fix geometry: header 91, toolbar 45, pane top 136, first group header 142 (h 33), first row 175, rows 46+3.

## P2 triage (2026-09-02)

| id | action | note |
|---|---|---|
| APPS-01 | fixed by toast wiring | verified in source: `useToasts`/`ToastStack` mounted, `error` toast at all 8 previously console-only paths + the swallowed clipboard catch; `GET /resumes` chip list still silent (P4, non-blocking). |
| APPS-02 | fixed (JSX, rebuild pending) | `loadErr` state + “Couldn’t load your applications · Try again” card replaces the empty-state copy; mirrors `Searches.jsx`. |
| APPS-05 | fixed (JSX, rebuild pending) | `await` the clipboard write, “Copied ✓” only on success, error toast on failure, copy blocked while loading / after a failed prep build (button dimmed). |
| APPS-06 | fixed (JSX, rebuild pending) | draft reset on `sel` change — a half-filled interview can no longer be filed against another application. |
| APPS-07 | fixed (backend + JSX), **restart pending** | no-op stage PATCH no longer bumps `updated_at`; client stops sending it at all. Notes/interview bumps left as-is (separate `last_activity_at` decision). |

## Couldn't test
- **"Building the bundle…" loading state** (`:523`) — the prep endpoint returned in <300 ms even on the first call, so the loading text never rendered long enough to sample. Verified by code inspection only.
- **"Posting URL · reading…"** (`:588`) — same: the real extract resolved before the DOM could be sampled, and a route-fulfilled stub is instantaneous. Verified by code inspection only.
- **Empty company popover** (`:243`, "empty 240 px box") — unreachable: 122 companies in the real DB and no way to reach zero without an empty database. Deferred to the empty-DB pass.
- **`ghosted`/`withdrawn` legacy rows** — none exist; the "invisible but counted" behaviour is reasoned from `STAGES` (`:35-40`), not observed.
- **>2000 applications truncation** — 378 rows; latent only.
- **Empty `data.text` from `/prep`** (`:523`) — the endpoint always returns a bundle; unreachable without stubbing.
- **Résumé chip list empty / errored** (`:551`, `:606`) — 4 base résumés exist and the error path is the swallowed `.catch(()=>{})` already logged under APPS-01.
- **Detail eyebrow with no company** (`:362`, no `Unknown Company` fallback) — unreachable: all 378 rows have a company.
- The 404 seen once on `/v2/feed` after the deep-link hop belongs to the Feed screen, not this one.
(8 inventory boxes marked `[~]`.)

## Scratch data
- Created: 2 applications (`ZZTEST Staff Engineer`, `ZZTEST Staff Platform Engineer …` 210 chars), their 2 jobs (`https://example.com/zztest-*`), 5 interviews, 1 company (`ZZTEST Industries`).
- Deleted: **all of the above.** Verified: `GET /applications?limit=2000` → `total 378 → 377` (the pre-test baseline), `zztest: []`; DB query for `Job.title LIKE '%ZZTEST%'` owned by me → 0; `Interview.what LIKE '%ZZTEST%'` → 0; company `ZZTEST Industries` → gone.
- Reversible edits to my own scratch row only: `updated_at` back-dated 20 days three times (to exercise the stale indicator) — the row was deleted afterwards. **No real row was mutated at any point.**
- ⚠️ **Not mine, left in place**: 9 `ZZTEST*` **jobs** and 2 `ZZTEST*` **companies** from other agents' runs — `ZZTEST scored with full report`, `ZZTEST quick scored no report`, `ZZTEST null cv_scores and no url`, `ZZTEST scored by tailored resume`, `ZZTEST skipped row`, `ZZTEST ignored row`, `ZZTEST applied with cached page` (status `applied` — it is what gives `ZZTEST Alpha` an `application_count` of 1), `ZZTEST job with no company`, `ZZTEST Principal Staff Senior Lead Director of Technical Pro…`; companies `ZZTEST Alpha` and `ZZTEST Bundesdruckerei Digital Solutions International GmbH …`. Reported, not deleted (not my rows).

---

## Summary

**Inventory boxes:** 154 total — **102 verified OK** `[x]`, **44 failed** `[!]` (each carries its finding id in `v2-testing/inventory/v2-applications.md`), **8 untestable** `[~]`. The 44 failures collapse into the 23 findings below (several boxes describe the same defect from different angles).

**Findings by severity:** P1 0 · **P2 7** (APPS-01…07) · **P3 10** (APPS-08…17) · **P4 6** (APPS-18…23).

**Fixes applied:** 3, all in `Applications.jsx` (integer line-heights, rebuild pending). No backend edit was made, so **no backend restart is needed from this screen**.

**Highest-value items for the user:** APPS-03 (interview times are silently wrong by the UTC offset — the one finding that produces bad data a user would act on), APPS-04 (re-logging silently overwrites), APPS-02 + APPS-01 (a broken backend looks like an empty pipeline), APPS-06 (a draft interview can be filed against the wrong application).

**Scratch rows remaining: 0** (mine). 11 rows from other agents flagged above.
