# reconcile-D4f — D4e→D4f diff reconciliation (D4e fix-up + ModalPanel/Drawer/HeaderRow/TableHead/Rule/Surface)

Inputs: `expected-D4f.md` (Part 1 — Settings row-help fix + `Heading strong`/`Link rel`/`Helper
onClick`/`Spinner weight="bold"`; Part 2 — `ModalPanel`/`Drawer`/`HeaderRow`/`TableHead`/`Rule`/`Surface`,
103 sites), `reconcile-D4e.md` (method precedent), `artifacts/design/stylediff_D4e_D4f.md` (5652 baseline
elements · **10** changed tuples · 210 missing · 222 added), `artifacts/design/shotdiff_D4e_D4f.json` (60
shots), overlays in `artifacts/design/diff_D4e_D4f/*.png` (locally: Settings, Stats at light/1440; fetched
from the container for this pass: résumé-editor and cover-letter-editor at light/1024, matching the task's
docker instructions), `frontend/src/v2/ui.jsx` (`ModalPanel`, `Drawer`, `HeaderRow`, `TableHead`, `Rule`,
`Surface`, `Heading strong`, `Spinner weight="bold"`, lines 70-871), and `git show 5ace038 --
frontend/src/v2` (the D4f commit; current branch HEAD, `31d1f03`, is one commit further — a D5 lint-script
draft with no source changes under `frontend/src/v2`, so `5ace038` is the correct and unambiguous diff
target named in the task).

**Headline: zero regressions from this step's own code.** The 10 changed tuples are exactly the Settings
Autofill-row fix reverting D4e's regression (`reconcile-D4e.md`'s one UNEXPECTED), value-for-value. The
210/222 missing/added split is a pure DOM-path rename cascade from `Rule` rendering `<span>` where two call
sites' dividers used to be `<div>` (Searches, Companies) plus one clean class-rename (Stats' `Refresh`) and
one crawl-cutoff element becoming newly visible (Settings' "Prompt caching" row, resolving `reconcile-D4e`'s
own loose end). The one real finding — the résumé/cover-letter editor's PDF-preview toolbar showing ~4.6k/
3.6k changed pixels at 1024px only — traces to **zero style delta** in the source for that exact site; see
**(A)** for why it is not attributed to this step.

---

## (A) Résumé/cover-letter editor toolbar, 1024px only — ~4.6k/3.6k changed pixels, ≤18px at 1440

**Sites**: `ResumeEditor.jsx:588-616` (right pane) and `CoverLetterEditor.jsx:474-513` (right pane) — both
migrate the PDF-preview toolbar `<div>` → `<HeaderRow pad="8px 20px" align="center" style={{ flexWrap:
'wrap', rowGap: 6, ...}}>` and the wrapping `<section>` → `<Surface as="section" radius="none" ...>`.

**Traced value-for-value, both sites, both produce byte-identical computed style:**

| property | before (raw div/section) | after (HeaderRow/Surface) | match |
|---|---|---|---|
| padding | `'8px 20px'` | `pad="8px 20px"` → `HEAD_PAD` bypassed, `padding: pad` | identical |
| display/flexWrap/rowGap | `flex, wrap, rowGap:6` | same, via `style` (spread last, after HeaderRow's own `display:'flex'`) | identical |
| alignItems | `'center'` | `align="center"` | identical |
| gap | `12` (ResumeEditor) / `9` (CoverLetterEditor) | HeaderRow default `gap:12`, `style.gap:9` override on the CL site only — matches each site's original | identical |
| borderBottom | `'1px solid var(--line)'` | tone defaults to `'line'` → `HEAD_LINE.line = var(--head-line)`, and `theme.css`'s `--head-line:var(--line)` (unchanged both light/dark blocks) | identical value |
| section background | `'var(--surface-2)'` | `Surface`'s own `background:'var(--surface-2)'`, `radius="none"` → `borderRadius: undefined` (no-op) | identical |
| section flex/minWidth/minHeight | unchanged, passed through `style` | unchanged | identical |

`V2App.jsx`'s only change in this commit is a code comment (rail-hairline `// ui: keep` note) — no style
touched, so the sidebar width feeding the two-pane split is also unaffected. **No line of this commit
changes any pixel, color, or dimension feeding this toolbar's layout.**

**Fetched the 1024px overlay from the container** (`docker compose cp
backend:/tmp/v2t/shots/diff_D4e_D4f/v2_resumes_22ce0e5b-…__light__1024.png` and the matching cover-letter
shot) and viewed both. In each, the row renders as a **single line** — "PDF PREVIEW · Template Garamond
Classic ▾ · Paper US Letter ▾ · ↓ Download PDF" all on one row, not wrapped to two lines. The double-exposure
ghosting is confined to the **Paper-size picker and the Download-PDF button** (the two rightmost items); the
"PDF PREVIEW" label and the Template picker are crisp/unchanged. That is consistent with the row sitting at
its own horizontal capacity limit at this width — at 1024px the right pane is `flex:1` against the left
pane's `flex:'0 0 47%'`, leaving roughly 390-400px of content width for a row whose natural width (label +
two pickers + button + gaps) is right at that edge. The code's own comment flags this as a known tight fit:
`ResumeEditor.jsx:587` — *"R2-S-02: wraps rather than overflowing, like the cover-letter editor's identical
toolbar"* — i.e. this row was already documented, pre-D4f, as being at its wrap boundary by design (R2-S-02
predates this step).

