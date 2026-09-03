# Round 3 smoke test

Read-only pass, no data mutations, no LLM calls, no rebuilds, no restarts. Repo v2-redesign branch, HEAD 69d36b1 (round-2 fixes landed).
Playwright inside backend container against http://caddy. Themes light/dark, viewports 1440x900 and 1024x700.

Legend: check rows are per column light-1440 / dark-1440 / light-1024 / dark-1024. X-Frame-Options iframe console noise ignored per instructions. Primary controls are auto-detected (main-content clickable elements near the top of the screen, up to 6, deduped by label) rather than a hand-picked list per screen. Methodology matches round 2 (`v2-testing/round2/smoke.md`) plus this round's additions: a modal/menu open+close inventory per v2 screen, a Toast Lab pass, and a Feed-keyboard pass with `PATCH /api/jobs/*` intercepted+aborted.

## V2 Feed
`/v2/feed`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | The Feed | The Feed | The Feed | The Feed |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search titles…, Open tailored résumé, Open ↗, More actions, Source ▾] | ✔ [Search titles…, Open tailored résumé, Open ↗, More actions, Source ▾] | ✔ [Search titles…, Open ↗, More actions, Source ▾, ▾] | ✔ [Search titles…, Open ↗, More actions, Source ▾, ▾] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '5', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '5', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/jobs` -> 500): ✔ nonblank=248 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: A[Open in new tab ↗] > BODY[JobNavigator
JN
FIND
Jobs
9
Se] > A[Jobs
9]

### Feed deep links
- `?job=f9f55248-fe40-4a40-973d-0383e8308459` opens detail panel with job title present: ✔ (looked for 'Sales Enablement Lead')
- `?company=Anthropic` filter chip shows 'Company' active: ✔; page text includes company name: ✔
- `?job=` with a bad id: toast 'no longer exists' seen: ✔

## V2 Searches
`/v2/searches`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Searches | Searches | Searches | Searches |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Resume the schedule, More actions, Pause — leaves the schedule,, + New search, JobSpy JOBSPY “product manag] | ✔ [Resume the schedule, More actions, Pause — leaves the schedule,, + New search, JobSpy JOBSPY “product manag] | ✔ [Resume the schedule, More actions, Pause — leaves the schedule,, + New search, JobSpy JOBSPY “product manag] | ✔ [Resume the schedule, More actions, Pause — leaves the schedule,, + New search, JobSpy JOBSPY “product manag] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/searches` -> 500): ✔ nonblank=149 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: A[Jobs
9] > A[Searches
6] > A[Companies
128]

## V2 Companies
`/v2/companies`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Companies | Companies | Companies | Companies |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 127 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 127 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 127 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 127 companies, Click to pause scraping, Scrape this company now] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1306 | ✖ sw=1024 iw=1024 right=1306 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/companies` -> 500): ✔ nonblank=308 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: DIV[COMPANY
TIER
HEALTH
RÉSUMÉS
AT] > BODY[JobNavigator
JN
FIND
Jobs
9
Se] > A[Jobs
9]

## V2 Applications
`/v2/applications`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Applications | Applications | Applications | Applications |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search title or company…, Snapshot of the posting from, Open the live posting, More actions, + Log application] | ✔ [Search title or company…, Snapshot of the posting from, Open the live posting, More actions, + Log application] | ✔ [Search title or company…, Snapshot of the posting from, Open the live posting, More actions, + Log application] | ✔ [Search title or company…, Snapshot of the posting from, Open the live posting, More actions, + Log application] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/applications` -> 500): ✔ nonblank=317 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: TEXTAREA[Notes…] > BODY[JobNavigator
JN
FIND
Jobs
22
S] > A[Jobs
22]

