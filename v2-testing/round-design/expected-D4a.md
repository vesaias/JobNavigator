# expected-D4a — Button / Pill / IconButton replacements

D4a swaps every inline **primary button**, **danger button**, **secondary pill** and
**icon button** in `frontend/src/v2/*.jsx` (screens, modals, drawers, rail;
`UiGallery.jsx` + `ToastLab.jsx` out of scope) for `Button` / `Pill` / `IconButton`
from `./ui`. Handlers, `title`/`aria-label`, disabled/busy logic, keyboard access,
`data-*` and layout position are untouched; `style` is passed for flex/margin only.

## Mapping rules used
- `Button` sizes: **md** h36 / 13.5 / pad 0 18 · **sm** h33 / 13 / pad 0 15 · **xs** h28 / 12.5 / pad 0 14.
  Nearest height wins: ≥35 → md, 31–34 → sm, ≤30 → xs.
- `Pill` sizes: **md** h31 / 12.5 / pad 0 15 · **sm** h26 / 11.5 / pad 0 13. ≥29 → md, ≤28 → sm.
- `IconButton`: default **26** (bare glyph, `--icon-btn-ink`, 13px, hover `v2-hover-accent`);
  **36** (bordered ⋯ head button, 15px, hover `v2-act`, accent when `on`).
- A disabled/greyed primary becomes `disabled`; a spinner-or-dimmed primary becomes `busy`
  (`Button` renders `--btn-primary-disabled-bg/-ink` for `disabled`, and 0.6 opacity + a
  12px `currentColor` spinner for `busy`).
- A **modal/drawer footer secondary** (Cancel / Close / Reset) becomes `Button variant="secondary"`
  at the **same size as the primary it sits beside**, not a `Pill`: `Pill` md is h31 and `Button` sm
  is h33, so using `Pill` there would leave every Cancel 2 px shorter than its Save. `Pill` keeps the
  filter/toggle/standalone-pill sites (pagers, chips, "Try again", stand-alone Close).
- Migrated dropdown triggers gain `aria-expanded` / `aria-haspopup` where they lacked them (the
  primitives forward them now); nothing visual changes.
- No new visual variants were added to `ui.jsx`.

Rows are `file:line | element text | before → after (properties that change)`.
A row with **zero-pixel** changes nothing and is listed only for the record.

## LoginModal.jsx

| site | element | before → after |
|---|---|---|
| LoginModal.jsx:77 | "Sign in" / "Signing in…" submit | `<button type="submit">` h38 · `border:none` · r99 · accent bg (→ `--edge` while loading) · `--sans` 13.5/500 · no h-padding · own 11px spinner → `Button` (primary md, `busy={loading}`): **height 38 → 36**, **padding 0 → 0 18px** (button is a stretched flex child, so the box width does not change), **loading fill `--edge` → `--btn-primary-bg` at opacity .6**, **spinner 11px → 12px**, element `button[type=submit]` → `div[role=button]` + `onClick={submit}` (form keeps Enter-to-submit through implicit submission) |

### kept inline
- `LoginModal.jsx:50` — 34×34 round accent ✓ badge in the success panel. `// ui: keep — success glyph, not a control`.

## WelcomeModal.jsx

| site | element | before → after |
|---|---|---|
| WelcomeModal.jsx:57 | "Start with Settings →" | inline primary h30 · 12/500 · pad 0 15 → `Button size="xs"`: **height 30 → 28**, **font-size 12 → 12.5**, **padding 0 15px → 0 14px**; gains `role="button"`/`tabIndex=0` (Enter/Space) from `kb()` — it was a bare `<span onClick>` |

### kept inline
- `WelcomeModal.jsx:44` — 22×22 round mono step-number badge (`--surface-2` on `--text-2`). `// ui: keep — step number badge, not an icon button`.

## Persona.jsx

| site | element | before → after |
|---|---|---|
| Persona.jsx:311 | "Try again" (load-error retry) | inline pill h27 · pad 0 13 · 12px · `color:--accent` · transparent bg · 1px `--edge` · hover `v2-act` → `Pill size="sm"`: **height 27 → 26**, **font-size 12 → 11.5**, **ink `--accent` → `--pill-ink`**, **background transparent → `--pill-bg`**, **hover `v2-act` (accent border + `--card-bg-hover` wash) → `v2-bd` (accent border only)** |

## ui.jsx — zero-pixel additions (no new visual variants)

`Button`, `Pill` and `IconButton` gained optional `ariaExpanded` / `ariaHaspopup`
(+ `ariaBusy` on `Button`/`Pill`) pass-through props, so a migrated dropdown
trigger or busy pager keeps the exact ARIA it had inline. No style, size or look
map changed — `/v2/ui` renders identically.

## Stats.jsx

