# Stage 3 — Persona + Stats

Tested: 2026-09-02, bundle `index-Dnrx3n0f.js` (working tree at `438d27a` plus in-flight wave fixes), themes light+dark, viewport 1440×900 plus a 1024×700 narrow pass.
Designs: `v2-testing/design/Persona Ops.dc.html`, `v2-testing/design/Stats Ops.dc.html` — both read in full, including the `<script type="text/x-dc">` block.
Inventory: `v2-testing/inventory/v2-persona-stats.md` (§2.5–2.8 written during this pass, then every box ticked)
v1 references: `frontend/src/components/Persona.jsx`, `frontend/src/components/Stats.jsx` · Backend: `backend/api/routes_persona.py`, `backend/main.py`
Scripts: `ps_1` … `ps_11` — Stats recon / theme+hovers / interactions+triggers / zero-data+hostile-data / Persona recon / autofill round-trip / résumé editors / error paths+hovers / reorder diagnosis / PATCH-body capture / cross-screen
Screenshots (container `/tmp/v2t/shots/`): `stats-light`, `stats-dark`, `stats-sankey`, `stats-empty`, `stats-500`, `stats-long`, `stats-narrow-1024`, `persona-light`, `persona-dark`

**Bundle note.** The served bundle predates two `theme.css` fixes landed elsewhere in this wave (`.v2-hover-accent` colour `!important`, `.v2-menuitem` background `!important`). Hover numbers below are measured against the served bundle; where a source fix already exists I say so rather than logging it again.

---

## Findings

### PERS-01 · P1 · A non-list `qa_bank` white-screens the whole app
**Where** `frontend/src/v2/Persona.jsx:216` — `(p?.qa_bank || []).map(toPair)` — route `/v2/persona`
**Repro** Intercept `GET /api/persona`, return the real payload with `qa_bank` replaced by `{"a":"b"}`.
**Expected + why** Every other malformed node degrades gracefully — `resume_content` served as a bare string still renders all seven section cards without throwing (measured). The backend's `_to_dict` returns `p.qa_bank or []` (`routes_persona.py:34`), so any *truthy* non-list passes straight through, and HANDOVER §"Hostile data" names legacy `qa_bank` shapes from the extension as a live risk.
**Actual** `pageerror: "…|| []).map is not a function"`, `document.body.innerText.length === 0`. The entire v2 shell unmounts, rail included. There is no error boundary anywhere in v2, so the user gets a blank white page with no way out but editing the URL.
**Proposed fix** One line at `:216` — `(Array.isArray(p?.qa_bank) ? p.qa_bank : []).map(toPair)`.
**Status** fixed + verified after rebuild (`Persona.jsx` qa memo accepts list, legacy dict → pairs, anything else → []; dict qa_bank rendered with 0 page errors)

### PERS-02 · P2 · `PATCH /api/persona` silently dropped every order-only write — Skills ▲▼ did nothing
**Where** `backend/api/routes_persona.py:63-64` (was `setattr(p, k, v)` with no `flag_modified`); surfaced by `ResumeSections.jsx:280` (`move`) / `:283` (arrows)
**Repro** No browser needed: `PATCH /api/persona {"resume_content": {…,"skills": {…two keys swapped…}}}` → 200, echoes back the **original** order; a following GET has the original order.
**Expected + why** The route documents itself as *"PATCH replaces a whole node atomically"*. `POST /persona/qa-bank` in the same file (`:95`) already calls `flag_modified` with the comment *"JSON columns need explicit change flagging so SQLAlchemy detects the mutation"* — `update_persona` was missing it. The `personas` columns are `json` (verified in `information_schema`), so key order is meaningful and Postgres preserves it; SQLAlchemy compares JSON by value, and two dicts with the same items are `==` regardless of order, so **no `UPDATE` was ever emitted**.
**Actual** Through the UI: clicking a Skills row's ▼ swaps the rows optimistically (DOM order changes) and the PATCH body carries the correct new order, but the server returns the old order and the change reverts on reload. Contrast `header.contact_items` reorder — a **list**, order-sensitive under `==` — which persists correctly from the same component with the same debounce.
**Proposed fix** `flag_modified(p, k)` inside the update loop.
**Status** fixed + verified (backend). After the restart the PATCH echoes and reads back `['Technical','Certifications','Tools','Languages']`; original order restored afterwards.

### PERS-03 · P2 · The Skills value box is dead for any category containing a dot
**Where** `ResumeSections.jsx:35` (`setField` splits the path on `.`) via `:298` (`setField(\`skills.${k}\`, …)`)
**Repro** Give the persona a category `ZZTEST.Dotted`, open Skills, type into that row's value input.
**Expected + why** Typing should write the value, as it does for every other category (verified against `Certifications`).
**Actual** Measured: after typing `AFTER-TYPING` the input still displays `before` and the server value is unchanged. `setField('skills.ZZTEST.Dotted')` resolves to `d.skills.ZZTEST` → `undefined` → `:36` returns silently. Realistic categories that hit this: `Node.js`, `Web3.0`, `CI/CD.`. Shared with the Résumé editor.
**Proposed fix** Give `SkillsEditor` its own writer using `mutate` instead of the dotted-path `setField`: `onChange={(e) => mutate((d) => { d.skills[k] = e.target.value })}`. Rename/remove already use `mutate` and are unaffected. ~2 lines.
**Status** fixed in source (rebuild pending): `ResumeSections.jsx:283-286` — `SkillsEditor` writes `d.skills[k]` directly through a new `setVal()` (the `↩` tailoring revert too) instead of the dotted-path `setField`, which is no longer passed to this editor. Blast radius is the Skills editor only; `setField` is unchanged for every other section. Same edit as RES-04.

### PERS-04 · P2 · Renaming a skill category onto an existing name silently destroys that category's value
**Where** `ResumeSections.jsx:279` — `rename` rebuilds the object as `ns[k === oldK ? newK : k] = v`
**Repro** Rename `ZZTEST.Dotted` (value `before`) to `Certifications` (a real category with real content) and blur.
**Actual** Measured: keys become `['Certifications','Technical','Tools','Languages']` and `Certifications` now holds `'before'` — the user's real certifications string is gone. No warning, no undo, and it PATCHes 500 ms later.
**Expected + why** Either refuse the rename or merge. Losing real content on a typo is not acceptable for a field the tailoring prompt reads verbatim.
**Proposed fix** Bail when `newK` already exists and differs from `oldK` (reverting the input), or suffix it.
**Status** fixed in source (rebuild pending): `ResumeSections.jsx:287-298` (`rename`), `:313` (`onBlur`) — **refuse**, not merge (a merge still has to discard one of the two values). `rename()` returns false on a collision, a blank name or a `DANGEROUS` key; `onBlur` reverts the uncontrolled input to the old key and a new `onError` prop — plumbed through `SectionEditor` and wired to `pushToast` at `Persona.jsx:277-278` and `ResumeEditor.jsx:409` — raises the `error` toast “… already exists — renaming onto it would erase its values.” Same edit as RES-05.

