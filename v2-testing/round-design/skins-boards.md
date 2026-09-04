# Three board skins: `cobalt` · `saas` · `win98`

Source boards (Claude Design project `4d073a40-62f3-4af1-adc2-4f5acbae6a31`):

| skin | board | size | palette source | ~ geometry source |
|---|---|---|---|---|
| `cobalt` | `Feed - Cobalt.dc.html` | 203 KB / 2396 lines | `:root` l.95–99, `[data-theme="dark"]` l.100–104 | markup l.106–2396, plus `Cobalt Elements.dc.html` (the full primitive-by-primitive swap) |
| `saas` | `Feed - SaaS.dc.html` | 205 KB / 2397 lines | `:root` l.95–99, `[data-theme="dark"]` l.100–104 | markup l.106–2397 |
| `win98` | `Feed - Win98.dc.html` | 208 KB / 2395 lines | `:root` l.95–99, `[data-theme="dark"]` l.100–104 | markup l.106–2395 |

`Skin Lab.dc.html` (l.98–176) is the five-column shape-language study (Paper · Soft ·
Outline · Glass · Pop) these three descend from. It is explicit that palette is the
*secondary* axis — "What changes per skin: surface model, radii, border/shadow regime,
type stacks, label casing, density, canvas texture. Palette is secondary" (l.22). That
sentence is this document's whole subject: v2's skin layer carries the secondary axis
and none of the primary one.

Each board's helmet also carries a ~60-line `[data-skin="…"]` preamble (l.15–90) left
over from the Skin Lab experiment. It is dead in all three — the board root never sets
`data-skin` — and in the Win98 copy its radii were globally search/replaced to `0`, so
it does not describe any of these three boards. It is **not** a source; the boards' own
`:root` and inline markup are.

Shipped as: `frontend/src/v2/theme.css` (6 new blocks), `theme.js` (`SKINS`,
`SKIN_LABEL`), `frontend/index.html` (boot skin list + 6 ground rules),
`frontend/src/v2/Settings.jsx` (Skin help line).

---

## What a skin can carry, and what these boards ask for

A `[data-skin]` block may declare **the 60 palette tokens the `alt` skin declares, and
nothing else** — three ring offsets, the colour ladder, the state colours, the stage and
chart colours, the rail, and the three font stacks. Everything geometric —
`--radius-*` (10), `--shadow-*` (5), `--t-*` (21), every border width, every primitive's
box model — lives once in the two base `.jn-v2` blocks and is shared by construction
(that is the D6 guarantee: switching `data-skin` may change colour and font family and
nothing else).

All three boards change geometry. So each skin below reproduces the board's **colour and
type identity** and reads as a recolour of the shipped shape language, not as the board.
The per-board delta lists say precisely what is missing.

### Gate results

| gate | result |
|---|---|
| identical token names across all 16 `[data-skin]` blocks | 60 tokens each, no missing / extra / duplicate names |
| `py v2-testing/tools/stylelint.py` | `0 findings ({}), 93 allowed, 0 css` — exit 0 |
| `npx esbuild@0.21.5 --loader:.css=css --minify theme.css` | exit 0; **16** `[data-skin]` rules survive (2 each × alt, tone1–3, editorial, cobalt, saas, win98) |
| `node --check frontend/src/v2/theme.js` | parses; `SKINS = ['default','tone1','tone2','tone3','editorial','alt','cobalt','saas','win98']` |
| `index.html` grounds vs each block's `--bg` | 16/16 identical |

### Ring offsets

All three seed at the **default** values — `--ring-shift-sm:2px`, `--ring-shift-md:1px`,
`--ring-label-shift:0px` — and the ink measurement is to be re-run after the build.

Reasoning. `ring-sizes.md` gives exactly two calibrated cross-face points: Newsreader
(default display face) needs +2.00px at `sm`/14px, Georgia (`alt`) +1.25px. The whole
0.75px move is explained by one qualitative fact, not by nominal metrics: **Georgia has
old-style figures** — in the reference score `77` both digits descend, dropping the ink
centre roughly 0.05 em, i.e. 0.70px at 14px and 0.95px at 19px, which brackets the
measured 0.75px / 0.58px. The residual (hhea ascent−descent differs by ~0.05 em between
the two faces) moves the number the other way and is second-order.

The three new display faces — IBM Plex Sans (cap 0.698), system-ui / Segoe UI (cap
0.700), Tahoma (cap 0.727) — all have **lining figures**, like Newsreader. They therefore
sit in the 2px family, not the 1.25px family. The remaining metric spread against the
default's Public Sans body face and Newsreader display face is ≤ 0.03 em in cap height
and ≤ 0.05 em in A−D, which is ≤ 0.25px at the 14px / 19px numeral sizes and ≤ 0.2px at
the 7.5px "No fit" label — inside the ±0.25px tolerance that measurement pass used. A
metrics-derived number would be false precision: the same model predicts 0.19px for the
Public Sans → Inter label move, where the measurement produced 1.58px. So: seed at the
default, measure, adjust.

