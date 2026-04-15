import React, { useState, useEffect, useCallback } from 'react'
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd'
import api from '../api'
import { Trash2, X } from 'lucide-react'

const COLUMNS = [
  { id: 'applied', label: 'Applied', color: 'bg-blue-500' },
  { id: 'interview', label: 'Interview', color: 'bg-amber-500' },
  { id: 'offer', label: 'Offer', color: 'bg-green-500' },
  { id: 'rejected', label: 'Rejected', color: 'bg-red-500' },
]

// Map removed statuses into visible columns
const STATUS_REMAP = {
  screening: 'applied',
  phone_screen: 'interview',
  final_round: 'interview',
}

const COMPANY_STORAGE_KEY = 'appboard_company_filter'

export default function ApplicationBoard() {
  const [apps, setApps] = useState([])
  const [editingApp, setEditingApp] = useState(null)
  const [cachedPageJob, setCachedPageJob] = useState(null) // {job_id, title, company}
  const [loading, setLoading] = useState(true)
  const [companyFilter, setCompanyFilter] = useState(() => {
    try {
      const raw = localStorage.getItem(COMPANY_STORAGE_KEY)
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })

  const fetchApps = useCallback(async () => {
    try {
      const { data } = await api.get('/applications', { params: { limit: 200 } })
      setApps(data.applications)
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [])

  useEffect(() => { fetchApps() }, [fetchApps])

  useEffect(() => {
    try { localStorage.setItem(COMPANY_STORAGE_KEY, JSON.stringify(companyFilter)) } catch {}
  }, [companyFilter])

  const onDragEnd = async (result) => {
    if (!result.destination) return
    const appId = result.draggableId
    const newStatus = result.destination.droppableId

    // Optimistic update
    setApps(prev => prev.map(a => a.id === appId ? { ...a, status: newStatus } : a))

    try {
      await api.patch(`/applications/${appId}`, { status: newStatus })
    } catch (e) {
      console.error(e)
      fetchApps() // Revert on error
    }
  }

  const updateApp = async (appId, updates) => {
    try {
      await api.patch(`/applications/${appId}`, updates)
      fetchApps()
      setEditingApp(null)
    } catch (e) { console.error(e) }
  }

  const deleteApp = async (appId) => {
    try {
      await api.delete(`/applications/${appId}`)
      setEditingApp(null)
      fetchApps()
    } catch (e) { console.error(e) }
  }

  // Build case-insensitive company map and classify rejected-only companies
  const { activeCompanies, rejectedOnlyKeys } = React.useMemo(() => {
    const displayMap = {} // lowercase → first-seen display name
    const statusSets = {} // lowercase → Set of mapped statuses
    apps.forEach(a => {
      if (!a.company) return
      const key = a.company.toLowerCase()
      if (!displayMap[key]) displayMap[key] = a.company
      if (!statusSets[key]) statusSets[key] = new Set()
      statusSets[key].add(STATUS_REMAP[a.status] || a.status)
    })
    const active = []
    const rejOnly = new Set()
    Object.entries(statusSets).forEach(([key, statuses]) => {
      if (statuses.size === 1 && statuses.has('rejected')) {
        rejOnly.add(key)
      } else {
        active.push({ key, display: displayMap[key] })
      }
    })
    active.sort((a, b) => a.display.localeCompare(b.display))
    return { activeCompanies: active, rejectedOnlyKeys: rejOnly }
  }, [apps])

  const toggleCompany = (key) => {
    setCompanyFilter(prev => prev.includes(key) ? prev.filter(x => x !== key) : [...prev, key])
  }

  // Auto-prune stale company selections
  const allValidKeys = React.useMemo(() => {
    const keys = new Set(activeCompanies.map(c => c.key))
    if (rejectedOnlyKeys.size > 0) keys.add('__rejected_only__')
    return keys
  }, [activeCompanies, rejectedOnlyKeys])

  useEffect(() => {
    if (companyFilter.length && allValidKeys.size) {
      const valid = companyFilter.filter(c => allValidKeys.has(c))
      if (valid.length !== companyFilter.length) setCompanyFilter(valid)
    }
  }, [allValidKeys])

  const filteredApps = companyFilter.length
    ? apps.filter(a => {
        const key = (a.company || '').toLowerCase()
        if (companyFilter.includes(key)) return true
        if (companyFilter.includes('__rejected_only__') && rejectedOnlyKeys.has(key)) return true
        return false
      })
    : apps

  const grouped = COLUMNS.reduce((acc, col) => {
    acc[col.id] = filteredApps.filter(a => (STATUS_REMAP[a.status] || a.status) === col.id)
    return acc
  }, {})

  const daysSince = (dateStr) => {
    if (!dateStr) return null
    const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000)
    return days
  }

  if (loading) return <div className="p-6 text-center text-gray-500 dark:text-gray-400">Loading applications...</div>

  return (
    <div className="p-6 h-full">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Application Board</h1>
        <span className="text-sm text-gray-500 dark:text-gray-400">{filteredApps.length} of {apps.length} applications</span>
      </div>

      {/* Company filter */}
      {(activeCompanies.length > 0 || rejectedOnlyKeys.size > 0) && (
        <div className="flex flex-wrap gap-1 mb-3">
          {activeCompanies.map(c => (
            <button key={c.key} onClick={() => toggleCompany(c.key)}
              className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                companyFilter.includes(c.key) ? 'bg-indigo-100 border-indigo-300 text-indigo-800 dark:bg-indigo-900 dark:border-indigo-700 dark:text-indigo-200' : 'bg-white dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
              }`}>{c.display}</button>
          ))}
          {rejectedOnlyKeys.size > 0 && (
            <button onClick={() => toggleCompany('__rejected_only__')}
              className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                companyFilter.includes('__rejected_only__') ? 'bg-red-100 border-red-300 text-red-800 dark:bg-red-900 dark:border-red-700 dark:text-red-200' : 'bg-white dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
              }`}>Other - Rejected ({rejectedOnlyKeys.size})</button>
          )}
          {companyFilter.length > 0 && (
            <button onClick={() => setCompanyFilter([])}
              className="px-2 py-0.5 text-xs rounded-full text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">Clear</button>
          )}
        </div>
      )}

      {/* Cached page modal */}
      {cachedPageJob && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setCachedPageJob(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[900px] h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b dark:border-gray-600 flex-shrink-0">
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate">{cachedPageJob.title}</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">{cachedPageJob.company}</p>
              </div>
              <button onClick={() => setCachedPageJob(null)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 p-1 ml-3 flex-shrink-0">
                <X size={18} />
              </button>
            </div>
            <iframe
              src={`/api/jobs/${cachedPageJob.job_id}/cached-page`}
              className="flex-1 w-full border-0 rounded-b-xl"
              title="Cached job page"
            />
          </div>
        </div>
      )}

      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-3 overflow-x-auto pb-4 h-[calc(100vh-150px)]">
          {COLUMNS.map(col => (
            <div key={col.id} className="flex-shrink-0 w-96">
              <div className={`${col.color} text-white px-3 py-2 rounded-t-lg text-sm font-medium flex justify-between`}>
                {col.label}
                <span className="bg-white/20 px-1.5 rounded text-xs">{grouped[col.id]?.length || 0}</span>
              </div>
              <Droppable droppableId={col.id}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`bg-gray-100 dark:bg-gray-800 rounded-b-lg p-2 min-h-[200px] max-h-[calc(100vh-230px)] overflow-y-auto ${
                      snapshot.isDraggingOver ? 'bg-blue-50 dark:bg-blue-900/40' : ''
                    }`}
                  >
                    {(grouped[col.id] || []).map((app, index) => {
                      const days = daysSince(app.updated_at)
                      const mapped = STATUS_REMAP[app.status] || app.status
                      const isStale = days !== null && days > 7 && !['offer', 'rejected'].includes(mapped)
                      const isRejected = mapped === 'rejected'

                      return (
                        <Draggable key={app.id} draggableId={app.id} index={index}>
                          {(provided) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              onClick={() => setEditingApp(editingApp?.id === app.id ? null : app)}
                              className={`bg-white dark:bg-gray-700 rounded-lg p-3 mb-2 shadow-sm cursor-pointer hover:shadow border-l-4 ${
                                isRejected ? 'border-l-red-400' : isStale ? 'border-l-yellow-400' : 'border-l-green-400'
                              }`}
                            >
                              <div className="flex items-center gap-1.5">
                                {app.short_id && <span className="text-[10px] text-gray-400 dark:text-gray-500 font-mono">#{app.short_id}</span>}
                                <p className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate" title={app.title || 'Unknown Role'}>{app.title || 'Unknown Role'}</p>
                              </div>
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{app.company || 'Unknown Company'}</p>
                              <div className="flex items-center gap-2 mt-1.5">
                                {app.cv_version_used && (
                                  <span className="text-xs bg-blue-50 text-blue-700 dark:bg-blue-900 dark:text-blue-300 px-1.5 py-0.5 rounded">{app.cv_version_used}</span>
                                )}
                                {days !== null && (
                                  <span className={`text-xs ${isStale ? 'text-yellow-600 dark:text-yellow-400' : 'text-gray-400 dark:text-gray-500'}`}>{days}d ago</span>
                                )}
                              </div>

                              {editingApp?.id === app.id && (
                                <div className="mt-3 pt-2 border-t dark:border-gray-600" onClick={e => e.stopPropagation()}>
                                  <textarea
                                    className="w-full text-xs border rounded p-1.5 mb-1.5 dark:bg-gray-600 dark:text-gray-200 dark:border-gray-500"
                                    placeholder="Notes..."
                                    defaultValue={app.notes || ''}
                                    onBlur={e => updateApp(app.id, { notes: e.target.value })}
                                    rows={2}
                                  />
                                  {app.last_email_snippet && (
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">Last email: {app.last_email_snippet}</p>
                                  )}
                                  <div className="flex items-center gap-3 mt-2">
                                    {app.job_id && (
                                      <button
                                        onClick={() => setCachedPageJob({ job_id: app.job_id, title: app.title, company: app.company })}
                                        className="text-xs text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-300 font-medium">
                                        Cached
                                      </button>
                                    )}
                                    {app.url && (
                                      <a href={app.url} target="_blank" rel="noopener noreferrer"
                                        className="text-xs text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 font-medium">Live</a>
                                    )}
                                    <button
                                      onClick={() => { if (confirm('Delete this application?')) deleteApp(app.id) }}
                                      className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 ml-auto">
                                      <Trash2 size={12} /> Delete
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </Draggable>
                      )
                    })}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          ))}
        </div>
      </DragDropContext>
    </div>
  )
}
