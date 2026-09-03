# reconcile-D4d — D4c→D4d diff reconciliation (incl. the D4c fix-up)

Inputs: `expected-D4d.md` (Part 1 — the D4c fix-up: `Searches.jsx:614`'s
`borderColor: … : undefined` bug and `Card`/`Band`/`Row`'s static-cursor
inheritance; Part 2 — `Menu`/`MenuItem`/`SectionHead`/`Chip`/`Tag`/`Dot` on the
ui.jsx primitives, 75 sites across 12 files, 41 non-zero-pixel drift fixes),
`reconcile-D4c.md` items **(A)** (536×`cursor auto→default`, expected to
reverse) and **(B)** (the `Searches.jsx:614` border-colour bug, expected to be
fixed), `artifacts/design/stylediff_D4c_D4d.md` (5665 baseline elements · 757
changed tuples · 83 missing · 82 added), `artifacts/design/shotdiff_D4c_D4d.json`
(per-shot changed-pixel bbox), `artifacts/design/diff_D4c_D4d/*.png` (Companies,
Searches, Résumés — light/1440), `frontend/src/v2/ui.jsx` (`Menu`, `MenuItem`,
`SectionHead`, `Chip`, `Tag`, `Dot`, `Card`, `Band`), and
`git diff 9ee9e9d fd6b243 -- frontend/src/v2` (D4c → D4d fixup+migration, one
commit) cross-checked against current source.

Both D4c's fix-up and D4d's migration land in this single diff (commit
`fd6b243`), matching `expected-D4d.md`'s own framing.

---

## (A) 80×`fontSize 14→12.5` (+66 hover) and 24×`lineHeight 21→18` (+24 hover) — closed menus, so what is this?

None of it is a menu (menus are closed at rest, as the question assumes). All
of it is `SectionHead`'s own `card` styling landing on a **container that has
no text of its own** — a wrapper `<span>`/`<div>` that groups a title + a meta
span, each of which sets its **own** explicit `fontSize`/`lineHeight`, so the
container's cascaded value never reaches a rendered glyph.

Confirmed by diff-reading `ResumeSections.jsx` (`SectionShell`, the migration
that produces the `.v2-hover-accent` sites) and `CoverLetterEditor.jsx`
(`Card`'s local header, `.v2-clhead`, the migration that produces the
`lineHeight 21→18` sites):

- **Before** (`9ee9e9d`): the header `<div>` had no inline `fontSize`/
  `lineHeight` at all — it inherited the ambient 14px/21px (1.5×14) from the
  page. Its child wrapper (`<span style={{display:'inline-flex', gap:6}}>` in
  `SectionShell`; `<span style={{flex:1, display:'flex', gap:9}}>` in
  `CoverLetterEditor`) carried no size either, so it inherited the same 14/21.
  The *grandchildren* — the name span (`fontSize:13`), the count/note span
  (`fontSize:11.5`) — already set their own size and were unaffected.
- **After** (`fd6b243`): `SectionHead`'s own style sets
  `fontSize:'var(--t-12-5)', lineHeight:'18px'` directly on the header `<div>`
  (`ui.jsx:556`). The wrapper span still sets no size of its own, so it now
  inherits **12.5/18** instead of **14/21** — a real, measurable computed-style
  change — but it still renders no text directly (its children still carry
  their own explicit sizes), so **nothing moves on screen**.

This is exactly what `expected-D4d.md` documents at `Persona.jsx:348`
("the container's font-size goes 14 → 12.5 but every child sets its own") and
is marked **zero-pixel**. Traced concretely:

- **fontSize 14→12.5 rest** (80): Persona's 5 group headers (`.v2-clhead`×4 +
  `.v2-qahead`×1) + their wrapper spans, the 2 résumé routes' `SectionShell`/
  `ExperienceEditor` headers (`.v2-hover-accent`) + wrapper spans, the
  cover-letter editor's 3 `.v2-clhead` letter-section headers (counted
  separately below because they *also* carry the `lineHeight` change), and
  Applications' stage-band header (2, covered in **(C)**). All confirmed
  zero-pixel against source (children keep explicit sizes) except the résumé
  `.v2-hover-accent:2>div:1>div>div:0` sites, which are `ExperienceEditor`
  headers whose children are all direct spans with explicit sizes — same
  outcome, just no wrapper-span leaf.
