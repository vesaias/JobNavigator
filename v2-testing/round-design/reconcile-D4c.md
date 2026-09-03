# reconcile-D4c — D4b→D4c diff reconciliation (incl. the D4b fix-up)

Inputs: `expected-D4b-fixup.md` (32 px fields + the Applications dead-`minHeight`
fix, applied as source-only changes ahead of D4c), `expected-D4c.md` (`Row` /
`Card` / `Band` / `DashedAdd` migrations, 49 sites across 11 files),
`artifacts/design/stylediff_D4b_D4c.md` (5670 baseline elements · 721 changed
tuples · 1172 missing · 1167 added — isolated D4b→D4c, so both the field-height
fix-up and D4c land in this one diff, matching the single commit `9ee9e9d`),
`artifacts/design/shotdiff_D4b_D4c.json` (per-shot changed-pixel bbox, isolated),
`artifacts/design/diff_D4b_D4c/*.png` (four overlays: Companies, Persona,
Searches, the cover-letter editor — all light/1440), `frontend/src/v2/ui.jsx`
(`Row`/`Card`/`Band`/`DashedAdd`/`kb()`), and `git show 9ee9e9d --
frontend/src/v2` cross-checked against current source for every migrated file.

No D0-baseline caveat applies — every number below is this step's own
contribution. Per the task's known-and-decided list, the following are **not**
re-litigated except where they explain a cascade: fields 29→32 / 30→32 and their
container cascades, textarea padding/minHeight changes, paragraph cards
`--edge`→`--line` + r6→r9, letter rows `v2-bd`→`v2-act`, `Row flush` on
Companies, and radius 10→9 / 8→9 / 8→7 canonicalisations.

## (A) 536 × `cursor: auto → default` at rest

**Source:** `ui.jsx:399`, `Card`'s own style object —

```js
cursor: live ? 'pointer' : 'default', ...style,
```

`live = interactive || !!onClick`. Every **static** `Card` (no `onClick`, no
`interactive`) now sets `cursor: 'default'` on itself. `cursor` is an inherited
CSS property with no per-child override anywhere in the migrated screens, so
that `default` cascades down through every descendant of every static card —
which is why the diff shows the change repeated on the card's own box *and*
every nested `<div>`/`<span>`/text node inside it (Stats' KPI tiles, chart
headers, the LLM-cost table, Persona's contact-grid labels and inputs' wrapper
divs, the Searches cards' whole subtree, both résumé-shelf non-clickable
regions). Before D4c these elements had no inline `cursor` at all, so the
browser's default UA behaviour (`cursor: auto`) applied — which, over a text
node, resolves to the text-selection **I-beam**. After D4c, `cursor: default`
is inherited all the way down, so hovering a text label *inside* a static card
now shows the plain arrow instead of the I-beam.

**What a user notices:** the I-beam hint disappears when hovering selectable
text inside a static card (KPI numbers, table cells, Persona field labels,
Searches summary lines). Text is **still selectable** — `user-select` is
untouched anywhere — only the cursor's visual hint is gone. This is exactly the
`live ? pointer : default` split the primitive's own comment implies (an
interactive card should look clickable, an inert one should look inert), and
it matches an existing pattern already used elsewhere in the codebase before
D4c (`Searches.jsx` already sets explicit `cursor: 'help'` / `cursor: 'default'`
on several inline elements). Every one of the 536 sites is a static (non-
interactive) card or one of its descendants — confirmed by cross-referencing
the grouped stylediff against `expected-D4c.md`'s card-static list (Stats' 7
cards minus 1 below-the-fold, Persona's 5 group cards, both résumé-route
`SectionShell` cards, the Searches search cards, and their descendant text).
No `Row`, `Band`, or interactive `Card` site appears in this bucket (`Row`'s
`cursor: onClick ? 'pointer' : 'default'` only affects clickable rows, and
every migrated Row site has an `onClick`).

**Verdict: expected (harmless).** A deliberate, if undocumented in
`expected-D4c.md`'s prose, consequence of the `Card` primitive's `live`
distinction — consistent with the project's existing explicit-cursor
conventions and worth zero action. Flagging only as a design note, not a fix:
if a future skin wants the I-beam preserved over card text, the primitive would
need to switch from `cursor: 'default'` to omitting the property (`cursor:
undefined` is unsafe per **(B)** below — use conditional spread, not an
undefined key, if this is ever revisited).

