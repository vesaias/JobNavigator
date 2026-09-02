import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
const daysSince = (iso) => (iso ? Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)) : 0)
const ago = (iso) => {
  if (!iso) return ''
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 60) return `${Math.max(1, m)}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
// interview slot: "Tue 9 Sep, 14:00" — locale-formatted from the stored UTC instant
const fmtWhen = (iso) => {
  if (!iso) return ''
  const dt = new Date(iso)
  if (isNaN(dt)) return ''
  return dt.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
const fmtSalary = (lo, hi) => {
  const k = (v) => `$${Math.round(v / 1000)}K`
  if (lo && hi && lo !== hi) return `${k(lo)}–${k(hi)}`
  return lo || hi ? k(lo || hi) : ''
}

const srcLabel = (v) => ({
  direct: 'a company scrape', jobright: 'Jobright.ai', levels_fyi: 'Levels.fyi',
  linkedin_personal: 'LinkedIn Personal', linkedin_extension: 'the LinkedIn extension',
  extension: 'the extension', freehire: 'freehire.me',
}[v] || (v ? v.replace(/^jobspy_/, '').replace(/_/g, ' ') : 'the Job Feed'))

const STAGES = [
  { id: 'applied', label: 'Applied', dot: 'var(--stage-applied)', hint: 'Waiting on a first response' },
  { id: 'interview', label: 'Interview', dot: 'var(--warn)', hint: 'In the interview loop' },
  { id: 'offer', label: 'Offer', dot: 'var(--good)', hint: 'Offer received' },
  { id: 'rejected', label: 'Rejected', dot: 'var(--bad)', hint: 'Closed — kept for the Stats funnel' },
]
const STAGE = Object.fromEntries(STAGES.map((s) => [s.id, s]))
const GROUP_LABEL = { applied: 'Applied', interview: 'Interview', offer: 'Offer', rejected: 'Rejected' }
const SORTS = [['recent', 'Recent activity'], ['oldest', 'Waiting longest'], ['company', 'Company name']]
const isStale = (a) => daysSince(a.updated_at) > 7 && ['applied', 'interview'].includes(a.status)

const LABEL = { fontSize: 9.5, lineHeight: '14px', letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }
const FIELD_LABEL = { fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }
const POPOVER = {
  position: 'absolute', top: '100%', zIndex: 40, background: 'var(--surface)',
  border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)',
  padding: 6, display: 'flex', flexDirection: 'column',
}
// Header action pill — same metrics as the Feed's "Open ↗" (collapsed header).
// lineHeight:1 is local to these fixed-height controls: at the inherited 1.5 the
// line box stops centring in the pill and the label rides ~1px high, and under
// `normal` a fallback-font glyph (the ↗) drags it 1px the other way. Because the
// height is fixed, this cannot affect any surrounding layout.
const ACT_BTN = {
  height: 30, padding: '0 14px', borderRadius: 99, border: '1px solid var(--edge)',
  background: 'var(--surface)', display: 'flex', alignItems: 'center', lineHeight: 1,
  fontSize: 13, color: 'var(--text-2)', whiteSpace: 'nowrap',
}
const inputSt = {
  height: 29, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6,
  background: 'var(--surface)', fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--text)', outline: 'none',
}
// FastAPI's `detail` is a plain string for HTTPException; append it when present.
const errSuffix = (e) => (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '')

// ── main ─────────────────────────────────────────────────────────────────────
export default function Applications() {
  const navigate = useNavigate()
  const [apps, setApps] = useState([])
  // hold the screen back until the first fetch lands — otherwise the chrome
  // paints with "0 applications" and an empty list, then everything pops in
  const [loaded, setLoaded] = useState(false)
  const [sel, setSel] = useState(null)
  const [query, setQuery] = useState('')
  const [companies, setCompanies] = useState([])
  const [sortBy, setSortBy] = useState('recent')
  const [openFlt, setOpenFlt] = useState(null)     // null | 'company' | 'sort'
  const [closed, setClosed] = useState({ rejected: true })
  const [menuOpen, setMenuOpen] = useState(false)
  const [intForm, setIntForm] = useState(false)
  const [intWhat, setIntWhat] = useState(''); const [intWhen, setIntWhen] = useState('')
  const [intWhere, setIntWhere] = useState(''); const [intPrep, setIntPrep] = useState('')
  const [prep, setPrep] = useState(null)           // {text} | 'loading'
  const [copied, setCopied] = useState(false)
  const [logOpen, setLogOpen] = useState(false)
  const timers = useRef([])
  const notesTimer = useRef(null)
  useEffect(() => () => { timers.current.forEach(clearTimeout); clearTimeout(notesTimer.current) }, [])
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  const load = useCallback(async (keep) => {
    try {
      const { data } = await api.get('/applications', { params: { limit: 2000 } })
      const list = data.applications || []
      setApps(list)
      setSel((cur) => (keep ?? cur) || (list[0]?.id ?? null))
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not load applications' + errSuffix(e) }) }
    setLoaded(true)
  }, [pushToast])
  useEffect(() => { load() }, [load])

  const closeAll = () => { setOpenFlt(null); setMenuOpen(false) }
  useEffect(() => {
    const onDoc = () => closeAll()
    const onKey = (e) => { if (e.key === 'Escape') { closeAll(); setPrep(null); setLogOpen(false) } }
    document.addEventListener('click', onDoc); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])

  // ── derived ──
  const nInterview = apps.filter((a) => a.status === 'interview').length
  const nOffer = apps.filter((a) => a.status === 'offer').length
  const nStale = apps.filter(isStale).length
  const countLine = `${apps.length} application${apps.length === 1 ? '' : 's'} · ${nInterview} in interview · ${nOffer} offer`
    + (nStale ? ` · ${nStale} waiting >7d` : '')

  const companyOf = (a) => a.company_canonical || a.company || 'Unknown Company'
  // live companies (≥1 non-rejected application) first, then a rule, then the closed ones
  const companyOpts = useMemo(() => {
    const m = new Map()
    apps.forEach((a) => {
      const c = companyOf(a)
      const e = m.get(c) || { n: 0, live: false }
      e.n += 1; if (a.status !== 'rejected') e.live = true
      m.set(c, e)
    })
    const byName = (x, y) => x[0].localeCompare(y[0])
    const all = [...m.entries()]
    return {
      live: all.filter(([, e]) => e.live).sort(byName),
      closed: all.filter(([, e]) => !e.live).sort(byName),
    }
  }, [apps])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    let out = apps.filter((a) => {
      if (companies.length && !companies.includes(companyOf(a))) return false
      if (!q) return true
      return `${a.title || ''} ${companyOf(a)}`.toLowerCase().includes(q)
    })
    const byName = (x, y) => (x.title || '').localeCompare(y.title || '')
    const cmp = {
      recent: (x, y) => daysSince(x.updated_at) - daysSince(y.updated_at) || byName(x, y),
      oldest: (x, y) => daysSince(y.updated_at) - daysSince(x.updated_at) || byName(x, y),
      company: (x, y) => companyOf(x).localeCompare(companyOf(y)) || byName(x, y),
    }[sortBy]
    return [...out].sort(cmp)
  }, [apps, query, companies, sortBy])

  const d = apps.find((a) => a.id === sel) || null

  // ── actions ──
  const patch = async (id, body) => {
    setApps((p) => p.map((a) => (a.id === id ? { ...a, ...body } : a)))   // optimistic
    try { await api.patch(`/applications/${id}`, body); load(id) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not save that change' + errSuffix(e) }); load(id) }
  }
  // autosave: debounce while typing, flush immediately on blur
  const saveNotes = useCallback((id, value, now) => {
    clearTimeout(notesTimer.current)
    const run = () => {
      setApps((p) => p.map((a) => (a.id === id ? { ...a, notes: value } : a)))
      api.patch(`/applications/${id}`, { notes: value })
        .catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not save notes' + errSuffix(e) }) })
    }
    if (now) run(); else notesTimer.current = setTimeout(run, 700)
  }, [pushToast])

  const remove = async (a) => {
    setMenuOpen(false)
    if (!window.confirm(`Delete the application for "${a.title}"?`)) return
    try { await api.delete(`/applications/${a.id}`); setSel(null); load(null); pushToast({ kind: 'success', msg: 'Application deleted' }) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not delete this application' + errSuffix(e) }) }
  }
  const addInterview = async () => {
    if (!d) return
    try {
      await api.post(`/applications/${d.id}/interviews`, {
        // APPS-03: datetime-local is wall-clock in the viewer's zone; send an instant so the server's UTC store round-trips
        what: intWhat.trim() || 'Interview', when_at: intWhen ? new Date(intWhen).toISOString() : null,
        where_text: intWhere.trim() || null, status: 'scheduled', prep: intPrep.trim() || null,
      })
      setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep(''); load(d.id)
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not add the interview' + errSuffix(e) }) }
  }
  const delInterview = async (iv) => {
    try { await api.delete(`/applications/interviews/${iv.id}`); load(d.id) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not remove the interview' + errSuffix(e) }) }
  }
  const toggleInterview = async (iv) => {
    try { await api.patch(`/applications/interviews/${iv.id}`, { status: iv.status === 'done' ? 'scheduled' : 'done' }); load(d.id) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not update the interview' + errSuffix(e) }) }
  }
  const openPrep = async () => {
    if (!d) return
    closeAll(); setPrep('loading'); setCopied(false)
    try { const { data } = await api.get(`/applications/${d.id}/prep`); setPrep({ text: data.text }) }
    catch (e) { setPrep({ text: `Could not build the prep bundle: ${e.message}` }) }
  }
  const copyPrep = async () => {
    try { await navigator.clipboard.writeText(prep?.text || '') } catch { /* clipboard blocked */ }
    setCopied(true); timers.current.push(setTimeout(() => setCopied(false), 1800))
  }

  // history from real status_transitions + the Gmail timestamp
  const history = useMemo(() => {
    if (!d) return []
    const h = (d.status_transitions || []).map((t) => ({
      what: `Moved to ${STAGE[t.to]?.label || t.to}`, at: t.at,
      dot: STAGE[t.to]?.dot || 'var(--line-strong)',
    }))
    if (d.last_email_received) h.push({ what: 'Reply detected in Gmail', at: d.last_email_received, dot: 'var(--line-strong)' })
    if (d.applied_at) h.push({ what: `Applied with ${d.tailored_resume_name || d.cv_version_used || d.best_cv || 'unknown résumé'}`, at: d.applied_at, dot: 'var(--line-strong)' })
    if (d.discovered_at) h.push({ what: `Discovered via ${srcLabel(d.source)}`, at: d.discovered_at, dot: 'var(--line-strong)' })
    return h.sort((a, b) => new Date(b.at) - new Date(a.at))
  }, [d])

  if (!loaded) return <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)' }} />

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* header */}
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px 24px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Applications</h1>
          {/* integer line-height: at the inherited 1.5 this span is 19.5px, which
              lands the whole list pane on a half pixel and every row on x.25 */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div onClick={() => { closeAll(); setLogOpen(true) }} style={{ flex: '0 0 auto', height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>+ Log application</div>
        </div>
      </header>

      {/* toolbar */}
      <div style={{ flex: '0 0 auto', padding: '0 30px 14px 24px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--line)' }}>
        <div style={{ flex: '0 1 210px', minWidth: 0, height: 30, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or company…"
            style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
        </div>

        <span style={{ position: 'relative', flex: '0 0 auto', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
          <div onClick={() => setOpenFlt(openFlt === 'company' ? null : 'company')}
            style={{ height: 30, padding: '0 13px', border: `1px solid ${openFlt === 'company' || companies.length ? 'var(--accent)' : 'var(--edge)'}`, background: openFlt === 'company' || companies.length ? 'var(--accent-soft)' : 'var(--surface)', color: openFlt === 'company' || companies.length ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', lineHeight: 1, gap: 6, fontSize: 12.5, whiteSpace: 'nowrap', cursor: 'pointer' }}>
            Company{companies.length ? ` · ${companies.length}` : ''}<span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>
          </div>
          {openFlt === 'company' && (
            <div className="v2-scroll" style={{ ...POPOVER, left: 0, marginTop: 5, width: 240, gap: 1, maxHeight: 340, overflow: 'auto' }}>
              {['live', 'closed'].map((band) => companyOpts[band].map(([name, e], i) => {
                const on = companies.includes(name)
                const first = band === 'closed' && i === 0 && companyOpts.live.length > 0
                return (
                  <div key={name} className="v2-menuitem" onClick={() => setCompanies((p) => on ? p.filter((x) => x !== name) : [...p, name])}
                    style={{ padding: '6px 8px', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 9, fontSize: 12.5, lineHeight: '18px', color: band === 'closed' ? 'var(--muted)' : 'var(--text-2)', cursor: 'pointer', marginTop: first ? 5 : 0, borderTop: first ? '1px solid var(--line)' : 'none', paddingTop: first ? 10 : 6 }}>
                    <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent)' : 'var(--surface)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>{on ? '✓' : ''}</span>
                    <span title={band === 'closed' ? 'Every application here is rejected' : undefined} style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)' }}>{e.n}</span>
                  </div>
                )
              }))}
            </div>
          )}
        </span>

        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {visible.length !== apps.length && <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{visible.length} of {apps.length} shown</span>}
          <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
            <div onClick={() => setOpenFlt(openFlt === 'sort' ? null : 'sort')} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>
              Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORTS.find((s) => s[0] === sortBy)?.[1]}</span><span style={{ fontSize: 10 }}>▾</span>
            </div>
            {openFlt === 'sort' && (
              <div style={{ ...POPOVER, right: 0, marginTop: 8, width: 190, gap: 1 }}>
                {SORTS.map(([id, label]) => {
                  const on = sortBy === id
                  return (
                    <div key={id} className="v2-menuitem" onClick={() => { setSortBy(id); setOpenFlt(null) }}
                      style={{ padding: '7px 9px', borderRadius: 6, display: 'flex', alignItems: 'center', fontSize: 12.5, color: on ? 'var(--accent)' : 'var(--text-2)', fontWeight: on ? 500 : 400, background: on ? 'var(--accent-soft)' : 'transparent', cursor: 'pointer' }}>
                      {label}{on && <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--accent)' }}>✓</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </span>
        </span>
      </div>

      {/* split body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* list */}
        <div className="v2-scroll" style={{ flex: '0 0 472px', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '6px 14px 14px 22px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {STAGES.map((st) => {
            const rows = visible.filter((a) => a.status === st.id)
            const shut = !!closed[st.id]
            return (
              <React.Fragment key={st.id}>
                <div onClick={() => setClosed((p) => ({ ...p, [st.id]: !p[st.id] }))}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 8px 5px', lineHeight: '16px', cursor: 'pointer' }}>
                  <span style={{ width: 7, height: 7, flex: '0 0 7px', borderRadius: 99, background: st.dot }} />
                  <span style={{ fontSize: 10.5, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>{GROUP_LABEL[st.id]}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--edge)' }}>{rows.length}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted)' }}>{shut ? '›' : '⌄'}</span>
                </div>
                {!shut && rows.map((a) => {
                  const stale = isStale(a)
                  const unknownTitle = !a.title || a.title === 'Unknown Role'
                  return (
                    <div key={a.id} onClick={() => { closeAll(); setSel(a.id) }} className="v2-arow"
                      style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 46px', height: 46, marginBottom: 3, padding: '0 10px', borderRadius: 7, background: sel === a.id ? 'var(--surface-2)' : 'transparent', cursor: 'pointer' }}>
                      {/* lineHeight:normal — the design is authored at the browser default;
                          Tailwind's preflight sets 1.5 on <html>, which would inflate the block */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2, lineHeight: 'normal' }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, minWidth: 0 }}>
                          <span title={a.title || 'Unknown Role'} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: unknownTitle || a.status === 'rejected' ? 'var(--muted)' : 'var(--text)' }}>{a.title || 'Unknown Role'}</span>
                          <span title="Reply detected in Gmail" style={{ flex: '0 0 auto', fontSize: 10, color: (a.last_email_received || a.last_email_snippet) ? 'var(--accent)' : 'transparent' }}>✉</span>
                        </div>
                        <span title={companyOf(a)} style={{ fontSize: 11, color: companyOf(a) === 'Unknown Company' ? 'var(--edge)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{companyOf(a)}</span>
                      </div>
                      <span title={stale ? `No movement for ${daysSince(a.updated_at)} days` : `Last activity ${daysSince(a.updated_at)}d ago`}
                        style={{ flex: '0 0 30px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 10.5, color: stale ? 'var(--warn)' : 'var(--muted)' }}>{daysSince(a.updated_at)}d</span>
                    </div>
                  )
                })}
              </React.Fragment>
            )
          })}
          {visible.length === 0 && (
            <div style={{ padding: '34px 8px', textAlign: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
              {apps.length === 0 ? 'No applications yet — mark a job applied in the Feed, or log one here.' : 'Nothing matches those filters.'}
            </div>
          )}
        </div>

        {/* detail */}
        {d ? <Detail d={d} history={history} menuOpen={menuOpen} setMenuOpen={setMenuOpen} closeAll={closeAll}
          onStage={(s) => patch(d.id, { status: s })} onNotes={(v, now) => saveNotes(d.id, v, now)}
          onDelete={() => remove(d)} navigate={navigate}
          intForm={intForm} setIntForm={setIntForm} intWhat={intWhat} setIntWhat={setIntWhat}
          intWhen={intWhen} setIntWhen={setIntWhen} intWhere={intWhere} setIntWhere={setIntWhere}
          intPrep={intPrep} setIntPrep={setIntPrep}
          addInterview={addInterview} delInterview={delInterview} toggleInterview={toggleInterview} openPrep={openPrep} />
          : <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface)', color: 'var(--muted)', fontSize: 13 }}>Select an application.</div>}
      </div>

      {prep && <PrepModal prep={prep} company={d ? companyOf(d) : ''} copied={copied} onCopy={copyPrep} onClose={() => setPrep(null)} />}
      {logOpen && <LogModal onClose={() => setLogOpen(false)} onSaved={(id) => { setLogOpen(false); load(id) }} pushToast={pushToast} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── detail pane ──────────────────────────────────────────────────────────────
function Detail({ d, history, menuOpen, setMenuOpen, closeAll, onStage, onNotes, onDelete, navigate,
                  intForm, setIntForm, intWhat, setIntWhat, intWhen, setIntWhen,
                  intWhere, setIntWhere, intPrep, setIntPrep,
                  addInterview, delInterview, toggleInterview, openPrep }) {
  const meta = [fmtSalary(d.salary_min, d.salary_max), d.location].filter(Boolean).join(' · ') || 'No posting details captured'
  const cv = d.tailored_resume_name || d.cv_version_used || d.best_cv || 'unknown résumé'
  const ivs = d.interviews || []

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 }}>
      {/* header block */}
      <div style={{ flex: '0 0 auto', padding: '16px 26px 14px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>
              {d.short_id ? `#${d.short_id} · ` : ''}{d.company_canonical || d.company}
            </span>
            <span style={{ fontFamily: 'var(--serif)', fontSize: 23, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '26px', textWrap: 'pretty' }}>
              {d.title || 'Unknown Role'}
              {(d.last_email_received || d.last_email_snippet) &&
                <span title="Reply detected in Gmail" style={{ marginLeft: 8, fontSize: 13, color: 'var(--accent)', verticalAlign: 'middle' }}>✉</span>}
            </span>
            <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>
              {meta} · applied with <span onClick={() => d.tailored_resume_id && navigate(`/v2/resumes/${d.tailored_resume_id}`)}
                title={d.tailored_resume_id ? 'Open the tailored résumé' : 'No tailored résumé for this job'}
                style={{ color: 'var(--accent)', fontWeight: 500, cursor: d.tailored_resume_id ? 'pointer' : 'default' }}>{cv}{d.tailored_resume_id ? ' ↗' : ''}</span>
            </span>
          </div>
          <div style={{ flex: '0 0 auto', display: 'flex', gap: 4, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
            {d.has_cached_page && <a href={`/api/jobs/${d.job_id}/cached-page`} target="_blank" rel="noopener noreferrer" className="v2-bdc" title="Snapshot of the posting from application day"
              style={{ ...ACT_BTN, textDecoration: 'none' }}>Cached</a>}
            {d.url && <a href={d.url} target="_blank" rel="noopener noreferrer" className="v2-bdc" title="Open the live posting"
              style={{ ...ACT_BTN, gap: 4, textDecoration: 'none' }}>Live ↗</a>}
            <div onClick={() => setMenuOpen((v) => !v)} className="v2-bd" title="More actions"
              style={{ ...ACT_BTN, width: 30, padding: 0, justifyContent: 'center', border: `1px solid ${menuOpen ? 'var(--accent)' : 'var(--edge)'}`, background: menuOpen ? 'var(--accent-soft)' : 'var(--surface)', cursor: 'pointer' }}>⋯</div>
            {menuOpen && (
              <div style={{ ...POPOVER, right: 0, marginTop: 4, width: 226, padding: 5, textAlign: 'left' }}>
                {[['☰', 'View job in feed', () => navigate(`/v2/feed?job=${d.job_id}`)],
                  ...(d.has_cover_letter ? [['✎', 'Open cover letter', () => navigate(`/v2/cover-letters?job=${d.job_id}`)]] : [])].map(([g, label, act]) => (
                  <div key={label} onClick={() => { setMenuOpen(false); act() }} className="v2-menuitem"
                    style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>
                    <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>{g}</span>{label}
                  </div>
                ))}
                <div onClick={onDelete} className="v2-hover-bad" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--bad)', cursor: 'pointer', marginTop: 3, borderTop: '1px solid var(--line-soft)' }}>
                  <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11 }}>✕</span>Delete application
                </div>
              </div>
            )}
          </div>
        </div>

        {/* stage stepper */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {STAGES.map((s) => {
            const on = d.status === s.id
            const rej = s.id === 'rejected'
            return (
              <div key={s.id} onClick={() => onStage(s.id)} title={s.hint} className="v2-bd"
                style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, height: 34, borderRadius: 8, fontSize: 12.5, cursor: 'pointer', fontWeight: on ? 600 : 400,
                  border: `1px solid ${on ? (rej ? 'var(--bad)' : 'var(--accent)') : 'var(--line)'}`,
                  background: on ? (rej ? 'var(--bad-soft)' : 'var(--accent-soft)') : 'var(--surface)',
                  color: on ? (rej ? 'var(--bad)' : 'var(--accent)') : 'var(--text-2)' }}>
                <span style={{ width: 7, height: 7, borderRadius: 99, background: s.dot }} />{s.label}
              </div>
            )
          })}
        </div>
      </div>

      {/* body */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '18px 26px', display: 'flex', gap: 24, minHeight: 0 }}>
        <div style={{ flex: 1.2, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 15 }}>

          {(d.last_email_received || d.last_email_snippet) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={LABEL}>Last email · Gmail detection</span>
              <div style={{ padding: '10px 12px', borderLeft: '2px solid var(--accent)', background: 'var(--bg)', borderRadius: '0 8px 8px 0', fontSize: 12.5, fontStyle: 'italic', lineHeight: '19px', color: 'var(--text-2)', textWrap: 'pretty' }}>{d.last_email_snippet ? `“${d.last_email_snippet}”` : 'A reply was detected, but no snippet was stored.'}</div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={LABEL}>Interviews · {ivs.length}</span>
              <div onClick={openPrep} className="v2-bdc"
                title="Builds one pasteable block — the role, my résumé, the posting and what to ask for — for the AI of your choice"
                style={{ marginLeft: 'auto', height: 25, padding: '0 10px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                <span style={{ fontSize: 11 }}>⧉</span>Generate prep handover for AI
              </div>
            </div>
            {ivs.map((iv) => (
              <div key={iv.id} style={{ border: '1px solid var(--line)', borderRadius: 9, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 3, background: 'var(--bg)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{iv.what}</span>
                  <span onClick={() => toggleInterview(iv)} title="Toggle scheduled / done" style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, cursor: 'pointer', background: iv.status === 'scheduled' ? 'var(--accent-soft)' : 'var(--surface-2)', color: iv.status === 'scheduled' ? 'var(--good)' : 'var(--text-2)' }}>{iv.status}</span>
                  <span onClick={() => delInterview(iv)} title="Remove this interview" className="v2-hover-bad" style={{ fontSize: 11, color: 'var(--muted)', cursor: 'pointer', padding: 2, borderRadius: 4 }}>✕</span>
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)' }}>
                  {[fmtWhen(iv.when_at), iv.where_text].filter(Boolean).join(' · ') || 'Unscheduled'}
                </span>
                {iv.prep && <span style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty' }}>{iv.prep}</span>}
              </div>
            ))}
            {intForm ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, border: '1px solid var(--accent)', borderRadius: 9, padding: '10px 12px', background: 'var(--surface)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={FIELD_LABEL}>What</span>
                  <input value={intWhat} onChange={(e) => setIntWhat(e.target.value)} placeholder="e.g. System design round" style={inputSt} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <span style={FIELD_LABEL}>When</span>
                    <input type="datetime-local" value={intWhen} onChange={(e) => setIntWhen(e.target.value)} style={{ ...inputSt, minWidth: 0 }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <span style={FIELD_LABEL}>Where</span>
                    <input value={intWhere} onChange={(e) => setIntWhere(e.target.value)} placeholder="Zoom · Onsite — London" style={{ ...inputSt, minWidth: 0 }} />
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={FIELD_LABEL}>Prep note · optional</span>
                  <input value={intPrep} onChange={(e) => setIntPrep(e.target.value)} placeholder="Who I'm meeting, what to revise…" style={inputSt} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 7 }}>
                  <div onClick={() => { setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep('') }} className="v2-bdc" style={{ height: 27, padding: '0 12px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
                  <div onClick={addInterview} style={{ height: 27, padding: '0 13px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: 500, cursor: 'pointer' }}>Add interview</div>
                </div>
              </div>
            ) : (
              <div onClick={() => setIntForm(true)} className="v2-bdc" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, height: 34, border: '1px dashed var(--line-strong)', borderRadius: 9, fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>+ Add interview</div>
            )}
          </div>


          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={LABEL}>Notes · autosaves</span>
            <textarea key={d.id} defaultValue={d.notes || ''} onChange={(e) => onNotes(e.target.value)}
              onBlur={(e) => onNotes(e.target.value, true)} placeholder="Notes…"
              style={{ minHeight: 64, padding: '10px 12px', border: '1px solid var(--line)', borderRadius: 8, fontSize: 13, lineHeight: '20px', color: 'var(--text-2)', background: 'var(--bg)', fontFamily: 'var(--sans)', outline: 'none', resize: 'vertical' }} />
          </div>
        </div>

        {/* history rail */}
        <div style={{ flex: '0 0 250px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={LABEL}>History</span>
          {history.map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: h.dot, marginTop: 4 }} />
                {i < history.length - 1 && <span style={{ width: 1, flex: 1, background: 'var(--line)' }} />}
              </div>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1, paddingBottom: 12 }}>
                <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--text)' }}>{h.what}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)' }}>{ago(h.at)}</span>
              </div>
            </div>
          ))}
          {history.length === 0 && <span style={{ fontSize: 12, lineHeight: '18px', color: 'var(--muted)' }}>No history recorded yet.</span>}
        </div>
      </div>
    </div>
  )
}

