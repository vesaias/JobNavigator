# Skins proof, part B — visual review

Reviewed the 1440-width light/dark screenshots for all 13 routes in each of `P_cobalt/`, `P_saas/`, `P_win98/` (26 images per theme), plus the 1024-width light/dark shots for `feed` and `companies` (4 more per theme), against `v2-testing/round-design/design-in/Skins handoff.md` §3 and the default-theme reference set in `S4b/`. The original `Feed - Cobalt/SaaS/Win98.dc.html` boards were not available; judgments are against the handoff text and the default-skin screenshots only.

Severity: **P1** clipped/unreadable · **P2** wrong paint (missed the skin, palette leak, wrong radius/shadow/selection style) · **P3** nit.

---

## Cobalt

Spec: 8px control/field radius (row radius 0), primary-button-only cobalt-tinted shadow, Plex Sans 600, `#eef3fe` + inset 3px accent edge row selection (square corners), filled `#2c3442` rail tile (radius 5), ScoreRing = **pill** (40×44 tile, Plex Mono).

| Route | Appearance | Finding | Severity |
|---|---|---|---|
| v2_feed (light+dark, 1440) | Two-pane list/detail; rail "Jobs" a filled navy tile; ScoreRing a pink "40 FIT" pill; selected row light-blue with left accent bar | "Tailor résumé" primary button in the detail pane's sticky sub-header shows **no drop shadow** — a hard cutoff to the background in both modes — while every other primary CTA checked (Applications "+ Log application", Résumés "+ New résumé" / "Tailor for a job…", Cover Letters "Regenerate…") correctly shows the soft cobalt-tinted shadow. Likely clipped by the pane's overflow. | P2 |
| v2_feed / v2_companies (1024, light+dark) | Detail pane content overflows the narrower viewport | "Tailor résumé" truncates to "Tailor r…" and "Full report" is pushed off-screen with no scroll affordance. Identical in the S4b baseline at 1024 — pre-existing, not a cobalt regression. | P3 (not cobalt-attributable) |
| v2_toasts (light+dark, 1440) | "Toast lab" H1 in a lighter-weight sans | Doesn't match the bold ~600-weight Plex Sans display heading used on every other route's page title. Internal, explicitly-temporary dev page — low stakes. | P3 |
| v2_applications, v2_companies, v2_cover-letters (+detail), v2_persona, v2_resumes (+2 details), v2_searches, v2_settings, v2_stats | Rail active tile, ScoreRing pill, row/tag/chip radii, control radius, panel shadow, switches/dropdowns | No issues — all correctly picked up the cobalt palette/geometry. | — |
| v2_stats | Funnel/score-distribution chart fills use independent teal/gold/red/gray/blue | Confirmed as the accepted, documented keep (chart fills are inline Recharts/SVG colors, not skin-driven). | — |
| v2_cover-letters detail, v2_resumes details | PDF preview panel renders blank | Identical blank behavior in the S4b baseline — a capture-environment limitation (no PDF actually rendered), not a cobalt leftover. | — |

**Verdict**: Cobalt implements the geometry spec correctly and consistently across essentially every screen — rail active-tile fill (~`#2c3442`, radius ~5), the pill ScoreRing (confirmed on Feed and the tailored Résumé detail: 40×44 rounded tile, mono score + "FIT" caps label, no circular ring anywhere), row selection (`#eef3fe`-ish fill with a crisp 3px left accent edge, square corners, pixel-verified), 8px control/field radius, and correctly-colored tags/chips/pills throughout. The one real defect is an isolated missing shadow on one primary button.

**What looks right**: the blue accent and Plex Sans display weight are applied thoroughly with no warm-paper palette leaks anywhere, and dark mode correctly re-derives row-selection/rail colors rather than reusing light-mode hex values.

---

## SaaS

Spec: 8px control radius (8/8/10/10 field/row/card/menu), soft 1px shadow on **every** bordered control (stronger 12% on primary), 750-weight system-sans titles, 700-weight .06em caps labels, accent-soft row-selection wash, filled accent rail tile (radius 8, 10px inset), ScoreRing = **bar** (mono numeral + 32×3 track).