### PERS-05 · P2 · A failed save is completely invisible
**Where** `Persona.jsx:200` — `catch (e) { console.error(\`persona ${key}\`, e) }`
**Repro** Intercept `PATCH /api/persona` with 500, edit `City`.
**Actual** Measured: the field keeps showing the typed value, `Saved ✓` stays `visibility: hidden`, the server still holds `Frankfurt`, and nothing on the page contains "fail" or "error". `Toast.jsx` is not imported by this screen at all. State was already applied optimistically at `:197`, so screen and server diverge silently until a reload.
**Expected + why** HANDOVER ranks error paths #2 and says the `error` toast kind (`TTL.error = null`, never auto-dismisses) should be *"wired at every failure site, not just the two or three where it was demonstrated"*.
**Proposed fix** Raise an `error` toast in the catch; ideally also mark the node dirty so the header can say "unsaved".
**Status** fixed (rebuild pending) — already landed earlier in this wave: `Toast.jsx` is imported, `ToastStack` is mounted, and `saveNode`'s catch raises an `error` toast carrying the backend detail (`Persona.jsx:206`). No further change in this triage.

### PERS-06 · P2 · Any load failure leaves the screen on `Loading…` forever
**Where** `Persona.jsx:185` (`.catch(() => {})`), `:232` (`if (!p) return … Loading…`)
**Repro** Intercept `GET /api/persona` with (a) 500 `"Persona singleton missing — restart app to re-seed"` — the real backend response at `routes_persona.py:46` — and (b) `200 null`.
**Actual** Both render `Loading…` indefinitely: no retry, no error copy, no toast. The 500 case is the *documented* first-run/reseed failure, and the user is given no hint that restarting the app is the fix.
**Proposed fix** Track an `err` state; render the message plus a Retry that re-issues the GET.
**Status** fixed in source (rebuild pending): the load-failure toast landed earlier in the wave, but the `Loading…` state still stuck — confirmed in source at `Persona.jsx` (`if (!p) return … Loading…`). Added a `loadErr` flag set by the `.catch()` **and** by a `200 null` body; the placeholder now renders “Couldn’t load your persona.” + a **Try again** that re-issues the GET. The toast is kept.

### PERS-07 · P2 · A legacy multi-key `qa_bank` entry loses every key but the first, permanently
**Where** `Persona.jsx:95` (`toPair` takes `Object.keys(e)[0]`), `:217` (`writeQa` always rewrites the whole bank canonically)
**Repro** Serve `qa_bank: [{"ZZTEST k1":"v1","ZZTEST k2":"v2"}, …]`.
**Actual** Measured: the card renders `ZZTEST k1 / v1` only; `k2/v2` appears nowhere. Because *any* edit to *any* entry rewrites the entire bank through `writeQa`, the next keystroke anywhere on the screen persists the lossy version. HANDOVER explicitly flags `{question: answer}` shapes as arriving from the extension.
**Proposed fix** Flat-map legacy entries to one pair per key.
**Status** fixed in source (rebuild pending): `Persona.jsx:93-101`, `:259` — `toPair` became `toPairs`, returning one pair **per key**, and the memo uses `flatMap`. Every key of a legacy multi-key entry now renders and survives the next canonical rewrite.

