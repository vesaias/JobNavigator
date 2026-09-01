import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api'
import './theme.css'
import { useToasts, ToastStack } from './Toast'
// The résumé-content editors are shared with /v2/persona (a Persona's
// resume_content is the same shape as a Resume's json_data).
import {
  EMPTY, SECTION_ORDER, sectionCounts, makeMutators,
  MenuHead, MenuItem, SectionShell, SectionEditor,
} from './ResumeSections'

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
const timeAgo = (s) => {
  if (!s) return ''
  const m = Math.floor((Date.now() - new Date(s).getTime()) / 60000)
  if (m < 1) return 'just now'; if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── MOVED to ResumeSections.jsx ──────────────────────────────────────────────
// Field, BulletText, MicroField, RemoveLink, DashedAdd, EmptyState, MenuHead,
// MenuItem, UPPER, cellInput and the seven *Editor sections now live there so
// /v2/persona edits resume_content with the identical components. IconBtn,
// AddLink and normUrl were unreferenced and were dropped rather than moved.
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
  const saveTimer = useRef(null)
  const pdfTimer = useRef(null)
  const pendingRef = useRef([])   // [{baseId, jobId, company, since}]

  const isCopy = doc && !doc.is_base

  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  // background tailoring: after POST, watch for the new copy (parent+job, updated after start)
  useEffect(() => {
    const iv = setInterval(async () => {
      if (!pendingRef.current.length) return
      try {
        const { data } = await api.get('/resumes', { params: { is_base: false } })
        const list = data || []
        pendingRef.current = pendingRef.current.filter((p) => {
          const hit = list.find((r) => String(r.parent_id) === String(p.baseId) && String(r.job_id) === String(p.jobId) && new Date(r.updated_at).getTime() >= p.since - 1000)
          if (hit) { pushToast({ kind: 'success', msg: `Tailored copy for ${p.company} is ready.`, action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${hit.id}`) }); return false }
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
      pushToast({ kind: 'progress', msg: `Tailoring ${company ? 'for ' + company : ''}… runs in the background.` })
    } catch (e) {
      if (e.response?.status === 409) pushToast({ kind: 'error', msg: 'Already tailoring for that job.' })
      else pushToast({ kind: 'error', msg: e.response?.data?.detail || 'Tailoring failed to start.' })
    }
  }, [pushToast])

  // Re-tailor keeps this copy's job and swaps what it is built from: either run
  // the tailoring LLM against another base, or take a plain copy of that base
  // (no LLM) purely to get a fresh set of tracer links.
  const runRetailor = useCallback(async ({ mode, baseId }) => {
    setTailorOpen(false)
    const company = jobData?.company || 'this job'
    try {
      if (mode === 'copy') {
        const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: doc.job_id })
        pushToast({ kind: 'success', msg: `Copy created for ${company}.`, action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${data.id}`) })
      } else {
        await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: doc.job_id })
        pendingRef.current.push({ baseId, jobId: doc.job_id, company, since: Date.now() })
        pushToast({ kind: 'progress', msg: `Tailoring for ${company}… runs in the background.` })
      }
    } catch (e) {
      if (e.response?.status === 409) pushToast({ kind: 'error', msg: 'Already tailoring for that job.' })
      else pushToast({ kind: 'error', msg: e.response?.data?.detail || 'Could not start.' })
    }
  }, [doc, jobData, pushToast, navigate])

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
    if (!doc?.job_id) { pushToast({ kind: 'error', msg: 'This copy isn’t linked to a job to score against.' }); return }
    setHeadMenu(false); setScoring(true)
    try {
      await api.post(`/resumes/${id}/score-check`, { depth })
      pushToast({ kind: 'progress', msg: `Scoring (${depth}) — runs in the background.` })
      // poll until the score lands (or ~60s)
      const t0 = Date.now()
      const iv = setInterval(async () => {
        try {
          const { data: j } = await api.get(`/jobs/${doc.job_id}`)
          const sc = j?.cv_scores?.['Tailored']
          if (typeof sc === 'number') { setJobData(j); setScoring(false); clearInterval(iv); pushToast({ kind: 'success', msg: `Scored: ${Math.round(sc)}${scores.base != null ? ` (${sc - scores.base >= 0 ? '+' : ''}${Math.round(sc - scores.base)} vs base)` : ''}` }) }
          else if (Date.now() - t0 > 60000) { setScoring(false); clearInterval(iv) }
        } catch {}
      }, 3000)
    } catch (e) { setScoring(false); pushToast({ kind: 'error', msg: e.response?.status === 409 ? 'Already scoring this copy.' : (e.response?.data?.detail || 'Scoring failed to start.') }) }
  }, [doc, id, pushToast, scores.base])

  const markApplied = useCallback(async () => {
    if (!doc?.job_id) return
    setHeadMenu(false)
    try { await api.patch(`/jobs/${doc.job_id}`, { status: 'applied' }); loadJobCtx(); pushToast({ kind: 'success', msg: 'Marked applied.' }) } catch { pushToast({ kind: 'error', msg: 'Could not mark applied.' }) }
  }, [doc, loadJobCtx, pushToast])

  const deleteResume = useCallback(async () => {
    if (!window.confirm(`Delete “${doc.name}”?${doc.is_base ? ' Its tailored copies will be removed too.' : ''}`)) return
    try { await api.delete(`/resumes/${id}`); navigate('/v2/resumes') } catch { pushToast({ kind: 'error', msg: 'Delete failed.' }) }
  }, [doc, id, navigate, pushToast])

  const goCover = () => { setHeadMenu(false); navigate(`/v2/cover-letters?resume=${id}${doc.job_id ? `&job=${doc.job_id}` : ''}`) }

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
    pushToast({ kind: 'success', msg: 'Review applied — declined changes restored to base.' })
  }, [changes, data, onData, pushToast])

  // ── json_data mutation (mirrors v1 ResumeContentEditor) ────────────────────
  const { mutate, setField } = makeMutators(data, onData)
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

  const counts = sectionCounts(data)
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
                  <MenuItem icon="✦" label="Re-tailor…" hint="adds a copy" onClick={() => { setHeadMenu(false); setTailorOpen(true) }} />
                  <MenuItem icon="◎" label="Score again · light" hint="score only" onClick={() => runScore('light')} />
                  <MenuItem icon="◎" label="Score again · full" hint="with report" onClick={() => runScore('full')} />
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
          {SECTION_ORDER.map((name) => (
            <SectionShell key={name} name={name} count={counts[name]} open={open.has(name)} onToggle={() => toggle(name)}
              meta={changedSections.has(name) ? <span title="Contains unreviewed tailoring changes" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--warn)' }}>● changed by tailoring</span> : null}>
              <SectionEditor name={name} data={data} setField={setField} mutate={mutate} baseData={baseData} />
            </SectionShell>
          ))}
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

      {tailorOpen && (isCopy
        ? <RetailorModal doc={doc} job={jobData} onClose={() => setTailorOpen(false)} onRun={runRetailor} />
        : <TailorModal doc={doc} onClose={() => setTailorOpen(false)} onRun={runTailor} />)}
      {reviewOpen && <ReviewModal changes={changes} onClose={() => setReviewOpen(false)} onApply={applyReview} />}

      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── re-tailor (a tailored copy) ──────────────────────────────────────────────