| site | element | before → after |
|---|---|---|
| Stats.jsx:105 | "Load more" / "Loading…" pager (`LoadMore`) | inline pill h26 · pad 0 13 · 11.5 · 1px `--edge` · ink `--text-2` (busy → `--muted`) · hover `v2-bdc` → `Pill size="sm" disabled={busy} ariaBusy`: **background transparent → `--pill-bg`**, **hover `v2-bdc` (accent border + accent ink) → `v2-bd` (accent border only)**, **busy ink `--muted` → `--pill-ink` at opacity .5**; height/padding/font unchanged. Its own 9px spinner is kept as a child |
| Stats.jsx:451 | "Funnel" / "Flow" flow-view toggle | inline pill h23 · pad 0 9 · 10.5 · `fontWeight: on ? 600 : 400` · bg `on ? --accent-soft : transparent` · no hover → `Pill size="sm" on={on}`: **height 23 → 26**, **font-size 10.5 → 11.5**, **padding 0 9px → 0 13px**, **font-weight 600-when-on → 400**, **off background transparent → `--pill-bg`**, **gains hover `v2-bd`** |
| Stats.jsx:541 | "1d/7d/30d/all" LLM-cost period toggle | same signature as :451 → `Pill size="sm" on={on}`: same five changes |
| Stats.jsx:637 | "Type ▾" activity-log filter trigger | inline pill h26 · pad 0 11 · 11.5 · bg `actType ? --accent-soft : transparent` · no hover · `aria-expanded` → `Pill size="sm" on={!!actType} ariaExpanded ariaHaspopup="menu"`: **padding 0 11px → 0 13px**, **off background transparent → `--pill-bg`**, **gains hover `v2-bd`**; `aria-expanded` preserved, `aria-pressed` now also set |

### kept inline
- `Stats.jsx:412` — 16px round `!` glyph in the core-error band. `// ui: keep — not a control`.
- `Stats.jsx:606` — 7px scheduler status dot (`Dot` role, migrates with Tag/Dot). `// ui: keep`.
- `Stats.jsx:653` — the activity-log search `v2-fieldwrap` (r99 box around an `<input>`); an Input-role site, not a pill. `// ui: keep`.
- `Stats.jsx:99` — the file's own local `Pill` helper is a **badge** (mono 9.5 uppercase, `padding 2px 7px`), i.e. the Tag role; left alone, and `./ui`'s `Pill` is imported as `UiPill` to avoid the clash.

## Companies.jsx

| site | element | before → after |
|---|---|---|
| Companies.jsx:93 | "Show N more" test-modal pager (`ShowMore`) | inline pill h26 · pad 0 13 · 11.5 · `--text-2` · 1px `--edge` · hover `v2-bdc` → `Pill size="sm"`: **background transparent → `--pill-bg`**, **hover `v2-bdc` → `v2-bd`** (accent border only, ink no longer turns accent) |
| Companies.jsx:146 | résumé chips in the add modal (`ResumeChips`) | inline pill h27 · pad 0 11 · 11.5 · on/off accent → `Pill size="sm" on={on}`: **height 27 → 26**, **padding 0 11px → 0 13px** |
| Companies.jsx:149 | "Persona" chip (same component) | same as :146 |
| Companies.jsx:418 | "+ Add company" | inline primary h36 · 13.5/500 · pad 0 18 → `Button` — **zero-pixel** (gains `role="button"`/Enter/Space) |
| Companies.jsx:433 | Tier 1/2/3/Untiered filter pills | inline pill h30 · pad 0 13 · 12 · `fontWeight: on ? 600 : 400` → `Pill on={on}` (md): **height 30 → 31**, **font-size 12 → 12.5**, **padding 0 13px → 0 15px**, **font-weight 600-when-on → 400** |
| Companies.jsx:531 | "Active"/"Inactive" row toggle | inline pill h23 · pad 0 11 · 11 · weight 500 · off ink `--muted` → `Pill size="sm" on={c.active}`: **height 23 → 26**, **font-size 11 → 11.5**, **padding 0 11px → 0 13px**, **font-weight 500 → 400**, **off ink `--muted` → `--pill-ink` (`--text-2`)** |
| Companies.jsx:665 | drawer header ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** (gains `role`/Enter/Space + `aria-label` from `title`) |
| Companies.jsx:779 | "Save changes" (drawer footer) | inline primary h32 · 12.5/500 · pad 0 16 · opacity .6 while saving → `Button size="sm" busy={saving}`: **height 32 → 33**, **font-size 12.5 → 13**, **padding 0 16px → 0 15px**, **gains a 12px spinner while saving** |
| Companies.jsx:870 | Depth pills in the add modal | inline pill h26 · pad 0 11 · 11.5 · `fontWeight: on ? 600 : 400` → `Pill size="sm" on={on}`: **padding 0 11px → 0 13px**, **font-weight 600-when-on → 400** |
| Companies.jsx:880 | "Cancel" (add modal) | inline pill h33 · pad 0 14 · 12.5 · no hover → `Button variant="secondary" size="sm"`: **height 33 → 33 (unchanged)**, **font-size 12.5 → 13**, **padding 0 14px → 0 15px**, **gains hover `v2-bdc`** |
| Companies.jsx:881 | "Save" (add modal) | inline primary h33 · 12.5/500 · pad 0 17 · opacity .6 while saving → `Button size="sm" busy={saving}`: **font-size 12.5 → 13**, **padding 0 17px → 0 15px**, **gains a 12px spinner while saving** |
| Companies.jsx:900 | "Close" (test-error modal) | inline pill h31 · pad 0 15 · 12 · `display:inline-flex` · no background · hover `v2-bdc` → `Pill` (md): **font-size 12 → 12.5**, **background transparent → `--pill-bg`**, **hover `v2-bdc` → `v2-bd`**, **display inline-flex → flex** |
| Companies.jsx:945 | "Show/Hide screenshots" | inline pill h26 · pad 0 11 · 11.5 · on/off accent · no hover → `Pill size="sm" on={showShots}`: **padding 0 11px → 0 13px**, **gains hover `v2-bd`** |
| Companies.jsx:947 | test-modal header ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| Companies.jsx:1007 | "Close" (test-modal footer) | inline pill h31 · pad 0 15 · 12 · hover `v2-bdc` → `Pill` (md): **font-size 12 → 12.5**, **hover `v2-bdc` → `v2-bd`** |

