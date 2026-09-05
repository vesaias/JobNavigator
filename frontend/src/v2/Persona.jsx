import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import { useSettled } from './hooks'
import { Band, Button, Card, ChoiceCard, ChoiceModal, ChoiceRow, Heading, HeaderRow, Helper, Input, Label, PageTitle, Pill, SectionHead, Select } from './ui'
import { ago } from './time'
import './theme.css'
import {
  EMPTY, SECTION_ORDER, sectionCounts, makeMutators,
  SectionShell, SectionEditor, BulletText, DashedAdd, RemoveX, kb,
} from './ResumeSections'

// The Persona is the singleton applicant record, in two independent halves:
// left · resume_content (same shape as a Resume's json_data, edited with ResumeSections.jsx; feeds tailoring, cover letters, scoring).
// right · autofill nodes (contact/demographics/work_auth/preferences/compensation, read by the extension) plus the Q&A bank.
//
// Every node write spreads the existing node: `preferences` carries keys no control shows
// (e.g. preferred_locations) and is JSON-dumped whole into every cover-letter prompt, so dropping one silently changes output.

// ── the autofill field table ────────────────────────────────────────────────
// Mirrors backend/autofill_schema.py ANSWER_SCHEMA one-for-one (31 answerable fields + the decline flag).
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
      text: 'Decline demographic questions where the form allows it',
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
// the server's own words for a failure, when it sent any
const errDetail = (e) => (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '')
const plural = (n, word) => `${n || 0} ${word}${(n || 0) === 1 ? '' : 's'}`
// The Picker's clear row needs a value of its own: an unset answer renders as the
// placeholder, so '' would make "— not answered" the trigger's *label* instead of the em dash.
const UNSET = '__unset__'

// qa_bank holds two shapes: canonical {question, answer}, and legacy single-key
// {"<question>": "<answer>"} maps (expand to one pair per key). Read both, always write canonical, skipping entries with nothing editable.
const toPairs = (e) => {
  if (!e || typeof e !== 'object' || Array.isArray(e)) return []
  if ('question' in e || 'answer' in e) return [{ question: e.question == null ? '' : String(e.question), answer: e.answer == null ? '' : String(e.answer) }]
  return Object.keys(e).filter((k) => k !== '').map((k) => ({ question: k, answer: String(e[k] ?? '') }))
}

// layout only — the type (uppercase 10/15px · .13em · --label-ink) comes from Label
const FIELD_LABEL = { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }
// Thin wrapper over ui.jsx's Select that keeps the "— not answered" row: clearing an
// answer is a real action here (unset differs from empty for the autofill extension).
function Picker({ value, options, onChange, placeholder = '—', ariaLabel }) {
  const opts = useMemo(() => [[UNSET, '— not answered'], ...options], [options])
  return (
    <Select value={isSet(value) ? value : ''} options={opts} placeholder={placeholder}
      ariaLabel={ariaLabel} onPick={(v) => onChange(v === UNSET ? undefined : v)}
      style={{ flex: '0 0 auto', width: '100%' }} />
  )
}

function AutofillField({ node, fkey, label, kind, opts, nodes, write }) {
  const val = (nodes[node] || {})[fkey]
  if (kind === 'check') {
    const on = !!val
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, gridColumn: opts?.wide ? 'span 2' : 'auto' }}>
        <div onClick={() => write(node, fkey, !on)} {...kb(() => write(node, fkey, !on), 'checkbox')} aria-checked={on} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer' }}>
          {/* ui: keep — checkbox indicator, not a card */}
          <span style={{ flex: '0 0 auto', width: 15, height: 15, marginTop: 1, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent)' : 'var(--surface)', borderRadius: 'var(--radius-inline)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-ink)', fontSize: 9, lineHeight: 1 }}>{on ? '✓' : ''}</span>
          <span style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: '18px', textWrap: 'pretty' }}>{opts.text}</span>
        </div>
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, gridColumn: opts?.wide ? 'span 2' : 'auto' }}>
      <Label style={FIELD_LABEL} title={label}>{label}</Label>
      {kind === 'text' ? (
        <Input value={val ?? ''} onChange={(v) => write(node, fkey, v)} ariaLabel={label} />
      ) : kind === 'bool' ? (
        <Picker value={val === true ? 'yes' : val === false ? 'no' : undefined} options={YESNO} ariaLabel={label}
          onChange={(v) => write(node, fkey, v === undefined ? undefined : v === 'yes')} />
      ) : (
        <Picker value={val} options={opts.options} ariaLabel={label} onChange={(v) => write(node, fkey, v)} />
      )}
    </div>
  )
}

