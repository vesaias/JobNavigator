# expected-S4 — new primitives and the last hand-drawn sites

Step 3 of the skins pass. Seven roles that had no component (Skins handoff §4 item 10) become
primitives; the sites the spec lists for them (`PRIMITIVES-SPEC.md` §E.1) are migrated; the four
palette leaks in §4 item 11 are re-pointed.

**Target: no computed-style change in the default theme beyond the crawl's own re-keying**, plus the
short list of *non-painting* computed values below. Every one of them is a property that does not
move a pixel in a fixed-height, flex-centred box — they are recorded here so a crawl diff is read as
"expected" rather than "drift".

---

## 1. Same-value re-points (U-16, handoff §4 item 11) — zero computed change

| Site | Was | Now | Resolves to |
|---|---|---|---|
| `ui.jsx` TableHead | `--bg` | `--head-bg-page` | `var(--bg)` — **already done in step 2**, verified |
| `ui.jsx` Surface | `--surface-2` | `--head-bg-recessed` | `var(--surface-2)` |
| `Toast.jsx` success mark | `--accent` | `--toast-mark-ok` | `var(--accent)` |
| `Toast.jsx` error mark | `--bad` | `--toast-mark-bad` | `var(--bad)` |
| `ConfirmDialog.jsx` body ×2 | `--muted` | `--helper-ink` | `var(--muted)` |

Both new toast names are declared in **both** base blocks (`.jn-v2` and
`.jn-v2[data-appearance="dark"]`), so neither can leak across appearances.

Still leaking, and **out of scope** because the handoff's list does not name them: `Toast.jsx`
`--accent-ink` (the mark's ink) and `--rail-accent` (the undo action link). U-16's other half — the
raw 9.5/11/12/12.5 px sizes in `Toast.jsx` and `ConfirmDialog.jsx` — is untouched too.

## 2. New semantic tokens — 28 names, all `var(<palette token the site already wrote>)`

Added to the two base blocks only (a theme replaces the palette these point at, so no theme block
needs to grow):

`--mono-ink` `--mono-ink-muted` `--mono-ink-faint` `--mono-ink-strong` `--mono-ink-accent` ·
`--glyph-bg` `--glyph-ink` `--glyph-border` `--glyph-on-bg` `--glyph-on-ink` `--glyph-on-border`
`--glyph-neutral-bg` `--glyph-neutral-ink` `--glyph-accent-bg` `--glyph-accent-ink` `--glyph-bad-bg`
`--glyph-bad-ink` · `--notice-warn-bg/-border/-mark` `--notice-bad-bg/-border/-mark`
`--notice-quiet-bg/-border/-mark` · `--toast-mark-ok` `--toast-mark-bad`.

`checkvars.py`: 372 → 400 base names, no light-only or dark-only addition.

---

## 3. Sites where a computed value changes — and why no pixel does

### 3.1 `line-height` — **this one WAS painting, and is reverted**

The first cut of this step let the primitives hand every migrated control their `line-height: 1`
(`v2-ctl` on Pill / IconButton / ToolbarTrigger, an inline `1` on GlyphBadge) and recorded it here as
non-painting, on the reasoning that a line box centred in a fixed flex box leaves the glyph on the
same row whatever its leading.

**That reasoning is wrong.** A glyph sits at the centre of *its own* line box, and half-leading —
`(line-height − content-height) / 2` — rounds to a different device row at 18 px than at 9 px. The S4
gate against S3 caught it: the settings info "i" sat one pixel higher, and four computed tuples
moved. The hand-nudged glyphs are the worst case, because their `transform` was calibrated against
the old rounding.

The line box is now **reproduced exactly per site**. `Pill`, `IconButton` and `ToolbarTrigger` take a
`line` prop (an inline value beats the `v2-ctl` class); `GlyphBadge` writes **no** `line-height`
unless asked, so the four sites that inherited theirs still do.

| Site | S3 | first S4 cut | now |
|---|---|---|---|
| `Settings.jsx` 15 px "i" ×3 — inner span | `18px` (h 18) | `9px` (h 9) ✗ **1 px shift** | `18px` — no `line` |
| `JobFeed.jsx` 16 px "?" badge | `15px` | `10px` ✗ | `15px` — no `line` |
| `JobFeed.jsx` 16 px selected ✓ | inherited | `1` ✗ | inherited — no `line` |
| `Stats.jsx` error-band `!` badge | `18px` (from the band) | `1` ✗ | `18px` — no `line` |
| `Searches.jsx` Run / Test 25 px pills | `17.25px` (inherited 1.5) | `11.5px` ✗ | `17.25px` — `line="inherit"` |
| `Companies.jsx` Run / Test 25 px pills | inherited 1.5 | `1` ✗ | inherited — `line="inherit"` |
| `Companies.jsx` · `Searches.jsx` 25×25 ⋯ | inherited 1.5 | `1` ✗ | inherited — `line="inherit"` |
| `ResumeEditor.jsx` Template / Paper triggers | inherited 1.5 | `1` ✗ | inherited — `line="inherit"` |
| `CoverLetterEditor.jsx` Template / Paper | `1` (site had `v2-ctl`) | `1` | `1` — the primitive's default |
| `LoginModal.jsx` 34 px ✓ | `1` (site wrote it) | `1` | `1` — `line={1}` |
| `WelcomeModal.jsx` 22 px step numeral | `1` (site wrote it) | `1` | `1` — `line={1}` |
| `Toast.jsx` 16 px mark | `1` (site wrote it) | `1` | `1` — `line={1}` |

`line="inherit"` resolves to the parent's computed number (the shell's 1.5), which is what these
controls had — none of the seven hand-drawn small controls ever carried `v2-ctl`. Adopting it is a
one-pixel change on purpose, not a side effect of taking the primitive: **D-16**.

