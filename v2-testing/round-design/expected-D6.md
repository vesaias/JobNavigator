# expected-D6 — theme store, System mode, and the `alt` skin

D6 is the proof that the D2–D5 semantic layer is a *layer*: a second palette and a
second font set, dropped in at the palette level, must repaint the app without
moving a single pixel of geometry. It also closes SHELL-02 (three-state theme) and
SHELL-06 (two shells, two copies of the flag).

Source-only step: no rebuild, no restart, no commit was made by the D6 run itself.

---

## 1 · What changed in source

| file | change |
|---|---|
| `frontend/src/v2/theme.js` | **new.** The one theme store: mode `light \| dark \| system` (localStorage `jobnavigator_theme`, migrating the old boolean `jobnavigator_dark_mode` once), skin `default \| alt` (localStorage `jobnavigator_skin`), a `prefers-color-scheme` listener for `system`, a cross-tab `storage` listener, `useTheme()` → `{mode, resolved, skin, setMode, setSkin, cycle}`, plus `themeAttrs()`, `themeTitle()`, `MODE_ICON/MODE_LABEL/MODE_OPTIONS/SKIN_OPTIONS`. |
| `frontend/index.html` | inline boot script (stamps `data-theme` + `data-skin` + `html.dark` before React mounts) and a 4-rule `<style>` that paints the pre-mount ground. |
| `frontend/src/v2/theme.css` | header comment rewritten; **two new blocks** `.jn-v2[data-skin="alt"]` and `.jn-v2[data-skin="alt"][data-theme="dark"]`. Every pre-existing declaration is byte-identical (`git diff` on this file shows exactly two removed lines, both comment). |
| `frontend/src/v2/V2App.jsx` | rail ◐ now cycles Light → Dark → System, glyph `◐ / ◑ / ◒`, tooltip `Theme: <Mode> — click to switch`; both the footer button and the collapsed one. Root spreads `themeAttrs()`. |
| `frontend/src/v2/UiGallery.jsx` | header switcher: `Skin` pills (`default`/`alt`) + `Theme` pills (`◐ Light`/`◑ Dark`/`◒ System`), replacing the single ◐ Dark/Light button — all four combinations one click apart. |
| `frontend/src/v2/ToastLab.jsx` | its private dark flag replaced by the store; the header button cycles the three modes. |
| `frontend/src/v2/LoginModal.jsx`, `WelcomeModal.jsx` | their private `localStorage.getItem('jobnavigator_dark_mode')` reads replaced by `useTheme()`; scrim gets `themeAttrs()`. |
| `frontend/src/v2/Settings.jsx` | new **first** section `GENERAL › Appearance` with two localStorage-only rows (`Theme`, `Skin`) rendered by `ThemeRow`/`SkinRow`; anchor-rail default `active` moved `'models'` → `'appearance'`. |
| `frontend/src/App.jsx` | the classic shell drops its own `darkMode` state + `html.dark` effect and reads `useTheme().resolved` instead, so v1 follows the same store with no reload. |

### Attribute host
`<html>` is the **boot host**: the inline script stamps `data-theme` (the *resolved*
light/dark, not the mode), `data-skin`, and the classic shell's `.dark` class before
the bundle runs; `theme.js` re-stamps the same three on every change. Every `.jn-v2`
root **mirrors** both attributes through React props (`themeAttrs()`).
`theme.css` therefore keeps selecting on the root itself — `.jn-v2[data-theme="dark"]`,
`.jn-v2[data-skin="alt"]`, `.jn-v2[data-skin="alt"][data-theme="dark"]` — exactly as
before; `<html>` is a copy for the pre-mount frame, never a second source of truth.
No descendant selector (`[data-theme="dark"] .jn-v2`) was added: it would weigh the
same (0,2,0) as `.jn-v2[data-theme="dark"]` and make the cascade order-dependent, and
it is not needed once every root mirrors.

The only palette values living outside `theme.css` are the four `--bg` hexes in
`index.html`'s `<style>` (`:root[data-theme=…]`, specificity (0,2,0), which beats
`index.css`'s `html.dark` (0,1,1) deterministically whatever order Vite emits the
sheets in). They are only ever visible before React mounts — both shells cover the
viewport with their own ground.

---

## 2 · The skin gate

**A skin switch may change colour and font family. It may change nothing else.**

Run the crawl twice on the same bundle — once default, once `--skin alt` — and diff.
Using `stylecrawl.py`'s `PROPS`:

| may differ under `data-skin="alt"` | must be identical |
|---|---|
| `backgroundColor` | `borderTopWidth`, `borderTopStyle` |
| `color` | `borderRadius` |
| `borderTopColor`, `borderBottomColor` | `fontSize`, `fontWeight` |
| `boxShadow` — **colour components only**; every offset/blur/spread must match | `lineHeight` |
| `fontFamily` | `paddingTop`, `paddingLeft` |
| | `height` (see the caveat below) |
| | `letterSpacing`, `textTransform`, `opacity`, `cursor` |

In practice `boxShadow` should not move at all: `--shadow-*` is deliberately **not**
re-skinned (black alphas, already theme-neutral, and their offsets are part of the
geometry this gate pins). A `boxShadow` diff whose *offsets* changed is a regression,
full stop.

`--cc-*` / `--sm-*` (ATS and search-mode badge hues) are also deliberately not
re-skinned — they are an identity taxonomy, not theme colour — so every `.cc-*`/`.sm-*`
chip should show **zero** diffs, `backgroundColor`/`color` included. Same for the
on-rail overlays `--rail-active` / `--rail-hover` / `--on-rail-*` (white alphas that
work on any dark rail) and `--knob` / `--iframe-bg`.

### The `height` caveat (the one honest exception)
`height` is fixed by the primitives for every control, row, header and modal, so it
must not move there. It is *not* fixed for text-wrapped containers (help columns,
card bodies, the Settings row stack, `textWrap: 'pretty'` blocks): a different
`fontFamily` changes glyph advance widths, so a paragraph can rewrap and grow or lose
a line. That is a font consequence, not a layer failure.

**So run the proof in two passes:**

1. **Palette pass** — temporarily neutralise the three font declarations in the alt
   blocks (or crawl with `document.documentElement.style.setProperty` overriding
   `--sans/--serif/--mono` back to the defaults). Gate: **zero** diffs in every "must
   be identical" property, `height` included. This is the strict gate.
2. **Font pass** — full alt skin. Gate: the "must be identical" list still holds for
   every element with an explicit height (anything from `ui.jsx`), and the only
   `height` diffs are on auto-height text blocks, each explainable by a rewrap. Any
   `fontSize`/`lineHeight`/`padding*`/`borderRadius`/`borderTopWidth` diff at all is a
   regression.

### Commands

```bash
# inside the backend container, after a rebuild
python /tmp/v2t/stylecrawl.py D6                 # default skin
python /tmp/v2t/stylecrawl.py D6alt --skin alt   # alt skin
python /tmp/v2t/stylediff.py D6 D6alt --out /tmp/v2t/shots/stylediff_D6_D6alt.md

python /tmp/v2t/shots.py D6
python /tmp/v2t/shots.py D6alt --skin alt
python /tmp/v2t/shotdiff.py D5 D6                # plumbing diffs only — section 3
```

`shots.py` and `stylecrawl.py` already accept `--skin` (they set
`localStorage.jobnavigator_skin` in an init script), so no tool change is needed for
the skin passes.

---

## 3 · Expected diffs **vs D5** (the plumbing, not the skin)

These are the changes D6 makes at the *default* skin. Anything else in a D5 → D6 diff
is a regression.

1. **Rail theme glyph, every route, dark theme.** The footer ◐ and the collapsed ◐
   now render `◑` in dark and `◒` in system; `◐` stays for light. So every dark shot
   changes by the handful of pixels in that one 13 px glyph, and the crawl key for
   those two elements changes (their key carries the text head) → they appear as
   `missing`+`added` rather than `changed`.
   Their `title` also changes (`Switch to dark mode` → `Theme: Dark — click to switch`);
   titles are not crawled.
2. **`/v2/settings`, both themes, both viewports.** A whole new first section:
   anchor rail gains a `GENERAL` label + an `Appearance` row (and the highlighted
   anchor at rest moves from `Models` to `Appearance`); the pane gains an
   `Appearance` heading and two rows (`Theme` with a 260 px Select, `Skin` with a
   260 px Select). Everything below is pushed down by the height of that block, so
   the Settings shots differ over most of their area and every element below the new
   section gets a new crawl key position. This is a **content** change, not a style
   change: no row's own tuple may differ.
3. **`/v2/ui`.** The header's single `◐ Dark` secondary Button is replaced by two
   Pill groups with `Skin` / `Theme` labels. The gallery is not in the pixel route
   list (`shots.py` covers `/v2/toasts`, not `/v2/ui`) but is crawled by hand during
   D3-style spot checks.
