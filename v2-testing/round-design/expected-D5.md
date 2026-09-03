# D5 — lint (`tools/stylelint.py`) → exit 0

Source-only run: no rebuild, no restart, no commit. Verification here is the lint
itself, an `esbuild` parse of every touched file and a `{}`/`()`/`[]` balance check
against `git show HEAD:<file>`; the pixel and style crawls run in D6.

```
stylelint: 0 findings ({}), 109 allowed, 0 css      # exit 0
```
Start state: `130 findings ({'radius-literal': 73, 'pill-shaped-inline': 24,
'hover-class-on-non-primitive': 31, 'font-family-literal': 2}), 127 allowed`.

## Per-rule outcome

| rule | start | lint-parsing FP | migrated | tokenised | kept (annotated) | left |
|---|---|---|---|---|---|---|
| radius-literal | 73 | 3 | 5 | 65 | 0 | **0** |
| pill-shaped-inline | 24 | — | 3 | — | 21 | **0** |
| hover-class-on-non-primitive | 31 | 3 | 6 | — | 22 | **0** |
| font-family-literal | 2 | — | — | 2 | 0 | **0** |
| theme.css token parity | 0 | — | — | — | — | **0** |

"migrated" counts findings removed because the element became a primitive (or a
primitive absorbed its style object); "tokenised" counts findings removed by
swapping a literal for a token with no other change.

---

## 1. Lint parsing fixes (`v2-testing/tools/stylelint.py`)

Three parsing bugs, all reported rather than worked around. None of them weakens a
rule; the third *strengthens* one.

**(a) multi-line block comments were read as code.** Each line was tested on its
own, so the continuation lines of a `/* … */` or `{/* … */}` that spans several
lines looked like live JSX. Three false positives:
`Applications.jsx:412`, `Searches.jsx:608`, `Searches.jsx:609` — all of them prose
that happens to mention a hover class (`(theme.css .v2-hover-accent) — the stage
bands were the last`). Fixed with `strip_block_comments()`, which carries the
open/closed state across lines and blanks the comment spans while keeping the line
numbering.

**(b) a `ui: keep` note above a multi-line element was ignored.** `is_allowed()`
walked back up to 7 lines and broke at the first line starting with `<Tag`. When the
flagged line is a *continuation* of an element (`style={{…}}` on its own line), that
break fired on the element's **own** opening tag, so the note directly above it never
counted — which is where D4 wrote all of them, and where JSX makes it the only legal
place (a comment cannot sit between two attributes of an open tag). The walk now
crosses **one** opening tag when the flagged line carries no `<Tag` of its own, and
breaks at the second; when the flagged line does carry its own tag, nothing is
crossed, exactly as before. This converted 24 already-annotated D4 keeps from
"finding" to "allowed" — no code change, the notes were always there.

**(c) `pill-shaped-inline` could be silenced by tokenising.** The rule matched only
the literal `borderRadius: 99`, so §2 below would have made every hand-rolled pill
invisible to it. The pattern now also matches `borderRadius: 'var(--radius-control)'`.
This is why 21 pill sites still needed a written keep after tokenisation.

## 2. Radius tokens

Four tokens added to **both** blocks of `theme.css` (light + dark, identical by
construction — the css parity check stays 0), filling the gaps below `--radius-field`
and between `--radius-row` and `--radius-card`:

| token | value | what it is |
|---|---|---|
| `--radius-mark` | 3px | the inline diff highlight drawn behind running text |
| `--radius-inline` | 4px | the inline mono code chip and the 14–16 px tick box |
| `--radius-mini` | 5px | the 17–22 px square control (checkbox, ¶ button, funnel bar) |
| `--radius-cell` | 8px | the pick cell / small panel, one step between row (7) and card (9) |

No token removed from the radius scale; no radius **value** changed anywhere.

Every numeric `borderRadius` in `frontend/src/v2/*.jsx` was then replaced by its
token — including the ~64 sites that were already `allowed` by a keep note, because
a keep note is about the *element* staying inline, never about the radius staying a
literal. `ui.jsx` had none to convert. 137 substitutions, all zero-pixel
(`borderRadius: 9` and `borderRadius: 'var(--radius-card)'` both compute to 9px):

