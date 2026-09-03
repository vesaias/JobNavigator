# expected-D4c — Row / Card / Band / DashedAdd replacements

D4c routes every list row, card, static card, dashed band and dashed add-line in
`frontend/src/v2/*.jsx` (screens, modals, drawers; `UiGallery.jsx` + `ToastLab.jsx`
out of scope) through `Row` / `Card` / `Band` / `DashedAdd` from `./ui`.
Click handlers, selection state, `data-*` hooks, sticky action cells, the résumé
shelf's chip rows and every screen's own local wrapper name are untouched; `style`
is passed for layout only (padding, gap, flex, height, alignment) plus the handful
of **state tints** noted per row.

## Mapping rules used
- `Card` canonical: **`--card-bg` · 1px `--card-border` · `--radius-card` (9) ·
  pad 10 14**. `interactive` (or any `onClick`) adds `v2-act` — accent border +
  `--card-bg-hover` on hover — and the `kb()` keyboard contract. A **static card**
  is the same box with no hover and `cursor:default`; its own padding is passed as
  layout (`padding: 0` where the card's children carry the padding).
- `Band` is the dashed sibling: **1px dashed `--band-border` · r9 · pad 10 14**,
  `interactive={false}` for an inert one.
- `Row` canonical: **h46 · `--radius-row` (7) · gap 10 · pad 0 10 · hover
  `--row-hover`**; `selected` paints `--row-selected` and a 3 px
  `--row-selected-mark` bar with the compensating left pad; `divider` draws the
  1px `--row-line` rule beneath.
- `DashedAdd` canonical: **accent ink · 1px dashed `--dashadd-border` · r6 · 11.5 ·
  h28**, `big` = 32 / 12 / 500.
- A **state tint** (a card that goes `--recessed` when archived, `--accent` when
  open, `--bad` on an error) stays a `borderColor`/`background` override on the
  primitive — the same treatment D4b gave Settings' error textarea. It is a
  palette token, not a literal, so a skin still swaps in one place.
- Anything **badge-, checkbox-, toggle- or segment-shaped** that the scan's
  card/band signature happens to match is **not** a card: it keeps its inline
  style and gains a `// ui: keep — …` line. Same for the field-shaped (r6) prose
  rows in the résumé editor.

Rows are `file:line | element | before → after`. A row marked **zero-pixel**
changes nothing and is listed only for the record. Line numbers are post-change.

## ui.jsx — additions (all zero-pixel on `/v2/ui` except the new `flush` specimen)

| site | change | why |
|---|---|---|
| ui.jsx:370 | `Card` becomes `React.forwardRef` and gains an `id` prop | Stats scrolls two static cards into view (`schedRef`, `runsCardRef`) and deep-links one as `#runs`; without a forwarded ref and an `id` those two could not migrate |
| ui.jsx:356 | `Row` gains `...rest` (spread first, before the handlers) | carries the `data-*` hooks a screen already relies on — the Feed keys `scrollIntoView` and its harness selectors off `data-row={i}` |
| ui.jsx:355 | `Row` gains the named variant **`flush`** (radius 0, everything else canonical) | Companies is v2's one full-bleed table: its list has no side padding, so a 7 px radius would round the hover fill away from the pane edges and leave a notch under the square sticky `.v2-cactions` cell. Rendered on `/v2/ui` as `flush — no radius (full-bleed table row)` |

## Persona.jsx

| site | element | before → after |
|---|---|---|
| Persona.jsx:347 | the five autofill **group cards** (contact / work auth / demographics / compensation / preferences) | inline `1px --line · r9 · --surface · flex column` → `Card style={{padding:0, …}}` — **zero-pixel** (`--card-bg` = `--surface`, `--card-border` = `--line`, `--radius-card` = 9); the header and the field grid keep their own padding |

### kept inline
- `Persona.jsx:364` — the **Q&A bank card**: the only amber-tinted card in v2
  (`--amber-bg` on `--amber-line`; theme.css pins the tint because its answers
  reach the LLM verbatim). `Card` has no tone variant, and overriding both colours
  at the call site would put two colours back into a screen. `// ui: keep`.
- `Persona.jsx:383` — a Q&A entry row **inside** that amber card, bordered
  `--amber-line-soft` at r7; a `Card` here would reintroduce `--line`. `// ui: keep`.
- `Persona.jsx:134` — the 15×15 **checkbox indicator** (r4, accent when checked).
  Not a card. `// ui: keep`.

## Stats.jsx

The screen's shared `CARD` style object is **deleted**; all seven users become `Card`.

| site | element | before → after |
|---|---|---|
| Stats.jsx:421 | KPI strip (5 tiles in one card) | `CARD` (`1px --line · r10 · --surface`) → `Card style={{padding:0, display:'flex'}}`: **radius 10 → 9** |
| Stats.jsx:443 | Application funnel / Flow card (fixed h230) | same → `Card`: **radius 10 → 9**; the fixed height and `16px 20px` padding pass through as layout |
| Stats.jsx:492 | Score distribution card | same → `Card`: **radius 10 → 9** |
| Stats.jsx:517 | Jobs-discovered timeline card | same → `Card`: **radius 10 → 9** |
| Stats.jsx:533 | LLM cost card (fixed h300, `overflow:hidden`) | same → `Card`: **radius 10 → 9** |
| Stats.jsx:579 | Scheduler card (`ref={schedRef}`) | same → `Card ref={…}`: **radius 10 → 9** |
| Stats.jsx:629 | Run history card (`id="runs" ref={runsCardRef}`) | same → `Card id ref`: **radius 10 → 9** |

The chart containers keep their fixed heights (230 / 300) — those are layout on
the primitive, not a reason to stay inline.

## Settings.jsx

**Nothing to migrate.** The screen has no card, row, band or dashed-add site in
the scan: its sections are rule-separated form rows (`minHeight 52`, `padding 9px 0`,
1px `--line-soft` beneath, no radius, no hover, no click) and its model-catalog
list is a 36 px table row of the same shape. Neither is a list row in the `Row`
sense — migrating either would add a 46 px height, a radius and a hover to a form.
`// ui: keep` is not added at those sites because the scan does not classify them
as row/card either; they are `layout`.

## Resumes.jsx

| site | element | before → after |
|---|---|---|
| Resumes.jsx:165 | shelf **load-error band** | `1px dashed --bad · r9 · pad 20 14` → `Band interactive={false} style={{borderColor:'var(--bad)', padding:'20px 14px', …}}` — **zero-pixel** (the `--bad` edge is kept as a state tint) |
| Resumes.jsx:176 | "Nothing matches …" empty band | `1px dashed --line · r9 · pad 20 14` → `Band interactive={false}` — **zero-pixel** |
| Resumes.jsx:193 | "Nothing archived yet …" empty band | same → `Band interactive={false}` — **zero-pixel** |
| Resumes.jsx:178 | search-result row | `v2-act · 1px --line · r9 · --surface · pad 10 14 · cursor pointer` → `Card onClick`: **zero-pixel**; gains `role="button"`, `tabIndex=0` and Enter/Space from `kb()` (it was a bare `<div onClick>`) |
| Resumes.jsx:195 | archived-copy row | same signature → `Card onClick`: **zero-pixel**; same keyboard gain |
| Resumes.jsx:210 | **Persona card** | `v2-card · 1px --line · r11 · --surface · pad 16 20` → `Card onClick`: **radius 11 → 9**; hover `v2-card` → `v2-act` is **zero-pixel** (theme.css gives both rules the identical accent-border + `--card-bg-hover`); gains the `kb()` keyboard contract |
| Resumes.jsx:253 | **base-résumé cards** | same signature → `Card onClick`: **radius 11 → 9**, same hover equivalence, same keyboard gain |
| Resumes.jsx:294 | "Archived · N copies … browse ›" band | `v2-act · 1px dashed --line · r9 · pad 10 14` → `Band onClick`: **zero-pixel**; gains `kb()` |

### kept inline
- `Resumes.jsx:230/…` — the shelf **copy chips** and the in-flight "tailoring…"
  chips (h26 · r99 · `--bg` on `--line`, `v2-chip` hover) and the 6 px "unreviewed"
  dot. Already annotated `// ui: keep — Chip role …, migrates with Chip`; they are
  the `chip`/`dot` roles, not cards, and D4c does not touch them. The chip rows
  inside the base and Persona cards render exactly as before.

## CoverLetters.jsx

| site | element | before → after |
|---|---|---|
| CoverLetters.jsx:308 | **letter row** (active and archived) | `v2-bd · 1px --line / --line-soft · r10 · --surface / --recessed · pad 13 15`, with a hand-rolled `tabIndex/role/onKeyDown(Enter)` → `Card onClick` keeping the archived tint as `{borderColor:'var(--line-soft)', background:'var(--recessed)'}`: **radius 10 → 9**, **hover `v2-bd` (accent border only) → `v2-act` (accent border + `--card-bg-hover` wash)**, keyboard goes from Enter-only to Enter **and** Space via `kb()` |
| CoverLetters.jsx:383 | "Generating — …" pending band | `1px dashed --accent · r10 · --recessed · pad 13 15` → `Band interactive={false}` with the accent + recessed tints as overrides: **radius 10 → 9** |
| CoverLetters.jsx:398 | "Archived · N letters … browse ›" band | `v2-act · 1px dashed --line · r9 · pad 10 14 · marginTop 6` → `Band onClick`: **zero-pixel**; gains `kb()` |

### kept inline
- `CoverLetters.jsx:110` — `LengthPicker`: a **segmented control**, not a card —
  three equal-flex cells sharing one border run, swinging to `--accent-soft` when
  picked. `// ui: keep`.

## Searches.jsx

| site | element | before → after |
|---|---|---|
| Searches.jsx:579 | **"New search" card** | `1px --accent · r10 · --surface` → `Card style={{padding:0, borderColor:'var(--accent)'}}`: **radius 10 → 9** |
| Searches.jsx:585 | its inline form's bottom corners | `borderBottomLeft/RightRadius 9` → **8** (inner radius = the card's new 9 minus its 1 px border) |
| Searches.jsx:613 | the **search cards** (one per search) | `1px --warn-line / --accent / --line · r10 · --surface`, hover class `v2-card` / `v2-card v2-bd-warn` / none-when-open → `Card className={…}` (static — the summary row inside owns the click) with the warn/open edge as a `borderColor` override: **radius 10 → 9**; the hover classes, including `.v2-bd-warn` winning over `.v2-card`, are passed straight through unchanged |
| Searches.jsx:659 | the open card's inline edit form corners | `borderBottomLeft/RightRadius 9` → **8**, same reason |

