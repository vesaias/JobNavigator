# v2 Résumés — Inventory (Shelf + Editor)

Catalogue for the verification pass. Nothing here was run or fixed; every line is a
checkbox so it can be pasted into a test plan. Paths are relative to
`V:\JTrakProject\frontend\src\` unless stated. Backend references are
`V:\JTrakProject\backend\api\routes_resumes.py` (abbreviated `routes_resumes.py`).

Files read in full: `v2/Resumes.jsx` (282 lines), `v2/ResumeEditor.jsx` (665),
`v2/ResumeSections.jsx` (375), `v2/V2App.jsx` (162), `v2/Toast.jsx` (82), `api.js` (29),
plus `useTitle.js`, `v2/theme.css` (tokens + hover classes), and the backend
endpoints the screens call.

Conventions used below:
- **toast kinds** are from `v2/Toast.jsx:15-21` — `progress` 2.5s, `success` 2.5s, `undo` 5s, `error` sticky until dismissed.
- "**silent catch**" = the promise has a `catch` but it produces no user-visible feedback (console or nothing).
- "**no catch**" = the promise has no error handling at all (none were found — see the summary).

---

# 1. Shelf — `v2/Resumes.jsx` (route `/v2/resumes`)

## 1.1 Routes & params

- [ ] Route registered at `App.jsx:156` — `<Route path="resumes" element={<V2Resumes />} />` nested under `/v2` (`App.jsx:153`, shell `V2App`).
- [ ] No `:id` on this route. Navigation to a document is `navigate('/v2/resumes/${id}')` — `Resumes.jsx:77` (`openResume`).
- [ ] No query params are read: no `useSearchParams`, no `window.location` anywhere in `Resumes.jsx` (grep confirmed). `?job=` deep-link is NOT handled on the shelf.
- [ ] Persona card navigates to `/v2/persona` — `Resumes.jsx:157`.
- [ ] localStorage read/written by this file: **none**. Indirect keys via the shell/API: `jobnavigator_v2_rail` (`V2App.jsx:48` read, `:55` write), `jobnavigator_dark_mode` (`V2App.jsx:52` read, `:54` write), `jobnavigator_api_key` (`api.js:11` read).
- [ ] Browser tab title: not set by this file — `TitleSync` (`useTitle.js:37-44`, mounted at `App.jsx:31`) resolves `/v2/resumes` → "Résumés · JobNavigator" (`useTitle.js:13`).

## 1.2 Data loads

- [ ] **GET `/resumes/shelf`** on mount — `Resumes.jsx:42-52` (`load`, run by `useEffect` at `:52`). Sets `bases`, `persona`, `archived`, `totalCopies`. Failure: `console.error('shelf load failed', e)` at `:49` — **silent catch**; `setLoading(false)` runs regardless (`:50`), so a failed load renders the "No base résumés yet" branch (`:151`) instead of an error.
- [ ] **GET `/monitor/active`** polled every **3000 ms** — `Resumes.jsx:55-75`. Keyed by `r.job_type === 'tailor_resume'` (`:59`), then `scope_key.split(':')` → `{baseId, jobId}` (`:60-61`). Backend scope format: `f"{base_resume_id}:{job_id or 'freeform'}"` at `routes_resumes.py:715`, so a freeform tailor yields `jobId === 'freeform'`. First tick runs immediately (`:72`).
- [ ] Shelf refresh trigger: when the joined key string **shrinks in length** (`:65` `key.length < inflightKeys.current.length`) → `load()` (`:68`). Errors swallowed at `:70` — **silent catch**.
- [ ] Also refreshed when AddModal `onCreated` is called without an id — `:234` (`else load()`). In practice `POST /resumes` always returns an id, so this path is effectively unused.
- [ ] AddModal on-demand calls: **POST `/resumes`** (`:250`), **POST `/resumes/import-pdf`** multipart (`:258`) followed by **POST `/resumes`** (`:259`). See 1.3.
- [ ] Shell counts that also touch this screen's data (in `V2App.jsx:57-72`, mounted once): GET `/resumes?is_base=true` (`:59`) for the rail's "Résumés" count.

## 1.3 Interactive elements

### Header
- [ ] **Search input** — placeholder "Search bases, copies, archived…" — `Resumes.jsx:112-113`. Handler: inline `onChange` → `setQ(value)` and `setShowArchived(false)`. No API. Mutates `q`, `showArchived`. No toast.
- [ ] **"+ New résumé"** pill (a `<div>`, not a `<button>`) — `:114`. Handler: inline → `setAddOpen(true)`. No API.

### Search-results view (`searching === true`, `:120-135`)
- [ ] **"‹ Back"** — `:123`, class `v2-navlink`. Handler: `setQ('')`.
- [ ] **Result row** (one per match) — `:128`, class `v2-act`. Handler: `openResume(r.id)` → navigate. Shows kind badge (`:129` — `base` / `tailored` / `archived`), name (`:130`), note (`:131` — copy count for bases, `why` for archived), score (`:132`, coloured by `scoreColor` `:16`).

### Archived view (`showArchived === true`, `:136-149`)
- [ ] **"‹ Back"** — `:139`, class `v2-navlink`. Handler: `setShowArchived(false)`.
- [ ] **Archived row** — `:143`, class `v2-act`. Handler: `openResume(c.id)`. Shows `copyLabel(c)` (`:145`) and `c.why` (`:146`).

### Default view (`:150-230`)
- [ ] **Persona card** — `:157`, class `v2-card`, `title="Open Persona — your full profile"`. Handler: `navigate('/v2/persona')`. Rendered only when `persona` truthy (`:154`) — backend always returns a persona object (`routes_resumes.py:597-604`), so it always shows when `bases.length > 0`.
- [ ] **Persona in-flight chip** ("tailoring…" + spinner) — `:170-172`, class `v2-spin` on the ring. **No handler** (display only). One per `/monitor/active` row with `baseId === 'persona'` (`:167`, `:169`).
- [ ] **Persona copy chip** — `:175-179`, class `v2-chip`, `title={c.name}`. Handler: `e.stopPropagation(); openResume(c.id)`. Shows `copyLabel(c)` (`:176`), score (`:177`), fresh dot (`:178`, `title="Has tailoring changes you haven't reviewed"`). Only first 6 (`:174` `slice(0, 6)`).
- [ ] **Persona "+ N more ›"** — `:181`. Handler: `stopPropagation(); setQ('persona')` — switches to search view with the literal query `persona`. Shown when `persona.copies.length > 6`.
- [ ] **Base card** — `:192`, class `v2-card`. Handler: `openResume(b.id)`. Header line: name (`:194`), meta (`:195`), avg fit (`:196-200`, `title="Average fit across this base's scored copies (archived included)"`).
- [ ] **Base in-flight chip** — `:205-208`. **No handler**. One per `/monitor/active` row whose `baseId` string-equals `b.id` (`:190`).
- [ ] **Base copy chip** — `:211-216`, class `v2-chip`, `title={c.name}`. Handler: `stopPropagation(); openResume(c.id)`. First 6 only (`:210`).
- [ ] **Base "+ N more ›"** — `:218`. Handler: `stopPropagation(); setQ(b.name.split(' ')[0])` — searches by the **first word** of the base name.
- [ ] **Archived browse row** ("Archived · N cop(y/ies) from rejected or stale applications" + "browse ›") — `:225-228`, class `v2-act`. Handler: `setShowArchived(true)`. Shown only when `archived.length > 0` (`:224`).

### Grouping / archived toggle
- [ ] There is **no grouping control** — grouping is fixed: "Profile" label (`:156`) → Persona card → "Résumés" label (`:185`) → base cards (ordered as returned by the API, `updated_at desc` per `routes_resumes.py:478`) → archived row.
- [ ] The **archived toggle** is the browse row (`:225`) + "‹ Back" (`:139`); there is no checkbox/switch. Typing in search also clears `showArchived` (`:112`).
- [ ] **Card ⋯ menus: none exist** on the shelf — no per-card menu, rename, delete, or duplicate. Only click-to-open.

### Add modal (`AddModal`, `:239-282`, opened at `:234`)
- [ ] **Scrim** — `:265`. Handler: `onClose` (closes on outside click). Inner panel stops propagation `:266`.
- [ ] **Name input** — `:269-271`, `autoFocus`, placeholder "Résumé name (e.g. Backend — Platform v4)". Handlers: `onChange → setName`; `onKeyDown Enter → createScratch()` (`:270`).
- [ ] **Inline error text** — `:272`, red (`var(--bad)`), rendered when `err` non-empty. This modal uses **no toasts**.
- [ ] **"Create from scratch"** — `:274`. Handler: `createScratch` (`:247-252`): guard `!name.trim() || busy`; **POST `/resumes`** `{ name, is_base: true, json_data: EMPTY }` (`:250`); success → `onCreated(data.id)` → `:234` closes modal and `openResume(id)`. Failure: `setErr(e.response?.data?.detail || 'Create failed')` (`:251`) — inline text, `busy` reset. Visual disabled state (grey bg, default cursor) when name empty (`:274`) but the click handler is still attached (guard inside). Label becomes "Creating…" while busy.
- [ ] **"Import PDF ↑"** — `:275`, class `v2-act`. Handler: `fileRef.current?.click()`. No busy label on this button.
- [ ] **Hidden file input** — `:276`, `accept="application/pdf"`. Handler: `importPdf(e.target.files?.[0])` (`:253-262`): guard `!file || busy`; **POST `/resumes/import-pdf`** multipart (`:258`); then **POST `/resumes`** with `name.trim() || file.name` minus `.pdf` and `json_data: parsed.json_data || parsed` (`:259`); success → `onCreated(data.id)`. Failure: `setErr(detail || 'Import failed — is it a text PDF?')` (`:261`). Choosing the same file twice will not re-fire `onChange` (input value never reset).
- [ ] **"Cancel"** — `:278`. Handler: `onClose`.

## 1.4 States rendered

- [ ] **Loading** — `:119` "Loading…" (centered, muted) while `loading` true.
- [ ] **Search header** — `:124` "{n} match / matches — bases, copies, and archived".
- [ ] **Search zero results** — `:126` "Nothing matches “{q}” — search covers base names, company names, and job titles." (dashed box).
- [ ] **Archived header** — `:140` "Archived · {n} from rejected or stale applications".
- [ ] **Archived list empty** — **no branch**. Reachable only if the shelf reloads (in-flight tailor finishing → `load()` `:68`) while in the archived view and `archived` becomes `[]`: header shows "Archived · 0 …" over nothing.
- [ ] **No bases** — `:151` "No base résumés yet. Create one to start." This branch also **hides the Persona card and the archived row** even if persona-tailored copies or archived copies exist (`:150` checks only `bases.length`).
- [ ] **Shelf load failure** — **no branch**; falls through to "No base résumés yet." (see 1.2).
- [ ] **Header subtitle** — `:109` "{bases} base(s) · {totalCopies} tailored cop(y/ies) live under their jobs[ · {archived} archived]". No truncation.
- [ ] **Persona meta** — `:160`: "your full profile · " then `copy_count > 0 ? "N recent cop(y/ies)" : archived_count > 0 ? "no recent copies" : "no copies"`, then `edited {timeAgo}` only if `updated_at` (persona `updated_at` = newest live copy's timestamp, `routes_resumes.py:603`).
- [ ] **Persona avg fit** — `:161-165`, hidden when `avg_fit == null`.
- [ ] **Persona chips row** — `:167` hidden unless `copies.length > 0` or an in-flight persona tailor exists.
- [ ] **Base meta** — `:195`: same recent/no-recent/no-copies logic, then `edited {timeAgo(b.updated_at)}`. `timeAgo('')`/null returns `''` (`:7`) → renders "edited " with nothing after it when `updated_at` is null.
- [ ] **Base avg fit** — `:196-200`, hidden when null.
- [ ] **Base chips row** — `:202` hidden unless copies or in-flight.
- [ ] **In-flight chip** — `:170`/`:205` "tailoring…" with spinner, `title="Tailoring in progress — opens when ready"`. A freeform tailor (`scope … :freeform`) also renders a spinner chip (it has a `baseId`).
- [ ] **Fresh dot** — `:178`/`:215` amber 6px dot when `c.fresh` (backend `_fresh` = any `suggested_bullets` present, `routes_resumes.py:495-499`).
- [ ] **"+ N more ›"** — `:181`/`:218` when more than 6 copies.
- [ ] **Score colouring** — `scoreColor` `:16`: ≥70 good, ≥50 warn, else bad (applied to `avg_fit` too, `:162`/`:197`).
- [ ] **Long strings**: result-row name ellipsis `:130`; archived-row name ellipsis `:145`; chip label ellipsis with `maxWidth: 250` `:175-176` / `:212-213`; **base name `:194` has no truncation** (wraps/pushes the avg-fit badge); persona/base meta `:160`/`:195` no truncation; `copyLabel` `:19-27` falls back to `c.name` when neither company nor role.
- [ ] **AddModal error** — `:272` inline red text (`err`).
- [ ] **AddModal busy** — `:274` label "Creating…" (Create button only; Import button shows no busy state).

## 1.5 Hover styles

- [ ] `.v2-navlink` — `:123`, `:139` (Back links). CSS: `theme.css:133-134` (`background: var(--surface-2); color: var(--text)`).
- [ ] `.v2-act` — `:128` (result row), `:143` (archived row), `:225` (browse row), `:275` (Import PDF). CSS: `theme.css:147` (`border-color: var(--accent) !important; background: var(--hover-soft) !important`).
- [ ] `.v2-card` — `:157` (Persona card), `:192` (base card). CSS: `theme.css:138,142` (border accent + `--hover-soft`).
- [ ] `.v2-chip` — `:175`, `:211` (copy chips). CSS: `theme.css:143-144` (border accent, bg surface, `color: var(--good)`, ring `--ring-accent`).
- [ ] `.v2-spin` — `:171`, `:206` (in-flight ring). CSS: `theme.css:225-226` (animation only, not a hover).
- [ ] **No inline `onMouseEnter`/`onMouseLeave`** and no `style-hover` props in this file.
- [ ] Controls with **no hover style at all**: "+ New résumé" `:114`, "+ N more ›" `:181`/`:218`, "browse ›" text `:227` (parent row has `v2-act`), AddModal "Create from scratch" `:274`, "Cancel" `:278`, search input `:112`.

## 1.6 Theme

- [ ] Dark mode is read once in the shell: `V2App.jsx:52` (`localStorage.getItem('jobnavigator_dark_mode') === 'true'`), applied as `data-theme={dark ? 'dark' : 'light'}` on `.jn-v2` at `V2App.jsx:90`; tokens swap in `theme.css:74` (`.jn-v2[data-theme="dark"]`). `Resumes.jsx` never reads the theme itself.
- [ ] **Colour literals in `Resumes.jsx`: none** (grep for `#hex`, `rgb(`, `hsl(` returned nothing). All colours are `var(--…)` tokens: `--good/--warn/--bad` (`:16`), `--surface-2/--muted/--accent-soft/--accent/--faint` (`:97-101`), `--line`, `--surface`, `--bg`, `--text`, `--text-2`, `--accent-ink`, `--scrim`, `--shadow-modal`, `--edge`.
- [ ] `--faint` is defined once as `var(--muted)` at `theme.css:68` (shared scope, outside both palette blocks) — resolves in both themes. `--shadow-modal` at `theme.css:27` (shared).

