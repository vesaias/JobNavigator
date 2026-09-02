import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToasts, ToastStack } from './Toast'
import api from '../api'
import { Picker, VoicePicker, LengthPicker, LENGTHS, STAGE_CLASS } from './CoverLetters'
import ConfirmDialog from './ConfirmDialog'
import { useEscape } from './hooks'
// the undo-removal helper and the band rule are shared with the résumé editors
import { useUndoRemove, BandRule } from './ResumeSections'
import './theme.css'
import { useTitle } from '../useTitle'

const EMPTY = {
  header: { name: '', contact_items: [] },
  recipient: { company: '', manager: '', address: '' },
  date: '', greeting: 'Dear Hiring Team,', body_paragraphs: [''], closing: 'Sincerely,', signature: '',
}
const PAGE_FORMATS = [['letter', 'US Letter'], ['a4', 'A4']]
const UI_KEY = 'v2_cl_sections'
const loadUI = () => { try { return JSON.parse(localStorage.getItem(UI_KEY)) || {} } catch { return {} } }

import { ago } from './time'

const FLABEL = { fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }
// Contact-item cells are 1:1 with the Résumé editor's header (cellInput there)
const CELL = {
  width: '100%', height: 29, padding: '0 9px', border: '1px solid var(--edge)', borderRadius: 6,
  background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, outline: 'none', fontFamily: 'var(--sans)',
}
const INPUT = {
  height: 32, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 6,
  background: 'var(--surface)', fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--text)', outline: 'none',
}