| Route | Appearance | Finding | Severity |
|---|---|---|---|
| v2_feed | Filter pills ~8px radius with a faint soft shadow; primary blue buttons show a visibly stronger shadow; rail "Jobs" a filled solid-blue radius-8 tile; selected row a light/deep blue wash; scores render as mono numerals with a small horizontal bar underneath | Matches spec on every count checked (elevation, rail, row wash, bar ScoreRing). | — |
| v2_feed / v2_companies (1024) | Detail pane text truncates ("Tailor résumé" → cut, meta line clipped) | Identical truncation in the S4b baseline at 1024 — pre-existing, not saas-specific. | P3 |
| v2_companies | Tier badges and ATS chips ~8px radius, pastel tint backgrounds, readable both modes | No issues. | — |
| v2_companies (1024) | Résumés/ATS/Apps/Ø Fit columns shed | Same shedding behavior as S4b baseline. | — |
| v2_cover-letters | Voice/Length option pills use a blue-border selected state vs. S4b's filled-green selected state | Legitimate per-skin selection-state divergence, not a bug. | P3 |
| v2_cover-letters / v2_resumes detail | PDF preview panel renders blank in both modes | Identical to S4b baseline — capture-environment limitation, background color matches the page's own skin token (reads intentional). | P3 |
| v2_persona, v2_resumes, v2_searches | Fields/cards/chips consistent radius and soft shadow; no contrast issues | No issues. | — |
| v2_settings | Appearance/Theme/Primary provider dropdowns show a clear ~8px radius with a faint soft bottom shadow even on dense form fields | Strongest confirmation of the core saas "soft elevation on bordered controls" signature. | — |
| v2_settings | Toggle switches render as fully rounded pills, not 8px rects | Expected — switches are conventionally pill-shaped regardless of skin, not a radius violation. | — |
| v2_stats | Stat band has a subtle soft shadow, ~10px card radius; chart bars use their own inline colors | Chart fills correctly stay off-skin (accepted keep); card elevation present, no readability issues. | — |
| v2_toasts | "0 showing", no live toast to inspect | Not saas-specific — temporary internal dev page. | P3 |

**Verdict**: SaaS implements the geometry spec accurately and consistently across all 13 routes, both modes, both widths. The signature soft-elevation-on-every-bordered-control look is clearly present and is the standout correctly-executed feature. No clipped/unreadable text, no palette leaks, no incorrect hard/bevel shadows found anywhere.

**What looks right**: the soft-shadow elevation signature is genuinely present and consistent everywhere a bordered control appears (fields, dropdowns, buttons, status pills, card bands) — exactly the core saas differentiator called for in the spec.

---

## Win98

Spec: 0 radius everywhere, 2px bevelled controls (raised/inset 3D borders, no soft/hard shadow), hard `3px 3px 0` panel shadow, Tahoma 700 ×.92 (no caps tracking — sentence case), teal/navy desktop ground behind `--surface` pages, navy row selection with **white** ink, navy rail fill, 1px dotted focus outline, "engraved" disabled state (`#808080` ink + `1px 1px 0 #fff`), ScoreRing = **ascii** (`87 [████████░░]`).

| Route | Appearance | Finding | Severity |
|---|---|---|---|
| v2_feed (light+dark, 1440+1024) | Teal/navy desktop behind a grey window; navy-filled selected row; ASCII score badges | **Selected row text is unreadable.** The row fills navy correctly, but the title (`Heading`), company, and meta text keep their normal near-black ink instead of the white `--row-selected-ink` the row sets — pixel-sampled ~RGB(0,0,0) text on ~RGB(0,0,128) fill, ≈1.4:1 contrast. Root cause: `Row` (`ui.jsx` ~L575-596) sets `color:var(--row-selected-ink)` on itself, but `JobFeed.jsx`'s row markup (~L1077-1128) nests spans/`Heading` with their own explicit non-inherited `color`, so white never cascades down. | **P1** |
| v2_feed, v2_resumes\*, v2_persona, v2_settings, v2_cover-letters\* | Inputs/Textareas/Selects, Pills (Run/Test/Voice/Length/filter chips) | **Bevels never render.** win98's `--bevel-inset-*`/`--bevel-raised-*` tokens exist in `theme.css` (~L1072), but `ui.jsx`'s shared `FIELD` style (~L342-347) and `Pill` style (~L265-274) set `border`/`boxShadow` **inline**, which beats the `.v2-inset`/`.v2-raised` class rules (no `!important`, theme.css ~L1358-1359). Every text field and pill shows a flat, uniform `#404040` 2px border on all four sides — no light/dark 3D split. The signature "sunken field / raised button" look never appears anywhere in the app. | **P2** |
| Rail (all routes), résumé/cover-letter status pill, Settings nav, Toast lab | Section/status labels | **Hardcoded caps+tracking bypasses the win98 sentence-case rule.** Tokens (`--label-case:none`, `--label-tracking:0`, `--tag-tracking:0`) are correctly set and honored by table headers, "H-1B Likely", filter pills, and status segments — but several labels hardcode `textTransform:'uppercase'` + `letterSpacing` inline instead of reading the tokens: rail group headers "FIND / APPLY / YOU" (`V2App.jsx` ~L186), the "BASE"/"TAILORED"/"DRAFT" pill (`ResumeEditor.jsx` ~L533), Settings' left-nav group headers, and the toast-lab kind labels. (ATS chips "GREENHOUSE"/"PHENOM" on Companies are literal uppercase data, identical to S4b — not a bug.) | P2 |
| v2_cover-letters (light, empty form) | Disabled "✦ Generate cover letter" button | Disabled ink hardcoded to `--btn-primary-disabled-ink` (= `--muted`, `#404040`) instead of win98's own `--disabled-ink` (`#808080`) + `--disabled-engrave` shadow — same inline-override pattern as the bevel issue. Legible but flat, missing the spec's "engraved" look. | P2 |
| v2_feed, v2_resumes detail | ASCII ScoreRing | Renders correctly: `40 [███████░░░░]` / `77 [█████████░]` — solid block + light hatch + brackets, no wrap/clip — on Feed rows, Feed detail panel, and the Résumé tailored-copy header. | — |
| All 13 routes | Corner radius | Zero radius confirmed everywhere checked: cards, table rows, pills, chips, dashed-add bands, buttons, modals — no stray rounding found in either mode. | — |
| All 13 routes | Desktop/surface split, rail active state | Teal (light) / navy (dark) desktop ground correctly shows behind the grey window chrome; rail active item is a solid navy fill with white ink. | — |
| v2_feed / v2_companies (1024) | Narrow width | Companies correctly sheds the Résumés/ATS columns; Feed's detail title/company truncate hard. Both reproduce identically in the S4b baseline at 1024 — pre-existing, not a win98 regression. | — |
| v2_resumes detail (tailored copy) | Green-tinted tailored bullets | `--change-bg` fill kept as the only accent-colored content per the cross-skin convention; unaffected by win98 geometry. | — |

