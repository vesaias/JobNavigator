// hooks.js — the cross-screen hooks, with `useWarm`'s cache contract as the
// headline. R4-T2B-03: a settled-but-FAILED load carries zeroes, and writing
// those to the warm cache made the next visit open by asserting "0 bases · 0
// tailored copies" next to an error. The invariant tested here is therefore:
//
//   ok === false  ->  nothing is written to localStorage, and `warm` is null
//                     (so the caller renders DASH, not a zero).
//
// `useWarm` is rendered for real with @testing-library/react's renderHook — the
// package installs cleanly against React 18 here — because the write happens in
// an effect and there is no pure surface that would exercise it.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api', () => ({
  default: { get: vi.fn() },
}))

import api from '../../api'
import {
  useWarm, useEscape, useFlashToast, setFlashToast,
  fetchRunOutcome, runFailed, runFailureReason, NBSP, DASH,
} from '../hooks'

const WARM_NS = 'jobnavigator_v2_warm:'
const FLASH_KEY = 'jobnavigator_v2_flash'
const cache = (screen) => localStorage.getItem(WARM_NS + screen)

let n = 0
const freshScreen = () => `screen_${++n}`

beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
afterEach(() => { vi.useRealTimers() })

// ── useWarm ─────────────────────────────────────────────────────────────────
describe('useWarm — a failed load must not poison the cache', () => {
  it('writes nothing and hands back null when ok is false', () => {
    const s = freshScreen()
    const live = { bases: 0, tailored: 0 }          // the zeroes a failed load carries
    const { result } = renderHook(() => useWarm(s, live, true, false))
    expect(cache(s)).toBeNull()
    expect(result.current.warm).toBeNull()
  })

  it('does not overwrite a GOOD cached snapshot when a later load fails', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, JSON.stringify({ bases: 4, tailored: 7 }))
    const { result } = renderHook(() => useWarm(s, { bases: 0, tailored: 0 }, true, false))
    expect(JSON.parse(cache(s))).toEqual({ bases: 4, tailored: 7 })
    // and it refuses to show the stale snapshot too: null -> the caller prints DASH
    expect(result.current.warm).toBeNull()
  })

  it('a failed load reports null even while still loading', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, JSON.stringify({ bases: 4 }))
    const { result } = renderHook(() => useWarm(s, null, false, false))
    expect(result.current.warm).toBeNull()
    expect(JSON.parse(cache(s))).toEqual({ bases: 4 })
  })

  it('writes and returns live data once ready && ok', () => {
    const s = freshScreen()
    const live = { bases: 3, tailored: 11 }
    const { result } = renderHook(() => useWarm(s, live, true, true))
    expect(result.current.warm).toBe(live)
    expect(JSON.parse(cache(s))).toEqual(live)
  })

  it('ok defaults to true, so existing callers keep caching', () => {
    const s = freshScreen()
    const { result } = renderHook(() => useWarm(s, { a: 1 }, true))
    expect(result.current.warm).toEqual({ a: 1 })
    expect(JSON.parse(cache(s))).toEqual({ a: 1 })
  })

  it('paints the cached snapshot before the load settles, then swaps to live', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, JSON.stringify({ bases: 2 }))
    const live = { bases: 5 }
    const { result, rerender } = renderHook(
      ({ ready }) => useWarm(s, ready ? live : null, ready, true),
      { initialProps: { ready: false } },
    )
    expect(result.current.warm).toEqual({ bases: 2 })    // the warm start
    expect(JSON.parse(cache(s))).toEqual({ bases: 2 })   // nothing written yet
    rerender({ ready: true })
    expect(result.current.warm).toBe(live)
    expect(JSON.parse(cache(s))).toEqual({ bases: 5 })
  })

  it('does not write while the load is still running (ready false)', () => {
    const s = freshScreen()
    renderHook(() => useWarm(s, { bases: 9 }, false, true))
    expect(cache(s)).toBeNull()
  })

  it('does not write a null live value', () => {
    const s = freshScreen()
    const { result } = renderHook(() => useWarm(s, null, true, true))
    expect(cache(s)).toBeNull()
    expect(result.current.warm).toBeNull()
  })

  it('a first visit does not cross-fade; a changed reconcile does', () => {
    const first = freshScreen()
    const { result: r1 } = renderHook(() => useWarm(first, { bases: 1 }, true, true))
    expect(r1.current.fade).toBe(false)                 // nothing to fade from
    expect(r1.current.style).toEqual({ opacity: 1, transition: 'opacity .15s' })

    const second = freshScreen()
    localStorage.setItem(WARM_NS + second, JSON.stringify({ bases: 1 }))
    const { result: r2 } = renderHook(() => useWarm(second, { bases: 2 }, true, true))
    expect(r2.current.fade).toBe(true)
    expect(r2.current.style.opacity).toBe(0.6)
  })

  it('an unchanged reconcile neither fades nor rewrites', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, JSON.stringify({ bases: 1 }))
    const { result } = renderHook(() => useWarm(s, { bases: 1 }, true, true))
    expect(result.current.fade).toBe(false)
    expect(JSON.parse(cache(s))).toEqual({ bases: 1 })
  })

  it('survives an unreadable / corrupt cache entry', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, '{not json')
    const { result } = renderHook(() => useWarm(s, null, false, true))
    expect(result.current.warm).toBeNull()
  })

  it('ignores a cached non-object (a bare number is not a snapshot)', () => {
    const s = freshScreen()
    localStorage.setItem(WARM_NS + s, '42')
    const { result } = renderHook(() => useWarm(s, null, false, true))
    expect(result.current.warm).toBeNull()
  })
})

