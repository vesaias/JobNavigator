import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
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
  jobspy_zip_recruiter: 'ZipRecruiter', jobspy_google: 'Google', levels_fyi: 'Levels', linkedin_personal: 'LinkedIn Personal',
  linkedin_extension: 'LinkedIn Extension', jobright: 'Jobright', freehire: 'FreeHire', playwright_url: 'Company careers', playwright_direct: 'Career page',
}
const srcLabel = (s) => SOURCE_LABELS[s] || s || ''
const STATUS_OPTS = [['new', 'New'], ['saved', 'Saved'], ['applied', 'Applied'], ['skip', 'Skip'], ['ignored', 'Ignored']]
const SORT_OPTS = [['score', 'Top score'], ['date', 'Newest first'], ['salary', 'Salary, high to low'], ['company', 'Company A–Z']]
const DEFAULTS = { status: [], company: [], source: [], h1b_verdict: [], min_score: '', min_salary: '', max_salary: '' }

// small dropdown shell (trigger pill + panel + backdrop). Flips to right-align
// when the panel would overflow the viewport's right edge.
function Drop({ label, active, open, onToggle, children, align = 'left', width = 216, trigger }) {
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
        <div onClick={onToggle} style={{ height: 30, padding: '0 13px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, cursor: 'pointer',
          border: `1px solid ${active ? 'var(--accent)' : 'var(--edge)'}`, background: active ? 'var(--accent-soft)' : 'var(--surface)', color: active ? 'var(--accent)' : 'var(--text-2)' }}>
          {label}<span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>
        </div>
      )}
      {open && pos && (
        <>
          <div onClick={onToggle} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
          <div className="v2-scroll" style={{ position: 'fixed', left: pos.left, top: pos.top, zIndex: 45, width, maxHeight: 360, overflowY: 'auto', overflowX: 'hidden', boxSizing: 'border-box',
            background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 8 }}>
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
      <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: on ? 'none' : '1px solid var(--line)', background: on ? 'var(--accent)' : 'transparent', color: 'var(--accent-ink)', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{on ? '✓' : ''}</span>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  )
}

// pick modifier: ⌘ on macOS, Ctrl elsewhere (matches rowClick's metaKey||ctrlKey)
const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || '')
const PICK_KEY = IS_MAC ? '⌘' : 'Ctrl'
const SHORTCUTS = [['j / ↓', 'Next job'], ['k / ↑', 'Previous job'], ['s', 'Save / unsave'], ['x', 'Skip'], ['a', 'Mark applied'], ['e / o', 'Open posting'], ['r', 'Rescore'], [`${PICK_KEY}-click`, 'Select'], ['Shift-click', 'Select range']]

