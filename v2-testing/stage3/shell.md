# Stage 3 — Shell (rail, health line, theme/collapse, toasts, Login + Welcome overlays)
Tested: 2026-09-02, bundle index-Dnrx3n0f.js (HEAD 9ed8963), themes light+dark, viewport 1440×900
Design: `Nav Rail.dc.html`, `Toasts.dc.html`, `System Overlays.dc.html` (panels 1+2)   Code: `V2App.jsx`, `Toast.jsx`, `ToastLab.jsx`, `LoginModal.jsx`, `WelcomeModal.jsx`, `App.jsx`   Scripts: `shell_1.py`, `shell_2.py` (results `artifacts/shell_*.json`, shots `shell_rail_*`, `shell_toastlab_*`, `shell_welcome_*`, `shell_login_dark`)

## Verified OK (measured)
- Rail 206 px expanded / 50 px collapsed; header 64; group header 18 (10 px, .16em); item 34 (14 px); count 11 px JetBrains Mono; health row 30 (11.5 px / 18 px lh); footer 34 with 1 px `--rail-line` top; padX 20 → 11/13 collapsed so the 15 px icon centres at x=25; JN mark, divider ticks (16 px), chevron and mini ◐ all centre at x=25. Zero fractional tops on nav items (both themes).
- Rail counts = API: Jobs 9 (`/jobs?status=new` total), Searches 6, Companies 126, Applications 377, Résumés 4 (`is_base=true`), Cover Letters 16. Collapsed tooltips "Jobs · 9" … "Companies · 126 · needs attention". Amber dot on Companies when collapsed (warn from `/health/entities`).
- Health line "1 source needs attention" + amber 7 px dot (design: amber when a source needs attention); click → `/v2/stats`.
- Active item: 2 px `--rail-accent` left bar, `--rail-active` wash, ink text, accent count.
- Theme toggle (footer ◐ and the collapsed ◐ in the status slot) flips `data-theme` + `jobnavigator_dark_mode`; collapse persists via `jobnavigator_v2_rail` across reload; "← Classic UI" lands on `/` with the classic `html.dark` in sync.
- Toasts (lab): all four kinds match the design tokens exactly in both themes (bg/border/ink, 16 px roundel, 9 px radius, 10×13 padding, 380 max, `--shadow-toast`, 16 px from the corner). Progress gone by 3.2 s, error still present at 7.2 s, cap of 3 with newest at the bottom, Undo/✕ close, Clear empties.
- Login: no key → modal; 360 px card on `--recessed` with `--line` border and `--shadow-modal`, scrim `rgba(20,19,15,.42)`, 36 px input box on `--edge`, 38 px accent button, placeholder `jn_live_…`, show/hide toggles input type, wrong key → "Invalid API key" + `--bad` border, right key → "Signed in · Loading dashboard…" → reload → welcome. Dark variant themed. A mid-session 401 (intercepted `/api/searches`) raises the modal.
- Welcome: 420 px card, header 22/24/6 padding, 21 px Newsreader, steps 22 px mono numerals on `--surface-2`, footer CTA 30 px accent pill; step click navigates (`/v2/companies`) and clears `jn:welcome`; scrim click, ✕ and CTA all close; from the classic shell the steps route to classic paths (`/resumes`); dark variant themed.

## Findings
### SHELL-01 · P3 · Every rail hover is dead (inline colour beats `.v2-navdark:hover`)
**Where** `frontend/src/v2/theme.css:136`, `V2App.jsx` nav items / Collapse / chevron / ◐ / ← Classic UI; route any `/v2/*`
**Repro** Hover an inactive nav item, the Collapse label, the chevron, the ◐ button or ← Classic UI.
**Expected + why** `Nav Rail.dc.html` sets `style-hover="color:#f6f3ea"` on items, chevron, Collapse and both ◐ buttons, and `background:rgba(255,255,255,.06)` on the footer ◐. HANDOVER: "any hover overriding an inline colour needs `!important` or it silently does nothing".
**Actual** `hover_delta` on all five: `changed: []` in both themes (colour stays `rgb(168,163,150)` / `rgb(148,141,122)`).
**Proposed fix** `.v2-navdark:hover { color: var(--rail-ink) !important }`, new `--rail-hover: rgba(255,255,255,.06)` + `.v2-themebtn:hover { background: var(--rail-hover) !important }` on the footer ◐.
**Status** fixed in source (rebuild pending) — `theme.css:31,136-137`, `V2App.jsx` footer ◐ gets `v2-themebtn`.

