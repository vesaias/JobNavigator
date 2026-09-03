# Stage 3 — Résumés (Shelf + Editor)
Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (HEAD f60ec5e, on top of 9ed8963), themes light+dark, viewport 1440×900 (+ a 1024×700 pass)
Design: `v2-testing/design/Resumes Home D.dc.html` (read in full, markup + `text/x-dc`)  Inventory: `v2-testing/inventory/v2-resumes.md`
Scripts (scratchpad → `/tmp/v2t/` in the backend container): `res_1.py` … `res_16.py`
v1 reference: `frontend/src/components/ResumeBuilder.jsx`, `ResumeContentEditor.jsx`; backend `backend/api/routes_resumes.py`

Live data at test time: 4 bases (PM 45 live / 255 archived · TPgM 0/0 · PjM 2/1 · PjM FinTech 0/1), Persona 2 live / 39 archived,
`total_copies` 49, `archived` 296, `GET /resumes?is_base=false` → 345 = 49 + 296, `GET /resumes` → 349. Rail badge (`?is_base=true`) → 4.
**All counts agree**: Σ`copy_count` + persona = 49 = `total_copies`; Σ`archived_count` + persona = 296 = `len(archived)` = `archived_count`;
rail badge 4 = `bases.length` 4 = rendered base cards 4; header subtitle string matched the API exactly, byte for byte, in both themes.

---

## Findings

### RES-01 · P1 · A rejected autosave is completely silent — the status line still says "saved just now"
**Where** `frontend/src/v2/ResumeEditor.jsx:246-253` (`persist`), route `/v2/resumes/:id`
**Repro** open any résumé, intercept `PATCH /api/resumes/*` → 500, type in *Full name*, wait 2.5 s.
**Expected + why** every other write on this screen surfaces failure as an `error` toast (`:128`, `:149`, `:204`, `:219`, `:225`, `:230`), and `Toast.jsx:21` gives `error` a null TTL precisely so "a failure that evaporates before you read it may as well not exist". The autosave is the *only* write that can lose typed text.
**Actual** measured: status text after the failed PATCH = `'saved just now · autosaves'`; toast count 0; `GET /resumes/{id}` still returned the pre-edit value `'ZZTEST Person'`. The catch at `:250` is `console.error(e)` and `savedAt` is left at its last successful value, so the reading is not just missing — it is affirmatively wrong.
**Proposed fix** in the catch: `pushToast({ kind: 'error', msg: 'Could not save — your last change is not stored.' })` and set a `saveFailed` flag that makes the status line read "not saved" until the next success.
**Status** fixed + verified after rebuild (`ResumeEditor.jsx:250` autosave catch → error toast "Save failed — your last edit is not stored", `savedAt` cleared; measured on PATCH 500)

### RES-02 · P2 · Skills ▲▼ reorder was never persisted — the UI showed the new order until reload, then snapped back
**Where** `backend/api/routes_resumes.py:958-976` (`update_resume`); control at `ResumeSections.jsx:280-284`
**Repro** open a résumé with ≥2 skill rows, click ▼ on the first row, reload.
**Expected + why** `move()` rebuilds `d.skills` from swapped entries and calls `onData` → `persist({json_data})`, so the new order must reach the DB.
**Actual** measured before the fix — DOM after ▼: `['Beta','Alpha']`; `GET /resumes/{id}` → `['Alpha','Beta']`; after reload the DOM was back to `['Alpha','Beta']`. Reproduced at API level with no browser: `PATCH {"Beta":"b","Alpha":"a"}` over `{"Alpha":"a","Beta":"b"}` returned 200 and read back **unchanged**; adding a key made the same PATCH stick. Cause: SQLAlchemy decides whether to emit an UPDATE by comparing old `==` new, and two dicts with the same pairs in a different order are equal in Python, so the column was never marked dirty (`resume.updated_at` was, which is why the request looked successful).
**Proposed fix** `flag_modified(resume, "json_data")` after `setattr`.
**Status** fixed + verified (backend) — after the restart: API `['Alpha','Beta','Gamma']` → PATCH reorder → `['Gamma','Alpha','Beta']` PASS, second reorder PASS; UI ▼ → DOM `['Gamma','Beta','Alpha']` = API = after reload. `name`/`template`/`page_format` PATCHes still round-trip.

### RES-03 · P2 · "Import PDF" creates **two** base résumés
**Where** `frontend/src/v2/Resumes.jsx:253-262` (`AddModal.importPdf`) vs `backend/api/routes_resumes.py:1150-1163`
**Repro** New résumé → Import PDF → pick a text PDF.
**Expected + why** one import, one row.
**Actual** `POST /resumes/import-pdf` already builds and commits a `Resume` (`routes_resumes.py:1152-1161`) and returns it via `_resume_to_dict(include_json_data=True)`; the client then fires a second `POST /resumes` with `parsed.json_data`. Measured request sequence with the import stubbed: `['/resumes/import-pdf', '/resumes']` — two creates. The orphan carries the filename as its name and is invisible until it appears as an extra card on the shelf.
**Proposed fix** reuse the row the endpoint created; `PATCH` its `name` when the user typed one; keep the old two-step as a fallback for a response without an `id`.
**Status** fixed in source (rebuild pending) — `Resumes.jsx:253-268`

### RES-04 · P2 · A skills category containing a "." makes its value field inert
**Where** `ResumeSections.jsx:298` (`setField(\`skills.${k}\`, …)`) + `:34-37`
**Repro** rename a category to `A.B`, then type in its values field.
**Expected + why** the value is stored under the literal key `"A.B"`.
**Actual** measured: value field left at its old text; `GET` returned `{"A.B": "Go · Python"}` — the typed "dotted" never landed. `setField` splits the path on `.`, walks `d.skills.A` (undefined), hits the `if (o && typeof o === 'object')` guard and writes nothing — while `mutate` still fires a PATCH, so the save indicator says it saved. Dots in a category are plausible (".NET", "Node.js" as a heading).
**Proposed fix** give `SkillsEditor` a direct mutator (`mutate(d => { d.skills[k] = v })`) instead of routing through the dotted-path helper.
**Status** fixed in source (rebuild pending): `ResumeSections.jsx:283-286` — `SkillsEditor` writes `d.skills[k]` directly via a new `setVal()` instead of the dotted-path `setField`; the `↩` revert uses it too, and `setField` is no longer passed to this editor. `setField` itself is untouched (it is still correct for every fixed-key path). Closes PERS-03.

