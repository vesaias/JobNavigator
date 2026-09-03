import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
import ConfirmDialog from './ConfirmDialog'
import { useEscape, useSnapTop } from './hooks'
import { Button, Card, DashedAdd, Dot, Heading, Helper, IconButton, Input, Label, Link, Menu, MenuItem, PageTitle, Pill, Row, SectionHead, Textarea } from './ui'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
const ts = (iso) => (iso ? new Date(iso).getTime() : 0)
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
  direct: 'a company scrape', manual: 'the Log application form', jobright: 'Jobright.ai', levels_fyi: 'Levels.fyi',
  linkedin_personal: 'LinkedIn Personal', linkedin_extension: 'the LinkedIn extension',
  extension: 'the extension', freehire: 'freehire.me',
}[v] || (v ? v.replace(/^jobspy_/, '').replace(/_/g, ' ') : 'the Job Feed'))

// R3-U-01: the dots read the shared --stage-* tokens (theme.css) rather than the
// generic --warn/--good/--bad status hues, so a stage is the same colour here, in
// the Stats funnel and on the Sankey nodes of the Flow view. The values are
// unchanged — --stage-interview/-offer/-rejected were seeded from --warn/--good/
// --bad; what moved is which screens are guaranteed to track them.
const STAGES = [
  { id: 'applied', label: 'Applied', dot: 'var(--stage-applied)', hint: 'Waiting on a first response' },
  { id: 'interview', label: 'Interview', dot: 'var(--stage-interview)', hint: 'In the interview loop' },
  { id: 'offer', label: 'Offer', dot: 'var(--stage-offer)', hint: 'Offer received' },
  { id: 'rejected', label: 'Rejected', dot: 'var(--stage-rejected)', hint: 'Closed — kept for the Stats funnel' },
]
const STAGE = Object.fromEntries(STAGES.map((s) => [s.id, s]))
// APPS-22: legacy rows (ghosted / withdrawn) have no stage of their own — they are closed, so they list under Rejected
const groupOf = (status) => (STAGE[status] ? status : 'rejected')
const SORTS = [['recent', 'Recent activity'], ['oldest', 'Waiting longest'], ['company', 'Company name']]
const isStale = (a) => daysSince(a.updated_at) > 7 && ['applied', 'interview'].includes(a.status)

// where a popover sits; how it looks is `Menu`'s.
const POPOVER = { position: 'absolute', top: '100%', zIndex: 40 }
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
// FastAPI's `detail` is a plain string for HTTPException; append it when present.
const errSuffix = (e) => (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '')

