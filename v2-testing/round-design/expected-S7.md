# expected-S7 — the default-theme deltas of the decision pass (2026-09-05)

Every visual change this pass makes to `data-theme="default"`. Anything not
listed here must be pixel-identical to S5/S6. **Rest paint does not move except
where D-14 and D-21 say so; hover and :active tuples do move.**

Colour values are the resolved base-block tokens: `light` / `dark`.

---

## D-06 — field hover border (`--input-border-hover`)

`theme.css` base blocks: `--input-border-hover: var(--input-border)` → `var(--line-strong)`.
The rule (`.jn-v2 .v2-inset:not(.v2-underline):not([aria-expanded="true"]):hover:not(:focus)`)
was already live and inert; it now paints.

| primitive | rest border | hover border (new) |
|---|---|---|
| `Input` | `--input-border` = `--edge` `#8a826e` / `#7f7a66` | `--line-strong` `#c9c3b4` / `#4a4638` |
| `Textarea` | same | same |
| `Select` (closed trigger) | same | same |
| `SearchInput` variant `boxed` | same | same |

Carve-outs, unchanged and still correct: `SearchInput` variant `underline`
(rests on `--input-underline`), an **open** `Select` trigger (`aria-expanded`,
already `--input-border-focus`), a focused field, and field **wrappers**
(`.v2-fieldwrap`, which LoginModal paints `--bad` while an error stands).