## 1.7 Suspicious

- [ ] `:49` — shelf load failure only `console.error`s; the UI shows the "No base résumés yet" copy instead.
- [ ] `:65` — "shrank" is decided by comparing **string lengths** of the joined scope keys, not row counts. A finished tailor replaced in the same tick by a new one with a longer key would not trigger a reload; a same-length swap would not either.
- [ ] `:60` — `scope_key.split(':')` assumes exactly two segments; the persona base id is the literal string `'persona'` (`:167`, `:169`) — relies on backend scope format `routes_resumes.py:715`.
- [ ] `:114`, `:274`, `:275`, `:278` — all "buttons" are `<div>`s with `onClick`; no keyboard/`role`/`tabIndex` (Enter on the name input is the only keyboard path, `:270`).
- [ ] `:151` — `bases.length === 0` branch hides the Persona card and the archived row (persona-only workflows invisible until a base exists).
- [ ] `:181` — `setQ('persona')` assumes persona-tailored copies' `name` or `copyLabel` contains "persona" (search matches `${copyLabel(c)} ${c.name}` `:88`). Not verified against the tailor route's naming.
- [ ] `:218` — `setQ(b.name.split(' ')[0])`: a generic first word (e.g. "Backend", "Senior") matches other bases' copies too; a base whose first word is unique to it works.
- [ ] `:245` — `EMPTY` skeleton is **duplicated** from `ResumeSections.jsx:16` rather than imported; drift risk.
- [ ] `:259` — `parsed.json_data || parsed`: import-pdf response shape is assumed loosely.
- [ ] `:276` — file input `value` never reset; picking the same PDF twice in one modal session does nothing.
- [ ] `:195` — `edited ${timeAgo(...)}` renders "edited " when `updated_at` is null.
- [ ] `:86` — base search result shows `avg_fit` in the score slot with score colouring; visually indistinguishable from a real fit score.
- [ ] No `console.log`, `TODO`, `FIXME` in this file (grep). No handler defined-but-unattached. All imports (`useState, useEffect, useMemo, useCallback, useRef, useNavigate, api`) are used.