// ── main ─────────────────────────────────────────────────────────────────────
export default function Applications() {
  const navigate = useNavigate()
  const [apps, setApps] = useState([])
  // hold the screen back until the first fetch lands — otherwise the chrome
  // paints with "0 applications" and an empty list, then everything pops in
  const [loaded, setLoaded] = useState(false)
  // APPS-02: a failed fetch must not read as "you have no applications"
  const [total, setTotal] = useState(null)
  const [loadErr, setLoadErr] = useState(null)
  const [sel, setSel] = useState(null)
  const [query, setQuery] = useState('')
  const [companies, setCompanies] = useState([])
  const [sortBy, setSortBy] = useState('recent')
  const [openFlt, setOpenFlt] = useState(null)     // null | 'company' | 'sort'
  const [closed, setClosed] = useState({ rejected: true })
  const [menuOpen, setMenuOpen] = useState(false)
  const [intForm, setIntForm] = useState(false)
  const [intWhat, setIntWhat] = useState(''); const [intWhen, setIntWhen] = useState('')
  const [intBusy, setIntBusy] = useState(false)   // APPS-11: one POST at a time
  const [intWhere, setIntWhere] = useState(''); const [intPrep, setIntPrep] = useState('')
  // R3-A-06: an interview row could only be deleted and retyped. A reschedule is
  // the most common change there is, and the PATCH the status chip already uses
  // takes every field — so the row reopens into the same four-field form.
  const [editIv, setEditIv] = useState(null)      // interview id being edited
  const [ivDraft, setIvDraft] = useState({ what: '', when: '', where: '', prep: '' })
  const [prep, setPrep] = useState(null)           // {text} | 'loading'
  const [copied, setCopied] = useState(false)
  const [logOpen, setLogOpen] = useState(false)
  const timers = useRef([])
  const notesTimer = useRef(null)
  useEffect(() => () => { timers.current.forEach(clearTimeout); clearTimeout(notesTimer.current) }, [])
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()
  const [confirm, setConfirm] = useState(null)   // R2-A-01 / R2-H-08: the shared destructive-confirm dialog

  const load = useCallback(async (keep) => {
    try {
      const { data } = await api.get('/applications', { params: { limit: 2000 } })
      setTotal(typeof data?.total === 'number' ? data.total : null)   // APPS-22: the header counts what the server has, not what fits in one page
      const list = data.applications || []
      setApps(list); setLoadErr(null)
      setSel((cur) => (keep ?? cur) || (list[0]?.id ?? null))
    } catch (e) {
      console.error(e)
      setLoadErr(e?.response?.status ? `The server answered ${e.response.status}.${errSuffix(e)}` : (e.message || 'Network error'))
      pushToast({ kind: 'error', msg: 'Could not load applications' + errSuffix(e) })
    }
    setLoaded(true)
  }, [pushToast])
  useEffect(() => { load() }, [load])
  // APPS-06: the interview draft belongs to the application it was opened on —
  // carrying it to the next row posted it against the wrong application
  useEffect(() => { setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep(''); setEditIv(null) }, [sel])

  const closeAll = () => { setOpenFlt(null); setMenuOpen(false) }
  const logDirty = useRef(false)   // APPS-22: typed fields survive a stray Escape
  // R2-A-01: the styled dialog, not the browser's. Every handler it touches is a
  // setter or a ref, so the once-registered Escape effect below keeps working.
  const dropLog = () => { logDirty.current = false; setLogOpen(false) }
  const closeLog = () => {
    if (!logDirty.current) { dropLog(); return }
    setConfirm({ title: 'Discard this application?', body: 'Everything typed will be lost.', label: 'Discard', danger: true, onConfirm: () => { setConfirm(null); dropLog() } })
  }
  useEffect(() => {
    const onDoc = () => closeAll()
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])
  // OPEN-08: was this screen's own `document` keydown listener, the last one of
  // its kind. Same behaviour — one Escape closes the filter menus, the prep
  // modal, the interview edit (R3-A-06) and the Log modal (whose dirty-discard
  // confirm still fires) — but through the shared hook, which claims the event
  // so nothing behind it also acts on the same keypress.
  //
  // Ordering: this listener is registered at mount, i.e. *before* a
  // ConfirmDialog that opens later, so it would otherwise fire first and swallow
  // the Escape meant for the dialog. Gating it on `!confirm` hands the key to the
  // dialog's own useEscape while one is open — the same guard Settings' model
  // catalog uses for its dropdown.
  useEscape(() => { closeAll(); setPrep(null); setEditIv(null); closeLog() }, !confirm)

  // ── derived ──
  const nInterview = apps.filter((a) => a.status === 'interview').length
  const nOffer = apps.filter((a) => a.status === 'offer').length
  const nStale = apps.filter(isStale).length
  const shown = total ?? apps.length
  const countLine = `${shown} application${shown === 1 ? '' : 's'} · ${nInterview} in interview · ${nOffer} offer${nOffer === 1 ? '' : 's'}${total > apps.length ? ` · showing the first ${apps.length}` : ''}`
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
      recent: (x, y) => ts(y.updated_at) - ts(x.updated_at) || byName(x, y),   // APPS-22: whole-day buckets tied every row touched today
      oldest: (x, y) => ts(x.updated_at) - ts(y.updated_at) || byName(x, y),
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
        .then(() => load(id))   // APPS-22: the row's age and the header follow the server's updated_at
        .catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not save notes' + errSuffix(e) }) })
    }
    if (now) run(); else notesTimer.current = setTimeout(run, 700)
  }, [pushToast, load])

  const remove = (a) => {
    setMenuOpen(false)
    // R2-H-08: the styled dialog — deleting an application is the most
    // destructive action on this screen and looked the least considered.
    setConfirm({
      title: `Delete the application for “${a.title}”?`,
      body: 'The job goes back to Saved in the feed. This cannot be undone.',
      label: 'Delete', danger: true,
      onConfirm: async () => {
        setConfirm(null)
        try { await api.delete(`/applications/${a.id}`); setSel(null); load(null); pushToast({ kind: 'success', msg: 'Application deleted' }); window.dispatchEvent(new CustomEvent('jn:counts-changed')) }
        catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not delete this application' + errSuffix(e) }) }
      },
    })
  }
  const canAddInterview = !intBusy && (!!intWhat.trim() || !!intWhen)   // APPS-12: a blank form adds nothing
  const addInterview = async () => {
    if (!d || !canAddInterview) return
    setIntBusy(true)
    try {
      await api.post(`/applications/${d.id}/interviews`, {
        // APPS-03: datetime-local is wall-clock in the viewer's zone; send an instant so the server's UTC store round-trips
        what: intWhat.trim() || 'Interview', when_at: intWhen ? new Date(intWhen).toISOString() : null,
        where_text: intWhere.trim() || null, status: 'scheduled', prep: intPrep.trim() || null,
      })
      setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep(''); load(d.id)
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not add the interview' + errSuffix(e) }) }
    finally { setIntBusy(false) }
  }
  const delInterview = async (iv) => {
    try {
      await api.delete(`/applications/interviews/${iv.id}`); load(d.id)
      // APPS-13: no confirm — an undo toast re-creates the interview from the row we still hold
      pushToast({ kind: 'undo', msg: `Removed “${iv.what || 'Interview'}”`, action: 'Undo', onAction: async () => {
        try { await api.post(`/applications/${d.id}/interviews`, { what: iv.what, when_at: iv.when_at, where_text: iv.where_text, status: iv.status || 'scheduled', prep: iv.prep }); load(d.id) }
        catch (e) { pushToast({ kind: 'error', msg: 'Could not restore the interview' + errSuffix(e) }) }
      } })
    }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not remove the interview' + errSuffix(e) }) }
  }
  // R3-A-06: ISO instant → the wall-clock string <input type="datetime-local">
  // wants, in the viewer's own zone — the mirror of what addInterview sends.
  const toLocalInput = (iso) => {
    if (!iso) return ''
    const dt = new Date(iso)
    if (Number.isNaN(dt.getTime())) return ''
    const p = (n) => String(n).padStart(2, '0')
    return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}T${p(dt.getHours())}:${p(dt.getMinutes())}`
  }
  const openIvEdit = (iv) => {
    setIntForm(false)
    setEditIv(iv.id)
    setIvDraft({ what: iv.what || '', when: toLocalInput(iv.when_at), where: iv.where_text || '', prep: iv.prep || '' })
  }
  const saveInterview = async () => {
    if (!d || !editIv || intBusy) return
    setIntBusy(true)
    try {
      await api.patch(`/applications/interviews/${editIv}`, {
        what: ivDraft.what.trim() || 'Interview',
        when_at: ivDraft.when ? new Date(ivDraft.when).toISOString() : null,
        where_text: ivDraft.where.trim() || null,
        prep: ivDraft.prep.trim() || null,
      })
      setEditIv(null); load(d.id)
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not save the interview' + errSuffix(e) }) }
    finally { setIntBusy(false) }
  }
  const toggleInterview = async (iv) => {
    try { await api.patch(`/applications/interviews/${iv.id}`, { status: iv.status === 'done' ? 'scheduled' : 'done' }); load(d.id) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not update the interview' + errSuffix(e) }) }
  }
  const openPrep = async () => {
    if (!d) return
    closeAll(); setPrep('loading'); setCopied(false)
    try { const { data } = await api.get(`/applications/${d.id}/prep`); setPrep({ text: data.text }) }
    catch (e) {
      console.error(e)
      setPrep({ text: `Could not build the prep bundle: ${e.message}${errSuffix(e)}`, failed: true })
      pushToast({ kind: 'error', msg: 'Could not build the prep bundle' + errSuffix(e) })
    }
  }
  // APPS-05: "Copied ✓" only after the write actually resolved; nothing to copy
  // while the bundle is still loading or after it failed
  const copyPrep = async () => {
    if (prep === 'loading' || prep?.failed) return
    try {
      await navigator.clipboard.writeText(prep?.text || '')
      setCopied(true); timers.current.push(setTimeout(() => setCopied(false), 1800))
    } catch (e) {
      console.error(e)
      pushToast({ kind: 'error', msg: 'Could not copy — select the text and copy it manually' })
    }
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
          <PageTitle>Applications</PageTitle>
          {/* integer line-height: at the inherited 1.5 this span is 19.5px, which
              lands the whole list pane on a half pixel and every row on x.25 */}
          {/* ui: keep — the count line is 13/20px, off the 11.5 helper step, and its
              integer line-height is what keeps the pane on whole pixels */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button onClick={() => { closeAll(); setLogOpen(true) }}>+ Log application</Button>
        </div>
      </header>

      {/* toolbar */}
      <div style={{ flex: '0 0 auto', padding: '0 30px 14px 24px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--line)' }}>
        {/* ui: keep — search field wrapper (Input role), not a pill; h32 tracks
            ui.jsx's boxed SearchInput so the two read as one control */}
        <div className="v2-fieldwrap" style={{ flex: '0 1 210px', minWidth: 0, height: 32, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7 }}>
          {/* ui: keep — the search field's own ⌕ glyph, on the control's icon scale
              (like the ▾ carets), not a helper sub-line */}
          <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or company…"
            style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
        </div>

        <span style={{ position: 'relative', flex: '0 0 auto', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
          <Pill on={openFlt === 'company' || !!companies.length} ariaExpanded={openFlt === 'company'} ariaHaspopup="menu"
            onClick={() => setOpenFlt(openFlt === 'company' ? null : 'company')}>
            Company{companies.length ? ` · ${companies.length}` : ''}<span style={{ fontSize: 10, opacity: 0.6 }}>▾</span>
          </Pill>
          {openFlt === 'company' && (
            <Menu ariaLabel="Filter by company" className="v2-scroll" style={{ ...POPOVER, left: 0, marginTop: 5, width: 240, maxHeight: 340, overflow: 'auto' }}>
              {['live', 'closed'].map((band) => companyOpts[band].map(([name, e], i) => {
                const on = companies.includes(name)
                const first = band === 'closed' && i === 0 && companyOpts.live.length > 0
                return (
                  <MenuItem key={name} ellipsis hint={e.n} hintMono divider={first}
                    title={band === 'closed' ? 'Every application here is rejected' : undefined}
                    onClick={() => setCompanies((p) => on ? p.filter((x) => x !== name) : [...p, name])}
                    style={{ ...(band === 'closed' ? { color: 'var(--muted)' } : null), ...(first ? { marginTop: 5, paddingTop: 10 } : null) }}
                    icon={/* ui: keep — checkbox indicator, not a card; it rides in MenuItem's icon gutter */
                      <span style={{ width: 14, height: 14, flex: '0 0 14px', borderRadius: 4, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent)' : 'var(--surface)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9 }}>{on ? '✓' : ''}</span>}>
                    {name}
                  </MenuItem>
                )
              }))}
            </Menu>
          )}
        </span>

        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {visible.length !== apps.length && <Helper style={{ whiteSpace: 'nowrap' }}>{visible.length} of {apps.length} shown</Helper>}
          <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
            {/* ui: keep — a menu disclosure trigger (muted 12.5 + value + caret), not a
                link: it opens the Sort menu and carries the trigger's own hover */}
            <div onClick={() => setOpenFlt(openFlt === 'sort' ? null : 'sort')} className="v2-hover-accent-text" style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>
              Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORTS.find((s) => s[0] === sortBy)?.[1]}</span><span style={{ fontSize: 10 }}>▾</span>
            </div>
            {openFlt === 'sort' && (
              <Menu ariaLabel="Sort applications" style={{ ...POPOVER, right: 0, marginTop: 8, width: 190 }}>
                {SORTS.map(([id, label]) => {
                  const on = sortBy === id
                  return (
                    <MenuItem key={id} selected={on} hint={on ? '✓' : null}
                      onClick={() => { setSortBy(id); setOpenFlt(null) }}>{label}</MenuItem>
                  )
                })}
              </Menu>
            )}
          </span>
        </span>
      </div>

      {/* split body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* list */}
        <div className="v2-scroll" style={{ flex: '0 0 472px', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '6px 14px 14px 22px', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {STAGES.map((st) => {
            const rows = visible.filter((a) => groupOf(a.status) === st.id)
            const shut = !!closed[st.id]
            return (
              <React.Fragment key={st.id}>
                {/* every collapsible header in v2 washes to --surface-2 on hover
                    (theme.css .v2-hover-accent) — the stage bands were the last
                    ones with no hover at all */}
                <SectionHead boxed caret="pin" open={!shut} onToggle={() => setClosed((p) => ({ ...p, [st.id]: !p[st.id] }))}
                  style={{ gap: 8, padding: '12px 8px 5px', lineHeight: '16px' }}>
                  <Dot style={{ background: st.dot }} />
                  <Label>{st.label}</Label>
                  {/* ui: keep — the band's row count is the mono-id ink (--edge), a
                      `mono-text` site, not a helper */}
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--edge)' }}>{rows.length}</span>
                </SectionHead>
                {!shut && rows.map((a) => {
                  const stale = isStale(a)
                  const unknownTitle = !a.title || a.title === 'Unknown Role'
                  // APPS-20: selected and hovered were the same fill, so the selection
                  // vanished under the pointer. The 3px accent bar carries the
                  // selection; the 10→7px left pad keeps the text on the same axis.
                  return (
                    <Row key={a.id} selected={sel === a.id} onClick={() => { closeAll(); setSel(a.id) }} className="v2-arow"
                      style={{ gap: 8, flex: '0 0 46px', marginBottom: 3 }}>
                      {/* lineHeight:normal — the design is authored at the browser default;
                          Tailwind's preflight sets 1.5 on <html>, which would inflate the block */}
                      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2, lineHeight: 'normal' }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, minWidth: 0 }}>
                          <span title={a.title || 'Unknown Role'} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: unknownTitle || a.status === 'rejected' ? 'var(--muted)' : 'var(--text)' }}>{a.title || 'Unknown Role'}</span>
                          <span title="Reply detected in Gmail" style={{ flex: '0 0 auto', fontSize: 10, color: (a.last_email_received || a.last_email_snippet) ? 'var(--accent)' : 'transparent' }}>✉</span>
                        </div>
                        <Helper title={companyOf(a)} style={{ color: companyOf(a) === 'Unknown Company' ? 'var(--edge)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{companyOf(a)}</Helper>
                      </div>
                      <Helper size="xs" mono title={stale ? `No movement for ${daysSince(a.updated_at)} days` : `Last activity ${daysSince(a.updated_at)}d ago`}
                        style={{ flex: '0 0 30px', textAlign: 'right', color: stale ? 'var(--warn)' : 'var(--muted)' }}>{daysSince(a.updated_at)}d</Helper>
                    </Row>
                  )
                })}
              </React.Fragment>
            )
          })}
          {visible.length === 0 && (loadErr ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '34px 8px' }}>
              {/* ui: keep — the empty-state's 13px --bad headline, off the helper step */}
              <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load your applications</span>
              <Helper style={{ textAlign: 'center' }}>{loadErr}</Helper>
              <Link onClick={() => load()} style={{ paddingTop: 2 }}>Try again</Link>
            </div>
          ) : (
            <div style={{ padding: '34px 8px', textAlign: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
              {apps.length === 0 ? 'No applications yet — mark a job applied in the Feed, or log one here.' : 'Nothing matches those filters.'}
            </div>
          ))}
        </div>

        {/* detail */}
        {d ? <Detail d={d} history={history} menuOpen={menuOpen} setMenuOpen={setMenuOpen}
          onStage={(s) => patch(d.id, { status: s })} onNotes={(v, now) => saveNotes(d.id, v, now)}
          onDelete={() => remove(d)} navigate={navigate}
          intForm={intForm} setIntForm={setIntForm} intWhat={intWhat} setIntWhat={setIntWhat}
          intWhen={intWhen} setIntWhen={setIntWhen} intWhere={intWhere} setIntWhere={setIntWhere}
          intPrep={intPrep} setIntPrep={setIntPrep} intBusy={intBusy}
          editIv={editIv} setEditIv={setEditIv} ivDraft={ivDraft} setIvDraft={setIvDraft}
          openIvEdit={openIvEdit} saveInterview={saveInterview}
          addInterview={addInterview} canAddInterview={canAddInterview} delInterview={delInterview} toggleInterview={toggleInterview} openPrep={openPrep} />
          : <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface)', color: 'var(--muted)', fontSize: 13 }}>Select an application.</div>}
      </div>

      {prep && <PrepModal prep={prep} company={d ? companyOf(d) : ''} copied={copied} onCopy={copyPrep} onClose={() => setPrep(null)} />}
      {logOpen && <LogModal onClose={closeLog} onDirty={(v) => { logDirty.current = v }} onSaved={(id) => { setLogOpen(false); load(id); setTimeout(() => load(id), 5000); window.dispatchEvent(new CustomEvent('jn:counts-changed')) }} pushToast={pushToast} />}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── detail pane ──────────────────────────────────────────────────────────────
function Detail({ d, history, menuOpen, setMenuOpen, onStage, onNotes, onDelete, navigate,
                  intForm, setIntForm, intWhat, setIntWhat, intWhen, setIntWhen,
                  intWhere, setIntWhere, intPrep, setIntPrep, intBusy,
                  // R3-A-06: the inline interview editor's state lives in the parent
                  // (the Escape handler there clears it) — Detail is a separate closure,
                  // so every one of these has to arrive as a prop, like canAddInterview.
                  editIv, setEditIv, ivDraft, setIvDraft, openIvEdit, saveInterview,
                  addInterview, canAddInterview, delInterview, toggleInterview, openPrep }) {
  const meta = [fmtSalary(d.salary_min, d.salary_max), d.location].filter(Boolean).join(' · ') || 'No posting details captured'
  const cv = d.tailored_resume_name || d.cv_version_used || d.best_cv || 'unknown résumé'
  const ivs = d.interviews || []

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 }}>
      {/* header block */}
      <div style={{ flex: '0 0 auto', padding: '16px 26px 14px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Label>
              {d.short_id ? `#${d.short_id} · ` : ''}{d.company_canonical || d.company}
            </Label>
            {/* ui: keep — serif 23/26px: the detail title's own step, between
                Heading's 22 and the 30px page title */}
            <span style={{ fontFamily: 'var(--serif)', fontSize: 23, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '26px', textWrap: 'pretty' }}>
              {d.title || 'Unknown Role'}
              {(d.last_email_received || d.last_email_snippet) &&
                <span title="Reply detected in Gmail" style={{ marginLeft: 8, fontSize: 13, color: 'var(--accent)', verticalAlign: 'middle' }}>✉</span>}
            </span>
            {/* ui: keep — a 12.5/18px sentence, and the résumé link inside it inherits
                that run; Link's 11.5/500/17px would break the line */}
            <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>
              {meta} · applied with <span onClick={() => d.tailored_resume_id && navigate(`/v2/resumes/${d.tailored_resume_id}`)}
                title={d.tailored_resume_id ? 'Open the tailored résumé' : 'No tailored résumé for this job'}
                style={{ color: d.tailored_resume_id ? 'var(--accent)' : 'var(--text-2)', fontWeight: d.tailored_resume_id ? 500 : 400, cursor: d.tailored_resume_id ? 'pointer' : 'default' }}>{cv}{d.tailored_resume_id ? ' ↗' : ''}</span>
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
              <Menu ariaLabel="Application actions" style={{ ...POPOVER, right: 0, marginTop: 4, width: 226, textAlign: 'left' }}>
                {[['☰', 'View job in feed', () => navigate(`/v2/feed?job=${d.job_id}`)],
                  ...(d.has_cover_letter ? [['✎', 'Open cover letter', () => navigate(`/v2/cover-letters?job=${d.job_id}`)]] : [])].map(([g, label, act]) => (
                  <MenuItem key={label} icon={g} onClick={() => { setMenuOpen(false); act() }}>{label}</MenuItem>
                ))}
                <MenuItem danger icon="✕" onClick={onDelete}>Delete application</MenuItem>
              </Menu>
            )}
          </div>
        </div>

        {/* stage stepper */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {STAGES.map((s) => {
            const on = d.status === s.id
            const rej = s.id === 'rejected'
            return (
              /* ui: keep — a segmented stage stepper, not a card: equal-flex cells
                 tinted per stage (accent / bad) when current */
              <div key={s.id} onClick={() => { if (!on) onStage(s.id) }} title={s.hint} className="v2-bd"
                style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, height: 34, borderRadius: 8, fontSize: 12.5, cursor: 'pointer', fontWeight: on ? 600 : 400,
                  border: `1px solid ${on ? (rej ? 'var(--bad)' : 'var(--accent)') : 'var(--line)'}`,
                  background: on ? (rej ? 'var(--bad-soft)' : 'var(--accent-soft)') : 'var(--surface)',
                  color: on ? (rej ? 'var(--bad)' : 'var(--accent)') : 'var(--text-2)' }}>
                {/* ui: keep — the stage stepper's own dot, part of the segmented control */}
                <span style={{ width: 7, height: 7, borderRadius: 99, background: s.dot }} />{s.label}
              </div>
            )
          })}
        </div>
      </div>

      {/* body */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '18px 26px', display: 'flex', flexWrap: 'wrap', gap: 24, minHeight: 0 }}>
        <div style={{ flex: '1.2 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 15 }}>

          {(d.last_email_received || d.last_email_snippet) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <Label>Last email · Gmail detection</Label>
              <div style={{ padding: '10px 12px', borderLeft: '2px solid var(--accent)', background: 'var(--bg)', borderRadius: '0 8px 8px 0', fontSize: 12.5, fontStyle: 'italic', lineHeight: '19px', color: 'var(--text-2)', textWrap: 'pretty' }}>{d.last_email_snippet ? `“${d.last_email_snippet}”` : 'A reply was detected, but no snippet was stored.'}</div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Label>Interviews · {ivs.length}</Label>
              <Pill size="sm" onClick={openPrep} style={{ marginLeft: 'auto' }}
                title="Builds one pasteable block — the role, my résumé, the posting and what to ask for — for the AI of your choice">
                <span style={{ fontSize: 11 }}>⧉</span>Generate prep handover for AI
              </Pill>
            </div>
            {ivs.map((iv) => (
              <Card key={iv.id} style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: editIv === iv.id ? 8 : 3, ...(editIv === iv.id ? { borderColor: 'var(--accent)' } : { background: 'var(--bg)' }) }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {/* R3-A-06: the row text opens the editor; the status chip and ✕
                      keep the behaviour they had, so nothing that worked moved. */}
                  <span onClick={() => (editIv === iv.id ? setEditIv(null) : openIvEdit(iv))} title={editIv === iv.id ? 'Close without saving' : 'Edit this interview'} style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'pointer' }}>{iv.what}</span>
                  {/* ui: keep — an uppercase status badge with a background + r99: the
                      `Tag` role (D4d), not a Label */}
                  <span onClick={() => toggleInterview(iv)} title="Toggle scheduled / done" style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, cursor: 'pointer', background: iv.status === 'scheduled' ? 'var(--accent-soft)' : 'var(--surface-2)', color: iv.status === 'scheduled' ? 'var(--good)' : 'var(--text-2)' }}>{iv.status}</span>
                  <span onClick={() => delInterview(iv)} title="Remove this interview" className="v2-hover-bad" style={{ fontSize: 11, color: 'var(--muted)', cursor: 'pointer', padding: 2, borderRadius: 4 }}>✕</span>
                </div>
                {editIv === iv.id ? (
                  <>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Label>What</Label>
                      <Input autoFocus value={ivDraft.what} onChange={(t) => setIvDraft((v) => ({ ...v, what: t }))} placeholder="e.g. System design round" ariaLabel="What" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                        <Label>When</Label>
                        <Input type="datetime-local" value={ivDraft.when} onChange={(t) => setIvDraft((v) => ({ ...v, when: t }))} ariaLabel="When" style={{ minWidth: 0 }} />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                        <Label>Where</Label>
                        <Input value={ivDraft.where} onChange={(t) => setIvDraft((v) => ({ ...v, where: t }))} placeholder="Zoom · Onsite — London" ariaLabel="Where" style={{ minWidth: 0 }} />
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Label>Prep note · optional</Label>
                      <Input value={ivDraft.prep} onChange={(t) => setIvDraft((v) => ({ ...v, prep: t }))} placeholder="Who I'm meeting, what to revise…" ariaLabel="Prep note" />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <Helper>Escape cancels</Helper>
                      <Button variant="secondary" size="xs" onClick={() => setEditIv(null)} style={{ marginLeft: 'auto' }}>Cancel</Button>
                      <Button size="xs" onClick={saveInterview} busy={intBusy}>{intBusy ? 'Saving…' : 'Save'}</Button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* ui: keep — the whole slot line is a click target that opens the
                        interview editor, and `Helper` takes no `onClick` */}
                    <span onClick={() => openIvEdit(iv)} title="Edit this interview" style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)', cursor: 'pointer' }}>
                      {[fmtWhen(iv.when_at), iv.where_text].filter(Boolean).join(' · ') || 'Unscheduled'}
                    </span>
                    {iv.prep && <span onClick={() => openIvEdit(iv)} style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-2)', textWrap: 'pretty', cursor: 'pointer' }}>{iv.prep}</span>}
                  </>
                )}
              </Card>
            ))}
            {intForm ? (
              <Card style={{ display: 'flex', flexDirection: 'column', gap: 8, borderColor: 'var(--accent)', padding: '10px 12px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <Label>What</Label>
                  <Input value={intWhat} onChange={setIntWhat} placeholder="e.g. System design round" ariaLabel="What" />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <Label>When</Label>
                    <Input type="datetime-local" value={intWhen} onChange={setIntWhen} ariaLabel="When" style={{ minWidth: 0 }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                    <Label>Where</Label>
                    <Input value={intWhere} onChange={setIntWhere} placeholder="Zoom · Onsite — London" ariaLabel="Where" style={{ minWidth: 0 }} />
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <Label>Prep note · optional</Label>
                  <Input value={intPrep} onChange={setIntPrep} placeholder="Who I'm meeting, what to revise…" ariaLabel="Prep note" />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 7 }}>
                  <Button variant="secondary" size="xs" onClick={() => { setIntForm(false); setIntWhat(''); setIntWhen(''); setIntWhere(''); setIntPrep('') }}>Cancel</Button>
                  <Button size="xs" onClick={addInterview} disabled={!canAddInterview}>Add interview</Button>
                </div>
              </Card>
            ) : (
              <DashedAdd big onClick={() => setIntForm(true)} style={{ gap: 7 }}>+ Add interview</DashedAdd>
            )}
          </div>


          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Notes · autosaves</Label>
            {/* rows={2} keeps the intrinsic height (2×19 + 13 = 51) under the 64 px
                floor, so `minHeight` is the value that actually renders — the pre-D4b
                box. At rows={3} the intrinsic height wins and the floor is dead code. */}
            <Textarea key={d.id} defaultValue={d.notes || ''} onChange={(t) => onNotes(t)}
              onBlur={(e) => onNotes(e.target.value, true)} placeholder="Notes…" ariaLabel="Notes"
              rows={2} style={{ minHeight: 64 }} />
          </div>
        </div>

        {/* history rail */}
        <div style={{ flex: '1 0 250px', maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 6 }}>   {/* APPS-09: wraps under the content when the pane is narrow */}
          <Label>History</Label>
          {history.map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <Dot size={8} style={{ background: h.dot, marginTop: 4 }} />
                {i < history.length - 1 && <span style={{ width: 1, flex: 1, background: 'var(--line)' }} />}
              </div>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1, paddingBottom: 12 }}>
                <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--text)' }}>{h.what}</span>
                <Helper size="xs" mono>{ago(h.at)}</Helper>
              </div>
            </div>
          ))}
          {/* ui: keep — the empty rail sits on the history entries' own 12/18px line
              rhythm (matching the 12.5/18px event lines), not the helper step */}
          {history.length === 0 && <span style={{ fontSize: 12, lineHeight: '18px', color: 'var(--muted)' }}>No history recorded yet.</span>}
        </div>
      </div>
    </div>
  )
}

