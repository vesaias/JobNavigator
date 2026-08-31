import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
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
  if (m <= 0) return 'any moment'
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}
const short = (u, n = 52) => {
  const s = (u || '').replace(/^https?:\/\//, '')
  return s.length > n ? s.slice(0, n) + '…' : s
}

// mode → [badge label, badge class]. `url` is legacy: still rendered if a search
// has it, but never offered in the picker (see MODE_OPTIONS).
const MODES = {
  keyword: ['JOBSPY', 'sm-keyword'],
  levels_fyi: ['LEVELS.FYI', 'sm-levels'],
  linkedin_personal: ['LINKEDIN PERSONAL', 'sm-lipersonal'],
  jobright: ['JOBRIGHT.AI', 'sm-jobright'],
  freehire: ['FREEHIRE.ME', 'sm-freehire'],
  linkedin_extension: ['EXTENSION', 'sm-extension'],
  extension: ['EXTENSION', 'sm-extension'],
  url: ['URL', 'sm-extension'],
}
const MODE_OPTIONS = [
  ['keyword', 'Keyword (JobSpy)'],
  ['levels_fyi', 'Levels.fyi'],
  ['linkedin_personal', 'LinkedIn Personal'],
  ['jobright', 'Jobright.ai'],
  ['freehire', 'freehire.me'],
]
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

const MICRO = { fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }
const HELP = { fontSize: 10.5, color: 'var(--muted)' }

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
const NEW_DRAFT = draftOf({ sources: ['linkedin', 'indeed', 'zip_recruiter', 'google'], title_exclude_keywords: ['intern', 'junior', 'associate'] })

const toPayload = (d) => {
  const list = (v) => (v || '').split(',').map((x) => x.trim()).filter(Boolean)
  return {
    name: d.name, search_mode: d.search_mode,
    search_term: d.search_term || null, direct_url: d.direct_url || null,
    location: d.location || 'United States',
    is_remote: d.is_remote === 'true' ? true : d.is_remote === 'false' ? false : null,
    job_type: d.job_type, hours_old: parseInt(d.hours_old) || 24,
    results_wanted: parseInt(d.results_wanted) || 50,
    max_pages: parseInt(d.max_pages) || 50, min_fit_score: parseInt(d.min_fit_score) || 0,
    require_salary: !!d.require_salary, sources: d.sources,
    title_include_keywords: list(d.title_include_keywords),
    title_exclude_keywords: list(d.title_exclude_keywords),
    company_filter: list(d.company_filter), company_exclude: list(d.company_exclude),
    exclude_active_companies: !!d.exclude_active_companies,
    auto_scoring_depth: d.auto_scoring_depth,
    run_interval_minutes: parseInt(d.run_interval_minutes) || 0,
  }
}

// ── small pieces ─────────────────────────────────────────────────────────────
function Cell({ label, value, onChange, mono, placeholder, span, sub, disabled, options, type }) {
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
        : <input type={type || 'text'} value={value} disabled={disabled} placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)} style={st} />}
      {sub && <span style={{ ...HELP, textWrap: 'pretty' }}>{sub}</span>}
    </div>
  )
}
const Chip = ({ on, label, onClick }) => (
  <div onClick={onClick} className="v2-bd" style={{ height: 27, padding: '0 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer', whiteSpace: 'nowrap' }}>
    <span>{on ? '✓' : '○'}</span>{label}
  </div>
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
        <div key={d.id} title={d.hint} onClick={(e) => { e.stopPropagation(); onPick(d.id) }} className="v2-bd"
          style={{ height: 31, padding: '0 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, fontWeight: on ? 600 : 400, whiteSpace: 'nowrap', cursor: 'pointer' }}>
          <span>{d.dots}</span>{d.label}
        </div>
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
      <Cell key="ho" label="Hours old" mono type="number" value={d.hours_old} onChange={(v) => set({ hours_old: v })} />,
      <Cell key="rw" label="Results wanted" mono type="number" value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
    )
  } else if (m === 'levels_fyi') {
    fields.push(
      <Cell key="mp" label="Max pages" mono type="number" value={d.max_pages} onChange={(v) => set({ max_pages: v })} />,
      <Cell key="url" label="Levels.fyi URL · filters applied" mono span={3} value={d.direct_url} onChange={(v) => set({ direct_url: v })}
        placeholder="https://www.levels.fyi/jobs/location/united-states?jobFamilySlugs=software-engineer" />,
    )
  } else if (m === 'jobright') {
    fields.push(
      <Cell key="term" label="Search term · optional" value={d.search_term} onChange={(v) => set({ search_term: v })} placeholder="Leave empty for AI recommendations" />,
      <Cell key="rw" label="Results wanted · 20–500" mono type="number" value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
      <Cell key="ms" label="Min score" mono type="number" value={d.min_fit_score} onChange={(v) => set({ min_fit_score: v })} placeholder="0 = no filter" />,
    )
  } else if (m === 'freehire') {
    fields.push(
      <Cell key="term" label="Search term · optional" mono value={d.search_term} onChange={(v) => set({ search_term: v })} placeholder="e.g. golang backend"
        sub="ANDed with the URL — must appear in the posting text" />,
      <Cell key="url" label="freehire.me URL · filters forwarded" mono span={2} value={d.direct_url} onChange={(v) => set({ direct_url: v })}
        placeholder="https://freehire.me/?role=backend&seniority=senior&countries=us"
        sub="Role, seniority, countries, posted_within_days… pass straight through" />,
      <Cell key="rw" label="Results wanted" mono type="number" value={d.results_wanted} onChange={(v) => set({ results_wanted: v })} />,
    )
  } else if (m === 'url') {
    fields.push(<Cell key="url" label="Direct URL" mono span={2} value={d.direct_url} onChange={(v) => set({ direct_url: v })} placeholder="https://…" />)
  }

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 10 }}>{fields}</div>

      {note && (
        <div className={note[1]} style={{ padding: '9px 12px', borderRadius: 8, fontSize: 11.5, lineHeight: 1.5, textWrap: 'pretty' }}>{note[0]}</div>
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
            <input type="number" min={0} value={d.run_interval_minutes} onChange={(e) => set({ run_interval_minutes: e.target.value })}
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
  const [testTab, setTestTab] = useState('all')
  const mounted = useRef(true)
  useEffect(() => () => { mounted.current = false }, [])

  const load = useCallback(async () => {
    try { const { data } = await api.get('/searches'); setSearches(data) } catch (e) { console.error(e) }
  }, [])
  useEffect(() => {
    load()
    api.get('/health/entities').then(({ data }) => { const m = {}; (data.searches || []).forEach((s) => { m[s.id] = s.reason }); setDownMap(m) }).catch(() => {})
    api.get('/monitor/active').then(({ data }) => { const m = {}; (data || []).forEach((r) => { if (r.scope_key) m[r.scope_key] = true }); setRunning(m) }).catch(() => {})
    api.get('/scheduler/jobs').then(({ data }) => {
      const j = (data || []).find((x) => x.id === 'scrape_all')
      if (j?.next_run) setNextRun(j.next_run)
    }).catch(() => {})
  }, [load])

  // poll while anything is running
  useEffect(() => {
    if (!Object.keys(running).length) return
    const h = setInterval(async () => {
      try {
        const { data } = await api.get('/monitor/active')
        if (!mounted.current) return
        const m = {}; (data || []).forEach((r) => { if (r.scope_key) m[r.scope_key] = true })
        setRunning((prev) => { if (Object.keys(prev).some((k) => !m[k])) load(); return m })
      } catch { /* retry */ }
    }, 3000)
    return () => clearInterval(h)
  }, [running, load])

  useEffect(() => {
    const onDoc = () => setMenuFor(null)
    const onKey = (e) => { if (e.key === 'Escape') { setMenuFor(null); setTest(null) } }
    document.addEventListener('click', onDoc); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])

  const nActive = searches.filter((s) => s.active).length
  // an error wins; then health's 3-run verdict; then a single clean-but-empty run
  const warnOf = (s) => s.last_error || downMap[s.id]
    || (s.last_run_warning ? 'Last run finished cleanly but returned no jobs' : null)
  const nWarn = searches.filter((s) => warnOf(s)).length
  const countLine = [
    `${searches.length} config${searches.length === 1 ? '' : 's'}`,
    `${nActive} active`,
    ...(nWarn ? [`${nWarn} need attention`] : []),
    ...(until(nextRun) ? [`next scheduled run in ${until(nextRun)}`] : []),
  ].join(' · ')

  const openEdit = (s) => { setMenuFor(null); if (editing === s.id) { setEditing(null); return } setEditing(s.id); setDraft(draftOf(s)) }
  const save = async (s) => {
    try { await api.patch(`/searches/${s.id}`, toPayload(draft)); setEditing(null); load() } catch (e) { console.error(e); window.alert('Could not save this search') }
  }
  const create = async () => {
    if (!newDraft.name.trim()) { window.alert('Name is required'); return }
    try { await api.post('/searches', toPayload(newDraft)); setNewOpen(false); setNewDraft(NEW_DRAFT); load() }
    catch (e) { window.alert(e.response?.data?.detail || 'Could not create this search') }
  }
  const toggleActive = async (s) => { setMenuFor(null); try { await api.patch(`/searches/${s.id}`, { active: !s.active }); load() } catch (e) { console.error(e) } }
  const runNow = async (s) => {
    if (running[s.id]) return
    setRunning((m) => ({ ...m, [s.id]: true }))
    try { await api.post(`/searches/${s.id}/run`) } catch (e) { console.error(e); setRunning((m) => { const n = { ...m }; delete n[s.id]; return n }) }
  }
  const remove = async (s) => {
    setMenuFor(null)
    if (!window.confirm(`Delete "${s.name}"?`)) return
    try { await api.delete(`/searches/${s.id}`); load() } catch (e) { console.error(e) }
  }
  const duplicate = async (s) => {
    setMenuFor(null)
    try { await api.post('/searches', { ...toPayload(draftOf(s)), name: `${s.name} (copy)` }); load() } catch (e) { console.error(e) }
  }

  const runTest = async (s) => {
    setMenuFor(null); setTestingId(s.id); setTestTab('all')
    try {
      const res = await api.post(`/searches/${s.id}/test`, null, { timeout: 30000 })
      if (res.status === 202 && res.data?.run_id) {
        for (let i = 0; i < 100; i++) {
          await new Promise((r) => setTimeout(r, 3000))
          if (!mounted.current) return
          try {
            const p = await api.get(`/searches/test-result/${res.data.run_id}`, { timeout: 10000 })
            if (p.status === 200) { setTest({ name: s.name, data: p.data }); setTestingId(null); return }
          } catch (err) {
            if (err.response?.status === 404) { setTest({ name: s.name, error: 'Test run expired or not found' }); setTestingId(null); return }
          }
        }
        setTest({ name: s.name, error: 'Test timed out after 5 minutes — check Stats › Run History' })
      } else setTest({ name: s.name, data: res.data })
    } catch (e) {
      setTest({ name: s.name, error: e.response?.data?.detail || e.message })
    }
    if (mounted.current) setTestingId(null)
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* header */}
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px 24px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Searches</h1>
          <span style={{ fontSize: 13, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div onClick={() => { setNewOpen((v) => !v); setEditing(null); setMenuFor(null) }}
            style={{ flex: '0 0 auto', height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>+ New search</div>
        </div>
      </header>
      <div style={{ flex: '0 0 auto', margin: '0 30px 0 24px', borderBottom: '1px solid var(--line)' }} />

      {/* body */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '14px 30px 24px 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* new search card */}
        {newOpen && (
          <div style={{ border: '1px solid var(--accent)', borderRadius: 10, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '11px 16px', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 15.5, fontWeight: 500, letterSpacing: '-.01em' }}>New search</span>
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>pick a mode — the fields below follow it</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', background: 'var(--bg)', borderBottomLeftRadius: 9, borderBottomRightRadius: 9 }}>
              <ConfigForm d={newDraft} set={(p) => setNewDraft((x) => ({ ...x, ...p }))} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>Runs on the next scheduled sweep once created</span>
                <div onClick={() => setNewOpen(false)} className="v2-bdc" style={{ marginLeft: 'auto', height: 31, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
                <div onClick={create} style={{ height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Create search</div>
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
          const summary = spin ? 'running now — results land in the Job Feed as they arrive…' : (warn || summaryOf(s))
          const summaryFg = spin ? 'var(--accent)' : warn ? 'var(--warn)' : 'var(--muted)'
          return (
            <div key={s.id} style={{ border: `1px solid ${warn ? 'var(--warn-line)' : isOpen ? 'var(--accent)' : 'var(--line)'}`, borderRadius: 10, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
              {/* summary row */}
              <div onClick={() => openEdit(s)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 16px', cursor: 'pointer' }}>
                {warn && <span title={`Needs attention — ${warn}`} style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)' }}>▲</span>}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span style={{ fontFamily: 'var(--serif)', fontSize: 15.5, fontWeight: 500, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</span>
                    <span className={badgeCls} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', padding: '2px 8px', borderRadius: 99, whiteSpace: 'nowrap' }}>{badge}</span>
                  </div>
                  <span title={summary} style={{ fontSize: 11.5, color: summaryFg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{summary}</span>
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
                <span onClick={(e) => { e.stopPropagation(); toggleActive(s) }} className="v2-bd"
                  title={ext ? (s.active ? 'Pause — captured jobs stop importing' : 'Resume importing captured jobs') : (s.active ? 'Pause — leaves the schedule, config is kept' : 'Resume the schedule')}
                  style={{ flex: '0 0 62px', height: 23, borderRadius: 99, border: `1px solid ${s.active ? 'var(--accent)' : 'var(--edge)'}`, background: s.active ? 'var(--accent-soft)' : 'var(--surface)', color: s.active ? 'var(--accent)' : 'var(--muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>
                  {s.active ? 'Active' : 'Paused'}
                </span>
                {ext ? (
                  <span title="Jobs arrive from the browser extension — there is nothing to run or test"
                    style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', cursor: 'help' }}>extension • passive capture</span>
                ) : (
                  <span style={{ flex: '0 0 169px', marginLeft: -11, display: 'flex', justifyContent: 'flex-end', gap: 3, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                    <span onClick={() => runNow(s)} className="v2-bdc"
                      title={spin ? 'Run in progress — the summary line updates when it finishes' : `Run ${s.name} now, outside the schedule`}
                      style={{ height: 25, padding: '0 9px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: spin ? 'var(--accent)' : 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                      {spin ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /> : <span style={{ fontSize: 11 }}>↻</span>}
                      {spin ? 'Running' : 'Run'}
                    </span>
                    {TESTABLE.includes(s.search_mode) && (
                      <span onClick={() => runTest(s)} className="v2-bdc" title="Dry run — previews results and per-job filter reasons, saves nothing"
                        style={{ height: 25, padding: '0 9px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                        {testingId === s.id ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /> : <span style={{ fontSize: 11 }}>⚗</span>}Test
                      </span>
                    )}
                    <span onClick={() => setMenuFor(menuFor === s.id ? null : s.id)} className="v2-bd" title="More actions"
                      style={{ width: 25, height: 25, border: `1px solid ${menuFor === s.id ? 'var(--accent)' : 'var(--edge)'}`, background: menuFor === s.id ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>⋯</span>
                    {menuFor === s.id && (
                      <span style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 4, width: 236, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5, display: 'flex', flexDirection: 'column', textAlign: 'left' }}>
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '14px 16px', borderTop: '1px solid var(--line-soft)', background: 'var(--bg)', borderBottomLeftRadius: 9, borderBottomRightRadius: 9 }} onClick={(e) => e.stopPropagation()}>
                  <ConfigForm d={draft} set={(p) => setDraft((x) => ({ ...x, ...p }))} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 12, borderTop: '1px solid var(--line-soft)' }}>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>Changes apply from the next run</span>
                    <div onClick={() => setEditing(null)} className="v2-bdc" style={{ marginLeft: 'auto', height: 31, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
                    <div onClick={() => save(s)} style={{ height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Save changes</div>
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {searches.length === 0 && !newOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>No searches yet</span>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Create one to start pulling roles into the Job Feed on a schedule.</span>
            <span onClick={() => setNewOpen(true)} style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', paddingTop: 2 }}>+ New search</span>
          </div>
        )}
      </div>

      {test && <TestModal test={test} tab={testTab} setTab={setTestTab} onClose={() => setTest(null)} />}
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
  const bySource = d.by_source || {}
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
      <div onClick={(e) => e.stopPropagation()} style={{ width: 980, maxHeight: 660, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Test run — {test.name}</span>
          <span style={{ flex: '0 0 auto', fontSize: 11.5, color: 'var(--muted)' }}>dry run · nothing saved</span>
          <div onClick={onClose} className="v2-hover-accent" style={{ marginLeft: 'auto', flex: '0 0 auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
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
                  <div key={id} onClick={() => setTab(id)} className="v2-bd" style={{ height: 26, padding: '0 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: on ? 600 : 400, cursor: 'pointer' }}>{label}</div>
                )
              })}
            </div>

            <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              <div style={{ position: 'sticky', top: 0, zIndex: 2, background: 'var(--bg)', display: 'flex', alignItems: 'center', height: 28, padding: '0 22px', borderBottom: '1px solid var(--line-strong)', fontSize: 9.5, letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }}>
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
                    <a href={j.url} target="_blank" rel="noopener noreferrer" title={j.title} style={{ flex: 2, minWidth: 0, fontSize: 12, color: ok ? 'var(--text)' : 'var(--muted)', textDecoration: ok ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.title}</a>
                    <span title={j.location} style={{ flex: '0 0 116px', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>{j.location}</span>
                    <span title={j.salary || ''} style={{ flex: '0 0 120px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.salary || '—'}</span>
                    <span style={{ flex: '0 0 44px', textAlign: 'center', fontSize: 11, color: hasDesc ? 'var(--accent)' : 'var(--line-strong)' }}>{hasDesc ? '✓' : '✕'}</span>
                    <span style={{ flex: '0 0 66px', display: 'flex', justifyContent: 'flex-end' }}>
                      <span title={j.reason || 'Passed all filters'} style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: ok ? 'var(--accent-soft)' : 'var(--bad-soft)', color: ok ? 'var(--good)' : 'var(--bad)', cursor: j.reason ? 'help' : 'default' }}>{ok ? 'Kept' : 'Out'}</span>
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
              <span>
                <b style={{ color: 'var(--good)' }}>{d.after_filter ?? kept.length} kept</b> · <b style={{ color: 'var(--bad)' }}>{(d.raw_count ?? jobs.length) - (d.after_filter ?? kept.length)} filtered</b> · {d.raw_count ?? jobs.length} raw{d.duration != null && <span style={{ color: 'var(--muted)' }}> · {d.duration}s</span>}
              </span>
              <div onClick={onClose} className="v2-bdc" style={{ marginLeft: 'auto', height: 31, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Close</div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
