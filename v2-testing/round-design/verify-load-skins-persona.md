# Initial load, skins and persona import — live verification

Branch `v2-redesign` @ HEAD `aac3a45`, built and live (`docker compose up -d`, all 4 containers running). Backend
container Playwright vs `http://caddy`, API key `pick-a-password`. Scripts written locally this session, copied to
`backend:/tmp/v2t/` via `docker compose cp`, run via `docker compose exec -T backend python /tmp/v2t/<name>.py`.
`DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"; export MSYS_NO_PATHCONV=1`. No commits, builds,
restarts or source edits made. No LLM calls made (the résumé-only import path was exercised; the PDF-import path,
which calls an LLM, was not touched).

Read first: `v2-testing/round-design/initial-load.md` (per-screen gating table, the `useSettled`/`useWarm` mechanism)
and `v2-testing/round3/verify-final.md` (harness method: held-route pattern — register the route handler on the
**context** before the page is created, stash the `Route` object without resolving it, resolve later from the main
thread; per-iteration closures must be built by a factory function, not loop-scope default arguments, or the
handler silently never fires).

Subtitle selector used throughout: `h1 + span` (every v2 screen head renders `<PageTitle>` (`<h1>`) immediately
followed by the count-line `<span>`, whether or not the wrapping row is a `<header>` landmark — confirmed against
source for all 9 screens, including `Resumes.jsx`, which is the one screen whose head row is not `as="header"`).

## Part A — initial-load flash (11 targets)

Fresh-context sampling: subtitle text read every ~20ms for 1.5s after `goto(wait_until="commit")` (fastest possible
observation point, well before "load"). Revisit: second `goto()` in the *same* context (default `wait_until="load"`),
first sample taken immediately after. Held-route: `context.route("**/api/**", …)` captures the *first* GET whose path
exactly matches the screen's main list/document endpoint, holds it 1.3s (chrome sampled every 50ms throughout),
then releases via `route.continue_()` and the response is allowed through for real (no fabricated body).

