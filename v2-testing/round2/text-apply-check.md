# R4b — misalignment check before applying `text-suggestions.md`

Checked on 2026-09-05, against `frontend/src/v2/*.jsx` at HEAD 6abcdec. All 120 accepted
rows (§1 … §10, up to "Removed as settled") were located by wording; the line numbers in
the first column are stale throughout and were ignored. Three rows name two sites each
(ResumeSections/CoverLetterEditor stub title, CoverLetters/Applications server error,
JobFeed "from /persona"), so 120 rows map to 123 edit sites.

No row was found missing, in a different file than named, or in conflict with another row.
No suggestion reintroduces one of the twelve §0 vocabulary decisions. No suggestion drops a
placeholder or a JSX expression the code needs. Every issue below is mechanical and was
resolved without changing meaning, so the pass continued to Phase 2.

| row | issue | what I did |
|---|---|---|
| all 120 | line numbers stale (files have grown since R4b was written) | located every row by its **current** wording; matched exactly once each unless noted below |
| all rows with an apostrophe or a quote | the table renders `'` and `"` as ASCII; the code uses `’` `“ ”` wherever a single-quoted JS string requires it | kept the character the code already uses at that site (`’` inside single-quoted strings, `'` in template literals / JSX / double-quoted strings). Em dash, ellipsis, `·`, `›`, `→` taken verbatim from the suggested column |
| V2App:95, V2App:96 | the tail "Click → Stats · Run history." also ends a third tooltip (V2App.jsx:167, the failing-sources branch) that no row covers | applied the two named strings only; line 167 keeps its old tail — flagged as a residual inconsistency, not fixed |
| Resumes:153 | **current** is the flattened form of a template with plural and conditional interpolations | applied the one difference (" are under their jobs" → ", listed under their jobs"); `${sub.b}`, `cop${…}`, `${sub.a ? …}` untouched |
| ResumeSections:324 | suggestion drops the whole `pageHint && txt.length > 600 ? …` clause, which leaves the `pageHint` prop (passed by SectionEditor and Persona) unused | rendered `{txt.length} characters` only; left the `pageHint` prop plumbing in place (no identifier renamed or removed). Dead prop noted for a later cleanup |
| ResumeEditor:493 (×2) | two rows, one code site: `title={stage.done ? 'Pipeline complete' : 'The one next step'}` | mapped each row to its own branch |
| ResumeEditor:523 | **current** flattens JSX: the copy count is an interpolated fragment | replaced only the trailing literal "editing here changes future tailoring only" |
| ResumeEditor:813 (×2) | **current** flattens a template with a plural interpolation | replaced the literal tails; `${changes.length}` and `change${…}` kept |
| CoverLetters:254 | the fragment "live application" also appears in the resting count line (CoverLetters.jsx:266), which no row covers | applied to the search form only; the resting line still reads "live applications" — flagged, not fixed |
| Applications:111 / CoverLetters:151 | Applications' copy appends `${errSuffix(e)}` after the sentence | kept the suffix, appended after the new "Try again." text; CoverLetters has no suffix |
| Applications:136 | the suggestion reorders the two conditional tails (stale count before "showing") and renames both | rebuilt the concatenation in the suggested order; `total > apps.length` and `nStale` conditions unchanged |
| Stats:566 | the schedErr branch on the same line reuses the fragment "intervals and crons are in Settings" | applied to the long line only; the error branch keeps its wording — flagged, not fixed |
| Searches:575 | the sibling branch ("Full — every new result gets a score plus …") is covered by no row | applied the Light branch only — the two now differ in style; flagged, not fixed |
| Searches:785 | **current** says "${m} filtered" where the code reads "title-filtered"; the suggested column repeats "filtered" unchanged | treated the clause as unchanged and applied the one real difference, "raw" → "found" |
| Companies:240,241 | the row cites both ternary branches but quotes only the filtered one; the "Applies to all …" branch has no suggestion | applied the quoted branch only — flagged, not fixed |
| Companies:537 (filings), Companies:424 | **current** flattens templates whose "% approved" clause is conditional | rewrote around the conditional; both interpolations kept |
| Companies:805 | **current** says "keyword-filtered"; the code reads "title-filtered" (an earlier pass renamed it). The row also omits the two body-phrase clauses the code adds conditionally | mapped clause by clause — extracted → "${t} found" moved to the front, "title-filtered" → "removed by title filter", "validation-rejected" → "invalid", "removed by the global list" → "removed by the global exclude list"; the two body clauses keep their positions and wording |
| Settings:940,955 | one row, two sites (the typeahead placeholder and the match footer), paired "A / B" | mapped each half to its site |
| JobFeed:339 | **current** is the pre-ConfirmDialog `window.confirm` text (title `\n\n` body); the code is a ConfirmDialog with separate `title` and `body` | mapped sentence 1 → `title` (unchanged) and the rest → `body`; the `job${n === 1 ? '' : 's'}` plural kept |
| JobFeed:1098 | **current** flattens a ternary — the quoted tail is the non-cached branch | replaced the leading literal and the non-cached branch; the "cached snapshot is available" branch untouched |
| JobFeed:773 | **current** flattens JSX containing two `<a>` links | kept both anchors inside the new sentence |
| JobFeed:587 | the suggestion carries an instruction, "(use the verb of the run type)"; the toast serves both score and tailor runs (`meta.op`) | derived the verb per run type: Scored / Scoring failed for, and Tailored / Tailoring failed for — the same pattern the suggested column gives for scoring, matching the existing "Scoring failed for …" and "Tailor failed for …" toasts elsewhere in the file |

