# v2 verification — consolidated OPEN items (rounds 1–3)

**Date** 2026-09-04 · **Branch** `v2-redesign` · **HEAD** `373c042` ("v2 testing: R3-A-03 and R3-A-06 re-verified live")

**Scope.** Everything still open after the three verification rounds, reconciled from `REPORT.md` + `FINDINGS.md` + `PLAN.md` + `DECISIONS-design.md` + `P3-P4.md` + `stage3/*` + `stage4/*` + `stage5/*` + `inventory/*` (round 1), `REPORT-round2.md` + `ROUND2-PLAN.md` + `round2/{audit,smoke,happy-path,verify}.md` (round 2), and `REPORT-final.md` + `ROUND3-PLAN.md` + `round3/{smoke,flows-A,flows-B,user-notes,verify,verify-final}.md` (round 3), plus a code check at HEAD for the items whose fix scope was recorded only in a commit. **The plain-language text work (`round2/text-candidates.md`, `round2/text-suggestions.md`, 156 strings) is excluded by request and tracked separately.**

**Reconciliation result.** Every numbered finding across the three rounds now carries a `fixed` / `decided` / `closed` / `ignored` status, and every `fixed` has a recorded live verification (round 1: `stage3/REVERIFY.md`; round 2: `round2/verify.md` 22/23 plus the RES-32 re-fix; round 3: `round3/verify.md` 14/14 and `round3/verify-final.md` 8/10, with R3-A-03 and R3-A-06 re-fixed and re-verified at HEAD). **No filed finding is open.** What follows is therefore everything recorded as a *note*, *residue*, *partial fix*, *known limit*, *observation never filed*, or *verification / worksheet debt* that was never closed by a decision.

---

## 1. Open items

### P1 — none
### P2 — none

### P3 (1)

| id | screen / area | what | why open | proposed fix | source |
|---|---|---|---|---|---|
| **OPEN-01** | Backend · settings | The backend accepts any value for every enum / int / cron settings key — no server-side validation. A non-numeric interval is written happily and then raises at `configure_scheduler()`, i.e. the backend cannot start. SET-27 added the client-side digit filter and cron guard only. | partial (client half fixed, server half never was) | Validate by key type in `PATCH /settings` (int / cron / enum) and reject with 400, the way the unknown-key guard (SET-28) already does. | `stage4/settings-roundtrip.md:24`; `stage3/settings.md` "Couldn't test" (SET-27 verified by reading only) |

### P4 (4)

