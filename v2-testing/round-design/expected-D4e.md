# expected-D4e — Link / NavLink / Label / Helper / Heading / PageTitle / Spinner / ShowMore

D4e routes every inline link, back-link, uppercase label, helper/sub-line, heading,
page title, spinner ring and "Show more" pager in `frontend/src/v2/*.jsx` through
`Link` / `NavLink` / `Label` / `Helper` / `Heading` / `PageTitle` / `Spinner` /
`ShowMore` from `./ui` (`UiGallery.jsx` + `ToastLab.jsx` out of migration scope;
`V2App.jsx`'s rail text is a named keep). Behaviour is untouched: `href`/`target`,
`onClick`, `title`/`aria-*`, ellipsis and `maxWidth` clamps, and the keyboard
contract — `Link`/`NavLink` supply `kb()` themselves, so hand-written
`tabIndex`/`role`/`onKeyDown` pairs were deleted, never dropped.

Rows are `file:line | element | before → after`, line numbers **after** the change.
A row marked **zero-pixel** changes nothing and is listed for the record.

**Scanner counts (`tools/stylescan.py`, in-scope files only)**

| role | before | after | migrated |
|---|---|---|---|
| helper-text | 147 | 23 | 124 |
| label | 58 | 20 | 38 |
| heading | 45 | 25 | 20 |
| link | 26 | 4 | 22 |
| page-title | 10 | 1 | 9 |
| spinner | 11 | **0** | 11 |
| section-head | 11 | 11 | 0 (D4d's role — the 9 "remainders" turned out to be links, glyphs and menu heads; see below) |

Every remaining site is a listed keep. The scanner only sees literal
`style={{…}}` objects, so it **undercounts**: nine shared style consts
(`helpTxt`, `HELP`, `NOTE`, `MICRO`, `UPPER`, `FLABEL`, `LABEL`, `FIELD_LABEL`,
`CHIP_LABEL`) were deleted or reduced to layout-only, and their ~60 call sites
migrated with them without ever appearing in the scan.

---

## The three systematic drift fixes (the bulk of the diff)

**1. Helper line-height → 16 px.** v2 inherits Tailwind preflight's
`line-height:1.5` on `html`, so a sub-line with no `lineHeight` of its own
computed to 1.5 × its size. `Helper` declares a whole-pixel **16 px** at both
sizes. Measured across the 124 migrated helper sites:

| before (size · own line-height) | sites | line-height move |
|---|---|---|
| 11.5 · none (inherited **17.25**) | **49** | 17.25 → 16 |
| 11.5 · explicit 17px | 11 | 17 → 16 |
| 11.5 · explicit 16px | 3 | zero-pixel |
| 11 · none (inherited 16.5) | 21 | 16.5 → 16 (+ size 11 → 11.5) |
| 11 · explicit 16 / 17 / 15px | 3 / 1 / 1 | → 16 (+ size 11 → 11.5) |
| 10.5 · explicit 16px | 17 | zero-pixel |
| 10.5 · none (inherited 15.75) | 10 | 15.75 → 16 |
| 10.5 · explicit 15px | 2 | 15 → 16 |
| 10 · none (inherited 15) | 4 | 15 → 16 (+ size 10 → 10.5) |
| 10 · explicit 16px | 2 | zero-pixel (+ size 10 → 10.5) |

A handful of const-driven sites moved from an inherited **18 px / 20 px / 26 px /
28 px** (a parent row's explicit line-height) or from `lineHeight:'normal'`; each
is listed in its file section with the note that the row's height is held by a
taller sibling.

**2. Label → 10 px · .13 em · 15 px.** v2 had .05 / .08 / .1 / .11 / .12 /
**.14** / .15 em in circulation. Of the 38 scanned label sites migrated:
**.14em → .13em ×14**, **.15em → .13em ×12**, .12em → .13em ×1, .08em → .13em ×1,
already .13em ×10; sizes 9.5 → 10 ×4, 10.5 → 10 ×8, 11 → `size="lg"` ×2.
The const-driven sites add another ~19 at .14em and ~6 at .12em.

**3. Link/NavLink gain their hover class and a whole-pixel line-height.** Most
inline links carried no hover class at all; `Link` adds `v2-hover-accent-text`,
which is a **no-op today** because `--link-ink-hover` = `--link-ink` = `--accent`
in both themes — it exists so a theme can differentiate them. The three sites
that carried `v2-anchor` lose its darker `--anchor-ink-hover` (`--text`) hover.
Line-height goes to 17 px (from an inherited 17.25). Ten links were already
11.5/500; the rest moved 10.5 / 11.5-no-weight / 12 / 12.5 / 13 onto it.

## Scope calls made in this step (worth a decision before D5)

- **Two serif families.** `Heading` is serif 18/27, 19/26, 22/30 at **-.02em** and
  **weight 400**. v2 also draws a *card/column-title* family — serif 15 / 15.5 / 16 /
  17 / 18 / 19 at **weight 500-600** and -.01/-.015em (`Stats`' `H`, `Persona`'s
  `ColumnHead`, `Companies`' three drawer sections, `Searches`' two card titles,
  `CoverLetters`' row title + "Generate new", `Settings`' section title, `Résumés`'
  base cards, the Feed row title) — plus five orphan 400-weight display sizes
  (20, 21, 23 ×3, 27) and six serif **score numerals** (13.5 / 14 / 15 / 17 / 19).
  **D4e migrated the 400-weight 18/19 family only**; all 25 remaining serif sites
  are `// ui: keep` with a reason. Collapsing them is a design decision (new named
  `Heading` steps, or a redesign onto three), not a drift fix.
- **Size tolerance.** A site within **1.0 px** of a canonical step was collapsed
  (helper 11 → 11.5 and 10 → 10.5; label 9.5/10.5 → 10; link 10.5/12/12.5 → 11.5);
  anything further is a keep (helper at 9 / 9.5, label at 8, heading at 13.5-17).
- **Row cells vs sub-lines.** Muted small text centred in a **fixed-height row**
  (Companies' list cells, Stats' run/activity cells, Applications' rows) was
  migrated — the line-height change is invisible in a centred fixed row. Text whose
  explicit `lineHeight` of **19 px or more** is doing the alignment (the résumé
  prose rows, the cover-letter section heads, Settings' 26 px section sub-line)
  stayed inline.
- **`rel="noopener noreferrer"`.** `Link` emits only `rel="noreferrer"` for
  `target="_blank"`, so the three anchors that spell out `noopener noreferrer`
  (Settings' colophon ×2, Companies' test-row ↗) are keeps. A `rel` passthrough on
  `Link` would retire them.
- **`Helper` takes no `onClick`.** Two muted sub-lines that are themselves click
  targets (`Applications.jsx:620`'s interview slot) stayed inline for that reason.
- **Spinner ring weights.** Nine of the eleven rings were the canonical 1.5 px;
  the Feed's two absolute-positioned score rings were **1 px** and **2 px** and both
  become 1.5 px (listed under JobFeed) — the only spinner drift in the pass.

## ui.jsx — the one addition

| site | change | why |
|---|---|---|
| `Label` | gains a **`title`** prop (forwarded to both the `<label>` and the `<span>` branch) | `Helper`, `Heading` and `Link` already take one, and two labels are `cursor:'help'` affordances whose tooltip is the point (`Searches`' auto-score depth chip, `Persona`'s autofill field labels). **Zero-pixel** |

No other primitive changed and no new variant was added: every migration lands on a
canonical signature or on an existing named size (`Label size="lg"`,
`Helper size="xs"` / `mono`, `Heading size={19}`, `Spinner size={n}` / `color=`).

---

## Persona.jsx

| site | element | before → after |
|---|---|---|
| Persona.jsx:4 | import | `{ Card, Input, Pill, SectionHead, Select }` → `+ Helper, Label, PageTitle` — **zero-pixel** |
| Persona.jsx:111-112 | `FIELD_LABEL` shared const | `{fontSize 9.5, lh 14px, ls .12em, uppercase, --muted, nowrap/ellipsis}` → layout-only `{nowrap/ellipsis}`; type now from `Label` — **9.5 → 10px**, lh **14 → 15px**, ls **.12em → .13em**, ink `--muted` → `--label-ink` (= `--muted`, zero-pixel) |
| Persona.jsx:143 | autofill field label | `<span style={FIELD_LABEL} title={label}>` → `<Label style={FIELD_LABEL} title={label}>` — the const's drift above; each field block grows 1px, `title` kept |
| Persona.jsx:162 | ColumnHead "what is this?" | `--muted 11/14px`, `fontFamily var(--sans)` (= ambient, redundant), `cursor:help` + dotted underline → `Helper` — **11 → 11.5px**, lh **14 → 16px**; the flex item's box grows 2px so the dotted underline drops ~1px; `title={help}` kept |
| Persona.jsx:311 | page title | `<h1>` serif 30/400/lh 1/-.02em/margin 0 → `PageTitle` — **zero-pixel** |
| Persona.jsx:359 | group "n of m set" / "complete" | `10.5`, inherited lh 15.75, `color: done ? var(--accent) : var(--muted)` → `Helper size="xs"` with the tint kept in `style` — lh **15.75 → 16px**, size zero-pixel |
| Persona.jsx:381 | Q&A bank sub-line | `--muted 11`, inherited lh 16.5, nowrap/ellipsis clamp → `Helper` — **11 → 11.5px**, lh **16.5 → 16px**, clamp kept |
| Persona.jsx:382 | Q&A answer count | `--muted 10.5`, inherited lh 15.75 → `Helper size="xs"` — lh **15.75 → 16px**, size zero-pixel |
| Persona.jsx:406 | Q&A empty note | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px**, size/ink zero-pixel |

### kept inline
- `Persona.jsx:161` — serif 18 / **fontWeight 500** / -.015em ColumnHead title: the card/column-title serif family, not the 400-weight 18/19/22 `Heading` scale (orchestrator decision).
- `Persona.jsx:318` — header sub-line `--muted 13/20px`: 13 is 1.5px past `Helper`'s 11.5, and the explicit 20px line-height is the integer-line-height fix documented in the comment directly above it.
- `Persona.jsx:324` — "Saved ✓" `--accent 11.5/17px`: an inert status indicator, not a link (no `href`/`onClick`) and not a muted helper; `Link` would add `cursor:pointer` + `v2-hover-accent-text` to non-interactive text.
- `Persona.jsx:294` (empty/error state) container — `fontSize 13` on a flex *container* that only sets the inherited size for its children; not a text-run site. No comment added (not a candidate site in the scan).

## Stats.jsx

| site | element | before → after |
|---|---|---|
| Stats.jsx:6 | import | `{ Card, Menu, MenuItem, Pill as UiPill }` → `+ Helper, Label, PageTitle, Spinner` — **zero-pixel** |
| Stats.jsx:94 (was) | `NOTE` shared const | `{fontSize 11, lh 16px, --muted}` — const **deleted**; its 8 call sites became `Helper` (11 → **11.5px**, lh 16 → 16px = unchanged, ink `--muted` → `--helper-ink` = `--muted`) |
| Stats.jsx:110 | `LoadMore` busy ring | `v2-spin` span, `1.5px solid currentColor`, r99, 9×9 → `Spinner size={9} color="currentColor"` — **zero-pixel** (adds `flex:'0 0 auto'` + `display:inline-block`, both inert inside the Pill's flex box); the stale `ui: keep` comment removed. `LoadMore` itself **kept** (busy state; `ShowMore` has none) |
| Stats.jsx:394 | page title | `<h1>` serif 30/400/lh 1/-.02em/margin 0 → `PageTitle` — **zero-pixel** |
| Stats.jsx:413 | Refresh ring | `v2-spin` span, `1.5px solid var(--accent)`, r99, 10×10 → `Spinner size={10}` (`--spinner-ink` = `--accent`) — **zero-pixel** |
| Stats.jsx:442 | KPI tile label | `--muted 10/14px, ls .13em, uppercase, nowrap` → `Label style={{whiteSpace:'nowrap'}}` — lh **14 → 15px** (each KPI tile, and so the strip, grows 1px); size/ls/ink zero-pixel |
| Stats.jsx:513 | score-distribution sub-line | `NOTE` (`--muted 11/16px`) → `Helper` — **11 → 11.5px**, lh unchanged |
| Stats.jsx:539 | timeline sub-line | `NOTE` → `Helper` — **11 → 11.5px**, lh unchanged |
| Stats.jsx:555 | "how priced?" | `--muted 11/14px`, `fontFamily var(--sans)` (= ambient, redundant), `cursor:help` + dotted underline → `Helper` — **11 → 11.5px**, lh **14 → 16px**; the flex item's box grows 2px so the dotted underline drops ~1px; `title` kept |
| Stats.jsx:568 | LLM-cost figure labels | `--muted 10/14px, ls .12em, uppercase` → `Label` — lh **14 → 15px**, ls **.12em → .13em**; the figure row grows 1px inside the fixed 300px card (absorbed by the table's `flex:1 minHeight:0`) |
| Stats.jsx:592 | "No LLM calls in this window." | `<div>` `NOTE` + `padding 14px 0` → `Helper style={{padding:'14px 0'}}` (parent is a flex column, so span ≡ div) — **11 → 11.5px** |
| Stats.jsx:602 | Schedules sub-line | `NOTE` → `Helper` — **11 → 11.5px**, lh unchanged |
| Stats.jsx:625 | scheduler "running" ring | `v2-spin` span, `1.5px solid var(--accent)`, r99, 9×9, `flex:'0 0 auto'` → `Spinner size={9}` — **zero-pixel** |
| Stats.jsx:637 | "Run now" pill ring | `v2-spin` span, `1.5px solid currentColor`, r99, 9×9 → `Spinner size={9} color="currentColor"` — **zero-pixel**; the stale `ui: keep` comment removed |
| Stats.jsx:640 | no-trigger em-dash cell | `NOTE` → `Helper` — **11 → 11.5px**, lh unchanged |
| Stats.jsx:654 | run/activity tab sub-line | `NOTE` → `Helper` — **11 → 11.5px**, lh unchanged |
| Stats.jsx:699 | run-history "Trigger" cell | `--muted 10.5`, lh inherited 18px from the 34px row → `Helper size="xs"` — lh **18 → 16px**; the row is fixed-height + `alignItems:center`, so a single centred line does not move. Size/ink zero-pixel |
| Stats.jsx:708 | "No runs yet." | `<div>` `NOTE` + `padding 16px 20px` → `Helper style={{padding:'16px 20px'}}` (flex-column parent) — **11 → 11.5px** |
| Stats.jsx:724 | activity "Company" cell | `--muted 11`, lh inherited 18px, nowrap/ellipsis clamp → `Helper` — **11 → 11.5px**, lh **18 → 16px** (centred in the fixed 34px row, no move), clamp kept |
| Stats.jsx:728 | activity empty note | `<div>` `NOTE` + `padding 16px 20px` → `Helper style={{padding:'16px 20px'}}` — **11 → 11.5px** |

### kept inline
- `Stats.jsx:95` — `const H` serif 17 / **fontWeight 500** / -.015em (all 5 card-title + tab sites): the 500-weight card-title family, and 17 is off the 18/19/22 `Heading` scale (orchestrator decision).
- `Stats.jsx:98` — `const COL` (9.5 uppercase .11em muted): every `...COL` site is a table head (fixed height + `borderBottom`) → the `TableHead` role, D4f.
- `Stats.jsx:100` — `const MONO`: the mono-text role, excluded from D4e.
- `Stats.jsx:102` `const BADGE` / local `Pill` — the `Tag` role, D4d.
- `Stats.jsx:400` — header sub-line `--muted 13/20px`: 13 is 1.5px past `Helper`'s 11.5 and the explicit 20px line-height pins the header column to integer line-heights.
- `Stats.jsx:411` — **"Refresh"** (`v2-hover-accent-text v2-ctl`, 12.5, `--muted`, `cursor:pointer`, icon+label flex row). **needs-decision**: it is filed under the `link` role but does not fit `Link` — ink is `--muted` (`Link` forces `--link-ink` = accent at rest), and `v2-ctl`'s `line-height:1` is what baselines it in the `alignItems:flex-end` header, which `Link`'s inline `lineHeight:'17px'` would override (the control would grow 12.5 → 17px and jump ~4px). Hover class is already `v2-hover-accent-text` at HEAD, so there is **no** `v2-hover-accent` → `v2-hover-accent-text` change to make here.
- `Stats.jsx:426` — **"Try again"** inside the error band: §3's "a link inside a running body-text paragraph" — it inherits the band's 12.5/18px and its `--bad` ink through `currentColor` (the dotted underline is `currentColor` too). `Link` would set 11.5/500 accent, breaking the sentence and painting a green word in a red band. Hover class is already `v2-hover-accent-text` at HEAD.
- `Stats.jsx:445` — KPI numeral serif **27**/30px/400: 3px off `PageTitle`'s 30 and above `Heading`'s 22 (orchestrator decision) — **flagged**: this is the only serif-400 site in v2 at 27 and would be the natural fifth step if the scale ever grows.
- `Stats.jsx:491` — funnel "snapshot" `--muted 9.5/18px`: 9.5 is an explicit §3 keep, and the 18px line-height baselines it against the 22px funnel bar.
- `Stats.jsx:498` — funnel caveat `--muted 11/**15px**` (2 stacked lines): the 15px line-height is what fits both lines inside the card's fixed 230px height; `Helper`'s 16px would add 2px and overflow.
- `Stats.jsx:527` — score-bucket range label `--muted 10/14px`: an axis tick label under a bar (charts excluded).
- `Stats.jsx:524` — bucket count above the bar (`MONO` + `lineHeight:'14px'`): chart value label.
- `Stats.jsx:570` — serif **23**/28px LLM figure: not one of `Heading`'s 18/19/22 steps.
- `Stats.jsx:679` — the 10px `⌕` glyph in the search field wrap: an icon, not helper text; `Helper size="xs"` would take it to 10.5/16 inside a 26px control.
- `Stats.jsx:388`, `:470`, `:549`, `:605` and the chart legend `:544` — `fontSize 12`/`13` "Unavailable — the request failed" / "Loading…" boxes and the chart legend (`--text-2 11`): flex *centering containers* (or `--text-2`, not `--helper-ink`), not muted text runs; not listed as candidate sites by the scan. No comment added.
- All Recharts props (`axis`, `Tooltip contentStyle/labelStyle`, `SankeyNode` `<text fontSize={11}>`) untouched.

## Settings.jsx

| site | element | before → after |
|---|---|---|
| Settings.jsx:100 | TextBox secret show/hide toggle | accent `10.5`/lh `16px`, hand-written `kb()` (role=button) → `Link` — size **10.5 → 11.5**, lh **16 → 17px**, weight **— → 500**, role **button → link**, ink unchanged (`--accent` = `--link-ink`), hover class `— → v2-hover-accent-text` |
| Settings.jsx:113 | Toggle's On/Off caption | `--muted 11`/lh `16px` → `Helper` — size **11 → 11.5**, lh unchanged (16px) |
| Settings.jsx:460 | load-failure detail line | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Settings.jsx:461 | "Try again" retry link | accent `11.5`/`500`, inherited lh 17.25 → `Link` — lh **17.25 → 17px**; gains `tabIndex`/`role="link"`/Enter-Space + `v2-hover-accent-text` |
| Settings.jsx:464 | "Loading settings…" row | `--muted 11.5` flex row, inherited lh 17.25 → `Helper` (layout kept in `style`) — lh **17.25 → 16px** |
| Settings.jsx:465 | loading spinner ring | `v2-spin` 10px `1.5px solid var(--muted)` r99 → `Spinner size={10} color="var(--muted)"` — **zero-pixel** (`--radius-control` = 99px); gains `aria-hidden`, `flex:0 0 auto` |
| Settings.jsx:484 | page title | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** |
| Settings.jsx:505 | anchor-rail group caption | uppercase `--muted 10`, `.15em`, inherited lh 15 → `Label` — letter-spacing **.15em → .13em**, lh unchanged (15px), size unchanged |
| Settings.jsx:544 | colophon row | `--muted 11`/lh `16px` container → `Helper` (flex/gap/padding kept in `style`) — size **11 → 11.5** for the row and its inherited children (the italic "v.2.0" run and the two links); lh unchanged (16px) |
| Settings.jsx:633 | `edit` row value preview | mono `--muted 10.5`/`16px` → `Helper size="xs" mono` — **zero-pixel** |
| Settings.jsx:641 | `models` row count preview | mono `--muted 10.5`/`16px` → `Helper size="xs" mono` — **zero-pixel** |
| Settings.jsx:657 | `button` row boxed preview | mono `--muted 11.5`/`16px` → `Helper mono` — **zero-pixel** |
| Settings.jsx:659 | `button` row bare preview | mono `--muted 10.5`/`16px` → `Helper size="xs" mono` — **zero-pixel** |
| Settings.jsx:667 | `readonly` "Not set" | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Settings.jsx:680 | session-expiry sub-line | `11.5`, ink `expired ? --warn : --muted`, inherited lh 17.25 → `Helper` (tint kept in `style`) — lh **17.25 → 16px** |
| Settings.jsx:722 | settings-row help sub-line | `--muted 11`/lh `16px`, `textWrap:'pretty'` → `Helper` — size **11 → 11.5**, lh unchanged (16px) |
| Settings.jsx:738 | ActionBtn running spinner | `v2-spin` 9px `1.5px solid var(--accent)` r99 → `Spinner` (defaults) — **zero-pixel**; gains `aria-hidden`, `flex:0 0 auto` |
| Settings.jsx:758 | API-key show/hide toggle | accent `10.5`/lh `16px`, hand-written `kb()` (role=button) → `Link` — size **10.5 → 11.5**, lh **16 → 17px**, weight **— → 500**, role **button → link**, hover class `— → v2-hover-accent-text` |
| Settings.jsx:800 | LinkedIn session status line | `11.5`, ink `tone` (`--good`/`--warn`/`--muted`), inherited lh 17.25 → `Helper` (tint kept in `style`) — lh **17.25 → 16px** |
| Settings.jsx:888 | EditModal title | serif `18`/-.02em, no weight, inherited lh 27 → `Heading` (size 18) — **zero-pixel** |
| Settings.jsx:889 | EditModal sub-title | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Settings.jsx:898 | EditModal footer status | `11.5`, ink `err ? --bad : --muted`, inherited lh 17.25 → `Helper` (tint kept in `style`) — lh **17.25 → 16px** |
| Settings.jsx:988 | ModelsModal title | serif `18`/-.02em, no weight, inherited lh 27 → `Heading` (size 18) — **zero-pixel** |
| Settings.jsx:989 | ModelsModal sub-title | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Settings.jsx:1027 | typeahead "N of M match" footer | `--muted 10.5`/`16px` (border/padding kept in `style`) → `Helper size="xs"` — **zero-pixel** |
| Settings.jsx:1040 | catalog row provider cell | mono `--muted 10`/`16px` → `Helper size="xs" mono` — size **10 → 10.5**, lh unchanged (16px) |
| Settings.jsx:1043 | catalog row seeded/custom note | `10`/`16px`, ink `m.custom ? --accent : --muted` → `Helper size="xs"` (tint kept in `style`) — size **10 → 10.5**, lh unchanged (16px) |

**27 sites migrated.**
Helper line-height moves: **8** sites went from an inherited **17.25px → 16px**
(:460, :464, :667, :680, :800, :889, :898, :989). **0** sites moved 16.5 → 16 and
**0** moved 15.75 → 16 — every 11px and 10.5px helper on this screen already
carried an explicit `lineHeight:'16px'`. (One link, :461, moved 17.25 → 17px.)

### kept inline
- `Settings.jsx:494` — the settings-search `⌕` glyph (`--muted 11`): an icon adornment inside the h32 field, not a helper sub-line; `Helper`'s 11.5 would grow the glyph.
- `Settings.jsx:508` — the anchor-rail jump row: a **nav row** (h29, `0 26px 0 29px` pad, selected state = `--text` + weight 600 + 3px accent border-left, `v2-anchor`), not an inline link. Orchestrator-decided keep.
- `Settings.jsx:527` — section title serif **19/500/-.015em**: the second (card-title) serif family; `Heading` is 400/-.02em. Orchestrator-decided keep.
- `Settings.jsx:530` — section sub-line `--muted 11.5` with an explicit **lineHeight 26px**: the 26px is the alignment (the comment above it says integer line-heights keep every row below the header off a half pixel); `Helper`'s 16px would move the row.
- `Settings.jsx:547` — colophon wordmark, serif **12**: below the 18/19 `Heading` scale.
- `Settings.jsx:553` / `:555` — the two colophon links (`API docs ↗`, `github.com/… ↗`). Three reasons: they are links inside a running colophon line that deliberately inherit the row's size (§3 "link inside a running body-text paragraph"); their ink is `--muted` by an explicit contrast decision (SET-13 comment right above), while `Link` forces `--link-ink` (`--accent`) at weight 500; and they carry `rel="noopener noreferrer"`, which `Link` cannot express (it only emits `rel="noreferrer"` for `target="_blank"`). *(This is the site the scan filed under `section-head` by hover class.)*
- `Settings.jsx:608` — "inherits Primary" chip: uppercase 9.5 on a `--surface-2` r99 background = the `Tag` role (D4d), not a `Label`.
- `Settings.jsx:679` — the six-bullet masked value: mono at `--text-2` = the `mono-text` role, not helper ink.
- `Settings.jsx:713` — the 15×15 italic-serif "i" info glyph button (pre-existing keep). Orchestrator-decided keep.
- `Settings.jsx:1023` — typeahead suggestion id: mono at `--text`/`--text-2`, keyboard-highlighted with its row = `mono-text`; the row itself is a documented D4d keep.
- `Settings.jsx:1042` — catalog model id: mono at `--text` = `mono-text`.

### notes / uncertainties
- `Settings.jsx:1024` (`↵ to add`, accent 10/16px inside the highlighted typeahead row) and `Settings.jsx:726` (the expanded `info` panel, `--text-2` 11/17px on a `--surface-2` r7 card) are **not** helper-ink sites, are not in the candidate list, and were left untouched without a keep comment.
- `Settings.jsx:1027` keeps `borderTop: '1px solid var(--line-soft)'` inside the primitive's `style` — it is pre-existing chrome on that footer row, not a new inline colour, but it is the one migrated site whose `style` carries something other than pure layout + a palette tint.
- `Settings.jsx:465` (the 10px loading ring) was previously marked `ui: keep — Spinner role …` by D4d; since `Spinner` is D4e's primitive and it takes a `color`, the keep was retired and the site migrated. Flagging in case D4d meant it to stay.
- The two show/hide toggles (:100, :758) change their announced role from `button` to `link` because `Link` supplies `kb(fn, 'link')`. Behaviour (Enter/Space, aria-label, handler) is identical.

## Resumes.jsx

| site | element | before → after |
|---|---|---|
| Resumes.jsx:8 | import | added `Heading, Helper, Label, Link, NavLink, PageTitle, ShowMore, Spinner` to the existing `./ui` import — **no code change** |
| Resumes.jsx:24-26 | local `ShowMore` pager (deleted) | `<div flex/center pad '10px 20px 12px'><Pill size="sm">Show {n} more</Pill></div>` → ui's `ShowMore`. Control geometry identical (h26 · pad 0 13 · 11.5 · `--pill-ink` · 1px `--pill-border` · r99 · row pad `10px 20px 12px`). **Two changes:** background `--pill-bg` (= `--surface`) → **none** (transparent), and hover class `v2-bd` (border → `--pill-border-hover`) → **`v2-bdc`** (border **and** text → `--pill-ink-hover`). Also loses `aria-pressed=undefined`/`v2-ctl`-on-a-div wrapper; keyboard (`kb`) preserved by ui's `act()` |
| Resumes.jsx:52 | `CHIP_LABEL` const | type keys (`fontSize:10`, `.13em`, `uppercase`, `--muted`) removed — now `Label`'s; const keeps only the layout half (`flex:'0 0 auto'`, `marginRight:3`) |
| Resumes.jsx:146 | page title "Résumés" | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** |
| Resumes.jsx:169 | search "‹ Back" | accent 12, `cursor:pointer`, `v2-navlink`, inherited lh 18 → `NavLink` — **zero-pixel**; gains `tabIndex=0` + `role="link"` + Enter/Space (behaviour add, per §1). No `pad` — the padding lives on the parent row |
| Resumes.jsx:170 | "N matches — bases, copies, and archived" | `--muted 11 / .13em / uppercase`, inherited lh 16.5 → `Label size="lg"` — lh **16.5 → 16px** (size, ls, ink unchanged) |
| Resumes.jsx:178 | search-row note ("N copies") | `--muted 11`, inherited lh 20 (from the Card's `lineHeight:'20px'`) → `Helper` — **11 → 11.5px**, lh **20 → 16px**. Row height unchanged: the 13px title beside it still carries lh 20 |
| Resumes.jsx:183 / :200 | the two pager call sites | unchanged JSX (`n` + `onClick`) — now resolve to ui's `ShowMore` |
| Resumes.jsx:188 | archived "‹ Back" | as :169 — **zero-pixel** + keyboard |
| Resumes.jsx:189 | "Archived · N from rejected or stale applications" | as :170 — lh **16.5 → 16px** |
| Resumes.jsx:197 | archived-row reason (`c.why`) | `--muted 11`, inherited lh 20 → `Helper` — **11 → 11.5px**, lh **20 → 16px** |
| Resumes.jsx:208 | "Profile" section label | `--muted 10 / .15em / uppercase`, pad `4px 2px 0`, inherited lh 15 → `Label` (pad kept in `style`) — letter-spacing **.15em → .13em**; size + lh unchanged |
| Resumes.jsx:213 | Persona sub-line | `--muted 11.5`, inherited lh 28 (the baseline row's `lineHeight:'28px'`) → `Helper` — lh **28 → 16px**. Row is `align-items:baseline`, so the glyphs stay on the same baseline; the row's descent contribution drops (~1px shorter box) |
| Resumes.jsx:224 | "Recent copies" chip label | `style={CHIP_LABEL}` (`--muted 10 / .13em / uppercase`), inherited lh 15 → `Label style={CHIP_LABEL}` — **zero-pixel** |
| Resumes.jsx:227 | Persona tailoring spinner | `span.v2-spin` 9×9, `1.5px solid var(--accent)`, `borderTopColor:transparent`, `r99`, `flex:'0 0 auto'` → `Spinner` — **zero-pixel** (`--spinner-ink` = `--accent`, `--radius-control` = 99px); adds `display:inline-block` + `aria-hidden="true"` |
| Resumes.jsx:240 | "+ N more ›" / "show fewer ‹" | accent 11.5, weight 400, `cursor:pointer`, inherited lh 17.25 → `Link` — **weight 400 → 500**, lh **17.25 → 17px**; gains `v2-hover-accent-text` (hover ink `--link-ink-hover` = `--accent`, i.e. no visible hover change) + keyboard. `e.stopPropagation()` handler kept verbatim |
| Resumes.jsx:247 | "Résumés" section label | as :208 — letter-spacing **.15em → .13em** |
| Resumes.jsx:258 | base-card sub-line | as :213 — lh **28 → 16px** |
| Resumes.jsx:269 | "Recent copies" chip label | as :224 — **zero-pixel** |
| Resumes.jsx:272 | base tailoring spinner | as :227 — **zero-pixel** |
| Resumes.jsx:287 | "+ N more ›" / "show fewer ‹" | as :240 — weight **400 → 500**, lh **17.25 → 17px** |
| Resumes.jsx:352 | AddModal heading "New base résumé" | `<div>` serif 19, no weight (inherits 400), -.02em, `marginBottom:4`, inherited lh 28.5 → `Heading size={19}` with `style={{display:'block', marginBottom:4}}` (parent is the modal panel, not a flex box) — lh **28.5 → 26px** |

### kept inline
- `Resumes.jsx:175` / `:194` — uppercase 9.5/.08em kind badge with `background` + `borderRadius:99` + `padding`: the **Tag** role (D4d), not `Label`.
- `Resumes.jsx:179` / `:233` / `:280` — mono numerals in `scoreColor(...)`: the **mono-text** role the step excludes, and the ink is not `--helper-ink`.
- `Resumes.jsx:211` / `:256` — serif **19/500**/-.015em card titles: the second serif family (card titles at 500-600), which `Heading` (no `fontWeight`, inherits 400) deliberately does not cover.
- `Resumes.jsx:215` / `:260` — serif **17** score numerals (`scoreColor`, `marginLeft:auto`): a data display, out of the 18/19/22 heading scale. Their nested ` avg fit` unit (sans **10**, `--muted`) is kept with them: it resets `fontFamily` back to sans inside a serif parent, and `Helper` exposes only `mono` — passing `fontFamily` through `style` is forbidden by §1.
- `Resumes.jsx:151` — the header count line, `--muted` **13**/lh 20: outside the helper scale (11.5 / 10.5) and not in the scan's helper bucket. No comment added (never a candidate).
- `Resumes.jsx:293` / `:298` (Archived band) — `--muted` **12** and accent **11.5** with no `cursor`/`onClick` of its own (the whole `Band` is the control). Not in the scan's helper/link buckets; migrating the accent half would add `cursor:pointer` + weight 500. Left untouched.
- `Resumes.jsx:369` — modal "Cancel", `--muted` 12 with `cursor:pointer`: ink is `--muted`, not `--link-ink`; not a link site.

## CoverLetters.jsx

| site | element | before → after |
|---|---|---|
| CoverLetters.jsx:5 | import | added `Helper, Label, Link, PageTitle, Spinner` to the existing `./ui` import — **no code change** |
| CoverLetters.jsx:17 (deleted) | `LABEL` const | `{fontSize:9.5, lineHeight:'14px', .13em, uppercase, --muted}` deleted; its 4 call sites now render `Label` |
| CoverLetters.jsx:77 | `Picker` option `sub` line | `--muted 11`, inherited lh 16.5 → `Helper` with `display:'block'` (parent menu row is a block, and the ellipsis clamp needs a block box) — **11 → 11.5px**, lh **16.5 → 16px**; `whiteSpace/overflow/textOverflow` clamp kept |
| CoverLetters.jsx:88 | `VoicePicker` "No voice presets…" (CL-13) | `--muted 11.5/16px` → `Helper` — **zero-pixel** |
| CoverLetters.jsx:313 | letter-row sub-line | `--muted 11.5/16px` + ellipsis clamp → `Helper` (clamp in `style`) — **zero-pixel** |
| CoverLetters.jsx:319 | letter-row `agoShort` stamp | `--muted`, `var(--mono)` **10.5/16px**, `flex:'0 0 40px'`, `textAlign:'right'` → `Helper size="xs" mono` (layout in `style`) — **zero-pixel** (`--font-mono` = `var(--mono)`, `--helper-ink` = `--muted`) |
| CoverLetters.jsx:329 | page title "Cover Letters" | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** |
| CoverLetters.jsx:345 | "Your résumé" field label | `--muted **9.5**/**14px**/.13em/uppercase` → `Label` — **9.5 → 10px**, lh **14 → 15px** |
| CoverLetters.jsx:347 | "Base for achievements and motivation" | `--muted 10.5/16px`, `textWrap:'pretty'` → `Helper size="xs"` (textWrap kept in `style`) — **zero-pixel** |
| CoverLetters.jsx:351 | "Target job" label | as :345 — **9.5 → 10px**, lh **14 → 15px** |
| CoverLetters.jsx:356 | "Voice" label | as :345 — **9.5 → 10px**, lh **14 → 15px** |
| CoverLetters.jsx:361 | "Length" label | as :345 — **9.5 → 10px**, lh **14 → 15px** |
| CoverLetters.jsx:369 | Generate-button spinner | `span.v2-spin` 10×10, `1.5px solid currentColor`, `borderTopColor:transparent`, `r99` → `Spinner size={10} color="currentColor"` — **zero-pixel** on the ring (`--radius-control` = 99px); gains `flex:'0 0 auto'` + `display:'inline-block'` + `aria-hidden="true"` (the ring can no longer be shrunk by the button's flex row) |
| CoverLetters.jsx:378 | "All letters" gutter label | `--muted 10/**16px**/**.14em**/uppercase` → `Label` — lh **16 → 15px**, letter-spacing **.14em → .13em**. Row height unchanged: the mono count beside it keeps its explicit 16px |
| CoverLetters.jsx:386 | pending-row spinner | `span.v2-spin` 11×11, `1.5px solid var(--accent)`, r99 → `Spinner size={11}` — **zero-pixel** (`--spinner-ink` = `--accent`); gains `flex:'0 0 auto'` + `display:'inline-block'` + `aria-hidden` |
| CoverLetters.jsx:393 | pending-row "~30s" | `--muted 11`, inherited lh 16.5 → `Helper` (`marginLeft:'auto'`, `flex` kept) — **11 → 11.5px**, lh **16.5 → 16px**. Row height unchanged (the 12.5/20px label beside it still sets it) |
| CoverLetters.jsx:415 | load-error detail (`loadErr`) | `--muted 11.5`, inherited lh 17.25, `textAlign:'center'` → `Helper` — lh **17.25 → 16px** |
| CoverLetters.jsx:416 | "Try again" | accent **11.5/500**, `cursor:pointer`, `paddingTop:2`, inherited lh 17.25 → `Link` — lh **17.25 → 17px** (size + weight + ink identical); gains `v2-hover-accent-text` (hover ink `--link-ink-hover` = `--accent`, no visible hover change) + `tabIndex=0`/`role="link"`/Enter-Space |

### kept inline
- `CoverLetters.jsx:58` — the `Picker` chevron `▾`, `--muted` **9**: below the helper scale (§3 "helper at 9 or 9.5"), and a glyph rather than a sub-line.
- `CoverLetters.jsx:311` — serif **15.5/500**/-.01em row title: the 500-weight card-title family, not the 18/19/22 `Heading` scale.
- `CoverLetters.jsx:341` — serif **16/600**/-.01em "Generate new": the 600-weight card-title family; 16 is also outside the heading scale.
- `CoverLetters.jsx:379` — mono **10.5/16** count in `--edge` ink: the **mono-text** role, and the ink is not `--helper-ink`.
- `CoverLetters.jsx:107-112` `LengthPicker` and `CoverLetters.jsx:27-31 / :69-70` `Picker` — pre-existing documented D4c/D4d keeps; only the two-line option's `sub` (:77) and the four field labels moved, the structures are untouched.
- `CoverLetters.jsx:319+1` (`›` chevron, `--edge` 11), `:329+1` (header count line, `--muted` 13/20), `:400` (Archived band text, `--muted` 12), `:403` (`browse ›`, accent 11.5, no own `cursor`/`onClick`), `:373` (`err`, **11.5 `--bad`**), `:388` (accent 12.5/20 with a load-bearing integer-line-height comment), `:414` / `:419` (13 `--bad` / 12.5 `--muted` empty states) — none are helper/label/link sites by ink or size; not in the scan's buckets, left untouched with no comment.

Line numbers are **after** the change. 29 sites migrated.

## Searches.jsx

| site | element | before → after |
|---|---|---|
| Searches.jsx:562 | page title "Searches" | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** |
| Searches.jsx:182 | `Cell` field label (was the shared `MICRO` const) | `--muted 9.5/14px/.13em uppercase` → `Label` — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:280 | "Sources" chip-row label (`MICRO`) | same as above, `marginRight:3` kept in `style` — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:286 | "Collections" chip-row label (`MICRO`) | same — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:301 | "Auto-scoring" label (`MICRO`) | same — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:307 | "Run interval · min" label (`MICRO`) | same — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:315 | "Import rules" label (`MICRO`) | same — size **9.5 → 10**, lh **14 → 15px** |
| Searches.jsx:637 | auto-score depth chip (`cursor:'help'` + `title`) | `--muted 10 uppercase .08em`, inherited lh 15 → `Label title=…` — letter-spacing **.08em → .13em** only (size 10, lh 15px, ink both unchanged); the inner `dep?.dots` span keeps its own `letterSpacing:2 / fontSize:9` |
| Searches.jsx:188 | `Cell` sub-line (shared `HELP` const) | `--muted 10.5/16px` → `Helper size="xs"`, `textWrap:'pretty'` kept in `style` — **zero-pixel** |
| Searches.jsx:303 | "How deeply new results are scored…" (`HELP`) | `--muted 10.5/16px` → `Helper size="xs"` — **zero-pixel** |
| Searches.jsx:311 | "0 follows the global schedule…" (`HELP`) | `--muted 10.5/16px` → `Helper size="xs"` — **zero-pixel** |
| Searches.jsx:288 | "Credentials live in Settings › Accounts" | `--muted 11`, inherited lh 16.5 → `Helper` — size **11 → 11.5**, lh **16.5 → 16px** |
| Searches.jsx:580 | new-search card sub-line | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Searches.jsx:585 | "Runs on the next scheduled sweep once created" | `--muted 11`, inherited lh 16.5 → `Helper` — size **11 → 11.5**, lh **16.5 → 16px** |
| Searches.jsx:692 | "Changes apply from the next run" | `--muted 11`, inherited lh 16.5 → `Helper` — size **11 → 11.5**, lh **16.5 → 16px** |
| Searches.jsx:706 | loading row wrapper ("Loading searches…") | `<div>` `--muted 11.5`, inherited lh 17.25 → `Helper` carrying the flex/gap/padding in `style` — lh **17.25 → 16px** |
| Searches.jsx:713 | load-error detail `{loadErr}` | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Searches.jsx:720 | empty-state sub-line | `--muted 11.5`, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| Searches.jsx:788 | "dry run · nothing saved" (test modal head) | `--muted 11.5`, inherited lh 17.25 → `Helper`, `flex:'0 0 auto'` kept in `style` — lh **17.25 → 16px** |
| Searches.jsx:837 | test-row Source cell | `--muted` mono 10, inherited lh 15 → `Helper size="xs" mono` — size **10 → 10.5**, lh **15 → 16px** (font `var(--mono)` → `var(--font-mono)`, same value) |
| Searches.jsx:848 | test-row filter reason sub-line | `11/15px`, `ok ? --muted : --bad` → `Helper` keeping the conditional tint in `style` — size **11 → 11.5**, lh **15 → 16px** |
| Searches.jsx:852 | test-row "body check needs the description" | `--muted 11/15px` → `Helper` — size **11 → 11.5**, lh **15 → 16px** |
| Searches.jsx:854 | test-row Location cell | `--muted 11`, inherited lh 16.5 → `Helper` — size **11 → 11.5**, lh **16.5 → 16px** |
| Searches.jsx:787 | test-modal title "Test run — …" | serif 18/-.02em, inherited lh 27, ellipsis clamp → `Heading size={18}` with the clamp in `style` — **zero-pixel** |
| Searches.jsx:714 | "Try again" (load-error) | `--accent 11.5/500`, inherited lh 17.25 → `Link` — lh **17.25 → 17px**; gains `v2-hover-accent-text` (no-op today: `--link-ink-hover` = `--link-ink` = `--accent`) and `kb()` keyboard operability (`tabIndex=0`, `role="link"`, Enter/Space) |
| Searches.jsx:721 | "+ New search" (empty state) | same as above — lh **17.25 → 17px**, + hover class + `kb()` |
| Searches.jsx:659 | Run-pill spinner ring | `v2-spin` 9px `1.5px solid var(--accent)` r99 → `Spinner` — **zero-pixel** (`--spinner-ink` = `--accent`, `--radius-control` = 99px); gains `flex:'0 0 auto'`, `display:'inline-block'`, `aria-hidden` |
| Searches.jsx:667 | Test-pill spinner ring | same → `Spinner` — **zero-pixel** |
| Searches.jsx:707 | loading-row spinner ring | `v2-spin` 10px `1.5px solid var(--muted)` r99 → `Spinner size={10} color="var(--muted)"` — **zero-pixel**; the old `ui: keep` comment above it is removed |

### line-height accounting (helper sites)
- inherited **17.25 → 16px**: **5** sites (580, 706, 713, 720, 788)
- **16.5 → 16px**: **4** sites (288, 585, 692, 854)
- **15.75 → 16px**: **0** sites (both 10.5px helpers came from `HELP`, which already declared `lineHeight:'16px'` → zero-pixel)
- other helper lh moves: 837 (15 → 16), 848 and 852 (explicit 15px → 16px)

### kept inline
- `Searches.jsx:578` — serif 15.5/**500**/-.01em "New search" card title: the second serif family (card/column titles at 500-600), not the 18/19 `Heading` scale. *(orchestrator decision)*
- `Searches.jsx:621` — serif 15.5/**500**/-.01em/lh 23px search-name card title: same family, and the 23px line-height is load-bearing for the card's integer height (see the comment right above it). *(orchestrator decision)*
- `Searches.jsx:628` — "Acknowledge": the scan files it under `section-head` by its `v2-hover-accent-text` class, but it is neither a section head nor `Link`'s signature — it is `--muted` 11 at normal weight, where `Link` is `--accent` 11.5/500. Migrating it would flip a quiet inline action to accent and bold. Its explicit `lineHeight:'17px'` also matches the summary line it sits beside in the same flex row.
- `Searches.jsx:655` / `:662` / `:670` — pre-existing keeps (25px Run/Test/⋯ controls), untouched.
- `Searches.jsx:804` — pre-existing keep (mono source badge on the `sm-`/`cc-` hue taxonomy), untouched.
- `Searches.jsx:822` — table head: `height:28` + `borderBottom` + `background`, and 9.5/.11em is the table-head signature, not `Label`'s 10/.13em. TableHead role, D4f. *(orchestrator decision)*
- `Searches.jsx:860` — pre-existing keep (per-row Kept/Ignored/Out verdict badge, `Tag` role), untouched.
- `Searches.jsx:563` — `{countLine}` header sub-line, `--muted` **13**/20px: size out of `Helper` tolerance (13 vs 11.5). Not scan-flagged; left as is.
- `Searches.jsx:712` / `:719` — empty/error-state headline spans at **13**px (`--bad` / `--text-2`): size out of tolerance. Not scan-flagged.
- `Searches.jsx:855` — mono 9.5 salary cell: `mono-text` role, excluded by the step.

## Companies.jsx

| site | element | before → after |
|---|---|---|
| Companies.jsx:400 | page title | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** |
| Companies.jsx:93 (deleted) | the local `ShowMore` pager, used by the test modal (`:993`) | `<div flex/centre pad '10px 20px 12px'><Pill size="sm">Show n more</Pill></div>` → ui's `ShowMore`. Geometry identical (h26 · pad 0 13 · 11.5 · `--pill-ink` · 1px `--pill-border` · r99). **Two changes:** background `--pill-bg` (=`--surface`) → **transparent**, hover class `v2-bd` → **`v2-bdc`** (border **and** ink turn accent) |
| Companies.jsx:99 (deleted) | the shared `helpTxt` const (8 sites: `:689`, `:702`, `:707`, `:713`, `:732`, `:737`, `:742`, `:747`) | 10.5 `--muted`, inherited lh 15.75 → `Helper size="xs"` — **lh 15.75 → 16px** ×8 |
| Companies.jsx:497 | the row's résumé cell | 11.5, `--text-2`/`--muted`, ellipsis → `Helper` (tint as a conditional spread) — **lh 17.25 → 16px**; the row is a fixed 46px centred flex row, so nothing moves |
| Companies.jsx:501 | the "+N more URLs" cell | 10 `--muted` → `Helper size="xs"` — **10 → 10.5px**, lh 15 → 16px (inside the fixed row) |
| Companies.jsx:502 | the "—" no-ATS cell | 11 `--muted` → `Helper` — **11 → 11.5px**, lh 16.5 → 16px |
| Companies.jsx:505 | the Open · 7d cell | mono 11.5, `--text-2`/`--muted` → `Helper mono` — **lh 17.25 → 16px**; the nested `+N` week span keeps its own `--good`/`--muted` tint |
| Companies.jsx:509 | the Apps cell | mono 11.5, `--text-2`/`--muted` → `Helper mono` — **lh 17.25 → 16px** |
| Companies.jsx:524, :531, :765 | the Run / Test / footer-Test rings | 9px `1.5px var(--accent)` `v2-spin` rings → `Spinner` — **zero-pixel** (`--spinner-ink` = `--accent`) |
| Companies.jsx:550 | the "Loading companies…" row | `<div>` 11.5 `--muted` + flex/centre/pad → `Helper` carrying the layout in `style` — **lh 17.25 → 16px** |
| Companies.jsx:551 | its ring | 10px `1.5px var(--muted)` → `Spinner size={10} color="var(--muted)"` — **zero-pixel**; the stale D4d `ui: keep — Spinner role …` comment is removed |
| Companies.jsx:560, :567 | the load-error detail and the empty-state sub-line | 11.5 `--muted` → `Helper` — **lh 17.25 → 16px** ×2 |
| Companies.jsx:561, :568 | "Try again" / "Clear filters" | `--accent` 11.5/500 → `Link` — **lh 17.25 → 17px**; gains `v2-hover-accent-text` (a no-op today: `--link-ink-hover` = `--link-ink`) and `kb()` keyboard operability |
| Companies.jsx:649 | the drawer subtitle | 11.5 `--muted` → `Helper` — **lh 17.25 → 16px** |
| Companies.jsx:662 | the drawer banner's "last ran …" line | 10.5 `--muted` → `Helper size="xs"` — **lh 15.75 → 16px** |
| Companies.jsx:724 | the "Scraper tuning" note | 10.5, `--muted`/`--bad`/`--warn` → `Helper size="xs"` (tint as a conditional spread) — **lh 15.75 → 16px** |
| Companies.jsx:753 | the H-1B LCA line | 10.5, `--good`/`--muted` → `Helper size="xs"` — **lh 15.75 → 16px** |
| Companies.jsx:768 | the drawer footer's save error | **12**/16px `--bad` → `Helper` with a `--bad` tint — **12 → 11.5px**, lh unchanged |
| Companies.jsx:821 | "Add company" | serif 18 · -.02em, inherited lh 27 → `Heading` — **zero-pixel** |
| Companies.jsx:822, :831, :865, :866, :869 | the add modal's five sub-lines | 11 / 11.5 `--muted` (`:831` also `--warn`) → `Helper` — **11 → 11.5px** at `:831`/`:865`, **lh 17.25/16.5 → 16px** |
| Companies.jsx:826, :835, :839, :845, :849, :854 | the add modal's six field labels | 10 · **.14em** uppercase `--muted` → `Label` — **letter-spacing .14 → .13em** ×6 |
| Companies.jsx:888 | the test-modal error title | `<div>` serif 18, **no letter-spacing**, `marginBottom:10` → `Heading style={{display:'block', marginBottom:10}}` — **gains -.02em** |
| Companies.jsx:933 | the test-modal title | serif 18 · -.02em → `Heading` — **zero-pixel** |
| Companies.jsx:941 | "URLs scraped · N" | 11 `--muted` → `Helper` — **11 → 11.5px**, lh 16.5 → 16px |
| Companies.jsx:942, :955 | the scraped-URL list and each screenshot's URL | mono 10 `--muted` → `Helper size="xs" mono` — **10 → 10.5px**, lh 15 → 16px |

### kept inline
- `Companies.jsx:110`, `:507`, `:834`, `:991` — the ATS / status badges: `Tag` role (D4d); `:834`'s `background`/`color: … : undefined` is the documented deliberate-undefined case.
- `Companies.jsx:467`, `:978` — the list and test-modal **column heads** (height + `borderBottom` + `background`, 9.5/.11em): `TableHead` role, D4f.
- `Companies.jsx:656` — the drawer title: serif **20**; the `Heading` scale is 18/19/22.
- `Companies.jsx:687`, `:704`, `:729` — serif **15/600**/-.01em section titles: the 500-600-weight card-title serif family this step does not touch.
- `Companies.jsx:670` — "Acknowledge": `--muted` 11 at normal weight, deliberately quieter than a `Link` (`--link-ink` 11.5/500). Same call as `Searches.jsx`'s twin.
- `Companies.jsx:964` — "Pagination debug": accent at **weight 600**.
- `Companies.jsx:984`-`:988` — the test-row cells: the mono row numeral and the reason cell's *variable* ink (`st.reasonFg`) are row-cell/mono-text, and the row's `↗` anchor carries `rel="noopener noreferrer"`, which `Link` cannot emit (it only writes `noreferrer`).
- `Companies.jsx:411` — the header count line (`--muted` **13**/20px): the `text` role, and the 20px is the documented integer-line-height pin.

## Applications.jsx

| site | element | before → after |
|---|---|---|
| Applications.jsx:330 | the screen title | `<h1>` serif 30/400/lh 1/-.02em → `PageTitle` — **zero-pixel** (gains the explicit `--heading-ink`, which is `--text`, the colour it already inherited) |
| Applications.jsx:380 | the toolbar's "N of M shown" | `--muted` 11, inherited lh 16.5 → `Helper` — **11 → 11.5px**, **lh 16.5 → 16px**; it is centred in the toolbar's `alignItems:center` row, so neither move is visible |
| Applications.jsx:417 | the stage-band label (Applied / Interview / Offer / Rejected) | `--muted` **10.5** · .13em uppercase, lh 16px inherited from `SectionHead`'s call-site override → `Label` — **10.5 → 10px**, **lh 16 → 15px**; the band keeps its height because the mono count and the ⌄ caret beside it still render at 16px |
| Applications.jsx:438 | the list row's company sub-line | `--muted` (`--edge` when "Unknown Company") 11, lh `normal` (≈13px) inherited from the row's `lineHeight:'normal'` block → `Helper` — **11 → 11.5px**, **lh normal ≈13 → 16px**. The cell is centred in a fixed 46px `Row` (`alignItems:'center'`), so the row does not move; only the gap between the title and the company line opens by ~1.5px |
| Applications.jsx:440 | the list row's "Nd" age cell | `--mono` 10.5, `--warn` when stale else `--muted`, inherited lh 15.75 → `Helper size="xs" mono` — **lh 15.75 → 16px**, invisible (centred in the fixed 46px row). Size, ink, the stale/fresh tint, `flex:'0 0 30px'`, `textAlign:'right'` and the `title` all unchanged |
| Applications.jsx:452 | the load-error detail line | `--muted` 11.5 centred, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px** |
| Applications.jsx:453 | the load-error "Try again" | `--accent` 11.5/500, `cursor:pointer`, inherited lh 17.25 → `Link` — **lh 17.25 → 17px**, **gains `v2-hover-accent-text`** and keyboard operability (`tabIndex=0`, `role="link"`, Enter/Space) it did not have |
| Applications.jsx:502 | the detail head's "#id · Company" line | `--muted` 10 · .13em uppercase, inherited lh 15 → `Label` — **zero-pixel** |
| Applications.jsx:566, :573, :660, :672 | the four section labels that used the shared `LABEL` const (Last email · Gmail detection / Interviews · n / Notes · autosaves / History) | `LABEL` = **9.5** · **.14em** uppercase `--muted` · lh **14px** → `Label`; the const is deleted — **9.5 → 10px**, **letter-spacing .14 → .13em**, **lh 14 → 15px** |
| Applications.jsx:593, :598, :602, :607, :631, :636, :640, :645, :802, :808, :812, :817, :827, :836, :841 | the fifteen field labels that used the shared `FIELD_LABEL` const (interview edit + add forms, Log-application modal) | `FIELD_LABEL` = 10 · **.14em** uppercase `--muted`, inherited lh 15 → `Label`; the const is deleted — **letter-spacing .14 → .13em** only, lh 15 → 15px |
| Applications.jsx:611 | the interview editor's "Escape cancels" | `--muted` 11, inherited lh 16.5 → `Helper` — **11 → 11.5px**, **lh 16.5 → 16px**; centred in an `alignItems:center` button row, so it does not move |
| Applications.jsx:681 | the history rail's relative timestamp | `--mono` `--muted` 10.5/**16px** → `Helper size="xs" mono` — **zero-pixel** |
| Applications.jsx:703 | the prep-modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| Applications.jsx:704 | its "paste into the AI of your choice" sub-line | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**, invisible (centred in the modal head's `alignItems:center` row) |
| Applications.jsx:713 | the prep-modal footer note | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**, invisible (centred footer row) |
| Applications.jsx:797 | the Log-application modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| Applications.jsx:798 | its explainer sub-line | `--muted` 11.5 `textWrap:pretty`, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**; this one wraps to two lines, so the tighter leading is visible and the modal head loses ~2.5px of height |
| Applications.jsx:847 | the Log-modal footer's "The posting is cached on save" | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**, invisible (centred footer row) |

### kept inline
- `Applications.jsx:335` — the header count line: 13/20px `--muted`, 1.5px off the 11.5 helper step, and its integer line-height is what holds the list pane on whole pixels (its own comment says so).
- `Applications.jsx:349` — the search field's `⌕` glyph: 11px `--muted`, but a control glyph on the field's icon scale, not a sub-line (same call as the `▾` carets kept elsewhere).
- `Applications.jsx:384` — the Sort trigger: `--muted` 12.5 + value + `▾`, `v2-hover-accent-text`, `aria`-less disclosure that opens the Sort `Menu`. Not a link — `Link`'s accent 11.5/500 would read as navigation.
- `Applications.jsx:420` — the stage band's row count: `--mono` 10.5 in `--edge` (the dimmer mono-id ink, not `--helper-ink`) — the `mono-text` role the step excludes.
- `Applications.jsx:451` — "Couldn't load your applications": 13px `--bad` error headline, off the helper step.
- `Applications.jsx:507` — the detail title: serif **23**/26px, its own step between `Heading`'s 22 and the 30px page title.
- `Applications.jsx:514` — the "meta · applied with <résumé>" sentence and the résumé link inside it: a running 12.5/18px line; `Link`'s 11.5/500/17px would break the run.
- `Applications.jsx:587` — the interview status chip: uppercase 9.5 with `background` + `borderRadius:99` — the `Tag` role (D4d).
- `Applications.jsx:620` — the interview slot line (`mono` 10.5 `--muted`): the whole line is a click target that opens the interview editor, and **`Helper` takes no `onClick`** (nor `role`/`tabIndex`). Would migrate the moment `Helper` grows one.
- `Applications.jsx:687` — "No history recorded yet.": 12/**18px**, sitting on the history rail's own 12.5/18px event-line rhythm rather than the helper step.

### not candidates (left untouched, no comment added)
- `:588` the interview ✕ (11 `--muted` glyph with `v2-hover-bad`), `:436`/`:510` the ✉ glyphs, `:576`/`:716` the `⧉` glyphs inside a `Pill`/`Button` — icon glyphs, not text roles.
- `:457` "No applications yet…" (12.5 `--muted`) and `:472` "Select an application." (13 `--muted`) — empty-state body copy, off the helper scale and not in the D1 scan's helper set.

## JobFeed.jsx

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:723 | page title "The Feed" | `<h1>` serif 30/400/lh 1/-.02em/margin 0 → `PageTitle` — **zero-pixel** |
| JobFeed.jsx:764 | the Company drop's "Top by open roles …" footnote | `--muted` 10.5/**16px explicit** → `Helper size="xs"` — **zero-pixel** (padding `6px 8px 2px` moved into `style`; it is a flex item of `Menu`, so the div→span swap is neutral) |
| JobFeed.jsx:777 | the Score drop's "or at least" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:781 | "Also hides unscored jobs — …" | `--muted` 10.5, inherited lh 15.75 → `Helper size="xs"` — lh **15.75 → 16px** |
| JobFeed.jsx:788 | the Salary drop's "at least" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:792 | "Also hides jobs without a listed salary" | `--muted` 10.5, inherited lh 15.75 → `Helper size="xs"` — lh **15.75 → 16px** |
| JobFeed.jsx:866 | the F-010 empty state's "No open roles yet" | serif 18, `--text`, **no letter-spacing**, lh **20px** (inherited from the paragraph's `lineHeight:'20px'`), `marginBottom:6` → `Heading` — **gains -.02em**, lh **20 → 27px**; `display:'block'` added because the parent is a plain block `<div>`, `marginBottom:6` kept in `style` |
| JobFeed.jsx:869 | the "no jobs match" → "Clear filters" action | `--accent`, size inherited from the 13/20px block, `v2-anchor` → `Link` — **13 → 11.5px**, **+ weight 500**, lh **20 → 17px** (it sits alone after a `<br/>`, and the paragraph's 20px strut still sets the line box, so nothing reflows), hover ink `--anchor-ink-hover` (`--text`) → `--link-ink-hover` (`--accent`, i.e. no hover colour change), **+ keyboard-operable** |
| JobFeed.jsx:899 | the row score-ring "scoring" spinner | 44px ring (`inset:0`), **`1px` solid `--accent`**, `borderRadius:99`, `v2-spin` → `Spinner size={44}` — border **1 → 1.5px** (`--accent` = `--spinner-ink`, so colour is zero-pixel) |
| JobFeed.jsx:959 | "Loading more…" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:960 | "End of the list · N jobs" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:976 | the detail header eyebrow (company · source · age) | `--muted` 10.5 / **.14em** / lh **16px**, a flex row → `Label` — **10.5 → 10px**, **.14 → .13em**, lh **16 → 15px**; `display:'flex'`, `alignItems`, `gap:7` kept in `style` |
| JobFeed.jsx:988 | the collapsed detail header's one-line summary | `--muted` 11.5 / **17px** + ellipsis clamp → `Helper` — lh **17 → 16px**; `whiteSpace`/`overflow`/`textOverflow` kept |
| JobFeed.jsx:1061 | the report tabs' "+ Rescore" | `--muted` 12, `v2-navlink`, `padding:'7px 0'`, `marginLeft:'auto'`, inherited lh 18 → `NavLink pad="7px 0" style={{ marginLeft:'auto', color:'var(--muted)' }}` — **zero-pixel** (12/18px, same class, same padding; the tab row's height is set by its 12.5px tabs). The `--muted` ink is carried as a `style` override of `--navlink-ink`; the site **gains keyboard operability** (`tabIndex=0`, `role="link"`, Enter/Space) |
| JobFeed.jsx:1072 | report band head "Score breakdown" | `--muted` 10 / **.15em**, lh **18px** inherited from `SectionHead` → `Label` — **.15 → .13em**, lh **18 → 15px**. The head row does not move: `SectionHead`'s own caret glyph still renders at 18px |
| JobFeed.jsx:1099 | report band head "Keyword coverage" | same → `Label` — **.15 → .13em**, lh **18 → 15px**, row height held by the caret |
| JobFeed.jsx:1108 | "N matched · M missing" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:1109 | "Show matched" / "Hide matched" toggle | `--accent` 11.5, **no weight**, inherited lh 17.25 → `Link` — **+ weight 500**, lh **17.25 → 17px**, gains `v2-hover-accent-text` and **keyboard operability** |
| JobFeed.jsx:1125 | report band head "Requirement mapping" | `--muted` 10 / **.15em**, lh **18px** inherited → `Label` — **.15 → .13em**, lh **18 → 15px**, row height held by the caret |
| JobFeed.jsx:1126 | "N of M met" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:1161 | the ATS-tip eyebrow | `--muted` **9.5** / **14px** / .13em → `Label` — **9.5 → 10px**, lh **14 → 15px**; `flex:'0 0 auto'` + `paddingTop:2` kept (its 12.5/18px sibling still sets the Card row height) |
| JobFeed.jsx:1190 | the "scoring in progress" band spinner | 28px ring (`inset:3` in a 34px box), **`2px` solid `--accent`**, `borderRadius:99`, `v2-spin` → `Spinner size={28}` — border **2 → 1.5px** |
| JobFeed.jsx:1226 | "This posting refuses to be framed" | serif 18 / **-.015em**, inherited lh 27px → `Heading` — letter-spacing **-.015 → -.02em**, lh **zero-pixel** (18 × 1.5 = 27px = `Heading`'s 27px) |
| JobFeed.jsx:1255 | the résumé-copy modal eyebrow | `--muted` 10.5 / **.15em**, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1256 | the résumé-copy modal title | serif 19 / -.02em / lh **24px** → `Heading size={19}` — lh **24 → 26px** |
| JobFeed.jsx:1264 | the existing-copy banner's "Open it ↗" | `--accent` / weight 500, size inherited from the banner's 12.5, inherited lh 18.75 → `Link` — **12.5 → 11.5px** (exactly at the 1.0px tolerance), lh **18.75 → 17px**, gains `v2-hover-accent-text` and **keyboard operability**. It is a distinct flex item (not inline in the sentence), and the banner's height is held by its 12.5px sibling, so the row does not move |
| JobFeed.jsx:1270 | modal eyebrow "Method" | `--muted` 10.5 / .15em, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1277 | the method cards' help line | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:1284 | modal eyebrow "Base résumé" | `--muted` 10.5 / .15em, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1293 | the "from /persona" note | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px**; `flex:'0 0 auto'` kept, row height held by its 13.5px sibling |
| JobFeed.jsx:1301 | the picker footer's cost note | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** (footer height is set by the 33px `Button size="sm"`) |
| JobFeed.jsx:1316 | the rescore modal eyebrow | `--muted` 10.5 / .15em, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1317 | the rescore modal title | serif 19 / -.02em / lh **24px** → `Heading size={19}` — lh **24 → 26px** |
| JobFeed.jsx:1324 | modal eyebrow "Résumés" | `--muted` 10.5 / .15em, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1325 | "N selected" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px**; `marginLeft:'auto'` kept (the row is `alignItems:'baseline'`) |
| JobFeed.jsx:1335 | the rescore option's note | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px**; `flex:'0 0 auto'` kept |
| JobFeed.jsx:1341 | modal eyebrow "Depth" | `--muted` 10.5 / .15em, inherited lh 15.75 → `Label` — **10.5 → 10px**, **.15 → .13em**, lh **15.75 → 15px** |
| JobFeed.jsx:1348 | the depth cards' help line | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |
| JobFeed.jsx:1357 | the rescore footer's "Runs in the background" | `--muted` 11.5, inherited lh 17.25 → `Helper` — lh **17.25 → 16px** |

**39 sites migrated** — `PageTitle` 1, `Heading` 4, `Label` 11, `Helper` 17, `Link` 3, `NavLink` 1, `Spinner` 2.

Helper line-height moves: **13** sites moved **17.25 → 16px** (`:777`, `:788`, `:959`, `:960`, `:1108`, `:1126`, `:1277`, `:1293`, `:1301`, `:1325`, `:1335`, `:1348`, `:1357`); **0** sites moved 16.5 → 16px (no 11px helper in this file); **2** sites moved **15.75 → 16px** (`:781`, `:792`). The remaining two helper sites are `:764` (already an explicit 16px — zero-pixel) and `:988` (explicit **17 → 16px**).

### kept inline
- `JobFeed.jsx:834` (comment at `:833`) — the shortcuts popover's "Keyboard" head (10.5 / .12em / `--muted`): it is the head of a `<Menu>`, which is `MenuHead`'s role (9.5/14px/.13em, its own padding), not a filter-bar eyebrow. Flagged below as a judgement call.
- `JobFeed.jsx:862` (comment at `:861`) — "Couldn't load jobs · **Try again**": the link runs inline inside a 13px sentence; `Link`'s 11.5/500 would break the run. (Same rule keeps the two bare `<a>Searches</a>` / `<a>Companies</a>` in the F-010 paragraph at `:867` — they carry no style at all and inherit the 13px run.)
- `JobFeed.jsx:894` — the row score numeral: serif 19, `color: scoreColor(score)`, `lineHeight: 1`, centred in the 44px ring. Data display, not a heading.
- `JobFeed.jsx:901` — the 8px `···` marker inside the running ring: `.07em` accent micro-glyph, not a label.
- `JobFeed.jsx:914` — the feed row title: serif **16 / 500 / -.01em / lh 1.15**. The card-title family (500-600, -.01/-.015em), which this step deliberately does not touch.
- `JobFeed.jsx:917` — the status badge (9.5/600/.1em with `background` + `border` + `borderRadius:99`): `Tag` role (D4d), not a `Label`.
- `JobFeed.jsx:934` and its two siblings — the `v2-rail-cell` glyph cells (♥ / ✕ / ⋯) at 11-12px: rail text is out of scope for D4e.
- `JobFeed.jsx:980` — the collapsing detail `<h2>`: serif **26 / 17** with `-.025em`, `lineHeight` 30/20px and a `WebkitLineClamp`. Two sizes outside the 18/19 heading scale, and the line-height is doing the header's collapse animation.
- `JobFeed.jsx:1032` — the report band's `⌄`/`›` caret at 11px in a fixed 19px centred gutter: a caret glyph, not helper text.
- `JobFeed.jsx:1039` — the band score numeral: serif 14, `color: scoreColor(...)`, centred in the 34px ring. Data display, and 14 is out of the heading scale.
- `JobFeed.jsx:1084` — the breakdown numeral `serif 15` and its inline 11px `/20` unit: data display, not a heading/helper (15 is out of the heading scale; the `/20` is a unit suffix inside the numeral).
- `JobFeed.jsx:1137` — the requirement table's column-head row (`Requirement · Résumé match · Status`, 9.5/14px/.12em with `borderBottom` + row padding): `TableHead` role (D4f).
- `JobFeed.jsx:1155` — "Hard blockers": `--bad` 10 / **600**. Neither the ink nor the weight is `Label`'s.
- `JobFeed.jsx:1208`, `:1209` — the Live / Cached segmented toggle cells (22px, `background`, r99): toggle cells, not links. The existing D4d keep comment at `:1206` was widened to say so.
- Not candidates, left untouched and uncommented: the 12px muted empty-state lines `No sources` (`:745`), `No matches` (`:766`), the 13px `No base résumés found.` (`:1285`) / `No résumés available.` (`:1327`), and the 12px cached/live caption (`:1205`) — all outside the helper size set (11 / 11.5 / 10 / 10.5).

### unsure / flag for the orchestrator
1. **`:833` "Keyboard"** — the brief said "judge it: if it is a filter-bar eyebrow it migrates". It is not; it is the head of a `<Menu>` popover, and `ui.jsx` already has a `MenuHead` primitive for exactly that role (9.5/14px/.13em + its own padding). I kept it and pointed the comment at `MenuHead`. If D4e is meant to normalise it anyway, `Label` would be a near-zero move (10.5 → 10, .12 → .13em, lh 15.75 → 15).
2. **The two spinner rings** (`:899`, `:1190`) — neither was the canonical `1.5px` ring: they are `1px` and `2px`, and both are `position:absolute` rings sized by their parent box rather than by a `size` px. I followed "any `v2-spin` ring → `Spinner`" and expressed them as `size={44}` / `size={28}` plus the original `position/inset` in `style`; the **border width changes (1 → 1.5px and 2 → 1.5px)**. If the 2px band ring was a deliberate weight, revert `:1190`.
3. **`:1264` "Open it ↗"** — at 12.5px inherited it is exactly at the 1.0px tolerance edge; migrating drops it to 11.5 next to a 12.5px sibling on the same banner line. It is a separate flex item, not inline in the sentence, so I migrated it.
4. **`:869` "Clear filters"** — migrated (13 → 11.5 + weight 500) because it sits alone on its own line after a `<br/>`, while its twin at `:862` ("Try again") is kept because it is mid-sentence. That is a deliberate split between two adjacent empty states; say the word if they should match.
5. **`:866`** grows the first-run empty state by 7px (lh 20 → 27px) because the parent paragraph sets `lineHeight:'20px'` and `Heading` overrides it. This is the only migration in the file that changes a block's height by more than ~1.5px.

## ResumeEditor.jsx

| site | element | before → after |
|---|---|---|
| ResumeEditor.jsx:466 | the top bar's "‹ Résumés" back-link | `--accent` 13/500/lh 20px, `v2-navlink` → `NavLink` — **13 → 12px**, **weight 500 → 400**, **lh 20 → 18px**; hover class unchanged (it already carried `v2-navlink`). Gains `whiteSpace:'nowrap'` and keyboard operability, matching `CoverLetterEditor.jsx:315` exactly. The bar's height is set by its 14/20px `<h1>`, so nothing moves |
| ResumeEditor.jsx:473 | the top bar's autosave line | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**; `marginLeft:'auto'` kept in `style` |
| ResumeEditor.jsx:504 | the band's "+Δ based on ‹base› ↗" jump | `v2-navlink` with no type keys — inherited 12.5/18px from the 12.5 band line — → `NavLink` — **12.5 → 12px**, lh 18 → 18px (**zero-pixel** on line-height), ink zero-pixel (both children set their own colour, so `--navlink-ink` is never painted), hover zero-pixel (already `v2-navlink`). Migrated rather than kept: the drift is 0.5px (inside the 1.0px tolerance) and the site is a bare `onClick` span that was **not keyboard-operable** — `NavLink` gives it `role="link"` + Enter/Space. `position:'relative', top:'1px'` kept in `style`; `cursor:'pointer'` dropped (the primitive supplies it) |
| ResumeEditor.jsx:512 | the band's state sub-line ("N reviewable changes" / "ready" / tracers) | `--muted` 11, inherited lh 16.5 → `Helper` — **11 → 11.5px**, **lh 16.5 → 16px**; the `whiteSpace/overflow/textOverflow` clamp kept in `style` |
| ResumeEditor.jsx:524 | the one-next-step Button's ring | 11px `1.5px currentColor` `v2-spin` ring → `Spinner size={11} color="currentColor"` — **zero-pixel** (gains `flex:'0 0 auto'` + `display:'inline-block'`; `borderRadius:99` → `--radius-control`, which is 99px). The stale D4d `ui: keep — Spinner role …` comment above it was removed, superseded by D4e |
| ResumeEditor.jsx:592 | the "PDF preview" toolbar label | `--muted` 10 · **.14em** uppercase, inherited lh 15 → `Label` — **letter-spacing .14 → .13em**, lh 15 (inherited) → 15px (explicit) |
| ResumeEditor.jsx:677 | the re-tailor modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| ResumeEditor.jsx:678 | its "company — title · adds a new copy" sub-line | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px**; ellipsis clamp kept in `style` |
| ResumeEditor.jsx:685 | the "How" label | `--muted` 10 · **.14em** uppercase → `Label` — **letter-spacing .14 → .13em** |
| ResumeEditor.jsx:693 | the tailor/copy mode hint | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel**; `textWrap:'pretty'` kept in `style` |
| ResumeEditor.jsx:701 | the "From which base" label | `--muted` 10 · **.14em** uppercase → `Label` — **letter-spacing .14 → .13em** |
| ResumeEditor.jsx:711 | the base-row "current base"/note | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel**; `flex:'0 0 auto'` kept in `style` |
| ResumeEditor.jsx:715 | the "No base résumés yet." empty band | the `Band` `style` carried `11.5/17px --muted` → the text is wrapped in `Helper`, `Band` keeps only `padding:12` — **lh 17 → 16px** |
| ResumeEditor.jsx:721 | the re-tailor footer's "Runs in the background" | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** |
| ResumeEditor.jsx:722 | its chain note | `--muted` 10.5/15px → `Helper size="xs"` — **lh 15 → 16px**; `textWrap:'pretty'` kept in `style` |
| ResumeEditor.jsx:783 | the tailor modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| ResumeEditor.jsx:784 | its sub-line | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** |
| ResumeEditor.jsx:792 | the "Pick a job · saved and scored first" label | `--muted` 10 · **.14em** uppercase → `Label` — **letter-spacing .14 → .13em** |
| ResumeEditor.jsx:802 | the job row's "company · status" | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel**; ellipsis clamp kept in `style` |
| ResumeEditor.jsx:810 | the "No jobs match…" empty band | the `Band` `style` carried `11.5/17px --muted` → the text is wrapped in `Helper`, `Band` keeps only `padding:12` — **lh 17 → 16px** |
| ResumeEditor.jsx:813 | the "…or a freeform job description" label | `--muted` 10 · **.14em** uppercase → `Label` — **letter-spacing .14 → .13em** |
| ResumeEditor.jsx:821 | the tailor footer's "Runs in the background" | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** |
| ResumeEditor.jsx:824 | its chain note | `--muted` 10.5/15px → `Helper size="xs"` — **lh 15 → 16px**; `textWrap:'pretty'` kept in `style` |
| ResumeEditor.jsx:857 | the review modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| ResumeEditor.jsx:858 | its explanatory sub-line | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** |
| ResumeEditor.jsx:877 | the change row's "where" label | `--muted` 10 · .13em uppercase, **lh 16px** → `Label` — **lh 16 → 15px**; safe: the row is `flex / align-items:center / flex-wrap` with no fixed height, so nothing is being centred by that line-height |
| ResumeEditor.jsx:882 | "added when you finish reviewing" | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel** |
| ResumeEditor.jsx:902 | the review footer's count line | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px** |

### kept inline
- `ResumeEditor.jsx:469` — the tailored/base badge: `Tag` role (D4d) — uppercase 9.5 · .08em but with a `background` and `borderRadius:99`.
- `ResumeEditor.jsx:486` — the score numeral in the ring: serif 13.5 in `scoreColor(…)`, centred; data display, not a `Heading`.
- `ResumeEditor.jsx:597`, `:606` — the two 9px muted `▾` carets in the Template / Paper triggers: the PDF-preview toolbar's own paper scale, below `Helper`'s tolerance.
- `ResumeEditor.jsx:472` — the `<h1>` doc name (14/20px sans, deliberately not the serif `PageTitle`, R2-S-06) — same call as `CoverLetterEditor.jsx:320`.
- `ResumeEditor.jsx:805` — the job row's fit score: the `mono-text` role (`var(--mono)` 10.5/16 in `--accent`, not `--helper-ink`); the step excludes mono ids.
- `ResumeEditor.jsx:806` — the "✦ exists" hint: 9/14px in `--warn`; below `Helper`'s tolerance and not a muted ink.
- `ResumeEditor.jsx:580` — the "● changed by tailoring" section meta: 10px in `--warn`, a state meta mark rather than a muted helper.
- `ResumeEditor.jsx:880` — the applied/suggested/declined state badge: `Tag` role (D4d), already carried its own keep comment.
- `ResumeEditor.jsx:552`, `:619`, `:867`, `:886` — 12.5px body copy (base-résumé band, "Preview failed", the empty-review line, the diff run): the 12.5 body step, not a helper size.

## ResumeSections.jsx

| site | element | before → after |
|---|---|---|
| ResumeSections.jsx:66 | `Field`'s label (every résumé/Persona field on both screens) | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel** |
| ResumeSections.jsx:137 | `EmptyState`'s note line | `--muted` 11.5/17px, centred → `Helper style={{textAlign:'center'}}` — **lh 17 → 16px** |
| ResumeSections.jsx:144 | `MicroField`'s label (Education/Projects micro-fields) | `--muted` 9.5/14px · .13em uppercase → `Label` — **9.5 → 10px**, **lh 14 → 15px** |
| ResumeSections.jsx:157 | `SectionShell`'s `(count)` | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** |
| ResumeSections.jsx:197, :204, :209 | the header editor's three uppercase labels (`style={UPPER}`) | the shared `UPPER` const (10 · .13em · uppercase · `--muted`, inherited lh 15px) → `Label`; the const is deleted — **zero-pixel** |
| ResumeSections.jsx:210 | "text · link · stub" hint | `--faint` (= `--muted`) 10.5/16px → `Helper size="xs"` — **zero-pixel** |
| ResumeSections.jsx:266, :267 | an experience row's date and bullet count in the collapsed head | `--muted` 11 (one also `fontFamily:'var(--sans)'`), line-height inherited from `SectionHead card` (18px) → `Helper` — **11 → 11.5px**, **lh 18 → 16px** (the row's height is still set by the 12.5/18px title, so the head does not move) |
| ResumeSections.jsx:330 | the summary character count | `--faint` 10.5/16px → `Helper size="xs"` — **zero-pixel** |
| ResumeSections.jsx:453 | the Projects "Bullets" label | `--muted` 9.5/14px · .13em uppercase → `Label` — **9.5 → 10px**, **lh 14 → 15px** |

### kept inline
- `ResumeSections.jsx:287`, `:299`, `:301`, `:329`, `:456` — the ✦ / — / ↩ markers and the "suggested" tag inside the field-shaped prose rows: they carry `lineHeight:'19px'` to ride `BulletText`'s prose line; `Helper`'s 16px would unalign them (one comment marks the group).
- `ResumeSections.jsx:136`, `:265`, `:266` (title/company) — 12.5/13 body runs: the `text` role.

## CoverLetterEditor.jsx

| site | element | before → after |
|---|---|---|
| CoverLetterEditor.jsx:295, :296 | the error state's "‹ Back to cover letters" / "Try again" | `--accent`, size inherited from the block's 13px, `v2-anchor` → `Link` — **13 → 11.5px**, **+ weight 500**, **lh 19.5 → 17px**, hover ink `--anchor-ink-hover` (`--text`) → `--link-ink-hover` (`--accent`, i.e. no hover colour change) |
| CoverLetterEditor.jsx:315 | the top bar's "‹ Cover Letters" back-link | `--accent` 13/500, `v2-ctl` (lh 1), no hover class → `NavLink` — **13 → 12px**, **weight 500 → 400**, **lh 1 → 18px**, **gains the `v2-navlink` background wash on hover**. The bar's height is set by its 14/20px `<h1>`, so it does not move |
| CoverLetterEditor.jsx:322 | the autosave / save-error line | `--muted`, `--bad` on error, 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px**; the `--bad` ink stays a state tint, written as a conditional spread (never `: undefined`, per the D4c rule) |
| CoverLetterEditor.jsx:336 | the context band's voice · length line | `--muted` 11/17px → `Helper` — **11 → 11.5px**, **lh 17 → 16px** |
| CoverLetterEditor.jsx:340 | the "Generate/Regenerate" button's ring | 11px `1.5px currentColor` `v2-spin` ring → `Spinner size={11} color="currentColor"` — **zero-pixel** (gains `flex:'0 0 auto'`) |
| CoverLetterEditor.jsx:370, :375, :419, :423, :427, :431, :440, :466, :470 | the nine letter-field labels (`style={FLABEL}`) | the shared `FLABEL` const (10 · .13em · uppercase · `--muted`, inherited lh 15px) → `Label`; the const is deleted — **zero-pixel** |
| CoverLetterEditor.jsx:378 | "text · link · stub" hint | `--muted` 10.5/16px → `Helper size="xs"` — **zero-pixel** |
| CoverLetterEditor.jsx:480 | the "PDF preview" toolbar label | `--muted` 10 · **.14em** → `Label` — **letter-spacing .14 → .13em**, lh 15 (inherited) → 15px |
| CoverLetterEditor.jsx:481 | the PDF-preview busy ring | 10px `1.5px var(--edge)` ring → `Spinner size={10} color="var(--edge)"` — **zero-pixel** |
| CoverLetterEditor.jsx:528 | the "Regenerate letter" modal title | serif 18 · -.02em, inherited lh 27px → `Heading` — **zero-pixel** |
| CoverLetterEditor.jsx:529 | its sub-line | `--muted` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px** |
| CoverLetterEditor.jsx:535, :540, :544 | the regenerate modal's three labels (`{...FLABEL, letterSpacing:'.14em'}`) | 10 · **.14em** uppercase `--muted` → `Label` — **letter-spacing .14 → .13em** |
| CoverLetterEditor.jsx:537 | "Bases and Persona — …" hint | `--muted` 10.5, inherited lh 15.75 → `Helper size="xs"` — **lh 15.75 → 16px** |
| CoverLetterEditor.jsx:549 | the modal footer's "~30 seconds" / error line | `--muted` / `--bad` 11.5, inherited lh 17.25 → `Helper` — **lh 17.25 → 16px** |
| CoverLetterEditor.jsx:554 | the modal's Generate ring | 9px `currentColor` ring → `Spinner color="currentColor"` — **zero-pixel** |

### kept inline
- `CoverLetterEditor.jsx:44` — the letter-section head's note: `lineHeight:'20px'` rides the 13/20px title; `Helper`'s 16px would unalign the head.
- `CoverLetterEditor.jsx:447` — the `¶ n` paragraph ordinal: drawn in `--edge` (a dimmer ink than `--label-ink`) at .1em.
- `CoverLetterEditor.jsx:317` — the stage badge: `Tag` role (D4d), painted by a `cc-*` class.
- `CoverLetterEditor.jsx:487`, `:502` — the 9px `▾` carets in the template / paper triggers: the preview toolbar's own glyph scale.
- `CoverLetterEditor.jsx:320` — the `<h1>` doc name (14/20px sans, deliberately not the serif page title, R2-S-06).

## LoginModal.jsx

| site | element | before → after |
|---|---|---|
| LoginModal.jsx:53 | the "Signed in" title | serif 19 · -.02em, no `lineHeight` (inherited 1.5 = 28.5px) → `Heading size={19}` — **line-height 28.5 → 26px** |
| LoginModal.jsx:67 | the "API key" field label | `--muted` 9.5/14px · .13em uppercase → `Label` — **9.5 → 10px**, **lh 14 → 15px** |
| LoginModal.jsx:81 | the sign-in error line | `--bad` 11.5/16px → `Helper style={{color:'var(--bad)'}}` — **zero-pixel** (the bad ink stays as a state tint) |
| LoginModal.jsx:88 | the "First run with no key…" note | `--muted` 11 · lh 1.55 (= 17.05px) → `Helper` — **11 → 11.5px**, **lh 17.05 → 16px** |

### kept inline
- `LoginModal.jsx:60` — the wordmark "JobNavigator": serif 23/28px; the `Heading` scale is 18/19/22.
- `LoginModal.jsx:77` — the show/hide key toggle: deliberately `tabIndex={-1}` (out of the tab order beside the field); `Link` is a tab stop with `role="link"`.
- `LoginModal.jsx:54`, `:61` — 12.5 `--muted` runs: the `text` role, which stays inline.

## WelcomeModal.jsx

| site | element | before → after |
|---|---|---|
| WelcomeModal.jsx:52 | each step's description line | `--muted` 11.5/17px → `Helper` — **lh 17 → 16px** (×4 rows) |

### kept inline
- `WelcomeModal.jsx:35` — the welcome title: serif 21/26px; the `Heading` scale is 18/19/22.
- `WelcomeModal.jsx:36` — the ✕ close control (13/26px, `v2-hover-accent-text`): an icon button, not a link; the scanner files it under `section-head` by hover-class prefix.
- `WelcomeModal.jsx:39`, `:48` — 12.5 / 13 body runs: the `text` role.

## ConfirmDialog.jsx  *(not in the ordered file list; both sites are exactly canonical)*

| site | element | before → after |
|---|---|---|
| ConfirmDialog.jsx:18 | confirm dialog title | serif 19/26px · -.02em → `Heading size={19}` — **zero-pixel** |
| ConfirmDialog.jsx:43 | prompt dialog title | serif 19/26px · -.02em → `Heading size={19}` — **zero-pixel** |

## Toast.jsx  *(not in the ordered file list; one spinner site)*

| site | element | before → after |
|---|---|---|
| Toast.jsx:63 | the toast's busy ring | 11px `1.5px currentColor` `v2-spin` ring → `Spinner size={11} color="currentColor"` — **zero-pixel** (gains `flex:'0 0 auto'`, `display:'inline-block'`, `aria-hidden`); the stale D4d `ui: keep — Spinner role …` comment is removed, superseded by D4e. `Toast.jsx` now imports from `./ui` (no cycle: `ui.jsx` imports only `hooks`/`theme.css`) |

### kept inline
- `Toast.jsx:65` — the 16px filled ✓/✕ glyph badge (a D4d keep: `Dot` draws a bare tone disc with no glyph).
- `Toast.jsx:69`, `:71` — the 12.5 message run and the 12/600 action word: the `text` role.