## V2 Résumés (shelf)
`/v2/resumes`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Résumés | Résumés | Résumés | Résumés |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes` -> 500): ✔ nonblank=135 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
22] > A[Searches
6] > A[Companies
127]

### Résumés bad-id deep link
- bad id navigates to shelf: ✔ (path=/v2/resumes); error toast/state seen: ✔

## V2 Résumé Editor (base: PM)
`/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | PM | PM | PM | PM |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a` -> 500): ✔ nonblank=1020 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: INPUT[] > SPAN[Move up] > SPAN[Move down]
- base resume id=22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a

## V2 Résumé Editor (tailored copy)
`/v2/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager | PM → Meta — Product Manager |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e` -> 500): ✔ nonblank=1020 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: INPUT[] > SPAN[Move up] > SPAN[Move down]
- tailored resume id=d28bbd9e-6419-445e-8259-2ac0e002aa7e

## V2 Cover Letters (shelf)
`/v2/cover-letters`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Cover Letters | Cover Letters | Cover Letters | Cover Letters |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/cover-letters` -> 500): ✔ nonblank=400 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
22] > A[Searches
7] > A[Companies
127]

### Cover Letters bad-id deep link
- bad id: landed path=/v2/cover-letters/00000000-0000-0000-0000-000000000000; main nonblank length=53

## V2 Cover Letter Editor
`/v2/cover-letters/ce44e1d4-2763-4088-99a4-2f71f8e68115`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Scale — Senior AI Product Manager, Finance Agents | Scale — Senior AI Product Manager, Finance Agents | Scale — Senior AI Product Manager, Finance Agents | Scale — Senior AI Product Manager, Finance Agents |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/cover-letters/ce44e1d4-2763-4088-99a4-2f71f8e68115` -> 500): ✔ nonblank=72 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: INPUT[] > TEXTAREA[] > TEXTAREA[]
- cover letter id=ce44e1d4-2763-4088-99a4-2f71f8e68115

## V2 Persona
`/v2/persona`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Persona | Persona | Persona | Persona |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [› Header, › Summary, ⌄ Contact / basics complete, ›, Header] | ✔ [› Header, › Summary, ⌄ Contact / basics complete, ›, Header] | ✔ [› Header, › Summary, ⌄ Contact / basics complete, ›, Header] | ✔ [› Header, › Summary, ⌄ Contact / basics complete, ›, Header] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/persona` -> 500): ✔ nonblank=88 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: INPUT[] > SPAN[Move up] > SPAN[Move down]

## V2 Stats
`/v2/stats`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Stats | Stats | Stats | Stats |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Reload every figure on this , ↻] | ✔ [Reload every figure on this , ↻] | ✔ [Reload every figure on this , ↻] | ✔ [Reload every figure on this , ↻] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/stats` -> 500): ✔ nonblank=3927 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
22] > A[Searches
7] > A[Companies
128]

### Stats #runs deep link
- light-1440: `#runs` card found, top=92px, in view: ✔
- light-1024: `#runs` card found, top=92px, in view: ✔
- dark-1440: `#runs` card found, top=92px, in view: ✔
- dark-1024: `#runs` card found, top=92px, in view: ✔

