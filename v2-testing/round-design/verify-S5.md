# verify-S5 — fix verification against fresh screenshots

Before: `v2-testing/artifacts/design/P_win98/`, `P_cobalt/`. After: `P2_win98/`,
`P2_cobalt/` (52 PNGs each, `<route>__<light|dark>__<width>.png`). Findings
source: `proof-skins-B.md`. Fix description source: `expected-S5.md`. All crops
below were done with PIL in the scratchpad and read back with the Read tool;
pixel samples were taken with `im.getpixel()`.

---

## 1. win98 Feed selected row — text on navy fill

**Fixed.**

`v2_feed__light__1440`, before vs after, row 1 ("Agentic Experience Product
Manager · JPMorgan Chase · $163K · H-1B Likely · just now"):

- Before: title/company/meta rendered near-black on the navy row fill —
  confirmed by pixel sampling text-stroke pixels at ~RGB(0,0,0)–(20,20,20)
  against a (0,0,128) fill, unreadable.
- After: the same three lines render in a light blue-white ink, clearly
  legible against the navy fill. Sampled visually via 3x crops; the title,
  company line, and meta line (`$163K · H-1B Likely · just now`, including the
  green "H-1B Likely" span, which now inherits the row's white ink instead of
  keeping its own green) are all white/near-white.
- `v2_feed__dark__1440`: same result — selected-row fill is a lighter
  navy/slate in dark mode (correct per-mode re-derivation, not a bug) and all
  three text lines are white/legible there too.

**Rail glyph cells (♥ ✕ ⋯), as flagged "known to remain dim":** confirmed
still dim in both before and after, unchanged by this fix. On the selected
row: the ♥ (heart) renders solid black, filled, clearly visible; the ✕ and
⋯ glyphs render as a dim muted brownish-gray outline against the navy cell,
noticeably lower contrast than the heart but not invisible. This matches the
task's expectation and is not treated as a defect.

## 2. win98 bevels — pills, buttons, ⋯ icon button, fields, select trigger

**Fixed** for real bevel-hook carriers; **one pre-existing hand-drawn
exception noted, not a defect of this fix.**

- Feed toolbar (`v2_feed__light__1440`): before, "Search titles…" input and
  the Source/Company/H-1B/Score/Salary/Status pills all show a flat uniform
  `#404040`-ish border on all four sides. After, the search input shows a
  clear **inset** bevel (dark border top/left, light bottom/right) and every
  filter pill shows a clear **raised** bevel (light top/left edge, dark
  bottom/right edge) — classic Windows-98 3D look, confirmed at 4x zoom.
- Companies row-action `IconButton` ("⋯" per row, `v2_companies__light__1440`):
  before flat border; after a clean raised bevel (light top-left, dark
  bottom-right), 8x zoom confirmed.
- Settings Select triggers ("Light", "Win98 — desktop grey", provider/model
  selects, `v2_settings__light__1440`): all show the inset bevel (dark
  top/left, light bottom/right), same as the search input.
- Cover Letters Voice/Length pills (`v2_cover-letters__light__1440`): raised
  bevel visible on all six pills.
- Applications status pills (Applied/Interview/Offer/Rejected) and Searches'
  Run/Test/Active/Paused pills: all show the raised bevel consistently.
- **Exception**: the "⋯" *More actions* control in the Feed **detail-pane
  header** (next to "Open ↗" / "Tailor résumé") is a hand-drawn `<div
  className="v2-act">`, not the `IconButton` component — it never carried the
  `v2-raised` class before or after, so it still shows a flat gray border in
  both `P_win98` and `P2_win98`. This is outside the scope of the S5 fix
  (`expected-S5.md` only touches the JobFeed "Tailor résumé" CTA, §8) and is
  identical before/after — not a regression, just a control that was never
  wired to the bevel hook.
- Hover state on a field: not present in any static shot, skipped per
  instructions.
- Menus/toasts: not present selected/open in any shot, skipped per
  instructions.

## 3. win98 label case — rail group headers and Base/Tailored badge

**Fixed.**

- Rail group headers: before "FIND" / "APPLY" / "YOU" in tracked small caps;
  after "Find" / "Apply" / "You" in sentence case with no visible
  letter-spacing, confirmed on `v2_feed__light__1440` (and consistent on every
  other win98 route, since the rail is shared chrome).
- Résumé editor Base/Tailored badge: `v2_resumes_22ce0e5b-...__light__1440`
  (base copy) shows "base" lowercase, no tracking, vs. before's "BASE" tracked
  caps — pixel-zoom confirms both the case change and no letter-spacing.
  `v2_resumes_db3ad036-...__light__1440` (tailored copy) shows "tailored"
  lowercase, same fix.
- Toast lab kind labels ("progress", "success", "error", "undo",
  `v2_toasts__light__1440`) also now read lowercase — consistent with the same
  token fix (`design-base/ToastLab.jsx`, per `expected-S5.md` §6).
- Noted but out of scope for this check: the Settings side-nav group headers
  ("GENERAL", "AI", "PIPELINE", …) and the Cover Letter editor's "DRAFT" badge
  still render as literal caps in both before and after. Per
  `expected-S5.md` these are either already correctly wired to
  `<Label>`/tokens (Settings side-nav — the underlying string itself is
  authored as literal uppercase data) or intentionally left alone (the cover
  letter `badge` value is built with `stage.toUpperCase()` / `'DRAFT'` in
  `CoverLetterEditor.jsx:339`, so the CSS `textTransform:none` token has
  nothing to undo — the source string is already all-caps). Unchanged
  before/after, not a regression.

## 4. win98 disabled primary button — engraved ink

**Fixed.**

`v2_cover-letters__light__1440`, the disabled "✦ Generate cover letter"
button (no résumé/target job picked yet):

- Pixel sample (before): button fill ~RGB(128,128,128); ink stroke pixels
  ~RGB(64,64,64) (`#404040`, the flat `--muted` token) — a plain grey label,
  no shadow.
- Pixel sample (after): the ink itself now samples at ~RGB(128,128,128) —
  identical to the button's own fill — with a `1px`-offset highlight running
  up to RGB(254,254,254) (pure white) along each glyph's lower-right edge.
  Visually this reads exactly as "engraved" — the grey glyph fill disappears
  into the grey surface and only the white shadow edge remains legible,
  matching the spec's `#808080` ink + `1px 1px 0 #fff` shadow pairing.
- No other disabled primary button was found in any of the 52 shots (Feed
  detail always has a job auto-selected; Searches/Companies/Settings buttons
  are all enabled in these fixtures), so Cover Letters' "Generate cover
  letter" was the only example available, as anticipated by the task.

## 5. cobalt Feed detail-pane "Tailor résumé" — drop shadow

**Fixed.**

`v2_feed__light__1440` (cobalt): before, "Tailor résumé" has a hard flat
bottom edge with no shadow, visibly different from "Full report" directly
below it in the fit-panel sub-header, which has a soft blurred drop shadow.
After, "Tailor résumé" shows the same soft cobalt-tinted shadow as "Full
report" (and the button's font-weight now also matches — the fix routed the
control through `Button`, which corrected weight along with the shadow, per
`expected-S5.md` §8). Confirmed at 3x zoom in both light and dark
(`v2_feed__dark__1440` shows a matching subtle glow, harder to see against
the near-black canvas but present and consistent with the other primary CTAs
on that shot).

