import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
const ago = (iso) => {
  if (!iso) return ''
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 60) return `${Math.max(1, m)}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  return `${Math.floor(h / 24)}d`
}

export const LENGTHS = [['concise', 'Concise'], ['standard', 'Standard'], ['detailed', 'Detailed']]

// Stage chip on a row mirrors the Applications stage colours.
export const STAGE_CLASS = { applied: 'cc-smartrecruiters', interview: 'cc-workday', offer: 'cc-tier1', rejected: 'cc-generic' }

const LABEL = { fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }
const CTRL = {
  height: 33, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 8,
  background: 'var(--surface)', display: 'flex', alignItems: 'center', lineHeight: 1,
  justifyContent: 'space-between', fontSize: 12.5, cursor: 'pointer', color: 'var(--text)',
}
const POPOVER = {
  position: 'absolute', top: '100%', left: 0, zIndex: 40, marginTop: 4, background: 'var(--surface)',
  border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)',
  padding: 5, display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 300, overflow: 'auto',
}

// Design draws these selects as a bordered row with a ▾ — a native <select>
// can't carry the two-line job labels, so this is a small popover instead.
export function Picker({ value, options, placeholder, onPick, width }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [open])
  const cur = options.find((o) => o.id === value)
  return (
    <span style={{ position: 'relative', display: 'block' }} onClick={(e) => e.stopPropagation()}>
      <div onClick={() => setOpen((v) => !v)} className="v2-bd" style={{ ...CTRL, borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
        <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: cur ? 'var(--text)' : 'var(--muted)' }}>
          {cur ? cur.label : placeholder}
        </span>
        <span style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--muted)', marginLeft: 8 }}>▾</span>
      </div>
      {open && (
        <div className="v2-scroll" style={{ ...POPOVER, width: width || '100%' }}>
          {options.length === 0 && <div style={{ padding: '7px 9px', fontSize: 12, color: 'var(--muted)' }}>Nothing to pick yet.</div>}
          {options.map((o) => (
            <div key={o.id} className="v2-menuitem" onClick={() => { onPick(o.id); setOpen(false) }}
              style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', minWidth: 0,
                color: o.id === value ? 'var(--accent)' : 'var(--text-2)', fontWeight: o.id === value ? 500 : 400,
                background: o.id === value ? 'var(--accent-soft)' : 'transparent' }}>
              <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.label}</div>
              {o.sub && <div style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.sub}</div>}
            </div>
          ))}
        </div>
      )}
    </span>
  )
}

// Voice chips + length segments are shared with the editor's Regenerate modal.
export function VoicePicker({ presets, value, onPick }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {presets.map((v) => {
        const on = v.id === value
        return (
          <div key={v.id} onClick={() => onPick(v.id)} title={v.instruction || ''} className="v2-bd"
            style={{ height: 27, padding: '0 11px', borderRadius: 99, display: 'flex', alignItems: 'center', lineHeight: 1,
              border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)',
              color: on ? 'var(--accent)' : 'var(--text-2)', fontSize: 11.5, whiteSpace: 'nowrap', cursor: 'pointer' }}>{v.label}</div>
        )
      })}
    </div>
  )
}

export function LengthPicker({ value, onPick }) {
  return (
    <div style={{ display: 'flex', gap: 5 }}>
      {LENGTHS.map(([id, name]) => {
        const on = id === value
        return (
          <div key={id} onClick={() => onPick(id)} className="v2-bd"
            style={{ flex: 1, height: 31, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
              border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)',
              color: on ? 'var(--accent)' : 'var(--text-2)', fontSize: 12, fontWeight: on ? 600 : 400, cursor: 'pointer' }}>{name}</div>
        )
      })}
    </div>
  )
}

// ── main ─────────────────────────────────────────────────────────────────────
export default function CoverLetters() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [letters, setLetters] = useState([])
  const [resumes, setResumes] = useState([])
  const [jobs, setJobs] = useState([])
  const [personaAvailable, setPersonaAvailable] = useState(false)
  const [presets, setPresets] = useState([])
  const [genResume, setGenResume] = useState('')
  const [genJob, setGenJob] = useState('')
  const [genVoice, setGenVoice] = useState('')
  const [genLength, setGenLength] = useState('standard')
  const [pending, setPending] = useState([])     // active generate_cover_letter runs
  const [query, setQuery] = useState('')
  const [err, setErr] = useState('')
  const pendingRef = useRef([])
  useEffect(() => { pendingRef.current = pending }, [pending])

  const load = useCallback(async () => {
    try { const { data } = await api.get('/cover-letters'); setLetters(data || []) } catch (e) { console.error(e) }
  }, [])

  useEffect(() => {
    load()
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
    // saved AND applied — v1 fetched only saved, so a ?job= from an applied job
    // landed on an id with no matching option and the field rendered blank
    api.get('/jobs', { params: { status: 'saved,applied', limit: 200 } })   // 200 is the endpoint's cap
      .then(({ data }) => setJobs(data.jobs || [])).catch(() => {})
    api.get('/settings').then(({ data }) => {
      let p = data.cover_letter_voice_presets
      if (typeof p === 'string') { try { p = JSON.parse(p) } catch { p = [] } }
      const list = Array.isArray(p) ? p : []
      setPresets(list)
      setGenVoice(data.cover_letter_default_voice || list[0]?.id || '')
    }).catch(() => {})
  }, [load])

  // ?job= / ?resume= deep links (from the Feed, Résumé editor and Applications)
  useEffect(() => {
    const j = searchParams.get('job'); const r = searchParams.get('resume')
    if (!j && !r) return
    if (j) {
      setGenJob(j)
      // make sure the target is pickable even if it's outside the fetched window
      api.get(`/jobs/${j}`).then(({ data }) => {
        setJobs((p) => p.some((x) => x.id === data.id) ? p : [data, ...p])
      }).catch(() => {})
    }
    if (r) {
      setGenResume(r)
      api.get(`/resumes/${r}`).then(({ data }) => {
        setResumes((p) => p.some((x) => x.id === data.id) ? p : [data, ...p])
      }).catch(() => {})
    }
    setSearchParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // poll for running generations; when one clears, reload the list
  useEffect(() => {
    let dead = false
    const tick = async () => {
      try {
        const { data } = await api.get('/monitor/active')
        const runs = (data || []).filter((r) => r.job_type === 'generate_cover_letter')
        if (dead) return
        const before = pendingRef.current
        const ids = runs.map((r) => r.run_id).join(',')
        if (ids !== before.map((r) => r.run_id).join(',')) setPending(runs)
        if (before.length && before.some((b) => !runs.some((r) => r.run_id === b.run_id))) load()
      } catch { /* retry next tick */ }
    }
    tick()
    const iv = setInterval(tick, 3000)
    return () => { dead = true; clearInterval(iv) }
  }, [load])

  const resumeOpts = useMemo(() => [
    ...(personaAvailable ? [{ id: 'persona', label: 'Persona (full profile)' }] : []),
    ...resumes.map((r) => ({ id: r.id, label: r.name })),
  ], [resumes, personaAvailable])

  const jobOpts = useMemo(() => jobs.map((j) => ({
    id: j.id, label: j.company ? `${j.company} — ${j.title}` : (j.title || 'Untitled role'),
  })), [jobs])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return letters
    return letters.filter((c) => `${c.name || ''} ${c.company || ''} ${c.title || ''}`.toLowerCase().includes(q))
  }, [letters, query])

  const linked = letters.filter((c) => c.has_application).length
  const countLine = `${letters.length} letter${letters.length === 1 ? '' : 's'} · ${linked} linked to applications`

  const generating = pending.length > 0
  const genJobLabel = jobOpts.find((o) => o.id === genJob)?.label || ''
  const voiceLabel = presets.find((p) => p.id === genVoice)?.label || genVoice
  const lengthLabel = LENGTHS.find(([id]) => id === genLength)?.[1] || genLength

  const generate = async () => {
    if (!genResume || !genJob || generating) return
    setErr('')
    try {
      const { data } = await api.post('/cover-letters/generate', {
        resume_id: genResume, job_id: genJob, voice: genVoice, length: genLength,
      })
      setPending((p) => [...p, { run_id: data.run_id, job_type: 'generate_cover_letter' }])
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Generation failed')
    }
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Cover Letters</h1>
          <span style={{ fontSize: 13, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
      </header>

      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {/* generate panel */}
        <div className="v2-scroll" style={{ flex: '0 0 340px', borderRight: '1px solid var(--line)', background: 'var(--bg)', overflow: 'auto', padding: '16px 26px 20px 30px', display: 'flex', flexDirection: 'column', gap: 13, minHeight: 0 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 16, fontWeight: 600, letterSpacing: '-.01em' }}>Generate new</span>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={LABEL}>Your résumé</span>
            <Picker value={genResume} options={resumeOpts} placeholder="Select a résumé…" onPick={setGenResume} />
            <span style={{ fontSize: 10.5, color: 'var(--muted)', textWrap: 'pretty' }}>Base for achievements and motivation</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={LABEL}>Target job</span>
            <Picker value={genJob} options={jobOpts} placeholder="Select a saved or applied job…" onPick={setGenJob} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={LABEL}>Voice</span>
            <VoicePicker presets={presets} value={genVoice} onPick={setGenVoice} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={LABEL}>Length</span>
            <LengthPicker value={genLength} onPick={setGenLength} />
          </div>

          <div onClick={generate} title={!genResume || !genJob ? 'Pick a résumé and a job first' : 'Write the letter'}
            style={{ height: 36, borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, lineHeight: 1, fontSize: 13, fontWeight: 500, cursor: (!genResume || !genJob || generating) ? 'default' : 'pointer', opacity: (!genResume || !genJob || generating) ? 0.55 : 1 }}>
            {generating && <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--accent-ink)', borderTopColor: 'transparent', borderRadius: 99 }} />}
            {generating ? 'Generating…' : '✦ Generate cover letter'}
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--muted)', textWrap: 'pretty' }}>
            Takes about 30 seconds — the letter appears in the list when it's done, drafted for your review.
          </span>
          {err && <span style={{ fontSize: 11.5, color: 'var(--bad)', textWrap: 'pretty' }}>{err}</span>}
        </div>

        {/* list */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)' }}>
          <div style={{ flex: '0 0 auto', padding: '13px 30px 9px', display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--line-soft)' }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>All letters</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--edge)' }}>{letters.length + pending.length}</span>
            {query && visible.length !== letters.length &&
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>{visible.length} shown</span>}
            <div style={{ marginLeft: 'auto', flex: '0 1 210px', minWidth: 0, height: 28, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>⌕</span>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search letter or company…"
                style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
            </div>
          </div>

          <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '10px 30px 22px', display: 'flex', flexDirection: 'column', gap: 7, minHeight: 0 }}>
            {generating && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', border: '1px dashed var(--accent)', borderRadius: 10, background: 'var(--change-bg)' }}>
                <span className="v2-spin" style={{ width: 11, height: 11, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                <span style={{ fontSize: 12.5, color: 'var(--accent)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Generating{genJobLabel ? ` — ${genJobLabel}` : ''}{voiceLabel ? ` · ${voiceLabel}` : ''} · {lengthLabel}
                </span>
                <span style={{ marginLeft: 'auto', flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>~30s</span>
              </div>
            )}

            {visible.map((c) => {
              const bits = [c.source_name, presets.find((p) => p.id === c.voice)?.label || c.voice,
                LENGTHS.find(([id]) => id === c.length)?.[1] || c.length].filter(Boolean)
              const sub = [...bits, `edited ${ago(c.updated_at)} ago`].join(' · ')
              return (
                <div key={c.id} onClick={() => navigate(`/v2/cover-letters/${c.id}`)} className="v2-bd"
                  style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--surface)', cursor: 'pointer' }}>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span title={c.name} style={{ fontFamily: 'var(--serif)', fontSize: 15.5, fontWeight: 500, letterSpacing: '-.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</span>
                    <span style={{ fontSize: 11.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</span>
                  </div>
                  {c.stage && (
                    <span title="Stage of the linked application" className={STAGE_CLASS[c.stage] || 'cc-generic'}
                      style={{ flex: '0 0 auto', fontSize: 10, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 8px', borderRadius: 99 }}>{c.stage}</span>
                  )}
                  <span style={{ flex: '0 0 40px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)' }}>{ago(c.updated_at)}</span>
                  <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--edge)' }}>›</span>
                </div>
              )
            })}

            {visible.length === 0 && !generating && (
              <div style={{ padding: '34px 8px', textAlign: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
                {letters.length === 0 ? 'No cover letters yet — generate one on the left.' : 'Nothing matches that search.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