## (B) 6 × `borderTopColor/borderBottomColor rgb(226,221,208) → rgb(229,231,235)`

**This is UNEXPECTED — a real bug, not a design change.**

`rgb(229, 231, 235)` (`#e5e7eb`) is not a v2 token anywhere in `theme.css` — it
is Tailwind's/the browser's stock default border grey. Its appearance means a
border-color property was **cleared**, not intentionally recoloured.

**Trace.** Route `/v2/searches`, the six search cards (one per search),
DOM path `main>div>div.v2-scroll:1>div.v2-card:0..5` (`Searches.jsx:613`,
i.e. `expected-D4c.md`'s "the search cards" row). All six are in the **rest**
state (not `warn`, not `isOpen`) — confirmed against the visible search names
in the diff sample: JobSpy, 3 Days Levels Search, LinkedIn Recommended + Top,
Jobright 3 Days, Extension LI, Extension. Dark theme shows the identical bug,
6 more sites (`--line`'s dark value `rgb(62,59,50)` → the same
`rgb(229,231,235)`), for 12 element-state entries total; the task's "6 ×" is
the light-theme grouped line, its dark twin appears as its own grouped line
right below it in `stylediff_D4b_D4c.md`. Overlay confirmation:
`diff_D4b_D4c/v2_searches__light__1440.png` outlines the full 1px border ring
of all six cards, not just their radius corners — consistent with a
border-color regression across the whole box, not a positional/radius-only
change.

**Root cause — `frontend/src/v2/Searches.jsx:614`:**

```js
<Card key={s.id} className={isOpen ? undefined : warn ? 'v2-card v2-bd-warn' : 'v2-card'}
  style={{ padding: 0, borderColor: warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : undefined, display: 'flex', flexDirection: 'column' }}>
```

When neither `warn` nor `isOpen` is true, `style.borderColor` is `undefined` —
but the key `borderColor` is still **present** in the object (`{...style}` is
spread onto `Card`'s own `style={{ ..., border: '1px solid var(--card-border)',
..., ...style }}` at `ui.jsx:397-399`). React does not skip a style key whose
value is `null`/`undefined`; it explicitly clears that CSS property on the DOM
node. Since `border` (the shorthand, setting `border-color: var(--card-border)`
among other things) is applied first in the same style object and `borderColor`
is applied after, the later `borderColor: undefined` **clears the border-color
half of the shorthand specifically**, leaving `border-width`/`border-style`
alone. With no inline `border-color` left, the box falls through to whatever
the page's CSS cascade supplies for an unstyled border — in this Tailwind-based
app that's the Preflight/browser default grey, `#e5e7eb`, exactly the value
observed.

**Confirms the pattern is a real bug, not a coincidence:** `CoverLetters.jsx:308`
has the *same kind* of conditional card tint and gets it right —

```js
style={{ ..., ...(arc ? { borderColor: 'var(--line-soft)', background: 'var(--recessed)' } : null) }}
```

— spreading `null` (which contributes **no keys at all**) instead of an object
whose `borderColor` key is present-but-`undefined`. `Searches.jsx:614` should
follow the identical shape.

**Fix (`frontend/src/v2/Searches.jsx:614`):** replace the inline ternary's
`undefined` fallback with a real value, or switch to a conditional spread so the
key is absent instead of present-and-undefined:

```js
style={{ padding: 0, ...(warn ? { borderColor: 'var(--warn-line)' } : isOpen ? { borderColor: 'var(--accent)' } : null), display: 'flex', flexDirection: 'column' }}
```