## V2 Settings
`/v2/settings`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Settings | Settings | Settings | Settings |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search settings…, More detail, Primary provider · model — p, Primary provider · model — m, Jump to Models] | ✔ [Search settings…, More detail, Primary provider · model — p, Primary provider · model — m, Jump to Models] | ✔ [Search settings…, More detail, Primary provider · model — p, Primary provider · model — m, Jump to Models] | ✔ [Search settings…, More detail, Primary provider · model — p, Primary provider · model — m, Jump to Models] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '128', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '128', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '128', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '22', '/v2/searches': '7', '/v2/companies': '128', '/v2/applications': '377', '/v2/resumes': '6', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/settings` -> 500): ✔ nonblank=54 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: DIV[Primary provider · model — pro] > DIV[Primary provider · model — mod] > SPAN[Scoring — override the Primary]

## V2 Toast Lab
`/v2/toasts`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Toast lab | Toast lab | Toast lab | Toast lab |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [◐ Light, paper card + spinner · 2.5s, same, plural form, green tint + ✓ roundel · 2.5, success with an action] | ✔ [◐ Dark, paper card + spinner · 2.5s, same, plural form, green tint + ✓ roundel · 2.5, success with an action] | ✔ [◐ Light, paper card + spinner · 2.5s, same, plural form, green tint + ✓ roundel · 2.5, success with an action] | ✔ [◐ Dark, paper card + spinner · 2.5s, same, plural form, green tint + ✓ roundel · 2.5, success with an action] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
## V1 Job Feed
`/`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Job Feed | Job Feed | Job Feed | Job Feed |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Keyboard shortcuts, Reset] | ✔ [1 company need attention. Re, Dismiss, Persona, Keyboard shortcuts, Reset] | ✔ [Dismiss, Persona, Keyboard shortcuts, Reset, BUTTON] | ✔ [Dismiss, Persona, Keyboard shortcuts, Reset, BUTTON] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/jobs` -> 500): ✔ nonblank=473 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Application Board
`/applications`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Application Board | Application Board | Application Board | Application Board |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Application Board, Adobe] | ✔ [1 company need attention. Re, Dismiss, Persona, Application Board, Adobe] | ✔ [Dismiss, Persona, Application Board, 1 company need attention. Re, 1 company need attention.] | ✔ [Dismiss, Persona, Application Board, 1 company need attention. Re, 1 company need attention.] |  |
| no h-overflow | ✖ sw=1440 iw=1440 right=1820 | ✖ sw=1440 iw=1440 right=1820 | ✖ sw=1024 iw=1024 right=1820 | ✖ sw=1024 iw=1024 right=1820 |  |

- **API failure** (stub `/api/applications` -> 500): ✔ nonblank=507 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Company Manager
`/companies`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Company Manager | Company Manager | Company Manager | Company Manager |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Company Manager, Activate All] | ✔ [1 company need attention. Re, Dismiss, Persona, Company Manager, Activate All] | ✔ [Dismiss, Persona, Company Manager, 1 company need attention. Re, 1 company need attention.] | ✔ [Dismiss, Persona, Company Manager, 1 company need attention. Re, 1 company need attention.] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/companies` -> 500): ✔ nonblank=572 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Search Manager
`/searches`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Search Manager | Search Manager | Search Manager | Search Manager |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Search Manager, New Search] | ✔ [1 company need attention. Re, Dismiss, Persona, Search Manager, New Search] | ✔ [Dismiss, Persona, Search Manager, New Search, 1 company need attention. Re] | ✔ [Dismiss, Persona, Search Manager, New Search, 1 company need attention. Re] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/searches` -> 500): ✔ nonblank=511 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Resume Builder
`/resumes`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, [tailored] ZZB Base (tailore, Delete resume] | ✔ [1 company need attention. Re, Dismiss, Persona, [tailored] ZZB Base (tailore, Delete resume] | ✔ [Dismiss, Persona, [tailored] ZZB Base (tailore, Delete resume, Download PDF] | ✔ [Dismiss, Persona, [tailored] ZZB Base (tailore, Delete resume, Download PDF] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/resumes` -> 500): ✔ nonblank=502 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Cover Letter Builder
`/cover-letters`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan | (none) 💼
JobNavigator
Jobs
Applications
Compan |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Scale — Senior AI Product Ma, Generate New] | ✔ [1 company need attention. Re, Dismiss, Persona, Scale — Senior AI Product Ma, Generate New] | ✔ [Dismiss, Persona, Scale — Senior AI Product Ma, Download PDF, 1 company need attention. Re] | ✔ [Dismiss, Persona, Scale — Senior AI Product Ma, Download PDF, 1 company need attention. Re] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/cover-letters` -> 500): ✔ nonblank=1504 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Persona
`/persona`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Persona | Persona | Persona | Persona |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, 1 company need attention.] | ✔ [1 company need attention. Re, Dismiss, Persona, 1 company need attention.] | ✔ [Dismiss, Persona, 1 company need attention. Re, 1 company need attention.] | ✔ [Dismiss, Persona, 1 company need attention. Re, 1 company need attention.] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1050 | ✖ sw=1024 iw=1024 right=1050 |  |

- **API failure** (stub `/api/persona` -> 500): ✔ nonblank=484 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Stats
`/stats`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Statistics & Activity | Statistics & Activity | Statistics & Activity | Statistics & Activity |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, Refresh, 1 company need attention.] | ✔ [1 company need attention. Re, Dismiss, Persona, Refresh, 1 company need attention.] | ✔ [Dismiss, Persona, Refresh, 1 company need attention. Re, 1 company need attention.] | ✔ [Dismiss, Persona, Refresh, 1 company need attention. Re, 1 company need attention.] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1397 | ✖ sw=1024 iw=1024 right=1397 |  |

