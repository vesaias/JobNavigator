import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import { useToasts, ToastStack } from './Toast'
// shared dialog also serves résumé and cover-letter deletes, so it lives in its own file.
import ConfirmDialog from './ConfirmDialog'
import { useSettled, useWarm, NBSP } from './hooks'
import { Button, DashedAdd, Dot, Drawer as UiDrawer, FooterRow, Heading, HeaderRow, Helper, IconButton, Input, Label, Link, Menu, MenuItem, ModalPanel, Mono, Notice, PageTitle, Pill, Row, Rule, SearchInput, Segmented, ShowMore, Spinner, TableHead, TableRow, Tag } from './ui'
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

// A paused company's last-run state stays on the row as muted "inactive" history rather than
// driving the ▲/attention count/rail dot; same for an acknowledged warning until a newer run fails.
const warnTextOf = (c, downReason) => c.last_error || downReason
  || (c.last_run_warning ? `last run found nothing · ${ago(c.last_scraped_at)}` : null)
const warnMuted = (c) => !c.active || !!c.warning_acknowledged
const isAlarming = (c, downReason) => !!warnTextOf(c, downReason) && !warnMuted(c)
// FastAPI's `detail` is a plain string for HTTPException; append it when present.
const errSuffix = (e) => (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '')

// ATS + tier chip colors live in theme.css (.cc-*) so they flip with dark mode.
const ATS_SLUGS = new Set(['greenhouse', 'workday', 'lever', 'ashby', 'phenom', 'oraclehcm', 'smartrecruiters', 'rippling', 'eightfold', 'talentbrew', 'meta', 'google'])
const atsShort = (detected) => (detected || 'Generic')
  .replace(' API', '').replace(' AJAX', '').replace(' (Playwright)', '').replace(' Careers', '')
const atsSlug = (short) => { const s = (short || 'generic').toLowerCase().replace(/[^a-z0-9]/g, ''); return 'cc-' + (ATS_SLUGS.has(s) ? s : 'generic') }
const tierSlug = (key) => 'cc-tier' + (key === 'none' ? 'none' : key)
// Company.tier is stored as an integer 1/2/3 (nullable) — backend/models/db.py.
// The UI shows priority tiers as letters; tierLabel(1) -> 'A', tierLabel(1, { long: true }) -> 'Tier A'.
const TIER_LETTERS = { 1: 'A', 2: 'B', 3: 'C' }
const tierLabel = (t, { long = false } = {}) => {
  const letter = TIER_LETTERS[t]
  if (!letter) return long ? 'Untiered' : '—'
  return long ? `Tier ${letter}` : letter
}

// client-side ATS detection (mirror of backend detect, for live editor chips)
const hostMatches = (url, ...domains) => {
  let host; try { host = new URL(url).hostname.toLowerCase() } catch { return false }
  return domains.some((d) => d && (host === d || host.endsWith('.' + d)))
}
const pathHas = (url, ...needles) => {
  let p; try { p = new URL(url).pathname.toLowerCase() } catch { return false }
  return needles.some((n) => n && p.includes(n))
}
// Mirrors backend/api/routes_companies.py:detect_scrape_type (and the scraper/ats/*.is_* predicates)
// so the live chip in the drawer/add modal agrees with the row chip the backend computes.
const detectAts = (url) => {
  if (!url) return 'Generic'
  if (url.toUpperCase().startsWith('POST|')) return 'Phenom'
  if (hostMatches(url, 'myworkdayjobs.com')) return 'Workday'
  // oracle_hcm.is_oracle_hcm: exact hcmUI path, or /sites/ + /jobs anywhere in the
  // URL (hash included) on an oraclecloud.com host or careers.oracle.com
  if (url.includes('oraclecloud.com/hcmUI/CandidateExperience')) return 'Oracle HCM'
  if (url.includes('/sites/') && url.includes('/jobs') && hostMatches(url, 'oraclecloud.com', 'careers.oracle.com')) return 'Oracle HCM'
  if (url.toLowerCase().includes('jobs.lever.co/')) return 'Lever'
  if (url.toLowerCase().includes('/search-jobs/results?')) return 'TalentBrew'
  if (hostMatches(url, 'jobs.ashbyhq.com')) return 'Ashby'
  if (hostMatches(url, 'greenhouse.io')) return 'Greenhouse'
  if (hostMatches(url, 'ats.rippling.com') || (hostMatches(url, 'rippling.com') && pathHas(url, '/careers'))) return 'Rippling'
  if (hostMatches(url, 'jobs.smartrecruiters.com', 'careers.smartrecruiters.com', 'api.smartrecruiters.com')) return 'SmartRecruiters'
  if (hostMatches(url, 'metacareers.com')) return 'Meta'
  if (url.toLowerCase().includes('google.com/about/careers')) return 'Google'
  return 'Generic'
}

const SORT_OPTIONS = [
  { id: 'health', label: 'Needs attention', hint: 'Warnings, then active, then inactive' },
  { id: 'name', label: 'Company name', hint: 'A to Z' },
  { id: 'tier', label: 'Priority tier', hint: 'Tier A first, untiered last' },
  { id: 'open', label: 'Open roles', hint: 'Most roles in the feed first' },
  { id: 'fit', label: 'Average fit', hint: 'Best-scoring companies first' },
  { id: 'run', label: 'Last scrape', hint: 'Longest since last run' },
]
const DEPTHS = [
  { id: 'off', label: 'Off', hint: 'New jobs are stored unscored' },
  { id: 'light', label: 'Light', hint: 'Scores only, no report' },
  { id: 'full', label: 'Full', hint: 'Full report with keywords and requirements' },
]
const TIER_BTNS = [{ v: 1, label: tierLabel(1) }, { v: 2, label: tierLabel(2) }, { v: 3, label: tierLabel(3) }, { v: null, label: 'None' }]

// A Playwright board can return ~600 rows; page them client-side with the pager
// the résumé shelf and Stats logs already use.
const TEST_PAGE = 100
const fieldLabel = { fontSize: 11.5, fontWeight: 500, color: 'var(--text)' }

// ── URL list editor (drawer + add) ───────────────────────────────────────────
function UrlEditor({ urls, onChange }) {
  const set = (i, v) => { const u = [...urls]; u[i] = v; onChange(u) }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {urls.map((u, i) => {
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span className={atsSlug(detectAts(u))} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', textTransform: 'uppercase', padding: '3px 8px', borderRadius: 'var(--radius-control)', whiteSpace: 'nowrap' }}>{detectAts(u)}</span>
            <Input value={u} onChange={(v) => set(i, v)} placeholder="https://boards.greenhouse.io/company"
              mono ariaLabel="Career page URL" style={{ flex: 1, minWidth: 0 }} />
            <span title="Remove this URL" onClick={() => onChange(urls.filter((_, j) => j !== i))} className="v2-hover-bad v2-hover-bad-text"
              style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)', cursor: 'pointer', padding: 2, borderRadius: 'var(--radius-inline)' }}>✕</span>
          </div>
        )
      })}
      <DashedAdd onClick={() => onChange([...urls, ''])}>+ Add another career page</DashedAdd>
    </div>
  )
}

// `opts` keeps this screen's two shapes — DEPTHS keys on `id`, TIER_BTNS on `v` — so the
// three call sites don't need to change; cells render via the Segmented primitive.
const Seg = ({ opts, value, onPick, valueKey = 'id' }) => (
  <Segmented value={value} onChange={onPick}
    options={opts.map((o) => ({ value: o[valueKey] !== undefined ? o[valueKey] : o.v, label: o.label, hint: o.hint }))} />
)