| id | ✔/✖/~ | measured |
|---|---|---|
| A-feed `/v2/feed` | ✔ | Fresh: 1 distinct non-blank subtitle state, switch at 312ms → `"16 open roles · 401 arrived today · 3 not yet scored"`. No `Loading…` chrome line on first paint (the only `Loading <host>…` text seen was the per-job iframe loader for the auto-opened first row, first appearing at 784ms — well after the settle, inside the already-rendered detail pane; that's `FEED-38`/prior-round behaviour, unrelated to this commit's hooks). Revisit: subtitle present verbatim in the very first sample after `goto` resolves. Held `/api/jobs` (matched): subtitle stayed exactly `""` for the full 1.3s hold, header height `91px` throughout, `91px` after release — identical, no shift. |
| A-searches `/v2/searches` | ✔ | Fresh: 1 state, switch at 276ms → `"6 configs · 4 active · next scheduled run in 2d 10h"`. No Loading line. Revisit: instant. Held `/api/searches`: blank `91px` header held → `91px` after — no shift. |
| A-companies `/v2/companies` | ✔ | Fresh: 1 state, switch at 397ms → `"126 tracked · 61 active · 0 need attention"`. No Loading line. Revisit: instant. Held `/api/companies`: blank `91px` → `91px` — no shift. |
| A-applications `/v2/applications` | ✔ | Fresh: 1 state, switch at 760ms → `"377 applications · 0 in interview · 0 offers · 26 waiting >7d"`. No Loading line (confirms `Applications.jsx`'s pre-existing blank-pane gate, now via `useSettled`, is unchanged). Revisit: first sample after `goto` is blank (`h1` absent) — correct per spec, Applications has **no warm cache** ("nothing is drawn before the settle, so there is nothing to warm"), so a revisit re-runs the same blank→settle sequence, not an instant paint. Held `/api/applications`: nothing rendered during the hold (no `header` element exists pre-ready — consistent with the no-warm design), `91px` header appears only after release, matching every other screen's header height. |
| A-resumes `/v2/resumes` | ✔ | Fresh: 1 state, switch at 331ms → `"4 bases · 51 tailored copies live under their jobs · 297 archived"`. No Loading line (the shelf's `Loading…` row is gone, per spec). Revisit: instant. Held `/api/resumes/shelf`: blank `53px` header (Resumes' head row is shorter, no bottom border) throughout → `53px` after — no shift. |
| A-coverletters `/v2/cover-letters` | ✔ | Fresh: 1 state, switch at 411ms → `"18 letters · 1 live application"`. No Loading line. Revisit: instant. Held `/api/cover-letters`: blank `92px` → `92px` — no shift. |
| A-persona `/v2/persona` | ✔ | Fresh: 1 state, switch at 234ms → `"Saves automatically · autofill 27 of 31 set"`. No Loading line (the whole screen is a blank flex box pre-ready — `if (!ready || !p) return (…null…)`). Revisit: blank at first sample — correct, Persona has no warm cache (spec: "nothing is drawn before the settle"). Held `/api/persona`: nothing rendered during hold, `92px` header appears intact after release. |
| A-stats `/v2/stats` | ✔ | Fresh: 1 state, switch at 379ms → `"Last sweep 2h ago · $0.00 on LLM calls in 30d"`. No Loading line. Revisit: instant (Stats **does** warm-start its header, per spec — subtitle present at the first sample even though the cards still wait). Held `/api/stats`: **the header itself rendered immediately** (title + subtitle box present) while the cards area stayed reserved/blank for the full hold — matches the documented exception ("the header itself… render before the cards"); header height `92px` throughout and `92px` after — no shift. |
| A-settings `/v2/settings` | ✔ | Fresh: 1 state, switch at 179ms → `"Saves automatically · everything stays on this machine"`. No Loading line (`Loading settings…` spinner confirmed gone — whole screen is one blank block pre-ready, matching `if (!ready || !S) return (…)`). Revisit: blank at first sample — correct, no warm cache documented for Settings. Held `/api/settings`: nothing during hold, `92px` header intact after. |
| A-resume-editor `/v2/resumes/{base id}` | **~** | See "Unexpected" below — the **base** band (`isCopy` false branch) is **not** single-settle: fresh-context sampling caught it in **2** distinct states, reproduced on a second independent run: `180ms → "Base résumé · editing here changes future tailoring only …"`, then `248ms → "Base résumé · 303 tailored copies · editing here changes future tailoring only …"` (run 2: `248ms` then `387ms`, same two-step pattern). No page errors either run. Revisit: `docLoaded:false` at first sample — correct, no warm cache for editors. Item 4 (held `/api/resumes/templates`, 1.3s): `[title="Résumé template"]` and `[title="Paper size"]` absent for the entire hold, preview box `757×654px` held **constant** the whole time, both triggers appear only after release, box unchanged (`757px`) afterward — no shift. The doc's own `Loading…` text (line 504, pre-existing, ungated by this commit) is briefly visible before `doc`/`data` populate — out of scope of `aac3a45` but present. |
| A-coverletter-editor `/v2/cover-letters/{id}` | ✔ | Fresh: 1 state at 188/195ms (both runs) → the full context band (`"Written for Camunda — Senior Product Manager - Core Platform (Remote)from Persona Professional & direct · Standard ↻ Regenerate… ⋯"`) appears complete on first non-blank sample — no two-step reveal (this band's line **is** fully NBSP-gated, unlike the résumé base band). Revisit: `docLoaded:false` at first sample — correct, no warm cache. Item 4 (held `/api/cover-letters/templates`, 1.3s): both triggers absent throughout, preview box `758×654px` constant, triggers appear only after release, box unchanged (`758px`) after — no shift. Pre-existing doc-load `Loading…` text (line 309, ungated, out of scope) briefly visible before the document itself resolves. |

### Unexpected

- **A-resume-editor base band is a two-render reveal, not one.** `frontend/src/v2/ResumeEditor.jsx` line ~604 (the
  non-`isCopy` sub-band): `<span>Base résumé · {ctxReady && baseCopyCount != null && <>…N tailored copies · …</>}editing
  here changes future tailoring only</span>`. Unlike the copy branch (whose entire line is `!ctxReady ? NBSP : <>…</>`,
  correctly withheld until the settle), the base branch's sentence is *always* rendered as soon as `doc`/`data` load
  (a separate, earlier, ungated fetch), and only the `N tailored copies ·` clause in the middle is conditioned on
  `ctxReady`. Live sampling shows exactly the flash the whole change was meant to eliminate: the sentence paints once
  without the copy count, then a second render ~70–140ms later inserts it. `initial-load.md`'s per-screen table
  states "The base band's copy count is part of the same settle" — true of the *data*, not of the *paint*: the count
  is fetched alongside the rest of `ctxReady`'s promises, but the base band's JSX doesn't gate on `ctxReady` the way
  the copy band's JSX does, so it still renders twice. Reproduced on two independent fresh-context runs. Cosmetic
  (a few words appearing mid-sentence, not a layout jump — the two states differ only in that inserted clause), but a
  genuine violation of item (1)'s "exactly one non-blank state" for this specific line.
- Both editor doc routes show a brief pre-existing `Loading…` text (`ResumeEditor.jsx:504`, `CoverLetterEditor.jsx:309`)
  while the document's own fetch (not part of `tplReady`/`ctxReady`) is in flight. This fetch was not touched by
  `aac3a45` — the editors were never in the `useSettled`-for-the-document category, only for their auxiliary
  requests — so this isn't a regression, but it is a literal `Loading…` line on first paint of those two routes,
  worth flagging since item (1)'s phrasing names "no Loading… line for first paint" without carving the editors out.

## Part B — skins

`localStorage.jobnavigator_skin` set directly (bypassing the UI), each of the 7 values loaded on `/v2/feed` in both
themes (`localStorage.jobnavigator_theme`). Tokens read via `getComputedStyle(document.querySelector('.jn-v2'))`.

| skin | theme | `--bg` | `--surface-2` | `--muted` | `--text` | `--rail-dim` |
|---|---|---|---|---|---|---|
| default | light | `#fcfbf7` | `#f6f4ee` | `#6d6862` | `#1b1a16` | `#948d7a` |
| default | dark | `#1e1c17` | `#322f24` | `#a8a49d` | `#d9d7d0` | `#8a8371` |
| tone1 | light | `#fbfaf6` | `#f5f3ec` | `#757069` | `#1b1a16` | `#88816f` |
| tone1 | dark | `#1c1a15` | `#2e2c21` | `#9e9a91` | `#dedcd3` | `#817a68` |
| tone2 | light | `#fbf9f5` | `#f4f2eb` | `#7e796f` | `#1b1a16` | `#7d7664` |
| tone2 | dark | `#191813` | `#2a281e` | `#948f85` | `#e4e0d7` | `#787160` |
| tone3 | light | `#faf9f4` | `#f4f1e9` | `#868176` | `#1b1a16` | `#716b59` |
| tone3 | dark | `#171611` | `#27251c` | `#8a8579` | `#e9e5da` | `#6f6957` |
| editorial | light | `#faf8f3` | `#f3f0e8` | `#8f8a7d` | `#1b1a16` | `#66604f` |
| editorial | dark | `#15140f` | `#232219` | `#807b6e` | `#efeade` | `#66604f` |
| alt | light | `#f7f8fa` | `#eef1f6` | `#5f6878` | `#161a21` | `#868d9c` |
| alt | dark | `#161a21` | `#262c37` | `#9aa2b0` | `#d6dae2` | `#828997` |

Every ramp column (`--bg`, `--surface-2`, `--muted`, `--rail-dim` in light) moves monotonically default → tone1 →
tone2 → tone3 → editorial, confirming the OKLab interpolation lands where `theme.js`'s comments describe it
(¼/½/¾ of the way from default to editorial). `--text` stays flat at `#1b1a16`/dark `#…` across the warm ramp by
design (only `alt` moves it, to the cool slate `#161a21`/`#d6dae2`) — matches "switching data-skin may change colour
and font family and nothing else" plus the documented alt-only exception.

**`board` is gone**: setting `localStorage.jobnavigator_skin = "board"` and loading the page resolves
`document.querySelector('.jn-v2').getAttribute('data-skin')` to `"default"` (not `"board"`) and every token above is
byte-identical to the `default` row, in both themes — confirmed live, not just by absence of a CSS block. (Grepped
`frontend/src/v2/theme.css`: only `.jn-v2[data-skin="editorial"]`/`[data-skin="tone1"/"tone2"/"tone3"/"alt"]` blocks
exist; no `[data-skin="board"]` rule anywhere, so the unmatched selector falls through to the unqualified `:root`
tokens, i.e. default — and `theme.js`'s `SKINS` array / `index.html`'s boot-script `skins` array both list
`editorial` in `board`'s old slot, so a stored `"board"` value also fails the `skins.indexOf(k) >= 0` guard and is
normalized to `"default"` before paint, which is exactly what was measured.)

**No page errors** on any of the 12 skin×theme combinations; console noise limited to the same two pre-existing
artifacts every run surfaces (`400` on a probing request, `X-Frame-Options` refusal from the auto-opened Meta job's
iframe) — unrelated to skins.

**`/v2/ui` gallery**: the route is live in this build and lists, verbatim, under `SKIN`: `default`, `tone1`, `tone2`,
`tone3`, `editorial`, `alt` — six pills, that exact order, `board` absent.

## Part C — persona import (résumé path only)

`GET /api/persona` snapshotted first (`persona_before.json`, kept for the session) — this is the **live production
persona** (real contact data), not a fixture, so the restore step at the end matters.

1. **UI flow**: `/v2/persona` → counters read `27 of 31 set` (autofill) before. Clicked `Import ↑` → `From a résumé…`
   → picker modal opened, listing the 4 base résumés → clicked the base named `PM`.
2. **Confirm dialog body** (`ConfirmDialog`, exact text): *"Contact and résumé content will be replaced by PM. Work
   authorization, demographics, compensation, preferences and the Q&A bank stay as they are."* — names all five
   untouched nodes (`work_auth`, `demographics`, `compensation`, `preferences`, `qa_bank`).
3. Clicked **Replace** → `POST /api/persona/import` → `200`. Toast: **`"Imported 3 roles · 13 bullets · 4 skill
   groups from PM"`** — exact `N roles · M bullets · K skill groups from <name>` shape, and the numbers match the
   PM résumé's own data (3 experience entries, 13 bullets total, 4 skill groups, checked independently against
   `GET /resumes/{id}`).
4. **Editor reflects the import** immediately: Experience `(3)` accordion shows the three imported roles verbatim
   (`Senior Product Manager · Additiv · May 2022 – Present · 7 bullets`, `Product Manager · Fincite · Jul 2018 – Apr
   2022 · 4 bullets`, `Operations Intern · Tracktics · Apr – Dec 2017 · 2 bullets`). Autofill counter changed
   `Contact / basics` to `7 of 11 set`; the header counter changed `27 of 31 set` → **`23 of 31 set`** — a real,
   observed change, not a static label.
5. **API cross-check**: `contact` after import = `{first_name: "Viktor", last_name: "Esadze", city: "Frankfurt",
   state: "Germany  ·  Open to relocation", linkedin: "linkedin.com/in/viktoresadze", portfolio:
   "viktoresadze.com", email: "viktoresadze@gmail.com"}` — matches `_contact_from_header`'s documented rules applied
   to PM's header verbatim (mailto: → email, "LinkedIn"-labelled url → linkedin, url-bearing item → portfolio,
   2-part comma location → `city` = first part, second part tested against the dial-code country table and — since
   the résumé's own contact line is `"Frankfurt, Germany  ·  Open to relocation"`, not a clean `"Frankfurt,
   Germany"` — the untrimmed `"Germany  ·  Open to relocation"` fails the exact country-name match and lands in
   `state` instead of `country`. This is a real edge case worth noting: the parser has no way to separate a
   relocation note appended after `·` from the country name, so a résumé header written this way imports a messy
   `state` value rather than a clean `country`. Not a crash or data-loss bug — just a parsing edge the source data
   exposes — logged here as an observation, not a defect.). `resume_content.header` is `null` (correct — the header
   maps to `contact`, not `resume_content`, per the code's own `_CONTENT_DEFAULTS`/comment). `resume_content.skills`
   = PM's 4 skill groups verbatim. The five untouched nodes (`work_auth`, `demographics`, `compensation`,
   `preferences`, `qa_bank`) are **byte-equal** to the pre-import snapshot.