- **lineHeight 21→18 rest+hover (24 each)**: exclusively `CoverLetterEditor.jsx:34`'s
  three letter-section headers (Header/Recipient/Letter, ×2 themes ×2 states…
  the count reflects the div itself + its SVG-chevron wrapper span + the `<svg>`
  + the title/note wrapper span, none of which render text directly under the
  changed node — the visible title (`fontSize:13,lineHeight:'20px'`) and note
  (`11.5/20`) spans are untouched). Zero-pixel, matching
  `CoverLetterEditor.jsx:34`'s documented entry exactly.
- **fontSize hover (66) / lineHeight-adjacent hover (24)**: the same sites'
  `:hover` computed style (`.v2-clhead`/`.v2-hover-accent`/`.v2-qahead`
  trigger a background wash on hover, not a font change, so the font numbers
  merely mirror rest). The rest/hover count mismatch (80 vs 66, 32 vs 28 for
  **(B)**) is fully explained by which rows the crawler's hover pass reaches —
  the same below-the-fold/first-N-rows limitation `reconcile-D4c.md §(6)`
  already established, not a partial migration.

**Verdict: expected, zero-pixel, matches `expected-D4d.md` verbatim.** No
elements outside the documented `SectionHead card` migration set are touched.

## (B) 32×`height auto→19px` (+28 hover) on `span.cc-tier*` — Tag canonical? Row layout change?

**Expected, and it is exactly the `Tag` canonical's own documented caveat.**
`Companies.jsx:496`'s entry in `expected-D4d.md` reads: "`Tag tone="none"` —
zero-pixel apart from the explicit 15 px line-height **and inline-flex box**."

Source (`git diff 9ee9e9d fd6b243 -- Companies.jsx`): before, the tier badge
was a bare `<span style={{fontSize:10, padding:'2px 8px', borderRadius:99, …}}>`
with no `display` set — a plain **inline** element. CSS defines `height` as
not applying to non-replaced inline boxes, so `getComputedStyle(...).height`
reports the literal keyword `"auto"`. `Tag` (`ui.jsx:601`) sets
`display:'inline-flex'` unconditionally — for a flex box `height` **does**
apply, so the same visual pill (padding 2+2 + line-height 15 = 19px) now
reports a real `19px`. The rendered pixel content is identical; only how the
box model *reports* itself changed.

**Row layout does not change.** The tier badge sits inside a fixed
`<span style={{flex:'0 0 62px'}}>` cell that is itself unaffected, and the
`Row` primitive's own height is fixed independent of this cell's content.
Overlay confirmation: `diff_D4c_D4d/v2_companies__light__1440.png`'s
shotdiff bbox is `(382, 182, 411, 891)` — a **29 px-wide vertical strip**
running the full height of the visible company list, exactly the tier column
(x≈382–411). This is a hairline, not a box outline (unlike Searches' visible
red rings, see the per-image notes below) — consistent with a ~1px
antialiasing shift in the pill's rounded corners from the inline→inline-flex
box-model change, not a repositioning. **Expected, harmless, documented.**

## (C) `color rgb(27,26,22)→rgb(109,104,98)` ×2 rest (+1 hover) — `--text`→`--muted`

**Expected — a zero-pixel consequence of `SectionHead`'s non-`card` default
ink, undocumented in `expected-D4d.md`'s prose but structurally identical to
every other case in this diff.**

Site: `Applications.jsx:410`, the stage-band header (Applied/Interview/Offer/
Rejected). `expected-D4d.md`'s entry only calls out `radius 7→6`, but the
migration also crosses `SectionHead`'s ink rule
(`ui.jsx:557`: `...(card ? null : { color: 'var(--section-head-ink)' })`).
`--section-head-ink: var(--muted)` (`theme.css:140/276`) — `--muted` is
`#6d6862` = `rgb(109,104,98)` light / `#a8a49d` = `rgb(168,164,157)` dark,
exactly the "after" values; `--text` is `#1b1a16` = `rgb(27,26,22)` light /
`#d9d7d0` = `rgb(217,215,208)` dark, exactly the "before" values (the dark
pair is the separately-grouped "`rgb(217,215,208)→rgb(168,164,157)` ×2" row).

