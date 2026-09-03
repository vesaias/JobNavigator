import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import ConfirmDialog from './ConfirmDialog'
import { Button, IconButton, Pill } from './ui'
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
// /monitor/active carries every background job. Only POST /searches/{id}/run
// tags its run with job_type 'search_run' (routes_searches.py) - company scrapes
// and resume jobs also carry a scope_key, and used to keep this screen polling.
const isSearchRun = (r) => r?.job_type === 'search_run'
const EXT_MODES = ['linkedin_extension', 'extension']
const isExt = (m) => EXT_MODES.includes(m)
const TESTABLE = ['keyword', 'levels_fyi', 'linkedin_personal', 'jobright', 'freehire']

const DEPTHS = [
  { id: 'off', label: 'Off', dots: '', hint: 'New results arrive unscored — score them by hand from the feed' },
  { id: 'light', label: 'Light', dots: '●', hint: 'Score only — cheap enough to leave on' },
  { id: 'full', label: 'Full', dots: '●●', hint: 'Score plus the full report with keywords and requirements' },
]
const SOURCES = [['linkedin', 'LinkedIn'], ['indeed', 'Indeed'], ['zip_recruiter', 'ZipRecruiter'], ['google', 'Google Jobs'], ['direct', 'Direct (Playwright)']]
const COLLECTIONS = [['recommended', 'Recommended'], ['top-applicant', 'Top Applicant']]

const MICRO = { fontSize: 9.5, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }
const HELP = { fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)' }

// note banners reuse the mode-badge palettes (sm-levels green / sm-jobright teal)
const noteFor = (mode) => {
  if (mode === 'levels_fyi') return ['Configure filters on levels.fyi, then paste the URL here — location, job family, salary and recency are all encoded in it.', 'sm-levels']
  if (mode === 'jobright') return ['Personalized AI recommendations from your Jobright.ai account. A search term switches it to search mode; credentials live in Settings.', 'sm-jobright']
  if (mode === 'extension') return ['Jobs arrive via the “Save to Job Feed” button on any website. Set auto-score depth and the filters below — they apply as each job is saved.', 'sm-levels']
  if (mode === 'linkedin_extension') return ['Jobs import via passive capture on linkedin.com/jobs/collections/* pages. The filters below auto-filter during import.', 'sm-levels']
  return null
}

// one-line "what this search does", mirroring the design's summary strings
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
// R2-H-03: a new search opens on Light, the same as the Add-company modal — the
// two creation flows used to disagree (off vs light) on the one control that
// spends money per scraped job.
const NEW_DRAFT = draftOf({ sources: ['linkedin', 'indeed', 'zip_recruiter', 'google'], title_exclude_keywords: ['intern', 'junior', 'associate'], auto_scoring_depth: 'light' })

// R2-A-02: the numeric bounds live in one place so an input's min/max and the
// payload clamp can't drift apart (COMP-12 did the same for Companies).
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
  // SRCH-12: `parseInt(x) || fallback` turned an explicit 0 into 24 / 50. A
  // cleared field now goes out as null — the backend falls back to the column
  // default on create and stores NULL on update, which reads back as the default.
  const num = (v) => { const n = parseInt(v, 10); return Number.isNaN(n) ? null : n }
  // R2-A-02: `parseInt(x) || fallback` swallowed a legal 0 (max_pages 0 became 50)
  // and let a negative page count or a 999-page run reach the wire, while the
  // "20–500" label enforced nothing. Clamp to the bounds the inputs declare; a
  // cleared field still goes out as null so the column default applies.
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
  // SRCH-12: location is a keyword-search field only — sending it for
  // levels_fyi / jobright / freehire / extension searches means nothing.
  if (d.search_mode === 'keyword') p.location = d.location || 'United States'
  return p
}

