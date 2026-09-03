import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import './theme.css'
import { useToasts, ToastStack } from './Toast'
import { useFlashToast } from './hooks'
import { EMPTY } from './ResumeSections'
import { Band, Button, Card, Chip, Heading, HeaderRow, Helper, Input, Label, Link, ModalPanel, NavLink, PageTitle, Pill, SearchInput, ShowMore, Spinner } from './ui'

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

// RES-19: the archived band and a broad search both render every matching row —
// 296 rows in 1.56 s on this account. Page them client-side, 100 at a time, with
// the shared `ShowMore` pager from ./ui (the same one the Stats logs use).
const PAGE = 100

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

// RES2-03: a chip can only show the company and a number, so the design puts the
// rest in its tooltip (Resumes Shelf.dc.html:775-778): base, job, fit and its
// delta against the base's average, and whether tailoring changes are unreviewed.
// Parts the shelf payload doesn't carry are simply left out.
const chipTitle = (c, baseName, avgFit) => {
  const d = c.score != null && avgFit != null ? c.score - avgFit : null
  return [
    baseName,
    copyLabel(c),
    c.score != null ? `fit ${c.score}${d != null ? ` (${d >= 0 ? '+' : ''}${d} vs ${baseName} avg)` : ''}` : null,
    c.fresh ? 'changes unreviewed' : null,
  ].filter(Boolean).join(' · ')
}
// layout half of the chip-row label; the type is `Label`'s (ui.jsx)
const CHIP_LABEL = { flex: '0 0 auto', marginRight: 3 }

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
  const [loadErr, setLoadErr] = useState(false)   // RES-07: a failed load is not an empty account
  const [inflight, setInflight] = useState([])   // [{baseId, jobId}] tailors in progress
  const [resLimit, setResLimit] = useState(PAGE)      // RES-19
  const [archLimit, setArchLimit] = useState(PAGE)    // RES-19
  // RES-13: "+ N more" used to run a first-word search, which pulled in other
  // bases' copies and the archived rows the shelf had deliberately folded away.
  // It expands the card in place instead. Keyed by base id ('persona' for Persona).
  const [expanded, setExpanded] = useState(() => new Set())
  const toggleExpand = (key) => setExpanded((p) => { const n = new Set(p); n.has(key) ? n.delete(key) : n.add(key); return n })
  const inflightKeys = useRef('')
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()
  useFlashToast(pushToast)   // RES-21: the editor's "no longer exists" lands here

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/resumes/shelf')
      setBases(data.bases || [])
      setPersona(data.persona || null)
      setArchived(data.archived || [])
      setTotalCopies(data.total_copies || 0)
      setLoadErr(false)
    } catch (e) { console.error('shelf load failed', e); setLoadErr(true) }
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
  useEffect(() => { setResLimit(PAGE) }, [q])
  useEffect(() => { setArchLimit(PAGE) }, [showArchived])

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
      <HeaderRow pad="22px 30px 16px 24px" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <PageTitle>Résumés</PageTitle>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)' }}>{bases.length} base{bases.length === 1 ? '' : 's'} · {totalCopies} tailored cop{totalCopies === 1 ? 'y' : 'ies'} live under their jobs{archived.length ? ` · ${archived.length} archived` : ''}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <SearchInput variant="underline" width="300px" value={q} onChange={(v) => { setQ(v); setShowArchived(false) }}
            placeholder="Search bases, copies, archived…" ariaLabel="Search résumés" />
          <Button onClick={() => setAddOpen(true)}>+ New résumé</Button>
        </div>
      </HeaderRow>

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '6px 30px 26px 24px', minHeight: 0, display: 'flex', flexDirection: 'column', gap: searching || showArchived ? 4 : 12 }}>
        {loading ? <div style={{ padding: 50, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
          /* RES-07: a 500/401 used to render as "No base résumés yet", inviting the
             user to create a résumé they already have. */
          : loadErr ? (
            <Band interactive={false} style={{ padding: '20px 14px', borderColor: 'var(--bad)', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12.5, color: 'var(--muted)' }}>
              <span style={{ flex: 1, minWidth: 0 }}>Couldn’t load your résumés — the shelf request failed.</span>
              <Pill size="sm" onClick={() => { setLoading(true); load() }}>Try again</Pill>
            </Band>
          )
          : searching ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 2px' }}>
                <NavLink onClick={() => setQ('')}>‹ Back</NavLink>
                <Label size="lg">{results.length} {results.length === 1 ? 'match' : 'matches'} — bases, copies, and archived</Label>
              </div>
              {results.length === 0 ? <Band interactive={false} style={{ padding: '20px 14px', fontSize: 12.5, color: 'var(--muted)' }}>Nothing matches “{q}” — search covers base names, company names, and job titles.</Band>
                : results.slice(0, resLimit).map((r, i) => (
                  <Card key={`${r.kind}-${r.id}-${i}`} onClick={() => openResume(r.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, lineHeight: '20px' }}>
                    {/* ui: keep — uppercase kind badge (bg + r99): the Tag role, not Label */}
                    <span style={{ flex: '0 0 auto', fontSize: 9.5, lineHeight: '16px', letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', background: BADGE[r.kind].bg, color: BADGE[r.kind].fg }}>{r.kind}</span>
                    <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: r.muted ? 'var(--muted)' : 'var(--text)' }}>{r.name}</span>
                    {r.note && <Helper style={{ flex: '0 0 auto' }}>{r.note}</Helper>}
                    {/* ui: keep — mono score numeral in scoreColor(): the mono-text role, not a helper */}
                    {r.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 11, color: scoreColor(r.score) }}>{r.score}</span>}
                  </Card>
                ))}
              {results.length > resLimit && <ShowMore n={Math.min(PAGE, results.length - resLimit)} onClick={() => setResLimit((n) => n + PAGE)} />}
            </>
          ) : showArchived ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 2px' }}>
                <NavLink onClick={() => setShowArchived(false)}>‹ Back</NavLink>
                <Label size="lg">Archived · {archived.length} from rejected or stale applications</Label>
              </div>
              {archived.length === 0 && <Band interactive={false} style={{ padding: '20px 14px', fontSize: 12.5, color: 'var(--muted)' }}>Nothing archived yet — copies land here when their application is rejected or goes stale.</Band>}
              {archived.slice(0, archLimit).map((c) => (
                <Card key={c.id} onClick={() => openResume(c.id)} style={{ display: 'flex', alignItems: 'center', gap: 11, lineHeight: '20px' }}>
                  {/* ui: keep — uppercase "archived" badge (bg + r99): the Tag role, not Label */}
                  <span style={{ flex: '0 0 auto', fontSize: 9.5, lineHeight: '16px', letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', background: 'var(--surface-2)', color: 'var(--faint)' }}>archived</span>
                  <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--muted)' }}>{copyLabel(c)}</span>
                  <Helper style={{ flex: '0 0 auto' }}>{c.why}</Helper>
                </Card>
              ))}
              {archived.length > archLimit && <ShowMore n={Math.min(PAGE, archived.length - archLimit)} onClick={() => setArchLimit((n) => n + PAGE)} />}
            </>
          ) : bases.length === 0 ? (
            <div style={{ padding: 50, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No base résumés yet. Create one to start.</div>
          ) : (
            <>
              {persona && (
                <>
                  <Label style={{ padding: '4px 2px 0' }}>Profile</Label>
                  <Card onClick={() => navigate('/v2/persona')} title="Open Persona — your full profile" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 11 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, lineHeight: '28px' }}>
                      <Heading strong size={19}>Persona</Heading>
                      <Helper>{['your full profile', persona.copy_count > 0 ? `${persona.copy_count} recent cop${persona.copy_count === 1 ? 'y' : 'ies'}` : (persona.archived_count > 0 ? 'no recent copies' : 'no copies'), persona.updated_at ? `edited ${timeAgo(persona.updated_at)}` : null].filter(Boolean).join(' · ')}</Helper>
                      {persona.avg_fit != null && (
                        /* ui: keep — serif 17 score numeral in scoreColor(), plus its nested sans-10 unit:
                           Helper has no sans reset for a child of a serif parent */
                        <span title="Average fit across copies tailored from Persona (archived included)" style={{ marginLeft: 'auto', fontFamily: 'var(--serif)', fontSize: 17, color: scoreColor(persona.avg_fit) }}>
                          {persona.avg_fit}<span style={{ fontFamily: 'var(--sans)', fontSize: 10, color: 'var(--muted)' }}> avg fit</span>
                        </span>
                      )}
                    </div>
                    {(persona.copies?.length > 0 || inflight.some((f) => f.baseId === 'persona')) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        {(persona.copies?.length || 0) > 0 && <Label style={CHIP_LABEL}>Recent copies</Label>}
                        {inflight.filter((f) => f.baseId === 'persona').map((f, k) => (
                          <Chip key={`pfl${k}`} title="Tailoring in progress — opens when ready" style={{ color: 'var(--muted)' }}>
                            <Spinner /><span>tailoring…</span>
                          </Chip>
                        ))}
                        {(expanded.has('persona') ? (persona.copies || []) : (persona.copies || []).slice(0, 6)).map((c) => (
                          <Chip key={c.id} onClick={(e) => { e.stopPropagation(); openResume(c.id) }} title={chipTitle(c, 'Persona', persona.avg_fit)} style={{ maxWidth: 250 }}>
                            <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{copyLabel(c)}</span>
                            {/* ui: keep — mono score numeral in scoreColor(): the mono-text role, not a helper */}
                            {c.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10, color: scoreColor(c.score) }}>{c.score}</span>}
                            {/* ui: keep — 6px "unreviewed" dot, not a control */}
                            {c.fresh && <span title="Has tailoring changes you haven't reviewed" style={{ flex: '0 0 auto', width: 6, height: 6, borderRadius: 'var(--radius-control)', background: 'var(--warn)' }} />}
                          </Chip>
                        ))}
                        {(persona.copies?.length || 0) > 6 && (
                          <Link onClick={(e) => { e.stopPropagation(); toggleExpand('persona') }}>
                            {expanded.has('persona') ? 'show fewer ‹' : `+ ${persona.copies.length - 6} more ›`}
                          </Link>
                        )}
                      </div>
                    )}
                  </Card>
                  <Label style={{ padding: '4px 2px 0' }}>Résumés</Label>
                </>
              )}
              {bases.map((b) => {
                const copies = b.copies || []
                const baseInflight = inflight.filter((f) => String(f.baseId) === String(b.id))
                return (
                  <Card key={b.id} onClick={() => openResume(b.id)} title={`Open ${b.name} — the base résumé`} style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 11 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, lineHeight: '28px' }}>
                      <Heading strong size={19} title={b.name} style={{ flex: '0 1 auto', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.name}</Heading>
                      <Helper>{[b.copy_count > 0 ? `${b.copy_count} recent cop${b.copy_count === 1 ? 'y' : 'ies'}` : (b.archived_count > 0 ? 'no recent copies' : 'no copies'), `edited ${timeAgo(b.updated_at)}`].join(' · ')}</Helper>
                      {b.avg_fit != null && (
                        /* ui: keep — serif 17 score numeral in scoreColor(), plus its nested sans-10 unit:
                           Helper has no sans reset for a child of a serif parent */
                        <span title="Average fit across this base's scored copies (archived included)" style={{ marginLeft: 'auto', fontFamily: 'var(--serif)', fontSize: 17, color: scoreColor(b.avg_fit) }}>
                          {b.avg_fit}<span style={{ fontFamily: 'var(--sans)', fontSize: 10, color: 'var(--muted)' }}> avg fit</span>
                        </span>
                      )}
                    </div>
                    {(copies.length > 0 || baseInflight.length > 0) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        {copies.length > 0 && <Label style={CHIP_LABEL}>Recent copies</Label>}
                        {baseInflight.map((f, k) => (
                          <Chip key={`fl${k}`} title="Tailoring in progress — opens when ready" style={{ color: 'var(--muted)', maxWidth: 250 }}>
                            <Spinner />
                            <span>tailoring…</span>
                          </Chip>
                        ))}
                        {(expanded.has(b.id) ? copies : copies.slice(0, 6)).map((c) => (
                          <Chip key={c.id} onClick={(e) => { e.stopPropagation(); openResume(c.id) }} title={chipTitle(c, b.name, b.avg_fit)}
                            style={{ maxWidth: 250 }}>
                            <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{copyLabel(c)}</span>
                            {/* ui: keep — mono score numeral in scoreColor(): the mono-text role, not a helper */}
                            {c.score != null && <span style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10, color: scoreColor(c.score) }}>{c.score}</span>}
                            {/* ui: keep — 6px "unreviewed" dot, not a control */}
                            {c.fresh && <span title="Has tailoring changes you haven't reviewed" style={{ flex: '0 0 auto', width: 6, height: 6, borderRadius: 'var(--radius-control)', background: 'var(--warn)' }} />}
                          </Chip>
                        ))}
                        {copies.length > 6 && (
                          <Link onClick={(e) => { e.stopPropagation(); toggleExpand(b.id) }}>
                            {expanded.has(b.id) ? 'show fewer ‹' : `+ ${copies.length - 6} more ›`}
                          </Link>
                        )}
                      </div>
                    )}
                  </Card>
                )
              })}
              {archived.length > 0 && (
                <Band onClick={() => setShowArchived(true)} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>Archived · {archived.length} cop{archived.length === 1 ? 'y' : 'ies'} from rejected or stale applications</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--accent)' }}>browse ›</span>
                </Band>
              )}
            </>
          )}
      </div>

      {addOpen && <AddModal onClose={() => setAddOpen(false)} onCreated={(id) => { setAddOpen(false); openResume(id) }} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

function AddModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  // RES-18: one shared flag put the import's busy label on the *other* button.
  // '' | 'create' | 'import' — the label follows the action that is actually running.
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const fileRef = useRef(null)

  const createScratch = async () => {
    if (!name.trim() || busy) return
    setBusy('create'); setErr('')
    try { const { data } = await api.post('/resumes', { name: name.trim(), is_base: true, json_data: EMPTY }); onCreated(data.id) }
    catch (e) { setErr(e.response?.data?.detail || 'Create failed'); setBusy('') }
  }
  const importPdf = async (file) => {
    if (!file || busy) return
    setBusy('import'); setErr('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const { data: parsed } = await api.post('/resumes/import-pdf', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      // /resumes/import-pdf already persists the parsed résumé (routes_resumes.py:1152)
      // — reuse that row (renaming it when a name was typed) instead of creating a duplicate.
      if (parsed?.id) {
        const wanted = name.trim()
        if (wanted && wanted !== parsed.name) { try { await api.patch(`/resumes/${parsed.id}`, { name: wanted }) } catch { /* keep the imported name */ } }
        onCreated(parsed.id); return
      }
      const { data } = await api.post('/resumes', { name: name.trim() || file.name.replace(/\.pdf$/i, ''), is_base: true, json_data: parsed.json_data || parsed })
      onCreated(data.id)
    } catch (e) { setErr(e.response?.data?.detail || 'Import failed — is it a text PDF?'); setBusy('') }
  }

  const canCreate = !!name.trim() && !busy

  return (
    // zIndex 60 kept: this modal opens from the Résumés shelf, under the app's
    // ConfirmDialog (70) and the toast stack (80).
    <ModalPanel width={420} onClose={onClose} zIndex={60} style={{ padding: 22 }}>
        <Heading size={19} style={{ display: 'block', marginBottom: 4 }}>New base résumé</Heading>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14 }}>Start from scratch, or import an existing PDF to parse.</div>
        <Input autoFocus value={name} onChange={setName} placeholder="Résumé name (e.g. Backend — Platform v4)"
          ariaLabel="Résumé name" onKeyDown={(e) => e.key === 'Enter' && createScratch()}
          style={{ marginBottom: 14 }} />
        {err && <div style={{ fontSize: 12, color: 'var(--bad)', marginBottom: 10 }}>{err}</div>}
        <div style={{ display: 'flex', gap: 9 }}>
          {/* RES-17: a disabled primary pill is --line on --muted (the design's
              disabled Tailor button); --edge as a fill reads as a second live button. */}
          <Button onClick={createScratch} disabled={!canCreate} style={{ flex: 1 }}>{busy === 'create' ? 'Creating…' : 'Create from scratch'}</Button>
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={!!busy} style={{ flex: 1 }}>{busy === 'import' ? 'Parsing…' : 'Import PDF ↑'}</Button>
          {/* RES-28: clear the input after every pick, or choosing the same PDF
              twice in one modal session fires no change event at all. */}
          {/* ui: keep — hidden <input type="file">, not a rendered field */}
          <input ref={fileRef} type="file" accept="application/pdf" style={{ display: 'none' }}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; importPdf(f) }} />
        </div>
        <div onClick={onClose} style={{ marginTop: 14, textAlign: 'center', fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>Cancel</div>
    </ModalPanel>
  )
}
