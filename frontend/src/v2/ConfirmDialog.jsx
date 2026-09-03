import React, { useRef, useState } from 'react'
import './theme.css'
import { useEscape, useSnapTop } from './hooks'

// RES-16: the one destructive-confirm dialog for v2. Lifted out of Companies.jsx
// (COMP-28) so the résumé and cover-letter deletes stop falling back to
// window.confirm — a native dialog on a screen that owns a modal system.
// Escape and the scrim both cancel; the confirm side never auto-focuses, so
// Enter can't destroy anything by reflex.
export default function ConfirmDialog({ title, body, label, danger, onConfirm, onCancel }) {
  useEscape(onCancel)
  const panel = useRef(null)
  useSnapTop(panel)   // RES-32
  return (
    <div onClick={onCancel} style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70 }}>
      <div ref={panel} onClick={(e) => e.stopPropagation()} style={{ width: 400, background: 'var(--recessed)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', padding: '22px 24px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em', lineHeight: '26px' }}>{title}</span>
        {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>{body}</span>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
          <div onClick={onCancel} className="v2-bdc v2-ctl" style={{ height: 31, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
          <div onClick={onConfirm} className="v2-ctl" style={{ height: 31, padding: '0 16px', borderRadius: 99, background: danger ? 'var(--bad)' : 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>{label || 'Confirm'}</div>
        </div>
      </div>
    </div>
  )
}

// R2-A-01's sibling: the two `window.prompt` calls left in Settings (reveal the
// rotated webhook secret, ask for the public base URL) are the same interaction
// rendered by the browser. Same card, same Escape/scrim rules; `readOnly` turns
// it into a reveal-and-copy panel with a single Done button.
export function PromptDialog({ title, body, label, value, placeholder, readOnly, mono, onSubmit, onCancel }) {
  useEscape(onCancel)
  const panel = useRef(null)
  useSnapTop(panel)   // RES-32
  const [v, setV] = useState(value || '')
  const [copied, setCopied] = useState(false)
  const copy = () => { try { navigator.clipboard.writeText(v); setCopied(true) } catch { /* silent: clipboard blocked — the value is selectable in the field */ } }
  return (
    <div onClick={onCancel} style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70 }}>
      <div ref={panel} onClick={(e) => e.stopPropagation()} style={{ width: 440, background: 'var(--recessed)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', padding: '22px 24px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em', lineHeight: '26px' }}>{title}</span>
        {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>{body}</span>}
        <input value={v} readOnly={readOnly} placeholder={placeholder} autoFocus
          onChange={(e) => setV(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onSubmit(v) } }}
          onFocus={(e) => readOnly && e.target.select()}
          style={{ height: 33, marginTop: 4, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 8, background: 'var(--surface)', color: 'var(--text)', fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5, outline: 'none' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
          {readOnly && <div onClick={copy} className="v2-bdc v2-ctl" style={{ height: 31, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: copied ? 'var(--accent)' : 'var(--text-2)', cursor: 'pointer' }}>{copied ? 'Copied ✓' : '⧉ Copy'}</div>}
          {!readOnly && <div onClick={onCancel} className="v2-bdc v2-ctl" style={{ marginLeft: 'auto', height: 31, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>}
          <div onClick={() => onSubmit(v)} className="v2-ctl" style={{ marginLeft: readOnly ? 'auto' : 0, height: 31, padding: '0 16px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: 'pointer' }}>{label || 'OK'}</div>
        </div>
      </div>
    </div>
  )
}
