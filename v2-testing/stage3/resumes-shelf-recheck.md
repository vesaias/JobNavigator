# Stage 3 — Résumés re-check against the canonical board (`Resumes Shelf`)

Re-checked: 2026-09-02, bundle `index-ClAeCNUL.js` (the earlier pass ran on `index-Dnrx3n0f.js`; the tree has been rebuilt since, so the RES-10/RES-12 source fixes are live), theme **light**, viewport 1440×900, read-only (no writes, no data created, no source modified).
Design: `v2-testing/design/Resumes Shelf.dc.html` — read in full, markup + the `text/x-dc` block.
Superseded design: `v2-testing/design/Resumes Home D.dc.html` (what `resumes.md` was measured against).
Script: `res2_1.py` (one run, harness `/tmp/v2t/h.py`; `rect` / `style` / `hover_delta` / `assert_int_tops` / `report`).
Fixtures: shelf `/v2/resumes`; editor base `22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a` ("PM", base, 300 copies); editor copy `d28bbd9e-6419-445e-8259-2ac0e002aa7e` ("PM → Meta — Product Manager", scored 77, +7, 14 changes) for the copy band.
Screenshots: `v2-testing/artifacts/resumes/res2-{shelf,editor,editor-copy}-light.png`.
Scope: **design fidelity only** — geometry, colours-as-tokens, hovers, labels, empty-state copy, section order. No behaviour was re-tested.
Console clean on all three passes: `0 console / 0 pageerror / 0 http≥400 / 0 requestfailed`.

Design→token map used (from the brief): `#e2ddd0`→`--line` · `#eeeae0`→`--line-soft` · `#8a826e`→`--edge` · `#f3f0e8`→`--surface-2` · `#faf8f3`→`--bg` · `#fdfcf9`→`--recessed` · `#3f6b52`→`--accent` · `#9c3b30`→`--bad` · `#c9c3b4`→`--line-strong`. Two more that recur in Shelf and resolve cleanly: `#f4f8f5`→`--hover-soft`, `rgba(63,107,82,.22)`→`--ring-accent`, `rgba(20,19,15,.42)`→`--scrim`, `#d6e8dc`→`--change-soft`, `#9a5b28`→`--warn`, `#f7ecea`→`--bad-soft`.

---

## 1 · Disposition of the existing RES-xx findings against `Resumes Shelf`

Only the P3/P4 design findings can change; the P1/P2 behavioural ones are listed for completeness with a one-line "not a design matter" where Shelf has nothing to say.

| # | Sev | Disposition vs Shelf |
|---|---|---|
| RES-01 autosave failure silent | P1 | **Unchanged** — behavioural. Shelf's top bar shows only a static "saved 2m ago · autosaves on blur" (line 143); it models no failure state either way. Already fixed + verified. |
| RES-02 skills reorder not persisted | P2 | **Unchanged** — backend. Fixed + verified. |
| RES-03 Import PDF creates two rows | P2 | **Unchanged** — behavioural. Fix is live in the current bundle (source `Resumes.jsx:253-268`). |
| RES-04 dotted skills category inert | P2 | **Unchanged** — behavioural. |
| RES-05 skills rename destroys a row | P2 | **Unchanged** — behavioural. |
| RES-06 CTA stuck on "Review N changes" | P2 | **Still holds, and Shelf strengthens it.** Shelf's `applyDiff` (line 1118) is `stage: Math.max(s.stage, 1)` — "Done reviewing" *advances a stored stage*; the design never recomputes "reviewed" from the diff. The build's `changes = computeChanges(baseData, data)` is therefore a deviation from the canonical machine, not just a bug. Confirmed live: the copy fixture shows CTA **"Review 14 changes"** with `title="The one next step"`. Better citation: `Resumes Shelf.dc.html:1118` + `STAGES` at :658-664. |
| RES-07 failed shelf load → "No base résumés yet" | P2 | **Still holds; no design counter-copy.** Shelf has **no empty state and no error state for the shelf at all** — the only "nothing" copy in the board is the search miss (line 79). The string `No base résumés yet. Create one to start.` is a code invention with no design source, so "match the design" is not an option here; the fix is the code's own. |
| RES-08 stale PDF preview on render failure | P2 | **Unchanged** — Shelf models no PDF error/loading state (lines 415-475 are a static paper). |
| RES-09 a base cannot be deleted | P2 | **Moot as a design gap — Shelf agrees with the code.** The base sub-band (lines 201-206) holds exactly two things: the copy-count sentence and "✦ Tailor for a job…" — no ⋯, no menu; and the shelf cards (line 107) have no per-card menu. The design deliberately gives bases no delete. Answer to the finding's own question ("is *bases are permanent* intentional?"): **yes, per the canonical board.** Keep as a product question, drop the design-deviation framing. |
| RES-10 half-pixel shelf rows | P3 | **Fixed and now verified live.** `assert_int_tops('.v2-card')` 0/5 fractional, `.v2-chip` 0/10, search rows **0/337**. Card header row h 29, card top 289, subtitle line-height 20px, badge line-height 16px — all integers. Close it. |
| RES-11 fractional rows inside the editor | P3 | **Unchanged** — left-pane internals, outside this re-check. Shelf gives no line-heights (its `text-wrap:pretty` blocks are static), so it cannot arbitrate the 1.5 bullet line-height either. |
| RES-12 template/paper dropdown had no hover | P3 | **Fix stands; the citation must move.** Shelf never opens the Template/Paper dropdowns — it draws only the *triggers* (lines 411-412, `style-hover="border-color:#3f6b52"`). The only `background:#f3f0e8` menu-row hover in Shelf is the ⋯ menu (lines 177, 185). So the fix is right by analogy with the ⋯ menu (measured working: `rgba(0,0,0,0)` → `rgb(246,244,238)` = `--surface-2`), but it is no longer supported by a design line for *these* rows. |
| RES-13 "+ N more ›" is a first-word search | P3 | **MOOT — the design does exactly this.** Shelf line 924: `searchMore: (e) => this.setState({ query: b.name.split(" ")[0].toLowerCase() })`, and Persona's is `query: "persona"` (line 915) — byte-for-byte what `Resumes.jsx:218`/`:181` do. Shelf's search also spans `ARCHIVED` (line 862), so pulling archived rows in is the designed behaviour too. Withdraw as a deviation; it survives only as a UX opinion. |
| RES-14 200-char base name overflows the card | P3 | **MOOT as a design deviation.** Shelf's card-name span (line 109) is `font-family/size/weight/letter-spacing` only — no `min-width:0`, no `overflow`, no ellipsis, exactly like the build. The design does not truncate a base name either. Keep it as a robustness P4 if you want it fixed, but "match the design" would change nothing. |
| RES-15 Escape closes no modal | P3 | **Unchanged** — Shelf has no keyboard logic. |
| RES-16 destructive edits: no confirm/undo | P3 | **Unchanged** — Shelf models no confirm. |
| RES-17 disabled primary buttons filled with `--edge` | P3 | **Still holds, unchanged.** Shelf line 705-706 is the same as Home D: `tailorGoBg:"#e2ddd0"` (`--line`), `tailorGoFg:"#6d6862"` (`--muted`). Re-measured live in the Add modal: disabled "Create from scratch" = `rgb(138,130,110)` (`--edge`) on `rgb(255,255,255)` (`--accent-ink`). |
| RES-18 shared `busy` shows on the wrong button | P3 | **Unchanged** — behavioural. |
| RES-19 archived + "+N more" render unvirtualised | P3 | **Unchanged, re-confirmed.** Query `a` rendered **337** rows in one list. Shelf's own lists are 3 rows of mock data, so the board neither supports nor forbids paging. |
| RES-20 job-less copy CTA can only fail | P3 | **Unchanged** — Shelf's `STAGES` has no job-less branch. |
| RES-21 missing/malformed id redirects silently | P3 | **Unchanged**; backend half fixed + verified. |
| RES-22 grouped design deviations | P3 | **Split — see below.** |
| RES-23 `.v2-navlink:hover` colour never fires | P4 | **No longer reproduces.** `theme.css:134` now carries `!important` on both properties, and the live measurement on "‹ Résumés" is `color rgb(63,107,82) → rgb(27,26,22)` **and** `background rgba(0,0,0,0) → rgb(246,244,238)`, i.e. `changed: ['color','backgroundColor']`. Close it. (It is replaced by the opposite problem — see **RES2-10**: the design gives "‹ Résumés" *no* hover at all.) |
| RES-24 one localStorage key for all section state | P4 | **Unchanged** — Shelf keeps `openSections` in component state. |
| RES-25 action-bearing success toast 2.5 s | P4 | **Unchanged** — toasts are not in this board. |
| RES-26 freeform tailor never reports completion | P4 | **Unchanged.** |
| RES-27 `?job=` inert | P4 | **Unchanged.** |
| RES-28 dead code / always-false branches | P4 | **Unchanged.** |
| RES-29 archived empty branch + sort comment | P4 | **Unchanged**; Shelf's archived affordance is a search seed (`query:"→"`, line 902), so it has no empty branch to copy. |
| RES-30 score poll resolves on a stale number | P4 | **Unchanged.** |
| RES-31 "autosaves on blur" is wrong | P4 | **Still holds, but the design carries the same wrong string.** Shelf line 143 literally reads `saved 2m ago · autosaves on blur`. The build is *more* accurate than the design after the first save (`saved {ago} · autosaves`) and repeats the design's error only in the pre-first-save state. "Match the design" would make it worse; fix the copy in both. |

