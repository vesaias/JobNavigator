# Round design-final — flows B (the document loop)

Tested: 2026-09-04, branch `v2-redesign` @ `d23817c` (design-consistency pass, D1–D6 + D6-fixup), Playwright inside the backend container vs `http://caddy`, light theme unless noted, 1440×900.
Repeat of `v2-testing/round3/flows-B.md` — same ten steps, same assertions, same method. Scripts `scratchpad/zzbd_*.py` → `backend:/tmp/v2t/`. Prefix for every row created: **`ZZB`**. Findings numbered `DS-B-NN`.
Theme is now localStorage `jobnavigator_theme` (+ `jobnavigator_skin`); the harness's legacy `jobnavigator_dark_mode` still migrates, but every script sets the new keys explicitly.

## Baseline (`zzbd_00_recon.py`, captured before anything was touched)
- Résumé shelf: 4 bases (`PM` 45 copies, `TPgM` 0, `PjM` 2, `PjM FinTech` 0), 49 live copies, 296 archived, 349 résumé rows total.
- Cover letters: 16. Persona `qa_bank`: 18 entries. 0 pre-existing `ZZ*` rows.
- Persona snapshot → `/tmp/v2t/zzbd_persona_before.json`; settings (87 keys) → `/tmp/v2t/zzbd_settings_before.json`; scheduler (7 jobs) → `/tmp/v2t/zzbd_sched_before.json`.
- **Target job:** `73503701-de3c-4eb9-ab3e-8eb42c7b1866` — *Product Manager, Claude Tag* @ **Anthropic**, `status=new`, description 6198 chars, `cv_scores = {"PM": 40}`, `tailored_resume_id=null`. Identical to the round-3 baseline (the round-3 `Tailored: 35` residue is gone — the R3-B-05 fix cleaned it).
- Settings that step 9 will change, read first: `scoring_default_depth="light"`, `fit_score_threshold=80`, `scrape_interval_minutes=3500`, `h1b_cron="0 2 * * 0"`, `prompt_caching_enabled=true`. Also relevant: `tailor_auto_quick_score="full"`, `tracer_links_enabled=true`, `autofill_default_length=250`.

---
_(steps appended as they complete)_

## Step 1 — New base from scratch + autosave  ✔
Script `zzbd_01_base.py`. LLM calls: 0. UI throughout, API to confirm.

**Did** `/v2/resumes` (header `Résumés` / `4 bases · 49 tailored copies live under their jobs · 296 archived`) → `+ New résumé` → modal `New base résumé` → typed `ZZB Base` → `Create from scratch`.
**Asserted**
- `Create from scratch` was `aria-disabled="true"` with the name box empty, and enabled once typed.
- Routed to `/v2/resumes/3b314e9b-dc02-4895-bdf9-238ae4ac18c8`; **exactly one** `POST /api/resumes`.
- Top bar reads `‹ Résumés | BASE | ZZB Base | saved just now · autosaves`; band `Base résumé · 0 tailored copies · editing here changes future tailoring only · ✦ Tailor for a job… · ⋯`.
- Seven accordions in design order Header / Summary / Experience (0) / Skills (0) / Education (0) / Projects (0) / Publications (0); the open Experience shows `No experience yet — Empty sections are skipped in the PDF — nothing prints until you add one.` (`Publications` now carries a `(0)` count too — round 3 had none; cosmetic, consistent with its siblings.)
- **Autosave/debounce unchanged by the migration to `ui.jsx`'s `Input`**: typed `ZZB Dana Okonkwo` (16 keystrokes @ 60 ms) into *Full name* → exactly **1** `PATCH /resumes/{id}`, **439 ms after the last keystroke** (500 ms trailing debounce minus event-loop slack — 440 ms in round 3). Status went `Saving…` → `saved just now · autosaves`.
- **`Title` (headline) field is present** in Header — the R3-B-01 fix survives the design pass (`input[aria-label="Title"]`, 1 match).
- `GET /resumes/{id}` → `name="ZZB Base"`, `is_base=true`, `json_data.header.name="ZZB Dana Okonkwo"`.
- `data-theme="light"` / `data-skin="default"` stamped on `<html>` from the new keys.
- Console: 0 errors, 0 page errors, 0 ≥400 responses, 0 failed requests.

## Step 2 — Export a base's PDF, import it back through the Add modal (real LLM parse)  ✔
Scripts `zzbd_02_import.py`, `zzbd_02d/02e_busy.py`. **LLM #1** — PDF parse, 19.2 s, success.