`3 → var(--radius-mark)` · `4 → var(--radius-inline)` · `5 → var(--radius-mini)` ·
`6 → var(--radius-field)` · `7 → var(--radius-row)` · `8 → var(--radius-cell)` ·
`9 → var(--radius-card)` · `10 → var(--radius-menu)` · `99 → var(--radius-control)`

| file | sites (HEAD line numbers) |
|---|---|
| Applications.jsx | r4 370, 588 · r8 548, 829 · r99 65, 346, 553, 587 |
| Companies.jsx | r4 106, 937, 938 · r7 124 · r8 948 · r9 658 · r99 102, 428, 433, 484, 499, 521, 529, 534, 763, 765, 825, 980 |
| CoverLetterEditor.jsx | r5 445, 447, 451 · r6 481, 496 · r99 314 |
| CoverLetters.jsx | r6 73 · r8 18, 110 |
| JobFeed.jsx | r4 96, 754, 816 · r5 1330 · r8 1149, 1272, 1286, 1329, 1343 · r99 730, 821, 841, 846–849, 889, 899, 902, 912, 988, 990, 993, 1102 ×2, 1108, 1110, 1125, 1174, 1203–1205, 1221, 1226, 1228, 1288 ×2 |
| LoginModal.jsx | r7 69 · r99 53 |
| Persona.jsx | r4 135 · r7 387 · r9 376 |
| ResumeEditor.jsx | r3 874, 878 · r6 597, 606 · r8 687, 703, 788 · r9 861 · r99 469, 614, 705 ×2, 790 ×2, 867, 870 |
| ResumeSections.jsx | r4 385 · r6 284, 296, 325, 380, 456 |
| Resumes.jsx | r99 176, 195, 235, 281 |
| Searches.jsx | r4 200, 797 · r8 275 · r99 621, 656, 664, 670, 806, 859 |
| Settings.jsx | r5 1035 · r6 29 · r99 117, 122, 491, 608, 724, 1063 |
| Stats.jsx | r5 490, 491 · r8 480, 765 · r99 105, 426, 634, 643, 684 |
| Toast.jsx | r9 64 · r99 72 |
| ToastLab.jsx | r10 40, 60 · r99 33, 34, 45, 53, 55 (lab page, outside the lint's scope — converted for consistency) |
| V2App.jsx | r99 144, 166, 176 |
| WelcomeModal.jsx | r8 46 · r99 48 |

## 3. Font-family literals → token

Both were `fontFamily: 'inherit'` on the editor `<h1>`, written defensively against
a UA/preflight heading family that neither actually sets. `.jn-v2` resolves the
inherited family to `--sans`, and `--font-body: var(--sans)`, so the computed value
is unchanged.

| site | before → after |
|---|---|
| `CoverLetterEditor.jsx:317` | `<h1>` doc title · `fontFamily: 'inherit'` → `'var(--font-body)'` |
| `ResumeEditor.jsx:472` | `<h1>` doc title · `fontFamily: 'inherit'` → `'var(--font-body)'` |

## 4. Migrations to a primitive

### 4a. Three row affordances move into `ui.jsx`

`RemoveLink` and `RemoveX` were already the primitive for their role — they just
lived in `ResumeSections.jsx`, so the lint (correctly) saw a hand-rolled span with a
hover class. They now live in `ui.jsx` and `ResumeSections.jsx` re-exports both names,
so every existing import (`Persona.jsx`, `ResumeEditor.jsx`, and the five call sites
inside `ResumeSections.jsx`) is untouched. The ▲▼ pair, written out three times, became
one `MoveArrows`.

| site | element | before → after |
|---|---|---|
| `ResumeSections.jsx:106` | `RemoveLink` | defined here → `export { RemoveLink } from './ui'`; ink `var(--muted)` → `var(--helper-ink)` (same value), `fontSize: 11.5` → `var(--t-11-5)` |
| `ResumeSections.jsx:111` | `RemoveX` | defined here → `export { RemoveX } from './ui'`; ink `var(--faint)` → `var(--helper-ink)` (`--faint` is an alias of `--muted`) |
| `ResumeSections.jsx:189` | header contact `arrows(i)` | inline ▲▼ span pair → `<MoveArrows onUp onDown />` |
| `ResumeSections.jsx:357` | skills `arrows(k)` | the same pair, hand-copied → `<MoveArrows onUp onDown />` |
| `CoverLetterEditor.jsx:381–385` | contact-item ▲▼ | inline pair → `<MoveArrows upOff={i===0} downOff={i===arr.length-1} …>` |
| `CoverLetterEditor.jsx:401` | contact-item ✕ | inline span → `<RemoveX />` |

Rest state is pixel-identical at all six sites (`--faint`/`--muted`/`--helper-ink`
all resolve to the same colour; 8 px glyphs, `gap: 1`, `flex: '0 0 auto'` preserved).
Two **hover-state** changes, both deliberate and both listed here so the D6 crawl
accepts them:

- `CoverLetterEditor` ▲▼ hovered `v2-hover-accent-text` (ink → accent); it now hovers
  `v2-navlink` like the résumé editor's identical pair (wash → `--navlink-hover-bg`,
  ink → `--navlink-hover-ink`). One control, one hover.