### kept inline
- `Searches.jsx:203` — the 14×14 **checkbox indicator** in `Check`. `// ui: keep`.
- `Searches.jsx:663` — the 25 px **Run / Test pills** on the card's action row,
  sized to their row siblings (`Pill sm` is 26). `// ui: keep` (the ⋯ beside them
  already carried the same note from D4a).

## Companies.jsx

| site | element | before → after |
|---|---|---|
| Companies.jsx:490 | the **company table row** | `v2-crow · h46 · pad 0 30 0 24 · 1px --line-soft beneath · cursor pointer`, no radius → `Row flush divider onClick className="v2-crow" style={{gap:0, padding:'0 30px 0 24px'}}`: **zero-pixel** — `flush` keeps radius 0, `divider` draws the same `--row-line` (= `--line-soft`) rule, `gap:0` keeps the column widths (Row's canonical gap is 10 and every cell here carries its own `paddingRight`). `.v2-crow` is **kept on the element** because `.v2-crow:hover .v2-cactions` is what repaints the **sticky actions cell** on hover; `.v2-row` from the primitive hovers to the identical `--row-hover`. Gains `role="button"`, `tabIndex=0` and Enter/Space |
| Companies.jsx:118 | "+ Add another career page" | `v2-dashadd · h30 · 1px dashed --edge · r7 · 11.5 · ink --muted` → `DashedAdd`: **height 30 → 28**, **radius 7 → 6**, **ink `--muted` → `--dashadd-ink` (`--accent`)**; border, dash, font-size and hover unchanged; gains `kb()` |

### kept inline
- `Companies.jsx:131` — `Seg`: a **segmented control** (equal-flex cells, accent-soft
  when picked). `// ui: keep`.
- `Companies.jsx:532` / `:540` — the 25 px **Run / Test pills** in the row's sticky
  actions cell, sized to the 46 px row (`Pill sm` is 26). `// ui: keep`.
- `Companies.jsx:772` — the drawer footer's **Test scrape** pill (h32 · r99),
  paired with the tinted "Make inactive" pill beside it. `// ui: keep`.

## Applications.jsx

| site | element | before → after |
|---|---|---|
| Applications.jsx:428 | the **application list row** | inline `v2-arow · h46 · r7 · pad 0 10 (0 10 0 7 when selected) · borderLeft 3px --accent when selected · --surface-2 when selected` → `Row selected onClick className="v2-arow" style={{gap:8, flex:'0 0 46px', marginBottom:3}}`: **zero-pixel** — this row *is* the canonical signature the primitive was drawn from (D1-D2 lists it as the dominant `row`); `gap:8` and the flex/margin stay as layout. Gains `role="button"`, `tabIndex=0` and Enter/Space |
| Applications.jsx:578 | **interview card** | `1px --accent / --line · r9 · pad 10 12 · --surface / --bg` → `Card` with the edit-state tint as `{borderColor:'var(--accent)'}` and the rest state as `{background:'var(--bg)'}`: **zero-pixel** |
| Applications.jsx:623 | **add-interview form card** | `1px --accent · r9 · pad 10 12 · --surface` → `Card style={{borderColor:'var(--accent)', padding:'10px 12px'}}`: **zero-pixel** |
| Applications.jsx:648 | "+ Add interview" | `v2-bdc · h34 · 1px dashed --line-strong · r9 · 12 · ink --muted` → `DashedAdd big style={{gap:7}}`: **height 34 → 32**, **radius 9 → 6 (`--radius-field`)**, **border `--line-strong` → `--dashadd-border` (`--edge`)**, **ink `--muted` → `--dashadd-ink` (`--accent`)**, **weight 400 → 500**, **hover `v2-bdc` (accent border + accent ink) → `v2-dashadd` (accent border + `--dashadd-bg-hover` wash)**; gains `kb()` |

### kept inline
- `Applications.jsx:546` — the **stage stepper** (Applied / Interview / Offer /
  Rejected): a segmented control whose cells tint per stage (`--accent` or `--bad`).
  `// ui: keep`.
- `Applications.jsx:823` — the log-application modal's **status segments**, same
  shape. `// ui: keep`.
- `Applications.jsx:369` — the company-filter **checkbox indicator**. `// ui: keep`.
- `Applications.jsx:349` — the toolbar search composite (see `expected-D4b-fixup.md`).

## JobFeed.jsx

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:879 | the **feed row** | `v2-row · data-row={i} · r8 · 1px --line-soft beneath · backgroundColor accent-soft / surface-2 / transparent · ignored stripes · alignItems stretch · content height (~64px)` → `Row data-row divider onClick` with `{height:'auto', alignItems:'stretch', gap:0, padding:0, backgroundColor, backgroundImage, overflow:'hidden', flex:'0 0 auto'}`: **radius 8 → 7 (`--radius-row`)**. The box (radius, divider, hover, cursor) is now the primitive's; the layout is the caller's, because this row is a 64 px two-column block, not a 46 px single-line one. Its three background states (bulk-checked `--accent-soft`, focused `--surface-2`, rest transparent) stay inline — `Row selected` would additionally draw the 3 px accent bar and shift the left pad, which this row does not have. `data-row` survives via `Row`'s new `...rest` (the screen's `scrollIntoView` and the harness both query `[data-row]`). Gains `role="button"`, `tabIndex=0`, Enter/Space — no clash with the screen's shortcut handler, which ignores Enter and Space |
| JobFeed.jsx:1135 | report → **ATS tip card** | `1px --line · r9 · --surface-2 · pad 12 14` → `Card style={{background:'var(--surface-2)', padding:'12px 14px'}}`: **zero-pixel** |