### RES-05 · P2 · Renaming a skills category onto an existing one silently destroys a row
**Where** `ResumeSections.jsx:279` (`rename`)
**Repro** two rows `Languages` / `Skill 2`; rename `Skill 2` → `Languages`, blur.
**Expected + why** either a rejection or a merge the user is told about.
**Actual** measured: `{'Languages': 'Go · Python', 'Skill 2': ''}` → `{'Languages': 'Go · Python'}`. Two rows became one; the later value wins and the other is gone. No confirm, no toast, no undo.
**Proposed fix** refuse the rename when the key already exists (revert the uncontrolled input and flash the field), or append a suffix.
**Status** fixed in source (rebuild pending): `ResumeSections.jsx:287-298` (`rename`), `:313` (`onBlur`) — `rename()` returns a boolean and refuses a collision, a blank name and a `DANGEROUS` key; `onBlur` reverts the uncontrolled input to the old key when it returns false, and a new `onError` prop (plumbed through `SectionEditor`, wired to `pushToast` in `ResumeEditor.jsx:409` and `Persona.jsx:277-278`) raises the `error` toast “… already exists — renaming onto it would erase its values.” Refusal, not merge. Closes PERS-04.

### RES-06 · P2 · The "one next step" CTA can never get past "Review N changes"
**Where** `ResumeEditor.jsx:176` (`changes`), `:236-243` (`stage`), `:280-299` (`applyReview`)
**Repro** open a tailored copy with tailoring diffs, click "Review N changes", decline nothing, "Done reviewing", then reopen.
**Expected + why** the design's stage machine (`Resumes Home D` `STAGES`) advances Review → Score → Cover letter → Applied; the modal's own copy says "these landed automatically".
**Actual** measured on a 5-change copy: after "Done reviewing" the toast fired, the summary was restored, the suggested bullet was appended and `suggested_bullets` was deleted — but the sub-line went to **"4 reviewable changes"** and the CTA to **"Review 4 changes"**. `changes` is recomputed from `computeChanges(baseData, data)` on every render, so every change the user *keeps* stays a diff vs the base forever. The shelf disagrees at the same moment: its `fresh` dot clears (backend `_fresh` = "any suggested_bullets", `routes_resumes.py:495-499`), so the copy stops being flagged there while the editor still demands review.
**Proposed fix** persist a `reviewed_at` (or a `reviewed: true` marker inside `json_data`) when "Done reviewing" runs, and gate the Review stage on it rather than on the raw diff. Keep the inline ✦ marks — they are informational.
**Status** fixed in source (rebuild pending): `ResumeEditor.jsx:68-77` (helpers), `:99` (state), `:168` (per-id load), `:254` (`stage`), `:323` (`applyReview`), `:387` (sub-line) — the acknowledgement is stored in **localStorage** (`jobnavigator_v2_resume_reviewed`, an id list capped at 300), not in `json_data`. That is the smaller of the two options: no backend change, no migration, no extra PATCH, and it is a per-user UI acknowledgement rather than résumé content — the cost is that it does not follow the user to another browser. `applyReview` marks it, `stage` and the sub-line gate on `changes.length && !reviewed`, and the inline ✦ marks stay.

### RES-07 · P2 · A failed shelf load is rendered as "No base résumés yet"
**Where** `Resumes.jsx:42-51` (`load`), `:150-151`
**Repro** intercept `GET /api/resumes/shelf` → 500 (and separately → 401), open `/v2/resumes`.
**Expected + why** a 500 and an empty database are different facts; the first-run copy invites the user to create a résumé they already have.
**Actual** measured for **both** 500 and 401: body = `'No base résumés yet. Create one to start.'`, subtitle = `'0 bases · 0 tailored copies live under their jobs'`. The only trace is `console.error('shelf load failed', e)` at `:49`. A 401 (the API key changed) is indistinguishable from an empty account — and the shelf has no `ToastStack` mounted at all, so it cannot report anything.
**Proposed fix** keep an `err` state; render "Couldn't load your résumés." + a Retry, and mount `ToastStack` on the shelf.
**Status** fixed in source (rebuild pending): `Resumes.jsx:39`, `:50-51`, `:122-130` — `load()` sets `loadErr`; a dashed `--bad` row "Couldn’t load your résumés — the shelf request failed." + **Try again** now renders ahead of the search / archived / "No base résumés yet" branches, so a 500 or 401 can no longer read as an empty account. The `ToastStack` half was not taken: the row is already visible and permanent, and a toast would duplicate it.

### RES-08 · P2 · PDF render failure leaves a stale preview with no signal
**Where** `ResumeEditor.jsx:261-275`, iframe at `:444`
**Repro** with a preview loaded, intercept `GET /api/resumes/*/pdf*` → 500, switch template.
**Expected + why** the pane is the only feedback that a template/paper change worked.
**Actual** measured: iframe still present showing the **previous** PDF, 0 toasts, no error text anywhere on the page. `:271` is `console.error('pdf', e)`. There is also no loading state while a render is in flight (measured: nothing changes for the ~1-2 s the render takes), so a stale preview and a current one look identical.
**Proposed fix** an error strip over the pane ("Preview failed — Retry") and a faint "rendering…" overlay while a request is open.
**Status** fixed in source (rebuild pending): `ResumeEditor.jsx:100-101`, `:288-297`, `:471-476` — a non-cancelled `/pdf` failure now revokes and clears the stale blob and raises a `pdfErr` overlay ("Preview failed — the PDF could not be rendered." + **Retry**, which bumps a `pdfNonce` in the effect deps); a successful render clears the flag. The "rendering…" in-flight overlay was **not** added — it is a separate missing state, not part of the failure signal, and is left as the open half of this finding.

### RES-09 · P2 · A base résumé cannot be deleted anywhere in v2
**Where** `ResumeEditor.jsx:395-398` (base sub-band), `Resumes.jsx:188-223` (shelf cards have no ⋯ menu)
**Repro** open a base résumé.
**Actual** measured on the base editor: `.v2-act:has-text("⋯")` count **0**; the band holds only the copy count and "✦ Tailor for a job…". The shelf has no per-card menu either (inventory §1.3 "Card ⋯ menus: none exist"). The backend supports it — `DELETE /resumes/{id}` cascades to children and their tracer links (`routes_resumes.py:979-997`), and `deleteResume` even carries the base wording ("Its tailored copies will be removed too.", `:229`) that is unreachable because the only Delete lives in the copy-only menu. So a mistyped base (like the 200-char one I created) can only be removed by hand via the API.
**Proposed fix** add a ⋯ menu to the base band with Delete (and the base branch of the existing confirm), or a per-card menu on the shelf.
**Status** fixed + verified after rebuild: the base band has a ⋯ menu (This base · Tailor for a job… · Delete résumé…); delete uses the existing cascade confirm ("Its tailored copies will be removed too"); scratch base + copy both 404 after delete