- `CoverLetterEditor` ✕ hovered `v2-hover-bad-text` (ink only); `RemoveX` also carries
  `v2-hover-bad`, so the glyph now takes the `--hover-bad-bg` wash the other ✕s take.

`cursor` moved from the arrow container onto each arrow (so a disabled end shows the
default arrow); the only pixel this touches is the 1 px gap between the two glyphs.

### 4b. The Feed's on-rail bulk controls share one object

`JobFeed.jsx:846–848` repeated the same nine-property style object three times. It is
now module-level `RAIL_BTN` (with the keep note on the object, not on three copies);
`848` spreads it plus `gap: 5`. No value changed. This removed two
`pill-shaped-inline` findings without a keep, since the sites no longer carry the
signature inline.

## 5. `Heading strong` — line-heights pinned to whole pixels

Per D1-D2 §"Decisions during D4" → "`Heading strong` line-heights". `HEADING_STRONG`
declared no line-height, so these titles inherited preflight's 1.5 and landed on
x.5 heights — the heights Chrome rounds a 1 px card border away from. Pinned:
**15→22 · 15.5→23 · 16→24 · 17→25 · 18→27 · 19→26** (19 takes 26 so the 400- and
500-weight 19s share one box).

Sites whose title box height changes:

| site | size | line-height before → after | Δ |
|---|---|---|---|
| `Companies.jsx:682` "Identity and sources" | 15 | 22.5 → 22 | −0.5 |
| `Companies.jsx:699` "Which postings to keep" | 15 | 22.5 → 22 | −0.5 |
| `Companies.jsx:724` "Scraper tuning" | 15 | 22.5 → 22 | −0.5 |
| `Searches.jsx:578` "New search" | 15.5 | 23.25 → 23 | −0.25 |
| `Stats.jsx:464` "Application funnel" | 17 | 25.5 → 25 | −0.5 |
| `Stats.jsx:517` "Score distribution" | 17 | 25.5 → 25 | −0.5 |
| `Stats.jsx:543` "New jobs · last 30 days" | 17 | 25.5 → 25 | −0.5 |
| `Stats.jsx:559` "LLM costs" | 17 | 25.5 → 25 | −0.5 |
| `Stats.jsx:606` "Schedules" | 17 | 25.5 → 25 | −0.5 |
| `Resumes.jsx:211` "Persona" card title | 19 | 28.5 → 26 | **−2.5** |
| `Resumes.jsx:255` base-résumé card title | 19 | 28.5 → 26 | **−2.5** |

