# R1 — audit of the v2 verification pass

Read-only reconciliation of every finding file against the code at HEAD `b7582ad`
(= `1fd6152` + the round-2 plan commit; working tree clean, so working tree == HEAD).
No code, no finding file and no commit was touched.

## Method

- Parsed every `### ID · P<n> · title` / `**Status**` block out of `stage3/*.md`,
  `FINDINGS.md`, `stage5/cross-cutting.md` (289 findings; `stage4/settings-roundtrip.md`
  and `P3-P4.md` / `DECISIONS-design.md` carry no `###` findings of their own).
- Every `fixed` status was checked against the tree: backticked identifiers and quoted UI
  strings from the status line were searched in `frontend/src`, `backend/`, `extension/`.
  106 matched automatically; 79 more were confirmed by hand (`✔ (grep-confirmed)`), the
  rest are narrative statuses with no checkable token (`~ doc-only`) — see the note below.
- **Zero `fixed` statuses turned out to be false.** Every claim I could reduce to a token
  or a string is in the tree at HEAD, including the ones whose evidence is an *absence*
  (`arrivedToday`, `forceFrame`, `GROUP_LABEL`, `by_source`, `/resumes?resume=`,
  `bg:` in `jobState`, `--paper`, the nine dead theme aliases — all gone).
- One status is materially wrong: **COMP-11 says it was *not* fixed but is worded so the
  report counts it as fixed.** Confirmed in code: `Companies.jsx:425` still reads
  `aliases.length > 1` → `+{aliases.length - 1}`.

### What `~ doc-only` means

