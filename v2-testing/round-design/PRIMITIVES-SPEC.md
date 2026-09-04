# v2 primitive parameter sheet

Transcribed from the code as it is at **branch `v2-redesign`, HEAD `539da1e`** (tree clean), 2026-09-04.
Machine-readable twin: [`PRIMITIVES-SPEC.json`](./PRIMITIVES-SPEC.json).

Every value below is quoted from source. Nothing is inferred or proposed. Where the code leaves
something undefined, the cell reads **unspecified**.

---

## A. Global

### A.1 Provenance

| File | Last commit touching it | Lines |
|---|---|---|
| `frontend/src/v2/ui.jsx` | `539da1e` | 1425 |
| `frontend/src/v2/theme.css` | `539da1e` | 1033 |
| `frontend/src/v2/Toast.jsx` | `6010959` | 96 |
| `frontend/src/v2/ConfirmDialog.jsx` | `5ace038` | 51 |
| `frontend/src/v2/hooks.js` | `aac3a45` | 217 |
| `frontend/src/v2/theme.js` | `539da1e` | 178 |
| `frontend/index.html` | `539da1e` | 76 |

`ui.jsx` exports 46 names (45 components + `kb` + `scoreTone`). **There is no `MenuLabel`** — the
menu caption row is `MenuHead` (ui.jsx:491).

### A.2 The two recorded decisions (verbatim)

> skins may set radius/shadow/border-width: yes — geometry tokens become per-skin, the skin proof becomes "only tokens may differ"

> new tokens/variants: allowed as additions defaulting to today's values

### A.3 Token layers

`theme.css` has two layers:

1. a **palette** block of literal colours and font stacks, repeated per theme and per skin;
2. a **semantic** block whose every value is `var(--palette-token)`.

Primitives read semantic names only; a skin replaces the palette block wholesale. `theme.css` and
`ui.jsx` are the only two files where a literal is allowed (`v2-testing/tools/stylelint.py` enforces it).

- **308** distinct token names are defined in `theme.css`.
- The light semantic block (`.jn-v2`) and the dark one (`.jn-v2[data-theme="dark"]`) are **byte-identical today**. The duplication exists so a future skin can re-point a semantic token at a *different* palette token per theme.

### A.4 Semantic tokens read by the primitive layer — 182 distinct names

Deduped `var(--x)` in `ui.jsx` + `Toast.jsx` + `ConfirmDialog.jsx`. `--ring-shift-sm` / `--ring-shift-md`
are read through a template literal (`var(--ring-shift-${…})`, ui.jsx:962), so a plain grep only shows
the stem.

| Family | Tokens |
|---|---|
| type | `--font-body` `--font-display` `--font-mono` · `--t-7-5` `--t-9` `--t-9-5` `--t-10` `--t-10-5` `--t-11` `--t-11-5` `--t-12` `--t-12-5` `--t-13` `--t-13-5` `--t-14` `--t-15` `--t-15-5` `--t-16` `--t-17` `--t-18` `--t-19` `--t-22` `--t-30` |
| radii | `--radius-inline` `--radius-mini` `--radius-field` `--radius-row` `--radius-cell` `--radius-card` `--radius-menu` `--radius-modal` `--radius-control` |
| buttons | `--btn-primary-bg` `--btn-primary-ink` `--btn-primary-disabled-bg` `--btn-primary-disabled-ink` `--btn-danger-bg` `--btn-danger-ink` `--btn-secondary-bg` `--btn-secondary-ink` `--btn-secondary-border` `--btn-secondary-disabled-ink` `--btn-secondary-disabled-border` `--btn-ghost-ink` |
| pills / icon buttons | `--pill-bg` `--pill-ink` `--pill-border` `--pill-on-bg` `--pill-on-ink` `--pill-on-border` `--icon-btn-ink` |
| fields | `--input-bg` `--input-border` `--input-border-focus` `--input-ink` `--input-placeholder` `--input-underline` `--search-bg` `--search-glyph` |
| rows | `--row-selected` `--row-line` |
| cards | `--card-bg` `--card-border` `--band-border` `--dashadd-ink` `--dashadd-border` |
| menus | `--menu-bg` `--menu-border` `--menu-shadow` `--menu-item-ink` `--menu-item-on-bg` `--menu-item-on-ink` `--menu-item-danger-ink` `--menu-item-sep` |
| check / switch | `--check-bg` `--check-border` `--check-on-bg` `--check-on-ink` `--check-label-ink` · `--switch-track-on` `--switch-track-off` `--switch-knob-on` `--switch-knob-off` |
| segmented | `--seg-bg` `--seg-ink` `--seg-border` `--seg-on-bg` `--seg-on-ink` `--seg-on-border` `--seg-on-bad-bg` `--seg-on-bad-ink` `--seg-on-bad-border` `--seg-inset-bg` `--seg-inset-ink` |
| choice | `--choice-bg` `--choice-ink` `--choice-border` `--choice-on-bg` `--choice-on-ink` `--choice-on-border` |
| meter | `--meter-track` `--meter-accent` `--meter-good` `--meter-warn` `--meter-bad` `--meter-neutral` |
| ring | `--ring-track` + `--ring-{good,warn,bad,accent,neutral}-{border,ink,bg}` + `--ring-shift-sm` `--ring-shift-md` `--ring-label-shift` |
| toasts | `--toast-{progress,ok,bad,undo}-{bg,line,ink}` · `--shadow-toast` |
| tags / dots | `--tag-{neutral,accent,good,warn,bad}-{bg,ink}` · `--dot-{neutral,accent,good,warn,bad}` |
| chips | `--chip-bg` `--chip-ink` `--chip-border` |
| overlays | `--scrim-bg` `--modal-bg` `--modal-border` `--modal-shadow` `--drawer-bg` `--drawer-border` `--drawer-shadow` |
| structure | `--head-line` `--head-line-soft` `--head-line-strong` `--head-bg` `--head-bg-page` `--head-bg-recessed` `--section-head-ink` |
| text roles | `--label-ink` `--helper-ink` `--heading-ink` `--link-ink` `--navlink-ink` `--spinner-ink` |
| **palette leaks** | `--bg` (TableHead) · `--surface-2` (Surface) · `--accent` `--bad` `--accent-ink` `--rail-accent` (Toast.jsx) · `--muted` (ConfirmDialog.jsx) |

The last row breaks the layer's own rule ("Primitives read semantic tokens only; they never read a
palette token directly", ui.jsx:40).

**Hover paint lives in CSS, not in JSX.** Inline styles cannot express `:hover`, so every hover swap
is a `.v2-*` class in `theme.css` using `!important` to beat the primitive's inline declaration.
These tokens are therefore read by `theme.css`, never by `ui.jsx`:
`--row-hover` `--pill-border-hover` `--pill-ink-hover` `--card-border-hover` `--card-bg-hover`
`--chip-border-hover` `--chip-bg-hover` `--chip-ink-hover` `--chip-ring-hover`
`--dashadd-border-hover` `--dashadd-bg-hover` `--dashadd-ink-hover` `--menu-item-hover`
`--hover-wash-bg` `--hover-wash-ink` `--hover-bad-bg` `--hover-bad-ink` `--navlink-hover-bg`
`--navlink-hover-ink` `--link-ink-hover` `--anchor-ink-hover` `--focus-ring`.

### A.5 Dead tokens

**None.** All 308 defined names are live — read by a painting declaration, by JS, or (transitively)
by another live token's value.

Seven are **alias-only**: live, but never read directly by a paint rule or by any JS — they exist
only to feed one other token. These are the flattening candidates.

| Token | Feeds |
|---|---|
| `--track` | `--ring-track` |
| `--ring-accent` | `--chip-ring-hover`, `--focus-ring` |
| `--scrim` | `--scrim-bg` |
| `--shadow-modal` | `--modal-shadow` |
| `--shadow-menu` | `--menu-shadow` |
| `--shadow-drawer` | `--drawer-shadow` |
| `--knob` | `--switch-knob-off` |

Nine tokens have exactly one consumer: `--shadow-pop` (JobFeed:1036), `--faint` (Resumes:143,203 —
a back-compat alias for `--muted`), `--radius-mark` (ResumeEditor:917,921), `--iframe-bg`
(JobFeed:1438,1449), `--ink-2` (JobFeed:1113), `--bad-faint` (Searches:843), `--t-16` / `--t-17`
(ui.jsx Heading-strong), `--t-7-5` (ui.jsx ScoreRing sm unscored).

### A.6 Type scale

| Token | Value | | Token | Value |
|---|---|---|---|---|
| `--t-7-5` | 7.5px | | `--t-13` | 13px |
| `--t-9` | 9px | | `--t-13-5` | 13.5px |
| `--t-9-5` | 9.5px | | `--t-14` | 14px |
| `--t-10` | 10px | | `--t-15` | 15px |
| `--t-10-5` | 10.5px | | `--t-15-5` | 15.5px |
| `--t-11` | 11px | | `--t-16` | 16px |
| `--t-11-5` | 11.5px | | `--t-17` | 17px |
| `--t-12` | 12px | | `--t-18` | 18px |
| `--t-12-5` | 12.5px | | `--t-19` | 19px |
| | | | `--t-22` | 22px |
| | | | `--t-30` | 30px |

Root: `.jn-v2 { font-family: var(--sans); color: var(--text); background: var(--bg);
-webkit-font-smoothing: antialiased; font-size: 14px; }`.
Root line-height is **unspecified** — inherited from the v1 shell's Tailwind preflight (1.5).
`.v2-ctl { line-height: 1 }` is the opt-out that every fixed-height control carries.

Font stacks (default skin): `--serif: 'Newsreader',Georgia,serif` · `--sans: 'Public
Sans',system-ui,sans-serif` · `--mono: 'JetBrains Mono',ui-monospace,monospace`. Only these three are
loaded as webfonts (index.html:13); every other skin uses system fallbacks.

### A.7 Radius scale

| Token | Value | Role (from theme.css:96-104) |
|---|---|---|
| `--radius-mark` | 3px | inline diff highlight behind running text |
| `--radius-inline` | 4px | inline mono chip, the 14-16px tick box |
| `--radius-mini` | 5px | the 17-22px square control (checkbox, paragraph button, funnel bar) |
| `--radius-field` | 6px | |
| `--radius-row` | 7px | |
| `--radius-cell` | 8px | the pick cell / small panel between the row and the card |
| `--radius-card` | 9px | |
| `--radius-menu` | 10px | |
| `--radius-modal` | 12px | |
| `--radius-control` | 99px | pill / full |

### A.8 Shadow scale

