import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import api from '../api'
import './theme.css'

// ── helpers ──────────────────────────────────────────────────────────────────
const ago = (iso) => {
  if (!iso) return 'never'
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}
const norm = (s) => (s || '').toLowerCase().replace(/\s+/g, '')

// ATS + tier chip colors live in theme.css (.cc-*) so they flip with dark mode.
const ATS_SLUGS = new Set(['greenhouse', 'workday', 'lever', 'ashby', 'phenom', 'oraclehcm', 'smartrecruiters', 'rippling', 'eightfold', 'talentbrew', 'meta', 'google'])
const atsShort = (detected) => (detected || 'Generic')
  .replace(' API', '').replace(' AJAX', '').replace(' (Playwright)', '').replace(' Careers', '')
const atsSlug = (short) => { const s = (short || 'generic').toLowerCase().replace(/[^a-z0-9]/g, ''); return 'cc-' + (ATS_SLUGS.has(s) ? s : 'generic') }
const tierSlug = (key) => 'cc-tier' + (key === 'none' ? 'none' : key)

// client-side ATS detection (mirror of backend detect, for live editor chips)
const hostMatches = (url, ...domains) => {
  let host; try { host = new URL(url).hostname.toLowerCase() } catch { return false }
  return domains.some((d) => d && (host === d || host.endsWith('.' + d)))
}
const pathHas = (url, ...needles) => {
  let p; try { p = new URL(url).pathname.toLowerCase() } catch { return false }
  return needles.some((n) => n && p.includes(n))
}
const detectAts = (url) => {
  if (!url) return 'Generic'
  if (url.toUpperCase().startsWith('POST|')) return 'Phenom'
  if (hostMatches(url, 'myworkdayjobs.com')) return 'Workday'
  if (hostMatches(url, 'oraclecloud.com') && pathHas(url, '/hcmui/')) return 'Oracle HCM'
  if (hostMatches(url, 'careers.oracle.com')) return 'Oracle HCM'
  if (hostMatches(url, 'jobs.lever.co', 'jobs.eu.lever.co')) return 'Lever'
  if (hostMatches(url, 'jobs.ashbyhq.com')) return 'Ashby'
  if (hostMatches(url, 'greenhouse.io')) return 'Greenhouse'
  if (hostMatches(url, 'ats.rippling.com') || (hostMatches(url, 'rippling.com') && pathHas(url, '/careers'))) return 'Rippling'
  if (hostMatches(url, 'jobs.smartrecruiters.com', 'careers.smartrecruiters.com', 'api.smartrecruiters.com')) return 'SmartRecruiters'
  if (hostMatches(url, 'eightfold.ai')) return 'Eightfold'
  if (hostMatches(url, 'metacareers.com')) return 'Meta'
  if (hostMatches(url, 'google.com') && pathHas(url, '/about/careers')) return 'Google'
  return 'Generic'
}

const SORT_OPTIONS = [
  { id: 'health', label: 'Needs attention', hint: 'Warnings, then active, then inactive' },
  { id: 'name', label: 'Company name', hint: 'A to Z' },
  { id: 'tier', label: 'Priority tier', hint: 'Tier 1 first, untiered last' },
  { id: 'open', label: 'Open roles', hint: 'Most roles in the feed first' },
  { id: 'fit', label: 'Average fit', hint: 'Best-scoring companies first' },
  { id: 'run', label: 'Last scrape', hint: 'Longest since a run first' },
]
const DEPTHS = [
  { id: 'off', label: 'Off', hint: 'New jobs are stored unscored' },
  { id: 'light', label: 'Light', hint: 'Scores only, no report' },
  { id: 'full', label: 'Full', hint: 'Full report with keywords and requirements' },
]
const TIER_BTNS = [{ v: 1, label: '1' }, { v: 2, label: '2' }, { v: 3, label: '3' }, { v: null, label: 'None' }]

const inputBox = { width: '100%', minHeight: 32, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 7, background: 'var(--surface)', color: 'var(--text)', fontSize: 12, outline: 'none', fontFamily: 'var(--sans)' }
const monoBox = { ...inputBox, fontFamily: 'var(--mono)', fontSize: 10.5 }
const helpTxt = { fontSize: 10.5, color: 'var(--muted)' }
const fieldLabel = { fontSize: 11.5, fontWeight: 500, color: 'var(--text)' }

// ── URL list editor (drawer + add) ───────────────────────────────────────────
function UrlEditor({ urls, onChange }) {
  const set = (i, v) => { const u = [...urls]; u[i] = v; onChange(u) }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {urls.map((u, i) => {
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span className={atsSlug(detectAts(u))} style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.05em', padding: '3px 8px', borderRadius: 99, whiteSpace: 'nowrap' }}>{detectAts(u)}</span>
            <input value={u} onChange={(e) => set(i, e.target.value)} placeholder="https://boards.greenhouse.io/company"
              style={{ ...monoBox, flex: 1, height: 32, minHeight: 0 }} />
            <span title="Remove this URL" onClick={() => onChange(urls.filter((_, j) => j !== i))} className="v2-hover-bad"
              style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)', cursor: 'pointer', padding: 2, borderRadius: 4 }}>✕</span>
          </div>
        )
      })}
      <div onClick={() => onChange([...urls, ''])} className="v2-dashadd"
        style={{ height: 30, border: '1px dashed var(--edge)', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11.5, color: 'var(--muted)', cursor: 'pointer' }}>+ Add another career page</div>
    </div>
  )
}

const Seg = ({ opts, value, onPick, valueKey = 'id', big }) => (
  <div style={{ display: 'flex', gap: big ? 6 : 5 }}>
    {opts.map((o) => {
      const v = o[valueKey] !== undefined ? o[valueKey] : o.v
      const on = value === v
      return (
        <div key={String(v)} onClick={() => onPick(v)} title={o.hint || ''} className="v2-bd"
          style={{ flex: 1, height: 32, border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: on ? 600 : 400, cursor: 'pointer' }}>{o.label}</div>
      )
    })}
  </div>
)

