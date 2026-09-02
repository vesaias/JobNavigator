# v2 inventory — Persona (`/v2/persona`) and Stats (`/v2/stats`)

Catalogue for the verification pass. Nothing here was run or fixed — every line is read from source. Line numbers are from the working tree at commit `438d27a` (branch `v2-redesign`).

Files:
- `frontend/src/v2/Persona.jsx` (335 lines) — abbreviated **P:**
- `frontend/src/v2/ResumeSections.jsx` (375 lines) — the résumé editors Persona reuses — **RS:**
- `frontend/src/v2/Stats.jsx` (578 lines) — **S:**
- `frontend/src/v2/V2App.jsx` (162 lines) shell — **V2App:**
- `frontend/src/v2/Toast.jsx` (82 lines) — **Toast:** (neither screen imports it)
- `frontend/src/api.js` (29 lines) — axios, `baseURL: '/api'`, `X-API-Key` from `localStorage.jobnavigator_api_key` (api.js:11), 401 → `jn:unauthorized` event (api.js:22-24)
- `frontend/src/v2/theme.css` (229 lines) — tokens + hover classes — **T:**
- backend: `backend/api/routes_persona.py`, `backend/main.py` (stats/monitor/scheduler endpoints), `backend/api/routes_jobs.py`, `backend/api/routes_applications.py`, `backend/api/routes_companies.py`

---

# 1. Persona — `/v2/persona`

## 1.1 Routes & params

- [x] Route: `<Route path="persona" element={<V2Persona />} />` nested under `<Route path="/v2" element={<V2App />}>` — `frontend/src/App.jsx:164` (parent :153). Import `V2Persona from './v2/Persona'` App.jsx:27.
- [x] Browser-tab title `Persona` — `frontend/src/useTitle.js:15` (`['/v2/persona', 'Persona']`).
- [x] Rail entry: group "You", `{ to: '/v2/persona', label: 'Persona', Icon: Fingerprint }` — V2App:29. No count badge (no `countKey`).
- [x] Query params / deep-links handled: **none**. Persona.jsx imports no `useSearchParams`/`useLocation`/`useNavigate`; `?section=`/`?group=` are NOT supported.
- [x] localStorage `jobnavigator_v2_persona_sections` — read P:174 (JSON array → `Set`, default `new Set(['Experience'])` P:175); written P:226 inside `toggler` (called via `toggleSection` P:229). Holds the open résumé section names (`Header|Summary|Experience|Skills|Education|Projects|Publications`).
- [x] localStorage `jobnavigator_v2_persona_groups` — read P:178 (default `new Set(['contact','qa'])` P:179); written P:226 via `toggleGroup` P:230. Holds open autofill group ids (`contact|demographics|workauth|screening|qa`).
- [x] Both reads are wrapped in `try/catch` and validated with `Array.isArray` (P:174, P:178); a corrupt value silently falls back to the default. Both writes wrapped in `try/catch` (P:226).
- [x] Shell-level keys (apply to both screens): `jobnavigator_v2_rail` read V2App:48, written V2App:55 (`'expanded'|'collapsed'`); `jobnavigator_dark_mode` read V2App:52, written V2App:54 (`'true'|'false'`); `jobnavigator_api_key` read api.js:11 (never written by v2).
- [x] Experience-entry open/closed state (`new Set([0])`, RS:196) is component state only — NOT persisted, resets to "first entry open" on every mount/navigation.

## 1.2 Data loads

- [!] `GET /api/persona` on mount — P:185 (`useEffect([], …)`). Success → `setP(data)`. **Failure: `.catch(() => {})`** — `p` stays `null` → the screen shows `Loading…` (P:232) forever. No retry, no error copy, no toast.  — **PERS-06**
  - Backend `routes_persona.py:40-47`: 500 `"Persona singleton missing — restart app to re-seed"` if row id=1 absent (seeded by `seed_persona`, `backend/seed.py:868`). Response shape `_to_dict` routes_persona.py:25-37: `{id, contact{}, work_auth{}, demographics{}, compensation{}, preferences{}, resume_content{}, qa_bank[], created_at, updated_at}` (null nodes coerced to `{}` / `[]`).
- [!] `PATCH /api/persona` body `{ [node]: wholeNodeValue }` — P:200, fired from `saveNode` P:196-202 after a **500 ms debounce, one timer per node** (`timers.current[key]`, P:198-199). Trigger: every keystroke / click on any control (all controls call `write`→`saveNode` or `mutate`→`saveNode` or `writeQa`→`saveNode`). This is **debounce-on-change, not save-on-blur** (CLAUDE.md says "saves on blur" — mismatch).  — **PERS-05**
  - Success → `flash()` P:189-193 → `saved=true` for 1800 ms → `Saved ✓` span visible (P:248). **No toast.**
  - Failure → `console.error(\`persona ${key}\`, e)` P:200 only. **No toast, no UI error, no rollback** — local state was already updated optimistically at P:197, so the screen shows the edit while the server never received it. Nothing marks the node dirty.
  - Backend `routes_persona.py:50-70`: 400 on unknown top-level key; 500 if row missing; replaces each node atomically (`setattr`), returns the full record (return value is discarded by the frontend at P:200).
- [!] Pending timers and the flash timer are cleared on unmount (P:186) — **navigating away within 500 ms of the last edit drops that edit silently** (timer cleared before the PATCH fires).  — **PERS-08**
- [x] Polling: **none**. No refetch on focus/visibility. No `/monitor/active` use.
- [x] Nothing else is fetched: no `/settings`, no `/resumes`, no `/autofill/*`. `POST /api/persona/qa-bank` (routes_persona.py:73-99) is NOT used by this screen — the Q&A bank is edited only through `PATCH /persona {qa_bank}`.

## 1.3 Interactive elements

Every control is a `<span>`/`<div>` with `onClick` (no `<button>`, no `tabIndex`, no `role`) except the native `<input>`/`<textarea>` fields — none of the click controls are keyboard-reachable.

### Header (P:238-249)
- [x] `Saved ✓` indicator — P:248. Not interactive; `visibility` toggled by `saved`. Only success signal on the screen.
- [x] Subtitle `Saves automatically · autofill {filled} of {ANSWERABLE} set` — P:245. `filled` P:219-222 counts `isSet()` (P:86: not `undefined`/`null`/`''`) across all non-`uncounted` GROUPS fields; `ANSWERABLE` = 31 (P:84: 11 contact + 8 demographics + 5 work_auth + 7 screening).
- [x] `what is this?` help text ×2 — `ColumnHead` P:161-168 (`title={help}`, `cursor: help`, dotted underline P:165). Instances: "Résumé content" P:254-255, "Autofill content" P:268-269. Hover-only tooltip, no click.

### Left column — Résumé content (P:253-264)
All seven sections render `SectionShell` (RS:123-141) + `SectionEditor` (RS:145-156) with `pageHint={false}` and `emptyNote="Tailored résumés draw from whatever you add here."` (P:259-260). Every edit goes `setField`/`mutate` (RS:32-39: JSON deep-clone of `resume`, write one path) → `onData` → `saveNode('resume_content', next)` P:214 → `PATCH /persona {resume_content}`. `resume` is `p.resume_content` or the `EMPTY` skeleton (P:213, RS:16) when the node is `{}`/missing — the first edit therefore writes the whole skeleton (`header, summary, experience, skills, education, projects, publications`).

- [x] Section header toggle ×7 (`Header`, `Summary`, `Experience`, `Skills`, `Education`, `Projects`, `Publications`) — RS:126 `onClick={onToggle}` → P:258 `toggleSection(name)` → state + localStorage. Shows `(count)` from `sectionCounts` (RS:23-29; Header/Summary have no count → `undefined` → hidden RS:130). Class `v2-hover-accent`. No API.

**Header section** (`HeaderEditor` RS:158-193)
- [x] `Full name` input — RS:170, `setField('header.name', v)`.
- [x] Contact item ▲ / ▼ reorder — RS:163 (`move(i, ±1)` RS:160, swaps in `header.contact_items`). Class `v2-navlink`.
- [x] Contact item `Display text` input — RS:182, `setField(\`header.contact_items.${i}.text\`)`.
- [x] Contact item `URL (optional)` input — RS:183, `setField(…url)`.
- [x] Contact item `id` stub input — RS:184, only rendered when `url` set and not `mailto:` (RS:178); `setField(…stub)`; tooltip "Short stub for the tracer link id (e.g. l, w, gh)".
- [x] Contact item ✕ remove — RS:185, `mutate(d => d.header.contact_items.splice(i,1))`, class `v2-hover-bad`, title "Remove".
- [x] `+ Add contact item` — RS:189 (`DashedAdd` RS:95-97), pushes `{text:'', url:''}`.

**Summary** (`SummaryEditor` RS:261-274)
- [x] Summary `BulletText` textarea — RS:268, `setField('summary', v)`; Ctrl/Cmd+B wraps selection in `**` (RS:80-88).
- [x] `{n} characters` counter — RS:271 (the "long summaries" hint is suppressed by `pageHint=false`).
- [~] ↩ revert — RS:269: only when `baseSummary != null`; Persona never passes `baseData` → **never rendered here**.  — *untestable: requires baseSummary; Persona never passes it*

