# v2 verification round 2 — plan

Started 2026-09-03 (evening). Orchestrator: Fable (this session). Workers: Opus / Sonnet only.
Resume rule: continue from the first unticked box. Each stage writes its own file under `v2-testing/round2/` incrementally, so a killed agent leaves partial output that the next one extends.

## Fixed inputs
- Baseline DB dump: `backups/round2_baseline_20260903.dump` (taken before R1). Restore to it in R5.
- LLM settings already on Sonnet: `llm_model=claude-sonnet-5`, `llm_provider=claude_code`; all per-feature `*_llm_model` empty (fall back to primary). Nothing to change or restore.
- Budget: ≤20 real LLM calls in R3. R1/R2/R4 make none.
- Harness: `v2-testing/tools/h.py` (copied to `/tmp/v2t/h.py` in the backend container). Docker from Git Bash: `DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"; export MSYS_NO_PATHCONV=1; "$DOCKER" compose …`. Scripts: write locally, `compose cp` into `backend:/tmp/v2t/`, `compose exec -T backend python /tmp/v2t/x.py`. Backend edits need `compose restart backend`; frontend edits need `compose build frontend && compose up -d frontend`.
- Never push. Commits by the orchestrator only, bare messages.

## Stages
- [x] **R0 baseline** — dump taken, settings read, tree clean at `1fd6152`.
- [x] **R1 audit** (Opus) → `round2/audit.md`. Reconcile every finding file (`stage3/*.md`, `FINDINGS.md`, `stage5/cross-cutting.md`, `stage4/settings-roundtrip.md`) against the code at HEAD: every `fixed` status names a commit whose diff actually contains the change; every `decided keep` has a user decision recorded; anything `logged` without a decision is listed; items mentioned in chat but never filed are filed. Also the four open decisions (RES-32, APPS-20, COMP-26, CL-28).
- [ ] **R2 smoke** (Sonnet) → `round2/smoke.md`. No LLM calls, read-only. Every v2 route and every v1 route: loads, zero console/page errors, both themes, 1440×900 and 1024×700, rail counts present, primary controls present and enabled, deep links (`?job=`, `?company=`, `#runs`, `/v2/resumes/{id}`, `/v2/cover-letters/{id}`), API-failure path per screen (stub one GET with 500 → error row/toast, no white screen), keyboard (Escape closes every open modal/drawer/menu; Tab reaches the first three controls).
- [ ] **R3 happy path** (Opus) → `round2/happy-path.md`. Real end-to-end flows with the DB, ≤20 LLM calls, all scratch rows prefixed `ZZTEST` and deleted at the end:
  1. Search: create keyword search → Test (real JobSpy/Indeed is not public-API — stub) → edit → run interval → delete.
  2. Company: add with a public Greenhouse URL (Anthropic exists — use a second public board, e.g. `boards.greenhouse.io/…`) → Test scrape (real) → Run scrape (real) → jobs appear in Feed with the company → delete company.
  3. Feed: filter → open detail → Score (real LLM, 1 call) → Save → Applied → Application auto-created + company auto-created → undo toast path.
  4. Applications: log manual application (409 on duplicate) → stage to Interview (interview row) → Offer → Rejected → history/Sankey/KPI update → delete.
  5. Résumés: new base from scratch → edit header/experience/skills (autosave) → Tailor to a job (real LLM) → toast + copy appears → Score (real LLM) → Tailored chip in Feed → Review changes → freeform tailor from pasted JD (real LLM) → job-less score (real LLM) → PDF download (200, PDF magic bytes) → delete copy → delete base.
  6. Cover letters: generate for the tailored copy (real LLM) → edit paragraph → PDF → regenerate with another voice (real LLM) → delete.
  7. Persona: edit contact/preferences (autosave) → add Q&A → `POST /autofill/answer` (real LLM, 1–2 calls) → save to bank → verify count.
  8. Settings: change threshold/interval/toggle → reload → persisted; scheduler reconfigured (monitor shows new interval); revert.
  9. Stats: counts/funnel reflect the rows above; Run history shows the scrapes; Activity log entries.
  10. Extension endpoints via API: `POST /applications` from the popup shape, `POST /jobs/linkedin-import` with an empty list (no Voyager call), `POST /persona/qa-bank`.
- [x] **R4 text candidates** (Opus) → `round2/text-candidates.md`. Every user-facing string in `frontend/src/v2/*.jsx` longer than ~6 words (toasts, empty states, helper/sub-lines, tooltips, modal copy, settings help/info) listed as `file:line | current text | flag` where flag ∈ {mannered, metaphor, hedge, long, fine}. No rewrites.
- [x] **R4b text suggestions** (Fable) → `round2/text-suggestions.md`. Plain rewrites for every flagged line; prompt: "Avoid mannered prose, say things plainly. No metaphors or figures of speech." Suggestions only — nothing applied.
- [ ] **R5 close** — `v2-testing/REPORT-round2.md` (open items, considerations, text suggestions), restore DB from the baseline dump, confirm ZZTEST rows gone, commit.
