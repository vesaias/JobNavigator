# expected-D6-fixup — closing the font-metric height leaks

Follow-on to `expected-D6.md` §2 ("Font pass") and `reconcile-D6.md` Part 2. Source-only:
no rebuild, no restart, no commit. The running bundle is still the pre-fix D6 build, so
every number below was measured **directly in Chromium**, not inferred from grep.

---

## 1 · Method — real measurements, not guesses

Two passes, both inside the backend container:

1. **Raw crawl diff.** `/tmp/v2t/shots/D6/styles.json` vs `/tmp/v2t/shots/D6alt/styles.json`
   (5641 keys in common), every element whose **rest** `height` differs, then reduced to
   the **45 leaf** diffs (an element with a changed descendant is a cascade, not a
   finding). Grouped by DOM-path suffix + text with `lineHeight`/`fontSize`/`paddingTop`/
   `borderTopWidth` in both skins.
2. **Live Chromium probe** (`/tmp/v2t/probe{,2,3,4}.py`, Playwright against the running
   app so the real webfonts and `--sans/--serif` values are in play): each suspect row
   rebuilt as isolated DOM, measured at `data-skin="default"` and `data-skin="alt"`,
   with **per-child `top` and `height`** — plus a one-child-at-a-time **ablation** to name
   the child responsible, and an A/B of each candidate fix.

### What the measurements actually say

`reconcile-D6.md` guessed three `line-height: normal` sites. Only **one** of them is real
(and not the one named); the rest of the leak — including the unresolved `36 → 37 px`
group — is a **different mechanism**:

> **`align-items: baseline` + mixed font-size children.**
> A baseline-aligned flex row's height is `max(distance above the shared baseline) +
> max(distance below it)`. For a single-line item that distance is `L/2 ± (A−D)/2`, where
> `A`/`D` are the font's ascent/descent **scaled by that item's font-size**. Two items with
> the same `line-height` but different `font-size` therefore contribute different extents,
> and the union is a function of the font's `A−D` ratio. Swap Public Sans/Newsreader for
> Inter/Georgia and the union moves — even though every child's own height is byte-identical
> in both skins. Same thing one level down, inside a single line box, when a small `<span>`
> with no `line-height` of its own sits inside a large serif numeral.

That is why the crawl shows parents growing while **every crawled child stays the same
height** — the signature that misled the earlier read. The three suspects in
`reconcile-D6.md` Part 2 resolve as:

| suspected | verdict |
|---|---|
| `SectionHead` caret `ui.jsx:551` | **real, but via baseline alignment, not `normal`** — the caret inherits `18px`, and it is the *baseline offset* of a 10px glyph in an 18px box that moves. It only leaks in the one head that sets `alignItems:'baseline'` (`ResumeSections.jsx:254`), and there it is **not sufficient on its own** — the `●` "unreviewed" dot beside it leaks identically. |
| Settings `.v2-anchor` rows `Settings.jsx:519` | **not a leak.** No `.v2-anchor` row appears in the 45 leaf diffs; the anchor rail is stable in both skins. The `29→31` group the earlier read attributed to it is in fact the `/v2/resumes` shelf score numeral (below). |
| stage/tier chips `Applications.jsx:837` / `Companies.jsx:124` | **not a leak.** No `33→35` `v2-bd` chip appears in the leaf diffs; the `33→35` group is the Stats KPI numeral. Every `.v2-ctl`/`.v2-chip` in the crawl is height-stable (e.g. `div.v2-ctl.v2-chip` 26px, `v2-bd` voice pills 26px, both skins). |
| unresolved `36 → 37` | **resolved:** `ResumeSections.jsx:254`, the résumé/Persona experience-entry head. Ablation: dropping the caret **or** the `●` dot removes the growth; both must be pinned. |

`v2-ctl`'s `line-height: 1` is doing its job everywhere: **not one** element carrying it
changed height.

---

## 2 · The measured leak list (rest state, 1440×900, dark)

45 leaf height diffs. `L` = leak (fixed below), `R` = allowed reflow, `C` = cascade of one
of those.

| # | route · element | D6 → D6alt | class | cause |
|---|---|---|---|---|
| 1 | `/v2/applications` · row `✉` span ×15 | `12 → 11` | **L** | `line-height: normal` on a 10px glyph |
| 2 | `/v2/persona`, `/v2/resumes/{id}` ×3 · `div.v2-hover-accent` entry head | `36 → 37` | **L** | baseline union — caret + `●` dot |
| 3 | `/v2/settings` ×3 · section head `div:N>div:0` | `56 → 59` | **L** | baseline union — 19px serif title vs 11.5px sub |
| 4 | `/v2/resumes` ×4 · shelf score numeral `span:2` (`71`/`69`/`78`) | `29 → 31` | **L** | nested sans-10 " avg fit" unit inside a serif-17 numeral |
| 5 | `/v2/stats` ×3 · KPI numeral `span:1` (`361`/`377`/`77`) | `33 → 35` | **L** | nested 13px delta unit inside the serif-27 numeral |
| 6 | `/v2/stats` · Score-distribution head | `25 → 27` | **L** | baseline union — 11px `avg …` span |
| 7 | `/v2/stats` · Timeline head | `27 → 29` | **L** | baseline union — two 11px legend spans |
| 8 | `/v2/applications` · detail title `span:1` | `52 → 78` | R | 26px line-height, 2 → 3 lines (Georgia advance) |
| 9 | `/v2/persona`, `/v2/resumes/{id}` ×6 · `<textarea>` | `57→76`, `76→95`, `247→266` | R | 19px line-height, +1 line |
| 10 | `/v2/settings` · helper `span:1` | `16 → 32` | R | 16px line-height, +1 line |
| 11 | `/v2/cover-letters` · voice-pill row | `88 → 119` | R | five `h26` pills wrap onto an extra row |
| 12 | `/v2/stats` ×5 KPI cards `83→85` + card `85→87` | | C | of #5 (grid stretch) |
| 13 | `/v2/stats` funnel/timeline bodies `159→157`, `229→227`, recharts `215→213`, `179→177` | | C | of #6/#7 inside fixed-height cards |
| 14 | `/v2/resumes` shelf rows `29→31`, `100→102`, `132→134`, `63→65` | | C | of #4 |
| 15 | `/v2/settings` `198→201`, `496→515`, `512→515`, `4979→5074`, `55→71`, `36→52` | | C | of #3 + #10 |
| 16 | `/v2/applications` detail `91→117`, `168→194`, `558→532` ×2, `594→568` | | C | of #8 |
| 17 | `/v2/persona`, `/v2/resumes/{id}` `75→94`, `94→113`, `928→947`, `1170→1489` … | | C | of #9 |

No `fontSize`, `fontWeight`, `letterSpacing`, `borderRadius`, `borderTopWidth`,
`paddingTop` or `boxShadow`-offset diff exists on any rest-state element in either skin.

---

## 3 · Fixes

`file:line | element | leak (old → new under alt) | fix`

| file:line | element | leak | fix |
|---|---|---|---|
| `frontend/src/v2/ui.jsx:558` | `SectionHead` caret glyph `<span>` (`⌄`/`›`) | `36 → 37 px` on the head (`ResumeSections.jsx:254`), with the `●` below | add `lineHeight: 1` to the glyph's style object (10px box instead of the inherited 18px). With `align-items:center` the content area stays centred, with `baseline` it stays on the baseline — the glyph does not move in either. **Primitive fix: covers every `SectionHead` call site.** |
| `frontend/src/v2/ResumeSections.jsx:262` | entry-head `●` "unreviewed tailoring" dot, `fontSize: 10`, no `lineHeight` | second half of `36 → 37 px` | add `lineHeight: 1` |
| `frontend/src/v2/Applications.jsx:440` | row `✉` "reply detected" glyph, `fontSize: 10`, inheriting `line-height: normal` | `12 → 11 px` (×15 rows) | add `lineHeight: 1` |
| `frontend/src/v2/Resumes.jsx:220` | nested `" avg fit"` unit (`sans` 10) inside the Persona serif-17 score numeral | numeral `29 → 31 px`, shelf row `29 → 31`, card `132 → 134` | add `lineHeight: 1` |
| `frontend/src/v2/Resumes.jsx:267` | same unit on the base-résumé card | same | add `lineHeight: 1` |
| `frontend/src/v2/Stats.jsx:454` | nested KPI delta unit (`fontSize: 13`) inside the serif-27 numeral | numeral `33 → 35 px`, every KPI card `83 → 85` | add `lineHeight: 1` |
| `frontend/src/v2/Stats.jsx:526` | Score-distribution head's `avg n · tailored n` span (`fontSize: 11`, no `lineHeight`) | head `25 → 27 px`, chart body `159 → 157` | add `lineHeight: 1` |
| `frontend/src/v2/Stats.jsx:557` | Timeline head's two legend spans (`fontSize: 11`, no `lineHeight`) | head `27 → 29 px`, chart body `229 → 227` and the recharts stack `215 → 213` | add `lineHeight: 1` |
| `frontend/src/v2/Settings.jsx:537` | section head row, `alignItems: 'baseline'` | `56 → 59 px` ×3, and `+3 px` through the whole page (`4979 → 5074`) | `alignItems: 'center'`. Both children are exactly 26 px tall (they share `line-height: 26px`), so centring places them **identically** to baseline in the default skin — measured `top` `[26, 26]` before and after, in both skins — while pinning the row to the 26px line instead of a font-dependent baseline union. The load-bearing `26px` line-heights the surrounding comments protect are untouched. |

Nothing else was touched: no colour, no `fontSize`, no padding, no radius, no border.

### Measured result (live Chromium, default vs alt)

| row | before | after |
|---|---|---|
| Applications row `✉` | `12 → 11` | `10 → 10` |
| Résumé entry head | `36 → 37` | `36 → 36` (unchanged at default) |
| Settings section head | `56 → 59` | `56 → 56` (unchanged at default, children at identical `top`) |
| Résumés shelf score numeral | `29 → 31` | `28 → 28` |
| Stats KPI card | `83 → 85` | `80 → 80` |
| Stats Score-distribution head | `25 → 27` | `25 → 25` (unchanged at default) |
| Stats Timeline head | `27 → 29` | `25 → 25` |

### Default-skin geometry this deliberately changes

Four rows land on their **declared** line-height instead of the font-metric overshoot they
had at D6. All are shrinks onto an integer grid, none change a control, and all are
expected to show up as D6 → D7 diffs:

- `/v2/applications` row `✉` box `12 → 10 px` — **no layout effect**: the box is
  transparent, the glyph rides the baseline, and its parent stays `15 px`.
- `/v2/resumes` score numeral `29 → 28`, shelf row `29 → 28`, cards `132 → 131`,
  `100 → 99`, `63 → 62`.
- `/v2/stats` KPI numeral `33 → 30`, KPI cards `83 → 80` (strip `85 → 82`).
- `/v2/stats` Timeline head `27 → 25`; its chart body gains the 2 px inside the
  fixed-height card.

`ui.jsx`'s caret shrinking `18 → 10 px` moves nothing anywhere: under `align-items:center`
the content-area centre is unchanged, under `baseline` the baseline is unchanged. Verified
on both a `center` head (`SectionShell`, `38 px` before and after) and the `baseline` head.

---

## 4 · Checks run

- `py v2-testing/tools/stylelint.py` → **exit 0**, `0 findings, 109 allowed, 0 css`.
- `npx esbuild@0.21.5 --loader:.jsx=jsx --log-level=error` parses all six touched files clean.
- `{}` / `()` / `[]` balance identical to `HEAD` on all six files.
- No rebuild, no restart, no commit; the only `v2-testing` file written is this one.

---

## 5 · Not attributed / left alone

1. **`JobFeed.jsx:1091`** — the report breakdown's `serif 15` numeral with a nested `11px
   /20` unit is the same *shape* as the two fixed numerals, but it **measures stable**
   (`22.5 px` in both skins: the outer 15px box dominates the line). Left untouched rather
   than churned; it is latent, not leaking.
2. **The three `missing` crawl keys.** Two are the Skin `Select`'s own value text
   (`Default — warm paper` → `Alt — cool slate`) — the control reporting the switch, as
   `reconcile-D6.md` says. The third,
   `dark|/v2/settings|…v2-scroll:1>div>div:2>div:2`, remains a viewport-fold artifact of
   `stylecrawl.py` (the page renders taller under Inter and the row's top crosses
   `innerHeight`); unchanged by this fix-up and still unconfirmed by a re-crawl.
3. **The 25 `added` keys** are `stylecrawl.py`'s `r.width < 4` visibility cutoff, not
   geometry: separator `|`/`·` glyphs and closed-state `›` carets that are slightly wider
   under Inter/Georgia. All of them measure `h = 18/16.5/15 px` identically in both skins.
   `stylecrawl.py`'s `<4px` and viewport-edge filters are not skin-stable — a tool note,
   not a product defect.
4. **Hover-state diffs** (`~34` tuples) were not re-examined: they are `elementFromPoint`
   mis-hits with no rest counterpart, already traced end-to-end in `reconcile-D6.md`.
5. **Other `align-items: baseline` rows** (`JobFeed.jsx:1061/1088/1337`,
   `CoverLetterEditor.jsx:40/370`, `ResumeSections.jsx:150/199`, `Stats.jsx:463/605/658`,
   `Persona.jsx:158`, `Applications.jsx:436`, `UiGallery.jsx:30`, `WelcomeModal.jsx:37`)
   are **stable in the crawled state** — `Persona.jsx:158` and `Stats.jsx:658` were probed
   explicitly and hold at `52 px` / `38 px` in both skins. They carry the same latent risk
   whenever a child with a differing `font-size` and no own `line-height` is added; the rule
   to apply is the one used above.

## 6 · Still to run

The D6 gate itself. After a rebuild:

```bash
python /tmp/v2t/stylecrawl.py D7                 # default skin
python /tmp/v2t/stylecrawl.py D7alt --skin alt   # alt skin
python /tmp/v2t/stylediff.py D7 D7alt            # expect: rest-height diffs only on §2's R rows
python /tmp/v2t/stylediff.py D6 D7               # expect: only §3's four documented shrinks
```