### kept inline
- `Companies.jsx:442` — "Make N active" toolbar bulk action: `--accent` ink, `v2-act` hover. `// ui: keep — accent-ink bulk action, paired with the --warn one below; Pill has no tinted variant`.
- `Companies.jsx:446` — "Make N inactive": `--warn` ink, `v2-bd-warn` hover. `// ui: keep — no warn Pill variant`.
- `Companies.jsx:549` — 25×25 round ⋯ row-menu trigger, sized to the (unmigrated) Run/Test row pills next to it; `IconButton`'s bordered look is 36×36/15px. `// ui: keep`.
- `Companies.jsx:773` — drawer-footer "Make active"/"Make inactive": ink swings `--warn`/`--accent` with state. `// ui: keep`.

## Searches.jsx

| site | element | before → after |
|---|---|---|
| Searches.jsx:200 | source/collection chips (`Chip` helper) | inline pill h27 · pad 0 11 · 11.5 · gap 6 · on/off accent → `Pill size="sm" on={on}`: **height 27 → 26**, **padding 0 11px → 0 13px**, **gap 6 → 7** |
| Searches.jsx:216 | depth pills (`DepthPills`) | inline pill h31 · pad 0 12 · 11.5 · gap 5 · `fontWeight: on ? 600 : 400` → `Pill on={on}` (md): **font-size 11.5 → 12.5**, **padding 0 12px → 0 15px**, **gap 5 → 7**, **font-weight 600-when-on → 400** |
| Searches.jsx:573 | "+ New search" | inline primary h36 · 13.5/500 · pad 0 18 → `Button` — **zero-pixel** |
| Searches.jsx:593 | "Cancel" (new-search card) | inline pill h31 · pad 0 13 · 12 · hover `v2-bdc` → `Button variant="secondary" size="sm"` (matches the Create button beside it): **height 31 → 33**, **font-size 12 → 13**, **padding 0 13px → 0 15px**; hover `v2-bdc` unchanged |
| Searches.jsx:594 | "Create search" | inline primary h31 · 12/500 · pad 0 15 · opacity .6 while busy → `Button size="sm" busy`: **height 31 → 33**, **font-size 12 → 13**, **gains a 12px spinner while busy** |
| Searches.jsx:649 | "Active"/"Paused" row toggle (fixed 62px) | inline pill h23 · no h-padding · 11 · weight 500 · off ink `--muted` → `Pill size="sm" on={s.active}` + `style={{flex:'0 0 62px'}}`: **height 23 → 26**, **font-size 11 → 11.5**, **padding 0 → 0 13px** (width still pinned at 62px), **font-weight 500 → 400**, **off ink `--muted` → `--pill-ink`** |
| Searches.jsx:698 | "Cancel" (inline edit form) | same as :593 (`Button variant="secondary" size="sm"`) |
| Searches.jsx:699 | "Save changes" (inline edit form) | same as :594 |
| Searches.jsx:794 | test-modal header ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| Searches.jsx:818 | "All / Kept / Filtered" result tabs | inline pill h26 · pad 0 12 · 11.5 · `fontWeight: on ? 600 : 400` → `Pill size="sm" on={on}`: **padding 0 12px → 0 13px**, **font-weight 600-when-on → 400** |
| Searches.jsx:882 | "Close" (test-modal footer) | inline pill h31 · pad 0 15 · 12 · hover `v2-bdc` → `Pill` (md): **font-size 12 → 12.5**, **hover `v2-bdc` → `v2-bd`** |

### kept inline
- `Searches.jsx:659` — 25px "Run" row pill; its "Test" twin beside it carries an opacity state the scan left unclassified, so migrating one alone would break the pair. `// ui: keep`.
- `Searches.jsx:672` — 25×25 round ⋯ row-menu trigger (same as Companies:549). `// ui: keep`.
- `Searches.jsx:861` — per-row Kept/Ignored/Out verdict badge (Tag role, `cursor:help`, no handler). `// ui: keep`.