## 1.8 Counts that must agree

- [ ] **Header "{n} base(s)"** `:109` = `data.bases.length` from GET `/resumes/shelf` (`routes_resumes.py:608` `bases: out`, one per `Resume.is_base`). Must equal the **rail "Résumés" count** (`V2App.jsx:59`, GET `/resumes?is_base=true` length) and the number of base cards rendered (`:188`).
- [ ] **Header "{n} tailored copies"** `:109` = `total_copies` = `len(copies) - len(archived)` (`routes_resumes.py:608`). Must equal Σ `bases[].copy_count` + `persona.copy_count` (each = `len(copies_out)`, `:569`, `:598`).
- [ ] **Header "{n} archived"** `:109`, archived header `:140`, browse row `:226` = `data.archived.length`. Backend also returns `archived_count` (`:609`) — unused by the client; must equal `Σ bases[].archived_count + persona.archived_count`.
- [ ] **Per-base "N recent copies"** `:195` = `b.copy_count` = `len(copies_out)` (`:569`) which excludes rejected/stale; must equal `b.copies.length` (`:189`) and the chip count (≤6 shown + "+N more").
- [ ] **Persona "N recent copies"** `:160` = `persona.copy_count` vs `persona.copies.length`.
- [ ] **avg fit** `:162`/`:197` = `int(round(mean))` over scored copies **including archived** (`:539-541`, `:579-581`) — so a base with `copy_count 0` but archived scored copies still shows an avg. Tooltip says so.
- [ ] **Copy chip score** `:177`/`:214` = `_copy_score(job, c.name)` (`routes_resumes.py:521-531`): `cv_scores[c.name]` → `cv_scores['Tailored']` → max numeric. Compare with **Editor score ring** (`ResumeEditor.jsx:197` = `cv_scores['Tailored']` only) and **Feed chip** (`v2/JobFeed.jsx:24-25` `bestScore` = max of all numeric entries, base names included). The three can disagree for the same copy: Feed shows the base résumé's score when it beats the tailored one; Editor shows nothing when only a name-keyed score exists.
- [ ] **In-flight chips** `:169`/`:204` = rows of GET `/monitor/active` with `job_type 'tailor_resume'`; the same run is what the Editor waits for (via a different mechanism — see 2.2).
- [ ] **Search header "{n} matches"** `:124` = `results.length` (client-side, `:81-95`) = rendered rows.

---

# 2. Editor — `v2/ResumeEditor.jsx` + `v2/ResumeSections.jsx` (route `/v2/resumes/:id`)

## 2.1 Routes & params

- [ ] Route registered at `App.jsx:157` — `<Route path="resumes/:id" element={<V2ResumeEditor />} />` under `/v2`.
- [ ] `:id` read via `useParams` — `ResumeEditor.jsx:69`. Used verbatim in every `/resumes/${id}` call; no validation.
- [ ] **Missing / deleted id**: GET `/resumes/{id}` rejects → `.catch(() => navigate('/v2/resumes'))` — `:159`. Silent redirect to the shelf; **no toast, no "not found" message**. Same behaviour for a 401/500 as for a 404.
- [ ] **Query params: none are read.** `useSearchParams` is imported (`:2`) and `const [, setSearchParams] = useSearchParams()` is declared (`:71`) but `setSearchParams` is **never called**. `?job=`, `?tailor=`, etc. are NOT handled on this route.
- [ ] Outbound deep-links produced here: `/v2/feed?job={job_id}` (`:385`), `/v2/cover-letters?resume={id}[&job={job_id}]` (`:233`), `/v2/resumes/{parent_id}` (`:352`), `/v2/resumes/{new id}` from toasts (`:112`, `:142`), `/v2/resumes` (`:324`, `:159`, `:230`).
- [ ] localStorage: `jobnavigator_v2_resume_sections` — read `:81` (JSON array → `Set`, default `['Experience']` `:82`), written `:306` (`toggle`). **One key shared by every résumé** (and by Persona if it uses the same key — not verified here). Both wrapped in try/catch.
- [ ] Tab title: `useTitle(doc?.name)` — `:302` → "{name} · JobNavigator" (`useTitle.js:47-54`); falls back to "Résumés" from `TitleSync` until the doc loads.

## 2.2 Data loads

Mount / on `id` (`:154-162`):
- [ ] **GET `/resumes/{id}`** `:156` → `doc`, `data = json_data || EMPTY`, `template`, `format` (default `'letter'`), `savedAt`. Guarded by `alive` flag. Failure → redirect (`:159`).
- [ ] **GET `/resumes/templates`** `:160` → `templates`. `.catch(() => {})` — **silent catch**.

On `doc` (`:165-174`):
- [ ] Base résumé → **GET `/resumes?is_base=false`** `:169` → `baseCopyCount` = client-side count of rows with `parent_id === doc.id` (includes archived/rejected/stale copies). **silent catch**.
- [ ] Copy with `parent_id` → **GET `/resumes/{parent_id}`** `:171` → `baseData = json_data`. **silent catch** (failure → no diff, no ✦ marks, no "Review" stage — silently).
- [ ] Copy without `parent_id` (persona-tailored) → `baseData = null` `:172` → `changes` always `[]`.

On `doc, id` (`:189-193`), copies only:
- [ ] `loadJobCtx` `:184-188` (returns early if no `job_id`): **GET `/jobs/{job_id}`** `:186` → `jobData`; **GET `/cover-letters?job_id=`** `:187` → `coverExists` (backend filter at `routes_cover_letters.py:154-157`). Both **silent catch**.
- [ ] **GET `/resumes/{id}/tracer-stats`** `:192` → `tracers` (fields `token, source_label, destination_url, clicks, last_clicked, is_active` — `routes_resumes.py:1312-1319`; `clicks` excludes `is_likely_bot`). Fetched even for a job-less copy. **silent catch**.

Polling:
- [ ] **Pending-tailor watcher** `:104-119`: `setInterval` **3000 ms**, runs only while `pendingRef.current.length > 0`; **GET `/resumes?is_base=false`** `:108`; a pending entry `{baseId, jobId, company, since}` is resolved when a row has matching `parent_id` + `job_id` and `updated_at >= since − 1000 ms` (`:111`) → `success` toast "Tailored copy for {company} is ready." with action "Open ↗" (`:112`); gives up silently after **120 s** (`:113`). **Not keyed by `/monitor/active`** (unlike the Shelf). Errors swallowed `:116`.
- [ ] **Score watcher** `:210-218` (inside `runScore`): `setInterval` **3000 ms**, **GET `/jobs/{job_id}`** `:213`, resolves when `cv_scores['Tailored']` is a number (`:214`), gives up after **60 s** (`:216`) with no toast. **Not keyed by `/monitor/active`** either; the backend run is `score_resume` with scope `f"{job_id}:resume:{resume_id}"` (`routes_resumes.py:1277-1282`) but the client never reads it. Errors swallowed `:217`.
- [ ] **Autosave** `persist` `:246-253`: debounce **500 ms**, **PATCH `/resumes/{id}`** with `{json_data}` / `{template}` / `{page_format}`. Failure → `console.error(e)` `:250` — **silent catch**; `saving` flips back to false and `savedAt` is NOT updated, so the status text just reverts to the previous "saved X ago". `saveTimer` is not cleared on unmount (the PATCH still fires; state setters run on an unmounted component).
- [ ] **PDF preview** `:261-275`: debounce **800 ms** on `[data, template, format, doc, id]`; **GET `/resumes/{id}/pdf?template&format`** as `arraybuffer` `:268` with `AbortController` (previous request aborted `:265`); blob URL swapped and previous revoked `:270`, revoked on unmount `:276`. Failure (non-cancel) → `console.error('pdf', e)` `:271` — **silent catch**; the iframe keeps the last good PDF or stays blank.

