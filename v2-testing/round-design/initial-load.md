# Initial load — one settle, warm start, reserved boxes

Source-only run: no rebuild, no restart, no commit. Verification is
`py v2-testing/tools/stylelint.py` (exit 0), an `esbuild --loader:.jsx=jsx` parse
of every touched file, and a `{}`/`()`/`[]` balance check against
`git show HEAD:<file>` (HEAD `06d09cf`).

```
stylelint: 0 findings ({}), 98 allowed, 0 css      # exit 0
esbuild   12/12 files parse
braces    12/12 files balanced vs HEAD
```

## The problem

Every screen painted its chrome from empty state and then jumped: a subtitle that
counted `0 bases · 0 tailored copies`, a Voice picker that said "No voice presets
— add them in Settings → AI", a table under a `Loading companies…` row, an
editor band reading "Tailored copy · not scored yet" that rewrote itself twice as
four separate requests landed. Each fetch resolved in its own render, so each one
was a visible step.

The nav rail had already been fixed this way (`V2App.jsx:46-150`): one
`Promise.allSettled`, one `setState`, plus a localStorage snapshot read back
synchronously in the initial state so the badges are there on the first frame.
That is now a pair of shared hooks, and every screen uses them.

## The mechanism (`frontend/src/v2/hooks.js`)

**`useSettled(loaders, key?) → { ready, data }`** — runs the screen's initial
fetches through one `Promise.allSettled` and flips `ready` once, when the last of
them settles. `loaders` is an array of thunks read from a ref, so an inline array
does not re-run them; only a change of `key` does (an editor passes its document
id, a "Try again" link passes a counter). Each thunk keeps doing what it already
did — its own `setState`, its own `catch` — so **every existing error path,
toast and error row is unchanged**; `ready` only decides when the chrome may be
drawn. Readiness is derived during render (`done.key === key`), so a key change
is stale immediately rather than one painted frame later.

No spinner for this first paint, by design: the layout keeps its boxes, so a
spinner would be one more thing that appears and disappears. `Spinner` stays for
explicit long actions (scoring, tailoring, generating, a running test).

**`useWarm(screen, live, ready) → { warm, fade, style }`** — caches the values
that are the same on the frame after a refresh as they were before it, under
`localStorage['jobnavigator_v2_warm:<screen>']`. `warm` is the cached snapshot
until `ready` and the live value after. A value that comes back equal to its
cache causes no render at all; one that differs is written back and fades in over
`.15s` from `.6` — the same two-`requestAnimationFrame` cross-fade the rail
badges use. A first-ever visit has nothing cached, so `warm` is `null` and the
line renders `NBSP` — which keeps its line box, so nothing shifts when the text
lands.

**`NBSP`** (`'\u00A0'`) is the exported placeholder: an empty `<span>` collapses
to zero height, a non-breaking space keeps the box.

## Per screen

| screen | gated on one settle | warm-started | stays instant |
|---|---|---|---|
| `JobFeed.jsx` | `/jobs/companies/list`, `/jobs/sources/list`, `/jobs/verdicts/list`, `/resumes?is_base=true`, `/jobs/feed-stats` (+ the first `/jobs` page, tracked as `firstLoaded`) | subtitle (`N open roles · M arrived today · K not yet scored`), the "Score N unscored jobs" button, the Source and H-1B option lists with their counts | title, search field, every filter pill trigger, Sort, the two panes |
| `Searches.jsx` | `/searches`, `/health/entities` + `/scheduler/jobs` (one `loadAux` promise), `/monitor/active` | subtitle (`N configs · M active · K need attention · next scheduled run in …`; the timestamp is cached, the countdown recomputed at render) | title, `+ New search`, the New-search card |
| `Companies.jsx` | `/companies` + `/health/entities` (one `fetchCompanies` promise), `/resumes`, `/persona`, `/monitor/active` | subtitle (`N tracked · M active · K need attention`) and the four tier pills' counts | title, `+ Add company`, search box, tier pill labels, Sort, the table head |
| `Applications.jsx` | `/applications` — **already correct**: it held the whole screen back behind its one request and rendered an empty pane, never a spinner. Converted to `useSettled` for uniformity, no behaviour change | — (nothing is drawn before the settle, so there is nothing to warm) | — |
| `Resumes.jsx` | `/resumes/shelf` | subtitle (`N bases · M tailored copies … · K archived`) | title, search field, `+ New résumé` |
| `ResumeEditor.jsx` | **`tplReady`**: `/resumes/templates`. **`ctxReady`** (keyed on the document id): parent `/resumes/{parent}` or the base's copy count, `/jobs/{id}` + `/cover-letters?job_id=`, `/resumes/{id}/tracer-stats` | — | top bar, section list, the preview pane and its iframe box, Download PDF |
| `CoverLetters.jsx` | `/cover-letters`, `/resumes`, `/persona`, `/jobs?status=saved,applied`, `/settings` (voice presets) | subtitle (`N letters · M live applications`) | title, search, the Generate panel's labels, résumé/job pickers, Length |
| `CoverLetterEditor.jsx` | **`metaReady`**: `/cover-letters/templates`, `/resumes`, `/persona`, `/settings`; the document itself already gates the screen | — | top bar, context band, the three editor cards, the preview pane and its iframe box, Download PDF |
| `Persona.jsx` | `/persona` | — (nothing is drawn before the settle) | — |
| `Stats.jsx` | `loadCore` (7 requests incl. `/health/entities` and the last sweep), `loadLive`, `/stats/llm-costs` | subtitle (last sweep · sources needing attention · LLM spend; the sweep timestamp is cached, "3h ago" recomputed at render) | the header itself — title, subtitle line and Refresh now render before the cards |
| `Settings.jsx` | `/settings` + `/settings/defaults` (one `load` promise), `/resumes`, `/persona`, `/linkedin/session` | — | — (the rows pane is one block; it keeps its box and draws once) |

