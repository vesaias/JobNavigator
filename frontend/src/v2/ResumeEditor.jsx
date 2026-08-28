import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api'
import './theme.css'

const DANGEROUS = new Set(['__proto__', 'constructor', 'prototype'])
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
const IconBtn = ({ onClick, title, children, danger }) => (
  <span onClick={onClick} title={title} className="v2-hover-accent" style={{ flex: '0 0 auto', width: 22, height: 22, borderRadius: 5, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: danger ? 'var(--bad)' : 'var(--muted)', cursor: 'pointer' }}>{children}</span>
)
const AddLink = ({ onClick, children }) => (
  <span onClick={onClick} style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', alignSelf: 'flex-start' }} className="v2-navlink">{children}</span>
)
const RemoveLink = ({ onClick, children = 'Remove' }) => (
  <span onClick={onClick} style={{ fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer', whiteSpace: 'nowrap' }} className="v2-hover-bad">{children}</span>
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
  const [pdfLoading, setPdfLoading] = useState(true)
  const [open, setOpen] = useState(() => new Set(['Experience']))
  const [tplOpen, setTplOpen] = useState(false)
  const [fmtOpen, setFmtOpen] = useState(false)
  const [tailorOpen, setTailorOpen] = useState(false)
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

  // live PDF preview (endpoint renders stored template/format; persist fires first at 500ms, this at 800ms)
  useEffect(() => {
    if (!doc) return
    clearTimeout(pdfTimer.current)
    setPdfLoading(true)
    pdfTimer.current = setTimeout(async () => {
      try {
        const r = await api.get(`/resumes/${id}/pdf`, { responseType: 'arraybuffer', params: { template, format } })
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
        setPdfUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return url })
      } catch (e) { console.error('pdf', e) }
      setPdfLoading(false)
    }, 800)
    return () => clearTimeout(pdfTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, template, format, doc, id])
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl) }, [pdfUrl])

  // ── json_data mutation (mirrors v1 ResumeContentEditor) ────────────────────
  const mutate = (fn) => { const d = JSON.parse(JSON.stringify(data || EMPTY)); fn(d); onData(d) }
  const setField = (path, val) => {
    const keys = String(path).split('.'); if (keys.some((k) => DANGEROUS.has(k))) return
    mutate((d) => { let o = d; for (let i = 0; i < keys.length - 1; i++) { if (o == null || typeof o !== 'object') return; o = o[keys[i]] } if (o && typeof o === 'object') o[keys[keys.length - 1]] = val })
  }
  const toggle = (name) => setOpen((p) => { const n = new Set(p); n.has(name) ? n.delete(name) : n.add(name); return n })

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
        <div style={{ flex: '0 0 auto', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)', padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 13, fontSize: 12.5, color: 'var(--text-2)' }}>
          <span>Tailored copy{doc.job_id ? <> · <span onClick={() => navigate(`/v2/feed?job=${doc.job_id}`)} style={{ color: 'var(--accent)', cursor: 'pointer' }} className="v2-navlink">open job ↗</span></> : ''}</span>
          <span style={{ color: 'var(--line)' }}>·</span>
          <span style={{ color: 'var(--muted)' }}>editing here changes only this copy</span>
          <div onClick={() => setTailorOpen(true)} style={{ marginLeft: 'auto', height: 30, padding: '0 15px', borderRadius: 99, border: '1px solid var(--edge)', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, cursor: 'pointer' }} className="v2-act">✦ Re-tailor…</div>
        </div>
      ) : (
        <div style={{ flex: '0 0 auto', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)', padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 13, fontSize: 12.5, color: 'var(--text-2)' }}>
          <span>Base résumé · <span style={{ color: 'var(--text)', fontWeight: 500 }}>editing here changes future tailoring</span></span>
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
                  <span style={{ color: 'var(--muted)', fontSize: 11 }}>{isOpen ? '⌄' : '›'}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                  {counts[name] != null && <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>({counts[name]})</span>}
                </div>
                {isOpen && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
                    {name === 'Header' && <HeaderEditor data={data} setField={setField} mutate={mutate} />}
                    {name === 'Summary' && <Field multiline rows={4} value={data.summary} onChange={(v) => setField('summary', v)} placeholder="Professional summary…" />}
                    {name === 'Experience' && <ExperienceEditor data={data} setField={setField} mutate={mutate} />}
                    {name === 'Skills' && <SkillsEditor data={data} setField={setField} mutate={mutate} />}
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
              <span onClick={() => { setTplOpen((v) => !v); setFmtOpen(false) }} style={{ fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer' }} className="v2-navlink">{tplLabel} ▾</span>
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
              <span onClick={() => { setFmtOpen((v) => !v); setTplOpen(false) }} style={{ fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer' }} className="v2-navlink">{format === 'a4' ? 'A4' : 'US Letter'} ▾</span>
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
            {pdfUrl
              ? <iframe title="pdf" src={`${pdfUrl}#view=FitH`} style={{ width: '100%', height: '100%', border: 'none' }} />
              : <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Rendering…</div>}
            {pdfLoading && pdfUrl && <div style={{ position: 'absolute', top: 10, right: 14, fontSize: 11, color: 'var(--muted)', background: 'var(--surface)', padding: '3px 8px', borderRadius: 99, border: '1px solid var(--line)' }}>updating…</div>}
          </div>
        </section>
      </div>

      {tailorOpen && <TailorModal doc={doc} onClose={() => setTailorOpen(false)} onRun={runTailor} />}

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

// ── section editors (v2-styled, same handlers as v1) ─────────────────────────
function HeaderEditor({ data, setField, mutate }) {
  const items = data.header?.contact_items || []
  const move = (i, dir) => mutate((d) => { const a = d.header.contact_items; const j = i + dir; if (j < 0 || j >= a.length) return;[a[i], a[j]] = [a[j], a[i]] })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 8 }}>
      <Field label="Name" value={data.header?.name} onChange={(v) => setField('header.name', v)} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>Contact items</span>
        {items.map((it, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <IconBtn onClick={() => move(i, -1)} title="Up">↑</IconBtn>
              <IconBtn onClick={() => move(i, 1)} title="Down">↓</IconBtn>
            </div>
            <Field value={it.text} onChange={(v) => setField(`header.contact_items.${i}.text`, v)} placeholder="Display text" />
            <Field value={it.url} onChange={(v) => setField(`header.contact_items.${i}.url`, v)} placeholder="URL (optional)" flex={1} />
            {it.url && !it.url.startsWith('mailto:') && <div style={{ width: 46 }}><Field value={it.stub} onChange={(v) => setField(`header.contact_items.${i}.stub`, v)} placeholder="id" /></div>}
            <IconBtn danger onClick={() => mutate((d) => d.header.contact_items.splice(i, 1))} title="Remove">✕</IconBtn>
          </div>
        ))}
        <AddLink onClick={() => mutate((d) => { d.header = d.header || { contact_items: [] }; (d.header.contact_items = d.header.contact_items || []).push({ text: '', url: '' }) })}>+ Add item</AddLink>
      </div>
    </div>
  )
}
function ExperienceEditor({ data, setField, mutate }) {
  const exp = data.experience || []
  const setBullet = (i, bi, v) => mutate((d) => { d.experience[i].bullets[bi] = v })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
      {exp.map((e, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 7, padding: 11, display: 'flex', flexDirection: 'column', gap: 8, position: 'relative' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <Field label="Company" value={e.company} onChange={(v) => setField(`experience.${i}.company`, v)} />
            <Field label="Title" value={e.title} onChange={(v) => setField(`experience.${i}.title`, v)} />
            <Field label="Location" value={e.location} onChange={(v) => setField(`experience.${i}.location`, v)} />
            <Field label="Date" value={e.date} onChange={(v) => setField(`experience.${i}.date`, v)} placeholder="Jan 2022 – Present" mono />
          </div>
          <Field label="Description" value={e.description} onChange={(v) => setField(`experience.${i}.description`, v)} placeholder="Optional role description" />
          <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>Bullets</span>
          {(e.bullets || []).map((b, bi) => (
            <div key={bi} style={{ display: 'flex', alignItems: 'flex-start', gap: 7 }}>
              <span style={{ color: 'var(--muted)', fontSize: 11, paddingTop: 7 }}>·</span>
              <Field value={b} onChange={(v) => setBullet(i, bi, v)} flex={1} multiline rows={1} />
              <IconBtn danger onClick={() => mutate((d) => d.experience[i].bullets.splice(bi, 1))} title="Remove">✕</IconBtn>
            </div>
          ))}
          {(e.suggested_bullets || []).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '7px 9px', border: '1px solid var(--accent)', background: 'var(--accent-soft)', borderRadius: 6 }}>
              <span style={{ fontSize: 9.5, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--accent)' }}>✦ Suggested by tailoring · review to keep</span>
              {e.suggested_bullets.map((sb, k) => <div key={k} style={{ display: 'flex', gap: 6, fontSize: 12, color: 'var(--text-2)' }}><span style={{ color: 'var(--accent)' }}>+</span><span>{sb}</span></div>)}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AddLink onClick={() => mutate((d) => { d.experience[i].bullets = d.experience[i].bullets || []; d.experience[i].bullets.push('') })}>+ Bullet</AddLink>
            <RemoveLink onClick={() => mutate((d) => d.experience.splice(i, 1))}>Remove role</RemoveLink>
          </div>
        </div>
      ))}
      <AddLink onClick={() => mutate((d) => { d.experience = d.experience || []; d.experience.push({ company: '', title: '', location: '', date: '', description: '', bullets: [] }) })}>+ Add experience</AddLink>
    </div>
  )
}
function SkillsEditor({ data, setField, mutate }) {
  const entries = Object.entries(data.skills || {})
  const rename = (oldK, newK) => { if (oldK === newK || !newK.trim()) return; mutate((d) => { const ns = {}; for (const [k, v] of Object.entries(d.skills)) ns[k === oldK ? newK : k] = v; d.skills = ns }) }
  const move = (k, dir) => mutate((d) => { const e = Object.entries(d.skills); const i = e.findIndex(([x]) => x === k); const j = i + dir; if (i < 0 || j < 0 || j >= e.length) return;[e[i], e[j]] = [e[j], e[i]]; d.skills = Object.fromEntries(e) })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7, paddingTop: 8 }}>
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}><IconBtn onClick={() => move(k, -1)} title="Up">↑</IconBtn><IconBtn onClick={() => move(k, 1)} title="Down">↓</IconBtn></div>
          <div style={{ width: '32%' }}><input defaultValue={k} onBlur={(e) => rename(k, e.target.value)} placeholder="Category" style={{ width: '100%', height: 30, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12.5, outline: 'none', fontFamily: 'var(--sans)' }} /></div>
          <Field value={v} onChange={(nv) => setField(`skills.${k}`, nv)} placeholder="Skill values…" flex={1} />
          <IconBtn danger onClick={() => mutate((d) => delete d.skills[k])} title="Remove">✕</IconBtn>
        </div>
      ))}
      <AddLink onClick={() => mutate((d) => { d.skills = d.skills || {}; d.skills[`Skill ${Object.keys(d.skills).length + 1}`] = '' })}>+ Add skill row</AddLink>
    </div>
  )
}
function EducationEditor({ data, setField, mutate }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
      {(data.education || []).map((e, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 7, padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <Field label="School" value={e.school} onChange={(v) => setField(`education.${i}.school`, v)} />
            <Field label="Location" value={e.location} onChange={(v) => setField(`education.${i}.location`, v)} />
          </div>
          <Field label="Degree" value={e.degree} onChange={(v) => setField(`education.${i}.degree`, v)} />
          <div style={{ alignSelf: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.education.splice(i, 1))} /></div>
        </div>
      ))}
      <AddLink onClick={() => mutate((d) => { d.education = d.education || []; d.education.push({ school: '', location: '', degree: '' }) })}>+ Add education</AddLink>
    </div>
  )
}
function ProjectsEditor({ data, setField, mutate }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
      {(data.projects || []).map((p, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 7, padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <Field label="Name" value={p.name} onChange={(v) => setField(`projects.${i}.name`, v)} />
            <Field label="URL" value={p.url} onChange={(v) => setField(`projects.${i}.url`, v)} />
          </div>
          <Field label="Description" value={p.description} onChange={(v) => setField(`projects.${i}.description`, v)} />
          <Field label="Bullets (one per line)" multiline rows={3} value={(p.bullets || []).join('\n')} onChange={(v) => setField(`projects.${i}.bullets`, v.split('\n'))} />
          <div style={{ alignSelf: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.projects.splice(i, 1))} /></div>
        </div>
      ))}
      <AddLink onClick={() => mutate((d) => { d.projects = d.projects || []; d.projects.push({ name: '', description: '', url: '', bullets: [] }) })}>+ Add project</AddLink>
    </div>
  )
}
function PublicationsEditor({ data, setField, mutate }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
      {(data.publications || []).map((p, i) => (
        <div key={i} style={{ border: '1px solid var(--line)', borderRadius: 7, padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Field label="Title" value={p.title} onChange={(v) => setField(`publications.${i}.title`, v)} />
          <Field label="Description" value={p.description} onChange={(v) => setField(`publications.${i}.description`, v)} />
          <div style={{ alignSelf: 'flex-end' }}><RemoveLink onClick={() => mutate((d) => d.publications.splice(i, 1))} /></div>
        </div>
      ))}
      <AddLink onClick={() => mutate((d) => { d.publications = d.publications || []; d.publications.push({ title: '', description: '' }) })}>+ Add publication</AddLink>
    </div>
  )
}
