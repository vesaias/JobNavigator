import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Spinner, ToastCard } from './ui'
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
// The card's ground/edge/ink per kind now live on ui.jsx's `ToastCard`
// (--toast-{progress,ok,bad,undo}-bg/-line/-ink, the same values this table held);
// what stays here is what the taxonomy owns: whether the card spins, and the
// glyph roundel it carries.
const KINDS = {
  progress: { spin: true },
  success: { mark: '✓', markBg: 'var(--accent)' },
  error: { mark: '!', markBg: 'var(--bad)' },
  undo: {},
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
    // the show/hide animation stays at the site: it is this toast's own mount
    // state, not design. Everything else about the box is `ToastCard`'s.
    <ToastCard kind={t.kind} style={{
      opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(10px)',
      transition: 'opacity 250ms ease, transform 250ms ease',
    }}>
      {/* DS-B-02: a `progress` card is also the quiet ground for a neutral
          *result* ("finished, but …"), which must not keep spinning. `spin: false`
          on the toast opts that one card out; nothing else changes. */}
      {k.spin && t.spin !== false && <Spinner size={11} color="currentColor" />}
      {/* ui: keep — a 16px filled glyph badge (✓ / ✕ on the toast tint), not a status dot: Dot draws a bare tone disc with no glyph */}
      {k.mark && (
        <span style={{ flex: '0 0 auto', width: 16, height: 16, borderRadius: 'var(--radius-control)', background: k.markBg, color: 'var(--accent-ink)', fontSize: 9.5, lineHeight: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{k.mark}</span>
      )}
      <span style={{ minWidth: 0, fontSize: 12.5, lineHeight: 1.45 }}>{t.msg}</span>
      {label && (
        <span onClick={() => { t.onAction?.(); onClose() }}
          style={{ flex: '0 0 auto', fontSize: 12, fontWeight: 600, cursor: 'pointer', borderBottom: '1px dotted currentColor', color: t.kind === 'undo' ? 'var(--rail-accent)' : 'inherit' }}>{label}</span>
      )}
      {/* the design gives each kind its own dimmed ✕; a tint of the ink is the
          same thing and survives dark mode without four more tokens */}
      <span onClick={onClose} style={{ flex: '0 0 auto', fontSize: 11, cursor: 'pointer', opacity: 0.55 }}>✕</span>
    </ToastCard>
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