### PERS-08 · P2 · Navigating away within 500 ms of the last keystroke drops that edit silently
**Where** `Persona.jsx:186` (unmount clears every pending timer), `:201` (500 ms debounce)
**Repro** Type into `Notice period`, wait 120 ms, navigate to `/v2/stats`.
**Actual** Measured: the server value is unchanged. No flush on unmount, no unsaved-changes guard — and the header still says "Saves automatically".
**Proposed fix** Flush pending timers in the cleanup rather than clearing them (fire the PATCH, don't await it).
**Status** fixed in source (rebuild pending): `Persona.jsx:189-204` (`flushPending`), `:214-217` (unmount + `beforeunload`), `:226-239` (`timers.current[key] = {timer, value}`) — the unmount cleanup now **flushes** pending node PATCHes instead of clearing them, and the same flush is bound to `beforeunload`. It uses `fetch(..., {keepalive: true})` with the same cookie + `X-API-Key` as `api.js`, because an axios XHR started during `beforeunload` is aborted with the page; axios stays as the fallback. Fire-and-forget — nothing is left mounted to toast a failure.

### PERS-09 · P3 · Remove ✕ hovers to a red *background*; the design specifies a red *glyph*
**Where** `theme.css:130` (`.v2-hover-bad:hover { background:var(--bad-soft) !important }`) used at `Persona.jsx:320` and `ResumeSections.jsx:185/237/302/348`
**Expected + why** `Persona Ops.dc.html`: the bullet ✕ carries `style-hover="color:#9c3b30"` and the skill × carries `style-hover="color:#9c3b30"` — colour only, no background.
**Actual** Measured: `backgroundColor rgba(0,0,0,0) → rgb(247,236,234)` (`--bad-soft`), `color` unchanged at `rgb(109,104,98)` (`--muted`). The glyph never turns red.
**Status** fixed + verified after rebuild: every remove ✕ (shared editor + Q&A) tints its glyph `--bad` on hover as well as the background (consistent with the Companies ruling)

### PERS-10 · P3 · Two collapsible headers on the same screen wash to different colours, and only one matches the design
**Where** `theme.css:129` (`.v2-hover-accent` → `--surface-2`) on `SectionShell` (RS:126) and the Experience entry header (RS:213); `theme.css:164` (`.v2-clhead` → `--bg`) on the four autofill group headers (P:278)
**Expected + why** The design gives **every** collapsible header the same `style-hover="background:#faf8f3"` — section headers, role headers and group headers alike. `#faf8f3` maps to `--bg`.
**Actual** Measured light: section header → `rgb(246,244,238)` = `--surface-2`; group header → `rgb(252,251,247)` = `--bg`. Side by side in one viewport they read as two different affordances.
**Status** fixed + verified after rebuild: all collapsible headers hover to `--surface-2` (`.v2-clhead` unified; Q&A card keeps its amber)

### PERS-11 · P3 · Experience entry headers are 36.75 px tall, putting five rows on a half pixel
**Where** `ResumeSections.jsx:213`
**Repro** `assert_int_tops(pg, '.v2-hover-accent')`
**Expected + why** HANDOVER: *"Half-pixel rows drop their 1px borders … fix with explicit integer line-heights"* — and the sibling `SectionShell` header (RS:126) already carries `lineHeight: '18px'` for exactly this reason.
**Actual** `{'count': 10, 'fractional': 5, 'samples': [1501.25, 1653.75, 1703.75, 1753.75, 1803.75]}`, identical in light and dark. The 12.5 px title at the inherited 1.5 gives 18.75 px, so the row is 36.75 px and every card below inherits the fraction.
**Proposed fix** Add `lineHeight: '18px'` to the entry header.
**Status** fixed in source (rebuild pending) — `ResumeSections.jsx:213`.

### PERS-12 · P3 · Picker menu-item hover is dead in the served bundle
**Where** `theme.css:149`; items at `Persona.jsx:118` / `:120`
**Actual** Measured against the served bundle: hovering a Picker option changes nothing (`changed=[]`), because each item sets an inline `background` and the class rule had no `!important`. The design specifies `style-hover="background:#f3f0e8"` on exactly these rows.
**Status** fixed + verified: `.v2-menuitem` hover hardened tree-wide

### PERS-13 · P3 · Every destructive control is one unconfirmed click and PATCHes immediately
**Where** `Persona.jsx:320` (remove Q&A answer); `ResumeSections.jsx:185` (contact item), `:237` (bullet), `:249` (**Remove role** — an entire job with all its bullets), `:302` (skill category), `:324`/`:353`/`:369` (education / project / publication)
**Actual** Hit accidentally and then confirmed deliberately: a single click on `Remove role` deleted a 10-bullet role, persisted 500 ms later. No confirmation, no undo, no toast. This is the user's real résumé source pool.
**Expected + why** HANDOVER's standing constraint on destructive operations; `Remove role` alone destroys ~10 authored bullets.
**Status** fixed + verified after rebuild: every destructive control removes immediately and shows a 5 s undo toast that re-inserts the item at its index (shared `useUndoRemove`; measured on a Q&A answer: qa_bank identical after undo)

### PERS-14 · P3 · Garbage `qa_bank` entries become blank editable pairs and are counted as answers
**Where** `Persona.jsx:92-97` (`toPair`), `:301` (count)
**Actual** Serving `qa_bank: [{q:a}, {k1,k2}, null, {}, "not-an-object"]` renders **five** cards — three completely blank — and the header reads `5 answers`. The next edit rewrites all five canonically, so the garbage becomes permanent blank rows.
**Status** fixed + verified after rebuild: non-object / empty / junk `qa_bank` entries are skipped and not counted (5 injected entries → 2 cards)

### PERS-15 · P3 · No keyboard access and no focus styling anywhere on the screen
**Where** every clickable control is a `span`/`div` with `onClick`, no `tabIndex`/`role`/`onKeyDown` (P:108, 116, 118, 120, 136, 278, 297, 320, 325; RS:126, 163, 185, 189, 213, 237, 248, 249, 283, 302, 307, 324, 328, 348, 351, 353, 357, 369, 372). Every `<input>`/`<textarea>` sets `outline: 'none'` with no replacement.
**Actual** Measured on a focused input: `outlineStyle: 'none'`, `boxShadow: 'none'` — focus is completely invisible. No `aria-expanded` on the eleven toggles, no `aria-checked` on the custom checkbox.
**Status** fixed + verified after rebuild (simple): 46 controls are Tab-reachable with roles, `aria-expanded` on 15 headers, Enter/Space activate, accent focus ring

### PERS-16 · P4 · Both column heads are missing the design's right-hand caption
**Where** `Persona.jsx:161-168` — `ColumnHead` renders only title + "what is this?"
**Expected + why** The design gives each column head a third element: `<span style="margin-left:auto;…">the pool tailored résumés draw from</span>` and `…>read by the extension on ATS forms</span>` — the line that explains the two-column split at a glance.
**Actual** Measured: the head has 2 children, not 3.
**Status** decided 2026-09-02: keep

### PERS-17 · P4 · The four autofill group headers are missing the design's subtitle
**Where** `Persona.jsx:281` renders a bare spacer `<span style={{flex:1, minWidth:0}} />` where the design has `{{ g.sub }}`
**Expected + why** Design subtitles: contact *"name, links, current company — writes the contact node"*; demographics *"unset by default — filled only where you choose"*; workauth *"the yes/no answers every ATS asks"*; screening *"relocation, notice, salary — writes preferences + compensation"*. The Q&A card **does** render its subtitle (P:300), so the gap is visible inside the same column.
**Status** decided 2026-09-02: keep

### PERS-18 · P4 · `＋ Add answer` carries a hover class that can never do anything
**Where** `Persona.jsx:325-326` — `className="v2-hover-accent-text"` on a span whose inline `color` is already `var(--accent)`
**Actual** Measured: `changed=[]`, before and after both `rgb(63,107,82)`. The design gives this control no hover at all, so the class is dead weight either way.
**Status** fixed + verified after rebuild: `+ Add answer` is the same dashed add control as the other cards

### PERS-19 · P4 · `+ Add bullet` is muted grey while every other add-control on the screen is accent
**Where** `ResumeSections.jsx:248` — `color: 'var(--muted)'` with `.v2-act`, versus `DashedAdd` (RS:96) at `color: 'var(--accent)'` with `.v2-dashadd`
**Expected + why** Design: `+ Add bullet` is `color:#3f6b52` — the same accent as `+ Add experience`, `+ Add education`, `+ Add skill`.
**Actual** Measured: `+ Add bullet` is `rgb(109,104,98)` before and after hover (`.v2-act` does not touch `color`); the sibling `DashedAdd` is `rgb(63,107,82)` throughout. Two visually different "add" affordances inside one card.
**Status** fixed + verified after rebuild: `+ Add bullet` is accent like every other add control (résumé editor too)

### PERS-20 · P4 · `--edge` used as small text sits under the AA contrast floor
**Where** `Persona.jsx:109` (Picker placeholder `—`), `:282` (`{n} of {N} set`), `:301` (`{n} answers`)
**Actual** Measured light: `rgb(138,130,110)` on `rgb(255,255,255)` ≈ **3.9:1** at 10.5 px — short of the 4.5:1 needed at that size. Dark: `rgb(127,122,102)` on `rgb(40,37,27)` ≈ 4.2:1, also short. The design uses the same `#8a826e`, so this is inherited rather than introduced.
**Status** fixed + verified after rebuild: the three small `--edge` texts are `--muted` (rgb 109,104,98)

### PERS-21 · P4 · Blank Q&A pairs and empty strings are persisted
**Where** `Persona.jsx:325` (`＋ Add answer` pushes `{question:'', answer:''}`), `:208` (only `undefined` deletes a key)
**Actual** Measured: `＋ Add answer` PATCHes a blank pair 500 ms later (`qa_bank` 18 → 19, header `19 answers`) before a character is typed — while the backend's own `POST /persona/qa-bank` rejects blanks with a 400 (`routes_persona.py:84`). Separately, clearing a text field stores `''` rather than deleting the key (verified for `earliest_start`, `referral_source`, `desired_salary`, whose originals were absent and came back as `''`).
**Status** fixed + verified after rebuild: `+ Add answer` no longer persists a blank pair; cleared fields delete the key instead of storing ''

### PERS-22 · P4 · Q&A subtitle is truncated relative to the design
**Where** `Persona.jsx:300` — `reusable screener answers`
**Expected** Design: `reusable screener answers — sent verbatim, worth writing well`. The dropped half is the part that explains why the card is amber.
**Status** decided 2026-09-02: keep the user's subtitle ("reusable screener answers")

### PERS-23 · P4 · "Saves automatically" / "saves on blur" both misdescribe a 500 ms debounce-on-change
**Where** header copy `Persona.jsx:245`; `CLAUDE.md` §Resume + Persona System says *"saves on blur via `PATCH /api/persona`"*
**Actual** Measured: every keystroke re-arms a 500 ms timer per node; blur is irrelevant (the uncontrolled skill Category input at RS:295 is the sole genuine commit-on-blur). Combined with PERS-08 the copy is actively misleading.
**Status** fixed (docs): the screen copy "Saves automatically" was right; CLAUDE.md now says the Persona editor autosaves 500 ms after the last change

---

### STAT-01 · P2 · A refused or failed trigger is indistinguishable from a successful one
**Where** `Stats.jsx:159-164` (`trigger`), buttons at `:439`
**Repro** Route-intercepted the `Run now` POSTs and fulfilled 202 / 409 / 500 in turn (nothing reached the backend — see Scratch data).
**Expected + why** These buttons fire `/scrape/run-all`, `/db/backup`, `/db/cleanup`, `/auto-reject/run`, `/email/check-now`, `/telegram/digest`, `/h1b/refresh`. A 409 is a *routine* outcome per CLAUDE.md §Non-blocking triggers, and HANDOVER records that a `job_cleanup` trigger once deleted 81 real jobs. The user has to be able to tell "started" from "refused" from "blew up".
**Actual** All three statuses give byte-identical UI for a fixed 4 s: button `Running` + spinner, `borderTopColor rgb(226,221,208)`, `color rgb(63,107,82)`, status cell `Running · 0s`, Next-run `now` — then a silent revert to `Run now` / `Scheduled`. The only difference is a `console.error('trigger', …)`. The 4 s window is a bare `setTimeout` in `finally` (`:163`), decoupled from what the job actually did.
**Proposed fix** Toast the outcome (`ok` on 202, `warn` on 409 "already running", `error` otherwise) and clear `triggering` from the response rather than a timer.
**Status** fixed in source (rebuild pending): `Stats.jsx:167-184` — checked the two gaps the wave's error toast left open. 409 was **not** distinguished (any failure produced the same “Could not start …”), and the 4 s revert lived in `finally`, so a refused trigger still read `Running` for 4 s. Now 202 → `progress` toast “{job} started.” plus the 4 s optimistic window; 409 → `error` toast “{job} is already running.” with `triggering` cleared immediately; any other failure → the existing error toast, also cleared immediately.

### STAT-02 · P2 · "Best open score" renders the literal string `-Infinity`
**Where** `Stats.jsx:268`
**Repro** Intercept `/api/jobs` and return one job with `cv_scores: {}`.
**Expected + why** `{}` is truthy so the guard passes, and `Math.max()` of an empty list is `-Infinity`. The shape is real: `routes_jobs.py:232` explicitly treats `cv_scores::text = '{}'` as unscored, so the Feed already knows these rows exist.
**Actual** Measured: the tile reads `BEST OPEN SCORE=-InfinityZZTEST Co`.
**Proposed fix** Build the numeric list first and fall back to `—` when it is empty.
**Status** fixed in source (rebuild pending): `Stats.jsx:189-194`, `:294` — a `bestScore` memo builds the numeric list first and falls back to `—` when it is empty, and the company sub-label is suppressed in that case, so `cv_scores: {}` no longer renders `-InfinityZZTEST Co`.

### STAT-03 · P2 · With every endpoint failing, the screen renders a plausible-looking dashboard
**Where** `Stats.jsx:102` / `:126-127` / `:135` / `:139` — every request `.catch()`es to `null`
**Repro** Intercept all ten endpoints with 500.
**Actual** Measured: header `Stats · No scrape recorded yet`; KPIs `—`, `0`, `—`, `—`, `—`; funnel four rows of `0` with the footnote intact; the 30-day chart drawn as a flat line with real axes; `0 jobs` schedules; `No runs yet.`; `No LLM calls in this window.`. Sixteen console errors, nothing on screen. A user cannot distinguish a dead backend from an empty database — and `New this week` shows `0` where its neighbours show `—`, because the series is always filled client-side (`:171-181`).
**Expected + why** HANDOVER ranks error paths #2 and empty-DB #1 precisely because these two collapse into each other.
**Proposed fix** Track a per-request failure flag and render one header-level "couldn't reach the backend — Retry" banner.
**Status** fixed + verified after rebuild: KPI tiles render “—” on failure; a red banner under the header ("Couldn’t reach the backend for some of these numbers…" + Try again) appears when any core request fails; funnel and 30-day cards show "Unavailable — the request failed"; Try again clears it

### STAT-04 · P3 · The Schedules table overflows its card below ~1100 px
**Where** `Stats.jsx:417-419` / `:424-444` — fixed columns `250 + 132 + 140 + 132 + 110 = 764` plus `0 20px` padding, in a card with no horizontal scroll container
**Repro** 1024×700.
**Actual** Measured: all 7 rows have `scrollWidth 856` against `clientWidth 756`; the document itself does not scroll (`scrollWidth === clientWidth === 1024`), so the `Run now` buttons spill past the card's right border. Run-history and activity rows are fine (their last column is `flex: 1`). Row tops stay integral.
**Proposed fix** Wrap the schedules body in `overflow-x: auto`, or make `Job`/`Job ID` shrinkable.
**Status** fixed + verified after rebuild: the Schedules table shrinks the Job column and hides Job ID / Schedule / Next run / Status progressively (ResizeObserver); no overflow at 1024, only name + Run now at 700

### STAT-05 · P3 · Two of the four funnel bars use different tokens from the design
**Where** `Stats.jsx:202-205`
**Expected + why** Design funnel palette: Saved `#c9c3b4` (`--line-strong`), Applied `#8fae9b` (`--funnel-low`), Interview `#5f8a70` (`--funnel-mid`), Offer `#3f6b52` (`--accent`) — one neutral→accent ramp, the same ramp the score buckets use on the same row of the page.
**Actual** Measured light: Saved `rgb(201,195,180)` ✓, Applied `rgb(58,90,134)` = `--stage-applied` (blue), Interview `rgb(154,91,40)` = `--warn` (orange), Offer `rgb(63,107,82)` ✓. The code comment at `:561-563` says the intent was to share the Applications stage palette.
**Status** fixed + verified after rebuild: Applied `--funnel-low`, Interview `--funnel-mid`, Offer `--accent`, Rejected `--line-strong`

### STAT-06 · P3 · The funnel is upside down, because `Saved` counts jobs and the other three count applications
**Where** `Stats.jsx:199-212`
**Actual** Measured against live data: `Saved 5` → 2 % bar, `Applied 377` → 100 % bar, `Interview 3` → 2 %, `Offer 0` → 0 %. Widths normalise to the widest row (`:207`), so the "funnel" renders as sliver / full bar / sliver / nothing. `Saved` is `stats.saved_jobs` (the live shortlist, 5 today) while `Applied` is every application ever (377). The footnote at `:320` says as much, but the geometry still reads as a funnel.
**Expected + why** The design's example data (26 → 8 → 5 → 1) narrows monotonically, which is what makes the shape legible — and that only holds while the shortlist exceeds the lifetime application count.
**Proposed fix** Drop `Saved` from the funnel, or normalise against `Applied` and label `Saved` as a separate reference row.
**Status** fixed + verified after rebuild: Saved dropped from the funnel; rows Applied → Interview → Offer → Rejected, all applications, normalised against Applied; footnote updated

### STAT-07 · P3 · The `applied` line uses `--warn` where the design *and theme.css's own comment* say `--gold` — and the series is all zeros
**Where** `Stats.jsx:356` (legend), `:553` (`<Line stroke="var(--warn)">`), `:548` (right axis ticks)
**Expected + why** The design draws the applied polyline in `#c9a35a` with a solid `#c9a35a` legend swatch, and `theme.css:16-18` states outright *"`--gold` doubles as the 'applied' line on the 30-day chart"*. `--warn` is `#9a5b28` in light — a brown that reads as an error colour, not a series colour.
**Actual** Measured: stroke resolves to `rgb(154,91,40)` light / `rgb(212,160,106)` dark; the legend swatch is additionally a dashed `repeating-linear-gradient` the design does not have. Separately, `/stats/timeline` returns `applied: 0` for **every** day over the last 30 *and* the last 90 — so the second line, the second Y axis and half the legend currently render nothing. The endpoint counts jobs whose *current* status is `applied`, grouped by *discovery* date, which is structurally near-always zero.
**Status** fixed in source: applied line + solid legend swatch + right-axis ticks use `--stage-applied`

### STAT-08 · P3 · Activity `Type` menu-item hover is dead in the served bundle
**Where** `theme.css:149`; items at `Stats.jsx:468`
**Actual** Measured: hovering `Scrape` in the open menu gives `changed=[]` (`rgba(0,0,0,0)` / `rgb(87,83,74)` before and after). The design specifies `style-hover="background:#f3f0e8"` on these rows.
**Status** fixed + verified: `.v2-menuitem` hover hardened tree-wide

### STAT-09 · P3 · The funnel silently falls back to the status snapshot while still claiming "ever reached"
**Where** `Stats.jsx:204-205` (`reached.interview || st.interview || 0`), footnote `:320`
**Repro** Intercept `/stats/sankey` with only self-loops and backward hops.
**Actual** Measured: `Interview` drops from 3 to 0 with no indicator, while the footnote still reads *"the rest count every application that ever reached that stage"*. This is exactly the bug HANDOVER records as previously fixed (*"Stats funnel read `application_statuses`, a snapshot, and showed Interview as 0 of 377"*) — the fallback quietly reintroduces it whenever transition data is missing.
**Note** `reached` (`:194-198`) sums over **all** flows including the backward `interview → applied` hop and the `applied → applied` self-loop, unlike `sankey` (`:217`) which filters them. Live data: `reached.applied` = 373 = 372 + 1 backward hop.
**Status** fixed in source: a row that falls back to the status snapshot shows a `snapshot` note (with explanatory title) and the footnote says so; after the STAT-19 backfill no row currently falls back

### STAT-10 · P4 · Score bucket `61-80` uses `--funnel-mid` where the design uses `--funnel-low`
**Where** `Stats.jsx:15`
**Actual** Measured `rgb(95,138,112)` = `--funnel-mid` (`#5f8a70`); design `#8fae9b` = `--funnel-low`. The other four buckets match exactly (`--line`, `--sand`, `--gold`, `--accent`), so the ramp is one step too dark in the middle. Bucket range keys are hyphens on both sides (`main.py:1215`), so the lookup itself is sound.
**Status** decided 2026-09-02: keep `--funnel-mid`

### STAT-11 · P4 · The funnel rows lost the design's per-row percentage, and the card lost its subtitle
**Where** `Stats.jsx:315` (`flex: '0 0 40px'`, count only), `:286` (no sibling note)
**Expected** Design: `flex:0 0 56px` rendering `{{ f.count }}<span style="color:#6d6862"> {{ f.pct }}</span>` — e.g. `8 31%` — plus the card subtitle `where the 8 applications stand`.
**Status** decided 2026-09-02: keep

### STAT-12 · P4 · `Avg / call` renders `$0.0000` for a genuinely non-zero average
**Where** `Stats.jsx:23` (`money`), `:379`
**Actual** Measured at `all`: Spend `$0.019`, Calls `4,573`, Avg / call `$0.0000` (true value ≈ $4.05e-6). `money` bottoms out at four decimals, so any sub-$0.0001 average reads as zero.
**Proposed fix** Fall back to significant digits or `<$0.0001` below the four-decimal floor.
**Status** decided 2026-09-02: keep

### STAT-13 · P4 · A long-running job reads `Running · 3671s`
**Where** `Stats.jsx:434` uses raw seconds; `dur()` (`:37`) already formats `m s` and is used two cards down at `:501`
**Actual** Confirmed with an intercepted `elapsed_seconds: 3671`.
**Status** fixed in source: running duration formatted with `dur()` (m s)

### STAT-14 · P4 · The Schedules subtitle states the timezone twice and can contradict itself
**Where** `Stats.jsx:414` — `next runs in {TZ_SHORT}, schedules as configured (UTC)`
**Actual** Measured in the container (TZ=UTC): `7 jobs · next runs in UTC, schedules as configured (UTC) · intervals and crons live in Settings`. Also: "Settings" is plain text, not a link (the design does not link it either).
**Status** decided 2026-09-02: correct as is — crons are configured in UTC, next runs shown in the viewer's zone; the doubled 'UTC' only appears when the viewer's zone is UTC

### STAT-15 · P4 · The 30-day series keys on UTC dates while the backend groups on local dates
**Where** `Stats.jsx:176` (`d.toISOString().slice(0, 10)`) versus `main.py:1145` (`cast(Job.discovered_at, Date)`)
**Actual** Not observable in the container (TZ=UTC) but latent: for a viewer west of UTC all 30 buckets shift by a day, which also shifts `New this week` and `peak`. Related: `when()` (`:34`) formats in `TZ` while `dayLabel()` (`:25`) passes no `timeZone`.
**Status** fixed in source: the 30-day series is bucketed by local calendar date; `dayLabel()` and `when()` share the zone

### STAT-16 · P4 · Nothing on the screen is a link, including the one the rail advertises
**Where** no `<a>`, `Link` or `navigate` anywhere in `Stats.jsx`
**Actual** The rail's pipeline-pulse tooltip says `Click → Stats · Run history` (`V2App.jsx:84-85`) and `:142` navigates to `/v2/stats`, but Run history is the last card on a ~2400 px page — the click lands at the top, below the fold. Other dead ends: `{n} sources need attention` (`:247`, live now — Oracle) does not go to Companies; `Best open score` does not open the job (the Feed's `?job=` deep-link exists); the score buckets do not filter the Feed by `min_score`.
**Status** fixed + verified after rebuild: the rail's health line goes to `/v2/stats#runs` and the Run history card scrolls into view

