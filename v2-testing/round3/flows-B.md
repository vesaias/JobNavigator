# Round 3 — flows B (the document loop)

Tested: 2026-09-03, branch `v2-redesign` @ `69d36b1`, Playwright inside the backend container vs `http://caddy`, light theme unless noted, 1440×900.
Scripts: `scratchpad/zzb_*.py` (copied to `backend:/tmp/v2t/`). Prefix for every row created: **`ZZB`**.
Findings numbered `R3-B-NN`.

## Baseline (captured before anything was touched, `zzb_00_recon.py`)
- Résumé shelf: 4 bases (`PM` 45 copies, `TPgM` 0, `PjM` 2, `PjM FinTech` 0), 49 live copies, 296 archived.
- Cover letters: 16. Persona `qa_bank`: 18 entries.
- Persona snapshot → `/tmp/v2t/zzb_persona_before.json`; settings snapshot → `/tmp/v2t/zzb_settings_before.json`.
- **Target job (not modified beyond the Tailored score chip):** `73503701-de3c-4eb9-ab3e-8eb42c7b1866` — *Product Manager, Claude Tag* @ **Anthropic**, `status=new`, description 6198 chars, `cv_scores = {"PM": 40}` (no `Tailored` key yet), url `https://job-boards.greenhouse.io/anthropic/jobs/5251866008`.
- Settings that will be changed later, read first: `scoring_default_depth`, `fit_score_threshold`, `scrape_interval_minutes=3500`, `h1b_cron="0 2 * * 0"`, `prompt_caching_enabled=true`.

---
Scripts, in order: `zzb_00_recon`, `zzb_01_base`, `zzb_02_import`, `zzb_03_sections`, `zzb_03b_sections`, `zzb_04a_tailor`, `zzb_04b_review`, `zzb_04c_score`, `zzb_04d_feed`, `zzb_05_freeform`, `zzb_06_pdf`, `zzb_06b_pdflinks`, `zzb_07a_cl`, `zzb_07b_cl`, `zzb_07c_regen`, `zzb_07d_tracer`, `zzb_08_persona`, `zzb_08b_autofill`, `zzb_09_settings`, `zzb_09b_depth`, `zzb_10_cleanup`, `zzb_10b_delete`, `zzb_10c_sweep`.

## Step 1 — New base from scratch + autosave  ✔
Script `zzb_01_base.py`. LLM calls: 0. UI throughout, API to confirm.

**Did** `/v2/resumes` (header `Résumés · 4 bases · 49 tailored copies live under their jobs · 296 archived`) → `+ New résumé` → modal `New base résumé` → typed `ZZB Base` → `Create from scratch`.
**Asserted**
- Routed to `/v2/resumes/54acb867-e8a1-481e-a84c-8e49fde0dbfb`; `POST /resumes` 201.
- Header bar reads `‹ Résumés | BASE | ZZB Base | saved just now · autosaves`; band `Base résumé · 0 tailored copies · editing here changes future tailoring only`.
- Seven accordions render in order Header / Summary / Experience (0) / Skills (0) / Education (0) / Projects (0) / Publications; the open Experience shows the empty note `No experience yet — Empty sections are skipped in the PDF — nothing prints until you add one.`
- **Autosave**: opened Header, typed `ZZB Dana Okonkwo` into *Full name* (16 keystrokes at 60 ms). Exactly **1** `PATCH /resumes/{id}` fired, **440 ms after the last keystroke** (design: 500 ms trailing debounce — the measurement starts at the last keypress event, so 440 ms is the debounce minus event-loop slack). Status went `Saving…` → `saved just now · autosaves`.
- `GET /resumes/{id}` → `name="ZZB Base"`, `is_base=true`, `json_data.header.name="ZZB Dana Okonkwo"`.
- Console: 0 errors, 0 page errors, 0 ≥400 responses, 0 failed requests.

## Step 2 — Export a base's PDF, import it back through the Add modal (real LLM parse)  ✔
Script `zzb_02_import.py`. **LLM #1** — `pdf` purpose, PDF parse, 22.6 s, success.

