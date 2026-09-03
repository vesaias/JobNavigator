import React, { useState, useEffect, useCallback } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Newspaper, Search, Building2, Send, FileUser, Mail,
  Fingerprint, ChartLine, Settings as SettingsIcon,
} from 'lucide-react'
import api from '../api'
import './theme.css'

// Canonical v2 shell (Nav Rail.dc.html): dark grouped rail, 206 ⇄ 50px.
//
// The expanded rail is deliberately pure text — that's the signature. Icons
// exist ONLY in the collapsed state and cross-fade as the labels fade out, so
// the rail never shows both at once. Group headers become short divider ticks.
// Warnings survive collapse as an amber dot beside the icon, since the label
// and count they'd otherwise appear next to are gone.
const GROUPS = [
  { label: 'Find', items: [
    { to: '/v2/feed', label: 'Jobs', ready: true, countKey: 'jobs', Icon: Newspaper },
    { to: '/v2/searches', label: 'Searches', ready: true, countKey: 'searches', Icon: Search, warnKey: 'searches' },
    { to: '/v2/companies', label: 'Companies', ready: true, countKey: 'companies', Icon: Building2, warnKey: 'companies' },
  ]},
  { label: 'Apply', items: [
    { to: '/v2/applications', label: 'Applications', ready: true, countKey: 'apps', Icon: Send },
    { to: '/v2/resumes', label: 'Résumés', ready: true, countKey: 'resumes', Icon: FileUser },
    { to: '/v2/cover-letters', label: 'Cover Letters', ready: true, countKey: 'letters', Icon: Mail },
  ]},
  { label: 'You', items: [
    { to: '/v2/persona', label: 'Persona', ready: true, Icon: Fingerprint },
    { to: '/v2/stats', label: 'Stats', ready: true, Icon: ChartLine },
    { to: '/v2/settings', label: 'Settings', ready: true, Icon: SettingsIcon },
    // API docs moved to the Settings footer — it is a reference link, not a screen
  ]},
]

