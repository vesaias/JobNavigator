# expected-D4b-fixup — 32 px fields, and the dead `minHeight` in Applications

Two user decisions taken after D4b's reconciliation (`reconcile-D4b.md`), applied
as a source-only fix-up before D4c.

1. **Every boxed field is 32 px.** D4b shipped `Input` at h29 while `Select` is
   h32, so any row that pairs a text field with a dropdown — Persona's autofill
   grid, Searches' `Cell` grid, Settings' value rows, the model-catalog toolbar —
   mixed two heights. `D1-D2.md` §"Decisions during D4" resolves it: **32 px
   everywhere**. `Input`, the boxed `SearchInput` and every `Field`/`MicroField`/
   `Cell`/`TextBox` wrapper line up with `Select`. `Textarea` has no fixed height
   (its box is intrinsic to `rows`), so the 32 is expressed as its **single-line
   basis**. Underline search fields are visually a different control — no box at
   all — and keep their own 36.
2. **`Applications.jsx` notes box** — the `style={{minHeight:64}}` flagged as dead
   in `reconcile-D4b.md` §(6) is **made effective**, not removed (see below).

Rows are `file:line | element | before → after`. One row per primitive/wrapper
with its site count — not one row per call site.

## ui.jsx — the primitives

| site | element | before → after | sites |
|---|---|---|---|
| ui.jsx:234 | `Input` | **height 29 → 32**; everything else unchanged (pad `0 9px`, 1px `--input-border`, `--radius-field`, `--t-12-5`, `--input-bg`, focus = accent border) | **53** call sites across 10 screens (`Applications` 12, `Companies` 13, `CoverLetterEditor` 11, `ResumeSections` 8, `JobFeed` 3, `Searches` 2, `ConfirmDialog`/`Persona`/`ResumeEditor`/`Resumes` 1 each) + 6 in `UiGallery` |
| ui.jsx:245-246 | `Textarea` | **padding `7px 9px` → `5.5px 9px`**, **`minHeight` `rows*20` → `rows*19 + 13`**. Line-height stays 19 px and the border stays 1 px, so the **single-line box is 19 + 11 + 2 = 32 px**, identical to `Input`; `minHeight` now *equals* the browser's intrinsic `rows`-driven height instead of being an arbitrary floor 3-4 px under it. Net effect on a box with no caller floor: **−3 px per textarea** (was `rows*19 + 16`) | **5** call sites (`Applications` 2, `ResumeEditor` 1, `ResumeSections` 1 (`Field multiline`), `Settings` 1) + 3 in `UiGallery` |
| ui.jsx:266 | `SearchInput` **boxed** | **height 30 → 32**; r99, 1px `--input-border`, `--search-bg`, `--t-12`, `padding 0 12px 0 29px` and the ⌕ inset unchanged (the glyph is centred by `top:50%`, so it tracks the new height) | **2** (`Companies.jsx:419`, `JobFeed.jsx:735`) |
| ui.jsx:260-264 | `SearchInput` **underline** | **unchanged — h36.** Per the brief: a visually different control (no box, no radius, a rule beneath instead of a border) | 2 (`CoverLetters.jsx:331`, `Resumes.jsx:154`) — **zero-pixel** |
| ui.jsx:300 | `Select` trigger | **unchanged — already h32.** It is the height the other three moved to | 12 call sites — **zero-pixel** |

## Screen wrappers — they inherit, no code change

These four kept their names and prop shapes in D4b and already delegate to
`Input`/`Textarea`/`Select`, so the 32 arrives through the primitive. Listed for
the record: every one of their call sites moves 29 → 32.

| site | wrapper | before → after | sites |
|---|---|---|---|
| ResumeSections.jsx:51 | `Field` (single-line arm renders `Input`; `multiline` arm renders `Textarea`) | **height 29 → 32** (single-line); the multiline arm takes the textarea's **−3 px** | **5** uses inside the résumé/persona sections; the `<label>` wrapping each grows to 51 px (was 48) |
| ResumeSections.jsx:148 | `MicroField` (label + `Input`) | **height 29 → 32** | **9** |
| Searches.jsx:182 | `Cell` (renders `Input` or `Select`) | **height 29 → 32** on the `Input` arm; the `Select` arm was already 32, so a `Cell` grid is now uniform | **21** |
| Settings.jsx:62 / :28 | `TextBox` / the `BOX` style object | **unchanged — already h32.** The comment above `BOX` pins it to `Select`; that pin is now correct for `Input` too | 2 `TextBox` + 3 other `BOX` users |