### RES-22 re-scored bullet by bullet

| RES-22 bullet | Verdict vs Shelf |
|---|---|
| "the design is a two-pane browser (312 px source column + copies table)" | **WITHDRAWN.** That was `Resumes Home D`. `Resumes Shelf` *is* the source-card home the build implements: Profile label → Persona card → Résumés label → base cards (name · meta · avg fit / "Recent copies" chips / "+ N more ›") → dashed archived band. **Section order and structure match exactly.** |
| Review modal 920×760 vs 620×580 | **Holds unchanged** — Shelf line 484 `width:620px;max-height:580px`. |
| ⋯ menu 244 vs 248 px; hints "adds a copy" / split light+full vs "replaces copy" / "quick / full" | **Holds unchanged** — Shelf lines 174, 983-985 are identical to Home D. Re-measured: menu width **244**, rows `Re-tailor… / adds a copy`, `Score again · light / score only`, `Score again · full / with report`, `Review changes / 14 applied`. Menu border is `--edge` vs the design's `#e2ddd0` (`--line`) — small extra, folded in here. |
| Tailored badge green vs the design's plum | **Holds unchanged** — Shelf `badgeBg:"#f3e7ef"`, `badgeFg:"#7c4066"` at lines 937-938 and in the search rows at line 843. Measured: `rgb(234,241,235)` / `rgb(63,107,82)` = `--accent-soft` / `--accent`. Deliberate cross-screen change. |
| ▲▼ and ✕ hovers colour-only in the design | **Holds unchanged** — Shelf lines 230, 234, 294, 316, 325. |
| Card hover: accent border + `--hover-soft` vs "the design's beige" | **CHANGES — see RES2-04.** Shelf's card hover is `cardBg:"#f4f8f5"` / `cardBd:"#8a826e"` (lines 746-748). `#f4f8f5` **is** `--hover-soft` — the build's background lift matches the canonical design *exactly*. Only the border deviates (`--accent` vs `--edge`). The `#d4cec0` beige the `theme.css:140-142` comment cites as the design value appears nowhere in `Resumes Shelf`. |
| Header h1 30 px / 24 px gutter vs 28 / 30 | **Holds unchanged** — Shelf line 56-58: `padding:22px 30px 14px`, h1 `font-size:28px`. Shell convention. |

---

## 2 · Design vs measured

Verdicts: **match** · **deviates** · **DCC** = deliberate-consistency-candidate (a known cross-screen unification; `needs decision`).

### 2.1 Shelf — header band