const ago = (iso) => {
  if (!iso) return null
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`
}

export default function V2App() {
  const loc = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('jobnavigator_v2_rail') !== 'collapsed' } catch { return true } })
  const [counts, setCounts] = useState({})
  const [warn, setWarn] = useState({})
  const [health, setHealth] = useState(null)
  const [dark, setDark] = useState(() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })

  const toggleTheme = () => setDark((v) => { const n = !v; try { localStorage.setItem('jobnavigator_dark_mode', String(n)) } catch {} return n })
  const toggleRail = () => setOpen((v) => { const n = !v; try { localStorage.setItem('jobnavigator_v2_rail', n ? 'expanded' : 'collapsed') } catch {} return n })

  const loadCounts = useCallback(() => {
    api.get('/jobs', { params: { status: 'new', limit: 1 } }).then(({ data }) => setCounts((c) => ({ ...c, jobs: data.total }))).catch(() => { /* silent: a nav badge — the screen behind it owns the error state */ })
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setCounts((c) => ({ ...c, resumes: Array.isArray(data) ? data.length : undefined }))).catch(() => { /* silent: nav badge */ })
    // /applications returns {applications, total} — ask for one row and read the
    // total, so this count no longer trails the others by ~half a second
    api.get('/applications', { params: { limit: 1 } }).then(({ data }) => setCounts((c) => ({ ...c, apps: Array.isArray(data) ? data.length : (data?.total) }))).catch(() => { /* silent: nav badge */ })
    api.get('/companies').then(({ data }) => setCounts((c) => ({ ...c, companies: Array.isArray(data) ? data.length : undefined }))).catch(() => { /* silent: nav badge */ })
    api.get('/searches').then(({ data }) => setCounts((c) => ({ ...c, searches: Array.isArray(data) ? data.length : undefined }))).catch(() => { /* silent: nav badge */ })
    api.get('/cover-letters').then(({ data }) => setCounts((c) => ({ ...c, letters: Array.isArray(data) ? data.length : undefined }))).catch(() => { /* silent: nav badge */ })
    // sources needing attention — the same signal Companies/Searches badge with
    api.get('/health/entities').then(({ data }) => setWarn({
      companies: (data?.companies || []).length,
      searches: (data?.searches || []).length,
    })).catch(() => { /* silent: nav badge */ })
    // the pipeline pulse: the last scrape sweep, however it ended
    api.get('/monitor/history', { params: { limit: 1, job_type: 'scrape_all' } })
      .then(({ data }) => setHealth((data || [])[0] || null)).catch(() => { /* silent: the rail's health line — it just stays as it was */ })
  }, [])
  // APPS-19: screens dispatch jn:counts-changed after a create/delete so the badges follow
  useEffect(() => { loadCounts(); window.addEventListener('jn:counts-changed', loadCounts); return () => window.removeEventListener('jn:counts-changed', loadCounts) }, [loadCounts])

  const failing = (warn.companies || 0) + (warn.searches || 0)
  const healthy = failing === 0 && health?.status !== 'failed'
  // the rail gives this line ~166px at 11.5px, so the unhealthy variant drops the
  // timestamp rather than ellipsing away the part that matters
  const healthText = failing
    ? `${failing} source${failing === 1 ? ' needs' : 's need'} attention`
    : health
      ? `Scraper ${health.status === 'failed' ? 'run failed' : 'healthy'} · ${ago(health.finished_at || health.started_at) || '—'}`
      : 'No scrape recorded yet'
  // the label merges both signals into one number; the tooltip says what the dot
  // actually aggregates — failing companies and failing searches, named separately
  const nC = warn.companies || 0
  const nS = warn.searches || 0
  const lastSweep = health ? (ago(health.finished_at || health.started_at) || '—') : 'no sweep recorded yet'
  const healthTip = failing
    ? `${nC} compan${nC === 1 ? 'y' : 'ies'} and ${nS} search${nS === 1 ? '' : 'es'} need attention. Click → Stats · Run history.`
    : health?.status === 'failed'
      ? `No company or search is failing, but the last scrape sweep failed · ${lastSweep}. Click → Stats · Run history.`
      : `All companies and searches healthy · last sweep ${lastSweep}. Click → Stats · Run history.`

  const W = open ? 206 : 50
  const padX = open ? 20 : 13
  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'} style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <aside style={{ width: W, flex: `0 0 ${W}px`, background: 'var(--rail)', display: 'flex', flexDirection: 'column', padding: '0 0 8px', transition: 'width .32s ease', overflow: 'hidden' }}>
        <div style={{ height: 64, flex: '0 0 auto', position: 'relative', display: 'flex', alignItems: 'center', padding: `0 ${padX}px`, color: 'var(--rail-ink)', whiteSpace: 'nowrap', transition: 'padding .32s ease' }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.01em', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>JobNavigator</span>
          <span style={{ position: 'absolute', left: 0, width: W, display: 'flex', justifyContent: 'center', fontFamily: 'var(--serif)', fontSize: 17, letterSpacing: '.02em', opacity: open ? 0 : 1, transition: 'opacity .2s, width .32s ease', pointerEvents: 'none' }}>JN</span>
        </div>

        <nav className="v2-railscroll" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, padding: '6px 0', overflowX: 'hidden', overflowY: 'auto' }}>
          {GROUPS.map((g) => (
            <div key={g.label} style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ position: 'relative', height: 18, padding: '0 20px', marginBottom: 4, display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
                <span style={{ fontSize: 10, lineHeight: '18px', letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--rail-dim)', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>{g.label}</span>
                <span style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', width: 16, height: 1, background: 'var(--rail-line)', opacity: open ? 0 : 1, transition: 'opacity .2s', pointerEvents: 'none' }} />
              </div>
              {g.items.map((it) => {
                const active = loc.pathname === it.to || loc.pathname.startsWith(it.to + '/')
                const count = it.countKey != null ? counts[it.countKey] : undefined
                const warned = it.warnKey ? (warn[it.warnKey] || 0) > 0 : false
                const { Icon } = it
                const tip = open ? undefined : `${it.label}${count != null ? ` · ${count}` : ''}${warned ? ' · needs attention' : ''}`
                const base = {
                  position: 'relative', display: 'flex', alignItems: 'center', height: 34,
                  // the 3px left border is inside the 50px column, so collapsed
                  // padding is asymmetric to keep the icon on the axis; each
                  // left padding is 1px short of its old value so widening the
                  // accent from 2px to 3px doesn't shift the label
                  padding: open ? `0 ${padX}px 0 ${padX - 1}px` : '0 13px 0 10px',
                  fontSize: 14, whiteSpace: 'nowrap', borderLeft: `3px solid ${active ? 'var(--rail-accent)' : 'transparent'}`,
                  background: active ? 'var(--rail-active)' : 'transparent', transition: 'padding .32s ease',
                }
                const inner = (
                  <>
                    <span style={{ flex: `0 0 ${open ? 0 : 24}px`, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: open ? 'flex-start' : 'center', opacity: open ? 0 : 1, transition: 'opacity .2s, flex-basis .32s ease' }}>
                      <Icon size={15} strokeWidth={1.8} />
                    </span>
                    <span style={{ flex: open ? 1 : '0 0 0px', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>{it.label}</span>
                    {/* the slot is reserved at its final width while the count is
                        in flight — an empty span, never a placeholder 0, so the
                        label doesn't shift when the number lands */}
                    {it.countKey != null && <span style={{ flex: '0 0 auto', minWidth: open ? 18 : 0, width: open ? undefined : 0, textAlign: 'right', overflow: 'hidden', fontFamily: 'var(--mono)', fontSize: 11, color: active ? 'var(--rail-accent)' : 'var(--rail-dim)', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>{count != null ? count : ''}</span>}
                    {!open && warned && <span title="Needs attention" style={{ position: 'absolute', top: 8, left: 'calc(50% + 5px)', width: 5, height: 5, borderRadius: 99, background: 'var(--warn)' }} />}
                  </>
                )
                if (it.external) return <a key={it.to} href={it.to} target="_blank" rel="noopener noreferrer" title={tip} className="v2-navdark" style={{ ...base, color: 'var(--rail-text)' }}>{inner}</a>
                if (!it.ready) return <div key={it.to} title={tip || 'Coming in the redesign'} style={{ ...base, color: 'var(--rail-dim)', cursor: 'default' }}>{inner}</div>
                return <NavLink key={it.to} to={it.to} title={tip} className="v2-navdark" style={{ ...base, color: active ? 'var(--rail-ink)' : 'var(--rail-text)' }}>{inner}</NavLink>
              })}
            </div>
          ))}
        </nav>

        <a href="/" className="v2-navdark" title={open ? undefined : 'Classic UI'} style={{ display: 'flex', alignItems: 'center', height: 30, padding: `0 ${padX}px`, fontSize: 12, color: 'var(--rail-dim)', whiteSpace: 'nowrap', transition: 'padding .32s ease' }}>
          <span style={{ flex: `0 0 ${open ? 0 : 24}px`, display: 'flex', justifyContent: 'center', overflow: 'hidden', opacity: open ? 0 : 1, transition: 'opacity .2s, flex-basis .32s ease' }}>←</span>
          <span style={{ opacity: open ? 1 : 0, transition: 'opacity .2s' }}>← Classic UI</span>
        </a>

        {/* pipeline pulse — the dot yields its slot to the theme toggle when collapsed */}
        {/* STAT-16: the tooltip promises Run history, the last card on the page — deep-link to it */}
        <div onClick={() => navigate('/v2/stats#runs')} title={healthTip} className="v2-navdark" style={{ display: 'flex', alignItems: 'center', height: 30, padding: `0 ${padX}px`, cursor: 'pointer', whiteSpace: 'nowrap', transition: 'padding .32s ease' }}>
          <span style={{ flex: '0 0 24px', display: 'flex', justifyContent: open ? 'flex-start' : 'center' }}>
            {open
              ? <span style={{ width: 7, height: 7, borderRadius: 99, background: healthy ? 'var(--rail-accent)' : 'var(--warn)' }} />
              : <span onClick={(e) => { e.stopPropagation(); toggleTheme() }} title={`Switch to ${dark ? 'light' : 'dark'} mode`} style={{ fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer' }}>◐</span>}
          </span>
          <span style={{ fontSize: 11.5, lineHeight: '18px', color: 'var(--rail-dim)', opacity: open ? 1 : 0, transition: 'opacity .2s', overflow: 'hidden', textOverflow: 'ellipsis' }}>{healthText}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', height: 34, padding: `0 12px 0 ${padX}px`, borderTop: '1px solid var(--rail-line)', whiteSpace: 'nowrap', transition: 'padding .32s ease' }}>
          <span onClick={toggleRail} title={open ? 'Collapse to icons' : 'Expand navigation'} className="v2-navdark" style={{ flex: '0 0 24px', fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer', display: 'flex', justifyContent: open ? 'flex-start' : 'center' }}>{open ? '‹' : '›'}</span>
          <span onClick={toggleRail} className="v2-navdark" style={{ flex: 1, fontSize: 12, lineHeight: '18px', color: 'var(--rail-dim)', cursor: 'pointer', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>Collapse</span>
          <span onClick={toggleTheme} title={`Switch to ${dark ? 'light' : 'dark'} mode`} className="v2-navdark v2-themebtn" style={{ flex: '0 0 auto', width: 26, height: 26, borderRadius: 99, display: open ? 'flex' : 'none', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer' }}>◐</span>
        </div>
      </aside>
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Outlet />
      </main>
    </div>
  )
}