### STAT-17 · P4 · Hover, column and label deviations from the design (grouped)
**Where** `Stats.jsx:292` / `:373` / `:460` / `:417-419` / `:441`
**Actual** Measured: (a) the Funnel/Flow pills, the LLM period pills and the `Type ▾` button all carry `.v2-bdc`, and the design gives none of the three a `style-hover` — and on the *active* pill it is a visible no-op (`changed=[]`) because border and colour are already accent; (b) the design has no Funnel/Flow toggle at all (its script comment says the funnel *"replaces the source's bar/Sankey toggle"*); (c) the code adds a `Job ID` column (132 px) and widens `Job` to 250 px where the design has `Job 190 / Schedule 150 / Next run 130`; (d) the running button reads `Running` where the design says `Running…`, in `--accent` where the design uses `#8a826e`.
**Everything else measured matches the design exactly:** header `92 px` / `22px 30px 16px`, h1 `30px`, period pill `23 px` / `0 9px` / `10.5px`, run button `25 px` / `0 11px`, run-history columns `118/140/90/100/76/flex`, card radius `10px`, `Schedules` heading `17px` Newsreader, funnel track `--surface-2`, status dot `--funnel-low`, `how priced?` underline `--line-strong`, inactive tab `--edge`, running-button border `--line`, and `Run now` hover → border+colour accent.
**Status** (a) and (d) fixed + verified after rebuild: no hover on the Funnel/Flow, period and Type ▾ pills; the running Run button reads "Running…" in `--edge`. (b), (c), (e) decided keep

