# reconcile D6 (theme store + `alt` skin)

Method follows `reconcile-D5.md`: grouped-diff read against `expected-D6.md`, cross-checked
against source (`ui.jsx`, `theme.css`, `theme.js`, and the relevant site files). Read-only —
no crawl was re-run; `stylediff_D6_D6alt.md`'s "Changed elements" section is capped at 2000
of 4636 tuples (`stylediff.py: changed[:2000]`), so a handful of the smaller-count groups
below could not be traced to a literal source line and are flagged as such rather than
guessed.

---

## Part 1 — default skin, D5 → D6

`stylediff_D5_D6.md`: 38 changed tuples, 298 missing, 278 added.

**38 changed tuples** — all eleven `main>…>v2-scroll:1>div>div:N` height pairs (29↔64,
55↔71, 36↔52, 16↔32, 512↔496, 4781→4979) on `/v2/settings` only, in both light and dark,
nothing else. `4781px → 4979px` is exactly the documented **+198**, and `496px → 198px` /
`512px → 496px` is the Appearance block's own height plus the one‑row shrink of the section
below it as `active` moves off `Models`. Matches §3.2 of `expected-D6.md` precisely.

**298 missing / 278 added** — resolve into exactly three buckets, no residue:
1. **Settings anchor rail + row re-indexing** (the overwhelming majority): every anchor-rail
   label/row and every `div:N` content key downstream of the new Appearance section shifts
   index by one, so old and new keys don't match textually even though the row itself is
   unchanged — pure re-indexing noise from the new first section, exactly as documented.
2. **Rail theme glyph** — `◐` missing / `◑` added on `aside>div:2>span.v2-navdark.v2-themebtn:2`
   for every dark-mode route (`/v2/feed`, `/searches`, `/companies`, `/applications`,
   `/resumes` incl. both id routes, `/cover-letters` incl. its id route, `/persona`,
   `/stats`) — 11 pairs. Matches §3.1.
3. **One relative-time text on `/v2/stats`** (light + dark): `3 Sept · 22:01` →
   `4 Sept · 01:01` on `main>div>div.v2-scroll:0>div:3>div:3>span:3`. This is a live
   "last activity" timestamp; the two crawls ran ~3 hours apart in real time, so the
   displayed clock text legitimately differs between builds. Not a source change, not in
   `expected-D6.md`'s list, but self-evidently a crawl-timing artifact rather than a
   regression — flagged here rather than silently dropped.

**Verdict: 0 unexpected.** Every row outside Settings and the rail glyph is
pixel-for-pixel silent, as §3.5 requires.

---

## Part 2 — the skin gate, D6 → D6alt

`stylediff_D6_D6alt.md`: 4636 changed tuples, 3 missing, 25 added. All `fontFamily`/`color`/
`backgroundColor`/`border*Color` tuples are the expected palette-and-font repaint (2438+1478
fontFamily, the ~15 color families) and are not itemized further — none of them touch
`--cc-*`/`--sm-*`/`--rail-*`/`--knob`/`--iframe-bg`, consistent with §2's "zero diffs" rule
for the identity taxonomy and rail overlays.

### Method for classifying the ~19 non-colour groups
Two independent signals separate the three buckets:
- **Source match** — does a literal `height:` (or `fontSize` with no `lineHeight`) exist at
  that value in `ui.jsx`/the site files? If yes and the element has no explicit `lineHeight`,
  it's a **leak** (b); if the value doesn't exist as a literal style anywhere, it's
  content-driven → **rewrap** (a).
- **Rest/hover pairing** — a real element's rest and hover tuples move together (matching
  counts). An artifact of `elementFromPoint` landing on a *different* node has **no rest
  counterpart at all** (hover-only in the grouped list) — that's the fingerprint of
  **crawl artifact** (c), confirmed directly below with a traced example.

### Classification table