**`ToolbarTrigger` is NOT in this table.** D-06's wording names it, but the
primitive deliberately does not carry `v2-inset` (the inset hover rule is
`!important` and sits later in the file than `.v2-bdc:hover`, so it would beat
the trigger's own accent hover). D-13 names `v2-bdc` as the trigger's hover, and
that is the paint it keeps. The two decisions conflict on this one control and
D-13 — the later, more specific one — was taken.

**Value note for whoever reviews the render.** In the default theme
`--line-strong` is *lighter* than `--edge` in light mode (`#c9c3b4` vs `#8a826e`)
and *darker* in dark mode (`#4a4638` vs `#7f7a66`) — i.e. on both grounds the
hovered border reads **softer** than the rest border, not stronger. cobalt/saas
point this token at `--text-2`, which darkens. If the intent was "stronger on
hover", the base value wants `--text-2` (`#57534a` / `#cbc7bf`), not
`--line-strong`. Implemented as decided; flagged, not changed.

---

## D-07 — pressed state (`--pressed-shift`, `--pressed-wash`, `*-pressed-bg`)

`theme.css` base blocks (both):

- `--pressed-shift: none` → `translateY(1px)`
- `--pressed-wash: transparent` → `var(--surface-2)` (`#f6f4ee` / `#322f24`)
- `--btn-primary-pressed-bg: var(--btn-primary-bg)` → `color-mix(in oklab, var(--btn-primary-bg) 82%, black)`
- `--btn-danger-pressed-bg` — **new name**, `color-mix(in oklab, var(--btn-danger-bg) 82%, black)`

New rule in `theme.css`:
`.jn-v2 .v2-btn-danger:active { background:var(--btn-danger-pressed-bg) !important; transform:var(--pressed-shift); }`
(the danger twin of the primary rule that already existed).

Primitives that now shift 1px and take a `--surface-2` wash while held — every
carrier of `v2-bd` / `v2-bdc` / `v2-act`:

| primitive | class | notes |
|---|---|---|
| `Pill` md · sm | `v2-bd` | |
| `Pill` xs | `v2-bdc` | after D-13 |
| `IconButton` 25 | `v2-bdc` | after D-13 |
| `IconButton` 36 | `v2-act` | |
| `IconButton` 26 | — | `v2-hover-accent`, not in the rule; unchanged |
| `ToolbarTrigger` sm · md | `v2-bdc` | |
| `Button` tone `secondary` | `v2-bdc` | |
| `Segmented` cell (non-`inset`) | `v2-bd` | |
| `Card` `interactive` | `v2-act` | |
| `Band` | `v2-act` | |
| `ChoiceCard` · `ChoiceRow` | `v2-act` | |

Filled buttons take the darkened ground plus the same 1px shift:

| primitive | pressed background |
|---|---|
| `Button` tone `primary` | `color-mix(--accent 82%, black)` — `#3f6b52` → ~`#325744` / `#8dbb9f` → ~`#719a82` |
| `Button` tone `danger` | `color-mix(--bad 82%, black)` — `#9c3b30` → ~`#7f2f26` / `#d98a7e` → ~`#b27065` |

Skin blocks got `--btn-danger-pressed-bg` too, mirroring each one's primary
treatment: cobalt/saas `color-mix(… 78%, black)`, win98 `var(--btn-danger-bg)`
(it flips its bevel instead of darkening). No other skin value moved.

---

## D-11 — filled-button hover (`--btn-*-hover-bg`)

`theme.css` base blocks (both): both names stop resolving to the button's own
rest paint.

| primitive | rest | hover (new) |
|---|---|---|
| `Button` tone `primary` | `--accent` `#3f6b52` / `#8dbb9f` | `color-mix(--accent 90%, black)` ≈ `#396047` / `#7fa88f` |
| `Button` tone `danger` | `--bad` `#9c3b30` / `#d98a7e` | `color-mix(--bad 90%, black)` ≈ `#8c352b` / `#c37c71` |

Every other tone (`secondary`, `ghost`) is unchanged — they hover through
`v2-bdc` / `v2-hover-accent` and always did.

---

## D-13 — one paint for the small row control

The four hover signatures collapse to one: **`v2-bdc`** (accent border + accent
ink) on the 25px pills, the 25×25 ⋯ and the 24px triggers. Defaults moved into
the primitives; the per-site `hover=` props are gone.

`v2-act:hover` = accent border **+ `--card-bg-hover` (`--hover-soft`) wash**.
`v2-bd:hover` = accent border only. `v2-bdc:hover` = accent border **+ accent ink**.

| site | before | after | delta |
|---|---|---|---|
| Companies "Run" `Pill xs` | `v2-act` | `v2-bdc` | loses the `--hover-soft` wash (`#f4f8f5` / `#2e2b20`), gains accent ink |
| Companies "Test" `Pill xs` | `v2-act` | `v2-bdc` | same |
| Companies ⋯ `IconButton 25` | `v2-act` (size default) | `v2-bdc` (size default) | same |
| Searches "Run" `Pill xs` | `v2-bdc` (prop) | `v2-bdc` (size default) | none — prop deleted only |
| Searches "Test" `Pill xs` | `v2-bdc` (prop) | `v2-bdc` (size default) | none — prop deleted only |
| Searches ⋯ `IconButton 25` | `v2-bd` (prop) | `v2-bdc` (size default) | gains accent ink on hover |
| ResumeEditor Template/Paper `ToolbarTrigger` | `v2-act` (prop) | `v2-bdc` (default) | loses the wash, gains accent ink |
| CoverLetterEditor Template/Paper `ToolbarTrigger` | `v2-bd` (default) | `v2-bdc` (default) | gains accent ink |
| Settings cron "Preset" `ToolbarTrigger` | `v2-bd` (default) | `v2-bdc` (default) | gains accent ink |

Accent ink on hover = `--pill-ink-hover` = `--accent` `#3f6b52` / `#8dbb9f`
(from `--pill-ink` = `--text-2` `#57534a` / `#cbc7bf`).

### Running-state boxes — measured, kept identical

Every busy branch was measured before the unification and none of them moved:

| site | busy box | outcome |
|---|---|---|
| Companies "Run" (`Spinner` + "Running") | h25 · pad `0 10` · gap 5 | already canonical — untouched |
| Companies "Test" (`Spinner` + "Testing…", `on`, `opacity:1`) | h25 · pad `0 10` · gap 5 | already canonical — untouched |
| Searches "Run" (`Spinner` + "Running", ink → `--pill-on-ink`) | h25 · pad **`0 9`** · gap 5 | **kept inline** — canonical `0 10` would widen it 2px |
| Searches "Test" (`Spinner` + "Test") | h25 · pad **`0 9`** · gap 5 | **kept inline** — same, so it matches its twin |
| Stats scheduler "Run now" / "Running…" | h25 · pad **`0 11`** · gap **6** · no ground · running quiets border `--line` + ink `--edge` | **kept hand-drawn** |

The three exceptions carry a `// ui: keep — running-state box` note at the site.

**Stats' ground-less scheduler pill: kept and noted, no `quiet`/`ghost` variant
added.** A variant would have to reproduce three things at once — no ground,
`0 11`/gap 6, and a running state that goes quiet through border+ink rather than
dimming with `--disabled-opacity`. Adopting `Pill xs` for even its rest branch
moves the box, which is what D-13 says not to do. One `ui: keep` note is cheaper
and honest.

Still-open remainder of D-13: Searches' two pills sit at `0 9` against
Companies' `0 10`. The *hover paint* is now one signature everywhere; the
*padding* is two. Closing that last 1px is a deliberate 2px widening of a
running pill and needs its own call.

---

## D-14 — the two off-tone glyph badges take the primitive's paint

Tokens stay at the shipped paint. The two sites that drew off-tone now read
`--glyph-border` / `--glyph-bg` / `--glyph-ink`.

**JobFeed head, the "?" shortcuts badge** (16×16, `tone="outline"`), `JobFeed.jsx`:

| property | before | after |
|---|---|---|
| background | `transparent` (inline) | `--glyph-bg` = `--surface` `#ffffff` / `#28251b` |
| border-color | `--head-line` = `--line` `#e2ddd0` / `#3e3b32` (inline) | `--glyph-border` = `--edge` `#8a826e` / `#7f7a66` |
| ink | `--glyph-ink` = `--muted` `#6d6862` / `#a8a49d` | unchanged |
| font-size | `var(--t-10)` (kept — glyph size, not paint) | unchanged |

**Settings → Model catalog, the 22px "×" remove button**, `Settings.jsx`. A
hand-drawn `<span>` becomes `GlyphBadge size={22} tone="outline"`:

| property | before | after |
|---|---|---|
| background | none (transparent) | `--glyph-bg` = `--surface` `#ffffff` / `#28251b` |
| border | `1px solid var(--line)` `#e2ddd0` / `#3e3b32` | `var(--bw-hair) solid var(--glyph-border)` = 1px `--edge` `#8a826e` / `#7f7a66` |
| ink | `--edge` `#8a826e` / `#7f7a66` | `--glyph-ink` = `--muted` `#6d6862` / `#a8a49d` |
| box · radius · font-size | 22×22 · `--radius-control` · 11px | identical (`GLYPH_SIZE[22]` is `var(--t-11)` = 11px) |
| hover | `v2-hover-bad-bdc` | unchanged (passed as `hover=`) |
| keyboard | local `kb()` | `act()` inside the primitive — same tabIndex/role/Enter-Space |

`Notice`'s tokens were the other half of D-14 and are unchanged: the shipped
`--warn` at `--radius-card` stands, the board's `--warn-line` at `--radius-cell`
was not taken.

---

## D-15 — the open 25×25 ⋯ swings the full on-trio

`style={{ color: 'var(--pill-ink)' }}` deleted at both sites (`Companies.jsx`,
`Searches.jsx`). While the menu is open the glyph ink now follows the fill and
border instead of staying behind.

| state | before | after |
|---|---|---|
| ⋯ open, glyph ink | `--pill-ink` = `--text-2` `#57534a` / `#cbc7bf` | `--pill-on-ink` = `--accent` `#3f6b52` / `#8dbb9f` |

Fill (`--pill-on-bg`) and border (`--pill-on-border`) are unchanged; the 36px ⋯
already painted this way, so the two sizes now agree.

---

## D-21 — `ToolbarTrigger` gets `size`

`sm` = 24 (the canonical PDF-toolbar box, unchanged and the default), `md` = 32
(field height). Radius and border are a field's already (`--radius-field`,
`--input-border`), so `md` only changes the box.

