import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import ConfirmDialog from './ConfirmDialog'
import { useSettled, useWarm, NBSP } from './hooks'
import { Button, Card, Check, Dot, FooterRow, Heading, HeaderRow, Helper, IconButton, Input, Label, Link, Menu, MenuItem, ModalPanel, PageTitle, Pill, Rule, Segmented, Select, Spinner, TableHead } from './ui'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
const ago = (iso) => {
  if (!iso) return 'never'
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
const until = (iso) => {
  if (!iso) return null
  const m = Math.round((new Date(iso).getTime() - Date.now()) / 60000)
  if (m <= 0) return 'due now'
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ${m % 60}m`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}
const short = (u, n = 52) => {
  const s = (u || '').replace(/^https?:\/\//, '')
  return s.length > n ? s.slice(0, n) + '…' : s
}
// FastAPI sends `detail` as a string for HTTPException but as an ARRAY of
// {loc,msg,type} objects for a 422 — stringifying that array gives the user
// "[object Object]", so unpack it here.
const errText = (e, fallback) => {
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d) return d
  if (Array.isArray(d) && d.length) return d.map((x) => x?.msg || JSON.stringify(x)).join('; ')
  return fallback
}

// mode → [badge label, badge class]. The legacy `url` mode was removed from the
// backend dispatch, so it is no longer rendered here either.
const MODES = {
  keyword: ['JOBSPY', 'sm-keyword'],
  levels_fyi: ['LEVELS.FYI', 'sm-levels'],
  linkedin_personal: ['LINKEDIN PERSONAL', 'sm-lipersonal'],
  jobright: ['JOBRIGHT.AI', 'sm-jobright'],
  freehire: ['FREEHIRE.ME', 'sm-freehire'],
  linkedin_extension: ['EXTENSION', 'sm-extension'],
  extension: ['EXTENSION', 'sm-extension'],
}
const MODE_OPTIONS = [
  ['keyword', 'Keyword (JobSpy)'],
  ['levels_fyi', 'Levels.fyi'],
  ['linkedin_personal', 'LinkedIn Personal'],
  ['jobright', 'Jobright.ai'],
  ['freehire', 'freehire.me'],
]
// /monitor/active carries every background job; only POST /searches/{id}/run
// tags its run with job_type 'search_run' (routes_searches.py) — filter on that.
const isSearchRun = (r) => r?.job_type === 'search_run'
const EXT_MODES = ['linkedin_extension', 'extension']
const isExt = (m) => EXT_MODES.includes(m)
const TESTABLE = ['keyword', 'levels_fyi', 'linkedin_personal', 'jobright', 'freehire']

// `dots` is a COUNT, not a glyph string — Segmented draws that many accent Dots
// before the label; 0 must draw nothing, not an empty span (that shifts centering).
const DEPTHS = [
  { id: 'off', label: 'Off', dots: 0, hint: 'New results arrive unscored — score them by hand from the feed' },
  { id: 'light', label: 'Light', dots: 1, hint: 'Score only. Low cost.' },
  { id: 'full', label: 'Full', dots: 2, hint: 'Score plus the full report with keywords and requirements' },
]
const SOURCES = [['linkedin', 'LinkedIn'], ['indeed', 'Indeed'], ['zip_recruiter', 'ZipRecruiter'], ['google', 'Google Jobs'], ['direct', 'Direct (Playwright)']]
const COLLECTIONS = [['recommended', 'Recommended'], ['top-applicant', 'Top Applicant']]

// note banners reuse the mode-badge palettes (sm-levels green / sm-jobright teal)
const noteFor = (mode) => {
  if (mode === 'levels_fyi') return ['Set your filters on levels.fyi and paste the URL here. The URL contains location, job family, salary and date filters.', 'sm-levels']
  if (mode === 'jobright') return ['Recommendations from your Jobright.ai account. Enter a search term to search instead. Credentials are in Settings › Accounts.', 'sm-jobright']
  if (mode === 'extension') return ['Jobs come from the “Save to Job Feed” button on any website. The filters and auto-score depth below apply to each job as it is saved.', 'sm-levels']
  if (mode === 'linkedin_extension') return ['Jobs are captured while you browse linkedin.com/jobs/collections pages. The filters below are applied on import.', 'sm-levels']
  return null
}

// one-line summary of what this search does
const summaryOf = (s) => {
  const last = s.last_run_at ? ` · last run ${ago(s.last_run_at)}` : ''
  const m = s.search_mode
  if (m === 'linkedin_extension') return 'Passive capture on linkedin.com/jobs/collections/* · title filters apply on import'
  if (m === 'extension') return 'Manual “Save to Job Feed” button on any website'
  if (m === 'keyword') {
    const bits = []
    if (s.search_term) bits.push(`“${s.search_term}”`)
    if (s.location) bits.push(s.location)
    if ((s.sources || []).length) bits.push((s.sources || []).join(', '))
    return bits.join(' · ') + last
  }
  if (m === 'levels_fyi') return `${short(s.direct_url)} · ${s.max_pages || 50} pages${last}`
  if (m === 'linkedin_personal') return `Collections: ${((s.sources || []).length ? s.sources : ['recommended', 'top-applicant']).join(', ')} · credentials in Settings${last}`
  if (m === 'jobright') {
    const bits = [s.search_term ? `“${s.search_term}”` : 'AI recommendations', `max ${s.results_wanted || 100}`]
    if (s.require_salary) bits.push('require salary')
    return bits.join(' · ') + last
  }
  if (m === 'freehire') {
    const bits = []
    if (s.search_term) bits.push(`“${s.search_term}”`)
    if (s.direct_url) bits.push(short(s.direct_url))
    return (bits.join(' · ') || 'freehire.me') + last
  }
  return `${short(s.direct_url) || 'no URL'}${last}`
}

const draftOf = (s) => ({
  name: s.name || '', search_mode: s.search_mode || 'keyword',
  search_term: s.search_term || '', direct_url: s.direct_url || '',
  location: s.location || '', is_remote: s.is_remote === true ? 'true' : s.is_remote === false ? 'false' : '',
  job_type: s.job_type || 'fulltime', hours_old: s.hours_old ?? 24, results_wanted: s.results_wanted ?? 50,
  max_pages: s.max_pages ?? 50, min_fit_score: s.min_fit_score ?? 0, require_salary: !!s.require_salary,
  sources: [...(s.sources || [])],
  title_include_keywords: (s.title_include_keywords || []).join(', '),
  title_exclude_keywords: (s.title_exclude_keywords || []).join(', '),
  company_filter: (s.company_filter || []).join(', '),
  company_exclude: (s.company_exclude || []).join(', '),
  exclude_active_companies: !!s.exclude_active_companies,
  auto_scoring_depth: s.auto_scoring_depth || 'off',
  run_interval_minutes: s.run_interval_minutes ?? 0,
})
// New search opens on Light, matching the Add-company modal — keeps the one
// control that spends money per scraped job consistent across creation flows.
const NEW_DRAFT = draftOf({ sources: ['linkedin', 'indeed', 'zip_recruiter', 'google'], title_exclude_keywords: ['intern', 'junior', 'associate'], auto_scoring_depth: 'light' })

// Numeric bounds live in one place so an input's min/max and the payload clamp
// can't drift apart.
const BOUNDS = {
  hours_old: [0, 720],
  results_wanted: [1, 500],
  results_wanted_jobright: [20, 500],
  max_pages: [1, 50],
  min_fit_score: [0, 100],
  run_interval_minutes: [0, 10080],
}

const toPayload = (d) => {
  const list = (v) => (v || '').split(',').map((x) => x.trim()).filter(Boolean)
  // `parseInt(x) || fallback` turned an explicit 0 into 24 / 50 — a cleared field
  // goes out as null instead; the backend falls back to the column default.
  const num = (v) => { const n = parseInt(v, 10); return Number.isNaN(n) ? null : n }
  // Clamp to the bounds the inputs declare — a label like "20–500" enforces
  // nothing on its own; a cleared field still goes out as null.
  const clamp = (v, key) => { const n = num(v); if (n == null) return null; const [lo, hi] = BOUNDS[key]; return Math.min(hi, Math.max(lo, n)) }
  const rwKey = d.search_mode === 'jobright' ? 'results_wanted_jobright' : 'results_wanted'
  const p = {
    name: d.name, search_mode: d.search_mode,
    search_term: d.search_term || null, direct_url: d.direct_url || null,
    is_remote: d.is_remote === 'true' ? true : d.is_remote === 'false' ? false : null,
    job_type: d.job_type, hours_old: clamp(d.hours_old, 'hours_old'),
    results_wanted: clamp(d.results_wanted, rwKey),
    max_pages: clamp(d.max_pages, 'max_pages') ?? 50, min_fit_score: clamp(d.min_fit_score, 'min_fit_score') ?? 0,
    require_salary: !!d.require_salary, sources: d.sources,
    title_include_keywords: list(d.title_include_keywords),
    title_exclude_keywords: list(d.title_exclude_keywords),
    company_filter: list(d.company_filter), company_exclude: list(d.company_exclude),
    exclude_active_companies: !!d.exclude_active_companies,
    auto_scoring_depth: d.auto_scoring_depth,
    run_interval_minutes: clamp(d.run_interval_minutes, 'run_interval_minutes') ?? 0,
  }
  // location is a keyword-search field only — sending it for
  // levels_fyi / jobright / freehire / extension searches means nothing.
  if (d.search_mode === 'keyword') p.location = d.location || 'United States'
  return p
}

// ── small pieces ─────────────────────────────────────────────────────────────
function Cell({ label, value, onChange, mono, placeholder, span, sub, disabled, options, type, min, max }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: span ? `span ${span}` : undefined, minWidth: 0 }}>
      <Label>{label}</Label>
      {options
        ? <Select value={value} options={options} onPick={onChange} disabled={disabled} mono={mono}
            ariaLabel={label} style={{ flex: '0 0 auto', width: '100%' }} />
        : <Input type={type || 'text'} value={value} disabled={disabled} placeholder={placeholder} min={min} max={max}
            mono={mono} ariaLabel={label} onChange={onChange} />}
      {sub && <Helper size="xs" style={{ textWrap: 'pretty' }}>{sub}</Helper>}
    </div>
  )
}
const Chip = ({ on, label, onClick }) => (
  <Pill size="sm" on={on} onClick={onClick}>
    <span>{on ? '✓' : '○'}</span>{label}
  </Pill>
)
// The two call sites live inside the edit form, whose own wrapper already calls
// stopPropagation on the clickable card behind it, so the cells need none.
const DepthPills = ({ value, onPick }) => (
  <Segmented size="sm" ariaLabel="Auto-scoring depth" value={value} onChange={onPick}
    options={DEPTHS.map((d) => ({ value: d.id, label: d.label, hint: d.hint, dots: d.dots }))}
    style={{ height: 31 }} />
)

// ── the shared config form (new + edit) ──────────────────────────────────────
function ConfigForm({ d, set }) {
  const m = d.search_mode
  const ext = isExt(m)
  const toggleSrc = (id) => set({ sources: d.sources.includes(id) ? d.sources.filter((x) => x !== id) : [...d.sources, id] })
  const note = noteFor(m)

  const fields = []
  fields.push(<Cell key="name" label="Name" value={d.name} onChange={(v) => set({ name: v })} placeholder="e.g. TPM roles — Tier 1" />)
  if (ext) {
    fields.push(<Cell key="mode" label="Mode" span={2} disabled
      value={m === 'extension' ? 'Extension (manual Save-to-Feed)' : 'LinkedIn Extension (passive capture)'} onChange={() => {}} />)
  } else {
    fields.push(<Cell key="mode" label="Mode" value={m} options={MODE_OPTIONS} onChange={(v) => {
      const patch = { search_mode: v }
      if (v === 'linkedin_personal') patch.sources = ['recommended', 'top-applicant']
      else if (v === 'jobright') patch.sources = ['recommended']
      else if (v === 'keyword') patch.sources = ['linkedin', 'indeed', 'zip_recruiter', 'google']
      set(patch)
    }} />)
  }
  if (m === 'keyword') {
    fields.push(
      <Cell key="term" label="Search term" mono value={d.search_term} onChange={(v) => set({ search_term: v })} placeholder="e.g. technical program manager" />,
      <Cell key="loc" label="Location" value={d.location} onChange={(v) => set({ location: v })} placeholder="United States" />,
      <Cell key="rem" label="Remote" value={d.is_remote} options={[['', 'Any'], ['true', 'Remote only'], ['false', 'On-site only']]} onChange={(v) => set({ is_remote: v })} />,
      <Cell key="jt" label="Job type" value={d.job_type} options={[['fulltime', 'Full-time'], ['parttime', 'Part-time'], ['contract', 'Contract']]} onChange={(v) => set({ job_type: v })} />,
      <Cell key="ho" label="Hours old · 0–720" mono type="number" min={BOUNDS.hours_old[0]} max={BOUNDS.hours_old[1]} value={d.hours_old} onChange={(v) => set({ hours_old: v })} />,
      <Cell key="rw" label="Results wanted · 1–500" mono type="number" min={BOUNDS.results_wanted[0]} max={BOUNDS.results_wanted[1]} value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
    )
  } else if (m === 'levels_fyi') {
    fields.push(
      <Cell key="mp" label="Max pages · 1–50" mono type="number" min={BOUNDS.max_pages[0]} max={BOUNDS.max_pages[1]} value={d.max_pages} onChange={(v) => set({ max_pages: v })} />,
      <Cell key="url" label="Levels.fyi URL · filters applied" mono span={3} value={d.direct_url} onChange={(v) => set({ direct_url: v })}
        placeholder="https://www.levels.fyi/jobs/location/united-states?jobFamilySlugs=software-engineer" />,
    )
  } else if (m === 'jobright') {
    fields.push(
      <Cell key="term" label="Search term · optional" value={d.search_term} onChange={(v) => set({ search_term: v })} placeholder="Leave empty for AI recommendations" />,
      <Cell key="rw" label="Results wanted · 20–500" mono type="number" min={BOUNDS.results_wanted_jobright[0]} max={BOUNDS.results_wanted_jobright[1]} value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
      <Cell key="ms" label="Min score · 0–100" mono type="number" min={BOUNDS.min_fit_score[0]} max={BOUNDS.min_fit_score[1]} value={d.min_fit_score} onChange={(v) => set({ min_fit_score: v })} placeholder="0 = no filter" />,
    )
  } else if (m === 'freehire') {
    fields.push(
      <Cell key="term" label="Search term · optional" mono value={d.search_term} onChange={(v) => set({ search_term: v })} placeholder="e.g. golang backend"
        sub="Added to the URL filters. Must appear in the posting text." />,
      <Cell key="url" label="freehire.me URL · filters forwarded" mono span={2} value={d.direct_url} onChange={(v) => set({ direct_url: v })}
        placeholder="https://freehire.me/?role=backend&seniority=senior&countries=us"
        sub="Role, seniority, countries and posting age are taken from the URL as is" />,
      <Cell key="rw" label="Results wanted · 1–500" mono type="number" min={BOUNDS.results_wanted[0]} max={BOUNDS.results_wanted[1]} value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
    )
  }

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 10 }}>{fields}</div>

      {note && (
        <div className={note[1]} style={{ padding: '9px 12px', borderRadius: 'var(--radius-cell)', fontSize: 11.5, lineHeight: '17px', textWrap: 'pretty' }}>{note[0]}</div>
      )}

      {m === 'keyword' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
          <Label style={{ marginRight: 3 }}>Sources</Label>
          {SOURCES.map(([id, label]) => <Chip key={id} on={d.sources.includes(id)} label={label} onClick={() => toggleSrc(id)} />)}
        </div>
      )}
      {m === 'linkedin_personal' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
          <Label style={{ marginRight: 3 }}>Collections</Label>
          {COLLECTIONS.map(([id, label]) => <Chip key={id} on={d.sources.includes(id)} label={label} onClick={() => toggleSrc(id)} />)}
          <Helper>Credentials are in Settings › Accounts</Helper>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <Cell label="Title include · comma-separated" mono value={d.title_include_keywords} onChange={(v) => set({ title_include_keywords: v })} placeholder="e.g. backend, platform" />
        <Cell label="Title exclude" mono value={d.title_exclude_keywords} onChange={(v) => set({ title_exclude_keywords: v })} placeholder="intern, junior, associate" />
        <Cell label="Company include · exact" value={d.company_filter} onChange={(v) => set({ company_filter: v })} placeholder="Any" />
        <Cell label="Company exclude · exact" value={d.company_exclude} onChange={(v) => set({ company_exclude: v })} placeholder="e.g. Walmart, CommScope" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Label>Auto-scoring</Label>
          <DepthPills value={d.auto_scoring_depth} onPick={(v) => set({ auto_scoring_depth: v })} />
          <Helper size="xs">How deeply new results are scored as they arrive</Helper>
        </div>
        {!ext ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Label>Run interval · min</Label>
            <Input type="number" min={BOUNDS.run_interval_minutes[0]} max={BOUNDS.run_interval_minutes[1]} mono
              value={d.run_interval_minutes} onChange={(v) => set({ run_interval_minutes: v })}
              ariaLabel="Run interval in minutes" style={{ width: 110 }} />
            <Helper size="xs">0 follows the global schedule from Settings</Helper>
          </div>
        ) : <div />}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Label>Import rules</Label>
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6, minHeight: 31 }}>
            <Check checked={d.exclude_active_companies} label="Skip active companies"
              title="Their Company scrapes already bring these postings"
              onChange={(v) => set({ exclude_active_companies: v })} />
            {m === 'jobright' && <Check checked={d.require_salary} label="Require salary" title="Drop results without a listed salary"
              onChange={(v) => set({ require_salary: v })} />}
          </div>
        </div>
      </div>
    </>
  )
}

// ── main screen ──────────────────────────────────────────────────────────────
export default function Searches() {
  const navigate = useNavigate()
  const [searches, setSearches] = useState([])
  const [downMap, setDownMap] = useState({})
  const [running, setRunning] = useState({})
  const [editing, setEditing] = useState(null)
  const [menuFor, setMenuFor] = useState(null)
  const [draft, setDraft] = useState(null)
  const [newOpen, setNewOpen] = useState(false)
  const [newDraft, setNewDraft] = useState(NEW_DRAFT)
  const [nextRun, setNextRun] = useState(null)
  const [test, setTest] = useState(null)       // {name, data} | {name, error}
  const [testingId, setTestingId] = useState(null)
  const [confirm, setConfirm] = useState(null)   // the shared destructive-confirm dialog
  const [busy, setBusy] = useState(null)      // 'new' | search id while a POST/PATCH is in flight
  const [testTab, setTestTab] = useState('all')
  const [reload, setReload] = useState(0)   // "Try again" re-arms the settle below
  const [loadErr, setLoadErr] = useState(null)
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()
  const mounted = useRef(true)
  useEffect(() => () => { mounted.current = false }, [])

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/searches')
      setSearches(data); setLoadErr(null)
    } catch (e) {
      console.error(e); setLoadErr(errText(e, 'Could not load your searches'))
      pushToast({ kind: 'error', msg: errText(e, 'Could not load your searches') })
    }
  }, [pushToast])
  // Health + the schedule are re-read after every mutation and whenever a run
  // finishes, not only on mount; failures stay silent and keep the last value.
  const loadAux = useCallback(() => Promise.all([
    api.get('/health/entities').then(({ data }) => { const m = {}; (data.searches || []).forEach((s) => { m[s.id] = s.reason }); setDownMap(m) }).catch(() => { /* silent — a failure leaves the last verdict in place */ }),
    api.get('/scheduler/jobs').then(({ data }) => {
      const j = (data || []).find((x) => x.id === 'scrape_all')
      if (j?.next_run) setNextRun(j.next_run)
    }).catch(() => { /* silent — the “next run” hint keeps its last value */ }),
  ]), [])
  // Cards, health verdicts, next-sweep time and the running set settle together —
  // otherwise cards render before verdicts, growing amber edges a beat later.
  const { ready } = useSettled([
    () => load(),
    () => loadAux(),
    () => api.get('/monitor/active').then(({ data }) => { const m = {}; (data || []).filter(isSearchRun).forEach((r) => { if (r.scope_key) m[r.scope_key] = true }); setRunning(m) }).catch(() => { /* silent: poller — the interval below retries */ }),
  ], reload)

  // One interval for the life of the screen — state and callbacks are read via
  // refs so a fresh `running`/`load` value each tick doesn't tear it down.
  const runningRef = useRef(running)
  const cbRef = useRef({ load, loadAux })
  useEffect(() => { runningRef.current = running }, [running])
  useEffect(() => { cbRef.current = { load, loadAux } }, [load, loadAux])
  useEffect(() => {
    const h = setInterval(async () => {
      if (!Object.keys(runningRef.current).length) return
      try {
        const { data } = await api.get('/monitor/active')
        if (!mounted.current) return
        const m = {}; (data || []).filter(isSearchRun).forEach((r) => { if (r.scope_key) m[r.scope_key] = true })
        setRunning((prev) => {
          const pk = Object.keys(prev)
          if (pk.some((k) => !m[k])) { cbRef.current.load(); cbRef.current.loadAux() }
          // keep the same object when nothing changed - otherwise every tick
          // re-rendered the whole list for nothing
          return (pk.length === Object.keys(m).length && pk.every((k) => m[k])) ? prev : m
        })
      } catch { /* retry */ }
    }, 3000)
    return () => clearInterval(h)
  }, [])

  // Relative times ("last run 3d ago", the countdown) are computed at render, so
  // without this tick they'd freeze until some other state changed.
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const h = setInterval(() => setTick((t) => t + 1), 60000)
    return () => clearInterval(h)
  }, [])

  useEffect(() => {
    const onDoc = () => setMenuFor(null)
    // Test modal is the top layer — Escape closes it alone; otherwise Escape closes
    // whichever editor is open, resetting the New-search draft like Cancel does.
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      setMenuFor(null)
      if (test) { setTest(null); return }
      if (editing) setEditing(null)
      if (newOpen) { setNewOpen(false); setNewDraft(NEW_DRAFT) }
    }
    document.addEventListener('click', onDoc); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [test, editing, newOpen])

  const nActive = searches.filter((s) => s.active).length
  // A hard-failed source is the most specific verdict, so it outranks the generic
  // ones below — otherwise "9 seen, +0 new" reads like a quiet day.
  const sourceWarnOf = (s) => {
    const errs = s.last_source_errors || []
    if (!errs.length) return null
    return `${errs.map((e) => `${e.label || e.source} failed (${e.error})`).join(' · ')} on the last run`
  }
  // a failed source wins; then an error; then health's 3-run verdict; then a
  // single clean-but-empty run
  const warnTextOf = (s) => sourceWarnOf(s) || s.last_error || downMap[s.id]
    || (s.last_run_warning ? 'Last run finished cleanly but returned no jobs' : null)
  // A paused search or an acknowledged warning is muted on the card ("paused"),
  // not driving the ▲/amber/header/rail — the backend re-raises it once a newer run fails.
  const warnMuted = (s) => !s.active || !!s.warning_acknowledged
  const warnOf = (s) => { const t = warnTextOf(s); return t && !warnMuted(s) ? t : null }
  const mutedWarnOf = (s) => {
    const t = warnTextOf(s)
    if (!t || !warnMuted(s)) return null
    return `${t} · ${s.active ? `acknowledged ${ago(s.warning_acknowledged_at)}` : 'paused'}`
  }
  // Header count uses health's verdict alone — same source as the rail's “N need
  // attention”; the row ▲ and drawer banner keep the broader warnOf() predicate.
  const nWarn = searches.filter((s) => s.active && downMap[s.id]).length
  // Warm start: counts and next-sweep time match the pre-refresh frame (the
  // countdown recomputes from the cached timestamp), then reconcile on settle.
  const { warm: sub, style: subStyle } = useWarm('searches', ready
    ? { n: searches.length, active: nActive, warn: nWarn, next: nextRun }
    : null, ready)
  const countLine = useMemo(() => {
    if (!sub) return NBSP
    const nxt = until(sub.next)
    return [
      `${sub.n} config${sub.n === 1 ? '' : 's'}`,
      `${sub.active} active`,
      ...(sub.warn ? [`${sub.warn} need attention`] : []),
      ...(nxt ? [nxt === 'due now' ? 'next scheduled run due now' : `next scheduled run in ${nxt}`] : []),
    ].join(' · ')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub && sub.n, sub && sub.active, sub && sub.warn, sub && sub.next, tick])

  const openEdit = (s) => { setMenuFor(null); if (editing === s.id) { setEditing(null); return } setEditing(s.id); setDraft(draftOf(s)) }
  const fail = (e, fallback) => { console.error(e); pushToast({ kind: 'error', msg: errText(e, fallback) }) }
  // The shell re-reads its rail badges on this event — every mutation that
  // changes how many searches exist fires it.
  const bumpCounts = () => window.dispatchEvent(new CustomEvent('jn:counts-changed'))
  const save = async (s) => {
    if (busy) return
    setBusy(s.id)
    try { await api.patch(`/searches/${s.id}`, toPayload(draft)); setEditing(null); load(); loadAux() } catch (e) { fail(e, 'Could not save this search') }
    finally { if (mounted.current) setBusy(null) }
  }
  const create = async () => {
    if (busy) return
    if (!newDraft.name.trim()) { pushToast({ kind: 'error', msg: 'Name is required' }); return }
    setBusy('new')
    try { await api.post('/searches', toPayload(newDraft)); setNewOpen(false); setNewDraft(NEW_DRAFT); load(); loadAux(); bumpCounts() }
    catch (e) { fail(e, 'Could not create this search') }
    finally { if (mounted.current) setBusy(null) }
  }
  const toggleActive = async (s) => {
    setMenuFor(null)
    // pausing/resuming changes what /health/entities counts, so the rail dot is
    // re-read too — loadAux() alone only updates this screen's own badge.
    try { await api.patch(`/searches/${s.id}`, { active: !s.active }); load(); loadAux(); bumpCounts() }
    catch (e) { fail(e, `Could not ${s.active ? 'pause' : 'resume'} “${s.name}”`) }
  }
  // “I have seen this, stop shouting” — the warning stays on the card, muted,
  // and /health/entities re-raises it by itself once a newer run fails.
  const acknowledge = async (s) => {
    try {
      await api.post(`/searches/${s.id}/acknowledge`)
      load(); loadAux(); bumpCounts()
      pushToast({ kind: 'success', msg: `“${s.name}” acknowledged — it stops counting until a later run fails` })
    } catch (e) { fail(e, `Could not acknowledge “${s.name}”`) }
  }
  const runNow = async (s) => {
    if (running[s.id]) return
    setRunning((m) => ({ ...m, [s.id]: true }))
    try { await api.post(`/searches/${s.id}/run`) } catch (e) {
      // 409 means the run is genuinely in flight — keep the spinner, the
      // /monitor/active poll clears it when the run finishes.
      if (e.response?.status === 409) { pushToast({ kind: 'progress', msg: `“${s.name}” is already running` }); return }
      fail(e, `Could not start “${s.name}”`)
      setRunning((m) => { const n = { ...m }; delete n[s.id]; return n })
    }
  }
  // The styled dialog every other v2 destructive action uses.
  const remove = (s) => {
    setMenuFor(null)
    setConfirm({
      title: `Delete “${s.name}”?`, body: 'Jobs this search already found are kept.', label: 'Delete', danger: true,
      onConfirm: async () => {
        setConfirm(null)
        try { await api.delete(`/searches/${s.id}`); load(); loadAux(); bumpCounts(); pushToast({ kind: 'success', msg: `“${s.name}” deleted` }) } catch (e) { fail(e, `Could not delete “${s.name}”`) }
      },
    })
  }
  const duplicate = async (s) => {
    setMenuFor(null)
    try { await api.post('/searches', { ...toPayload(draftOf(s)), name: `${s.name} (copy)` }); load(); loadAux(); bumpCounts() } catch (e) { fail(e, `Could not duplicate “${s.name}”`) }
  }

  const runTest = async (s) => {
    if (testingId) return                       // one Test at a time
    setMenuFor(null); setTestingId(s.id); setTestTab('all')
    // Every preview path reports failure as {"error": …} with HTTP 200 — without this
    // the modal renders the data branch and claims "No results returned." on a real error.
    const settle = (data) => setTest(data?.error ? { name: s.name, error: data.error } : { name: s.name, data })
    try {
      const res = await api.post(`/searches/${s.id}/test`, null, { timeout: 30000 })
      if (res.status === 202 && res.data?.run_id) {
        for (let i = 0; i < 100; i++) {
          await new Promise((r) => setTimeout(r, 3000))
          if (!mounted.current) return
          try {
            const p = await api.get(`/searches/test-result/${res.data.run_id}`, { timeout: 10000 })
            if (p.status === 200) { settle(p.data); setTestingId(null); return }
          } catch (err) {
            if (err.response?.status === 404) { setTest({ name: s.name, error: 'Test run expired or not found' }); setTestingId(null); return }
          }
        }
        setTest({ name: s.name, error: 'Test timed out after 5 minutes — check Stats › Run History' })
      } else settle(res.data)
    } catch (e) {
      setTest({ name: s.name, error: errText(e, e.message) })
    }
    if (mounted.current) setTestingId(null)
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* header */}
      <HeaderRow as="header" variant="screen" line="none" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Searches</PageTitle>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', ...subStyle }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button onClick={() => { setNewOpen((v) => !v); setEditing(null); setMenuFor(null) }}>+ New search</Button>
        </div>
      </HeaderRow>
      {/* the design draws the rule inset by 30px on both sides, not full-bleed */}
      <Rule tone="line" style={{ flex: '0 0 auto', margin: '0 30px' }} />

      {/* body */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '14px 30px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* new search card */}
        {newOpen && (
          <Card style={{ padding: 0, borderColor: 'var(--accent)', display: 'flex', flexDirection: 'column' }}>
            <HeaderRow pad="11px 16px" soft align="center" style={{ gap: 10 }}>
              <Heading strong size={15.5}>New search</Heading>
              <Helper>pick a mode — the fields below follow it</Helper>
            </HeaderRow>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', background: 'var(--recessed)', borderBottomLeftRadius: 8, borderBottomRightRadius: 8 }}>
              <ConfigForm d={newDraft} set={(p) => setNewDraft((x) => ({ ...x, ...p }))} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                <Helper>Runs at the next scheduled scrape after you create it</Helper>
                <Button variant="secondary" size="sm" onClick={() => { setNewOpen(false); setNewDraft(NEW_DRAFT) }} style={{ marginLeft: 'auto' }}>Cancel</Button>
                <Button size="sm" onClick={create} busy={busy === 'new'}>{busy === 'new' ? 'Creating…' : 'Create search'}</Button>
              </div>
            </div>
          </Card>
        )}

        {/* cards */}
        {searches.map((s) => {
          const warn = warnOf(s)
          const ext = isExt(s.search_mode)
          const spin = !!running[s.id]
          const [badge, badgeCls] = MODES[s.search_mode] || [String(s.search_mode || '?').toUpperCase(), 'sm-extension']
          const depth = s.auto_scoring_depth || 'off'
          const dep = DEPTHS.find((x) => x.id === depth)
          const isOpen = editing === s.id
          const testBlocked = !!testingId && testingId !== s.id
          const mutedWarn = mutedWarnOf(s)
          const summary = spin ? 'running now. Results appear in the Job Feed as they are found.' : (warn || mutedWarn || summaryOf(s))
          const summaryFg = spin ? 'var(--accent)' : warn ? 'var(--warn)' : 'var(--muted)'
          return (
            /* Same card hover as Résumés/Cover Letters, suppressed while open; a warned
               card keeps its amber edge — .v2-bd-warn comes later in theme.css so it wins over .v2-card. */
            <Card key={s.id} className={isOpen ? undefined : warn ? 'v2-card v2-bd-warn' : 'v2-card'}
              style={{ padding: 0, ...(warn ? { borderColor: 'var(--warn-line)' } : isOpen ? { borderColor: 'var(--accent)' } : null), display: 'flex', flexDirection: 'column' }}>
              {/* summary row */}
              <div onClick={() => openEdit(s)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', cursor: 'pointer' }}>
                {warn && <span title={`Needs attention — ${warn}`} style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)' }}>▲</span>}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    {/* Card's integer height comes from `Heading strong`'s own pinned line-height. */}
                    <Heading strong size={15.5} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</Heading>
                    <span className={badgeCls} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', padding: '2px 8px', borderRadius: 'var(--radius-control)', whiteSpace: 'nowrap' }}>{badge}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                    <span title={summary} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 11.5, lineHeight: '17px', color: summaryFg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{summary}</span>
                    {warn && !ext && (
                      /* ui: keep — muted 11 inline action, not the Link signature (accent 11.5/500); matches the summary line's 17px row rhythm. */
                      <span onClick={(e) => { e.stopPropagation(); acknowledge(s) }} className="v2-hover-accent-text"
                        title="Stop counting this search as needing attention. The warning stays here; a run that fails after this raises it again."
                        style={{ flex: '0 0 auto', fontSize: 11, lineHeight: '17px', color: 'var(--muted)', cursor: 'pointer' }}>Acknowledge</span>
                    )}
                  </div>
                </div>
                {depth !== 'off' && (
                  <Label title={depth === 'full'
                    ? 'Full — every new result gets a score plus the full report with keywords and requirements'
                    : 'Light: each new job gets a score. Open the job to generate a full report.'}
                    style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 5, cursor: 'help' }}>
                    {/* the same discs the Segmented cells draw — DEPTHS.dots is a count */}
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                      {Array.from({ length: dep?.dots || 0 }, (_, k) => <Dot key={k} tone="accent" size={6} />)}
                    </span>{dep?.label}
                  </Label>
                )}
                {/* fixed width so Active matches Paused and both sit on one vertical axis */}
                <Pill size="sm" on={s.active} onClick={(e) => { e.stopPropagation(); toggleActive(s) }}
                  title={ext ? (s.active ? 'Pause — captured jobs stop importing' : 'Resume importing captured jobs') : (s.active ? 'Pause. Removed from the schedule, settings kept.' : 'Resume the schedule')}
                  style={{ flex: '0 0 62px' }}>
                  {s.active ? 'Active' : 'Paused'}
                </Pill>
                {ext ? (
                  <span title="Jobs arrive from the browser extension — there is nothing to run or test"
                    style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', cursor: 'help' }}>extension • passive capture</span>
                ) : (
                  <span style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', gap: 3, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                    {/* ui: keep — running-state box: these 25px pills are padded 0 9, and the running "Running" pill was measured at that width; canonical 0 10 would widen it 2px. */}
                    <Pill size="xs" line="inherit" onClick={() => runNow(s)}
                      title={spin ? 'Run in progress — the summary line updates when it finishes' : `Run ${s.name} now, outside the schedule`}
                      style={{ padding: '0 9px', ...(spin ? { color: 'var(--pill-on-ink)' } : null) }}>
                      {spin ? <Spinner /> : <span style={{ fontSize: 11 }}>↻</span>}
                      {spin ? 'Running' : 'Run'}
                    </Pill>
                    {/* ui: keep — running-state box: 0 9 like its twin above, so the spinner branch keeps the width it was measured at. */}
                    {TESTABLE.includes(s.search_mode) && (
                      <Pill size="xs" line="inherit" disabled={testBlocked} onClick={() => runTest(s)}
                        title={testBlocked ? 'A test is already running' : 'Preview run. Shows results and why each job was kept or filtered. Saves nothing.'}
                        style={{ padding: '0 9px' }}>
                        {testingId === s.id ? <Spinner /> : <span style={{ fontSize: 11 }}>⚗</span>}Test
                      </Pill>
                    )}
                    <IconButton size={25} line="inherit" on={menuFor === s.id}
                      onClick={() => setMenuFor(menuFor === s.id ? null : s.id)}
                      title="More actions" ariaExpanded={menuFor === s.id} ariaHaspopup="menu">⋯</IconButton>
                    {menuFor === s.id && (
                      <Menu ariaLabel={`${s.name} actions`} style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 4, width: 236, textAlign: 'left' }}>
                        {[['✎', 'Edit search', () => openEdit(s)],
                          ['☰', 'View results in feed', () => navigate(`/v2/feed?search=${s.id}`)],
                          ['⧉', 'Duplicate', () => duplicate(s)]].map(([g, label, act]) => (
                          <MenuItem key={label} icon={g} onClick={act}>{label}</MenuItem>
                        ))}
                        <MenuItem danger icon="✕" onClick={() => remove(s)}>Delete search</MenuItem>
                      </Menu>
                    )}
                  </span>
                )}
              </div>

              {/* inline edit form */}
              {isOpen && draft && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', borderTop: '1px solid var(--line-soft)', background: 'var(--recessed)', borderBottomLeftRadius: 8, borderBottomRightRadius: 8 }} onClick={(e) => e.stopPropagation()}>
                  <ConfigForm d={draft} set={(p) => setDraft((x) => ({ ...x, ...p }))} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                    <Helper>Changes apply from the next run</Helper>
                    <Button variant="secondary" size="sm" onClick={() => setEditing(null)} style={{ marginLeft: 'auto' }}>Cancel</Button>
                    <Button size="sm" onClick={() => save(s)} busy={busy === s.id}>{busy === s.id ? 'Saving…' : 'Save changes'}</Button>
                  </div>
                </div>
              )}
            </Card>
          )
        })}

        {/* Error state is shown separately, or a failed GET reads as an empty
            database and the empty state flashes before the first response lands. */}
        {/* No "Loading searches…" row — the scroller keeps its box and cards draw
            once with warning edges already on. */}
        {ready && loadErr && searches.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
            <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load your searches</span>
            <Helper>{loadErr}</Helper>
            <Link onClick={() => setReload((n) => n + 1)} style={{ paddingTop: 2 }}>Try again</Link>
          </div>
        )}
        {ready && !loadErr && searches.length === 0 && !newOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>No searches yet</span>
            <Helper>Create one to add jobs to the Job Feed on a schedule.</Helper>
            <Link onClick={() => setNewOpen(true)} style={{ paddingTop: 2 }}>+ New search</Link>
          </div>
        )}
      </div>

      {test && <TestModal test={test} tab={testTab} setTab={setTestTab} onClose={() => setTest(null)} />}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── test-run modal ───────────────────────────────────────────────────────────
function TestModal({ test, tab, setTab, onClose }) {
  const d = test.data || {}
  const jobs = d.jobs || []
  const kept = jobs.filter((j) => j.kept)
  const filtered = jobs.filter((j) => !j.kept)
  const rows = tab === 'kept' ? kept : tab === 'filtered' ? filtered : jobs
  const cfg = d.config || {}
  // Footer arithmetic: `body_excluded_count` is the number the run would store as
  // `ignored`; the rest of the drops are the two title/company layers.
  const nRaw = d.raw_count ?? jobs.length
  const nKept = d.after_filter ?? kept.length
  const nBodyExcluded = d.body_excluded_count ?? 0
  const nBodyUnchecked = d.body_unchecked_count ?? 0
  // Global title-exclude list is a third filtering layer the run applies —
  // broken out here the same way Companies does it.
  const nGlobalExcluded = d.global_excluded_count ?? 0
  const nPassSearch = typeof d.after_search_filter === 'number' ? d.after_search_filter : null
  const nTitleFiltered = Math.max(0, nRaw - nKept - nBodyExcluded - nGlobalExcluded)
  const globalOut = (j) => Array.isArray(j.global_excluded_by) && j.global_excluded_by.length > 0
  // a kept row the scan couldn't run on (no description in the preview)
  const needsDesc = (j) => (d.body_phrase_count ?? 0) > 0 && j.body_checked === false && !j.body_excluded_by
  // the backend calls this `source_breakdown` on every preview path
  // (routes_searches.py:391/:621, jobright.py:730, freehire.py:330,
  // linkedin_personal.py:1123); `by_source` never existed.
  const bySource = d.source_breakdown || d.by_source || {}
  // per-board chip colours from the design: linkedin blue, indeed plum, zip amber, google red
  const srcChip = (k) => {
    if (k === 'linkedin') return { className: 'sm-keyword' }
    if (k === 'indeed') return { className: 'sm-lipersonal' }
    if (k.startsWith('zip')) return { style: { background: 'var(--warn-soft)', color: 'var(--warn)' } }
    if (k === 'google') return { style: { background: 'var(--bad-soft)', color: 'var(--bad)' } }
    return { className: 'sm-extension' }
  }

  // params strip — mode aware (v1 rendered freehire through the keyword branch)
  const params = []
  if (cfg.mode === 'jobright') {
    params.push(cfg.search_term ? `“${cfg.search_term}”` : 'AI recommendations', `${cfg.results_wanted || 100} wanted`)
  } else if (cfg.mode === 'linkedin_personal') {
    params.push(`Collections: ${(cfg.collections || cfg.sources || []).join(', ')}`)
  } else if (cfg.mode === 'levels_fyi') {
    params.push(short(cfg.url || cfg.direct_url, 70))
  } else if (cfg.mode === 'freehire') {
    if (cfg.search_term) params.push(`“${cfg.search_term}”`)
    if (cfg.direct_url) params.push(short(cfg.direct_url, 60))
    if (cfg.results_wanted) params.push(`${cfg.results_wanted} wanted`)
  } else {
    if (cfg.location) params.push(cfg.location)
    if (cfg.is_remote === true) params.push('remote only')
    if (cfg.is_remote === false) params.push('on-site only')
    if (cfg.hours_old) params.push(`${cfg.hours_old}h`)
    if (cfg.results_wanted) params.push(`${cfg.results_wanted} wanted`)
  }

  return (
    // ModalPanel brings Escape handling and pixel-snap; the scrim click already closes it.
    <ModalPanel width={980} onClose={onClose} zIndex={60} style={{ maxHeight: 660, overflow: 'hidden' }}>
        <HeaderRow variant="compact" align="center" style={{ gap: 10 }}>
          <Heading size={18} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Test run — {test.name}</Heading>
          <Helper style={{ flex: '0 0 auto' }}>preview run · saves nothing</Helper>
          <IconButton onClick={onClose} title="Close" style={{ marginLeft: 'auto' }}>✕</IconButton>
        </HeaderRow>

        {test.error ? (
          <div style={{ padding: 22, fontSize: 12.5, color: 'var(--bad)' }}>{test.error}</div>
        ) : (
          <>
            <HeaderRow pad="9px 22px" soft bg="page" align="center" style={{ flexWrap: 'wrap', fontSize: 11, color: 'var(--text-2)' }}>
              {cfg.search_term && cfg.mode !== 'jobright' && cfg.mode !== 'freehire' && (
                <span>Term <span style={{ fontFamily: 'var(--mono)', background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 'var(--radius-inline)' }}>“{cfg.search_term}”</span></span>
              )}
              <span>{params.join(' · ')}</span>
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {Object.entries(bySource).map(([k, v]) => {
                  const c = srcChip(k)
                  /* ui: keep — mono source badge on the cc- / sm- hue taxonomy (colour from `c.className`/`c.style`, which an inline Tag tone would beat). */
                  return <span key={k} className={c.className} style={{ fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 7px', borderRadius: 'var(--radius-control)', ...(c.style || {}) }}>{k} {v}</span>
                })}
              </span>
            </HeaderRow>

            <HeaderRow pad="9px 22px" soft style={{ gap: 6 }}>
              {[['all', `All (${jobs.length})`], ['kept', `Kept (${kept.length})`], ['filtered', `Filtered (${filtered.length})`]].map(([id, label]) => {
                const on = tab === id
                return (
                  <Pill key={id} size="sm" on={on} onClick={() => setTab(id)}>{label}</Pill>
                )
              })}
            </HeaderRow>

            <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              <TableHead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
                <span style={{ flex: '0 0 80px' }}>Source</span>
                <span style={{ flex: 1.3, minWidth: 0 }}>Company</span>
                <span style={{ flex: 2, minWidth: 0 }}>Title</span>
                <span style={{ flex: '0 0 116px' }}>Location</span>
                <span style={{ flex: '0 0 120px', textAlign: 'right' }}>Salary</span>
                <span style={{ flex: '0 0 44px', textAlign: 'center' }} title="Description scraped">Desc</span>
                <span style={{ flex: '0 0 66px', textAlign: 'right' }}>Status</span>
              </TableHead>
              {rows.map((j, i) => {
                const ok = !!j.kept
                const hasDesc = !!(j.desc_length || j.description_length || j.has_description)
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', minHeight: 34, padding: '2px 22px', borderBottom: '1px solid var(--line-soft)', background: ok ? 'transparent' : 'var(--bad-faint)' }}>
                    <Helper size="xs" mono style={{ flex: '0 0 80px' }}>{j.source}</Helper>
                    <span title={j.company} style={{ flex: 1.3, minWidth: 0, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.company}</span>
                    {/* A preview row can arrive with url: null — render the title as text, not a dead link. */}
                    {/* Filter reason is the point of the Filtered tab; render it under the title
                        instead of only in the OUT chip's hover tooltip. */}
                    <span style={{ flex: 2, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1, paddingRight: 8 }}>
                      {j.url
                        ? <a href={j.url} target="_blank" rel="noopener noreferrer" title={j.title} style={{ minWidth: 0, fontSize: 12, lineHeight: '17px', color: ok ? 'var(--text)' : 'var(--muted)', textDecoration: ok ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</a>
                        : <span title={j.title} style={{ minWidth: 0, fontSize: 12, lineHeight: '17px', color: ok ? 'var(--text-2)' : 'var(--muted)', textDecoration: ok ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'default' }}>{j.title}</span>}
                      {j.reason && <Helper title={j.reason} style={{ minWidth: 0, color: ok ? 'var(--muted)' : 'var(--bad)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.reason}</Helper>}
                      {/* A kept row the body scan couldn't run on isn't a promise — say which
                          check is missing rather than let the run silently mark it `ignored`. */}
                      {ok && needsDesc(j) && <Helper title="The run scans the description for body_exclusion_phrases; this preview didn’t have one" style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>body check needs the description</Helper>}
                    </span>
                    <Helper title={j.location} style={{ flex: '0 0 116px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.location}</Helper>
                    <span title={j.salary || ''} style={{ flex: '0 0 120px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.salary || '—'}</span>
                    <span style={{ flex: '0 0 44px', textAlign: 'center', fontSize: 11, color: hasDesc ? 'var(--accent)' : 'var(--line-strong)' }}>{hasDesc ? '✓' : '✕'}</span>
                    <span style={{ flex: '0 0 66px', display: 'flex', justifyContent: 'flex-end' }}>
                      {/* A body-phrase drop is stored as `ignored`, not filtered out — label it as what it becomes. */}
                      {/* ui: keep — per-row verdict badge (Tag role), not a control */}
                      {/* A global-list drop reads GLOBAL, not a bare OUT — the row passed this search's own filters. */}
                      <span title={j.reason || 'Passed all filters'} style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', background: ok ? 'var(--accent-soft)' : j.body_excluded_by ? 'var(--warn-soft)' : 'var(--bad-soft)', color: ok ? 'var(--good)' : j.body_excluded_by ? 'var(--warn)' : 'var(--bad)', cursor: j.reason ? 'help' : 'default' }}>{ok ? 'Kept' : j.body_excluded_by ? 'Ignored' : globalOut(j) ? 'Global' : 'Out'}</span>
                    </span>
                  </div>
                )
              })}
              {rows.length === 0 && (
                <div style={{ padding: 32, textAlign: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
                  {tab === 'filtered' ? 'Nothing was filtered out.' : tab === 'kept' ? 'Nothing passed the filters.' : 'No results returned.'}
                </div>
              )}
            </div>

            <FooterRow variant="compact" bg="page" style={{ flex: '0 0 auto', fontSize: 11.5, color: 'var(--text-2)' }}>
              {/* Three buckets, not two — a body-phrase drop is stored as `ignored` by
                  the run, distinct from "filtered". */}
              <span>
                <b style={{ color: 'var(--good)' }}>{nKept} kept</b> · <b style={{ color: 'var(--bad)' }}>{nTitleFiltered} title-filtered</b>
                {/* The global list gets its own term, like the Companies footer */}
                {nGlobalExcluded > 0 && (
                  <> · <b style={{ color: 'var(--bad)' }}>{nGlobalExcluded} removed by the global list</b>
                    {nPassSearch != null && <span style={{ color: 'var(--muted)' }}> ({nPassSearch} pass this search’s filters)</span>}
                  </>
                )}
                {nBodyExcluded > 0 && <> · <b style={{ color: 'var(--warn)' }}>{nBodyExcluded} would be ignored (body phrases)</b></>}
                {' · '}{nRaw} found{d.duration != null && <span style={{ color: 'var(--muted)' }}> · {d.duration}s</span>}
                {nBodyUnchecked > 0 && <span style={{ color: 'var(--muted)' }}> · {nBodyUnchecked} not body-checked (needs the description)</span>}
              </span>
              <Pill onClick={onClose} style={{ marginLeft: 'auto' }}>Close</Pill>
            </FooterRow>
          </>
        )}
    </ModalPanel>
  )
}