## Appendix — applied change list (`file:line | before | after`)

Line numbers are post-edit. Only the differing run of each line is shown; `git diff` is authoritative.

```
Applications.jsx:47 | the interview loop | terviewing
Applications.jsx:117 | answered ${e.response.status} | returned error ${e.response.status}. Try again
Applications.jsx:166 | interview · ${nOffer} offer${nOffer === 1 ? '' : 's'}${total > apps.length ? ` · showing the first ${apps.length}` : ' | terviewing · ${nOffer} offer${nOffer === 1 ? '' : 's
Applications.jsx:167 | aiting >7d | ith no reply for 7+ days
Applications.jsx:168 |  | + (total > apps.length ? ` · showing ${apps.length}` : '')
Applications.jsx:576 | pasteable block — the role, my résumé, the posting and what to ask for — for the AI of your choice | text block with the role, your résumé, the posting and the questions to ask, to paste into any AI chat
Applications.jsx:717 | closing ask | questions added at the end
Applications.jsx:799 | — jobs from the feed log themselves when you mark them applied | . Jobs marked Applied in the Feed are logged automatically
Applications.jsx:845 | The posting is cached on save | A copy of the posting is saved with the application
Companies.jsx:88 | a run first | last run
Companies.jsx:285 | in the current filter · jobs already found are kept | shown. Jobs already found are kept.
Companies.jsx:431 | /remove from filter · multi-select, remembered per browser | to or remove from the filter. Multiple allowed. Saved in this browser.
Companies.jsx:497 | on record${c.h1b_approval_rate ? `, ${c.h1b_approval_rate}% approved` : ''} — feeds the verdict on each job | ${c.h1b_approval_rate ? `, ${c.h1b_approval_rate}% approved` : ''}. Used for each job's H-1B verdict.
Companies.jsx:514 | H-1B slug | MyVisaJobs company id
Companies.jsx:619 | filings on record${company.h1b_approval_rate ? ` · ${company.h1b_approval_rate}% approved` : ''} — each job's H-1B verdict is based on these.` : 'No filings on record, so jobs here show H-1B Unknown. Blank auto-detects from the company | H-1B filings on record${company.h1b_approval_rate ? ` · ${company.h1b_approval_rate}% approved` : ''}. Each job's H-1B verdict is based on these.` : 'No H-1B filings on record, so jobs show H-1B Unknown. Leave blank to detect the company from its
Companies.jsx:681 | on the | in
Companies.jsx:707 | collapse in | are matched
Companies.jsx:765 | Stops paging after this many | Maximum number of result pages to read
Companies.jsx:808 | No known ATS — the page is loaded and read as HTML. If it lists nothing, set a wait-for selector in the company config | Unknown job board. The page is read as HTML. If no jobs are found, set a wait-for selector in the company settings
Companies.jsx:882 | — change them in the company config when a board needs it | . Change them in the company settings if needed
Companies.jsx:920 | kept} kept · ${Math.max(0, found - kept - bodyExcluded)} title-filtered | found + rejected} found · ${kept} kept · ${Math.max(0, found - kept - bodyExcluded)} removed by title filter
Companies.jsx:922 | validation-rejected · ${found + rejected} extracte | invali
Companies.jsx:923 |  | exclude
Companies.jsx:976 | ination debug | e-by-page details
CoverLetterEditor.jsx:342 | not recorded | unknown for this letter
CoverLetterEditor.jsx:433 | for the tracked link id (e.g. l, w, gh) — tracked links are short links that record when a recruiter opens them | used in the tracked link, e.g. l, w, gh
CoverLetterEditor.jsx:549 | — showing the last render | . Showing the previous version
CoverLetterEditor.jsx:575 | — switch to use different | . Switch to use a different set of
CoverLetters.jsx:143 | answered ${e.response.status} | returned error ${e.response.status}. Try again
CoverLetters.jsx:265 | live | open
JobFeed.jsx:493 | here and excludes the company from every future scrape. Undo it in Settings → global company | and skips the company in all future scrapes. You can undo this in Settings → Global
JobFeed.jsx:529 | /p | P
JobFeed.jsx:838 | ok ? 'Done' : 'Failed'} — | meta.op === 'tailor' ? (ok ? 'Tailored' : 'Tailoring failed for') : (ok ? 'Scored' : 'Scoring failed for')}
JobFeed.jsx:1012 | ⇧ range · {PICK_KEY} pick | Shift-click selects a range · {PICK_KEY}-click selects one
JobFeed.jsx:1060 | arrive from <a href="/v2/searches" onClick={(e) => { e.preventDefault(); navigate('/v2/searches') }}>Searches</a> and <a href="/v2/companies" onClick={(e) => { e.preventDefault(); navigate('/v2/companies') }}>Companies</a> — activate one, or widen the Status filter to see skipped and applied role | come from <a href="/v2/searches" onClick={(e) => { e.preventDefault(); navigate('/v2/searches') }}>Searches</a> and <a href="/v2/companies" onClick={(e) => { e.preventDefault(); navigate('/v2/companies') }}>Companies</a>. Activate one, or change the Status filter to include skipped and applied job
JobFeed.jsx:1463 | osting refuses to be framed | age can't be shown here
JobFeed.jsx:1464 | sends X-Frame-Options, so the live page cannot render here. {dCached ? 'You applied to this role, so a cached snapshot is available.' : 'Open it in a new tab, or install the Navigator extension to strip frame-blocking headers | does not allow its page to be shown inside another site. {dCached ? 'You applied to this role, so a cached snapshot is available.' : 'Open it in a new tab, or install the Navigator extension, which removes that restriction
JobFeed.jsx:1510 | against the report · LLM run | to match the posting · uses the LLM
JobFeed.jsx:1532 | /p | P
JobFeed.jsx:1541 | an LLM pass against | the LLM on the
LoginModal.jsx:93 | First run with no key configured? Leave the field blank and sign in — you’ll set one | If no API key is set yet, leave this blank and sign in. You can add a key later
Persona.jsx:68 | Prefer not to answer demographic questions — autofill picks “decline” | Decline demographic questions
Persona.jsx:382 | The AI uses this as the source pool for tailored résumés, as raw material for cover-letter anecdotes, and as the candidate profile when scoring jobs | Used for tailored résumés, cover letters and job scoring
Persona.jsx:398 | Personal info used to auto-fill application forms — contact details, work authorization, EEO answers, salary expectations and reusable screener answers. Not used by the AI for résumé generation | Details used to fill application forms: contact, work authorization, EEO answers, salary and reusable screener answers. Not used for résumés
ResumeEditor.jsx:589 | Pipeline complete' : 'The one n | All steps done' : 'N
ResumeEditor.jsx:624 | ing here changes future tailoring | s here affect new copies
ResumeEditor.jsx:771 | has no résumé row to copy — tailor from it instead | is not a résumé, so it can’t be copied. Use Tailor instead.
ResumeEditor.jsx:830 | — you review and decline | . You can decline any of them
ResumeEditor.jsx:861 | ny job description — the copy won't be linked to a feed job | job description. The copy will not be linked to a job in the Feed.
ResumeEditor.jsx:890 | were applied automatically. Decline any you don't want; the base text comes back | changes were applied automatically. Decline any you don't want to restore the base text
ResumeEditor.jsx:935 | — base text restored · the rest stay` : `All ${changes.length} change${changes.length === 1 ? '' : 's'} live · decline any to restore the | and restored to the base text · the other changes are kept` : `All ${changes.length} change${changes.length === 1 ? '' : 's'} applied · decline one to restore its
ResumeSections.jsx:132 | skipped in the PDF — nothing prints until you add one | left out of the PDF
ResumeSections.jsx:213 | for the tracked link id (e.g. l, w, gh) — tracked links are short links that record when a recruiter opens them | used in the tracked link, e.g. l, w, gh
ResumeSections.jsx:291 | — keep on review | . Kept unless you decline it in Review.
ResumeSections.jsx:324 | {pageHint && txt.length > 600 ? ' · long summaries can push to a second page' : ''} | 
Resumes.jsx:152 | are | , listed
Resumes.jsx:170 | — the shelf request failed | . Retry, or check that the backend is running
Resumes.jsx:199 | — copies appear here when their application is rejected or goes stal | . A copy is archived when its application is rejected or has had no activity for a long tim
Resumes.jsx:353 | — is it a text PDF? | . The PDF must contain selectable text, not a scanned image.
Searches.jsx:75 | — cheap enough to leave on | . Low cost.
Searches.jsx:83 | Configure filters on levels.fyi, then paste the URL here — location, job family, salary and recency are all encoded in it | Set your filters on levels.fyi and paste the URL here. The URL contains location, job family, salary and date filters
Searches.jsx:84 | Personalized AI recommendations from your Jobright.ai account. A search term switches it to search mode; credentials are in Setting | Recommendations from your Jobright.ai account. Enter a search term to search instead. Credentials are in Settings › Account
Searches.jsx:85 | arrive via the “Save to Job Feed” button on any website. Set auto-score depth and the filters below — they apply as each job | come from the “Save to Job Feed” button on any website. The filters and auto-score depth below apply to each job as it
Searches.jsx:86 | import via passive capture on linkedin.com/jobs/collections/* pages. The filters below auto-filter during | are captured while you browse linkedin.com/jobs/collections pages. The filters below are applied on
Searches.jsx:255 | NDed with the URL — must appear in the posting text | dded to the URL filters. Must appear in the posting text.
Searches.jsx:258 | , posted_within_days… pass straight through | and posting age are taken from the URL as is
Searches.jsx:588 | on the next scheduled run once created | at the next scheduled scrape after you create it
Searches.jsx:607 | — results appear in the Job Feed as they arrive… | . Results appear in the Job Feed as they are found.
Searches.jsx:640 | — every new result gets a score only; open a job to generate its report | : each new job gets a score. Open the job to generate a full report.
Searches.jsx:650 | — leaves the schedule, config is kept | . Removed from the schedule, settings kept.
Searches.jsx:669 | — shows results and per-job filter reasons, saves nothing | . Shows results and why each job was kept or filtered. Saves nothing.
Searches.jsx:721 | start pulling roles in | add jobs
Searches.jsx:895 | raw | found
Settings.jsx:282 | That did not work | Save failed. Try again.
Settings.jsx:309 | individual prompt can be run against different model, | prompt can use its own model
Settings.jsx:312 | (Anthropic), Claude Code, OpenAI, Ollama (local), OpenRouter. Picking a provider filters the model dropdown to that provider's models — seeded ones plus any you added under Custom models. OpenRouter reaches every vendor with one key but get | , Claude Code, OpenAI, Ollama (local), OpenRouter. The model list shows that provider's models, including any you added under Model catalog. OpenRouter covers every vendor with one key but ha
Settings.jsx:313 | Key for the Primary provider API model | API key for the primary provider
Settings.jsx:316 | Fires only when the scoring call errors or hits a rate limit; one retry, then the job is left unscored for the next scrape run. Pick a cheap, reliable model from a different provider than the Primary so one outage can’t take both down | Used only when the scoring call fails or is rate-limited. One retry, then the job stays unscored until the next run. Choose a cheap model from a different provider than the primary
Settings.jsx:322 | For models newer than the seeded list. The add search hits the provider’s live catalog for OpenRouter, OpenAI and Claude; Ollama has no catalog — enter the local model name. Removals persist | Add models that are not in the built-in list. Search uses the provider’s catalog for OpenRouter, OpenAI and Claude. For Ollama, type the local model name. Removed models stay removed
Settings.jsx:326 | queue — protects the DB pool | wait in a queue to limit database load
Settings.jsx:329 | returns scores + a one-liner (cheap, for high-volume searches). Full adds keyword coverage, requirement mapping and a written report. Companies and Searches can each override this per config | : score and one line, low cost. Full: adds keyword coverage, requirement mapping and a written report. Each company and search can override this
Settings.jsx:330 | once you save it on the feed, if yet unscored | when you save it in the Feed, if it has no score yet
Settings.jsx:332 | Rubric + résumés + schema sent as a cached block — ~10× cheaper input tokens on repeat call | Sends the rubric, résumés and schema as a cached block. Repeat calls cost about 10× les
Settings.jsx:333 | ctive when the effective provider is claude_api — no effect with Claude Code, Ollama or OpenRouter. If scoring output ever looks stale after a rubric edit, disable this as a rollback lever, run once, re-enable | pplies to the Claude API provider. If scores look outdated after you edit the rubric, turn this off, run once, then turn it back on
Settings.jsx:334 | placeholders stay literal — replaced at runtime | keep placeholders like {job_description} as written; they are filled in when the prompt runs
Settings.jsx:339 | benefi | the job description makes relevan
Settings.jsx:340 | selection from Persona’s richer pool, | uses the Persona résumé content;
Settings.jsx:342 | Rescores tailored resume when the tailor | Scores a tailored résumé as soon as tailoring
Settings.jsx:347 | Label + prompt per voice, can be expanded | One label and prompt per voice. Add more if you want
Settings.jsx:356 | Applications exports for your LLM of choice | that Applications builds for an AI chat
Settings.jsx:357 | hardcoded ask appended to | questions added at the end of
Settings.jsx:358 | the prep handover carries. Ask is | included in the prep handover. The questions are
Settings.jsx:367 | Additional known sender domains check | Extra sender domains treated as job-related email
Settings.jsx:368 | Exclusion of newsletters and job-alert spam | Ignore newsletters and job-alert email
Settings.jsx:375 | s from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in Stats — nothing is deleted | ed from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in Stats
Settings.jsx:383 | Exclusion of postings whose description matches any phrase from this list | Skip postings whose description contains any of these phrases
Settings.jsx:384 | Exclusion of the job title matche | Skip jobs whose title matches any of these word
Settings.jsx:385 | Exclusion of exact company names | Skip jobs from these companies (exact name).
Settings.jsx:391 | High-fit arrivals and the daily digest go | New high-scoring jobs and the daily digest are sent
Settings.jsx:395 | — alerts and the digest work without a webhook. Validates every Telegram → backend call | . Checks every call from Telegram to the backend. Alerts and the digest work without it
Settings.jsx:398 | e secret as X-Telegram-Bot-Api-Secret-Token on every webhook call; mismatched headers return 401. Rotating shows the new secret once — copy it immediately, then re-register the webhook | is secret with every webhook call. Calls with the wrong secret are rejected. After rotating, the new secret is shown once: copy it, then register the webhook again
Settings.jsx:417 | per document link. When a recruiter opens one, the hit is recorded in Stats against | for every document link. When a recruiter opens one, it is recorded in Stats for
Settings.jsx:419 | needs to support selected | must support the selected link
Settings.jsx:435 | cookie. LinkedIn gates the login behind an emailed PIN | session. LinkedIn asks for an emailed PIN at login
Settings.jsx:437 | Capture happens while the extension browses LinkedIn collections. Doing that on a throwaway account means rate limits, CAPTCHAs or bans hit the mock identity — never | The extension captures jobs while you browse LinkedIn collections. Use a separate account so rate limits, CAPTCHAs or bans affect it and not
Settings.jsx:440 | escape hatches — most days none of this gets touched | rarely needed settings
Settings.jsx:792 | — the dashboard is open | set. Anyone who can reach this address can use the dashboard.
Settings.jsx:1049 | live models, or paste any slug | models, or paste a model id
Settings.jsx:1070 | ny slug and | model id and press
Settings.jsx:1089 | — removal persists | from the list (stays removed)
Stats.jsx:469 | Couldn’t reach the backend for some of these numbers — tiles show “—” and charts are marked unavailable until it answer | Some numbers could not be loaded. They show “—” until the backend respond
Stats.jsx:482 | Everything ever scraped or captured, minus | All jobs ever found, excluding ones removed by
Stats.jsx:483 | last | previous period
Stats.jsx:485 | in play`, 'In play | open`, 'Open
Stats.jsx:540 | recorded for these — counted by current status, so anything that passed through this stage and moved on is missing | for these applications. They are counted by current status only.
Stats.jsx:551 | Rows count applications that ever reached that stage; snapshot rows count current status | Stage rows count every application that reached the stage. Snapshot rows count current status only.
Stats.jsx:552 | very row counts applications that ever reached that stage; bars are relative to Applied | ach row counts applications that reached that stage. Bar length is relative to Applied.
Stats.jsx:609 | es come from a static table; OpenRouter uses live catalog pricing refreshed at most every 12h; Claude Code and Ollama count as $0. Cost is computed per call at log time, so past rows keep the price in effect then | ing info comes from a fixed table, OpenRouter from its catalog (updated every 12 h), Claude Code and Ollama counted as $0. Each call is priced when it is logged
Stats.jsx:632 | Prompt-cache hit ratio | Share of calls that reused a cached prompt
Stats.jsx:646 | window | period
Stats.jsx:656 | s in ${TZ_SHORT}, schedules as configured (UTC) · intervals and crons are | shown in ${TZ_SHORT}, schedule set in UTC · edit intervals
Stats.jsx:711 | thing the pipeline did | run and change
V2App.jsx:169 | No company or search is failing, but the last scrape run failed · ${lastSweep}. Click → Stats · | All companies and searches are healthy, but the last scrape run failed ${lastSweep}. Click to open
V2App.jsx:170 | → Stats · | to open
WelcomeModal.jsx:44 | and your search runs itself | to set up automatic searching
```