**Experience** (`ExperienceEditor` RS:194-259)
- [x] Entry header toggle — RS:213 `toggle(i)` (local `open` Set RS:196/206), class `v2-hover-accent`. Shows title (`'Untitled role'` fallback RS:215), company, date, `{n} bullet(s)`.
- [x] `Company` / `Title` / `Location` / `Date` fields — RS:224-227 (`Field` RS:42-61; Date is `mono`, placeholder `Jan 2022 – Present`), each `setField(\`experience.${i}.<key>\`)`.
- [x] `Description` field — RS:229, placeholder "Optional role description".
- [x] Bullet `BulletText` — RS:235, `setBullet(i, bi, v)` (RS:197 → `mutate`).
- [x] Bullet ✕ — RS:237, `mutate(d => d.experience[i].bullets.splice(bi,1))`, `v2-hover-bad`.
- [x] `+ Add bullet` — RS:248, pushes `''`; class `v2-act` (different from the `DashedAdd` used elsewhere).
- [x] `Remove role` — RS:249 (`RemoveLink` RS:92-94, `v2-hover-bad`), `mutate(d => d.experience.splice(i,1))`.
- [x] `+ Add experience` — RS:256 (`DashedAdd big`), pushes `{company,title,location,date,description:'',bullets:[]}`.
- [~] `suggested_bullets` rows — RS:241-247 read-only display with "suggested" tag if the data carries them (no control).  — *untestable: live persona carries no suggested_bullets*
- [~] ↩ revert on bullet — RS:236 only with `baseExp` → never in Persona. `●` unreviewed marker RS:219 only with `baseExp` **or** `suggested_bullets.length > 0` (RS:205) → CAN appear in Persona if `resume_content` contains `suggested_bullets`.  — *untestable: requires baseExp; Persona never passes it*

**Skills** (`SkillsEditor` RS:277-310)
- [!] ▲ / ▼ reorder — RS:283 (`move(k, ±1)` RS:280 rebuilds the object from entries), `v2-navlink`.  — **PERS-02**
- [!] `Category` input — RS:295: **uncontrolled** (`defaultValue={k}`), commits on `onBlur` via `rename(k, newValue)` RS:279 (no-op if unchanged or blank). Renaming onto an existing category **overwrites** that category's value (RS:279 `ns[k === oldK ? newK : k] = v`).  — **PERS-04**
- [!] Skill values input — RS:298, `setField(\`skills.${k}\`, v)`.  — **PERS-03**
- [x] ✕ remove — RS:302, `mutate(d => delete d.skills[k])`, `v2-hover-bad`.
- [x] `+ Add skill row` — RS:307, adds key `Skill {n+1}` with `''`.
- [~] `added` tag / ↩ revert — RS:299-300 only with `baseSkills` → never in Persona.  — *untestable: requires baseSkills; Persona never passes it*

**Education** (`EducationEditor` RS:311-331)
- [x] `School` / `Location` / `Degree` / `Years` — RS:317-322 (`MicroField` RS:114-119; Years `mono`, placeholder `2015 – 2019`), `setField(\`education.${i}.<key>\`)`.
- [x] `Remove` — RS:324 (`RemoveLink` default label).
- [x] `+ Add education` — RS:328, pushes `{school,location,degree}` (no `years` key until typed).

**Projects** (`ProjectsEditor` RS:332-360)
- [x] `Name` / `URL` / `Description` — RS:338-341, `setField(\`projects.${i}.<key>\`)`.
- [x] Project bullet `BulletText` — RS:347, `mutate(d => d.projects[i].bullets[bi] = v)`.
- [x] Project bullet ✕ — RS:348, `v2-hover-bad`.
- [x] `+ Add bullet` — RS:351 (`DashedAdd`).
- [x] `Remove project` — RS:353.
- [x] `+ Add project` — RS:357, pushes `{name,description,url,bullets:[]}`.

**Publications** (`PublicationsEditor` RS:361-375)
- [x] `Title` / `Description` — RS:367-368, `setField(\`publications.${i}.<key>\`)`.
- [x] `Remove` — RS:369.
- [x] `+ Add publication` — RS:372, pushes `{title,description}`.

### Right column — Autofill content (P:267-330)
Field table `GROUPS` P:39-83 (`[node, key, label, kind, opts]`). Each `AutofillField` (P:130-159) calls `write(node, fkey, value)` P:206-211 → spreads the live node, `undefined` deletes the key, else sets it → `saveNode(node, next)` → `PATCH /persona {node}`.

- [x] Group header toggle ×4 — P:278 `toggleGroup(id)` (`contact`, `demographics`, `workauth`, `screening`), class `v2-clhead`. Right-hand status P:282: `complete` (accent) when every counted field `isSet`, else `{n} of {N} set` (edge colour).

**contact** (`Contact / basics`, 11 text fields P:41-51): `first_name`, `last_name`, `email`, `phone`, `city`, `state`, `country`, `current_company`, `linkedin`, `github`, `portfolio` (wide).
- [x] Each: `<input>` P:148 `onChange → write('contact', key, e.target.value)`. Clearing a field stores `''` (not deleted — only `undefined` deletes, P:208). No validation, no `type="email"`/`tel`/`url`, no `maxLength`. Every keystroke re-arms the 500 ms timer.

**demographics** (`Demographics · EEO`, P:53-66)
- [x] `Gender` Picker — P:54, options `GENDER` P:25.
- [x] `Race / ethnicity` Picker — P:55, `RACE` P:26-28.
- [x] `Hispanic or Latino?` Picker — P:56, `YESNO` P:30 (stores `'yes'|'no'` strings).
- [x] `Veteran status` Picker — P:57, `VETERAN` P:29.
- [x] `Disability status` Picker — P:58, `YESNO`.
- [x] `Age range` Picker — P:59, `AGE` P:31.
- [x] `Transgender?` Picker — P:60, `TRANS` P:32.
- [x] `Sexual orientation` Picker — P:61, `ORIENT` P:33-34.
- [x] `Prefer not to answer demographic questions — autofill picks "decline" where the form allows it` checkbox — P:62-65 (`kind:'check'`, `uncounted`, wide); P:136 `onClick → write('demographics','decline_demographics', !on)`. Custom 15px box P:137 (✓ glyph), no native `<input type=checkbox>`.

`Picker` (P:103-128): box P:108 (`v2-act v2-ctl`, border accent while open) toggles `open`; full-screen backdrop P:116 closes; menu P:117 (`v2-scroll`, maxHeight 260, maxWidth 280, `zIndex 31`); `— not answered` item P:118 → `onChange(undefined)` (deletes key); option items P:119-122 → `onChange(v)`. Value label via `labelFor` P:87 — falls back to the raw stored value if it is not in `options`.

**workauth** (`Work authorization`, P:67-73)
- [x] `Authorized to work in the US?` bool Picker — P:68 (`work_auth.authorized_us`).
- [x] `Require sponsorship now?` — P:69 (`requires_sponsorship_now`).
- [x] `Require sponsorship in the future?` — P:70 (`requires_sponsorship_future`).
- [x] `Are you over 18?` — P:71 (`over_18`).
- [x] `Work authorization type` enum Picker (wide) — P:72, `WORK_AUTH_TYPE` P:35-36.
- Bool mapping P:152-153: displays `yes` only when `val === true`, `no` only when `val === false`; writes `true`/`false`/`undefined`.

**screening** (`Screening defaults`, P:74-82)
- [x] `Willing to relocate?` bool — P:75 (`preferences.willing_to_relocate`).
- [x] `Willing to work remote?` bool — P:76 (`preferences.willing_remote`).
- [x] `Notice period` text — P:77 (`preferences.notice_period`).
- [x] `Earliest start date` text — P:78 (`preferences.earliest_start`) — free text, no date picker.
- [x] `Referral source` text — P:79 (`preferences.referral_source`).
- [x] `How did you hear about us?` text — P:80 (`preferences.how_did_you_hear`).
- [x] `Desired salary` text (wide) — P:81 (`compensation.desired_salary`) — free text, no number parsing.
- Writes to `preferences` spread the whole node (P:207) so unrendered keys like `preferred_locations` survive (comment P:17-20, P:204-205).

**Q&A bank** (amber card, P:296-329)
- [x] Header toggle — P:297 `toggleGroup('qa')`, class `v2-qahead`; count `{qa.length} answer(s)` P:301.
- [x] Question `BulletText` (bold) — P:312, placeholder "Question as the form asks it…", `onChange → writeQa(map …question)`.
- [x] Answer `BulletText` — P:316, placeholder "Your reusable answer…", `writeQa(map …answer)`.
- [x] ✕ `Remove answer` — P:320, `writeQa(filter)`, `v2-hover-bad`. **No confirmation.**
- [x] `＋ Add answer` — P:325, `writeQa([...qa, {question:'', answer:''}])`, `v2-hover-accent-text`. Adds a blank pair and immediately PATCHes it (after debounce) — blank pairs are persisted.
- `writeQa` P:217 always writes the canonical `[{question, answer}]` list → the first edit of any entry rewrites **every** legacy-shape entry to canonical (P:89-91 comment). `qa` derived via `toPair` P:92-97 (memoised on `p`, P:216).
- Save-on-blur / explicit save / import / export / "reset" / "copy from résumé": **none exist** on this screen.