const ResumeChips = ({ resumes, personaPopulated, selected, toggle }) => (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
    {resumes.map((r) => {
      const on = selected.includes(r.id)
      return <Pill key={r.id} size="sm" on={on} onClick={() => toggle(r.id)}>{r.name}</Pill>
    })}
    {personaPopulated && (() => { const on = selected.includes('persona'); return (
      <Pill size="sm" on={on} onClick={() => toggle('persona')}>Persona</Pill>
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
  const [confirm, setConfirm] = useState(null)   // styled confirm {title, body, label, danger, onConfirm}
  const [test, setTest] = useState(null)              // test-scrape result
  const [testingId, setTestingId] = useState(null)
  const [showShots, setShowShots] = useState(false)
  const [reload, setReload] = useState(0)   // "Try again" re-arms the settle below
  const [loadErr, setLoadErr] = useState(null)
  // Fixed columns overflow the container at narrow widths, so the four lowest-value columns (all
  // visible in the edit drawer) shed as the pane narrows, same ResizeObserver shape as Settings/Stats.
  const tableRef = useRef(null)
  const [tblW, setTblW] = useState(1400)
  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()
  const navigate = useNavigate()
  const mounted = useRef(true)
  useEffect(() => () => { mounted.current = false }, [])

  // only company_scrape runs belong on this screen; /monitor/active also carries scoring/search runs
  // keyed by job/search id. Prefer company_id when present; scope_key is the fallback for older runs.
  const runMap = (data) => { const m = {}; (data || []).forEach((r) => { if (r.job_type !== 'company_scrape') return; const id = r.company_id || r.scope_key; if (id) m[id] = true }); return m }
  // health is refetched with the list, so a run that clears (or causes)
  // a failure updates the row ▲, the header count and the sort without a reload.
  const fetchHealth = useCallback(async () => {
    try { const { data } = await api.get('/health/entities'); const m = {}; (data.companies || []).forEach((c) => { m[c.id] = c.reason }); setDownMap(m) }
    catch { /* keep the last known verdict */ }
  }, [])
  const fetchCompanies = useCallback(async () => {
    try { const { data } = await api.get('/companies'); setCompanies(data); setLoadErr(null) }
    catch (e) { console.error(e); const msg = 'Could not load companies' + errSuffix(e); setLoadErr(msg); pushToast({ kind: 'error', msg }) }
    return fetchHealth()
  }, [pushToast, fetchHealth])
  // list, health, résumé names and running scrapes settle together via useSettled, so the table,
  // tier counts, bulk buttons and subtitle never render in a staggered, half-loaded order.
  const { ready } = useSettled([
    () => fetchCompanies(),
    () => api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(Array.isArray(data) ? data : [])).catch(() => { /* silent: the résumé chips are decoration on this screen; the list load has its own error state */ }),
    () => api.get('/persona').then(({ data }) => setPersonaPopulated(Object.keys(data?.resume_content || {}).length > 0)).catch(() => { /* silent: one optional chip — absent Persona simply isn't offered */ }),
    () => api.get('/monitor/active').then(({ data }) => setScraping(runMap(data))).catch(() => { /* silent: poller — the 3s tick below retries, a toast per tick would be worse */ }),
  ], reload)

  useEffect(() => {
    const el = tableRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(([en]) => { const w = en?.contentRect?.width; if (typeof w === 'number') setTblW(w) })
    ro.observe(el)
    return () => ro.disconnect()
  }, [ready])

  // polls the real run registry and refreshes the list once a run disappears, rather than a fixed timer.
  useEffect(() => {
    if (!Object.keys(scraping).length) return
    const h = setInterval(async () => {
      try {
        const { data } = await api.get('/monitor/active')
        if (!mounted.current) return
        const m = runMap(data)
        setScraping((prev) => { if (Object.keys(prev).some((k) => !m[k])) fetchCompanies(); return m })
      } catch { /* retry on the next tick */ }
    }, 3000)
    return () => clearInterval(h)
  }, [scraping, fetchCompanies])
  useEffect(() => { try { localStorage.setItem('company_filter_tiers', JSON.stringify(tiers)) } catch {} }, [tiers])
  useEffect(() => { try { localStorage.setItem('company_query', query) } catch {} }, [query])
  useEffect(() => { try { localStorage.setItem('company_sort', sortBy) } catch {} }, [sortBy])

  // close menus on outside click / escape
  useEffect(() => {
    const onDoc = () => { setSortOpen(false); setMenuId(null) }
    const onKey = (e) => { if (e.key === 'Escape') { setSortOpen(false); setMenuId(null); setAddOpen(false); setTest(null); setConfirm(null); if (drawerRef.current) closeDrawer() } }
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
    // row ▲, health line and drawer banner all treat last_error as "needs attention"; sort and
    // count must agree, including skipping paused/acknowledged rows.
    const down = (c) => isAlarming(c, downMap[c.id])
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
  const downCount = companies.filter((c) => isAlarming(c, downMap[c.id])).length
  // Warm start: the subtitle's three numbers and the tier pills' counts are the
  // same on the frame after a refresh as they were before it. They paint from the
  // cache and reconcile (with the rail's .15s fade) when the settle disagrees.
  const { warm, style: warmStyle } = useWarm('companies', ready
    ? { n: companies.length, active: activeCount, down: downCount, tiers: tierCounts }
    : null, ready)
  const countLine = warm ? `${warm.n} tracked · ${warm.active} active · ${warm.down} need attention` : NBSP
  const warmTier = (t) => (warm && warm.tiers ? warm.tiers[t] : undefined)
  const inactiveInFilter = filtered.filter((c) => !c.active)
  const activeInFilter = filtered.filter((c) => c.active)
  const bulkHint = tiers.length || query.trim()
    ? `Applies to the ${filtered.length} companies shown. Jobs already found are kept.`
    : `Applies to all ${filtered.length} companies · jobs already found are kept`

  // ── actions ──
  // the shell re-reads its rail badges (including the amber health dot) on this
  // event, so every mutation that changes what needs attention fires it.
  const bumpCounts = () => window.dispatchEvent(new CustomEvent('jn:counts-changed'))
  const patchCompany = async (id, patch) => {
    // pausing/resuming changes what /health/entities counts, so the row, the
    // header count and the rail dot are all re-read — not just the list.
    try { await api.patch(`/companies/${id}`, patch); fetchCompanies(); fetchHealth(); bumpCounts(); return true }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: 'Could not save company changes' + errSuffix(e) }); return false }
  }
  // "I have seen this, stop shouting" — the warning stays on the row, muted,
  // and /health/entities re-raises it by itself once a newer run fails.
  const acknowledgeCompany = async (c) => {
    try {
      await api.post(`/companies/${c.id}/acknowledge`)
      fetchCompanies(); fetchHealth(); bumpCounts()
      pushToast({ kind: 'success', msg: `${c.name} acknowledged — it stops counting until a later run fails` })
    } catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Could not acknowledge ${c.name}` + errSuffix(e) }) }
  }
  const bulkSet = async (active) => {
    const targets = active ? inactiveInFilter : activeInFilter
    const results = await Promise.allSettled(targets.map((c) => api.patch(`/companies/${c.id}`, { active })))
    const failed = results.filter((r) => r.status === 'rejected').length
    if (failed) pushToast({ kind: 'error', msg: `Could not update ${failed} of ${targets.length} companies` })
    else pushToast({ kind: 'success', msg: `${targets.length} companies made ${active ? 'active' : 'inactive'}` })
    fetchCompanies()
  }
  const runScrape = async (id) => {
    if (scraping[id]) return
    setScraping((m) => ({ ...m, [id]: true }))
    try { await api.post(`/scrape/company/${id}`) }
    catch (e) {
      // 409 means the run is genuinely in flight — keep the spinner, the
      // /monitor/active poll clears it when the run finishes.
      if (e.response?.status === 409) { pushToast({ kind: 'progress', msg: 'That company is already being scraped' }); return }
      console.error(e); pushToast({ kind: 'error', msg: 'Could not start the scrape' + errSuffix(e) })
      setScraping((m) => { const n = { ...m }; delete n[id]; return n })
    }
  }
  // one test at a time: the POST is synchronous and can take tens of seconds on a Playwright
  // board; a second click would race its own result into the modal.
  const runTest = async (id) => {
    if (testingId) return
    setTestingId(id); setShowShots(false)
    try { const { data } = await api.post(`/companies/${id}/test-scrape`); setTest(data) }
    catch (e) { setTest({ error: e.response?.data?.detail || e.message }) }
    setTestingId(null)
  }
  const deleteCompany = (c) => setConfirm({ title: `Delete ${c.name}?`, body: 'Jobs already found are kept.', label: 'Delete', danger: true, onConfirm: async () => {   // styled, not window.confirm
    setConfirm(null)
    try { await api.delete(`/companies/${c.id}`); setMenuId(null); setDrawer(null); fetchCompanies(); pushToast({ kind: 'success', msg: `${c.name} deleted` }) }
    catch (e) { console.error(e); pushToast({ kind: 'error', msg: `Could not delete ${c.name}` + errSuffix(e) }) }
  } })

  // ── row cell derivations ──
  const resumeNames = (c) => {
    const ids = c.selected_resume_ids || []
    if (!ids.length) return null
    const names = resumes.filter((r) => ids.includes(r.id)).map((r) => r.name)
    if (ids.includes('persona')) names.push('Persona')
    // ids that resolve to nothing (list not loaded, or deleted résumés) must still
    // read as a selection, matching what the drawer shows.
    if (names.length) return names.join(', ')
    return `${ids.length} selected`
  }
  const healthOf = (c) => {
    if (scraping[c.id]) return { dot: 'var(--accent)', fg: 'var(--accent)', text: 'scraping now…' }
    const warn = warnTextOf(c, downMap[c.id])
    // paused or acknowledged: keep the verdict, drop the alarm colours
    if (warn && warnMuted(c)) return { dot: 'var(--edge)', fg: 'var(--muted)',
      text: `${c.last_error ? `error · ${warn}` : warn} · ${c.active ? `acknowledged ${ago(c.warning_acknowledged_at)}` : 'inactive'}` }
    if (c.last_error) return { dot: 'var(--bad)', fg: 'var(--bad)', text: `error · ${warn}` }
    if (warn) return { dot: 'var(--warn)', fg: 'var(--warn)', text: warn }
    if (c.active && !c.last_scraped_at) return { dot: 'var(--edge)', fg: 'var(--muted)', text: 'not scraped yet' }
    if (c.active) return { dot: 'var(--good)', fg: 'var(--text-2)', text: `healthy · scraped ${ago(c.last_scraped_at)}` }
    return { dot: 'var(--edge)', fg: 'var(--muted)', text: `inactive · last run ${ago(c.last_scraped_at)}` }
  }
  const fitColor = (f) => (f == null ? 'var(--muted)' : f >= 80 ? 'var(--good)' : f >= 65 ? 'var(--text-2)' : 'var(--warn)')
  const testBusy = !!testingId   // a running test locks every other Test/Run pill

  const clearFilters = () => { setQuery(''); setTiers([]) }
  const toDraft = (c) => ({
      name: c.name, aliases: (c.aliases || []).join(', '),
      scrape_urls: [...(c.scrape_urls || [])],
      title_include_expr: c.title_include_expr || '',
      title_exclude_keywords: (c.title_exclude_keywords || []).join(', '),
      auto_scoring_depth: c.auto_scoring_depth || 'off',
      selected_resume_ids: [...(c.selected_resume_ids || [])],
      tier: c.tier, scrape_interval_minutes: c.scrape_interval_minutes ?? '',
      wait_for_selector: c.wait_for_selector || '', max_pages: c.max_pages ?? 5,
      h1b_slug: c.h1b_slug || '', active: c.active,
  })
  // 1130 is the width at which every column fits; each lower threshold is that minus columns
  // already dropped. Below the last, Health also gives up 40px of its minimum, keeping ~50px slack at 1024.
  const showResumes = tblW >= 1130
  const showAts = tblW >= 998
  const showFit = tblW >= 890
  const showApps = tblW >= 842
  const healthMin = showApps ? 210 : 170

  const drawerRef = useRef(null)
  useEffect(() => { drawerRef.current = drawer }, [drawer])
  const drawerDirty = (d) => !!d && JSON.stringify(d.draft) !== JSON.stringify(toDraft(d.company))
  // Escape, the ✕, and clicking another row all route through here so an edited draft is never dropped silently
  const closeDrawer = () => {
    const cur = drawerRef.current
    if (drawerDirty(cur)) { setConfirm({ title: 'Discard changes?', body: `Edits to ${cur.company.name} have not been saved.`, label: 'Discard', danger: true, onConfirm: () => { setConfirm(null); setDrawer(null) } }); return }
    setDrawer(null)
  }
  const openDrawer = (c) => {
    const cur = drawerRef.current
    if (cur && cur.company.id !== c.id && drawerDirty(cur)) { setConfirm({ title: 'Discard changes?', body: `Edits to ${cur.company.name} have not been saved.`, label: 'Discard', danger: true, onConfirm: () => { setConfirm(null); setDrawer({ company: c, draft: toDraft(c) }) } }); return }
    setDrawer({ company: c, draft: toDraft(c) })
  }

  return (
    <div className="v2-scroll" style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* header — title + subtitle, matching The Feed */}
      <HeaderRow as="header" pad="22px 30px 16px 24px" line="none" align="flex-end" style={{ gap: 18 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <PageTitle>Companies</PageTitle>
          {/* integer line-height: at inherited 1.5 this 13px line is 19.5px tall, ending the header
              on a half pixel and dropping the 1px border on alternating rows below. */}
          <span style={{ fontSize: 13, lineHeight: '20px', color: 'var(--muted)', ...warmStyle }}>{countLine}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button onClick={() => setAddOpen(true)}>+ Add company</Button>
        </div>
      </HeaderRow>

      {/* toolbar */}
      <HeaderRow pad="2px 30px 12px 24px" align="center" style={{ flexWrap: 'wrap', gap: 8 }}>
        <SearchInput width="226px" value={query} onChange={setQuery}
          placeholder="Search name, alias, URL or ATS…" ariaLabel="Search companies" />
        <Rule vertical length={20} tone="line" style={{ margin: '0 3px' }} />
        {['1', '2', '3', 'none'].map((t) => {
          const on = tiers.includes(t)
          return (
            <Pill key={t} on={on} onClick={() => setTiers((p) => p.includes(t) ? p.filter((x) => x !== t) : [...p, t])}
              title="Add to or remove from the filter. Multiple allowed. Saved in this browser.">
              {/* the count comes from the warm snapshot until the list settles, so
                  the pill is its final width on the first frame */}
              <span>{t === 'none' ? 'Untiered' : tierLabel(t, { long: true })}<span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, opacity: 0.7, marginLeft: 6, ...warmStyle }}>{warmTier(t) != null ? warmTier(t) : NBSP}</span></span>
            </Pill>
          )
        })}
        <Rule vertical length={20} tone="line" style={{ margin: '0 2px' }} />
        {inactiveInFilter.length > 0 && (
          // ui: keep — accent-ink bulk action, paired with the --warn one below; Pill has no tinted variant
          <div onClick={() => bulkSet(true)} title={bulkHint} className="v2-act"
            style={{ flex: '0 0 auto', height: 30, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--accent)', whiteSpace: 'nowrap', cursor: 'pointer' }}>Make {inactiveInFilter.length} active</div>
        )}
        {activeInFilter.length > 0 && (
          // ui: keep — --warn ink + v2-bd-warn hover; Pill has no warn variant
          <div onClick={() => bulkSet(false)} title={bulkHint} className="v2-bd-warn"
            style={{ flex: '0 0 auto', height: 30, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--warn)', whiteSpace: 'nowrap', cursor: 'pointer' }}>Make {activeInFilter.length} inactive</div>
        )}
        <span style={{ marginLeft: 'auto', flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ position: 'relative', display: 'flex' }} onClick={(e) => e.stopPropagation()}>
            <div onClick={() => setSortOpen((v) => !v)} title="Change row order"
              style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)', cursor: 'pointer' }}>
              Sort<span style={{ color: 'var(--text-2)', fontWeight: 500 }}>{SORT_OPTIONS.find((s) => s.id === sortBy)?.label}</span><span style={{ fontSize: 10 }}>▾</span>
            </div>
            {sortOpen && (
              <Menu ariaLabel="Row order" className="v2-scroll" style={{ position: 'absolute', top: '100%', right: 0, zIndex: 45, marginTop: 5, width: 172 }}>
                {SORT_OPTIONS.map((so) => {
                  const on = so.id === sortBy
                  return (
                    <MenuItem key={so.id} selected={on} title={so.hint} hint={on ? '✓' : null}
                      onClick={() => { setSortBy(so.id); setSortOpen(false) }}>{so.label}</MenuItem>
                  )
                })}
              </Menu>
            )}
          </span>
        </span>
      </HeaderRow>

      {/* rows (column header lives inside the scroll container so its width
          tracks the rows' — otherwise the body scrollbar shifts every column) */}
      <div ref={tableRef} className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <TableHead height={30} pad="0 30px 0 24px" style={{ position: 'sticky', top: 0, zIndex: 3 }}>
          <span style={{ flex: 1, minWidth: 118 }}>Company</span>
          <span style={{ flex: '0 0 62px' }}>Tier</span>
          <span style={{ flex: 1.9, minWidth: healthMin }}>Health</span>
          {showResumes && <span style={{ flex: '0 0 132px' }} title="Which résumés new jobs from this company are scored against">Résumés</span>}
          {showAts && <span style={{ flex: '0 0 108px' }} title="ATS detected from the career URLs">ATS</span>}
          <span style={{ flex: '0 0 74px', textAlign: 'right', paddingRight: 10 }} title="Open roles in the Job Feed · postings found in the last 7 days — the +N counts everything the scraper discovered, including titles the filters rejected">Open · 7d</span>
          {showApps && <span style={{ flex: '0 0 46px', textAlign: 'right', paddingRight: 10 }} title="Applications recorded for this company">Apps</span>}
          {showFit && <span style={{ flex: '0 0 48px', textAlign: 'right', paddingRight: 14 }} title="Average fit across this company's scored roles">Ø Fit</span>}
          <span style={{ flex: '0 0 88px', textAlign: 'center' }}>Status</span>
          <span style={{ flex: '0 0 190px' }} />
        </TableHead>
        {filtered.map((c) => {
          const h = healthOf(c)
          const rn = resumeNames(c)
          const urls = c.scrape_urls || []
          const firstAts = urls.length ? atsShort(c.detected_scrape_types?.[urls[0]]) : 'Generic'
          const aliases = c.aliases || []
          return (
            <Row key={c.id} flush divider onClick={() => openDrawer(c)} className="v2-crow"
              style={{ gap: 0, padding: '0 30px 0 24px' }}>
              {/* company */}
              <span style={{ flex: 1, minWidth: 118, display: 'flex', alignItems: 'center', gap: 7, paddingRight: 10 }}>
                {isAlarming(c, downMap[c.id]) && <span title={`Needs attention — ${warnTextOf(c, downMap[c.id])}`} style={{ flex: '0 0 auto', fontSize: 11, color: c.last_error ? 'var(--bad)' : 'var(--warn)' }}>▲</span>}
                <span title={c.h1b_lca_count ? `${c.name} · ${c.h1b_lca_count} H-1B filings${c.h1b_approval_rate ? `, ${c.h1b_approval_rate}% approved` : ''}. Used for each job's H-1B verdict.` : c.name} style={{ flex: '0 1 auto', minWidth: 0, fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</span>
                {/* ui: keep — the “+N aliases” count badge: 9.5 on --surface-2, pad 1 5; Tag is 10/pad 2 8 uppercase */}
                {aliases.length > 0 && <span title={`Also scraped as ${aliases.join(', ')}`} style={{ flex: '0 0 auto', position: 'relative', top: 1, fontSize: 9.5, padding: '1px 5px', borderRadius: 'var(--radius-control)', background: 'var(--surface-2)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>+{aliases.length}</span>}
              </span>
              {/* tier */}
              <span style={{ flex: '0 0 62px' }}>
                <Tag tone="none" className={tierSlug(tierKey(c))}>{tierLabel(c.tier)}</Tag>
              </span>
              {/* health */}
              <span style={{ flex: 1.9, minWidth: healthMin, display: 'flex', alignItems: 'center', gap: 7, paddingRight: 10 }}>
                <Dot style={{ background: h.dot }} />
                <span title={c.last_error || downMap[c.id] || (c.active ? `Last successful run ${ago(c.last_scraped_at)}` : 'Inactive — jobs already found are kept')} style={{ flex: 1, minWidth: 0, fontSize: 12, color: h.fg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.text}</span>
              </span>
              {/* résumés */}
              {showResumes && <Helper title={rn || 'Scored against your default résumé from Settings'} style={{ flex: '0 0 132px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10, ...(rn ? { color: 'var(--text-2)' } : null) }}>{rn || 'Default'}</Helper>}
              {/* ats */}
              {showAts && <span style={{ flex: '0 0 108px', display: 'flex', alignItems: 'center', gap: 6, paddingRight: 10 }}>
                {urls.length > 0 && <span className={atsSlug(firstAts)} title={[...urls.map((u) => `${detectAts(u)} · ${u}`), `MyVisaJobs company id · ${c.h1b_slug || 'auto-detected'}`].join('\n')} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', whiteSpace: 'nowrap' }}>{firstAts}</span>}
                {urls.length > 1 && <Helper size="xs" title={urls.join('\n')} style={{ flex: '0 0 auto' }}>+{urls.length - 1}</Helper>}
                {urls.length === 0 && <Helper>—</Helper>}
              </span>}
              {/* open · 7d */}
              <Helper mono title={`${c.open_jobs || 0} open roles from ${c.name} in the Job Feed · ${c.open_jobs_week || 0} found in the last 7 days — everything discovered, including titles the filters rejected`} style={{ flex: '0 0 74px', textAlign: 'right', paddingRight: 10, ...(c.open_jobs ? { color: 'var(--text-2)' } : null) }}>
                {c.open_jobs || 0}<span style={{ color: c.open_jobs_week ? 'var(--good)' : 'var(--muted)' }}> +{c.open_jobs_week || 0}</span>
              </Helper>
              {/* apps */}
              {showApps && <Helper mono style={{ flex: '0 0 46px', textAlign: 'right', paddingRight: 10, ...(c.application_count ? { color: 'var(--text-2)' } : null) }}>{c.application_count || '·'}</Helper>}
              {/* fit */}
              {showFit && <span title={c.avg_fit == null ? 'No scored roles yet' : `Average fit ${c.avg_fit} across this company's scored roles`} style={{ flex: '0 0 48px', textAlign: 'right', paddingRight: 14, fontFamily: 'var(--mono)', fontSize: 11.5, color: fitColor(c.avg_fit) }}>{c.avg_fit == null ? '–' : c.avg_fit}</span>}
              {/* status */}
              <span style={{ flex: '0 0 88px', display: 'flex', justifyContent: 'center' }}>
                <Pill size="sm" on={c.active} onClick={(e) => { e.stopPropagation(); patchCompany(c.id, { active: !c.active }) }}
                  title={c.active ? 'Click to pause scraping' : 'Click to resume scraping'}>{c.active ? 'Active' : 'Inactive'}</Pill>
              </span>
              {/* actions: pinned to the right edge of the scroller so the ⋯ stays reachable when the row is wider than the pane at 1024px */}
              {/* position:sticky makes this cell its own stacking context, trapping the menu's z-index 40 inside it;
                  raise the cell itself while its menu is open: 28 clears the sticky head (3)/rows, stays under drawer (29/30). */}
              <span className="v2-cactions" style={{ flex: '0 0 190px', display: 'flex', alignSelf: 'stretch', alignItems: 'center', justifyContent: 'flex-end', gap: 4, position: 'sticky', right: 0, paddingLeft: 8, zIndex: menuId === c.id ? 28 : undefined }} onClick={(e) => e.stopPropagation()}>
                <Pill size="xs" line="inherit" disabled={testBusy} onClick={() => runScrape(c.id)}
                  title={testBusy ? 'A test is already running' : 'Scrape this company now'}>
                  {scraping[c.id]
                    ? <Spinner />
                    : <span style={{ fontSize: 11 }}>↻</span>}
                  {scraping[c.id] ? 'Running' : 'Run'}
                </Pill>
                {/* the running test names itself; every other pill goes quiet, so the running one keeps full opacity while un-clickable */}
                <Pill size="xs" line="inherit" on={testingId === c.id} disabled={testBusy} onClick={() => runTest(c.id)}
                  style={testingId === c.id ? { opacity: 1 } : undefined}
                  title={testingId === c.id ? 'Reading the board — nothing is saved' : testBusy ? 'A test is already running' : 'Preview run — shows what would be kept, saves nothing'}>
                  {testingId === c.id ? <Spinner /> : <span style={{ fontSize: 11 }}>⚗</span>}{testingId === c.id ? 'Testing…' : 'Test'}
                </Pill>
                <IconButton size={25} line="inherit" on={menuId === c.id} onClick={() => setMenuId(menuId === c.id ? null : c.id)}
                  title="More actions" ariaExpanded={menuId === c.id} ariaHaspopup="menu">⋯</IconButton>
                {menuId === c.id && (
                  <Menu ariaLabel={`${c.name} actions`} style={{ position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: 4, width: 236, textAlign: 'left' }}>
                    <MenuItem icon="✎" onClick={() => { setMenuId(null); openDrawer(c) }}>Edit config</MenuItem>
                    {urls.length > 0 && <MenuItem icon="↗" onClick={() => { setMenuId(null); urls.forEach((u) => window.open(u, '_blank', 'noopener,noreferrer')) }}>{urls.length > 1 ? `Open ${urls.length} career pages` : 'Open career page'}</MenuItem>}
                    <MenuItem icon="☰" href={`/v2/feed?company=${encodeURIComponent(c.name)}`}
                      onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); setMenuId(null); navigate(`/v2/feed?company=${encodeURIComponent(c.name)}`) }}>View jobs in feed</MenuItem>
                    <MenuItem danger icon="✕" onClick={() => deleteCompany(c)}>Delete company</MenuItem>
                  </Menu>
                )}
              </span>
            </Row>
          )
        })}
        {/* no "Loading companies…" row — the table keeps its container and stays empty until the settle, then draws once */}
        {/* loadErr is checked separately so a failed GET never reads as "nothing matches your search", where Clear filters would fix nothing */}
        {ready && loadErr && companies.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 28px' }}>
            <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load companies</span>
            <Helper>{loadErr}</Helper>
            <Link onClick={() => setReload((n) => n + 1)} style={{ paddingTop: 2 }}>Try again</Link>
          </div>
        )}
        {ready && filtered.length === 0 && !(loadErr && companies.length === 0) && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 28px' }}>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>{companies.length === 0 ? 'No companies yet' : 'No companies match'}</span>
            <Helper>{companies.length === 0 ? 'Add one with + Add company — its career page is scraped and the jobs appear in the Feed.' : query.trim() ? `Nothing matches "${query}" in names, aliases, URLs or ATS.` : `No companies in ${tiers.map((t) => (t === null || t === 'none' || t === 'untiered' ? 'Untiered' : tierLabel(t, { long: true }))).join(', ')}.`}</Helper>
            {companies.length > 0 && <Link onClick={clearFilters} style={{ paddingTop: 2 }}>Clear filters</Link>}
          </div>
        )}
      </div>

      {/* drawer.company is a snapshot from openDrawer and goes stale on any refetch (Save, status
          pill, bulk, /monitor poll); re-read the row by id each render, keep only `draft` in state. */}
      {drawer && (() => {
        const live = companies.find((c) => c.id === drawer.company.id) || drawer.company
        return <Drawer state={{ ...drawer, company: live }} setState={setDrawer} onClose={closeDrawer} resumes={resumes} personaPopulated={personaPopulated} onSave={patchCompany} onDelete={deleteCompany} onTest={runTest} testingId={testingId} downReason={downMap[live.id]} onAcknowledge={acknowledgeCompany} />
      })()}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}
      {addOpen && <AddModal onClose={() => setAddOpen(false)} resumes={resumes} personaPopulated={personaPopulated} onCreated={fetchCompanies} pushToast={pushToast} />}
      {test && <TestModal test={test} onClose={() => setTest(null)} showShots={showShots} setShowShots={setShowShots} />}
      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── edit drawer ───────────────────────────────────────────────────────────────
function Drawer({ state, setState, onClose, resumes, personaPopulated, onSave, onDelete, onTest, testingId, downReason, onAcknowledge }) {
  const { company, draft } = state
  const [tuning, setTuning] = useState(() => {
    try { const v = localStorage.getItem('company_tuning_open'); if (v !== null) return v === 'true' } catch { /* ignore */ }
    return !!warnTextOf(company, downReason) && !warnMuted(company)
  })
  const toggleTuning = () => setTuning((v) => { const n = !v; try { localStorage.setItem('company_tuning_open', String(n)) } catch {} return n })
  const set = (patch) => setState((s) => ({ ...s, draft: { ...s.draft, ...patch } }))
  const toggleResume = (id) => set({ selected_resume_ids: draft.selected_resume_ids.includes(id) ? draft.selected_resume_ids.filter((x) => x !== id) : [...draft.selected_resume_ids, id] })
  const nUrl = draft.scrape_urls.filter(Boolean).length, nApp = company.application_count || 0
  const subtitle = `${tierLabel(draft.tier, { long: true })} · ${nUrl} career URL${nUrl === 1 ? '' : 's'} · ${nApp} application${nApp === 1 ? '' : 's'}`
  const lca = company.h1b_lca_count
  const lcaLine = lca ? `${lca} H-1B filings on record${company.h1b_approval_rate ? ` · ${company.h1b_approval_rate}% approved` : ''}. Each job's H-1B verdict is based on these.` : 'No H-1B filings on record, so jobs show H-1B Unknown. Leave blank to detect the company from its name.'
  const selNames = [...resumes.filter((r) => draft.selected_resume_ids.includes(r.id)).map((r) => r.name), ...(draft.selected_resume_ids.includes('persona') ? ['Persona'] : [])]
  const resumeHelp = selNames.length ? `New jobs are scored against ${selNames.join(', ')}.` : 'Nothing selected, so new jobs use your default résumé from Settings.'
  const bannerText = warnTextOf(company, downReason)
  const bannerMuted = !!bannerText && warnMuted(company)
  const tuningNote = (bannerText && !bannerMuted) ? 'needs attention' : (draft.scrape_interval_minutes || draft.wait_for_selector || (draft.max_pages && draft.max_pages !== 5) || draft.h1b_slug) ? 'customised' : 'using defaults'

  const [saveErr, setSaveErr] = useState('')
  const [saving, setSaving] = useState(false)
  const save = async () => {
    if (saving) return
    setSaveErr('')
    const payload = {
      name: draft.name,
      aliases: draft.aliases.split(',').map((s) => s.trim()).filter(Boolean),
      scrape_urls: draft.scrape_urls.filter(Boolean),
      title_include_expr: draft.title_include_expr || null,
      title_exclude_keywords: draft.title_exclude_keywords.split(',').map((s) => s.trim()).filter(Boolean),
      auto_scoring_depth: draft.auto_scoring_depth,
      selected_resume_ids: draft.selected_resume_ids,
      tier: draft.tier,
      // min/max on <input type=number> block neither typing nor a paste, so out-of-range
      // values (999 pages, a negative interval) must be clamped here before the PATCH.
      scrape_interval_minutes: draft.scrape_interval_minutes === '' ? null : (parseInt(draft.scrape_interval_minutes) > 0 ? parseInt(draft.scrape_interval_minutes) : null),
      wait_for_selector: draft.wait_for_selector || null,
      max_pages: Math.min(20, Math.max(1, parseInt(draft.max_pages) || 5)),
      h1b_slug: draft.h1b_slug || null,
    }
    // wait for the PATCH; only close on success, otherwise say so and keep the edit
    setSaving(true)
    const ok = await onSave(company.id, payload)
    setSaving(false)
    if (ok) setState(null); else setSaveErr('Save failed — nothing was changed. Try again.')
  }

  return (
    // ui's Drawer draws the backdrop (scoped to the pane) and routes outside clicks through onClose, so
    // the dirty-discard confirm still fires; Escape hits the same onClose and is idempotent with closeDrawer().
    <UiDrawer width={720} onClose={onClose}>
      <HeaderRow>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* ui: keep — the drawer title is serif 20/-.02em; Heading's 400-weight scale is 18/19/22 */}
          <span style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-.02em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{draft.name || company.name}</span>
          <Helper>{subtitle}</Helper>
        </div>
        <IconButton onClick={onClose} title="Close" style={{ flex: '0 0 auto' }}>✕</IconButton>
      </HeaderRow>

      <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '15px 22px 20px', display: 'flex', flexDirection: 'column', gap: 15, minHeight: 0 }}>
        {bannerText && (
          /* muted while the company is paused or the warning is acknowledged:
             the history is still worth reading, it just isn't an open problem */
          <Notice tone={bannerMuted ? 'quiet' : company.last_error ? 'bad' : 'warn'}
            action={!bannerMuted && onAcknowledge && (
              /* ui: keep — "Acknowledge" is the quiet inline action on the banner: --muted 11 normal weight, where Link is --link-ink 11.5/500 */
              <span onClick={() => onAcknowledge(company)} className="v2-hover-accent-text"
                title="Stop counting this company as needing attention. The warning stays here; a run that fails after this raises it again."
                style={{ flex: '0 0 auto', alignSelf: 'flex-start', fontSize: 11, color: 'var(--muted)', cursor: 'pointer' }}>Acknowledge</span>
            )}>
            <span style={{ fontSize: 12, color: bannerMuted ? 'var(--text-2)' : 'var(--text)', lineHeight: 1.5 }}>{bannerText}</span>
            <Helper size="xs">
              {company.last_error ? 'Last scrape run' : 'Detected in recent runs'} · last ran {ago(company.last_run_at || company.last_scraped_at)}
              {bannerMuted
                ? ` · ${company.active ? `acknowledged ${ago(company.warning_acknowledged_at)}` : 'paused, so it is not counted'}`
                : null}
            </Helper>
          </Notice>
        )}

        {/* identity + sources */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <Heading strong={600} size={15}>Identity and sources</Heading>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Display name</span>
            <Input value={draft.name} onChange={(v) => set({ name: v })} ariaLabel="Display name" />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Also known as</span>
            <Input value={draft.aliases} onChange={(v) => set({ aliases: v })} placeholder="Alt names, comma-separated" ariaLabel="Also known as" />
            <Helper size="xs">Postings under these names are matched to this company.</Helper>
          </div>
          <UrlEditor urls={draft.scrape_urls} onChange={(u) => set({ scrape_urls: u })} />
        </div>

        <Rule />

        {/* which postings to keep */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <Heading strong={600} size={15}>Which postings to keep</Heading>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Title must match</span>
            <Input value={draft.title_include_expr} onChange={(v) => set({ title_include_expr: v })} placeholder="(Product OR Project) AND Manager" ariaLabel="Title must match" />
            <Helper size="xs">Supports AND, OR and parentheses. Blank keeps every title.</Helper>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={fieldLabel}>Skip titles containing</span>
            <Input value={draft.title_exclude_keywords} onChange={(v) => set({ title_exclude_keywords: v })} placeholder="intern, junior, associate" ariaLabel="Skip titles containing" />
            <Helper size="xs">Comma-separated. Applied after the match above.</Helper>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={fieldLabel}>Score new jobs automatically</span>
            <Seg opts={DEPTHS} value={draft.auto_scoring_depth} onPick={(v) => set({ auto_scoring_depth: v })} />
            <div style={{ paddingTop: 2 }}><ResumeChips resumes={resumes} personaPopulated={personaPopulated} selected={draft.selected_resume_ids} toggle={toggleResume} /></div>
            <Helper size="xs">{resumeHelp}</Helper>
          </div>
        </div>

        <Rule />

        {/* scraper tuning */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div onClick={toggleTuning} style={{ display: 'flex', alignItems: 'center', gap: 9, cursor: 'pointer' }}>
            <span style={{ flex: '0 0 12px', display: 'inline-flex', justifyContent: 'center', position: 'relative', top: -2, fontSize: 11, color: 'var(--muted)' }}>{tuning ? '⌄' : '›'}</span>
            <Heading strong={600} size={15}>Scraper tuning</Heading>
            <Helper size="xs" style={{ ...(bannerMuted ? null : company.last_error ? { color: 'var(--bad)' } : downReason ? { color: 'var(--warn)' } : null) }}>{tuningNote}</Helper>
          </div>
          {tuning && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 11 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Priority tier</span>
                  <Seg opts={TIER_BTNS} value={draft.tier} onPick={(v) => set({ tier: v })} valueKey="v" />
                  <Helper size="xs">Groups companies for filtering and bulk actions.</Helper>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Scrape interval in minutes</span>
                  <Input type="number" min={1} value={draft.scrape_interval_minutes} onChange={(v) => set({ scrape_interval_minutes: v })} placeholder="Use global interval" ariaLabel="Scrape interval in minutes" />
                  <Helper size="xs">Blank follows the schedule set in Settings.</Helper>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Wait for element</span>
                  <Input value={draft.wait_for_selector} onChange={(v) => set({ wait_for_selector: v })} placeholder="CSS selector" mono ariaLabel="Wait for element" />
                  <Helper size="xs">CSS selector the page must render before reading.</Helper>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={fieldLabel}>Pages to read</span>
                  <Input type="number" min={1} max={20} value={draft.max_pages} onChange={(v) => set({ max_pages: v })} ariaLabel="Pages to read" />
                  <Helper size="xs">Maximum number of result pages to read.</Helper>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={fieldLabel}>H-1B employer name</span>
                <Input value={draft.h1b_slug} onChange={(v) => set({ h1b_slug: v })} placeholder="Auto-detect" mono ariaLabel="H-1B employer name" />
                <Helper size="xs" style={{ ...(lca ? { color: 'var(--good)' } : null) }}>{lcaLine}</Helper>
              </div>
            </div>
          )}
        </div>
      </div>

      <FooterRow bg="page" gap={8} style={{ flex: '0 0 auto' }}>
        {/* ui: keep — ink swings --warn/--accent with the company's state; Pill has no tinted variant */}
        <div onClick={() => { onSave(company.id, { active: !draft.active }); set({ active: !draft.active }) }} className="v2-bdc v2-ctl" style={{ height: 32, padding: '0 13px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', fontSize: 12, color: draft.active ? 'var(--warn)' : 'var(--accent)', whiteSpace: 'nowrap', cursor: 'pointer' }}>{draft.active ? 'Make inactive — jobs already found are kept' : 'Make active'}</div>
        {/* ui: keep — footer pill (r99), paired with the tinted one above it */}
        <div onClick={testingId ? undefined : () => onTest(company.id)} title={testingId && testingId !== company.id ? 'A test is already running' : undefined} className={testingId ? undefined : 'v2-act'} style={{ height: 32, padding: '0 13px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', cursor: testingId ? 'default' : 'pointer', opacity: testingId && testingId !== company.id ? 0.5 : 1 }}>
          {testingId === company.id && <Spinner />}
          {testingId === company.id ? 'Testing…' : 'Test scrape'}
        </div>
        {saveErr && <Helper style={{ marginLeft: 'auto', color: 'var(--bad)' }}>{saveErr}</Helper>}
        <Button size="sm" onClick={save} busy={saving} style={{ marginLeft: saveErr ? 10 : 'auto' }}>{saving ? 'Saving…' : 'Save changes'}</Button>
      </FooterRow>
    </UiDrawer>
  )
}

// ── add modal ─────────────────────────────────────────────────────────────────
function AddModal({ onClose, resumes, personaPopulated, onCreated, pushToast }) {
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
      : 'Unknown job board. The page is read as HTML. If no jobs are found, set a wait-for selector in the company settings.'
  const selNames = [...resumes.filter((r) => selected.includes(r.id)).map((r) => r.name), ...(selected.includes('persona') ? ['Persona'] : [])]
  const scoreNote = depth === 'off' ? 'New jobs arrive unscored — you can score them by hand from the feed.'
    : `New jobs are scored against ${selNames.length ? selNames.join(', ') : 'your default résumé from Settings'} as they arrive.`
  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  const save = async () => {
    if (saving) return
    if (!name.trim()) { pushToast({ kind: 'error', msg: 'Company name is required' }); return }
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
    } catch (e) {
      pushToast({ kind: 'error', msg: 'Could not add company' + (typeof e?.response?.data?.detail === 'string' ? ' — ' + e.response.data.detail : '') })
      setSaving(false)
    }
  }

  return (
    <ModalPanel width={520} onClose={onClose} zIndex={60} style={{ overflow: 'hidden' }}>
        <HeaderRow align="stretch" style={{ flexDirection: 'column', gap: 3 }}>
          <Heading>Add company</Heading>
          <Helper>Paste a careers URL — the ATS is read from it.</Helper>
        </HeaderRow>
        <div className="v2-scroll" style={{ padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 470, overflow: 'auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>Career page URL</Label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              {/* ui: keep — the ATS badge: mono 9.5/.05em/pad 3 8 painted by its cc-* class; Tag is 10/.06em/pad 2 8 */}
              <span className={url ? atsSlug(ats) : undefined} style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '.05em', textTransform: 'uppercase', padding: '3px 8px', borderRadius: 'var(--radius-control)', background: url ? undefined : 'var(--surface-2)', color: url ? undefined : 'var(--muted)', whiteSpace: 'nowrap' }}>{url ? ats : '—'}</span>
              <Input value={url} onChange={setUrl} placeholder="https://boards.greenhouse.io/acme" mono ariaLabel="Career page URL" style={{ flex: 1, minWidth: 0 }} />
            </div>
            <Helper style={{ ...(url && !known ? { color: 'var(--warn)' } : null) }}>{atsNote}</Helper>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <Label>Company name</Label>
              <Input value={name} onChange={setName} placeholder="Acme" ariaLabel="Company name" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <Label>Aliases</Label>
              <Input value={aliases} onChange={setAliases} placeholder="Alt names, comma-separated" ariaLabel="Aliases" />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <Label>Tier</Label>
              <Seg opts={TIER_BTNS} value={tier} onPick={setTier} valueKey="v" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <Label>Scrape interval in minutes</Label>
              <Input type="number" min={1} value={interval} onChange={setIntervalV} placeholder="Use global interval" ariaLabel="Scrape interval in minutes" />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, paddingTop: 2, borderTop: '1px solid var(--line-soft)', marginTop: 2 }}>
            <Label style={{ paddingTop: 8 }}>Score new jobs against</Label>
            <ResumeChips resumes={resumes} personaPopulated={personaPopulated} selected={selected} toggle={toggle} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 2 }}>
              <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>Depth</span>
              {/* same auto_scoring_depth control as the drawer, via Seg, for a consistent segmented control */}
              <Segmented size="sm" ariaLabel="Auto-scoring depth" value={depth} onChange={setDepth}
                options={DEPTHS.map((d) => ({ value: d.id, label: d.label, hint: d.hint }))}
                style={{ flex: 1 }} />
            </div>
          </div>
          <Helper style={{ paddingTop: 2 }}>{scoreNote}</Helper>
          <Helper>Title filters, wait-for selector and max pages use the defaults. Change them in the company settings if needed.</Helper>
        </div>
        <FooterRow bg="page" style={{ flex: '0 0 auto' }}>
          <Helper>Scrapes on the next scheduled run</Helper>
          <Button variant="secondary" size="sm" onClick={onClose} style={{ marginLeft: 'auto' }}>Cancel</Button>
          <Button size="sm" onClick={save} busy={saving}>{saving ? 'Saving…' : 'Save'}</Button>
        </FooterRow>
    </ModalPanel>
  )
}

