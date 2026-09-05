# Round 4 — R4-T1-01..04 · existing-jobs collision report

Read-only. Produced 2026-09-05 against the live `jtrakproject` database by loading
`backend/scraper/_shared/dedup.make_external_id` (post-fix) inside the backend
container and re-hashing every `jobs` row. **`SELECT` only — nothing was updated,
merged or deleted, and no backup was needed.**

Script: `scratchpad/dup_report.py` + `scratchpad/dup_shift2.py` (run with
`docker compose exec -T backend sh -c "cd /app && python -" < <script>`).

## The change under test

`_canonical_for_hash()` now folds five spellings before hashing: scheme
(`http`→`https`), a leading `www.`, host/path case (already folded), a trailing
slash, the ATS `/apply|/application|/thanks` suffix that a trailing slash used to
hide, and query-param order. `_normalize_url()` — which is what the company-page
scraper stores as `Job.url` — is **unchanged**, so stored URLs keep the bytes the
board handed us.

## 1 · Rows that collide onto one id today

| measure | value |
|---|---:|
| jobs in the table | 19,190 |
| distinct `external_id` stored today | 19,190 |
| distinct ids under the new normalisation | 19,189 |
| **colliding groups** | **1** |
| **redundant rows inside those groups** | **1** |

**One duplicate pair in 19,190 rows.** Both examples below are the complete list —
the report asks for up to 20 and there is exactly 1.

### Example 1 of 1 — trailing slash + `lever-source` tracking

Canonical: `https://revolut.com/careers/position/04bf0992-3b62-48c4-a20c-aa744c8ad6e1`
New shared id: `6ad3d751…ca6f2c0`

| # | url | stored `external_id` | source | status | discovered |
|---|---|---|---|---|---|
| A | `https://www.revolut.com/careers/position/04bf0992-3b62-48c4-a20c-aa744c8ad6e1/?source=Indeed&lever-source=Indeed` | `db30707f…0ae9d5b5` | jobright | skip | 2026-05-13 |
| B | `https://www.revolut.com/careers/position/04bf0992-3b62-48c4-a20c-aa744c8ad6e1` | `0c8f5563…2deee195` | jobright | skip | 2026-05-14 |

Same company, same title ("Credit Product Manager"), same posting id in the path;
A carries a trailing slash and Indeed referral params, B does not. Exactly the
`R4-T1-01` shape. Both are already `skip`, so nothing user-facing is affected.
**No action taken.**

## 2 · The bigger number: ids that *shift* without colliding

This is the part that matters more than the single duplicate above, and it is the
risk `T1.md`'s own "Notes for the fix loop" flagged.

| measure | value |
|---|---:|
| rows whose recomputed id **differs from the stored one** | **6,843 of 19,190 (35.7 %)** |
| …of which also carry a `content_hash` | 6,842 (99.99 %) |

Why they shift:

| cause | rows |
|---|---:|
| `www.` prefix | 5,934 |
| `http://` scheme | 432 |
| trailing slash | 379 |
| query-param order | 96 |
| apply-suffix behind a slash / case | 2 |

By status: `ignored` 4,355 · `skip` 2,409 · `applied` 77 · `new` 2.

**What this means.** Stored `external_id` values are not rewritten by this change.
If one of those 6,843 postings is scraped again, layer 1 (`external_id`) will no
longer match the stored row, so the insert falls through to layer 2
(`content_hash` = company + title), which 6,842 of the 6,843 rows have. Layer 2
catches it, so the practical exposure is **one row** — the single posting with no
`content_hash`. The mitigation is already in the design; it is just doing more
work than it used to.

**Recommended follow-up (not done here — it is a write, and the live DB was
read-only for this pass).** A one-shot backfill that recomputes `external_id`
for every row, so layer 1 keeps carrying the load and the 6,843 stop depending on
the company+title fallback. It cannot be a plain SQL `UPDATE` — the canonical
form is Python — so it belongs in `backend/seed.py` as a guarded one-shot
(`SELECT id, company, title, url`, recompute, `UPDATE … WHERE id = …`, skipping
any row whose new id already exists on another row, and logging the count). Take a
`pg_dump` first, per the project rule. Until then nothing is broken; the fallback
layer covers it.

## 3 · What did not change

- Identity params still survive: Indeed `jk`/`vjk`, Glassdoor `jl`,
  Dice/Monster `jobId`, LinkedIn `currentJobId` on search shapes (and correctly
  dropped on `/jobs/view/<id>`). Host matching stays strict —
  `indeed.com.evil.net` gets no identity protection.
  Pinned by `test_r4_dedup.py::test_identity_params_match_subdomains_only_not_lookalikes`.
- Distinct postings stay distinct: the 9-URL separation set still yields 9 ids.
- Malformed URLs still hash without raising (8 shapes).
- `Job.url` is byte-for-byte what the scraper produced —
  `test_r4_dedup.py::test_normalize_url_keeps_the_trailing_slash_the_board_gave_us`
  pins that the folding lives in the hash only.
- R4-T1-05 (percent-encoded unreserved chars) and R4-T1-06 (`content_hash`
  internal whitespace) are deferred to v2.1 and keep their xfail-strict tests.

## 4 · Backfill run

Ran the §2 follow-up. Backup taken first: `backups/pre_dedup_backfill_20260905.dump`.
Script: `backend/scripts/backfill_external_id.py` (new — reads every row with
`SELECT id, company, title, url, external_id`, recomputes via
`dedup.make_external_id`, batches UPDATEs 1000 at a time in one transaction per
batch; `--dry-run` prints counts only). Run inside the backend container:

```
docker compose exec -T backend sh -c "cd /app && python -m backend.scripts.backfill_external_id --dry-run"
docker compose exec -T backend sh -c "cd /app && python -m backend.scripts.backfill_external_id --apply"
```

| measure | dry-run (pre) | apply | dry-run (post, verification) |
|---|---:|---:|---:|
| total jobs | 19,190 | 19,190 | 19,190 |
| unchanged | 12,347 | 12,347 | 19,189 |
| updated | 6,842 (would) | 6,842 (committed, 7 batches) | 0 (would) |
| skipped-collisions | 1 | 1 | 1 |

Matches the report's estimate: 6,842 updates + 1 skipped collision = 6,843,
the exact "rows whose recomputed id differs" figure from §2. The
post-`--apply` dry run confirms convergence — recomputing again now yields 0
changes and the same single, expected collision.

**The one collision** (same pair as §1's example): row
`30aae283-c41a-4064-a13e-e8395c7de37d` (url with the trailing slash and
`source=Indeed&lever-source=Indeed`, `status=skip`) was updated to the new
shared id `6ad3d751…ca6f2c0`. Row `4fa8ae60-0ff8-4c5a-b8af-a035a3cf8e98`
(canonical url, no query, `status=skip`) was left on its old stored id
`0c8f5563…2deee195` — skipped, not merged, not deleted. Full list:
`v2-testing/round4/backfill-collisions.md`.

**Post-run checks:**
- `SELECT COUNT(*), COUNT(DISTINCT external_id) FROM jobs` → `19190 | 19190`
  (constraint intact, no duplicates introduced by the update itself).
- Total job count unchanged at 19,190 (no scrapes landed mid-run).
- `GET /api/jobs?limit=5` → `200`, `"total":19190`, rows well-formed.

No commit made per instructions; the working tree carries
`backend/scripts/backfill_external_id.py`,
`v2-testing/round4/backfill-collisions.md`, and this section.
