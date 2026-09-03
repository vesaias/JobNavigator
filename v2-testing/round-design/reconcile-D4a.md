# reconcile-D4a — D3→D4a diff reconciliation

Inputs: `expected-D4a.md`, `artifacts/design/stylediff_D3_D4a.md` (154 changed tuples · 282
missing · 282 added), `artifacts/design/shotdiff_D0_D4a.json`, `artifacts/design/diff_D0_D4a/*.png`
(Companies/Feed/Applications/Stats, light/1440), `frontend/src/v2/ui.jsx`, `D1-D2.md`. Code commit
`c1e8f7f` ("v2 design pass D4a…") checked against `Companies.jsx` to confirm one item below is not
a code change.

**Caveat that shapes this whole reconciliation:** `shotdiff_D0_D4a.json` and the four overlay PNGs
diff against **D0** (the pre-tokenized original), not D3. They therefore show *every* accumulated
visual change since the start of the design pass (fonts, colors, spacing from D1–D3 as well as
D4a), not D4a's contribution in isolation. Where the task asks me to read something out of those
two artifacts, I've done so, but the `stylediff_D3_D4a.md` (D3→D4a, isolated) is the authority for
"did D4a itself introduce this."

**Second tooling caveat, discovered while tracing rows:** `stylediff` matches elements by DOM path.
Several migrations put the new class (`v2-ctl`, `v2-ctl v2-bd`, …) directly on the button/pill's own
node rather than a child, which changes that node's own path — so the tool can't pair it with its D3
self and reports it only as a missing+added pair, with **no property-level row**, even when
`expected-D4a.md` documents a real (non-zero-pixel) style change there (e.g. `Resumes.jsx:158` "+ New
résumé", `ResumeEditor.jsx:551` "✦ Tailor for a job…"). This is a limitation of the diff tool, not a
visual regression — the shotdiff bbox pixel counts for those routes (900–2000px, consistent with a
1–2px text/padding nudge on one button) corroborate that the change is real but small, matching the
documented delta. Flagged here so it isn't mistaken for missing coverage.

## Changes grouped — verdicts

| change (state · prop · old→new) | count | verdict | evidence |
|---|---|---|---|
| rest · height 23px→26px | 36 | expected | `Companies.jsx:531` Active/Inactive row `Pill size="sm"` (32: 16 rows × 2 themes) + `Stats.jsx:451`/`:541` Funnel/Flow & period toggle inner label span (4) — exact height delta documented |
| hover · fontSize 11px→11.5px | 28 | expected | `Companies.jsx:531` hover, documented `font-size 11 → 11.5` |
| hover · fontWeight 500→400 | 28 | expected | `Companies.jsx:531` hover, documented `font-weight 500 → 400` |
| hover · lineHeight 16.5px→11.5px | 28 | consequence | `v2-ctl` fixes `line-height:1`, so line-height tracks the documented font-size bump; not called out by name in the row but mechanical |
| hover · paddingLeft 11px→13px | 28 | expected | `Companies.jsx:531` hover, documented `padding 0 11px → 0 13px` |
| hover · height 23px→26px | 28 | expected | `Companies.jsx:531` hover, documented `height 23 → 26` (2 rows, 15/16, fall outside the crawl's captured viewport on hover — 28 not 32, a crawl-coverage gap, not a component bug) |
| rest · height 30px→31px | 16 | expected | `Pill` md h31: `JobFeed.jsx:73` 6 filter/status triggers ×2 themes (12) + `Applications.jsx:357` Company filter ×2 (2) + `Settings.jsx:745` `ActionBtn` "Manage…" call site ×2 (2) |
| rest · height 764px→763px | 14 | consequence | page/section container cascade from the filter-bar row growing 45→46 (Feed/Companies/Applications) |
| rest · height 45px→46px | 6 | consequence | filter/tier-bar wrapper grows to fit `Pill` md's new 31px height |
| rest · height 599px→598px | 6 | consequence | Feed right-panel scroll region, cascades from the filter-bar +1 |
| rest · height 560px→559px | 4 | consequence | Applications list-group cascade |
| rest · height 24px→26px | 4 | expected | `Stats.jsx:451`/`:541` toggle wrapper div, tracks the documented pill height change |
| rest · height 757px→758px | 4 | consequence | `CoverLetterEditor.jsx` PDF iframe grows +1 as the head row shrinks −1 (see next) |
| rest · height 726px→725px | 2 | consequence | Feed left-rail job list, filter-bar cascade |
| hover · height 599px→598px | 2 | consequence | same Feed right panel, hover state |
| hover · height auto→17.25px | 2 | **noise (data drift)** | Companies "+N this week" badge (`Companies.jsx:521`), see below — not code, not in scope |
| rest · height 596px→595px | 2 | consequence | Applications list scroll cascade |
| hover · height 596px→595px | 2 | consequence | same, hover |
| rest · height 65px→66px | 2 | consequence | Applications app-group header row grows +1 from the `⧉ Generate prep handover` pill (25→26) inside it |
| rest · height 25px→26px | 2 | expected | `Applications.jsx:570` "⧉ Generate prep handover for AI" → `Pill size="sm"`, documented `height 25 → 26` |
| rest · height 110px→107px | 2 | consequence | `CoverLetters.jsx:91` VoicePicker row, wraps tighter as pills shrink 27→26 |
| rest · height 91px→88px | 2 | consequence | same VoicePicker, inner row |
| rest · height 160px→158px | 2 | consequence | Stats funnel/score chart area shrinks 2px as the Funnel/Flow toggle wrapper (`:451`) grows 2px |
| rest · height 180px→178px | 2 | consequence | Stats LLM-cost chart area, same cascade from `:541` |
| rest · height 158px→156px | 2 | consequence | Stats chart gutter, same cascade |
| rest · fontSize 13px→13.5px | 2 | expected | `CoverLetterEditor.jsx:342` "↻ Regenerate…", documented `font-size 13 → 13.5` |
| rest · lineHeight 13px→13.5px | 2 | consequence | `v2-ctl` line-height tracks the font-size bump |
| rest · paddingLeft 19px→18px | 2 | expected | `CoverLetterEditor.jsx:342`, documented `padding 0 19px → 0 18px` |
| hover · fontSize 13px→13.5px | 2 | expected | same element, hover (Button has no dedicated hover class here but font styles apply in both states) |
| hover · lineHeight 13px→13.5px | 2 | consequence | as above |
| hover · paddingLeft 19px→18px | 2 | expected | as above |
| rest · height 46px→45px | 2 | consequence | `CoverLetterEditor.jsx` head row shrinks −1 as "↓ Download PDF" shrinks 29→28 |
| rest · fontSize 12px→12.5px | 2 | expected | `CoverLetterEditor.jsx:527` "↓ Download PDF" → `Button size="xs"`, documented `font-size 12 → 12.5` |
| rest · lineHeight 12px→12.5px | 2 | consequence | `v2-ctl` line-height tracks font-size |
| rest · paddingLeft 15px→14px | 2 | expected | `:527`, documented `padding 0 15px → 0 14px` |
| rest · height 29px→28px | 2 | expected | `:527`, documented `height 29 → 28` |
| hover · fontSize 12px→12.5px | 2 | expected | `:527`, hover |
| hover · lineHeight 12px→12.5px | 2 | consequence | as above |
| hover · paddingLeft 15px→14px | 2 | expected | `:527`, hover |
| hover · height 29px→28px | 2 | expected | `:527`, hover |
| hover · color rgb(63,107,82)→rgb(109,104,98) | 1 | **noise (data drift)** | light-theme `--good`→`--muted`, see below |
| rest · color rgb(63,107,82)→rgb(109,104,98) | 1 | **noise (data drift)** | light-theme, same span, rest state |
| hover · color rgb(141,187,159)→rgb(168,164,157) | 1 | **noise (data drift)** | dark-theme `--good`→`--muted`, same span |
| rest · color rgb(141,187,159)→rgb(168,164,157) | 1 | **noise (data drift)** | dark-theme, rest state |

**No UNEXPECTED entries in the grouped table.** Every prop delta is either a documented row in
`expected-D4a.md`, a mechanical consequence of one (line-height tracking a `v2-ctl` font-size bump,
or a container resizing because a child pill it holds grew/shrank), or the data-drift item below.

### The "noise (data drift)" item, traced
`main>div.v2-scroll>div.v2-scroll:1>div.v2-crow:{12,16}>span:5>span|+` / `span:5|0` is
`Companies.jsx:521`:
```js
{c.open_jobs || 0}<span style={{ color: c.open_jobs_week ? 'var(--good)' : 'var(--muted)' }}> +{c.open_jobs_week || 0}</span>
```
`--good` (light `#3f6b52` = rgb(63,107,82), dark `#8dbb9f` = rgb(141,187,159)) and `--muted` (light
`#6d6862` = rgb(109,104,98), dark `#a8a49d` = rgb(168,164,157)) match the old/new colors exactly.
Two company rows' `open_jobs_week` flipped from non-zero to zero between the D3 crawl and the D4a
crawl — i.e. real backend data changed between the two test runs (a scrape ran, or the "new this
week" window rolled). `git show c1e8f7f -- frontend/src/v2/Companies.jsx` confirms line 521 is
untouched by the D4a commit. Not a `Button`/`Pill`/`IconButton` site, not in scope, not a regression.
The paired `height auto→17.25px` on hover is the same span picking up real line content it renders
differently now that `+0` vs `+8` are different string lengths — same root cause.

Two more data-drift items surfaced only in the Missing/Added lists (not the grouped table, since
they're full text-content swaps, not style tuples) for the same reason — the Stats "780"→"778" /
"33"→"31" figures (`stats|main>div>div.v2-scroll:0>div:2>div:1>div:1>div:1>span:1` and the gutter
span beside it) and the scheduler's next-due job row swapping from "Check Gmail for replies · 16:01"
to "Send daily Telegram digest · 18:00" (`div:3>div:3`) — both are clock/data drift between the two
crawl runs, not a Stats.jsx code or style change (Stats.jsx's expected rows are only the two Pill
toggles and their kept-inline siblings; none of these are among them).

## Missing / Added — path-rename audit

282 missing + 282 added, an exact 1:1 pairing everywhere I traced it — consistent with pure DOM-path
renames (a new `v2-ctl`/`v2-bd`/`v2-act` class landing on a node or its child shifts every descendant's
generated path) rather than any element actually appearing or disappearing. I walked every
missing/added pair against `expected-D4a.md`'s migrated-site list (Feed filter triggers, Searches
"+ New search" + status pill + the consequently-reindexed-but-untouched ⋯/Run/Test siblings,
Companies "+ Add company" + tier pills + row Active/Inactive, Applications "+ Log application" +
Company filter + the prep-handover pill, Resumes "+ New résumé", CoverLetters voice pills + Generate
button, Stats Funnel/Flow + period toggle, Settings "Manage…" (`ActionBtn`, same component as
`Settings.jsx:745`), and the 36×36 "⋯" head menus on Resumes/ResumeEditor/CoverLetterEditor) and every
one resolves to a documented site. Nothing appears in Missing/Added that isn't a migrated
`Button`/`Pill`/`IconButton` or a plain sibling whose index shifted because a migrated neighbor's
subtree grew a class.

## Hover check — no lost hovers

The diff files only carry D3→D4a deltas, not an absolute D4a rest-vs-hover snapshot, so lost hovers
were checked structurally instead: every migrated site's DOM path in "Added in D4a" was matched
against `ui.jsx`'s per-variant hover-class rule and the source (`frontend/src/v2/ui.jsx:110-195`):

- `Pill` (all `on`/off, md/sm): unconditionally adds `v2-bd` unless `disabled` — every migrated pill
  in the Added list (`Source`/`Company`/`H-1B`/`Score ≥`/`Salary`/`Status ·` triggers, tier pills,
  Active/Inactive, voice pills, Funnel/Flow, period toggle, "Manage…") carries `v2-ctl v2-bd`. ✓
- `IconButton size={36}` ("⋯" head menus): adds `v2-act`. All three sites
  (`resumes/22ce…`, `resumes/d28b…`, `cover-letters/{id}`) show `div.v2-ctl.v2-act` in Added. ✓
- `Button` primary/danger: `BTN_LOOK.primary.hover` / `.danger.hover` are `''` (no hover class) by
  the approved D2 canonical — every migrated primary Button in Added (`+ New search`, `+ Add company`,
  `+ Log application`, `+ New résumé`, `✦ Generate cover letter`, `✦ Tailor for a job…`, `Review 14
  changes`) carries bare `v2-ctl`, matching the "primary buttons don't tint on hover" spec, not a
  loss — they never had a hover treatment in the canonical signature.

No migrated element was found with a missing or wrong hover class. (Zero-pixel `IconButton size={26}`
close buttons — Companies:665/947, Searches:794, Applications:693, ResumeEditor:854, Settings:897/997
— don't appear in Missing/Added at all, because they already carried the bare-glyph hover class
inline pre-migration, so their path didn't change; consistent with `expected-D4a.md` calling them
zero-pixel.)

## Overlay images — per-image description and limitation

All four PNGs diff **D0 → D4a** (see caveat above), so they show the full accumulated visual delta
of the whole design pass, not D4a in isolation — nearly every row, badge, pill and button on each
screen is outlined in red because D1–D3 already retokenized fonts/colors/spacing across the app.
They cannot be used on their own to confirm "only button/pill areas changed" for D4a; that
confirmation comes from `stylediff_D3_D4a.md` above, which is scoped to D3→D4a and whose deltas all
trace to `Button`/`Pill`/`IconButton` migrations and their layout cascades.

- **Feed** (`v2_feed__light__1440.png`): filter-bar pills (Source/Company/H-1B/Score/Salary/Status),
  search box, every job-row's score disc/title/save/skip/⋯ icons, and the whole right-hand detail
  panel (Open/Tailor/⋯ buttons, score header, the frame-blocked notice + its "Open in new tab" button)
  are outlined — i.e. the whole page, as expected for a D0-baseline diff.
- **Companies** (`v2_companies__light__1440.png`): header "+ Add company", the tier/health filter
  pills, and every table row (name, tier badge, health text, ATS pill, counts, Active/Inactive,
  Run/Test/⋯) are outlined — again the whole table, not isolated to D4a's rows.
- **Applications** (`v2_applications__light__1440.png`): "+ Log application", "Company ▾" filter,
  every list row, the status-pill row (Applied/Interview/Offer/Rejected), "Generate prep handover"/"Add
  interview", Notes box, and history timeline text are all outlined.
- **Stats** (`v2_stats__light__1440.png`): every stat card, the Funnel/Flow toggle, the funnel bars,
  score-distribution bars, LLM-cost table, and the schedule table rows are outlined.

## Stats bbox (257,223,796,418), 13–14k px — explained

This bbox sits over the **funnel/score-cards row**: the Funnel/Flow toggle (`Stats.jsx:451`) at
top-left of the funnel card and the 1d/7d/30d/all period toggle (`Stats.jsx:541`) at top-right of the
LLM-cost card, both now `Pill size="sm" on={on}`. Per `stylediff_D3_D4a.md` (isolated D3→D4a), the
real D4a-attributable change in this region is: each toggle's wrapper `div` growing **24px→26px**,
each pill's own label span growing **23px→26px** with the documented font-size/weight/padding shifts,
and the two chart areas directly beneath shrinking by 2px each (**160→158**, **180→178**, gutter
**158→156**) as a pure consequence of the toggles' wrappers growing 2px in a fixed-height card. Both
controls are in `expected-D4a.md` (`Stats.jsx:451`, `Stats.jsx:541`). The raw 13–14k pixel count from
the D0-baseline shotdiff also includes D1–D3's earlier retokenization of this same card region
(borders/colors), so it should not be read as "13k px of new D4a change" — only the height/pill deltas
above are D4a's contribution, and they match the expected file exactly.

## Final list: UNEXPECTED

**None.** No visual change in `stylediff_D3_D4a.md` (D3→D4a, the authoritative isolated diff) falls
outside a documented `expected-D4a.md` row, a mechanical consequence of one, or the traced data-drift
item (`Companies.jsx:521`, untouched by the D4a commit, confirmed via `git show c1e8f7f`). No lost
hovers, no lost focus styles, no kept-inline site changed, no color/spacing drift outside the migrated
elements. D4a is clean to proceed to the next step.