36 fixed statuses are pure prose ("fixed + verified after rebuild: Escape closes the
filter dropdowns…"). They name a behaviour, not a symbol, so there is nothing to grep and
this stage cannot re-confirm them without running the app. They are **not** suspect — the
screens they belong to passed every symbol-level check I did make — but they are the set
that R2 smoke should re-observe. Listed per file below.

### Verification debt carried in the statuses themselves

38 statuses still say "fixed in source (rebuild pending)" or "restart pending". The
frontend was rebuilt on 2026-09-02 (`REVERIFY.md` §Results) and the backend restarted at
14:03/14:09, both *after* most of those lines were written, so the wording is stale rather
than the fix — but no one went back and re-marked them. Flagged per row in the tables.


## (a) Per-file tables

Columns: `status class` = what the status line actually says · `counted-as` = what
`tools/report_gen.py` scores it · `verified-in-code` = ✔ grep/read-confirmed at HEAD,
`~ doc-only` = narrative status with no checkable symbol, ✖ = claim not in the code.

### applications.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| APPS-01 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| APPS-02 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| APPS-03 | P2 | fixed | fixed | ✔ |  |
| APPS-04 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-05 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| APPS-06 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| APPS-07 | P2 | fixed | fixed | ✔ (grep-confirmed) | backend source only; restart pending |
| APPS-08 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| APPS-09 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-10 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-11 | P3 | fixed | fixed | ✔ |  |
| APPS-12 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-13 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-14 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| APPS-15 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-16 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| APPS-17 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| APPS-18 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-19 | P4 | fixed | fixed | ✔ |  |
| APPS-20 | P4 | needs-decision | decision | — |  |
| APPS-21 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-22 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| APPS-23 | P4 | decided-keep **MISCOUNT** | logged | — |  |

### companies.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| COMP-01 | P1 | fixed | fixed | ✔ |  |
| COMP-02 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-03 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| COMP-04 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-05 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-06 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| COMP-07 | P2 | fixed | fixed | ~ doc-only | source-only; not re-measured on the built bundle |
| COMP-08 | P2 | fixed | fixed | ✔ (grep-confirmed) | backend source only; restart pending |
| COMP-09 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-10 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-11 | P2 | needs-decision **MISCOUNT** | fixed | ✖ **not fixed** | status opens "fixed in source? no" so the tool scores it fixed; `Companies.jsx:425` still `aliases.length > 1` → `+{aliases.length - 1}` |
| COMP-12 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-13 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| COMP-14 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-15 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| COMP-16 | P3 | fixed | fixed | ✔ |  |
| COMP-17 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-18 | P3 | fixed | fixed | ✔ |  |
| COMP-19 | P3 | fixed | fixed | ✔ |  |
| COMP-20 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-21 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-22 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-23 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| COMP-24 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| COMP-25 | P3 | fixed | fixed | ✔ |  |
| COMP-26 | P3 | needs-decision | decision | — |  |
| COMP-27 | P3 | fixed | fixed | ✔ |  |
| COMP-28 | P3 | fixed | fixed | ~ doc-only |  |
| COMP-29 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| COMP-30 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-31 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-32 | P4 | fixed | fixed | ✔ |  |
| COMP-33 | P4 | fixed | fixed | ✔ |  |
| COMP-34 | P4 | fixed | fixed | ~ doc-only |  |
| COMP-35 | P4 | fixed | fixed | ✔ |  |
| COMP-36 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| COMP-37 | P4 | fixed | fixed | ✔ |  |

### cover-letters.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| CL-01 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-02 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-03 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-04 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| CL-05 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| CL-06 | P2 | fixed | fixed | ~ doc-only | source-only; not re-measured on the built bundle |
| CL-07 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-08 | P3 | fixed | fixed | ✔ |  |
| CL-09 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-10 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| CL-11 | P3 | fixed | fixed | ~ doc-only |  |
| CL-12 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| CL-13 | P3 | fixed | fixed | ✔ |  |
| CL-14 | P3 | fixed | fixed | ✔ |  |
| CL-15 | P3 | fixed | fixed | ✔ |  |
| CL-16 | P3 | fixed | fixed | ~ doc-only |  |
| CL-17 | P3 | fixed | fixed | ✔ |  |
| CL-18 | P3 | fixed | fixed | ~ doc-only |  |
| CL-19 | P3 | fixed | fixed | ✔ |  |
| CL-20 | P3 | fixed | fixed | ✔ |  |
| CL-21 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| CL-22 | P4 | fixed | fixed | ✔ |  |
| CL-23 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| CL-24 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| CL-25 | P4 | fixed | fixed | ~ doc-only |  |
| CL-26 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| CL-27 | P4 | fixed | fixed | ~ doc-only |  |
| CL-28 | P4 | needs-decision | decision | — |  |
| CL-29 | P4 | fixed | fixed | ~ doc-only |  |

### feed.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| FEED-01 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-02 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| FEED-03 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| FEED-04 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| FEED-05 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| FEED-06 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| FEED-07 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| FEED-08 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| FEED-09 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| FEED-10 | P2 | fixed | fixed | ✔ |  |
| FEED-11 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| FEED-12 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-13 | P3 | fixed | fixed | ✔ |  |
| FEED-14 | P3 | fixed | fixed | ✔ |  |
| FEED-15 | P3 | fixed | fixed | ✔ |  |
| FEED-16 | P3 | fixed | fixed | ~ doc-only |  |
| FEED-17 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-18 | P3 | fixed | fixed | ~ doc-only |  |
| FEED-19 | P3 | fixed | fixed | ~ doc-only |  |
| FEED-20 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-21 | P3 | fixed | fixed | ✔ |  |
| FEED-22 | P3 | fixed | fixed | ~ doc-only |  |
| FEED-23 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-24 | P3 | fixed | fixed | ✔ |  |
| FEED-25 | P3 | fixed | fixed | ~ doc-only |  |
| FEED-26 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-27 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-28 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-29 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-30 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-31 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| FEED-32 | P4 | fixed | fixed | ~ doc-only |  |
| FEED-33 | P4 | fixed | fixed | ~ doc-only |  |
| FEED-34 | P4 | fixed | fixed | ~ doc-only |  |
| FEED-35 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-36 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-37 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| FEED-38 | P4 | fixed | fixed | ✔ |  |

### persona-stats.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| PERS-01 | P1 | fixed | fixed | ✔ |  |
| PERS-02 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| PERS-03 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| PERS-04 | P2 | fixed | fixed | ~ doc-only | source-only; not re-measured on the built bundle |
| PERS-05 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| PERS-06 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| PERS-07 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| PERS-08 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| PERS-09 | P3 | fixed | fixed | ✔ |  |
| PERS-10 | P3 | fixed | fixed | ✔ |  |
| PERS-11 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| PERS-12 | P3 | fixed | fixed | ✔ |  |
| PERS-13 | P3 | fixed | fixed | ✔ |  |
| PERS-14 | P3 | fixed | fixed | ✔ |  |
| PERS-15 | P3 | fixed | fixed | ✔ |  |
| PERS-16 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| PERS-17 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| PERS-18 | P4 | fixed | fixed | ✔ |  |
| PERS-19 | P4 | fixed | fixed | ✔ |  |
| PERS-20 | P4 | fixed | fixed | ✔ |  |
| PERS-21 | P4 | fixed | fixed | ✔ |  |
| PERS-22 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| PERS-23 | P4 | fixed | fixed | ✔ |  |
| STAT-01 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| STAT-02 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| STAT-03 | P2 | fixed | fixed | ✔ |  |
| STAT-04 | P3 | fixed | fixed | ~ doc-only |  |
| STAT-05 | P3 | fixed | fixed | ✔ |  |
| STAT-06 | P3 | fixed | fixed | ~ doc-only |  |
| STAT-07 | P3 | fixed | fixed | ✔ |  |
| STAT-08 | P3 | fixed | fixed | ✔ |  |
| STAT-09 | P3 | fixed | fixed | ✔ |  |
| STAT-10 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-11 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-12 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-13 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| STAT-14 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-15 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| STAT-16 | P4 | fixed | fixed | ✔ |  |
| STAT-17 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-18 | P4 | fixed | fixed | ✔ |  |
| STAT-19 | P4 | fixed | fixed | ✔ |  |
| STAT-20 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| STAT-21 | P4 | fixed | fixed | ✔ |  |
| STAT-22 | P4 | fixed | fixed | ✔ |  |

### resumes-shelf-recheck.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| RES2-01 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-02 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-03 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES2-04 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-05 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-06 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-07 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-08 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-09 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-10 | P3 | fixed | fixed | ✔ |  |
| RES2-11 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| RES2-12 | P4 | decided-keep **MISCOUNT** | logged | — |  |

### resumes.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| RES-01 | P1 | fixed | fixed | ✔ |  |
| RES-02 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-03 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-04 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| RES-05 | P2 | fixed | fixed | ~ doc-only | source-only; not re-measured on the built bundle |
| RES-06 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-07 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-08 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-09 | P2 | fixed | fixed | ✔ |  |
| RES-10 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-11 | P3 | fixed | fixed | ✔ |  |
| RES-12 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| RES-13 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-14 | P3 | fixed | fixed | ✔ |  |
| RES-15 | P3 | fixed | fixed | ✔ |  |
| RES-16 | P3 | fixed | fixed | ✔ |  |
| RES-17 | P3 | fixed | fixed | ✔ |  |
| RES-18 | P3 | fixed | fixed | ✔ |  |
| RES-19 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-20 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-21 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-22 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| RES-23 | P4 | fixed | fixed | ✔ |  |
| RES-24 | P4 | closed **MISCOUNT** | logged | — |  |
| RES-25 | P4 | fixed | fixed | ~ doc-only |  |
| RES-26 | P4 | fixed | fixed | ✔ |  |
| RES-27 | P4 | fixed | fixed | ✔ |  |
| RES-28 | P4 | fixed | fixed | ✔ |  |
| RES-29 | P4 | fixed | fixed | ✔ |  |
| RES-30 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-31 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| RES-32 | P4 | needs-decision | decision | — |  |

### searches.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| SRCH-01 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-02 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-03 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-04 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-05 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-06 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-07 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SRCH-08 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-09 | P3 | fixed | fixed | ~ doc-only |  |
| SRCH-10 | P3 | fixed | fixed | ✔ |  |
| SRCH-11 | P3 | fixed | fixed | ✔ |  |
| SRCH-12 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| SRCH-13 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-14 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-15 | P3 | fixed | fixed | ✔ |  |
| SRCH-16 | P3 | fixed | fixed | ~ doc-only |  |
| SRCH-17 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-18 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-19 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| SRCH-20 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-21 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-22 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-23 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-24 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-25 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SRCH-26 | P3 | fixed | fixed | ~ doc-only |  |
| SRCH-27 | P4 | fixed | fixed | ~ doc-only |  |
| SRCH-28 | P4 | fixed | fixed | ✔ |  |
| SRCH-29 | P4 | fixed | fixed | ✔ |  |

### settings.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| SET-01 | P1 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-02 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-03 | P1 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-04 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-05 | P2 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-06 | P2 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SET-07 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-08 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| SET-09 | P4 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-10 | P3 | fixed | fixed | ✔ (grep-confirmed) | source-only; not re-measured on the built bundle |
| SET-11 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| SET-12 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| SET-13 | P3 | fixed | fixed | ✔ |  |
| SET-14 | P3 | fixed | fixed | ✔ |  |
| SET-15 | P3 | fixed | fixed | ✔ |  |
| SET-16 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| SET-17 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SET-18 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SET-19 | P4 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SET-20 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SET-21 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SET-22 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| SET-23 | P4 | fixed | fixed | ✔ |  |
| SET-24 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SET-25 | P4 | fixed | fixed | ✔ |  |
| SET-26 | P4 | closed **MISCOUNT** | logged | — |  |
| SET-27 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |

### shell.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| SHELL-01 | P3 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SHELL-02 | P3 | decided-keep **MISCOUNT** | logged | — |  |
| SHELL-03 | P4 | fixed | fixed | ✔ | source-only; not re-measured on the built bundle |
| SHELL-04 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SHELL-05 | P4 | decided-keep **MISCOUNT** | logged | — |  |
| SHELL-06 | P4 | decided-keep **MISCOUNT** | logged | — |  |

### FINDINGS.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| F-001 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| F-002 | P2 | fixed | fixed | ✔ (grep-confirmed) |  |
| F-003 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |
| F-004 | P4 | fixed | fixed | ~ doc-only |  |
| F-005 | P2 | fixed | fixed | ✔ |  |
| F-006 | P2 | decided-keep **MISCOUNT** | logged | — |  |
| F-007 | P2 | fixed | fixed | ~ doc-only |  |
| F-008 | P2 | fixed | fixed | ~ doc-only |  |
| F-009 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |
| F-010 | P3 | fixed | fixed | ✔ (grep-confirmed) |  |

### cross-cutting.md

| ID | P | status class | counted-as | verified-in-code | note |
|---|---|---|---|---|---|
| X-01 | P4 | fixed | fixed | ✔ (grep-confirmed) |  |

---

## (b) Open items

### Genuinely open — no decision recorded

| ID | P | Sev now | Item | Recommendation |
|---|---|---|---|---|
| COMP-11 | P2 | **high** | Alias badge under-reports by one; a 1-alias company shows no badge. Not fixed, but scored as fixed, so it is missing from REPORT's "Open P2s that need you". | Decide: `aliases.length > 0` → `+{aliases.length}`. One line, `Companies.jsx:425`. Ask in R5. |
| APPS-20 | P4 | low | Selected row and hovered row are the same colour. | Give the selected row a left accent bar; hover stays `--surface-2`. |
| COMP-26 | P3 | medium | No in-progress state for the test scrape; the result table renders every row. | Spinner + "Testing…" on the button, cap the table at 100 rows with a "show all" row (matches Résumés' RES-19 pattern). |
| CL-28 | P4 | low | One shared `err` slot in the editor, cleared only by a successful save. | Fold into the toast system already mounted there (CL-18) and drop the slot. |
| RES-32 | P4 | low | Centred modals land on a half pixel when the panel height is odd. | `top: 50%` + `translateY(-50%)` → round the computed offset, or give the modal an even min-height. |
| stage4 obs. | P4 | low | `POST /settings` accepts an unknown key (`routes_settings.py:51-54`) — no allow-list. **Has no finding id, so `report_gen` never counted it.** | File it as `SET-28 · P4` in `stage3/settings.md` so it is tracked, then decide reject-vs-accept. |
| APPS-01 residue | P4 | low | `Applications.jsx:612` — `GET /resumes` in the Log modal is still `.catch(() => {})`. Recorded inside APPS-01's status text as "logged, not fixed", so it has no id and is invisible to the report. | Either fix (one toast) or split into its own id. |

### Resolved by a user decision (recorded, attributed) — 58 items

All 58 carry a dated attribution and read as real decisions, so none needs re-asking:

- Dated **2026-09-02**, wording "decided 2026-09-02: keep …": APPS-14, APPS-16, APPS-17,
  APPS-23, COMP-17, COMP-20, COMP-21, COMP-22, COMP-30, COMP-31, COMP-36, CL-12, CL-24,
  FEED-23, FEED-27, FEED-28, FEED-30, FEED-35, FEED-36, FEED-37, PERS-16, PERS-17,
  PERS-22, STAT-10, STAT-11, STAT-12, STAT-14, STAT-17 (partial — see below), STAT-20,
  SRCH-08, SRCH-13, SRCH-14, SRCH-17, SRCH-18, SRCH-25, F-006.
- Dated **2026-09-02**, wording "decided keep current (user 2026-09-02)": SET-17, SET-18,
  SET-20, SET-21, SET-24.
- Dated **2026-09-03**, wording "decided keep current (user 2026-09-03)": RES-22, RES2-01,
  RES2-02, RES2-04, RES2-05, RES2-06, RES2-07, RES2-08, RES2-09, RES2-11, RES2-12,
  SHELL-02, SHELL-04, SHELL-05, SHELL-06.
- **Closed by fact, not by preference**: RES-24 (section-open localStorage keys already
  split three ways — verified in code), SET-26 (`ZZTEST Base A` gone — verified via
  `GET /api/resumes` on 2026-09-03).

**No bare "keep" without attribution was found.** Every keep names a date, and most name
the reason. The one to watch is **STAT-17**, which is half fix and half decision in a
single line — see (c).

### Stale worksheets (not findings, but they will mislead the next reader)

| File | Problem | Recommendation |
|---|---|---|
| `v2-testing/P3-P4.md` | Header says "Open: P3 97 · P4 87 · total 184". Its per-row Status column still reads "needs decision." for items that are now fixed (APPS-12, APPS-13, APPS-15, …) or decided-keep. | Regenerate from the current statuses, or stamp it "snapshot of 2026-09-02 — superseded by the per-screen statuses". |
| `v2-testing/DECISIONS-design.md` | The "Your call" column is empty on every row although all 109+12 rows now carry a `decided … keep` status in `stage3/*.md`. | Same: regenerate or stamp as superseded. |
| `v2-testing/stage3/REVERIFY.md` | Its "NOT CONFIRMED / RESIDUAL" list (FEED-02, SRCH-07, APPS-08, CL-09, PERS-11) is answered by F-009, but REVERIFY never says so. | Add one line: "residuals consolidated into F-009 — closed there." |
| `v2-testing/tools/report_gen.py` | Lines 3-11 permanently re-write three status lines (COMP-01, PERS-01, RES-01) on every run. Re-running it now is idempotent, but the block is a landmine for anyone who edits those three statuses later. | Delete the `ups` block — the statuses it writes are already in the files. |

### Cross-references — all resolve

| Reference | Target | Verdict |
|---|---|---|
| `P3-P4.md` SET-26 "whoever owns the Résumés pass should remove it" | `stage3/settings.md` SET-26 | ✔ closed there ("no `ZZTEST` base résumé remains", 2026-09-03) |
| `DECISIONS-design.md:168` "Full detail: `stage3/resumes-shelf-recheck.md`" | that file | ✔ exists, 12 RES2 findings, all statused |
| `shell.md` SHELL-06 "folded into SHELL-02" | SHELL-02 | ✔ SHELL-02 is decided-keep and covers the two-state toggle |
| `resumes-shelf-recheck.md` "folded into RES-22" (menu border token) | RES-22 | ✔ RES-22 is decided-keep and grouped |
| `PERS-03` "Same edit as RES-04" / `RES-04` "Closes PERS-03" | each other | ✔ both point at `ResumeSections.jsx:283-286`; code at HEAD has `setVal` at `:336` |
| `F-005` "live verification deferred to Stage 3 Searches" | `stage3/searches.md:209` | ✔ verified there (`trigger_url` `/searches/<id>/run` → 202) |
| `F-009` "systematic pass, `stage3/F-009-linheights.md`" | that file | ✔ exists; 73 fixes + a "Not fixed (with the same detail)" table justifying each residual |
| REVERIFY residuals → F-009 | F-009 | ✔ covered, though F-009 itself is not named in REVERIFY |
| `PLAN.md` "Follow-up round" — "Still open for the user's call: Résumés, Settings, Shell, F-003/F-004" | those files | ✔ all closed since: RES/RES2 decided 09-03, SET-17..24 decided 09-02, SHELL-02..06 decided 09-03, F-003 fixed (cf50554), F-004 fixed (9e03e5b). PLAN's bullet is stale — no work is actually owed. |

### `~ doc-only` — statuses R2 smoke should re-observe (36)

COMP-07, COMP-28, COMP-34 · CL-06, CL-11, CL-16, CL-18, CL-25, CL-27, CL-29 ·
FEED-16, FEED-18, FEED-19, FEED-22, FEED-25, FEED-32, FEED-33, FEED-34 ·
PERS-04, STAT-04, STAT-06 · RES-05, RES-25 ·
SRCH-09, SRCH-16, SRCH-20, SRCH-21, SRCH-22, SRCH-23, SRCH-24, SRCH-26, SRCH-27 ·
F-004, F-007, F-008. (COMP-11 was in this set and turned out to be the one real ✖.)

---

## (c) Status-line fixes so the report counts are right

`tools/report_gen.py:21` scores a status **fixed** only if it starts with `fixed`,
**decision** only if it contains `needs decision` / `needs your`, and **logged** for
everything else. Three consequences, in priority order.

### C1 — one status is scored the opposite of what it says (must fix)

| file | ID | old first words | new first words |
|---|---|---|---|
| `stage3/companies.md` | COMP-11 | `fixed in source? no — logged; one-line change but it silently shifts every row, so: needs decision.` | `needs decision — not fixed: one-line change (aliases.length > 0 → +{aliases.length}) but it silently shifts every row.` |

Effect: P2 fixed 55 → 54, P2 decision 0 → 1, and COMP-11 appears in REPORT's
"Open P2s that need you", where it belongs.

### C2 — statuses that record real code changes but are scored "logged" (should fix)

| file | ID | old first words | new first words |
|---|---|---|---|
| `stage3/applications.md` | APPS-17 | `decided: URL stays required (it seeds the dedup id); the message now says why…` | `fixed + decided: URL stays required (it seeds the dedup id); the message now says why…` |
| `stage3/companies.md` | COMP-17 | `decided 2026-09-02: the accent border+wash hover is deliberate and now unified — the URL ✕ …` | `fixed + decided 2026-09-02: the accent border+wash hover is deliberate and now unified — the URL ✕ …` |
| `stage3/cover-letters.md` | CL-24 | `decided 2026-09-02: keep all except (d); contact rows in the cover-letter, résumé and persona editors now split 45/55 …` | `fixed (d) + decided 2026-09-02: keep all except (d); contact rows … now split 45/55 …` |
| `stage3/persona-stats.md` | STAT-17 | `(a) and (d) fixed + verified after rebuild: no hover on the Funnel/Flow, period and Type ▾ pills; …` | `fixed (a, d) + decided keep (b, c, e): no hover on the Funnel/Flow, period and Type ▾ pills; …` |
| `FINDINGS.md` | F-006 | `docs fixed; decided 2026-09-02: keep restart-only (no --reload), the watcher could restart mid-scrape.` | `fixed (docs) + decided 2026-09-02: keep restart-only (no --reload), the watcher could restart mid-scrape.` |

Effect: fixed +5, logged −5. Each of these five really did change code or docs.

### C3 — the systemic one: "decided keep" and "closed" have no bucket (recommended)

53 further statuses are resolved by a recorded user decision (`decided … keep`) or by fact
(`closed: …`), yet the report prints them under **"Logged only"**, which reads as
"nobody looked at it". This is the single biggest distortion in `REPORT.md`: the
"Logged only" column is ~90 % settled work.

Rather than rewrite 53 status lines, change the classifier — one line in
`tools/report_gen.py:21`:

```python
kind = ("fixed"    if st.startswith("fixed")
   else "decision" if "needs decision" in st or "needs your" in st or st.startswith("awaiting")
   else "decided"  if st.startswith("decided") or st.startswith("closed")
   else "logged")
```

…and add a **Decided / closed** column to the two tables it writes. Expected result on the
current files (after C1 + C2): **fixed 231 · needs decision 5 · decided/closed 53 · logged 0**.
A genuinely empty "logged" column is the correct outcome — every finding in this pass has
been resolved one way or the other.

### C4 — one status has no owner file at all

`stage4/settings-roundtrip.md` ends with an unnumbered observation ("`POST /settings` with
an unknown key is accepted … P4, needs decision whether to reject unknown keys"). The file
is not in `report_gen`'s glob and the observation has no `### ID` heading, so it is counted
nowhere. Give it an id in `stage3/settings.md`:

```
### SET-28 · P4 · POST /settings accepts an unknown key (no allow-list)
**Where** `backend/api/routes_settings.py:51-54`
**Actual** the UI cannot produce one, but the API writes any key it is handed.
**Status** needs decision — reject unknown keys, or keep the open write path.
```

---

## (d) Missed — defects seen in the code while verifying, not filed by the pass

Only things I actually read at HEAD. No speculation.

### R2-A-01 · P3 · Native `window.confirm` survives on four screens after the pass declared them gone

**Where** `Applications.jsx:123` (discard a dirty Log modal), `:195` (delete an
application), `JobFeed.jsx:339` (ignore a company everywhere), `Searches.jsx:467`
(delete a search), `Settings.jsx:401` (rotate the webhook secret), `:915` (remove a
catalog model).

**Actual** `ConfirmDialog.jsx` exists and is imported by exactly three files —
`Companies.jsx`, `ResumeEditor.jsx`, `CoverLetterEditor.jsx`. COMP-28's status says
"no native dialogs left on the screen" and the Résumés P3/P4 commit (`10c434d`/`a858334`)
says "shared Escape hook + ConfirmDialog, native confirms removed" — both true, but only
for their own screens. The remaining six sites are the same interaction (destructive
confirm) rendered by the browser instead of the app, so the two most destructive actions
in the product (delete an application, ignore a company everywhere) look less considered
than deleting a résumé does. APPS-22's own status ("Escape/close on a dirty Log modal
asks 'Discard this application?'") describes one of them approvingly.

**Proposed** either convert the six to `ConfirmDialog` (it already takes
`{title, body, confirmLabel, danger, onConfirm, onCancel}`), or record a decision that
native confirms are acceptable outside Companies/Résumés/Cover Letters — but the two
should not silently coexist.

### R2-A-02 · P4 · Searches' numeric payload has none of the clamping COMP-12 added to Companies

**Where** `Searches.jsx:144` — `max_pages: parseInt(d.max_pages) || 50`,
`min_fit_score: parseInt(d.min_fit_score) || 0`; the inputs at `:236`/`:243`/`:244`
are bare `type="number"` `Cell`s with no `min`/`max`.

**Actual** COMP-12 was fixed by clamping the Companies drawer to the bounds its own
input declares (`Companies.jsx:560`, `Math.min(20, Math.max(1, …))`, input `min={1}
max={20}` at `:658`). The Searches editor has the same class of control and no clamp:
`max_pages` typed as `0` silently becomes `50` (`|| 50` swallows the zero — the very bug
SRCH-12 fixed for `hours_old` by introducing `num()`, then did not apply here), a
negative page count is sent through, and the label "Results wanted · 20–500" (`:243`)
advertises a range nothing enforces on either side of the wire.

**Proposed** route `max_pages`, `min_fit_score` and `results_wanted` through the same
clamp-to-declared-bounds treatment as COMP-12, and put the `min`/`max` on the inputs so
the label and the control agree.

### R2-A-03 · P4 · 48 silent `.catch(() => {})` in `frontend/src/v2` after a pass whose headline fix was "toasts on every failure path"

**Where** `frontend/src/v2/*.jsx`, 48 occurrences.

**Actual** APPS-01 explicitly leaves one behind (`Applications.jsx:612`, the Log modal's
résumé chip list) and says so in its status. The other 47 were never counted. Many are
deliberate and correct — the `/monitor/active` pollers, the auxiliary count fetches
(`/jobs/sources/list`, `/jobs/verdicts/list`) — where a toast per poll tick would be
worse than silence. But the pass fixed this class one screen at a time by inspection
(SRCH-04, COMP-04, APPS-01, PERS/STAT toast wiring) and never produced the list, so
nobody knows which of the 47 are decisions and which are the next APPS-01.

**Proposed** one sweep that tags each site `// silent: <reason>` or converts it; the
count then becomes an assertable number rather than a guess. Cheap, and it retires the
whole category instead of re-finding it screen by screen next round.

---

## Totals after this audit

| | count |
|---|---|
| Findings reconciled | 289 |
| `fixed` statuses | 227 → **226 real** (COMP-11 is not fixed) |
| …verified in code at HEAD | 190 (106 automatic + 84 by hand) |
| …narrative only, R2 smoke should re-observe | 36 |
| …false | **1** (COMP-11) |
| Decided-keep / closed, attributed | 58 |
| Genuinely needing your decision | 4 filed (APPS-20, COMP-26, CL-28, RES-32) + COMP-11 + the stage4 settings observation = **6** |
| New defects filed here | 3 (R2-A-01..03) |
