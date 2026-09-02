# v2 Companies — screen inventory

Screen file: `frontend/src/v2/Companies.jsx` (760 lines, read in full). Shell: `frontend/src/v2/V2App.jsx`. Toast API: `frontend/src/v2/Toast.jsx` (NOT imported by this screen). Axios: `frontend/src/api.js`.
All `file:line` refs below are `Companies.jsx` unless prefixed. Backend refs: `backend/api/routes_companies.py` (RC), `backend/main.py` (M), `backend/job_monitor.py` (JM), `frontend/src/v2/theme.css` (T).

---

## 1. Routes & params

- [ ] Route `/v2/companies` — nested under the `/v2` shell: `frontend/src/App.jsx:151` (`<Route path="/v2" element={<V2App />}>`) → `frontend/src/App.jsx:158` (`<Route path="companies" element={<V2Companies />} />`). Import at `App.jsx:21`.
- [ ] Query params READ by this screen: **none** — no `useSearchParams`/`useLocation`/`window.location` anywhere in `Companies.jsx`. No `?company=`/`?edit=`/`?add=` deep-link into the drawer/add modal.
- [ ] Query param EMITTED: `⋯ → View jobs in feed` builds `/v2/feed?company=<encodeURIComponent(name)>` at `393`. Note: `JobFeed.jsx` reads only `?job=` (`JobFeed.jsx:476, 490`) and `?search=` (`JobFeed.jsx:179`) — a `?company=` param is never read, so the link opens an unfiltered feed.
- [ ] localStorage `company_query` — read `125` (initial search text), written `147` (every keystroke).
- [ ] localStorage `company_filter_tiers` — read `126` (`JSON.parse`, falls back to `[]`), written `146` (JSON array of `'1'|'2'|'3'|'none'`).
- [ ] localStorage `company_sort` — read `127` (default `'health'`), written `148`.
- [ ] localStorage `company_tuning_open` — read `421` (Drawer mount; `'true'`/`'false'` string; if absent falls back to `!!(downReason || company.last_error)` at `422`), written `424` on toggle.
- [ ] Inherited (shell/axios): `jobnavigator_dark_mode` read `V2App.jsx:52`, written `V2App.jsx:54`; `jobnavigator_v2_rail` read `V2App.jsx:48`, written `V2App.jsx:55`; `jobnavigator_api_key` read `api.js:11` (sent as `X-API-Key`).
- [ ] Keyboard: `Escape` (document listener `153`) closes sort menu, row menu, drawer, add modal, test modal — all at once, no unsaved-changes confirm. Document `click` (`152`) closes sort menu + row menu only.

## 2. Data loads

- [ ] GET `/companies` — `fetchCompanies` `136-138`, called on mount `140`; `catch → console.error` (no UI). Re-called after: PATCH success `196`, bulk PATCH `200`, 2.6 s after Run `205`, DELETE success `215`, Add success `411`/`597`. Response fields consumed: `id, name, aliases, active, tier, scrape_urls, detected_scrape_types, selected_resume_ids, auto_scoring_depth, title_include_expr, title_exclude_keywords, scrape_interval_minutes, wait_for_selector, max_pages, h1b_slug, h1b_lca_count, h1b_approval_rate, application_count, open_jobs, open_jobs_week, avg_fit, last_error, last_run_at, last_scraped_at` (serialiser `RC:597-636`). `last_run_warning` (`RC:626`) is returned but never read.
- [ ] GET `/resumes?is_base=true` — `141`, on mount; `.catch(() => {})`; non-array → `[]`.
- [ ] GET `/persona` — `142`, on mount; `personaPopulated = Object.keys(resume_content).length > 0`; `.catch(() => {})`.
- [ ] GET `/health/entities` — `143`, on mount ONLY; builds `downMap[id] = reason` from `data.companies[]` (`M:1150-1176`: active companies whose last 3 ScrapeLogs all errored/warned). Never refreshed after Run/Save/bulk. `.catch(() => {})`.
- [ ] GET `/monitor/active` — `144`, on mount ONLY; sets `scraping[scope_key] = true` for every running job of any type (`JM:57-69`; `company_scrape` runs use `scope_key = company_id` string, `M:670`). Never polled. `.catch(() => {})`.
- [ ] Polling intervals: **none**. The only timer is the fixed `setTimeout(…, 2600)` after Run (`205`), which clears the spinner and refetches `/companies` regardless of whether the scrape finished.
- [ ] Shell loads that feed the rail badge for this screen: GET `/companies` `V2App.jsx:61` (badge = `data.length`), GET `/health/entities` `V2App.jsx:65-68` (amber dot / "N sources need attention").

## 3. Interactive elements

Legend: **API** = call(s) made; **State** = local state mutated; **OK toast** / **Fail** = feedback. This screen never imports `Toast.jsx`, so every "OK toast" below is **none**.

### Header
- [ ] `+ Add company` pill — `260` — `onClick={() => setAddOpen(true)}` — API none — State `addOpen` — OK toast none — no failure path. No hover class (inline style only).

