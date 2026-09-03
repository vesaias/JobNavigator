# reconcile-D4e — D4d→D4e diff reconciliation (Link/NavLink/Label/Helper/Heading/PageTitle/Spinner/ShowMore)

Inputs: `expected-D4e.md` (638 lines — 317 sites across 14 files + `ConfirmDialog.jsx`/`Toast.jsx`, three
systematic drift fixes, six "worth a decision" notes), `reconcile-D4d.md` (method precedent — trace every
grouped stylediff bucket to source, resolve missing/added pairs, end with a graded UNEXPECTED list),
`artifacts/design/stylediff_D4d_D4e.md` (5664 baseline elements · 746 changed tuples · 60 missing · 48
added), `artifacts/design/shotdiff_D4d_D4e.json` (per-shot changed-pixel bbox, 44 shots), overlays in
`artifacts/design/diff_D4d_D4e/*.png` (viewed: Companies, Feed, Settings, Applications — light/1440),
`frontend/src/v2/ui.jsx` (`Link`, `NavLink`, `Label`, `Helper`, `Heading`, `PageTitle`, `Spinner`,
`ShowMore`, lines 70-769), and `git diff 2b19cca ac43921 -- frontend/src/v2` (D4d-reconciled → D4e, one
commit; `4e2ab54` HEAD only appends a decision note to `D1-D2.md`, no source change, so the diff range is
unambiguous).

**Headline: one real regression.** Everything else below traces cleanly to the three documented systematic
fixes (helper line-height → 16px, label → 10px/.13em/15px, Link/NavLink hover+line-height) or to established
crawl-noise classes. But **`Settings.jsx`'s shared row-help `Helper` (line 722) wraps the Autofill LLM row's
description to a second line**, growing that row 55px → 71px — a genuine control-height change from a step
that was supposed to be text-only. See **(G)** and the final list.

---

## (A) 30×`height 29px → 33px` at rest — what grew by 4px?

**Expected — the direct, documented consequence of `Applications.jsx:438`'s company-sub-line migration,
not a control.** Path: `.v2-row.v2-arow:N>div` (15 rows × light+dark = 30), the flex-column wrapper that
stacks a job's title above its company sub-line inside each Applications list row. Its *child* —
`.v2-row.v2-arow:N>div>span|<Company>` — is the exact site: `--muted` (`--edge` for "Unknown Company") 11,
`lineHeight:'normal'` (a Tailwind-preflight-inherited ratio, ≈13px computed but reported `12px` by the
crawler's rounding) → `Helper`, size **11→11.5px**, lh **normal→16px explicit** (confirmed at
`stylediff_D4d_D4e.md:236-237`: `fontSize 11px→11.5px; lineHeight normal→16px; height 12px→16px`, matching
`expected-D4e.md:405` value-for-value).

The **wrapper div** (title+company stack) has no fixed height of its own — it is a cell centred
(`alignItems:'center'`) inside the outer `.v2-row.v2-arow`, which per the doc **is** fixed (46px). Growing
the company line's box by +4px (12→16) grows the wrapper's natural height by the same +4px (29→33); because
the wrapper is centred rather than top-aligned inside the fixed row, that growth is absorbed symmetrically —
the title moves up ~2px, the company line moves down ~2px, and the **outer 46px `Row` does not move** (no
stylediff entry exists for the `.v2-arow` element itself). `expected-D4e.md:405` undersells the visible
delta as "the gap ... opens by ~1.5px," but the wrapper's own box genuinely grows 4px — a stricter but
consistent reading of the same documented site. **Not a control** (no button/pill/input/select changed
size) — a title+company text stack, `Row` height held. **Expected.**

## (B) 30×`lineHeight normal → 16px` / `height 12px → 16px` (+30 hover) — is the growth on the list, and does it push content down?