| Token | Light | Dark |
|---|---|---|
| `--shadow-modal` | `0 18px 50px rgba(0,0,0,.28)` | `0 18px 50px rgba(0,0,0,.6)` |
| `--shadow-menu` | `0 12px 32px rgba(0,0,0,.16)` | `0 12px 32px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.04)` |
| `--shadow-pop` | `0 10px 30px rgba(0,0,0,.28)` | `0 10px 30px rgba(0,0,0,.6)` |
| `--shadow-toast` | `0 8px 24px rgba(20,19,15,.18)` | `0 8px 24px rgba(0,0,0,.5)` |
| `--shadow-drawer` | `-14px 0 40px rgba(0,0,0,.14)` | `-14px 0 40px rgba(0,0,0,.45)` |

The `--shadow-*` family is deliberately excluded from every skin block: *"black alphas, already
theme-neutral — and their offsets are part of the geometry the gate pins."*

### A.9 z-index layers

There is **no named z-index scale**; every value is a literal, most of them at a call site.

| Layer | Value | Owner |
|---|---|---|
| sticky TableHead in a modal | 2 | Companies:984, Searches:830 |
| sticky TableHead on a page | 3 | Companies:473 |
| Feed detail header block | 18 | JobFeed:1244 |
| Feed grab-line strip · Settings typeahead | 20 | JobFeed:1169, Settings:1054 |
| ResumeEditor template/paper pickers | 21 | ResumeEditor:675,685 |
| Feed floating multi-select bar | 25 | JobFeed:1036 |
| **Drawer scrim** | **29** | `ui.jsx:1103` |
| **Drawer panel** | **30** | `ui.jsx:1108` |
| Feed shortcuts backdrop / panel | 34 / 35 | JobFeed:1018-1019 |
| popover click-away backdrop | 39 | CoverLetters:66, Stats:721 |
| **Select listbox** · row-action Menus | **40** | `ui.jsx:378`, Applications:58, Companies:557, Searches:678, Stats:722 |
| header-menu backdrop / Menu | 44 / 45 | JobFeed:123-124,1218-1219, ResumeEditor:599-600,633-634, Companies:456 |
| CoverLetterEditor letter menu | 50 | CoverLetterEditor:383 |
| Feed row-menu backdrop | 59 | JobFeed:1139 |
| **ChoiceModal** and every screen modal | **60** | `ui.jsx:1396` + 12 screen sites |
| **ModalPanel default** (ConfirmDialog, PromptDialog) | **70** | `ui.jsx:1075` |
| **ToastStack** | **80** | `Toast.jsx:92` |
| WelcomeModal | 9998 | WelcomeModal:32 |
| LoginModal | 9999 | LoginModal:50 |

> "z-index 80 is what puts a toast over an open modal (70) and drawer (30)." (Toast.jsx:89)

ConfirmDialog sits at 70 alongside the modal it is raised from and relies on DOM order: *"it mounts
last in the tree, and equal z-index resolves in DOM order."*

### A.10 Hairline model

| Width | Occurrences across `frontend/src/v2/*.jsx` |
|---|---|
| `1px solid` | 135 |
| `1px dashed` | 7 |
| `2px solid` | 5 |
| `1px dotted` | 5 |
| `3px solid` | 2 |
| `8.5px dashed` | 1 (JobFeed:1096, the micro-badge) |

**There is no 0.5px border anywhere in v2.** The only sub-pixel border in the primitive layer is the
Spinner's `1.5px` band (ui.jsx:87; `weight="bold"` → `2px`). The `borderWidth` shorthand property is
never used — every border is written as the `border` / `borderTop…` shorthand string. There is **no
border-width token of any kind**.

Half-pixel avoidance is a stated rule, enforced two ways: line-heights are pinned to whole pixels
(Heading-strong table, ui.jsx:1258-1265) and `useSnapTop` (hooks.js:60-83) measures a flex-centred
modal panel after layout and applies `translateY(round(top) - top)` so every 1px border inside lands
on a device row.

Non-border 2-3px paint: the focus ring `0 0 0 2px`, the chip halo `0 0 0 2px`, the scroll thumb's
`2px solid var(--bg)` inset, and the grab handle's `0 0 0 3px var(--surface)` ring.

### A.11 Focus recipe

**Fields** (theme.css:1018):
```css
.jn-v2 input:focus-visible, .jn-v2 textarea:focus-visible, .jn-v2 select:focus-visible {
  border-color: var(--input-border-focus) !important; outline: none;
}
```
> "The 2px ring is gone: browsers apply `:focus-visible` to text inputs on *mouse* focus too, so every
> click drew a rectangle… A field now signals focus the way it draws itself at rest: a bordered box
> turns its border accent, an underline input turns its underline accent."

**Composite fields** (theme.css:1021) — 13 sites use `v2-fieldwrap`:
```css
.jn-v2 .v2-fieldwrap:focus-within { border-color: var(--input-border-focus) !important; }
```

**Keyboard ring, every other control** (theme.css:1024):
```css
.jn-v2 [tabindex="0"]:focus-visible { outline: none; box-shadow: 0 0 0 2px var(--focus-ring); }
```
`--focus-ring` = `var(--ring-accent)` = light `rgba(63,107,82,.22)` / dark `rgba(141,187,159,.24)`.
Because the selector keys on `[tabindex="0"]`, any control that `act()` has switched to `tabIndex -1`
(every disabled or busy primitive) **loses the ring while remaining focusable**.

**Focus trap: unspecified.** No primitive traps focus, sets initial focus or restores it on close.
`ModalPanel` and `Drawer` wire Escape and a scrim click, and nothing else.

### A.12 Keyboard helper

```js
export const kb = (fn, role = 'button') => ({
  tabIndex: 0, role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})
const act = (fn, off, role) => (
  fn ? (off ? { role: role || 'button', tabIndex: -1 } : { onClick: fn, ...kb(fn, role) }) : {}
)
```
`kb` is re-declared (not imported) in `ResumeSections.jsx` and `Settings.jsx` "so `ui.jsx` stays a leaf
of the v2 import graph." `act()` hands back **nothing** when there is no handler — an inert Card is not
a button — and for a disabled control keeps the role and drops only the interactivity (DS-B-01).

### A.13 Disabled recipe, per primitive

There is **no single disabled token**. Six treatments are in use.

| Treatment | Primitives |
|---|---|
| token swap, **no dim** | Button (`--btn-*-disabled-*`) |
| `opacity 0.6` | Input, Textarea, Select · *and* a **busy** Button (`busy && !disabled ? 0.6 : 1`) |
| `opacity 0.5` | Pill, IconButton, Chip, DashedAdd, MenuItem, Check, Radio, Switch, Segmented |
| `opacity 0.45` | ChoiceCard, ChoiceRow |
| `opacity 0.35` | MoveArrows (per arrow, `upOff`/`downOff`) |
| **no `disabled` prop at all** | Row, Card, Band, Tag, Dot, Meter, ScoreRing, Spinner, Rule, Surface, Label, Helper, Heading, PageTitle, HeaderRow, TableHead, ShowMore, Link, NavLink, RemoveX, RemoveLink, ToastCard, Menu, MenuHead, SectionHead, SearchInput, ModalPanel, Drawer, ChoiceModal |

In every case the hover class is dropped, `cursor` becomes `default`, `aria-disabled` is set and the
element goes to `tabIndex -1`.

### A.14 Motion

| Duration | Where |
|---|---|
| `.12s` | the standard hover — `.v2-card` `.v2-chip` `.v2-dashadd` `.v2-navlink` `.v2-navdark` `.v2-tab` `.v2-welcomestep` `.v2-grab > span` `.v2-fold` |
| `150ms` | Switch knob (`transition: 'left 150ms'`, ui.jsx:766) |
| `250ms ease` | Toast enter/leave opacity + translateY (Toast.jsx:65) |
| `260ms` | Toast leave-to-unmount timer (Toast.jsx:39) — 10 ms after the transition |
| `.15s` | `useWarm` cross-fade (hooks.js:165) |
| `.2s` | screen-level opacity fades (5 sites) |
| `.32s ease` | rail expand/collapse padding + width (V2App) |
| `.9s linear infinite` | `@keyframes v2-spin` |

**Hover classes with NO transition** (instant swap): `.v2-act` `.v2-bd` `.v2-bdc` `.v2-row` `.v2-crow`
`.v2-arow` `.v2-menuitem` `.v2-hover-accent` `.v2-hover-bad` `.v2-hover-bad-text`
`.v2-hover-accent-text` `.v2-clhead` `.v2-qahead` `.v2-parabtn` `.v2-anchor` `.v2-hover-bad-bdc`.

`prefers-reduced-motion: reduce` covers only `.v2-grab > span` and `.v2-fold` (theme.css:893-896).
The spinner, the Switch knob, the toast animation and the warm-start fade are **not** covered.

### A.15 Theme and skin mechanism

| Axis | Values | Storage key |
|---|---|---|
| `mode` | `light` · `dark` · `system` | `jobnavigator_theme` (legacy boolean `jobnavigator_dark_mode` migrated once) |
| `skin` | `default` `tone1` `tone2` `tone3` `editorial` `alt` `cobalt` `saas` `win98` | `jobnavigator_skin` |

The store is `frontend/src/v2/theme.js` — a `useSyncExternalStore` singleton; nothing reads
localStorage from a component. `system` resolves live through `matchMedia`, and a `storage` event
moves a second tab.

**Attribute hosts.** `<html>` carries `data-theme`, `data-skin` and the classic shell's `.dark`
class, stamped by the inline boot script in `index.html:22-42` *before* React mounts and re-stamped
by `apply()` on every change. Every `.jn-v2` root mirrors the same two attributes through
`themeAttrs()`; `theme.css` selects on the root itself. `<html>` is "the boot copy, not a second
source of truth."

**No-flash boot.** `index.html:51-70` carries one `:root[data-skin=…][data-theme=…] { background: … }`
rule per skin — 18 rules, the only place a palette value is written outside `theme.css`. `:root[…]` is
(0,2,0), which beats `index.css`'s `html.dark` (0,1,1) whatever order Vite emits the stylesheets in.

**What a skin block may contain today.** Two blocks per skin — `.jn-v2[data-skin="X"]` and
`.jn-v2[data-skin="X"][data-theme="dark"]` — each declaring the **identical set of 60 token names**.
Verified programmatically at this commit: all 8 non-default skins × both modes declare exactly the
same 60.

