import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

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
const scoreColor = (s) => (s >= 80 ? 'var(--accent)' : s >= 65 ? 'var(--stone)' : 'var(--warn)')

// company / role for a copy — from the shelf payload, else parse "Base → Company — Role"
const copyMeta = (copy) => {
  if (copy.company || copy.role) return { company: copy.company || '', role: copy.role || '' }
  const after = (copy.name || '').split('→').slice(1).join('→').trim()
  const [company, ...rest] = after.split('—')
  return { company: (company || '').trim(), role: rest.join('—').trim() }
}

const PREVIEW_CHIPS = 4

export default function V2Resumes() {
  const navigate = useNavigate()
  const [bases, setBases] = useState([])
  const [totalCopies, setTotalCopies] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [expanded, setExpanded] = useState(() => new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/resumes/shelf')
      setBases(data.bases || [])
      setTotalCopies(data.total_copies || 0)
    } catch (e) { console.error('shelf load failed', e) }
    setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase()
    if (!t) return bases.map((b) => ({ ...b, _forceExpand: false }))
    return bases
      .map((b) => {
        if (b.name.toLowerCase().includes(t)) return { ...b, _forceExpand: false }
        const mc = (b.copies || []).filter((c) => {
          const { company, role } = copyMeta(c)
          return `${company} ${role} ${c.name}`.toLowerCase().includes(t)
        })
        return mc.length ? { ...b, copies: mc, _forceExpand: true } : null
      })
      .filter(Boolean)
  }, [bases, q])

  const openResume = (id) => navigate(`/resumes?resume=${id}`)

  return (
    <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', background: 'var(--bg)', color: 'var(--ink)' }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '30px 40px 60px' }}>
        {/* header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, marginBottom: 22 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 500, letterSpacing: '-.02em' }}>Résumés</h1>
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted)' }}>
              {bases.length} base{bases.length === 1 ? '' : 's'} · {totalCopies} tailored cop{totalCopies === 1 ? 'y' : 'ies'} live under their jobs
            </div>
          </div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search bases, copies…"
            style={{ width: 320, height: 38, padding: '0 14px', borderRadius: 99, border: '1px solid var(--border)', background: 'var(--surface)', fontSize: 13, fontFamily: 'var(--sans)', color: 'var(--ink)', outline: 'none' }} />
          <button onClick={() => navigate('/resumes')} className="v2-pill"
            style={{ height: 38, padding: '0 16px', borderRadius: 99, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>+ New résumé</button>
        </div>

        {loading ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>{q ? 'No résumés match.' : 'No base résumés yet. Create one to start.'}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {filtered.map((b) => {
              const copies = b.copies || []
              const isExp = b._forceExpand || expanded.has(b.id)
              const shown = isExp ? copies : copies.slice(0, PREVIEW_CHIPS)
              const moreN = copies.length - shown.length
              return (
                <div key={b.id} className="v2-card" style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, padding: '15px 18px' }}>
                  {/* base header */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                    <span onClick={() => openResume(b.id)} title="Open résumé"
                      style={{ fontFamily: 'var(--serif)', fontSize: 20, fontWeight: 500, letterSpacing: '-.01em', cursor: 'pointer' }}>{b.name}</span>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                      {b.copy_count} cop{b.copy_count === 1 ? 'y' : 'ies'} · edited {timeAgo(b.updated_at)}
                    </span>
                    <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: 5 }}>
                      {b.avg_fit != null ? (
                        <>
                          <span style={{ fontFamily: 'var(--serif)', fontSize: 22, letterSpacing: '-.02em', color: scoreColor(b.avg_fit) }}>{b.avg_fit}</span>
                          <span style={{ fontSize: 10, color: 'var(--muted)' }}>avg fit</span>
                        </>
                      ) : <span style={{ fontSize: 11, color: 'var(--faint)' }}>no scored copies</span>}
                    </span>
                  </div>

                  {/* copies */}
                  {copies.length > 0 && (
                    <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 9.5, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)', marginRight: 2 }}>Recent copies</span>
                      {shown.map((c) => {
                        const { company, role } = copyMeta(c)
                        return (
                          <div key={c.id} className="v2-chip" onClick={() => openResume(c.id)} title={c.name}
                            style={{ display: 'flex', alignItems: 'center', gap: 7, maxWidth: 300, height: 27, padding: '0 10px', borderRadius: 99, border: '1px solid var(--border)', background: 'var(--surface)', cursor: 'pointer', fontSize: 11.5 }}>
                            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--stone)' }}>
                              {company ? <b style={{ fontWeight: 600 }}>{company}</b> : null}{company && role ? ' · ' : ''}{role}
                            </span>
                            {c.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 11, color: scoreColor(c.score) }}>{c.score}</span>}
                          </div>
                        )
                      })}
                      {moreN > 0 && (
                        <span onClick={() => setExpanded((prev) => { const n = new Set(prev); n.add(b.id); return n })}
                          style={{ fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>+ {moreN} more ›</span>
                      )}
                      {isExp && !b._forceExpand && copies.length > PREVIEW_CHIPS && (
                        <span onClick={() => setExpanded((prev) => { const n = new Set(prev); n.delete(b.id); return n })}
                          style={{ fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer' }}>show less</span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
