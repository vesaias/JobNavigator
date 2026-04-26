import React, { useState } from 'react'
import { Plus, Trash2, ChevronDown, ChevronRight, ArrowUp, ArrowDown } from 'lucide-react'

export const EMPTY_RESUME_DATA = {
  header: {
    name: '',
    contact_items: [],
  },
  summary: '',
  experience: [],
  skills: {},
  education: [],
  projects: [],
  publications: [],
}

const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

export function CollapsibleSection({ title, defaultOpen = true, children, badge }) {
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

export function FieldInput({ label, value, onChange, onBlur, placeholder, multiline, rows }) {
  const cls = "border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
  const handleBoldShortcut = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault()
      const ta = e.target
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = ta.value
      if (start === end) return
      const selected = text.slice(start, end)
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

/**
 * Controlled editor for the Resume json_data shape (also Persona.resume_content).
 * `value` — current data; `onChange(nextValue)` — fires on every internal mutation.
 * The parent owns persistence (debounce, PATCH, etc.) — this component only edits.
 */
export default function ResumeContentEditor({ value, onChange }) {
  const data = value || EMPTY_RESUME_DATA

  const updateField = (path, fieldValue) => {
    const keys = String(path).split('.')
    if (keys.some(k => DANGEROUS_KEYS.has(k))) return
    const updated = JSON.parse(JSON.stringify(data))
    let obj = updated
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i]
      if (obj == null || typeof obj !== 'object') return
      obj = obj[k]
    }
    if (obj == null || typeof obj !== 'object') return
    obj[keys[keys.length - 1]] = fieldValue
    onChange(updated)
  }

  const mutate = (fn) => {
    const updated = JSON.parse(JSON.stringify(data))
    fn(updated)
    onChange(updated)
  }

  const addExperience = () => mutate(d => {
    d.experience = d.experience || []
    d.experience.push({ company: '', title: '', location: '', date: '', description: '', bullets: [] })
  })
  const removeExperience = (idx) => mutate(d => { d.experience.splice(idx, 1) })

  const addEducation = () => mutate(d => {
    d.education = d.education || []
    d.education.push({ school: '', location: '', degree: '' })
  })
  const removeEducation = (idx) => mutate(d => { d.education.splice(idx, 1) })

  const addProject = () => mutate(d => {
    d.projects = d.projects || []
    d.projects.push({ name: '', description: '', url: '', bullets: [] })
  })
  const removeProject = (idx) => mutate(d => { d.projects.splice(idx, 1) })

  const addPublication = () => mutate(d => {
    d.publications = d.publications || []
    d.publications.push({ title: '', description: '' })
  })
  const removePublication = (idx) => mutate(d => { d.publications.splice(idx, 1) })

  const addSkillRow = () => mutate(d => {
    d.skills = d.skills || {}
    const key = `Skill ${Object.keys(d.skills).length + 1}`
    d.skills[key] = ''
  })
  const removeSkillRow = (key) => mutate(d => { delete d.skills[key] })
  const renameSkillKey = (oldKey, newKey) => {
    if (oldKey === newKey || !newKey.trim()) return
    mutate(d => {
      const entries = Object.entries(d.skills)
      const newSkills = {}
      for (const [k, v] of entries) newSkills[k === oldKey ? newKey : k] = v
      d.skills = newSkills
    })
  }

  const moveContact = (idx, dir) => mutate(d => {
    const items = d.header?.contact_items || []
    const j = idx + dir
    if (j < 0 || j >= items.length) return
    ;[items[idx], items[j]] = [items[j], items[idx]]
  })
  const removeContact = (idx) => mutate(d => { d.header.contact_items.splice(idx, 1) })
  const addContact = () => mutate(d => {
    if (!d.header) d.header = { name: '', contact_items: [] }
    if (!d.header.contact_items) d.header.contact_items = []
    d.header.contact_items.push({ text: '', url: '' })
  })

  return (
    <>
      {/* Header */}
      <CollapsibleSection title="Header">
        <FieldInput label="Name" value={data.header?.name} onChange={v => updateField('header.name', v)} />
        <div className="mt-3">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Contact Items</label>
          {(data?.header?.contact_items || []).map((item, idx) => (
            <div key={idx} className="flex items-center gap-2 mb-1.5">
              <div className="flex flex-col">
                <button onClick={() => moveContact(idx, -1)}
                  disabled={idx === 0}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowUp size={11} /></button>
                <button onClick={() => moveContact(idx, 1)}
                  disabled={idx === (data?.header?.contact_items || []).length - 1}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-20"><ArrowDown size={11} /></button>
              </div>
              <input
                type="text"
                value={item.text || ''}
                placeholder="Display text"
                onChange={e => updateField(`header.contact_items.${idx}.text`, e.target.value)}
                className="border rounded px-2 py-1 text-sm w-36 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              />
              <input
                type="text"
                value={item.url || ''}
                placeholder="URL (optional)"
                onChange={e => updateField(`header.contact_items.${idx}.url`, e.target.value)}
                className="border rounded px-2 py-1 text-sm flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              />
              {item.url && !item.url.startsWith('mailto:') && (
                <input
                  type="text"
                  value={item.stub || ''}
                  placeholder="id"
                  title="Short stub for tracer link ID (e.g. l, w, gh)"
                  onChange={e => updateField(`header.contact_items.${idx}.stub`, e.target.value)}
                  className="border rounded px-2 py-1 text-sm w-12 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                />
              )}
              <button onClick={() => removeContact(idx)} className="text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          <button onClick={addContact} className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1 mt-1">
            <Plus size={12} /> Add Item
          </button>
        </div>
      </CollapsibleSection>

      {/* Summary */}
      <CollapsibleSection title="Summary">
        <FieldInput
          multiline
          rows={4}
          value={data.summary}
          onChange={v => updateField('summary', v)}
          placeholder="Professional summary..."
        />
      </CollapsibleSection>

      {/* Experience */}
      <CollapsibleSection title="Experience" badge={data.experience?.length || 0}>
        {(data.experience || []).map((exp, idx) => (
          <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
            <button
              onClick={() => removeExperience(idx)}
              className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
              title="Remove">
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
      <CollapsibleSection title="Skills" badge={Object.keys(data.skills || {}).length}>
        {Object.entries(data.skills || {}).map(([key, value]) => (
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
      <CollapsibleSection title="Education" badge={data.education?.length || 0}>
        {(data.education || []).map((edu, idx) => (
          <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
            <button
              onClick={() => removeEducation(idx)}
              className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
              title="Remove">
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
      <CollapsibleSection title="Projects" defaultOpen={(data.projects || []).length > 0} badge={data.projects?.length || 0}>
        {(data.projects || []).map((proj, idx) => (
          <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
            <button
              onClick={() => removeProject(idx)}
              className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
              title="Remove">
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
      <CollapsibleSection title="Publications" defaultOpen={(data.publications || []).length > 0} badge={data.publications?.length || 0}>
        {(data.publications || []).map((pub, idx) => (
          <div key={idx} className="border dark:border-gray-600 rounded p-3 mb-3 relative">
            <button
              onClick={() => removePublication(idx)}
              className="absolute top-2 right-2 text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
              title="Remove">
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
    </>
  )
}