### STAT-18 · P4 · Both logs are silently truncated
**Where** `Stats.jsx:127` (`limit: 30`), `:134` (`limit: 50`)
**Actual** Measured: 30 run rows and exactly 50 activity rows against a log holding far more. No pagination, no "load more", no row click, no link to `/monitor/run/{id}`, and nothing signals the cap. The activity empty state (`No activity matches.`) is the same copy whether the log is empty or the filter excluded everything.
**Status** fixed + verified after rebuild (+ backend `offset` on `/monitor/history` and `/activity-log`, restarted): Load more on both logs (32 → 62 runs measured); activity empty state distinguishes filtered vs empty

### STAT-19 · P4 · Sankey and funnel disagree on how many applications there are
**Where** `Stats.jsx:222` (Sankey nodes) versus `:203` (funnel `Applied`)
**Actual** Measured live: the Sankey labels read `new (372) → applied (372) → rejected (348)` with `interview (3)`, while the funnel row says `Applied 377` and the KPI says `Applications 377`. Five applications carry no `new → applied` transition, so two views of the same quantity differ by 5 with no explanation.
**Everything else cross-checks exactly:** `Total jobs 18,943` = `/jobs?limit=1 → total 18943`; `Saved 5` = `/jobs?status=saved → total 5` = funnel `Saved`; `Applications 377` = `/applications → total 377` = `/stats.total_applications`; bucket counts `313+1385+904+975+94 = 3671` = `scored_count`; LLM `Calls 969` = Σ`by_purpose.calls`; `7 jobs` = `len(/scheduler/jobs)`; header spend = card spend at all four periods.
**Status** fixed + verified (data): 5 applications whose history started at applied→rejected got a backfilled `→ applied` edge (source `backfill`); Sankey new→applied 377 = funnel = KPI. 105 applied→applied self-loops remain (offered to strip)