### Toolbar
- [ ] Search box, placeholder "Search name, alias, URL or ATS…", ⌕ glyph `267` — `268-269` — inline `setQuery` — API none — State `query` (+ localStorage `147`) — filters client-side over `name`, `aliases[]`, `scrape_urls[]`, `Object.values(detected_scrape_types)` (`171`). No debounce, no clear (✕) button.
- [ ] Tier chip `Tier 1` + count — `272-281` — inline `setTiers` toggle — API none — State `tiers` (+ localStorage `146`) — class `v2-bd` — title "Add/remove from filter · multi-select, remembered per browser".
- [ ] Tier chip `Tier 2` + count — same (`272-281`).
- [ ] Tier chip `Tier 3` + count — same.
- [ ] Tier chip `Untiered` + count — same (`t === 'none'`, label at `278`).
- [ ] `Make {n} active` — `283-286`, rendered only when `inactiveInFilter.length > 0` — `bulkSet(true)` `197-201` — API `PATCH /companies/{id} {active:true}` once per inactive company in the current filter (`Promise.all`, each `.catch(() => {})`), then GET `/companies` — State none directly — OK toast none — **Fail: swallowed per item, no feedback, refetch still runs** — class `v2-act` — title = `bulkHint` (`191-193`).
- [ ] `Make {n} inactive` — `287-290`, rendered only when `activeInFilter.length > 0` — `bulkSet(false)` — API `PATCH /companies/{id} {active:false}` per active company in filter — same swallow — class `v2-bd-warn` (text `var(--warn)`) — no confirm dialog.
- [ ] `Sort <current label> ▾` trigger — `293-296` — `setSortOpen(v => !v)` — wrapper `292` stops propagation so document click doesn't immediately close — title "Change row order" — no hover class.
- [ ] Sort option `Needs attention` (`health`) — `299-307` (option data `52`) — `setSortBy('health'); setSortOpen(false)` — comparator `176`: downMap first, then active, then name. **Does NOT consider `last_error`.** class `v2-menuitem`, ✓ on active `304`.
- [ ] Sort option `Company name` (`name`) — `53`/`177` — A→Z `localeCompare`.
- [ ] Sort option `Priority tier` (`tier`) — `54`/`178` — `tier ?? 99` ascending, then name.
- [ ] Sort option `Open roles` (`open`) — `55`/`179` — `open_jobs` desc, then name.
- [ ] Sort option `Average fit` (`fit`) — `56`/`180` — `avg_fit ?? -1` desc (unscored last), then name.
- [ ] Sort option `Last scrape` (`run`) — `57`/`181` — `last_scraped_at` ascending; `null` → epoch 0 → never-scraped first.
- [ ] Column headers `Company / Tier / Health / Résumés / ATS / Open · 7d / Apps / Ø Fit / Status / (actions)` — `317-328` — **not clickable**, no handlers; tooltips on Résumés `321`, ATS `322`, Open·7d `323` ("Open roles in the Job Feed · new in the last 7 days"), Apps `324` ("Open applications"), Ø Fit `325`. Header is `position: sticky` inside the scroll container (`317`).

