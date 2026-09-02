# F-009 — systematic integer line-height pass (v2)

Scope: eliminate fractional-pixel row positions across the v2 screens. Source-only edits;
**not rebuilt, not re-measured** — every "after" below is arithmetic, to be confirmed on the
next `docker compose build frontend`.

## Method

Three Playwright scans against the live bundle (`/tmp/v2t/lh_scan.py`, `lh_scan2.py`,
`lh_scan3.py`, run inside the backend container at 1440×900 light, routes `/v2/feed` (+ first
job clicked), `/v2/searches`, `/v2/companies`, `/v2/applications`, `/v2/resumes`,
`/v2/resumes/22ce0e5b-…`, `/v2/cover-letters`, `/v2/cover-letters/de0add32-…`, `/v2/persona`,
`/v2/stats`, `/v2/settings`):

1. **scan1** — every element under `.jn-v2 main` with a fractional `top` and a fractional own
   `line-height` or height, grouped by (font-size, line-height). 417 such sites exist in source;
   most are inside fixed-height controls (`height: N` pills, `.v2-ctl`) where the fractional line
   box cannot move anything. Grouping alone over-reports by ~10×.
2. **scan2** — restricted to *leaf* fractional-height elements (no fractional-height descendant)
   whose fractional height still propagates (parent height also fractional) up to a ≥280 px
   ancestor. Cuts Companies from 1022 → 0, Feed 178 → 12.
3. **scan3** — the decisive one. For every wide block (w ≥ 280, 12–400 px tall) with a fractional
   `top` or height, walk back through previous siblings / ancestors to the element whose
   fractional height actually produces the offset, then drill into its fractional-height leaves.
   Those leaves are the fix list below.

Baseline from scan3 (blocks with a fractional top / of those, bordered / blocks with a fractional
own height):

| route | frac-top blocks | bordered | frac-height blocks | culprits |
|---|---|---|---|---|
| feed | 8 | 2 | 8 | 4 |
| searches | 30 | 6 | 3 | 2 |
| companies | 1 | 0 | 1 | 2 |
| applications | 106 | 2 | 7 | 4 |
| resumes | 0 | 0 | 0 | 0 |
| resume-editor | 38 | 17 | 16 | 7 |
| cover-letters | 12 | 2 | 8 | 7 |
| cover-letter-editor | 0 | 0 | 0 | 0 |
| persona | 0 | 0 | 0 | 0 |
| stats | 48 | 0 | 8 | 12 |
| settings | 32 | 0 | 30 | 0 |

Line-height table used (never touching `.jn-v2` root, never a font size, padding or copy):
9.5 → 14px · 10 → 15px (already integer) · 10.5 → 16px · 11 → 16px · 11.5 → 17px · 12 → 18px ·
12.5 → 18px (19px where a paragraph textarea) · 13 → 20px · 13.5 → 22px · 16 → 18px ·
19 → 24px · 23 → 26px · 26 → 30px.

## Edits (73 lines, all one-line inline-style changes)

### Shared style constants (fix many sites at once)

| route(s) | file:line | element | before (font / lh / h) | after |
|---|---|---|---|---|
| applications | `Applications.jsx:47` | `LABEL` (section captions "Notes · autosaves", "History") | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| cover-letters | `CoverLetters.jsx:22` | `LABEL` (generate-panel captions "Your résumé", "Target job", "Voice", "Length") | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| searches | `Searches.jsx:70` | `MICRO` (uppercase micro captions) | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| searches | `Searches.jsx:71` | `HELP` (field help text) | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| stats | `Stats.jsx:68` | `NOTE` | 11 / 16.5 / 16.5 | lh `16px`, h 16 |
| stats | `Stats.jsx:69` | `COL` (all table column heads: Job, Job ID, Schedule, Status, Duration, Trigger, Purpose, Model, Calls, Cost, Cache) | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| stats | `Stats.jsx:70` | `MONO` | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| resume-editor, persona | `ResumeSections.jsx:90` | `BulletText` textarea default (auto-grows to `scrollHeight`) | 12.5 / 18.75 / 18.75·n | lh `19px`, h 19·n — **fixes the "bullets 112 px" residue (6 × 18.75 = 112.5 → 6 × 19 = 114)** |
| resume-editor, persona | `ResumeSections.jsx:52` | `Field` multiline textarea | 12.5 / 18.75 / n·18.75 | lh `19px` |
| resume-editor, persona | `ResumeSections.jsx:55` | `Field` label | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| resume-editor, persona | `ResumeSections.jsx:93` | `RemoveLink` | 11.5 / 17.25 / 17.25 | lh `17px`, h 17 |
| resume-editor, persona | `ResumeSections.jsx:102-103` | `EmptyState` two lines ("No projects yet" + note) | 12.5 / 18.75 · 11.5 / 17.25 | lh `18px` / `17px`, h 18 / 17 |
| resume-editor, persona | `ResumeSections.jsx:106` | `MenuHead` | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| resume-editor, persona | `ResumeSections.jsx:111` | `MenuItem` hint | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| resume-editor, persona | `ResumeSections.jsx:116` | `MicroField` label (School / Location / Degree / Years / Description …) | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| resume-editor, persona | `ResumeSections.jsx:130` | `SectionShell` count `(2)` | 11.5 / 17.25 / 17.25 | lh `17px`, h 17 |
| settings | `Settings.jsx:106` | `Toggle` label ("Override", "On") | 11 / 16.5 / 16.5 | lh `16px`, h 16 |

