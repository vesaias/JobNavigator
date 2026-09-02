# R4 — user-facing text candidates (v2 frontend)

Scope: every user-visible string in `frontend/src/v2/*.jsx` and `*.js`. JSX text,
`title=` / `aria-label=` / `placeholder=`, toast messages, `confirm` bodies,
settings `help` / `info` / `offHelp`, empty-state and error copy, tooltips.
Excluded: code comments, `console.*`, CSS, class names, HANDOVER.md, anything
outside `src/v2/`.

Row format: `file:line | "exact current text" | flag | why`

Flags: `mannered` · `metaphor` · `hedge` · `long` · `unclear` · `fine`.
No rewrites here — R4b writes those.

Note on `fine`: where a file has more than ~15 plain strings they are collapsed
to a count line at the end of that file's section, so the flagged rows stay
readable. Every flagged row is listed individually.

---
## time.js

No strings ≥6 words. Relative-time tokens only: `just now`, `now`, `Nm ago`,
`Nh ago`, `Nd ago`, `Nm`, `Nh`, `Nd` (lines 6–16).

`fine`: 8 strings.

---

## ConfirmDialog.jsx

Only two button labels, both short.

`fine`: 2 strings — `Cancel` (18), `Confirm` (19, default when no `label` passed).

---

## hooks.js

No user-facing strings.

---

## Toast.jsx

No user-facing copy — the component renders `t.msg` / `t.action` supplied by
callers. Only the two glyphs `✓` / `!` (17–18) and the dismiss `✕` (74).

`fine`: 3 strings.

---

## WelcomeModal.jsx

| file:line | text | flag | why |
|---|---|---|---|
| WelcomeModal.jsx:34 | `Four steps and your search runs itself.` | mannered | personifies the search; ad-copy cadence |
| WelcomeModal.jsx:10 | `Pick your LLM provider and add its key — Anthropic, OpenAI, Ollama or OpenRouter.` | fine | em-dash introduces a real list |
| WelcomeModal.jsx:11 | `Edit a base résumé and fill Persona (contact, work auth) so jobs score against your profile.` | fine | plain, one instruction |
| WelcomeModal.jsx:12 | `Enable a seeded company or add your own to start scraping.` | fine | plain |
| WelcomeModal.jsx:13 | `Enable a keyword search or LinkedIn Personal to discover jobs from boards.` | fine | plain |
| WelcomeModal.jsx:30 | `Welcome to JobNavigator` | fine | title |
| WelcomeModal.jsx:54 | `Start with Settings →` | fine | button |

Short/label strings not listed: `Set up AI scoring` (10), `Build your résumé + Persona` (11),
`Activate a company` (12), `Configure a search` (13), aria-label `Close` (31).

---

## ToastLab.jsx

Temporary debug route `/v2/toasts`, not linked from the rail (file comment says
delete before sign-off). Listed for completeness; a reviewer may want to skip it.

| file:line | text | flag | why |
|---|---|---|---|
| ToastLab.jsx:60 | `progress — paper card, ink text, spinner. Ambient status, not news. 2.5s.` | mannered | "Ambient status, not news" is a flourish |
| ToastLab.jsx:63 | `undo — the one dark toast. Dark means still actionable, which is why progress is not dark. 5s.` | long | three clauses, two ideas |
| ToastLab.jsx:29 | `Temporary — fire each kind, check both themes, then delete this page.` | fine | plain instruction |
| ToastLab.jsx:50 | `Fire all (watch the 3-toast cap)` | fine | button, plain |
| ToastLab.jsx:61 | `success — green tint, solid ✓ roundel. The only green toast. 2.5s.` | fine | plain |
| ToastLab.jsx:62 | `error — red tint, ! roundel, stays until dismissed.` | fine | plain |
| ToastLab.jsx:64 | `Stack bottom-right, newest at the bottom, at most three visible. Slide + fade 250ms.` | fine | plain spec line |
| ToastLab.jsx:9 | `paper card + spinner · 2.5s` (title attr) | unclear | dev shorthand as a tooltip |
| ToastLab.jsx:11 | `green tint + ✓ roundel · 2.5s` (title attr) | unclear | dev shorthand as a tooltip |
| ToastLab.jsx:13 | `red tint + ! roundel · stays until dismissed` (title attr) | unclear | dev shorthand as a tooltip |
| ToastLab.jsx:15 | `the only dark toast · 5s` (title attr) | unclear | dev shorthand as a tooltip |
| ToastLab.jsx:16 | `dark = still actionable` (title attr) | unclear | dev shorthand as a tooltip |

Sample toast payloads (fake data, not product copy): `Tailoring for Senior SWE at Plaid…` (9),
`Scoring 14 jobs…` (10), `Tailored for Senior SWE at Plaid` (11), `Copy created for Datadog.` (12),
`Scoring failed for Backend Engineer at Datadog` (13), `Tailoring failed to start.` (14),
`Skipped "Senior Go Engineer"` (15), `Marked applied — "Staff Engineer"` (16).
Labels: `Toast lab` (28), `Fire one` (38), `Clear` (52), `N showing` (53), `Rules` (58),
`Open ↗` (12), `Undo` (15,16), `◐ Dark`/`◐ Light` (32).

`fine`: 5 listed + ~14 short/sample.

---

## LoginModal.jsx

| file:line | text | flag | why |
|---|---|---|---|
| LoginModal.jsx:80 | `First run with no key configured? Leave the field blank and sign in — you'll set one in Settings › Advanced.` | long | 21 words; question + two instructions |
| LoginModal.jsx:56 | `Enter your dashboard API key — you can view or change it later in Settings.` | fine | plain; em-dash joins two clauses |
| LoginModal.jsx:31 | `Unexpected response from server` | fine | error, plain |
| LoginModal.jsx:34 | `Invalid API key` | fine | error, plain |
| LoginModal.jsx:34 | `Login failed: ${err.message \|\| 'unknown error'}` | fine | error, plain |
| LoginModal.jsx:49 | `Loading dashboard…` | fine | status |

Short/label strings: `Signed in` (48), `JobNavigator` (54), `API key` (61),
placeholder `jn_live_…` (64), aria-labels `Hide API key` / `Show API key` (67),
`hide` / `show` (68), `Signing in…` / `Sign in` (76).

`fine`: 6 listed + 10 short.

---
## V2App.jsx (nav rail shell)

| file:line | text | flag | why |
|---|---|---|---|
| V2App.jsx:95 | `No company or search is failing, but the last scrape sweep failed · ${lastSweep}. Click → Stats · Run history.` | long | 20 words, two ideas; "sweep" is jargon |
| V2App.jsx:96 | `All companies and searches healthy · last sweep ${lastSweep}. Click → Stats · Run history.` | unclear | "sweep" is not a user term |
| V2App.jsx:91 | `no sweep recorded yet` | unclear | "sweep" for a scrape run |
| V2App.jsx:93 | `${nC} companies and ${nS} searches need attention. Click → Stats · Run history.` | fine | plain, two short sentences |
| V2App.jsx:83 | `${failing} sources need attention` | fine | plain |
| V2App.jsx:85 | `Scraper healthy · ${ago}` / `Scraper run failed · ${ago}` | fine | plain status |
| V2App.jsx:86 | `No scrape recorded yet` | fine | plain |
| V2App.jsx:120 | `${label} · ${count} · needs attention` (collapsed-rail tooltip) | fine | plain |
| V2App.jsx:145 | `Coming in the redesign` (tooltip on a not-ready item) | fine | unreachable today — every item has `ready: true` |
| V2App.jsx:163,171 | `Switch to ${dark ? 'light' : 'dark'} mode` | fine | plain |
| V2App.jsx:169 | `Collapse to icons` / `Expand navigation` | fine | plain |

Short/label strings: `JobNavigator` (104), `JN` (105), group headers `Find` (18) /
`Apply` (23) / `You` (28), item labels `Jobs`, `Searches`, `Companies`,
`Applications`, `Résumés`, `Cover Letters`, `Persona`, `Stats`, `Settings` (19–31),
`Needs attention` (141), `Classic UI` / `← Classic UI` (152,154), `Collapse` (170),
relative-time tokens (39–42).

`fine`: 11 listed + ~20 short.

---
## Resumes.jsx (shelf)

| file:line | text | flag | why |
|---|---|---|---|
| Resumes.jsx:153 | `${n} bases · ${m} tailored copies live under their jobs${archived ? ` · ${k} archived` : ''}` | metaphor | "live under their jobs" is spatial imagery |
| Resumes.jsx:195 | `Nothing archived yet — copies land here when their application is rejected or goes stale.` | metaphor | "land here"; also "goes stale" |
| Resumes.jsx:168 | `Couldn't load your résumés — the shelf request failed.` | unclear | "shelf request" is an internal name |
| Resumes.jsx:335 | `Import failed — is it a text PDF?` | unclear | "text PDF" needs explaining |
| Resumes.jsx:291 | `Archived · ${n} copies from rejected or stale applications` | fine | plain |
| Resumes.jsx:193 | `Archived · ${n} from rejected or stale applications` | fine | plain |
| Resumes.jsx:178 | `Nothing matches "${q}" — search covers base names, company names, and job titles.` | fine | plain, states the scope |
| Resumes.jsx:176 | `${n} matches — bases, copies, and archived` | fine | plain |
| Resumes.jsx:206 | `No base résumés yet. Create one to start.` | fine | plain empty state |
| Resumes.jsx:212 | `Open Persona — your full profile` (title) | fine | plain |
| Resumes.jsx:217 | `Average fit across copies tailored from Persona (archived included)` (title) | fine | plain |
| Resumes.jsx:226,266 | `Tailoring in progress — opens when ready` (title) | fine | plain |
| Resumes.jsx:234,276 | `Has tailoring changes you haven't reviewed` (title) | fine | plain |
| Resumes.jsx:252 | `Open ${b.name} — the base résumé` (title) | fine | plain |
| Resumes.jsx:257 | `Average fit across this base's scored copies (archived included)` (title) | fine | plain |
| Resumes.jsx:344 | `Start from scratch, or import an existing PDF to parse.` | fine | plain |
| Resumes.jsx:345 | `Résumé name (e.g. Backend — Platform v4)` (placeholder) | fine | plain |

