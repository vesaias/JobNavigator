import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToasts, ToastStack } from './Toast'
import api from '../api'
import { Picker, VoicePicker, LengthPicker, LENGTHS, STAGE_CLASS } from './CoverLetters'
import ConfirmDialog from './ConfirmDialog'
// the undo-removal helper and the band rule are shared with the résumé editors
import { useUndoRemove, BandRule } from './ResumeSections'
import { Button, Card as UiCard, DashedAdd, FooterRow, Heading, HeaderRow, Helper, IconButton, Input, Label, Link, Menu, MenuItem, ModalPanel, MoveArrows, NavLink, RemoveX, SectionHead, Spinner, Surface, ToolbarTrigger } from './ui'
import './theme.css'
import { useTitle } from '../useTitle'
import { fetchRunOutcome, runFailed, runFailureReason, useSettled, NBSP } from './hooks'

const EMPTY = {
  header: { name: '', contact_items: [] },
  recipient: { company: '', manager: '', address: '' },
  date: '', greeting: 'Dear Hiring Team,', body_paragraphs: [''], closing: 'Sincerely,', signature: '',
}
const PAGE_FORMATS = [['letter', 'US Letter'], ['a4', 'A4']]
const UI_KEY = 'v2_cl_sections'
const loadUI = () => { try { return JSON.parse(localStorage.getItem(UI_KEY)) || {} } catch { return {} } }

import { ago } from './time'

// Contact-item cells are 1:1 with the Résumé editor's header — both are `Input` now.

