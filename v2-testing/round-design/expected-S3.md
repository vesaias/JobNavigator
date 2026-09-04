# expected-S3 — ui.jsx reads the theme tokens (Skins handoff §4, items 1–9)

Gate: `bash v2-testing/tools/gate.sh S3 S2f`.

**The default theme must be pixel-identical.** Every name a primitive started
reading resolves, in `.jn-v2` and `.jn-v2[data-appearance="dark"]`, to exactly the
literal it replaced — the four still-open decisions (D-05…D-08) and the two
proposals the board tags **P** (U-02 primary/danger hover, U-01 pressed) are held
inert in the base blocks and live only in cobalt/saas/win98. So:

- **`shotdiff.py S2f S3` → 0 changed pixels** on every route, light and dark.
- **`stylediff.py S2f S3` → 0 changed tuples**, with the two exceptions in §3.
- `stylediff` **will** report a large `missing` + `added` list. That is expected
  and is not a visual change — see §1.

---

## 1 · Key renames (missing + added, zero computed change)

`stylecrawl.py` builds an element's key out of `tag.class1.class2`, so a primitive
that gains a class gets a *new key*: the old one lands in "Missing in S3" and the
new one in "Added in S3", both with identical style tuples. Every class below is a
hook for a rule that is inert in the default theme.

| primitive | class added | why | what the class rule paints here |
|---|---|---|---|
| Button `primary` | `v2-btn-primary` | `:hover`/`:active` state rules | nothing — `--btn-primary-hover-bg` = `--btn-primary-bg`, `--btn-primary-pressed-bg` = `--btn-primary-bg`, `--pressed-shift` = `none` |
| Button `ai` (new variant) | `v2-btn-primary` | same, per the board | as above |
| Button `danger` | `v2-btn-danger` | `:hover` state rule | nothing — `--btn-danger-hover-bg` = `--btn-danger-bg` |
| Pill · Chip · IconButton 36 · Segmented non-inset cells | `v2-raised` | win98 bevel | nothing — each carries an inline `border`/`box-shadow` that beats the rule, and the rule's own values are `none`/`transparent` |
| Menu · ModalPanel · ToastCard | `v2-raised` | win98 bevel | nothing — inline `border` + `box-shadow` |
| Input · Textarea · SearchInput (both variants) · Select trigger | `v2-inset` | win98 bevel **and** the field-hover hook | nothing — inline `border` + `box-shadow`; the hover rule resolves to the field's own rest border |
| SearchInput `variant="underline"` | `v2-underline` | carve-out from the field-hover rule (it rests on `--input-underline`) | nothing |
| Select trigger | `v2-select-trigger` | a named hook for the field-hover rule (the trigger is a div, so `input:hover` never reaches it) | nothing |

The class is dropped while a Button is `disabled`/`busy` (a disabled control has no
hover), so a disabled button keeps its old key.

Segmented's **inset** cells go from `className={undefined}` to `className=""`
(`cx()` of nothing). `e.className` is falsy either way, so the crawl key is
unchanged; only the DOM gains an empty `class` attribute.

## 2 · New markup that does not exist in the default theme

- `HeaderRow variant="titlebar"` — the 22 px `_ □ ×` caption bar. `ModalPanel` and
  `Drawer` mount it **only** when `useTitleBar()` is true, i.e. when `--title-bar`
  is a gradient. It is `none` in every theme that ships today except win98, so no
  panel grows a bar and no route gains an element.
- `ScoreRing` variants `bar` · `pill` · `ascii` — chosen by `--ring-variant`, which
  is `ring` in every theme but the three boards. The default theme takes the
  original branch, unchanged line for line.
- Both read the cascade through one cached `getComputedStyle` per
  (theme, appearance, name) — not per mount. On the very first frame the cache is
  cold and the fallback (`ring` / `none`) is used, which is the default theme's own
  value, so there is nothing to flash.

## 3 · The two sites where a computed value CAN move

1. **`Stats.jsx:691` — the scheduler "Run now" pill, while its job is running.**
   It is the one hand-rolled control in the screens that writes
   `aria-disabled` without an inline `opacity`, so the new
   `.jn-v2 [aria-disabled="true"] { opacity: var(--disabled-opacity) }` rule reaches
   it: `opacity 1 → 0.5` for as long as the run lasts. Every primitive writes
   `opacity: var(--disabled-opacity)` inline (= `.5`, the number it wrote before),
   so none of them moves. The crawl runs with the scheduler paused and no job
   active, so this state is not reachable in the gate — listed because it is a real
   behaviour change, and a correct one (a disabled control should read disabled).
2. **`TableHead` ground: `var(--bg)` → `var(--head-bg-page)`.** The palette-leak
   re-point from handoff §4.11, done while the component was open.
   `--head-bg-page: var(--bg)` in both base blocks, so the resolved colour is
   byte-identical; it only stops win98 painting its *desktop* teal behind a column
   strip. No other §4.11 item is in this pass.

