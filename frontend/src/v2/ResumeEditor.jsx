import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api'
import './theme.css'

const DANGEROUS = new Set(['__proto__', 'constructor', 'prototype'])
const scoreColor = (s) => (s >= 70 ? 'var(--good)' : s >= 50 ? 'var(--warn)' : 'var(--bad)')

// contiguous prefix/suffix word diff → { before, removed, added, after } (matches the design's model)
function wordDiff(a = '', b = '') {
  a = a || ''; b = b || ''
  if (a === b) return null
  const aw = a.split(' '), bw = b.split(' ')
  let p = 0
  while (p < aw.length && p < bw.length && aw[p] === bw[p]) p++
  let sa = aw.length, sb = bw.length
  while (sa > p && sb > p && aw[sa - 1] === bw[sb - 1]) { sa--; sb-- }
  const before = aw.slice(0, p).join(' ')
  return {
    before: before ? before + ' ' : '',
    removed: aw.slice(p, sa).join(' '),
    added: bw.slice(p, sb).join(' '),
    after: sa < aw.length ? ' ' + aw.slice(sa).join(' ') : '',
  }
}
// changes a tailored copy carries vs its base: modified summary/bullets + added (suggested) bullets
function computeChanges(base, copy) {
  if (!base || !copy) return []
  const out = []
  const sd = wordDiff(base.summary, copy.summary)
  if (sd) out.push({ key: 'summary', where: 'Summary', kind: 'modified', path: 'summary', baseText: base.summary || '', ...sd })
  ;(copy.experience || []).forEach((ce, i) => {
    const be = (base.experience || [])[i] || {}
    const bb = be.bullets || [], cb = ce.bullets || []
    cb.forEach((txt, j) => {
      if (j < bb.length) { const d = wordDiff(bb[j], txt); if (d) out.push({ key: `exp${i}b${j}`, where: `Experience · ${ce.company || 'role'} · bullet ${j + 1}`, kind: 'modified', path: `experience.${i}.bullets.${j}`, baseText: bb[j], ...d }) }
      else out.push({ key: `exp${i}nb${j}`, where: `Experience · ${ce.company || 'role'} · new bullet`, kind: 'added', before: '', removed: '', added: txt, after: '', text: txt })
    })
    ;(ce.suggested_bullets || []).forEach((sb, k) => out.push({ key: `exp${i}sb${k}`, where: `Experience · ${ce.company || 'role'} · suggested bullet`, kind: 'suggested', expIdx: i, sbIdx: k, before: '', removed: '', added: sb, after: '', text: sb }))
  })
  const bs = base.skills || {}, cs = copy.skills || {}
  Object.keys(cs).forEach((cat) => {
    if (!(cat in bs)) out.push({ key: `sk:${cat}`, where: `Skills · ${cat}`, kind: 'added', path: `skills.${cat}`, before: '', removed: '', added: String(cs[cat] || ''), after: '', text: String(cs[cat] || '') })
    else { const d = wordDiff(String(bs[cat] || ''), String(cs[cat] || '')); if (d) out.push({ key: `sk:${cat}`, where: `Skills · ${cat}`, kind: 'modified', path: `skills.${cat}`, baseText: String(bs[cat] || ''), ...d }) }
  })
  return out
}
const EMPTY = { header: { name: '', contact_items: [] }, summary: '', experience: [], skills: {}, education: [], projects: [], publications: [] }
const SECTION_ORDER = ['Header', 'Summary', 'Experience', 'Skills', 'Education', 'Projects', 'Publications']
const timeAgo = (s) => {
  if (!s) return ''
  const m = Math.floor((Date.now() - new Date(s).getTime()) / 60000)
  if (m < 1) return 'just now'; if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── field primitives (v2-styled, with the **bold** shortcut) ─────────────────
function Field({ label, value, onChange, placeholder, multiline, rows, mono, flex }) {
  const boldKey = (e) => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'b')) return
    e.preventDefault()
    const ta = e.target, s = ta.selectionStart, en = ta.selectionEnd, t = ta.value
    if (s === en) return
    const sel = t.slice(s, en)
    if (t.slice(s - 2, s) === '**' && t.slice(en, en + 2) === '**') { onChange(t.slice(0, s - 2) + sel + t.slice(en + 2)); setTimeout(() => { ta.selectionStart = s - 2; ta.selectionEnd = en - 2 }, 0) }
    else { onChange(t.slice(0, s) + '**' + sel + '**' + t.slice(en)); setTimeout(() => { ta.selectionStart = s + 2; ta.selectionEnd = en + 2 }, 0) }
  }
  const st = { width: '100%', padding: multiline ? '7px 9px' : '0 9px', height: multiline ? undefined : 30, minHeight: multiline ? (rows || 3) * 20 : undefined, border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface-2)', color: 'var(--text)', fontSize: mono ? 11 : 12.5, fontFamily: mono ? 'var(--mono)' : 'var(--sans)', outline: 'none', resize: multiline ? 'vertical' : undefined, lineHeight: multiline ? 1.5 : undefined }
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: flex || undefined, minWidth: 0 }}>
      {label && <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>{label}</span>}
      {multiline
        ? <textarea value={value || ''} onChange={(e) => onChange(e.target.value)} onKeyDown={boldKey} placeholder={placeholder} rows={rows || 3} style={st} />
        : <input type="text" value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={st} />}
    </label>
  )
}
// bullet text: borderless auto-growing textarea so a bullet reads as flowing text
// (the row supplies the border/highlight) — matches the design's static-text bullets
function BulletText({ value, onChange }) {
  const ref = useRef(null)
  const fit = () => { const el = ref.current; if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }
  useEffect(fit, [value])
  const boldKey = (e) => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'b')) return
    e.preventDefault()
    const ta = e.target, s = ta.selectionStart, en = ta.selectionEnd, t = ta.value
    if (s === en) return
    const sel = t.slice(s, en)
    if (t.slice(s - 2, s) === '**' && t.slice(en, en + 2) === '**') { onChange(t.slice(0, s - 2) + sel + t.slice(en + 2)); setTimeout(() => { ta.selectionStart = s - 2; ta.selectionEnd = en - 2 }, 0) }
    else { onChange(t.slice(0, s) + '**' + sel + '**' + t.slice(en)); setTimeout(() => { ta.selectionStart = s + 2; ta.selectionEnd = en + 2 }, 0) }
  }
  return <textarea ref={ref} value={value || ''} onChange={(e) => onChange(e.target.value)} onInput={fit} onKeyDown={boldKey} rows={1}
    style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', resize: 'none', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)', padding: 0, overflow: 'hidden' }} />
}
const IconBtn = ({ onClick, title, children, danger }) => (
  <span onClick={onClick} title={title} className="v2-hover-accent" style={{ flex: '0 0 auto', width: 22, height: 22, borderRadius: 5, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: danger ? 'var(--bad)' : 'var(--muted)', cursor: 'pointer' }}>{children}</span>
)
const AddLink = ({ onClick, children }) => (
  <span onClick={onClick} style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', alignSelf: 'flex-start' }} className="v2-navlink">{children}</span>
)
const RemoveLink = ({ onClick, children = 'Remove' }) => (
  <span onClick={onClick} style={{ fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer', whiteSpace: 'nowrap' }} className="v2-hover-bad">{children}</span>
)
const DashedAdd = ({ onClick, children, big }) => (
  <div onClick={onClick} className="v2-dashadd" style={{ height: big ? 32 : 28, border: '1px dashed var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: big ? 12 : 11.5, fontWeight: big ? 500 : 400, color: 'var(--accent)', cursor: 'pointer' }}>{children}</div>
)
const EmptyState = ({ what }) => (
  <div style={{ padding: '16px 12px', border: '1px dashed var(--edge)', borderRadius: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
    <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>No {what} yet</span>
    <span style={{ fontSize: 11.5, color: 'var(--muted)', textAlign: 'center' }}>Empty sections are skipped in the PDF — nothing prints until you add one.</span>
  </div>
)
const MenuHead = ({ children }) => <div style={{ padding: '4px 11px 3px', fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{children}</div>
const MenuItem = ({ icon, label, hint, onClick }) => (
  <div onClick={onClick} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
    <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>{icon}</span>
    <span style={{ flex: 1, minWidth: 0 }}>{label}</span>
    {hint && <span style={{ flex: '0 0 auto', fontSize: 10.5, color: 'var(--faint)' }}>{hint}</span>}
  </div>
)

export default function ResumeEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()
  const [doc, setDoc] = useState(null)
  const [data, setData] = useState(null)
  const [templates, setTemplates] = useState([])
  const [template, setTemplate] = useState('')
  const [format, setFormat] = useState('letter')
  const [savedAt, setSavedAt] = useState(null)
  const [saving, setSaving] = useState(false)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [open, setOpen] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem('jobnavigator_v2_resume_sections')); if (Array.isArray(s)) return new Set(s) } catch { /* ignore */ }
    return new Set(['Experience'])
  })
  const [tplOpen, setTplOpen] = useState(false)
  const [fmtOpen, setFmtOpen] = useState(false)
  const [tailorOpen, setTailorOpen] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [baseData, setBaseData] = useState(null)   // parent json_data (for diff + inline marks)
  const [jobData, setJobData] = useState(null)     // the copy's job (cv_scores, status)
  const [tracers, setTracers] = useState([])
  const [coverExists, setCoverExists] = useState(false)
  const [baseCopyCount, setBaseCopyCount] = useState(null)
  const [scoring, setScoring] = useState(false)
  const [headMenu, setHeadMenu] = useState(false)
  const [toasts, setToasts] = useState([])
  const saveTimer = useRef(null)
  const pdfTimer = useRef(null)
  const pendingRef = useRef([])   // [{baseId, jobId, company, since}]

  const isCopy = doc && !doc.is_base

  const pushToast = useCallback((t) => {
    const tid = `${Date.now()}-${Math.random()}`
    setToasts((p) => [...p, { id: tid, ...t }])
    if (t.ttl !== 0) setTimeout(() => setToasts((p) => p.filter((x) => x.id !== tid)), t.ttl || 5000)
    return tid
  }, [])

  // background tailoring: after POST, watch for the new copy (parent+job, updated after start)
  useEffect(() => {
    const iv = setInterval(async () => {
      if (!pendingRef.current.length) return
      try {
        const { data } = await api.get('/resumes', { params: { is_base: false } })
        const list = data || []
        pendingRef.current = pendingRef.current.filter((p) => {
          const hit = list.find((r) => String(r.parent_id) === String(p.baseId) && String(r.job_id) === String(p.jobId) && new Date(r.updated_at).getTime() >= p.since - 1000)
          if (hit) { pushToast({ msg: `Tailored copy for ${p.company} is ready.`, action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${hit.id}`) }); return false }
          if (Date.now() - p.since > 120000) return false   // give up after 2m
          return true
        })
      } catch {}
    }, 3000)
    return () => clearInterval(iv)
  }, [pushToast, navigate])

  const runTailor = useCallback(async ({ baseId, jobId, jobDescription, company }) => {
    setTailorOpen(false)
    try {
      await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: jobId || undefined, job_description: jobDescription || undefined })
      if (jobId) pendingRef.current.push({ baseId, jobId, company: company || 'the job', since: Date.now() })
      pushToast({ msg: `Tailoring ${company ? 'for ' + company : ''}… runs in the background.` })
    } catch (e) {
      if (e.response?.status === 409) pushToast({ msg: 'Already tailoring for that job.' })
      else pushToast({ msg: e.response?.data?.detail || 'Tailoring failed to start.' })
    }
  }, [pushToast])

  useEffect(() => {
    let alive = true
    api.get(`/resumes/${id}`).then(({ data: d }) => {
      if (!alive) return
      setDoc(d); setData(d.json_data || EMPTY); setTemplate(d.template || ''); setFormat(d.page_format || 'letter'); setSavedAt(d.updated_at)
    }).catch(() => navigate('/v2/resumes'))
    api.get('/resumes/templates').then(({ data }) => setTemplates(data || [])).catch(() => {})
    return () => { alive = false }
  }, [id, navigate])

  // parent base data for the diff/marks (tailored copies only); copy count for a base
  useEffect(() => {
    let alive = true
    if (doc && doc.is_base) {
      setBaseData(null)
      api.get('/resumes', { params: { is_base: false } }).then(({ data }) => { if (alive) setBaseCopyCount((data || []).filter((r) => String(r.parent_id) === String(doc.id)).length) }).catch(() => {})
    } else if (doc && doc.parent_id) {
      api.get(`/resumes/${doc.parent_id}`).then(({ data: p }) => { if (alive) setBaseData(p.json_data || null) }).catch(() => {})
    } else { setBaseData(null) }
    return () => { alive = false }
  }, [doc])

  const changes = useMemo(() => (isCopy && baseData && data ? computeChanges(baseData, data) : []), [isCopy, baseData, data])
  const changedSections = useMemo(() => {
    const s = new Set()
    changes.forEach((c) => { if (c.key === 'summary') s.add('Summary'); else if (c.key.startsWith('exp')) s.add('Experience'); else if (c.key.startsWith('sk:')) s.add('Skills') })
    return s
  }, [changes])

  // copy job context: score/delta, tracers, cover-letter existence
  const loadJobCtx = useCallback(() => {
    if (!doc || doc.is_base || !doc.job_id) return
    api.get(`/jobs/${doc.job_id}`).then(({ data: j }) => setJobData(j)).catch(() => {})
    api.get(`/cover-letters`, { params: { job_id: doc.job_id } }).then(({ data }) => setCoverExists((data || []).length > 0)).catch(() => {})
  }, [doc])
  useEffect(() => {
    if (!doc || doc.is_base) { setJobData(null); setTracers([]); return }
    loadJobCtx()
    api.get(`/resumes/${id}/tracer-stats`).then(({ data }) => setTracers(data || [])).catch(() => {})
  }, [doc, id, loadJobCtx])

  const scores = useMemo(() => {
    const cs = jobData?.cv_scores || {}
    const tailored = typeof cs['Tailored'] === 'number' ? Math.round(cs['Tailored']) : null
    const others = Object.entries(cs).filter(([k, v]) => k !== 'Tailored' && typeof v === 'number').map(([, v]) => v)
    const base = others.length ? Math.round(Math.max(...others)) : null
    return { tailored, base, delta: tailored != null && base != null ? tailored - base : null }
  }, [jobData])

  const runScore = useCallback(async (depth) => {
    if (!doc?.job_id) { pushToast({ msg: 'This copy isn’t linked to a job to score against.' }); return }
    setHeadMenu(false); setScoring(true)
    try {
      await api.post(`/resumes/${id}/score-check`, { depth })
      pushToast({ msg: `Scoring (${depth}) — runs in the background.` })
      // poll until the score lands (or ~60s)
      const t0 = Date.now()
      const iv = setInterval(async () => {
        try {
          const { data: j } = await api.get(`/jobs/${doc.job_id}`)
          const sc = j?.cv_scores?.['Tailored']
          if (typeof sc === 'number') { setJobData(j); setScoring(false); clearInterval(iv); pushToast({ msg: `Scored: ${Math.round(sc)}${scores.base != null ? ` (${sc - scores.base >= 0 ? '+' : ''}${Math.round(sc - scores.base)} vs base)` : ''}` }) }
          else if (Date.now() - t0 > 60000) { setScoring(false); clearInterval(iv) }
        } catch {}
      }, 3000)
    } catch (e) { setScoring(false); pushToast({ msg: e.response?.status === 409 ? 'Already scoring this copy.' : (e.response?.data?.detail || 'Scoring failed to start.') }) }
  }, [doc, id, pushToast, scores.base])

  const markApplied = useCallback(async () => {
    if (!doc?.job_id) return
    setHeadMenu(false)
    try { await api.patch(`/jobs/${doc.job_id}`, { status: 'applied' }); loadJobCtx(); pushToast({ msg: 'Marked applied.' }) } catch { pushToast({ msg: 'Could not mark applied.' }) }
  }, [doc, loadJobCtx, pushToast])

  const deleteResume = useCallback(async () => {
    if (!window.confirm(`Delete “${doc.name}”?${doc.is_base ? ' Its tailored copies will be removed too.' : ''}`)) return
    try { await api.delete(`/resumes/${id}`); navigate('/v2/resumes') } catch { pushToast({ msg: 'Delete failed.' }) }
  }, [doc, id, navigate, pushToast])

  const goCover = () => { setHeadMenu(false); window.location.href = `/cover-letters?resume=${id}${doc.job_id ? `&job=${doc.job_id}` : ''}` }

  // the "one next step" stage for a tailored copy
  const stage = useMemo(() => {
    if (!isCopy) return null
    if (changes.length) return { label: `Review ${changes.length} change${changes.length === 1 ? '' : 's'}`, act: () => setReviewOpen(true) }
    if (scores.tailored == null) return { label: scoring ? 'Scoring…' : 'Score the result', act: () => runScore('full') }
    if (!coverExists) return { label: '✉ Write cover letter', act: goCover }
    if (jobData?.status !== 'applied') return { label: 'Mark applied', act: markApplied }
    return { label: 'Applied ✓', act: null, done: true }
  }, [isCopy, changes.length, scores.tailored, scoring, coverExists, jobData, runScore, markApplied]) // eslint-disable-line

  // debounced persist
  const persist = useCallback((patch) => {
    setSaving(true)
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try { await api.patch(`/resumes/${id}`, patch); setSavedAt(new Date().toISOString()) } catch (e) { console.error(e) }
      setSaving(false)
    }, 500)
  }, [id])
  const onData = useCallback((next) => { setData(next); persist({ json_data: next }) }, [persist])
  const pickTemplate = (t) => { setTemplate(t); setTplOpen(false); persist({ template: t }) }
  const pickFormat = (f) => { setFormat(f); setFmtOpen(false); persist({ page_format: f }) }

  // live PDF preview — one request at a time (abort the in-flight render before the
  // next so overlapping edits don't hammer /pdf or race the tracer-link writer)
  const pdfAbort = useRef(null)
  useEffect(() => {
    if (!doc) return
    clearTimeout(pdfTimer.current)
    pdfTimer.current = setTimeout(async () => {
      if (pdfAbort.current) pdfAbort.current.abort()
      const ac = new AbortController(); pdfAbort.current = ac
      try {
        const r = await api.get(`/resumes/${id}/pdf`, { responseType: 'arraybuffer', params: { template, format }, signal: ac.signal })
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
        setPdfUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return url })
      } catch (e) { if (e.code !== 'ERR_CANCELED' && e.name !== 'CanceledError') console.error('pdf', e) }
    }, 800)
    return () => clearTimeout(pdfTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, template, format, doc, id])
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl) }, [pdfUrl])

  // apply the decline-based review: declined modified/added → revert to base; kept
  // suggested bullets → append; then clear all suggested_bullets. One save.
  const applyReview = useCallback((declined) => {
    const d = JSON.parse(JSON.stringify(data || EMPTY))
    changes.forEach((c) => {
      const off = !!declined[c.key]
      if (c.kind === 'modified' && off) {
        const keys = c.path.split('.'); let o = d
        for (let i = 0; i < keys.length - 1; i++) o = o?.[keys[i]]
        if (o) o[keys[keys.length - 1]] = c.baseText
      } else if (c.kind === 'added' && off) {
        // remove the added copy bullet (match by text within its experience)
        d.experience?.forEach((e) => { if (e.bullets) e.bullets = e.bullets.filter((b) => b !== c.text) })
      } else if (c.kind === 'suggested' && !off) {
        const e = d.experience?.[c.expIdx]; if (e) { e.bullets = e.bullets || []; e.bullets.push(c.text) }
      }
    })
    ;(d.experience || []).forEach((e) => { delete e.suggested_bullets })
    onData(d)
    setReviewOpen(false)
    pushToast({ msg: 'Review applied — declined changes restored to base.' })
  }, [changes, data, onData, pushToast])

  // ── json_data mutation (mirrors v1 ResumeContentEditor) ────────────────────
  const mutate = (fn) => { const d = JSON.parse(JSON.stringify(data || EMPTY)); fn(d); onData(d) }
  const setField = (path, val) => {
    const keys = String(path).split('.'); if (keys.some((k) => DANGEROUS.has(k))) return
    mutate((d) => { let o = d; for (let i = 0; i < keys.length - 1; i++) { if (o == null || typeof o !== 'object') return; o = o[keys[i]] } if (o && typeof o === 'object') o[keys[keys.length - 1]] = val })
  }
  const toggle = (name) => setOpen((p) => {
    const n = new Set(p); n.has(name) ? n.delete(name) : n.add(name)
    try { localStorage.setItem('jobnavigator_v2_resume_sections', JSON.stringify([...n])) } catch { /* ignore */ }
    return n
  })

  const pdfDownloadUrl = useMemo(() => {
    const base = (api.defaults.baseURL || '').replace(/\/api$/, '')
    return `${base}/api/resumes/${id}/pdf?template=${encodeURIComponent(template)}&format=${encodeURIComponent(format)}`
  }, [id, template, format])

  if (!doc || !data) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>

  const counts = { Experience: data.experience?.length || 0, Skills: Object.keys(data.skills || {}).length, Education: data.education?.length || 0, Projects: data.projects?.length || 0, Publications: data.publications?.length || 0 }
  const tplLabel = templates.find((t) => t.id === template)?.name || template || 'Template'

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* top bar */}
      <div style={{ flex: '0 0 auto', padding: '10px 24px', background: 'var(--surface)', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span onClick={() => navigate('/v2/resumes')} style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer' }} className="v2-navlink">‹ Résumés</span>
        <span style={{ color: 'var(--line)' }}>|</span>
        <span style={{ fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: isCopy ? 'var(--accent-soft)' : 'var(--surface-2)', color: isCopy ? 'var(--accent)' : 'var(--muted)' }}>{isCopy ? 'tailored' : 'base'}</span>
        <span title={doc.name} style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 460 }}>{doc.name}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--muted)' }}>{saving ? 'Saving…' : savedAt ? `saved ${timeAgo(savedAt)} · autosaves` : 'autosaves on blur'}</span>
      </div>

      {/* sub-band: base vs copy */}
      {isCopy ? (
        <div style={{ flex: '0 0 auto', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)', padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 13 }}>
          {scores.tailored != null && (
            <div style={{ position: 'relative', width: 34, height: 34, flex: '0 0 34px' }}>
              <svg viewBox="0 0 78 78" style={{ width: 34, height: 34 }}>
                <circle cx="39" cy="39" r="35" fill="none" stroke="var(--track)" strokeWidth="6" />
                <circle cx="39" cy="39" r="35" fill="none" stroke={scoreColor(scores.tailored)} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${(219.9 * scores.tailored / 100).toFixed(1)} 219.9`} transform="rotate(-90 39 39)" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 13.5, color: scoreColor(scores.tailored), transform: 'translateY(1px)' }}>{scores.tailored}</div>
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0, lineHeight: 1.4 }}>
              Tailored{jobData?.company ? <> for <span style={{ color: 'var(--text)' }}>{jobData.company}{jobData.title ? ` — ${jobData.title}` : ''}</span></> : ' copy'}
              {doc.parent_id && (() => {
                const baseName = (doc.name || '').split('→')[0].trim() || 'base'
                const dfg = scores.delta == null ? undefined : (scores.delta >= 0 ? 'var(--accent)' : 'var(--warn)')
                return (
                  <>
                    <span style={{ color: 'var(--line)' }}>{'  │  '}</span>
                    <span onClick={() => navigate(`/v2/resumes/${doc.parent_id}`)} title={`Open the ${baseName} base résumé this was tailored from`} style={{ cursor: 'pointer', position: 'relative', top: '1px' }} className="v2-navlink">
                      {scores.delta != null && <span style={{ color: dfg, fontWeight: 600 }}>{scores.delta >= 0 ? '+' : ''}{scores.delta} </span>}
                      <span style={{ color: 'var(--accent)' }}>based on {baseName} ↗</span>
                    </span>
                  </>
                )
              })()}
            </div>
            <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {(changes.length ? `${changes.length} reviewable change${changes.length === 1 ? '' : 's'}` : scores.tailored == null ? 'not scored yet' : 'ready')}
              {tracers.length > 0 && <> · tracers: {tracers.map((t) => `${t.source_label} ${t.clicks}`).join(' · ')}</>}
            </span>
          </div>
          {stage && (
            <div onClick={() => !stage.done && stage.act && stage.act()} title={stage.done ? 'Pipeline complete' : 'The one next step'} style={{ flex: '0 0 auto', height: 36, padding: '0 19px', borderRadius: 99, background: stage.done ? 'var(--accent-soft)' : 'var(--accent)', color: stage.done ? 'var(--accent)' : 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 500, cursor: stage.done ? 'default' : 'pointer' }}>
              {scoring && <span className="v2-spin" style={{ width: 11, height: 11, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
              {stage.label}
            </div>
          )}
          <div style={{ position: 'relative', flex: '0 0 auto' }}>
            <div onClick={() => setHeadMenu((v) => !v)} className="v2-act" style={{ width: 36, height: 36, border: `1px solid ${headMenu ? 'var(--accent)' : 'var(--edge)'}`, background: headMenu ? 'var(--accent-soft)' : 'transparent', color: headMenu ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, cursor: 'pointer' }}>⋯</div>
            {headMenu && (
              <>
                <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 5, zIndex: 45, width: 244, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5, display: 'flex', flexDirection: 'column' }}>
                  <MenuHead>This copy</MenuHead>
                  <MenuItem icon="✦" label="Re-tailor…" hint="replaces copy" onClick={() => { setHeadMenu(false); setTailorOpen(true) }} />
                  <MenuItem icon="◎" label="Score again" hint="quick / full" onClick={() => runScore('full')} />
                  {changes.length > 0 && <MenuItem icon="≋" label="Review changes" hint={`${changes.length} applied`} onClick={() => { setHeadMenu(false); setReviewOpen(true) }} />}
                  <div style={{ height: 1, margin: '4px 8px', background: 'var(--line-soft)' }} />
                  <MenuHead>Job</MenuHead>
                  <MenuItem icon="✉" label="Cover letter" hint="c" onClick={goCover} />
                  {doc.job_id && <MenuItem icon="↗" label="Open in feed" hint="e" onClick={() => navigate(`/v2/feed?job=${doc.job_id}`)} />}
                  {doc.job_id && <MenuItem icon="✓" label="Mark applied" hint="a" onClick={markApplied} />}
                  <div style={{ height: 1, margin: '4px 8px', background: 'var(--line-soft)' }} />
                  <div onClick={deleteResume} className="v2-hover-bad" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--bad)', cursor: 'pointer' }}><span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11 }}>✕</span>Delete copy</div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div style={{ flex: '0 0 auto', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)', padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 13, fontSize: 12.5, color: 'var(--text-2)' }}>
          <span>Base résumé · {baseCopyCount != null && <><span style={{ color: 'var(--text)', fontWeight: 500 }}>{baseCopyCount} tailored cop{baseCopyCount === 1 ? 'y' : 'ies'}</span> · </>}editing here changes future tailoring only</span>
          <div onClick={() => setTailorOpen(true)} style={{ marginLeft: 'auto', height: 36, padding: '0 19px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>✦ Tailor for a job…</div>
        </div>
      )}

      {/* two-pane */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* left: sections */}
        <section className="v2-scroll" style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '14px 20px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {SECTION_ORDER.map((name) => {
            const isOpen = open.has(name)
            return (
              <div key={name} style={{ border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
                <div onClick={() => toggle(name)} className="v2-hover-accent" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', cursor: 'pointer', borderRadius: 9 }}>
                  <span style={{ color: 'var(--muted)', fontSize: 10 }}>{isOpen ? '⌄' : '›'}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                  {counts[name] != null && <span style={{ fontSize: 11.5, color: 'var(--muted)', position: 'relative', top: '0.5px' }}>({counts[name]})</span>}
                  {changedSections.has(name) && <span title="Contains unreviewed tailoring changes" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--warn)' }}>● changed by tailoring</span>}
                </div>
                {isOpen && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
                    {name === 'Header' && <HeaderEditor data={data} setField={setField} mutate={mutate} tracers={tracers} />}
                    {name === 'Summary' && <SummaryEditor data={data} setField={setField} baseSummary={baseData?.summary} />}
                    {name === 'Experience' && <ExperienceEditor data={data} setField={setField} mutate={mutate} baseExp={baseData?.experience} />}
                    {name === 'Skills' && <SkillsEditor data={data} setField={setField} mutate={mutate} baseSkills={baseData?.skills} />}
                    {name === 'Education' && <EducationEditor data={data} setField={setField} mutate={mutate} />}
                    {name === 'Projects' && <ProjectsEditor data={data} setField={setField} mutate={mutate} />}
                    {name === 'Publications' && <PublicationsEditor data={data} setField={setField} mutate={mutate} />}
                  </div>
                )}
              </div>
            )
          })}
        </section>

        {/* right: PDF preview */}
        <section style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface-2)', minHeight: 0 }}>
          <div style={{ flex: '0 0 auto', padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--line)' }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>PDF preview</span>
            {/* template picker */}
            <div style={{ position: 'relative' }}>
              <span onClick={() => { setTplOpen((v) => !v); setFmtOpen(false) }} title="Résumé template" className="v2-act" style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}><span style={{ color: 'var(--muted)' }}>Template</span><span style={{ color: 'var(--text)' }}>{tplLabel}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span></span>
              {tplOpen && (
                <>
                  <div onClick={() => setTplOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 20 }} />
                  <div className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 5, zIndex: 21, width: 190, maxHeight: 300, overflow: 'auto', background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 9, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                    {templates.map((t) => <div key={t.id} onClick={() => pickTemplate(t.id)} className="v2-menuitem" style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: t.id === template ? 'var(--accent)' : 'var(--text-2)', background: t.id === template ? 'var(--accent-soft)' : 'transparent' }}>{t.name}</div>)}
                  </div>
                </>
              )}
            </div>
            {/* format */}
            <div style={{ position: 'relative' }}>
              <span onClick={() => { setFmtOpen((v) => !v); setTplOpen(false) }} title="Paper size" className="v2-act" style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}><span style={{ color: 'var(--muted)' }}>Paper</span><span style={{ color: 'var(--text)' }}>{format === 'a4' ? 'A4' : 'US Letter'}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span></span>
              {fmtOpen && (
                <>
                  <div onClick={() => setFmtOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 20 }} />
                  <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 5, zIndex: 21, width: 130, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 9, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
                    {[['letter', 'US Letter'], ['a4', 'A4']].map(([v, l]) => <div key={v} onClick={() => pickFormat(v)} className="v2-menuitem" style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: v === format ? 'var(--accent)' : 'var(--text-2)', background: v === format ? 'var(--accent-soft)' : 'transparent' }}>{l}</div>)}
                  </div>
                </>
              )}
            </div>
            <a href={pdfDownloadUrl} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 'auto', height: 29, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 500 }}>↓ Download PDF</a>
          </div>
          <div style={{ flex: 1, minHeight: 0, position: 'relative', background: 'var(--surface-2)' }}>
            {pdfUrl && <iframe title="pdf" src={`${pdfUrl}#view=FitH`} style={{ width: '100%', height: '100%', border: 'none' }} />}
          </div>
        </section>
      </div>

      {tailorOpen && <TailorModal doc={doc} onClose={() => setTailorOpen(false)} onRun={runTailor} />}
      {reviewOpen && <ReviewModal changes={changes} onClose={() => setReviewOpen(false)} onApply={applyReview} />}

      {/* toasts */}
      <div style={{ position: 'fixed', right: 20, bottom: 20, zIndex: 80, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
        {toasts.map((t) => (
          <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px', background: 'var(--rail)', borderRadius: 10, boxShadow: '0 10px 30px rgba(0,0,0,.28)', maxWidth: 360 }}>
            <span style={{ fontSize: 12.5, lineHeight: 1.45, color: 'var(--rail-ink)' }}>{t.msg}</span>
            {t.action && <span onClick={() => { t.onAction?.(); setToasts((p) => p.filter((x) => x.id !== t.id)) }} style={{ flex: '0 0 auto', fontSize: 12, fontWeight: 600, color: 'var(--rail-accent)', cursor: 'pointer' }}>{t.action}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── tailor modal (job picker + freeform + persona) ───────────────────────────
function TailorModal({ doc, onClose, onRun }) {
  const isCopy = !doc.is_base
  const baseId = isCopy ? (doc.parent_id || 'persona') : doc.id
  const [jobs, setJobs] = useState([])
  const [existing, setExisting] = useState(new Set())
  const [q, setQ] = useState('')
  const [pick, setPick] = useState(isCopy && doc.job_id ? doc.job_id : null)
  const [jd, setJd] = useState('')
  const [personaBase, setPersonaBase] = useState(baseId === 'persona')

  useEffect(() => {
    api.get('/jobs', { params: { status: 'saved,applied,new', sort_by: 'date', limit: 60 } })
      .then(({ data }) => setJobs((data.jobs || data.items || data || []))).catch(() => {})
    api.get('/resumes', { params: { is_base: false } })
      .then(({ data }) => setExisting(new Set((data || []).filter((r) => String(r.parent_id) === String(baseId)).map((r) => String(r.job_id))))).catch(() => {})
  }, [baseId])

  const baseName = (r) => (typeof r === 'string' ? r : r?.name)
  const jobScore = (j) => {
    const cs = j.cv_scores || {}
    for (const k of [doc.name, 'Tailored']) if (typeof cs[k] === 'number') return Math.round(cs[k])
    const nums = Object.values(cs).filter((v) => typeof v === 'number')
    return nums.length ? Math.round(Math.max(...nums)) : null
  }
  const t = q.trim().toLowerCase()
  const list = jobs.filter((j) => !t || `${j.title} ${j.company}`.toLowerCase().includes(t))
    .sort((a, b) => (['saved', 'applied'].includes(b.status) ? 1 : 0) - (['saved', 'applied'].includes(a.status) ? 1 : 0))

  const canRun = personaBase ? !!(pick || jd.trim()) : !!(pick || jd.trim())
  const chosen = jobs.find((j) => String(j.id) === String(pick))
  const run = () => onRun({ baseId: personaBase ? 'persona' : baseId, jobId: pick, jobDescription: pick ? '' : jd.trim(), company: chosen?.company })

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 480, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>{isCopy ? 'Re-tailor this copy' : `Tailor ${doc.name} for a job`}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Changes land automatically — you review and decline afterwards.</span>
        </div>
        <div className="v2-scroll" style={{ padding: '14px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 460, overflow: 'auto' }}>
          {!isCopy && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>
              <input type="checkbox" checked={personaBase} onChange={(e) => setPersonaBase(e.target.checked)} />
              Tailor from Persona instead of this base
            </label>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Pick a job · saved and scored first</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search jobs…" style={{ height: 32, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 8, background: 'var(--surface-2)', fontSize: 12.5, color: 'var(--text)', outline: 'none', fontFamily: 'var(--sans)' }} />
            {list.slice(0, 40).map((j) => {
              const on = String(pick) === String(j.id), sc = jobScore(j), has = existing.has(String(j.id))
              return (
                <div key={j.id} onClick={() => { setPick(j.id); setJd('') }} className="v2-act" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 8, cursor: 'pointer' }}>
                  <span style={{ flex: '0 0 auto', width: 14, height: 14, borderRadius: 99, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 99, background: on ? 'var(--accent)' : 'transparent' }} /></span>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.title}</span>
                    <span style={{ fontSize: 10.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j.company} · {j.status}</span>
                  </div>
                  {sc != null && <span title="This base's fit on that job" style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--accent)' }}>{sc}</span>}
                  {has && <span title="A tailored copy already exists — tailoring again adds another" style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--warn)' }}>✦ exists</span>}
                </div>
              )
            })}
            {list.length === 0 && <div style={{ padding: 12, border: '1px dashed var(--edge)', borderRadius: 8, fontSize: 11.5, color: 'var(--muted)' }}>No jobs match — paste a description below instead.</div>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>…or a freeform job description</span>
            <textarea value={jd} onChange={(e) => { setJd(e.target.value); if (e.target.value.trim()) setPick(null) }} placeholder="Paste any JD — the copy won't be linked to a feed job" rows={3} style={{ padding: '8px 10px', border: '1px dashed var(--edge)', borderRadius: 8, background: 'var(--surface-2)', fontSize: 12, color: 'var(--text)', outline: 'none', fontFamily: 'var(--sans)', resize: 'vertical' }} />
          </div>
        </div>
        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Runs in the background</span>
          <div onClick={onClose} className="v2-act" style={{ marginLeft: 'auto', height: 33, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
          <div onClick={() => canRun && run()} style={{ height: 33, padding: '0 17px', borderRadius: 99, background: canRun ? 'var(--accent)' : 'var(--edge)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: canRun ? 'pointer' : 'default' }}>✦ Tailor</div>
        </div>
      </div>
    </div>
  )
}

// ── review modal (decline-based) ─────────────────────────────────────────────
function ReviewModal({ changes, onClose, onApply }) {
  const [declined, setDeclined] = useState({})
  const n = Object.values(declined).filter(Boolean).length
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(920px, 94vw)', height: 'min(760px, 90vh)', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Tailoring changes — already applied</span>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>These landed automatically. Decline any you don't want; the base text comes back.</span>
          </div>
          <div onClick={onClose} className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 11, minHeight: 0 }}>
          {changes.length === 0 && <div style={{ padding: 20, fontSize: 12.5, color: 'var(--muted)' }}>No tailoring changes to review.</div>}
          {changes.map((c) => {
            const off = !!declined[c.key]
            const added = c.kind === 'modified' ? (off ? c.removed : c.added) : c.added
            const removed = c.kind === 'modified' ? (off ? c.added : c.removed) : ''
            return (
              <div key={c.key} style={{ border: `1px solid ${off ? 'var(--line)' : 'var(--change-soft)'}`, borderRadius: 9, padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: 7, background: off ? 'var(--bg)' : 'var(--change-bg)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{c.where}</span>
                  <span style={{ fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', padding: '1px 7px', borderRadius: 99, background: off ? 'var(--surface-2)' : 'var(--accent-soft)', color: off ? 'var(--muted)' : 'var(--accent)' }}>{off ? 'declined' : 'applied'}</span>
                  <div onClick={() => setDeclined((p) => ({ ...p, [c.key]: !p[c.key] }))} style={{ marginLeft: 'auto', height: 24, padding: '0 12px', borderRadius: 99, border: `1px solid ${off ? 'var(--accent)' : 'var(--warn)'}`, color: off ? 'var(--accent)' : 'var(--warn)', fontSize: 11, fontWeight: 500, display: 'flex', alignItems: 'center', cursor: 'pointer' }}>{off ? 'Restore change' : 'Decline ↩'}</div>
                </div>
                <span style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-2)' }}>
                  {c.before}
                  {removed && <span style={{ background: 'var(--bad-soft)', textDecoration: 'line-through', opacity: 0.75, borderRadius: 3, padding: '0 3px' }}>{removed}</span>}
                  {added && <span style={{ background: off ? 'var(--surface-2)' : 'var(--change-soft)', borderRadius: 3, padding: '0 3px' }}>{added || '(base text restored)'}</span>}
                  {c.after}
                </span>
              </div>
            )
          })}
        </div>
        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{n ? `${n} declined — base text restored · the rest stay` : `All ${changes.length} change${changes.length === 1 ? '' : 's'} live · decline any to restore the base text`}</span>
          <div onClick={() => onApply(declined)} style={{ marginLeft: 'auto', height: 33, padding: '0 17px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>Done reviewing</div>
        </div>
      </div>
    </div>
  )
}

// ── section editors (v2-styled, same handlers as v1) ─────────────────────────
const UPPER = { fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }
const cellInput = { width: '100%', height: 29, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, outline: 'none', fontFamily: 'var(--sans)' }
const normUrl = (u) => (u || '').replace(/^https?:\/\//, '').replace(/\/$/, '').toLowerCase()

function HeaderEditor({ data, setField, mutate, tracers }) {
  const items = data.header?.contact_items || []
  const move = (i, dir) => mutate((d) => { const a = d.header.contact_items; const j = i + dir; if (j < 0 || j >= a.length) return;[a[i], a[j]] = [a[j], a[i]] })
  const arrows = (i) => (
    <span style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1, color: 'var(--faint)', fontSize: 8, cursor: 'pointer' }}>
      <span onClick={() => move(i, -1)} className="v2-navlink">▲</span><span onClick={() => move(i, 1)} className="v2-navlink">▼</span>
    </span>
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 10 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <span style={UPPER}>Full name</span>
        <input value={data.header?.name || ''} onChange={(e) => setField('header.name', e.target.value)} style={{ ...cellInput, height: 32, fontSize: 13 }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={UPPER}>Contact items</span>
          <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--faint)' }}>text · link · stub</span>
        </div>
        {items.map((it, i) => {
          const showStub = it.url && !it.url.startsWith('mailto:')
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {arrows(i)}
              <input value={it.text || ''} onChange={(e) => setField(`header.contact_items.${i}.text`, e.target.value)} placeholder="Display text" style={{ ...cellInput, flex: '0 0 170px', minWidth: 0 }} />
              <input value={it.url || ''} onChange={(e) => setField(`header.contact_items.${i}.url`, e.target.value)} placeholder="URL (optional)" style={{ ...cellInput, flex: 1, minWidth: 0, fontSize: 11.5, color: 'var(--accent)' }} />
              {showStub && <input value={it.stub || ''} onChange={(e) => setField(`header.contact_items.${i}.stub`, e.target.value)} placeholder="id" title="Short stub for the tracer link id (e.g. l, w, gh)" style={{ ...cellInput, flex: '0 0 34px', padding: '0 6px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 11 }} />}
              <span onClick={() => mutate((d) => d.header.contact_items.splice(i, 1))} title="Remove" className="v2-hover-bad" style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: 11, cursor: 'pointer' }}>✕</span>
            </div>
          )
        })}
        <DashedAdd onClick={() => mutate((d) => { d.header = d.header || { contact_items: [] }; (d.header.contact_items = d.header.contact_items || []).push({ text: '', url: '' }) })}>+ Add contact item</DashedAdd>
      </div>
    </div>
  )
}
function ExperienceEditor({ data, setField, mutate, baseExp }) {
  const exp = data.experience || []
  const [open, setOpen] = useState(() => new Set([0]))   // first entry open by default
  const setBullet = (i, bi, v) => mutate((d) => { d.experience[i].bullets[bi] = v })
  const bulletMark = (i, bi, txt) => {
    if (!baseExp) return null
    const bb = baseExp[i]?.bullets || []
    if (bi >= bb.length) return { kind: 'added', label: 'Added by tailoring' }
    if (bb[bi] !== txt) return { kind: 'changed', label: 'Changed by tailoring', base: bb[bi] }
    return null
  }
  const entryChanged = (e, i) => (e.bullets || []).some((b, bi) => bulletMark(i, bi, b)) || (e.suggested_bullets || []).length > 0
  const toggle = (i) => setOpen((p) => { const n = new Set(p); n.has(i) ? n.delete(i) : n.add(i); return n })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {exp.map((e, i) => {
        const ch = entryChanged(e, i), isOpen = open.has(i), nb = (e.bullets || []).length
        return (
          <div key={i} style={{ border: `1px solid ${ch ? 'var(--change-soft)' : 'var(--line)'}`, borderRadius: 8, background: ch ? 'var(--change-bg)' : 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
            <div onClick={() => toggle(i)} className="v2-hover-accent" style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '9px 11px', cursor: 'pointer', borderRadius: 8 }}>
              <span style={{ flex: '0 0 auto', color: 'var(--muted)', fontSize: 10 }}>{isOpen ? '⌄' : '›'}</span>
              <span style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.title || 'Untitled role'}</span>
              <span style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.company}</span>
              <span style={{ flex: '0 0 auto', marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{e.date}</span>
              <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>{nb} bullet{nb === 1 ? '' : 's'}</span>
              {ch && <span title="Contains unreviewed tailoring changes" style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--warn)' }}>●</span>}
            </div>
            {isOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '2px 11px 11px', borderTop: '1px solid var(--line-soft)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7, paddingTop: 9 }}>
                  <Field label="Company" value={e.company} onChange={(v) => setField(`experience.${i}.company`, v)} />
                  <Field label="Title" value={e.title} onChange={(v) => setField(`experience.${i}.title`, v)} />
                  <Field label="Location" value={e.location} onChange={(v) => setField(`experience.${i}.location`, v)} />
                  <Field label="Date" value={e.date} onChange={(v) => setField(`experience.${i}.date`, v)} placeholder="Jan 2022 – Present" mono />
                </div>
                <Field label="Description" value={e.description} onChange={(v) => setField(`experience.${i}.description`, v)} placeholder="Optional role description" />
                {(e.bullets || []).map((b, bi) => {
                  const m = bulletMark(i, bi, b)
                  return (
                    <div key={bi} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: `1px solid ${m ? 'var(--change-soft)' : 'var(--line)'}`, background: m ? 'var(--change-bg)' : 'var(--surface)', borderRadius: 6 }}>
                      <span title={m?.label || ''} style={{ flex: '0 0 auto', color: m ? 'var(--accent)' : 'var(--muted)', fontSize: 11, lineHeight: 1.5 }}>{m ? '✦' : '—'}</span>
                      <BulletText value={b} onChange={(v) => setBullet(i, bi, v)} />
                      {m?.kind === 'changed' && <span onClick={() => setBullet(i, bi, m.base)} title="Decline this tailoring change — restores the base text" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500, lineHeight: 1.5 }}>↩</span>}
                      <span onClick={() => mutate((d) => d.experience[i].bullets.splice(bi, 1))} title="Remove" className="v2-hover-bad" style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: 10, cursor: 'pointer', lineHeight: 1.7 }}>✕</span>
                    </div>
                  )
                })}
                {(e.suggested_bullets || []).map((sb, k) => (
                  <div key={`sb${k}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: '1px solid var(--change-soft)', background: 'var(--change-bg)', borderRadius: 6 }}>
                    <span title="Suggested by tailoring — keep on review" style={{ flex: '0 0 auto', color: 'var(--accent)', fontSize: 11, lineHeight: 1.5 }}>✦</span>
                    <span style={{ flex: 1, fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-2)' }}>{sb}</span>
                    <span style={{ flex: '0 0 auto', fontSize: 9.5, color: 'var(--muted)', lineHeight: 1.6 }}>suggested</span>
                  </div>
                ))}
                <div onClick={() => mutate((d) => { d.experience[i].bullets = d.experience[i].bullets || []; d.experience[i].bullets.push('') })} className="v2-act" style={{ height: 28, border: '1px dashed var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer' }}>+ Add bullet</div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.experience.splice(i, 1))}>Remove role</RemoveLink></div>
              </div>
            )}
          </div>
        )
      })}
      {exp.length === 0 && <EmptyState what="experience" />}
      <DashedAdd big onClick={() => mutate((d) => { d.experience = d.experience || []; d.experience.push({ company: '', title: '', location: '', date: '', description: '', bullets: [] }) })}>+ Add experience</DashedAdd>
    </div>
  )
}
// Summary as a marked row (tailoring ✦/— + revert + highlight) with a char-count meta
function SummaryEditor({ data, setField, baseSummary }) {
  const txt = data.summary || ''
  const changed = baseSummary != null && baseSummary !== txt
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 11px', border: `1px solid ${changed ? 'var(--change-soft)' : 'var(--line)'}`, background: changed ? 'var(--change-bg)' : 'var(--surface)', borderRadius: 6 }}>
        <span title={changed ? 'Changed by tailoring' : ''} style={{ flex: '0 0 auto', color: changed ? 'var(--accent)' : 'var(--muted)', fontSize: 11, lineHeight: 1.55 }}>{changed ? '✦' : '—'}</span>
        <BulletText value={txt} onChange={(v) => setField('summary', v)} />
        {changed && <span onClick={() => setField('summary', baseSummary)} title="Decline this tailoring change — restores the base text" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500, lineHeight: 1.55 }}>↩</span>}
      </div>
      <span style={{ fontSize: 10.5, color: 'var(--faint)' }}>{txt.length} characters{txt.length > 600 ? ' · long summaries can push to a second page' : ''}</span>
    </div>
  )
}

// Skills: fixed-width category + value with tailoring ✦/revert/highlight when changed
function SkillsEditor({ data, setField, mutate, baseSkills }) {
  const entries = Object.entries(data.skills || {})
  const rename = (oldK, newK) => { if (oldK === newK || !newK.trim()) return; mutate((d) => { const ns = {}; for (const [k, v] of Object.entries(d.skills)) ns[k === oldK ? newK : k] = v; d.skills = ns }) }
  const move = (k, dir) => mutate((d) => { const e = Object.entries(d.skills); const i = e.findIndex(([x]) => x === k); const j = i + dir; if (i < 0 || j < 0 || j >= e.length) return;[e[i], e[j]] = [e[j], e[i]]; d.skills = Object.fromEntries(e) })
  const arrows = (k) => (
    <span style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1, color: 'var(--faint)', fontSize: 8, cursor: 'pointer' }}>
      <span onClick={() => move(k, -1)} className="v2-navlink">▲</span><span onClick={() => move(k, 1)} className="v2-navlink">▼</span>
    </span>
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 10 }}>
      {entries.map(([k, v]) => {
        const changed = baseSkills != null && (k in baseSkills) && String(baseSkills[k] || '') !== String(v || '')
        const added = baseSkills != null && !(k in baseSkills)
        const marked = changed || added
        return (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {arrows(k)}
            <input defaultValue={k} onBlur={(e) => rename(k, e.target.value)} placeholder="Category" style={{ flex: '0 0 118px', height: 29, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontWeight: 500, outline: 'none', fontFamily: 'var(--sans)' }} />
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6, height: 29, padding: '0 9px', border: `1px solid ${marked ? 'var(--change-soft)' : 'var(--edge)'}`, background: marked ? 'var(--change-bg)' : 'var(--surface-2)', borderRadius: 6 }}>
              {marked && <span title={added ? 'Added by tailoring' : 'Changed by tailoring'} style={{ flex: '0 0 auto', color: 'var(--accent)', fontSize: 10 }}>✦</span>}
              <input value={v} onChange={(e) => setField(`skills.${k}`, e.target.value)} placeholder="Skill values…" style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: 'var(--text-2)', fontFamily: 'var(--sans)' }} />
              {added && <span title="Added by tailoring" style={{ flex: '0 0 auto', padding: '1px 6px', borderRadius: 4, background: 'var(--change-soft)', color: 'var(--good)', fontSize: 11, fontWeight: 500 }}>added</span>}
              {changed && <span onClick={() => setField(`skills.${k}`, baseSkills[k])} title="Decline this tailoring change" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500 }}>↩</span>}
            </div>
            <span onClick={() => mutate((d) => delete d.skills[k])} title="Remove" className="v2-hover-bad" style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: 11, cursor: 'pointer' }}>✕</span>
          </div>
        )
      })}
      {entries.length === 0 && <EmptyState what="skills" />}
      <DashedAdd onClick={() => mutate((d) => { d.skills = d.skills || {}; d.skills[`Skill ${Object.keys(d.skills).length + 1}`] = '' })}>+ Add skill row</DashedAdd>
    </div>
  )
}
const MicroField = ({ label, value, onChange, placeholder, mono }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <span style={{ fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{label}</span>
    <input value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={{ width: '100%', height: 30, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface-2)', color: 'var(--text)', fontSize: mono ? 11 : 12.5, outline: 'none', fontFamily: mono ? 'var(--mono)' : 'var(--sans)' }} />
  </div>
)
function EducationEditor({ data, setField, mutate }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {(data.education || []).map((e, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--surface)', padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="School" value={e.school} onChange={(v) => setField(`education.${i}.school`, v)} />
            <MicroField label="Location" value={e.location} onChange={(v) => setField(`education.${i}.location`, v)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="Degree" value={e.degree} onChange={(v) => setField(`education.${i}.degree`, v)} />
            <MicroField label="Years" value={e.years} onChange={(v) => setField(`education.${i}.years`, v)} placeholder="2015 – 2019" mono />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.education.splice(i, 1))} /></div>
        </div>
      ))}
      {(data.education || []).length === 0 && <EmptyState what="education" />}
      <DashedAdd big onClick={() => mutate((d) => { d.education = d.education || []; d.education.push({ school: '', location: '', degree: '' }) })}>+ Add education</DashedAdd>
    </div>
  )
}
function ProjectsEditor({ data, setField, mutate }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {(data.projects || []).map((p, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--surface)', padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="Name" value={p.name} onChange={(v) => setField(`projects.${i}.name`, v)} />
            <MicroField label="URL" value={p.url} onChange={(v) => setField(`projects.${i}.url`, v)} />
          </div>
          <MicroField label="Description" value={p.description} onChange={(v) => setField(`projects.${i}.description`, v)} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>Bullets</span>
            {(p.bullets || []).map((b, bi) => (
              <div key={bi} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: '1px solid var(--line)', background: 'var(--surface)', borderRadius: 6 }}>
                <span style={{ flex: '0 0 auto', color: 'var(--muted)', fontSize: 11, lineHeight: 1.5 }}>—</span>
                <BulletText value={b} onChange={(v) => mutate((d) => { d.projects[i].bullets[bi] = v })} />
                <span onClick={() => mutate((d) => d.projects[i].bullets.splice(bi, 1))} title="Remove" className="v2-hover-bad" style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: 10, cursor: 'pointer', lineHeight: 1.7 }}>✕</span>
              </div>
            ))}
            <DashedAdd onClick={() => mutate((d) => { d.projects[i].bullets = d.projects[i].bullets || []; d.projects[i].bullets.push('') })}>+ Add bullet</DashedAdd>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.projects.splice(i, 1))}>Remove project</RemoveLink></div>
        </div>
      ))}
      {(data.projects || []).length === 0 && <EmptyState what="projects" />}
      <DashedAdd big onClick={() => mutate((d) => { d.projects = d.projects || []; d.projects.push({ name: '', description: '', url: '', bullets: [] }) })}>+ Add project</DashedAdd>
    </div>
  )
}
function PublicationsEditor({ data, setField, mutate }) {
  const pubs = data.publications || []
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 10 }}>
      {pubs.length === 0 ? <EmptyState what="publications" /> : pubs.map((p, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--surface)', padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <MicroField label="Title" value={p.title} onChange={(v) => setField(`publications.${i}.title`, v)} />
          <MicroField label="Description" value={p.description} onChange={(v) => setField(`publications.${i}.description`, v)} />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.publications.splice(i, 1))} /></div>
        </div>
      ))}
      <DashedAdd big onClick={() => mutate((d) => { d.publications = d.publications || []; d.publications.push({ title: '', description: '' }) })}>+ Add publication</DashedAdd>
    </div>
  )
}
