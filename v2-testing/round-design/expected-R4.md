# expected-R4 — the default-theme computed-style delta of the round-4 frontend fix loop

Same instrument and same slice as `expected-S5.md`: `tools/stylecrawl.py` records 19
properties per visible element — `backgroundColor, color, borderTopWidth,
borderTopColor, borderBottomColor, borderTopStyle, borderRadius, boxShadow,
fontFamily, fontSize, fontWeight, lineHeight, paddingTop, paddingLeft, height,
letterSpacing, textTransform, opacity, cursor` — at 1440×900, light and dark, over
the 12 crawled routes, keyed by `theme|route|DOM-path-with-classes[|text head]`.

`stylediff.py` joins the two crawls on that key, so this file separates three kinds
of delta:

* **A · property changes** — the same key, a different recorded value. **There is
  exactly one, and it is conditional (win98 only), so at 1440 in the DEFAULT theme
  the expected count of property changes is ZERO.**
* **B · key changes** — the element is unchanged on screen but its key moved,
  because the key embeds the class list and the first text node. These show up as
  paired added/removed keys and are the bulk of this round's diff.
* **C · things the crawl cannot see** — real changes outside the 19 properties, the
  12 routes, or the settled state. Listed so nothing here reads as unexplained.

---

## A · property changes at 1440, default theme

**None expected.**

The one property rule added this round is `[data-theme="win98"]`-scoped:

| change | where | default theme |
|---|---|---|
| `Button` now carries `v2-raised` (`ui.jsx:168-173`) | every `Button`, every variant, enabled and disabled | `.v2-raised` has a rule **only** under `.jn-v2[data-theme="win98"]`, so `border*`, `boxShadow` and `borderRadius` are untouched here — R4-T3-09 |

Three token re-points were checked for value equality and are same-value by
construction:

| site | before | after | base value |
|---|---|---|---|
| `JobFeed.jsx` unscored "Score" chip | `textTransform:'uppercase'` | `textTransform:'var(--label-case)'` | `uppercase` |
| `Stats.jsx` `COL` (LLM-cost head) | `textTransform:'uppercase'` | `var(--label-case)` | `uppercase` |
| `Stats.jsx` `COL` | `letterSpacing:'.11em'` | `var(--label-tracking-strip)` | `.11em` |

New tokens (`--rail-focus`, `--scroll-thumb`, `--scroll-track`) and the new win98
values (`--link-ink`, `--link-ink-hover`, `--scroll-*`, dark `--row-selected`) change
no *recorded* property in the default theme: the first three are read only by the
scrollbar rule and the rail `:focus-visible` rule (neither state is sampled), and the
win98 ones live in a `[data-theme="win98"]` block.

---

## B · key changes (same pixels, new crawl key)

These are expected as **paired added/removed keys**, not as property diffs.

