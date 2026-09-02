# Design-vs-Code Decisions — Stage 3

**How to use this:** for each row, fill in **Your call** with `keep code`, `match design`, or `other: …` (short note). Nothing here changes until you decide.
**Scope:** P3/P4 findings tagged "needs decision" in the Stage 3 reports where the deviation is about a design value, hover, copy, or layout — functional bugs (missing error handling, wrong data, dead controls) were pulled out to the excluded list at the end, even where they were P3/P4 + needs decision.
**Row counts by screen:** Feed 14 · Searches 7 · Companies 15 · Applications 10 · Résumés 12 · Cover Letters 13 · Persona + Stats 20 · Settings 11 · Shell 7 — **109 total** + 12 Résumés re-check rows below.

---

## Feed (14)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| FEED-12 | Row action rail hovers (♥ ✕ ⋯) | ♥ bg surface-2 + accent text; ✕ bg warn-soft + warn text; ⋯ bg surface-2 + text | Only bg/border change on ♥/✕, colour unchanged; ⋯ nothing changes | Add !important to color/background, or drop inline colours | |
| FEED-13 | Row SCORE button hover | Border solid + accent, text accent, bg accent-soft | Only bg surface-2 changes; border stays dashed, colour unchanged | — | |
| FEED-14 | Detail chevron / "+ Rescore" hover | Colour → accent only, no background change | Both show bg wash (surface-2), colour unchanged | — | |
| FEED-15 | Score/Salary presets & bulk-bar buttons hover | Presets border → accent; bulk Skip/Score border #f6f3ea, ✕ colour #f6f3ea | No hover fires on preset "80" or bulk Skip/Score | Apply existing .v2-bdc/.v2-bd classes | |
| FEED-23 | Requirement table unmet rows/header | Unmet rows bg var(--bad-soft); header sticky top:0 z-index:2 | Rows always transparent bg; header position:static | — | |
| FEED-24 | Empty state (no jobs match) | Dashed card with explanation + Clear search button; "Nothing to show" overlay | "No jobs match." only, no way back; detail "Select a job." | — | |
| FEED-25 | Title search clear affordance | ✕ inside input + removable "Title" chip in filter bar | Neither exists; only way to clear is select-all-delete | — | |
| FEED-26 | Source/H-1B dropdown counts | Mono count per row (LinkedIn 64, Likely 112, etc.) | No per-value counts shown; no counted endpoint exists | — | |
| FEED-27 | Score ring geometry/colours | 40×40, viewBox 44, r17.5, sw1.5; ≥80 accent/≥65 text-2/else muted | 44×44, viewBox 88, r35, sw5; ≥70 good/≥50 warn/else bad | — | |
| FEED-28 | Sort menu 4th option | "Last updated" | "Company A–Z" (works, wrong label) | — | |
| FEED-30 | Row/header padding & widths | Row pad 12/12/12/22px; company max-width 170px; header pad 30px | Row pad 10px/12px; company width 230px; header pad 24px | — | |
| FEED-35 | Posting pane (iframe vs reader) | 66ch reader column with sections; toggle as inset card | Full-bleed third-party iframe; toggle as full-width bar | — | |
| FEED-36 | --iframe-bg token (both themes) | — | rgb(255,255,255) identical in light and dark | — | |
| FEED-37 | Palette values (theme.css) | --surface-2 #f3f0e8; --bg #faf8f3 | --surface-2 #f6f4ee; --bg #fcfbf7 | — | |

## Searches (7)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| SRCH-08 | Test-modal table rows (geometry) | — | Rows offset .75px; modal height 389.5px fractional | Integer line-heights on strip/footer/title (17/26px) | |
| SRCH-13 | Test modal width | 880px | 980px (900px at narrow widths, no overflow) | — | |
| SRCH-14 | Test-modal Salary column | 92px width, 10.5px font | 120px width, 9.5px font | — | |
| SRCH-15 | New-card body / edit drawer bg | #fdfcf9 → --recessed | --bg rgb(252,251,247) | — | |
| SRCH-16 | Header rule / left gutter | Rule inset 30px, symmetric padding | Full-bleed rule, 24px left gutter | — | |
| SRCH-17 | Card/chip/pill/tab/Close hovers | No style-hover authored on these controls | Extra hovers: card border+bg, chips, pills, tabs, Close | Keep for consistency, or trim to design | |
| SRCH-18 | Card action-cluster metrics | Actions flex 148px gap4; Run/Test pad 0 10px; pill auto-width | Wrapper 169px margin -11px gap3; pad 0 9px; pill fixed 62px | — | |