// ── test scrape modal ─────────────────────────────────────────────────────────
function TestModal({ test, onClose, showShots, setShowShots }) {
  const [limit, setLimit] = useState(TEST_PAGE)
  useEffect(() => { setLimit(TEST_PAGE) }, [test])   // a fresh run starts at page 1
  if (test.error) {
    return (
      <ModalPanel width={520} onClose={onClose} zIndex={60} style={{ padding: 22 }}>
        <Heading style={{ display: 'block', marginBottom: 10 }}>Test scrape — Error</Heading>
        <div style={{ fontSize: 12.5, color: 'var(--bad)' }}>{test.error}</div>
        <Pill onClick={onClose} style={{ marginTop: 16 }}>Close</Pill>
      </ModalPanel>
    )
  }
  const jobs = test.jobs || []
  const kept = test.after_filter ?? jobs.filter((j) => j.kept).length
  const rejected = test.total_rejected || 0
  const found = test.total_found ?? jobs.length
  // total_found already excludes the validation-rejected rows (routes_companies.py:
  // len(all_jobs) vs len(all_rejected)), so the four numbers add up to the rows shown.
  const passCo = typeof test.after_company_filter === 'number' ? test.after_company_filter : null
  // the run also drops jobs whose body matches a body_exclusion_phrases entry, stored as `ignored` —
  // a class the preview above doesn't count, so "kept" can exceed what's actually saved.
  const bodyExcluded = test.body_excluded_count ?? 0
  const bodyUnchecked = test.body_unchecked_count ?? 0
  const bodyPhrases = test.body_phrase_count ?? 0
  const summary = `${found + rejected} found · ${kept} kept · ${Math.max(0, found - kept - bodyExcluded)} removed by title filter`
    + (bodyExcluded ? ` · ${bodyExcluded} would be ignored (body phrases)` : '')
    + ` · ${rejected} invalid`
    + (passCo != null && passCo !== kept ? ` · ${passCo} pass this company's filters · ${Math.max(0, passCo - kept - bodyExcluded)} removed by the global exclude list` : '')
    + (bodyUnchecked ? ` · ${bodyUnchecked} not body-checked (needs the description)` : '')
  const urls = test.urls_scraped || []
  const pag = test.pagination_debug || []
  const shots = test.screenshots || []
  const jobState = (j) => {
    if (j.reason?.startsWith('[Validation]')) return { tag: 'Drop', tagBg: 'var(--warn-soft)', tagFg: 'var(--warn)', reasonFg: 'var(--warn)', reason: j.reason.replace('[Validation] ', '') }
    // a body-phrase drop is stored as `ignored`, not filtered out of the feed; label it with the phrase that did it.
    if (j.body_excluded_by) return { tag: 'Ignored', tagBg: 'var(--warn-soft)', tagFg: 'var(--warn)', reasonFg: 'var(--warn)', reason: j.reason || `Body exclusion: ${j.body_excluded_by}` }
    if (j.kept) return {
      tag: 'Kept', tagBg: 'var(--accent-soft)', tagFg: 'var(--good)', reasonFg: 'var(--muted)',
      // a kept row the body scan couldn't run on is not a promise — say so
      reason: j.reason || (bodyPhrases > 0 && j.body_checked === false ? 'body check needs the description' : ''),
    }
    if (j.reason?.startsWith('[Global]')) return { tag: 'Global', tagBg: 'var(--warn-soft)', tagFg: 'var(--warn)', reasonFg: 'var(--warn)', reason: j.reason.replace('[Global] ', '') }   // the global exclude list, not this company's filters
    return { tag: 'Out', tagBg: 'var(--bad-soft)', tagFg: 'var(--bad)', reasonFg: 'var(--bad)', reason: j.reason || '' }
  }
  return (
    <ModalPanel width={840} onClose={onClose} zIndex={60} style={{ maxHeight: 660, overflow: 'hidden' }}>
        <HeaderRow variant="compact" align="center" style={{ gap: 10 }}>
          <Heading>Test scrape — {test.company}</Heading>
          {shots.length > 0 && (
            <Pill size="sm" on={showShots} onClick={() => setShowShots((v) => !v)} style={{ marginLeft: 'auto' }}>{showShots ? 'Hide' : 'Show'} screenshots</Pill>
          )}
          <IconButton onClick={onClose} title="Close" style={{ marginLeft: shots.length ? 0 : 'auto' }}>✕</IconButton>
        </HeaderRow>

        <HeaderRow align="stretch" pad="9px 22px" bg="page" soft style={{ flexDirection: 'column', gap: 2 }}>
          <Helper>URLs scraped · {urls.length}</Helper>
          {urls.map((u, i) => <Helper key={i} size="xs" mono style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u}</Helper>)}
          {(test.include_expr || (test.exclude_keywords || []).length > 0) && (
            <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
              {test.include_expr && <>Include <span style={{ fontFamily: 'var(--mono)', fontSize: 10, background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 'var(--radius-inline)' }}>{test.include_expr}</span> </>}
              {(test.exclude_keywords || []).length > 0 && <>· Exclude <span style={{ fontFamily: 'var(--mono)', fontSize: 10, background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 'var(--radius-inline)' }}>{test.exclude_keywords.join(', ')}</span></>}
            </span>
          )}
        </HeaderRow>

        {showShots && shots.length > 0 && (
          <HeaderRow align="stretch" pad="11px 22px" bg="page" soft style={{ flexDirection: 'column', gap: 8, maxHeight: 280, overflow: 'auto' }}>
            {shots.map((s, i) => (
              <div key={i}>
                <Helper size="xs" mono>{s.url}</Helper>
                <img src={`data:image/png;base64,${s.data}`} alt="" style={{ width: '100%', border: '1px solid var(--line)', borderRadius: 'var(--radius-cell)', marginTop: 4 }} />
              </div>
            ))}
          </HeaderRow>
        )}

        {pag.length > 0 && (
          <HeaderRow align="stretch" pad="10px 22px" bg="recessed" soft style={{ flexDirection: 'column', gap: 3 }}>
            {/* ui: keep — the debug band's head is accent at weight 600; Label is --label-ink at 400 */}
            <span style={{ fontSize: 10, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--accent)', fontWeight: 600 }}>Page-by-page details</span>
            {pag.map((p, i) => (
              <span key={i} style={{ fontSize: 11, color: p.clicked ? 'var(--good)' : 'var(--bad)' }}>Page {p.page} · {p.clicked ? `Clicked ${p.clicked_via?.selector || ''} — ${p.clicked_via?.text || ''}` : 'No next button found'}</span>
            ))}
          </HeaderRow>
        )}

        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <TableHead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
            <span style={{ flex: '0 0 30px' }}>#</span>
            <span style={{ flex: 1, minWidth: 0 }}>Title</span>
            <span style={{ flex: '0 0 62px' }}>Status</span>
            <span style={{ flex: '0 0 260px' }}>Reason</span>
            <span style={{ flex: '0 0 40px', textAlign: 'right' }}>Link</span>
          </TableHead>
          {jobs.slice(0, limit).map((j, i) => {
            const st = jobState(j)
            return (
              <TableRow key={i} height={32} pad="0 22px">
                <Mono size="sm" tone="muted" style={{ flex: '0 0 30px' }}>{i + 1}</Mono>
                <span title={j.title} style={{ flex: 1, minWidth: 0, fontSize: 12, color: j.kept ? 'var(--text)' : 'var(--muted)', textDecoration: j.kept ? 'none' : 'line-through', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{j.title}</span>
                {/* ui: keep — the test row's kept/dropped tag (9.5 · pad 2 7, tinted from `st`); Tag is 10/pad 2 8 */}
                <span style={{ flex: '0 0 62px' }}><span style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', background: st.tagBg, color: st.tagFg }}>{st.tag}</span></span>
                <span title={st.reason} style={{ flex: '0 0 260px', fontSize: 11, color: st.reasonFg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 10 }}>{st.reason}</span>
                {/* Link takes `rel`, so the ↗ isn't a hand-written anchor; it keeps the row's own 11px glyph size */}
                <span style={{ flex: '0 0 40px', textAlign: 'right' }}><Link href={j.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, fontWeight: 400, lineHeight: 'inherit' }}>↗</Link></span>
              </TableRow>
            )
          })}
          {jobs.length > limit && <ShowMore n={Math.min(TEST_PAGE, jobs.length - limit)} onClick={() => setLimit((n) => n + TEST_PAGE)} />}
          {jobs.length === 0 && <div style={{ textAlign: 'center', padding: 32, color: 'var(--muted)', fontSize: 12.5 }}>No job links found on this page.</div>}
        </div>

        <FooterRow variant="compact" bg="page" style={{ flex: '0 0 auto' }}>
          <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{summary}{jobs.length > limit ? ` · showing the first ${limit}` : ''}</span>
          <Pill onClick={onClose} style={{ marginLeft: 'auto' }}>Close</Pill>
        </FooterRow>
    </ModalPanel>
  )
}