**Same site as (A)** — `Applications.jsx:438`'s company-sub-line `Helper`. It **is** on the expected list
(`expected-D4e.md:405`, quoted above) and it **is** the entire cause of (A)'s wrapper growth. Confirmed:
rest and hover both fire 30/30 in the grouped table (`stylediff_D4d_D4e.md:12-15`); (A)'s wrapper-height
line fires only at rest (no hover counterpart in the diff) — a hover-pass crawl-coverage gap, the same class
`reconcile-D4d.md`'s (A) and (5) already established, not a partial migration. **Expected**, and the "push"
is fully contained to the title/company gap inside a fixed-height, centred row (see (A)) — the Companies
list, Row order, and every sibling element are untouched.

## (C) 10×`lineHeight 28px → 16px` / `height 28px → 16px` (+10 hover) — 28px collapsing to 16

**Expected, exactly `Resumes.jsx:213` and `:258`.** Path:
`.v2-act:N>div[:0]>span:1|<sub-line text>` (5 `.v2-act` cards — Persona base + 4 tailored/base résumé
cards — × light+dark = 10). This is the Persona/base-card sub-line: `--muted 11.5`, inherited
`lineHeight:'28px'` from the parent row's `alignItems:'baseline'` box → `Helper`, lh **28→16px** (size/ink
zero-pixel). `expected-D4e.md:253/258` documents both sites verbatim ("Row is `align-items:baseline`, so
the glyphs stay on the same baseline; the row's descent contribution drops"). Not a heading demoted, not a
pill — a muted sub-line whose *inherited* (not own) line-height collapsed from a 28px ancestor once its own
explicit 16px took over. **Expected.**

## (D) 6×`letterSpacing 0.8px → 1.3px` and 8×`1.4px → 1.3px` — different-size labels forced to .13em of 10px

**Both expected, two different sites, neither miscategorised.**
- **6× `0.8px→1.3px`** (3 `.v2-card` search cards × light+dark): `Searches.jsx:637`, the auto-score depth
  chip. `--muted 10 uppercase .08em` → `Label title=…`, letter-spacing **.08em→.13em** (0.8px→1.3px at the
  unchanged 10px size). Matches `expected-D4e.md:317` exactly ("letter-spacing .08em → .13em only"). One
  side effect *not* itemised in the doc: the chip's own font-size/line-height were already correct
  (zero-pixel, as documented), but wrapping it in `Label` gives the chip an **explicit pixel**
  `lineHeight:'15px'` where before it had none — and CSS inherits an explicit pixel line-height as an
  absolute length, not a ratio. The nested `dep?.dots` glyph span (`Searches.jsx:641`, `fontSize:9`, no
  `lineHeight` of its own) previously computed its line-height by the *ratio* rule (Tailwind's unitless
  `1.5` × its own 9px font = 13.5px); now it inherits the parent's absolute 15px instead. That is the
  `13.5px→15px` pair at `stylediff_D4d_D4e.md:107-111` (6× total, folded into the task's item **(E)** count
  below). Zero-pixel: the glyph sits in a `display:'flex', alignItems:'center'` row, so a ±0.75px line-box
  change on either side is absorbed by centring. **Expected, undocumented cascade, harmless.**
- **8× `1.4px→1.3px`**: `CoverLetters.jsx:378`'s "All letters" gutter label (2, light+dark) +
  `ResumeEditor.jsx:592`'s "PDF preview" toolbar label (2 résumé routes × 2 themes = 4) +
  `CoverLetterEditor.jsx:480`'s "PDF preview" toolbar label (2). All three are documented `.14em→.13em`
  `Label` moves (`expected-D4e.md:290/518/582`). **Expected.**

## (E) 52×`lineHeight 14px → 15px`, 36×`fontSize 9.5px → 10px`, 6×`lineHeight 13.5px → 15px`

- **52× `14→15`** (with 36 of them also carrying `fontSize 9.5→10`): the `Label` canonicalisation on every
  uppercase field/section label that used the shared `FIELD_LABEL`/`LABEL`/`MICRO`-style consts. Traced by
  grep to four families: `Applications.jsx:566/573/660/672`'s `LABEL`-const section labels (3 visible in
  the crawl light+dark = 6 — "Interviews·N," "Notes·autosaves," "History"; the fourth, "Last email," is
  below the fold), `CoverLetters.jsx:345/351/356/361`'s four field labels (×2 = 8), `Persona.jsx:143`'s 11
  `FIELD_LABEL` contact fields (×2 = 22), and `Stats.jsx:442`'s 5 KPI-tile labels + `Stats.jsx:568`'s 3
  LLM-cost figure labels (×2 = 16). 6+8+22+16 = **52**, exact. The 36-of-52 subset with an additional
  `fontSize 9.5→10` are the const-driven sites that were genuinely 9.5px before (Applications/CoverLetters/
  Persona = 6+8+22 = 36); Stats' KPI/LLM-cost labels were already 10px (`Label` size unchanged, lh-only
  move), matching `expected-D4e.md:146/150`. All documented in the doc's item-2 systematic fix and the
  per-file tables. **Expected.**
