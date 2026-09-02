import React from 'react'
import './theme.css'
import { useEscape } from './hooks'

// RES-16: the one destructive-confirm dialog for v2. Lifted out of Companies.jsx
// (COMP-28) so the résumé and cover-letter deletes stop falling back to
// window.confirm — a native dialog on a screen that owns a modal system.
// Escape and the scrim both cancel; the confirm side never auto-focuses, so
// Enter can't destroy anything by reflex.
export default function ConfirmDialog({ title, body, label, danger, onConfirm, onCancel }) {
  useEscape(onCancel)
  return (
    <div onClick={onCancel} style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 400, background: 'var(--recessed)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', padding: '22px 24px 18px', display: 'flex', flexDirection: 'column', gap: 8 }}>
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
