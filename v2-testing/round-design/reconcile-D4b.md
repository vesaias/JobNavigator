# reconcile-D4b — D4a→D4b diff reconciliation

Inputs: `expected-D4b.md`, `artifacts/design/stylediff_D4a_D4b.md` (5688 baseline
elements · 144 changed tuples · 54 missing · 36 added — isolated D4a→D4b),
`artifacts/design/shotdiff_D4a_D4b.json` (per-shot changed-pixel bbox, isolated
D4a→D4b), `artifacts/design/diff_D4a_D4b/*.png` (two overlays exist:
`v2_applications__light__1440.png`, `v2_persona__light__1440.png` — see the
"Overlay images" section for why Searches/Settings have none), `frontend/src/v2/ui.jsx`
(`Input`/`Textarea`/`SearchInput`/`Select`, `theme.css` focus rules), and the D4b
code commit `bc3d351` ("v2 design pass D4b: inputs, textareas, search fields and
selects…") cross-checked against `ResumeSections.jsx`/`CoverLetterEditor.jsx`/
`Applications.jsx` source to confirm two items below.

Unlike D4a's shotdiff/overlays (which diffed against D0), `stylediff_D4a_D4b.md`
and `shotdiff_D4a_D4b.json` are **both isolated to this step** (D4a→D4b), so no
D0-baseline caveat applies here — every number below is D4b's own contribution.

**Per the task's known-and-decided list:** every `30→29` height row and its
container-shrink cascade is the pre-approved field-height decision (will move to
32 next round) — not re-litigated below except where it explains a bbox number.

## Changes grouped — verdicts

| change (state · prop · old→new) | count | verdict | evidence |
|---|---|---|---|
| rest · height 30px→29px | 30 | expected | `Input` canonical h29. `ResumeSections.jsx:151` MicroField sites + `Persona.jsx:142` AutofillField (label-wrapped subset) — both documented `height 30→29` |
| rest · height 49px→48px | 30 | consequence | the `<label>` wrapping each of the above inputs grows/shrinks 1px to track the input's own −1 |
| rest · height 48px→47px | 22 | consequence | `Persona.jsx:142` AutofillField (fieldwrap-wrapped subset, 11 sites × 2 themes) — row wrapper shrinks 1px as its child goes from `v2-fieldwrap` (h30) to bare `Input` (h29) |
| rest · fontSize 13px→12.5px | 8 | expected | `Applications.jsx:651` notes textarea (2: light/dark) + `CoverLetterEditor.jsx:380/430.../481`-family INPUT sites, 3 of 8 rendered in the `ce44e1d4` fixture (6: 3 sites × 2 themes) — all documented `font-size 13→12.5` |
| rest · height 1164px→1161px | 6 | consequence | page-container cascade: `Persona.jsx` left column + `resumes/22ce…` + `resumes/d28bbd9e…` (nested), each −3 from the Field/AutofillField height chain |
| rest · height 114px→112px | 6 | consequence | same cascade, one level in (Persona `div:0>div:1` row-group + both résumé routes) |
| rest · lineHeight 19.5px→18.75px | 6 | consequence | `v2-ctl`-style line-height tracking `CoverLetterEditor.jsx` INPUT font-size bump (13→12.5 ⇒ 19.5→18.75 at the same 1.5 ratio) |
| rest · paddingLeft 10px→9px | 6 | expected | `CoverLetterEditor.jsx` INPUT sites, documented `padding 0 10px → 0 9px` |
| rest · height 32px→29px | 6 | expected | `CoverLetterEditor.jsx` INPUT sites, documented `height 32→29` |
| rest · height 52px→49px | 6 | consequence | `CoverLetterEditor.jsx` contact-item row + its two children, tracks the row's inputs shrinking |
| rest · height 1406px→1403px | 4 | consequence | `Persona.jsx` outer scroll container + `resumes/d28bbd9e…` outer container, −3 top-of-cascade |
| rest · height 1366px→1363px | 4 | consequence | same cascade, one level in |
| rest · height 1347px→1344px | 4 | consequence | same cascade |
| rest · height 1202px→1199px | 4 | consequence | same cascade |
| rest · backgroundColor rgb(255,255,255)→rgb(246,244,238) | 3 | expected | see **(5)** below — `CoverLetterEditor.jsx` INPUT, light theme, `--surface`→`--input-bg` |
| rest · backgroundColor rgb(40,37,27)→rgb(50,47,36) | 3 | expected | same, dark theme |
| rest · height 83px→92px | 2 | consequence | see **(6)** below — `Applications.jsx:651` notes-box wrapper, tracks the textarea's own +9 |
| rest · borderRadius 8px→6px | 2 | expected | `Applications.jsx:651`, documented `radius 8→6` |
| rest · lineHeight 20px→19px | 2 | expected | `Applications.jsx:651`, documented `line-height 20→19` |
| rest · paddingTop 10px→7px | 2 | expected | `Applications.jsx:651`, documented `padding 10px 12px → 7px 9px` |
| rest · paddingLeft 12px→9px | 2 | expected | `Applications.jsx:651`, same |
| rest · height 64px→73px | 2 | consequence | see **(6)** below — the notes textarea itself; not the direction the padding change alone implies |
| rest · height 402px→396px, 360px→354px | 2+2 | consequence | `Persona.jsx` right-column container cascade, top of the AutofillField/fieldwrap chain |
| rest · height 1124px→1121px, 1105px→1102px, 960px→957px, 922px→919px | 2 each | consequence | `resumes/22ce0e5b…` container cascade (mirrors the 1406/1366/1347/1202 chain for the other résumé) |
| rest · height 605px→599px, 563px→557px, 62px→59px | 2 each | consequence | `cover-letters/ce44e1d4…` container cascade above the INPUT sites |
| rest · backgroundColor rgb(252,251,247)→rgb(246,244,238) | 1 | expected | `Applications.jsx:651`, light, `--bg`→`--input-bg` (Applications' own background token, not `--surface`) |
| rest · color rgb(87,83,74)→rgb(27,26,22) | 1 | expected | see **(2)** below — `Applications.jsx:651` ink fix, light |
| rest · borderTopColor / borderBottomColor rgb(226,221,208)→rgb(138,130,110) | 1+1 | expected | `Applications.jsx:651`, documented `border --line → --input-border` |
| rest · backgroundColor rgb(30,28,23)→rgb(50,47,36), color rgb(203,199,191)→rgb(217,215,208), borderTop/BottomColor rgb(62,59,50)→rgb(127,122,102) | 1 each | expected | `Applications.jsx:651`, dark twins of the four rows above |

**No UNEXPECTED entries in the grouped table.** Every one of the 144 changed
tuples traces to a documented `expected-D4b.md` row or a mechanical consequence
of one (a `<label>`/row/container shrinking because the field or wrapper it
holds changed height). I spot-checked every distinct prop/value pair against
its site; none require a code fix.

## Missing / Added — the 54-vs-36 imbalance, reconciled

Per theme (light and dark are identical in structure, so the count halves
cleanly): **27 missing, 18 added, net 9**. × 2 themes = the 54/36/**18** gap
named in the task. Three independent causes, none a lost element:

1. **Feed** (`main>div>div:0>div:0>…`) — old: `span:0|⌕` + `span:1` (wrapper) +
   `span:1>input` (3 nodes). New: `span` (wrapper) + `span>span|⌕` + `span>input`
   (3 nodes). Like-for-like restructuring, **3 missing / 3 added, net 0** — this
   is `JobFeed.jsx:735`'s `SearchInput`.
2. **Resumes + Cover Letters headers** — old: a **bare** `input` (1 node, no
   wrapper existed). New: `SearchInput`'s own `span` wrapper + `span>input` (2
   nodes) — the primitive always wraps. **1 missing / 2 added each, net +1 each
   (−2 to the imbalance, per theme)** — `Resumes.jsx:154`, `CoverLetters.jsx:331`.
3. **Persona's 11 visible `v2-fieldwrap`-wrapped AutofillField text sites**
   (`main>div>div:0>div:1>div.v2-scroll:1>div:0>div:1>div:0..10`) — old:
   `div:N > div.v2-fieldwrap > input` (2 nodes per site: the wrapper, and the
   input nested inside it). New: `div:N > input` (1 node — the wrapper is
   **genuinely gone**, not renamed: `Input` styles the bare input directly).
   **2 missing / 1 added per site, net +1 missing-heavy per site × 11 sites = +11
   per theme.**

Net per theme: 0 (Feed) − 2 (Resumes+CoverLetters) + 11 (Persona) = **9** →
× 2 themes = **18**, exactly the 54−36 gap. The wrapper removal in (3) is not a
diff-tool artifact like D4a's path-rename cases — it's confirmed as an intended,
documented structural simplification by `expected-D4b.md`'s own language:
*"focus signal moves from the wrapper (`v2-fieldwrap:focus-within`) to the
input's own border"* — that sentence only makes sense if the wrapper element is
actually removed. Verified directly against `ui.jsx`'s `Input` (renders a bare
`<input>`, no wrapping element) vs. the pre-D4b `BOX`/`v2-fieldwrap` pattern
still visible at kept-inline sites (e.g. `Settings.jsx:86`). **Not a lost
element — a real, intended, and correctly-documented node count reduction.**

(11-of-15 AutofillField text sites is itself a coverage gap, not a miss: the
other 4 are presumably below the crawl's captured viewport for this route,
matching the same partial-capture pattern D4a already established for pill
hovers — see D4a §"hover · height auto→17.25px" precedent.)

## Focus check — no migrated field lost its focus signal

`theme.css` carries three independent focus rules (lines 404/407/410):

```css
.jn-v2 input:focus-visible, .jn-v2 textarea:focus-visible, .jn-v2 select:focus-visible { border-color:var(--input-border-focus) !important; outline:none; }
.jn-v2 .v2-fieldwrap:focus-within { border-color:var(--input-border-focus) !important; }
.jn-v2 [tabindex="0"]:focus-visible { outline:none; box-shadow:0 0 0 2px var(--focus-ring); }
```

- **`Input` / `Textarea` / `SearchInput`** (`ui.jsx:205-262`) all render a bare
  native `<input>` or `<textarea>` with no wrapping element and no focus styling
  of their own. The first rule is a **bare tag selector** — `input:focus-visible`
  / `textarea:focus-visible` — not scoped to any class, so it fires on every one
  of the 54 migrated sites automatically, with zero possibility of a site
  "forgetting" to opt in. Confirmed by reading `ui.jsx:205-262` line by line: no
  site overrides `className` in a way that could exclude it.
- **`Select`** (`ui.jsx:280-340`) renders a `<div>` trigger, not a native field —
  it goes through `act(toggle, disabled)` which spreads `kb(fn)` (`ui.jsx:52`),
  giving it `tabIndex={0}`, so the third rule (`[tabindex="0"]:focus-visible`)
  applies. This is the same ring mechanism already reconciled clean for
  `Button`/`Pill`/`IconButton` in D4a — `Select`'s trigger also keeps its
  accent-border-while-`open` (a JS state, not a focus pseudo-class), so keyboard
  users get both the state border and the ring; no regression.
- **Kept-inline composites** (`LoginModal.jsx:70`, `Applications.jsx:350`,
  `Settings.jsx:86/735/790/979`, `Stats.jsx:661`) are untouched by D4b and keep
  `.v2-fieldwrap:focus-within` (second rule) exactly as before.
- **Persona's 11 fieldwrap→bare-input sites** are the one place the mechanism
  actually *changes* (rule 2 → rule 1, per the Missing/Added trace above) —
  confirmed this is not a loss: both rules produce the identical visual
  (`border-color: var(--input-border-focus)`), so the swap is behaviorally
  zero-pixel even though the DOM shrank by one node.

**No migrated site was found whose class/wrapper would fail to receive a focus
signal.**

## (2) The two ink drift-fixes

- **Applications notes box** (`Applications.jsx:651`) — fully captured and
  quantified: `color rgb(87, 83, 74) → rgb(27, 26, 22)` (light, `--text-2` →
  `--input-ink`/`--text`) and its dark twin `rgb(203, 199, 191) → rgb(217, 215,
  208)`, each count 1 in the grouped table, matching the single notes-box
  element on the single Applications-detail route in the crawl. **On the
  expected list** (`expected-D4b.md` §Applications.jsx, row `:651`, "ink
  `--text-2` → `--input-ink` (`--text`)").
- **Contact URL cells** (`ResumeSections.jsx:228`, `CoverLetterEditor.jsx:405`)
  — **not captured anywhere in `stylediff_D4a_D4b.md` or `shotdiff_D4a_D4b.json`**
  for either résumé route (`22ce0e5b…`, `d28bbd9e…`) or the cover-letter route
  (`ce44e1d4…`). I read both source files directly to confirm the fix is real
  and already in place: both URL-cell call sites are now a plain
  `<Input value={…url} style={{flex:1,minWidth:0}} />` with **no** `fontSize`
  or `color` override — the old `{...cellInput/CELL, fontSize:11.5,
  color:'var(--text-2)'}` spread is gone, so the field now inherits `Input`'s
  default 12.5/`--input-ink` exactly as `expected-D4b.md` documents. The crawl
  simply doesn't exercise this: none of the three fixture routes' captured diff
  regions touch a `header.contact_items` row with a populated `url` (the
  visible cascades for those routes are the "Full name"/label-grid sections
  traced above, not the contact-item block), so this is a **crawl-coverage
  gap**, the same category as D4a's partial pill-hover capture — not a
  regression, and **on the expected list** (rows `ResumeSections.jsx:228`,
  `CoverLetterEditor.jsx:405`).

## (3) Résumés shelf, `/v2/resumes` (list, no id), 1024 dark — 215,863 px

**Noise (data drift), not a D4b code effect.** Evidence:

- The isolated `stylediff_D4a_D4b.md` records **zero** structural/style changes
  for the bare `/v2/resumes` route other than the header search field's
  wrapper-node rename (Missing/Added case 2 above — 1 vs 2 nodes, no property
  delta beyond what `Resumes.jsx:154` already documents as a small padding
  change). If a real reflow were happening on this page, the card grid or
  header row below it would show up as changed-property rows (heights, at
  minimum); none exist.
- The **same route, same theme family, wider viewport** —
  `v2_resumes__dark__1440.png` — shows only 7,423 px in a bbox confined to
  `(973, 39)–(1440, 222)`, the top-right corner where the header/search box
  lives. Same code, same components, a 30× smaller and topologically different
  diff. A real CSS regression from the `SearchInput` swap would reproduce at
  both widths; it doesn't.
- The magnitude is nearly identical between **light and dark** at 1024
  (215,863 vs 216,443) — consistent with a *content* difference (résumé/copy
  count, list length, relative timestamps — all theme-independent), not a
  theme-CSS bug, which would produce different numbers between the two palettes.
- `Resumes.jsx`'s list is driven by live `bases`/`archived`/copy counts
  (`useEffect` polling, `useMemo`-derived `results`) — exactly the kind of
  between-crawl-runs data drift D4a already established for `Companies.jsx:521`
  ("+N this week"), just at list-cardinality scale instead of one span's text.

**Limitation:** no overlay PNG exists for `/v2/resumes` (the task's four image
paths cover Persona/Searches/Applications/Settings only), so this conclusion is
inferred from the numbers, not eyeballed. Given the isolated style-diff — the
authoritative D4a→D4b source per this reconciliation's own method — shows
nothing on this route, this does not block, but flag it for a fresh single-page
crawl if the number needs to be fully closed out.

## (4) Persona, 1440 — 233,265 (dark) / 234,129 (light) px

**Expected**, and fully traced (not just inferred) in `stylediff_D4a_D4b.md`.
Persona has two long stacked columns, and D4b's canonical-height changes hit
both:

- **Left "Résumé content" column** reuses `ResumeSections.jsx`'s `Field`
  (`:66`) / `MicroField` (`:151`) — the same primitives the `/v2/resumes/{id}`
  editor uses (Persona's `resume_content` node mirrors the Resume JSON shape).
  Every labelled cell there goes `30→29` with its `<label>` wrapper `49→48`,
  cascading up through the column's container chain to `1406→1403` at the top —
  the exact chain visible in rows 53-68 of the "Changed elements" section.
- **Right "Autofill content" column** — `Persona.jsx:142`'s AutofillField text
  sites (`30→29`, wrapper-row `48→47`, cascading to `402→396`/`360→354`) plus
  the `Picker`→`Select` migration elsewhere in the same column.

Because Persona stacks contact/demographics/work-auth/screening/Q&A-bank rows
one after another with no independent scroll offset between them, every row
below any shrunk field shifts up by 1-3 cumulative px — which is why the
overlay (`v2_persona__light__1440.png`) shows almost the entire visible page
outlined, not just the migrated boxes themselves. Confirms visually:

- Left-column `Field` boxes (height-only change, no background/color delta per
  `expected-D4b.md`) render as **thin dashed outlines** — only the border edge
  moved.
- Right-column `AutofillField` boxes (`background --surface → --input-bg` is a
  real color change) render as **solid red fill** — every non-text pixel in the
  box differs, not just its edge.
- The Q&A-bank text further down (unchanged, kept-inline `BulletText`, not a
  D4b site) is still outlined — pure position drift from the cascade above it,
  not a content change.

This internal consistency (dashed vs. solid matching exactly which sites do/
don't have a background-color delta) is strong corroboration that the whole
233k/234k is the pre-approved height cascade and nothing else. Matches the
task's own "known and decided" note about container shrink being expected.

## (5) `backgroundColor rgb(255,255,255)→rgb(246,244,238)` ×3 (+ dark twin ×3)

`CoverLetterEditor.jsx` INPUT-class sites (`:380` "Full name", plus two more of
the file's 8 INPUT call sites rendered in the `ce44e1d4` fixture — the row-pair
under `div:5`, most likely two of Recipient/Greeting/Closing/Signature). Each
is `expected-D4b.md`'s documented **"background `--surface` → `--input-bg`
(`--surface-2`)"** for every `INPUT`-style call site (`:380/430/434/438/442/
451/477/481`, "same four changes" as `:380`). Light `--surface` = rgb(255,255,
255), `--input-bg` = rgb(246,244,238); dark twin `--surface` = rgb(40,37,27),
`--input-bg` = rgb(50,47,36) — token values match exactly. **Expected.** Only
3 of the file's 8 INPUT sites appear because the other 5 (Recipient fields,
Greeting, Closing, Signature) aren't populated/visible in this fixture's
captured region — a coverage gap, not a miss (the delta itself, when it does
appear, is exactly the documented one).

## (6) The two `height 83px → 92px` rows

`Applications.jsx:651`'s notes-box **wrapper** div. Direct downstream of the
notes **textarea** itself, which is the paired `64px → 73px` row two lines
above it in the "Changed elements" list — same element family, same 2 rows
(light/dark), +9 each, container tracking child exactly.

Traced precisely from source (`Applications.jsx:653`: `<Textarea key={d.id}
defaultValue={…} rows={3} style={{ minHeight: 64 }} />`) and `ui.jsx`'s
`Textarea` (`padding: '7px 9px', lineHeight: '19px', …, ...style` — `style`
spreads *last*, so the caller's `minHeight:64` does win over the component's
own `rows*20` fallback in the *inline style itself*). The catch is that
`rows={3}` also sets the native HTML `rows` attribute, which the browser uses
to compute the textarea's **intrinsic** content height independent of any CSS
`min-height` — and with `box-sizing:border-box` (`theme.css:279`, global reset)
that intrinsic height is:

```
3 rows × 19px line-height = 57px content
 + 7px × 2 padding         = 14px
 + 1px × 2 border          =  2px
                            = 73px
```

73 > the `minHeight:64` floor, so the floor never engages — the box renders at
its natural rows-driven 73px, not 64px. This is a **fully deterministic,
arithmetically exact consequence** of the specific `rows={3}` value chosen
alongside the new 19px line-height (the old box was `lineHeight:20` at
`minHeight:64` with no `rows` set, so the browser's default `rows=2` intrinsic
height never exceeded the CSS floor — that's why this effect is new in D4b).
**Verdict: consequence**, not unexpected — nothing is lost or broken, the box
is simply 9px taller than the `minHeight:64` in the code implies it should be.
Flagging as a minor open item for the author: the `style={{minHeight:64}}` is
currently dead code (superseded by the rows-driven intrinsic height); either
drop it or drop to `rows={2}` if 64px was the actual intent. Not blocking.

## (7) 54 missing / 36 added — see "Missing / Added" section above

Fully reconciled to the 18-element net difference: Feed's SearchInput restructure
is balanced (3/3), Resumes' and Cover Letters' SearchInput each add one wrapper
node that didn't exist before (net +1 each), and Persona's 11 visible
AutofillField sites each genuinely lose their `v2-fieldwrap` wrapper node (net
+11 missing-heavy) — 0 − 2 + 11 = 9 per theme × 2 = 18. Nothing disappeared
unaccountably; the wrapper removal is real, intended, and matches
`expected-D4b.md`'s own description of the focus-signal handoff.

## Overlay images — per-image description and a note on missing pairs

Only two overlay PNGs exist in `diff_D4a_D4b/`
(`v2_applications__light__1440.png`, `v2_persona__light__1440.png`), not four —
`shotdiff_D4a_D4b.json` shows **Searches and Settings both at 0 changed pixels**
across every viewport/theme, so the diff tool generated no overlay for them (no
diff to draw). This lines up with `expected-D4b.md`: Searches' `Cell`
migrations and Settings' `Select`/textarea migrations are all in
drawers/modals/collapsed sections not open by default (`Searches.jsx` fields
live inside a search's edit drawer; `Settings.jsx:876`'s textarea is a modal),
so the crawl's default-state screenshot never renders them — a coverage gap,
not evidence the migrations didn't happen (both are confirmed directly in
`git show bc3d351` and current source).

- **Applications** (`v2_applications__light__1440.png`): only the "Notes ·
  autosaves" textarea is highlighted (solid red block). Nothing else on the
  page — job list rows, status pills, "Generate prep handover", history rail —
  is outlined. Matches the isolated stylediff exactly: this route's only D4b
  delta is `Applications.jsx:651`.
- **Persona** (`v2_persona__light__1440.png`): both columns are extensively
  outlined/filled top to bottom — see **(4)** above for the full explanation
  (cascading reflow from every migrated field's height change, corroborated by
  the dashed-outline-vs-solid-fill distinction matching exactly which sites
  have a background-color delta and which don't).

## Final list: UNEXPECTED

**None.** Every prop delta in `stylediff_D4a_D4b.md` (isolated D4a→D4b, the
authoritative source per this reconciliation's method) traces to a documented
`expected-D4b.md` row or a mechanical consequence of one. The 54/36
missing-added imbalance is fully accounted for by a real, intended,
documented DOM simplification (Persona's `v2-fieldwrap` removal), not a lost
element. No migrated field lost its focus signal — every `Input`/`Textarea`/
`SearchInput` site keeps the border-accent via `theme.css`'s bare `input`/
`textarea` tag selectors, `Select`'s div trigger keeps the same
`[tabindex="0"]` ring already clean since D4a, and every kept-inline composite
keeps `.v2-fieldwrap:focus-within` untouched. The Résumés-shelf 1024 bbox is
data drift, not code (no matching stylediff evidence, and the same route at
1440 shows only the documented header change). The `Textarea` `83→92`/`64→73`
pair is a real, fully-traced arithmetic consequence of `rows={3}` at the new
19px line-height exceeding the caller's `minHeight:64` — logged as a minor
non-blocking cleanup item, not a regression.

D4b is clean to proceed to the next step. One follow-up worth carrying forward
(not a blocker): `Applications.jsx:651`'s `style={{minHeight:64}}` is currently
inert — `frontend/src/v2/Applications.jsx:653` — the box renders at 73px from
`rows={3}` regardless; reconcile the two or drop the now-dead `minHeight`.