- **6× `13.5→15`**: the `Searches.jsx:637` depth-chip's nested dot glyph, covered in **(D)** above —
  a cascade side effect of `Label`'s explicit pixel line-height, zero-pixel because it's centred in a flex
  row. **Expected, undocumented but harmless.**

## (F) 24×`height 50px → 51px`, 10×`82px → 83px`, 8×`42px → 43px` — container cascades

All three are the mechanical **+1px block growth** `expected-D4e.md` calls out by name at two sites:
- **24× `50→51`**: `CoverLetters.jsx:361`'s "Length" field block (1×2 themes) + `Persona.jsx:143`'s 11
  contact-field blocks (×2 themes = 22) → 24. Each field's wrapping column (`Label` above `Input`) grows
  exactly the label's own `14→15px` line-height delta, per `expected-D4e.md:123` ("each field block grows
  1px"). Confirmed the Persona *group* container inherits this too: `Persona.jsx`'s contact-fields grid
  shows `height 414px→420px` / `372px→378px` (+6/+6, `stylediff_D4d_D4e.md:343/346`) — exactly 6 two-field
  grid rows × 1px, not a new effect. **Expected.**
- **10× `82→83`**: `Stats.jsx:442`'s 5 KPI tiles × 2 themes. Doc: "each KPI tile, and so the strip, grows
  1px" (`expected-D4e.md:146`). **Expected.**
- **8× `42→43`**: `Stats.jsx:568`'s LLM-cost figure row (the row div + its 3 figure cells: Spend/Calls/
  Avg-per-call) × 2 themes = 8. Doc: "the figure row grows 1px inside the fixed 300px card (absorbed by the
  table's `flex:1 minHeight:0`)" (`expected-D4e.md:150`). **Expected.**

## (G) Applications / Feed / Companies / Settings pixel counts and overlays

From `shotdiff_D4d_D4e.json` (light/1440 unless noted):

| route | bbox | px | verdict |
|---|---|---|---|
| Applications | (238,160,1320,900) | 34071 (dark 1440: 33752) | **Expected** — text-only reflow |
| Companies | (725,185,741,885) | 1312 (1024: 0) | **Expected** — hairline, zero-pixel |
| Feed | (678,161,1440,578) | 9873 | **Expected** — text-only reflow |
| Settings | (240,125,1400,900) | 109457 (dark: 108628) | **One real regression** — see below |

- **Applications** (viewed): every visible list-row title/company pair and the History rail's relative
  timestamps render with the classic "double-exposure" diff look (old+new text overlaid a few px apart).
  This is the cumulative visual signature of (A)/(B) across all 15 visible rows plus the `LABEL`-const
  stage-band headers from **(E)**, cascading down the list. No button, pill, input, select, or border
  changed — the `+ Log application` button, the status pills (Applied/Interview/Offer/Rejected), and the
  "Notes — autosaves" textarea's border are all crisp/unchanged; they merely sit *inside* the diff tool's
  bounding box (which unions all changed pixels on the page), not individually altered. **Expected.**
