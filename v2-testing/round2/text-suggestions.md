# R4b — plain-language suggestions for v2 UI copy

Rule applied: **"Avoid mannered prose, say things plainly. No metaphors or figures of speech."**
Source list: `round2/text-candidates.md` (156 flagged rows; `ToastLab.jsx` skipped — debug route). Nothing here is applied; each row is a proposal for you to accept, edit or reject. Placeholders (`${n}` etc.) are kept as in the code.

## 0. Decide these once — they settle ~40 rows

| Term in the UI today | Suggested replacement | Where |
|---|---|---|
| **sweep** (scrape sweep, last sweep, next sweep) | **scrape run** ("last scrape run", "next scheduled run") | V2App, Stats, Searches, Settings |
| **land / lands / landed** (jobs land in the Feed, changes land, the hit lands) | **appear / are applied / is recorded** | 8 sites |
| **live in / lives under** (credentials live in Settings) | **are in / is under** | Searches, Settings, Resumes, Stats |
| **draw from / drawn from / draw on** | **use / is based on / taken from** | Persona, Companies, CoverLetterEditor |
| **funnel** (Application funnel, Stats funnel) | keep **funnel** as the chart name (standard analytics word), drop it from hints elsewhere ("kept in Stats") | Stats, Applications, Settings |
| **tracer / tracers / tracer links** | **tracked links** (first use per screen: "tracked links — short links that record when a recruiter opens them") | Résumés, Cover Letters, Feed, Settings |
| **slug** | **id** ("model id", "company id on MyVisaJobs") | Settings, Companies |
| **dry run** | **preview run — saves nothing** | Searches, Companies |
| **JD** | **job description** | ResumeEditor |
| **pipeline** | **the app** / **all runs** | ResumeEditor, Stats |
| **LCA / LCAs** | **H-1B filings** (expand once per screen) | Feed |
| **prep handover / prep bundle / the bundle / handover bundle** | one name: **prep pack** | Applications, Settings |
| **The Feed** (page title) vs **Jobs** (rail) | use **Jobs** in both, or rename the rail item to **Feed** — one word for the screen | JobFeed:633, V2App:19 |
| **quick-scored** vs **Light** | **Light** everywhere ("This report was scored at Light depth") | JobFeed:1040 |

## 1. Shell

| file:line | current | suggested |
|---|---|---|
| WelcomeModal.jsx:34 | Four steps and your search runs itself. | Four steps to set up automatic searching. |
| LoginModal.jsx:80 | First run with no key configured? Leave the field blank and sign in — you'll set one in Settings › Advanced. | If no API key is set yet, leave this blank and sign in. You can add a key later in Settings › Advanced. |
| V2App.jsx:95 | No company or search is failing, but the last scrape sweep failed · ${lastSweep}. Click → Stats · Run history. | All companies and searches are healthy, but the last scrape run failed ${lastSweep}. Click to open Run history. |
| V2App.jsx:96 | All companies and searches healthy · last sweep ${lastSweep}. Click → Stats · Run history. | All companies and searches healthy · last scrape run ${lastSweep}. Click to open Run history. |
| V2App.jsx:91 | no sweep recorded yet | no scrape run recorded yet |

## 2. Résumés (shelf + editor + shared sections)

