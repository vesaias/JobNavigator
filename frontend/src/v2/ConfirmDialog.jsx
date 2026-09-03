import React, { useRef, useState } from 'react'
import './theme.css'
import { useEscape, useSnapTop } from './hooks'
import { Button, Heading, Input } from './ui'

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
        <Heading size={19}>{title}</Heading>
        {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>{body}</span>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
          <Button variant="secondary" size="sm" onClick={onCancel}>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} size="sm" onClick={onConfirm}>{label || 'Confirm'}</Button>
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
        <Heading size={19}>{title}</Heading>
        {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>{body}</span>}
        <Input value={v} readOnly={readOnly} placeholder={placeholder} autoFocus mono={mono}
          ariaLabel={title} onChange={setV}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onSubmit(v) } }}
          onFocus={(e) => readOnly && e.target.select()}
          style={{ marginTop: 4 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
          {readOnly && <Button variant="secondary" size="sm" onClick={copy}>{copied ? 'Copied ✓' : '⧉ Copy'}</Button>}
          {!readOnly && <Button variant="secondary" size="sm" onClick={onCancel} style={{ marginLeft: 'auto' }}>Cancel</Button>}
          <Button size="sm" onClick={() => onSubmit(v)} style={{ marginLeft: readOnly ? 'auto' : 0 }}>{label || 'OK'}</Button>
        </div>
      </div>
    </div>
  )
}