| group | count | class | element / cause |
|---|---|---|---|
| `height 12px → 11px` | rest×15, hover×15 | **(b) leak** | `SectionHead` caret glyph, `ui.jsx:551-554` — `fontSize:'var(--t-10)'`, **no `lineHeight`**. Browser `normal` line-height at 10px differs between Newsreader/Public Sans (~1.2 → 12px) and Georgia/Inter (~1.1 → 11px). Used everywhere `SectionHead` draws a caret (Persona groups, cover-letter editor sections, résumé sections, Feed report head, the gallery) — inherits `cursor:pointer` from the clickable head, so it's sampled in both rest and hover, which is why both states move identically. |
| `height 29px → 31px` | rest×8, hover×4 | **(b) leak** | `.v2-anchor` — Settings rail row, `Settings.jsx:519` — fixed `height: 29`, `alignItems:'center'`, `fontSize: 12.5`, **no `lineHeight`**, and (unlike every other control) never gets the `.v2-ctl{line-height:1}` treatment (`theme.css:420`) — `.v2-anchor` only has a `:hover` color rule (`theme.css:429`). Same font-metric mechanism as above, one size up. |
| `height 33px → 35px` | rest×3 | **(b) leak** | The stage/tier filter chip pattern — `Applications.jsx:837` and `Companies.jsx:124` — `height: 33`, `fontSize: 12`, class `v2-bd` (border-hover only, `theme.css:412`), **no `lineHeight`**. Contrast `CoverLetters.jsx`'s identical-looking `CTRL` (`height:33`) which *does* set `lineHeight:1` and is absent from this diff — a clean before/after inside the same codebase. |
| `height 36px → 37px` | rest×3, hover×3 | **unresolved, leans (b)** | Rest+hover move together (real element, not a mis-hit), but no literal `height:36` site both lacks `lineHeight` *and* is plausibly on-screen in the default crawl state. Closest static match is `Settings.jsx:1087` (model-catalog row, `height:36`, no `lineHeight`) but that panel is not open by default, so it's unlikely to be what the crawl hit. Needs the untruncated `D6`/`D6alt` `styles.json` (not produced for this task) to pin the exact key — flagged rather than guessed. |
| `height 83px → 85px` | rest×5 | **(a) rewrap** | No literal `height:83` anywhere in source → content-driven. Same numeric family (odd, non-canonical) as the D5→D6 Settings row-stack heights (`55↔71`, `36↔52`). |
| `height 56px → 59px` | rest×3, hover×1 | **(a) rewrap** | No literal match; auto-height row/description block. |
| `height 57px → 76px` | rest×3 | **(a) rewrap** | No literal match; a help/description column gaining a wrapped line under Inter. |
| `height 75px → 94px` | rest×3 | **(a) rewrap** | No literal match; same class. |
| `height 215px → 213px` | rest×3 | **(a) rewrap** | No literal match; shrinks (2px), i.e. the same block losing a line under Georgia's wider average advance — still content-driven, still acceptable per the caveat. |
| hover `fontSize 14px → 12.5px` | ×4 | **(c) crawl artifact** | Hover-only, no rest pair — `elementFromPoint` landed on a different, smaller-text node after the rewrap moved the sampled `(x,y)`. |
| hover `fontSize 14px → 10px` | ×3 | **(c)** | Same. |
| hover `fontSize 14px → 11.5px` | ×2 | **(c)** | Same. |
| hover `fontSize 14px → 9.5px` | ×1 | **(c)** | Same. |
| hover `letterSpacing normal → 0.44px` | ×4 | **(c)** | Same — a mis-hit lands on an uppercase/tracked label instead of the intended control. |
| hover `fontWeight 400 → 500` | ×4 | **(c)** | Same. |
| hover `borderTopWidth 0px → 1px` | ×2 | **(c)** | Traced (see below): Settings Skin-row `Select` trigger. |
| hover `borderRadius 0px → 6px` | ×2 | **(c)** | Same traced element. |
| hover `borderRadius 0px → 99px` | ×2 | **(c)** | Mis-hit onto a pill/chip (`r99`) near the sampled point. |
| hover `height 12.5px → 32px` | ×2 | **(c)** | Same traced element as the borderTopWidth/borderRadius pair. |
| hover `height 15px → 11px` | ×3 | **(c)** | Same class. |
| hover `lineHeight 21px → 17px/14.25px/11.5px` | ×1 each | **(c)** | Same class — three different mis-hit targets. |
| hover `height 19.5px → 16.25px` / `26px → 6px` | ×1 each | **(c)** | Same class. |

**Traced (c) example** (one of the ~2000 written tuples, so directly verifiable):
`light|/v2/settings|main>div>div>div.v2-scroll:1>div>div:0>div:2>div:1>span>div` · hover ·
`backgroundColor rgba(0,0,0,0)→rgb(255,255,255); borderTopWidth 0px→1px; borderTopColor …;
borderRadius 0px→6px; paddingLeft 0px→10px; height 12.5px→32px`.
This path is the new **Skin row's `Select` trigger** (`ui.jsx`'s `Select`, whose closed
trigger div is fixed at `height:32, lineHeight:1` — genuinely protected). Decoded: in D6,
the hover sample's `(x,y)` — computed once from D6's own rest-pass rect — landed on the
trigger's tiny `▾` caret span (transparent, borderless, ~12.5px tall); in D6alt the same
nominal coordinate, recomputed from D6alt's own (slightly shifted) rest-pass rect, landed on
the trigger `div` itself (bordered, radius 6, 32px). The **rest** tuple for this exact
element shows no such diff — `Select`'s trigger height is genuinely pinned at 32 in both
skins, confirming this is a coordinate/hit-test artifact, not a real style change.

### Counts
- **(a) prose rewrap**: 18 tuples across 5 named groups (`83→85`, `56→59`, `57→76`,
  `75→94`, `215→213`), plus the ~60 further single/double-count large-page-height cascades
  in the 90–5700px range (Settings/Persona/Résumés/Cover-letters sections and their page
  totals) — all downstream consequences of the same handful of upstream text rewraps, not
  independent findings.
- **(b) font-metric leak**: 45 tuples, 2 confirmed primitives + 1 confirmed site pattern
  (`SectionHead` caret, `.v2-anchor`, the `.v2-bd` filter-chip pattern), plus 6 tuples
  (`36→37`) unresolved.