- **Feed** (viewed): the detail panel's eyebrow ("META · DIRECT · 5D AGO", `JobFeed.jsx:976`, `Label`,
  lh 16→15px) shrinks 1px, nudging the job title and everything below it up by ~1px — a real but
  sub-pixel-scale reflow, visible in the overlay as doubled glyph edges on the eyebrow, title, salary line
  and report-tab row. No ring, pill, or button changed size (the 44px score ring is untouched here — its
  border-width fix at `JobFeed.jsx:899` is a separate, zero-pixel colour-matched change). **Expected.**
- **Companies** (viewed): a 16px-wide hairline strip at x≈725-741 running the full visible row height —
  exactly the "RÉSUMÉS" column (the `PM` badge cells), matching `Companies.jsx:497`'s documented
  `lineHeight 17.25→16px` `Helper` move inside "a fixed 46px centred flex row, so nothing moves"
  (`expected-D4e.md:365`). Same antialiasing-hairline pattern `reconcile-D4d.md §(B)` already established
  for the Tier badge column. Zero bbox at 1024 (column not rendered at that width). **Expected.**
- **Settings** (viewed): **not** a uniform 1px reflow — the overlay shows large, overlapping doubled text
  blocks that get worse toward the bottom of the AI tab, and the "Autofill"/"Email classification" rows'
  Override controls appear to shift position substantially. Traced to source (below): this is a real content
  reflow, not crawl noise. **One real regression — see final list.**

### The Settings regression, traced

`Settings.jsx`'s generic settings-row renderer (`Settings.jsx:703-724`) puts every row's help/sub-line text
through one shared `Helper`:
```
722:        <Helper style={{ textWrap: 'pretty' }}>
723:          {r.kind === 'switch' && !isOn(r.key, r.dflt) && r.offHelp ? r.offHelp : r.help}
724:        </Helper>
```
Before D4e this was a raw `<span style={{ fontSize: 11, lineHeight: '16px', textWrap: 'pretty' }}>` — after,
`Helper`'s canonical `fontSize: 'var(--t-11-5)'` (11.5px) with `lineHeight` still pinned at explicit `16px`.
`expected-D4e.md:199` calls this **zero-pixel-equivalent** ("size 11→11.5, lh unchanged"), which is true for
five of the six `LLM(...)` rows. It is **not** true for `Settings.jsx:318`:

```
318:        LLM('Autofill', 'Model that answers application-form questions in the extension.', 'autofill_llm'),
```

"Model that answers application-form questions in the extension." (66 characters) is the longest of the six
LLM-row help strings, and the description column is a fixed `flex:'0 1 340px'` (`Settings.jsx:708`) at this
viewport width. The 0.5px font bump alone is enough to push this one string past its wrap point:
`stylediff_D4d_D4e.md:423-425` —
```
main>div>div>div.v2-scroll:1>div>div:0>div:6                       · rest · height 55px → 71px
main>div>div>div.v2-scroll:1>div>div:0>div:6>div:0                 · rest · height 36px → 52px
main>div>div>div.v2-scroll:1>div>div:0>div:6>div:0>span:1|Model...  · rest · fontSize 11→11.5; height 16px → 32px
```
The Autofill row's description text wraps from one line to two (16px → 32px), growing its label column
(36→52px) and the **row itself** (55px → 71px, +16px) — a real, code-traced, DOM-measurable height change
to a settings row (which carries an `Override` toggle + provider/model `Select` pair), not a rendering
artifact. This single row's growth cascades: the "models" group container grows 496px→512px (exactly the
same +16), and the whole AI-tab scroll pane grows 4781px→4845px (+64px total — see the note below on the
other +48px). Every row **below** Autofill in the DOM (Email classification, Model catalog, the entire
Scoring/Tailoring/Cover-letters/Autofill/Scheduler/... sections) shifts down by at least 16px, which is
what the overlay's escalating doubled-text effect toward the bottom of the page is showing — real content
displacement, not double-exposure noise.