### RES-10 · P3 · Shelf: every other card and row landed on a half pixel — **fixed**
**Where** `Resumes.jsx:109` (header subtitle), `:158`/`:193` (card header rows), `:128`/`:143` (result + archived rows)
**Expected + why** HANDOVER §Conventions: fractional tops make Chrome round the 1 px border away on alternating rows; the fix is explicit integer line-heights (the same fix landed on Companies `:262` and Applications `:249`).
**Actual** measured: header 91.5 (h1 30 + gap 3 + subtitle 13 × 1.5 = **19.5**), card top 128.5, card height 99.5 (its baseline row measured 28.5 — 19 px Newsreader at 1.5), `assert_int_tops('.v2-card')` **3 of 5 fractional**, `.v2-chip` **8 of 10**; search results and the archived list `41.5` px rows, **10/20** and **148/296** fractional — identical in both themes and at 1024 px.
**Proposed fix (measured in the live page before editing)** subtitle `lineHeight:'20px'` → header 92, card top 129; card header row `lineHeight:'28px'` → row 29, card 100, all card tops integer; row `lineHeight:'20px'` + badge `lineHeight:'16px'` → 42 px rows, tops `128,174,220,266`.
**Status** fixed in source (rebuild pending) — `Resumes.jsx:109,128-129,143-144,158,193`

### RES-11 · P3 · Editor: section cards, bullet rows, modal rows all fractional
**Where** `ResumeSections.jsx:175` (`fontSize:10.5` "text · link · stub"), `:271` (`10.5` char count), `:90` (`BulletText` line-height 1.5 at 12.5 px = 18.75/line); `ResumeEditor.jsx:590-603`, `:642`
**Actual** measured with every section open: left-pane top 97 (integer) but card tops `73.5, 268.5, 445.5, 640.5, 835.5` — the Header card is 180.75 and Summary 129.75, and the .75 propagates to everything below. Bullet rows `TOPS` 2/2 fractional; tailor-modal job rows **41/41** fractional (`332.625, 392.125, …`); review-modal change rows **5/5** (`162.25, 248.25, …`).
**Expected + why** same rule as RES-10 — but `BulletText`'s own comment (`ResumeSections.jsx:64-66`) says résumé bullets *deliberately* keep the 1.5 line-height, so removing the .75 entirely means overriding a documented choice.
**Proposed fix** integer line-heights on the two 10.5 px labels (16 px) and on the modal rows; for the bullet textareas, either accept `lh={19}` (the escape hatch the component already exposes) or leave as-is.
**Status** fixed (a858334 + follow-up): integer line-heights on the tailor / re-tailor / review modal rows and every sub-11.5 px span inside them; `BulletText` default is 19 px. Measured: 0 fractional-height leaves in the Tailor modal, panel height 597 (integer). Residual: row tops still land on .5 because the flex-centred panel has an odd height in a 700 px viewport — shared by every centred v2 modal (Companies, Confirm, Add). Logged as needs decision RES-32 below.

### RES-12 · P3 · The Template and Paper dropdown items had no hover at all — **fixed**
**Where** `ResumeEditor.jsx:424`, `:436`
**Expected + why** the design gives menu rows `style-hover="background:#f3f0e8"`; `.v2-menuitem:hover { background: var(--surface-2) }` (`theme.css:149`) has no `!important`, and both item types set an inline `background: … : 'transparent'` — the exact trap HANDOVER calls out ("Inline styles beat class `:hover`").
**Actual** measured `hover_delta` on an unselected template item: `changed: []` (bg stayed `rgba(0,0,0,0)`); on the selected one it stayed `accent-soft`. The same `.v2-menuitem` class *does* hover correctly in the ⋯ menu (`MenuItem` sets no inline background) — measured `rgba(0,0,0,0)` → `rgb(246,244,238)` — which is what makes this an accident rather than a decision.
**Proposed fix** `background: … : undefined` instead of `'transparent'` (keeps the selected-item highlight, restores the hover).
**Status** fixed in source (rebuild pending) — `ResumeEditor.jsx:424,436`

### RES-13 · P3 · "+ N more ›" promises N and delivers a first-word search over everything
**Where** `Resumes.jsx:218` (`setQ(b.name.split(' ')[0])`), `:181` (`setQ('persona')`)
**Repro** shelf → PM card → "+ 39 more ›".
**Actual** measured: label `'+ 39 more ›'` → query `'PM'` → header **"303 MATCHES — bases, copies, and archived"**. The 303 are the PM base + its 45 live copies + 255 *archived* PM copies — i.e. the control that says "39 more live copies" hands back the 255 rows the shelf had deliberately folded into the archived band. A base whose first word is generic would also pull in other bases' copies.
**Proposed fix** make the affordance expand the card in place (show all `copies`), or seed the search with a filter that scopes to the base and excludes archived.
**Status** fixed (a858334): "+ N more ›" expands the card in place (all live copies) and toggles to "show fewer ‹". Measured: 10 → 49 chips, no search header.

### RES-14 · P3 · A 200-character base name is not truncated and overflows its card
**Where** `Resumes.jsx:194`
**Repro** create a base with a 200-char name (I used `ZZTEST` + 193×`L`), open `/v2/resumes`.
**Expected + why** every sibling string on this screen truncates — result rows `:130`, archived `:145`, chips `:176`/`:213` (`maxWidth: 250`), and the editor's own top bar (`maxWidth: 460` + ellipsis, measured working: width 460, `text-overflow: ellipsis`).
**Actual** measured on the shelf card: `white-space: normal`, `text-overflow: clip`, name span **width 2068 px, right edge 2319** against a card whose right edge is **1410** — it runs ~900 px past the card and takes the avg-fit badge with it; card height grew 99.5 → 143.5.
**Proposed fix** give the name span `flex: '0 1 auto'; minWidth: 0; whiteSpace: 'nowrap'; overflow: 'hidden'; textOverflow: 'ellipsis'` and a `title`.
**Status** fixed (a858334): name span nowrap/hidden/ellipsis with `title`. Measured: white-space nowrap, text-overflow ellipsis, overflow hidden.