## 1.4 States rendered

Branches that exist:
- [x] Loading — P:232 `if (!p) return … Loading…` (centered, `var(--muted)`, 13px). This is also the **permanent** state when `GET /persona` fails or returns 500 (P:185 swallows) — there is no distinguishable error state.
- [x] `resume_content` missing / `{}` — P:213 falls back to `EMPTY` so every section renders its editor; counts all 0 (RS:23-29).
- [x] Empty Experience / Skills / Education / Projects / Publications — `EmptyState` RS:100-105: `No {what} yet` + note `Tailored résumés draw from whatever you add here.` (P:260). Rendered at RS:255, 306, 327, 356, 365. Header and Summary have **no** empty state (always show inputs).
- [x] Experience entry with no title — `'Untitled role'` RS:215.
- [x] Q&A bank empty — P:324 `No saved answers yet — the extension can add them as you apply.` (still followed by `＋ Add answer`).
- [x] Q&A count pluralisation — P:301 `1 answer` / `n answers`.
- [x] Group progress — P:282 `complete` vs `{n} of {N} set`; header P:245 `autofill {filled} of 31 set`.
- [x] Picker unset — placeholder `—` in `var(--edge)` P:109-110; menu marks `— not answered` as selected P:118.
- [!] Legacy `qa_bank` shapes — `toPair` P:92-97 accepts canonical `{question, answer}`, single-key `{"<q>": "<a>"}` (first key only — a multi-key map loses all but its first key, P:95), non-object / null → blank pair, `{}` → blank pair. Non-string legacy answers are `String()`-coerced (P:96).  — **PERS-07 + PERS-14**
- [x] Saved flash — P:248 (1.8 s).
- [x] Long strings: field labels ellipsis + `title` P:99/P:145; Picker value ellipsis P:109; Picker menu scrolls at 260px and caps at 280px wide P:117; Q&A bank subtitle ellipsis P:300; group titles `nowrap` P:280 (no ellipsis — a long title would overflow); header subtitle ellipsis P:244; `BulletText` auto-grows to content (RS:69-79, `ResizeObserver`) so long Q&A answers and bullets wrap fully; Experience header title/company ellipsis RS:215-216; contact `<input>`s scroll natively. No `maxLength` anywhere.

Branches that do NOT exist:
- [!] **Persona row missing entirely** (backend 500 at routes_persona.py:46) — no branch; shows `Loading…` forever. `POST /persona/qa-bank` would auto-create the row (routes_persona.py:88-90) but this screen never calls it.  — **PERS-06**
- [!] **Network / 401 / 5xx on load** — no error copy, no retry button (401 only fires the global `jn:unauthorized` event, api.js:23).  — **PERS-06**
- [!] **PATCH failure** — no toast, no "unsaved changes" marker, no rollback (P:200 `console.error` only). A 400 from an unknown node key (routes_persona.py:57-59) is likewise invisible.  — **PERS-05**
- [!] **`qa_bank` not an array** (e.g. legacy dict) — `(p?.qa_bank || []).map` P:216 throws → React error boundary (none in v2) → white screen. Backend `_to_dict` returns `p.qa_bank or []` so only a non-list truthy JSON value triggers it.  — **PERS-01**
- [x] **`resume_content` not an object** (e.g. a string) — `Object.keys(p.resume_content).length` P:213 on a non-empty string → truthy → `resume` becomes the string → `sectionCounts` reads `.experience` of a string → 0s; `mutate` then JSON-clones the string and `fn(d)` throws on property write. No guard.
- [~] **Bool field holding a legacy string** (`'yes'`/`'no'` instead of `true`/`false`) — displays `—` (P:152) yet counts as set (P:86) → "complete" with a visibly unanswered picker.  — *untestable: no such value in the live record; not injected*
- [~] **Enum field holding a value outside `options`** — shows the raw value (P:87), still counted.  — *untestable: not injected this pass*
- [~] **Concurrent edit / stale write** — `write` spreads the render-time `p[node]` (P:207); no version/etag; last PATCH wins.  — *untestable: needs two simultaneous clients*
- [x] **Unmount with a pending debounce** — P:186 clears timers → edit dropped; no "leaving with unsaved changes" guard.
- [x] **Zero-width / empty-string persistence** — clearing a text field stores `''` rather than deleting; no branch distinguishes `''` from unset except `isSet`.
- [x] No skeleton, no per-section loading, no "last saved at" timestamp.

## 1.5 Hover styles

All hover is CSS-class based (inline styles cannot `:hover`, T:123). No `onMouseEnter`/`onMouseLeave` in Persona.jsx or ResumeSections.jsx.

- [x] `.v2-act:hover` (T:147: accent border + `--hover-soft` bg, `!important`) — Picker box P:108; `+ Add bullet` (experience) RS:248.
- [x] `.v2-ctl` (T:160: `line-height:1` only — **not** a hover class) — Picker box P:108.
- [!] `.v2-menuitem:hover` (T:148: `--surface-2` bg) — Picker items P:118, P:120.  — **PERS-12**
- [x] `.v2-clhead:hover` (T:163: `--bg`) — the four autofill group headers P:278.
- [x] `.v2-qahead:hover` (T:165: `--amber-hover`) — Q&A bank header P:297.
- [!] `.v2-hover-bad:hover` (T:130: `--bad-soft` bg `!important`) — Q&A ✕ P:320; `RemoveLink` RS:93 (Remove role/project/education/publication); contact ✕ RS:185; bullet ✕ RS:237, RS:348; skill ✕ RS:302. Note: the class changes **background** only — the ✕ glyph stays `var(--faint)` (no red text).  — **PERS-09**
- [!] `.v2-hover-accent-text:hover` (T:173: accent text) — `＋ Add answer` P:325.  — **PERS-18**
- [!] `.v2-hover-accent:hover` (T:129: `--surface-2` bg + `--text`) — `SectionShell` header RS:126; Experience entry header RS:213.  — **PERS-10**
- [x] `.v2-dashadd:hover` (T:146: accent border + `--hover-soft` + accent text) — every `DashedAdd` RS:96 (add contact item / skill row / education / project / publication / project bullet / experience).
- [x] `.v2-navlink:hover` (T:134: `--surface-2` bg + `--text`) — ▲▼ reorder arrows RS:163, RS:283.
- [~] `.v2-scroll` scrollbar styling (T:221-223) — both columns P:256, P:270; Picker menu P:117.  — *untestable: headless Linux overlay scrollbars are 0px wide*
- [x] State-driven (not hover): Picker border turns accent while open P:108; checkbox fill P:137; group status colour P:282.
- [x] `cursor: help` + dotted underline on `what is this?` P:165 (tooltip only).
- [!] Rows with **no** hover treatment: Q&A entry cards P:306, education/project/publication cards RS:315/336/366, autofill text inputs P:147-150 (no focus ring either — `outline: none` P:149, RS:20, RS:52, RS:90, RS:117, RS:295, RS:298). **Focus is invisible on every text field.**  — **PERS-15 (focus invisible)**

## 1.6 Theme

- [x] Dark mode is read once in the shell: `localStorage.getItem('jobnavigator_dark_mode') === 'true'` V2App:52; applied as `data-theme={dark ? 'dark' : 'light'}` on the `.jn-v2` root V2App:90; `theme.css` swaps tokens under `.jn-v2[data-theme="dark"]` T:74. Persona.jsx never inspects the theme.
- [x] Every colour in Persona.jsx and ResumeSections.jsx is a `var(--…)` token. Checked programmatically: every token referenced by P/RS/S exists in T (light block T:4-73 and dark block T:74+). **Colour literals (hex/rgb/hsl) in P or RS: none.**
- [x] Persona-specific tokens: `--amber-bg`, `--amber-line`, `--amber-line-soft`, `--amber-hover` (T:16) — used P:296, P:304, P:306, T:165.
- [!] Token used off-purpose: `var(--edge)` (a border token, `#8a826e` light) is used as **text** colour for the Picker placeholder P:109, the group "n of N set" P:282, and the Q&A count P:301 — verify contrast in dark mode (`--edge` dark value at T:75+).  — **PERS-20**
- [x] Custom checkbox uses `var(--accent)` fill + `var(--accent-ink)` glyph P:137.
- [x] Recharts: not used on this screen.

## 1.7 Suspicious