### kept inline
- `JobFeed.jsx:891` — the "N résumé reports" **16 px mono badge** on the score
  ring. Already a badge, not a card.
- `JobFeed.jsx:1153` — the dashed 34 px **"No fit" badge** filling the score slot,
  and `JobFeed.jsx:1200` — the dashed 44 px **▲ glyph** on the frame-blocked panel.
  Both are dashed *badges* (r99), not add-lines. `// ui: keep`.
- `JobFeed.jsx:1182` — the **Live / Cached segmented toggle track** (r99, 2 px
  inset). `// ui: keep`.
- `JobFeed.jsx:1129` — the report's "Hard blockers" box (`1px --bad · r8`, no
  background) is not classified as a card by the scan (it has no fill) and is left
  untouched; flagged for D5 rather than migrated on a guess.

## ResumeEditor.jsx

| site | element | before → after |
|---|---|---|
| ResumeEditor.jsx:713 | tailor modal → "No base résumés yet." | `1px dashed --edge · r8 · pad 12 · 11.5/17 · --muted` → `Band interactive={false}`: **border `--edge` → `--band-border` (`--line`)**, **radius 8 → 9** |
| ResumeEditor.jsx:806 | tailor modal → "No jobs match — paste a description below instead." | same signature → `Band interactive={false}`: same two changes |