### RES-15 · P3 · Escape closes none of the four modals
**Where** `Resumes.jsx:264` (Add), `ResumeEditor.jsx:489` (Re-tailor), `:576` (Tailor), `:626` (Review)
**Actual** measured: Add modal — scrim click closes ✓, Cancel closes ✓, inner click keeps it open ✓, **Escape → still open**. Re-tailor — same, **Escape → still open**. Companies' test modal closes on Escape (`companies.md`), so v2 is inconsistent with itself.
**Proposed fix** one `useEffect` keydown listener per modal (or a shared `useEscape(onClose)`).
**Status** fixed (a858334): shared `useEscape` hook in `v2/hooks.js` on Add / Re-tailor / Tailor / Review / Regenerate / Confirm. Measured: Escape closes the Add modal, the Tailor modal and the delete dialog.

### RES-16 · P3 · Destructive edits have no confirm and no undo; the one confirm is the browser's
**Where** `ResumeSections.jsx:249` (Remove role), `:237`/`:302`/`:348` (✕), `:324`/`:353`/`:369` (Remove); `ResumeEditor.jsx:229`
**Actual** measured: "Remove role" on an entry holding two bullets deleted it immediately — `dialog` events captured: **none**, `experience` went 2 → 1 in the next PATCH. Deleting a copy *does* confirm, but via `window.confirm` — captured message: `Delete “ZZTEST Base A → Meta — Product Manager”?` — a native dialog in a screen that owns a modal system and an `undo` toast kind (`Toast.jsx:19`, 5 s) that this screen never uses.
**Proposed fix** an `undo` toast for role/education/project/publication removal (the state is already a deep clone, so the snapshot is free); move the delete confirm into a v2 modal.
**Status** fixed (a858334): `ConfirmDialog` extracted to `v2/ConfirmDialog.jsx` and used by Companies, ResumeEditor and CoverLetterEditor; cover-letter paragraph removal gets an undo toast. Measured: ⋯ → Delete raised 0 native dialogs and a v2 dialog with Cancel.

### RES-17 · P3 · Disabled primary buttons are filled with `--edge`, which reads as enabled
**Where** `Resumes.jsx:274` (Create from scratch), `ResumeEditor.jsx:614` (✦ Tailor), `:536` (✦ Re-tailor / Make copy)
**Expected + why** the design's disabled Tailor button is `tailorGoBg:"#e2ddd0"` / `tailorGoFg:"#6d6862"` — i.e. `--line` on `--muted`.
**Actual** measured disabled: `background rgb(138,130,110)` (`--edge`) with `color rgb(255,255,255)` (`--accent-ink`); dark: `rgb(127,122,102)` on `rgb(21,20,15)`. `--edge` is the *interactive border* token (3:1 floor) — as a fill it produces a solid olive pill that looks like a second live button next to the accent one. `cursor: default` is correctly set, so only the colour misleads.
**Proposed fix** `background: 'var(--line)'`, `color: 'var(--muted)'` when disabled.
**Status** fixed (a858334): disabled primary pills are `--line` on `--muted` across the shelf and all three builders. Measured: rgb(226,221,208) / rgb(109,104,98).

### RES-18 · P3 · Import PDF shows its busy state on the *other* button
**Where** `Resumes.jsx:241` (one shared `busy`), `:274` label, `:275` (no busy label)
**Repro** New résumé → Import PDF; the parse is a real LLM call (`routes_resumes.py:1128`) and takes seconds.
**Actual** measured with the import stubbed to a 2.5 s response: the **"Create from scratch"** button read `'Creating…'` while the import ran; the Import button was unchanged. Nothing else moved.
**Proposed fix** separate `busy` per action, label the Import button "Parsing…", and disable both while either runs.
**Status** fixed (a858334): per-action busy — Import reads "Parsing…", Create "Creating…", both inert while either runs; file input reset per pick. Measured: Parsing… 1, Creating… 0, Create cursor default.

### RES-19 · P3 · The archived band and the "+N more" search render every row unvirtualised
**Where** `Resumes.jsx:142-148`, `:127-134`
**Actual** measured: "browse ›" rendered **296** rows in **1.56 s**; the PM "+39 more" search rendered **303**. No paging, no cap, no count guard. It works today; it is the shape that will not (255 of the 296 come from a single base).
**Proposed fix** cap the archived list (e.g. 100 + "show more"), or paginate server-side.
**Status** fixed (a858334): 100-row pages with a "Show N more" row on search results and the archived list. Measured: 100 → 200 rows after one click.

### RES-20 · P3 · On a job-less copy the "one next step" is an action that can only fail
**Where** `ResumeEditor.jsx:239` (stage 2) vs `:204` (guard)
**Repro** open a persona-tailored copy with `job_id = null` (e.g. `Persona → Decagon — …`), click the CTA.
**Actual** measured: headline falls back to `'Tailored copy'`, CTA reads **"Score the result"**, clicking it produces the error toast `'This copy isn’t linked to a job to score against.'` The same rendering also covers "the job fetch failed", so a transient 500 on `GET /jobs/{id}` is indistinguishable from "this copy has no job".
**Proposed fix** when `!doc.job_id`, skip the Score stage (go straight to Cover letter) and say so in the sub-line; render a distinct state when the job fetch fails.
**Status** fixed (a858334, option 1): the pasted description is kept on the copy (`json_data._tailor_context`), `score-check` scores against it when there is no job and stores `json_data._score` on the copy; the PDF namespace drops `_` keys. 7 new backend tests (602 total). Frontend: "Tailored from a pasted description" headline + Score CTA for freeform copies; legacy job-less copies skip Score with "No job or description linked, so this copy can't be scored."; a failed job fetch says "Couldn't load the linked job." Measured both copy states live.

### RES-21 · P3 · A missing, malformed or just-deleted id redirects silently
**Where** `ResumeEditor.jsx:156-159`
**Actual** measured for `/v2/resumes/00000000-0000-0000-0000-000000000000`, `/v2/resumes/not-a-uuid` and the id of a copy deleted seconds earlier: all three land on `/v2/resumes` with **0 toasts** and no message — identical to a deliberate "‹ Résumés". A 401 or 500 on the same fetch behaves the same way.
The backend half of this is now fixed: before the restart `GET /resumes/not-a-uuid` and `/resumes/not-a-uuid/tracer-stats` returned **500 Internal Server Error** (unhandled `DataError` on the UUID cast); after the coordinator's `main.py` handler they return **404** — verified across `GET /{id}`, `/{id}/tracer-stats`, `/{id}/pdf`, `PATCH` and `DELETE`.
**Proposed fix** (frontend) push an `error` toast "That résumé no longer exists." before navigating.
**Status** fixed (a858334): 404 → "That résumé no longer exists.", other errors → "Couldn't load that résumé.", handed to the shelf via `setFlashToast`. Measured on a zero UUID.

