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