Before D4c/D4d, the raw `<div className="v2-hover-accent">` header set no
`color` at all, so it inherited ambient `--text`. `SectionHead`'s boxed
(non-`card`) variant explicitly sets `color:var(--section-head-ink)`. But
both of the header's rendered-text children already set their **own** explicit
color — the uppercase stage label (`color:'var(--muted)'`) and the mono count
(`color:'var(--edge)'`) — so this is the identical "container ink changes,
children already override it" pattern as **(A)**. Confirmed zero-pixel by the
shotdiff: `/v2/applications` has **no bbox entry at all** in
`shotdiff_D4c_D4d.json` (0 changed pixels on the whole page), despite six
distinct property changes firing in the stylediff at this one site.
**Expected/harmless**, worth a documentation note only.

## (D) the single hover row: `borderTop 1px→0, radius 6→0, fontSize 11.5→9, height 24→9`

**Noise — a recurrence of the exact crawl-pairing artifact `reconcile-D4c.md
§(B)`'s closing note already flagged, now reversing.** Nothing moved in the
touched source: `git diff 9ee9e9d fd6b243 -- CoverLetterEditor.jsx` shows
**zero changes** at this site (`CoverLetterEditor.jsx:485-511`, the Template/
Paper trigger boxes and their `▾` glyphs) — the trigger is `span.v2-bd.v2-ctl`
(`height:24, border:1px var(--edge), radius:6, fontSize:11.5, padding:'0 8px'`)
containing a plain child `<span style={{color:'var(--muted)', fontSize:9}}>▾</span>`
with none of its own box styling, byte-identical in both commits.

The diff's own DOM path names the small 9px `▾` child span directly
(`span:2>span.v2-bd.v2-ctl>span:2|▾`), yet reports it carrying the **parent**
trigger box's border/radius/height/padding in one build and its own bare
9px/no-border/no-radius values in the other — i.e. across the two crawl runs
the tool's hover-state read landed on two *different* physical nodes at the
same recorded path (an `elementFromPoint`-vs-DOM-path mismatch, the same class
`reconcile-D4c.md` diagnosed for this identical site in the D4b→D4c diff,
where it ran in the opposite direction, 9px→24px). Confirmed **not on the
migration list**: the Template/Paper trigger + `▾` glyph is a segmented
`v2-ctl` control, not a `Menu`/`MenuItem`/`SectionHead`/`Chip`/`Tag`/`Dot` site
— it is correctly untouched by D4d. Flagged for completeness only, not
actioned, same as `reconcile-D4c.md`'s treatment.

## (E) Résumés shelf 642–673 px at (466,337,1272,565) — the copy chips

**Expected, matches `Resumes.jsx:230/273`'s `Chip` migration exactly.**
`git diff 9ee9e9d fd6b243 -- Resumes.jsx` shows the raw `<div className="v2-chip"
style={{height:26, padding:'0 10px', border:'1px solid var(--line)',
background:'var(--bg)', borderRadius:99, gap:6, fontSize:11.5, …}}>` becoming
`<Chip>` value-for-value — `Chip`'s canonical style (`ui.jsx:574`) matches
every one of those numbers. The bbox's small pixel count (642–673 px over a
~806×228 px region, well under 1%) is explained by `Chip` unconditionally
adding the `v2-ctl` class, and `theme.css:326`: `.v2-ctl { line-height:1; }` —
a real line-height change (from the ambient default ratio) inside a
fixed-height, `align-items:center` flex row. `expected-D4d.md` calls this out
directly: "gains … `v2-ctl`'s `line-height:1` (pixel-safe in a fixed-height
centred flex row)" — the "pixel-safe" framing is about keeping text vertically
centred at any zoom, and the crawl's hairline delta is exactly the kind of
sub-pixel text-baseline shift that produces. **Expected, harmless.**

---

## Verdict table — grouped changes

