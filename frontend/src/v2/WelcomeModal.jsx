import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Settings as SettingsIcon, FileUser, Building2, Search } from 'lucide-react'
import './theme.css'

// First-run overlay (System Overlays.dc.html · 2). The design draws the steps as
// static rows; v1 made each one a link to the screen it names, which is the
// whole point of the list, so they stay clickable and hover.
const STEPS = [
  [SettingsIcon, 'Set up AI scoring', 'Pick your LLM provider and add its key — Anthropic, OpenAI, Ollama or OpenRouter.', 'settings'],
  [FileUser, 'Build your résumé + Persona', 'Edit a base résumé and fill Persona (contact, work auth) so jobs score against your profile.', 'resumes'],
  [Building2, 'Activate a company', 'Enable a seeded company or add your own to start scraping.', 'companies'],
  [Search, 'Configure a search', 'Enable a keyword search or LinkedIn Personal to discover jobs from boards.', 'searches'],
]

export default function WelcomeModal({ onClose }) {
  const navigate = useNavigate()
  // land in whichever shell you're already in — this overlay is global
  const base = useLocation().pathname.startsWith('/v2') ? '/v2/' : '/'
  const dark = (() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })()
  const go = (slug) => { onClose?.(); navigate(base + slug) }

  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'} onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9998, padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ width: 420, maxWidth: '100%', background: 'var(--recessed)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '22px 24px 6px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'baseline' }}>
            <span style={{ fontFamily: 'var(--serif)', fontSize: 21, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '26px' }}>Welcome to JobNavigator</span>
            <span onClick={onClose} className="v2-hover-accent-text" role="button" aria-label="Close"
              style={{ marginLeft: 'auto', fontSize: 13, lineHeight: '26px', color: 'var(--muted)', cursor: 'pointer' }}>✕</span>
          </div>
          <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--muted)' }}>Four steps and your search runs itself.</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '14px 24px 18px' }}>
          {STEPS.map(([Icon, title, desc, to], i) => (
            <div key={to} onClick={() => go(to)} className="v2-welcomestep"
              style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '9px 2px', borderRadius: 8, cursor: 'pointer' }}>
              <span style={{ flex: '0 0 auto', width: 22, height: 22, borderRadius: 99, background: 'var(--surface-2)', color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--mono)', fontSize: 11, lineHeight: 1 }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, lineHeight: '18px', fontWeight: 600 }}>
                  {title}<Icon size={15} strokeWidth={1.8} style={{ color: 'var(--muted)', flex: '0 0 auto' }} />
                </span>
                <span style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.5, textWrap: 'pretty' }}>{desc}</span>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 24px', borderTop: '1px solid var(--line-soft)', background: 'var(--bg)' }}>
          <span onClick={() => go('settings')}
            style={{ marginLeft: 'auto', height: 30, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, lineHeight: 1, cursor: 'pointer' }}>Start with Settings →</span>
        </div>
      </div>
    </div>
  )
}
