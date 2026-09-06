import React, { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api'
import { ChevronDown, ChevronRight, FileText, Info, ClipboardList } from 'lucide-react'
import ResumeContentEditor, { EMPTY_RESUME_DATA } from './ResumeContentEditor'

// Right-column sections — everything except resume_content (which gets the
// dedicated structured editor in the left column). Per-section info is rolled
// up into the column-level header tooltip.
const RIGHT_SECTIONS = [
  // Contact section merged into the Application Answers "Contact / Basics" group
  // below (email/phone/linkedin/github now live there alongside first_name/etc).
  // Work Authorization section removed: citizenship/sponsorship_needed/visa_status/
  // earliest_start_date were legacy free-text, superseded by the canonical
  // authorized_us / work_auth_type / requires_sponsorship_now|future / over_18
  // controls in "Application Answers" below (+ preferences.earliest_start).
  // Demographics (EEO) section removed: every one of its legacy free-text fields
  // (gender, race, veteran_status, disability_status) has been superseded by the
  // canonical enum selects in the "Application Answers" card below, which write
  // the same `demographics` node keys (gender, race_ethnicity, veteran_status,
  // disability_status) in a structured, autofill-consumable format. Keeping
  // both would let two controls clobber the same JSON keys with conflicting
  // representations (free text vs. enum value / boolean).
  // Compensation section removed: its legacy fields (target_min/max/currency/notes)
  // were unused by any backend consumer; the only comp value autofill needs is
  // `desired_salary`, edited in "Application Answers" below.
  // Preferences section removed: its autofill-relevant fields (willing_remote,
  // willing_to_relocate, notice_period, earliest_start, referral_source,
  // how_did_you_hear) are in "Application Answers" below, which writes the
  // `preferences`/`compensation` nodes directly. Existing preferences values are
  // preserved and still flow into cover-letter generation.
  { key: 'qa_bank', label: 'Q&A Bank', kind: 'array',
    hint: 'Reusable answers to free-text application questions ("Why this company?", "Comp expectations")',
    usedBy: ['Autofill (free-text screener questions)'] },
]

// All contact keys, edited inside the Application Answers "Contact / Basics"
// group (the standalone Contact card was merged in here). Each writes the
// `contact` node.
const APPLICATION_ANSWERS_CONTACT_FIELDS = [
  { key: 'first_name', label: 'First name' },
  { key: 'last_name', label: 'Last name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State' },
  { key: 'country', label: 'Country' },
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'github', label: 'GitHub' },
  { key: 'portfolio', label: 'Portfolio URL' },
  { key: 'current_company', label: 'Current company' },
]

// Demographic dropdowns are unset ("—") by default; the "prefer not to answer"
// checkbox is the single decline control (no per-field "Decline" option).
const GENDER_OPTIONS = [
  ['male', 'Male'], ['female', 'Female'], ['nonbinary', 'Non-binary'],
]
const RACE_ETHNICITY_OPTIONS = [
  ['hispanic_latino', 'Hispanic/Latino'], ['white', 'White'], ['black', 'Black/African American'],
  ['asian', 'Asian'], ['native_american', 'Native American'], ['pacific_islander', 'Pacific Islander'],
  ['two_or_more', 'Two or more'],
]
const VETERAN_STATUS_OPTIONS = [
  ['protected_veteran', 'I am a protected veteran'], ['not_protected_veteran', 'Not a protected veteran'],
]
const DISABILITY_STATUS_OPTIONS = [['yes', 'Yes'], ['no', 'No']]
const HISPANIC_LATINO_OPTIONS = [['yes', 'Yes'], ['no', 'No']]
const AGE_RANGE_OPTIONS = [
  ['under_30', 'Under 30'], ['30_39', '30–39'], ['40_49', '40–49'],
  ['50_59', '50–59'], ['60_plus', '60 or older'],
]
const TRANSGENDER_OPTIONS = [['no', 'No'], ['yes', 'Yes']]
const SEXUAL_ORIENTATION_OPTIONS = [
  ['heterosexual', 'Heterosexual / straight'], ['gay', 'Gay'], ['lesbian', 'Lesbian'],
  ['bisexual', 'Bisexual'], ['queer', 'Queer'], ['other', 'Other'],
]
const WORK_AUTH_TYPE_OPTIONS = [
  ['citizen', 'U.S. citizen'], ['permanent_resident', 'Permanent resident'], ['visa', 'Visa holder'], ['other', 'Other'],
]

