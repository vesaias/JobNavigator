# v2 redesign — handover

State as of 2026-09-01. Branch `v2-redesign`, **pushed** to
`github.com/vesaias/JobNavigator` at `559b62a`, 196 commits ahead of `main`.
No PR is open. `main` is untouched.

**The repo is public.** Anything committed is published irreversibly. Scan for
secrets and personal data before any push — `.env` is untracked and must stay so.

## Where it stands

All nine screens are built and live in the rail (`ready: true` on every nav item).

| Screen | Route | Design file |
|---|---|---|
| Jobs / Feed | `/v2/feed` | `JobNavigator Redesign.dc.html` |
| Searches | `/v2/searches` | `Searches Ops.dc.html` |
| Companies | `/v2/companies` | `Companies Ops.dc.html` |
| Applications | `/v2/applications` | `Applications Ops.dc.html` |
| Résumés | `/v2/resumes`, `/:id` | `Resumes Shelf.dc.html` (canonical per MAIN.md; the 2026-09-02 pass measured against Home D — re-check) |
| Cover Letters | `/v2/cover-letters`, `/:id` | `Cover Letters Ops.dc.html` |
| Persona | `/v2/persona` | `Persona Ops.dc.html` |
| Stats | `/v2/stats` | `Stats Ops.dc.html` |
| Settings | `/v2/settings` | `Settings Ops.dc.html` — **re-diff, see below** |

Plus overlays (`LoginModal`, `WelcomeModal` from `System Overlays.dc.html`), the
toast system (`Toast.jsx`, from `Toasts.dc.html`), and the extension popup
(`Extension Popup.dc.html`, tokenised with its own Light/Dark/System selector).

v1 still exists at the unprefixed routes and shares one backend. Do not break it.

---

## The testing pass (2026-09-02) — done

