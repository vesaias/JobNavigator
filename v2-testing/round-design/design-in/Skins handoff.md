# Skins handoff — Primitives Board → ui.jsx / theme.css

Source of truth: `skins.js` (geometry + state per skin) and `skins-palette.json` (the 60-name palette blocks lifted from `theme.css @539da1e`). `Primitives Board.dc.html` renders from them; `theme-skins.css` is generated from them. Change the object, both follow.

Board: rows = ui.jsx export names (+ six new); columns = editorial · saas · cobalt · win98; states left→right rest · hover · pressed · on · disabled · focus · loading. A **P** tag = proposed (spec §F); a dash = state does not apply.

## 1 · Contract change (U-21)

Per-skin blocks now carry, beyond the 60 palette names:

| family | names | why |
|---|---|---|
| radii (11) | `--radius-mark … --radius-control`, `--radius-rail-item` | saas/cobalt 8px rects; win98 zero |
| border widths (3) | `--bw-hair --bw-control --bw-panel` | U-22; win98 2px controls/panels |
| shadows (10) | the 5 existing + `--btn-shadow --pill-shadow --field-shadow --card-shadow --seg-on-shadow` | saas elevation, cobalt coloured button drop, win98 hard offsets |
| type (20 + 6) | `--t-*` stops + `--btn-weight --title-weight --label-weight --label-tracking --label-case --display-tracking` | saas 750 titles / 700 caps; win98 ×.92 scale, no tracking |
| state (13) | `--btn-primary-hover-bg --btn-primary-pressed-bg --btn-danger-hover-bg --pressed-shift --pressed-wash --motion-fast --motion-mid --ease --disabled-opacity --disabled-ink --disabled-engrave --input-border-error --input-ring-error` | U-01/02/03/05/06 |
| selection (5) | `--row-selected --row-selected-ink --row-selected-edge --row-line-style --divider` | cobalt inset edge, win98 navy, saas accent wash (S6/W12/C4) |
| rail (4) | `--rail-active-bg --rail-active-ink --rail-active-mark --rail-item-inset` | filled tiles (S5/C8) — resolves U-18 partially |
| bevel (6) | `--bevel-{raised,inset}-{border,color,shadow}` | win98 W2; `none` elsewhere |
| ai (2) | `--ai --ai-ink` | Button `variant="ai"`; = accent where a skin has no violet |
| score (8+1) | `--sc-{hi,mid,lo,none}[-bg]`, `--ring-variant` | ScoreRing variants |
| field hover (1) | `--input-border-hover` | Input/Select/SearchInput/ToolbarTrigger hover ≠ focus (proposal; win98 none) |
| on-states (7) | `--pill-on-{bg,ink,border,hover-bg}`, `--chip-on-{bg,ink,border}` | emitted per mode so cobalt/win98 dark carry values (win98 = navy fill) |
| focus (2) | `--focus-ring --focus-outline` | win98 dotted outline instead of a ring |
| title bar (2) | `--title-bar --title-bar-ink` | win98 W4; `none` elsewhere |

Total per block: 60 + 78 names. The generator guarantees light/dark parity; the gate becomes "only tokens may differ" (the recorded decision).

## 2 · Proposed values (spec §F) — same recipe in every skin

- **U-01 pressed**: filled controls → `--btn-primary-pressed-bg` (= `color-mix(in oklab, bg 82%, black)`), bordered → `--pressed-wash` + `--pressed-shift` (1px down; none in saas/cobalt; 1px diagonal in win98 = bevel flips to inset).
- **U-02 primary/danger hover**: `color-mix(... 90%, black)` (88% for saas/cobalt whose accents are brighter). win98: none — the bevel is the affordance.
- **U-03 motion**: `--motion-fast .12s`, `--motion-mid .2s`, `--ease cubic-bezier(.2,.7,.2,1)`; win98 `0s`. One `prefers-reduced-motion` rule zeroes everything (closes U-04).
- **U-05 disabled**: `--disabled-opacity .5` everywhere except Button (keeps its token swap) and win98 (engraved: `#808080` ink + `1px 1px 0 #fff` shadow, opacity 1).
- **U-06 error**: `--input-border-error: var(--bad)`, `--input-ring-error: 0 0 0 2–3px var(--bad-soft)`; hooks on `aria-invalid`. Also gives Textarea/Select the state.
- **U-11 hit target**: rule "interactive ≥ 24px" — RemoveX and MoveArrows get a 24px padded hit box, glyph size unchanged.
- **Chip on-state** (open question in §2 of your answer): `--accent-soft` fill + accent border, like Pill on; win98 navy fill.
- **ON-pill hover**: no border change (already accent); add `--pressed-wash`-style 6% darkening of `--pill-on-bg`. Mark P.

## 3 · Per-skin geometry summary

