# v2 design-consistency pass — REPORT

Branch `v2-redesign`, 2026-09-04 → 2026-09-05. Plan and log: `DESIGN-PASS-PLAN.md`. Working files: `round-design/` (scan, spec, expected-diff lists, reconciliations, final smoke/flows/verify). Artifacts (gitignored): `artifacts/design/` (D0 screenshots, per-step style diffs, alt-skin samples).

## What changed

**Before:** 1 737 inline style objects across 20 v2 files; every button, pill, input, row, card, menu, header and label was its own copy, drifting by a pixel or a token at a time (79 pill sites in 57 variants, 39 primary buttons in 33, 69 inputs in 37 …).

**After:**
- `frontend/src/v2/ui.jsx` — one primitive layer: `Button` (primary/secondary/danger/ghost · md/sm/xs · disabled/busy), `Pill`, `IconButton`, `Input`, `Textarea`, `SearchInput` (boxed/underline), `Select`, `Row`, `Card`, `Band`, `DashedAdd`, `Menu`/`MenuItem`, `SectionHead`, `Chip`, `Tag`, `Dot`, `Link`/`NavLink`, `ModalPanel`, `Drawer`, `HeaderRow`, `TableHead`, `Rule`, `Surface`, `Label`, `Helper`, `Heading` (+`strong`), `PageTitle`, `Spinner` (+`bold`), `ShowMore`, `RemoveX`/`RemoveLink`, `MoveArrows`. Keyboard access, ARIA, integer line-heights and the app's own focus style are built in.
- `frontend/src/v2/theme.css` — a semantic token layer (≈250 tokens: `--btn-*`, `--pill-*`, `--input-*`, `--row-*`, `--card-*`, `--menu-*`, `--modal-*`, `--tag-*`, `--font-*`, `--t-*`, `--radius-*`) on top of the palette, identical name set in the light and dark blocks; every hover rule reads semantic tokens. A theme now changes the palette only.
- **691 sites migrated** in six steps (buttons/pills/icons 93 · fields 54 · rows/cards/bands 49 · menus/headers/chips/tags/dots 75 · links/labels/helper/headings/spinners 317 · modals/drawers/header rows/table heads/rules 103) plus the D5 sweep. 109 sites deliberately kept inline, each annotated `// ui: keep — <reason>` (segmented controls, checkbox indicators, chart fills, the rail, the toast card, a few badges).
- **Lint** `tools/stylelint.py` at exit 0: no raw colour, font, radius or shadow outside `theme.css`/`ui.jsx`; no hover class on a non-primitive; semantic tokens present in both theme blocks.
- **Theme store** `frontend/src/v2/theme.js`: `light | dark | system` with a `prefers-color-scheme` listener and a no-flash boot script; v1 and v2 read one source (SHELL-02 and SHELL-06 closed). **Skin** `default | alt` (palette + fonts only) from Settings › Appearance; gallery `/v2/ui` shows every primitive in all four combinations.

## How the design was proven unchanged
- Pixel baseline D0 (52 screenshots, clock frozen, DB at a fixed dump) and a computed-style crawl (≈5 700 elements, rest + hover tuples) taken before any change; re-taken after every step.
- Every step shipped an expected-diff list; a Sonnet agent reconciled every changed tuple and overlay against it. Six steps, six reconciliations, **two regressions caught and fixed within the next step** (a card border colour cleared by an `undefined` style key; a Settings help line wrapping at 11.5 px), one crash caught by the gate itself (a moved component not imported → blank Persona/résumé editor), and the deliberate drift fixes accepted (≈220 sites moved to the canonical value: pill 23→26 px, inputs to 32 px, helper text to a 16 px line box, labels to .13em, radii to the shared scale …).
- Skin proof: default vs alt crawl on the same build and a still database — only `color`, `backgroundColor`, `border*Color`, `fontFamily` and the heights of multi-line prose differ; fixed-height controls, headers, labels and tags are identical (three baseline-alignment font leaks found and pinned).
- Final behavioural gate: smoke over 14 routes × 4 theme/skin combinations, both flow groups end to end (real scrapes, real LLM calls, Telegram, Gmail): all steps pass; the issues they raised are fixed and re-verified (see below).

## Decisions taken with the user
Canonical = dominant signature per role (approved as proposed); footers at 33 px; disabled/finished buttons grey; fields and selects 32 px; thick 2 px score ring kept as a `Spinner` variant; `--series-new` timeline token confirmed; `Heading strong` line-heights pinned to whole pixels; experience reorder not added.