### Contrast — all four text roles on `--surface`, the rail inks, the button ink

`default` is included as the reference the `alt` skin was matched against.

| skin / mode | `--text` | `--text-2` | `--muted` | `--accent` | `--text` on `--bg` | `--muted` on `--bg` | `--rail-text` | `--rail-dim` | `--rail-accent` | `--accent-ink` on `--accent` |
|---|---|---|---|---|---|---|---|---|---|---|
| default light | 17.41 | 7.66 | 5.52 | 6.11 | 16.82 | 5.33 | 6.41 | 4.88 | 7.48 | 6.11 |
| default dark | 10.64 | 9.09 | 6.17 | 7.11 | 11.82 | 6.86 | 5.94 | 5.08 | 8.89 | 8.55 |
| **cobalt light** | 17.76 | 6.13 | 4.44 | 5.65 | 16.28 | 4.07 | 5.90 | 3.67 | 6.75 | 5.65 |
| **cobalt dark** | 14.76 | 9.10 | 5.90 | 4.55 | 15.71 | 6.28 | 6.51 | 3.19 | 7.43 | **3.90** |
| **saas light** | 17.74 | 7.56 | 4.83 | 6.70 | 16.98 | 4.63 | 12.02 | 6.96 | 9.90 | 6.70 |
| **saas dark** | 13.34 | 9.96 | 5.78 | 5.77 | 16.12 | 6.99 | 7.69 | 4.29 | 10.85 | 7.36 |
| **win98 light** | 11.54 | 11.54 | 5.70 | 8.80 | **4.40** | **2.17** | 11.54 | 5.70 | 8.80 | 16.01 |
| **win98 dark** | 11.54 | 11.54 | 5.70 | 6.20 | **1.46** | **1.38** | 11.54 | 5.70 | 6.20 | 11.28 |

Bold = below 4.5:1. Rail inks are measured against that skin's own `--rail`.

Secondary pairs (tone ink on its own soft ground, and the two chart invariants):

| skin / mode | good on accent-soft | warn on warn-soft | bad on bad-soft | accent on accent-soft | `--series-new` vs `--stage-applied` (≥2.0) | `--series-new` vs `--bg` (≥3.0) | `--series-new` vs `--surface` |
|---|---|---|---|---|---|---|---|
| default light | 5.32 | 4.68 | 5.89 | 5.32 | 2.10 ✓ | 3.24 ✓ | 3.35 |
| default dark | 6.37 | 6.80 | 6.27 | 6.37 | 2.20 ✓ | 4.04 ✓ | 3.64 |
| cobalt light | 4.60 | 4.26 | 4.57 | 4.82 | 2.46 ✓ | 3.07 ✓ | 3.35 |
| cobalt dark | 7.48 | 9.20 | 6.49 | **3.58** | 2.23 ✓ | 4.24 ✓ | 3.98 |
| saas light | 4.61 | 4.84 | 5.91 | 6.16 | 2.13 ✓ | 3.27 ✓ | 3.42 |
| saas dark | 6.60 | 10.01 | 6.25 | 4.52 | 2.32 ✓ | 3.92 ✓ | 3.24 |
| win98 light | 4.32 | 7.38 | 7.92 | 8.80 | 2.40 ✓ | **1.40 ✗** | 3.67 |
| win98 dark | 4.09 | 6.21 | 7.92 | 6.20 | 2.01 ✓ | **2.56 ✗** | 3.08 |

Four numbers to call out, all recorded rather than silently retuned:

- **cobalt dark `--accent-ink` 3.90** and **`--accent` on `--accent-soft` 3.58** are the
  board's own `#ffffff` on `#4d79f6` and `#4d79f6` on `#1c2b4d` (l.102). Kept for board
  fidelity; both are button/tag inks, not body copy. Precedent: the `editorial` skin
  ships the board's `--muted` at 3.44 and `--rail-dim` at 2.57 for the same reason.
- **cobalt light `--muted` 4.44** is the board's `#707887` (also its `--sc-none`).
  Within rounding of AA; kept as extracted.
- **win98 `--bg`** is a *desktop* colour, not a text ground: `#008080` in light,
  `#1f2b3a` in dark, with the whole rest of the skin on black ink. On the board that is
  fine — every glyph sits on a `#c0c0c0` window or a white client area, and the desktop
  shows only as the gutter around the floating panes (l.106, l.245, l.320). In v2 the
  root paints `--bg` under `--text`, and `--head-bg-page` and `--chip-bg` both resolve to
  it, so any uncovered area inherits 4.40:1 (light) / 1.46:1 (dark). This is not fixable
  inside a palette block: it needs `--head-bg-page` / `--chip-bg` re-pointed at
  `--surface` per skin, i.e. a semantic-layer change. Also note black on `#008080` tops
  out at 4.40:1 — the hue itself cannot carry AA text, whatever ink is chosen.