export default function Persona() {
  const [persona, setPersona] = useState(null)
  const [open, setOpen] = useState(() => {
    try { return JSON.parse(localStorage.getItem('persona_open_sections') || '["contact"]') }
    catch { return ['contact'] }
  })
  const [savedFlash, setSavedFlash] = useState('')
  const [loadError, setLoadError] = useState('')
  const debounceTimerRef = useRef(null)
  const nodeDebounceRef = useRef({})  // per-key debounce timers for autofill nodes

  const fetchPersona = useCallback(async () => {
    try {
      setLoadError('')
      const { data } = await api.get('/persona')
      setPersona(data)
    } catch (e) {
      console.error('Failed to load persona:', e)
      // detail can be a validation-error array; only a string is renderable
      const detail = e?.response?.data?.detail
      setLoadError(typeof detail === 'string' ? detail : (e?.message || 'Could not load persona'))
    }
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

  if (loadError && !persona) return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Persona</h1>
      <div className="text-sm text-red-600 dark:text-red-400">
        Failed to load persona — {loadError}{' '}
        <button onClick={fetchPersona} className="underline hover:no-underline">Retry</button>
      </div>
    </div>
  )

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
          {/* Application Answers — structured contact + yes/no + enum fields the
              Autofill feature reads directly. Spans several persona nodes
              (demographics, work_auth, contact, preferences, compensation), so
              it's rendered as its own card rather than the single-node NodeEditor.
              Rendered first; the Q&A Bank (free-text pairs) sits at the bottom. */}
          <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg mb-4">
            <button
              onClick={() => toggle('application_answers')}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
            >
              <span className="flex items-center gap-2">
                {open.includes('application_answers') ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                Application Answers
              </span>
            </button>
            {open.includes('application_answers') && (
              <div className="px-4 pb-4">
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 mb-3">
                  Contact details plus fixed yes/no and multiple-choice answers the Autofill feature
                  uses to fill screener questions (work authorization, EEO, relocation) consistently
                  across applications.
                </p>
                <ApplicationAnswersEditor persona={persona} saveNodeDebounced={saveNodeDebounced} />
              </div>
            )}
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
  // array — kept as JSON textarea (qa_bank is a free-form list of objects whose
  // shape varies per entry). Saves on blur so we don't try to
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

// -- Application Answers field primitives -----------------------------------
// Mirror the input styling from NodeEditor's object-kind fields (same border/
// dark classes) so the new section looks identical to the rest of the column.

function TextField({ label, value, onChange }) {
  return (
    <label className="text-xs text-gray-600 dark:text-gray-400">
      {label}
      <input
        type="text"
        defaultValue={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
      />
    </label>
  )
}

// Enum select. Empty string ("—") means unset and is treated the same as
// yes/no's unset state: the key is cleared from the node rather than storing "".
function SelectField({ label, value, options, onChange, placeholder }) {
  return (
    <label className="text-xs text-gray-600 dark:text-gray-400">
      {label}
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value)}
        className="mt-1 w-full border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
      >
        <option value="">{placeholder || '—'}</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  )
}

// 3-state yes/no select. Stores real booleans; "—" clears the key.
function YesNoField({ label, value, onChange }) {
  const selectValue = value === true ? 'true' : value === false ? 'false' : ''
  return (
    <label className="text-xs text-gray-600 dark:text-gray-400">
      {label}
      <select
        value={selectValue}
        onChange={(e) => {
          const v = e.target.value
          onChange(v === '' ? undefined : v === 'true')
        }}
        className="mt-1 w-full border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
      >
        <option value="">—</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </label>
  )
}

function CheckboxField({ label, checked, onChange }) {
  return (
    <label className="col-span-2 flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-gray-300 dark:border-gray-600"
      />
      {label}
    </label>
  )
}

// Groups A-D from the Application Answers spec. Each group edits a different
// persona node; saveNodeDebounced(nodeKey, mergedNode) PATCHes the whole node
// (the persona PATCH contract replaces a node atomically), matching the merge
// pattern used by NodeEditor's object-kind fields above.
function ApplicationAnswersEditor({ persona, saveNodeDebounced }) {
  const demographics = persona.demographics || {}
  const workAuth = persona.work_auth || {}
  const contact = persona.contact || {}
  const preferences = persona.preferences || {}
  const compensation = persona.compensation || {}

  const setField = (nodeKey, node, field, value) => {
    const next = { ...node }
    if (value === undefined) delete next[field]
    else next[field] = value
    saveNodeDebounced(nodeKey, next)
  }

  return (
    <div className="mt-1 space-y-5">
      <div>
        <h3 className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
          Contact / Basics
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {APPLICATION_ANSWERS_CONTACT_FIELDS.map(f => (
            <TextField key={f.key} label={f.label} value={contact[f.key]}
              onChange={(v) => setField('contact', contact, f.key, v)} />
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
          Demographics
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <SelectField label="Gender" value={demographics.gender} options={GENDER_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'gender', v)} />
          <SelectField label="Race / ethnicity" value={demographics.race_ethnicity} options={RACE_ETHNICITY_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'race_ethnicity', v)} />
          <SelectField label="Hispanic or Latino?" value={demographics.hispanic_latino} options={HISPANIC_LATINO_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'hispanic_latino', v)} />
          <SelectField label="Veteran status" value={demographics.veteran_status} options={VETERAN_STATUS_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'veteran_status', v)} />
          <SelectField label="Disability status" value={demographics.disability_status} options={DISABILITY_STATUS_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'disability_status', v)} />
          <SelectField label="Age range" value={demographics.age_range} options={AGE_RANGE_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'age_range', v)} />
          <SelectField label="Transgender?" value={demographics.transgender} options={TRANSGENDER_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'transgender', v)} />
          <SelectField label="Sexual orientation" value={demographics.sexual_orientation} options={SEXUAL_ORIENTATION_OPTIONS}
            onChange={(v) => setField('demographics', demographics, 'sexual_orientation', v)} />
          <CheckboxField label="Prefer not to answer demographic questions (fill 'decline' where possible)"
            checked={demographics.decline_demographics}
            onChange={(v) => setField('demographics', demographics, 'decline_demographics', v)} />
        </div>
      </div>

      <div>
        <h3 className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
          Work Authorization
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <YesNoField label="Authorized to work in the US?" value={workAuth.authorized_us}
            onChange={(v) => setField('work_auth', workAuth, 'authorized_us', v)} />
          <YesNoField label="Require visa sponsorship now?" value={workAuth.requires_sponsorship_now}
            onChange={(v) => setField('work_auth', workAuth, 'requires_sponsorship_now', v)} />
          <YesNoField label="Require sponsorship in the future?" value={workAuth.requires_sponsorship_future}
            onChange={(v) => setField('work_auth', workAuth, 'requires_sponsorship_future', v)} />
          <YesNoField label="Are you over 18?" value={workAuth.over_18}
            onChange={(v) => setField('work_auth', workAuth, 'over_18', v)} />
          <SelectField label="Work authorization type" value={workAuth.work_auth_type} options={WORK_AUTH_TYPE_OPTIONS}
            onChange={(v) => setField('work_auth', workAuth, 'work_auth_type', v)} />
        </div>
      </div>

      <div>
        <h3 className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
          Screening Defaults
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <YesNoField label="Willing to relocate?" value={preferences.willing_to_relocate}
            onChange={(v) => setField('preferences', preferences, 'willing_to_relocate', v)} />
          <YesNoField label="Willing to work remote?" value={preferences.willing_remote}
            onChange={(v) => setField('preferences', preferences, 'willing_remote', v)} />
          <TextField label="Notice period" value={preferences.notice_period}
            onChange={(v) => setField('preferences', preferences, 'notice_period', v)} />
          <TextField label="Earliest start date" value={preferences.earliest_start}
            onChange={(v) => setField('preferences', preferences, 'earliest_start', v)} />
          <TextField label="Referral source" value={preferences.referral_source}
            onChange={(v) => setField('preferences', preferences, 'referral_source', v)} />
          <TextField label="How did you hear about us?" value={preferences.how_did_you_hear}
            onChange={(v) => setField('preferences', preferences, 'how_did_you_hear', v)} />
          <TextField label="Desired salary" value={compensation.desired_salary}
            onChange={(v) => setField('compensation', compensation, 'desired_salary', v)} />
        </div>
      </div>
    </div>
  )
}
