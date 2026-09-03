import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useToasts, ToastStack } from './Toast'
import api from '../api'
import { Band, Button, Card, Heading, HeaderRow, Helper, Label, Link, Menu, PageTitle, Pill, SearchInput, Spinner, Tag } from './ui'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
import { ago, agoShort } from './time'

export const LENGTHS = [['concise', 'Concise'], ['standard', 'Standard'], ['detailed', 'Detailed']]

// Stage chip on a row mirrors the Applications stage colours.
export const STAGE_CLASS = { applied: 'cc-smartrecruiters', interview: 'cc-workday', offer: 'cc-tier1', rejected: 'cc-generic' }

const ARCH_KEY = 'v2_cl_archive_open'
const CTRL = {
  height: 33, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 8,
  background: 'var(--surface)', display: 'flex', alignItems: 'center', lineHeight: 1,
  justifyContent: 'space-between', fontSize: 12.5, cursor: 'pointer', color: 'var(--text)',
}
// where a popover sits; how it looks is `Menu`'s.
const POPOVER = { position: 'absolute', top: '100%', left: 0, zIndex: 40, marginTop: 4, maxHeight: 300, overflow: 'auto' }

// Design draws these selects as a bordered row with a ▾ — a native <select>
// can't carry the two-line job labels, so this is a small popover instead.
// ui: keep — ui.jsx's Select renders single-line `[value, label]` rows; this one
// carries a second `sub` line per option and claims Escape (RES-15) so the modal
// it may sit in does not close on the same press. Not an input-role scan site.
export function Picker({ value, options, placeholder, onPick, width }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [open])
  // RES-15: Escape closes the popover and claims the event, so the modal this
  // picker may be sitting in doesn't close on the same press. Registered on mount
  // (not on open) so it runs before the modal's own handler.
  const openRef = useRef(false)
  openRef.current = open
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented || !openRef.current) return
      e.preventDefault(); setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  const cur = options.find((o) => o.id === value)
  return (
    <span style={{ position: 'relative', display: 'block' }} onClick={(e) => e.stopPropagation()}>
      <div onClick={() => setOpen((v) => !v)} style={{ ...CTRL, borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
        <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: cur ? 'var(--text)' : 'var(--muted)' }}>
          {cur ? cur.label : placeholder}
        </span>
        {/* ui: keep — 9px ▾ glyph, below the Helper scale (md 11.5 / xs 10.5) */}
        <span style={{ flex: '0 0 auto', fontSize: 9, color: 'var(--muted)', marginLeft: 8 }}>▾</span>
      </div>
      {/* CL-07: the popover physically covers the control below it, so without a
          scrim the next click lands on an option of *this* picker. The scrim sits
          just under the popover: clicks on the popover still work, everything else
          just closes it. */}
      {open && <div onClick={(e) => { e.stopPropagation(); setOpen(false) }} style={{ position: 'fixed', inset: 0, zIndex: 39 }} />}
      {open && (
        <Menu role="listbox" className="v2-scroll" style={{ ...POPOVER, width: width || '100%' }}>
          {options.length === 0 && <div style={{ padding: '7px 9px', fontSize: 12, color: 'var(--muted)' }}>Nothing to pick yet.</div>}
          {/* ui: keep — two-line option (label over `sub`); MenuItem draws a single-line
              row, and this Picker is already a documented keep for the same reason */}
          {options.map((o) => (
            <div key={o.id} className="v2-menuitem" onClick={() => { onPick(o.id); setOpen(false) }}
              style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', minWidth: 0,
                color: o.id === value ? 'var(--accent)' : 'var(--text-2)', fontWeight: o.id === value ? 500 : 400,
                background: o.id === value ? 'var(--accent-soft)' : 'transparent' }}>
              <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.label}</div>
              {o.sub && <Helper style={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.sub}</Helper>}
            </div>
          ))}
        </Menu>
      )}
    </span>
  )
}

