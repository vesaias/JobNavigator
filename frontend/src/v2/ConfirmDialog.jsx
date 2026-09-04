import React, { useState } from 'react'
import './theme.css'
import { Button, Heading, Input, ModalPanel } from './ui'

// RES-16: the one destructive-confirm dialog for v2. Lifted out of Companies.jsx
// (COMP-28) so the résumé and cover-letter deletes stop falling back to
// window.confirm — a native dialog on a screen that owns a modal system.
// Escape and the scrim both cancel; the confirm side never auto-focuses, so
// Enter can't destroy anything by reflex.
// U-16 / handoff §4.11: both dialogs' body lines read the PALETTE name --muted;
// they are helper prose, so they read --helper-ink, which points at --muted.
// Same value, no repaint — the raw 12.5px step stays (U-16's other half).
export default function ConfirmDialog({ title, body, label, danger, onConfirm, onCancel }) {
  return (
    // ModalPanel carries the scrim, Escape (RES-15) and the pixel snap (RES-32).
    // It also sits at z-index 70, the same layer the hand-written panel used, so a
    // confirm raised from inside a drawer (z 30) or another modal still lands on
    // top — it mounts last in the tree, and equal z-index resolves in DOM order.
    <ModalPanel width={400} onClose={onCancel} style={{ padding: '22px 24px 18px', gap: 8 }}>
      <Heading size={19}>{title}</Heading>
      {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--helper-ink)' }}>{body}</span>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
        <Button variant="secondary" size="sm" onClick={onCancel}>Cancel</Button>
        <Button variant={danger ? 'danger' : 'primary'} size="sm" onClick={onConfirm}>{label || 'Confirm'}</Button>
      </div>
    </ModalPanel>
  )
}

// R2-A-01's sibling: the two `window.prompt` calls left in Settings (reveal the
// rotated webhook secret, ask for the public base URL) are the same interaction
// rendered by the browser. Same card, same Escape/scrim rules; `readOnly` turns
// it into a reveal-and-copy panel with a single Done button.
export function PromptDialog({ title, body, label, value, placeholder, readOnly, mono, onSubmit, onCancel }) {
  const [v, setV] = useState(value || '')
  const [copied, setCopied] = useState(false)
  const copy = () => { try { navigator.clipboard.writeText(v); setCopied(true) } catch { /* silent: clipboard blocked — the value is selectable in the field */ } }
  return (
    <ModalPanel width={440} onClose={onCancel} style={{ padding: '22px 24px 18px', gap: 8 }}>
      <Heading size={19}>{title}</Heading>
      {body && <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--helper-ink)' }}>{body}</span>}
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
    </ModalPanel>
  )
}