**Verdict**: win98 gets the palette-level geometry right — zero radius applies with no exceptions found, the teal/navy desktop-vs-surface split reads correctly, the rail's navy active fill is correct, and the ASCII ScoreRing works exactly as specified with no clipping in any of the ~10 places it appears. However, the skin's two most Windows-98-defining behaviors are both broken by the same CSS-precedence mistake — inline `border`/`boxShadow` in `ui.jsx`'s shared `FIELD` and `Pill` styles beats the `.v2-inset`/`.v2-raised` class rules, so bevelled controls never actually bevel — and the navy row-selection fill loses its text to a black-on-navy contrast failure because child components in `JobFeed.jsx` hardcode their own ink instead of inheriting `--row-selected-ink`. A handful of labels also hardcode uppercase+tracking and so miss the sentence-case rule even though the underlying tokens are configured correctly.

**What looks right**: the zero-radius geometry and the teal/navy "desktop behind a grey window" concept are implemented cleanly and consistently across every route and mode, and the ascii ScoreRing is a correct, non-clipping implementation of the most unusual variant in the set.

---

## Overall

| Theme | P1 | P2 | Verdict |
|---|---|---|---|
| Cobalt | 0 | 1 | Solid — one isolated missing button shadow |
| SaaS | 0 | 0 | Clean pass |
| Win98 | 1 | 3 | Geometry (radius/desktop/rail/ScoreRing) is right; bevels, selected-row contrast, and caps-case leaks need fixes |

### P1/P2 list

- **P1 (win98)** — Feed selected-row text (title/company/meta) renders black-on-navy (~1.4:1 contrast) instead of white; `Heading`/spans in `JobFeed.jsx` hardcode ink instead of inheriting `--row-selected-ink` (`ui.jsx` `Heading` ~L1775-1787).
- **P2 (win98)** — Bevel borders/shadows never render on Input/Textarea/Select/Pill/bordered IconButton anywhere: inline `border`/`boxShadow` in `ui.jsx`'s `FIELD` (~L342-347) and `Pill` (~L265-274) permanently beat the `.v2-inset`/`.v2-raised` CSS rules.
- **P2 (win98)** — Hardcoded uppercase+letter-spacing bypasses the sentence-case tokens on: rail group headers (`V2App.jsx` ~L186), the Base/Tailored/Draft badge (`ResumeEditor.jsx` ~L533), Settings nav group headers, and toast-lab kind labels.
- **P2 (win98)** — Disabled-button ink uses `--muted` instead of win98's `--disabled-ink`/`--disabled-engrave` pair, missing the "engraved" look (Cover Letters "Generate cover letter").
- **P2 (cobalt)** — "Tailor résumé" primary button in the Feed detail-pane sticky header has no cobalt-tinted drop shadow, unlike every other primary CTA checked.

No P1s found in cobalt or saas. The 1024-width feed/companies clipping noted in all three themes is pre-existing (identical in the S4b baseline) and not attributable to any skin.