**Did** `GET /resumes/22ce0e5b…/pdf` (base `PM`) → saved as `ZZB Import PM.pdf` → `/v2/resumes` → `+ New résumé` → typed `ZZB Import PM` → `Import PDF ↑` file picker.
**Asserted**
- Export: **200**, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="ViktorEsadze_PM_Resume.pdf"`, **116 294 bytes** (identical to round 3), magic `%PDF-`, 0.6 s.
- Busy state (measured with an in-page XHR delay so the window is observable): the modal reads `New base résumé | … | Create from scratch | Parsing… | Cancel` — the busy label is on the **import** button and the other keeps `Create from scratch`. The RES-18 fix holds through the `ui.jsx` Button migration.
- `POST /resumes/import-pdf` → routed to the row the endpoint created after 19.2 s; the network log holds **exactly one POST** for the whole flow (`/api/resumes/import-pdf`, no follow-up `POST /resumes`) — the RES-27 no-duplicate fix holds.
- New base `53931520-0456-4b2e-a03b-fd499b8bb890`, `name="ZZB Import PM"` (the typed name), `is_base=true`, `parent_id=null`.
- Sections filled by the LLM: `header.name="Viktor Esadze"`, 4 contact items, summary 615 chars, **3** experience roles (first *Senior Product Manager · Additiv · May 2022 – Present*, 7 bullets), skills `{Certifications, Technical, Tools, Languages}`, 2 education, 0 projects, 0 publications. Editor rendered `Experience (3) · Skills (4) · Education (2)`.
- **Failure path:** with `POST /resumes/import-pdf` intercepted as `500 {"detail":"boom"}` the modal stays open, shows `boom` in `--bad`, both buttons return to their idle labels, the route does not change, and no row is created (`ZZB Stall` → 0 rows).
- Console clean (0/0/0/0).

### DS-B-01 · P4 · A busy/disabled `Button` drops `role="button"` entirely, not just its interactivity
**Where** `frontend/src/v2/ui.jsx:65` (`act = (fn, off, role) => (fn && !off ? {...} : {})`) → `:152` (non-native `Button` branch)
**Repro** Open `+ New résumé`, pick a PDF; while `Parsing…` shows, query `div[role="button"]`.
**Actual** Neither `Parsing…` nor the sibling `Create from scratch` matches — while `off` is true the div carries only `aria-disabled="true"`, with no `role`, no `tabIndex` and no key handler, so a screen reader reads it as loose text rather than a disabled button, and focus that was on it is dropped.
**Expected + why** A disabled control should keep its role and announce `aria-disabled`; ARIA's own guidance is to keep disabled buttons discoverable. This is `ui.jsx`-wide (every non-native `Button`, `DashedAdd`, `Select`), so it is one line, not a per-screen fix.
**Proposed fix** `act = (fn, off, role) => (fn ? (off ? { role: role || 'button' } : { onClick: fn, ...kb(fn, role) }) : {})`.
**Status** needs decision: keep (deliberate "inert while busy") or restore the role?

## Step 3 — every section editor on `ZZB Base`  ✔
Scripts `zzbd_03a_hdr.py` (header + summary), `zzbd_03b_exp.py` (experience + skills), `zzbd_03c_edu.py` (education/projects/publications + keyboard collapse). LLM calls: 0. UI throughout, `GET /resumes/{id}` after every change.

| control (design-pass component) | what was done | result |
|---|---|---|
| Header · **Full name** (`Input`) | 16 keystrokes | 1 PATCH @ 439 ms · `header.name` ✔ |
| Header · **Title** (`Input`, R3-B-01 fix) | typed `ZZB Head of Widgets` | 1 PATCH @ **456 ms** · `header.title` ✔ |
| Header · contact rows (`DashedAdd` ×3 + `Input`) | filled text + URL | 3 rows; the stub box appeared on **only** the non-`mailto:` row (1 of 3) and took `li` ✔ |
| Header · **MoveArrows ▼/▲** | `▼` row 0, then `▲` row 1 | `[Berlin, LinkedIn, mail]` → `[LinkedIn, Berlin, mail]` → back, PATCH @ 499 ms ✔ |
| Header · **RemoveX + undo** | `✕` row 3 → toast `Removed contact item · Undo · ✕` → Undo | 3 → 2 → **3, byte-identical** ✔ |
| **Summary** (`BulletText` textarea) | typed 54 chars | 1 PATCH @ 475 ms · meta reads `54 characters` ✔ |
| Experience (`DashedAdd big` + `Field`) | `+ Add experience`, Company/Title/Location/Date, `+ Add bullet` ×3 + text | one role, 3 bullets ✔; section head `⌄ Experience (1)`, entry head `⌄ Product Lead · ZZB Labs · 2023 – Present · 3 bullets` |
| Experience · bullet **RemoveX + undo** | `✕` bullet 2 → `Removed bullet · Undo` → Undo | 3 → 2 → **3 restored in order** ✔ |
| Experience · ● marker | — | `changed by tailoring` marks = **0** on a base ✔ |
| **Skills** (`DashedAdd` ×2, `CategoryName`) | renamed `Skill 1`→`Tools`, typed values | `{Tools: "Jira, Figma", Skill 2: ""}` ✔ |
| Skills · **collision** | renamed `Skill 2`→`Tools`, blurred | **refused**: toast `! “Tools” already exists — renaming onto it would erase its values. ✕`, the input snapped back to `Skill 2`, `skills` unchanged in the API ✔ |
| Skills · rename + **MoveArrows** | → `Methods`, then `▼` on row 0 | `{Tools, Methods}` → key order `["Methods","Tools"]` ✔ (the order-only `flag_modified` write still lands) |
| Education (`MicroField` ×4) | School/Location/Degree/Years | one entry ✔ |
| Projects (`MicroField` + bullets) | Name/URL/Description + `+ Add bullet` + text | one project with 1 bullet ✔ |
| Projects · **RemoveLink + undo** | `Remove project` → `Removed project · Undo` → Undo | `[]` → **restored byte-equal with its bullet** ✔ |
| Publications | `+ Add publication`, then its `Remove` | added then removed ✔ |
| **SectionHead keyboard** | `Skills` head: `tabindex=0`, `role=button`, `aria-expanded=true` → **Enter** → `false` → **Space** → `true` | ✔, persisted to `localStorage.jobnavigator_v2_resume_sections` (order updated), no scroll jump on Space |
| Entry-head keyboard | Experience role head → Enter | `aria-expanded` `true`→`false` ✔ |

Console clean on every pass (0/0/0/0).

*Note (cosmetic, not filed):* the worded remove is `Remove role` / `Remove project` in Experience/Projects but the bare default `Remove` in Education and Publications (`RemoveLink` is called with no children there) — the design-pass move of `RemoveLink` into `ui.jsx` kept that asymmetry from round 3.

## Step 4 — Tailor `ZZB Base` for the Anthropic job  ✔ (1 finding)
Scripts `zzbd_04a_tailor.py`, `zzbd_04b_failtoast.py`, `zzbd_04d_review.py`, `zzbd_04e_score.py`, `zzbd_04f_feed.py`, `zzbd_04g_tabs.py`.
**LLM #2** tailor attempt — **failed** (8.5 s, see DS-B-02) · **LLM #3** tailor retry (21.1 s, completed) · **LLM #4** chained full score fired by the tailor (`analyze_job`, 26.6 s) · **LLM #5** `Score again · light` (18.8 s) · **LLM #6** `Score again · full` (55.6 s).

**Did / asserted**
1. `✦ Tailor for a job…` → modal `Tailor ZZB Base for a job`, panel 480×596 at a whole-pixel `top: 152` (`useSnapTop` holds), searched `Claude Tag`, picked `Product Manager, Claude Tag · Anthropic · new · 40`.
2. **Modal dismissal** — **Escape** closes it; a **scrim click** at (30, 500) closes it; both leave the editor untouched. ✔
3. **Chain-score line** — absent before a job is picked (`Runs in the background` only) and present after: `Also scores the copy afterwards at full depth · 1 more LLM call · change under Settings › AI`. `POST /resumes/tailor` → **202** `{"run_id":"ec7ffb08…","status":"running","chain_score":"full"}`, matching `tailor_auto_quick_score="full"`. ✔ (R2-H-09 fix holds.)
4. Progress toast `Tailoring for Anthropic… runs in the background.`; success toast **24.1 s** later: `✓ Tailored copy for Anthropic is ready. — Open ↗`.
5. Copy `3d84349b-0525-49d7-8009-d2e546b37215`, `is_base=false`, `parent_id=ZZB Base`, `job_id=<Anthropic job>`, name `ZZB Base → Anthropic — Product Manager, Claude Tag`. Top bar `‹ Résumés | TAILORED | … | saved 1m ago · autosaves`; band `Tailored for Anthropic — Product Manager, Claude Tag │ −27 based on ZZB Base ↗` (lineage names the **base** — R2-H-10 fix holds).
6. Run history: `tailor_resume completed 21.1 s — "Created 'ZZB Base → Anthropic — Product Manager, Claude Tag' - full score chained"`, then `analyze_job completed 26.6 s — "Product Manager, Claude Tag - best 13 (PM), full"`.
7. **⋯ menu on a copy** = `THIS COPY · ✦ Re-tailor… (adds a copy) · ◎ Score again · light (score only) · ◎ Score again · full (with report) · ≋ Review changes (3 to review) · JOB · ✉ Cover letter (c) · ↗ Open in feed (e) · ✓ Mark applied (a) · ✕ Delete copy`.
8. **Review changes — the R3-B-02 fix is live and correct.**
   - Heading is `Tailoring changes` (not "… — already applied") whenever a suggested row is present, with the sub-line `Applied changes are already in the document — decline any and the base text comes back. Suggested bullets are not in it yet: they are added when you finish reviewing.`
   - Rows: `SUMMARY · APPLIED · Decline ↩` and `EXPERIENCE · ZZB LABS · SUGGESTED BULLET · SUGGESTED · added when you finish reviewing · Drop ↩` ×2 — 1 `Decline ↩` and 2 `Drop ↩` buttons, exactly matching kind.
   - Footer `1 applied · 2 suggested — added on Done reviewing`; after declining the summary, `0 applied · 2 suggested — added on Done reviewing · 1 declined`.
   - **Escape** and a **scrim click** both close it.
   - API before: `bullets` = the 3 base bullets, `suggested_bullets` = the 2 LLM proposals; **after `Done reviewing`**: `bullets` = 5 (the 2 suggestions appended), `suggested_bullets` = gone, `summary` **byte-equal to the base's** (the declined row restored). Toast `✓ Review applied — declined changes restored to base.` ✔
   - The editor itself also renders the two pending rows with a `suggested` tag before review — they are no longer invisible.
9. **Scores** — `Score again · light` → `Scoring (light) — runs in the background.` → 18.8 s → `✓ Scored: 26 (-14 vs base)`; `Score again · full` → 55.6 s → `✓ Scored: 39 (-1 vs base)`. Job `cv_scores = {"PM": 40, "Tailored": 39}`, `tailored_resume_id` = the copy; the copy's ring reads **39** after reload.
10. **Feed** — `/v2/feed?job=73503701…`: the row carries `✦ Open tailored résumé`, the detail header `✦ Open tailored ↗`, the collapsed band `› 40 │ PM │ 27% keywords │ 4 of 12 requirements met │ 2 reports`. Expanding shows two tabs, `PM` and `✦ Tailored (39)`, and the Tailored report renders `SCORE BREAKDOWN` / `KEYWORD COVERAGE` / `REQUIREMENT MAPPING 4 of 12 met`. ✔
11. Console clean on every résumé screen (0/0/0/0). On `/v2/feed` the only console traffic is the **external** `job-boards.cdn.greenhouse.io` page inside the detail iframe (React hydration #418/#423/#425, a Greenhouse `401 my.greenhouse.io/users/self`, font-preload warnings) — same as round 3, not the app.

### DS-B-02 · P2 · A tailor run that fails is reported to the user as a success
**Where** `frontend/src/v2/ResumeEditor.jsx:135-165` — the watcher decides "done" purely by the run disappearing from `GET /monitor/active` and then always calls `pushToast({ kind: 'success', … })`; `:160-162` falls back to `'Tailoring finished.'` when no new copy is found. The run's `status` is never read (`/monitor/history` carries it).
**Repro** Tailor a base whose content the LLM refuses (here: `ZZB Base` while its bullets were still `ZZB bullet 1..3` — the model answered in prose, not JSON, and `routes_resumes.py:920` raised `Expecting value: line 1 column 1 (char 0)`; run `ec7ffb08…` → `status=failed`, 8.5 s). Any backend failure reproduces it.
**Actual** The run vanishes from `/monitor/active`; ~3 s later the editor shows a green `✓` toast. Nothing anywhere in the UI says the tailoring failed; the user is left looking for a copy that does not exist. (Measured: the failed run produced no error toast and no copy; the run history is the only place the failure is visible.)
**Expected + why** A background job that ends `failed` must surface as an error toast naming the failure, the way `runScore`'s foreground errors already do. "Tailoring finished." is actively misleading — it is the copy-not-found branch, i.e. exactly the failure case.
**Proposed fix** In the watcher, when a pending scope disappears, `GET /monitor/history?limit=5&job_type=tailor_resume`, match the run, and push `{kind:'error', msg: 'Tailoring failed — ' + run.error}` when `status !== 'completed'`; keep the success branch for `completed`.
**Status** logged (frontend; a rebuild would be needed to verify a fix, so not fixed here).

*Not a defect, recorded:* the same placeholder résumé tailored **successfully** on the retry (21.1 s) — the refusal is the model reacting to obviously fake content, not a code path. Every later step used the retry's copy.

**DS-B-02, proven without an LLM call** (`zzbd_04h_falsetoast.py`): with `POST /resumes/tailor` stubbed `202 {"status":"running"}` and `GET /monitor/active` stubbed `[]`, the editor shows `Tailoring from a pasted description… runs in the background.` and then, 9.6 s later, the green **`✓ Tailoring finished. — Résumés ↗`** — for a run that produced nothing at all.

## Step 5 — Freeform tailor from a pasted description + job-less score  ✔
Scripts `zzbd_05_freeform.py`, `zzbd_05b_chain.py`. **LLM #7** freeform tailor (60.5 s) · **LLM #8** job-less `Score again · light` (19.7 s).
*Deviation from round 3, deliberate:* the freeform tailor was run from **`ZZB Import PM`** (the real parsed résumé) rather than the placeholder `ZZB Base`, after the placeholder content made the first tailor call fail (DS-B-02). Same code path, realistic input.

**Did** `ZZB Import PM` → `✦ Tailor for a job…` → pasted a **136-word** JD (*ZZB Director of Platform Product, Developer Experience*) into `…or a freeform job description` → `✦ Tailor`.
**Asserted**
- **`✦ Tailor` is disabled** (`aria-disabled="true"`) with neither a job nor a JD, and enables as soon as the JD box has text. ✔
- **Chain-score line, all three states** (`zzbd_05b_chain.py`): nothing picked → footer is `Runs in the background` only; JD pasted → still only `Runs in the background`; a job picked → `Runs in the background` **+** `Also scores the copy afterwards at full depth · 1 more LLM call · change under Settings › AI`, and picking the job **clears the JD box**. ✔ Matching the backend's `if chain_depth and job_id`, the freeform run chained **no** score: its run summary is the bare `Created 'ZZB Import PM (tailored)'` (the job-linked one reads `… - full score chained`) and no `analyze_job` followed it.
- Progress toast `Tailoring from a pasted description… runs in the background.`; **the completion toast fired** — `✓ Tailored copy from your pasted description is ready. — Open ↗` at 63.2 s.
- New copy `d39f22a0-5e42-419c-8f3e-bf300c72e80c`, name `ZZB Import PM (tailored)`, `job_id = null`, `parent_id = ZZB Import PM`.
- `json_data._tailor_context` present, keys exactly `["job_description","source"]`, `source="freeform"`, `job_description` **byte-equal** to the pasted text. ✔
- Band: `Tailored from a pasted description │ based on ZZB Import PM ↗` — the lineage names the **base** (R2-H-10 fix holds).
- `Score again · light` on a job-less copy → `Scoring (light) — runs in the background.` → 19.7 s → `✓ Scored: 38`; `json_data._score = {"Tailored": 38, "scored_at": "2026-09-03T23:33:07Z"}`; after a reload the band ring reads **38**. Run summary `ZZB Import PM (tailored) (pasted JD) - Tailored 38, light`. ✔
- Console clean; the single `requestfailed` is the `…/pdf` blob abort in the preview `<iframe>` (headless Linux has no PDF viewer — documented artifact).

## Step 6 — PDFs for both bases and both copies, tracked links  ✔
Scripts `zzbd_06_pdf.py`, `zzbd_06b_dl.py` (link extraction via pdfplumber annots). LLM calls: 0.
Tracer settings in play: `tracer_links_enabled=true`, `tracer_links_base_url="https://viktoresadze.com"`, `tracer_links_url_style="param_jobid"`.

| résumé | PDF | filename | `GET /tracer-stats` | URL inside the PDF |
|---|---|---|---|---|
| `ZZB Base` | **200**, `application/pdf`, `%PDF-`, 84 998 B, 0.6 s | `ZZBDanaOkonkwo_ZZBBase_Resume.pdf` | 1 row · `ZZB LinkedIn → https://linkedin.com/in/zzb-dana` · token `0li` · 0 clicks · active | `https://viktoresadze.com/?cv=0li` |
| job copy | **200**, 90 320 B | `ZZBDanaOkonkwo_ZZBBase_Resume_20892.pdf` (job short-id) | 1 row · token **`20892li`** | `https://viktoresadze.com/?cv=20892li` |
| `ZZB Import PM` | **200**, 112 483 B | `ViktorEsadze_ZZBImportPM_Resume.pdf` | 1 row · token `so08ut` | `https://viktoresadze.com/?cv=so08ut` |
| freeform copy | **200**, 116 719 B | `ViktorEsadze_ZZBImportPM(tailored)_Resume.pdf` | 1 row · token `e5ithw` (random — job-less, the documented fallback) | `https://viktoresadze.com/?cv=e5ithw` |