- **API failure** (stub `/api/stats` -> 500): ✔ nonblank=7935 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

## V1 Settings
`/settings`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Settings | Settings | Settings | Settings |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, General, AI] | ✔ [1 company need attention. Re, Dismiss, Persona, General, AI] | ✔ [Dismiss, Persona, 1 company need attention. Re, 1 company need attention.] | ✔ [Dismiss, Persona, 1 company need attention. Re, 1 company need attention.] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |

- **API failure** (stub `/api/settings` -> 500): ✔ nonblank=1625 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]


### V2 Feed — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Source filter menu | ✔ | ✔ | ✔ |  |
| Sort menu | ✔ | ✔ | ✔ |  |
| Keyboard shortcuts modal | ✔ | ✔ | ✔ |  |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Tailor/Create-copy picker modal (from detail head) | ✔ | ✔ | ✔ |  |

### V2 Searches — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + New search inline panel | ✔ | ✔ | — | inline panel, no scrim to click |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Test (dry-run) modal — request stubbed | ✔ | ✔ | ✔ |  |


### V2 Companies — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + Add company modal | ✔ | ✔ | ✔ |  |
| Row click -> edit config drawer | ✔ | ✔ | ✖ |  |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Sort menu | ✔ | ✔ | ✔ |  |
| Test (dry-run) modal — request stubbed | ✔ | ✔ | ✔ |  |


### V2 Applications — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + Log application modal | ✔ | ✔ | ✔ |  |
| Row · more actions menu | ✔ | ✔ | ✔ |  |
| Prep pack modal (real GET, no LLM) | ✔ | ✔ | ✔ |  |


### V2 Résumés (shelf) — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| + New résumé modal | ✔ | ✔ | ✔ |  |


### V2 Résumé Editor (base) — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Tailor for a job… modal (standalone button) | ✔ | ✔ | ✔ |  |
| ⋯ head menu (base) | ✔ | ✖ | ✔ |  |


### V2 Résumé Editor (tailored copy) — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| ⋯ head menu (tailored copy) | ✔ | ✖ | ✔ |  |
| Re-tailor modal (via ⋯ menu > Re-tailor…) | ✔ | ✔ | ✔ |  |
| Review changes modal (via ⋯ menu > Review changes) | ✔ | ✔ | ✔ |  |


### V2 Cover Letters (shelf) — modal/menu inventory

No modal/drawer/menu trigger on this screen — "Generate new" is an always-open inline panel (`CoverLetters.jsx`), not an overlay; nothing to open/close.

### V2 Cover Letter Editor — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Regenerate letter modal | ✔ | ✔ | ✔ |  |
| ⋯ head menu | ✔ | ✔ | ✔ |  |

### V2 Persona — modal/menu inventory

No modal/drawer/menu trigger found — every section is an inline accordion (`Persona.jsx`), no overlay controls.

### V2 Stats — modal/menu inventory

No modal/drawer/menu trigger found — the screen is read-only charts/tables plus a ↻ reload button; no overlay controls.