Modals (on open):
- [ ] `RetailorModal` `:469-472`: **GET `/resumes?is_base=true`** `:470`, **GET `/persona`** `:471` (persona option shown when `resume_content` has keys). Both **silent catch**.
- [ ] `TailorModal` `:553-558`: **GET `/jobs?status=saved,applied,new&sort_by=date&limit=60`** `:554` (response `{total, jobs}` per `routes_jobs.py:155-156`; client reads `data.jobs || data.items || data`), **GET `/resumes?is_base=false`** `:556` → `existing` set of job ids already tailored from this base. Both **silent catch**.

## 2.3 Interactive elements

### Top bar (`:323-329`)
- [ ] **"‹ Résumés"** — `:324`, class `v2-navlink`. Handler: `navigate('/v2/resumes')`.
- [ ] **Kind badge** "tailored"/"base" — `:326`. No handler.
- [ ] **Document name** — `:327`, `title={doc.name}`, ellipsis `maxWidth: 460`. **Read-only — there is no rename control anywhere in the editor** (no input, no menu item, no PATCH of `name`).
- [ ] **Save status** — `:328`: "Saving…" / "saved {timeAgo} · autosaves" / "autosaves on blur". Display only.

### Copy sub-band (`isCopy`, `:332-393`)
- [ ] **Score ring** — `:335-341` (SVG, `r=35`, circumference 219.9; stroke `scoreColor(scores.tailored)`; number inside). **No handler.** Hidden when `scores.tailored == null` (`:334`). Source: `jobData.cv_scores['Tailored']` rounded (`:197`).
- [ ] **"based on {baseName} ↗"** with optional delta — `:352-355`, class `v2-navlink`, `title="Open the {baseName} base résumé this was tailored from"`. Handler: `navigate('/v2/resumes/${doc.parent_id}')`. Delta `:353` = `scores.tailored − scores.base` (accent if ≥0, warn if <0 `:348`). `baseName` = text before "→" in `doc.name` (`:347`). Rendered only when `doc.parent_id` (`:346`).
- [ ] **Sub-line** — `:360-363`: "N reviewable change(s)" / "not scored yet" / "ready" + " · tracers: {source_label} {clicks} · …" when `tracers.length > 0`. Display only.
- [ ] **"One next step" CTA** — `:366-369`, `title` "The one next step" / "Pipeline complete". Handler: `!stage.done && stage.act && stage.act()`. `stage` (`:236-243`) resolves in order: (1) `changes.length > 0` → "Review N change(s)" → `setReviewOpen(true)`; (2) `scores.tailored == null` → "Score the result" (or "Scoring…") → `runScore('full')`; (3) `!coverExists` → "✉ Write cover letter" → `goCover`; (4) `jobData.status !== 'applied'` → "Mark applied" → `markApplied`; (5) "Applied ✓" (done, soft style, no handler). Spinner `:367` (`v2-spin`) while `scoring`. **No hover class.**
- [ ] **⋯ menu button** — `:372`, class `v2-act`. Handler: `setHeadMenu(v => !v)`. Accent border/bg while open.
- [ ] **Menu backdrop** — `:375`. Handler: `setHeadMenu(false)`.
- [ ] Menu item **"✦ Re-tailor…"** (hint "adds a copy") — `:378` (`MenuItem`, `ResumeSections.jsx:107-113`, class `v2-menuitem`). Handler: close menu + `setTailorOpen(true)` → `RetailorModal` (`:450`).
- [ ] Menu item **"◎ Score again · light"** (hint "score only") — `:379`. Handler: `runScore('light')` (`:203-220`): if no `job_id` → `error` toast "This copy isn’t linked to a job to score against." (`:204`); else **POST `/resumes/{id}/score-check`** `{depth}` (`:207`) → `progress` toast "Scoring (light) — runs in the background." (`:208`) → poll (2.2) → `success` toast "Scored: N (+Δ vs base)" (`:215`). Failure: `error` toast — 409 → "Already scoring this copy.", else `detail || 'Scoring failed to start.'` (`:219`). Mutates `scoring`, `jobData`, `headMenu`.
- [ ] Menu item **"◎ Score again · full"** (hint "with report") — `:380`. Handler: `runScore('full')`, same as above.
- [ ] Menu item **"≋ Review changes"** (hint "{n} applied") — `:381`, only when `changes.length > 0`. Handler: close menu + `setReviewOpen(true)`.
- [ ] Menu item **"✉ Cover letter"** (hint "c") — `:384`. Handler: `goCover` (`:233`) → `navigate('/v2/cover-letters?resume={id}&job={job_id}')` (`&job` omitted when no job). No API. The hint "c" implies a keyboard shortcut — **no keyboard handler exists** in this file.
- [ ] Menu item **"↗ Open in feed"** (hint "e") — `:385`, only when `doc.job_id`. Handler: `navigate('/v2/feed?job={job_id}')`. Hint "e" — **no shortcut wired**.
- [ ] Menu item **"✓ Mark applied"** (hint "a") — `:386`, only when `doc.job_id`. Handler: `markApplied` (`:222-226`): **PATCH `/jobs/{job_id}`** `{status: 'applied'}` → `loadJobCtx()` → `success` toast "Marked applied." Failure → `error` toast "Could not mark applied." Hint "a" — **no shortcut wired**.
- [ ] Menu item **"✕ Delete copy"** — `:388`, class `v2-hover-bad`, red. Handler: `deleteResume` (`:228-231`): native `window.confirm("Delete “{name}”?")` (`:229`; appends " Its tailored copies will be removed too." for bases — unreachable from this menu since it is copy-only) → **DELETE `/resumes/{id}`** → `navigate('/v2/resumes')`. Failure → `error` toast "Delete failed." **The delete confirm is the browser's native dialog, not a v2 modal.**

### Base sub-band (`!isCopy`, `:395-398`)
- [ ] **Copy count text** — `:396` "Base résumé · {N tailored cop(y/ies)} · editing here changes future tailoring only" (count hidden until `baseCopyCount` loads).
- [ ] **"✦ Tailor for a job…"** — `:397`. Handler: `setTailorOpen(true)` → `TailorModal` (`:451`). **No hover class.**
- [ ] **A base résumé has NO ⋯ menu, no Delete, no Cover letter, no Score, no rename** — only the Tailor button. Base résumés cannot be deleted from the v2 UI.

### Section cards (left pane, `:404-411`; `SectionShell` at `ResumeSections.jsx:123-141`)
- [ ] **Section header toggle** ×7 (`SECTION_ORDER` `ResumeSections.jsx:17`: Header, Summary, Experience, Skills, Education, Projects, Publications) — `ResumeSections.jsx:126`, class `v2-hover-accent`. Handler: `onToggle` → `toggle(name)` (`ResumeEditor.jsx:304-308`, persists to localStorage). Shows chevron `⌄`/`›` (`:127`), name, `(count)` for Experience/Skills/Education/Projects/Publications (`sectionCounts` `:23-29`; Header and Summary get no count), and `meta` "● changed by tailoring" (`ResumeEditor.jsx:407`, `title="Contains unreviewed tailoring changes"`) when `changedSections` has the name (`:177-181`: Summary / Experience / Skills only).
- [ ] Every editor mutation goes through `makeMutators` (`ResumeSections.jsx:32-39`): `mutate(fn)` deep-clones via JSON and calls `onData` → `setData` + `persist({json_data})` (`ResumeEditor.jsx:254`). `setField(path, val)` splits on `.`, refuses `__proto__/constructor/prototype` segments (`:15`, `:35`). **Saving is per keystroke (debounced 500 ms), not on blur**, despite the status text at `ResumeEditor.jsx:328`.