function ColumnHead({ title, help }) {
  return (
    <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'baseline', gap: 9, padding: '16px 26px 10px', lineHeight: '26px' }}>
      <Heading strong size={18}>{title}</Heading>
      <Helper title={help} style={{ cursor: 'help', borderBottom: '1px dotted var(--line-strong)' }}>what is this?</Helper>
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
  const [loadErr, setLoadErr] = useState(false)   // a failed load is not "still loading"
  const [groups, setGroups] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem('jobnavigator_v2_persona_groups')); if (Array.isArray(s)) return new Set(s) } catch { /* ignore */ }
    return new Set(['contact', 'qa'])
  })
  const timers = useRef({})
  const flashTimer = useRef(null)
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  // Flush pending debounced saves on unmount rather than dropping them.
  // fetch+keepalive rather than axios: an XHR started in `beforeunload` is aborted with the page.
  const flushPending = useCallback(() => {
    const pend = timers.current
    timers.current = {}
    Object.entries(pend).forEach(([key, e]) => {
      clearTimeout(e.timer)
      const headers = { 'Content-Type': 'application/json' }
      try { const k = localStorage.getItem('jobnavigator_api_key'); if (k) headers['X-API-Key'] = k } catch { /* ignore */ }
      try { fetch('/api/persona', { method: 'PATCH', headers, credentials: 'include', keepalive: true, body: JSON.stringify({ [key]: e.value }) }) }
      // silent: last-chance flush on unmount/beforeunload — nowhere to show a toast.
      catch { api.patch('/persona', { [key]: e.value }).catch(() => { /* silent: see above — nowhere left to report to */ }) }
    })
  }, [])

  const loadPersona = useCallback(() => (
    api.get('/persona').then(({ data }) => { if (data) { setP(data); setLoadErr(false) } else { setLoadErr(true) } })
      .catch((e) => { console.error(e); setLoadErr(true); pushToast({ kind: 'error', msg: 'Could not load your persona' + (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '') }) })
  ), [pushToast])

  // One request; the screen simply waits for it rather than showing a "Loading…" line.
  const [reload, setReload] = useState(0)
  const { ready } = useSettled([() => loadPersona()], reload)

  useEffect(() => {
    window.addEventListener('beforeunload', flushPending)
    return () => { window.removeEventListener('beforeunload', flushPending); flushPending(); clearTimeout(flashTimer.current) }
  }, [flushPending])

  const flash = useCallback(() => {
    setSaved(true)
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setSaved(false), 1800)
  }, [])

  // One debounce timer per node so an autofill edit never cancels a résumé edit.
  // `payload` lets the local node hold rows the server should not, e.g. a blank Q&A pair.
  const saveNode = useCallback((key, value, payload) => {
    const body = payload === undefined ? value : payload
    setP((prev) => (prev ? { ...prev, [key]: value } : prev))
    clearTimeout(timers.current[key]?.timer)
    const timer = setTimeout(async () => {
      delete timers.current[key]
      try { await api.patch('/persona', { [key]: body }); flash() }
      catch (e) {
        console.error(`persona ${key}`, e)
        pushToast({ kind: 'error', msg: 'Could not save your changes' + (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '') })
      }
    }, 500)
    timers.current[key] = { timer, value: body }
  }, [flash, pushToast])

  // Spread the live node: keys with no control (preferences.preferred_locations) must survive.
  // Clearing a text field is the same intent as "— not answered", so an empty string drops the key too.
  const write = useCallback((node, fkey, value) => {
    const next = { ...((p || {})[node] || {}) }
    if (value === undefined || value === '') delete next[fkey]
    else next[fkey] = value
    saveNode(node, next)
  }, [p, saveNode])

  const resume = p?.resume_content && Object.keys(p.resume_content).length ? p.resume_content : EMPTY
  const { mutate, setField } = makeMutators(resume, (next) => saveNode('resume_content', next))

  // qa_bank may not be a list (legacy {question: answer} dict, or junk from the
  // extension) — guard against .map on it, which used to white-screen the whole shell.
  const qa = useMemo(() => {
    const raw = p?.qa_bank
    const list = Array.isArray(raw) ? raw : (raw && typeof raw === 'object' ? Object.entries(raw).map(([question, answer]) => ({ question, answer })) : [])
    return list.flatMap(toPairs)
  }, [p])
  // A pair with neither half filled is not an answer (POST /persona/qa-bank rejects it
  // with a 400) — keep it locally so the row stays editable, but leave it out of the PATCH.
  const writeQa = (list) => {
    const rows = list.map((e) => ({ question: e.question || '', answer: e.answer || '' }))
    saveNode('qa_bank', rows, rows.filter((e) => e.question.trim() || e.answer.trim()))
  }
  // the removal toast fires up to 5s later, so re-insert into the list as it is
  // *then* rather than the one captured when the ✕ was clicked
  const qaRef = useRef(qa)
  qaRef.current = qa
  const removeQa = (i) => {
    const gone = qa[i]
    writeQa(qa.filter((_, j) => j !== i))
    pushToast({ kind: 'undo', msg: 'Removed answer', action: 'Undo', onAction: () => writeQa([...qaRef.current.slice(0, i), gone, ...qaRef.current.slice(i)]) })
  }

  const filled = useMemo(() => {
    if (!p) return 0
    return GROUPS.reduce((n, g) => n + g[2].filter((f) => !f[4]?.uncounted && isSet((p[f[0]] || {})[f[1]])).length, 0)
  }, [p])

  // ── Import ─────────────────────────────────────────────────────────────────
  // Initial population, from a base résumé or a PDF. The *server* decides what an
  // import means (POST /api/persona/import replaces `contact` and `resume_content`,
  // leaves the five autofill nodes alone); this picks the source and re-seats the editor.
  // Uses ui.jsx's ChoiceModal, the same shell as the résumé editor's Tailor modal.
  const [importOpen, setImportOpen] = useState(false)
  const [importing, setImporting] = useState(false)

  const runImport = useCallback(async ({ label, run }) => {
    setImporting(true)
    try {
      const { data } = await run()
      // The import replaced both nodes outright; drop any pending PATCH holding the pre-import value.
      ;['contact', 'resume_content'].forEach((k) => {
        clearTimeout(timers.current[k]?.timer)
        delete timers.current[k]
      })
      setP(data.persona)
      const s = data.summary || {}
      pushToast({
        kind: 'success',
        msg: `Imported ${plural(s.roles, 'role')} · ${plural(s.bullets, 'bullet')} · ${plural(s.skill_groups, 'skill group')} from ${label}`,
      })
      setImportOpen(false)
    } catch (e) {
      // the modal stays up on a failure: the source is still picked, so "Replace" is one click away again
      console.error('persona import', e)
      pushToast({ kind: 'error', msg: 'Import failed' + errDetail(e) })
    } finally { setImporting(false) }
  }, [pushToast])

  const toggler = (setter, storeKey) => (name) => setter((prev) => {
    const n = new Set(prev); n.has(name) ? n.delete(name) : n.add(name)
    try { localStorage.setItem(storeKey, JSON.stringify([...n])) } catch { /* ignore */ }
    return n
  })
  const toggleSection = toggler(setSections, 'jobnavigator_v2_persona_sections')
  const toggleGroup = toggler(setGroups, 'jobnavigator_v2_persona_groups')

  // A 500 ("singleton missing — restart to re-seed") or a `200 null` needs a retry, not an infinite "Loading…".
  if (!ready || !p) return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 9, color: 'var(--muted)', fontSize: 13 }}>
      {ready && loadErr ? (
        <>
          <span>Couldn’t load your persona.</span>
          <Pill size="sm" onClick={() => { setLoadErr(false); setReload((n) => n + 1) }}>Try again</Pill>
        </>
      ) : null}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )

  const counts = sectionCounts(resume)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <HeaderRow as="header" variant="screen" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Persona</PageTitle>
          {/* integer line-heights: at the inherited 1.5, 13px would be 19.5px, landing
              rows below the header on a half pixel where Chrome rounds borders away */}
          {/* ui: keep — 13/20px is outside Helper's 11.5/16 tolerance; needed for whole-pixel rows */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Saves automatically · autofill {filled} of {ANSWERABLE} set
          </span>
        </div>
        {/* ui: keep — accent-ink save indicator, not a Link (would add cursor:pointer + hover) */}
        <span style={{ marginLeft: 'auto', fontSize: 11.5, lineHeight: '17px', color: 'var(--accent)', visibility: saved ? 'visible' : 'hidden' }}>Saved ✓</span>
        <Button variant="secondary" size="sm" busy={importing} ariaHaspopup="dialog"
          title="Fill contact details and résumé content from a base résumé or a PDF"
          onClick={() => setImportOpen(true)}>{importing ? 'Parsing…' : 'Import ↑'}</Button>
      </HeaderRow>

      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* left — résumé content, edited with the Résumé editor's own components */}
        <div style={{ flex: 1.1, minWidth: 0, borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <ColumnHead title="Résumé content"
            help="Your full work history, summary, skills and achievements. Used for tailored résumés, cover letters and job scoring." />
          <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 26px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            {SECTION_ORDER.map((name) => (
              <SectionShell key={name} name={name} count={counts[name]} open={sections.has(name)} onToggle={() => toggleSection(name)}>
                <SectionEditor name={name} data={resume} setField={setField} mutate={mutate}
                  onError={(msg) => pushToast({ kind: 'error', msg })}
                  onRemoved={(msg, undo) => pushToast({ kind: 'undo', msg, action: 'Undo', onAction: undo })}
                  pageHint={false} emptyNote="Tailored résumés use whatever you add here." />
              </SectionShell>
            ))}
          </div>
        </div>

        {/* right — the autofill nodes + the Q&A bank */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <ColumnHead title="Autofill content"
            help="Details used to fill application forms: contact, work authorization, EEO answers, salary and reusable screener answers. Not used for résumés or scoring." />
          <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 26px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            {GROUPS.map(([id, title, fields]) => {
              const open = groups.has(id)
              const counted = fields.filter((f) => !f[4]?.uncounted)
              const n = counted.filter((f) => isSet((p[f[0]] || {})[f[1]])).length
              const done = n === counted.length
              return (
                <Card key={id} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
                  <SectionHead card open={open} onToggle={() => toggleGroup(id)} hover="v2-clhead" style={{ padding: '11px 14px' }}>
                    <span style={{ flex: '0 0 auto', fontSize: 13, fontWeight: 600 }}>{title}</span>
                    <span style={{ flex: 1, minWidth: 0 }} />
                    <Helper size="xs" style={{ flex: '0 0 auto', color: done ? 'var(--accent)' : 'var(--muted)' }}>{done ? 'complete' : `${n} of ${counted.length} set`}</Helper>
                  </SectionHead>
                  {open && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, padding: '12px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
                      {fields.map(([node, fkey, label, kind, opts]) => (
                        <AutofillField key={`${node}.${fkey}`} node={node} fkey={fkey} label={label} kind={kind} opts={opts} nodes={p} write={write} />
                      ))}
                    </div>
                  )}
                </Card>
              )
            })}

            {/* Q&A bank — the one amber card; answers go to the LLM verbatim */}
            {/* ui: keep — only amber-tinted card in v2; answers reach the LLM verbatim, sets it apart */}
            <div style={{ border: '1px solid var(--amber-line)', borderRadius: 'var(--radius-card)', background: 'var(--amber-bg)', display: 'flex', flexDirection: 'column' }}>
              <SectionHead card open={groups.has('qa')} onToggle={() => toggleGroup('qa')} hover="v2-qahead" style={{ padding: '11px 14px' }}>
                <span style={{ flex: '0 0 auto', fontSize: 13, fontWeight: 600 }}>Q&amp;A bank</span>
                <Helper style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>reusable screener answers</Helper>
                <Helper size="xs" style={{ flex: '0 0 auto' }}>{qa.length} answer{qa.length === 1 ? '' : 's'}</Helper>
              </SectionHead>
              {groups.has('qa') && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7, padding: '12px 14px 14px', borderTop: '1px solid var(--amber-line-soft)' }}>
                  {/* ui: keep — row tinted to the amber card (--amber-line-soft); a Card would reintroduce --line */}
                  {qa.map((e, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 11px', border: '1px solid var(--amber-line-soft)', borderRadius: 'var(--radius-row)', background: 'var(--surface)' }}>
                      {/* BulletText needs a ROW flex parent — in a column parent, flex:1 drives
                          height instead of width and clips the answer to one line */}
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
                      <RemoveX onClick={() => removeQa(i)} title="Remove answer" lh="19px" />
                    </div>
                  ))}
                  {qa.length === 0 && <Helper>No saved answers yet — the extension can add them as you apply.</Helper>}
                  <DashedAdd onClick={() => writeQa([...qa, { question: '', answer: '' }])}>+ Add answer</DashedAdd>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {importOpen && <ImportModal busy={importing} onClose={() => setImportOpen(false)} onRun={runImport} pushToast={pushToast} />}

      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── Import ──────────────────────────────────────────────────────────────────
// Same ChoiceModal shell as the résumé editor's Tailor modal, with this screen's two
// sources as ChoiceCards/ChoiceRows. Escape closes (ModalPanel's useEscape), Enter picks a row (kb()).
const IMPORT_SOURCES = [
  ['resume', '☰ From a résumé', 'Copies a base résumé’s header and sections — no LLM call'],
  ['pdf', '↑ From a PDF', 'The AI reads the file — one LLM call; nothing is stored as a résumé'],
]

function ImportModal({ busy, onClose, onRun, pushToast }) {
  const [source, setSource] = useState('resume')
  const [bases, setBases] = useState(null)   // null while the list is in flight
  const [pick, setPick] = useState(null)
  const [file, setFile] = useState(null)
  const [dropping, setDropping] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    // The panel stays open on failure — the PDF half still works when the résumé list failed to load.
    api.get('/resumes', { params: { is_base: true } })
      .then(({ data }) => setBases(Array.isArray(data) ? data : []))
      .catch((e) => {
        console.error('persona import: list résumés', e)
        setBases([])
        pushToast({ kind: 'error', msg: 'Could not list your résumés' + errDetail(e) })
      })
  }, [pushToast])

  const chosen = (bases || []).find((r) => String(r.id) === String(pick))
  const takePdf = (f) => { if (f) { setFile(f); setSource('pdf') } }
  const canRun = source === 'pdf' ? !!file : !!chosen
  const run = () => {
    if (!canRun) return
    if (source === 'pdf') {
      onRun({
        label: file.name,
        run: () => {
          const fd = new FormData()
          fd.append('file', file)
          return api.post('/persona/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        },
      })
    } else {
      onRun({ label: chosen.name, run: () => api.post('/persona/import', { resume_id: chosen.id }) })
    }
  }

  return (
    <ChoiceModal
      title="Import persona content"
      sub="Fills your contact block and résumé content from one source."
      onClose={onClose}
      note={<Helper style={{ textWrap: 'pretty' }}>
        Replaces contact and résumé content. Work authorization, demographics, compensation, preferences and the Q&amp;A bank stay.
      </Helper>}
      action={busy ? 'Parsing…' : 'Replace'} actionVariant="danger" actionBusy={busy}
      actionDisabled={!canRun} onAction={run}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Label>Where from</Label>
        <div style={{ display: 'flex', gap: 7 }}>
          {IMPORT_SOURCES.map(([id, label, hint]) => (
            <ChoiceCard key={id} on={source === id} label={label} hint={hint} title={hint}
              onClick={() => setSource(id)} />
          ))}
        </div>
      </div>

      {source === 'resume' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Label>Which base résumé</Label>
          {/* nothing drawn while the list is in flight — rows land once, no "Loading…" line */}
          {(bases || []).map((r) => (
            <ChoiceRow key={r.id} on={String(pick) === String(r.id)} label={r.name}
              hint={ago(r.updated_at)} onClick={() => setPick(r.id)} />
          ))}
          {bases && bases.length === 0 && (
            <Band interactive={false} style={{ padding: 12 }}><Helper>No base résumés yet — import a PDF instead.</Helper></Band>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
          onDragOver={(e) => { e.preventDefault(); setDropping(true) }}
          onDragLeave={() => setDropping(false)}
          onDrop={(e) => {
            e.preventDefault(); setDropping(false)
            const f = e.dataTransfer?.files?.[0]
            if (f && /\.pdf$/i.test(f.name)) takePdf(f)
            else if (f) pushToast({ kind: 'error', msg: 'That is not a PDF.' })
          }}>
          <Label>Which PDF</Label>
          <DashedAdd big title="Choose a résumé PDF, or drop one here"
            onClick={() => fileRef.current?.click()} style={{ padding: '0 11px' }}>
            {/* a picked file writes its own name here, and a résumé PDF's name is
                routinely longer than the row — clip it rather than blow the row out */}
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {dropping ? 'Drop the PDF here' : file ? file.name : 'Choose a PDF…'}
            </span>
          </DashedAdd>
          {/* clear the value after every pick, or choosing the same PDF twice fires no change event */}
          {/* ui: keep — hidden <input type="file">, not a rendered field */}
          <input ref={fileRef} type="file" accept="application/pdf" style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; takePdf(f) }} />
        </div>
      )}
    </ChoiceModal>
  )
}