// The job is already decided — we are on that job's résumé. What is open is
// which base to work from, and whether to run the tailoring LLM at all or just
// take an exact copy for a fresh set of tracer links.
function RetailorModal({ doc, job, onClose, onRun }) {
  const [mode, setMode] = useState('tailor')
  const [bases, setBases] = useState([])
  const [persona, setPersona] = useState(false)
  const [baseId, setBaseId] = useState(doc.parent_id || 'persona')

  useEffect(() => {
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setBases(data || [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersona(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
  }, [])

  // /resumes/copy takes a Resume row; the Persona isn't one, so it can only be tailored from.
  const personaCopyable = false
  const options = [
    ...(persona ? [{ id: 'persona', name: 'Persona', note: 'your full profile' }] : []),
    ...bases.map((b) => ({ id: String(b.id), name: b.name, note: 'base résumé' })),
  ]
  const disabled = (id) => mode === 'copy' && id === 'persona' && !personaCopyable
  const canRun = !!baseId && !disabled(baseId)

  const MODES = [
    ['tailor', '✦ Tailor', 'Rewrites bullets against this job description'],
    ['copy', 'Copy', 'Exact copy of the base, with its own tracer links'],
  ]

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 480, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Re-tailor for this job</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {job?.company ? `${job.company}${job.title ? ` — ${job.title}` : ''}` : 'the job this copy is for'} · adds a new copy
          </span>
        </div>

        <div className="v2-scroll" style={{ padding: '14px 22px', display: 'flex', flexDirection: 'column', gap: 13, maxHeight: 460, overflow: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>How</span>
            <div style={{ display: 'flex', gap: 7 }}>
              {MODES.map(([id, label, hint]) => {
                const on = mode === id
                return (
                  <div key={id} onClick={() => setMode(id)} title={hint} className="v2-act"
                    style={{ flex: 1, padding: '9px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 8, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 500, color: on ? 'var(--accent)' : 'var(--text)' }}>{label}</span>
                    <span style={{ fontSize: 10.5, lineHeight: 1.4, color: 'var(--muted)', textWrap: 'pretty' }}>{hint}</span>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>From which base</span>
            {options.map((o) => {
              const on = String(baseId) === String(o.id), off = disabled(o.id)
              return (
                <div key={o.id} onClick={() => !off && setBaseId(o.id)} className={off ? undefined : 'v2-act'}
                  title={off ? 'Persona has no résumé row to copy — tailor from it instead' : undefined}
                  style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'transparent', borderRadius: 8, cursor: off ? 'default' : 'pointer', opacity: off ? 0.45 : 1 }}>
                  <span style={{ flex: '0 0 auto', width: 14, height: 14, borderRadius: 99, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 99, background: on ? 'var(--accent)' : 'transparent' }} /></span>
                  <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.name}</span>
                  <span style={{ flex: '0 0 auto', fontSize: 10.5, color: 'var(--muted)' }}>{String(doc.parent_id || 'persona') === String(o.id) ? 'current base' : o.note}</span>
                </div>
              )
            })}
            {options.length === 0 && <div style={{ padding: 12, border: '1px dashed var(--edge)', borderRadius: 8, fontSize: 11.5, color: 'var(--muted)' }}>No base résumés yet.</div>}
          </div>
        </div>

        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{mode === 'tailor' ? 'Runs in the background' : 'Instant — no LLM call'}</span>
          <div onClick={onClose} className="v2-act" style={{ marginLeft: 'auto', height: 33, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
          <div onClick={() => canRun && onRun({ mode, baseId })} style={{ height: 33, padding: '0 17px', borderRadius: 99, background: canRun ? 'var(--accent)' : 'var(--edge)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: canRun ? 'pointer' : 'default' }}>{mode === 'tailor' ? '✦ Re-tailor' : 'Make copy'}</div>
        </div>
      </div>
    </div>
  )
}

// ── tailor modal (job picker + freeform + persona) ───────────────────────────
function TailorModal({ doc, onClose, onRun }) {
  const baseId = doc.id
  const [jobs, setJobs] = useState([])
  const [existing, setExisting] = useState(new Set())
  const [q, setQ] = useState('')
  const [pick, setPick] = useState(null)
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

  const canRun = !!(pick || jd.trim())
  const chosen = jobs.find((j) => String(j.id) === String(pick))
  const run = () => onRun({ baseId: personaBase ? 'persona' : baseId, jobId: pick, jobDescription: pick ? '' : jd.trim(), company: chosen?.company })

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 480, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Tailor {doc.name} for a job</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Changes land automatically — you review and decline afterwards.</span>
        </div>
        <div className="v2-scroll" style={{ padding: '14px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 460, overflow: 'auto' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>
            <input type="checkbox" checked={personaBase} onChange={(e) => setPersonaBase(e.target.checked)} />
            Tailor from Persona instead of this base
          </label>
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