| file:line | current | suggested |
|---|---|---|
| Resumes.jsx:153 | ${n} bases · ${m} tailored copies live under their jobs · ${k} archived | ${n} bases · ${m} tailored copies, listed under their jobs · ${k} archived |
| Resumes.jsx:195 | Nothing archived yet — copies land here when their application is rejected or goes stale. | Nothing archived yet. A copy is archived when its application is rejected or has had no activity for a long time. |
| Resumes.jsx:168 | Couldn't load your résumés — the shelf request failed. | Couldn't load your résumés. Retry, or check that the backend is running. |
| Resumes.jsx:335 | Import failed — is it a text PDF? | Import failed. The PDF must contain selectable text, not a scanned image. |
| ResumeSections.jsx:324 | ${n} characters · long summaries can push to a second page | ${n} characters · a long summary can make the résumé two pages |
| ResumeSections.jsx:135 | Empty sections are skipped in the PDF — nothing prints until you add one. | Empty sections are left out of the PDF. |
| ResumeSections.jsx:220 / CoverLetterEditor.jsx:390 | Short stub for the tracer link id (e.g. l, w, gh) | Short code used in the tracked link, e.g. l, w, gh |
| ResumeSections.jsx:293 | Suggested by tailoring — keep on review | Suggested by tailoring. Kept unless you decline it in Review. |
| ResumeSections.jsx:208 / CoverLetterEditor.jsx:370 | text · link · stub | label · URL · link code |
| ResumeEditor.jsx:730 | Changes land automatically — you review and decline afterwards. | Changes are applied automatically. You can decline any of them afterwards. |
| ResumeEditor.jsx:783 | These landed automatically. Decline any you don't want; the base text comes back. | These changes were applied automatically. Decline any you don't want to restore the base text. |
| ResumeEditor.jsx:493 | The one next step | Next step |
| ResumeEditor.jsx:493 | Pipeline complete | All steps done |
| ResumeEditor.jsx:535 | Delete copy (on a base) | Delete résumé (bases) / Delete copy (copies) |
| ResumeEditor.jsx:523 | Base résumé · ${n} tailored copies · editing here changes future tailoring only | Base résumé · ${n} tailored copies · edits here affect new copies only, not existing ones |
| ResumeEditor.jsx:489 | · tracers: ${t.source_label} ${t.clicks} | · tracked link opens: ${t.source_label} ${t.clicks} |
| ResumeEditor.jsx:631 | Exact copy of the base, with its own tracer links | Exact copy of the base, with its own tracked links |
| ResumeEditor.jsx:667 | Persona has no résumé row to copy — tailor from it instead | Persona is not a résumé, so it can't be copied. Use Tailor instead. |
| ResumeEditor.jsx:758 | Paste any JD — the copy won't be linked to a feed job | Paste a job description. The copy will not be linked to a job in the Feed. |
| ResumeEditor.jsx:813 | ${n} declined — base text restored · the rest stay | ${n} declined and restored to the base text · the other changes are kept |
| ResumeEditor.jsx:813 | All ${n} changes live · decline any to restore the base text | All ${n} changes applied · decline one to restore its base text |

## 3. Cover letters

| file:line | current | suggested |
|---|---|---|
| CoverLetters.jsx:151 / Applications.jsx:111 | The server answered ${status}. | The server returned error ${status}. Try again. |
| CoverLetters.jsx:337 | Base for achievements and motivation | Résumé to take achievements and motivation from |
| CoverLetters.jsx:254 | ${n} of ${m} letters match · ${live} live applications | ${n} of ${m} letters match · ${live} open applications |
| CoverLetterEditor.jsx:525 | Bases and Persona — switch to draw on different achievements. | Bases and Persona. Switch to use a different set of achievements. |
| CoverLetterEditor.jsx:501 | Preview failed — showing the last render · Retry | Preview failed. Showing the previous version · Retry |
| CoverLetterEditor.jsx:288 | voice and length not recorded | voice and length unknown for this letter |

## 4. Persona

| file:line | current | suggested |
|---|---|---|
| Persona.jsx:337 | Your full work history, summary, skills and achievements. The AI uses this as the source pool for tailored résumés, as raw material for cover-letter anecdotes, and as the candidate profile when scoring jobs. | Your full work history, summary, skills and achievements. Used for tailored résumés, cover letters and job scoring. |
| Persona.jsx:353 | Personal info used to auto-fill application forms — contact details, work authorization, EEO answers, salary expectations and reusable screener answers. Not used by the AI for résumé generation or scoring. | Details used to fill application forms: contact, work authorization, EEO answers, salary and reusable screener answers. Not used for résumés or scoring. |
| Persona.jsx:65 | Prefer not to answer demographic questions — autofill picks "decline" where the form allows it | Decline demographic questions where the form allows it |
| Persona.jsx:344 | Tailored résumés draw from whatever you add here. | Tailored résumés use what you add here. |
| Persona.jsx:175 | what is this? | What is this used for? |

## 5. Applications

| file:line | current | suggested |
|---|---|---|
| Applications.jsx:491 | Builds one pasteable block — the role, my résumé, the posting and what to ask for — for the AI of your choice | Builds one text block with the role, your résumé, the posting and the questions to ask, to paste into any AI chat |
| Applications.jsx:136 | ${n} applications · ${i} in interview · ${o} offers · showing the first ${x} · ${s} waiting >7d | ${n} applications · ${i} interviewing · ${o} offers · ${s} with no reply for 7+ days · showing ${x} |
| Applications.jsx:653 | For applications made outside the app — jobs from the feed log themselves when you mark them applied. | For applications made outside the app. Jobs marked Applied in the Feed are logged automatically. |
| Applications.jsx:39 | In the interview loop | Interviewing |
| Applications.jsx:41 | Closed — kept for the Stats funnel | Closed. Still counted in Stats. |
| Applications.jsx:493 | Generate prep handover for AI | Build prep pack for AI |
| Applications.jsx:234,235 | Could not build the prep bundle | Could not build the prep pack |
| Applications.jsx:583 | Building the bundle… | Building the prep pack… |
| Applications.jsx:587 | Edit the closing ask in Settings → AI | Edit the questions added at the end in Settings → AI |
| Applications.jsx:703 | The posting is cached on save | A copy of the posting is saved with the application |