6. **Error paths** (`POST /api/persona/import`, API-only):
   - tailored copy id → **`400`**, `detail: "'PM → Nomura — Product Manager- Electronic Trading' is a tailored copy
     — import from a base résumé"`.
   - unknown id (`00000000-0000-0000-0000-000000000000`) → **`404`**, `detail: "Resume not found"`.
   - empty body (`{}`) → **`400`**, `detail: "Send a resume_id, or upload a PDF file"`.
7. **Restore**: `PATCH /api/persona` with all seven nodes set back to the snapshot values → `200`. Re-fetched
   `GET /api/persona` and diffed every node against `persona_before.json`: **`contact`, `work_auth`, `demographics`,
   `compensation`, `preferences`, `resume_content`, `qa_bank` all byte-equal** (`all_restored: true`). The live
   persona is back to exactly what it was before this session touched it.
8. **Activity-log rows**: exactly one row was created by the whole test (the three error-path calls raise before
   reaching `log_activity`, so they logged nothing): `id a61d6e94-3054-418a-b84b-a16eb45dfd6a`, `type "persona"`,
   `message "Persona imported from resume:PM"`, `created_at 2026-09-04T16:36:44Z`. **No delete endpoint exists**
   for `/api/activity-log` (grepped `backend/main.py` and every `backend/api/routes_*.py` — only the `GET` handler
   at `main.py:1073`), so per the task's fallback this row is left in place and noted here rather than removed.