#### Header (`HeaderEditor`, `ResumeSections.jsx:158-193`)
- [ ] **Full name** input — `:170`. Handler: `setField('header.name', v)`.
- [ ] **Contact item ▲ / ▼** — `:163` (class `v2-navlink`, 8px glyphs). Handler: `move(i, ±1)` (`:160`, swaps in `header.contact_items`, no-op at bounds).
- [ ] **Contact "Display text"** input — `:182`. Handler: `setField('header.contact_items.{i}.text')`.
- [ ] **Contact "URL (optional)"** input — `:183`. Handler: `setField('…{i}.url')`.
- [ ] **Contact "id" stub** input — `:184`, only when `url` set and not `mailto:` (`:178`), `title="Short stub for the tracer link id (e.g. l, w, gh)"`. Handler: `setField('…{i}.stub')`.
- [ ] **Contact ✕** — `:185`, class `v2-hover-bad`, `title="Remove"`. Handler: `mutate(d => d.header.contact_items.splice(i, 1))`.
- [ ] **"+ Add contact item"** — `:189` (`DashedAdd`, class `v2-dashadd`). Handler: push `{text: '', url: ''}` (creates `header` if missing).
- [ ] Header has **no empty state** — an empty `contact_items` shows only the add row.

#### Summary (`SummaryEditor`, `ResumeSections.jsx:261-274`)
- [ ] **Summary text** — `:268` (`BulletText`, borderless auto-grow textarea, Ctrl/Cmd+B wraps selection in `**` `:80-88`). Handler: `setField('summary', v)`.
- [ ] **↩ revert** — `:269`, only when `baseSummary != null && baseSummary !== txt` (`:263`), `title="Decline this tailoring change — restores the base text"`. Handler: `setField('summary', baseSummary)`. Row tinted `--change-bg` and marked ✦ when changed (`:266-267`).
- [ ] **Char count** — `:271` "{n} characters" + " · long summaries can push to a second page" when `pageHint && n > 600`. Display only.
- [ ] Summary has **no empty state** (shows "0 characters").

#### Experience (`ExperienceEditor`, `ResumeSections.jsx:194-259`)
- [ ] **Role header toggle** — `:213`, class `v2-hover-accent`. Handler: local `toggle(i)` (`:206`; `useState(new Set([0]))` `:196` — first entry open by default, **not persisted**, indexed by position). Shows title (`'Untitled role'` fallback `:215`), company, date (mono), "N bullet(s)" (`:218`), ● when `entryChanged` (`:219`, `:205`).
- [ ] **Company / Title / Location / Date** fields — `:224-227` (`Field`, `:42-61`; Date is `mono` with placeholder "Jan 2022 – Present"). Handlers: `setField('experience.{i}.{key}')`.
- [ ] **Description** field — `:229`, placeholder "Optional role description". Handler: `setField('experience.{i}.description')`.
- [ ] **Bullet text** — `:235` (`BulletText`). Handler: `setBullet(i, bi, v)` (`:197`).
- [ ] **Bullet ↩** — `:236`, only for `kind === 'changed'` marks (`bulletMark` `:198-204`: index ≥ base length → "Added by tailoring"; text differs → "Changed by tailoring"), `title="Decline this tailoring change — restores the base text"`. Handler: `setBullet(i, bi, m.base)`. Added bullets get a ✦ but **no inline decline** (only via Review modal).
- [ ] **Bullet ✕** — `:237`, class `v2-hover-bad`. Handler: `mutate(d => d.experience[i].bullets.splice(bi, 1))`.
- [ ] **Suggested bullet row** — `:242-246` ("✦ … suggested", `title="Suggested by tailoring — keep on review"`). **No handler; no inline keep/discard** — only the Review modal resolves it.
- [ ] **"+ Add bullet"** — `:248` (inline `v2-act` dashed row, NOT `DashedAdd`). Handler: push `''`.
- [ ] **"Remove role"** — `:249` (`RemoveLink`, class `v2-hover-bad`). Handler: `splice(i, 1)`. **No confirm.**
- [ ] **"+ Add experience"** — `:256` (`DashedAdd big`). Handler: push `{company, title, location, date, description, bullets: []}`.
- [ ] **No reorder** for experience entries or bullets (no ▲▼).

#### Skills (`SkillsEditor`, `ResumeSections.jsx:277-310`)
- [ ] **Row ▲ / ▼** — `:283` (`v2-navlink`). Handler: `move(k, ±1)` (`:280`, rebuilds object from swapped entries).
- [ ] **Category** input — `:295`, **uncontrolled** (`defaultValue={k}`), saves on **blur** via `rename(k, value)` (`:279`; no-op if unchanged or blank; a rename onto an existing key silently **merges** the two rows, the later one winning).
- [ ] **Values** input — `:298`, placeholder "Skill values…". Handler: `setField('skills.{k}', v)` — a category containing `.` mis-routes the path.
- [ ] **"added" pill** — `:299`, when `baseSkills != null && !(k in baseSkills)`. Display only.
- [ ] **↩ revert** — `:300`, when changed vs base, `title="Decline this tailoring change"`. Handler: `setField('skills.{k}', baseSkills[k])`.
- [ ] **Row ✕** — `:302`, class `v2-hover-bad`. Handler: `mutate(d => delete d.skills[k])`.
- [ ] **"+ Add skill row"** — `:307` (`DashedAdd`). Handler: `d.skills['Skill {n+1}'] = ''` — **collides** with an existing "Skill N" category (overwrites its value with `''`).

#### Education (`EducationEditor`, `ResumeSections.jsx:311-331`)
- [ ] **School / Location / Degree / Years** — `:317-322` (`MicroField` `:114-119`; Years is mono, placeholder "2015 – 2019"). Handlers: `setField('education.{i}.{key}')`.
- [ ] **"Remove"** — `:324` (`RemoveLink`). Handler: `splice(i, 1)`. No confirm.
- [ ] **"+ Add education"** — `:328`. Handler: push `{school, location, degree}` (note: no `years` key until typed).
- [ ] No reorder.

#### Projects (`ProjectsEditor`, `ResumeSections.jsx:332-360`)
- [ ] **Name / URL / Description** — `:338-341`. Handlers: `setField('projects.{i}.{key}')`.
- [ ] **Project bullet text** — `:347` (`BulletText`). Handler: `mutate(d => d.projects[i].bullets[bi] = v)`.
- [ ] **Project bullet ✕** — `:348`, `v2-hover-bad`. Handler: splice.
- [ ] **"+ Add bullet"** — `:351` (`DashedAdd`). Handler: push `''`.
- [ ] **"Remove project"** — `:353`. Handler: splice. No confirm.
- [ ] **"+ Add project"** — `:357`. Handler: push `{name, description, url, bullets: []}`.
- [ ] No reorder; no tailoring marks on project bullets.

#### Publications (`PublicationsEditor`, `ResumeSections.jsx:361-375`)
- [ ] **Title / Description** — `:367-368`. Handlers: `setField('publications.{i}.{key}')`.
- [ ] **"Remove"** — `:369`. Handler: splice. No confirm.
- [ ] **"+ Add publication"** — `:372`. Handler: push `{title, description}`.
- [ ] No reorder.

### Right pane — PDF preview (`:414-446`)
- [ ] **Template picker** — trigger `:419` (class `v2-act`, `title="Résumé template"`, label "Template {tplLabel}" where `tplLabel` `:318` = template name → raw id → "Template"). Handler: toggle `tplOpen`, close `fmtOpen`. Backdrop `:422`. Items `:424` (class `v2-menuitem`, accent when selected). Item handler: `pickTemplate(t.id)` (`:255`) → `setTemplate`, close, `persist({template})` → PATCH; PDF re-renders via the effect. Empty `templates` → empty dropdown, **no message**.
- [ ] **Paper picker** — trigger `:431` (`v2-act`, `title="Paper size"`, "Paper US Letter/A4"). Backdrop `:434`. Items `:436` (`letter` → "US Letter", `a4` → "A4"). Handler: `pickFormat(v)` (`:256`) → `persist({page_format})`.
- [ ] **"↓ Download PDF"** — `:441`, a real `<a target="_blank" rel="noopener noreferrer">` to `pdfDownloadUrl` (`:310-313` = `{origin-less}/api/resumes/{id}/pdf?template=&format=`). **Bypasses axios** — the `X-API-Key` header (`api.js:10-16`) is not sent; relies on the `jn_session` cookie (`api.js:6`). No hover class. Not a JS download (works in the artifact-style sandbox only as a navigation).
- [ ] **Preview iframe** — `:444`, `src="{blobUrl}#view=FitH"`, only when `pdfUrl` set. **There is no manual "refresh preview" control** — refresh is implicit (800 ms after any data/template/format change, 2.2). No loading indicator on the preview while re-rendering; no error state.

