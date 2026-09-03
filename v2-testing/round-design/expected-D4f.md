# expected-D4f — D4e fix-up + ModalPanel / Drawer / HeaderRow / TableHead / Rule / Surface

Two parts.

**Part 1** repairs the one regression `reconcile-D4e.md` found (the Settings row-help
wrap) and adds the four primitive capabilities the D4e keeps were waiting on:
`Heading strong`, `Link rel`, `Helper onClick`, `Spinner weight="bold"`.

**Part 2** routes every modal panel (with its scrim), the one drawer, every screen /
modal / card header row, every column-caption strip, every thin rule and the
recessed `--surface-2` blocks in `frontend/src/v2/*.jsx` through `ModalPanel` /
`Drawer` / `HeaderRow` / `TableHead` / `Rule` / `Surface` from `./ui`
(`UiGallery.jsx` + `ToastLab.jsx` out of migration scope).

Rows are `file:line | element | before → after`, line numbers **after** the change.
A row marked **zero-pixel** changes nothing and is listed for the record.

**Scanner counts (`tools/stylescan.py`, all of `frontend/src/v2/`)**

| role | before | after | migrated | what the "after" is |
|---|---|---|---|---|
| modal-panel | 22 | **3** | 19 | `JobFeed:84`, `JobFeed:940` (menu positioning wrappers, no design keys) + `Toast:91` (the stack container) |
| drawer | 1 | **0** | 1 | — |
| header-row | 41 | **7** | 34 | 5 table **body** rows + the Settings row divider + `ToastLab` (out of scope) |
| scrim | 28 | **9** | 19 | 8 invisible click-catchers (`position:fixed;inset:0;zIndex` and nothing else) + `ui.jsx`'s own |
| rule | 10 | **4** | 6 | the Feed's score **meter** (track + fill), `V2App`'s rail hairline, `UiGallery` |
| surface-block | 65 | **51** | 14 | see "the surface-block bucket" below — it is not one role |
| heading | 29 | **17** | 12 (+5 const) | 6 serif score numerals, 8 orphan 400-weight display sizes, the 2 wordmarks, `ToastLab` |
| toast | 1 | 1 | 0 | the toast card — a named keep, see below |

The scanner only sees literal `style={{…}}` objects, so it **undercounts**: `Stats`'
`H` const (5 card-title sites) and its `COL` const (3 table-head sites) migrated
without ever appearing in the count.

---

## Part 1 — the D4e fix-up

### 1a. The Settings row-help wrap (`reconcile-D4e.md`'s one UNEXPECTED)

D4e put the shared settings-row help through `Helper` (11.5 px) where it had been a
hand-written 11 px span, inside a description column pinned at `flex:'0 1 340px'`.
The longest string on the page then wrapped to a second line and grew its row
55 px → 71 px.

**Fix, at the layout level (`Settings.jsx:717`):**

| site | element | before → after |
|---|---|---|
| Settings.jsx:717 | settings-row description column | `flex: '0 1 340px'`, `minWidth: 200` → `flex: '0 1 356px'`, `minWidth: 210` |

**Why 356 and not the suggested 380.** Text layout is linear in font size, so a
column scaled by the same ratio as the font breaks on exactly the same words:
340 × 11.5 / 11 = **355.45**, rounded **up** to 356 (and 200 × 11.5/11 = 209.1 → 210).
The 0.55 px of slack is far narrower than a space (≈ 2.8 px at this size), so it
cannot pull a word up either — line counts are identical to D4d **by construction**,
for every row, not just the one that regressed. 380 px would have been the opposite
mistake: it is 24 px wider than proportional, so every help string that *already*
wrapped at D4d (there are eight multi-line rows) would have re-flowed and **shrunk**
its row — the same class of regression in the other direction.

`Helper size="xs"` was the other option offered and was rejected for the same
reason: 10.5 px is 0.5 px *below* D4d's 11 px, so a string sitting just past a
boundary would un-wrap and shrink its row; it would also de-canonicalise the one
helper size D4e had just unified across v2.

**Every row in all three tabs, checked by string width.** All 73 help / offHelp
strings were laid out with a proportional-advance model at (11 px, 340 px) and at
(11.5 px, 356 px): **no row changes line count**, as the proportional argument
predicts. (Script kept out of the repo; it is a ~40-line width table.)

Rows whose widest line comes within 20 px of the 356 px box — the ones to re-check
first if this ever moves again:

| row (tab) | lines | tightest line clears the box by |
|---|---|---|
| **Stripped params** (Global exclude → Dedup) | 1 | **0.7 px** |
| Confidence threshold (Email classification) | 1 | 12.1 px |
| Webhook secret (Notifications) | 2 | 12.1 px |
| Session cookie (LinkedIn) | 2 | 14.7 px |
| Body phrases (Global exclude) | 2 | 19.8 px |
| Prompt caching (Scoring) | 2 | 4.1 px |
| Persona tailoring prompt (Tailoring) | 2 | 2.9 px |
| Register webhook (Notifications) | 2 | 4.5 px |

Two caveats on that table. (1) The width model is a generic grotesque, not Public
Sans, so its **absolute** margins run a little wide — run against the D4e geometry
(11.5 px in the un-widened 340 px box) it predicts *Stripped params* and *Confidence
threshold* as the wrappers, where the crawl measured *Autofill*. The ordering, not
the millimetre, is what the table is for. (2) The model does confirm the shape of
the regression: at a fixed 340 px, a 0.5 px font bump flips **more than one** row
across its boundary — which is what accounts for the +48 px of AI-tab growth
`reconcile-D4e.md` could not attribute to the Autofill row alone.

### 1b. `ui.jsx` — the four capabilities the D4e keeps were waiting on

| primitive | change | why |
|---|---|---|
| `Heading` | gains a **`strong`** variant (`strong` = weight 500, `strong={600}` = 600) at sizes **15 · 15.5 · 16 · 17 · 18 · 19**, tracked -.01em to 16 and -.015em from 17 | v2's *second* serif family — the card / column / drawer-section title. D4e left its 17 sites inline because collapsing the two families is a design decision; D4f **names** the family rather than collapsing it. Sizes and weights are exactly the ones already drawn — no site changes size, weight or tracking. New tokens `--t-15-5`, `--t-17` in `theme.css` (both blocks). **Zero-pixel** |
| `Heading strong` | declares **no line-height** | every one of these titles sits in a content-driven card box whose height *is* its own line box; a whole-pixel step would move each card. The three sites with a load-bearing line-height (22 / 23 / 26 px) pass it in `style` with the reason at the call site. **Flagged as needs-decision below** |
| `Link` | gains **`rel`** (overriding the `target="_blank"` default of `noreferrer`) | retires the three D4e keeps that spell out `rel="noopener noreferrer"` — Settings' two colophon links and the Companies test-row ↗. **Zero-pixel** |
| `Helper` | gains **`onClick`** (spreads `act()`, so it brings `kb()` and `cursor:pointer`) | retires the D4e keep at Applications' interview-slot line, which was inline only because "`Helper` takes no `onClick`" |
| `Spinner` | gains **`weight="bold"`** (2 px band) | the user decision in `D1-D2.md` §"Decisions during D4": the Feed's 28 px score ring was deliberately heavy, and D4e's flattening to 1.5 px is reverted through a named variant |
| `ModalPanel` | gains `as="form"` + `onSubmit`, `zIndex`, `scrimProps`, `escape` | see Part 2 |
| `HeaderRow` | gains `as="header"`, `pad`, `bg`, `line`, `height`, `strong` | see Part 2 |
| `TableHead`, `Rule`, `Surface` | **new** | see Part 2 |

### 1c. Part-1 site migrations

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:1186 | the scoring-band 28 px ring | `Spinner size={28}` (1.5 px, D4e) → `Spinner size={28} weight="bold"` — border **1.5 → 2 px**, restoring the pre-D4e band ring (user decision) |
| Stats.jsx:415 | header **Refresh** | `--muted 12.5`, `v2-hover-accent-text v2-ctl` (line-height 1), hand-written `kb()` → `Link` — ink **--muted → --link-ink** (accent), size **12.5 → 11.5**, weight **— → 500**, line-height **1 → 17 px**, role **button → link**. The icon-row layout (`marginLeft:auto`, flex, gap 7) stays in `style`. **The control grows ~4 px and its baseline in the `align-items:flex-end` header moves** — the D4e keep note called this out; it is now the accepted cost of the consistency decision |
| Stats.jsx:431 | error-band **Try again** | inherited `12.5/18px`, `--bad` through `currentColor`, weight 600, dotted underline → `Link` — ink **--bad → --link-ink** (accent), size **12.5 → 11.5**, weight **600 → 500**, line-height **18 → 17 px**. The dotted `currentColor` underline is kept, so it now underlines in accent. **A green word inside a red band** — the deliberate outcome of "migrate like the Companies/Searches/Settings retry links" |
| Settings.jsx:553 / :555 | the two colophon links | `<a … rel="noopener noreferrer" className="v2-hover-accent-text">` → `Link href target rel` with the colophon's own ink/size held in `style` (`--muted`, `fontSize:'inherit'`, `lineHeight:'inherit'`, `fontWeight:400`) — **zero-pixel**; the hover class was already there |
| Companies.jsx:984 | test-row **↗** | `<a … rel="noopener noreferrer">` accent 11 → `Link href target rel` with `fontSize:11`, `fontWeight:400`, `lineHeight:'inherit'` in `style` — **zero-pixel**; gains `v2-hover-accent-text` (a no-op today: `--link-ink-hover` = `--link-ink`) |
| Applications.jsx:620 | interview-slot line | mono `--muted` **10.5**, inherited line-height **15.75**, hand-written `onClick`/`cursor` → `Helper size="xs" mono onClick` — line-height **15.75 → 16 px**; gains `kb()` (tab stop, Enter/Space, `role="button"`), which it did not have |