Everything else that changed is a `var()` standing where a literal stood:
`1px` → `var(--bw-control)` / `var(--bw-panel)` / `var(--bw-hair)` (all `1px`),
`500` → `var(--btn-weight)` (`500`), `400` → `var(--title-weight)` (`400`),
`.13em` → `var(--label-tracking)` (`.13em`), `.11em` → `var(--label-tracking-strip)`
(`.11em`), `.06em` → `var(--tag-tracking)` (`.06em`), `uppercase` →
`var(--label-case)` (`uppercase`), `-.02em` → `var(--display-tracking)` (`-.02em`),
`0.5` → `var(--disabled-opacity)` (`.5`), `solid` → `var(--row-line-style)`
(`solid`), and five shadows that are `none`: `--btn-shadow`, `--pill-shadow`,
`--field-shadow`, `--card-shadow`, `--seg-on-shadow`.

## 4 · theme.css: base values re-pointed so the new rules stay inert

| token | was (handoff / step 1) | now | why |
|---|---|---|---|
| `--btn-primary-hover-bg` | `color-mix(… 90%, black)` | `var(--btn-primary-bg)` | U-02 is tagged **P**; a primary button has no hover today |
| `--btn-primary-pressed-bg` | `color-mix(… 82%, black)` | `var(--btn-primary-bg)` | U-01 / D-07 open |
| `--btn-danger-hover-bg` | `color-mix(… 90%, black)` | `var(--btn-danger-bg)` | as above |
| `--pressed-shift` | `translateY(1px)` | `none` | D-07 open |
| `--pressed-wash` | `var(--surface-2)` | `transparent` | D-07 open |
| `--input-border-hover` | `var(--line-strong)` | `var(--input-border)` | D-06 open — = the field's rest border, so hover is a no-op |
| `--disabled-ink` | `var(--muted)` | `inherit` | D-08 — the rule must not repaint a disabled control that sets no colour of its own |
| `--rail-active-mark` | `2px solid var(--rail-accent)` | `3px solid var(--rail-accent)` | V2App widened its accent edge to 3 px (and pads 1 px short to compensate); 2 px would have shifted every rail label |
| `--label-tracking-strip` | *(new)* | `.11em` | TableHead's tracking is a third value, kept as a third name |
| `--tag-tracking` | *(new)* | `.06em` | Tag's tracking, likewise — handoff §4.7 says do not unify |
| `--disabled-opacity` | `.5` | `.5` (kept) | `.5` **is** the inline dim every primitive already wrote, so the token can be read inline and the default theme does not move |

Both new tracking names are declared in all eight blocks that declare
`--label-tracking` (the two base blocks + cobalt/saas/win98 × light/dark), at that
block's own value, so the "every theme block declares the identical set of names"
contract holds.

`.jn-v2 [tabindex="0"]:focus-visible` gained `!important` on its `box-shadow`.
Required, not cosmetic: Button, Pill, Chip, the Select trigger, Segmented's picked
cell and a selected Row now write `box-shadow` inline (`--btn-shadow`,
`--pill-shadow`, `--field-shadow`, `--seg-on-shadow`, `--row-selected-edge` — all
`none` here), and an inline declaration beats a class rule. Without the flag the
keyboard focus ring would have disappeared from every one of them. The painted
ring is unchanged.

## 5 · Deliberate omissions (so a later crawl does not read them as drift)

- **`v2-raised` is NOT on IconButton 26 or Drawer.** Both lack a full inline
  `border`, so the bevel rule would hand them its own `border-color: transparent`
  in the themes where it is inert — a `borderTopColor` move for zero pixels.
  win98 draws small glyph buttons flat and keeps the drawer's hard shadow.
- **`v2-pill` is still not on Pill.** The `[aria-pressed="true"]:hover` rule is
  tagged **P** and would darken an ON pill on contact; not writing the class is
  what keeps it inert.
- **The blanket transition rule is still held back** — it would give `.v2-row`,
  `.v2-menuitem`, `.v2-bd`, `.v2-bdc` and `.v2-act` hover fades they do not have.
- **`Heading strong` keeps its own weights and tracking** (500/600 at −.01/−.015em
  per size). `--title-weight` / `--display-tracking` are the 400-weight display
  scale's names; only the plain scale reads them.
- **`SectionHead` reads none of the three label names.** It is 12.5 px sentence-case
  body text, not a caps label: `--label-case` would put every section head in
  uppercase and `--label-tracking` would space it out. Its weight is inherited from
  the card head it sits in, and pinning it to 400 would flatten that.
- **`ShowMore`** still writes `1px solid var(--pill-border)`. Handoff §4b wants it
  folded into `Pill size="sm"`; that is a composition change, not a token read.
- **Chip's on-state is inline**, from `--chip-on-bg/-ink/-border`, rather than
  through the proposed `.v2-chip[aria-pressed="true"]` rule — same tokens, and no
  cascade fires for a chip that never sets `on`.