Short/label strings: `Show ${n} more` (29), `fit ${n} (${d} vs ${base} avg)` (54),
`changes unreviewed` (55), `Résumés` (152,245), placeholder `Search bases, copies, archived…` (156),
`+ New résumé` (158), `Loading…` (163), `Try again` (169), `‹ Back` (175,192),
badge words `base` / `tailored` / `archived` (181,198), `Profile` (211), `Persona` (214),
`your full profile` / `no recent copies` / `no copies` / `edited ${ago}` (215,255),
` avg fit` (218,258), `Recent copies` (224,264), `tailoring…` (227,268),
`show fewer ‹` / `+ ${n} more ›` (239,281), `browse ›` (292), `Create failed` (318),
`New base résumé` (343), `Creating…` / `Create from scratch` (352),
`Parsing…` / `Import PDF ↑` (353), `Cancel` (359), time tokens (13–17).

`fine`: 13 listed + ~30 short.

---
## ResumeSections.jsx (shared résumé/persona editors)

| file:line | text | flag | why |
|---|---|---|---|
| ResumeSections.jsx:324 | `${n} characters · long summaries can push to a second page` | metaphor | text that "pushes" to a page |
| ResumeSections.jsx:135 | `Empty sections are skipped in the PDF — nothing prints until you add one.` | long | second clause restates the first |
| ResumeSections.jsx:220 | `Short stub for the tracer link id (e.g. l, w, gh)` (title) | unclear | "tracer link id" is internal jargon |
| ResumeSections.jsx:293 | `Suggested by tailoring — keep on review` (title) | unclear | "keep on review" reads ambiguously |
| ResumeSections.jsx:208 | `text · link · stub` (column legend) | unclear | three bare nouns, no explanation |
| ResumeSections.jsx:284,322 | `Decline this tailoring change — restores the base text` (title) | fine | plain |
| ResumeSections.jsx:344 | `"${newK}" already exists — renaming onto it would erase its values.` | fine | plain, states the consequence |
| ResumeSections.jsx:343 | `"${newK}" can't be used as a category name.` | fine | plain |
| ResumeSections.jsx:342 | `A skills category needs a name.` | fine | plain |
| ResumeSections.jsx:267 | `Contains unreviewed tailoring changes` (title) | fine | plain |
| ResumeSections.jsx:275 | `Jan 2022 – Present` (placeholder) | fine | example value |
| ResumeSections.jsx:277 | `Optional role description` (placeholder) | fine | plain |

Short/label strings: section names `Header`/`Summary`/`Experience`/`Skills`/`Education`/`Projects`/`Publications` (26),
`Remove` (101,106), `No ${what} yet` (134), `Full name` (202), `Contact items` (207),
placeholders `Display text` (216), `URL (optional)` (219), `id` (220), `Skill values…` (374),
`Category` (401), `2015 – 2019` (419); titles `Move up` / `Move down` (196,353),
`Added by tailoring` / `Changed by tailoring` (242,243,373,375), `Decline this tailoring change` (376);
`Untitled role` (263), `${n} bullets` (266), `suggested` (295), `added` (375);
field labels `Company`/`Title`/`Location`/`Date`/`Description`/`School`/`Degree`/`Years`/`Name`/`URL`/`Bullets` (272–277, 414–473);
adds `+ Add contact item` (228), `+ Add bullet` (299,453), `+ Add experience` (309),
`+ Add skill row` (386), `+ Add education` (427), `+ Add project` (461), `+ Add publication` (479);
remove links `Remove role` (302), `Remove project` (457);
undo labels `Removed contact item` (221), `Removed bullet` (285,448), `Removed role` (300),
`Removed skill category` (379), `Removed education entry` (421), `Removed project` (455),
`Removed publication` (474).

`fine`: 7 listed + ~50 short.

---
## ResumeEditor.jsx

| file:line | text | flag | why |
|---|---|---|---|
| ResumeEditor.jsx:730 | `Changes land automatically — you review and decline afterwards.` | metaphor | "land" for "are applied" |
| ResumeEditor.jsx:783 | `These landed automatically. Decline any you don't want; the base text comes back.` | metaphor | "landed"; "the base text comes back" |
| ResumeEditor.jsx:493 | `The one next step` (title on the stage button) | mannered | design slogan, not an instruction |
| ResumeEditor.jsx:493 | `Pipeline complete` (title when done) | unclear | "pipeline" is internal vocabulary |
| ResumeEditor.jsx:535 | `Delete copy` (on the **base** résumé menu) | unclear | a base is not a copy — wrong noun |
| ResumeEditor.jsx:523 | `Base résumé · ${n} tailored copies · editing here changes future tailoring only` | unclear | "changes future tailoring only" is compressed |
| ResumeEditor.jsx:489 | `· tracers: ${t.source_label} ${t.clicks}` | unclear | "tracers" unexplained |
| ResumeEditor.jsx:631 | `Exact copy of the base, with its own tracer links` | unclear | "tracer links" unexplained |
| ResumeEditor.jsx:667 | `Persona has no résumé row to copy — tailor from it instead` (title) | unclear | "résumé row" is a DB term |
| ResumeEditor.jsx:758 | `Paste any JD — the copy won't be linked to a feed job` (placeholder) | unclear | "JD" abbreviation; "feed job" |
| ResumeEditor.jsx:813 | `${n} declined — base text restored · the rest stay` | unclear | "the rest stay" is elliptical |
| ResumeEditor.jsx:813 | `All ${n} changes live · decline any to restore the base text` | unclear | "changes live" reads as a state term |
| ResumeEditor.jsx:274 | `This copy has no job and no saved description to score against.` | fine | plain |
| ResumeEditor.jsx:487 | `No job or description linked, so this copy can't be scored.` | fine | plain |
| ResumeEditor.jsx:361 | `Save failed — your last edit is not stored. ${detail}` | fine | plain, says the consequence |
| ResumeEditor.jsx:418 | `Review applied — declined changes restored to base.` | fine | plain |
| ResumeEditor.jsx:302,311 | `Scoring finished without a score — try again.` | fine | plain |
| ResumeEditor.jsx:328 | `Its tailored copies will be removed too.` | fine | plain warning |
| ResumeEditor.jsx:149 | `Tailored copy for ${company} is ready.` | fine | plain |
| ResumeEditor.jsx:149 | `Tailored copy from your pasted description is ready.` | fine | plain |
| ResumeEditor.jsx:163,183 | `Tailoring for ${company}… runs in the background.` | fine | plain |
| ResumeEditor.jsx:163 | `Tailoring from a pasted description… runs in the background.` | fine | plain |
| ResumeEditor.jsx:284 | `Scoring (${depth}) — runs in the background.` | fine | plain |
| ResumeEditor.jsx:474 | `Open the ${baseName} base résumé this was tailored from` (title) | fine | plain |
| ResumeEditor.jsx:585 | `Preview failed — the PDF could not be rendered.` | fine | plain |
| ResumeEditor.jsx:630 | `Rewrites bullets against this job description` | fine | plain |
| ResumeEditor.jsx:680 | `Instant — no LLM call` | fine | plain for this app's user |
| ResumeEditor.jsx:735 | `Tailor from Persona instead of this base` | fine | plain |
| ResumeEditor.jsx:738 | `Pick a job · saved and scored first` | fine | plain |
| ResumeEditor.jsx:750 | `A tailored copy already exists — tailoring again adds another` (title) | fine | plain |
| ResumeEditor.jsx:754 | `No jobs match — paste a description below instead.` | fine | plain |
| ResumeEditor.jsx:749 | `This base's fit on that job` (title) | fine | plain |

Short/label strings: `Already tailoring for that job.` (165,186), `Tailoring failed to start.` (166),
`Tailoring finished.` (151), `Could not start.` (187), `Copy created for ${company}.` (179),
`That résumé no longer exists.` / `Couldn't load that résumé.` (216), `Scored: ${n}` (301,312),
`Already scoring this copy.` / `Scoring failed to start.` (315), `Marked applied.` /
`Could not mark applied.` (321), `Delete "${name}"?` (327), `Delete failed.` (332),
`Review ${n} changes` (346), `Scoring…` / `Score the result` (348), `✉ Write cover letter` (349),
`Ready ✓` (350), `Mark applied` / `Applied ✓` (351,352), `Loading…` (435), `‹ Résumés` (444),
`tailored` / `base` (446), `Saving…` / `saved ${ago} · autosaves` / `autosaves` (448),
`Tailored for …` / `Tailored from a pasted description` / `Tailored copy` (466,467),
`based on ${baseName} ↗` (476), `Couldn't load the linked job.` (486),
`${n} reviewable changes` / `not scored yet` / `ready` (488), menu `This copy` (504),
`Re-tailor…` + `adds a copy` (505), `Score again · light` + `score only` (506),
`Score again · full` + `with report` (507), `Review changes` + `${n} applied` (508),
`Job` (510), `Cover letter` (511), `Open in feed` (512), `Mark applied` (513),
`Delete copy` (515), `✦ Tailor for a job…` (524), `More` (527), `This base` (532),
`● changed by tailoring` + title `Contains unreviewed tailoring changes` (549),
`PDF preview` (559), `Résumé template` / `Template` (563), `Paper size` / `Paper` /
`US Letter` / `A4` (572,575), `↓ Download PDF` (579), `Retry` (586),
`Persona` + `your full profile` (623), `base résumé` (624), `✦ Tailor` / `Copy` (630,631),
`Re-tailor for this job` (638), `the job this copy is for · adds a new copy` (640),
`How` (646), `From which base` (662), `current base` (671), `No base résumés yet.` (675),
`Runs in the background` (680,762), `Cancel` (681,763), `✦ Re-tailor` / `Make copy` (683),
`Tailor ${name} for a job` (729), `Search jobs…` (739), `✦ exists` (750),
`…or a freeform job description` (757), `Tailoring changes — already applied` (782),
`No tailoring changes to review.` (788), change locations `Summary` /
`Experience · ${company} · bullet ${n}` / `· new bullet` / `· suggested bullet` /
`Skills · ${cat}` (40–53,796), `declined` / `applied` (797),
`Restore change` / `Decline ↩` (798), `Done reviewing` (814).