| Item | `Resumes Shelf` | Measured | Verdict |
|---|---|---|---|
| header padding | `22px 30px 14px` (:56) | `22px 30px 16px 24px` | deviates (left gutter, bottom) — DCC, shell convention |
| header border-bottom | none (:56) | `1px solid --line` | deviates → **RES2-01** |
| header gap | 16 (:56) | 18 | deviates (minor) |
| h1 | Newsreader 28 / 400 / `-.02em` / lh 1 (:58) | Newsreader **30** / 400 / `-0.6px` / lh 30px | deviates — DCC (all nine screens) |
| h1↔subtitle gap | 3 (:57) | 3 | match |
| subtitle | 12.5px `#6d6862` (:59) | 13px `rgb(109,104,98)` = `--muted`, lh 20px | deviates (size) |
| subtitle copy | `3 bases · 17 tailored copies live under their jobs · 14 archived` (:59) | `4 bases · 49 tailored copies live under their jobs · 296 archived` | **match** (shape, pluralisation, archived clause) |
| search input | h36 · w300 · `padding:0 13px` · border-bottom 1px `#e2ddd0` · 13px (:62) | h36 · w300 · **padding 0 2px** · border-bottom 1px `--line` · 13px | deviates (padding) → **RES2-02** |
| search placeholder | `Search bases, copies, archived… (try “plaid”)` (:62) | `Search bases, copies, archived…` | deviates (example dropped) |
| `+ New résumé` | h36 · `0 18px` · r99 · `#3f6b52`/`#fff` · 13.5/500 (:63) | h36 · `0 17px` · r99 · `--accent`/`--accent-ink` · 13/500 | deviates (1 px pad, .5 px type) |
| right group gap | 9 (:61) | 10 | deviates (minor) |
| header hovers | none on input or `+ New résumé` | `changed: []` on both | **match** |

### 2.2 Shelf — browse body

| Item | `Resumes Shelf` | Measured | Verdict |
|---|---|---|---|
| scroll padding / gap | `6px 30px 26px` / gap 12 (:85) | `6px 30px 26px 24px` / gap 12 | deviates (left gutter only) |
| group labels | 10px · `.15em` · `#6d6862` · `4px 2px 0` — **"Profile"**, **"Résumés"** (:86,:105) | 10px · 1.5px · `--muted` · `4px 2px 0` — "Profile", "Résumés" | **match** |
| card | border 1px `#e2ddd0` · r11 · `#fff` · `16px 20px` · gap 11 (:87,:107) | 1px `--line` · r11 · `--surface` · `16px 20px` · gap 11 | **match** |
| card header row | `align-items:baseline`, gap 12 (:88) | baseline, gap 12, lh 28px, h 29 | **match** (lh added by the RES-10 fix) |
| base name | Newsreader 19/500/`-.015em` (:109) | Newsreader 19/500/`-0.285px` | **match** |
| card meta | 11.5px `#6d6862` (:110) | 11.5px `--muted` | **match** |
| avg fit | Newsreader 17px + inner Public Sans 10px `#6d6862`, `margin-left:auto` (:111) | Newsreader 17 / inner Public Sans 10 `--muted`, ml auto | **match** |
| avg colour rule | `avg>=75 ? #3f6b52 : #57534a` (:922) | `scoreColor()` — measured 71 → `rgb(63,107,82)` (accent) | deviates (threshold) |
| base card `title` | `Open <name> — the base résumé` (:107,:920) | **null** | deviates → **RES2-03** |
| Persona card `title` | `Open Persona — your full profile` (:87) | identical | **match** |
| avg-fit `title` | `Average fit across this base's scored copies` (:111) | + ` (archived included)` | match (superset) |
| "Recent copies" label | 10px · `.13em` · uppercase · `#6d6862` · `margin-right:3px` (:94,:114) | **absent** — the build starts the chip row with the chips | deviates → **RES2-03** |
| chip | h26 · `0 10px` · r99 · 1px `#e2ddd0` · bg `#faf8f3` · fg `#57534a` · 11.5px · gap 6 · maxW 250 (:96,:116) | h26 · `0 10px` · r99 · 1px `--line` · `--bg` (`#fcfbf7`) · `--text-2` · 11.5 · gap 6 · maxW 250 | **match** (bg differs only by the global `--bg` token drift) |
| chip score | JetBrains Mono 10px `#3f6b52` (:98,:119) | JetBrains Mono 10px — but `scoreColor()`: 77→accent, 68→`--warn`, 38→`--bad` | deviates (design is always accent) |
| chip fresh dot | 6×6 r99 `#9a5b28` (:99,:120) | 6×6 r99 `rgb(154,91,40)` = `--warn` | **match** |
| chip spinner | 9×9 border 1.5px `#3f6b52`, `jnspin 900ms` (:117) | 9×9 1.5px `--accent`, `.v2-spin` | **match** |
| chip `title` | `<base> · <job> · fit N (+d vs X avg) · N changes unreviewed` (:775-778) | the bare résumé name (`Persona → Decagon — Senior Agent Product Manager`) | deviates → **RES2-03** |
| chip cap | design shows 3-4 + "+N more"; build caps at 6 | 6 | n/a (design has no stated cap) |
| `+ N more ›` | 11.5px `#3f6b52`, no hover (:102,:123) | 11.5px `--accent`, class `(none)` → no hover | **match** |
| archived band | `10px 14px` · gap 8 · 1px dashed `#e2ddd0` · r9 (:127) | `10px 14px` · gap 8 · 1px dashed `--line` · r9 · h40 | **match** |
| archived copy | `Archived · 14 copies from rejected or stale applications` + `browse ›` 11.5px `#3f6b52` (:128-129) | `Archived · 296 copies from rejected or stale applications` + `browse ›` 11.5px `--accent` | **match** |
| card tops | — | `.v2-card` 5, **0 fractional**; `.v2-chip` 10, **0 fractional** | **match** (RES-10 closed) |

### 2.3 Shelf — search state

| Item | `Resumes Shelf` | Measured | Verdict |
|---|---|---|---|
| scroll gap (searching) | 4 (:68) | 4 | **match** |
| result line | `N matches — bases, copies, and archived`, 11px · `.13em` · uppercase · `#6d6862` · `padding:4px 2px` (:69,:901) | `337 matches — bases, copies, and archived`, 11px · 1.43px · uppercase · `--muted`; wrapped in a 10px-gap row with padding `4px 2px` | deviates (extra wrapper + `‹ Back`) → **RES2-07** |
| `‹ Back` control | **not in the design** (clearing the field is the exit) | present, 12px `--accent`, `.v2-navlink` | deviates (extra control + extra hover) → **RES2-07** |
| result row | gap 11 · `10px 14px` · 1px `#e2ddd0` · r9 · `#fff` (:71) | gap 11 · `10px 14px` · 1px `--line` · r9 · `--surface` · h42 · lh 20px | **match** |
| row badge | 9.5px · `.08em` · uppercase · `2px 7px` · r99 (:72) | 9.5px · 0.76px · `2px 7px` · r99 · lh 16px | **match** (colours: see RES-22 plum) |
| row name / note / score | 13/500 ellipsis · 11px `#6d6862` · mono 11px `#3f6b52` (:73-75) | 13/500 ellipsis · 11px `--muted` · mono 11px `scoreColor()` | match / match / deviates (score colour) |
| no-results | `20px 14px` · 1px dashed `#e2ddd0` · r9 · 12.5px `#6d6862`, copy `Nothing matches “{q}” — search covers base names, company names, and job titles.` (:79) | identical padding/border/radius/size/colour, **identical string** | **match** |
| row tops | — | 337 rows, **0 fractional** | **match** |