(equivalently, `borderColor: warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : 'var(--card-border)'` also works, but the conditional-spread form matches the codebase's own established pattern one file over.)

One unrelated single-count anomaly surfaced by the same grep for
`rgb(229,231,235)`: a **hover** diff at
`/v2/cover-letters/{id}|…>span.v2-bd.v2-ctl>span:2|▾` (the length-picker's ▾
glyph) shows `borderTopColor rgb(229,231,235) → rgb(63,107,82)` alongside
completely unrelated property jumps (`fontSize 9px→11.5px`, `height 9px→24px`).
This is **not** the same bug — `LengthPicker` is explicitly kept inline per
`expected-D4c.md` (not a `Card`/`Row`/`Band`/`DashedAdd` site) and the
magnitude of unrelated property change (a 9px glyph becoming a 24px control)
indicates the crawler paired two *different* DOM elements at a reused path
(a conditional-render index collision), the same class of artifact
`reconcile-D4a.md`/`reconcile-D4b.md` already established as crawl noise.
Flagged for completeness, not actioned.

## Verdict table — grouped changes

| change (state · prop · old→new) | count | verdict | evidence |
|---|---|---|---|
| rest · cursor `auto`→`default` | 536 | expected (harmless) | see **(A)** — `ui.jsx:399` `Card`'s `live` split, inherited into every static card's subtree |
| hover · cursor `auto`→`default` | 4 | expected (harmless) | Stats LLM-cost table head/gutter hover states, same inheritance as (A) |
| rest · height 29px→32px | 58 | expected (known/decided) | `Input` canonical h32 (D4b fix-up), all `Input`/`Field`/`MicroField`/`Cell` sites |
| rest · height 30px→32px | 14 | expected (known/decided) | boxed `SearchInput` + `v2-fieldwrap` composites (D4b fix-up) |
| rest · height 48px→51px | 30 | consequence | `<label>` wrapper tracking the +3 Input height (ResumeSections `Field`/`MicroField`, Persona) |
| rest · height 47px→50px | 22 | consequence | Persona `AutofillField` row wrapper tracking the same +3 |
| rest · height 763px→762px, 598px→597px, 595px→594px (rest+hover), 559px→558px, 725px→724px | 14+6+2+6+4+2 | consequence | page-header rows grow +1 (SearchInput/fieldwrap 30→32), so the sibling flex-1 scroll body loses 1px to sub-pixel rounding — Feed, Companies, Applications, cover-letters list |
| rest · borderRadius 10px→9px | 24 | expected (known/decided) | Stats' 7 `Card` users (6 visible), Résumés/Persona/Searches card canonicalisation |
| rest · borderRadius 8px→7px | 20 | expected (known/decided) | `JobFeed.jsx:879` feed row → `--radius-row` |
| rest · borderRadius 8px→9px, hover · borderRadius 8px→9px | 12+6 | expected | `ResumeSections.jsx:267` experience card + `:271` its collapsible header tracking it (hover is the same header's `.v2-hover-accent` class) |
| rest · borderTopColor/borderBottomColor rgb(226,221,208)/(62,59,50) → rgb(229,231,235) | 6+6 | **UNEXPECTED** | see **(B)** — `Searches.jsx:614` |
| rest · borderTopColor/borderBottomColor `--edge`→`--line` (light rgb(138,130,110)→rgb(226,221,208), dark rgb(127,122,102)→rgb(62,59,50)) | 3+3+3+3 | expected | `CoverLetterEditor.jsx:453` ¶ paragraph card, documented border+radius drift fix |
| rest · height 92px→83px, 73px→64px, 66px→64px, paddingTop 7px→5.5px | 2 each | expected (D4b fix-up) | `Applications.jsx:655` notes box — `rows={3}`→`rows={2}` makes the `minHeight:64` floor effective again, restoring the pre-D4b 83/64 px look |
| rest/hover · height 396px→414px, 354px→372px, 1403px→1412px, 1363px→1372px, 1344px→1353px, 1199px→1208px, 1161px→1170px, 112px→118px, 1121→1130/1102→1111/957→966/919→928, 605→599 &c (résumé/cover-letter mirrors) | 2-6 each | expected (known/decided) | field-height + card-radius container cascade, Persona/résumé/cover-letter left columns |
| hover · backgroundColor rgb(255,255,255)→rgb(244,248,245) (light), rgb(40,37,27)→rgb(46,43,32) (dark); hover · borderRadius 10px→9px | 1+1+2 | expected | `CoverLetters.jsx:308` letter row `v2-bd`→`v2-act`: gains the `--card-bg-hover` wash on hover, exactly as documented |
| hover · color/borderTopWidth/borderTopColor/borderBottomColor/borderRadius/fontSize/lineHeight/paddingLeft/height (the ▾ glyph) | 1 each | noise (crawl-path collision) | see **(B)**'s closing note — unrelated to any D4c primitive, magnitude of change (9px→24px) indicates a mismatched pairing, not a real single-element diff |

**One UNEXPECTED item: `Searches.jsx:614`'s `borderColor: undefined`, item (B) above.** Everything else in the grouped table is expected or a documented/mechanical consequence.

## Checks (1)–(6)

### (1) 1172 missing / 1167 added — the 5-element imbalance

The exported `stylediff_D4b_D4c.md` truncates both the "Missing in D4c" and
"Added in D4c" enumerations at exactly 300 lines each (the file ends mid-entry,
with no "…N more" marker) even though the header states the true totals
(1172/1167) — so the full pairing cannot be walked by hand from this artifact.
The visible 300-line sample is fully explained by one mechanism, with no
evidence of anything silently missing:

- **Companies rows dominate the sample (297 of 300 missing, 300 of 300
  added).** Old class string: `div.v2-crow`. New: `div.v2-row.v2-crow` —
  because `Row` always prepends its own `v2-row` class (`ui.jsx:370`,
  `cx('v2-row', className)`) ahead of the caller's `className="v2-crow"`
  (`Companies.jsx:490`). The crawl's element-matcher keys off the exact class
  string, so every row — and every one of its ~30 descendant spans (tier
  badge, health text, ATS badge, apps/fit numbers, the sticky actions cell and
  its three action spans) — is reported as one `div.v2-crow` element vanishing
  and one `div.v2-row.v2-crow` element appearing at the identical position with
  identical children/text (`Oracle`, `Addepar`, `Adobe`, … pair up 1:1 between
  the two sections at the same offsets). This is a pure rename artifact
  (the same class of "path-rename" false-positive documented in
  `reconcile-D4a.md`/`reconcile-D4b.md`), not element loss — confirmed
  directly against `Companies.jsx:490`'s source and `Row`'s definition. With
  ~120+ companies × ~30 descendants × 2 themes, this single mechanism plausibly
  accounts for nearly all of both the 1172 and the 1167 — and being a 1:1
  rename, it contributes **net 0** to the imbalance.
- **The one genuine asymmetry in the sample:** `light|/v2/feed|…
  div.v2-row:9>div:0>div:1>div:1` and its two child spans (`"AIS (Applied
  Information…"`, `"United States"`) appear as **missing with no Added
  counterpart anywhere in the visible sample** — 3 lines, one theme. `Row`'s
  own migration at `JobFeed.jsx:879` is documented zero-pixel/layout-only in
  `expected-D4c.md`, and nothing else on that route changed structurally, so
  this reads as **live data drift** between the two crawl runs (that specific
  job's content or rank changed) — the same category `reconcile-D4b.md §(3)`
  already established for the Résumés shelf's cardinality drift, not a code
  regression.
- Given the sample is capped before reaching the dark-theme Companies rows or
  the tail of the light-theme company list, I cannot enumerate all five of the
  net-imbalance elements by name from this artifact alone. But the shape is
  clear: a bulk, exactly-1:1, path-rename mechanism (net 0) dwarfing a handful
  of small, asymmetric, content-only drift lines (net ≈ a few, in the same
  direction and same character as the visible Feed example) — nothing in
  either category is an element that a user would notice missing. **Not
  blocking**; if the exact 5 need to be named, re-run the crawl twice
  back-to-back on D4c alone (no code change between runs) and diff those two
  outputs — any survivors are guaranteed live-data drift, not migration loss.

### (2) Hover on migrated interactive cards/rows still changes

Checked every `hover` line in `stylediff_D4b_D4c.md` (17 total) against the
migrated `.v2-act`/`.v2-row`/`.v2-crow`/`.v2-arow`/`.v2-card` sites:

- **`CoverLetters.jsx:308`** (letter row, `v2-bd`→`v2-act`) is the one site
  `expected-D4c.md` documents as *gaining* a hover effect (a `--card-bg-hover`
  wash where before there was only an accent border) — and it is exactly the
  one hover line that fires: `backgroundColor rgb(255,255,255)→rgb(244,248,245)`
  light / `rgb(40,37,27)→rgb(46,43,32)` dark, plus `borderRadius 10px→9px`
  tracking the row's own radius fix. This confirms the hover migration is real
  and rendering, not silently dropped.
- **Every other migrated interactive site — Companies rows, Applications rows,
  the Résumés/Persona cards, the Searches summary click — produces *no* hover
  diff line at all.** That is exactly what "zero-pixel" hover-equivalence
  predicts (`expected-D4c.md`: `Companies.jsx:490` "`.v2-crow:hover
  .v2-cactions` … `.v2-row` from the primitive hovers to the identical
  `--row-hover`"; `Applications.jsx:428` "zero-pixel"; Résumés cards "hover
  `v2-card`→`v2-act` is zero-pixel — theme.css gives both rules the identical
  accent-border + `--card-bg-hover`"). An absence of a diff line here is
  corroborating evidence the hover CSS is unchanged, not evidence hover broke —
  the diff tool only emits a line when a value differs.
- The remaining hover lines are all **consequences**, not migrations: two
  1px height-rounding lines (Feed/Applications scroll containers, tracking the
  same rest-state rounding as in the verdict table), the `SectionShell` header
  radius tracking its card (`ResumeSections.jsx:271`, 4 sites), and the two
  Stats LLM-table cursor lines from **(A)**.

**No hover regression found.**

### (3) Feed rows still carry `[data-row]`

`frontend/src/v2/JobFeed.jsx:879` — `<Row key={j.id} data-row={i} divider
onClick={…}`. `Row` (`ui.jsx:367`) destructures `...rest` and spreads it onto
the rendered `<div {...rest} …>` before its own props, so `data-row` passes
through untouched. `JobFeed.jsx:562`'s `scrollIntoView` query
(`` `[data-row="${sel}"]` ``) still resolves. Confirmed directly in source —
no diff evidence needed since this is a DOM attribute, not a style property.

### (4) Persona 267k / cover-letter-editor 66k — cascade + paragraph cards, nothing else

- **Persona** (`v2_persona__light__1440.png`, 267,425 px): every red region
  traces to either (a) the field-height cascade already established as
  known/decided (every `label`/`AutofillField` row +3px, cascading through the
  column's container chain — the dashed-outline-only regions in the overlay)
  or (b) the five group cards' migration to `Card` (`Persona.jsx:347`,
  documented zero-pixel token match) plus **(A)**'s inherited
  `cursor:default` (which paints no pixels itself but the crawl's diff
  highlighter still outlines any element with *any* changed computed style,
  cursor included — explaining why plain, unstyled text spans like "First
  name"/"Last name" show as outlined even though their rendered pixels are
  identical). No unexplained region.
- **Cover-letter editor** (`v2_cover-letters_ce44e1d4…__light__1440.png`,
  66,313 px): for this specific letter, the Header and Recipient sections are
  collapsed by default, so the only visible content is the Letter section —
  the three ¶ paragraph cards (`CoverLetterEditor.jsx:453`, border `--edge`→
  `--card-border` + radius 6→9, a real edge-color change, hence the *solid*
  fill rather than a dashed outline in the overlay) and the "+ Add paragraph"
  `DashedAdd` beside them. Nothing else on the visible page changed. Matches
  the task's framing exactly: field-height cascade (not visible here because
  the field-bearing sections are collapsed) plus the paragraph cards — and for
  *this* record, effectively all of the 66k is the paragraph cards since the
  cascade sections aren't rendered.

### (5) Settings 1.4k at (1180,43,1410,75) — which control

Only one Settings element changed in the entire diff:
`main>div>header>div.v2-fieldwrap:1` rest · `height 30px→32px` (light+dark).
This is `Settings.jsx:487`'s header "Search settings…" `v2-fieldwrap`
composite, documented in `expected-D4b-fixup.md` ("header 'Search settings…' —
same r99 composite | height 30 → 32"). The bbox (top-right corner of the page,
~230px wide, 32px tall) matches a single search box sitting in the page header
exactly. **Expected**, and the only change on the whole Settings screen —
consistent with `expected-D4c.md`'s own note that Settings "has no card, row,
band or dashed-add site in the scan" for D4c itself.

### (6) Stats ≤518px — which

All non-cursor Stats changes are `borderRadius 10px→9px` on 6 of the 7
`Card` sites (`Stats.jsx:421/443/492/517/533/579` — KPI strip, funnel, score
distribution, timeline, LLM cost, scheduler). `cursor:auto→default` changes
are computed-style-only and paint zero pixels, so the entire 441-518px
shot-diff range (light/1440 = 518, the largest) is the four-corner
antialiased sliver from six cards' radius shrinking by 1px — roughly
6 cards × 4 corners × a few px each, which is exactly this order of magnitude.
The 7th `Card` (Run history, `id="runs"`, `Stats.jsx:629`) shows **no** diff
line at all — confirmed it *is* migrated in current source
(`<Card id="runs" ref={runsCardRef} …>`), so its absence is a below-the-fold
coverage gap (it's the last card on the page, past the crawl's captured
viewport height), the same limitation already established for overlay
coverage in `reconcile-D4b.md`. Not a sign it was skipped.

## Spot-checks against source (all confirmed shipped as documented)

- `Stats.jsx` — local `CARD` object deleted; all 7 sites are `<Card …>` (421, 443, 492, 517, 533, `ref={schedRef}` 579, `id="runs" ref={runsCardRef}` 629).
- `Companies.jsx:118` — `<DashedAdd onClick={…}>+ Add another career page</DashedAdd>`.
- `Companies.jsx:490` — `<Row flush divider onClick={…} className="v2-crow" …>`.
- `ResumeSections.jsx:19` — `export { DashedAdd } from './ui'`; all 8 call sites unchanged.
- `CoverLetterEditor.jsx:29-49` — local `Card` wraps `UiCard` (imported as `Card as UiCard`) with `padding:0`; the ¶ card at `:453` has no `borderColor` override (correctly inherits `--card-border`).
- `Searches.jsx:585/692` — both inline-form bottom corners at `borderBottomLeftRadius/borderBottomRightRadius: 8`.
- `Resumes.jsx` — `Card`/`Band` imported and used at 178/195/210/253 (`onClick` cards) and 165/176/193/294 (`Band`).
- `CoverLetters.jsx:308` — letter row uses `...(arc ? {borderColor, background} : null)` — the **correct** conditional-spread pattern that `Searches.jsx:614` should be fixed to match.
- `ResumeEditor.jsx:713/806` — both `<Band interactive={false} …>No base résumés yet./No jobs match…</Band>`.
- `Applications.jsx:655/835` — the D4b-fixup's `rows={2}` + kept `minHeight` floor, both sites, matching `expected-D4b-fixup.md` exactly.
- `JobFeed.jsx:879` — `<Row data-row={i} divider onClick={…} style={{height:'auto', alignItems:'stretch', gap:0, padding:0, …}}>`; `:562` still queries `[data-row="${sel}"]`.

## Final list: UNEXPECTED

**One item.**

| file:line | issue | fix |
|---|---|---|
| `frontend/src/v2/Searches.jsx:614` | `style={{ …, borderColor: warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : undefined, … }}` — the rest-state `undefined` is spread as a present-but-empty `borderColor` key, which React resolves by clearing the border-color half of `Card`'s `border` shorthand, exposing the Tailwind/browser default grey `#e5e7eb` (`rgb(229,231,235)`) instead of `var(--card-border)` on all 6 search cards (12 element-state entries across both themes) | Switch to a conditional spread so the key is absent in the rest case — `...(warn ? { borderColor: 'var(--warn-line)' } : isOpen ? { borderColor: 'var(--accent)' } : null)` — mirroring the already-correct pattern at `CoverLetters.jsx:308`. (Equivalently: `borderColor: warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : 'var(--card-border)'`.) |

Everything else — the 536× inherited `cursor:default` from `Card`'s `live`
split (item **A**, expected/harmless), all height/radius cascades from the
pre-approved 32px field decision and the radius canonicalisations, the
Applications notes-box `minHeight` fix, the CoverLetterEditor paragraph-card
border/radius drift fix, and the Companies `.v2-crow`→`.v2-row.v2-crow`
rename inflating the missing/added counts — traces cleanly to
`expected-D4b-fixup.md`/`expected-D4c.md` or a mechanical, documented
consequence of one. No migrated element lost keyboard access, hover feedback,
or its `data-*` hooks. D4c is clean to proceed once `Searches.jsx:614` is
fixed.