### 3.2 `flex` on a badge or a control that had none

The primitives pin `flex: 0 0 auto` so a control cannot be squeezed. Four sites left it at the
initial `0 1 auto`:

- `Companies.jsx` — the **Test** 25 px pill (its Run sibling already wrote `0 0 auto`)
- `Companies.jsx` · `Searches.jsx` — the two 25×25 ⋯ buttons
- `LoginModal.jsx` — the 34 px success badge (**no** change: GlyphBadge does not set `flex`; the four
  sites that wrote it keep writing it in `style`)

Nothing in those rows overflows, so `flex-shrink` never fired.

### 3.3 `justify-content` on a content-sized box

`Companies.jsx`'s **Test** pill had none (`flex-start`); Pill writes `center`. The box is sized by its
content plus padding, so the two are identical. Its Run sibling already wrote `center`.

### 3.4 `box-shadow` written as a token that resolves to `none`

Pill / IconButton (`--pill-shadow`) and ToolbarTrigger (`--field-shadow`) now declare a shadow. Both
names are `none` in the base blocks, and the computed value of an undeclared `box-shadow` is `none`,
so this is a no-op here and the hook a theme needs.

### 3.5 Class additions that paint nothing in the default theme

`v2-raised` (Pill xs, IconButton 25) reads `--bevel-raised-*` — `none` / `transparent` / `none` in
every theme but win98 — and both primitives write `border` and `box-shadow` **inline**, which beats
the class rule outright.

`ToolbarTrigger` deliberately does **not** take `v2-inset`. That hook's hover rule is
`(0,6,0)` with `!important` and would have beaten the trigger's own `v2-bd` / `v2-act` accent hover,
silently replacing it with `--input-border-hover`. Noted in the code at the class list.

### 3.6 Interactivity added by `act()`

Eleven sites were plain `<span onClick>` with no role and no tab stop. Through the primitive they
gain `role="button"`, `tabIndex="0"` and Enter/Space, and therefore theme.css's
`[tabindex="0"]:focus-visible` ring **while focused from the keyboard**:

`Companies` Run · Test · ⋯ · `Searches` Run · Test · ⋯ · `ResumeEditor` Template · Paper ·
`CoverLetterEditor` Template · Paper · `JobFeed` "?" badge.

Rest-state paint is unchanged; only the focus state is new, and it is the app's existing ring.

### 3.7 Element and attribute changes

- `JobFeed.jsx` selected ✓ badge: `<div>` → `<span>`; both carry `display: flex`, so the computed
  `display` is the same.
- `GlyphBadge` sets `aria-hidden="true"` on a badge with no handler, title or label — the Feed's ✓
  and the toast mark are decorative and were being announced as loose glyphs.
- `ToolbarTrigger` emits `aria-haspopup="listbox"`; `IconButton` at the two ⋯ sites emits
  `aria-expanded` / `aria-haspopup="menu"`. Neither is a style.

### 3.8 Structure — unchanged everywhere it matters

`FooterRow`, `TableRow`, `ToolbarTrigger`, `Mono`, `GlyphBadge` and `Notice` each render exactly the
box their site rendered, with the same children in the same order. `Notice` renders its `action`
**as a direct child**, not in a wrapper, so the acknowledge link keeps its own
`flex: 0 0 auto; align-self: flex-start`.

---

## 4. The crawl's own re-keying

`stylescan.py` classifies by tag + className + inline style keys. Where a site's design keys move
into a primitive, its remaining inline object becomes `layout` and the role loses a signature. This
is the intended direction, not a diff to explain:

| role | before (sig/sites) | after |
|---|---|---|
| `header-row` | 6 / 7 | 1 / 1 |
| `mono-text` | 14 / 16 | 6 / 6 |
| `card-static` | 20 / 21 | 13 / 14 |
| `surface-block` | 40 / 53 | 37 / 45 |
| `helper-text` | 14 / 23 | 13 / 18 |
| `row` | 3 / 3 | 4 / 4 |
| `pill` · `icon-btn` · `dot-or-badge` | 0 / 0 | 0 / 0 |
| `layout` | 58 / 749 | 59 / 773 |

`row` gains two `ui.jsx` entries (TableRow, FooterRow — the primitives themselves) and loses
`ui.jsx:504` to a line shift. `section-head`'s 7 → 8 is the Companies banner's two inner spans
re-keying inside `<Notice>`; neither carries a design key of its own any more.

---

## 5. What deliberately did NOT migrate

Kept inline with a `// ui: keep` reason, and each one logged in `DECISIONS.md`:

| Site | Why | Decision |
|---|---|---|
| `Stats.jsx:690` scheduler Run pill | a fourth 25 px signature: no ground, pad `0 11`, gap 6, and a running state that quiets the *border* and the *ink* rather than dimming | D-13 |
| `Searches.jsx` Run / Test pills | pad `0 9` against Pill xs's canonical `0 10` — pinned through `style`, so the pixels are identical and the disagreement stays visible | D-13 |
| `Companies` · `Searches` open ⋯ | takes the on-trio's fill and border but keeps `--pill-ink` for the glyph | D-15 |
| `JobFeed.jsx` "?" badge | outline on `--line` with no ground and a 10 px glyph, against GlyphBadge's `--edge` / `--surface` / 9.5 | D-14 |
| `Settings.jsx:1081` 22×22 ✕ | outline on `--line`, ink `--edge`, `v2-hover-bad-bdc` — three tokens off the outline tone | D-14 |
| the seven small controls' inherited 1.5 line box | `v2-ctl` would lift their glyph a device pixel | D-16 |
| `JobFeed.jsx:1084` "+N reports" count | not a round box: `min-width 16` with `padding 0 3`, so it grows with the number | — |
| `Stats.jsx:104` `MONO` const | three sites left, each overriding the role's 10.5 with its own 11.5 / 10 / 10 | — |