`fine`: 20 listed + ~60 short.

---
## CoverLetters.jsx (list + generate panel)

| file:line | text | flag | why |
|---|---|---|---|
| CoverLetters.jsx:151 | `The server answered ${status}.` | unclear | "answered 500" reads oddly; no next step |
| CoverLetters.jsx:337 | `Base for achievements and motivation` | unclear | "Base" as a noun is ambiguous here |
| CoverLetters.jsx:254 | `${n} of ${m} letters match · ${live} live applications` | unclear | "live applications" is app jargon |
| CoverLetters.jsx:357 | `Write the letter — you can start others while it runs` (title) | fine | plain, two short clauses |
| CoverLetters.jsx:85 | `No voice presets — add them in Settings → AI.` | fine | plain, names the fix |
| CoverLetters.jsx:281 | `A letter for this résumé and job is already generating.` | fine | plain |
| CoverLetters.jsx:392 | `Archived · ${n} letters from rejected applications & skipped jobs` | fine | plain |
| CoverLetters.jsx:389 | `Archived letters are shown while you search` (title) | fine | plain |
| CoverLetters.jsx:409 | `No cover letters yet — generate one on the left.` | fine | plain; "on the left" is a layout reference |
| CoverLetters.jsx:307 | `Stage of the linked application` (title) | fine | plain |
| CoverLetters.jsx:342 | `Select a saved or applied job…` (placeholder) | fine | plain |

Short/label strings: `Concise` / `Standard` / `Detailed` (10), `Nothing to pick yet.` (67),
`Network error` (151), `Generation failed — ${err}` (217,280,281), `Cover letter ready.` (218),
`Persona (full profile)` (229), `Untitled role` (234,290), `${n} letters · ${live} live applications` (255),
`a cover letter` (290), `edited ${ago}` (297), `No application yet` (307), `Draft` (308),
`Cover Letters` (320), `Search letters, companies…` (324), `Generate new` (332),
`Your résumé` (335), `Select a résumé…` (336), `Target job` (341), `Voice` (346),
`Length` (351), `Already writing this one` / `Pick a résumé and a job first` (357),
`Generating…` / `✦ Generate cover letter` (360), `All letters` (368),
`Generating — ${label}` (380), `~30s` (382), `shown while searching` / `hide ⌄` /
`browse ›` (395), `Couldn't load your letters` (403), `Try again` (405),
`Nothing matches that search.` (409).

`fine`: 8 listed + ~30 short.

---
## CoverLetterEditor.jsx

| file:line | text | flag | why |
|---|---|---|---|
| CoverLetterEditor.jsx:525 | `Bases and Persona — switch to draw on different achievements.` | metaphor | "draw on" is idiomatic |
| CoverLetterEditor.jsx:390 | `Short stub for the tracer link id (e.g. l, w, gh)` (title) | unclear | "tracer link id" is internal jargon |
| CoverLetterEditor.jsx:370 | `text · link · stub` (column legend) | unclear | three bare nouns, no explanation |
| CoverLetterEditor.jsx:501 | `Preview failed — showing the last render · Retry` | unclear | "the last render" is developer wording |
| CoverLetterEditor.jsx:288 | `voice and length not recorded` | unclear | passive, no next step |
| CoverLetterEditor.jsx:518 | `Rewrites the whole letter for ${company} — your edits to this draft are replaced.` | fine | plain warning |
| CoverLetterEditor.jsx:317 | `Rewrite the letter — pick base résumé, voice and length` (title) | fine | plain |
| CoverLetterEditor.jsx:139 | `Could not save — your last edit is not stored.` | fine | plain, states the consequence |
| CoverLetterEditor.jsx:108 | `Couldn't load this letter — try again.` | fine | plain |
| CoverLetterEditor.jsx:487 | `Paper size — US Letter or A4` (title) | fine | plain |
| CoverLetterEditor.jsx:312 | `Open the source résumé` / `Written from your Persona` (title) | fine | plain |

Short/label strings: defaults `Dear Hiring Team,` / `Sincerely,` (16), `US Letter` / `A4` (18),
`This letter no longer exists.` (108), `Could not download the PDF.` (192),
`This cannot be undone.` (198), `Could not delete this letter.` (202),
`Regeneration failed` (217,218), `Loading…` (274), `‹ Back to cover letters` (276),
`Try again` (277), `DRAFT` (285), `‹ Cover Letters` (296), `saved ${ago} · autosaves` /
`autosaves` (302), `Written for …` (310), `Regenerate…` (322), `More actions` (325),
`View application` (332), `View job in feed` (338), `Open job posting` (344),
`Delete letter` (349), card titles `Header` / `Recipient` / `Letter` (360,405,427),
labels `Full name` (362), `Contact items` (367), `Company` (409), `Date` (413),
`Hiring manager` (417), `Address` (421), `Greeting` (430), `Closing` (454), `Signature` (458),
placeholders `Display text` (383), `URL (optional)` (387), `id` (390), `Unknown` (418), `—` (422),
titles `Move up` / `Move down` (379,381,437,439), `Remove` (394), `Delete paragraph` (443),
`Removed paragraph` (441), `+ Add contact item` (401), `+ Add paragraph` (451),
`${n} paragraphs` (427), `¶ ${i}` (436), `PDF preview` (468),
`Cover letter template` / `Template` (472,474), `Paper` (489),
`↓ Download PDF` (502), `Rendering the preview…` (507), `Regenerate letter` (516),
`From résumé` (523), `Select a source…` (524), `Voice` (528), `Length` (532),
`~30 seconds` (537), `Cancel` (538), `Regenerating…` / `Regenerate` (543).

`fine`: 6 listed + ~45 short.

---
## Persona.jsx

| file:line | text | flag | why |
|---|---|---|---|
| Persona.jsx:337 | `Your full work history, summary, skills and achievements. The AI uses this as the source pool for tailored résumés, as raw material for cover-letter anecdotes, and as the candidate profile when scoring jobs.` (ColumnHead help) | long | 33 words, three roles in one sentence; "source pool", "raw material" |
| Persona.jsx:353 | `Personal info used to auto-fill application forms — contact details, work authorization, EEO answers, salary expectations and reusable screener answers. Not used by the AI for résumé generation or scoring.` (ColumnHead help) | long | 29 words, list plus a caveat |
| Persona.jsx:65 | `Prefer not to answer demographic questions — autofill picks "decline" where the form allows it` | long | a preference and a behaviour in one line |
| Persona.jsx:344 | `Tailored résumés draw from whatever you add here.` (emptyNote) | metaphor | "draw from" is idiomatic |
| Persona.jsx:175 | `what is this?` (help affordance label) | mannered | informal aside used as a label |
| Persona.jsx:407 | `No saved answers yet — the extension can add them as you apply.` | fine | plain, names the mechanism |
| Persona.jsx:327 | `Saves automatically · autofill ${filled} of ${ANSWERABLE} set` | fine | plain status line |
| Persona.jsx:215 | `Could not load your persona — ${detail}` | fine | plain |
| Persona.jsx:245 | `Could not save your changes — ${detail}` | fine | plain |
| Persona.jsx:396 | `Question as the form asks it…` (placeholder) | fine | plain |
| Persona.jsx:384 | `reusable screener answers` | fine | plain |

Short/label strings: option labels `Male`/`Female`/`Non-binary` (26), race list (27–29),
`I am a protected veteran` / `Not a protected veteran` (30), `Yes`/`No` (31),
age bands (32), orientation list (34–35), `U.S. citizen`/`Permanent resident`/`Visa holder`/`Other` (36–37);
group titles `Contact / basics` (41), `Demographics · EEO` (54), `Work authorization` (68),
`Screening defaults` (75); field labels `First name`…`Portfolio URL` (42–52),
`Gender`…`Sexual orientation` (55–62), `Authorized to work in the US?` (69),
`Require sponsorship now?` (70), `Require sponsorship in the future?` (71), `Are you over 18?` (72),
`Work authorization type` (73), `Willing to relocate?` (76), `Willing to work remote?` (77),
`Notice period` (78), `Earliest start date` (79), `Referral source` (80),
`How did you hear about us?` (81), `Desired salary` (82);
`— not answered` (128), `Couldn't load your persona.` (308), `Try again` (309), `Loading…` (311),
`Persona` (322), `Saved ✓` (330), `Résumé content` (336), `Autofill content` (352),
`complete` / `${n} of ${m} set` (366), `Q&A bank` (383), `${n} answers` (385),
`Your reusable answer…` (400), `Remove answer` (404,286), `+ Add answer` (408).

`fine`: 6 listed + ~60 short.

---
## Applications.jsx

