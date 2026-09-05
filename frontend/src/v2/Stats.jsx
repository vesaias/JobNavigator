import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { ResponsiveContainer, Sankey, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import { useEscape, useSettled, useWarm, NBSP } from './hooks'
import { Card, GlyphBadge, Heading, HeaderRow, Helper, Label, Link, Menu, MenuItem, Meter, Mono, PageTitle, Pill as UiPill, Spinner, TableHead, TableRow } from './ui'
import './theme.css'

// Stats reads the pipeline back: funnel, scorer, LLM costs, scheduler activity.
// Score averages and run result summaries come from the newer endpoint fields.

const PERIODS = [[1, '1d'], [7, '7d'], [30, '30d'], [0, 'all']]
// Both logs page via limit+offset; the control hides itself when a page comes back short.
const RUN_PAGE = 30
const ACT_PAGE = 50
const BUCKET_COLOR = {
  // --line is a border token; as a fill it vanished into the card in dark mode.
  '0-20': 'var(--line-strong)', '21-40': 'var(--sand)', '41-60': 'var(--gold)',
  '61-80': 'var(--funnel-mid)', '81-100': 'var(--accent)',
}
const TYPE_CLASS = {
  scrape: 'sm-keyword', h1b: 'sm-lipersonal', cv_score: 'sm-levels',
  email: 'sm-freehire', telegram: 'sm-jobright',
}
const TYPE_OPTS = [['', 'All types'], ['scrape', 'Scrape'], ['h1b', 'H-1B'], ['cv_score', 'Résumé score'], ['email', 'Email'], ['telegram', 'Telegram']]

// v2 draws controls as span/div, so spread kb(fn) on one to make it focusable and
// keyboard-operable; the focus ring is theme.css's `[tabindex="0"]:focus-visible`.
const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

const money = (n) => (n == null ? '—' : n === 0 || n >= 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(n < 0.01 ? 4 : 3)}`)
const int = (n) => (n == null ? '—' : Number(n).toLocaleString('en-US'))
// Timeline keys are calendar dates in the viewer's zone; `new Date('2026-09-02')` parses
// as UTC midnight and renders a day early west of UTC — build the Date from parts instead.
const localKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const dayLabel = (key) => {
  const p = String(key).split('-').map(Number)
  if (p.length === 3 && p.every((n) => Number.isFinite(n))) {
    try { return new Date(p[0], p[1] - 1, p[2]).toLocaleDateString('en-GB', { timeZone: TZ, month: 'short', day: 'numeric' }) } catch { return key }
  }
  try { return new Date(key).toLocaleDateString('en-GB', { timeZone: TZ, month: 'short', day: 'numeric' }) } catch { return key }
}
// The viewer's own zone — v1 hardcoded Europe/Berlin, which is only right for one person.
const TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone } catch { return 'UTC' } })()
const TZ_SHORT = (() => {
  try { return new Intl.DateTimeFormat('en-GB', { timeZone: TZ, timeZoneName: 'short' }).formatToParts(new Date()).find((x) => x.type === 'timeZoneName')?.value || TZ }
  catch { return TZ }
})()
const when = (iso) => {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('en-GB', { timeZone: TZ, month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).replace(',', ' ·') }
  catch { return iso }
}
const dur = (s) => (s == null ? '—' : s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`)
const ago = (iso) => {
  if (!iso) return null
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`
}
// Turn a 5-field cron into English; anything else (including "Every 90 min") passes through.
const decodeCron = (expr) => {
  if (!expr || expr.includes('Every')) return expr || '—'
  const p = expr.trim().split(/\s+/)
  if (p.length !== 5) return expr
  const [min, hour, day, month, dow] = p
  const DOW = { 0: 'Sun', 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun' }
  let t
  if (hour !== '*' && min !== '*') t = `at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  else if (hour !== '*') t = `at ${hour.padStart(2, '0')}:00`
  else if (min.startsWith('*/')) t = `every ${min.slice(2)} min`
  else if (hour.startsWith('*/')) t = `every ${hour.slice(2)}h`
  else return expr
  if (dow !== '*') return `${DOW[dow] || dow} ${t}`
  if (day !== '*') return `Day ${day} ${t}`
  if (month !== '*') return `Month ${month} ${t}`
  return `Daily ${t}`
}

