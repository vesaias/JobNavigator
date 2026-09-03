import { useEffect, useLayoutEffect, useRef } from 'react'

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
// layout and pull it back onto the pixel grid with a sub-pixel margin.
//
//   const panel = useRef(null); useSnapTop(panel)   → ref={panel} on the panel
//
// It runs after every render because the panel's height changes with its
// content (a picker opening, an error line appearing), and re-runs on resize.
export function useSnapTop(ref) {
  useLayoutEffect(() => {
    const snap = () => {
      const el = ref.current
      if (!el) return
      el.style.marginTop = '0px'
      const top = el.getBoundingClientRect().top
      const delta = Math.round(top) - top
      if (delta) el.style.marginTop = `${delta}px`
    }
    snap()
    window.addEventListener('resize', snap)
    return () => window.removeEventListener('resize', snap)
  })
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