## Found by the final gate and fixed
| id | what | fix |
|---|---|---|
| DS-S-31 P1 | alt skin inert in light mode | a `--cc-*/--sm-*` glob in a CSS comment spelled `*/` and swallowed the alt light block |
| DS-S-11/12 P1/P2 | "+ New résumé" clipped to "+ N"; latent overflow on Cover Letters | `SearchInput` wrapper sized by flex-basis only → explicit width |
| DS-S-21/32 P3 | `Select` did not close on Escape | capture-phase Escape while open |
| DS-A-03 P2 | every Escape on Applications raised "Discard?" after a save | dirty flag reset on save/close; Escape routed only while the modal is open |
| DS-A-02 P2 | Searches test preview ignored `title_exclude_global` | preview applies it like the run; `GLOBAL` badge + footer count |
| DS-B-02 P2 | a failed tailor/score/regenerate shown as success | pollers read the run's real status; error toasts with the reason |
| DS-B-03 P3 | autofill sometimes returned the JSON envelope | robust extraction, never returns text starting with `{` |
| DS-B-01 P4 | disabled primitives dropped `role` | role kept, `tabindex -1` |
Verification: `round-design/verify-final.md` — 10/10 confirmed live on the final build (including the skin fixed-height check: no control differs between skins; the two flagged heights are a wrapped hint label).

## After the report: user-found items and the last primitives (2026-09-05)
- Fixed and verified live (`round-design/verify-postpass.md` 15/15, plus a spot check after `e91930c`): company-filter search field collapsing to 17 px (menu children never shrink), H-1B filing count moved to hover, `Select` on `--input-bg`, Off/Light/Full dots and centring, Companies row menu above the sticky cells, selected row = accent wash on Feed and Applications (no left bar), Stats type menu Escape, Feed popups on one inner geometry (Salary gained its missing max field), `ScoreRing` viewBox (small ring no longer clipped), unscored label "No fit".
- New primitives: `ScoreRing`, `Segmented` (5 sites), `Switch`, `Check`/`Radio`, `Meter`, `ToastCard` — every recurring hand-written control is now in `ui.jsx`; the remaining inline sites are one-offs (rail, PDF toolbar, chart fills, a few badges), 97 annotated keeps. Lint still 0.
- The gallery and the toast lab now live in `frontend/src/design-base/` (git-ignored, local only); their routes register only when the folder exists.
- Not reproduced: a flush-left text inset in the company search field (measured 16 px, one pixel from the menu items' 17 px).
- Decisions still open: keyboard access on the kept one-offs (user: ignore unless critical); bulk-checked rows and the open-detail row share the accent wash (say if bulk needs its own tint).

## Still open after the pass
- DS-A-01 (P3): the hand-written controls kept inline (row Run/Test/⋯, Feed Sort trigger, row rail ♥/✕/⋯, stage stepper, `Select all shown`, `?` badge) are not keyboard-reachable. Suggested: give them `kb()` or migrate to `IconButton`/`Pill`.
- DS-S-33 (P4): the toast lab page (now local-only in `design-base/`) has no keyboard access; low priority.
- The prose/`text` role (≈200 plain runs at 12.5–13 px) stays inline by decision; if the type scale ever changes, those move to `--t-*` in one mechanical pass.
- Persona's Q&A card and the résumé editor's field-shaped prose rows keep their own look (annotated).

## How to add a theme or a skin
1. **Theme (light/dark values):** edit the palette tokens in `.jn-v2 { … }` / `.jn-v2[data-theme="dark"] { … }` in `theme.css`. Do not touch the semantic block.
2. **Skin (a new look):** copy the two `[data-skin="alt"]` blocks, rename the attribute value, set palette tokens (backgrounds, surfaces, text, accent, lines, edge, states, stage colours, `--sans/--serif/--mono`); keep the token set identical in both blocks. Register the value in `theme.js` `SKIN_OPTIONS`. Run `tools/stylelint.py`, then the skin proof (`stylecrawl.py X`, `stylecrawl.py Xalt --skin <name>`, `stylediff.py X Xalt` — only colours/fonts/prose heights may differ).
3. **Never** style a screen inline with a colour, font, radius or shadow; use a primitive or a token. The lint will fail otherwise.

## Numbers
- Worker tokens: ≈3.6 M (Opus 12 runs, Sonnet 9 runs); orchestrator ≈0.4 M.
- Backend suite: 880 passing. Lint: 0 findings, 109 annotated keeps.
- DB restored to `backups/design_baseline_20260904.dump`; 0 scratch rows.

Nothing pushed. All commits bare, on `v2-redesign`.
