import React, { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { ChevronDown, ChevronRight, User, Briefcase, Globe, DollarSign, Settings as SettingsIcon, FileText, MessageSquare, Quote } from 'lucide-react'

// One section per persona node. Order = display order.
const SECTIONS = [
  { key: 'contact', label: 'Contact', icon: User, kind: 'object',
    fields: ['name', 'email', 'phone', 'address', 'linkedin', 'github', 'website'] },
  { key: 'work_auth', label: 'Work Authorization', icon: Globe, kind: 'object',
    fields: ['citizenship', 'sponsorship_needed', 'visa_status', 'earliest_start_date'] },
  { key: 'demographics', label: 'Demographics (EEO)', icon: User, kind: 'object',
    fields: ['gender', 'race', 'veteran_status', 'disability_status'],
    hint: 'All fields default to "decline to answer". Most postings make these optional.' },
  { key: 'compensation', label: 'Compensation', icon: DollarSign, kind: 'object',
    fields: ['target_min', 'target_max', 'currency', 'notes'] },
  { key: 'preferences', label: 'Preferences', icon: SettingsIcon, kind: 'object',
    fields: ['remote', 'hybrid_ok', 'onsite_ok', 'willing_to_relocate', 'preferred_locations', 'availability_notes'] },
  { key: 'resume_content', label: 'Resume Content', icon: FileText, kind: 'json',
    hint: 'Mirrors the Resume Builder JSON shape: summary, experience[], skills, education[], projects[].' },
  { key: 'qa_bank', label: 'Q&A Bank', icon: MessageSquare, kind: 'array',
    hint: 'Reusable answers to free-text application questions ("Why this company?", "Comp expectations")' },
  { key: 'writing_samples', label: 'Writing Samples', icon: Quote, kind: 'array',
    hint: 'Voice anchors — short paragraphs the cover letter generator uses for tone' },
]

export default function Persona() {
  const [persona, setPersona] = useState(null)
  const [open, setOpen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('persona_open_sections') || '["contact"]') }
    catch { return ['contact'] }
  })

  const fetchPersona = useCallback(async () => {
    const { data } = await api.get('/persona')
    setPersona(data)
  }, [])

  useEffect(() => { fetchPersona() }, [fetchPersona])
  useEffect(() => { localStorage.setItem('persona_open_sections', JSON.stringify(open)) }, [open])

  const toggle = (k) => setOpen(prev => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k])

  const saveNode = async (key, value) => {
    try {
      const { data } = await api.patch('/persona', { [key]: value })
      setPersona(data)
    } catch (e) { alert(`Failed to save ${key}: ${e.response?.data?.detail || e.message}`) }
  }

  if (!persona) return <div className="p-6 text-sm text-gray-500">Loading persona…</div>

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-2">
      <h1 className="text-xl font-semibold mb-4 dark:text-gray-100">Persona</h1>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
        Single source of truth: tailoring + cover letter + autofill all read from here. Changes save on blur.
      </p>
      {SECTIONS.map(s => {
        const Icon = s.icon
        const isOpen = open.includes(s.key)
        return (
          <div key={s.key} className="border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
            <button onClick={() => toggle(s.key)}
                    className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-gray-800 dark:text-gray-100">
              <span className="flex items-center gap-2">
                <Icon size={14} className="text-gray-400" />
                {s.label}
              </span>
              {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {isOpen && (
              <div className="px-4 pb-4 border-t dark:border-gray-700">
                {s.hint && <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 mb-3">{s.hint}</p>}
                <NodeEditor section={s} value={persona[s.key]} onSave={(v) => saveNode(s.key, v)} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function NodeEditor({ section, value, onSave }) {
  if (section.kind === 'object') {
    return (
      <div className="grid grid-cols-2 gap-3 mt-3">
        {section.fields.map(f => (
          <label key={f} className="text-xs text-gray-600 dark:text-gray-400">
            {f.replace(/_/g, ' ')}
            <input
              type="text"
              defaultValue={(value || {})[f] ?? ''}
              onBlur={(e) => {
                const next = { ...(value || {}), [f]: e.target.value }
                onSave(next)
              }}
              className="mt-1 w-full border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            />
          </label>
        ))}
      </div>
    )
  }
  if (section.kind === 'json') {
    return (
      <textarea
        defaultValue={JSON.stringify(value || {}, null, 2)}
        onBlur={(e) => {
          try { onSave(JSON.parse(e.target.value)) }
          catch (err) { alert(`Invalid JSON: ${err.message}`) }
        }}
        rows={20}
        className="w-full border rounded px-2 py-2 text-xs font-mono mt-3 dark:bg-gray-900 dark:text-gray-200 dark:border-gray-600"
      />
    )
  }
  // array
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