- **Each document gets its own token for the same destination**, so a click is attributable to the exact PDF that was sent. ✔
- `mailto:zzb@example.com` and the *project* URL `https://example.com/zzb` are left alone — only `header.contact_items` are rewritten. ✔
- **The new Header `Title` prints**: the PDF text of `ZZB Base` reads `ZZB DANA OKONKWO | ZZB Head of Widgets | ZZB Berlin, DE | …`, so the R3-B-01 field round-trips editor → API → PDF. ✔
- The job copy's PDF carries the 5 bullets that survived review (3 base + 2 accepted suggestions) and the base summary (the row I declined). ✔
- **`↓ Download PDF` control** (`zzbd_06b_dl.py`): exactly one `<a target="_blank">`, `href=/api/resumes/{id}/pdf?template=garamond&format=letter`; fetching it returns **200 / application/pdf / 90 320 B** with the right filename. Switching **Paper → A4** rewrites the href to `…&format=a4` and that fetch returns 200 / 90 343 B. The `Template` picker lists all eight layouts (`Garamond Classic … Traditional Serif`); the `Paper` picker `US Letter | A4`.
- Editor band shows `2 reviewable changes · tracers: ZZB LinkedIn 0`.

## Step 7 — Cover letter from the job-linked copy: generate → edit → regenerate → PDF  ✔ (R3-B-03 fixed)
Scripts `zzbd_07a_cl.py`, `zzbd_07b_cledit.py`, `zzbd_07c_split.py`, `zzbd_07d_regen.py`.
**LLM #9** generate (12.5 s) · **LLM #10** regenerate, different voice **and** length (21.1 s).