| file:line | text | flag | why |
|---|---|---|---|
| Applications.jsx:491 | `Builds one pasteable block — the role, my résumé, the posting and what to ask for — for the AI of your choice` (title) | long | 23 words, nested em-dash aside; "my" vs "your" |
| Applications.jsx:136 | `${n} applications · ${i} in interview · ${o} offers · showing the first ${x} · ${s} waiting >7d` | long | up to five facts in one line |
| Applications.jsx:653 | `For applications made outside the app — jobs from the feed log themselves when you mark them applied.` | metaphor | "jobs … log themselves" personifies |
| Applications.jsx:39 | `In the interview loop` (stage hint) | metaphor | "loop" is figurative |
| Applications.jsx:41 | `Closed — kept for the Stats funnel` (stage hint) | metaphor | "funnel" is figurative |
| Applications.jsx:493 | `Generate prep handover for AI` | unclear | "prep handover" is invented vocabulary |
| Applications.jsx:234,235 | `Could not build the prep bundle` / `Could not build the prep bundle: ${msg}` | unclear | "prep bundle" — a third name for the same thing |
| Applications.jsx:583 | `Building the bundle…` | unclear | "the bundle" unexplained |
| Applications.jsx:587 | `Edit the closing ask in Settings → AI` | unclear | "the closing ask" is opaque |
| Applications.jsx:111 | `The server answered ${status}.${detail}` | unclear | "answered 500"; no next step |
| Applications.jsx:703 | `The posting is cached on save` | unclear | passive; "cached" undefined for a user |
| Applications.jsx:123 | `Discard this application? Everything typed will be lost.` (window.confirm) | fine | plain (note: native confirm, not the v2 dialog) |
| Applications.jsx:382 | `No applications yet — mark a job applied in the Feed, or log one here.` | fine | plain, two routes named |
| Applications.jsx:628 | `The posting URL is required — it identifies the job` | fine | plain, gives the reason |
| Applications.jsx:659 | `Paste the job URL — title and company are read from it` (placeholder) | fine | plain |
| Applications.jsx:247 | `Could not copy — select the text and copy it manually` | fine | plain fallback instruction |
| Applications.jsx:483 | `A reply was detected, but no snippet was stored.` | fine | plain |
| Applications.jsx:435 | `Snapshot of the posting from application day` (title) | fine | plain |
| Applications.jsx:642 | `Already logged — opened the existing application.` | fine | plain |
| Applications.jsx:366 | `No movement for ${n} days` / `Last activity ${n}d ago` (title) | fine | plain |
| Applications.jsx:303 | `Every application here is rejected` (title) | fine | plain |
| Applications.jsx:38 | `Waiting on a first response` (stage hint) | fine | plain |
| Applications.jsx:622 | `Could not read job details from that URL` | fine | plain |
| Applications.jsx:578 | `paste into the AI of your choice` | fine | plain |

Short/label strings: source labels `a company scrape` / `the Log application form` /
`Jobright.ai` / `Levels.fyi` / `LinkedIn Personal` / `the LinkedIn extension` / `the extension` /
`freehire.me` / `the Job Feed` (31–35); stage labels `Applied` / `Interview` / `Offer` /
`Rejected` (38–41), `Offer received` (40); sorts `Recent activity` / `Waiting longest` /
`Company name` (46); `Network error` (111), `Could not load applications` (112),
`Could not save that change` (179), `Could not save notes` (188),
`Delete the application for "${title}"?` (195), `Application deleted` (196),
`Could not delete this application` (197), `Could not add the interview` (210),
`Removed "${what}"` (217), `Could not restore the interview` (219),
`Could not remove the interview` (222), `Could not update the interview` (226),
`Moved to ${stage}` (255), `Reply detected in Gmail` (258,362,426),
`Applied with ${résumé}` / `unknown résumé` (259,411), `Discovered via ${source}` (260),
`Applications` (271), `+ Log application` (277), `Search title or company…` (285),
`Company · ${n}` (292), `${n} of ${m} shown` (313), `Sort` (316), `Unknown Role` (361,424),
`Unknown Company` (139,364), `Couldn't load your applications` (376), `Try again` (378),
`Nothing matches those filters.` (382), `Select an application.` (395),
`No posting details captured` (410), `applied with` (429),
`Open the tailored résumé` / `No tailored résumé for this job` (430), `Cached` (436),
`Open the live posting` / `Live ↗` (437,438), `More actions` (439),
`View job in feed` / `Open cover letter` (443,444), `Delete application` (451),
`Last email · Gmail detection` (482), `Interviews · ${n}` (489),
`Toggle scheduled / done` (500), `Remove this interview` (501), `Unscheduled` (504),
`What` / `When` / `Where` / `Prep note · optional` (512–526),
placeholders `e.g. System design round` (513), `Zoom · Onsite — London` (522),
`Who I'm meeting, what to revise…` (527), `Cancel` (530,704), `Add interview` (531),
`+ Add interview` (535), `Notes · autosaves` (541), `Notes…` (543), `History` (550),
`No history recorded yet.` (563), `Prep handover — ${company}` (577), `Close` (588),
`Copied ✓` / `Copy to clipboard` (590), `Title and company are required` (628),
`Could not save this application` (643), `Log application` (652),
`Posting URL · reading…` (657), `Senior Backend Engineer` (665), `Acme` (669),
`Applied with` (673), `Stage` (683), `Applied on` (692), `Notes` (697),
`Optional — referral, recruiter contact…` (698), `Saving…` / `Save application` (705).

`fine`: 14 listed + ~70 short.

---
## Stats.jsx

| file:line | text | flag | why |
|---|---|---|---|
| Stats.jsx:520 | `OpenAI and Claude prices come from a static table; OpenRouter uses live catalog pricing refreshed at most every 12h; Claude Code and Ollama count as $0. Cost is computed per call at log time, so past rows keep the price in effect then.` (title) | long | 42 words, four claims in one tooltip |
| Stats.jsx:460 | `No stage history recorded for these — counted by current status, so anything that passed through this stage and moved on is missing` (title) | long | 22 words, two chained explanations |
| Stats.jsx:398 | `Couldn't reach the backend for some of these numbers — tiles show "—" and charts are marked unavailable until it answers.` | long | 20 words, three ideas; "until it answers" personifies |
| Stats.jsx:566 | `${n} jobs · next runs in ${TZ}, schedules as configured (UTC) · intervals and crons live in Settings` | long | three facts, two time zones, one line |
| Stats.jsx:470 | `Every row counts applications that ever reached that stage; bars are relative to Applied` | long | two ideas joined by a semicolon |
| Stats.jsx:469 | `Rows count applications that ever reached that stage; snapshot rows count current status` | long | two definitions in one sentence |
| Stats.jsx:411 | `In play = not rejected, ghosted or withdrawn` / `${n} in play` | metaphor | "in play" is a sporting figure |
| Stats.jsx:430 | `Application funnel` (card title) | metaphor | "funnel" — standard analytics usage; reviewer may keep |
| Stats.jsx:521 | `how priced?` (help affordance label) | mannered | informal lowercase question as a label |
| Stats.jsx:382 | `Last sweep ${failed}${ago}` | unclear | "sweep" is not a user term |
| Stats.jsx:408 | `Everything ever scraped or captured, minus cleanup` (KPI hint) | unclear | "minus cleanup" is opaque |
| Stats.jsx:542 | `Prompt-cache hit ratio` (title) | unclear | jargon with no explanation |
| Stats.jsx:613 | `everything the pipeline did, newest first` | unclear | "the pipeline" is internal vocabulary |
| Stats.jsx:556 | `No LLM calls in this window.` | unclear | "window" for "period" |
| Stats.jsx:409 | `${d} vs last` (KPI sub-value) | unclear | elliptical — last what? |
| Stats.jsx:179 | `Some stats failed to load — try Refresh` | fine | plain, names the fix |
| Stats.jsx:412 | `Highest-scoring posting you haven't applied to` (hint) | fine | plain |
| Stats.jsx:484 | `Average score after tailoring, across the ${n} jobs with a tailored copy` (title) | fine | plain |
| Stats.jsx:388 | `Reload every figure on this page` (title) | fine | plain |
| Stats.jsx:441,514 | `Unavailable — the request failed` | fine | plain |
| Stats.jsx:410 | `In your feed shortlist` (hint) | fine | plain |
| Stats.jsx:505 | `daily arrivals across all sources` | fine | plain |
| Stats.jsx:617 | `Filter the activity log by type` (title) | fine | plain |
| Stats.jsx:683 | `No activity matches these filters.` / `No activity recorded yet.` | fine | plain, two distinct states |

Short/label strings: period chips `1d`/`7d`/`30d`/`all` (14), type options `All types` /
`Scrape` / `H-1B` / `Résumé score` / `Email` / `Telegram` (28), `Loading…` / `Load more` (108,370),
`${job} started.` (239), `${job} is already running.` / `Could not start ${job}` (245),
`Could not load more runs` (261), `Could not load more activity` (274), `Stats` (376),
`No scrape recorded yet` (383), `${n} sources need attention` (384),
`${money} on LLM calls in ${n}d` / `all time` (385), `Refresh` (392), `Try again` (399),
KPI labels `Total jobs` / `New this week` / `Saved` / `Applications` / `Best open score` (408–412),
`Funnel` / `Flow` (434), funnel rows `Applied` / `Interview` / `Offer` / `Rejected` (337–340),
`snapshot` (461), `applied → interview ${x} · interview → offer ${y}` (471),
`Score distribution` (479), `${n} scored jobs · best résumé per job` (480),
`avg ${n}` / `tailored ${n}` (483,484), `${n} jobs scored ${range}` (490),
`New jobs · last 30 days` (504), `new` / `applied` legend (508), `LLM costs` (519),
`Spend` / `Calls` / `Avg / call` (530,531), column heads `Purpose` / `Model` / `Calls` /
`Cost` / `Cache` (540–542), `Schedules` (565), `Job` / `Job ID` / `Schedule` / `Next run` /
`Status` / `Run` (569–574), `now` (583), `Running · ${dur}` / `Pending` / `Scheduled` (589),
`${job} is running` / `Run ${job} now` (595), `Running…` / `Run now` (598),
`Run history` / `Activity log` (610), `last ${n} scheduler and manual runs` (613),
`Type · 1` (618), `Company…` (635), run columns `Time` / `Job ID` / `Trigger` / `Status` /
`Duration` / `Result` (645,646), `No runs yet.` (663), activity columns `Time` / `Type` /
`Message` / `Company` (669,670), `peak ${n} · ${day}` (717),
cron phrasings `Daily at HH:MM` / `every N min` / `Day N …` / `${DOW} …` (81–89).

`fine`: 9 listed + ~65 short.

---
## Searches.jsx

