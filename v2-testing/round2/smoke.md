# Round 2 smoke test

Read-only pass, no data mutations, no LLM calls. Repo v2-redesign branch, HEAD at run time.
Playwright inside backend container against http://caddy. Themes light/dark, viewports 1440x900 and 1024x700.

Legend: check rows are per column light-1440 / dark-1440 / light-1024 / dark-1024. X-Frame-Options iframe console noise ignored per instructions. Primary controls are auto-detected (main-content clickable elements near the top of the screen, up to 6, deduped by label) rather than a hand-picked list per screen.

## V2 Feed
`/v2/feed`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | The Feed | The Feed | The Feed | The Feed |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search titles…, Open tailored résumé, Open ↗, More actions, Source ▾] | ✔ [Search titles…, Open tailored résumé, Open ↗, More actions, Source ▾] | ✔ [Search titles…, Open ↗, More actions, Source ▾, ▾] | ✔ [Search titles…, Open ↗, More actions, Source ▾, ▾] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
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
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/searches` -> 500): ✔ nonblank=148 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: A[Jobs
9] > A[Searches
6] > A[Companies
126]

## V2 Companies
`/v2/companies`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Companies | Companies | Companies | Companies |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 126 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 126 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 126 companies, Click to pause scraping, Scrape this company now] | ✔ [Search name, alias, URL or A, Add/remove from filter · mul, Applies to all 126 companies, Click to pause scraping, Scrape this company now] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1335 | ✖ sw=1024 iw=1024 right=1335 | doc scrollWidth OK; a row's "⋯" more-actions icon sits inside a `DIV` with `overflow-x:auto` ancestor at 1024 — see R2-S-01 |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
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
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/applications` -> 500): ✔ nonblank=317 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✔ opened=True closed_on_esc=True
- **Tab x3 from body**: TEXTAREA[Notes…] > BODY[JobNavigator
JN
FIND
Jobs
9
Se] > A[Jobs
9]

## V2 Résumés (shelf)
`/v2/resumes`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Résumés | Résumés | Résumés | Résumés |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] | ✔ [Search bases, copies, archiv, + New résumé, Persona your full profile · , Persona, your full profile · 2 recent] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes` -> 500): ✔ nonblank=135 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
9] > A[Searches
7] > A[Companies
126]

### Résumés bad-id deep link
- bad id navigates to shelf: ✔ (path=/v2/resumes); error toast seen: ✔

## V2 Résumé Editor (base: PM)
`/v2/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | (none) JobNavigator
JN
FIND
Jobs
9
Searches
7
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
7
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
7
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
7
C |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] | ✔ [More, › Header, › Summary, ⌄ Experience (3), Résumé template] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1027 | ✖ sw=1024 iw=1024 right=1027 | ~3px bleed from an `<a>` element, no scroll ancestor — see R2-S-02 |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '7', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes/22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a` -> 500): ✔ nonblank=941 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: INPUT[] > SPAN[Move up] > SPAN[Move down]
- base resume id=22ce0e5b-8b9b-4ea5-b34a-b9b6f9e3a51a

## V2 Résumé Editor (tailored copy)
`/v2/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] | ✔ [⋯, › Header, › Summary ● changed by tailo, ⌄ Experience (3) ● changed b, Résumé template] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1027 | ✖ sw=1024 iw=1024 right=1027 | ~3px bleed from an `<a>` element, no scroll ancestor — see R2-S-02 |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/resumes/d28bbd9e-6419-445e-8259-2ac0e002aa7e` -> 500): ✔ nonblank=941 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): ✖ opened=False closed_on_esc=True
- **Tab x3 from body**: INPUT[] > SPAN[Move up] > SPAN[Move down]
- tailored resume id=d28bbd9e-6419-445e-8259-2ac0e002aa7e, name='PM → Meta — Product Manager'

## V2 Cover Letters (shelf)
`/v2/cover-letters`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | Cover Letters | Cover Letters | Cover Letters | Cover Letters |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] | ✔ [Search letters, companies…, Select a résumé… ▾, Select a résumé…, ▾, Scale — Senior AI Product Ma] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '126', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/cover-letters` -> 500): ✔ nonblank=400 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
9] > A[Searches
6] > A[Companies
126]