## Regression scan — every win98 and cobalt 1440 light shot

A pixel-diff pass (`ImageChops.difference`) between `P_*` and `P2_*` for all
1440-light shots, followed by full-page visual review of each win98 image
(applications, companies, cover-letters list + detail, feed, persona, résumés
list + 2 details, searches, settings, stats, toasts — 13/13 routes):

- **Cobalt**: 12 of 13 routes are byte-identical (`applications`, `companies`,
  both `cover-letters`, `persona`, all three `résumés`, `searches`,
  `settings`, `stats`, `toasts`). Only `feed` changed, and only in the
  detail-pane header region (bbox `(323,59)-(1368,197)`, 0.24% of pixels) —
  exactly the "Tailor résumé" button fix in item 5. No other cobalt route
  moved at all.
- **Win98**: every route changed (0.18%–2.34% of pixels), as expected — the
  rail sentence-case fix and the field/pill bevel fix both touch shared
  chrome present on all 13 routes. Full-page review of each route (Read tool,
  1440 light) found no clipping, no broken layout, no misaligned controls, no
  missing content, and no new contrast problems beyond what's already
  described above. Table rows, status pills, chart bands (Stats), the PDF
  preview panel and empty-report chart layouts all look structurally
  identical to before aside from the intended bevel/case changes.

**No regressions found** in either theme.
