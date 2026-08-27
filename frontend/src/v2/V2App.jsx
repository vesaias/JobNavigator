import React from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Briefcase, LayoutDashboard, Building2, Search, FileText, Mail, User, Settings, BarChart3, ArrowLeft } from 'lucide-react'
import './theme.css'

// v2 nav. Only screens rebuilt so far are enabled; the rest are dimmed
// placeholders until their redesign lands. Swap /v2 → / when all are done.
const NAV = [
  { to: '/v2/feed', icon: Briefcase, label: 'Feed', ready: true },
  { to: '/v2/applications', icon: LayoutDashboard, label: 'Applications' },
  { to: '/v2/companies', icon: Building2, label: 'Companies' },
  { to: '/v2/searches', icon: Search, label: 'Searches' },
  { to: '/v2/resumes', icon: FileText, label: 'Résumés' },
  { to: '/v2/cover-letters', icon: Mail, label: 'Cover Letters' },
  { to: '/v2/persona', icon: User, label: 'Persona' },
  { to: '/v2/settings', icon: Settings, label: 'Settings' },
  { to: '/v2/stats', icon: BarChart3, label: 'Stats' },
]

export default function V2App() {
  const loc = useLocation()
  return (
    <div className="jn-v2" style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <aside style={{ width: 208, flex: '0 0 208px', background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: 56, flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 9, padding: '0 18px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: 18 }}>🧭</span>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em' }}>JobNavigator</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 99, padding: '1px 5px' }}>v2</span>
        </div>
        <nav style={{ flex: 1, padding: '8px 8px', display: 'flex', flexDirection: 'column', gap: 1, overflow: 'auto' }}>
          {NAV.map(({ to, icon: Icon, label, ready }) => {
            const active = loc.pathname === to || loc.pathname.startsWith(to + '/')
            if (!ready) {
              return (
                <div key={to} title="Coming in the redesign" style={{ display: 'flex', alignItems: 'center', gap: 11, height: 38, padding: '0 12px', borderRadius: 8, fontSize: 13.5, color: 'var(--faint)', cursor: 'default' }}>
                  <Icon size={17} /><span>{label}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--faint)' }}>soon</span>
                </div>
              )
            }
            return (
              <NavLink key={to} to={to} className="v2-navlink"
                style={{ display: 'flex', alignItems: 'center', gap: 11, height: 38, padding: '0 12px', borderRadius: 8, fontSize: 13.5,
                  background: active ? 'var(--accent-bg)' : 'transparent',
                  color: active ? 'var(--accent)' : 'var(--stone)',
                  fontWeight: active ? 600 : 400 }}>
                <Icon size={17} /><span>{label}</span>
              </NavLink>
            )
          })}
        </nav>
        <a href="/" className="v2-navlink" style={{ display: 'flex', alignItems: 'center', gap: 9, height: 40, padding: '0 14px', borderTop: '1px solid var(--border)', fontSize: 12, color: 'var(--muted)' }}>
          <ArrowLeft size={15} /> Classic UI
        </a>
      </aside>
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Outlet />
      </main>
    </div>
  )
}