- **win98 `--series-new` vs `--bg` misses in both modes** (1.40 / 2.56). With a
  near-black `--stage-applied` (`#000080` / `#2b3a5c`) and a mid-grey chart ground
  (`--surface` `#c0c0c0`), the ≥2:1-vs-stage and ≥3:1-vs-`--surface` windows leave a
  luminance band of ~0.006 wide, and no value in it also clears the teal/navy desktop.
  Optimised for the ground the chart actually paints on (`--surface`: 3.67 / 3.08) and
  the stage gap (2.40 / 2.01); the `--bg` leg is recorded as missed.

Two board values were **moved**, both because they fell below 3:1 as ink on `--surface`
(the rule applied uniformly here: keep every board value unless a text role drops below
3:1, then take the smallest step that clears 4:1):

| skin/mode | token | board | shipped | before → after on `--surface` |
|---|---|---|---|---|
| win98 light | `--good` | `#008000` (l.97) | `#006000` | 2.82 → 4.32 |
| win98 light | `--warn` | `#808000` (l.97) | `#575700` | 2.31 → 4.17 |

---

## 1 · `cobalt`

**Board name** "Cobalt". `Cobalt Elements.dc.html` is its element sheet: "Left: the
Editorial primitive as shipped in `ui.jsx`. Right: the same primitive in Cobalt … only
the primitive's own paint changes, so this is a theme.css block plus a handful of variant
tweaks" (l.20). The "handful of variant tweaks" is the delta below.

### Extracted tokens

Straight from `:root` (l.96–98) and `[data-theme="dark"]` (l.101–103):

| token | light | dark | board line |
|---|---|---|---|
| `--bg` | `#f4f5f7` | `#0f1115` | 96 / 101 |
| `--surface` | `#ffffff` | `#16181d` | 96 / 101 |
| `--surface-2` | `#f7f8fa` | `#1c1f26` | 96 / 101 |
| `--line` | `#e3e5ea` | `#2a2f3a` | 96 / 101 |
| `--line-soft` | `#eef0f3` | `#22262f` | 96 / 101 |
| `--edge` | `#d7dae1` | `#3a4050` | 96 / 101 |
| `--track` | `#eef0f3` | `#2a2f3a` | 96 / 101 |
| `--text` | `#16181d` | `#e8eaf0` | 97 / 102 |
| `--text-2` | `#5b6270` | `#b3bac7` | 97 / 102 |
| `--muted` | `#707887` | `#8d95a6` | 97 / 102 |
| `--accent` | `#2d5be3` | `#4d79f6` | 97 / 102 |
| `--accent-ink` | `#ffffff` | `#ffffff` | 97 / 102 |
| `--accent-soft` | `#e7edfd` | `#1c2b4d` | 97 / 102 |
| `--good` | `#157a43` | `#5fd394` | 98 / 103 |
| `--warn` | `#946c07` | `#e8c46a` | 98 / 103 |
| `--warn-soft` | `#fbf2d7` | `#2b2410` | 98 / 103 |
| `--bad` | `#c23b32` | `#f28b82` | 98 / 103 |
| `--bad-soft` | `#fdeaea` | `#3c1a1a` | 98 / 103 |
| `--rail` | `#16181d` | `#090c12` | 98 / 103 |
| `--rail-text` | `#8d95a6` | `#8d95a6` | 98 / 103 |
| `--rail-dim` | `#6b7280` | `#5b6270` | 98 / 103 |
| `--rail-accent` | `#7f9cf5` | `#7f9cf5` | 98 / 103 |
| `--rail-ink` | `#ffffff` | `#ffffff` | 98 / 103 |
| `--rail-line` | `#232a38` | `#1a1f2b` (derived) | 118 (rail footer `border-top`) |
| `--warn-line` | `#ecd9a0` | derived | Elements l.60 (ATS notice border) |
| `--toast-ok-bg` / `-line` / `-ink` | `#e2f5e9` / `#bfe3cc` / `#157a43` | derived | Elements l.62 |
| fonts | `'IBM Plex Sans'` / `'IBM Plex Mono'` | same | 91, 148, and every `font-family` in the markup |

Board tokens with **no home in the 60-token set**, listed so the loss is explicit:
`--sc-hi-bg`/`--sc-hi`/`--sc-mid-bg`/`--sc-mid`/`--sc-lo-bg`/`--sc-lo`/`--sc-none-bg`/`--sc-none`
(l.96 — the eight score-pill tone pairs that replace the ScoreRing), `--ai`/`--ai-ink`
(`#7b3ff2` / `#a375f5`, a dedicated violet for LLM actions, l.98/103), `--paper`.
`--sc-*` maps only approximately onto `--ring-*-border` / `--ring-*-ink` / `--tag-*`;
`--ai` has no counterpart at all (v2 draws Tailor on `--accent`).