// ── small pieces ─────────────────────────────────────────────────────────────
function Cell({ label, value, onChange, mono, placeholder, span, sub, disabled, options, type, min, max }) {   // R2-A-02: min/max
  const st = {
    width: '100%', height: 31, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 7,
    background: disabled ? 'var(--surface-2)' : 'var(--surface)', color: disabled ? 'var(--muted)' : 'var(--text)',
    fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5, outline: 'none',
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: span ? `span ${span}` : undefined, minWidth: 0 }}>
      <span style={MICRO}>{label}</span>
      {options
        ? <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} style={st}>
            {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        : <input type={type || 'text'} value={value} disabled={disabled} placeholder={placeholder} min={min} max={max}
            onChange={(e) => onChange(e.target.value)} style={st} />}
      {sub && <span style={{ ...HELP, textWrap: 'pretty' }}>{sub}</span>}
    </div>
  )
}
const Chip = ({ on, label, onClick }) => (
  <Pill size="sm" on={on} onClick={onClick}>
    <span>{on ? '✓' : '○'}</span>{label}
  </Pill>
)
const Check = ({ on, label, title, onClick }) => (
  <div onClick={onClick} title={title} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>
    <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent)' : 'var(--surface)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>{on ? '✓' : ''}</span>
    {label}
  </div>
)
const DepthPills = ({ value, onPick }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 4, height: 31 }}>
    {DEPTHS.map((d) => {
      const on = value === d.id
      return (
        <Pill key={d.id} on={on} title={d.hint} onClick={(e) => { e.stopPropagation(); onPick(d.id) }}>
          <span>{d.dots}</span>{d.label}
        </Pill>
      )
    })}
  </div>
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
        sub="ANDed with the URL — must appear in the posting text" />,
      <Cell key="url" label="freehire.me URL · filters forwarded" mono span={2} value={d.direct_url} onChange={(v) => set({ direct_url: v })}
        placeholder="https://freehire.me/?role=backend&seniority=senior&countries=us"
        sub="Role, seniority, countries, posted_within_days… pass straight through" />,
      <Cell key="rw" label="Results wanted · 1–500" mono type="number" min={BOUNDS.results_wanted[0]} max={BOUNDS.results_wanted[1]} value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
    )
  }

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 10 }}>{fields}</div>

      {note && (
        <div className={note[1]} style={{ padding: '9px 12px', borderRadius: 8, fontSize: 11.5, lineHeight: '17px', textWrap: 'pretty' }}>{note[0]}</div>
      )}

      {m === 'keyword' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ ...MICRO, marginRight: 3 }}>Sources</span>
          {SOURCES.map(([id, label]) => <Chip key={id} on={d.sources.includes(id)} label={label} onClick={() => toggleSrc(id)} />)}
        </div>
      )}
      {m === 'linkedin_personal' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ ...MICRO, marginRight: 3 }}>Collections</span>
          {COLLECTIONS.map(([id, label]) => <Chip key={id} on={d.sources.includes(id)} label={label} onClick={() => toggleSrc(id)} />)}
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>Credentials live in Settings › Accounts</span>
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
          <span style={MICRO}>Auto-scoring</span>
          <DepthPills value={d.auto_scoring_depth} onPick={(v) => set({ auto_scoring_depth: v })} />
          <span style={HELP}>How deeply new results are scored as they arrive</span>
        </div>
        {!ext ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={MICRO}>Run interval · min</span>
            <input type="number" min={BOUNDS.run_interval_minutes[0]} max={BOUNDS.run_interval_minutes[1]} value={d.run_interval_minutes} onChange={(e) => set({ run_interval_minutes: e.target.value })}
              style={{ width: 110, height: 31, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 7, background: 'var(--surface)', color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 11.5, outline: 'none' }} />
            <span style={HELP}>0 follows the global schedule from Settings</span>
          </div>
        ) : <div />}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={MICRO}>Import rules</span>
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6, minHeight: 31 }}>
            <Check on={d.exclude_active_companies} label="Skip active companies"
              title="Their Company scrapes already bring these postings"
              onClick={() => set({ exclude_active_companies: !d.exclude_active_companies })} />
            {m === 'jobright' && <Check on={d.require_salary} label="Require salary" title="Drop results without a listed salary"
              onClick={() => set({ require_salary: !d.require_salary })} />}
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
  const [confirm, setConfirm] = useState(null)   // R2-A-01: the shared destructive-confirm dialog
  const [busy, setBusy] = useState(null)      // SRCH-29: 'new' | search id while a POST/PATCH is in flight
  const [testTab, setTestTab] = useState('all')
  const [loading, setLoading] = useState(true)
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
    } finally { setLoading(false) }
  }, [pushToast])
  // SRCH-24: health + the schedule are re-read after every mutation and whenever
  // a run finishes, not only on mount. Failures stay silent and leave whatever
  // was loaded before in place.
  const loadAux = useCallback(() => {
    api.get('/health/entities').then(({ data }) => { const m = {}; (data.searches || []).forEach((s) => { m[s.id] = s.reason }); setDownMap(m) }).catch(() => { /* silent: SRCH-24 — re-read after every mutation; a failure leaves the last verdict in place */ })
    api.get('/scheduler/jobs').then(({ data }) => {
      const j = (data || []).find((x) => x.id === 'scrape_all')
      if (j?.next_run) setNextRun(j.next_run)
    }).catch(() => { /* silent: SRCH-24 — the “next run” hint keeps its last value */ })
  }, [])
  useEffect(() => {
    load()
    loadAux()
    api.get('/monitor/active').then(({ data }) => { const m = {}; (data || []).filter(isSearchRun).forEach((r) => { if (r.scope_key) m[r.scope_key] = true }); setRunning(m) }).catch(() => { /* silent: poller — the interval below retries */ })
  }, [load, loadAux])

  // SRCH-28: one interval for the life of the screen. It used to list `running`
  // and `load` as deps, so every tick (which always wrote a fresh object) tore
  // the timer down and rebuilt it; state and callbacks are read through refs now.
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

  // SRCH-20: relative times ("last run 3d ago", the countdown) are computed at
  // render, so without this they froze until some other state changed.
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const h = setInterval(() => setTick((t) => t + 1), 60000)
    return () => clearInterval(h)
  }, [])

  useEffect(() => {
    const onDoc = () => setMenuFor(null)
    // SRCH-21: the test modal is the top layer - Escape closes it alone;
    // otherwise Escape closes whichever editor is open (drawer / New search),
    // and the New-search draft is reset exactly as its Cancel button does.
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
  // R3-A-03: a board that hard-failed on the last run is the most specific thing
  // we can say, so it outranks the generic verdicts below — "9 seen, +0 new"
  // otherwise reads like a quiet day on every configured source.
  const sourceWarnOf = (s) => {
    const errs = s.last_source_errors || []
    if (!errs.length) return null
    return `${errs.map((e) => `${e.label || e.source} failed (${e.error})`).join(' · ')} on the last run`
  }
  // a failed source wins; then an error; then health's 3-run verdict; then a
  // single clean-but-empty run
  const warnTextOf = (s) => sourceWarnOf(s) || s.last_error || downMap[s.id]
    || (s.last_run_warning ? 'Last run finished cleanly but returned no jobs' : null)
  // A paused search is not an open problem: it was switched off deliberately, so
  // its last-run state stays on the card as history — muted, labelled “paused” —
  // rather than driving the ▲, the amber edge, the header count and the rail dot.
  // Same for a warning the operator acknowledged, until a newer run fails
  // (the backend re-raises it by itself; `warning_acknowledged` says which).
  const warnMuted = (s) => !s.active || !!s.warning_acknowledged
  const warnOf = (s) => { const t = warnTextOf(s); return t && !warnMuted(s) ? t : null }
  const mutedWarnOf = (s) => {
    const t = warnTextOf(s)
    if (!t || !warnMuted(s)) return null
    return `${t} · ${s.active ? `acknowledged ${ago(s.warning_acknowledged_at)}` : 'paused'}`
  }
  // SRCH-09: the header count uses health's verdict alone — the same source as
  // the rail's “N sources need attention”. The row ▲ and the drawer banner keep
  // the broader warnOf() predicate.
  const nWarn = searches.filter((s) => s.active && downMap[s.id]).length
  const countLine = useMemo(() => {
    const nxt = until(nextRun)
    return [
      `${searches.length} config${searches.length === 1 ? '' : 's'}`,
      `${nActive} active`,
      ...(nWarn ? [`${nWarn} need attention`] : []),
      ...(nxt ? [nxt === 'due now' ? 'next scheduled run due now' : `next scheduled run in ${nxt}`] : []),
    ].join(' · ')
  }, [searches.length, nActive, nWarn, nextRun, tick])

  const openEdit = (s) => { setMenuFor(null); if (editing === s.id) { setEditing(null); return } setEditing(s.id); setDraft(draftOf(s)) }
  const fail = (e, fallback) => { console.error(e); pushToast({ kind: 'error', msg: errText(e, fallback) }) }
  // SRCH-10: the shell re-reads its rail badges on this event, so every mutation
  // that changes how many searches exist fires it.
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
  // R2-A-01: the styled dialog every other v2 destructive action uses.
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
    if (testingId) return                       // SRCH-23: one Test at a time
    setMenuFor(null); setTestingId(s.id); setTestTab('all')
    // Every preview path (jobright/freehire/linkedin_personal, and the keyword
    // scrape-failed branch) reports failure as {"error": …} with HTTP 200.
    // Without this the modal would render the data branch and claim
    // "No results returned." over a real error.
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
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Searches</h1>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button onClick={() => { setNewOpen((v) => !v); setEditing(null); setMenuFor(null) }}>+ New search</Button>
        </div>
      </header>
      {/* the design draws the rule inset by 30px on both sides, not full-bleed */}
      <div style={{ flex: '0 0 auto', height: 1, margin: '0 30px', background: 'var(--line)' }} />

      {/* body */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '14px 30px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* new search card */}
        {newOpen && (
          <div style={{ border: '1px solid var(--accent)', borderRadius: 10, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '11px 16px', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 15.5, fontWeight: 500, letterSpacing: '-.01em' }}>New search</span>
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>pick a mode — the fields below follow it</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', background: 'var(--recessed)', borderBottomLeftRadius: 9, borderBottomRightRadius: 9 }}>
              <ConfigForm d={newDraft} set={(p) => setNewDraft((x) => ({ ...x, ...p }))} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>Runs on the next scheduled sweep once created</span>
                <Button variant="secondary" size="sm" onClick={() => { setNewOpen(false); setNewDraft(NEW_DRAFT) }} style={{ marginLeft: 'auto' }}>Cancel</Button>
                <Button size="sm" onClick={create} busy={busy === 'new'}>{busy === 'new' ? 'Creating…' : 'Create search'}</Button>
              </div>
            </div>
          </div>
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
          const testBlocked = !!testingId && testingId !== s.id   // SRCH-23
          const mutedWarn = mutedWarnOf(s)
          const summary = spin ? 'running now — results land in the Job Feed as they arrive…' : (warn || mutedWarn || summaryOf(s))
          const summaryFg = spin ? 'var(--accent)' : warn ? 'var(--warn)' : 'var(--muted)'
          return (
            /* same card hover as Résumés and Cover Letters. Not while open — the
               expanded editor shouldn't wash under the cursor — and a warned card
               keeps its amber edge (.v2-bd-warn comes later in theme.css, so its
               border-color wins over .v2-card's accent). */
            <div key={s.id} className={isOpen ? undefined : warn ? 'v2-card v2-bd-warn' : 'v2-card'}
              style={{ border: `1px solid ${warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : 'var(--line)'}`, borderRadius: 10, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
              {/* summary row */}
              <div onClick={() => openEdit(s)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', cursor: 'pointer' }}>
                {warn && <span title={`Needs attention — ${warn}`} style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)' }}>▲</span>}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    {/* integer line-heights: 15.5px/11.5px text under Tailwind
                        preflight's 1.5 gives a 67.5px card, so every other row
                        lands on x.5 and Chrome rounds its 1px border away. */}
                    <span style={{ fontFamily: 'var(--serif)', fontSize: 15.5, lineHeight: '23px', fontWeight: 500, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</span>
                    <span className={badgeCls} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', padding: '2px 8px', borderRadius: 99, whiteSpace: 'nowrap' }}>{badge}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                    <span title={summary} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 11.5, lineHeight: '17px', color: summaryFg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{summary}</span>
                    {warn && !ext && (
                      <span onClick={(e) => { e.stopPropagation(); acknowledge(s) }} className="v2-hover-accent-text"
                        title="Stop counting this search as needing attention. The warning stays here; a run that fails after this raises it again."
                        style={{ flex: '0 0 auto', fontSize: 11, lineHeight: '17px', color: 'var(--muted)', cursor: 'pointer' }}>Acknowledge</span>
                    )}
                  </div>
                </div>
                {depth !== 'off' && (
                  <span title={depth === 'full'
                    ? 'Full — every new result gets a score plus the full report with keywords and requirements'
                    : 'Light — every new result gets a score only; open a job to generate its report'}
                    style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--muted)', cursor: 'help' }}>
                    <span style={{ color: 'var(--accent)', letterSpacing: 2, fontSize: 9 }}>{dep?.dots}</span>{dep?.label}
                  </span>
                )}
                {/* fixed width so Active matches Paused and both sit on one vertical axis */}
                <Pill size="sm" on={s.active} onClick={(e) => { e.stopPropagation(); toggleActive(s) }}
                  title={ext ? (s.active ? 'Pause — captured jobs stop importing' : 'Resume importing captured jobs') : (s.active ? 'Pause — leaves the schedule, config is kept' : 'Resume the schedule')}
                  style={{ flex: '0 0 62px' }}>
                  {s.active ? 'Active' : 'Paused'}
                </Pill>
                {ext ? (
                  <span title="Jobs arrive from the browser extension — there is nothing to run or test"
                    style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', cursor: 'help' }}>extension • passive capture</span>
                ) : (
                  <span style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', gap: 3, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                    {/* ui: keep — 25px Run pill matched to the Test pill beside it (Test carries an opacity state the scan left unclassified) */}
                    <span onClick={() => runNow(s)} className="v2-bdc"
                      title={spin ? 'Run in progress — the summary line updates when it finishes' : `Run ${s.name} now, outside the schedule`}
                      style={{ height: 25, padding: '0 9px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: spin ? 'var(--accent)' : 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                      {spin ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /> : <span style={{ fontSize: 11 }}>↻</span>}
                      {spin ? 'Running' : 'Run'}
                    </span>
                    {TESTABLE.includes(s.search_mode) && (
                      <span onClick={testBlocked ? undefined : () => runTest(s)} className={testBlocked ? undefined : 'v2-bdc'}
                        title={testBlocked ? 'A test is already running' : 'Dry run — previews results and per-job filter reasons, saves nothing'}
                        style={{ height: 25, padding: '0 9px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: testBlocked ? 'default' : 'pointer', opacity: testBlocked ? .5 : 1 }}>
                        {testingId === s.id ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /> : <span style={{ fontSize: 11 }}>⚗</span>}Test
                      </span>
                    )}
                    {/* ui: keep — 25x25 ⋯ sized to its Run/Test row siblings; IconButton's bordered look is 36 */}
                    <span onClick={() => setMenuFor(menuFor === s.id ? null : s.id)} className="v2-bd" title="More actions"
                      style={{ width: 25, height: 25, border: `1px solid ${menuFor === s.id ? 'var(--accent)' : 'var(--edge)'}`, background: menuFor === s.id ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>⋯</span>
                    {menuFor === s.id && (
                      <span style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 4, width: 236, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)', padding: 5, display: 'flex', flexDirection: 'column', textAlign: 'left' }}>
                        {[['✎', 'Edit search', () => openEdit(s)],
                          ['☰', 'View results in feed', () => navigate(`/v2/feed?search=${s.id}`)],
                          ['⧉', 'Duplicate', () => duplicate(s)]].map(([g, label, act]) => (
                          <span key={label} onClick={act} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>
                            <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>{g}</span>{label}
                          </span>
                        ))}
                        <span onClick={() => remove(s)} className="v2-hover-bad" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--bad)', cursor: 'pointer', marginTop: 3, borderTop: '1px solid var(--line-soft)' }}>
                          <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11 }}>✕</span>Delete search
                        </span>
                      </span>
                    )}
                  </span>
                )}
              </div>

              {/* inline edit form */}
              {isOpen && draft && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', borderTop: '1px solid var(--line-soft)', background: 'var(--recessed)', borderBottomLeftRadius: 9, borderBottomRightRadius: 9 }} onClick={(e) => e.stopPropagation()}>
                  <ConfigForm d={draft} set={(p) => setDraft((x) => ({ ...x, ...p }))} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>Changes apply from the next run</span>
                    <Button variant="secondary" size="sm" onClick={() => setEditing(null)} style={{ marginLeft: 'auto' }}>Cancel</Button>
                    <Button size="sm" onClick={() => save(s)} busy={busy === s.id}>{busy === s.id ? 'Saving…' : 'Save changes'}</Button>
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {/* a failed GET used to fall through to "No searches yet", which reads
            as an empty database; and the empty state flashed on every mount
            before the first response landed. */}
        {loading && searches.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '44px 30px', fontSize: 11.5, color: 'var(--muted)' }}>
            <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--muted)', borderTopColor: 'transparent', borderRadius: 99 }} />Loading searches…
          </div>
        )}
        {!loading && loadErr && searches.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
            <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load your searches</span>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{loadErr}</span>
            <span onClick={() => { setLoading(true); load() }} style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', paddingTop: 2 }}>Try again</span>
          </div>
        )}
        {!loading && !loadErr && searches.length === 0 && !newOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>No searches yet</span>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Create one to start pulling roles into the Job Feed on a schedule.</span>
            <span onClick={() => setNewOpen(true)} style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', paddingTop: 2 }}>+ New search</span>
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
  // R3-A-01 footer arithmetic. `body_excluded_count` is the number the run would
  // store as `ignored`; the rest of the drops are the two title/company layers.
  const nRaw = d.raw_count ?? jobs.length
  const nKept = d.after_filter ?? kept.length
  const nBodyExcluded = d.body_excluded_count ?? 0
  const nBodyUnchecked = d.body_unchecked_count ?? 0
  const nTitleFiltered = Math.max(0, nRaw - nKept - nBodyExcluded)
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
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 980, maxHeight: 660, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Test run — {test.name}</span>
          <span style={{ flex: '0 0 auto', fontSize: 11.5, color: 'var(--muted)' }}>dry run · nothing saved</span>
          <IconButton onClick={onClose} title="Close" style={{ marginLeft: 'auto' }}>✕</IconButton>
        </div>

        {test.error ? (
          <div style={{ padding: 22, fontSize: 12.5, color: 'var(--bad)' }}>{test.error}</div>
        ) : (
          <>
            <div style={{ flex: '0 0 auto', padding: '9px 22px', borderBottom: '1px solid var(--line-soft)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-2)' }}>
              {cfg.search_term && cfg.mode !== 'jobright' && cfg.mode !== 'freehire' && (
                <span>Term <span style={{ fontFamily: 'var(--mono)', background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>“{cfg.search_term}”</span></span>
              )}
              <span>{params.join(' · ')}</span>
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {Object.entries(bySource).map(([k, v]) => {
                  const c = srcChip(k)
                  return <span key={k} className={c.className} style={{ fontFamily: 'var(--mono)', fontSize: 10, padding: '1px 7px', borderRadius: 99, ...(c.style || {}) }}>{k} {v}</span>
                })}
              </span>
            </div>

            <div style={{ flex: '0 0 auto', padding: '9px 22px', borderBottom: '1px solid var(--line-soft)', display: 'flex', gap: 6 }}>
              {[['all', `All (${jobs.length})`], ['kept', `Kept (${kept.length})`], ['filtered', `Filtered (${filtered.length})`]].map(([id, label]) => {
                const on = tab === id
                return (
                  <Pill key={id} size="sm" on={on} onClick={() => setTab(id)}>{label}</Pill>
                )
              })}
            </div>

            <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              <div style={{ position: 'sticky', top: 0, zIndex: 2, background: 'var(--bg)', display: 'flex', alignItems: 'center', height: 28, padding: '0 22px', borderBottom: '1px solid var(--line-strong)', fontSize: 9.5, lineHeight: '14px', letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }}>
                <span style={{ flex: '0 0 80px' }}>Source</span>
                <span style={{ flex: 1.3, minWidth: 0 }}>Company</span>
                <span style={{ flex: 2, minWidth: 0 }}>Title</span>
                <span style={{ flex: '0 0 116px' }}>Location</span>
                <span style={{ flex: '0 0 120px', textAlign: 'right' }}>Salary</span>
                <span style={{ flex: '0 0 44px', textAlign: 'center' }} title="Description scraped">Desc</span>
                <span style={{ flex: '0 0 66px', textAlign: 'right' }}>Status</span>
              </div>
              {rows.map((j, i) => {
                const ok = !!j.kept
                const hasDesc = !!(j.desc_length || j.description_length || j.has_description)
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', minHeight: 34, padding: '2px 22px', borderBottom: '1px solid var(--line-soft)', background: ok ? 'transparent' : 'var(--bad-faint)' }}>
                    <span style={{ flex: '0 0 80px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>{j.source}</span>
                    <span title={j.company} style={{ flex: 1.3, minWidth: 0, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.company}</span>
                    {/* SRCH-27: a preview row can arrive with url: null - render
                        the title as text then, not as a link that goes nowhere */}
                    {/* R2-H-01: the reason a row was filtered is the whole point of
                        the Filtered tab, and it only existed on the OUT chip's
                        title= — one hover per row. Render it under the title. */}
                    <span style={{ flex: 2, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1, paddingRight: 8 }}>
                      {j.url
                        ? <a href={j.url} target="_blank" rel="noopener noreferrer" title={j.title} style={{ minWidth: 0, fontSize: 12, lineHeight: '17px', color: ok ? 'var(--text)' : 'var(--muted)', textDecoration: ok ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</a>
                        : <span title={j.title} style={{ minWidth: 0, fontSize: 12, lineHeight: '17px', color: ok ? 'var(--text-2)' : 'var(--muted)', textDecoration: ok ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'default' }}>{j.title}</span>}
                      {j.reason && <span title={j.reason} style={{ minWidth: 0, fontSize: 11, lineHeight: '15px', color: ok ? 'var(--muted)' : 'var(--bad)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.reason}</span>}
                      {/* R3-A-01: a kept row the body scan could not run on is not
                          a promise — say which check is missing rather than let
                          the run turn it into an `ignored` row unexplained. */}
                      {ok && needsDesc(j) && <span title="The run scans the description for body_exclusion_phrases; this preview didn’t have one" style={{ minWidth: 0, fontSize: 11, lineHeight: '15px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>body check needs the description</span>}
                    </span>
                    <span title={j.location} style={{ flex: '0 0 116px', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.location}</span>
                    <span title={j.salary || ''} style={{ flex: '0 0 120px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.salary || '—'}</span>
                    <span style={{ flex: '0 0 44px', textAlign: 'center', fontSize: 11, color: hasDesc ? 'var(--accent)' : 'var(--line-strong)' }}>{hasDesc ? '✓' : '✕'}</span>
                    <span style={{ flex: '0 0 66px', display: 'flex', justifyContent: 'flex-end' }}>
                      {/* R3-A-01: a body-phrase drop is stored as `ignored`, not
                          filtered out of the feed — label it as what it becomes. */}
                      {/* ui: keep — per-row verdict badge (Tag role), not a control */}
                      <span title={j.reason || 'Passed all filters'} style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: ok ? 'var(--accent-soft)' : j.body_excluded_by ? 'var(--warn-soft)' : 'var(--bad-soft)', color: ok ? 'var(--good)' : j.body_excluded_by ? 'var(--warn)' : 'var(--bad)', cursor: j.reason ? 'help' : 'default' }}>{ok ? 'Kept' : j.body_excluded_by ? 'Ignored' : 'Out'}</span>
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

            <div style={{ flex: '0 0 auto', padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9, fontSize: 11.5, color: 'var(--text-2)' }}>
              {/* R3-A-01: three buckets, not two — a body-phrase drop is stored
                  as `ignored` by the run and used to hide inside "filtered". */}
              <span>
                <b style={{ color: 'var(--good)' }}>{nKept} kept</b> · <b style={{ color: 'var(--bad)' }}>{nTitleFiltered} title-filtered</b>
                {nBodyExcluded > 0 && <> · <b style={{ color: 'var(--warn)' }}>{nBodyExcluded} would be ignored (body phrases)</b></>}
                {' · '}{nRaw} raw{d.duration != null && <span style={{ color: 'var(--muted)' }}> · {d.duration}s</span>}
                {nBodyUnchecked > 0 && <span style={{ color: 'var(--muted)' }}> · {nBodyUnchecked} not body-checked (needs the description)</span>}
              </span>
              <Pill onClick={onClose} style={{ marginLeft: 'auto' }}>Close</Pill>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