### Feed — `/v2/feed` (detail band)

| file:line | element | before | after |
|---|---|---|---|
| `JobFeed.jsx:822` | eyebrow row `Citi · Jobright · 13d ago` | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `JobFeed.jsx:825` | `<h2>` job title, `-webkit-line-clamp:2` | 26 / 29.9 (1.15) / 59.781 | lh `30px` open / `20px` collapsed → h 60 (2 lines) / 20 |
| `JobFeed.jsx:827` | meta row `$139K–$208K \| Irving, TX \| H-1B …` (the 12.5 px salary span inherits it) | 13 / 19.5 / 19.5 | lh `20px`, h 20 |
| `JobFeed.jsx:833` | collapsed one-line meta | 11.5 / 17.25 / 17.25 | lh `17px`, h 17 |
| `JobFeed.jsx:1051` | "…sends X-Frame-Options…" note (2 lines) | 13 / 20.15 (1.55) / 40.281 | lh `20px`, h 40 |
| `JobFeed.jsx:967` | report table head, `border-bottom:1px` | 9.5 / 14.25 / 20.25 (+6 pad) | lh `14px`, h 20 |
| `JobFeed.jsx:971` | report table row, `border-bottom:1px` | 12 / 17.4 (1.45) | lh `18px` |
| `JobFeed.jsx:985,990,991` | hard-blocker rows, "ATS tip" label + text | 12.5 / 18.75 · 9.5 / 14.25 | lh `18px` / `14px` |
| `JobFeed.jsx:900` | report summary | 13.5 / 21.6 (1.6) | lh `22px` |
| `JobFeed.jsx:640` | company-filter menu hint | 10.5 / 14.7 (1.4) | lh `16px` |
| `JobFeed.jsx:1078,1138` | tailor / rescore modal titles | 19 / 23.75 (1.25) | lh `24px`, h 24 |

**Expected:** detail band `143.031 → 144` (35 pad + 1 border + 16 + 6 + 60 + 6 + 20 = 144);
collapsed band `23 + 1 + 20 + 6 + 17 = 67`. All 8 fractional-top blocks and both bordered ones
on this route go to 0.

### Searches — `/v2/searches`

| file:line | element | before | after |
|---|---|---|---|
| `Searches.jsx:449` | header subtitle `6 configs · 4 active · …` | 13 / 19.5 / 19.5 | lh `20px`, h 20 |
| `Searches.jsx:681` | test-modal result table head (`height:28`, `border-bottom`) | 9.5 / 14.25 spans | lh `14px`, spans h 14 |
| `Searches.jsx:253` | mode note banner | 11.5 / 17.25 (1.5) | lh `17px` |

**Expected:** `<header>` `91.5 → 92` (22 + 16 pad + h1 30 + gap 3 + 20 + 1 border). That single
line was the culprit behind 27 of the 30 fractional-top blocks (6 of them bordered), including
the "cards at 105.5" in the finding — the card pitch is already an integer 75, so every card top
becomes an integer once the header does.

### Companies — `/v2/companies`

| file:line | element | before | after |
|---|---|---|---|
| `Companies.jsx:340` | list column head (`height:30`, borders top+bottom) | 9.5 / 14.25 spans | lh `14px`, spans h 14, top `(30-14)/2 = 8` |
| `Companies.jsx:769` | modal column head (`height:28`, `border-bottom`) | 9.5 / 14.25 spans | lh `14px`, spans h 14, top 7 |