- [!] **Silent save failure** — P:200 `catch (e) { console.error(…) }`: optimistic state already applied (P:197), no toast/rollback. The only `console.error` in the file.  — **PERS-05**
- [!] **Permanent `Loading…` on load failure** — P:185 `.catch(() => {})`.  — **PERS-06**
- [!] **Edits dropped on navigation** — P:186 clears every pending debounce timer on unmount instead of flushing.  — **PERS-08**
- [!] **`setField` path bug for dotted skill categories** — RS:35 splits the path on `.`; `setField(\`skills.${k}\`)` RS:298 with a category like `Node.js` or `CI/CD.` resolves to `skills.Node.js` → `o = d.skills.Node` is `undefined` → RS:36 returns silently. **Typing in the value box of such a category does nothing** (ResumeEditor shares the bug). Rename/remove still work (they use `mutate`).  — **PERS-03**
- [!] **Skill rename collision** — RS:279 renaming a category to an existing name silently overwrites the other row's value; rename with surrounding whitespace is accepted (`newK.trim()` only guards blank).  — **PERS-04**
- [x] **Uncontrolled category input** — RS:295 `defaultValue`; after `move(k, ±1)` the `key={k}` is unchanged so it keeps its DOM value — fine — but an in-progress (unblurred) rename is lost if another mutation re-renders first.
- [x] **Bool/legacy-string mismatch** — P:152 vs P:86 (see 1.4): counted as set, shown as unset.
- [x] **`{}` empty object `resume_content` triggers full-skeleton write** — P:213/RS:33: the first keystroke PATCHes `header/summary/experience/skills/education/projects/publications` in one go; harmless but the backend node grows from `{}` to a 7-key skeleton.
- [!] **Doc mismatch** — header copy P:245 "Saves automatically" and CLAUDE.md "saves on blur" vs actual 500 ms debounce on change (P:201).  — **PERS-23**
- [x] **Experience open-state by index** — RS:196 `new Set([0])`; removing entry 0 leaves index 0 "open" so the next entry pops open; adding an entry appends closed (never auto-opens).
- [!] **Q&A blank pairs persisted** — P:325 pushes `{question:'', answer:''}` and it is PATCHed as-is; the backend `POST /qa-bank` rejects blanks (routes_persona.py:84-85) but `PATCH` does not.  — **PERS-21**
- [~] **`suggested_bullets` marker leaks into Persona** — RS:205 `entryChanged` is true when an entry carries `suggested_bullets`, so the amber `●` "Contains unreviewed tailoring changes" (RS:219) can render on the Persona even though no tailoring exists there.  — *untestable: live persona carries no suggested_bullets*
- [x] **`write` recreated every render** — P:206-211 depends on `p`; every `AutofillField` re-renders on any keystroke anywhere (perf only).
- [x] **Index keys** — Q&A entries `key={i}` P:305; contact items RS:180; experience RS:212; education RS:315; projects RS:336; publications RS:366. Deleting a middle row re-maps DOM nodes; `BulletText`'s `ResizeObserver`/height cache (RS:69-79) is re-fitted via `useLayoutEffect([value])` so no visual bug expected, but worth a delete-middle-row check.
- [!] **No keyboard access** — every clickable control is a `span`/`div` without `tabIndex`/`role`/`onKeyDown` (P:108, 116, 118, 120, 136, 278, 297, 320, 325; RS:126, 163, 185, 189, 213, 237, 248, 249, 283, 302, 307, 324, 328, 348, 351, 353, 357, 369, 372). No `aria-expanded` on toggles, no `aria-checked` on the decline checkbox.  — **PERS-15**
- [!] **No focus styles** — `outline: none` on every input (see 1.5).  — **PERS-15**
- [x] Exports in RS not used by Persona (used by ResumeEditor, so not dead): `Field.flex`, `MenuHead` RS:106, `MenuItem` RS:107, `UPPER`, `cellInput`, `DANGEROUS`. `SectionEditor`'s `baseData` prop is never passed from Persona (by design, RS:143-144).
- [x] `TODO`/`FIXME`/`console.log`/`debugger`: **none** in P or RS.
- [x] Handlers defined but never attached: **none** (all `useCallback`s — `flash`, `saveNode`, `write`, `toggleSection`, `toggleGroup` — are used).
- [x] Props referenced but never passed: `AutofillField.opts` is `undefined` for plain text fields (P:41-50 have 4 elements) — guarded with `opts?.wide` P:135/144, but `opts.text` P:138 and `opts.options` P:155 are unguarded (fine because `check`/`enum` rows always supply opts).
- [x] Toast.jsx is **not imported** — the screen has no toast surface at all.

## 1.8 Counts that must agree (Persona)

- [x] Header `autofill {filled} of 31 set` P:245 — sum of the four group counters P:274 (`contact 0-11`, `demographics 0-8`, `workauth 0-5`, `screening 0-7`). Both computed with the same `isSet` over `p[node][key]`; they must add up.
- [x] `Q&A bank … {qa.length} answer(s)` P:301 — equals the number of entry cards rendered P:305 and equals `len(persona.qa_bank)` from `GET /persona` (routes_persona.py:34). The extension's `POST /api/persona/qa-bank` returns `{count}` (routes_persona.py:99) — after a reload this count must match.
- [x] Section counts `(n)` RS:130 — `experience.length`, `Object.keys(skills).length`, `education.length`, `projects.length`, `publications.length` (RS:23-29) vs rows rendered in each editor.
- [x] Experience header `{n} bullet(s)` RS:218 vs bullet rows RS:230.
- [x] Cross-screen: other v2 screens gate a "Persona" option on `Object.keys(persona.resume_content).length > 0` — `ResumeEditor.jsx:471`, `JobFeed.jsx:473` (`personaAvailable`), `CoverLetters.jsx:192`, `CoverLetterEditor.jsx:233`, `Companies.jsx:113/223`. After adding the first résumé item here, those screens should offer "Persona"; after clearing everything they will NOT hide it (the node stays a non-empty skeleton — see 1.7).
- [x] Rail: no badge for Persona (V2App:29 has no `countKey`).

---

# 2. Stats — `/v2/stats`

## 2.1 Routes & params

- [x] Route: `<Route path="stats" element={<V2Stats />} />` under `/v2` — `frontend/src/App.jsx:165`. Tab title `Stats` — `useTitle.js:16`.
- [x] Rail entry: group "You", `{ to: '/v2/stats', label: 'Stats', Icon: ChartLine }` V2App:30 — no count badge.
- [x] Second entry point: the rail's pipeline-pulse line `onClick={() => navigate('/v2/stats')}` V2App:142. Its tooltip (V2App:84-85) says `Click → Stats · Run history`, but Stats has **no anchor/scroll target** — the click lands at the top of the page; the Run history card is the last card (S:451) and is below the fold.
- [x] Query params / deep-links handled: **none** (`?tab=`, `?period=`, `?job=` are not read). `tab` (S:87), `flowView` (S:88), `period` (S:83), `actType`/`actQuery` (S:91-92) are plain state, reset on every mount.
- [x] localStorage read/written by Stats.jsx: **none**. Only the shell keys apply (`jobnavigator_v2_rail` V2App:48/55, `jobnavigator_dark_mode` V2App:52/54, `jobnavigator_api_key` api.js:11).
- [~] Timezone: `TZ` = `Intl.DateTimeFormat().resolvedOptions().timeZone` S:27 (fallback `'UTC'`), `TZ_SHORT` S:28-31; used by `when()` S:32-36 for every timestamp; shown in the Schedules subtitle S:414.  — *untestable: container runs UTC; harness context() exposes no timezone_id*

## 2.2 Data loads

All requests go through `api` (axios, `baseURL /api`). **Every request on this screen swallows its error** — there is no error branch anywhere (see 2.4).

`loadCore` (S:101-122) — on mount (S:138) and on Refresh (S:153). Seven parallel GETs via `Promise.all`, each wrapped `.catch(() => null)` (S:102):
- [x] `GET /stats` — S:106 → `{total_jobs, new_jobs, saved_jobs, total_applications, application_statuses{status:count}}` (main.py:1333-1359). Feeds KPIs, funnel, `inPlay`.
- [x] `GET /stats/timeline?days=30` — S:107 → `[{date, total, new, saved, applied, skipped, filtered}]` (main.py:1119-1147; days with no discoveries are omitted — filled client-side S:171-181).
- [x] `GET /stats/score-distribution?detail=true` — S:108 → `{buckets:[{range,count}×5], scored_count, avg, tailored_count, tailored_avg}` (main.py:1183-1240).
- [x] `GET /jobs?status=new,saved&sort_by=score&limit=1` — S:109 → `{total, jobs:[…]}` (routes_jobs.py:120-156; `sort_by=score` orders by `best_cv_score desc nullslast` :124). Only `jobs[0]` is used (S:119-120) → "Best open score" tile.
- [x] `GET /stats/sankey` — S:110 → `[{source, target, value}]` (main.py:1243-1261; `from` null → `'new'`).
- [x] `GET /monitor/history?limit=1&job_type=scrape_all` — S:111 → `[run]` (main.py:984-1011) → header "Last sweep …".
- [x] `GET /health/entities` — S:112 → `{companies[], searches[], count}` (main.py:1150-1180; window=3 consecutive bad scrapes) → `failing` count only (reasons unused).