## Kept-inline field composites — the boxed ones follow, the odd ones do not

D4b left seven `v2-fieldwrap` composites inline (a bare input inside a bordered
wrapper that carries the focus signal and an extra affordance). The wrapper *is*
the box there, so its height is the field's height and it has to track the same
decision — where it is the same kind of box.

| site | element | before → after |
|---|---|---|
| Applications.jsx:348 | toolbar search — r99 `v2-fieldwrap` + ⌕ + bare input | **height 30 → 32**; it is the boxed-search shape `SearchInput` draws, so it moves with it. Nothing else changes |
| Settings.jsx:487 | header "Search settings…" — same r99 composite | **height 30 → 32**, same reason |
| Settings.jsx:979 | model-catalog typeahead — `{...BOX, flex:1, height:31}` | **the `height: 31` override is deleted** → inherits `BOX`'s **32**. It sits in a toolbar beside a `Select` and was 1 px short of it; a pure drift fix |

### kept inline (unchanged, with reasons)

- `Stats.jsx:659` — the activity-log "Company…" search: a **26 px transparent**
  r99 fieldwrap sitting on a log-header row, not a form field. Already documented
  as deliberately different from the boxed search; the comment's stale
  "SearchInput's boxed variant is h30" is corrected to h32.
  `// ui: keep — 26px transparent log-header pill`.
- `LoginModal.jsx:67` — the API-key field, **h36**: the only field on that screen,
  sized to its `Button` md (h36) submit directly beneath it. Moving it to 32
  would misalign the pair it exists to match. `// ui: keep — sized to the submit`.
- `Settings.jsx:86` (`TextBox`), `:735` (`ApiKeyRow`), `:790` (LinkedIn PIN),
  `:639` (webhook-secret preview) — all already h32 via `BOX`. **zero-pixel.**
- `ResumeSections.jsx:100` (`BulletText`), `:385` (skills values),
  `CoverLetterEditor.jsx:468` (¶ paragraph), `Applications.jsx:350` /
  `Settings.jsx:87`/`:736`/`:791`/`:980` / `Stats.jsx:661` (the bare inputs inside
  the composites above), `Resumes.jsx:363` (hidden file input) — borderless
  inputs with no box of their own. **zero-pixel.**

## Applications.jsx:653 — the dead `minHeight:64`

`reconcile-D4b.md` §(6): the notes box carried `rows={3}` **and**
`style={{minHeight:64}}`; at line-height 19 the `rows`-driven intrinsic height
(73 px) exceeded the floor, so the floor never engaged and the box rendered 9 px
taller than the code implies — 73 px in a 92 px wrapper, against **83 px** before
D4b.

**Chosen: make the floor effective** (the brief's "whichever matches the pre-D4b
look (83 px)").

| site | element | before → after |
|---|---|---|
| Applications.jsx:655 | Notes · autosaves textarea | **`rows={3}` → `rows={2}`**, `minHeight:64` kept. Intrinsic height is now 2×19 + 13 = **51 px**, under the 64 floor, so the floor is what renders: **textarea 73 → 64 px**, **wrapper 92 → 83 px** — exactly the pre-D4b box. A comment records why the two values are paired |

Removing the `minHeight` instead would have left the box at the textarea's new
intrinsic 70 px (3×19 + 13) — closer to 73 than to 64, and still not the pre-D4b
look, so the floor is kept and made real rather than dropped.

### consequence elsewhere

| site | element | before → after |
|---|---|---|
| Applications.jsx:831 | "Add application" modal → Notes textarea (`rows={2}`, `minHeight:52`) | intrinsic 54 → 51, so the 52 floor now wins: **height 54 → 52**. Same mechanism, no code change |

## Gallery

`UiGallery.jsx` (`/v2/ui`) updates the two canonical strings — `Input · Textarea`
to `h32 (textarea: 32 single-line, rows·19+13)` and `SearchInput` to
`boxed h32 r99 …` — and gains one specimen, **`textarea · 1 row (= Input h32)`**,
so the style crawl can assert the single-line basis directly against `Input`.

## Scanner

The `input` role is unchanged in count: 19 sites / 13 signatures before and after
(17 screen sites, all under a "kept inline" heading in `expected-D4b.md` or this
file, plus `ui.jsx`'s own two). Three of those signatures change value
(`height: 30` → `height: 32` on the two r99 composites, and `height: 31`
disappearing from `Settings.jsx:979`), none change count.
