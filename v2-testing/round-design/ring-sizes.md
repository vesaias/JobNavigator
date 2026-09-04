# Score ring sizes: pre-pass (4f3a5f5) vs current `ScoreRing`

## Current primitive (`frontend/src/v2/ui.jsx:896-954`)

`RING_VB = 88` is now a **constant** for every size (was per-site before the primitive existed).
Rendered geometry scales as `scale = box/88`, `r_rendered = 35*scale`, `stroke_rendered = trackValue*scale`.

| preset | box | viewBox | r (rendered) | stroke (rendered) | outer Ø (r+stroke/2)*2 | numeral font |
|---|---|---|---|---|---|---|
| `sm` | 34px | 0 0 88 88 | 13.52px | 1.93px | ~29.0px | `--t-14` = 14px |
| `md` | 44px | 0 0 88 88 | 17.5px | 2.5px | 37.5px | `--t-19` = 19px |

Unscored (`value == null`) state is a plain dashed `<div>` at `z.box` — no SVG/viewBox scaling involved, so it always renders at the literal preset box (34 for sm, 44 for md), label font `--t-7-5` (sm) / `--t-9-5` (md).

## Pre-pass geometry (commit `4f3a5f5`)

| site | file:line | box | viewBox | stroke (literal) | scale (box/vb) | r (rendered) | stroke (rendered) | numeral font |
|---|---|---|---|---|---|---|---|---|
| Feed row ring | `JobFeed.jsx:882-885` | 44×44 | 0 0 88 88 | 5 | 0.5 | 17.5px | 2.5px | 19px |
| Feed report band ring | `JobFeed.jsx:1005-1009` | 34×34 | 0 0 78 78 | 5 | 0.4359 | 15.26px | 2.18px | 14px |
| Feed "No fit" (unscored) box | `JobFeed.jsx:1141` | 34×34, dashed border, no SVG | — | — | — | — | — | 7.5px, uppercase, `.1em` |
| ResumeEditor band ring | `ResumeEditor.jsx:478-483` | 34×34 | 0 0 78 78 | 6 | 0.4359 | 15.26px | 2.62px | 13.5px |

## Current call sites (as of this branch)

- `JobFeed.jsx:908` (row) → `size="md"`
- `JobFeed.jsx:1050` (report band) → `size="md"` **(comment at :1044 says "carries a 34px score ring" — code disagrees)**
- `JobFeed.jsx:1188` ("No fit") → `size="md"`
- `ResumeEditor.jsx:498` (band) → `size="md"`

Only the row ring actually uses `md` deliberately; the other three all currently render at 44px, not 34px.

## Verdict

| site | pre-pass box/stroke/font | current preset in code | what it actually renders | recommendation |
|---|---|---|---|---|
| Feed row ring | 44px box / 2.5px stroke (rendered) / 19px | `size="md"` | **Exact match** — same box (44) and same viewBox scale (44/88 = pre-pass's 44/88), so r/stroke/font are pixel-identical | Keep `size="md"`. No change. |
| Feed report band ring | 34px box / 2.18px stroke (rendered) / 14px | `size="md"` (44px) | Wrong box entirely — 44px, not 34px | Change to `size="sm"`. This fixes the **box** to 34×34 exactly and the **font** to 14px exactly (`--t-14`), but the **ring itself** renders thinner/smaller inside that box than pre-pass (r 13.52 vs 15.26, stroke 1.93 vs 2.18) — a known, documented tradeoff (see `ui.jsx:910-917`, D-POST-16): `RING_VB` was pinned to a constant 88 to stop `sm` clipping into a squircle, at the cost of `sm`'s arc no longer being geometrically identical to the old per-site 78-viewBox ring. If pixel-exact arc geometry (not just box) is required, no preset does it — use an explicit numeric `size={38.4}` (keeps default `weight=5`), which reproduces r=15.26px/stroke=2.18px exactly, but that also grows the box to 38.4×38.4 instead of 34×34 (viewBox is fixed at 88, so box and arc-thickness can't both match 34px-era values simultaneously). |
| Feed "No fit" ring | 34px box, dashed, no SVG / 7.5px label | `size="md"` (44px) | Wrong box — 44px, not 34px | Change to `size="sm"`. Since the unscored path is a plain div (no viewBox scaling), `sm` reproduces this **exactly**: 34×34 box, `--t-7-5` = 7.5px label. No compromise here, unlike the scored-arc case above. |
| ResumeEditor band ring | 34px box / 2.62px stroke (rendered) / 13.5px | `size="md"` (44px) | Wrong box — 44px, not 34px | Change to `size="sm" weight={6}` to get the box back to 34×34 and preserve the old 6-unit stroke ratio (stroke_rendered = 6*(34/88) = 2.32px, closer to old 2.62 than default weight=5 gives). Font becomes `--t-14` = 14px vs pre-pass's 13.5px (0.5px off — no preset carries a 13.5 numeral size). For exact geometry parity, use explicit `size={38.36} weight={6}` (reproduces r=15.26px/stroke=2.615px exactly) plus an explicit `fontSize: 13.5` style override for the numeral — but again this means an 38.4px box, not 34px. |