## Companies (15)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| COMP-16 | Drawer/test-modal ✕ hover colour | style-hover bg+colour both (#f3f0e8;#1b1a16) | Only backgroundColor changes; colour stays --muted | Add !important to .v2-hover-accent:hover colour (cross-screen) | |
| COMP-17 | Run/Test/⋯/Make-active/URL✕ hovers | Border-colour only, no background, per control | Border + background extra on most; URL✕ bg-only | Keep code (unified) or match design | |
| COMP-20 | Drawer width | 520px | 720px (50% at 1440, 70% at 1024) | — | |
| COMP-21 | Column widths (Company/Health/Résumés/ATS/actions) | Company 206px; Health flex1 min190; Résumés104; ATS84; actions168 | Company flex1 min118 (149/118px); Health flex1.9 min210(283/210); Résumés132; ATS108; actions190 | — | |
| COMP-22 | "{n} of {N} shown" counter | Shown only while filtered | No such element; header always shows unfiltered total | — | |
| COMP-23 | Test-modal row tints | bg per state #fff/#fdf8f7(out)/#fdfaf5(drop) | Every row backgroundColor transparent; field is dead code | Apply st.bg mapped tokens, or delete field | |
| COMP-25 | Column-header rule placement/weight | Toolbar border-bottom 1px #e2ddd0; header row 1px #c9c3b4 only | Header has border top+bottom both 1px; toolbar border 0 | — | |
| COMP-28 | Delete/Add native confirm & alert | No dialogs; rest of v2 uses modals/toasts | Native window.confirm/alert used for delete & validation | — | |
| COMP-29 | Tier-empty state copy | Names the tiers, e.g. "No companies in X, Y." | Generic "No companies in the selected tiers." | — | |
| COMP-30 | "Ø Fit" header glyph | U+2300 ⌀ diameter sign | U+00D8 Ø Latin O with stroke | — | |
| COMP-31 | Tier chip count/tooltip | Count "(n)"; tooltip states dynamic Add/Remove action | Bare count "Tier 1 5"; static tooltip regardless of state | — | |
| COMP-32 | Drawer subtitle pluralisation | Pluralises both nouns | "1 career URL(s) · 1 open application(s)" | — | |
| COMP-33 | Row tooltips (name/ATS/health/résumés) | Detailed dynamic text (H-1B%, per-line ATS+slug, help text) | Name=name itself; ATS=urls only; health/résumés=visible text again | — | |
| COMP-34 | Add-modal input/tier-seg radii | Inputs 33px/8px radius; tier segs 33px/8px | Inputs 33px/7px radius; tier segs 32px/7px | — | |
| COMP-36 | Sort menu options/geometry | 5 options; w190; margin-top8; pad6; z-index40 | 6 options (+Priority tier); w172; margin-top5; pad8; z-index45 | — | |