### RES-22 · P3 · Design deviations (grouped — all read as decisions)
**Where** `Resumes Home D.dc.html` vs the built screens
- **Shelf layout**: the design is a two-pane browser (312 px "Tailor from" source column + a sorted copies table with fit/Δ/when/Open ›, an order label, and an "All résumés" neutral state). The build is the *source-card* home — Persona card + base cards + copy chips — i.e. `Resumes Shelf`, which `design/MAIN.md` names as the **canonical** Résumés screen ("Resumes Home Flat and Resumes Shelf are the other two Résumés homes"). Flagging once so it is not re-raised: the two files disagree about which home was chosen.
- **Review modal** `min(920px,94vw) × min(760px,90vh)` — measured 920×760 — vs the design's 620×580.
- **⋯ menu** 244 px vs 248; hints "adds a copy" / split light+full rows vs the design's "replaces copy" / "quick / full" (the behaviour genuinely differs — re-tailor adds a copy).
- **Tailored badge** measured `--accent-soft`/`--accent` (green) vs the design's plum `#f3e7ef`/`#7c4066` — the deliberate cross-screen change.
- **▲▼ and ✕ hovers**: design says colour-only (`color:#3f6b52`, `color:#9c3b30`); measured `.v2-navlink` → `color+background` and `.v2-hover-bad` → `background: --bad-soft` with the colour unchanged.
- **Card hover** accent border + `--hover-soft` (theme.css:140-143 documents the unification) vs the design's beige.
- **Header** h1 30 px / 24 px left gutter vs the design's 28 px / 30 px — the shell convention, identical on all nine screens (grep-verified).
**Status** decided keep current (user 2026-09-03: consistency with the other v2 screens wins over the board).

### RES-23 · P4 · `.v2-navlink:hover`'s colour rule never fires where the caller sets an inline colour
**Where** `theme.css:133-134`; callers `Resumes.jsx:123`, `:139`, `ResumeEditor.jsx:324`, `:352`
**Actual** measured on "‹ Résumés": `color` stayed `rgb(63,107,82)` through the hover; only `background` changed. `.v2-hover-accent` was given `!important` for exactly this reason (theme.css:129 + its comment); `.v2-navlink` was not. On "based on {base} ↗" the outer span does change colour, but its two inner spans carry inline colours, so nothing visible moves either.
**Status** fixed earlier (5c6c17a hover hardening): `.v2-navlink:hover` now carries `!important` on both background and colour — measured on “‹ Résumés” in the Feed/Companies rounds.

### RES-24 · P4 · One localStorage key holds the section-open state for every résumé and for Persona
**Where** `ResumeEditor.jsx:81`, `:306` — `jobnavigator_v2_resume_sections`
**Actual** measured: opened Skills on copy A → `["Experience","Skills"]`; opened copy B → Skills already open; navigated to `/v2/persona` → same single key, and `Object.keys(localStorage).filter(k => k.includes('section'))` returned exactly `['jobnavigator_v2_resume_sections']`. So Persona and every résumé share one preference.
**Status** closed: already split — Persona uses `jobnavigator_v2_persona_sections`, Cover Letters `v2_cl_sections`, Résumés `jobnavigator_v2_resume_sections` (user 2026-09-03: split for all three).

### RES-25 · P4 · The success toast that carries "Open ↗" expires in 2.5 s
**Where** `ResumeEditor.jsx:112`, `:142`; `Toast.jsx:21`
**Actual** measured the full pending-tailor path with the POST stubbed 202 and `/resumes?is_base=false` returning a matching row: at t+800 ms both toasts were up — `'Tailoring for Meta… runs in the background.'` (progress: `--recessed`/`--line`/`--text-2`) and `'✓ | Tailored copy for Meta is ready. | Open ↗'` (success: `--toast-ok-*`); "Open ↗" navigated correctly. By t+5 s it was gone. The action is the only route to the new copy from here.
**Status** fixed (a858334): toast TTLs progress 4 s / success 4 s / undo 5 s / error sticky (user: 3–5 s, consistent). Measured: success toast up at 3.5 s, gone at 4.7 s.

### RES-26 · P4 · A freeform tailor never reports completion
**Where** `ResumeEditor.jsx:125` (`if (jobId) pendingRef.current.push(...)`)
**Actual** measured: ticking "Tailor from Persona instead of this base" + a pasted JD posted `{"base_resume_id":"persona","job_description":"freeform JD text"}` and showed `'Tailoring … runs in the background.'` (note the empty slot where the company name goes — `:126` interpolates nothing). After 4 s and beyond: no further toast. The copy only ever surfaces on the shelf.
**Status** fixed (a858334): pending tailors tracked via `/monitor/active` scope (`{base}:{job|freeform}`), so persona/freeform runs report completion; the progress copy no longer has an empty company slot.

### RES-27 · P4 · `setSearchParams` is declared and never used; `?job=` is inert
**Where** `ResumeEditor.jsx:2`, `:71`
**Actual** measured `/v2/resumes/{id}?job={uuid}`: the param stays in the URL and changes nothing (band still "Base résumé · 0 tailored copies"). Confirmed by grep that no `searchParams.get` exists in either file. (For contrast, `/v2/cover-letters?resume=&job=` *is* consumed and cleared — `CoverLetters.jsx:151-170` — which is why the ⋯ → "Cover letter" jump lands on a bare `/v2/cover-letters`; that is correct, not a defect.)
**Status** fixed (a858334): unused `setSearchParams` and the inert `?job=` handling removed.