## Applications.jsx

| site | element | before → after |
|---|---|---|
| Applications.jsx:344 | "+ Log application" | inline primary h36 · 13.5/500 · pad 0 18 → `Button` — **zero-pixel** |
| Applications.jsx:357 | "Company ▾" filter trigger | inline pill h30 · pad 0 13 · 12.5 · gap 6 · on/off accent → `Pill on={…} ariaExpanded ariaHaspopup="menu"` (md): **height 30 → 31**, **padding 0 13px → 0 15px**, **gap 6 → 7**; gains `aria-pressed` |
| Applications.jsx:570 | "⧉ Generate prep handover for AI" | inline pill h25 · pad 0 10 · 11.5 · gap 5 · hover `v2-bdc` → `Pill size="sm"`: **height 25 → 26**, **padding 0 10px → 0 13px**, **gap 5 → 7**, **hover `v2-bdc` → `v2-bd`** |
| Applications.jsx:607 | "Cancel" (interview edit) | inline pill h27 · pad 0 12 · 11.5 · hover `v2-bdc` → `Button variant="secondary" size="xs"` (matches the Save beside it): **height 27 → 28**, **font-size 11.5 → 12.5**, **padding 0 12px → 0 14px**; hover `v2-bdc` unchanged |
| Applications.jsx:608 | "Save" (interview edit) | inline primary h27 · 11.5/500 · pad 0 13 · opacity .5 while busy → `Button size="xs" busy={intBusy}`: **height 27 → 28**, **font-size 11.5 → 12.5**, **padding 0 13px → 0 14px**, **busy opacity .5 → .6**, **gains a 12px spinner while busy** |
| Applications.jsx:642 | "Cancel" (new interview) | same as :607 (`Button variant="secondary" size="xs"`) |
| Applications.jsx:643 | "Add interview" | inline primary h27 · 11.5/500 · pad 0 13 · greyed by `opacity: .5` when `!canAddInterview` → `Button size="xs" disabled={!canAddInterview}`: **height 27 → 28**, **font-size 11.5 → 12.5**, **padding 0 13px → 0 14px**, **disabled look accent-at-50% → `--btn-primary-disabled-bg` (`--line`) on `--btn-primary-disabled-ink` (`--muted`)** |
| Applications.jsx:693 | prep-modal header ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| Applications.jsx:702 | "Close" (prep modal) | inline pill h31 · pad 0 14 · 12 · hover `v2-bdc` → `Button variant="secondary" size="sm"` (matches the Copy button beside it): **height 31 → 33**, **font-size 12 → 13**, **padding 0 14px → 0 15px**; hover `v2-bdc` unchanged |
| Applications.jsx:703 | "⧉ Copy to clipboard" | inline primary h31 · 12/500 · pad 0 15 · gap 6 · fill `copied ? --good : --accent` · opacity .5 while busy → `Button size="sm" busy={busy}`: **height 31 → 33**, **font-size 12 → 13**, **gap 6 → 8**, **busy opacity .5 → .6**, **gains a 12px spinner while busy**, **the `copied → --good` fill is dropped** (`--good` and `--btn-primary-bg` resolve to the same colour in both themes, so no pixel changes there) |
| Applications.jsx:811 | "Applied with" résumé pills | inline pill h27 · pad 0 11 · 11.5 · on/off accent → `Pill size="sm" on={on}`: **height 27 → 26**, **padding 0 11px → 0 13px** |
| Applications.jsx:838 | "Cancel" (log-application modal) | inline pill h33 · pad 0 14 · 12.5 · no hover → `Button variant="secondary" size="sm"`: **height unchanged (33)**, **font-size 12.5 → 13**, **padding 0 14px → 0 15px**, **gains hover `v2-bdc`** |
| Applications.jsx:839 | "Save application" | inline primary h33 · 12.5/500 · pad 0 17 · opacity .6 while busy → `Button size="sm" busy={busy}`: **font-size 12.5 → 13**, **padding 0 17px → 0 15px**, **gains a 12px spinner while busy** |

### kept inline
- `Applications.jsx:350` — toolbar search `v2-fieldwrap` (r99 box around an `<input>`), an Input-role site. `// ui: keep`.

## CoverLetters.jsx

| site | element | before → after |
|---|---|---|
| CoverLetters.jsx:91 | voice-preset pills (`VoicePicker`) | inline pill h27 · pad 0 11 · 11.5 · hover `v2-bdc` → `Pill size="sm" on={on}`: **height 27 → 26**, **padding 0 11px → 0 13px**, **hover `v2-bdc` → `v2-bd`** |
| CoverLetters.jsx:363 | "✦ Generate cover letter" | inline primary h36 · 13/500 · no h-padding (stretched) · gap 7 · disabled = `--line` on `--muted` → `Button disabled={!canGenerate}`: **font-size 13 → 13.5**, **gap 7 → 8**, **padding 0 → 0 18px** (stretched flex child, so the box width does not change); disabled tokens are identical (`--btn-primary-disabled-bg/-ink` = `--line`/`--muted`); the 10px spinner stays a child |