## 6. Stats

| file:line | current | suggested |
|---|---|---|
| Stats.jsx:520 | OpenAI and Claude prices come from a static table; OpenRouter uses live catalog pricing refreshed at most every 12h; Claude Code and Ollama count as $0. Cost is computed per call at log time, so past rows keep the price in effect then. | Prices: OpenAI and Claude from a fixed table, OpenRouter from its catalog (updated every 12 h), Claude Code and Ollama counted as $0. Each call is priced when it is logged. |
| Stats.jsx:460 | No stage history recorded for these — counted by current status, so anything that passed through this stage and moved on is missing | No stage history for these applications. They are counted by current status only. |
| Stats.jsx:398 | Couldn't reach the backend for some of these numbers — tiles show "—" and charts are marked unavailable until it answers. | Some numbers could not be loaded. They show "—" until the backend responds. |
| Stats.jsx:566 | ${n} jobs · next runs in ${TZ}, schedules as configured (UTC) · intervals and crons live in Settings | ${n} jobs · next run shown in ${TZ}, schedule set in UTC · edit intervals in Settings |
| Stats.jsx:470 | Every row counts applications that ever reached that stage; bars are relative to Applied | Each row counts applications that reached that stage. Bar length is relative to Applied. |
| Stats.jsx:469 | Rows count applications that ever reached that stage; snapshot rows count current status | Stage rows count every application that reached the stage. Snapshot rows count current status only. |
| Stats.jsx:411 | In play = not rejected, ghosted or withdrawn / ${n} in play | Open = not rejected, ghosted or withdrawn / ${n} open |
| Stats.jsx:430 | Application funnel | keep |
| Stats.jsx:521 | how priced? | How costs are calculated |
| Stats.jsx:382 | Last sweep ${failed}${ago} | Last scrape run ${failed}${ago} |
| Stats.jsx:408 | Everything ever scraped or captured, minus cleanup | All jobs ever found, excluding ones removed by cleanup |
| Stats.jsx:542 | Prompt-cache hit ratio | Share of calls that reused a cached prompt |
| Stats.jsx:613 | everything the pipeline did, newest first | every run and change, newest first |
| Stats.jsx:556 | No LLM calls in this window. | No LLM calls in this period. |
| Stats.jsx:409 | ${d} vs last | ${d} vs previous period |

## 7. Searches

