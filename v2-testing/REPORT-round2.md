# v2 verification — round 2 REPORT

Branch `v2-redesign`, 2026-09-03 → 2026-09-04. Stages and resume boxes: `ROUND2-PLAN.md`. Detail files: `round2/audit.md` (R1), `round2/smoke.md` (R2), `round2/happy-path.md` (R3), `round2/text-candidates.md` (R4), `round2/text-suggestions.md` (R4b). Round-1 totals live in `REPORT.md` (regenerated: 278 findings · 229 fixed · 43 decided/closed · 6 need a decision · 0 logged-only).

## What ran

| Stage | Model | Scope | Result |
|---|---|---|---|
| R1 audit | Opus | 289 statuses reconciled against HEAD; every `fixed` checked in code | 190 verified in code, 36 narrative-only (re-observed by R2), **1 false fixed** (COMP-11), 5 mis-scored statuses corrected, report classifier gained a decided/closed bucket, SET-28 filed, 3 missed defects filed |
| R2 smoke | Sonnet | 23 routes (13 v2 + 9 v1) × 2 themes × 2 viewports; load, console, controls, overflow, deep links, stubbed 500, Escape, Tab | **0 console/page errors** on normal load everywhere; every v2 screen shows an error state on a 500; 6 issues (1 P2, in v1) |
| R3 happy path | Opus | 10 end-to-end flows on the real DB, real LLM (Sonnet) | **10/10 pass**; 9 of 20 LLM calls used; 15 findings (5 P2); 0 `ZZTEST` rows left; DB restored from `backups/round2_baseline_20260903.dump` afterwards |
| R4 / R4b text | Opus → Fable | 1 235 UI strings scanned, 156 flagged | plain rewrites for all 156 + 14 vocabulary decisions; **nothing applied** |

## Open items — need your decision

### P2 (6)
| id | where | what | suggested fix |
|---|---|---|---|
| **COMP-11** | Companies.jsx:425 | Alias badge under-reports by one; a one-alias company shows no badge. Was scored fixed in round 1 — it is not. | `aliases.length > 0` → `+{aliases.length}` (one line) |
| **R2-H-02** | backend manual company scrape | Manual scrape writes no `ScrapeLog` row, so `/scrape-log`, `is_warning` and `/health/entities` never see manual runs | write the ScrapeLog row in `scrape_single_career_page()` or in the trigger |
| **R2-H-05** | JobFeed undo after Applied | Undo restores the job but leaves the auto-created Application and Company | undo deletes the application it created (and the company if it created it and it has no other rows) |
| **R2-H-07** | Applications Log modal | URL reader overwrites a title/company typed while the fetch is in flight | only fill fields that are still empty when the response lands |
| **R2-H-15** | cover-letter LLM logging | Calls logged as `claude_api / claude-sonnet-4-6` while dispatch used `claude_code / claude-sonnet-5`; cost report prices a model that never ran | make the log use the same provider/model resolution as dispatch |
| **R2-S-04** | v1 `components/Persona.jsx:92` | No try/catch on `GET /persona`; failed load throws an unhandled page error | wrap and show the v1 error banner |

### P3 (10)
| id | what | suggested |
|---|---|---|
| COMP-26 | Test scrape has no in-progress overlay; result table renders every row | spinner + "Testing…", block a second click, cap table at 100 rows with show-more |
| R2-A-01 / R2-H-08 | 6 native `window.confirm` sites remain (delete application, discard dirty log, ignore company everywhere, delete search, rotate webhook, remove catalog model) while Companies/Résumés/Cover Letters use `ConfirmDialog` | convert the six, or record that native confirms are acceptable there |
| R2-H-03 | Add-company defaults auto-scoring to Light, New-search defaults to Off | pick one default |
| R2-H-06 | Feed auto-opens row 0's detail and iframes the third-party posting on every visit | open nothing until the user picks a row, or keep (deliberate?) |
| R2-H-09 | A job-linked tailor silently spends a second LLM call (auto-chain score at Full depth) with no UI mention or setting | show it in the tailor modal ("also scores the copy · 1 more call") and/or expose the depth setting |
| R2-H-14 | Regenerate modal shows "Select a source…" for a letter written from a tailored copy | preselect the copy |
| R2-S-01 | Companies row ⋯ sits past the viewport at 1024 px inside a scrollable container | pin the actions column, or accept (narrow viewports unsupported) |
| R2-S-05 | 8 of 9 v1 screens show no visible error on a failed data GET | v1 backlog, or ignore since v2 replaces them |
| SET-28 | `POST /settings` accepts unknown keys | reject with 400, or keep |
| R2-A-02 | Searches' numeric fields have no clamping (max_pages 0 → 50 silently; "20–500" label enforces nothing) | reuse the COMP-12 clamp + `min`/`max` on the inputs |