// ui: keep — H serves only the run-history/activity-log tabs (kb() control + accent underline); Heading covers everything else.
const H = { fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 500, letterSpacing: '-.015em' }
// ui: keep — COL serves only the LLM-cost card's 9px column strip (h22/9px, smaller than TableHead's 9.5 step) inside a scroll-gutter head.
const COL = { fontSize: 9.5, lineHeight: '14px', letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }
// ui: keep — MONO covers the funnel count, LLM model cell and peak caption, each overriding font-size (11.5/10/10) vs Mono's 10.5 step; everything else uses <Mono>.
const MONO = { fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px' }
// Same badge idiom as Companies: mono, 9.5px, .05em, 2px 7px, full radius.
const BADGE = { fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', lineHeight: '14px', whiteSpace: 'nowrap' }
const Pill = ({ children, bg, fg }) => (
  <span style={{ ...BADGE, background: bg, color: fg }}>{children}</span>
)
// The pager both logs share.
const LoadMore = ({ onClick, busy }) => (
  <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 20px 12px' }}>
    <UiPill size="sm" disabled={!!busy} ariaBusy={!!busy} onClick={onClick}>
      {busy && <Spinner size={9} color="currentColor" />}
      {busy ? 'Loading…' : 'Load more'}
    </UiPill>
  </div>
)
// FastAPI's `detail` is a plain string for HTTPException; append it when present.
const errSuffix = (e) => (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '')

export default function Stats() {
  const [stats, setStats] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [scores, setScores] = useState(null)
  const [best, setBest] = useState(null)
  const [flows, setFlows] = useState([])
  const [costs, setCosts] = useState(null)
  const [period, setPeriod] = useState(30)
  const [jobs, setJobs] = useState([])
  const [runs, setRuns] = useState([])
  const [runsMore, setRunsMore] = useState(false)
  const [activity, setActivity] = useState([])
  const [actMore, setActMore] = useState(false)
  const [moreBusy, setMoreBusy] = useState(false)
  const [tab, setTab] = useState('runs')
  const [flowView, setFlowView] = useState('bar')
  const [sweep, setSweep] = useState(null)
  const [failing, setFailing] = useState(0)
  const [actType, setActType] = useState('')
  const [actQuery, setActQuery] = useState('')
  const [typeOpen, setTypeOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [coreErr, setCoreErr] = useState(false)   // any core stats request failed
  const [schedErr, setSchedErr] = useState(false) // /scheduler/jobs failed
  const [triggering, setTriggering] = useState(new Set())
  const pollRef = useRef(null)
  const runningRef = useRef(false)
  const qRef = useRef(null)
  const runsPaged = useRef(false)   // Load more was used, so the poll must not shrink the list back
  const runsCardRef = useRef(null)  // the rail links here as /v2/stats#runs
  const { hash } = useLocation()
  // Schedules columns are fixed-width with no scroller, so below ~1100px Run now spilled
  // past the border. Measure the card and drop columns right-to-left as it narrows.
  const schedRef = useRef(null)
  const [schedW, setSchedW] = useState(1200)
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()
  // Same shared Escape hook every overlay uses; the second argument gates the
  // listener on the menu being open.
  useEscape(() => setTypeOpen(false), typeOpen)

  const loadCore = useCallback(async () => {
    let anyFailed = false
    const get = (u, params) => api.get(u, { params }).then(({ data }) => data).catch((e) => { console.error(u, e); anyFailed = true; return null })
    // one Promise.all round — sweep and health calls run alongside the rest.
    const [s, tl, sd, bj, fl, sw, he] = await Promise.all([
      get('/stats'),
      get('/stats/timeline', { days: 30 }),
      get('/stats/score-distribution', { detail: true }),
      get('/jobs', { status: 'new,saved', sort_by: 'score', limit: 1 }),
      get('/stats/sankey'),
      get('/monitor/history', { limit: 1, job_type: 'scrape_all' }),
      get('/health/entities'),
    ])
    setSweep((sw || [])[0] || null)
    setFailing(((he?.companies || []).length) + ((he?.searches || []).length))
    // Clear the node on failure instead of keeping the previous value — int(null)
    // renders "—", so a dead backend doesn't look like a plausible dashboard.
    setStats(s)
    setTimeline(tl)
    setScores(sd)
    const list = bj?.jobs || bj?.items || (Array.isArray(bj) ? bj : [])
    setBest(list[0] || null)
    setFlows(Array.isArray(fl) ? fl : [])
    setCoreErr(anyFailed)
    if (anyFailed) pushToast({ kind: 'error', msg: 'Some stats failed to load — try Refresh' })
  }, [pushToast])

  const loadLive = useCallback(async () => {
    const [j, r] = await Promise.all([
      api.get('/scheduler/jobs').then(({ data }) => data).catch(() => null),
      api.get('/monitor/history', { params: { limit: RUN_PAGE } }).then(({ data }) => data).catch(() => null),
    ])
    // Drop stale rows and flag the failure explicitly — an empty table here reads
    // exactly like a correctly configured, idle scheduler.
    if (j) { setJobs(j); setSchedErr(false); runningRef.current = j.some((x) => x.running) }
    else { setJobs([]); setSchedErr(true); runningRef.current = false }
    // the poll only ever re-reads the first page, so rows fetched by Load more sit
    // past it and have to survive the refresh
    if (r) {
      setRuns((prev) => (prev.length > r.length ? [...r, ...prev.slice(r.length)] : r))
      if (!runsPaged.current) setRunsMore(r.length >= RUN_PAGE)
    }
  }, [])

  const loadActivity = useCallback(() => {
    api.get('/activity-log', { params: { limit: ACT_PAGE, ...(actType && { type: actType }), ...(actQuery.trim() && { company: actQuery.trim() }) } })
      .then(({ data }) => { const rows = data || []; setActivity(rows); setActMore(rows.length >= ACT_PAGE) })
      // A failed reload needs its own toast — otherwise old/empty rows have nothing to explain them.
      .catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the activity log' }) })
  }, [actType, actQuery])

  // Core figures, the live half and LLM spend settle together as one `ready` flag
  // so the header line doesn't grow a late " · $x on LLM calls" tail after paint.
  const { ready } = useSettled([
    () => loadCore(),
    () => loadLive(),
    () => api.get('/stats/llm-costs', { params: { days: period } }).then(({ data }) => setCosts(data)).catch(() => setCosts(null)),
  ])
  // a later period change is an explicit action, so it reloads on its own
  const firstCosts = useRef(true)
  useEffect(() => {
    if (firstCosts.current) { firstCosts.current = false; return }
    api.get('/stats/llm-costs', { params: { days: period } }).then(({ data }) => setCosts(data)).catch(() => setCosts(null))
  }, [period])
  // debounce the company box — v1 fired a request per keystroke
  useEffect(() => { clearTimeout(qRef.current); qRef.current = setTimeout(loadActivity, 300); return () => clearTimeout(qRef.current) }, [loadActivity])

  // poll the live half only: 3s while something runs, 10s otherwise
  useEffect(() => {
    const poll = () => { loadLive(); pollRef.current = setTimeout(poll, runningRef.current ? 3000 : 10000) }
    pollRef.current = setTimeout(poll, 3000)
    return () => clearTimeout(pollRef.current)
  }, [loadLive])

  useEffect(() => {
    const el = schedRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(([en]) => setSchedW(en.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [ready])

  const refresh = async () => {
    if (refreshing) return
    setRefreshing(true)
    await Promise.all([loadCore(), loadLive()])
    loadActivity()
    // Behind the Refresh button — a failure that leaves old figures on screen has to say so.
    api.get('/stats/llm-costs', { params: { days: period } }).then(({ data }) => setCosts(data)).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not refresh the LLM costs' }) })
    setRefreshing(false)
  }

  // Toast the real outcome (202/409/500 differ) and drop the optimistic "Running"
  // state immediately when nothing was actually started.
  const trigger = async (job) => {
    if (!job.trigger_url) return
    const clear = () => setTriggering((p) => { const n = new Set(p); n.delete(job.id); return n })
    setTriggering((p) => new Set(p).add(job.id))
    try {
      await api.post(job.trigger_url)
      pushToast({ kind: 'progress', msg: `${job.name} started.` })
      loadLive()
      setTimeout(clear, 4000)
    } catch (e) {
      console.error('trigger', e)
      clear()
      pushToast({ kind: 'error', msg: e.response?.status === 409 ? `${job.name} is already running.` : `Could not start ${job.name}` + errSuffix(e) })
    }
  }

  // One more page of whichever log you're looking at, appended.
  const moreRuns = async () => {
    if (moreBusy) return
    setMoreBusy(true)
    try {
      const { data } = await api.get('/monitor/history', { params: { limit: RUN_PAGE, offset: runs.length } })
      const rows = data || []
      runsPaged.current = true
      setRuns((prev) => [...prev, ...rows])
      setRunsMore(rows.length >= RUN_PAGE)
    } catch (e) {
      console.error('more runs', e)
      pushToast({ kind: 'error', msg: 'Could not load more runs' + errSuffix(e) })
    } finally { setMoreBusy(false) }
  }
  const moreActivity = async () => {
    if (moreBusy) return
    setMoreBusy(true)
    try {
      const { data } = await api.get('/activity-log', { params: { limit: ACT_PAGE, offset: activity.length, ...(actType && { type: actType }), ...(actQuery.trim() && { company: actQuery.trim() }) } })
      const rows = data || []
      setActivity((prev) => [...prev, ...rows])
      setActMore(rows.length >= ACT_PAGE)
    } catch (e) {
      console.error('more activity', e)
      pushToast({ kind: 'error', msg: 'Could not load more activity' + errSuffix(e) })
    } finally { setMoreBusy(false) }
  }

  // The rail's health line links to /v2/stats#runs, the last card on a ~2400px page;
  // scroll there once the cards exist (the ref is null before that).
  useEffect(() => {
    if (!ready || hash !== '#runs') return
    runsCardRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [ready, hash])

  // ── derived ───────────────────────────────────────────────────────────────
  const st = stats?.application_statuses || {}
  const inPlay = Math.max(0, (stats?.total_applications || 0) - ((st.rejected || 0) + (st.ghosted || 0) + (st.withdrawn || 0)))
  // cv_scores can be {} (unscored); Math.max() of an empty list is -Infinity,
  // which rendered as the literal string "-Infinity" in the tile.
  const bestScore = useMemo(() => {
    const nums = Object.values(best?.cv_scores || {}).filter((v) => typeof v === 'number')
    return nums.length ? String(Math.round(Math.max(...nums))) : '—'
  }, [best])

  // fill the 30-day window: the API omits days with no discoveries
  const series = useMemo(() => {
    const byDate = Object.fromEntries((timeline || []).map((r) => [r.date, r]))
    const out = []
    for (let i = 29; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i)
      // Local calendar date, not UTC — toISOString() shifted all 30 buckets a day
      // west of UTC, skewing "New this week" and the peak label with them.
      const key = localKey(d)
      const r = byDate[key]
      out.push({ date: key, total: r?.total || 0, applied: r?.applied || 0 })
    }
    return out
  }, [timeline])
  const weekly = useMemo(() => {
    const sum = (a) => a.reduce((n, r) => n + r.total, 0)
    return { now: sum(series.slice(-7)), prev: sum(series.slice(-14, -7)) }
  }, [series])
  const peak = useMemo(() => series.reduce((m, r) => (r.total > (m?.total ?? -1) ? r : m), null), [series])

  // A funnel needs "ever reached", not "currently in": application_statuses is a snapshot
  // that undercounts stages, so downstream stages use the transition graph; bar widths are relative to Applied.
  const reached = useMemo(() => {
    const to = {}
    for (const f of flows) to[f.target] = (to[f.target] || 0) + (f.value || 0)
    return to
  }, [flows])
  const funnel = useMemo(() => {
    const applied = stats?.total_applications || 0
    // With no transition history a row falls back to the status snapshot (a
    // different question: "currently in" vs "ever reached") — flag those rows.
    const pick = (k) => (reached[k] ? { count: reached[k], snapshot: false } : { count: st[k] || 0, snapshot: !!st[k] })
    const rows = [
      // One stage, one colour: funnel rows, Sankey nodes and Applications stage
      // dots all read the same --stage-* tokens (kept in sync across files).
      { label: 'Applied', count: applied, snapshot: false, color: 'var(--stage-applied)' },
      { label: 'Interview', ...pick('interview'), color: 'var(--stage-interview)' },
      { label: 'Offer', ...pick('offer'), color: 'var(--stage-offer)' },
      { label: 'Rejected', ...pick('rejected'), color: 'var(--stage-rejected)' },
    ]
    const base = Math.max(1, applied)
    // `frac` is what Meter takes (0–1); the 2% floor keeps a non-zero row visible
    // and an empty row at nothing, exactly as the percentage string did.
    return rows.map((r) => ({
      ...r,
      frac: Math.min(100, Math.max(r.count ? 2 : 0, Math.round((r.count / base) * 100))) / 100,
    }))
  }, [stats, st, reached])
  const conv = (a, b) => (a ? `${Math.round((b / a) * 100)}%` : '—')

  const RANK = { new: 0, saved: 1, applied: 2, interview: 3, offer: 4, rejected: 5, ghosted: 5, withdrawn: 5 }
  const sankey = useMemo(() => {
    const fwd = flows.filter((d) => d.source && d.target && d.source !== d.target && (RANK[d.source] ?? 99) < (RANK[d.target] ?? 99))
    if (!fwd.length) return null
    const names = [...new Set(fwd.flatMap((d) => [d.source, d.target]))]
    const links = fwd.map((d) => ({ source: names.indexOf(d.source), target: names.indexOf(d.target), value: d.value }))
      .filter((l) => l.source !== -1 && l.target !== -1 && l.value > 0)
    return links.length ? { nodes: names.map((name) => ({ name })), links } : null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flows])

  // scrape_all is the job you look at first, so it leads regardless of APScheduler order
  const ordered = useMemo(() => [...jobs].sort((a, b) => (a.id === 'scrape_all' ? -1 : b.id === 'scrape_all' ? 1 : 0)), [jobs])

  const buckets = scores?.buckets || []
  const maxBucket = Math.max(1, ...buckets.map((b) => b.count))
  const spend = costs?.total_cost_usd
  // widths each column needs, measured against the 250/132/140/132/110 grid + 40px padding
  const showId = schedW >= 830, showSched = schedW >= 700, showNext = schedW >= 560, showStatus = schedW >= 430

  // Warm start: the header line (last sweep, sources needing attention, spend) matches
  // the pre-refresh frame. Only the timestamp is cached — "3h ago" recomputes at render.
  const { warm: sub, style: subStyle } = useWarm('stats', ready ? {
    has: !!sweep, status: sweep?.status || null, at: sweep ? (sweep.finished_at || sweep.started_at) : null,
    failing, spend: spend == null ? null : spend, period,
  } : null, ready)
  const subLine = !sub ? NBSP : (
    <>
      {sub.has ? `Last scrape run ${sub.status === 'failed' ? 'failed ' : ''}${ago(sub.at) || '—'}` : 'No scrape recorded yet'}
      {sub.failing > 0 && <> · <span style={{ color: 'var(--warn)' }}>{sub.failing} source{sub.failing === 1 ? ' needs' : 's need'} attention</span></>}
      {sub.spend != null && <> · {money(sub.spend)} on LLM calls {sub.period ? `in ${sub.period}d` : 'all time'}</>}
    </>
  )
  // Volume, outcomes, scoring and spend already have cards below; the header carries
  // the one thing none of them shows — whether the pipeline ran and whether anything's broken.
  // ui: keep — 13/20px is outside Helper's 11.5/16 tolerance; the header column is pinned to integer line-heights.
  const subSpan = (
    <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', ...subStyle }}>{subLine}</span>
  )

  // The header is real chrome and draws immediately (warm-started where cached)
  // while the cards below wait on the single `ready` settle.
  if (!ready) return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <HeaderRow as="header" variant="screen" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Stats</PageTitle>
          {subSpan}
        </div>
      </HeaderRow>
    </div>
  )

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <HeaderRow as="header" variant="screen" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Stats</PageTitle>
          {subSpan}
        </div>
        {/* Consistency: retry/refresh is a Link here too, matching Companies/Searches/Settings —
            accent 11.5/500 at the canonical 17px line-height. */}
        <Link onClick={refresh} title="Reload every figure on this page"
          style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 7 }}>
          {refreshing
            ? <Spinner size={10} />
            : <span style={{ fontSize: 12 }}>↻</span>}
          Refresh
        </Link>
      </HeaderRow>
      {coreErr && (
        <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 12, padding: '8px 30px', background: 'var(--bad-soft)', borderBottom: '1px solid var(--line)', fontSize: 12.5, lineHeight: '18px', color: 'var(--bad)' }}>
          <GlyphBadge tone="bad" style={{ flex: '0 0 auto' }}>!</GlyphBadge>
          <span style={{ flex: 1 }}>Some numbers could not be loaded. They show “—” until the backend responds.</span>
          {/* Consistency: retry is a Link everywhere else, so it is one here too,
              with the dotted underline as its affordance. */}
          <Link onClick={refresh} style={{ flex: '0 0 auto', borderBottom: '1px dotted currentColor' }}>Try again</Link>
        </div>
      )}

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '18px 30px 30px', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* KPI strip */}
        <Card style={{ padding: 0, display: 'flex' }}>
          {[
            ['Total jobs', int(stats?.total_jobs), '', 'All jobs ever found, excluding ones removed by cleanup'],
            ['New this week', int(timeline ? weekly.now : null), timeline && weekly.prev ? `${weekly.now - weekly.prev >= 0 ? '+' : ''}${weekly.now - weekly.prev} vs previous period` : '', 'Discovered in the last 7 days'],
            ['Saved', int(stats?.saved_jobs), '', 'In your feed shortlist'],
            ['Applications', int(stats?.total_applications), `${inPlay} open`, 'Open = not rejected, ghosted or withdrawn'],
            ['Best open score', bestScore, bestScore === '—' ? '' : (best?.company || ''), 'Highest-scoring posting you haven’t applied to'],
          ].map(([label, value, sub, hint], i, arr) => (
            <div key={label} title={hint} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 11, padding: '14px 20px 10px', borderRight: `1px solid ${i === arr.length - 1 ? 'transparent' : 'var(--line-soft)'}` }}>
              <Label style={{ whiteSpace: 'nowrap' }}>{label}</Label>
              {/* ui: keep — KPI numeral is serif 27/30px, its own step (3px off PageTitle's 30, above Heading's 22). */}
              <span style={{ fontFamily: 'var(--serif)', fontSize: 27, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '30px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {/* lineHeight 1 on the sub-unit: at the numeral's 30px it baselines at a font-dependent
                    offset, growing the numeral to 33px (35px alt) and the whole strip with it. */}
                {value}{sub && <span style={{ marginLeft: 7, fontSize: 13, lineHeight: 1, color: String(sub).startsWith('+') ? 'var(--accent)' : 'var(--muted)' }}>{sub}</span>}
              </span>
            </div>
          ))}
        </Card>

        {/* funnel + score distribution */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {/* Fixed height: funnel and Sankey are different shapes; letting either size the
              card made the row jump on toggle. Both get the same 162px inside 230. */}
          <Card style={{ height: 230, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <Heading strong size={17}>Application funnel</Heading>
              <span style={{ flex: 1 }} />
              {sankey && (
                <span style={{ alignSelf: 'center', display: 'flex', gap: 3 }}>
                  {[['bar', 'Funnel'], ['sankey', 'Flow']].map(([id, label]) => {
                    const on = flowView === id
                    return <UiPill key={id} size="sm" on={on} onClick={() => setFlowView(id)}>{label}</UiPill>
                  })}
                </span>
              )}
            </div>
            {coreErr && !stats ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>Unavailable — the request failed</div> : flowView === 'sankey' && sankey ? (
              <div style={{ flex: 1, minHeight: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <Sankey data={sankey} nodePadding={18} nodeWidth={10} margin={{ top: 4, right: 112, left: 4, bottom: 4 }}
                    link={{ stroke: 'var(--stage-applied)', strokeOpacity: 0.22 }} node={<SankeyNode />}>
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-cell)', color: 'var(--text)', fontSize: 12 }} />
                  </Sankey>
                </ResponsiveContainer>
              </div>
            ) : (
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {funnel.map((f) => (
                <div key={f.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ flex: '0 0 76px', fontSize: 12, lineHeight: '18px', color: 'var(--text-2)' }}>{f.label}</span>
                  <Meter value={f.frac} height={22} tone={f.color} track="var(--surface-2)" radius="var(--radius-mini)"
                    style={{ flex: 1 }} ariaLabel={`${f.label}: ${f.count}`} />
                  <span style={{ flex: '0 0 40px', ...MONO, fontSize: 11.5, lineHeight: '18px', color: 'var(--text)', textAlign: 'right' }}>{f.count}</span>
                  {/* ui: keep — 9.5 is below Helper's 10.5 xs step; 18px line-height baselines it against the 22px funnel bar beside it. */}
                  {f.snapshot && <span title="No stage history for these applications. They are counted by current status only."
                    style={{ flex: '0 0 auto', fontSize: 9.5, lineHeight: '18px', color: 'var(--muted)', cursor: 'help' }}>snapshot</span>}
                </div>
              ))}
            </div>
            {/* ui: keep — 15px line-height fits two caveat lines inside the card's fixed 230px height; Helper's 16px would overflow it. */}
            <span style={{ fontSize: 11, lineHeight: '15px', color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: 2 }}>
              {/* the card's height is fixed, so the caveat replaces the "bars are
                  relative to Applied" clause rather than adding a third line */}
              <span>{funnel.some((f) => f.snapshot)
                ? 'Stage rows count every application that reached the stage. Snapshot rows count current status only.'
                : 'Each row counts applications that reached that stage. Bar length is relative to Applied.'}</span>
              <span>applied → interview {conv(stats?.total_applications, reached.interview || 0)} · interview → offer {conv(reached.interview || 0, reached.offer || 0)}</span>
            </span>
            </div>
            )}
          </Card>

          <Card style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <Heading strong size={17}>Score distribution</Heading>
              <Helper style={{ flex: 1 }}>{int(scores?.scored_count)} scored jobs · best résumé per job</Helper>
              {scores?.avg != null && (
                // lineHeight 1: baseline-aligned head — an 11px span on the row's 24px
                // line-height rides a font-dependent offset, growing the head 25→27px under alt.
                <span style={{ fontSize: 11, lineHeight: 1, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                  avg {scores.avg}
                  {scores.tailored_avg != null && <> · <span title={`Average score after tailoring, across the ${scores.tailored_count} jobs with a tailored copy`} style={{ color: 'var(--accent)', cursor: 'help' }}>tailored {scores.tailored_avg}</span></>}
                </span>
              )}
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 14, minHeight: 118, padding: '0 6px' }}>
              {buckets.map((b) => (
                <div key={b.range} title={`${b.count} jobs scored ${b.range}`} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                  <Mono line={14} tone="base">{b.count}</Mono>
                  <div style={{ width: '100%', height: Math.max(2, Math.round((b.count / maxBucket) * 96)), background: BUCKET_COLOR[b.range] || 'var(--accent)', borderRadius: '5px 5px 0 0' }} />
                  {/* ui: keep — an axis tick label under a bar, not body helper text */}
                  <span style={{ fontSize: 10, lineHeight: '14px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{b.range}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* timeline + llm costs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12 }}>
          <Card style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <Heading strong size={17}>New jobs · last 30 days</Heading>
              <Helper style={{ flex: 1 }}>daily arrivals across all sources</Helper>
              {/* --stage-applied is the applied series everywhere else in v2 (swatch solid,
                  as designed); legend swatches follow the strokes below, so "new" is --series-new too. */}
              {[['new', 'var(--series-new)'], ['applied', 'var(--stage-applied)']].map(([l, c]) => (
                // lineHeight 1: same baseline-alignment leak as the score head above —
                // these 11px legends on the row's 24px line-height grew it 27→29px alt
                <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, lineHeight: 1, color: 'var(--text-2)' }}>
                  <span style={{ width: 14, height: 2, background: c }} />{l}
                </span>
              ))}
            </div>
            {coreErr && !timeline ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>Unavailable — the request failed</div> : <Spark series={series} peak={peak} />}
          </Card>

          <Card style={{ height: 300, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0, overflow: 'hidden' }}>
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <Heading strong size={17}>LLM costs</Heading>
              <Helper title="OpenAI and Claude pricing info comes from a fixed table, OpenRouter from its catalog (updated every 12 h), Claude Code and Ollama counted as $0. Each call is priced when it is logged."
                style={{ cursor: 'help', borderBottom: '1px dotted var(--line-strong)' }}>how priced?</Helper>
              <span style={{ marginLeft: 'auto', alignSelf: 'center', display: 'flex', gap: 3 }}>
                {PERIODS.map(([id, label]) => {
                  const on = period === id
                  return <UiPill key={label} size="sm" on={on} onClick={() => setPeriod(id)}>{label}</UiPill>
                })}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 18 }}>
              {[['Spend', money(costs?.total_cost_usd)], ['Calls', int(costs?.total_calls)],
                ['Avg / call', costs?.total_calls ? money(costs.total_cost_usd / costs.total_calls) : '—']].map(([l, v]) => (
                <div key={l} style={{ display: 'flex', flexDirection: 'column' }}>
                  <Label>{l}</Label>
                  {/* ui: keep — serif 23/28px figure: not one of Heading's 18/19/22 steps */}
                  <span style={{ fontFamily: 'var(--serif)', fontSize: 23, lineHeight: '28px', letterSpacing: '-.02em' }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <div className="v2-gutter-head" style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', height: 22, ...COL, fontSize: 9, borderBottom: '1px solid var(--line-strong)' }}>
                <span style={{ flex: 1.1 }}>Purpose</span><span style={{ flex: 1.4 }}>Model</span>
                <span style={{ flex: '0 0 42px', textAlign: 'right' }}>Calls</span><span style={{ flex: '0 0 58px', textAlign: 'right' }}>Cost</span>
                <span title="Share of calls that reused a cached prompt" style={{ flex: '0 0 44px', textAlign: 'right' }}>Cache</span>
              </div>
              {/* takes whatever the fixed-height card leaves, so switching period
                  (2 rows at 1d, 13 at all-time) can't resize anything */}
              <div className="v2-scroll v2-gutter" style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              {(costs?.by_purpose || []).map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', height: 26, borderBottom: '1px solid var(--line-soft)', fontSize: 11, lineHeight: '16px' }}>
                  <span style={{ flex: 1.1, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 6 }}>{c.purpose}</span>
                  <span title={c.model} style={{ flex: 1.4, ...MONO, fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 6 }}>{c.model || '—'}</span>
                  <Mono line={16} tone="base" style={{ flex: '0 0 42px', textAlign: 'right' }}>{c.calls}</Mono>
                  <Mono line={16} tone="strong" style={{ flex: '0 0 58px', textAlign: 'right' }}>{money(c.cost_usd)}</Mono>
                  <Mono line={16} style={{ flex: '0 0 44px', textAlign: 'right', color: c.cache_involving ? 'var(--mono-ink-accent)' : 'var(--mono-ink-muted)' }}>{c.cache_involving ? `${Math.round(c.cache_hit_ratio * 100)}%` : '—'}</Mono>
                </div>
              ))}
              {!(costs?.by_purpose || []).length && <Helper style={{ display: 'block', padding: '14px 0' }}>No LLM calls in this period.</Helper>}
              </div>
            </div>
          </Card>
        </div>

        {/* schedules */}
        <Card ref={schedRef} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '14px 20px 10px', lineHeight: '24px' }}>
            <Heading strong size={17}>Schedules</Heading>
            <Helper>{schedErr ? 'intervals and crons are in Settings' : `${jobs.length} job${jobs.length === 1 ? '' : 's'} · next run shown in ${TZ_SHORT}, schedule set in UTC · edit intervals in Settings`}</Helper>
          </div>
          {schedErr ? (
            <div style={{ padding: '26px 20px 30px', borderTop: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>Unavailable — the request failed</div>
          ) : (<>
          <TableHead height={26} pad="0 20px" top style={{ background: 'transparent' }}>
            <span style={{ flex: '0 1 250px', minWidth: 0 }}>Job</span>
            {showId && <span style={{ flex: '0 0 132px' }}>Job ID</span>}
            {showSched && <span style={{ flex: '0 0 140px' }}>Schedule</span>}
            {showNext && <span style={{ flex: '0 0 132px' }}>Next run</span>}
            <span style={{ flex: 1, minWidth: 0 }}>{showStatus ? 'Status' : ''}</span>
            <span style={{ flex: '0 0 110px', textAlign: 'right' }}>Run</span>
          </TableHead>
          {ordered.map((j) => {
            const running = !!j.running || triggering.has(j.id)
            return (
              <TableRow key={j.id} height={38}>
                <span title={j.name} style={{ flex: '0 1 250px', minWidth: 0, fontSize: 12.5, lineHeight: '18px', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{j.name}</span>
                {showId && <Mono title={j.id} line={18} tone="muted" style={{ flex: '0 0 132px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.id}</Mono>}
                {showSched && <span title={j.schedule} style={{ flex: '0 0 140px', fontSize: 11.5, lineHeight: '18px', color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{decodeCron(j.schedule)}</span>}
                {showNext && <Mono line={18} tone="muted" style={{ flex: '0 0 132px' }}>{running ? 'now' : when(j.next_run)}</Mono>}
                <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {showStatus && (running
                    ? <Spinner size={9} />
                    /* ui: keep — 7px scheduler status dot (Dot role, migrates with Tag/Dot) */
                    : <span style={{ flex: '0 0 auto', width: 7, height: 7, borderRadius: 'var(--radius-control)', background: j.pending ? 'var(--warn)' : 'var(--funnel-low)' }} />)}
                  {showStatus && <span style={{ minWidth: 0, fontSize: 11.5, lineHeight: '18px', color: running ? 'var(--accent)' : 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {running ? `Running · ${dur(j.running?.elapsed_seconds || 0)}` : j.pending ? 'Pending' : 'Scheduled'}
                  </span>}
                </span>
                <span style={{ flex: '0 0 110px', display: 'flex', justifyContent: 'flex-end' }}>
                  {j.trigger_url
                    // ui: keep — Pill xs is the role, but this control's paint differs: no ground, pad 0 11 vs 0 9/0 10, gap 6 vs 5, and a running state that quiets border+ink instead of dimming via opacity.
                    ? <span onClick={() => !running && trigger(j)} {...kb(() => !running && trigger(j))} aria-disabled={running}
                        title={running ? `${j.name} is running` : `Run ${j.name} now`} aria-label={running ? `${j.name} is running` : `Run ${j.name} now`}
                        className={running ? '' : 'v2-bdc'} style={{ height: 25, padding: '0 11px', border: `1px solid ${running ? 'var(--line)' : 'var(--edge)'}`, borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, lineHeight: 1, color: running ? 'var(--edge)' : 'var(--text-2)', whiteSpace: 'nowrap', cursor: running ? 'default' : 'pointer' }}>
                        {running && <Spinner size={9} color="currentColor" />}
                        {running ? 'Running…' : 'Run now'}
                      </span>
                    : <Helper>—</Helper>}
                </span>
              </TableRow>
            )
          })}
          </>)}
        </Card>

        {/* run history / activity log */}
        <Card id="runs" ref={runsCardRef} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '12px 20px 10px' }}>
            {[['runs', 'Run history'], ['activity', 'Activity log']].map(([id, label]) => (
              <span key={id} onClick={() => { setTab(id); setTypeOpen(false) }} {...kb(() => { setTab(id); setTypeOpen(false) })} style={{ ...H, lineHeight: '24px', color: tab === id ? 'var(--text)' : 'var(--muted)', cursor: 'pointer', borderBottom: `2px solid ${tab === id ? 'var(--accent)' : 'transparent'}`, paddingBottom: 2 }}>{label}</span>
            ))}
            <Helper style={{ flex: 1 }}>{tab === 'runs' ? `last ${runs.length} scheduler and manual runs` : 'every run and change, newest first'}</Helper>
            {tab === 'activity' && (
              <span style={{ alignSelf: 'center', display: 'flex', gap: 6 }}>
                <span style={{ position: 'relative' }}>
                  <UiPill size="sm" on={!!actType} ariaExpanded={typeOpen} ariaHaspopup="menu"
                    title="Filter the activity log by type" onClick={() => setTypeOpen((v) => !v)} style={{ gap: 5 }}>
                    Type{actType ? ' · 1' : ''}<span style={{ fontSize: 9, opacity: 0.6 }}>▾</span>
                  </UiPill>
                  {typeOpen && (
                    <>
                      <span onClick={() => setTypeOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 39 }} />
                      <Menu ariaLabel="Filter by type" style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 5, width: 150 }}>
                        {TYPE_OPTS.map(([id, label]) => (
                          <MenuItem key={id} selected={actType === id} hint={actType === id ? '✓' : null}
                            onClick={() => { setActType(id); setTypeOpen(false) }}>{label}</MenuItem>
                        ))}
                      </Menu>
                    </>
                  )}
                </span>
                {/* ui: keep — 26px transparent v2-fieldwrap pill carrying ⌕ + focus signal around a bare input; SearchInput's boxed h32 variant wouldn't sit on this log header row. */}
                <span className="v2-fieldwrap" style={{ height: 26, width: 140, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  {/* ui: keep — a 10px icon glyph inside the field wrap, not helper text */}
                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>⌕</span>
                  <input value={actQuery} onChange={(e) => setActQuery(e.target.value)} placeholder="Company…"
                    style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--text)' }} />
                </span>
              </span>
            )}
          </div>

          {tab === 'runs' ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <TableHead height={26} pad="0 20px" top style={{ background: 'transparent' }}>
                <span style={{ flex: '0 0 118px' }}>Time</span><span style={{ flex: '0 0 140px' }}>Job ID</span><span style={{ flex: '0 0 90px' }}>Trigger</span>
                <span style={{ flex: '0 0 100px' }}>Status</span><span style={{ flex: '0 0 76px' }}>Duration</span><span style={{ flex: 1 }}>Result</span>
              </TableHead>
              {runs.map((r) => {
                const failed = r.status === 'failed'
                return (
                  <TableRow key={r.id} size="sm">
                    <Mono line={16} tone="muted" style={{ flex: '0 0 118px' }}>{when(r.started_at)}</Mono>
                    <Mono line={16} tone="base" style={{ flex: '0 0 140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{r.job_type}</Mono>
                    <Helper size="xs" style={{ flex: '0 0 90px' }}>{r.trigger}</Helper>
                    <span style={{ flex: '0 0 100px', display: 'flex' }}>
                      <Pill bg={failed ? 'var(--bad-soft)' : r.status === 'running' ? 'var(--accent-soft)' : 'var(--hover-soft)'} fg={failed ? 'var(--bad)' : 'var(--accent)'}>{r.status}</Pill>
                    </span>
                    <Mono line={16} tone="base" style={{ flex: '0 0 76px' }}>{dur(r.duration_seconds)}</Mono>
                    <span title={r.error || r.result_summary || ''} style={{ flex: 1, minWidth: 0, color: failed ? 'var(--bad)' : 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.error || r.result_summary || '—'}</span>
                  </TableRow>
                )
              })}
              {!runs.length && <Helper style={{ padding: '16px 20px' }}>No runs yet.</Helper>}
              {runsMore && <LoadMore onClick={moreRuns} busy={moreBusy} />}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <TableHead height={26} pad="0 20px" top style={{ background: 'transparent' }}>
                <span style={{ flex: '0 0 118px' }}>Time</span><span style={{ flex: '0 0 110px' }}>Type</span>
                <span style={{ flex: 1 }}>Message</span><span style={{ flex: '0 0 130px' }}>Company</span>
              </TableHead>
              {activity.map((a) => (
                <TableRow key={a.id} size="sm">
                  <Mono line={16} tone="muted" style={{ flex: '0 0 118px' }}>{when(a.created_at)}</Mono>
                  <span style={{ flex: '0 0 110px', display: 'flex' }}>
                    <span className={TYPE_CLASS[a.type] || 'sm-extension'} style={BADGE}>{String(a.type || '').replace('_', ' ')}</span>
                  </span>
                  <span title={a.message} style={{ flex: 1, minWidth: 0, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{a.message}</span>
                  <Helper style={{ flex: '0 0 130px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.company || '—'}</Helper>
                </TableRow>
              ))}
              {/* An empty log and an over-tight filter are different problems */}
              {!activity.length && <Helper style={{ padding: '16px 20px' }}>{actType || actQuery.trim() ? 'No activity matches these filters.' : 'No activity recorded yet.'}</Helper>}
              {actMore && <LoadMore onClick={moreActivity} busy={moreBusy} />}
            </div>
          )}
        </Card>
      </div>
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// Dual Y-axis: applied is an order of magnitude smaller than new, and a shared scale
// flattens it to the baseline. The chart flexes to fill the card (sized by the LLM card beside it).
function Spark({ series, peak }) {
  const data = series.map((r) => ({ ...r, label: dayLabel(r.date) }))
  const axis = { tick: { fontSize: 9.5, fill: 'var(--muted)', fontFamily: 'var(--mono)' }, axisLine: false, tickLine: false }
  return (
    <div style={{ flex: 1, minHeight: 168, display: 'flex', flexDirection: 'column' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 4, left: -14, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
          <XAxis dataKey="label" interval={6} {...axis} />
          <YAxis yAxisId="l" allowDecimals={false} width={38} {...axis} tick={{ ...axis.tick, fill: 'var(--series-new)' }} />
          <YAxis yAxisId="r" orientation="right" allowDecimals={false} width={26} {...axis} tick={{ ...axis.tick, fill: 'var(--stage-applied)' }} />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--radius-cell)', fontSize: 12, padding: '6px 10px' }}
            labelStyle={{ color: 'var(--text)', fontSize: 11, marginBottom: 2 }} itemStyle={{ padding: 0 }} />
          {/* --series-new is a warm ochre tuned per theme for >=2:1 luminance contrast
              against --stage-applied's blue (dash pattern also separates the lines). */}
          <Line yAxisId="l" type="monotone" dataKey="total" name="new" stroke="var(--series-new)" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
          <Line yAxisId="r" type="monotone" dataKey="applied" name="applied" stroke="var(--stage-applied)" strokeWidth={2} strokeDasharray="4 3" dot={false} activeDot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
      {peak?.total > 0 && <span style={{ flex: '0 0 auto', alignSelf: 'center', ...MONO, fontSize: 10, lineHeight: '14px', color: 'var(--muted)' }}>peak {peak.total} · {dayLabel(peak.date)}</span>}
    </div>
  )
}

// Custom Sankey node rendering, painted with the Applications stage palette so a
// stage looks the same on both screens; label format ("name (value)") matches v1.
const STAGE_FILL = {
  new: 'var(--stage-new)', saved: 'var(--stage-new)', applied: 'var(--stage-applied)',
  interview: 'var(--stage-interview)', offer: 'var(--stage-offer)', rejected: 'var(--stage-rejected)',
  // ghosted/withdrawn have no stage of their own — they group under Rejected
  ghosted: 'var(--stage-rejected)', withdrawn: 'var(--stage-rejected)',
}
function SankeyNode({ x, y, width, height, payload }) {
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={3} fill={STAGE_FILL[payload.name] || 'var(--edge)'} />
      <text x={x + width + 6} y={y + height / 2} textAnchor="start" dominantBaseline="middle" fontSize={11} fill="var(--text-2)">
        {payload.name} ({payload.value})
      </text>
    </g>
  )
}
