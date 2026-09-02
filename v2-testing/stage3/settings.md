# Stage 3 — Settings

Tested: 2026-09-02, bundle index-Dnrx3n0f.js (HEAD 3819fe8), themes light+dark, viewport 1440×900 (+ one narrow 1024×700 pass)
Design: `v2-testing/design/Settings Ops.dc.html`   Inventory: `v2-testing/inventory/v2-settings.md` + `v2-testing/inventory/settings-matrix.md`
Scripts: `set_1.py` … `set_9.py` (scratchpad)

Live DB at test time: 86 settings rows; `llm_provider = claude_code` (keyless → the **API key** row is hidden, so **67** of the 68 spec'd rows render — matches the inventory).

---

## Design re-diff (required deliverable)

`Settings Ops.dc.html` grew after the screen was built and had never been re-diffed. Below is every section and row in the design's `<script type="text/x-dc">` `sections()` block, marked against `frontend/src/v2/Settings.jsx:210-338`.

**Sections: 15 in the design, 15 in the JSX, same ids and same order.** Group labels AI / PIPELINE / INTEGRATIONS / SYSTEM identical.

### Row-by-row

| # | Design section · row (dc line) | In JSX? | Note |
|---|---|---|---|
| **models** | sub: "one Primary model for everything; override per feature only where it pays" (`:311`) | **differs** | JSX `:211` "each individual prompt can be run against different model, if needed" |
| 1 | Primary provider · model (`:312`) | present `:212` | design box 220 + box2 260 = JSX |
| 2 | API key (`:315`) | present `:215` | JSX adds `hide()` for keyless providers — design always shows it |
| 3 | Scoring (`:316`) | present `:216` | |
| 4 | Scoring fallback (`:317`) | present `:217` | |
| 5 | Tailoring (`:319`) | present `:219` | |
| 6 | Cover letters (`:320`) | present `:220` | |
| 7 | Autofill (`:321`) | present `:221` | |
| 8 | Email classification (`:322`) | present `:222` | |
| 9 | Model catalog (`:323`) | present `:223` | help truncated in JSX ("… — changes show up in every model picker" dropped) |
| **scoring** | sub identical (`:329`) | ✓ | |
| 10 | Default résumé (`:330`) w260 | present `:227` | design help is longer ("…the last stop before nothing gets scored. Empty = score against all bases + Persona.") |
| 11 | Max parallel jobs (`:331`) **w170** | present `:228` | JSX w135 → SET-05 |
| 12 | Default depth (`:332`) **w340** | present `:229` | JSX w260 → SET-05 |
| 13 | On save action (`:334`) **w340** | present `:232` | JSX w260 → SET-05 |
| 14 | Prompt caching (`:335`) | present `:234` | |
| 15 | Scoring rubric (`:337`) | present `:236` | |
| 16 | Light output schema (`:339`) | present `:237` | |
| 17 | Full output schema (`:341`) | present `:238` | |
| **tailoring** | sub: "bullet rewrites — never invents skills or experience" (`:344`) | **differs** | JSX `:240` "AI-rewritten résumés" |
| 18 | Résumé tailoring prompt (`:345`) | present `:241` | |
| 19 | Persona tailoring prompt (`:347`) | present `:242` | |
| 20 | Auto-score after tailoring (`:349`) **w340** | present `:244` | JSX w260; JSX also moves it below the new row 21 |
| — | *(no design row)* | **EXTRA in JSX** `:243` | **Max parallel tailors** — `tailoring_max_concurrent`, a key that post-dates the design and is not in v1 either. Correct addition. |
| **letters** | sub: "voice presets are injected into the prompt" (`:351`) | **differs** | JSX `:247` "AI-written based on Persona or résumé" |
| 21 | Default voice (`:352`) | present `:248` | |
| 22 | Voice presets (`:353`) | present `:249` | design sub says `prompt` per voice, live schema uses `instruction`; JSX sub is correct |
| 23 | Cover letter prompt (`:355`) | present `:250` | design placeholders `{length} {voice_prompt} {job_description} {resume_json}`; JSX sub matches the real prompt |
| **autofill** | sub "used by the extension on ATS forms" (`:358`) | ~ | JSX "used by the Chrome extension on ATS forms" |
| 24 | Default answer length (`:359`) **w170** | present `:253` | JSX w135 → SET-05 |
| 25 | Autofill prompt (`:360`) | present `:254` | |
| 26 | Field patterns (`:362`) | present `:255` | |
| 27 | Option synonyms (`:364`) | present `:256` | |
| **prep** | sub identical (`:367`) | ✓ | |
| 28 | **"Prep handover template"** (`:368`) | renamed `:259` | JSX `"What I need from you" section` — same key `prep_ask`. Deliberate; the backend only appends this block. |
| 29 | Include by default (`:370`) **w340** | present `:260` | JSX w260 → SET-05. Design value example "Posting · résumé · emails · notes" — a 4th section (emails) the backend does not support. |
| **emailclass** | sub "turns Gmail replies into application events" (`:372`) | **differs** | JSX `:264` "reads Gmail replies" |
| 30 | LLM classification (`:373`) | present `:265` | |
| 31 | Confidence threshold (`:374`) **w170** | present `:266` | JSX w135 → SET-05 |
| 32 | Classification prompt (`:375`) | present `:267` | |
| 33 | Gmail query · subjects (`:377`) | present `:268` | |
| 34 | Gmail query · senders (`:379`) | present `:269` | |
| 35 | Gmail query · exclusions (`:381`) | present `:270` | |
| **scheduler** | sub "…crons are min hour day month dow, empty = off" (`:384`) | **differs** | JSX `:272` drops the field legend: "crons empty = off" |
| 36 | Scrape all companies (`:385`) **w170** | present `:273` | w135 |
| 37 | Email check (`:386`) **w170** | present `:274` | w135 |
| 38 | Cleanup after (`:387`) **w170** | present `:275` | w135; design help "Days before unsaved postings are purged" vs JSX "ignored and skipped job postings" (JSX matches `scheduler.py:238`) |
| 39 | **"Auto-reject after"** (`:388`) | renamed `:276` | JSX "Auto-reject threshold" |
| 40 | DB backup · cron (`:390`) | present `:279` | design help "Nightly **SQLite** snapshot" — wrong DB (Postgres); JSX "Database snapshot" is right |
| 41 | Telegram digest · cron (`:391`) | present `:280` | |
| 42 | H-1B refresh · cron (`:392`) | present `:281` | |
| 43 | Job cleanup · cron (`:393`) | present `:282` | |
| 44 | Auto-reject · cron (`:394`) — **last row** | present `:278` — **5th row** | order differs |
| **exclude** | sub identical (`:397`) | ✓ | 3/3 rows present |
| **dedup** | sub "same job from two sources isn't saved twice" (`:405`) | **MISSING** | JSX `:289` passes `""` → the section header renders with no subtitle |
| 45 | Stripped params (`:406`) | present `:290` | |
| **notifications** | sub identical (`:409`) | ✓ | |
| 46 | Telegram (`:410`) | present `:293` | |
| 47 | Chat ID (`:411`) **w170** | present `:294` | w135 |
| 48 | Score threshold (`:412`) **w170** | present `:295` | w135 |
| 49 | Test / "Send test message" (`:413`) | present `:296` | |
| 50 | Webhook secret (`:414`) — a **bordered BOX** (w260, muted value) + Rotate | present `:297` but **not a box** | JSX renders the preview as a bare mono span, `flex:1`. Visual deviation → SET-06 |
| 51 | Register webhook (`:417`) | present `:306` | |
| **tracer** | sub "per-application open tracking in Stats" (`:419`) | ~ | JSX "per-application link click tracking" |
| 52 | Rewrite links (`:420`) | present `:314` | |
| 53 | Base URL (`:422`) | present `:316` | |
| 54 | URL style (`:423`) | present `:317` | design offers "Short — /l, /gh" / "readable" — a scheme the backend never had. JSX's path/param/path_jobid/param_jobid matches `routes_resumes.py:296`. **Design is stale, code is right.** |
| **jobright** | sub identical (`:425`) | ✓ | 2/2 rows present |
| **linkedin** | sub "…the extension's separate capture identity" (`:429`) | ~ | JSX "…separate mock account" |
| 55 | Personal email (`:430`) | present `:326` | |
| 56 | Personal password (`:431`) | present `:327` | |
| 57 | Session cookie (`:432`) — a plain BTN with a static help string | present `:328` as a live `LinkedInRow` | **code is richer**: live status/phase, PIN entry, 2.5 s poll |
| 58 | Mock account email (`:433`) | present `:329` | |
| 59 | Mock account password (`:435`) | present `:331` | |
| **advanced** | sub "escape hatches — most days none of this gets touched" (`:437`) | **MISSING** | JSX `:333` passes `""` |
| 60 | Proxy URL (`:438`) | present `:334` | |
| 61 | Dashboard API key (`:439`) — a **BOX pw** echoing `jn_live_8Kd2…9mQx` with show/hide, **no save button** | present `:335` as `ApiKeyRow` | **code is safer and deliberately different** (never echoes, explicit "Save key"). Design would have re-saved the mask. |
| 62 | DB backup / "Run backup" (`:440`) | present `:336` | |
| 63 | **H-1B data / "Refresh now"** (`:441`) | **MISSING** | → SET-07 |
| 64 | **Job cleanup / "Run cleanup"** (`:442`) | **MISSING** | → SET-07 |

**Totals: design 64 rows across 15 sections; JSX 68 rows.** The JSX adds `Max parallel tailors` and, relative to the design's `advanced`, drops two manual triggers. The remaining count difference is the design's row list being written before six keys existed.

### Modals

| Design | JSX | Verdict |
|---|---|---|
| Edit modal 680 × 640, textarea `min-height:220px` (`:138,:145`) | `min(1020px, 94vw)` × `min(1280px, 92vh)`, textarea `minHeight:440` (`:649,:658`) | deliberate ("1.5× wider and 2× taller", comment `:656`) → SET-08 needs decision |
| Edit footer: status · Reset to default · Done (`:148-150`) | same (`:661-667`) | ✓ |
| Catalog modal 600 × 620 (`:158`) | same (`:717`) | ✓ |
| Catalog typeahead = absolutely-positioned dropdown under the field, first item pre-highlighted with `↵ to add`, matched substrings **bolded**, footer "4 of 324 match · or paste any slug and Add" (`:168-174`) | plain inline list of ≤8 rows rendered *above* the catalog, no bolding, no ↵ hint, no match-count footer (`:737-743`) | → SET-09 |
| Catalog row `×`: `delDisplay: custom ? "flex" : "none"` (`:466`) — **seeded models cannot be removed** | `×` on every row incl. seeded (`:749`) | → SET-10 |
| Catalog `×` hover: `border-color:#9c3b30;color:#9c3b30` (`:184`) | `.v2-hover-bad-text` = colour only, border unchanged | → SET-11 |
| Catalog "N of M match" footer | absent | part of SET-09 |
| Design has a `CHIPS()` renderer + 3 chip slots (`:113-117,:283-293`) | absent | **dead in the design too** — no section calls `CH`. Correctly not built. |

### Hovers declared in the design

| design `style-hover` | element | built? |
|---|---|---|
| `color:#1b1a16` on rail anchor (`:69`) | `.v2-anchor` | ✓ `.v2-anchor:hover{color:var(--text)}` |
| `border-color:#3f6b52;color:#3f6b52` on **Edit** pill (`:105`) | `.v2-bdc` | ✓ |
| `border-color:#3f6b52` on **ActionBtn** (`:110`) | `.v2-bd` | ✓ |
| `background:#f3f0e8;color:#1b1a16` on modal ✕ (`:142,:162`) | `.v2-hover-accent` | ✓ |
| `background:#f3f0e8` on catalog suggestion rows (`:170-172`) | `.v2-menuitem` | ✓ |
| `border-color:#9c3b30;color:#9c3b30` on catalog × (`:184`) | `.v2-hover-bad-text` (colour only) | **partial** → SET-11 |
| `color:#9c3b30` on chip × (`:114-116`) | chips not built | n/a |
| `border-color:#3f6b52;color:#3f6b52` on Reset to default (`:149`) | `.v2-bdc` | ✓ |
| rail/collapse hovers (`:42,:43,:48`) | shell, not this screen | n/a |

---

## Findings