**Did** `GET /resumes/22ce0e5b…/pdf` (base `PM`) → saved as `ZZB Import PM.pdf` → `/v2/resumes` → `+ New résumé` → typed `ZZB Import PM` → `Import PDF ↑` file picker.
**Asserted**
- Export: **200**, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="ViktorEsadze_PM_Resume.pdf"`, 116 294 bytes, magic `%PDF-`, 0.6 s.
- Busy state: `Parsing…` appeared on the **import** button within 150 ms and the *other* button kept its own label `Create from scratch` (the RES-18 fix holds).
- `POST /resumes/import-pdf` → 201 after 22.6 s; the app routed straight to the row the endpoint created (one row, no duplicate — the RES-27 fix holds: exactly one `POST` in the network log).
- New base `1b042a4d-10b0-4fa3-a0ac-048c235d42c5`, `name="ZZB Import PM"` (filename-derived, matched the typed name so no rename `PATCH` was needed), `is_base=true`.
- Sections filled by the LLM: `header.name="VIKTOR ESADZE"`, 4 contact items, summary 615 chars, **3** experience roles (first: *Senior Product Manager · Additiv · May 2022 – Present · 7 bullets*), skills `{Certifications, Technical, Tools, Languages}`, 2 education entries, 0 projects, 0 publications (the source résumé has none). Editor rendered `Experience (3)` with the role expanded.
- Console clean.

## Step 3 — every section editor on `ZZB Base`  ✔ (2 findings)
Scripts `zzb_03_sections.py` (header/summary), `zzb_03b_sections.py` (experience/skills/education/projects). LLM calls: 0. UI throughout, `GET /resumes/{id}` after every change.

| section | what was done | API reached within | result |
|---|---|---|---|
| Header · name | typed 16 chars | 1 PATCH @ 440 ms | `header.name` ✔ |
| Header · contact rows | `+ Add contact item` ×3, filled text+URL, stub box appeared **only** on the non-`mailto:` row (1 of 3) and took `li` | 1.02 s | `[{Berlin, DE},{LinkedIn,https://linkedin.com/in/zzb-dana,stub li},{zzb@example.com,mailto:…}]` ✔ |
| Header · reorder | `▼` on row 0 | 1.4 s | `[Berlin, LinkedIn, mail]` → `[LinkedIn, Berlin, mail]` ✔ |
| Header · remove + undo | `✕` on row 3 → dark undo toast `Removed contact item · Undo · ✕` → Undo | 1.4 s | 3 → 2 → **3, byte-identical to before** ✔ |
| Summary | typed 61 chars | 1.00 s | `summary` ✔, meta reads `61 characters` |
| Experience | `+ Add experience`, filled Company/Title/Location/Date, `+ Add bullet` ×3, typed each | 1.12 s | one role, 3 bullets ✔; header row reads `⌄ Experience (1)` |
| Experience · bullet remove + undo | `✕` on bullet 2 → `Removed bullet · Undo` → Undo | 1.4 s | 3 → 2 → **3 restored in order** ✔ |
| Experience · ● marker | — | — | `changed by tailoring` count = **0** on a base ✔ |
| Skills | `+ Add skill row` ×2, renamed `Skill 1`→`Tools`, typed values | 1.1 s | `{Tools: "Jira, Figma", Skill 2: ""}` ✔ |
| Skills · collision | renamed `Skill 2`→`Tools`, blurred | — | **refused**: error toast `“Tools” already exists — renaming onto it would erase its values.`, the input snapped back to `Skill 2`, and `skills` was unchanged in the API ✔ |
| Skills · rename + reorder | → `Methods`, then `▼` on row 0 | 1.2 s | `{Tools, Methods}` → key order `["Methods","Tools"]` ✔ (the `flag_modified` fix for order-only writes holds) |
| Education | `+ Add education`, School/Location/Degree/Years | 1.1 s | one entry ✔ |
| Projects | `+ Add project`, Name/URL/Description, `+ Add bullet` + text | 1.1 s | one project with 1 bullet ✔ |
| Projects · remove + undo | `Remove project` → `Removed project · Undo` → Undo | 1.4 s | `[]` → **project restored with its bullet** ✔ |

Console clean on every pass (0/0/0/0).

### R3-B-01 · P3 · The header has no job-title/headline field, and Experience has no reorder at all
**Where** `frontend/src/v2/ResumeSections.jsx:190-231` (`HeaderEditor`), `:233-311` (`ExperienceEditor`)
**Repro** Open any résumé → Header: the only fields are *Full name* and the contact-item rows. Open Experience: roles and bullets have `✕` and `+ Add`, but no `▲/▼`.
**Actual** `[title="Move up"]` count inside Experience = **0**; no `Title`/headline input in Header (`header.title` exists in real résumé data — the file's own comment at `ResumeSections.jsx:9` says live résumés "carry keys these editors don't render (e.g. `header.title`)"). Contact items and skill categories *do* have `▲/▼`.
**Expected + why** `Resumes Home D.dc.html:258` and `:344` give `▲/▼` only to contact items and skills, so the code matches the design — but a résumé editor where roles and bullets can be added and deleted yet never moved forces a delete-and-retype to change order, and `header.title` round-trips through the API and the PDF while being invisible and uneditable in v2.
**Status** needs decision: add reorder + a header title field, or accept the design's scope.

### R3-B-02 · P3 · "Tailoring changes — already applied" is not true of suggested bullets
**Where** `frontend/src/v2/ResumeEditor.jsx:822-823` (modal copy) and `:838` (the `APPLIED` chip) vs `backend/api/routes_resumes.py:930-931`, `:504-506`
**Repro** Tailor a base for a job → open the copy → `⋯ → Review changes` **without** touching anything → read `GET /resumes/{copy}`.
**Actual** The three change rows were `SUMMARY`, `EXPERIENCE · ZZB LABS · SUGGESTED BULLET` ×2, all chipped `APPLIED`, under the header *"Tailoring changes — already applied / These landed automatically."* But before the review the copy's `json_data.experience[0].bullets` had **3** entries — the two suggested bullets lived in `experience[0].suggested_bullets`, which no résumé template renders (`grep -rn suggested backend/resume_templates/` = 0 hits) and which the backend's own comment calls "still pending accept/decline". Only after `Done reviewing` did `bullets` grow to **5**.
**Expected + why** A change the user is told has "landed automatically" must be in the document and in the PDF. Either label suggested bullets `SUGGESTED` / "not yet in the PDF" in the modal, or commit them at tailor time like the summary and the rewritten bullets.
**Proposed fix** Give `kind === 'suggested'` rows their own chip (`suggested`) and button (`Keep` / `Drop`), and soften the modal header when any suggested row is present.

## Step 4 — Tailor `ZZB Base` for the Anthropic job  ✔
Scripts `zzb_04a_tailor.py`, `zzb_04b_review.py`, `zzb_04c_score.py`, `zzb_04d_feed.py`.
**LLM #2** tailor (15.4 s, completed) · **LLM #3** chained full score fired automatically by the tailor (`analyze_job`, 28.6 s) · **LLM #4** `Score again · light` (17.9 s) · **LLM #5** `Score again · full` (46.3 s).

**Did / asserted**
1. `✦ Tailor for a job…` → modal `Tailor ZZB Base for a job`, searched `Claude Tag`, picked the Anthropic row (`Anthropic · new`).
2. **Chain-score line present** (the R2-H-09 fix): `Also scores the copy afterwards at full depth · 1 more LLM call · change under Settings › AI` — and it only appears once a job is picked. The `POST /resumes/tailor` response body read `{"run_id": "cceb8040…", "status": "running", "chain_score": "full"}`, matching `tailor_auto_quick_score="full"` in this DB. ✔
3. Progress toast `Tailoring for Anthropic… runs in the background.`; success toast **17.6 s** later: `✓ Tailored copy for Anthropic is ready. — Open ↗`.
4. `Open ↗` navigated to the copy `6af7a7c7-23ca-4640-910c-5fbc15c0e4c6`. Band: `Tailored for Anthropic — Product Manager, Claude Tag │ −12 based on ZZB Base ↗` (delta and lineage link both render; `parent_id` resolves the base's real name, so the R2-H-10 fix holds). API: `is_base=false`, `parent_id=<ZZB Base>`, `job_id=<Anthropic job>`, name `ZZB Base → Anthropic — Product Manager, Claude Tag`; the summary was genuinely rewritten against the JD and company/title/dates were preserved verbatim.
5. Run history: `tailor_resume completed 15.4 s — "Created 'ZZB Base → Anthropic — …' - full score chained"`, then `analyze_job completed 28.6 s — "Product Manager, Claude Tag - best 28 (PM), full"`. Both carry a `result_summary` (the round-2 backend fix holds).
6. **Review changes** — the `⋯` menu on a copy = `Re-tailor… · Score again · light · Score again · full · Review changes (3 applied) · Cover letter · Mark applied · Delete copy`. Modal listed `SUMMARY`, `EXPERIENCE · ZZB LABS · SUGGESTED BULLET` ×2; footer `All 3 changes live · decline any to restore the base text`. Declined the SUMMARY row → footer became `1 declined — base text restored · the rest stay` → `Done reviewing`. After: the copy's `summary` is **byte-equal to the base's** and the other two changes stayed (see R3-B-02 for what "stayed" means for suggested bullets). ✔
7. **Scores** — `Score again · light` → toast `Scoring (light) — runs in the background.`, run 17.9 s, `Tailored 35`. `Score again · full` → run 46.3 s, `Tailored 35`, completion toast `✓ Scored: 35 (-5 vs base)`. Job `cv_scores = {"PM": 40, "Tailored": 35}`, `tailored_resume_id` = the copy.
8. **Feed** — `/v2/feed?job=73503701…`: the row carries the `✦` *Open tailored résumé* link, the detail header carries `✦ Open tailored ↗`, and the score band reads `40 │ PM │ 27% keywords │ 4 of 12 requirements met │ 2 reports`. Expanding it shows two tabs, `PM (40)` and `✦ Tailored (35)`; the Tailored tab renders the full report — narrative summary, `SCORE BREAKDOWN`, `KEYWORD COVERAGE 28%`, `REQUIREMENT MAPPING 6 of 13 met`. ✔
   *Note (not a defect):* the collapsed band shows the **best** score, which here is the base `PM 40`, so the word "Tailored" is only visible once the band is expanded. In round 2 the tailored score was the higher one, which is why it read as a top-level chip there.
9. Console clean on the résumé screens. On `/v2/feed` the only console errors come from the **external** `job-boards.cdn.greenhouse.io` page the detail panel embeds (React hydration #418/#425 inside their bundle); with that host blocked via `page.route`, the console is 0/0/0/0.

## Step 5 — Freeform tailor from a pasted description + job-less score  ✔ (round-2 R2-H-11 now passes)
Script `zzb_05_freeform.py`. **LLM #6** freeform tailor (20.4 s) · **LLM #7** job-less `Score again · light` (21.1 s).

**Did** `ZZB Base` → `✦ Tailor for a job…` → pasted a **295-word** JD (*Director of Platform Product, Developer Experience*) into `…or a freeform job description` → `✦ Tailor`.
**Asserted**
- **No chain-score line** when only a JD is pasted, and `POST /resumes/tailor` returned `{"chain_score": "off"}` — matching `if chain_depth and job_id` in the backend. ✔
- Progress toast `Tailoring from a pasted description… runs in the background.`
- **The completion toast fired** — `✓ Tailored copy from your pasted description is ready. — Open ↗` at 21.2 s. (Round-2 finding **R2-H-11** — "the freeform completion toast did not fire" — no longer reproduces.) ✔
- Run `tailor_resume completed 20.4 s — "Created 'ZZB Base (tailored)'"`. New copy `4e15f18f-ea32-4735-9880-a2d292bf43b8`, `job_id = null`, `parent_id = ZZB Base`.
- `json_data._tailor_context` present, keys `["job_description","source"]`, `source="freeform"`, and its `job_description` is **byte-equal** to the pasted text. ✔
- Headline: `Tailored from a pasted description │ based on ZZB Base ↗` — the lineage label names the **base**, not the copy (R2-H-10 fix holds). Band also reads `6 reviewable changes · tracers: LinkedIn 0` with a `Review 6 changes` action.
- `Score again · light` → toast `Scoring (light) — runs in the background.` → 21.1 s → `json_data._score = {"Tailored": 26, "scored_at": "2026-09-03T08:29:30Z"}`, completion toast `✓ Scored: 26`, and after a reload the band ring shows **26**. ✔
- Console clean.

## Step 6 — PDFs for the base and both copies, tracked links  ✔
Scripts `zzb_06_pdf.py`, `zzb_06b_pdflinks.py` (link extraction via pdfplumber annots). LLM calls: 0.
Tracer settings in play: `tracer_links_enabled=true`, `tracer_links_base_url="https://viktoresadze.com"`, `tracer_links_url_style="param_jobid"`.

| résumé | PDF | filename | `GET /tracer-stats` | URL inside the PDF |
|---|---|---|---|---|
| `ZZB Base` | **200**, `application/pdf`, `%PDF-`, 82 495 B | `ZZBDanaOkonkwo_ZZBBase_Resume.pdf` | 1 row · `LinkedIn → https://linkedin.com/in/zzb-dana` · token `0li` · 0 clicks · active | `https://viktoresadze.com/?cv=0li` |
| job copy | **200**, `%PDF-`, 85 266 B | `ZZBDanaOkonkwo_ZZBBase_Resume_20892.pdf` (job short-id) | 1 row · token **`20892li`** | `https://viktoresadze.com/?cv=20892li` |
| freeform copy | **200**, `%PDF-`, 86 726 B | `ZZBDanaOkonkwo_ZZBBase(tailored)_Resume.pdf` | 1 row · token `tkjlah` (random — job-less and `0li` was already taken by the base, exactly the documented fallback) | `https://viktoresadze.com/?cv=tkjlah` |

- **The base's header URL is rewritten in every copy, and each owner gets its own token** — the three PDFs carry three different `?cv=` tokens for the same destination, so a click is attributable to the specific document that was sent. ✔
- `mailto:zzb@example.com` is left alone and the *project* URL `https://example.com/zzb` is left alone — only `header.contact_items` are rewritten (`routes_resumes.py:344`). Correct, and worth knowing.
- PDF text confirms the right content per document: the job copy carries the base summary (I declined that change in step 4), the freeform copy carries its own rewritten summary.
- **`GET /resumes/{id}/preview` returns the *un-rewritten* HTML** (raw `https://linkedin.com/in/zzb-dana`) — deliberate: `preview_resume` calls `_render_html` directly at `routes_resumes.py:1053` while `export_pdf` rewrites first at `:1070`. The editor's preview pane uses `/pdf`, not `/preview`, so what the user sees is the tracked version. Noted, not filed.

## Step 7 — Cover letter from the job-linked copy: generate → edit → regenerate → PDF  ✔ (1 finding)
Scripts `zzb_07a_cl.py`, `zzb_07b_cl.py`, `zzb_07c_regen.py`, `zzb_07d_tracer.py`.
**LLM #8** generate (15.7 s) · **LLM #9** regenerate, different voice **and** length (25.7 s).

1. **Entry** — résumé copy → `⋯ → Cover letter` → `/v2/cover-letters` with both pickers pre-filled from the `?resume=&job=` deep link (the route consumes and clears the params). `✦ Generate cover letter` → `POST /cover-letters/generate` → run `generate_cover_letter completed 15.7 s — "Generated letter for Anthropic — Product Manager, Claude Tag (professional voice)"`, success toast `✓ Cover letter ready.` at 16.6 s.
2. **Row** — new letter `8fd7c319…`, `name="Anthropic — Product Manager, Claude Tag"`, `voice=professional`, `length=standard`, `template=garamond`, `resume_id` = **the tailored copy**, `source_name="ZZB Base → Anthropic — Product Manager, Claude Tag"`. `json_data` keys = `header/recipient/date/greeting/body_paragraphs/closing/signature`; 3 paragraphs; `greeting="Dear Hiring Team,"`; `recipient={company:"Anthropic",manager:"",address:""}`. The opening paragraph is job-specific and grounded in the copy's own facts, no invented employer.
3. **Edit a paragraph** — typed ` ZZB edit marker.` at the end of ¶3: one `PATCH` at **1.51 s**, only `body_paragraphs[2]` changed (¶1/¶2 byte-identical), status line `saved just now · autosaves`. ✔
4. **Add / reorder / remove + undo** — `+ Add paragraph` → typed ¶4 → 4 paragraphs in the API; `↑` on ¶4 → it moved to position 3 and the old ¶3 to 4; `✕` on ¶3 → undo toast `Removed paragraph · Undo` → 4→3→**4 restored byte-identical**. ✔ (extra paragraph then removed again to leave the letter at 3).
5. **Regenerate** — modal `Regenerate letter / Rewrites the whole letter for Anthropic — your edits to this draft are replaced.` **`FROM RÉSUMÉ` now reads `ZZB Base → Anthropic — Product Manager, Claude Tag · tailored copy`, not `Select a source…`** — the round-2 finding **R2-H-14 is fixed**. Picked `Storytelling` + `Detailed` → button showed `Regenerating…` → run `completed 25.7 s — "Regenerated letter for Anthropic — … (storytelling voice)"`. Read back: `voice="storytelling"`, `length="detailed"`, a genuinely different opening, the `ZZB edit marker` gone (exactly as the modal warns), and the letter **count stayed 17** — rewritten in place, no duplicate row. ✔
6. **PDF** — `GET /cover-letters/{id}/pdf` → **200**, `application/pdf`, `%PDF-`, 106 333 B, `filename="ZZBDanaOkonkwo_Anthropic_CoverLetter_20892.pdf"` (name + company + job short-id). PDF text: header, `September 03, 2026`, `Anthropic`, `Dear Anthropic Hiring Team,` then the storytelling opening. Links inside: `https://viktoresadze.com/?cv=20892li` + `mailto:` — the letter carries a tracked link too. ✔
7. **Header contact rows 45/55** — measured in both editors at 1440×900 with the same data:
   - cover-letter editor: text column **226.3 px (45.0 %)**, url column **276.6 px (55.0 %)**, computed `flex: 45 1 0px` / `55 1 0px`
   - résumé editor: **226.3 px / 276.6 px**, identical flex values. Byte-for-byte the same split. ✔
8. Console clean; the only `requestfailed` entries are the `…/pdf` blob aborts in the preview `<iframe>`, which is the documented headless-Linux artifact (no PDF viewer), not a defect.

### R3-B-03 · P2 · A résumé and its cover letter fight over the same tracer link, so one of them always shows zero
**Where** `backend/api/routes_resumes.py:398-401` (`_repoint` — sets the new owner and **nulls the other**) driven from `:1070` (résumé PDF) and `routes_cover_letters.py` (letter PDF); surfaced by `GET /resumes/{id}/tracer-stats` and `GET /cover-letters/{id}/tracer-stats`.
**Repro** Tailor a base for a job, render the copy's PDF, then generate a cover letter for the same résumé+job and render its PDF. Then `GET /resumes/{copy}/tracer-stats`.
**Actual** (measured, `zzb_07d_tracer.py`)
| after | `/resumes/{copy}/tracer-stats` | `/cover-letters/{cl}/tracer-stats` |
|---|---|---|
| résumé PDF only | 1 row, token `20892li` | — |
| cover-letter PDF | **0 rows** | 1 row, token `20892li` |
| résumé PDF again | 1 row, token `20892li` | **0 rows** |

The résumé editor's band correspondingly loses its `tracers: LinkedIn 0` segment while the letter owns the link.
**Expected + why** Sharing one token for one job is deliberate (the `_repoint` comment says so), but `TracerLink` then models ownership as an exclusive FK, so the two documents can never both report. A user asking "did anyone open my CV?" is shown *no tracked links at all* on whichever document was rendered second-to-last. No click data is lost — `TracerClickEvent` rows hang off the `TracerLink`, which survives — but per-document attribution is wrong and flips on every render.
**Proposed fix** Either give `TracerLink` both FKs at once (drop the null-out in `_repoint` and let a link belong to a résumé *and* its letter), or make the stats endpoints resolve by `(job, destination)` rather than by owner FK so both documents report the same shared counter.

## Step 8 — Persona: contact, preference, résumé bullet, **Q&A through the UI**, autofill ×2, save to bank  ✔ (1 finding, 1 round-2 item resolved)
Scripts `zzb_08_persona.py`, `zzb_08b_autofill.py`. **LLM #10** autofill @120 (3.4 s) · **LLM #11** autofill @600 (5.1 s).

Snapshot check first: all seven persona nodes were byte-equal to the recon snapshot before I touched anything (no drift from the parallel group-A run).

| what | how | API within | result |
|---|---|---|---|
| contact field | `State` `Hesse` → `Hesse ZZB` | 1.4 s | `contact.state = "Hesse ZZB"`, header flashed `Saved ✓` ✔ |
| preference | `Screening defaults` → `Notice period` `3 months` → `3 months ZZB` | 1.4 s | `preferences.notice_period = "3 months ZZB"` ✔ |
| resume_content | Experience → role 1 → `+ Add bullet` → typed | 1.5 s | `resume_content.experience[0].bullets` 9 → **10**, last = `ZZB persona bullet.` ✔ |

### The round-2 unverified item — **adding a Q&A pair through the Persona UI works**
Round 2 could not confirm this (`round2/happy-path.md`, Flow 7 "Couldn't verify"). Definitive result, measured:
1. Card header read `18 answers`. `+ Add answer` → a blank pair rendered with **both** boxes empty and **no PATCH** (the PERS-21 rule: a pair with neither half filled is kept locally only). `GET /persona` still 18.
2. Typed only the **question** (`textarea[placeholder="Question as the form asks it…"]`) → after the 500 ms debounce `qa_bank` became **19**, last entry `{question: "ZZB why do you want to work here?", answer: ""}` — a half-filled pair *is* persisted.
3. Typed the **answer** (`textarea[placeholder="Your reusable answer…"]`) → 1.61 s later the same entry carried both halves; card header `19 answers`.
4. Full page reload → still 19 entries, header `19 answers`. ✔
**Why round 2 missed it:** the two boxes are borderless auto-growing `<textarea>`s that are only reachable by their placeholder text; a positional locator lands on a résumé bullet instead. Not a product defect — the UI path is sound.

### Autofill
| call | `max_chars` | HTTP | time | answer length | within limit? |
|---|---|---|---|---|---|
| "Why do you want to work at Anthropic… first 90 days?" | **120** | 200 | 3.4 s | **137** | ✖ over by 17 (+14 %) |
| "Describe a time you aligned several engineering teams…" | **600** | 200 | 5.1 s | **714** | ✖ over by 114 (+19 %) |

Both answers were first-person, persona-grounded (the 600-char one used the real Additiv platform launch with its own numbers) and free of résumé boilerplate. `POST /autofill/answer` with no `question` → **400** `{"detail":"question is required"}`.
**Save to bank** — `POST /api/persona/qa-bank` with the 600-char answer → **200** `{"count": 20}` (19 → 20), read back at the end of `qa_bank` with the exact text. `{question:"", answer:"x"}` → **400** `question and answer are required`. ✔

### R3-B-04 · P3 · `max_chars` is still only a hint — the round-2 cap lives in the extension and only fires when the field declares a `maxLength`
**Where** `backend/api/routes_autofill.py:121-147` (the value is interpolated into the prompt, never enforced) vs `extension/content_autofill.js:503-513` (`capForField`) and `:27` (`noLimit = !(el.maxLength > 0) || el.maxLength > 200`)
**Repro** `POST /api/autofill/answer {question, max_chars: 120}` — and in the extension, focus a plain `<textarea>` (no `maxLength`), generate, pick a length.
**Actual** 137 chars for a 120 ask and 714 for a 600 ask (measured above). The round-2 fix truncates on **insert**, but only `if (s.fieldMax)`; a `<textarea>` with no `maxLength` — the normal case on Greenhouse/Lever/Ashby — has `fieldMax = null`, so `capForField` returns the text unchanged and the counter reads `714/600` with no `· trimmed to …` note. `max_tokens` (`max_chars // 4 + 96`) is a token budget, not a character bound.
**Expected + why** The user picks "~600" from a length picker; the answer that gets inserted should honour it, or the over-limit counter should be visibly an error state. This is the same behaviour v1 has, so it is not a v2 regression — but the round-2 note says it was fixed, and for limitless fields it is not.
**Proposed fix** Apply the same word-boundary trim server-side (or in `capForField` fall back to `s.len` when `fieldMax` is null) and colour the counter `--bad` when over.

## Step 9 — Settings: change 5 things through the UI → reload → persisted → scheduler → revert  ✔
Scripts `zzb_09_settings.py`, `zzb_09b_depth.py`. LLM calls: 0.

Read first: `scoring_default_depth="light"`, `fit_score_threshold=80`, `scrape_interval_minutes=3500`, `h1b_cron="0 2 * * 0"`, `prompt_caching_enabled=true`.

| control | UI action | new value in `GET /settings` | after a full reload the UI shows |
|---|---|---|---|
| **Default depth** (select) | picked `Full — score + keywords + report` | `scoring_default_depth = "full"` | `Full — score + keywords + report ▾` |
| **Score threshold** (int box) | `80` → `77`, blur | `fit_score_threshold = 77` | `77` |
| **Scrape all companies** (int box) | `3500` → `240`, blur | `scrape_interval_minutes = 240` | `240` |
| **H-1B refresh · cron** | `0 2 * * 0` → `0 5 * * 3`, blur | `h1b_cron = "0 5 * * 3"` | `0 5 * * 3` |
| **Prompt caching** (toggle) | clicked; `aria-checked` `true`→`false` | `prompt_caching_enabled = false` | `aria-checked="false"`, label `Off` |

- **Cron validation** — typing `0 5 *` (3 fields) and blurring fired the inline flash `Cron needs 5 fields` and **did not PATCH**; `h1b_cron` stayed `0 5 * * 3` (the SET-27 guard holds). ✔
- **Scheduler reconfigured live, no restart** — `GET /api/scheduler/jobs` diff was exactly `{scrape_all: "Every 3500 min" → "Every 240 min", h1b_refresh: "0 2 * * 0" → "0 5 * * 3"}`; `email_check`, `daily_digest`, `db_backup`, `auto_reject`, `job_cleanup` and the per-search override `search_7d018537… Every 120 min (search override)` were untouched. ✔
- **Unknown key** — `PATCH /api/settings {"zzb_not_a_setting":"1"}` → **400** `{"detail":"Unknown setting: zzb_not_a_setting"}`. A *mixed* body (`{unknown, fit_score_threshold: 78}`) is also **400** and **nothing is applied** — the threshold stayed 77. The SET-28 fix is all-or-nothing, which is the right shape. ✔
- **Revert** — `PATCH` with the five captured values → `{"updated":[…5 keys…],"warnings":[]}`; the whole `GET /settings` blob then diffed **empty** against the pre-flow snapshot, and the full scheduler table compared equal to `scheduler_before`. ✔
- Console clean.
- *Harness note, not a defect:* `Default depth` and `On save action` render the identical option label `Full — score + keywords + report`, and a closed `Select` shows its value as trigger text, so a `.last` text locator hits the other select's trigger. Scoped to `.first` the pick fires `PATCH {"scoring_default_depth":"full"}` correctly. `on_save_action` was verified unchanged.

## Step 10 — Cleanup through the UI, persona/settings restore, sweep  ✔ (2 findings)
Scripts `zzb_10_cleanup.py`, `zzb_10b_delete.py`, `zzb_10c_sweep.py`.

Deleted in dependency order, each through `⋯ → Delete → ConfirmDialog → Delete`:

| row | menu item | dialog | after |
|---|---|---|---|
| cover letter `8fd7c319` | `✕ Delete letter` | *Delete this letter?* | `GET` → **404**, routed back to `/v2/cover-letters` |
| copy `6af7a7c7` | `✕ Delete copy` | `Delete “ZZB Base → Anthropic — Product Manager, Claude Tag”?` | **404**, routed to `/v2/resumes` |
| freeform copy `4e15f18f` | `✕ Delete copy` | `Delete “ZZB Base (tailored)”?` | **404** |
| base `54acb867` (`ZZB Base`) | `✕ Delete copy` ← *mislabelled*, see R3-B-06 | `Delete “ZZB Base”? Its tailored copies will be removed too.` | **404** |
| base `1b042a4d` (`ZZB Import PM`) | `✕ Delete copy` | `Delete “ZZB Import PM”? Its tailored copies will be removed too.` | **404** |

Console clean throughout the deletes.

**Persona restore** — `PATCH /persona` with the seven captured nodes → every node compares equal **and** the whole seven-node blob is byte-equal to the pre-flow snapshot (`persona_byte_equal: true`); `qa_bank` back to **18** entries.
**Settings restore** — the full `GET /settings` blob diffs **empty** against the pre-flow snapshot.

### Final sweep — 0 `ZZB` rows

| endpoint | rows | `ZZB` rows |
|---|---|---|
| `/resumes` | 349 | **0** |
| `/cover-letters` | 16 (= the 16 at baseline) | **0** |
| `/jobs?title_search=ZZB` | 0 | **0** |
| `/companies` | 130 | **0** |
| `/searches` | 7 | **0** |
| `/applications` | 200 | **0** |
| `/persona` (all 7 nodes) | — | **0** (`'ZZB' in json` = false) |

`GET /resumes/shelf` is back to the exact baseline: bases `PM 45 · TPgM 0 · PjM 2 · PjM FinTech 0`, 49 live copies, 296 archived.
(The `/companies`, `/searches` and `/applications` totals differ from my baseline read because group A was creating and deleting `ZZA` rows in parallel; none of those rows are mine.)

**One residue left deliberately** — the target job `73503701…` (*Product Manager, Claude Tag* @ Anthropic) still reads `status="new"`, `tailored_resume_id=null`, `cv_scores={"PM":40,"Tailored":35}`. The `Tailored: 35` chip is the one change the brief sanctioned; see R3-B-05 for why deleting the copy did not take it with it.

### R3-B-05 · P3 · Deleting a tailored copy leaves an orphaned `Tailored` score on the job
**Where** `backend/api/routes_resumes.py:1022-1040` (`delete_resume` — deletes tracer links and child résumés, never touches `Job.cv_scores`)
**Repro** Tailor a base for a job → score the copy → delete the copy from the résumé editor → open the job on the Feed.
**Actual** `Job.tailored_resume_id` goes `null` (FK), but `cv_scores` keeps `{"PM": 40, "Tailored": 35}` and the scoring report keyed `Tailored` stays with it. The Feed's score band therefore still renders a `✦ Tailored (35)` tab and its report, while the `✦ Open tailored résumé` link and the `✦ Open tailored ↗` button are gone — a score attributed to a document that no longer exists and cannot be inspected.
**Expected + why** Either drop the `Tailored` key (and its report) when the last tailored copy for that job is deleted, or relabel it `Tailored (deleted)` so the number isn't read as live. As it stands the number silently outlives its source and can still win `best_score`.
**Proposed fix** In `delete_resume`, for each deleted résumé with a `job_id`, pop `Tailored` from that job's `cv_scores` / `scoring_report` when no other tailored copy remains for the job (`flag_modified` on both).

### R3-B-06 · P4 · A base résumé's delete item says "Delete copy"
**Where** `frontend/src/v2/ResumeEditor.jsx:553` (the base branch of the `⋯` menu reuses the copy branch's row from `:533`)
**Repro** Open a **base** résumé → `⋯`.
**Actual** The menu reads `✦ Tailor for a job… / ✕ Delete copy`, even though the document is a base and the confirm dialog correctly says `Delete “ZZB Base”? Its tailored copies will be removed too.`
**Expected** `✕ Delete résumé` (or `Delete base`) on a base. Deleting a base destroys every copy under it, so the least accurate word to use is "copy".
**Proposed fix** `{doc.is_base ? 'Delete résumé' : 'Delete copy'}` at both sites.

---

## Summary

| step | verdict | LLM calls | findings |
|---|---|---|---|
| 1 · new base from scratch + autosave | ✔ | 0 | — |
| 2 · export PDF → import through the Add modal | ✔ | 1 | — |
| 3 · every section editor | ✔ | 0 | R3-B-01, R3-B-02 |
| 4 · tailor → toast → copy → review → scores → Feed | ✔ | 4 | — (R2-H-09/R2-H-10 fixes confirmed) |
| 5 · freeform tailor + job-less score | ✔ | 2 | — (R2-H-11 no longer reproduces) |
| 6 · PDFs + tracked links | ✔ | 0 | — |
| 7 · cover letter: generate → edit → regenerate → PDF | ✔ | 2 | R3-B-03 (R2-H-14 fix confirmed) |
| 8 · persona + Q&A through the UI + autofill ×2 | ✔ | 2 | R3-B-04 · round-2 "couldn't verify" **resolved: the UI path works** |
| 9 · settings change → reload → scheduler → revert | ✔ | 0 | — |
| 10 · cleanup + restore + sweep | ✔ | 0 | R3-B-05, R3-B-06 |

**Total LLM calls: 11** — pdf import (22.6 s) · tailor→job (15.4 s) · **chained** full score fired by the tailor (28.6 s) · score light (17.9 s) · score full (46.3 s) · freeform tailor (20.4 s) · freeform score light (21.1 s) · cover-letter generate (15.7 s) · cover-letter regenerate (25.7 s) · autofill @120 (3.4 s) · autofill @600 (5.1 s). All eleven succeeded; no failed or retried run.

**Findings** — P2: 1 (R3-B-03) · P3: 4 (R3-B-01, R3-B-02, R3-B-04, R3-B-05) · P4: 1 (R3-B-06).

**Round-2 items re-checked here**
- **R2-H-09** (silent second LLM call) — fixed: the modal says `Also scores the copy afterwards at full depth · 1 more LLM call · change under Settings › AI` and `POST /resumes/tailor` returns `chain_score`.
- **R2-H-10** (freeform copy's "based on" showed the copy's own name) — fixed: reads `based on ZZB Base ↗`.
- **R2-H-11** (freeform completion toast missing) — does not reproduce; the toast fired at 21.2 s.
- **R2-H-14** (Regenerate modal showed "Select a source…") — fixed: shows `… · tailored copy`.
- **R2-H-12** (autofill over-length) — only partly addressed; see R3-B-04.
- **Round-2 "couldn't verify: adding a Q&A pair through the Persona UI"** — verified working, with the exact locators that make it reproducible.

**Restore results**
- Persona: byte-equal to the pre-flow snapshot across all seven nodes; `qa_bank` 18 → 20 → **18**.
- Settings: full-blob diff **empty**; scheduler table equal to the pre-flow table.
- Scratch rows: **0 `ZZB`** on every endpoint. Résumé shelf identical to baseline.
- Left behind by design: `cv_scores.Tailored = 35` on job `73503701…` (see R3-B-05).