### Tailor modal (base résumés; `TailorModal` `:544-619`, mounted at `:451`)
- [ ] **Scrim** — `:576` → `onClose`; panel stops propagation `:577`.
- [ ] Title "Tailor {doc.name} for a job" `:579`; subtitle "Changes land automatically — you review and decline afterwards." `:580`.
- [ ] **"Tailor from Persona instead of this base"** checkbox — `:584`. Handler: `setPersonaBase(checked)`. Initial value `baseId === 'persona'` (`:551`) is always `false` because `baseId = doc.id` (`:545`). When checked, `run` sends `base_resume_id: 'persona'` (`:573`).
- [ ] **"Search jobs…"** input — `:589`. Handler: `setQ`. Filters `title + company` (`:568`).
- [ ] **Job row** — `:593` (class `v2-act`, radio glyph `:594`). Handler: `setPick(j.id); setJd('')`. Shows title `:596`, "{company} · {status}" `:597`, score `:599` (`jobScore` `:561-566`: `cv_scores[doc.name]` → `['Tailored']` → max numeric; `title="This base's fit on that job"`), "✦ exists" `:600` (`title="A tailored copy already exists — tailoring again adds another"`) when `existing` has the job. List: 60 fetched, saved/applied sorted first (`:569`), **first 40 rendered** (`:590`).
- [ ] **Freeform JD textarea** — `:608`, placeholder "Paste any JD — the copy won't be linked to a feed job", `rows=3`, resizable. Handler: `setJd`; non-empty text clears `pick`.
- [ ] **"Cancel"** — `:613` (`v2-act`). Handler: `onClose`.
- [ ] **"✦ Tailor"** — `:614`. Enabled when `pick || jd.trim()` (`:571`). Handler: `run` (`:573`) → `onRun` = `runTailor` (`:121-131`): closes modal, **POST `/resumes/tailor`** `{base_resume_id, job_id?, job_description?}` → `progress` toast "Tailoring for {company}… runs in the background." (`:126`); if `jobId` set, a pending watcher entry is pushed (`:125`) so a `success` toast with "Open ↗" arrives later. **Freeform tailors get no completion toast** (no `jobId` → never pushed). Failure: `error` toast — 409 "Already tailoring for that job." else `detail || 'Tailoring failed to start.'` (`:128-129`). Backend fast-fails (routes_resumes.py:702-712) on a job with no description/URL/cached page (400) or an empty `cv_tailor_prompt` setting (500) — both surface via `detail`.
- [ ] Empty list — `:604` "No jobs match — paste a description below instead." (also shown when the `/jobs` fetch fails).

### Re-tailor modal (tailored copies; `RetailorModal` `:463-541`, mounted at `:450`)
- [ ] **Scrim** — `:489`; panel `:490`.
- [ ] Title "Re-tailor for this job" `:492`; subtitle "{company} — {title} · adds a new copy" or "the job this copy is for · adds a new copy" `:494` (ellipsis).
- [ ] **Mode cards "✦ Tailor" / "Copy"** — `:505` (`v2-act`, `title` = hint: "Rewrites bullets against this job description" / "Exact copy of the base, with its own tracer links"). Handler: `setMode(id)`.
- [ ] **Base radio rows** — `:520` (`v2-act` unless disabled). Options `:476-479`: "Persona · your full profile" (only if `/persona` returned non-empty `resume_content`) + every base résumé. Handler: `!off && setBaseId(o.id)`. Right label shows "current base" for `doc.parent_id || 'persona'` (`:525`). Disabled (`opacity .45`, `title="Persona has no résumé row to copy — tailor from it instead"`) when `mode === 'copy' && id === 'persona'` (`:480`, `personaCopyable` hard-coded `false` `:475`).
- [ ] Empty options — `:529` "No base résumés yet." (also when the fetch fails).
- [ ] Footer note — `:534` "Runs in the background" / "Instant — no LLM call".
- [ ] **"Cancel"** — `:535` (`v2-act`).
- [ ] **"✦ Re-tailor" / "Make copy"** — `:536`. Enabled when `baseId && !disabled(baseId)` (`:481`). Handler: `onRun({mode, baseId})` = `runRetailor` (`:136-152`): `copy` → **POST `/resumes/copy`** `{base_resume_id, job_id: doc.job_id}` (`:141`; backend requires both — 400 otherwise, `routes_resumes.py:643-644`) → `success` toast "Copy created for {company}." with "Open ↗" (`:142`); `tailor` → **POST `/resumes/tailor`** (`:144`) → pending watcher + `progress` toast (`:145-146`). Failure: `error` toast 409 "Already tailoring for that job." else `detail || 'Could not start.'` (`:149-150`). Default `baseId = doc.parent_id || 'persona'` (`:467`) — a persona-tailored copy pre-selects "persona" even when that option is absent from the list.

### Review modal (`ReviewModal` `:622-665`, mounted at `:452`)
- [ ] **Scrim** — `:626`; panel `:627` (`min(920px, 94vw)` × `min(760px, 90vh)`).
- [ ] Title "Tailoring changes — already applied" `:630`; subtitle "These landed automatically. Decline any you don't want; the base text comes back." `:631`.
- [ ] **✕ close** — `:633`, class `v2-hover-accent`. Handler: `onClose`.
- [ ] **Per-change "Decline ↩" / "Restore change"** toggle — `:646`. Handler: flips `declined[c.key]`. Row shows `c.where` label `:644`, "applied"/"declined" badge `:645`, and a word-diff `:648-653` (`removed` strikethrough on `--bad-soft`, `added` on `--change-soft`). **There is no per-change "Accept" control — accept is the default; the UI is decline-only.**
- [ ] **"Done reviewing"** — `:660`. Handler: `onApply(declined)` = `applyReview` (`:280-299`): declined `modified` → path reset to `baseText` (`:284-287`); declined `added` → bullet removed **by text match across every experience entry** (`:288-290`); kept `suggested` → appended to that entry's bullets (`:291-292`); every `suggested_bullets` array deleted (`:295`); one `onData` (PATCH) + `success` toast "Review applied — declined changes restored to base." (`:298`). Closes modal.
- [ ] Footer text `:659`: "{n} declined — base text restored · the rest stay" or "All {N} change(s) live · decline any to restore the base text".
- [ ] Empty — `:636` "No tailoring changes to review." (reachable only via stale state; the CTA/menu item are gated on `changes.length > 0`).
- [ ] `changes` come from `computeChanges(baseData, data)` (`:34-54`): summary word-diff, experience bullets **aligned by entry index and bullet index** (`:39-45`), copy bullets beyond base length → `added`, `suggested_bullets` → `suggested`, skills added/modified (`:48-52`). Education/Projects/Publications/Header are never diffed.

### Toasts (`ToastStack` `:454`)
- [ ] `progress`: `:126`, `:146`, `:208`. `success`: `:112`, `:142`, `:215`, `:225`, `:298`. `error`: `:128`, `:129`, `:149`, `:150`, `:204`, `:219`, `:225`, `:230`. No `undo` toasts on this screen. Success toasts carrying an "Open ↗" action (`:112`, `:142`) auto-dismiss after **2.5 s** (`Toast.jsx:21`).

## 2.4 States rendered

