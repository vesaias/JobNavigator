import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import './theme.css'

const timeAgo = (s) => {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  const days = Math.floor(h / 24)
  if (days < 21) return `${days}d ago`
  return `${Math.floor(days / 7)}w ago`
}
const scoreColor = (s) => (s >= 70 ? 'var(--good)' : s >= 50 ? 'var(--warn)' : 'var(--bad)')

// company / role label for a copy — from the shelf payload, else parse "Base → Company — Role"
const copyLabel = (c) => {
  let company = c.company, role = c.role
  if (!company && !role) {
    const after = (c.name || '').split('→').slice(1).join('→').trim()
    const [co, ...rest] = after.split('—')
    company = (co || '').trim(); role = rest.join('—').trim()
  }
  return [company, role].filter(Boolean).join(' · ') || c.name
}

export default function V2Resumes() {
  const navigate = useNavigate()
  const [bases, setBases] = useState([])
  const [persona, setPersona] = useState(null)
  const [archived, setArchived] = useState([])
  const [totalCopies, setTotalCopies] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  const [inflight, setInflight] = useState([])   // [{baseId, jobId}] tailors in progress
  const inflightKeys = useRef('')

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/resumes/shelf')
      setBases(data.bases || [])
      setPersona(data.persona || null)
      setArchived(data.archived || [])
      setTotalCopies(data.total_copies || 0)
    } catch (e) { console.error('shelf load failed', e) }
    setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])

  // in-flight tailors: poll /monitor/active; refresh the shelf when the set shrinks
  useEffect(() => {
    const tick = async () => {
      try {
        const { data } = await api.get('/monitor/active')
        const rows = (data || []).filter((r) => r.job_type === 'tailor_resume').map((r) => {
          const [baseId, jobId] = (r.scope_key || '').split(':')
          return { baseId, jobId }
        })
        const key = rows.map((r) => `${r.baseId}:${r.jobId}`).sort().join(',')
        if (key !== inflightKeys.current) {
          const shrank = key.length < inflightKeys.current.length
          inflightKeys.current = key
          setInflight(rows)
          if (shrank) load()   // a tailor finished → new copy exists
        }
      } catch {}
    }
    tick()
    const iv = setInterval(tick, 3000)
    return () => clearInterval(iv)
  }, [load])

  const openResume = (id) => navigate(`/v2/resumes/${id}`)
  const searching = q.trim().length > 0

  // unified search across bases, live copies, and archived copies
  const results = useMemo(() => {
    const t = q.trim().toLowerCase()
    if (!t) return []
    const out = []
    bases.forEach((b) => {
      if (b.name.toLowerCase().includes(t)) out.push({ id: b.id, kind: 'base', name: b.name, note: `${b.copy_count} cop${b.copy_count === 1 ? 'y' : 'ies'}`, score: b.avg_fit })
      ;(b.copies || []).forEach((c) => {
        if (`${copyLabel(c)} ${c.name}`.toLowerCase().includes(t)) out.push({ id: c.id, kind: 'tailored', name: copyLabel(c), score: c.score })
      })
    })
    archived.forEach((c) => {
      if (`${copyLabel(c)} ${c.name}`.toLowerCase().includes(t)) out.push({ id: c.id, kind: 'archived', name: copyLabel(c), note: c.why, muted: true })
    })
    return out
  }, [q, bases, archived])

  const BADGE = {
    base: { bg: 'var(--surface-2)', fg: 'var(--muted)' },
    tailored: { bg: 'var(--accent-soft)', fg: 'var(--accent)' },
    archived: { bg: 'var(--surface-2)', fg: 'var(--faint)' },
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* header */}
      <div style={{ flex: '0 0 auto', padding: '22px 30px 14px', display: 'flex', alignItems: 'flex-end', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 28, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Résumés</h1>
          <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>{bases.length} base{bases.length === 1 ? '' : 's'} · {totalCopies} tailored cop{totalCopies === 1 ? 'y' : 'ies'} live under their jobs{archived.length ? ` · ${archived.length} archived` : ''}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 9 }}>
          <input value={q} onChange={(e) => { setQ(e.target.value); setShowArchived(false) }} placeholder="Search bases, copies, archived…"
            style={{ height: 36, width: 300, padding: '0 2px', border: 'none', borderBottom: '1px solid var(--line)', background: 'transparent', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--text)', outline: 'none' }} />
          <div onClick={() => setAddOpen(true)} style={{ height: 36, padding: '0 17px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>+ New résumé</div>
        </div>
      </div>

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '6px 30px 26px', minHeight: 0, display: 'flex', flexDirection: 'column', gap: searching || showArchived ? 4 : 12 }}>
        {loading ? <div style={{ padding: 50, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
          : searching ? (
            <>
              <span style={{ fontSize: 11, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)', padding: '4px 2px' }}>{results.length} {results.length === 1 ? 'match' : 'matches'} — bases, copies, and archived</span>
              {results.length === 0 ? <div style={{ padding: '20px 14px', border: '1px dashed var(--line)', borderRadius: 9, fontSize: 12.5, color: 'var(--muted)' }}>Nothing matches “{q}” — search covers base names, company names, and job titles.</div>
                : results.map((r, i) => (
                  <div key={`${r.kind}-${r.id}-${i}`} className="v2-act" onClick={() => openResume(r.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '10px 14px', border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface)', cursor: 'pointer' }}>
                    <span style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: BADGE[r.kind].bg, color: BADGE[r.kind].fg }}>{r.kind}</span>
                    <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: r.muted ? 'var(--muted)' : 'var(--text)' }}>{r.name}</span>
                    {r.note && <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>{r.note}</span>}
                    {r.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 11, color: scoreColor(r.score) }}>{r.score}</span>}
                  </div>
                ))}
            </>
          ) : showArchived ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 2px' }}>
                <span onClick={() => setShowArchived(false)} style={{ fontSize: 12, color: 'var(--accent)', cursor: 'pointer' }} className="v2-navlink">‹ Back</span>
                <span style={{ fontSize: 11, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>Archived · {archived.length} from rejected or stale applications</span>
              </div>
              {archived.map((c) => (
                <div key={c.id} className="v2-act" onClick={() => openResume(c.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '10px 14px', border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface)', cursor: 'pointer' }}>
                  <span style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: 'var(--surface-2)', color: 'var(--faint)' }}>archived</span>
                  <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--muted)' }}>{copyLabel(c)}</span>
                  <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>{c.why}</span>
                </div>
              ))}
            </>
          ) : bases.length === 0 ? (
            <div style={{ padding: 50, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No base résumés yet. Create one to start.</div>
          ) : (
            <>
              {persona && (
                <>
                  <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)', padding: '4px 2px 0' }}>Profile</span>
                  <div className="v2-card" onClick={() => navigate('/persona')} title="Open Persona — your full profile" style={{ border: '1px solid var(--line)', borderRadius: 11, background: 'var(--surface)', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 11, cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                      <span style={{ fontFamily: 'var(--serif)', fontSize: 19, fontWeight: 500, letterSpacing: '-.015em' }}>Persona</span>
                      <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{persona.updated_at ? `edited ${timeAgo(persona.updated_at)}` : ''}</span>
                      <span title="Average fit across copies tailored from Persona" style={{ marginLeft: 'auto', fontFamily: 'var(--serif)', fontSize: 17, color: persona.avg_fit == null ? 'var(--faint)' : scoreColor(persona.avg_fit) }}>
                        {persona.avg_fit == null ? <span style={{ fontFamily: 'var(--sans)', fontSize: 11 }}>no recent copies</span> : <>{persona.avg_fit}<span style={{ fontFamily: 'var(--sans)', fontSize: 10, color: 'var(--muted)' }}> avg fit</span></>}
                      </span>
                    </div>
                    {(persona.copies?.length > 0 || inflight.some((f) => f.baseId === 'persona')) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)', marginRight: 3 }}>{persona.copy_count} recent cop{persona.copy_count === 1 ? 'y' : 'ies'}</span>
                        {inflight.filter((f) => f.baseId === 'persona').map((f, k) => (
                          <div key={`pfl${k}`} title="Tailoring in progress — opens when ready" style={{ height: 26, padding: '0 10px', border: '1px solid var(--line)', background: 'var(--bg)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--muted)' }}>
                            <span className="v2-spin" style={{ flex: '0 0 auto', width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /><span>tailoring…</span>
                          </div>
                        ))}
                        {(persona.copies || []).slice(0, 6).map((c) => (
                          <div key={c.id} onClick={(e) => { e.stopPropagation(); openResume(c.id) }} title={c.name} className="v2-chip" style={{ height: 26, padding: '0 10px', border: '1px solid var(--line)', background: 'var(--bg)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer', maxWidth: 250 }}>
                            <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{copyLabel(c)}</span>
                            {c.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10, color: scoreColor(c.score) }}>{c.score}</span>}
                            {c.fresh && <span title="Has tailoring changes you haven't reviewed" style={{ flex: '0 0 auto', width: 6, height: 6, borderRadius: 99, background: 'var(--warn)' }} />}
                          </div>
                        ))}
                        {(persona.copies?.length || 0) > 6 && <span onClick={(e) => { e.stopPropagation(); setQ('persona') }} style={{ fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>+ {persona.copies.length - 6} more ›</span>}
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)', padding: '4px 2px 0' }}>Résumés</span>
                </>
              )}
              {bases.map((b) => {
                const copies = b.copies || []
                const baseInflight = inflight.filter((f) => String(f.baseId) === String(b.id))
                return (
                  <div key={b.id} className="v2-card" onClick={() => openResume(b.id)} style={{ border: '1px solid var(--line)', borderRadius: 11, background: 'var(--surface)', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 11, cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                      <span style={{ fontFamily: 'var(--serif)', fontSize: 19, fontWeight: 500, letterSpacing: '-.015em' }}>{b.name}</span>
                      <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>edited {timeAgo(b.updated_at)}</span>
                      <span title="Average fit across this base's scored copies" style={{ marginLeft: 'auto', fontFamily: 'var(--serif)', fontSize: 17, color: b.avg_fit == null ? 'var(--faint)' : scoreColor(b.avg_fit) }}>
                        {b.avg_fit == null ? <span style={{ fontFamily: 'var(--sans)', fontSize: 11 }}>no recent copies</span> : <>{b.avg_fit}<span style={{ fontFamily: 'var(--sans)', fontSize: 10, color: 'var(--muted)' }}> avg fit</span></>}
                      </span>
                    </div>
                    {(copies.length > 0 || baseInflight.length > 0) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)', marginRight: 3 }}>{b.copy_count} recent cop{b.copy_count === 1 ? 'y' : 'ies'}</span>
                        {baseInflight.map((f, k) => (
                          <div key={`fl${k}`} title="Tailoring in progress — opens when ready" style={{ height: 26, padding: '0 10px', border: '1px solid var(--line)', background: 'var(--bg)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--muted)', maxWidth: 250 }}>
                            <span className="v2-spin" style={{ flex: '0 0 auto', width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                            <span>tailoring…</span>
                          </div>
                        ))}
                        {copies.slice(0, 6).map((c) => (
                          <div key={c.id} onClick={(e) => { e.stopPropagation(); openResume(c.id) }} title={c.name} className="v2-chip"
                            style={{ height: 26, padding: '0 10px', border: '1px solid var(--line)', background: 'var(--bg)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer', maxWidth: 250 }}>
                            <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{copyLabel(c)}</span>
                            {c.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10, color: scoreColor(c.score) }}>{c.score}</span>}
                            {c.fresh && <span title="Has tailoring changes you haven't reviewed" style={{ flex: '0 0 auto', width: 6, height: 6, borderRadius: 99, background: 'var(--warn)' }} />}
                          </div>
                        ))}
                        {copies.length > 6 && <span onClick={(e) => { e.stopPropagation(); setQ(b.name.split(' ')[0]) }} style={{ fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>+ {copies.length - 6} more ›</span>}
                      </div>
                    )}
                  </div>
                )
              })}
              {archived.length > 0 && (
                <div onClick={() => setShowArchived(true)} className="v2-act" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', border: '1px dashed var(--line)', borderRadius: 9, cursor: 'pointer' }}>
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>Archived · {archived.length} cop{archived.length === 1 ? 'y' : 'ies'} from rejected or stale applications</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--accent)' }}>browse ›</span>
                </div>
              )}
            </>
          )}
      </div>

      {addOpen && <AddModal onClose={() => setAddOpen(false)} onCreated={(id) => { setAddOpen(false); if (id) openResume(id); else load() }} />}
    </div>
  )
}

function AddModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const fileRef = useRef(null)

  const EMPTY = { header: { name: '', contact_items: [] }, summary: '', experience: [], skills: {}, education: [], projects: [], publications: [] }

  const createScratch = async () => {
    if (!name.trim() || busy) return
    setBusy(true); setErr('')
    try { const { data } = await api.post('/resumes', { name: name.trim(), is_base: true, json_data: EMPTY }); onCreated(data.id) }
    catch (e) { setErr(e.response?.data?.detail || 'Create failed'); setBusy(false) }
  }
  const importPdf = async (file) => {
    if (!file || busy) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const { data: parsed } = await api.post('/resumes/import-pdf', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const { data } = await api.post('/resumes', { name: name.trim() || file.name.replace(/\.pdf$/i, ''), is_base: true, json_data: parsed.json_data || parsed })
      onCreated(data.id)
    } catch (e) { setErr(e.response?.data?.detail || 'Import failed — is it a text PDF?'); setBusy(false) }
  }

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(20,19,15,.42)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 420, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', padding: 22 }}>
        <div style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em', marginBottom: 4 }}>New base résumé</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>Start from scratch, or import an existing PDF to parse.</div>
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Résumé name (e.g. Backend — Platform v4)"
          onKeyDown={(e) => e.key === 'Enter' && createScratch()}
          style={{ width: '100%', height: 38, padding: '0 12px', border: '1px solid var(--edge)', borderRadius: 8, background: 'var(--surface-2)', fontSize: 13, color: 'var(--text)', outline: 'none', fontFamily: 'var(--sans)', marginBottom: 14 }} />
        {err && <div style={{ fontSize: 12, color: 'var(--bad)', marginBottom: 10 }}>{err}</div>}
        <div style={{ display: 'flex', gap: 9 }}>
          <div onClick={createScratch} style={{ flex: 1, height: 40, borderRadius: 99, background: name.trim() ? 'var(--accent)' : 'var(--edge)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 500, cursor: name.trim() ? 'pointer' : 'default' }}>{busy ? 'Creating…' : 'Create from scratch'}</div>
          <div onClick={() => fileRef.current?.click()} className="v2-act" style={{ flex: 1, height: 40, borderRadius: 99, border: '1px solid var(--edge)', color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, cursor: 'pointer' }}>Import PDF ↑</div>
          <input ref={fileRef} type="file" accept="application/pdf" style={{ display: 'none' }} onChange={(e) => importPdf(e.target.files?.[0])} />
        </div>
        <div onClick={onClose} style={{ marginTop: 14, textAlign: 'center', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>Cancel</div>
      </div>
    </div>
  )
}
