import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api'
import { Plus, Trash2, ChevronDown, ChevronRight, Download, Loader2, Wand2, ArrowUp, ArrowDown, Mail } from 'lucide-react'

const PAGE_FORMATS = [
  { id: 'letter', name: 'US Letter' },
  { id: 'a4', name: 'A4' },
]

const LENGTHS = [
  { id: 'concise', name: 'Concise' },
  { id: 'standard', name: 'Standard' },
  { id: 'detailed', name: 'Detailed' },
]

const EMPTY_DATA = {
  header: { name: '', contact_items: [] },
  recipient: { company: '', manager: '', address: '' },
  date: '',
  greeting: 'Dear Hiring Team,',
  body_paragraphs: [''],
  closing: 'Sincerely,',
  signature: '',
}

function Section({ title, children, defaultOpen = true, badge }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg mb-4">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg">
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {title}
        {badge != null && <span className="text-xs text-gray-400 font-normal">({badge})</span>}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

function Field({ label, value, onChange, onBlur, placeholder, multiline, rows }) {
  const cls = "border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
  return (
    <div className="mb-2">
      {label && <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">{label}</label>}
      {multiline
        ? <textarea className={cls} rows={rows || 4} value={value || ''} placeholder={placeholder}
            onChange={e => onChange(e.target.value)} onBlur={onBlur} />
        : <input className={cls} value={value || ''} placeholder={placeholder}
            onChange={e => onChange(e.target.value)} onBlur={onBlur} />}
    </div>
  )
}

export default function CoverLetterBuilder() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [letters, setLetters] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [editData, setEditData] = useState({ ...EMPTY_DATA })
  const [template, setTemplate] = useState('garamond')
  const [pageFormat, setPageFormat] = useState('letter')
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dataLoaded, setDataLoaded] = useState(false)
  const [previewKey, setPreviewKey] = useState(0)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null)
  const [pickerOpen, setPickerOpen] = useState(false)

  // Generate panel
  const [resumes, setResumes] = useState([])
  const [jobs, setJobs] = useState([])
  const [personaAvailable, setPersonaAvailable] = useState(false)
  const [voicePresets, setVoicePresets] = useState([])
  const [genResume, setGenResume] = useState('')
  const [genJob, setGenJob] = useState('')
  const [genVoice, setGenVoice] = useState('')
  const [genLength, setGenLength] = useState('standard')
  const [generating, setGenerating] = useState(false)

  const saveTimeoutRef = useRef(null)
  const prevBlobRef = useRef(null)
  const pendingGenRef = useRef([])
  const [pendingGen, setPendingGen] = useState([])

  useEffect(() => { pendingGenRef.current = pendingGen }, [pendingGen])

  useEffect(() => {
    fetchLetters()
    api.get('/cover-letters/templates').then(({ data }) => setTemplates(data)).catch(() => setTemplates([]))
    // Base resumes only — tailored ones have long auto-names and clutter the picker.
    api.get('/resumes?is_base=true').then(({ data }) => setResumes(data)).catch(() => {})
    // Offer "Persona" as a base if its resume_content is filled in.
    api.get('/persona').then(({ data }) => {
      setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)
    }).catch(() => {})
    // Saved jobs are the target set (jobs you're about to apply to). /jobs returns {jobs, total}.
    api.get('/jobs?status=saved&limit=200').then(r => setJobs(r.data.jobs || [])).catch(() => setJobs([]))
    api.get('/settings').then(({ data }) => {
      try {
        const raw = data.cover_letter_voice_presets
        const presets = Array.isArray(raw) ? raw : JSON.parse(raw || '[]')
        setVoicePresets(presets)
        setGenVoice(data.cover_letter_default_voice || (presets[0]?.id || ''))
      } catch { setVoicePresets([]) }
    }).catch(() => {})
    // Deep-link pre-fill for the generate panel (from JobFeed / Resume editor)
    const preJob = searchParams.get('job')
    const preResume = searchParams.get('resume')
    if (preJob) setGenJob(preJob)
    if (preResume) {
      setGenResume(preResume)
      // The Resume editor links a tailored resume, which isn't in the base-only
      // list — fetch it and add it so the pre-selection is valid.
      api.get(`/resumes/${preResume}`).then(({ data }) => {
        setResumes(prev => prev.some(r => r.id === preResume) ? prev : [data, ...prev])
      }).catch(() => {})
    }
  }, [])

  // Poll /monitor/active for generate_cover_letter runs so the spinner survives navigation.
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const { data: active } = await api.get('/monitor/active')
        const runs = (active || []).filter(r => r.job_type === 'generate_cover_letter')
        if (cancelled) return
        const prevIds = new Set(pendingGenRef.current.map(p => p.run_id))
        const nowIds = new Set(runs.map(r => r.run_id))
        const finished = [...prevIds].some(id => !nowIds.has(id))
        if (runs.length !== pendingGenRef.current.length ||
            !runs.every((r, i) => r.run_id === pendingGenRef.current[i]?.run_id)) {
          setPendingGen(runs)
        }
        if (finished) { setGenerating(false); fetchLetters(true) }
      } catch {/* retry next tick */}
    }
    tick()
    const h = setInterval(tick, 3000)
    return () => { cancelled = true; clearInterval(h) }
  }, [])

  const fetchLetters = async (selectNewest = false) => {
    try {
      const { data } = await api.get('/cover-letters')
      setLetters(data)
      const target = searchParams.get('cl')
      if (target) {
        const found = data.find(c => c.id === target)
        if (found) { selectLetter(found); setSearchParams({}, { replace: true }) }
        else if (data.length && !selectedId) selectLetter(data[0])
      } else if (selectNewest && data.length) {
        selectLetter(data[0])
      } else if (data.length && !selectedId) {
        selectLetter(data[0])
      }
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const selectLetter = async (c) => {
    setDataLoaded(false)
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    setSelectedId(c.id)
    setTemplate(c.template || 'garamond')
    setPageFormat(c.page_format || 'letter')
    setPickerOpen(false)
    try {
      const { data } = await api.get(`/cover-letters/${c.id}`)
      setEditData(data.json_data || { ...EMPTY_DATA })
    } catch { setEditData({ ...EMPTY_DATA }) }
    setDataLoaded(true)
    setPreviewKey(k => k + 1)
  }

  const triggerSave = (data, tmpl, fmt) => {
    if (!dataLoaded || !selectedId) return
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(async () => {
      setSaving(true)
      try {
        await api.patch(`/cover-letters/${selectedId}`, {
          json_data: data || editData, template: tmpl || template, page_format: fmt || pageFormat,
        })
        setPreviewKey(k => k + 1)
      } catch (e) { console.error(e) }
      setSaving(false)
    }, 500)
  }

  const update = (mutator) => {
    const next = JSON.parse(JSON.stringify(editData))
    mutator(next)
    setEditData(next)
    triggerSave(next)
  }

  // Live PDF preview
  useEffect(() => {
    if (!selectedId) { setPdfPreviewUrl(null); return }
    const fetchPdf = async () => {
      try {
        const r = await api.get(`/cover-letters/${selectedId}/pdf`, { responseType: 'arraybuffer' })
        const blob = new Blob([r.data], { type: 'application/pdf' })
        const url = URL.createObjectURL(blob)
        if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current)
        prevBlobRef.current = url
        setPdfPreviewUrl(url + '#view=FitH')
      } catch { setPdfPreviewUrl(null) }
    }
    const t = setTimeout(fetchPdf, 800)
    return () => clearTimeout(t)
  }, [previewKey, selectedId, template, pageFormat])

  const changeTemplate = (t) => { setTemplate(t); triggerSave(editData, t, pageFormat) }
  const changeFormat = (f) => { setPageFormat(f); triggerSave(editData, template, f) }

  const pdfDownloadUrl = selectedId
    ? (api.defaults.baseURL || '').replace('/api', '') + '/api/cover-letters/' + selectedId + '/pdf'
    : null

  // When a tailored resume is picked, auto-select its job
  const onPickResume = (rid) => {
    setGenResume(rid)
    const r = resumes.find(x => x.id === rid)
    if (r && r.job_id) setGenJob(r.job_id)
  }

  const doGenerate = async () => {
    if (!genResume || !genJob) return
    setGenerating(true)
    try {
      const { data } = await api.post('/cover-letters/generate', {
        resume_id: genResume, job_id: genJob, voice: genVoice, length: genLength,
      })
      // optimistic pending entry until the monitor surfaces it
      setPendingGen(prev => [...prev, { run_id: data.run_id, job_type: 'generate_cover_letter' }])
    } catch (e) {
      setGenerating(false)
      const msg = e?.response?.data?.detail || 'Generation failed'
      alert(msg)
    }
  }

  const regenerate = async () => {
    const cl = letters.find(c => c.id === selectedId)
    if (!cl || !cl.resume_id || !cl.job_id) { alert('This letter is missing its resume/job link — generate a new one.'); return }
    setGenerating(true)
    try {
      const { data } = await api.post('/cover-letters/generate', {
        resume_id: cl.resume_id, job_id: cl.job_id, voice: genVoice, length: genLength,
      })
      setPendingGen(prev => [...prev, { run_id: data.run_id, job_type: 'generate_cover_letter' }])
    } catch (e) {
      setGenerating(false)
      alert(e?.response?.data?.detail || 'Regeneration failed')
    }
  }

  const paras = editData.body_paragraphs || []

  return (
    <div className="grid grid-cols-5 gap-0 h-full">
      {/* Left: controls (2/5, matches resume editor) */}
      <div className="col-span-2 border-r dark:border-gray-700 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900">
        {/* Picker */}
        <div className="relative cl-picker mb-4">
          <button onClick={() => setPickerOpen(!pickerOpen)}
            className="w-full flex items-center justify-between bg-white dark:bg-gray-800 border dark:border-gray-700 rounded px-3 py-2 text-sm dark:text-gray-200">
            <span className="flex items-center gap-2 truncate"><Mail size={14} />{letters.find(c => c.id === selectedId)?.name || 'Select a cover letter'}</span>
            <ChevronDown size={14} />
          </button>
          {pickerOpen && (
            <div className="absolute z-20 mt-1 w-full bg-white dark:bg-gray-800 border dark:border-gray-700 rounded shadow-lg max-h-72 overflow-y-auto">
              {letters.length === 0 && <div className="px-3 py-2 text-xs text-gray-400">No cover letters yet — generate one below.</div>}
              {letters.map(c => (
                <button key={c.id} onClick={() => selectLetter(c)}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 dark:text-gray-200 ${c.id === selectedId ? 'bg-indigo-50 dark:bg-indigo-900/30' : ''}`}>
                  {c.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Generate panel */}
        <Section title="Generate New" defaultOpen={letters.length === 0}>
          <div className="mb-2">
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Your resume</label>
            <select value={genResume} onChange={e => onPickResume(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Select resume…</option>
              {personaAvailable && <option value="persona">Persona (full profile)</option>}
              {resumes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">The letter pulls your achievements and writing style from this resume (or your full Persona profile).</p>
          </div>
          <div className="mb-2">
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Target job</label>
            <select value={genJob} onChange={e => setGenJob(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Select job (saved/applied)…</option>
              {jobs.map(j => <option key={j.id} value={j.id}>{j.company} — {j.title}</option>)}
            </select>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">The posting the letter is written for (its description is the target).</p>
          </div>
          <div className="flex gap-2 mb-2">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Voice</label>
              <select value={genVoice} onChange={e => setGenVoice(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                {voicePresets.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Length</label>
              <select value={genLength} onChange={e => setGenLength(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                {LENGTHS.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
          </div>
          <button onClick={doGenerate} disabled={!genResume || !genJob || generating}
            className="w-full bg-indigo-600 text-white px-3 py-2 rounded text-sm hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2">
            {generating ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
            {generating ? 'Generating…' : 'Generate Cover Letter'}
          </button>
        </Section>

        {selectedId && (
          <>
            {/* Template + format */}
            <Section title="Style" defaultOpen={false}>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Template</label>
                  <select value={template} onChange={e => changeTemplate(e.target.value)}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Format</label>
                  <select value={pageFormat} onChange={e => changeFormat(e.target.value)}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    {PAGE_FORMATS.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </div>
              </div>
              <button onClick={regenerate} disabled={generating}
                className="mt-3 w-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1.5 rounded text-sm hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 flex items-center justify-center gap-2">
                {generating ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                Regenerate (current voice/length)
              </button>
            </Section>

            {/* Recipient */}
            <Section title="Recipient & Date" defaultOpen={false}>
              <Field label="Date" value={editData.date} onChange={v => update(d => d.date = v)} />
              <Field label="Company" value={editData.recipient?.company} onChange={v => update(d => { d.recipient = d.recipient || {}; d.recipient.company = v })} />
              <Field label="Hiring manager (optional)" value={editData.recipient?.manager} onChange={v => update(d => { d.recipient = d.recipient || {}; d.recipient.manager = v })} />
              <Field label="Address (optional)" value={editData.recipient?.address} onChange={v => update(d => { d.recipient = d.recipient || {}; d.recipient.address = v })} />
            </Section>

            {/* Body */}
            <Section title="Letter" badge={paras.length}>
              <Field label="Greeting" value={editData.greeting} onChange={v => update(d => d.greeting = v)} />
              {paras.map((p, i) => (
                <div key={i} className="mb-3 border dark:border-gray-700 rounded p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-400">Paragraph {i + 1}</span>
                    <div className="flex gap-1">
                      <button onClick={() => update(d => { if (i > 0) { const a = d.body_paragraphs; [a[i-1], a[i]] = [a[i], a[i-1]] } })} disabled={i === 0}
                        className="text-gray-400 hover:text-gray-600 disabled:opacity-30"><ArrowUp size={13} /></button>
                      <button onClick={() => update(d => { const a = d.body_paragraphs; if (i < a.length - 1) [a[i+1], a[i]] = [a[i], a[i+1]] })} disabled={i === paras.length - 1}
                        className="text-gray-400 hover:text-gray-600 disabled:opacity-30"><ArrowDown size={13} /></button>
                      <button onClick={() => update(d => d.body_paragraphs.splice(i, 1))}
                        className="text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
                    </div>
                  </div>
                  <textarea className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" rows={4}
                    value={p} onChange={e => update(d => d.body_paragraphs[i] = e.target.value)} />
                </div>
              ))}
              <button onClick={() => update(d => { d.body_paragraphs = d.body_paragraphs || []; d.body_paragraphs.push('') })}
                className="text-sm text-indigo-600 dark:text-indigo-400 flex items-center gap-1 hover:underline">
                <Plus size={13} /> Add paragraph
              </button>
              <div className="mt-3">
                <Field label="Closing" value={editData.closing} onChange={v => update(d => d.closing = v)} />
                <Field label="Signature" value={editData.signature} onChange={v => update(d => d.signature = v)} />
              </div>
            </Section>

            {/* Header */}
            <Section title="Header" defaultOpen={false}>
              <Field label="Name" value={editData.header?.name} onChange={v => update(d => { d.header = d.header || {}; d.header.name = v })} />
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-0.5">Contact items</label>
              {(editData.header?.contact_items || []).map((item, i) => {
                const items = editData.header?.contact_items || []
                return (
                <div key={i} className="flex items-center gap-1 mb-1">
                  <div className="flex flex-col">
                    <button onClick={() => update(d => { if (i > 0) { const a = d.header.contact_items; [a[i-1], a[i]] = [a[i], a[i-1]] } })} disabled={i === 0}
                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowUp size={11} /></button>
                    <button onClick={() => update(d => { const a = d.header.contact_items; if (i < a.length - 1) [a[i+1], a[i]] = [a[i], a[i+1]] })} disabled={i === items.length - 1}
                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowDown size={11} /></button>
                  </div>
                  <input className="border rounded px-2 py-1 text-sm w-32 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" placeholder="text"
                    value={item.text || ''} onChange={e => update(d => d.header.contact_items[i].text = e.target.value)} />
                  <input className="border rounded px-2 py-1 text-sm flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" placeholder="url"
                    value={item.url || ''} onChange={e => update(d => d.header.contact_items[i].url = e.target.value)} />
                  {item.url && !item.url.startsWith('mailto:') && (
                    <input className="border rounded px-2 py-1 text-sm w-12 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" placeholder="id"
                      title="Short stub for tracer link ID (e.g. l, w, gh)"
                      value={item.stub || ''} onChange={e => update(d => d.header.contact_items[i].stub = e.target.value)} />
                  )}
                  <button onClick={() => update(d => d.header.contact_items.splice(i, 1))} className="text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
                </div>
                )
              })}
              <button onClick={() => update(d => { d.header = d.header || {}; d.header.contact_items = d.header.contact_items || []; d.header.contact_items.push({ text: '', url: '' }) })}
                className="text-sm text-indigo-600 dark:text-indigo-400 flex items-center gap-1 hover:underline mt-1">
                <Plus size={13} /> Add contact
              </button>
            </Section>
          </>
        )}
      </div>

      {/* Right: preview */}
      <div className="col-span-3 flex flex-col bg-gray-100 dark:bg-gray-950 min-h-0">
        <div className="flex items-center justify-between px-4 py-2 border-b dark:border-gray-700 bg-white dark:bg-gray-800">
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
            Preview {saving && <Loader2 size={12} className="animate-spin text-gray-400" />}
          </span>
          {pdfDownloadUrl && (
            <a href={pdfDownloadUrl} target="_blank" rel="noopener noreferrer"
              className="bg-blue-600 text-white px-2.5 py-1.5 rounded text-sm hover:bg-blue-700 flex items-center gap-1">
              <Download size={14} /> Download PDF
            </a>
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center text-gray-400"><Loader2 className="animate-spin" /></div>
          ) : !selectedId ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">Generate or select a cover letter to preview.</div>
          ) : pdfPreviewUrl ? (
            <iframe key={`cl-${selectedId}-${previewKey}`} src={pdfPreviewUrl} className="w-full h-full border-0" title="Cover letter preview" />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400"><Loader2 className="animate-spin" /></div>
          )}
        </div>
      </div>
    </div>
  )
}