## CoverLetterEditor.jsx

| site | element | before → after |
|---|---|---|
| CoverLetterEditor.jsx:342 | "↻ Regenerate…" head button | inline primary h36 · 13/500 · pad 0 19 · gap 8 → `Button`: **font-size 13 → 13.5**, **padding 0 19px → 0 18px**; the ↻/spinner child is unchanged |
| CoverLetterEditor.jsx:350 | 36×36 "⋯" head menu trigger | inline bordered icon 36×36 · 15px · ink `--text-2` in both states · bg/border accent when open · no hover class → `IconButton size={36} on={menuOpen} ariaExpanded ariaHaspopup="menu"`: **open-state ink `--text-2` → `--pill-on-ink` (accent)**, **gains hover `v2-act`** (accent border + `--card-bg-hover`) |
| CoverLetterEditor.jsx:527 | "↓ Download PDF" | inline primary h29 · 12/500 · pad 0 15 · gap 6 → `Button size="xs"`: **height 29 → 28**, **font-size 12 → 12.5**, **padding 0 15px → 0 14px**, **gap 6 → 8** |
| CoverLetterEditor.jsx:563 | "Cancel" (regenerate modal) | inline pill h33 · pad 0 14 · 12.5 · no hover → `Button variant="secondary" size="sm"`: **height unchanged (33)**, **font-size 12.5 → 13**, **padding 0 14px → 0 15px**, **gains hover `v2-bdc`** |
| CoverLetterEditor.jsx:566 | "Regenerate" (regenerate modal) | inline primary h33 · 12.5/500 · pad 0 17 · gap 7 · disabled = `--line` on `--muted` → `Button size="sm" disabled={regening || !rSource}`: **font-size 12.5 → 13**, **padding 0 17px → 0 15px**, **gap 7 → 8**; disabled tokens identical; the 9px spinner stays a child |

## Resumes.jsx

| site | element | before → after |
|---|---|---|
| Resumes.jsx:25 | "Show N more" shelf pager (`ShowMore`) | inline pill h26 · pad 0 13 · 11.5 · hover `v2-bdc` → `Pill size="sm"`: **background transparent → `--pill-bg`**, **hover `v2-bdc` → `v2-bd`** |
| Resumes.jsx:158 | "+ New résumé" | inline primary h36 · 13/500 · pad 0 17 → `Button`: **font-size 13 → 13.5**, **padding 0 17px → 0 18px** |
| Resumes.jsx:169 | "Try again" (shelf load error) | inline pill h27 · pad 0 13 · 12 · `--accent` ink · no background · hover `v2-act` → `Pill size="sm"`: **height 27 → 26**, **font-size 12 → 11.5**, **ink `--accent` → `--pill-ink`**, **background transparent → `--pill-bg`**, **hover `v2-act` → `v2-bd`** |
| Resumes.jsx:354 | "Create from scratch" (add modal) | inline primary h40 · flex 1 · 13/500 · no h-padding · disabled = `--line` on `--muted` → `Button disabled={!canCreate}` + `style={{flex:1}}`: **height 40 → 36**, **font-size 13 → 13.5**, **padding 0 → 0 18px** (flex:1, so the box width is unchanged); disabled tokens identical |
| Resumes.jsx:355 | "Import PDF ↑" (add modal) | *not one of the four scanned roles* (the scan left it unclassified), but it is the side-by-side twin of :354 — migrated to `Button variant="secondary" disabled={!!busy}` so the pair stays the same height: **height 40 → 36**, **font-size 13 → 13.5**, **padding 0 → 0 18px**, **background transparent → `--btn-secondary-bg` (`--surface`)**, **hover `v2-act` → `v2-bdc`**, **busy ink `--muted` → `--btn-secondary-disabled-ink` (`--muted`, unchanged) with `--btn-secondary-disabled-border` (`--line`)** |

### kept inline
- `Resumes.jsx:226`, `Resumes.jsx:266` — "tailoring…" in-flight chips (`--bg` on `--line`, no handler): Chip role. `// ui: keep`.
- `Resumes.jsx:231`, `Resumes.jsx:272` — tailored-copy chips (`v2-chip` hover, `--bg` on `--line`): Chip role — their values already *are* the Chip canonical, so they migrate cleanly in the Chip step. `// ui: keep`.
- `Resumes.jsx:234`, `Resumes.jsx:276` — 6px `--warn` "unreviewed changes" dots the scan tagged `btn-danger`. `// ui: keep — not a control`.

## ResumeEditor.jsx