| site | before | after |
|---|---|---|
| Settings, the five cron rows' "Preset" trigger | h24 · pad `0 8` | h32 · pad `0 10` |
| ResumeEditor Template/Paper | h24 · pad `0 8` | unchanged (`sm` default) |
| CoverLetterEditor Template/Paper | h24 · pad `0 8` | unchanged (`sm` default) |

This is the pass's one intentional rest-geometry change: the cron picker now
lines up with the 32px cron box beside it instead of sitting 8px short.

---

## D-02 — Board theme restored (new theme, no default-theme delta)

`.jn-v2[data-theme="board"]` and `…[data-appearance="dark"]` restored from
`17a2dfc` under the current attribute names, 60 tokens each — the same set
`editorial` carries, verified by the parity gate (no name added, none missing).
`index.html` gained the two boot grounds (`#faf7ef` / `#15140f`).

Picker (`THEME_PICKER` in `theme.js`, read by Settings → Display → Theme):
**Default · Board · Cobalt · SaaS · Win98**. `tone1/2/3`, `editorial` and `alt`
stay in `THEMES` (so a stored key still validates and still paints) and in
`theme.css`, but are off the picker. `themeOptions(current)` prepends the
current theme when it is one of the hidden stops, so a machine that stored
`editorial` sees its name in the box rather than a blank one.

No change to the default theme.

---

## Not repainted (checked)

- Every `--cc-*` / `--sm-*` badge hue, `--shadow-*`, the on-rail overlays.
- `Notice`, `Meter`, `ScoreRing`, `Switch`, `Check`/`Radio`, `Toast*`, `Row`,
  `Menu`, `Modal`/`Drawer`, `Chip`, `Tag`, `Dot`, `Mono`, `Link`/`NavLink`.
- Disabled paint (D-08 stands as implemented), rail mark width (D-12, 3px),
  `--label-tracking-scale` (D-18), the win98-named selectors (D-17).
- `IconButton` 26 and 36, `Pill` md and sm: no default change beyond the
  :active tuple that D-07 gives every bordered control.