1. **Entry** — résumé copy → `⋯ → Cover letter` → `/v2/cover-letters` with **both pickers pre-filled** from the `?resume=&job=` deep link: `YOUR RÉSUMÉ ZZB Base → Anthropic — Product Manager, Claude Tag` and `TARGET JOB Anthropic — Product Manager, Claude Tag`, voice `Professional & direct`, length `Standard`. `✦ Generate cover letter` → run `generate_cover_letter completed 12.5 s — "Generated letter for Anthropic — Product Manager, Claude Tag (professional voice)"`, toast `✓ Cover letter ready.` at 16.6 s.
2. **Row** — new letter `423e4be4…`, `name="Anthropic — Product Manager, Claude Tag"`, `voice=professional`, `length=standard`, `template=garamond`, `resume_id` = **the tailored copy**, `job_id` = the Anthropic job, `source_name="ZZB Base → Anthropic — Product Manager, Claude Tag"`. `json_data` keys = `header/recipient/date/greeting/body_paragraphs/closing/signature`; 3 paragraphs; `greeting="Dear Hiring Team,"`; `recipient={company:"Anthropic",manager:"",address:""}`. The opening paragraph is job-specific and grounded in the copy's own facts (it names *ZZB Labs*, no invented employer). Letters 16 → 17.
3. **Edit a paragraph** — typed ` ZZB edit marker.` into ¶3: **one** `PATCH` at **475 ms**, only `body_paragraphs[2]` changed (¶1/¶2 byte-identical), header reads `saved just now · autosaves`. ✔
4. **Add / reorder / remove + undo** — `+ Add paragraph` → typed ¶4 → 4 in the API; `↑` on ¶4 → it moved to position 3; `✕` on ¶3 → toast `Removed paragraph · Undo · ✕` → 4 → 3 → **4 restored byte-identical**; the extra paragraph removed again to leave the letter at 3. ✔
5. **Regenerate** — modal `Regenerate letter / Rewrites the whole letter for Anthropic — your edits to this draft are replaced.`; **`FROM RÉSUMÉ` reads `ZZB Base → Anthropic — Product Manager, Claude Tag · tailored copy`** (R2-H-14 fix holds), panel 460×410 at whole-pixel `top: 245`, **Escape** closes it, a **scrim click** closes it. Picked `Storytelling` + `Detailed` → the button showed `Regenerating…` → run `completed 21.1 s — "Regenerated letter for … (storytelling voice)"`. Read back: `voice="storytelling"`, `length="detailed"`, a genuinely different opening, the `ZZB edit marker` **gone** (as the modal warns), 3 paragraphs, and the letter **count stayed 17** — rewritten in place, no duplicate row. ✔
6. **PDF** — `GET /cover-letters/{id}/pdf` → **200**, `application/pdf`, `%PDF-`, 108 409 B, `filename="ZZBDanaOkonkwo_Anthropic_CoverLetter_20892.pdf"`. Text: header + contact line, `September 03, 2026`, `Anthropic`, `Dear Hiring Team,`, then the storytelling opening. Links: `https://viktoresadze.com/?cv=20892li` + `mailto:` — the letter carries the tracked link too. ✔
7. **R3-B-03 (P2 in round 3) is fixed** — after rendering the letter PDF, **both** documents report the shared link:

| after the letter's PDF | `/resumes/{copy}/tracer-stats` | `/cover-letters/{id}/tracer-stats` |
|---|---|---|
| round 3 | **0 rows** | 1 row `20892li` |
| now | 1 row `20892li` · 0 clicks · active | 1 row `20892li` · 0 clicks · active |

8. **Header contact rows 45/55** — measured in both editors at 1440×900 with the same data: cover-letter editor **226.3 px / 276.6 px**, computed `flex: 45 1 0px` / `55 1 0px`; résumé editor **226.3 px / 276.6 px**, identical flex. Byte-for-byte the same split, and identical to round 3's numbers. ✔
9. Console clean on both editors (0/0/0/0).

## Step 8 — Persona: contact, preference, résumé bullet, **Q&A through the UI**, autofill ×2, save to bank  ✔ (1 finding, R3-B-04 fixed)
Scripts `zzbd_08_persona.py`, `zzbd_08b_autofill.py`, `zzbd_08c_envelope.py`. **LLM #11** autofill @120 (3.9 s) · **LLM #12** autofill @600 (8.1 s) · **LLM #13–14** two repeat autofills for DS-B-03 (4.4 s, 5.8 s).

Snapshot check first: `work_auth`, `demographics` and `compensation` were byte-equal to the recon snapshot throughout — the only nodes that changed are the four I edited, so there was no drift from the parallel group-A run.

| what | how | API within | result |
|---|---|---|---|
| contact field | `Contact / basics` → `State` `Hesse` → `Hesse ZZB` | 1 PATCH @ 500 ms | `contact.state = "Hesse ZZB"`, header flashed `Saved ✓` (visible) ✔ |
| preference | `Screening defaults` → `Notice period` → `3 months ZZB` | 1 PATCH @ 501 ms | `preferences.notice_period = "3 months ZZB"` ✔ |
| resume_content | Experience → role 1 → `+ Add bullet` → typed | 2 PATCH | `resume_content.experience[0].bullets` 9 → **10**, last = `ZZB persona bullet.` ✔ |