### 2.4 Shelf — Add modal

| Item | `Resumes Shelf` (:552-563) | Measured | Verdict |
|---|---|---|---|
| scrim | `rgba(20,19,15,.42)` | `rgba(20,19,15,0.42)` = `--scrim` | **match** |
| panel | **w400** · 1px `#e2ddd0` · r12 · `0 18px 50px rgba(0,0,0,.28)` · `padding:18px 22px` · gap 11 | **w420** · 1px `--line` · r12 · same shadow · `padding:22px` | deviates → **RES2-08** |
| title | Newsreader 18px `-.02em` — **"Add résumé"** | Newsreader **19px** — **"New base résumé"** | deviates |
| sub-line | **none** | `Start from scratch, or import an existing PDF to parse.` 12px | deviates (extra) |
| name input | h33 · `0 10px` · 1px `#8a826e` · r8 · **no fill** · 12.5px · placeholder `e.g. Backend — Platform v5` | h38 · `0 12px` · 1px `--edge` · r8 · **`--surface-2` fill** · 13px · placeholder `Résumé name (e.g. Backend — Platform v4)` | deviates |
| buttons | 2-col grid gap 8, both h36, 12.5px — `+ From scratch` (accent fill) and `↑ Import PDF` (1px `#8a826e`, `#57534a`) | flex gap 9, both h40, 13px — `Create from scratch` (disabled fill `--edge`, see RES-17) and `Import PDF ↑` | deviates (labels, icon side, height) |
| Cancel | **none in the design** | extra centred `Cancel` row, 12px `--muted` | deviates (extra) |
| Import PDF hover | `border-color:#3f6b52; color:#3f6b52` (:559) | class `.v2-act` → border `--accent` **+ background `--hover-soft`**, colour unchanged | deviates → **RES2-06** |

### 2.5 Editor — top bar (both fixtures)

| Item | `Resumes Shelf` (:138-144) | Measured | Verdict |
|---|---|---|---|
| bar | `padding:10px 24px` · `#fff` · border-bottom 1px `#eeeae0` · gap 12 · align center | `10px 24px` · `--surface` · 1px `--line-soft` · gap 12 · center · h42 | **match** |
| `‹ Résumés` | 13px `#3f6b52` 500, **no `style-hover`** | 13px `--accent` 500, `.v2-navlink` → hover `color→--text` + `background→--surface-2` | deviates (extra hover) → **RES2-10** |
| separator | `\|` `#e2ddd0` | `\|` `--line` | **match** |
| badge | 9.5px `.08em` uppercase `2px 7px` r99; base `#f3f0e8`/`#6d6862`, copy `#f3e7ef`/`#7c4066` | 9.5px 0.76px uppercase `2px 7px` r99; base `--surface-2`/`--muted` ✓, copy `--accent-soft`/`--accent` ✗ | geometry match; copy colours = RES-22 plum (DCC) |
| name | 14/600 ellipsis, **`max-width:420px`** | 14/600 ellipsis, `max-width:460px`, `title` = full name | deviates → **RES2-09** |
| status | 11.5px `#6d6862`, `saved 2m ago · autosaves on blur` | 11.5px `--muted`, `saved 4d ago · autosaves` / `saved 20h ago · autosaves` | match geometry; copy = RES-31 |

### 2.6 Editor — base sub-band

| Item | `Resumes Shelf` (:201-206) | Measured | Verdict |
|---|---|---|---|
| band | `#f3f0e8` · border-bottom 1px `#e2ddd0` · `9px 24px` · gap 13 | `--surface-2` · 1px `--line` · `9px 24px` · gap 13 · h55 | **match** |
| sentence | 12.5px `#57534a`, `Base résumé · <N> tailored copies · editing here changes future tailoring only`, count in `#1b1a16`/500 | identical string and tokens (`Base résumé · 300 tailored copies · editing here changes future tailoring only`) | **match** |
| Tailor button | `margin-left:auto` · h36 · `0 19px` · r99 · `#3f6b52`/`#fff` · gap 7 · 13/500 · `✦ Tailor for a job…` | ml auto · h36 · `0 19px` · r99 · `--accent`/`--accent-ink` · 13/500 · same label | **match** |

### 2.7 Editor — copy sub-band