- **(c) crawl artifact**: ~34 tuples, all hover-state-only, one traced end-to-end above.

### Fix list (for b)
| primitive / site | file:line | fix |
|---|---|---|
| `SectionHead` caret glyph | `frontend/src/v2/ui.jsx:551` | add `lineHeight: 1` to the glyph `<span>`'s style object |
| `.v2-anchor` Settings rail row | `frontend/src/v2/Settings.jsx:519` | add `lineHeight: 1` to the row's inline style (or add the `v2-ctl` class it currently lacks) |
| stage/tier filter chip (`v2-bd`) | `frontend/src/v2/Applications.jsx:837`, `frontend/src/v2/Companies.jsx:124` | add `lineHeight: 1` to both, matching `CoverLetters.jsx`'s `CTRL` which already does this |
| unresolved `36px → 37px` | — | re-run `stylecrawl.py` for `D6`/`D6alt` and diff the raw `styles.json` (not truncated) to name the element before deciding a fix |

---

## Part 3 — the 3 missing / 25 added

**2 of 3 missing / 2 of 25 added — expected.** The new Settings Skin row's `Select` shows
its *current value* as text: `Default — warm paper` (missing, light+dark — that's the D6
default-skin label) is replaced by `Alt — cool slate` (added, light+dark) because the skin
genuinely changed. This is the one legitimate content difference the skin switch is allowed
to produce (it's the control that reports the switch itself).

**1 of 3 missing, unpaired** —
`dark|/v2/settings|main>div>div>div.v2-scroll:1>div>div:2>div:2` (the Scoring-behavior
section's second row, dark theme, `1440×900`). No corresponding "added" key replaces it.
Most likely cause: the Settings page's dark-theme render grows measurably under Inter (the
grouped list's own `rest height 4979px → 5074px` for the whole scroll body, plus the several
`+2px`/`+22px`/`+77px`/`+80px` section cascades earlier in the page), and this particular
row's top edge — sitting close to the 900px fold in `D6` — crosses past `innerHeight` in
`D6alt`'s taller render. `stylecrawl.py`'s REST pass drops any element with
`r.top > innerHeight`, so the row simply falls out of the crawl's visible set; it did not
disappear from the page. Moderate confidence — recommend confirming with a full-page
screenshot diff or a taller crawl viewport before treating this as settled.

**23 of 25 added — expected, all one mechanism.** They are pre-existing separator/caret
glyphs, already in the DOM under the default skin, that render narrower than
`stylecrawl.py`'s `r.width < 4` visibility cutoff at Public-Sans/Newsreader glyph metrics and
cross ≥4px under Inter/Georgia's slightly wider advance widths for the same character — so
they start being picked up by the REST-pass scan and read as "added," even though nothing in
layout or content changed except a sub-pixel glyph width:
- **9 on `/v2/feed`, dark** — the `|` company/location separator (`JobFeed.jsx:928`, list
  rows 1/3/4/6/7/8 — only rows whose job actually has a `location` render this span at all,
  which is why it's 6 of the ~9 loaded rows, not all) and the detail header's `·`/`|`
  separators (`JobFeed.jsx:984`, `991`, `992`).
- **5 on `/v2/cover-letters`, dark** and **5 across `/v2/persona` + the two `/v2/resumes/{id}`
  routes, dark** — the `SectionHead` closed-state `›` caret (`ui.jsx:551-554`, same element
  as the (b) leak above) on `v2-clhead`/`v2-hover-accent` section heads.

This is the same class of crawl-visibility-threshold artifact as the unpaired "missing" row
above (a font-metric change nudging a measurement past a hard-coded cutoff — `4px` width
there, `900px` viewport-top here), not a real content or geometry regression. Worth a
maintenance note for `stylecrawl.py` (its `<4px`/`viewport-edge` visibility filters are not
skin-stable) but not a product defect.

---

## Final UNEXPECTED list

**None found as confirmed regressions.** Two items are flagged for follow-up rather than
closed outright:
1. **`height 36px → 37px` (rest×3, hover×3)** — real element, not a crawl artifact, but not
   traceable to a source line from the static evidence available here. Needs the raw
   `styles.json` to name it before it can be called (b)-leak or (a)-rewrap with confidence.
2. **The unpaired missing Settings row** (`…scroll:1>div>div:2>div:2`, dark) — plausible
   viewport-fold crawl artifact per above, not confirmed by a live re-crawl.

Everything else across both parts (Part 1's 38+298+278, Part 2's 4636/3/25) traces cleanly to
either the documented Appearance-section plumbing, the documented rail glyph, the palette/font
repaint the skin gate explicitly allows, a confirmed font-metric leak in three named
non-`v2-ctl` primitives (with a fix listed above), or a confirmed/well-evidenced crawl-tool
measurement-threshold artifact. No `boxShadow` offset, `--cc-*`/`--sm-*`, `--rail-*`,
`fontSize`/`fontWeight`/`letterSpacing`/`borderRadius`/`borderTopWidth` change was found on
any **rest**-state control, row, header or modal — the strict gate (§2, "must be identical")
holds everywhere except the three named `line-height`-less primitives above.