// ── the "we don't know" glyphs ──────────────────────────────────────────────
describe('NBSP / DASH', () => {
  it('are the loading and the failed marks, and are different', () => {
    expect(NBSP).toBe('\u00A0')        // loading: the shell holds its box open
    expect(DASH).toBe('\u2014')        // failed: an em dash, never an asserted zero
    expect(NBSP).not.toBe(DASH)
    expect(NBSP).not.toBe(' ')         // a plain space would collapse in HTML
    expect(NBSP).toHaveLength(1)
    expect(DASH).toHaveLength(1)
  })
})

// ── run outcome ─────────────────────────────────────────────────────────────
describe('runFailed', () => {
  it('is false for an unknown run — null is never a failure', () => {
    for (const r of [null, undefined, {}, { status: '' }, { status: null }]) {
      expect(runFailed(r), JSON.stringify(r)).toBe(false)
    }
  })
  it('is false while still running and on completion', () => {
    expect(runFailed({ status: 'running' })).toBe(false)
    expect(runFailed({ status: 'completed' })).toBe(false)
  })
  it('is true for any other terminal state', () => {
    for (const s of ['failed', 'error', 'cancelled', 'timeout']) {
      expect(runFailed({ status: s }), s).toBe(true)
    }
  })
  it('always returns a boolean, never a truthy object', () => {
    expect(typeof runFailed({ status: 'failed' })).toBe('boolean')
    expect(typeof runFailed(undefined)).toBe('boolean')
  })
})

describe('runFailureReason', () => {
  it('prefers the run\'s own error', () => {
    expect(runFailureReason({ error: 'boom', result_summary: 'sum', status: 'failed' })).toBe('boom')
  })
  it('falls back to the result summary', () => {
    expect(runFailureReason({ result_summary: 'sum', status: 'failed' })).toBe('sum')
  })
  it('then to the bare status', () => {
    expect(runFailureReason({ status: 'failed' })).toBe('failed')
  })
  it('and finally to a sentence, so the user is never told only that something failed', () => {
    for (const r of [null, undefined, {}, { error: '', result_summary: '', status: '' }]) {
      expect(runFailureReason(r), JSON.stringify(r)).toBe('the run did not finish')
    }
  })
})