### STAT-20 · P4 · KPI tile internals differ from the design
**Where** `Stats.jsx:270-273`
**Actual** Measured: tile `82 px` tall, `padding 14px 20px 10px`, `gap 11px`, value `line-height 30px`; the design is `padding:14px 20px`, `gap:2px`, `line-height:1.1`, and places the sub inside the serif span after a plain space rather than at `marginLeft: 7`.
**Status** decided 2026-09-02: keep

### STAT-21 · P4 · Border tokens used as fills and as text lose their contrast in dark
**Where** `Stats.jsx:14` (`'0-20': 'var(--line)'` as a bar fill), `:401` (`--edge` as the Cache `—`), `:454` (`--edge` as the inactive tab label)
**Actual** Measured dark: the `0-20` bar is `rgb(62,59,50)` on card `rgb(40,37,27)` — a 22-point luminance step for a bar representing 313 jobs. In light it is `rgb(226,221,208)` on white, which reads fine. `--line` is a border token doing duty as a fill.
**Status** fixed + verified after rebuild: `0-20` bucket fills `--line-strong`; Cache — and the inactive tab label are `--muted`

### STAT-22 · P4 · No keyboard access on Stats either
**Where** every control is a `span`/`div` with `onClick`, no `tabIndex`/`role`/`onKeyDown` (`Stats.jsx:251, 292, 373, 439, 454, 460, 465, 468`); no `aria-expanded` on the Type dropdown
**Actual** The only focusable element is the company `<input>` (`:479`), which sets `outline: 'none'` with no replacement — focus is invisible. `Run now` in particular is an unlabelled `span` firing an irreversible pipeline job.
**Status** fixed + verified after rebuild (simple): 17 Tab-reachable controls incl. `Run now` with an aria-label naming the job, `aria-expanded` on Type ▾, `aria-pressed` on pills

