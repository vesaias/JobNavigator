import React, { useState } from 'react'
import './theme.css'
import { Button, CopyGlyph, Heading, Input, ModalPanel } from './ui'

// The one destructive-confirm dialog for v2, so deletes stop falling back to
// window.confirm. Escape and the scrim both cancel; the confirm side never
// auto-focuses, so Enter can't destroy anything by reflex.
export default function ConfirmDialog({ title, body, label, danger, onConfirm, onCancel }) {
  return (
    // ModalPanel carries the scrim, Escape and the pixel snap; it sits at
    // z-index 70, so a confirm raised from a drawer (z 30) or modal still lands on top.
    <ModalPanel width={400} title={title} onClose={onCancel} style={{ padding: '22px 24px 18px', gap: 8 }}>
      {/* round 7 #4: the name moves into the caption bar where a theme draws one,
          and the body heading it duplicates is hidden there. Round 8 #11 dropped
          the `prompt` flag this panel used to pass: a small 98 window wears the
          same full caption as a large one — only its size differs. */}
      <Heading size={19} className="v2-dialogtitle">{title}</Heading>
      {/* round 10 · `v2-dialogtext` is a NAME, like `v2-dialogtitle` above it: it
          computes nothing here, and win98 reads it to put the message on the
          window-text ink at its own UI stop, because a 98 message box's body is
          plain text on the grey face and not a muted helper line. */}
      {body && <span className="v2-dialogtext" style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--helper-ink)' }}>{body}</span>}
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
    <ModalPanel width={440} title={title} onClose={onCancel} style={{ padding: '22px 24px 18px', gap: 8 }}>
      {/* round 7 #4: the name moves into the caption bar where a theme draws one,
          and the body heading it duplicates is hidden there. Round 8 #11: the
          caption is the full one — `_ □ ×`, the first two disabled. */}
      <Heading size={19} className="v2-dialogtitle">{title}</Heading>
      {body && <span className="v2-dialogtext" style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--helper-ink)' }}>{body}</span>}
      <Input value={v} readOnly={readOnly} placeholder={placeholder} autoFocus mono={mono}
        ariaLabel={title} onChange={setV}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onSubmit(v) } }}
        onFocus={(e) => readOnly && e.target.select()}
        style={{ marginTop: 4 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
        {readOnly && <Button variant="secondary" size="sm" onClick={copy}>{copied ? 'Copied ✓' : <><CopyGlyph />Copy</>}</Button>}
        {!readOnly && <Button variant="secondary" size="sm" onClick={onCancel} style={{ marginLeft: 'auto' }}>Cancel</Button>}
        <Button size="sm" onClick={() => onSubmit(v)} style={{ marginLeft: readOnly ? 'auto' : 0 }}>{label || 'OK'}</Button>
      </div>
    </ModalPanel>
  )
}
