# Reconcile S0 → S1 (design pixel + computed-style diff)

S0 = `3e6a653`. S1 = working tree = `3e97008` (Settings subtitles/help-line copy) + uncommitted
`frontend/src/v2/theme.css` (skins step 1: ~62 new semantic tokens for cobalt/saas/win98, plus a
handful of new hover/state rules gated to classes/attributes ui.jsx does not write yet). DB not
frozen between captures, so feed order/ages/stats counts can drift; tool clock is frozen.

Source data: `v2-testing/artifacts/design/diff_S0_S1/summary.json`,
`v2-testing/artifacts/design/stylediff_S0_S1.md`, cropped regions of the per-route diff PNGs
(`v2_settings`, `v2_searches`, `v2_stats`, `v2_resumes_db3ad036-...` at `light`/`dark` × `1440`),
and `git diff 3e6a653 -- frontend/src/v2/theme.css`.

## Table

| Route | Element | Class | Evidence |
|---|---|---|---|
| `/v2/settings` (light+dark, 1024+1440) | Appearance section header subtitle, Models section header subtitle, Telegram/Rewrite-links/Stripped-params field help text | (a) expected | Diff crop shows exactly the "theme and skin — remembered in this browser, not in the database" and "each prompt can use its own model if needed" strings as the only changed pixels; `git show 3e97008 --stat` touches only `Settings.jsx`, 18 insertions/18 deletions, commit message "section header subtitles removed … tracked-links, dedup and digest facts moved into field help" — matches task description verbatim. |
| `/v2/settings` (light+dark) | scroll container height 5091px → 5123px (+32px) | (a) expected | Net of 15 removed subtitle lines (shrink) and 3 lengthened help lines wrapping to an extra line (grow); same commit as above, no theme.css geometry token (`--radius-*`, `--t-*`, line-height) touches any Settings-reachable rule. |
| `/v2/searches` (light+dark) | one search card: warning border removed, "Acknowledge" button gone, run-status text changed ("A string literal cannot …" → different message, timestamp → "just now") | (b) data drift | Diff-marked region is a single `.v2-card.v2-bd-warn` (S0) becoming a plain `.v2-card` (S1) at the same list slot — a scrape/log event resolved between captures (DB not frozen). `v2-bd-warn` is a pre-existing conditional class, not touched by theme.css. |
| `/v2/stats` (light+dark) | Applications / scored-jobs / stage counts (3,578→3,581, 1354→1357, 748→751, 500→503, etc.), bar heights (135X, 943/953), best-open-score bar height 106→105px, its inner bar 68→67px | (b) data drift | All changed spans are numeric values that incremented by a small constant (2–3) between captures — live counters, not styling. The 1px height deltas on the score bars are the pixel-rounding consequence of the new digit widths inside a flex/measured bar, not a token change (no bar/meter rule appears in the theme.css diff). |
| `/v2/feed` (light) | row order swap (Product Manager/Meta ⇄ Product Manager-Electro/Nomura), fold-body score spans (65→72, 10→7), one `div.v2-hover-accent` hover-state color swapping between the two rows | (b) data drift | `summary.json` missing/added lists show the two rows' full content (title/company/salary/location) swapped position — a re-sort (new job scraped, or re-scored) between captures; the hover-color "change" is the same pre-existing hover rule now sampled on different row content at that DOM slot, not a new rule (not present in theme.css diff). |
| `/v2/resumes/db3ad036-…` — Experience bullet list, both themes | bullet div at `…div:1>div:1` (was 1st bullet "ZZV Verify Freeform JD…", 37px, `--surface`/`--line`) removed; every following bullet shifts up one slot; container heights shrink by 45px at each ancestor (1393→1348, 1353→1308, 1334→1289, 1189→1144, 1151→1106); bullet count badge 7→6; new top bullet ("Identified critical end-to-end…") now shows `--change-bg`/`--change-soft` styling (green tint) plus a `↩` revert icon | (b) data drift, confirmed not a style change | The "ZZV Verify Freeform JD…" placeholder/test bullet (plain, untailored) is gone in S1 — one fewer bullet, and everything below it shifted up by exactly one row. The color pair on the shifted-in bullet is an exact match to existing tokens: light `rgb(253,252,249)`/`rgb(214,232,220)` = `--change-bg:#fdfcf9` / `--change-soft:#d6e8dc` (theme.css:16, untouched by the diff); dark `rgb(33,42,36)`/`rgb(51,80,63)` = `--change-bg:#212a24` / `--change-soft:#33503f` (theme.css:256, also untouched). `ResumeSections.jsx:278/290/319` already conditionally applies `--change-bg`/`--change-soft` vs `--surface`/`--line` per-bullet based on whether the bullet is tailoring-changed — this is pre-existing logic, not new markup or new CSS. The bullet simply moved from an untailored slot into a tailored one because the row above it disappeared. |
| theme.css (all skins) | ~62 new tokens on cobalt/saas/win98 `[data-skin=...]` blocks + `data-theme="dark"` twins; new hover/active rules for `.v2-btn-primary`, `.v2-btn-danger`, `[aria-invalid]`, `.v2-row[aria-current]`, `.v2-raised`/`.v2-inset` | verified INERT for default skin | `git diff 3e6a653 -- frontend/src/v2/theme.css`: every new block is scoped under `[data-skin="cobalt"/"saas"/"win98"]` or is a state rule on classes/attributes ui.jsx does not yet write (`v2-btn-primary`, `v2-btn-danger`, `v2-raised`, `v2-inset`, `aria-invalid`, `data-invalid`) or resolves, for the default skin, to the exact paint already applied inline (`--row-selected` = what Row/Feed already set; `--focus-outline:none` + `--focus-shadow:0 0 0 2px var(--focus-ring)` reproduces the old hardcoded focus rule byte-for-byte). No default-skin selector, token value, or rule changed — matches the diff summary's "no changed default-skin element" result and the file's own header comment confirming this staging. |

## Verdict

No regressions. Every changed pixel/computed-style tuple across the five inspected routes
(Settings, Searches, Stats, Résumé editor, and the Feed swap called out in the style diff) traces
to either the expected commit `3e97008` (Settings copy/height) or unfrozen-DB data drift (search
warning cleared, stats counters incremented, feed row reorder/rescoring, one résumé bullet
deleted). The `theme.css` skins-step-1 addition was independently confirmed inert for the default
skin: all new tokens are skin-scoped or gate rules on markup/attributes the primitives don't emit
yet, and the two rules that could touch default-skin elements (`[tabindex="0"]:focus-visible`,
`.v2-row[aria-current]`) resolve to the same paint the old hardcoded rule / inline style already
produced.

Regression list: **empty.**
