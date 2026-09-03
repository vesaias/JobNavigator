import React, { useState } from 'react'
import './theme.css'
import { useToasts, ToastStack } from './Toast'

// TEMPORARY debug page at /v2/toasts — fire every toast kind and check it in
// both themes. Not linked from the rail; delete this file and its route when
// the taxonomy is signed off.
const SAMPLES = [
  ['progress', 'Tailoring for Senior SWE at Plaid…', null, 'paper card + spinner · 2.5s'],
  ['progress', 'Scoring 14 jobs…', null, 'same, plural form'],
  ['success', 'Tailored for Senior SWE at Plaid', null, 'green tint + ✓ roundel · 2.5s'],
  ['success', 'Copy created for Datadog.', 'Open ↗', 'success with an action'],
  ['error', 'Scoring failed for Backend Engineer at Datadog', null, 'red tint + ! roundel · stays until dismissed'],
  ['error', 'Tailoring failed to start.', null, 'also persists'],
  ['undo', 'Skipped “Senior Go Engineer”', 'Undo', 'the only dark toast · 5s'],
  ['undo', 'Marked applied — “Staff Engineer”', 'Undo', 'dark = still actionable'],
]

export default function ToastLab() {
  const { toasts, push, dismiss } = useToasts()
  const [dark, setDark] = useState(() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })
  const toggle = () => setDark((v) => { const n = !v; try { localStorage.setItem('jobnavigator_dark_mode', String(n)) } catch {} return n })

  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'} style={{ flex: 1, minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', display: 'flex', flexDirection: 'column' }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Toast lab</h1>
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)' }}>Temporary — fire each kind, check both themes, then delete this page.</span>
        </div>
        {/* D3: the primitive gallery is the other rail-less lab page; neither is in
            the rail, so they link to each other rather than being unreachable. */}
        <a href="/v2/ui" className="v2-navlink v2-ctl" style={{ marginLeft: 'auto', height: 32, padding: '0 12px', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--accent)' }}>Primitives ›</a>
        <div onClick={toggle} className="v2-act v2-ctl" style={{ height: 32, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, cursor: 'pointer' }}>
          ◐ {dark ? 'Dark' : 'Light'}
        </div>
      </header>

      <div style={{ flex: 1, padding: '18px 30px 30px', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        <div style={{ border: '1px solid var(--line)', borderRadius: 10, background: 'var(--surface)', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 500, letterSpacing: '-.015em' }}>Fire one</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {SAMPLES.map(([kind, msg, action, note], i) => (
              <div key={i} onClick={() => push({ kind, msg, action, onAction: () => {} })} title={note} className="v2-bdc v2-ctl"
                style={{ height: 30, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>
                <span style={{ fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--muted)' }}>{kind}</span>
                {msg.length > 34 ? `${msg.slice(0, 34)}…` : msg}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <div onClick={() => SAMPLES.forEach(([kind, msg, action], i) => setTimeout(() => push({ kind, msg, action, onAction: () => {} }), i * 350))}
              className="v2-ctl" style={{ height: 30, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Fire all (watch the 3-toast cap)</div>
            <div onClick={() => toasts.forEach((t) => dismiss(t.id))} className="v2-act v2-ctl"
              style={{ height: 30, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Clear</div>
            <span style={{ alignSelf: 'center', fontSize: 11.5, color: 'var(--muted)' }}>{toasts.length} showing</span>
          </div>
        </div>

        <div style={{ border: '1px solid var(--line)', borderRadius: 10, background: 'var(--surface)', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 500, letterSpacing: '-.015em' }}>Rules</span>
          {[
            'progress — paper card, ink text, spinner. Ambient status, not news. 2.5s.',
            'success — green tint, solid ✓ roundel. The only green toast. 2.5s.',
            'error — red tint, ! roundel, stays until dismissed.',
            'undo — the one dark toast. Dark means still actionable, which is why progress is not dark. 5s.',
            'Stack bottom-right, newest at the bottom, at most three visible. Slide + fade 250ms.',
          ].map((t) => <span key={t} style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-2)' }}>{t}</span>)}
        </div>
      </div>

      <ToastStack toasts={toasts} onClose={dismiss} />
    </div>
  )
}
