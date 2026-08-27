import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react'
import api from '../api'

const FILTERS_KEY = 'v2_feed_filters'
const SORT_KEY = 'v2_feed_sort'

// ── helpers ──────────────────────────────────────────────────────────────
const ROW_C = 2 * Math.PI * 17.5   // row ring (viewBox 44, r17.5)
const BAND_C = 2 * Math.PI * 35     // band ring (viewBox 78, r35)
const timeAgo = (s) => {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
const isToday = (s) => s && (Date.now() - new Date(s).getTime()) < 86400000
const scoreColor = (s) => (s >= 80 ? 'var(--good)' : s >= 65 ? 'var(--text-2)' : 'var(--warn)')
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
const SOURCE_LABELS = {
  direct: 'Direct', extension: 'Extension', jobspy_linkedin: 'LinkedIn', jobspy_indeed: 'Indeed',
  jobspy_zip_recruiter: 'ZipRecruiter', jobspy_google: 'Google', levels_fyi: 'Levels', linkedin_personal: 'LinkedIn',
  linkedin_extension: 'LinkedIn', jobright: 'Jobright', freehire: 'FreeHire', playwright_url: 'Company careers', playwright_direct: 'Company careers',
}
const srcLabel = (s) => SOURCE_LABELS[s] || s || ''
const STATUS_OPTS = [['new', 'New'], ['saved', 'Saved'], ['applied', 'Applied'], ['skip', 'Skip'], ['ignored', 'Ignored']]
const SORT_OPTS = [['score', 'Top score'], ['date', 'Newest first'], ['salary', 'Salary, high to low'], ['company', 'Company A–Z']]
const DEFAULTS = { status: ['new', 'saved', 'applied'], company: [], source: [], h1b_verdict: [], min_score: '', min_salary: '', max_salary: '' }

// small dropdown shell (trigger pill + panel + backdrop). Flips to right-align
// when the panel would overflow the viewport's right edge.
function Drop({ label, active, open, onToggle, children, align = 'left', width = 216, trigger }) {
  const ref = useRef(null)
  const [side, setSide] = useState(align)
  useLayoutEffect(() => {
    if (!open || !ref.current) { return }
    const r = ref.current.getBoundingClientRect()
    setSide(r.left + width > window.innerWidth - 14 ? 'right' : align)
  }, [open, width, align])
  return (
    <div ref={ref} style={{ position: 'relative', flex: '0 0 auto' }}>
      {trigger ? trigger(onToggle) : (
        <div onClick={onToggle} style={{ height: 30, padding: '0 13px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, cursor: 'pointer',
          border: `1px solid ${active ? 'var(--accent)' : 'var(--line)'}`, background: active ? 'var(--accent-soft)' : 'var(--surface)', color: active ? 'var(--accent)' : 'var(--text-2)' }}>
          {label}<span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>
        </div>
      )}
      {open && (
        <>
          <div onClick={onToggle} style={{ position: 'fixed', inset: 0, zIndex: 34 }} />
          <div className="v2-scroll" style={{ position: 'absolute', top: '100%', [side]: 0, zIndex: 35, marginTop: 5, width, maxHeight: 340, overflow: 'auto',
            background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 8 }}>
            {children}
          </div>
        </>
      )}
    </div>
  )
}
function Check({ on, label, onClick }) {
  return (
    <div className="v2-menuitem" onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '6px 8px', borderRadius: 6, cursor: 'pointer', fontSize: 12.5, color: 'var(--text-2)' }}>
      <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: on ? 'none' : '1px solid var(--line)', background: on ? 'var(--accent)' : 'transparent', color: '#fff', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{on ? '✓' : ''}</span>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  )
}

