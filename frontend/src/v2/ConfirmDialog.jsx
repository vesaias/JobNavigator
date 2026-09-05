import React, { useState } from 'react'
import './theme.css'
import { Button, Heading, Input, ModalPanel } from './ui'

// The one destructive-confirm dialog for v2, so deletes stop falling back to
// window.confirm. Escape and the scrim both cancel; the confirm side never
// auto-focuses, so Enter can't destroy anything by reflex.
export default function ConfirmDialog({ title, body, label, danger, onConfirm, onCancel }) {
  return (
    // ModalPanel carries the scrim, Escape and the pixel snap; it sits at
    // z-index 70, so a confirm raised from a drawer (z 30) or modal still lands on top.
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

// Replaces the `window.prompt` calls left in Settings (reveal the rotated
// webhook secret, ask for the public base URL). `readOnly` turns it into a
// reveal-and-copy panel with a single Done button.
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