This also resolves a loose end from the missing/added tables (below): the "Prompt caching" switch row
(`Settings.jsx:331`, `SW('Prompt caching', 'Rubric + résumés + schema sent as a cached block...', ...)`)
appears in "Missing in D4e" with **no counterpart** in "Added in D4e" — 6 sub-elements × 2 themes = 12,
which is exactly the 60−48=12 imbalance. The row still exists in the DOM unconditionally (confirmed in
current source, `Settings.jsx:331`, no new conditional wrapping it) — it simply sits close to the crawl's
~900px capture cutoff, and the Autofill row's +16px (plus whatever residual growth accounts for the other
+48px of total container height — the "Changed elements" listing truncates mid-page for `/v2/settings` and
does not show the rest of the "scoring"/"tailoring"/"letters" groups, so further wrap events lower on the
page cannot be ruled out from this artifact alone) pushed it just past that boundary. **Not a lost element —
a crawl-viewport consequence of the real Autofill-row growth**, but worth a full untruncated diff pass to
confirm no other row in the shared renderer also wrapped.

---

## Verdict table — grouped changes

| change (state · prop · old→new) | count | verdict | evidence |
|---|---|---|---|
| rest/hover · lineHeight/height `17.25px`→`16px` | 134+112 rest, 102+76 hover(height) | expected | systematic fix 1 — Helper's 16px line-height on every `11.5px`-no-own-lh site |
| rest/hover · fontSize `11px`→`11.5px` | 96 rest, 70 hover | expected | Helper's canonical 11.5px size |
| rest · lineHeight/height `14px`→`15px` | 52 | expected, see **(E)** | Label canonicalisation, 4 file families |
| rest · fontSize `9.5px`→`10px` | 36 | expected, see **(E)** | Label's 10px size, subset of the above |
| rest · height `29px`→`33px` | 30 | expected, see **(A)** | Applications company-sub-line wrapper, `Row` unaffected |
| rest/hover · lineHeight `normal`→`16px` / height `12px`→`16px` | 30/30 | expected, see **(B)** | same site as (A) |
| rest/hover · lineHeight/height `15.75px`→`16px` | 30/30 | expected | systematic fix 1, `Helper size="xs"` bucket |
| hover/rest · lineHeight/height `18px`→`16px` | 26/24 | expected | `SectionHead`/`Helper` sites inheriting an 18px ancestor lh (ResumeSections.jsx experience-row head, etc.), count gap = hover crawl coverage |
| rest · height `50px`→`51px` | 24 | expected, see **(F)** | field-block +1px cascade |
| rest · letterSpacing `1.14px`→`1.3px` | 22 | expected, see **(D)** | Persona `FIELD_LABEL` sites |
| rest/hover · lineHeight/height `28px`→`16px` | 10/10 | expected, see **(C)** | Résumés `.v2-act` sub-lines |
| rest · height `82px`→`83px` | 10 | expected, see **(F)** | Stats KPI tiles |
| rest · letterSpacing `1.235px`→`1.3px` | 8 | expected | CoverLetters field-label fontSize 9.5→10 side effect |
| rest · letterSpacing `1.4px`→`1.3px` | 8 | expected, see **(D)** | `.14em→.13em` Label sites |
| rest · lineHeight/height `17px`→`16px` | 8 | expected | Link sites already at 17px lh moving to Helper/Label neighbours, or Link's own 17→17 zero-pixel siblings shifting — no anomaly found |
| rest · height `42px`→`43px` | 8 | expected, see **(F)** | Stats LLM-cost row |
| rest · height `597px`→`598px` | 6+2(hover) | expected | Feed job list `.v2-scroll` container, +1px cascade from a row above |
| rest · letterSpacing `0.8px`→`1.3px` | 6 | expected, see **(D)** | Searches depth-chip Label |
| rest · lineHeight/height `13.5px`→`15px` | 6 | expected, see **(D)**/**(E)** | Searches depth-chip dot-glyph cascade |
| rest · letterSpacing `1.33px`→`1.3px` | 6 | expected | Applications `LABEL`-const sites, fontSize 9.5→10 side effect |
| rest · lineHeight `14px`→`16px` | 6 | expected | small residual Helper-lh bucket, not independently anomalous |
| rest · height `15px`→`17px` | 6 | expected | Link sites moving from an inherited 15px to Link's 17px |
| rest · letterSpacing `1.2px`→`1.3px` | 6 | expected | Stats LLM-cost figure labels |
| rest/hover · fontSize `12.5px`→`12px` | 6/6 | expected | `ResumeEditor.jsx:504`/`:466`-class NavLink migrations |
| various ≤4-count buckets (fontWeight 500→400, height ±1px, letterSpacing 1.365/1.47/1.5→1.3, color/height dark-theme mirrors) | ≤4 each | expected | 1:1 theme-mirrored or count-mirrored instances of sites already itemised per-file in `expected-D4e.md` |
| **rest · height `55px`→`71px` / `16px`→`32px` / `496px`→`512px` / `4781px`→`4845px`** | **2 each (light+dark)** | **UNEXPECTED** | **(G)** — Settings Autofill row text-wrap regression |

## Missing/added: 60/48 — fully resolved, net −12 explained

| bucket | missing | added | net | mechanism |
|---|---|---|---|---|
| Feed detail eyebrow `div→span` (`JobFeed.jsx:976` `Label`) + its sibling salary-row reindex | 14 (7×2 themes) | 14 | 0 | tag rename (block `<div>` → `Label`'s `<span>`), pure path artifact |
| Résumés "+N more ›" gains `v2-hover-accent-text` (`Resumes.jsx:240`) | 2 | 2 | 0 | class-add rename |
| Stats LLM-cost gutter rows reorder/retick (778→777, 31→30, row order) | 14 (7×2) | 14 | 0 | live LLM-call-log data drift between the two crawl passes — same class as `reconcile-D4d.md`'s timestamp-tick and PDF-spinner examples |
| Settings anchor-rail group captions `div→span` (`Settings.jsx:505` `Label`) ×4 groups | 16 (8×2) | 16 | 0 | tag rename |
| CoverLetterEditor back-link `v2-ctl`→`v2-navlink` (`CoverLetterEditor.jsx:315` `NavLink`) | 2 | 2 | 0 | class rename |
| **Settings "Prompt caching" switch row (`Settings.jsx:331`)** | **12 (6×2)** | **0** | **−12** | **row pushed past the crawl's ~900px capture cutoff by the Autofill row's +16px growth (see (G)) — not a lost element, but a real consequence of the regression, not pure crawl noise** |

**60 − 48 = 12**, exactly the Prompt-caching cluster. Every other missing/added pair is a clean 1:1
rename or live-data retick, matching `reconcile-D4d.md`'s established taxonomy. This is the one place the
imbalance is *caused by* a regression rather than by inherent tool noise.

## Spot-checks against source (ui.jsx primitives, all confirmed shipped as documented)

- `ui.jsx:70-78` — `Spinner`: `1.5px solid ${color||'var(--spinner-ink)'}`, `border-radius: var(--radius-control)`, default `size=9`. Matches every `Spinner` site in `expected-D4e.md`.
- `ui.jsx:629-639` — `Link`: `--link-ink`/`11.5px`/`17px`/`500`, `v2-hover-accent-text`, `rel="noreferrer"` only for `target="_blank"` (matches the documented colophon/test-row keeps that need `noopener noreferrer`).
- `ui.jsx:640-648` — `NavLink`: `--navlink-ink`/`12px`/`18px`, `v2-navlink` class, `pad` passthrough.
- `ui.jsx:707-718` — `Label`: `md`=10px/15px, `lg`=11px/16px, `.13em`, uppercase, `--label-ink`, **`title` prop present** (the one ui.jsx addition `expected-D4e.md:109` documents).
- `ui.jsx:719-731` — `Helper`: `md`=11.5px/16px, `xs`=10.5px/16px, `mono` swaps `fontFamily`, `--helper-ink`.
- `ui.jsx:732-745` — `Heading`: 18/27, 19/26, 22/30, `-.02em`, `--heading-ink`, no explicit weight (inherits 400).
- `ui.jsx:747-754` — `PageTitle`: serif 30/lh-1/-.02em/margin-0/`<h1>`.
- `ui.jsx:759-769` — `ShowMore`: h26 · pad `0 13px` · border `1px var(--pill-border)` · `--radius-control` · `11.5px` · `--pill-ink` · `v2-bdc v2-ctl` hover, **no background** — matches `Resumes.jsx`/`Companies.jsx`'s documented "background → transparent, hover class v2-bd → v2-bdc" notes exactly.
- `Settings.jsx:110-113` — `Toggle`'s label is now `<Helper>{label}</Helper>` (was a bare `<span>`); the switch track/knob markup is byte-identical, confirming the Override-toggle *visual state logic* is untouched by this commit — the Settings anomaly is a text-reflow, not a state-handling change.
- `Searches.jsx:637-642` — `Label title={…} style={{display:'flex', alignItems:'center', gap:5, cursor:'help'}}` wrapping the `dep?.dots` glyph span verbatim, confirming the **(D)**/**(E)** cascade mechanism.