- [ ] **Loading** — `:315` "Loading…" while `!doc || !data`.
- [ ] **Id not found / fetch failed** — **no message**; silent `navigate('/v2/resumes')` `:159`.
- [ ] **Copy band: no score yet** — ring hidden `:334`; sub-line "not scored yet" `:361`; CTA "Score the result" `:239`.
- [ ] **Copy band: no job context** (`jobData` null — copy has no `job_id`, or the fetch failed) — headline falls back to "Tailored copy" `:345`. **Same rendering for "no job" and "job fetch failed"** — indistinguishable.
- [ ] **Copy with no `job_id`**: CTA still offers "Score the result" → clicking yields the `error` toast at `:204`; then "✉ Write cover letter" (navigates without `&job=`); "Mark applied"/"Open in feed" menu items hidden (`:385-386`). **No dedicated "not linked to a job" state.**
- [ ] **Copy with no `parent_id`** (persona-tailored): no "based on … ↗" (`:346`), no diff marks, no Review stage; "current base" in Re-tailor shows on the Persona option.
- [ ] **Copy band: changes pending** — sub-line "N reviewable change(s)" `:361`; CTA "Review N change(s)" `:238`; menu item `:381`; section meta "● changed by tailoring" `:407`; entry ● `ResumeSections.jsx:219`; tinted rows `:212`, `:233`, `:266`, `:296`.
- [ ] **Copy band: ready** — "ready" `:361` once scored and no changes.
- [ ] **Delta** — `:353` only when both tailored and base scores exist.
- [ ] **Tracers** — `:362` only when `tracers.length > 0`; **no "no clicks yet" / "no tracer links" copy**.
- [ ] **Scoring in progress** — CTA label "Scoring…" `:239` + spinner `:367`; 60 s give-up leaves the CTA back at "Score the result" with no toast (`:216`).
- [ ] **Base band** — `:396`; copy count hidden until loaded (`baseCopyCount != null`); after a failed fetch it stays hidden forever (no error).
- [ ] **Section empty states** (`EmptyState` `ResumeSections.jsx:100-105`): "No {what} yet" + "Empty sections are skipped in the PDF — nothing prints until you add one." for experience `:255`, skills `:306`, education `:327`, projects `:356`, publications `:365`. **Header and Summary have no empty state.** A résumé with every section empty shows five EmptyStates + a blank Header/Summary — **no whole-document empty branch**; PDF still renders from the backend.
- [ ] **Section counts** — "(n)" `ResumeSections.jsx:130` for five sections; `count == null` → omitted (Header, Summary).
- [ ] **Experience header fallbacks** — "Untitled role" `:215`; "0 bullets" `:218`.
- [ ] **Skills "added" pill** `:299`; **✦ marks** `:234`, `:267`, `:297` with `title` explaining the mark.
- [ ] **Summary length hint** `:271` (>600 chars, only when `pageHint`).
- [ ] **Template label fallback** `:318` (`Template` when nothing loaded). **Templates fetch failure → no message.**
- [ ] **PDF failure** — **no branch**; iframe keeps stale/blank (`:444`).
- [ ] **Save failure** — **no branch**; status silently returns to "saved X ago" (`:328`).
- [ ] **Tailor modal empty** `:604`; **Re-tailor modal empty** `:529`; **Review modal empty** `:636`.
- [ ] **Long strings**: doc name ellipsis `maxWidth 460` `:327`; copy headline ellipsis `:344`; sub-line ellipsis `:360`; re-tailor subtitle ellipsis `:493`; base-row name ellipsis `:524`; job-row title/company ellipsis `:596-597`; experience header title/company ellipsis `:215-216`; base band text `:396` **no truncation**; CTA label `:368` no truncation; menu labels no truncation; Review modal `c.where` no truncation. Bullet textareas auto-grow (`BulletText` `:67-91`, `ResizeObserver`).
- [ ] **Templates list overflow** — `:423` `maxHeight 300` scroll.

## 2.5 Hover styles

All hover is via `theme.css` classes; **no inline `onMouseEnter`/`onMouseLeave` and no `style-hover` props** in either file.

- [ ] `.v2-navlink` (`theme.css:133-134`) — `ResumeEditor.jsx:324` (‹ Résumés), `:352` (based on ↗); `ResumeSections.jsx:163`, `:283` (▲▼ arrows).
- [ ] `.v2-act` (`theme.css:147`) — `ResumeEditor.jsx:372` (⋯), `:419` (Template), `:431` (Paper), `:505` (mode cards), `:520` (base rows, only when enabled), `:535` (Cancel), `:593` (job rows), `:613` (Cancel); `ResumeSections.jsx:248` (+ Add bullet, experience).
- [ ] `.v2-menuitem` (`theme.css:148`) — `ResumeEditor.jsx:424` (template items), `:436` (paper items); `ResumeSections.jsx:108` (`MenuItem`, used at `ResumeEditor.jsx:378-386`).
- [ ] `.v2-hover-bad` (`theme.css:130`, `--bad-soft` bg) — `ResumeEditor.jsx:388` (Delete copy); `ResumeSections.jsx:93` (`RemoveLink`), `:185`, `:237`, `:302`, `:348` (✕ buttons).
- [ ] `.v2-hover-accent` (`theme.css:129`) — `ResumeEditor.jsx:633` (Review ✕); `ResumeSections.jsx:126` (section header), `:213` (experience entry header).
- [ ] `.v2-dashadd` (`theme.css:145-146`) — `ResumeSections.jsx:96` (`DashedAdd`, used at `:189`, `:256`, `:307`, `:328`, `:351`, `:357`, `:372`).
- [ ] `.v2-spin` (`theme.css:225-226`, animation) — `ResumeEditor.jsx:367`.
- [ ] `.v2-scroll` (`theme.css:221-223`, scrollbar only) — `ResumeEditor.jsx:404`, `:423`, `:498`, `:582`, `:635`.
- [ ] Controls with **no hover style**: CTA pill `:366`, "✦ Tailor for a job…" `:397`, "↓ Download PDF" `:441`, "✦ Tailor" `:614`, "✦ Re-tailor"/"Make copy" `:536`, "Decline ↩/Restore change" `:646`, "Done reviewing" `:660`, every ↩ revert (`ResumeSections.jsx:236`, `:269`, `:300`), the persona checkbox label `:583`, all text inputs.

## 2.6 Theme

- [ ] Dark mode: read only in the shell — `V2App.jsx:52` → `data-theme` on `.jn-v2` `V2App.jsx:90` → `theme.css:74`. Neither editor file reads the theme.
- [ ] **Colour literals in `ResumeEditor.jsx` and `ResumeSections.jsx`: none** (grep for `#hex`, `rgb(`, `hsl(` clean). SVG ring uses `stroke="var(--track)"` `:337` and `scoreColor` `:338`.
- [ ] Tokens used that live only in the palette blocks — all present in both light (`theme.css:5-10`) and dark (`:75-80`): `--change-soft`, `--change-bg`, `--bad-soft`, `--track`, `--hover-soft`, `--ring-accent`, `--accent-soft`, `--scrim`, `--edge`, `--text-2`, `--line-soft`, `--surface-2`, `--good`, `--warn`, `--bad`, `--accent-ink`. Shared-scope tokens: `--faint` (`:68`, alias of `--muted`), `--shadow-modal`/`--shadow-menu` (`:27`), fonts (`:62-64`).
- [ ] `textWrap: 'pretty'` at `:508` — CSS property support varies by browser (not a colour issue; noting for visual QA).

## 2.7 Suspicious

`ResumeEditor.jsx`:
- [ ] `:2`, `:71` — `useSearchParams` imported and `setSearchParams` declared, **never used**.
- [ ] `:328` — status copy "autosaves on blur" but persistence is per-keystroke debounced 500 ms (`:246-254`); only the Skills category is blur-saved (`ResumeSections.jsx:295`).
- [ ] `:250` — autosave PATCH failure is `console.error` only; `savedAt` not bumped; **no toast** — silent data loss risk.
- [ ] `:271` — PDF render failure `console.error` only.
- [ ] `:213-215` — score poll resolves on **any** numeric `cv_scores['Tailored']`. Re-scoring a copy that already has a Tailored score makes the first tick (3 s) report "Scored: {old value}" before the new run finishes. Also `scores.base` is captured in the closure at call time (`:220` dep).
- [ ] `:243` — `// eslint-disable-line` on `stage`'s dependency list; `goCover` is omitted from deps.
- [ ] `:229` — delete confirm text mentions "Its tailored copies will be removed too." for bases, but the only Delete control is inside the copy-only menu (`:388`) — the base branch of the message is unreachable. Whether the backend cascades was not verified.
- [ ] `:125` — freeform tailoring (`jobId` empty) never enters `pendingRef`, so no completion toast; the resulting copy is only discoverable from the shelf.
- [ ] `:169` — `baseCopyCount` counts every non-base row with matching `parent_id`, **including archived** — disagrees with the shelf's `copy_count` (see 2.8).
- [ ] `:290` — declined `added` bullet is removed by exact text from **every** experience entry (`d.experience?.forEach`), not just the one it belongs to.
- [ ] `:39-45` — `computeChanges` aligns experience entries and bullets **by index**; a tailoring pass that reorders or inserts a role/bullet mis-labels every subsequent bullet as modified.
- [ ] `:651` — `{added || '(base text restored)'}` is inside `{added && …}` — the fallback string can never render (dead code).
- [ ] `:467` — `RetailorModal` default `baseId = doc.parent_id || 'persona'`; if `/persona` has no `resume_content`, "persona" is selected but not listed, and "✦ Re-tailor" is still enabled (`:481`) → posts `base_resume_id: 'persona'`.
- [ ] `:475` — `const personaCopyable = false` hard-coded; `:480` branch is effectively constant.
- [ ] `:551` — `useState(baseId === 'persona')` is always `false` (`baseId = doc.id`, `:545`).
- [ ] `:311-313` — `pdfDownloadUrl` anchor bypasses the axios `X-API-Key` interceptor; works only via cookie auth.
- [ ] `:378-386` — `MenuItem` hints "c", "e", "a" read as keyboard shortcuts; **no `keydown` handler exists** in the editor.
- [ ] `:327` — no rename control for `doc.name` (task asked for "name rename" — it does not exist).
- [ ] `:395-398` — base résumés have no ⋯ menu / delete / cover letter; **no delete path for a base** in v2.
- [ ] `:112`, `:142` — success toasts with an "Open ↗" action expire in 2.5 s (`Toast.jsx:21`); easy to miss.
- [ ] `:249` — `saveTimer` not cleared on unmount; the deferred PATCH still fires (fine) but `setSaving/setSavedAt` run on an unmounted component.
- [ ] `:444` — no loading indicator on the PDF pane; the previous PDF stays visible while the new one renders (users may read a stale preview as current).
- [ ] `:81`, `:306` — one localStorage key for section-open state across all résumés (and possibly Persona).
- [ ] `:63-67` — comment block documenting a move; harmless. No `TODO`/`FIXME`/`console.log` in the file (only `console.error` at `:250`, `:271`).