| id | screen / area | what | why open | proposed fix | source |
|---|---|---|---|---|---|
| **OPEN-02** | v2 modals · `useSnapTop` | The RES-32 re-fix (`translateY` snap) is wired into 8 modals (Companies ×2, ConfirmDialog ×2, CoverLetterEditor, ResumeEditor ×3, Resumes) but **not** into Applications' Log and Prep modals, the Feed's copy/tailor picker and rescore modals, `WelcomeModal` or `LoginModal` — all flex-centred `position:fixed` panels, the exact shape the bug lives in. | partial | Add `useSnapTop(panel)` at the six remaining centred panels. | `round2/verify.md` item 19 + `round3/verify.md` item 14 (RES-32); code at HEAD: `Applications.jsx:674,764`, `JobFeed.jsx:1180,1240`, `WelcomeModal.jsx`, `LoginModal.jsx` (no import) |
| **OPEN-03** | Search runs · run summary | On the R3-A-02 re-verification the Indeed run stored **8** rows while the run summary and ScrapeLog both read `6 seen, +6 new`. Explicitly recorded as "an accounting nuance in the run-summary count … not investigated further". | logged, not investigated | Trace the seen/new counters in `sources/jobspy.py` against the rows actually committed. | `round3/verify.md` item 2 |
| **OPEN-04** | Applications · URL reader | The R3-A-05 fix returns the real employer, but the LinkedIn path still returns a title carrying a raw HTML ampersand entity. Recorded as "minor, out of scope … not touched". | logged (deliberately outside that fix's scope) | `html.unescape()` the extracted title in `extract_posting`. | `round3/verify.md` item 3 |
| **OPEN-05** | v2 · silent `.catch` | R2-A-03 was closed by **tagging** 45 sites with a `silent:` comment and converting 4 — none of the tagged ones became user-visible. The APPS-01 residue (the Log modal's `GET /resumes` chip list) is one of them and was already called out as having no id of its own. | partial by design | Re-read the 45 reasons once and convert any a user would want to see (the Log-modal résumé list is the named candidate). | `round2/audit.md` §(b) "APPS-01 residue" + §(d) R2-A-03; `round2/verify.md` item 23; `REPORT-final.md` consideration 6 |

### Unclassified (17)

Recorded as notes / observations / decisions-in-passing; no severity was ever assigned.

| id | screen / area | what | why open | proposed fix | source |
|---|---|---|---|---|---|
| **OPEN-06** | Stats · total-failure state | STAT-03's triage listed the funnel, the 30-day chart **and the Schedules card** as still drawing an empty-but-plausible shape on total backend failure. The shipped fix covers the header banner, the funnel and the 30-day card; the Schedules card is not mentioned. | partial | Give the Schedules card the same "Unavailable — the request failed" branch. | `stage3/persona-stats.md:369` (triage) vs the STAT-03 `**Status**` line (`:184`) |
| **OPEN-07** | Stats · timeline colours | R3-U-02 proposed `--stage-applied` + `--accent`/`--text-2`; the fix instead introduced a new `--series-new` token (`#b8822b` / `#a1731f`). Measured contrast 2.098:1 light / 2.199:1 dark — just over the fix's own 2:1 target. A deliberate deviation from the suggested tokens, never ruled on. | needs decision (a deviation is a decision, per the project's own addendum) | Confirm `--series-new` as the token, or widen the gap. | `round3/user-notes.md` R3-U-02; `round3/verify.md` item 13 |
| **OPEN-08** | Applications + Feed · Escape | Both screens keep their own once-registered `document` keydown handler (`Applications.jsx:144`, `JobFeed.jsx:515`) instead of the shared `useEscape` hook that ConfirmDialog / ResumeEditor / Resumes / CoverLetterEditor / Settings all use. Works, but is the last inconsistency of its kind. | needs decision | Migrate the two, or record that a screen-level handler is the accepted pattern for multi-overlay screens. | code at HEAD; pattern established by `round3/smoke.md` R3-S-03 |
| **OPEN-09** | Backend · companies API | `GET /api/companies/{id}` is **405** — there is no single-company read endpoint; the UI only ever reads the list. "Not a defect, but worth knowing for any future deep link." | logged | Add the read route if a company deep link is ever wanted. | `round3/flows-A.md` step 1 |
| **OPEN-10** | Feed · scoring cost | The row `SCORE` pill and the detail panel's "Score this role" both post `?depth=full` unconditionally — the one-click path always spends the expensive call; the Light/Full choice exists only behind `r` / ⋯ → Rescore. "Deliberate-looking, but it is the path a new user hits first." | logged, not filed | Make the one-click path honour `scoring_default_depth`. | `round3/flows-A.md` step 4 |
| **OPEN-11** | Docs · scoring columns | `apply_recommendation`, `fit_strengths` and `fit_gaps` stay **null** after a full score (the content now lives in `scoring_report.<résumé>`), but `CLAUDE.md` still documents those three columns as populated. | doc drift, logged | Correct the CV-scoring section of `CLAUDE.md`. | `round3/flows-A.md` step 4 |
| **OPEN-12** | Extension · save-to-feed | `POST /jobs/save-from-extension` applies `title_exclude_global` silently: the job is stored `ignored` and never appears in the feed, with no signal to the person who saved it. | logged ("worth knowing") | Return the exclusion reason and surface it in the extension's response. | `round3/flows-A.md` step 5 |
| **OPEN-13** | Résumés · tracked links | `GET /resumes/{id}/preview` returns the **un-rewritten** HTML (raw destination URLs) while `/pdf` rewrites them. Deliberate in code; the editor uses `/pdf`, so no live defect — but the two endpoints disagree. | logged, not filed | Rewrite in `preview_resume` too, or document the split. | `round3/flows-B.md` step 6 |
| **OPEN-14** | Feed · score band | The collapsed score band shows the **best** score, so when the base outscores the tailored copy the word "Tailored" is invisible until the band is expanded. | note, not filed | Show a marker on the collapsed band whenever a tailored report exists. | `round3/flows-B.md` step 4 |
| **OPEN-15** | Feed · filter dropdowns | Per-value counts in the Source / H-1B / Company dropdowns are **database-wide**, not scoped to the active filter set (measured: Source menu "Direct 15179" while the filtered list showed 13 rows). | semantics never ruled on | Scope the counted endpoints to the active filters, or label the counts as totals. | `round3/flows-A.md` step 3 (filters table); FEED-26 fix at `stage3/feed.md:315` |
| **OPEN-16** | Settings | `jobright_session_id` has no control anywhere in the UI (auto-managed by the scraper). | logged, still open | Hide it explicitly, or show it read-only with its expiry. | `stage4/settings-roundtrip.md:24` |
| **OPEN-17** | Settings | `llm_models_list` has no backend reader — the key is written and rendered but nothing consumes it server-side. | logged, still open | Wire it, or drop the key. | `stage4/settings-roundtrip.md:24`; `inventory/settings-matrix.md` |
| **OPEN-18** | Worksheet | `P3-P4.md` still carries its 2026-09-02 snapshot header ("Open: P3 97 · P4 87 · total 184") and per-row "needs decision" statuses for items now fixed or decided. Will mislead the next reader. | stale worksheet, never regenerated | Regenerate from the current statuses, or stamp it "snapshot of 2026-09-02 — superseded". | `round2/audit.md` §(b) "Stale worksheets" (verified still true at HEAD) |
| **OPEN-19** | Worksheet | `DECISIONS-design.md`'s "Your call" column is empty on all 109 + 12 rows although every row now carries a `decided … keep` status in `stage3/*`. | stale worksheet | Same: regenerate or stamp as superseded. | `round2/audit.md` §(b) |
| **OPEN-20** | Worksheet | 99 round-1 `**Status**` lines still read "fixed in source (rebuild pending)" / "restart pending" although the frontend was rebuilt 2026-09-02 and the backend restarted at 14:03/14:09. The wording is stale, not the fixes. | verification-debt wording, never re-marked | One pass to re-word the 99 lines to "fixed + verified (rebuild <date>)". | `round2/audit.md` §"Verification debt carried in the statuses themselves" (38 at the time; 99 counted at HEAD across `stage3/*` + `FINDINGS.md`) |
| **OPEN-21** | Verification debt | 36 round-1 `fixed` statuses are pure narrative ("~ doc-only") with no greppable symbol; the audit asked R2 smoke to re-observe them, and smoke covered the screens functionally but never signed them off per id. | unverified per-id | Tick the 36 ids explicitly, or accept the screen-level smoke as sufficient. | `round2/audit.md` §"`~ doc-only` — statuses R2 smoke should re-observe (36)" |
| **OPEN-22** | Worksheet | `round2/happy-path.md` — R2-H-11's closure line ("closed: did not reproduce in round 3 …") sits at the end of Flow 6, *after* R2-H-13's block, so R2-H-13 appears to own it and R2-H-11 has no status of its own. | mis-filed status line | Move the line under R2-H-11 and give R2-H-13 its own "fixed + verified (`round3/flows-A.md` step 8)". | `round2/happy-path.md:220,291,312` |

---

## 2. Deferred / limits

Recorded as deliberate limitations rather than defects — listed because several may still deserve work.

| id | area | what | recorded as | source |
|---|---|---|---|---|
| **DEF-01** | v1 shell | Three v1 screens overflow horizontally at 1024 px (Resume Builder, Persona, Stats) and 8 of 9 show no visible error state on a failed data GET. | decided **ignore** — "v1 is being replaced by v2" | `round2/smoke.md` R2-S-03 / R2-S-05 |
| **DEF-02** | Schema | `ondelete="SET NULL"` is now declared on the scrape-log FKs but only applies to a **fresh** database — there is no Alembic; existing DBs rely on the delete handlers nulling explicitly. First candidates if a migration tool is ever added. | consideration | `REPORT-final.md` consideration 2; `round3/flows-A.md` R3-A-08 |
| **DEF-03** | Dedup | `jk` is protected by a per-host identity keep-list, but R3-A-02's second proposed guard — hash `company + title + canonical_url` in `make_external_id`, the way `CLAUDE.md` still documents it — was **not** implemented, and the other very generic entries in `_DEFAULT_TRACKING_PARAMS` (`v`, `r`, `a`, `st`, `for`, `country`, `category`, `ss`, `bid`) were never audited. A note in the Settings dedup help text is also outstanding. | partial fix + unaudited list | `round3/flows-A.md` R3-A-02 (proposed fix (b)); `REPORT-final.md` consideration 1 |
| **DEF-04** | Tracked links | A `TracerLink` is now co-owned by a résumé and its cover letter; deleting one document releases the link rather than deleting it, and **click history is never re-parented**. | by design | `REPORT-final.md` consideration 3 |
| **DEF-05** | LLM spend | The remaining silent spend is the auto-score on searches/companies with `auto_score` on. | by design | `REPORT-final.md` consideration 4 |
| **DEF-06** | Companies / Searches · test preview | The preview cannot run the body-exclusion check on rows with no description; the footer now says `N not body-checked (needs the description)` instead of fetching descriptions during a dry run. | known limit of the R3-A-01 fix | `round3/verify-final.md` item 2; `round3/flows-A.md` R3-A-01 |
| **DEF-07** | Companies scraping | A posting that collides on the `jobs.url` unique constraint is swallowed by the `IntegrityError` branch (`company_pages.py:317`) — correct dedup, but invisible in every count (88 extracted → 87 stored, measured). | correct behaviour, no signal | `round3/flows-A.md` step 1 |
| **DEF-08** | Build | `/v2/toasts` (`ToastLab`) is still routed and shipped (`App.jsx:29,168-169`, both marked `TEMP`). Round 1 listed it as "your call to delete". | not done | `REPORT.md` §"Not done / deferred"; code at HEAD |
| **DEF-09** | Line-heights | F-009's residual fractional blocks, deliberately left: Feed 14 (title `line-height:1.15` in a fixed 20 px box), Applications 98 (offset only, nothing fractional), Résumé editor 5, Settings 3, Stats 44 (Recharts SVG). Closed as P4 residue. | closed as residue | `FINDINGS.md` F-009; `stage3/F-009-linheights.md` §"Not fixed (with the same detail)" |
| **DEF-10** | Coverage | Round 1 "Couldn't test": **48 items** across the nine screen reports (e.g. `h1b_approval_rate` scale never seen as a 0–1 fraction; `total_rejected > 0` in the Companies test modal; the `awaiting_pin` LinkedIn PIN entry and its 2.5 s poll; live OpenAI/Claude catalog error paths; a real key rotation; `ago()` with a null `updated_at`; the two cover-letter 400 branches; a real preview against a live board; `DELETE` on the seeded extension searches; two concurrent Tests; non-UTC timezone drift for STAT-15). | never exercised | `REPORT.md` §"Couldn't test (48 items …)" |
| **DEF-11** | Coverage | Round 2 smoke "Couldn't test": curated per-screen primary-control lists; Escape-close on screens with no menu trigger (Cover Letters shelf, Résumés shelf, Stats, all 9 v1); hover/geometry-vs-design (Stage 3's remit). | out of scope for that pass | `round2/smoke.md` §"Couldn't test" |
| **DEF-12** | Coverage | Round 3 smoke "Couldn't test": menu items *behind* an opened overlay (Score again, Delete config/company, Delete search/application, Decline/Done reviewing); Toast Lab's "Fire all" 3-toast cap; `Manage…` on rows other than Model catalog; whether R3-S-02/03/04 were deliberate. | out of scope (read-only, no-mutation brief) | `round3/smoke.md` §"Couldn't test" |
| **DEF-13** | Harness | Structural limits that make some checks unrepeatable here: headless Linux uses 0 px overlay scrollbars (`.v2-scroll` / `.v2-gutter` behaviour unverifiable); no PDF plug-in (PDF viewer chrome and preview pixels unverifiable); the container runs UTC (STAT-15's local-vs-UTC drift reasoned, not measured); extension content-script closures are not callable from a page context (R2-H-12 read, not driven). | environment | `REPORT.md` §"Couldn't test"; `round2/verify.md` item 22 + §"Notes on method" |
| **DEF-14** | Repo | `v2-testing/design/` (14 decoded boards) and `v2-testing/artifacts/` (raw JSON + every screenshot) are gitignored, so none of the evidence behind these reports is in the repo. | plan convention | `PLAN.md` §Conventions |
| **DEF-15** | Text | 156 plain-language rewrites + 14 vocabulary decisions, **none applied**. Excluded from this report by request. | awaiting per-line approval | `round2/text-suggestions.md`; `REPORT-final.md` §Text |

---

## 3. Deliberately kept (for reference)

Not open — each carries a dated user decision. Listed so any of them can be re-opened.

| id | one line |
|---|---|
| APPS-14 | A filtered-out application stays open in the detail pane, with no indication |
| APPS-16 | Applications layout/copy deviations from the board (pane width, pill metrics, section order, labels) |
| APPS-17 | The Log modal keeps the URL as required (it seeds the dedup id); the message now says why |
| APPS-23 | The "Cached" link relies on the session cookie, not the API-key header |
| COMP-17 | Accent border+wash hover taxonomy kept and unified across the screen |
| COMP-20 | Drawer stays 720 px (board draws 520) |
| COMP-21 | Column widths stay as coded |
| COMP-22 | No "{n} of {N} shown" counter |
| COMP-30 | Ø Fit keeps U+00D8 rather than the board's U+2300 |
| COMP-31 | Tier chip keeps a bare count and a static tooltip |
| COMP-36 | Sort menu keeps six options (board has five) |
| CL-12 | Generate panel keeps no explanatory line |
| CL-24 | Cover-letter deviations kept except (d), the 45/55 contact split, which was fixed |
| FEED-23 | Requirement table: no tint on unmet rows, header not sticky |
| FEED-27 | Score ring geometry + traffic-light scale kept |
| FEED-28 | Sort's fourth option stays "Company A–Z" |
| FEED-30 | Row/header padding and widths kept |
| FEED-35 | Posting pane stays an iframe, not a reader column |
| FEED-36 | `--iframe-bg` stays white in both themes |
| FEED-37 | `--surface-2` / `--bg` palette values kept (changed on purpose) |
| PERS-16 | Column heads keep no right-hand caption |
| PERS-17 | Autofill group headers keep no subtitle |
| PERS-22 | Q&A subtitle stays the shorter wording |
| STAT-10 | Score bucket 61–80 keeps `--funnel-mid` |
| STAT-11 | Funnel rows keep no per-row percentage and no card subtitle |
| STAT-12 | "Avg / call" keeps $0.0000 |
| STAT-14 | Schedules subtitle keeps both timezone clauses (crons are UTC, next runs local) |
| STAT-17 | (b), (c), (e) kept — Funnel/Flow toggle, Schedules columns, Running label |
| STAT-20 | KPI tile padding/gap/line-height kept |
| RES-22 | Résumé design deviations kept (consistency with the other v2 screens) |
| RES2-01…12 | Eleven Résumés-Shelf board deviations kept (header border, search inset, card/chip/border hovers, back row, Add modal, 460 px name clamp, ⋯ trigger tint, section-header hover) — RES2-03 and RES2-10 were fixed |
| SRCH-08 | Test-modal .75 px offset kept (row heights are integer; only the centred modal height is fractional) |
| SRCH-13 | Test modal stays 980 px |
| SRCH-14 | Test-modal Salary column stays 120 px / 9.5 px |
| SRCH-17 | Extra card/chip/pill/tab hovers kept for consistency |
| SRCH-18 | Card action-cluster metrics kept |
| SRCH-25 | Depth indicator keeps `cursor: help` while opening the editor |
| SET-17 | Seeded models stay removable from the catalog |
| SET-18 | H-1B refresh + Job cleanup triggers stay on Stats › Run history, not Settings |
| SET-20 | 135 px numeric/cron boxes and 260 px Selects kept |
| SET-21 | Edit modal stays 1020 px |
| SET-24 | Section subtitles and row labels keep the code's wording |
| SET-27 (part) | Chat ID deliberately excluded from the digit-only numeric filter — group ids are negative |
| SHELL-02 | Theme toggle stays two-state until the theming groundwork |
| SHELL-04 | Welcome modal keeps its unauthored step/✕ hovers |
| SHELL-05 | Rail transition, dim colour, health dot and dark background keep their values |
| SHELL-06 | `App.jsx` and `V2App` keep separate theme flags (harmless while "← Classic UI" is a full navigation) |
| F-006 | Backend stays restart-only — no `--reload` (the watcher could restart mid-scrape) |
| R2-H-06 | The Feed keeps auto-opening row 0's detail and iframing the posting on every visit |
| R2-S-03 | v1 screens keep their 1024 px overflow (ignored — v1 is being replaced) |
| R2-S-05 | v1 screens keep having no error state on a failed GET (ignored — same reason) |
| R3-B-01 (part) | Experience role/bullet reorder **not** added — only the header Title field; reorder kept as designed |

Closed by fact rather than by preference (not re-openable as decisions): **RES-24** (section-open localStorage keys were already split three ways), **SET-26** (`ZZTEST Base A` no longer exists), **R2-H-11** (the freeform completion toast did not reproduce in round 3).

---

## 4. Counts

| bucket | count |
|---|---|
| Open — P1 | 0 |
| Open — P2 | 0 |
| Open — P3 | 1 |
| Open — P4 | 4 |
| Open — unclassified | 17 |
| **Open — total** | **22** |
| Deferred / limits | 15 |
| Deliberately kept (appendix rows) | 53 rows, covering 63 individual ids (RES2-01…12 is one row for 11 ids) |
| Closed by fact | 3 |
| Filed findings still open across rounds 1–3 | **0** |
| Text suggestions (excluded here) | 156 |

## Decisions (2026-09-04, user — this is the final list)
- Fix: OPEN-01, 02, 03, 04, 06, 10, 12 (Opus batch in progress).
- OPEN-07: `--series-new` confirmed as the token (decided).
- OPEN-14: no need. OPEN-15: don't care. OPEN-18..22: ignored (worksheet debt).
- OPEN-17: checked — `llm_models_list` is consumed by the frontend model pickers via `GET /settings`; the backend only seeds/refreshes it. No action.
- OPEN-05 (critical spots), 08 (migrate to `useEscape`), 13 (tracked links in preview), 16 (read-only with expiry): fix, in the same Opus batch. OPEN-09: no need. OPEN-11: CLAUDE.md corrected (gitignored, local).

## Closure (2026-09-04, later)
All decided items are fixed and verified live (`round3/verify-open.md`, 12/12): OPEN-01, 02, 03, 04, 05, 06, 08, 10, 12, 13, 16 plus the user-reported health rule (inactive entities never count; per-entity Acknowledge). Commits `2927bdb`, `63790cf`. Backend suite: 858 passing. OPEN-07 decided (token kept), OPEN-09 no need, OPEN-11 corrected in CLAUDE.md, OPEN-14/15 dropped, OPEN-17 no action, OPEN-18..22 ignored. **Nothing from rounds 1–3 remains open except the unapplied text suggestions.**