| | editorial | saas | cobalt | win98 |
|---|---|---|---|---|
| control radius | 99 | 8 | 8 | 0 |
| field / row / card / menu | 6 / 7 / 9 / 10 | 8 / 8 / 10 / 10 | 8 / 0 / 9 / 9 | 0 |
| border width | 1 | 1 | 1 | 2 (hair 1) |
| control shadow | none | 1px soft on every bordered control; primary 12% | primary only, cobalt-tinted | none; bevel |
| panel shadow | soft blur | two-layer + hairline ring | soft + `rgba(0,0,0,.06)` ring | hard `3px 3px 0` |
| display face / weight | Newsreader 400 | system sans 750 | IBM Plex Sans 600 | Tahoma 700 (×.92 scale) |
| caps labels | .13em 400 | .06em 700 | .06em 600 | none, sentence case 700 |
| row selection | surface-2 wash | accent-soft wash | `#eef3fe` + inset 3px accent edge, radius 0 | navy fill, white ink |
| rail active | 2px left bar | filled accent tile, r8, inset 10 | filled `#2c3442` tile, r5 | navy fill |
| ScoreRing | ring | bar (mono numeral + 32×3 track) | pill (40×44 tile, Plex Mono) | ascii (`87 [████████░░]`) |
| focus | 2px ring | 3px accent-soft + 1px accent | same as saas | 1px dotted outline |

## 4 · ui.jsx changes (code, not CSS)

Small, all additive, defaults = today:

1. **Button**: `variant="ai"` (reads `--ai/--ai-ink`); classes `v2-btn-primary`/`v2-btn-danger` so the hover/pressed rules can target them; read `--btn-weight`, `--btn-shadow`, `--bw-control`.
2. **Pill / Segmented / Chip / IconButton**: read `--pill-shadow`, `--seg-on-shadow`, `--bw-control`; add class `v2-raised` (bevel hook, inert outside win98).
3. **Input / Textarea / Select / SearchInput**: read `--field-shadow`, `--bw-control`; `aria-invalid` prop → error paint; class `v2-inset`.
4. **Row**: read `--row-selected-ink`, `--row-selected-edge`, `--row-line-style` (the `aria-current` rule in theme-skins.css does the rest).
5. **Card / Band / Menu / ModalPanel / Drawer / ToastCard**: read `--card-shadow` (Card), `--bw-panel`; `v2-raised` on win98 panels.
6. **ScoreRing**: `variant` from the skin store (mirrors `--ring-variant`; names are a closed set `ring | bar | pill | ascii`, pinned in skins.js). `pill` reads `--sc-*`; `ascii` derives the bar from the score (no new data field needed — `Math.round(score/10)`).
7. **Label / MenuHead / TableHead / Tag / SectionHead**: read `--label-tracking`, `--label-case`, `--label-weight`.
8. **Heading / PageTitle**: read `--title-weight`, `--display-tracking`. win98's title bar is a `HeaderRow variant="titlebar"` (gradient `--title-bar`, 22px, window glyphs) — the one composition change; only mounts when `--title-bar` ≠ `none`.
9. **Rail (V2App)**: active item reads `--rail-active-bg/-ink/-mark`, `--rail-item-inset`, `--radius-rail-item`.
10. **New primitives** (board rows tagged "new primitive"): `PillXs` (25px — or `Pill size="xs"`), `ToolbarTrigger` (24px), `TableRow` (32/34/38, `--row-line-style` divider, no hover by default), `FooterRow` (mirror of HeaderRow, rule on top via `--divider`), `Mono` (`--font-mono`, size + tone props), `GlyphBadge` (15/16/22/34 round glyph box, tone + `ai`), `Notice` (warn ground + CTA slot).
11. **Palette leaks** (U-16): TableHead → `--head-bg-page`; Surface → `--head-bg-recessed`; Toast.jsx marks → `--toast-mark-ok/--toast-mark-bad` (= accent/bad); ConfirmDialog body → `--helper-ink`. Not on the board; listed so they land with the rest.

## 4b · Added rows (round 2)
Drawer · ChoiceModal+ChoiceCard+ChoiceRow (one composition) · Link · RemoveX/RemoveLink/MoveArrows · ModalPanel header (HeaderRow). Cells added: Input/Select/SearchInput/ToolbarTrigger **hover** (P), SearchInput **underline** variant, Pill **on·hover** (P), Chip **on** shown in both modes.

**Composed from existing — no row:** Textarea (= Input rules, multiline, min-height rows×19+13), Spinner (12/14/16px; `weight="bold"` 2px as in ScoreRing busy), Surface (`--head-bg-recessed` ground, radius token), Rule (`--bw-hair` in the three head-line tones), ShowMore (= Pill sm paint + Button-secondary hover; recommend it become `Pill size="sm"` with a label).

## 5 · Known gaps left open

- win98 `--bg` is a desktop colour: `--head-bg-page` and `--chip-bg` should re-point to `--surface` in that skin (semantic re-point; the board already paints cells on `--surface` for win98).
- Floating windows (W7) and the `_ □ ×` bar are composition, not tokens — `HeaderRow variant="titlebar"` covers the bar; the pane margins stay a V2App branch.
- `--cc-*` / `--sm-*` remain unskinned by design.
- a11y items U-09/10/12/13 documented in the spec; not designed here.
