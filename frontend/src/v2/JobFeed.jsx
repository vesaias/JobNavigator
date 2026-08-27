import React, { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'

// ── helpers ──────────────────────────────────────────────────────────────
const RING_C = 2 * Math.PI * 35   // score-ring circumference

const timeAgo = (s) => {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
const ringColor = (s) => (s >= 80 ? 'var(--accent)' : s >= 65 ? 'var(--stone)' : 'var(--warn)')
const bestScore = (j) => {
  if (typeof j.best_score === 'number' && j.best_score > 0) return j.best_score
  const v = Object.values(j.cv_scores || {}).filter((x) => typeof x === 'number')
  return v.length ? Math.max(...v) : 0
}
const isTailored = (j) => Object.keys(j.cv_scores || {}).includes('Tailored') || j.best_cv === 'Tailored'
const EDGE = { saved: 'var(--warn)', applied: 'var(--accent)' }
const H1B_LABEL = { likely: 'H-1B likely', possible: 'H-1B possible', unlikely: 'H-1B unlikely' }
const fmtSalary = (min, max) => {
  if (!min && !max) return null
  const f = (v) => `$${Math.round(v / 1000)}K`
  return min && max && min !== max ? `${f(min)} - ${f(max)}` : f(min || max)
}
const STATUS_OPTS = [
  { v: 'new', label: 'New' }, { v: 'saved', label: 'Saved' },
  { v: 'applied', label: 'Applied' }, { v: 'skip', label: 'Skip' },
]
const SORT_OPTS = [
  { v: 'score', label: 'fit ↓' }, { v: 'date', label: 'newest' },
  { v: 'salary', label: 'salary ↓' }, { v: 'company', label: 'A–Z' },
]

// ── component ────────────────────────────────────────────────────────────
export default function V2JobFeed() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(['new'])
  const [sortBy, setSortBy] = useState('score')

  const [sel, setSel] = useState(0)
  const [detail, setDetail] = useState(null)   // full focused job (hydrated)
  const [drawer, setDrawer] = useState(false)

  const [selectMode, setSelectMode] = useState(false)
  const [checked, setChecked] = useState(() => new Set())

  const [resumes, setResumes] = useState([])    // base resumes for tailor/copy
  const [picker, setPicker] = useState(null)    // 'tailor' | 'copy' | null

  const listRef = useRef(null)
  const jobsRef = useRef(jobs); useEffect(() => { jobsRef.current = jobs }, [jobs])
  const selRef = useRef(sel); useEffect(() => { selRef.current = sel }, [sel])

  // fetch base resumes once (for the Tailor / Copy pickers)
  useEffect(() => {
    api.get('/resumes?is_base=true').then(({ data }) => setResumes(data || [])).catch(() => {})
  }, [])

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 60, offset: 0 }
      if (status.length) params.status = status.join(',')
      if (sortBy !== 'date') params.sort_by = sortBy
      const { data } = await api.get('/jobs', { params })
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
    } catch (e) { console.error('v2 feed load failed', e) }
    setLoading(false)
  }, [status, sortBy])
  useEffect(() => { fetchJobs() }, [fetchJobs])

  // keep focus valid + hydrate the focused job's full detail
  const focusAt = useCallback((idx) => {
    const list = jobsRef.current
    if (idx < 0 || idx >= list.length) return
    setSel(idx)
    const j = list[idx]
    setDetail(j)                                    // instant from list
    api.get(`/jobs/${j.id}`).then(({ data }) => {   // then hydrate
      setDetail((cur) => (cur && cur.id === data.id ? data : cur))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (loading) return
    if (jobs.length === 0) { setDetail(null); return }
    const idx = Math.min(sel, jobs.length - 1)
    focusAt(idx)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, loading])

  // patch one job locally; drop it if its new status leaves the active filter
  const patchLocal = useCallback((id, changes) => {
    const leaves = status.length && changes.status && !status.includes(changes.status)
    setJobs((prev) => {
      if (leaves) {
        const next = prev.filter((j) => j.id !== id)
        setTotal((t) => Math.max(0, t - 1))
        return next
      }
      return prev.map((j) => (j.id === id ? { ...j, ...changes } : j))
    })
  }, [status])

  const saveJob = useCallback(async (job) => {
    const willSave = !job.saved
    const newStatus = willSave ? 'saved' : 'new'
    patchLocal(job.id, { saved: willSave, status: newStatus })
    try { await api.patch(`/jobs/${job.id}`, { saved: willSave, status: newStatus }) }
    catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])

  const skipJob = useCallback(async (job) => {
    patchLocal(job.id, { status: 'skip' })
    try { await api.patch(`/jobs/${job.id}`, { status: 'skip' }) }
    catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])

  const applyJob = useCallback(async (job) => {
    patchLocal(job.id, { status: 'applied' })
    try { await api.patch(`/jobs/${job.id}`, { status: 'applied' }) }
    catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])

  // tailor / copy against a chosen base résumé
  const runResume = useCallback(async (mode, baseId) => {
    const job = detail || jobsRef.current[selRef.current]
    setPicker(null)
    if (!job) return
    try {
      if (mode === 'copy') {
        const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: job.id })
        window.location.href = `/resumes?resume=${data.id}`
      } else {
        await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: job.id })
        setJobs((prev) => prev.map((j) => j.id === job.id
          ? { ...j, in_flight: [...new Set([...(j.in_flight || []), 'tailor_resume'])] } : j))
      }
    } catch (e) { alert(`${mode} failed: ${e.response?.data?.detail || e.message}`) }
  }, [detail])

  // bulk
  const toggleCheck = useCallback((id) => setChecked((prev) => {
    const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n
  }), [])
  const bulk = useCallback(async (action) => {
    if (checked.size === 0) return
    const ids = [...checked]
    const updates = action === 'skip' ? { status: 'skip' } : { saved: true, status: 'saved' }
    try {
      await api.post('/jobs/bulk-update', { job_ids: ids, updates })
      setChecked(new Set()); setSelectMode(false); fetchJobs()
    } catch (e) { console.error(e) }
  }, [checked, fetchJobs])

  // keyboard
  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      const list = jobsRef.current, idx = selRef.current
      const job = list[idx]
      switch (e.key) {
        case 'j': case 'ArrowDown': e.preventDefault(); focusAt(Math.min(idx + 1, list.length - 1)); break
        case 'k': case 'ArrowUp': e.preventDefault(); focusAt(Math.max(idx - 1, 0)); break
        case 's': if (job) { saveJob(job); focusAt(Math.min(idx + 1, list.length - 1)) } break
        case 'x': if (job) { skipJob(job); focusAt(Math.min(idx, list.length - 2)) } break
        case 'o': case 'e': if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer'); break
        case 'r': setDrawer((d) => !d); break
        case 't': if (job) setPicker('tailor'); break
        default: break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [focusAt, saveJob, skipJob])

  // scroll focused row into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-row="${sel}"]`)
    if (el) el.scrollIntoView({ block: 'nearest' })
  }, [sel])

  const checkboxW = selectMode ? '34px' : '0px'
  const railW = selectMode ? '0px' : '25px'
  const d = detail

  // ── action column (acts on the focused job) ──
  const focusedJob = jobs[sel]
  const ACTIONS = [
    { icon: '♥', label: 'Save', on: focusedJob?.saved, act: () => focusedJob && saveJob(focusedJob) },
    { icon: '✕', label: 'Skip', warn: true, act: () => focusedJob && skipJob(focusedJob) },
    { icon: '✦', label: 'Tailor', primary: true, act: () => focusedJob && setPicker('tailor') },
    { icon: '▤', label: 'Report', onState: drawer, act: () => setDrawer((v) => !v) },
    { icon: '⧉', label: 'Copy', act: () => focusedJob && setPicker('copy') },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', minHeight: 0, background: 'var(--bg)', color: 'var(--ink)' }}>
      {/* ── LIST COLUMN ── */}
      <div style={{ width: 356, flex: '0 0 356px', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
        {/* header: select toggle + count + sort + shortcut hint */}
        <div style={{ flex: '0 0 auto', padding: '9px 14px', display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--border-lt)' }}>
          <div className="v2-pill" onClick={() => { setSelectMode((s) => !s); setChecked(new Set()) }}
            title={selectMode ? 'Leave select mode' : 'Select multiple'}
            style={{ height: 26, padding: '0 11px', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5,
              border: `1px solid ${selectMode ? 'var(--accent)' : 'var(--border)'}`,
              background: selectMode ? 'var(--accent)' : 'var(--surface)',
              color: selectMode ? '#fff' : 'var(--stone)' }}>
            {selectMode ? 'Done' : 'Select'}
          </div>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{total} shown</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
            style={{ fontSize: 11, color: 'var(--stone)', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'var(--sans)' }}>
            {SORT_OPTS.map((o) => <option key={o.v} value={o.v}>{o.label}</option>)}
          </select>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--faint)' }}>j k s x t r</span>
        </div>

        {/* status filter pills */}
        <div style={{ flex: '0 0 auto', padding: '7px 12px', display: 'flex', gap: 5, borderBottom: '1px solid var(--border-lt)' }}>
          {STATUS_OPTS.map((o) => {
            const on = status.includes(o.v)
            return (
              <div key={o.v} className="v2-pill"
                onClick={() => { setStatus((prev) => prev.includes(o.v) ? prev.filter((x) => x !== o.v) : [...prev, o.v]); setSel(0) }}
                style={{ height: 23, padding: '0 10px', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11,
                  border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`,
                  background: on ? 'var(--accent-bg)' : 'var(--surface)',
                  color: on ? 'var(--accent)' : 'var(--muted)' }}>{o.label}</div>
            )
          })}
        </div>

        {/* bulk bar — only while selecting with a non-empty selection */}
        {selectMode && checked.size > 0 && (
          <div style={{ flex: '0 0 auto', borderBottom: '1px solid var(--accent)', background: 'var(--accent-bg)', display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px' }}>
            <span style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 600 }}>{checked.size} selected</span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
              <div className="v2-pill" onClick={() => bulk('save')} style={{ height: 26, padding: '0 11px', borderRadius: 99, background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: 500 }}>Save all</div>
              <div className="v2-pill" onClick={() => bulk('skip')} style={{ height: 26, padding: '0 11px', borderRadius: 99, border: '1px solid var(--faint)', background: 'var(--surface)', color: 'var(--warn)', display: 'flex', alignItems: 'center', fontSize: 11.5 }}>Skip all</div>
            </div>
          </div>
        )}

        {/* rows */}
        <div ref={listRef} className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '5px 8px', display: 'flex', flexDirection: 'column', gap: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
          ) : jobs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13 }}>No jobs.</div>
          ) : jobs.map((j, i) => {
            const score = bestScore(j)
            const rc = ringColor(score)
            const on = checked.has(j.id)
            const running = (j.in_flight || []).length > 0
            return (
              <div key={j.id} data-row={i} className="v2-row" onClick={() => focusAt(i)}
                style={{ display: 'flex', alignItems: 'stretch', borderRadius: 8, background: i === sel ? 'var(--panel)' : 'transparent', borderLeft: `2px solid ${EDGE[j.status] || 'transparent'}` }}>
                {/* checkbox (select mode) */}
                <div onClick={(e) => { e.stopPropagation(); toggleCheck(j.id) }}
                  style={{ width: checkboxW, flex: `0 0 ${checkboxW}`, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'width .18s' }}>
                  <div style={{ width: 15, height: 15, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, color: '#fff',
                    border: `1px solid ${on ? 'var(--accent)' : 'var(--faint)'}`, background: on ? 'var(--accent)' : 'var(--surface)' }}>{on ? '✓' : ''}</div>
                </div>
                {/* score + title */}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 11, padding: '9px 4px 9px 10px' }}>
                  <div style={{ position: 'relative', width: 32, height: 32, flex: '0 0 32px' }}>
                    <svg viewBox="0 0 78 78" style={{ width: 32, height: 32, transform: 'rotate(-90deg)' }}>
                      <circle cx="39" cy="39" r="35" fill="none" stroke="var(--border-lt)" strokeWidth="6" />
                      <circle cx="39" cy="39" r="35" fill="none" stroke={rc} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${(RING_C * score / 100).toFixed(1)} ${RING_C}`} />
                    </svg>
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 12, color: rc }}>
                      {running ? <span className="v2-spin" style={{ width: 10, height: 10, borderRadius: 99, border: '2px solid var(--faint)', borderTopColor: rc }} /> : (score || '–')}
                    </div>
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      <span title={j.title} style={{ flex: '0 1 auto', minWidth: 0, fontFamily: 'var(--serif)', fontSize: 14.5, fontWeight: 500, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</span>
                      {isTailored(j) && <span style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--accent)' }}>✦</span>}
                    </div>
                    <span title={j.company} style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.company} · {timeAgo(j.discovered_at)}</span>
                  </div>
                </div>
                {/* hover rail (non-select mode) */}
                <div style={{ width: railW, flex: `0 0 ${railW}`, overflow: 'hidden', display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--border-lt)', opacity: i === sel ? 1 : 0.45, transition: 'width .18s' }}>
                  <div className="v2-rail-cell v2-rail-copy" title="Copy résumé with tracers" onClick={(e) => { e.stopPropagation(); focusAt(i); setPicker('copy') }} style={{ flex: 1, borderBottom: '1px solid var(--border-lt)' }}>⧉</div>
                  <div className="v2-rail-cell v2-rail-save" title="Save (s)" onClick={(e) => { e.stopPropagation(); saveJob(j) }} style={{ flex: 1, borderBottom: '1px solid var(--border-lt)' }}>♥</div>
                  <div className="v2-rail-cell v2-rail-skip" title="Skip (x)" onClick={(e) => { e.stopPropagation(); skipJob(j) }} style={{ flex: 1 }}>✕</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── ACTION COLUMN ── */}
      <div style={{ width: 62, flex: '0 0 62px', borderRight: '1px solid var(--border)', background: 'var(--panel)', display: 'flex', flexDirection: 'column', padding: '9px 6px', gap: 4 }}>
        {ACTIONS.map((a) => (
          <div key={a.label} className="v2-act" title={a.label} onClick={a.act}
            style={{ height: 48, flex: '0 0 48px', borderRadius: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2,
              border: `1px solid ${a.primary ? 'var(--accent)' : a.onState ? 'var(--accent)' : 'var(--border)'}`,
              background: a.primary ? 'var(--accent)' : a.onState || a.on ? 'var(--accent-bg)' : 'var(--surface)',
              color: a.primary ? '#fff' : a.onState || a.on ? 'var(--accent)' : a.warn ? 'var(--warn)' : 'var(--stone)' }}>
            <span style={{ fontSize: 13, lineHeight: 1 }}>{a.icon}</span>
            <span style={{ fontSize: 8, letterSpacing: '.02em', lineHeight: 1.1 }}>{a.label}</span>
          </div>
        ))}
        <div style={{ marginTop: 'auto', padding: '5px 1px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'center' }}>
          <span style={{ fontSize: 8, color: 'var(--faint)', textAlign: 'center', lineHeight: 1.25 }}>acts on focused</span>
        </div>
      </div>

      {/* ── DETAIL PANE ── */}
      <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {!d ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Select a job.</div>
        ) : (
          <>
            <div style={{ flex: '0 0 auto', padding: '11px 22px', borderBottom: '1px solid var(--border-lt)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 13 }}>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span title={d.title} style={{ fontFamily: 'var(--serif)', fontSize: 18, fontWeight: 500, letterSpacing: '-.02em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.title}</span>
                <span style={{ fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {[d.company, d.location, fmtSalary(d.salary_min, d.salary_max), H1B_LABEL[d.h1b_verdict], timeAgo(d.discovered_at)].filter(Boolean).join(' · ')}
                </span>
              </div>
              {bestScore(d) > 0 && <span style={{ flex: '0 0 auto', fontFamily: 'var(--serif)', fontSize: 22, letterSpacing: '-.02em', color: ringColor(bestScore(d)) }}>{bestScore(d)}</span>}
            </div>
            {d.url && (
              <div style={{ flex: '0 0 auto', padding: '6px 22px', borderBottom: '1px solid var(--border-lt)', background: 'var(--panel)', display: 'flex', alignItems: 'center', gap: 9 }}>
                <a href={d.url} target="_blank" rel="noopener noreferrer" style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 440 }}>{d.url.replace(/^https?:\/\//, '')}</a>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--accent)', textTransform: 'capitalize' }}>● {d.status}</span>
              </div>
            )}
            <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '20px 26px', minHeight: 0, background: 'var(--surface)' }}>
              <div style={{ maxWidth: '72ch', display: 'flex', flexDirection: 'column', gap: 11 }}>
                <h3 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 500, letterSpacing: '-.015em' }}>Description</h3>
                <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.62, color: 'var(--stone)', whiteSpace: 'pre-wrap' }}>
                  {d.description || 'No description captured for this job.'}
                </p>
              </div>
            </div>

            {/* report drawer */}
            {drawer && (
              <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 396, background: 'var(--surface)', borderLeft: '2px solid var(--accent)', boxShadow: '-12px 0 34px rgba(0,0,0,.12)', display: 'flex', flexDirection: 'column', zIndex: 20 }}>
                <div style={{ flex: '0 0 auto', padding: '12px 17px', borderBottom: '1px solid var(--border)', background: 'var(--panel)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-.02em' }}>{bestScore(d) || '–'}</span>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
                    {Object.entries(d.cv_scores || {}).filter(([, v]) => typeof v === 'number').map(([name, sc], k) => (
                      <div key={name} title={name} style={{ height: 23, padding: '0 9px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5, maxWidth: 160,
                        border: `1px solid ${k === 0 ? 'var(--accent)' : 'var(--border)'}`, background: k === 0 ? 'var(--accent-bg)' : 'var(--surface)', color: k === 0 ? 'var(--accent)' : 'var(--stone)' }}>
                        {name === 'Tailored' && <span style={{ flex: '0 0 auto', fontSize: 8 }}>✦</span>}
                        <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</span>
                        <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, opacity: 0.7 }}>{sc}</span>
                      </div>
                    ))}
                  </div>
                  <div className="v2-x" onClick={() => setDrawer(false)} style={{ flex: '0 0 auto', width: 24, height: 24, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--muted)' }}>✕</div>
                </div>
                <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '15px 17px', display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0 }}>
                  {d.apply_recommendation && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={{ fontSize: 9.5, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Recommendation</span>
                      <span style={{ fontFamily: 'var(--serif)', fontSize: 16, color: 'var(--accent)' }}>{d.apply_recommendation}</span>
                    </div>
                  )}
                  {(d.fit_strengths || []).length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={{ fontSize: 9.5, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Strengths</span>
                      {(d.fit_strengths || []).map((s, k) => (
                        <div key={k} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 9px', borderRadius: 6, background: 'var(--accent-bg)' }}>
                          <span style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--accent)', lineHeight: 1.5 }}>✓</span>
                          <span style={{ flex: 1, fontSize: 12, lineHeight: 1.5, color: 'var(--stone)' }}>{s}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {(d.fit_gaps || []).length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={{ fontSize: 9.5, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Gaps</span>
                      {(d.fit_gaps || []).map((g, k) => (
                        <div key={k} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 9px', borderRadius: 6, background: 'var(--danger-bg)' }}>
                          <span style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--danger)', lineHeight: 1.5 }}>✕</span>
                          <span style={{ flex: 1, fontSize: 12, lineHeight: 1.5, color: 'var(--stone)' }}>{g}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {!d.apply_recommendation && !(d.fit_strengths || []).length && !(d.fit_gaps || []).length && (
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>No score report yet. Save or rescore this job to generate one.</span>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* tailor / copy picker */}
        {picker && (
          <div onClick={() => setPicker(null)} style={{ position: 'absolute', inset: 0, background: 'rgba(27,26,22,.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 40 }}>
            <div onClick={(e) => e.stopPropagation()} style={{ width: 340, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)', boxShadow: '0 20px 50px rgba(0,0,0,.22)', padding: 18 }}>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 17, marginBottom: 4 }}>{picker === 'tailor' ? '✦ Tailor a résumé' : '⧉ Copy a résumé'}</div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12 }}>
                {picker === 'tailor' ? 'Pick a base — a tailored version is generated for this job.' : 'Pick a base — an editable copy with tracer links is created.'}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 260, overflow: 'auto' }} className="v2-scroll">
                {resumes.length === 0 ? (
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>No base résumés found.</span>
                ) : resumes.map((r) => (
                  <div key={r.id} className="v2-navlink" onClick={() => runResume(picker, r.id)}
                    style={{ padding: '9px 11px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, display: 'flex', alignItems: 'center' }}>
                    {r.name}
                  </div>
                ))}
              </div>
              <div className="v2-pill" onClick={() => setPicker(null)} style={{ marginTop: 12, textAlign: 'center', fontSize: 12, color: 'var(--muted)' }}>Cancel</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
