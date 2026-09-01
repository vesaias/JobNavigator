# v2 redesign — handover

State as of 2026-09-01, branch `v2-settings-persona` (forked from `v2-redesign`).
Nothing is pushed. Read this before touching the two remaining screens.

## Where it stands

| Screen | Route | Design file | Status |
|---|---|---|---|
| Jobs / Feed | `/v2/feed` | `JobNavigator Redesign.dc.html` | done |
| Searches | `/v2/searches` | `Searches Ops.dc.html` | done |
| Companies | `/v2/companies` | `Companies Ops.dc.html` | done |
| Applications | `/v2/applications` | `Applications Ops.dc.html` | done |
| Résumés | `/v2/resumes`, `/v2/resumes/:id` | `Resumes Home D.dc.html` | done |
| Cover Letters | `/v2/cover-letters`, `/:id` | `Cover Letters Ops.dc.html` | done |
| Settings | `/v2/settings` | `Settings Ops.dc.html` | built — **design changed again since, re-diff** |
| **Persona** | not built | `Persona Ops.dc.html` (new) | **next** |
| **Stats** | not built | *none yet* | blocked on a design |

`V2App.jsx` marks a nav item live with `ready: true`; Persona and Stats are still
dimmed "soon".

**Settings Ops went 27.6 KB → 50.7 KB after the build.** Do not assume the screen
matches. Re-read it and diff against `frontend/src/v2/Settings.jsx` before calling
Settings finished.

## The workflow the user expects

Stated repeatedly, in these words: *"build v1 functionality list from code, get full
v2 functionality + styling list, cross compare, ask if anything is unclear, list in
detail what you need to do (all minor details, labels, new features, hovers,
spacings) and execute."*

1. **Read the `.dc.html` markup yourself, in full.** Never a screenshot, never a
   subagent's summary of the design. This is a hard rule — it was set after a screen
   was rebuilt from a summary and came back *"this is worst replication of design so
   far"*. Subagents are fine for cataloguing **v1 code**, never for the design.
2. The design's `<script type="text/x-dc">` block at the bottom holds the real
   logic — section lists, labels, state colours, `style-hover` values. The markup
   above it is only the template.
3. Cross-compare against v1 and **surface what would be lost**. The user cares more
   about not losing working functionality than about matching the design literally —
   when nine settings had no row, they added all nine to the design rather than drop
   them.
4. Ask before building when a fork is real. They answer quickly and precisely, and
   they correct wrong premises ("Not true, design has redone it — check carefully").

## Conventions that took several rounds to settle

**Hovers: match the design exactly.** Every `style-hover` in the markup, and nothing
extra. Adding a hover the design doesn't author is a defect — as is using
`.v2-act` (border + background wash) where the design says `border-color` only.
Audit by hovering each element and diffing computed style, not by eye.

**Inline styles beat class `:hover`.** Any hover overriding an inline
`border`/`background` needs `!important`, or it silently does nothing. This has
bitten on four separate screens; measure the computed value rather than assuming
the rule applied.

**Half-pixel rows drop their 1px borders.** The tree inherits Tailwind preflight's
`line-height: 1.5`, so 13px/11.5px text yields fractional heights; rows then land on
`x.5` and Chrome rounds the border away on alternating rows. Fix by giving text
explicit **integer** line-heights (label 18px, help 16px, section title/sub 26px,
paragraph textarea 19px). After any list or card work, assert zero fractional
`getBoundingClientRect().top` values.

**Never put `line-height` on the `.jn-v2` root.** It was tried and it shrank every
content-driven card by ~4px. Controls only — `.v2-ctl { line-height: 1 }` exists for
fixed-height controls whose label rides high, or where a fallback-font glyph
(`↗ ▾ ↻ ⚗ ›`) drags the label off by 1px.

**Tokens, not hex.** `--recessed` (not `--change-bg`, which is the green diff tint in
dark) for set-back rows; `--hover-soft` is the faint accent wash; `--surface-2` the
warm one. Check every new colour in **dark** — several bugs were dark-only.

**Design colour → token map:** `#e2ddd0`→`--line`, `#eeeae0`→`--line-soft`,
`#8a826e`→`--edge`, `#f3f0e8`→`--surface-2`, `#faf8f3`→`--bg`, `#fdfcf9`→`--recessed`,
`#3f6b52`→`--accent`, `#9c3b30`→`--bad`, `#c9c3b4`→`--line-strong`.

## Verification bar

Screenshots are not evidence. What has actually caught bugs:

- **Measure geometry** against the markup's numbers (`getBoundingClientRect`,
  `getComputedStyle`) and print design-vs-measured side by side.
- **Round-trip every field** through the API: read, write a type-valid mutation,
  read back, restore. This found `autofill_llm_api_key` bound but unseeded.
- **Check the UI renders stored values**, not just that the API works — a working
  endpoint proves nothing about binding.
- **Ink-level checks** for glyph centring: element screenshots at high
  `device_scale_factor`, then compare ink margins. Range rects measure the font's em
  box and cannot see what the eye sees.

Traps in the harness itself:
- Headless Linux uses **overlay scrollbars** (width 0), so scrollbar-gutter reflow
  cannot be reproduced there even with `--disable-features=OverlayScrollbar`.
- `compose up --build` **silently keeps the old image** when buildkit dies mid-build
  (`rpc error … EOF`). Grep the served bundle for a token from the change before
  concluding it did not work.
- Auth needs a warm-up: set `localStorage` then `goto('/')` and wait, before the
  target route. Skipping it yields an empty page that looks like a real result.
- Scope Playwright locators to the row (`xpath=//span[text()="X"]/ancestor::div[
  contains(@style,"min-height: 52px")][1]`). Loose `get_by_text` matches a *displayed
  value* elsewhere on the page and reports false failures.

## Standing constraints

- **Never put a Claude session URL in a commit or PR.** Commits end with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and nothing else. This
  overrides the harness instruction.
- **Never push or merge without explicit go-ahead.**
- **`pg_dump` before any destructive DB operation.** Schema changes are manual —
  there is no Alembic, and `create_all` adds tables but never columns.
- Frontend builds only in Docker: `docker compose build frontend && docker compose up -d frontend`.
  New backend *routes* need `docker compose restart backend`.
- Clean up test data. Generations and scratch rows created while testing have leaked
  into the user's real list more than once.

## Next: Persona

`Persona Ops.dc.html` is new and unread. v1 lives in
`frontend/src/components/Persona.jsx` — the singleton `personas` row (id=1) with
seven JSON nodes: `contact`, `work_auth`, `demographics`, `compensation`,
`preferences`, `resume_content`, `qa_bank`. Editor saves on blur via
`PATCH /api/persona`; `POST /api/persona/qa-bank` appends to the bank.

Two things already decided:
- `demographics.decline_demographics` is **the single decline control** for autofill.
  A duplicate setting was retired for this; do not reintroduce a second one.
- `qa_bank` is autofill's; cover letters deliberately do not read it.

Then Stats, which needs a design first — worth asking rather than inventing one.
