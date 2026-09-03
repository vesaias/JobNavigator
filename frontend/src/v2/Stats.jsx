import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { ResponsiveContainer, Sankey, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import { Card, Menu, MenuItem, Pill as UiPill } from './ui'
import './theme.css'

// Stats reads the pipeline back to you: what's in the funnel, how the scorer is
// doing, what the LLM costs, and what the scheduler has actually been up to.
// Everything here is derived from endpoints that already existed, except the
// score averages (score-distribution?detail=true) and run result summaries
// (JobRun.result_summary, which used to be written as None on every run).

const PERIODS = [[1, '1d'], [7, '7d'], [30, '30d'], [0, 'all']]
// STAT-18: both logs used to stop at one silent page. They now page with
// limit+offset, and the control hides itself when a page comes back short.
const RUN_PAGE = 30
const ACT_PAGE = 50
const BUCKET_COLOR = {
  // STAT-21: --line is a border token; as a fill it vanished into the card in dark
  '0-20': 'var(--line-strong)', '21-40': 'var(--sand)', '41-60': 'var(--gold)',
  '61-80': 'var(--funnel-mid)', '81-100': 'var(--accent)',
}
const TYPE_CLASS = {
  scrape: 'sm-keyword', h1b: 'sm-lipersonal', cv_score: 'sm-levels',
  email: 'sm-freehire', telegram: 'sm-jobright',
}
const TYPE_OPTS = [['', 'All types'], ['scrape', 'Scrape'], ['h1b', 'H-1B'], ['cv_score', 'Résumé score'], ['email', 'Email'], ['telegram', 'Telegram']]

// STAT-22: v2 draws its controls as span/div, so they were neither focusable nor
// operable from the keyboard. Spread kb(fn) on such an element; the focus ring is
// theme.css's `[tabindex="0"]:focus-visible`. (Same helper as ResumeSections.jsx.)
const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

const money = (n) => (n == null ? '—' : n === 0 || n >= 1 ? `$${n.toFixed(2)}` : `$${n.toFixed(n < 0.01 ? 4 : 3)}`)
const int = (n) => (n == null ? '—' : Number(n).toLocaleString('en-US'))
// STAT-15: the timeline keys are calendar dates in the viewer's own zone (the
// backend groups on the DB's local date). `new Date('2026-09-02')` parses as UTC
// midnight, which renders as the previous day west of UTC — build the Date from
// the parts instead so the label matches the bucket it names.
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

const H = { fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 500, letterSpacing: '-.015em' }
const NOTE = { fontSize: 11, lineHeight: '16px', color: 'var(--muted)' }
const COL = { fontSize: 9.5, lineHeight: '14px', letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }
const MONO = { fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px' }
// Same badge idiom as Companies: mono, 9.5px, .05em, 2px 7px, full radius.
const BADGE = { fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, lineHeight: '14px', whiteSpace: 'nowrap' }
const Pill = ({ children, bg, fg }) => (
  <span style={{ ...BADGE, background: bg, color: fg }}>{children}</span>
)
// STAT-18: the pager both logs share.
const LoadMore = ({ onClick, busy }) => (
  <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 20px 12px' }}>
    <UiPill size="sm" disabled={!!busy} ariaBusy={!!busy} onClick={onClick}>
      {/* ui: keep — Spinner role (the v2-spin ring), not a status dot; the scan files it under dot-or-badge because it is a round bordered box */}
      {busy && <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
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
  const [coreErr, setCoreErr] = useState(false)   // STAT-03: any core stats request failed
  const [schedErr, setSchedErr] = useState(false) // OPEN-06: /scheduler/jobs failed
  const [triggering, setTriggering] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const pollRef = useRef(null)
  const runningRef = useRef(false)
  const qRef = useRef(null)
  const runsPaged = useRef(false)   // STAT-18: Load more was used, so the poll must not shrink the list back
  const runsCardRef = useRef(null)  // STAT-16: the rail links here as /v2/stats#runs
  const { hash } = useLocation()
  // STAT-04: the schedules columns are fixed-width and the card has no scroller,
  // so below ~1100px the Run now buttons spilled past its right border. Measure
  // the card and drop columns right-to-left as it narrows; the job name (which
  // shrinks to an ellipsis) and the run control are the two that always survive.
  const schedRef = useRef(null)
  const [schedW, setSchedW] = useState(1200)
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  const loadCore = useCallback(async () => {
    let anyFailed = false
    const get = (u, params) => api.get(u, { params }).then(({ data }) => data).catch((e) => { console.error(u, e); anyFailed = true; return null })
    // one round, not two: the sweep and health calls used to wait on the first
    // batch for no reason
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
    // STAT-03: keeping the previous value on failure rendered a dead backend as a
    // plausible dashboard. Clear the node instead — int(null) renders “—”.
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
    // OPEN-06: STAT-03 gave the funnel and the 30-day card an explicit failure
    // state but left this one drawing an empty-but-plausible table — "0 jobs" and
    // no rows reads exactly like a correctly configured, idle scheduler. Same
    // treatment: drop the stale rows and say the request failed.
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
      // R2-A-03: converted — the activity log is a list the user filters; a failed
      // reload used to leave the old rows (or none) with nothing to explain them
      .catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the activity log' }) })
  }, [actType, actQuery])

  useEffect(() => { loadCore().finally(() => setLoading(false)); loadLive() }, [loadCore, loadLive])
  useEffect(() => { api.get('/stats/llm-costs', { params: { days: period } }).then(({ data }) => setCosts(data)).catch(() => setCosts(null)) }, [period])
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
  }, [loading])

  const refresh = async () => {
    if (refreshing) return
    setRefreshing(true)
    await Promise.all([loadCore(), loadLive()])
    loadActivity()
    // R2-A-03: converted — this one is behind the Refresh button, so a failure
    // that leaves the old figures on screen has to say so
    api.get('/stats/llm-costs', { params: { days: period } }).then(({ data }) => setCosts(data)).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not refresh the LLM costs' }) })
    setRefreshing(false)
  }

  // STAT-01: 202, 409 and 500 used to give byte-identical UI for a fixed 4s, so a
  // refused or failed trigger read as a started one. Toast the outcome, and drop
  // the optimistic "Running" immediately when nothing was actually started.
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

  // STAT-18: one more page of whichever log you're looking at, appended.
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

  // STAT-16: the rail's health line promises "Stats · Run history", which is the
  // last card on a ~2400px page. It now navigates to /v2/stats#runs; scroll there
  // once the cards exist (before that the ref is null and the page is one screen).
  useEffect(() => {
    if (loading || hash !== '#runs') return
    runsCardRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [loading, hash])

  // ── derived ───────────────────────────────────────────────────────────────
  const st = stats?.application_statuses || {}
  const inPlay = Math.max(0, (stats?.total_applications || 0) - ((st.rejected || 0) + (st.ghosted || 0) + (st.withdrawn || 0)))
  // STAT-02: cv_scores can be {} (routes_jobs.py treats that as unscored) and
  // Math.max() of an empty list is -Infinity — the tile rendered "-Infinity".
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
      // STAT-15: local calendar date, not the UTC one — toISOString() shifted all
      // 30 buckets by a day west of UTC, and with them "New this week" and peak
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

  // A funnel needs "ever reached", not "currently in". application_statuses is a
  // snapshot — an application that interviewed and was then rejected counts as
  // rejected there, so reading Interview off it undercounts badly. The status
  // transition graph records every hop, so downstream stages come from that.
  // STAT-06: every row now counts applications (Saved was the live job shortlist,
  // a different population, which made the widest-row normalisation read upside
  // down). Widths are relative to Applied, the top of the funnel.
  const reached = useMemo(() => {
    const to = {}
    for (const f of flows) to[f.target] = (to[f.target] || 0) + (f.value || 0)
    return to
  }, [flows])
  const funnel = useMemo(() => {
    const applied = stats?.total_applications || 0
    // STAT-05: the design's one neutral → accent ramp, ending on the neutral
    // --line-strong for the terminal Rejected row.
    // STAT-09: with no transition history the row falls back to the status
    // snapshot, which is a different question ("currently in" vs "ever reached")
    // — flag those rows so the footnote isn't claiming something it can't know.
    const pick = (k) => (reached[k] ? { count: reached[k], snapshot: false } : { count: st[k] || 0, snapshot: !!st[k] })
    const rows = [
      // R3-U-01: one stage, one colour. These used to run on the neutral chart
      // ramp (--funnel-low/-mid/--accent/--line-strong), so Applied was green
      // here, blue on the Flow view's Sankey nodes and blue again on the
      // Applications stage dots. All three now read the same --stage-* tokens.
      { label: 'Applied', count: applied, snapshot: false, color: 'var(--stage-applied)' },
      { label: 'Interview', ...pick('interview'), color: 'var(--stage-interview)' },
      { label: 'Offer', ...pick('offer'), color: 'var(--stage-offer)' },
      { label: 'Rejected', ...pick('rejected'), color: 'var(--stage-rejected)' },
    ]
    const base = Math.max(1, applied)
    return rows.map((r) => ({
      ...r,
      w: `${Math.min(100, Math.max(r.count ? 2 : 0, Math.round((r.count / base) * 100)))}%`,
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

  if (loading) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Stats</h1>
          {/* Volume, outcomes, scoring and spend each already have a card below,
              so the header carries the one thing none of them shows: whether the
              pipeline ran and whether anything is broken. */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {sweep
              ? `Last sweep ${sweep.status === 'failed' ? 'failed ' : ''}${ago(sweep.finished_at || sweep.started_at) || '—'}`
              : 'No scrape recorded yet'}
            {failing > 0 && <> · <span style={{ color: 'var(--warn)' }}>{failing} source{failing === 1 ? ' needs' : 's need'} attention</span></>}
            {spend != null && <> · {money(spend)} on LLM calls {period ? `in ${period}d` : 'all time'}</>}
          </span>
        </div>
        <span onClick={refresh} {...kb(refresh)} title="Reload every figure on this page" className="v2-hover-accent-text v2-ctl" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>
          {refreshing
            ? <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
            : <span style={{ fontSize: 12 }}>↻</span>}
          Refresh
        </span>
      </header>
      {coreErr && (
        <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 12, padding: '8px 30px', background: 'var(--bad-soft)', borderBottom: '1px solid var(--line)', fontSize: 12.5, lineHeight: '18px', color: 'var(--bad)' }}>
          {/* ui: keep — 16px round "!" glyph in the error band, not a control */}
          <span style={{ width: 16, height: 16, borderRadius: 99, background: 'var(--bad)', color: 'var(--accent-ink)', fontSize: 9.5, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>!</span>
          <span style={{ flex: 1 }}>Couldn’t reach the backend for some of these numbers — tiles show “—” and charts are marked unavailable until it answers.</span>
          <span onClick={refresh} {...kb(refresh)} className="v2-hover-accent-text v2-ctl" style={{ fontWeight: 600, cursor: 'pointer', borderBottom: '1px dotted currentColor' }}>Try again</span>
        </div>
      )}

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '18px 30px 30px', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* KPI strip */}
        <Card style={{ padding: 0, display: 'flex' }}>
          {[
            ['Total jobs', int(stats?.total_jobs), '', 'Everything ever scraped or captured, minus cleanup'],
            ['New this week', int(timeline ? weekly.now : null), timeline && weekly.prev ? `${weekly.now - weekly.prev >= 0 ? '+' : ''}${weekly.now - weekly.prev} vs last` : '', 'Discovered in the last 7 days'],
            ['Saved', int(stats?.saved_jobs), '', 'In your feed shortlist'],
            ['Applications', int(stats?.total_applications), `${inPlay} in play`, 'In play = not rejected, ghosted or withdrawn'],
            ['Best open score', bestScore, bestScore === '—' ? '' : (best?.company || ''), 'Highest-scoring posting you haven’t applied to'],
          ].map(([label, value, sub, hint], i, arr) => (
            <div key={label} title={hint} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 11, padding: '14px 20px 10px', borderRight: `1px solid ${i === arr.length - 1 ? 'transparent' : 'var(--line-soft)'}` }}>
              <span style={{ fontSize: 10, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)', whiteSpace: 'nowrap' }}>{label}</span>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 27, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '30px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {value}{sub && <span style={{ marginLeft: 7, fontSize: 13, color: String(sub).startsWith('+') ? 'var(--accent)' : 'var(--muted)' }}>{sub}</span>}
              </span>
            </div>
          ))}
        </Card>

        {/* funnel + score distribution */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {/* Fixed height: the funnel and the Sankey are different shapes, so
              letting either size the card made the row jump on toggle. Both
              views get the same 162px of content area inside 230. */}
          <Card style={{ height: 230, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <span style={H}>Application funnel</span>
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
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--text)', fontSize: 12 }} />
                  </Sankey>
                </ResponsiveContainer>
              </div>
            ) : (
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {funnel.map((f) => (
                <div key={f.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ flex: '0 0 76px', fontSize: 12, lineHeight: '18px', color: 'var(--text-2)' }}>{f.label}</span>
                  <div style={{ flex: 1, height: 22, background: 'var(--surface-2)', borderRadius: 5, overflow: 'hidden', display: 'flex' }}>
                    <div style={{ width: f.w, background: f.color, borderRadius: 5 }} />
                  </div>
                  <span style={{ flex: '0 0 40px', ...MONO, fontSize: 11.5, lineHeight: '18px', color: 'var(--text)', textAlign: 'right' }}>{f.count}</span>
                  {f.snapshot && <span title="No stage history recorded for these — counted by current status, so anything that passed through this stage and moved on is missing"
                    style={{ flex: '0 0 auto', fontSize: 9.5, lineHeight: '18px', color: 'var(--muted)', cursor: 'help' }}>snapshot</span>}
                </div>
              ))}
            </div>
            <span style={{ ...NOTE, display: 'flex', flexDirection: 'column', gap: 2, lineHeight: '15px' }}>
              {/* the card's height is fixed, so the caveat replaces the "bars are
                  relative to Applied" clause rather than adding a third line */}
              <span>{funnel.some((f) => f.snapshot)
                ? 'Rows count applications that ever reached that stage; snapshot rows count current status'
                : 'Every row counts applications that ever reached that stage; bars are relative to Applied'}</span>
              <span>applied → interview {conv(stats?.total_applications, reached.interview || 0)} · interview → offer {conv(reached.interview || 0, reached.offer || 0)}</span>
            </span>
            </div>
            )}
          </Card>

          <Card style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <span style={H}>Score distribution</span>
              <span style={{ flex: 1, ...NOTE }}>{int(scores?.scored_count)} scored jobs · best résumé per job</span>
              {scores?.avg != null && (
                <span style={{ fontSize: 11, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                  avg {scores.avg}
                  {scores.tailored_avg != null && <> · <span title={`Average score after tailoring, across the ${scores.tailored_count} jobs with a tailored copy`} style={{ color: 'var(--accent)', cursor: 'help' }}>tailored {scores.tailored_avg}</span></>}
                </span>
              )}
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 14, minHeight: 118, padding: '0 6px' }}>
              {buckets.map((b) => (
                <div key={b.range} title={`${b.count} jobs scored ${b.range}`} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                  <span style={{ ...MONO, lineHeight: '14px', color: 'var(--text-2)' }}>{b.count}</span>
                  <div style={{ width: '100%', height: Math.max(2, Math.round((b.count / maxBucket) * 96)), background: BUCKET_COLOR[b.range] || 'var(--accent)', borderRadius: '5px 5px 0 0' }} />
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
              <span style={H}>New jobs · last 30 days</span>
              <span style={{ flex: 1, ...NOTE }}>daily arrivals across all sources</span>
              {/* STAT-07: --stage-applied is the applied series everywhere else in
                  v2; the swatch is solid, as designed. R3-U-02: the legend swatches
                  follow the strokes below, so "new" is --series-new here too. */}
              {[['new', 'var(--series-new)'], ['applied', 'var(--stage-applied)']].map(([l, c]) => (
                <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-2)' }}>
                  <span style={{ width: 14, height: 2, background: c }} />{l}
                </span>
              ))}
            </div>
            {coreErr && !timeline ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>Unavailable — the request failed</div> : <Spark series={series} peak={peak} />}
          </Card>

          <Card style={{ height: 300, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0, overflow: 'hidden' }}>
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, lineHeight: '24px' }}>
              <span style={H}>LLM costs</span>
              <span title="OpenAI and Claude prices come from a static table; OpenRouter uses live catalog pricing refreshed at most every 12h; Claude Code and Ollama count as $0. Cost is computed per call at log time, so past rows keep the price in effect then."
                style={{ fontFamily: 'var(--sans)', fontSize: 11, lineHeight: '14px', color: 'var(--muted)', cursor: 'help', borderBottom: '1px dotted var(--line-strong)' }}>how priced?</span>
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
                  <span style={{ fontSize: 10, lineHeight: '14px', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)' }}>{l}</span>
                  <span style={{ fontFamily: 'var(--serif)', fontSize: 23, lineHeight: '28px', letterSpacing: '-.02em' }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <div className="v2-gutter-head" style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', height: 22, ...COL, fontSize: 9, borderBottom: '1px solid var(--line-strong)' }}>
                <span style={{ flex: 1.1 }}>Purpose</span><span style={{ flex: 1.4 }}>Model</span>
                <span style={{ flex: '0 0 42px', textAlign: 'right' }}>Calls</span><span style={{ flex: '0 0 58px', textAlign: 'right' }}>Cost</span>
                <span title="Prompt-cache hit ratio" style={{ flex: '0 0 44px', textAlign: 'right' }}>Cache</span>
              </div>
              {/* takes whatever the fixed-height card leaves, so switching period
                  (2 rows at 1d, 13 at all-time) can't resize anything */}
              <div className="v2-scroll v2-gutter" style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              {(costs?.by_purpose || []).map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', height: 26, borderBottom: '1px solid var(--line-soft)', fontSize: 11, lineHeight: '16px' }}>
                  <span style={{ flex: 1.1, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 6 }}>{c.purpose}</span>
                  <span title={c.model} style={{ flex: 1.4, ...MONO, fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 6 }}>{c.model || '—'}</span>
                  <span style={{ flex: '0 0 42px', textAlign: 'right', ...MONO, color: 'var(--text-2)' }}>{c.calls}</span>
                  <span style={{ flex: '0 0 58px', textAlign: 'right', ...MONO, color: 'var(--text)' }}>{money(c.cost_usd)}</span>
                  <span style={{ flex: '0 0 44px', textAlign: 'right', ...MONO, color: c.cache_involving ? 'var(--accent)' : 'var(--muted)' }}>{c.cache_involving ? `${Math.round(c.cache_hit_ratio * 100)}%` : '—'}</span>
                </div>
              ))}
              {!(costs?.by_purpose || []).length && <div style={{ padding: '14px 0', ...NOTE }}>No LLM calls in this window.</div>}
              </div>
            </div>
          </Card>
        </div>

        {/* schedules */}
        <Card ref={schedRef} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '14px 20px 10px', lineHeight: '24px' }}>
            <span style={H}>Schedules</span>
            <span style={NOTE}>{schedErr ? 'intervals and crons live in Settings' : `${jobs.length} job${jobs.length === 1 ? '' : 's'} · next runs in ${TZ_SHORT}, schedules as configured (UTC) · intervals and crons live in Settings`}</span>
          </div>
          {schedErr ? (
            <div style={{ padding: '26px 20px 30px', borderTop: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>Unavailable — the request failed</div>
          ) : (<>
          <div style={{ display: 'flex', alignItems: 'center', height: 26, padding: '0 20px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-strong)', ...COL }}>
            <span style={{ flex: '0 1 250px', minWidth: 0 }}>Job</span>
            {showId && <span style={{ flex: '0 0 132px' }}>Job ID</span>}
            {showSched && <span style={{ flex: '0 0 140px' }}>Schedule</span>}
            {showNext && <span style={{ flex: '0 0 132px' }}>Next run</span>}
            <span style={{ flex: 1, minWidth: 0 }}>{showStatus ? 'Status' : ''}</span>
            <span style={{ flex: '0 0 110px', textAlign: 'right' }}>Run</span>
          </div>
          {ordered.map((j) => {
            const running = !!j.running || triggering.has(j.id)
            return (
              <div key={j.id} style={{ display: 'flex', alignItems: 'center', height: 38, padding: '0 20px', borderBottom: '1px solid var(--line-soft)' }}>
                <span title={j.name} style={{ flex: '0 1 250px', minWidth: 0, fontSize: 12.5, lineHeight: '18px', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{j.name}</span>
                {showId && <span title={j.id} style={{ flex: '0 0 132px', ...MONO, lineHeight: '18px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.id}</span>}
                {showSched && <span title={j.schedule} style={{ flex: '0 0 140px', fontSize: 11.5, lineHeight: '18px', color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{decodeCron(j.schedule)}</span>}
                {showNext && <span style={{ flex: '0 0 132px', ...MONO, lineHeight: '18px', color: 'var(--muted)' }}>{running ? 'now' : when(j.next_run)}</span>}
                <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {showStatus && (running
                    ? <span className="v2-spin" style={{ flex: '0 0 auto', width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                    /* ui: keep — 7px scheduler status dot (Dot role, migrates with Tag/Dot) */
                    : <span style={{ flex: '0 0 auto', width: 7, height: 7, borderRadius: 99, background: j.pending ? 'var(--warn)' : 'var(--funnel-low)' }} />)}
                  {showStatus && <span style={{ minWidth: 0, fontSize: 11.5, lineHeight: '18px', color: running ? 'var(--accent)' : 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {running ? `Running · ${dur(j.running?.elapsed_seconds || 0)}` : j.pending ? 'Pending' : 'Scheduled'}
                  </span>}
                </span>
                <span style={{ flex: '0 0 110px', display: 'flex', justifyContent: 'flex-end' }}>
                  {j.trigger_url
                    ? <span onClick={() => !running && trigger(j)} {...kb(() => !running && trigger(j))} aria-disabled={running}
                        title={running ? `${j.name} is running` : `Run ${j.name} now`} aria-label={running ? `${j.name} is running` : `Run ${j.name} now`}
                        className={running ? '' : 'v2-bdc'} style={{ height: 25, padding: '0 11px', border: `1px solid ${running ? 'var(--line)' : 'var(--edge)'}`, borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, lineHeight: 1, color: running ? 'var(--edge)' : 'var(--text-2)', whiteSpace: 'nowrap', cursor: running ? 'default' : 'pointer' }}>
                        {/* ui: keep — Spinner role (the v2-spin ring), not a status dot; the scan files it under dot-or-badge because it is a round bordered box */}
                        {running && <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
                        {running ? 'Running…' : 'Run now'}
                      </span>
                    : <span style={{ ...NOTE }}>—</span>}
                </span>
              </div>
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
            <span style={{ flex: 1, ...NOTE }}>{tab === 'runs' ? `last ${runs.length} scheduler and manual runs` : 'everything the pipeline did, newest first'}</span>
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
                {/* ui: keep — a 26px transparent v2-fieldwrap pill that carries the ⌕ and
                    the focus signal around a bare input; SearchInput's boxed variant is h32
                    on --search-bg, which would not sit on this log header row */}
                <span className="v2-fieldwrap" style={{ height: 26, width: 140, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>⌕</span>
                  <input value={actQuery} onChange={(e) => setActQuery(e.target.value)} placeholder="Company…"
                    style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 11.5, color: 'var(--text)' }} />
                </span>
              </span>
            )}
          </div>

          {tab === 'runs' ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', height: 26, padding: '0 20px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-strong)', ...COL }}>
                <span style={{ flex: '0 0 118px' }}>Time</span><span style={{ flex: '0 0 140px' }}>Job ID</span><span style={{ flex: '0 0 90px' }}>Trigger</span>
                <span style={{ flex: '0 0 100px' }}>Status</span><span style={{ flex: '0 0 76px' }}>Duration</span><span style={{ flex: 1 }}>Result</span>
              </div>
              {runs.map((r) => {
                const failed = r.status === 'failed'
                return (
                  <div key={r.id} style={{ display: 'flex', alignItems: 'center', height: 34, padding: '0 20px', borderBottom: '1px solid var(--line-soft)', fontSize: 11.5, lineHeight: '18px' }}>
                    <span style={{ flex: '0 0 118px', ...MONO, color: 'var(--muted)' }}>{when(r.started_at)}</span>
                    <span style={{ flex: '0 0 140px', ...MONO, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{r.job_type}</span>
                    <span style={{ flex: '0 0 90px', fontSize: 10.5, color: 'var(--muted)' }}>{r.trigger}</span>
                    <span style={{ flex: '0 0 100px', display: 'flex' }}>
                      <Pill bg={failed ? 'var(--bad-soft)' : r.status === 'running' ? 'var(--accent-soft)' : 'var(--hover-soft)'} fg={failed ? 'var(--bad)' : 'var(--accent)'}>{r.status}</Pill>
                    </span>
                    <span style={{ flex: '0 0 76px', ...MONO, color: 'var(--text-2)' }}>{dur(r.duration_seconds)}</span>
                    <span title={r.error || r.result_summary || ''} style={{ flex: 1, minWidth: 0, color: failed ? 'var(--bad)' : 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.error || r.result_summary || '—'}</span>
                  </div>
                )
              })}
              {!runs.length && <div style={{ padding: '16px 20px', ...NOTE }}>No runs yet.</div>}
              {runsMore && <LoadMore onClick={moreRuns} busy={moreBusy} />}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', height: 26, padding: '0 20px', borderTop: '1px solid var(--line-soft)', borderBottom: '1px solid var(--line-strong)', ...COL }}>
                <span style={{ flex: '0 0 118px' }}>Time</span><span style={{ flex: '0 0 110px' }}>Type</span>
                <span style={{ flex: 1 }}>Message</span><span style={{ flex: '0 0 130px' }}>Company</span>
              </div>
              {activity.map((a) => (
                <div key={a.id} style={{ display: 'flex', alignItems: 'center', height: 34, padding: '0 20px', borderBottom: '1px solid var(--line-soft)', fontSize: 11.5, lineHeight: '18px' }}>
                  <span style={{ flex: '0 0 118px', ...MONO, color: 'var(--muted)' }}>{when(a.created_at)}</span>
                  <span style={{ flex: '0 0 110px', display: 'flex' }}>
                    <span className={TYPE_CLASS[a.type] || 'sm-extension'} style={BADGE}>{String(a.type || '').replace('_', ' ')}</span>
                  </span>
                  <span title={a.message} style={{ flex: 1, minWidth: 0, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{a.message}</span>
                  <span style={{ flex: '0 0 130px', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.company || '—'}</span>
                </div>
              ))}
              {/* STAT-18: an empty log and an over-tight filter are different problems */}
              {!activity.length && <div style={{ padding: '16px 20px', ...NOTE }}>{actType || actQuery.trim() ? 'No activity matches these filters.' : 'No activity recorded yet.'}</div>}
              {actMore && <LoadMore onClick={moreActivity} busy={moreBusy} />}
            </div>
          )}
        </Card>
      </div>
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// 30-day arrivals, on Recharts like v1 — a real dated X axis and one Y axis per
// series, because applied is an order of magnitude smaller than new and a shared
// scale flattens it onto the baseline. The chart flexes to fill the card, which
// is sized by the taller LLM card beside it; a fixed height left a third of the
// card empty.
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
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12, padding: '6px 10px' }}
            labelStyle={{ color: 'var(--text)', fontSize: 11, marginBottom: 2 }} itemStyle={{ padding: 0 }} />
          {/* R3-U-02: "new" was --accent, a dark green that sits within 1.2:1 of
              --stage-applied's dark blue in light mode — the two lines read as one.
              --series-new is a warm ochre tuned per theme to keep a >=2:1 luminance
              gap from the applied line (and the dash pattern still separates them). */}
          <Line yAxisId="l" type="monotone" dataKey="total" name="new" stroke="var(--series-new)" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
          <Line yAxisId="r" type="monotone" dataKey="applied" name="applied" stroke="var(--stage-applied)" strokeWidth={2} strokeDasharray="4 3" dot={false} activeDot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
      {peak?.total > 0 && <span style={{ flex: '0 0 auto', alignSelf: 'center', ...MONO, fontSize: 10, lineHeight: '14px', color: 'var(--muted)' }}>peak {peak.total} · {dayLabel(peak.date)}</span>}
    </div>
  )
}

// Recharts renders Sankey nodes itself; this draws them on the Applications
// stage palette so a stage looks the same on both screens, with the
// "name (value)" label v1 used.
const STAGE_FILL = {
  new: 'var(--stage-new)', saved: 'var(--stage-new)', applied: 'var(--stage-applied)',
  interview: 'var(--stage-interview)', offer: 'var(--stage-offer)', rejected: 'var(--stage-rejected)',
  // APPS-22: ghosted/withdrawn have no stage of their own — they group under Rejected
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