| Item | `Resumes Shelf` (:146-198) | Measured | Verdict |
|---|---|---|---|
| band | `#f3f0e8` · 1px `#e2ddd0` · `9px 24px` · gap 13 | `--surface-2` · 1px `--line` · `9px 24px` · gap 13 · h55 | **match** |
| score ring | 34×34, `viewBox 0 0 78 78`, r35, stroke-width 6, track `#e2ddd0`, dasharray `X 219.9`, rotate −90 | 34×34, same viewBox/r/width/dasharray; rotate on the circle not the svg (equivalent); track `--track` (`#8d8571`) | deviates (track token: design `--line`, code `--track`) |
| ring number | Newsreader 13.5px, tier colour | Newsreader 13.5px, `scoreColor()` | **match** |
| line 1 | 12.5/500 `#57534a`, `Tailored for <job>` with the job in `#1b1a16` | 12.5/500 `--text-2`, lh 17.5px, `Tailored for Meta — Product Manager` with `--text` | **match** |
| lineage divider | a **1px × 11px block**, `background:#8a826e`, self-centred (:158) | the literal text `"  │  "` coloured `--line`, w 13.5 × h 15 | deviates → **RES2-10** |
| delta + base link | `+7 vs` (`deltaFg`, 600) then the base name underlined-on-hover, then `↗` 10px | `+7 ` (`--accent`, 600) then `based on PM ↗` (`--accent`), the whole thing a `.v2-navlink` | deviates (wording, and the underline hover is gone) → **RES2-10** |
| line 2 | 11px `#6d6862`, `<stageNote> · tracers: LinkedIn 3 · Portfolio 1 · Email 0` | 11px `--muted`, lh 16.5px, `14 reviewable changes · tracers: LinkedIn 0 · viktoresadze.com 0` | **match** (shape) |
| CTA | h36 · `0 19px` · r99 · gap 8 · 13/500; active `#3f6b52`/`#fff`, terminal `#eaf1eb`/`#3f6b52` | h36 · `0 19px` · r99 · gap 8 · 13/500 · `--accent`/`--accent-ink`; `title="The one next step"` | **match** |
| ⋯ trigger | 36×36 · r99 · 1px `#8a826e` · **`background:#fff`** · 15px `#57534a` | 36×36 · r99 · 1px `--edge` · **transparent** · 15px `--text-2` | deviates → **RES2-11** |
| menu shell | w**248** · `#fff` · 1px `#e2ddd0` · r10 · `0 12px 32px rgba(0,0,0,.16)` · padding 5 · `top:100%; margin-top:5` | w**244** · `--surface` · 1px **`--edge`** · r10 · same shadow · padding 5 · same offset | deviates (width = RES-22; border token new, folded into RES-22) |
| menu heads | `4px 11px 3px` · 9.5px · `.13em` · uppercase · `#6d6862`; **"This copy"** and **"<Company> job"** | identical box; **"This copy"** ✓ and **"Job"** ✗ | deviates (second head is generic) |
| menu items | gap 9 · `7px 11px` · r6 · 13px `#57534a`; icon col 16px 11px `#6d6862`; hint 10.5px `#6d6862` | gap 9 · `7px 11px` · r6 · 13px `--text-2` | **match** |
| menu item hover | `background:#f3f0e8` (:177,:185) | `rgba(0,0,0,0)` → `rgb(246,244,238)` = `--surface-2` | **match** |
| Delete row | 13px `#9c3b30`, `✕`, `Delete copy`, top-border, hover `background:#f7ecea` | 13px `--bad`, same label, hover → `rgb(247,236,234)` = `--bad-soft` | **match** |

### 2.8 Editor — panes and PDF header (context for the band; not a full pane re-check)

| Item | `Resumes Shelf` | Measured | Verdict |
|---|---|---|---|
| left pane | `flex:0 0 47%`, border-right 1px `#e2ddd0`, `padding:14px 20px 24px`, gap 10 (:209-210) | `flex-basis 47%` (580 px), 1px `--line`, `14px 20px 24px`, gap 10 | **match** |
| right pane | `#f3f0e8` (:408) | `--surface-2` | **match** |
| PDF header | `padding:8px 20px`, gap 9, border-bottom 1px `#e2ddd0` (:409) | `8px 20px`, **gap 12**, 1px `--line` | deviates (gap) |
| `PDF preview` label | 10px `.14em` uppercase `#6d6862` (:410) | 10px `--muted` | **match** |
| Template / Paper pills | h24 · `0 8px` · 1px `#8a826e` · r6 · gap 6 · 11.5px; hover `border-color:#3f6b52` (:411-412) | h24 · `0 8px` · 1px `--edge` · r6 · gap 6 · 11.5px (source `ResumeEditor.jsx:420,432`); class `.v2-act` → border `--accent` **+ background `--hover-soft`** | geometry **match**; hover deviates → **RES2-06** |
| Download | h29 · `0 15px` · r99 · `#3f6b52`/`#fff` · gap 6 · 12/500 · `↓ Download PDF` (:413) | h29 · `0 15px` · r99 · `--accent`/`--accent-ink` · 12 · same label | **match** |
| section card | 1px `#e2ddd0` · r9 · `#fff`; header `10px 14px` gap 9; chev 10px `#6d6862`; title 13/600; count 11.5px `#6d6862`; changed 10px `#9a5b28`; body `2px 14px 14px` border-top 1px `#eeeae0` (:211-218) | 1px `--line` · r9 · `--surface`; header `10px 14px` gap 9; chev 10px `--muted`; title 13/600; count 11.5 `--muted`; changed 10px `--warn`; body **`4px 14px 14px`** border-top 1px `--line-soft` | **match** except body top padding (4 vs 2) |
| section header hover | `background:#faf8f3` (= `--bg`) (:212 and every section) | `.v2-hover-accent` → `background:--surface-2` **+ `color:--text`** | deviates → **RES2-12** |
| section order | header · summary · experience · skills · education · projects · publications (:622) | identical (`SECTION_ORDER`) | **match** |
| empty-section copy | `No publications yet` / `Empty sections are skipped in the PDF — nothing prints until you add one.` (:399-400) | verified in the earlier pass ("five `EmptyState`s with the PDF wording") | **match** |

### 2.9 Every `style-hover` in `Resumes Shelf` (shelf + editor band scope)

