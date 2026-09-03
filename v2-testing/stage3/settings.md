# Stage 3 — Settings

Tested: 2026-09-02, bundle index-Dnrx3n0f.js (HEAD 5c6c17a), themes light+dark, viewport 1440×900 (+ one narrow 1024×700 pass)
Design: `v2-testing/design/Settings Ops.dc.html`   Inventory: `v2-testing/inventory/v2-settings.md` + `v2-testing/inventory/settings-matrix.md`
Scripts: `set_1.py` … `set_11.py` (scratchpad)   Screenshots: `v2-testing/artifacts/settings/`

Live DB at test time: 86 settings rows; `llm_provider = claude_code` (keyless → the **API key** row is hidden, so **67** of the 68 spec'd rows render — matches the inventory).

---

## Design re-diff (required deliverable)

`Settings Ops.dc.html` grew after the screen was built and had never been re-diffed. Below is every section and row in the design's `<script type="text/x-dc">` `sections()` block, marked against `frontend/src/v2/Settings.jsx:210-338`.

**Sections: 15 in the design, 15 in the JSX, same ids and same order.** Group labels AI / PIPELINE / INTEGRATIONS / SYSTEM identical.

### Row-by-row

| # | Design section · row (dc line) | In JSX? | Note |
|---|---|---|---|
| **models** | sub: "one Primary model for everything; override per feature only where it pays" (`:311`) | **differs** | JSX `:211` "each individual prompt can be run against different model, if needed" |
| 1 | Primary provider · model (`:312`) | present `:212` | design box 220 + box2 260 = JSX |
| 2 | API key (`:315`) | present `:215` | JSX adds `hide()` for keyless providers — design always shows it |
| 3 | Scoring (`:316`) | present `:216` | |
| 4 | Scoring fallback (`:317`) | present `:217` | |
| 5 | Tailoring (`:319`) | present `:219` | |
| 6 | Cover letters (`:320`) | present `:220` | |
| 7 | Autofill (`:321`) | present `:221` | |
| 8 | Email classification (`:322`) | present `:222` | |
| 9 | Model catalog (`:323`) | present `:223` | help truncated in JSX ("… — changes show up in every model picker" dropped) |
| **scoring** | sub identical (`:329`) | ✓ | |
| 10 | Default résumé (`:330`) w260 | present `:227` | design help is longer ("…the last stop before nothing gets scored. Empty = score against all bases + Persona.") |
| 11 | Max parallel jobs (`:331`) **w170** | present `:228` | JSX w135 → SET-20 |
| 12 | Default depth (`:332`) **w340** | present `:229` | JSX w260 → SET-20 |
| 13 | On save action (`:334`) **w340** | present `:232` | JSX w260 → SET-20 |
| 14 | Prompt caching (`:335`) | present `:234` | |
| 15 | Scoring rubric (`:337`) | present `:236` | |
| 16 | Light output schema (`:339`) | present `:237` | |
| 17 | Full output schema (`:341`) | present `:238` | |
| **tailoring** | sub: "bullet rewrites — never invents skills or experience" (`:344`) | **differs** | JSX `:240` "AI-rewritten résumés" |
| 18 | Résumé tailoring prompt (`:345`) | present `:241` | |
| 19 | Persona tailoring prompt (`:347`) | present `:242` | |
| 20 | Auto-score after tailoring (`:349`) **w340** | present `:244` | JSX w260; JSX also moves it below the new row 21 |
| — | *(no design row)* | **EXTRA in JSX** `:243` | **Max parallel tailors** — `tailoring_max_concurrent`, a key that post-dates the design and is not in v1 either. Correct addition. |
| **letters** | sub: "voice presets are injected into the prompt" (`:351`) | **differs** | JSX `:247` "AI-written based on Persona or résumé" |
| 21 | Default voice (`:352`) | present `:248` | |
| 22 | Voice presets (`:353`) | present `:249` | design sub says `prompt` per voice, live schema uses `instruction`; JSX sub is correct |
| 23 | Cover letter prompt (`:355`) | present `:250` | design placeholders `{length} {voice_prompt} {job_description} {resume_json}`; JSX sub matches the real prompt |
| **autofill** | sub "used by the extension on ATS forms" (`:358`) | ~ | JSX "used by the Chrome extension on ATS forms" |
| 24 | Default answer length (`:359`) **w170** | present `:253` | JSX w135 → SET-20 |
| 25 | Autofill prompt (`:360`) | present `:254` | |
| 26 | Field patterns (`:362`) | present `:255` | |
| 27 | Option synonyms (`:364`) | present `:256` | |
| **prep** | sub identical (`:367`) | ✓ | |
| 28 | **"Prep handover template"** (`:368`) | renamed `:259` | JSX `"What I need from you" section` — same key `prep_ask`. Deliberate; the backend only appends this block. |
| 29 | Include by default (`:370`) **w340** | present `:260` | JSX w260 → SET-20. Design value example "Posting · résumé · emails · notes" — a 4th section (emails) the backend does not support. |
| **emailclass** | sub "turns Gmail replies into application events" (`:372`) | **differs** | JSX `:264` "reads Gmail replies" |
| 30 | LLM classification (`:373`) | present `:265` | |
| 31 | Confidence threshold (`:374`) **w170** | present `:266` | JSX w135 → SET-20 |
| 32 | Classification prompt (`:375`) | present `:267` | |
| 33 | Gmail query · subjects (`:377`) | present `:268` | |
| 34 | Gmail query · senders (`:379`) | present `:269` | |
| 35 | Gmail query · exclusions (`:381`) | present `:270` | |
| **scheduler** | sub "…crons are min hour day month dow, empty = off" (`:384`) | **differs** | JSX `:272` drops the field legend: "crons empty = off" |
| 36 | Scrape all companies (`:385`) **w170** | present `:273` | w135 |
| 37 | Email check (`:386`) **w170** | present `:274` | w135 |
| 38 | Cleanup after (`:387`) **w170** | present `:275` | w135; design help "Days before unsaved postings are purged" vs JSX "ignored and skipped job postings" (JSX matches `scheduler.py:238`) |
| 39 | **"Auto-reject after"** (`:388`) | renamed `:276` | JSX "Auto-reject threshold" |
| 40 | DB backup · cron (`:390`) | present `:279` | design help "Nightly **SQLite** snapshot" — wrong DB (Postgres); JSX "Database snapshot" is right |
| 41 | Telegram digest · cron (`:391`) | present `:280` | |
| 42 | H-1B refresh · cron (`:392`) | present `:281` | |
| 43 | Job cleanup · cron (`:393`) | present `:282` | |
| 44 | Auto-reject · cron (`:394`) — **last row** | present `:278` — **5th row** | order differs |
| **exclude** | sub identical (`:397`) | ✓ | 3/3 rows present |
| **dedup** | sub "same job from two sources isn't saved twice" (`:405`) | **MISSING** | JSX `:289` passes `""` → the section header renders with no subtitle |
| 45 | Stripped params (`:406`) | present `:290` | |
| **notifications** | sub identical (`:409`) | ✓ | |
| 46 | Telegram (`:410`) | present `:293` | |
| 47 | Chat ID (`:411`) **w170** | present `:294` | w135 |
| 48 | Score threshold (`:412`) **w170** | present `:295` | w135 |
| 49 | Test / "Send test message" (`:413`) | present `:296` | |
| 50 | Webhook secret (`:414`) — a **bordered BOX** (w260, muted value) + Rotate | present `:297` but **not a box** | JSX renders the preview as a bare mono span, `flex:1`. Visual deviation → SET-22 |
| 51 | Register webhook (`:417`) | present `:306` | |
| **tracer** | sub "per-application open tracking in Stats" (`:419`) | ~ | JSX "per-application link click tracking" |
| 52 | Rewrite links (`:420`) | present `:314` | |
| 53 | Base URL (`:422`) | present `:316` | |
| 54 | URL style (`:423`) | present `:317` | design offers "Short — /l, /gh" / "readable" — a scheme the backend never had. JSX's path/param/path_jobid/param_jobid matches `routes_resumes.py:296`. **Design is stale, code is right.** |
| **jobright** | sub identical (`:425`) | ✓ | 2/2 rows present |
| **linkedin** | sub "…the extension's separate capture identity" (`:429`) | ~ | JSX "…separate mock account" |
| 55 | Personal email (`:430`) | present `:326` | |
| 56 | Personal password (`:431`) | present `:327` | |
| 57 | Session cookie (`:432`) — a plain BTN with a static help string | present `:328` as a live `LinkedInRow` | **code is richer**: live status/phase, PIN entry, 2.5 s poll |
| 58 | Mock account email (`:433`) | present `:329` | |
| 59 | Mock account password (`:435`) | present `:331` | |
| **advanced** | sub "escape hatches — most days none of this gets touched" (`:437`) | **MISSING** | JSX `:333` passes `""` |
| 60 | Proxy URL (`:438`) | present `:334` | |
| 61 | Dashboard API key (`:439`) — a **BOX pw** echoing `jn_live_8Kd2…9mQx` with show/hide, **no save button** | present `:335` as `ApiKeyRow` | **code is safer and deliberately different** (never echoes, explicit "Save key"). Design would have re-saved the mask. |
| 62 | DB backup / "Run backup" (`:440`) | present `:336` | |
| 63 | **H-1B data / "Refresh now"** (`:441`) | **MISSING** | → SET-18 |
| 64 | **Job cleanup / "Run cleanup"** (`:442`) | **MISSING** | → SET-18 |

**Totals: design 64 rows across 15 sections; JSX 68 rows.** The JSX adds `Max parallel tailors` and, relative to the design's `advanced`, drops two manual triggers. The remaining count difference is the design's row list being written before six keys existed.

### Modals

| Design | JSX | Verdict |
|---|---|---|
| Edit modal 680 × 640, textarea `min-height:220px` (`:138,:145`) | `min(1020px, 94vw)` × `min(1280px, 92vh)`, textarea `minHeight:440` (`:649,:658`) | deliberate ("1.5× wider and 2× taller", comment `:656`) → SET-21 needs decision |
| Edit footer: status · Reset to default · Done (`:148-150`) | same (`:661-667`) | ✓ |
| Catalog modal 600 × 620 (`:158`) | same (`:717`) | ✓ |
| Catalog typeahead = absolutely-positioned dropdown under the field, first item pre-highlighted with `↵ to add`, matched substrings **bolded**, footer "4 of 324 match · or paste any slug and Add" (`:168-174`) | plain inline list of ≤8 rows rendered *above* the catalog, no bolding, no ↵ hint, no match-count footer (`:737-743`) | → SET-16 |
| Catalog row `×`: `delDisplay: custom ? "flex" : "none"` (`:466`) — **seeded models cannot be removed** | `×` on every row incl. seeded (`:749`) | → SET-17 |
| Catalog `×` hover: `border-color:#9c3b30;color:#9c3b30` (`:184`) | `.v2-hover-bad-text` = colour only, border unchanged | → SET-15 |
| Catalog "N of M match" footer | absent | part of SET-16 |
| Design has a `CHIPS()` renderer + 3 chip slots (`:113-117,:283-293`) | absent | **dead in the design too** — no section calls `CH`. Correctly not built. |

### Hovers declared in the design

| design `style-hover` | element | built? |
|---|---|---|
| `color:#1b1a16` on rail anchor (`:69`) | `.v2-anchor` | ✓ `.v2-anchor:hover{color:var(--text)}` |
| `border-color:#3f6b52;color:#3f6b52` on **Edit** pill (`:105`) | `.v2-bdc` | ✓ |
| `border-color:#3f6b52` on **ActionBtn** (`:110`) | `.v2-bd` | ✓ |
| `background:#f3f0e8;color:#1b1a16` on modal ✕ (`:142,:162`) | `.v2-hover-accent` | ✓ |
| `background:#f3f0e8` on catalog suggestion rows (`:170-172`) | `.v2-menuitem` | ✓ |
| `border-color:#9c3b30;color:#9c3b30` on catalog × (`:184`) | `.v2-hover-bad-text` (colour only) | **partial** → SET-15 |
| `color:#9c3b30` on chip × (`:114-116`) | chips not built | n/a |
| `border-color:#3f6b52;color:#3f6b52` on Reset to default (`:149`) | `.v2-bdc` | ✓ |
| rail/collapse hovers (`:42,:43,:48`) | shell, not this screen | n/a |

---

## Findings

### SET-01 · P1 · Typing after a revealed secret mask saves `••••••<typed>` and destroys the stored secret
**Where** `frontend/src/v2/Settings.jsx:66-88` (`TextBox`), route `/v2/settings` — affects 11 secret rows (`llm_api_key`, the 6 override `*_api_key` boxes, `jobright_password`, `linkedin_password`, `linkedin_mock_password`).
**Repro** Settings → Jobright.ai → Password (stored, 15 chars). Click into the box; it reveals the *literal* mask `••••••` as editable text. Press End, type one character, blur.
**Expected + why** The mask is a display artefact of `GET /settings` (`routes_settings.py:28` returns `"•"*6` for any set secret). `PATCH` only drops a value that is *exactly* the mask (`routes_settings.py:44-46`), so anything built on top of it is written verbatim. Editing a secret must never send mask characters.
**Actual** intercepted PATCH body: `{"jobright_password":"••••••X"}` (script `set_3.py`). Server-side that becomes the stored password — the real one is gone, with a "Saved" flash. Blur without editing correctly sends nothing.
**Proposed fix** Clear the box on reveal; refuse to commit a value that is still the mask; refuse to commit an empty box over a stored secret.
**Status** fixed in source (rebuild pending) — `Settings.jsx:66-100`

### SET-02 · P2 · An unset secret renders as six bullets, identical to a set one
**Where** `Settings.jsx:70` — `const masked = secret && !shown` ignores whether a value exists.
**Repro** Intercept `GET /settings` with `jobright_password: ""` (unset). The row still shows `••••••` and a "show" link.
**Expected + why** `routes_settings.py:28` returns `""` for an unset secret precisely so the UI can distinguish the two; the inventory (§4) assumed "unset secret renders empty box with 'show'". It does not.
**Actual** `set_10.py` → `unset_secret_input = "••••••"`, `unset_secret_eye = "show"`. There is no way to tell from the screen whether a password is stored, and revealing an *empty* field still shows a phantom mask you can type after (SET-01).
**Proposed fix** `masked = secret && !shown && !!value`; hide the show/hide link when there is nothing to show.
**Status** fixed in source (rebuild pending) — `Settings.jsx:76,96`

### SET-03 · P1 · "Save key" writes the new API key locally and refreshes the session cookie even when the PATCH failed → dashboard lockout
**Where** `ApiKeyRow`, `Settings.jsx:555-576` (pre-fix). `save()` (`:145-149`) swallows its own PATCH error, so the caller cannot tell.
**Repro** Advanced → Dashboard API key. Route `PATCH /api/settings` to 500. Type a key, click **Save key**.
**Expected + why** A failed save must not change the client's credential — the server still holds the old key while `localStorage.jobnavigator_api_key` and the `jn_session` cookie hold the new one, so every subsequent request 401s and the login modal takes over (`api.js:20-27`).
**Actual** measured (`set_6.py`): calls `/settings` (500) then `/auth/set-session` regardless; flash reads **"Key saved"** in accent green (the real "Could not save — try again" is overwritten 40 ms later); `localStorage.jobnavigator_api_key = "ZZTEST-key-500"`.
**Proposed fix** `save()` returns a boolean; bail out before touching localStorage / the cookie.
**Status** fixed in source (rebuild pending) — `Settings.jsx:165-169`, `:590-594`

### SET-04 · P2 · "Reset to default" on a list editor saves a one-element list containing the seed's JSON text
**Where** `EditModal` reset handler `Settings.jsx:662-666` + `commit()` `:637`; `GET /settings/defaults` returns raw seed strings (`routes_settings.py:102`). Affects all 7 `list` rows: `body_exclusion_phrases`, `title_exclude_global`, `company_exclude_global`, `dedup_tracking_params`, `email_gmail_query_subjects` / `_senders` / `_exclusions`.
**Repro** Global exclude → Title exclude → Edit → **Reset to default**.
**Expected + why** The seed is `json.dumps([])` (`seed.py:28`), i.e. the *string* `"[]"`. `asList()` returns a string unchanged, so the textarea holds one line `[]` and `commit` splits it into `["[]"]`.
**Actual** intercepted PATCH `{"title_exclude_global":["[]"]}` and the row preview then reads `[]` (script `set_4.py`). For `dedup_tracking_params` the same path would replace ~80 params with one entry containing the whole JSON blob.
**Proposed fix** `JSON.parse` the default before formatting it when the row is `list` (or `json`).
**Status** fixed in source (rebuild pending) — `Settings.jsx:672-683`

### SET-05 · P2 · "Reset to default" wipes a prompt to `""` when `GET /settings/defaults` is unavailable
**Where** `Settings.jsx:122` swallows the `/settings/defaults` failure to `{}`; the reset handler then does `String(undefined ?? '')`.
**Repro** Route `GET /api/settings/defaults` to 500, then Scoring behavior → Scoring rubric → Edit → **Reset to default**.
**Actual** intercepted PATCH `{"scoring_rubric":""}` and an empty textarea (script `set_8.py`). Every one of the 19 editable prompts/lists is exposed. An empty `scoring_rubric` reaches `cv_scorer.py:279` with no guard.
**Proposed fix** Bail out with the existing error line when the key has no default.
**Status** fixed in source (rebuild pending) — `Settings.jsx:676`

### SET-06 · P2 · A failed `GET /settings` renders a permanently blank pane — no message, no retry
**Where** `Settings.jsx:130` (`console.error` only) → `S` stays `null` → `:347` returns a bare `<div>`.
**Repro** Route `GET /api/settings` to 500 (or abort it) and open `/v2/settings`.
**Actual** measured (`set_8.py`, `set_10.py`): no `<h1>`, 0 rail anchors, one empty `flex:1` div painted `--bg` (`rgb(252,251,247)`), zero text. Identical to the loading state, so a hung request and a hard failure are indistinguishable and both look like a hang forever. Screenshots `set-get500.png`, `set-loading.png`.
**Expected + why** Other v2 screens render an error state on a failed list load. The toast taxonomy's `error` kind (`Toast.jsx`, `TTL.error = null`) exists for exactly this and is not imported here at all (inventory §2).
**Actual, side-question from the brief** — *does a blur afterwards overwrite real values?* No: with `S === null` the component returns before rendering any control, so there is nothing to blur. The dangerous variant is SET-05 (settings load, defaults don't).
**Proposed fix** Keep an `err` state; render a short line plus a Retry that re-runs `load()`.
**Status** fixed in source (rebuild pending) — `Settings.jsx:129,145-150,377-393`: `load()` keeps a `loadErr`, and the `!S` early return now renders either a spinner + “Loading settings…” (request still in flight) or “Couldn’t load your settings · <detail> · Try again”, whose Retry clears the error and re-runs `load()`. The two states are no longer identical. `save()` additionally bails with a `bad` flash while `S` is null (`:171-173`), so no blur can PATCH a control’s placeholder over a stored value even if a future edit renders controls before the load lands.

### SET-07 · P3 · A failed webhook registration flashes in accent green, reading as success
**Where** `Settings.jsx:306-311` — `flash(...)` is called with no `bad` argument on the `ok === false` branch.
**Repro** `POST /telegram/register-webhook` returning `{"ok": false, "description": "Bad Request: bad webhook"}`.
**Actual** measured (`set_6.py`): text `"Bad Request: bad webhook"` in `rgb(63,107,82)` = `--accent`, i.e. the success colour. The local failure dicts additionally use the key `error`, not `description` (`notifier/telegram.py:82,85,102`), so a missing bot token or missing secret degrades to the generic "Registration failed".
**Proposed fix** Pass `bad = data?.ok === false`; fall back `description || error`.
**Status** fixed in source (rebuild pending) — `Settings.jsx:311-314`

### SET-08 · P3 · Optimistic state is never rolled back after a failed save
**Where** `Settings.jsx:146-148` — `setS` runs before the PATCH and the catch branch only flashes.
**Repro** Scoring behavior → Prompt caching. Route PATCH to 500, click the toggle.
**Actual** measured (`set_3.py`): flash "Could not save — try again" in `--bad` (correct), but the switch stays in its new position (`Off` → `On` after the failed save) and the help text swaps with it. The UI now disagrees with the server until a reload. Same for every Select, TextBox and the 6 override rows (whose `ovr` open/closed state is separate local state and would also need reverting).
**Proposed fix** Capture the previous value in `save()` and restore it in the catch; the `llm` override toggle needs its `ovr` entry reverted too, so this is more than a one-liner.
**Status** fixed (a4996a5): `save()` snapshots the prior value and restores it on failure (key deleted when it was absent); the override-off path re-opens the row if either PATCH fails. Verified: switch flipped against a 500 returns to its stored state.

### SET-09 · P4 · Two saves inside 2.2 s: the first flash's timer clears the second message early
**Where** `Settings.jsx:140-143` — each `flash()` pushes its own independent `setTimeout`.
**Repro** Toggle any switch, wait 1.5 s, toggle it again.
**Actual** measured (`set_4.py`): message present at t+1.8 s, **gone at t+2.4 s** — 0.9 s of visibility instead of 2.2 s. Guaranteed on every override-off, which fires two PATCHes (`:471`) and therefore two flashes back to back. This also masked SET-03's real error message during testing.
**Proposed fix** One `useRef` timer, cleared before each new one.
**Status** fixed in source (rebuild pending) — `Settings.jsx:155-162`

### SET-10 · P3 · "Submit PIN" has no catch — a 401/500/network error is an unhandled rejection with no feedback
**Where** `Settings.jsx:614-618` (pre-fix). The sibling `start()` (`:583-595`) does catch.
**Repro** LinkedIn → Session cookie in `awaiting_pin`, with `POST /linkedin/session/pin` failing.
**Actual** (read, not run — the live session is `stale`, phase `idle`, so the PIN box never rendered): `const { data } = await api.post(...)` throws, `data` is never read, the component logs an unhandled promise rejection and the button silently returns to idle.
**Proposed fix** Wrap in try/catch and flash the detail.
**Status** fixed in source (rebuild pending) — `Settings.jsx:625-631`. Runtime path listed under "Couldn't test".

### SET-11 · P3 · Four rows overflow their control column at 1024 px
**Where** `Settings.jsx:518` — the label column is a hard `flex: 0 0 340px`; the `inherits Primary` pill (`:466`) and the Override toggle (`:92`) are both `flex: 0 0 auto`.
**Repro** 1024×700, `/v2/settings`, Models section.
**Actual** measured (`set_8.py`): content column 522 px → label 340 px, controls **158 px**. `scrollWidth > clientWidth` on **Scoring, Tailoring, Cover letters, Autofill** (the four overrides that are OFF: pill 111 px + toggle 77 px + 8 px gap = 196 px). The page itself does not scroll horizontally (`body.scrollWidth === 1024`), so the toggle is simply clipped and cannot be reached. Row tops stay integer (0 fractional of 67). Screenshot `set-narrow.png`.
**Proposed fix** Make the label column `flex: 0 1 340px` (or stack the row below ~1150 px).
**Status** fixed (a4996a5): label column `flex: 0 1 340px`; a ResizeObserver on the scroll pane stacks label above controls under 720 px of pane (~1150 px window with the rail open). Verified: 0 clipped control rows at 1024×700.

### SET-12 · P3 · No keyboard operability, no labels, no ARIA
**Where** every control is a `span`/`div` with `onClick` — `Select :44-50`, `Toggle :90-98`, Edit pill `:485`, `ActionBtn :545`, info "i" `:522`, show/hide `:82,:565`, rail anchors `:380`, modal ✕/Done/Reset/Add.
**Actual** measured (`set_11.py`): inside the content pane there are **128 elements with `cursor:pointer`**, but only **25 focusable inputs**, **2 links**, **0 `<label>`**, **0 `aria-*`**. Tabbing from the top reaches the 10 rail links, then the search box, then the raw `<input>`s; the 15 anchors, all 7 Selects, all 10 toggles, all 19 Edit pills and all 7 action buttons are unreachable. No input has an `id`/`for` association, so a screen reader announces an unlabelled text box.
**Proposed fix** `role="button"` + `tabIndex={0}` + Enter/Space on the shared primitives (`Select`, `Toggle`, `ActionBtn`, the Edit pill), and `aria-label` from `r.label` on each row's control.
**Status** fixed (a4996a5): `kb()` helper on every primitive — Toggle is `role=switch` + `aria-checked`, Select is `aria-haspopup=listbox` + `aria-expanded` with `role=option` rows, anchors `role=link`, all controls carry `aria-label` from the row label. Verified: 75 focusable / 10 switches / 99 labelled controls.

### SET-13 · P3 · `--edge` body text falls below 4.5:1 in both themes
**Where** colophon links `Settings.jsx:414-417` (11 px `--edge` on `--bg`); catalog "seeded" tag `:748` and provider column `:746` (10 px `--edge` on `--surface`).
**Actual** measured contrast (`set_8.py`): light `--edge #8a826e` on `--bg #fcfbf7` = **3.69:1**, on `--surface #ffffff` = 3.82:1. Dark `#7f7a66` on `#1e1c17` = **3.95:1**, on `#28251b` = 3.56:1. All below the 4.5:1 needed at these sizes. Everything else measured clean: `--text-2` 7.66 / 9.09, `--muted` 5.52 / 6.17 on `--surface`, 5.02 / 5.40 on `--surface-2`, `--accent` 6.11 / 7.11, `--bad` 6.58 / 6.39, `--warn` 5.38 / 6.59, `--accent-ink` on `--accent` 6.11 / 8.55.
**Expected + why** The design uses `#8a826e` for the same elements, so this is inherited, not introduced — but it is the only sub-AA text on the screen.
**Status** fixed (a4996a5): colophon links and the catalog provider column + seeded/added tag use `--muted` instead of `--edge`. Verified: colophon link colour rgb(109,104,98) = `--muted`.

### SET-14 · P3 · Dark mode: the toggle knob is white on the light-green accent — 2.16:1
**Where** `Toggle` `Settings.jsx:95` uses `var(--knob)`, which `theme.css:34` defines once (`#ffffff`) with **no dark override** (HANDOVER already flags `--knob` as single-definition).
**Actual** measured (`set_8.py`): dark ON state = `--knob #ffffff` on `--accent #8dbb9f` → **2.16:1**; the knob is nearly invisible against the track. In light the ON state is 6.11:1 and only the OFF state is low (1.76:1 on `--line-strong`, which matches the design exactly). Ten switches on this screen (4 `SW` + 6 override toggles).
**Proposed fix** Give `--knob` a dark value (`--surface` / `#28251b`), or use `--accent-ink` for the knob when the switch is on.
**Status** fixed (a4996a5): ON knob uses `--surface-2` (user's pick, 2026-09-03), OFF keeps `--knob`. Verified: light ON knob rgb(246,244,238), dark ON knob rgb(50,47,36) = `--surface-2` in each theme.

### SET-15 · P3 · Model-catalog `×` hover changes colour only; the design changes the border too
**Where** `Settings.jsx:749-750` uses `.v2-hover-bad-text` (`theme.css:175`, `color` only). Design `Settings Ops.dc.html:184`: `style-hover="border-color:#9c3b30;color:#9c3b30"`.
**Actual** measured (`set_9.py`): `color` `rgb(138,130,110)` → `rgb(156,59,48)`; `borderColor` stays `rgb(226,221,208)`.
**Proposed fix** A `.v2-hover-bad-bdc` rule (border + colour); adding `border-color` to the existing class would change the `×` on other screens too.
**Status** fixed (a4996a5): `.v2-hover-bad-bdc:hover` (border + glyph → `--bad`) in theme.css, used only on the catalog ×. Verified: hover changes borderColor and color.

### SET-16 · P3 · Catalog typeahead is a plain inline list, not the design's dropdown
**Where** `ModelsModal` `Settings.jsx:737-743` vs design `:166-175`.
**Actual** measured (`set_9.py`, term `deep`, OpenRouter live catalog of 421): 8 suggestion rows render as `.v2-menuitem`s *inside the scroll area above the 44 catalog rows*. Missing versus the design: the absolutely-positioned dropdown anchored to the field, the first row pre-highlighted with `↵ to add` (`cat_has_enter_hint = false`), `<b>`-bolded matched substrings (`cat_sugg_bold = false`), and the footer `"4 of 324 match · or paste any slug and Add"` (`cat_has_match_footer = false`). Enter-to-add itself does work (`:727`). Screenshot `set-catalog.png`.
**Status** fixed (a4996a5): design dropdown anchored under the search field — first row pre-highlighted with `↵ to add`, ↑/↓ wrap, Enter adds, Escape closes, matches bolded, footer `N of M match · or paste any slug and Add`. Verified live. Note: M is the total match count, not the 8 rows shown.

### SET-17 · P3 · Catalog offers `×` on seeded models; the design restricts removal to your own additions
**Where** `Settings.jsx:749` renders `×` unconditionally. Design `:466`: `delDisplay: custom ? "flex" : "none"`.
**Actual** measured (`set_5.py`): 44 rows, **44 `×` buttons**, and removing a seeded row PATCHes the filtered list (the removal then persists through `seed.py:638-667` via `llm_seeded_models`).
**Expected + why** The code behaviour is arguably better — a stale seeded model is exactly what you want to delete, and the tooltip says "Remove — removal persists". But it contradicts the design, and the "seeded" tag implies immutability.
**Status** decided keep current (user 2026-09-02): seeded models stay removable.

### SET-18 · P3 · Advanced is missing the design's H-1B refresh and Job cleanup triggers
**Where** design `:441-442` — `BT("h1b", "H-1B data", "Re-import the sponsorship dataset.", "Refresh now")` and `BT("cleanup", "Job cleanup", "Purge expired postings now.", "Run cleanup")`. `Settings.jsx:333-337` has only Proxy URL, Dashboard API key and DB backup.
**Expected + why** Both endpoints exist (`main.py` `/h1b/refresh`, `/db/cleanup`) and v1's Settings exposes them; v2 Settings drops them, and v2 has no other manual-trigger surface (inventory §8: "v1 additionally exposes scrape/email/h1b/cleanup/digest/backfill triggers that v2 Settings does not").
**Status** decided keep current (user 2026-09-02): Stats › Run history is the home for the H-1B refresh and cleanup triggers.

### SET-19 · P4 · Two section headers rendered with no subtitle
**Where** `Settings.jsx:289` (`dedup`) and `:333` (`advanced`) passed `""`, while the design supplies "same job from two sources isn't saved twice" (`:405`) and "escape hatches — most days none of this gets touched" (`:437`).
**Actual** measured (`set_11.py`): `sec-dedup.sub = ""`, `sec-advanced.sub = ""`; the other 13 all have one.
**Status** fixed in source (rebuild pending) — `Settings.jsx:299,343`

### SET-20 · P4 · Every numeric/cron box is 135 px against the design's 170 px; four Selects are 260 px against 340 px
**Where** design `:331,:359,:374,:385-394,:411-412` all use `w: "170px"`; `:332,:334,:349,:370` use `w: "340px"`.
**Actual** measured (`set_1.py`): 15 mono boxes at **135 px** (Max parallel jobs, Max parallel tailors, Default answer length, Confidence threshold, Chat ID, Score threshold, the 4 scheduler intervals/day counts and the 5 crons); Default depth / On save action / Auto-score after tailoring / Include by default all at **260 px**. The 135 px cron boxes fit `0 4 * * *` but ellipsis anything longer; "Full — score + keywords + report" is close to the edge at 260 px.
**Status** decided keep current (user 2026-09-02): 135/260 px widths stay.

### SET-21 · P4 · The Edit modal is 1020 px wide against the design's 680
**Where** `Settings.jsx:649,658` — `min(1020px, 94vw)` / `min(1280px, 92vh)` and `minHeight: 440` on the textarea. Design `:138,:145`: 680 × 640 with a 220 px text area.
**Actual** measured (`set_4.py`): panel **1020 × 583**, textarea **974 × 440**. An in-code comment ("1.5x wider and 2x taller than before") says this was intentional.
**Status** decided keep current (user 2026-09-02): 1020 px Edit modal stays.

### SET-22 · P4 · The webhook-secret preview isn't in a box
**Where** `Settings.jsx:503` renders `r.preview` as a bare mono 10.5 px span, `flex: 1` (measured 497 px). Design `:414-416` renders it as a bordered 260 px BOX with muted text, like every other value on the screen.
**Actual** measured (`set_1.py`): the `Webhook secret` control row is `[497, 69]` (span + Rotate button) versus the neighbouring `Chat ID` row's `[135]` box. The text itself is correct in all three states — "Set (hidden — rotate to view)" / "Set" / "Not set" (verified in `set_6.py` and `set_10.py`).
**Status** fixed (a4996a5): webhook preview renders in the standard bordered box at `flex: 0 1 260px`, mono 11.5 px `--muted`, Rotate beside it. Verified: 260 px wide, 1 px border.

### SET-23 · P4 · An empty model catalog opens a 12 px empty popover
**Where** `Select` `Settings.jsx:51-60` renders the menu chrome even with zero options.
**Actual** measured (`set_10.py`, `llm_models_list: []`): the summary reads "0 models · 0 seeded · 0 added by you", the model picker shows "pick model…" (correct), and clicking it opens a **260 × 12 px** bordered box with nothing in it.
**Proposed fix** Render a muted "no models for this provider — add one under Model catalog" row instead of an empty menu.
**Status** fixed (a4996a5): zero-option Select renders one muted row ("no models for this provider — add one under Model catalog", overridable via `emptyText`). Verified with an empty `llm_models_list`.

### SET-24 · P4 · Section subtitles and two row labels drifted from the design
**Where / Actual** measured (`set_11.py`) — the `models`, `tailoring`, `letters`, `emailclass` and `scheduler` subtitles are all rewritten; `"Prep handover template"` → `"What I need from you" section`; `"Auto-reject after"` → `"Auto-reject threshold"`; `Auto-reject · cron` moved from last to 5th in Scheduler. Full list in the design re-diff table above. Several of the code's strings are *more* accurate than the design's: the design calls the Postgres backup a "Nightly SQLite snapshot" (`:390`) and its `URL style` options (`Short — /l, /gh`) describe a scheme the backend never had (`:423`).
**Status** decided keep current text (user 2026-09-02).

### SET-25 · P4 · The Edit modal drops keystrokes typed within 600 ms of closing
**Where** `Settings.jsx:632` clears the pending debounce timer on unmount; Done / ✕ / scrim (`:648,:653,:667`) all just call `onClose` without flushing.
**Repro** Body phrases → Edit → type a line → click **Done** immediately.
**Actual** measured (`set_4.py`): typed `\nZZDROPPED`, clicked Done 150 ms later, waited 1.2 s → **zero PATCHes**. The footer says "Saves automatically as you type", so the loss is silent.
**Proposed fix** Flush the pending commit in `onClose` (or on the Done click) before unmounting.
**Status** fixed (a4996a5): `commit()` records the owed value, `close()` flushes it before `onClose` (Done, ✕, scrim, Escape); unmount flushes as a backstop. Verified: a value typed 100 ms before Done is PATCHed.

### SET-26 · P4 · A leftover scratch résumé `ZZTEST Base A` is in the Default-résumé dropdown
**Where** `GET /resumes?is_base=true` — not created by this run.
**Actual** measured (`set_9.py`): options `(all bases + Persona) · Persona · ZZTEST Base A · PM · TPgM · PjM · PjM FinTech`. Left behind by an earlier Stage-3 script (Résumés screen). Flagged, not deleted — the data rules say only delete rows you created.
**Status** closed: no `ZZTEST` base résumé remains (verified via `GET /api/resumes` 2026-09-03); the dropdown is clean.

### SET-27 · P3 · PATCH `warnings` are discarded, so a scheduler / semaphore / dedup-reload failure is invisible
**Where** `Settings.jsx:147` ignores the response body; `routes_settings.py:57-92` returns `{"updated": [...], "warnings": [...]}` and appends one entry per failed side effect.
**Repro** Set `scrape_interval_minutes` to `abc` — `configure_scheduler()` raises inside `int()` (`scheduler.py:29`), the PATCH returns 200 with `warnings: ["configure_scheduler failed: ..."]`, the screen flashes a green "Saved" and the bad value stays in the box.
**Expected + why** The scheduler is then not reconfigured, and the same unguarded `int()` runs at boot (`main.py:52` → `scheduler.py:29-30`), so the backend fails to start until the row is fixed by SQL. None of the 9 numeric boxes or 5 cron boxes has any client-side validation (`type="number"`, `inputMode`, or a cron pattern) — matrix finding (d), 17 soft type mismatches.
**Actual** the green "Saved" flash and the warnings-blind save path were both confirmed by intercept (`set_2.py`, `set_3.py`). The `abc` case itself was **not** written to the live DB (it would risk the user's backend boot) — read from `routes_settings.py:63-67` and `scheduler.py:29`.
**Proposed fix** Flash `warnings[0]` as `bad` when the array is non-empty; add `inputMode="numeric"` plus a digit filter to the 9 int rows.
**Status** fixed (a4996a5): `save()` flashes `warnings[0]` in `--bad` instead of the green Saved; 9 integer rows are `inputMode=numeric` with a digit-only filter (Chat ID deliberately excluded — group ids are negative); 5 cron rows refuse a non-empty value without exactly 5 fields ("Cron needs 5 fields") and never PATCH. Verified all three.

---

## Verified working (no finding)

Measured, all as specified — full data in the scripts.

- **Structure** — 15 sections / 15 rail anchors / 4 group labels; **67 rows** rendered with `llm_provider = claude_code` (keyless → API-key row hidden) and **68** with `openai` (`set_10.py`). Matches the inventory's 68/67 counts exactly.
- **Geometry vs design** (`set_11.py`) — row `min-height 52 / padding 9px 0 / gap 24`, label column **340 px**, label 13 px on an 18 px line, help 11 px on 16 px, section header `26px 0 4px` with a 19 px title and 11.5 px sub both on 26 px, box 32 px / 12.5 px, Edit pill 26 px / 11.5 px, ActionBtn 30 px / 12 px, info circle 15×15, toggle track 26×15, header 92 px with `22px 30px 16px`, search pill 230×30, `<h1>` 30 px on line-height 1, rail 216 px, anchor 29 px with `0 26px 0 30px`, Select menu 260 px wide with `max-height 320` and `z-index 40`. Every one matches the design's number.
- **`assert_int_tops`** — 0 fractional row tops out of 67 at the top of the page, 67 after scrolling to the bottom, 67 at 1024×700, 67 with 400-character values, and 0 of 44 in the catalog modal.
- **Save mechanics** — a TextBox blur with no change sends **nothing**; a changed blur sends exactly one PATCH (`{"proxy_url":"socks5://zztest.invalid:9"}`), round-trips to the server, and was restored to `""`. Select saves immediately on pick (`{"tracer_links_url_style":"path"}`). Toggle saves the string `'true'`/`'false'`, swaps to `offHelp`, moves the knob 2 px → 13 px and flips the track `--line-strong` → `--accent`. Edit-modal debounce measured: no PATCH at 300 ms, exactly one by 900 ms.
- **Error paths** — PATCH 500 → flash "Could not save — try again" in `--bad` `rgb(156,59,48)`. PATCH 401 → the same flash **plus** the global login modal (`api.js:20-27` dispatches `jn:unauthorized`); expected, not a defect.
- **Redacted secrets on save** — blurring a masked box untouched sends nothing, so the mask never overwrites the stored secret. (The SET-01 path is the one that does.)
- **Prompt-editor Reset** — `prep_ask` reset sent the full 644-character seed string correctly; only `list` rows are broken (SET-04).
- **JSON editor** — invalid JSON gives a `--bad` textarea border, the footer "Not valid JSON — nothing saved yet" in `--bad`, and **no PATCH**. Scrim click closes.
- **Model catalog** — modal is exactly 600×620; a live `GET /llm/models?provider=openrouter` returned 421 models; placeholder "Search 421 live models, or paste any slug…"; Add PATCHes the whole list plus `{provider, model, label:"… (custom)", custom:true}`; remove PATCHes the filtered list. All intercepted — `llm_models_list` md5 unchanged.
- **Manual triggers** — `POST /db/backup`, `/telegram/rotate-webhook-secret` (with its `window.confirm` + `window.prompt` + `load()`), and `/telegram/register-webhook` (with its URL prompt, body `{"public_url": …}`) each fire the right call and show `Done ✓` with an accent border/fill for 2.6 s, then reset. **`POST /telegram/test` was fired once for real** and returned `Done ✓`. Backup, rotate and register-webhook were intercepted, never fired.
- **LinkedIn panel** — `GET /linkedin/session` renders "Last refreshed 49d ago — likely expired." in `--warn` `rgb(154,91,40)` for `status: stale`; **Refresh cookie** POSTs `/linkedin/session/refresh`; a 409 flashes `already running` in `--bad`. LinkedIn itself was never contacted.
- **API-key control** — the input is `type="password"`, never echoes the stored value, its placeholder switches on `isSet` ("Set — type a new key to replace it" / "No key — the dashboard is open"), show/hide flips it to `type="text"`, an empty save flashes "Type the new key first" in `--bad` with no request, and a successful save PATCHes `{"dashboard_api_key": …}` then `POST /auth/set-session {"api_key": …}` and writes `localStorage.jobnavigator_api_key`. `dashboard_api_key` was never changed (md5 identical before and after).
- **Search** — "telegram" matches Scheduler + Notifications and renders **all 15** of their rows (per-section, not per-row, as documented); the rail highlight is suppressed while a query is active; "zzznothing" gives `No settings match "zzznothing".` with the colophon still rendered; `jump()` clears the query.
- **Anchor rail** — a click scrolls the section to the top of the scroller and sets the accent `border-left` plus `font-weight 600`; manual scrolling does **not** move the highlight (no scroll-spy — documented, not a defect).
- **Info panels** — the "i" flips to an `--accent` border, `--accent-soft` fill and `--accent` glyph; the panel renders on `--surface-2` in `--text-2` at 11 px; only one is open at a time.
- **Override rows** — turning an override off sends exactly two PATCHes (`{"email_llm_provider":""}` then `{"email_llm_model":""}`) and never touches `*_api_key`; the "inherits Primary" pill appears on `--surface-2` at 9.5 px; turning it back on restores all three controls.
- **Selects / orphan values** — the open state borders `--accent`; the selected option is `--accent` on `--accent-soft`; a `cover_letter_default_voice` id missing from the presets appends "`<id>` — not in presets" (verified with both a bogus id and an empty preset list); an unknown `prep_include` combo, a deleted `default_resume_id` and an unknown `tailor_auto_quick_score` all fall back to "Select…"; an empty `scoring_default_depth` correctly falls back to the row's `dflt`.
- **Empty / unset states** — an empty list preview renders `—`; an unset webhook secret renders "Not set"; 400-character values ellipsis inside their box with no row or body overflow.
- **Colophon** — `/docs` and `https://github.com/vesaias/JobNavigator`, both `target="_blank" rel="noopener noreferrer"`, both hovering `--edge` → `--accent` via `.v2-hover-accent-text`.
- **Hovers** — Edit pill `--edge` → `--accent` on border **and** colour; ActionBtn border only; catalog `×` colour only (SET-15). No hover on rows, toggles, the info icon, show/hide links, text boxes or select boxes — exactly what the design declares. No extra hovers.
- **Themes** — every measured colour differs between light and dark (h1, status line, search box, rail border, anchors on/off, section title/sub, row border, label, help, box border/bg/fg, Edit pill, ActionBtn, previews, colophon, modal scrim/panel/textarea/footer/Done). No light-only value survives except `--knob` (SET-14) and the modal `box-shadow` `rgba(0,0,0,.28)` — a known cross-screen gap (HANDOVER: the five `--shadow-*` tokens have no dark variants). Screenshots `set-light.png`, `set-dark.png`, `set-light-modal.png`, `set-dark-modal.png`.
- **Console** — clean on load, on every interaction, in both themes and at 1024×700: 0 console errors, 0 page errors, 0 failed requests, 0 4xx/5xx apart from the ones deliberately injected.
- **Deep links** — `/v2/settings?job=999&foo=bar#sec-linkedin` renders normally (15 anchors, `active = Models`, `scrollTop 0`); unknown params and the hash are ignored without error. The route takes no params.
- **localStorage** — this screen writes only `jobnavigator_api_key`; nothing else is added.

### Already fixed elsewhere in this session (verified dead in the shipped bundle, not re-logged)

- `.v2-anchor:hover` (rail anchor → `--text`) and `.v2-menuitem:hover` (Select options and catalog suggestions → `--surface-2`) measure **no change** in bundle `index-Dnrx3n0f.js`; both now carry `!important` in `theme.css:149,168` from commit `5c6c17a` ("harden menu/anchor/navlink hovers"). Rebuild pending.
- `.v2-hover-accent` (modal ✕) still changes background only, not colour, in the shipped bundle — the source fix flagged in my brief. Not re-logged.

### SET-28 · P4 · POST /settings accepts an unknown key (no allow-list)
**Where** `backend/api/routes_settings.py:51-54` (filed from the stage-4 round-trip observation by the R1 audit)
**Actual** the UI cannot produce one, but the API writes any key it is handed.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

## Fixed in source

- `frontend/src/v2/Settings.jsx:66-100` — `TextBox`: an unset secret no longer renders the mask, show/hide is hidden when there is nothing to show, revealing clears the mask instead of leaving it editable, and `commit()` refuses to save a bare mask or to wipe a stored secret with an empty box (SET-01, SET-02).
- `frontend/src/v2/Settings.jsx:131,155-162` — a single `flashTimer` ref, so back-to-back flashes each get their full 2.2 s (SET-09).
- `frontend/src/v2/Settings.jsx:165-169` — `save()` returns whether the PATCH landed.
- `frontend/src/v2/Settings.jsx:590-594` — `ApiKeyRow` bails out before writing `localStorage` / refreshing the cookie when the PATCH failed (SET-03).
- `frontend/src/v2/Settings.jsx:311-314` — register-webhook failures flash as `bad` and fall back to `data.error` (SET-07).
- `frontend/src/v2/Settings.jsx:299,343` — `dedup` and `advanced` section subtitles restored from the design (SET-19).
- `frontend/src/v2/Settings.jsx:672-683` — `EditModal` reset parses a JSON seed string for `list`/`json` rows, and refuses to reset at all when the key has no default (SET-04, SET-05).
- `frontend/src/v2/Settings.jsx:625-631` — `Submit PIN` wrapped in try/catch (SET-10).

All eight are **rebuild pending** — the frontend is a static Docker bundle and I did not rebuild it (shared stack). The file parses clean (`esbuild --loader:.jsx=jsx`, 54.2 kB, no errors). No backend file was touched, so no restart is needed.

## Couldn't test

- **`awaiting_pin` PIN entry** (`Settings.jsx:608-620`) — the live LinkedIn session is `status: stale`, `phase: idle`, so the PIN input and its Submit button never render, and driving a real refresh is out of scope (no LinkedIn contact). SET-10 comes from reading the code; the fix is unverified at runtime.
- **The 2.5 s `GET /linkedin/session` poll** (`:587-593`) — same reason: the poll only starts after a refresh that reaches `running`.
- **Non-numeric interval → backend boot failure** (SET-27) — writing `abc` into `scrape_interval_minutes` would leave the user's backend unable to start (`main.py:52` → `scheduler.py:29`, unguarded `int()`). Verified by reading only.
- **A real key rotation** — `POST /telegram/rotate-webhook-secret` and a real `dashboard_api_key` change were intercepted; both would have invalidated live credentials. `md5` of both rows was confirmed identical before and after.
- **Fresh-install counts** (inventory §8: "45 models · 45 seeded · 0 added by you", a 78-key `/settings/defaults`) — the live DB holds 44 catalog entries and 86 settings rows including 8 runtime/legacy keys. Empty-DB rendering is a separate later pass.
- **Live catalog error paths for OpenAI / Claude** (`routes_llm.py:117` 400 when no key, `:135-143` 502) — `llm_api_key` is empty on this install and firing a real provider call to prove a 400 was not worth a request. The OpenRouter path (no key needed) was exercised and returned 421 models.

## Scratch data

- Created: **none**. Every mutation was either interception-only or a single-field edit restored in the same script.
- `proxy_url` — `""` → `socks5://zztest.invalid:9` → `""` (restored; verified by `GET /settings` and by `select value from settings`).
- `POST /telegram/test` fired once for real (permitted by the brief); no rows written.
- Verified unchanged after the run: `jobright_password` (15 chars, plaintext identical), `dashboard_api_key`, `telegram_webhook_secret`, `llm_models_list` (all three by `md5(value)` before/after), `prompt_caching_enabled = true`, `tracer_links_url_style = param_jobid`, `telegram_enabled = true`, `title_exclude_global` (84 entries), `prep_ask`.
- **Scratch rows remaining: 0** created by this pass. One pre-existing scratch row — résumé **`ZZTEST Base A`** — was found in the Default-résumé dropdown; not created here, left in place, logged as SET-26.

## Summary

- **Inventory boxes: 207.** Verified OK **168**, failed **33**, untestable **6** (the LinkedIn `awaiting_pin` PIN box + Submit, the 2.5 s session poll, the two fresh-install counts, the catalog's live 400/502 error line, and the non-numeric-interval boot failure). Ticks are written back into `v2-testing/inventory/v2-settings.md` as `[x]` / `[!]` + finding id / `[~]` + reason.
- **Findings: 27** — **2 P1** (secret-mask corruption SET-01, API-key lockout SET-03), **4 P2** (SET-02, SET-04, SET-05, SET-06), **13 P3**, **8 P4**.
- **Fixes applied: 8**, all in `frontend/src/v2/Settings.jsx`, all rebuild-pending, file parse-verified. **0 backend edits, 0 restarts needed.**
- **Design re-diff: done** (the required deliverable, table above). 15/15 sections match; 64 design rows against 68 built; **2 design rows never built** (H-1B refresh, Job cleanup — SET-18), **1 row built that the design predates** (Max parallel tailors), **2 subtitles missing** (now fixed), **21 rows differing in width**, **2 rows renamed**, **1 reordered**, and 5 section subtitles rewritten. The catalog modal diverges most (typeahead shape, seeded-row deletion, `×` hover). Several design strings are simply stale — it still calls the Postgres backup "SQLite" and offers a tracer URL scheme the backend never had.
- **Geometry: exact.** Every number the design specifies was measured and matches. Zero fractional row tops in four render conditions.
- **Console: clean** in both themes, at both viewports, across every interaction.

---

## P2 triage (2026-09-02)

Triage of the open P2 findings assigned to this pass (SET-06 only; SET-02, SET-04 and SET-05 were not in scope). Frontend edit, so **rebuild pending**; no backend change, no restart.

| id | action | note |
|---|---|---|
| SET-06 | fixed (JSX) | `loadErr` state; the `!S` early return renders a spinner + “Loading settings…” while the GET is in flight and “Couldn’t load your settings · Try again” on failure, so a hang and a hard failure are now distinguishable; `save()` also refuses to PATCH while `S` is null |

Files touched: `frontend/src/v2/Settings.jsx`. Brace / paren / backtick balance checked against `git show HEAD:frontend/src/v2/Settings.jsx` — unchanged (all zero).
