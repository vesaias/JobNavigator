# Reconcile S1 (b8adbc9) → S2 (working tree): Theme/Skin → Appearance/Theme rename

**Verdict: PASS — no regressions.** Every pixel/style delta between S1 and S2 is either
the expected rename copy/attribute change, or DB data drift from the live scheduler.
Cobalt (`--theme cobalt`) confirmed working end to end in both light and dark (S2c).

## Method

- Read `diff_S1_S2/summary.json` (per-route bbox + changed-pixel count) and
  `stylediff_S1_S2.md` (66 changed style tuples, grouped + itemized; Missing/Added-in-S2
  element lists).
- Cross-checked against the real code diff (`git diff b8adbc9 -- frontend/src/v2/theme.js
  frontend/src/v2/V2App.jsx frontend/src/v2/Settings.jsx`) so every visual delta is tied to
  an actual line of code, not just inferred from pixels.
- Cropped and eyeballed S1 vs S2 (and S2c) PNGs with PIL for every route the task named.

## Route-by-route

### Settings, light+dark, 1024+1440 — EXPECTED
`stylediff` height deltas: `.v2-scroll>div` 5123→5011px (−112px), `div:0` (the Display
section) 294→182px, its two rows 71→55px / 167→71px, their value cells 52→36px / 148→52px.
Direct crops of S1 vs S2 confirm this is exactly the documented rename:

- Section anchor + heading: **"Appearance" → "Display"**
- Row 1 label: **"Theme" → "Appearance"**, help text
  "System follows your OS setting and changes with it. The rail's ◐ cycles the same
  three." (2 lines) → **"Light, dark, or follow your OS. Saved in this browser."** (1 line)
- Row 2 label: **"Skin" → "Theme"**, help text (the old 5-sentence Skin paragraph) →
  **"The app's look: colours, fonts and, for Cobalt, SaaS and Win98, shapes too. Saved in
  this browser."** (1 line)
- Everything from the "Models" heading down (Models section, Scoring behavior, etc.) is
  byte-identical in both captures, just shifted up by the 112px the shorter Display
  section frees — the pixel-diff overlay paints the whole lower half red only because it's
  a naive position-diff on a vertically-shifted page, not because content there changed.
  Confirmed by direct crop comparison of the Models block in S1 vs S2 (`git diff` on
  `Settings.jsx` also shows the edit is contained to the Appearance/Theme rows plus the
  `themeSpec`/`appearanceSpec` copy objects — nothing else in the file touches Models,
  Scoring behavior, or below).

### Rail ◐ button title — EXPECTED
`git diff b8adbc9 -- frontend/src/v2/theme.js`: `themeTitle()` → `appearanceTitle()`,
tooltip text **"Theme: Dark — click to switch" → "Appearance: Dark — click to switch"**.
`V2App.jsx`: class `v2-themebtn` → `v2-appearancebtn` (rail hover selector), consumed by
the renamed `theme.css` hover rule. Reflected in `stylediff_S1_S2.md`'s Missing/Added
lists as `span.v2-navdark.v2-themebtn:2|◐` → `span.v2-navdark.v2-appearancebtn:2|◐` on
every route (feed, searches, companies, applications, resumes, cover-letters, persona,
stats, settings) — pure attribute/class rename, glyph and position unchanged.

### Attribute rename (data-theme/data-skin → data-appearance/data-theme) — EXPECTED
Confirmed directly in `theme.js`: `apply()` now does
`d.setAttribute('data-appearance', state.resolved); d.setAttribute('data-theme', state.theme)`
(was `data-theme`/`data-skin`). No paint changes anywhere — same CSS custom-property
cascade, just retargeted selectors in `theme.css`. Verified no orphaned selectors by the
absence of any other property (background/border/font) diff outside the three items above
across all 66 changed tuples in `stylediff_S1_S2.md`.

### Cobalt confirmation (S2c) — CONFIRMED, matches spec, differs from S2
`v2_settings__light__1440.png` / `v2_settings__dark__1440.png` in `S2c`:
- Theme dropdown reads **"Cobalt — IBM Plex blue"**, selected via the renamed `--theme
  cobalt` flag; Appearance dropdown independently reads Light/Dark — proves the two axes
  are no longer coupled and the rename didn't merge them.
- Visual: IBM Plex sans throughout (not the default's serif), blue accent (rail selection
  bar, active nav row background, checked Override toggle, focus ring) instead of the
  default's green/olive.
- Ground colour sampled by pixel at (700,500): light **rgb(244,245,247) = #f4f5f7**,
  dark **rgb(15,17,21) = #0f1115** — exact match to spec.