---

## Fixed in source
- `backend/api/routes_persona.py:63-69` — `flag_modified(p, k)` in `update_persona`'s loop, so an order-only node write is actually persisted (PERS-02). **Verified live after the restart.**
- `frontend/src/v2/ResumeSections.jsx:213` — explicit `lineHeight: '18px'` on the Experience entry header, removing five fractional row tops (PERS-11). **Rebuild pending.**

## Verified working (no finding)
- **Persona autofill round-trip, all 31 fields + the decline flag:** 16 text fields (11 contact, 4 preferences, 1 compensation), 9 enum pickers, 6 bool pickers, `— not answered` (deletes the key), and the checkbox — each read → edited through the UI → PATCH body asserted → server read-back asserted → original restored → restoration asserted. Node routing correct in every case, one debounce timer per node, `Saved ✓` fires on success.
- `preferences.preferred_locations` — the key with no control — survived every write to `preferences` (the spread at `Persona.jsx:207` works as documented).
- Counters agree: header `27 of 31`; groups `complete` / `complete` / `4 of 5 set` / `4 of 7 set`, computed independently from the API payload; clearing `age_range` moved them to `26 of 31` and `7 of 8 set` in the same render.
- Q&A bank: add (persists), edit question, edit answer (both rewritten canonically), remove, count pluralisation, `18 answers` = 18 cards = `len(qa_bank)`; `BulletText` auto-grow measured at 19 / 247 / 19 / 190 px.
- Résumé editors: header name; contact-item reorder ▲▼ (persists); add/remove contact item; the stub-input rule (2 stubs for 2 non-`mailto:` URLs); summary + live character counter; experience company/title/location/date/description; bullet edit/add/remove; section `(n)` counts; skills value, rename, add, remove; education/projects/publications add + field + remove; and the empty states carrying Persona's override note.
- `resume_content` served as a bare string renders all seven sections and does not throw on typing.
- localStorage `jobnavigator_v2_persona_sections` / `_groups` persist across reload; corrupt values fall back to the documented defaults with no error.
- Both screens: console clean on load in light and dark (`{console: 0, pageerrors: 0, http: 0, reqfailed: 0}`); tab titles `Persona · JobNavigator` / `Stats · JobNavigator`; every colour resolves from tokens in both themes, including inside Recharts SVG attributes (stroke resolves to `rgb(141,187,159)` / `rgb(212,160,106)` in dark).
- `assert_int_tops` clean on: Persona group headers (4), autofill field grid (11), Q&A cards (18); Stats schedule rows (7), 34 px rows (31), 26 px rows (8), activity rows (51), and schedule rows at 1024 px.
- Stats interactions: Refresh (fires all 11 GETs, spinner, guarded by `refreshing`); Funnel↔Flow toggle; all four period pills (`days=1|7|30|0`, figures and header text move together); tab switching; the Type dropdown (open / backdrop-close / select / `Type · 1` accent state / filter persists across a tab switch / correct `type=` param / only `sm-keyword` badges after selecting Scrape); the debounced company search (`limit=50&type=scrape&company=…`, 300 ms, one request per settle) and its `No activity matches.` empty state.
- Stats zero-data and hostile-data: empty-DB payloads across all ten endpoints (no crash, no console error); 200-character job name / job id / schedule / activity message / company / run error (all ellipsis + `title`, no row overflow at 1440, no document overflow); unknown activity type falls back to the `sm-extension` badge; `trigger_url: null` renders `—`; `Last sweep failed 1d ago`; `pending` → warn dot; an LLM fetch failure *is* distinguishable from an empty window (`Spend —` vs `$0.00`).
- The one `<rect fill="black">` visible in the Recharts DOM is the LineChart's `<defs><clipPath>` rect — inside `<defs>`, never painted. Not a defect.

## Couldn't test
- **Rebuild-dependent:** the `ResumeSections.jsx` line-height fix and the two `theme.css` `!important` hover fixes are source-only; the served bundle still has the old behaviour, so PERS-11, PERS-12 and STAT-08 need a re-measure after the wave rebuild.
- **Non-UTC timezone (STAT-15):** the container runs UTC and the harness's `context()` exposes no `timezone_id`, so the UTC-vs-local date-key drift is reasoned from code, not measured.
- **Scrollbar-gutter behaviour** on the LLM cost table (`.v2-gutter` / `.v2-gutter-head`) and `.v2-scroll` styling on both screens: headless Linux uses overlay scrollbars (width 0) — documented harness trap.
- **Real trigger execution:** every `Run now` POST was intercepted by design; the 202 path was verified as a UI state, not as an actual scheduler launch. Live trigger behaviour is Stage 5.
- **A genuinely running scheduler job:** none ran during the pass, so `Running · {n}s` with real `elapsed_seconds`, the 3 s fast-poll cadence and the `now` Next-run cell were exercised through interception and the `triggering` path only.
- **Sankey link hover / Recharts tooltip content:** both tooltips render and are token-styled, but their content was not asserted.
- **Persona tailoring-diff affordances** (`↩` revert on summary/bullet/skill, the `added` tag, the `●` unreviewed marker): Persona deliberately passes no `baseData`, and the live record carries no `suggested_bullets`, so these never render here.
- **Legacy-typed bool/enum values** (a `work_auth` bool holding `'yes'`, an enum outside `options`) and **concurrent-edit / stale-write**: not injected this pass.

