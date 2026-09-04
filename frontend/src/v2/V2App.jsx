import React, { useState, useEffect, useCallback, useRef } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Newspaper, Search, Building2, Send, FileUser, Mail,
  Fingerprint, ChartLine, Settings as SettingsIcon,
} from 'lucide-react'
import api from '../api'
import { useTheme, themeAttrs, appearanceTitle, MODE_ICON } from './theme'
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

// Warm start. The badges and the health signal are the same on the frame after a
// refresh as they were before it, so they are cached and read back synchronously
// in the initial state — the rail paints with its numbers instead of popping them
// in one endpoint at a time. A miss (first ever load, cleared storage) just leaves
// the slots empty until the single settle below.
// NB `jobnavigator_v2_rail` is taken: it holds the expanded/collapsed state.
const CACHE_KEY = 'jobnavigator_v2_railcache'
const COUNT_KEYS = ['jobs', 'searches', 'companies', 'apps', 'resumes', 'letters']
// only the three fields the rail reads — a whole JobRun row has no business in
// localStorage, and a slim shape keeps the equality check honest
const slimHealth = (h) => (h ? { status: h.status, started_at: h.started_at, finished_at: h.finished_at } : null)
const readCache = () => {
  try {
    const v = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')
    return v && typeof v === 'object' ? v : {}
  } catch { return {} }
}
const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {})
const sameCounts = (a, b) => COUNT_KEYS.every((k) => a[k] === b[k])
const sameWarn = (a, b) => (a.companies || 0) === (b.companies || 0) && (a.searches || 0) === (b.searches || 0)
const sameHealth = (a, b) => (!a && !b) || !!(a && b && a.status === b.status && a.started_at === b.started_at && a.finished_at === b.finished_at)