### Adding a Q&A pair through the Persona UI — still works
1. Card header read `18 answers`. `+ Add answer` → a blank pair rendered with both boxes empty; `qa_bank` in the API stayed **18** (one PATCH fired, carrying the *filtered* list — round 3 saw no PATCH at all; either way the blank pair is not persisted, which is the PERS-21 rule).
2. Typed only the **question** (`textarea[placeholder="Question as the form asks it…"]`) → after the debounce `qa_bank` became **19**, last entry `{question: "ZZB why do you want to work here?", answer: ""}`.
3. Typed the **answer** (`textarea[placeholder="Your reusable answer…"]`) → the same entry carried both halves.
4. Full page reload → still 19 entries, header `19 answers`. ✔ Console clean.

### Autofill
| call | `max_chars` | HTTP | time | answer length | within limit? |
|---|---|---|---|---|---|
| "Why do you want to work at Anthropic… first 90 days?" | **120** | 200 | 3.9 s | **81** | ✔ |
| "Describe a time you aligned several engineering teams…" | **600** | 200 | 8.1 s | **460** | ✔ (but see DS-B-03) |
| repeat @600 | **600** | 200 | 4.4 s | 574 | ✔ |
| repeat @1200 | **1200** | 200 | 5.8 s | 928 | ✔ |

**R3-B-04 is fixed**: `max_chars` is now enforced server-side by `_trim_to_chars()` (`routes_autofill.py:24-47`, sentence- then word-boundary) and the response carries `trimmed`. Four calls, none over its budget — round 3 measured 137/120 and 714/600.
Answers were first-person and persona-grounded (the long one used the real *additiv* Tier-1-bank delivery with its own numbers). `POST /autofill/answer` with no `question`, and with an empty `question`, both returned **400** `{"detail":"question is required"}`.
**Save to bank** — `POST /api/persona/qa-bank` → **200** `{"count": 20}` (19 → 20), read back at the end of `qa_bank` with matching text. A missing question and a missing answer each returned **400** `question and answer are required`. ✔

### DS-B-03 · P3 · When the model's JSON envelope can't be parsed, the wrapper is served to the user as the answer
**Where** `backend/api/routes_autofill.py:180-192` — the salvage regex needs a closing brace; if the match or `json.loads` fails, `answer = raw` is returned unchanged.
**Repro** Intermittent — 1 of 4 identical `POST /api/autofill/answer` calls (`{question, company:"Anthropic", position:"Product Manager, Claude Tag", max_chars:600}`).
**Actual** The 200 response's `answer` began with the literal `{"answer": "At additiv I owned a Tier 1 bank platform delivery where 5 engineering squads had conflicting views…` — 460 chars of JSON envelope, which the extension would insert verbatim into an application form. The three repeat calls returned clean prose, so the envelope only leaks when the model's JSON is malformed or truncated.
**Expected + why** The endpoint's whole job is to hand back a paste-ready answer. An opening brace as the first character is always wrong, and a user pasting it into a real application would not notice until after submitting.
**Proposed fix** After the regex attempt, if the answer still starts with a brace, salvage it (strip the leading `{"answer":` prefix and the trailing brace, unescape); if that also fails return **502** rather than the envelope — that failure path already exists for LLM errors.
**Status** logged (backend; not fixed — a backend edit needs a restart other agents are sharing).

## Step 9 — Settings: Appearance rows, five DB settings → reload → scheduler → revert, Edit modal, model catalog  ✔
Scripts `zzbd_09a_appearance.py`, `zzbd_09a2_persist.py`, `zzbd_09c_settings.py`, `zzbd_09d_sched.py`, `zzbd_09e_modal.py`, `zzbd_09f_catalog.py`. LLM calls: 0.

### The new Appearance group (`GENERAL › Appearance`, the first section)
`Appearance — theme and skin — remembered in this browser, not in the database`, two `Select` rows (`aria-label="Theme"`, `aria-label="Skin"`).

| action | `<html>` | `.jn-v2` | localStorage | tokens |
|---|---|---|---|---|
| start | `data-theme=light data-skin=default`, no `.dark` | `light` / `default` | `jobnavigator_theme=light` | `--bg #fcfbf7`, `--font-body "Public Sans"` |
| Theme → **Dark** | `dark`, `.dark` **on** | `dark` | `theme=dark` (+ legacy `dark_mode=true`) | `--bg #1e1c17` |
| Skin → **Alt** | `data-skin=alt` | `alt` | `skin=alt` | `--bg #161a21`, `--font-body "Inter","Source Sans 3"…` |
| Theme → **System** | resolves to `light` here | `light` | `theme=system` | helper row appears: `following your OS — currently light` |