| site | element | before → after |
|---|---|---|
| ResumeEditor.jsx:520 | next-stage head button (label from `stage`) | inline primary h36 · 13/500 · pad 0 19 · gap 8 · **done state = `--accent-soft` on `--accent`**, cursor default → `Button disabled={stage.done}`: **font-size 13 → 13.5**, **padding 0 19px → 0 18px**, **done state `--accent-soft`/`--accent` → `--btn-primary-disabled-bg`/`-ink` (`--line`/`--muted`)** — this is the drift the file's own RES-17 note describes ("a disabled primary pill is --line on --muted across the three builders") |
| ResumeEditor.jsx:526 | 36×36 "⋯" copy-head menu | inline bordered icon 36×36 · 15 · **closed background transparent** · hover `v2-act` → `IconButton size={36} on={headMenu} ariaExpanded ariaHaspopup="menu"`: **closed background transparent → `--pill-bg` (`--surface`)**; open state and hover unchanged |
| ResumeEditor.jsx:551 | "✦ Tailor for a job…" | inline primary h36 · 13/500 · pad 0 19 · gap 7 → `Button`: **font-size 13 → 13.5**, **padding 0 19px → 0 18px**, **gap 7 → 8** |
| ResumeEditor.jsx:555 | 36×36 "⋯" base-head menu | inline bordered icon 36×36 · 15 · bg always `--surface` · ink always `--text-2` · border accent when open → `IconButton size={36} on={headMenu} ariaExpanded ariaHaspopup="menu"`: **open state gains `--pill-on-bg` (`--accent-soft`) and `--pill-on-ink` (`--accent`)** (before, only the border changed) |
| ResumeEditor.jsx:616 | "Retry" (PDF preview error) | inline pill h27 · pad 0 13 · 12 · `--accent` ink · no background · hover `v2-act` → `Pill size="sm"`: **height 27 → 26**, **font-size 12 → 11.5**, **ink `--accent` → `--pill-ink`**, **background transparent → `--pill-bg`**, **hover `v2-act` → `v2-bd`** |
| ResumeEditor.jsx:718 | "Cancel" (copy modal) | inline pill h33 · pad 0 14 · 12.5 · no background · hover `v2-act` → `Button variant="secondary" size="sm"`: **height unchanged (33)**, **font-size 12.5 → 13**, **padding 0 14px → 0 15px**, **background transparent → `--btn-secondary-bg` (`--surface`)**, **hover `v2-act` → `v2-bdc`** |
| ResumeEditor.jsx:720 | "✦ Re-tailor" / "Make copy" | inline primary h33 · 12.5/500 · pad 0 17 · disabled = `--line` on `--muted` → `Button size="sm" disabled={!canRun}`: **font-size 12.5 → 13**, **padding 0 17px → 0 15px**; disabled tokens identical |
| ResumeEditor.jsx:816 | "Cancel" (tailor modal) | same as :718 (`Button variant="secondary" size="sm"`) |
| ResumeEditor.jsx:818 | "✦ Tailor" | same as :720 |
| ResumeEditor.jsx:854 | review-modal header ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| ResumeEditor.jsx:891 | "Done reviewing" | inline primary h33 · 12.5/500 · pad 0 17 → `Button size="sm"`: **font-size 12.5 → 13**, **padding 0 17px → 0 15px** |

### kept inline
- `ResumeEditor.jsx:609` — "↓ Download PDF" is a native `<a href target="_blank">`; `Button` renders a `div`, which would drop the anchor (middle-click, ctrl-click, download). `// ui: keep`.
- `ResumeEditor.jsx:871` — per-change "Drop ↩" / "Keep it" button: border **and** ink swing `--accent`/`--warn` with the change's state. `// ui: keep — no tinted Pill variant`.

## ResumeSections.jsx

No `btn-primary`, `btn-danger`, `pill` or `icon-btn` sites in the scan — the file's controls are `dashed-add`, `menu-item`, `section-head` and `input` roles, which belong to later D4 steps. **Untouched.**

## Settings.jsx

| site | element | before → after |
|---|---|---|
| Settings.jsx:645 | "Edit" (prompt/JSON rows) | inline pill h26 · pad 0 12 · 11.5 · hover `v2-bdc` → `Pill size="sm"`: **padding 0 12px → 0 13px**, **hover `v2-bdc` → `v2-bd`** |
| Settings.jsx:745 | manual-trigger buttons (`ActionBtn`) | inline pill h30 · pad 0 14 · 12 · gap 6 · done = `--accent-soft`/`--accent` · hover `v2-bd` → `Pill on={done}` (md): **height 30 → 31**, **font-size 12 → 12.5**, **padding 0 14px → 0 15px**, **gap 6 → 7**; the "on"/done tokens and the hover are already canonical |
| Settings.jsx:897 | prompt-editor modal ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| Settings.jsx:906 | "Reset to default" | inline pill h31 · pad 0 13 · 12 · hover `v2-bdc` → `Button variant="secondary" size="sm"` (matches the Done button beside it): **height 31 → 33**, **font-size 12 → 13**, **padding 0 13px → 0 15px**; hover `v2-bdc` unchanged |
| Settings.jsx:907 | "Done" (prompt editor) | inline primary h31 · 12/500 · pad 0 15 → `Button size="sm"`: **height 31 → 33**, **font-size 12 → 13** |
| Settings.jsx:997 | model-catalog modal ✕ | inline icon-btn 26×26 · 13 · `--muted` · hover `v2-hover-accent` → `IconButton` — **zero-pixel** |
| Settings.jsx:1032 | "Add" (model catalog) | inline primary h31 · 12/500 · pad 0 15 → `Button size="sm"`: **height 31 → 33**, **font-size 12 → 13** |