// A collapsible editor card — the three sections of the letter.
function Card({ title, note, open, onToggle, children }) {
  return (
    <UiCard style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
      {/* caret={false}: this head keeps its own SVG chevron, which *rotates* between
          the two states rather than swapping glyphs */}
      <SectionHead card caret={false} hover="v2-clhead" open={!!open} onToggle={onToggle}
        style={{ padding: '10px 14px', borderRadius: '9px 9px 0 0' }}>
        <span style={{ flex: '0 0 auto', width: 10, height: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
          <svg width="8" height="8" viewBox="0 0 10 10" aria-hidden="true"
            style={{ display: 'block', transform: open ? 'none' : 'rotate(-90deg)', transition: 'transform .12s' }}>
            <path d="M2 4 L5 7 L8 4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', gap: 9 }}>
          <span style={{ flex: '0 0 auto', fontSize: 13, lineHeight: '20px', fontWeight: 600 }}>{title}</span>
          {/* ui: keep — the head's note rides the 13/20px title's line; Helper's 16px would unalign the row */}
          {note && <span style={{ flex: '0 1 auto', fontSize: 11.5, lineHeight: '20px', color: 'var(--muted)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{note}</span>}
        </span>
      </SectionHead>
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '2px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
          {children}
        </div>
      )}
    </UiCard>
  )
}

export default function CoverLetterEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  useTitle(doc?.name)
  const [data, setData] = useState(EMPTY)
  const [template, setTemplate] = useState('')
  const [format, setFormat] = useState('letter')
  const [templates, setTemplates] = useState([])
  const [savedAt, setSavedAt] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [tplOpen, setTplOpen] = useState(false)
  const [fmtOpen, setFmtOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [regenOpen, setRegenOpen] = useState(false)
  const [confirm, setConfirm] = useState(null)   // RES-16: v2 dialog, not window.confirm
  // CL-28: one `err` slot used to hold every failure on the screen, so a PDF
  // download error sat in the top bar indefinitely (only a successful save
  // cleared it) next to a letter name it had pushed out. The bar now holds save
  // failures only — they are the one error the autosave header is about — and
  // everything else goes to the toast host. `err` keeps the load and regenerate
  // failures, which have their own slots (the empty state and the regen footer).
  const [saveErr, setSaveErr] = useState('')
  const [regening, setRegening] = useState(false)
  const [presets, setPresets] = useState([])
  const [resumes, setResumes] = useState([])
  const [personaAvailable, setPersonaAvailable] = useState(false)
  const [rSource, setRSource] = useState('')
  const [rVoice, setRVoice] = useState('')
  const [rLength, setRLength] = useState('standard')
  const [err, setErr] = useState('')
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()   // CL-18
  const [pdfErr, setPdfErr] = useState(false); const [pdfNonce, setPdfNonce] = useState(0)   // CL-19
  const [headOpen, setHeadOpen] = useState(() => loadUI().headOpen ?? false)
  const [recipOpen, setRecipOpen] = useState(() => loadUI().recipOpen ?? false)
  const [letterOpen, setLetterOpen] = useState(() => loadUI().letterOpen ?? true)
  useEffect(() => { try { localStorage.setItem(UI_KEY, JSON.stringify({ headOpen, recipOpen, letterOpen })) } catch {} }, [headOpen, recipOpen, letterOpen])

  const saveTimer = useRef(null)
  const pendingPatch = useRef({})
  const pdfTimer = useRef(null)
  const prevBlob = useRef(null)
  const loaded = useRef(false)

  useEffect(() => {
    let dead = false
    loaded.current = false
    api.get(`/cover-letters/${id}`).then(({ data: d }) => {
      if (dead) return
      setDoc(d); setData({ ...EMPTY, ...(d.json_data || {}) })
      setTemplate(d.template || ''); setFormat(d.page_format || 'letter'); setSavedAt(d.updated_at)
      setRSource(d.from_persona ? 'persona' : (d.resume_id || ''))
      setRVoice(d.voice || ''); setRLength(d.length || 'standard')
      loaded.current = true
    }).catch((e) => { if (!dead) setErr(e?.response?.status === 404 ? 'This letter no longer exists.' : 'Couldn’t load this letter — try again.') })   // CL-15
    return () => { dead = true }
  }, [id])

  // DESIGN-LOAD: these four are the editor's chrome — the layout and paper
  // pickers, the Regenerate source list and the voice list. They settle as one,
  // and `metaReady` (with the document, which already gates the whole screen)
  // is what lets the preview toolbar draw: otherwise the Template trigger paints
  // the raw template *id* and swaps to its name a moment later.
  // OPEN-05: converted — failing silently left those pickers empty with nothing
  // to say why, on a screen the user just opened. Each keeps its own catch.
  const { ready: metaReady } = useSettled([
    () => api.get('/cover-letters/templates').then(({ data }) => setTemplates(data || [])).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the layouts — the picker is empty.' }) }),
    () => api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your résumés — Regenerate has no source to pick.' }) }),
    () => api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load your Persona — it will not be offered as a source.' }) }),
    () => api.get('/settings').then(({ data }) => {
      let p = data.cover_letter_voice_presets
      if (typeof p === 'string') { try { p = JSON.parse(p) } catch { p = [] } }
      setPresets(Array.isArray(p) ? p : [])
      setRVoice((v) => v || data.cover_letter_default_voice || '')
    }).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the voice presets — the voice picker is empty.' }) }),
  ])

  useEffect(() => () => { clearTimeout(saveTimer.current); clearTimeout(pdfTimer.current) }, [])
  useEffect(() => () => { if (prevBlob.current) URL.revokeObjectURL(prevBlob.current) }, [])

  // autosave (debounced) — the header says "autosaves", so no save button.
  // One timer serves every patch kind, so the pending patches must MERGE:
  // replacing them wholesale silently dropped a {template} pick made within
  // 500 ms of a keystroke (and vice versa) while the header still said "saved".
  const persist = useCallback((patch) => {
    if (!loaded.current) return
    pendingPatch.current = { ...pendingPatch.current, ...patch }
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      const body = pendingPatch.current
      pendingPatch.current = {}
      try { await api.patch(`/cover-letters/${id}`, body); setSavedAt(new Date().toISOString()); setSaveErr('') }
      catch (e) { console.error(e); setSaveErr('Could not save — your last edit is not stored.'); pushToast({ kind: 'error', msg: 'Could not save — your last edit is not stored.' }) }
    }, 500)
  }, [id])

  const update = (mutator) => {
    setData((prev) => {
      const next = JSON.parse(JSON.stringify(prev))
      mutator(next)
      persist({ json_data: next })
      return next
    })
  }

  // RES-16: every other destructive edit in the three builders is undoable; the
  // body paragraph was the one that just vanished.
  const undoRemove = useUndoRemove(update, (msg, undo) => pushToast({ kind: 'undo', msg, action: 'Undo', onAction: undo }))

  // live PDF, debounced behind the save so we never render a stale draft
  useEffect(() => {
    if (!doc) return
    clearTimeout(pdfTimer.current)
    const ac = new AbortController()
    setPdfBusy(true)
    pdfTimer.current = setTimeout(async () => {
      try {
        const r = await api.get(`/cover-letters/${id}/pdf`, { responseType: 'arraybuffer', signal: ac.signal })
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
        if (prevBlob.current) URL.revokeObjectURL(prevBlob.current)
        prevBlob.current = url
        setPdfUrl(url)
        setPdfErr(false)
      } catch (e) { if (e.name !== 'CanceledError') { console.error(e); setPdfErr(true) } }   // CL-19
      setPdfBusy(false)
    }, 900)
    return () => { clearTimeout(pdfTimer.current); ac.abort() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, template, format, doc, id, pdfNonce])

  const pickTemplate = (t) => { setTemplate(t); setTplOpen(false); persist({ template: t }) }
  const pickFormat = (f) => { setFormat(f); setFmtOpen(false); persist({ page_format: f }) }

  // v1's download was a bare <a>, which drops the X-API-Key header and 401s
  // whenever a dashboard key is set — go through axios and save the blob.
  const download = async () => {
    try {
      const r = await api.get(`/cover-letters/${id}/pdf`, { responseType: 'blob' })
      const cd = r.headers['content-disposition'] || ''
      const m = /filename="?([^"]+)"?/.exec(cd)
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url; a.download = m ? m[1] : 'CoverLetter.pdf'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not download the PDF.' }) }   // CL-28: a download failure is not a save failure
  }

  const remove = () => {
    setMenuOpen(false)
    setConfirm({
      title: `Delete "${doc?.name}"?`, body: 'This cannot be undone.', label: 'Delete', danger: true,
      onConfirm: async () => {
        setConfirm(null)
        try { await api.delete(`/cover-letters/${id}`); window.dispatchEvent(new CustomEvent('jn:counts-changed')); navigate('/v2/cover-letters') }   // CL-17
        catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not delete this letter.' }) }   // CL-28
      },
    })
  }

  const regenRun = useRef(null)   // DS-B-02: run_id of the regenerate in flight
  const regenerate = async () => {
    if (regening || !rSource) return
    setRegening(true); setErr('')
    try {
      const { data: started } = await api.post('/cover-letters/generate', {
        resume_id: rSource, job_id: doc.job_id, voice: rVoice, length: rLength,
        cover_letter_id: id,       // rewrite this draft in place
      })
      regenRun.current = started?.run_id || null   // DS-B-02: read its status below
    } catch (e) {
      setRegening(false)
      setErr(e?.response?.data?.detail || 'Regeneration failed')
      pushToast({ kind: 'error', msg: e?.response?.data?.detail || 'Regeneration failed' })   // CL-14/18: visible above the modal scrim
    }
  }

  // watch the run; when it clears, reload the rewritten letter
  useEffect(() => {
    if (!regening) return
    let dead = false
    const iv = setInterval(async () => {
      try {
        const { data: runs } = await api.get('/monitor/active')
        // scope to THIS letter — the backend keys a regenerate as cl:{letter id}
        // (routes_cover_letters.py:341). Matching any generate_cover_letter run
        // kept this modal spinning until every unrelated generation finished.
        const live = (runs || []).some((r) => r.job_type === 'generate_cover_letter' && r.scope_key === `cl:${id}`)
        if (!live && !dead) {
          // DS-B-02: the run leaving /monitor/active only means it ended. A failed
          // regenerate used to close this modal on an unchanged draft, silently
          // indistinguishable from a rewrite. Ask the run what happened; on a
          // failure keep the modal open with the reason so it can be retried.
          const run = await fetchRunOutcome(regenRun.current, 'generate_cover_letter')
          if (dead) return
          if (runFailed(run)) {
            clearInterval(iv)
            setRegening(false)
            setErr(`Regeneration failed — ${runFailureReason(run)}`)
            pushToast({ kind: 'error', msg: `Regeneration failed — ${runFailureReason(run)}` })
            return
          }
          // reload FIRST: clearing the interval before a GET that throws left
          // `regening` true for ever with no poll to clear it (modal locked)
          const { data: d } = await api.get(`/cover-letters/${id}`)
          if (dead) return
          clearInterval(iv)
          setDoc(d); setData({ ...EMPTY, ...(d.json_data || {}) })
          setTemplate(d.template || ''); setFormat(d.page_format || 'letter'); setSavedAt(d.updated_at)
          setRVoice(d.voice || ''); setRLength(d.length || 'standard')
          setRegening(false); setRegenOpen(false)
        }
      } catch { /* retry */ }
    }, 2000)
    return () => { dead = true; clearInterval(iv) }
  }, [regening, id, pushToast])

  // RES-15: Escape closes the modal through the shared hook. This handler keeps the
  // menu/dropdown half (CL-25) and marks the event handled when one was actually
  // open, so the same press can't close a dropdown and the modal behind it.
  const openUi = useRef({ menuOpen: false, tplOpen: false, fmtOpen: false })
  openUi.current = { menuOpen, tplOpen, fmtOpen }
  useEffect(() => {
    const onDoc = () => { setMenuOpen(false); setTplOpen(false); setFmtOpen(false) }
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const u = openUi.current
      if (u.menuOpen || u.tplOpen || u.fmtOpen) { e.preventDefault(); onDoc() }
    }
    document.addEventListener('click', onDoc); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])

  const sourceOpts = useMemo(() => {
    const opts = [
      ...(personaAvailable ? [{ id: 'persona', label: 'Persona (full profile)' }] : []),
      ...resumes.map((r) => ({ id: r.id, label: r.name })),
    ]
    // R2-H-14: the list is bases + Persona, but a letter generated from the
    // Résumé editor is paired with a *tailored* copy. Its id matched no option, so
    // the picker showed "Select a source…" while Regenerate ran against that very
    // copy. Prepend the letter's own source when it isn't already there.
    const own = doc?.resume_id
    if (own && !doc.from_persona && !opts.some((o) => String(o.id) === String(own))) {
      opts.unshift({ id: own, label: doc.source_name ? `${doc.source_name} · tailored copy` : 'This letter’s tailored copy' })
    }
    return opts
  }, [resumes, personaAvailable, doc])

  if (!doc) {
    // the 404 / load-failure page stays exactly as it was
    if (err) {
      return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, color: 'var(--muted)', fontSize: 13 }}>
          <span>{err}</span>
          <span style={{ display: 'flex', gap: 14 }}>
            <Link onClick={() => navigate('/v2/cover-letters')}>‹ Back to cover letters</Link>
            {!/no longer exists/.test(err) && <Link onClick={() => window.location.reload()}>Try again</Link>}
          </span>
        </div>
      )
    }
    // DESIGN-LOAD: reserve the chrome's own shape while the document fetch is in
    // flight, instead of a bare "Loading…" that collapses the whole screen to one
    // centred line and then jumps to the real top-bar + two-pane layout once the
    // doc lands. NBSP holds the top bar's line height; the panes need no content
    // to reserve theirs — they already flex to fill what's left.
    return (
      <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <HeaderRow pad="10px 24px" bg="surface" soft align="center">
          <span style={{ fontSize: 14, lineHeight: '20px' }}>{NBSP}</span>
        </HeaderRow>
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <section style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)' }} />
          <Surface as="section" radius="none" style={{ flex: 1, minWidth: 0 }} />
        </div>
      </div>
    )
  }

  const paras = data.body_paragraphs || []
  const stage = doc.stage
  const badge = stage ? stage.toUpperCase() : 'DRAFT'
  const voiceLabel = presets.find((p) => p.id === doc.voice)?.label || doc.voice
  const lengthLabel = LENGTHS.find(([lid]) => lid === doc.length)?.[1] || doc.length
  const voiceLen = [voiceLabel, lengthLabel].filter(Boolean).join(' · ') || 'voice and length unknown for this letter'
  const tplLabel = templates.find((t) => t.id === template)?.name || template || 'Template'
  const fmtLabel = PAGE_FORMATS.find(([f]) => f === format)?.[1] || format

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* top bar */}
      <HeaderRow pad="10px 24px" bg="surface" soft align="center">
        <NavLink onClick={() => navigate('/v2/cover-letters')} style={{ whiteSpace: 'nowrap' }}>‹ Cover Letters</NavLink>
        <span style={{ color: 'var(--line)' }}>|</span>
        {/* S5: the Draft/stage badge is ResumeEditor's Base/Tailored twin — same Tag
            role, same token read. --label-case is `uppercase` and
            --label-tracking-scale 1 in the base blocks, so the paint is unchanged. */}
        <span className={stage ? (STAGE_CLASS[stage] || 'cc-generic') : 'cc-generic'}
          style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: 'calc(.08em * var(--label-tracking-scale))', textTransform: 'var(--label-case)', padding: '2px 7px', borderRadius: 'var(--radius-control)' }}>{badge}</span>
        {/* R2-S-06: every other v2 screen names itself with an h1; visually this
            is the same span it always was (margin and font reset inline). */}
        <h1 title={doc.name} style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: '20px', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 420 }}>{doc.name}</h1>
        <Helper title={saveErr || undefined} style={{ marginLeft: 'auto', flex: '0 1 auto', minWidth: 0, maxWidth: 300, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', ...(saveErr ? { color: 'var(--bad)' } : null) }}>
          {saveErr || (savedAt ? `saved ${ago(savedAt)} · autosaves` : 'autosaves')}
        </Helper>
      </HeaderRow>

      {/* context band */}
      <HeaderRow pad="9px 24px" bg="recessed" align="center" style={{ gap: 13 }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ minWidth: 0, fontSize: 12.5, lineHeight: '18px', fontWeight: 500, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Written for <span style={{ color: 'var(--text)' }}>{doc.company ? `${doc.company} — ${doc.title}` : doc.name}</span>
            {doc.source_name && <><BandRule />from <span onClick={() => doc.resume_id && navigate(`/v2/resumes/${doc.resume_id}`)}
              title={doc.resume_id ? 'Open the source résumé' : 'Written from your Persona'}
              style={{ color: 'var(--accent)', cursor: doc.resume_id ? 'pointer' : 'default' }}>{doc.source_name}{doc.resume_id ? ' ↗' : ''}</span></>}
          </span>
          <Helper>{voiceLen}</Helper>
        </div>
        <Button onClick={() => { setRegenOpen(true); setMenuOpen(false) }} title="Rewrite the letter — pick base résumé, voice and length">
          {regening
            ? <Spinner size={11} color="currentColor" />
            : <span style={{ fontSize: 12 }}>↻</span>}
          Regenerate…
        </Button>
        <div style={{ position: 'relative', flex: '0 0 auto' }} onClick={(e) => e.stopPropagation()}>
          <IconButton size={36} on={menuOpen} ariaExpanded={menuOpen} ariaHaspopup="menu"
            onClick={() => setMenuOpen((v) => !v)} title="More actions">⋯</IconButton>
          {menuOpen && (
            <Menu ariaLabel="Letter actions" style={{ position: 'absolute', top: '100%', right: 0, marginTop: 5, width: 224, zIndex: 50 }}>
              {doc.has_application && (
                <MenuItem icon="▤" onClick={() => { setMenuOpen(false); navigate('/v2/applications') }}>View application</MenuItem>
              )}
              {doc.job_id && (
                <MenuItem icon="☰" onClick={() => { setMenuOpen(false); navigate(`/v2/feed?job=${doc.job_id}`) }}>View job in feed</MenuItem>
              )}
              {doc.job_url && (
                <MenuItem icon="↗" href={doc.job_url} target="_blank" onClick={() => setMenuOpen(false)}>Open job posting</MenuItem>
              )}
              <MenuItem danger icon="✕" onClick={remove}>Delete letter</MenuItem>
            </Menu>
          )}
        </div>
      </HeaderRow>

      {/* split body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <section className="v2-scroll" style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '14px 20px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>

          <Card title="Header" open={headOpen} onToggle={() => setHeadOpen((v) => !v)}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 10 }}>
              <Label>Full name</Label>
              <Input value={data.header?.name || ''} onChange={(v) => update((d) => { d.header = d.header || {}; d.header.name = v })} ariaLabel="Full name" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <Label>Contact items</Label>
                {/* integer line-height: at 1.5 this 10.5px hint is 15.75 tall and
                    pushes every card below onto a half pixel (borders drop out) */}
                <Helper size="xs" style={{ marginLeft: 'auto' }}>text · link · stub</Helper>
              </div>
              {(data.header?.contact_items || []).map((ct, i, arr) => {
                const tracked = ct.url && !String(ct.url).startsWith('mailto:')
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ flex: '45 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* controls + text: 45 % of the row */}
                    <MoveArrows upOff={i === 0} downOff={i === arr.length - 1}
                      onUp={() => update((d) => { const a = d.header.contact_items; [a[i - 1], a[i]] = [a[i], a[i - 1]] })}
                      onDown={() => update((d) => { const a = d.header.contact_items; [a[i + 1], a[i]] = [a[i], a[i + 1]] })} />
                    <Input value={ct.text || ''} placeholder="Display text" ariaLabel="Contact item text"
                      onChange={(v) => update((d) => { d.header.contact_items[i].text = v })}
                      style={{ flex: 1, minWidth: 0 }} />
                    </div>
                    <div style={{ flex: '55 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* url + stub: 55 % */}
                    <Input value={ct.url || ''} placeholder="URL (optional)" ariaLabel="Contact item URL"
                      onChange={(v) => update((d) => { d.header.contact_items[i].url = v })}
                      style={{ flex: 1, minWidth: 0 }} />
                    {tracked && (
                      <Input value={ct.stub || ''} placeholder="id" mono ariaLabel="Tracked link stub"
                        title="Short stub used in the tracked link, e.g. l, w, gh"
                        onChange={(v) => update((d) => { d.header.contact_items[i].stub = v })}
                        style={{ flex: '0 0 34px', padding: '0 6px', textAlign: 'center', minWidth: 0 }} />
                    )}
                    <RemoveX onClick={() => update((d) => { d.header.contact_items.splice(i, 1) })} />
                    </div>
                  </div>
                )
              })}
              <DashedAdd onClick={() => update((d) => { d.header = d.header || {}; d.header.contact_items = [...(d.header.contact_items || []), { text: '', url: '' }] })}>+ Add contact item</DashedAdd>
            </div>
          </Card>

          <Card title="Recipient" note={[data.recipient?.company, data.date].filter(Boolean).join(' · ')}
            open={recipOpen} onToggle={() => setRecipOpen((v) => !v)}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, paddingTop: 10 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Company</Label>
                <Input value={data.recipient?.company || ''} onChange={(v) => update((d) => { d.recipient = d.recipient || {}; d.recipient.company = v })} ariaLabel="Company" style={{ minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Date</Label>
                <Input value={data.date || ''} onChange={(v) => update((d) => { d.date = v })} ariaLabel="Date" style={{ minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Hiring manager</Label>
                <Input value={data.recipient?.manager || ''} placeholder="Unknown" onChange={(v) => update((d) => { d.recipient = d.recipient || {}; d.recipient.manager = v })} ariaLabel="Hiring manager" style={{ minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Address</Label>
                <Input value={data.recipient?.address || ''} placeholder="—" onChange={(v) => update((d) => { d.recipient = d.recipient || {}; d.recipient.address = v })} ariaLabel="Address" style={{ minWidth: 0 }} />
              </div>
            </div>
          </Card>

          <Card title="Letter" note={`${paras.length} paragraph${paras.length === 1 ? '' : 's'}`}
            open={letterOpen} onToggle={() => setLetterOpen((v) => !v)}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 10 }}>
              <Label>Greeting</Label>
              <Input value={data.greeting || ''} onChange={(v) => update((d) => { d.greeting = v })} ariaLabel="Greeting" />
            </div>
            {paras.map((text, i) => (
              <UiCard key={i} style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '7px 10px 0' }}>
                  {/* ui: keep — the ¶ ordinal is drawn in --edge, a dimmer ink than --label-ink, at .1em */}
                  <span style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--edge)' }}>¶ {i + 1}</span>
                  <span onClick={() => i > 0 && update((d) => { const a = d.body_paragraphs; [a[i - 1], a[i]] = [a[i], a[i - 1]] })} title="Move up" className={i > 0 ? 'v2-parabtn' : ''}
                    style={{ marginLeft: 'auto', width: 20, height: 20, borderRadius: 'var(--radius-mini)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: i === 0 ? 'var(--line-strong)' : 'var(--text-2)', cursor: i === 0 ? 'default' : 'pointer' }}>↑</span>
                  <span onClick={() => i < paras.length - 1 && update((d) => { const a = d.body_paragraphs; [a[i + 1], a[i]] = [a[i], a[i + 1]] })} title="Move down" className={i < paras.length - 1 ? 'v2-parabtn' : ''}
                    style={{ width: 20, height: 20, borderRadius: 'var(--radius-mini)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: i === paras.length - 1 ? 'var(--line-strong)' : 'var(--text-2)', cursor: i === paras.length - 1 ? 'default' : 'pointer' }}>↓</span>
                  <span onClick={() => undoRemove('Removed paragraph',
                    (d) => { d.body_paragraphs.splice(i, 1) },
                    (d) => { d.body_paragraphs = d.body_paragraphs || []; d.body_paragraphs.splice(i, 0, text) })} title="Delete paragraph" className="v2-parabtn-bad"
                    style={{ width: 20, height: 20, borderRadius: 'var(--radius-mini)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--edge)', cursor: 'pointer' }}>✕</span>
                </div>
                {/* ui: keep — a paragraph is flowing text inside the ¶ card's own box: no
                    border, no background, margin instead of padding, resize:none */}
                <textarea value={text} rows={4} onChange={(e) => update((d) => { d.body_paragraphs[i] = e.target.value })}
                  style={{ margin: '4px 10px 9px', border: 'none', background: 'transparent', fontFamily: 'var(--sans)', fontSize: 12.5, lineHeight: '19px', color: 'var(--text)', outline: 'none', resize: 'none' }} />
              </UiCard>
            ))}
            <DashedAdd onClick={() => update((d) => { d.body_paragraphs = [...(d.body_paragraphs || []), ''] })} style={{ gap: 7 }}>+ Add paragraph</DashedAdd>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Closing</Label>
                <Input value={data.closing || ''} onChange={(v) => update((d) => { d.closing = v })} ariaLabel="Closing" style={{ minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <Label>Signature</Label>
                <Input value={data.signature || ''} onChange={(v) => update((d) => { d.signature = v })} ariaLabel="Signature" style={{ minWidth: 0 }} />
              </div>
            </div>
          </Card>
        </section>

        {/* preview */}
        <Surface as="section" radius="none" style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <HeaderRow pad="8px 20px" align="center" style={{ flexWrap: 'wrap', rowGap: 6, gap: 9 }}>
            <Label>PDF preview</Label>
            {pdfBusy && <Spinner size={10} color="var(--edge)" />}

            {/* DESIGN-LOAD: the two triggers wait for the template list. The row's
                height is the Download button's, so nothing moves when they land —
                and the Template trigger never shows a raw id first. */}
            {metaReady && <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
              <ToolbarTrigger label="Template" value={tplLabel} onClick={() => { setTplOpen((v) => !v); setFmtOpen(false) }}
                title="Cover letter template" />
              {tplOpen && (
                <Menu role="listbox" ariaLabel="Cover letter template" className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, width: 210, maxHeight: 300, overflow: 'auto' }}>
                  {templates.map((t) => (
                    <MenuItem key={t.id} role="option" ariaSelected={t.id === template} selected={t.id === template}
                      title={t.description || ''} onClick={() => pickTemplate(t.id)}>{t.name}</MenuItem>
                  ))}
                </Menu>
              )}
            </span>}

            {metaReady && <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
              <ToolbarTrigger label="Paper" value={fmtLabel} onClick={() => { setFmtOpen((v) => !v); setTplOpen(false) }}
                title="Paper size — US Letter or A4" />
              {fmtOpen && (
                <Menu role="listbox" ariaLabel="Paper size" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, width: 130 }}>
                  {PAGE_FORMATS.map(([f, label]) => (
                    <MenuItem key={f} role="option" ariaSelected={f === format} selected={f === format}
                      onClick={() => pickFormat(f)}>{label}</MenuItem>
                  ))}
                </Menu>
              )}
            </span>}

            {pdfErr && <span style={{ fontSize: 11, lineHeight: '14px', color: 'var(--bad)', whiteSpace: 'nowrap' }}>Preview failed. Showing the previous version · <span onClick={() => setPdfNonce((n) => n + 1)} style={{ cursor: 'pointer', borderBottom: '1px dotted currentColor' }}>Retry</span></span>}
            <Button size="xs" onClick={download} style={{ marginLeft: 'auto' }}>↓ Download PDF</Button>
          </HeaderRow>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {pdfUrl
              ? <iframe title="cover letter preview" src={`${pdfUrl}#view=FitH`} style={{ width: '100%', height: '100%', border: 'none' }} />
              : <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12.5, color: 'var(--muted)' }}>Rendering the preview…</div>}
          </div>
        </Surface>
      </div>

      {regenOpen && (
        // CL: a run in flight is not cancellable, so while `regening` the panel
        // takes no `onClose` at all — no scrim click, no Escape listener, exactly
        // the `regenOpen && !regening` guard it had.
        <ModalPanel width={460} zIndex={60} onClose={regening ? undefined : () => setRegenOpen(false)} style={{ overflow: 'hidden' }}>
            <HeaderRow align="stretch" style={{ flexDirection: 'column', gap: 3 }}>
              <Heading>Regenerate letter</Heading>
              <Helper style={{ textWrap: 'pretty' }}>
                Rewrites the whole letter for {doc.company || 'this role'} — your edits to this draft are replaced.
              </Helper>
            </HeaderRow>
            <div style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 13 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <Label>From résumé</Label>
                <Picker value={rSource} options={sourceOpts} placeholder="Select a source…" onPick={setRSource} />
                <Helper size="xs" style={{ textWrap: 'pretty' }}>Bases and Persona. Switch to use a different set of achievements.</Helper>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <Label>Voice</Label>
                {/* DESIGN-LOAD: "No voice presets…" is a verdict, not a loading
                    state — the row holds a pill's height until the settle. */}
                <div style={{ minHeight: 26 }}>{metaReady && <VoicePicker presets={presets} value={rVoice} onPick={setRVoice} />}</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <Label>Length</Label>
                <LengthPicker value={rLength} onPick={setRLength} />
              </div>
            </div>
            <FooterRow bg="page" style={{ flex: '0 0 auto' }}>
              {err && !regening ? <Helper style={{ color: 'var(--bad)' }}>{err}</Helper> : <Helper>~30 seconds</Helper>}   {/* CL-14 */}
              <Button variant="secondary" size="sm" onClick={() => !regening && setRegenOpen(false)} style={{ marginLeft: 'auto' }}>Cancel</Button>
              {/* RES-17: a disabled primary pill is --line on --muted across the three
                  builders — a dimmed accent still reads as the live button. */}
              <Button size="sm" onClick={regenerate} disabled={regening || !rSource}>
                {regening && <Spinner color="currentColor" />}
                {regening ? 'Regenerating…' : 'Regenerate'}
              </Button>
            </FooterRow>
        </ModalPanel>
      )}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}