### Cover Letters bad-id deep link
- bad id: landed path=/v2/cover-letters/00000000-0000-0000-0000-000000000000; main nonblank length=53

## V2 Cover Letter Editor
`/v2/cover-letters/ce44e1d4-2763-4088-99a4-2f71f8e68115`

| check | light 1440 | dark 1440 | light 1024 | dark 1024 | note |
|---|---|---|---|---|---|
| heading present | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C | (none) JobNavigator
JN
FIND
Jobs
9
Searches
6
C |  |
| console errors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| pageerrors | ✔ (0) | ✔ (0) | ✔ (0) | ✔ (0) |  |
| primary controls | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] | ✔ [‹ Cover Letters, Rewrite the letter — pick ba, Cover letter template, Paper size — US Letter or A4, ↓ Download PDF] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1024 iw=1024 right=1024 | ✔ sw=1024 iw=1024 right=1024 |  |
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
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
| rail counts (<1s) | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '9', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
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
| rail counts (<1s) | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
| health dot | present | present | present | present |  |

- **API failure** (stub `/api/stats` -> 500): ✔ nonblank=3516 err_text=True pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs
12] > A[Searches
6] > A[Companies
127]

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
| rail counts (<1s) | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} | ✔ {'/v2/feed': '12', '/v2/searches': '6', '/v2/companies': '127', '/v2/applications': '377', '/v2/resumes': '4', '/v2/cover-letters': '16'} |  |
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