| change (state · prop · old→new) | count | verdict | evidence |
|---|---|---|---|
| rest · cursor `default`→`auto` | 542 | expected | Part 1 — `Card`'s conditional-spread fix reverses `reconcile-D4c.md §(A)`'s 536; the +6 are `Band`'s parallel fix (Cover Letters' pending band, Résumés' empty/error bands) which weren't in D4c's `Card`-only enumeration |
| hover · cursor `default`→`auto` | 4 | expected | Stats LLM-cost table, mirrors `reconcile-D4c.md`'s 4 hover entries reversing |
| rest · fontSize `14px`→`12.5px` | 80 | expected, zero-pixel | see **(A)** — `SectionHead card`'s own font-size on a wrapper with no direct text |
| hover · fontSize `14px`→`12.5px` | 66 | expected, zero-pixel | same sites' hover read; count gap vs. 80 is crawl hover-pass coverage, not a partial migration |
| rest · height `auto`→`19px` | 32 | expected, zero-pixel | see **(B)** — `Tag`'s `inline-flex` box model change on `span.cc-tier*` |
| hover · height `auto`→`19px` | 28 | expected, zero-pixel | same sites' hover read; count gap is crawl coverage |
| rest · lineHeight `21px`→`18px` | 24 | expected, zero-pixel | see **(A)** — `CoverLetterEditor.jsx:34`'s three letter-section headers |
| hover · lineHeight `21px`→`18px` | 24 | expected, zero-pixel | same sites' hover read |
| rest · borderTop/BottomColor `rgb(229,231,235)`→`rgb(226,221,208)`/`rgb(62,59,50)` | 6+6+6+6 | expected | Part 1 — `Searches.jsx:614` fix reverses `reconcile-D4c.md §(B)`'s bug (light + dark, 6 cards each) |
| hover · borderRadius `7px`→`6px` | 4 | expected, zero-pixel | `Applications.jsx:410` stage-band header radius fix (hover read of the same 2 rest sites + their scroll-container ancestor) |
| hover · lineHeight/height `17.25px`→`11.5px` | 4+4 | consequence (low confidence) | `/v2/resumes` `.v2-act` cards' "Recent copies" row wrapper (`div:1`, no explicit font metrics of its own); only fires in **hover**, not rest, for the same path — most likely a chip-count/inflight-state difference between the two crawl runs (live-data drift, the same class `reconcile-D4b.md §(3)` established) rather than a CSS regression; zero visual impact either way (the wrapper renders no text of its own) |
| rest · cursor `default`→`auto` (Stats) | (included above) | expected | — |
| rest · color `rgb(27,26,22)`→`rgb(109,104,98)` / dark `rgb(217,215,208)`→`rgb(168,164,157)` | 2+2 | expected, zero-pixel | see **(C)** — `SectionHead`'s non-`card` `--section-head-ink` on `Applications.jsx:410`, undocumented but harmless |
| hover · color `rgb(27,26,22)`→`rgb(109,104,98)` | 1 | noise | see **(D)**'s closing note — same crawl-pairing artifact, not this site's actual property |
| rest · borderRadius `7px`→`6px` | 2 | expected | `Applications.jsx:410` radius fix (`--radius-field`), documented |
| hover · borderTopWidth/Color/BottomColor/borderRadius/fontSize/lineHeight/paddingLeft/height (the ▾ glyph) | 1 each | noise (crawl-pairing artifact) | see **(D)** — confirmed zero source changes at this exact site |

## Per-image / per-shot notes

- **`v2_searches__light__1440.png`** (bbox 236,106,1410,548 · 15,012 px, the
  largest delta in the set): a full 1px red outline ring around **all six**
  search cards, corners included — this is the `Searches.jsx:614` bug fix
  landing (border-color restored from the Tailwind-default grey to
  `var(--card-border)`), exactly matching `reconcile-D4c.md §(B)`'s prediction
  and overlay description. Nothing else on the page changed (no menu is open
  in the steady-state capture). **Expected.**
- **`v2_companies__light__1440.png`** (bbox 382,182,411,891 · 1,802 px): a
  29px-wide hairline running the full visible row height, over the tier badge
  column only — see **(B)**. No visible box outline (unlike Searches) because
  the delta is sub-pixel antialiasing, not a position/size change. **Expected.**
- **`v2_resumes__light__1440.png`** (bbox 466,337,1272,565 · 673 px): the
  "Recent copies" chip row under Persona/PM — see **(E)**, the `Chip`
  migration's `line-height:1` hairline. **Expected.**
- **`v2_applications__*` (all 4 viewport/theme combos)**: 0 bbox — despite six
  changed CSS properties firing on the stage-band header in the stylediff (see
  **(C)**), nothing paints differently. Confirms the "zero-pixel apart from
  ink container change" read.
- **`v2_persona__*`, `v2_stats__*`, `v2_settings__*`, `v2_toasts__*`,
  `v2_cover-letters__*` (list route)**: 0 bbox. Consistent — every touched
  site on these routes is a `SectionHead card` wrapper-span cascade
  (Persona), a below-the-fold or closed-menu-only change (Stats, Settings),
  or entirely out of D4d's scope (Toasts).