Unchanged (already integer, or the call site holds its own): `CoverLetters.jsx:342`
and `Persona.jsx:159` (16→24, 18→27 were already exact); `CoverLetters.jsx:313` keeps
its documented `lineHeight: '22px'` (the row's own integer height) and
`JobFeed.jsx:921` keeps `lineHeight: 1.15` (the two-line list-row title block) — both
still carry the reason at the call site, which is what the primitive's comment asks for.

Two call-site overrides became redundant and were removed, so the value now comes
from the primitive: `Settings.jsx:528` (`lineHeight: '26px'`, size 19) and
`Searches.jsx:620` (`lineHeight: '23px'`, size 15.5). Both are zero-pixel.

## 6. `theme.css`

- Both blocks carry the identical semantic list (the lint's css check is 0).
- Tokens removed — nothing in `frontend/src/v2` reads `var(--name)` for either, and
  nothing outside v2 does:
  - `--btn-primary-bg-hover` — `BTN_LOOK.primary.hover` is `''`; a primary button has
    no hover class, so the token was never consumed.
  - `--menu-item-danger-hover` — a danger `MenuItem` hovers through `v2-hover-bad`,
    which reads `--hover-bad-bg`.
- Tokens added: the four radii in §2. Full audit: 252 defined → 250 read → 2 removed;
  0 tokens read but not defined.

## 7. Kept inline (annotated `// ui: keep — …`)

Every remaining finding is a composite control that no current primitive draws
without a metric change, and this run makes no metric change without a pixel gate.
Notes added at these sites (existing D4 notes reworded where a sibling needed cover):

### pill-shaped-inline
- `Applications.jsx:65` `ACT_BTN` — the detail header's own action pill (h30 · 13 · pad 0 14) shared by two anchors and the ⋯; `Pill` md is 31/12.5/pad 0 15.
- `Companies.jsx:484` — the "+N aliases" count badge (9.5 on `--surface-2`, pad 1 5); `Tag` is 10/pad 2 8 uppercase.
- `Companies.jsx:529` — the 25 px Test pill (twin of Run above); `Pill` sm is 26.
- `Companies.jsx:825` — the ATS badge (mono 9.5/.05em/pad 3 8, painted by its `cc-*` class); `Tag` is 10/.06em/pad 2 8.
- `Companies.jsx:980` — the test row's kept/dropped tag (9.5 · pad 2 7, tinted from `st`).
- `JobFeed.jsx:841` — the floating bulk **bar**: pill-shaped, on the dark `--rail` ground with `--shadow-pop`; no primitive owns a bar.
- `JobFeed.jsx:889` — the "+N reports" count badge pinned to the score ring (16 px min box on `--surface` with a `--line` hairline).
- `JobFeed.jsx:1125` — a two-cell segmented filter track (one shared border run, overflow hidden).
- `JobFeed.jsx:1204`, `1205` — the Live / Cached cells of that pattern's sibling toggle.
- `Settings.jsx:122` — the switch knob: an 11 px disc that slides inside the track (absolute + transition); `Dot` is a static status disc.
- `Stats.jsx:643` — the 25 px scheduler Run pill, matched to Searches/Companies.
- (plus the D4 notes that (b) above finally honours: `Companies.jsx:124/428/433/521/534`, `CoverLetters.jsx:73/110`, `JobFeed.jsx:846/1203`, `LoginModal.jsx:69`, `ResumeEditor.jsx:469/867/870`, `Searches.jsx:656/664/670`, `Settings.jsx:724/1063`, `Applications.jsx:548/587`, `WelcomeModal.jsx:48`, `Toast.jsx:64`.)

### hover-class-on-non-primitive
- `Applications.jsx:521/523/525` — the three ACT_BTN header actions; two are real `<a>` so ⌘/middle-click still opens the posting, and `Button`/`Pill` render a div.
- `Applications.jsx:588` — a ✕ with a padded, rounded hover target so the `--hover-bad` wash reads as a box on the interview row; `RemoveX` draws no box.
- `Applications.jsx:829`, and the already-noted `548` — segmented **stage cells**.
- `Companies.jsx:528` — the Test pill (see above).
- `CoverLetterEditor.jsx:476/491`, `ResumeEditor.jsx:597/606` — the 24 px PDF-toolbar dropdown triggers; `Select`'s box is 32.
- `JobFeed.jsx:802` — the Sort control is a text trigger (muted 12.5 + bold value + caret), not a `Pill` or a `Link`.
- `JobFeed.jsx:847` — a `RAIL_BTN` control (see §4b).
- `JobFeed.jsx:1286/1328`, `ResumeEditor.jsx:686/701/788` — selectable **choice cards** (padded block, radio/tick slot, accent-soft when picked, `v2-act` hover).
- `WelcomeModal.jsx:37` — the modal's own ✕: muted 13 sitting on the title's 26 px line box; `IconButton` is a 26 px round box.

## 8. Needs a decision (deferred to D6/D7, where the pixel gate is available)

1. **A `Choice` primitive for the pick cell.** Nine sites, two coherent families:
   a *segmented cell* (fixed 31–34 px, one label, hovers `v2-bd`/`v2-bdc`) at
   `Applications.jsx:548/829`, `Companies.jsx:124`, `CoverLetters.jsx:110`; and a
   *choice card* (padded block, title + helper, hovers `v2-act`) at
   `ResumeEditor.jsx:686/701/788`, `JobFeed.jsx:1286/1328`. Each family is already
   internally consistent, which is why nothing was changed — but two of the choice
   cards' siblings, `JobFeed.jsx:1272` and `1343`, carry **no** hover class at all
   while sitting in the same modal as `1286`/`1328`.
2. **The PDF-toolbar trigger hovers two ways.** `ResumeEditor.jsx:597/606` uses
   `v2-act` (accent border + wash); `CoverLetterEditor.jsx:476/491` draws the
   identical control with `v2-bd v2-ctl` (accent border only). A note at the résumé
   site records this so a third variant doesn't appear. Under the
   "segmented cell / choice card" split above a 24 px bordered trigger is a *control*,
   which argues for `v2-bd` — a hover-only change, deliberately not made here.
3. **The bulk bar mixes two button metrics.** `JobFeed.jsx:844` is a real
   `Button size="xs"` (h28 · 12.5 · pad 0 14) next to three `RAIL_BTN` controls
   (h27 · 11.5 · pad 0 11). A `Button variant="rail"` plus a matching size would
   collapse them, but that is a metric change.
4. `Stats.jsx:450` draws a serif **27/30px** KPI numeral — its own step between
   `PageTitle` (30) and `Heading` (22). Annotated, not folded in.

## 9. Note on the tooling

`tools/stylescan.py` rewrites `round-design/scan.md` in place. It was run for the
role counts below and `scan.md` was then restored to HEAD, since D5 is only allowed
to write this file; the D1 snapshot in the repo is unchanged.

Final scan — 1 486 objects, 23 roles (was 1 737 / 32 at D1):

```
layout 62/761 · unclassified 217/266 · text 117/222 · surface-block 38/51
card-static 27/30 · helper-text 16/25 · label 25/25 · input 12/19 · heading 16/17
mono-text 14/15 · scrim 2/9 · section-head 6/8 · header-row 6/7 · link 7/7
dashed-add 6/6 · rule 4/4 · row 3/3 · menu-item 3/3 · modal-panel 1/3
page-title 2/2 · toast 1/1 · band 1/1 · chip 1/1
```

Every remaining site of a *design* role is either in `ui.jsx` (`row` ui.jsx:374,
`menu-item` ui.jsx:347, `band` ui.jsx:417, `chip` ui.jsx:581), a primitive carrying a
layout-only `style` (`row` `Applications.jsx:431` / `Companies.jsx:478` — `<Row>` with
an extra hover class; `modal-panel` `JobFeed.jsx:91`/`952` — `<Menu>`; `Toast.jsx:91`
— the stack wrapper), an annotated keep (`menu-item` `CoverLetters.jsx:72`,
`Settings.jsx:1034`; `toast` `Toast.jsx:62`; `page-title` `Stats.jsx:450`), or the
`/v2/toasts` lab page (`ToastLab.jsx:28`), which the lint does not police.

## Verification run

- `py v2-testing/tools/stylelint.py` → `stylelint: 0 findings ({}), 109 allowed, 0 css`, exit 0.
- `npx esbuild@0.21.5 --loader:.jsx=jsx <file> --log-level=error` on all 19 touched
  `.jsx` files → clean.
- `{}` / `()` / `[]` balance for each touched file matches `git show HEAD:<file>` (0 unbalanced).
- Not run in D5 (no build available): `shots.py` / `shotdiff.py` / `stylecrawl.py` /
  `stylediff.py`. The eleven `Heading strong` rows in §5 and the two hover changes in
  §4a are the diffs D6 should expect from this step; everything else is zero-pixel.

## 10. Gallery

`UiGallery.jsx` (`/v2/ui`) gains one `Role` block for the three primitives added in
§4a — `RemoveLink`, `RemoveX` (two sizes) and `MoveArrows` (free, first-row,
last-row) — per `ui.jsx`'s own rule that a primitive with nothing on `/v2/ui` has
nothing for the crawl to measure. Gallery-only; no screen is affected.