- **No `/api/settings` traffic at all** while changing either row — 0 PATCH/POST/PUT, exactly as the group's subtitle promises. ✔
- **Persistence** (`zzbd_09a2_persist.py`, run without the harness's theme keys in its init script, which would otherwise mask it): after `Dark`+`Alt`, a **reload** and a **fresh navigation** both come back `dark`/`alt` from localStorage, and the inline boot script has already stamped `data-theme="dark" data-skin="alt"` on `<html>` before React mounts (`boot_stamp = "dark/alt"`). ✔
- **Cross-shell**: with dark+alt set in v2, the classic shell at `/` carries `.dark` + `data-theme="dark"` + `data-skin="alt"`. ✔
- **Rail ◐** cycles `Dark → System → Light → Dark`, its tooltip naming the current mode (`Theme: Dark — click to switch`), the localStorage key follows each click, and the Settings `Theme` select re-renders to match. ✔
- Restored to `light`/`default` at the end; console clean throughout.

### The five DB settings
| control | UI action | new value in `GET /settings` | after a full reload the UI shows |
|---|---|---|---|
| **Default depth** (select) | picked `Full — score + keywords + report` | `scoring_default_depth = "full"` | `Full — score + keywords + report ▾` |
| **Score threshold** (int box) | `80` → `77`, blur | `fit_score_threshold = 77` | `77` |
| **Scrape all companies** (int box) | `3500` → `240`, blur | `scrape_interval_minutes = 240` | `240` |
| **H-1B refresh · cron** | `0 2 * * 0` → `0 5 * * 3`, blur | `h1b_cron = "0 5 * * 3"` | `0 5 * * 3` |
| **Prompt caching** (toggle) | clicked; `aria-checked` `true`→`false` | `prompt_caching_enabled = false` | `aria-checked="false"` |

- **Cron validation** — typing a 3-field cron and blurring fired the inline flash `Cron needs 5 fields` and **did not PATCH**; `h1b_cron` kept its last good value (SET-27 guard holds). ✔
- **Scheduler reconfigures live, no restart** — `h1b_refresh` moved `0 2 * * 0 → 0 5 * * 3` on the UI pass, and a controlled API pass (`zzbd_09d_sched.py`) moved `scrape_all` `Every 240 min → Every 241 min → Every 240 min` with every other job (`email_check`, `daily_digest`, `db_backup`, `auto_reject`, `job_cleanup`) untouched. ✔
- **Unknown key** — `PATCH /api/settings {"zzb_not_a_setting":"1"}` → **400** `{"detail":"Unknown setting: zzb_not_a_setting"}`. A *mixed* body (unknown key + `fit_score_threshold: 78`) is also **400** and **nothing is applied** — the threshold kept its previous value. All-or-nothing, as SET-28 intends. ✔
- **Revert** — `PATCH` with the five captured values → `{"updated":[…5 keys…],"warnings":[]}`; the whole `GET /settings` blob then diffed **empty** against the pre-flow snapshot and the scheduler table compared equal.
- *Harness note, not a defect:* an early probe run of the same script left `scoring_default_depth` / `fit_score_threshold` / `scrape_interval_minutes` at the changed values; the drift was caught by diffing against `zzbd_settings_before.json` and restored (`zzbd_restore_settings.py`) before the clean pass. Diff **only** against the recon snapshot, never against a value read mid-flow.

### Edit modal — flush on close (SET-25)
Opened `Edit Gmail query · exclusions` (7 lines), typed a new line, and left the modal **51 ms** later — far inside the 600 ms debounce:
- **`Done`** → the modal closed and `email_gmail_query_exclusions` came back with `ZZB TEST PHRASE` appended. ✔
- **`Escape`** → same, `ZZB ESC PHRASE` was written. ✔ Both exits flush; nothing typed in the last 600 ms is lost.
- Restored the key to its baseline value; full settings blob equal again.

### Model catalog typeahead (`Model catalog — manage`)
- Modal opens as `Model catalog · available in every model picker · ✕`; the search box (`aria-label="Search the model catalog"`) queried the **live** provider catalog: typing `haiku` returned `anthropic/claude-3-haiku · anthropic/claude-haiku-4.5 · anthropic/claude-haiku-4.5:batch · ~anthropic/claude-haiku-latest` with the footer **`4 of 425 match · or paste any slug and Add`** and an `↵ to add` hint on the highlighted row.
- **ArrowDown** moves the highlight (the row's background goes to `rgb(234,241,235)` = `--accent-soft`). ✔
- **First Escape closes the typeahead only** (0 listboxes, catalog still open); **second Escape closes the catalog** — the R3-S-04 fix and its guard both hold. ✔
- Nothing was added: `llm_custom_models` unchanged, full settings blob equal to baseline at the end.

## Step 10 — Cleanup through the UI, persona/settings restore, sweep  ✔ (R3-B-05 and R3-B-06 both fixed)
Scripts `zzbd_10_cleanup.py`, `zzbd_10b_sweep.py`.

Deleted in dependency order, each through `⋯ → Delete → ConfirmDialog → Delete`:

| row | menu | menu item | after |
|---|---|---|---|
| cover letter `423e4be4` | `☰ View job in feed · ↗ Open job posting · ✕ Delete letter` | `✕ Delete letter` | `GET` → **404**, routed back to `/v2/cover-letters` |
| copy `3d84349b` | `THIS COPY · ✦ Re-tailor… · ◎ Score again · light · ◎ Score again · full · ≋ Review changes (2 to review) · JOB · ✉ Cover letter · ↗ Open in feed · ✓ Mark applied · ✕ Delete copy` | `✕ Delete copy` | **404**, routed to `/v2/resumes` |
| freeform copy `d39f22a0` | same minus the job rows (`≋ Review changes (14 to review)`, no *Open in feed* / *Mark applied* — it has no job) | `✕ Delete copy` | **404** |
| base `3b314e9b` (`ZZB Base`) | `THIS BASE · ✦ Tailor for a job… · ✕ **Delete résumé**` | `✕ Delete résumé` | **404** |
| base `53931520` (`ZZB Import PM`) | `THIS BASE · ✦ Tailor for a job… · ✕ **Delete résumé**` | `✕ Delete résumé` | **404** |

- **R3-B-06 is fixed** — a base's delete row now reads `Delete résumé`, and the menu head reads `THIS BASE` (a copy's reads `THIS COPY`). Both confirm dialogs offered `Cancel | Delete`.
- **R3-B-05 is fixed** — after deleting the tailored copy the target job reads `cv_scores = {"PM": 40}`, `tailored_resume_id = null`, `best_cv = "PM"`: **no orphaned `Tailored` score survives the delete**, so nothing at all is left behind on the job this time (round 3 had to leave `Tailored: 35` on it).
- Console clean throughout the deletes (0/0/0/0).

**Persona restore** — `PATCH /persona` with the seven captured nodes → every node compares equal **and** the whole seven-node blob is byte-equal to the pre-flow snapshot (`persona_byte_equal: true`); `qa_bank` back to **18** entries (18 → 20 → 18); `'ZZB' in persona` is **false**.
**Settings restore** — the full `GET /settings` blob diffs **empty** against the pre-flow snapshot, and the scheduler table compares equal to `zzbd_sched_before.json`.

### Final sweep — 0 `ZZB` rows

| endpoint | rows | `ZZB` rows |
|---|---|---|
| `/resumes` | 349 (= baseline) | **0** |
| `/cover-letters` | 16 (= the 16 at baseline) | **0** |
| `/jobs?title_search=ZZB` | 0 | **0** |
| `/companies` | 126 | **0** |
| `/searches` | 6 | **0** |
| `/applications` | 377 | **0** |
| `/persona` (all 7 nodes) | — | **0** (`'ZZB' in json` = false) |

`GET /resumes/shelf` is back to the exact baseline: bases `PM 45 · TPgM 0 · PjM 2 · PjM FinTech 0`, 49 live copies, 296 archived.
(The `/companies` and `/searches` totals differ from the baseline read because group A was creating and deleting `ZZA` rows in parallel; none of those rows are mine, and none were touched.)

---

## Summary

| step | verdict | LLM calls | findings |
|---|---|---|---|
| 1 · new base from scratch + autosave | ✔ | 0 | — |
| 2 · export PDF → import through the Add modal (+ 500 path) | ✔ | 1 | DS-B-01 (P4) |
| 3 · every section editor + keyboard collapse | ✔ | 0 | — |
| 4 · tailor → toast → copy → review → scores → Feed | ✔ | 5 | DS-B-02 (P2) |
| 5 · freeform tailor + job-less score | ✔ | 2 | — |
| 6 · PDFs + tracked links + Download control | ✔ | 0 | — |
| 7 · cover letter: generate → edit → regenerate → PDF | ✔ | 2 | — |
| 8 · persona + Q&A through the UI + autofill ×4 | ✔ | 4 | DS-B-03 (P3) |
| 9 · Appearance rows + settings → reload → scheduler → revert + Edit modal + catalog | ✔ | 0 | — |
| 10 · cleanup + restore + sweep | ✔ | 0 | — |

**Total LLM calls: 14** — pdf import (19.2 s) · tailor→job **failed** (8.5 s) · tailor→job retry (21.1 s) · **chained** full score fired by the tailor (26.6 s) · score light (18.8 s) · score full (55.6 s) · freeform tailor (60.5 s) · freeform score light (19.7 s) · cover-letter generate (12.5 s) · cover-letter regenerate (21.1 s) · autofill @120 (3.9 s) · autofill @600 (8.1 s) · autofill repeat @600 (4.4 s) · autofill repeat @1200 (5.8 s). Thirteen succeeded; the one failure is the model refusing obviously-placeholder résumé text, and it is what surfaced DS-B-02.

**Findings** — P2: 1 (DS-B-02) · P3: 1 (DS-B-03) · P4: 1 (DS-B-01). No P1.

### Every design-pass-migrated editor control re-verified
`Input` / `Textarea` autosave and its 500 ms trailing debounce (439–501 ms measured across résumé Header · Title · Summary · cover-letter paragraph · persona contact · persona preference — always exactly **one** PATCH) · `Field` / `MicroField` · `BulletText` · `DashedAdd` (contact item, bullet, skill row, experience, education, project, publication, paragraph, Q&A answer) · `MoveArrows` ▲▼ (contact items, skill categories, cover-letter paragraphs) · `RemoveX` + undo (contact item, bullet, skill category) · `RemoveLink` + undo (role, project, education, publication) · skills category rename **and** its collision refusal · `SectionHead` collapse by click, **Enter** and **Space** with the state persisted to localStorage · `Select` (depth, paper, template, theme, skin) · `Toggle` (prompt caching) · `Menu`/`MenuItem` (résumé, letter, catalog) · `ModalPanel` Escape + scrim + whole-pixel snap on the Tailor, Review and Regenerate modals · the Settings `EditModal`'s flush-on-close on **both** exits · the model-catalog typeahead with its two-stage Escape · the header `Title` field · `↓ Download PDF` · the new Appearance rows.

### Round-3 findings re-checked — **all six are fixed**
- **R3-B-01** (no header Title field) — fixed: `input[aria-label="Title"]` autosaves at 456 ms and the value prints in the PDF (`ZZB DANA OKONKWO | ZZB Head of Widgets | …`).
- **R3-B-02** ("already applied" was untrue of suggested bullets) — fixed: separate `SUGGESTED`/`APPLIED` chips, `Drop ↩` vs `Decline ↩`, a footer that counts them apart, a softened heading, and suggested bullets that reach `json_data.bullets` only on `Done reviewing`. The editor now shows them as `suggested` rows too.
- **R3-B-03** (résumé and letter fought over one tracer link) — fixed: after the letter's PDF, **both** `/resumes/{copy}/tracer-stats` and `/cover-letters/{id}/tracer-stats` report `20892li`.
- **R3-B-04** (`max_chars` was only a hint) — fixed: `_trim_to_chars()` enforces it server-side; 4 of 4 calls inside budget (81/120, 460/600, 574/600, 928/1200).
- **R3-B-05** (orphaned `Tailored` score) — fixed: deleting the copy left `cv_scores = {"PM": 40}` and `tailored_resume_id = null`.
- **R3-B-06** ("Delete copy" on a base) — fixed: reads `Delete résumé`.

Earlier round-2 items confirmed still fixed: **R2-H-09** (the chain-score line, in all three states), **R2-H-10** (lineage names the base), **R2-H-11** (the freeform completion toast fires), **R2-H-14** (Regenerate names the tailored copy), **RES-17/18/27/28**, **SET-25/27/28**, **R3-S-04**.

**Restore results**
- Persona: byte-equal to the pre-flow snapshot across all seven nodes; `qa_bank` 18 → 20 → **18**.
- Settings: full-blob diff **empty**; scheduler table equal to the pre-flow table.
- Scratch rows: **0 `ZZB`** on every endpoint. Résumé shelf identical to baseline. The target job is byte-equal to its baseline (`status=new`, `cv_scores={"PM":40}`, `tailored_resume_id=null`) — **nothing left behind at all**.
- No commits, no rebuilds, no restarts, no source edits.