// ── prep modal ───────────────────────────────────────────────────────────────
function PrepModal({ prep, company, copied, onCopy, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 640, maxHeight: 640, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Prep handover — {company}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>paste into the AI of your choice</span>
          <div onClick={onClose} className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '14px 22px', background: 'var(--bg)' }}>
          <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: 11, lineHeight: '18px', color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {prep === 'loading' ? 'Building the bundle…' : prep.text}
          </pre>
        </div>
        <div style={{ padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Edit the closing ask in Settings → AI</span>
          <div onClick={onClose} style={{ marginLeft: 'auto', height: 31, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Close</div>
          <div onClick={onCopy} style={{ height: 31, padding: '0 15px', borderRadius: 99, background: copied ? 'var(--good)' : 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>
            <span style={{ fontSize: 11 }}>⧉</span>{copied ? 'Copied ✓' : 'Copy to clipboard'}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── log-application modal ────────────────────────────────────────────────────
function LogModal({ onClose, onSaved, pushToast }) {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [resumes, setResumes] = useState([])
  const [cv, setCv] = useState('')
  const [stage, setStage] = useState('applied')
  const [when, setWhen] = useState(() => new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [reading, setReading] = useState(false)

  useEffect(() => { api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch(() => {}) }, [])

  // paste a URL → read title + company off the posting
  const readUrl = async (u) => {
    if (!u.trim().startsWith('http')) return
    setReading(true)
    try {
      const { data } = await api.post('/applications/extract', { url: u.trim() })
      if (data.title && !title) setTitle(data.title)
      if (data.company && !company) setCompany(data.company)
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not read job details from that URL' + errSuffix(e) }) }
    setReading(false)
  }

  const save = async () => {
    if (!title.trim() || !company.trim() || !url.trim()) { pushToast({ kind: 'error', msg: 'URL, title and company are all required' }); return }
    setBusy(true)
    try {
      const { data } = await api.post('/applications', {
        url: url.trim(), title: title.trim(), company: company.trim(),
        cv_version_used: cv || null, notes: notes.trim() || null,
        status: stage, applied_at: when ? new Date(when).toISOString() : null,
      })
      onSaved(data.id)
    } catch (e) {
      const existing = e.response?.status === 409 ? e.response?.data?.detail?.application_id : null
      if (existing) { pushToast({ kind: 'progress', msg: 'Already logged — opened the existing application.' }); onSaved(existing); return }   // APPS-04
      pushToast({ kind: 'error', msg: 'Could not save this application' + errSuffix(e) }); setBusy(false)
    }
  }

  const box = { height: 33, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 8, background: 'var(--surface)', color: 'var(--text)', fontSize: 12.5, outline: 'none', fontFamily: 'var(--sans)', width: '100%' }
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 520, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Log application</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)', textWrap: 'pretty' }}>For applications made outside the app — jobs from the feed log themselves when you mark them applied.</span>
        </div>
        <div className="v2-scroll" style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 470, overflow: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={FIELD_LABEL}>Posting URL{reading ? ' · reading…' : ''}</span>
            <input value={url} onChange={(e) => setUrl(e.target.value)} onBlur={(e) => readUrl(e.target.value)}
              placeholder="Paste the job URL — title and company are read from it"
              style={{ ...box, fontFamily: 'var(--mono)', fontSize: 11 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
              <span style={FIELD_LABEL}>Title</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Senior Backend Engineer" style={box} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
              <span style={FIELD_LABEL}>Company</span>
              <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme" style={box} />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={FIELD_LABEL}>Applied with</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {resumes.map((r) => {
                const on = cv === r.name
                return <div key={r.id} onClick={() => setCv(on ? '' : r.name)} className="v2-bd" style={{ height: 27, padding: '0 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, whiteSpace: 'nowrap', cursor: 'pointer' }}>{r.name}</div>
              })}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
            <span style={FIELD_LABEL}>Stage</span>
            <div style={{ display: 'flex', gap: 5 }}>
              {['applied', 'interview', 'offer'].map((id) => {
                const on = stage === id
                return <div key={id} onClick={() => setStage(id)} className="v2-bd" style={{ flex: 1, height: 33, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: on ? 600 : 400, cursor: 'pointer' }}>{STAGE[id].label}</div>
              })}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
            <span style={FIELD_LABEL}>Applied on</span>
            <input type="date" value={when} onChange={(e) => setWhen(e.target.value)} style={box} />
          </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={FIELD_LABEL}>Notes</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional — referral, recruiter contact…"
              style={{ ...box, height: 'auto', minHeight: 52, padding: '9px 10px', lineHeight: '19px', resize: 'vertical' }} />
          </div>
        </div>
        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>The posting is cached on save</span>
          <div onClick={onClose} style={{ marginLeft: 'auto', height: 33, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
          <div onClick={busy ? undefined : save} style={{ height: 33, padding: '0 17px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1 }}>{busy ? 'Saving…' : 'Save application'}</div>
        </div>
      </div>
    </div>
  )
}