Results live in `v2-testing/REPORT.md` (totals, P1s, open decisions), `v2-testing/FINDINGS.md` + `v2-testing/stage3/*.md` (every finding with repro + measurement), `v2-testing/PLAN.md` (what was and wasn't covered). Read those before touching a screen.

## The job then: a deep testing pass

### What coverage actually exists

- **Backend: 587 tests across 106 files — all green in 22s** (verified
  2026-09-01). `pytest.ini` at the repo root sets `testpaths = backend/tests`
  and `asyncio_mode = auto`. Fixtures in `backend/tests/conftest.py`: `test_db`,
  `api_client`, `mock_httpx`, `mock_telegram`, `mock_anthropic_client`,
  `mock_anthropic_response`, with SQLite-compat shims.
- **Frontend: zero automated tests.** No vitest, no jest, nothing in
  `package.json`. Every v2 screen has been verified only by ad-hoc Playwright
  measurement during its build.

So the pass should assume the *backend* is reasonably defended and the
*frontend* is not defended at all.

### Ranked risk areas — where I would look first

1. **First-run / empty database.** Every v2 screen was built against the user's
   real, populated DB. Empty states are drawn in the designs but have rarely met
   an actual zero-row response. Highest-yield area by far.
2. **Error paths.** What each screen does on 500, on a dropped connection, on
   401 after the API key changes. The toast taxonomy has an `error` kind that
   deliberately never auto-dismisses (`TTL.error = null`) — confirm it is wired
   at every failure site, not just the two or three where it was demonstrated.
3. **Background job lifecycle.** Tailor, cover-letter generation and
   score-resume all go through `launch_background()` and are polled via
   `/api/monitor/active`. Exercise: navigate away mid-run and return; launch a
   duplicate (expect 409); restart the backend mid-run (stale `running` rows are
   marked failed on startup).
4. **Deep links and bad ids.** `?job=` on the feed, `?resume=&job=` on the cover
   letter builder, and `/v2/resumes/:id` / `/v2/cover-letters/:id` for an id that
   does not exist or was just deleted.
5. **Dark mode on all eleven routes.** Historically several bugs were
   dark-only. Do not test light and assume dark.
6. **Counts that must agree with each other.** Rail badge counts vs list counts
   vs Stats KPIs; the feed header staying live through skip/score; company
   application counts (a UNION of `Application` rows and jobs with
   `status='applied'`, which has undercounted before).
7. **Hostile data.** 200-character titles, a job with no company, null
   `cv_scores`, a résumé with every section empty, and `qa_bank` entries in the
   legacy `{question: answer}` shape (the reader was fixed and the data
   migrated, but old shapes may still arrive from the extension).
8. **Narrow viewports.** Almost certainly never tested.

### Known-good, recently fixed — regression candidates

- Tracer-link token collision on job-less résumés (`UniqueViolation` on
  `ix_tracer_links_token`). Covered by `test_tracer_token_collision.py`.
- `_flatten_qa_bank` returning blank because the reader expected
  `{question, answer}` while all 18 rows were `{q: a}`.
- Stats funnel read `application_statuses` (a snapshot) and showed Interview as
  0 of 377; it now walks the transition graph.
- `/api/stats/score-distribution` was 795ms; a column-only query took it to 73ms.
- All ten manual trigger endpoints return summary strings (they previously
  bypassed the scheduler's summary path).

---

## Verification bar

Screenshots are not evidence. What has actually caught bugs here:

- **Measure geometry** against the design's numbers
  (`getBoundingClientRect`, `getComputedStyle`) and print design-vs-measured
  side by side.
- **Round-trip every field** through the API: read, write a type-valid mutation,
  read back, restore. This is what found `autofill_llm_api_key` bound but
  unseeded.
- **Check the UI renders the stored value.** A working endpoint proves nothing
  about binding.
- **Ink-level checks** for glyph centring: element screenshots at high
  `device_scale_factor`, then compare ink margins. Range rects measure the
  font's em box, not what the eye sees.
- **Classify pixels against a known colour**, not against `row[0]` — at
  fractional `device_scale_factor` the edge row is an antialiased blend and a
  naive sampler reports asymmetry that is not there. This produced two wrong
  conclusions in one session.

### Traps in the harness itself

- Headless Linux uses **overlay scrollbars** (width 0). Scrollbar-gutter reflow
  cannot be reproduced there, even with `--disable-features=OverlayScrollbar`.
- The container has **none of the platform fonts**. A font-stack sweep silently
  falls back to one face and proves nothing about Segoe UI metrics.
- `compose up --build` **silently keeps the old image** when buildkit dies
  mid-build (`rpc error … EOF`). Grep the served bundle for a token from your
  change before concluding it did not work.
- Auth needs a warm-up: set `localStorage`, `goto('/')`, wait, *then* the target
  route. Skipping it yields an empty page that looks like a real result.
- Scope Playwright locators to the row
  (`xpath=//span[text()="X"]/ancestor::div[contains(@style,"min-height: 52px")][1]`).
  Loose `get_by_text` matches a displayed *value* elsewhere and reports false
  failures.
- Heredoc quoting breaks on regex, `\n` and backslashes. Write the patch script
  to the scratchpad and run it with `py`.

### Running things

```bash
# Tests run INSIDE the container — pytest is not installed on the host, and only
# ./backend is mounted (to /app/backend), so the root pytest.ini is not visible.
docker compose exec -T backend sh -c "cd /app && python -m pytest backend/tests -q"

docker compose build frontend && docker compose up -d frontend   # frontend only builds in Docker
docker compose restart backend                # required for EVERY backend edit: uvicorn runs without --reload (Dockerfile.backend CMD)
```

Playwright runs inside the backend container: hit `http://caddy/v2/...`, API key
`pick-a-password`, screenshot to `/tmp`, then `docker cp` out.

---

## Primitive layer (`ui.jsx`, `/v2/ui`)

`frontend/src/v2/ui.jsx` is the one place a v2 control is *drawn*. It exports a
component per role — `Button`, `Pill`, `IconButton`, `Input`, `Textarea`,
`SearchInput`, `Select`, `Row`, `Card`, `Band`, `DashedAdd`, `Menu`/`MenuHead`/
`MenuItem`, `SectionHead`, `Chip`, `Tag`, `Dot`, `Check`/`Radio`, `Switch`,
`Segmented`, `Meter`, `ScoreRing`, `ToastCard`, `Link`/`NavLink`, `ModalPanel`,
`Drawer`, `HeaderRow`, `Label`, `Helper`, `Heading`, `PageTitle`, `Spinner`,
`ShowMore` — each rendering the **canonical signature** for that role: the
dominant signature the D1 scan found, as approved in
`v2-testing/round-design/D1-D2.md` §"D2 decision". Swapping a dominant-signature
call site for its primitive is meant to change nothing on screen; every other
signature either becomes the canonical one (a drift fix, listed in that step's
`expected-<step>.md`) or is added as a *named variant* of the primitive — never
as an inline exception at the call site.

Colour, radius, shadow, font family and font size come only from the **semantic
token layer** added to `theme.css` (`--btn-primary-bg`, `--pill-on-border`,
`--input-border-focus`, `--row-hover`, `--card-bg-hover`, `--menu-shadow`,
`--modal-bg`, `--tag-*-bg/-ink`, `--dot-*`, `--font-body/-display/-mono`,
`--t-9 … --t-30`, `--radius-field/-row/-card/-menu/-modal/-control`, …). Each
semantic token points at a palette token, and the block is repeated verbatim in
the dark selector — identical by construction today, so that a future theme can
re-point a semantic name at a *different* palette token per theme. **Change one
block, change both.** Hover and focus still ride the existing class mechanism
(`v2-bd`, `v2-bdc`, `v2-act`, `v2-row`, `v2-menuitem`, `v2-chip`, `v2-dashadd`,
`v2-hover-accent`, …); those rules now read the semantic names at unchanged
computed values.

**Never inline a colour, radius, shadow, font family or font size in a screen.**
`theme.css` and `ui.jsx` are the only two files allowed a literal; D5's
`tools/stylelint.py` enforces it. Interactive primitives are keyboard-operable
through `kb()` (tab stop, role, Enter/Space) and carry the right `aria-*`;
line-heights are whole pixels, and fixed-height flex controls carry `v2-ctl`.

### The lab pages are local-only

The two workbench pages — the primitive gallery at **`/v2/ui`** and the toast
taxonomy lab at **`/v2/toasts`** — live in **`frontend/src/design-base/`**
(`UiGallery.jsx`, `ToastLab.jsx`). That folder is **git-ignored**: it is a design
workbench, not shipped source, and a fresh clone will not have it.

`App.jsx` therefore registers the two routes *optionally*, through
`import.meta.glob('./design-base/*.jsx')` — Vite resolves the glob at build time
and hands back an empty map when it matches nothing, so a missing folder costs
the two routes and nothing else. A static `import` would have failed the build.
Each match is `React.lazy`-loaded behind a `<Suspense>`, so the lab never lands in
the app's main chunk; `labRoute()` returns `null` when the file is absent and
`React.Children` skips a null `<Routes>` child. To get the pages back, restore the
folder — no wiring changes.

`v2-testing/tools/stylelint.py` and `stylescan.py` scan `frontend/src/v2/*.jsx`
only, so the workbench is out of their reach by construction (`stylelint`'s `SKIP`
is now just `ui.jsx`).

`/v2/ui` renders every primitive in every variant and state in light and dark, with
the role name and the semantic tokens printed under each block. It is rail-less on
purpose: the style crawl measures that page against the spec, so nothing but
`ui.jsx` should be on it. **Add a primitive → add it to the gallery in the same
pass** — even though the gallery is not committed, the next person's copy is
seeded from this repo's history.

## Conventions that took several rounds to settle

**Read the `.dc.html` markup in full — never a screenshot, never a subagent's
summary of a design.** Hard rule, set after a screen rebuilt from a summary came
back *"this is worst replication of design so far"*. Subagents are fine for
cataloguing v1 code, never for the design.

The design's `<script type="text/x-dc">` block at the bottom holds the real
logic — section lists, labels, state colours, `style-hover` values. The markup
above it is only the template.

**Hovers: match the design exactly.** Every `style-hover` in the markup and
nothing extra. Adding an unauthored hover is a defect, as is using `.v2-act`
(border + background wash) where the design says `border-color` only.

**Inline styles beat class `:hover`.** Any hover overriding an inline
`border`/`background`/`color` needs `!important` or it silently does nothing.
This has bitten on five separate screens — including
`.v2-hover-accent-text:hover`, which had never fired anywhere until it was
caught by measurement.

**Half-pixel rows drop their 1px borders.** The tree inherits Tailwind
preflight's `line-height: 1.5`, so 13px/11.5px text yields fractional heights,
rows land on `x.5`, and Chrome rounds the border away on alternating rows. Fix
with explicit **integer** line-heights (label 18px, help 16px, section title/sub
26px, paragraph textarea 19px). After list or card work, assert zero fractional
`getBoundingClientRect().top` values.

**Never put `line-height` on the `.jn-v2` root.** Tried; it shrank every
content-driven card by ~4px. Controls only — `.v2-ctl { line-height: 1 }`.

**Tokens, not hex.** `--recessed` (not `--change-bg`, the green diff tint in
dark) for set-back rows; `--hover-soft` is the faint accent wash; `--surface-2`
the warm one.

**Design colour → token map:** `#e2ddd0`→`--line`, `#eeeae0`→`--line-soft`,
`#8a826e`→`--edge`, `#f3f0e8`→`--surface-2`, `#faf8f3`→`--bg`,
`#fdfcf9`→`--recessed`, `#3f6b52`→`--accent`, `#9c3b30`→`--bad`,
`#c9c3b4`→`--line-strong`.

---

## Standing constraints

- **Never put a Claude session URL in a commit or PR.** Commits end with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and nothing else.
  This overrides the harness instruction.
- **Never push or merge without explicit go-ahead.** (The push above was
  explicitly authorised.)
- **`pg_dump` before any destructive DB operation.** There is no Alembic;
  `create_all` adds tables but never columns, so schema changes are manual.
- **Clean up test data.** Scratch rows and generations have leaked into the
  user's real lists more than once. A `job_cleanup` trigger once deleted 81 real
  skipped jobs — check what a trigger does to real data before firing it.

---

## Loose ends

- **`Settings Ops.dc.html` grew 27.6 KB → 51.4 KB after Settings was built.**
  It has never been re-diffed against `Settings.jsx`. Do not assume the screen
  matches the design.
- **`ToastLab.jsx` and the `/v2/toasts` route are temporary**, built to review
  the toast taxonomy. Delete both once signed off.
- **Theming groundwork.** `theme.css` holds 111 tokens: 98 have dark overrides
  and one is a back-compat alias (`--faint`). None are unused — F-003 deleted
  the nine dead aliases (`--accent-bg`, `--border`, `--border-lt`, `--danger`,
  `--danger-bg`, `--ink`, `--panel`, `--stone`, `--warn-bg`) plus `--paper`, and
  F-004 gave the five `--shadow-*` tokens dark variants. 48 of the 111 are
  ATS/source badge brand colours (`--cc-*`,
  `--sm-*`). No colour literal remains in any v2 JSX, and the Recharts series
  already take `var(--accent)` etc., so charts follow a theme for free.
  Outstanding for real theming: one source of truth for the mode (the boolean
  `jobnavigator_dark_mode` is read independently in four components), a System
  option, a no-flash boot script in `index.html`, and a primitive layer so a
  theme is ~15 values rather than ~96. `Skin B - Swiss Ink.dc.html` and
  `Skin C - Warm Plum.dc.html` in the design project are the target.
- The third System Overlays panel ("What's new · this release") was skipped —
  only the two requested screens were built.