### RES-28 · P4 · Dead code and always-false branches
- `ResumeEditor.jsx:651` — `{added || '(base text restored)'}` sits inside `{added && …}`; the fallback can never render.
- `:475` `const personaCopyable = false` makes `:480` a constant; `:551` `useState(baseId === 'persona')` is always false because `baseId = doc.id` (`:545`) — so the Tailor modal's persona checkbox always starts unchecked (verified: `checked False`).
- `:419` `setFmtOpen(false)` / `:431` `setTplOpen(false)` are unreachable — measured: with one dropdown open its `position:fixed` backdrop intercepts every click, so the other trigger cannot be reached (Playwright reported `<div></div> … intercepts pointer events` for 30 s).
- `Resumes.jsx:234` `else load()` — `POST /resumes` always returns an id, so the branch never runs.
- `Resumes.jsx:245` duplicates the `EMPTY` skeleton instead of importing it from `ResumeSections.jsx:16` (drift risk).
- `Resumes.jsx:276` the file input's `value` is never reset — picking the same PDF twice in one modal session does nothing.
**Status** fixed (a858334): all six spots cleaned — the preview dropdowns now close on a document click so the other trigger is reachable (measured: second dropdown opens while the first is open), `EMPTY` imported from ResumeSections, file input reset (see RES-18).

### RES-29 · P4 · Archived view has no empty branch; the archived sort comment is wrong
**Where** `Resumes.jsx:136-149`; `routes_resumes.py:607`
**Actual** the archived list has no zero-row branch — reachable when an in-flight tailor finishes (`:68 load()`) while the archived view is open and the set empties: the header would read "Archived · 0 from rejected or stale applications" over nothing. And `archived.sort(key=lambda a: a["why"] != "rejected")` is commented "newest archived first" but actually sorts rejected before stale, with no date involved — measured order: the first 4 rows were all `rejected`; the set is 187 rejected + 109 stale.
**Status** fixed (a858334): archived view has an empty branch; the backend now carries `archived_at` and sorts newest-first, comment corrected. Measured: first 6 `archived_at` values descend.

### RES-30 · P4 · The score poll resolves on any numeric `Tailored`, so a re-score reports the old number
**Where** `ResumeEditor.jsx:211-218`
**Actual** the poll's only condition is `typeof j.cv_scores['Tailored'] === 'number'` (`:214`). On a copy that already has a Tailored score, the first tick (3 s) matches the *existing* value and pushes "Scored: {old}" while the real run is still going. Verified in the intercepted flow that the poll fires at 3 s and takes whatever is there — my run only passed because I flipped the score before the first tick. Also `scores.base` is captured in the closure at call time (`:220`).
**Proposed fix** capture the pre-run value and resolve only when it changes, or key the poll on `/monitor/active` (scope `f"{job_id}:resume:{resume_id}"`, `routes_resumes.py:1276`), which the backend already publishes and the client ignores.
**Status** fixed (a858334): the score poll keys on the `score_resume` run and reads the score and base only after it disappears (8 s grace, 180 s stop); `scores.base` read at resolve time.

### RES-31 · P4 · "autosaves on blur" is wrong — saving is per keystroke, debounced 500 ms
**Where** `ResumeEditor.jsx:328` vs `:246-253`
**Actual** measured: typing 13 characters into *Full name* produced exactly **1** `PATCH`, **471 ms** after the last keystroke, body keys `['json_data']` — a trailing debounce, not a blur. The only genuinely blur-saved field on the screen is the Skills category (`ResumeSections.jsx:295`). The string is only shown before the first save (`savedAt` null); afterwards it reads "saved {ago} · autosaves", which is accurate.
**Status** fixed (a858334): "autosaves on blur" → "autosaves"; the Skills category name saves through the same 500 ms debounce (blur flushes). Measured: 1 PATCH 1016 ms after typing without blur (category debounce + editor debounce).

---

### RES-32 · P4 · Centred modals land on a half pixel whenever the panel height is odd
**Where** every `position: fixed; inset: 0; display: flex; align-items: center` wrapper — `ResumeEditor.jsx` (Tailor, Re-tailor, Review), `Resumes.jsx` (Add), `Companies.jsx` (3), `ConfirmDialog.jsx`
**Actual** measured after RES-11: the Tailor panel is 597 px tall (all leaves integer), so in a 700 px viewport its top is 51.5 and all 82 row tops end in .5. Any odd panel height in an even viewport (or vice versa) does this.
**Proposed fix** snap the panel: a tiny hook that reads the rect top after layout and applies `marginTop: round(top) - top` (re-run on resize), or a shared `Modal` wrapper doing the same. Cosmetic (blurred 1 px borders inside modals).
**Status** fixed (8804ae3): `useSnapTop` now snaps with `transform: translateY` (the margin version moved a flex-centred panel by half the delta — caught by `round2/verify.md`); live re-check in `round3/verify.md`.

## What was verified working (measured, no finding)

**Shelf** — subtitle string identical to the API in both themes; 5 cards (Persona + 4 bases) with correct `N recent copies` / `no recent copies` / `no copies` wording; avg-fit badges with `scoreColor` thresholds; copy chips capped at 6 with `title` = full name and `maxWidth: 250` ellipsis; chip click `stopPropagation` opens the copy (`/v2/resumes/{id}`) while the card opens the base and the Persona card opens `/v2/persona`; group labels "Profile"/"Résumés"; archived browse row wording and count; search across bases + live copies + archived (`'Google'` → 20 rows, matching a client-side recount exactly; badge kinds 6 tailored / 14 archived with correct token colours); zero-result copy; "‹ Back" clears the query; typing in search leaves the archived view; in-flight `tailoring…` chips driven by `/monitor/active` land on the right cards for both a base scope (`{id}:{job}`) and a persona scope (`persona:freeform`), and `score_resume` rows are correctly ignored. Hovers `.v2-card` / `.v2-chip` (incl. the `--ring-accent` ring) / `.v2-act` all fire in both themes; "+ New résumé" and "+ N more ›" have none, as in the design. **Console clean (0/0/0/0) on every shelf pass.**

**Add modal** — 420 px panel, `--shadow-modal`, `--scrim` (0.42 light / 0.58 dark), autofocus, Enter creates, empty name fires no POST, `POST /resumes` body `{name, is_base:true, json_data:EMPTY}` and the row comes back with `template: 'garamond'` (the default) / `page_format: 'letter'` / null parent+job; 500 → inline `--bad` text "boom", 401 → "Invalid API key" (no toasts, by design); Cancel, scrim and inner-click all behave.