### B1 · every `Button` re-keys — all 12 routes
`Button`'s className goes from `v2-ctl [state] [hover]` to `v2-ctl v2-raised [state]
[hover]`, so every button's path segment changes, e.g.

```
div.v2-ctl.v2-btn-primary|Tailor résumé   →   div.v2-ctl.v2-raised.v2-btn-primary|Tailor résumé
```

This is the single largest source of churn in the diff. The rendered box is
identical (see A). Every `<Button>` on every route is affected, including the
`as="button"` one in `LoginModal` (not crawled).

### B2 · four Settings nav group labels re-key — `/v2/settings`
`Settings.jsx` passed literal upper-case **strings** to `Label`, so `--label-case`
had nothing left to lower-case in win98 (R4-T3-08). The strings are now sentence
case and `Label`'s own `textTransform: var(--label-case)` does the work:

| before (text head) | after |
|---|---|
| `GENERAL` | `General` |
| `PIPELINE` | `Pipeline` |
| `INTEGRATIONS` | `Integrations` |
| `SYSTEM` | `System` |

`AI` is unchanged. In the default theme all five still *render* upper-case.

### B3 · the cover-letter stage badge re-keys — `/v2/cover-letters/{id}`
`CoverLetterEditor.jsx` called `.toUpperCase()` on the stage; it now capitalises
only the first letter, so `DRAFT` → `Draft` (rendered upper-case here). Same
element, same style, new text head.

### B4 · the Applications prep pill's glyph becomes an SVG — `/v2/applications`
`⧉` (U+29C9) has no glyph in the container's font stack and drew an empty box
(R4-T2A-12). The `<span style="font-size:11px">⧉</span>` inside the "Generate prep
handover for AI" pill is replaced by `<CopyGlyph />`:

```
removed:  span|⧉                (inside div.v2-ctl.v2-raised.v2-bd … the prep Pill)
added:    svg   (+ its path and rect children, if they clear the crawl's ≥1×4px filter)
```

The pill's own recorded properties are unchanged. The four other `⧉` sites are
inside modals and menus the crawl never opens (Feed tailor-picker method card,
Searches row menu "Duplicate", the prep modal's "Copy to clipboard", `PromptDialog`'s
"Copy").

### B5 · possible — a cover letter may move band on `/v2/cover-letters`
`isActive` now treats "no stage **and** no job status" as a draft instead of an
archive row (R4-T2B-09). If the live database holds any letter with neither, it
moves from the collapsed *Archived* band into the active list, and that route's
element census changes with it. Zero letters of that shape ⇒ zero diff.

---

## C · changes the crawl cannot see

1. **`.v2-scroll` scrollbars are now theme-aware — the one deliberate VISUAL change
   in the default theme** (R4-T3-02). `.v2-scroll` gains `scrollbar-width: thin` and
   `scrollbar-color: var(--scroll-thumb) var(--scroll-track)`; the `::-webkit-*`
   rules stay and now read the same two tokens. Neither standard property is in the
   crawl's 19, so **`stylediff` will show nothing** — but Chromium ≥ 121 and Firefox
   honour the standard pair and ignore the `-webkit-` pseudos, so a scrolling pane
   draws the native *thin* bar (≈ 11 px, square) instead of the 9 px rounded pill
   with its 2 px `--bg` border. Two consequences to expect in **screenshots**, not in
   the crawl: the bar itself looks different wherever a pane scrolls, and panes with
   `scrollbar-gutter: stable` (`.v2-gutter`, `.v2-gutter-head` — the Stats cost table
   and its head) reserve ~2 px more, so their content is ~2 px narrower. Base token
   values are today's (`--muted` on `transparent`); win98 gets `#808080` on `#c0c0c0`.
2. **Rail focus ring** — new `.jn-v2 .v2-navdark:focus-visible { outline: 2px solid
   var(--rail-focus) }` (R4-T2B-07). Only paints while a rail anchor holds keyboard
   focus; the crawl never focuses anything.
3. **Menu dismiss backdrops** — `Menu` gained an `onDismiss` prop that mounts the
   fixed transparent sheet the Feed's `Drop` already drew, and six menus on
   Searches / Companies / Applications pass it (R4-T2A-05). The sheet exists only
   while a menu is open; the crawl opens none.
4. **Loading and error states** — Applications now reserves its shell (R4-T2A-02);
   Settings and Persona reserve their header (R4-T2B-06); six screens render `—`
   instead of `0` in the count line after a failed load, and `useWarm` no longer
   caches a failed load (R4-T2A-08 / R4-T2B-03). Every one of these is identical in
   the settled, successful frame the crawl samples — verified line by line: the
   hoisted `header` blocks are the same JSX, `countLine`'s success branch is the same
   template string, and `useWarm(…, ok)` with `ok === true` is the old behaviour.
5. **Feed pane widths** — the list column is `flex: 0 1 472px; min-width: 340px` and
   the detail column `flex: 1 0 420px` (R4-T2A-01). At 1440 the two bases sum to 892
   against a 1234 px pane, so there is free space, no shrink runs, and the columns
   are 472 / 762 — exactly today's. `width` and `flex` are not recorded either way.
   The change only bites below ~1100 px, where the list now yields instead of the
   detail.
6. **Behaviour with no paint** — the welcome overlay's first-visit flag
   (R4-T0-02, see the note below), the Feed's dedupe-and-refetch loop
   (R4-T2A-11), the Searches Test-run sessionStorage record (R4-T2A-07), the cover
   letter editor's mount-time `/monitor/active` probe (R4-T2B-02), Settings'
   ResizeObserver callback ref (R4-T2B-01), the rail's "Backend unreachable" state
   (R4-T2A-09), Escape on Applications' add-interview form (R4-T2A-14), and clearing
   the Companies row menu before its delete confirm (R4-T2A-15).
7. **`/v2/toasts`** — the lab page's hand-rolled `<h1>` is now `PageTitle`
   (R4-T3-06). That route is in `shots.py` but not in `stylecrawl.py`'s `ROUTES`, and
   `design-base/` is git-ignored.

### Harness note — the welcome overlay must stay suppressed

R4-T0-02 makes the onboarding overlay appear on a browser profile that has never
recorded a visit. Every Playwright context is exactly that. Two things keep the
crawl and the screenshots clean, and **both must hold or every route gains a modal
and a full-viewport scrim**:

* `App.jsx` treats the two legacy keys the harness already seeds
  (`jobnavigator_v2_welcome_seen`, `jobnavigator_welcome_seen`, either `'true'`) as
  "already welcomed", so **no existing script changes behaviour**;
* `tools/h.py` and `tools/console_sweep.py` now also seed the canonical
  `jobnavigator_welcomed: '1'`.

Any script that builds its own context instead of `h.py`'s `context()` — several of
the round-4 scratch scripts do (`c.py`'s `mkpage()`) — needs one of those three keys
in its `localStorage` seed.