describe('fetchRunOutcome', () => {
  beforeEach(() => { api.get.mockReset() })
  it('returns null for a falsy run id without calling the API', async () => {
    await expect(fetchRunOutcome(null, 'scrape')).resolves.toBeNull()
    await expect(fetchRunOutcome(0, 'scrape')).resolves.toBeNull()
    expect(api.get).not.toHaveBeenCalled()
  })
  it('uses /monitor/run/{id} when it carries a status', async () => {
    api.get.mockResolvedValueOnce({ data: { id: 7, status: 'completed' } })
    await expect(fetchRunOutcome(7, 'scrape')).resolves.toEqual({ id: 7, status: 'completed' })
    expect(api.get).toHaveBeenCalledWith('/monitor/run/7')
  })
  it('falls back to /monitor/history when the direct read throws', async () => {
    api.get
      .mockRejectedValueOnce(new Error('404'))
      .mockResolvedValueOnce({ data: [{ id: 8, status: 'failed' }, { id: 7, status: 'completed' }] })
    await expect(fetchRunOutcome('7', 'scrape')).resolves.toEqual({ id: 7, status: 'completed' })
    expect(api.get).toHaveBeenLastCalledWith('/monitor/history', { params: { job_type: 'scrape', limit: 10 } })
  })
  it('falls back when the direct read answers without a status', async () => {
    api.get
      .mockResolvedValueOnce({ data: {} })
      .mockResolvedValueOnce({ data: [{ id: 7, status: 'failed' }] })
    await expect(fetchRunOutcome(7, 'scrape')).resolves.toEqual({ id: 7, status: 'failed' })
  })
  it('returns null (unknown), not a success, when the run is in neither place', async () => {
    api.get
      .mockRejectedValueOnce(new Error('nope'))
      .mockResolvedValueOnce({ data: [] })
    await expect(fetchRunOutcome(7, 'scrape')).resolves.toBeNull()
    expect(runFailed(null)).toBe(false)
  })
  it('returns null when the history call throws too', async () => {
    api.get.mockRejectedValueOnce(new Error('a')).mockRejectedValueOnce(new Error('b'))
    await expect(fetchRunOutcome(7, 'scrape')).resolves.toBeNull()
  })
})

// ── flash toast ─────────────────────────────────────────────────────────────
describe('setFlashToast / useFlashToast', () => {
  it('stores the toast in sessionStorage, not localStorage', () => {
    setFlashToast({ msg: 'Saved', kind: 'ok' })
    expect(JSON.parse(sessionStorage.getItem(FLASH_KEY))).toEqual({ msg: 'Saved', kind: 'ok' })
    expect(localStorage.getItem(FLASH_KEY)).toBeNull()
  })
  it('swallows an unserialisable payload rather than throwing', () => {
    const cyclic = {}; cyclic.self = cyclic
    expect(() => setFlashToast(cyclic)).not.toThrow()
  })
  it('is picked up once and then cleared', () => {
    setFlashToast({ msg: 'Deleted' })
    const push = vi.fn()
    const { unmount } = renderHook(() => useFlashToast(push))
    expect(push).toHaveBeenCalledWith({ msg: 'Deleted' })
    expect(sessionStorage.getItem(FLASH_KEY)).toBeNull()
    unmount()
    // a second screen mounting must not replay it
    const push2 = vi.fn()
    renderHook(() => useFlashToast(push2))
    expect(push2).not.toHaveBeenCalled()
  })
  it('pushes nothing when there is no flash, or when it has no msg', () => {
    const push = vi.fn()
    renderHook(() => useFlashToast(push))
    expect(push).not.toHaveBeenCalled()
    sessionStorage.setItem(FLASH_KEY, JSON.stringify({ kind: 'ok' }))
    renderHook(() => useFlashToast(push))
    expect(push).not.toHaveBeenCalled()
  })
  it('survives a corrupt flash entry', () => {
    sessionStorage.setItem(FLASH_KEY, '{oops')
    const push = vi.fn()
    expect(() => renderHook(() => useFlashToast(push))).not.toThrow()
    expect(push).not.toHaveBeenCalled()
  })
})

