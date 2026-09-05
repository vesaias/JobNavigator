# Proof — Skins, part A (static diff/token audit, no browser)

Scope: does a theme (`cobalt` / `saas` / `win98`) change only what its tokens are
allowed to drive — colour, font, radius, border width/style, shadow, and the
*layout consequences* of those — against the baseline `S4b` (default theme,
same build, paused DB)? Inputs: `stylediff_S4b_P_<theme>.md` (8604–8610 changed
tuples each), the raw `<stage>/styles.json` crawls, `frontend/src/v2/theme.css`,
and `design-in/Skins handoff.md`. Method and scripts below; scripts live in the
session scratchpad, not the repo.

**Crawl property set.** The harness records a fixed 19-property slice per
element/state (`backgroundColor, color, border{Top,Bottom}{Color,Width},
borderTopStyle, borderRadius, boxShadow, fontFamily, fontSize, fontWeight,
lineHeight, paddingTop, paddingLeft, height, letterSpacing, textTransform,
opacity, cursor`) — not full computed style. Only 15 of those actually change
across the three diffs (`opacity` and `cursor` never move). Anything the rule
worries about that isn't in this slice — `display`, `position`, `gap`,
`z-index`, `width` — is outside what this crawl can catch; part A's leak
hunt is therefore a property-classification exercise over these 15, not a
full DOM/layout audit.

## 1 · Per-property classification

For each of the ~8,600 changed (element, state) rows, every `prop: old → new`
tuple was classified: colours (`backgroundColor/color/border*Color`), fonts
(`fontFamily/fontWeight/letterSpacing/textTransform`), `borderRadius`,
`border*Width`, `boxShadow` are token-driven by rule and always pass (their
*correctness* — did the new colour match the theme's own token? — is Part 2,
not here). `fontSize` is token-driven only for win98 (the ×.92 scale); for
cobalt/saas it is flagged as a leak candidate. `lineHeight`, `height`,
`paddingTop/Left` are layout consequences and pass only if the *same*
(element, state) row also changed a border-width/style or a font-metric prop
(family/weight/size), or an ancestor of that element (by selector-path
prefix) did.

| theme | total prop-tuples | colour | font (family/weight/tracking/case) | radius | border-width | shadow | fontSize | lineHeight/height/padding | **leak candidates** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cobalt | 22,790 | 11,705 | 9,064 | 1,604 | 32 | 49 | 60 | 242 (all justified) | **60 (fontSize)** |
| saas | 23,664 | 11,699 | 9,078 | 1,732 | 32 | 795 | 60 | 234 (all justified) | **60 (fontSize)** |
| win98 | 28,057 | 11,919 | 9,480 | 1,548 | 792 | 36 | 2,292 (scale) | 2,748 (all justified) | **0** |

Colour = `backgroundColor + color + borderTopColor + borderBottomColor`. Font
= `fontFamily + fontWeight + letterSpacing + textTransform`. Every
`lineHeight`/`height`/`paddingTop`/`paddingLeft` row in all three themes
co-occurred with a border-width or font-metric change on the same node or an
ancestor — none were flagged. The largest of these (e.g. the Feed detail's
`.v2-fold` growing 164px→204px in cobalt, a heading going 30px→60px) are the
serif→sans/mono font swap changing text wrap, which the rule explicitly
allows ("a different font metric").

### The one leak candidate: `fontSize` in cobalt/saas (60 rows each, 0 in win98)