Derived, not on the board (the 60-token set is wider than the board's): `--line-strong`,
`--ink-2`, `--change-soft`, `--change-bg`, `--hover-soft`, `--ring-accent`, `--scrim`,
`--recessed`, the five `--stage-*`, `--series-new`, the four `--amber-*`, `--sand`,
`--gold`, `--funnel-low`, `--funnel-mid`, `--bad-faint`, `--toast-bad-*`. `--stage-applied`
moves off blue to a deep teal `#0b5570` / `#6fc3dd` because the board's accent *is* the
blue the default gives to `applied` — the same move the `alt` skin makes for its indigo.

### What the skin reproduces

The whole colour identity: the cool grey ladder, the cobalt accent and its `#e7edfd`
wash, the green/amber/red state trio, the near-black rail with a periwinkle
`#7f9cf5` badge ink, and both modes exactly as drawn. Type identity: IBM Plex Sans in the
display *and* body slot (the board swaps the Editorial serif out entirely — `h1` is
`'IBM Plex Sans' 600 30px / -.02em`, l.148) and IBM Plex Mono for numerals and shortcut
hints.

Font loading: the stacks name IBM Plex first and fall back to `'Segoe UI', system-ui` /
`Consolas`. No `<link>` was added to `index.html`, matching the `alt`-skin rule that a
skin switch costs no network request. On a machine without Plex installed, cobalt renders
on Segoe UI / Consolas — the right *weight and width class*, not the right face. Adding
the two Google Fonts families is a one-line change if the tradeoff is later accepted.

### Geometry delta — what the skin cannot reproduce

| # | board detail | board evidence | v2 today | token(s) that would have to become per-skin |
|---|---|---|---|---|
| C1 | Every pill / button / input / select / icon-button is an **8px rounded rect**; the design has no 99px control at all | l.150, 154, 158, 165 (`border-radius:8px` on the Scan button, search box, every filter pill and the picker cells) | `--radius-control:99px` for Pill/Segmented/Chip/Tag/Switch; `--radius-field:6px` for Input/Select | `--radius-control`, `--radius-field`, `--radius-row` |
| C2 | **5px** small radius for menu items, tags, chips, segmented cells | l.155–160 (`border-radius:5px` on every menu row), Elements l.36 (`C.rs = "5px"`) | `--radius-mini:5px` exists but menu items use `--radius-field:6px` and tags `--radius-control:99px` | `--radius-mini`, `--radius-inline`, `--radius-field` |
| C3 | **9px** card / menu / popover panel | l.153, 289 (`border-radius:9px`), Elements l.52 | `--radius-card:9px` ✓ but `--radius-menu:10px`, `--radius-modal:12px` | `--radius-menu`, `--radius-modal` |
| C4 | The **selected row is square** — `background:#eef3fe` + `box-shadow: inset 3px 0 0 var(--accent)`, radius 0, edge to edge | Elements l.48; head preamble repeats it as the cobalt element set | `--row-selected` is a flat `--surface-2` wash on a `--radius-row:7px` box; there is no inset-edge token | `--radius-row`, plus a new `--row-selected-edge` (colour+width) read by `Row` |
| C5 | Primary button carries a **1px coloured drop shadow** `0 1px 2px rgba(45,91,227,.3)`; the picked Segmented tile carries `0 1px 2px rgba(0,0,0,.08)`; focus is `border:1px accent` + `0 0 0 3px accent-soft` | Elements l.39, 57, 44 | Buttons, pills and segmented cells have no shadow at all; focus is a border-colour change (`theme.css` l.828) | new `--btn-shadow`, `--seg-on-shadow`, `--focus-ring-width` — none exist |
| C6 | Menu shadow is `0 8px 24px rgba(22,24,29,.12)` + a `0 0 0 1px rgba(0,0,0,.06)` ring; card border is a `rgba(0,0,0,.08)` **alpha hairline**, not a solid line | l.153 vs the preamble's cobalt rules; Elements l.52 | `--shadow-menu:0 12px 32px rgba(0,0,0,.16)`; `--card-border:var(--line)`, an opaque hex | `--shadow-menu` (already a token — just not per-skin), and `--card-border` would have to accept an alpha, which it can |
| C7 | **ScoreRing is replaced by a score pill**: a 40×44 `6px` rounded rect filled with the score's tone (`--sc-*-bg`), the numeral in Plex **Mono 600 14px** `-.01em`, and an 8.5px uppercase `FIT` sub-label at .7 opacity | l.268 | `ScoreRing` is an SVG arc + a `--font-display` numeral; no fill, no sub-label | not a token change at all — a per-skin branch in `ScoreRing` (`ui.jsx`), plus 8 `--sc-*` tokens |
| C8 | The rail's active item is a **filled `#2c3442` tile**, 5px radius, `margin:0 10px`, `padding:0 12px` | preamble cobalt rule for `border-left: 2px solid var(--rail-accent)` | v2 marks the active item with a 2px left border | `--rail-active` (exists, but is a white alpha deliberately not re-skinned) + a `--radius-rail-item`, plus a `V2App` branch for the margin |
| C9 | A **new `ai` Button variant** (violet `#7b3ff2`, `✦` glyph) for every LLM action, and a **new ATS notice component** (`#fbf2d7` fill, `#ecd9a0` border, `#7a5a06` ink, 8px, violet CTA) | Elements l.39, l.60 | Neither exists; Tailor is a normal primary button; ATS advice is inline text | new primitives + `--ai` / `--ai-ink` tokens |
| C10 | Uppercase micro-labels track at `.06em`; the rail section labels at `.16em` | preamble; l.113, 121 | v2 writes `.12em` on micro-labels | not tokenised (letter-spacing is inline in `ui.jsx`) |
| C11 | The score numeral is **mono**, not the display face | l.268 | `ScoreRing` reads `--font-display` | needs `--font-display` re-pointed per skin — a *semantic* token, which a skin block may not set |
| C12 | Board's `--surface-2` is used at two values: `#f7f8fa` for flat hovers, `#eef0f3` for anything rounded (chips, the Segmented track, the meter track) | preamble rule `[style*="background: var(--surface-2)"][style*="border-radius"] { background:#eef0f3 }`; Elements `C.s2 = "#eef0f3"` | one `--surface-2` for both | a third ground token (`--surface-3` / `--track-2`), which would break the 60-token parity gate |

**Work to close it.** C1–C3 + C6 are the cheap half: move `--radius-*` (10 tokens) and
`--shadow-*` (5) out of the two base blocks into every skin block — mechanical, no JSX
change, **~2 h** — but it invalidates the `stylecrawl.py` + `stylediff.py` invariant
("only colours, fonts and prose heights may differ"), which has to be widened first, and
that gate is the point of the D6 pass. C5 + C8 need three or four new tokens read by
`Button` / `Segmented` / the rail (**~3 h**). C4 and C7 are per-skin branches inside
primitives (**~3 h**). C9 is two new primitives (**~4 h**). C11 and C12 need the skin
contract itself loosened. Realistically **1–1.5 days** for a cobalt that reads like its
board, most of it spent on the gate rewrite rather than the CSS.

---

## 2 · `saas`

**Board name** "SaaS". The board's own note (preamble l.79): *"saas — ModernSaaS + v1:
Inter, 750-weight tight titles, 7px rounded rects instead of pills, chip meta, soft
two-layer card shadows, filled active nav item."* Its palette is the Tailwind gray + blue
ladder; its type is a **pure system stack** — the board loads no webfont for itself
(l.93, l.148: `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, …`).

### Extracted tokens

| token | light | dark | board line |
|---|---|---|---|
| `--bg` | `#f9fafb` | `#111827` | 96 / 101 |
| `--surface` | `#ffffff` | `#1f2937` | 96 / 101 |
| `--surface-2` | `#f3f4f6` | `#273244` | 96 / 101 |
| `--line` | `#e5e7eb` | `#374151` | 96 / 101 |
| `--line-soft` | `#f3f4f6` | `#2c3646` | 96 / 101 |
| `--edge` | `#d1d5db` | `#4b5563` | 96 / 101 |
| `--track` | `#e5e7eb` | `#272b34` | 96 / 101 |
| `--text` | `#111827` | `#f3f4f6` | 97 / 102 |
| `--text-2` | `#4b5563` | `#d1d5db` | 97 / 102 |
| `--muted` | `#6b7280` | `#9ca3af` | 97 / 102 |
| `--accent` | `#1d4ed8` | `#60a5fa` | 97 / 102 |
| `--accent-ink` | `#ffffff` | `#0b1220` | 97 / 102 |
| `--accent-soft` | `#eff6ff` | `#1e3a5f` | 97 / 102 |
| `--good` | `#15803d` | `#4ade80` | 98 / 103 |
| `--warn` | `#b45309` | `#fbbf24` | 98 / 103 |
| `--warn-soft` | `#fffbeb` | `#241d0e` | 98 / 103 |
| `--bad` | `#b91c1c` | `#f87171` | 98 / 103 |
| `--bad-soft` | `#fef2f2` | `#2a1512` | 98 / 103 |
| `--rail` | `#0f172a` | `#0a0c10` | 98 / 103 |
| `--rail-text` | `#cbd5e1` | `#9aa3b2` | 98 / 103 |
| `--rail-dim` | `#94a3b8` | `#6f7684` | 98 / 103 |
| `--rail-accent` | `#93c5fd` | `#93c5fd` | 98 / 103 |
| `--rail-ink` | `#ffffff` | `#ffffff` | 98 / 103 |
| fonts | system sans / `ui-monospace` | same | 93, 148, 165, 267 |

Board tokens with no home: `--shadow-sm` / `--shadow-lg` (l.96/101 — geometry, see S4),
`--ai`/`--ai-ink` (here identical to `--accent`, so nothing is lost), `--paper`.
`--rail-line` (`#1e293b` / `#1a2030`), `--line-strong` and the rest of the derived list
are as for cobalt; `--stage-applied` moves to cyan-800 `#155e75` / `#5ec8dd` for the same
accent-collision reason.

### What the skin reproduces

Everything colour-side: the Tailwind gray-50/white/gray-100 ladder, blue-700 accent on
blue-50, the green-700 / amber-700 / red-700 state trio, slate-900 rail with a blue-300
badge ink, and both modes as drawn. And, unusually, the type identity **completely** — the
board's stacks are `ui-sans-serif, system-ui, …` and `ui-monospace, SFMono-Regular, …`,
which is exactly what the skin ships. This is the only one of the three whose fonts are
byte-identical to the board.

### Geometry delta

| # | board detail | board evidence | v2 today | token(s) that would have to become per-skin |
|---|---|---|---|---|
| S1 | **8px everywhere a control lives** — the board's preamble states it as `border-radius: 99px → 8px` and `6/7/8/9px → 8px`; secondary buttons are 7px, menus 10px | l.81–83; markup l.152, 156, 166 (`border-radius:8px`), l.327 (`7px`), l.164 (`10px`) | `--radius-control:99px` on pills/tags/switch/segmented, `--radius-field:6px`, `--radius-menu:10px` ✓ | `--radius-control`, `--radius-field`, `--radius-row`, `--radius-cell` |
| S2 | **Every bordered control carries a shadow**: `border:1px solid var(--edge)` also gets `0 1px 2px rgba(16,24,40,.06)` | preamble l.84 | Buttons, pills, inputs and selects have no shadow | new `--btn-shadow`, `--pill-shadow`, `--field-shadow` — none exist |
| S3 | Primary button is `font-weight:600` and carries `0 1px 2px rgba(16,24,40,.12)`; uppercase micro-labels are `font-weight:700` at `.06em` | preamble l.86–87; l.331 | Weight and tracking are inline literals in `ui.jsx`; no button shadow | not tokenised at all |
| S4 | **Two-layer elevation**: cards `0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)`; menus `0 4px 16px rgba(16,24,40,.08)` **plus** a `0 0 0 1px var(--line)` ring in the same declaration | `--shadow-sm`/`--shadow-lg` l.96; used at l.164, l.306, l.370 | `--shadow-menu` is a single soft layer; cards have no shadow, only a border | `--shadow-menu` / `--shadow-modal` / `--shadow-pop` per skin (they *are* tokens, just shared), plus a new `--card-shadow` |
| S5 | The rail's active item is a **filled accent tile**: `background:var(--accent); color:#fff; border-radius:8px; margin:0 10px; padding:0 12px; font-size:13px; font-weight:500` — and the inactive rows stay at 14px | preamble l.88; l.150 | 2px left-border mark, 14px, no fill, full-bleed | `--rail-active` + a `--radius-rail-item` + a `V2App` branch |
| S6 | The selected list row is an `--accent-soft` wash | preamble l.89 | `--row-selected` = `--surface-2` (a neutral wash) | `--row-selected` is a *semantic* token; a skin may not re-point it |
| S7 | **ScoreRing is replaced by a numeral + mini bar**: 16px mono 600 tabular numeral over a 32×3px, 2px-radius track filled to the score | l.266–268 | SVG arc ring, 34/44px box, display-face numeral | per-skin branch in `ScoreRing` (`ui.jsx`), not a token |
| S8 | Detail-head "Tailor" button is `background:var(--ai)`, which the board sets equal to `--accent` — so v2 matches by accident, but the *concept* of an LLM colour slot is absent | l.334 | Tailor is a normal primary button | `--ai` / `--ai-ink` |

**Work to close it.** S1 + S4 are the per-skin `--radius-*` / `--shadow-*` move again
(**~2 h** plus the gate rewrite). S2 + S3 need three shadow tokens and two weight/tracking
tokens read by `Button`, `Pill`, `Input`, `Select`, `SectionHead` (**~4 h**). S5 is a rail
branch (**~1 h**), S7 a `ScoreRing` branch (**~2 h**), S6 needs the skin contract widened
to allow semantic re-pointing. Roughly **1 day** for a saas that reads like its board —
the cheapest of the three, because its palette and fonts already land exactly and only
the elevation regime is missing.

---

## 3 · `win98`

**Board name** "Win98". The most divergent board in the set and the clearest
demonstration of where the skin layer stops: almost everything that makes it Windows 98
is border geometry, not colour.

### Extracted tokens

| token | light | dark | board line |
|---|---|---|---|
| `--bg` | `#008080` (desktop teal) | `#1f2b3a` (desktop navy) | 96 / 101 |
| `--surface` | `#c0c0c0` (window chrome) | `#c0c0c0` | 96 / 101 |
| `--surface-2` | `#ffffff` (client area) | `#ffffff` | 96 / 101 |
| `--line` | `#808080` | `#808080` | 96 / 101 |
| `--line-soft` | `#a0a0a0` | `#a0a0a0` | 96 / 101 |
| `--edge` | `#404040` | `#404040` | 96 / 101 |
| `--track` | `#808080` | `#808080` | 96 / 101 |
| `--text` / `--text-2` | `#000000` | `#000000` | 97 / 102 |
| `--muted` | `#404040` | `#404040` | 97 / 102 |
| `--accent` | `#000080` | `#2b3a5c` | 97 / 102 |
| `--accent-ink` | `#ffffff` | `#ffffff` | 97 / 102 |
| `--accent-soft` | `#c0c0c0` | `#c0c0c0` | 97 / 102 |
| `--good` | `#008000` → shipped `#006000` | `#006400` | 98 / 103 |
| `--warn` | `#808000` → shipped `#575700` | `#7a5a00` | 98 / 103 |
| `--warn-soft` | `#ffffcc` | `#ffffcc` | 98 / 103 |
| `--bad` | `#800000` | `#800000` | 98 / 103 |
| `--bad-soft` | `#ffd0d0` | `#ffd0d0` | 98 / 103 |
| `--rail` | `#c0c0c0` | `#c0c0c0` | 98 / 103 |
| `--rail-text` / `--rail-ink` | `#000000` | `#000000` | 98 / 103 |
| `--rail-dim` | `#404040` | `#404040` | 98 / 103 |
| `--rail-accent` | `#000080` | `#2b3a5c` | 98 / 103 |
| fonts | Tahoma / `'Lucida Console'` | same | 93, 108, 148, 267 |

Note the inversion: `--surface` (`#c0c0c0`) is **darker** than `--surface-2`
(`#ffffff`). That is exactly how the era worked — grey chrome, white client area — and it
maps onto v2 without a fight: row hover, input fill, tag ground and the recessed head all
become white against a grey pane, which is correct.

Board tokens with no home: `--title` / `--title-2` / `--title-ink` (the title-bar
gradient, `#000080`→`#1084d0` light, `#2b3a5c`→`#4a6a99` dark, l.96/101), `--sel` /
`--sel-ink` (the navy selection, l.96/101), `--ai` / `--ai-ink` (`#800080` / `#5c2d7a`),
`--paper`. `--sel` is the biggest loss: in v2 the selected row falls back to
`--row-selected` = `--surface-2` = white, where the board wants navy-on-white-text.

Dark mode on this board is a **wallpaper change only** — bg, the title gradient, the
selection navy, the accent, `--good` and `--warn` move; the entire chrome stays `#c0c0c0`
with black ink. Reproduced as drawn, including the consequence recorded in the contrast
section.

### What the skin reproduces

The VGA palette: teal desktop, `#c0c0c0` chrome, white client area, `#808080` /
`#404040` shadow greys, navy accent, and the four system colours (green / olive /
maroon / the `#ffffcc` and `#ffd0d0` tints). And the type identity exactly: Tahoma with
`'MS Sans Serif'` and Verdana behind it, and Lucida Console for numerals — all system
faces, so no request is added.

Sitting in the app it reads as **a grey-and-teal recolour of the current v2 shape
language**: rounded pills, hairline borders, soft shadows, 30px page titles. Everything
below is why.

### Geometry delta

| # | board detail | board evidence | v2 today | token(s) that would have to become per-skin |
|---|---|---|---|---|
| W1 | **Radius 0 on every element.** Rows, panes, menus, buttons, pills, inputs, tags, badges, the bulk bar, the grab handle — all `border-radius:0` | l.134–136, 154, 158, 262, 279, 291, 304, 331 | the whole `--radius-*` ladder, 3px → 12px, plus `--radius-control:99px` | all 10 `--radius-*` tokens |
| W2 | **2px bevel borders**, not 1px lines: raised is `border:2px solid; border-color:#ffffff #404040 #404040 #ffffff` + `box-shadow: inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080`; inset (list panes, the client area) flips to `#808080 #ffffff #ffffff #808080` + `inset 1px 1px 0 #404040, inset -1px -1px 0 #dfdfdf` | raised: l.106 (rail), 154, 235–241, 304, 331; inset: l.245, 320 | every primitive writes `border: '1px solid var(--x)'` inline — ~40 sites in `ui.jsx` — and a single border colour | new `--bw-control` / `--bw-panel` widths **and** a four-colour `--bevel-raised` / `--bevel-inset` family with the paired inset shadow. Not expressible as one colour token: a bevel needs 4 border colours + 2 inset shadows **per state** (raised at rest, inset when pressed), and the primitives model no such state |
| W3 | **Hard offset shadows, no blur**: every menu and popover is `box-shadow: 3px 3px 0 rgba(0,0,0,.5)` | l.155, 159, 166, 291, 305 | `--shadow-menu:0 12px 32px rgba(0,0,0,.16)` etc. — five soft, blurred tokens | the five `--shadow-*` (they are tokens; just shared) |
| W4 | **11–12.5px system type scale**, and a **12px page title inside a 22px title bar** instead of a 30px `PageTitle`: `h1` is `Tahoma 700 12px` on a `linear-gradient(90deg,var(--title),var(--title-2))` strip with `_ □ ×` window buttons | l.146–149 vs cobalt/saas l.146–148 (`padding:22px 30px 16px`, `font-size:30px`) | `--t-30` `PageTitle` in a 22px-padded header, `--t-12-5` body | all 21 `--t-*` tokens — **and even then this is not a type change but a layout change**: the title bar, its gradient and its three window buttons are a different composition, not a smaller font |
| W5 | **`2px groove` dividers** instead of 1px lines (`border-top:2px groove #dfdfdf` under the rail, `border-bottom:2px groove #dfdfdf` under the toolbar) | l.134, 152 | `--head-line` etc. are 1px solid | a `--divider-style` (width + style) family; `groove` also needs the border to be 2px, i.e. W2 |
| W6 | List rows separate with **1px dotted `#808080`**, not a solid hairline | l.262 | `--row-line` is 1px solid `--line-soft` | a `--row-line-style` token |
| W7 | **Floating windows**: the rail is `margin:12px 0 12px 12px` and the two panes `margin:6px …`, so the teal desktop shows between them | l.106, 245, 320 | panes are full-bleed and share edges | not a token: a `V2App` / screen layout branch |
| W8 | **ScoreRing is replaced by text**: a 64px column with a `Lucida Console 700 13px` numeral above a **9px ASCII bar glyph** (`job.bar`) — a text-mode meter, no SVG | l.264–267 | SVG arc + display-face numeral | per-skin branch in `ScoreRing`, plus data (`job.bar`) the app does not compute |
| W9 | **The rail is light** (`#c0c0c0` with black ink), so `--rail-active`, `--rail-hover` and the three `--on-rail-*` white alphas — which the skin contract deliberately does *not* re-skin, because they are "white alphas that work on any dark rail" — all but vanish | l.106 | those five tokens live in the base block | they would have to join the per-skin set (a 65-token contract) |
| W10 | Uppercase micro-labels are **sentence case at `letter-spacing:0`, weight 700** — the board strips the tracking everywhere | l.117, 122, 128, 337 | `.12em` uppercase micro-labels, inline in `ui.jsx` | not tokenised |
| W11 | Buttons are `font-weight:700` at 11–13px with 12–14px padding; the `Scan` button is 23px tall, not 36px | l.151, 331–332 | 30/36px heights, weight 500 | control heights are inline literals in `ui.jsx` |
| W12 | Selection is `--sel` navy with white ink (`#000080` / `#ffffff`) | l.96 | `--row-selected` = `--surface-2`, ink unchanged | `--row-selected` + a `--row-selected-ink`, both semantic |

**Work to close it.** W1 + W3 are the same per-skin `--radius-*` / `--shadow-*` move
(**~2 h** + the gate rewrite). W5 + W6 add two style tokens (**~1 h**). W2 is the real
cost: a bevel is four border colours plus two inset shadows *per raised/inset state*, so
it needs a new token family **and** a raised/pressed state model threaded through ~15
primitives — **1–2 days**. W4 as a font-scale change is mechanical (21 tokens, ~2 h) but
does not get the title bar; the title bar, window buttons and floating panes (W4 + W7)
are a different shell — **2–3 days**. W8 is a `ScoreRing` branch plus a new derived field
(**~3 h**). W9 needs the token contract widened to 65. W12 needs semantic re-pointing.
Total for a win98 that reads like its board: **≈ 1 week**, and by the end roughly half
the "skin" would live in `ui.jsx`, not in `theme.css` — which is the argument for keeping
it a palette skin and labelling it honestly in the Skin help line.

---

## Summary: what would have to move to support all three

| what | tokens | exists today? | where it lives now |
|---|---|---|---|
| radii | `--radius-mark` `-inline` `-mini` `-field` `-row` `-cell` `-card` `-menu` `-modal` `-control` (10) | yes, as shared tokens | the two base `.jn-v2` blocks — move into every skin block |
| shadows | `--shadow-modal` `-menu` `-pop` `-toast` `-drawer` (5) | yes, as shared tokens | same |
| type scale | `--t-7-5` … `--t-30` (21) | yes, as shared tokens | same |
| border widths | `--bw-hair` `--bw-control` `--bw-panel` | **no** | `border: '1px solid …'` inline at ~40 sites in `ui.jsx` |
| bevels | `--bevel-raised` `--bevel-inset` (4 colours + 2 inset shadows each) | **no** | nothing comparable exists |
| control shadows | `--btn-shadow` `--pill-shadow` `--field-shadow` `--card-shadow` `--seg-on-shadow` | **no** | these elements draw no shadow |
| divider style | `--divider-width` `--divider-style` `--row-line-style` | **no** | 1px solid, inline |
| weights + tracking | `--btn-weight` `--label-tracking` `--label-case` | **no** | inline literals in `ui.jsx` |
| semantic re-pointing per skin (`--row-selected`, `--head-bg-page`, `--chip-bg`, `--font-display`) | — | forbidden by the skin contract | the semantic layer, shared |
| primitive variants (score pill / score bar / ASCII meter, rail active tile, `ai` button, ATS notice) | — | **no** | `ui.jsx` — a per-skin branch, not CSS |

Moving the first three rows (36 tokens) is a couple of hours of mechanical editing and
buys most of cobalt and saas. It also ends the D6 guarantee that a skin switch changes
colour and font family *and nothing else*, and with it the `stylecrawl.py` +
`stylediff.py` invariant — which is a design decision, not an implementation one, and is
why nothing below the third row was attempted here.

**Status**: needs decision — ship the three as palette+font skins (done, gates green), or
widen the skin contract to carry radii, shadows and the type scale.