// ── useEscape ───────────────────────────────────────────────────────────────
describe('useEscape', () => {
  const esc = (init = {}) => {
    const e = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true, ...init })
    act(() => { document.body.dispatchEvent(e) })
    return e
  }

  it('closes on Escape and prevents the default', () => {
    const onClose = vi.fn()
    renderHook(() => useEscape(onClose))
    const e = esc()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(e.defaultPrevented).toBe(true)
  })
  it('ignores other keys', () => {
    const onClose = vi.fn()
    renderHook(() => useEscape(onClose))
    act(() => { document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })) })
    expect(onClose).not.toHaveBeenCalled()
  })
  it('ignores an event an inner handler already claimed', () => {
    const onClose = vi.fn()
    renderHook(() => useEscape(onClose))
    const inner = (e) => e.preventDefault()
    document.addEventListener('keydown', inner, true)   // capture: runs first
    try { esc() } finally { document.removeEventListener('keydown', inner, true) }
    expect(onClose).not.toHaveBeenCalled()
  })
  it('does nothing when inactive, and detaches on unmount', () => {
    const onClose = vi.fn()
    const { unmount } = renderHook(() => useEscape(onClose, false))
    esc()
    expect(onClose).not.toHaveBeenCalled()
    unmount()
    esc()
    expect(onClose).not.toHaveBeenCalled()

    const onClose2 = vi.fn()
    const h = renderHook(() => useEscape(onClose2, true))
    esc()
    expect(onClose2).toHaveBeenCalledTimes(1)
    h.unmount()
    esc()
    expect(onClose2).toHaveBeenCalledTimes(1)
  })
  it('always calls the LATEST callback without re-registering the listener', () => {
    const a = vi.fn(); const b = vi.fn()
    const { rerender } = renderHook(({ cb }) => useEscape(cb), { initialProps: { cb: a } })
    esc()
    rerender({ cb: b })
    esc()
    expect(a).toHaveBeenCalledTimes(1)
    expect(b).toHaveBeenCalledTimes(1)
  })
  // ── capture: the topmost overlay wins (R4-E2E-01) ──────────────────────────
  it('capture=true beats a screen handler that registered first', () => {
    // The screen behind a global overlay mounts first, so in the bubble phase its
    // listener runs first and preventDefault()s the key — which made the Welcome
    // modal's own handler bail and left Escape doing nothing on /v2/feed.
    const screen = vi.fn((e) => e.preventDefault())
    document.addEventListener('keydown', screen)
    const onClose = vi.fn()
    try {
      renderHook(() => useEscape(onClose, true, true))
      esc()
    } finally { document.removeEventListener('keydown', screen) }
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen).not.toHaveBeenCalled()      // stopPropagation kept it from ever running
  })
  it('a capture listener stops an overlay underneath from closing too', () => {
    const under = vi.fn()
    const top = vi.fn()
    renderHook(() => useEscape(under))              // an in-shell modal
    renderHook(() => useEscape(top, true, true))    // the global overlay above it
    esc()
    expect(top).toHaveBeenCalledTimes(1)
    expect(under).not.toHaveBeenCalled()
  })
  it('capture=false (the default) stays in the bubble phase', () => {
    const onClose = vi.fn()
    const screen = vi.fn((e) => e.preventDefault())
    document.addEventListener('keydown', screen)
    try {
      renderHook(() => useEscape(onClose))
      esc()
    } finally { document.removeEventListener('keydown', screen) }
    expect(screen).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()          // the claimed event is honoured
  })
})