| file:line | text | flag | why |
|---|---|---|---|
| Searches.jsx:81 | `Jobs arrive via the "Save to Job Feed" button on any website. Set auto-score depth and the filters below — they apply as each job is saved.` (note banner) | long | 25 words, three instructions |
| Searches.jsx:79 | `Configure filters on levels.fyi, then paste the URL here — location, job family, salary and recency are all encoded in it.` (note banner) | long | 20 words, instruction plus explanation |
| Searches.jsx:80 | `Personalized AI recommendations from your Jobright.ai account. A search term switches it to search mode; credentials live in Settings.` (note banner) | long | three unrelated facts; "credentials live in" |
| Searches.jsx:575 | `Light — every new result gets a score only; open a job to generate its report` (title) | long | two instructions in one tooltip |
| Searches.jsx:68 | `Score only — cheap enough to leave on` (depth hint) | mannered | conversational aside, not a description |
| Searches.jsx:275 | `Credentials live in Settings › Accounts` | metaphor | "live in" |
| Searches.jsx:550 | `running now — results land in the Job Feed as they arrive…` | metaphor | "land in" |
| Searches.jsx:657 | `Create one to start pulling roles into the Job Feed on a schedule.` | metaphor | "pulling roles into" |
| Searches.jsx:249 | `ANDed with the URL — must appear in the posting text` (field sub) | unclear | "ANDed" is developer jargon |
| Searches.jsx:252 | `Role, seniority, countries, posted_within_days… pass straight through` (field sub) | unclear | raw parameter name in user copy |
| Searches.jsx:532 | `Runs on the next scheduled sweep once created` | unclear | "sweep" is not a user term |
| Searches.jsx:582 | `Pause — leaves the schedule, config is kept` (title) | unclear | "leaves the schedule" reads two ways |
| Searches.jsx:599 | `Dry run — previews results and per-job filter reasons, saves nothing` (title) | unclear | "dry run", "per-job filter reasons" |
| Searches.jsx:82 | `Jobs import via passive capture on linkedin.com/jobs/collections/* pages. The filters below auto-filter during import.` (note banner) | unclear | "auto-filter during import" is circular |
| Searches.jsx:785 | `${n} kept · ${m} filtered · ${r} raw · ${d}s` | unclear | "raw" as a count label |
| Searches.jsx:67 | `New results arrive unscored — score them by hand from the feed` (depth hint) | fine | plain |
| Searches.jsx:69 | `Score plus the full report with keywords and requirements` (depth hint) | fine | plain |
| Searches.jsx:290 | `How deeply new results are scored as they arrive` | fine | plain |
| Searches.jsx:297 | `0 follows the global schedule from Settings` | fine | plain |
| Searches.jsx:304 | `Their Company scrapes already bring these postings` (title) | fine | plain |
| Searches.jsx:415 | `Last run finished cleanly but returned no jobs` | fine | plain |
| Searches.jsx:496 | `Test timed out after 5 minutes — check Stats › Run History` | fine | plain, names the next place to look |
| Searches.jsx:527 | `pick a mode — the fields below follow it` | fine | plain |
| Searches.jsx:573 | `Full — every new result gets a score plus the full report with keywords and requirements` (title) | fine | plain, one idea |
| Searches.jsx:587 | `Jobs arrive from the browser extension — there is nothing to run or test` (title) | fine | plain |
| Searches.jsx:592 | `Run in progress — the summary line updates when it finishes` (title) | fine | plain |
| Searches.jsx:592 | `Run ${name} now, outside the schedule` (title) | fine | plain |
| Searches.jsx:467 | `Delete "${name}"?` (window.confirm) | fine | plain (note: native confirm, not the v2 dialog) |
| Searches.jsx:90 | `Passive capture on linkedin.com/jobs/collections/* · title filters apply on import` | fine | plain |
| Searches.jsx:629 | `Changes apply from the next run` | fine | plain |

Short/label strings: `never` (9), `just now` / `${n}m ago` / … (11–15), `due now` (20),
mode badges `JOBSPY` / `LEVELS.FYI` / `LINKEDIN PERSONAL` / `JOBRIGHT.AI` / `FREEHIRE.ME` /
`EXTENSION` (43–49), mode options (52–56), depth labels `Off` / `Light` / `Full` (67–69),
sources `LinkedIn` / `Indeed` / `ZipRecruiter` / `Google Jobs` / `Direct (Playwright)` (71),
collections `Recommended` / `Top Applicant` (72),
`Manual "Save to Job Feed" button on any website` (91), `AI recommendations` (102,693),
`require salary` (103), `no URL` (112), field labels `Name` (212), `Mode` (214,217),
`Search term` (227), `Location` (228), `Remote` (229), `Job type` (230), `Hours old` (231),
`Results wanted` (232,253), `Max pages` (236), `Levels.fyi URL · filters applied` (237),
`Search term · optional` (242,248), `Results wanted · 20–500` (243), `Min score` (244),
`freehire.me URL · filters forwarded` (250), `Title include · comma-separated` (280),
`Title exclude` (281), `Company include · exact` (282), `Company exclude · exact` (283),
`Sources` (267), `Collections` (273), `Auto-scoring` (288), `Run interval · min` (294),
`Import rules` (301), `Skip active companies` (303), `Require salary` (306),
`Drop results without a listed salary` (306); placeholders `e.g. TPM roles — Tier 1` (212),
`e.g. technical program manager` (227), `United States` (228), `intern, junior, associate` (281),
`Any` (282), `e.g. Walmart, CommScope` (283), `Leave empty for AI recommendations` (242),
`0 = no filter` (244), `e.g. golang backend` (248), the two example URLs (238,251);
`Could not load your searches` (342), `Could not save this search` (438), `Name is required` (443),
`Could not create this search` (446), `Could not pause/resume "${name}"` (452),
`"${name}" is already running` (460), `Could not start "${name}"` (461),
`Could not delete "${name}"` (468), `Could not duplicate "${name}"` (472),
`Test run expired or not found` (493), `Searches` (509), `+ New search` (514,658),
`New search` (526), `Cancel` (533,630), `Creating…` / `Create search` (534),
`Needs attention — ${warn}` (561), `Active` / `Paused` (584),
`extension • passive capture` (588), `Running` / `Run` (595), `A test is already running` (599),
`Test` (601), `More actions` (604), `Edit search` / `View results in feed` / `Duplicate` (608–610),
`Delete search` (616), `Saving…` / `Save changes` (631), `Loading searches…` (644),
`Couldn't load your searches` (649), `Try again` (651), `No searches yet` (656),
`Test run — ${name}` (714), `dry run · nothing saved` (715), `Term` (725),
`All (${n})` / `Kept (${n})` / `Filtered (${n})` (737), columns `Source` / `Company` / `Title` /
`Location` / `Salary` / `Desc` / `Status` (747–753), `Description scraped` (752),
`Passed all filters` (771), `Kept` / `Out` (771), `Nothing was filtered out.` /
`Nothing passed the filters.` / `No results returned.` (778), `Close` (787).

`fine`: 15 listed + ~90 short.

---
## Companies.jsx

| file:line | text | flag | why |
|---|---|---|---|
| Companies.jsx:805 | `${k} kept · ${x} keyword-filtered · ${r} validation-rejected · ${t} extracted · ${p} pass this company's filters · ${d} removed by the global list` | long | six figures and four coined terms in one line |
| Companies.jsx:699 | `No known ATS — the page is loaded and read as HTML. If it lists nothing, set a wait-for selector in the company config.` | long | 23 words, explanation plus conditional fix |
| Companies.jsx:773 | `Title filters, wait-for selector and max pages use the defaults — change them in the company config when a board needs it.` | long | 21 words, two ideas |
| Companies.jsx:537 | `No filings on record, so jobs here show H-1B Unknown. Blank auto-detects from the company name.` | long | second sentence is about a different thing |
| Companies.jsx:240,241 | `Applies to the ${n} companies in the current filter · jobs already found are kept` | long | scope plus a reassurance in one line |
| Companies.jsx:502 | `Add one with + Add company — its career page is scraped and the jobs land in the Feed.` | metaphor | "jobs land in the Feed" |
| Companies.jsx:601 | `Postings under these names collapse into this company.` | metaphor | "collapse into" |
| Companies.jsx:537 | `${n} filings on record · ${p}% approved — each job's H-1B verdict is drawn from these.` | metaphor | "drawn from" |
| Companies.jsx:424 | `${name} · ${n} H-1B filings on record, ${p}% approved — feeds the verdict on each job` (title) | metaphor | "feeds the verdict" |
| Companies.jsx:466 | `Dry run — shows what would be kept, writes nothing` (title) | unclear | "dry run" unexplained |
| Companies.jsx:851 | `Pagination debug` | unclear | developer label shown to the user |
| Companies.jsx:813 | `Global` (status tag on a filtered row) | unclear | a bare adjective as a status |
| Companies.jsx:440 | `H-1B slug · ${slug or auto-detected}` (title) | unclear | "slug" is a developer term |
| Companies.jsx:586 | `Detected on the recent runs` | unclear | reads as broken grammar |
| Companies.jsx:659 | `Stops paging after this many.` | unclear | elliptical; "paging" undefined |
| Companies.jsx:68 | `Longest since a run first` (sort hint) | unclear | elliptical |
| Companies.jsx:357 | `Add/remove from filter · multi-select, remembered per browser` (title) | unclear | "remembered per browser" |
| Companies.jsx:698 | `Jobs are read from the board's API, so no page settings are needed.` | fine | plain, gives the reason |
| Companies.jsx:701 | `New jobs arrive unscored — you can score them by hand from the feed.` | fine | plain |
| Companies.jsx:614 | `Supports AND, OR and parentheses. Blank keeps every title.` | fine | plain, two short sentences |
| Companies.jsx:649 | `Blank follows the schedule set in Settings.` | fine | plain |
| Companies.jsx:654 | `CSS selector the page must render before reading.` | fine | plain; jargon is the field's subject |
| Companies.jsx:644 | `Groups companies for filtering and bulk actions.` | fine | plain |
| Companies.jsx:539 | `Nothing selected, so new jobs use your default résumé from Settings.` | fine | plain |
| Companies.jsx:404 | `Which résumés new jobs from this company are scored against` (title) | fine | plain |
| Companies.jsx:445 | `${n} open roles from ${name} in the Job Feed · ${m} new in the last 7 days` (title) | fine | plain |
| Companies.jsx:434 | `Inactive — jobs already found are kept` (title) | fine | plain |
| Companies.jsx:673 | `Make inactive — jobs already found are kept` | fine | plain |
| Companies.jsx:502 | `Nothing matches "${q}" in names, aliases, URLs or ATS.` | fine | plain |
| Companies.jsx:567 | `Save failed — nothing was changed. Try again.` | fine | plain |
| Companies.jsx:320,325 | `Discard changes?` / `Edits to ${name} have not been saved.` | fine | plain |
| Companies.jsx:729 | `Paste a careers URL — the ATS is read from it.` | fine | plain |
| Companies.jsx:878 | `No job links found on this page.` | fine | plain |