| Group | Count | Names |
|---|---|---|
| ring offsets | 3 | `--ring-shift-sm` `--ring-shift-md` `--ring-label-shift` |
| grounds & lines | 8 | `--bg` `--surface` `--surface-2` `--line` `--line-soft` `--line-strong` `--edge` `--track` |
| ink | 4 | `--text` `--text-2` `--muted` `--ink-2` |
| accent | 3 | `--accent` `--accent-ink` `--accent-soft` |
| states | 8 | `--good` `--warn` `--warn-soft` `--warn-line` `--bad` `--bad-soft` `--bad-faint` `--recessed` |
| diff / hover / overlay | 5 | `--change-soft` `--change-bg` `--hover-soft` `--ring-accent` `--scrim` |
| stages & series | 6 | `--stage-applied` `--stage-interview` `--stage-offer` `--stage-rejected` `--stage-new` `--series-new` |
| amber card | 4 | `--amber-bg` `--amber-line` `--amber-line-soft` `--amber-hover` |
| chart ramp | 4 | `--sand` `--gold` `--funnel-low` `--funnel-mid` |
| toast tints | 6 | `--toast-ok-{bg,line,ink}` `--toast-bad-{bg,line,ink}` |
| rail | 6 | `--rail` `--rail-text` `--rail-dim` `--rail-accent` `--rail-line` `--rail-ink` |
| fonts | 3 | `--serif` `--sans` `--mono` |

> "The two blocks MUST declare the identical set of names. `[data-skin="alt"]` and
> `.jn-v2[data-theme="dark"]` weigh the same (0,2,0), so a token that the light skin block sets and
> the dark one forgets would beat the default dark value and leak a light colour into the dark skin."