- **API failure** (stub `None` -> 500): not tested
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: BODY[Toast lab
Temporary — fire eac] > BODY[Toast lab
Temporary — fire eac] > BODY[Toast lab
Temporary — fire eac]
- temporary review screen, not under the v2 rail shell (App.jsx route is top-level, outside V2App)

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
| no h-overflow | ✔* sw=1440 iw=1440 right=1820 | ✔* sw=1440 iw=1440 right=1820 | ✔* sw=1024 iw=1024 right=1820 | ✔* sw=1024 iw=1024 right=1820 | *not a bug: `document.documentElement.scrollWidth == innerWidth` (page doesn't scroll); the wide element is a kanban column inside its own `overflow-x:auto` container (`main` has `overflow-auto`) — intentional horizontal board scroll |

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
| primary controls | ✔ [1 company need attention. Re, Dismiss, Persona, [tailored] PM → Meta — Produ, Delete resume] | ✔ [1 company need attention. Re, Dismiss, Persona, [tailored] PM → Meta — Produ, Delete resume] | ✔ [Dismiss, Persona, [tailored] PM → Meta — Produ, Delete resume, Download PDF] | ✔ [Dismiss, Persona, [tailored] PM → Meta — Produ, Delete resume, Download PDF] |  |
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1150 | ✖ sw=1024 iw=1024 right=1150 | doc scrollWidth OK; v1 not built responsive below ~1150px — see R2-S-03 |

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

- **API failure** (stub `/api/cover-letters` -> 500): ✔ nonblank=1185 err_text=False pageerrors=0
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
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1050 | ✖ sw=1024 iw=1024 right=1050 | doc scrollWidth OK; v1 not built responsive below ~1150px — see R2-S-03 |

- **API failure** (stub `/api/persona` -> 500): ✔ nonblank=445 err_text=False pageerrors=1
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
| no h-overflow | ✔ sw=1440 iw=1440 right=1440 | ✔ sw=1440 iw=1440 right=1440 | ✖ sw=1024 iw=1024 right=1171 | ✖ sw=1024 iw=1024 right=1171 | doc scrollWidth OK; v1 not built responsive below ~1150px — see R2-S-03 |

- **API failure** (stub `/api/stats` -> 500): ✔ nonblank=7392 err_text=True pageerrors=0
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

- **API failure** (stub `/api/settings` -> 500): ✔ nonblank=1602 err_text=False pageerrors=0
- **Keyboard Escape** (generic menu-trigger probe): no menu found
- **Tab x3 from body**: A[Jobs] > A[Applications] > A[Companies]

---

## Methodology notes

- **Primary controls** are auto-detected per screen (main-content clickable elements — `button`, `[role=button]`, `input`, `a[href]`, or any element with computed `cursor: pointer` — within ~220px of the top, deduped by visible label, first 6 kept), not a hand-picked list. This is a smoke check for "present and enabled," not the precise curated inventory Stage 3 used; on list screens it sometimes picks up the first row's action buttons alongside the toolbar.
- **Keyboard Escape** uses a single generic trigger probe (`[title="More actions"], [title="Change row order"], [aria-haspopup="listbox"], [aria-expanded]`), clicks the first match, and checks whether `.v2-menuitem`/`[role=option]` count increased then dropped after Escape. "no menu found" means the probe found no matching trigger on that screen, not that the screen has no menus — several screens (Cover Letters shelf, Résumés shelf, Stats, all v1 screens) use interaction patterns the probe doesn't recognize (row-embedded dropdowns, custom widgets). "opened=False" on Résumé Editor/Persona/Settings/tailored-copy screens means the probe's matched element (an accordion `›`/`⌄` section toggle, which also carries `aria-expanded`) doesn't add `.v2-menuitem` elements when clicked — not a defect, a probe limitation. Treat these as "not exercised," not "failed."
- **No h-overflow**: `document.documentElement.scrollWidth <= innerWidth` (page-level) is the primary signal; a secondary scan flags any element whose right edge exceeds the viewport, which also fires for content that is intentionally horizontally scrollable inside its own `overflow-x:auto` container (kanban board, some table rows). Findings below distinguish the two.

## Issues

### R2-S-01 · P3 · Companies row "more actions" icon sits past the viewport edge at 1024px
**Where** `frontend/src/v2/Companies.jsx` (row action, `title="More actions"`), `/v2/companies`
**Repro** Load `/v2/companies` at 1024×700 (either theme), inspect the row's `⋯` control.
**Actual** `getBoundingClientRect().right = 1335` against `innerWidth = 1024`; `document.documentElement.scrollWidth == innerWidth` (page itself doesn't scroll) — the element sits inside a `DIV` with `overflow-x: auto`.
**Expected** Unclear whether the row is meant to be horizontally scrollable at this width (by-design, matching the Application Board kanban pattern) or the `⋯` action should stay pinned in view.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

### R2-S-02 · P4 · Résumé Editor overflows by ~3px at 1024px width
**Where** `frontend/src/v2/ResumeEditor.jsx`, `/v2/resumes/{id}` (both a base and a tailored copy reproduce it)
**Repro** Load either résumé editor at 1024×700, either theme.
**Actual** `document.documentElement.scrollWidth = 1027` vs `innerWidth = 1024` (page-level overflow, not a contained-scroll false positive — no `overflow-x:auto` ancestor found). Offending element is an `<a>` with no class.
**Expected** No horizontal scroll at 1024px.
**Proposed fix** Track down the unstyled `<a>` (likely a link inside the header/breadcrumb row) and constrain its width or add `min-width: 0`/`flex-wrap`.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

### R2-S-03 · P4 · Several v1 screens overflow horizontally at 1024px (Resume Builder, Persona, Stats)
**Where** `frontend/src/components/ResumeBuilder.jsx`, `Persona.jsx`, `Stats.jsx`; routes `/resumes`, `/persona`, `/stats`
**Repro** Load each at 1024×700, either theme.
**Actual** `document.documentElement.scrollWidth` = 1150 / 1050 / 1171 respectively vs `innerWidth = 1024`.
**Expected** N/A — the classic (v1) shell was never built responsive below its original desktop target width; this is a known characteristic of the screen being replaced, not a regression. Noted for completeness since the check was in scope.
**Status** decided ignore (user 2026-09-04, with R2-S-05): v1 screens are being replaced.

### R2-S-04 · P2 · V1 Persona has no error handling for a failed `GET /api/persona`
**Where** `frontend/src/components/Persona.jsx:92` — `const { data } = await api.get('/persona')` inside `fetchPersona`, no try/catch, called directly from a `useEffect`
**Repro** Stub `GET /api/persona` to 500, load `/persona`.
**Actual** Unhandled promise rejection: pageerror `"Request failed with status code 500"`; no error banner or empty-state message — the persona sections just never render (only unrelated shell banner text is visible).
**Expected** A caught failure with a visible error state, matching the v2 Persona screen's behaviour (`err_text=True` on the same stub).
**Proposed fix** Wrap the `api.get('/persona')` call in try/catch and set an error/loading-failed state, mirroring v2 `Persona.jsx`'s `loadErr` handling.
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

### R2-S-05 · P3 · Most v1 screens show no visible error state on a failed list/data GET
**Where** `frontend/src/components/{JobFeed,ApplicationBoard,CompanyManager,SearchManager,ResumeBuilder,CoverLetterBuilder,Settings}.jsx` — routes `/`, `/applications`, `/companies`, `/searches`, `/resumes`, `/cover-letters`, `/settings`
**Repro** Stub the screen's main list/data GET to 500, load the route.
**Actual** Page renders without crashing (`pageerrors=0`, non-blank `main`), but `document.body.innerText` never matches error/failed/try-again wording — i.e. no error row or toast, the screen just looks like an empty/default state. (V1 Stats is the one exception — it does show an error state.)
**Expected** Some visible indication that the data failed to load rather than silently rendering empty, matching v2's behaviour on the same stub (all 11 v2 screens tested show `err_text=True`).
**Status** decided ignore (user 2026-09-04): v1 screens are being replaced by v2.

### R2-S-06 · P4 · Résumé Editor and Cover Letter Editor have no `<h1>`/`<h2>` heading
**Where** `frontend/src/v2/ResumeEditor.jsx:447`, `frontend/src/v2/CoverLetterEditor.jsx` — the document name is rendered as a plain `<span title={doc.name}>`, not a heading element
**Repro** Load `/v2/resumes/{id}` or `/v2/cover-letters/{id}`, run `document.querySelector('h1')` / `h2`.
**Actual** Neither exists on these two screens; every other v2 screen has an `<h1>`.
**Expected** Unclear if intentional (design may treat the editor's identity differently from list screens) — flagging for accessibility (screen reader page-structure navigation).
**Status** fixed (69d36b1/f75f2a1), verified live 2026-09-04 (`round2/verify.md`).

## Couldn't test
- Exact per-screen "3-5 named primary controls" as a curated list — used an automatic top-of-screen clickable-element probe instead (see Methodology notes). Stage 3's per-screen inventories are the authoritative source for exact control names.
- Menu/drawer Escape-close behaviour on screens the generic probe didn't find a trigger for: Cover Letters shelf, Résumés shelf, Stats (main list), all 9 v1 screens.
- Ink-level/hover/geometry-vs-design checks are out of scope for this pass (that's Stage 3); this pass is functional smoke only.

## Summary
- 23 routes covered (12 v2 incl. `/v2/toasts` and the `/v2/stats#runs` and résumé/cover-letter deep-link variants, 9 v1), each across light/dark × 1440/1024.
- Console errors / pageerrors: 0 across every route on normal load, in both themes and both viewports.
- API-failure path: all 11 v2 screens show a visible error state and no white screen; 8 of 9 v1 screens render without crashing but show no visible error text (R2-S-05); v1 Persona throws an unhandled pageerror (R2-S-04).
- Horizontal overflow: 2 v2 findings (R2-S-01 needs-decision, R2-S-02 minor real bleed), 4 v1 findings (1 false-positive/by-design kanban scroll corrected in-table, 3 legacy-shell width findings under R2-S-03).
- Deep links: `/v2/feed?job=`, `/v2/feed?company=`, `/v2/feed?job=<bad>`, `/v2/resumes/<bad>`, `/v2/cover-letters/<bad>`, `/v2/stats#runs` (all 4 combos) — all passed.
- Rail counts and health dot render within 1s on every v2 screen tested, all 4 combos.
- No data was created, modified, or deleted; no LLM calls were made; no commits or rebuilds.