### Row (one per `filtered` company, `329-400`)
- [ ] Row click (whole row) — `336` — `openDrawer(c)` `236-249` builds `draft` from company — API none — State `drawer` — class `v2-crow`. Opening a second row while the drawer is open replaces the draft silently.
- [ ] ▲ needs-attention glyph — `340`, shown when `c.last_error || downMap[c.id]` — no handler — title `Needs attention — {reason}` — colour `var(--bad)` for last_error else `var(--warn)`.
- [ ] Company name — `341` — no handler — title = name — ellipsis.
- [ ] `+{aliases.length-1}` alias badge — `342`, shown only when `aliases.length > 1` — no handler — title "Also scraped as {all aliases}". (A company with exactly one alias gets no badge.)
- [ ] Tier chip `T1/T2/T3/—` — `346` — display only — class `tierSlug()` `23`.
- [ ] Health dot + text — `350-351` — display only — title = full text (see §4 for variants).
- [ ] Résumés cell — `354` — display only — text `resumeNames(c)` `219-225` or `Default`; title = names or "Scored against your default résumé from Settings".
- [ ] ATS chip (first URL's detected type via `atsShort` `20-21`) — `357` — display only — title = all URLs joined by `\n` — class `atsSlug()` `22`.
- [ ] ATS `+{n}` extra-URL count — `358` — display only, shown when `urls.length > 1`.
- [ ] ATS `—` — `359` — shown when no URLs.
- [ ] `Open +7d` numbers — `362-364` — display only — title "{open} open roles from {name} in the Job Feed · {week} new in the last 7 days".
- [ ] `Apps` — `366` — display only — `application_count || '·'`.
- [ ] `Ø Fit` — `368` — display only — `avg_fit ?? '–'`, colour via `fitColor` `233` (≥80 good, ≥65 text-2, else warn, null muted); title "No scored roles yet" / "Average fit {n} …".
- [ ] `Active` / `Inactive` status pill — `371-372` — `e.stopPropagation(); patchCompany(c.id, { active: !c.active })` `196` — API `PATCH /companies/{id}` then GET `/companies` — OK toast none — **Fail: `console.error` only** — class `v2-bd` — title "Click to pause/resume scraping". No optimistic update (pill flips after refetch).
- [ ] `↻ Run` / `Running` — `376-382` — `runScrape(c.id)` `202-206` — API `POST /scrape/company/{id}` (202 + run_id; 409 if already running `M:672-677`) — State `scraping[id]=true` immediately, cleared after fixed 2600 ms + GET `/companies` — OK toast none — **Fail (incl. 409): `console.error` only; spinner still shows "Running" for 2.6 s** — class `v2-act` — spinner `v2-spin` `379`.
- [ ] `⚗ Test` — `383-386` — `runTest(c.id)` `207-212` — API `POST /companies/{id}/test-scrape` (synchronous; 400 "No scrape URLs configured" when empty `RC:404-405`; 500 on scrape error `RC:590`) — State `testingId`, `showShots=false`, `test` — success opens `TestModal`; **Fail: caught → `setTest({error: detail || message})` → error modal** — class `v2-act`.
- [ ] `⋯` more-actions — `387-388` — `setMenuId(menuId === c.id ? null : c.id)` — actions cell `375` stops propagation so row doesn't open — class `v2-act`; border/background turn accent while open.
- [ ] ⋯ → `✎ Edit config` — `391` — `setMenuId(null); openDrawer(c)` — API none — class `v2-menuitem`.
- [ ] ⋯ → `↗ Open career page` / `Open {n} career pages` — `392`, shown only when `urls.length > 0` — `window.open(u, '_blank', 'noopener,noreferrer')` in a loop — API none — popup blockers will typically allow only the first window.
- [ ] ⋯ → `☰ View jobs in feed` — `393` — plain `<a href="/v2/feed?company=…">` (not React Router `Link` → full page reload) — API none — Feed ignores the param (see §1) — class `v2-menuitem`.
- [ ] ⋯ → `✕ Delete company` — `394` — `deleteCompany(c)` `213-216` — native `window.confirm("Delete {name}? Jobs already found are kept.")` then API `DELETE /companies/{id}` → `setMenuId(null); setDrawer(null); fetchCompanies()` — OK toast none — **Fail: `console.error` only** — class `v2-hover-bad`, text `var(--bad)`.

### Empty-state
- [ ] `Clear filters` link — `405` — `clearFilters` `235` (`setQuery(''); setTiers([])`) — API none — no hover class.

### Edit drawer (`Drawer`, `418-564`, 720 px, `position:absolute` inside the screen, z 30; no scrim, no outside-click close)
- [ ] `✕` close — `459` — `setState(null)` — discards unsaved draft with no confirm — class `v2-hover-accent`.
- [ ] Warning banner — `463-471`, shown when `company.last_error || downReason` — non-interactive (see §4).
- [ ] `Display name` input — `478` — `set({ name })` — draft only; drawer title mirrors live `456`.
- [ ] `Also known as` input, placeholder "Alt names, comma-separated" — `482` — `set({ aliases })` (string, split on save `437`). Help `483`.
- [ ] URL editor (`UrlEditor` `72-91`, mounted `485`):
  - [ ] Live ATS chip per URL — `79` — display; `detectAts()` `34-49` client-side mirror, re-evaluated per keystroke; class `atsSlug()`.
  - [ ] URL input per row, placeholder "https://boards.greenhouse.io/company" — `80-81` — `set(i, v)` `73` → `onChange` → `set({ scrape_urls })`. Rows keyed by index `78`.
  - [ ] `✕` remove URL — `82-83` — `onChange(urls.filter(...))` — title "Remove this URL" — class `v2-hover-bad`.
  - [ ] `+ Add another career page` dashed row — `87-88` — `onChange([...urls, ''])` — class `v2-dashadd`. Empty strings are dropped on save `438`.
- [ ] `Title must match` input, placeholder "(Product OR Project) AND Manager" — `495` — `set({ title_include_expr })` — help `496`. Saved as `null` when blank `439`.
- [ ] `Skip titles containing` input, placeholder "intern, junior, associate" — `500` — `set({ title_exclude_keywords })` — help `501`; split on save `440`.
- [ ] `Score new jobs automatically` — `Seg` `Off` — `505` (Seg `93-104`, option `60`) — `set({ auto_scoring_depth: 'off' })` — class `v2-bd` — title hint.
- [ ] Seg `Light` — `505`/`61` — `'light'`.
- [ ] Seg `Full` — `505`/`62` — `'full'`.
- [ ] Résumé chips (`ResumeChips` `106-116`, mounted `506`): one chip per base résumé `108-111` — `toggleResume(r.id)` `426` — class `v2-bd`.
- [ ] `Persona` chip — `112-114`, shown only when `personaPopulated` — `toggleResume('persona')` (magic id understood by `backend/analyzer/cv_scorer.py:135`).
- [ ] Résumé help line — `507` — `resumeHelp` `431` (names or "Nothing selected, so new jobs use your default résumé from Settings.").
- [ ] `Scraper tuning` collapsible header `› / ⌄` + note — `515-519` — `toggleTuning` `424` (localStorage) — note text `tuningNote` `432` = `needs attention` (bad/warn colour) / `customised` / `using defaults` — no hover class.
- [ ] `Priority tier` Seg `1` — `525` (`TIER_BTNS` `64`, `valueKey="v"`) — `set({ tier: 1 })`.
- [ ] Seg `2` — `525`.
- [ ] Seg `3` — `525`.
- [ ] Seg `None` — `525` — `set({ tier: null })`.
- [ ] `Scrape interval in minutes` number input, `min=1`, placeholder "Use global interval" — `530` — `set({ scrape_interval_minutes })` — save: `'' → null`, else `parseInt || null` `444` (so `0` → null).
- [ ] `Wait for element` input (mono), placeholder "CSS selector" — `535` — `set({ wait_for_selector })` — `null` when blank `445`.
- [ ] `Pages to read` number input, `min=1 max=20` — `540` — `set({ max_pages })` — save `parseInt || 5` `446` (no clamp to 1–20).
- [ ] `H-1B employer name` input (mono), placeholder "Auto-detect" — `546` — `set({ h1b_slug })` — `null` when blank `447`. Backend re-fires H-1B lookup when slug or name changes (`RC:236-239`).
- [ ] H-1B line — `547` — `lcaLine` `429`: with filings → "{n} filings on record[ · {rate}% approved] — each job's H-1B verdict is drawn from these." (colour `var(--good)`); else "No filings on record, so jobs here show H-1B Unknown. Blank auto-detects from the company name." (muted). Display only.
- [ ] Footer `Make inactive — jobs already found are kept` / `Make active` — `555` — `onSave(company.id, { active: !draft.active }); set({ active })` — API `PATCH /companies/{id}` **immediately** (independent of Save) + GET `/companies` — OK toast none — **Fail: `console.error` only; local `draft.active` flips anyway** — no hover class; text colour warn/accent.
- [ ] Footer `Test scrape` / `Testing…` — `556-559` — `onTest(company.id)` (= `runTest`) — same API/feedback as row Test — spinner when `testingId === company.id` — class `v2-act`.
- [ ] Footer `Save changes` — `560` — `save` `434-450` — API `PATCH /companies/{id}` with `{name, aliases[], scrape_urls[], title_include_expr, title_exclude_keywords[], auto_scoring_depth, selected_resume_ids, tier, scrape_interval_minutes, wait_for_selector, max_pages, h1b_slug}` (`active` intentionally absent) — `setState(null)` runs synchronously **before** the request resolves — OK toast none — **Fail: `console.error` inside `patchCompany`; drawer already closed, user sees nothing** — no hover class.
- [ ] Delete from drawer — **does not exist**: `onDelete` is passed (`410`) and destructured (`418`) but no control uses it.

### Add modal (`AddModal`, `567-660`, fixed scrim z 60)
- [ ] Scrim click — `602` — `onClose`; inner card `603` stops propagation.
- [ ] Live ATS chip — `612` — display; `—` on empty URL; `atsSlug(ats)` otherwise.
- [ ] `Career page URL` input (mono), placeholder "https://boards.greenhouse.io/acme" — `613` — `setUrl`. Only ONE URL can be entered here (more via drawer).
- [ ] ATS note — `615` — `atsNote` `578-580`: no URL → "The ATS is detected once you paste a URL."; known → "Jobs are read from the board's API, so no page settings are needed."; unknown → warn-coloured "No known ATS — the page is loaded and read as HTML. If it lists nothing, set a wait-for selector in the company config."
- [ ] `Company name` input, placeholder "Acme" — `620` — `setName`. Required (checked `587`).
- [ ] `Aliases` input — `624` — `setAliases`.
- [ ] `Tier` Seg `1 / 2 / 3 / None` — `630` — `setTier`; default `2` (`571`).
- [ ] `Scrape interval in minutes` input — `634` — `setIntervalV`.
- [ ] `Score new jobs against` résumé chips + Persona — `639` — `toggle` `584`.
- [ ] `Depth` chips `Off / Light / Full` — `643-645` — `setDepth`; default `'light'` (`574`) — class `v2-bd` — title hint.
- [ ] Score note — `649` — `scoreNote` `582-583`.
- [ ] Static note — `650` — "Title filters, wait-for selector and max pages use the defaults — change them in the company config when a board needs it."
- [ ] Footer note — `653` — "Scrapes on the next scheduled run".
- [ ] `Cancel` — `654` — `onClose` — no hover class.
- [ ] `Save` / `Saving…` — `655` — `save` `586-599` — empty name → native `window.alert('Company name is required')`; API `POST /companies {name, aliases[], scrape_urls[0..1], tier, scrape_interval_minutes, selected_resume_ids, auto_scoring_depth}` — success → `onCreated()` (GET `/companies`) + `onClose()`, OK toast none — **Fail: native `window.alert(detail || 'Failed to add company')`** (409 "Company already exists" surfaces this way), `setSaving(false)`. While `saving`, the handler is still attached (only cursor/opacity change) → double-click can double-POST. `saving` never resets on success (component unmounts).

### Test-scrape modal (`TestModal`, `663-760`, fixed scrim z 60)
- [ ] Error variant scrim click — `666` — `onClose`.
- [ ] Error variant `Close` — `670` — `onClose`. Copy: title "Test scrape — Error" `668`, message in `var(--bad)` `669`.
- [ ] Result variant scrim click — `689` — `onClose`.
- [ ] `Show screenshots` / `Hide screenshots` toggle — `694`, shown only when `test.screenshots.length > 0` — `setShowShots(v => !v)` (state lives in parent `134`, reset on each Test `208`) — no hover class.
- [ ] `✕` close — `696` — `onClose` — class `v2-hover-accent`.
- [ ] Per-job `↗` link — `746` — `<a href={j.url} target="_blank" rel="noopener noreferrer">` — hover via `.jn-v2 a:hover` `T:121`.
- [ ] Footer `Close` — `755` — `onClose` — no hover class.
- [ ] Display-only regions: "URLs scraped · {n}" + list `700-701`; Include/Exclude chips `702-707`; screenshot panel `710-719` (`data:image/png;base64`); "Pagination debug" `721-728` (green "Clicked {selector} — {text}" / red "No next button found"); sticky table header `# / Title / Status / Reason / Link` `731-737`; rows `738-749` with tag `Kept` (accent-soft/good) / `Out` (bad) / `Drop` (warn, `[Validation]` prefix stripped) via `jobState` `683-687`; summary line `679`/`754`.

## 4. States rendered

### Company list (`316-408`)
- [ ] **Loading: does NOT exist.** `companies` initialises to `[]` (`120`), so until GET `/companies` resolves the screen renders the zero-results branch below with copy "No companies match / No companies in the selected tiers." (`401-406`) and the header reads "0 tracked · 0 active · 0 need attention" (`188`). No skeleton, no spinner.
- [ ] **Error (GET /companies fails): does NOT exist** as UI — `console.error` `137`; same empty branch as above is shown.
- [ ] **No companies at all (first run): no dedicated branch** — falls into "No companies match" + "No companies in the selected tiers." + a `Clear filters` link that does nothing useful (`401-407`).
- [ ] Zero results with a search query — `401-405` — copy `No companies match` / `Nothing matches "{query}" in names, aliases, URLs or ATS.` / `Clear filters`.
- [ ] Zero results with tier filter only — `404` — `No companies in the selected tiers.`
- [ ] Bulk buttons hidden when no targets — `283`, `287` (conditional render, not disabled).
- [ ] Long strings: company name ellipsis `341`; health text ellipsis `351` (title shows full); résumé names ellipsis `354`; ATS chip `nowrap` without ellipsis `357` (fixed 108 px cell — long ATS names like `SmartRecruiters` may overflow/clip the `+n`); alias badge nowrap `342`.

### Health cell (`healthOf` `226-232`, precedence top→bottom)
- [ ] `scraping now…` — accent dot, accent text — when `scraping[c.id]` (`227`): set from GET `/monitor/active` on mount (any running job whose `scope_key === c.id`) or for 2.6 s after clicking Run.
- [ ] `error · {last_error}` — bad dot, bad text — when `c.last_error` (`228`) = `error` of the company's most recent `ScrapeLog` (`RC:157-183`). Applies even when the company is inactive (checked before `active`).
- [ ] warning / "down" — warn dot, warn text = `downMap[c.id]` reason (`229`), i.e. `/health/entities` reason: the first error text of the last 3 runs (truncated to 160 chars, `M:1162-1163`) or `No results in the last 3 scrapes` (`M:1164`). Only active companies can be here (`M:1167`).
- [ ] `healthy · scraped {ago}` — good dot, text-2 — active and none of the above (`230`).
- [ ] `inactive · last run {ago}` — edge dot, muted — not active (`231`).
- [ ] **Never scraped: no dedicated variant** — `ago(null)` returns `'never'` (`7`) so an active never-run company reads `healthy · scraped never` with a GREEN dot; inactive reads `inactive · last run never`.
- [ ] **Last-run-warning (0 results once, `last_run_warning` `RC:626`): NOT surfaced** — shows as healthy until three consecutive bad runs promote it to `downMap`.
- [ ] `ago()` buckets (`6-15`): `just now` (<1 m), `{m}m ago`, `{h}h ago`, `{d}d ago` — no week/month cap; no future-time guard.

### Row ▲ / header count
- [ ] ▲ shown when `c.last_error || downMap[c.id]` (`340`); header "{n} need attention" counts only `downMap` (`187`) — so rows can show ▲ while the header says 0.

### Drawer (`418-564`)
- [ ] Banner variant "error" — `463-468` — border/bg `var(--bad)`/`var(--bad-soft)`, text `company.last_error`, sub "Last scrape run · last ran {ago(last_run_at || last_scraped_at)}".
- [ ] Banner variant "down" — same block — warn colours, text `downReason`, sub "Detected on the recent runs · last ran …".
- [ ] Banner absent — when neither.
- [ ] Subtitle `457` — `{Untiered|Tier n} · {k} career URL(s) · {application_count} open application(s)` (`427`; label says "open" but `application_count` is all applications).
- [ ] Scraper tuning collapsed/expanded — `520`; note `needs attention` / `customised` / `using defaults` (`432`; "customised" when interval, selector, `max_pages !== 5`, or `h1b_slug` set).
- [ ] H-1B line two variants — `429`/`547` (see §3).
- [ ] Résumé help two variants — `431`.
- [ ] **Résumé chips when there are no base résumés and persona is empty: renders nothing** (`106-116`) — no "No résumés yet" copy; only the help line remains.
- [ ] **URL editor with zero URLs: no copy** — only the dashed add row `87-88`.
- [ ] Drawer title ellipsis `456`; subtitle `457` no ellipsis; banner text wraps `467`.
- [ ] **No saving/pending state on `Save changes`** — drawer closes instantly `449`.

### Add modal
- [ ] ATS chip `—` (empty URL) vs detected chip — `612`.
- [ ] `atsNote` three variants — `578-580`; unknown-ATS variant is warn-coloured `615`.
- [ ] `scoreNote` — `582-583`: depth off → "New jobs arrive unscored — you can score them by hand from the feed."; else "New jobs are scored against {names | your default résumé from Settings} as they arrive."
- [ ] Saving state — `655` label `Saving…`, opacity 0.6.
- [ ] Validation error — native alert `587`; server error — native alert `598`.

### Test modal
- [ ] Error variant — `664-674`.
- [ ] Screenshots toggle only when `screenshots.length > 0` — `693`; panel `710`.
- [ ] Include/Exclude line only when `include_expr` or `exclude_keywords.length` — `702`.
- [ ] Pagination debug only when `pagination_debug.length` — `721`.
- [ ] Zero rows — `750` — "No job links found on this page."
- [ ] Row tags `Kept` / `Out` / `Drop` — `683-687`; `[Global] Excluded by …` rows render as plain `Out` (backend `RC:551`), indistinguishable from per-company exclusions.
- [ ] Long strings: URLs ellipsis `701`; title ellipsis + strike-through when not kept `743`; reason ellipsis `745`; include/exclude chips `704-705` no wrap control; pagination lines `725` no ellipsis.
- [ ] **In-progress state: only the button spinner** (`385`, `557`) — no modal/overlay while the synchronous test-scrape runs (can be tens of seconds for Playwright boards).

## 5. Hover styles

- [ ] `.v2-bd` (`T:152`, `border-color: var(--accent) !important`) — Seg options `99`, résumé chips `110`, Persona chip `113`, tier filter chips `276`, status pill `371`, Add-modal depth chips `644`.
- [ ] `.v2-act` (`T:147`, accent border + `var(--hover-soft)` bg) — `Make n active` `284`, Run `376`, Test `383`, ⋯ `387`, drawer Test scrape `556`.
- [ ] `.v2-bd-warn` (`T:153`, `border-color: var(--warn)`) — `Make n inactive` `288`.
- [ ] `.v2-hover-bad` (`T:130`, `var(--bad-soft)` bg) — URL row ✕ `82`, ⋯ Delete company `394`.
- [ ] `.v2-dashadd` (`T:145-146`, accent border/text + hover-soft bg, .12 s transition) — `+ Add another career page` `87`.
- [ ] `.v2-menuitem` (`T:148`, `var(--surface-2)` bg) — sort options `302`, ⋯ Edit `391`, Open career page `392`, View jobs `393`.
- [ ] `.v2-crow` (`T:149`, `var(--hover-soft)` bg) — company row `336`.
- [ ] `.v2-hover-accent` (`T:129`, surface-2 bg + text colour) — drawer ✕ `459`, test modal ✕ `696`.
- [ ] `.jn-v2 a:hover` (`T:121`, colour → `var(--text)`) — View jobs anchor `393`, test-row `↗` `746`.
- [ ] Inline `onMouseEnter`/`onMouseLeave`: **none** in this file. `style-hover`: none.
- [ ] `cursor:pointer` controls with **no hover treatment at all**: `+ Add company` `260`, Sort trigger `293`, `Clear filters` `405`, Scraper-tuning header `515`, drawer active toggle `555`, `Save changes` `560`, Add-modal `Cancel` `654` / `Save` `655`, `Show screenshots` `694`, test `Close` `670`/`755`.
- [ ] Spinner `.v2-spin` (`T:225-226`) at `379`, `385`, `557`; scrollbar `.v2-scroll` (`T:221-223`) at `252`, `298`, `316`, `462`, `608`, `730`.

## 6. Theme

- [ ] Dark mode is not read in this file. Shell reads `localStorage.jobnavigator_dark_mode` (`V2App.jsx:52`), toggles via `toggleTheme` (`V2App.jsx:54`), and stamps `data-theme="dark|light"` on the `.jn-v2` root (`V2App.jsx:90`); `theme.css:4` defines light tokens, `theme.css:74` (`.jn-v2[data-theme="dark"]`) overrides them. No `prefers-color-scheme` fallback.
- [ ] `.cc-*` chip classes: `atsSlug()` `22` emits `cc-greenhouse | cc-workday | cc-lever | cc-ashby | cc-phenom | cc-oraclehcm | cc-smartrecruiters | cc-rippling | cc-eightfold | cc-talentbrew | cc-meta | cc-google | cc-generic` (allow-list `ATS_SLUGS` `19`; rules `T:182-194`, tokens `T:36-48` light / `T:93-105` dark). `tierSlug()` `23` emits `cc-tier1 | cc-tier2 | cc-tier3 | cc-tiernone` (`T:195-198`, tokens `T:49-52` / `T:106-109`). Used at `79`, `346`, `357`, `612`.
- [ ] Colour literals (hex / rgb / hsl) in `Companies.jsx`: **none found**. Only the keyword `transparent` at `303` (sort item bg), `379`, `385`, `557` (spinner `borderTopColor`). Every other colour is a `var(--…)` token: `--accent --accent-soft --accent-ink --bad --bad-soft --warn --warn-soft --good --text --text-2 --muted --edge --line --line-soft --surface --surface-2 --bg --scrim --shadow-menu --shadow-drawer --shadow-modal --hover-soft` (the last via CSS classes).
- [ ] Add-modal ATS chip with empty URL uses `var(--surface-2)` / `var(--muted)` inline (`612`) instead of a `.cc-*` class.

## 7. Suspicious

- [ ] `useRef` imported at `1` — never used.
- [ ] `norm` helper defined at `16` — never used (the row filter re-implements lowercasing inline at `167-172`).
- [ ] `Seg` prop `big` (`93-94`) — never passed by any caller (`505`, `525`, `630`).
- [ ] `onDelete` prop passed to `Drawer` (`410`) and destructured (`418`) — never used; the drawer has no delete control.
- [ ] `console.error` at `137`, `196`, `204`, `215` — the only failure feedback for list load, status toggle, drawer save, Run, and Delete. No `console.log`, no TODO/FIXME.
- [ ] No toast at all: `Toast.jsx` is not imported; success feedback for Save / Add / Delete / Run / bulk is purely the list re-rendering. `window.confirm` (`214`) and `window.alert` (`587`, `598`) are native dialogs, off the v2 idiom.
- [ ] Client-side `detectAts` (`34-49`) diverges from backend `detect_scrape_type` (`RC:24-59`): client returns `Eightfold` (`45`) which the backend never emits → drawer/add chips say `EIGHTFOLD` while the row (backend `detected_scrape_types`) says `GENERIC`; client has no TalentBrew rule although `ATS_SLUGS` lists it (`19`) and the backend returns `TalentBrew AJAX` → row says `TALENTBREW`, drawer says `GENERIC`. Host/path heuristics for the other ATSs are not verified against the backend `is_*` predicates.
- [ ] `Needs attention` sort (`176`) and header `downCount` (`187`) use only `downMap`, while the row ▲ (`340`), health text (`228`) and drawer banner (`463`) also trigger on `last_error` — a company with a fresh error is neither counted nor sorted to the top.
- [ ] Alias badge shows `+{aliases.length-1}` only when `aliases.length > 1` (`342`) — a single alias is invisible in the row (tooltip lists all, so the `-1` looks like an off-by-one, not a "primary alias" rule).
- [ ] Add modal posts `aliases` (`592`) and `auto_scoring_depth` (`595`), but backend `create_company` (`RC:188-205`) never passes either to the `Company(...)` constructor → aliases are lost and the depth chip (default `Light`) is not persisted on create. (Only a subsequent drawer Save writes them, via PATCH's allow-list `RC:225-230`.)
- [ ] Drawer `Save changes` closes the drawer synchronously (`449`) before the PATCH resolves; a 4xx/5xx is invisible.
- [ ] Drawer footer active toggle (`555`) PATCHes immediately (not part of Save), and the `company` object held in `drawer.company` is never refreshed after `fetchCompanies`, so subtitle / banner / `application_count` / `last_error` go stale while the drawer stays open.
- [ ] Run uses a fixed 2600 ms timer (`205`) instead of polling `/monitor/active`; the "scraping now…" health text and `Running` label disappear after 2.6 s regardless of the real run, and a 409 duplicate still shows the spinner. `/health/entities` and `/monitor/active` are fetched once on mount (`143-144`) and never refreshed.
- [ ] `scraping` map (`144`) is keyed by every running job's `scope_key`, including `analyze_job` scopes (`M:429-433`) — harmless today but not company-scoped.
- [ ] `⋯ → View jobs in feed` is a raw `<a href>` (`393`) → full SPA reload; and the `?company=` param is not read by `JobFeed.jsx` (`179`, `476`, `490`) → arrives at an unfiltered feed.
- [ ] `⋯ → Open n career pages` loops `window.open` (`392`) — popup blockers allow one.
- [ ] `TestModal` ignores backend fields `passes_company_filter`, `global_excluded_by` (`RC:559-561`), `after_company_filter`, `global_exclude_keyword_count` (`RC:581-584`); global-exclude rows are undifferentiated `Out`.
- [ ] `TestModal` summary maths (`679`): `keyword-filtered = found − kept − rejected`, but `found = total_found = len(all_jobs)` already excludes rejected (`RC:582-583`) → keyword-filtered is under-reported by `total_rejected` whenever any rows were validation-rejected; and "{found} extracted" is smaller than the number of rows in the table (rows = `total_found + total_rejected`, `RC:546-571`).
- [ ] Add-modal `Save` remains clickable while `saving` (`655`, no guard in `586`) → possible double POST (second returns 409 → alert).
- [ ] `max_pages` `min/max` are HTML attributes only (`540`); `save` does `parseInt || 5` (`446`) with no clamp — `0`, negatives, `999` pass through (0 → 5).
- [ ] `scrape_interval_minutes` `parseInt(x) || null` (`444`, `594`) — an explicit `0` becomes `null` (global). Probably intended, but differs from Searches' "0 = use global" convention.
- [ ] `UrlEditor` rows keyed by index (`78`) — removing a middle URL re-keys inputs; focus/IME state may jump.
- [ ] `Escape` (`153`) closes the drawer and add modal discarding edits with no confirm; clicking another row while the drawer is open silently replaces the draft (`336` → `236`).
- [ ] Column header tooltip "Open applications" (`324`) and drawer subtitle "open application(s)" (`427`) describe `application_count`, which counts ALL applications + applied jobs (`RC:96-113`), not open ones.
- [ ] `h1b_approval_rate` rendered as `${rate}% approved` (`429`) with no scale check — if the cache stores a 0–1 fraction this prints "0.95% approved" (unverified).
- [ ] `resumeNames()` (`219-225`) silently drops `selected_resume_ids` that are not base résumés (deleted / tailored ids) — cell shows `Selected` only when NONE resolve; partial matches hide the dangling ids.
- [ ] Health "scraped {ago}" (`230-231`) uses `Company.last_scraped_at`, while the drawer banner (`468`) uses `last_run_at || last_scraped_at` (latest `ScrapeLog.ran_at`) — two clocks for "last run".
- [ ] Stacking: drawer is `zIndex: 30` (`453`) but the row ⋯ menu is `40` (`390`) and the sort menu `45` (`298`), so an open row/sort menu paints over the drawer if both are open (Escape closes all; the ⋯ click never reaches the document listener because of the `375` stopPropagation, so the menu can stay open while the drawer is opened via `Edit config` `391` — that item does call `setMenuId(null)`, but the row-click path `336` does not).

## 8. Counts that must agree

- [ ] Header `{n} tracked` (`188`, `companies.length` from GET `/companies`) == rail badge next to "Companies" (`V2App.jsx:61`, separate GET `/companies`, `data.length`) == sum of the four tier-chip counts (`160-164`, `278`). Tier counts ignore the search/tier filter by design.
- [ ] Header `{n} active` (`186`) == `Make {n} inactive` button count (`289`) when no search/tier filter is set; with a filter the button uses `activeInFilter` (`190`) and the tooltip `bulkHint` (`191-193`) reports `filtered.length`.
- [ ] Header `{n} need attention` (`187`, companies in `downMap`) == rail amber-dot/`warn.companies` (`V2App.jsx:66`, `health.companies.length`) == the companies share of rail text "N sources need attention" (`V2App.jsx:78-79`, companies + searches) == Stats `failing` (`Stats.jsx:115`). NOT equal to the number of rows showing ▲ (which adds `last_error`, `340`).
- [ ] Row `scraping now…` set (`227`) == entries of GET `/monitor/active` with `job_type = company_scrape` (`scope_key = company id`, `M:670`) at mount time — Searches screen reads the same endpoint (`Searches.jsx:320`).
- [ ] `Open` column = `open_jobs` (`RC:128-134`, `Job.status IN ('new','saved')` grouped by normalised `Job.company`, summed over name + aliases `RC:146-147`). Compare with the Feed's company filter counts (GET `/jobs/companies/list?counts=1`, `JobFeed.jsx:197`) and with the Feed filtered to that company + status new/saved. Tooltip `362` calls these "open roles … in the Job Feed".
- [ ] `+7d` = `open_jobs_week` (`RC:137-143`, `discovered_at >= now−7d`, ANY status) — can exceed `Open`; tooltip (`323`, `362`) says "new in the last 7 days". Compare with Stats' jobs-discovered timeline last-7-day sum for that company.
- [ ] `Apps` = `application_count` (`RC:96-113`, UNION of `Application.job_id` and `Job.status='applied'`, grouped by normalised `Job.company`, looked up by `c.name` ONLY at `RC:177` — aliases are NOT summed, unlike Open/Fit). Compare with Applications screen per-company counts and rail `apps` (`V2App.jsx:60`). Drawer subtitle `427` shows the same number.
- [ ] `Ø Fit` = `avg_fit` (`RC:145-154`, `round(sum(best_cv_score)/count)` over name + aliases, all statuses). Compare with per-job scores in the Feed for that company and with the Stats score-distribution `avg` (`M:1184-1196`, which averages `max(cv_scores)` per job — a different column, `cv_scores` vs `best_cv_score`).
- [ ] Résumés cell names (`219-225`) resolve `selected_resume_ids` against GET `/resumes?is_base=true` (`141`) — must match the Résumés screen's base list and the chips offered in the drawer/add modal (`106-116`).
- [ ] Drawer H-1B line `{n} filings … {rate}% approved` (`429`) from `VisaCache` (`RC:116-118`, keyed by lowercased name, US only) — compare with the H-1B verdict shown on that company's jobs in the Feed and the classic Company Manager.
- [ ] Row ATS chip (backend `detected_scrape_types[urls[0]]`, `RC:601`) vs drawer/add live chip (client `detectAts`, `34-49`) — must agree for every URL (known divergences: Eightfold, TalentBrew — §7).
- [ ] Drawer subtitle `{k} career URL(s)` (`427`, non-empty drafts) == row `+{n}` (`358`, `urls.length − 1`) + 1 before edits.
- [ ] Test modal summary (`679`): `kept` == number of `Kept` rows; `validation-rejected` == number of `Drop` rows; `extracted` == `Kept + Out` rows (NOT the total row count); `keyword-filtered` == `Out` rows only when `total_rejected == 0` (see §7).
- [ ] Test modal "URLs scraped · {n}" (`700`) == number of `scrape_urls` on the company (backend appends one entry per URL, including error entries `RC:436-515`).

---

**Summary**
- Interactive elements catalogued: 109 (header 1, toolbar 15, column headers 1 group, per-row 22 incl. 4 menu items, empty-state 1, drawer 34, add modal 16, test modal 8, plus keyboard/outside-click handlers).
- API endpoints used: 10 (GET /companies, GET /resumes, GET /persona, GET /health/entities, GET /monitor/active, POST /companies, PATCH /companies/{id}, DELETE /companies/{id}, POST /companies/{id}/test-scrape, POST /scrape/company/{id}).
- Uncaught failure paths: 0 strictly uncaught; 9 are caught-but-silent (console.error or empty catch: list load, résumés, persona, health, monitor, status toggle/drawer save, bulk per-item, Run, Delete) — only Test (error modal) and Add (native alert) surface failures.
- Missing empty/error branches: 10 (list loading, list load error, first-run "no companies", never-scraped health variant, last-run-warning variant, résumé chips with zero résumés, URL editor with zero URLs, drawer save pending/failed, Run failed/409, test-scrape in-progress overlay).
- Suspicious items: 28.