export default function V2App() {
  const loc = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('jobnavigator_v2_rail') !== 'collapsed' } catch { return true } })
  // one read of the warm-start snapshot, before the first paint
  const [boot] = useState(readCache)
  const [counts, setCounts] = useState(() => obj(boot.counts))
  const [warn, setWarn] = useState(() => obj(boot.warn))
  const [health, setHealth] = useState(() => slimHealth(boot.health))
  // a badge that comes back different from its cached value fades in rather than
  // swapping hard: the span renders at .6 for one frame, then transitions to 1.
  // Unchanged badges never dim, so a routine refresh is invisible.
  const [fade, setFade] = useState(false)
  const countsRef = useRef(counts)
  const warnRef = useRef(warn)
  const healthRef = useRef(health)
  const rafRef = useRef([])
  const flash = useCallback(() => {
    rafRef.current.forEach((id) => cancelAnimationFrame(id)); rafRef.current = []
    setFade(true)
    // two frames: the first guarantees a painted frame at .6, the second starts
    // the transition back up. One frame alone can be coalesced away.
    rafRef.current = [requestAnimationFrame(() => { rafRef.current = [requestAnimationFrame(() => setFade(false))] })]
  }, [])
  useEffect(() => () => { rafRef.current.forEach((id) => cancelAnimationFrame(id)) }, [])
  // One store for both axes (theme.js) — the rail, the two global overlays and
  // the classic shell all read it, so a click here moves every one of them
  // without a reload (SHELL-02 / SHELL-06).
  const look = useTheme()
  const appearanceTip = appearanceTitle(look.mode)
  const toggleRail = () => setOpen((v) => { const n = !v; try { localStorage.setItem('jobnavigator_v2_rail', n ? 'expanded' : 'collapsed') } catch {} return n })

  const loadCounts = useCallback(() => {
    const len = (d) => (Array.isArray(d) ? d.length : undefined)
    // One settle, not six. Every badge lands in a single setCounts, so the rail
    // reconciles once instead of re-rendering per endpoint; a request that fails
    // leaves its cached number in place rather than blanking the slot.
    Promise.allSettled([
      api.get('/jobs', { params: { status: 'new', limit: 1 } }),
      api.get('/resumes', { params: { is_base: true } }),
      // /applications returns {applications, total} — ask for one row and read the
      // total, so this count no longer trails the others by ~half a second
      api.get('/applications', { params: { limit: 1 } }),
      api.get('/companies'),
      api.get('/searches'),
      api.get('/cover-letters'),
    ]).then((r) => {
      const data = (i) => (r[i].status === 'fulfilled' ? r[i].value?.data : undefined)
      const prev = countsRef.current
      const next = { ...prev }
      if (r[0].status === 'fulfilled') next.jobs = data(0)?.total
      if (r[1].status === 'fulfilled') next.resumes = len(data(1))
      if (r[2].status === 'fulfilled') { const d = data(2); next.apps = Array.isArray(d) ? d.length : d?.total }
      if (r[3].status === 'fulfilled') next.companies = len(data(3))
      if (r[4].status === 'fulfilled') next.searches = len(data(4))
      if (r[5].status === 'fulfilled') next.letters = len(data(5))
      if (sameCounts(next, prev)) return  // the cache was right: no render, no fade
      const warmed = COUNT_KEYS.some((k) => prev[k] != null)
      countsRef.current = next
      setCounts(next)
      if (warmed) flash()  // first ever load has nothing to cross-fade from
    }).catch(() => { /* silent: a nav badge — the screen behind it owns the error state */ })
    // the health pair settles together too — the dot and its line are one signal:
    // sources needing attention, and the last scrape sweep however it ended
    Promise.allSettled([
      api.get('/health/entities'),
      api.get('/monitor/history', { params: { limit: 1, job_type: 'scrape_all' } }),
    ]).then(([w, h]) => {
      if (w.status === 'fulfilled') {
        const d = w.value?.data
        const nw = { companies: (d?.companies || []).length, searches: (d?.searches || []).length }
        if (!sameWarn(nw, warnRef.current)) { warnRef.current = nw; setWarn(nw) }
      }
      if (h.status === 'fulfilled') {
        const nh = slimHealth((h.value?.data || [])[0] || null)
        if (!sameHealth(nh, healthRef.current)) { healthRef.current = nh; setHealth(nh) }
      }
    }).catch(() => { /* silent: the rail's health line — it just stays as it was */ })
  }, [flash])
  // APPS-19: screens dispatch jn:counts-changed after a create/delete so the badges follow
  useEffect(() => { loadCounts(); window.addEventListener('jn:counts-changed', loadCounts); return () => window.removeEventListener('jn:counts-changed', loadCounts) }, [loadCounts])
  // keep the warm-start snapshot current — best effort, never a blocker
  useEffect(() => { try { localStorage.setItem(CACHE_KEY, JSON.stringify({ counts, warn, health })) } catch {} }, [counts, warn, health])

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
  const lastSweep = health ? (ago(health.finished_at || health.started_at) || '—') : 'no scrape run recorded yet'
  const healthTip = failing
    ? `${nC} compan${nC === 1 ? 'y' : 'ies'} and ${nS} search${nS === 1 ? '' : 'es'} need attention. Click to open Run history.`
    : health?.status === 'failed'
      ? `All companies and searches are healthy, but the last scrape run failed ${lastSweep}. Click to open Run history.`
      : `All companies and searches healthy · last scrape run ${lastSweep}. Click to open Run history.`

  const W = open ? 206 : 50
  const padX = open ? 20 : 13
  return (
    <div className="jn-v2" {...themeAttrs(look)} style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
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
                {/* ui: keep — a rail hairline on --rail-line; Rule reads the --head-line
                    pair, which is the light-surface rule, not the dark rail's */}
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
                  fontSize: 14, whiteSpace: 'nowrap',
                  // the active item is a token set, not a hard-coded bar: the
                  // default theme keeps its 3px accent edge on a faint wash
                  // (--rail-active-mark / --rail-active-bg), saas and cobalt swap
                  // the mark for `none` and fill an inset, rounded tile instead.
                  // The inactive item holds the same 3px in transparent so the
                  // labels stay on one axis whichever the theme picks.
                  borderLeft: active ? 'var(--rail-active-mark)' : '3px solid transparent',
                  borderRadius: 'var(--radius-rail-item)', margin: 'var(--rail-item-inset)',
                  background: active ? 'var(--rail-active-bg)' : 'transparent', transition: 'padding .32s ease',
                }
                const inner = (
                  <>
                    <span style={{ flex: `0 0 ${open ? 0 : 24}px`, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: open ? 'flex-start' : 'center', opacity: open ? 0 : 1, transition: 'opacity .2s, flex-basis .32s ease' }}>
                      <Icon size={15} strokeWidth={1.8} />
                    </span>
                    <span style={{ flex: open ? 1 : '0 0 0px', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>{it.label}</span>
                    {/* the slot is reserved at its final width while the count is
                        in flight — an empty span, never a placeholder 0, so the
                        label doesn't shift when the number lands. A reconciled
                        value arrives at .6 and fades up: same box, no jump. */}
                    {it.countKey != null && <span style={{ flex: '0 0 auto', minWidth: open ? 18 : 0, width: open ? undefined : 0, textAlign: 'right', overflow: 'hidden', fontFamily: 'var(--mono)', fontSize: 11, color: active ? 'var(--rail-accent)' : 'var(--rail-dim)', opacity: open ? (fade ? .6 : 1) : 0, transition: 'opacity .15s' }}>{count != null ? count : ''}</span>}
                    {/* ui: keep — 5px "needs attention" rail dot, not a control */}
                    {!open && warned && <span title="Needs attention" style={{ position: 'absolute', top: 8, left: 'calc(50% + 5px)', width: 5, height: 5, borderRadius: 'var(--radius-control)', background: 'var(--warn)' }} />}
                  </>
                )
                if (it.external) return <a key={it.to} href={it.to} target="_blank" rel="noopener noreferrer" title={tip} className="v2-navdark" style={{ ...base, color: 'var(--rail-text)' }}>{inner}</a>
                if (!it.ready) return <div key={it.to} title={tip || 'Coming in the redesign'} style={{ ...base, color: 'var(--rail-dim)', cursor: 'default' }}>{inner}</div>
                return <NavLink key={it.to} to={it.to} title={tip} className="v2-navdark" style={{ ...base, color: active ? 'var(--rail-active-ink)' : 'var(--rail-text)' }}>{inner}</NavLink>
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
              /* ui: keep — 7px scrape-health rail dot, not a control */
              ? <span style={{ width: 7, height: 7, borderRadius: 'var(--radius-control)', background: healthy ? 'var(--rail-accent)' : 'var(--warn)' }} />
              /* the ◐ cycles Light -> Dark -> System; the glyph names the mode
                 it is in, the tooltip spells it out (Nav Rail spec) */
              : <span onClick={(e) => { e.stopPropagation(); look.cycle() }} title={appearanceTip} style={{ fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer' }}>{MODE_ICON[look.mode]}</span>}
          </span>
          <span style={{ fontSize: 11.5, lineHeight: '18px', color: 'var(--rail-dim)', opacity: open ? 1 : 0, transition: 'opacity .2s', overflow: 'hidden', textOverflow: 'ellipsis' }}>{healthText}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', height: 34, padding: `0 12px 0 ${padX}px`, borderTop: '1px solid var(--rail-line)', whiteSpace: 'nowrap', transition: 'padding .32s ease' }}>
          <span onClick={toggleRail} title={open ? 'Collapse to icons' : 'Expand navigation'} className="v2-navdark" style={{ flex: '0 0 24px', fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer', display: 'flex', justifyContent: open ? 'flex-start' : 'center' }}>{open ? '‹' : '›'}</span>
          <span onClick={toggleRail} className="v2-navdark" style={{ flex: 1, fontSize: 12, lineHeight: '18px', color: 'var(--rail-dim)', cursor: 'pointer', opacity: open ? 1 : 0, transition: 'opacity .2s' }}>Collapse</span>
          {/* ui: keep — rail-dark theme toggle (--rail-dim ink, v2-navdark + v2-appearancebtn rail hovers); IconButton reads the light-surface tokens */}
          <span onClick={look.cycle} title={appearanceTip} className="v2-navdark v2-appearancebtn" style={{ flex: '0 0 auto', width: 26, height: 26, borderRadius: 'var(--radius-control)', display: open ? 'flex' : 'none', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--rail-dim)', cursor: 'pointer' }}>{MODE_ICON[look.mode]}</span>
        </div>
      </aside>
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Outlet />
      </main>
    </div>
  )
}