**Deliberately not re-skinned:** the `--cc-*` (17 pairs) and `--sm-*` (6 pairs) badge families ("an
identity taxonomy, not theme colour"); the `--shadow-*` family; the on-rail white overlays
`--rail-active` `--rail-hover` `--on-rail-line` `--on-rail-dim` `--on-rail-sep`; and `--knob` /
`--iframe-bg`.

**What a skin cannot express today:** `--radius-*`, `--shadow-*`, `--t-*` and every primitive's border
width live in the shared semantic layer. `theme.css:670-678` records that the cobalt / saas / win98
boards change radii, border widths, bevels, shadows and the type scale, and that "that is the part a
skin cannot express"; `skins-boards.md` lists the delta per board.

**Ring offsets per skin.** Every skin uses `sm 2px / md 1px / label 0px` except `alt`, which is
`sm 1.25px / md .42px / label 1.58px` — "Georgia/Inter metrics: digits sit lower, the small-caps label
higher — pixel-measured against the default skin, see `ring-sizes.md`." The three board skins seed at
the default offsets pending a re-run of the ink measurement.

**Current skin gate:** `expected-D6.md` + `tools/stylecrawl.py` + `stylediff.py` — "switching
`data-skin` may change colour and font family and nothing else."

---

## B. Per primitive

Conventions: token names are written without `var()`. "keyboard ring" means the
`[tabindex="0"]:focus-visible` `box-shadow: 0 0 0 2px var(--focus-ring)` rule. States not listed are
**unspecified**.

### Button — `ui.jsx:97-168`

`div`, or a real `<button type>` with `as="button"` (LoginModal's form submit; UA styles reset with
`margin 0, border none, appearance none, WebkitAppearance none`, `tabIndex` stays 0).

| Variant | rest | disabled | hover class |
|---|---|---|---|
| `primary` | bg `--btn-primary-bg` · ink `--btn-primary-ink` | bg `--btn-primary-disabled-bg` · ink `--btn-primary-disabled-ink` | **none** |
| `danger` | bg `--btn-danger-bg` · ink `--btn-danger-ink` | same as primary's disabled | **none** |
| `secondary` | bg `--btn-secondary-bg` · ink `--btn-secondary-ink` · 1px `--btn-secondary-border` | ink `--btn-secondary-disabled-ink` · 1px `--btn-secondary-disabled-border` | `v2-bdc` |
| `ghost` | transparent · ink `--btn-ghost-ink` | ink `--btn-secondary-disabled-ink` | `v2-hover-accent` |

| Size | height | font | padding |
|---|---|---|---|
| `md` (default) | 36 | `--t-13-5` | `0 18px` |
| `sm` | 33 | `--t-13` | `0 15px` |
| `xs` | 28 | `--t-12-5` | `0 14px` |

Geometry: gap 8 · radius `--radius-control` · `flex 0 0 auto` · flex-centred both axes · min-width **unspecified** · icon size **unspecified** (an icon is just a child glyph).
Type: `--font-body` · weight 500 · `white-space: nowrap` · line-height 1 via `v2-ctl` · letter-spacing / transform unspecified.

| State | Paint |
|---|---|
| hover (secondary) | `.v2-bdc:hover { border-color: var(--pill-border-hover) !important; color: var(--pill-ink-hover) !important }` |
| hover (ghost) | `.v2-hover-accent:hover { background: var(--hover-wash-bg) !important; color: var(--hover-wash-ink) !important }` |
| hover (primary / danger) | **none — identical to rest** |
| active | unspecified |
| disabled | variant `off` tokens, no dim, cursor default, hover class dropped, `aria-disabled`, role kept, `tabIndex -1` |
| busy | as disabled **plus** `opacity 0.6` and a leading `<Spinner size={12} color="currentColor" />`, `aria-busy` |
| focus-visible | keyboard ring — **lost when off** (`tabIndex -1`) |

Motion: none. A11y: role `button` · `aria-label` `aria-expanded` `aria-haspopup` `aria-busy` `aria-disabled` · Enter/Space.
**Known exceptions: zero** — no screen passes geometry or colour into Button.

### Pill — `ui.jsx:173-198`

| Variant | bg | ink | border |
|---|---|---|---|
| off (default) | `--pill-bg` | `--pill-ink` | 1px `--pill-border` |
| `on` | `--pill-on-bg` | `--pill-on-ink` | 1px `--pill-on-border` |

| Size | height | font | padding |
|---|---|---|---|
| `md` | 31 | `--t-12-5` | `0 15px` |
| `sm` | 26 | `--t-11-5` | `0 13px` |

gap 7 · radius `--radius-control` · `--font-body` · nowrap · line-height 1 (`v2-ctl`) · `flex 0 0 auto`.

Hover `.v2-bd:hover { border-color: var(--pill-border-hover) !important }` — **border only, no wash**.
Note: `--pill-on-border` and `--pill-border-hover` both resolve to `--accent`, so **an ON pill has no
visible hover feedback**. Disabled: opacity 0.5. `aria-pressed` is emitted only when `on !== undefined`.
Known exceptions: zero.

### IconButton — `ui.jsx:205-230`

| Size | font | paint | hover class |
|---|---|---|---|
| `26` (default, the bare glyph) | `--t-13` | ink `--icon-btn-ink`, no bg, no border | `v2-hover-accent` |
| `36` (the bordered ⋯ head button) | `--t-15` | off: `--pill-{bg,ink,border}` · on: `--pill-on-{bg,ink,border}` | `v2-act` |

Box = the `size` prop · radius `--radius-control` · flex-centred · `flex 0 0 auto`.
`aria-label` falls back to `title`. Disabled: opacity 0.5.
**Gap:** any size other than 26 or 36 gets the small look at that box — the intermediate is undefined.
Known exceptions: zero (but see the 25×25 and 22×22 hand-drawn ⋯ buttons in §C).

### Input — `ui.jsx:243-261`

Native `<input>`. Shared `FIELD` map: width 100% · minWidth 0 · 1px `--input-border` · radius
`--radius-field` · bg `--input-bg` · ink `--input-ink` · `--font-body` · `--t-12-5` · `outline: none`.
Own: **height 32** · padding `0 9px` · `mono` → `--font-mono` · disabled opacity 0.6.

| State | Paint |
|---|---|
| hover | unspecified |
| focus-visible | `border-color: var(--input-border-focus) !important; outline: none` — **no ring** |
| disabled | opacity 0.6 + native `disabled` |
| readOnly | passes through, **no distinct paint** |
| invalid / error | **unspecified — no token exists** |

Placeholder: `--input-placeholder`, `!important`, `opacity 1`. `defaultValue` (instead of `value`)
renders it uncontrolled. `...rest` forwards any DOM prop.

**Known exceptions (6):** `JobFeed:930` width+paddingLeft · `ResumeSections:213` padding · `ResumeSections:404` fontWeight 500 · `Searches:303` width 110 · `CoverLetterEditor:435` padding. Input has no `width` and no `pad` prop.

### Textarea — `ui.jsx:262-275`

No fixed height. padding `5.5px 9px` · line-height **19px** · `minHeight = rows*19 + 13`
(rows default 3 → 70) · `resize: vertical`. Its single-line basis is
`19 + 2×5.5 + 2×1 = 32` — the same box a one-line Input draws.
Everything else = Input.

**Known exceptions (4):** `Applications:668` minHeight 64 · `Applications:839` minHeight 52 ·
`Settings:934` minHeight 440 + `borderColor: --bad` on error · `ResumeEditor:862` `borderStyle: dashed`.

### SearchInput — `ui.jsx:284-314`

| Variant | height | padding | border | bg | font | glyph |
|---|---|---|---|---|---|---|
| `boxed` (default) | 32 | `0 12px 0 29px` | 1px `--input-border`, radius `--radius-control` | `--search-bg` | `--t-12` | `⌕` at left 12, `--t-12`, `--search-glyph`, aria-hidden, pointer-events none |
| `underline` | 36 | `0 13px` | none; borderBottom 1px `--input-underline` | transparent | `--t-13` | none |

Wrapper: relative flex, minWidth 0, `width = width ?? 226`, `flex: 0 1 auto` — a real `width`, not a
flex-basis, because a bare `<input>`'s intrinsic width (~178px) would otherwise be what a max-content
parent budgets.
No `disabled` prop. `aria-label` falls back to `placeholder` (default `Search…`). Known exceptions: zero.

### Select — `ui.jsx:320-405`

**Trigger:** height 32 · padding `0 10px` · gap 7 · 1px `--input-border` (open → `--input-border-focus`)
· radius `--radius-field` · bg `--input-bg` · ink `--input-ink` · `--t-12-5` · line-height 1 ·
wrapper `flex: 0 1 ${width ?? '220px'}`. Empty value → `--input-placeholder`. `mono` → `--font-mono` at
`--t-11-5`. Caret `▾` at `--t-9` in `--icon-btn-ink`.

**Listbox:** `v2-menu v2-scroll`, absolute `top 100%`, marginTop 4, **z 40**, minWidth 100%, maxWidth
420, maxHeight 320, overflow auto, padding 5, gap 1, radius `--radius-menu`, 1px `--menu-border`, bg
`--menu-bg`, shadow `--menu-shadow`.
**Options:** padding `7px 9px` · radius `--radius-field` · `--t-12-5` · ellipsis · rest
`--menu-item-ink` on transparent · selected `--menu-item-on-ink` on `--menu-item-on-bg` · hover
`.v2-menuitem`.
**Empty:** padding `7px 9px`, `--t-11-5` / 16px, `--helper-ink`, text = `emptyText ?? 'Nothing to pick yet.'`.

Escape is registered in the **capture** phase, only while open, and calls `preventDefault` +
`stopPropagation` so a Select inside a modal does not take the modal down with it. A document click closes.

A11y: trigger role `button` + `aria-haspopup="listbox"` + `aria-expanded`; panel `role="listbox"`;
options `role="option"` + `aria-selected`, each its own tab stop.
**Gaps:** no arrow-key navigation, no typeahead, no `aria-activedescendant`, no `aria-controls`, no
focus move into the panel. Options shape `[[value, label], …]`. Known exceptions: zero.

### Row — `ui.jsx:419-435`

height 46 · padding `0 10px` · gap 10 · radius `--radius-row` (`flush` → 0) · `divider` → borderBottom
1px `--row-line`.

| State | Paint |
|---|---|
| rest | transparent |
| selected | `--row-selected` + `aria-current="true"` |
| hover | `.v2-row:hover { background: var(--row-hover) !important }` |
| selected + hover | `.v2-row[aria-current="true"]:hover { background: var(--row-selected) !important }` |

> "Selection is a **background wash and nothing else**. APPS-20 added a 3px `--row-selected-mark` bar
> with a compensating left pad; Applications never had one… The token went with it."

`cursor: pointer` only when `onClick` is present — an inert row keeps the I-beam. `...rest` carries the
`data-*` hooks the Feed keys its scroll-into-view and harness selectors off.
Sibling classes: `.v2-crow` (Companies), `.v2-arow` (Applications), `.v2-cactions` (the pinned actions cell).
**Known exceptions (2):** `Companies:493` padding `0 30px 0 24px` · `JobFeed:1076` height auto + padding 0 + backgroundColor + a diagonal-hatch `backgroundImage`.

### Card — `ui.jsx:443-459` (forwardRef)

bg `--card-bg` · 1px `--card-border` · radius `--radius-card` · padding `10px 14px`.
`interactive` (or any `onClick`) adds class `v2-act` and `cursor: pointer`; a static card sets **no**
cursor, so its text keeps the I-beam.
Hover `.v2-act:hover { border-color: var(--card-border-hover) !important; background: var(--card-bg-hover) !important }` — **no transition**. The `.v2-card` class has the same paint *with* `transition: border-color .12s, background .12s`, but it is applied by screens, not by the primitive.
`id` and a forwarded ref are zero-pixel pass-throughs.
**Known exceptions (23) — the largest family.** Keys: `padding` (dominant: `0`, `11`, `'16px 20px'`), `height` (Stats' 230/300 chart cards), `borderColor`, `background`, `lineHeight`.
Sites: Applications 580, 631 · CoverLetters 311 · JobFeed 1383 · Persona 406 · ResumeSections 148, 249, 412, 436, 472 · Resumes 182, 201, 217, 264 · Searches 580, 615 · Stats 480, 507, 559, 588, 606, 653, 706.
**Missing parameters:** `pad`, `tone`.

### Band — `ui.jsx:460-470`

1px **dashed** `--band-border` · radius `--radius-card` · padding `10px 14px` · no background.
`interactive` defaults to **true** (unlike Card). Hover `v2-act`.
**Known exceptions (8):** CoverLetters 396 (padding, borderColor `--accent`, background `--recessed`) · Persona 554 · ResumeEditor 776, 856 · ResumeSections 130 · Resumes 169 (borderColor `--bad`, fontSize 12.5, color `--muted`), 180, 199. Missing: `pad`, `tone`.

### DashedAdd — `ui.jsx:475-486`

| Variant | height | font | weight |
|---|---|---|---|
| default | 28 | `--t-11-5` | 400 |
| `big` | 32 | `--t-12` | 500 |

1px dashed `--dashadd-border` · radius `--radius-field` · gap 6 · flex-centred · ink `--dashadd-ink` ·
`--font-body` · line-height 1 · **no padding of its own**.
Hover `.v2-dashadd:hover` moves border → `--dashadd-border-hover`, bg → `--dashadd-bg-hover`, color →
`--dashadd-ink-hover`; the transition list is `border-color .12s, background .12s` — **`color` is
animated by the hover but absent from the transition**.
Disabled: opacity 0.5. **Known exception (1):** `Persona:569` padding `0 11px`.

### Menu — `ui.jsx:509-517`

bg `--menu-bg` · 1px `--menu-border` · radius `--radius-menu` · shadow `--menu-shadow` · padding 5 ·
column · gap 1 · class `v2-menu`.
`.jn-v2 .v2-menu > * { flex-shrink: 0 }` — *"Menu rows are fixed-height by definition; a scrolling menu
scrolls, it never squashes."* (Before it, the Feed's ~1300-company filter squashed its in-menu search
field from 32px to 17.)
Positioning is **entirely the caller's**, passed as `style` with a hand-picked z-index (40/45/50).
`role` prop, default `menu`; `listbox` for an option picker.
**Gaps:** no roving focus, no arrow keys, no focus trap, no return-focus, no Escape of its own — every
row is an independent tab stop and callers hand-roll a click-away backdrop div.
**Known exceptions (6):** JobFeed 124 (maxHeight 360), 1019 (padding 10, overriding Menu's 5) · Applications 368 (maxHeight 340) · CoverLetters 68 via the `POPOVER` const (maxHeight 300) · CoverLetterEditor 524 · ResumeEditor 675.

### MenuHead — `ui.jsx:491-498`

padding `4px 11px 3px` · `--t-9-5` / 14px · `.13em` · uppercase · ink `--label-ink`.
Props: `children`, `style` only. Known exceptions: zero — but `JobFeed:1020` draws its own at 10.5 /
`.12em` / `marginBottom 6` because MenuHead's box does not fit there.

### MenuItem — `ui.jsx:531-579`

`div`, or a real `<a>` when `href` (rel `noreferrer` on `_blank`, `text-decoration: none`) — the one
primitive that keeps ⌘/middle-click.

| Variant | ink | extra |
|---|---|---|
| default | `--menu-item-ink` | hover `v2-menuitem` |
| `selected` | `--menu-item-on-ink` | bg `--menu-item-on-bg`, weight 500 |
| `danger` | `--menu-item-danger-ink` | hover `v2-hover-bad`; `divider` defaults to **true** → borderTop 1px `--menu-item-sep` |

padding `7px 11px` · gap 9 · radius `--radius-field` · `--t-12-5` · line-height inherited.
Slots: `icon` in a fixed **16px** flex gutter at `--t-11` in `--label-ink` (a flex box, not text-align,
because the gutter also holds a 14/15px checkbox) · `children` at `flex 1, minWidth 0` · `hint` as a
trailing `Helper size="xs"` (colour → `inherit` when selected). `ellipsis` truncates the label slot only.
Disabled: opacity 0.5. **Known exception (1):** `Applications:376` color `--muted` + paddingTop 10.

### SectionHead — `ui.jsx:599-632`

| Variant | gap | radius | ink |
|---|---|---|---|
| default | 6 | none | `--section-head-ink` |
| `boxed` | 6 | `--radius-field`, padding `2px 4px` | `--section-head-ink` |
| `card` | 9 | `--radius-card` | **inherited from the card** |

`--t-12-5` / 18px. Caret `⌄` open / `›` closed at `--t-10`, **line-height 1** (without it a 10px glyph in
an 18px box sits at a font-dependent baseline offset and the head grew 36→37px under the alt skin),
ink `--label-ink`, aria-hidden. `caret`: `'start'` (default) · `'end'` · `'pin'` (marginLeft auto) ·
`false`. Rendered only when `onToggle` **and** `caret` are truthy.
`count` appends a `Helper size="xs"`. Hover class from the `hover` prop, default `v2-hover-accent`,
applied only when `onToggle` is present.
**Known exceptions (6)** — padding is documented as intentional ("Its padding is layout and is passed in
`style`"): Applications 422 (+ lineHeight 16px) · CoverLetterEditor 34 (+ `borderRadius: '9px 9px 0 0'`,
**not** documented) · Persona 407, 430 · ResumeSections 149, 254.

### Chip — `ui.jsx:638-650`

height 26 · padding `0 10px` · gap 6 · radius `--radius-control` · bg `--chip-bg` · ink `--chip-ink` ·
1px `--chip-border` · `--font-body` · `--t-11-5` · nowrap · inline-flex · line-height 1.
Hover (only when `onClick && !disabled`):
`.v2-chip:hover { border-color: --chip-border-hover; background: --chip-bg-hover; color: --chip-ink-hover; box-shadow: 0 0 0 2px --chip-ring-hover }` — all `!important`,
with `transition: border-color .12s, background .12s, box-shadow .12s, color .12s`.
Disabled: opacity 0.5. **Known exceptions (3):** Resumes 236, 283 `color: --muted` (+ maxWidth 250 at 241/290).

### Tag — `ui.jsx:657-674`

`span`, never interactive, **no states at all**.
radius `--radius-control` · `--t-10` / 15px · padding `2px 8px` · `.06em` · uppercase · nowrap ·
inline-flex · `flex 0 0 auto`. Font family and weight are **unspecified** (inherited).

| Tone | bg | ink |
|---|---|---|
| `neutral` (default) | `--tag-neutral-bg` | `--tag-neutral-ink` |
| `accent` | `--tag-accent-bg` | `--tag-accent-ink` |
| `good` | `--tag-good-bg` | `--tag-good-ink` |
| `warn` | `--tag-warn-bg` | `--tag-warn-ink` |
| `bad` | `--tag-bad-bg` | `--tag-bad-ink` |
| `none` | — sets no colour at all — | |

`tone="none"` exists so the ATS / search-mode / tier taxonomy can paint from a class: 17 `cc-*` and 6
`sm-*` rules of the shape `.jn-v2 .cc-X { background: var(--cc-X-bg); color: var(--cc-X-fg) }`.
Recipe: *"8 hues, one oklch recipe per mode. light bg L.94/C.03 + ink L.45/C.09 · dark bg L.32/C.05 +
ink L.84/C.07 — all pass AA."* **These families are excluded from every skin.**
Known exceptions: zero on the primitive — but **12 sites draw the Tag role by hand** (see §C).

### Dot — `ui.jsx:675-687`

`size` prop default **7** (a raw px number) · radius `--radius-control` · inline-block · `flex 0 0 auto`.
Tones `--dot-{neutral,accent,good,warn,bad}`. `aria-hidden` unless `title`, in which case `role="img"` +
`aria-label`. No states.
**Known exceptions (3)** — all defeat the `tone` prop by setting `background` directly, because the
`--stage-*` colours are outside DOT_TONE's five names: Applications 423, 678 · Companies 507. Segmented
does the same internally for `dotColor` (ui.jsx:848).

### Check / Radio — `ui.jsx:697-737`

One `Ticker` + `Indicator` pair; `Check` is `round={false}`, `Radio` is `round` with `indeterminate` forced off.

| | Check | Radio |
|---|---|---|
| indicator radius | `--radius-inline` (4px) | `--radius-control` |
| glyph | `✓` U+2713 · `–` U+2013 indeterminate | `●` U+25CF |
| role | `checkbox` | `radio` |
| `aria-checked` | `'mixed'` when indeterminate | `true`/`false` |

Sizes `sm` 14 (default) · `md` 15. Rest: 1px `--check-border` on `--check-bg` (transparent). On/
indeterminate: **no border**, bg `--check-on-bg`, ink `--check-on-ink`, glyph at `--t-9` / line-height 1.
Wrapper: inline-flex, gap 7, `--t-12`, ink `--check-label-ink`, label truncates with ellipsis.
The role is named **even without an `onChange`** ("aria-checked on a role-less span is ignored"); the tab
stop is added only when there is something to click. Disabled: opacity 0.5.
**Hit target 14-15px.** There is no radiogroup wrapper for `Radio` — the caller owns grouping.
Known exceptions: zero.

### Switch — `ui.jsx:743-771`

| Size | track | knob | inset |
|---|---|---|---|
| `md` (default) | 26 × 15 | 11 | 2 |
| `sm` | 22 × 13 | 9 | 2 |

Both radii `--radius-control`. Knob `top = pad`, `left = pad` off / `w - knob - pad` on.
Track `--switch-track-on` / `--switch-track-off`; knob `--switch-knob-on` / `--switch-knob-off`
(*"the ON knob is a surface disc on the accent track so it reads in both themes; OFF keeps `--knob`"*).
`label` renders as a `Helper` **before** the track, gap 7.
Motion: `transition: left 150ms` — **not** covered by the reduced-motion query.
role `switch` · `aria-checked` · disabled opacity 0.5. Known exceptions: zero.

### Segmented — `ui.jsx:791-858`

`role="radiogroup"` of `role="radio"` cells.

| Size | height | font |
|---|---|---|
| `sm` | 31 | `--t-12` |
| `md` (default) | 33 | `--t-12` |
| `lg` | 34 | `--t-12-5` |
| `inset` | 22 | `--t-11` |

| | default (bordered cells) | `inset` (framed toggle) |
|---|---|---|
| group | flex, gap = `gap` prop (5) | `flex 0 0 auto`, padding 2, bg `--seg-inset-bg`, 1px `--seg-border`, radius `--radius-control`, gap 2 |
| cell border | 1px `--seg-border` (picked → tone border) | none |
| cell radius | `--radius-cell` | `--radius-control` |
| cell bg / ink | `--seg-bg` / `--seg-ink` | transparent / `--seg-inset-ink` |
| cell flex | `1` when `grow` (default) | `0 0 auto`, padding `0 10px` |
| hover | `v2-bd` (border only) | **none** |

Picked tones: `accent` → `--seg-on-{bg,ink,border}` · `bad` → `--seg-on-bad-{bg,ink,border}`.
Cell type: `--font-body`, line-height 1, weight **600 when picked and not inset**, else 400, nowrap.
Slots (gap 7): `dotColor` → a fixed-colour `Dot` drawn picked or not · `dots` → N `Dot`s at size 6
overlapped by `marginRight: -4` except the last, tone accent when picked · `label` · `hint` → the
cell's `title`. An **absent** dot draws nothing at all ("an empty span would still eat a gap and push
its label off the cell's centre").
Keyboard: roving tabstop (picked cell, or cell 0 when nothing is picked, is `tabIndex 0`); Arrow
Right/Down +1 and **picks**, Arrow Left/Up −1 and **picks** (wrapping); Enter/Space picks the focused
cell. Select-follows-focus.
Disabled: opacity 0.5 per cell, all cells `tabIndex -1`.
Options shape `[{ value, label, hint, dots, dotColor, tone }]`.
**Known exception (1):** `Searches:207` sets `height: 31` over `size="sm"`'s own 31.

### Meter — `ui.jsx:865-881`

`role="meter"` + one fill div. `value` is 0-1, clamped.
height = `height` prop, default 4 (in use: 1px criterion bars, 4px keyword coverage, 22px funnel bars).
radius = `radius` prop, else `--radius-mini` when `height >= 12`, else `--radius-control`. `overflow: hidden`.
track = `track` prop, else `--meter-track`. Fill = `METER_TONE[tone]` (`accent` `good` `warn` `bad`
`neutral`) **or the raw `tone` string passed through** — the Stats funnel passes `var(--stage-applied)`
etc. through this escape hatch.
`aria-valuenow` (rounded percent) / `-valuemin 0` / `-valuemax 100`. No states. Known exceptions: zero.

### ScoreRing — `ui.jsx:899-969`

| Size | box | viewBox | numeral | stroke | letter-spacing | unscored font | shift fallback |
|---|---|---|---|---|---|---|---|
| `sm` | 34 | 78 | `--t-14` | 5 | `-.02em` | `--t-7-5` | 2px |
| `md` (default) | 44 | 88 | `--t-19` | 5 | *(none)* | `--t-9-5` | 1px |
| numeric | = the number | 88 (`RING_VB`) | md's | 5 | md's | md's | md's |

`RING_R = 35`, circumference `2πR ≈ 219.9`. Arc `rotate(-90 cx cy)`, `strokeLinecap: round`,
`strokeDasharray = (c·clamp(value,0,100)/100).toFixed(1) + ' ' + c.toFixed(0)`.
> "the viewBox is a **constant**, not `2 × box`. With a per-size viewBox, `r = 35 + stroke/2` is a fixed
> 37.5px outer radius whatever the box is: it fits md's 44px box and overflowed sm's 34px one, where
> the SVG root's UA `overflow:hidden` sliced 1.75px off all four sides — the ring rendered as a squircle."

Tones (`--ring-{good,warn,bad,accent,neutral}-{border,ink,bg}`) + track `--ring-track`.
Bands via the exported `scoreTone(s)`: `null` → neutral · `≥70` → good · `≥50` → warn · else bad.

| State | Drawing |
|---|---|
| value | track circle + value arc; numeral absolute inset 0, flex-centred, line-height 1, `--font-display`, tone ink, `transform: translateY(var(--ring-shift-sm\|md, <fallback>))` |
| `value == null` | a single div: 100%×100%, 1px **dashed** `--ring-neutral-border`, radius `--radius-control`, bg = tone bg, `--font-body` at the size's unscored token, `.1em`, uppercase, `--ring-neutral-ink`, `translateY(var(--ring-label-shift, 0px))`, label default **`'No fit'`** (no caller overrides it) |
| `busy` | the same track + an indeterminate **quarter** arc in the accent tone, `v2-spin` on the `<svg>`, `transformOrigin: 50% 50%` — "a score that is being computed occupies the box the score will occupy… so nothing shifts when it lands" |

`children` ride in the ring's own relative box (that is where the Feed's "+N reports" badge pins itself).
`role="img"` only when `ariaLabel` is given. No hover/active/disabled; not a tab stop. Known exceptions: zero.

### Spinner — `ui.jsx:82-92`

`size` default **9** (raw px) · border `SPIN_WEIGHT[weight] ?? '1.5px'` solid (`weight="bold"` → 2px) ·
`borderTopColor: transparent` · radius `--radius-control` · inline-block · `flex 0 0 auto` · aria-hidden.
Colour = the `color` prop, else `--spinner-ink`; Button passes `currentColor`.
`.v2-spin { animation: v2-spin .9s linear infinite }` with `@keyframes v2-spin { to { transform: rotate(360deg) } }` — **not** in the reduced-motion query.
Sizes in use: 9 (default), 11 (Toast), 12 (busy Button). Known exceptions: zero.

### ShowMore — `ui.jsx:1289-1299`

Outer: flex, centred, padding `10px 20px 12px`.
Inner span (`v2-bdc v2-ctl`): height 26 · padding `0 13px` · gap 6 · 1px `--pill-border` · radius
`--radius-control` · `--t-11-5` · ink `--pill-ink` · transparent.
Hover `.v2-bdc` (accent border + accent ink). Label = `label ?? \`Show ${n} more\``.
No `disabled`, no `ariaLabel`. **This is Pill's paint at Pill-sm's height with Button-secondary's
hover — built from neither.** Known exceptions: zero.

### Link — `ui.jsx:998-1008`

`<a>` when `href`, else a `span` with `role="link"`.
`--t-11-5` / 17px / weight 500 · ink `--link-ink` · hover `.v2-hover-accent-text:hover { color: var(--link-ink-hover) !important }`.
`--link-ink` and `--link-ink-hover` **both resolve to `--accent`**, so the hover is currently a no-op on
the ink (the class's `!important` beats the global `.jn-v2 a:hover { color: var(--text) }`).
`rel` overrides the default; `_blank` without one gets `noreferrer`.
The `<a>` form carries **no `tabindex="0"`**, so it gets no keyboard ring from theme.css:1024.
**Known exceptions (4 type/colour + a 7-site `paddingTop: 2` idiom):** Companies 1004 (fontSize 11,
weight 400, lineHeight inherit) · Settings 558, 560 (color `--muted`, fontSize/lineHeight inherit,
weight 400) · Stats 473 (dotted underline) · `paddingTop: 2` at Companies 578/585, Applications 462,
Settings 464, Searches 715/722, CoverLetters 427.
Five further sites (see §C, *quiet inline actions*) do not use Link at all because its 11.5/500 breaks a running sentence.

### NavLink — `ui.jsx:1009-1017`

`span` with `role="link"` · ink `--navlink-ink` · `--t-12` / 18px · padding = the `pad` prop.
Hover `.v2-navlink:hover { background: var(--navlink-hover-bg) !important; color: var(--navlink-hover-ink) !important }` with `transition: background .12s, color .12s`.
The hover wash has **no radius** unless the caller supplies one.
**Known exceptions (2):** JobFeed 1283 (`color: --muted`) · V2App 224 (rail inks + a spread of the
`base` const at V2App:197 carrying `height 34` and padding).

### Label — `ui.jsx:1208-1219`

`span`, or `<label htmlFor>`. `.13em` · uppercase · ink `--label-ink`. Font family and weight unspecified.

| Size | font | line-height |
|---|---|---|
| `md` (default) | `--t-10` | 15px |
| `lg` | `--t-11` | 16px |

**Known exceptions (5), all padding:** Companies 870 · JobFeed 1384 · Resumes 216, 257 · Settings 504.

### Helper — `ui.jsx:1221-1236`

`span` · ink `--helper-ink` · `mono` → `--font-mono`.

| Size | font | line-height |
|---|---|---|
| `md` (default) | `--t-11-5` | 16px |
| `xs` | `--t-10-5` | 16px |

`onClick` makes the sub-line itself the control (act/kb + `cursor: pointer`); inert helpers get neither.
**No hover class even when clickable.**
**Known exceptions (29) — the largest colour family in v2.** Keys: `color` (`--bad`, `--warn`, `--good`,
`--accent`, `--text-2`, `--edge`, a computed tone), `padding` (empty-state / footer helpers),
`borderBottom` (a dotted help underline).
Sites: Applications 447, 450 · Companies 511, 519, 523, 742, 771, 787, 847, 881 · CoverLetterEditor 357, 590 · JobFeed 944, 1154, 1155 · LoginModal 85 · Persona 165, 410 · Searches 855 · Settings 548, 692, 836, 938, 1069, 1085 · Stats 610, 646, 766, 787.
**Missing parameter: a tone/ink prop.**

### Heading — `ui.jsx:1237-1275`

`span` (never a heading element — PageTitle is the only `<h1>`). `--font-display` · ink `--heading-ink`.

**Display family** (weight inherited ≈400, `-.02em`):

| size | font | line-height |
|---|---|---|
| `18` (default) | `--t-18` | 27px |
| `19` | `--t-19` | 26px |
| `22` | `--t-22` | 30px |

**`strong` family** — v2's *second* serif family, the card / column / drawer-section title
(weight 500, or 600 with `strong={600}`):

| size | font | line-height | letter-spacing |
|---|---|---|---|
| `15` | `--t-15` | 22px | `-.01em` |
| `15.5` (default) | `--t-15-5` | 23px | `-.01em` |
| `16` | `--t-16` | 24px | `-.01em` |
| `17` | `--t-17` | 25px | `-.015em` |
| `18` | `--t-18` | 27px | `-.015em` |
| `19` | `--t-19` | 26px | `-.015em` |

> "Left unset these titles inherited preflight's 1.5, so 15/15.5/17/19 landed on 22.5/23.25/25.5/28.5
> and every card that holds one measured x.5 — the height Chrome rounds a 1px border away from. 19
> takes 26 so the two 19s (400- and 500-weight) share a box."

**Known exceptions (2), both sanctioned in-code:** CoverLetters 316 (`lineHeight: '22px'`, `color: --text-2`)
· JobFeed 1107 (`lineHeight: 1.15`).

### PageTitle — `ui.jsx:1277-1284`

`<h1>` · margin 0 · `--font-display` · `--t-30` · weight 400 · line-height 1 · `-.02em` · ink `--heading-ink`.
Known exceptions: zero.

### HeaderRow — `ui.jsx:1128-1150`

`div`, or `<header>` with `as="header"` ("a screen title deserves its element").

| Padding variant | Value |
|---|---|
| `modal` (default) | `16px 22px 13px` |
| `screen` | `22px 30px 16px` |
| `compact` | `15px 22px 12px` |
| `pad` prop | the escape hatch for heads whose gutter is set by the pane they sit in |

| Line variant | Value |
|---|---|
| `line` (default) | borderBottom 1px `--head-line` |
| `soft` | 1px `--head-line-soft` |
| `strong` | 1px `--head-line-strong` |
| `none` | no border at all |

| Background variant | Value |
|---|---|
| unset (default) | transparent |
| `surface` | `--head-bg` |
| `page` | `--head-bg-page` |
| `recessed` | `--head-bg-recessed` |

flex · `alignItems = align` prop (default `flex-start`) · gap 12 · `flex 0 0 auto` · optional `height`.
`id` and `...rest` are zero-pixel pass-throughs.
**Known exceptions (3):** Companies 963 (maxHeight 280) · ResumeEditor 618 (fontSize 12.5, color `--text-2`) · Searches 804 (fontSize 11, color `--text-2`).

### TableHead — `ui.jsx:1158-1170`

`div` with **no role** ("an orphan row role is worse than none").
height = `height` prop, default 28 · padding = `pad` prop, default `0 22px` · flex, centred ·
`flex 0 0 auto` · bg **`--bg`** (a palette token) · ink `--label-ink` · `--t-9-5` / 14px / `.11em` /
uppercase · borderBottom 1px `--head-line-strong` (`soft` → `--head-line-soft`) · `top` → borderTop 1px
`--head-line-soft`.
**Known exceptions (4), all `background: 'transparent'`** — because the `--bg` ground is hard-coded and
there is no `bg="none"`: JobFeed 1359 · Stats 661, 746, 771.

### Rule — `ui.jsx:1177-1186`

`span`, aria-hidden, `display: block`. Tones `soft` (default, `--head-line-soft`) · `line`
(`--head-line`) · `strong` (`--head-line-strong`).
Horizontal: `height: 1`. Vertical: `flex 0 0 auto`, `width: 1`, `height = length ?? 14`.
Known exceptions: zero.

### Surface — `ui.jsx:1192-1204`

`div`, or `<section>` with `as="section"`. Background **`--surface-2`** (a palette token).
Radius: `card` (default, `--radius-card`) · `none` (undefined — the full-bleed PDF preview column) ·
`field` · `row` · `menu`. Padding = the `pad` prop. `...rest` forwards.
**Known exception (1):** Settings 747 (fontSize 11, lineHeight 17px, color `--text-2`).

### ModalPanel — `ui.jsx:1074-1096`

| Part | Spec |
|---|---|
| scrim | `position: fixed; inset: 0`, bg `--scrim-bg`, flex-centred, `zIndex` prop default **70**, click → `onClose`; `scrimProps` carries the `className="jn-v2"` + `data-theme` the two global overlays need; `scrimStyle` merges last |
| panel | `div`, or `<form>` with `as="form"` + `onSubmit`; `width` prop default **480**; bg `--modal-bg`; 1px `--modal-border`; radius `--radius-modal`; shadow `--modal-shadow`; flex column; `minHeight: 0`; click `stopPropagation` |

Escape: `useEscape(onClose, escape && !!onClose)` — a panel with no `onClose` takes **no listener at
all**, "rather than one that swallows the key and does nothing". `escape={false}` is for a screen that
already owns Escape for its whole modal set and guards it (Applications, Settings).
Pixel snap: `useSnapTop(panelRef)` re-runs after every render and on resize.
`role="dialog"` `aria-modal="true"` `aria-labelledby={labelledBy}`.
**No focus trap, no initial focus, no focus restore, no body scroll-lock.**
**Known exceptions (12):** `padding` at ConfirmDialog 16, 36 · LoginModal 52 · Resumes 361 · Companies
900; `maxHeight` at Companies 942 (660), Applications 703 (640), Searches 793 (660), Settings 925
(`min(1280px,92vh)`), Settings 1028 (620); `height` at ResumeEditor 883 (`min(760px,90vh)`);
`scrimStyle` padding at WelcomeModal 34. **Missing parameters: `pad`, `maxHeight`.**

### Drawer — `ui.jsx:1099-1112`

Positioned against its **pane**, not the viewport ("the rail stays reachable while a company is open"),
so the scrim is `position: absolute` too.

| Part | Spec |
|---|---|
| scrim | absolute inset 0, bg `--scrim-bg`, **z 29**, click → `onClose` |
| panel | absolute right 0 / top 0 / bottom 0, `width` prop default **720**, bg `--drawer-bg`, borderLeft 1px `--drawer-border`, shadow `--drawer-shadow`, flex column, **z 30** |

`useEscape(onClose)` — always active, no opt-out. `role="dialog"` `aria-modal="true"`.
**Motion: unspecified — the drawer does not slide, it appears.** No focus trap. Known exceptions: zero.

### ChoiceCard — `ui.jsx:1322-1343`

`role="radio"` · `flex 1, minWidth 0` · padding `9px 11px` · 1px `--choice-border` (on →
`--choice-on-border`) · bg `--choice-bg` (transparent) → `--choice-on-bg` · radius `--radius-cell` ·
column, gap 2.
Label `--t-12-5` / 18px / weight 500, ink `--choice-ink` → `--choice-on-ink`.
Hint: `Helper size="xs"` with `textWrap: 'pretty'`.
Hover `v2-act` — **the card tokens (`--card-border-hover`, `--card-bg-hover`), not the choice tokens**.
Disabled: opacity 0.45. Known exceptions: zero.

### ChoiceRow — `ui.jsx:1346-1389`

`role="radio"` · flex, centred, gap 9 · padding `8px 11px` · same border/bg/radius as ChoiceCard.
Disc: outer 14×14 at `--radius-control`, 1px `--choice-border` (on → `--choice-on-border`); inner 7×7 at
`--radius-control`, bg `--choice-on-border` when on, else transparent.
Label `--t-12-5` / 18px / weight 500, **colour unspecified — inherited** (ChoiceCard sets it, ChoiceRow
does not). Slots: `children` (replaces the label/sub pair) · `sub` (Helper xs, ellipsis) · `hint`
(Helper xs) · `trail`.
Disabled: opacity 0.45. Known exceptions: zero.
**Note: this disc is hand-drawn from `--choice-*`. The `Radio` primitive uses `--check-*` and a `●`
glyph, and `JobFeed:1529` draws a third version. Three radio discs, three token families.**

### ChoiceModal — `ui.jsx:1393-1424`

> "The geometry below IS the Re-tailor modal's, to the pixel — 480 panel · modal head (16/22/13) ·
> body 14/22 on a 460 cap · footer 12/22 over a `--modal-border` rule."

| Part | Spec |
|---|---|
| shell | `ModalPanel` with `overflow: hidden`; `width` default 480, `zIndex` default **60** |
| head | `HeaderRow align="stretch"` column gap 3 → `Heading id={labelledBy}` (display 18) + optional `Helper` sub (`subClamp` truncates to one line). HeaderRow's `modal` padding + `--head-line` rule apply |
| body | class `v2-scroll` · padding `14px 22px` · column · gap = `bodyGap` prop, default **13** ("the one dimension the two résumé modals already disagreed on — Re-tailor 13, Tailor 12") · `maxHeight` = `bodyMax`, default **460** · `overflow: auto` |
| footer | padding `12px 22px` · borderTop 1px `--modal-border` · flex, centred, gap 9 |

Footer order: **note (column, gap 1) … Cancel (secondary sm, `marginLeft: auto`) … action (sm)**.
Cancel is always left of the action. A disabled primary action is `--line` on `--muted` (Button's own
`off` look, RES-17). Known exceptions: zero.

### RemoveLink — `ui.jsx:1029-1032`

`span` · `--t-11-5` / 17px · nowrap · ink `--helper-ink` · class `v2-hover-bad v2-hover-bad-text`
(background → `--hover-bad-bg`, colour → `--hover-bad-ink`). Default children `'Remove'`.
**No padding and no radius**, so the hover wash is a bare text rectangle.
Props: `onClick`, `children` only — no `style`, no `className`. Re-exported from `ResumeSections.jsx`.

### RemoveX — `ui.jsx:1033-1036`

`span` · glyph `✕` · `flex 0 0 auto` · ink `--helper-ink` · **fontSize = the `size` prop, default 11 — a
raw px number outside the `--t-*` scale** · `lineHeight` = the `lh` prop. Same hover pair as RemoveLink.
`title` default `'Remove'`, `aria-label` = title. Props: `onClick`, `title`, `size`, `lh` only.

### MoveArrows — `ui.jsx:1041-1055`

`span` column, gap 1, `flex 0 0 auto`, ink `--helper-ink`, **fontSize 8 — a raw px number**.
Glyphs `▲` / `▼`, titles `Move up` / `Move down`, each with `v2-navlink` (hover wash + `.12s` transition).
`upOff` / `downOff` → opacity **0.35**, cursor default, class dropped, `aria-disabled`.
**The 8px glyph is the smallest hit target in the layer.** Known exceptions: zero.

### ToastCard — `ui.jsx:975-990`

flex, centred, gap 10 · maxWidth **380** · padding `10px 13px` · 1px kind line · radius `--radius-card`
· shadow `--shadow-toast`.

| Kind | bg | border | ink |
|---|---|---|---|
| `progress` (default) | `--toast-progress-bg` | `--toast-progress-line` | `--toast-progress-ink` |
| `success` | `--toast-ok-bg` | `--toast-ok-line` | `--toast-ok-ink` |
| `error` | `--toast-bad-bg` | `--toast-bad-line` | `--toast-bad-ink` |
| `undo` | `--toast-undo-bg` | `--toast-undo-line` | `--toast-undo-ink` |

No states — the enter/leave animation is `Toast.jsx`'s, passed in `style`.
**Known exception (1):** `Toast.jsx:63` `opacity` (documented at the site as mount state, not design).

---

## C. Toasts — `Toast.jsx`

| Kind | TTL | Spins | Mark | Taxonomy note (verbatim) |
|---|---|---|---|---|
| `progress` | 4000 ms | ✔ | — | "quiet paper card + spinner. Ambient status, not news." |
| `success` | 4000 ms | | `✓` on `--accent` | "green tint, solid ✓ roundel. The only green toast." |
| `error` | **null — until dismissed** | | `!` on `--bad` | "red tint, ! roundel… a failure that evaporates before you read it may as well not exist." |
| `undo` | 5000 ms | | — | "the one dark toast. Dark means 'still actionable', which is why progress must NOT be dark." |

> "One 3–5 s band across the app: 4 s for the two that only report, 5 s for undo (which asks for a
> decision), errors until dismissed."

`t.ttl` overrides the table. `spin: false` opts a `progress` card out of spinning (DS-B-02: a progress
card is also the quiet ground for a neutral *result*, which must not keep spinning).

| Property | Value |
|---|---|
| Max stack | **3** — `[...p.slice(-(MAX-1)), next]`, so the oldest is dropped **immediately, with no leave animation** |
| Position | `fixed`, `right 16`, `bottom 16`, **z 80**, flex column, gap 8, `alignItems: flex-end`; newest at the bottom |
| Mark roundel | 16×16, `--radius-control`, kind's markBg, ink `--accent-ink`, fontSize **9.5** (raw), line-height 1 |
| Message | fontSize **12.5** (raw, not `--t-12-5`), line-height **1.45** |
| Action slot | `t.action` / `t.actionLabel`; fontSize 12 (raw), weight 600, `borderBottom: 1px dotted currentColor`, colour `--rail-accent` for `undo` and `inherit` otherwise; fires `t.onAction()` then closes |
| Dismiss | a trailing `✕`, fontSize 11 (raw), opacity 0.55 — "a tint of the ink… survives dark mode without four more tokens" |
| Enter / leave | opacity 0→1 + `translateY(10px)→0` over `opacity 250ms ease, transform 250ms ease`, started on the first rAF after mount; the node is removed **260 ms** after `dismiss` |
| Cross-screen | `setFlashToast(t)` → `sessionStorage['jobnavigator_v2_flash']`; `useFlashToast(push)` reads and clears it once on mount |
| A11y | **unspecified** — no `aria-live`, no `role="status"`/`"alert"`; the action link and the ✕ are bare spans with no role, no label, no tab stop, no key handler |
| Reduced motion | not covered |

---

## D. Dialogs

| | ConfirmDialog | PromptDialog |
|---|---|---|
| Source | `ConfirmDialog.jsx:10-25` | `ConfirmDialog.jsx:31-51` |
| Width | **400** | **440** |
| z-index | 70 (ModalPanel default) | 70 |
| Panel style | `padding: '22px 24px 18px'`, `gap: 8` | same |
| Header | `Heading size={19}` — display serif, `--t-19` / 26px. **No HeaderRow, no rule.** | same |
| Body | optional span: fontSize **12.5** (raw), lineHeight `18px`, colour `var(--muted)` (a palette token) | same |
| Field | — | `Input autoFocus mono readOnly ariaLabel={title}` with `marginTop: 4`; Enter submits; a readOnly field selects all on focus |
| Footer | flex, `justify-content: flex-end`, gap 8, `marginTop: 10` — no rule, no separate padding | flex, centred, gap 8, `marginTop: 10` |
| Button order | **Cancel** (secondary sm) → **confirm** (danger when `danger`, else primary; sm) | editable: Cancel (secondary sm, `marginLeft: auto`) → OK (sm). readOnly: `⧉ Copy` / `Copied ✓` (secondary sm) on the left → Done (sm, `marginLeft: auto`) |
| Escape / backdrop | both cancel (ModalPanel's `useEscape` + scrim click) | same |
| Autofocus | **deliberately none** — "the confirm side never auto-focuses, so Enter can't destroy anything by reflex" | the field autofocuses |
| `aria-labelledby` | **not wired** (the Heading has no id) | **not wired** |

Scrim token: `--scrim-bg` → `--scrim` = light `rgba(20,19,15,.42)` · dark `rgba(0,0,0,.58)` · alt light
`rgba(17,20,27,.46)`.
`ModalPanel` and `ChoiceModal` are specified in §B. `Drawer` is pane-relative at z 29/30.
The two global overlays: **LoginModal** (`as="form"`, width 360, z **9999**, `scrimProps` carrying
`className="jn-v2"` + `data-theme`, no Escape) and **WelcomeModal** (width 420, z **9998**).

---

## E. Known exceptions — the sites the primitive layer does not cover

Two sweeps across `frontend/src/v2/*.jsx` (excluding `ui.jsx`).

### E.1 `ui: keep` markers — 172 sites

| File | Count | | File | Count |
|---|---|---|---|---|
| JobFeed.jsx | 37 | | CoverLetterEditor.jsx | 6 |
| Settings.jsx | 20 | | Persona.jsx | 6 |
| Companies.jsx | 18 | | CoverLetters.jsx | 4 |
| Stats.jsx | 17 | | LoginModal.jsx | 4 |
| Applications.jsx | 15 | | V2App.jsx | 4 |
| ResumeEditor.jsx | 10 | | WelcomeModal.jsx | 4 |
| Resumes.jsx | 10 | | Toast.jsx | 2 |
| ResumeSections.jsx | 8 | | ConfirmDialog.jsx | 0 |
| Searches.jsx | 7 | | | |

Recurring categories:

| Category | Sites | Shape | Why no primitive |
|---|---|---|---|
| **modal / drawer FOOTER bar** | 11 | padding `11-14px 22-24px`, borderTop 1px `--line`/`--line-soft`, bg `--bg` (ResumeEditor: `--surface-2`) | "HeaderRow draws its rule beneath" — there is no `FooterRow` |
| **Tag role by hand** | 12 | uppercase badge, r99, bg+ink pair, 9.5 or 10px, `.06em`/`.08em`/`.1em`, pad `1px 5px`\|`1px 7px`\|`2px 7px`\|`3px 8px` | Tag has one fixed box (10 / 15px / `.06em` / `2px 8px`) and five tones |
| **mono-text role** | 12 | `--mono` at 9.5/10/10.5/11/11.5 in `--edge`, `--text-2`, `--text`, `--accent` or a score colour | there is no `Mono`/`Code` primitive; Helper's `mono` covers only `--helper-ink` |
| **serif outside the Heading scale** | 10 | 12, 15, 17, 20, 21, 23, 26, 27 px | Heading offers 18/19/22 and 15-19 strong; and there is no nested-unit slot |
| **glyph badge** | 9 | a small round filled/bordered box holding one glyph (15, 16, 22, 34 px) | Dot draws a bare disc with no glyph; IconButton's smallest box is 26 and is a control |
| **the 25px Run/Test pill** | 7 | h25, pad `0 9-11px`, r99, 1px `--edge` on `--surface`, 11.5 (+ a 25×25 ⋯ twin) | "Pill sm is 26"; "IconButton's bordered look is 36" |
| **the 24px PDF-toolbar trigger** | 4 | h24, pad `0 8px`, 1px `--edge`, r6, 11.5, + a 9px `▾` | "Select's box is 32". *Logged drift:* CoverLetterEditor uses `v2-bd v2-ctl`, ResumeEditor uses `v2-act` — "a needs-decision, not a licence to add a third" |
| **`v2-fieldwrap` composites** | 9 | a bordered box holding a **bare** `<input>` plus a ⌕, a show/hide toggle, a ✕ or an error tint | Input draws its own box; SearchInput's boxed variant is h32 on `--search-bg` only |
| **prose rows / bare textareas** | 7 | border none, background transparent, `resize: none`, autosizing; the parent row supplies the box | "Textarea would have to be overridden away entirely" |
| **table BODY rows** | 7 | flex, h32/34/38, pad `0 20-22px`, borderBottom 1px `--line-soft` | Row is 46px with a hover and a `--row-line` divider |
| **native anchors** | 5 | `<a href target=_blank>` that must stay ⌘/middle-clickable | Button has `as="button"` but no `as="a"`/`href`; only MenuItem solved this |
| **on-rail controls** | 6 | `--rail-ink` on a 1px `--on-rail-line` hairline over the dark `--rail` ground | "Pill and Button paint for light surfaces" — no primitive has an on-dark variant |
| **quiet inline actions** | 5 | a clickable span at `--muted` 11/12.5 weight 400 that must run inline inside a sentence | "not the Link signature (accent 11.5/500)" |

One-off composites worth naming: the two-line `Picker` (CoverLetters 28/70) · the keyboard-driven
typeahead rows (Settings 1055) · the grab-strip + 52×4 handle (JobFeed 1163/1170) · the report *band*
header (JobFeed 1245/1252) · the two-cell segmented filter track with one shared border run (JobFeed
1350) · the pre-ChoiceCard choice cards at 13.5 (JobFeed 1527/1570) · the amber Q&A card (Persona
424/437) · `ACT_BTN` (Applications 64) · `RAIL_BTN` (JobFeed 72) · `BOX` (Settings 23) · the settings
anchor rail (Settings 505) · `COL` / `MONO` (Stats 99/103) · the collapsing 36↔30 header actions
(JobFeed 1211/1214).

### E.2 Geometry or colour passed into a primitive

| Primitive | Sites | Keys | Missing parameter |
|---|---|---|---|
| **Helper** | 29 | `color` (dominant), `padding`, `borderBottom` | a tone/ink prop |
| **Card** | 23 | `padding` (dominant), `height`, `borderColor`, `background`, `lineHeight` | `pad`, `tone` |
| **ModalPanel** | 12 | `padding`, `maxHeight`, `height` | `pad`, `maxHeight` |
| **Band** | 8 | `padding`, `borderColor`, `background`, `fontSize`, `color` | `pad`, `tone` |
| **Menu** | 6 | `maxHeight`, `padding` | `maxHeight` |
| **SectionHead** | 6 | `padding` (documented), `lineHeight`, `borderRadius` | — |
| **Input** | 6 | `width`, `padding`, `fontWeight` | `width`, `pad` |
| **Label** | 5 | `padding` | `pad` |
| **Link** | 4 (+7 `paddingTop:2`) | `fontSize`, `fontWeight`, `lineHeight`, `color`, `borderBottom` | a size/tone scale |
| **Textarea** | 4 | `minHeight`, `borderColor`, `borderStyle` | an error state |
| **TableHead** | 4 | `background: transparent` | `bg="none"` |
| **HeaderRow** | 3 | `maxHeight`, `fontSize`, `color` | — |
| **Dot** | 3 | `background` (defeats `tone`) | an arbitrary-colour prop |
| **Chip** | 3 | `color` | a tone prop |
| **Heading** | 2 | `lineHeight`, `color` | *(both sanctioned in-code)* |
| **NavLink** | 2 | `color`, `height`, `padding` | — |
| **Row** | 2 | `padding`, `height`, `background*` | — |
| **Surface** | 1 | `fontSize`, `lineHeight`, `color` | — |
| **MenuItem** | 1 | `color`, `paddingTop` | a tone prop |
| **Segmented** | 1 | `height` | — |
| **DashedAdd** | 1 | `padding` | `pad` |
| **ToastCard** | 1 | `opacity` (mount state) | — |

**Zero geometry/colour overrides:** Button · Pill · IconButton · SearchInput · Select · MenuHead · Tag ·
Check · Radio · Switch · Meter · ScoreRing · Spinner · ShowMore · PageTitle · Rule · Drawer ·
ChoiceCard · ChoiceRow · ChoiceModal · RemoveX · RemoveLink · MoveArrows.

**Spread constants that smuggle geometry:** `CoverLetters:24 POPOVER` (maxHeight into Menu) ·
`V2App:197 base` (height 34 + padding into NavLink) · `Applications:64 ACT_BTN` · `JobFeed:72 RAIL_BTN` ·
`Settings:23 BOX` (a copy of Select's trigger that has **drifted** — BOX paints `--surface`, Select now
paints `--input-bg`) · `Stats:99 COL` · `Stats:103 MONO`.

---

## F. What the code leaves unspecified — for Claude Design to fill

| # | Area | Gap |
|---|---|---|
| U-01 | state | **No `:active` / pressed paint anywhere in v2.** Every control goes rest → hover → (focus ring), nothing between. |
| U-02 | state | Button `primary` and `danger` have **no hover at all** — the app's two loudest controls are the only ones that don't react to the pointer. |
| U-03 | motion | Hover transitions are inconsistent: `.v2-card`/`.v2-chip`/`.v2-dashadd`/`.v2-navlink` animate at `.12s`; `.v2-act`/`.v2-bd`/`.v2-bdc`/`.v2-row`/`.v2-menuitem`/`.v2-hover-*` swap instantly. No motion token — `.12s` is a literal repeated 11 times, and there is no easing token. |
| U-04 | motion | `prefers-reduced-motion` covers only `.v2-grab` and `.v2-fold`. The spinner, the Switch knob (150 ms), the toast (250 ms) and the warm-start fade (.15 s) are uncovered. |
| U-05 | state | Six disabled treatments (token swap / 0.6 / 0.5 / 0.45 / 0.35, plus busy-only 0.6). No `--disabled-opacity` token; no disabled ink token for a field. |
| U-06 | state | **No error / invalid state for Input, Textarea or Select.** No `--input-border-error`; the three sites that need one set `borderColor: var(--bad)` inline. |
| U-07 | state | `readOnly` on Input/Textarea has no distinct paint. |
| U-08 | state | No loading / skeleton / empty-state primitive. Only Button and ScoreRing have a `busy`; `useSettled` ships no spinner by design. |
| U-09 | a11y | **No focus trap, no initial focus, no focus restore, no body scroll-lock** in ModalPanel, Drawer, ChoiceModal, ConfirmDialog or PromptDialog. |
| U-10 | a11y | Select has no arrow keys, typeahead, `aria-activedescendant` or `aria-controls`, and its trigger is a div. Menu has no roving focus, no arrow keys and no Escape of its own; callers hand-roll a click-away backdrop at a hand-picked z-index. |
| U-11 | a11y | **No minimum hit-target rule.** Present: MoveArrows 8 px, RemoveX 11 px, Check/Radio 14-15 px, Switch 26×15, Button xs 28 px tall, IconButton 26×26. |
| U-12 | a11y | The toast stack has no `aria-live`/`role="status"`; its action link and ✕ are bare spans with no role, label, tab stop or key handler. |
| U-13 | a11y | ConfirmDialog and PromptDialog never wire `aria-labelledby` — the dialog is announced without its title. |
| U-14 | tokens | No ink/tone parameter on **Helper** (29 inline colour sites), Card, Band, Link, Chip, MenuItem, Dot. |
| U-15 | tokens | No `pad`/`size` parameter on Card (23), ModalPanel (12), Band (8), Input (6), Label (5), DashedAdd (1). |
| U-16 | tokens | Four primitives read **palette** tokens directly: TableHead (`--bg`), Surface (`--surface-2`), Toast.jsx (`--accent` `--bad` `--accent-ink` `--rail-accent`), ConfirmDialog.jsx (`--muted`). Toast.jsx and ConfirmDialog.jsx also set raw px font sizes (9.5, 11, 12, 12.5). |
| U-17 | tokens | RemoveX (11) and MoveArrows (8) set raw px font sizes outside `--t-*`; Dot's `size` (7) and Spinner's `size` (9) are raw numbers. |
| U-18 | tokens | **The rail has no semantic layer.** `--rail*` and `--on-rail-*` are palette names read straight by V2App and JobFeed; six `ui: keep` sites exist purely because no primitive has an on-dark variant. |
| U-19 | tokens | The `--cc-*` (17) / `--sm-*` (6) badge taxonomy is painted by a class, sits outside the semantic layer and is excluded from every skin — a skin cannot restyle a third of the on-screen badges. `Tag tone="none"` exists only to get out of its way. |
| U-20 | layering | **No named z-index scale** — 20 literals (2…9999), most at call sites; ConfirmDialog's stacking relies on DOM order at equal z-index. |
| U-21 | geometry | A skin cannot express geometry today. Under the recorded decision, the per-skin set must grow from **60** names to include the radius scale (10), the shadow scale (5), the type scale (20) and a border-width family that **does not exist yet** — and the proof restated as "only tokens may differ". |
| U-22 | geometry | **No border-width token of any kind.** `1px` is a literal 135× in screens and 20× in `ui.jsx`; 1.5 / 2 / 3 px are literals too. |
| U-23 | roles | Sizes the primitives don't offer, each drawn by hand at multiple sites: a 25 px pill (7), a 24 px toolbar trigger (4), 25×25 / 22×22 / 16×16 / 15×15 icon boxes (9), a 32/34/38 px table body row (7), a modal footer bar (11), a two-line option row (2), an on-dark control (6). |
| U-24 | roles | Two roles have **no primitive at all**: `Mono` (12 hand-drawn sites, five inks, five sizes) and `FooterRow` (the mirror of HeaderRow, rule on top). |
| U-25 | type | Serif 12, 20, 21, 23, 26, 27 are drawn at 10 sites outside Heading's two tables, and there is no slot for a nested sans unit inside a serif numeral. |
| U-26 | type | The root line-height is **inherited from the v1 shell's Tailwind preflight (1.5)**, not declared. Every fixed-height control opts out with `.v2-ctl`, and every text role pins an integer line-height by hand. |
| U-27 | composition | Button has `as="button"` but no `as="a"`/`href`; five sites hand-draw the button to keep a real anchor. |
| U-28 | composition | No `Field` primitive with an adornment slot — nine composites use a `v2-fieldwrap` div around a bare `<input>`. |
| U-29 | consistency | **Three radio discs, three token families:** ChoiceRow (`--choice-*`, no label ink), Radio (`--check-*`, `●`), JobFeed:1529 (hand-drawn). |
| U-30 | consistency | `Settings:23 BOX` claims to be Select's trigger "to the pixel" but paints `--surface` where Select now paints `--input-bg`. The code drifted; the comment did not. |
| U-31 | consistency | The two 24 px PDF-toolbar triggers use different hover classes for the same control (`v2-bd v2-ctl` vs `v2-act`) — logged in-code as a needs-decision. |
| U-32 | skins | The light and dark semantic blocks are byte-identical: no semantic token has ever been re-pointed per theme. The mechanism exists but is untested. |
| U-33 | skins | The board skins are palette-only imports of designs that also changed geometry. `win98` additionally records two things a palette cannot fix: `--bg` is a *desktop* colour (black ink reads 1.46:1 on the dark one), and its rail is *light*, so the white-alpha on-rail overlays vanish. |
| U-34 | responsive | **No breakpoints and no responsive tokens.** The only viewport-aware values are three `min(px, vh\|vw)` literals in modal sizes and one recorded ≤1024 px fix (`.v2-cactions`). |
| U-35 | misc | IconButton at a size other than 26/36 is undefined; Meter's `tone` accepts an arbitrary `var(--…)` pass-through, and Dot is overridden the same way at three sites. |
