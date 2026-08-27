import React, { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import api from '../api'
import './theme.css'

// Canonical v2 shell: dark grouped sidebar (Find / Apply / You).
// ready:true items route to a built v2 screen; the rest are dimmed placeholders
// until their redesign lands. countKey pulls a live badge count.
const GROUPS = [
  { label: 'Find', items: [
    { to: '/v2/feed', label: 'Jobs', ready: true, countKey: 'jobs' },
    { to: '/v2/searches', label: 'Searches' },
    { to: '/v2/companies', label: 'Companies' },
  ]},
  { label: 'Apply', items: [
    { to: '/v2/applications', label: 'Applications', countKey: 'apps' },
    { to: '/v2/resumes', label: 'Résumés', ready: true, countKey: 'resumes' },
    { to: '/v2/cover-letters', label: 'Cover Letters' },
  ]},
  { label: 'You', items: [
    { to: '/v2/persona', label: 'Persona' },
    { to: '/v2/stats', label: 'Stats' },
    { to: '/v2/settings', label: 'Settings' },
    { to: '/docs', label: 'API Docs', external: true },
  ]},
]

export default function V2App() {
  const loc = useLocation()
  const [open, setOpen] = useState(true)
  const [counts, setCounts] = useState({})
  const [dark, setDark] = useState(() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })
  const toggleTheme = () => setDark((v) => { const n = !v; try { localStorage.setItem('jobnavigator_dark_mode', String(n)) } catch {} return n })

  useEffect(() => {
    api.get('/jobs', { params: { status: 'new', limit: 1 } }).then(({ data }) => setCounts((c) => ({ ...c, jobs: data.total }))).catch(() => {})
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setCounts((c) => ({ ...c, resumes: Array.isArray(data) ? data.length : undefined }))).catch(() => {})
    api.get('/applications').then(({ data }) => setCounts((c) => ({ ...c, apps: Array.isArray(data) ? data.length : (data?.total) }))).catch(() => {})
  }, [])

  const W = open ? 206 : 60
  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'} style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <aside style={{ width: W, flex: `0 0 ${W}px`, background: 'var(--rail)', display: 'flex', flexDirection: 'column', padding: '0 0 8px', transition: 'width .18s', overflow: 'hidden' }}>
        <div style={{ height: 64, flex: '0 0 auto', display: 'flex', alignItems: 'center', padding: '0 22px', color: '#f6f3ea', whiteSpace: 'nowrap' }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.01em' }}>{open ? 'JobNavigator' : 'JN'}</span>
        </div>
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 18, padding: '6px 0', overflow: 'auto' }}>
          {GROUPS.map((g) => (
            <div key={g.label} style={{ display: 'flex', flexDirection: 'column' }}>
              {open && <div style={{ fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase', color: '#66604f', padding: '0 22px 8px' }}>{g.label}</div>}
              {g.items.map((it) => {
                const active = loc.pathname === it.to || loc.pathname.startsWith(it.to + '/')
                const count = it.countKey != null ? counts[it.countKey] : undefined
                const base = { display: 'flex', alignItems: 'center', height: 32, padding: '0 20px', fontSize: 14, whiteSpace: 'nowrap', borderLeft: `2px solid ${active ? 'var(--accent)' : 'transparent'}` }
                const inner = (
                  <>
                    <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{open ? it.label : it.label.slice(0, 2)}</span>
                    {open && count != null && <span style={{ flex: '0 0 auto', fontSize: 11, fontFamily: 'var(--mono)', color: active ? '#a8a396' : '#66604f' }}>{count}</span>}
                    {open && !it.ready && !it.external && <span style={{ flex: '0 0 auto', fontSize: 9, color: '#66604f', marginLeft: 6 }}>soon</span>}
                  </>
                )
                if (it.external) return <a key={it.to} href={it.to} target="_blank" rel="noopener noreferrer" className="v2-navdark" style={{ ...base, color: '#a8a396' }}>{inner}</a>
                if (!it.ready) return <div key={it.to} title="Coming in the redesign" style={{ ...base, color: '#66604f', cursor: 'default' }}>{inner}</div>
                return (
                  <NavLink key={it.to} to={it.to} className="v2-navdark" style={{ ...base, color: active ? '#f6f3ea' : '#a8a396', background: active ? 'rgba(63,107,82,.14)' : 'transparent' }}>{inner}</NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <a href="/" className="v2-navdark" style={{ display: 'flex', alignItems: 'center', gap: 8, height: 32, padding: '0 20px', fontSize: 12, color: '#66604f', whiteSpace: 'nowrap' }}>
          {open ? '← Classic UI' : '←'}
        </a>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: 42, padding: '0 14px', borderTop: '1px solid #2e2c24' }}>
          <div onClick={toggleTheme} className="v2-navdark" title={`Switch to ${dark ? 'light' : 'dark'} mode`} style={{ width: 30, height: 30, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--rail-text)', fontSize: 14, cursor: 'pointer' }}>◐</div>
          {open && <div title="Scraper healthy" style={{ display: 'flex', alignItems: 'center', gap: 6, height: 30, padding: '0 9px', borderRadius: 8, color: '#66604f', fontSize: 11.5 }}><span style={{ width: 6, height: 6, borderRadius: 99, background: '#8dbb9f' }} />healthy</div>}
          <div onClick={() => setOpen((o) => !o)} className="v2-navdark" title="Collapse sidebar" style={{ marginLeft: 'auto', width: 30, height: 30, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#66604f', fontSize: 14, cursor: 'pointer' }}>{open ? '‹' : '›'}</div>
        </div>
      </aside>
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Outlet />
      </main>
    </div>
  )
}