### What was gated, in detail

- **JobFeed** — the header line and the unscored button read from the warm
  snapshot; `{jobs.length} shown · {total} matching` keeps its box until the
  first page answers. The list's `Loading…` line is suppressed on the **first**
  paint only: a later reload is a filter change, an explicit action, and keeps
  its line.
- **Searches** — the `Loading searches…` spinner row is gone; the scroller keeps
  its box and the cards draw once, with their amber warning edges already on.
  Empty-state and error rows now key off `ready`, so neither can flash before the
  first response. "Try again" bumps a reload key rather than re-entering a
  `loading` flag.
- **Companies** — same treatment for `Loading companies…`; the tier pills are
  their final width on the first frame because the count comes from the warm
  snapshot. The bulk "Make N active/inactive" buttons appear with everything
  else, in one render.
- **Résumés** — the shelf's `Loading…` line is gone; the scroll container is
  `flex: 1` and simply stays empty, so the error band or the shelf appears in one
  render.
- **Résumé editor** — the copy band's two lines both keep their boxes
  (`18px` and the `Helper`'s own) while the four context requests are in flight,
  so the band is at its final height from the first frame: the fit ring, "Tailored
  for …", the "based on ‹base› ↗" link with its delta, the status line **with its
  ` · tracers: …` tail**, and the one next-step button all appear together. The
  base band's copy count is part of the same settle. The Template/Paper triggers
  wait for the template list, so the Template trigger never paints a raw
  template id and renames itself.
- **Cover-letter editor** — the preview toolbar's Template and Paper triggers
  wait for the template list; the toolbar row's height is the Download button's,
  so nothing moves when they land, and the preview iframe keeps its box
  throughout. The Regenerate modal's Voice row reserves a pill's height.
- **Cover Letters** — the Voice row reserves `26px` (a `sm` Pill) so the panel
  below it does not shift; "No voice presets — add them in Settings → AI" is a
  verdict and may only be drawn once `/settings` has answered. The "All letters"
  pane keeps its container and its contents wait for the settle.
- **Stats** — the whole page used to be replaced by a centred `Loading…`. The
  header is real chrome, so it is drawn at once (warm-started where there is a
  cache) and only the cards wait. `/stats/llm-costs` joined the settle, so the
  header line no longer grows a ` · $x on LLM calls` tail after the fact; a later
  period change is an explicit action and still reloads on its own.
- **Settings** — the rows pane waits for the settings blob *and* the three lists
  that fill pickers on top of it, so the Default-résumé picker and the LinkedIn
  row are never filled in after the rows are already on screen. The failure
  branch (SET-06) is untouched; only the `Loading settings…` spinner is gone.

### Kept as they were

- Every `catch` — error rows, error bands, error toasts, `loadErr` state, the
  `Try again` affordances (now re-arming the settle through a reload key where
  they used to re-enter a `loading` flag).
- `window.dispatchEvent(new CustomEvent('jn:counts-changed'))` after every
  create/delete, and the refreshes it drives.
- All polling (`/monitor/active`, the Stats live poll, the Feed's in-flight
  watcher): these run after the settle and update in place, and a reconciled warm
  value cross-fades rather than swapping hard.
- `Spinner` on explicit long actions: scoring, tailoring, generating, running or
  testing a search or a company, the PDF re-render.

## Expected first paint

**(a) First visit — no cache.** The frame, the rail, the page title and every
static control are there immediately. Data-dependent text is blank but its box is
reserved: the subtitle line holds its 20px line box, the toolbar its height, the
table and list their containers, the preview its iframe box. Nothing moves. When
the settle lands (one render), the counts, rows, pills and bands all appear at
once. No fade — there is nothing to cross-fade from.

**(b) Revisit — cache warm.** The subtitle counts, the Companies tier counts, the
Feed's unscored button and its Source/H-1B option lists, and the Stats header line
are **already correct on the first frame**, read straight out of
`jobnavigator_v2_warm:<screen>`. The lists and tables still wait for their settle
(they are not cached), but the header no longer changes when it arrives: if the
numbers match the cache there is no render at all, and if they differ the changed
text dips to `.6` and fades back over `.15s`, exactly like a rail badge. Relative
times ("next scheduled run in 12m", "Last sweep 3h ago") are recomputed at render
from the cached timestamp, so a warm start never shows a frozen clock.

## Files

`frontend/src/v2/hooks.js` (the two hooks + `NBSP`), and
`JobFeed.jsx`, `Searches.jsx`, `Companies.jsx`, `Applications.jsx`,
`Resumes.jsx`, `ResumeEditor.jsx`, `CoverLetters.jsx`, `CoverLetterEditor.jsx`,
`Persona.jsx`, `Stats.jsx`, `Settings.jsx`.

**Status**: fixed — source-only; needs a `frontend` rebuild to be seen.
