import React, { useState, useEffect, useRef } from 'react'
import api from '../api'
import { Upload, Download, RefreshCw, Send, Play, Trash2, Plus, Info, Eye, EyeOff } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState({})
  const [cvs, setCvs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [triggerStatus, setTriggerStatus] = useState({})
  const [newCvName, setNewCvName] = useState('')
  const [showAddCv, setShowAddCv] = useState(false)
  const [showPw, setShowPw] = useState({})
  const [activeTab, setActiveTab] = useState(() => localStorage.getItem('settings_tab') || 'general')
  const switchTab = (tab) => { setActiveTab(tab); localStorage.setItem('settings_tab', tab) }
  const togglePw = (key) => setShowPw(p => ({...p, [key]: !p[key]}))
  const fileRef = useRef()

  const fetchAll = async () => {
    try {
      const { data: settingsData } = await api.get('/settings')
      setSettings(settingsData)

      const { data: cvData } = await api.get('/cvs')
      setCvs(cvData)
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { fetchAll() }, [])

  const saveSetting = async (key, value) => {
    setSaving(true)
    try {
      await api.patch('/settings', { [key]: value })
      setSettings({ ...settings, [key]: value })
      setMessage('Setting saved')
      setTimeout(() => setMessage(''), 2000)
    } catch (e) { console.error(e) }
    setSaving(false)
  }

  const saveApiKey = async () => {
    const key = settings.dashboard_api_key
    localStorage.setItem('jobnavigator_api_key', key)
    await saveSetting('dashboard_api_key', key)
  }

  const uploadCV = async (version) => {
    const file = fileRef.current?.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      await api.post(`/cvs/${encodeURIComponent(version)}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setMessage(`${version} CV uploaded`)
      setTimeout(() => setMessage(''), 3000)
      fetchAll()
    } catch (e) {
      setMessage(`Upload failed: ${e.response?.data?.detail || e.message}`)
    }
    fileRef.current.value = ''
  }

  const deleteCV = async (version) => {
    if (!confirm(`Delete CV "${version}"?`)) return
    try {
      await api.delete(`/cvs/${encodeURIComponent(version)}`)
      setMessage(`${version} CV deleted`)
      setTimeout(() => setMessage(''), 3000)
      fetchAll()
    } catch (e) {
      setMessage(`Delete failed: ${e.response?.data?.detail || e.message}`)
    }
  }

  const handleAddCv = () => {
    if (!newCvName.trim()) return
    // Trigger file picker, then upload with the name
    fileRef.current._pendingVersion = newCvName.trim()
    fileRef.current.click()
  }

  const handleFileChange = () => {
    const version = fileRef.current._pendingVersion
    if (version) {
      uploadCV(version)
      fileRef.current._pendingVersion = null
      setShowAddCv(false)
      setNewCvName('')
    }
  }

  const triggerAction = async (endpoint, label) => {
    setTriggerStatus({ ...triggerStatus, [endpoint]: 'running' })
    try {
      await api.post(endpoint)
      setTriggerStatus({ ...triggerStatus, [endpoint]: 'done' })
      setTimeout(() => setTriggerStatus(prev => ({ ...prev, [endpoint]: '' })), 3000)
    } catch (e) {
      setTriggerStatus({ ...triggerStatus, [endpoint]: 'error' })
    }
  }

  const updatePhrases = (key, value) => {
    try {
      const arr = typeof value === 'string' ? value.split('\n').map(s => s.trim()).filter(Boolean) : value
      saveSetting(key, arr)
    } catch (e) { console.error(e) }
  }

  if (loading) return <div className="p-6 text-center text-gray-500 dark:text-gray-400">Loading settings...</div>

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Settings</h1>
      {message && (
        <div className="fixed top-4 right-8 z-50 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm">
          {message}
        </div>
      )}

      {/* Hidden file input shared across CV operations */}
      <input type="file" accept=".pdf" ref={fileRef} className="hidden" onChange={handleFileChange} />

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b dark:border-gray-700">
        {[
          { id: 'general', label: 'General' },
          { id: 'ai', label: 'AI' },
          { id: 'accounts', label: 'Accounts' },
        ].map(tab => (
          <button key={tab.id} onClick={() => switchTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.id
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'general' && (<>
      {/* CV Upload Section */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-lg dark:text-gray-100">Resume Management</h2>
            <div className="relative group">
              <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
              <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
                <p className="font-semibold mb-1.5">Resume Management (Scoring Only)</p>
                <p className="mb-1">These resumes are used <b>only for AI scoring</b> — text is extracted from uploaded PDFs and sent to the LLM to rate job fit. Up to 9 resumes.</p>
                <p className="mb-1">For building and generating actual resume PDFs, use the <b>Resumes</b> page instead.</p>
                <p>Set a <b>default resume</b> to auto-select it in scoring modals. Companies can override with specific resumes.</p>
              </div>
            </div>
          </div>
          <span className="text-xs text-gray-400 dark:text-gray-500">{cvs.length}/9 Resumes</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {cvs.map(cv => (
            <div key={cv.id} className="border dark:border-gray-600 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium text-sm dark:text-gray-200">{cv.version}</h3>
                <button onClick={() => deleteCV(cv.version)} className="text-red-400 hover:text-red-600 p-0.5" title="Delete">
                  <Trash2 size={12} />
                </button>
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                <p>{cv.filename}</p>
                <p>{cv.page_count} pages | {cv.uploaded_at ? new Date(cv.uploaded_at).toLocaleDateString() : 'N/A'}</p>
                <p className="mt-1 text-gray-400 dark:text-gray-500 truncate">{cv.extracted_text_preview?.substring(0, 100)}...</p>
                <a href={`/api/cvs/${encodeURIComponent(cv.version)}/download`}
                  className="text-blue-600 hover:underline flex items-center gap-1 mt-1">
                  <Download size={12} /> Download PDF
                </a>
              </div>
              <button onClick={() => {
                fileRef.current._pendingVersion = cv.version
                fileRef.current.click()
              }}
                className="flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700">
                <Upload size={12} /> Replace PDF
              </button>
            </div>
          ))}
        </div>

        {/* Add new CV */}
        {cvs.length < 5 && (
          <div className="mt-4">
            {showAddCv ? (
              <div className="flex items-center gap-2">
                <input type="text" placeholder="CV name (e.g. TPM, Frontend)" value={newCvName}
                  onChange={e => setNewCvName(e.target.value)} maxLength={50}
                  className="border rounded px-2 py-1.5 text-sm flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                <button onClick={handleAddCv} disabled={!newCvName.trim()}
                  className="flex items-center gap-1 text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 disabled:opacity-50">
                  <Upload size={12} /> Upload PDF
                </button>
                <button onClick={() => { setShowAddCv(false); setNewCvName('') }}
                  className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 px-2 py-1.5">Cancel</button>
              </div>
            ) : (
              <button onClick={() => setShowAddCv(true)}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
                <Plus size={12} /> Add CV
              </button>
            )}
          </div>
        )}

        {/* Default CV */}
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Default CV (used when company or search has no CVs configured)</label>
          <select value={settings.default_cv_id || ''}
            onChange={e => saveSetting('default_cv_id', e.target.value)}
            className="border rounded px-2 py-1.5 text-sm w-full max-w-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
            <option value="">None (score against all)</option>
            {cvs.map(cv => (
              <option key={cv.id} value={cv.id}>{cv.version}</option>
            ))}
          </select>
        </div>
      </section>

      {/* Scheduler Settings */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Scheduler</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Scheduler</p>
              <p className="mb-1"><b>Intervals</b>: scrape and email run every N minutes. 0 = disabled.</p>
              <p className="mb-1"><b>Cron</b>: 5-field cron expression (min hour day month dow). E.g. <code>0 3 * * *</code> = daily 3am, <code>0 2 * * 0</code> = Sundays 2am. Empty = disabled.</p>
              <p><b>Thresholds</b>: how old (in days) skipped jobs or stale applications must be before cleanup/reject acts on them.</p>
            </div>
          </div>
        </div>
        {/* Interval-based */}
        <label className="block text-[10px] font-semibold text-gray-500 dark:text-gray-500 uppercase tracking-wider mb-2">Intervals &amp; Thresholds (0 = disabled)</label>
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Scrape All (min)</label>
            <input type="number" value={settings.scrape_interval_minutes ?? 0}
              onChange={e => setSettings({...settings, scrape_interval_minutes: e.target.value})}
              onBlur={e => saveSetting('scrape_interval_minutes', parseInt(e.target.value) || 0)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Email Check (min)</label>
            <input type="number" value={settings.email_check_interval_minutes ?? 0}
              onChange={e => setSettings({...settings, email_check_interval_minutes: e.target.value})}
              onBlur={e => saveSetting('email_check_interval_minutes', parseInt(e.target.value) || 0)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Cleanup Threshold (days)</label>
            <input type="number" value={settings.job_archive_after_days ?? 0}
              onChange={e => setSettings({...settings, job_archive_after_days: e.target.value})}
              onBlur={e => saveSetting('job_archive_after_days', parseInt(e.target.value) || 0)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Auto-Reject Threshold (days)</label>
            <input type="number" value={settings.auto_reject_after_days ?? 0}
              onChange={e => setSettings({...settings, auto_reject_after_days: e.target.value})}
              onBlur={e => saveSetting('auto_reject_after_days', parseInt(e.target.value) || 0)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        </div>
        {/* Cron-based */}
        <label className="block text-[10px] font-semibold text-gray-500 dark:text-gray-500 uppercase tracking-wider mb-2">Cron Schedules (empty = disabled, format: min hour day month dow)</label>
        <div className="grid grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">DB Backup</label>
            <input type="text" value={settings.backup_cron ?? ''}
              onChange={e => setSettings({...settings, backup_cron: e.target.value})}
              onBlur={e => saveSetting('backup_cron', e.target.value)}
              placeholder="0 3 * * *"
              className="border rounded px-2 py-1.5 text-sm w-full font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Telegram Digest</label>
            <input type="text" value={settings.digest_cron ?? ''}
              onChange={e => setSettings({...settings, digest_cron: e.target.value})}
              onBlur={e => saveSetting('digest_cron', e.target.value)}
              placeholder="0 8 * * *"
              className="border rounded px-2 py-1.5 text-sm w-full font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">H-1B Refresh</label>
            <input type="text" value={settings.h1b_cron ?? ''}
              onChange={e => setSettings({...settings, h1b_cron: e.target.value})}
              onBlur={e => saveSetting('h1b_cron', e.target.value)}
              placeholder="0 2 * * 0"
              className="border rounded px-2 py-1.5 text-sm w-full font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Job Cleanup</label>
            <input type="text" value={settings.cleanup_cron ?? ''}
              onChange={e => setSettings({...settings, cleanup_cron: e.target.value})}
              onBlur={e => saveSetting('cleanup_cron', e.target.value)}
              placeholder="0 4 * * *"
              className="border rounded px-2 py-1.5 text-sm w-full font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Auto-Reject</label>
            <input type="text" value={settings.reject_cron ?? ''}
              onChange={e => setSettings({...settings, reject_cron: e.target.value})}
              onBlur={e => saveSetting('reject_cron', e.target.value)}
              placeholder="0 4 * * *"
              className="border rounded px-2 py-1.5 text-sm w-full font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        </div>
      </section>
      </>)}

      {activeTab === 'ai' && (<>
      {/* AI Scoring Configuration */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">CV AI Scoring Configuration</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">How scoring works</p>
              <p className="mb-1.5"><b>Primary LLM</b> — provider + model used for all CV scoring. Claude API uses the API key from settings (or ANTHROPIC_API_KEY env var as fallback). Claude Code uses your subscription via OAuth. OpenAI/Ollama/OpenAI-compat use their respective keys.</p>
              <p className="mb-1.5"><b>Fallback LLM</b> — if the primary fails (rate limit, error, timeout), scoring automatically retries with this provider. Each has its own API key. Leave provider as "None" to disable.</p>
              <p className="mb-1.5"><b>Add Custom Model</b> — models added here appear in both Primary and Fallback dropdowns for the selected provider.</p>
              <p className="mb-1.5"><b>Scoring Depth</b> — <i>Light</i>: scores only (fast, 600 tokens). <i>Full</i>: scores + keyword analysis + requirement mapping + report (2000 tokens).</p>
              <p className="mb-1.5"><b>On Save Action</b> — what happens when you save a job. Only runs if the job has no existing scores.</p>
              <p><b>Rubric &amp; Output Schemas</b> — editable prompts sent to the LLM. CV_NAMES_HERE is replaced with actual CV names at runtime.</p>
            </div>
          </div>
        </div>
        {/* Primary LLM */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const provider = settings.llm_provider || 'claude_api'
          const filtered = models.filter(m => m.provider === provider)
          const currentModel = settings.llm_model || ''
          const currentInList = filtered.some(m => m.model === currentModel)
          return (
            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Primary LLM</label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Provider</label>
                  <select value={provider}
                    onChange={e => { setSettings(p => ({...p, llm_provider: e.target.value})); saveSetting('llm_provider', e.target.value) }}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    <option value="claude_api">Claude API (Anthropic)</option>
                    <option value="claude_code">Claude Code (Subscription)</option>
                    <option value="openai">OpenAI</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai_compat">OpenAI Compatible (OpenRouter, etc.)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Model</label>
                  <select value={currentModel}
                    onChange={e => { setSettings(p => ({...p, llm_model: e.target.value})); saveSetting('llm_model', e.target.value) }}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                    {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                  </select>
                </div>
              </div>
              {!['claude_code', 'ollama'].includes(provider) && (
                <div className="mt-2">
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">API Key</label>
                  <div className="relative">
                    <input type={showPw.llm_api_key ? 'text' : 'password'} autoComplete="off" value={settings.llm_api_key || ''}
                      onChange={e => setSettings(p => ({...p, llm_api_key: e.target.value}))}
                      onBlur={e => saveSetting('llm_api_key', e.target.value)}
                      className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                    <button type="button" onClick={() => togglePw('llm_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                      {showPw.llm_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>
              )}
              {provider === 'openai_compat' && (
                <div className="mt-2">
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Base URL</label>
                  <input type="text" autoComplete="off" value={settings.llm_base_url || ''}
                    onChange={e => setSettings(p => ({...p, llm_base_url: e.target.value}))}
                    onBlur={e => saveSetting('llm_base_url', e.target.value)}
                    placeholder="https://openrouter.ai/api/v1"
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              )}
            </div>
          )
        })()}
        {/* Fallback LLM */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const provider = settings.llm_fallback_provider || ''
          const filtered = models.filter(m => m.provider === provider)
          const currentModel = settings.llm_fallback_model || ''
          const currentInList = filtered.some(m => m.model === currentModel)
          return (
            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Fallback LLM <span className="font-normal text-gray-400">(auto-switch on error/rate limit)</span></label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Provider</label>
                  <select value={provider}
                    onChange={e => { setSettings(p => ({...p, llm_fallback_provider: e.target.value})); saveSetting('llm_fallback_provider', e.target.value) }}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    <option value="">None (disabled)</option>
                    <option value="claude_api">Claude API (Anthropic)</option>
                    <option value="claude_code">Claude Code (Subscription)</option>
                    <option value="openai">OpenAI</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai_compat">OpenAI Compatible (OpenRouter, etc.)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Model</label>
                  <select value={currentModel}
                    onChange={e => { setSettings(p => ({...p, llm_fallback_model: e.target.value})); saveSetting('llm_fallback_model', e.target.value) }}
                    disabled={!provider}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600 disabled:opacity-50">
                    <option value="">Select model</option>
                    {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                    {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                  </select>
                </div>
              </div>
              {provider && !['claude_code', 'ollama'].includes(provider) && (
                <div className="mt-2">
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">API Key</label>
                  <div className="relative">
                    <input type={showPw.llm_fallback_api_key ? 'text' : 'password'} autoComplete="off" value={settings.llm_fallback_api_key || ''}
                      onChange={e => setSettings(p => ({...p, llm_fallback_api_key: e.target.value}))}
                      onBlur={e => saveSetting('llm_fallback_api_key', e.target.value)}
                      className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                    <button type="button" onClick={() => togglePw('llm_fallback_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                      {showPw.llm_fallback_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>
              )}
              {provider === 'openai_compat' && (
                <div className="mt-2">
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Base URL</label>
                  <input type="text" autoComplete="off" value={settings.llm_fallback_base_url || ''}
                    onChange={e => setSettings(p => ({...p, llm_fallback_base_url: e.target.value}))}
                    onBlur={e => saveSetting('llm_fallback_base_url', e.target.value)}
                    placeholder="https://openrouter.ai/api/v1"
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              )}
            </div>
          )
        })()}
        {/* Custom Models — shared across primary & fallback */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const customModels = models.filter(m => m.custom)
          const providerLabels = { claude_api: 'Claude API', claude_code: 'Claude Code', openai: 'OpenAI', ollama: 'Ollama', openai_compat: 'OpenAI Compat' }
          return (
            <div className="mb-5">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Add Custom Model</label>
              <div className="flex items-center gap-2">
                <select id="custom-model-provider" defaultValue={settings.llm_provider || 'claude_api'}
                  className="border rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="claude_api">Claude API</option>
                  <option value="claude_code">Claude Code</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="openai_compat">OpenAI Compat</option>
                </select>
                <input type="text" id="custom-model-name" placeholder="Add custom model..."
                  className="border rounded px-2 py-1 text-xs flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                <button onClick={() => {
                  const prov = document.getElementById('custom-model-provider').value
                  const input = document.getElementById('custom-model-name')
                  const name = input.value.trim(); if (!name) return
                  if (models.some(m => m.model === name && m.provider === prov)) return
                  const updated = [...models, { provider: prov, model: name, label: name + ' (custom)', custom: true }]
                  saveSetting('llm_models_list', updated)
                  setSettings(p => ({...p, llm_models_list: updated}))
                  input.value = ''
                }} className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Add</button>
              </div>
              {customModels.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {customModels.map(m => (
                    <span key={m.provider + ':' + m.model} className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                      <span className="text-gray-400">{providerLabels[m.provider] || m.provider}:</span> {m.model}
                      <button onClick={() => {
                        const updated = models.filter(x => !(x.model === m.model && x.provider === m.provider && x.custom))
                        saveSetting('llm_models_list', updated); setSettings(p => ({...p, llm_models_list: updated}))
                      }} className="text-red-400 hover:text-red-600">&times;</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })()}
        <hr className="border-gray-200 dark:border-gray-700 my-4" />
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Max Parallel Scoring Jobs</label>
          <input type="number" min="1" max="20"
            className="border rounded px-2 py-1.5 text-sm w-20 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            value={settings.scoring_max_concurrent || '5'}
            onChange={e => setSettings({...settings, scoring_max_concurrent: e.target.value})}
            onBlur={e => saveSetting('scoring_max_concurrent', e.target.value)}
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Additional scoring requests queue until a slot opens. Prevents DB connection pool exhaustion.</p>
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Default Scoring Depth</label>
          <select value={settings.scoring_default_depth || 'full'}
            onChange={e => { setSettings({...settings, scoring_default_depth: e.target.value}); saveSetting('scoring_default_depth', e.target.value) }}
            className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
            <option value="light">Light (score only)</option>
            <option value="full">Full (score + keyword analysis + report)</option>
          </select>
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">On Save Action</label>
          <select value={settings.on_save_action || 'off'}
            onChange={e => { setSettings({...settings, on_save_action: e.target.value}); saveSetting('on_save_action', e.target.value) }}
            className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
            <option value="off">Off (don't score on save)</option>
            <option value="light">Light (score only)</option>
            <option value="full">Full (score + keywords + report)</option>
          </select>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">What happens when you save a job. Only runs if the job has no existing scores.</p>
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Scoring Rubric</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={5}
            defaultValue={settings.scoring_rubric || ''}
            onBlur={e => saveSetting('scoring_rubric', e.target.value)}
            placeholder="Custom scoring rubric..."
          />
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Light Output Schema</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={5}
            defaultValue={settings.scoring_output_light || ''}
            onBlur={e => saveSetting('scoring_output_light', e.target.value)}
            placeholder="Light scoring output schema..."
          />
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Full Output Schema</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={5}
            defaultValue={settings.scoring_output_full || ''}
            onBlur={e => saveSetting('scoring_output_full', e.target.value)}
            placeholder="Full scoring output schema..."
          />
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">Placeholders available: {'{job_description}'}, {'{cv_text}'}, {'{cv_names}'}. CV_NAMES_HERE in output schemas is replaced with actual CV names at runtime.</p>
      </section>

      {/* CV Tailoring */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">CV Tailoring</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">CV Tailoring</p>
              <p className="mb-1">LLM reformulates your resume bullets with JD-specific keywords. Only changes bullets that benefit from alignment -- leaves well-suited ones unchanged.</p>
              <p className="mb-1">Also suggests 1-2 new bullets per role in STAR format, derived from your existing experience.</p>
              <p><b>Rule</b>: never invents skills or experience. Only reformulates what's already in your resume.</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Provider</label>
            <select value={settings.cv_tailor_llm_provider || ''}
              onChange={e => { setSettings(p => ({...p, cv_tailor_llm_provider: e.target.value})); saveSetting('cv_tailor_llm_provider', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Use Primary</option>
              <option value="claude_api">Claude API (Anthropic)</option>
              <option value="claude_code">Claude Code (Subscription)</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (Local)</option>
              <option value="openai_compat">OpenAI Compatible</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Model</label>
            {(() => {
              const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
              const provider = settings.cv_tailor_llm_provider || settings.llm_provider || 'claude_api'
              const filtered = models.filter(m => m.provider === provider)
              const currentModel = settings.cv_tailor_llm_model || ''
              const currentInList = filtered.some(m => m.model === currentModel)
              return (
                <select value={currentModel}
                  onChange={e => { setSettings(p => ({...p, cv_tailor_llm_model: e.target.value})); saveSetting('cv_tailor_llm_model', e.target.value) }}
                  className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="">Use Primary</option>
                  {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                  {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                </select>
              )
            })()}
          </div>
        </div>

        {settings.cv_tailor_llm_provider && !['claude_code', 'ollama', ''].includes(settings.cv_tailor_llm_provider) && (
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">API Key</label>
            <div className="relative">
              <input type={showPw.cv_tailor_llm_api_key ? 'text' : 'password'} autoComplete="off" value={settings.cv_tailor_llm_api_key || ''}
                onChange={e => setSettings(p => ({...p, cv_tailor_llm_api_key: e.target.value}))}
                onBlur={e => saveSetting('cv_tailor_llm_api_key', e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('cv_tailor_llm_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.cv_tailor_llm_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        )}

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Tailoring Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={10}
            defaultValue={settings.cv_tailor_prompt || ''}
            onBlur={e => saveSetting('cv_tailor_prompt', e.target.value)}
            placeholder="CV tailoring prompt template..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Placeholders: {'{resume_json}'}, {'{job_description}'}</p>
        </div>
      </section>

      {/* Email Classification */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Email Classification</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Email Classification</p>
              <p className="mb-1"><b>Pass 1</b> (free): phrase-based filter catches obvious auto-replies and rejections instantly.</p>
              <p className="mb-1"><b>Pass 2</b> (LLM): for ambiguous emails, sends to LLM with your active applications list. LLM picks the matching application and classifies as interview/offer/rejected.</p>
              <p className="mb-1"><b>Confidence threshold</b>: below this, LLM results are logged but not acted on.</p>
              <p><b>Gmail Query</b>: subject keywords + sender patterns build the Gmail search. Company/ATS domains are always included.</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Enable LLM Classification</label>
            <select value={settings.email_llm_enabled || 'false'}
              onChange={e => { setSettings(p => ({...p, email_llm_enabled: e.target.value})); saveSetting('email_llm_enabled', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="false">Disabled</option>
              <option value="true">Enabled (LLM for ambiguous emails)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Confidence Threshold</label>
            <input type="number" min="0" max="100" value={settings.email_llm_confidence_threshold || '70'}
              onChange={e => setSettings(p => ({...p, email_llm_confidence_threshold: e.target.value}))}
              onBlur={e => saveSetting('email_llm_confidence_threshold', e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Min confidence (0-100) to auto-act on LLM result</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Provider</label>
            <select value={settings.email_llm_provider || ''}
              onChange={e => { setSettings(p => ({...p, email_llm_provider: e.target.value})); saveSetting('email_llm_provider', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Use Primary</option>
              <option value="claude_api">Claude API (Anthropic)</option>
              <option value="claude_code">Claude Code (Subscription)</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (Local)</option>
              <option value="openai_compat">OpenAI Compatible</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Model</label>
            {(() => {
              const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
              const provider = settings.email_llm_provider || settings.llm_provider || 'claude_api'
              const filtered = models.filter(m => m.provider === provider)
              const currentModel = settings.email_llm_model || ''
              const currentInList = filtered.some(m => m.model === currentModel)
              return (
                <select value={currentModel}
                  onChange={e => { setSettings(p => ({...p, email_llm_model: e.target.value})); saveSetting('email_llm_model', e.target.value) }}
                  className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="">Use Primary</option>
                  {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                  {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                </select>
              )
            })()}
          </div>
        </div>

        {settings.email_llm_provider && !['claude_code', 'ollama', ''].includes(settings.email_llm_provider) && (
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">API Key</label>
            <div className="relative">
              <input type={showPw.email_llm_api_key ? 'text' : 'password'} autoComplete="off" value={settings.email_llm_api_key || ''}
                onChange={e => setSettings(p => ({...p, email_llm_api_key: e.target.value}))}
                onBlur={e => saveSetting('email_llm_api_key', e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('email_llm_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.email_llm_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        )}

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Classification Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={8}
            defaultValue={settings.email_llm_prompt || ''}
            onBlur={e => saveSetting('email_llm_prompt', e.target.value)}
            placeholder="Email classification prompt template..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Placeholders: {'{applications}'}, {'{from}'}, {'{subject}'}, {'{body}'}</p>
        </div>

        <hr className="border-gray-200 dark:border-gray-700 my-4" />
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Gmail Search Query</h3>
        <div className="grid gap-4" style={{gridTemplateColumns: '1.2fr 1.2fr 1.6fr'}}>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Subject Keywords</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.email_gmail_query_subjects) ? settings.email_gmail_query_subjects.join('\n') : ''}
              onBlur={e => updatePhrases('email_gmail_query_subjects', e.target.value)}
              placeholder="One keyword per line..."
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Sender Patterns</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.email_gmail_query_senders) ? settings.email_gmail_query_senders.join('\n') : ''}
              onBlur={e => updatePhrases('email_gmail_query_senders', e.target.value)}
              placeholder="One pattern per line..."
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Exclusions</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.email_gmail_query_exclusions) ? settings.email_gmail_query_exclusions.join('\n') : ''}
              onBlur={e => updatePhrases('email_gmail_query_exclusions', e.target.value)}
              placeholder="One term per line..."
            />
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">These build the Gmail search query. An email matches if it's from any sender pattern OR contains any subject keyword. Exclusions filter out matches. Sender formats: domains (microsoft.com), prefixes (careers@), or full addresses (no-reply@greenhouse.io).</p>
      </section>

      </>)}

      {activeTab === 'general' && (<>
      {/* Tracer Links */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Tracer Links</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Tracer Links</p>
              <p className="mb-1">When enabled, PDF downloads replace your real URLs (LinkedIn, Portfolio) with redirect links through your domain.</p>
              <p className="mb-1">When a recruiter clicks, the click is logged (device, browser, referrer) and they're redirected to the real URL.</p>
              <p><b>Requires</b>: a public domain pointing to this app. Set the base URL to your domain.</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">Replace URLs in resume PDFs with tracking redirects to see when recruiters click your links.</p>

        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Enable</label>
            <select value={settings.tracer_links_enabled || 'false'}
              onChange={e => { setSettings(p => ({...p, tracer_links_enabled: e.target.value})); saveSetting('tracer_links_enabled', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="false">Disabled</option>
              <option value="true">Enabled</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Base URL</label>
            <input type="text" value={settings.tracer_links_base_url || ''}
              onChange={e => setSettings(p => ({...p, tracer_links_base_url: e.target.value}))}
              onBlur={e => saveSetting('tracer_links_base_url', e.target.value)}
              placeholder="https://yourdomain.com"
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">URL Style</label>
            <select value={settings.tracer_links_url_style || 'path'}
              onChange={e => { setSettings(p => ({...p, tracer_links_url_style: e.target.value})); saveSetting('tracer_links_url_style', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="path">Path + random (/cv/a7x2kp)</option>
              <option value="param">Param + random (?cv=a7x2kp)</option>
              <option value="path_jobid">Path + job ID (/cv/142li)</option>
              <option value="param_jobid">Param + job ID (?cv=142li)</option>
            </select>
          </div>
        </div>
      </section>

      {/* Global Exclude */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Global Exclude</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Global Exclude</p>
              <p className="mb-1"><b>Companies</b>: exact match, case-insensitive. Jobs from these companies are skipped in ALL searches.</p>
              <p className="mb-1"><b>Title Keywords</b>: whole-word match. Merged with per-search/company excludes. E.g. "intern" skips "Software Engineering Intern".</p>
              <p><b>Body Phrases</b>: scanned in job descriptions. Used for H-1B restrictions ("will not sponsor") and language markers ("Deutschkenntnisse").</p>
            </div>
          </div>
        </div>
        <div className="grid gap-4" style={{gridTemplateColumns: '1.2fr 1.2fr 1.6fr'}}>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Companies</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.company_exclude_global) ? settings.company_exclude_global.join('\n') : ''}
              onBlur={e => updatePhrases('company_exclude_global', e.target.value)}
              placeholder="One company per line..."
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Exact match, case-insensitive.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title Keywords</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.title_exclude_global) ? settings.title_exclude_global.join('\n') : ''}
              onBlur={e => updatePhrases('title_exclude_global', e.target.value)}
              placeholder="One keyword per line..."
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Whole-word, case-insensitive.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Body Phrases</label>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              rows={8}
              defaultValue={Array.isArray(settings.body_exclusion_phrases) ? settings.body_exclusion_phrases.join('\n') : ''}
              onBlur={e => updatePhrases('body_exclusion_phrases', e.target.value)}
              placeholder="One phrase per line..."
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">JD phrases that auto-skip (H-1B, language). Case-insensitive.</p>
          </div>
        </div>
      </section>

      {/* Dedup Tracking Params */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Dedup Tracking Params</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Dedup Tracking Params</p>
              <p className="mb-1">URL query parameters stripped before hashing for deduplication. Prevents tracking noise (utm_source, fbclid, etc.) from creating false "new" jobs.</p>
              <p>All <b>utm_*</b> params are always stripped regardless. Add params here when you notice the same job appearing multiple times with different URL params.</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">URL query parameters stripped before dedup hashing. Adding a param here prevents it from creating false "new" jobs. All <code>utm_*</code> params are always stripped regardless.</p>
        <textarea
          className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
          rows={5}
          defaultValue={Array.isArray(settings.dedup_tracking_params) ? settings.dedup_tracking_params.join('\n') : ''}
          onBlur={e => updatePhrases('dedup_tracking_params', e.target.value)}
          placeholder="One param per line..."
        />
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          {Array.isArray(settings.dedup_tracking_params) ? settings.dedup_tracking_params.length : 0} params configured. One per line, case-insensitive.
        </p>
      </section>
      </>)}

      {activeTab === 'accounts' && (<>
      {/* Notification Settings */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Notifications</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Telegram Notifications</p>
              <p className="mb-1">Sends alerts for: new high-scoring jobs, daily digest, application status changes (email), and scrape health warnings.</p>
              <p>Get your <b>chat_id</b> by messaging @userinfobot on Telegram. The bot token comes from @BotFather.</p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Enabled</label>
            <select value={String(settings.telegram_enabled ?? 'true')}
              onChange={e => saveSetting('telegram_enabled', e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Chat ID</label>
            <input type="text" value={settings.telegram_chat_id || ''}
              onChange={e => setSettings({...settings, telegram_chat_id: e.target.value})}
              onBlur={e => saveSetting('telegram_chat_id', e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Alert Score Threshold</label>
            <input type="number" value={settings.fit_score_threshold || 60}
              onChange={e => setSettings({...settings, fit_score_threshold: e.target.value})}
              onBlur={e => saveSetting('fit_score_threshold', parseInt(e.target.value))}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        </div>
      </section>

      {/* Jobright.ai */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Jobright.ai</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Jobright.ai</p>
              <p className="mb-1">AI-powered job recommendations via REST API. Uses a 60-day session cookie (auto-managed).</p>
              <p className="mb-1">Two modes: <b>recommendations</b> (leave search term empty) or <b>keyword search</b> (enter a term). Session auto-refreshes on expiry.</p>
              <p className="text-yellow-300"><b>ToS Notice</b>: this feature may violate Jobright's Terms of Service. Use at your own risk. See LEGAL_DISCLAIMER.md.</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          Credentials for fetching personalized job recommendations from Jobright.ai. Session cookie is auto-managed (60-day expiry).
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Email</label>
            <input type="text" value={settings.jobright_email || ''}
              onChange={e => setSettings({...settings, jobright_email: e.target.value})}
              onBlur={e => saveSetting('jobright_email', e.target.value)}
              placeholder="your@email.com"
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Password</label>
            <div className="relative">
              <input type={showPw.jobright_password ? 'text' : 'password'} autoComplete="off" value={settings.jobright_password || ''}
                onChange={e => setSettings({...settings, jobright_password: e.target.value})}
                onBlur={e => saveSetting('jobright_password', e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('jobright_password')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.jobright_password ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* LinkedIn Personal Scraping */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">LinkedIn Personal Scraping</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">LinkedIn Personal Scraping</p>
              <p className="mb-1">Uses Playwright with stealth mode to scrape your personalized LinkedIn collections (Recommended, Top Applicant).</p>
              <p className="mb-1">Requires your real LinkedIn credentials. Cookie is cached to avoid repeated logins.</p>
              <p className="mb-1"><b>Warning</b>: excessive scraping may trigger LinkedIn security. Use conservative intervals.</p>
              <p className="text-yellow-300"><b>ToS Notice</b>: this feature may violate LinkedIn's Terms of Service. Use at your own risk. See LEGAL_DISCLAIMER.md.</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          Credentials for scraping personalized job recommendations. Use sparingly -- LinkedIn may restrict automated accounts.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Email</label>
            <input type="text" value={settings.linkedin_email || ''}
              onChange={e => setSettings({...settings, linkedin_email: e.target.value})}
              onBlur={e => saveSetting('linkedin_email', e.target.value)}
              placeholder="your@email.com"
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Password</label>
            <div className="relative">
              <input type={showPw.linkedin_password ? 'text' : 'password'} autoComplete="off" value={settings.linkedin_password || ''}
                onChange={e => setSettings({...settings, linkedin_password: e.target.value})}
                onBlur={e => saveSetting('linkedin_password', e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('linkedin_password')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.linkedin_password ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* LinkedIn Extension (Voyager API) */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">LinkedIn Extension (Mock Account)</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">LinkedIn Extension Mock Account</p>
              <p className="mb-1">The Chrome Extension captures job IDs as you browse LinkedIn. The backend uses a <b>separate account</b> to fetch full job data via LinkedIn's Voyager API.</p>
              <p className="mb-1"><b>Important</b>: if the account gets a CHALLENGE error, log in manually via browser first to clear the security prompt, then restart.</p>
              <p className="text-yellow-300"><b>ToS Notice</b>: this feature may violate LinkedIn's Terms of Service. Use at your own risk. See LEGAL_DISCLAIMER.md.</p>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          Separate LinkedIn account used by the Extension capture to fetch job details via Voyager API. Use a throwaway account -- not your main one.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Email</label>
            <input type="text" value={settings.linkedin_mock_email || ''}
              onChange={e => setSettings({...settings, linkedin_mock_email: e.target.value})}
              onBlur={e => saveSetting('linkedin_mock_email', e.target.value)}
              placeholder="mock@email.com"
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Password</label>
            <div className="relative">
              <input type={showPw.linkedin_mock_password ? 'text' : 'password'} autoComplete="off" value={settings.linkedin_mock_password || ''}
                onChange={e => setSettings({...settings, linkedin_mock_password: e.target.value})}
                onBlur={e => saveSetting('linkedin_mock_password', e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('linkedin_mock_password')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.linkedin_mock_password ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>
      </section>

      </>)}

      {activeTab === 'general' && (<>
      {/* Proxy & API Key */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Advanced</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Advanced</p>
              <p className="mb-1"><b>Proxy</b>: optional rotating proxy for scraping (socks5://... format). Used by all scrapers.</p>
              <p><b>API Key</b>: protects the dashboard. If empty, all access is allowed (first-run mode). Set a key to require authentication.</p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Proxy URL</label>
            <input type="text" value={settings.proxy_url || ''} placeholder="Optional: socks5://..."
              onChange={e => setSettings({...settings, proxy_url: e.target.value})}
              onBlur={e => saveSetting('proxy_url', e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Dashboard API Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input type={showPw.dashboard_api_key ? 'text' : 'password'} autoComplete="off" value={settings.dashboard_api_key || ''}
                  onChange={e => setSettings({...settings, dashboard_api_key: e.target.value})}
                  className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                <button type="button" onClick={() => togglePw('dashboard_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                  {showPw.dashboard_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <button onClick={saveApiKey}
                className="px-3 py-1.5 text-sm bg-gray-600 text-white rounded hover:bg-gray-700">Save</button>
            </div>
          </div>
        </div>
      </section>

      {/* Manual Triggers */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Manual Triggers</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-72 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Manual Triggers</p>
              <p>Run scraping, email checks, H-1B refresh, CV analysis, and database backups on demand. These bypass scheduler intervals and run immediately.</p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { endpoint: '/scrape/run-all', label: 'Run All Searches', icon: Play },
            { endpoint: '/email/check-now', label: 'Check Email', icon: RefreshCw },
            { endpoint: '/h1b/refresh', label: 'Refresh H-1B Data', icon: RefreshCw },
            { endpoint: '/telegram/test', label: 'Send Test Telegram', icon: Send },
          ].map(({ endpoint, label, icon: Icon }) => (
            <button key={endpoint} onClick={() => triggerAction(endpoint, label)}
              disabled={triggerStatus[endpoint] === 'running'}
              className={`flex items-center justify-center gap-2 px-3 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 ${
                triggerStatus[endpoint] === 'running' ? 'opacity-50' : ''
              } ${triggerStatus[endpoint] === 'done' ? 'bg-green-50 border-green-300' : ''}`}>
              <Icon size={14} />
              {triggerStatus[endpoint] === 'running' ? 'Running...' : triggerStatus[endpoint] === 'done' ? 'Done!' : label}
            </button>
          ))}
        </div>
      </section>
      </>)}
    </div>
  )
}
