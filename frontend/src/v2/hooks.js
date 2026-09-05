import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import api from '../api'

// Small cross-screen hooks. Kept out of Toast.jsx so a screen can take the
// Escape handling without also pulling in the toast host.

// Escape closes v2 modals from one place. Ignores events another handler
// already claimed, so an inner dropdown/menu can swallow Escape without closing everything above it.
//
// `capture` is for the two overlays that mount OUTSIDE the v2 shell (Welcome,
// sign-in) and therefore sit above every screen: document-level listeners run in
// registration order, and the screen behind mounts first, so a bubble-phase
// listener there loses the key to whatever the screen registered — and to the
// preventDefault() above. A capture-phase listener runs before all of them and
// stops the event dead, so the topmost overlay wins (R4-E2E-01).
export function useEscape(onClose, active = true, capture = false) {
  const cb = useRef(onClose) // ref so an inline arrow doesn't re-register the listener every render
  cb.current = onClose
  useEffect(() => {
    if (!active) return undefined
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      e.preventDefault()
      if (capture) e.stopPropagation()   // nothing underneath closes with us
      cb.current?.()
    }
    document.addEventListener('keydown', onKey, capture)
    return () => document.removeEventListener('keydown', onKey, capture)
  }, [active, capture])
}

// Nudges a flex-centred modal panel whose fractional top blurs 1px borders back
// onto the pixel grid, via a paint-time translateY; re-runs after every render and on resize.
export function useSnapTop(ref) {
  useLayoutEffect(() => {
    let busy = false
    const snap = () => {
      const el = ref.current
      if (!el || busy) return
      busy = true                       // a resize during the reflow below must not re-enter
      try {
        // clear the transform first so the reading isn't the already-corrected position
        el.style.transform = ''
        const delta = (() => {
          const top = el.getBoundingClientRect().top
          return Math.round(top) - top
        })()
        el.style.transform = delta ? `translateY(${delta}px)` : ''
      } finally { busy = false }
    }
    snap()
    window.addEventListener('resize', snap)
    return () => window.removeEventListener('resize', snap)
  })
}

// ── initial load: settle once, then paint ───────────────────────────────────
// Settles every loader once (avoids a per-fetch render jump) before revealing data-dependent chrome.
// `loaders` is read from a ref, so only a `key` change re-runs them; no spinner since the wait is short.
export function useSettled(loaders, key = '') {
  const ref = useRef(loaders)
  ref.current = loaders
  // readiness is derived during render (not in an effect) so a key change goes
  // stale immediately — one frame later, the previous document's numbers would still paint.
  const [done, setDone] = useState(null)
  useEffect(() => {
    let alive = true
    const list = (typeof ref.current === 'function' ? ref.current() : ref.current) || []
    Promise.allSettled(list.map((l) => (typeof l === 'function' ? l() : l)))
      .then((rs) => { if (alive) setDone({ key, data: rs.map((r) => (r.status === 'fulfilled' ? r.value : undefined)) }) })
    return () => { alive = false }
  }, [key])
  const ready = done !== null && done.key === key
  return { ready, data: ready ? done.data : [] }
}

// ── warm start ──────────────────────────────────────────────────────────────
// Caches parts of a screen that don't change between refreshes so they paint immediately,
// then reconciles silently when live data settles, cross-fading (.15s) like a rail badge.
const WARM_NS = 'jobnavigator_v2_warm:'
export const NBSP = '\u00A0'
// The count line's "we don't know" mark. NBSP is the *loading* state (the shell
// holds its box); a load that FAILED says so with an em dash rather than
// asserting zeroes next to an error message (R4-T2A-08).
export const DASH = '\u2014'
const readWarm = (screen) => {
  try {
    const v = JSON.parse(localStorage.getItem(WARM_NS + screen) || 'null')
    return v && typeof v === 'object' ? v : null
  } catch { return null }
}
// `ok` is the load's own verdict: a settled-but-FAILED load carries zeroes, and
// writing those to the cache made the next visit open by asserting "0 bases · 0
// tailored copies" (R4-T2B-03). A failed load neither writes the cache nor hands
// back a snapshot — callers render `—` from a null `warm` instead of zeroes.
export function useWarm(screen, live, ready, ok = true) {
  const [boot] = useState(() => readWarm(screen))
  const [fade, setFade] = useState(false)
  const raf = useRef([])
  const last = useRef(boot === null ? null : JSON.stringify(boot))
  useEffect(() => () => { raf.current.forEach((id) => cancelAnimationFrame(id)) }, [])
  const json = ready && ok && live != null ? JSON.stringify(live) : null
  useEffect(() => {
    if (json === null || json === last.current) return   // the cache was right: no render, no fade
    const warmed = last.current !== null                 // nothing to cross-fade from on a first visit
    last.current = json
    try { localStorage.setItem(WARM_NS + screen, json) } catch { /* ignore */ }
    if (!warmed) return
    raf.current.forEach((id) => cancelAnimationFrame(id)); raf.current = []
    setFade(true)
    // two frames: the first guarantees a painted frame at .6, the second starts
    // the transition back up (one frame alone can be coalesced away)
    raf.current = [requestAnimationFrame(() => { raf.current = [requestAnimationFrame(() => setFade(false))] })]
  }, [json, screen])
  return { warm: ok ? (ready ? live : boot) : null, fade, style: { opacity: fade ? 0.6 : 1, transition: 'opacity .15s' } }
}

const FLASH_KEY = 'jobnavigator_v2_flash'
export function setFlashToast(t) {
  try { sessionStorage.setItem(FLASH_KEY, JSON.stringify(t)) } catch { /* ignore */ }
}
export function useFlashToast(push) {
  useEffect(() => {
    let t = null
    try {
      const raw = sessionStorage.getItem(FLASH_KEY)
      if (raw) { t = JSON.parse(raw); sessionStorage.removeItem(FLASH_KEY) }
    } catch { /* ignore */ }
    if (t && t.msg) push(t)
  }, [push])
}

// A run vanishing from GET /monitor/active only means it ended, not that it succeeded.
// Check GET /monitor/run/{id} for real status (falls back to /monitor/history); returns null when unknown — never treat null as success.
export async function fetchRunOutcome(runId, jobType) {
  if (!runId) return null
  try {
    const { data } = await api.get(`/monitor/run/${runId}`)
    if (data && data.status) return data
  } catch { /* fall back to the history list below */ }
  try {
    const { data } = await api.get('/monitor/history', { params: { job_type: jobType, limit: 10 } })
    return (data || []).find((h) => String(h.id) === String(runId)) || null
  } catch { return null }
}

// A run row is a failure only when it reached a terminal state that is not
// `completed`; an unknown row (null) and a still-settling `running` are not.
export function runFailed(run) {
  return !!(run && run.status && run.status !== 'completed' && run.status !== 'running')
}

// The failure text a toast should name: the run's own error, else its summary,
// else the bare status so the user is never told only that "something failed".
export function runFailureReason(run) {
  return (run && (run.error || run.result_summary || run.status)) || 'the run did not finish'
}