## Applications (10)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| APPS-10 | Prep modal ✕ hover colour | style-hover bg+colour both (#f3f0e8;#1b1a16) | Only backgroundColor changes; colour unchanged | Coordinator: add !important cross-screen (15 elements) | |
| APPS-16a | Detail list pane width | flex 0 0 340px | 472px — matches Feed's 472, deliberate | — | |
| APPS-16b | Cached/Live/⋯ pill metrics | Height 25px, pad 0 10px, 11.5px font, ⋯ 25×25 | 30px, pad 0 14px, 13px font, ⋯ 30×30 (matches Feed) | — | |
| APPS-16c | Detail body section order | Notes → Last email → Interviews → Cached posting | Last email → Interviews → Notes | — | |
| APPS-16d | Cached posting preview panel | 140px inline preview panel | Absent — replaced by header "Cached" link | — | |
| APPS-16f | Rejected group label | "Rejected · kept for stats" | "Rejected" | — | |
| APPS-16g | Prep modal terminology | "Prep bundle", "the LLM", résumé-content footer note | "Prep handover", "the AI", different footer wording | — | |
| APPS-16h | Prep trigger button label/width | "Prep for LLM" (~90px pill) | "Generate prep handover for AI" (202.6px wide) | — | |
| APPS-16i | Interview form fields | 3 placeholder-only inputs, no Where field | 4 labelled inputs incl. Where + datetime-local | Keep (functional improvement) | |
| APPS-20 | Selected vs hovered row colour | Same collision in design (hover & selected both #f3f0e8) | Identical — inherited from design, not introduced | — | |

## Résumés (12)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| RES-11 | Editor section/bullet/modal row heights | Bullet textarea deliberately keeps 1.5 line-height (documented) | Card tops fractional (.75px); modal rows fractional | Integer line-heights on 10.5px labels; accept/override bullet lh | |
| RES-14 | 200-char base name overflow | Every sibling string on screen truncates | No truncation; name overflows card ~900px past edge | Add flex/minWidth/ellipsis + title attribute | |
| RES-17 | Disabled primary button fill | --line bg / --muted text (design tailorGoBg #e2ddd0) | --edge fill rgb(138,130,110) with white text — reads enabled | background:var(--line), color:var(--muted) when disabled | |
| RES-22a | Résumés screen layout identity | Two-pane browser (312px source col + copies table) | Source-card "Shelf" home (Persona + base cards + chips) | — | |
| RES-22b | Review modal size | 620×580 | 920×760 | — | |
| RES-22c | Copy ⋯ menu width/behaviour | 248px; hint "replaces copy", quick/full split | 244px; hint "adds a copy" (behaviour genuinely differs) | — | |
| RES-22d | Tailored badge colour | Plum #f3e7ef / #7c4066 | Accent-soft/accent (green) — deliberate cross-screen change | — | |
| RES-22e | ▲▼ and ✕ hovers | Colour-only (#3f6b52 / #9c3b30) | .v2-navlink adds background too; .v2-hover-bad bg-only | — | |
| RES-22f | Card hover | Beige wash | Accent border + --hover-soft (documented unification) | — | |
| RES-22g | Header h1 size / left gutter | 28px h1 / 30px gutter | 30px h1 / 24px gutter (shell convention, all 9 screens) | — | |
| RES-23 | "‹ Résumés" / based-on-link hover | Colour changes on hover (per .v2-hover-accent precedent) | Only background changes; colour unchanged | Add !important to .v2-navlink:hover, or accept bg-only | |
| RES-31 | Autosave status copy | — | "autosaves on blur" but actually 500ms debounce per keystroke | Reword to "autosaves" | |

## Cover Letters (13)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| CL-08 | Picker/Template/Paper popover hover | Hover intended via shared .v2-menuitem class | changed:[] — inline background beats class at 4 sites | Drop inline transparent at the 4 sites (surgical) | |
| CL-12 | Generate panel explanatory line | 10.5px muted line: "Takes about 30 seconds… drafted for your review." | Nothing follows the Generate button | Restore the line | |
| CL-13 | Voice-preset empty state | — | 0px gap, labelled void, no explanation when no presets | Copy: "No voice presets — add in Settings → AI" | |
| CL-24a | List count line | "4 letters · 2 linked to applications · Garamond, US Letter defaults" | "16 letters · 1 live application" | — | |
| CL-24b | Archive rule | Drafts and rejected both sink to archive | Drafts whose job is new/saved/applied stay active | — | |
| CL-24c | Archive band copy | "…from drafts & rejected applications" | "…from rejected applications & skipped jobs" | — | |
| CL-24d | Contact "Display text" cell width | flex 0 0 118px | flex 0 0 170px | — | |
| CL-24e | Card chevron | Text glyph ›/⌄ | Rotating 8×8 SVG | — | |
| CL-24f | Paragraph line-height | 1.55 | 19px (integer, per HANDOVER convention) | — | |
| CL-24g | PDF preview | 540px paper mock, drop shadow, centred scroller | Full-bleed iframe of real server PDF | — | |
| CL-24h | ⋯ menu items | View application / Open job posting / Delete | + extra "View job in feed" item | — | |
| CL-24i | Template control tooltip | Lists every template id | "Cover letter template" (generic) | — | |
| CL-29 | Disabled arrow hovers (▲▼/↑↓) | style-hover applied unconditionally to both arrows | Same — disabled arrows still hover (matches design) | — | |

## Persona + Stats (20)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| PERS-09 | Remove ✕ hover (bullet/skill) | style-hover color:#9c3b30 (glyph only, no bg) | bg --bad-soft added; colour unchanged (--muted) | Keep code (bg wash) or match design (red glyph) | |
| PERS-10 | Section vs group header hover colour | Every collapsible header hovers to bg:#faf8f3 (--bg) | Section header → --surface-2; group header → --bg | Align section headers to --bg, or keep shared class | |
| PERS-16 | Column head caption | Third span explaining column ("the pool tailored résumés draw from") | Only title + "what is this?" — 2 children, not 3 | — | |
| PERS-17 | Autofill group header subtitle | g.sub text per group (contact/demographics/workauth/screening) | Bare spacer, no subtitle text | — | |
| PERS-18 | "+ Add answer" hover class | No hover authored | Class present but changed:[] — dead either way | Drop class, or give real hover | |
| PERS-19 | "+ Add bullet" colour | color:#3f6b52 (accent), matches sibling add-controls | rgb(109,104,98) --muted, no hover change | Align to accent + .v2-dashadd | |
| PERS-20 | --edge small text contrast | Uses #8a826e (inherited from design) | ~3.9:1 light / 4.2:1 dark — below 4.5:1 floor | Lift to --muted, or keep design fidelity | |
| PERS-22 | Q&A card subtitle | "reusable screener answers — sent verbatim, worth writing well" | "reusable screener answers" (second half dropped) | — | |
| PERS-23 | Persona header save-behaviour copy | — | "Saves automatically" but is 500ms debounce, no blur | Reword header text (and CLAUDE.md) | |
| STAT-05 | Funnel bar colours (Applied/Interview) | Applied --funnel-low #8fae9b; Interview --funnel-mid #5f8a70 | Applied --stage-applied (blue); Interview --warn (orange) | Keep shared Applications palette, or match design ramp | |
| STAT-07 | "Applied" line colour, 30-day chart | #c9a35a (--gold), solid legend swatch | --warn rgb(154,91,40)/rgb(212,160,106); dashed legend swatch | Switch stroke to --gold | |
| STAT-10 | Score bucket 61-80 colour | --funnel-low #8fae9b | --funnel-mid rgb(95,138,112) — one step too dark | — | |
| STAT-11 | Funnel row percentage / subtitle | "{count} {pct}%" e.g. "8 31%"; card subtitle present | Count only, no pct; no subtitle | — | |
| STAT-14 | Schedules subtitle timezone wording | — | "next runs in UTC, schedules as configured (UTC)" — redundant | Suppress second clause when TZ_SHORT===UTC | |
| STAT-17a | Funnel/Flow, LLM period, Type▾ hover | No style-hover authored on these three | All three carry .v2-bdc (extra hover, no-op when active) | — | |
| STAT-17b | Funnel vs Flow toggle | No toggle — funnel replaces bar/Sankey toggle | Code has both funnel and Flow toggle | — | |
| STAT-17c | Schedules table columns | Job190/Schedule150/Next run130 | Added Job ID(132); Job widened to 250 | — | |
| STAT-17d | Running-button label/colour | "Running…" in #8a826e | "Running" in --accent | — | |
| STAT-20 | KPI tile padding/gap/line-height | padding 14px 20px; gap2px; line-height1.1 | padding 14px 20px 10px; gap11px; value line-height 30px | — | |
| STAT-21 | Border tokens as fills/text in dark | — (inherited use) | 0-20 bucket bar rgb(62,59,50) on rgb(40,37,27), low contrast | Use --line-strong in dark, or accept as intended | |

## Settings (11)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| SET-13 | --edge body text contrast | Uses #8a826e (inherited from design) | Light 3.69-3.82:1, dark 3.56-3.95:1 — below 4.5:1 | Keep design tone, or lift --edge for text use | |
| SET-14 | Toggle knob colour (dark, ON) | — (--knob single-definition, flagged in HANDOVER) | White knob on --accent → 2.16:1 contrast in dark | Give --knob a dark value, or use --accent-ink | |
| SET-15 | Model-catalog × hover | style-hover border-colour + colour (#9c3b30) | Colour only; border unchanged | New .v2-hover-bad-bdc rule (border+colour) | |
| SET-16 | Catalog typeahead UI | Anchored dropdown, pre-highlighted row, bolded matches, match-count footer | Plain inline list, no bolding, no hint, no footer | Keep simpler list, or build design's dropdown | |
| SET-17 | Catalog "×" on seeded models | delDisplay: custom-only — seeded rows cannot be removed | × rendered on all 44 rows incl. seeded | Keep code (useful), or match design (custom-only) | |
| SET-18 | Advanced section triggers | H-1B refresh + Job cleanup rows present | Both rows missing; only Proxy/API key/DB backup shown | Add rows back, or confirm Stats is the home | |
| SET-20 | Numeric/cron box & Select widths | Mono boxes 170px; wide Selects 340px | Mono boxes 135px; wide Selects 260px | — | |
| SET-21 | Edit modal size | 680×640, textarea min-height 220px | min(1020px,94vw)×min(1280px,92vh), textarea 440px | — | |
| SET-22 | Webhook-secret preview control | Bordered 260px box, muted text (like other values) | Bare mono span, flex:1 (measured 497px) | — | |
| SET-23 | Empty model-catalog popover | — | 260×12px empty bordered box, no guidance | Muted "no models for this provider" row | |
| SET-24 | Section subtitles / row labels | Original subtitles/labels (5 rewritten, 2 renamed, 1 reordered) | Rewritten copy; some code strings more accurate than design | Adopt design copy where code isn't more correct | |

## Shell (7)

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| SHELL-02 | Theme toggle (footer/collapsed ◐) | Cycles Light→Dark→System, icons ◐/◑/◒, tooltip names mode | Boolean flip only, icon always ◐, static tooltip | One theme store (light/dark/system) — larger effort | |
| SHELL-04 | Welcome modal step/✕ hover | Steps: no hover; ✕ hovers to #1b1a16 (--text) | Step bg → --surface-2; ✕ → accent colour | Keep (link-affordance consistency) or match board | |
| SHELL-05a | Rail width transition speed | 220ms | .32s | — | |
| SHELL-05b | Rail dim text colour | #66604f | #948d7a light / #8a8371 dark | — | |
| SHELL-05c | Health dot colour | #7fae8f | --rail-accent #8dbb9f | — | |
| SHELL-05d | Rail background in dark mode | Rail stays dark in both themes: #22211c | #100f0b | — | |
| SHELL-05e | Collapsed warn-dot position | left:34 | left31/top8 | — | |

---


## Résumés — re-check against the canonical `Resumes Shelf` board (12)

The Stage 3 Résumés pass measured against `Resumes Home D`. Re-checked against Shelf: RES-22's headline ("design is a two-pane browser") is withdrawn, RES-13 / RES-14 / RES-09 / RES-23 are moot (Shelf does what the code does, or the fix is live), and the code's card hover (`--hover-soft` lift on an `--edge` border) is an exact match to Shelf. Full detail: `stage3/resumes-shelf-recheck.md`.

| ID | Element | Design says | Code does | Agent's recommendation | Your call |
|---|---|---|---|---|---|
| RES2-01 | The shelf header carries a border the canonical board does … | `Resumes Shelf.dc.html:56` — `padding:22px 30px 14px;display:flex;align-items:flex-end;gap:16px` and **no bor… | measured `padding: 22px 30px 16px 24px`, `gap: 18px`, `border-bottom: 1px solid rgb(226,221,208)` (`--line`).… | drop `borderBottom`; set `paddingBottom: 14`, `gap: 16`. |  |
| RES2-02 | The search field is inset 2 px, not 13, so its text starts … | `Resumes Shelf.dc.html:62` — `height:36px;width:300px;padding:0 13px`. The 13 px inset is what lines the plac… | measured `paddingLeft: 2px`, `paddingRight: 2px` (h36 ✓, w300 ✓, fontSize 13 ✓, border-bottom 1px `--line` ✓)… | `padding: '0 13px'`; optionally restore the example in the placeholder. |  |
| RES2-03 | The shelf drops three of the board's affordance labels/tool… | `Resumes Shelf.dc.html`: | measured: base card `title` = `null`; no "Recent copies" span exists anywhere in the shelf DOM; chip `title` … | add the base-card `title`; add the "Recent copies" label span to both chip rows… |  |
| RES2-04 | Card hover — the background matches the board exactly; only… | `Resumes Shelf.dc.html:744-751` (`cardHover`): `cardBg: lit ? "#f4f8f5" : "#fff"`, `cardBd: lit ? "#8a826e" :… | measured on both the Persona and a base card: `border-color rgb(226,221,208) → rgb(63,107,82)` (`--line` → `-… | none required for the background. For the border, either accept the accent as t… |  |
| RES2-05 | Chip hover text goes to `--good`; the board darkens it past… | `Resumes Shelf.dc.html:769` — `chipFg: hovered ? "#26543c" : "#57534a"`. `#26543c` is a deliberately darker g… | measured `color rgb(87,83,74) → rgb(63,107,82)` (`--text-2` → `--good`/`--accent`). The other three propertie… | none, or add a `--accent-deep` token if the extra contrast is wanted. |  |
| RES2-06 | Four border-only hovers in the board also lift their backgr… | all four are `border-color:#3f6b52` **only** in `Resumes Shelf.dc.html` (`:71`, `:127`, `:411`, `:412`), and … | measured on the search result row and on the archived band: `border-color rgb(226,221,208) → rgb(63,107,82)` … | give the outlined rows/pills `.v2-bd` (`theme.css:153`, border-only — it alread… |  |
| RES2-07 | The search and archived views add a `‹ Back` control and a … | `Resumes Shelf.dc.html:67-81` — the searching branch renders exactly one label (`{{ resultLine }}`, `padding:… | measured: a `display:flex; gap:10px; padding:4px 2px` row containing `‹ Back` (12px, `--accent`, `.v2-navlink… | none if the back control is wanted (it is a genuine usability addition over a m… |  |
| RES2-08 | The Add modal deviates from the board in width, height, typ… | `Resumes Shelf.dc.html:552-563`: `width:400px`, `padding:18px 22px`, `gap:11`, title Newsreader 18px reading … | measured: panel **420 × 234.5**, `padding: 22px`; title `New base résumé` at **19px**; an extra 12px sub-line… | if matching: 400 px, `18px 22px`, 18px title "Add résumé", input h33/`0 10px`/t… |  |
| RES2-09 | Editor top-bar name clamps at 460 px, the board at 420 | `Resumes Shelf.dc.html:142` — `max-width:420px`. At 420 the ellipsised name leaves the status string room at … | measured `max-width: 460px` on both fixtures (rendered widths 22 px and 207.7 px, so it does not currently cl… | `maxWidth: 420`. |  |
| RES2-10 | The copy band's lineage cluster: a text divider instead of … | `Resumes Shelf.dc.html`: | measured: the divider is the literal string `" │ "` coloured `rgb(226,221,208)` (`--line`, one step lighter t… | replace the glyph with `<span style={{width:1,height:11,background:'var(--edge)… |  |
| RES2-11 | The ⋯ trigger is transparent, so the band tint shows throug… | `Resumes Shelf.dc.html:172` — `background: {{ menuBg }}` where `menuBg = S.menuOpen ? "#eaf1eb" : "#fff"`. Ag… | measured closed: `background rgba(0, 0, 0, 0)` (so the button reads as the `--surface-2` band), `border 1px r… | `background: headMenu ? 'var(--accent-soft)' : 'var(--surface)'`. |  |
| RES2-12 | Section-header hover uses `--surface-2` and also changes th… | `Resumes Shelf.dc.html:212, 242, 260, 270, 306, 333, 358, 390` — every section header and every experience-en… | measured header class `v2-hover-accent`; rule `background:var(--surface-2) !important; color:var(--text) !imp… | `background: var(--bg)` and drop the colour override for these headers (or intr… |  |

## Excluded (functional, not design)

Findings that met P3/P4 + "needs decision" but are functional bugs (wrong data, missing error handling, dead controls, missing confirm/undo, stale counts, etc.) rather than design deviations — flagged here so they aren't lost, not for design ruling.

**Feed:** FEED-16 Escape closes nothing · FEED-17 keyboard legend and handler disagree · FEED-18 report band mixes best report's identity with active tab's numbers · FEED-19 rescoring gives no signal in detail panel · FEED-20 bulk Save/Skip are silent and leave header counts stale · FEED-21 "Run scoring" with nothing selected is a silent no-op · FEED-22 live iframe mounts before frame-check answers · FEED-29 Save gives no feedback · FEED-31 Dead code · FEED-32 Company menu remembers the previous query · FEED-33 Score/Salary inputs fire one request per keystroke · FEED-34 job with no company still offers "Ignore everywhere" · FEED-38 No load-more or end-of-list indicator

**Searches:** SRCH-09 header "N need attention" and rail count different things · SRCH-10 rail Searches badge diverges after create/duplicate/delete · SRCH-11 legacy url-mode search shows wrong Mode dropdown · SRCH-12 toPayload silently rewrites cleared fields · SRCH-19 until() has no day unit · SRCH-26 backend does not enforce extension-search gating

**Companies:** COMP-18 never-scraped active company reads "healthy" with a green dot · COMP-19 last_run_warning returned but never rendered · COMP-24 globally-excluded rows indistinguishable from per-company exclusions · COMP-26 no in-progress state for test scrape · COMP-27 Add-modal Save stays live while saving, double-POST · COMP-35 Dead code · COMP-37 Escape discards edited draft with no confirmation

**Applications:** APPS-09 detail body collapses to unusable 20px at 1024px · APPS-11 Add-interview has no in-flight guard · APPS-12 blank interview form creates an "Interview/Unscheduled" card · APPS-13 interview ✕ deletes with no confirm and no undo · APPS-14 filtered-out application stays open in detail pane · APPS-15 hand-logged application's history reads "Discovered via a company scrape" · APPS-17 Log modal demands a URL although its copy says off-app · APPS-18 "Cached" never appears until a later refetch · APPS-19 rail Applications badge never refreshed · APPS-21 "Applied on" is a UTC date sent as UTC midnight

**Résumés:** RES-13 "+N more" promises N and delivers a first-word search over everything · RES-15 Escape closes none of the four modals · RES-16 destructive edits have no confirm and no undo · RES-18 Import PDF shows its busy state on the other button · RES-19 archived band and "+N more" search unvirtualised · RES-20 job-less copy's "one next step" can only fail · RES-21 missing/malformed id redirects silently (frontend half) · RES-24 one localStorage key holds section state for every résumé and Persona · RES-25 success toast with "Open ↗" expires in 2.5s · RES-26 freeform tailor never reports completion · RES-27 setSearchParams declared and never used, ?job= inert · RES-28 Dead code and always-false branches · RES-29 archived view has no empty branch, sort comment wrong · RES-30 score poll resolves on any numeric Tailored

**Cover Letters:** CL-11 Download PDF button pushed off-screen below ~1090px · CL-14 Regenerate failures reported behind the modal's scrim · CL-15 Load-error page has no back link, no retry · CL-16 backend: non-UUID cover-letter id returns 500 instead of 404 · CL-17 rail badge never refreshes after a generate or delete · CL-18 neither screen imports Toast.jsx · CL-19 a failed PDF render is invisible · CL-20 Regenerate started in editor shows as unlabelled pending row on list · CL-21 neither screen is keyboard-operable, no focus shown · CL-22 Regenerate keeps no lineage · CL-23 header/gutter/archive counts disagree while a search is typed · CL-25 Escape closes the Regenerate modal mid-run · CL-26 two screens format the same timestamp differently · CL-27 POST /cover-letters returns a context-free row · CL-28 one shared err slot in the editor

**Persona + Stats:** PERS-13 every destructive control is one unconfirmed click and PATCHes immediately · PERS-14 garbage qa_bank entries become blank editable pairs · PERS-15 no keyboard access and no focus styling anywhere on the screen · PERS-21 blank Q&A pairs and empty strings are persisted · STAT-04 Schedules table overflows its card below ~1100px · STAT-06 the funnel is upside down (Saved counts jobs, others count applications) · STAT-09 funnel silently falls back to the status snapshot · STAT-12 "Avg / call" renders $0.0000 · STAT-13 a long-running job reads "Running · 3671s" · STAT-15 30-day series keys on UTC while the backend groups on local dates · STAT-16 nothing on the screen is a link, including the one the rail advertises · STAT-18 both logs are silently truncated · STAT-19 Sankey and funnel disagree on how many applications there are · STAT-22 no keyboard access on Stats

**Settings:** SET-08 optimistic state is never rolled back after a failed save · SET-11 four rows overflow their control column at 1024px · SET-12 no keyboard operability, no labels, no ARIA · SET-25 Edit modal drops keystrokes typed within 600ms of closing · SET-26 leftover scratch résumé in the Default-résumé dropdown · SET-27 PATCH warnings are discarded

**Shell:** none