### kept inline
- `ResumeEditor.jsx:876` — the change list's **suggested / applied / declined state
  badge**, whose dashed `--warn-line` edge marks a suggestion. A badge, not an
  add-line. `// ui: keep`.
- `ResumeEditor.jsx:888` — the **inline diff highlight** on a run of text (r3,
  dashed while suggested). `// ui: keep`.
- `ResumeEditor.jsx:871` — the change card itself (three tint states across
  `--line`/`--warn-line`/`--change-soft` and `--bg`/`--warn-soft`/`--change-bg`).
  Not a card/band site in the scan; left for D5.

## ResumeSections.jsx  (shared by Résumé editor + Persona)

The file's local `DashedAdd` is **deleted** and re-exported from `./ui`
(`export { DashedAdd } from './ui'`), so Persona and ResumeEditor keep importing it
from here and its **seven existing call sites do not churn**.

| site | element | before → after |
|---|---|---|
| ResumeSections.jsx:128 (deleted) | local `DashedAdd` → `./ui`'s | `h28/32 · 1px dashed --edge · r6 · 11.5/12 · w400/500 · --accent · v2-dashadd` → the primitive, value-for-value — **zero-pixel** across all **8** call sites (`+ Add contact item`, `+ Add bullet` ×2, `+ Add experience`, `+ Add skill row`, `+ Add education`, `+ Add project`, `+ Add publication`) |
| ResumeSections.jsx:137 | `EmptyState` | `1px dashed --edge · r8 · pad 16 12` → `Band interactive={false}`: **border `--edge` → `--band-border` (`--line`)**, **radius 8 → 9**. Used by every empty résumé section |
| ResumeSections.jsx:161 | `SectionShell` — the collapsible section card | `1px --line · r9 · --surface` → `Card style={{padding:0}}` — **zero-pixel** |
| ResumeSections.jsx:267 | **experience entry card** | `1px --line · r8 · --surface` → `Card style={{padding:0}}`: **radius 8 → 9** |
| ResumeSections.jsx:271 | its collapsible header | `borderRadius 8` → **9**, tracking its card (the header's radius exists to clip the hover wash to the card's corner, and matched the card before) |
| ResumeSections.jsx:313 | "+ Add bullet" (experience) | `v2-act · h28 · 1px dashed --edge · r6 · 11.5 · --accent` → `DashedAdd`: **hover `v2-act` → `v2-dashadd`** — the two rules paint the same accent border and the same `--hover-soft` wash (`--card-bg-hover` and `--dashadd-bg-hover` both point at it), so this is **zero-pixel**; the ink was already `--accent` |
| ResumeSections.jsx:431 | **education entry card** | `1px --line · r8 · --surface · pad 11` → `Card style={{padding:11}}`: **radius 8 → 9** |
| ResumeSections.jsx:455 | **projects entry card** | same → `Card`: **radius 8 → 9** |
| ResumeSections.jsx:491 | **publications entry card** | same → `Card`: **radius 8 → 9** |

