// Shared résumé-content editors.
//
// A Resume's `json_data` and a Persona's `resume_content` are the same shape, so
// /v2/resumes/:id and /v2/persona edit it with the *same* components rather than
// two lookalikes that drift. Everything here was lifted verbatim out of
// ResumeEditor.jsx; the tailoring-diff props (baseSummary/baseExp/baseSkills) are
// optional, so Persona simply omits them and no ✦ marks render.
//
// Real data is looser than the EMPTY skeleton: live résumés carry keys these
// editors don't render, and omit whole sections. Every mutation
// goes through mutate(), which deep-clones and writes one path, so unknown keys
// survive — never rebuild a node from a known field list.
import React, { useState, useEffect, useLayoutEffect, useRef } from 'react'
import { Band, Card, DashedAdd, Input, Textarea } from './ui'

// The résumé sections' add-line IS ui.jsx's DashedAdd (accent ink · 1px dashed
// --dashadd-border · r6 · 11.5 · h28, `big` = 32/12/500) — re-exported under the
// same name so Persona/ResumeEditor keep importing it from here.
export { DashedAdd } from './ui'

export const DANGEROUS = new Set(['__proto__', 'constructor', 'prototype'])
// PERS-15 / STAT-22: v2 draws its controls as span/div, so none of them were
// focusable or operable from the keyboard. Spread `kb(fn)` onto such an element:
// it becomes tabbable, announces a role, and fires the same handler the click
// does on Enter/Space. The focus ring is theme.css's `[tabindex="0"]:focus-visible`.
export const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})
export const EMPTY = { header: { name: '', contact_items: [] }, summary: '', experience: [], skills: {}, education: [], projects: [], publications: [] }
export const SECTION_ORDER = ['Header', 'Summary', 'Experience', 'Skills', 'Education', 'Projects', 'Publications']

export const UPPER = { fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }

// Section counts for the collapsed header, from whichever sections exist.
export const sectionCounts = (data) => ({
  Experience: data.experience?.length || 0,
  Skills: Object.keys(data.skills || {}).length,
  Education: data.education?.length || 0,
  Projects: data.projects?.length || 0,
  Publications: data.publications?.length || 0,
})

// The two mutation helpers both screens use. `onData(next)` owns persistence.
export function makeMutators(data, onData) {
  const mutate = (fn) => { const d = JSON.parse(JSON.stringify(data || EMPTY)); fn(d); onData(d) }
  const setField = (path, val) => {
    const keys = String(path).split('.'); if (keys.some((k) => DANGEROUS.has(k))) return
    mutate((d) => { let o = d; for (let i = 0; i < keys.length - 1; i++) { if (o == null || typeof o !== 'object') return; o = o[keys[i]] } if (o && typeof o === 'object') o[keys[keys.length - 1]] = val })
  }
  return { mutate, setField }
}

