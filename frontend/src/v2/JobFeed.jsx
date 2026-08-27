import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import api from '../api'

// ── helpers ──────────────────────────────────────────────────────────────
const RING_C = 2 * Math.PI * 35
const timeAgo = (s) => {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
const isToday = (s) => s && (Date.now() - new Date(s).getTime()) < 86400000
const scoreColor = (s) => (s >= 80 ? 'var(--accent)' : s >= 65 ? 'var(--stone)' : 'var(--warn)')
const bestScore = (j) => {
  if (typeof j.best_score === 'number' && j.best_score > 0) return j.best_score
  const v = Object.values(j.cv_scores || {}).filter((x) => typeof x === 'number')
  return v.length ? Math.max(...v) : 0
}
const scoredCount = (j) => Object.values(j.cv_scores || {}).filter((x) => typeof x === 'number').length
const isTailored = (j) => Object.keys(j.cv_scores || {}).includes('Tailored') || j.best_cv === 'Tailored'
const fmtSalary = (min, max) => {
  if (!min && !max) return null
  const f = (v) => `$${Math.round(v / 1000)}K`
  return min && max && min !== max ? `${f(min)} - ${f(max)}` : f(min || max)
}
const H1B = {
  likely: { label: 'H-1B Likely', c: 'var(--accent)' },
  possible: { label: 'H-1B Possible', c: 'var(--warn)' },
  unlikely: { label: 'H-1B Unlikely', c: 'var(--danger)' },
  unknown: { label: 'H-1B Unknown', c: 'var(--muted)' },
}
const STATUS_BADGE = {
  applied: { label: 'APPLIED', bg: 'var(--accent-bg)', fg: 'var(--accent)' },
  saved: { label: 'SAVED', bg: 'var(--warn-bg)', fg: 'var(--warn)' },
  skip: { label: 'SKIPPED', bg: 'var(--panel)', fg: 'var(--muted)' },
  ignored: { label: 'IGNORED', bg: 'var(--panel)', fg: 'var(--faint)' },
}
const SOURCE_LABELS = {
  direct: 'Direct', extension: 'Extension', jobspy_linkedin: 'LinkedIn', jobspy_indeed: 'Indeed',
  jobspy_zip_recruiter: 'ZipRecruiter', jobspy_google: 'Google', levels_fyi: 'Levels', linkedin_personal: 'LinkedIn Personal',
  linkedin_extension: 'LinkedIn', jobright: 'Jobright', freehire: 'FreeHire', playwright_url: 'Career page', playwright_direct: 'Career page',
}
const STATUS_OPTS = [['new', 'New'], ['saved', 'Saved'], ['applied', 'Applied'], ['skip', 'Skip'], ['ignored', 'Ignored']]
const SORT_OPTS = [['score', 'Top Score'], ['date', 'Newest'], ['salary', 'Top Salary'], ['company', 'Company A–Z']]

// ── dropdown pill ──────────────────────────────────────────────────────────
function Pill({ label, summary, active, open, onToggle, onClear, children, width = 220 }) {
  return (
    <div style={{ position: 'relative' }}>
      <div className="v2-pill" onClick={onToggle}
        style={{ height: 28, padding: '0 10px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
          border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
          background: active ? 'var(--accent-bg)' : 'var(--surface)',
          color: active ? 'var(--accent)' : 'var(--stone)' }}>
        <span>{summary || label}</span>
        {active && onClear
          ? <span onClick={(e) => { e.stopPropagation(); onClear() }} style={{ fontSize: 12, opacity: 0.7 }}>✕</span>
          : <span style={{ fontSize: 9, opacity: 0.6 }}>▾</span>}
      </div>
      {open && (
        <>
          <div onClick={onToggle} style={{ position: 'fixed', inset: 0, zIndex: 30 }} />
          <div className="v2-scroll" style={{ position: 'absolute', top: 'calc(100% + 5px)', left: 0, zIndex: 31, width, maxHeight: 320, overflow: 'auto',
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, boxShadow: '0 14px 40px rgba(0,0,0,.16)', padding: 8 }}>
            {children}
          </div>
        </>
      )}
    </div>
  )
}
function CheckRow({ on, label, onClick }) {
  return (
    <div className="v2-navlink" onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer' }}>
      <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: `1px solid ${on ? 'var(--accent)' : 'var(--faint)'}`, background: on ? 'var(--accent)' : 'transparent', color: '#fff', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{on ? '✓' : ''}</span>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  )
}

const DEFAULT_FILTERS = { status: ['new', 'saved', 'applied'], company: [], source: [], h1b_verdict: [], min_score: '', min_salary: '', max_salary: '' }

// ── component ────────────────────────────────────────────────────────────
export default function V2JobFeed() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [sortBy, setSortBy] = useState('score')
  const [search, setSearch] = useState('')
  const [dSearch, setDSearch] = useState('')
  const [menu, setMenu] = useState(null)   // open dropdown key

  const [sel, setSel] = useState(0)
  const [detail, setDetail] = useState(null)
  const [reportOpen, setReportOpen] = useState(true)

  const [companyList, setCompanyList] = useState([])
  const [sourceList, setSourceList] = useState([])
  const [verdictList, setVerdictList] = useState([])
  const [resumes, setResumes] = useState([])
  const [picker, setPicker] = useState(null)      // {mode, job}
  const [rowMenu, setRowMenu] = useState(null)    // job id whose ⋯ menu is open

  const listRef = useRef(null)
  const jobsRef = useRef(jobs); useEffect(() => { jobsRef.current = jobs }, [jobs])
  const selRef = useRef(sel); useEffect(() => { selRef.current = sel }, [sel])

  useEffect(() => { const t = setTimeout(() => setDSearch(search), 400); return () => clearTimeout(t) }, [search])
  useEffect(() => {
    api.get('/jobs/companies/list').then(({ data }) => setCompanyList(data || [])).catch(() => {})
    api.get('/jobs/sources/list').then(({ data }) => setSourceList(data || [])).catch(() => {})
    api.get('/jobs/verdicts/list').then(({ data }) => setVerdictList(data || [])).catch(() => {})
    api.get('/resumes?is_base=true').then(({ data }) => setResumes(data || [])).catch(() => {})
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
    setSel(idx)
    const j = list[idx]
    setDetail(j)
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
    setJobs((prev) => leaves
      ? (setTotal((t) => Math.max(0, t - 1)), prev.filter((j) => j.id !== id))
      : prev.map((j) => (j.id === id ? { ...j, ...changes } : j)))
    setDetail((d) => (d && d.id === id ? { ...d, ...changes } : d))
  }, [filters.status])

  const patchRemote = useCallback(async (job, changes) => {
    patchLocal(job.id, changes)
    try { await api.patch(`/jobs/${job.id}`, changes) } catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])

  const saveJob = (j) => patchRemote(j, { saved: !j.saved, status: j.saved ? 'new' : 'saved' })
  const skipJob = (j) => patchRemote(j, { status: 'skip' })
  const applyJob = (j) => patchRemote(j, { status: 'applied' })
  const ignoreJob = (j) => patchRemote(j, { status: 'ignored' })

  const runResume = useCallback(async (mode, job, baseId) => {
    setPicker(null)
    try {
      if (mode === 'copy') {
        const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: job.id })
        window.location.href = `/resumes?resume=${data.id}`
      } else {
        await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: job.id })
        setJobs((prev) => prev.map((j) => j.id === job.id ? { ...j, in_flight: [...new Set([...(j.in_flight || []), 'tailor_resume'])] } : j))
      }
    } catch (e) { alert(`${mode} failed: ${e.response?.data?.detail || e.message}`) }
  }, [])

  const openTailored = useCallback(async (job) => {
    // find an existing tailored copy for this job, else offer to tailor
    try {
      const { data } = await api.get('/resumes')
      const copy = (data || []).find((r) => !r.is_base && r.job_id === job.id)
      if (copy) { window.location.href = `/resumes?resume=${copy.id}`; return }
    } catch {/* fall through */}
    setPicker({ mode: 'tailor', job })
  }, [])

  const scoreJob = useCallback((job) => {
    api.post(`/analyze/${job.id}?depth=full`, { }).then(() => {
      setJobs((prev) => prev.map((j) => j.id === job.id ? { ...j, in_flight: [...new Set([...(j.in_flight || []), 'analyze_job'])] } : j))
    }).catch((e) => console.error(e))
  }, [])

  const unscored = useMemo(() => jobs.filter((j) => scoredCount(j) === 0 && ['new', 'saved'].includes(j.status)), [jobs])
  const scoreAllUnscored = () => unscored.slice(0, 50).forEach(scoreJob)

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
        case 'o': case 'e': if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer'); break
        case 'r': setReportOpen((v) => !v); break
        default: break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAt])
  useEffect(() => { const el = listRef.current?.querySelector(`[data-row="${sel}"]`); if (el) el.scrollIntoView({ block: 'nearest' }) }, [sel])

  const setF = (patch) => { setFilters((f) => ({ ...f, ...patch })); setSel(0) }
  const toggleIn = (key, val) => setF({ [key]: filters[key].includes(val) ? filters[key].filter((x) => x !== val) : [...filters[key], val] })
  const activeCount = filters.company.length + filters.source.length + filters.h1b_verdict.length + (filters.min_score !== '' ? 1 : 0) + (filters.min_salary || filters.max_salary ? 1 : 0)

  const d = detail
  const arrivedToday = jobs.filter((j) => isToday(j.discovered_at)).length

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)', color: 'var(--ink)' }}>
      {/* header */}
      <div style={{ flex: '0 0 auto', padding: '16px 24px 0' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 26, fontWeight: 500, letterSpacing: '-.02em' }}>The Feed</h1>
            <div style={{ marginTop: 2, fontSize: 12, color: 'var(--muted)' }}>
              {total} matching · {jobs.length} shown{arrivedToday ? ` · ${arrivedToday} arrived today` : ''}{unscored.length ? ` · ${unscored.length} not yet scored` : ''}
            </div>
          </div>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search titles…"
            style={{ width: 220, height: 34, padding: '0 12px', borderRadius: 99, border: '1px solid var(--border)', background: 'var(--surface)', fontSize: 13, fontFamily: 'var(--sans)', color: 'var(--ink)', outline: 'none' }} />
          {unscored.length > 0 && (
            <button onClick={scoreAllUnscored} className="v2-pill"
              style={{ height: 34, padding: '0 14px', borderRadius: 99, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>
              Score {unscored.length} unscored
            </button>
          )}
        </div>

        {/* filter bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 0 10px', flexWrap: 'wrap' }}>
          <Pill label="Source" active={filters.source.length > 0} open={menu === 'source'} onToggle={() => setMenu(menu === 'source' ? null : 'source')}
            summary={filters.source.length ? `Source · ${filters.source.length}` : null} onClear={() => setF({ source: [] })}>
            {sourceList.map((s) => <CheckRow key={s} on={filters.source.includes(s)} label={SOURCE_LABELS[s] || s} onClick={() => toggleIn('source', s)} />)}
            {sourceList.length === 0 && <div style={{ padding: 8, fontSize: 12, color: 'var(--muted)' }}>None</div>}
          </Pill>
          <Pill label="Company" active={filters.company.length > 0} open={menu === 'company'} onToggle={() => setMenu(menu === 'company' ? null : 'company')}
            summary={filters.company.length ? `Company · ${filters.company.length}` : null} onClear={() => setF({ company: [] })} width={260}>
            {companyList.map((c) => <CheckRow key={c} on={filters.company.includes(c)} label={c} onClick={() => toggleIn('company', c)} />)}
            {companyList.length === 0 && <div style={{ padding: 8, fontSize: 12, color: 'var(--muted)' }}>None</div>}
          </Pill>
          <Pill label="H-1B" active={filters.h1b_verdict.length > 0} open={menu === 'h1b'} onToggle={() => setMenu(menu === 'h1b' ? null : 'h1b')}
            summary={filters.h1b_verdict.length ? `H-1B · ${filters.h1b_verdict.length}` : null} onClear={() => setF({ h1b_verdict: [] })} width={180}>
            {['likely', 'possible', 'unlikely', 'unknown'].filter((v) => verdictList.includes(v)).map((v) => <CheckRow key={v} on={filters.h1b_verdict.includes(v)} label={H1B[v].label} onClick={() => toggleIn('h1b_verdict', v)} />)}
          </Pill>
          <Pill label="Score ≥" active={filters.min_score !== ''} open={menu === 'score'} onToggle={() => setMenu(menu === 'score' ? null : 'score')}
            summary={filters.min_score !== '' ? `Score ≥ ${filters.min_score}` : null} onClear={() => setF({ min_score: '' })} width={160}>
            <input type="number" placeholder="Minimum score" value={filters.min_score} onChange={(e) => setF({ min_score: e.target.value })}
              style={{ width: '100%', height: 30, padding: '0 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12.5, background: 'var(--surface)', color: 'var(--ink)' }} />
          </Pill>
          <Pill label="Salary" active={!!(filters.min_salary || filters.max_salary)} open={menu === 'salary'} onToggle={() => setMenu(menu === 'salary' ? null : 'salary')}
            summary={(filters.min_salary || filters.max_salary) ? `Salary · ${filters.min_salary || '0'}–${filters.max_salary || '∞'}K` : null} onClear={() => setF({ min_salary: '', max_salary: '' })} width={200}>
            <div style={{ display: 'flex', gap: 6 }}>
              <input type="number" placeholder="Min $K" value={filters.min_salary} onChange={(e) => setF({ min_salary: e.target.value })} style={{ width: '50%', height: 30, padding: '0 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12.5, background: 'var(--surface)', color: 'var(--ink)' }} />
              <input type="number" placeholder="Max $K" value={filters.max_salary} onChange={(e) => setF({ max_salary: e.target.value })} style={{ width: '50%', height: 30, padding: '0 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12.5, background: 'var(--surface)', color: 'var(--ink)' }} />
            </div>
          </Pill>
          <Pill label="Status" active={filters.status.length > 0 && filters.status.length < STATUS_OPTS.length} open={menu === 'status'} onToggle={() => setMenu(menu === 'status' ? null : 'status')}
            summary={`Status · ${filters.status.map((s) => STATUS_OPTS.find((o) => o[0] === s)?.[1]).join(', ') || 'Any'}`} onClear={() => setF({ status: [] })} width={170}>
            {STATUS_OPTS.map(([v, label]) => <CheckRow key={v} on={filters.status.includes(v)} label={label} onClick={() => toggleIn('status', v)} />)}
          </Pill>
          {activeCount > 0 && <span onClick={() => setFilters(DEFAULT_FILTERS)} style={{ fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer' }}>reset</span>}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Sort</span>
            <Pill label={SORT_OPTS.find((o) => o[0] === sortBy)?.[1]} open={menu === 'sort'} onToggle={() => setMenu(menu === 'sort' ? null : 'sort')} width={160}>
              {SORT_OPTS.map(([v, label]) => <CheckRow key={v} on={sortBy === v} label={label} onClick={() => { setSortBy(v); setMenu(null); setSel(0) }} />)}
            </Pill>
          </div>
        </div>
      </div>

      {/* body: list + detail */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, borderTop: '1px solid var(--border)' }}>
        {/* list */}
        <div style={{ width: 452, flex: '0 0 452px', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ flex: '0 0 auto', padding: '7px 16px', display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--border-lt)' }}>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{jobs.length} shown · {total} matching</span>
            <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--faint)' }}>j k · s save · x skip</span>
          </div>
          <div ref={listRef} className="v2-scroll" style={{ flex: 1, overflow: 'auto' }}>
            {loading ? <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
              : jobs.length === 0 ? <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No jobs match.</div>
              : jobs.map((j, i) => {
                const score = bestScore(j); const nsc = scoredCount(j)
                const badge = STATUS_BADGE[j.status]
                const running = (j.in_flight || []).length > 0
                const dim = j.status === 'ignored' || j.status === 'skip'
                return (
                  <div key={j.id} data-row={i} className="v2-row" onClick={() => focusAt(i)}
                    style={{ display: 'flex', gap: 11, padding: '11px 12px 11px 14px', borderBottom: '1px solid var(--border-lt)',
                      background: i === sel ? 'var(--panel)' : 'transparent',
                      backgroundImage: dim ? 'repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(0,0,0,.02) 6px, rgba(0,0,0,.02) 7px)' : 'none',
                      opacity: dim ? 0.6 : 1 }}>
                    {/* ring */}
                    <div style={{ position: 'relative', width: 38, height: 38, flex: '0 0 38px', marginTop: 1 }}>
                      <svg viewBox="0 0 78 78" style={{ width: 38, height: 38, transform: 'rotate(-90deg)' }}>
                        <circle cx="39" cy="39" r="35" fill="none" stroke="var(--border-lt)" strokeWidth="5" />
                        {nsc > 0 && <circle cx="39" cy="39" r="35" fill="none" stroke={scoreColor(score)} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(RING_C * score / 100).toFixed(1)} ${RING_C}`} />}
                      </svg>
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: nsc > 0 ? 14 : 8, color: nsc > 0 ? scoreColor(score) : 'var(--faint)', letterSpacing: nsc > 0 ? 0 : '.06em' }}>
                        {running ? <span className="v2-spin" style={{ width: 11, height: 11, borderRadius: 99, border: '2px solid var(--faint)', borderTopColor: 'var(--accent)' }} /> : (nsc > 0 ? score : 'SCORE')}
                      </div>
                      {nsc > 0 && <span style={{ position: 'absolute', right: -3, bottom: -2, fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--muted)', background: i === sel ? 'var(--panel)' : 'var(--bg)', borderRadius: 6, padding: '0 1px' }}>{nsc}</span>}
                    </div>
                    {/* body */}
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span title={j.title} style={{ flex: 1, minWidth: 0, fontFamily: 'var(--serif)', fontSize: 14.5, fontWeight: 500, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</span>
                        {isTailored(j) && <span style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--accent)' }}>✦</span>}
                        {badge && <span style={{ flex: '0 0 auto', fontSize: 8.5, letterSpacing: '.08em', padding: '2px 6px', borderRadius: 99, background: badge.bg, color: badge.fg, fontWeight: 600 }}>{badge.label}</span>}
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {j.company}{j.location ? `  |  ${j.location}` : ''}
                      </span>
                      <span style={{ fontSize: 10.5, color: 'var(--faint)', display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span>{fmtSalary(j.salary_min, j.salary_max) || 'Salary not listed'}</span>
                        {j.h1b_verdict && <span style={{ color: (H1B[j.h1b_verdict] || H1B.unknown).c }}>{(H1B[j.h1b_verdict] || H1B.unknown).label}</span>}
                        <span>{timeAgo(j.discovered_at)}</span>
                      </span>
                    </div>
                    {/* action stack */}
                    <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 2, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                      <div className="v2-rail-save v2-rail-cell" title="Save (s)" onClick={() => saveJob(j)} style={{ width: 20, height: 20, borderRadius: 5, color: j.saved ? 'var(--accent)' : 'var(--muted)' }}>♥</div>
                      <div className="v2-rail-skip v2-rail-cell" title="Skip (x)" onClick={() => skipJob(j)} style={{ width: 20, height: 20, borderRadius: 5 }}>✕</div>
                      <div className="v2-rail-copy v2-rail-cell" title="More" onClick={() => setRowMenu(rowMenu === j.id ? null : j.id)} style={{ width: 20, height: 20, borderRadius: 5 }}>⋯</div>
                      {rowMenu === j.id && (
                        <>
                          <div onClick={() => setRowMenu(null)} style={{ position: 'fixed', inset: 0, zIndex: 30 }} />
                          <div style={{ position: 'absolute', right: 24, top: 0, zIndex: 31, width: 150, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, boxShadow: '0 12px 30px rgba(0,0,0,.16)', padding: 5 }}>
                            {[['Apply', () => applyJob(j)], ['Tailor…', () => setPicker({ mode: 'tailor', job: j })], ['Copy…', () => setPicker({ mode: 'copy', job: j })], ['Score', () => scoreJob(j)], ['Ignore', () => ignoreJob(j)]].map(([label, act]) => (
                              <div key={label} className="v2-navlink" onClick={() => { setRowMenu(null); act() }} style={{ padding: '6px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer' }}>{label}</div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
        </div>

        {/* detail */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)' }}>
          {!d ? <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Select a job.</div> : (
            <>
              <div style={{ flex: '0 0 auto', padding: '16px 26px 0' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 5 }}>
                      {[j_company(d), SOURCE_LABELS[d.source] || d.source, timeAgo(d.discovered_at)].filter(Boolean).join(' · ')}
                    </div>
                    <h2 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 22, fontWeight: 500, letterSpacing: '-.02em' }}>{d.title}</h2>
                    <div style={{ marginTop: 5, fontSize: 12.5, color: 'var(--stone)' }}>
                      {[fmtSalary(d.salary_min, d.salary_max), d.location, d.h1b_verdict && (H1B[d.h1b_verdict] || H1B.unknown).label].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <div style={{ flex: '0 0 auto', display: 'flex', gap: 7 }}>
                    {d.url && <a href={d.url} target="_blank" rel="noopener noreferrer" className="v2-pill" style={{ height: 30, padding: '0 12px', borderRadius: 99, border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--stone)' }}>Open ↗</a>}
                    <div onClick={() => openTailored(d)} className="v2-pill" style={{ height: 30, padding: '0 12px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, cursor: 'pointer' }}>✦ Open tailored ↗</div>
                  </div>
                </div>

                {/* report band */}
                <div style={{ marginTop: 14, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                  <div onClick={() => setReportOpen((v) => !v)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 14px', background: 'var(--panel)', cursor: 'pointer' }}>
                    <span style={{ fontFamily: 'var(--serif)', fontSize: 20, color: scoreColor(bestScore(d)) }}>{bestScore(d) || '–'}</span>
                    {d.best_cv && <span style={{ fontSize: 12, color: 'var(--stone)' }}>✦ {d.best_cv}</span>}
                    {d.apply_recommendation && <span style={{ fontSize: 12, color: 'var(--accent)' }}>{d.apply_recommendation}</span>}
                    {(d.fit_gaps || []).length > 0 && <span style={{ fontSize: 12, color: 'var(--muted)' }}>{d.fit_gaps.length} gap{d.fit_gaps.length === 1 ? '' : 's'}</span>}
                    <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--muted)' }}>{Object.keys(d.cv_scores || {}).length} report{Object.keys(d.cv_scores || {}).length === 1 ? '' : 's'} {reportOpen ? '▲' : '▾'}</span>
                  </div>
                  {reportOpen && (
                    <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {Object.entries(d.cv_scores || {}).filter(([, v]) => typeof v === 'number').length > 0 && (
                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                          {Object.entries(d.cv_scores).filter(([, v]) => typeof v === 'number').sort((a, b) => b[1] - a[1]).map(([name, sc], k) => (
                            <span key={name} style={{ display: 'flex', alignItems: 'center', gap: 5, height: 24, padding: '0 9px', borderRadius: 99, fontSize: 11, border: `1px solid ${k === 0 ? 'var(--accent)' : 'var(--border)'}`, background: k === 0 ? 'var(--accent-bg)' : 'var(--surface)', color: k === 0 ? 'var(--accent)' : 'var(--stone)' }}>
                              {name === 'Tailored' && <span style={{ fontSize: 8 }}>✦</span>}{name} <b style={{ fontFamily: 'var(--mono)', fontWeight: 500 }}>{sc}</b>
                            </span>
                          ))}
                        </div>
                      )}
                      {(d.fit_strengths || []).map((s, k) => (
                        <div key={`s${k}`} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--stone)' }}><span style={{ color: 'var(--accent)' }}>✓</span><span>{s}</span></div>
                      ))}
                      {(d.fit_gaps || []).map((g, k) => (
                        <div key={`g${k}`} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--stone)' }}><span style={{ color: 'var(--danger)' }}>✕</span><span>{g}</span></div>
                      ))}
                      {!Object.keys(d.cv_scores || {}).length && <span style={{ fontSize: 12, color: 'var(--muted)' }}>Not scored yet. Use the ⋯ menu → Score, or the header button.</span>}
                    </div>
                  )}
                </div>
              </div>

              {/* description */}
              <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '18px 26px 30px', minHeight: 0 }}>
                <div style={{ maxWidth: '74ch', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <h3 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 16, fontWeight: 500, letterSpacing: '-.015em' }}>About the role</h3>
                  <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.62, color: 'var(--stone)', whiteSpace: 'pre-wrap' }}>{d.description || 'No description captured for this job.'}</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* tailor / copy picker */}
      {picker && (
        <div onClick={() => setPicker(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(27,26,22,.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 360, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)', boxShadow: '0 20px 50px rgba(0,0,0,.22)', padding: 18 }}>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 17, marginBottom: 4 }}>{picker.mode === 'tailor' ? '✦ Tailor a résumé' : '⧉ Copy a résumé'}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12 }}>for {picker.job.title}</div>
            <div className="v2-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 260, overflow: 'auto' }}>
              {resumes.length === 0 ? <span style={{ fontSize: 12, color: 'var(--muted)' }}>No base résumés found.</span>
                : resumes.map((r) => <div key={r.id} className="v2-navlink" onClick={() => runResume(picker.mode, picker.job, r.id)} style={{ padding: '9px 11px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, cursor: 'pointer' }}>{r.name}</div>)}
            </div>
            <div className="v2-pill" onClick={() => setPicker(null)} style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>Cancel</div>
          </div>
        </div>
      )}
    </div>
  )
}

function j_company(d) { return d.company || '' }