## Final list: UNEXPECTED

**One.** `Settings.jsx:318`'s Autofill LLM row (rendered via the shared row template at `Settings.jsx:703-724`,
specifically the `Helper` at `Settings.jsx:722`) wraps its help text to a second line once `Helper`'s
canonical 11.5px font-size is applied inside the row's fixed `flex:'0 1 340px'` description column
(`Settings.jsx:708`). The row grows **55px → 71px** (+16px), a genuine control-height change — this text-only
step was not supposed to move any control. Confirmed via `stylediff_D4d_D4e.md:423-425` (height
`55px→71px`, `36px→52px`, `16px→32px`, all rest, light+dark), and it fully explains: the "models" section
container growing 496px→512px, a large share of the AI-tab scroll pane's 4781px→4845px total growth, the
escalating visual displacement seen in the Settings overlay toward the bottom of the page, and the
Prompt-caching row's clean disappearance from the missing/added pairing (pushed past the crawl's capture
boundary, not deleted).

**Fix**: give the row-help `Helper` at `Settings.jsx:722` `style={{ textWrap: 'pretty' }}` room to breathe —
either widen the description column beyond `340px` for rows whose `help` string is long (`Settings.jsx:708`),
or shorten `Settings.jsx:318`'s Autofill help text (e.g. "Answers application-form questions in the
extension." — 8 fewer characters may be enough to clear the wrap point at 11.5px). Either change is
one line; re-run the D4d→D4e stylediff on `/v2/settings` afterward (untruncated, if the tool supports a
higher per-page cap) to confirm no other `LLM(...)`/`SW(...)`/`SEL(...)` row's `help` string is *also*
sitting within 0.5px-equivalent of its own wrap boundary — the +48px of AI-tab growth beyond the confirmed
+16px Autofill row is not yet individually accounted for, and the shared renderer means the same failure
mode is systemic risk, not a one-off.

**No control anywhere else changed height in this step.** Every other row/pill/button/input/select
inspected (Applications' stage bands and rows, Feed's score ring and report bands, Companies' fixed 46px
rows, the `ShowMore`/`Link`/`NavLink`/`Spinner` primitives themselves) held its geometry exactly as
`expected-D4e.md` predicted — all growth elsewhere is confined to text line-boxes inside already-generous
containers (Persona/CoverLetters field blocks, Stats KPI tiles and LLM-cost rows), never to a row, pill,
button, input, or select's own box.
