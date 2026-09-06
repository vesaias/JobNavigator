import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import api from '../api'

// Banner shown when one or more active companies/searches have failing scrapes
// (from GET /api/health/entities). Dismissal is keyed by the exact set of down
// entities, so it reappears next session or when a NEW entity breaks.
export default function HealthBanner() {
  const [health, setHealth] = useState(null)
  const [dismissedKey, setDismissedKey] = useState(() => {
    try { return sessionStorage.getItem('jn:health_dismissed') || '' } catch { return '' }
  })
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/health/entities').then(({ data }) => setHealth(data)).catch(() => {})
  }, [])

  if (!health || !health.count) return null
  const key = [...health.companies.map(c => 'c:' + c.id), ...health.searches.map(s => 's:' + s.id)].sort().join(',')
  if (dismissedKey === key) return null

  const dismiss = (e) => {
    e.stopPropagation()
    try { sessionStorage.setItem('jn:health_dismissed', key) } catch {}
    setDismissedKey(key)
  }
  const go = () => navigate(health.companies.length ? '/companies' : '/searches')

  const parts = []
  if (health.companies.length) parts.push(`${health.companies.length} compan${health.companies.length > 1 ? 'ies' : 'y'}`)
  if (health.searches.length) parts.push(`${health.searches.length} search${health.searches.length > 1 ? 'es' : ''}`)

  return (
    <div onClick={go} role="button"
      className="flex items-start gap-3 px-4 py-3 bg-gradient-to-r from-amber-500 to-orange-600 text-white text-sm cursor-pointer">
      <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />
      <div className="flex-1">
        <span className="font-semibold">{parts.join(' and ')} need attention.</span>{' '}
        Recent scrapes are failing or returning nothing — a URL or ATS may have changed. Click to review.
      </div>
      <button onClick={dismiss} aria-label="Dismiss" className="flex-shrink-0 text-white/80 hover:text-white transition-colors">
        <X size={18} />
      </button>
    </div>
  )
}
