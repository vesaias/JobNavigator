import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import api from '../api'
import './theme.css'
import {
  EMPTY, SECTION_ORDER, sectionCounts, makeMutators,
  SectionShell, SectionEditor, BulletText,
} from './ResumeSections'

// The Persona is the singleton applicant record. Two independent halves:
//
//   left  · resume_content — same shape as a Resume's json_data, so it is edited
//           with the *same* components (see ResumeSections.jsx). Feeds tailoring,
//           cover-letter anecdotes and job scoring.
//   right · the autofill nodes — contact / demographics / work_auth / preferences
//           / compensation, read by the extension on ATS forms, plus the Q&A bank.
//
// Every node write spreads the existing node rather than rebuilding it from the
// field table below: `preferences` in particular carries keys no control shows
// (e.g. preferred_locations from the retired Preferences card) and is JSON-dumped
// whole into every cover-letter prompt, so dropping one silently changes output.

// ── the autofill field table ────────────────────────────────────────────────
// Mirrors backend/autofill_schema.py ANSWER_SCHEMA one-for-one (31 answerable
// fields + the decline flag). Order and labels follow the design.
const GENDER = [['male', 'Male'], ['female', 'Female'], ['nonbinary', 'Non-binary']]
const RACE = [['hispanic_latino', 'Hispanic/Latino'], ['white', 'White'], ['black', 'Black/African American'],
  ['asian', 'Asian'], ['native_american', 'Native American'], ['pacific_islander', 'Pacific Islander'],
  ['two_or_more', 'Two or more']]
const VETERAN = [['protected_veteran', 'I am a protected veteran'], ['not_protected_veteran', 'Not a protected veteran']]
const YESNO = [['yes', 'Yes'], ['no', 'No']]
const AGE = [['under_30', 'Under 30'], ['30_39', '30–39'], ['40_49', '40–49'], ['50_59', '50–59'], ['60_plus', '60 or older']]
const TRANS = [['no', 'No'], ['yes', 'Yes']]
const ORIENT = [['heterosexual', 'Heterosexual / straight'], ['gay', 'Gay'], ['lesbian', 'Lesbian'],
  ['bisexual', 'Bisexual'], ['queer', 'Queer'], ['other', 'Other']]
const WORK_AUTH_TYPE = [['citizen', 'U.S. citizen'], ['permanent_resident', 'Permanent resident'],
  ['visa', 'Visa holder'], ['other', 'Other']]

// GROUPS: [id, title, fields[]]   fields: [node, key, label, kind, opts]
const GROUPS = [
  ['contact', 'Contact / basics', [
    ['contact', 'first_name', 'First name', 'text'],
    ['contact', 'last_name', 'Last name', 'text'],
    ['contact', 'email', 'Email', 'text'],
    ['contact', 'phone', 'Phone', 'text'],
    ['contact', 'city', 'City', 'text'],
    ['contact', 'state', 'State', 'text'],
    ['contact', 'country', 'Country', 'text'],
    ['contact', 'current_company', 'Current company', 'text'],
    ['contact', 'linkedin', 'LinkedIn', 'text'],
    ['contact', 'github', 'GitHub', 'text'],
    ['contact', 'portfolio', 'Portfolio URL', 'text', { wide: true }],
  ]],
  ['demographics', 'Demographics · EEO', [
    ['demographics', 'gender', 'Gender', 'enum', { options: GENDER }],
    ['demographics', 'race_ethnicity', 'Race / ethnicity', 'enum', { options: RACE }],
    ['demographics', 'hispanic_latino', 'Hispanic or Latino?', 'enum', { options: YESNO }],
    ['demographics', 'veteran_status', 'Veteran status', 'enum', { options: VETERAN }],
    ['demographics', 'disability_status', 'Disability status', 'enum', { options: YESNO }],
    ['demographics', 'age_range', 'Age range', 'enum', { options: AGE }],
    ['demographics', 'transgender', 'Transgender?', 'enum', { options: TRANS }],
    ['demographics', 'sexual_orientation', 'Sexual orientation', 'enum', { options: ORIENT }],
    ['demographics', 'decline_demographics', '', 'check', {
      wide: true, uncounted: true,
      text: 'Prefer not to answer demographic questions — autofill picks “decline” where the form allows it',
    }],
  ]],
  ['workauth', 'Work authorization', [
    ['work_auth', 'authorized_us', 'Authorized to work in the US?', 'bool'],
    ['work_auth', 'requires_sponsorship_now', 'Require sponsorship now?', 'bool'],
    ['work_auth', 'requires_sponsorship_future', 'Require sponsorship in the future?', 'bool'],
    ['work_auth', 'over_18', 'Are you over 18?', 'bool'],
    ['work_auth', 'work_auth_type', 'Work authorization type', 'enum', { options: WORK_AUTH_TYPE, wide: true }],
  ]],
  ['screening', 'Screening defaults', [
    ['preferences', 'willing_to_relocate', 'Willing to relocate?', 'bool'],
    ['preferences', 'willing_remote', 'Willing to work remote?', 'bool'],
    ['preferences', 'notice_period', 'Notice period', 'text'],
    ['preferences', 'earliest_start', 'Earliest start date', 'text'],
    ['preferences', 'referral_source', 'Referral source', 'text'],
    ['preferences', 'how_did_you_hear', 'How did you hear about us?', 'text'],
    ['compensation', 'desired_salary', 'Desired salary', 'text', { wide: true }],
  ]],
]
const ANSWERABLE = GROUPS.reduce((n, g) => n + g[2].filter((f) => !f[4]?.uncounted).length, 0)