`loadLive` (S:124-131) — on mount (S:138), on every poll tick, on Refresh (S:153), and after a successful trigger (S:162). Both `.catch(() => null)`:
- [x] `GET /scheduler/jobs` — S:126 → `[{id, name, schedule, next_run, pending, trigger_url, running:{run_id, elapsed_seconds}|null}]` (main.py:776-885). Includes 7 core jobs (`scrape_all, email_check, daily_digest, h1b_refresh, db_backup, job_cleanup, auto_reject` :783-791) **plus** one `search_{id}` row per active search with `run_interval_minutes > 0` (:838-856, `trigger_url /searches/{id}/run`) and one `company_{id}` row per active company with `scrape_interval_minutes` set (:858-881, `trigger_url /scrape/company/{id}`). Sets `runningRef` (S:129) = any row with `running`.
- [x] `GET /monitor/history?limit=30` — S:127 → run history rows.

`loadActivity` (S:133-136) — debounced 300 ms (S:141) on mount and whenever `actType` or `actQuery` changes:
- [x] `GET /activity-log?limit=50[&type=<actType>][&company=<trimmed query>]` — S:134 → `[{id, type, message, company, details, created_at}]` (main.py:1038-1074; `company` is ILIKE substring). `.catch(() => {})`.

LLM costs:
- [x] `GET /stats/llm-costs?days=<period>` — S:139, on mount and whenever `period` changes (1/7/30/0; `0` → all-time, main.py:1274). → `{window_days, total_calls, total_cost_usd, by_purpose:[{purpose, provider, model, calls, cost_usd, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cache_involving, cache_hits, cache_hit_ratio}]}` (main.py:1266-1324). `.catch(() => setCosts(null))`.
- [x] Refresh also refetches llm-costs — S:155 with `.catch(() => {})` (stale value kept on failure, unlike S:139 which nulls it).

Polling (S:144-148):
- [~] `loadLive` only. First tick 3000 ms after mount; then `setTimeout` chain at **3000 ms while `runningRef.current`** (any scheduler job reports `running`) **else 10000 ms**. Cleared on unmount (S:147). Core stats, activity and costs are **never** polled — only the Refresh control (S:150-157) reloads them. No `visibilitychange` guard — polling continues in background tabs.  — *untestable: 3s fast cadence needs a genuinely running job; none ran*

Triggers:
- [!] `POST {job.trigger_url}` — S:162 (`trigger(job)` S:159-164): returns early if no `trigger_url`; adds `job.id` to `triggering`; on success calls `loadLive()`; on failure `console.error('trigger', e)` only; `finally` removes the id after a fixed **4000 ms** regardless of outcome (S:163). URLs (relative to `/api`): `/scrape/run-all`, `/email/check-now`, `/telegram/digest`, `/h1b/refresh`, `/db/backup`, `/db/cleanup`, `/auto-reject/run`, `/searches/{id}/run`, `/scrape/company/{id}`. Backend returns 202 + `run_id`, 409 on duplicate (CLAUDE.md "Non-blocking triggers").  — **STAT-01**
- [x] `loading` (S:96) is set `false` once in `loadCore().finally` (S:138) and never `true` again — Refresh never shows the full-page loader.

## 2.3 Interactive elements

Again: every control is a `span`/`div` with `onClick` (no `<button>`, no `tabIndex`) except the Company `<input>` (S:478).

### Header (S:237-257)
- [x] `↻ Refresh` — S:251-256, `onClick={refresh}` (S:150-157). Guarded by `refreshing` (S:151). Calls: the 7 `loadCore` GETs + 2 `loadLive` GETs + `/activity-log` + `/stats/llm-costs`. Shows `v2-spin` spinner while pending (S:253). **No toast** on completion or failure. Classes `v2-hover-accent-text v2-ctl`.
- [x] Header subtitle (S:243-249) — not interactive: `Last sweep [failed ]{ago}` / `No scrape recorded yet`; ` · {n} source(s) need attention` in `var(--warn)` (S:247, only when `failing > 0`); ` · {money} on LLM calls in {period}d|all time` (S:248, only when `costs.total_cost_usd != null`). The "sources need attention" text is **not a link** to Companies/Searches.

### KPI strip (S:262-277) — five tiles, none interactive, each with a `title` hint (S:270)
- [x] `Total jobs` — `int(stats.total_jobs)` S:264; hint "Everything ever scraped or captured, minus cleanup".
- [x] `New this week` — `weekly.now` S:265 (sum of `total` over the last 7 filled series days S:182-185); sub `±{now-prev} vs last` **only when `weekly.prev` is truthy** (prev week 0 → no delta shown); `+` prefix coloured accent (S:273).
- [x] `Saved` — `stats.saved_jobs` S:266; hint "In your feed shortlist".
- [x] `Applications` — `stats.total_applications` S:267; sub `{inPlay} in play` (S:168 = total − rejected − ghosted − withdrawn, floored at 0); hint explains.
- [!] `Best open score` — S:268: `Math.round(Math.max(...numeric cv_scores values))` of the first job from `/jobs?status=new,saved&sort_by=score&limit=1`; sub = `best.company`; `—` when no job or no `cv_scores`. Hint "Highest-scoring posting you haven't applied to". **Not a link** to the job (`?job=` deep-link exists on the Feed but is not used here).  — **STAT-02**

### Application funnel card (S:284-325, fixed height 230)
- [x] `Funnel` / `Flow` toggle pills — S:290-293, `setFlowView('bar'|'sankey')`, classes `v2-bdc v2-ctl`. **Rendered only when `sankey` is non-null** (S:288) — with no forward transition data the toggle is absent and only the bar funnel shows.
- [x] Sankey (`flowView==='sankey'`) — S:297-305: Recharts `<Sankey>` (v2.15, package.json:18) with `data={sankey}` (S:216-224: only forward hops per `RANK` S:215, self-loops and backward hops dropped, `value > 0`), `nodePadding 18`, `nodeWidth 10`, right margin 112 for labels, link stroke `var(--stage-applied)` @ 0.22, custom `node={<SankeyNode />}` (S:569-578: rect fill from `STAGE_FILL` S:564-568, label `name (value)`), `<Tooltip>` S:302 (hover only).
- [!] Bar funnel (default) — S:307-323: four rows from `funnel` S:199-212: `Saved` (`stats.saved_jobs`, `--line-strong`), `Applied` (`total_applications`, `--stage-applied`), `Interview` (`reached.interview || st.interview`, `--warn`), `Offer` (`reached.offer || st.offer`, `--good`). Width = % of the widest row, min 2 % when non-zero (S:210). Count in mono right column S:315. Not interactive.  — **STAT-05 + STAT-06**
- [!] Funnel footnote — S:319-322: "Saved is your live shortlist; the rest count every application that ever reached that stage" + `applied → interview {conv} · interview → offer {conv}` (`conv` S:213: `—` when denominator 0).  — **STAT-11**

### Score distribution card (S:327-347)
- [x] Subtitle `{scored_count} scored jobs · best résumé per job` S:330; `avg {avg}` S:333 only when `avg != null`; `tailored {tailored_avg}` S:334 only when non-null, with `title` tooltip naming `tailored_count`, `cursor: help`.
- [!] Five bucket bars — S:339-345: plain `div`s (not Recharts), height `max(2, count/maxBucket*96)` px, colour `BUCKET_COLOR[range]` S:13-16 (`0-20 --line`, `21-40 --sand`, `41-60 --gold`, `61-80 --funnel-mid`, `81-100 --accent`, fallback `--accent`), count label above, range below, `title="{count} jobs scored {range}"` S:340. Not clickable — **no link to the Feed with `min_score`**.  — **STAT-10**

### New jobs · last 30 days card (S:352-363 + `Spark` S:538-559)
- [!] Legend swatches `new` (accent, solid) / `applied` (`--warn`, dashed via `repeating-linear-gradient`) — S:356-360, static.  — **STAT-07**
- [x] Recharts `<LineChart>` S:544-554: `data` = 30 filled days (S:171-181) with `label` from `dayLabel` S:25 (`en-GB` short month + day); `<CartesianGrid>` S:545; `<XAxis interval={6}>` S:546; two `<YAxis>` (left `l` for `total`, accent ticks S:547; right `r` for `applied`, warn ticks S:548), `allowDecimals={false}`; `<Tooltip>` S:549-551 (hover only); `<Line total>` S:552, `<Line applied>` dashed S:553, `dot={false}`, `activeDot r=3`.
- [x] `peak {n} · {date}` caption — S:556, only when `peak.total > 0` (S:186).

### LLM costs card (S:365-407, fixed height 300)
- [x] `how priced?` — S:368-369, `title` tooltip only (pricing sources explanation), `cursor: help`.
- [x] Period pills `1d` / `7d` / `30d` / `all` — S:371-374 (`PERIODS` S:12 → `1|7|30|0`), `setPeriod(id)` → effect S:139 refetches `/stats/llm-costs`. Classes `v2-bdc v2-ctl`. Default `30` (S:83). Also changes the header's "in {period}d" text (S:248).
- [x] Figures `Spend` / `Calls` / `Avg / call` — S:378-384 (`money` S:23: `$x.xx` ≥ $1 or 0, 3 dp < $1, 4 dp < $0.01; `int` S:24). `Avg / call` is `—` when `total_calls` is 0/undefined.
- [x] By-purpose table — header S:387-391 (`Cache` column `title="Prompt-cache hit ratio"` S:390); rows S:395-403 keyed by index: `purpose` (ellipsis), `model` (mono, ellipsis, `title={c.model}` S:398, `—` fallback), `calls`, `cost`, `cache` (`{ratio}%` accent when `cache_involving` else `—` in `--edge`). Scroll container `v2-scroll v2-gutter` S:394. Rows not clickable.