### kept inline
- `ResumeSections.jsx:294` (experience bullet), `:302` (suggested bullet), `:334`
  (summary), `:465` (project bullet) — **field-shaped prose rows**: r6
  (`--radius-field`), pad 8 10 / 9 11, wrapping one `BulletText` and carrying the
  ✦ tailoring tint (`--change-soft` / `--change-bg`). They are the field role, not
  the card role — a `Card` would take them to r9 and to `--line`. `// ui: keep`.
- `ResumeSections.jsx:389` — the skills **value box**: a real field
  (h29 · r6 · `--edge` · `--surface-2`) holding a bare input plus the ✦ / added /
  ↩ affordances. `// ui: keep`.
- `ResumeSections.jsx:127` — `BandRule`, a 1×11 px separator glyph. Not a band.

## CoverLetterEditor.jsx

| site | element | before → after |
|---|---|---|
| CoverLetterEditor.jsx:31 | the file's local `Card` (the three collapsible letter sections) | `1px --line · r9 · --surface` → renders `./ui`'s `Card` (imported as `UiCard`) with `padding:0` — **zero-pixel**; the local component keeps its name, its props (`title/note/open/onToggle`) and its three call sites |
| CoverLetterEditor.jsx:453 | the **¶ paragraph card** | `1px --edge · r6 · --surface` → `UiCard style={{padding:0}}`: **border `--edge` → `--card-border` (`--line`)**, **radius 6 → 9**. This is the only genuinely visible drift fix in the file — the paragraph blocks lose their heavy `--edge` outline for the standard card edge |
| CoverLetterEditor.jsx:420 | "+ Add contact item" | `v2-dashadd · h28 · 1px dashed --edge · r6 · 11.5 · --accent` → `DashedAdd` — **zero-pixel**; gains `kb()` |
| CoverLetterEditor.jsx:471 | "+ Add paragraph" | same signature with `gap:7` → `DashedAdd style={{gap:7}}` — **zero-pixel**; gains `kb()` |

