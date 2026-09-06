import React, { useState, useEffect } from 'react'
import api from '../api'
import ModelCombobox from './ModelCombobox'
import { RefreshCw, Send, Play, Info, Eye, EyeOff } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState({})
  const [resumes, setResumes] = useState([])
  const [personaPopulated, setPersonaPopulated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [triggerStatus, setTriggerStatus] = useState({})
  const [showPw, setShowPw] = useState({})
  const [activeTab, setActiveTab] = useState(() => localStorage.getItem('settings_tab') || 'general')
  const switchTab = (tab) => { setActiveTab(tab); localStorage.setItem('settings_tab', tab) }
  const togglePw = (key) => setShowPw(p => ({...p, [key]: !p[key]}))

  // Live model catalogs for the "Add Custom Model" typeahead (per provider).
  const SEARCHABLE_PROVIDERS = ['openrouter', 'openai', 'claude_api', 'claude_code']
  const [customProvider, setCustomProvider] = useState('claude_api')
  const [customModelName, setCustomModelName] = useState('')
  const [providerModels, setProviderModels] = useState({})   // provider -> [{id,name}]
  const [modelsLoading, setModelsLoading] = useState({})      // provider -> bool
  const [modelsError, setModelsError] = useState({})          // provider -> string
  const fetchProviderModels = async (provider) => {
    if (!SEARCHABLE_PROVIDERS.includes(provider)) return
    if (providerModels[provider] || modelsLoading[provider]) return
    setModelsLoading(p => ({ ...p, [provider]: true }))
    setModelsError(p => ({ ...p, [provider]: '' }))
    try {
      const { data } = await api.get('/llm/models', { params: { provider } })
      setProviderModels(p => ({ ...p, [provider]: data.models || [] }))
    } catch (e) {
      setModelsError(p => ({ ...p, [provider]: e?.response?.data?.detail || 'Could not load models' }))
    }
    setModelsLoading(p => ({ ...p, [provider]: false }))
  }

  const fetchAll = async () => {
    try {
      const { data: settingsData } = await api.get('/settings')
      setSettings(settingsData)
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { fetchAll() }, [])

  useEffect(() => {
    api.get('/resumes?is_base=true')
      .then(({ data }) => setResumes(data || []))
      .catch(() => {})
    api.get('/persona')
      .then(({ data }) => {
        setPersonaPopulated(Object.keys(data?.resume_content || {}).length > 0)
      })
      .catch(() => setPersonaPopulated(false))
  }, [])

  const saveSetting = async (key, value) => {
    try {
      await api.patch('/settings', { [key]: value })
      // Functional update — a plain {...settings} spread here would snapshot
      // pre-await state and revert any field edited during the request.
      setSettings(prev => ({ ...prev, [key]: value }))
      setMessage('Setting saved')
      setTimeout(() => setMessage(''), 2000)
    } catch (e) { console.error(e) }
  }

  const saveApiKey = async () => {
    const key = settings.dashboard_api_key
    localStorage.setItem('jobnavigator_api_key', key)
    await saveSetting('dashboard_api_key', key)
    // Refresh the httpOnly session cookie so iframe/download requests keep working
    try {
      await api.post('/auth/set-session', { api_key: key })
    } catch (e) {
      console.warn('Failed to refresh session cookie:', e)
    }
  }

  const triggerAction = async (endpoint) => {
    setTriggerStatus(prev => ({ ...prev, [endpoint]: 'running' }))
    try {
      await api.post(endpoint)
      setTriggerStatus(prev => ({ ...prev, [endpoint]: 'done' }))
      setTimeout(() => setTriggerStatus(prev => ({ ...prev, [endpoint]: '' })), 3000)
    } catch (e) {
      setTriggerStatus(prev => ({ ...prev, [endpoint]: 'error' }))
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
      {/* Default Resume for Scoring */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <h2 className="font-semibold text-lg dark:text-gray-100 mb-3">Default Resume for Scoring</h2>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          Used when a Company has no <code>selected_resume_ids</code> configured.
        </p>
        <select
          value={settings.default_resume_id || ''}
          onChange={(e) => saveSetting('default_resume_id', e.target.value)}
          className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
        >
          <option value="">(use all base resumes + Persona)</option>
          {(resumes || []).filter(r => r.is_base).map(r => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
          {personaPopulated && <option value="persona">Persona</option>}
        </select>
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
      {/* AI Models & Providers — global LLM config shared by every AI feature */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">AI Models &amp; Providers</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Provider &amp; model config (used by every AI feature)</p>
              <p className="mb-1.5"><b>Primary LLM</b> — the default provider + model every AI feature uses. Claude API uses the settings key (or ANTHROPIC_API_KEY). Claude Code uses your subscription via OAuth (same models as Claude API). OpenAI/Ollama use their keys. <b>OpenRouter</b> reaches every vendor with one key — vendor-prefixed slugs (e.g. <code>anthropic/claude-sonnet-5</code>), no prompt-cache discount.</p>
              <p><b>Add Custom Model</b> — type to search a provider's live catalog (OpenRouter / OpenAI / Claude) or enter any slug, then Add. Models appear in the dropdowns; the × on a chip deletes one (removals persist).</p>
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
                    <option value="openrouter">OpenRouter</option>
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
            </div>
          )
        })()}
        {/* Custom Models — shared across primary & fallback */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const providerLabels = { claude_api: 'Claude API', claude_code: 'Claude Code', openai: 'OpenAI', ollama: 'Ollama', openrouter: 'OpenRouter' }
          const canSearch = SEARCHABLE_PROVIDERS.includes(customProvider)
          const liveModels = providerModels[customProvider] || []
          const loadingModels = modelsLoading[customProvider]
          const modelErr = modelsError[customProvider]
          const addModel = () => {
            const name = (customModelName || '').trim(); if (!name) return
            if (!models.some(m => m.model === name && m.provider === customProvider)) {
              const updated = [...models, { provider: customProvider, model: name, label: name + ' (custom)', custom: true }]
              saveSetting('llm_models_list', updated)
              setSettings(p => ({...p, llm_models_list: updated}))
            }
            setCustomModelName('')
          }
          return (
            <div className="mb-5">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Add Custom Model</label>
              <div className="flex items-center gap-2">
                <select value={customProvider}
                  onChange={e => { setCustomProvider(e.target.value); fetchProviderModels(e.target.value) }}
                  className="border rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="claude_api">Claude API</option>
                  <option value="claude_code">Claude Code</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
                {canSearch ? (
                  <ModelCombobox
                    models={liveModels}
                    value={customModelName}
                    onChange={setCustomModelName}
                    onFocus={() => fetchProviderModels(customProvider)}
                    onEnter={addModel}
                    loading={loadingModels}
                    placeholder="Search live models…"
                  />
                ) : (
                  <input type="text" value={customModelName}
                    onChange={e => setCustomModelName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') addModel() }}
                    placeholder="Add custom model..."
                    className="border rounded px-2 py-1 text-xs flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                )}
                <button onClick={addModel} className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Add</button>
              </div>
              {canSearch && (
                <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1">
                  {loadingModels ? 'Loading live models…'
                    : modelErr ? modelErr
                    : liveModels.length ? `${liveModels.length} models available — type to search, then Add.${customProvider === 'openrouter' ? ' Slugs are vendor-prefixed (e.g. anthropic/claude-sonnet-5).' : ''}`
                    : 'Type a model name, then Add.'}
                </p>
              )}
              {(() => {
                const provModels = models.filter(m => m.provider === customProvider)
                if (!provModels.length) return null
                return (
                  <div className="mt-2">
                    <div className="text-[10px] text-gray-400 dark:text-gray-500 mb-1">{providerLabels[customProvider] || customProvider} models — <b>×</b> to delete:</div>
                    <div className="flex flex-wrap gap-1">
                      {provModels.map(m => (
                        <span key={m.provider + ':' + m.model} className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                          {m.model}{m.custom && <span className="text-blue-400" title="custom">•</span>}
                          <button title="Delete model" onClick={() => {
                            if (!window.confirm(`Delete model "${m.model}" from ${providerLabels[m.provider] || m.provider}?`)) return
                            const updated = models.filter(x => !(x.model === m.model && x.provider === m.provider))
                            saveSetting('llm_models_list', updated); setSettings(p => ({...p, llm_models_list: updated}))
                          }} className="text-red-400 hover:text-red-600 leading-none">&times;</button>
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </div>
          )
        })()}
      </section>

      {/* Resume AI Scoring Configuration — scoring-specific settings */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Resume AI Scoring Configuration</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">How scoring works</p>
              <p className="mb-1.5"><b>Scoring LLM → Fallback</b> — scores with the Scoring LLM (empty = the shared Primary); on error/rate-limit it retries with the Fallback (scoring-only).</p>
              <p className="mb-1.5"><b>Scoring Depth</b> — <i>Light</i>: scores only (fast, 600 tokens). <i>Full</i>: scores + keyword analysis + requirement mapping + report (2000 tokens).</p>
              <p className="mb-1.5"><b>On Save Action</b> — what happens when you save a job. Only runs if the job has no existing scores.</p>
              <p><b>Rubric &amp; Output Schemas</b> — editable prompts sent to the LLM. CV_NAMES_HERE is replaced with actual Resume names at runtime.</p>
            </div>
          </div>
        </div>
        {/* Scoring provider/model — empty = use Primary. Falls back to the Fallback below on error. */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const scProvider = settings.scoring_llm_provider || ''
          const effProvider = scProvider || settings.llm_provider || 'claude_api'
          const filtered = models.filter(m => m.provider === effProvider)
          const currentModel = settings.scoring_llm_model || ''
          const currentInList = filtered.some(m => m.model === currentModel)
          return (
            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Scoring LLM <span className="font-normal text-gray-400">(empty = use Primary)</span></label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Provider</label>
                  <select value={scProvider}
                    onChange={e => { setSettings(p => ({...p, scoring_llm_provider: e.target.value})); saveSetting('scoring_llm_provider', e.target.value) }}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    <option value="">Use Primary</option>
                    <option value="claude_api">Claude API (Anthropic)</option>
                    <option value="claude_code">Claude Code (Subscription)</option>
                    <option value="openai">OpenAI</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openrouter">OpenRouter</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">Model</label>
                  <select value={currentModel}
                    onChange={e => { setSettings(p => ({...p, scoring_llm_model: e.target.value})); saveSetting('scoring_llm_model', e.target.value) }}
                    className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    <option value="">Use Primary</option>
                    {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                    {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                  </select>
                </div>
              </div>
              {scProvider && !['claude_code', 'ollama'].includes(scProvider) && (
                <div className="mt-2">
                  <label className="block text-[10px] text-gray-500 dark:text-gray-500 mb-0.5">API Key</label>
                  <div className="relative">
                    <input type={showPw.scoring_llm_api_key ? 'text' : 'password'} autoComplete="off" value={settings.scoring_llm_api_key || ''}
                      onChange={e => setSettings(p => ({...p, scoring_llm_api_key: e.target.value}))}
                      onBlur={e => saveSetting('scoring_llm_api_key', e.target.value)}
                      className="border rounded px-2 py-1.5 text-sm w-full pr-8 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                    <button type="button" onClick={() => togglePw('scoring_llm_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                      {showPw.scoring_llm_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })()}
        {/* Fallback LLM — scoring-only */}
        {(() => {
          const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
          const provider = settings.llm_fallback_provider || ''
          const filtered = models.filter(m => m.provider === provider)
          const currentModel = settings.llm_fallback_model || ''
          const currentInList = filtered.some(m => m.model === currentModel)
          return (
            <div className="mb-4">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Fallback LLM <span className="font-normal text-gray-400">(scoring only — auto-switch on error/rate limit)</span></label>
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
                    <option value="openrouter">OpenRouter</option>
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
            </div>
          )
        })()}
        <hr className="border-gray-200 dark:border-gray-700 my-4" />
        <div>
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
          <label className="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
            <input type="checkbox"
              checked={settings.prompt_caching_enabled === true || settings.prompt_caching_enabled === 'true' || settings.prompt_caching_enabled === undefined}
              onChange={e => { const v = e.target.checked; setSettings({...settings, prompt_caching_enabled: v}); saveSetting('prompt_caching_enabled', v ? 'true' : 'false') }}
              className="accent-indigo-600"
            />
            Prompt Caching (Anthropic)
          </label>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Send the rubric + Resumes + schema as a cached block so subsequent scoring calls reuse it at ~10× cheaper input tokens. Only active when provider is <code>claude_api</code>; no effect with <code>claude_code</code> or local providers. Disable as a rollback lever.</p>
        </div>
        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Default Scoring Depth</label>
          <select value={settings.scoring_default_depth || 'full'}
            onChange={e => { setSettings({...settings, scoring_default_depth: e.target.value}); saveSetting('scoring_default_depth', e.target.value) }}
            className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
            <option value="light">Light (score only)</option>
            <option value="full">Full (score + keyword analysis + report)</option>
          </select>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Ultimate fallback for the auto-scorer. Used when neither the source Company nor the Search has its own depth override.
          </p>
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
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">Placeholders available: {'{job_description}'}, {'{cv_text}'}, {'{cv_names}'}. CV_NAMES_HERE in output schemas is replaced with actual Resume names at runtime.</p>
      </section>

      {/* Resume Tailoring */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Resume Tailoring</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Resume Tailoring</p>
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
                    <option value="openrouter">OpenRouter</option>
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
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Resume Tailoring Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={10}
            defaultValue={settings.cv_tailor_prompt || ''}
            onBlur={e => saveSetting('cv_tailor_prompt', e.target.value)}
            placeholder="Resume tailoring prompt template..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Used when tailoring from a base Resume. Placeholders: {'{resume_json}'}, {'{job_description}'}
          </p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Persona Tailoring Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={10}
            defaultValue={settings.persona_tailor_prompt || ''}
            onBlur={e => saveSetting('persona_tailor_prompt', e.target.value)}
            placeholder="Persona tailoring prompt template (selects 3-5 best bullets per role from rich pool)..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Used when tailoring from Persona (richer pool — needs constrained selection). Falls back to the Resume prompt if empty. Placeholders: {'{resume_json}'}, {'{job_description}'}
          </p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Auto-score after tailoring</label>
          <select
            value={(() => {
              const raw = (settings.tailor_auto_quick_score || 'light').toString().toLowerCase()
              if (raw === 'off' || raw === 'false' || raw === 'no' || raw === '0') return 'off'
              if (raw === 'full') return 'full'
              return 'light'
            })()}
            onChange={e => saveSetting('tailor_auto_quick_score', e.target.value)}
            className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
          >
            <option value="off">Off (don't score after tailoring)</option>
            <option value="light">Light (score only)</option>
            <option value="full">Full (score + keywords + report)</option>
          </select>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            When a tailor finishes, a "Tailored: N" entry is added to the job's score list. Light is fast and cheap; Full also writes the requirement_mapping / keyword_coverage report.
          </p>
        </div>
      </section>

      {/* Cover Letters */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Cover Letters</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Cover Letters</p>
              <p className="mb-1">Generated from the paired resume + persona preferences + job description. Voice presets are injected into the prompt; switching voice/length reuses the cached resume prefix (cheap to regenerate).</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Provider</label>
            <select value={settings.cover_letter_llm_provider || ''}
              onChange={e => { setSettings(p => ({...p, cover_letter_llm_provider: e.target.value})); saveSetting('cover_letter_llm_provider', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Use Primary</option>
              <option value="claude_api">Claude API (Anthropic)</option>
              <option value="claude_code">Claude Code (Subscription)</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (Local)</option>
                    <option value="openrouter">OpenRouter</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Model</label>
            {(() => {
              const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
              const provider = settings.cover_letter_llm_provider || settings.llm_provider || 'claude_api'
              const filtered = models.filter(m => m.provider === provider)
              const currentModel = settings.cover_letter_llm_model || ''
              const currentInList = filtered.some(m => m.model === currentModel)
              return (
                <select value={currentModel}
                  onChange={e => { setSettings(p => ({...p, cover_letter_llm_model: e.target.value})); saveSetting('cover_letter_llm_model', e.target.value) }}
                  className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="">Use Primary</option>
                  {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                  {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                </select>
              )
            })()}
          </div>
        </div>

        {settings.cover_letter_llm_provider && !['claude_code', 'ollama', ''].includes(settings.cover_letter_llm_provider) && (
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">API Key</label>
            <div className="relative">
              <input type={showPw.cover_letter_llm_api_key ? 'text' : 'password'} autoComplete="off" value={settings.cover_letter_llm_api_key || ''}
                onChange={e => setSettings(p => ({...p, cover_letter_llm_api_key: e.target.value}))}
                onBlur={e => saveSetting('cover_letter_llm_api_key', e.target.value)}
                className="w-full border rounded px-3 py-2 pr-9 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
              <button type="button" onClick={() => togglePw('cover_letter_llm_api_key')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                {showPw.cover_letter_llm_api_key ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        )}

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Default Voice</label>
          <input
            className="w-full border rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            defaultValue={settings.cover_letter_default_voice || ''}
            onBlur={e => saveSetting('cover_letter_default_voice', e.target.value)}
            placeholder="professional"
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Must match an <code>id</code> in the voice presets below.</p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Voice Presets (JSON)</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={8}
            defaultValue={typeof settings.cover_letter_voice_presets === 'string' ? settings.cover_letter_voice_presets : JSON.stringify(settings.cover_letter_voice_presets || [], null, 2)}
            onBlur={e => { try { saveSetting('cover_letter_voice_presets', JSON.parse(e.target.value)) } catch { alert('Voice presets must be valid JSON') } }}
            placeholder='[{"id":"professional","label":"Professional & direct","instruction":"..."}]'
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">List of <code>{'{id, label, instruction}'}</code>. The selected preset's instruction is injected into the generation prompt suffix.</p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Cover Letter Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={10}
            defaultValue={settings.cover_letter_prompt || ''}
            onBlur={e => saveSetting('cover_letter_prompt', e.target.value)}
            placeholder="Cover letter generation prompt template..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Placeholders: {'{voice_instruction}'}, {'{length_instruction}'}, {'{job_description}'}. The resume + persona preferences are sent as a cached prefix automatically.
          </p>
        </div>
      </section>

      {/* Application Autofill */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-lg dark:text-gray-100">Application Autofill</h2>
          <div className="relative group">
            <Info size={15} className="text-gray-400 dark:text-gray-500 cursor-help" />
            <div className="hidden group-hover:block absolute left-6 top-0 z-50 w-80 p-3 text-xs bg-gray-900 text-gray-100 rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1.5">Application Autofill</p>
              <p className="mb-1">Generates first-person answers to job-application free-text questions from the extension, grounded in your persona + Q&amp;A bank. Triggered by the Navigator button anchored to answer fields on job sites.</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Provider</label>
            <select value={settings.autofill_llm_provider || ''}
              onChange={e => { setSettings(p => ({...p, autofill_llm_provider: e.target.value})); saveSetting('autofill_llm_provider', e.target.value) }}
              className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">Use Primary</option>
              <option value="claude_api">Claude API (Anthropic)</option>
              <option value="claude_code">Claude Code (Subscription)</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (Local)</option>
                    <option value="openrouter">OpenRouter</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Model</label>
            {(() => {
              const models = Array.isArray(settings.llm_models_list) ? settings.llm_models_list : []
              const provider = settings.autofill_llm_provider || settings.llm_provider || 'claude_api'
              const filtered = models.filter(m => m.provider === provider)
              const currentModel = settings.autofill_llm_model || ''
              const currentInList = filtered.some(m => m.model === currentModel)
              return (
                <select value={currentModel}
                  onChange={e => { setSettings(p => ({...p, autofill_llm_model: e.target.value})); saveSetting('autofill_llm_model', e.target.value) }}
                  className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="">Use Primary</option>
                  {!currentInList && currentModel && <option value={currentModel}>Custom: {currentModel}</option>}
                  {filtered.map(m => <option key={m.model} value={m.model}>{m.label || m.model}</option>)}
                </select>
              )
            })()}
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Default Answer Length (characters)</label>
          <input type="number" min="1" value={settings.autofill_default_length || '120'}
            onChange={e => setSettings(p => ({...p, autofill_default_length: e.target.value}))}
            onBlur={e => saveSetting('autofill_default_length', e.target.value)}
            className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Used when the field has no detectable <code>maxlength</code>.</p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Autofill Prompt</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={10}
            defaultValue={settings.autofill_prompt || ''}
            onBlur={e => saveSetting('autofill_prompt', e.target.value)}
            placeholder="Application autofill generation prompt template..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Placeholders: {'{persona} {qa_bank} {company} {position} {question} {max_chars}'}
          </p>
        </div>

        <hr className="border-gray-200 dark:border-gray-700 my-4" />
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Interview Prep Handover</h3>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
          The prep handover (Applications &rarr; <em>Generate prep handover for AI</em>) is assembled as four plain sections:
          the role, your r&eacute;sum&eacute;, the posting, and the closing ask below. No LLM call is made &mdash; you paste the block into the AI of your choice.
        </p>
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">What I Need From You</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={8}
            defaultValue={settings.prep_ask || ''}
            onBlur={e => saveSetting('prep_ask', e.target.value)}
            placeholder="What you want the AI to produce from the handover..."
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Plain text, no placeholders &mdash; appended verbatim as the last section.</p>
        </div>

        <hr className="border-gray-200 dark:border-gray-700 my-4" />
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Application Autofill (structured)</h3>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">Fills known-answer fields directly from field/option dictionaries — no LLM call for matched fields. Unmatched free-text questions still fall back to the generated flow above. On/off and the fill trigger (one-click vs. on page load) live in the extension popup.</p>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Field Patterns (JSON)</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={8}
            defaultValue={typeof settings.autofill_field_patterns === 'string' ? settings.autofill_field_patterns : JSON.stringify(settings.autofill_field_patterns || {}, null, 2)}
            onBlur={e => { try { saveSetting('autofill_field_patterns', JSON.parse(e.target.value)) } catch { alert('Field patterns must be valid JSON') } }}
            placeholder='{"first_name": ["first name", "given name"]}'
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Maps a known field key to the label/placeholder text patterns used to detect it on application forms.</p>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Option Synonyms (JSON)</label>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm font-mono dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
            rows={8}
            defaultValue={typeof settings.autofill_option_synonyms === 'string' ? settings.autofill_option_synonyms : JSON.stringify(settings.autofill_option_synonyms || {}, null, 2)}
            onBlur={e => { try { saveSetting('autofill_option_synonyms', JSON.parse(e.target.value)) } catch { alert('Option synonyms must be valid JSON') } }}
            placeholder='{"yes": ["yes", "y", "true"]}'
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Maps a canonical answer value to the synonym text used to match dropdown/radio options on application forms.</p>
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
                    <option value="openrouter">OpenRouter</option>
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
        <div className="mt-3">
          <button onClick={() => triggerAction('/telegram/test')}
            disabled={triggerStatus['/telegram/test'] === 'running'}
            className={`inline-flex items-center gap-2 px-3 py-2 text-sm border dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200 ${triggerStatus['/telegram/test'] === 'running' ? 'opacity-50' : ''} ${triggerStatus['/telegram/test'] === 'done' ? 'bg-green-50 border-green-300 dark:bg-green-900/30' : ''}`}>
            <Send size={14} />
            {triggerStatus['/telegram/test'] === 'running' ? 'Sending…' : triggerStatus['/telegram/test'] === 'done' ? 'Sent!' : 'Send Test Telegram'}
          </button>
        </div>
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="mb-2 px-3 py-2 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded text-xs text-blue-900 dark:text-blue-200">
            <b>Optional.</b> Outbound alerts and the daily digest work without any webhook configured.
            Only set this up if you want the inline <b>Apply / Skip</b> buttons in Telegram messages
            to call back into this app. Requires a public HTTPS URL (Tailscale Funnel, Cloudflare Tunnel,
            ngrok, etc.) — it won't work on a LAN-only install.
          </div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Webhook Secret <span className="font-normal text-gray-400">(validates every Telegram → backend call)</span>
          </label>
          <div className="flex gap-2 items-start">
            <input type="text" readOnly
              value={settings.telegram_webhook_secret === '\u2022\u2022\u2022\u2022\u2022\u2022' ? 'Set (hidden — rotate to view)' : (settings.telegram_webhook_secret || 'Not set')}
              className="flex-1 border rounded px-2 py-1.5 text-sm font-mono text-xs bg-gray-50 dark:bg-gray-900 dark:text-gray-200 dark:border-gray-600" />
            <button
              onClick={async () => {
                if (!confirm('Rotate webhook secret? You must re-register the webhook afterward.')) return;
                const r = await api.post('/telegram/rotate-webhook-secret');
                if (r.data?.webhook_secret) {
                  window.prompt('Copy the new secret now — it will not be shown again:', r.data.webhook_secret);
                }
              }}
              className="px-3 py-1.5 text-xs font-medium bg-amber-500 hover:bg-amber-600 text-white rounded">
              Rotate
            </button>
            <button
              onClick={async () => {
                const url = prompt('Public base URL (https://...):');
                if (!url) return;
                const r = await api.post('/telegram/register-webhook', { public_url: url });
                alert(r.data?.ok ? 'Webhook registered' : `Failed: ${r.data?.description || r.data?.error || 'unknown error'}`);
              }}
              className="px-3 py-1.5 text-xs font-medium bg-blue-500 hover:bg-blue-600 text-white rounded">
              Register
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            Telegram sends this as <code className="font-mono text-[10px]">X-Telegram-Bot-Api-Secret-Token</code> on every webhook call; mismatched headers return 401.
          </p>
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

      </>)}
    </div>
  )
}