**Bottom line:** `md` is correct and unchanged from pre-pass. `sm` is *close* but not pixel-identical to the old 34px band rings — it fixes the box size and (for the unscored/"No fit" state) matches exactly, but for the scored arc it's a deliberately-accepted thinner ring due to the `RING_VB` constant-88 fix. The current code isn't even using `sm` at the three non-row call sites yet (all say `size="md"`), which looks like an unintentional regression against the band comment at `JobFeed.jsx:1044` and against pre-pass — worth flagging as a fix (switch those three to `size="sm"`, with `weight={6}` on the ResumeEditor one) rather than a deliberate design deviation.

## Numeral optical-centre offsets: alt skin vs default (pixel-measured)

Followup to the geometry table above — this covers the *numeral/label vertical
centring* inside the ring, not the ring's own box/stroke/font sizing. The alt
skin (Georgia display face + small-caps sans label) sits on different font
metrics than the default skin, so the same `translateY` shift used for the
default numerals lands the alt ones off-centre. Measured by pixel, not glyph
rects: Playwright screenshot of each `ScoreRing`'s own box (device-scale 6x)
on `/v2/feed?job=<id>`, then PIL scan for ink pixels (colour distance > 40
from the sampled background) inside a mask that stays clear of the ring's
arc/track and (for `md`) the "+N reports" badge, bounding-box the ink, and
compare its vertical centre to the box's geometric centre. Reference job:
`537141a9-ea76-44d1-ae5a-b2fe00f91531` (score 77, 2 reports) for `md`/`sm`;
`f9f55248-fe40-4a40-973d-0383e8308459` (unscored) for the "No fit" label.
Mask radius was swept (10–16px css) per ring to confirm the measured offset
is stable and not an artifact of the mask boundary; contamination from the
arc/dashed-border only appeared once the mask reached the ring's own stroke,
well outside the reported radii.

Ink-centre vertical offset from the ring box's geometric centre (css px,
positive = ink sits below centre):

| ring | default token (before) | default ink offset | alt token (before) | alt ink offset (before) | delta needed | alt token (after) | predicted alt ink offset (after) |
|---|---|---|---|---|---|---|---|
| `md` (Feed row, 44px box) | `1px` | **-0.58px** | `-1px` | **-2.00px** | +1.42px | `.42px` | -0.58px (matches default) |
| `sm` (report band, 34px box) | `2px` | **0.00px** | `0px` | **-1.25px** | +1.25px | `1.25px` | 0.00px (matches default) |
| "No fit" label (unscored, 34px box) | `0px` | **-0.75px** | `1.5px` | **-0.83px** | +0.08px | `1.58px` | -0.75px (matches default) |

Default `sm` ink centre lands at **0.00px** offset (dead-centre) — confirms
the user's approval of `--ring-shift-sm: 2px` in the default skin; no change
made there.

`theme.css` alt-skin tokens updated (both `[data-skin="alt"]` and
`[data-skin="alt"][data-theme="dark"]` blocks, identical):

```
--ring-shift-sm: 0px   → 1.25px
--ring-shift-md: -1px  → .42px
--ring-label-shift: 1.5px → 1.58px
```

Predicted-after offsets above are exact by construction (delta = target −
measured-before, added straight into the `translateY`), assuming the
sub-pixel rendering path is linear in the shift, which it should be for a
plain `transform: translateY()` — no rebuild was performed to re-verify
visually; flag if the built app still looks off after the next frontend
build and a re-measurement pass should follow.