**Editor** — an all-empty document renders five `EmptyState`s with the PDF wording, `(0)` counts, no Header/Summary empty state, and the PDF still renders; all seven sections toggle and persist; Header name + contact items (add, edit, `stub` field appearing only for non-`mailto:` URLs, ▲▼ reorder incl. a no-op at the bounds, ✕ remove) all round-trip through `PATCH` and back through `GET`; Summary char count (`200 characters`, `700 characters · long summaries can push to a second page` at >600) and auto-grow; Experience entry add/collapse/expand with header `title · company · date · N bullets`, all four fields + description, bullet add/edit/remove, a **200-character bullet** stored and rendered intact (textarea grew to 75 px, 4 lines), "Remove role"; Skills add/rename/reorder/remove; Education, Projects (incl. project bullets) and Publications add/edit/remove with counts tracking. Template picker lists all 8 templates with friendly names, marks the selection `--accent-soft`/`--accent`, persists via `PATCH {template}` and re-requests `/pdf?template=garamond&format=a4`; Paper picker the same; backdrops close both. `GET /resumes/{id}/pdf?template&format` returns **200, `application/pdf`, `%PDF-` magic** for `inter/letter` and `traditional/a4`. The Download anchor (`/api/resumes/{id}/pdf?template=…&format=…`, `target=_blank`, `rel=noopener noreferrer`) works **without** the `X-API-Key` header — fetched from the page it returned 200 + `attachment; filename="ZZTESTPerson_ZZTESTBaseA_Resume.pdf"` on the `jn_session` cookie.

**Copy band + pipeline** — ring hidden when unscored, shown with the rounded value and `scoreColor` when scored; delta `+12` accent / `-55` warn; sub-line cycles "N reviewable changes" → "not scored yet" → "ready", with `· tracers: LinkedIn 0` appended from `GET /{id}/tracer-stats` (the link is created by the PDF render and is removed with the résumé — verified `[]` after delete). CTA states all four plus the terminal `Applied ✓` (`--accent-soft`/`--accent`, `cursor: default`). ⋯ menu: 6 items + Delete under the design's "This copy"/"Job" heads, correct hover, backdrop close, Cover letter and Open in feed navigate correctly, "Open in feed" and "Mark applied" hidden on a job-less copy. Score: `POST /{id}/score-check` body `{"depth":"full"}` → progress toast → poll → `'Scored: 88 (+18 vs base)'`; 409 → sticky error toast (`--toast-bad-*`, still present after 4 s). Mark applied → `PATCH /jobs/{id}` → "Marked applied." Delete: native confirm, cancel fires no DELETE, 500 → "Delete failed.", accept → DELETE + redirect, `total_copies` 52 → 51, rail badge unchanged (copies are not bases), tracer links gone.

**Review modal** — 5 changes computed correctly from a crafted diff (summary modified, bullet 1 modified, new bullet, suggested bullet, skills added) and consistent across the sub-line, CTA, menu hint ("5 applied") and footer; word diff renders removed (strikethrough on `--bad-soft`) + added (`--change-soft`); Decline toggles to "declined" + "Restore change"; "Done reviewing" restored the declined summary to base text, appended the kept suggested bullet, deleted `suggested_bullets`, saved once and toasted. Inline marks agree: 4 ✦ with the right `title`s, 2 ↩ reverts, the "added" pill, the entry ●, the section "● changed by tailoring", and the `--change-bg`/`--change-soft` row tint.

**Tailor / Re-tailor** — 480 px panels matching the design's width; job list sorted saved/applied first, capped at 40, searchable, radio selection, the base's fit score chip, "✦ exists" with the right tooltip, "No jobs match…" empty copy; freeform textarea clears the pick and vice-versa; disabled→enabled Tailor button; `POST /resumes/tailor` bodies exact for both `{base, job_id}` and `{base:'persona', job_description}`; 409 → "Already tailoring for that job.", 400 → the backend's own detail verbatim; the pending watcher produced the success toast with a working "Open ↗". Re-tailor: mode cards, all 6 base options + Persona, "current base" on the right row (correct on a persona copy too), Persona disabled in Copy mode with the right title, footer note switching "Runs in the background"/"Instant — no LLM call", and a real "Make copy" produced a row.

**Themes** — every token measured in both: shelf card `#fff`/`--line` vs `rgb(40,37,27)`/`rgb(62,59,50)`; chips, badges, `+ New résumé` (`--accent`/`--accent-ink` → `rgb(141,187,159)`/`rgb(21,20,15)`), search underline, editor top bar/sub-band/section cards/PDF pane/CTA/Download/dash-add. **No light-only value survived in dark.**

**Narrow (1024×700)** — no horizontal overflow on either route (`body.scrollWidth === innerWidth === 1024`); card 764 px, 13 chips; left pane 384 px (47 %); the preview header still fits (Download right edge 1009 < 1024).

**Console** — clean (`0 console / 0 pageerror / 0 http≥400 / 0 requestfailed`) on every non-error-injection pass, both themes, both viewports.

---

## Fixed in source
- `backend/api/routes_resumes.py:14,973-978` — `flag_modified(resume, "json_data")` so a key-order-only PATCH persists (RES-02). **Fixed + verified after the restart.**
- `frontend/src/v2/Resumes.jsx:109` — header subtitle `lineHeight: '20px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:128-129` — search-result row `lineHeight: '20px'` + badge `lineHeight: '16px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:143-144` — archived row + badge, same (RES-10).
- `frontend/src/v2/Resumes.jsx:158,193` — Persona and base card header rows `lineHeight: '28px'` (RES-10).
- `frontend/src/v2/Resumes.jsx:253-268` — `importPdf` reuses the row `/resumes/import-pdf` already created (renaming it when the user typed a name) instead of creating a second one (RES-03).
- `frontend/src/v2/ResumeEditor.jsx:424,436` — template/paper menu items drop the inline `background:'transparent'` that killed `.v2-menuitem:hover` (RES-12).

All five JSX edits are **rebuild pending**; the geometry numbers in RES-10 were measured by injecting the exact same values into the live page before editing, so the arithmetic is known, not assumed.

## Couldn't test
- **Real tailoring / real PDF import** — both are LLM calls. The tailor flow was exercised end-to-end with `POST /resumes/tailor` intercepted (202 + a stubbed `/resumes?is_base=false` row) so the pending watcher, both toasts and "Open ↗" were verified; the review flow was exercised against a hand-crafted diff that reproduces the four change kinds the tailor emits. The import duplicate (RES-03) is proven from the client side (two POSTs) plus the backend's own commit at `routes_resumes.py:1152-1161` — no LLM call was spent. **0 real LLM calls used.**
- **PDF pixels** — headless Linux has no PDF viewer, so the iframe cannot be read. Verified instead through the API (status, `application/pdf`, `%PDF-` magic, byte length, `Content-Disposition`) and by watching the re-render requests fire with the right query string.
- **Archived-view-empty branch** — needs an in-flight tailor to finish while the archived list is open and the set drops to zero; not reachable without a real tailor run. Logged from code as RES-29.
- **Rail badge going stale mid-session** — the rail fetches its counts once (`V2App.jsx:57-72`); after deleting a base the number only corrects on reload. Already logged cross-screen as SRCH-10, not duplicated here.

