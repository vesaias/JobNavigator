# expected-S5 — default-theme computed-style changes

**Target: none.** Every change in S5 is either scoped to a theme by selector, or
resolves through a token whose base-block value reproduces the literal it
replaced. The list below is the per-edit argument, property by property, against
the 19-property slice `tools/stylecrawl.py` records (`backgroundColor, color,
border{Top,Bottom}{Color,Width}, borderTopStyle, borderRadius, boxShadow,
fontFamily, fontSize, fontWeight, lineHeight, paddingTop, paddingLeft, height,
letterSpacing, textTransform, opacity, cursor`).

Gate to run: `tools/stylecrawl.py` at `data-theme=default`, then `stylediff.py`
against `S4b`. **Expected diff: 0 rows.**

---

## 1 · theme.css — the two bevel rules move behind a theme gate

Before: `.jn-v2 .v2-raised { border:…; border-color:…; box-shadow:… }` and the
matching `.v2-inset` rule, unscoped, no `!important`.
After: both scoped to `.jn-v2[data-theme="win98"]`, both `!important`.

In the default theme the selector no longer matches, so the question is what the
old rule was contributing there. It could only reach a property the carrier does
**not** set inline (an inline declaration beats a plain class rule) — so the audit
is "which carrier leaves `border` or `box-shadow` undeclared":

| carrier (ui.jsx) | inline `border` | inline `boxShadow` | old rule reached | after |
|---|---|---|---|---|
| `Pill` | yes | yes (`--pill-shadow`) | nothing | unchanged |
| `IconButton` 36/25 (bordered) | yes | yes (`--pill-shadow`) | nothing | unchanged |
| `IconButton` 26 | — (no `v2-raised`) | — | n/a | unchanged |
| `Chip` | yes | yes (`--pill-shadow`) | nothing | unchanged |
| `Menu` | yes (`--bw-panel`) | yes (`--menu-shadow`) | nothing | unchanged |
| `ModalPanel` | yes (`--bw-panel`) | yes (`--modal-shadow`) | nothing | unchanged |
| `ToastCard` | yes (`--bw-panel`) | yes (`--shadow-toast`) | nothing | unchanged |
| `Segmented` cell, `!inset`, **on** | yes | yes (`--seg-on-shadow`) | nothing | unchanged |
| `Segmented` cell, `!inset`, **off** | yes | **no** | `box-shadow:none` | still `none` — `none` *is* the initial value |
| `Input` / `Textarea` (`FIELD`) | yes | yes (`--field-shadow`) | nothing | unchanged |
| `Select` trigger | yes | yes (`--field-shadow`) | nothing | unchanged |
| `SearchInput` boxed | yes | yes (`--field-shadow`) | nothing | unchanged |
| `SearchInput` underline | yes (`border:'none'` + `borderBottom`) | **no** | `box-shadow:none` | still `none` |
| `Drawer` | — (deliberately no hook) | — | n/a | unchanged |
| `HeaderRow variant="titlebar"` glyphs | no | no | `border:none` + `border-color:transparent` | **never mounts outside win98** — `useTitleBar()` gates on `--title-bar ≠ none`, which is `none` in every block but win98's two |

Net: the only properties the old rule actually painted in the default theme were
`box-shadow:none` on two carriers, where `none` is already the computed initial
value. **0 changed tuples.**

`:active` is not in the crawl's state set, so the `.v2-raised:active` half is out
of scope either way; the same table applies to it.

Two carve-outs added to the inset selector (`:not(.v2-underline)`,
`:not([aria-invalid="true"])`) only narrow a win98-only rule.

## 2 · theme.css — new rule `.v2-rowink` (selected-row ink)

`.jn-v2[data-theme="win98"] .v2-row[aria-current="true"] .v2-rowink{, *}`.
A new selector that names a theme; it cannot match at `data-theme="default"`.
**0 changed tuples.**

## 3 · theme.css — new token `--label-tracking-scale`

Added to both base blocks as `1`, and to the two win98 blocks as `0`. Custom
properties are not in the crawl's property slice, and the three call sites that
read it (§6) resolve to their previous literal at `1`. **0 changed tuples.**

## 4 · theme.css — win98 `--input-border-hover`

`none` → `var(--bevel-inset-color)`, in the two win98 blocks only. Not reachable
from the default theme. **0 changed tuples.**

## 5 · ui.jsx — `Button` disabled ink + engrave