Short/label strings: `never` + relative times (12–19); sort labels `Needs attention` /
`Company name` / `Priority tier` / `Open roles` / `Average fit` / `Last scrape` (63–68);
sort hints `Warnings, then active, then inactive` / `A to Z` / `Tier 1 first, untiered last` /
`Most roles in the feed first` / `Best-scoring companies first` (63–67);
depth labels and hints `Off` / `New jobs are stored unscored` / `Light` / `Scores only, no report` /
`Full` / `Full report with keywords and requirements` (71–73); `None` (75);
`Remove this URL` (93); `+ Add another career page` (99); `Persona` (124);
`Could not load companies` (167); `${n} tracked · ${a} active · ${d} need attention` (236);
`Could not save company changes` (246); `Could not update ${n} of ${m} companies` (252);
`${n} companies made active/inactive` (253); `That company is already being scraped` (263);
`Could not start the scrape` (264); `Delete ${name}?` / `Jobs already found are kept.` (274);
`${name} deleted` / `Could not delete ${name}` (276,277); `${n} selected` (289);
health texts `scraping now…` / `error · ${e}` / `last run found nothing · ${ago}` /
`not scraped yet` / `healthy · scraped ${ago}` / `inactive · last run ${ago}` (292–298);
`Companies` (334); `+ Add company` (341); `Search name, alias, URL or ATS…` (349);
`Untiered` / `Tier ${n}` (359); `Make ${n} active` / `Make ${n} inactive` (366,370);
`Change row order` / `Sort` (374,376); column heads `Company` / `Tier` / `Health` / `Résumés` /
`ATS` / `Open · 7d` / `Apps` / `Ø Fit` / `Status` (401–409) with their titles (405–408);
`Needs attention — ${e}` (423); `Also scraped as ${aliases}` (425);
`Last successful run ${ago}` (434); `Scored against your default résumé from Settings` /
`Default` (437); `No scored roles yet` / `Average fit ${n} …` (451);
`Click to pause scraping` / `Click to resume scraping` (454); `Active` / `Inactive` (455);
`Scrape this company now` (459); `Running` / `Run` (464); `Test` (468); `More actions` (470);
`Edit config` (474); `Open career page` / `Open ${n} career pages` (475);
`View jobs in feed` (476); `Delete company` (477); `Loading companies…` (486);
`Couldn't load companies` (494); `Try again` (496); `No companies yet` / `No companies match` (501);
`No companies in ${tiers}.` (502); `Clear filters` (503); drawer subtitle (535);
`New jobs are scored against ${names}.` (539); `needs attention` / `customised` /
`using defaults` (540); `Last scrape run` / `last ran ${ago}` (586);
`Identity and sources` (593); `Display name` (595); `Also known as` (599);
`Alt names, comma-separated` (600,747); `Which postings to keep` (610); `Title must match` (612);
`(Product OR Project) AND Manager` (613); `Skip titles containing` (617);
`intern, junior, associate` (618); `Comma-separated. Applied after the match above.` (619);
`Score new jobs automatically` (622); `Scraper tuning` (635); `Priority tier` (642);
`Scrape interval in minutes` (647,756); `Use global interval` (648,757);
`Wait for element` (652); `CSS selector` (653); `Pages to read` (657);
`H-1B employer name` (663); `Auto-detect` (664); `Make active` (673);
`Testing…` / `Test scrape` (676); `Saving…` / `Save changes` (679);
`The ATS is detected once you paste a URL.` (697); `Company name is required` (707);
`Could not add company` (719); `Add company` (728); `Career page URL` (733);
`Acme` (743); `Aliases` (746); `Tier` (752); `Score new jobs against` (761); `Depth` (764);
`Scrapes on the next scheduled run` (776); `Cancel` (777); `Save` (778);
`Test scrape — Error` (791); `Close` (793,883); `Drop` / `Kept` / `Out` (811–814);
`Test scrape — ${company}` (820); `Hide/Show screenshots` (822); `URLs scraped · ${n}` (828);
`Include` / `Exclude` (832,833); `Page ${n} · Clicked …` / `No next button found` (853);
columns `#` / `Title` / `Status` / `Reason` / `Link` (860–864).

`fine`: 16 listed + ~95 short.

---
## Settings.jsx

The densest file on the screen: `help`, `offHelp`, `info` and `sub` fields on
~70 rows. Flagged rows first, then the plain ones.

| file:line | text | flag | why |
|---|---|---|---|
| Settings.jsx:313 | `Providers: Claude API (Anthropic), Claude Code, OpenAI, Ollama (local), OpenRouter. Picking a provider filters the model dropdown to that provider's models — seeded ones plus any you added under Custom models. OpenRouter reaches every vendor with one key but gets no prompt-cache discount.` (info) | long | 43 words, three ideas; "Custom models" is not the real label ("Model catalog") |
| Settings.jsx:317 | `Fires only when the scoring call errors or hits a rate limit; one retry, then the job is left unscored for the next sweep. Pick a cheap, reliable model from a different provider than the Primary so one outage can't take both down.` (info) | long | 42 words; "sweep"; "take both down" |
| Settings.jsx:334 | `Only active when the effective provider is claude_api — no effect with Claude Code, Ollama or OpenRouter. If scoring output ever looks stale after a rubric edit, disable this as a rollback lever, run once, re-enable.` (info) | metaphor | "rollback lever"; also 35 words |
| Settings.jsx:323 | `For models newer than the seeded list. The add search hits the provider's live catalog for OpenRouter, OpenAI and Claude; Ollama has no catalog — enter the local model name. Removals persist.` (info) | long | 31 words, three ideas |
| Settings.jsx:330 | `Light returns scores + a one-liner (cheap, for high-volume searches). Full adds keyword coverage, requirement mapping and a written report. Companies and Searches can each override this per config.` (info) | long | 29 words, three sentences |
| Settings.jsx:432 | `Capture happens while the extension browses LinkedIn collections. Doing that on a throwaway account means rate limits, CAPTCHAs or bans hit the mock identity — never your real profile.` (info) | long | 28 words, two ideas |
| Settings.jsx:399 | `Telegram sends the secret as X-Telegram-Bot-Api-Secret-Token on every webhook call; mismatched headers return 401. Rotating shows the new secret once — copy it immediately, then re-register the webhook.` (info) | long | 27 words, protocol detail plus a procedure |
| Settings.jsx:376 | `Counts from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in the Stats funnel — nothing is deleted.` (info) | long | 26 words; "funnel" |
| Settings.jsx:417 | `Each application gets its own short link per document link. When a recruiter opens one, the hit lands in Stats against that application.` (info) | metaphor | "the hit lands in Stats" |
| Settings.jsx:333 | `Rubric + résumés + schema sent as a cached block — ~10× cheaper input tokens on repeat calls.` (help) | long | 16 words of dense jargon |
| Settings.jsx:396 | `Optional — alerts and the digest work without a webhook. Validates every Telegram → backend call.` (help) | long | two unrelated statements in one help line |
| Settings.jsx:341 | `Default: selection from Persona's richer pool, falls back to the résumé prompt if empty.` (help) | metaphor | "richer pool" |
| Settings.jsx:430 | `The extension import reuses a signed-in cookie. LinkedIn gates the login behind an emailed PIN.` (help) | metaphor | "gates the login behind" |
| Settings.jsx:435 | `escape hatches — most days none of this gets touched` (section sub) | metaphor | "escape hatches"; conversational aside |
| Settings.jsx:391 | `Telegram bot · digest schedule lives under Scheduler` (section sub) | metaphor | "lives under" |
| Settings.jsx:310 | `each individual prompt can be run against different model, if needed` (section sub) | unclear | missing article; "different model" than what? |
| Settings.jsx:314 | `Key for the Primary provider API model.` (help) | unclear | three nouns stacked; no article |
| Settings.jsx:368 | `Additional known sender domains check.` (help) | unclear | not a sentence |
| Settings.jsx:419 | `Your domain needs to support selected style.` (help) | unclear | missing article; vague "support" |
| Settings.jsx:385 | `Exclusion of the job title matches.` (help) | unclear | not a sentence |
| Settings.jsx:384 | `Exclusion of postings whose description matches any phrase from this list.` (help) | unclear | nominalised opener ("Exclusion of…") |
| Settings.jsx:386 | `Exclusion of exact company names` (help) | unclear | nominalised, no period |
| Settings.jsx:369 | `Exclusion of newsletters and job-alert spam.` (help) | unclear | same nominalised pattern |
| Settings.jsx:343 | `Rescores tailored resume when the tailor finishes.` (help) | unclear | "the tailor" reads as a person; also `resume` unaccented here, `résumé` everywhere else |
| Settings.jsx:340 | `Default: rewrites only bullets that benefit.` (help) | unclear | benefit from what? |
| Settings.jsx:331 | `Score a job once you save it on the feed, if yet unscored.` (help) | unclear | "if yet unscored" |
| Settings.jsx:327 | `Extra requests queue — protects the DB pool.` (help) | unclear | "DB pool" is internal |
| Settings.jsx:335 | `placeholders stay literal — replaced at runtime` (sub) | unclear | the two halves appear to contradict |
| Settings.jsx:348 | `Label + prompt per voice, can be expanded.` (help) | unclear | "can be expanded" — by whom, how? |
| Settings.jsx:357 | `the handover bundle Applications exports for your LLM of choice` (section sub) | unclear | "handover bundle" is invented vocabulary |
| Settings.jsx:358 | `The hardcoded ask appended to the handover.` (help) | unclear | "hardcoded" contradicts an editable field; "the ask" as a noun |
| Settings.jsx:359 | `Sections the handover carries. Ask is always included.` (help) | unclear | "Ask" as a bare noun |
| Settings.jsx:392 | `High-fit arrivals and the daily digest go to your chat.` (help) | unclear | "High-fit arrivals" is compressed |
| Settings.jsx:290 | `That did not work` (error toast) | unclear | says nothing about what failed |
| Settings.jsx:703 | `No key — the dashboard is open` (placeholder) | unclear | "open" = unprotected is not obvious |
| Settings.jsx:940,955 | `Search ${n} live models, or paste any slug…` / `${n} of ${m} match · or paste any slug and Add` | unclear | "slug" is a developer term |
| Settings.jsx:972 | `Remove — removal persists` (title) | unclear | repeats itself; "persists" unexplained |
| Settings.jsx:311 | `Every AI feature uses this pair unless overridden below.` | fine | plain |
| Settings.jsx:316 | `Retries scoring once on error or rate limit — scoring only.` | fine | plain |
| Settings.jsx:326 | `Used when a company has no résumés of its own selected.` | fine | plain |
| Settings.jsx:328 | `Used when neither the company nor the search sets its own.` | fine | plain |
| Settings.jsx:364 | `Replies are auto-classified into interview / rejection / offer and attached to the right application.` | fine | plain |
| Settings.jsx:365 | `0–100 — below this, the email is flagged for manual review instead.` | fine | plain |
| Settings.jsx:374 | `Days before ignored and skipped job postings are removed.` | fine | plain |
| Settings.jsx:375 | `Days of silence before an application is auto-moved to Rejected.` | fine | plain |
| Settings.jsx:383 | `titles, companies and body phrases dropped before anything else runs` (section sub) | fine | plain |
| Settings.jsx:389 | `Query params removed from job URLs. All utm_* are always stripped.` | fine | plain |
| Settings.jsx:393 | `Your Telegram chat — get it by messaging @userinfobot.` | fine | plain, actionable |
| Settings.jsx:394 | `Only jobs scoring at or above this trigger an instant alert.` | fine | plain |
| Settings.jsx:395 | `Confirms the bot token and chat ID work end to end.` | fine | plain |
| Settings.jsx:401 | `Rotate the webhook secret? You must re-register the webhook afterward.` (window.confirm) | fine | plain (note: native confirm) |
| Settings.jsx:403 | `Copy the new secret now — it will not be shown again:` (window.prompt) | fine | plain (note: native prompt) |
| Settings.jsx:406 | `Points Telegram at your public URL so inbound bot commands reach the backend.` | fine | plain |
| Settings.jsx:416 | `Résumé and letter links route through your domain.` | fine | plain |
| Settings.jsx:436 | `Used by scrapes that hit rate limits or geo-blocks. Empty = direct.` | fine | plain |
| Settings.jsx:437 | `Saving refreshes the session cookie so iframes keep working.` | fine | plain |
| Settings.jsx:353 | `Answers as the candidate, from Persona autofill content only.` | fine | plain |
| Settings.jsx:482 | `Saves automatically · everything stays on this machine` | fine | plain |
| Settings.jsx:70 | `no models for this provider — add one under Model catalog` | fine | plain, names the fix |
| Settings.jsx:748 | `LinkedIn emailed a PIN to the mock account.` | fine | plain |
| Settings.jsx:784 | `Not valid JSON — nothing saved yet` | fine | plain |
| Settings.jsx:810 | `Defaults are unavailable — nothing was reset` | fine | plain |