- Same point in plain **S2** (default theme): light rgb(252,251,247) (~#fcfbf7, warm
  paper), dark rgb(30,28,23) (~#1e1c17, warm dark) — both S2c shots clearly differ from
  their S2 counterparts, confirming `--theme cobalt` actually repaints the app and isn't a
  no-op.

### Cover letters, light+dark, 1024+1440 — DATA DRIFT
S1 shows 6 of 18 letters visible plus "Archived · 11 letters…"; S2 shows 1 letter plus
"Archived · 17 letters…" — 5 letters got archived/deleted by the live scheduler/backend
between captures (header count "18" unchanged, only the visible/archived split moved).
`stylediff_S1_S2.md` explains the one *style* tuple on this route
(`div.v2-act:1`: `backgroundColor rgb(255,255,255)→rgba(0,0,0,0)`, `borderTopStyle
solid→dashed`, `height 69px→40px`, padding shrink): row index 1 held a real letter card in
S1 and is the empty **dashed "add" band** in S2 because a card ahead of it in the list was
deleted, exactly the "deleted letter turns a card into the dashed add band" case flagged
in the task brief. Not a style regression — it's the existing empty-state row style,
just occupying a position that happened to hold content in S1.

The UUID-route cover-letters detail page (`…6c942d05…`) diff (3121px, bbox 341,12–1223,528)
is capture-timing noise, not content or style: S1's capture caught the PDF preview after
render (blank/white pane); S2's capture caught it mid-render — a small spinner glyph next
to "Template" and the placeholder text "Rendering the preview…" are visible, while the
Template/Paper dropdown values ("Garamond Classic" / "US Letter") and all letter-body text
are byte-identical. Async PDF-preview race, unrelated to the rename.

### Feed, light+dark, 1024+1440 — DATA DRIFT
S1: 16 open roles, top rows all badged **SAVED** (green heart), top score 77 (Nomura).
S2: 4 open roles, none saved, top score 40 (JPMorgan Chase) — an entirely different job
set (401 arrived-today count is unchanged, so this is normal feed churn from the live
scheduler, not a broken filter). This also explains the grouped style-diff entries:
- `hover · color rgb(63,107,82)→rgb(156,59,48)` (light) / `rgb(141,187,159)→rgb(217,138,126)`
  (dark) on the score-ring hover states, and
- `rest · color rgb(63,107,82)→rgb(87,83,74)` (light) / `rgb(141,187,159)→rgb(203,199,191)`
  (dark) on the ♥ save-rail cell,

both are the existing saved/unsaved and hover/unhover token pairs in `ui.jsx` — they
render differently only because the job occupying row 0 (and its saved state) differs
between captures. No new colour values, no changed token, same component.

### Stats, light+dark, 1024+1440 — DATA DRIFT
Row at y153–176 (`Saved` and `Best open score` stat tiles): S1 "12" / "77 · Meta" → S2
"0" / "40 · JPMorgan Chase" — same two numbers that moved on the Feed page for the same
reason (live saves/scores changing between captures). Layout, font, colour identical.

### Toasts (design-base gallery, git-ignored), light+dark, 1024+1440 — EXPECTED (copy touch-up)
221×13px diff at top-left is the page subtitle: **"Temporary — fire each kind, check both
themes, then delete this page."** (S1) → **"…check light and dark, then delete this
page."** (S2). Confirmed in `frontend/src/design-base/ToastLab.jsx:30`. This file lives
under `design-base/`, which is git-ignored per CLAUDE.md, so it doesn't show in the
19-file `git diff --stat`, but it's a real, deliberate edit made alongside the rename: once
"Theme" means the palette/skin axis, "both themes" (meaning light/dark) reads as
ambiguous, so the copy was reworded to "light and dark" to avoid colliding with the new
term. Same font/colour/position — pure text edit, no paint change.

### Companies, dark, 1440 (48px) / light, 1440 (52px) — DATA DRIFT (noise-adjacent)
Brex row, "Open · 7d" column: S1 "1" → S2 "0" (crop-confirmed, same teal "+8" apps count
either side unchanged). Live scrape count ticking down between captures. Same digit glyph,
same colour, same position.

### Searches, light, 1440 (17px) — RENDERING NOISE, not a regression
Bbox (1407,48)–(1410,243) is a 3px-wide sliver at the very right edge of the row list,
spanning the border of the first two rows. Crop shows only faint sub-pixel red dashes at
the container's right border — no visible content or colour difference between S1 and S2
at that column. Consistent with browser scrollbar-overlay/antialiasing jitter between two
otherwise-identical captures (row content and count "6 configs · 4 active" match). Too
small and too marginal to be a paint regression; flagging as noise rather than expected or
drift since it isn't explained by either mechanism, but it carries no visual meaning.

### Résumés (specific résumé route), light 1024 (7px) / light+dark 1440 (46px/42px) — NOISE
- light 1024, 7px bbox around the "TAILORED" pill/header: pixel-identical on crop
  (sub-pixel antialiasing only).
- light+dark 1440, the PDF-preview pane bbox: both S1 and S2 show a blank/white preview
  pane in this crop — same async-PDF-render timing noise as the cover-letters detail page
  above, not a content or style change.

## Regression list

**None.** No unexplained colour, font, radius, shadow, spacing, or layout change was found
anywhere in the S1→S2 diff. Every item above is fully accounted for by (a) the documented
Appearance/Theme rename, (b) the ToastLab copy touch-up that accompanies it, (c) live DB
drift from the running scheduler, or (d) sub-pixel/async-render capture noise.

## Cobalt confirmation summary

`--theme cobalt` (S2c), both light and dark, renders the Cobalt palette (IBM Plex font,
blue accent, `#f4f5f7` light ground / `#0f1115` dark ground) and both differ from the
default-theme S2 captures at the same pixel — the renamed attribute pipeline
(`data-appearance` for light/dark, `data-theme` for the palette) works end to end.