- `color: 'var(--btn-*-disabled-ink)'` → `color: 'var(--disabled-ink, var(--btn-*-disabled-ink))'`
  (5 sites: primary/ai/danger `off` → the primary token, secondary/ghost `off` →
  the secondary token).
  In both base blocks `--disabled-ink` is the CSS-wide keyword `inherit`. On a
  **custom property** that keyword applies to the property itself, so the name
  inherits from `<body>`, where nothing sets it, and lands on the
  guaranteed-invalid value. `var()` therefore takes the **fallback**, which is the
  literal token the line used before. Same computed `color`.
  (Cross-check: `theme.css`'s own comment on `.jn-v2 [aria-disabled="true"]`
  relies on the identical reading — "`--disabled-ink` is `inherit` here so it
  cannot repaint a control that sets no colour of its own".)
  Cobalt/saas set `--disabled-ink: var(--muted)` and never override
  `--btn-*-disabled-ink` (which is `var(--muted)` in the base blocks), so those
  two themes are unchanged as well; only win98 (`#808080`) takes over.
- new `textShadow: 'var(--disabled-engrave)'` on `off` buttons only.
  `--disabled-engrave` is `none` in both base blocks, which is `text-shadow`'s
  initial value — and `text-shadow` is not one of the 19 recorded properties.

**0 changed tuples.**

## 6 · Three caps labels read `--label-case` / `--label-tracking-scale`

`V2App.jsx:186` (rail group headers), `ResumeEditor.jsx:533` (Base/Tailored
badge), `CoverLetterEditor.jsx:353` (the Draft/stage badge), plus
`design-base/ToastLab.jsx:47` (the lab's kind label — git-ignored, not crawled).

- `textTransform: 'uppercase'` → `'var(--label-case)'`; base value **is**
  `uppercase`. Identical.
- `letterSpacing: '.16em'` / `'.08em'` → `calc(.16em * var(--label-tracking-scale))`
  / `calc(.08em * var(--label-tracking-scale))`; base scale is `1`, and
  multiplication by exactly 1 is exact in the used-value arithmetic (both forms
  compute `font-size × 0.16` through the same em resolution). Identical.

`Settings.jsx:620` ("inherits Primary" badge) additionally swaps its `.06em`
literal for `var(--tag-tracking)` — whose base value **is** `.06em`, so the read
is exact rather than scaled. The Settings **side-nav group headers** needed no
change at all: they are already `<Label>` (`ui.jsx:1694`), which has read
`--label-tracking` / `--label-case` / `--label-weight` since S3. The proof's
claim that they hard-code caps is stale.

`fontWeight` is deliberately **not** switched to `--label-weight` at any of these
sites: none of them declares a weight today, so they inherit one, and writing
`var(--label-weight)` (base `400`) would pin a value where an inherited one
stands. That is a real default-theme change and is left for a decision.

**0 changed tuples.**

## 7 · Class-only additions (`v2-rowink`)

`JobFeed.jsx` — the row title `Heading`, the ✦ tailored link, the company line
and the meta line. `Applications.jsx` — the row title, the ✉ (conditionally, see
below), the company `Helper` and the days `Helper`.

`v2-rowink` is a new class name with exactly one rule in the stylesheet, and that
rule is theme-gated (§2). It does not match `tools/stylelint.py`'s `HOVER`
pattern (`v2-row` followed by `ink` fails the `\b`), so no lint state changes
either. **0 changed tuples.**

The ✉ in Applications takes the class only when it is actually visible; it hides
itself with `color: transparent`, and an unconditional ink override would reveal
a glyph that means "no reply". Its `className` is `undefined` in the hidden case,
which React omits.

## 8 · `JobFeed.jsx:1217` — the "Tailor résumé" CTA routed through `Button`

The hand-drawn `<div>` becomes `<Button size="sm" style={{height, padding, lineHeight}}>`.
Property by property, in the default theme:

| property | before (hand-drawn div) | after (`Button size="sm"` + override) |
|---|---|---|
| `backgroundColor` | `var(--accent)` | `var(--btn-primary-bg)` = `var(--accent)` |
| `color` | `var(--accent-ink)` | `var(--btn-primary-ink)` = `var(--accent-ink)` |
| `border{Top,Bottom}{Color,Width}`, `borderTopStyle` | undeclared → `0px none currentColor` | primary `rest` declares no border either (only the `as="button"` branch does, unused here) → same |
| `borderRadius` | `var(--radius-control)` | `var(--radius-control)` |
| `boxShadow` | undeclared → `none` | `var(--btn-shadow)` = **`none`** in both base blocks (this is the whole point: cobalt sets `0 1px 2px rgba(45,91,227,.30)`) |
| `fontFamily` | inherited | `var(--font-body)` = `var(--sans)`, which is what `.jn-v2` sets and nothing between (`HeaderRow` non-titlebar, `.v2-fold`, `.v2-foldbody`, the two wrapper divs) overrides |
| `fontSize` | `13` | `BTN_SIZE.sm` = `var(--t-13)` = `13px` |
| `fontWeight` | `500` | `var(--btn-weight)` = `500` |
| `lineHeight` | inherited (`.v2-ctl` was absent) | `Button` adds `v2-ctl` (`line-height:1`), so the override writes `lineHeight:'inherit'` — an inline value beats the `(0,1,0)` class rule, and `inherit` on a child that previously had no declaration is the same computed value by definition |
| `paddingTop` / `paddingLeft` | `0` / `19` | override `'0 19px'` |
| `height` | `headOpen ? 36 : 30` | override, unchanged |
| `letterSpacing` / `textTransform` | inherited, undeclared | `Button` declares neither |
| `opacity` | undeclared → `1` | `busy && !disabled ? .6 : 1` → `1` |
| `cursor` | `pointer` | `off ? 'default' : 'pointer'` → `pointer` |

Not in the crawl slice, listed for completeness: `Button` adds
`flex:'0 0 auto'` (the parent actions cell is itself `0 0 auto` and sized to
max-content, so nothing shrinks at any width the gate captures),
`justifyContent:'center'` and `gap:8` (one child, no effect),
`whiteSpace:'nowrap'`, and the `v2-btn-primary` state class — whose hover and
pressed rules resolve to the button's own rest paint in the base blocks (D-11 /
D-07 are still inert). `role="button"` + `tabIndex` are the accessibility gain.

**0 changed tuples.**

---

## What is NOT covered by this file

`width` is not in the crawl slice, so the `flex-shrink` change on the Tailor CTA
(§8) is argued from the layout, not measured. At the gate's 1440 width the
actions cell has slack; at 1024 the pane already truncated its header before this
change (`proof-skins-B.md`, "identical in the S4b baseline at 1024").