Short/label strings: provider names (7–11); `Select…` (60); `type a new value to replace it` (123);
`hide` / `show` (129,706); `On` / `Off` (565); `The server did not answer.` (187);
`Settings are not loaded yet` (228); `Saved` / `Could not save — try again` (238,245);
row labels `Primary provider · model` (311), `API key` (314), `Scoring` (315),
`Scoring fallback` (316), `Tailoring` (318), `Cover letters` (319), `Autofill` (320),
`Email classification` (321), `Model catalog` (322,923), `Default résumé` (326),
`Max parallel jobs` (327), `Default depth` (328), `On save action` (331),
`Prompt caching` (333), `Scoring rubric` (335), `Light output schema` (336),
`Full output schema` (337), `Résumé tailoring prompt` (340), `Persona tailoring prompt` (341),
`Max parallel tailors` (342), `Auto-score after tailoring` (343), `Default voice` (347),
`Voice presets` (348), `Cover letter prompt` (349), `Default answer length` (352),
`Autofill prompt` (353), `Field patterns` (354), `Option synonyms` (355),
`"What I need from you" section` (358), `Include by default` (359),
`LLM classification` (364), `Confidence threshold` (365), `Classification prompt` (366),
`Gmail query · subjects` / `· senders` / `· exclusions` (367–369),
`Scrape all companies` (372), `Email check` (373), `Cleanup after` (374),
`Auto-reject threshold` (375), the five `· cron` rows (377–381), `Body phrases` (384),
`Title exclude` (385), `Company exclude` (386), `Stripped params` (389), `Telegram` (392),
`Chat ID` (393), `Score threshold` (394), `Test` / `Send test message` (395),
`Webhook secret` / `Rotate` (396,397), `Set (hidden — rotate to view)` / `Set` / `Not set` (398),
`Register webhook` / `Register…` (406), `Rewrite links` (416), `Base URL` (418),
`URL style` + its four options (419–421), `Email` / `Password` (424,425),
`Personal email` / `Personal password` (428,429), `Session cookie` (430),
`Mock account email` / `Mock account password` (431,433), `Proxy URL` (436),
`Dashboard API key` (437), `DB backup` / `Run backup` (438);
section titles `Models` / `Scoring behavior` / `Tailoring` / `Cover letters` / `Autofill` /
`Interview prep` / `Email classification` / `Scheduler` / `Global exclude` /
`Dedup tracking params` / `Notifications` / `Tracer links` / `Jobright.ai` / `LinkedIn` /
`Advanced` (310–439) and group heads `AI` / `PIPELINE` / `INTEGRATIONS` / `SYSTEM`;
select option labels `(all bases + Persona)` (296), `Light — score only` /
`Full — score + keywords + report` / `Off — don't score on save` (329–332,344),
`${id} — not in presets` (307), prep-include options (360,361);
subs `placeholders: {…}` (340,341,349,353,366), `one term per line …` (367–369,384–386,389),
`JSON — …` (348,354,355), `CV_NAMES_HERE expands to your résumé names` (336,337);
`Settings` (480), `Search settings…` (487), `No settings match "${q}".` (524),
`JobNavigator v.2.0` (532), `API docs ↗` (536), `github.com/vesaias/JobNavigator ↗` (538),
`Couldn't load your settings` / `Try again` (455,457), `Loading settings…` (461),
`inherits Primary` (588), `Override` (590), `API key for this override's provider` (584),
`pick provider…` / `pick model…` (572,581,582), `Edit` (614),
`${n} models · ${x} seeded · ${c} added by you` (624), `Manage…` (626),
`More detail` (661), `Running…` / `Done ✓` (687),
`Set — type a new key to replace it` (703), `Save key` (708), `Type the new key first` (709),
`Key saved` (716), `Could not start the refresh` (738), `Signing in…` / `Unknown` (749,750),
`6-digit PIN` (755), `Submit PIN` (758), `Enter the digits from the email` (761),
`PIN sent` (762), `Could not send the PIN` (763), `Refresh cookie` (767),
`Saves automatically as you type` (844), `Reset to default` (845), `Done` (846),
`Could not reach the catalog` (871), `Remove "${m}" from ${provider}?` (915),
`available in every model picker` (924), `Loading live models…` (940),
`Enter the local model name…` (941), `↵ to add` (951), `Add` (960),
`added by you` / `seeded` (969).

`fine`: 26 listed + ~130 short.

---
## JobFeed.jsx