### Schedules card (S:411-448)
- [x] Subtitle `{n} job(s) · next runs in {TZ_SHORT}, schedules as configured (UTC) · intervals and crons live in Settings` — S:414. "Settings" is **not a link**.
- [x] Column header — S:416-420: `Job | Job ID | Schedule | Next run | Status | Run`.
- [!] Rows — S:421-447 from `ordered` (S:227: `scrape_all` first, rest in API order). Per row: name (`title={j.name}` S:425, ellipsis), id (mono, `title` S:426), schedule via `decodeCron` S:47-63 (`title={j.schedule}` raw S:427), next run `when(j.next_run)` or `now` while running S:428, status dot/spinner + text S:429-436 (`Running · {elapsed}s` / `Pending` (`--warn` dot) / `Scheduled` (`--funnel-low` dot)).  — **STAT-04 + STAT-13**
- [!] `Run now` button — S:439-442: rendered only when `trigger_url` (else `—` S:443); `onClick={() => !running && trigger(j)}`; shows `Running` + spinner and drops `v2-bdc` while `running = !!j.running || triggering.has(j.id)` (S:422). **No `disabled` attribute** (guard is the `!running &&` expression). POSTs `job.trigger_url` (list in 2.2). No toast on 202, 409 or failure; the button reads `Running` for a fixed 4 s (S:163) even when the POST failed.  — **STAT-01 + STAT-04 + STAT-13**

### Run history / Activity log card (S:451-527)
- [x] Tab `Run history` / `Activity log` — S:453-455, `setTab(id); setTypeOpen(false)`. Serif headings, accent underline on the active tab. Not persisted.
- [x] Tab note — S:456: `last 30 scheduler and manual runs` / `everything the pipeline did, newest first`.

**Run history** (S:485-507)
- [x] Column header `Time | Job ID | Trigger | Status | Duration | Result` — S:487-490.
- [x] Rows — S:491-505, keyed `r.id`: `when(started_at)`, `job_type` (ellipsis), `trigger`, status `Pill` (S:499: `--bad-soft/--bad` when failed, `--accent-soft/--accent` when running, `--hover-soft/--accent` otherwise), `dur(duration_seconds)` (S:37, `—` while running), result = `r.error || r.result_summary || '—'` (ellipsis, `title` carries full text S:502, red when failed).
- [!] **No pagination, no "load more", no row click, no link to `/monitor/run/{id}`** — hard `limit=30` (S:127). `meta` and `finished_at` fields unused in the table.  — **STAT-18**

**Activity log** (S:509-526)
- [x] `Type ▾` dropdown button — S:460-462 (`v2-bdc v2-ctl`; accent styling + ` · 1` suffix when a type is active); toggles `typeOpen`.
- [x] Dropdown backdrop — S:465 closes.
- [!] Type menu items — S:467-471 from `TYPE_OPTS` S:21 (`All types`, `Scrape`, `H-1B`, `Résumé score`, `Email`, `Telegram`), `setActType(id); setTypeOpen(false)`; ✓ on the active one; class `v2-menuitem`. Selecting triggers `loadActivity` via the debounced effect S:141.  — **STAT-08**
- [x] `⌕ Company…` search `<input>` — S:478-479, `setActQuery`; debounced 300 ms (S:141); trimmed before sending (S:134). No clear (×) control; no Enter handling (not needed).
- [x] Column header `Time | Type | Message | Company` — S:510-513.
- [x] Rows — S:514-523 keyed `a.id`: `when(created_at)`, type badge (`TYPE_CLASS` S:17-20 → `sm-keyword|sm-lipersonal|sm-levels|sm-freehire|sm-jobright`, fallback `sm-extension` S:518; `_` → space), message (ellipsis + `title` S:520), company (ellipsis, `—` fallback S:521). Not clickable; `details` unused.
- [!] **No pagination** — hard `limit=50` (S:134).  — **STAT-18**

### Links out / other manual triggers
- [!] **No `<a>`, no `navigate`, no `Link` anywhere in Stats.jsx.** Nothing links to Feed, Companies, Searches, Settings, or a job. The only outbound actions are `Run now` POSTs and `Refresh`.  — **STAT-16**
- [x] Manual trigger buttons beyond `Run now`: **none** (no backup/digest/cleanup buttons outside the schedule rows — they exist only as rows when the scheduler registers those jobs).

## 2.4 States rendered

Branches that exist:
- [x] Loading — S:233 `Loading…` until `loadCore` settles (S:138). Because every GET catches to `null`, this always resolves — it cannot hang like Persona.
- [x] Header sweep — S:244-246: `No scrape recorded yet` (no `scrape_all` run) / `Last sweep {ago}` / `Last sweep failed {ago}` (`status==='failed'`); `ago()` S:38-45 returns `null` for missing dates → `—`.
- [x] Header failing sources — S:247 `{n} source needs attention` / `{n} sources need attention`.
- [x] Header LLM spend — S:248 hidden when `costs` is null (fetch failed) — no other symptom of the failure.
- [x] KPI missing data — `int(undefined)` → `—` (S:24) for Total/Saved/Applications when `/stats` failed; `New this week` shows `0` (series always fills 30 days, S:171-181); `Best open score` `—` (S:268).
- [x] `New this week` delta hidden when previous week was 0 (S:265).
- [x] `in play` sub always shown (S:267), `0 in play` when no applications.
- [x] Funnel with zero applications — bars at `0%` width (S:210), counts `0`, conversions `—` (S:213). Card still renders (no empty copy).
- [x] Funnel toggle absent when `sankey === null` — S:288 (no `/stats/sankey` rows, only backward/self hops, or all `value` 0). No copy explains why "Flow" is missing.
- [x] Sankey with data — S:297-305.
- [x] Score distribution zero scored jobs — endpoint still returns 5 zero buckets (main.py:1204/1229) → five 2 px bars labelled `0` (S:342), subtitle `0 scored jobs`, `avg` hidden (S:331). **No empty copy.** If the request failed, `buckets = []` (S:229) → blank 118 px area, subtitle `— scored jobs`.
- [x] `tailored` average hidden when `tailored_avg == null` (S:334).
- [x] Timeline with no jobs — flat line at 0 across 30 days; `peak` caption hidden (S:556). **No empty copy.**
- [x] LLM costs empty window — S:404 `No LLM calls in this window.`; figures `—`/`$0.00` (`money(0)` → `$0.00`, S:23; `int(0)` → `0`).
- [x] Schedules — subtitle `0 jobs` (S:414) + header row and **nothing else** when `/scheduler/jobs` returns `[]` or failed. **No empty copy.**
- [~] Schedule row states — `Running · {n}s` (spinner) / `Pending` (warn dot) / `Scheduled` (green dot) S:430-435; `now` in Next-run while running S:428; `Run now` vs `Running` vs `—` S:438-443. `next_run` null → `—` (S:33).  — *untestable: running state simulated via triggering/interception, not a live run*
- [x] `decodeCron` — S:47-63: passes through strings containing `Every` (interval jobs, search/company overrides), non-5-field strings, and unrecognised patterns unchanged; converts `m h * * *` → `Daily at HH:MM`, `*/n` minute/hour, day-of-week/day/month prefixes.
- [x] Run history empty — S:506 `No runs yet.`
- [x] Run row failed — red result text + red pill (S:499, S:502); running row — accent pill, `—` duration.
- [x] Activity empty — S:524 `No activity matches.` — same copy whether the log is empty or the filters excluded everything.
- [x] Type filter active — `Type · 1` label + accent styling (S:460-461).
- [x] Long strings — ellipsis + `title` on: schedule name S:425, id S:426, schedule S:427, run result S:502, activity message S:520, activity company S:521 (no title), cost model S:398, cost purpose S:397 (no title); KPI value S:272 (ellipsis, no title — a huge `Best open score` company sub is clipped); header subtitle S:243 (nowrap + ellipsis, so a long "sources need attention · $ on LLM" line truncates from the right). Fixed-width cells with **no** ellipsis: Time S:495/S:516, Trigger S:497, Duration S:501, Pill status S:499 (nowrap — a long status string would overflow). Sankey node labels S:573-575 have a 112 px right margin and no truncation.