// ── prep modal ───────────────────────────────────────────────────────────────
function PrepModal({ prep, company, copied, onCopy, onClose }) {
  const busy = prep === 'loading' || prep?.failed === true
  const panel = useRef(null)
  useSnapTop(panel)   // RES-32
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div ref={panel} onClick={(e) => e.stopPropagation()} style={{ width: 640, maxHeight: 640, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Heading>Prep handover — {company}</Heading>
          <Helper>paste into the AI of your choice</Helper>
          <IconButton onClick={onClose} title="Close" style={{ marginLeft: 'auto' }}>✕</IconButton>
        </div>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '14px 22px', background: 'var(--bg)' }}>
          <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: 11, lineHeight: '18px', color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {prep === 'loading' ? 'Building the bundle…' : prep.text}
          </pre>
        </div>
        <div style={{ padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <Helper>Edit the closing ask in Settings → AI</Helper>
          <Button variant="secondary" size="sm" onClick={onClose} style={{ marginLeft: 'auto' }}>Close</Button>
          <Button size="sm" onClick={onCopy} busy={busy}>
            <span style={{ fontSize: 11 }}>⧉</span>{copied ? 'Copied ✓' : 'Copy to clipboard'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── log-application modal ────────────────────────────────────────────────────
function LogModal({ onClose, onSaved, pushToast, onDirty }) {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [resumes, setResumes] = useState([])
  const [cv, setCv] = useState('')
  const [stage, setStage] = useState('applied')
  const [when, setWhen] = useState(() => { const t = new Date(), p = (n) => String(n).padStart(2, '0'); return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}` })   // APPS-21: local date
  const [notes, setNotes] = useState('')
  useEffect(() => { onDirty?.(!!(url.trim() || title.trim() || company.trim() || notes.trim())) }, [url, title, company, notes])   // APPS-22
  const [busy, setBusy] = useState(false)
  const [reading, setReading] = useState(false)
  const panel = useRef(null)
  useSnapTop(panel)   // RES-32

  // OPEN-05: converted (the APPS-01 residue). The chips are the modal's only
  // way to attach a résumé, and the user opened the modal to log an application —
  // an empty row read as "you have no résumés", which is a different thing.
  useEffect(() => { api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your résumés — log it now and attach one later.' }) }) }, [pushToast])

  // R2-H-07: `title`/`company` are captured in readUrl's closure at call time —
  // both empty — so a response landing after the user had typed overwrote what
  // they typed. Read the live draft off a ref instead, and drop a response whose
  // URL is no longer the one in the field.
  const draftRef = useRef({ title: '', company: '' })
  draftRef.current = { title, company }
  const urlRef = useRef('')

  // paste a URL → read title + company off the posting
  const readUrl = async (u) => {
    const target = u.trim()
    if (!target.startsWith('http')) return
    urlRef.current = target
    setReading(true)
    try {
      const { data } = await api.post('/applications/extract', { url: target })
      if (urlRef.current !== target) return                                  // a newer URL is in the field
      if (data.title && !draftRef.current.title.trim()) setTitle(data.title)
      if (data.company && !draftRef.current.company.trim()) setCompany(data.company)
    } catch (e) {
      if (urlRef.current !== target) return
      console.error(e); pushToast({ kind: 'error', msg: 'Could not read job details from that URL' + errSuffix(e) })
    } finally {
      if (urlRef.current === target) setReading(false)
    }
  }

  const save = async () => {
    if (!title.trim() || !company.trim() || !url.trim()) {
      pushToast({ kind: 'error', msg: !url.trim() ? 'The posting URL is required — it identifies the job' : 'Title and company are required' })
      const first = [url, title, company].findIndex((v) => !v.trim()); document.querySelectorAll('input[placeholder]')[first]?.focus()   // APPS-17
      return
    }
    setBusy(true)
    try {
      const { data } = await api.post('/applications', {
        url: url.trim(), title: title.trim(), company: company.trim(),
        cv_version_used: cv || null, notes: notes.trim() || null,
        status: stage, applied_at: when ? new Date(when + 'T12:00:00').toISOString() : null,   // APPS-21: local noon, never the previous UTC day
      })
      onSaved(data.id)
    } catch (e) {
      const existing = e.response?.status === 409 ? e.response?.data?.detail?.application_id : null
      if (existing) { pushToast({ kind: 'progress', msg: 'Already logged — opened the existing application.' }); onSaved(existing); return }   // APPS-04
      pushToast({ kind: 'error', msg: 'Could not save this application' + errSuffix(e) }); setBusy(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div ref={panel} onClick={(e) => e.stopPropagation()} style={{ width: 520, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Heading>Log application</Heading>
          <Helper style={{ textWrap: 'pretty' }}>For applications made outside the app — jobs from the feed log themselves when you mark them applied.</Helper>
        </div>
        <div className="v2-scroll" style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 470, overflow: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Posting URL{reading ? ' · reading…' : ''}</Label>
            <Input value={url} onChange={setUrl} onBlur={(e) => readUrl(e.target.value)} mono
              placeholder="Paste the job URL — title and company are read from it" ariaLabel="Posting URL" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
              <Label>Title</Label>
              <Input value={title} onChange={setTitle} placeholder="Senior Backend Engineer" ariaLabel="Title" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
              <Label>Company</Label>
              <Input value={company} onChange={setCompany} placeholder="Acme" ariaLabel="Company" />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <Label>Applied with</Label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {resumes.map((r) => {
                const on = cv === r.name
                return <Pill key={r.id} size="sm" on={on} onClick={() => setCv(on ? '' : r.name)}>{r.name}</Pill>
              })}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
            <Label>Stage</Label>
            <div style={{ display: 'flex', gap: 5 }}>
              {['applied', 'interview', 'offer'].map((id) => {
                const on = stage === id
                return <div key={id} onClick={() => setStage(id)} className="v2-bd" style={{ flex: 1, height: 33, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: on ? 600 : 400, cursor: 'pointer' }}>{STAGE[id].label}</div>
              })}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
            <Label>Applied on</Label>
            <Input type="date" value={when} onChange={setWhen} ariaLabel="Applied on" />
          </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Notes</Label>
            <Textarea value={notes} onChange={setNotes} placeholder="Optional — referral, recruiter contact…"
              ariaLabel="Notes" rows={2} style={{ minHeight: 52 }} />
          </div>
        </div>
        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <Helper>The posting is cached on save</Helper>
          <Button variant="secondary" size="sm" onClick={onClose} style={{ marginLeft: 'auto' }}>Cancel</Button>
          <Button size="sm" onClick={save} busy={busy}>{busy ? 'Saving…' : 'Save application'}</Button>
        </div>
      </div>
    </div>
  )
}