**Expected:** the single fractional block ("Health" head span at top 142.875) → 0.

### Applications — `/v2/applications`

| file:line | element | before | after |
|---|---|---|---|
| `Applications.jsx:377` | detail title `Sr. Product Manager` | 23 / 26.45 (1.15) / 26.438 | lh `26px`, h 26 |
| `Applications.jsx:382` | detail sub `$140K–$207K · Seattle, WA · …` | 12.5 / 18.75 / 18.75 | lh `18px`, h 18 |
| `Applications.jsx:512` | history entry text | 12.5 / 18.75 / 18.75 | lh `18px`, h 18 |
| `Applications.jsx:513` | history entry timestamp | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `Applications.jsx:517` | "No history recorded yet." | 12 / 18 | lh `18px` (no change, made explicit) |
| `Applications.jsx:437` | email-snippet quote | 12.5 / 19.375 (1.55) | lh `19px` |
| `Applications.jsx:460` | interview prep line | 12 / 18 | unchanged (already integer) |
| `Applications.jsx:498` | notes textarea | 13 / 20.15 (1.55) | lh `20px` |
| `Applications.jsx:535` | activity-log `<pre>` | 11 / 17.6 (1.6) | lh `18px` |
| `Applications.jsx:643` | interview-prep textarea | 12.5 / 18.75 (1.5) | lh `19px` |

**Expected:** detail head `143.188 → 142` (30 pad + 1 border + [15 + 3 + 26 + 3 + 18 = 65] + 12
gap + 34); each history row `47.5 → 47` (18 + 1 + 16 + 12 pad-bottom), so the history rail
`620.813` becomes an integer and the 106 fractional-top blocks (2 bordered) go to 0.

### Résumés — `/v2/resumes`

0 fractional sources measured; no edits. (Confirms the earlier per-screen pass.)

### Résumé editor — `/v2/resumes/{id}`

Handled almost entirely by the shared `ResumeSections.jsx` constants above (`MicroField`,
`RemoveLink`, `Field`, `BulletText`, `SectionShell`, `EmptyState`, `MenuHead`, `MenuItem`), plus:

| file:line | element | before | after |
|---|---|---|---|
| `ResumeSections.jsx:275` | summary char counter `615 characters · …` | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `ResumeSections.jsx:175` | contact-items hint `text · link · stub` | 10.5 / 15.75 | lh `16px` |
| `ResumeSections.jsx:238,240,241,247,248,249,271,273,350,352` | bullet-row markers `—`/`✦`/`↩`/`✕`, suggested-bullet text and its "suggested" tag | 11 / 16.5 · 12.5 / 18.75 · 9.5 / 15.2 (1.6) · 10 / 17 (1.7) | all lh `19px` — matches `BulletText`, so a bordered bullet row is `19 + 16 pad + 2 border = 37` |
| `ResumeSections.jsx:347` | "Bullets" caption | 9.5 / 14.25 | lh `14px` |
| `ResumeEditor.jsx:325` | `‹ Résumés` back link | 13 / 19.5 / 19.5 | lh `20px`, h 20 |
| `ResumeEditor.jsx:345` | tailored sub-band title | 12.5 / 17.5 (1.4) | lh `18px` |
| `ResumeEditor.jsx:509` | score-panel hint | 10.5 / 14.7 (1.4) | lh `16px` |

**Expected:** the two culprit section cards (Summary `279.75`, Education `426.5` — the ones
carrying `border:1px` and 15 of the 17 bordered fractional-top blocks) get integer heights; the
Education field grid `48.25 → 48`, its inner card `153.75 → 153`.

### Cover letters — `/v2/cover-letters`

| file:line | element | before | after |
|---|---|---|---|
| `CoverLetters.jsx:22` | `LABEL` (all four generate-panel captions) | 9.5 / 14.25 / 14.25 | lh `14px`, h 14 |
| `CoverLetters.jsx:301` | "Base for achievements and motivation" | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `CoverLetters.jsx:274` | row timestamp `1d` | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |

**Expected:** picker blocks `51.25 → 51`, `110.25 → 110`, `50.25 → 50`; the 12 fractional-top
blocks (2 bordered — the `x.25` pickers named in the finding) go to 0.

### Cover-letter editor — `/v2/cover-letters/{id}`

0 fractional wide blocks measured; no edits. (Two cosmetic-only leaves remain — see below.)

### Persona — `/v2/persona`

