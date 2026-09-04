import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import api from '../api'

// Small cross-screen hooks. Kept out of Toast.jsx so a screen can take the
// Escape handling without also pulling in the toast host.

// RES-15: Escape closes every v2 modal, from one place rather than a keydown
// effect copied into each modal.
//
//   useEscape(onClose)              — a component that only renders while open
//   useEscape(onClose, isOpen)      — a screen that holds the modal's flag
//
// The handler ignores an event another handler already claimed
// (`e.defaultPrevented`) and claims the ones it acts on, so a dropdown or menu
// *inside* a modal can swallow Escape and close only itself. Child effects run
// before parent effects, so an inner control's listener is registered — and
// therefore fires — first; the callback is held in a ref so an inline arrow
// doesn't re-register (and re-order) this listener on every render.
export function useEscape(onClose, active = true) {
  const cb = useRef(onClose)
  cb.current = onClose
  useEffect(() => {
    if (!active) return undefined
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      e.preventDefault()
      cb.current?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active])
}

// RES-21: a toast pushed immediately before navigate() dies with the screen that
// pushed it — the ToastStack is per-screen. Hand the message to the destination
// instead: the leaving screen stores it, the arriving screen pushes it once.
// RES-32: a flex-centred modal whose panel has an odd height lands on a half
// pixel in an even viewport (or vice versa), so every 1px border inside it is
// drawn across two device rows and reads blurred. Measure the panel after
// layout and pull it back onto the pixel grid.
//
//   const panel = useRef(null); useSnapTop(panel)   → ref={panel} on the panel
//
// It runs after every render because the panel's height changes with its
// content (a picker opening, an error line appearing), and re-runs on resize.
//
// RES-32 re-open: the correction used to be a `marginTop`, which does NOT move
// the panel 1:1. Every panel this is wired to sits in a
// `display:flex; align-items:center` wrapper, where the leftover space is split
// above and below the child — so a margin-top of d shifts a centred child by
// only d/2. Measured: a natural top of 151.5 asked for +0.5px and rendered at
// 151.75, still off the grid, for odd and even panel heights alike. `translateY`
// is a paint-time offset: exactly 1:1, no effect on the parent's layout (so the
// centring can't react to it and re-open the gap), and it is only applied when
// there is a fraction to correct — so a panel that already lands on the grid
// keeps a clean `transform`, and none of these panels contains a
// `position: fixed` descendant that a transform's containing block would
// re-anchor (every fixed element in the v2 modals is the *wrapper*, not a child
// of the panel).
export function useSnapTop(ref) {
  useLayoutEffect(() => {
    let busy = false
    const snap = () => {
      const el = ref.current
      if (!el || busy) return
      busy = true                       // a resize during the reflow below must not re-enter
      try {
        // Measure the *natural* top: clearing the transform first keeps the last
        // correction out of the reading, otherwise each pass would snap the
        // already-snapped position and drift.
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
// DESIGN-LOAD: every screen used to render its chrome from empty state and then
// jump — the subtitle counted 0 bases, the filter pills held no options, the
// table was an empty box — because each fetch landed in its own render. The rail
// already solved this (V2App.jsx:46-150): one `Promise.allSettled`, one setState,
// plus a warm-start snapshot so the numbers are there on the first frame.
//
//   const { ready } = useSettled([() => load(), () => loadHealth()])
//
// `loaders` is an array of thunks (or promises); it is read from a ref, so an
// inline array does NOT re-run it — only a change of `key` does (a screen whose
// document id is in the URL passes that id). The thunks keep doing whatever they
// already did, including their own setState and their own catch; `ready` simply
// flips once, after the last of them settles, so the screen can reveal its
// data-dependent chrome in a single render. `data` carries the fulfilled values
// (undefined where a loader rejected) for screens that would rather read them
// here than through their own state.
//
// Deliberately no spinner: the wait is a few hundred ms and the layout keeps its
// boxes, so a spinner would be one more thing appearing and disappearing. The
// `Spinner` primitive stays for explicit long actions (scoring, tailoring).
export function useSettled(loaders, key = '') {
  const ref = useRef(loaders)
  ref.current = loaders
  // the settled result carries the key it belongs to, and readiness is derived
  // during render — a key change (another document) is stale *immediately*,
  // rather than a frame later when an effect could clear it. That frame is the
  // whole bug: it is where the previous document's numbers get painted.
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
// The parts of a screen that are the same on the frame after a refresh as they
// were before it — a subtitle's counts, a filter's option list — are cached and
// read back synchronously in the initial state, so they paint immediately and are
// silently reconciled when the real data settles.
//
//   const { warm, style } = useWarm('resumes', ready ? { bases, copies } : null, ready)
//
// `warm` is the cached snapshot until `ready`, the live value after. A value that
// comes back equal to its cache causes no render at all; one that differs fades
// (.15s, from .6) exactly like a rail badge. A first-ever visit has nothing
// cached: `warm` is null and the screen renders the empty line — with its box
// reserved (NBSP) so nothing shifts when the text lands.
const WARM_NS = 'jobnavigator_v2_warm:'
export const NBSP = '\u00A0'
const readWarm = (screen) => {
  try {
    const v = JSON.parse(localStorage.getItem(WARM_NS + screen) || 'null')
    return v && typeof v === 'object' ? v : null
  } catch { return null }
}
export function useWarm(screen, live, ready) {
  const [boot] = useState(() => readWarm(screen))
  const [fade, setFade] = useState(false)
  const raf = useRef([])
  const last = useRef(boot === null ? null : JSON.stringify(boot))
  useEffect(() => () => { raf.current.forEach((id) => cancelAnimationFrame(id)) }, [])
  const json = ready && live != null ? JSON.stringify(live) : null
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
  return { warm: ready ? live : boot, fade, style: { opacity: fade ? 0.6 : 1, transition: 'opacity .15s' } }
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

// DS-B-02: a background run disappearing from GET /monitor/active only means it
// ENDED — it says nothing about whether it worked, so a screen that infers
// "done" from the run vanishing reports a crashed run as a success. Every
// launcher (POST /resumes/tailor, /resumes/{id}/score-check, /cover-letters/
// generate) hands back a `run_id`; GET /monitor/run/{id} (main.py:1040) carries
// the real `status` + `error`, with GET /monitor/history as the fallback for a
// deployment where the by-id route is missing.
//
// Returns the run row, or null when it cannot be identified — callers must treat
// null as "unknown", never as success. `status === 'running'` is also possible
// for a moment: the in-memory registry drops a run before its row is finalised,
// so a caller should not read that as a failure.
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
