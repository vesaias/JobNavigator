# Post-pass batch — live verification

Repo `V:\JTrakProject`, branch `v2-redesign`, HEAD `60109599fa873f47c298c33b3e60e213b08ed979` (commit
"Post-pass fixes: menu children never shrink…"), committed 2026-09-04 09:44:28 +0200. Frontend
container confirmed built from exactly this commit — `docker compose ps` shows the `frontend`
service created 2026-09-04 09:44:36 (8s after the commit), unchanged for the full duration of this
pass. Read-only pass: no commits, no builds, no restarts, no source edits, no LLM calls, no data
writes except one intercepted PATCH (item 10). Playwright inside the `backend` container against
`http://caddy`, API key `pick-a-password`, harness `/tmp/v2t/h.py` (pre-existing). Scripts written
locally then `docker compose cp` + `docker compose exec -T backend python /tmp/v2t/<name>.py`.
`DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"; export MSYS_NO_PATHCONV=1`.
Theme/skin set via localStorage `jobnavigator_theme`/`jobnavigator_skin` in the harness's
`extra_ls=` init-script param.

Read first: `v2-testing/round-design/smoke-final.md` ("Post-pass fixes" section, items D-POST-01
through D-POST-14 + DS-S-22 + the three primitive decisions), `v2-testing/round-design/verify-final.md`
(harness method precedent).