| file:line | element | before | after |
|---|---|---|---|
| `Persona.jsx:266` | header "Saved ✓" chip | 11.5 / 17.25 / 17.25 | lh `17px`, h 17 |

The résumé-content editor named in the finding ("label 48.75 px, bullets 112 px") is rendered by
`ResumeSections.jsx` and is fixed by the shared constants above: `MicroField`/`Field` labels
14.25 → 14 and 15.75 → 16 (label + gap 4 + 30 px input = 48.75 → 48/50), `BulletText` 18.75·n →
19·n (112.5 → 114). Persona's own `FIELD_LABEL`, group heads and Q&A `BulletText` calls already
carried integer line-heights.

### Settings — `/v2/settings`

| file:line | element | before | after |
|---|---|---|---|
| `Settings.jsx:106` | `Toggle` label | 11 / 16.5 / 16.5 | lh `16px`, h 16 |
| `Settings.jsx:488` | "inherits Primary" badge (`padding:1px 7px`) | 9.5 / 14.25 / 16.25 | lh `14px`, h 16 |
| `Settings.jsx:95,587` | secret-field `show` / `hide` links | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `Settings.jsx:506,514,525` | mono value previews (`44 models · …`, prompt previews) | 10.5 / 15.75 / 15.75 | lh `16px`, h 16 |
| `Settings.jsx:685` | prompt-editor textarea | 11.5 / 19.55 (1.7) | lh `20px` |

**Expected:** the 30 fractional-height blocks on this route are the `16.5 px` override rows and
the `15.75 px` preview lines; both become 16. Settings had no bordered fractional-top blocks, so
this is convention compliance rather than a visible border drop.

## Not fixed (with the same detail)

| route | file:line | element | measurement | why not |
|---|---|---|---|---|
| feed | `JobFeed.jsx:768` | list-row job title | 16 / 18.4 (1.15) / 18.391 | The row is already a clean 77 px (its parent column is a fixed 20 px and the row is 10 + 56 + 10 + 1). Forcing 18px would shorten the content box by 0.391 and risks pushing an integer row to a fraction. Cosmetic only — the fractional box is fully contained. |
| feed | `JobFeed.jsx:772` | list-row sub-line | 12.5 / 15 (1.2) | already integer |
| feed | `.v2-rail-skip.v2-rail-cell` | rail action cells | h 25.672 | height comes from the flex row, not a line box; contained by the 77 px row |
| stats | Recharts `<g>` / `<path>` (Score-distribution + Timeline) | 6 groups, h 178.952 / 190.827 / 89.476, tops x.02–x.72 | data-driven SVG geometry inside `ResponsiveContainer`; no line-height and no border involved. Fixing would mean pinning chart heights *and* domains — out of scope for this pass, and nothing bordered is affected. |
| stats | axis `<text>`/`<tspan>` ticks | 9.5 px, h 13, fractional top | SVG baseline placement by Recharts; `COL`/`MONO` do not apply |
| searches | `Searches.jsx:497` `▲` warn glyph, `:504` mode badge | 11 / 16.5 · 9.5 / 18.25 | centred inside an `align-items:center` flex row whose height is set by the 23 px title; no vertical propagation, no border on the element |
| companies | 1020 in-row `<span>`s (11.5/11/13/9.5 px) | h 17.25 / 16.5 / 19.5 / 14.25 | all inside fixed-height `.v2-crow`; scan2/scan3 confirm zero propagation (0 load-bearing) |
| cover-letter editor | `CoverLetterEditor.jsx:269` badge, `:~110` "saved 1d ago · autosaves" | 9.5 / 14.25 / 18.25 · 11.5 / 17.25 | route measures 0 fractional wide blocks; both sit in `align-items:center` rows taller than themselves |
| all | ~340 further `fontSize: 9.5/10.5/11/11.5/12.5/13` sites with no `lineHeight` | — | inside `height: N` pills, `.v2-ctl` controls, menus and inputs; a fractional line box there cannot move a row. Listed for completeness by `scratchpad/lh_grep.py` (417 sites total, 73 fixed). |

## Verification after the rebuild

Re-run `/tmp/v2t/lh_scan3.py` and compare the table at the top: the target is
`blocks_frac_top = 0` and `blocks_frac_top_bordered = 0` on feed, searches, companies,
applications, resume-editor, cover-letters, settings, and stats reduced to the Recharts groups
only (expected residual: 6 SVG `<g>`/`<path>` + their tick `<text>`).