4. **`/v2/toasts`.** The header's `◐ Light` box now reads `◐ Light` / `◑ Dark` /
   `◒ System` and carries a title. Same box, same geometry — only the glyph and the
   label text.
5. **Nothing else.** No screen's rows, cards, modals, fields, pills or headers may
   move. In particular `/v2/feed`, `/v2/searches`, `/v2/companies`,
   `/v2/applications`, `/v2/resumes`, `/v2/resumes/{id}`, `/v2/cover-letters`,
   `/v2/cover-letters/{id}`, `/v2/persona` and `/v2/stats` must be pixel-identical to
   D5 in **light** mode, and differ only in the rail glyph in **dark**.

---

## 4 · The alt palette (for the record)

Cool slate ground, indigo accent, Georgia/Inter system stacks — no webfont is loaded,
so a skin switch costs no request. 57 tokens, declared in **both** alt blocks (they
must carry the identical name set: `[data-skin="alt"]` and `.jn-v2[data-theme="dark"]`
weigh the same, so a token the light skin sets and the dark one forgets would leak a
light colour into the dark skin).

| token | alt light | alt dark | | token | alt light | alt dark |
|---|---|---|---|---|---|---|
| `--bg` | `#f7f8fa` | `#161a21` | | `--stage-applied` | `#1b5f78` | `#8fc3d8` |
| `--surface` | `#ffffff` | `#1d222b` | | `--stage-interview` | `#8f5a10` | `#d3a469` |
| `--surface-2` | `#eef1f6` | `#262c37` | | `--stage-offer` | `#26694c` | `#8fc4a5` |
| `--line` | `#dbe0e9` | `#343b47` | | `--stage-rejected` | `#a33334` | `#e09a92` |
| `--line-soft` | `#e9edf3` | `#232830` | | `--stage-new` | `#c3cad6` | `#454d5b` |
| `--line-strong` | `#c3cad6` | `#454d5b` | | `--series-new` | `#bd8226` | `#a9772a` |
| `--edge` | `#7c8698` | `#737d8f` | | `--amber-bg` | `#fdfaf1` | `#282318` |
| `--track` | `#828c9e` | `#7d8798` | | `--amber-line` | `#d9cca6` | `#483f28` |
| `--text` | `#161a21` | `#d6dae2` | | `--amber-line-soft` | `#eee7d2` | `#372f1e` |
| `--text-2` | `#4b5468` | `#c6cbd5` | | `--amber-hover` | `#f8f3e6` | `#312b1c` |
| `--muted` | `#5f6878` | `#9aa2b0` | | `--sand` | `#c9cfdc` | `#5f6675` |
| `--ink-2` | `#2a3140` | `#ced3dc` | | `--gold` | `#c08b3a` | `#c9a35a` |
| `--accent` | `#3f52a8` | `#9aabee` | | `--funnel-low` | `#8fa0cf` | `#5b6fb8` |
| `--accent-ink` | `#ffffff` | `#12151b` | | `--funnel-mid` | `#5b6fb8` | `#8fa0cf` |
| `--accent-soft` | `#e6e9f7` | `#232a3d` | | `--toast-ok-bg` | `#eaf2ec` | `#1f2c26` |
| `--good` | `#26694c` | `#8fc4a5` | | `--toast-ok-line` | `#8fb59f` | `#3f6b52` |
| `--warn` | `#8f5a10` | `#d3a469` | | `--toast-ok-ink` | `#26694c` | `#8fc4a5` |
| `--warn-soft` | `#f6efe2` | `#2a2318` | | `--toast-bad-bg` | `#faecec` | `#2c1d1c` |
| `--warn-line` | `#c99a55` | `#6a5738` | | `--toast-bad-line` | `#d19a9a` | `#7a3a36` |
| `--bad` | `#a33334` | `#e09a92` | | `--toast-bad-ink` | `#8f2c2d` | `#e09a92` |
| `--bad-soft` | `#f9eaea` | `#2b1b1a` | | `--rail` | `#171a21` | `#0e1116` |
| `--bad-faint` | `#fdf5f5` | `#241a1a` | | `--rail-text` | `#9aa1af` | `#8d94a2` |
| `--change-soft` | `#cfd8f0` | `#334066` | | `--rail-dim` | `#868d9c` | `#828997` |
| `--change-bg` | `#fafbfd` | `#1e2430` | | `--rail-accent` | `#8f9fe0` | `#9aabee` |
| `--hover-soft` | `#f2f5fb` | `#242a35` | | `--rail-line` | `#252932` | `#20242c` |
| `--ring-accent` | `rgba(63,82,168,.22)` | `rgba(154,171,238,.24)` | | `--rail-ink` | `#f2f4f8` | `#f2f4f8` |
| `--scrim` | `rgba(17,20,27,.46)` | `rgba(0,0,0,.58)` | | | | |
| `--recessed` | `#fafbfd` | `#1a1f27` | | | | |