**Mid-pass note (does not affect the results below):** a further commit, `e91930c` ("Feed popups
share one inner geometry (+ salary max field), ScoreRing viewBox fixed…"), landed on this branch at
10:05:39 — after this pass had already begun and while the target frontend container (built 09:44:36)
was still running unchanged. Everything measured here is against `6010959` as instructed; `e91930c`
touches the same areas as items 2, 7 and 9 but was never live during this pass and was not tested.
Flagging it so the coordinator knows the tree has already moved past the commit this report covers.

---

## Results

| id | status | measured |
|---|---|---|
| 1. Feed › Company filter menu — inner search field | ✔ | `/v2/feed` → Company filter: `[aria-label="Search companies"]` computed `height: 32px`, `width: 236px` (≥200 required) in **all 4** theme×skin combos, byte-identical. Placeholder reads `"Type to search 1347 companies…"` — the list is fully loaded. Menu box is `maxHeight: 360` (measured `h: 360`) while 80 menu items render (`sorted.slice(0, 80)`, ~30px each ≈ 2400px of content) — well overflowing the box, exactly the condition D-POST-01's fix (`.jn-v2 .v2-menu > * { flex-shrink:0 }`) targets. Confirms `Menu`'s children no longer absorb the flex squash. |
| 2. Feed › Score ≥ and Salary popups — number input padding | ✔ | Both `[aria-label="Minimum score"]` and `[aria-label="Minimum salary in thousands"]`: computed `padding: 0px 9px`, `paddingLeft: 9px`, `paddingRight: 9px` — in **all 4** theme×skin combos, both fields. Matches the canonical `Input` padding; no override found at either site. |
| 3. Feed rows — H-1B verdict span, no "LCA", correct `title` | ✔ (nuance) | **List row** span (`JobFeed.jsx:929`): text `"H-1B Likely"` — no "LCA" anywhere — but this span carries **no `title` attribute at all** (confirmed live: `title: null`); the row-level H-1B span was never wired to `visaTitle` in the source (only the expanded detail header was). **Expanded detail band** span (`JobFeed.jsx:989`, opened via `?job=`): live-measured on two jobs — verdict=`likely`, `h1b_company_lca_count=603` → text `"H-1B Likely"`, `title="Based on 603 H-1B filings"`; verdict=`unknown`, no count → text `"H-1B Unknown"`, `title="No H-1B filings on record"`. Both exactly match the fix's two title strings, and neither text contains "LCA". The task's premise ("Feed rows … its title says…") holds for the **detail band**, not for the bare list row, which the fix (`JobFeed.jsx:701-702, 989`) never touched — that's the code's own scope, not a gap. |
| 4. Searches › New search — `Select` trigger vs `Input` background | ✔ | `/v2/searches` → "+ New search": Mode `Select` trigger vs Name `Input`, computed `backgroundColor`, **all 4 combos, exact match both fields**: light/default `rgb(246,244,238)` / `rgb(246,244,238)`; light/alt `rgb(238,241,246)` / `rgb(238,241,246)`; dark/default `rgb(50,47,36)` / `rgb(50,47,36)`; dark/alt `rgb(38,44,55)` / `rgb(38,44,55)`. Confirms the `Select` trigger now draws on `--input-bg`. |
| 5. Searches editor — auto-scoring Off/Light/Full | ✔ | Same "+ New search" panel, `[role="radiogroup"][aria-label="Auto-scoring depth"]`. **Off centring**: cell rect centre `(321.336, 548.5)` vs the "Off" text glyph's own `Range.getBoundingClientRect()` centre `(321.328, 548.5)` — Δx 0.008px, Δy 0.0px, in **both** light combos and both dark combos (identical numbers all 4 times since the geometry doesn't depend on skin). **Dot colour**: Light cell (selected) dot `backgroundColor` == `--accent`/`--dot-accent` exactly in all 4 combos (`#3f6b52`, `#3f52a8`, `#8dbb9f`, `#9aabee`); Full cell (unselected) dots == `--dot-neutral` exactly (`#6d6862`, `#5f6878`, `#a8a49d`, `#9aa2b0`). Off cell correctly draws **zero** dot spans (`dots: []`). |
| 6. Companies › row ⋯ menu z-index / hit-test | ✔ | `/v2/companies`, 126 rows loaded. **First row**: opened its ⋯ menu, `document.elementFromPoint` at the first menu item's centre resolves to the `<span>` reading "Edit config" **inside** `.v2-menuitem` (`inMenuitem: true`) — not a later row. Its `.v2-cactions` cell reads `zIndex: "28"`, `position: "sticky"` while the menu is open. **Middle row** (index 63 of 126): identical result — `elementFromPoint` → "Edit config" inside the menu, cell `zIndex: 28`. Both confirm D-POST-06's fix. |
| 7. Applications — selected row border/background | ✔ | `/v2/applications`, clicked the first row. `borderLeftWidth: 0px` both before and after selection, in **all 4** combos. Background stayed `var(--row-selected)` in every combo (`#f6f4ee`, `#eef1f6`, `#322f24`, `#262c37`) — no 3px accent bar in any state. Confirmed `--row-hover` and `--row-selected` are **the same token value** in all 4 combos (both resolve to `--surface-2`), exactly as `verify-final.md` already documented — reporting per the task, not treating as a defect. |
| 8. Stats › "Type ▾" menu Escape | ✔ | `/v2/stats` → Activity log tab → opened "Type" menu: `aria-expanded="true"` present before Escape. **1 Escape** → the `[aria-expanded="true"]` menu trigger no longer exists (closed). Matches `useEscape(() => setTypeOpen(false), typeOpen)` (`Stats.jsx:161-164`, DS-S-22). |
| 9. `ScoreRing` numeral centring | ✔ | Measured the **glyph's own text-node `Range` bbox** (not the flex container div, which is always `inset:0` and trivially centred) against the ring box, in light/default, light/alt and dark/alt as specified. Feed row ring (md 44px): Δx ≤0.0px, Δy ≤0.5px (the 0.5px only in the alt skins, from Inter's slightly different glyph metrics). Feed detail-band ring (sm 34px): Δx ≤0.008px, Δy 0.0px, all 3 combos. Résumé-editor score band ring (sm 34px, tailored copy `5b3e2d…`, score 90): Δx ≤0.008px, Δy 0.0px, all 3 combos. All well inside the ≤1px bar. |
| 10. `Segmented` — 4 sites, radiogroup contract | ✔ | All 4 sites: `role="radiogroup"` present, cells `role="radio"`, `aria-checked` correct before and after, ←/→ moves the roving selection, **all cells in a group render the same height**. **Applications stage stepper** (live control, `onStage` calls `PATCH /api/applications/{id}`): intercepted the route (`route.abort()` on PATCH) before pressing →; selection still moved visually (`applied`→`interview`, `aria-checked` flipped 1→2), the network call was aborted (`net::ERR_FAILED` in console, expected/intentional), and no server write occurred. Cell heights `[34,34,34,34]`. **Searches auto-scoring** (New-search panel, local draft state only — no network call until "Create"): cell heights `[31,31,31]`, → moved `Light`→`Full` correctly. **Companies tier control** (add-company modal, local draft state): cell heights `[31,31,31]`, → moved correctly. **Cover Letters length picker** (local `setGenLength` state): cell heights `[31,31,31]`, → moved correctly. |
| 11. `Switch` — Settings toggles | ✔ | `/v2/settings`: 10 `[role="switch"]` elements found. Track (the `aria-hidden` span, not the outer label wrapper — an earlier selector mistake grabbed the wrong span and is not reported): `26px × 15px` on every sample. Knob: `11px × 11px`. An **on** sample's knob `backgroundColor` = `rgb(246,244,238)` = `--surface-2` exactly (read live from `.jn-v2`); an **off** sample's knob is white (`--switch-knob-off`, not part of the check but consistent). `role="switch"` confirmed on all 10. |
| 12. `Check`/`Radio` — Feed select box + Select all | ✔ (nuance) | **"Select all shown"**: `role="checkbox"`, `tabindex="0"`, `aria-checked` `false`→`true` on a single `Space` keypress while focused (toggled back after). **In-menu company row check** (the per-row tick in the Company filter dropdown — the closest analogue to a "row select box" in the Feed, since individual job rows have no visible checkbox of their own and are selected only via ⌘/Ctrl/Shift-click): the tick itself is `role="checkbox"` with `aria-checked`, but by design (`ui.jsx` comment: "the row itself owns the click") it carries no `tabindex` of its own — its parent `.v2-menuitem` (`role="menuitem"`, `tabindex="0"`) is the real keyboard target. Confirmed: focusing the **menu item** and pressing `Space` flips the child checkbox's `aria-checked` `false`→`true` (toggled back after). Both patterns work as coded; no defect. Note for the record: a literal per-job-row `role="checkbox"` element does not exist in the Feed list (`feed_row_checkbox_elements: []` — verified by scanning a live row) — row selection there is indicated only by a plain, role-less ✓ badge on the score ring. |
| 13. `Meter` — Feed bars | ✔ (clarification) | Opened a scored job's report band (`bf69f8a1…`, PM=91 with both `breakdown` and `keyword_coverage_pct`) and expanded both sections. Two distinct `Meter`s exist in the Feed, not one: the **score-breakdown criterion bars** (5 found) render at `height: 1px`, track `#e2ddd0` (= `--meter-track`), fill `#3f6b52` (= `--meter-accent`, default tone) — by design, not 4/6px. The **keyword-coverage bar** ("the report keyword bar") renders at `height: 4px` — matching the task's expected range — `aria-valuenow="78"`, tone resolved to `good` (≥75%), fill `#3f6b52` = `--meter-good` exactly (this palette's `good` and `accent` happen to be the same hex in light/default). Both bars carry `role="meter"` with correct `aria-valuenow`. |
| 14. Toast + `/v2/ui` | ✔ | `/v2/toasts` → HTTP 200, page renders ("Toast lab…"). Fired the real "success" sample (`push({kind:'success', …})`) — live toast card: `bg: rgb(238,245,239)`, `border: rgb(143,174,155)`, `borderWidth: 1px`, `boxShadow` present. Cross-checked against `--toast-ok-bg`/`--toast-ok-line` read from `.jn-v2`: `#eef5ef` / `#8fae9b` — exact match (`rgb(238,245,239)` = `#eef5ef`, `rgb(143,174,155)` = `#8fae9b`). `/v2/ui` → HTTP 200; found all 5 expected `Role name="…"` headings by text (`Check · Radio`, `Switch`, `Segmented`, `Meter`, `ScoreRing`) plus a `ToastCard` role block (confirmed in source, `UiGallery.jsx:383`) whose static `kind="success"` sample ("Saved to the feed") independently reproduces the identical tokens (`rgb(238,245,239)` / `rgb(143,174,155)`). |
| 15. Regression sweep — all v2 routes × 4 combos × 2 widths | ✔ | 13 routes (`/v2/feed`, `/v2/resumes`, `/v2/resumes/{id}`, `/v2/companies`, `/v2/searches`, `/v2/applications`, `/v2/cover-letters`, `/v2/cover-letters/{id}`, `/v2/settings`, `/v2/persona`, `/v2/stats`, `/v2/toasts`, `/v2/ui`) × 4 theme/skin combos × 2 widths (1440, 1024) = 104 loads. **0 console errors, 0 page errors, in every load.** `document.documentElement.scrollWidth <= innerWidth` held in **every** load at both 1440 and 1024 (no horizontal overflow anywhere). The only non-zero signal: 16 `requestfailed` entries, all `net::ERR_ABORTED` on an in-flight PDF preview fetch (`/api/resumes/{id}/pdf…` or `/api/cover-letters/{id}/pdf`) cancelled by the harness's own navigation to the next route 500ms later — a harness timing artifact from visiting the résumé/cover-letter editor then moving on before their live PDF preview finished loading, not a product defect (confirmed: identical 1-per-visit count, same two URLs, across all 8 combos that visit those two routes). |

## Summary

**15 of 15 ✔.** Every item in the task list, and every defect (D-POST-01 through D-POST-07,
DS-S-22) plus the three post-report primitive decisions (D-POST-08 ScoreRing, D-POST-09 lab-page
move, D-POST-10..14 Segmented/Switch/Check-Radio/Meter/ToastCard) documented in
`smoke-final.md`'s "Post-pass fixes" section is confirmed live and working against the built,
running stack at HEAD `6010959`:

- **D-POST-01** (Company filter search field height) — fixed; 32px/236px in all 4 combos, menu genuinely overflowing.
- **D-POST-02** (Score/Salary popup padding) — was already correct per `smoke-final.md`'s own "not reproducible" finding; re-confirmed `0px 9px` in all 4 combos.
- **D-POST-03** (H-1B "N LCAs" text) — fixed in the detail band (verified both title strings live); the plain list row never carried a title to begin with (out of the fix's scope, not a regression).
- **D-POST-04** (Select vs Input background) — fixed; exact background match in all 4 combos.
- **D-POST-05** (Off/Light/Full centring + dot colour) — fixed; sub-pixel centring, dot colours match tokens exactly.
- **D-POST-06** (Companies row menu z-index) — fixed; hit-tests correctly on first and middle rows.
- **D-POST-07** (Applications selected-row border) — fixed; no border, correct wash, in all 4 combos.
- **DS-S-22** (Stats Type menu Escape) — fixed; single Escape closes it.
- **D-POST-08 (ScoreRing), D-POST-10 (Segmented), D-POST-11 (Switch), D-POST-12 (Check/Radio), D-POST-13 (Meter), D-POST-14 (ToastCard)** — all six primitives confirmed live, matching their documented contracts (roles, ARIA states, keyboard behavior, geometry, token-driven colour) across every site tested.
- **D-POST-09** (lab pages moved to `design-base/`, optional routes) — confirmed: `/v2/toasts` and `/v2/ui` both route (200) and are fully functional.
- **Regression sweep** — clean across all 13 routes, all 4 theme/skin combos, both breakpoints.

No P1/P2 defects found. No behavior contradicted `smoke-final.md`'s "Post-pass fixes" section.

## UNEXPECTED

- A newer commit, `e91930c` ("Feed popups share one inner geometry (+ salary max field), ScoreRing
  viewBox fixed…"), landed on `v2-redesign` at 10:05:39 — mid-pass, after this verification had
  already begun against the running `6010959` build. It touches the same surfaces as items 2, 7 and
  9. It was never live during this pass (the frontend container was last built at 09:44:36, before
  the commit existed) and was **not** tested here — flagging only so the coordinator knows the
  working tree has already moved past what this report covers.
- Individual Feed job rows have no `role="checkbox"` element of their own (see item 12) — selection
  is indicated only by a role-less ✓ badge on the score ring, with the actual selection made via
  ⌘/Ctrl/Shift-click on the row. This is consistent with `smoke-final.md`'s own list of migrated
  `Check`/`Radio` sites (which never included a per-row Feed checkbox), so it reads as working as
  designed rather than a gap — noted for the record since the task's phrasing implied one might exist.
- The score-breakdown criterion bars in the Feed report band render at `1px`, not in the `4/6px`
  range the task described (see item 13). Only the keyword-coverage bar matches that range. Also
  working as designed (`JobFeed.jsx:1096`, unchanged by this pass) — noted since it's a real
  divergence from the task's phrasing, not from the source.

## Data / state note

No setting was changed and no record was created, edited, or deleted. The only network mutation
attempted was the Applications stage-stepper PATCH in item 10, which was intercepted with
`route.abort()` before it reached the server — the UI's optimistic local-state update flipped the
visible selection, but the abort is confirmed in the console log and no application record was
touched (not re-verified via a fresh GET since the abort itself is the proof; the route was
`**/api/applications/**` scoped to `PATCH` only, `GET`s continued normally). All other items were
pure reads, client-side draft-state edits never saved (Searches new-search panel, Companies
add-modal, Cover Letters generate panel), or toggles with no backing write (Select-all, in-menu
company check, keyboard nav on local-state Segmented controls).
