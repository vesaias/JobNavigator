import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api'
import { Plus, Trash2, X, ChevronDown, ChevronRight, ChevronUp, Download, Upload, Loader2, Wand2, ArrowUp, ArrowDown, ExternalLink, Briefcase, CheckCircle2 } from 'lucide-react'
import { diffWords } from 'diff'

function InlineDiff({ oldText, newText }) {
  if (!oldText && !newText) return null
  if (oldText === newText) return <span>{newText}</span>
  const changes = diffWords(oldText || '', newText || '')
  return (
    <span>
      {changes.map((part, i) => (
        <span key={i} className={
          part.added ? 'bg-green-200 dark:bg-green-900 rounded px-0.5' :
          part.removed ? 'bg-red-200 dark:bg-red-900 line-through rounded px-0.5 opacity-70' :
          ''
        }>{part.value}</span>
      ))}
    </span>
  )
}

// Templates loaded from API on mount (auto-discovered from backend filesystem)

const PAGE_FORMATS = [
  { id: 'letter', name: 'US Letter' },
  { id: 'a4', name: 'A4' },
]

const EMPTY_DATA = {
  header: {
    name: '',
    contact_items: [
      { text: 'City, Country', url: '' },
      { text: 'your@email.com', url: 'mailto:your@email.com' },
      { text: 'LinkedIn', url: 'linkedin.com/in/yourname', stub: 'l' },
      { text: 'Portfolio', url: 'yoursite.com', stub: 'w' },
      { text: '+1 234 567 8900', url: '' },
    ]
  },
  summary: '',
  experience: [],
  skills: {},
  education: [],
  projects: [],
  publications: [],
}

function CollapsibleSection({ title, defaultOpen = true, children, badge }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg mb-4">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
      >
        <span className="flex items-center gap-2">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {title}
          {badge != null && <span className="text-xs text-gray-400 font-normal">({badge})</span>}
        </span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

function FieldInput({ label, value, onChange, onBlur, placeholder, multiline, rows }) {
  const cls = "border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
  const handleBoldShortcut = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault()
      const ta = e.target
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = ta.value
      if (start === end) return // no selection
      const selected = text.slice(start, end)
      // Toggle: if already wrapped in **, remove; otherwise add
      if (text.slice(start - 2, start) === '**' && text.slice(end, end + 2) === '**') {
        const newText = text.slice(0, start - 2) + selected + text.slice(end + 2)
        onChange(newText)
        setTimeout(() => { ta.selectionStart = start - 2; ta.selectionEnd = end - 2 }, 0)
      } else {
        const newText = text.slice(0, start) + '**' + selected + '**' + text.slice(end)
        onChange(newText)
        setTimeout(() => { ta.selectionStart = start + 2; ta.selectionEnd = end + 2 }, 0)
      }
    }
  }
  return (
    <div className="mb-2">
      {label && <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{label}</label>}
      {multiline ? (
        <textarea
          className={cls}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          onBlur={onBlur}
          onKeyDown={handleBoldShortcut}
          placeholder={placeholder}
          rows={rows || 3}
        />
      ) : (
        <input
          type="text"
          className={cls}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          onBlur={onBlur}
          placeholder={placeholder}
        />
      )}
    </div>
  )
}

