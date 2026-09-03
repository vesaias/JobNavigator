# expected-D4b — Input / Textarea / SearchInput / Select replacements

D4b routes every text input, textarea, search field and select trigger in
`frontend/src/v2/*.jsx` (screens, modals, drawers; `UiGallery.jsx` + `ToastLab.jsx`
out of scope) through `Input` / `Textarea` / `SearchInput` / `Select` from `./ui`.
Values, `onChange`/`onBlur`/debounces, placeholders, `min`/`max`/`inputMode`,
`aria-label`, `readOnly`/`disabled`, secret masking, autosize and the `BulletText`
line-height 19 rule are untouched; `style` is passed for layout only.

Each screen's local field primitive (`Field`, `MicroField`, `cellInput`, `BOX`,
`INPUT`, `Cell`, `TextBox`, …) keeps its name and prop shape and becomes a thin
wrapper around the ui.jsx one, so call sites do not churn.

## Mapping rules used
- Canonical field (`Input`): **h29 · 1px `--input-border` · r6 (`--radius-field`) ·
  12.5 · `--input-bg`**, focus = accent border, no ring. Where a site already
  equals that, the swap is zero-pixel and is listed only for the record.
- `Textarea`: same box, `padding 7px 9px`, `lineHeight 19px`, `minHeight rows*20`,
  `resize: vertical`. A site that autosizes passes `style={{height, resize:'none'}}`
  exactly as it did inline.
- `SearchInput` **boxed**: h30 · r99 · 1px `--input-border` on `--search-bg` · 12 ·
  `padding 0 12px 0 29px` with the ⌕ inset. **underline**: h36 · no box ·
  1px `--input-underline` beneath · 13 · `padding 0 13px`.
- `Select`: h32 · r6 · 1px `--input-border` (accent while open) on `--search-bg` ·
  12.5 · caret 9px, listbox = `Menu` box with `--pill-on-*` on the selected row.
- A bare input inside a `v2-fieldwrap` (Applications/Settings/Stats toolbars,
  LoginModal) keeps its wrapper: the wrapper is the box and carries the focus
  signal, so the input itself stays borderless and inline.

Rows are `file:line | element | before → after`. A row marked **zero-pixel**
changes nothing and is listed only for the record.

## ui.jsx — additions

