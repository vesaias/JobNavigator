import React, { useState, useEffect, useCallback, useRef } from 'react'
import './theme.css'

// Toast taxonomy (Toasts.dc.html): one accent per meaning, so a glance from the
// corner of your eye tells you which it is.
//
//   progress — quiet paper card + spinner. Ambient status, not news.       2.5s
//   success  — green tint, solid ✓ roundel. The only green toast.         2.5s
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
const TTL = { progress: 2500, success: 2500, undo: 5000, error: null }
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
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, maxWidth: 380, padding: '10px 13px',
      background: k.bg, border: `1px solid ${k.bd}`, borderRadius: 9, color: k.fg,
      boxShadow: '0 8px 24px rgba(20,19,15,.18)',
      opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(10px)',
      transition: 'opacity 250ms ease, transform 250ms ease',
    }}>
      {k.spin && <span className="v2-spin" style={{ flex: '0 0 auto', width: 11, height: 11, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
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

export function ToastStack({ toasts, onClose }) {
  return (
    <div style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 80, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
      {toasts.map((t) => <Toast key={t.id} t={t} onClose={() => onClose(t.id)} />)}
    </div>
  )
}