// Voice chips + length segments are shared with the editor's Regenerate modal.
export function VoicePicker({ presets, value, onPick }) {
  if (!presets.length) return <Helper>No voice presets — add them in Settings → AI.</Helper>   // CL-13
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {presets.map((v) => {
        const on = v.id === value
        return (
          <Pill key={v.id} size="sm" on={on} onClick={() => onPick(v.id)} title={v.instruction || ''}>{v.label}</Pill>
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
          /* ui: keep — a segmented control, not a card: three equal-flex cells
             that share one border run and swing to accent-soft when picked */
          <div key={id} onClick={() => onPick(id)} className="v2-bdc v2-ctl"
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
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()   // CL-18
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
  const [loadErr, setLoadErr] = useState(null)   // CL-05: failed load ≠ empty account
  const [runMeta, setRunMeta] = useState({})   // run_id -> {label, voice, length}
  const pendingRef = useRef([])
  useEffect(() => { pendingRef.current = pending }, [pending])

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/cover-letters')
      setLetters(data || []); setLoadErr(null)
    } catch (e) {
      console.error(e)
      setLoadErr(e?.response?.status ? `The server answered ${e.response.status}.` : (e.message || 'Network error'))
    }
  }, [])

  useEffect(() => {
    load()
    // merge, don't replace: the ?job=/?resume= effect below prepends a row that
    // isn't in these windows, and this response usually lands last (the 200-job
    // list is the slowest call on the screen) — replacing wiped the deep link.
    const mergeKeep = (rows) => (p) => [...p.filter((x) => !rows.some((r) => r.id === x.id)), ...rows]
    // OPEN-05: converted — the generate panel is the point of this screen, and a
    // disabled button is not an explanation. Same for the job picker and the
    // voice list below.
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(mergeKeep(data || []))).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your résumés — there is nothing to generate from.' }) })
    api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your Persona — it will not be offered as a source.' }) })
    // saved AND applied — v1 fetched only saved, so a ?job= from an applied job
    // landed on an id with no matching option and the field rendered blank
    api.get('/jobs', { params: { status: 'saved,applied', limit: 200 } })   // 200 is the endpoint's cap
      .then(({ data }) => setJobs(mergeKeep(data.jobs || []))).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your saved jobs — the job picker is empty.' }) })
    api.get('/settings').then(({ data }) => {
      let p = data.cover_letter_voice_presets
      if (typeof p === 'string') { try { p = JSON.parse(p) } catch { p = [] } }
      const list = Array.isArray(p) ? p : []
      setPresets(list)
      setGenVoice(data.cover_letter_default_voice || list[0]?.id || '')
    }).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the voice presets — the voice picker is empty.' }) })
  }, [load, pushToast])

  // ?job= / ?resume= deep links (from the Feed, Résumé editor and Applications)
  useEffect(() => {
    const j = searchParams.get('job'); const r = searchParams.get('resume')
    if (!j && !r) return
    if (j) {
      setGenJob(j)
      // make sure the target is pickable even if it's outside the fetched window
      // R2-A-03: converted — the user followed a link *to this job*; if the row
      // can't be fetched the picker silently shows an unmatched id
      api.get(`/jobs/${j}`).then(({ data }) => {
        setJobs((p) => p.some((x) => x.id === data.id) ? p : [data, ...p])
      }).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the linked job — pick it from the list' }) })
    }
    if (r) {
      setGenResume(r)
      // R2-A-03: converted — same for the résumé half of the deep link
      api.get(`/resumes/${r}`).then(({ data }) => {
        setResumes((p) => p.some((x) => x.id === data.id) ? p : [data, ...p])
      }).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the linked résumé — pick it from the list' }) })
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
        const runs = (data || []).filter((r) => r.job_type === 'generate_cover_letter' && /^cl:[^:]+:[^:]+$/.test(r.scope_key || ''))   // CL-20: regenerates (cl:{id}) rewrite in place
        if (dead) return
        const before = pendingRef.current
        const ids = runs.map((r) => r.run_id).join(',')
        if (ids !== before.map((r) => r.run_id).join(',')) setPending(runs)
        const gone = before.filter((b) => !runs.some((r) => r.run_id === b.run_id))
        if (gone.length) {
          load()
          window.dispatchEvent(new CustomEvent('jn:counts-changed'))   // CL-17
          // CL-06: a failed run leaves /monitor/active exactly like a successful
          // one — the row just vanishes. Ask the history what actually happened.
          try {
            const { data: hist } = await api.get('/monitor/history', { params: { job_type: 'generate_cover_letter', limit: 20 } })
            const bad = (hist || []).find((h) => h.status === 'failed' && gone.some((g) => g.run_id === h.id))
            if (bad && !dead) { setErr(`Generation failed${bad.error ? ' — ' + bad.error : ''}`); pushToast({ kind: 'error', msg: `Generation failed${bad.error ? ' — ' + bad.error : ''}` }) }
            else if (!dead) pushToast({ kind: 'success', msg: 'Cover letter ready.' })
          } catch { /* the reloaded list is then the only signal */ }
        }
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
  const countLine = query.trim()
    ? `${visible.length} of ${letters.length} letter${letters.length === 1 ? '' : 's'} match · ${live} live application${live === 1 ? '' : 's'}`   // CL-23
    : `${letters.length} letter${letters.length === 1 ? '' : 's'} · ${live} live application${live === 1 ? '' : 's'}`

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
      pushToast({ kind: 'error', msg: e?.response?.status === 409 ? 'A letter for this résumé and job is already generating.' : `Generation failed${e?.response?.data?.detail ? ' — ' + e.response.data.detail : ''}` })
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
    const sub = [...bits, `edited ${ago(c.updated_at)}`].join(' · ')
    return (
      <Card key={c.id} onClick={() => navigate(`/v2/cover-letters/${c.id}`)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px',
          ...(arc ? { borderColor: 'var(--line-soft)', background: 'var(--recessed)' } : null) }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* the 22px line-height is the row's: it holds the card at an integer
              height, the way the pending row below documents */}
          <Heading strong size={15.5} title={c.name} style={{ lineHeight: '22px', ...(arc ? { color: 'var(--text-2)' } : null), whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</Heading>
          <Helper style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</Helper>
        </div>
        {(c.stage || arc) && (
          <Tag tone="none" title={c.stage ? 'Stage of the linked application' : 'No application yet'}
            className={STAGE_CLASS[c.stage] || 'cc-generic'}>{c.stage || 'Draft'}</Tag>
        )}
        <Helper size="xs" mono style={{ flex: '0 0 40px', textAlign: 'right' }}>{agoShort(c.updated_at)}</Helper>
        <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--edge)' }}>›</span>
      </Card>
    )
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <HeaderRow as="header" variant="screen" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Cover Letters</PageTitle>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          <SearchInput variant="underline" width="280px" value={query} onChange={setQuery}
            placeholder="Search letters, companies… " ariaLabel="Search cover letters" />
        </div>
      </HeaderRow>

      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        {/* generate panel */}
        <div className="v2-scroll" style={{ flex: '0 0 340px', borderRight: '1px solid var(--line)', background: 'var(--bg)', overflow: 'auto', padding: '16px 26px 20px 30px', display: 'flex', flexDirection: 'column', gap: 13, minHeight: 0 }}>
          <Heading strong={600} size={16}>Generate new</Heading>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Label>Your résumé</Label>
            <Picker value={genResume} options={resumeOpts} placeholder="Select a résumé…" onPick={setGenResume} />
            <Helper size="xs" style={{ textWrap: 'pretty' }}>Base for achievements and motivation</Helper>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Label>Target job</Label>
            <Picker value={genJob} options={jobOpts} placeholder="Select a saved or applied job…" onPick={setGenJob} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Voice</Label>
            <VoicePicker presets={presets} value={genVoice} onPick={setGenVoice} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Length</Label>
            <LengthPicker value={genLength} onPick={setGenLength} />
          </div>

          {/* RES-17: --line on --muted when disabled, like every other primary pill
              in the three builders — a dimmed accent still reads as live. */}
          <Button onClick={generate} disabled={!canGenerate}
            title={thisPairRunning ? 'Already writing this one' : (!genResume || !genJob ? 'Pick a résumé and a job first' : 'Write the letter — you can start others while it runs')}>
            {thisPairRunning && <Spinner size={10} color="currentColor" />}
            {thisPairRunning ? 'Generating…' : '✦ Generate cover letter'}
          </Button>
          {err && <span style={{ fontSize: 11.5, color: 'var(--bad)', textWrap: 'pretty' }}>{err}</span>}
        </div>

        {/* list */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--surface)' }}>
          <HeaderRow className="v2-gutter-head" pad="13px 30px 9px" soft align="center" style={{ gap: 9 }}>
            <Label>All letters</Label>
            {/* ui: keep — mono count in --edge ink: the mono-text role, not a muted helper */}
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--edge)' }}>{letters.length + pending.length}</span>
          </HeaderRow>

          <div className="v2-scroll v2-gutter" style={{ flex: 1, overflow: 'auto', padding: '10px 30px 22px', display: 'flex', flexDirection: 'column', gap: 7, minHeight: 0 }}>
            {pending.map((r) => (
              <Band key={r.run_id} interactive={false} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', borderColor: 'var(--accent)', background: 'var(--recessed)' }}>
                <Spinner size={11} />
                {/* integer line-height: at 1.5 this 12.5px label makes the row
                    46.75px tall and every letter row below it lands on a half
                    pixel, which drops their 1px borders on alternating rows */}
                <span style={{ fontSize: 12.5, lineHeight: '20px', color: 'var(--accent)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Generating — {rowLabel(r)}
                </span>
                <Helper style={{ marginLeft: 'auto', flex: '0 0 auto' }}>~30s</Helper>
              </Band>
            ))}

            {active.map((c) => row(c, false))}

            {archived.length > 0 && (
              <Band onClick={() => { if (!query.trim()) setArchOpen((v) => !v) }} title={query.trim() ? 'Archived letters are shown while you search' : undefined}
                style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Archived · {archived.length} letter{archived.length === 1 ? '' : 's'} from rejected applications &amp; skipped jobs
                </span>
                <span className="v2-ctl" style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--accent)', whiteSpace: 'nowrap' }}>
                  {query.trim() ? 'shown while searching' : showArch ? 'hide ⌄' : 'browse ›'}
                </span>
              </Band>
            )}
            {showArch && archived.map((c) => row(c, true))}

            {visible.length === 0 && pending.length === 0 && (loadErr ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '34px 8px' }}>
                <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load your letters</span>
                <Helper style={{ textAlign: 'center' }}>{loadErr}</Helper>
                <Link onClick={() => load()} style={{ paddingTop: 2 }}>Try again</Link>
              </div>
            ) : (
              <div style={{ padding: '34px 8px', textAlign: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
                {letters.length === 0 ? 'No cover letters yet — generate one on the left.' : 'Nothing matches that search.'}
              </div>
            ))}
          </div>
        </div>
      </div>
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}
