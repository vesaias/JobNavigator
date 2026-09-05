import React, { useState, useEffect, useCallback, useRef } from 'react'
import { GlyphBadge, Spinner, ToastCard } from './ui'
import './theme.css'

// Toast taxonomy: progress (spinner), success (green check), error (red !,
// stays until dismissed), undo (dark, still-actionable). Stack bottom-right, max 3.
const KINDS = {
  progress: { spin: true },
  // the two marks read palette names (--accent / --bad) via the taxonomy's
  // own semantic names — same values, so nothing repaints.
  success: { mark: '✓', markBg: 'var(--toast-mark-ok)' },
  error: { mark: '!', markBg: 'var(--toast-mark-bad)' },
  undo: {},
}
// 4s for toasts that only report, 5s for undo (asks for a decision), errors
// stay until dismissed.
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
    // show/hide animation is this toast's own mount state; everything else
    // about the box is `ToastCard`'s.
    <ToastCard kind={t.kind} style={{
      opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(10px)',
      transition: 'opacity 250ms ease, transform 250ms ease',
    }}>
      {/* a `progress` card also serves a neutral result ("finished, but…")
          which must not keep spinning; `spin: false` opts that one out */}
      {k.spin && t.spin !== false && <Spinner size={11} color="currentColor" />}
      {/* `tone="none"` because the mark's ground is the taxonomy's own, not
          one of GlyphBadge's tones */}
      {k.mark && (
        <GlyphBadge tone="none" line={1} style={{ flex: '0 0 auto', background: k.markBg, color: 'var(--accent-ink)' }}>{k.mark}</GlyphBadge>
      )}
      <span style={{ minWidth: 0, fontSize: 12.5, lineHeight: 1.45 }}>{t.msg}</span>
      {label && (
        <span onClick={() => { t.onAction?.(); onClose() }}
          style={{ flex: '0 0 auto', fontSize: 12, fontWeight: 600, cursor: 'pointer', borderBottom: '1px dotted currentColor', color: t.kind === 'undo' ? 'var(--rail-accent)' : 'inherit' }}>{label}</span>
      )}
      {/* a tint of the ink stands in for a per-kind dimmed ✕ and survives
          dark mode without four more tokens */}
      <span onClick={onClose} style={{ flex: '0 0 auto', fontSize: 11, cursor: 'pointer', opacity: 0.55 }}>✕</span>
    </ToastCard>
  )
}

// ui: keep — pure layout, no design keys; z-index 80 puts a toast over an open modal (70) and drawer (30)
export function ToastStack({ toasts, onClose }) {
  return (
    <div style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 80, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
      {toasts.map((t) => <Toast key={t.id} t={t} onClose={() => onClose(t.id)} />)}
    </div>
  )
}
