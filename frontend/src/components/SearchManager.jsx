import React, { useState, useEffect } from 'react'
import api from '../api'
import { Plus, Play, Trash2, Edit2, Check, X, FlaskConical, ExternalLink, Loader2 } from 'lucide-react'

const SOURCES = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'indeed', label: 'Indeed' },
  { value: 'zip_recruiter', label: 'ZipRecruiter' },
  { value: 'google', label: 'Google Jobs' },
  { value: 'direct', label: 'Direct (Playwright)' },
]

const SOURCE_COLORS = {
  linkedin: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  indeed: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  zip_recruiter: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
  google: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  levels_fyi: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  linkedin_personal: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300',
  jobright: 'bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300',
}

const DEFAULT_FORM = {
  name: '', search_mode: 'keyword', search_term: '', direct_url: '',
  location: 'United States', is_remote: '', job_type: 'fulltime',
  hours_old: 24, results_wanted: 50,
  sources: ['linkedin', 'indeed', 'zip_recruiter', 'google'],
  title_include_keywords: '', title_exclude_keywords: 'intern, junior, associate',
  company_filter: '', company_exclude: '', max_pages: 50, min_fit_score: 0,
  require_salary: false, auto_scoring_depth: 'off', run_interval_minutes: 0,
}

export default function SearchManager() {
  const [searches, setSearches] = useState([])
  const [editing, setEditing] = useState(null) // null | 'new' | search_id
  const [editData, setEditData] = useState({})
  const [running, setRunning] = useState(null)
  const [testing, setTesting] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [testFilter, setTestFilter] = useState('all')

  const fetchSearches = async () => {
    try {
      const { data } = await api.get('/searches')
      setSearches(data)
    } catch (e) { console.error(e) }
  }

  useEffect(() => { fetchSearches() }, [])

  const startEdit = (s) => {
    setEditing(s.id)
    setEditData({
      name: s.name, search_mode: s.search_mode, search_term: s.search_term || '',
      direct_url: s.direct_url || '', location: s.location || 'United States',
      is_remote: s.is_remote === true ? 'true' : s.is_remote === false ? 'false' : '',
      job_type: s.job_type || 'fulltime', hours_old: s.hours_old || 24,
      results_wanted: s.results_wanted || 50, sources: s.sources || [],
      title_include_keywords: (s.title_include_keywords || []).join(', '),
      title_exclude_keywords: (s.title_exclude_keywords || []).join(', '),
      company_filter: (s.company_filter || []).join(', '),
      company_exclude: (s.company_exclude || []).join(', '),
      max_pages: s.max_pages || 50,
      min_fit_score: s.min_fit_score || 0,
      require_salary: s.require_salary || false,
      auto_scoring_depth: s.auto_scoring_depth || 'off',
      run_interval_minutes: s.run_interval_minutes || 0,
    })
  }

  const saveSearch = async () => {
    const payload = {
      ...editData,
      title_include_keywords: editData.title_include_keywords ? editData.title_include_keywords.split(',').map(s => s.trim()).filter(Boolean) : [],
      title_exclude_keywords: editData.title_exclude_keywords ? editData.title_exclude_keywords.split(',').map(s => s.trim()).filter(Boolean) : [],
      company_filter: editData.company_filter ? editData.company_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
      company_exclude: editData.company_exclude ? editData.company_exclude.split(',').map(s => s.trim()).filter(Boolean) : [],
      max_pages: parseInt(editData.max_pages) || 50,
      min_fit_score: parseInt(editData.min_fit_score) || 0,
      require_salary: editData.require_salary || false,
      auto_scoring_depth: editData.auto_scoring_depth || 'off',
      is_remote: editData.is_remote === 'true' ? true : editData.is_remote === 'false' ? false : null,
    }
    try {
      if (editing === 'new') {
        await api.post('/searches', payload)
      } else {
        await api.patch(`/searches/${editing}`, payload)
      }
      setEditing(null)
      setEditData({})
      fetchSearches()
    } catch (e) { console.error(e) }
  }

  const deleteSearch = async (id) => {
    if (!confirm('Delete this search config?')) return
    try {
      await api.delete(`/searches/${id}`)
      fetchSearches()
    } catch (e) { console.error(e) }
  }

  const toggleActive = async (id, active) => {
    try {
      await api.patch(`/searches/${id}`, { active: !active })
      fetchSearches()
    } catch (e) { console.error(e) }
  }

  const runSearch = async (id) => {
    setRunning(id)
    try {
      await api.post(`/searches/${id}/run`)
      fetchSearches()
    } catch (e) { console.error(e) }
    setRunning(null)
  }

  const testSearch = async (id) => {
    setTesting(id)
    setTestResult(null)
    setTestFilter('all')
    try {
      const { data, status } = await api.post(`/searches/${id}/test`, null, { timeout: 30000 })
      if (status === 202 && data.run_id) {
        // Async mode — poll for results
        const runId = data.run_id
        while (true) {
          await new Promise(r => setTimeout(r, 3000))
          try {
            const poll = await api.get(`/searches/test-result/${runId}`, { timeout: 10000 })
            if (poll.status === 200) {
              setTestResult(poll.data)
              break
            }
            // 202 = still running, continue polling
          } catch (pollErr) {
            if (pollErr.response?.status === 404) {
              setTestResult({ error: 'Test run expired or not found' })
              break
            }
            // Network error during poll — keep trying
          }
        }
      } else {
        // Sync mode (keyword) — result returned directly
        setTestResult(data)
      }
    } catch (e) {
      setTestResult({ error: e.response?.data?.detail || e.message })
    }
    setTesting(null)
  }

  const getFilteredJobs = () => {
    if (!testResult?.jobs) return []
    if (testFilter === 'kept') return testResult.jobs.filter(j => j.kept)
    if (testFilter === 'filtered') return testResult.jobs.filter(j => !j.kept)
    return testResult.jobs
  }

  const ed = editData
  const setEd = (patch) => setEditData(prev => ({ ...prev, ...patch }))

  // Inline edit form rendered inside each card
  const renderEditFields = () => (
    <div className="mt-3 pt-3 border-t dark:border-gray-600">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Name</label>
          <input type="text" value={ed.name} onChange={e => setEd({ name: e.target.value })}
            placeholder="e.g. TPM roles — Tier 1" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Mode</label>
          {ed.search_mode === 'linkedin_extension' ? (
            <input type="text" value="LinkedIn Extension" disabled
              className="border rounded px-2 py-1.5 text-sm w-full bg-gray-100 text-gray-500 dark:bg-gray-600 dark:text-gray-400 dark:border-gray-600" />
          ) : (
            <select value={ed.search_mode} onChange={e => {
                const mode = e.target.value
                const patch = { search_mode: mode }
                if (mode === 'linkedin_personal') patch.sources = ['recommended', 'top-applicant']
                else if (mode === 'jobright') patch.sources = ['recommended']
                else if (mode === 'keyword') patch.sources = ['linkedin', 'indeed', 'zip_recruiter', 'google']
                setEd(patch)
              }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="keyword">Keyword (JobSpy)</option>
              <option value="url">URL (Playwright)</option>
              <option value="levels_fyi">Levels.fyi</option>
              <option value="linkedin_personal">LinkedIn Personal</option>
              <option value="jobright">Jobright.ai</option>
            </select>
          )}
        </div>
        {ed.search_mode === 'linkedin_extension' ? (
          <div className="col-span-2">
            <div className="p-2 bg-green-50 dark:bg-green-900/30 rounded text-xs text-green-700 dark:text-green-300">
              Jobs are imported via the Chrome Extension. Configure title/company filters below to auto-filter during import.
            </div>
          </div>
        ) : ed.search_mode === 'linkedin_personal' ? (
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Collections</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={(ed.sources || []).includes('recommended')}
                  onChange={e => {
                    const s = ed.sources || []
                    setEd({ sources: e.target.checked ? [...s.filter(x => x !== 'recommended'), 'recommended'] : s.filter(x => x !== 'recommended') })
                  }} />
                Recommended
              </label>
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={(ed.sources || []).includes('top-applicant')}
                  onChange={e => {
                    const s = ed.sources || []
                    setEd({ sources: e.target.checked ? [...s.filter(x => x !== 'top-applicant'), 'top-applicant'] : s.filter(x => x !== 'top-applicant') })
                  }} />
                Top Applicant
              </label>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Configure credentials in Settings.</p>
          </div>
        ) : ed.search_mode === 'jobright' ? (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Search Term (optional)</label>
              <input type="text" value={ed.search_term} onChange={e => setEd({ search_term: e.target.value })}
                placeholder="Leave empty for AI recommendations" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Results Wanted</label>
              <input type="number" value={ed.results_wanted} onChange={e => setEd({ results_wanted: parseInt(e.target.value) || 100 })}
                min={20} max={500} className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Min Score</label>
              <input type="number" value={ed.min_fit_score || 0} onChange={e => setEd({ min_fit_score: parseInt(e.target.value) || 0 })}
                min={0} max={100} placeholder="0 = no filter" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div className="flex items-center pt-5">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={ed.require_salary || false}
                  onChange={e => setEd({ require_salary: e.target.checked })} />
                Require salary
              </label>
            </div>
          </>
        ) : ed.search_mode === 'keyword' ? (
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Search Term</label>
            <input type="text" value={ed.search_term} onChange={e => setEd({ search_term: e.target.value })}
              placeholder="e.g. technical program manager" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        ) : (
          <div className={ed.search_mode === 'levels_fyi' ? 'col-span-2' : ''}>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              {ed.search_mode === 'levels_fyi' ? 'Levels.fyi URL (with filters applied)' : 'Direct URL'}
            </label>
            <input type="text" value={ed.direct_url} onChange={e => setEd({ direct_url: e.target.value })}
              placeholder={ed.search_mode === 'levels_fyi'
                ? 'https://www.levels.fyi/jobs/location/united-states?jobFamilySlugs=...'
                : 'https://linkedin.com/jobs/...'}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        )}
        {ed.search_mode === 'levels_fyi' && (
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Max Pages</label>
            <input type="number" value={ed.max_pages} onChange={e => setEd({ max_pages: parseInt(e.target.value) || 50 })}
              min={1} max={100} className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        )}
        {ed.search_mode !== 'levels_fyi' && ed.search_mode !== 'linkedin_personal' && ed.search_mode !== 'jobright' && ed.search_mode !== 'linkedin_extension' && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Location</label>
              <input type="text" value={ed.location} onChange={e => setEd({ location: e.target.value })}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Remote</label>
              <select value={ed.is_remote} onChange={e => setEd({ is_remote: e.target.value })}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="">Any</option>
                <option value="true">Remote Only</option>
                <option value="false">On-site Only</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Job Type</label>
              <select value={ed.job_type} onChange={e => setEd({ job_type: e.target.value })}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="fulltime">Full-time</option>
                <option value="parttime">Part-time</option>
                <option value="contract">Contract</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Hours Old</label>
              <input type="number" value={ed.hours_old} onChange={e => setEd({ hours_old: parseInt(e.target.value) || 24 })}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Results Wanted</label>
              <input type="number" value={ed.results_wanted} onChange={e => setEd({ results_wanted: parseInt(e.target.value) || 50 })}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            </div>
          </>
        )}
      </div>

      {ed.search_mode === 'keyword' && (
        <div className="mt-3">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Sources</label>
          <div className="flex gap-3">
            {SOURCES.map(s => (
              <label key={s.value} className="flex items-center gap-1 text-xs">
                <input type="checkbox" checked={(ed.sources || []).includes(s.value)}
                  onChange={e => {
                    const newSources = e.target.checked
                      ? [...(ed.sources || []), s.value]
                      : (ed.sources || []).filter(x => x !== s.value)
                    setEd({ sources: newSources })
                  }} />
                {s.label}
              </label>
            ))}
          </div>
        </div>
      )}

      {ed.search_mode === 'levels_fyi' && (
        <div className="mt-3">
          <div className="p-2 bg-emerald-50 dark:bg-emerald-900/30 rounded text-xs text-emerald-700 dark:text-emerald-300">
            Configure filters on levels.fyi, then paste the URL here. Filters (location, job family, salary, recency) are encoded in the URL.
          </div>
        </div>
      )}

      {ed.search_mode === 'jobright' && (
        <div className="mt-3">
          <div className="p-2 bg-teal-50 dark:bg-teal-900/30 rounded text-xs text-teal-700 dark:text-teal-300">
            Configure credentials in Settings. Uses personalized AI recommendations from Jobright.ai. Leave search term empty for recommendations, or enter a keyword for search mode.
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mt-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Include Keywords (comma-separated)</label>
          <input type="text" value={ed.title_include_keywords}
            onChange={e => setEd({ title_include_keywords: e.target.value })}
            placeholder="program manager, TPM" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Exclude Keywords (comma-separated)</label>
          <input type="text" value={ed.title_exclude_keywords}
            onChange={e => setEd({ title_exclude_keywords: e.target.value })}
            placeholder="intern, junior, associate" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Company Include (comma-separated, exact match)</label>
          <input type="text" value={ed.company_filter}
            onChange={e => setEd({ company_filter: e.target.value })}
            placeholder="Google, Microsoft" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Company Exclude (comma-separated, exact match)</label>
          <input type="text" value={ed.company_exclude}
            onChange={e => setEd({ company_exclude: e.target.value })}
            placeholder="Walmart, CommScope" className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-4">
        <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
          Auto Scoring:
          <select value={ed.auto_scoring_depth || 'off'}
            onChange={e => setEd({ auto_scoring_depth: e.target.value })}
            className="border rounded px-1.5 py-0.5 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
            <option value="off">Off</option>
            <option value="light">Light</option>
            <option value="full">Full</option>
          </select>
        </label>
        {ed.search_mode !== 'linkedin_extension' && (
          <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
            Run interval (min):
            <input type="number" min={0} value={ed.run_interval_minutes || 0}
              onChange={e => setEd({ run_interval_minutes: parseInt(e.target.value) || 0 })}
              className="border rounded px-1.5 py-0.5 text-xs w-16 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            <span className="text-gray-400 dark:text-gray-500">(0 = global)</span>
          </label>
        )}
      </div>
    </div>
  )

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Search Manager</h1>
        <button onClick={() => { setEditing('new'); setEditData({ ...DEFAULT_FORM }) }}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-navy text-white rounded-lg hover:bg-navy-hover">
          <Plus size={14} /> New Search
        </button>
      </div>

      {/* Test Results Modal */}
      {testResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setTestResult(null)}>
          <div className="bg-card dark:bg-card-dark rounded-xl shadow-2xl w-[950px] max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border dark:border-border-dark flex-shrink-0">
              <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                Test Search {testResult.error ? '— Error' : `— ${testResult.search_name}`}
              </h2>
              <button onClick={() => setTestResult(null)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1"><X size={18} /></button>
            </div>

            {testResult.error ? (
              <div className="p-5 text-red-600 text-sm">{testResult.error}</div>
            ) : (
              <div className="overflow-y-auto flex-1">
                {/* Config info */}
                <div className="text-xs text-gray-500 dark:text-gray-400 px-5 py-2 border-b border-border dark:border-border-dark space-y-0.5 bg-gray-50 dark:bg-gray-700">
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {testResult.config?.mode === 'jobright' ? (
                      <>
                        <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300 font-medium">Jobright.ai</span>
                        {testResult.config?.search_term ? (
                          <span>Search: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">"{testResult.config.search_term}"</code></span>
                        ) : (
                          <span>Mode: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">AI Recommendations</code></span>
                        )}
                        <span>Wanted: {testResult.config?.results_wanted}</span>
                      </>
                    ) : testResult.config?.mode === 'linkedin_personal' ? (
                      <>
                        <span className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300 font-medium">LinkedIn Personal</span>
                        <span>Collections: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">{(testResult.config?.collections || []).join(', ')}</code></span>
                      </>
                    ) : testResult.config?.mode === 'levels_fyi' ? (
                      <>
                        <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300 font-medium">Levels.fyi</span>
                        <span className="truncate max-w-[500px]" title={testResult.config?.url}>URL: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">{testResult.config?.url}</code></span>
                      </>
                    ) : (
                      <>
                        <span>Term: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">"{testResult.config?.search_term}"</code></span>
                        <span>Location: <code className="bg-gray-100 dark:bg-gray-600 px-1 rounded">{testResult.config?.location}</code></span>
                        <span>Sources: {(testResult.config?.sources || []).join(', ')}</span>
                        <span>Hours: {testResult.config?.hours_old}h</span>
                        <span>Wanted: {testResult.config?.results_wanted}</span>
                        {testResult.config?.is_remote !== null && <span>Remote: {String(testResult.config?.is_remote)}</span>}
                        {testResult.config?.proxy && <span className="text-amber-600">Proxy: on</span>}
                      </>
                    )}
                  </div>
                  {testResult.include_keywords?.length > 0 && (
                    <p>Include: <code className="bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-300 px-1 rounded">{testResult.include_keywords.join(', ')}</code></p>
                  )}
                  {testResult.exclude_keywords?.length > 0 && (
                    <p>Exclude: <code className="bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-300 px-1 rounded">{testResult.exclude_keywords.join(', ')}</code></p>
                  )}
                  {testResult.company_filter?.length > 0 && (
                    <p>Company filter: <code className="bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 px-1 rounded">{testResult.company_filter.join(', ')}</code></p>
                  )}
                  {testResult.company_exclude?.length > 0 && (
                    <p>Company exclude: <code className="bg-orange-50 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300 px-1 rounded">{testResult.company_exclude.join(', ')}</code></p>
                  )}
                </div>

                {/* Source & Company breakdowns */}
                {(Object.keys(testResult.source_breakdown || {}).length > 0 || Object.keys(testResult.company_breakdown || {}).length > 0) && (
                  <div className="px-5 py-2 border-b border-border dark:border-border-dark bg-blue-50/50 dark:bg-gray-700/50 flex gap-8 text-xs">
                    {Object.keys(testResult.source_breakdown || {}).length > 0 && (
                      <div>
                        <span className="font-medium text-gray-600 dark:text-gray-400">By source: </span>
                        {Object.entries(testResult.source_breakdown).map(([source, count]) => (
                          <span key={source} className={`inline-block px-1.5 py-0.5 rounded mr-1 ${SOURCE_COLORS[source] || 'bg-gray-100 text-gray-600'}`}>
                            {source} ({count})
                          </span>
                        ))}
                      </div>
                    )}
                    {Object.keys(testResult.company_breakdown || {}).length > 0 && (
                      <details className="flex-1">
                        <summary className="font-medium text-gray-600 dark:text-gray-400 cursor-pointer">
                          Top companies ({Object.keys(testResult.company_breakdown).length})
                        </summary>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {Object.entries(testResult.company_breakdown).map(([company, count]) => (
                            <span key={company} className="bg-white dark:bg-gray-700 border dark:border-gray-600 px-1.5 py-0.5 rounded">
                              {company} ({count})
                            </span>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {/* Filter tabs */}
                <div className="px-5 py-2 border-b border-border dark:border-border-dark flex items-center gap-2 bg-card dark:bg-card-dark">
                  {['all', 'kept', 'filtered'].map(f => (
                    <button key={f} onClick={() => setTestFilter(f)}
                      className={`px-2.5 py-1 text-xs rounded ${testFilter === f ? 'bg-navy text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}`}>
                      {f === 'all' && `All (${testResult.jobs?.length || 0})`}
                      {f === 'kept' && `Kept (${testResult.after_filter || 0})`}
                      {f === 'filtered' && `Filtered (${(testResult.raw_count || 0) - (testResult.after_filter || 0)})`}
                    </button>
                  ))}
                </div>

                {/* Results table */}
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-700 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-8">#</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-20">Source</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400">Company</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400">Title</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-28">Location</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-24">Salary</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-12">Desc</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-16">Status</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-400 w-10">Link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getFilteredJobs().map((j, i) => (
                      <tr key={i} className={`border-t dark:border-gray-700 ${j.kept ? 'hover:bg-gray-50 dark:hover:bg-gray-700' : 'bg-red-50/50 dark:bg-red-900/30'}`}>
                        <td className="px-3 py-1.5 text-xs text-gray-400 dark:text-gray-500">{i + 1}</td>
                        <td className="px-3 py-1.5">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${SOURCE_COLORS[j.source] || 'bg-gray-100 text-gray-600'}`}>
                            {j.source}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 max-w-[120px] truncate" title={j.company}>{j.company}</td>
                        <td className={`px-3 py-1.5 text-xs ${j.kept ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 line-through'}`} title={j.title}>
                          <span className="block max-w-[250px] truncate">{j.title}</span>
                        </td>
                        <td className="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 max-w-[120px] truncate" title={j.location}>{j.location}</td>
                        <td className="px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400">{j.salary || ''}</td>
                        <td className="px-3 py-1.5 text-center">
                          {j.has_description ? (
                            <span className="text-xs text-green-600" title={`${j.desc_length} chars`}>Y</span>
                          ) : (
                            <span className="text-xs text-red-400">N</span>
                          )}
                        </td>
                        <td className="px-3 py-1.5">
                          {j.kept ? (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">Kept</span>
                          ) : (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300" title={j.reason}>Out</span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 text-right">
                          {j.url && (
                            <a href={j.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-700">
                              <ExternalLink size={14} />
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(testResult.jobs || []).length === 0 && (
                  <p className="text-center py-8 text-gray-400 dark:text-gray-500">No results returned.</p>
                )}
              </div>
            )}

            {/* Footer */}
            <div className="px-5 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700 flex justify-between items-center rounded-b-xl">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {!testResult.error && (
                  <>
                    <span className="font-medium text-green-700">{testResult.after_filter}</span>
                    <span> kept / </span>
                    <span className="font-medium text-red-600">{(testResult.raw_count || 0) - (testResult.after_filter || 0)}</span>
                    <span> filtered / </span>
                    <span className="font-medium">{testResult.raw_count}</span>
                    <span> raw</span>
                    <span className="ml-3 text-gray-400 dark:text-gray-500">({testResult.duration}s)</span>
                  </>
                )}
              </span>
              <button onClick={() => setTestResult(null)} className="px-4 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-500">Close</button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {/* New search card (inline at top) */}
        {editing === 'new' && (
          <div className="bg-card dark:bg-card-dark border-2 border-blue-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900 dark:text-gray-100">New Search Config</h3>
              <div className="flex items-center gap-1">
                <button onClick={saveSearch} className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 p-1" title="Save">
                  <Check size={16} />
                </button>
                <button onClick={() => { setEditing(null); setEditData({}) }} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1" title="Cancel">
                  <X size={16} />
                </button>
              </div>
            </div>
            {renderEditFields()}
          </div>
        )}

        {searches.length === 0 && editing !== 'new' ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">No search configs yet. Click "New Search" to create one.</div>
        ) : searches.map(s => (
          <div key={s.id} className={`bg-card dark:bg-card-dark border border-border dark:border-border-dark rounded-lg p-4 ${editing === s.id ? 'border-blue-200 border-2' : ''}`}>
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100">{s.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    s.search_mode === 'levels_fyi' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' :
                    s.search_mode === 'linkedin_personal' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300' :
                    s.search_mode === 'linkedin_extension' ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300' :
                    s.search_mode === 'jobright' ? 'bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300' :
                    s.search_mode === 'url' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}>{s.search_mode === 'levels_fyi' ? 'Levels.fyi' : s.search_mode === 'linkedin_personal' ? 'LinkedIn Personal' : s.search_mode === 'linkedin_extension' ? 'Extension' : s.search_mode === 'jobright' ? 'Jobright.ai' : s.search_mode === 'keyword' ? 'JobSpy' : s.search_mode}</span>
                </div>
                {editing !== s.id && (
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {s.search_term && <span>Term: "{s.search_term}"</span>}
                    {s.search_mode === 'levels_fyi' && s.direct_url && (
                      <span className="truncate max-w-[400px]" title={s.direct_url}>URL: {s.direct_url}</span>
                    )}
                    {s.search_mode === 'url' && s.direct_url && <span>URL mode</span>}
                    {s.search_mode === 'linkedin_personal' && <span>Collections: {(s.sources || ['recommended', 'top-applicant']).join(', ')}</span>}
                    {s.search_mode === 'jobright' && <span>{s.search_term ? `Search: "${s.search_term}"` : 'AI Recommendations'} (max {s.results_wanted || 100})</span>}
                    {s.search_mode === 'keyword' && <span>{s.location}</span>}
                    {s.search_mode === 'keyword' && <span>Sources: {(s.sources || []).join(', ')}</span>}
                    {s.last_run_at && <span>Last run: {new Date(s.last_run_at).toLocaleString()}</span>}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                {editing === s.id ? (
                  <>
                    <button onClick={saveSearch} className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 p-1" title="Save">
                      <Check size={16} />
                    </button>
                    <button onClick={() => { setEditing(null); setEditData({}) }} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1" title="Cancel">
                      <X size={16} />
                    </button>
                  </>
                ) : (
                  <>
                    <button onClick={() => toggleActive(s.id, s.active)}
                      className={`text-xs px-2 py-0.5 rounded ${s.active ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                      {s.active ? 'Active' : 'Paused'}
                    </button>
                    {s.auto_scoring_depth && s.auto_scoring_depth !== 'off' && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        s.auto_scoring_depth === 'full' ? 'bg-purple-50 text-purple-600 dark:bg-purple-900 dark:text-purple-300' : 'bg-blue-50 text-blue-600 dark:bg-blue-900 dark:text-blue-300'
                      }`} title={`Auto scoring: ${s.auto_scoring_depth}`}>
                        {s.auto_scoring_depth === 'full' ? 'Full' : 'Light'}
                      </span>
                    )}
                    {s.search_mode !== 'linkedin_extension' && (
                      <button onClick={() => testSearch(s.id)} disabled={testing === s.id || !['keyword', 'levels_fyi', 'linkedin_personal', 'jobright'].includes(s.search_mode)}
                        className="p-1.5 rounded hover:bg-amber-50 dark:hover:bg-amber-900/30 text-amber-600 dark:text-amber-400 disabled:opacity-40" title="Test Search (dry run)">
                        {testing === s.id ? <Loader2 size={16} className="animate-spin" /> : <FlaskConical size={16} />}
                      </button>
                    )}
                    {s.search_mode !== 'linkedin_extension' && (
                      <button onClick={() => runSearch(s.id)} disabled={running === s.id}
                        className="p-1.5 rounded hover:bg-green-50 dark:hover:bg-green-900/30 text-green-600 dark:text-green-400" title="Run Now">
                        {running === s.id ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                      </button>
                    )}
                    <button onClick={() => startEdit(s)} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 dark:text-gray-500" title="Edit">
                      <Edit2 size={16} />
                    </button>
                    {s.search_mode !== 'linkedin_extension' && (
                      <button onClick={() => deleteSearch(s.id)} className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-400" title="Delete">
                        <Trash2 size={16} />
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
            {editing === s.id && renderEditFields()}
          </div>
        ))}
      </div>
    </div>
  )
}
