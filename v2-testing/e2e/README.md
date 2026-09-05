# v2 e2e suite

A repeatable, one-command version of the round-3 / round-design Playwright smoke
run and flows A/B, plus five new cases that pin behaviour those passes only ever
checked by hand.

```bash
bash v2-testing/e2e/run.sh            # every case
bash v2-testing/e2e/run.sh modals     # only cases whose name contains "modals"
bash v2-testing/e2e/run.sh flows      # the whole flows group
JN_E2E_LIVE=1 bash v2-testing/e2e/run.sh flows-company-crud
```

`run.sh` copies `v2-testing/tools/h.py` plus every `.py` in this folder into
`/tmp/v2e` inside the backend container (which already has Playwright and a
browser) and runs `main.py` there against `http://caddy`. It exits non-zero if
any case fails. The optional argument is a substring filter on the case name.

Output ends with a per-case table and one summary line:

```
E2E: 13 cases · 11 passed · 0 failed · 2 skipped · 118s
```

## Cases

| case | what it covers | writes? |
|---|---|---|
| `smoke` | every v2 route at 1440×900 and 1024×700: heading, 0 console errors, 0 pageerrors, no horizontal overflow, rail counts within ~1.2 s, health dot | read-only |
| `smoke-error-state` | a stubbed 500 on each screen's own list endpoint renders a visible, non-blank error state with no pageerror | route-mocked |
| `theme` | the `theme.js` storage migration in a real browser: legacy `jobnavigator_dark_mode` → `jobnavigator_appearance`; `jobnavigator_skin` → `jobnavigator_theme` (old key removed); a light\|dark value parked in `jobnavigator_theme` moves to appearance while the skin still wins the palette; an unknown palette falls back to `default`; the modern keys are honoured and mirrored onto `.jn-v2` | localStorage only |
| `cron` | Settings' cron helper: eleven expressions from the checked table at the bottom of `frontend/src/v2/time.js`, read live from the field without ever saving, then the setting is re-read from the API to prove it is untouched | read-only |
| `welcome` | the first-run overlay: a profile with no welcome mark sees it, dismissal writes `jobnavigator_welcomed`, a second load does not replay it, a legacy mark also suppresses it, and Escape closes it (checked over both the Feed and Stats) | localStorage only |
| `persona-import` | the Persona import path with `POST /api/persona/import` **and** the modal's résumé list route-mocked: the parsed result renders, the success toast names the counts, the real POST never leaves the browser, and the persona row is re-read afterwards to prove it | route-mocked |
| `feed-collapse` | the Feed's analysis fold (`jn_feed_analysis_collapsed`) survives a reload and toggles back | localStorage only |
| `modals` | six overlays — Feed keyboard shortcuts, Feed Source menu, Companies Add-company modal, Searches row ⋯ menu, Résumés New-résumé modal, Settings Model-catalog modal — each opens, closes on Escape, and closes on an outside/scrim click | opens only, submits nothing |
| `flows-search-crud` | `POST` → read the JSON shape back → `PATCH` → `DELETE` on a `ZZE` search | creates + deletes its own row |
| `flows-monitor` | the `/monitor/active`, `/monitor/history` and `/monitor/in-flight` shapes the spinners poll on | read-only |
| `flows-pause-pill` | the status pill's Pause/Resume contract, with the `PATCH` route-mocked so nothing is written; afterwards every other search's `active` flag is re-read to prove none moved | creates + deletes its own row |
| `flows-confirm-delete` | the ⋯ menu → `ConfirmDialog` (not `window.confirm`) → Escape cancels → confirming deletes → the rail badge agrees with the API again (`jn:counts-changed`) | creates + deletes its own row |
| `flows-undo-toast` | removing a résumé section raises an undo toast, and Undo restores it both on screen and in the autosaved `json_data` | creates + deletes its own row |
| `flows-company-crud` | **JN_E2E_LIVE only** — company create/read/patch/delete | creates + deletes its own row |
| `flows-live-run` | **JN_E2E_LIVE only** — a real test scrape and a real search run, tracked through `/monitor/active` by scope key | creates + deletes its own row |
| `flows-sweep` | asserts no `ZZE` row survived the run, anywhere | read-only |

## Safety rules this suite follows

- **Every row it creates is prefixed `ZZE` and deleted again in the same case.**
  `flows-sweep` fails the run if one survives. Nothing that was not created by
  the suite is ever deleted or modified.
- **Destructive UI actions are guarded twice.** A row's control is located only
  through `_common.row_index()`, which refuses to return an index unless the
  ancestor it settled on mentions our `ZZE` marker and no other row's name; and
  before a confirm dialog is accepted, its own text must name our row. A naive
  "walk up until an ancestor mentions the name" lookup once landed on the whole
  list and deleted a real user search — hence both guards.
- **Nothing that costs money or scrapes runs by default.** Searches are created
  with `active: false` and `auto_scoring_depth: 'off'`, the scratch résumé is
  created with `is_base: false` so it can never be scored against a job someone
  else saves mid-run, and any endpoint that calls out is either route-mocked or
  behind `JN_E2E_LIVE`.
- **Prefer route mocks to writes.** `persona-import`, `flows-pause-pill`,
  `smoke-error-state` and the Model-catalog modal all answer the browser's own
  requests instead of letting them reach the backend.

## `JN_E2E_LIVE=1`

Off by default; those cases report `SKIP (needs JN_E2E_LIVE=1)`. Setting it to
`1` unlocks exactly two cases:

- **`flows-company-crud`** — `POST /api/companies` ignores any `active` value and
  stores `active=True`, then fires a background MyVisaJobs H-1B lookup: a real
  outbound request, and a row the scheduler would consider live.
- **`flows-live-run`** — runs a real JobSpy test preview and a real search run
  against live job boards, and waits for them on `/monitor/active`.

Both still create only `ZZE` rows and delete them again.

## Environment

| var | default | meaning |
|---|---|---|
| `JN_KEY` | `pick-a-password` | dashboard API key (`X-API-Key`) |
| `JN_BASE` | `http://caddy` | base URL as seen from inside the container |
| `JN_E2E_LIVE` | unset | `1` unlocks the two live cases above |
| `JN_BACKEND` | `jtrakproject-backend-1` | backend container name |
| `DOCKER` | Docker Desktop's `docker.exe` | docker binary |

## Files

- `run.sh` — the one command; copies files in and runs them
- `main.py` — imports every case module (import order is run order) and exits with
  the runner's status
- `_suite.py` — `case()` registration, per-case try/except, `check()`/`eq()`/`skip()`,
  the per-case table and the summary line
- `_common.py` — browser contexts that speak the current storage keys, the page
  probes (overflow, rail, console, overlays), `row_index()`, and the `ZZE` bookkeeping
- `case_*.py` — one file per group

`h.py` is **not** modified: it seeds the legacy `jobnavigator_dark_mode` key, so
`_common.mpage()` / `seeded_page()` set `jobnavigator_appearance` +
`jobnavigator_theme` through `extra_ls` instead. Use `seeded_page()` (not
`mpage()`) in any case that reloads — `h.context()`'s init script re-seeds on
every navigation and would mask what the app itself wrote.
