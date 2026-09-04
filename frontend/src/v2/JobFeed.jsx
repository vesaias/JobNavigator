import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import ConfirmDialog from './ConfirmDialog'
import { useEscape, useSettled, useWarm, NBSP } from './hooks'
import { Button, Card, Check as UICheck, FooterRow, GlyphBadge, Heading, HeaderRow, Helper, Input, kb, Label, Link, Menu, MenuItem, Meter, ModalPanel, NavLink, PageTitle, Pill, Row, Rule, ScoreRing, SearchInput, SectionHead, Segmented, Spinner, TableHead, TableRow } from './ui'

const FILTERS_KEY = 'v2_feed_filters'
const SORT_KEY = 'v2_feed_sort'
const UI_KEY = 'v2_feed_ui'   // persisted panel open/collapse prefs
const loadUI = () => { try { return JSON.parse(localStorage.getItem(UI_KEY)) || {} } catch { return {} } }
// The board's whole-top collapse ("JobNavigator Redesign.dc.html" §Feed, l.252-255,
// l.301, l.1403-1404 and l.1732-1741): an 11px grab-line above the detail header
// folds the ENTIRE top of the right side away — the metadata header AND the
// score/report band together — so the posting frame rises to the top of the panel.
// It is its own key, `jn_feed_analysis_collapsed` ('1'/'0'), exactly as the board
// names it, and it is deliberately NOT part of the UI_KEY blob: the board reads it
// straight from localStorage, and it survives both reloads and job selection (the
// board's select handler, l.1545, resets report/menuFor/headMenu/checked/
// filterOpen/viewCached — never this).
const ANA_KEY = 'jn_feed_analysis_collapsed'
const loadAnaCollapsed = () => { try { return localStorage.getItem(ANA_KEY) === '1' } catch { return false } }
// F4: per-host frame-check results ({host: 1 embeddable | 0 blocked}). The probe
// is a server-side fetch of the posting (measured 0.8–1.9 s on a cold host), and
// v2 used to mount nothing until it answered — v1 never probed at all. A host we
// have already asked about answers from here, instantly; an unknown host renders
// the live frame optimistically and only swaps to the "refuses to be framed"
// panel if its probe comes back blocked.
const FRAME_KEY = 'v2_feed_frameable'
const FRAME_CACHE_MAX = 300
// F7: how long the live frame may stay under the loading cover before the pane
// gives up on it and shows the "refuses to be framed" panel instead.
const FRAME_LOAD_MS = 8000
// The grab-line fold runs at .12s (theme.css `.v2-fold`, the board's own timing);
// this is that travel plus slack, the window the wrapper clips for.
const FOLD_MS = 200
const loadFrameCache = () => { try { return JSON.parse(localStorage.getItem(FRAME_KEY)) || {} } catch { return {} } }
const hostOf = (u) => { try { return new URL(u, window.location.origin).host } catch { return '' } }

// ── helpers ──────────────────────────────────────────────────────────────
const timeAgo = (s) => {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
const isToday = (s) => s && (Date.now() - new Date(s).getTime()) < 86400000
const scoreEntries = (j) => Object.entries(j.cv_scores || {}).filter(([, v]) => typeof v === 'number')
const bestScore = (j) => { const e = scoreEntries(j); return e.length ? Math.max(...e.map(([, v]) => v)) : 0 }
const scoredCount = (j) => scoreEntries(j).length
const isTailoredName = (n) => n === 'Tailored'
const fmtSalary = (min, max) => {
  if (!min && !max) return null
  const f = (v) => `$${Math.round(v / 1000)}K`
  return min && max && min !== max ? `${f(min)} - ${f(max)}` : f(min || max)
}
const H1B = {
  likely: { label: 'H-1B Likely', c: 'var(--good)' },
  possible: { label: 'H-1B Possible', c: 'var(--muted)' },
  unlikely: { label: 'H-1B Unlikely', c: 'var(--warn)' },
  unknown: { label: 'H-1B Unknown', c: 'var(--muted)' },
}
const BADGE = {
  applied: { label: 'Applied', bd: 'var(--accent)', bg: 'var(--accent-soft)', fg: 'var(--accent)' },
  saved: { label: 'Saved', bd: 'var(--warn)', bg: 'var(--warn-soft)', fg: 'var(--warn)' },
  skip: { label: 'Skipped', bd: 'var(--line)', bg: 'transparent', fg: 'var(--muted)' },
  ignored: { label: 'Ignored', bd: 'var(--line)', bg: 'transparent', fg: 'var(--muted)' },
}
// ui: keep — the bulk bar's on-rail controls: --rail-ink on an --on-rail-line
// hairline, drawn over the dark --rail bar. Pill and Button paint for light
// surfaces, so these keep their own look — one object so they cannot drift.
const RAIL_BTN = {
  height: 27, padding: '0 11px', border: '1px solid var(--on-rail-line)', borderRadius: 'var(--radius-control)',
  display: 'flex', alignItems: 'center', fontSize: 11.5, color: 'var(--rail-ink)', cursor: 'pointer',
}
const SOURCE_LABELS = {
  direct: 'Direct', extension: 'Extension', jobspy_linkedin: 'LinkedIn', jobspy_indeed: 'Indeed',
  jobspy_zip_recruiter: 'ZipRecruiter', jobspy_google: 'Google', levels_fyi: 'Levels', linkedin_personal: 'LinkedIn Personal',
  linkedin_extension: 'LinkedIn Extension', jobright: 'Jobright', freehire: 'FreeHire', playwright_url: 'Company careers', playwright_direct: 'Career page',
}
const srcLabel = (s) => SOURCE_LABELS[s] || s || ''
const STATUS_OPTS = [['new', 'New'], ['saved', 'Saved'], ['applied', 'Applied'], ['skip', 'Skip'], ['ignored', 'Ignored']]
const SORT_OPTS = [['score', 'Top score'], ['date', 'Newest first'], ['salary', 'Salary, high to low'], ['company', 'Company A–Z']]
const DEFAULTS = { status: [], company: [], source: [], h1b_verdict: [], min_score: '', min_salary: '', max_salary: '' }

// small dropdown shell (trigger pill + panel + backdrop). Flips to right-align
// when the panel would overflow the viewport's right edge.
//
// D-POST-15: every Drop panel is a `Menu` (padding 5). A *list* popup (Source,
// Company, H-1B, Status, Sort) gets its inner room from MenuItem's `7px 11px`,
// so its text sits 17px in from the panel's outer edge; the popups whose body is
// a row of fields (Score >=, Salary) had no such inset and their content sat at
// the panel's bare 6px, which read as cramped next to the list menus. `inset`
// wraps such a body in the same 11px gutter, so all six popups share one inner
// geometry. Measured before -> after (content left, from the panel's border):
// Score/Salary 6 -> 17, list menus unchanged at 17.
function Drop({ label, active, open, onToggle, children, width = 216, trigger, onClear, inset }) {
  const ref = useRef(null)
  const [pos, setPos] = useState(null)
  useLayoutEffect(() => {
    if (!open || !ref.current) { setPos(null); return }
    const r = ref.current.getBoundingClientRect()
    // fixed positioning escapes the list/detail clip; flip left when it would
    // overflow the right edge, and keep it on-screen
    const left = (r.left + width > window.innerWidth - 12) ? Math.max(8, r.right - width) : r.left
    setPos({ left, top: r.bottom + 5 })
  }, [open, width])
  return (
    <div ref={ref} style={{ position: 'relative', flex: '0 0 auto' }}>
      {trigger ? trigger(onToggle) : (
        <Pill on={active} onClick={onToggle} ariaExpanded={open} ariaHaspopup="menu">
          {label}
          {active && onClear
            ? <span onClick={(e) => { e.stopPropagation(); onClear() }} title="Clear" style={{ fontSize: 11, opacity: 0.7 }}>✕</span>
            : <span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>}
        </Pill>
      )}
      {open && pos && (
        <>
          <div onClick={onToggle} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
          <Menu className="v2-scroll" style={{ position: 'fixed', left: pos.left, top: pos.top, zIndex: 45, width, maxHeight: 360, overflowY: 'auto', overflowX: 'hidden', boxSizing: 'border-box' }}>
            {inset ? <div style={{ padding: '6px 11px' }}>{children}</div> : children}
          </Menu>
        </>
      )}
    </div>
  )
}
function Check({ on, label, count, onClick }) {
  return (
    <MenuItem ellipsis onClick={onClick} hint={count} hintMono
      icon={<UICheck checked={on} />}>
      {label}
    </MenuItem>
  )
}

// pick modifier: ⌘ on macOS, Ctrl elsewhere (matches rowClick's metaKey||ctrlKey)
const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || '')
const PICK_KEY = IS_MAC ? '⌘' : 'Ctrl'
const SHORTCUTS = [['j / f / ↓', 'Next job'], ['k / g / ↑', 'Previous job'], ['s', 'Save / unsave'], ['x', 'Skip'], ['a', 'Mark applied'], ['e / o', 'Open posting'], ['r', 'Rescore'], ['t', 'Tailor résumé'], ['c', 'Cover letter'], ['Esc', 'Close menus'], [`${PICK_KEY}-click`, 'Select'], ['Shift-click', 'Select range']]