// toast (progress + undo). phase: '' | 'start' | 'ok' | 'nok'
function Toast({ t, onClose }) {
  const [shown, setShown] = useState(false)
  useEffect(() => { const r = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(r) }, [])
  const vis = shown && !t.leaving
  const bg = t.phase === 'ok' ? 'var(--good)' : t.phase === 'nok' ? 'var(--bad)' : 'var(--rail)'
  const icon = t.phase === 'start' ? '⋯' : t.phase === 'ok' ? '✓' : t.phase === 'nok' ? '✕' : '●'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 13px', borderRadius: 10, background: bg, color: '#f6f3ea', fontSize: 12.5, boxShadow: '0 10px 30px rgba(0,0,0,.28)', maxWidth: 360, transform: vis ? 'translateY(0)' : 'translateY(8px)', opacity: vis ? 1 : 0, transition: 'opacity .28s, transform .28s' }}>
      <span style={{ flex: '0 0 auto', color: t.phase === 'start' ? 'var(--rail-accent)' : 'inherit' }}>{icon}</span>
      <span style={{ flex: 1, minWidth: 0 }}>{t.msg}</span>
      {t.actionLabel && <span onClick={t.onAction} style={{ flex: '0 0 auto', color: 'var(--rail-accent)', cursor: 'pointer', fontWeight: 600 }}>{t.actionLabel}</span>}
      <span onClick={onClose} style={{ flex: '0 0 auto', opacity: 0.6, cursor: 'pointer' }}>✕</span>
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
  const [companyQuery, setCompanyQuery] = useState('')

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
  const [picker, setPicker] = useState(null)      // {mode, jobs:[...]} — opens the Create-copy modal
  const [cvMode, setCvMode] = useState('tailor')  // 'tailor' | 'copy' method toggle
  const [cvBase, setCvBase] = useState(null)      // selected base résumé id (or 'persona')
  const [rowMenu, setRowMenu] = useState(null)
  const [headMenu, setHeadMenu] = useState(false)
  const [checked, setChecked] = useState(() => new Set())
  const lastIdx = useRef(null)

  const [personaAvailable, setPersonaAvailable] = useState(false)
  const [toasts, setToasts] = useState([])
  const [watchExtra, setWatchExtra] = useState([])   // ids of jobs pruned from view but still processing
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [rescoreJob, setRescoreJob] = useState(null)
  const [rescoreOpts, setRescoreOpts] = useState([])
  const [rescoreSel, setRescoreSel] = useState([])
  const [rescoreDepth, setRescoreDepth] = useState('full')
  const scoreWatchRef = useRef([])
  const pendingRef = useRef({})   // {jobId:{title,company}} → completion toast
  const seenActiveRef = useRef(new Set())   // jobs confirmed in-flight (avoids first-tick false completion)
  const [searchParams, setSearchParams] = useSearchParams()
  const PAGE = 40

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 300)
  }, [])
  const pushToast = useCallback((toast) => {
    const id = `${toast.phase || 'x'}-${Object.keys(pendingRef.current).length}-${Math.random().toString(36).slice(2, 7)}`
    setToasts((prev) => [...prev, { ...toast, id }])
    setTimeout(() => dismissToast(id), toast.ttl ?? 2600)
    return id
  }, [dismissToast])

  const listRef = useRef(null)
  const jobsRef = useRef(jobs); useEffect(() => { jobsRef.current = jobs }, [jobs])
  const selRef = useRef(sel); useEffect(() => { selRef.current = sel }, [sel])
  const detailRef = useRef(detail); useEffect(() => { detailRef.current = detail }, [detail])

  useEffect(() => { const t = setTimeout(() => setDSearch(search), 400); return () => clearTimeout(t) }, [search])
  useEffect(() => {
    api.get('/jobs/companies/list', { params: { counts: 1 } }).then(({ data }) => setCompanyList(data || [])).catch(() => {})
    api.get('/jobs/sources/list').then(({ data }) => setSourceList(data || [])).catch(() => {})
    api.get('/jobs/verdicts/list').then(({ data }) => setVerdictList(data || [])).catch(() => {})
    api.get('/resumes?is_base=true').then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/jobs/feed-stats').then(({ data }) => setStats(data)).catch(() => {})
  }, [])

  const buildParams = useCallback((off) => {
    const p = { limit: PAGE, offset: off }
    if (filters.status.length) p.status = filters.status.join(',')
    if (filters.company.length) p.company = filters.company.join(',')
    if (filters.source.length) p.source = filters.source.join(',')
    if (filters.h1b_verdict.length) p.h1b_verdict = filters.h1b_verdict.join(',')
    if (filters.min_score !== '') p.min_score = filters.min_score
    if (filters.min_salary) p.min_salary = Number(filters.min_salary) * 1000
    if (filters.max_salary) p.max_salary = Number(filters.max_salary) * 1000
    if (dSearch) p.title_search = dSearch
    if (sortBy !== 'date') p.sort_by = sortBy
    return p
  }, [filters, sortBy, dSearch])

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/jobs', { params: buildParams(0) })
      const n = (data.jobs || []).length
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
      setOffset(n)
      setHasMore(n < (data.total || 0))
    } catch (e) { console.error('v2 feed load failed', e) }
    setLoading(false)
  }, [buildParams])
  useEffect(() => { fetchJobs() }, [fetchJobs])

  // append next page (infinite scroll + refill after triage drains the list)
  const loadingMoreRef = useRef(false)
  const offsetRef = useRef(offset); useEffect(() => { offsetRef.current = offset }, [offset])
  const hasMoreRef = useRef(hasMore); useEffect(() => { hasMoreRef.current = hasMore }, [hasMore])
  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current || !hasMoreRef.current) return
    loadingMoreRef.current = true
    try {
      const off = offsetRef.current
      const { data } = await api.get('/jobs', { params: buildParams(off) })
      const fetched = data.jobs || []
      setJobs((prev) => { const seen = new Set(prev.map((j) => j.id)); const fresh = fetched.filter((j) => !seen.has(j.id)); return fresh.length ? [...prev, ...fresh] : prev })
      setTotal(data.total || 0)
      setOffset(off + fetched.length)
      setHasMore(off + fetched.length < (data.total || 0) && fetched.length > 0)
    } catch (e) { console.error('load more failed', e) }
    loadingMoreRef.current = false
  }, [buildParams])
  const onListScroll = useCallback((e) => {
    const el = e.currentTarget
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 320) loadMore()
  }, [loadMore])

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
    // keep the current/deep-linked detail if it's still in the list (align focus);
    // otherwise focus the top of the (re)loaded list
    const curId = detailRef.current?.id
    const idx = curId ? jobs.findIndex((j) => j.id === curId) : -1
    if (idx >= 0) setSel(idx)
    else focusAt(Math.min(sel, jobs.length - 1))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, loading])

  const patchLocal = useCallback((id, changes) => {
    const leaves = filters.status.length && changes.status && !filters.status.includes(changes.status)
    setJobs((prev) => {
      if (leaves) {
        const next = prev.filter((j) => j.id !== id)
        setTotal((t) => Math.max(0, t - 1))
        if (next.length < 12) loadMore()
        return next
      }
      return prev.map((j) => (j.id === id ? { ...j, ...changes } : j))
    })
    setDetail((d) => (d && d.id === id ? { ...d, ...changes } : d))
  }, [filters.status, loadMore])
  const patchRemote = useCallback(async (job, changes) => {
    patchLocal(job.id, changes)
    try { await api.patch(`/jobs/${job.id}`, changes) } catch (e) { console.error(e); fetchJobs() }
  }, [patchLocal, fetchJobs])
  const watchForScore = useCallback((id) => {
    if (id && !scoreWatchRef.current.some((w) => w.id === id)) scoreWatchRef.current = [...scoreWatchRef.current, { id, until: Date.now() + 90000 }]
  }, [])
  const showUndo = useCallback((job, prevStatus, prevSaved, msg) => {
    pushToast({ msg, actionLabel: 'Undo', ttl: 5000, onAction: async () => { try { await api.patch(`/jobs/${job.id}`, { status: prevStatus, saved: prevSaved }); fetchJobs() } catch (e) { console.error(e) } } })
  }, [pushToast, fetchJobs])
  const saveJob = (j) => { const willSave = !j.saved; if (willSave && scoredCount(j) === 0) watchForScore(j.id); patchRemote(j, { saved: willSave, status: willSave ? 'saved' : 'new' }) }
  const skipJob = (j) => { showUndo(j, j.status, j.saved, `Skipped "${j.title}"`); patchRemote(j, { status: 'skip' }) }
  const applyJob = (j) => { showUndo(j, j.status, j.saved, `Applied to "${j.title}"`); patchRemote(j, { status: 'applied' }) }
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
    pendingRef.current[job.id] = { title: job.title, company: job.company }
    pushToast({ phase: 'start', msg: `Scoring "${job.title}"…` })
    api.post(`/analyze/${job.id}?depth=full`, {}).then(() => {
      setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'analyze_job'])] } : x))
      setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
    }).catch((e) => { delete pendingRef.current[job.id]; pushToast({ phase: 'nok', msg: `Scoring failed for "${job.title}"` }); console.error(e) })
  }, [pushToast])

  // rescoreJob holds { label, jobs:[...] } — one job or a bulk set
  const loadRescoreOpts = useCallback(async () => {
    setRescoreDepth('full')
    try {
      const [rz, st] = await Promise.all([api.get('/resumes?is_base=true'), api.get('/settings')])
      const opts = (rz.data || []).map((r) => ({ id: r.id, name: r.name, note: 'base' }))
      if (personaAvailable) opts.push({ id: 'persona', name: 'Persona', note: 'from /persona' })
      setRescoreOpts(opts)
      const def = st.data?.default_resume_id
      setRescoreSel(def && opts.some((o) => o.id === def) ? [def] : opts.map((o) => o.id))
    } catch (e) { console.error(e); setRescoreOpts([]); setRescoreSel([]) }
  }, [personaAvailable])
  const openRescore = useCallback((job) => { setRescoreJob({ verb: scoredCount(job) > 0 ? 'Rescore' : 'Score', title: job.title, company: job.company, jobs: [job] }); loadRescoreOpts() }, [loadRescoreOpts])
  const runRescore = useCallback(async () => {
    const target = rescoreJob
    if (!target || !rescoreSel.length) return
    const list = target.jobs || []
    setRescoreJob(null)
    if (list.length > 1) pushToast({ phase: 'start', msg: `Scoring ${list.length} jobs…` })
    for (const job of list) {
      if (list.length === 1) { pendingRef.current[job.id] = { title: job.title, company: job.company }; pushToast({ phase: 'start', msg: `Scoring "${job.title}"…` }) }
      try {
        await api.post(`/analyze/${job.id}?depth=${rescoreDepth}`, { cv_ids: rescoreSel })
        setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'analyze_job'])] } : x))
        setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
      } catch (e) { delete pendingRef.current[job.id]; console.error(e) }
    }
  }, [rescoreJob, rescoreSel, rescoreDepth, pushToast])

  const runResume = useCallback(async (mode, list, baseId) => {
    setPicker(null)
    for (const job of list) {
      try {
        if (mode === 'copy') { const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: job.id }); if (list.length === 1) window.location.href = `/resumes?resume=${data.id}` }
        else {
          pendingRef.current[job.id] = { title: job.title, company: job.company }
          pushToast({ phase: 'start', msg: `Tailoring for "${job.title}"…` })
          await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: job.id })
          setJobs((prev) => prev.map((x) => x.id === job.id ? { ...x, in_flight: [...new Set([...(x.in_flight || []), 'tailor_resume'])] } : x))
          setWatchExtra((prev) => prev.includes(job.id) ? prev : [...prev, job.id])
        }
      } catch (e) { delete pendingRef.current[job.id]; pushToast({ phase: 'nok', msg: `${mode === 'copy' ? 'Copy' : 'Tailor'} failed for "${job.title}"` }); console.error(`${mode} failed`, e.response?.data?.detail || e.message) }
    }
    setChecked(new Set())
  }, [pushToast])
  const openTailored = useCallback(async (job) => {
    if (job.tailored_resume_id) { window.location.href = `/resumes?resume=${job.tailored_resume_id}`; return }
    try { const { data } = await api.get('/resumes'); const copy = (data || []).find((r) => !r.is_base && r.job_id === job.id); if (copy) { window.location.href = `/resumes?resume=${copy.id}`; return } } catch {}
    setPicker({ mode: 'tailor', jobs: [job] })
  }, [])

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

  const unscored = useMemo(() => jobs.filter((j) => scoredCount(j) === 0 && ['new', 'saved'].includes(j.status)), [jobs])
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
        case 'f': case 'j': case 'ArrowDown': e.preventDefault(); focusAt(Math.min(idx + 1, list.length - 1)); break
        case 'g': case 'k': case 'ArrowUp': e.preventDefault(); focusAt(Math.max(idx - 1, 0)); break
        case 's': if (job) { saveJob(job); focusAt(Math.min(idx + 1, list.length - 1)) } break
        case 'x': if (job) { skipJob(job); focusAt(Math.min(idx, list.length - 2)) } break
        case 'a': if (job) applyJob(job); break
        case 'e': if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer'); break
        case 'r': if (job) openRescore(job); break
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

  // persona availability (adds a "Persona" option to score/tailor)
  useEffect(() => { api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {}) }, [])

  // deep-link ?job=<id> → open that job's detail
  useEffect(() => {
    const jid = searchParams.get('job')
    if (!jid) return
    api.get(`/jobs/${jid}`).then(({ data }) => { setDetail(data); setSearchParams({}, { replace: true }) }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

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
            try { const { data: jd } = await api.get(`/jobs/${id}`); setJobs((prev) => prev.map((j) => j.id === id ? jd : j)); setDetail((d) => (d && d.id === id ? jd : d)) } catch {}
            const meta = pendingRef.current[id]
            if (meta) {
              const ok = statusMap[id] !== 'failed'
              pushToast({ phase: ok ? 'ok' : 'nok', msg: `${ok ? 'Done' : 'Failed'} — "${meta.title}"${meta.company ? ` at ${meta.company}` : ''}` })
              delete pendingRef.current[id]
            }
          }
          setWatchExtra((prev) => prev.filter((id) => !finished.includes(id)))
        }
        setJobs((prev) => prev.map((j) => (data[j.id] ? { ...j, in_flight: data[j.id] } : j)))
      } catch { /* retry next tick */ }
    }
    const h = setInterval(tick, 3000); tick()
    return () => { cancelled = true; clearInterval(h) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((j) => ((j.in_flight || []).length ? j.id : null)).filter(Boolean).join(','), watchExtra.join(',')])

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
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px 24px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>The Feed</h1>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>{total} open roles · {stats.arrived_today} arrived today · {stats.unscored} not yet scored</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {stats.unscored > 0 && <div onClick={openRescoreBulk} title="Pick résumés + depth, then score every unscored job" style={{ height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, cursor: 'pointer' }}>Score {stats.unscored} unscored jobs</div>}
        </div>
      </header>

      {/* filter bar */}
      <div style={{ flex: '0 0 auto', padding: '0 30px 14px 24px', display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--line)' }}>
        <div style={{ position: 'relative', flex: '0 0 auto', marginRight: 3 }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: 'var(--muted)', pointerEvents: 'none' }}>⌕</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search titles…" style={{ width: 184, height: 30, padding: '0 12px 0 29px', borderRadius: 99, border: '1px solid var(--line)', background: 'var(--surface)', fontSize: 12.5, color: 'var(--text)', outline: 'none', fontFamily: 'var(--sans)' }} />
        </div>
        <Drop label="Source" active={filters.source.length > 0} open={menu === 'source'} onToggle={() => setMenu(menu === 'source' ? null : 'source')}>
          {sourceList.length ? sourceList.map((s) => <Check key={s} on={filters.source.includes(s)} label={srcLabel(s)} onClick={() => togF('source', s)} />) : <div style={{ padding: 8, fontSize: 12, color: 'var(--muted)' }}>No sources</div>}
        </Drop>
        <Drop label="Company" active={filters.company.length > 0} open={menu === 'company'} onToggle={() => setMenu(menu === 'company' ? null : 'company')} width={248}>
          <input autoFocus value={companyQuery} onChange={(e) => setCompanyQuery(e.target.value)} placeholder={`Type to search ${companyList.length} companies…`}
            style={{ width: '100%', height: 30, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 7, fontSize: 12.5, background: 'var(--surface-2)', color: 'var(--text)', outline: 'none', marginBottom: 6, fontFamily: 'var(--sans)' }} />
          {(() => {
            const q = companyQuery.trim().toLowerCase()
            const list = companyList.filter((c) => filters.company.includes(c.name) || c.name.toLowerCase().includes(q))
            // picked companies pin to the top, keeping the backend's count-desc order within each group
            const sorted = [...list].sort((a, b) => (filters.company.includes(b.name) ? 1 : 0) - (filters.company.includes(a.name) ? 1 : 0)).slice(0, 80)
            return sorted.length ? (
              <>
                {sorted.map((c) => (
                  <div key={c.name} className="v2-menuitem" onClick={() => togF('company', c.name)} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '6px 8px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer' }}>
                    <span style={{ flex: '0 0 auto', width: 15, height: 15, borderRadius: 4, border: filters.company.includes(c.name) ? 'none' : '1px solid var(--edge)', background: filters.company.includes(c.name) ? 'var(--accent)' : 'transparent', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>{filters.company.includes(c.name) ? '✓' : ''}</span>
                    <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-2)' }}>{c.name}</span>
                    <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--muted)' }}>{c.count}</span>
                  </div>
                ))}
                <div style={{ padding: '6px 8px 2px', fontSize: 10.5, color: 'var(--muted)', lineHeight: 1.4 }}>Top by open roles · picked companies pin to the top</div>
              </>
            ) : <div style={{ padding: '6px 8px', fontSize: 12, color: 'var(--muted)' }}>No matches</div>
          })()}
        </Drop>
        <Drop label="H-1B" active={filters.h1b_verdict.length > 0} open={menu === 'h1b'} onToggle={() => setMenu(menu === 'h1b' ? null : 'h1b')} width={196}>
          {['likely', 'possible', 'unlikely', 'unknown'].filter((v) => verdictList.includes(v)).map((v) => <Check key={v} on={filters.h1b_verdict.includes(v)} label={H1B[v].label.replace('H-1B ', '')} onClick={() => togF('h1b_verdict', v)} />)}
        </Drop>
        <Drop label="Score ≥" active={filters.min_score !== ''} open={menu === 'score'} onToggle={() => setMenu(menu === 'score' ? null : 'score')} width={212}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[70, 80, 90].map((n) => <div key={n} onClick={() => setF({ min_score: String(n) })} style={{ flex: 1, height: 28, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, cursor: 'pointer', border: `1px solid ${filters.min_score === String(n) ? 'var(--accent)' : 'var(--edge)'}`, background: filters.min_score === String(n) ? 'var(--accent-soft)' : 'transparent', color: filters.min_score === String(n) ? 'var(--accent)' : 'var(--text-2)' }}>{n}</div>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>or at least</span>
            <input type="number" value={filters.min_score} onChange={(e) => setF({ min_score: e.target.value })} style={{ flex: 1, minWidth: 0, height: 28, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--surface-2)', color: 'var(--text)' }} />
          </div>
          <div style={{ marginTop: 8, fontSize: 10.5, color: 'var(--muted)' }}>Unscored jobs stay visible — this only hides low scores</div>
        </Drop>
        <Drop label="Salary" active={!!(filters.min_salary || filters.max_salary)} open={menu === 'salary'} onToggle={() => setMenu(menu === 'salary' ? null : 'salary')} width={224}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[150, 180, 220].map((n) => <div key={n} onClick={() => setF({ min_salary: String(n) })} style={{ flex: 1, height: 28, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, cursor: 'pointer', border: `1px solid ${filters.min_salary === String(n) ? 'var(--accent)' : 'var(--edge)'}`, background: filters.min_salary === String(n) ? 'var(--accent-soft)' : 'transparent', color: filters.min_salary === String(n) ? 'var(--accent)' : 'var(--text-2)' }}>${n}K</div>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>at least</span>
            <input type="number" placeholder="$K" value={filters.min_salary} onChange={(e) => setF({ min_salary: e.target.value })} style={{ flex: 1, minWidth: 0, height: 28, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--surface-2)', color: 'var(--text)' }} />
          </div>
          <div style={{ marginTop: 8, fontSize: 10.5, color: 'var(--muted)' }}>Jobs without a listed salary stay visible</div>
        </Drop>
        <Drop align="left" width={170} active open={menu === 'status'} onToggle={() => setMenu(menu === 'status' ? null : 'status')}
          trigger={(t) => {
            const statusActive = !(filters.status.length === DEFAULTS.status.length && DEFAULTS.status.every((s) => filters.status.includes(s)))
            return (
              <div onClick={t} style={{ height: 30, padding: '0 13px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 500, cursor: 'pointer',
                border: `1px solid ${statusActive ? 'var(--accent)' : 'var(--edge)'}`, background: statusActive ? 'var(--accent-soft)' : 'var(--surface)', color: statusActive ? 'var(--accent)' : 'var(--text-2)' }}>
                Status · {filters.status.map((s) => STATUS_OPTS.find((o) => o[0] === s)?.[1]).join(', ') || 'Any'}
                {statusActive ? <span onClick={(e) => { e.stopPropagation(); setF({ status: DEFAULTS.status }) }} style={{ opacity: 0.6 }}>✕</span> : <span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>}
              </div>
            )
          }}>
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
          <div style={{ position: 'relative', padding: '12px 14px 8px 24px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
            <div onClick={() => setChecked(checked.size === jobs.length && jobs.length ? new Set() : new Set(jobs.map((j) => j.id)))} title="Select all shown" style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: `1px solid ${checked.size === jobs.length && jobs.length ? 'var(--accent)' : 'var(--faint)'}`, background: checked.size === jobs.length && jobs.length ? 'var(--accent)' : 'transparent', color: 'var(--accent-ink)', fontSize: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>{checked.size === jobs.length && jobs.length ? '✓' : ''}</div>
            <span style={{ flex: '0 0 auto', whiteSpace: 'nowrap' }}>{jobs.length} shown · {total} matching</span>
            <div style={{ marginLeft: 'auto', flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.02em' }}>⇧ range · {PICK_KEY} pick</span>
              <span onClick={() => setShortcutsOpen((v) => !v)} title="Keyboard shortcuts" style={{ cursor: 'pointer', width: 16, height: 16, borderRadius: 99, border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--muted)' }}>?</span>
            </div>
            {shortcutsOpen && (
              <>
                <div onClick={() => setShortcutsOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 34 }} />
                <div style={{ position: 'absolute', top: '100%', right: 14, zIndex: 35, marginTop: 4, width: 214, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 10 }}>
                  <div style={{ fontSize: 10.5, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6 }}>Keyboard</div>
                  {SHORTCUTS.map(([k, desc]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '3px 0', fontSize: 12 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{k}</span>
                      <span style={{ color: 'var(--muted)' }}>{desc}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {checked.size > 0 && (
            <div style={{ position: 'absolute', left: '50%', bottom: 14, transform: 'translateX(-50%)', zIndex: 25, display: 'flex', alignItems: 'center', gap: 6, padding: '7px 8px 7px 14px', background: 'var(--rail)', borderRadius: 99, boxShadow: '0 10px 30px rgba(0,0,0,.28)' }}>
              <span style={{ fontSize: 12, color: '#f6f3ea', fontWeight: 600, whiteSpace: 'nowrap' }}>{checked.size} selected</span>
              <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,.18)', margin: '0 3px' }} />
              <div onClick={() => bulkStatus('saved')} style={{ height: 27, padding: '0 12px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: 500, cursor: 'pointer' }}>Save</div>
              <div onClick={() => bulkStatus('skip')} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.42)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}>Skip</div>
              <div onClick={bulkScore} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.42)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}>Score</div>
              <div onClick={() => setPicker({ mode: 'tailor', jobs: jobs.filter((j) => checked.has(j.id)) })} style={{ height: 27, padding: '0 11px', border: '1px solid rgba(255,255,255,.42)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: '#f6f3ea', cursor: 'pointer' }}><span style={{ color: 'var(--rail-accent)' }}>✦</span>Tailor</div>
              <div onClick={() => setChecked(new Set())} style={{ width: 27, height: 27, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'rgba(255,255,255,.55)', cursor: 'pointer' }}>✕</div>
            </div>
          )}

          <div ref={listRef} onScroll={onListScroll} className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px 12px', display: 'flex', flexDirection: 'column', userSelect: 'none', WebkitUserSelect: 'none' }}>
            {loading ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
              : jobs.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No jobs match.</div>
              : jobs.map((j, i) => {
                const score = bestScore(j), nsc = scoredCount(j)
                const badge = BADGE[j.status]
                const run = (j.in_flight || []).length > 0
                const isIgnored = j.status === 'ignored'
                const on = checked.has(j.id)
                const visa = H1B[j.h1b_verdict]
                return (
                  <div key={j.id} data-row={i} className="v2-row" onClick={(e) => rowClick(e, i, j)}
                    style={{ flex: '0 0 auto', display: 'flex', alignItems: 'stretch', borderBottom: '1px solid var(--line-soft)', cursor: 'pointer', borderRadius: 8, backgroundColor: on ? 'var(--accent-soft)' : i === sel ? 'var(--surface-2)' : 'transparent', backgroundImage: (isIgnored && !on && i !== sel) ? 'repeating-linear-gradient(-45deg, transparent 0 8px, var(--line-soft) 8px 10px)' : 'none', overflow: 'hidden' }}>
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 14, padding: '10px 12px', opacity: isIgnored ? 0.55 : 1 }}>
                      {/* ring */}
                      <div style={{ position: 'relative', width: 44, height: 44, flex: '0 0 44px' }}>
                        {nsc > 0 ? (
                          <>
                            <svg viewBox="0 0 44 44" style={{ width: 44, height: 44, transform: 'rotate(-90deg)' }}>
                              <circle cx="22" cy="22" r="17.5" fill="none" stroke="var(--track)" strokeWidth="2" />
                              <circle cx="22" cy="22" r="17.5" fill="none" stroke={scoreColor(score)} strokeWidth="2" strokeLinecap="round" strokeDasharray={`${(ROW_C * score / 100).toFixed(1)} ${ROW_C.toFixed(0)}`} />
                            </svg>
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 17, lineHeight: 1, color: scoreColor(score), transform: 'translateY(1px)' }}>{score}</div>
                            {nsc > 1 && <div title={`${nsc} résumé reports`} style={{ position: 'absolute', right: -3, bottom: -2, minWidth: 16, height: 16, padding: '0 3px', borderRadius: 99, background: 'var(--surface)', border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--text-2)' }}>{nsc}</div>}
                          </>
                        ) : run ? (
                          <>
                            <div className="v2-spin" style={{ position: 'absolute', inset: 0, border: '1px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, letterSpacing: '.07em', textTransform: 'uppercase', color: 'var(--accent)' }}>···</div>
                          </>
                        ) : (
                          <div className="v2-hover-accent" onClick={(e) => { e.stopPropagation(); scoreJob(j) }} title="Score this role" style={{ position: 'absolute', inset: 0, border: '1px dashed var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8.5, fontWeight: 600, letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--muted)', cursor: 'pointer' }}>Score</div>
                        )}
                        {on && <div style={{ position: 'absolute', left: -4, top: -3, width: 16, height: 16, borderRadius: 99, background: 'var(--accent)', border: '2px solid var(--surface)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>✓</div>}
                      </div>
                      {/* text */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, minHeight: 20 }}>
                          <span title={j.title} style={{ flex: 1, minWidth: 0, fontFamily: 'var(--serif)', fontSize: 16, fontWeight: 500, lineHeight: 1.15, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textDecoration: isIgnored ? 'line-through' : 'none', textDecorationColor: 'var(--muted)' }}>{j.title}</span>
                          {j.tailored_resume_id && <a href={`/resumes?resume=${j.tailored_resume_id}`} onClick={(e) => e.stopPropagation()} title="Open tailored résumé" style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, margin: '-2px -2px -2px 0', fontSize: 14, lineHeight: 1, color: 'var(--accent)' }}>✦</a>}
                          {badge && <span style={{ flex: '0 0 auto', fontSize: 9.5, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, border: `1px solid ${badge.bd}`, background: badge.bg, color: badge.fg }}>{badge.label}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, lineHeight: 1.2, fontWeight: 450, color: 'var(--text-2)', minWidth: 0 }}>
                          <span title={j.company} style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 230, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.company}</span>
                          {j.location && <span style={{ flex: '0 0 auto', color: 'var(--line)' }}>|</span>}
                          {j.location && <span title={j.location} style={{ flex: '1 1 auto', minWidth: 40, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.location}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 11, lineHeight: 1.2, fontWeight: 450, minWidth: 0, marginTop: 2 }}>
                          <span style={{ flex: '0 1 auto', minWidth: 0, maxWidth: 170, fontFamily: 'var(--mono)', color: fmtSalary(j.salary_min, j.salary_max) ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmtSalary(j.salary_min, j.salary_max) || 'Salary not listed'}</span>
                          {visa && <><span style={{ color: 'var(--line)' }}>·</span><span style={{ letterSpacing: '.04em', color: visa.c }}>{visa.label}</span></>}
                          <span style={{ color: 'var(--line)' }}>·</span><span style={{ color: 'var(--muted)' }}>{timeAgo(j.discovered_at)}</span>
                        </div>
                      </div>
                    </div>
                    {/* action column */}
                    <div style={{ position: 'relative', flex: '0 0 27px', display: 'flex', flexDirection: 'column', borderLeft: '1px solid var(--line-soft)' }} onClick={(e) => e.stopPropagation()}>
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
                          <div style={{ position: 'fixed', left: rowMenu.left, top: rowMenu.top, bottom: rowMenu.bottom, zIndex: 60, width: 228, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                            {[['Mark applied', 'a', () => applyJob(j)], ['Tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [j] })], ['Rescore', 'r', () => openRescore(j)], ['Open posting ↗', 'e', () => j.url && window.open(j.url, '_blank', 'noopener,noreferrer')]].map(([label, kb, act]) => (
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
                        {d.location && <><span style={{ color: 'var(--line)' }}>|</span><span style={{ maxWidth: 270, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.location}</span></>}
                        <span style={{ color: 'var(--line)' }}>|</span>
                        <span style={{ color: visaCol }}>{visaText}</span>
                      </div>
                    ) : <span style={{ fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{[d.company, fmtSalary(d.salary_min, d.salary_max) || 'Salary not listed', d.location, visaText, srcLabel(d.source), timeAgo(d.discovered_at)].filter(Boolean).join(' · ')}</span>}
                  </div>
                  {/* actions */}
                  <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {d.url && <a href={d.url} target="_blank" rel="noopener noreferrer" className="v2-act" style={{ height: headOpen ? 36 : 30, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-2)' }}>Open ↗</a>}
                    <div onClick={() => d.tailored_resume_id ? openTailored(d) : setPicker({ mode: 'tailor', jobs: [d] })} style={{ height: headOpen ? 36 : 30, padding: '0 19px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>{d.tailored_resume_id ? '✦ Open tailored ↗' : 'Tailor résumé'}</div>
                    <div style={{ position: 'relative', flex: '0 0 auto' }}>
                      <div title="More actions" onClick={(e) => { e.stopPropagation(); setHeadMenu((v) => !v) }} className="v2-act" style={{ width: headOpen ? 36 : 30, height: headOpen ? 36 : 30, border: `1px solid ${headMenu ? 'var(--accent)' : 'var(--edge)'}`, background: headMenu ? 'var(--accent-soft)' : 'transparent', color: headMenu ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, cursor: 'pointer' }}>⋯</div>
                      {headMenu && (
                        <>
                          <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                          <div style={{ position: 'absolute', top: '100%', right: 0, zIndex: 45, marginTop: 5, width: 236, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                            {[
                              ...(d.tailored_resume_id ? [['✦ Re-tailor résumé', 't', () => setPicker({ mode: 'tailor', jobs: [d] }), true]] : []),
                              ['Mark applied', 'a', () => applyJob(d)],
                              ['Rescore', 'r', () => openRescore(d)],
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
                        <circle cx="39" cy="39" r="35" fill="none" stroke="var(--track)" strokeWidth="5" />
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
                        <div onClick={() => openRescore(d)} className="v2-navlink" style={{ marginLeft: 'auto', padding: '7px 0', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>+ Rescore</div>
                      </div>
                      {/* body */}
                      <div className="v2-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '14px 30px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {rpt?.summary && <span style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-2)' }}>{rpt.summary}</span>}
                        {(d.fit_strengths || []).length > 0 && !rpt?.summary && <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{(d.fit_strengths || []).map((s, k) => <div key={k} style={{ display: 'flex', gap: 8, fontSize: 12.5, color: 'var(--text-2)' }}><span style={{ color: 'var(--good)' }}>✓</span><span>{s}</span></div>)}</div>}

                        {rpt?.breakdown && Object.keys(rpt.breakdown).length > 0 && (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '11px 30px' }}>
                            {Object.entries(rpt.breakdown).filter(([, v]) => typeof v === 'number').map(([label, val]) => {
                              const pct = Math.max(0, Math.min(100, Math.round((val / 20) * 100)))
                              return (
                                <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                                    <span style={{ fontSize: 12.5, color: 'var(--text-2)', textTransform: 'capitalize' }}>{label}</span>
                                    <span style={{ fontFamily: 'var(--serif)', fontSize: 15 }}>{val}<span style={{ fontSize: 11, color: 'var(--muted)' }}>/20</span></span>
                                  </div>
                                  <div style={{ height: 1, background: 'var(--line)' }}><div style={{ height: 1, background: 'var(--accent)', width: `${pct}%` }} /></div>
                                </div>
                              )
                            })}
                          </div>
                        )}

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
                              <div style={{ marginLeft: 'auto', display: 'flex', border: '1px solid var(--edge)', borderRadius: 99, overflow: 'hidden' }}>
                                {[['all', `All ${reqRows.length}`], ['gaps', `Gaps ${reqRows.length - reqMet}`]].map(([id, label]) => <div key={id} onClick={() => setReqFilter(id)} style={{ height: 24, padding: '0 11px', display: 'flex', alignItems: 'center', fontSize: 11.5, cursor: 'pointer', background: reqFilter === id ? 'var(--accent)' : 'transparent', color: reqFilter === id ? 'var(--accent-ink)' : 'var(--text-2)' }}>{label}</div>)}
                              </div>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <div style={{ display: 'flex', gap: 14, padding: '0 0 6px', borderBottom: '1px solid var(--line)', fontSize: 9.5, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)' }}>
                              <span style={{ flex: 1.05 }}>Requirement</span><span style={{ flex: 1.1 }}>Résumé match</span><span style={{ flex: '0 0 34px', textAlign: 'center' }}>Status</span>
                            </div>
                            {reqRows.filter((r) => reqFilter === 'all' || !r.matched).map((r, k) => (
                              <div key={k} style={{ display: 'flex', gap: 14, padding: '8px 0', borderBottom: '1px solid var(--line-soft)', fontSize: 12, lineHeight: 1.45 }}>
                                <span style={{ flex: 1.05, minWidth: 0 }}>{r.requirement}</span>
                                <span style={{ flex: 1.1, minWidth: 0, color: 'var(--muted)' }}>{r.cv_evidence || r.cv_match || '—'}</span>
                                <span style={{ flex: '0 0 34px', textAlign: 'center', color: r.matched ? 'var(--good)' : 'var(--bad)' }}>{r.matched ? '✓' : '✕'}</span>
                              </div>
                            ))}
                            </div>
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
                    <div style={{ flex: '0 0 auto', margin: '18px 30px 4px', display: 'flex', alignItems: 'center', gap: 20, padding: '16px 18px', border: '1px dashed var(--edge)', borderRadius: 10 }}>
                      <div style={{ width: 74, height: 74, flex: '0 0 74px', border: '1px dashed var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>No fit</div>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.015em' }}>Not scored yet</span>
                        <span style={{ fontSize: 13, color: 'var(--text-2)', maxWidth: '54ch' }}>Score this role against your résumés to see the fit breakdown, requirement mapping and missing keywords.</span>
                      </div>
                      <div onClick={() => openRescore(d)} style={{ flex: '0 0 auto', height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>Score this role</div>
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
                  {/* live / cached posting — full-bleed iframe */}
                  <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                    {dCached && (
                      <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 9, padding: '9px 30px', borderBottom: '1px solid var(--line)', background: 'var(--surface-2)' }}>
                        <span style={{ fontSize: 12, color: viewCached ? 'var(--accent)' : 'var(--muted)' }}>{viewCached ? 'Cached snapshot · captured when you applied' : 'Live posting'}</span>
                        <div style={{ marginLeft: 'auto', display: 'flex', background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 99, padding: 2, gap: 2 }}>
                          <div onClick={() => setViewCached(false)} style={{ height: 22, padding: '0 10px', borderRadius: 99, fontSize: 11, display: 'flex', alignItems: 'center', cursor: 'pointer', background: !viewCached ? 'var(--surface-2)' : 'transparent', color: !viewCached ? 'var(--text)' : 'var(--muted)' }}>Live</div>
                          <div onClick={() => setViewCached(true)} style={{ height: 22, padding: '0 10px', borderRadius: 99, fontSize: 11, display: 'flex', alignItems: 'center', cursor: 'pointer', background: viewCached ? 'var(--accent-soft)' : 'transparent', color: viewCached ? 'var(--accent)' : 'var(--muted)' }}>Cached</div>
                        </div>
                      </div>
                    )}
                    {viewCached && dCached ? (
                      <iframe title="cached" srcDoc={cachedHtml || '<p style="padding:16px;font-family:sans-serif">Loading cached snapshot…</p>'} sandbox="allow-same-origin" style={{ flex: 1, width: '100%', border: 'none', background: '#fff' }} />
                    ) : d.url ? (
                      <iframe title="posting" src={d.url} sandbox="allow-scripts allow-same-origin allow-popups allow-forms" style={{ flex: 1, width: '100%', border: 'none', background: '#fff' }} />
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

      {/* create résumé copy modal — method (tailor / copy) + base pick */}
      {picker && (() => {
        const single = picker.jobs.length === 1 ? picker.jobs[0] : null
        const existing = single?.tailored_resume_id
        return (
          <div onClick={() => setPicker(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
            <div onClick={(e) => e.stopPropagation()} style={{ width: 436, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* header */}
              <div style={{ padding: '20px 24px 16px', display: 'flex', flexDirection: 'column', gap: 5, borderBottom: '1px solid var(--line)' }}>
                <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Create résumé copy</span>
                <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em', lineHeight: 1.25 }}>{single ? single.title : `${picker.jobs.length} selected roles`}</span>
                {single?.company && <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{single.company}</span>}
              </div>
              {/* existing-copy banner */}
              {existing && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 24px', background: 'var(--accent-soft)', borderBottom: '1px solid var(--line)', fontSize: 12.5, color: 'var(--text-2)' }}>
                  <span style={{ flex: '0 0 auto', color: 'var(--accent)' }}>✦</span>
                  <span style={{ flex: 1, minWidth: 0 }}>A tailored copy already exists for this job.</span>
                  <span onClick={() => { setPicker(null); openTailored(single) }} style={{ flex: '0 0 auto', color: 'var(--accent)', fontWeight: 500, cursor: 'pointer' }}>Open it ↗</span>
                </div>
              )}
              {/* body */}
              <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Method</span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {[['tailor', '✦ Tailor with AI', 'Rewrites bullets against the report · LLM run'], ['copy', '⧉ Copy with tracers', 'Exact duplicate with tracking links · instant']].map(([m, label, help]) => {
                      const on = cvMode === m
                      return (
                        <div key={m} onClick={() => pickMethod(m)} style={{ flex: 1, padding: '10px 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 8, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <span style={{ fontSize: 13, fontWeight: 500, color: on ? 'var(--accent)' : 'var(--text)' }}>{label}</span>
                          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{help}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Base résumé</span>
                  {cvBases.length === 0 ? <span style={{ fontSize: 13, color: 'var(--muted)' }}>No base résumés found.</span>
                    : cvBases.map((r) => {
                      const on = cvBase === r.id
                      return (
                        <div key={r.id} className="v2-act" onClick={() => setCvBase(r.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, borderRadius: 8, cursor: 'pointer', fontSize: 13.5 }}>
                          <span style={{ flex: '0 0 auto', width: 15, height: 15, borderRadius: 99, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 99, background: on ? 'var(--accent)' : 'transparent' }} /></span>
                          <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</span>
                          {r.id === 'persona' && <span style={{ flex: '0 0 auto', fontSize: 11.5, color: 'var(--muted)' }}>from /persona</span>}
                        </div>
                      )
                    })}
                </div>
              </div>
              {/* footer */}
              <div style={{ padding: '14px 24px 18px', display: 'flex', alignItems: 'center', gap: 9, borderTop: '1px solid var(--line)' }}>
                <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{cvMode === 'tailor' ? 'Runs an LLM pass against résumé' : 'Instant · no LLM cost · lands in Résumés'}</span>
                <div onClick={() => setPicker(null)} className="v2-act" style={{ marginLeft: 'auto', height: 34, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
                <div onClick={() => cvBase != null && runResume(cvMode, picker.jobs, cvBase)} style={{ height: 34, padding: '0 18px', borderRadius: 99, background: cvBase != null ? 'var(--accent)' : 'var(--edge)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: cvBase != null ? 'pointer' : 'default', whiteSpace: 'nowrap', flex: '0 0 auto' }}>{cvMode === 'tailor' ? 'Tailor résumé' : 'Create copy'}</div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* rescore modal — pick résumés + depth */}
      {rescoreJob && (
        <div onClick={() => setRescoreJob(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 436, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* header */}
            <div style={{ padding: '20px 24px 16px', display: 'flex', flexDirection: 'column', gap: 5, borderBottom: '1px solid var(--line)' }}>
              <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>{rescoreJob.verb} against résumés</span>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em', lineHeight: 1.25 }}>{rescoreJob.title}</span>
              {rescoreJob.company && <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{rescoreJob.company}</span>}
            </div>
            {/* body */}
            <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Résumés</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--muted)' }}>{rescoreSel.length} selected</span>
                </div>
                {rescoreOpts.length === 0 ? <span style={{ fontSize: 13, color: 'var(--muted)' }}>No résumés available.</span>
                  : rescoreOpts.map((o) => {
                    const on = rescoreSel.includes(o.id)
                    return (
                      <div key={o.id} className="v2-act" onClick={() => setRescoreSel((prev) => prev.includes(o.id) ? prev.filter((x) => x !== o.id) : [...prev, o.id])}
                        style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, borderRadius: 8, cursor: 'pointer', fontSize: 13.5 }}>
                        <span style={{ flex: '0 0 auto', width: 17, height: 17, borderRadius: 5, border: on ? 'none' : '1px solid var(--edge)', background: on ? 'var(--accent)' : 'transparent', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>{on ? '✓' : ''}</span>
                        <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.name}</span>
                        <span style={{ flex: '0 0 auto', fontSize: 11.5, color: 'var(--muted)' }}>{o.note}</span>
                      </div>
                    )
                  })}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span style={{ fontSize: 10.5, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)' }}>Depth</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[['light', 'Light', 'Scores only'], ['full', 'Full', 'Report + keywords']].map(([v, label, help]) => {
                    const on = rescoreDepth === v
                    return (
                      <div key={v} onClick={() => setRescoreDepth(v)} style={{ flex: 1, padding: '10px 12px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 8, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
                        <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{help}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
            {/* footer */}
            <div style={{ padding: '14px 24px 18px', display: 'flex', alignItems: 'center', gap: 9, borderTop: '1px solid var(--line)' }}>
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Runs in the background</span>
              <div onClick={() => setRescoreJob(null)} className="v2-act" style={{ marginLeft: 'auto', height: 34, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
              <div onClick={runRescore} style={{ height: 34, padding: '0 18px', borderRadius: 99, background: rescoreSel.length ? 'var(--accent)' : 'var(--edge)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: rescoreSel.length ? 'pointer' : 'default', whiteSpace: 'nowrap', flex: '0 0 auto' }}>Run scoring</div>
            </div>
          </div>
        </div>
      )}

      {/* toasts (progress + undo) */}
      <div style={{ position: 'fixed', right: 20, bottom: 20, zIndex: 80, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
        {toasts.map((t) => <Toast key={t.id} t={t} onClose={() => dismissToast(t.id)} />)}
      </div>
    </div>
  )
}