export default function ResumeBuilder() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [TEMPLATES, setTemplates] = useState([])
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [editData, setEditData] = useState(null)
  const [template, setTemplate] = useState('')
  const [pageFormat, setPageFormat] = useState('letter')
  const [previewKey, setPreviewKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newName, setNewName] = useState('')
  const [dataLoaded, setDataLoaded] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [importing, setImporting] = useState(false)
  const [showTailorModal, setShowTailorModal] = useState(false)
  const [tailorJobId, setTailorJobId] = useState('')
  const [tailorJdText, setTailorJdText] = useState('')
  const [tailoring, setTailoring] = useState(false)
  const [recentJobs, setRecentJobs] = useState([])
  const [pageCount, setPageCount] = useState(null)
  const [tracerStats, setTracerStats] = useState([])
  const [resumeSearch, setResumeSearch] = useState('')
  const [resumeDropdownOpen, setResumeDropdownOpen] = useState(false)
  const [jobSearch, setJobSearch] = useState('')
  const [tailorMode, setTailorMode] = useState('tailor') // 'tailor' or 'copy'
  const [showDiffModal, setShowDiffModal] = useState(false)
  const [baseData, setBaseData] = useState(null)
  const [diffDecisions, setDiffDecisions] = useState({})
  const [scoreChecking, setScoreChecking] = useState(null) // null | 'light' | 'full'
  const [scoreResult, setScoreResult] = useState(null)
  const [jobUrl, setJobUrl] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [jobMenuOpen, setJobMenuOpen] = useState(false)
  const [applyingJob, setApplyingJob] = useState(false)
  const saveTimeoutRef = useRef(null)
  const pdfInputRef = useRef(null)

  useEffect(() => {
    api.get('/resumes/templates').then(({ data }) => {
      setTemplates(data)
      if (data.length && !template) setTemplate(data[0].id)
    }).catch(() => {})
    fetchResumes()
  }, [])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.resume-picker')) setResumeDropdownOpen(false)
      if (!e.target.closest('.job-menu')) setJobMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchResumes = async () => {
    try {
      const { data } = await api.get('/resumes')
      setResumes(data)
      const targetId = searchParams.get('resume')
      if (targetId) {
        const target = data.find(r => r.id === targetId)
        if (target) {
          selectResume(target)
          setSearchParams({}, { replace: true })
        } else if (data.length > 0 && !selectedId) {
          selectResume(data[0])
        }
      } else if (data.length > 0 && !selectedId) {
        selectResume(data[0])
      }
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  const selectResume = async (r) => {
    setDataLoaded(false)
    setScoreResult(null)
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    setSelectedId(r.id)
    setTemplate(r.template || 'garamond')
    setPageFormat(r.page_format || 'letter')
    // Always fetch full resume with json_data
    try {
      const { data } = await api.get(`/resumes/${r.id}`)
      setEditData(data.json_data || { ...EMPTY_DATA })
    } catch (e) {
      console.error('Failed to load resume data', e)
      setEditData({ ...EMPTY_DATA })
    }
    // Load saved score + job URL for tailored resumes
    setJobUrl(null)
    setJobId(r.job_id || null)
    setJobMenuOpen(false)
    if (r.job_id && !r.is_base) {
      try {
        const { data: job } = await api.get(`/jobs/${r.job_id}`)
        if (job.url) setJobUrl(job.url)
        const scores = job.cv_scores || {}
        const tailoredScore = scores['Tailored']
        if (tailoredScore != null) {
          const numeric = Object.entries(scores).filter(([k, v]) => k !== 'Tailored' && typeof v === 'number')
          const originalScore = numeric.length ? Math.max(...numeric.map(([, v]) => v)) : null
          setScoreResult({
            original_score: originalScore,
            tailored_score: tailoredScore,
            delta: originalScore != null ? tailoredScore - originalScore : null,
          })
        }
      } catch {}
    }
    setDataLoaded(true)
    setPreviewKey(k => k + 1)
  }

  const triggerSave = (updatedData, tmpl, fmt) => {
    if (!dataLoaded) return
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(async () => {
      if (!selectedId) return
      setSaving(true)
      try {
        await api.patch(`/resumes/${selectedId}`, {
          json_data: updatedData || editData,
          template: tmpl || template,
          page_format: fmt || pageFormat,
        })
        setPreviewKey(k => k + 1)
      } catch (e) {
        console.error(e)
      }
      setSaving(false)
    }, 500)
  }

  // Guard against prototype pollution when the user (or a caller) injects
  // special keys like "__proto__", "constructor", or "prototype" into the
  // dotted `path` argument. Such keys would otherwise let a recursive set
  // walk off the edit object and mutate Object.prototype.
  const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

  const updateField = (path, value) => {
    const keys = String(path).split('.')
    if (keys.some(k => DANGEROUS_KEYS.has(k))) {
      console.warn('updateField: refusing to write reserved key in path', path)
      return
    }
    const updated = JSON.parse(JSON.stringify(editData))
    let obj = updated
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i]
      if (obj == null || typeof obj !== 'object') return
      obj = obj[k]
    }
    if (obj == null || typeof obj !== 'object') return
    obj[keys[keys.length - 1]] = value
    setEditData(updated)
    triggerSave(updated)
  }

  const createResume = async () => {
    if (!newName.trim()) return
    try {
      const { data } = await api.post('/resumes', { name: newName.trim(), json_data: { ...EMPTY_DATA } })
      setNewName('')
      await fetchResumes()
      selectResume(data)
    } catch (e) {
      console.error(e)
    }
  }

  const deleteResume = async (id) => {
    if (!confirm('Delete this resume?')) return
    try {
      await api.delete(`/resumes/${id}`)
      if (selectedId === id) {
        setSelectedId(null)
        setEditData(null)
      }
      await fetchResumes()
    } catch (e) {
      console.error(e)
    }
  }

  const importPdf = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data: parsed } = await api.post('/resumes/import-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const name = file.name.replace(/\.pdf$/i, '')
      const { data: created } = await api.post('/resumes', { name, json_data: parsed.json_data })
      await fetchResumes()
      selectResume(created)
    } catch (e) {
      console.error(e)
      alert('PDF import failed: ' + (e.response?.data?.detail || e.message))
    }
    if (pdfInputRef.current) pdfInputRef.current.value = ''
  }

  const loadRecentJobs = async () => {
    try {
      const { data } = await api.get('/jobs?limit=50&sort_by=date&status=saved,applied')
      setRecentJobs(data.jobs || [])
    } catch (e) { console.error(e) }
  }

  const tailorForJob = async () => {
    if (!selectedId) return
    if (!tailorJobId && !tailorJdText.trim()) return
    setTailoring(true)
    try {
      let data
      if (tailorMode === 'copy') {
        const resp = await api.post('/resumes/copy', { base_resume_id: selectedId, job_id: tailorJobId })
        data = resp.data
      } else {
        const payload = { base_resume_id: selectedId }
        if (tailorJobId) payload.job_id = tailorJobId
        else payload.job_description = tailorJdText.trim()
        const resp = await api.post('/resumes/tailor', payload)
        data = resp.data
      }
      await fetchResumes()
      selectResume(data)
      setShowTailorModal(false)
      setTailorJobId('')
      setTailorJdText('')
    } catch (e) {
      console.error(e)
      alert((tailorMode === 'copy' ? 'Copy' : 'Tailoring') + ' failed: ' + (e.response?.data?.detail || e.message))
    }
    setTailoring(false)
  }

  const openDiffModal = async () => {
    const current = resumes.find(r => r.id === selectedId)
    if (!current?.parent_id) return
    try {
      const { data } = await api.get(`/resumes/${current.parent_id}`)
      setBaseData(data.json_data || {})
      setDiffDecisions({})
      setShowDiffModal(true)
    } catch (e) {
      console.error('Failed to load base resume for diff', e)
    }
  }

  const applyDiffDecisions = () => {
    if (!baseData || !editData) return
    const updated = JSON.parse(JSON.stringify(editData))

    // Summary
    if (diffDecisions.summary === 'reject') {
      updated.summary = baseData.summary || ''
    }

    // Skills
    if (diffDecisions.skills === 'reject') {
      updated.skills = baseData.skills || {}
    }

    // Experience bullets
    const baseExp = baseData.experience || []
    ;(updated.experience || []).forEach((exp, ei) => {
      const baseJob = baseExp[ei]
      if (!baseJob) return

      // Per-bullet decisions
      ;(exp.bullets || []).forEach((_, bi) => {
        const key = `exp.${ei}.bullet.${bi}`
        if (diffDecisions[key] === 'reject' && baseJob.bullets?.[bi]) {
          exp.bullets[bi] = baseJob.bullets[bi]
        }
      })

      // Suggested bullets
      const accepted = []
      ;(exp.suggested_bullets || []).forEach((sb, si) => {
        const key = `exp.${ei}.suggested.${si}`
        if (diffDecisions[key] === 'accept') {
          accepted.push(sb)
        }
      })
      if (accepted.length > 0) {
        exp.bullets = [...(exp.bullets || []), ...accepted]
      }
      // Remove all suggested_bullets after processing
      delete exp.suggested_bullets
    })

    setEditData(updated)
    triggerSave(updated)
    setShowDiffModal(false)
  }

  const changeTemplate = async (tmplId) => {
    setTemplate(tmplId)
    triggerSave(editData, tmplId, pageFormat)
  }

  const changeFormat = async (fmt) => {
    setPageFormat(fmt)
    triggerSave(editData, template, fmt)
  }

  const pdfDownloadUrl = selectedId
    ? (api.defaults.baseURL || '').replace('/api', '') + '/api/resumes/' + selectedId + '/pdf?template=' + template + '&format=' + pageFormat
    : null

  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null)
  const prevBlobRef = useRef(null)

  // Fetch actual PDF for preview as blob URL
  useEffect(() => {
    if (!selectedId) { setPdfPreviewUrl(null); return }
    const fetchPdf = async () => {
      try {
        const r = await api.get(`/resumes/${selectedId}/pdf?template=${template}&format=${pageFormat}`, { responseType: 'arraybuffer' })
        const blob = new Blob([r.data], { type: 'application/pdf' })
        const url = URL.createObjectURL(blob)
        if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current)
        prevBlobRef.current = url
        setPdfPreviewUrl(url + '#view=FitH')
      } catch {
        setPdfPreviewUrl(null)
      }
    }
    const timer = setTimeout(fetchPdf, 800)
    return () => clearTimeout(timer)
  }, [previewKey, selectedId, template, pageFormat])

  useEffect(() => {
    if (!selectedId) { setTracerStats([]); return }
    const r = resumes.find(r => r.id === selectedId)
    if (!r || r.is_base) { setTracerStats([]); return }
    api.get(`/resumes/${selectedId}/tracer-stats`).then(({ data }) => setTracerStats(data)).catch(() => setTracerStats([]))
  }, [selectedId, previewKey])

  // --- Local state helpers for controlled inputs ---
  // We keep local state for inputs and only commit on blur

  const addExperience = () => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.experience = updated.experience || []
    updated.experience.push({ company: '', title: '', location: '', date: '', description: '', bullets: [] })
    setEditData(updated)
    triggerSave(updated)
  }

  const removeExperience = (idx) => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.experience.splice(idx, 1)
    setEditData(updated)
    triggerSave(updated)
  }

  const addEducation = () => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.education = updated.education || []
    updated.education.push({ school: '', location: '', degree: '' })
    setEditData(updated)
    triggerSave(updated)
  }

  const removeEducation = (idx) => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.education.splice(idx, 1)
    setEditData(updated)
    triggerSave(updated)
  }

  const addProject = () => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.projects = updated.projects || []
    updated.projects.push({ name: '', description: '', url: '', bullets: [] })
    setEditData(updated)
    triggerSave(updated)
  }

  const removeProject = (idx) => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.projects.splice(idx, 1)
    setEditData(updated)
    triggerSave(updated)
  }

  const addPublication = () => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.publications = updated.publications || []
    updated.publications.push({ title: '', description: '' })
    setEditData(updated)
    triggerSave(updated)
  }

  const removePublication = (idx) => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.publications.splice(idx, 1)
    setEditData(updated)
    triggerSave(updated)
  }

  const addSkillRow = () => {
    const updated = JSON.parse(JSON.stringify(editData))
    updated.skills = updated.skills || {}
    const key = `Skill ${Object.keys(updated.skills).length + 1}`
    updated.skills[key] = ''
    setEditData(updated)
    triggerSave(updated)
  }

  const removeSkillRow = (key) => {
    const updated = JSON.parse(JSON.stringify(editData))
    delete updated.skills[key]
    setEditData(updated)
    triggerSave(updated)
  }

  const renameSkillKey = (oldKey, newKey) => {
    if (oldKey === newKey || !newKey.trim()) return
    const updated = JSON.parse(JSON.stringify(editData))
    const entries = Object.entries(updated.skills)
    const newSkills = {}
    for (const [k, v] of entries) {
      newSkills[k === oldKey ? newKey : k] = v
    }
    updated.skills = newSkills
    setEditData(updated)
    triggerSave(updated)
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-gray-500 dark:text-gray-400">
        <Loader2 size={18} className="animate-spin" /> Loading...
      </div>
    )
  }

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Top bar: resume picker + download + add */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative resume-picker flex-shrink-0">
          <div className="relative">
            <input
              type="text"
              placeholder={selectedId ? (() => { const r = resumes.find(r => r.id === selectedId); return r ? `[${r.is_base ? 'base' : 'tailored'}] ${r.name}` : 'Search resumes...' })() : 'Search resumes...'}
              value={resumeSearch}
              onChange={e => { setResumeSearch(e.target.value); setResumeDropdownOpen(true) }}
              onFocus={() => setResumeDropdownOpen(true)}
              className="border rounded px-3 py-1.5 text-sm w-96 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600 pr-8"
            />
            {selectedId && !resumeSearch && (
              <button onClick={(e) => { e.stopPropagation(); e.preventDefault(); deleteResume(selectedId) }}
                onMouseDown={(e) => e.preventDefault()}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-red-500 dark:text-gray-600 dark:hover:text-red-400 z-10" title="Delete resume">
                <X size={14} />
              </button>
            )}
          </div>
          {resumeDropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-96 max-h-72 overflow-y-auto bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-lg shadow-lg z-50">
              {(() => {
                const search = resumeSearch.toLowerCase()
                const bases = resumes.filter(r => r.is_base)
                const tailored = resumes.filter(r => !r.is_base)
                const recentTailored = tailored.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')).slice(0, 10)
                let filtered
                if (search) {
                  filtered = resumes.filter(r => r.name.toLowerCase().includes(search))
                } else {
                  filtered = [...bases, ...recentTailored]
                }
                if (filtered.length === 0) {
                  return <div className="px-3 py-2 text-xs text-gray-400">No resumes found</div>
                }
                return filtered.map(r => (
                  <button key={r.id}
                    onClick={() => { selectResume(r); setResumeSearch(''); setResumeDropdownOpen(false) }}
                    className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between ${
                      r.id === selectedId ? 'bg-blue-50 dark:bg-blue-900/30' : ''
                    }`}>
                    <span className={!r.is_base ? 'pl-3' : ''}>{r.name}</span>
                    {r.is_base && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400">base</span>}
                  </button>
                ))
              })()}
            </div>
          )}
        </div>

        {pdfDownloadUrl && selectedId && (
          <a href={pdfDownloadUrl} target="_blank" rel="noopener noreferrer"
            className="bg-blue-600 text-white px-2.5 py-1.5 rounded text-sm hover:bg-blue-700 flex items-center gap-1 flex-shrink-0">
            <Download size={14} /> Download PDF
          </a>
        )}
        {jobId && (
          <div className="relative job-menu flex-shrink-0">
            <button onClick={() => setJobMenuOpen(!jobMenuOpen)}
              className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-2.5 py-1.5 rounded text-sm hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center gap-1">
              <Briefcase size={14} /> Job <ChevronDown size={12} />
            </button>
            {jobMenuOpen && (
              <div className="absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded shadow-lg z-50 min-w-[160px] py-1">
                <a href={`/?job=${jobId}`}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 w-full"
                  onClick={() => setJobMenuOpen(false)}>
                  <Briefcase size={14} /> Open in Job Feed
                </a>
                {jobUrl && (
                  <a href={jobUrl} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 w-full"
                    onClick={() => setJobMenuOpen(false)}>
                    <ExternalLink size={14} /> Open Job Link
                  </a>
                )}
                <button
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 w-full text-left"
                  disabled={applyingJob}
                  onClick={async () => {
                    setApplyingJob(true)
                    try {
                      await api.patch(`/jobs/${jobId}`, { status: 'applied' })
                      setJobMenuOpen(false)
                    } catch (e) { console.error(e) }
                    setApplyingJob(false)
                  }}>
                  <CheckCircle2 size={14} /> {applyingJob ? 'Applying...' : 'Set as Applied'}
                </button>
              </div>
            )}
          </div>
        )}
        {saving && (
          <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" /> Saving...
          </span>
        )}

        <button onClick={() => { setNewName(''); setShowAddModal(true) }}
          className="ml-auto bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700 flex items-center gap-1 flex-shrink-0">
          <Plus size={14} /> Add Resume
        </button>
        <input ref={pdfInputRef} type="file" accept=".pdf" className="hidden" onChange={async (e) => {
          const file = e.target.files?.[0]
          if (!file || !newName.trim()) return
          setImporting(true)
          try {
            const formData = new FormData()
            formData.append('file', file)
            const { data: parsed } = await api.post('/resumes/import-pdf', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
            const { data: created } = await api.post('/resumes', { name: newName.trim(), json_data: parsed.json_data })
            await fetchResumes()
            selectResume(created)
            setShowAddModal(false)
          } catch (err) {
            alert('PDF import failed: ' + (err.response?.data?.detail || err.message))
          }
          setImporting(false)
          if (pdfInputRef.current) pdfInputRef.current.value = ''
        }} />
      </div>

      {/* Add Resume modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-[400px] relative">
            <button onClick={() => setShowAddModal(false)} disabled={importing}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-50">
              <X size={18} />
            </button>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Add Resume</h3>
            <div className="mb-5">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Name</label>
              <input type="text" value={newName} onChange={e => setNewName(e.target.value)}
                placeholder="e.g. PM, TPgM, PjM..."
                className="border rounded px-3 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" autoFocus />
            </div>
            {importing && (
              <div className="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-4">
                <Loader2 size={16} className="animate-spin" /> Importing PDF and extracting data...
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <button onClick={async () => {
                if (!newName.trim()) return
                const { data } = await api.post('/resumes', { name: newName.trim(), json_data: { ...EMPTY_DATA } })
                await fetchResumes()
                selectResume(data)
                setShowAddModal(false)
                setNewName('')
              }} disabled={!newName.trim() || importing}
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-1">
                <Plus size={14} /> Create from Scratch
              </button>
              <button onClick={() => pdfInputRef.current?.click()} disabled={!newName.trim() || importing}
                className="px-3 py-2 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50 flex items-center justify-center gap-1">
                <Upload size={14} /> Import Existing
              </button>
            </div>
          </div>
        </div>
      )}

      {!editData ? (
        <div className="text-gray-500 dark:text-gray-400 text-sm">
          No resume selected. Create one or import a PDF to get started.
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-4 flex-1 min-h-0">
          {/* Left panel: form editor */}
          <div className="col-span-2 overflow-auto pr-1">
            {/* Actions bar */}
            <div className="flex items-center gap-2 flex-wrap mb-3 text-xs">
              {selectedId && !resumes.find(r => r.id === selectedId)?.is_base && (
                <>
                  <button onClick={() => {
                    const r = resumes.find(r => r.id === selectedId)
                    if (r?.parent_id && r?.job_id) {
                      setTailoring(true)
                      api.post('/resumes/tailor', { base_resume_id: r.parent_id, job_id: r.job_id })
                        .then(async ({ data }) => { await fetchResumes(); selectResume(data); setTailoring(false) })
                        .catch(e => { alert('Re-tailor failed: ' + e.message); setTailoring(false) })
                    }
                  }} disabled={tailoring}
                    className="text-xs px-2.5 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1">
                    <Wand2 size={12} /> {tailoring ? 'Tailoring...' : 'Re-tailor'}
                  </button>
                  {resumes.find(r => r.id === selectedId)?.parent_id && (
                    <button onClick={openDiffModal}
                      className="text-xs px-2.5 py-1 border border-purple-300 text-purple-700 rounded hover:bg-purple-50 dark:border-purple-700 dark:text-purple-300 dark:hover:bg-purple-900/30">
                      Review Changes
                    </button>
                  )}
                  {resumes.find(r => r.id === selectedId)?.job_id && (
                    <div className="inline-flex">
                      <button onClick={async () => {
                        setScoreChecking('light'); setScoreResult(null)
                        try {
                          const { data } = await api.post(`/resumes/${selectedId}/score-check`, { depth: 'light' })
                          setScoreResult(data)
                        } catch (e) { alert('Score failed: ' + (e.response?.data?.detail || e.message)) }
                        setScoreChecking(null)
                      }} disabled={!!scoreChecking}
                        className="text-xs px-2 py-1 border border-green-300 text-green-700 rounded-l hover:bg-green-50 dark:border-green-700 dark:text-green-300 dark:hover:bg-green-900/30 disabled:opacity-50 flex items-center gap-1">
                        {scoreChecking === 'light' ? <><Loader2 size={12} className="animate-spin" /> Scoring...</> : 'Quick Score'}
                      </button>
                      <button onClick={async () => {
                        setScoreChecking('full'); setScoreResult(null)
                        try {
                          const { data } = await api.post(`/resumes/${selectedId}/score-check`, { depth: 'full' })
                          setScoreResult(data)
                        } catch (e) { alert('Score failed: ' + (e.response?.data?.detail || e.message)) }
                        setScoreChecking(null)
                      }} disabled={!!scoreChecking}
                        className="text-xs px-2 py-1 border border-l-0 border-green-300 text-green-700 rounded-r hover:bg-green-50 dark:border-green-700 dark:text-green-300 dark:hover:bg-green-900/30 disabled:opacity-50 flex items-center gap-1">
                        {scoreChecking === 'full' ? <><Loader2 size={12} className="animate-spin" /> Scoring...</> : 'Full Score'}
                      </button>
                    </div>
                  )}
                  {scoreResult && (
                    <span className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 ml-1">
                      {scoreResult.original_score != null && <>Original: <span className="font-semibold text-gray-700 dark:text-gray-300">{scoreResult.original_score}</span></>}
                      {scoreResult.tailored_score != null && <>
                        {scoreResult.original_score != null && <span>→</span>}
                        <span className={`font-semibold ${scoreResult.delta > 0 ? 'text-green-600 dark:text-green-400' : scoreResult.delta < 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}>{scoreResult.tailored_score}</span>
                      </>}
                      {scoreResult.delta != null && scoreResult.delta !== 0 && (
                        <span className={scoreResult.delta > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                          ({scoreResult.delta > 0 ? '+' : ''}{scoreResult.delta})
                        </span>
                      )}
                      <button onClick={() => setScoreResult(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 ml-0.5">
                        <X size={12} />
                      </button>
                    </span>
                  )}
                </>
              )}
              {selectedId && editData && resumes.find(r => r.id === selectedId)?.is_base && (
                <>
                  <button
                    onClick={() => { setTailorMode('tailor'); loadRecentJobs(); setJobSearch(''); setShowTailorModal(true) }}
                    className="text-xs px-2.5 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 flex items-center gap-1">
                    <Wand2 size={12} /> Tailor
                  </button>
                  <button
                    onClick={() => { setTailorMode('copy'); loadRecentJobs(); setJobSearch(''); setShowTailorModal(true) }}
                    className="text-xs px-2.5 py-1 border border-purple-300 text-purple-700 rounded hover:bg-purple-50 dark:border-purple-700 dark:text-purple-300 dark:hover:bg-purple-900/30">
                    Copy for Job
                  </button>
                </>
              )}
              {tracerStats.length > 0 && (
                <div className="flex items-center gap-2 text-[10px] text-gray-500 dark:text-gray-400 ml-auto">
                  {tracerStats.map(s => (
                    <span key={s.token} title={`${s.destination_url} - Last: ${s.last_clicked || 'never'}`}>
                      {s.source_label}: <span className={s.clicks > 0 ? 'text-green-600 dark:text-green-400 font-medium' : ''}>{s.clicks}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
            {/* Template picker */}
            <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-4">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">Template</label>
              <div className="flex gap-2 flex-wrap">
                {TEMPLATES.map(t => (
                  <button
                    key={t.id}
                    onClick={() => changeTemplate(t.id)}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      template === t.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 mt-3">Page Format</label>
              <div className="flex gap-2">
                {PAGE_FORMATS.map(f => (
                  <button
                    key={f.id}
                    onClick={() => changeFormat(f.id)}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      pageFormat === f.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Header */}
            <CollapsibleSection title="Header">
              <FieldInput label="Name" value={editData.header?.name} onChange={v => updateField('header.name', v)} />
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Contact Items</label>
                {(editData?.header?.contact_items || []).map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2 mb-1.5">
                    <div className="flex flex-col">
                      <button onClick={() => {
                        if (idx === 0) return
                        const updated = JSON.parse(JSON.stringify(editData))
                        const temp = updated.header.contact_items[idx]
                        updated.header.contact_items[idx] = updated.header.contact_items[idx - 1]
                        updated.header.contact_items[idx - 1] = temp
                        setEditData(updated)
                        triggerSave(updated)
                      }} disabled={idx === 0} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowUp size={11} /></button>
                      <button onClick={() => {
                        if (idx === (editData?.header?.contact_items || []).length - 1) return
                        const updated = JSON.parse(JSON.stringify(editData))
                        const temp = updated.header.contact_items[idx]
                        updated.header.contact_items[idx] = updated.header.contact_items[idx + 1]
                        updated.header.contact_items[idx + 1] = temp
                        setEditData(updated)
                        triggerSave(updated)
                      }} disabled={idx === (editData?.header?.contact_items || []).length - 1} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowDown size={11} /></button>
                    </div>
                    <input
                      type="text"
                      value={item.text || ''}
                      placeholder="Display text"
                      onChange={e => {
                        const updated = JSON.parse(JSON.stringify(editData))
                        updated.header.contact_items[idx].text = e.target.value
                        setEditData(updated)
                      }}
                      onBlur={() => triggerSave(editData)}
                      className="border rounded px-2 py-1 text-sm w-36 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                    />
                    <input
                      type="text"
                      value={item.url || ''}
                      placeholder="URL (optional)"
                      onChange={e => {
                        const updated = JSON.parse(JSON.stringify(editData))
                        updated.header.contact_items[idx].url = e.target.value
                        setEditData(updated)
                      }}
                      onBlur={() => triggerSave(editData)}
                      className="border rounded px-2 py-1 text-sm flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                    />
                    {item.url && !item.url.startsWith('mailto:') && (
                      <input
                        type="text"
                        value={item.stub || ''}
                        placeholder="id"
                        title="Short stub for tracer link ID (e.g. l, w, gh)"
                        onChange={e => {
                          const updated = JSON.parse(JSON.stringify(editData))
                          updated.header.contact_items[idx].stub = e.target.value
                          setEditData(updated)
                        }}
                        onBlur={() => triggerSave(editData)}
                        className="border rounded px-2 py-1 text-sm w-12 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                      />
                    )}
                    <button onClick={() => {
                      const updated = JSON.parse(JSON.stringify(editData))
                      updated.header.contact_items.splice(idx, 1)
                      setEditData(updated)
                      triggerSave(updated)
                    }} className="text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"><Trash2 size={14} /></button>
                  </div>
                ))}
                <button onClick={() => {
                  const updated = JSON.parse(JSON.stringify(editData))
                  if (!updated.header.contact_items) updated.header.contact_items = []
                  updated.header.contact_items.push({text: '', url: ''})
                  setEditData(updated)
                }} className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1 mt-1">
                  <Plus size={12} /> Add Item
                </button>
              </div>
            </CollapsibleSection>

            {/* Summary */}
            <CollapsibleSection title="Summary">
              <FieldInput
                multiline
                rows={4}
                value={editData.summary}
                onChange={v => updateField('summary', v)}
                placeholder="Professional summary..."
              />
            </CollapsibleSection>

            {/* Experience */}
            <CollapsibleSection title="Experience" badge={editData.experience?.length || 0}>
              {(editData.experience || []).map((exp, idx) => (
                <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
                  <button
                    onClick={() => removeExperience(idx)}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                  <div className="grid grid-cols-2 gap-x-3">
                    <FieldInput label="Company" value={exp.company} onChange={v => updateField(`experience.${idx}.company`, v)} />
                    <FieldInput label="Title" value={exp.title} onChange={v => updateField(`experience.${idx}.title`, v)} />
                    <FieldInput label="Location" value={exp.location} onChange={v => updateField(`experience.${idx}.location`, v)} />
                    <FieldInput label="Date" value={exp.date} onChange={v => updateField(`experience.${idx}.date`, v)} placeholder="Jan 2022 - Present" />
                  </div>
                  <FieldInput label="Description" value={exp.description} onChange={v => updateField(`experience.${idx}.description`, v)} placeholder="Optional role description" />
                  <FieldInput
                    label="Bullets"
                    multiline
                    rows={4}
                    value={(exp.bullets || []).join('\n')}
                    onChange={v => updateField(`experience.${idx}.bullets`, v.split('\n'))}
                    placeholder="One bullet per line"
                  />
                  {exp.suggested_bullets && exp.suggested_bullets.length > 0 && (
                    <div className="mt-2 p-2 bg-purple-50 dark:bg-purple-900/20 rounded border border-purple-200 dark:border-purple-800">
                      <label className="block text-[10px] font-medium text-purple-600 dark:text-purple-400 mb-1">LLM Suggested Bullets</label>
                      {exp.suggested_bullets.map((sb, sbi) => (
                        <div key={sbi} className="text-xs text-purple-700 dark:text-purple-300 mb-1 flex items-start gap-1">
                          <span className="text-purple-400 mt-0.5">+</span>
                          <span>{sb}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <button onClick={addExperience} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm flex items-center gap-1">
                <Plus size={14} /> Add Experience
              </button>
            </CollapsibleSection>

            {/* Skills */}
            <CollapsibleSection title="Skills" badge={Object.keys(editData.skills || {}).length}>
              {Object.entries(editData.skills || {}).map(([key, value]) => (
                <div key={key} className="flex gap-2 mb-2 items-start">
                  <input
                    type="text"
                    className="border rounded px-2 py-1.5 text-sm w-1/3 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                    defaultValue={key}
                    onBlur={e => renameSkillKey(key, e.target.value)}
                    placeholder="Category"
                  />
                  <input
                    type="text"
                    className="border rounded px-2 py-1.5 text-sm flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                    value={value}
                    onChange={e => updateField(`skills.${key}`, e.target.value)}
                    placeholder="Skill values..."
                  />
                  <button onClick={() => removeSkillRow(key)} className="text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 mt-1">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <button onClick={addSkillRow} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm flex items-center gap-1">
                <Plus size={14} /> Add Skill Row
              </button>
            </CollapsibleSection>

            {/* Education */}
            <CollapsibleSection title="Education" badge={editData.education?.length || 0}>
              {(editData.education || []).map((edu, idx) => (
                <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
                  <button
                    onClick={() => removeEducation(idx)}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                  <div className="grid grid-cols-2 gap-x-3">
                    <FieldInput label="School" value={edu.school} onChange={v => updateField(`education.${idx}.school`, v)} />
                    <FieldInput label="Location" value={edu.location} onChange={v => updateField(`education.${idx}.location`, v)} />
                  </div>
                  <FieldInput label="Degree" value={edu.degree} onChange={v => updateField(`education.${idx}.degree`, v)} />
                </div>
              ))}
              <button onClick={addEducation} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm flex items-center gap-1">
                <Plus size={14} /> Add Education
              </button>
            </CollapsibleSection>

            {/* Projects */}
            <CollapsibleSection title="Projects" defaultOpen={(editData.projects || []).length > 0} badge={editData.projects?.length || 0}>
              {(editData.projects || []).map((proj, idx) => (
                <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
                  <button
                    onClick={() => removeProject(idx)}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                  <div className="grid grid-cols-2 gap-x-3">
                    <FieldInput label="Name" value={proj.name} onChange={v => updateField(`projects.${idx}.name`, v)} />
                    <FieldInput label="URL" value={proj.url} onChange={v => updateField(`projects.${idx}.url`, v)} />
                  </div>
                  <FieldInput label="Description" value={proj.description} onChange={v => updateField(`projects.${idx}.description`, v)} />
                  <FieldInput
                    label="Bullets"
                    multiline
                    rows={3}
                    value={(proj.bullets || []).join('\n')}
                    onChange={v => updateField(`projects.${idx}.bullets`, v.split('\n'))}
                    placeholder="One bullet per line"
                  />
                </div>
              ))}
              <button onClick={addProject} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm flex items-center gap-1">
                <Plus size={14} /> Add Project
              </button>
            </CollapsibleSection>

            {/* Publications */}
            <CollapsibleSection title="Publications" defaultOpen={(editData.publications || []).length > 0} badge={editData.publications?.length || 0}>
              {(editData.publications || []).map((pub, idx) => (
                <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
                  <button
                    onClick={() => removePublication(idx)}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                  <FieldInput label="Title" value={pub.title} onChange={v => updateField(`publications.${idx}.title`, v)} />
                  <FieldInput label="Description" value={pub.description} onChange={v => updateField(`publications.${idx}.description`, v)} />
                </div>
              ))}
              <button onClick={addPublication} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 text-sm flex items-center gap-1">
                <Plus size={14} /> Add Publication
              </button>
            </CollapsibleSection>
          </div>

          {/* Right panel: preview */}
          <div className="col-span-3 flex flex-col min-h-0">
            {pdfPreviewUrl ? (
              <iframe
                key={pdfPreviewUrl}
                src={pdfPreviewUrl}
                className="flex-1 w-full border rounded-lg bg-white"
                title="Resume Preview"
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400 border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-500">
                Select a resume to preview
              </div>
            )}
          </div>
        </div>
      )}

      {showTailorModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-[500px] max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{tailorMode === 'copy' ? 'Copy Resume for Job' : 'Tailor Resume for Job'}</h3>
            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Select Job</label>
              <input
                type="text"
                placeholder="Search by company or title..."
                value={jobSearch}
                onChange={e => { setJobSearch(e.target.value); setTailorJobId('') }}
                className="border rounded px-2 py-1.5 text-sm w-full mb-2 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              />
              <div className="max-h-40 overflow-y-auto border dark:border-gray-600 rounded">
                {(() => {
                  const search = jobSearch.toLowerCase()
                  const filtered = search
                    ? recentJobs.filter(j => (j.company || '').toLowerCase().includes(search) || (j.title || '').toLowerCase().includes(search))
                    : recentJobs.slice(0, 20)
                  if (filtered.length === 0) return <div className="px-3 py-2 text-xs text-gray-400">No jobs found</div>
                  return filtered.map(j => (
                    <button key={j.id}
                      onClick={() => { setTailorJobId(j.id); setJobSearch(j.company + ' — ' + j.title); setTailorJdText('') }}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 dark:hover:bg-gray-700 border-b dark:border-gray-700 last:border-0 ${
                        tailorJobId === j.id ? 'bg-purple-50 dark:bg-purple-900/30' : ''
                      }`}>
                      <span className="font-medium">{j.company}</span> — {j.title}
                    </button>
                  ))
                })()}
              </div>
            </div>
            {tailorMode !== 'copy' && !tailorJobId && (
              <div className="mb-4">
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Or Paste Job Description</label>
                <textarea value={tailorJdText} onChange={e => setTailorJdText(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                  rows={6} placeholder="Paste job description text here..." />
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowTailorModal(false)}
                className="px-4 py-1.5 text-sm border rounded dark:border-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">Cancel</button>
              <button onClick={tailorForJob} disabled={tailoring || (tailorMode === 'copy' ? !tailorJobId : (!tailorJobId && !tailorJdText.trim()))}
                className="px-4 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2">
                {tailoring ? <><Loader2 size={14} className="animate-spin" /> {tailorMode === 'copy' ? 'Copying...' : 'Tailoring...'}</> : tailorMode === 'copy' ? 'Copy with Tracer Links' : 'Generate Tailored CV'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showDiffModal && baseData && editData && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl w-[800px] max-h-[90vh] overflow-y-auto shadow-2xl">
            {/* Header */}
            <div className="sticky top-0 bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4 flex items-center justify-between z-10">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Review Changes</h2>
              <div className="flex items-center gap-2">
                <button onClick={() => {
                  const all = {}
                  all.summary = 'accept'
                  all.skills = 'accept'
                  ;(editData.experience || []).forEach((exp, ei) => {
                    ;(exp.bullets || []).forEach((_, bi) => { all[`exp.${ei}.bullet.${bi}`] = 'accept' })
                    ;(exp.suggested_bullets || []).forEach((_, si) => { all[`exp.${ei}.suggested.${si}`] = 'accept' })
                  })
                  setDiffDecisions(all)
                }} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200 dark:bg-green-900 dark:text-green-300 dark:hover:bg-green-800">
                  Accept All
                </button>
                <button onClick={() => {
                  const all = {}
                  all.summary = 'reject'
                  all.skills = 'reject'
                  ;(editData.experience || []).forEach((exp, ei) => {
                    ;(exp.bullets || []).forEach((_, bi) => { all[`exp.${ei}.bullet.${bi}`] = 'reject' })
                    ;(exp.suggested_bullets || []).forEach((_, si) => { all[`exp.${ei}.suggested.${si}`] = 'reject' })
                  })
                  setDiffDecisions(all)
                }} className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 dark:bg-red-900 dark:text-red-300 dark:hover:bg-red-800">
                  Reject All
                </button>
              </div>
            </div>

            <div className="px-6 py-4 space-y-6">
              {/* Summary diff */}
              {baseData.summary !== editData.summary && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Summary</h3>
                    <div className="flex gap-1">
                      <button onClick={() => setDiffDecisions(d => ({...d, summary: 'accept'}))}
                        className={`text-xs px-2 py-0.5 rounded ${diffDecisions.summary === 'accept' ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                        Accept
                      </button>
                      <button onClick={() => setDiffDecisions(d => ({...d, summary: 'reject'}))}
                        className={`text-xs px-2 py-0.5 rounded ${diffDecisions.summary === 'reject' ? 'bg-red-500 text-white' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                        Reject
                      </button>
                    </div>
                  </div>
                  <div className="text-sm leading-relaxed text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 rounded p-3">
                    <InlineDiff oldText={baseData.summary} newText={editData.summary} />
                  </div>
                </div>
              )}

              {/* Experience diffs */}
              {(editData.experience || []).map((exp, ei) => {
                const baseJob = (baseData.experience || [])[ei]
                if (!baseJob) return null
                const hasChanges = (exp.bullets || []).some((b, bi) => b !== baseJob.bullets?.[bi]) || (exp.suggested_bullets || []).length > 0
                if (!hasChanges) return null

                return (
                  <div key={ei}>
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                      {exp.company} — {exp.title}
                    </h3>
                    <div className="space-y-2">
                      {(exp.bullets || []).map((bullet, bi) => {
                        const baseBullet = baseJob.bullets?.[bi] || ''
                        if (bullet === baseBullet) return null
                        const key = `exp.${ei}.bullet.${bi}`
                        return (
                          <div key={key} className="flex items-start gap-2 bg-gray-50 dark:bg-gray-900 rounded p-2">
                            <div className="flex-1 text-sm text-gray-700 dark:text-gray-300">
                              <span className="text-gray-400 mr-1">•</span>
                              <InlineDiff oldText={baseBullet} newText={bullet} />
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                              <button onClick={() => setDiffDecisions(d => ({...d, [key]: 'accept'}))}
                                className={`text-xs px-1.5 py-0.5 rounded ${diffDecisions[key] === 'accept' ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                                ✓
                              </button>
                              <button onClick={() => setDiffDecisions(d => ({...d, [key]: 'reject'}))}
                                className={`text-xs px-1.5 py-0.5 rounded ${diffDecisions[key] === 'reject' ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                                ✗
                              </button>
                            </div>
                          </div>
                        )
                      })}

                      {/* Suggested bullets */}
                      {(exp.suggested_bullets || []).map((sb, si) => {
                        const key = `exp.${ei}.suggested.${si}`
                        return (
                          <div key={key} className="flex items-start gap-2 bg-purple-50 dark:bg-purple-900/20 rounded p-2 border border-purple-200 dark:border-purple-800">
                            <div className="flex-1 text-sm text-purple-700 dark:text-purple-300">
                              <span className="text-purple-400 mr-1">+</span>
                              {sb}
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                              <button onClick={() => setDiffDecisions(d => ({...d, [key]: 'accept'}))}
                                className={`text-xs px-1.5 py-0.5 rounded ${diffDecisions[key] === 'accept' ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                                ✓
                              </button>
                              <button onClick={() => setDiffDecisions(d => ({...d, [key]: 'reject'}))}
                                className={`text-xs px-1.5 py-0.5 rounded ${diffDecisions[key] === 'reject' ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                                ✗
                              </button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}

              {/* Skills diff */}
              {JSON.stringify(baseData.skills) !== JSON.stringify(editData.skills) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Skills (reordered)</h3>
                    <div className="flex gap-1">
                      <button onClick={() => setDiffDecisions(d => ({...d, skills: 'accept'}))}
                        className={`text-xs px-2 py-0.5 rounded ${diffDecisions.skills === 'accept' ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                        Accept
                      </button>
                      <button onClick={() => setDiffDecisions(d => ({...d, skills: 'reject'}))}
                        className={`text-xs px-2 py-0.5 rounded ${diffDecisions.skills === 'reject' ? 'bg-red-500 text-white' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                        Reject
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="bg-red-50 dark:bg-red-900/20 rounded p-3">
                      <div className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">Base</div>
                      {Object.entries(baseData.skills || {}).map(([k, v]) => (
                        <div key={k} className="text-gray-700 dark:text-gray-300"><strong>{k}:</strong> {v}</div>
                      ))}
                    </div>
                    <div className="bg-green-50 dark:bg-green-900/20 rounded p-3">
                      <div className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">Tailored</div>
                      {Object.entries(editData.skills || {}).map(([k, v]) => (
                        <div key={k} className="text-gray-700 dark:text-gray-300"><strong>{k}:</strong> {v}</div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 bg-white dark:bg-gray-800 border-t dark:border-gray-700 px-6 py-4 flex justify-end gap-2">
              <button onClick={() => setShowDiffModal(false)}
                className="px-4 py-1.5 text-sm border rounded dark:border-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                Cancel
              </button>
              <button onClick={applyDiffDecisions}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">
                Apply Decisions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