const ResumeChips = ({ resumes, personaPopulated, selected, toggle }) => (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
    {resumes.map((r) => {
      const on = selected.includes(r.id)
      return <div key={r.id} onClick={() => toggle(r.id)} className="v2-bd" style={{ height: 27, padding: '0 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, cursor: 'pointer', whiteSpace: 'nowrap' }}>{r.name}</div>
    })}
    {personaPopulated && (() => { const on = selected.includes('persona'); return (
      <div onClick={() => toggle('persona')} className="v2-bd" style={{ height: 27, padding: '0 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, cursor: 'pointer' }}>Persona</div>
    ) })()}
  </div>
)

// ── main screen ──────────────────────────────────────────────────────────────
export default function Companies() {
  const [companies, setCompanies] = useState([])
  const [resumes, setResumes] = useState([])
  const [personaPopulated, setPersonaPopulated] = useState(false)
  const [downMap, setDownMap] = useState({})
  const [scraping, setScraping] = useState({})       // company id -> true while running
  const [query, setQuery] = useState(() => { try { return localStorage.getItem('company_query') || '' } catch { return '' } })
  const [tiers, setTiers] = useState(() => { try { return JSON.parse(localStorage.getItem('company_filter_tiers')) || [] } catch { return [] } })
  const [sortBy, setSortBy] = useState(() => { try { return localStorage.getItem('company_sort') || 'health' } catch { return 'health' } })
  const [sortOpen, setSortOpen] = useState(false)
  const [menuId, setMenuId] = useState(null)
  const [drawer, setDrawer] = useState(null)          // {company, draft}
  const [addOpen, setAddOpen] = useState(false)
  const [test, setTest] = useState(null)              // test-scrape result
  const [testingId, setTestingId] = useState(null)
  const [showShots, setShowShots] = useState(false)

  const fetchCompanies = useCallback(async () => {
    try { const { data } = await api.get('/companies'); setCompanies(data) } catch (e) { console.error(e) }
  }, [])
  useEffect(() => {
    fetchCompanies()
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(Array.isArray(data) ? data : [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersonaPopulated(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
    api.get('/health/entities').then(({ data }) => { const m = {}; (data.companies || []).forEach((c) => { m[c.id] = c.reason }); setDownMap(m) }).catch(() => {})
    api.get('/monitor/active').then(({ data }) => { const m = {}; (data || []).forEach((r) => { if (r.scope_key) m[r.scope_key] = true }); setScraping(m) }).catch(() => {})
  }, [fetchCompanies])
  useEffect(() => { try { localStorage.setItem('company_filter_tiers', JSON.stringify(tiers)) } catch {} }, [tiers])
  useEffect(() => { try { localStorage.setItem('company_query', query) } catch {} }, [query])
  useEffect(() => { try { localStorage.setItem('company_sort', sortBy) } catch {} }, [sortBy])

  // close menus on outside click / escape
  useEffect(() => {
    const onDoc = () => { setSortOpen(false); setMenuId(null) }
    const onKey = (e) => { if (e.key === 'Escape') { setSortOpen(false); setMenuId(null); setDrawer(null); setAddOpen(false); setTest(null) } }
    document.addEventListener('click', onDoc); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', onDoc); document.removeEventListener('keydown', onKey) }
  }, [])

  // ── derived ──
  const tierKey = (c) => (c.tier == null ? 'none' : String(c.tier))
  const tierCounts = useMemo(() => {
    const m = { 1: 0, 2: 0, 3: 0, none: 0 }
    companies.forEach((c) => { m[tierKey(c)]++ })
    return m
  }, [companies])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    let list = companies.filter((c) => {
      if (tiers.length && !tiers.includes(tierKey(c))) return false
      if (!q) return true
      const hay = [c.name, ...(c.aliases || []), ...(c.scrape_urls || []), ...Object.values(c.detected_scrape_types || {})].join(' ').toLowerCase()
      return hay.includes(q)
    })
    const down = (c) => !!downMap[c.id]
    const cmp = {
      health: (a, b) => (down(b) - down(a)) || ((b.active ? 1 : 0) - (a.active ? 1 : 0)) || a.name.localeCompare(b.name),
      name: (a, b) => a.name.localeCompare(b.name),
      tier: (a, b) => (a.tier ?? 99) - (b.tier ?? 99) || a.name.localeCompare(b.name),
      open: (a, b) => (b.open_jobs || 0) - (a.open_jobs || 0) || a.name.localeCompare(b.name),
      fit: (a, b) => (b.avg_fit ?? -1) - (a.avg_fit ?? -1) || a.name.localeCompare(b.name),
      run: (a, b) => (new Date(a.last_scraped_at || 0)) - (new Date(b.last_scraped_at || 0)) || a.name.localeCompare(b.name),
    }[sortBy] || (() => 0)
    return [...list].sort(cmp)
  }, [companies, query, tiers, sortBy, downMap])

  const activeCount = companies.filter((c) => c.active).length
  const downCount = companies.filter((c) => downMap[c.id]).length
  const countLine = `${companies.length} tracked · ${activeCount} active · ${downCount} need attention`
  const inactiveInFilter = filtered.filter((c) => !c.active)
  const activeInFilter = filtered.filter((c) => c.active)
  const bulkHint = tiers.length || query.trim()
    ? `Applies to the ${filtered.length} companies in the current filter · jobs already found are kept`
    : `Applies to all ${filtered.length} companies · jobs already found are kept`

  // ── actions ──
  const patchCompany = async (id, patch) => { try { await api.patch(`/companies/${id}`, patch); fetchCompanies() } catch (e) { console.error(e) } }
  const bulkSet = async (active) => {
    const targets = active ? inactiveInFilter : activeInFilter
    await Promise.all(targets.map((c) => api.patch(`/companies/${c.id}`, { active }).catch(() => {})))
    fetchCompanies()
  }
  const runScrape = async (id) => {
    setScraping((m) => ({ ...m, [id]: true }))
    try { await api.post(`/scrape/company/${id}`) } catch (e) { console.error(e) }
    setTimeout(() => { setScraping((m) => { const n = { ...m }; delete n[id]; return n }); fetchCompanies() }, 2600)
  }
  const runTest = async (id) => {
    setTestingId(id); setShowShots(false)
    try { const { data } = await api.post(`/companies/${id}/test-scrape`); setTest(data) }
    catch (e) { setTest({ error: e.response?.data?.detail || e.message }) }
    setTestingId(null)
  }
  const deleteCompany = async (c) => {
    if (!window.confirm(`Delete ${c.name}? Jobs already found are kept.`)) return
    try { await api.delete(`/companies/${c.id}`); setMenuId(null); setDrawer(null); fetchCompanies() } catch (e) { console.error(e) }
  }

  // ── row cell derivations ──
  const resumeNames = (c) => {
    const ids = c.selected_resume_ids || []
    if (!ids.length) return null
    const names = resumes.filter((r) => ids.includes(r.id)).map((r) => r.name)
    if (ids.includes('persona')) names.push('Persona')
    return names.join(', ') || 'Selected'
  }
  const healthOf = (c) => {
    if (scraping[c.id]) return { dot: 'var(--accent)', fg: 'var(--accent)', text: 'scraping now…' }
    if (downMap[c.id]) return { dot: 'var(--warn)', fg: 'var(--warn)', text: downMap[c.id] }
    if (c.active) return { dot: 'var(--good)', fg: 'var(--text-2)', text: `healthy · scraped ${ago(c.last_scraped_at)}` }
    return { dot: 'var(--edge)', fg: 'var(--muted)', text: `inactive · last run ${ago(c.last_scraped_at)}` }
  }
  const fitColor = (f) => (f == null ? 'var(--muted)' : f >= 80 ? 'var(--good)' : f >= 65 ? 'var(--text-2)' : 'var(--warn)')

  const clearFilters = () => { setQuery(''); setTiers([]) }
  const openDrawer = (c) => setDrawer({
    company: c,
    draft: {
      name: c.name, aliases: (c.aliases || []).join(', '),
      scrape_urls: [...(c.scrape_urls || [])],
      title_include_expr: c.title_include_expr || '',
      title_exclude_keywords: (c.title_exclude_keywords || []).join(', '),
      auto_scoring_depth: c.auto_scoring_depth || 'off',
      selected_resume_ids: [...(c.selected_resume_ids || [])],
      tier: c.tier, scrape_interval_minutes: c.scrape_interval_minutes ?? '',
      wait_for_selector: c.wait_for_selector || '', max_pages: c.max_pages ?? 5,
      h1b_slug: c.h1b_slug || '', active: c.active,
    },
  })

  return (
    <div className="v2-scroll" style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* header — title + subtitle, matching The Feed */}
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px 24px', display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Companies</h1>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div onClick={() => setAddOpen(true)} style={{ height: 36, padding: '0 18px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, cursor: 'pointer' }}>+ Add company</div>
        </div>
      </header>

      {/* toolbar */}
      <div style={{ flex: '0 0 auto', padding: '2px 30px 12px 24px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ position: 'relative', flex: '0 0 226px', display: 'flex', alignItems: 'center' }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: 'var(--muted)', pointerEvents: 'none' }}>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, alias, URL or ATS…"
            style={{ width: '100%', height: 30, padding: '0 12px 0 29px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', fontSize: 12, color: 'var(--text)', outline: 'none', fontFamily: 'var(--sans)' }} />
        </span>
        <div style={{ flex: '0 0 auto', width: 1, height: 20, background: 'var(--line)', margin: '0 3px' }} />
        {['1', '2', '3', 'none'].map((t) => {
          const on = tiers.includes(t)
          return (
            <div key={t} onClick={() => setTiers((p) => p.includes(t) ? p.filter((x) => x !== t) : [...p, t])}
              title="Add/remove from filter · multi-select, remembered per browser" className="v2-bd"
              style={{ flex: '0 0 auto', height: 30, padding: '0 13px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: on ? 600 : 400, whiteSpace: 'nowrap', cursor: 'pointer' }}>
              {t === 'none' ? 'Untiered' : `Tier ${t}`}<span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, opacity: 0.7, position: 'relative', top: 1 }}>{tierCounts[t]}</span>
            </div>
          )
        })}
        <div style={{ flex: '0 0 auto', width: 1, height: 20, background: 'var(--line)', margin: '0 2px' }} />
        {inactiveInFilter.length > 0 && (
          <div onClick={() => bulkSet(true)} title={bulkHint} className="v2-act"
            style={{ flex: '0 0 auto', height: 30, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--accent)', whiteSpace: 'nowrap', cursor: 'pointer' }}>Make {inactiveInFilter.length} active</div>
        )}
        {activeInFilter.length > 0 && (
          <div onClick={() => bulkSet(false)} title={bulkHint} className="v2-bd-warn"
            style={{ flex: '0 0 auto', height: 30, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--warn)', whiteSpace: 'nowrap', cursor: 'pointer' }}>Make {activeInFilter.length} inactive</div>
        )}
        <span style={{ marginLeft: 'auto', flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
            <div onClick={() => setSortOpen((v) => !v)} title="Change row order"
              style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>
              Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORT_OPTIONS.find((s) => s.id === sortBy)?.label}</span><span style={{ fontSize: 10 }}>▾</span>
            </div>
            {sortOpen && (
              <div className="v2-scroll" style={{ position: 'absolute', top: '100%', right: 0, zIndex: 45, marginTop: 5, width: 172, background: 'var(--surface)', border: '1px solid var(--edge)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 8, display: 'flex', flexDirection: 'column' }}>
                {SORT_OPTIONS.map((so) => {
                  const on = so.id === sortBy
                  return (
                    <div key={so.id} onClick={() => { setSortBy(so.id); setSortOpen(false) }} title={so.hint} className="v2-menuitem"
                      style={{ display: 'flex', alignItems: 'center', padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', color: on ? 'var(--accent)' : 'var(--text-2)', fontWeight: on ? 500 : 400, background: on ? 'var(--accent-soft)' : 'transparent' }}>
                      {so.label}{on && <span style={{ marginLeft: 'auto' }}>✓</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </span>
        </span>
      </div>

      {/* rows (column header lives inside the scroll container so its width
          tracks the rows' — otherwise the body scrollbar shifts every column) */}
      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <div style={{ position: 'sticky', top: 0, zIndex: 3, display: 'flex', alignItems: 'center', height: 30, padding: '0 30px 0 24px', background: 'var(--bg)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', fontSize: 9.5, letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }}>
          <span style={{ flex: 1, minWidth: 118 }}>Company</span>
          <span style={{ flex: '0 0 62px' }}>Tier</span>
          <span style={{ flex: 1.9, minWidth: 210 }}>Health</span>
          <span style={{ flex: '0 0 132px' }} title="Which résumés new jobs from this company are scored against">Résumés</span>
          <span style={{ flex: '0 0 108px' }} title="ATS detected from the career URLs">ATS</span>
          <span style={{ flex: '0 0 74px', textAlign: 'right', paddingRight: 10 }} title="Open roles in the Job Feed · new in the last 7 days">Open · 7d</span>
          <span style={{ flex: '0 0 46px', textAlign: 'right', paddingRight: 10 }} title="Open applications">Apps</span>
          <span style={{ flex: '0 0 48px', textAlign: 'right', paddingRight: 14 }} title="Average fit across this company's scored roles">Ø Fit</span>
          <span style={{ flex: '0 0 88px', textAlign: 'center' }}>Status</span>
          <span style={{ flex: '0 0 190px' }} />
        </div>
        {filtered.map((c) => {
          const h = healthOf(c)
          const rn = resumeNames(c)
          const urls = c.scrape_urls || []
          const firstAts = urls.length ? atsShort(c.detected_scrape_types?.[urls[0]]) : 'Generic'
          const aliases = c.aliases || []
          return (
            <div key={c.id} onClick={() => openDrawer(c)} className="v2-crow"
              style={{ display: 'flex', alignItems: 'center', height: 46, padding: '0 30px 0 24px', borderBottom: '1px solid var(--line-soft)', cursor: 'pointer' }}>
              {/* company */}
              <span style={{ flex: 1, minWidth: 118, display: 'flex', alignItems: 'center', gap: 7, paddingRight: 10 }}>
                {downMap[c.id] && <span title={`Needs attention — ${downMap[c.id]}`} style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--warn)' }}>▲</span>}
                <span title={c.name} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</span>
                {aliases.length > 1 && <span title={`Also scraped as ${aliases.join(', ')}`} style={{ flex: '0 0 auto', position: 'relative', top: 1, fontSize: 9.5, padding: '1px 5px', borderRadius: 99, background: 'var(--surface-2)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>+{aliases.length - 1}</span>}
              </span>
              {/* tier */}
              <span style={{ flex: '0 0 62px' }}>
                <span className={tierSlug(tierKey(c))} style={{ fontSize: 10, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 8px', borderRadius: 99 }}>{c.tier == null ? '—' : `T${c.tier}`}</span>
              </span>
              {/* health */}
              <span style={{ flex: 1.9, minWidth: 210, display: 'flex', alignItems: 'center', gap: 7, paddingRight: 10 }}>
                <span style={{ flex: '0 0 auto', width: 7, height: 7, borderRadius: 99, background: h.dot }} />
                <span title={h.text} style={{ flex: 1, minWidth: 0, fontSize: 12, color: h.fg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.text}</span>
              </span>
              {/* résumés */}
              <span title={rn || 'Scored against your default résumé from Settings'} style={{ flex: '0 0 132px', fontSize: 11.5, color: rn ? 'var(--text-2)' : 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{rn || 'Default'}</span>
              {/* ats */}
              <span style={{ flex: '0 0 108px', display: 'flex', alignItems: 'center', gap: 6, paddingRight: 10 }}>
                {urls.length > 0 && <span className={atsSlug(firstAts)} title={urls.join('\n')} style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.05em', padding: '2px 7px', borderRadius: 99, whiteSpace: 'nowrap' }}>{firstAts}</span>}
                {urls.length > 1 && <span title={urls.join('\n')} style={{ flex: '0 0 auto', fontSize: 10, color: 'var(--muted)' }}>+{urls.length - 1}</span>}
                {urls.length === 0 && <span style={{ fontSize: 11, color: 'var(--muted)' }}>—</span>}
              </span>
              {/* open · 7d */}
              <span title={`${c.open_jobs || 0} open roles from ${c.name} in the Job Feed · ${c.open_jobs_week || 0} new in the last 7 days`} style={{ flex: '0 0 74px', textAlign: 'right', paddingRight: 10, fontFamily: 'var(--mono)', fontSize: 11.5, color: c.open_jobs ? 'var(--text-2)' : 'var(--muted)' }}>
                {c.open_jobs || 0}<span style={{ color: c.open_jobs_week ? 'var(--good)' : 'var(--muted)' }}> +{c.open_jobs_week || 0}</span>
              </span>
              {/* apps */}
              <span style={{ flex: '0 0 46px', textAlign: 'right', paddingRight: 10, fontFamily: 'var(--mono)', fontSize: 11.5, color: c.application_count ? 'var(--text-2)' : 'var(--muted)' }}>{c.application_count || '·'}</span>
              {/* fit */}
              <span title={c.avg_fit == null ? 'No scored roles yet' : `Average fit ${c.avg_fit} across this company's scored roles`} style={{ flex: '0 0 48px', textAlign: 'right', paddingRight: 14, fontFamily: 'var(--mono)', fontSize: 11.5, color: fitColor(c.avg_fit) }}>{c.avg_fit == null ? '–' : c.avg_fit}</span>
              {/* status */}
              <span style={{ flex: '0 0 88px', display: 'flex', justifyContent: 'center' }}>
                <span onClick={(e) => { e.stopPropagation(); patchCompany(c.id, { active: !c.active }) }} title={c.active ? 'Click to pause scraping' : 'Click to resume scraping'} className="v2-bd"
                  style={{ height: 23, padding: '0 11px', borderRadius: 99, border: `1px solid ${c.active ? 'var(--accent)' : 'var(--edge)'}`, background: c.active ? 'var(--accent-soft)' : 'var(--surface)', color: c.active ? 'var(--accent)' : 'var(--muted)', display: 'flex', alignItems: 'center', fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>{c.active ? 'Active' : 'Inactive'}</span>
              </span>
              {/* actions */}
              <span style={{ flex: '0 0 190px', display: 'flex', justifyContent: 'flex-end', gap: 4, position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                <span onClick={() => runScrape(c.id)} title="Scrape this company now" className="v2-act"
                  style={{ flex: '0 0 auto', height: 25, padding: '0 10px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                  {scraping[c.id]
                    ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />
                    : <span style={{ fontSize: 11 }}>↻</span>}
                  {scraping[c.id] ? 'Running' : 'Run'}
                </span>
                <span onClick={() => runTest(c.id)} title="Dry run — shows what would be kept, writes nothing" className="v2-act"
                  style={{ height: 25, padding: '0 10px', borderRadius: 99, border: '1px solid var(--edge)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
                  {testingId === c.id ? <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} /> : <span style={{ fontSize: 11 }}>⚗</span>}Test
                </span>
                <span onClick={() => setMenuId(menuId === c.id ? null : c.id)} title="More actions" className="v2-act"
                  style={{ width: 25, height: 25, border: `1px solid ${menuId === c.id ? 'var(--accent)' : 'var(--edge)'}`, background: menuId === c.id ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>⋯</span>
                {menuId === c.id && (
                  <span style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 4, width: 236, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5, display: 'flex', flexDirection: 'column', textAlign: 'left' }}>
                    <span onClick={() => { setMenuId(null); openDrawer(c) }} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}><span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>✎</span>Edit config</span>
                    {urls.length > 0 && <span onClick={() => { setMenuId(null); urls.forEach((u) => window.open(u, '_blank', 'noopener,noreferrer')) }} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}><span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>↗</span>{urls.length > 1 ? `Open ${urls.length} career pages` : 'Open career page'}</span>}
                    <a href={`/v2/feed?company=${encodeURIComponent(c.name)}`} className="v2-menuitem" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer', textDecoration: 'none' }}><span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>☰</span>View jobs in feed</a>
                    <span onClick={() => deleteCompany(c)} className="v2-hover-bad" style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px', borderRadius: 6, fontSize: 12.5, color: 'var(--bad)', cursor: 'pointer', marginTop: 3, borderTop: '1px solid var(--line-soft)' }}><span style={{ flex: '0 0 16px', textAlign: 'center', fontSize: 11 }}>✕</span>Delete company</span>
                  </span>
                )}
              </span>
            </div>
          )
        })}
        {filtered.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 28px' }}>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>No companies match</span>
            <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{query.trim() ? `Nothing matches "${query}" in names, aliases, URLs or ATS.` : 'No companies in the selected tiers.'}</span>
            <span onClick={clearFilters} style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', paddingTop: 2 }}>Clear filters</span>
          </div>
        )}
      </div>

      {drawer && <Drawer state={drawer} setState={setDrawer} resumes={resumes} personaPopulated={personaPopulated} onSave={patchCompany} onDelete={deleteCompany} onTest={runTest} testingId={testingId} downReason={downMap[drawer.company.id]} />}
      {addOpen && <AddModal onClose={() => setAddOpen(false)} resumes={resumes} personaPopulated={personaPopulated} onCreated={fetchCompanies} />}
      {test && <TestModal test={test} onClose={() => setTest(null)} showShots={showShots} setShowShots={setShowShots} />}
    </div>
  )
}

// ── edit drawer ───────────────────────────────────────────────────────────────
function Drawer({ state, setState, resumes, personaPopulated, onSave, onDelete, onTest, testingId, downReason }) {
  const { company, draft } = state
  const [tuning, setTuning] = useState(() => {
    try { const v = localStorage.getItem('company_tuning_open'); if (v !== null) return v === 'true' } catch { /* ignore */ }
    return !!downReason
  })
  const toggleTuning = () => setTuning((v) => { const n = !v; try { localStorage.setItem('company_tuning_open', String(n)) } catch {} return n })
  const set = (patch) => setState((s) => ({ ...s, draft: { ...s.draft, ...patch } }))
  const toggleResume = (id) => set({ selected_resume_ids: draft.selected_resume_ids.includes(id) ? draft.selected_resume_ids.filter((x) => x !== id) : [...draft.selected_resume_ids, id] })
  const subtitle = `${draft.tier == null ? 'Untiered' : `Tier ${draft.tier}`} · ${draft.scrape_urls.filter(Boolean).length} career URL(s) · ${company.application_count || 0} open application(s)`
  const lca = company.h1b_lca_count
  const lcaLine = lca ? `${lca} filings on record${company.h1b_approval_rate ? ` · ${company.h1b_approval_rate}% approved` : ''} — each job's H-1B verdict is drawn from these.` : 'No filings on record, so jobs here show H-1B Unknown. Blank auto-detects from the company name.'
  const selNames = [...resumes.filter((r) => draft.selected_resume_ids.includes(r.id)).map((r) => r.name), ...(draft.selected_resume_ids.includes('persona') ? ['Persona'] : [])]
  const resumeHelp = selNames.length ? `New jobs are scored against ${selNames.join(', ')}.` : 'Nothing selected, so new jobs use your default résumé from Settings.'
  const tuningNote = downReason ? 'needs attention' : (draft.scrape_interval_minutes || draft.wait_for_selector || (draft.max_pages && draft.max_pages !== 5) || draft.h1b_slug) ? 'customised' : 'using defaults'

  const save = () => {
    const payload = {
      name: draft.name,
      aliases: draft.aliases.split(',').map((s) => s.trim()).filter(Boolean),
      scrape_urls: draft.scrape_urls.filter(Boolean),
      title_include_expr: draft.title_include_expr || null,
      title_exclude_keywords: draft.title_exclude_keywords.split(',').map((s) => s.trim()).filter(Boolean),
      auto_scoring_depth: draft.auto_scoring_depth,
      selected_resume_ids: draft.selected_resume_ids,
      tier: draft.tier,
      scrape_interval_minutes: draft.scrape_interval_minutes === '' ? null : parseInt(draft.scrape_interval_minutes) || null,
      wait_for_selector: draft.wait_for_selector || null,
      max_pages: parseInt(draft.max_pages) || 5,
      h1b_slug: draft.h1b_slug || null,
    }
    onSave(company.id, payload); setState(null)
  }

  return (
    <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 720, background: 'var(--surface)', borderLeft: '1px solid var(--line)', boxShadow: '-14px 0 40px rgba(0,0,0,.14)', display: 'flex', flexDirection: 'column', zIndex: 30 }}>
      <div style={{ flex: '0 0 auto', padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-.02em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{draft.name || company.name}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{subtitle}</span>
        </div>
        <div onClick={() => setState(null)} className="v2-hover-accent" style={{ flex: '0 0 auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
      </div>

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '15px 22px 20px', display: 'flex', flexDirection: 'column', gap: 15, minHeight: 0 }}>
        {downReason && (
          <div style={{ display: 'flex', gap: 9, padding: '11px 13px', border: '1px solid var(--warn)', background: 'var(--warn-soft)', borderRadius: 9 }}>
            <span style={{ flex: '0 0 auto', fontSize: 12, color: 'var(--warn)' }}>▲</span>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5 }}>{downReason}</span>
              <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>Detected on the recent runs · last ran {ago(company.last_scraped_at)}</span>
            </div>
          </div>
        )}

        {/* identity + sources */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 15, fontWeight: 600, letterSpacing: '-.01em' }}>Identity and sources</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Display name</span>
            <input value={draft.name} onChange={(e) => set({ name: e.target.value })} style={{ ...inputBox, height: 32 }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Also known as</span>
            <input value={draft.aliases} onChange={(e) => set({ aliases: e.target.value })} placeholder="Alt names, comma-separated" style={{ ...inputBox, height: 32 }} />
            <span style={helpTxt}>Postings under these names collapse into this company.</span>
          </div>
          <UrlEditor urls={draft.scrape_urls} onChange={(u) => set({ scrape_urls: u })} />
        </div>

        <div style={{ height: 1, background: 'var(--line-soft)' }} />

        {/* which postings to keep */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 15, fontWeight: 600, letterSpacing: '-.01em' }}>Which postings to keep</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Title must match</span>
            <input value={draft.title_include_expr} onChange={(e) => set({ title_include_expr: e.target.value })} placeholder="(Product OR Project) AND Manager" style={{ ...inputBox, height: 32 }} />
            <span style={helpTxt}>Supports AND, OR and parentheses. Blank keeps every title.</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Skip titles containing</span>
            <input value={draft.title_exclude_keywords} onChange={(e) => set({ title_exclude_keywords: e.target.value })} placeholder="intern, junior, associate" style={{ ...inputBox, height: 32 }} />
            <span style={helpTxt}>Comma-separated. Applied after the match above.</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={fieldLabel}>Score new jobs automatically</span>
            <Seg opts={DEPTHS} value={draft.auto_scoring_depth} onPick={(v) => set({ auto_scoring_depth: v })} />
            <div style={{ paddingTop: 2 }}><ResumeChips resumes={resumes} personaPopulated={personaPopulated} selected={draft.selected_resume_ids} toggle={toggleResume} /></div>
            <span style={helpTxt}>{resumeHelp}</span>
          </div>
        </div>

        <div style={{ height: 1, background: 'var(--line-soft)' }} />

        {/* scraper tuning */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div onClick={toggleTuning} style={{ display: 'flex', alignItems: 'center', gap: 9, cursor: 'pointer' }}>
            <span style={{ flex: '0 0 12px', display: 'inline-flex', justifyContent: 'center', position: 'relative', top: -2, fontSize: 11, color: 'var(--muted)' }}>{tuning ? '⌄' : '›'}</span>
            <span style={{ fontFamily: 'var(--serif)', fontSize: 15, fontWeight: 600, letterSpacing: '-.01em' }}>Scraper tuning</span>
            <span style={{ fontSize: 10.5, color: downReason ? 'var(--warn)' : 'var(--muted)' }}>{tuningNote}</span>
          </div>
          {tuning && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 11 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Priority tier</span>
                  <Seg opts={TIER_BTNS} value={draft.tier} onPick={(v) => set({ tier: v })} valueKey="v" />
                  <span style={helpTxt}>Groups companies for filtering and bulk actions.</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Scrape interval in minutes</span>
                  <input type="number" min={1} value={draft.scrape_interval_minutes} onChange={(e) => set({ scrape_interval_minutes: e.target.value })} placeholder="Use global interval" style={{ ...inputBox, height: 32 }} />
                  <span style={helpTxt}>Blank follows the schedule set in Settings.</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Wait for element</span>
                  <input value={draft.wait_for_selector} onChange={(e) => set({ wait_for_selector: e.target.value })} placeholder="CSS selector" style={{ ...monoBox, height: 32, minHeight: 0 }} />
                  <span style={helpTxt}>CSS selector the page must render before reading.</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Pages to read</span>
                  <input type="number" min={1} max={20} value={draft.max_pages} onChange={(e) => set({ max_pages: e.target.value })} style={{ ...inputBox, height: 32 }} />
                  <span style={helpTxt}>Stops paging after this many.</span>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={fieldLabel}>H-1B employer name</span>
                <input value={draft.h1b_slug} onChange={(e) => set({ h1b_slug: e.target.value })} placeholder="Auto-detect" style={{ ...monoBox, height: 32, minHeight: 0 }} />
                <span style={{ fontSize: 10.5, color: lca ? 'var(--good)' : 'var(--muted)' }}>{lcaLine}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ flex: '0 0 auto', padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div onClick={() => { onSave(company.id, { active: !draft.active }); set({ active: !draft.active }) }} style={{ height: 32, padding: '0 13px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 12, color: draft.active ? 'var(--warn)' : 'var(--accent)', whiteSpace: 'nowrap', cursor: 'pointer' }}>{draft.active ? 'Make inactive — jobs already found are kept' : 'Make active'}</div>
        <div onClick={() => onTest(company.id)} className="v2-act" style={{ height: 32, padding: '0 13px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: 'pointer' }}>
          {testingId === company.id && <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />}
          {testingId === company.id ? 'Testing…' : 'Test scrape'}
        </div>
        <div onClick={save} style={{ marginLeft: 'auto', height: 32, padding: '0 16px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>Save changes</div>
      </div>
    </div>
  )
}

// ── add modal ─────────────────────────────────────────────────────────────────
function AddModal({ onClose, resumes, personaPopulated, onCreated }) {
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [aliases, setAliases] = useState('')
  const [tier, setTier] = useState(2)
  const [interval, setIntervalV] = useState('')
  const [selected, setSelected] = useState([])
  const [depth, setDepth] = useState('light')
  const [saving, setSaving] = useState(false)
  const ats = detectAts(url)
  const known = ats !== 'Generic'
  const atsNote = !url ? 'The ATS is detected once you paste a URL.'
    : known ? "Jobs are read from the board's API, so no page settings are needed."
      : 'No known ATS — the page is loaded and read as HTML. If it lists nothing, set a wait-for selector in the company config.'
  const selNames = [...resumes.filter((r) => selected.includes(r.id)).map((r) => r.name), ...(selected.includes('persona') ? ['Persona'] : [])]
  const scoreNote = depth === 'off' ? 'New jobs arrive unscored — you can score them by hand from the feed.'
    : `New jobs are scored against ${selNames.length ? selNames.join(', ') : 'your default résumé from Settings'} as they arrive.`
  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  const save = async () => {
    if (!name.trim()) { window.alert('Company name is required'); return }
    setSaving(true)
    try {
      await api.post('/companies', {
        name: name.trim(),
        aliases: aliases.split(',').map((s) => s.trim()).filter(Boolean),
        scrape_urls: url.trim() ? [url.trim()] : [],
        tier, scrape_interval_minutes: interval === '' ? null : parseInt(interval) || null,
        selected_resume_ids: selected, auto_scoring_depth: depth,
      })
      onCreated(); onClose()
    } catch (e) { window.alert(e.response?.data?.detail || 'Failed to add company'); setSaving(false) }
  }

  return (
    <div style={{ position: 'absolute', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 520, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '16px 22px 13px', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Add company</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Paste a careers URL — the ATS is read from it.</span>
        </div>
        <div className="v2-scroll" style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 470, overflow: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Career page URL</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span className={url ? atsSlug(ats) : undefined} style={{ flex: '0 0 auto', fontSize: 9.5, letterSpacing: '.05em', padding: '3px 8px', borderRadius: 99, background: url ? undefined : 'var(--surface-2)', color: url ? undefined : 'var(--muted)', whiteSpace: 'nowrap' }}>{url ? ats : '—'}</span>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://boards.greenhouse.io/acme" style={{ ...monoBox, flex: 1, height: 33, minHeight: 0, fontSize: 11 }} />
            </div>
            <span style={{ fontSize: 11, color: url && !known ? 'var(--warn)' : 'var(--muted)' }}>{atsNote}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Company name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme" style={{ ...inputBox, height: 33, fontSize: 12.5 }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Aliases</span>
              <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="Alt names, comma-separated" style={{ ...inputBox, height: 33 }} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Tier</span>
              <Seg opts={TIER_BTNS} value={tier} onPick={setTier} valueKey="v" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>Scrape interval in minutes</span>
              <input type="number" min={1} value={interval} onChange={(e) => setIntervalV(e.target.value)} placeholder="Use global interval" style={{ ...inputBox, height: 33, fontSize: 12.5 }} />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 2, borderTop: '1px solid var(--line-soft)', marginTop: 2 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--muted)', paddingTop: 8 }}>Score new jobs against</span>
            <ResumeChips resumes={resumes} personaPopulated={personaPopulated} selected={selected} toggle={toggle} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 2 }}>
              <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>Depth</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {DEPTHS.map((d) => { const on = depth === d.id; return (
                  <div key={d.id} onClick={() => setDepth(d.id)} title={d.hint} className="v2-bd" style={{ height: 26, padding: '0 11px', border: `1px solid ${on ? 'var(--accent)' : 'var(--edge)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface)', color: on ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, fontWeight: on ? 600 : 400, whiteSpace: 'nowrap', cursor: 'pointer' }}>{d.label}</div>
                ) })}
              </div>
            </div>
          </div>
          <span style={{ fontSize: 11, color: 'var(--muted)', paddingTop: 2 }}>{scoreNote}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Title filters, wait-for selector and max pages use the defaults — change them in the company config when a board needs it.</span>
        </div>
        <div style={{ flex: '0 0 auto', padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>Scrapes on the next scheduled run</span>
          <div onClick={onClose} style={{ marginLeft: 'auto', height: 33, padding: '0 14px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12.5, color: 'var(--text-2)', cursor: 'pointer' }}>Cancel</div>
          <div onClick={save} style={{ height: 33, padding: '0 17px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 500, cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1 }}>{saving ? 'Saving…' : 'Save'}</div>
        </div>
      </div>
    </div>
  )
}

// ── test scrape modal ─────────────────────────────────────────────────────────
function TestModal({ test, onClose, showShots, setShowShots }) {
  if (test.error) {
    return (
      <div style={{ position: 'absolute', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
        <div onClick={(e) => e.stopPropagation()} style={{ width: 520, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', padding: 22 }}>
          <div style={{ fontFamily: 'var(--serif)', fontSize: 18, marginBottom: 10 }}>Test scrape — Error</div>
          <div style={{ fontSize: 12.5, color: 'var(--bad)' }}>{test.error}</div>
          <div onClick={onClose} style={{ marginTop: 16, height: 31, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, display: 'inline-flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Close</div>
        </div>
      </div>
    )
  }
  const jobs = test.jobs || []
  const kept = test.after_filter ?? jobs.filter((j) => j.kept).length
  const rejected = test.total_rejected || 0
  const found = test.total_found ?? jobs.length
  const summary = `${kept} kept · ${found - kept - rejected} keyword-filtered · ${rejected} validation-rejected · ${found} extracted`
  const urls = test.urls_scraped || []
  const pag = test.pagination_debug || []
  const shots = test.screenshots || []
  const jobState = (j) => {
    if (j.reason?.startsWith('[Validation]')) return { tag: 'Drop', tagBg: 'var(--warn-soft)', tagFg: 'var(--warn)', bg: 'var(--surface)', reasonFg: 'var(--warn)', reason: j.reason.replace('[Validation] ', '') }
    if (j.kept) return { tag: 'Kept', tagBg: 'var(--accent-soft)', tagFg: 'var(--good)', bg: 'var(--surface)', reasonFg: 'var(--muted)', reason: j.reason || '' }
    return { tag: 'Out', tagBg: 'var(--bad-soft)', tagFg: 'var(--bad)', bg: 'var(--surface)', reasonFg: 'var(--bad)', reason: j.reason || '' }
  }
  return (
    <div style={{ position: 'absolute', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 840, maxHeight: 660, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Test scrape — {test.company}</span>
          {shots.length > 0 && (
            <div onClick={() => setShowShots((v) => !v)} style={{ marginLeft: 'auto', height: 26, padding: '0 11px', border: `1px solid ${showShots ? 'var(--accent)' : 'var(--edge)'}`, background: showShots ? 'var(--accent-soft)' : 'var(--surface)', color: showShots ? 'var(--accent)' : 'var(--text-2)', borderRadius: 99, display: 'flex', alignItems: 'center', fontSize: 11.5, whiteSpace: 'nowrap', cursor: 'pointer' }}>{showShots ? 'Hide' : 'Show'} screenshots</div>
          )}
          <div onClick={onClose} className="v2-hover-accent" style={{ width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer', marginLeft: shots.length ? 0 : 'auto' }}>✕</div>
        </div>

        <div style={{ flex: '0 0 auto', padding: '9px 22px', background: 'var(--bg)', borderBottom: '1px solid var(--line-soft)', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>URLs scraped · {urls.length}</span>
          {urls.map((u, i) => <span key={i} style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u}</span>)}
          {(test.include_expr || (test.exclude_keywords || []).length > 0) && (
            <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
              {test.include_expr && <>Include <span style={{ fontFamily: 'var(--mono)', fontSize: 10, background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>{test.include_expr}</span> </>}
              {(test.exclude_keywords || []).length > 0 && <>· Exclude <span style={{ fontFamily: 'var(--mono)', fontSize: 10, background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>{test.exclude_keywords.join(', ')}</span></>}
            </span>
          )}
        </div>

        {showShots && shots.length > 0 && (
          <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 8, padding: '11px 22px', background: 'var(--bg)', borderBottom: '1px solid var(--line-soft)', maxHeight: 280, overflow: 'auto' }}>
            {shots.map((s, i) => (
              <div key={i}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>{s.url}</span>
                <img src={`data:image/png;base64,${s.data}`} alt="" style={{ width: '100%', border: '1px solid var(--line)', borderRadius: 8, marginTop: 4 }} />
              </div>
            ))}
          </div>
        )}

        {pag.length > 0 && (
          <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 3, padding: '10px 22px', background: 'var(--surface-2)', borderBottom: '1px solid var(--line-soft)' }}>
            <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--accent)', fontWeight: 600 }}>Pagination debug</span>
            {pag.map((p, i) => (
              <span key={i} style={{ fontSize: 11, color: p.clicked ? 'var(--good)' : 'var(--bad)' }}>Page {p.page} · {p.clicked ? `Clicked ${p.clicked_via?.selector || ''} — ${p.clicked_via?.text || ''}` : 'No next button found'}</span>
            ))}
          </div>
        )}

        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <div style={{ position: 'sticky', top: 0, zIndex: 2, background: 'var(--bg)', display: 'flex', alignItems: 'center', height: 28, padding: '0 22px', borderBottom: '1px solid var(--line)', fontSize: 9.5, letterSpacing: '.11em', textTransform: 'uppercase', color: 'var(--muted)' }}>
            <span style={{ flex: '0 0 30px' }}>#</span>
            <span style={{ flex: 1, minWidth: 0 }}>Title</span>
            <span style={{ flex: '0 0 62px' }}>Status</span>
            <span style={{ flex: '0 0 260px' }}>Reason</span>
            <span style={{ flex: '0 0 40px', textAlign: 'right' }}>Link</span>
          </div>
          {jobs.map((j, i) => {
            const st = jobState(j)
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', height: 32, padding: '0 22px', borderBottom: '1px solid var(--line-soft)' }}>
                <span style={{ flex: '0 0 30px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>{i + 1}</span>
                <span title={j.title} style={{ flex: 1, minWidth: 0, fontSize: 12, color: j.kept ? 'var(--text)' : 'var(--muted)', textDecoration: j.kept ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{j.title}</span>
                <span style={{ flex: '0 0 62px' }}><span style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99, background: st.tagBg, color: st.tagFg }}>{st.tag}</span></span>
                <span title={st.reason} style={{ flex: '0 0 260px', fontSize: 11, color: st.reasonFg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{st.reason}</span>
                <span style={{ flex: '0 0 40px', textAlign: 'right' }}><a href={j.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: 'var(--accent)' }}>↗</a></span>
              </div>
            )
          })}
          {jobs.length === 0 && <div style={{ textAlign: 'center', padding: 32, color: 'var(--muted)', fontSize: 12.5 }}>No job links found on this page.</div>}
        </div>

        <div style={{ flex: '0 0 auto', padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{summary}</span>
          <div onClick={onClose} style={{ marginLeft: 'auto', height: 31, padding: '0 15px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Close</div>
        </div>
      </div>
    </div>
  )
}