// ── component ────────────────────────────────────────────────────────────
export default function V2JobFeed() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [firstLoaded, setFirstLoaded] = useState(false)   // DESIGN-LOAD: the first /jobs page has answered
  const [loadError, setLoadError] = useState(false)   // FEED-11: a failed list is not an empty one
  const [filters, setFilters] = useState(() => {
    let f = DEFAULTS
    try { const s = JSON.parse(localStorage.getItem(FILTERS_KEY)); if (s) f = { ...DEFAULTS, ...s } } catch {}
    // ?company=<name> scopes the feed to one company (from Companies → View in feed)
    try { const c = new URLSearchParams(window.location.search).get('company'); if (c) f = { ...f, company: [c] } } catch {}
    return f
  })
  const [sortBy, setSortBy] = useState(() => { try { return localStorage.getItem(SORT_KEY) || 'score' } catch { return 'score' } })
  useEffect(() => { try { localStorage.setItem(FILTERS_KEY, JSON.stringify(filters)) } catch {} }, [filters])
  useEffect(() => { try { localStorage.setItem(SORT_KEY, sortBy) } catch {} }, [sortBy])
  const [search, setSearch] = useState('')
  const [dSearch, setDSearch] = useState('')
  const [menu, setMenu] = useState(null)
  const [companyQuery, setCompanyQuery] = useState('')
  useEffect(() => { if (menu !== 'company') setCompanyQuery('') }, [menu])   // FEED-32

  const [sel, setSel] = useState(0)
  const [detail, setDetail] = useState(null)
  const [confirm, setConfirm] = useState(null)   // R2-A-01: the shared destructive-confirm dialog
  const [headOpen, setHeadOpen] = useState(() => loadUI().headOpen ?? true)
  // whole-top collapse (header + score/report band). Its own key, its own effect:
  // the board persists it on its own, outside the panel-prefs blob.
  const [anaCollapsed, setAnaCollapsed] = useState(loadAnaCollapsed)
  useEffect(() => { try { localStorage.setItem(ANA_KEY, anaCollapsed ? '1' : '0') } catch {} }, [anaCollapsed])
  // The fold animates (theme.css `.v2-fold`), so for the length of the travel the
  // wrapper has to clip — and only then: left clipping, it would cut the header's
  // ⋯ menu, which hangs below the header on top:100%.
  const [folding, setFolding] = useState(false)
  const toggleAna = useCallback(() => { setFolding(true); setAnaCollapsed((v) => !v) }, [])
  useEffect(() => {
    if (!folding) return
    const t = setTimeout(() => setFolding(false), FOLD_MS)
    return () => clearTimeout(t)
  }, [folding, anaCollapsed])
  const [reportOpen, setReportOpen] = useState(() => loadUI().reportOpen ?? false)
  const [reportTab, setReportTab] = useState(0)   // per-job: reports differ per résumé, so this resets
  const [reqFilter, setReqFilter] = useState(() => loadUI().reqFilter ?? 'all')
  const [showMatched, setShowMatched] = useState(() => loadUI().showMatched ?? false)
  const [breakdownOpen, setBreakdownOpen] = useState(() => loadUI().breakdownOpen ?? false)
  const [keywordOpen, setKeywordOpen] = useState(() => loadUI().keywordOpen ?? false)
  const [reqOpen, setReqOpen] = useState(() => loadUI().reqOpen ?? false)
  useEffect(() => { try { localStorage.setItem(UI_KEY, JSON.stringify({ headOpen, reportOpen, breakdownOpen, keywordOpen, reqOpen, reqFilter, showMatched })) } catch {} }, [headOpen, reportOpen, breakdownOpen, keywordOpen, reqOpen, reqFilter, showMatched])
  const [viewCached, setViewCached] = useState(false)
  const [cachedHtml, setCachedHtml] = useState(null)
  const [frameOk, setFrameOk] = useState(true)          // true=render the live frame, false=known-blocked (extension off)
  // F7: changing `src` on one long-lived <iframe> keeps the OLD document on
  // screen until the new one paints, so switching jobs showed the previous
  // posting for as long as the next one took. The frame is remounted per job
  // instead (key), which tears the old document down at once, and these two
  // hold job ids so a fast j/k run can only ever act on the newest job:
  //   frameLoadId — its frame is still loading (the neutral cover is up)
  //   frameDeadId — its frame never fired load inside FRAME_LOAD_MS, so the pane
  //                 falls through to the existing "refuses to be framed" panel
  const [frameLoadId, setFrameLoadId] = useState(null)
  const [frameDeadId, setFrameDeadId] = useState(null)
  const frameDoneRef = useRef(false)                    // did the mounted frame settle (load or error)?
  const frameCache = useRef(loadFrameCache())
  // what to show the moment a job is selected: the fallback panel only for a host
  // we have already measured as blocked; everything else tries the frame at once
  const frameGuess = useCallback((url) => frameCache.current[hostOf(url)] !== 0, [])
  // The Navigator extension marks the page (data-jn-ext) once its content script
  // runs; its declarativeNetRequest rules strip X-Frame-Options so postings embed.
  // Without it, cross-origin postings (Ashby, Workday, …) return "refused to connect".
  const [extActive, setExtActive] = useState(() => { try { return !!document.documentElement.getAttribute('data-jn-ext') } catch { return false } })
  useEffect(() => {
    if (extActive) return
    let n = 0
    const id = setInterval(() => {
      try { if (document.documentElement.getAttribute('data-jn-ext')) { setExtActive(true); clearInterval(id) } } catch {}
      if (++n > 10) clearInterval(id)   // stop after ~2s; content script sets it at document_idle
    }, 200)
    return () => clearInterval(id)
  }, [extActive])

  const [companyList, setCompanyList] = useState([])
  const [sourceList, setSourceList] = useState([])
  const [sourceCounts, setSourceCounts] = useState({}); const [verdictCounts, setVerdictCounts] = useState({})   // FEED-26
  const [verdictList, setVerdictList] = useState([])
  const [resumes, setResumes] = useState([])
  const [stats, setStats] = useState({ arrived_today: 0, unscored: 0 })
  const [picker, setPicker] = useState(null)      // {mode, jobs:[...]} — opens the Create-copy modal
  const [cvMode, setCvMode] = useState('tailor')  // 'tailor' | 'copy' method toggle
  const [cvBase, setCvBase] = useState(null)      // selected base résumé id (or 'persona')
  const [rowMenu, setRowMenu] = useState(null)
  const [headMenu, setHeadMenu] = useState(false)
  const [checked, setChecked] = useState(() => new Set())
  const lastIdx = useRef(null)

  const [personaAvailable, setPersonaAvailable] = useState(false)
  // OPEN-10: the one-click SCORE pill used to post ?depth=full unconditionally,
  // so the first thing a new user clicks always spends the expensive call. The
  // Light/Full choice behind `r` / ⋯ → Rescore is unchanged; this is only the
  // default the no-choice paths use. Light until Settings says otherwise.
  const [defaultDepth, setDefaultDepth] = useState('light')
  const [watchExtra, setWatchExtra] = useState([])   // ids of jobs pruned from view but still processing
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)   // FEED-38
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [rescoreJob, setRescoreJob] = useState(null)
  const [rescoreOpts, setRescoreOpts] = useState([])
  const [rescoreSel, setRescoreSel] = useState([])
  const [rescoreDepth, setRescoreDepth] = useState('full')
  const scoreWatchRef = useRef([])
  const pendingRef = useRef({})   // {jobId:{title,company}} → completion toast
  const seenActiveRef = useRef(new Set())   // jobs confirmed in-flight (avoids first-tick false completion)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  // ?search=<id> scopes the feed to one saved search (from Searches → View results in feed)
  const [searchId, setSearchId] = useState(() => { try { return new URLSearchParams(window.location.search).get('search') || '' } catch { return '' } })
  const [searchName, setSearchName] = useState('')
  useEffect(() => {
    if (!searchId) { setSearchName(''); return }
    api.get('/searches').then(({ data }) => setSearchName((data || []).find((s) => String(s.id) === String(searchId))?.name || 'search')).catch(() => setSearchName('search'))
  }, [searchId])
  const PAGE = 40

  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  const listRef = useRef(null)
  const jobsRef = useRef(jobs); useEffect(() => { jobsRef.current = jobs }, [jobs])
  const selRef = useRef(sel); useEffect(() => { selRef.current = sel }, [sel])
  const detailRef = useRef(detail); useEffect(() => { detailRef.current = detail }, [detail])
  const pinnedRef = useRef(null)   // job id opened via ?job=, held until the user picks from the list
  const deadPinRef = useRef(false) // a ?job= id that 404s: keep the panel empty instead of focusing an unrelated job (FEED-09)

  useEffect(() => { const t = setTimeout(() => setDSearch(search), 400); return () => clearTimeout(t) }, [search])
  // FEED-33: the Score / Salary boxes commit 400 ms after the last keystroke, like the title search
  const [numDraft, setNumDraft] = useState({ min_score: filters.min_score, min_salary: filters.min_salary, max_salary: filters.max_salary })
  useEffect(() => { setNumDraft({ min_score: filters.min_score, min_salary: filters.min_salary, max_salary: filters.max_salary }) }, [filters.min_score, filters.min_salary, filters.max_salary])
  const numTimer = useRef(null)
  const setNum = (key, v) => { setNumDraft((p) => ({ ...p, [key]: v })); clearTimeout(numTimer.current); numTimer.current = setTimeout(() => setF({ [key]: v }), 400) }
  // DESIGN-LOAD: the five screen-level facets settle as one. The subtitle's three
  // counters and the "Score N unscored jobs" button hang off /jobs/feed-stats, and
  // the Source / H-1B menus off their two lists — drawn as they arrived, the
  // header read "0 open roles · 0 arrived today" for a beat on every visit.
  const { ready: facetsReady } = useSettled([
    () => api.get('/jobs/companies/list', { params: { counts: 1 } }).then(({ data }) => setCompanyList(data || [])).catch(() => { /* silent: a filter facet — the list itself has FEED-11's error state */ }),
    () => api.get('/jobs/sources/list', { params: { counts: 1 } }).then(({ data }) => { setSourceList((data || []).map((x) => x.name ?? x)); setSourceCounts(Object.fromEntries((data || []).filter((x) => x && x.name != null).map((x) => [x.name, x.count]))) }).catch(() => { /* silent: a filter facet */ }),   // FEED-26
    () => api.get('/jobs/verdicts/list', { params: { counts: 1 } }).then(({ data }) => { setVerdictList((data || []).map((x) => x.name ?? x)); setVerdictCounts(Object.fromEntries((data || []).filter((x) => x && x.name != null).map((x) => [x.name, x.count]))) }).catch(() => { /* silent: a filter facet */ }),
    () => api.get('/resumes?is_base=true').then(({ data }) => setResumes(data || [])).catch(() => { /* silent: only names the résumés in the score modal; scoring reports its own failures */ }),
    () => api.get('/jobs/feed-stats').then(({ data }) => setStats(data)).catch(() => { /* silent: the header counters; refreshStats re-runs them after every action */ }),
  ])
  const refreshStats = useCallback(() => { api.get('/jobs/feed-stats').then(({ data }) => setStats(data)).catch(() => { /* silent: the header counters; re-fetched after every action anyway */ }) }, [])

  // Warm start. The subtitle's three counters, the unscored button and the two
  // facet option lists are the same on the frame after a refresh as they were
  // before it, so they paint from the cache and reconcile (with the rail's .15s
  // fade) once the facets AND the first page of jobs have both answered.
  const headReady = facetsReady && firstLoaded
  const { warm: head, style: headStyle } = useWarm('feed', headReady
    ? { total, arrived: stats.arrived_today, unscored: stats.unscored, sources: sourceList, sourceCounts, verdicts: verdictList, verdictCounts }
    : null, headReady)
  const facetSources = (head && head.sources) || []
  const facetSourceCounts = (head && head.sourceCounts) || {}
  const facetVerdicts = (head && head.verdicts) || []
  const facetVerdictCounts = (head && head.verdictCounts) || {}

  const buildParams = useCallback((off) => {
    const p = { limit: PAGE, offset: off }
    // FEED-01: the default view is the OPEN set (new + saved); skipped/applied/ignored need an explicit Status filter
    p.status = filters.status.length ? filters.status.join(',') : 'new,saved'
    if (filters.company.length) p.company = filters.company.join(',')
    if (filters.source.length) p.source = filters.source.join(',')
    if (filters.h1b_verdict.length) p.h1b_verdict = filters.h1b_verdict.join(',')
    if (filters.min_score !== '') p.min_score = filters.min_score
    if (filters.min_salary) p.min_salary = Number(filters.min_salary) * 1000
    if (filters.max_salary) p.max_salary = Number(filters.max_salary) * 1000
    if (dSearch) p.title_search = dSearch
    if (searchId) p.search_id = searchId
    if (sortBy !== 'date') p.sort_by = sortBy
    return p
  }, [filters, sortBy, dSearch, searchId])

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/jobs', { params: buildParams(0) })
      const n = (data.jobs || []).length
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
      setOffset(n)
      setHasMore(n < (data.total || 0))
      setLoadError(false)
    } catch (e) {
      console.error('v2 feed load failed', e)
      setLoadError(true)
      if (e?.response?.status !== 401) pushToast({ kind: 'error', msg: "Couldn't load jobs" })   // a 401 opens the shell's login modal instead
    }
    setLoading(false)
    setFirstLoaded(true)   // DESIGN-LOAD: the header's `total` is real from here on
  }, [buildParams, pushToast])
  useEffect(() => { fetchJobs() }, [fetchJobs])

  // append next page (infinite scroll + refill after triage drains the list)
  const loadingMoreRef = useRef(false)
  const offsetRef = useRef(offset); useEffect(() => { offsetRef.current = offset }, [offset])
  const hasMoreRef = useRef(hasMore); useEffect(() => { hasMoreRef.current = hasMore }, [hasMore])
  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current || !hasMoreRef.current) return
    loadingMoreRef.current = true; setLoadingMore(true)
    try {
      const off = offsetRef.current
      const { data } = await api.get('/jobs', { params: buildParams(off) })
      const fetched = data.jobs || []
      setJobs((prev) => { const seen = new Set(prev.map((j) => j.id)); const fresh = fetched.filter((j) => !seen.has(j.id)); return fresh.length ? [...prev, ...fresh] : prev })
      setTotal(data.total || 0)
      setOffset(off + fetched.length)
      setHasMore(off + fetched.length < (data.total || 0) && fetched.length > 0)
    } catch (e) { console.error('load more failed', e) }
    loadingMoreRef.current = false; setLoadingMore(false)
  }, [buildParams])
  const onListScroll = useCallback((e) => {
    const el = e.currentTarget
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 320) loadMore()
  }, [loadMore])

  // open one job in the detail panel. `idx` is its row index in the list that is
  // (or is about to be) on screen — the advance after a triage action passes the
  // index the row will have once the acted-on rows are gone.
  const focusJob = useCallback((j, idx) => {
    pinnedRef.current = null                 // picking from the list releases a ?job= pin
    deadPinRef.current = false
    setSel(idx); lastIdx.current = idx
    setDetail(j); setReportTab(0); setViewCached(false); setCachedHtml(null); setFrameOk(frameGuess(j.url)); setFrameDeadId(null)
    api.get(`/jobs/${j.id}`).then(({ data }) => setDetail((c) => (c && c.id === data.id ? data : c))).catch(() => { /* silent: a background refresh of an already-rendered panel — the row data stays */ })
  }, [frameGuess])
  const focusAt = useCallback((idx) => {
    const list = jobsRef.current
    if (idx < 0 || idx >= list.length) return
    focusJob(list[idx], idx)
  }, [focusJob])
  useEffect(() => {
    if (loading) return
    if (jobs.length === 0) { setDetail(null); return }
    // keep the current/deep-linked detail if it's still in the list (align focus);
    // otherwise focus the top of the (re)loaded list
    const curId = detailRef.current?.id
    const idx = curId ? jobs.findIndex((j) => j.id === curId) : -1
    if (idx >= 0) setSel(idx)
    // a ?job= permalink owns the panel until the user picks from the list — it stays
    // open even when that job isn't in the list (applied/skipped jobs are filtered
    // out of the default feed), and holds while its fetch is still in flight
    else if (pinnedRef.current || deadPinRef.current) setSel(-1)
    else focusAt(Math.min(sel, jobs.length - 1))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, loading])

  // an empty status filter means "the open feed" (new + saved), so skipping or
  // applying a job drops it from the list + counts, same as under an explicit filter
  const openStatusRef = useRef(filters.status)
  useEffect(() => { openStatusRef.current = filters.status }, [filters.status])
  const leavesView = useCallback((status) => {
    if (!status) return false
    const openSet = openStatusRef.current.length ? openStatusRef.current : ['new', 'saved']
    return !openSet.includes(status)
  }, [])
  // F3/F5: one local write for one row or a whole bulk set. When the rows leave
  // the current view they go now — and, if the open job was one of them, the
  // panel moves to the next surviving row in the same tick (the `s`/`x` advance).
  // Before, the click path left the row's replacement to the [jobs] effect, which
  // hands the panel to a ?job= pin instead whenever one is still held (measured:
  // detail + ?job= still on the skipped job 3 s after the click).
  const patchLocalMany = useCallback((ids, changes) => {
    const idSet = new Set(ids)
    if (leavesView(changes.status)) {
      const list = jobsRef.current
      const gone = list.filter((j) => idSet.has(j.id)).length
      const remaining = list.filter((j) => !idSet.has(j.id))
      setJobs((prev) => prev.filter((j) => !idSet.has(j.id)))
      setTotal((t) => Math.max(0, t - gone))
      if (remaining.length < 12) loadMore()
      const cur = detailRef.current
      if (cur && idSet.has(cur.id)) {
        const i = list.findIndex((j) => j.id === cur.id)
        const next = list.slice(i + 1).find((j) => !idSet.has(j.id))
          || [...list.slice(0, Math.max(0, i))].reverse().find((j) => !idSet.has(j.id))
          || null
        if (next) focusJob(next, remaining.findIndex((j) => j.id === next.id))
        else { pinnedRef.current = null; deadPinRef.current = false; setSel(-1); setDetail(null) }
      }
      return
    }
    setJobs((prev) => prev.map((j) => (idSet.has(j.id) ? { ...j, ...changes } : j)))
    setDetail((d) => (d && idSet.has(d.id) ? { ...d, ...changes } : d))
  }, [leavesView, loadMore, focusJob])
  const patchLocal = useCallback((id, changes) => patchLocalMany([id], changes), [patchLocalMany])
  const patchRemote = useCallback(async (job, changes) => {
    patchLocal(job.id, changes)
    // FEED-07: report the outcome so callers only announce success once the PATCH
    // lands. R2-H-05: the body is handed back too — an "applied" PATCH reports the
    // Application/Company it created, which Undo needs.
    try { const { data } = await api.patch(`/jobs/${job.id}`, changes); refreshStats(); return data || true }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Couldn't update "${job.title}"` }); fetchJobs(); return false }
  }, [patchLocal, fetchJobs, refreshStats, pushToast])
  const watchForScore = useCallback((id) => {
    if (id && !scoreWatchRef.current.some((w) => w.id === id)) scoreWatchRef.current = [...scoreWatchRef.current, { id, until: Date.now() + 90000 }]
  }, [])
  // R2-H-05: "Applied" is compound — the PATCH also creates an Application and,
  // for an unknown company, a Company row. `created` carries the ids the backend
  // reports for exactly those two, so Undo takes them back out; a job that already
  // had an application (or a known company) reports nothing and nothing is deleted.
  const showUndo = useCallback((job, prevStatus, prevSaved, msg, created) => {
    pushToast({ kind: 'undo', msg, action: 'Undo', onAction: async () => {
      try {
        // the application first: DELETE releases its job back to `saved`, so the
        // status PATCH has to be the last word on the job's status
        if (created?.appId) await api.delete(`/applications/${created.appId}`)
        if (created?.coId) await api.delete(`/companies/${created.coId}`)
        await api.patch(`/jobs/${job.id}`, { status: prevStatus, saved: prevSaved })
        fetchJobs(); refreshStats()
        if (created?.appId || created?.coId) {
          pushToast({ kind: 'success', msg: 'Application removed' })
          window.dispatchEvent(new CustomEvent('jn:counts-changed'))
        }
      } catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Couldn't undo that — "${job.title}" is unchanged` }); fetchJobs() }
    } })
  }, [pushToast, fetchJobs, refreshStats])
  const saveJob = async (j) => { const willSave = !j.saved, ps = j.status, pv = j.saved; if (willSave && scoredCount(j) === 0) watchForScore(j.id); if (await patchRemote(j, { saved: willSave, status: willSave ? 'saved' : 'new' })) showUndo(j, ps, pv, `${willSave ? 'Saved' : 'Unsaved'} "${j.title}"`) }   // FEED-29
  const skipJob = async (j) => { const ps = j.status, pv = j.saved; if (await patchRemote(j, { status: 'skip' })) showUndo(j, ps, pv, `Skipped "${j.title}"`) }
  const applyJob = async (j) => {
    const ps = j.status, pv = j.saved
    const res = await patchRemote(j, { status: 'applied' })
    if (!res) return
    // R2-H-05: only ids this very PATCH created — never a pre-existing row
    const created = { appId: res.created_application_id || null, coId: res.created_company_id || null }
    if (created.appId || created.coId) window.dispatchEvent(new CustomEvent('jn:counts-changed'))
    showUndo(j, ps, pv, `Applied to "${j.title}"`, created)
  }
  // "Ignore {company} everywhere" — add to the global company-exclude setting
  // (matches classic ignoreCompany) and drop every job from that company now.
  const ignoreCompany = useCallback(async (job) => {
    const name = (job.company || '').trim()
    if (!name) return                    // nothing to exclude, and nothing to hide
    const n = jobsRef.current.filter((x) => (x.company || '').toLowerCase() === name.toLowerCase()).length
    // FEED-08: this edits a global scraper setting, so confirm first (classic
    // JobFeed did) and say what happened. R2-A-01: the styled dialog, not the
    // browser's — every other destructive confirm in v2 is this one.
    setConfirm({
      title: `Ignore “${name}” everywhere?`,
      body: `This hides ${n} job${n === 1 ? '' : 's'} and skips the company in all future scrapes. You can undo this in Settings → Global exclude.`,
      label: 'Ignore everywhere', danger: true,
      onConfirm: () => { setConfirm(null); doIgnoreCompany(name, n) },
    })
  }, [])
  const doIgnoreCompany = useCallback(async (name, n) => {
    setJobs((prev) => prev.filter((x) => (x.company || '').toLowerCase() !== name.toLowerCase()))
    setDetail((dd) => (dd && (dd.company || '').toLowerCase() === name.toLowerCase() ? null : dd))
    try {
      const { data: settings } = await api.get('/settings')
      const cur = Array.isArray(settings.company_exclude_global) ? settings.company_exclude_global : []
      if (!cur.some((c) => c.toLowerCase() === name.toLowerCase())) {
        await api.patch('/settings', { company_exclude_global: [...cur, name] })
      }
      pushToast({ kind: 'success', msg: `Ignoring "${name}" — ${n} job${n === 1 ? '' : 's'} hidden` })
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Couldn't ignore "${name}"` }); fetchJobs() }
  }, [fetchJobs, pushToast])
  const scoreJob = useCallback((job) => {
    pendingRef.current[job.id] = { title: job.title, company: job.company }
    pushToast({ kind: 'progress', msg: `Scoring "${job.title}"…` })
    api.post(`/analyze/${job.id}?depth=${defaultDepth}`, {}).then(() => {
      setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'analyze_job'])] } : x)); setDetail((cur) => (cur && cur.id === job.id ? { ...cur, in_flight: [...new Set([...(cur.in_flight || []), 'analyze_job'])] } : cur))
      setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
    }).catch((e) => { delete pendingRef.current[job.id]; pushToast({ kind: 'error', msg: `Scoring failed for "${job.title}"` }); console.error(e) })
  }, [pushToast, defaultDepth])

  // rescoreJob holds { label, jobs:[...] } — one job or a bulk set
  // `preferDepth` is for the one caller that is asking for a specific depth (the
  // report band's "Full report" — a Light score has nothing to open)
  const loadRescoreOpts = useCallback(async (preferDepth) => {
    // OPEN-10: the modal used to open on Full whatever Settings said. Both
    // options are still there and still switchable — only the preselection moved.
    setRescoreDepth(preferDepth || defaultDepth)
    try {
      const [rz, st] = await Promise.all([api.get('/resumes?is_base=true'), api.get('/settings')])
      const opts = (rz.data || []).map((r) => ({ id: r.id, name: r.name, note: 'base' }))
      if (personaAvailable) opts.push({ id: 'persona', name: 'Persona', note: 'from Persona' })
      setRescoreOpts(opts)
      const def = st.data?.default_resume_id
      setRescoreSel(def && opts.some((o) => o.id === def) ? [def] : opts.map((o) => o.id))
      const depth = st.data?.scoring_default_depth === 'full' ? 'full' : 'light'
      setDefaultDepth(depth)
      setRescoreDepth(preferDepth || depth)
    // OPEN-05: this list IS the modal — the user opened it to choose résumés, and
    // an empty body with a dead Score button explained nothing.
    } catch (e) { console.error(e); setRescoreOpts([]); setRescoreSel([]); pushToast({ kind: 'error', msg: 'Could not load your résumés — nothing to score against.' }) }
  }, [personaAvailable, defaultDepth, pushToast])
  const openRescore = useCallback((job, preferDepth) => { setRescoreJob({ verb: scoredCount(job) > 0 ? 'Rescore' : 'Score', title: job.title, company: job.company, jobs: [job] }); loadRescoreOpts(preferDepth) }, [loadRescoreOpts])
  const runRescore = useCallback(async () => {
    const target = rescoreJob
    if (!target || !rescoreSel.length) return
    const list = target.jobs || []
    setRescoreJob(null)
    if (list.length > 1) pushToast({ kind: 'progress', msg: `Scoring ${list.length} jobs…` })
    for (const job of list) {
      if (list.length === 1) { pendingRef.current[job.id] = { title: job.title, company: job.company }; pushToast({ kind: 'progress', msg: `Scoring "${job.title}"…` }) }
      try {
        await api.post(`/analyze/${job.id}?depth=${rescoreDepth}`, { cv_ids: rescoreSel })
        setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'analyze_job'])] } : x)); setDetail((cur) => (cur && cur.id === job.id ? { ...cur, in_flight: [...new Set([...(cur.in_flight || []), 'analyze_job'])] } : cur))
        setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
      } catch (e) { delete pendingRef.current[job.id]; console.error(e) }
    }
  }, [rescoreJob, rescoreSel, rescoreDepth, pushToast])

  const runResume = useCallback(async (mode, list, baseId) => {
    setPicker(null)
    for (const job of list) {
      try {
        if (mode === 'copy') { const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: job.id }); if (list.length === 1) navigate(`/v2/resumes/${data.id}`) }
        else {
          pendingRef.current[job.id] = { title: job.title, company: job.company, op: 'tailor' }
          pushToast({ kind: 'progress', msg: `Tailoring for "${job.title}"…` })
          await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: job.id })
          setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'tailor_resume'])] } : x)); setDetail((cur) => (cur && cur.id === job.id ? { ...cur, in_flight: [...new Set([...(cur.in_flight || []), 'tailor_resume'])] } : cur))
          setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
        }
      } catch (e) { delete pendingRef.current[job.id]; pushToast({ kind: 'error', msg: `${mode === 'copy' ? 'Copy' : 'Tailor'} failed for "${job.title}"` }); console.error(`${mode} failed`, e.response?.data?.detail || e.message) }
    }
    setChecked(new Set())
  }, [pushToast])
  const openTailored = useCallback(async (job) => {
    if (job.tailored_resume_id) { navigate(`/v2/resumes/${job.tailored_resume_id}`); return }
    try { const { data } = await api.get('/resumes'); const copy = (data || []).find((r) => !r.is_base && r.job_id === job.id); if (copy) { navigate(`/v2/resumes/${copy.id}`); return } } catch {}
    setPicker({ mode: 'tailor', jobs: [job] })
  }, [navigate])

  // Create-copy modal: seed method + default base when it opens
  useEffect(() => {
    if (!picker) return
    setCvMode(picker.mode || 'tailor')
    setCvBase(resumes[0]?.id ?? null)
  }, [picker, resumes])
  // 'Copy with tracers' can't use the Persona base — fall back to a real base
  const pickMethod = useCallback((m) => {
    setCvMode(m)
    if (m === 'copy') setCvBase((b) => (b === 'persona' ? (resumes[0]?.id ?? null) : b))
  }, [resumes])
  const cvBases = useMemo(() => {
    const list = resumes.map((r) => ({ id: r.id, name: r.name }))
    if (cvMode === 'tailor' && personaAvailable) list.push({ id: 'persona', name: 'Persona' })
    return list
  }, [resumes, cvMode, personaAvailable])

  const openRescoreBulk = useCallback(async () => {
    loadRescoreOpts()
    try {
      const { data } = await api.get('/jobs/unscored-ids')
      const ids = data.ids || []
      if (!ids.length) return
      setRescoreJob({ verb: 'Score', title: `${ids.length} unscored job${ids.length === 1 ? '' : 's'}`, company: '', jobs: ids.map((id) => ({ id })) })
    } catch (e) { console.error(e) }
  }, [loadRescoreOpts])

  // selection
  const rowClick = (e, i, job) => {
    if (e.metaKey || e.ctrlKey) { setChecked((p) => { const n = new Set(p); n.has(job.id) ? n.delete(job.id) : n.add(job.id); return n }); lastIdx.current = i; return }
    if (e.shiftKey && lastIdx.current != null) { const [a, b] = [lastIdx.current, i].sort((x, y) => x - y); setChecked((p) => { const n = new Set(p); for (let k = a; k <= b; k++) n.add(jobs[k].id); return n }); return }
    focusAt(i)
  }
  // R3-A-04: restore a whole batch. The rows can have had different prior
  // statuses, so group them and send one bulk-update per (status, saved) pair —
  // the same endpoint the forward path used.
  const bulkUndo = async (prev) => {
    if (!prev.length) return
    const groups = new Map()
    prev.forEach((p) => {
      const key = `${p.status}|${p.saved}`
      if (!groups.has(key)) groups.set(key, { updates: { status: p.status, saved: p.saved }, ids: [] })
      groups.get(key).ids.push(p.id)
    })
    try {
      for (const g of groups.values()) await api.post('/jobs/bulk-update', { job_ids: g.ids, updates: g.updates })
      fetchJobs(); refreshStats()
      pushToast({ kind: 'success', msg: `Restored ${prev.length} job${prev.length === 1 ? '' : 's'}.` })
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Could not undo ${prev.length} job${prev.length === 1 ? '' : 's'}` }) }
  }
  const bulkStatus = async (status) => {
    const ids = [...checked]; if (!ids.length) return
    // R3-A-04: the bulk path is the one where a mis-click costs the most and was
    // the only one with no way back. Snapshot before the write — after fetchJobs()
    // the rows are gone from the list.
    const idSet = new Set(ids)
    const prev = jobs.filter((j) => idSet.has(j.id)).map((j) => ({ id: j.id, status: j.status, saved: !!j.saved }))
    const updates = status === 'saved' ? { saved: true, status: 'saved' } : { status }
    // F5: write the rows locally first. The old order (POST, then fetchJobs())
    // blanked the whole list into its "Loading…" state for the round trip —
    // measured 12 rows → 0 rows 21 ms after the click, back only when the reload
    // landed. The server response only reconciles now; a failure reloads.
    setChecked(new Set())
    patchLocalMany(ids, updates)
    try { await api.post('/jobs/bulk-update', { job_ids: ids, updates }); refreshStats(); pushToast({ kind: 'undo', msg: `${status === 'saved' ? 'Saved' : 'Skipped'} ${ids.length} job${ids.length === 1 ? '' : 's'}.`, action: 'Undo', onAction: () => bulkUndo(prev) }) }   // FEED-20
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Could not update ${ids.length} job${ids.length === 1 ? '' : 's'}${e?.response?.data?.detail ? ' — ' + e.response.data.detail : ''}` }); fetchJobs() }   // the optimistic write did not stick — take the server's list back
  }
  const bulkScore = () => { jobs.filter((j) => checked.has(j.id) && scoredCount(j) === 0).forEach(scoreJob); setChecked(new Set()) }

  // OPEN-08: Escape used to be the first branch of the big window handler below,
  // which never looked at `defaultPrevented` — so with a ConfirmDialog open the
  // Feed also closed its own overlays behind it. It now goes through the shared
  // hook, gated on `!confirm` so a dialog's own useEscape owns the key while one
  // is open. Everything else is unchanged, including FEED-16: no INPUT guard
  // here, so Escape still works from inside a filter menu's search box.
  useEscape(() => { setMenu(null); setRowMenu(null); setHeadMenu(false); setShortcutsOpen(false); setPicker(null); setRescoreJob(null) }, !confirm)

  // keyboard
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') return   // OPEN-08: owned by the useEscape above
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      if (e.ctrlKey || e.metaKey || e.altKey) return  // let browser shortcuts (Ctrl+Shift+R etc.) through
      const list = jobsRef.current, idx = selRef.current, job = list[idx]
      switch (e.key) {
        case 'f': case 'j': case 'ArrowDown': e.preventDefault(); focusAt(Math.min(idx + 1, list.length - 1)); break
        case 'g': case 'k': case 'ArrowUp': e.preventDefault(); focusAt(Math.max(idx - 1, 0)); break
        // F3: the advance now lives in patchLocalMany, which knows the list the
        // row left behind. Only a row that STAYS in view (e.g. saving while the
        // Status filter still shows "saved") needs the key to step on by hand.
        case 's': if (job) { const nextStatus = job.saved ? 'new' : 'saved'; saveJob(job); if (!leavesView(nextStatus)) focusAt(Math.min(idx + 1, list.length - 1)) } break
        case 'x': if (job) { skipJob(job); if (!leavesView('skip')) focusAt(Math.min(idx + 1, list.length - 1)) } break
        case 'a': if (job) applyJob(job); break
        case 'e': case 'o': if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer'); break
        case 'r': if (job) openRescore(job); break
        case 't': if (job) setPicker({ mode: 'tailor', jobs: [job] }); break   // FEED-17: the ⋯ menus hint t
        case 'c': if (job) navigate(`/v2/cover-letters?job=${job.id}`); break   // and c
        default: break
      }
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAt])
  useEffect(() => { const el = listRef.current?.querySelector(`[data-row="${sel}"]`); if (el) el.scrollIntoView({ block: 'nearest' }) }, [sel])

  // cached page fetch when toggled on
  useEffect(() => {
    if (!detail || !viewCached || cachedHtml) return
    // The endpoint returns a complete reader HTML document (text/html), not JSON —
    // mirror v1's iframe, but fetch via axios so the X-API-Key header is sent, then
    // render the document string through srcDoc.
    const id = detail.id
    api.get(`/jobs/${id}/cached-page`, { responseType: 'text', transformResponse: (r) => r })
      .then(({ data }) => setCachedHtml(typeof data === 'string' && data.trim() ? data : '<p style="padding:16px;font-family:sans-serif">No cached snapshot.</p>'))
      .catch(() => setCachedHtml('<p style="padding:16px;font-family:sans-serif">No cached snapshot.</p>'))
  }, [detail, viewCached, cachedHtml])

  // Extension off: probe whether the posting will embed (X-Frame-Options / CSP
  // frame-ancestors). We still always TRY the live iframe — only a confident block
  // routes to the extension message. F4: the probe no longer gates the iframe; it
  // runs once per host, in the background, and its answer is remembered so every
  // later job on that host resolves with no wait at all.
  useEffect(() => {
    if (!detail || !detail.url || viewCached || extActive) return
    const host = hostOf(detail.url)
    if (!host || frameCache.current[host] !== undefined) return
    const id = detail.id
    api.get(`/jobs/${id}/frame-check`).then(({ data }) => {
      const ok = data?.embeddable !== false
      const next = { ...frameCache.current, [host]: ok ? 1 : 0 }
      const keys = Object.keys(next)
      if (keys.length > FRAME_CACHE_MAX) keys.slice(0, keys.length - FRAME_CACHE_MAX).forEach((k) => { delete next[k] })
      frameCache.current = next
      try { localStorage.setItem(FRAME_KEY, JSON.stringify(next)) } catch {}
      if (detailRef.current?.id === id) setFrameOk(ok)
    }).catch(() => { /* unknown — leave the optimistic frame up, as v1 did */ })
  }, [detail, viewCached, extActive])

  // F7: the src the live posting frame gets, and the job it belongs to. Every
  // route away from the live frame (the cached snapshot, a confirmed block, a
  // load that never arrived) makes it null, and the pane renders the cached or
  // fallback branch exactly as before.
  const cachedAvail = !!(detail && detail.status === 'applied' && detail.has_cached_page)
  const frameJobId = detail?.id || null
  const frameSrc = (detail?.url && !(viewCached && cachedAvail) && (extActive || frameOk !== false) && frameDeadId !== detail.id) ? detail.url : null
  // the cover goes up the moment a frame mounts (or its src changes) and comes
  // down on load/error — or on the safety timeout, which also retires a frame
  // that never answered. The id in the closure is the guard: a timer left over
  // from a job we have already stepped past can no longer clear the new cover.
  // Layout effect, not a plain one: the cover has to be painted with the frame's
  // first frame, or the empty iframe flashes --iframe-bg for one paint.
  useLayoutEffect(() => {
    if (!frameSrc) { setFrameLoadId(null); return }
    const id = frameJobId
    frameDoneRef.current = false
    setFrameLoadId(id)
    const t = setTimeout(() => {
      setFrameLoadId((c) => (c === id ? null : c))
      if (!frameDoneRef.current) setFrameDeadId(id)
    }, FRAME_LOAD_MS)
    return () => clearTimeout(t)
  }, [frameSrc, frameJobId])
  const settleFrame = useCallback((id) => {
    frameDoneRef.current = true
    setFrameLoadId((c) => (c === id ? null : c))
  }, [])

  // persona availability (adds a "Persona" option to score/tailor)
  useEffect(() => { api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => { /* silent: Persona is one optional entry in the score modal */ }) }, [])
  // OPEN-10: `scoring_default_depth` is the setting the scorer itself falls back
  // to; the Feed's one-click path now reads the same value instead of forcing full.
  useEffect(() => { api.get('/settings').then(({ data }) => setDefaultDepth(data?.scoring_default_depth === 'full' ? 'full' : 'light')).catch(() => { /* silent: the light default already applies */ }) }, [])

  // ?job=<id> is the job permalink — open that job's detail. The param is kept in
  // the URL (and re-synced below) so the link survives a refresh or a copy-paste.
  useEffect(() => {
    const jid = searchParams.get('job')
    if (!jid || jid === detailRef.current?.id) return
    pinnedRef.current = jid
    api.get(`/jobs/${jid}`).then(({ data }) => {
      if (pinnedRef.current !== jid) return
      setDetail(data); setReportTab(0); setViewCached(false); setCachedHtml(null); setFrameOk(frameGuess(data.url)); setFrameDeadId(null)
    }).catch(() => {
      if (pinnedRef.current !== jid) return
      pinnedRef.current = null; deadPinRef.current = true   // FEED-09: don't fall through to an unrelated job
      setSel(-1); setDetail(null)                           // the sync effect below then drops ?job= from the URL
      pushToast({ kind: 'error', msg: 'That job no longer exists' })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // keep ?job= pointing at whatever is open, without disturbing ?search=
  useEffect(() => {
    const id = detail?.id || null
    if (id === (searchParams.get('job') || null)) return
    setSearchParams((p) => {
      const n = new URLSearchParams(p)
      if (id) n.set('job', id); else n.delete('job')
      return n
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.id])

  // drop selected filter values that fall out of the dynamic lists
  useEffect(() => { if (sourceList.length && filters.source.length) { const v = filters.source.filter((s) => sourceList.includes(s)); if (v.length !== filters.source.length) setFilters((f) => ({ ...f, source: v })) } }, [sourceList]) // eslint-disable-line
  useEffect(() => { if (companyList.length && filters.company.length) { const v = filters.company.filter((c) => companyList.some((x) => x.name === c)); if (v.length !== filters.company.length) setFilters((f) => ({ ...f, company: v })) } }, [companyList]) // eslint-disable-line
  useEffect(() => { if (verdictList.length && filters.h1b_verdict.length) { const v = filters.h1b_verdict.filter((x) => verdictList.includes(x)); if (v.length !== filters.h1b_verdict.length) setFilters((f) => ({ ...f, h1b_verdict: v })) } }, [verdictList]) // eslint-disable-line

  // score-watch: save-triggered scoring runs untracked, so poll /jobs/{id} until it lands
  useEffect(() => {
    const tick = async () => {
      const w = scoreWatchRef.current
      if (!w.length) return
      const now = Date.now(); const keep = []
      for (const it of w) {
        if (now > it.until) continue
        try {
          const { data } = await api.get(`/jobs/${it.id}`)
          if (data.cv_scores && Object.keys(data.cv_scores).length) { setJobs((prev) => prev.map((j) => j.id === it.id ? data : j)); setDetail((d) => (d && d.id === it.id ? data : d)) }
          else keep.push(it)
        } catch { keep.push(it) }
      }
      scoreWatchRef.current = keep
    }
    const h = setInterval(tick, 3000)
    return () => clearInterval(h)
  }, [])

  // in-flight poll: tracked tailor/analyze ops → refetch + completion toast when they finish
  useEffect(() => {
    const activeIds = jobs.filter((j) => (j.in_flight || []).length).map((j) => j.id)
    const ids = [...new Set([...activeIds, ...watchExtra])]
    if (!ids.length) return
    let cancelled = false
    const tick = async () => {
      try {
        const { data } = await api.get('/monitor/in-flight', { params: { job_ids: ids.join(',') } })
        if (cancelled) return
        const present = new Set(ids.filter((id) => (data[id] || []).length))
        present.forEach((id) => seenActiveRef.current.add(id))
        const finished = ids.filter((id) => seenActiveRef.current.has(id) && !present.has(id))
        if (finished.length) {
          // resolve OK vs failed from the run's actual status, not just "it left in-flight"
          let statusMap = {}
          try {
            const { data: fin } = await api.get('/monitor/finished', { params: { job_ids: finished.join(','), since: Math.floor(Date.now() - 20000) } })
            ;(fin || []).forEach((r) => { if (!(r.target_job_id in statusMap)) statusMap[r.target_job_id] = r.status })
          } catch { /* status unknown — assume ok */ }
          for (const id of finished) {
            seenActiveRef.current.delete(id)
            let fresh = null
            try { const { data: jd } = await api.get(`/jobs/${id}`); fresh = jd; setJobs((prev) => prev.map((j) => j.id === id ? jd : j)); setDetail((d) => (d && d.id === id ? jd : d)) } catch {}
            const meta = pendingRef.current[id]
            if (meta) {
              const ok = statusMap[id] !== 'failed'
              // a finished tailor has a résumé to show; a finished score doesn't
              const rid = ok && meta.op === 'tailor' ? fresh?.tailored_resume_id : null
              pushToast({
                kind: ok ? 'success' : 'error',
                msg: `${meta.op === 'tailor' ? (ok ? 'Tailored' : 'Tailoring failed for') : (ok ? 'Scored' : 'Scoring failed for')} "${meta.title}"${meta.company ? ` at ${meta.company}` : ''}`,
                ...(rid ? { action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${rid}`) } : {}),
              })
              delete pendingRef.current[id]
            }
          }
          setWatchExtra((prev) => prev.filter((id) => !finished.includes(id)))
          refreshStats()
        }
        setJobs((prev) => prev.map((j) => (data[j.id] ? { ...j, in_flight: data[j.id] } : j)))
        setDetail((cur) => (cur && data[cur.id] ? { ...cur, in_flight: data[cur.id] } : cur))   // FEED-19
      } catch { /* retry next tick */ }
    }
    const h = setInterval(tick, 3000); tick()
    return () => { cancelled = true; clearInterval(h) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((j) => ((j.in_flight || []).length ? j.id : null)).filter(Boolean).join(','), watchExtra.join(',')])

  const setF = (patch) => { setFilters((f) => ({ ...f, ...patch })); setSel(0) }
  const togF = (key, val) => setF({ [key]: filters[key].includes(val) ? filters[key].filter((x) => x !== val) : [...filters[key], val] })
  // the list head's select-all cell: `all` is every shown row picked, `some` is any
  const allChecked = jobs.length > 0 && checked.size === jobs.length
  const someChecked = checked.size > 0

  const d = detail
  // the verdict is the fact the line carries; the LCA count is the evidence
  // behind it, so it moves into the title instead of a second clause
  const visaText = d ? (H1B[d.h1b_verdict] || H1B.unknown).label : ''
  const visaTitle = d ? (d.h1b_company_lca_count ? `Based on ${d.h1b_company_lca_count} H-1B filings` : 'No H-1B filings on record') : ''
  const visaCol = d ? (d.h1b_verdict === 'likely' ? 'var(--good)' : d.h1b_verdict === 'unlikely' ? 'var(--warn)' : 'var(--muted)') : ''

  // ── detail report derivation ──
  const reports = d ? scoreEntries(d).map(([name, score]) => ({ name, score, tailored: isTailoredName(name), rpt: (d.scoring_report || {})[name] })).sort((a, b) => b.score - a.score) : []
  const best = reports[0]
  const active = reports[Math.min(reportTab, Math.max(0, reports.length - 1))]
  const rpt = active?.rpt
  const reqRows = rpt?.requirement_mapping || []
  const reqMet = reqRows.filter((r) => r.matched).length
  const coverage = rpt?.keyword_coverage_pct
  // FEED-18: the collapsed band header is one résumé's story — the best one
  const bandReq = best?.rpt?.requirement_mapping || []
  const bandMet = bandReq.filter((r) => r.matched).length
  const bandCov = best?.rpt?.keyword_coverage_pct
  const running = d && (d.in_flight || []).some((o) => o === 'analyze_job')
  const dScored = reports.length > 0 && !running   // FEED-19: the running band replaces the report while a rescore runs
  // F1: a Light score has a number but no report. `reportOpen` is a persisted
  // preference, so a job with nothing to show used to open an empty report over
  // the posting (measured: report body 619px, posting container display:none).
  // The panel can only be open where there is a report to read.
  const hasReport = reports.some((r) => !!r.rpt)
  const reportShown = reportOpen && hasReport
  // The report only *covers* the posting while the top is standing. Collapsed, the
  // whole band is display:none, so a still-set `reportOpen` must not keep hiding
  // the posting too — the board binds its `postingDisplay` to `reportOpen` alone
  // (l.1766) and so renders an empty panel in that combination.
  const reportCovers = reportShown && !anaCollapsed
  const anaHint = anaCollapsed ? 'Show job details & analysis' : 'Hide job details & analysis — posting only'
  const dCached = cachedAvail   // hoisted above the frame effects, which need it too

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* header */}
      <HeaderRow as="header" pad="22px 30px 16px 24px" line="none" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <PageTitle>Jobs</PageTitle>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', ...headStyle }}>{head ? `${head.total} open roles · ${head.arrived} arrived today · ${head.unscored} not yet scored` : NBSP}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {head && head.unscored > 0 && <Button onClick={openRescoreBulk} title="Pick résumés + depth, then score every unscored job" style={headStyle}>Score {head.unscored} unscored jobs</Button>}
        </div>
      </HeaderRow>

      {/* filter bar */}
      <HeaderRow pad="0 30px 14px 24px" align="center" style={{ flexWrap: 'wrap', gap: 9, rowGap: 8 }}>
        {/* FEED-25: the clear ✕ rides in this relative wrapper, over SearchInput's box */}
        <div style={{ position: 'relative', flex: '0 0 auto', marginRight: 3, display: 'flex', alignItems: 'center' }}>
          <SearchInput width="226px" value={search} onChange={setSearch} placeholder="Search titles…" ariaLabel="Search job titles" />
          {search && <span onClick={() => setSearch('')} title="Clear search" className="v2-x" style={{ position: 'absolute', right: 8, width: 18, height: 18, borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--muted)', cursor: 'pointer' }}>✕</span>}
        </div>
        {searchId && (
          <Pill on onClick={() => { setSearchId(''); setSearchParams({}, { replace: true }) }}
            title="Showing only jobs from this saved search — click to clear">
            from “{searchName}”<span style={{ fontSize: 11, opacity: 0.7 }}>✕</span>
          </Pill>
        )}
        <Drop label={`Source${filters.source.length ? ` · ${filters.source.length}` : ''}`} active={filters.source.length > 0} onClear={() => setF({ source: [] })} open={menu === 'source'} onToggle={() => setMenu(menu === 'source' ? null : 'source')}>
          {/* warm-started: the option list is the cached one until the facets settle,
              so an early click on Source is not an empty menu */}
          {facetSources.length ? facetSources.map((s) => <Check key={s} on={filters.source.includes(s)} label={srcLabel(s)} count={facetSourceCounts[s]} onClick={() => togF('source', s)} />) : <div style={{ padding: 8, fontSize: 12, color: 'var(--muted)' }}>No sources</div>}
        </Drop>
        <Drop label={`Company${filters.company.length ? ` · ${filters.company.length}` : ''}`} active={filters.company.length > 0} onClear={() => setF({ company: [] })} open={menu === 'company'} onToggle={() => setMenu(menu === 'company' ? null : 'company')} width={248}>
          <Input autoFocus value={companyQuery} onChange={setCompanyQuery} ariaLabel="Search companies"
            placeholder={`Type to search ${companyList.length} companies…`} style={{ margin: '0 6px 6px', width: 'calc(100% - 12px)', paddingLeft: 12 }} />
          {(() => {
            const q = companyQuery.trim().toLowerCase()
            const list = companyList.filter((c) => filters.company.includes(c.name) || c.name.toLowerCase().includes(q))
            // picked companies pin to the top, keeping the backend's count-desc order within each group
            const sorted = [...list].sort((a, b) => (filters.company.includes(b.name) ? 1 : 0) - (filters.company.includes(a.name) ? 1 : 0)).slice(0, 80)
            return sorted.length ? (
              <>
                {sorted.map((c) => (
                  <MenuItem key={c.name} ellipsis onClick={() => togF('company', c.name)} hint={c.count} hintMono
                    icon={<UICheck checked={filters.company.includes(c.name)} size="md" />}>
                    {c.name}
                  </MenuItem>
                ))}
                <Helper size="xs" style={{ padding: '6px 8px 2px' }}>Top by open roles · picked companies pin to the top</Helper>
              </>
            ) : <div style={{ padding: '6px 8px', fontSize: 12, color: 'var(--muted)' }}>No matches</div>
          })()}
        </Drop>
        <Drop label={`H-1B${filters.h1b_verdict.length ? ` · ${filters.h1b_verdict.length}` : ''}`} active={filters.h1b_verdict.length > 0} onClear={() => setF({ h1b_verdict: [] })} open={menu === 'h1b'} onToggle={() => setMenu(menu === 'h1b' ? null : 'h1b')} width={196}>
          {['likely', 'possible', 'unlikely', 'unknown'].filter((v) => facetVerdicts.includes(v)).map((v) => <Check key={v} on={filters.h1b_verdict.includes(v)} label={H1B[v].label.replace('H-1B ', '')} count={facetVerdictCounts[v]} onClick={() => togF('h1b_verdict', v)} />)}
        </Drop>
        <Drop inset label={filters.min_score !== '' ? `Score ≥ ${filters.min_score}` : 'Score ≥'} active={filters.min_score !== ''} onClear={() => setF({ min_score: '' })} open={menu === 'score'} onToggle={() => setMenu(menu === 'score' ? null : 'score')} width={234}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[70, 80, 90].map((n) => <Pill key={n} size="sm" on={filters.min_score === String(n)} onClick={() => setF({ min_score: String(n) })} style={{ flex: 1 }}>{n}</Pill>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Helper>or at least</Helper>
            <Input type="number" mono value={numDraft.min_score} onChange={(v) => setNum('min_score', v)}
              ariaLabel="Minimum score" style={{ flex: 1, minWidth: 0 }} />
          </div>
          <Helper size="xs" style={{ marginTop: 8 }}>Also hides unscored jobs — they have no score to compare</Helper>
        </Drop>
        <Drop inset label={filters.min_salary && filters.max_salary ? `$${filters.min_salary}K–$${filters.max_salary}K` : filters.min_salary ? `Salary ≥ $${filters.min_salary}K` : filters.max_salary ? `Salary ≤ $${filters.max_salary}K` : 'Salary'} active={!!(filters.min_salary || filters.max_salary)} onClear={() => setF({ min_salary: '', max_salary: '' })} open={menu === 'salary'} onToggle={() => setMenu(menu === 'salary' ? null : 'salary')} width={288}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[150, 180, 220].map((n) => <Pill key={n} size="sm" on={filters.min_salary === String(n)} onClick={() => setF({ min_salary: String(n) })} style={{ flex: 1 }}>${n}K</Pill>)}
          </div>
          {/* both ends of the range: `max_salary` was already in DEFAULTS, in the
              trigger label and in the query params, but had no field to set it */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <Helper>min</Helper>
            <Input type="number" mono placeholder="$K" value={numDraft.min_salary} onChange={(v) => setNum('min_salary', v)}
              ariaLabel="Minimum salary in thousands" style={{ flex: 1, minWidth: 0 }} />
            <Helper>max</Helper>
            <Input type="number" mono placeholder="$K" value={numDraft.max_salary} onChange={(v) => setNum('max_salary', v)}
              ariaLabel="Maximum salary in thousands" style={{ flex: 1, minWidth: 0 }} />
          </div>
          <Helper size="xs" style={{ marginTop: 8 }}>Also hides jobs without a listed salary</Helper>
        </Drop>
        <Drop width={170} active open={menu === 'status'} onToggle={() => setMenu(menu === 'status' ? null : 'status')}
          trigger={(t) => {
            const statusActive = !(filters.status.length === DEFAULTS.status.length && DEFAULTS.status.every((s) => filters.status.includes(s)))
            return (
              <Pill on={statusActive} onClick={t} ariaExpanded={menu === 'status'} ariaHaspopup="menu">
                Status · {filters.status.map((s) => STATUS_OPTS.find((o) => o[0] === s)?.[1]).join(', ') || 'Any'}
                {statusActive ? <span onClick={(e) => { e.stopPropagation(); setF({ status: DEFAULTS.status }) }} style={{ opacity: 0.6 }}>✕</span> : <span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>}
              </Pill>
            )
          }}>
          {STATUS_OPTS.map(([v, label]) => <Check key={v} on={filters.status.includes(v)} label={label} onClick={() => togF('status', v)} />)}
        </Drop>
        <div style={{ marginLeft: 'auto', flex: '0 0 auto' }}>
          <Drop width={172} open={menu === 'sort'} onToggle={() => setMenu(menu === 'sort' ? null : 'sort')}
            trigger={(t) => /* ui: keep — the Sort control is a text trigger (muted 12.5 + bold value + caret), not a Pill or a Link */ <div onClick={t} className="v2-hover-accent-text" style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORT_OPTS.find((o) => o[0] === sortBy)?.[1]}</span><span style={{ fontSize: 10 }}>▾</span></div>}>
            {SORT_OPTS.map(([v, label]) => (
              <MenuItem key={v} selected={sortBy === v} hint={sortBy === v ? '✓' : null}
                onClick={() => { setSortBy(v); setMenu(null); setSel(0) }}>{label}</MenuItem>
            ))}
          </Drop>
        </div>
      </HeaderRow>

      {/* body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* list */}
        <section style={{ position: 'relative', width: 472, flex: '0 0 472px', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ position: 'relative', padding: '12px 14px 8px 24px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
            <UICheck checked={allChecked} indeterminate={someChecked && !allChecked} ariaLabel="Select all shown" title="Select all shown" style={{ flex: '0 0 auto' }}
              onChange={() => setChecked(allChecked ? new Set() : new Set(jobs.map((j) => j.id)))} />
            {/* the count line keeps its box until the first page answers */}
            <span style={{ flex: '0 0 auto', whiteSpace: 'nowrap' }}>{firstLoaded ? `${jobs.length} shown · ${total} matching` : NBSP}</span>
            <div style={{ marginLeft: 'auto', flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.02em' }}>Shift-click selects a range · {PICK_KEY}-click selects one</span>
              {/* ui: keep — the outline tone's edge is --glyph-border (= --edge); this one
                  has always drawn on --line, one step softer, with no ground and a 10px
                  glyph against the box's 9.5. Pinned, not drifted — see D-14. */}
              <GlyphBadge tone="outline" onClick={() => setShortcutsOpen((v) => !v)} title="Keyboard shortcuts"
                style={{ background: 'transparent', borderColor: 'var(--head-line)', fontSize: 'var(--t-10)' }}>?</GlyphBadge>
            </div>
            {shortcutsOpen && (
              <>
                <div onClick={() => setShortcutsOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 34 }} />
                <Menu role="group" ariaLabel="Keyboard shortcuts" style={{ position: 'absolute', top: '100%', right: 14, zIndex: 35, marginTop: 4, width: 214, padding: 10, gap: 0 }}>
                  {/* ui: keep — MenuHead role: the head of a <Menu> popover, not a filter-bar eyebrow */}
                  <div style={{ fontSize: 10.5, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6 }}>Keyboard</div>
                  {SHORTCUTS.map(([k, desc]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '3px 0', fontSize: 12 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{k}</span>
                      <span style={{ color: 'var(--muted)' }}>{desc}</span>
                    </div>
                  ))}
                </Menu>
              </>
            )}
          </div>

          {checked.size > 0 && (
            // ui: keep — the floating bulk bar is a pill-shaped *bar* on the dark --rail
            // ground with --shadow-pop; no primitive owns a bar, and Pill is a control.
            <div style={{ position: 'absolute', left: '50%', bottom: 14, transform: 'translateX(-50%)', zIndex: 25, display: 'flex', alignItems: 'center', gap: 6, padding: '7px 8px 7px 14px', background: 'var(--rail)', borderRadius: 'var(--radius-control)', boxShadow: 'var(--shadow-pop)' }}>
              <span style={{ fontSize: 12, color: 'var(--rail-ink)', fontWeight: 600, whiteSpace: 'nowrap' }}>{checked.size} selected</span>
              <div style={{ width: 1, height: 16, background: 'var(--on-rail-sep)', margin: '0 3px' }} />
              <Button size="xs" onClick={() => bulkStatus('saved')}>Save</Button>
              {/* ui: keep — RAIL_BTN controls (--rail-ink on --on-rail-line); the Pill tokens are for light surfaces */}
              <div onClick={() => bulkStatus('skip')} className="v2-bdc v2-ctl" style={RAIL_BTN}>Skip</div>
              {/* ui: keep — RAIL_BTN, as above */}
              <div onClick={bulkScore} className="v2-bdc v2-ctl" style={RAIL_BTN}>Score</div>
              <div onClick={() => setPicker({ mode: 'tailor', jobs: jobs.filter((j) => checked.has(j.id)) })} style={{ ...RAIL_BTN, gap: 5 }}><span style={{ color: 'var(--rail-accent)' }}>✦</span>Tailor</div>
              <div onClick={() => setChecked(new Set())} style={{ width: 27, height: 27, borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--on-rail-dim)', cursor: 'pointer' }}>✕</div>
            </div>
          )}

          <div ref={listRef} onScroll={onListScroll} className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px 12px', display: 'flex', flexDirection: 'column', userSelect: 'none', WebkitUserSelect: 'none' }}>
            {/* DESIGN-LOAD: no "Loading…" on the FIRST paint — the list keeps its
                box and fills in once. A later reload (a filter change) is an
                explicit action, and keeps its line. */}
            {loading ? (firstLoaded ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div> : null)
              // ui: keep — the "Try again" link runs inline inside a 13px sentence; Link's 11.5/500 would break the run
              : loadError ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Couldn't load jobs · <span onClick={fetchJobs} style={{ color: 'var(--accent)', cursor: 'pointer' }}>Try again</span></div>
              : jobs.length === 0 ? (
                  (!filters.status.length && !filters.company.length && !filters.source.length && !filters.h1b_verdict.length && filters.min_score === '' && !filters.min_salary && !dSearch && !searchId)
                    ? <div style={{ padding: '48px 40px', textAlign: 'center', color: 'var(--muted)', fontSize: 13, lineHeight: '20px' }}>   {/* F-010: first-run / nothing open */}
                        <Heading style={{ display: 'block', marginBottom: 6 }}>No open roles yet</Heading>
                        Jobs come from <a href="/v2/searches" onClick={(e) => { e.preventDefault(); navigate('/v2/searches') }}>Searches</a> and <a href="/v2/companies" onClick={(e) => { e.preventDefault(); navigate('/v2/companies') }}>Companies</a>. Activate one, or change the Status filter to include skipped and applied jobs.
                      </div>
                    : <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13, lineHeight: '20px' }}>No jobs match.<br /><Link onClick={() => { setFilters(DEFAULTS); setSearch(''); setSearchId('') }}>Clear filters</Link></div>)   /* FEED-24 */
              : jobs.map((j, i) => {
                const score = bestScore(j), nsc = scoredCount(j)
                const badge = BADGE[j.status]
                const run = (j.in_flight || []).length > 0
                const isIgnored = j.status === 'ignored'
                const on = checked.has(j.id)
                const visa = H1B[j.h1b_verdict]
                // the Feed row is a 64px two-column row: the box (radius, divider,
                // hover, cursor) comes from Row, the layout (auto height, stretch,
                // no gap, inner padding) is the caller's. `on` is the bulk-select
                // tint, which has no Row state of its own.
                return (
                  <Row key={j.id} data-row={i} divider selected={i === sel} onClick={(e) => rowClick(e, i, j)}
                    style={{ flex: '0 0 auto', height: 'auto', alignItems: 'stretch', gap: 0, padding: 0, backgroundColor: (on || i === sel) ? 'var(--row-selected)' : 'transparent', backgroundImage: (isIgnored && !on && i !== sel) ? 'repeating-linear-gradient(-45deg, transparent 0 8px, var(--line-soft) 8px 10px)' : 'none', overflow: 'hidden' }}>
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 14, padding: '10px 12px', opacity: isIgnored ? 0.55 : 1 }}>
                      {/* ring */}
                      <div style={{ position: 'relative', width: 44, height: 44, flex: '0 0 44px' }}>
                        {nsc > 0 ? (
                          <ScoreRing value={score} size="md">
                            {/* ui: keep — the “+N reports” count badge pinned to the ring: a 16px min-width
                                box on --surface with a --line hairline; Tag has no fixed box */}
                            {nsc > 1 && <div title={`${nsc} résumé reports`} style={{ position: 'absolute', right: -3, bottom: -2, minWidth: 16, height: 16, padding: '0 3px', borderRadius: 'var(--radius-control)', background: 'var(--surface)', border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--text-2)' }}>{nsc}</div>}
                          </ScoreRing>
                        ) : run ? (
                          // F6: the busy state is the ring it replaces — same 44px box,
                          // same 37.5px arc. It used to be a Spinner drawn to the full
                          // 44px box, 6.5px wider than the ring beside it in every other
                          // row, at a 1.5px band against the ring's 2.5px.
                          <ScoreRing busy size="md" title="Scoring…">
                            {/* ui: keep — 8px accent ··· marker inside the running ring, not a label */}
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, letterSpacing: '.07em', textTransform: 'uppercase', color: 'var(--accent)' }}>···</div>
                          </ScoreRing>
                        ) : (
                          /* ui: keep — 8.5px dashed uppercase micro-badge filling the 34px score slot (position:absolute inset 0) */
                          <div className="v2-bdc" onClick={(e) => { e.stopPropagation(); scoreJob(j) }} title={defaultDepth === 'full' ? 'Score this role — full (score + keywords + report)' : 'Score this role — light (score only). Change the default in Settings › Scoring, or press r to pick.'} style={{ position: 'absolute', inset: 0, border: '1px dashed var(--edge)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8.5, fontWeight: 600, letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--muted)', cursor: 'pointer' }}>Score</div>
                        )}
                        {/* ui: keep — the ring it sits on is 9px, half a step under the badge's
                            own 9.5, and it wears a 2px --surface knock-out ring so it reads
                            over the disc: two pins on top of the GlyphBadge box. */}
                        {on && <GlyphBadge style={{ position: 'absolute', left: -4, top: -3, border: '2px solid var(--surface)', fontSize: 'var(--t-9)' }}>✓</GlyphBadge>}
                      </div>
                      {/* text */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, minHeight: 20 }}>
                          {/* the 1.15 ratio is the row's: it keeps the two-line title block at
                              the list row's own rhythm, so it stays with the call site */}
                          <Heading strong size={16} title={j.title} style={{ flex: 1, minWidth: 0, lineHeight: 1.15, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textDecoration: isIgnored ? 'line-through' : 'none', textDecorationColor: 'var(--muted)' }}>{j.title}</Heading>
                          {j.tailored_resume_id && <a href={`/v2/resumes/${j.tailored_resume_id}`} onClick={(e) => { e.preventDefault(); e.stopPropagation(); navigate(`/v2/resumes/${j.tailored_resume_id}`) }} title="Open tailored résumé" style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, margin: '-2px -2px -2px 0', fontSize: 14, lineHeight: 1, color: 'var(--accent)' }}>✦</a>}
                          {/* ui: keep — status badge with background + border + r99: Tag role (D4d), not a Label */}
                          {badge && <span style={{ flex: '0 0 auto', fontSize: 9.5, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase', padding: '2px 7px', lineHeight: '14px', borderRadius: 'var(--radius-control)', border: `1px solid ${badge.bd}`, background: badge.bg, color: badge.fg }}>{badge.label}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, lineHeight: 1.2, fontWeight: 450, color: 'var(--text-2)', minWidth: 0, marginTop: -2 }}>
                          <span title={j.company} style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 230, fontWeight: 500, color: 'var(--ink-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.company}</span>
                          {j.location && <span style={{ flex: '0 0 auto', color: 'var(--line)' }}>|</span>}
                          {j.location && <span title={j.location} style={{ flex: '1 1 auto', minWidth: 40, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.location}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 11, lineHeight: '13px', fontWeight: 450, minWidth: 0, marginTop: 2 }}>
                          <span style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 170, fontFamily: 'var(--mono)', color: fmtSalary(j.salary_min, j.salary_max) ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtSalary(j.salary_min, j.salary_max) || 'Salary not listed'}</span>
                          {visa && <><span style={{ color: 'var(--line)' }}>·</span><span style={{ letterSpacing: '.04em', color: visa.c }}>{visa.label}</span></>}
                          <span style={{ color: 'var(--line)' }}>·</span><span style={{ color: 'var(--muted)' }}>{timeAgo(j.discovered_at)}</span>
                        </div>
                      </div>
                    </div>
                    {/* action column */}
                    <div style={{ position: 'relative', flex: '0 0 27px', display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--line-soft)' }} onClick={(e) => e.stopPropagation()}>
                      {/* ui: keep — v2-rail-cell glyph cells (♥ / ✕ / ⋯); rail text is out of scope for this step */}
                      {/* F5: the heart carries the saved state itself, so the control the
                          user clicked answers immediately — not only the title's badge */}
                      <div className="v2-rail-save v2-rail-cell" title={j.saved ? 'Unsave (s)' : 'Save (s)'} onClick={() => saveJob(j)} style={{ flex: 1, fontSize: 11, color: j.saved ? 'var(--accent)' : 'var(--text-2)', borderBottom: '1px solid var(--line-soft)' }}>♥</div>
                      <div className="v2-rail-skip v2-rail-cell" title="Skip (x)" onClick={() => skipJob(j)} style={{ flex: 1, fontSize: 11, color: 'var(--muted)', borderBottom: '1px solid var(--line-soft)' }}>✕</div>
                      <div className="v2-rail-copy v2-rail-cell" title="More" onClick={(ev) => {
                        if (rowMenu?.id === j.id) { setRowMenu(null); return }
                        const r = ev.currentTarget.getBoundingClientRect()
                        const up = r.bottom + 236 > window.innerHeight
                        setRowMenu({ id: j.id, left: Math.max(8, r.right - 228), top: up ? undefined : r.bottom + 3, bottom: up ? window.innerHeight - r.top + 3 : undefined })
                      }} style={{ flex: 1, fontSize: 12, color: rowMenu?.id === j.id ? 'var(--text)' : 'var(--muted)', background: rowMenu?.id === j.id ? 'var(--surface-2)' : 'transparent' }}>⋯</div>
                      {rowMenu?.id === j.id && (
                        <>
                          <div onClick={() => setRowMenu(null)} style={{ position: 'fixed', inset: 0, zIndex: 59 }} />
                          <Menu ariaLabel="Job actions" style={{ position: 'fixed', left: rowMenu.left, top: rowMenu.top, bottom: rowMenu.bottom, zIndex: 60, width: 228 }}>
                            {[['Mark applied', 'a', () => applyJob(j)], ['Tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [j] })], ['Rescore', 'r', () => openRescore(j)], ['Open posting ↗', 'e', () => j.url && window.open(j.url, '_blank', 'noopener,noreferrer')]].map(([label, key, act]) => (
                              <MenuItem key={label} hint={key} hintMono onClick={() => { setRowMenu(null); act() }}
                                style={label === 'Tailor résumé' ? { fontWeight: 600 } : undefined}>{label}</MenuItem>
                            ))}
                            <MenuItem danger onClick={() => { setRowMenu(null); ignoreCompany(j) }}
                              style={{ display: j.company ? 'flex' : 'none' }}>Ignore {j.company} everywhere</MenuItem>
                          </Menu>
                        </>
                      )}
                    </div>
                  </Row>
                )
              })}
            {loadingMore && <Helper style={{ padding: '14px 0', textAlign: 'center' }}>Loading more…</Helper>}   {/* FEED-38 */}
            {!loadingMore && !hasMore && jobs.length > 0 && <Helper style={{ padding: '14px 0 6px', textAlign: 'center' }}>End of the list · {total} job{total === 1 ? '' : 's'}</Helper>}
          </div>
        </section>

        {/* detail */}
        <section style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 }}>
          {!d ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Select a job.</div> : (
            <>
              {/* ui: keep — the board's grab-line (l.252-254): 12px of hit area that
                  FLOATS over the top of the pane (absolute, z-20, no background and no
                  border of its own) holding a bare 52x4 handle. It is the single
                  control that folds the whole top of the right side away, and it is not
                  a Row/Button/SectionHead: no label, no padding box, no head row. */}
              <div {...kb(toggleAna)} onClick={toggleAna} aria-expanded={!anaCollapsed} title={anaHint} className="v2-grab"
                style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 20, height: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                {/* ui: keep — the 52x4 handle itself: a rounded rule, not a Pill (no text,
                    no padding, no border) and not a Rule (which draws a 1px line token).
                    Its --surface ring, its hover (--accent, 64px) and the .12s transition
                    are `.v2-grab` rules in theme.css, where a shadow may be spelled out. */}
                <span style={{ width: 52, height: 4, borderRadius: 'var(--radius-control)', background: 'var(--edge)' }} />
              </div>

              {/* The fold the grab-line drives: the header and the score band travel
                  together (the board binds both to `analysisWrapDisplay`, l.1734-1735) on
                  one grid row — see `.v2-fold`. It carries the flex the report band used
                  to take, so an open report still fills the pane. */}
              <div className="v2-fold" data-collapsed={anaCollapsed ? 'true' : 'false'}
                style={{ flex: reportCovers ? '1 1 0%' : '0 0 auto', minHeight: 0 }}>
              <div className="v2-foldbody" style={{ overflow: anaCollapsed || folding ? 'hidden' : 'visible' }}>

              {/* header */}
              <HeaderRow align="stretch" pad={headOpen ? '20px 30px 15px' : '11px 30px 12px'} style={{ flexDirection: 'column', gap: headOpen ? 14 : 10 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 3, marginLeft: -26 }}>
                  {/* ui: keep — a bare 19x26 caret cell in the header gutter: it has no label,
                      so there is no head row for SectionHead to draw (the title beside it is a
                      separate click target) */}
                  <div onClick={() => setHeadOpen((v) => !v)} className="v2-hover-accent" style={{ flex: '0 0 auto', width: 19, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--muted)', cursor: 'pointer' }}>{headOpen ? '⌄' : '›'}</div>
                  <div onClick={() => setHeadOpen((v) => !v)} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6, cursor: 'pointer' }}>
                    {headOpen && <Label style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      {d.company && <><span style={{ maxWidth: 300, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.company}</span><span>·</span></>}<span>{srcLabel(d.source)}</span><span>·</span><span>{timeAgo(d.discovered_at)}</span>
                    </Label>}
                    {/* ui: keep — the collapsing detail title: serif 26/17, -.025em, line-clamped — outside the 18/19 heading scale */}
                    <h2 title={d.title} style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: headOpen ? 26 : 17, fontWeight: 400, letterSpacing: '-.025em', lineHeight: headOpen ? '30px' : '20px', display: '-webkit-box', WebkitLineClamp: headOpen ? 2 : 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{d.title}</h2>
                    {headOpen ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, lineHeight: '20px', color: 'var(--text-2)', flexWrap: 'wrap', rowGap: 3 }}>
                        <span style={{ maxWidth: 230, fontFamily: 'var(--mono)', fontSize: 12.5, color: fmtSalary(d.salary_min, d.salary_max) ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtSalary(d.salary_min, d.salary_max) || 'Salary not listed'}</span>
                        {d.location && <><span style={{ color: 'var(--line)' }}>|</span><span style={{ maxWidth: 270, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.location}</span></>}
                        <span style={{ color: 'var(--line)' }}>|</span>
                        <span title={visaTitle} style={{ color: visaCol }}>{visaText}</span>
                      </div>
                    ) : <Helper style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{[d.company, fmtSalary(d.salary_min, d.salary_max) || 'Salary not listed', d.location, visaText, srcLabel(d.source), timeAgo(d.discovered_at)].filter(Boolean).join(' · ')}</Helper>}
                  </div>
                  {/* actions */}
                  <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {/* ui: keep — a real <a href target=_blank>, and its height tracks the collapsing detail header (36/30) */}
                    {d.url && <a href={d.url} target="_blank" rel="noopener noreferrer" className="v2-act" style={{ height: headOpen ? 36 : 30, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-2)' }}>Open ↗</a>}
                    {/* ui: keep — height tracks the collapsing detail header (36/30); Button's sizes are fixed, and its Open ↗ / ⋯ siblings follow the same pair */}
                    <div onClick={() => d.tailored_resume_id ? openTailored(d) : setPicker({ mode: 'tailor', jobs: [d] })} style={{ height: headOpen ? 36 : 30, padding: '0 19px', borderRadius: 'var(--radius-control)', background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>{d.tailored_resume_id ? '✦ Open tailored ↗' : 'Tailor résumé'}</div>
                    <div style={{ position: 'relative', flex: '0 0 auto' }}>
                      {/* ui: keep — 36/30 with the collapsing detail header; IconButton's bordered size is a fixed 36 */}
                      <div title="More actions" onClick={(e) => { e.stopPropagation(); setHeadMenu((v) => !v) }} className="v2-act" style={{ width: headOpen ? 36 : 30, height: headOpen ? 36 : 30, border: `1px solid ${headMenu ? 'var(--accent)' : 'var(--edge)'}`, background: headMenu ? 'var(--accent-soft)' : 'transparent', color: headMenu ? 'var(--accent)' : 'var(--text-2)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, cursor: 'pointer' }}>⋯</div>
                      {headMenu && (
                        <>
                          <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                          <Menu ariaLabel="Job actions" style={{ position: 'absolute', top: '100%', right: 0, zIndex: 45, marginTop: 5, width: 236 }}>
                            {[
                              ...(d.tailored_resume_id ? [['✦ Re-tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [d] }), true]] : []),
                              ['Mark applied', 'a', () => applyJob(d)],
                              ['Rescore', 'r', () => openRescore(d)],
                              ['Cover letter ↗', 'c', () => navigate(`/v2/cover-letters?job=${d.id}`)],
                              ['Copy résumé with tracked links', '', () => setPicker({ mode: 'copy', jobs: [d] })],
                            ].map(([label, key, act, bold]) => (
                              <MenuItem key={label} hint={key} hintMono onClick={() => { setHeadMenu(false); act() }}
                                style={bold ? { color: 'var(--text)', fontWeight: 600 } : undefined}>{label}</MenuItem>
                            ))}
                            <MenuItem danger onClick={() => { setHeadMenu(false); ignoreCompany(d) }}
                              style={{ display: d.company ? 'flex' : 'none' }}>Ignore {d.company} everywhere</MenuItem>
                          </Menu>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </HeaderRow>

              {/* report band — inside the fold with the header: the band line AND the
                  expanded report (board l.301 binds its display to analysisWrapDisplay,
                  the same flag as the header) */}
              {dScored && (
                <div style={{ position: 'relative', zIndex: 18, flex: reportShown ? '1 1 0%' : '0 0 auto', minHeight: 0, borderBottom: '1px solid var(--line)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column' }}>
                  {/* ui: keep — the report *band* header, not a section head: its caret is a
                      fixed 19px gutter aligned to the row rail, it carries a 34px score ring and
                      résumé tabs, and its body text runs at the band's inherited size, which
                      SectionHead's 12.5/18px type box would restyle */}
                  <div onClick={hasReport ? () => { setReportOpen((v) => !v); if (!reportOpen && best) setReportTab(Math.max(0, reports.indexOf(best))) } : undefined}
                    className={hasReport ? 'v2-hover-accent' : undefined}
                    style={{ flex: '0 0 auto', padding: '8px 30px 8px 4px', display: 'flex', alignItems: 'center', gap: 9, cursor: hasReport ? 'pointer' : 'default' }}>
                    {/* ui: keep — the band's caret glyph in a fixed 19px gutter, not helper text */}
                    <span style={{ flex: '0 0 auto', width: 19, textAlign: 'center', color: 'var(--muted)', fontSize: 11 }}>{hasReport ? (reportShown ? '⌄' : '›') : ''}</span>
                    <ScoreRing value={best?.score} size="sm" style={{ marginLeft: -4 }} />
                    <span title={best?.name} style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 220, fontSize: 12.5, color: 'var(--text-2)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{best?.tailored ? '✦ ' : ''}{best?.name}</span>
                    {bandCov != null && <><Rule vertical tone="line" /><span style={{ fontSize: 12.5, color: 'var(--muted)' }}>{bandCov}% keywords</span></>}
                    {bandReq.length > 0 && <><Rule vertical tone="line" /><span style={{ flex: 1, minWidth: 0, fontSize: 12.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{bandMet} of {bandReq.length} requirements met</span></>}
                    <Rule vertical tone="line" style={{ marginLeft: 'auto' }} />
                    {hasReport
                      ? <span style={{ flex: '0 0 auto', fontSize: 12.5, color: 'var(--muted)' }}>{reports.length} report{reports.length === 1 ? '' : 's'}</span>
                      // F1: a Light score has no report to open — say so on the band line
                      // and leave the posting below it, instead of covering it with an
                      // empty panel.
                      : <>
                          <span style={{ flex: '0 0 auto', fontSize: 12.5, color: 'var(--muted)' }}>Score at full depth to see the report</span>
                          <Button size="xs" onClick={(e) => { e.stopPropagation(); openRescore(d, 'full') }} style={{ flex: '0 0 auto' }}>Full report</Button>
                        </>}
                  </div>
                  {reportShown && (
                    <div style={{ borderTop: '2px solid var(--accent)', background: 'var(--surface)', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                      {/* tabs */}
                      <HeaderRow pad="0 30px" align="center" style={{ gap: 0 }}>
                        {reports.map((r, k) => {
                          const onTab = k === Math.min(reportTab, reports.length - 1)
                          return (
                            <div key={r.name} className="v2-tab" onClick={() => { setReportTab(k); setReqFilter('all') }} title={r.name} style={{ padding: '7px 0', marginRight: 22, maxWidth: 230, fontSize: 12.5, color: onTab ? 'var(--text)' : 'var(--muted)', borderBottom: `2px solid ${onTab ? 'var(--accent)' : 'transparent'}`, marginBottom: -1, cursor: 'pointer', display: 'flex', alignItems: 'baseline', gap: 6 }}>
                              {r.tailored && <span style={{ fontSize: 10, color: 'var(--accent)' }}>✦</span>}
                              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</span>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, opacity: 0.7 }}>({r.score})</span>
                            </div>
                          )
                        })}
                        <NavLink pad="7px 0" onClick={() => openRescore(d)} style={{ marginLeft: 'auto', color: 'var(--muted)' }}>+ Rescore</NavLink>
                      </HeaderRow>
                      {/* body */}
                      <div className="v2-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '14px 30px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {rpt?.summary && <span style={{ fontSize: 13.5, lineHeight: '22px', color: 'var(--text-2)' }}>{rpt.summary}</span>}
                        {(d.fit_strengths || []).length > 0 && !rpt?.summary && <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{(d.fit_strengths || []).map((s, k) => <div key={k} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--good)' }}>✓</span><span>{s}</span></div>)}</div>}

                        {rpt?.breakdown && Object.keys(rpt.breakdown).length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: breakdownOpen ? 11 : 0 }}>
                            <SectionHead boxed caret="end" open={breakdownOpen} onToggle={() => setBreakdownOpen((v) => !v)}
                              style={{ gap: 8, margin: '-2px -4px' }}>
                              <Label>Score breakdown</Label>
                              <Rule style={{ flex: 1, minWidth: 0 }} />
                            </SectionHead>
                            {breakdownOpen && (
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '11px 30px' }}>
                                {Object.entries(rpt.breakdown).filter(([, v]) => typeof v === 'number').map(([label, val]) => {
                                  const pct = Math.max(0, Math.min(100, Math.round((val / 20) * 100)))
                                  return (
                                    <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                                      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                                        <span style={{ fontSize: 12.5, color: 'var(--text-2)', textTransform: 'capitalize' }}>{label}</span>
                                        {/* ui: keep — serif 15 breakdown numeral and its inline 11px "/20" unit: data display, not a heading or helper */}
                                        <span style={{ fontFamily: 'var(--serif)', fontSize: 15 }}>{val}<span style={{ fontSize: 11, color: 'var(--muted)' }}>/20</span></span>
                                      </div>
                                      <Meter value={pct / 100} height={1} radius="0" />
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {coverage != null && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: keywordOpen ? 6 : 0 }}>
                            <SectionHead boxed caret="end" open={keywordOpen} onToggle={() => setKeywordOpen((v) => !v)}
                              style={{ gap: 8, margin: '-2px -4px' }}>
                              <Label>Keyword coverage</Label>
                              <Rule style={{ flex: 1, minWidth: 8 }} />
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: coverage >= 75 ? 'var(--good)' : coverage >= 50 ? 'var(--warn)' : 'var(--bad)' }}>{coverage}%</span>
                            </SectionHead>
                            {keywordOpen && (
                              <>
                                <Meter value={coverage / 100} height={4} tone={coverage >= 75 ? 'good' : coverage >= 50 ? 'warn' : 'bad'} />
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 3 }}>
                                  <Helper>{(rpt.matched_keywords || []).length} matched · {(rpt.missing_keywords || []).length} missing</Helper>
                                  {(rpt.matched_keywords || []).length > 0 && <Link onClick={() => setShowMatched((v) => !v)}>{showMatched ? 'Hide matched' : 'Show matched'}</Link>}
                                </div>
                                {/* ui: keep — mono keyword tags (Tag role), not controls */}
                                {showMatched && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingTop: 2 }}>{(rpt.matched_keywords || []).map((w, k) => <span key={k} style={{ fontFamily: 'var(--mono)', fontSize: 10.5, padding: '3px 7px', borderRadius: 'var(--radius-control)', background: 'var(--accent-soft)', color: 'var(--good)' }}>{w}</span>)}</div>}
                                {/* ui: keep — mono keyword tags (Tag role), not controls */}
                                {(rpt.missing_keywords || []).length > 0 && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingTop: 2 }}>{(rpt.missing_keywords || []).map((w, k) => <span key={k} style={{ fontFamily: 'var(--mono)', fontSize: 10.5, padding: '3px 7px', borderRadius: 'var(--radius-control)', background: 'var(--bad-soft)', color: 'var(--bad)' }}>{w}</span>)}</div>}
                              </>
                            )}
                          </div>
                        )}

                        {reqRows.length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: reqOpen ? 9 : 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                              <SectionHead boxed caret="end" open={reqOpen} onToggle={() => setReqOpen((v) => !v)}
                                style={{ gap: 11, flex: '1 1 auto', minWidth: 0, margin: '-2px -4px' }}>
                                <Label>Requirement mapping</Label>
                                <Helper>{reqMet} of {reqRows.length} met</Helper>
                              </SectionHead>
                              {reqOpen && (
                                // ui: keep — a two-cell segmented filter track: one shared border run,
                                // overflow hidden, its cells are toggle cells rather than Pills.
                                <div style={{ marginLeft: 'auto', display: 'flex', border: '1px solid var(--edge)', borderRadius: 'var(--radius-control)', overflow: 'hidden' }}>
                                  {[['all', `All ${reqRows.length}`], ['gaps', `Gaps ${reqRows.length - reqMet}`]].map(([id, label]) => <div key={id} onClick={() => setReqFilter(id)} style={{ height: 24, padding: '0 11px', display: 'flex', alignItems: 'center', fontSize: 11.5, cursor: 'pointer', background: reqFilter === id ? 'var(--accent)' : 'transparent', color: reqFilter === id ? 'var(--accent-ink)' : 'var(--text-2)' }}>{label}</div>)}
                                </div>
                              )}
                            </div>
                            {reqOpen && (
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <TableHead height="auto" pad="0 0 6px" style={{ gap: 14, alignItems: 'flex-start', background: 'transparent' }}>
                              <span style={{ flex: 1.05 }}>Requirement</span><span style={{ flex: 1.1 }}>Résumé match</span><span style={{ flex: '0 0 34px', textAlign: 'center' }}>Status</span>
                            </TableHead>
                            {reqRows.filter((r) => reqFilter === 'all' || !r.matched).map((r, k) => (
                              // `align="normal"` because a wrapped requirement must not
                              // centre against its one-line verdict; `height="auto"` because
                              // this row is padded, not fixed.
                              <TableRow key={k} height="auto" pad="8px 0" size="md" align="normal" style={{ gap: 14 }}>
                                <span style={{ flex: 1.05, minWidth: 0 }}>{r.requirement}</span>
                                <span style={{ flex: 1.1, minWidth: 0, color: 'var(--muted)' }}>{r.cv_evidence || r.cv_match || '—'}</span>
                                <span style={{ flex: '0 0 34px', textAlign: 'center', color: r.matched ? 'var(--good)' : 'var(--bad)' }}>{r.matched ? '✓' : '✕'}</span>
                              </TableRow>
                            ))}
                            </div>
                            )}
                          </div>
                        )}

                        {(rpt?.hard_blockers || []).length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '11px 13px', border: '1px solid var(--bad)', borderRadius: 'var(--radius-cell)' }}>
                            {/* ui: keep — --bad 10/600 uppercase: neither the ink nor the weight Label carries */}
                            <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--bad)', fontWeight: 600 }}>Hard blockers</span>
                            {(rpt.hard_blockers || []).map((b, k) => <div key={k} style={{ display: 'flex', gap: 9, fontSize: 12.5, lineHeight: '18px', color: 'var(--text-2)' }}><span style={{ color: 'var(--bad)' }}>!</span><span>{b}</span></div>)}
                          </div>
                        )}
                        {rpt?.ats_tip && (
                          <Card style={{ display: 'flex', gap: 11, padding: '12px 14px', background: 'var(--surface-2)' }}>
                            <Label style={{ flex: '0 0 auto', paddingTop: 2 }}>ATS tip</Label>
                            <span style={{ flex: 1, fontSize: 12.5, lineHeight: '18px', color: 'var(--text-2)' }}>{rpt.ats_tip}</span>
                          </Card>
                        )}
                        {(d.fit_gaps || []).length > 0 && !reqRows.length && <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{(d.fit_gaps || []).map((g, k) => <div key={k} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--bad)' }}>✕</span><span>{g}</span></div>)}</div>}
                        {!rpt && !(d.fit_gaps || []).length && !(d.fit_strengths || []).length && <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>This report was scored at Light depth — rescore at Full depth for the keyword and requirement breakdown.</span>}
                      </div>
                    </div>
                  )}
                </div>
              )}
              </div>
              </div>

              {/* unscored band — mirrors the report band's placement + height */}
              {!dScored && !running && !anaCollapsed && (
                <div style={{ flex: '0 0 auto', borderBottom: '1px solid var(--line)', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 30px 8px 4px' }}>
                  <span style={{ flex: '0 0 auto', width: 19 }} />
                  <ScoreRing value={null} size="sm" label="No fit" style={{ marginLeft: -4 }} />
                  <div style={{ flex: 1, minWidth: 0, fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-2)' }}>Not scored yet</span>
                    <span style={{ color: 'var(--muted)' }}>{' '}Score against your résumés for the </span>
                    <span style={{ color: 'var(--accent)' }}>fit breakdown, requirements and keywords</span>
                  </div>
                  <Button size="xs" onClick={() => openRescore(d)}>Score this role</Button>
                </div>
              )}
              {running && !anaCollapsed && (
                <div style={{ flex: '0 0 auto', borderBottom: '1px solid var(--line)', background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', gap: 9, padding: '8px 30px 8px 4px' }}>
                  <span style={{ flex: '0 0 auto', width: 19 }} />
                  {/* F6: the band's busy ring is the same primitive as the row's, so the
                      two loading states cannot drift apart again */}
                  <ScoreRing busy size="sm" style={{ marginLeft: -4 }} />
                  <div style={{ flex: 1, minWidth: 0, fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-2)' }}>Scoring in progress</span>
                    <span style={{ color: 'var(--muted)' }}>{' '}This continues in the background if you navigate away.</span>
                  </div>
                </div>
              )}

              {/* posting area — always mounted (display toggled, not unmounted) so the
                  iframe isn't reloaded each time the report is opened/closed */}
              <div style={{ flex: 1, minHeight: 0, overflow: 'auto', display: reportCovers ? 'none' : 'flex', flexDirection: 'column' }} className="v2-scroll">
                  {/* live / cached posting — full-bleed iframe */}
                  <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                    {dCached && (
                      <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 9, padding: '9px 30px', borderBottom: '1px solid var(--line)', background: 'var(--surface-2)' }}>
                        <span style={{ fontSize: 12, color: viewCached ? 'var(--accent)' : 'var(--muted)' }}>{viewCached ? 'Cached snapshot · captured when you applied' : 'Live posting'}</span>
                        <Segmented variant="inset" ariaLabel="Posting view" value={viewCached ? 'cached' : 'live'}
                          onChange={(v) => setViewCached(v === 'cached')} style={{ marginLeft: 'auto' }}
                          options={[{ value: 'live', label: 'Live' }, { value: 'cached', label: 'Cached' }]} />
                      </div>
                    )}
                    {viewCached && dCached ? (
                      <iframe title="cached" srcDoc={cachedHtml || '<p style="padding:16px;font-family:sans-serif">Loading cached snapshot…</p>'} sandbox="allow-same-origin" style={{ flex: 1, width: '100%', border: 'none', background: 'var(--iframe-bg)' }} />
                    ) : frameSrc ? (
                      /* optimistic: always try the live frame; only a confirmed block swaps it out.
                         F7: `key` remounts the frame per job/src, so the previous posting is gone
                         the instant the selection changes; the cover below fills the gap until
                         onLoad fires. The frame keeps its own size underneath (the cover is
                         absolute inside the pane), so nothing shifts and load still fires. */
                      <div style={{ flex: 1, minHeight: 0, position: 'relative', display: 'flex' }}>
                        <iframe key={`${frameJobId}|${frameSrc}`} title="posting" src={frameSrc}
                          onLoad={() => settleFrame(frameJobId)} onError={() => settleFrame(frameJobId)}
                          sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
                          style={{ flex: 1, width: '100%', border: 'none', background: 'var(--iframe-bg)' }} />
                        {frameLoadId === frameJobId && (
                          <div style={{ position: 'absolute', inset: 0, background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                            <Spinner size={12} />
                            <Helper>{`Loading ${hostOf(frameSrc).replace(/^www\./, '')} …`}</Helper>
                          </div>
                        )}
                      </div>
                    ) : d.url ? (
                      /* frame-blocked — canonical design panel */
                      <div style={{ flex: '1 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '44px 30px', minHeight: 0 }}>
                        <div style={{ maxWidth: '44ch', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 11, textAlign: 'center' }}>
                          {/* ui: keep — dashed 44px warning glyph, not an add-line */}
                          <div style={{ width: 44, height: 44, border: '1px dashed var(--edge)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, color: 'var(--muted)' }}>▲</div>
                          <Heading>This page can't be shown here</Heading>
                          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--text-2)' }}>{d.company} does not allow its page to be shown inside another site. {dCached ? 'You applied to this role, so a cached snapshot is available.' : 'Open it in a new tab, or install the Navigator extension, which removes that restriction.'}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
                            {/* ui: keep — native <a href target=_blank>; Button renders a div and would drop the anchor */}
                            <a href={d.url} target="_blank" rel="noopener noreferrer" style={{ height: 34, padding: '0 16px', borderRadius: 'var(--radius-control)', background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500 }}>Open in new tab ↗</a>
                            {/* ui: keep — h34 to match the native anchor it sits beside (which stays inline) */}
                            {dCached && <div onClick={() => setViewCached(true)} className="v2-act" style={{ height: 34, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>View cached snapshot</div>}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>No posting URL captured for this job.</div>
                    )}
                  </div>
                </div>
            </>
          )}
        </section>
      </div>

      {/* create résumé copy modal — method (tailor / copy) + base pick */}
      {picker && (() => {
        const single = picker.jobs.length === 1 ? picker.jobs[0] : null
        const existing = single?.tailored_resume_id
        return (
          // escape={false}: the Feed closes every overlay from one handler that
          // stands down while a ConfirmDialog is up (OPEN-08, above)
          <ModalPanel width={436} onClose={() => setPicker(null)} escape={false} zIndex={60} style={{ overflow: 'hidden' }}>
              {/* header */}
              <HeaderRow align="stretch" pad="20px 24px 16px" style={{ flexDirection: 'column', gap: 5 }}>
                <Label>Create résumé copy</Label>
                <Heading size={19}>{single ? single.title : `${picker.jobs.length} selected roles`}</Heading>
                {single?.company && <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{single.company}</span>}
              </HeaderRow>
              {/* existing-copy banner */}
              {existing && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 24px', background: 'var(--accent-soft)', borderBottom: '1px solid var(--line)', fontSize: 12.5, color: 'var(--text-2)' }}>
                  <span style={{ flex: '0 0 auto', color: 'var(--accent)' }}>✦</span>
                  <span style={{ flex: 1, minWidth: 0 }}>A tailored copy already exists for this job.</span>
                  <Link onClick={() => { setPicker(null); openTailored(single) }} style={{ flex: '0 0 auto' }}>Open it ↗</Link>
                </div>
              )}
              {/* body */}
              <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <Label>Method</Label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {[['tailor', '✦ Tailor with AI', 'Rewrites bullets to match the posting · uses the LLM', undefined], ['copy', '⧉ Copy with tracked links', 'Exact duplicate with tracked links · instant', 'tracked links — short links that record when a recruiter opens them']].map(([m, label, help, tip]) => {
                      const on = cvMode === m
                      return (
                        <div key={m} onClick={() => pickMethod(m)} title={tip} style={{ flex: 1, padding: '10px 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 'var(--radius-cell)', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <span style={{ fontSize: 13, fontWeight: 500, color: on ? 'var(--accent)' : 'var(--text)' }}>{label}</span>
                          <Helper>{help}</Helper>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <Label>Base résumé</Label>
                  {cvBases.length === 0 ? <span style={{ fontSize: 13, color: 'var(--muted)' }}>No base résumés found.</span>
                    : cvBases.map((r) => {
                      const on = cvBase === r.id
                      return (
                        // ui: keep — a selectable choice card with a radio slot; v2-act is the choice-card hover.
                        <div key={r.id} className="v2-act" onClick={() => setCvBase(r.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, borderRadius: 'var(--radius-cell)', cursor: 'pointer', fontSize: 13.5 }}>
                          {/* ui: keep — radio indicator, not a status dot */}
                          <span style={{ flex: '0 0 auto', width: 15, height: 15, borderRadius: 'var(--radius-control)', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 'var(--radius-control)', background: on ? 'var(--accent)' : 'transparent' }} /></span>
                          <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</span>
                          {r.id === 'persona' && <Helper style={{ flex: '0 0 auto' }}>from Persona</Helper>}
                        </div>
                      )
                    })}
                </div>
              </div>
              {/* footer */}
              <FooterRow variant="wide">
                <Helper>{cvMode === 'tailor' ? 'Runs the LLM on the résumé' : 'Instant · no LLM cost · appears in Résumés'}</Helper>
                <Button variant="secondary" size="sm" onClick={() => setPicker(null)} style={{ marginLeft: 'auto' }}>Cancel</Button>
                <Button size="sm" onClick={() => runResume(cvMode, picker.jobs, cvBase)} disabled={cvBase == null}>{cvMode === 'tailor' ? 'Tailor résumé' : 'Create copy'}</Button>
              </FooterRow>
          </ModalPanel>
        )
      })()}

      {/* rescore modal — pick résumés + depth */}
      {rescoreJob && (
        // escape={false}: as the picker above — the screen owns Escape.
        <ModalPanel width={436} onClose={() => setRescoreJob(null)} escape={false} zIndex={60} style={{ overflow: 'hidden' }}>
            {/* header */}
            <HeaderRow align="stretch" pad="20px 24px 16px" style={{ flexDirection: 'column', gap: 5 }}>
              <Label>{rescoreJob.verb} against résumés</Label>
              <Heading size={19}>{rescoreJob.title}</Heading>
              {rescoreJob.company && <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{rescoreJob.company}</span>}
            </HeaderRow>
            {/* body */}
            <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <Label>Résumés</Label>
                  <Helper style={{ marginLeft: 'auto' }}>{rescoreSel.length} selected</Helper>
                </div>
                {rescoreOpts.length === 0 ? <span style={{ fontSize: 13, color: 'var(--muted)' }}>No résumés available.</span>
                  : rescoreOpts.map((o) => {
                    const on = rescoreSel.includes(o.id)
                    return (
                      // ui: keep — a selectable choice card with a tick slot; v2-act is the choice-card hover.
                      <div key={o.id} className="v2-act" onClick={() => setRescoreSel((prev) => prev.includes(o.id) ? prev.filter((x) => x !== o.id) : [...prev, o.id])}
                        style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, borderRadius: 'var(--radius-cell)', cursor: 'pointer', fontSize: 13.5 }}>
                        <span style={{ flex: '0 0 auto', width: 17, height: 17, borderRadius: 'var(--radius-mini)', border: on ? 'none' : '1px solid var(--edge)', background: on ? 'var(--accent)' : 'transparent', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>{on ? '✓' : ''}</span>
                        <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.name}</span>
                        <Helper style={{ flex: '0 0 auto' }}>{o.note}</Helper>
                      </div>
                    )
                  })}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Label>Depth</Label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[['light', 'Light', 'Scores only'], ['full', 'Full', 'Report + keywords']].map(([v, label, help]) => {
                    const on = rescoreDepth === v
                    return (
                      <div key={v} onClick={() => setRescoreDepth(v)} style={{ flex: 1, padding: '10px 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 'var(--radius-cell)', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
                        <Helper>{help}</Helper>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
            {/* footer */}
            <FooterRow variant="wide">
              <Helper>Runs in the background</Helper>
              <Button variant="secondary" size="sm" onClick={() => setRescoreJob(null)} style={{ marginLeft: 'auto' }}>Cancel</Button>
              <Button size="sm" onClick={runRescore} disabled={!rescoreSel.length} title={rescoreSel.length ? undefined : 'Pick at least one résumé'}>Run scoring</Button>
            </FooterRow>
        </ModalPanel>
      )}

      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}

      {/* toasts (progress + undo) */}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}