Branches that do NOT exist:
- [!] **Any error state** — no endpoint failure produces copy, a toast or a retry; the screen silently renders `—`/zeros. `/stats` 500 is indistinguishable from an empty database except that `int(undefined)` renders `—` vs `0`.  — **STAT-03**
- [x] **Zero jobs total** — no "nothing scraped yet" onboarding message; KPIs read `0`, charts flat.
- [x] **Zero applications** — funnel shows `0`s with no explanatory copy; Sankey toggle simply absent.
- [!] **No transition data but applications exist** (all created before `status_transitions` existed, or `from` missing) — funnel Interview/Offer fall back to the current-status snapshot (S:204-205) with no indicator that the fallback is in use; footnote still claims "ever reached that stage" (S:320).  — **STAT-09**
- [x] **No runs at all** — handled for the table (`No runs yet.`) but the header reads `No scrape recorded yet` and the funnel/score/timeline cards carry no first-run guidance.
- [x] **Schedules empty** — no copy (see above).
- [!] **Scheduler job running for a long time** — `Running · 3600s`, never formatted as minutes (S:434; `dur()` is not used there).  — **STAT-13**
- [!] **Trigger failure** (409 duplicate / 404 / 500) — no branch; button shows `Running` for 4 s then reverts (S:163).  — **STAT-01**
- [!] **`cv_scores` is `{}`** on the best job — `Math.max()` of an empty list is `-Infinity` → tile shows `-Infinity` (S:268: `best?.cv_scores` `{}` is truthy). Reachable when no `new/saved` job has a numeric score but at least one has `{}` (the Feed's `/jobs/feed-stats` explicitly treats `cv_scores::text = '{}'` as unscored, routes_jobs.py:232, so the shape occurs).  — **STAT-02**
- [x] **Score distribution request failed** — blank bar area, no copy.
- [x] **Activity `type` outside `TYPE_CLASS`** — falls back to `sm-extension` styling, still rendered (S:518); not a missing branch, but there is no "unknown type" label.
- [x] **Period pill with failed fetch** — S:139 nulls `costs`, so figures go `—` and the by-purpose list shows `No LLM calls in this window.` — **indistinguishable from a genuinely empty window.**
- [x] No skeleton loaders, no per-card loading state on Refresh (old numbers stay until replaced).

## 2.5 Hover styles (Stats)

All hover is CSS-class based. **No `onMouseEnter`/`onMouseLeave` anywhere in Stats.jsx** — the only mouse-driven state is Recharts' own `<Tooltip>`/`activeDot`.

- [x] `.v2-hover-accent-text:hover` (T:174 `color:var(--accent) !important`) — the `↻ Refresh` control S:251. Inline `color: var(--muted)`, so the `!important` is load-bearing. Design's `style-hover="color:#3f6b52"` on the same element (`Stats Ops.dc.html` header) — matches.
- [!] `.v2-bdc:hover` (T:156 `border-color` + `color` → accent, both `!important`) — four call sites, all with inline `border`/`color` that the `!important` must beat:  — **STAT-17**
  - Funnel/Flow toggle pills S:292 (both pills carry the class, including the active one, where border+colour are *already* accent → hover is a visual no-op on the active pill).
  - LLM period pills S:373 (same no-op on the active pill).
  - Activity `Type ▾` button S:460 (same no-op while a type is selected).
  - `Run now` button S:439 — class applied **only when not running** (`className={running ? '' : 'v2-bdc'}`), so a running row has no hover. Design gives this button `style-hover="border-color:#3f6b52;color:#3f6b52"` — matches.
  - Design has **no** `style-hover` on the period pills, the Funnel/Flow pills or the Type button — these three are hovers the code adds beyond the design.
- [!] `.v2-menuitem:hover` (T:149 `background:var(--surface-2)`, **no `!important`**) — activity Type menu items S:468. Each item sets an **inline** `background` (`--accent-soft` when selected, `transparent` otherwise), and an inline style beats a bare class rule → **this hover cannot fire**. Design specifies `style-hover="background:#f3f0e8"` (= `--surface-2`) on exactly these rows, so the intent is present but dead. (Same class/inline-background combination as Persona's Picker items P:118/P:120 — one shared root cause.)  — **STAT-08**
- [x] `.v2-ctl` (T:161 `line-height:1`, not a hover) — Refresh S:251, funnel pills S:292, period pills S:373, Type button S:460.
- [x] `.v2-spin` (T:227, `@keyframes v2-spin` T:226) — Refresh spinner S:253, schedule-row status spinner S:431, `Run now` spinner S:440. Animation, not hover.
- [~] `.v2-scroll` (T:222-224 webkit scrollbar 9px, thumb `--muted` with a 2px `--bg` border) — the page scroll container S:259 and the by-purpose cost list S:394. Headless Linux uses overlay scrollbars (width 0) so this is unmeasurable there.  — *untestable: headless Linux overlay scrollbars are 0px wide*
- [~] `.v2-gutter` / `.v2-gutter-head` (T:216-217 `scrollbar-gutter:stable`) — cost table body S:394 and its header S:387, so the columns stay aligned when the list overflows.  — *untestable: cannot reproduce gutter reflow with overlay scrollbars*
- [x] `.sm-*` badge classes (T:200-206) — activity type badge S:518 (`TYPE_CLASS` S:17-20, fallback `sm-extension`). Class supplies `background`+`color`; the inline `BADGE` object does not set either, so no specificity conflict. Not hover.
- [x] `cursor: help` + `title` only (no hover style): `how priced?` S:369 (also `borderBottom: 1px dotted var(--line-strong)`), `tailored {n}` S:334. Design matches both.
- [x] `title`-only tooltips, no hover style: KPI tiles S:270, score buckets S:340, `Cache` column head S:390, cost model S:398, schedule name/id/schedule S:425-427, run result S:502, activity message S:520.
- [x] Elements with `cursor: pointer` and **no hover treatment at all**: the `Run history` / `Activity log` tabs S:454 (design gives them none either — matches).
- [x] Rows with **no** hover: every table row on the screen — schedules S:424, run history S:494, activity S:515, cost by-purpose S:396 — and the five KPI tiles S:270. No `.v2-row`/`.v2-arow`/`.v2-crow` anywhere. Design also gives none.
- [~] Recharts hover surfaces (not CSS): `<Tooltip>` on the Sankey S:302 and the line chart S:549-551 (both styled with `var(--surface)`/`var(--line)`), `activeDot={{r:3}}` S:552-553, and Recharts' built-in link/node highlight on `<Sankey>`.  — *untestable: rendered and token-styled, but tooltip content not asserted*
- [x] No focus styles: the only focusable element is the company `<input>` S:479, which sets `outline: 'none'` with no replacement — **focus is invisible**.

## 2.6 Theme (Stats)

- [x] Theme comes from the shell only: `jobnavigator_dark_mode` → `data-theme` on `.jn-v2` (V2App:52/90), tokens swapped at T:74. Stats.jsx never reads the theme.
- [x] **Colour literals in Stats.jsx: none** — every colour is `var(--…)`, including inside the Recharts props (`stroke`, `fill`, `contentStyle`, axis `tick.fill`). Recharts passes these straight into SVG attributes, so they resolve against the element's own custom properties; this needs measuring in dark, since a `var()` that fails to resolve in an SVG attribute renders black with no error.
- [x] Tokens Stats uses that no other screen leans on: `--sand`, `--gold`, `--funnel-low`, `--funnel-mid` (T:18, dark T:86 — deliberately *lifted*, not darkened), `--stage-applied` (T:9 / T:79), `--good`, `--warn`.
- [x] `repeating-linear-gradient` legend swatch S:358 interpolates `var(--warn)` inside a gradient — check it renders in both themes (a gradient with an unresolved custom property drops the whole background).
- [!] Token used off-purpose: `var(--edge)` (a border token) as **text** for the `—` in the Cache column S:401 and for the inactive tab label S:454; `var(--line)` as a **bar fill** for the `0-20` bucket S:342 (dark `--line` is `#3e3b32`, barely distinguishable from `--surface` `#28251b`) — contrast worth measuring in dark.  — **STAT-21**
- [x] `--hover-soft` is used as a *static* background (the neutral run-status pill S:499), not as a hover.
- [x] Recharts `CartesianGrid stroke="var(--line-soft)"` S:545 — in dark `--line-soft` (`#2c2a20`) is *darker* than `--surface` (`#28251b`) is light; check the grid is still visible.
- [x] `SankeyNode` S:572-573 fills from `STAGE_FILL` and labels in `var(--text-2)`; `STAGE_FILL` has no `--edge` fallback problem (S:572 falls back to `var(--edge)`).
- [x] Design is light-only; every dark value has to be judged against theme.css, not the `.dc.html`.

## 2.7 Suspicious (Stats)

- [!] **`Math.max()` of an empty object → `-Infinity`** — S:268: `best?.cv_scores` is truthy for `{}`, and `Object.values({}).filter(...)` is `[]`, so `Math.round(Math.max())` renders the literal string `-Infinity` in the "Best open score" tile. Reachable: `routes_jobs.py:232` treats `cv_scores::text = '{}'` as unscored, so the shape exists in the DB.  — **STAT-02**
- [!] **Every fetch failure is silent** — `loadCore` S:102, `loadLive` S:126-127, `loadActivity` S:135, llm-costs S:139/S:155. A 500 renders as `—`/`0`, indistinguishable from an empty database. No toast surface (Toast.jsx not imported), no retry.  — **STAT-03**
- [!] **Trigger failures are `console.error` only** — S:162. A 409 (duplicate run) or a 500 shows the identical "Running" state for a fixed 4 s, then silently reverts. The user has no way to tell a fired job from a refused one. This is the single riskiest control on the screen (the buttons fire `/scrape/run-all`, `/db/backup`, `/db/cleanup`, `/auto-reject/run`, `/email/check-now`, `/telegram/digest`, `/h1b/refresh`).  — **STAT-01**
- [!] **`Run now` has no confirmation and no `disabled`** — S:439; the only guard is the `!running &&` expression. A stray click on `Job cleanup` deletes real rows (HANDOVER: "a `job_cleanup` trigger once deleted 81 real skipped jobs").  — **STAT-01**
- [!] **The 4 s `triggering` window is decoupled from reality** — S:163 `setTimeout` in `finally`. If the job finishes in 1 s the row still says "Running"; if `loadLive` then reports `running: null`, `triggering` still holds the id, so the row lies for the remainder of the 4 s.  — **STAT-01**
- [x] **Polling never pauses** — S:144-148, no `visibilitychange` guard, so a background tab keeps issuing two GETs every 10 s (3 s while anything runs) forever.
- [x] **`sankey` useMemo has a suppressed exhaustive-deps lint** S:223 — `RANK` is defined inside the component body (S:215) and recreated every render, so it is deliberately omitted. Benign, but it means the memo silently depends on a value it does not list.
- [x] **`ordered` sort is not a total order** S:227 — the comparator returns `0` for every pair that does not involve `scrape_all`; `Array.sort` is stable in V8 so this works, but it is a comparator that violates the sort contract.
- [!] **Funnel mixes two populations without saying so** — `Saved` is a live job count, the other three are application counts (S:202-205); the widest-bar normalisation therefore scales applications against a job count. The footnote S:320 half-explains it.  — **STAT-06**
- [!] **`reached.interview || st.interview` fallback is invisible** S:204-205 — when the transition graph is empty the card silently falls back to the current-status snapshot while the footnote still claims "ever reached that stage".  — **STAT-09**
- [x] **`conv()` divides by a different population than the bar** S:321 — `applied → interview` uses `stats.total_applications` (a total) over `reached.interview` (a transition count).
- [x] **`loading` is one-way** S:96/S:138 — never set back to `true`; Refresh silently swaps numbers under the user with no indication which card is stale.
- [x] **Refresh's llm-costs call swallows differently from the mount effect** — S:155 `.catch(() => {})` keeps the stale value, S:139 `.catch(() => setCosts(null))` clears it. Same failure, two different renders.
- [x] **`weekly.prev === 0` hides the delta** S:265 — a first week of use (prev = 0, now = 40) shows no `+40 vs last`, which is exactly when it would be most informative.
- [!] **`Running · {n}s` never formats** S:434 — `dur()` exists (S:37) but is not used here, so a long scrape reads `Running · 3600s`.  — **STAT-13**
- [x] **`decodeCron` passes anything containing the substring `Every` straight through** S:48 — a job named/scheduled with that word anywhere skips decoding.
- [x] **`when()` and `dayLabel()` use different locales** — `when` `en-GB` with the viewer's TZ, `dayLabel` `en-GB` with **no** `timeZone`, so the 30-day chart labels are in the browser's zone while every table timestamp is in `TZ`. Identical in practice (TZ is the browser zone) but they can drift.
- [!] **`series` builds its keys with `toISOString().slice(0,10)`** S:176 — that is a **UTC** date, compared against the backend's local-date grouping (`cast(Job.discovered_at, Date)`, main.py:1145). West of UTC the whole 30-day series is off by one day.  — **STAT-15**
- [x] **Index keys** — cost rows `key={i}` S:395 (the list is fully replaced per period, so benign).
- [!] **No pagination anywhere** — runs hard-capped at 30 (S:127), activity at 50 (S:134); nothing tells the user the list is truncated.  — **STAT-18**
- [!] **Nothing on the screen is a link** — the rail's pipeline-pulse advertises "Click → Stats · Run history" (V2App:84-85) but lands at the top of the page; `{n} sources need attention` (S:247) does not go to Companies/Searches; `Best open score` does not go to the job; the score buckets do not filter the Feed; "Settings" in the Schedules subtitle (S:414) is plain text.  — **STAT-16**
- [x] **`TODO`/`FIXME`/`console.log`/`debugger`: none.** The only `console` call is S:162.
- [x] **Handlers defined but never attached: none.** All of `loadCore`, `loadLive`, `loadActivity`, `refresh`, `trigger`, `conv` are used.
- [x] **Unused response fields**: `/monitor/history` `meta`/`finished_at` (the header uses `finished_at`, the table does not), `/health/entities` `reason` + `count`, `/stats/timeline` `new`/`saved`/`skipped`/`filtered`, `/stats/llm-costs` `input_tokens`/`output_tokens`/`cache_read_tokens`/`cache_write_tokens`/`cache_hits`/`window_days`, `/activity-log` `details`.
- [x] **Toast.jsx not imported** — the screen has no toast surface, so nothing here can ever report success or failure.
- [!] **No keyboard access** — every control is a `span`/`div` with `onClick`, no `tabIndex`, no `role`, no `onKeyDown`, no `aria-expanded` on the Type dropdown (S:251, 292, 373, 439, 454, 460, 465, 468).  — **STAT-22**

## 2.8 Counts that must agree (Stats)

- [x] `Total jobs` S:264 (`/stats.total_jobs`) — every Job row. Compare with the Feed header's total and with `SELECT count(*) FROM jobs`.
- [x] `Saved` S:266 (`/stats.saved_jobs`) vs the **Feed rail badge** (V2App `countKey`) vs the Feed's own `status=saved` count vs the funnel's `Saved` row S:202 (same source, must be identical).
- [!] `Applications` S:267 (`/stats.total_applications`) vs the **Applications screen** total (reported as 377/378 in the brief — a known discrepancy to chase) vs the funnel's `Applied` row S:203 vs the Sankey's inbound-to-`applied` total.  — **STAT-19**
- [x] `{inPlay} in play` S:168 = `total_applications − (rejected + ghosted + withdrawn)` from `application_statuses` — must equal the Applications board's non-terminal column sum.
- [x] `New this week` S:265 = sum of `total` over the last 7 entries of the filled 30-day series — must equal `/stats/timeline` summed over the same dates, and must be ≤ `Total jobs`.
- [!] Funnel `Interview`/`Offer` S:204-205 — `reached` from `/stats/sankey` vs `application_statuses` snapshot; the two disagree by design (ever-reached vs currently-in), so check which one is actually rendering and that the footnote matches.  — **STAT-09**
- [x] Funnel bar widths S:210 — `round(count / widest * 100)%`, min 2 % when non-zero: measure each bar's px width against the track width and the count.
- [x] Score buckets S:339 — the five counts must sum to `scores.scored_count` S:330, and each bar's height must equal `max(2, round(count/maxBucket*96))` px.
- [x] `avg` S:333 vs the bucket distribution (the mean must fall inside the populated range); `tailored {n}` S:334 vs `tailored_count` in the tooltip.
- [x] `Best open score` S:268 — must equal `max()` of the `cv_scores` of the top job from `/jobs?status=new,saved&sort_by=score&limit=1`, and that job must be the top of the Feed sorted by score.
- [x] LLM costs: `Spend` S:378 = `sum(by_purpose[].cost_usd)`; `Calls` = `sum(by_purpose[].calls)`; `Avg / call` = `Spend / Calls`; the header's `{money} on LLM calls in {period}d` S:248 must equal the card's `Spend` for the same period. Switching period must change all four together.
- [x] `Cache` per row S:401 = `round(cache_hit_ratio * 100)` and must be `—` exactly when `cache_involving` is falsy.
- [x] Schedules `{n} jobs` S:414 = rendered rows S:421 = `len(/scheduler/jobs)` = 7 core jobs + one row per active search with `run_interval_minutes > 0` + one per active company with `scrape_interval_minutes` (main.py:783-881). Cross-check against the Searches and Companies screens.
- [~] `Last sweep {ago}` S:245 (from `/monitor/history?limit=1&job_type=scrape_all`) must match the newest `scrape_all` row in the Run-history table below, and the rail's "pipeline pulse" line (V2App:142).  — *untestable: matches the newest scrape_all row; rail pipeline-pulse not cross-checked this pass*
- [x] `{n} sources need attention` S:247 = `len(companies) + len(searches)` from `/health/entities` — cross-check against the failing entities visible on the Companies and Searches screens.
- [x] Run history rows S:491 ≤ 30; Activity rows S:514 ≤ 50 — confirm the cap is the reason and not a filter.
- [x] Activity type filter: selecting `Scrape` must show only `sm-keyword`-badged rows, and the row count must equal `/activity-log?type=scrape&limit=50`.
- [x] Rail: no badge for Stats (V2App:30 has no `countKey`).
