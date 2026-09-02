import { useEffect, useRef } from 'react'

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