const isSet = (v) => v !== undefined && v !== null && v !== ''
const labelFor = (opts, v) => (opts.find(([ov]) => ov === v) || [])[1] || v

// qa_bank holds two shapes: the canonical {question, answer} the extension writes,
// and legacy single-key {"<question>": "<answer>"} maps. Read both, always write
// canonical (the backend reader is tolerant, but only one shape stays supported).
const toPair = (e) => {
  if (!e || typeof e !== 'object') return { question: '', answer: '' }
  if ('question' in e || 'answer' in e) return { question: e.question || '', answer: e.answer || '' }
  const k = Object.keys(e)[0]
  return k ? { question: k, answer: String(e[k] ?? '') } : { question: '', answer: '' }
}

const FIELD_LABEL = { fontSize: 9.5, lineHeight: '14px', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }
const BOX = { height: 30, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }

// A picker styled as the design's box: value + ▾, opening the standard v2 menu.
function Picker({ value, options, onChange, placeholder = '—' }) {
  const [open, setOpen] = useState(false)
  const set = isSet(value)
  return (
    <div style={{ position: 'relative' }}>
      <div onClick={() => setOpen((v) => !v)} className="v2-act v2-ctl" style={{ ...BOX, cursor: 'pointer', borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
        <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 12, color: set ? 'var(--text)' : 'var(--edge)' }}>
          {set ? labelFor(options, value) : placeholder}
        </span>
        <span style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--muted)' }}>▾</span>
      </div>
      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 30 }} />
          <div className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 5, zIndex: 31, minWidth: '100%', maxWidth: 280, maxHeight: 260, overflow: 'auto', background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 9, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5 }}>
            <div onClick={() => { onChange(undefined); setOpen(false) }} className="v2-menuitem" style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: !set ? 'var(--accent)' : 'var(--muted)', background: !set ? 'var(--accent-soft)' : 'transparent' }}>— not answered</div>
            {options.map(([v, l]) => (
              <div key={String(v)} onClick={() => { onChange(v); setOpen(false) }} className="v2-menuitem"
                style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: v === value ? 'var(--accent)' : 'var(--text-2)', background: v === value ? 'var(--accent-soft)' : 'transparent' }}>{l}</div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function AutofillField({ node, fkey, label, kind, opts, nodes, write }) {
  const val = (nodes[node] || {})[fkey]
  if (kind === 'check') {
    const on = !!val
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: opts?.wide ? 'span 2' : 'auto' }}>
        <div onClick={() => write(node, fkey, !on)} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer' }}>
          <span style={{ flex: '0 0 auto', width: 15, height: 15, marginTop: 1, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent)' : 'var(--surface)', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-ink)', fontSize: 9, lineHeight: 1 }}>{on ? '✓' : ''}</span>
          <span style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: '18px', textWrap: 'pretty' }}>{opts.text}</span>
        </div>
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, gridColumn: opts?.wide ? 'span 2' : 'auto' }}>
      <span style={FIELD_LABEL} title={label}>{label}</span>
      {kind === 'text' ? (
        <div style={BOX}>
          <input value={val ?? ''} onChange={(e) => write(node, fkey, e.target.value)}
            style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: 'var(--text)', fontFamily: 'var(--sans)' }} />
        </div>
      ) : kind === 'bool' ? (
        <Picker value={val === true ? 'yes' : val === false ? 'no' : undefined} options={YESNO}
          onChange={(v) => write(node, fkey, v === undefined ? undefined : v === 'yes')} />
      ) : (
        <Picker value={val} options={opts.options} onChange={(v) => write(node, fkey, v)} />
      )}
    </div>
  )
}