| file:line | text | flag | why |
|---|---|---|---|
| JobFeed.jsx:339 | `Ignore "${name}" everywhere?\n\nThis hides ${n} jobs here and excludes the company from every future scrape. Undo it in Settings → global company exclude.` (window.confirm) | long | 27-word body, three ideas (also a native confirm) |
| JobFeed.jsx:1098 | `${company} sends X-Frame-Options, so the live page cannot render here. Open it in a new tab, or install the Navigator extension to strip frame-blocking headers.` | long | 25 words; HTTP header name as user copy |
| JobFeed.jsx:773 | `Jobs arrive from Searches and Companies — activate one, or widen the Status filter to see skipped and applied roles.` | long | 19 words, two unrelated suggestions |
| JobFeed.jsx:1097 | `This posting refuses to be framed` | metaphor | personifies the page; "framed" is jargon |
| JobFeed.jsx:1169 | `Instant · no LLM cost · lands in Résumés` | metaphor | "lands in" |
| JobFeed.jsx:1051 | `No fit` (label on the unscored band's ring) | unclear | reads as "a bad fit", not "not scored" |
| JobFeed.jsx:1040 | `This report was quick-scored — rescore at full depth for the keyword and requirement breakdown.` | unclear | "quick-scored" is called `Light` everywhere else; "full depth" |
| JobFeed.jsx:1141 | `Rewrites bullets against the report · LLM run` | unclear | it rewrites against the posting, not the report |
| JobFeed.jsx:1169 | `Runs an LLM pass against résumé` | unclear | missing article; "LLM pass" |
| JobFeed.jsx:609 | `${verdict} · ${n} LCAs` / `${verdict} · no LCA records` | unclear | "LCA" is never expanded |
| JobFeed.jsx:1029 | `Hard blockers` (report section heading) | unclear | invented term |
| JobFeed.jsx:735 | `⇧ range · ${PICK_KEY} pick` | unclear | two glyph-verb pairs, no sentence |
| JobFeed.jsx:587 | `Done — "${title}" at ${company}` / `Failed — "${title}" at ${company}` (toast) | unclear | "Done" doesn't say what finished (score? tailor?) |
| JobFeed.jsx:895 | `Copy résumé with tracers` (menu item) | unclear | "tracers" unexplained at this point |
| JobFeed.jsx:1161,1203 | `from /persona` (option note) | unclear | a route path used as a label |
| JobFeed.jsx:633 | `The Feed` (page title) | unclear | the nav rail calls the same screen `Jobs` |
| JobFeed.jsx:1066 | `This continues in the background if you navigate away.` | fine | plain reassurance |
| JobFeed.jsx:1053–1055 | `Not scored yet Score against your résumés for the fit breakdown, requirements and keywords` | fine | plain |
| JobFeed.jsx:692 | `Also hides unscored jobs — they have no score to compare` | fine | plain, gives the reason |
| JobFeed.jsx:702 | `Also hides jobs without a listed salary` | fine | plain |
| JobFeed.jsx:651 | `Showing only jobs from this saved search — click to clear` (title) | fine | plain |
| JobFeed.jsx:637 | `Pick résumés + depth, then score every unscored job` (title) | fine | plain |
| JobFeed.jsx:634 | `${total} open roles · ${n} arrived today · ${m} not yet scored` | fine | plain |
| JobFeed.jsx:676 | `Top by open roles · picked companies pin to the top` | fine | plain, describes the order |
| JobFeed.jsx:854 | `End of the list · ${total} jobs` | fine | plain |
| JobFeed.jsx:1078 | `Cached snapshot · captured when you applied` | fine | plain |
| JobFeed.jsx:1106 | `No posting URL captured for this job.` | fine | plain |
| JobFeed.jsx:1132 | `A tailored copy already exists for this job.` | fine | plain |
| JobFeed.jsx:1141 | `Exact duplicate with tracking links · instant` | fine | plain; explains "tracers" |
| JobFeed.jsx:1098 | `You applied to this role, so a cached snapshot is available.` | fine | plain |

Short/label strings: H-1B verdicts `H-1B Likely` / `Possible` / `Unlikely` / `Unknown` (34–37);
badges `Applied` / `Saved` / `Skipped` / `Ignored` (40–43); source labels (46–48);
status options `New` / `Saved` / `Applied` / `Skip` / `Ignored` (51);
sort options `Top score` / `Newest first` / `Salary, high to low` / `Company A–Z` (52);
shortcut rows `Next job` / `Previous job` / `Save / unsave` / `Skip` / `Mark applied` /
`Open posting` / `Rescore` / `Tailor résumé` / `Cover letter` / `Close menus` / `Select` /
`Select range` (103); `Clear` (75); `Couldn't load jobs` (246,768);
`Couldn't update "${t}"` (321); `Saved "${t}"` / `Unsaved "${t}"` (329); `Skipped "${t}"` (330);
`Applied to "${t}"` (331); `Ignoring "${name}" — ${n} jobs hidden` (348);
`Couldn't ignore "${name}"` (349); `Scoring "${t}"…` (353,380);
`Scoring failed for "${t}"` (357); `Scoring ${n} jobs…` (378); `Tailoring for "${t}"…` (396);
`Copy failed for "${t}"` / `Tailor failed for "${t}"` (401); `${n} unscored jobs` (434);
`Saved ${n} jobs.` / `Skipped ${n} jobs.` (447); `Could not update ${n} jobs` (448);
`No cached snapshot.` (485,486); `That job no longer exists` (514); `The Feed` (633);
`Score ${n} unscored jobs` (637); `Search titles…` (646); `Clear search` (647);
`from "${searchName}"` (653); `Source` / `Company` / `H-1B` / `Score ≥` / `Salary` /
`Status` / `Sort` filter pills (656–719); `No sources` (657);
`Type to search ${n} companies…` (660); `No matches` (678); `or at least` (689);
`at least` (699); `$K` (700); `Any` (710); `Select all shown` (732);
`${n} shown · ${m} matching` (733); `Keyboard shortcuts` (736); `Keyboard` (742);
`${n} selected` (756,1193); `Save` / `Skip` / `Score` / `Tailor` bulk bar (758–761);
`Loading…` (767); `Try again` (768); `No open roles yet` (772); `No jobs match.` (775);
`Clear filters` (775); `${n} résumé reports` (796); `Score this role` (804,1057);
`Salary not listed` (821,873,878); `Save (s)` / `Skip (x)` / `More` (829–831);
`Mark applied` / `Tailor résumé` / `Rescore` / `Open posting ↗` (841);
`Ignore ${company} everywhere` (845,900); `Loading more…` (853); `Select a job.` (860);
`Open tailored résumé` (812); `Open ↗` (882); `✦ Open tailored ↗` (883);
`More actions` (885); `✦ Re-tailor résumé` / `Cover letter ↗` (891,894);
`${n}% keywords` (922); `${m} of ${n} requirements met` (923); `${n} reports` (925);
`+ Rescore` (941); `Score breakdown` (951); `/20` (963); `Keyword coverage` (977);
`${n} matched · ${m} missing` (986); `Hide matched` / `Show matched` (987);
`Requirement mapping` (1000); `${n} of ${m} met` (1001); `All ${n}` / `Gaps ${n}` (1006);
`Requirement` / `Résumé match` / `Status` (1013); `ATS tip` (1035);
`Not scored yet` (1053); `Scoring in progress` (1065); `Live posting` (1078);
`Live` / `Cached` (1080,1081); `Loading cached snapshot…` (1086);
`Open in new tab ↗` (1100); `View cached snapshot` (1101); `Create résumé copy` (1124);
`${n} selected roles` (1125); `Open it ↗` (1133); `Method` (1139);
`✦ Tailor with AI` / `⧉ Copy with tracers` (1141); `Base résumé` (1153);
`No base résumés found.` (1154); `Cancel` (1170,1226); `Create copy` (1171);
`${verb} against résumés` (1184); `Résumés` (1192); `No résumés available.` (1195);
`base` (365); `Depth` (1209); `Light` / `Scores only` / `Full` / `Report + keywords` (1211);
`Runs in the background` (1225); `Pick at least one résumé` (1227); `Run scoring` (1227);
`just now` / `${n}h ago` / `${n}d ago` (18–20).

`fine`: 14 listed + ~110 short.

---
## Summary

Counts are of *strings*, not lines. "Total" is every user-visible string found in
the file (listed rows plus the batched short/label strings). "Flagged" excludes
`fine`.

| file | total strings (approx.) | mannered | metaphor | hedge | long | unclear | flagged |
|---|---|---|---|---|---|---|---|
| time.js | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| ConfirmDialog.jsx | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| hooks.js | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Toast.jsx | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| WelcomeModal.jsx | 13 | 1 | 0 | 0 | 0 | 0 | 1 |
| ToastLab.jsx | 27 | 1 | 0 | 0 | 1 | 5 | 7 |
| LoginModal.jsx | 17 | 0 | 0 | 0 | 1 | 0 | 1 |
| V2App.jsx | 32 | 0 | 0 | 0 | 1 | 2 | 3 |
| Resumes.jsx | 47 | 0 | 2 | 0 | 0 | 2 | 4 |
| ResumeSections.jsx | 62 | 0 | 1 | 0 | 1 | 3 | 5 |
| ResumeEditor.jsx | 91 | 1 | 2 | 0 | 0 | 8 | 11 |
| CoverLetters.jsx | 41 | 0 | 0 | 0 | 0 | 3 | 3 |
| CoverLetterEditor.jsx | 56 | 0 | 1 | 0 | 0 | 4 | 5 |
| Persona.jsx | 71 | 1 | 1 | 0 | 3 | 0 | 5 |
| Applications.jsx | 95 | 0 | 3 | 0 | 2 | 6 | 11 |
| Stats.jsx | 89 | 1 | 2 | 0 | 6 | 6 | 15 |
| Searches.jsx | 120 | 1 | 3 | 0 | 4 | 7 | 15 |
| Companies.jsx | 128 | 0 | 4 | 0 | 5 | 8 | 17 |
| Settings.jsx | 193 | 0 | 6 | 0 | 9 | 22 | 37 |
| JobFeed.jsx | 140 | 0 | 2 | 0 | 3 | 11 | 16 |
| **total** | **~1235** | **6** | **27** | **0** | **36** | **87** | **156** |

### Notes for the reviewer

- **No `hedge` hits.** No "just", "simply", "a bit", "kinda" or "feel free"
  anywhere in v2 — that class of filler is already absent.
- **`unclear` dominates**, in two kinds: internal vocabulary leaking into the UI
  (sweep, slug, tracers, LCA, dry run, prep bundle / prep handover / the bundle,
  raw, DB pool, pagination debug, Hard blockers, from /persona, the last render),
  and nominalised or ungrammatical help text, concentrated in Settings
  ("Exclusion of the job title matches.", "Additional known sender domains check.",
  "Your domain needs to support selected style.").
- **Recurring metaphors** worth deciding once and applying everywhere:
  "land / lands / landed" (Resumes 153,195; ResumeEditor 730,783; Searches 550;
  Companies 502; JobFeed 1169; Settings 417); "live in / lives under"
  (Searches 275; Settings 391); "draw from / drawn from" (Persona 344;
  CoverLetterEditor 525; Companies 537); "funnel" (Applications 41; Stats 430;
  Settings 376).
- **Naming inconsistencies** found while collecting — not prose faults, but any
  rewrite has to settle them:
  - the same screen is `Jobs` in the rail (V2App.jsx:19) and `The Feed` in its
    own header (JobFeed.jsx:633);
  - scoring depth is `Light` in Searches / Companies / Settings but
    "quick-scored" in JobFeed.jsx:1040;
  - `Delete copy` appears on the base résumé menu (ResumeEditor.jsx:535);
  - the prep export is "prep handover" (Applications.jsx:493), "prep bundle"
    (Applications.jsx:234), "the bundle" (Applications.jsx:583) and
    "handover bundle" (Settings.jsx:357);
  - Settings.jsx:313 sends the user to "Custom models"; the row is called
    `Model catalog`.
- **Native dialogs still carrying copy** (they bypass the v2 dialog system):
  window.confirm at Applications.jsx:123,195; Searches.jsx:467; JobFeed.jsx:339;
  Settings.jsx:401,915. window.prompt at Settings.jsx:403,407.
- **ToastLab.jsx** is a temporary debug route (`/v2/toasts`, not linked from the
  rail; its own header says to delete it). Its seven flags can reasonably be
  skipped rather than rewritten.
