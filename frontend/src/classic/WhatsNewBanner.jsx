import React, { useState } from 'react'
import { Sparkles, X } from 'lucide-react'

// The classic shell's announcement strip. Mounted by ClassicShell only
// (App.jsx), so it never appears over the 2.0 dashboard it is pointing at.
//
// Dismissal is keyed by RELEASE, not by a boolean: one stable key holding the
// version that was dismissed. Bumping WHATS_NEW_VERSION is all a new
// announcement needs — everyone sees it once, including the people who
// dismissed the previous one (the 1.1.0 banner wrote a different key entirely,
// `jn:whatsnew:v1.1.0`, so it cannot suppress this one either).
const WHATS_NEW_KEY = 'jobnavigator_whatsnew_dismissed'
const WHATS_NEW_VERSION = '2.0.0'

export default function WhatsNewBanner() {
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(WHATS_NEW_KEY) === WHATS_NEW_VERSION } catch { return false }
  })
  if (dismissed) return null

  const close = () => {
    try { localStorage.setItem(WHATS_NEW_KEY, WHATS_NEW_VERSION) } catch {}
    setDismissed(true)
  }

  return (
    <div className="flex items-start gap-3 px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm">
      <Sparkles size={18} className="mt-0.5 flex-shrink-0" />
      <div className="flex-1">
        <span className="font-semibold">JobNavigator 2.0 &mdash; the new dashboard is here.</span>{' '}
        Rebuilt interface, five themes, Persona import, cron helper and more.
        <div className="mt-2 flex items-center gap-3">
          {/* Plain anchor, same tab: leaving the classic shell for the current
              interface is a whole-app move, so let the browser do it (the rail's
              "New UI ↗" link takes the same route). */}
          <a href="/"
            className="px-2.5 py-1 rounded bg-white text-blue-700 font-medium hover:bg-blue-50 transition-colors">
            Open the new UI
          </a>
          <button onClick={close} className="text-white/80 hover:text-white text-xs underline transition-colors">
            Later
          </button>
        </div>
      </div>
      <button
        onClick={close}
        aria-label="Dismiss"
        className="flex-shrink-0 text-white/80 hover:text-white transition-colors"
      >
        <X size={18} />
      </button>
    </div>
  )
}
