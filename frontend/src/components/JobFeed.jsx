import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api'
import { ExternalLink, Bookmark, X, CheckCircle, ChevronDown, ChevronUp, Filter, Ban, Info, FileText, Loader2, ScrollText, RotateCw } from 'lucide-react'

const STORAGE_KEY = 'jobfeed_filters'

const H1B_BADGES = {
  likely: { bg: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300', label: 'H-1B Likely' },
  possible: { bg: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300', label: 'H-1B Possible' },
  unlikely: { bg: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300', label: 'H-1B Unlikely' },
  unknown: { bg: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400', label: 'H-1B Unknown' },
}

const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  saved: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  applied: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  skip: 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-300',
  ignored: 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400',
}

const DEFAULT_FILTERS = {
  status: ['new'], company: [], min_score: '', h1b_verdict: [],
  source: [], saved: '',
}

function loadFilters() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      return { ...DEFAULT_FILTERS, ...saved }
    }
  } catch {}
  return DEFAULT_FILTERS
}

function saveFilters(filters) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(filters)) } catch {}
}

function capitalize(s) {
  if (!s) return s
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const timeAgo = (dateStr) => {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function JobFeed() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(loadFilters)
  const [showFilters, setShowFilters] = useState(() => {
    try { return localStorage.getItem('jobfeed_filters_panel') === 'true' } catch { return false }
  })
  const [selectedJob, setSelectedJob] = useState(null)
  const [viewCached, setViewCached] = useState(false)
  const [companyList, setCompanyList] = useState(null)
  const [sourceList, setSourceList] = useState(null)
  const [verdictList, setVerdictList] = useState(null)
  const [offset, setOffset] = useState(0)
  const limit = 30
  const listRef = useRef(null)

  // Rescore modal state
  const [rescoreJob, setRescoreJob] = useState(null)
  const [rescoreOptions, setRescoreOptions] = useState([])  // [{id, name}], 'persona' included when available
  const [selectedRescoreIds, setSelectedRescoreIds] = useState([])
  const [rescoring, setRescoring] = useState(false)
  const [rescoreDepth, setRescoreDepth] = useState('full')

  // #13 Debounce filter changes
  const filterTimerRef = useRef(null)

  // #14 Keyboard shortcuts
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const cardRefs = useRef({})

  // #15 Text search
  const [titleSearch, setTitleSearch] = useState('')
  const titleSearchTimerRef = useRef(null)
  const [debouncedTitleSearch, setDebouncedTitleSearch] = useState('')

  // #16 Sort controls
  const [sortBy, setSortBy] = useState('date')

  // #17 Bulk operations
  const [selectedIds, setSelectedIds] = useState(new Set())

  // #20 Undo toast
  const [undoToast, setUndoToast] = useState(null)

  // Score tooltip and report modal
  const [tooltipJob, setTooltipJob] = useState(null)
  const [reportJob, setReportJob] = useState(null)
  const [reportCv, setReportCv] = useState(null) // which CV's report to show

  // CV generation modal
  const [showCvModal, setShowCvModal] = useState(false)
  const [cvBaseResumes, setCvBaseResumes] = useState([])
  const [cvSelectedBase, setCvSelectedBase] = useState('')
  const [cvGenerating, setCvGenerating] = useState(false)
  const [cvMode, setCvMode] = useState('tailor') // 'tailor' or 'copy'

  // Tailor background toasts
  const [tailorToasts, setTailorToasts] = useState([])

  // #22 Additional filters
  const [minSalary, setMinSalary] = useState('')
  const [maxSalary, setMaxSalary] = useState('')

  const renderSlot = (job, type, label, idleContent) => {
    const isRunning = (job.in_flight || []).includes(type)
    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
          <Loader2 className="animate-spin" size={12} />
          {label}…
        </span>
      )
    }
    return idleContent
  }

  // #15 Debounce title search input
  useEffect(() => {
    if (titleSearchTimerRef.current) clearTimeout(titleSearchTimerRef.current)
    titleSearchTimerRef.current = setTimeout(() => {
      setDebouncedTitleSearch(titleSearch)
    }, 500)
    return () => { if (titleSearchTimerRef.current) clearTimeout(titleSearchTimerRef.current) }
  }, [titleSearch])

  // #13 Debounced filter list fetching
  useEffect(() => {
    if (filterTimerRef.current) clearTimeout(filterTimerRef.current)
    filterTimerRef.current = setTimeout(() => {
      const params = {}
      if (filters.status.length) params.status = filters.status.join(',')
      if (filters.source.length) params.source = filters.source.join(',')
      if (filters.h1b_verdict.length) params.h1b_verdict = filters.h1b_verdict.join(',')
      if (filters.min_score !== '') params.min_score = filters.min_score
      if (filters.saved !== '') params.saved = filters.saved
      if (debouncedTitleSearch) params.title_search = debouncedTitleSearch

      if (minSalary) params.min_salary = Number(minSalary) * 1000
      if (maxSalary) params.max_salary = Number(maxSalary) * 1000

      api.get('/jobs/companies/list', { params }).then(({ data }) => setCompanyList(data)).catch(() => {})

      const srcParams = {}
      if (filters.status.length) srcParams.status = filters.status.join(',')
      if (filters.company.length) srcParams.company = filters.company.join(',')
      if (filters.h1b_verdict.length) srcParams.h1b_verdict = filters.h1b_verdict.join(',')
      if (filters.min_score !== '') srcParams.min_score = filters.min_score
      if (filters.saved !== '') srcParams.saved = filters.saved
      if (debouncedTitleSearch) srcParams.title_search = debouncedTitleSearch

      if (minSalary) srcParams.min_salary = Number(minSalary) * 1000
      if (maxSalary) srcParams.max_salary = Number(maxSalary) * 1000

      api.get('/jobs/sources/list', { params: srcParams }).then(({ data }) => setSourceList(data)).catch(() => {})

      const vParams = {}
      if (filters.status.length) vParams.status = filters.status.join(',')
      if (filters.company.length) vParams.company = filters.company.join(',')
      if (filters.source.length) vParams.source = filters.source.join(',')
      if (filters.min_score !== '') vParams.min_score = filters.min_score
      if (filters.saved !== '') vParams.saved = filters.saved
      if (debouncedTitleSearch) vParams.title_search = debouncedTitleSearch

      if (minSalary) vParams.min_salary = Number(minSalary) * 1000
      if (maxSalary) vParams.max_salary = Number(maxSalary) * 1000

      api.get('/jobs/verdicts/list', { params: vParams }).then(({ data }) => setVerdictList(data)).catch(() => {})
    }, 300)
    return () => { if (filterTimerRef.current) clearTimeout(filterTimerRef.current) }
  }, [filters.status, filters.source, filters.company, filters.h1b_verdict, filters.min_score, filters.saved, debouncedTitleSearch, minSalary, maxSalary])

  // Auto-clear stale filter values not present in dynamic lists
  useEffect(() => {
    if (sourceList !== null && filters.source.length) {
      const valid = filters.source.filter(s => sourceList.includes(s))
      if (valid.length !== filters.source.length) setFilters(f => ({ ...f, source: valid }))
    }
  }, [sourceList])
  useEffect(() => {
    if (companyList !== null && filters.company.length) {
      const valid = filters.company.filter(c => companyList.includes(c))
      if (valid.length !== filters.company.length) setFilters(f => ({ ...f, company: valid }))
    }
  }, [companyList])
  useEffect(() => {
    if (verdictList !== null && filters.h1b_verdict.length) {
      const valid = filters.h1b_verdict.filter(v => verdictList.includes(v))
      if (valid.length !== filters.h1b_verdict.length) setFilters(f => ({ ...f, h1b_verdict: valid }))
    }
  }, [verdictList])

  // Persist filters to localStorage
  useEffect(() => { saveFilters(filters) }, [filters])

  // Persist filter panel open/closed
  useEffect(() => {
    try { localStorage.setItem('jobfeed_filters_panel', String(showFilters)) } catch {}
  }, [showFilters])

  const fetchJobs = useCallback(async () => {
    const scrollTop = listRef.current?.scrollTop ?? 0
    setLoading(true)
    try {
      const params = { limit, offset }
      if (filters.status.length) params.status = filters.status.join(',')
      if (filters.company.length) params.company = filters.company.join(',')
      if (filters.source.length) params.source = filters.source.join(',')
      if (filters.h1b_verdict.length) params.h1b_verdict = filters.h1b_verdict.join(',')
      if (filters.min_score !== '') params.min_score = filters.min_score
      if (filters.saved !== '') params.saved = filters.saved
      if (debouncedTitleSearch) params.title_search = debouncedTitleSearch
      if (sortBy !== 'date') params.sort_by = sortBy

      if (minSalary) params.min_salary = Number(minSalary) * 1000
      if (maxSalary) params.max_salary = Number(maxSalary) * 1000

      const { data } = await api.get('/jobs', { params })
      setJobs(data.jobs)
      setTotal(data.total)
      // Restore scroll position after re-render
      requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = scrollTop
      })
    } catch (e) {
      console.error('Failed to load jobs:', e)
    }
    setLoading(false)
  }, [filters, offset, debouncedTitleSearch, sortBy, minSalary, maxSalary])

  useEffect(() => { fetchJobs() }, [fetchJobs])

  // Poll /monitor/in-flight while any visible job has an active op.
  // Bails out immediately when no cards are running, so there's zero
  // network/CPU cost in the idle state.
  useEffect(() => {
    const activeIds = jobs
      .filter(j => (j.in_flight || []).length > 0)
      .map(j => j.id)
    if (activeIds.length === 0) return  // nothing running, no poll

    let cancelled = false
    const tick = async () => {
      try {
        const { data } = await api.get('/monitor/in-flight', {
          params: { job_ids: activeIds.join(',') },
        })
        if (cancelled) return

        // Which jobs finished? (were running, now absent from response)
        const finished = activeIds.filter(id => !data[id])
        if (finished.length > 0) {
          // Re-fetch each finished job so scores/tailored_id land in state
          await Promise.all(finished.map(async id => {
            try {
              const { data: jobData } = await api.get(`/jobs/${id}`)
              setJobs(prev => prev.map(j => j.id === id ? jobData : j))
            } catch {/* skip */}
          }))
        }
        // For still-active ones, patch in_flight in place
        setJobs(prev => prev.map(j => {
          if (data[j.id]) return { ...j, in_flight: data[j.id] }
          if (finished.includes(j.id)) return j  // already refreshed above
          return j
        }))
      } catch {/* network hiccup — next tick retries */}
    }

    const handle = setInterval(tick, 3000)
    tick()  // fire once immediately
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [jobs.map(j => (j.in_flight || []).length > 0 ? j.id : null).filter(Boolean).join(',')])
  // Re-subscribe only when the set of active IDs actually changes

  // Deep-link: ?job=<id> opens that job's detail panel
  useEffect(() => {
    const jobId = searchParams.get('job')
    if (jobId && !selectedJob) {
      api.get(`/jobs/${jobId}`).then(({ data }) => {
        setSelectedJob(data)
        setViewCached(!!data.has_cached_page)
        setSearchParams({}, { replace: true })
      }).catch(() => {})
    }
  }, [searchParams])

  // #14 Keyboard shortcuts — use refs so listener is stable (never torn down on re-render)
  const jobsRef = useRef(jobs)
  const fetchJobsRef = useRef(fetchJobs)
  const showUndoRef = useRef(null)
  const selectedIndexRef = useRef(selectedIndex)
  useEffect(() => { jobsRef.current = jobs }, [jobs])
  useEffect(() => { fetchJobsRef.current = fetchJobs }, [fetchJobs])
  useEffect(() => { selectedIndexRef.current = selectedIndex }, [selectedIndex])

  const selectJobAt = useCallback((idx) => {
    const jobs = jobsRef.current
    if (idx >= 0 && idx < jobs.length) {
      setSelectedIndex(idx)
      setSelectedJob(jobs[idx])
      setViewCached(jobs[idx].has_cached_page && jobs[idx].status === 'applied')
    }
  }, [])

  useEffect(() => {
    const handler = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      if (e.target.closest('iframe')) return
      const currentJobs = jobsRef.current
      const idx = selectedIndexRef.current
      switch (e.key) {
        case 'f':
        case 'j':
        case 'ArrowDown': {
          e.preventDefault()
          const next = Math.min((idx ?? -1) + 1, currentJobs.length - 1)
          selectJobAt(next)
          break
        }
        case 'g':
        case 'k':
        case 'ArrowUp': {
          e.preventDefault()
          const next = Math.max((idx ?? 1) - 1, 0)
          selectJobAt(next)
          break
        }
        case 's': {
          if (idx === null || idx < 0 || idx >= currentJobs.length) break
          const job = currentJobs[idx]
          const newSaved = !job.saved
          const newStatus = newSaved ? 'saved' : 'new'
          // Advance to next job immediately
          if (idx + 1 < currentJobs.length) selectJobAt(idx + 1)
          api.patch(`/jobs/${job.id}`, { saved: newSaved, status: newStatus }).then(() => {
            fetchJobsRef.current()
          }).catch(console.error)
          break
        }
        case 'x': {
          if (idx === null || idx < 0 || idx >= currentJobs.length) break
          const job = currentJobs[idx]
          // Advance to next job immediately (before API call)
          const nextJob = idx < currentJobs.length - 1 ? currentJobs[idx + 1] : null
          if (nextJob) {
            selectJobAt(idx + 1)
          }
          showUndoRef.current(job.id, job.status, job.saved, `Skipped "${job.title}"`)
          api.patch(`/jobs/${job.id}`, { status: 'skip' }).then(() => {
            fetchJobsRef.current()
            // After refetch, the skipped job is gone, so adjust index back
            if (nextJob) {
              selectedIndexRef.current = idx
            }
          }).catch(console.error)
          break
        }
        case 'e':
        case 'o': {
          if (idx !== null && idx >= 0 && idx < currentJobs.length) {
            const job = currentJobs[idx]
            if (job.url) window.open(job.url, '_blank', 'noopener,noreferrer')
          }
          break
        }
        case 'Enter': {
          e.preventDefault()
          if (idx !== null && idx >= 0 && idx < currentJobs.length) {
            const job = currentJobs[idx]
            setSelectedJob(prev => prev?.id === job.id ? null : job)
            setViewCached(job.has_cached_page && job.status === 'applied')
          }
          break
        }
        default:
          break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // #14 Auto-scroll selected card into view
  useEffect(() => {
    if (selectedIndex !== null && cardRefs.current[selectedIndex]) {
      cardRefs.current[selectedIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [selectedIndex])

  // Reset selectedIndex when jobs change
  useEffect(() => {
    setSelectedIndex(prev => {
      if (prev !== null && prev >= jobs.length) return jobs.length > 0 ? jobs.length - 1 : null
      return prev
    })
    setSelectedIds(new Set())
  }, [jobs])

  const toggleFilter = (key, value) => {
    setOffset(0)
    setFilters(prev => {
      const arr = prev[key]
      return { ...prev, [key]: arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value] }
    })
  }

  const updateJob = async (jobId, updates) => {
    try {
      await api.patch(`/jobs/${jobId}`, updates)
      fetchJobs()
    } catch (e) { console.error(e) }
  }

  const advanceToNext = (job) => {
    const idx = jobs.findIndex(j => j.id === job.id)
    const next = idx >= 0 && idx < jobs.length - 1 ? jobs[idx + 1] : null
    if (next) {
      setSelectedJob(next)
      setViewCached(next.has_cached_page && next.status === 'applied')
    } else if (selectedJob?.id === job.id) {
      setSelectedJob(null)
    }
  }

  // #20 Undo toast helpers
  const showUndo = (jobId, prevStatus, prevSaved, message) => {
    if (undoToast?.timer) clearTimeout(undoToast.timer)
    const timer = setTimeout(() => setUndoToast(null), 5000)
    setUndoToast({ jobId, prevStatus, prevSaved, message, timer })
  }
  showUndoRef.current = showUndo

  const handleUndo = async () => {
    if (!undoToast) return
    clearTimeout(undoToast.timer)
    await api.patch(`/jobs/${undoToast.jobId}`, { status: undoToast.prevStatus, saved: undoToast.prevSaved })
    setUndoToast(null)
    fetchJobs()
  }

  const generateCv = async () => {
    if (!cvSelectedBase || !selectedJob) return
    const jobId = selectedJob.id
    const company = selectedJob.company || 'Unknown'

    if (cvMode === 'copy') {
      // Copy is fast — keep synchronous redirect
      setCvGenerating(true)
      try {
        const { data } = await api.post('/resumes/copy', { base_resume_id: cvSelectedBase, job_id: jobId })
        setShowCvModal(false)
        setCvSelectedBase('')
        window.location.href = `/resumes?resume=${data.id}`
      } catch (e) {
        alert('Copy failed: ' + (e.response?.data?.detail || e.message))
      }
      setCvGenerating(false)
      return
    }

    // Tailor — background; endpoint returns 202 + run_id immediately.
    const toastId = Date.now()
    setTailorToasts(prev => [...prev, { id: toastId, company, status: 'loading' }])
    setShowCvModal(false)
    setCvSelectedBase('')

    api.post('/resumes/tailor', { base_resume_id: cvSelectedBase, job_id: jobId })
      .then(() => {
        // No payload to use — the tailored Resume appears once the background
        // job completes. The card polling loop (Task 9) picks it up.
        setTailorToasts(prev => prev.map(t => t.id === toastId ? { ...t, status: 'running' } : t))
        // optimistic refresh after a moment so the spinner badge shows
        setTimeout(() => fetchJobs(), 500)
      })
      .catch(e => {
        const msg = e.response?.data?.detail || e.message
        setTailorToasts(prev => prev.map(t => t.id === toastId ? { ...t, status: 'error', error: msg } : t))
        setTimeout(() => setTailorToasts(prev => prev.filter(t => t.id !== toastId)), 10000)
      })
  }

  const skipAndAdvance = async (e, job) => {
    e.stopPropagation()
    const prevStatus = job.status
    const prevSaved = job.saved
    advanceToNext(job)
    showUndo(job.id, prevStatus, prevSaved, `Skipped "${job.title}"`)
    try {
      await api.patch(`/jobs/${job.id}`, { status: 'skip' })
      fetchJobs()
    } catch (e) { console.error(e) }
  }

  const saveAndAdvance = async (e, job) => {
    e.stopPropagation()
    advanceToNext(job)
    try {
      await api.patch(`/jobs/${job.id}`, { saved: !job.saved, status: job.saved ? 'new' : 'saved' })
      fetchJobs()
    } catch (e) { console.error(e) }
  }

  const applyJob = async (e, job) => {
    e.stopPropagation()
    const prevStatus = job.status
    const prevSaved = job.saved
    showUndo(job.id, prevStatus, prevSaved, `Applied to "${job.title}"`)
    await updateJob(job.id, { status: 'applied' })
  }

  const ignoreCompany = async (e, companyName) => {
    e.stopPropagation()
    if (!companyName || !confirm(`Add "${companyName}" to global ignore list?`)) return
    try {
      const { data: settings } = await api.get('/settings')
      const current = Array.isArray(settings.company_exclude_global) ? settings.company_exclude_global : []
      if (!current.some(c => c.toLowerCase() === companyName.toLowerCase())) {
        await api.patch('/settings', { company_exclude_global: [...current, companyName] })
      }
    } catch (err) { console.error(err) }
  }

  const formatSalary = (min, max) => {
    if (!min && !max) return null
    const fmt = (v) => `$${(v / 1000).toFixed(0)}K`
    if (min && max && min !== max) return `${fmt(min)} - ${fmt(max)}`
    return fmt(min || max)
  }

  const openRescoreModal = async (e, job) => {
    e.stopPropagation()
    setRescoreJob(job)
    setSelectedRescoreIds([])
    setRescoring(false)
    setRescoreDepth('full')
    try {
      const [resumesRes, personaRes, settingsRes] = await Promise.all([
        api.get('/resumes?is_base=true'),
        api.get('/persona').catch(() => ({ data: null })),
        api.get('/settings'),
      ])
      const opts = (resumesRes.data || []).map(r => ({ id: r.id, name: r.name }))
      const personaContent = personaRes.data?.resume_content || {}
      const personaPopulated = Object.keys(personaContent).length > 0
      if (personaPopulated) opts.push({ id: 'persona', name: 'Persona' })
      setRescoreOptions(opts)
      const defaultId = settingsRes.data?.default_resume_id
      if (defaultId && opts.some(o => o.id === defaultId)) {
        setSelectedRescoreIds([defaultId])
      } else {
        setSelectedRescoreIds(opts.map(o => o.id))
      }
    } catch (err) { console.error(err) }
  }

  const runRescore = async () => {
    if (!rescoreJob || selectedRescoreIds.length === 0) return
    setRescoring(true)
    try {
      await api.post(`/analyze/${rescoreJob.id}?depth=${rescoreDepth}`, { cv_ids: selectedRescoreIds })
      setRescoreJob(null)
      fetchJobs()
    } catch (err) { console.error(err) }
    setRescoring(false)
  }

  // #17 Bulk operations
  const toggleSelectJob = (e, jobId) => {
    e.stopPropagation()
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(jobId)) next.delete(jobId)
      else next.add(jobId)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === jobs.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(jobs.map(j => j.id)))
    }
  }

  const bulkAction = async (action) => {
    if (selectedIds.size === 0) return
    try {
      const updates = action === 'skip' ? { status: 'skip' } : { saved: true, status: 'saved' }
      await api.post('/jobs/bulk-update', { job_ids: [...selectedIds], updates })
      setSelectedIds(new Set())
      fetchJobs()
    } catch (e) { console.error(e) }
  }

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* Left panel — job list */}
      <div className={`flex flex-col ${selectedJob ? 'w-[420px]' : 'w-full'} flex-shrink-0 border-r dark:border-gray-700`}
        onMouseEnter={() => window.focus()}>
        <div className="p-4 border-b dark:border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Job Feed</h1>
                <div className="relative">
                  <button
                    onClick={() => setShowShortcuts(!showShortcuts)}
                    className="p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    title="Keyboard shortcuts"
                  >
                    <Info size={14} />
                  </button>
                  {showShortcuts && (
                    <div className="absolute left-0 top-7 z-50 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg p-3 w-48 text-xs">
                      <div className="font-semibold text-gray-700 dark:text-gray-200 mb-2">Keyboard Shortcuts</div>
                      {[
                        ['f / j / \u2193', 'Next job'],
                        ['g / k / \u2191', 'Previous job'],
                        ['s', 'Save / unsave'],
                        ['x', 'Skip job'],
                        ['e / o', 'Open job URL'],
                        ['Enter', 'Toggle detail panel'],
                      ].map(([key, desc]) => (
                        <div key={key} className="flex justify-between py-0.5">
                          <kbd className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded font-mono text-gray-600 dark:text-gray-300">{key}</kbd>
                          <span className="text-gray-500 dark:text-gray-400">{desc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">{total} jobs found</p>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => { setFilters(DEFAULT_FILTERS); setOffset(0); setTitleSearch(''); setDebouncedTitleSearch(''); setSortBy('date'); setMinSalary(''); setMaxSalary('') }}
                className="px-2 py-1 text-xs text-red-500 border border-red-200 rounded hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/30"
              >Reset</button>
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-white border rounded hover:bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-600"
              >
                <Filter size={12} /> {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            </div>
          </div>

          {showFilters && (
            <div className="space-y-2 mt-2">
              {/* Row 0: Search + Sort */}
              <div className="flex items-center gap-2">
                <input type="text" placeholder="Search titles..." value={titleSearch}
                  onChange={e => setTitleSearch(e.target.value)}
                  className="border rounded px-1.5 py-0.5 text-[11px] flex-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                <select value={sortBy} onChange={e => { setSortBy(e.target.value); setOffset(0) }}
                  className="border rounded px-1.5 py-0.5 text-[11px] dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                  <option value="date">Newest</option>
                  <option value="score">Top Score</option>
                  <option value="salary">Top Salary</option>
                  <option value="company">Company A-Z</option>
                </select>
              </div>
              {/* Row 1: Status, Source, H-1B, Score, Saved */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">Status</span>
                  {[
                    { value: 'new', label: 'New' },
                    { value: 'saved', label: 'Saved' },
                    { value: 'applied', label: 'Applied' },
                    { value: 'skip', label: 'Skip' },
                    { value: 'ignored', label: 'Ignored' },
                  ].map(opt => (
                    <button key={opt.value} onClick={() => toggleFilter('status', opt.value)}
                      className={`px-1.5 py-0.5 text-[11px] rounded border ${
                        filters.status.includes(opt.value) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600'
                      }`}>{opt.label}</button>
                  ))}
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">Source</span>
                  {(sourceList || []).map(src => {
                    const labels = { direct: 'Direct', extension: 'Extension', jobspy_linkedin: 'LinkedIn', jobspy_indeed: 'Indeed', jobspy_zip_recruiter: 'Zip', jobspy_google: 'Google', levels_fyi: 'Levels', linkedin_personal: 'LI Personal', linkedin_extension: 'LI Extension', jobright: 'Jobright', playwright_url: 'Playwright', playwright_direct: 'Career' }
                    return (
                    <button key={src} onClick={() => toggleFilter('source', src)}
                      className={`px-1.5 py-0.5 text-[11px] rounded border ${
                        filters.source.includes(src) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600'
                      }`}>{labels[src] || src}</button>
                    )
                  })}
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">H-1B</span>
                  {['likely', 'possible', 'unlikely', 'unknown'].filter(v => (verdictList || []).includes(v)).map(v => (
                    <button key={v} onClick={() => toggleFilter('h1b_verdict', v)}
                      className={`px-1.5 py-0.5 text-[11px] rounded border ${
                        filters.h1b_verdict.includes(v) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600'
                      }`}>{capitalize(v)}</button>
                  ))}
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">Score≥</span>
                  <input type="number" placeholder="0" value={filters.min_score}
                    onChange={e => { setFilters({...filters, min_score: e.target.value}); setOffset(0) }}
                    className="border rounded px-1.5 py-0.5 text-[11px] w-12 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">Salary</span>
                  <input type="number" placeholder="Min $K" value={minSalary}
                    onChange={e => { setMinSalary(e.target.value); setOffset(0) }}
                    className="border rounded px-1.5 py-0.5 text-[11px] w-16 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                  <span className="text-[11px] text-gray-400 dark:text-gray-500">-</span>
                  <input type="number" placeholder="Max $K" value={maxSalary}
                    onChange={e => { setMaxSalary(e.target.value); setOffset(0) }}
                    className="border rounded px-1.5 py-0.5 text-[11px] w-16 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
                </div>
              </div>

              {/* Row 2: Company */}
              <div>
                <span className="text-[10px] text-gray-400 dark:text-gray-500 mr-1">Company</span>
                <div className="flex flex-wrap gap-1 mt-0.5 max-h-20 overflow-y-auto">
                  {(companyList || []).map(c => (
                    <button key={c} onClick={() => toggleFilter('company', c)}
                      className={`px-1.5 py-0.5 text-[11px] rounded border ${
                        filters.company.includes(c) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600'
                      }`}>{c}</button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Job cards */}
        <div ref={listRef} className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400 text-sm">Loading jobs...</div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400 text-sm">No jobs found.</div>
          ) : (
            <div>
              {/* #17 Select all header */}
              <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-gray-50 text-xs text-gray-500 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400">
                <input type="checkbox" checked={jobs.length > 0 && selectedIds.size === jobs.length}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-300 dark:border-gray-600" />
                <span>Select all</span>
              </div>
              {jobs.map((job, idx) => {
                const isDetailSelected = selectedJob?.id === job.id
                return (
                  <div
                    key={job.id}
                    ref={el => cardRefs.current[idx] = el}
                    onClick={() => { setSelectedJob(isDetailSelected ? null : job); setViewCached(job.has_cached_page && job.status === 'applied'); setSelectedIndex(idx) }}
                    className={`p-3 border-b dark:border-gray-700 cursor-pointer transition-colors ${
                      isDetailSelected ? 'bg-blue-50 border-l-4 border-l-blue-500 shadow-inner dark:bg-blue-900/30 dark:border-l-blue-400' :
                      'hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    <div className="flex items-stretch justify-between gap-2">
                      {/* #17 Checkbox */}
                      <div className="flex items-start pt-0.5 mr-1 self-start">
                        <input type="checkbox" checked={selectedIds.has(job.id)}
                          onChange={e => toggleSelectJob(e, job.id)}
                          onClick={e => e.stopPropagation()}
                          className="rounded border-gray-300 dark:border-gray-600" />
                      </div>
                      <div className="flex-1 min-w-0 flex flex-col">
                        <div>
                          {/* Title row with skip button */}
                          <div className="flex items-center gap-1.5">
                            <p className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate flex-1">{job.title}</p>
                            <div className="flex items-center gap-2 flex-shrink-0 ml-1">
                              {renderSlot(job, 'tailor_resume', 'Tailoring',
                                job.tailored_resume_id ? (
                                  <a href={`/resumes?resume=${job.tailored_resume_id}`} onClick={e => e.stopPropagation()}
                                    className="px-1.5 py-0.5 rounded text-purple-500 hover:text-purple-700 hover:bg-purple-50 dark:text-purple-400 dark:hover:text-purple-300 dark:hover:bg-purple-900/30"
                                    title="Tailored CV available">
                                    <ScrollText size={14} />
                                  </a>
                                ) : null
                              )}
                              <button onClick={e => skipAndAdvance(e, job)}
                                className="px-1.5 py-0.5 rounded bg-red-50 hover:bg-red-200 text-red-500 hover:text-red-700 transition-colors dark:bg-red-900/30 dark:hover:bg-red-900/50 dark:text-red-400 dark:hover:text-red-300"
                                title="Skip">
                                <X size={16} strokeWidth={2.5} />
                              </button>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[job.status] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                              {capitalize(job.status)}
                            </span>
                            {job.h1b_verdict && job.h1b_verdict !== 'unknown' && (
                              <span className={`text-[10px] px-1 py-0.5 rounded ${H1B_BADGES[job.h1b_verdict]?.bg || ''}`}>
                                {H1B_BADGES[job.h1b_verdict]?.label || job.h1b_verdict}
                              </span>
                            )}
                            {formatSalary(job.salary_min, job.salary_max) && (
                              <span className="text-[10px] text-green-700 dark:text-green-400 font-medium">{formatSalary(job.salary_min, job.salary_max)}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400" style={{marginTop: '0.25rem'}}>
                            <span className="font-medium">{job.company}</span>
                            {job.location && <span className="truncate">{job.location}</span>}
                          </div>
                          <div className="flex items-center gap-1.5">
                            {renderSlot(job, 'analyze_job', 'Scoring',
                              job.best_score > 0 ? (
                                <div className="relative"
                                  onMouseEnter={() => {
                                    const r = job.scoring_report
                                    const summary = r?.[job.best_cv]?.summary || Object.values(r || {})[0]?.summary
                                    if (summary) setTooltipJob(job.id)
                                  }}
                                  onMouseLeave={() => setTooltipJob(null)}>
                                  <div className="flex items-center gap-1">
                                    <div className="w-14 h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                                      <div className={`h-full rounded-full ${job.best_score >= 70 ? 'bg-green-500' : job.best_score >= 50 ? 'bg-yellow-500' : 'bg-red-400'}`}
                                        style={{ width: `${job.best_score}%` }} />
                                    </div>
                                    <span className="text-[10px] font-medium text-gray-600 dark:text-gray-400">{job.best_score}%</span>
                                  </div>
                                  {tooltipJob === job.id && (() => {
                                    const r = job.scoring_report
                                    const summary = r?.[job.best_cv]?.summary || Object.values(r || {})[0]?.summary
                                    return summary ? (
                                      <div className="absolute bottom-full left-0 mb-1 z-50 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded px-3 py-2 w-[450px] max-w-[60vw] shadow-lg pointer-events-none">
                                        {summary}
                                      </div>
                                    ) : null
                                  })()}
                                </div>
                              ) : null
                            )}
                            {job.best_cv && (
                              job.best_cv === 'Tailored' && job.tailored_resume_id ? (
                                <a href={`/resumes?resume=${job.tailored_resume_id}`} onClick={e => e.stopPropagation()}
                                  className="text-[10px] px-1 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 hover:underline">Tailored</a>
                              ) : (
                                <span className="text-[10px] px-1 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">{job.best_cv}</span>
                              )
                            )}
                            {job.best_cv && job.scoring_report?.[job.best_cv] && (
                              <button onClick={e => { e.stopPropagation(); setReportCv(job.best_cv); setReportJob(job) }}
                                className="p-0.5 text-gray-400 hover:text-indigo-500 dark:hover:text-indigo-400"
                                title={`View ${job.best_cv} report`}>
                                <FileText size={12} />
                              </button>
                            )}
                          </div>
                          {job.cv_scores && Object.keys(job.cv_scores).filter(k => k !== '_skipped' && k !== job.best_cv).length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(job.cv_scores).filter(([k]) => k !== '_skipped' && k !== job.best_cv).map(([name, score]) => (
                                <span key={name} className="inline-flex items-center gap-0.5">
                                  {name === 'Tailored' && job.tailored_resume_id ? (
                                    <a href={`/resumes?resume=${job.tailored_resume_id}`} onClick={e => e.stopPropagation()}
                                      className="text-[10px] text-gray-500 dark:text-gray-400 hover:underline">
                                      {name}: <strong className="text-purple-600 dark:text-purple-400">{score}</strong>
                                    </a>
                                  ) : (
                                    <span className="text-[10px] text-gray-500 dark:text-gray-400">
                                      {name}: <strong className="text-gray-700 dark:text-gray-300">{score}</strong>
                                    </span>
                                  )}
                                  {job.scoring_report?.[name] && (
                                    <button onClick={e => { e.stopPropagation(); setReportCv(name); setReportJob(job) }}
                                      className="p-0.5 text-gray-400 hover:text-indigo-500 dark:hover:text-indigo-400"
                                      title={`View ${name} report`}>
                                      <FileText size={10} />
                                    </button>
                                  )}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {job.discovered_at && <span className="text-[10px] text-gray-400 dark:text-gray-500 mt-auto">{timeAgo(job.discovered_at)}</span>}
                      </div>
                      <div className="flex flex-col items-center gap-0.5 ml-1 self-start">
                        <button onClick={e => saveAndAdvance(e, job)}
                          className={`p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 ${job.saved ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'}`} title="Save">
                          <Bookmark size={14} fill={job.saved ? 'currentColor' : 'none'} />
                        </button>
                        <button onClick={e => applyJob(e, job)}
                          className="p-1 rounded hover:bg-green-100 text-green-500 hover:text-green-700 dark:hover:bg-green-900/30 dark:text-green-400 dark:hover:text-green-300" title="Applied">
                          <CheckCircle size={14} />
                        </button>
                        <button onClick={e => openRescoreModal(e, job)}
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 dark:text-gray-500" title="Rescore">
                          <RotateCw size={14} />
                        </button>
                        {job.url && (
                          <a href={job.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400 dark:text-gray-500" title="Open in new tab">
                            <ExternalLink size={14} />
                          </a>
                        )}
                        <button onClick={e => ignoreCompany(e, job.company)}
                          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-400 hover:text-red-600 dark:hover:text-red-300" title="Ignore company globally">
                          <Ban size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-center gap-3 p-3 border-t dark:border-gray-700">
              <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
                className="px-2 py-1 text-xs border rounded disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">Prev</button>
              <span className="text-xs text-gray-600 dark:text-gray-400">
                {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
              <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total}
                className="px-2 py-1 text-xs border rounded disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">Next</button>
            </div>
          )}
        </div>
      </div>

      {/* Right panel — page viewer */}
      {selectedJob && (
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 dark:bg-gray-900 dark:border-gray-700">
            <div className="flex-1 min-w-0 mr-3">
              <p className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">{selectedJob.title}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{selectedJob.company} {selectedJob.location ? `— ${selectedJob.location}` : ''}</p>
            </div>
            <div className="flex items-center gap-1">
              {selectedJob.has_cached_page && (
                <div className="flex items-center bg-gray-200 dark:bg-gray-700 rounded text-xs mr-1">
                  <button onClick={() => setViewCached(true)}
                    className={`px-2 py-1 rounded ${viewCached ? 'bg-white shadow text-gray-900 font-medium dark:bg-gray-600 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
                    Cached
                  </button>
                  <button onClick={() => setViewCached(false)}
                    className={`px-2 py-1 rounded ${!viewCached ? 'bg-white shadow text-gray-900 font-medium dark:bg-gray-600 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
                    Live
                  </button>
                </div>
              )}
              <button onClick={async () => {
                    try { const { data } = await api.get('/resumes?is_base=true'); setCvBaseResumes(data) } catch {}
                    setCvMode('tailor'); setShowCvModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-purple-600 hover:bg-purple-50 rounded dark:text-purple-400 dark:hover:bg-purple-900/30">
                  <FileText size={12} /> Tailor CV
                </button>
                <button onClick={async () => {
                    try { const { data } = await api.get('/resumes?is_base=true'); setCvBaseResumes(data) } catch {}
                    setCvMode('copy'); setShowCvModal(true)
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-purple-600 hover:bg-purple-50 rounded dark:text-purple-400 dark:hover:bg-purple-900/30">
                  <FileText size={12} /> Copy CV
                </button>
              {selectedJob.url && (
                <a href={selectedJob.url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded dark:text-blue-400 dark:hover:bg-blue-900/30">
                  <ExternalLink size={12} /> Open
                </a>
              )}
              <button onClick={() => setSelectedJob(null)}
                className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-600">
                <X size={16} />
              </button>
            </div>
          </div>

          {viewCached && selectedJob.has_cached_page ? (
            <iframe
              key={`cached-${selectedJob.id}`}
              src={`/api/jobs/${selectedJob.id}/cached-page`}
              className="flex-1 w-full border-0"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
              title="Cached job posting"
            />
          ) : selectedJob.url ? (
            <iframe
              key={selectedJob.id}
              src={selectedJob.url}
              className="flex-1 w-full border-0"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
              title="Job posting"
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
              No URL available for this job
            </div>
          )}
        </div>
      )}

      {/* Rescore modal */}
      {rescoreJob && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setRescoreJob(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-80 p-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100 mb-1">Rescore</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3 truncate">{rescoreJob.title} — {rescoreJob.company}</p>
            {rescoreOptions.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">No base resumes or persona content yet.</p>
            ) : (
              <div className="space-y-1.5 mb-3 max-h-64 overflow-y-auto">
                {rescoreOptions.map(opt => (
                  <label key={opt.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={selectedRescoreIds.includes(opt.id)}
                      onChange={() => setSelectedRescoreIds(prev =>
                        prev.includes(opt.id) ? prev.filter(id => id !== opt.id) : [...prev, opt.id]
                      )}
                      className="rounded border-gray-300 dark:border-gray-600" />
                    <span className="text-gray-700 dark:text-gray-300">{opt.name}</span>
                    {opt.id === 'persona' && (
                      <span className="text-[10px] text-purple-600 dark:text-purple-400">(virtual)</span>
                    )}
                  </label>
                ))}
              </div>
            )}
            <div className="mt-3">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Scoring Depth</label>
              <select value={rescoreDepth} onChange={e => setRescoreDepth(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="light">Light (score only)</option>
                <option value="full">Full (score + keywords + report)</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 mt-3">
              <button onClick={() => setRescoreJob(null)}
                className="px-3 py-1.5 text-xs border rounded hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">Cancel</button>
              <button onClick={runRescore} disabled={rescoring || selectedRescoreIds.length === 0}
                className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1">
                {rescoring ? <><RotateCw size={12} className="animate-spin" /> Scoring...</> : 'Score'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* #17 Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-gray-900 dark:bg-gray-700 text-white rounded-lg px-4 py-2 flex items-center gap-3 shadow-xl z-50">
          <span className="text-sm">{selectedIds.size} selected</span>
          <button onClick={() => bulkAction('skip')} className="text-sm px-3 py-1 bg-gray-700 dark:bg-gray-600 rounded hover:bg-gray-600 dark:hover:bg-gray-500">Skip All</button>
          <button onClick={() => bulkAction('save')} className="text-sm px-3 py-1 bg-blue-600 rounded hover:bg-blue-700">Save All</button>
          <button onClick={() => setSelectedIds(new Set())} className="text-sm text-gray-400 hover:text-white">Clear</button>
        </div>
      )}

      {/* #20 Undo toast — hidden when bulk action bar is visible */}
      {undoToast && selectedIds.size === 0 && (
        <div className="fixed bottom-4 right-4 bg-gray-900 text-white rounded-lg px-4 py-3 flex items-center gap-3 shadow-xl z-50">
          <span className="text-sm">{undoToast.message}</span>
          <button onClick={handleUndo} className="text-sm text-blue-400 hover:text-blue-300 font-medium">Undo</button>
        </div>
      )}

      {/* Tailor background toasts */}
      {tailorToasts.length > 0 && (
        <div className="fixed bottom-16 right-4 flex flex-col gap-2 z-50">
          {tailorToasts.map(t => (
            <div key={t.id} className={`rounded-lg px-4 py-3 flex items-center gap-3 shadow-xl text-white text-sm ${
              t.status === 'loading' || t.status === 'running' ? 'bg-gray-800' : t.status === 'success' ? 'bg-green-700' : 'bg-red-700'
            }`}>
              {t.status === 'loading' && <><Loader2 size={14} className="animate-spin flex-shrink-0" /> Tailoring CV for {t.company}...</>}
              {t.status === 'running' && <><Loader2 size={14} className="animate-spin flex-shrink-0" /> Tailoring CV for {t.company} in background...</>}
              {t.status === 'success' && (
                <>
                  <CheckCircle size={14} className="flex-shrink-0" />
                  <span>Tailored CV ready for {t.company}</span>
                  <a href={`/resumes?resume=${t.resumeId}`} className="text-green-200 hover:text-white font-medium underline">View</a>
                </>
              )}
              {t.status === 'error' && (
                <>
                  <Ban size={14} className="flex-shrink-0" />
                  <span>Tailor failed for {t.company}: {t.error}</span>
                </>
              )}
              {t.status !== 'loading' && t.status !== 'running' && (
                <button onClick={() => setTailorToasts(prev => prev.filter(x => x.id !== t.id))} className="text-white/60 hover:text-white ml-1">
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Scoring report modal */}
      {reportJob && reportJob.scoring_report && (() => {
        const allReports = reportJob.scoring_report
        const cvNames = Object.keys(allReports).filter(k => allReports[k]?.summary)
        const activeCv = reportCv && cvNames.includes(reportCv) ? reportCv : cvNames[0]
        const rpt = allReports[activeCv] || {}
        const score = reportJob.cv_scores?.[activeCv]
        return (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setReportJob(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[700px] max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b dark:border-gray-700">
              <div className="min-w-0">
                <div className="flex items-center gap-2 min-w-0">
                  <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate min-w-0 flex-shrink">{reportJob.title}</h2>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 whitespace-nowrap ${activeCv === 'Tailored' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'}`}>
                    {activeCv}{score != null ? `: ${score}` : ''}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">{reportJob.company}</p>
              </div>
              <button onClick={() => setReportJob(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-1 ml-3 flex-shrink-0">
                <X size={18} />
              </button>
            </div>

            {/* CV tabs */}
            {cvNames.length > 1 && (
              <div className="flex gap-1 px-5 pt-3 border-b dark:border-gray-700">
                {cvNames.map(cv => (
                  <button key={cv} onClick={() => setReportCv(cv)}
                    className={`px-3 py-1.5 text-xs font-medium border-b-2 -mb-px transition-colors ${
                      cv === activeCv
                        ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                    }`}>
                    {cv} {reportJob.cv_scores?.[cv] != null && <span className="ml-1 opacity-70">({reportJob.cv_scores[cv]})</span>}
                  </button>
                ))}
              </div>
            )}

            <div className="p-5 space-y-4">

              {/* Summary */}
              {rpt.summary && <p className="text-sm text-gray-700 dark:text-gray-300">{rpt.summary}</p>}

              {/* Keyword coverage */}
              {rpt.keyword_coverage_pct != null && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Keyword Coverage</span>
                    <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{rpt.keyword_coverage_pct}%</span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${rpt.keyword_coverage_pct >= 75 ? 'bg-green-500' : rpt.keyword_coverage_pct >= 50 ? 'bg-yellow-500' : 'bg-red-400'}`}
                      style={{ width: `${rpt.keyword_coverage_pct}%` }} />
                  </div>
                </div>
              )}

              {/* Keywords */}
              {(rpt.matched_keywords?.length > 0 || rpt.missing_keywords?.length > 0) && (
                <div className="flex flex-wrap gap-1.5">
                  {(rpt.matched_keywords || []).map(kw => (
                    <span key={kw} className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">{kw}</span>
                  ))}
                  {(rpt.missing_keywords || []).map(kw => (
                    <span key={kw} className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-300">{kw}</span>
                  ))}
                </div>
              )}

              {/* Requirement mapping table */}
              {rpt.requirement_mapping?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Requirement Mapping</h3>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b dark:border-gray-700">
                        <th className="text-left py-1.5 text-gray-500 dark:text-gray-400 font-medium">Requirement</th>
                        <th className="text-left py-1.5 text-gray-500 dark:text-gray-400 font-medium">CV Match</th>
                        <th className="text-center py-1.5 w-16 text-gray-500 dark:text-gray-400 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rpt.requirement_mapping.map((req, i) => (
                        <tr key={i} className="border-b dark:border-gray-700">
                          <td className="py-1.5 pr-2 text-gray-700 dark:text-gray-300">
                            {req.requirement}
                            {req.severity === 'preferred' && <span className="ml-1 text-[9px] text-gray-400">(preferred)</span>}
                          </td>
                          <td className="py-1.5 pr-2 text-gray-600 dark:text-gray-400">{req.cv_match || '\u2014'}</td>
                          <td className={`py-1.5 text-center ${req.matched ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>{req.matched ? '\u2713' : '\u2717'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Hard blockers */}
              {rpt.hard_blockers?.length > 0 && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                  <h3 className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1">Hard Blockers</h3>
                  {rpt.hard_blockers.map((b, i) => (
                    <p key={i} className="text-xs text-red-600 dark:text-red-400">{b}</p>
                  ))}
                </div>
              )}

              {/* ATS Tip */}
              {rpt.ats_tip && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                  <h3 className="text-xs font-semibold text-blue-700 dark:text-blue-400 mb-1">ATS Tip</h3>
                  <p className="text-xs text-blue-600 dark:text-blue-400">{rpt.ats_tip}</p>
                </div>
              )}
            </div>
          </div>
        </div>
        )
      })()}

      {showCvModal && selectedJob && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-[400px]">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{cvMode === 'copy' ? 'Copy CV for Job' : 'Tailor CV for Job'}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {selectedJob.company} — {selectedJob.title}
            </p>
            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Base Resume</label>
              <select value={cvSelectedBase}
                onChange={e => setCvSelectedBase(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                <option value="">Select base resume...</option>
                {cvBaseResumes.map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCvModal(false)}
                className="px-4 py-1.5 text-sm border rounded dark:border-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">Cancel</button>
              <button onClick={generateCv} disabled={cvGenerating || !cvSelectedBase}
                className="px-4 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2">
                {cvGenerating ? <><Loader2 size={14} className="animate-spin" /> {cvMode === 'copy' ? 'Copying...' : 'Generating...'}</> : cvMode === 'copy' ? 'Copy with Tracer Links' : 'Generate Tailored CV'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