### SHELL-02 · P3 · Theme toggle is two-state; design cycles Light → Dark → System
**Where** `V2App.jsx:56` (`toggleTheme`), footer ◐ and collapsed ◐
**Expected + why** Nav Rail spec: "◐ … cycles Light → Dark → System (tooltip names the current mode)", icons ◐/◑/◒, tooltip "Theme: Dark — click to switch". HANDOVER lists the System option as outstanding theming work.
**Actual** Boolean flip, icon always ◐, tooltip "Switch to dark mode"; four components each read `jobnavigator_dark_mode` independently (`V2App`, `ToastLab`, `LoginModal`, `WelcomeModal`).
**Proposed fix** One theme store (`light|dark|system`) + `prefers-color-scheme` listener + no-flash boot script; out of scope for a contained fix.
**Status** decided keep current (user 2026-09-03): two-state toggle stays; the System mode waits for the theming groundwork.

### SHELL-03 · P4 · Welcome step rows land on half pixels
**Where** `WelcomeModal.jsx:56` (desc `lineHeight: 1.5` at 11.5 px = 17.25 px)
**Actual** Step tops 310.125 / 390.625 / 471.125 / 534.375, row height 72.5.
**Expected + why** HANDOVER convention: integer line-heights so rows never land on x.5 (no borders here, so cosmetic only).
**Status** fixed in source (rebuild pending): `lineHeight: '17px'`.

### SHELL-04 · P4 · Unauthored hovers on the Welcome modal
**Where** `WelcomeModal.jsx:52` (`.v2-welcomestep:hover` → `--surface-2`), `:43` (✕ uses `.v2-hover-accent-text` → accent)
**Expected + why** `System Overlays.dc.html` panel 2: steps have no `style-hover`; ✕ hovers to `#1b1a16` (`--text`), not the accent. The code comment says the step hover is deliberate ("v1 made each one a link").
**Actual** Step bg → `rgb(246,244,238)`; ✕ → `rgb(63,107,82)`.
**Status** decided keep current (user 2026-09-03): consistency with the app's link affordance.

### SHELL-05 · P4 · Rail values that differ from the Nav Rail board
**Where** `theme.css:60,117`, `V2App.jsx:71`
**Actual vs design** width transition `.32s` vs 220 ms; group-label / count / footer dim `#948d7a` (light) / `#8a8371` (dark) vs `#66604f`; health dot `--rail-accent #8dbb9f` vs `#7fae8f`; rail bg in dark `#100f0b` vs the board's "rail stays dark in both themes — it's the app's constant" (`#22211c`); collapsed warn dot at left 31 / top 8 vs `left:34`.
**Status** needs decision: these look like deliberate consistency/contrast changes (`#66604f` on `#22211c` is ~2.6:1) — confirm, then I'll mark them as accepted.

### SHELL-06 · P4 · `App.jsx` and V2App keep separate copies of the theme flag
**Where** `App.jsx:105-116` (sets `html.dark` from its own state), `V2App.jsx:52`
**Actual** Toggling in v2 updates localStorage + `data-theme` but `html.dark` only follows on the next full load (`after_toggle.html_dark` stayed `false`). Harmless today because "← Classic UI" is a full navigation; becomes a bug the moment the two shells share a route transition.
**Status** decided keep current (user 2026-09-03, folded into SHELL-02): harmless while "← Classic UI" is a full navigation.

## Fixed in source
- `theme.css:31` — `--rail-hover` token; `theme.css:136-137` — `!important` on `.v2-navdark:hover`, new `.v2-themebtn:hover`
- `V2App.jsx` footer ◐ — `className="v2-navdark v2-themebtn"`
- `WelcomeModal.jsx:56` — desc line-height 17 px

## Couldn't test
- Retry action on error toasts at real failure sites (design: "carries Retry when retryable") — per-screen agents check their own failure sites.
- Rail with zero counts / no health history — Stage 3b (empty DB).

## Scratch data
- none created

## Follow-up round (2026-09-03)
User requests outside the numbered findings, all in `9e03e5b` and measured on the rebuilt bundle:
- **Late Applications count** — the rail fetched the whole application list (200 rows) to count it, landing ~0.5 s after the others. Now `GET /applications?limit=1` + `total`; measured: all six count responses arrive within 118–191 ms of navigation, applications at 186 ms alongside companies. The count slot reserves 18 px until the value lands so labels never shift; no `0` placeholder.
- **Stronger active accent** — rail active item and Settings section anchors `2 px → 3 px` left bar, padding −1 px so text stays put. Measured: rail `3px rgb(141,187,159)` padL 19; Settings anchor `3px` padL 29. The only other 2 px left bar in v2 is the Applications email-quote bar (not an indicator) — left alone.
- **Health dot** — aggregates companies + searches needing attention from `/health/entities`, plus the last `scrape_all` outcome. Tooltip now says so: measured "1 company and 0 searches need attention. Click → Stats · Run history."