`ResumeSections.jsx`:
- [ ] `:6` — header comment says the tailoring props are `baseSummary/baseExp/baseSkills`, but `SectionEditor` (`:145`) takes `baseData` and derives them — stale comment.
- [ ] `:35` — `setField` splits on `.`; a Skills category containing a dot (`skills.${k}`, `:298`) writes to a nested path instead of the key.
- [ ] `:279` — `rename` onto an existing key merges rows silently (later entry wins).
- [ ] `:295` — uncontrolled category input keyed by `k`; renaming remounts the row (cursor/focus lost after blur — acceptable, but note for QA).
- [ ] `:307` — "+ Add skill row" key `Skill {n+1}` can overwrite an existing category of that name with `''`.
- [ ] `:196` — experience open-state is a `Set` of **indices**; removing a role shifts which entry is open.
- [ ] `:241-246` — suggested bullets have no inline keep/discard; only the Review modal (or manual delete of `suggested_bullets` via Done reviewing) resolves them.
- [ ] `:328` — "+ Add education" pushes `{school, location, degree}` without `years` (Years field still works; noting for shape drift).
- [ ] `:43-51` / `:80-88` — the Ctrl/Cmd+B `**bold**` shortcut is duplicated verbatim in `Field` and `BulletText`.
- [ ] No handler defined-but-unattached; all exports used somewhere (`Field`, `BulletText`, `RemoveLink`, `DashedAdd`, `EmptyState`, `MenuHead`, `MenuItem`, `MicroField`, `UPPER`, `cellInput`, `DANGEROUS` are consumed by this file, `ResumeEditor.jsx`, or `Persona.jsx:6`).

## 2.8 Counts that must agree

- [ ] **Score ring** `:340` = `Math.round(GET /jobs/{job_id}.cv_scores['Tailored'])` (`:197`). **Feed chip** (`v2/JobFeed.jsx:24-25`, `bestScore`) = max of **all** numeric `cv_scores` values on the same job. **Shelf chip** (`Resumes.jsx:214`) = `cv_scores[copy.name]` → `['Tailored']` → max (`routes_resumes.py:521-531`). The same copy can show three different numbers.
- [ ] **Delta** `:353` = `Tailored − max(non-Tailored numeric entries)` (`:198-200`) — the "base" here is the best other résumé's score, not necessarily the parent base's.
- [ ] **Success toast "Scored: N (+Δ vs base)"** `:215` uses the same `scores.base` and the freshly polled `sc`.
- [ ] **Base band "N tailored copies"** `:396` = client count over GET `/resumes?is_base=false` where `parent_id === id` (`:169`) — includes rejected/stale copies. Shelf card `copy_count` (`Resumes.jsx:195`) excludes them (`routes_resumes.py:569`); shelf `copy_count + archived_count` should equal the editor's number.
- [ ] **"N reviewable changes" / CTA "Review N changes" / menu hint "{n} applied" / Review-modal footer "All N changes"** — `:361`, `:238`, `:381`, `:659` — all from the same client `changes` array (`:176`). Must agree with each other.
- [ ] **Shelf "fresh" dot** (`Resumes.jsx:178`/`:215`; backend `_fresh` = any `suggested_bullets`, `routes_resumes.py:495-499`) vs **Editor `changes.length > 0`** (`:176`; summary/bullet/skill word-diffs + added + suggested). A copy with modified-but-not-suggested changes shows "N reviewable changes" here and **no** fresh dot on the shelf; after "Done reviewing" both clear (suggested deleted `:295`, declined reverted) — but any change the user *kept* remains a diff vs base, so the editor keeps reporting it as reviewable on every visit while the shelf stops flagging it.
- [ ] **Section "● changed by tailoring"** `:407` and entry ● `ResumeSections.jsx:219` derive from the same `baseData` diff as `changes` but via `bulletMark`/`entryChanged` (`:198-205`), which also fire on `suggested_bullets`; should agree with `changedSections` (`:177-181`).
- [ ] **Tracers line** `:362` "{source_label} {clicks}" from GET `/resumes/{id}/tracer-stats` (`routes_resumes.py:1296-1319`; bot clicks excluded). Any other surface showing tracer clicks (Stats page, classic UI) must use the same endpoint/field.
- [ ] **Tailor modal job score** `:599` (`jobScore`: `cv_scores[doc.name]` → `Tailored` → max) vs Feed chip (max) — differ when the base's own score is not the max.
- [ ] **Tailor modal "✦ exists"** `:600` = any non-base row with `parent_id === base && job_id === job` (includes archived) — compare with the shelf chips under that base (live only).
- [ ] **Section counts "(n)"** `ResumeSections.jsx:130` = `sectionCounts(data)` (`:23-29`) — must match the number of rows rendered inside each section and what the PDF prints.
- [ ] **Summary "N characters"** `ResumeSections.jsx:271` = `data.summary.length`.
- [ ] **Rail "Résumés" count** (`V2App.jsx:59`, bases only) — unchanged by opening a copy; must match shelf `bases.length`.
- [ ] **Review modal "n declined"** `:659` = count of truthy `declined` flags (`:624`).

---

## Endpoint index (unique, both screens)

GET `/resumes/shelf` · GET `/monitor/active` · POST `/resumes` · POST `/resumes/import-pdf` · GET `/resumes` (`?is_base=`) · GET `/resumes/templates` · GET `/resumes/{id}` · PATCH `/resumes/{id}` · DELETE `/resumes/{id}` · GET `/resumes/{id}/pdf` · GET `/resumes/{id}/tracer-stats` · POST `/resumes/{id}/score-check` · POST `/resumes/tailor` · POST `/resumes/copy` · GET `/jobs` · GET `/jobs/{id}` · PATCH `/jobs/{id}` · GET `/cover-letters` (`?job_id=`) · GET `/persona` — **19 endpoints**.

## Silent-failure index

Truly uncaught promises (no `catch`/`try`): **0**.
Caught but with no user-visible feedback: Shelf `Resumes.jsx:49` (shelf load → wrong empty state), `:70` (monitor poll); Editor `:159` (redirect w/o message), `:160`, `:169`, `:171`, `:186`, `:187`, `:192`, `:250` (**autosave**), `:271` (**PDF**), `:116`, `:217`, `:470`, `:471`, `:555`, `:557` — **17 paths**, of which autosave and PDF render are user-impacting.

## Missing empty/error branches (explicit list)

Shelf: shelf-load error state; archived view with zero rows; persona/archived hidden when no bases; null `updated_at` → "edited ". Editor: id-not-found message; templates empty/failed; PDF render failed; autosave failed; tracer stats empty; copy with no job (CTA leads to an error toast); Header empty state; Summary empty state; whole-document empty state; job-fetch-failed vs no-job indistinguishable; base-data fetch failed (diff silently absent); Re-tailor/Tailor modal fetch-failed vs empty share one message. — **17**.
