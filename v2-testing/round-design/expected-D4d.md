# expected-D4d — Menu / MenuItem / SectionHead / Chip / Tag / Dot replacements
### (plus the D4c fix-up: `borderColor: … : undefined` and `Card`'s static cursor)

D4d routes every dropdown-menu container, menu row, collapsible section header,
chip, tag/badge and status dot in `frontend/src/v2/*.jsx` (screens, modals,
drawers; `UiGallery.jsx` + `ToastLab.jsx` out of migration scope) through
`Menu` / `MenuItem` / `SectionHead` / `Chip` / `Tag` / `Dot` from `./ui`.
Open/close state, the fixed scrim + closer pattern, positioning, `aria-expanded`
and every handler are untouched; `style` carries **position and layout only**,
plus the handful of **state tints** noted per row (all palette tokens).

Rows are `file:line | element | before → after`, line numbers post-change. A row
marked **zero-pixel** changes nothing and is listed for the record.

---

## Part 1 — D4c fix-up

| site | change | why |
|---|---|---|
| `Searches.jsx:614` | `borderColor: warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : undefined` → `...(warn ? {borderColor:'var(--warn-line)'} : isOpen ? {borderColor:'var(--accent)'} : null)` | the rest-state `undefined` was spread as a **present** `borderColor` key, which React resolves by clearing the border-colour half of `Card`'s `border` shorthand — all six search cards fell through to the browser/Tailwind default grey `#e5e7eb`. **`rgb(229,231,235)` → `var(--card-border)`** (light `#e2ddd0`, dark `#3e3b32`), 6 cards × 2 themes. Matches the already-correct pattern at `CoverLetters.jsx:308` |
| `ui.jsx` `Card` | `cursor: live ? 'pointer' : 'default'` → `...(live ? {cursor:'pointer'} : null)` | `cursor` is inherited with no per-child override anywhere in the migrated screens, so a **static** card was pushing the plain arrow down through every text node inside it. **Reverts the 536 × `cursor auto → default` entries `reconcile-D4c.md` §(A) recorded** (rest) + the 4 hover ones: selectable card text (Stats KPI numbers and table cells, Persona field labels, Searches summary lines, both résumé-shelf regions) gets its I-beam back. Interactive cards keep `pointer` |
| `ui.jsx` `Band` | `cursor: live ? 'pointer' : 'default'` → conditional spread | same rule; only `interactive={false}` bands are affected (Résumés' three empty/error bands, Cover Letters' pending band, `EmptyState`, ResumeEditor's two tailor-modal bands) — **`cursor default` → unset** |
| `ui.jsx` `Row` | `cursor: onClick ? 'pointer' : 'default'` → conditional spread | aligned for the same reason; **zero-pixel today** — every migrated `Row` site has an `onClick`, so all of them keep `pointer` |

### grep for the `: undefined` style-key pattern
`grep -rn ": undefined" frontend/src/v2/*.jsx` → 30 hits, triaged:

- **1 bug, fixed:** `Searches.jsx:614` (the only `: undefined` **style key on a
  `Card`/`Row`/`Band` call site**, and the only one that lands after a shorthand
  that sets the same property).
- **Harmless, left alone (no shorthand sets the property, so nothing is
  cleared):** `ui.jsx:375/376` (`Row`'s `borderLeft`/`borderBottom` — `Row` draws
  no `border` shorthand), `ui.jsx:484` (`SectionHead`'s `borderRadius`/`padding`),
  `ui.jsx:647` (`Helper`'s `fontFamily`), `Searches.jsx:184` (`gridColumn`),
  `Companies.jsx:457` (a menu row's `background` — since migrated).
  `MenuItem`'s own `borderTop` was rewritten to a conditional spread anyway while
  the file was open.
- **Deliberate `undefined`, must stay:** `Companies.jsx:836` — `background`/`color`
  are `undefined` *on purpose* so the `cc-*` class supplies the hue.
- **Not style keys** (props, handlers, state): the remaining 22 hits
  (`title=`, `onChange=`, `className=`, `aria-current=`, `rel=`, `inputMode=`,
  `top/bottom` in a menu-position state object, `.map(...) : undefined` guards).

**No other `<Card` / `<Row` / `<Band` call site in v2 carries a `: undefined`
style key.**

---

## ui.jsx — additions (all zero-pixel on the screens; `/v2/ui` gains specimens)

| site | change | why |
|---|---|---|
| `Menu` | gains `role` (default `'menu'`) | the same box serves an action menu and an option picker — Settings' typeahead is `role="listbox"`, so are the two template/paper pickers and the cover-letter job picker |
| `MenuItem` | gains **`selected`** → `--menu-item-on-bg` / `--menu-item-on-ink` at weight 500 | the "picked row" tint (sort, template, paper, filter value) was hand-written at 12 sites as `accent-soft` + `accent`; it is now one named state. New tokens `--menu-item-on-bg:var(--accent-soft)` / `--menu-item-on-ink:var(--accent)` in **both** `theme.css` blocks; `Select`'s option row switched from `--pill-on-*` to them (**zero-pixel** — identical values) |
| `MenuItem` | `icon` moves into a fixed **16 px gutter** at `--t-11` / `--label-ink`, centred with flex (was `flex:'0 0 auto'`, unstyled) | every icon menu in v2 already drew that gutter by hand (Searches, Companies, Applications, CoverLetterEditor, ResumeSections' MenuItem) so labels start on one axis. It centres with flex rather than `text-align` alone because the filter menus put a 14/15 px checkbox (a block) in it. A `danger` row's icon inherits the row's `--bad` ink, as before |
| `MenuItem` | gains `hint` / **`hintMono`**, `ellipsis`, `href` + `target`, `role`, `ariaSelected` | `hintMono` is the trailing mono shortcut/count; `ellipsis` opts a row into clipping (menus are fixed-width, but the two "Ignore *company* everywhere" rows deliberately wrap); `href` renders a real `<a>` so a navigating row stays ⌘/middle-clickable (Companies' "View jobs in feed", the cover-letter editor's job link). A `selected` row's hint takes `color: inherit` so its ✓ reads accent, not muted |
| `SectionHead` | caret glyph **`▾ / ▸` → `⌄ / ›`** | the dominant-signature rule: `⌄ / ›` is the pair *every* screen in v2 draws; D3's `▾ / ▸` had no call site outside the gallery. Changing the primitive makes all nine migrations zero-pixel on the caret and moves the diff to `/v2/ui` alone |
| `SectionHead` | caret is `--t-10` / `--label-ink`, `flex:'0 0 auto'` | 10 px muted is the dominant caret; the Feed's report heads drew theirs at 11 (see the drift rows) |
| `SectionHead` | children render **as-is** (the `<span style={{minWidth:0}}>` wrapper is gone) | a head is often a row of its own — a hairline, a count, a status. Zero-pixel for a plain-string head (an anonymous flex item lays out identically); nothing outside the gallery used the wrapper |
| `SectionHead` | gains **`card`** variant: gap 9, `--radius-card`, ink inherited, padding passed as layout | the collapsible **card header** family — Persona's five autofill groups + its Q&A card, `SectionShell`, the experience entry, the cover-letter editor's three letter sections. Six sites that were one signature by hand; now one named variant |
| `SectionHead` | gains `caret="end"` (trailing, adjacent), `caret="pin"` (trailing, `margin-left:auto`), `caret={false}` (caller draws its own) | the Feed's report heads read label → rule → caret; Applications' stage band pins its caret right; the cover-letter editor keeps an SVG chevron that *rotates* rather than swapping glyphs |
| `SectionHead` | gains `hover` (class, default `v2-hover-accent`) | Persona's Q&A head washes to `--amber-hover` (`v2-qahead`) because it sits on the amber card; the `v2-clhead` sites keep their own class |
| `SectionHead` | `cursor: onToggle ? 'pointer' : 'default'` → conditional spread | same Part-1 rule (a static head is text) |
| `Tag` | gains **`tone="none"`** (no colour keys at all) | the ATS / search-mode / tier badges are a separate hue taxonomy painted from a `cc-*` / `sm-*` class (theme.css says so explicitly); an inline tone would beat the class |
| `UiGallery.jsx` | specimens added: option menu (selected / mono hint / ellipsis / anchor row), `SectionHead` `caret end` + `pin` + `card`, `Tag tone="none"` | the "a variant is rendered on /v2/ui" convention. **`/v2/ui` is expected to differ**: caret glyph, MenuItem icon gutter, and the four new specimen rows |

---

## Persona.jsx

| site | element | before → after |
|---|---|---|
| Persona.jsx:348 | the five **autofill group card headers** | inline `flex · gap 9 · pad 11 14 · r9 · lh 18 · cursor pointer · v2-clhead · kb() · aria-expanded`, caret `⌄/›` 10 px muted → `SectionHead card hover="v2-clhead" style={{padding:'11px 14px'}}` — **zero-pixel** (gap 9, `--radius-card`=9, lh 18px, caret 10/`--label-ink`=muted all match; the container's `font-size` goes 14 → 12.5 but every child sets its own) |
| Persona.jsx:371 | the **Q&A bank card header** (inside the kept amber card) | same signature with `v2-qahead` → `SectionHead card hover="v2-qahead"` — **zero-pixel**; the amber hover wash is preserved by the `hover` prop |

### kept inline
- `Persona.jsx:134` — the 15×15 **checkbox indicator** (already `// ui: keep` from D4c).
- `Persona.jsx:363`/`:383` — the amber Q&A **card** and its entry rows (D4c keeps).

## Stats.jsx

| site | element | before → after |
|---|---|---|
| Stats.jsx:647 | activity-log **type menu** | `<span>` · `--surface` · 1px `--line` · r10 · `--shadow-menu` · pad 5 · gap 1 → `Menu` — **zero-pixel** (canonical, exactly) |
| Stats.jsx:649 | its six **type rows** | `pad 6 9 · r6 · 12/16px · text-2 · accent-soft+accent+500 when picked · trailing ✓ 10 px accent` → `MenuItem selected hint="✓"`: **pad 6 9 → 7 11**, **12 → 12.5**, **line-height 16px → inherited (19px)** (row 28 → 33 px, menu grows ~30 px), **✓ 10 px → `Helper size="xs"` 10.5/16 in the row's accent ink** |

### kept inline
- `Stats.jsx:106`, `:617` — **Spinner-role** rings (the scan files a 1.5 px round bordered box under `dot-or-badge`); the `spinner` role is not part of D4d. `// ui: keep`.
- `Stats.jsx:402`, `:414` — "Refresh" and "Try again": `v2-hover-accent-text` **links**, which the scanner files under `section-head` by hover-class prefix. They belong to the `link` role (D4e).
- `Stats.jsx:659` — the log-header `v2-fieldwrap` search composite (D4b keep).

## Settings.jsx

| site | element | before → after |
|---|---|---|
| Settings.jsx:999 | the model-catalog **typeahead listbox** | `role="listbox"` · 1px `--line` · **r8** · `--shadow-menu` · **pad 4** → `Menu role="listbox" style={{…, gap:0}}`: **radius 8 → 10 (`--radius-menu`)**, **padding 4 → 5** |

### kept inline
- `Settings.jsx:1004` — the **typeahead rows**: the highlight is keyboard-driven (`hi`), so a row turns its own `v2-menuitem` hover *off* when highlighted and needs `onMouseEnter`/`onMouseDown` to keep the caret in the input. `MenuItem` owns its hover class and takes neither. `// ui: keep`.
- `Settings.jsx:117`/`:122` — the **switch** track + sliding knob: one control, not a status dot. `// ui: keep`.
- `Settings.jsx:465` — Spinner-role ring. `// ui: keep`.
- `Settings.jsx:541` — the footer `<a>` links (scanner-classified as `section-head`; `link` role, D4e).

## Resumes.jsx

| site | element | before → after |
|---|---|---|
| Resumes.jsx:230, :273 | the **copy chips** on the Persona and base cards | `h26 · pad 0 10 · 1px --line · --bg · r99 · gap 6 · 11.5 · --text-2 · v2-chip` → `Chip onClick style={{maxWidth:250}}` — **zero-pixel** (`--chip-bg`=`--bg`, `--chip-border`=`--line`, `--chip-ink`=`--text-2`); gains `role="button"`, `tabIndex=0` and Enter/Space from `kb()`, and `v2-ctl`'s `line-height:1` (pixel-safe in a fixed-height centred flex row) |
| Resumes.jsx:224, :266 | the in-flight **"tailoring…" chips** | same box, ink `--muted`, no click → `Chip style={{color:'var(--muted)'}}` — **zero-pixel**; the muted ink stays as a state tint (a palette token), because "in progress" is deliberately quieter than a finished copy |

### kept inline
- The 6 px "unreviewed" **dot** inside a chip, and the two 9 px Spinner rings in the in-flight chips. `// ui: keep`.

## CoverLetters.jsx

| site | element | before → after |
|---|---|---|
| CoverLetters.jsx:23 | the shared `POPOVER` const | its look keys (`background`, `border`, `borderRadius`, `boxShadow`, `padding`, `display`, `flexDirection`, `gap`) are **deleted**; it now carries position only | 
| CoverLetters.jsx:67 | the job/résumé/voice **Picker popover** | `--surface` · 1px `--line` · r10 · `--shadow-menu` · pad 5 · gap 1 → `Menu role="listbox"` — **zero-pixel** |
| CoverLetters.jsx:315 | the **stage tag** on a letter row (`Applied` / `Draft` / …) | `r99 · 10 · pad 2 8 · .06em uppercase` + a `cc-*` class → `Tag tone="none" className={STAGE_CLASS[…]}` — **zero-pixel** except `line-height` becoming an explicit 15 px (was the inherited 1.5 × 10 px = 15 px) and the box becoming `inline-flex` |

### kept inline
- `CoverLetters.jsx:72` — the Picker's **two-line option** (label over `sub`): `MenuItem` draws a single-line row, and this Picker is already a documented keep for the same reason. `// ui: keep`.
- `CoverLetters.jsx:110` — `LengthPicker`, a segmented control (D4c keep).
- `CoverLetters.jsx:367` — Spinner-role ring. `// ui: keep`.

## Searches.jsx

| site | element | before → after |
|---|---|---|
| Searches.jsx:673 | the search-card **⋯ menu** | `<span>` · `--surface` · 1px `--line` · r10 · `--shadow-menu` · pad 5 · no gap → `Menu` — **gap 0 → 1** (three rows, so +3 px of menu height) |
| Searches.jsx:677 | Edit / View results / Duplicate | `gap 9 · pad 7 11 · r6 · 12.5 · text-2` + a 16 px centred 11 px muted icon → `MenuItem icon` — **zero-pixel** (this is the canonical signature the primitive was drawn from) |
| Searches.jsx:679 | **Delete search** | same + `--bad` ink, `marginTop 3`, `borderTop 1px --line-soft` → `MenuItem danger icon="✕"`: **marginTop 3 → 0** (the `Menu`'s 1 px gap replaces it), border kept as `--menu-item-sep` (= `--line-soft`) — net **2 px tighter** above the divider |

### kept inline
- `Searches.jsx:806` — the **mono source badges** (`jobspy_linkedin 12` …): their hue comes from the `cc-` / `sm-` class taxonomy, which an inline `Tag` tone would beat, and they are mono at pad 1 7, not the uppercase .06em sans form. `// ui: keep`.
- `Searches.jsx:195` — the local `Chip` here is a **`Pill` wrapper** (a source toggle), not the `Chip` role; unrelated name collision, untouched.
- `Searches.jsx:203` — checkbox indicator; `:658`/`:666`/`:670` — the 25 px Run/Test/⋯ pills (D4a/D4c keeps); `:706` — Spinner-role ring.
- `Searches.jsx:629` — "Acknowledge": a `v2-hover-accent-text` **link** the scanner files under `section-head` (`link` role, D4e).

## Companies.jsx

| site | element | before → after |
|---|---|---|
| Companies.jsx:450 | the toolbar **sort menu** | 1px **`--edge`** · r10 · `--shadow-menu` · **pad 8** → `Menu`: **border `--edge` → `--menu-border` (`--line`)**, **padding 8 → 5**, **gap 0 → 1** |
| Companies.jsx:454 | its six **sort rows** | `pad 7 9 · r6 · 12.5 · accent-soft/accent/500 when picked · bare ✓` → `MenuItem selected hint="✓"`: **pad 7 9 → 7 11**; the ✓ moves into the hint slot (`Helper size="xs"` 10.5, inheriting the row's accent ink) |
| Companies.jsx:496 | the **tier tag** (`T1` / `T2` / `—`) | `r99 · 10 · pad 2 8 · .06em uppercase` + `cc-tierN` class → `Tag tone="none" className={tierSlug(…)}` — **zero-pixel** apart from the explicit 15 px line-height and `inline-flex` box |
| Companies.jsx:500 | the row **health dot** | `7×7 · r99 · background h.dot` → `Dot style={{background:h.dot}}` — **zero-pixel** (`h.dot` is a palette token: `--accent` / `--good` / `--warn` / `--bad` / `--edge`) |
| Companies.jsx:544 | the row **⋯ menu** | `<span>` · 1px `--line` · r10 · pad 5 · no gap → `Menu` — **gap 0 → 1** |
| Companies.jsx:545, :546 | Edit config / Open career page | canonical 16 px-gutter rows → `MenuItem icon` — **zero-pixel** |
| Companies.jsx:547 | **View jobs in feed** | a real `<a href>` with the same row style → `MenuItem icon href` — **zero-pixel**; the anchor survives (⌘/middle-click still opens a new tab) because `MenuItem` renders `<a>` when `href` is set |
| Companies.jsx:549 | **Delete company** | `--bad` + `marginTop 3` + `borderTop --line-soft` → `MenuItem danger icon="✕"`: **marginTop 3 → 0** (2 px tighter, as in Searches) |

### kept inline
- `Companies.jsx:131` `Seg`, `:528`/`:536` Run/Test pills, `:768` drawer Test pill (D4a/D4c keeps).
- `Companies.jsx:503` the ATS badge and `:492` the `+N` alias badge — mono class-toned badges the scan does **not** file under `tag`; untouched.
- `Companies.jsx:558` — Spinner-role ring. `// ui: keep`.
- `Companies.jsx:677` — "Acknowledge" link (`link` role, D4e).

## Applications.jsx

| site | element | before → after |
|---|---|---|
| Applications.jsx:59 | the shared `POPOVER` const | look keys deleted; position only |
| Applications.jsx:358 | the **company-filter popover** | 1px `--line` · r10 · **pad 6** · gap 1 → `Menu`: **padding 6 → 5** |
| Applications.jsx:363 | its **company rows** | `pad 6 8 · r6 · gap 9 · 12.5/18px · muted when closed-band · 14 px checkbox · mono 10.5 count · first-of-band `marginTop 5 / paddingTop 10 / borderTop 1px --line`` → `MenuItem ellipsis hint hintMono divider={first}` with the checkbox in the icon slot: **pad 6 8 → 7 11** (and 10 → 11 top pad on the band's first row), **checkbox gutter 14 → 16 px** (the 14 px box centres in it), **divider `--line` → `--menu-item-sep` (`--line-soft`)**, **line-height 18px → inherited 19px** |
| Applications.jsx:384 | the **sort popover** | same const → `Menu`: **padding 6 → 5** |
| Applications.jsx:388 | its **sort rows** | `pad 7 9 · accent-soft/accent/500 when picked · ✓ 10 px accent` → `MenuItem selected hint="✓"`: **pad 7 9 → 7 11**, ✓ → 10.5 in the row's ink |
| Applications.jsx:410 | the **stage band header** (Applied / Interview / Offer / Rejected) | `gap 8 · pad 12 8 5 · **r7** · lh 16px · v2-hover-accent`, trailing `⌄/›` 10 px muted with `margin-left:auto` → `SectionHead boxed caret="pin"`: **radius 7 → 6 (`--radius-field`)**; gains `aria-expanded`, `role="button"`, `tabIndex=0` and Enter/Space (it had none) |
| Applications.jsx:412 | the **stage dot** in that header | `7×7 · r99 · st.dot` → `Dot style={{background:st.dot}}` — **zero-pixel** (`--stage-*` tokens) |
| Applications.jsx:517 | the detail **⋯ menu** | same const with `padding:5` → `Menu` — **zero-pixel** |
| Applications.jsx:520 | View job in feed / Open cover letter | canonical 16 px-gutter rows → `MenuItem icon` — **zero-pixel** |
| Applications.jsx:522 | **Delete application** | `--bad` + `marginTop 3` + `borderTop --line-soft` → `MenuItem danger`: **marginTop 3 → 0** |
| Applications.jsx:661 | the **history rail dots** | `8×8 · r99 · h.dot · marginTop 4` → `Dot size={8} style={{background:h.dot, marginTop:4}}` — **zero-pixel** |

### kept inline
- `Applications.jsx:536`/`:541` — the **stage stepper** and its dot, `:829` the log-modal status segments, `:365` the filter checkbox indicator (all excluded by the brief / earlier keeps). `// ui: keep` added on the stepper dot.
- `Applications.jsx:380` — the "Sort ▾" **menu trigger** (a `v2-hover-accent-text` label + value + caret), scanner-classified as `section-head`; it is a trigger, not a head — `link`/`select-trigger` role, D4e.

## JobFeed.jsx

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:84 | `Drop`'s **filter panel** (used by Status / Company / H-1B / Score / Salary / Sort) | 1px **`--edge`** · r10 · `--shadow-menu` · **pad 8** · block flow → `Menu`: **border `--edge` → `--line`**, **padding 8 → 5**, **block → flex column with gap 1** (+1 px between rows) |
| JobFeed.jsx:94 | `Check` — the **checkbox filter row** | `gap 9 · pad 6 8 · r6 · 12.5 · text-2 · 14 px checkbox · mono 11 count with `paddingLeft 10`` → `MenuItem ellipsis hint hintMono` with the checkbox in the icon slot: **pad 6 8 → 7 11**, **checkbox gutter 14 → 16 px**, **count mono 11 → 10.5**, its `paddingLeft 10` replaced by the row's gap 9 |
| JobFeed.jsx:758 | the **company filter rows** | same shape with a 15 px checkbox and a mono 11 count → `MenuItem ellipsis hint hintMono`: **pad 6 8 → 7 11**, **checkbox gutter 15 → 16 px**, **count 11 → 10.5** |
| JobFeed.jsx:810 | the **sort rows** | `pad 7 9 · accent-soft/accent/500 when picked · bare ✓` → `MenuItem selected hint="✓"`: **pad 7 9 → 7 11**, ✓ at 10.5 in the row's ink |
| JobFeed.jsx:832 | the **keyboard-shortcuts popover** | 1px `--edge` · r10 · `--shadow-menu` · pad 10 → `Menu role="group" style={{padding:10, gap:0}}`: **border `--edge` → `--line`** only |
| JobFeed.jsx:938 | the row **⋯ menu** | `position:fixed` · 1px `--edge` · r10 · pad 5 → `Menu`: **border `--edge` → `--line`**, **gap 0 → 1** |
| JobFeed.jsx:940 | its four action rows | `gap 10 · pad 8 11 · **13** · text-2 · mono 10 keyboard hint pinned right` → `MenuItem hint hintMono`: **13 → 12.5**, **pad 8 11 → 7 11** (rows ~2 px shorter), **gap 10 → 9**, **hint mono 10 → 10.5** |
| JobFeed.jsx:943 | **Ignore … everywhere** | a separate `1px --line-soft` rule div with `margin 4px 8px`, then a `--bad` row → `MenuItem danger`: the **inset rule is replaced by the item's own full-width `--menu-item-sep` top border** (the rule element is deleted), same as every other danger row in v2 |
| JobFeed.jsx:994 | the detail-header **⋯ menu** | 1px `--edge` · r10 · pad 5 → `Menu`: **border `--edge` → `--line`**, **gap 0 → 1** |
| JobFeed.jsx:1002 | its five action rows | as JobFeed:940; the bold "Re-tailor résumé" row keeps `--text` + weight 600 as a call-site style | 
| JobFeed.jsx:1005 | **Ignore … everywhere** | as JobFeed:943; also `display:'block'` → `'flex'` so the row matches its siblings |
| JobFeed.jsx:1060 | report → **Score breakdown** head | `gap 8 · margin -2 -4 · pad 2 4 · r6 · v2-hover-accent`, trailing `⌄/›` **11 px** → `SectionHead boxed caret="end"`: **caret 11 → 10**, **line-height inherited → 18 px** (the head grows ~1 px); gains `aria-expanded` + keyboard |
| JobFeed.jsx:1086 | report → **Keyword coverage** head | same → `SectionHead boxed caret="end"`: same two changes |
| JobFeed.jsx:1112 | report → **Requirement mapping** head | same at `gap 11`, caret adjacent (not pinned) → `SectionHead boxed caret="end"`: same two changes |

### kept inline
- `JobFeed.jsx:967` — the bare **19×26 caret cell** in the detail header gutter: no label, so there is no head row for `SectionHead` to draw (the title beside it is a separate click target). `// ui: keep`.
- `JobFeed.jsx:1021` — the **report band header**: its caret is a fixed 19 px gutter aligned to the row rail, it carries a 34 px score ring and the résumé tabs, and its body text runs at the band's inherited size, which `SectionHead`'s 12.5/18 px type box would restyle. `// ui: keep`.
- `JobFeed.jsx:1099` / `:1101` — the **mono keyword tags** (matched / missing): mono at pad 3 7 with `--accent-soft`/`--bad-soft` fills, not the uppercase .06em `Tag`. `// ui: keep` on both.
- `JobFeed.jsx:1275` — the **radio indicator** in the base-résumé picker. `// ui: keep`.
- `JobFeed.jsx:984` — the "Open ↗" **anchor**, whose height tracks the collapsing detail header (36/30). `// ui: keep`.
- `JobFeed.jsx:1094` the 4 px coverage meter, `:1191` the Live/Cached segment track, `:895`/`:1177` the ring spinners (D4c keeps).
- `JobFeed.jsx:807`/`:808` — `Drop`'s default **"Sort *value* ▾" trigger**, scanner-classified as `section-head`; it is a trigger (`link` role, D4e).

## ResumeEditor.jsx

| site | element | before → after |
|---|---|---|
| ResumeEditor.jsx:533 | the copy **⋯ menu** | 1px **`--edge`** · r10 · pad 5 · no gap → `Menu`: **border `--edge` → `--line`**, **gap 0 → 1** |
| ResumeEditor.jsx:534, :540, :563 | `MenuHead` ("This copy" / "Job" / "This base") | ResumeSections' local copy (pad 4 11 3 · 9.5/14px · .13em uppercase · `--muted`) → **ui.jsx's `MenuHead`**, value-for-value — **zero-pixel** |
| ResumeEditor.jsx:535–543, :564 | the eight **action rows** | ResumeSections' local `MenuItem` (`gap 9 · pad 7 11 · r6 · **13** · text-2`, 16 px icon gutter, 10.5/16 `--faint` hint) → ui.jsx's `MenuItem` with children instead of `label=`: **13 → 12.5**; icon gutter, hint size/ink and padding are unchanged |
| ResumeEditor.jsx:544, :565 | **Delete copy / Delete résumé** | a rule div (`1px --line-soft`, `margin 4px 8px`) + a hand-rolled `--bad` row at 13 px → `MenuItem danger icon="✕"`: the **rule element is deleted** in favour of the item's own `--menu-item-sep` top border, and **13 → 12.5** |
| ResumeEditor.jsx:562 | the base **⋯ menu** | 1px `--line` · r10 · pad 5 · no gap → `Menu` — **gap 0 → 1** |
| ResumeEditor.jsx:597 | the **template picker** | 1px **`--edge`** · **r9** · pad 5 · no gap → `Menu role="listbox"`: **border `--edge` → `--line`**, **radius 9 → 10**, **gap 0 → 1** |
| ResumeEditor.jsx:598 | its template rows | `pad 7 9 · r6 · 12.5 · accent-soft/accent when picked` → `MenuItem role="option" selected`: **pad 7 9 → 7 11**, **picked row gains weight 500** |
| ResumeEditor.jsx:606 | the **paper picker** | same box → `Menu role="listbox"`: same three changes |
| ResumeEditor.jsx:607 | its paper rows | same → `MenuItem role="option" selected`: same two changes |

### kept inline
- `ResumeEditor.jsx:522` — Spinner-role ring; `:705`/`:794` — **radio indicators** in the base pickers. `// ui: keep`.
- `ResumeEditor.jsx:874`/`:886` — the change-list state badge and inline diff highlight (D4c keeps).

## ResumeSections.jsx

| site | element | before → after |
|---|---|---|
| ResumeSections.jsx:142 (deleted) | the local **`MenuHead`** | deleted — ui.jsx's is the only one now (per the brief: one, not both). ResumeEditor imports it from `./ui` |
| ResumeSections.jsx:143 (deleted) | the local **`MenuItem`** | deleted; its eight call sites move to ui.jsx's (see ResumeEditor above). No other file used it |
| ResumeSections.jsx:156 | `SectionShell`'s **section card header** | `gap 9 · pad 10 14 · r9 · lh 18px · v2-hover-accent · kb() · aria-expanded`, caret `⌄/›` 10 px muted → `SectionHead card` — **zero-pixel** |
| ResumeSections.jsx:265 | the **experience entry header** | same at `alignItems:'baseline'` · pad 9 11 → `SectionHead card style={{alignItems:'baseline', padding:'9px 11px'}}` — **zero-pixel** |

### kept inline
- `:294`/`:302`/`:334`/`:465` field-shaped prose rows, `:389` the skills value box, `:127` `BandRule` (D4c keeps).

## CoverLetterEditor.jsx

| site | element | before → after |
|---|---|---|
| CoverLetterEditor.jsx:34 | the local `Card`'s **collapsible letter-section header** (Header / Recipient / Letter) | `gap 9 · pad 10 14 · borderRadius '9px 9px 0 0' · v2-clhead · cursor pointer`, no keyboard access, with a **rotating SVG chevron** → `SectionHead card caret={false} hover="v2-clhead"` keeping the SVG as its first child — **zero-pixel**; gains `aria-expanded`, `role="button"`, `tabIndex=0` and Enter/Space |
| CoverLetterEditor.jsx:349 | the **⋯ menu** | 1px `--line` · r10 · pad 5 · no gap → `Menu` — **gap 0 → 1** |
| CoverLetterEditor.jsx:351, :354 | View application / View job in feed | `gap 9 · pad 7 11 · r6 · **13**` + 16 px icon gutter → `MenuItem icon`: **13 → 12.5** |
| CoverLetterEditor.jsx:357 | **Open job posting** | the same row as a real `<a href target=_blank>` → `MenuItem icon href target="_blank"`: **13 → 12.5**, anchor preserved (`rel` `noopener noreferrer` → `noreferrer`, the `Link` primitive's convention — `noreferrer` implies `noopener`) |
| CoverLetterEditor.jsx:359 | **Delete letter** | `--bad` at 13 + `marginTop 3` + `borderTop --line-soft` → `MenuItem danger icon="✕"`: **13 → 12.5**, **marginTop 3 → 0** |
| CoverLetterEditor.jsx:490 | the **template picker** | 1px `--line` · r10 · pad 5 · gap 1 → `Menu role="listbox"` — **zero-pixel** |
| CoverLetterEditor.jsx:492 | its template rows | `pad 7 9 · 12.5 · accent-soft/accent when picked` → `MenuItem role="option" selected`: **pad 7 9 → 7 11**, **picked row gains weight 500** |
| CoverLetterEditor.jsx:505 | the **paper picker** | same → `Menu role="listbox"` — **zero-pixel** |
| CoverLetterEditor.jsx:507 | its paper rows | same → `MenuItem role="option" selected`: same two changes |

### kept inline
- `CoverLetterEditor.jsx:340`, `:480`, `:553` — Spinner-role rings. `// ui: keep`.
- `CoverLetterEditor.jsx:459` the ¶ paragraph card and `:466` its textarea (D4b/D4c keeps).

## Toast.jsx

### kept inline
- `Toast.jsx:63` — Spinner-role ring. `// ui: keep`.
- `Toast.jsx:65` — a **16 px filled glyph badge** (✓ / ✕ on the toast tint), not a status dot: `Dot` draws a bare tone disc with no glyph. `// ui: keep`.

## V2App.jsx

**Nothing to migrate.** Its only round tokens are the two **rail** indicators
(the 5 px "needs attention" badge on a collapsed nav item, the 7 px health dot in
the rail footer) — the rail is out of scope, and both are painted from
`--rail-*` overlays that do not flip with the theme.

---

## Keyboard / semantics — what changed

Every migrated `MenuItem` and `SectionHead` goes through `act()` → `kb()`, so it
is `tabIndex=0`, announces a role (`menuitem` / `option` / `button`), fires on
Enter **and** Space and takes theme.css's `[tabindex="0"]:focus-visible` ring.
Sites that had no keyboard access before and now do: every menu row on Feed,
Companies, Searches, Applications, Stats, the two résumé pickers, the two
cover-letter pickers and both editors' ⋯ menus; the Applications stage bands; the
Feed's three report heads; the cover-letter editor's three section headers.
`aria-expanded` is new on the Applications stage bands, the Feed report heads and
the cover-letter section headers. Menus that pick a value announce
`role="listbox"` / `role="option"` / `aria-selected`. Two anchor rows
(Companies "View jobs in feed", the cover-letter editor's job link) stay real
`<a href>` elements. `MenuHead` labels are unchanged and still sit inside their
menus. The Feed row ⋯ menu keeps its `position:fixed` flip-up positioning
(`left`/`top`/`bottom` from `rowMenu`), and every screen keeps its fixed scrim +
closer div.

---

## Scanner — before → after (`py v2-testing/tools/stylescan.py`)

| role | before | after | migrated | remaining |
|---|---|---|---|---|
| `menu` | 6 sigs / 14 sites | **0 / 0** | 14 | none. (Two further menu boxes the scan filed under `modal-panel` because of their `--edge` border — `JobFeed.jsx:84` `Drop` and `JobFeed.jsx:938` the row menu — also migrated; both now read `(no design keys)` there, so **20 menu containers** in total) |
| `menu-item` | 22 / 32 | **3 / 3** | 29 | `ui.jsx:342` (the `Select` listbox row — a primitive), `CoverLetters.jsx:72` and `Settings.jsx:1004`, both `// ui: keep` above |
| `section-head` | 14 / 19 | **8 / 11** | 8 | 2 `// ui: keep` (`JobFeed.jsx:967`, `:1021`) + **9 that are not section heads**: `v2-hover-accent-text` links and menu triggers the scanner files here by hover-class prefix — `Applications.jsx:380`, `JobFeed.jsx:807`, `:808`, `Stats.jsx:402`, `:414`, `Companies.jsx:677`, `Searches.jsx:629`, `Settings.jsx:541`, `WelcomeModal.jsx:35`. They belong to the `link` role and are D4e's |
| `chip` | 1 / 1 | **1 / 1** | 4 | the remaining site is `ui.jsx`'s own `Chip` definition. The four screen chips were filed under `pill` by the scan (`Resumes.jsx:225/231/268/275`), which is why `pill` drops 24 → 20 |
| `tag` | 3 / 4 | **2 / 2** | 2 | `JobFeed.jsx:1099` and `Searches.jsx:806`, both `// ui: keep` (mono, class-toned) |
| `dot-or-badge` | 17 / 26 | **14 / 23** | 3 | 23 kept: **11 Spinner-role rings** (the `spinner` role owns them and no D4 step claims them — flagged), **5 radio-indicator sites**, the Applications stage-stepper dot, the Settings switch track + knob, the Feed's 4 px coverage meter and its 36/30 anchor pill, and Toast's 16 px glyph badge. Every one carries a `// ui: keep` |

Side effects, all accounted for: `helper-text` 171 → 149 (menu-row label/hint
spans folded into `MenuItem`'s children/hint), `rule` 13 → 10 (three inset
divider divs replaced by `MenuItem danger`'s own top border), `pill` 24 → 20 (the
four Résumés chips), `modal-panel` 9 sigs → 7 (the two Feed menu boxes above),
`layout` 576 → 597 and `label` 63 → 64 (call-site style objects and the two new
gallery specimens). No role gained an unexplained site.

**75 elements migrated across 12 files** — 20 menu containers, 37 menu rows,
9 section headers, 4 chips, 2 tags, 3 dots — plus ResumeSections' local
`MenuHead`/`MenuItem` deleted in favour of ui.jsx's.
**Drift fixes (non-zero-pixel): 41** — 6 menu borders `--edge` → `--line`,
4 menu paddings (8→5, 8→5, 6→5, 4→5), 2 menu radii (9→10, 8→10), 9 menus gaining
the canonical 1 px row gap, 13 row-padding/size canonicalisations (6 8 → 7 11,
7 9 → 7 11, 13 → 12.5, 12 → 12.5), 3 danger-row `marginTop 3 → 0`, 3 inset rule
divs replaced by the item border, and 1 radius (Applications' stage band 7 → 6).