// ── component ────────────────────────────────────────────────────────────
export default function V2JobFeed() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem(FILTERS_KEY)); if (s) return { ...DEFAULTS, ...s } } catch {}
    return DEFAULTS
  })
  const [sortBy, setSortBy] = useState(() => { try { return localStorage.getItem(SORT_KEY) || 'score' } catch { return 'score' } })
  useEffect(() => { try { localStorage.setItem(FILTERS_KEY, JSON.stringify(filters)) } catch {} }, [filters])
  useEffect(() => { try { localStorage.setItem(SORT_KEY, sortBy) } catch {} }, [sortBy])
  const [search, setSearch] = useState('')
  const [dSearch, setDSearch] = useState('')
  const [menu, setMenu] = useState(null)

  const [sel, setSel] = useState(0)
  const [detail, setDetail] = useState(null)
  const [headOpen, setHeadOpen] = useState(true)
  const [reportOpen, setReportOpen] = useState(false)
  const [reportTab, setReportTab] = useState(0)
  const [reqFilter, setReqFilter] = useState('all')
  const [showMatched, setShowMatched] = useState(false)
  const [viewCached, setViewCached] = useState(false)
  const [cachedHtml, setCachedHtml] = useState(null)

  const [companyList, setCompanyList] = useState([])
  const [sourceList, setSourceList] = useState([])
  const [verdictList, setVerdictList] = useState([])
  const [resumes, setResumes] = useState([])
  const [stats, setStats] = useState({ arrived_today: 0, unscored: 0 })
  const [picker, setPicker] = useState(null)      // {mode, jobs:[...]}
  const [rowMenu, setRowMenu] = useState(null)
  const [headMenu, setHeadMenu] = useState(false)
  const [checked, setChecked] = useState(() => new Set())
  const lastIdx = useRef(null)

  const listRef = useRef(null)
  const jobsRef = useRef(jobs); useEffect(() => { jobsRef.current = jobs }, [jobs])
  const selRef = useRef(sel); useEffect(() => { selRef.current = sel }, [sel])

  useEffect(() => { const t = setTimeout(() => setDSearch(search), 400); return () => clearTimeout(t) }, [search])
  useEffect(() => {
    api.get('/jobs/companies/list').then(({ data }) => setCompanyList(data || [])).catch(() => {})
    api.get('/jobs/sources/list').then(({ data }) => setSourceList(data || [])).catch(() => {})
    api.get('/jobs/verdicts/list').then(({ data }) => setVerdictList(data || [])).catch(() => {})
    api.get('/resumes?is_base=true').then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/jobs/feed-stats').then(({ data }) => setStats(data)).catch(() => {})
  }, [])

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    try {
      const p = { limit: 80, offset: 0 }
      if (filters.status.length) p.status = filters.status.join(',')
      if (filters.company.length) p.company = filters.company.join(',')
      if (filters.source.length) p.source = filters.source.join(',')
      if (filters.h1b_verdict.length) p.h1b_verdict = filters.h1b_verdict.join(',')
      if (filters.min_score !== '') p.min_score = filters.min_score
      if (filters.min_salary) p.min_salary = Number(filters.min_salary) * 1000
      if (filters.max_salary) p.max_salary = Number(filters.max_salary) * 1000
      if (dSearch) p.title_search = dSearch
      if (sortBy !== 'date') p.sort_by = sortBy
      const { data } = await api.get('/jobs', { params: p })
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
    } catch (e) { console.error('v2 feed load failed', e) }
    setLoading(false)
  }, [filters, sortBy, dSearch])
  useEffect(() => { fetchJobs() }, [fetchJobs])

  const focusAt = useCallback((idx) => {
    const list = jobsRef.current
    if (idx < 0 || idx >= list.length) return
    setSel(idx); lastIdx.current = idx
    const j = list[idx]
    setDetail(j); setReportOpen(false); setReportTab(0); setViewCached(false); setCachedHtml(null); setReqFilter('all'); setShowMatched(false)
    api.get(`/jobs/${j.id}`).then(({ data }) => setDetail((c) => (c && c.id === data.id ? data : c))).catch(() => {})
  }, [])
  useEffect(() => {
    if (loading) return
    if (jobs.length === 0) { setDetail(null); return }
    focusAt(Math.min(sel, jobs.length - 1))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, loading])

  const patchLocal = useCallback((id, changes) => {
    const leaves = filters.status.length && changes.status && !filters.status.includes(changes.status)
    setJobs((prev) => leaves ? (setTotal((t) => Math.max(0, t - 1)), prev.filter((j) => j.id !== id)) : prev.map((j) => (j.id === id ? { ...j, ...changes } : j)))
    setDetail((d) => (d && d.id === id ? { ...d, ...changes } : d))
  }, [filters.status])
  const patchRemote = useCallback(async (job, changes) => {
    patchLocal(job.id, changes)
    try { await api.patch(`/jobs/${job.id}`, changes) } catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])
  const saveJob = (j) => patchRemote(j, { saved: !j.saved, status: j.saved ? 'new' : 'saved' })
  const skipJob = (j) => patchRemote(j, { status: 'skip' })
  const applyJob = (j) => patchRemote(j, { status: 'applied' })
  // "Ignore {company} everywhere" — add to the global company-exclude setting
  // (matches classic ignoreCompany) and drop every job from that company now.
  const ignoreCompany = useCallback(async (job) => {
    const name = (job.company || '').trim()
    setJobs((prev) => prev.filter((x) => (x.company || '').toLowerCase() !== name.toLowerCase()))
    setDetail((dd) => (dd && (dd.company || '').toLowerCase() === name.toLowerCase() ? null : dd))
    if (!name) return
    try {
      const { data: settings } = await api.get('/settings')
      const cur = Array.isArray(settings.company_exclude_global) ? settings.company_exclude_global : []
      if (!cur.some((c) => c.toLowerCase() === name.toLowerCase())) {
        await api.patch('/settings', { company_exclude_global: [...cur, name] })
      }
    } catch (e) { console.error(e); fetchJobs() }
  }, [fetchJobs])
  const scoreJob = useCallback((job) => {
    api.post(`/analyze/${job.id}?depth=full`, {}).then(() => setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'analyze_job'])] } : x))).catch(console.error)
  }, [])

  const runResume = useCallback(async (mode, list, baseId) => {
    setPicker(null)
    for (const job of list) {
      try {
        if (mode === 'copy') { const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: job.id }); if (list.length === 1) window.location.href = `/resumes?resume=${data.id}` }
        else { await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: job.id }); setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'tailor_resume'])] } : x)) }
      } catch (e) { console.error(`${mode} failed`, e.response?.data?.detail || e.message) }
    }
    setChecked(new Set())
  }, [])
  const openTailored = useCallback(async (job) => {
    try { const { data } = await api.get('/resumes'); const copy = (data || []).find((r) => !r.is_base && r.job_id === job.id); if (copy) { window.location.href = `/resumes?resume=${copy.id}`; return } } catch {}
    setPicker({ mode: 'tailor', jobs: [job] })
  }, [])

  const unscored = useMemo(() => jobs.filter((j) => scoredCount(j) === 0 && ['new', 'saved'].includes(j.status)), [jobs])

  // selection
  const rowClick = (e, i, job) => {
    if (e.metaKey || e.ctrlKey) { setChecked((p) => { const n = new Set(p); n.has(job.id) ? n.delete(job.id) : n.add(job.id); return n }); lastIdx.current = i; return }
    if (e.shiftKey && lastIdx.current != null) { const [a, b] = [lastIdx.current, i].sort((x, y) => x - y); setChecked((p) => { const n = new Set(p); for (let k = a; k <= b; k++) n.add(jobs[k].id); return n }); return }
    focusAt(i)
  }
  const bulkStatus = async (status) => {
    const ids = [...checked]; if (!ids.length) return
    const updates = status === 'saved' ? { saved: true, status: 'saved' } : { status }
    try { await api.post('/jobs/bulk-update', { job_ids: ids, updates }); setChecked(new Set()); fetchJobs() } catch (e) { console.error(e) }
  }
  const bulkScore = () => { jobs.filter((j) => checked.has(j.id) && scoredCount(j) === 0).forEach(scoreJob); setChecked(new Set()) }

  // keyboard
  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      const list = jobsRef.current, idx = selRef.current, job = list[idx]
      switch (e.key) {
        case 'j': case 'ArrowDown': e.preventDefault(); focusAt(Math.min(idx + 1, list.length - 1)); break
        case 'k': case 'ArrowUp': e.preventDefault(); focusAt(Math.max(idx - 1, 0)); break
        case 's': if (job) { saveJob(job); focusAt(Math.min(idx + 1, list.length - 1)) } break
        case 'x': if (job) { skipJob(job); focusAt(Math.min(idx, list.length - 2)) } break
        case 'a': if (job) applyJob(job); break
        case 'e': if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer'); break
        case 'r': if (job) scoreJob(job); break
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
    api.get(`/jobs/${detail.id}/cached-page`).then(({ data }) => setCachedHtml(data.cached_page_html || (data.cached_page_text ? `<pre style="white-space:pre-wrap;font-family:sans-serif;padding:16px">${data.cached_page_text}</pre>` : '<p style="padding:16px">No cached snapshot.</p>'))).catch(() => setCachedHtml('<p style="padding:16px">No cached snapshot.</p>'))
  }, [detail, viewCached, cachedHtml])

  const setF = (patch) => { setFilters((f) => ({ ...f, ...patch })); setSel(0) }
  const togF = (key, val) => setF({ [key]: filters[key].includes(val) ? filters[key].filter((x) => x !== val) : [...filters[key], val] })

  const d = detail
  const arrivedToday = jobs.filter((j) => isToday(j.discovered_at)).length
  const visaText = d ? `${(H1B[d.h1b_verdict] || H1B.unknown).label}${d.h1b_company_lca_count ? ` · ${d.h1b_company_lca_count} LCAs` : ' · no LCA records'}` : ''
  const visaCol = d ? (d.h1b_verdict === 'likely' ? 'var(--good)' : d.h1b_verdict === 'unlikely' ? 'var(--warn)' : 'var(--muted)') : ''

  // ── detail report derivation ──
  const reports = d ? scoreEntries(d).map(([name, score]) => ({ name, score, tailored: isTailoredName(name), rpt: (d.scoring_report || {})[name] })).sort((a, b) => b.score - a.score) : []
  const best = reports[0]
  const active = reports[Math.min(reportTab, Math.max(0, reports.length - 1))]
  const rpt = active?.rpt
  const reqRows = rpt?.requirement_mapping || []
  const reqMet = reqRows.filter((r) => r.matched).length
  const coverage = rpt?.keyword_coverage_pct
  const dScored = reports.length > 0
  const running = d && (d.in_flight || []).some((o) => o === 'analyze_job')
  const dCached = d && d.status === 'applied' && d.has_cached_page

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* header */}
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>The Feed</h1>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>{total} open roles · {stats.arrived_today} arrived today · {stats.unscored} not yet scored</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search titles…" style={{ width: 200, height: 36, padding: '0 4px', border: 'none', borderBottom: '1px solid var(--line)', fontSize: 13.5, fontFamily: 'var(--sans)', outline: 'none', background: 'transparent' }} />
          {stats.unscored > 0 && <div onClick={() => unscored.slice(0, 50).forEach(scoreJob)} title={unscored.length ? `Scores the ${unscored.length} unscored roles in view` : 'No unscored roles in the current view'} style={{ height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, cursor: 'pointer' }}>Score {stats.unscored} unscored jobs</div>}
        </div>
      </header>

      {/* filter bar */}
      <div style={{ flex: '0 0 auto', padding: '0 30px 14px', display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--line)' }}>
        <Drop label="Source" active={filters.source.length > 0} open={menu === 'source'} onToggle={() => setMenu(menu === 'source' ? null : 'source')}>
          {sourceList.length ? sourceList.map((s) => <Check key={s} on={filters.source.includes(s)} label={srcLabel(s)} onClick={() => togF('source', s)} />) : <div style={{ padding: 8, fontSize: 12, color: 'var(--muted)' }}>No sources</div>}
        </Drop>
        <Drop label="Company" active={filters.company.length > 0} open={menu === 'company'} onToggle={() => setMenu(menu === 'company' ? null : 'company')} width={248}>
          <div style={{ height: 30, padding: '0 10px', border: '1px solid var(--line)', borderRadius: 7, display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--muted)', background: 'var(--surface-2)', marginBottom: 6 }}>Type to search {companyList.length} companies…</div>
          {companyList.slice(0, 60).map((c) => <Check key={c} on={filters.company.includes(c)} label={c} onClick={() => togF('company', c)} />)}
        </Drop>
        <Drop label="H-1B" active={filters.h1b_verdict.length > 0} open={menu === 'h1b'} onToggle={() => setMenu(menu === 'h1b' ? null : 'h1b')} width={196}>
          {['likely', 'possible', 'unlikely', 'unknown'].filter((v) => verdictList.includes(v)).map((v) => <Check key={v} on={filters.h1b_verdict.includes(v)} label={H1B[v].label.replace('H-1B ', '')} onClick={() => togF('h1b_verdict', v)} />)}
        </Drop>
        <Drop label="Score ≥" active={filters.min_score !== ''} open={menu === 'score'} onToggle={() => setMenu(menu === 'score' ? null : 'score')} width={212}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[70, 80, 90].map((n) => <div key={n} onClick={() => setF({ min_score: String(n) })} style={{ flex: 1, height: 28, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, cursor: 'pointer', border: `1px solid ${filters.min_score === String(n) ? 'var(--accent)' : 'var(--line)'}`, background: filters.min_score === String(n) ? 'var(--accent-soft)' : 'transparent', color: filters.min_score === String(n) ? 'var(--accent)' : 'var(--text-2)' }}>{n}</div>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>or at least</span>
            <input type="number" value={filters.min_score} onChange={(e) => setF({ min_score: e.target.value })} style={{ flex: 1, height: 28, padding: '0 9px', border: '1px solid var(--line)', borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--surface-2)' }} />
          </div>
          <div style={{ marginTop: 8, fontSize: 10.5, color: 'var(--muted)' }}>Unscored jobs stay visible — this only hides low scores</div>
        </Drop>
        <Drop label="Salary" active={!!(filters.min_salary || filters.max_salary)} open={menu === 'salary'} onToggle={() => setMenu(menu === 'salary' ? null : 'salary')} width={224}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[150, 180, 220].map((n) => <div key={n} onClick={() => setF({ min_salary: String(n) })} style={{ flex: 1, height: 28, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, cursor: 'pointer', border: `1px solid ${filters.min_salary === String(n) ? 'var(--accent)' : 'var(--line)'}`, background: filters.min_salary === String(n) ? 'var(--accent-soft)' : 'transparent', color: filters.min_salary === String(n) ? 'var(--accent)' : 'var(--text-2)' }}>${n}K</div>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>at least</span>
            <input type="number" placeholder="$K" value={filters.min_salary} onChange={(e) => setF({ min_salary: e.target.value })} style={{ flex: 1, height: 28, padding: '0 9px', border: '1px solid var(--line)', borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--surface-2)' }} />
          </div>
          <div style={{ marginTop: 8, fontSize: 10.5, color: 'var(--muted)' }}>Jobs without a listed salary stay visible</div>
        </Drop>
        <Drop align="left" width={170} active open={menu === 'status'} onToggle={() => setMenu(menu === 'status' ? null : 'status')}
          trigger={(t) => (
            <div onClick={t} style={{ height: 30, padding: '0 13px', borderRadius: 99, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>
              Status · {filters.status.map((s) => STATUS_OPTS.find((o) => o[0] === s)?.[1]).join(', ') || 'Any'}
              <span onClick={(e) => { e.stopPropagation(); setF({ status: [] }) }} style={{ opacity: 0.55 }}>✕</span>
            </div>
          )}>
          {STATUS_OPTS.map(([v, label]) => <Check key={v} on={filters.status.includes(v)} label={label} onClick={() => togF('status', v)} />)}
        </Drop>
        <div style={{ marginLeft: 'auto', flex: '0 0 auto' }}>
          <Drop align="right" width={172} open={menu === 'sort'} onToggle={() => setMenu(menu === 'sort' ? null : 'sort')}
            trigger={(t) => <div onClick={t} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORT_OPTS.find((o) => o[0] === sortBy)?.[1]}</span><span style={{ fontSize: 10 }}>▾</span></div>}>
            {SORT_OPTS.map(([v, label]) => (
              <div key={v} className="v2-menuitem" onClick={() => { setSortBy(v); setMenu(null); setSel(0) }} style={{ display: 'flex', alignItems: 'center', padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: sortBy === v ? 'var(--accent)' : 'var(--text-2)', fontWeight: sortBy === v ? 500 : 400, background: sortBy === v ? 'var(--accent-soft)' : 'transparent' }}>{label}{sortBy === v && <span style={{ marginLeft: 'auto' }}>✓</span>}</div>
            ))}
          </Drop>
        </div>
      </div>

      {/* body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* list */}
        <section style={{ position: 'relative', width: 472, flex: '0 0 472px', borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ padding: '12px 22px 8px', display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'var(--muted)' }}>
            <span>{jobs.length} shown · {total} matching</span>
            <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10.5, letterSpacing: '.05em' }}>⇧ range · ⌘ pick · s save · x skip</span>
          </div>

          {checked.size > 0 && (
            <div style={{ position: 'absolute', left: '50%', bottom: 14, transform: 'translateX(-50%)', zIndex: 25, display: 'flex', alignItems: 'center', gap: 6, padding: '7px 8px 7px 14px', background: 'var(--rail)', borderRadius: 99, boxShadow: '0 10px 30px rgba(0,0,0,.28)' }}>
              <span style={{ fontSize: 12, color: '#f6f3ea', fontWeight: 600, whiteSpace: 'nowrap' }}>{checked.size} selected</span>
              <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,.18)', margin: '0 3px' }} />
              <div onClick={() => bulkStatus('saved')} style={{ height: 27, padding: '0 12px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: 500, cursor: 'pointer' }}>Save</div>
              <div onClick={() => bulkStatus('skip')} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.25)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}>Skip</div>
              <div onClick={bulkScore} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.25)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}>Score</div>
              <div onClick={() => setPicker({ mode: 'tailor', jobs: jobs.filter((j) => checked.has(j.id)) })} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.25)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}><span style={{ color: '#8dbb9f' }}>✦</span>Tailor</div>
              <div onClick={() => setChecked(new Set())} style={{ width: 27, height: 27, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'rgba(255,255,255,.55)', cursor: 'pointer' }}>✕</div>
            </div>
          )}

          <div ref={listRef} className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px 12px', display: 'flex', flexDirection: 'column' }}>
            {loading ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
              : jobs.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No jobs match.</div>
              : jobs.map((j, i) => {
                const score = bestScore(j), nsc = scoredCount(j)
                const badge = BADGE[j.status]
                const run = (j.in_flight || []).length > 0
                const dim = j.status === 'ignored' || j.status === 'skip'
                const on = checked.has(j.id)
                const visa = H1B[j.h1b_verdict]
                return (
                  <div key={j.id} data-row={i} className="v2-row" onClick={(e) => rowClick(e, i, j)}
                    style={{ flex: '0 0 auto', display: 'flex', alignItems: 'stretch', borderBottom: '1px solid var(--line-soft)', cursor: 'pointer', borderRadius: 8, background: i === sel ? 'var(--surface-2)' : 'transparent', overflow: 'hidden' }}>
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 14, padding: 12, opacity: dim ? 0.5 : 1 }}>
                      {/* ring */}
                      <div style={{ position: 'relative', width: 40, height: 40, flex: '0 0 40px' }}>
                        {nsc > 0 ? (
                          <>
                            <svg viewBox="0 0 44 44" style={{ width: 40, height: 40, transform: 'rotate(-90deg)' }}>
                              <circle cx="22" cy="22" r="17.5" fill="none" stroke="var(--line)" strokeWidth="1.5" />
                              <circle cx="22" cy="22" r="17.5" fill="none" stroke={scoreColor(score)} strokeWidth="1.5" strokeLinecap="round" strokeDasharray={`${(ROW_C * score / 100).toFixed(1)} ${ROW_C.toFixed(0)}`} />
                            </svg>
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 15, color: scoreColor(score) }}>{score}</div>
                            {nsc > 1 && <div title={`${nsc} résumé reports`} style={{ position: 'absolute', right: -3, bottom: -2, minWidth: 15, height: 15, padding: '0 3px', borderRadius: 99, background: 'var(--surface)', border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-2)' }}>{nsc}</div>}
                          </>
                        ) : run ? (
                          <>
                            <div className="v2-spin" style={{ position: 'absolute', inset: 0, border: '1px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, letterSpacing: '.07em', textTransform: 'uppercase', color: 'var(--accent)' }}>···</div>
                          </>
                        ) : (
                          <div className="v2-hover-accent" onClick={(e) => { e.stopPropagation(); scoreJob(j) }} title="Score this role" style={{ position: 'absolute', inset: 0, border: '1px dashed var(--line)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8.5, fontWeight: 600, letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--muted)', cursor: 'pointer' }}>Score</div>
                        )}
                        {on && <div style={{ position: 'absolute', left: -4, top: -3, width: 16, height: 16, borderRadius: 99, background: 'var(--accent)', border: '2px solid var(--surface)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>✓</div>}
                      </div>
                      {/* text */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }}>
                          <span title={j.title} style={{ flex: 1, minWidth: 0, fontFamily: 'var(--serif)', fontSize: 16, fontWeight: 500, lineHeight: 1.15, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textDecoration: j.status === 'skip' ? 'line-through' : 'none', textDecorationColor: 'var(--muted)' }}>{j.title}</span>
                          {badge && <span style={{ flex: '0 0 auto', fontSize: 9.5, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, border: `1px solid ${badge.bd}`, background: badge.bg, color: badge.fg }}>{badge.label}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, lineHeight: 1.2, color: 'var(--text-2)', minWidth: 0 }}>
                          <span title={j.company} style={{ flex: '0 1 auto', minWidth: 40, maxWidth: 170, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.company}</span>
                          <span style={{ flex: '0 0 auto', color: 'var(--line)' }}>|</span>
                          <span title={j.location} style={{ flex: '1 1 auto', minWidth: 40, color: j.location ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.location || 'Location not specified'}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 11, lineHeight: 1.2, minWidth: 0 }}>
                          <span style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 160, fontFamily: 'var(--mono)', color: fmtSalary(j.salary_min, j.salary_max) ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtSalary(j.salary_min, j.salary_max) || 'Salary not listed'}</span>
                          {visa && <><span style={{ color: 'var(--line)' }}>·</span><span style={{ letterSpacing: '.04em', color: visa.c }}>{visa.label}</span></>}
                          <span style={{ color: 'var(--line)' }}>·</span><span style={{ color: 'var(--muted)' }}>{timeAgo(j.discovered_at)}</span>
                        </div>
                      </div>
                    </div>
                    {/* action column */}
                    <div style={{ position: 'relative', flex: '0 0 27px', display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--line-soft)', opacity: i === sel ? 1 : 0.55 }} onClick={(e) => e.stopPropagation()}>
                      <div className="v2-rail-save v2-rail-cell" title="Save (s)" onClick={() => saveJob(j)} style={{ flex: 1, fontSize: 11, color: j.saved ? 'var(--accent)' : 'var(--text-2)', borderBottom: '1px solid var(--line-soft)' }}>♥</div>
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
                          <div style={{ position: 'fixed', left: rowMenu.left, top: rowMenu.top, bottom: rowMenu.bottom, zIndex: 60, width: 228, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                            {[['Mark applied', 'a', () => applyJob(j)], ['Tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [j] })], ['Rescore', 'r', () => scoreJob(j)], ['Open posting ↗', 'e', () => j.url && window.open(j.url, '_blank', 'noopener,noreferrer')]].map(([label, kb, act]) => (
                              <div key={label} className="v2-menuitem" onClick={() => { setRowMenu(null); act() }} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer', fontWeight: label === 'Tailor résumé' ? 600 : 400 }}>{label}<span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>{kb}</span></div>
                            ))}
                            <div style={{ height: 1, margin: '4px 8px', background: 'var(--line-soft)' }} />
                            <div className="v2-hover-bad" onClick={() => { setRowMenu(null); ignoreCompany(j) }} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 11px', borderRadius: 6, fontSize: 13, color: 'var(--bad)', cursor: 'pointer' }}>Ignore {j.company} everywhere</div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
        </section>

        {/* detail */}
        <section style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 }}>
          {!d ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Select a job.</div> : (
            <>
              {/* header */}
              <div style={{ flex: '0 0 auto', padding: headOpen ? '20px 30px 15px' : '11px 30px 12px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: headOpen ? 14 : 10 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 3, marginLeft: -26 }}>
                  <div onClick={() => setHeadOpen((v) => !v)} className="v2-hover-accent" style={{ flex: '0 0 auto', width: 19, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--muted)', cursor: 'pointer' }}>{headOpen ? '⌄' : '›'}</div>
                  <div onClick={() => setHeadOpen((v) => !v)} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6, cursor: 'pointer' }}>
                    {headOpen && <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 10.5, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>
                      <span style={{ maxWidth: 300, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.company}</span><span>·</span><span>{srcLabel(d.source)}</span><span>·</span><span>{timeAgo(d.discovered_at)}</span>
                    </div>}
                    <h2 title={d.title} style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: headOpen ? 26 : 17, fontWeight: 400, letterSpacing: '-.025em', lineHeight: 1.15, display: '-webkit-box', WebkitLineClamp: headOpen ? 2 : 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{d.title}</h2>
                    {headOpen ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: 'var(--text-2)', flexWrap: 'wrap', rowGap: 3 }}>
                        <span style={{ maxWidth: 230, fontFamily: 'var(--mono)', fontSize: 12.5, color: fmtSalary(d.salary_min, d.salary_max) ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtSalary(d.salary_min, d.salary_max) || 'Salary not listed'}</span>
                        <span style={{ color: 'var(--line)' }}>|</span>
                        <span style={{ maxWidth: 270, color: d.location ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.location || 'Location not specified'}</span>
                        <span style={{ color: 'var(--line)' }}>|</span>
                        <span style={{ color: visaCol }}>{visaText}</span>
                      </div>
                    ) : <span style={{ fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{[d.company, fmtSalary(d.salary_min, d.salary_max) || 'Salary not listed', d.location || 'Location not specified', visaText, srcLabel(d.source), timeAgo(d.discovered_at)].join(' · ')}</span>}
                  </div>
                  {/* actions */}
                  <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {d.url && <a href={d.url} target="_blank" rel="noopener noreferrer" className="v2-act" style={{ height: headOpen ? 36 : 30, padding: '0 14px', border: '1px solid var(--line)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--text-2)' }}><span style={{ fontSize: 9, color: 'var(--muted)' }}>●</span>Open ↗</a>}
                    <div onClick={() => openTailored(d)} style={{ height: headOpen ? 36 : 30, padding: '0 19px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>✦ Open tailored ↗</div>
                    <div style={{ position: 'relative', flex: '0 0 auto' }}>
                      <div title="More actions" onClick={(e) => { e.stopPropagation(); setHeadMenu((v) => !v) }} className="v2-act" style={{ width: headOpen ? 36 : 30, height: headOpen ? 36 : 30, border: `1px solid ${headMenu ? 'var(--accent)' : 'var(--line)'}`, background: headMenu ? 'var(--accent-soft)' : 'transparent', color: headMenu ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, cursor: 'pointer' }}>⋯</div>
                      {headMenu && (
                        <>
                          <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                          <div style={{ position: 'absolute', top: '100%', right: 0, zIndex: 45, marginTop: 5, width: 236, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                            {[
                              ['✦ Re-tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [d] }), true],
                              ['Mark applied', 'a', () => applyJob(d)],
                              ['Rescore', 'r', () => scoreJob(d)],
                              ['Cover letter ↗', 'c', () => { window.location.href = `/cover-letters?job=${d.id}` }],
                              ['Copy résumé with tracers', '', () => setPicker({ mode: 'copy', jobs: [d] })],
                            ].map(([label, kb, act, bold]) => (
                              <div key={label} className="v2-menuitem" onClick={() => { setHeadMenu(false); act() }} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 11px', borderRadius: 6, fontSize: 13, color: bold ? 'var(--text)' : 'var(--text-2)', fontWeight: bold ? 600 : 400, cursor: 'pointer' }}>{label}{kb && <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>{kb}</span>}</div>
                            ))}
                            <div style={{ height: 1, margin: '4px 8px', background: 'var(--line-soft)' }} />
                            <div className="v2-hover-bad" onClick={() => { setHeadMenu(false); ignoreCompany(d) }} style={{ padding: '8px 11px', borderRadius: 6, fontSize: 13, color: 'var(--bad)', cursor: 'pointer' }}>Ignore {d.company} everywhere</div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* report band */}
              {dScored && (
                <div style={{ position: 'relative', zIndex: 18, flex: reportOpen ? '1 1 0%' : '0 0 auto', minHeight: 0, borderBottom: '1px solid var(--line)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column' }}>
                  <div onClick={() => { setReportOpen((v) => !v); if (!reportOpen && best) setReportTab(Math.max(0, reports.indexOf(best))) }} className="v2-hover-accent" style={{ flex: '0 0 auto', padding: '8px 30px 8px 4px', display: 'flex', alignItems: 'center', gap: 9, cursor: 'pointer' }}>
                    <span style={{ flex: '0 0 auto', width: 19, textAlign: 'center', color: 'var(--muted)', fontSize: 11 }}>{reportOpen ? '⌄' : '›'}</span>
                    <div style={{ position: 'relative', width: 34, height: 34, flex: '0 0 34px', marginLeft: -4 }}>
                      <svg viewBox="0 0 78 78" style={{ width: 34, height: 34, transform: 'rotate(-90deg)' }}>
                        <circle cx="39" cy="39" r="35" fill="none" stroke="var(--line)" strokeWidth="5" />
                        <circle cx="39" cy="39" r="35" fill="none" stroke="var(--accent)" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(BAND_C * (best?.score || 0) / 100).toFixed(1)} 220`} />
                      </svg>
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 14, letterSpacing: '-.02em' }}>{best?.score}</div>
                    </div>
                    <span title={best?.name} style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 220, fontSize: 12.5, color: 'var(--text-2)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{best?.tailored ? '✦ ' : ''}{best?.name}</span>
                    {coverage != null && <><span style={{ width: 1, height: 14, background: 'var(--line)' }} /><span style={{ fontSize: 12.5, color: 'var(--muted)' }}>{coverage}% keywords</span></>}
                    {reqRows.length > 0 && <><span style={{ width: 1, height: 14, background: 'var(--line)' }} /><span style={{ flex: 1, minWidth: 0, fontSize: 12.5, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{reqMet} of {reqRows.length} requirements met</span></>}
                    <span style={{ marginLeft: 'auto', width: 1, height: 14, background: 'var(--line)' }} />
                    <span style={{ flex: '0 0 auto', fontSize: 12.5, color: 'var(--muted)' }}>{reports.length} report{reports.length === 1 ? '' : 's'}</span>
                  </div>
                  {reportOpen && (
                    <div style={{ borderTop: '2px solid var(--accent)', background: 'var(--surface)', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                      {/* tabs */}
                      <div style={{ flex: '0 0 auto', padding: '0 30px', display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--line)' }}>
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
                        <div onClick={() => scoreJob(d)} className="v2-navlink" style={{ marginLeft: 'auto', padding: '7px 0', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>+ Rescore</div>
                      </div>
                      {/* body */}
                      <div className="v2-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '14px 30px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {rpt?.summary && <span style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-2)' }}>{rpt.summary}</span>}
                        {(d.fit_strengths || []).length > 0 && !rpt?.summary && <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{(d.fit_strengths || []).map((s, k) => <div key={k} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--good)' }}>✓</span><span>{s}</span></div>)}</div>}

                        {coverage != null && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Keyword coverage</span>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: coverage >= 75 ? 'var(--good)' : coverage >= 50 ? 'var(--warn)' : 'var(--bad)' }}>{coverage}%</span>
                            </div>
                            <div style={{ height: 4, borderRadius: 99, background: 'var(--line)' }}><div style={{ height: 4, borderRadius: 99, background: coverage >= 75 ? 'var(--good)' : coverage >= 50 ? 'var(--warn)' : 'var(--bad)', width: `${coverage}%` }} /></div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 3 }}>
                              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{(rpt.matched_keywords || []).length} matched · {(rpt.missing_keywords || []).length} missing</span>
                              {(rpt.matched_keywords || []).length > 0 && <div onClick={() => setShowMatched((v) => !v)} style={{ fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>{showMatched ? 'Hide matched' : 'Show matched'}</div>}
                            </div>
                            {showMatched && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingTop: 2 }}>{(rpt.matched_keywords || []).map((w, k) => <span key={k} style={{ fontFamily: 'var(--mono)', fontSize: 10.5, padding: '3px 7px', borderRadius: 99, background: 'var(--accent-soft)', color: 'var(--good)' }}>{w}</span>)}</div>}
                            {(rpt.missing_keywords || []).length > 0 && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingTop: 2 }}>{(rpt.missing_keywords || []).map((w, k) => <span key={k} style={{ fontFamily: 'var(--mono)', fontSize: 10.5, padding: '3px 7px', borderRadius: 99, background: 'var(--bad-soft)', color: 'var(--bad)' }}>{w}</span>)}</div>}
                          </div>
                        )}

                        {reqRows.length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                              <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Requirement mapping</span>
                              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{reqMet} of {reqRows.length} met</span>
                              <div style={{ marginLeft: 'auto', display: 'flex', border: '1px solid var(--line)', borderRadius: 99, overflow: 'hidden' }}>
                                {[['all', `All ${reqRows.length}`], ['gaps', `Gaps ${reqRows.length - reqMet}`]].map(([id, label]) => <div key={id} onClick={() => setReqFilter(id)} style={{ height: 24, padding: '0 11px', display: 'flex', alignItems: 'center', fontSize: 11.5, cursor: 'pointer', background: reqFilter === id ? 'var(--accent)' : 'transparent', color: reqFilter === id ? '#fff' : 'var(--text-2)' }}>{label}</div>)}
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 14, padding: '0 0 6px', borderBottom: '1px solid var(--line)', fontSize: 9.5, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)' }}>
                              <span style={{ flex: 1.05 }}>Requirement</span><span style={{ flex: 1.1 }}>Résumé match</span><span style={{ flex: '0 0 34px', textAlign: 'center' }}>Status</span>
                            </div>
                            {reqRows.filter((r) => reqFilter === 'all' || !r.matched).map((r, k) => (
                              <div key={k} style={{ display: 'flex', gap: 14, padding: '8px 0', borderBottom: '1px solid var(--line-soft)', fontSize: 12, lineHeight: 1.45 }}>
                                <span style={{ flex: 1.05, minWidth: 0 }}>{r.requirement}</span>
                                <span style={{ flex: 1.1, minWidth: 0, color: 'var(--muted)' }}>{r.cv_evidence || '—'}</span>
                                <span style={{ flex: '0 0 34px', textAlign: 'center', color: r.matched ? 'var(--good)' : 'var(--bad)' }}>{r.matched ? '✓' : '✕'}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {(rpt?.hard_blockers || []).length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '11px 13px', border: '1px solid var(--bad)', borderRadius: 8 }}>
                            <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--bad)', fontWeight: 600 }}>Hard blockers</span>
                            {(rpt.hard_blockers || []).map((b, k) => <div key={k} style={{ display: 'flex', gap: 9, fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--bad)' }}>!</span><span>{b}</span></div>)}
                          </div>
                        )}
                        {rpt?.ats_tip && (
                          <div style={{ display: 'flex', gap: 11, padding: '12px 14px', border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface-2)' }}>
                            <span style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)', paddingTop: 2 }}>ATS tip</span>
                            <span style={{ flex: 1, fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)' }}>{rpt.ats_tip}</span>
                          </div>
                        )}
                        {(d.fit_gaps || []).length > 0 && !reqRows.length && <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{(d.fit_gaps || []).map((g, k) => <div key={k} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--bad)' }}>✕</span><span>{g}</span></div>)}</div>}
                        {!rpt && !(d.fit_gaps || []).length && !(d.fit_strengths || []).length && <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>This report was quick-scored — rescore at full depth for the keyword and requirement breakdown.</span>}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* posting area (hidden when report is open) */}
              {!reportOpen && (
                <div style={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }} className="v2-scroll">
                  {!dScored && !running && (
                    <div style={{ flex: '0 0 auto', margin: '18px 30px 4px', display: 'flex', alignItems: 'center', gap: 20, padding: '16px 18px', border: '1px dashed var(--line)', borderRadius: 10 }}>
                      <div style={{ width: 74, height: 74, flex: '0 0 74px', border: '1px dashed var(--line)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>No fit</div>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.015em' }}>Not scored yet</span>
                        <span style={{ fontSize: 13, color: 'var(--text-2)', maxWidth: '54ch' }}>Score this role against your résumés to see the fit breakdown, requirement mapping and missing keywords.</span>
                      </div>
                      <div onClick={() => scoreJob(d)} style={{ flex: '0 0 auto', height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>Score this role</div>
                    </div>
                  )}
                  {running && (
                    <div style={{ flex: '0 0 auto', margin: '18px 30px 4px', display: 'flex', alignItems: 'center', gap: 20, padding: '16px 18px', border: '1px solid var(--accent)', borderRadius: 10, background: 'var(--accent-soft)' }}>
                      <div style={{ position: 'relative', width: 74, height: 74, flex: '0 0 74px' }}><div className="v2-spin" style={{ position: 'absolute', inset: 0, border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /></div>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.015em' }}>Scoring in progress</span>
                        <span style={{ fontSize: 13, color: 'var(--text-2)' }}>This continues in the background if you navigate away.</span>
                      </div>
                    </div>
                  )}
                  {/* live / cached posting */}
                  <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: '16px 30px 0' }}>
                    {dCached && (
                      <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12, padding: '7px 11px', border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface-2)' }}>
                        <span style={{ fontSize: 12, color: viewCached ? 'var(--accent)' : 'var(--muted)' }}>{viewCached ? 'Cached snapshot · captured when you applied' : 'Live posting'}</span>
                        <div style={{ marginLeft: 'auto', display: 'flex', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 99, padding: 2, gap: 2 }}>
                          <div onClick={() => setViewCached(false)} style={{ height: 22, padding: '0 10px', borderRadius: 99, fontSize: 11, display: 'flex', alignItems: 'center', cursor: 'pointer', background: !viewCached ? 'var(--surface-2)' : 'transparent', color: !viewCached ? 'var(--text)' : 'var(--muted)' }}>Live</div>
                          <div onClick={() => setViewCached(true)} style={{ height: 22, padding: '0 10px', borderRadius: 99, fontSize: 11, display: 'flex', alignItems: 'center', cursor: 'pointer', background: viewCached ? 'var(--accent-soft)' : 'transparent', color: viewCached ? 'var(--accent)' : 'var(--muted)' }}>Cached</div>
                        </div>
                      </div>
                    )}
                    {viewCached && dCached ? (
                      <iframe title="cached" srcDoc={cachedHtml || '<p style="padding:16px;font-family:sans-serif">Loading cached snapshot…</p>'} sandbox="allow-same-origin" style={{ flex: 1, width: '100%', border: '1px solid var(--line)', borderRadius: 10, background: '#fff', marginBottom: 20 }} />
                    ) : d.url ? (
                      <iframe title="posting" src={d.url} sandbox="allow-scripts allow-same-origin allow-popups allow-forms" style={{ flex: 1, width: '100%', border: '1px solid var(--line)', borderRadius: 10, background: '#fff', marginBottom: 20 }} />
                    ) : (
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>No posting URL captured for this job.</div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {/* cv modal */}
      {picker && (
        <div onClick={() => setPicker(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(27,26,22,.32)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 380, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--line)', boxShadow: '0 20px 50px rgba(0,0,0,.28)', padding: 18 }}>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 17, marginBottom: 4 }}>{picker.mode === 'tailor' ? '✦ Tailor a résumé' : '⧉ Copy a résumé'}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12 }}>{picker.jobs.length === 1 ? `for ${picker.jobs[0].title}` : `for ${picker.jobs.length} selected roles`} · pick a base</div>
            <div className="v2-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 260, overflow: 'auto' }}>
              {resumes.length === 0 ? <span style={{ fontSize: 12, color: 'var(--muted)' }}>No base résumés found.</span>
                : resumes.map((r) => <div key={r.id} className="v2-menuitem" onClick={() => runResume(picker.mode, picker.jobs, r.id)} style={{ padding: '9px 11px', borderRadius: 8, border: '1px solid var(--line)', fontSize: 13, cursor: 'pointer' }}>{r.name}</div>)}
            </div>
            <div onClick={() => setPicker(null)} style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>Cancel</div>
          </div>
        </div>
      )}
    </div>
  )
}