### V2 Settings — modal/menu inventory

| trigger | opened | closed (Escape) | closed (scrim click) | note |
|---|---|---|---|---|
| Settings Edit modal (first row) | ✔ | ✔ | ✔ |  |
| Model catalog modal | ✔ | ✖ | ✔ |  |

### V2 Toast Lab — toast-kind pass

(presence checked against the fixed toast-stack container only, zIndex 80 — not the sample buttons' own always-visible labels)

| kind | message (needle) | present @1s | present @6s | expected @6s | note |
|---|---|---|---|---|---|
| progress | Tailoring for Senior SWE at Plaid | ✔ | ✔ (gone) | gone | auto-dismissed as expected |
| progress | Scoring 14 jobs | ✔ | ✔ (gone) | gone | auto-dismissed as expected |
| success | Tailored for Senior SWE at Plaid | ✔ | ✔ (gone) | gone | auto-dismissed as expected |
| success | Copy created for Datadog. | ✔ | ✔ (gone) | gone | auto-dismissed as expected |
| error | Scoring failed for Backend Engineer at Datadog | ✔ | ✔ (shown) | shown | persisted as expected (error) |
| error | Tailoring failed to start. | ✔ | ✔ (shown) | shown | persisted as expected (error) |
| undo | Skipped | ✔ | ✔ (gone) | gone | auto-dismissed as expected |
| undo | Marked applied | ✔ | ✔ (gone) | gone | auto-dismissed as expected |

### Feed keyboard pass (`PATCH /api/jobs/*` intercepted + aborted; `?job=` deep-linked so `o` has a URL)

| key | observation |
|---|---|
| initial | {'selected_row': None, 'detail_heading': 'The Feed'} |
| j | {'selected_row': '0', 'moved_from_initial': True, 'detail_heading': 'The Feed', 'detail_changed': False} |
| k | {'selected_row': '0', 'back_to_initial': False, 'detail_heading': 'The Feed'} |
| Enter | {'selected_row': '0', 'changed_selection': False, 'detail_heading': 'The Feed', 'note': "v2 Feed's keydown switch has no 'Enter' case (JobFeed.jsx:494-506) — detail is already open via j/k selection, so Enter is expected to no-op here"} |
| Escape (after opening row menu) | {'result': 'opened=True closed_by_escape=True'} |
| o | {'new_page_or_tab': True, 'new_page_url': 'https://www.metacareers.com/profile/job_details/1238249364564427/'} |
| s | {'aborted_patch_count_so_far': 1, 'error_toast_seen': True} |
| x | {'aborted_patch_count_total': 2, 'error_toast_seen': True} |

- total intercepted PATCH attempts aborted: 2 (no real write reached the backend)
- reading the sequence: `initial` shows `selected_row: None` because the `?job=` deep link pins the detail panel without selecting a list row (`sel=-1` — JobFeed.jsx comment: "a ?job= permalink owns the panel until the user picks from the list"). Pressing `j` releases that pin and selects row 0 of the currently-loaded (default-sorted) list — confirmed by `selected_row` flipping `None → '0'`, which is the row-background check reading `JobFeed.jsx:823`'s `i === sel` styling directly (not text-matching, which the first draft of this script got wrong — the always-visible page `<h1>The Feed</h1>` was being read as the "detail heading" instead of the job-specific panel, so `detail_heading` in this table is not a reliable signal and should be ignored; `selected_row` is the trustworthy field). `k` staying at `'0'` is correct (`Math.max(idx-1,0)` clamps at the top). Because `j` already released the pin, `o`'s target is whatever job ended up at row 0 (a Meta posting), not the original deep-linked Anthropic job — expected chained behavior, not a bug. `s` and `x` both show the optimistic-update-then-revert pattern (`patchLocal` applies instantly, the aborted PATCH's `catch` fires `pushToast({kind:'error', msg:"Couldn't update ..."})` and `fetchJobs()`) exactly as coded in `JobFeed.jsx:319-326` — confirmed working with zero real writes reaching the backend.

## Methodology notes

- Matches round 2's methodology notes (`v2-testing/round2/smoke.md`) for primary-control auto-detection, the generic Escape probe, and the h-overflow page-vs-contained-scroller distinction — not repeated here.
- **Modal/menu inventory** (new this round): each trigger was probed on its own fresh browser context (`common3.fresh_probe` / `fresh_text_probe`) rather than reusing one page across a screen's triggers — round 1 of this pass reused pages and a mis-detected still-open Companies edit drawer silently blocked every later click on that screen (timeouts on "More actions"/"Sort"), which cost a rerun. "Opened" is measured by counting `position:fixed` or `position:absolute` elements with `zIndex` in `[25,80)` before/after the click (this codebase inlines all its overlay styling — Drop-menus and per-row menus use `position:absolute` anchored to the trigger at `zIndex 40-45`, modals use `position:fixed; inset:0` at `zIndex 60-70`); a handful of triggers reach their modal through a menu item instead of directly (Résumé Editor's Re-tailor/Review-changes, both behind the "⋯" menu) — those are verified by a distinctive heading string appearing/disappearing instead, since the menu-close-then-modal-open transition happens in one React render and z-index counting across it is unreliable. One trigger (Searches' "+ New search") is a genuinely inline expanding card with no `position`/`z-index` at all (no scrim) — verified by text only, "closed (scrim click)" is marked "—" for it.
- **Toast Lab**: the sample-button row on `/v2/toasts` permanently displays a truncated copy of each toast's own message as the button's own label (`SAMPLES.map` → `{msg.slice(0,34)}…`), so a whole-`document.body` text search always "finds" the message whether or not a toast is showing — the first run of this check produced false positives across every kind. The corrected check scopes to the one `position:fixed; zIndex:80` container (`Toast.jsx`'s `ToastStack`) and confirms the taxonomy exactly as documented in `Toast.jsx`'s header comment: progress/success 4s, undo 5s, error persists.
- **Companies "Row click → edit config drawer"**: opened/closed-by-Escape both measured true, but "closed by scrim click" is false — the drawer (`Companies.jsx` `Drawer`, `position:absolute; right:0`, no full-viewport backdrop) does not close on an outside click, only on Escape or its own close controls. Not a probe artifact — confirmed by design (no scrim element exists in the DOM for it), logged as R3-S-02.

## Issues

### R3-S-01 · P3 · Companies row overflows at 1024px — unresolved, same as R2-S-01
**Where** `frontend/src/v2/Companies.jsx`, `/v2/companies`, 1024×700 (both themes)
**Repro** Load `/v2/companies` at 1024×700; measure `document.documentElement.scrollWidth` (1024, page itself doesn't scroll) vs the worst element's `getBoundingClientRect().right` (1306 this run, was 1335 in round 2 — value moved with row content but the defect shape is identical).
**Actual** Confirmed again this round: `docScrollsPage=False`; the offending element is a `SPAN` inside a `.v2-scroll` ancestor with `overflow-x:auto` (chain: `SPAN → DIV → DIV.v2-scroll(auto) → DIV.v2-scroll(hidden) → MAIN(hidden) → DIV.jn-v2(hidden)`) — same shape as R2-S-01's "row action icon sits past the viewport edge inside a horizontally-scrollable container."
**Expected** R2-S-01 was left as "needs decision" in round 2 (is the row deliberately horizontally-scrollable at ≤1024px, matching the Applications kanban pattern, or should content stay in view without scrolling). It was on the R3-0 fix-verification list; the behavior is unchanged, so either no decision was made yet or the decision was "leave as-is."
**Status** needs decision (carried over from R2-S-01, unresolved)

### R3-S-02 · P3 · Companies edit-config drawer has no backdrop — outside clicks don't close it
**Where** `frontend/src/v2/Companies.jsx` `Drawer` component (`position:absolute; right:0; top:0; bottom:0; width:720`, no scrim sibling), `/v2/companies`
**Repro** Click a company row to open its edit drawer, then click elsewhere on the page (outside the drawer panel).
**Actual** Drawer stays open. Escape closes it (`Companies.jsx:214`'s `onKey` handler calls `closeDrawer()`), but there is no click-outside/backdrop element in the DOM for it, unlike the "+ Add company" modal and the row/sort menus, which all close on an outside click.
**Expected** Unclear whether a drawer (as opposed to a centered modal) is meant to stay open on background interaction by design — some design systems deliberately keep drawers non-modal so the list stays usable underneath — or whether it should behave like every other overlay on this screen and close on outside click.
**Status** needs decision: keep the drawer non-modal (no backdrop, Escape-only close) or add a click-outside close for consistency with the rest of the screen

### R3-S-03 · P3 · Résumé Editor "⋯" head menu does not close on Escape
**Where** `frontend/src/v2/ResumeEditor.jsx:517-521` (base) and `:545-549` (tailored copy) — the `headMenu` dropdown, only closed via its own `onClick={() => setHeadMenu(false)}` backdrop `div`
**Repro** Open a résumé (base or tailored copy), click "⋯"/"More", press Escape.
**Actual** Menu stays open (confirmed both on the base résumé and the tailored copy). Clicking the invisible backdrop does close it. The three modals reachable from this same menu (Tailor, Re-tailor, Review changes) all call `useEscape(onClose)` (commented `// RES-15`), so Escape-to-close is clearly the established pattern elsewhere in this file — the head menu itself appears to have been missed.
**Expected** Escape closes the menu, consistent with `useEscape` used on every modal in the same file and with the Feed/Companies/Searches/Applications row menus (all close on Escape via their screens' shared keydown handlers).
**Proposed fix** Add an `Escape` case to `ResumeEditor.jsx`'s existing keydown surface (or a small `useEscape(() => setHeadMenu(false))` guarded by `headMenu`), mirroring `RES-15`.
**Status** needs decision: fix (looks like an omission, not a deliberate choice) or confirm intentional

### R3-S-04 · P4 · Settings "Model catalog" modal does not close on Escape
**Where** `frontend/src/v2/Settings.jsx` `ModelsModal` (~line 870) — only `EditModal` (~line 789) has the `closeRef`/`onKey` Escape handler (~line 838); `ModelsModal` has no equivalent, only its `onClick={onClose}` backdrop
**Repro** Settings → any row with a "Manage…" action → the Model catalog modal opens → press Escape.
**Actual** Modal stays open; clicking the backdrop does close it.
**Expected** Escape closes it, consistent with `EditModal` in the same file.
**Proposed fix** Reuse the same `document.addEventListener('keydown', ...)` pattern `EditModal` already has, scoped to `ModelsModal`.
**Status** needs decision: fix (small, contained) or confirm intentional

## Fixed since round 2 (verified this round, no action needed)
- **R2-S-02** (Résumé Editor ~3px overflow at 1024px) — now clean: `sw=1024 iw=1024 right=1024` on both the base and tailored-copy editors, both themes.
- **R2-S-06** (Résumé/Cover Letter Editor missing `<h1>`/`<h2>`) — now present: `document.querySelector('h1')` returns the résumé/letter name on both editors (e.g. "PM", "PM → Meta — Product Manager", "Scale — Senior AI Product Manager, Finance Agents").

## Couldn't test
- Exact per-screen "3-5 named primary controls" as a curated list — used the same automatic top-of-screen clickable-element probe as round 2 (see its Methodology notes); Stage 3's per-screen inventories remain the authoritative source for exact control names.
- Menu items *behind* an opened modal/menu (e.g. Résumé Editor's "Score again · light/full", Companies' "Delete config"/"Delete company", Searches' "Delete search", Applications' "Delete application", the tailored ReviewModal's "Decline"/"Done reviewing") — the modal/menu inventory only opens and closes each overlay per the read-only, no-LLM, no-mutation brief; clicking an action inside one was out of scope for this pass.
- Toast Lab's "Fire all (watch the 3-toast cap)" cascading-stack behavior — only single-fire-per-kind was in scope this round (task asked for "each toast kind once").
- Settings "Manage…" only exercised on the one row that has it (Model catalog); if other rows gain a `kind: 'models'` action in the future they weren't separately checked.
- Whether the Companies drawer / Résumé Editor "⋯" menu / Settings ModelsModal gaps (R3-S-02/03/04) are deliberate — flagged as needs-decision rather than assumed defects, per the "design deviations are decisions" addendum.

## Summary
- 22 route/variant sections covered (13 v2 incl. `/v2/toasts`, a base and a tailored `/v2/resumes/{id}`, and `/v2/cover-letters/{id}`; 9 v1), each across light/dark × 1440/1024 — same matrix as round 2.
- Console errors / pageerrors: 0 across every route, both themes, both viewports, on normal load — matches round 2's clean result.
- API-failure path: all 13 v2 screens show a visible error state (`err_text=True`) and no white screen; v1 screens unchanged from round 2 (R2-S-04/05, both already logged, not re-litigated here).
- Horizontal overflow: one v2 recurrence (R3-S-01 = R2-S-01, still needs a decision), one v2 fix confirmed (R2-S-02, now clean); v1 legacy-shell findings (R2-S-03) unchanged in kind, values shifted with current data (Persona 1050 same as round 2, Stats 1397 vs round 2's 1171, Resume Builder now clean but data-dependent — not re-logged, same root cause).
- Deep links: `/v2/feed?job=`, `/v2/feed?company=`, `/v2/feed?job=<bad>`, `/v2/resumes/<bad>`, `/v2/cover-letters/<bad>`, `/v2/stats#runs` (all 4 combos) — all passed, same as round 2.
- **New this round — modal/menu inventory**: 24 triggers probed across 9 v2 screens (Feed 5, Searches 3, Companies 5, Applications 3, Résumés shelf 1, Résumé Editor base 2, Résumé Editor tailored copy 3, Cover Letter Editor 2, Settings 2), plus 3 screens confirmed to have none (Cover Letters shelf, Persona, Stats). 20/24 opened, closed-on-Escape and closed-on-scrim-click cleanly. 4 gaps found: R3-S-02 (Companies drawer, no scrim), R3-S-03 ×2 (Résumé Editor head menu, base + tailored copy, no Escape), R3-S-04 (Settings Model catalog, no Escape) — all logged as needs-decision, nothing fixed (out of scope for this stage).
- **New this round — Toast Lab**: all 8 sample toasts (2×progress, 2×success, 2×error, 2×undo) fired once, checked at 1s and 6s against the actual toast-stack container. Matches the documented taxonomy exactly: progress/success/undo auto-dismiss by 6s, both errors persist. No findings.
- **New this round — Feed keyboard pass**: with `PATCH /api/jobs/*` intercepted and aborted, `j`/`k`/`Escape`/`o`/`s`/`x` all produced the expected, code-traceable behavior (selection moves, a row menu opens/closes on Escape, `o` opens a real new tab via `window.open`, `s`/`x` optimistically update then revert with a "Couldn't update" error toast) with zero real writes reaching the backend (2/2 intercepted PATCHes aborted). `Enter` is a confirmed no-op — v2 Feed's keydown switch has no case for it (detail is already shown via row selection, so there's nothing for Enter to toggle); not a defect, matches the code.
- Scratch data: none created (read-only pass). `ZZA`/`ZZB` rows from parallel flow agents were visible in a couple of list snapshots (e.g. Resume Builder primary-controls capture picked up a "ZZB Base (tailored)" row) and were left untouched, per instructions.