// ── field primitives (v2-styled, with the **bold** shortcut) ─────────────────
export function Field({ label, value, onChange, placeholder, multiline, rows, flex }) {
  const boldKey = (e) => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'b')) return
    e.preventDefault()
    const ta = e.target, s = ta.selectionStart, en = ta.selectionEnd, t = ta.value
    if (s === en) return
    const sel = t.slice(s, en)
    if (t.slice(s - 2, s) === '**' && t.slice(en, en + 2) === '**') { onChange(t.slice(0, s - 2) + sel + t.slice(en + 2)); setTimeout(() => { ta.selectionStart = s - 2; ta.selectionEnd = en - 2 }, 0) }
    else { onChange(t.slice(0, s) + '**' + sel + '**' + t.slice(en)); setTimeout(() => { ta.selectionStart = s + 2; ta.selectionEnd = en + 2 }, 0) }
  }
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: flex || undefined, minWidth: 0 }}>
      {label && <span style={{ fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)' }}>{label}</span>}
      {multiline
        ? <Textarea value={value || ''} onChange={onChange} onKeyDown={boldKey} placeholder={placeholder} rows={rows || 3} />
        : <Input value={value || ''} onChange={onChange} placeholder={placeholder} />}
    </label>
  )
}
// bullet text: borderless auto-growing textarea so a bullet reads as flowing text
// (the row supplies the border/highlight) — matches the design's static-text bullets
// `lh` overrides the 1.5 line-height where the caller needs whole-pixel rows
// (12.5px * 1.5 = 18.75, which puts a bordered row on a half pixel and lets
// Chrome round its border away). The default is now 19px so bullet rows stay on whole pixels.
export function BulletText({ value, onChange, placeholder, bold, lh }) {
  const ref = useRef(null)
  const fit = () => { const el = ref.current; if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }
  // Measure after layout, and again whenever the box is resized. A plain
  // useEffect could run while the column was still at its pre-layout width,
  // which sized long text to a single clipped line that never re-measured.
  useLayoutEffect(fit, [value])
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(fit); ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const boldKey = (e) => {
    if (!((e.ctrlKey || e.metaKey) && e.key === 'b')) return
    e.preventDefault()
    const ta = e.target, s = ta.selectionStart, en = ta.selectionEnd, t = ta.value
    if (s === en) return
    const sel = t.slice(s, en)
    if (t.slice(s - 2, s) === '**' && t.slice(en, en + 2) === '**') { onChange(t.slice(0, s - 2) + sel + t.slice(en + 2)); setTimeout(() => { ta.selectionStart = s - 2; ta.selectionEnd = en - 2 }, 0) }
    else { onChange(t.slice(0, s) + '**' + sel + '**' + t.slice(en)); setTimeout(() => { ta.selectionStart = s + 2; ta.selectionEnd = en + 2 }, 0) }
  }
  // ui: keep — a bullet is flowing text, not a field: no border, no background, no
  // padding, resize:none + overflow:hidden for the autosize, and the row around it
  // supplies the box. Textarea would have to be overridden away entirely.
  return <textarea ref={ref} value={value || ''} onChange={(e) => onChange(e.target.value)} onInput={fit} onKeyDown={boldKey} rows={1} placeholder={placeholder}
    style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', resize: 'none', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12.5, lineHeight: lh || '19px', color: bold ? 'var(--text)' : 'var(--text-2)', fontWeight: bold ? 600 : 400, padding: 0, overflow: 'hidden' }} />
}
export const RemoveLink = ({ onClick, children = 'Remove' }) => (
  <span onClick={onClick} {...kb(onClick)} style={{ fontSize: 11.5, lineHeight: '17px', color: 'var(--muted)', cursor: 'pointer', whiteSpace: 'nowrap' }} className="v2-hover-bad v2-hover-bad-text">{children}</span>
)
// The ✕ every row carries. One component so the keyboard treatment (PERS-15) is
// written once rather than at each of the five sites.
export const RemoveX = ({ onClick, title = 'Remove', size = 11, lh }) => (
  <span onClick={onClick} {...kb(onClick)} title={title} aria-label={title} className="v2-hover-bad v2-hover-bad-text"
    style={{ flex: '0 0 auto', color: 'var(--faint)', fontSize: size, cursor: 'pointer', lineHeight: lh }}>✕</span>
)
// PERS-13: removals are undoable rather than confirmed — no window.confirm anywhere.
// `mutate` closes over the data of the render that produced the toast, so
// re-inserting through it five seconds later would work off stale state; keep the
// live one in a ref and restore through that. `onRemoved(label, restore)` is the
// toast host (Persona / ResumeEditor); without it a removal is simply immediate.
export function useUndoRemove(mutate, onRemoved) {
  const live = useRef(mutate)
  live.current = mutate
  return (label, remove, restore) => { mutate(remove); onRemoved?.(label, () => live.current(restore)) }
}
// RES2-10: the vertical rule that separates the two halves of an editor's context
// band. The résumé band drew it as the glyph "  │  " in --line and the letter band
// as a "·"; the design (Resumes Shelf.dc.html:158) is a 1×11 block in --edge.
// One component so the two bands cannot drift again.
export const BandRule = () => (
  <span aria-hidden="true" style={{ display: 'inline-block', width: 1, height: 11, margin: '0 9px', verticalAlign: 'middle', alignSelf: 'center', background: 'var(--edge)' }} />
)
// `note` is the second line. It defaults to the résumé PDF wording; Persona
// overrides it, since its resume_content is a source pool that never prints.
export const EmptyState = ({ what, note }) => (
  <Band interactive={false} style={{ padding: '16px 12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
    <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--text-2)' }}>No {what} yet</span>
    <span style={{ fontSize: 11.5, lineHeight: '17px', color: 'var(--muted)', textAlign: 'center' }}>{note || 'Empty sections are skipped in the PDF — nothing prints until you add one.'}</span>
  </Band>
)
export const MenuHead = ({ children }) => <div style={{ padding: '4px 11px 3px', fontSize: 9.5, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{children}</div>
export const MenuItem = ({ icon, label, hint, onClick }) => (
  <div onClick={onClick} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
    {icon != null && <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>{icon}</span>}
    <span style={{ flex: 1, minWidth: 0 }}>{label}</span>
    {hint && <span style={{ flex: '0 0 auto', fontSize: 10.5, lineHeight: '16px', color: 'var(--faint)' }}>{hint}</span>}
  </div>
)
export const MicroField = ({ label, value, onChange, placeholder }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <span style={{ fontSize: 9.5, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{label}</span>
    <Input value={value || ''} onChange={onChange} placeholder={placeholder} ariaLabel={label} />
  </div>
)

// The collapsible section card shared by both screens. `meta` is the optional
// right-aligned note (ResumeEditor's "● changed by tailoring").
export function SectionShell({ name, count, open, onToggle, meta, children }) {
  return (
    <Card style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
      <div onClick={onToggle} {...kb(onToggle)} aria-expanded={!!open} className="v2-hover-accent" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', cursor: 'pointer', borderRadius: 9, lineHeight: '18px' }}>
        <span style={{ color: 'var(--muted)', fontSize: 10 }}>{open ? '⌄' : '›'}</span>
        <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
          {count != null && <span style={{ fontSize: 11.5, lineHeight: '17px', color: 'var(--muted)' }}>({count})</span>}
        </span>
        {meta}
      </div>
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '4px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
          {children}
        </div>
      )}
    </Card>
  )
}

// Renders the right section editor for a SECTION_ORDER name. Tailoring props are
// optional — Persona passes none, so nothing renders as changed.
export function SectionEditor({ name, data, setField, mutate, baseData, emptyNote, pageHint = true, onError, onRemoved }) {
  switch (name) {
    case 'Header': return <HeaderEditor data={data} setField={setField} mutate={mutate} onRemoved={onRemoved} />
    case 'Summary': return <SummaryEditor pageHint={pageHint} data={data} setField={setField} baseSummary={baseData?.summary} />
    case 'Experience': return <ExperienceEditor emptyNote={emptyNote} data={data} setField={setField} mutate={mutate} baseExp={baseData?.experience} onRemoved={onRemoved} />
    case 'Skills': return <SkillsEditor emptyNote={emptyNote} data={data} mutate={mutate} baseSkills={baseData?.skills} onError={onError} onRemoved={onRemoved} />
    case 'Education': return <EducationEditor emptyNote={emptyNote} data={data} setField={setField} mutate={mutate} onRemoved={onRemoved} />
    case 'Projects': return <ProjectsEditor emptyNote={emptyNote} data={data} setField={setField} mutate={mutate} onRemoved={onRemoved} />
    case 'Publications': return <PublicationsEditor emptyNote={emptyNote} data={data} setField={setField} mutate={mutate} onRemoved={onRemoved} />
    default: return null
  }
}

export function HeaderEditor({ data, setField, mutate, onRemoved }) {
  const items = data.header?.contact_items || []
  const undoRemove = useUndoRemove(mutate, onRemoved)
  const move = (i, dir) => mutate((d) => { const a = d.header.contact_items; const j = i + dir; if (j < 0 || j >= a.length) return;[a[i], a[j]] = [a[j], a[i]] })
  const arrows = (i) => (
    <span style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1, color: 'var(--faint)', fontSize: 8, cursor: 'pointer' }}>
      <span onClick={() => move(i, -1)} {...kb(() => move(i, -1))} title="Move up" className="v2-navlink">▲</span><span onClick={() => move(i, 1)} {...kb(() => move(i, 1))} title="Move down" className="v2-navlink">▼</span>
    </span>
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 10 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <span style={UPPER}>Full name</span>
        <Input value={data.header?.name || ''} onChange={(v) => setField('header.name', v)} ariaLabel="Full name" />
      </div>
      {/* R3-B-01: header.title round-trips through the API and prints in the
          templates, but had no editor — it was invisible and uneditable in v2.
          Optional: an empty value renders nothing at all in the PDF. */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <span style={UPPER}>Title</span>
        <Input value={data.header?.title || ''} onChange={(v) => setField('header.title', v)} placeholder="Headline, e.g. Senior Product Manager" ariaLabel="Title" />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={UPPER}>Contact items</span>
          <span style={{ marginLeft: 'auto', fontSize: 10.5, lineHeight: '16px', color: 'var(--faint)' }}>text · link · stub</span>
        </div>
        {items.map((it, i) => {
          const showStub = it.url && !it.url.startsWith('mailto:')
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ flex: '45 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* controls + text: 45 % of the row */}
              {arrows(i)}
              <Input value={it.text || ''} onChange={(v) => setField(`header.contact_items.${i}.text`, v)} placeholder="Display text" ariaLabel="Contact item text" style={{ flex: 1, minWidth: 0 }} />
              </div>
              <div style={{ flex: '55 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* url + stub: 55 % */}
              <Input value={it.url || ''} onChange={(v) => setField(`header.contact_items.${i}.url`, v)} placeholder="URL (optional)" ariaLabel="Contact item URL" style={{ flex: 1, minWidth: 0 }} />
              {showStub && <Input value={it.stub || ''} onChange={(v) => setField(`header.contact_items.${i}.stub`, v)} placeholder="id" mono ariaLabel="Tracer link stub" title="Short stub for the tracer link id (e.g. l, w, gh)" style={{ flex: '0 0 34px', padding: '0 6px', textAlign: 'center' }} />}
              <RemoveX onClick={() => undoRemove('Removed contact item',
                (d) => d.header.contact_items.splice(i, 1),
                (d) => { d.header = d.header || {}; (d.header.contact_items = d.header.contact_items || []).splice(i, 0, it) })} />
              </div>
            </div>
          )
        })}
        <DashedAdd onClick={() => mutate((d) => { d.header = d.header || { contact_items: [] }; (d.header.contact_items = d.header.contact_items || []).push({ text: '', url: '' }) })}>+ Add contact item</DashedAdd>
      </div>
    </div>
  )
}
export function ExperienceEditor({ emptyNote, data, setField, mutate, baseExp, onRemoved }) {
  const exp = data.experience || []
  const undoRemove = useUndoRemove(mutate, onRemoved)
  const [open, setOpen] = useState(() => new Set([0]))   // first entry open by default
  const setBullet = (i, bi, v) => mutate((d) => { d.experience[i].bullets[bi] = v })
  const addBullet = (i) => mutate((d) => { d.experience[i].bullets = d.experience[i].bullets || []; d.experience[i].bullets.push('') })
  const bulletMark = (i, bi, txt) => {
    if (!baseExp) return null
    const bb = baseExp[i]?.bullets || []
    if (bi >= bb.length) return { kind: 'added', label: 'Added by tailoring' }
    if (bb[bi] !== txt) return { kind: 'changed', label: 'Changed by tailoring', base: bb[bi] }
    return null
  }
  const entryChanged = (e, i) => (e.bullets || []).some((b, bi) => bulletMark(i, bi, b)) || (e.suggested_bullets || []).length > 0
  const toggle = (i) => setOpen((p) => { const n = new Set(p); n.has(i) ? n.delete(i) : n.add(i); return n })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {exp.map((e, i) => {
        const ch = entryChanged(e, i), isOpen = open.has(i), nb = (e.bullets || []).length
        return (
          // containers are never tinted — only the prose rows inside them are.
          // The header's ● still says the entry holds unreviewed changes, and the
          // bullet rows below carry the --change-soft/--change-bg treatment.
          <Card key={i} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
            {/* explicit integer line-height: at the inherited 1.5 a 12.5px line is
                18.75px, which made this row 36.75px tall and put every row below it
                (and the Skills/Education/Projects cards) on a half pixel, where
                Chrome rounds their 1px borders away — same fix as SectionShell */}
            <div onClick={() => toggle(i)} {...kb(() => toggle(i))} aria-expanded={isOpen} className="v2-hover-accent" style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '9px 11px', cursor: 'pointer', borderRadius: 9, lineHeight: '18px' }}>
              <span style={{ flex: '0 0 auto', color: 'var(--muted)', fontSize: 10 }}>{isOpen ? '⌄' : '›'}</span>
              <span style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.title || 'Untitled role'}</span>
              <span style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.company}</span>
              <span style={{ flex: '0 0 auto', marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--sans)', color: 'var(--muted)' }}>{e.date}</span>
              <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>{nb} bullet{nb === 1 ? '' : 's'}</span>
              {ch && <span title="Contains unreviewed tailoring changes" style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--warn)' }}>●</span>}
            </div>
            {isOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '2px 11px 11px', borderTop: '1px solid var(--line-soft)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7, paddingTop: 9 }}>
                  <Field label="Company" value={e.company} onChange={(v) => setField(`experience.${i}.company`, v)} />
                  <Field label="Title" value={e.title} onChange={(v) => setField(`experience.${i}.title`, v)} />
                  <Field label="Location" value={e.location} onChange={(v) => setField(`experience.${i}.location`, v)} />
                  <Field label="Date" value={e.date} onChange={(v) => setField(`experience.${i}.date`, v)} placeholder="Jan 2022 – Present" />
                </div>
                <Field label="Description" value={e.description} onChange={(v) => setField(`experience.${i}.description`, v)} placeholder="Optional role description" />
                {(e.bullets || []).map((b, bi) => {
                  const m = bulletMark(i, bi, b)
                  return (
                    /* ui: keep — a field-shaped prose row (r6 = --radius-field), not a
                       card: it wraps one BulletText and carries the ✦ tailoring tint */
                    <div key={bi} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: `1px solid ${m ? 'var(--change-soft)' : 'var(--line)'}`, background: m ? 'var(--change-bg)' : 'var(--surface)', borderRadius: 6 }}>
                      <span title={m?.label || ''} style={{ flex: '0 0 auto', color: m ? 'var(--accent)' : 'var(--muted)', fontSize: 11, lineHeight: '19px' }}>{m ? '✦' : '—'}</span>
                      <BulletText value={b} onChange={(v) => setBullet(i, bi, v)} />
                      {m?.kind === 'changed' && <span onClick={() => setBullet(i, bi, m.base)} title="Decline this tailoring change — restores the base text" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500, lineHeight: '19px' }}>↩</span>}
                      <RemoveX size={10} lh="19px" onClick={() => undoRemove('Removed bullet',
                        (d) => d.experience[i].bullets.splice(bi, 1),
                        (d) => { d.experience[i].bullets = d.experience[i].bullets || []; d.experience[i].bullets.splice(bi, 0, b) })} />
                    </div>
                  )
                })}
                {/* ui: keep — same field-shaped prose row, always tinted */}
                {(e.suggested_bullets || []).map((sb, k) => (
                  <div key={`sb${k}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: '1px solid var(--change-soft)', background: 'var(--change-bg)', borderRadius: 6 }}>
                    <span title="Suggested by tailoring — keep on review" style={{ flex: '0 0 auto', color: 'var(--accent)', fontSize: 11, lineHeight: '19px' }}>✦</span>
                    <span style={{ flex: 1, fontSize: 12.5, lineHeight: '19px', color: 'var(--text-2)' }}>{sb}</span>
                    <span style={{ flex: '0 0 auto', fontSize: 9.5, color: 'var(--muted)', lineHeight: '19px' }}>suggested</span>
                  </div>
                ))}
                {/* PERS-19: accent like every other add-control on the screen */}
                <DashedAdd onClick={() => addBullet(i)}>+ Add bullet</DashedAdd>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => undoRemove('Removed role',
                  (d) => d.experience.splice(i, 1),
                  (d) => { d.experience = d.experience || []; d.experience.splice(i, 0, e) })}>Remove role</RemoveLink></div>
              </div>
            )}
          </Card>
        )
      })}
      {exp.length === 0 && <EmptyState note={emptyNote} what="experience" />}
      <DashedAdd big onClick={() => mutate((d) => { d.experience = d.experience || []; d.experience.push({ company: '', title: '', location: '', date: '', description: '', bullets: [] }) })}>+ Add experience</DashedAdd>
    </div>
  )
}
// Summary as a marked row (tailoring ✦/— + revert + highlight) with a char-count meta
export function SummaryEditor({ data, setField, baseSummary, pageHint = true }) {
  const txt = data.summary || ''
  const changed = baseSummary != null && baseSummary !== txt
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 10 }}>
      {/* ui: keep — the summary is one field-shaped prose row (r6), not a card */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 11px', border: `1px solid ${changed ? 'var(--change-soft)' : 'var(--line)'}`, background: changed ? 'var(--change-bg)' : 'var(--surface)', borderRadius: 6 }}>
        <span title={changed ? 'Changed by tailoring' : ''} style={{ flex: '0 0 auto', color: changed ? 'var(--accent)' : 'var(--muted)', fontSize: 11, lineHeight: '19px' }}>{changed ? '✦' : '—'}</span>
        <BulletText value={txt} onChange={(v) => setField('summary', v)} />
        {changed && <span onClick={() => setField('summary', baseSummary)} title="Decline this tailoring change — restores the base text" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500, lineHeight: '19px' }}>↩</span>}
      </div>
      <span style={{ fontSize: 10.5, lineHeight: '16px', color: 'var(--faint)' }}>{txt.length} characters{pageHint && txt.length > 600 ? ' · long summaries can push to a second page' : ''}</span>
    </div>
  )
}

// Skills: fixed-width category + value with tailoring ✦/revert/highlight when changed
export function SkillsEditor({ emptyNote, data, mutate, baseSkills, onError, onRemoved }) {
  const entries = Object.entries(data.skills || {})
  const undoRemove = useUndoRemove(mutate, onRemoved)
  // RES-04 / PERS-03: a category name is user text, so routing the value write
  // through the dotted-path setField silently dropped every write to a category
  // containing a "." (".NET", "Node.js", "Web3.0"). Write the key directly.
  const setVal = (k, v) => { if (DANGEROUS.has(k)) return; mutate((d) => { d.skills = d.skills || {}; d.skills[k] = v }) }
  // RES-05 / PERS-04: renaming onto an existing category used to overwrite that
  // category and destroy its values with no warning and no undo. Refuse the
  // collision (and a blank name); the caller reverts the uncontrolled input.
  const rename = (oldK, newK) => {
    if (oldK === newK) return true
    if (!newK.trim()) { onError?.('A skills category needs a name.'); return false }
    if (DANGEROUS.has(newK)) { onError?.(`“${newK}” can’t be used as a category name.`); return false }
    if (Object.prototype.hasOwnProperty.call(data.skills || {}, newK)) { onError?.(`“${newK}” already exists — renaming onto it would erase its values.`); return false }
    mutate((d) => { const ns = {}; for (const [k, v] of Object.entries(d.skills)) ns[k === oldK ? newK : k] = v; d.skills = ns })
    return true
  }
  const move = (k, dir) => mutate((d) => { const e = Object.entries(d.skills); const i = e.findIndex(([x]) => x === k); const j = i + dir; if (i < 0 || j < 0 || j >= e.length) return;[e[i], e[j]] = [e[j], e[i]]; d.skills = Object.fromEntries(e) })
  const liveRename = useRef(rename)
  liveRename.current = rename
  const arrows = (k) => (
    <span style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1, color: 'var(--faint)', fontSize: 8, cursor: 'pointer' }}>
      <span onClick={() => move(k, -1)} {...kb(() => move(k, -1))} title="Move up" className="v2-navlink">▲</span><span onClick={() => move(k, 1)} {...kb(() => move(k, 1))} title="Move down" className="v2-navlink">▼</span>
    </span>
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 10 }}>
      {entries.map(([k, v], ei) => {
        const changed = baseSkills != null && (k in baseSkills) && String(baseSkills[k] || '') !== String(v || '')
        const added = baseSkills != null && !(k in baseSkills)
        const marked = changed || added
        return (
          // RES-31: the row is keyed by position, not by the category name — a
          // debounced rename changes the name mid-edit, and a name key would
          // remount the input and steal the caret on every commit.
          <div key={ei} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {arrows(k)}
            <CategoryName name={k} rename={liveRename} />
            {/* the ✦ and the --change-soft border carry the tailoring signal here;
                the --change-bg fill is reserved for tailored prose (experience
                bullets and the summary), so a skills row keeps its field colour. */}
            {/* ui: keep — a *field* box (h29 · r6 · --edge · --surface-2) that holds a
                bare input plus the ✦/added/↩ affordances, not a card */}
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6, height: 29, padding: '0 9px', border: `1px solid ${marked ? 'var(--change-soft)' : 'var(--edge)'}`, background: 'var(--surface-2)', borderRadius: 6 }}>
              {marked && <span title={added ? 'Added by tailoring' : 'Changed by tailoring'} style={{ flex: '0 0 auto', color: 'var(--accent)', fontSize: 10 }}>✦</span>}
              {/* ui: keep — bare input inside the row's own bordered box; that box, not
                  the field, carries the tailoring border and the added/decline affordances */}
              <input value={v} onChange={(e) => setVal(k, e.target.value)} placeholder="Skill values…" style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: 'var(--text-2)', fontFamily: 'var(--sans)' }} />
              {added && <span title="Added by tailoring" style={{ flex: '0 0 auto', padding: '1px 6px', borderRadius: 4, background: 'var(--change-soft)', color: 'var(--good)', fontSize: 11, fontWeight: 500 }}>added</span>}
              {changed && <span onClick={() => setVal(k, baseSkills[k])} title="Decline this tailoring change" style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)', cursor: 'pointer', fontWeight: 500 }}>↩</span>}
            </div>
            {/* restore rebuilds the key order so the row comes back where it was */}
            <RemoveX onClick={() => undoRemove('Removed skill category',
              (d) => { delete d.skills[k] },
              (d) => { const en = Object.entries(d.skills || {}); en.splice(ei, 0, [k, v]); d.skills = Object.fromEntries(en) })} />
          </div>
        )
      })}
      {entries.length === 0 && <EmptyState note={emptyNote} what="skills" />}
      <DashedAdd onClick={() => mutate((d) => { d.skills = d.skills || {}; d.skills[`Skill ${Object.keys(d.skills).length + 1}`] = '' })}>+ Add skill row</DashedAdd>
    </div>
  )
}
// RES-31: the Skills category was the one field on the screen that genuinely saved
// on blur — everything else is a 500 ms trailing debounce. Same debounce here, with
// the rename-collision refusal intact: a refused name snaps back to the stored one
// (the caller's onError explains why). Blur flushes any pending rename immediately.
function CategoryName({ name, rename }) {
  const [draft, setDraft] = useState(name)
  const timer = useRef(null)
  useEffect(() => { setDraft(name) }, [name])
  useEffect(() => () => clearTimeout(timer.current), [])
  const commit = (v) => { clearTimeout(timer.current); if (v !== name && !rename.current(name, v)) setDraft(name) }
  return (
    <Input value={draft} placeholder="Category" ariaLabel="Skill category"
      onChange={(v) => { setDraft(v); clearTimeout(timer.current); timer.current = setTimeout(() => commit(v), 500) }}
      onBlur={() => commit(draft)}
      style={{ flex: '0 0 118px', fontWeight: 500 }} />
  )
}
export function EducationEditor({ emptyNote, data, setField, mutate, onRemoved }) {
  const undoRemove = useUndoRemove(mutate, onRemoved)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {(data.education || []).map((e, i) => (
        <Card key={i} style={{ padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="School" value={e.school} onChange={(v) => setField(`education.${i}.school`, v)} />
            <MicroField label="Location" value={e.location} onChange={(v) => setField(`education.${i}.location`, v)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="Degree" value={e.degree} onChange={(v) => setField(`education.${i}.degree`, v)} />
            <MicroField label="Years" value={e.years} onChange={(v) => setField(`education.${i}.years`, v)} placeholder="2015 – 2019" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => undoRemove('Removed education entry',
            (d) => d.education.splice(i, 1),
            (d) => { d.education = d.education || []; d.education.splice(i, 0, e) })} /></div>
        </Card>
      ))}
      {(data.education || []).length === 0 && <EmptyState note={emptyNote} what="education" />}
      <DashedAdd big onClick={() => mutate((d) => { d.education = d.education || []; d.education.push({ school: '', location: '', degree: '' }) })}>+ Add education</DashedAdd>
    </div>
  )
}
export function ProjectsEditor({ emptyNote, data, setField, mutate, onRemoved }) {
  const undoRemove = useUndoRemove(mutate, onRemoved)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9, paddingTop: 10 }}>
      {(data.projects || []).map((p, i) => (
        <Card key={i} style={{ padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <MicroField label="Name" value={p.name} onChange={(v) => setField(`projects.${i}.name`, v)} />
            <MicroField label="URL" value={p.url} onChange={(v) => setField(`projects.${i}.url`, v)} />
          </div>
          <MicroField label="Description" value={p.description} onChange={(v) => setField(`projects.${i}.description`, v)} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 9.5, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>Bullets</span>
            {(p.bullets || []).map((b, bi) => (
              /* ui: keep — field-shaped prose row (r6), as in Experience */
              <div key={bi} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', border: '1px solid var(--line)', background: 'var(--surface)', borderRadius: 6 }}>
                <span style={{ flex: '0 0 auto', color: 'var(--muted)', fontSize: 11, lineHeight: '19px' }}>—</span>
                <BulletText value={b} onChange={(v) => mutate((d) => { d.projects[i].bullets[bi] = v })} />
                <RemoveX size={10} lh="19px" onClick={() => undoRemove('Removed bullet',
                  (d) => d.projects[i].bullets.splice(bi, 1),
                  (d) => { d.projects[i].bullets = d.projects[i].bullets || []; d.projects[i].bullets.splice(bi, 0, b) })} />
              </div>
            ))}
            <DashedAdd onClick={() => mutate((d) => { d.projects[i].bullets = d.projects[i].bullets || []; d.projects[i].bullets.push('') })}>+ Add bullet</DashedAdd>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => undoRemove('Removed project',
            (d) => d.projects.splice(i, 1),
            (d) => { d.projects = d.projects || []; d.projects.splice(i, 0, p) })}>Remove project</RemoveLink></div>
        </Card>
      ))}
      {(data.projects || []).length === 0 && <EmptyState note={emptyNote} what="projects" />}
      <DashedAdd big onClick={() => mutate((d) => { d.projects = d.projects || []; d.projects.push({ name: '', description: '', url: '', bullets: [] }) })}>+ Add project</DashedAdd>
    </div>
  )
}
export function PublicationsEditor({ emptyNote, data, setField, mutate, onRemoved }) {
  const pubs = data.publications || []
  const undoRemove = useUndoRemove(mutate, onRemoved)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 10 }}>
      {pubs.length === 0 ? <EmptyState note={emptyNote} what="publications" /> : pubs.map((p, i) => (
        <Card key={i} style={{ padding: 11, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <MicroField label="Title" value={p.title} onChange={(v) => setField(`publications.${i}.title`, v)} />
          <MicroField label="Description" value={p.description} onChange={(v) => setField(`publications.${i}.description`, v)} />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}><RemoveLink onClick={() => undoRemove('Removed publication',
            (d) => d.publications.splice(i, 1),
            (d) => { d.publications = d.publications || []; d.publications.splice(i, 0, p) })} /></div>
        </Card>
      ))}
      <DashedAdd big onClick={() => mutate((d) => { d.publications = d.publications || []; d.publications.push({ title: '', description: '' }) })}>+ Add publication</DashedAdd>
    </div>
  )
}