## Summary

**12 of 13 ✔, 1 ~ (partial — a real but cosmetic two-render flash on one line), 0 ✖.**

- Part A: 9/9 named screens fully verified — exactly one non-blank subtitle state on first paint, no `Loading…`
  chrome line, correct revisit behaviour split cleanly along the documented warm/no-warm line (Feed, Searches,
  Companies, Résumés, Cover Letters, Stats warm-start instantly; Applications, Persona, Settings have no warm cache
  and correctly re-blank on every visit), and every held-route header height identical blank-vs-filled (no layout
  shift). The cover-letter editor is fully clean (single-render band, pickers correctly withheld, preview box height
  constant across the `tplReady` boundary). The résumé (base) editor passes item 4 cleanly but fails item 1's
  single-state requirement for its band line — a genuine, reproduced defect, logged above.
- Part B: fully verified — the six-skin ramp reads correctly in both themes, `board` is confirmed gone at both the
  CSS-source and live-computed-style level, and `/v2/ui` lists the six skin pills in the documented order.
- Part C: fully verified — dialog text, toast copy and numbers, editor reflection, counter change, API-level node
  mapping, all three error paths, and a clean byte-equal restore of the live production persona.

### Persona-restore proof

`persona_restore.py` output: `{"patch_status": 200, "restored_byte_equal": {"contact": true, "work_auth": true,
"demographics": true, "compensation": true, "preferences": true, "resume_content": true, "qa_bank": true},
"all_restored": true}` — every node of the live persona is back to its pre-test value, confirmed by a direct
`GET /api/persona` diff against the snapshot taken before the first import call.
