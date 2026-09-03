# v2 verification — FINAL REPORT (rounds 1–3)

> Update 2026-09-04 (later): the six open items below were fixed and verified after the user's decisions (`406aebe`, `2946d5b`); R3-B-01 got the Title field only. The authoritative list of what is still open is now **`REPORT-open.md`**.

Branch `v2-redesign`, 2026-09-01 → 2026-09-04. This file lists **everything still open** after three rounds, in one place, plus the text suggestions. Round detail: `REPORT.md` (round 1), `REPORT-round2.md`, `round2/*.md`, `round3/*.md`; plans `PLAN.md`, `ROUND2-PLAN.md`, `ROUND3-PLAN.md`.

## Where things stand

| Round | Findings | Fixed and verified | Decided keep / closed | Still open |
|---|---|---|---|---|
| 1 (7 stages + per-screen follow-ups) | 278 | 235 | 43 | 0 |
| 2 (audit, smoke, 10 happy-path flows, text scan) | 26 (R2-A 3 · R2-S 6 · R2-H 15 · SET-28, COMP-11 re-opened) | 23 | 3 (R2-H-06 keep, R2-S-03/05 ignore) | 0 |
| 3 (smoke, 2 deep flow groups, user notes) | 20 (R3-A 8 · R3-B 6 · R3-S 4 · R3-U 2) | 14 (incl. 2 P1, 2 P2) | 0 | **6** |
| Text (round 2) | 156 flagged strings | — | — | **156 suggestions, none applied** |

Last verification: every round-3 fix confirmed live on the rebuilt bundle (`round3/verify.md`, 14/14), 735 backend tests passing, DB restored to `backups/round3_baseline_20260904.dump`.

Real-world checks that passed in round 3: real Greenhouse company scrape and delete, real JobSpy search run (Indeed now stores rows), Light + Full scoring with correct provider/model logging, apply → undo → re-apply, manual log with URL reader, all application stages with interviews, prep pack, Stats reflecting it, Telegram digest, Gmail check, résumé from scratch, PDF import with real parse, every section editor, tailor + review + scores, freeform tailor + job-less score, PDFs with tracked links, cover letter generate + regenerate, persona Q&A through the UI, autofill with length limits, settings round trip with scheduler reconfigure.

## Open items — need a decision

### P3 (2)
| id | where | what | suggested |
|---|---|---|---|
| **R3-A-03** | search run summary / ScrapeLog | A source that hard-fails (ZipRecruiter 403, Google "cursor not found") is indistinguishable from one that found nothing: run `completed`, `is_warning:false`, summary "9 seen, +0 new". | Per-source outcome in the run summary and ScrapeLog (`zip: 403`, `google: no results`), `is_warning` when any source errored; surface it in the Searches health text. |
| **R3-B-01** | résumé editor | No job-title/headline field in the header (though `header.title` exists in real data and renders in the PDF), and no reorder in Experience (roles or bullets). Matches the design board. | Add a Title field to the header editor and Move up/down on roles and bullets (the shared `arrows()` helper already exists for skills), or keep the design. |

### P4 (4)
| id | where | what | suggested |
|---|---|---|---|
| **R3-A-01** | Companies test scrape vs run | Test says "14 kept", the run stores 13 + 1 `ignored`; the preview applies only the title filters, so a body-exclusion drop is invisible and unexplained. | Run the body-exclusion check in the preview too (it needs the description fetch — mark those rows "would be ignored: <phrase>"), or say "title filters only" in the footer. |
| **R3-A-04** | Feed bulk actions | Bulk skip/save toasts have no Undo, single-row ones do. | Bulk toast with Undo that reverts the batch (ids are known). |
| **R3-A-06** | Applications interview rows | An interview can only be toggled scheduled/done or deleted; rescheduling means delete and retype. `PATCH /applications/interviews/{id}` already exists. | Inline edit on click (date, time, type, note) using the existing PATCH. |
| **R3-A-07** | run history | Email-check summary reads "1 repl" / "2 repls". | Plural argument on `_activity_summary` ("reply"/"replies"). |

### Deferred by earlier decisions (not defects, listed so nothing is lost)
- R2-H-06: the Feed opens the first job's detail on load (kept).
- R2-S-03 / R2-S-05: v1 screens overflow at 1024 and show no error state on failed loads (ignored; v1 is being replaced).
- SHELL-02: theme toggle stays two-state until the theming groundwork.
- 43 round-1 design deviations recorded as deliberate consistency choices (`REPORT.md`, `DECISIONS-design.md`).

## Considerations
1. **Dedup identity params**: `jk` is now never stripped on any host and a per-host keep-list protects Indeed/Glassdoor/LinkedIn/Dice/Monster ids. Any new tracking param a user adds to `dedup_tracking_params` cannot erase an identity again. Worth a short note in the Settings help text (see text suggestions, Settings › dedup row).
2. **Schema without migrations**: `ondelete="SET NULL"` is now declared on the scrape-log FKs but only applies to a fresh database; the delete handlers do the nulling explicitly for existing ones. If a migration tool is ever added, these two columns are the first candidates.
3. **Tracked links are co-owned** by a résumé and its cover letter by design now; deleting one document releases the link rather than deleting it. Click history is never re-parented.
4. **LLM spend visibility**: the tailor's chained score is now stated in the modal and returned by the API (`chain_score`); autofill answers are trimmed server-side to the requested length. The remaining silent spend is the auto-score on searches/companies with `auto_score` on, which is by design.
5. **Native browser dialogs are gone from v2**; every destructive action goes through `ConfirmDialog`/`PromptDialog`.
6. **Silent `.catch`** sites are tagged `// silent: <reason>` (45) or converted (4); the count is now assertable.
7. **Source-level error visibility** (R3-A-03) is the one remaining place where a failing integration looks healthy. It is the most valuable of the open items.

## Text — plain-language suggestions (unapplied)
`round2/text-suggestions.md`: 156 rewrites grouped per screen, plus §0 with 14 vocabulary decisions that settle ~40 rows at once:
sweep → scrape run · land/lands → appear/applied/recorded · live in → is in · draw from → use · funnel kept only as the chart name · tracers → tracked links · slug → id · dry run → preview run · JD → job description · pipeline → the app · LCA → H-1B filings · prep handover/bundle → prep pack · "The Feed" vs "Jobs" → one name · quick-scored → Light.
Counts by flag: unclear 87 · long 36 · metaphor 27 · mannered 6 · hedge 0. Approve per section or per line; an Opus agent applies them and I re-measure the affected screens.

## Data and environment
- Baseline `backups/round3_baseline_20260904.dump` restored at the end of round 3 (backend stopped for the restore); counts verified; 0 `ZZA`/`ZZB`/`ZZV` rows. Earlier baselines: `round2_baseline_20260903.dump`, `pre_selfloop_strip_20260903.dump`, `v2testing_baseline_20260901_2345.dump`.
- LLM calls in round 3: 5 (flows A) + 11 (flows B) + 0 (smoke, verification), all `claude_code / claude-sonnet-5`.
- Real network used: Greenhouse boards, JobSpy (Indeed, LinkedIn, ZipRecruiter 403, Google no cursor), one Telegram digest message, one Gmail check.
- Backend must be restarted after `.py` edits (no hot reload); `CLAUDE.md` was rewritten on 2026-09-04 to the current layout.

## Nothing pushed. All commits bare, on `v2-redesign`.