- **`v2_feed__light__1440.png`** (bbox 805,99,1197,161 · 14 px): no
  corresponding stylediff line exists for `/v2/feed` at all (grep confirms
  zero changed elements on the route). At 14 px this is most plausibly render
  jitter from the Feed's own relative-time text ("discovered … ago") ticking
  between the two crawl captures — the same class of harmless timing noise as
  the stats-timestamp line below, not a design regression. Not further
  traceable from the available artifacts; not blocking.
- **`v2_resumes_22ce0e5b…__light__1024.png`** (bbox 879,63,163×100 · 22 px) /
  **`v2_resumes_d28bbd9e…__dark__1440.png`** (bbox 321,12,63×7 · 7 px): both
  tiny, near the page header. Likely the same relative-timestamp jitter
  ("edited … ago") as Feed above; no stylediff entry names a header element on
  these routes outside the cursor/fontSize cascade already covered in **(A)**.
  Not blocking.
- **`v2_cover-letters/ce44e1d4…__light/dark__*`**: 0 bbox in shotdiff despite
  20 changed elements per theme in the stylediff — all fully accounted for in
  **(A)** (the three `.v2-clhead` letter-section headers' zero-pixel font
  cascade). The route's missing/added asymmetry (below) is a separate,
  non-style artifact.

## Missing/added: 83 / 82 — the one-element imbalance, fully resolved

Unlike `reconcile-D4c.md §(1)` (whose 1172/1167 lists were truncated at 300
lines each and left ~5 elements unnamed), this diff's 83/82 lists are complete
and can be walked in full:

| bucket | missing | added | net | mechanism |
|---|---|---|---|---|
| `/v2/resumes` chip rename (light) | 36 | 36 | 0 | pure class-rename: `div.v2-chip` → `div.v2-ctl.v2-chip` (`Chip` always adds `v2-ctl`; `Resumes.jsx:230/273`). Same 1:1 path-rename mechanism `reconcile-D4c.md §(1)` established for `.v2-crow`→`.v2-row.v2-crow` |
| `/v2/resumes` chip rename (dark) | 36 | 36 | 0 | same, dark theme |
| `/v2/stats` timestamp text | 1 | 1 | 0 | `"3 Sept · 19:01"` → `"3 Sept · 22:01"` (light) / same pattern dark — wall-clock advancing between the two crawl runs, live-data drift, not code |
| `/v2/cover-letters/ce44e1d4…` (light only) | **9** | **8** | **+1** | see below |

**The +1 is the whole imbalance**, and it is a crawl-timing artifact, not a
lost element. `CoverLetterEditor.jsx`'s PDF-preview toolbar conditionally
renders a `pdfBusy` spinner (`span.v2-spin`) before the Template/Paper trigger
boxes, and the preview pane shows either a `"Rendering the preview…"` text
placeholder or the real `<iframe>` depending on load state. In the D4c capture
the PDF was still regenerating: the spinner was present (shifting the
Template trigger to `span:2` and Paper to `span:3`) and the preview showed the
placeholder `<div>`. By the D4d capture the PDF had finished: no spinner
(Template at `span:1`, Paper at `span:2`), and the preview shows the loaded
`<iframe>`. Every element pairs up 1:1 across the two captures **except** the
spinner itself, which has no counterpart in the "added" list (it simply isn't
there any more) — that's the one net-missing element. This is the same
"live render state between two independent crawl passes" class of artifact
`reconcile-D4b.md §(3)` and `reconcile-D4c.md §(1)`'s Feed example already
established, here fully traceable because the list is short enough to walk by
hand. **Not a regression, not blocking.**

## Coverage caveat: most of the 41 documented drift fixes don't appear here