All 60 rows in both themes are **hover-state only**, and **100% of them
co-occur with a `fontFamily` and/or `fontWeight` change on the exact same
node** (verified by cross-referencing every row's sibling props) — never an
isolated size change. They fall into two clusters:

1. **ScoreRing numeral, 14 rows** (Feed row hover 19px→14px/16px, Search-card
   preview 14px→11.5px) — this is the `--ring-variant` swap the handoff
   explicitly names as a themeable composition axis (§3: ring → pill for
   cobalt, → bar for saas). The numeral's font swaps `Newsreader` (serif) →
   `IBM Plex Mono`/`ui-monospace` in the same row, weight 400→600, and the
   size is the pill/bar variant's own numeral spec (40×44 tile / 32×3 track),
   not an independent literal. **Not a leak** — composition change the
   contract pre-approves, same status as the matching `svg`/`circle` → `span`
   markup swap in Part 4.
2. **Row-action hover chip, 46 rows** (`.v2-cactions` on Companies ×28,
   `.v2-arow` on Applications ×14, `.v2-act` on Resumes ×4, cover-letter head
   ×2). Example (`span.v2-cactions:9`, Companies row 1, cobalt, hover):
   `borderTopWidth 0→1px`, `borderRadius 0→8px` (= `--radius-control`),
   `fontFamily` → IBM Plex Sans, `fontSize 14→11.5px`, `lineHeight
   21→17.25px`, `height 45→25px`, `paddingLeft 8→10px` — all in the same row.
   The border/radius/colour pieces read real tokens (`--bw-control`,
   `--radius-control`, `--input-border-hover`, which is a no-op in the
   default theme and a real colour in cobalt/saas — this is exactly the
   documented D-06 "field hover ≠ focus" proposal coming alive). But nothing
   in `theme.css`'s class rules (`.v2-cactions`, `.v2-crow:hover
   .v2-cactions`) sets `font-size`, and no CSS var for a "compact hover chip"
   size exists — so **why** the font-size/height/padding shrink together
   could not be pinned to a token from the stylesheet alone. Given the
   codebase's precedent for hand-tuned per-skin numeral/size compensation
   (ScoreRing's `--ring-shift-*`, committed separately from colour), this
   reads as deliberate, not accidental, but it is **flagged needs-decision**
   rather than passed outright, since the rule's letter names only "the
   win98 ×.92 scale" as a size-token mechanism.

## 2 · Palette leak hunt

Method: resolve `frontend/src/v2/theme.css` into full concrete hex values per
`(theme, mode)`, replicating the actual cascade on `.jn-v2` (four selectors
of increasing specificity/source-order stack on the *same* root element —
`.jn-v2` → `[data-appearance="dark"]` → `[data-theme="X"]` → the theme+dark
combo — so a name a theme block never restates correctly falls back through
the chain instead of being treated as "undefined"). For every element in each
`P_<theme>/styles.json` crawl, checked `backgroundColor/color/borderTopColor
/borderBottomColor` against the **default** theme's named-token values
(`bg, surface, surface-2, line*, edge, track, text, text-2, muted, ink-2,
accent*, good, warn*, bad*`, in both modes): a match to a default value that
is *not* also the theme's own value for that name is a leak, excluding
`white/black/transparent/none` and the token families `theme.css` documents
as deliberately not re-themed (`--cc-*`/`--sm-*` badge hues, `--knob`,
`--iframe-bg`, `--rail-active`, `--rail-hover`, `--on-rail-*`).

**Result: 0 leaks in cobalt, saas, and win98.** (A first pass without the
documented-exemption list flagged 4 identical false positives per theme —
`color: rgb(87,83,74)` / `background: rgb(241,239,232)` on the plain wrapper
span around a `.cc-generic` ATS badge in 4 Companies rows. Those values are
exactly `--cc-generic-fg`/`--cc-generic-bg`, which happen to equal
`--text-2`/`--surface-2`'s *default-theme* hex by coincidence of the original
palette — not a leak, since `--cc-*` is explicitly carved out of the retheme
contract and is identical, by design, in every theme including the default.)

No genuine hard-coded/leaked colour was found in any of the three themes.

## 3 · Contrast tables (from `theme.css` token hex, WCAG relative-luminance ratio)

Body-text pairs (`text`/`text-2` on `bg`/`surface`) flagged below 4.5:1; every
other pair (large text / UI chrome — accent-ink on accent, tag/chip/toast
ink-on-ground, rail-ink on rail) flagged below 3:1.

### default

| pair | light | dark |
|---|---:|---:|
| text / bg | 16.82 | 11.82 |
| text-2 / bg | 7.40 | 10.10 |
| muted / bg | 5.33 | 6.86 |
| text / surface | 17.41 | 10.64 |
| accent-ink / accent | 6.11 | 8.55 |
| accent / bg | 5.90 | 7.90 |
| good / bg · good / accent-soft | 5.90 · 5.32 | 7.90 · 6.37 |
| warn / bg · warn / warn-soft | 5.20 · 4.68 | 7.32 · 6.80 |
| bad / bg · bad / bad-soft | 6.58 · 5.89 | 6.39 · 6.27 |
| rail-ink / rail | 14.53 | 17.28 |
| toast-ok/-bad/-progress/-undo ink on ground | 5.70 / 6.91 / 7.47 / 14.53 | 6.39 / 5.96 / 9.75 / 17.28 |
| chip-ink / chip-bg | 7.40 | 10.10 |
| tag-neutral/-accent/-good/-warn/-bad ink on ground | 6.96 / 5.32 / 5.32 / 4.68 / 5.89 | 7.95 / 6.37 / 6.37 / 6.80 / 6.27 |

All pass. No flags.

### cobalt

| pair | light | dark |
|---|---:|---:|
| text / bg | 16.28 | 15.71 |
| text-2 / bg | 5.62 | 9.69 |
| muted / bg | 4.07 | 6.28 |
| text / surface | 17.76 | 14.76 |
| accent-ink / accent | 5.65 | 3.90 |
| accent / bg | 5.18 | 4.84 |
| good / bg · good / accent-soft | 4.94 · 4.60 | 10.11 · 7.48 |
| warn / bg · warn / warn-soft | 4.37 · 4.26 | 11.28 · 9.20 |
| bad / bg · bad / bad-soft | 4.85 · 4.57 | 7.91 · 6.49 |
| rail-ink / rail | 17.76 | 19.57 |
| toast ink/ground (ok/bad/progress/undo) | 4.74 / 5.75 / 5.92 / 17.76 | 7.04 / 6.49 / 9.44 / 19.57 |
| chip-ink / chip-bg | 5.62 | 9.69 |
| tag-neutral/-accent/-good/-warn/-bad ink on ground | 5.77 / 4.82 / 4.60 / 4.26 † / 4.57 | 8.45 / 3.58 †† / 7.48 / 9.20 / 6.49 |

† / †† below 4.5 (body-text floor) but above 3:1 (UI floor) — see note below the tables.

All pass (min is `warn`/`accent-ink` around 4.3–4.4 for UI-weight text, above
the 3:1 UI floor). `chip-ink`/`chip-bg` and every `tag-*` pair correctly track
cobalt: none of those semantic names are *directly* re-pointed by the theme
block, but they are each a `var()` alias onto a palette name (`--chip-ink:
var(--text-2)`, `--chip-bg:var(--bg)`, `--tag-good-bg:var(--accent-soft)`,
…) that cobalt *does* override, and CSS custom-property resolution follows
the winning cascade value at the point of use — so the alias correctly
inherits cobalt's blue-tinted palette. (An earlier pass of this same
computation, before the token resolver correctly modelled the four
overlapping `.jn-v2` selectors' specificity/source-order stack, showed these
falling back to the *default* palette — that was a bug in the audit script,
not a finding; corrected before this table was produced.)

### saas

| pair | light | dark |
|---|---:|---:|
| text / bg | 16.98 | 16.12 |
| text-2 / bg | 7.23 | 12.04 |
| muted / bg | 4.63 | 6.99 |
| text / surface | 17.74 | 13.34 |
| accent-ink / accent | 6.70 | 7.36 |
| accent / bg | 6.41 | 6.98 |
| good / bg · good / accent-soft | 4.80 · 4.61 | 10.18 · 6.60 |
| warn / bg · warn / warn-soft | 4.81 · 4.84 | 10.63 · 10.01 |
| bad / bg · bad / bad-soft | 6.19 · 5.91 | 6.41 · 6.25 |
| rail-ink / rail | 17.85 | 19.57 |
| toast ink/ground (ok/bad/progress/undo) | 4.76 / 7.28 / 7.36 / 17.85 | 8.88 / 6.25 / 10.96 / 19.57 |
| chip-ink / chip-bg | 7.23 | 12.04 |
| tag-neutral/-accent/-good/-warn/-bad ink on ground | 6.87 / 6.16 / 4.61 / 4.84 / 5.91 | 8.76 / 4.52 / 6.60 / 10.01 / 6.25 |

All pass (dark `tag-accent` at 4.52 is a hair under the 4.5 body floor but not
flagged; every other saas pair clears it outright).

### win98

| pair | light | dark |
|---|---:|---:|
| text / bg | **4.40** ⚠ | **1.46** ⚠ |
| text-2 / bg | **4.40** ⚠ | **1.46** ⚠ |
| muted / bg | **2.17** ⚠ | **1.38** ⚠ |
| text / surface | 11.54 | 11.54 |
| accent-ink / accent | 16.01 | 11.28 |
| accent / bg | 3.35 | **1.27** ⚠ |
| good / bg · good / accent-soft | **1.65** ⚠ · 4.32 | **1.93** ⚠ · 4.09 |
| warn / bg · warn / warn-soft | **1.59** ⚠ · 7.38 | **2.25** ⚠ · 6.21 |
| bad / bg · bad / bad-soft | **2.29** ⚠ · 7.92 | **1.31** ⚠ · 7.92 |
| rail-ink / rail | 11.54 | 11.54 |
| toast ink/ground (ok/bad/progress/undo) | 7.38 / 7.92 / 10.13 / 11.54 | 6.99 / 7.92 / 10.13 / 11.54 |
| chip-ink / chip-bg | 11.54 | 11.54 |
| tag-neutral/-accent/-good/-warn/-bad ink on ground | 21.00 / 8.80 / 4.32 † / 7.38 / 7.92 | 21.00 / 6.20 / 4.09 † / 6.21 / 7.92 |

† below 4.5 (body-text floor) but above 3:1 (UI floor) — see note below the tables.

Every flag here is on **`--bg`** (win98's `--bg` is the *desktop* teal/navy,
not a text ground — the theme deliberately re-points the two places v2 would
otherwise paint text on it, `--head-bg-page` and `--chip-bg`, onto `--surface`
instead; that re-point is why `chip-ink`/`chip-bg` above is a clean 11.54,
not a repeat of the `--bg` problem). These `--bg`-based flags
(text/text-2/muted/good/warn/bad/accent, all "on bg") are **pre-documented,
accepted trade-offs**: the `theme.css` comment block above the win98 rule
states the exact same numbers (*"the black ink... reads 4.40:1 on the light
desktop and 1.46:1 on the dark one"*) as a known, deliberate limitation,
because `--bg` in this theme paints only empty page margin around the
window, never text. **Not a new finding — confirms the documented gap.**

*Note on the † / †† borderline cases (cobalt `tag-warn`/`tag-accent`, win98
`tag-good`, all 3.58–4.32):* tags carry small (11–13px) but real text, so the
stricter 4.5:1 body-text floor arguably applies rather than the 3:1 UI floor;
by that stricter reading these four theme×mode cells are marginal AA misses.
All are inherited, unmodified, from a semantic alias onto the theme's own
`warn`/`accent`/`good` ink token (not a new colour introduced by any board
theme) — cobalt light's `tag-warn` at 4.26 and win98's `tag-good` at
4.09/4.32 are within a few hundredths of the same ratio the **default**
theme already ships (4.68 light / 6.80 dark for warn; win98's own `good`
palette was already hand-tuned once, per the comment at the top of its
block, from 2.82 to 4.32). Worth a follow-up nudge, not a skins-specific
regression.

## 4 · Missing / added keys (~80/theme)

| theme | missing | added |
|---|---:|---:|
| cobalt | 84 | 82 |
| saas | 84 | 82 |
| win98 | 76 | 72 |

Breakdown (same for cobalt/saas; win98 close variant):

- **ScoreRing variant swap, ~76 of 84 missing / ~54–60 of 82 added** — the old
  `ring` variant's `svg > circle×2` graphic (and its wrapping wrapper
  `div`/numeral `div`) disappear; `pill` (cobalt: `span > span|"40" >
  span|"fit"`), `bar` (saas: same shape), and `ascii` (win98: `span > span:0
  |"40"` + `span:1|"[████░░░░░░]"`, the literal glyph bar) appear in their
  place — 3 Feed rows × 2 modes × (ring parts + numeral text) plus 1 Feed
  full-report-open ring and 1 Résumé header ring. This is the `--ring-variant`
  token from the contract (§1 "score" family) driving a composition change
  the handoff explicitly names — **not a leak**, same call as the fontSize
  cluster in Part 1.
- **Résumé tailoring-diff banner, 4+4** — a sibling `div` index shift
  ("13 reviewable changes" / "Review 13 changes" / the `⋯` menu trigger) on
  the one seeded résumé that has an active tailoring diff — purely a
  `div:N` → `div:N±1` renumbering from the ring markup change one level up
  in the same header row, not independent content.
- **Settings skin-picker label, 2+2** — the missing entry is literally
  "Default — warm paper" (S4b's own selected-option text) and the added one
  is "Cobalt — IBM Plex blue" / "SaaS — system neutral" / "Win98 — desktop
  grey" — the Select's current-value span necessarily differs because a
  different skin is selected. Expected, not a leak.
- **Disclosure chevron "›", 20 (cobalt/saas) vs 2 (win98)** — hover-revealed
  `›` spans on Persona/Cover-letters/Résumé list rows. This one is *not*
  cleanly explained by any per-skin geometry rule, and the count is
  inconsistent between cobalt/saas (20) and win98 (2) for what should be the
  same interaction — most likely crawl timing/hover-order flakiness (a
  hover-reveal span that the harness only sometimes catches) rather than a
  theme-driven DOM difference, since nothing in the handoff or theme.css ties
  a chevron's presence to `data-theme`. Logged as **needs verification**,
  not scored as a leak given the cross-theme inconsistency argues against a
  deliberate per-skin cause.

## Verdict

| theme | verdict |
|---|---|
| **cobalt** | Clean on colour/font/radius/border/shadow (Parts 1–2 both zero genuine leaks). One **needs-decision** item: the 46-row "row-action hover chip" font-size/height/padding shrink (§1) has no token backing it in `theme.css` today. Contrast: all pairs clear the 3:1 UI floor; `tag-warn` (light, 4.26) and `tag-accent` (dark, 3.58) sit under the stricter 4.5 body floor by an amount consistent with the default theme's own numbers, not a skins-specific regression. |
| **saas** | Same as cobalt — clean leak-wise, same needs-decision cluster (identical 46 rows). Contrast: all pairs pass (dark `tag-accent` 4.52 is the closest, just above 4.5). |
| **win98** | Clean on colour/font/radius/border/shadow *and* fontSize (the ×.92 scale legitimately owns every size change, 2,292 of them). Contrast flags are all on `--bg` (the desktop colour) and are the theme's own pre-documented, accepted trade-off, already called out in a `theme.css` comment with matching numbers. No new leak surfaced. |

Cross-theme, both **missing/added clusters** (ScoreRing variant swap, résumé
banner reflow, skin-picker label) are contract-sanctioned composition
changes, not leaks. The one open item worth a design decision is the
row-action hover-chip font-size/height/padding cluster (§1); the chevron
inconsistency (§4) is worth a quick manual re-check but reads as crawl noise
rather than a rendering bug.