| file:line | current | suggested |
|---|---|---|
| Searches.jsx:81 | Jobs arrive via the "Save to Job Feed" button on any website. Set auto-score depth and the filters below — they apply as each job is saved. | Jobs come from the "Save to Job Feed" button on any website. The filters and auto-score depth below apply to each job as it is saved. |
| Searches.jsx:79 | Configure filters on levels.fyi, then paste the URL here — location, job family, salary and recency are all encoded in it. | Set your filters on levels.fyi and paste the URL here. The URL contains location, job family, salary and date filters. |
| Searches.jsx:80 | Personalized AI recommendations from your Jobright.ai account. A search term switches it to search mode; credentials live in Settings. | Recommendations from your Jobright.ai account. Enter a search term to search instead. Credentials are in Settings › Accounts. |
| Searches.jsx:575 | Light — every new result gets a score only; open a job to generate its report | Light: each new job gets a score. Open the job to generate a full report. |
| Searches.jsx:68 | Score only — cheap enough to leave on | Score only. Low cost. |
| Searches.jsx:275 | Credentials live in Settings › Accounts | Credentials are in Settings › Accounts |
| Searches.jsx:550 | running now — results land in the Job Feed as they arrive… | running now. Results appear in the Job Feed as they are found. |
| Searches.jsx:657 | Create one to start pulling roles into the Job Feed on a schedule. | Create one to add jobs to the Job Feed on a schedule. |
| Searches.jsx:249 | ANDed with the URL — must appear in the posting text | Added to the URL filters. Must appear in the posting text. |
| Searches.jsx:252 | Role, seniority, countries, posted_within_days… pass straight through | Role, seniority, countries and posting age are taken from the URL as is |
| Searches.jsx:532 | Runs on the next scheduled sweep once created | Runs at the next scheduled scrape after you create it |
| Searches.jsx:582 | Pause — leaves the schedule, config is kept | Pause. Removed from the schedule, settings kept. |
| Searches.jsx:599 | Dry run — previews results and per-job filter reasons, saves nothing | Preview run. Shows results and why each job was kept or filtered. Saves nothing. |
| Searches.jsx:82 | Jobs import via passive capture on linkedin.com/jobs/collections/* pages. The filters below auto-filter during import. | Jobs are captured while you browse linkedin.com/jobs/collections pages. The filters below are applied on import. |
| Searches.jsx:785 | ${n} kept · ${m} filtered · ${r} raw · ${d}s | ${n} kept · ${m} filtered · ${r} found · ${d}s |

## 8. Companies

| file:line | current | suggested |
|---|---|---|
| Companies.jsx:805 | ${k} kept · ${x} keyword-filtered · ${r} validation-rejected · ${t} extracted · ${p} pass this company's filters · ${d} removed by the global list | ${t} found · ${k} kept · ${x} removed by title filter · ${r} invalid · ${p} pass this company's filters · ${d} removed by the global exclude list |
| Companies.jsx:699 | No known ATS — the page is loaded and read as HTML. If it lists nothing, set a wait-for selector in the company config. | Unknown job board. The page is read as HTML. If no jobs are found, set a wait-for selector in the company settings. |
| Companies.jsx:773 | Title filters, wait-for selector and max pages use the defaults — change them in the company config when a board needs it. | Title filters, wait-for selector and max pages use the defaults. Change them in the company settings if needed. |
| Companies.jsx:537 (no filings) | No filings on record, so jobs here show H-1B Unknown. Blank auto-detects from the company name. | No H-1B filings on record, so jobs show H-1B Unknown. Leave blank to detect the company from its name. |
| Companies.jsx:240,241 | Applies to the ${n} companies in the current filter · jobs already found are kept | Applies to the ${n} companies shown. Jobs already found are kept. |
| Companies.jsx:502 | Add one with + Add company — its career page is scraped and the jobs land in the Feed. | Add one with + Add company. Its career page is scraped and the jobs appear in the Feed. |
| Companies.jsx:601 | Postings under these names collapse into this company. | Postings under these names are matched to this company. |
| Companies.jsx:537 (filings) | ${n} filings on record · ${p}% approved — each job's H-1B verdict is drawn from these. | ${n} H-1B filings on record · ${p}% approved. Each job's H-1B verdict is based on these. |
| Companies.jsx:424 | ${name} · ${n} H-1B filings on record, ${p}% approved — feeds the verdict on each job | ${name} · ${n} H-1B filings, ${p}% approved. Used for each job's H-1B verdict. |
| Companies.jsx:466 | Dry run — shows what would be kept, writes nothing | Preview run. Shows what would be kept. Saves nothing. |
| Companies.jsx:851 | Pagination debug | Page-by-page details |
| Companies.jsx:813 | Global | Global exclude |
| Companies.jsx:440 | H-1B slug · ${slug or auto-detected} | MyVisaJobs company id · ${slug or auto-detected} |
| Companies.jsx:586 | Detected on the recent runs | Detected in recent runs |
| Companies.jsx:659 | Stops paging after this many. | Maximum number of result pages to read. |
| Companies.jsx:68 | Longest since a run first | Longest since last run |
| Companies.jsx:357 | Add/remove from filter · multi-select, remembered per browser | Add to or remove from the filter. Multiple allowed. Saved in this browser. |

## 9. Settings

| file:line | current | suggested |
|---|---|---|
| Settings.jsx:313 | Providers: Claude API (Anthropic), Claude Code, OpenAI, Ollama (local), OpenRouter. Picking a provider filters the model dropdown to that provider's models — seeded ones plus any you added under Custom models. OpenRouter reaches every vendor with one key but gets no prompt-cache discount. | Providers: Claude API, Claude Code, OpenAI, Ollama (local), OpenRouter. The model list shows that provider's models, including any you added under Model catalog. OpenRouter covers every vendor with one key but has no prompt-cache discount. |
| Settings.jsx:317 | Fires only when the scoring call errors or hits a rate limit; one retry, then the job is left unscored for the next sweep. Pick a cheap, reliable model from a different provider than the Primary so one outage can't take both down. | Used only when the scoring call fails or is rate-limited. One retry, then the job stays unscored until the next run. Choose a cheap model from a different provider than the primary. |
| Settings.jsx:334 | Only active when the effective provider is claude_api — no effect with Claude Code, Ollama or OpenRouter. If scoring output ever looks stale after a rubric edit, disable this as a rollback lever, run once, re-enable. | Only applies to the Claude API provider. If scores look outdated after you edit the rubric, turn this off, run once, then turn it back on. |
| Settings.jsx:323 | For models newer than the seeded list. The add search hits the provider's live catalog for OpenRouter, OpenAI and Claude; Ollama has no catalog — enter the local model name. Removals persist. | Add models that are not in the built-in list. Search uses the provider's catalog for OpenRouter, OpenAI and Claude. For Ollama, type the local model name. Removed models stay removed. |
| Settings.jsx:330 | Light returns scores + a one-liner (cheap, for high-volume searches). Full adds keyword coverage, requirement mapping and a written report. Companies and Searches can each override this per config. | Light: score and one line, low cost. Full: adds keyword coverage, requirement mapping and a written report. Each company and search can override this. |
| Settings.jsx:432 | Capture happens while the extension browses LinkedIn collections. Doing that on a throwaway account means rate limits, CAPTCHAs or bans hit the mock identity — never your real profile. | The extension captures jobs while you browse LinkedIn collections. Use a separate account so rate limits, CAPTCHAs or bans affect it and not your real profile. |
| Settings.jsx:399 | Telegram sends the secret as X-Telegram-Bot-Api-Secret-Token on every webhook call; mismatched headers return 401. Rotating shows the new secret once — copy it immediately, then re-register the webhook. | Telegram sends this secret with every webhook call. Calls with the wrong secret are rejected. After rotating, the new secret is shown once: copy it, then register the webhook again. |
| Settings.jsx:376 | Counts from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in the Stats funnel — nothing is deleted. | Counted from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in Stats. |
| Settings.jsx:417 | Each application gets its own short link per document link. When a recruiter opens one, the hit lands in Stats against that application. | Each application gets its own short link for every document link. When a recruiter opens one, it is recorded in Stats for that application. |
| Settings.jsx:333 | Rubric + résumés + schema sent as a cached block — ~10× cheaper input tokens on repeat calls. | Sends the rubric, résumés and schema as a cached block. Repeat calls cost about 10× less. |
| Settings.jsx:396 | Optional — alerts and the digest work without a webhook. Validates every Telegram → backend call. | Optional. Checks every call from Telegram to the backend. Alerts and the digest work without it. |
| Settings.jsx:341 | Default: selection from Persona's richer pool, falls back to the résumé prompt if empty. | Default: uses the Persona résumé content; falls back to the résumé prompt if empty. |
| Settings.jsx:430 | The extension import reuses a signed-in cookie. LinkedIn gates the login behind an emailed PIN. | The extension import reuses a signed-in session. LinkedIn asks for an emailed PIN at login. |
| Settings.jsx:435 | escape hatches — most days none of this gets touched | rarely needed settings |
| Settings.jsx:391 | Telegram bot · digest schedule lives under Scheduler | Telegram bot · the digest schedule is under Scheduler |
| Settings.jsx:310 | each individual prompt can be run against different model, if needed | each prompt can use its own model if needed |
| Settings.jsx:314 | Key for the Primary provider API model. | API key for the primary provider. |
| Settings.jsx:368 | Additional known sender domains check. | Extra sender domains treated as job-related email. |
| Settings.jsx:419 | Your domain needs to support selected style. | Your domain must support the selected link style. |
| Settings.jsx:385 | Exclusion of the job title matches. | Skip jobs whose title matches any of these words. |
| Settings.jsx:384 | Exclusion of postings whose description matches any phrase from this list. | Skip postings whose description contains any of these phrases. |
| Settings.jsx:386 | Exclusion of exact company names | Skip jobs from these companies (exact name). |
| Settings.jsx:369 | Exclusion of newsletters and job-alert spam. | Ignore newsletters and job-alert email. |
| Settings.jsx:343 | Rescores tailored resume when the tailor finishes. | Scores a tailored résumé as soon as tailoring finishes. |
| Settings.jsx:340 | Default: rewrites only bullets that benefit. | Default: rewrites only bullets that the job description makes relevant. |
| Settings.jsx:331 | Score a job once you save it on the feed, if yet unscored. | Score a job when you save it in the Feed, if it has no score yet. |
| Settings.jsx:327 | Extra requests queue — protects the DB pool. | Extra requests wait in a queue to limit database load. |
| Settings.jsx:335 | placeholders stay literal — replaced at runtime | keep placeholders like {job_description} as written; they are filled in when the prompt runs |
| Settings.jsx:348 | Label + prompt per voice, can be expanded. | One label and prompt per voice. Add more if you want. |
| Settings.jsx:357 | the handover bundle Applications exports for your LLM of choice | the prep pack that Applications builds for an AI chat |
| Settings.jsx:358 | The hardcoded ask appended to the handover. | The questions added at the end of the prep pack. |
| Settings.jsx:359 | Sections the handover carries. Ask is always included. | Sections included in the prep pack. The questions are always included. |
| Settings.jsx:392 | High-fit arrivals and the daily digest go to your chat. | New high-scoring jobs and the daily digest are sent to your chat. |
| Settings.jsx:290 | That did not work | Save failed. Try again. |
| Settings.jsx:703 | No key — the dashboard is open | No key set. Anyone who can reach this address can use the dashboard. |
| Settings.jsx:940,955 | Search ${n} live models, or paste any slug… / ${n} of ${m} match · or paste any slug and Add | Search ${n} models, or paste a model id… / ${n} of ${m} match · or paste a model id and press Add |
| Settings.jsx:972 | Remove — removal persists | Remove from the list (stays removed) |

## 10. Job Feed

| file:line | current | suggested |
|---|---|---|
| JobFeed.jsx:339 | Ignore "${name}" everywhere?\n\nThis hides ${n} jobs here and excludes the company from every future scrape. Undo it in Settings → global company exclude. | Ignore "${name}" everywhere? This hides ${n} jobs and skips the company in all future scrapes. You can undo this in Settings → Global exclude. |
| JobFeed.jsx:1098 | ${company} sends X-Frame-Options, so the live page cannot render here. Open it in a new tab, or install the Navigator extension to strip frame-blocking headers. | ${company} does not allow its page to be shown inside another site. Open it in a new tab, or install the Navigator extension, which removes that restriction. |
| JobFeed.jsx:773 | Jobs arrive from Searches and Companies — activate one, or widen the Status filter to see skipped and applied roles. | Jobs come from Searches and Companies. Activate one, or change the Status filter to include skipped and applied jobs. |
| JobFeed.jsx:1097 | This posting refuses to be framed | This page can't be shown here |
| JobFeed.jsx:1169 | Instant · no LLM cost · lands in Résumés | Instant · no LLM cost · saved under Résumés |
| JobFeed.jsx:1051 | No fit | Not scored |
| JobFeed.jsx:1040 | This report was quick-scored — rescore at full depth for the keyword and requirement breakdown. | This job was scored at Light depth. Score it at Full depth for the keyword and requirement breakdown. |
| JobFeed.jsx:1141 | Rewrites bullets against the report · LLM run | Rewrites bullets to match the posting · uses the LLM |
| JobFeed.jsx:1169 | Runs an LLM pass against résumé | Runs the LLM on the résumé |
| JobFeed.jsx:609 | ${verdict} · ${n} LCAs / ${verdict} · no LCA records | ${verdict} · ${n} H-1B filings / ${verdict} · no H-1B filings |
| JobFeed.jsx:1029 | Hard blockers | Disqualifying requirements |
| JobFeed.jsx:735 | ⇧ range · ${PICK_KEY} pick | Shift-click selects a range · ${PICK_KEY}-click selects one |
| JobFeed.jsx:587 | Done — "${title}" at ${company} / Failed — "${title}" at ${company} | Scored "${title}" at ${company} / Scoring failed for "${title}" at ${company} (use the verb of the run type) |
| JobFeed.jsx:895 | Copy résumé with tracers | Copy résumé with tracked links |
| JobFeed.jsx:1161,1203 | from /persona | from Persona |
| JobFeed.jsx:633 | The Feed | Jobs (see §0) |

## 11. Not changed on purpose

- Native `confirm`/`prompt` bodies are rewritten above only where flagged; whether they stay native is R2-A-01 (see the audit), not a copy question.
- `Application funnel` as a chart title stays: it is the standard name for that chart.
- Short labels already plain (`Save`, `Cancel`, `Run now`, …) are not listed.