`expected-D4d.md`'s Part 2 documents real (non-zero-pixel) drift on menu
containers and rows — border `--edge`→`--line` (6 sites), padding
canonicalisations (4), radii (2), the new 1px row gap (9), row-padding/size
fixes (13), danger-row `marginTop 3→0` (3), inset-rule removal (3), the
Applications stage-band radius (1) — **41 total**. Only the stage-band radius
(already covered in **(C)**) and the Searches border-colour fix show up in
this stylediff. This is expected, not a gap in the migration: every `Menu` is
closed in the crawl's default steady-state screenshot (Companies' sort/⋯
menus, Searches' ⋯ menu, Applications' company/sort/detail popovers,
`JobFeed`'s `Drop` filters and row/detail ⋯ menus, both résumé pickers, both
cover-letter pickers and editors' ⋯ menus — none are open when the page loads
fresh), so their padding/border/gap changes never render. Confirmed
structurally in every `git diff 9ee9e9d fd6b243` hunk reviewed above: the
`Menu`/`MenuItem` swaps are real and match `expected-D4d.md` value-for-value,
they are simply invisible to a closed-page crawl. Not blocking; would need a
menu-opening crawl pass (out of scope here) to visually verify the 41 drift
fixes directly.

## Spot-checks against source (all confirmed shipped as documented)

- `ui.jsx:392-399` — `Card`: `...(live ? { cursor: 'pointer' } : null)`, conditional spread, no stray key.
- `ui.jsx:409-417` — `Band`: identical conditional-spread fix.
- `ui.jsx:541-568` — `SectionHead`: `card`/`boxed`/`caret`/`hover` variants, `--section-head-ink` only applied when `!card`, conditional-spread cursor.
- `ui.jsx:601-610` — `Tag`: `tone="none"` in `TAG_TONE`, `inline-flex` box, 15px line-height.
- `ui.jsx:615-623` — `Dot`: bare tone disc, `--radius-control`.
- `ui.jsx:574-586` — `Chip`: value-for-value match to the old `Resumes.jsx` inline chip.
- `Searches.jsx:614` — `...(warn ? {borderColor:'var(--warn-line)'} : isOpen ? {borderColor:'var(--accent)'} : null)`, matches `CoverLetters.jsx:308`'s established pattern.
- `Companies.jsx:496/500/450/544-549` — `Tag`, `Dot`, `Menu`, `MenuItem` (incl. `href` anchor at "View jobs in feed", `danger` at "Delete company").
- `Applications.jsx:410` — `SectionHead boxed caret="pin"`, `Dot`; `:358/384/517` — `Menu`; `:363/388/520/522` — `MenuItem`.
- `Persona.jsx:348/371` — `SectionHead card hover="v2-clhead"/"v2-qahead"`.
- `ResumeSections.jsx:142-143` (deleted) — local `MenuHead`/`MenuItem` removed; `:156/265` — `SectionHead card`.
- `ResumeEditor.jsx` — imports `MenuHead`/`MenuItem` from `./ui` per the comment left in `ResumeSections.jsx`.
- `CoverLetterEditor.jsx:34` — `SectionHead card caret={false} hover="v2-clhead"` keeping the rotating SVG chevron as first child; `:349/490/505` — `Menu`; `:351-359/492/507` — `MenuItem`.
- `CoverLetters.jsx:23/67/315` — `POPOVER` stripped to position-only, `Menu role="listbox"`, `Tag tone="none"`.
- `JobFeed.jsx:84/832/938/994` — `Menu` (border `--edge`→`--line`, gap 0→1 where documented); `:1060/1086/1112` — `SectionHead boxed caret="end"`.
- `Companies.jsx:836` — `background`/`color` left `undefined` on purpose (the `: undefined` grep's one deliberate hit), unchanged.

## Final list: UNEXPECTED

**None.** Every grouped change and every changed shot traces to one of: the
Part-1 `Card`/`Band` cursor-inheritance fix, the Part-1 `Searches.jsx:614`
border-colour bug fix (both matching `reconcile-D4c.md`'s predictions
exactly), a documented zero-pixel `SectionHead`/`Tag`/`Chip` primitive
cascade landing on a text-free wrapper element, or a previously-established
class of crawl noise (path-rename missing/added pairs, live-data/timestamp
drift, an `elementFromPoint`-vs-DOM-path mismatch on the cover-letter
editor's `▾` glyph — the same site `reconcile-D4c.md §(B)`'s closing note
already flagged, here reversing rather than newly appearing). The 83/82
missing/added imbalance is fully resolved to one element: a PDF-preview
spinner present in the D4c capture and gone by the D4d capture, a load-timing
artifact, not a lost migration. No migrated element lost keyboard access,
hover feedback, its `data-*`/`href` hooks, or its aria semantics. D4d is
clean — no fix required before proceeding.