function ColumnHead({ title, help }) {
  return (
    <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, padding: '16px 26px 10px', lineHeight: '26px' }}>
      <span style={{ fontFamily: 'var(--serif)', fontSize: 18, fontWeight: 500, letterSpacing: '-.015em' }}>{title}</span>
      <span title={help} style={{ fontFamily: 'var(--sans)', fontSize: 11, lineHeight: '14px', color: 'var(--muted)', cursor: 'help', borderBottom: '1px dotted var(--line-strong)' }}>what is this?</span>
    </div>
  )
}

export default function Persona() {
  const [p, setP] = useState(null)
  const [saved, setSaved] = useState(false)
  const [sections, setSections] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem('jobnavigator_v2_persona_sections')); if (Array.isArray(s)) return new Set(s) } catch { /* ignore */ }
    return new Set(['Experience'])
  })
  const [groups, setGroups] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem('jobnavigator_v2_persona_groups')); if (Array.isArray(s)) return new Set(s) } catch { /* ignore */ }
    return new Set(['contact', 'qa'])
  })
  const timers = useRef({})
  const flashTimer = useRef(null)

  useEffect(() => {
    api.get('/persona').then(({ data }) => setP(data)).catch(() => {})
    return () => { Object.values(timers.current).forEach(clearTimeout); clearTimeout(flashTimer.current) }
  }, [])

  const flash = useCallback(() => {
    setSaved(true)
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setSaved(false), 1800)
  }, [])

  // One debounce timer per node so an autofill edit never cancels a résumé edit.
  const saveNode = useCallback((key, value) => {
    setP((prev) => (prev ? { ...prev, [key]: value } : prev))
    clearTimeout(timers.current[key])
    timers.current[key] = setTimeout(async () => {
      try { await api.patch('/persona', { [key]: value }); flash() } catch (e) { console.error(`persona ${key}`, e) }
    }, 500)
  }, [flash])

  // Spread the live node: keys with no control (preferences.preferred_locations)
  // must survive, and `undefined` clears a key rather than storing "".
  const write = useCallback((node, fkey, value) => {
    const next = { ...((p || {})[node] || {}) }
    if (value === undefined) delete next[fkey]
    else next[fkey] = value
    saveNode(node, next)
  }, [p, saveNode])

  const resume = p?.resume_content && Object.keys(p.resume_content).length ? p.resume_content : EMPTY
  const { mutate, setField } = makeMutators(resume, (next) => saveNode('resume_content', next))

  const qa = useMemo(() => (p?.qa_bank || []).map(toPair), [p])
  const writeQa = (list) => saveNode('qa_bank', list.map((e) => ({ question: e.question, answer: e.answer })))

  const filled = useMemo(() => {
    if (!p) return 0
    return GROUPS.reduce((n, g) => n + g[2].filter((f) => !f[4]?.uncounted && isSet((p[f[0]] || {})[f[1]])).length, 0)
  }, [p])

  const toggler = (setter, storeKey) => (name) => setter((prev) => {
    const n = new Set(prev); n.has(name) ? n.delete(name) : n.add(name)
    try { localStorage.setItem(storeKey, JSON.stringify([...n])) } catch { /* ignore */ }
    return n
  })
  const toggleSection = toggler(setSections, 'jobnavigator_v2_persona_sections')
  const toggleGroup = toggler(setGroups, 'jobnavigator_v2_persona_groups')

  if (!p) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>

  const counts = sectionCounts(resume)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Persona</h1>
          {/* integer line-heights throughout: at the inherited 1.5 a 13px line is
              19.5px, which lands every row below the header on a half pixel and
              makes Chrome round away their 1px borders on alternating rows */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Saves automatically · autofill {filled} of {ANSWERABLE} set
          </span>
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--accent)', visibility: saved ? 'visible' : 'hidden' }}>Saved ✓</span>
      </header>

      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* left — résumé content, edited with the Résumé editor's own components */}
        <div style={{ flex: 1.1, minWidth: 0, borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <ColumnHead title="Résumé content"
            help="Your full work history, summary, skills and achievements. The AI uses this as the source pool for tailored résumés, as raw material for cover-letter anecdotes, and as the candidate profile when scoring jobs." />
          <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 26px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            {SECTION_ORDER.map((name) => (
              <SectionShell key={name} name={name} count={counts[name]} open={sections.has(name)} onToggle={() => toggleSection(name)}>
                <SectionEditor name={name} data={resume} setField={setField} mutate={mutate}
                  pageHint={false} emptyNote="Tailored résumés draw from whatever you add here." />
              </SectionShell>
            ))}
          </div>
        </div>

        {/* right — the autofill nodes + the Q&A bank */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <ColumnHead title="Autofill content"
            help="Personal info used to auto-fill application forms — contact details, work authorization, EEO answers, salary expectations and reusable screener answers. Not used by the AI for résumé generation or scoring." />
          <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 26px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            {GROUPS.map(([id, title, fields]) => {
              const open = groups.has(id)
              const counted = fields.filter((f) => !f[4]?.uncounted)
              const n = counted.filter((f) => isSet((p[f[0]] || {})[f[1]])).length
              const done = n === counted.length
              return (
                <div key={id} style={{ border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
                  <div onClick={() => toggleGroup(id)} className="v2-clhead" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '11px 14px', cursor: 'pointer', borderRadius: 9, lineHeight: '18px' }}>
                    <span style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--muted)' }}>{open ? '⌄' : '›'}</span>
                    <span style={{ flex: '0 0 auto', fontSize: 13, fontWeight: 600 }}>{title}</span>
                    <span style={{ flex: 1, minWidth: 0 }} />
                    <span style={{ flex: '0 0 auto', fontSize: 10.5, color: done ? 'var(--accent)' : 'var(--edge)' }}>{done ? 'complete' : `${n} of ${counted.length} set`}</span>
                  </div>
                  {open && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, padding: '12px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
                      {fields.map(([node, fkey, label, kind, opts]) => (
                        <AutofillField key={`${node}.${fkey}`} node={node} fkey={fkey} label={label} kind={kind} opts={opts} nodes={p} write={write} />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Q&A bank — the one amber card; answers go to the LLM verbatim */}
            <div style={{ border: '1px solid var(--amber-line)', borderRadius: 9, background: 'var(--amber-bg)', display: 'flex', flexDirection: 'column' }}>
              <div onClick={() => toggleGroup('qa')} className="v2-qahead" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '11px 14px', cursor: 'pointer', borderRadius: 9, lineHeight: '18px' }}>
                <span style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--muted)' }}>{groups.has('qa') ? '⌄' : '›'}</span>
                <span style={{ flex: '0 0 auto', fontSize: 13, fontWeight: 600 }}>Q&amp;A bank</span>
                <span style={{ flex: 1, minWidth: 0, fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>reusable screener answers</span>
                <span style={{ flex: '0 0 auto', fontSize: 10.5, color: 'var(--edge)' }}>{qa.length} answer{qa.length === 1 ? '' : 's'}</span>
              </div>
              {groups.has('qa') && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7, padding: '12px 14px 14px', borderTop: '1px solid var(--amber-line-soft)' }}>
                  {qa.map((e, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 11px', border: '1px solid var(--amber-line-soft)', borderRadius: 7, background: 'var(--surface)' }}>
                      {/* each BulletText needs a ROW flex parent: its flex:1 sizes the
                          width there, whereas in a column parent flex:1 would drive the
                          height and override the auto-grow, clipping every answer to one line */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                        <div style={{ flex: '0 0 auto', display: 'flex', minWidth: 0 }}>
                          <BulletText bold lh="19px" value={e.question} placeholder="Question as the form asks it…"
                            onChange={(v) => writeQa(qa.map((x, j) => (j === i ? { ...x, question: v } : x)))} />
                        </div>
                        <div style={{ flex: '0 0 auto', display: 'flex', minWidth: 0 }}>
                          <BulletText lh="19px" value={e.answer} placeholder="Your reusable answer…"
                            onChange={(v) => writeQa(qa.map((x, j) => (j === i ? { ...x, answer: v } : x)))} />
                        </div>
                      </div>
                      <span onClick={() => writeQa(qa.filter((_, j) => j !== i))} title="Remove answer" className="v2-hover-bad"
                        style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: 11, cursor: 'pointer', lineHeight: '19px' }}>✕</span>
                    </div>
                  ))}
                  {qa.length === 0 && <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>No saved answers yet — the extension can add them as you apply.</span>}
                  <span onClick={() => writeQa([...qa, { question: '', answer: '' }])} className="v2-hover-accent-text"
                    style={{ alignSelf: 'flex-start', fontSize: 11.5, lineHeight: '19px', color: 'var(--accent)', cursor: 'pointer' }}>＋ Add answer</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
