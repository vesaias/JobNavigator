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

const ARCH_KEY = 'v2_cl_archive_open'
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
      <div onClick={() => setOpen((v) => !v)} style={{ ...CTRL, borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
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
          <div key={v.id} onClick={() => onPick(v.id)} title={v.instruction || ''}
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
          <div key={id} onClick={() => onPick(id)}
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
  const [archOpen, setArchOpen] = useState(() => { try { return localStorage.getItem(ARCH_KEY) === '1' } catch { return false } })
  // While searching, show archived matches too — otherwise a query that only
  // hits archived letters looks like it found nothing. Doesn't touch the
  // remembered preference.
  const showArch = archOpen || query.trim().length > 0
  useEffect(() => { try { localStorage.setItem(ARCH_KEY, archOpen ? '1' : '0') } catch {} }, [archOpen])
  const [err, setErr] = useState('')
  const [runMeta, setRunMeta] = useState({})   // run_id -> {label, voice, length}
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

  // Active = still in play. That covers a live application, and also a draft
  // whose job is still new/saved — you haven't applied yet, so the letter is
  // work in progress, not history. Only rejected applications and letters for
  // jobs you skipped (or that are gone) sink into the archive.
  const LIVE_JOB = ['new', 'saved', 'applied']
  const isActive = (c) => (c.stage ? c.stage !== 'rejected' : LIVE_JOB.includes(c.job_status))
  const active = useMemo(() => visible.filter(isActive), [visible])
  const archived = useMemo(() => visible.filter((c) => !isActive(c)), [visible])

  const live = letters.filter((c) => c.stage && c.stage !== 'rejected').length
  const countLine = `${letters.length} letter${letters.length === 1 ? '' : 's'} · ${live} live application${live === 1 ? '' : 's'}`

  const genJobLabel = jobOpts.find((o) => o.id === genJob)?.label || ''
  const voiceLabel = presets.find((p) => p.id === genVoice)?.label || genVoice
  const lengthLabel = LENGTHS.find(([id]) => id === genLength)?.[1] || genLength
  // The backend keys duplicates on cl:{resume}:{job}, so only this exact pair is
  // barred while it runs — other pairs generate alongside it.
  const thisPairRunning = pending.some((r) => r.scope_key === `cl:${genResume}:${genJob}`)
  const canGenerate = genResume && genJob && !thisPairRunning

  const generate = async () => {
    if (!canGenerate) return
    setErr('')
    const label = genJobLabel, v = voiceLabel, l = lengthLabel
    try {
      const { data } = await api.post('/cover-letters/generate', {
        resume_id: genResume, job_id: genJob, voice: genVoice, length: genLength,
      })
      setRunMeta((m) => ({ ...m, [data.run_id]: { label, voice: v, length: l } }))
      setPending((p) => [...p, { run_id: data.run_id, job_type: 'generate_cover_letter',
                                 scope_key: `cl:${genResume}:${genJob}`, target_job_id: genJob }])
      // clear just the job — the next letter is nearly always a different role,
      // and it stops a second click hitting the same-pair guard
      setGenJob('')
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Generation failed')
    }
  }

  // label a pending row from what we recorded, else from its target job
  const rowLabel = (r) => {
    const m = runMeta[r.run_id]
    if (m) return [m.label, m.voice, m.length].filter(Boolean).join(' · ')
    const j = jobs.find((x) => x.id === r.target_job_id)
    return j ? (j.company ? `${j.company} — ${j.title}` : j.title) : 'a cover letter'
  }

  // One row, dimmed with a neutral chip when it sits in the Not-active group
  const row = (c, arc) => {
    const bits = [c.source_name, presets.find((p) => p.id === c.voice)?.label || c.voice,
      LENGTHS.find(([id]) => id === c.length)?.[1] || c.length].filter(Boolean)
    const sub = [...bits, `edited ${ago(c.updated_at)} ago`].join(' · ')
    return (
      <div key={c.id} onClick={() => navigate(`/v2/cover-letters/${c.id}`)} className="v2-bd"
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px', borderRadius: 10, cursor: 'pointer',
          border: `1px solid ${arc ? 'var(--line-soft)' : 'var(--line)'}`, background: arc ? 'var(--recessed)' : 'var(--surface)' }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span title={c.name} style={{ fontFamily: 'var(--serif)', fontSize: 15.5, fontWeight: 500, letterSpacing: '-.01em', lineHeight: '22px', color: arc ? 'var(--text-2)' : 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</span>
          <span style={{ fontSize: 11.5, lineHeight: '16px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</span>
        </div>
        {(c.stage || arc) && (
          <span title={c.stage ? 'Stage of the linked application' : 'No application yet'} className={STAGE_CLASS[c.stage] || 'cc-generic'}
            style={{ flex: '0 0 auto', fontSize: 10, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 8px', borderRadius: 99 }}>{c.stage || 'Draft'}</span>
        )}
        <span style={{ flex: '0 0 40px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)' }}>{ago(c.updated_at)}</span>
        <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--edge)' }}>›</span>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Cover Letters</h1>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search letters, companies… "
            style={{ height: 36, width: 280, padding: '0 13px', border: 'none', borderBottom: '1px solid var(--line-strong)', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--text)' }} />
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

          <div onClick={generate} title={thisPairRunning ? 'Already writing this one' : (!genResume || !genJob ? 'Pick a résumé and a job first' : 'Write the letter — you can start others while it runs')}
            style={{ height: 36, borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, lineHeight: 1, fontSize: 13, fontWeight: 500, cursor: canGenerate ? 'pointer' : 'default', opacity: canGenerate ? 1 : 0.55 }}>
            {thisPairRunning && <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--accent-ink)', borderTopColor: 'transparent', borderRadius: 99 }} />}
            {thisPairRunning ? 'Generating…' : '✦ Generate cover letter'}
          </div>
          {err && <span style={{ fontSize: 11.5, color: 'var(--bad)', textWrap: 'pretty' }}>{err}</span>}
        </div>

        {/* list */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)' }}>
          <div className="v2-gutter-head" style={{ flex: '0 0 auto', padding: '13px 30px 9px', display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--line-soft)' }}>
            <span style={{ fontSize: 10, lineHeight: '16px', letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>All letters</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--edge)' }}>{letters.length + pending.length}</span>
          </div>

          <div className="v2-scroll v2-gutter" style={{ flex: 1, overflow: 'auto', padding: '10px 30px 22px', display: 'flex', flexDirection: 'column', gap: 7, minHeight: 0 }}>
            {pending.map((r) => (
              <div key={r.run_id} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', border: '1px dashed var(--accent)', borderRadius: 10, background: 'var(--recessed)' }}>
                <span className="v2-spin" style={{ width: 11, height: 11, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                <span style={{ fontSize: 12.5, color: 'var(--accent)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Generating — {rowLabel(r)}
                </span>
                <span style={{ marginLeft: 'auto', flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>~30s</span>
              </div>
            ))}

            {active.map((c) => row(c, false))}

            {archived.length > 0 && (
              <div onClick={() => setArchOpen((v) => !v)} className="v2-archband"
                style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', marginTop: 6, border: '1px dashed var(--line)', borderRadius: 9, cursor: 'pointer' }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Archived · {archived.length} letter{archived.length === 1 ? '' : 's'} from rejected applications &amp; skipped jobs
                </span>
                <span className="v2-ctl" style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--accent)', whiteSpace: 'nowrap' }}>
                  {showArch ? 'hide ⌄' : 'browse ›'}
                </span>
              </div>
            )}
            {showArch && archived.map((c) => row(c, true))}

            {visible.length === 0 && pending.length === 0 && (
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