// A collapsible editor card — the three sections of the letter.
function Card({ title, note, open, onToggle, children }) {
  return (
    <div style={{ border: '1px solid var(--line)', borderRadius: 9, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
      <div onClick={onToggle} className="v2-clhead" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', cursor: 'pointer', borderRadius: '9px 9px 0 0' }}>
        <span style={{ flex: '0 0 auto', width: 10, height: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
          <svg width="8" height="8" viewBox="0 0 10 10" aria-hidden="true"
            style={{ display: 'block', transform: open ? 'none' : 'rotate(-90deg)', transition: 'transform .12s' }}>
            <path d="M2 4 L5 7 L8 4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', gap: 9 }}>
          <span style={{ flex: '0 0 auto', fontSize: 13, lineHeight: '20px', fontWeight: 600 }}>{title}</span>
          {note && <span style={{ flex: '0 1 auto', fontSize: 11.5, lineHeight: '20px', color: 'var(--muted)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{note}</span>}
        </span>
      </div>
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '2px 14px 14px', borderTop: '1px solid var(--line-soft)' }}>
          {children}
        </div>
      )}
    </div>
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

  useEffect(() => {
    api.get('/cover-letters/templates').then(({ data }) => setTemplates(data || [])).catch(() => {})
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
    api.get('/settings').then(({ data }) => {
      let p = data.cover_letter_voice_presets
      if (typeof p === 'string') { try { p = JSON.parse(p) } catch { p = [] } }
      setPresets(Array.isArray(p) ? p : [])
      setRVoice((v) => v || data.cover_letter_default_voice || '')
    }).catch(() => {})
  }, [])

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
      try { await api.patch(`/cover-letters/${id}`, body); setSavedAt(new Date().toISOString()); setErr('') }
      catch (e) { console.error(e); setErr('Could not save — your last edit is not stored.'); pushToast({ kind: 'error', msg: 'Could not save — your last edit is not stored.' }) }
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
    } catch (e) { console.error(e); setErr('Could not download the PDF.'); pushToast({ kind: 'error', msg: 'Could not download the PDF.' }) }
  }

  const remove = () => {
    setMenuOpen(false)
    setConfirm({
      title: `Delete "${doc?.name}"?`, body: 'This cannot be undone.', label: 'Delete', danger: true,
      onConfirm: async () => {
        setConfirm(null)
        try { await api.delete(`/cover-letters/${id}`); window.dispatchEvent(new CustomEvent('jn:counts-changed')); navigate('/v2/cover-letters') }   // CL-17
        catch (e) { console.error(e); setErr('Could not delete this letter.'); pushToast({ kind: 'error', msg: 'Could not delete this letter.' }) }
      },
    })
  }

  const regenerate = async () => {
    if (regening || !rSource) return
    setRegening(true); setErr('')
    try {
      await api.post('/cover-letters/generate', {
        resume_id: rSource, job_id: doc.job_id, voice: rVoice, length: rLength,
        cover_letter_id: id,       // rewrite this draft in place
      })
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
  }, [regening, id])

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
  useEscape(() => setRegenOpen(false), regenOpen && !regening)

  const sourceOpts = useMemo(() => [
    ...(personaAvailable ? [{ id: 'persona', label: 'Persona (full profile)' }] : []),
    ...resumes.map((r) => ({ id: r.id, label: r.name })),
  ], [resumes, personaAvailable])

  if (!doc) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, color: 'var(--muted)', fontSize: 13 }}>
        <span>{err || 'Loading…'}</span>
        {err && <span style={{ display: 'flex', gap: 14 }}>
          <span onClick={() => navigate('/v2/cover-letters')} className="v2-anchor" style={{ color: 'var(--accent)', cursor: 'pointer' }}>‹ Back to cover letters</span>
          {!/no longer exists/.test(err) && <span onClick={() => window.location.reload()} className="v2-anchor" style={{ color: 'var(--accent)', cursor: 'pointer' }}>Try again</span>}
        </span>}
      </div>
    )
  }

  const paras = data.body_paragraphs || []
  const stage = doc.stage
  const badge = stage ? stage.toUpperCase() : 'DRAFT'
  const voiceLabel = presets.find((p) => p.id === doc.voice)?.label || doc.voice
  const lengthLabel = LENGTHS.find(([lid]) => lid === doc.length)?.[1] || doc.length
  const voiceLen = [voiceLabel, lengthLabel].filter(Boolean).join(' · ') || 'voice and length not recorded'
  const tplLabel = templates.find((t) => t.id === template)?.name || template || 'Template'
  const fmtLabel = PAGE_FORMATS.find(([f]) => f === format)?.[1] || format

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* top bar */}
      <div style={{ flex: '0 0 auto', padding: '10px 24px', background: 'var(--surface)', borderBottom: '1px solid var(--line-soft)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span onClick={() => navigate('/v2/cover-letters')} className="v2-ctl" style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>‹ Cover Letters</span>
        <span style={{ color: 'var(--line)' }}>|</span>
        <span className={stage ? (STAGE_CLASS[stage] || 'cc-generic') : 'cc-generic'}
          style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99 }}>{badge}</span>
        <span title={doc.name} style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 420 }}>{doc.name}</span>
        <span style={{ marginLeft: 'auto', flex: '0 0 auto', fontSize: 11.5, color: err ? 'var(--bad)' : 'var(--muted)' }}>
          {err || (savedAt ? `saved ${ago(savedAt)} · autosaves` : 'autosaves')}
        </span>
      </div>

      {/* context band */}
      <div style={{ flex: '0 0 auto', background: 'var(--surface-2)', borderBottom: '1px solid var(--line)', padding: '9px 24px', display: 'flex', alignItems: 'center', gap: 13 }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ minWidth: 0, fontSize: 12.5, lineHeight: '18px', fontWeight: 500, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Written for <span style={{ color: 'var(--text)' }}>{doc.company ? `${doc.company} — ${doc.title}` : doc.name}</span>
            {doc.source_name && <><BandRule />from <span onClick={() => doc.resume_id && navigate(`/v2/resumes/${doc.resume_id}`)}
              title={doc.resume_id ? 'Open the source résumé' : 'Written from your Persona'}
              style={{ color: 'var(--accent)', cursor: doc.resume_id ? 'pointer' : 'default' }}>{doc.source_name}{doc.resume_id ? ' ↗' : ''}</span></>}
          </span>
          <span style={{ fontSize: 11, lineHeight: '17px', color: 'var(--muted)' }}>{voiceLen}</span>
        </div>
        <div onClick={() => { setRegenOpen(true); setMenuOpen(false) }} title="Rewrite the letter — pick base résumé, voice and length"
          className="v2-ctl" style={{ flex: '0 0 auto', height: 36, padding: '0 19px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>
          {regening
            ? <span className="v2-spin" style={{ width: 11, height: 11, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />
            : <span style={{ fontSize: 12 }}>↻</span>}
          Regenerate…
        </div>
        <div style={{ position: 'relative', flex: '0 0 auto' }} onClick={(e) => e.stopPropagation()}>
          <div onClick={() => setMenuOpen((v) => !v)} title="More actions"
            style={{ width: 36, height: 36, border: `1px solid ${menuOpen ? 'var(--accent)' : 'var(--edge)'}`, background: menuOpen ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, color: 'var(--text-2)', cursor: 'pointer' }}>⋯</div>
          {menuOpen && (
            <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 5, width: 224, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)', zIndex: 50, padding: 5, display: 'flex', flexDirection: 'column' }}>
              {doc.has_application && (
                <div onClick={() => { setMenuOpen(false); navigate('/v2/applications') }} className="v2-menuitem"
                  style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
                  <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>▤</span><span style={{ flex: 1 }}>View application</span>
                </div>
              )}
              {doc.job_id && (
                <div onClick={() => { setMenuOpen(false); navigate(`/v2/feed?job=${doc.job_id}`) }} className="v2-menuitem"
                  style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
                  <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>☰</span><span style={{ flex: 1 }}>View job in feed</span>
                </div>
              )}
              {doc.job_url && (
                <a href={doc.job_url} target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)} className="v2-menuitem"
                  style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer', textDecoration: 'none' }}>
                  <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>↗</span><span style={{ flex: 1 }}>Open job posting</span>
                </a>
              )}
              <div onClick={remove} className="v2-hover-bad"
                style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 13, color: 'var(--bad)', cursor: 'pointer', marginTop: 3, borderTop: '1px solid var(--line-soft)' }}>
                <span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11 }}>✕</span><span style={{ flex: 1 }}>Delete letter</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* split body */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <section className="v2-scroll" style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '14px 20px 24px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>

          <Card title="Header" open={headOpen} onToggle={() => setHeadOpen((v) => !v)}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 10 }}>
              <span style={FLABEL}>Full name</span>
              <input value={data.header?.name || ''} onChange={(e) => update((d) => { d.header = d.header || {}; d.header.name = e.target.value })} style={INPUT} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={FLABEL}>Contact items</span>
                {/* integer line-height: at 1.5 this 10.5px hint is 15.75 tall and
                    pushes every card below onto a half pixel (borders drop out) */}
                <span style={{ marginLeft: 'auto', fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)' }}>text · link · stub</span>
              </div>
              {(data.header?.contact_items || []).map((ct, i, arr) => {
                const tracked = ct.url && !String(ct.url).startsWith('mailto:')
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ flex: '45 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* controls + text: 45 % of the row */}
                    <span style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1, color: 'var(--muted)', fontSize: 8 }}>
                      <span onClick={() => i > 0 && update((d) => { const a = d.header.contact_items; [a[i - 1], a[i]] = [a[i], a[i - 1]] })}
                        title="Move up" className={i > 0 ? 'v2-hover-accent-text' : ''} style={{ cursor: i > 0 ? 'pointer' : 'default', opacity: i > 0 ? 1 : 0.35 }}>▲</span>
                      <span onClick={() => i < arr.length - 1 && update((d) => { const a = d.header.contact_items; [a[i + 1], a[i]] = [a[i], a[i + 1]] })}
                        title="Move down" className={i < arr.length - 1 ? 'v2-hover-accent-text' : ''} style={{ cursor: i < arr.length - 1 ? 'pointer' : 'default', opacity: i < arr.length - 1 ? 1 : 0.35 }}>▼</span>
                    </span>
                    <input value={ct.text || ''} placeholder="Display text" onChange={(e) => update((d) => { d.header.contact_items[i].text = e.target.value })}
                      style={{ ...CELL, flex: 1, minWidth: 0 }} />
                    </div>
                    <div style={{ flex: '55 1 0', minWidth: 0, display: 'flex', alignItems: 'center', gap: 6 }}>   {/* url + stub: 55 % */}
                    <input value={ct.url || ''} placeholder="URL (optional)" onChange={(e) => update((d) => { d.header.contact_items[i].url = e.target.value })}
                      style={{ ...CELL, flex: 1, fontSize: 11.5, color: 'var(--text-2)', minWidth: 0 }} />
                    {tracked && (
                      <input value={ct.stub || ''} placeholder="id" title="Short stub for the tracer link id (e.g. l, w, gh)"
                        onChange={(e) => update((d) => { d.header.contact_items[i].stub = e.target.value })}
                        style={{ ...CELL, flex: '0 0 34px', padding: '0 6px', fontFamily: 'var(--mono)', fontSize: 11, textAlign: 'center', minWidth: 0 }} />
                    )}
                    <span onClick={() => update((d) => { d.header.contact_items.splice(i, 1) })} title="Remove"
                      className="v2-hover-bad-text" style={{ flex: '0 0 auto', color: 'var(--muted)', fontSize: 11, cursor: 'pointer' }}>✕</span>
                    </div>
                  </div>
                )
              })}
              <div onClick={() => update((d) => { d.header = d.header || {}; d.header.contact_items = [...(d.header.contact_items || []), { text: '', url: '' }] })}
                className="v2-dashadd" style={{ height: 28, border: '1px dashed var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>+ Add contact item</div>
            </div>
          </Card>

          <Card title="Recipient" note={[data.recipient?.company, data.date].filter(Boolean).join(' · ')}
            open={recipOpen} onToggle={() => setRecipOpen((v) => !v)}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, paddingTop: 10 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Company</span>
                <input value={data.recipient?.company || ''} onChange={(e) => update((d) => { d.recipient = d.recipient || {}; d.recipient.company = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Date</span>
                <input value={data.date || ''} onChange={(e) => update((d) => { d.date = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Hiring manager</span>
                <input value={data.recipient?.manager || ''} placeholder="Unknown" onChange={(e) => update((d) => { d.recipient = d.recipient || {}; d.recipient.manager = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Address</span>
                <input value={data.recipient?.address || ''} placeholder="—" onChange={(e) => update((d) => { d.recipient = d.recipient || {}; d.recipient.address = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
            </div>
          </Card>

          <Card title="Letter" note={`${paras.length} paragraph${paras.length === 1 ? '' : 's'}`}
            open={letterOpen} onToggle={() => setLetterOpen((v) => !v)}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, paddingTop: 10 }}>
              <span style={FLABEL}>Greeting</span>
              <input value={data.greeting || ''} onChange={(e) => update((d) => { d.greeting = e.target.value })} style={INPUT} />
            </div>
            {paras.map((text, i) => (
              <div key={i} style={{ border: '1px solid var(--edge)', borderRadius: 6, background: 'var(--surface)', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '7px 10px 0' }}>
                  <span style={{ fontSize: 10, letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--edge)' }}>¶ {i + 1}</span>
                  <span onClick={() => i > 0 && update((d) => { const a = d.body_paragraphs; [a[i - 1], a[i]] = [a[i], a[i - 1]] })} title="Move up" className={i > 0 ? 'v2-parabtn' : ''}
                    style={{ marginLeft: 'auto', width: 20, height: 20, borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: i === 0 ? 'var(--line-strong)' : 'var(--text-2)', cursor: i === 0 ? 'default' : 'pointer' }}>↑</span>
                  <span onClick={() => i < paras.length - 1 && update((d) => { const a = d.body_paragraphs; [a[i + 1], a[i]] = [a[i], a[i + 1]] })} title="Move down" className={i < paras.length - 1 ? 'v2-parabtn' : ''}
                    style={{ width: 20, height: 20, borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: i === paras.length - 1 ? 'var(--line-strong)' : 'var(--text-2)', cursor: i === paras.length - 1 ? 'default' : 'pointer' }}>↓</span>
                  <span onClick={() => undoRemove('Removed paragraph',
                    (d) => { d.body_paragraphs.splice(i, 1) },
                    (d) => { d.body_paragraphs = d.body_paragraphs || []; d.body_paragraphs.splice(i, 0, text) })} title="Delete paragraph" className="v2-parabtn-bad"
                    style={{ width: 20, height: 20, borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--edge)', cursor: 'pointer' }}>✕</span>
                </div>
                <textarea value={text} rows={4} onChange={(e) => update((d) => { d.body_paragraphs[i] = e.target.value })}
                  style={{ margin: '4px 10px 9px', border: 'none', background: 'transparent', fontFamily: 'var(--sans)', fontSize: 12.5, lineHeight: '19px', color: 'var(--text)', outline: 'none', resize: 'none' }} />
              </div>
            ))}
            <div onClick={() => update((d) => { d.body_paragraphs = [...(d.body_paragraphs || []), ''] })} className="v2-dashadd"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, height: 28, border: '1px dashed var(--edge)', borderRadius: 6, fontSize: 11.5, color: 'var(--accent)', cursor: 'pointer' }}>+ Add paragraph</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Closing</span>
                <input value={data.closing || ''} onChange={(e) => update((d) => { d.closing = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                <span style={FLABEL}>Signature</span>
                <input value={data.signature || ''} onChange={(e) => update((d) => { d.signature = e.target.value })} style={{ ...INPUT, minWidth: 0 }} />
              </div>
            </div>
          </Card>
        </section>

        {/* preview */}
        <section style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface-2)', minHeight: 0 }}>
          <div style={{ flex: '0 0 auto', padding: '8px 20px', display: 'flex', flexWrap: 'wrap', rowGap: 6, alignItems: 'center', gap: 9, borderBottom: '1px solid var(--line)' }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>PDF preview</span>
            {pdfBusy && <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--edge)', borderTopColor: 'transparent', borderRadius: 99 }} />}

            <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
              <span onClick={() => { setTplOpen((v) => !v); setFmtOpen(false) }} title="Cover letter template" className="v2-bd v2-ctl"
                style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}>
                <span style={{ color: 'var(--muted)' }}>Template</span><span style={{ color: 'var(--text)' }}>{tplLabel}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span>
              </span>
              {tplOpen && (
                <div className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, width: 210, maxHeight: 300, overflow: 'auto', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)', padding: 5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {templates.map((t) => (
                    <div key={t.id} onClick={() => pickTemplate(t.id)} className="v2-menuitem" title={t.description || ''}
                      style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: t.id === template ? 'var(--accent)' : 'var(--text-2)', background: t.id === template ? 'var(--accent-soft)' : 'transparent' }}>{t.name}</div>
                  ))}
                </div>
              )}
            </span>

            <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
              <span onClick={() => { setFmtOpen((v) => !v); setTplOpen(false) }} title="Paper size — US Letter or A4" className="v2-bd v2-ctl"
                style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}>
                <span style={{ color: 'var(--muted)' }}>Paper</span><span style={{ color: 'var(--text)' }}>{fmtLabel}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span>
              </span>
              {fmtOpen && (
                <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, width: 130, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)', padding: 5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {PAGE_FORMATS.map(([f, label]) => (
                    <div key={f} onClick={() => pickFormat(f)} className="v2-menuitem"
                      style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: f === format ? 'var(--accent)' : 'var(--text-2)', background: f === format ? 'var(--accent-soft)' : 'transparent' }}>{label}</div>
                  ))}
                </div>
              )}
            </span>

            {pdfErr && <span style={{ fontSize: 11, lineHeight: '14px', color: 'var(--bad)', whiteSpace: 'nowrap' }}>Preview failed — showing the last render · <span onClick={() => setPdfNonce((n) => n + 1)} style={{ cursor: 'pointer', borderBottom: '1px dotted currentColor' }}>Retry</span></span>}
            <div onClick={download} className="v2-ctl" style={{ marginLeft: 'auto', flex: '0 0 auto', height: 29, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 500, cursor: 'pointer', whiteSpace: 'nowrap' }}>↓ Download PDF</div>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {pdfUrl
              ? <iframe title="cover letter preview" src={`${pdfUrl}#view=FitH`} style={{ width: '100%', height: '100%', border: 'none' }} />
              : <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12.5, color: 'var(--muted)' }}>Rendering the preview…</div>}
          </div>
        </section>
      </div>

      {regenOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={() => !regening && setRegenOpen(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 460, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ flex: '0 0 auto', padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Regenerate letter</span>
              <span style={{ fontSize: 11.5, color: 'var(--muted)', textWrap: 'pretty' }}>
                Rewrites the whole letter for {doc.company || 'this role'} — your edits to this draft are replaced.
              </span>
            </div>
            <div style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 13 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{ ...FLABEL, letterSpacing: '.14em' }}>From résumé</span>
                <Picker value={rSource} options={sourceOpts} placeholder="Select a source…" onPick={setRSource} />
                <span style={{ fontSize: 10.5, color: 'var(--muted)', textWrap: 'pretty' }}>Bases and Persona — switch to draw on different achievements.</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{ ...FLABEL, letterSpacing: '.14em' }}>Voice</span>
                <VoicePicker presets={presets} value={rVoice} onPick={setRVoice} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{ ...FLABEL, letterSpacing: '.14em' }}>Length</span>
                <LengthPicker value={rLength} onPick={setRLength} />
              </div>
            </div>
            <div style={{ flex: '0 0 auto', padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
              {err && !regening ? <span style={{ fontSize: 11.5, color: 'var(--bad)' }}>{err}</span> : <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>~30 seconds</span>}   {/* CL-14 */}
              <div onClick={() => !regening && setRegenOpen(false)} style={{ marginLeft: 'auto', height: 33, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
              {/* RES-17: a disabled primary pill is --line on --muted across the three
                  builders — a dimmed accent still reads as the live button. */}
              <div onClick={regenerate} className="v2-ctl" style={{ height: 33, padding: '0 17px', borderRadius: 99, background: regening || !rSource ? 'var(--line)' : 'var(--accent)', color: regening || !rSource ? 'var(--muted)' : 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 500, cursor: regening || !rSource ? 'default' : 'pointer' }}>
                {regening && <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
                {regening ? 'Regenerating…' : 'Regenerate'}
              </div>
            </div>
          </div>
        </div>
      )}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}
