import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Spinner } from './ui'
import './theme.css'

// Toast taxonomy (Toasts.dc.html): one accent per meaning, so a glance from the
// corner of your eye tells you which it is.
//
//   progress — quiet paper card + spinner. Ambient status, not news.         4s
//   success  — green tint, solid ✓ roundel. The only green toast.           4s
//   error    — red tint, ! roundel. Stays until dismissed: a failure
//              that evaporates before you read it may as well not exist.
//   undo     — the one dark toast. Dark means "still actionable", which
//              is why progress must NOT be dark.                            5s
//
// Stack bottom-right, newest at the bottom, at most three visible.
const KINDS = {
  progress: { bg: 'var(--recessed)', bd: 'var(--line)', fg: 'var(--text-2)', spin: true },
  success: { bg: 'var(--toast-ok-bg)', bd: 'var(--toast-ok-line)', fg: 'var(--toast-ok-ink)', mark: '✓', markBg: 'var(--accent)' },
  error: { bg: 'var(--toast-bad-bg)', bd: 'var(--toast-bad-line)', fg: 'var(--toast-bad-ink)', mark: '!', markBg: 'var(--bad)' },
  undo: { bg: 'var(--rail)', bd: 'var(--rail)', fg: 'var(--rail-ink)' },
}
// RES-25: 2.5 s was not long enough to read a success toast, let alone act on the
// "Open ↗" it carries. One 3–5 s band across the app: 4 s for the two that only
// report, 5 s for undo (which asks for a decision), errors until dismissed.
const TTL = { progress: 4000, success: 4000, undo: 5000, error: null }
const MAX = 3

export function useToasts() {
  const [toasts, setToasts] = useState([])
  const timers = useRef([])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const dismiss = useCallback((id) => {
    setToasts((p) => p.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
    timers.current.push(setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 260))
  }, [])

  const push = useCallback((t) => {
    const kind = t.kind || 'progress'
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    setToasts((p) => [...p.slice(-(MAX - 1)), { ...t, kind, id }])
    const ttl = t.ttl !== undefined ? t.ttl : TTL[kind]
    if (ttl) timers.current.push(setTimeout(() => dismiss(id), ttl))
    return id
  }, [dismiss])

  return { toasts, push, dismiss }
}

function Toast({ t, onClose }) {
  const [shown, setShown] = useState(false)
  useEffect(() => { const r = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(r) }, [])
  const vis = shown && !t.leaving
  const k = KINDS[t.kind] || KINDS.progress
  const label = t.action || t.actionLabel
  return (
    // ui: keep — this *is* the toast primitive. D1-D2 files `toast` as "already
    // single" (one site, one signature) and D4f names no `Toast` in ui.jsx, so the
    // card stays where its taxonomy, TTL table and stack live rather than being
    // relocated object-for-object. It is not a ModalPanel (no scrim, no Escape, no
    // dialog role) and not a Surface (four tinted grounds, its own r9 + shadow).
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, maxWidth: 380, padding: '10px 13px',
      background: k.bg, border: `1px solid ${k.bd}`, borderRadius: 9, color: k.fg,
      boxShadow: 'var(--shadow-toast)',
      opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(10px)',
      transition: 'opacity 250ms ease, transform 250ms ease',
    }}>
      {k.spin && <Spinner size={11} color="currentColor" />}
      {/* ui: keep — a 16px filled glyph badge (✓ / ✕ on the toast tint), not a status dot: Dot draws a bare tone disc with no glyph */}
      {k.mark && (
        <span style={{ flex: '0 0 auto', width: 16, height: 16, borderRadius: 99, background: k.markBg, color: 'var(--accent-ink)', fontSize: 9.5, lineHeight: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{k.mark}</span>
      )}
      <span style={{ minWidth: 0, fontSize: 12.5, lineHeight: 1.45 }}>{t.msg}</span>
      {label && (
        <span onClick={() => { t.onAction?.(); onClose() }}
          style={{ flex: '0 0 auto', fontSize: 12, fontWeight: 600, cursor: 'pointer', borderBottom: '1px dotted currentColor', color: t.kind === 'undo' ? 'var(--rail-accent)' : 'inherit' }}>{label}</span>
      )}
      {/* the design gives each kind its own dimmed ✕; a tint of the ink is the
          same thing and survives dark mode without four more tokens */}
      <span onClick={onClose} style={{ flex: '0 0 auto', fontSize: 11, cursor: 'pointer', opacity: 0.55 }}>✕</span>
    </div>
  )
}

// ui: keep — the stack container carries no design keys at all (fixed corner,
// z 80 above every modal, column, gap 8): pure layout, nothing for a primitive
// to own. z-index 80 is what puts a toast over an open modal (70) and drawer (30).
export function ToastStack({ toasts, onClose }) {
  return (
    <div style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 80, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
      {toasts.map((t) => <Toast key={t.id} t={t} onClose={() => onClose(t.id)} />)}
    </div>
  )
}