### P4 (12)
APPS-20 selected = hovered row colour · CL-28 sticky editor error line · RES-32 half-pixel centred modals · R2-A-03 48 silent `.catch(() => {})` (tag each `// silent: reason` or convert) · R2-H-01 test-modal filter reasons tooltip-only · R2-H-04 Companies "+N" counts filter-rejected postings · R2-H-10 freeform copy's "based on" link shows itself · R2-H-11 freeform completion toast not observed (low confidence, retry once) · R2-H-12 autofill `max_chars` is a soft ceiling (346 for 300) · R2-H-13 Run-history RESULT empty except company scrapes · R2-S-02 Résumé editor overflows 3 px at 1024 (an unstyled `<a>`) · R2-S-03 three v1 screens overflow at 1024 · R2-S-06 Résumé/Cover-letter editors have no h1/h2.

### Not verified
- Adding a Q&A pair through the Persona UI: the row renders and fills but the bank stayed at 18 in the harness; the same write path works via the API and via autofill "save to bank". One manual click-through decides whether to file it.

## Considerations (not defects)
1. **Two prompt/model fallback chains** exist (dispatch vs logging, R2-H-15). Worth one shared resolver so cost, logs and dispatch can never disagree again.
2. **Round-1 statuses were scored by first words.** The audit found the counts systematically flattering (53 decided items printed as "logged only") and one false "fixed". The classifier is corrected; future status lines should start with `fixed`, `decided`, `closed` or `needs decision`.
3. **Native confirms vs `ConfirmDialog`** is now the only inconsistency of its kind left in v2 (six sites). Cheap to finish.
4. **Silent catches**: 48 sites. Most are deliberate (pollers, auxiliary counts). Tagging them once makes the number assertable.
5. **LLM spend visibility**: the tailor's hidden second call (R2-H-09) and the soft `max_chars` (R2-H-12) both spend tokens the user did not ask for.
6. **v1 shell** is untouched by rounds 1–2 except for backend regressions; three of its screens overflow at 1024 and most have no error state. Fine if v2 replaces it; otherwise a small pass.

## Text — plain-language suggestions
`round2/text-suggestions.md`: 156 strings with rewrites, grouped per screen, plus §0 with 14 vocabulary decisions that settle ~40 rows at once (sweep → scrape run · land → appear/applied · live in → is in · draw from → use · tracers → tracked links · slug → id · dry run → preview run · JD → job description · pipeline → the app · LCA → H-1B filings · four names for the prep export → prep pack · "The Feed" vs "Jobs" · quick-scored → Light). No hedging filler was found anywhere; the real problem is internal vocabulary (87 `unclear`) and long Settings tooltips (36 `long`). Approve per line or per section and an Opus agent applies them.

## Data
- Baseline `backups/round2_baseline_20260903.dump` taken before R1 and **restored after R3**; counts after restore match the baseline (see the R5 log in `ROUND2-PLAN.md`).
- R3 created and deleted its own rows (final sweep 0 `ZZTEST`); two harness slips (a `scrape_interval_minutes=240` left mid-script, an accidental blank experience row on Persona) were reverted in-flow and are moot after the restore.
- 9 real LLM calls, all on `claude-sonnet-5` via the Claude Code provider.

## Nothing pushed. All commits bare, on `v2-redesign`.