Fonts (both alt blocks, identical):
`--serif: Georgia,'Iowan Old Style','Times New Roman',serif` ·
`--sans: 'Inter','Source Sans 3','Segoe UI',system-ui,sans-serif` ·
`--mono: 'Cascadia Mono',Consolas,'SF Mono',ui-monospace,monospace`.

**Contrast** (measured, on `--surface`; default in brackets):

| | alt light | alt dark |
|---|---|---|
| `--text` | 17.44 (17.41) | 11.39 (10.64) |
| `--text-2` | 7.59 (7.66) | 9.81 (9.09) |
| `--muted` | 5.62 (5.52) | 6.21 (6.17) |
| `--accent` | 7.04 (6.11) | 7.17 (7.11) |
| `--good` / `--warn` / `--bad` | 6.55 / 5.77 / 6.82 | 8.06 / 7.06 / 7.00 |

`--accent` on `--accent-soft` 5.82 light / 6.42 dark; `--accent-ink` on `--accent`
7.04 / 8.21. Rail ink on rail: text 6.71 / 6.20, dim 5.23 / 5.38, accent 6.80 / 8.50
(default: 6.41 / 5.94, 4.88 / 5.08, 7.48 / 8.89). The two chart constraints the
default palette documents also hold: `--series-new` keeps ≥2:1 on `--stage-applied`
(2.16 light / 2.05 dark) and ≥3:1 on `--bg` (3.10 / 4.45).

---

## 5 · Checks already run (source-only)

- `py v2-testing/tools/stylelint.py` → **exit 0**, `0 findings, 109 allowed, 0 css`.
  (The two alt blocks are invisible to `lint_css`'s light/dark parity regex by
  construction — it only matches `.jn-v2 {` and `.jn-v2[data-theme="dark"] {` — and
  the parity of the alt pair was verified separately: 57 names each, symmetric
  difference empty.)
- `esbuild --loader=jsx` parses all eight touched JS/JSX files clean.
- `{}`/`()`/`[]` balance unchanged vs HEAD on all nine touched files; `theme.js`
  balanced.
- `git diff frontend/src/v2/theme.css` removes exactly two lines, both from the file
  header comment — every existing light and dark value is byte-identical.

## 6 · Open / unsure

- **Rebuild required.** Nothing here has been built or screenshotted; the gates in
  §2 and §3 are the D6 verification still to run.
- **`h.py:95 set_theme(pg, theme)`** writes only `jobnavigator_dark_mode` and reloads.
  That no longer switches the theme *within a live context*, because the boot script
  migrates the boolean into `jobnavigator_theme` on the first load and prefers the new
  key afterwards. It is currently **dead code** (defined, never called), and
  `h.py:62`'s `context()` path is unaffected — it seeds localStorage in a fresh
  context, so the migration produces the right mode. If it is ever used, add
  `localStorage.setItem('jobnavigator_theme', theme)` beside it.
- **Dev-server only:** in `vite dev` the theme CSS is injected by JS, so the pre-mount
  ground comes solely from the `<style>` in `index.html` (that is why it is there and
  not in `theme.css`). In the Docker production build the extracted stylesheet is in
  `<head>` and both work.
- **System mode and the crawl.** `stylecrawl.py`/`shots.py` seed `jobnavigator_dark_mode`
  and rely on the migration, so they always land on an explicit `light`/`dark` — the
  `system` branch is never exercised by the automated passes and needs a manual check
  (flip the OS appearance with the app open; the rail glyph stays `◒` and the palette
  follows).
- **`--sans`/`--serif`/`--mono` in the default palette are declared only in the light
  block** (they were always theme-invariant). Both alt blocks declare them, which is
  required by the parity rule in §4 and is why the alt skin's fonts survive a theme
  flip.
- **Settings › General naming.** The task said "Settings › General"; v2's Settings has
  no General group, so the section is `GENERAL` (the anchor-rail group label) ›
  `Appearance` (the section title). Rename if the user prefers the section itself to
  be called "General".