### kept inline
- `Settings.jsx:515` — header search `v2-fieldwrap` (Input role). `// ui: keep`.
- `Settings.jsx:721` — 15×15 italic-serif "i" info badge (its own optical centring note). `// ui: keep — no Pill/IconButton size is this small`.
- `Settings.jsx:1043` — 22×22 bordered "×" in the model catalog, with the SET-15 `v2-hover-bad-bdc` hover (border **and** glyph turn `--bad`). `// ui: keep`.

## JobFeed.jsx

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:73 | filter-bar dropdown triggers (`Drop`'s default trigger: Company, Source, H-1B, Score, Salary) | inline pill h30 · pad 0 13 · 12.5 · gap 6 · on/off accent · hover `v2-bd` → `Pill on={active} ariaExpanded ariaHaspopup="menu"` (md): **height 30 → 31**, **padding 0 13px → 0 15px**, **gap 6 → 7** (×5 triggers) |
| JobFeed.jsx:727 | "Score N unscored jobs" | inline primary h36 · 13.5/500 · pad 0 18 → `Button` — **zero-pixel** |
| JobFeed.jsx:741 | "from “<search>” ✕" active-search chip | inline always-on pill h30 · pad 0 12 · 12 · gap 7 · `--accent-soft`/`--accent`/accent border · no hover → `Pill on`: **height 30 → 31**, **font-size 12 → 12.5**, **padding 0 12px → 0 15px**, **gains hover `v2-bd`** |
| JobFeed.jsx:776 | 70 / 80 / 90 score quick-picks | inline pill h28 · flex 1 · no h-padding · 12 · off background transparent · hover `v2-bdc` → `Pill size="sm" on={…}` + `style={{flex:1}}`: **height 28 → 26**, **font-size 12 → 11.5**, **padding 0 → 0 13px** (flex:1 keeps the width), **off background transparent → `--pill-bg`**, **hover `v2-bdc` → `v2-bd`** |
| JobFeed.jsx:786 | $150K / $180K / $220K salary quick-picks | same signature as :776 → same five changes |
| JobFeed.jsx:794 | "Status · …" trigger | inline pill h30 · pad 0 13 · 12.5 · **weight 500** · on/off accent · hover `v2-bd` → `Pill on={statusActive} ariaExpanded ariaHaspopup="menu"` (md): **height 30 → 31**, **padding 0 13px → 0 15px**, **font-weight 500 → 400** |
| JobFeed.jsx:848 | bulk-bar "Save" | inline primary h27 · 11.5/500 · pad 0 12 → `Button size="xs"`: **height 27 → 28**, **font-size 11.5 → 12.5**, **padding 0 12px → 0 14px** |
| JobFeed.jsx:1147 | "Score this role" (unscored band) | inline primary h28 · 12/500 · pad 0 14 → `Button size="xs"`: **font-size 12 → 12.5** only |
| JobFeed.jsx:1260 | "Cancel" (tailor/copy picker footer) | inline pill h34 · pad 0 15 · 13 · no background · hover `v2-act` → `Button variant="secondary" size="sm"`: **height 34 → 33**, **font-size 13 → 13 (unchanged)**, **background transparent → `--btn-secondary-bg`**, **hover `v2-act` → `v2-bdc`** |
| JobFeed.jsx:1261 | "Tailor résumé" / "Create copy" | inline primary h34 · 13/500 · pad 0 18 · disabled fill `--edge` → `Button size="sm" disabled={cvBase == null}`: **height 34 → 33**, **padding 0 18px → 0 15px**, **disabled fill `--edge` → `--btn-primary-disabled-bg` (`--line`) with `--muted` ink** (was `--accent-ink` on `--edge`) |
| JobFeed.jsx:1316 | "Cancel" (rescore footer) | same as :1260 |
| JobFeed.jsx:1317 | "Run scoring" | same as :1261 (`disabled={!rescoreSel.length}`; the `pointerEvents:'none'` guard is replaced by `disabled`, which drops the handler and the tab stop) |

### kept inline
- `JobFeed.jsx:826` — 16×16 "?" keyboard-shortcuts badge. `// ui: keep — no primitive is this small`.
- `JobFeed.jsx:849`, `:850`, `:851` (+ the 27×27 ✕ beside them) — the bulk-selection bar's Skip / Score / Tailor / clear buttons sit **on the dark `--rail` pop bar** (`--rail-ink` on `--on-rail-line`); `Pill`'s tokens are light-surface. `// ui: keep`.
- `JobFeed.jsx:894` — the dashed 8.5px uppercase "Score" micro-badge that fills the 34px score disc (`position:absolute; inset:0`). `// ui: keep`.
- `JobFeed.jsx:896` — 16px accent ✓ badge on a selected row's score disc, not a control. `// ui: keep`.
- `JobFeed.jsx:973` / `:975` — the detail-header "Tailor résumé" primary and its 36/30 ⋯: **height tracks the collapsing header** (`headOpen ? 36 : 30`), and `Button`/`IconButton` sizes are fixed; their "Open ↗" sibling is a native anchor on the same pair. `// ui: keep`.
- `JobFeed.jsx:1074` — 4px keyword-coverage meter (tagged `btn-danger` by the scan). `// ui: keep`.
- `JobFeed.jsx:1080` — mono missing-keyword tags on `--bad-soft` (Tag role). `// ui: keep`.
- `JobFeed.jsx:1190` / `:1191` — the frame-blocked panel's "Open in new tab ↗" is a native `<a href target="_blank">`, and "View cached snapshot" is kept at h34 to match it. `// ui: keep`.

## ConfirmDialog.jsx

*(not in the run's file order, but it is a v2 modal with four in-scope sites, so it is included)*

| site | element | before → after |
|---|---|---|
| ConfirmDialog.jsx:20 | "Cancel" (confirm dialog) | inline pill h31 · pad 0 15 · 12.5 · hover `v2-bdc` → `Button variant="secondary" size="sm"`: **height 31 → 33**, **font-size 12.5 → 13**; hover `v2-bdc` unchanged |
| ConfirmDialog.jsx:21 | "Confirm" / "Delete …" | inline primary-or-danger h31 · 12.5/500 · pad 0 16 · fill `danger ? --bad : --accent` → `Button variant={danger ? 'danger' : 'primary'} size="sm"`: **height 31 → 33**, **font-size 12.5 → 13**, **padding 0 16px → 0 15px**; both fills are the same tokens (`--btn-danger-bg` = `--bad`, `--btn-primary-bg` = `--accent`) |
| ConfirmDialog.jsx:50 | "⧉ Copy" / "Copied ✓" (`PromptDialog`) | inline pill h31 · pad 0 13 · 12.5 · **ink `--accent` once copied** · hover `v2-bdc` → `Button variant="secondary" size="sm"`: **height 31 → 33**, **font-size 12.5 → 13**, **padding 0 13px → 0 15px**, **the copied-state `--accent` ink is dropped** (the label still switches to "Copied ✓") |
| ConfirmDialog.jsx:51 | "Cancel" (`PromptDialog`) | same as :20 |
| ConfirmDialog.jsx:52 | "OK" / submit (`PromptDialog`) | inline primary h31 · 12.5/500 · pad 0 16 → `Button size="sm"`: **height 31 → 33**, **font-size 12.5 → 13**, **padding 0 16px → 0 15px** |

## V2App.jsx

No site migrated — every in-scope site is the rail.

### kept inline
- `V2App.jsx:141` — 5px `--warn` "needs attention" dot on a collapsed rail item (tagged `btn-danger`). `// ui: keep`.
- `V2App.jsx:162` — 7px scrape-health dot (`--rail-accent`/`--warn`). `// ui: keep`.
- `V2App.jsx:171` — the rail's 26×26 theme toggle: `--rail-dim` ink with the `v2-navdark` + `v2-themebtn` rail hovers. `IconButton` reads `--icon-btn-ink` and `v2-hover-accent`, which are light-surface tokens. `// ui: keep`.

---

## Scanner gate (`py v2-testing/tools/stylescan.py`)

| role | before | after | after, excluding `ToastLab.jsx` / `UiGallery.jsx` |
|---|---|---|---|
| btn-primary | 39 | 6 | **5** — all listed under "kept inline" |
| btn-danger | 9 | 9 | **9** — every one is a dot, meter or badge the scan mis-tagged; all kept |
| pill | 79 | 26 | **23** — all listed under "kept inline" |
| icon-btn | 9 | 2 | **2** — the rail toggle and the WelcomeModal step badge |

Every remaining in-scope site carries a `// ui: keep — …` (or `{/* ui: keep — … */}`) comment;
verified mechanically (no remaining site is un-annotated). In-scope sites (excluding `ToastLab.jsx`)
were 38 + 9 + 76 + 9 = **132**; **39 kept inline**, **93 migrated**, plus one out-of-scan sibling
(`Resumes.jsx:355` "Import PDF ↑") migrated to keep its pair matched.

## Systemic consequence worth a look before D4b

`Pill` md is **h31** and `Button` sm is **h33**. Every modal-footer pair therefore uses
`Button variant="secondary"` (not `Pill`) so Cancel and Save stay the same height — which is why
those rows show a height change on the *secondary* rather than a 2 px mismatch. The knock-on is that
footers previously drawn at h31 (Searches new/edit cards, Applications prep modal, Settings prompt
editor, ConfirmDialog, PromptDialog) now stand at h33, and footers at h34 (JobFeed's two pickers)
drop to h33. If the design wants footers pinned at 31, the fix is a `Button` size in `ui.jsx`, not
per-site style.