## Scratch data
- Created: nothing persisted. All Persona edits were single-field, reversible and restored inside the same script; every script carries a `finally` that PATCHes a full-node backup and asserts equality. One temporary skill category `ZZTEST.Dotted` and one blank Q&A pair existed briefly to exercise PERS-03 / PERS-04 / PERS-21 and were removed by the same restore.
- Final integrity check: all seven persona nodes identical to the backup taken at the start (`contact`, `work_auth`, `demographics`, `compensation`, `preferences`, `qa_bank`, `resume_content`); skills order back to `['Certifications','Technical','Tools','Languages']`; `qa_bank` back to 18 entries; the string `ZZTEST` appears nowhere in the record.
- No global trigger fired: all nine trigger POSTs on Stats were intercepted and fulfilled in the browser; the backend received zero of them (asserted per click).
- **Scratch rows remaining: 0.**

---

## Summary

**Inventory boxes — 314 total.** Persona: 118 verified · 26 failed · 9 untestable. Stats: 120 verified · 34 failed · 7 untestable. Every failed box carries its finding id inline in `v2-testing/inventory/v2-persona-stats.md`; §2.5–2.8 (Stats hovers, theme, suspicious, counts) were written during this pass to complete the cut-off catalogue.

**Findings: 45** — P1 ×1, P2 ×10, P3 ×13, P4 ×21.

| | Persona | Stats |
|---|---|---|
| **P1** | PERS-01 | — |
| **P2** | PERS-02 … 08 (7) | STAT-01, 02, 03 |
| **P3** | PERS-09 … 15 (7) | STAT-04 … 09 (6) |
| **P4** | PERS-16 … 23 (8) | STAT-10 … 22 (13) |

**Fixes applied: 2** — one backend (`flag_modified`, verified live after the restart), one frontend (integer line-height, rebuild pending).

**The three that matter most.** PERS-01 is the only P1: a single malformed `qa_bank` value white-screens the entire app, and HANDOVER already names that shape as one the extension can produce. PERS-02 was a genuine backend defect — a visible control that did nothing while the UI cheerfully pretended otherwise — now fixed and verified. STAT-01 is the one with real-world consequences: seven buttons that fire irreversible pipeline jobs give byte-identical feedback whether the job started, was refused as a duplicate, or 500'd.

**The pattern underneath.** Neither screen imports `Toast.jsx`. Between them that accounts for PERS-05, PERS-06, STAT-01 and STAT-03 — four separate P2s with one root cause: every failure on both screens is a `console.error` at best, and both screens are optimistic, so the UI actively asserts success it has not got. One decision about giving these two screens a toast surface closes four findings.

**A second pattern worth a single decision.** Three of the P2s on Persona (PERS-03 dotted-category writes, PERS-04 rename collision, PERS-02 reorder) all live in `SkillsEditor` — the one editor whose model is a plain object keyed by user-supplied strings. It is the least defensible data shape in the résumé schema and it is shared with `/v2/resumes/:id`.

---

## P2 triage (2026-09-02)

Source-only pass over the open P2s. No rebuild, no backend restart — every fix below is **rebuild pending**.
Files touched: `frontend/src/v2/Persona.jsx`, `Stats.jsx`, `ResumeSections.jsx`.
Brace/paren/bracket/backtick balance of all three checked against `git show HEAD:<path>` — unchanged.

| id | action | note |
|---|---|---|
| PERS-03 | **fixed** | Same edit as RES-04: `SkillsEditor` gets its own `setVal(k, v)` writing `d.skills[k]` through `mutate`, so a category containing a `.` writes normally. `DANGEROUS` guard kept. |
| PERS-04 | **fixed** | Same edit as RES-05: `rename()` **refuses** the collision (chosen over merge — a merge still loses one of the two values) and returns false, `onBlur` reverts the uncontrolled input, and a new `onError` prop raises an `error` toast. Wired from both callers. |
| PERS-05 | **status corrected** | Already fixed earlier in this wave: `Toast.jsx` is imported, `ToastStack` mounted, and `saveNode`'s catch raises an `error` toast with the backend detail (`Persona.jsx:206`). No further code change. |
| PERS-06 | **fixed** | The load-failure toast alone left the screen on `Loading…` forever — confirmed in source (`if (!p) return … Loading…`). Added a `loadErr` state set by both the `.catch()` **and** a `200 null` body; the placeholder now renders "Couldn't load your persona." + a **Try again** that re-issues the GET. The toast stays. |
| PERS-07 | **fixed** | `toPair` → `toPairs`, returning one pair **per key**, and the memo uses `flatMap`. A legacy multi-key entry now renders every key instead of silently dropping all but the first on the next canonical rewrite. |
| PERS-08 | **fixed** | Pending debounced saves are flushed instead of cleared. `timers.current[key]` now holds `{timer, value}`; a `flushPending()` fires each pending node PATCH and is called from the unmount cleanup **and** from a `beforeunload` listener. `fetch(..., {keepalive: true})` with the same cookie + `X-API-Key` as `api.js`, because an axios XHR started in `beforeunload` is aborted with the page (axios remains the fallback). |
| STAT-01 | **fixed** | 409 was **not** distinguished (any failure gave the same "Could not start …" toast) and the 4 s revert ran in `finally`, so a refused trigger still showed `Running` for 4 s. Now: 202 → `progress` toast "{job} started." + the 4 s optimistic window; 409 → `error` toast "{job} is already running." and `triggering` cleared **immediately**; anything else → the existing error toast, also cleared immediately. |
| STAT-02 | **fixed** | `Math.max()` on an empty list is guarded: a `bestScore` memo builds the numeric list first and falls back to `—`; the company sub-label is suppressed when there is no score, so `cv_scores: {}` no longer renders `-InfinityZZTEST Co`. |
| STAT-03 | **partly fixed** | Checked: the one error toast fired, but stale/plausible numbers still rendered, because `loadCore` did `if (s) setStats(s)` — a failed request left the previous value on screen. Now `setStats/setTimeline/setScores` are assigned unconditionally, so a failure clears the node and `int(null)` renders `—`; `New this week` is additionally gated on `timeline` so it shows `—` rather than the client-filled `0`. **Still open (deferred):** the funnel bars, the 30-day chart axes and the schedules card still draw an empty-but-plausible shape on total failure — that needs the header-level "couldn't reach the backend" banner from the proposed fix, which is a layout decision rather than a contained one. |
