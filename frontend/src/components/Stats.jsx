import React, { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api'
import { RefreshCw, Play, Loader2 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Cell, Sankey } from 'recharts'

const TYPE_COLORS = {
  scrape: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  h1b: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  cv_score: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  email: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  telegram: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300',
}

const FUNNEL_COLORS = ['#6366f1', '#818cf8', '#a78bfa', '#c4b5fd', '#7c3aed']

const SCORE_COLORS = { "0-20": "#ef4444", "21-40": "#f97316", "41-60": "#eab308", "61-80": "#22c55e", "81-100": "#6366f1" }

function decodeCron(expr) {
  if (!expr || expr.includes('Every')) return expr
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return expr
  const [min, hour, day, month, dow] = parts
  const dowNames = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat', '7': 'Sun' }
  let time = ''
  if (hour !== '*' && min !== '*') time = `at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  else if (hour !== '*') time = `at ${hour.padStart(2, '0')}:00`
  else if (min.startsWith('*/')) time = `every ${min.slice(2)} min`
  else if (hour.startsWith('*/')) time = `every ${hour.slice(2)}h`
  else time = expr
  if (dow !== '*') return `${dowNames[dow] || dow} ${time}`
  if (day !== '*') return `Day ${day} ${time}`
  if (month !== '*') return `Month ${month} ${time}`
  return `Daily ${time}`
}

const SANKEY_NODE_COLORS = {
  new: '#94a3b8', applied: '#6366f1', screening: '#818cf8',
  phone_screen: '#a78bfa', interview: '#f59e0b', final_round: '#f97316',
  offer: '#22c55e', rejected: '#ef4444',
}

const SankeyNode = ({ x, y, width, height, index, payload }) => {
  const name = payload?.name || ''
  const value = payload?.value || 0
  const color = SANKEY_NODE_COLORS[name] || '#6366f1'
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} rx={3} opacity={0.9} />
      <text x={x + width + 6} y={y + height / 2} textAnchor="start" dominantBaseline="middle" fontSize={11} className="fill-gray-700 dark:fill-gray-300">
        {name} ({value})
      </text>
    </g>
  )
}

const TRIGGER_COLORS = {
  scheduler: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  manual: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
}

const STATUS_COLORS = {
  completed: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
}

const formatCET = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('en-GB', { timeZone: 'Europe/Berlin', dateStyle: 'short', timeStyle: 'short' })
  } catch { return new Date(iso).toLocaleString() }
}

const formatDuration = (seconds) => {
  if (seconds == null) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function LlmCostPanel() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState(7)

  useEffect(() => {
    api.get(`/stats/llm-costs?days=${days}`)
      .then(r => setData(r.data))
      .catch(() => setData({ total_calls: 0, total_cost_usd: 0, by_purpose: [] }))
  }, [days])

  if (!data) return null

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mt-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">LLM Costs — last {days} days</h2>
        <select
          value={days}
          onChange={e => setDays(parseInt(e.target.value, 10))}
          className="text-xs border rounded px-2 py-1 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
        >
          <option value={1}>1d</option>
          <option value={7}>7d</option>
          <option value={30}>30d</option>
        </select>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-3">
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Total spend</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            ${data.total_cost_usd?.toFixed(4) || '0.0000'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Total calls</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">{data.total_calls}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Avg $ / call</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            ${data.total_calls > 0 ? (data.total_cost_usd / data.total_calls).toFixed(4) : '0.0000'}
          </div>
        </div>
      </div>
      {data.by_purpose?.length > 0 && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
              <th className="py-1">Purpose</th>
              <th className="py-1">Model</th>
              <th className="py-1 text-right">Calls</th>
              <th className="py-1 text-right">Cost</th>
              <th className="py-1 text-right">Cache hit</th>
            </tr>
          </thead>
          <tbody>
            {data.by_purpose.map((g, i) => (
              <tr key={i} className="border-b border-gray-100 dark:border-gray-700">
                <td className="py-1 text-gray-900 dark:text-gray-100">{g.purpose}</td>
                <td className="py-1 text-gray-500 dark:text-gray-400">{g.model}</td>
                <td className="py-1 text-right">{g.calls}</td>
                <td className="py-1 text-right text-gray-900 dark:text-gray-100">${g.cost_usd.toFixed(4)}</td>
                <td className="py-1 text-right">{(g.cache_hit_ratio * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function Stats() {
  const [stats, setStats] = useState(null)
  const [schedulerJobs, setSchedulerJobs] = useState([])
  const [activityLog, setActivityLog] = useState([])
  const [runHistory, setRunHistory] = useState([])
  const [timeline, setTimeline] = useState([])
  const [scoreDistribution, setScoreDistribution] = useState([])
  const [sankeyData, setSankeyData] = useState(null)
  const [flowView, setFlowView] = useState('bar') // 'bar' | 'sankey'
  const [loading, setLoading] = useState(true)
  const [activityType, setActivityType] = useState('')
  const [activityCompany, setActivityCompany] = useState('')
  const pollRef = useRef(null)
  const hasRunningRef = useRef(false)

  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() => setIsDark(document.documentElement.classList.contains('dark')))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  const axisColor = isDark ? '#9ca3af' : '#6b7280'
  const gridColor = isDark ? '#374151' : '#e5e7eb'
  const tooltipBg = isDark ? '#1f2937' : '#ffffff'
  const tooltipBorder = isDark ? '#374151' : '#e5e7eb'
  const tooltipText = isDark ? '#e5e7eb' : '#374151'

  const fetchSchedulerJobs = useCallback(async () => {
    try {
      const { data } = await api.get('/scheduler/jobs')
      setSchedulerJobs(data)
      const anyRunning = data.some(j => j.running)
      hasRunningRef.current = anyRunning
    } catch (e) { console.error(e) }
  }, [])

  const fetchData = async () => {
    try {
      const [statsRes] = await Promise.all([
        api.get('/stats'),
      ])
      setStats(statsRes.data)
    } catch (e) { console.error(e) }
    await fetchSchedulerJobs()
    setLoading(false)
  }

  const fetchRunHistory = async () => {
    try {
      const { data } = await api.get('/monitor/history', { params: { limit: 30 } })
      setRunHistory(data)
    } catch (e) { console.error(e) }
  }

  const fetchTimeline = async () => {
    try {
      const { data } = await api.get('/stats/timeline', { params: { days: 30 } })
      setTimeline(data)
    } catch (e) { console.error(e) }
  }

  const fetchScoreDistribution = async () => {
    try {
      const { data } = await api.get('/stats/score-distribution')
      setScoreDistribution(data)
    } catch (e) { console.error(e) }
  }

  const fetchSankey = async () => {
    try {
      const { data } = await api.get('/stats/sankey')
      if (data && data.length > 0) {
        // Build Sankey nodes and links from flow data
        const nodeNames = new Set()
        data.forEach(d => { nodeNames.add(d.source); nodeNames.add(d.target) })
        const nodeList = [...nodeNames]
        const nodes = nodeList.map(name => ({ name }))
        const links = data.map(d => ({
          source: nodeList.indexOf(d.source),
          target: nodeList.indexOf(d.target),
          value: d.value,
        })).filter(l => l.source !== -1 && l.target !== -1 && l.source !== l.target)
        if (links.length > 0) setSankeyData({ nodes, links })
      }
    } catch (e) { console.error(e) }
  }

  const fetchActivityLog = async () => {
    try {
      const params = { limit: 50 }
      if (activityType) params.type = activityType
      if (activityCompany) params.company = activityCompany
      const { data } = await api.get('/activity-log', { params })
      setActivityLog(data)
    } catch (e) { console.error(e) }
  }

  const triggerJob = async (jobId, triggerUrl) => {
    try {
      await api.post(triggerUrl)
      // Immediately refresh to show running state
      fetchSchedulerJobs()
    } catch (e) {
      if (e.response?.status === 409) {
        alert(e.response.data.detail || 'Job is already running')
      } else {
        console.error('Trigger failed:', e)
      }
    }
  }

  // Polling: 3s when jobs running, 10s when idle
  useEffect(() => {
    const poll = () => {
      fetchSchedulerJobs()
      fetchRunHistory()
      const interval = hasRunningRef.current ? 3000 : 10000
      pollRef.current = setTimeout(poll, interval)
    }
    // Start first poll after initial load
    pollRef.current = setTimeout(poll, 3000)
    return () => clearTimeout(pollRef.current)
  }, [fetchSchedulerJobs])

  useEffect(() => { fetchData(); fetchRunHistory(); fetchTimeline(); fetchScoreDistribution(); fetchSankey() }, [])
  useEffect(() => { fetchActivityLog() }, [activityType, activityCompany])

  if (loading) return <div className="p-6 text-center text-gray-500 dark:text-gray-400">Loading stats...</div>

  const statCards = stats ? [
    { label: 'Total Jobs', value: stats.total_jobs, color: 'bg-blue-500' },
    { label: 'New Jobs', value: stats.new_jobs, color: 'bg-green-500' },
    { label: 'Saved', value: stats.saved_jobs, color: 'bg-indigo-500' },
    { label: 'Applications', value: stats.total_applications, color: 'bg-purple-500' },
    { label: 'Response Rate', value: `${stats.response_rate}%`, color: 'bg-amber-500' },
  ] : []

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Statistics & Activity</h1>
        <button onClick={() => { fetchData(); fetchRunHistory(); fetchActivityLog() }} className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {statCards.map(({ label, value, color }) => (
          <div key={label} className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4">
            <div className={`w-2 h-2 rounded-full ${color} inline-block mr-2`}></div>
            <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
            <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{value}</p>
          </div>
        ))}
      </div>

      {/* LLM Cost Panel */}
      <LlmCostPanel />

      {/* Charts */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Application Flow */}
          <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-gray-700 dark:text-gray-300">Application Flow</h2>
              {sankeyData && (
                <div className="flex text-xs border dark:border-gray-600 rounded overflow-hidden">
                  <button onClick={() => setFlowView('bar')}
                    className={`px-2 py-0.5 ${flowView === 'bar' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}`}>Bar</button>
                  <button onClick={() => setFlowView('sankey')}
                    className={`px-2 py-0.5 ${flowView === 'sankey' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}`}>Flow</button>
                </div>
              )}
            </div>
            {flowView === 'sankey' && sankeyData ? (
              <ResponsiveContainer width="100%" height={250}>
                <Sankey data={sankeyData} nodePadding={28} nodeWidth={12}
                  margin={{ top: 5, right: 120, left: 5, bottom: 5 }}
                  link={{ stroke: isDark ? '#6366f1' : '#c4b5fd', strokeOpacity: isDark ? 0.3 : 0.45 }}
                  node={<SankeyNode />}>
                  <Tooltip contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, color: tooltipText }} labelStyle={{ color: tooltipText }} itemStyle={{ color: tooltipText }} />
                </Sankey>
              </ResponsiveContainer>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart layout="vertical" data={[
                  { stage: 'Applied', count: (stats.application_statuses?.applied || 0) + (stats.application_statuses?.screening || 0) },
                  { stage: 'Interview', count: (stats.application_statuses?.interview || 0) + (stats.application_statuses?.phone_screen || 0) + (stats.application_statuses?.final_round || 0) },
                  { stage: 'Offer', count: stats.application_statuses?.offer || 0 },
                  { stage: 'Rejected', count: stats.application_statuses?.rejected || 0 },
                ]} margin={{ top: 5, right: 20, left: 70, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: axisColor }} stroke={axisColor} />
                  <YAxis type="category" dataKey="stage" tick={{ fontSize: 12, fill: axisColor }} stroke={axisColor} />
                  <Tooltip contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, color: tooltipText }} labelStyle={{ color: tooltipText }} itemStyle={{ color: tooltipText }} />
                  <Bar dataKey="count" name="Count">
                    {[0, 1, 2, 3].map(i => (
                      <Cell key={i} fill={['#6366f1', '#a78bfa', '#7c3aed', '#ef4444'][i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>

          {/* Score Distribution */}
          <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4">
            <h2 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-3">Score Distribution</h2>
            {scoreDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={scoreDistribution} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="range" tick={{ fontSize: 11, fill: axisColor }} stroke={axisColor} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: axisColor }} stroke={axisColor} />
                  <Tooltip contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, color: tooltipText }} labelStyle={{ color: tooltipText }} itemStyle={{ color: tooltipText }} />
                  <Bar dataKey="count" name="Jobs">
                    {scoreDistribution.map((entry, i) => (
                      <Cell key={i} fill={SCORE_COLORS[entry.range] || '#6366f1'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[200px] text-sm text-gray-400 dark:text-gray-500">No scored jobs yet</div>
            )}
          </section>
        </div>
      )}

      {/* Jobs Timeline - full width */}
      <section className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-4 mb-6">
        <h2 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-3">Jobs Discovered (Last 30 Days)</h2>
        {timeline.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={timeline} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: axisColor }} stroke={axisColor} />
              <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11, fill: axisColor }} stroke={axisColor} />
              <YAxis yAxisId="right" orientation="right" allowDecimals={false} tick={{ fontSize: 11, fill: '#22c55e' }} stroke="#22c55e" />
              <Tooltip contentStyle={{ backgroundColor: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, color: tooltipText }} labelStyle={{ color: tooltipText }} itemStyle={{ color: tooltipText }} />
              <Line yAxisId="left" type="monotone" dataKey="total" stroke="#6366f1" name="Discovered" strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="applied" stroke="#22c55e" name="Applied" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-[250px] text-sm text-gray-400 dark:text-gray-500">No timeline data available</div>
        )}
      </section>

      {/* Schedules */}
      <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg overflow-hidden mb-8">
        <div className="px-4 py-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
          <h2 className="font-semibold dark:text-gray-100">Schedules</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Job</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Schedule</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Next Run (CET)</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {schedulerJobs.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No scheduled jobs</td></tr>
              ) : schedulerJobs.map(job => {
                const isRunning = !!job.running
                return (
                  <tr key={job.id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-2 text-xs font-medium text-gray-800 dark:text-gray-200 whitespace-nowrap">{job.name}</td>
                    <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap" title={job.schedule}>{decodeCron(job.schedule)}</td>
                    <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">{formatCET(job.next_run)}</td>
                    <td className="px-4 py-2 text-xs">
                      {isRunning ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 animate-pulse">
                          <Loader2 size={10} className="animate-spin" />
                          Running ({Math.round(job.running.elapsed_seconds)}s)
                        </span>
                      ) : job.schedule === 'Manual only' ? (
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">Manual</span>
                      ) : job.pending ? (
                        <span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">Pending</span>
                      ) : (
                        <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">Active</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-right">
                      {job.trigger_url ? (
                        <button
                          onClick={() => triggerJob(job.id, job.trigger_url)}
                          disabled={isRunning}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded ${
                            isRunning
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                              : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                          }`}
                          title={isRunning ? 'Already running' : 'Run Now'}>
                          {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                          {isRunning ? 'Running' : 'Run'}
                        </button>
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600">-</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Run History */}
      <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg overflow-hidden mb-8">
        <div className="px-4 py-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
          <h2 className="font-semibold dark:text-gray-100">Run History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Time (CET)</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Job Type</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Trigger</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Duration</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Result / Error</th>
              </tr>
            </thead>
            <tbody>
              {runHistory.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No runs yet</td></tr>
              ) : runHistory.map(run => (
                <tr key={run.id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">{formatCET(run.started_at)}</td>
                  <td className="px-4 py-2 text-xs font-medium text-gray-800 dark:text-gray-200">{run.job_type}</td>
                  <td className="px-4 py-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded ${TRIGGER_COLORS[run.trigger] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                      {run.trigger}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded ${
                      run.status === 'running' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 animate-pulse' : STATUS_COLORS[run.status] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                    }`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400">{formatDuration(run.duration_seconds)}</td>
                  <td className="px-4 py-2 text-xs text-gray-700 dark:text-gray-300 max-w-[300px] truncate"
                    title={run.error || run.result_summary || ''}>
                    {run.error ? (
                      <span className="text-red-600 dark:text-red-400">{run.error}</span>
                    ) : run.result_summary || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Activity Log */}
      <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-700 flex items-center justify-between">
          <h2 className="font-semibold dark:text-gray-100">Activity Log</h2>
          <div className="flex items-center gap-2">
            <select value={activityType} onChange={e => setActivityType(e.target.value)}
              className="border rounded px-2 py-1 text-xs dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
              <option value="">All Types</option>
              <option value="scrape">Scrape</option>
              <option value="h1b">H-1B</option>
              <option value="cv_score">CV Score</option>
              <option value="email">Email</option>
              <option value="telegram">Telegram</option>
            </select>
            <input type="text" placeholder="Company..." value={activityCompany}
              onChange={e => setActivityCompany(e.target.value)}
              className="border rounded px-2 py-1 text-xs w-28 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Time (CET)</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Type</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Message</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Company</th>
              </tr>
            </thead>
            <tbody>
              {activityLog.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No activity yet</td></tr>
              ) : activityLog.map(log => (
                <tr key={log.id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">
                    {formatCET(log.created_at)}
                  </td>
                  <td className="px-4 py-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded ${TYPE_COLORS[log.type] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                      {log.type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-700 dark:text-gray-300 max-w-[400px] truncate" title={log.message}>
                    {log.message}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">{log.company || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