### kept inline
- `CoverLetterEditor.jsx:466` — the paragraph `<textarea>`: flowing text inside the
  ¶ card's own box (no border, no background, `margin` instead of padding,
  `resize:none`). Already a D4b keep.

## Keyboard access — what changed

Every migrated **interactive** primitive goes through `act()` → `kb()`, so it is
`tabIndex=0`, announces `role="button"`, fires on Enter **and** Space, and takes
theme.css's `[tabindex="0"]:focus-visible` ring. Sites that had no keyboard access
before and now do: the Companies table row, the Applications list row, the Feed
row, both Résumés shelf rows, the Persona and base-résumé cards, the two archived
bands (Résumés, Cover Letters), the Companies "+ Add another career page" line and
both Cover Letter editor add-lines. The Cover Letters letter row goes from a
hand-rolled Enter-only handler to Enter + Space. No screen's own shortcut handler
conflicts: the Feed's `window` keydown listener does not handle Enter or Space.

## Scanner — before → after (excluding `ui.jsx`'s own definitions)

| role | before | after | migrated | remaining |
|---|---|---|---|---|
| `row` | 3 sites / 3 sigs | 2 sites / 2 sigs | 3 | the 2 remaining are the **migrated `<Row>` call sites themselves** (`Applications.jsx:428` — signature `{}`, layout only; `Companies.jsx:490` — signature `{padding}`); no inline row box is left |
| `card` | 8 / 6 | 3 / 3 | 5 | 3 segmented controls (`Applications.jsx:546`, `:823`, `CoverLetters.jsx:110`), each `// ui: keep` |
| `card-static` | 29 / 24 (+2 ToastLab, 1 sig) | 18 / 16 (+2 ToastLab, 1 sig) | 12 | 18 kept: 4 badges/checkboxes, 6 pills, 4 field-shaped prose rows, the 2 amber Persona boxes, the Login and Settings fieldwrap composites — every one carries a `// ui: keep` here or in `expected-D4b-fixup.md` |
| `band` | 3 / 2 | 0 | 3 | none |
| `dashed-add` | 16 / 13 | 4 / 4 | 12 | 4 dashed **badges** (`JobFeed.jsx:1153`, `:1200`, `ResumeEditor.jsx:876`, `:888`), each `// ui: keep` |

`ui.jsx`'s own `Row` / `Band` / `DashedAdd` definitions still register one site each
in the scan (they are the primitives); `Card`'s definition is not classified because
its hover class is dynamic.

**49 elements migrated across 11 files. Drift fixes (non-zero-pixel): 27** — 7 Stats
radii, 2 Résumés radii, 2 Cover Letters (row radius + hover, pending band radius),
4 Searches (2 card radii + 2 tracking inner radii), 6 Résumé-sections (EmptyState,
experience card + its header, education/projects/publications cards), 2 ResumeEditor
bands, and 1 each in Companies, Applications, JobFeed and CoverLetterEditor.