| site | element | before → after |
|---|---|---|
| ui.jsx:110 | `Button` | gains `as` + `type` pass-through: `as="button"` renders a real `<button type=…>` (UA `border`/`margin`/`appearance` reset first, `tabIndex={0}` kept so theme.css's `[tabindex="0"]:focus-visible` ring still applies, `disabled` set natively instead of `aria-disabled`) — **zero-pixel**; the default `div` path is byte-identical to D4a |

## LoginModal.jsx

| site | element | before → after |
|---|---|---|
| LoginModal.jsx:81 | "Sign in" / "Signing in…" submit | `Button onClick={submit} busy={loading}` (a `div[role=button]` since D4a) → `Button as="button" type="submit" busy={loading}`: **element `div[role=button]` → `<button type="submit">`**, `onClick` dropped (the form's `onSubmit` is the single entry point again, so a click no longer runs `submit` twice), Enter-in-the-key-field submits the form natively again, `aria-disabled` → the native `disabled` attribute while loading — **zero-pixel** |

### kept inline
- `LoginModal.jsx:70` — the API-key field: a bare borderless `<input type=password/text>` inside a `v2-fieldwrap` that also holds the show/hide toggle and turns `--bad` on an error. `// ui: keep — bare input in a fieldwrap composite`.

## Persona.jsx

| site | element | before → after |
|---|---|---|
| Persona.jsx:142 | autofill text fields (`AutofillField`, `kind==='text'` — 15 rendered sites: name/email/phone/city/…/notice period) | `v2-fieldwrap` `BOX` (h30 · pad 0 10 · 1px `--edge` · r6 · `--surface`) wrapping a bare borderless `<input>` at 12/`--sans`/`--text` → `Input`: **height 30 → 29**, **padding 0 10px → 0 9px**, **font-size 12 → 12.5**, **background `--surface` → `--input-bg` (`--surface-2`)**, **focus signal moves from the wrapper (`v2-fieldwrap:focus-within`) to the input's own border** (same `--input-border-focus` accent); border/radius unchanged (`--edge` = `--input-border`, r6 = `--radius-field`); gains `aria-label` from the field's visible label |
| Persona.jsx:119 | `Picker` trigger (every `enum`/`bool` field — 17 rendered sites) | inline `BOX` trigger h30 · pad 0 10 · 1px `--edge` (accent when open) · r6 · `--surface` · value 12 · caret 9 · `v2-act` hover → `Select` (thin wrapper keeps the `Picker` prop shape): **height 30 → 32**, **font-size 12 → 12.5**, **hover `v2-act` (accent border + `--card-bg-hover` wash) dropped** — `Select` has no hover, the border only turns accent while open; background `--surface` → `--search-bg` (same token value), padding/radius/caret size unchanged; gains `aria-haspopup="listbox"`, `role="listbox"`/`role="option"` rows and `aria-label` |
| Persona.jsx:119 | `Picker` menu | inline menu: 1px `--edge` · r9 · marginTop 5 · maxWidth 280 · maxHeight 260 · a `position:fixed` click-catcher → `Select`'s listbox: **border `--edge` → `--menu-border` (`--line`)**, **radius 9 → 10 (`--radius-menu`)**, **marginTop 5 → 4**, **maxWidth 280 → 420**, **maxHeight 260 → 320**, **the fixed click-catcher is replaced by a document click listener** (same outside-click-closes behaviour, but the rest of the page stays hoverable while the menu is open) |
| Persona.jsx:119 | "— not answered" row | own row, ink `--muted` when not current and `--accent` on `--accent-soft` when the field is unset → prepended as an option with the sentinel value `UNSET`: **ink `--muted` → `--menu-item-ink` (`--text-2`)**, **it is no longer highlighted when the field is unset** (nothing matches the trigger's `''`, so the trigger keeps showing the "—" placeholder as before). Picking it still writes `undefined` |

### kept inline
- Persona's Q&A bank question/answer fields are `BulletText` from `ResumeSections.jsx` (borderless, autosizing, line-height 19) — see that file's "kept inline".

**Needs decision:** `Input` is canonical h29 and `Select` canonical h32, so the Persona autofill grid — which pairs text fields and pickers in the same rows — now mixes 29 px and 32 px boxes where it used to be a uniform 30. If that reads badly, the fix is a `Select size="sm"` (h29) variant in `ui.jsx`, not per-site style.

## ResumeSections.jsx

The file's two local field primitives keep their names and prop shapes and become
thin wrappers; the shared `cellInput` style object is **deleted** (every one of its
call sites is now `Input`).

| site | element | before → after |
|---|---|---|
| ResumeSections.jsx:66 | `Field` (single-line) — the summary/role/date/school cells across every résumé section | inline `st` h30 · pad 0 9 · 1px `--edge` · r6 · `--surface-2` · 12.5 → `Input`: **height 30 → 29**; everything else already canonical |
| ResumeSections.jsx:65 | `Field` (`multiline`) — Summary, bullets-as-block, notes | inline `st` pad 7 9 · minHeight `rows*20` · `resize:vertical` · lh 19 · 1px `--edge` · r6 · `--surface-2` · 12.5 → `Textarea` — **zero-pixel** (the canonical Textarea is that signature exactly); the Ctrl/⌘-B bold shortcut is passed straight through as `onKeyDown` |
| ResumeSections.jsx:151 | `MicroField` — the ResumeEditor drawer's small labelled cells | inline h30 · pad 0 9 · 1px `--edge` · r6 · `--surface-2` · 12.5 → `Input`: **height 30 → 29**; gains `aria-label` from its visible label |
| ResumeSections.jsx:205 | Header → "Full name" | `{...cellInput, height:32, fontSize:13}` → `Input`: **height 32 → 29**, **font-size 13 → 12.5**; gains `aria-label` |
| ResumeSections.jsx:212 | Header → "Title" | same as :205 → `Input`: **height 32 → 29**, **font-size 13 → 12.5**; gains `aria-label` |
| ResumeSections.jsx:225 | contact item → display text | `{...cellInput, flex:1}` (h29 · 12) → `Input style={{flex:1,minWidth:0}}`: **font-size 12 → 12.5**; gains `aria-label` |
| ResumeSections.jsx:228 | contact item → URL | `{...cellInput, flex:1, fontSize:11.5, color:'var(--text-2)'}` → `Input style={{flex:1,minWidth:0}}`: **font-size 11.5 → 12.5**, **ink `--text-2` → `--input-ink` (`--text`)** — the URL cell no longer reads dimmer than its display-text sibling; gains `aria-label` |
| ResumeSections.jsx:229 | contact item → tracer stub (34 px) | `{...cellInput, flex:'0 0 34px', padding:'0 6px', textAlign:'center', fontFamily:'var(--mono)', fontSize:11}` → `Input mono style={{flex:'0 0 34px', padding:'0 6px', textAlign:'center'}}`: **font-size 11 → 12.5** (mono, width and centring unchanged); gains `aria-label` |
| ResumeSections.jsx:412 | `CategoryName` — the skills category cell | inline h29 · pad 0 9 · 1px `--edge` · r6 · `--surface-2` · 12 · weight 500 · `flex:'0 0 118px'` → `Input style={{flex:'0 0 118px', fontWeight:500}}`: **font-size 12 → 12.5**; the 500 weight and the 118 px track are kept as layout/type-weight overrides. The 500 ms debounce + `onBlur` flush + rename-refusal snapback are untouched |

### kept inline
- `ResumeSections.jsx:100` — `BulletText`: a bullet is flowing text, not a field — no border, no background, `padding:0`, `resize:none` + `overflow:hidden` for the autosize, ink/weight swung by `bold`, and **line-height 19** (the whole-pixel rule). The row around it draws the box. `// ui: keep`.
- `ResumeSections.jsx:385` — the skills *values* input: a bare borderless input inside the row's own bordered box, which is what carries the ✦ tailoring border and the added/↩ affordances. `// ui: keep`.

## ResumeEditor.jsx

| site | element | before → after |
|---|---|---|
| ResumeEditor.jsx:791 | tailor modal → "Search jobs…" | inline h32 · pad 0 10 · 1px `--edge` · r8 · `--surface-2` · 12.5 → `Input`: **height 32 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6 (`--radius-field`)**; gains `aria-label` |
| ResumeEditor.jsx:810 | tailor modal → freeform JD textarea | inline pad 8 10 · **1px dashed** `--edge` · r8 · `--surface-2` · 12 · `resize:vertical` · rows 3 → `Textarea style={{borderStyle:'dashed'}}`: **padding 8px 10px → 7px 9px**, **radius 8 → 6**, **font-size 12 → 12.5**, **line-height 1.5 → 19px**; the dashed border is kept as a `borderStyle` override on the canonical `--input-border` (it is what marks this as the "…or paste one" alternative to the picker above); gains `aria-label` |

### kept inline
- `ResumeEditor.jsx:786` — `<input type="checkbox">` in the tailor modal: a native checkbox, not one of the four field roles. `// ui: n/a`.

## CoverLetterEditor.jsx

Both local style objects are **deleted**: `CELL` (the contact-item cell, 1:1 with
the résumé header's `cellInput`) and `INPUT` (the labelled letter fields).

| site | element | before → after |
|---|---|---|
| CoverLetterEditor.jsx:380 | Header → "Full name" | `INPUT` (h32 · pad 0 10 · 1px `--edge` · r6 · **`--surface`** · 13) → `Input`: **height 32 → 29**, **padding 0 10px → 0 9px**, **font-size 13 → 12.5**, **background `--surface` → `--input-bg` (`--surface-2`)**; gains `aria-label` |
| CoverLetterEditor.jsx:430 | Recipient → "Company" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:434 | Recipient → "Date" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:438 | Recipient → "Hiring manager" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:442 | Recipient → "Address" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:451 | Letter → "Greeting" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:477 | Letter → "Closing" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:481 | Letter → "Signature" | `INPUT` → `Input` — same four changes |
| CoverLetterEditor.jsx:400 | contact item → display text | `{...CELL, flex:1}` (h29 · 12) → `Input style={{flex:1,minWidth:0}}`: **font-size 12 → 12.5**; gains `aria-label` |
| CoverLetterEditor.jsx:405 | contact item → URL | `{...CELL, flex:1, fontSize:11.5, color:'var(--text-2)'}` → `Input style={{flex:1,minWidth:0}}`: **font-size 11.5 → 12.5**, **ink `--text-2` → `--input-ink`** (matches the identical fix in `ResumeSections.jsx:228`); gains `aria-label` |
| CoverLetterEditor.jsx:409 | contact item → tracer stub (34 px) | `{...CELL, flex:'0 0 34px', padding:'0 6px', fontFamily:'var(--mono)', fontSize:11, textAlign:'center'}` → `Input mono style={{flex:'0 0 34px', padding:'0 6px', textAlign:'center', minWidth:0}}`: **font-size 11 → 12.5**; gains `aria-label` |

### kept inline
- `CoverLetterEditor.jsx:468` — the ¶ body-paragraph textarea: a bare borderless, transparent, `resize:none` textarea whose box is the paragraph card around it (which carries the ¶ number and the ↑ ↓ ✕ controls); it uses `margin`, not padding, so the card's chrome sits above it. `// ui: keep`.

## CoverLetters.jsx

| site | element | before → after |
|---|---|---|
| CoverLetters.jsx:331 | header "Search letters, companies… " | inline h36 · width 280 · pad 0 13 · `border:none` · `borderBottom 1px --line-strong` · transparent · 13 → `SearchInput variant="underline" width="280px"` — **zero-pixel** (`--input-underline` = `--line-strong`, and the wrapper's `flex:0 0 280px` reproduces the fixed width); gains `aria-label` |

### kept inline
- `CoverLetters.jsx:34` — `Picker` (the résumé/job selects, shared with the editor's Regenerate modal): its options carry a **second `sub` line**, and it claims Escape (RES-15) so the modal around it does not close on the same press. `Select` renders single-line `[value, label]` rows. Not an input-role scan site either. `// ui: keep`.
- `CoverLetters.jsx:99` — `LengthPicker` is a segmented pill control, not a field (pill role).

## Resumes.jsx

| site | element | before → after |
|---|---|---|
| Resumes.jsx:154 | header "Search bases, copies, archived…" | inline h36 · width 300 · **pad 0 2** · `border:none` · `borderBottom 1px --line` · transparent · 13 → `SearchInput variant="underline" width="300px"`: **padding 0 2px → 0 13px** (the text starts 11 px further right, matching Cover Letters' identical field), **underline `--line` → `--input-underline` (`--line-strong`)**; height/width/font unchanged; gains `aria-label` |
| Resumes.jsx:351 | "New base résumé" modal → name field | inline w100% · h38 · pad 0 12 · 1px `--edge` · r8 · `--surface-2` · 13 → `Input style={{marginBottom:14}}`: **height 38 → 29**, **padding 0 12px → 0 9px**, **radius 8 → 6**, **font-size 13 → 12.5**; `autoFocus` and the Enter-to-create `onKeyDown` pass straight through; gains `aria-label` |

### kept inline
- `Resumes.jsx:363` — the hidden `<input type="file">` behind "Import PDF ↑" (`display:none`). `// ui: keep — not a rendered field`.

## Searches.jsx

`Cell` keeps its name and its full prop list (`label/value/onChange/mono/placeholder/
span/sub/disabled/options/type/min/max`) and now renders `Input` or `Select`; its
local `st` style object is deleted.

| site | element | before → after |
|---|---|---|
| Searches.jsx:189 | `Cell` text/number fields (Name, Search term, Location, Hours old, Results wanted, Max pages, Min score, the two direct URLs, the four title/company filter lists, the disabled Mode box for the two extension searches — ~16 rendered sites) | inline `st` h31 · pad 0 10 · 1px `--edge` · r7 · `--surface` · 12.5 (mono 11.5) → `Input`: **height 31 → 29**, **padding 0 10px → 0 9px**, **radius 7 → 6**, **background `--surface` → `--input-bg` (`--surface-2`)**, **mono font-size 11.5 → 12.5**; **disabled look `--surface-2` on `--muted` → the canonical box at opacity .6**; `type`/`min`/`max` (R2-A-02) pass straight through; gains `aria-label` from the cell's visible label |
| Searches.jsx:187 | `Cell` dropdowns (Mode, Remote, Job type) | a **native `<select>`** wearing the same `st` box → `Select`: **height 31 → 32**, **radius 7 → 6**, **element `<select>` → a `div` trigger + `role="listbox"` panel** (the popup is now drawn in-page instead of by the OS, so it is themed and the option rows match every other v2 menu — the trade is that a menu opened near the bottom of the scrolling form scrolls its container instead of floating over it), background `--surface` → `--search-bg` (same value), padding 0 10px and the 12.5 label unchanged; gains `aria-haspopup="listbox"`, `aria-expanded`, `aria-selected` and `aria-label` |
| Searches.jsx:310 | "Run interval · min" | inline width 110 · h31 · pad 0 10 · 1px `--edge` · r7 · `--surface` · mono 11.5 → `Input mono type="number" style={{width:110}}`: **height 31 → 29**, **padding 0 10px → 0 9px**, **radius 7 → 6**, **background `--surface` → `--surface-2`**, **font-size 11.5 → 12.5**; the 110 px track is kept; gains `aria-label` |

## Companies.jsx

The two local style objects `inputBox` (h33 min · pad 0 10 · 1px `--edge` · r8 ·
`--surface` · 12) and `monoBox` (the same at mono 10.5) are **deleted** — every
call site is now `Input`.

| site | element | before → after |
|---|---|---|
| Companies.jsx:419 | toolbar "Search name, alias, URL or ATS…" | inline `<span flex:0 0 226px>` + absolutely-positioned ⌕ + input h30 · pad 0 12 0 29 · 1px `--edge` · r99 · `--surface` · 12 → `SearchInput width="226px"` (boxed variant) — **zero-pixel**; the ⌕ glyph, its 12 px offset and the 226 px track are the primitive's own; gains `aria-label` |
| Companies.jsx:111 | `UrlEditor` row → career-page URL | `{...monoBox, flex:1, height:32}` (pad 0 10 · r8 · `--surface` · mono 10.5) → `Input mono style={{flex:1,minWidth:0}}`: **height 32 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--input-bg` (`--surface-2`)**, **font-size 10.5 → 12.5**; gains `aria-label` |
| Companies.jsx:690 | drawer → "Display name" | `{...inputBox, height:32}` → `Input`: **height 32 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**, **font-size 12 → 12.5**; gains `aria-label` |
| Companies.jsx:694 | drawer → "Also known as" | same as :690 |
| Companies.jsx:707 | drawer → "Title must match" | same as :690 |
| Companies.jsx:712 | drawer → "Skip titles containing" | same as :690 |
| Companies.jsx:742 | drawer → "Scrape interval in minutes" | same as :690 (`type="number" min={1}` passes through) |
| Companies.jsx:752 | drawer → "Pages to read" | same as :690 (`type="number" min={1} max={20}`) |
| Companies.jsx:747 | drawer → "Wait for element" | `{...monoBox, height:32}` → `Input mono`: same four box changes plus **font-size 10.5 → 12.5** |
| Companies.jsx:758 | drawer → "H-1B employer name" | same as :747 |
| Companies.jsx:834 | add modal → career page URL | `{...monoBox, flex:1, height:33, fontSize:11}` → `Input mono style={{flex:1,minWidth:0}}`: **height 33 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**, **font-size 11 → 12.5**; gains `aria-label` |
| Companies.jsx:841 | add modal → "Company name" | `{...inputBox, height:33, fontSize:12.5}` → `Input`: **height 33 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**; gains `aria-label` |
| Companies.jsx:845 | add modal → "Aliases" | `{...inputBox, height:33}` → `Input`: same as :841 plus **font-size 12 → 12.5** |
| Companies.jsx:855 | add modal → "Scrape interval in minutes" | `{...inputBox, height:33, fontSize:12.5}` → `Input type="number" min={1}`: same as :841 |

## ui.jsx — second addition

| site | element | before → after |
|---|---|---|
| ui.jsx:205 / :218 | `Input` / `Textarea` | gain a `defaultValue` prop: when it is passed, the field renders **uncontrolled** (`defaultValue` instead of `value`), which is the shape Applications' autosaving notes box needs. `value` behaves exactly as before — **zero-pixel** |

## Applications.jsx

The two local style objects `inputSt` (h29 · pad 0 9 · r6 · `--surface` · 12.5 —
canonical apart from its background) and `box` (h33 · pad 0 10 · r8 · `--surface` ·
12.5) are **deleted**.

| site | element | before → after |
|---|---|---|
| Applications.jsx:586 | interview edit → "What" | `inputSt` → `Input`: **background `--surface` → `--input-bg` (`--surface-2`)** only; `autoFocus` passes through; gains `aria-label` |
| Applications.jsx:591 | interview edit → "When" (`type="datetime-local"`) | same as :586 |
| Applications.jsx:595 | interview edit → "Where" | same as :586 |
| Applications.jsx:600 | interview edit → "Prep note" | same as :586 |
| Applications.jsx:622 | new interview → "What" | same as :586 |
| Applications.jsx:627 | new interview → "When" | same as :586 |
| Applications.jsx:631 | new interview → "Where" | same as :586 |
| Applications.jsx:636 | new interview → "Prep note" | same as :586 |
| Applications.jsx:651 | detail → "Notes · autosaves" | inline uncontrolled textarea: minHeight 64 · pad 10 12 · 1px **`--line`** · r8 · `--bg` · 13 · lh 20 · ink `--text-2` → `Textarea defaultValue rows={3} style={{minHeight:64}}`: **padding 10px 12px → 7px 9px**, **border `--line` → `--input-border` (`--edge`)**, **radius 8 → 6**, **background `--bg` → `--input-bg` (`--surface-2`)**, **font-size 13 → 12.5**, **line-height 20 → 19**, **ink `--text-2` → `--input-ink` (`--text`)**; the `key={d.id}` remount, the uncontrolled `defaultValue`, the per-keystroke `onChange` and the flush-on-`onBlur` are untouched; gains `aria-label` |
| Applications.jsx:788 | log modal → "Posting URL" | `{...box, fontFamily:'var(--mono)', fontSize:11}` → `Input mono`: **height 33 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**, **font-size 11 → 12.5**; the `onBlur` URL read is untouched; gains `aria-label` |
| Applications.jsx:794 | log modal → "Title" | `box` → `Input`: **height 33 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**; gains `aria-label` |
| Applications.jsx:798 | log modal → "Company" | same as :794 |
| Applications.jsx:822 | log modal → "Applied on" (`type="date"`) | same as :794 |
| Applications.jsx:827 | log modal → "Notes" | `{...box, height:'auto', minHeight:52, padding:'9px 10px', lineHeight:'19px', resize:'vertical'}` → `Textarea rows={2} style={{minHeight:52}}`: **padding 9px 10px → 7px 9px**, **radius 8 → 6**, **background `--surface` → `--surface-2`**; line-height 19 and the 52 px floor are kept; gains `aria-label` |

### kept inline
- `Applications.jsx:350` — the toolbar search: a bare borderless input inside the r99 `v2-fieldwrap` that carries the ⌕ and the focus signal (the brief pins this one). `// ui: keep` (annotation already in place from D4a).

## JobFeed.jsx

| site | element | before → after |
|---|---|---|
| JobFeed.jsx:735 | filter bar "Search titles…" | inline width 226 · h30 · pad 0 12 0 29 · r99 · **1px `--line`** · `--surface` · **12.5**, with the ⌕ absolutely placed by the outer div → `SearchInput width="226px"` (boxed): **border `--line` → `--input-border` (`--edge`)**, **font-size 12.5 → 12**; height/width/radius/padding/⌕ position unchanged. The FEED-25 clear ✕ keeps its `position:absolute; right:8` and now rides in the outer wrapper (which gains `display:flex; align-items:center` so it still overlays the box); gains `aria-label` |
| JobFeed.jsx:748 | Company filter menu → "Type to search N companies…" | inline h30 · pad 0 10 · 1px `--edge` · r7 · `--surface-2` · 12.5 · `marginBottom:6` → `Input style={{marginBottom:6}}`: **height 30 → 29**, **padding 0 10px → 0 9px**, **radius 7 → 6**; `autoFocus` passes through; gains `aria-label` |
| JobFeed.jsx:778 | Score menu → "or at least" number box | inline h28 · pad 0 9 · 1px `--edge` · r7 · `--surface-2` · mono 12 · `flex:1` → `Input mono type="number" style={{flex:1,minWidth:0}}`: **height 28 → 29**, **radius 7 → 6**, **font-size 12 → 12.5**; gains `aria-label` |
| JobFeed.jsx:789 | Salary menu → "at least" number box | same signature as :778 → same three changes; gains `aria-label` |

## Stats.jsx

No site migrated — the screen's one field is a kept-inline search wrapper.

### kept inline
- `Stats.jsx:661` — the activity-log "Company…" search: a bare borderless input inside a **26 px transparent** r99 `v2-fieldwrap` that carries the ⌕ and the focus signal. `SearchInput`'s boxed variant is h30 on `--search-bg`, which does not sit on this log-header row. `// ui: keep` (annotation from D4a, reason expanded).

## Settings.jsx

The screen's own `Select` component (and its `CARET` style object) are **deleted**
and replaced by `./ui`'s `Select`. Every call site keeps its exact props
(`value/options/onPick/width/mono/placeholder/ariaLabel/emptyText`).

| site | element | before → after |
|---|---|---|
| Settings.jsx:565 / :574 / :575 / :584 / :585 / :975 | the six `Select` dropdowns (row selects, provider + model pickers, the per-feature LLM overrides, the model-catalog provider) | the file's local `Select` → `./ui`'s `Select` — **zero-pixel**: `ui.jsx`'s Select was generalised from this exact component, and every value matches token-for-token (trigger h32 · pad 0 10 · 1px `--input-border`, accent while open · r6 · `--search-bg` · 12.5 / mono 11.5 · caret 9; listbox marginTop 4 · maxWidth 420 · maxHeight 320 · 1px `--menu-border` · r10 · `--menu-shadow` · pad 5; rows pad 7 9 · r6 · 12.5 · `--pill-on-*` when selected). Two differences, both handled: the empty-menu message loses `textWrap:'pretty'` (it now wraps on normal word breaks), and SET-23's default text is no longer the component's default — the two model pickers pass it explicitly as `emptyText={NO_MODELS}` |
| Settings.jsx:876 | prompt/JSON editor modal → textarea | inline flex 1 · minHeight 440 · pad 12 14 · 1px `--edge` (→ `--bad` on a parse error) · r8 · `--surface` · mono 11.5 · lh 20 → `Textarea mono style={{flex:1, minHeight:440, …err && borderColor}}`: **padding 12px 14px → 7px 9px**, **radius 8 → 6**, **background `--surface` → `--input-bg` (`--surface-2`)**, **font-size 11.5 → 12.5**, **line-height 20 → 19**; the `--bad` error border is kept as a `borderColor` override, and the save-as-you-type `commit` is untouched |

### kept inline
- `Settings.jsx:22` — the `BOX` style object: it *is* `Select`'s trigger box to the pixel, and the value rows pair a `Select` with a `TextBox`, so both have to stay h32. The comment above it now says to change the two together.
- `Settings.jsx:86` — `TextBox`: a bare input inside the `BOX` `v2-fieldwrap`, which carries the focus signal **and** the secret show/hide link; the secret-mask save rules (SET-27) are untouched. `// ui: keep`.
- `Settings.jsx:735` — `ApiKeyRow`: the same fieldwrap composite (bare mono input + show/hide). `// ui: keep`.
- `Settings.jsx:790` — the LinkedIn **PIN** box: a 120 px `v2-fieldwrap` on the sign-in status row (named as a keep in the brief). `// ui: keep`.
- `Settings.jsx:979` — the model-catalog typeahead: the input drives a suggestion listbox (`aria-expanded`, `aria-autocomplete`, ↑ ↓ Esc Enter) inside a 31 px fieldwrap. `// ui: keep`.
- `Settings.jsx:489` — the header "Search settings…" field: bare input in an r99 `v2-fieldwrap` (the brief pins this one). `// ui: keep` (annotation from D4a).
- `Settings.jsx:641` — the webhook-secret **preview** box: a `<span>` wearing `BOX`, no field inside; the scan tagged it `input` because of its `cursor:'default'`. `// ui: keep`.

**Needs decision (the D4b analogue of D4a's h31/h33 note):** the canonical `Input`
is **h29** and the canonical `Select` trigger is **h32**. Settings is built around
the 32 (its `BOX` and its Selects), so its value fields stay at 32 and are the
kept-inline list above; every other screen's fields move to 29, and Persona and
Searches now put a 29 `Input` next to a 32 `Select` in the same grid row. If that
gap should close, the fix is one number in `ui.jsx` — either `Input` to 32 or a
`Select size="sm"` at 29 — not per-site style.

## ConfirmDialog.jsx

*(not in the run's file order, but — as in D4a — it is a v2 modal with an in-scope
site, so it is included)*

| site | element | before → after |
|---|---|---|
| ConfirmDialog.jsx:45 | `PromptDialog` value field | inline h33 · marginTop 4 · pad 0 10 · 1px `--edge` · r8 · `--surface` · 12.5 (mono 11.5) → `Input mono={mono} style={{marginTop:4}}`: **height 33 → 29**, **padding 0 10px → 0 9px**, **radius 8 → 6**, **background `--surface` → `--input-bg` (`--surface-2`)**, **mono font-size 11.5 → 12.5**; `readOnly`, `autoFocus`, the Enter-to-submit `onKeyDown` and the select-all-on-focus `onFocus` all pass straight through; gains `aria-label` from the dialog title |

---

## Scanner gate (`py v2-testing/tools/stylescan.py`)

| role | before (post-D4a) | after | after, excluding `ui.jsx` |
|---|---|---|---|
| input (text inputs, textareas, search fields, select triggers) | 71 sites / 39 signatures | 19 sites / 13 signatures | **17** — every one is listed under a "kept inline" heading above |

`ui.jsx`'s own two rows (`ui.jsx:230` `Input`, `ui.jsx:241` `Textarea`) are the
primitives themselves. The 17 remaining screen sites are:

`Applications.jsx:350` · `CoverLetterEditor.jsx:468` · `LoginModal.jsx:71` ·
`ResumeSections.jsx:100` · `ResumeSections.jsx:385` · `Resumes.jsx:363` ·
`Settings.jsx:86`+`:87` · `:489` · `:639` · `:735`+`:736` · `:790`+`:791` ·
`:979`+`:980` · `Stats.jsx:661`

(the paired numbers are one composite each — the `v2-fieldwrap` box and the bare
input inside it, which the scanner counts separately). Every one carries a
`// ui: keep — …` or `{/* ui: keep — … */}` comment within the lines above it;
verified mechanically.

**54 sites migrated** across 13 files, plus the two `ui.jsx` pass-through additions
(`Button as/type`, `Input`/`Textarea` `defaultValue`) and the D4a carry-over fix to
`LoginModal`'s submit button. Six local field primitives were rewritten as thin
wrappers (`Field`, `MicroField`, `Picker` in Persona, `Cell` in Searches) or
deleted outright (`cellInput`, `CELL`, `INPUT`, `inputBox`, `monoBox`, `inputSt`,
`box`, `CARET`, and Settings' whole local `Select`).
