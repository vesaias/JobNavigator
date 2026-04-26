import React, { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'
import { ChevronDown, ChevronRight, FileText, Info, ClipboardList } from 'lucide-react'
import ResumeContentEditor, { EMPTY_RESUME_DATA } from './ResumeContentEditor'

// Right-column sections — everything except resume_content (which gets the
// dedicated structured editor in the left column). Per-section info is rolled
// up into the column-level header tooltip.
const RIGHT_SECTIONS = [
  { key: 'contact', label: 'Contact', kind: 'object',
    fields: ['name', 'email', 'phone', 'address', 'linkedin', 'github', 'website'],
    usedBy: ['Tailoring (header)', 'Cover letter (header)', 'Autofill (form fields)', 'Outreach'] },
  { key: 'work_auth', label: 'Work Authorization', kind: 'object',
    fields: ['citizenship', 'sponsorship_needed', 'visa_status', 'earliest_start_date'],
    usedBy: ['Autofill (visa / sponsorship questions)'] },
  { key: 'demographics', label: 'Demographics (EEO)', kind: 'object',
    fields: ['gender', 'race', 'veteran_status', 'disability_status'],
    hint: 'All fields default to "decline to answer". Most postings make these optional.',
    usedBy: ['Autofill (EEO sections)'] },
  { key: 'compensation', label: 'Compensation', kind: 'object',
    fields: ['target_min', 'target_max', 'currency', 'notes'],
    usedBy: ['Autofill (salary expectation fields)', 'Cover letter (when "expected comp" asked)'] },
  { key: 'preferences', label: 'Preferences', kind: 'object',
    fields: ['remote', 'hybrid_ok', 'onsite_ok', 'willing_to_relocate', 'preferred_locations', 'availability_notes'],
    usedBy: ['Autofill (work model / relocation fields)', 'Future: filter scraped jobs'] },
  { key: 'qa_bank', label: 'Q&A Bank', kind: 'array',
    hint: 'Reusable answers to free-text application questions ("Why this company?", "Comp expectations")',
    usedBy: ['Autofill (free-text screener questions)', 'Cover letter (custom prompts / motivations)'] },
  { key: 'writing_samples', label: 'Writing Samples', kind: 'array',
    hint: 'Voice anchors — short paragraphs the cover letter generator uses for tone',
    usedBy: ['Cover letter (voice / tone anchors)'] },
]

export default function Persona() {
  const [persona, setPersona] = useState(null)
  const [open, setOpen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('persona_open_sections') || '["contact"]') }
    catch { return ['contact'] }
  })
  const [savedFlash, setSavedFlash] = useState('')
  const debounceTimerRef = useRef(null)
  const nodeDebounceRef = useRef({})  // per-key debounce timers for autofill nodes

  const fetchPersona = useCallback(async () => {
    const { data } = await api.get('/persona')
    setPersona(data)
  }, [])

  useEffect(() => { fetchPersona() }, [fetchPersona])
  useEffect(() => { localStorage.setItem('persona_open_sections', JSON.stringify(open)) }, [open])

  const toggle = (k) => setOpen(prev => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k])

  const flashSaved = () => {
    setSavedFlash('Saved')
    setTimeout(() => setSavedFlash(''), 1800)
  }

  // Immediate save (used for array editors that validate JSON on blur).
  const saveNode = async (key, value) => {
    try {
      const { data } = await api.patch('/persona', { [key]: value })
      setPersona(data)
      flashSaved()
    } catch (e) { alert(`Failed to save ${key}: ${e.response?.data?.detail || e.message}`) }
  }

  // Debounced save for object-shaped autofill nodes (contact, work_auth, ...).
  // Mirrors the keystroke-debounced behavior of the Resume Content editor so both
  // columns feel identical from the user's POV.
  const saveNodeDebounced = (key, value) => {
    setPersona(prev => prev ? { ...prev, [key]: value } : prev)
    if (nodeDebounceRef.current[key]) clearTimeout(nodeDebounceRef.current[key])
    nodeDebounceRef.current[key] = setTimeout(async () => {
      try {
        const { data } = await api.patch('/persona', { [key]: value })
        setPersona(data)
        flashSaved()
      } catch (e) { console.error(`Failed to save ${key}:`, e) }
    }, 500)
  }

  // Debounced save for resume_content (typing-frequent edits) — keeps local state
  // optimistically updated and PATCHes 500ms after the last change.
  const saveResumeContentDebounced = (next) => {
    setPersona(prev => prev ? { ...prev, resume_content: next } : prev)
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const { data } = await api.patch('/persona', { resume_content: next })
        setPersona(data)
        flashSaved()
      } catch (e) { console.error('Failed to save resume_content:', e) }
    }, 500)
  }

  if (!persona) return <div className="p-6 text-sm text-gray-500">Loading persona…</div>

  return (
    <div className="p-6">
      {savedFlash && (
        <div className="fixed top-4 right-8 z-50 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm">
          {savedFlash}
        </div>
      )}
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Persona</h1>

      <div className="grid grid-cols-5 gap-4 mt-4">
        {/* Left column — Resume Content. col-span-2 of grid-cols-5 with gap-4 mirrors
            the editor pane on /resumes byte-for-byte (same grid template, same gap). */}
        <div className="col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <FileText size={14} className="text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Resume Content</h2>
            <span className="relative group inline-flex">
              <Info size={12} className="text-gray-400 cursor-help" />
              <span className="invisible group-hover:visible absolute left-5 top-1/2 -translate-y-1/2 z-10 w-80 px-3 py-2 rounded bg-gray-900 dark:bg-gray-700 text-gray-100 text-[11px] font-normal shadow-lg leading-relaxed">
                Your full work history, summary, skills, and achievements. The AI uses this as the source pool for tailored resumes (so it has lots of bullets to pick from), as raw material for cover letter anecdotes, and as the candidate profile when scoring jobs.
              </span>
            </span>
            <span className="text-[11px] text-gray-400 dark:text-gray-500 ml-auto">Saves automatically</span>
          </div>
          <ResumeContentEditor
            value={persona.resume_content || EMPTY_RESUME_DATA}
            onChange={saveResumeContentDebounced}
          />
        </div>

        {/* Right column — same col-span-2 of 5 as left, also matching /resumes editor.
            The 5th grid column is left implicit and becomes trailing whitespace. */}
        <div className="col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList size={14} className="text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100">Autofill Content</h2>
            <span className="relative group inline-flex">
              <Info size={12} className="text-gray-400 cursor-help" />
              <span className="invisible group-hover:visible absolute left-5 top-1/2 -translate-y-1/2 z-10 w-80 px-3 py-2 rounded bg-gray-900 dark:bg-gray-700 text-gray-100 text-[11px] font-normal shadow-lg leading-relaxed">
                Personal info used to auto-fill job application forms — contact details, work authorization, EEO answers, salary expectations, work-model preferences, and reusable answers to screener questions. Not used by the AI for resume generation or scoring.
              </span>
            </span>
            <span className="text-[11px] text-gray-400 dark:text-gray-500 ml-auto">Saves automatically</span>
          </div>
          {RIGHT_SECTIONS.map(s => {
            const isOpen = open.includes(s.key)
            return (
              <div key={s.key} className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg mb-4">
                <button
                  onClick={() => toggle(s.key)}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
                >
                  <span className="flex items-center gap-2">
                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    {s.label}
                  </span>
                </button>
                {isOpen && (
                  <div className="px-4 pb-4">
                    {s.hint && <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 mb-3">{s.hint}</p>}
                    <NodeEditor section={s} value={persona[s.key]}
                                onSave={(v) => saveNode(s.key, v)}
                                onSaveDebounced={(v) => saveNodeDebounced(s.key, v)} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function NodeEditor({ section, value, onSave, onSaveDebounced }) {
  if (section.kind === 'object') {
    return (
      <div className="grid grid-cols-2 gap-3 mt-3">
        {section.fields.map(f => (
          <label key={f} className="text-xs text-gray-600 dark:text-gray-400">
            {f.replace(/_/g, ' ')}
            <input
              type="text"
              defaultValue={(value || {})[f] ?? ''}
              onChange={(e) => {
                const next = { ...(value || {}), [f]: e.target.value }
                onSaveDebounced(next)
              }}
              className="mt-1 w-full border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            />
          </label>
        ))}
      </div>
    )
  }
  // array — kept as JSON textarea (qa_bank, writing_samples are free-form lists
  // of objects whose shape varies per entry). Saves on blur so we don't try to
  // parse mid-typed JSON; the parent treats this the same as the object editor
  // for the user-facing "Saves automatically" label.
  return (
    <textarea
      defaultValue={JSON.stringify(value || [], null, 2)}
      onBlur={(e) => {
        try { onSave(JSON.parse(e.target.value)) }
        catch (err) { alert(`Invalid JSON: ${err.message}`) }
      }}
      rows={12}
      className="w-full border rounded px-2 py-2 text-xs font-mono mt-3 dark:bg-gray-900 dark:text-gray-200 dark:border-gray-600"
    />
  )
}