| Design line | `style-hover` | Built element | Measured | Verdict |
|---|---|---|---|---|
| :71 search result row | `border-color:#3f6b52` | `.v2-act` | border → `--accent` **+ bg → `--hover-soft`** | deviates (extra bg) — RES2-06 |
| :127 archived band | `border-color:#3f6b52` | `.v2-act` | border → `--accent` **+ bg → `--hover-soft`** | deviates (extra bg) — RES2-06 |
| :559 Import PDF | `border-color:#3f6b52; color:#3f6b52` | `.v2-act` | border → `--accent` + bg → `--hover-soft`, **colour unchanged** | deviates — RES2-06 |
| :411/:412 Template · Paper pills | `border-color:#3f6b52` | `.v2-act` | same as above | deviates — RES2-06 |
| :177/:185 ⋯ menu rows | `background:#f3f0e8` | `.v2-menuitem` | → `--surface-2` | **match** |
| :191 Delete copy | `background:#f7ecea` | `.v2-hover-bad` | → `--bad-soft` | **match** |
| :160 delta label | `color:#1b1a16` | inside `.v2-navlink` | colour → `--text` ✓ **+ background → `--surface-2`** | deviates (extra bg) — RES2-10 |
| :161 base name | `text-decoration-color:#3f6b52` | inline `--accent` span in the same `.v2-navlink` | **no `text-decoration` anywhere** in the build | deviates (missing) — RES2-10 |
| :212/:242/:260/:270/:306/:333/:358/:390 section + entry headers | `background:#faf8f3` | `.v2-hover-accent` | → `--surface-2` **+ colour → `--text`** | deviates — RES2-12 |
| :230/:316 ▲▼ | `color:#3f6b52` | `.v2-navlink` | colour + background | deviates — RES-22 (unchanged) |
| :234/:294/:325/:379 ✕ | `color:#9c3b30` | `.v2-hover-bad` | background `--bad-soft`, colour unchanged | deviates — RES-22 (unchanged) |
| :237/:297/:301/:328/:353/:385/:402 dashed "+ Add …" | `border-color:#3f6b52; background:#f4f8f5` | `.v2-dashadd` | border `--accent` ✓ + bg `--hover-soft` (= `#f4f8f5`) ✓ + colour → `--accent` | **match** (+ a harmless colour change) |
| :490 review-modal ✕, :524 tailor job row | — | out of this re-check's scope | — | not measured |
| **card hover** (JS `cardHover`, :746-748) | bg `#f4f8f5`, bd `#8a826e` | `.v2-card` | bg `rgb(244,248,245)` = `#f4f8f5` ✓, bd `--accent` ✗ | bg **match**, border deviates — RES2-04 |
| **chip hover** (JS `copyChip`, :767-770) | bd `#3f6b52`, bg `#fff`, fg `#26543c`, ring `0 0 0 2px rgba(63,107,82,.22)` | `.v2-chip` | bd `rgb(63,107,82)` ✓, bg `rgb(255,255,255)` ✓, ring `rgba(63,107,82,0.22) 0 0 0 2px` ✓, fg `rgb(63,107,82)` ✗ (design `#26543c`) | 3/4 **match**, fg deviates — RES2-05 |
| **hovers present in the design with no built equivalent** | — | — | none found | — |
| **hovers in the build not in the design** | — | `‹ Résumés` back-link, `‹ Back` search link | both `.v2-navlink` (bg + colour) | deviates (P4 by §4's "extra hovers are defects too") — RES2-07, RES2-10 |

---

## 3 · New findings

### RES2-01 · P3 · The shelf header carries a border the canonical board does not
**Where** `frontend/src/v2/Resumes.jsx:110`, route `/v2/resumes`
**Repro** open `/v2/resumes`, measure the header wrapper.
**Expected + why** `Resumes Shelf.dc.html:56` — `padding:22px 30px 14px;display:flex;align-items:flex-end;gap:16px` and **no border**. The board lets the browse list flow straight out of the header; the only rules on the shelf are the card borders and the dashed archived band.
**Actual** measured `padding: 22px 30px 16px 24px`, `gap: 18px`, `border-bottom: 1px solid rgb(226,221,208)` (`--line`). Header wrapper 1234 × 92.
**Proposed fix** drop `borderBottom`; set `paddingBottom: 14`, `gap: 16`.
**Status** needs decision: keep code (consistency — every other v2 screen header has this rule) or match design?

### RES2-02 · P3 · The search field is inset 2 px, not 13, so its text starts hard against the underline's left edge
**Where** `Resumes.jsx:117-118`
**Expected + why** `Resumes Shelf.dc.html:62` — `height:36px;width:300px;padding:0 13px`. The 13 px inset is what lines the placeholder up with the `+ New résumé` pill's own 18 px inset and keeps the caret off the rule's corner. The board's placeholder also carries an example: `Search bases, copies, archived… (try “plaid”)`.
**Actual** measured `paddingLeft: 2px`, `paddingRight: 2px` (h36 ✓, w300 ✓, fontSize 13 ✓, border-bottom 1px `--line` ✓). Placeholder `Search bases, copies, archived…`.
**Proposed fix** `padding: '0 13px'`; optionally restore the example in the placeholder.
**Status** needs decision: keep code (consistency — the other v2 underline search fields are flush) or match design?

### RES2-03 · P3 · The shelf drops three of the board's affordance labels/tooltips
**Where** `Resumes.jsx:193` (base card, no `title`), `:202`/`:216` (chip `title`), and the missing "Recent copies" label on both card types
**Expected + why** `Resumes Shelf.dc.html`:
- `:107` + `:920` — every base card carries `title="Open <name> — the base résumé"`. The Persona card's equivalent (`:87`) *is* implemented, so the omission is asymmetric.
- `:94`/`:114` — the chip row opens with a `10px / .13em / uppercase / #6d6862 / margin-right:3px` label reading **"Recent copies"**. Without it the chips have no header and the meta line ("45 recent copies") is the only thing naming them.
- `:775-778` — the chip `title` is the board's deliberate overflow channel: `"<base> · <job> · fit N (+d vs <base> avg) · N changes unreviewed"`, with the comment "the delta it carried survives in the tooltip, which is the one place the chip can say more without occupying space".
**Actual** measured: base card `title` = `null`; no "Recent copies" span exists anywhere in the shelf DOM; chip `title` = `"Persona → Decagon — Senior Agent Product Manager"` (the bare name — no job, no fit, no delta, no unreviewed count).
**Proposed fix** add the base-card `title`; add the "Recent copies" label span to both chip rows; build the chip `title` from `name · job · fit N (±d vs <base> avg)` and append the fresh clause when `c.fresh`.
**Status** needs decision: keep code (consistency) or match design?

### RES2-04 · P3 · Card hover — the background matches the board exactly; only the border was changed, and `theme.css` justifies it against a colour the board doesn't contain
**Where** `frontend/src/v2/theme.css:140-143`
**Expected + why** `Resumes Shelf.dc.html:744-751` (`cardHover`): `cardBg: lit ? "#f4f8f5" : "#fff"`, `cardBd: lit ? "#8a826e" : "#e2ddd0"` — i.e. `--hover-soft` on `--edge`. The comment in `theme.css:140-142` reads *"Résumés' design hovers its cards to a soft beige (#d4cec0) while every other clickable card/row in v2 goes to the accent — and `--edge` was stronger than that beige anyway."* `#d4cec0` does not appear anywhere in `Resumes Shelf.dc.html`, and the canonical board's hover border **is** `--edge` — the exact token the comment says it was replacing something weaker than.
**Actual** measured on both the Persona and a base card: `border-color rgb(226,221,208) → rgb(63,107,82)` (`--line` → `--accent`), `background rgb(255,255,255) → rgb(244,248,245)`. `rgb(244,248,245)` is `#f4f8f5` — **the design's value byte for byte**.
**Proposed fix** none required for the background. For the border, either accept the accent as the cross-screen unification (then correct the comment: the canonical Résumés hover border is `--edge` = `#8a826e`, not a `#d4cec0` beige) or revert to `border-color: var(--edge)` on `.v2-card` for this screen only.
**Status** needs decision: keep code (consistency) or match design? — but the `theme.css:140-142` comment is factually wrong against the canonical board either way and should be corrected.

### RES2-05 · P4 · Chip hover text goes to `--good`; the board darkens it past the accent
**Where** `theme.css:145`
**Expected + why** `Resumes Shelf.dc.html:769` — `chipFg: hovered ? "#26543c" : "#57534a"`. `#26543c` is a deliberately darker green than `#3f6b52`; the board pairs it with a white fill so the label still carries weight against the brightened chip.
**Actual** measured `color rgb(87,83,74) → rgb(63,107,82)` (`--text-2` → `--good`/`--accent`). The other three properties are exact matches: `border-color → rgb(63,107,82)`, `background → rgb(255,255,255)`, `box-shadow → rgba(63,107,82,0.22) 0px 0px 0px 2px` (`--ring-accent`, the board's `0 0 0 2px rgba(63,107,82,.22)`).
**Proposed fix** none, or add a `--accent-deep` token if the extra contrast is wanted.
**Status** needs decision: keep code (no `#26543c` token exists) or match design?

### RES2-06 · P3 · Four border-only hovers in the board also lift their background, because they all share `.v2-act`
**Where** `theme.css:148` (`.v2-act:hover { border-color:--accent !important; background:--hover-soft !important; }`); callers `Resumes.jsx:127` (search row), `:143` (archived row), `:221` (archived band), `:277` (Import PDF), `ResumeEditor.jsx:420`/`:432` (Template / Paper pills)
**Expected + why** all four are `border-color:#3f6b52` **only** in `Resumes Shelf.dc.html` (`:71`, `:127`, `:411`, `:412`), and the Import PDF button is `border-color:#3f6b52; color:#3f6b52` (`:559`) — a border-and-text hover with no fill. The board draws a clear line: filled surfaces (cards) get a background lift, outlined rows and pills get a stroke.
**Actual** measured on the search result row and on the archived band: `border-color rgb(226,221,208) → rgb(63,107,82)` **and** `background → rgb(244,248,245)`. Import PDF and the two PDF pills carry the identical class, so the same rule applies (the modal's Import button could not be hovered in the same run — the first `.v2-act` on the page sits under the scrim; the class rule is deterministic and was measured three times elsewhere). On Import PDF the design's `color` change is additionally absent.
**Proposed fix** give the outlined rows/pills `.v2-bd` (`theme.css:153`, border-only — it already exists for exactly this case), and add `color: var(--accent)` on the Import PDF button.
**Status** needs decision: keep code (consistency — `.v2-act` is the shared row hover across v2) or match design?

### RES2-07 · P4 · The search and archived views add a `‹ Back` control and a wrapper row the board doesn't have
**Where** `Resumes.jsx:122-125` (search), `:137-141` (archived)
**Expected + why** `Resumes Shelf.dc.html:67-81` — the searching branch renders exactly one label (`{{ resultLine }}`, `padding:4px 2px`) followed by the rows. Clearing the input is the exit; the archived view *is* a search (`searchArchived: () => this.setState({ query: "→" })`, `:902`), so it has no separate header or back control either. §4 of the brief counts hovers not in the design as defects, and `‹ Back` is a `.v2-navlink` with a background+colour hover.
**Actual** measured: a `display:flex; gap:10px; padding:4px 2px` row containing `‹ Back` (12px, `--accent`, `.v2-navlink`) and then the result line; the archived view has the same row with `Archived · 296 from rejected or stale applications` as its label.
**Proposed fix** none if the back control is wanted (it is a genuine usability addition over a modal-less design); if matching, drop the row and let the empty field be the exit.
**Status** needs decision: keep code (usability addition) or match design?

### RES2-08 · P3 · The Add modal deviates from the board in width, height, type scale, both button labels, and two extra elements
**Where** `Resumes.jsx:270-283`
**Expected + why** `Resumes Shelf.dc.html:552-563`: `width:400px`, `padding:18px 22px`, `gap:11`, title Newsreader 18px reading **"Add résumé"**, one input `height:33px; padding:0 10px; border:1px solid #8a826e; border-radius:8px` with **no fill** and placeholder `e.g. Backend — Platform v5`, then a `grid-template-columns:1fr 1fr; gap:8` pair of h36 12.5px buttons labelled **"+ From scratch"** and **"↑ Import PDF"**. There is no sub-line and no Cancel row — the scrim is the cancel.
**Actual** measured: panel **420 × 234.5**, `padding: 22px`; title `New base résumé` at **19px**; an extra 12px sub-line `Start from scratch, or import an existing PDF to parse.`; input **h38**, `padding 0 12px`, filled `--surface-2`, 13px, placeholder `Résumé name (e.g. Backend — Platform v4)`; buttons **h40**, gap 9, `Create from scratch` / `Import PDF ↑` (icon on the trailing side); an extra centred `Cancel` row. Scrim `rgba(20,19,15,0.42)` ✓, radius 12 ✓, border 1px `--line` ✓, shadow `0 18px 50px rgba(0,0,0,.28)` ✓.
**Proposed fix** if matching: 400 px, `18px 22px`, 18px title "Add résumé", input h33/`0 10px`/transparent/12.5px, two h36 buttons `+ From scratch` / `↑ Import PDF` in a 1fr 1fr grid gap 8, drop the sub-line and Cancel.
**Status** needs decision: keep code (the sub-line and Cancel are real affordances the board omits) or match design?

### RES2-09 · P4 · Editor top-bar name clamps at 460 px, the board at 420
**Where** `ResumeEditor.jsx:325`
**Expected + why** `Resumes Shelf.dc.html:142` — `max-width:420px`. At 420 the ellipsised name leaves the status string room at 1440 without the two ever meeting; 460 narrows that margin by 40 px.
**Actual** measured `max-width: 460px` on both fixtures (rendered widths 22 px and 207.7 px, so it does not currently clamp — the deviation is latent).
**Proposed fix** `maxWidth: 420`.
**Status** needs decision: keep code (consistency with the other v2 title clamps) or match design?

### RES2-10 · P3 · The copy band's lineage cluster: a text divider instead of a rule, a `.v2-navlink` instead of an underline, and a hover on the back-link the board doesn't have
**Where** `ResumeEditor.jsx:315` (back-link), `:345` (divider), `:346-351` (base link)
**Expected + why** `Resumes Shelf.dc.html`:
- `:158` — the divider between "Tailored for …" and the lineage is a **block**: `width:1px; height:11px; background:#8a826e; align-self:center`. A vertical rule at `--edge`, not a glyph.
- `:160-161` — the delta hovers `color:#1b1a16` and the base name hovers `text-decoration-color:#3f6b52` over a permanently-underlined-but-transparent run (`text-decoration-line:underline; text-underline-offset:2px; text-decoration-color:transparent`). Two separate, text-only hovers.
- `:139` — `‹ Résumés` has **no `style-hover` at all**.
**Actual** measured: the divider is the literal string `"  │  "` coloured `rgb(226,221,208)` (`--line`, one step lighter than the design's `--edge`), 13.53 × 15 px — a glyph whose weight and baseline are font-dependent. The delta + base name are wrapped in one `.v2-navlink`, so hovering changes `color` **and** `background` for the whole cluster and no underline appears anywhere. The back-link measured `color rgb(63,107,82) → rgb(27,26,22)` + `background rgba(0,0,0,0) → rgb(246,244,238)` — an extra hover by §4.
**Proposed fix** replace the glyph with `<span style={{width:1,height:11,background:'var(--edge)',alignSelf:'center'}} />`; split the link into the two design hovers (`.v2-hover-accent-text` on the delta; a transparent-underline span that gains `text-decoration-color` on hover); leave the back-link's hover if the shell convention keeps it.
**Status** needs decision: keep code (consistency) or match design?

### RES2-11 · P4 · The ⋯ trigger is transparent, so the band tint shows through where the board paints it white
**Where** `ResumeEditor.jsx:369`
**Expected + why** `Resumes Shelf.dc.html:172` — `background: {{ menuBg }}` where `menuBg = S.menuOpen ? "#eaf1eb" : "#fff"`. Against the `#f3f0e8` sub-band the closed state is a white disc; the open state is `--accent-soft`. The build has the open state right and the closed state transparent.
**Actual** measured closed: `background rgba(0, 0, 0, 0)` (so the button reads as the `--surface-2` band), `border 1px rgb(138,130,110)` (`--edge`) ✓, 36 × 36 ✓, radius 99 ✓, font-size 15 ✓, colour `--text-2` ✓.
**Proposed fix** `background: headMenu ? 'var(--accent-soft)' : 'var(--surface)'`.
**Status** needs decision: keep code (consistency — v2's icon buttons are transparent by default) or match design?

### RES2-12 · P4 · Section-header hover uses `--surface-2` and also changes the text colour; the board uses `--bg` and nothing else
**Where** `ResumeSections.jsx:126` (`className="v2-hover-accent"`), rule at `theme.css:129`
**Expected + why** `Resumes Shelf.dc.html:212, 242, 260, 270, 306, 333, 358, 390` — every section header and every experience-entry header is `style-hover="background:#faf8f3"`. Per the brief's map `#faf8f3` → `--bg`; the board's card is `#fff`, so the hover is a *recede* toward the page ground. `.v2-hover-accent` instead lifts to `--surface-2` (`#f6f4ee`, a darker step) and forces `color: var(--text) !important`, which the design never asks for.
**Actual** measured header class `v2-hover-accent`; rule `background:var(--surface-2) !important; color:var(--text) !important`. Also measured: section body padding `4px 14px 14px` vs the design's `2px 14px 14px` (`:218`), and the PDF-preview header gap 12 vs the design's 9 (`:409`).
**Proposed fix** `background: var(--bg)` and drop the colour override for these headers (or introduce a `.v2-hover-recede`); `paddingTop: 2` on the section body; `gap: 9` on the PDF header.
**Status** needs decision: keep code (consistency — `.v2-hover-accent` is shared) or match design?

---

## 4 · Summary

**Canonical-board effect on the old list (31 findings):** 3 become **moot** (RES-13, RES-14, and RES-22's headline "wrong home" bullet), 1 is **answered by the design** (RES-09 — bases are deliberately undeletable), 1 **no longer reproduces** (RES-23 — `theme.css:134` now has `!important` and the hover measures `color`+`background`), 1 is **closed by the rebuild** (RES-10 — 0 fractional tops across 5 cards, 10 chips and 337 search rows), 1 is **strengthened** (RES-06 — Shelf's `applyDiff` stores the stage rather than recomputing it), 1 has its **citation moved** (RES-12), 1 gains a **new twist** (RES-31 — the board carries the same wrong "autosaves on blur" string). The remaining 22 stand unchanged; every one of RES-22's other six bullets survives against Shelf too.

**What the canonical board vindicates:** the shelf's whole structure — section order, card anatomy, chip anatomy, the dashed archived band, the search result row, the no-results copy (string-identical), the base sub-band sentence (string-identical), the copy band's ring/CTA/menu grammar, the left/right 47 % split, the section-card box, and the ⋯ menu's two `style-hover`s (`--surface-2` and `--bad-soft` land on the design's `#f3f0e8`/`#f7ecea` exactly). The card hover's background lift (`--hover-soft` = `#f4f8f5`) and three of the chip hover's four properties are byte-for-byte matches.

**New findings: 12** — P3 **7** (RES2-01, 02, 03, 04, 06, 08, 10) · P4 **5** (RES2-05, 07, 09, 11, 12). All twelve are `needs decision`; none is unambiguous enough to fix under the brief's "< 50 lines, one obviously correct answer" rule, and two (RES2-04's border, RES2-06's `.v2-act`) are explicitly cross-screen unifications already documented in `theme.css`.

**One correction worth carrying regardless of the decisions:** `theme.css:140-142` justifies the card-hover change against "the design's soft beige (`#d4cec0`)". That colour is not in `Resumes Shelf.dc.html`; the canonical hover is `#f4f8f5` on a `#8a826e` (`--edge`) border — i.e. the code already matches the design's fill, and the border it replaced was `--edge` itself, not something weaker.

**Scratch data: none created, none deleted. No source file modified. No rebuild. Console clean on all passes.**