### 1d. `Heading strong` migrations (the card/column-title family)

All **17** sites, every one **zero-pixel** unless noted (same face, size, weight and
tracking; only the declaration moves into the primitive).

| site | before → after |
|---|---|
| Persona.jsx:159 | `ColumnHead` title, serif 18/500/-.015em → `Heading strong size={18}` |
| Resumes.jsx:211 | Persona card title, serif 19/500/-.015em → `Heading strong size={19}` |
| Resumes.jsx:255 | base-résumé card title (ellipsis clamp kept in `style`) → `Heading strong size={19}` |
| Companies.jsx:681 / :698 / :723 | drawer section titles, serif 15/**600**/-.01em → `Heading strong={600} size={15}` |
| Searches.jsx:578 | "New search" card title, serif 15.5/500/-.01em → `Heading strong size={15.5}` |
| Searches.jsx:620 | search-name card title → `Heading strong size={15.5}` with the **load-bearing `lineHeight:'23px'`** kept in `style` (it holds the card at an integer height) |
| CoverLetters.jsx:313 | letter-row title, serif 15.5/500/-.01em → `Heading strong size={15.5}` with `lineHeight:'22px'` kept in `style`; the `arc ? --text-2 : --text` tint becomes a conditional `color` in `style` (unset = `--heading-ink` = `--text`) |
| CoverLetters.jsx:342 | "Generate new", serif 16/**600**/-.01em → `Heading strong={600} size={16}` |
| Settings.jsx:527 | section title, serif 19/500/-.015em → `Heading strong size={19}` with the load-bearing `lineHeight:'26px'` kept in `style` |
| JobFeed.jsx:909 | feed-row title, serif 16/500/-.01em → `Heading strong size={16}` with `lineHeight:1.15` kept in `style` (the list row's own rhythm) |
| Stats.jsx:464 / :517 / :543 / :559 / :606 | the five card titles that spread the `H` const, serif 17/500/-.015em → `Heading strong size={17}` |

**`Stats.jsx`'s `H` const survives** for its sixth site — the run-history /
activity-log **tabs** (`Stats.jsx:657`), which spread it as the *base* of a
keyboard-operable control (`kb()`, a swapped ink, a 2 px accent underline).
`Heading` renders inert text and takes no handler, so that one is a keep.

---

## Part 2 — ModalPanel / Drawer / HeaderRow / TableHead / Rule / Surface

### 2a. `ui.jsx` — what was added

**`ModalPanel`** (already carried scrim + `useEscape` + `useSnapTop` + `width`) gains:

| prop | why |
|---|---|
| `as="form"` + `onSubmit` | the sign-in overlay's panel *is* a form (Enter-in-field submits) |
| `zIndex` (default 70) | the two global overlays sit at 9998/9999, the in-screen modals at 60; ConfirmDialog keeps 70 |
| `scrimProps` | the two global overlays mount outside the v2 shell and carry the theme root (`className="jn-v2"`, `data-theme`) on the scrim |
| `escape` (default true) | Applications, the Feed and Settings each own Escape for their whole overlay set from one handler that **stands down while a ConfirmDialog is up**; a second unguarded listener here would close the modal *under* that confirm |
| — | `useEscape(onClose, escape && !!onClose)`: a panel with no `onClose` (sign-in — there is nowhere to go back to) registers no listener at all rather than one that swallows Escape and does nothing |

**`HeaderRow`** gains `as="header"` (keeps the five `<header>` landmarks),
`pad` (a named prop, not an inline `padding`, for the heads whose gutter is set by
the pane they sit in), `bg` (`surface` / `page` / `recessed` → new
`--head-bg` / `--head-bg-page` / `--head-bg-recessed`), `line`
(`line` / `soft` / `strong` / **`none`** — the four list screens whose title block
carries no rule), `height`, and a `...rest` passthrough.

**`TableHead`** (new) — the column-caption strip: `--head-bg` ground,
`--label-ink`, **9.5 / 14 px**, `.11em` uppercase, a **`--head-line-strong`**
hairline beneath; `height` (default 28) and `pad` (default `0 22px`) are the list's,
`top` adds the `--head-line-soft` rule above (the Stats cards), `soft` swaps the
bottom rule. New token `--head-line-strong: var(--line-strong)`.

**`Rule`** (new) — the 1 px hairline that is *not* a border on something else:
`tone` = `soft` (`--head-line-soft`, default) / `line` (`--head-line`) / `strong`;
`vertical` + `length` for the tick between two facts in a band.

**`Surface`** (new) — a recessed `--surface-2` block, `radius` from the shared scale
(`card` default, `field`, `row`, `menu`, `none` for the full-bleed pane form),
optional `pad`, `as="section"`.

New tokens in **both** `theme.css` blocks: `--t-15-5`, `--t-17`,
`--head-line-strong`, `--head-bg`, `--head-bg-page`, `--head-bg-recessed`.

### 2b. Canonical values, and the drift fixed against them

D1-D2's canon: modal = `--modal-bg` · 1 px `--modal-border` · radius 12 ·
`--modal-shadow`; header row = pad `16 22 13` + `--head-line` beneath; drawer =
`--drawer-*`.

| # | drift | sites | before → after |
|---|---|---|---|
| 1 | modal ground | 4 | `background: 'var(--recessed)'` → **`--modal-bg`** (= `--surface`): `ConfirmDialog.jsx:16`, `ConfirmDialog.jsx:36` (PromptDialog), `LoginModal.jsx:47`, `WelcomeModal.jsx:29`. Light `#fdfcf9 → #ffffff`, dark `#221f19 → #28251b` |
| 2 | table-head rule | 2 | `borderBottom: 1px var(--line)` → **`--head-line-strong`** (= `--line-strong`): `Companies.jsx:965` (test-scrape rows), `JobFeed.jsx:1132` (requirement table). Light `#e2ddd0 → #c9c3b4` |
| 3 | table-head tracking | 1 | `letterSpacing .12em → .11em` — `JobFeed.jsx:1132` (the requirement head was the one column strip at .12em) |
| 4 | spinner band | 1 | `1.5px → 2px` — `JobFeed.jsx:1186` (Part 1c, user decision) |
| 5 | header/retry link | 2 | Stats `Refresh` + `Try again` (Part 1c, consistency decision) |
| 6 | description column | 1 | Settings `340 → 356px` (Part 1a). Every control in the settings rows shifts **16 px right**; no row changes height |

**Six drift fixes, 11 sites.** Everything else in Part 2 is zero-pixel.

### 2c. Behaviour that changes (all additive, all zero-pixel)

| site | what it gains |
|---|---|
| every migrated modal (19) | `role="dialog"` + `aria-modal="true"` — most of them had neither |
| `Searches.jsx:784` (test-run modal) | **Escape** (RES-15) and the **pixel snap** (RES-32) — it had neither; the scrim already closed it |
| `Settings.jsx:1001` (model catalog) | the **pixel snap** — it had Escape (R3-S-04) but no snap |
| `Settings.jsx:897` (edit modal) | the **pixel snap** — it had its own Escape effect (kept, `escape={false}`, because it is paired with the flush-on-unmount in the same cleanup) |
| `WelcomeModal.jsx:29` | **Escape** — the scrim closed it, the key did not |
| `Companies.jsx` drawer | **Escape** through `Drawer`. Redundant with the screen's own handler (line 231 already calls `closeDrawer()`), and idempotent: a second call re-sets the same confirm object or re-runs `setDrawer(null)` |
| `Applications.jsx:620` | `kb()` on the interview-slot line |
| `Settings.jsx:553/:555`, `Companies.jsx:984` | `v2-hover-accent-text` (a no-op today) |
| `JobFeed.jsx:1037-1039` (band ticks) | `flex:'0 0 auto'` — a 1 px divider can no longer be shrunk away by the band's flex row |
| every `TableHead` | `flex:'0 0 auto'` — inert under a block parent (Companies/Searches), no-shrink under a flex column (Stats/Feed) |

Behaviour deliberately **held**: every modal's scrim-click and dirty-discard path
(`Companies`' `closeDrawer` confirm, `CoverLetterEditor`'s "no close while
regenerating" — expressed as `onClose={regening ? undefined : …}`, which removes
both the scrim click and the Escape listener exactly as the old
`regenOpen && !regening` guard did); the z-index ladder (drawer 30 < screen modals
60 < ConfirmDialog 70 < toasts 80 < welcome 9998 < sign-in 9999); the Settings edit
modal's flush-on-close; the Toast stack.

One structural change worth naming: `Settings.jsx`'s ModelsModal used to render its
ConfirmDialog **inside** its own scrim, wrapped in a `stopPropagation` div so the
confirm's scrim click would not also close the catalog. It now renders as a sibling
of `ModalPanel`, which achieves the same thing without the wrapper.

### 2d. Sites migrated, per file

Counts are of *sites*, not lines.

| file | ModalPanel | Drawer | HeaderRow | TableHead | Rule | Surface | Heading strong | other |
|---|---|---|---|---|---|---|---|---|
| ConfirmDialog.jsx | 2 | — | — | — | — | — | — | — |
| Toast.jsx | — | — | — | — | — | — | — | 2 keeps documented |
| LoginModal.jsx | 1 | — | — | — | — | — | — | — |
| WelcomeModal.jsx | 1 | — | — | — | — | — | — | — |
| Resumes.jsx | 1 | — | 1 | — | — | — | 2 | — |
| ResumeEditor.jsx | 3 | — | 7 | — | 1 | 2 | — | — |
| CoverLetterEditor.jsx | 1 | — | 4 | — | — | 1 | — | — |
| CoverLetters.jsx | — | — | 2 | — | — | — | 2 | — |
| Searches.jsx | 1 | — | 5 | 1 | 1 | — | 2 | — |
| Companies.jsx | 3 | 1 | 8 | 2 | 4 | — | 3 | 1 Link |
| Applications.jsx | 2 | — | 5 | — | — | — | — | 1 Helper |
| JobFeed.jsx | 2 | — | 6 | 1 | 5 | — | 1 | 1 Spinner |
| Settings.jsx | 2 | — | 4 | — | — | 1 | 1 | 2 Link · the column fix |
| Stats.jsx | — | — | 1 | 3 | — | — | 5 | 2 Link |
| Persona.jsx | — | — | 1 | — | — | — | 1 | — |
| **total** | **19** | **1** | **44** | **7** | **11** | **4** | **17** | **9** |

(The `HeaderRow` total exceeds the scanner's 34 because six of the migrated heads
were classified by the scan under `surface-block` — a strip with a background *and*
a bottom rule lands in that bucket, not in `header-row`.)

### 2e. Kept inline, with reasons (all carry a `// ui: keep` at the site)

**Toast** — `Toast.jsx:62` (the card) and `Toast.jsx:91` (the stack container).
D1-D2 files `toast` as "already single" (one site, one signature) and D4f names no
`Toast` primitive to add, so the card stays where its taxonomy, TTL table and stack
live. It is not a `ModalPanel` (no scrim, no Escape, no dialog role) and not a
`Surface` (four tinted grounds, its own r9 + `--shadow-toast`). The stack container
carries no design keys at all — fixed corner, z 80, column, gap 8.

**Table *body* rows the scanner files under `header-row`** (a bottom rule + padding
is the whole signature it matches on): `Stats.jsx:625` (schedules row),
`Stats.jsx:703` (run-history row), `Stats.jsx:725` (activity row),
`Companies.jsx:975` (test-scrape row), `JobFeed.jsx:1138` (requirement row),
`Settings.jsx:717` (the settings row itself — its rule is the list divider).

**Footer bars** — a rule on **top**, which is the opposite of what `HeaderRow`
draws: `Applications.jsx:713` / `:845`, `Companies.jsx:762` / `:867` / `:993`,
`CoverLetterEditor.jsx:549`, `JobFeed.jsx:1295` / `:1350`, `ResumeEditor.jsx:888`,
`Searches.jsx:873`, `Settings.jsx:911`, `WelcomeModal.jsx:59`.

**Rules that are not rules** — `JobFeed.jsx:1081` is a 1 px score **meter** (a
`--line` track with an `--accent` fill), and `V2App.jsx:113` is a rail hairline on
`--rail-line`, a token `Rule`'s `--head-line` pair deliberately does not reach.
`ResumeSections.jsx`'s `BandRule` (1 px on `--edge`, 11 px tall) is already its own
named component and stays one.

**Serif keeps** — the 15 in-scope `heading` sites that remain are *not* the
card-title family:
- six **score numerals** in `scoreColor()` ink: `JobFeed.jsx:888` (19), `:1034` (14),
  `:1079` (15), `ResumeEditor.jsx:486` (13.5), `Resumes.jsx:216` / `:260` (17);
- eight **orphan 400-weight display sizes** off the 18/19/22 scale:
  `Applications.jsx:507` (23), `Companies.jsx:648` (20, the drawer title),
  `JobFeed.jsx:975` (26 ⇄ 17), `LoginModal.jsx:61` (23), `Stats.jsx:575` (23),
  `Stats.jsx:450` (27, the KPI numeral), `WelcomeModal.jsx:36` (21),
  `Settings.jsx:547` (12, the colophon wordmark);
- the two `V2App.jsx` rail **wordmarks** (a named keep since D4e).

**Scrims that are not scrims** — eight `position:fixed; inset:0; zIndex:N`
click-catchers behind an open menu (`CoverLetters:65`, `JobFeed:83` / `:825` /
`:939` / `:996`, `ResumeEditor:533` / `:562`, `Stats:669`). They paint nothing;
there is no design signature for a primitive to own.

**The `surface-block` bucket (51 remaining) is not one role.** What is left is:
page and pane grounds (`background:'var(--surface)'` / `'var(--bg)'` on a
full-height column — layout, not a block); status **dots** (`h.dot`, `st.dot`);
chart fills (`background: c; height: 2`, the funnel bar track); tinted **banners**
inside a pane (the Feed's "not scored" / "scoring in progress" / cached-page bands,
the Stats error band, the Searches `--recessed` config bodies, the CoverLetters
pending row); the dark rail; and `ui.jsx`'s own objects. `Surface` was defined
narrowly — a **`--surface-2` block with a radius from the shared scale** — and
migrated only the four sites that are exactly that: the two PDF-preview panes
(`ResumeEditor.jsx:588`, `CoverLetterEditor.jsx:474`), the preview viewport
(`ResumeEditor.jsx:616`) and the Settings info panel (`Settings.jsx:735`, whose
`borderRadius: 7` **is** `--radius-row`, zero-pixel).

**Other pre-existing keeps** left untouched: the mono-text role, the Tag/badge
role (D4d), the `v2-fieldwrap` composites, the segmented steppers and every
`// ui: keep` D4a-D4e already recorded.

---

## Notes / uncertainties

1. **`Heading strong` declares no line-height.** Every other primitive in `ui.jsx`
   pins a whole-pixel line-height; this one deliberately does not, because at
   Tailwind preflight's 1.5 the six allowed sizes compute to 22.5 / 23.25 / 24 /
   25.5 / 27 / 28.5 px and only two of those are whole. Pinning a step would move
   every card that is sized by its title. **Needs a decision** before D5: either
   pick a step per size and accept the reflow, or keep the line-height at the call
   site (as now) and exempt `Heading strong` from the whole-pixel rule in the
   `ui.jsx` header comment.
2. **Stats `Try again` is now accent inside a `--bad` band.** That is the literal
   consequence of the consistency decision; it is the one migration in this step
   whose *design* outcome is arguable rather than mechanical.
3. **Stats `Refresh` grows.** Moving off `v2-ctl`'s `line-height:1` onto `Link`'s
   17 px makes the control ~4 px taller in an `align-items:flex-end` header, so the
   header's right side will shift a few pixels in the shot diff. Expected, not a
   regression.
4. **`--head-bg-*` are three new semantic tokens** whose only job is to keep a
   background token out of a screen's inline style. If D5's lint would rather see
   header grounds stay inline, they can be dropped and the six `bg=` call sites
   reverted to `style`.
5. `Companies.jsx` has a **local component also called `Drawer`**; ui's is imported
   as `UiDrawer`, matching the existing `Card as UiCard` / `Pill as UiPill` pattern.
6. The `Companies` drawer now has **two** Escape listeners (the screen's and
   `Drawer`'s). Both call the same `closeDrawer`, which is idempotent, so the
   behaviour is unchanged — but if the crawl ever shows a double confirm, the fix
   is to drop the screen's branch, not the primitive's.