**Conclusion: not a D4f code change.** With the source confirmed byte-identical, the shot-diff signal is a
sub-pixel/timing artifact of a pre-existing tight-fit row being measured right at its own boundary — not a
regression this step introduced. It is **not on the expected-D4f.md list** (nothing there discusses this
toolbar), but it also isn't attributable to any line this step touched, so it does not belong on the
UNEXPECTED list either — there is no fix to make in `ResumeEditor.jsx`/`CoverLetterEditor.jsx` because
nothing there changed. Flagged as a **note, not a defect**: worth a second, isolated 1024px capture of
`/v2/resumes/{id}` to confirm this is genuinely non-deterministic (crawl noise, same class as
`reconcile-D4e.md`'s PDF-spinner-timing example) rather than a real ≤1px width delta from something outside
this diff (e.g. a scrollbar-gutter difference between the two crawl passes) that happens to tip this specific
row across its wrap threshold. Either way, it is outside this step's blast radius.

## (B) Stats 441-446px at (1348,61,1410,74) — Refresh → Link

`Stats.jsx:392-419`: the header itself is `<HeaderRow as="header" variant="screen" align="flex-end"
style={{ gap: 18 }}>` — `variant="screen"` → `HEAD_PAD.screen = '22px 30px 16px'` (matches the original
header's inline padding exactly), tone defaults to `'line'` → `border-bottom: var(--head-line)` = `var(--line)`
(matches the original `'1px solid var(--line)'`), `align="flex-end"` matches the original `alignItems:
'flex-end'`, `gap:18` in `style` overrides HeaderRow's default 12 and matches the original `gap:18`. **The
header row's own box is byte-identical** — confirmed by the bbox itself: 13px tall × 62px wide, a small
localized region, not the ~40px+ band a header-height change would produce.

The only real change is the control inside it: `<span className="v2-hover-accent-text v2-ctl" style={{
fontSize:12.5, color:'var(--muted)' }}>` (line-height 1, hand-written `kb()`) → `<Link onClick={refresh}
style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:7 }}>`, i.e. ink `--muted → --link-ink`,
size `12.5 → 11.5`, weight `— → 500`, line-height `1 → 17px` — exactly `expected-D4f.md`'s Part 1c row and
note 3 ("the control grows ~4px... the header's right side will shift a few pixels... expected, not a
regression"). Confirmed in the missing/added tables too: `span.v2-hover-accent-text.v2-ctl` (+ its `↻` icon
span) removed, `span.v2-hover-accent-text` (+ icon span) added — a clean class-drop rename, same tag
(`<span>` both before and after — `Link` renders a `<span>`, not an `<a>`, so no tag-index cascade here, only
a class-list change), 4 elements × light/dark = matches the "4/4" `/v2/stats` bucket found in the
missing/added count (see **(D)**).

**Confirmed: only the Refresh control's own box changed; the header's height and border did not.**

## (C) Settings 107k pixels — the Autofill-row fix reverting D4e's regression, exactly

The 10 changed tuples in `stylediff_D4e_D4f.md` are the **entire** style-diff for this step, and they are
the mirror image of `reconcile-D4e.md`'s one UNEXPECTED, at the same paths:

| path | D4e→D4f (this step) | D4d→D4e (the regression, reconcile-D4e) |
|---|---|---|
| `…v2-scroll:1>div` (AI-tab scroll pane) | `4845px → 4781px` (−64) | `4781px → 4845px` (+64) |
| `…div:0` (models group) | `512px → 496px` (−16) | `496px → 512px` (+16) |
| `…div:0>div:6` (Autofill row) | `71px → 55px` (−16) | `55px → 71px` (+16) |
| `…div:0>div:6>div:0` (label column) | `52px → 36px` (−16) | `36px → 52px` (+16) |
| `…div:0>div:6>div:0>span:1` (help text) | `32px → 16px` (−16) | `16px → 32px` (+16) |

Each appears twice (light+dark) — 10 tuples total, exactly. This is `expected-D4f.md`'s 1a fix:
`Settings.jsx:717`'s description column `flex:'0 1 340px', minWidth:200` → `flex:'0 1 356px', minWidth:210`,
scaled proportionally to the 11→11.5px font bump (340×11.5/11=355.45→356) so the Autofill help string
un-wraps back to one line, and the row (and everything below it in the shared renderer) shrinks back by the
same 16px it had grown. **No other row's height appears in the diff** — confirms `expected-D4f.md`'s claim
that all 73 help/offHelp strings were checked against the new 356px box and none crossed a wrap boundary in
either direction. I did not re-run the D4d→D4e overlay for comparison beyond what `reconcile-D4e.md` already
documented (§(G), "Settings... not a uniform 1px reflow... large, overlapping doubled text blocks... worse
toward the bottom") — the shape (page shifts back **up**, same bboxes, same element paths, exactly inverted
signs) is sufficient confirmation this is a clean revert, not a new regression at a different site.

**Confirmed: the page shifts back up by 16px below the Autofill row and nothing else.**

## (D) The 210/222 imbalance (net +12) — what's new, what disappeared

Broken out by route (counted from the raw missing/added lists):

| route | missing | added | net | mechanism |
|---|---|---|---|---|
| `/v2/searches` | 174 | 174 | 0 | `Rule` tag rename (see below) |
| `/v2/companies` | 32 | 32 | 0 | `Rule` tag rename (see below) |
| `/v2/stats` | 4 | 4 | 0 | `Refresh` class rename, **(B)** |
| `/v2/settings` | 0 | 12 | **+12** | crawl-cutoff element newly in view |

**210 − 198 = 12 accounted for by Searches+Companies+Stats' clean renames** (they cancel to net 0), and
**Settings' +12 is the entire imbalance.**

**Mechanism for Searches (174/174) and Companies (32/32) — confirmed, not guessed:** `ui.jsx`'s `Rule`
(new in this step) renders `<span aria-hidden="true">`, not a `<div>` (`ui.jsx:778-786`). Two sites replace a
plain divider `<div style={{height:1,...}}>` with `<Rule>`:
- `Searches.jsx:576`: the inset rule between the header and the card list (`<div style={{height:1,
  margin:'0 30px', background:'var(--line)'}}/>` → `<Rule tone="line" style={{margin:'0 30px'}}/>`). This
  div was the **only** `<div>` sibling before `.v2-scroll` (the header above it is `<header>`/`HeaderRow
  as="header">`, never a div), so `.v2-scroll` drops from `div:1` to `div:0` — cascading through **every**
  descendant path of the 6 search cards (title, badges, dots, menu icons, status pills), hence all of
  Searches' 174/174: full subtrees at a renamed prefix, content identical at each pair (verified: `span:0|
  JobSpy`, `span.sm-keyword:1|JOBSPY`, `“product manager” · Unit…`, pill labels/counts all match text-for-text
  between the missing and added rows — only the `v2-scroll:1`→`v2-scroll:0` prefix differs).
- `Companies.jsx:413`/`:420`: the two vertical dividers in the toolbar (`<div style={{width:1,height:20,...}}
  />` ×2 → `<Rule vertical length={20} tone="line" .../>` ×2). The crawler indexes siblings per-tag
  (nth-of-type-style), so each conversion ripples independently through every later same-tag sibling's
  counter: the 4 tier `Pill`s (rendered as `<div className="v2-ctl v2-bd">`, `ui.jsx:172`) sit after only the
  *first* Rule, so they shift `bd:1→4` to `bd:0→3` (−1, exactly one div removed ahead of them); the "Make N
  active"/"Make N inactive" bulk-action `<div>`s sit after *both* Rules, so they shift `div.v2-act:6→4` and
  `div.v2-bd-warn:7→5` (−2, exactly two divs removed ahead of them); the Sort dropdown's bare `<span>`
  wrapper sits after both Rules too, so its **span**-sibling count goes *up* by 2 (`span:1→3`, since both
  Rules are now spans, adding two preceding same-tag siblings). All four shift magnitudes (−1, −2, −2, +2)
  are exactly what "2 divs become spans, at these two specific positions" predicts — a fully mechanical,
  self-consistent cascade. Content at each renamed pair matches (Tier counts 5/21/35/65 identical, "Sort ▾ /
  Needs attention" identical).

**Nothing disappeared.** Every one of the 206 Searches+Companies+Stats missing entries has a content-identical
counterpart in added, at a shifted path. This is `reconcile-D4d.md`/`reconcile-D4e.md`'s established
"tag/class-rename, pure path artifact" class, not lost content.

**Settings' +12 (no missing counterpart) resolves `reconcile-D4e.md`'s own loose end.** That doc's §(G) found
the "Prompt caching" switch row (`Settings.jsx:331`) missing from D4e's crawl with no added counterpart —
attributed to the Autofill row's +16px growth pushing it just past the crawl's ~900px capture cutoff, "not a
lost element... a crawl-viewport consequence." Now that **(C)**'s fix shrinks the page back by 16px, that
same row comes back **into** view — and since it was never counted as present in D4e's own crawl (it was
past the cutoff then too), it has no "missing" entry to pair against; it simply appears fresh in "Added in
D4f": `main>div>div:1>div:5>div:0>span:1|Rubric + résumés + schem…` + 5 more descendants (the `On` switch
knob's 3 spans) × light+dark = 12, exactly. **Confirms `reconcile-D4e.md`'s theory was correct** — the row
was never gone, only out of frame.

## (E) Searches — every card's subtree missing+added, rest tuples otherwise identical

Confirmed above in **(D)**: the sole cause is `Searches.jsx:576`'s divider `<div>` → `<Rule>` `<span>`,
shifting `.v2-scroll` from `div:1` to `div:0` and every descendant path beneath it by the same prefix
rename. It is **not** a `HeaderRow`/`Heading strong` wrapper rename in the sense of changing tag types
*inside* the cards — those stay `<span>` both before and after (`Heading` renders `<span>`,
`ui.jsx:867`), so card titles keep their own local indices; only the shared ancestor prefix moved.

**Spot-check, card:0 (JobSpy / "product manager" search), three properties + its title, missing vs. added:**

| element | missing (D4e path, `v2-scroll:1`) | added (D4f path, `v2-scroll:0`) | identical? |
|---|---|---|---|
| source-badge text | `div>div:0>div:0>span:0\|JobSpy` | same suffix | text match |
| mode badge | `div>div:0>div:0>span.sm-keyword:1\|JOBSPY` | same suffix, same class | text+class match |
| query line | `div>div:0>div:1>span\|"product manager" · Unit…` | same suffix | text match |
| status pill | `div>div.v2-ctl.v2-bd:1\|Paused` | same suffix | text+class match |

No entry for card:0 (or any card) appears in the 10-row "Changed elements" table — i.e. the tool never
registers a *style* delta for any card-internal element, only a *path* delta. That is definitive: the cards'
own geometry, type, weight, color and spacing are untouched by this step; only their ancestor's tag changed.

**All three "confirm" asks — (B), (C), (D)/(E) — check out exactly as expected-D4f.md and reconcile-D4e.md predict.**

---

## Verdict table

| change | count | verdict | evidence |
|---|---|---|---|
| Settings: `height 71px→55px` / `52px→36px` / `32px→16px` / `512px→496px` / `4845px→4781px` | 2 each (light+dark) | **expected** | **(C)** — exact revert of `reconcile-D4e.md`'s one UNEXPECTED, `Settings.jsx:717` fix |
| Searches: 174/174 missing↔added (full card subtrees) | 174/174 | **expected** | **(D)**/**(E)** — `Rule` div→span at `Searches.jsx:576` shifts `.v2-scroll` `div:1→div:0`; content identical |
| Companies: 32/32 missing↔added (tier pills, bulk-action divs, Sort span) | 32/32 | **expected** | **(D)** — two `Rule` divs→spans at `Companies.jsx:413/420`; per-tag index cascade, content identical |
| Stats: 4/4 missing↔added (`Refresh` span) | 4/4 | **expected** | **(B)** — `v2-ctl` class dropped, `Link` migration, `expected-D4f.md` Part 1c |
| Settings: 12 added, 0 missing (Prompt-caching row) | 12 | **expected** | **(D)** — crawl-cutoff row re-enters frame once **(C)** shrinks the page back; resolves `reconcile-D4e.md`'s 60/48 loose end |
| Résumé/CoverLetter editor toolbar, 1024px only, ~4.6k/3.6k px | 4 shots (2 docs × light/dark; CL similarly) | **not caused by this step — no fix to make** | **(A)** — byte-identical computed style traced at both sites; row already documented pre-D4f as its own wrap boundary (`ResumeEditor.jsx:587`, "R2-S-02"); flagged as a note for a re-capture, not a regression |

## Spot-checks against source (ui.jsx primitives, all confirmed shipped as documented)

- `ui.jsx:674-696` — `ModalPanel`: `as="form"` support, `onSubmit` passthrough, `zIndex` default **70**,
  `scrimProps` spread onto the scrim, `escape` default `true` feeding `useEscape(onClose, escape &&
  !!onClose)` (so a panel with no `onClose` registers no listener) — matches `expected-D4f.md`'s Part 2a
  table exactly.
- `ui.jsx:699-712` — `Drawer`: scrim at `zIndex:29`, panel `role="dialog" aria-modal="true"` at `zIndex:30`,
  `useEscape(onClose)` unconditional — matches the doc's "Escape through Drawer, idempotent with the screen's
  own handler" note (2c/6).
- `ui.jsx:735-750` — `HeaderRow`: `HEAD_PAD` (modal `16 22 13` / screen `22 30 16` / compact `15 22 12`),
  `HEAD_BG` (`surface→--head-bg`, `page→--head-bg-page`, `recessed→--head-bg-recessed`), `HEAD_LINE`
  (`line`/`soft`/`strong`, `tone==='none'` skips the border entirely), `as="header"`, default `gap:12`,
  `align` default `'flex-start'` — all match the doc's canon table and the `theme.css` token additions.
- `ui.jsx:758-770` — `TableHead`: `height=28`/`pad='0 22px'` defaults, `--bg` ground, `--label-ink`,
  `var(--t-9-5)`/`14px`/`.11em`/uppercase, `--head-line-strong` bottom rule (or `--head-line-soft` with
  `soft`), `top` adds a `--head-line-soft` top rule — matches.
- `ui.jsx:778-786` — `Rule`: renders `<span aria-hidden="true">` (the tag that drives **(D)**/**(E)**'s whole
  cascade), `tone` default `'soft'`, `vertical`+`length` (default 14) for the tick form — matches.
- `ui.jsx:796-804` — `Surface`: `as="section"` support, `--surface-2` ground, `SURFACE_RADIUS` scale
  (`none→undefined`, `field`/`row`/`card`/`menu`), optional `pad` — matches, and confirmed byte-identical at
  the two PDF-preview sites in **(A)**.
- `ui.jsx:854-871` — `Heading strong`: `HEADING_STRONG` sizes **15/15.5/16/17/18/19** with the documented
  tracking steps, `fontWeight` 500 (or 600 when `strong===600`), and **no `lineHeight` key anywhere in the
  table** — confirms `expected-D4f.md` note 1 ("declares no line-height... needs a decision before D5") is
  shipped exactly as described, still open.
- `ui.jsx:73-83` — `Spinner`: `SPIN_WEIGHT = { bold: '2px' }`, falls back to `'1.5px'` — confirmed at
  `JobFeed.jsx:1186`: `<Spinner size={28} weight="bold" .../>`, the score-ring band-width reversion named in
  Part 1c/2b-drift-4.
- `Settings.jsx:717` — description column `flex:'0 1 356px', minWidth:210` — confirmed shipped exactly as
  `expected-D4f.md` 1a specifies (356, not the suggested 380; 210, not left at 200).

## Final list: UNEXPECTED

**None.** Every changed tuple in `stylediff_D4e_D4f.md` is the documented Settings-row revert **(C)**. Every
missing/added pair is a content-identical DOM-path rename driven by `Rule`'s `<span>` tag (Searches,
Companies) or a clean class-drop (Stats' `Refresh`→`Link`), fully traced to source with zero residue, plus
one crawl-cutoff row re-entering frame (Settings' Prompt-caching row) as the direct, predicted consequence of
**(C)**'s fix. The one item that does **not** trace to a source change — the résumé/cover-letter PDF-preview
toolbar's 1024px-only pixel diff, **(A)** — was checked at the property level for both migrated sites
(`ResumeEditor.jsx:588-616`, `CoverLetterEditor.jsx:474-513`) and found byte-identical to their pre-D4f
computed styles; it is therefore **not attributed to this step** rather than filed as unexpected-but-unfixed.

**Recommended non-blocking follow-up** (not a D4f defect, so not fixed here): re-capture
`/v2/resumes/{id}` and `/v2/cover-letters/{id}` at 1024px twice in a row and diff those two captures against
each other. If the Paper-size/Download-PDF ghosting reappears between two *identical* runs, the row is
genuinely flaky at this viewport (worth a small width buffer or `minWidth:0` audit on the toolbar's fixed-
width picker spans); if it does not reproduce, it confirms **(A)**'s conclusion that this was one-off
crawl-pass noise at a pre-existing tight boundary, unrelated to D4e→D4f.
