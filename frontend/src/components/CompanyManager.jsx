import React, { useState, useEffect } from 'react'
import api from '../api'
import { Plus, Edit2, X, Play, Loader2, ExternalLink, Camera, Power, PowerOff, Tags, FlaskConical } from 'lucide-react'

const TIER_LABELS = { 1: 'Tier 1', 2: 'Tier 2', 3: 'Tier 3' }
const TIER_COLORS = { 1: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', 2: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300', 3: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' }

const ATS_TYPES = [
  { id: 'Workday', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300' },
  { id: 'Oracle HCM', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
  { id: 'Lever', color: 'bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300' },
  { id: 'Phenom', color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300' },
  { id: 'TalentBrew', color: 'bg-lime-100 text-lime-700 dark:bg-lime-900 dark:text-lime-300' },
  { id: 'Ashby', color: 'bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300' },
  { id: 'Greenhouse', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' },
  { id: 'Rippling', color: 'bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300' },
  { id: 'Eightfold', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' },
  { id: 'Apple', color: 'bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-200' },
  { id: 'Meta', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  { id: 'Google', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300' },
  { id: 'Uber', color: 'bg-gray-900 text-white dark:bg-gray-200 dark:text-gray-900' },
  { id: 'Visa', color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300' },
  { id: 'Generic', color: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400' },
]

const ATS_COLOR_MAP = Object.fromEntries(ATS_TYPES.map(t => [t.id, t.color]))

// Legacy mapping for backend detected_scrape_types
const SCRAPE_TYPE_COLORS = Object.fromEntries([
  ['Workday API', ATS_COLOR_MAP.Workday], ['Oracle HCM API', ATS_COLOR_MAP['Oracle HCM']],
  ['Lever API', ATS_COLOR_MAP.Lever], ['Phenom API', ATS_COLOR_MAP.Phenom],
  ['TalentBrew AJAX', ATS_COLOR_MAP.TalentBrew], ['Ashby API', ATS_COLOR_MAP.Ashby],
  ['Greenhouse API', ATS_COLOR_MAP.Greenhouse], ['Rippling API', ATS_COLOR_MAP.Rippling],
  ['Meta Careers (Playwright)', ATS_COLOR_MAP.Meta], ['Google Careers (Playwright)', ATS_COLOR_MAP.Google],
  ['Generic (Playwright)', ATS_COLOR_MAP.Generic],
])

// Hostname-safe URL matching helpers. These avoid the "substring of URL"
// pitfall where e.g. "evil-metacareers.com" would match "metacareers.com".
function hostMatches(url, ...domains) {
  let host
  try { host = new URL(url).hostname.toLowerCase() } catch { return false }
  return domains.some(raw => {
    const d = (raw || '').toLowerCase().replace(/\/$/, '')
    return d && (host === d || host.endsWith('.' + d))
  })
}

function pathContains(url, ...needles) {
  let path
  try { path = new URL(url).pathname.toLowerCase() } catch { return false }
  return needles.some(n => n && path.includes(n.toLowerCase()))
}

function detectAtsType(url) {
  if (!url) return 'Generic'
  // POST|<url>|<payload> prefix is not a URL at all — keep as-is.
  if (url.toUpperCase().startsWith('POST|')) return 'Phenom'
  if (hostMatches(url, 'myworkdayjobs.com')) return 'Workday'
  if (hostMatches(url, 'oraclecloud.com') && pathContains(url, '/hcmui/')) return 'Oracle HCM'
  if (hostMatches(url, 'careers.oracle.com')) return 'Oracle HCM'
  if (hostMatches(url, 'jobs.lever.co', 'jobs.eu.lever.co')) return 'Lever'
  if (hostMatches(url, 'jobs.ashbyhq.com')) return 'Ashby'
  if (hostMatches(url, 'greenhouse.io')) return 'Greenhouse'
  if (hostMatches(url, 'ats.rippling.com') || (hostMatches(url, 'rippling.com') && pathContains(url, '/careers'))) return 'Rippling'
  if (hostMatches(url, 'eightfold.ai', 'apply.careers.microsoft.com')) return 'Eightfold'
  if (hostMatches(url, 'jobs.apple.com')) return 'Apple'
  if (hostMatches(url, 'metacareers.com')) return 'Meta'
  if (hostMatches(url, 'google.com') && pathContains(url, '/about/careers')) return 'Google'
  if (hostMatches(url, 'uber.com') && pathContains(url, '/careers')) return 'Uber'
  if (hostMatches(url, 'visa.com') && pathContains(url, '/jobs')) return 'Visa'
  return 'Generic'
}

function UrlListEditor({ urls, onChange }) {
  // urls: array of { url: string, atsType: string }
  const handleUrlChange = (index, newUrl) => {
    const updated = [...urls]
    const oldUrl = updated[index].url
    updated[index] = { ...updated[index], url: newUrl }
    // Re-detect ATS only if URL actually changed
    if (newUrl !== oldUrl) {
      updated[index].atsType = detectAtsType(newUrl)
    }
    onChange(updated)
  }
  const handleAtsChange = (index, newType) => {
    const updated = [...urls]
    updated[index] = { ...updated[index], atsType: newType }
    onChange(updated)
  }
  const addUrl = () => onChange([...urls, { url: '', atsType: 'Generic' }])
  const removeUrl = (index) => onChange(urls.filter((_, i) => i !== index))

  return (
    <div className="space-y-1.5">
      {urls.map((item, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <select value={item.atsType || 'Generic'} onChange={e => handleAtsChange(i, e.target.value)}
            className={`text-[10px] px-1.5 py-1.5 rounded border-0 font-medium cursor-pointer flex-shrink-0 w-[85px] ${ATS_COLOR_MAP[item.atsType] || ATS_COLOR_MAP.Generic}`}>
            {ATS_TYPES.map(t => <option key={t.id} value={t.id}>{t.id}</option>)}
          </select>
          <input type="text" value={item.url} onChange={e => handleUrlChange(i, e.target.value)}
            placeholder="https://boards.greenhouse.io/company or POST|https://..."
            className="border rounded px-2 py-1 text-sm font-mono flex-1 min-w-0 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          <button onClick={() => removeUrl(i)} className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 flex-shrink-0 p-0.5">
            <X size={14} />
          </button>
        </div>
      ))}
      <button onClick={addUrl} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
        <Plus size={12} /> Add URL
      </button>
    </div>
  )
}

// Convert between flat url array (backend) and url+atsType array (editor)
function urlsToEditorFormat(urls) {
  return (urls || []).map(u => ({ url: u, atsType: detectAtsType(u) }))
}
function editorToUrls(items) {
  return items.map(i => i.url).filter(Boolean)
}

// Legacy helpers
const urlsToText = (urls) => (urls || []).join('\n')
const textToUrls = (text) => text.split('\n').map(s => s.trim()).filter(Boolean)

export default function CompanyManager() {
  const [companies, setCompanies] = useState([])
  const [cvs, setCvs] = useState([])
  const [editModal, setEditModal] = useState(null)
  const [editData, setEditData] = useState({})
  const [showAdd, setShowAdd] = useState(false)
  const [newCompany, setNewCompany] = useState({
    name: '', tier: 2, scrape_urls_editor: [], selected_cv_ids: [],
    scrape_interval_minutes: '', title_include_expr: '',
    title_exclude_keywords: '', wait_for_selector: '', max_pages: 5, notes: ''
  })
  const [filterTiers, setFilterTiers] = useState(() => {
    try { const v = localStorage.getItem('company_filter_tiers'); return v ? JSON.parse(v) : [] } catch { return [] }
  })
  const [testResult, setTestResult] = useState(null)
  const [showScreenshots, setShowScreenshots] = useState(false)
  const [testing, setTesting] = useState(null)
  const [scraping, setScraping] = useState(null)

  const fetchCompanies = async () => {
    try {
      const { data } = await api.get('/companies')
      setCompanies(data)
    } catch (e) { console.error(e) }
  }

  const fetchCvs = async () => {
    try {
      const { data } = await api.get('/cvs')
      setCvs(data)
    } catch (e) { console.error(e) }
  }

  useEffect(() => { fetchCompanies(); fetchCvs() }, [])
  useEffect(() => { try { localStorage.setItem('company_filter_tiers', JSON.stringify(filterTiers)) } catch {} }, [filterTiers])

  const saveEdit = async (id) => {
    try {
      const payload = { ...editData }
      if (typeof payload.title_exclude_keywords === 'string') {
        payload.title_exclude_keywords = payload.title_exclude_keywords
          .split(',').map(s => s.trim()).filter(Boolean)
      }
      if (payload.scrape_urls_editor) {
        payload.scrape_urls = editorToUrls(payload.scrape_urls_editor)
        delete payload.scrape_urls_editor
      } else if (typeof payload.scrape_urls === 'string') {
        payload.scrape_urls = textToUrls(payload.scrape_urls)
      }
      // Convert empty string interval to null
      if (payload.scrape_interval_minutes === '' || payload.scrape_interval_minutes === null) {
        payload.scrape_interval_minutes = null
      } else if (payload.scrape_interval_minutes !== undefined) {
        payload.scrape_interval_minutes = parseInt(payload.scrape_interval_minutes) || null
      }
      await api.patch(`/companies/${id}`, payload)
      fetchCompanies()
    } catch (e) { console.error(e) }
  }

  const addCompany = async () => {
    try {
      const { scrape_urls_editor, aliases, ...rest } = newCompany
      const payload = {
        ...rest,
        scrape_urls: editorToUrls(scrape_urls_editor),
        aliases: typeof aliases === 'string' ? aliases.split(',').map(s => s.trim()).filter(Boolean) : (aliases || []),
        title_exclude_keywords: newCompany.title_exclude_keywords
          ? newCompany.title_exclude_keywords.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        title_include_expr: newCompany.title_include_expr || null,
        wait_for_selector: newCompany.wait_for_selector || null,
        max_pages: parseInt(newCompany.max_pages) || 5,
        scrape_interval_minutes: newCompany.scrape_interval_minutes
          ? parseInt(newCompany.scrape_interval_minutes) : null,
      }
      await api.post('/companies', payload)
      setShowAdd(false)
      setNewCompany({
        name: '', tier: 2, scrape_urls_editor: [], selected_cv_ids: [],
        scrape_interval_minutes: '', title_include_expr: '',
        title_exclude_keywords: '', wait_for_selector: '', max_pages: 5, notes: ''
      })
      fetchCompanies()
    } catch (e) { console.error(e) }
  }

  const toggleActive = async (id, active) => {
    await api.patch(`/companies/${id}`, { active: !active })
    fetchCompanies()
  }

  const bulkActivate = async (active) => {
    try {
      const payload = { active }
      if (filterTiers.length > 0) payload.tiers = filterTiers
      await api.post('/companies/bulk-activate', payload)
      fetchCompanies()
    } catch (e) { console.error(e) }
  }

  const runTestScrape = async (companyId) => {
    setTesting(companyId)
    setTestResult(null)
    try {
      const { data } = await api.post(`/companies/${companyId}/test-scrape`)
      setTestResult(data)
    } catch (e) {
      setTestResult({ error: e.response?.data?.detail || e.message })
    }
    setTesting(null)
  }

  const runScrape = async (companyId) => {
    setScraping(companyId)
    try {
      await api.post(`/scrape/company/${companyId}`)
    } catch (e) { console.error(e) }
    setTimeout(() => setScraping(null), 3000)
  }

  // CV multi-select toggle helper
  const toggleCvSelection = (cvId, currentIds, setter) => {
    const ids = currentIds || []
    if (ids.includes(cvId)) {
      setter(ids.filter(id => id !== cvId))
    } else {
      setter([...ids, cvId])
    }
  }

  const filtered = filterTiers.length === 0
    ? companies
    : companies.filter(c => filterTiers.includes(c.tier == null ? 'none' : String(c.tier)))

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Company Manager</h1>
        <div className="flex gap-2">
          <button onClick={() => bulkActivate(true)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100 dark:bg-green-900 dark:text-green-300 dark:border-green-700 dark:hover:bg-green-800"
            title="Activate All">
            <Power size={14} /> Activate All
          </button>
          <button onClick={() => bulkActivate(false)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 dark:bg-red-900 dark:text-red-300 dark:border-red-700 dark:hover:bg-red-800"
            title="Deactivate All">
            <PowerOff size={14} /> Deactivate All
          </button>
          {['1','2','3','none'].map(t => (
            <button key={t} onClick={() => setFilterTiers(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t])}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                filterTiers.includes(t)
                  ? 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-700'
                  : 'bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:bg-gray-50'
              }`}>
              {t === 'none' ? 'Untiered' : `Tier ${t}`}
            </button>
          ))}
          <button onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Plus size={14} /> Add Company
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-4">
          {/* Row 1: Name, Aliases, Tier */}
          <div className="grid grid-cols-4 gap-3 mb-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Company Name</label>
              <input type="text" placeholder="e.g. Stripe" value={newCompany.name}
                onChange={e => setNewCompany({...newCompany, name: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Aliases</label>
              <input type="text" placeholder="Alt names, comma-separated" value={newCompany.aliases || ''}
                onChange={e => setNewCompany({...newCompany, aliases: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Tier</label>
              <select value={newCompany.tier ?? ''} onChange={e => setNewCompany({...newCompany, tier: e.target.value === '' ? null : parseInt(e.target.value)})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="">Untiered</option>
                <option value={1}>Tier 1</option>
                <option value={2}>Tier 2</option>
                <option value={3}>Tier 3</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Scrape Interval (min)</label>
              <input type="number" min={1} placeholder="Use global" value={newCompany.scrape_interval_minutes}
                onChange={e => setNewCompany({...newCompany, scrape_interval_minutes: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
          </div>
          {/* Row 2: Title filters */}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Include Expression</label>
              <input type="text" placeholder="(Product OR Project) AND Manager"
                value={newCompany.title_include_expr}
                onChange={e => setNewCompany({...newCompany, title_include_expr: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Supports AND, OR, parentheses</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Exclude Keywords</label>
              <input type="text" placeholder="intern, junior, associate"
                value={newCompany.title_exclude_keywords}
                onChange={e => setNewCompany({...newCompany, title_exclude_keywords: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
          </div>
          {/* Row 3: CVs + Auto Scoring */}
          <div className="flex items-center gap-4 mb-3 flex-wrap">
            {cvs.length > 0 && (
              <>
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Score Against CVs:</label>
                {cvs.map(cv => (
                  <label key={cv.id} className="flex items-center gap-1 text-xs cursor-pointer">
                    <input type="checkbox"
                      checked={(newCompany.selected_cv_ids || []).includes(cv.id)}
                      onChange={() => {
                        const ids = newCompany.selected_cv_ids || []
                        setNewCompany({...newCompany, selected_cv_ids:
                          ids.includes(cv.id) ? ids.filter(id => id !== cv.id) : [...ids, cv.id]
                        })
                      }} />
                    {cv.version}
                  </label>
                ))}
                <span className="text-xs text-gray-400 dark:text-gray-500">(none = all)</span>
                <span className="text-gray-300 dark:text-gray-600">|</span>
              </>
            )}
            <label className="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-400">
              Auto Scoring:
              <select value={newCompany.auto_scoring_depth || 'off'}
                onChange={e => setNewCompany({...newCompany, auto_scoring_depth: e.target.value})}
                className="border rounded px-1.5 py-0.5 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="off">Off</option>
                <option value="light">Light</option>
                <option value="full">Full</option>
              </select>
            </label>
          </div>
          {/* Row 4: URLs */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Career Page URLs</label>
            <UrlListEditor
              urls={newCompany.scrape_urls_editor}
              onChange={items => setNewCompany({...newCompany, scrape_urls_editor: items})}
            />
          </div>
          {/* Row 5: Advanced */}
          <div className="grid grid-cols-4 gap-3 mb-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">H-1B Slug</label>
              <input type="text" placeholder="Auto-detect"
                value={newCompany.h1b_slug || ''}
                onChange={e => setNewCompany({...newCompany, h1b_slug: e.target.value || null})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Wait-for Selector</label>
              <input type="text" placeholder="CSS selector"
                value={newCompany.wait_for_selector}
                onChange={e => setNewCompany({...newCompany, wait_for_selector: e.target.value})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div className="w-20">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Max Pages</label>
              <input type="number" min={1} max={20} value={newCompany.max_pages}
                onChange={e => setNewCompany({...newCompany, max_pages: parseInt(e.target.value) || 5})}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addCompany} className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700">Save</button>
            <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm border dark:border-gray-600 rounded hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700">Cancel</button>
          </div>
        </div>
      )}

      {/* Test Scrape Results Modal */}
      {testResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setTestResult(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[900px] max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b dark:border-gray-700 flex-shrink-0">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                Test Scrape {testResult.error ? '— Error' : `— ${testResult.company}`}
              </h2>
              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                {(testResult.screenshots || []).length > 0 && (
                  <button onClick={() => setShowScreenshots(!showScreenshots)}
                    className={`flex items-center gap-1 px-2 py-1 text-xs rounded whitespace-nowrap ${showScreenshots ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200'}`}>
                    <Camera size={14} /> {showScreenshots ? 'Hide' : 'Show'} Screenshots
                  </button>
                )}
                <button onClick={() => { setTestResult(null); setShowScreenshots(false) }} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1"><X size={18} /></button>
              </div>
            </div>

            {testResult.error ? (
              <div className="p-5 text-red-600 text-sm">{testResult.error}</div>
            ) : (
              <div className="overflow-y-auto flex-1">
                {/* Scrape info */}
                <div className="text-xs text-gray-500 dark:text-gray-400 px-5 py-2 border-b dark:border-gray-700 space-y-0.5 bg-gray-50 dark:bg-gray-700">
                  <p>URLs: {(testResult.urls_scraped || []).length}</p>
                  {(testResult.urls_scraped || []).map((u, i) => (
                    <p key={i} className="text-gray-400 dark:text-gray-500 truncate">{u}</p>
                  ))}
                  {testResult.include_expr && <p>Include: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">{testResult.include_expr}</code></p>}
                  {testResult.exclude_keywords?.length > 0 && <p>Exclude: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">{testResult.exclude_keywords.join(', ')}</code></p>}
                </div>

                {/* Screenshots */}
                {showScreenshots && (testResult.screenshots || []).length > 0 && (
                  <div className="border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700 p-3 space-y-3">
                    {testResult.screenshots.map((s, i) => (
                      <div key={i}>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate">{s.url}</p>
                        <img src={`data:image/png;base64,${s.data}`} alt={`Screenshot ${i+1}`}
                          className="w-full border rounded shadow-sm" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Pagination debug */}
                {(testResult.pagination_debug || []).length > 0 && (
                  <div className="border-b bg-indigo-50 px-3 py-2 text-xs space-y-1">
                    <p className="font-bold text-indigo-700">Pagination debug</p>
                    {testResult.pagination_debug.map((p, i) => (
                      <div key={i} className="ml-2">
                        <p className={p.clicked ? 'text-green-700' : 'text-red-600'}>
                          Page {p.page}: {p.clicked ? <>Clicked <code className="bg-white px-1 rounded">{p.clicked_via?.selector}</code> — tag={p.clicked_via?.tag} text="{p.clicked_via?.text}"</> : 'No next button found'}
                        </p>
                        {p.candidates?.length > 0 && (
                          <details className="ml-2">
                            <summary className="text-gray-500 cursor-pointer">{p.candidates.length} candidate(s) evaluated</summary>
                            {p.candidates.map((c, ci) => (
                              <p key={ci} className="text-gray-400 ml-2">
                                {c.selector} — {c.tag} "{c.text}" visible={String(c.visible)} disabled={String(c.disabled)} aria_disabled={String(c.aria_disabled)}
                              </p>
                            ))}
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <table className="w-full text-sm text-gray-900 dark:text-gray-200">
                  <thead className="bg-gray-50 dark:bg-gray-700 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-8">#</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400">Title</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-16">Status</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400">Reason</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-10">Link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(testResult.jobs || []).filter(j => !j.reason?.startsWith('[Validation]')).map((j, i) => (
                      <tr key={i} className={`border-t dark:border-gray-700 ${j.kept ? 'hover:bg-gray-50 dark:hover:bg-gray-700' : 'bg-red-50/50 dark:bg-red-900/30'}`}>
                        <td className="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">{i + 1}</td>
                        <td className={`px-3 py-1.5 ${j.kept ? 'dark:text-gray-200' : 'text-gray-400 line-through'}`}>{j.title}</td>
                        <td className="px-3 py-1.5">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${j.kept ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
                            {j.kept ? 'Kept' : 'Out'}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-xs text-red-500 max-w-[200px] truncate" title={j.reason || ''}>
                          {j.reason || ''}
                        </td>
                        <td className="px-3 py-1.5 text-right">
                          <a href={j.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
                            <ExternalLink size={14} />
                          </a>
                        </td>
                      </tr>
                    ))}
                    {/* Rejected by validation section */}
                    {(testResult.jobs || []).some(j => j.reason?.startsWith('[Validation]')) && (
                      <>
                        <tr className="bg-yellow-50 dark:bg-yellow-900/40 border-t-2 border-yellow-300 dark:border-yellow-700">
                          <td colSpan={5} className="px-3 py-2 text-xs font-bold text-yellow-700 dark:text-yellow-300">
                            Rejected by validation ({(testResult.jobs || []).filter(j => j.reason?.startsWith('[Validation]')).length} entries)
                          </td>
                        </tr>
                        {(testResult.jobs || []).filter(j => j.reason?.startsWith('[Validation]')).map((j, i) => (
                          <tr key={`r${i}`} className="border-t bg-yellow-50/30 dark:bg-yellow-900/20">
                            <td className="px-3 py-1 text-xs text-gray-300">{i + 1}</td>
                            <td className="px-3 py-1 text-xs text-gray-400">{j.title}</td>
                            <td className="px-3 py-1">
                              <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700">Drop</span>
                            </td>
                            <td className="px-3 py-1 text-xs text-yellow-600 max-w-[250px] truncate" title={j.reason}>
                              {j.reason?.replace('[Validation] ', '')}
                            </td>
                            <td className="px-3 py-1 text-right">
                              <a href={j.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-600">
                                <ExternalLink size={12} />
                              </a>
                            </td>
                          </tr>
                        ))}
                      </>
                    )}
                  </tbody>
                </table>
                {(testResult.jobs || []).length === 0 && (
                  <p className="text-center py-8 text-gray-400 dark:text-gray-500">No job links found on this page.</p>
                )}
              </div>
            )}

            <div className="px-5 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700 flex justify-between items-center rounded-b-xl">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {!testResult.error && (
                  <>
                    <span className="font-medium text-green-700">{testResult.after_filter}</span>
                    <span> kept / </span>
                    <span className="font-medium text-red-600">{testResult.total_found - testResult.after_filter}</span>
                    <span> keyword-filtered / </span>
                    <span className="font-medium">{testResult.total_found}</span>
                    <span> extracted</span>
                    {testResult.total_rejected > 0 && (
                      <>
                        <span> / </span>
                        <span className="font-medium text-yellow-600">{testResult.total_rejected}</span>
                        <span> validation-rejected</span>
                      </>
                    )}
                  </>
                )}
              </span>
              <button onClick={() => setTestResult(null)} className="px-4 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-500">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Company Modal */}
      {editModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setEditModal(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[700px] max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b dark:border-gray-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Edit: {editModal.name}</h2>
              <button onClick={() => setEditModal(null)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Name + Aliases */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Company Name</label>
                  <input type="text" defaultValue={editModal.name}
                    onChange={e => setEditData({...editData, name: e.target.value})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Aliases (comma-separated)</label>
                  <input type="text" defaultValue={(editModal.aliases || []).join(', ')}
                    onChange={e => setEditData({...editData, aliases: e.target.value.split(',').map(s => s.trim()).filter(Boolean)})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              </div>

              {/* Tier + Interval + H-1B Slug */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Tier</label>
                  <select defaultValue={editModal.tier ?? ''} className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
                    onChange={e => setEditData({...editData, tier: e.target.value === '' ? null : parseInt(e.target.value)})}>
                    <option value="">Untiered</option>
                    <option value={1}>Tier 1</option>
                    <option value={2}>Tier 2</option>
                    <option value={3}>Tier 3</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Scrape Interval (min)</label>
                  <input type="number" min={1} defaultValue={editModal.scrape_interval_minutes || ''}
                    placeholder="Use global"
                    onChange={e => setEditData({...editData, scrape_interval_minutes: e.target.value})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">H-1B Slug</label>
                  <input type="text" defaultValue={editModal.h1b_slug || ''}
                    placeholder="Auto-detect"
                    onChange={e => setEditData({...editData, h1b_slug: e.target.value || null})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              </div>

              {/* CVs + Auto Scoring */}
              <div className="flex items-center gap-4 flex-wrap">
                {cvs.length > 0 && (
                  <>
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Score Against CVs:</label>
                    {cvs.map(cv => (
                      <label key={cv.id} className="flex items-center gap-1.5 text-sm cursor-pointer">
                        <input type="checkbox"
                          defaultChecked={(editModal.selected_cv_ids || []).includes(cv.id)}
                          onChange={e => {
                            const current = editData.selected_cv_ids || editModal.selected_cv_ids || []
                            const updated = e.target.checked
                              ? [...current, cv.id]
                              : current.filter(id => id !== cv.id)
                            setEditData({...editData, selected_cv_ids: updated})
                          }} />
                        {cv.version}
                      </label>
                    ))}
                    <span className="text-xs text-gray-400 dark:text-gray-500">(none = all)</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                  </>
                )}
                <label className="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-400">
                  Auto Scoring:
                  <select defaultValue={editModal.auto_scoring_depth || 'off'}
                    onChange={e => setEditData({...editData, auto_scoring_depth: e.target.value})}
                    className="border rounded px-1.5 py-0.5 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    <option value="off">Off</option>
                    <option value="light">Light</option>
                    <option value="full">Full</option>
                  </select>
                </label>
              </div>

              {/* Scrape URLs */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Career Page URLs</label>
                <UrlListEditor
                  urls={editData.scrape_urls_editor || urlsToEditorFormat(editModal.scrape_urls)}
                  onChange={items => setEditData({...editData, scrape_urls_editor: items})}
                />
              </div>

              {/* Title Filters */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Include Expression</label>
                  <input type="text" defaultValue={editModal.title_include_expr || ''}
                    placeholder="(Product OR Project) AND Manager"
                    onChange={e => setEditData({...editData, title_include_expr: e.target.value})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Supports AND, OR, parentheses</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Exclude Keywords</label>
                  <input type="text" defaultValue={(editModal.title_exclude_keywords || []).join(', ')}
                    placeholder="intern, junior, associate"
                    onChange={e => setEditData({...editData, title_exclude_keywords: e.target.value})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              </div>

              {/* Advanced */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Wait-for Selector</label>
                  <input type="text" defaultValue={editModal.wait_for_selector || ''}
                    placeholder="CSS selector"
                    onChange={e => setEditData({...editData, wait_for_selector: e.target.value})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Max Pages</label>
                  <input type="number" min={1} max={20} defaultValue={editModal.max_pages || 5}
                    onChange={e => setEditData({...editData, max_pages: parseInt(e.target.value) || 5})}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700 rounded-b-xl">
              <button onClick={() => setEditModal(null)}
                className="px-4 py-1.5 text-sm border dark:border-gray-600 rounded hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-600">Cancel</button>
              <button onClick={() => { saveEdit(editModal.id); setEditModal(null) }}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm table-fixed text-gray-900 dark:text-gray-200">
          <colgroup>
            <col className="w-[160px]" />
            <col className="w-[55px]" />
            <col className="w-[120px]" />
            <col />
            <col className="w-[50px]" />
            <col className="w-[180px]" />
            <col className="w-[65px]" />
            <col className="w-[95px]" />
          </colgroup>
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Company</th>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Tier</th>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">CVs</th>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Scrape URLs</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Apps</th>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">H-1B</th>
              <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Status</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <tr key={c.id} className="border-t dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-2 font-medium align-middle">
                      <span className="inline-flex items-center gap-1">
                        {c.name}
                        {(c.aliases || []).length > 0 && (
                          <span title={c.aliases.join(', ')} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 cursor-help">
                            <Tags size={12} />
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-2 align-middle">
                      {c.tier != null ? (
                        <span className={`text-xs px-2 py-0.5 rounded ${TIER_COLORS[c.tier]}`}>{c.tier}</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded bg-yellow-50 text-yellow-600 dark:bg-yellow-900 dark:text-yellow-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs align-middle">
                      {(c.selected_cv_ids || []).length > 0
                        ? cvs.filter(cv => c.selected_cv_ids.includes(cv.id)).map(cv => cv.version).join(', ') || 'Selected'
                        : <span className="text-gray-400 dark:text-gray-500">All</span>}
                    </td>
                    <td className="px-4 py-2 text-xs overflow-hidden">
                      {(c.scrape_urls || []).map((u, i) => {
                        const scrapeType = c.detected_scrape_types?.[u]
                        return (
                          <div key={i} className="flex items-center gap-1 mb-0.5 min-w-0">
                            {scrapeType && (
                              <span className={`text-[10px] px-1 py-0.5 rounded whitespace-nowrap flex-shrink-0 w-[70px] text-center ${SCRAPE_TYPE_COLORS[scrapeType] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                                {scrapeType.replace(' (Playwright)', '').replace(' API', '').replace(' AJAX', '').replace(' Careers', '')}
                              </span>
                            )}
                            <a href={u} target="_blank" rel="noopener noreferrer"
                              className="text-blue-600 dark:text-blue-400 truncate min-w-0" title={u}>
                              {u.replace(/https?:\/\//, '')}
                            </a>
                          </div>
                        )
                      })}
                      {(c.scrape_urls || []).length === 0 && <span className="text-gray-400 dark:text-gray-500">-</span>}
                      {c.title_include_expr && (
                        <span className="block text-gray-500 dark:text-gray-400 truncate mt-0.5" title={c.title_include_expr}>
                          {c.title_include_expr}
                        </span>
                      )}
                      {c.scrape_interval_minutes && (
                        <span className="text-gray-400 dark:text-gray-500 text-[10px] block mt-0.5">
                          Every {c.scrape_interval_minutes}m
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right text-xs align-middle">
                      {c.application_count > 0 ? (
                        <span className="font-medium text-purple-700 dark:text-purple-400">{c.application_count}</span>
                      ) : <span className="text-gray-400 dark:text-gray-500">0</span>}
                    </td>
                    <td className="px-4 py-2 text-xs align-middle">
                      {c.h1b_lca_count ? (
                        <span>{c.h1b_lca_count} LCAs{c.h1b_approval_rate ? `, ${c.h1b_approval_rate}%` : ''}</span>
                      ) : <span className="text-gray-400 dark:text-gray-500">-</span>}
                      {c.h1b_slug && (
                        <span className="block text-[10px] text-gray-400 dark:text-gray-500 mt-0.5" title="H-1B slug">{c.h1b_slug}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 align-middle">
                      <button onClick={() => toggleActive(c.id, c.active)}
                        className={`text-xs px-2 py-0.5 rounded ${c.active ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                        {c.active ? 'Active' : 'Paused'}
                      </button>
                      {c.auto_scoring_depth && c.auto_scoring_depth !== 'off' && (
                        <span className={`text-[10px] px-1 py-0.5 rounded ml-1 ${
                          c.auto_scoring_depth === 'full' ? 'bg-purple-50 text-purple-600 dark:bg-purple-900 dark:text-purple-300' : 'bg-blue-50 text-blue-600 dark:bg-blue-900 dark:text-blue-300'
                        }`} title={`Auto scoring: ${c.auto_scoring_depth}`}>
                          {c.auto_scoring_depth === 'full' ? 'Full' : 'Light'}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right align-middle">
                      <div className="inline-flex items-center gap-1">
                        <button onClick={() => runTestScrape(c.id)} disabled={testing === c.id}
                          className="p-1 text-amber-500 hover:text-amber-700 disabled:opacity-50" title="Test Scrape (dry run)">
                          {testing === c.id ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
                        </button>
                        <button onClick={() => runScrape(c.id)} disabled={scraping === c.id}
                          className="p-1 text-green-500 hover:text-green-700 disabled:opacity-50" title="Run Scrape">
                          {scraping === c.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        </button>
                        <button onClick={() => { setEditModal(c); setEditData({ scrape_urls_editor: urlsToEditorFormat(c.scrape_urls) }) }} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1" title="Edit">
                          <Edit2 size={14} />
                        </button>
                      </div>
                    </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