## Scratch data
Created (all `ZZTEST`-prefixed) and **all deleted**:
- `ZZTEST Base A` (base, `eed94f6b…`) — created through the Add modal UI, used for every editor test.
- `ZZTEST Base A → Meta — Product Manager` ×3 copies (`65a734ef…`, `cb293732…`, `12b4afd6…`) — via `POST /resumes/copy` and the Re-tailor modal's "Make copy".
- `ZZTEST LLLL…` (base, 200-char name, `ff9cc665…`) — long-string test.
- `ZZTEST Verify` (base, `561c539a…`) — post-restart verification of RES-02.

**Final state (psql + API):** `SELECT count(*) FROM resumes WHERE name ILIKE '%ZZTEST%'` → **0**; `resumes` 349 total / 4 bases; shelf 4 bases · 49 copies · 296 archived — identical to the pre-test numbers. Orphaned `tracer_links` (rows whose `resume_id` no longer resolves): **7**, all with `resume_id IS NULL` and all created **before** this session (2026-05-30, 2026-06-12, 2026-08-31, 2026-09-01) — the known job-less-résumé NULL-token rows, none of them mine. `tracer_click_events` orphans: **0**. No real job, application, company or non-ZZTEST résumé was mutated: `PATCH /jobs/{id}` (Mark applied) and every `GET /jobs/{id}` in the pipeline tests were served by Playwright route interception, never by the backend.

---

## Summary

**Inventory boxes: 292 · verified OK 199 · failed 83 · untestable 10.**  (a finding usually fails several boxes — 31 findings across 83 boxes)

**Findings by severity — 31 total:** P1 **1** (RES-01) · P2 **8** (RES-02…09) · P3 **13** (RES-10…22) · P4 **9** (RES-23…31).

**Fixes applied: 7** — 1 backend (fixed + verified live), 6 frontend (rebuild pending). **Scratch rows remaining: 0.**

The headline is RES-01/RES-02: this screen writes continuously and reports success unconditionally. RES-02 was a write that never happened at all (a reorder that compared equal, so SQLAlchemy skipped the UPDATE) and RES-01 is the reason nobody would have noticed — the autosave's only failure handler is `console.error`, and because `savedAt` is left alone the status line keeps asserting "saved just now" over an edit the server rejected. RES-07 and RES-08 are the same shape one level out: a 500 on the shelf is rendered as an empty account, and a 500 on the PDF leaves the previous preview on screen. RES-06 is the one design-level bug — the "one next step" pipeline, which is the organising idea of the copy band, cannot be completed, because "reviewed" is recomputed from the diff instead of recorded. The rest are contained: two silent data-loss paths in the Skills editor (RES-04, RES-05), the duplicate row on PDF import (RES-03), and a set of geometry and hover deviations of which the two that read as accidents — half-pixel shelf rows and a dropdown hover that had never fired — are fixed.

---

## P2 triage (2026-09-02)

Source-only pass over the open P2s. No rebuild, no backend restart — every frontend fix below is
**rebuild pending**. Files touched: `frontend/src/v2/Resumes.jsx`, `ResumeEditor.jsx`, `ResumeSections.jsx`.
Brace/paren/bracket/backtick balance of all three checked against `git show HEAD:<path>` — unchanged.

| id | action | note |
|---|---|---|
| RES-02 | **status corrected** | Already fixed and verified (backend `flag_modified` in `update_resume`); the Status line just didn't read as "fixed". No code change. |
| RES-04 | **fixed** | `SkillsEditor` no longer routes the value write through the dotted-path `setField`. It gets its own `setVal(k, v)` writing `d.skills[k]` directly via `mutate`, with a `DANGEROUS` guard kept. Fixes the `↩` revert too. Same fix closes PERS-03. |
| RES-05 | **fixed** | `rename()` now returns a boolean and refuses a collision (and a blank/`__proto__` name); the uncontrolled Category input is reverted to the old key on refusal, and an `error` toast says why. `onError` is plumbed `SectionEditor` → `SkillsEditor` and wired to `pushToast` from both callers. Same fix closes PERS-04. |
| RES-06 | **fixed** | "Reviewed" is now recorded, not recomputed. `localStorage` key `jobnavigator_v2_resume_reviewed` (an id list, capped at 300) rather than a `json_data` marker — **the smaller of the two**: no backend change, no migration, no extra PATCH on a screen that already writes continuously, and the state is a per-user UI acknowledgement rather than résumé content. Trade-off: it does not follow the user to another browser. `applyReview` marks it; `stage` and the sub-line gate on `changes.length && !reviewed`; the inline ✦ marks and the ⋯ → "Review changes" entry are unchanged. |
| RES-07 | **fixed** | `load()` sets a `loadErr` flag; the shelf renders a dashed `--bad` row "Couldn't load your résumés — the shelf request failed." + a **Try again** that re-runs `load()`, ahead of the search/archived/empty branches. The `ToastStack`-on-the-shelf half of the proposed fix was **not** taken (it would duplicate the visible row). |
| RES-08 | **fixed** | On a non-cancelled `/pdf` failure the stale blob is revoked and cleared and a `pdfErr` overlay renders "Preview failed — the PDF could not be rendered." + **Retry** (bumps a `pdfNonce` that re-arms the render effect). Success clears the flag. The "rendering…" in-flight overlay from the proposed fix was **not** taken — it is a separate state, not part of the failure signal. |
| RES-09 | **deferred** | Needs the user's decision. The Shelf design deliberately gives base cards no ⋯ menu (inventory §1.3 "Card ⋯ menus: none exist"), so adding Delete to the base band or the shelf card contradicts the chosen design rather than repairing an accident — and the backend's cascade (`DELETE /resumes/{id}` removes every tailored copy and its tracer links) makes it the most destructive control on the screen. **Decision needed:** is "bases are permanent in the UI" intentional, or should the base band get a ⋯ → Delete with the existing base-wording confirm? |
