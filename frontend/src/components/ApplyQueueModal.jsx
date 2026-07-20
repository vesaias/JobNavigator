import React, { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, BriefcaseBusiness, Download, ExternalLink, FilePenLine, Loader2, X } from 'lucide-react'
import api from '../api'

const FEED_LABELS = {
  intern_usa: 'USA Internship',
  new_grad_usa: 'USA New Grad',
  intern_intl: 'International Internship',
  new_grad_intl: 'International New Grad',
  speedyapply_intern_usa: 'SpeedyApply Internship',
  speedyapply_new_grad_usa: 'SpeedyApply New Grad',
  vansh_summer_2027: 'Vansh Internship',
  vansh_new_grad_2027: 'Vansh New Grad',
}

export default function ApplyQueueModal() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [closing, setClosing] = useState(false)

  const loadReady = useCallback(async () => {
    try {
      const { data } = await api.get('/apply-queue/ready', { params: { unseen_only: true } })
      setItems(data.items || [])
    } catch (error) {
      // Authentication failures are handled by the global interceptor. Other
      // failures should not block the rest of the dashboard.
      if (error.response?.status !== 401) console.warn('Failed to load apply queue', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReady()
    const timer = window.setInterval(loadReady, 60_000)
    return () => window.clearInterval(timer)
  }, [loadReady])

  const acknowledgeAndClose = async () => {
    if (closing) return
    setClosing(true)
    const current = items
    setItems([])
    await Promise.allSettled(current.map(item => api.post(`/apply-queue/${item.id}/acknowledge`)))
    setClosing(false)
  }

  if (loading || items.length === 0) return null

  return (
    <div className="fixed inset-0 z-[70] bg-black/55 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="apply-queue-title">
      <div className="w-full max-w-4xl max-h-[88vh] overflow-hidden rounded-2xl bg-white dark:bg-gray-800 shadow-2xl border border-gray-200 dark:border-gray-700">
        <div className="flex items-start justify-between gap-4 px-6 py-5 border-b dark:border-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-indigo-950/40">
          <div className="flex gap-3">
            <div className="mt-0.5 rounded-xl bg-blue-600 text-white p-2.5">
              <BriefcaseBusiness size={22} />
            </div>
            <div>
              <h2 id="apply-queue-title" className="text-xl font-bold text-gray-900 dark:text-gray-100">
                {items.length} application {items.length === 1 ? 'packet is' : 'packets are'} ready
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                JobNavigator fetched each JD and prepared a tailored resume. Open the form, fill it in, and submit it yourself.
              </p>
            </div>
          </div>
          <button onClick={acknowledgeAndClose} className="p-2 rounded-lg text-gray-400 hover:bg-white/70 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200" aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto max-h-[62vh] divide-y dark:divide-gray-700">
          {items.map((item, index) => (
            <article key={item.id} className="px-6 py-5 hover:bg-gray-50/70 dark:hover:bg-gray-700/30">
              <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">#{index + 1}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                      {FEED_LABELS[item.source_feed] || item.source_feed || 'Job feed'}
                    </span>
                    {item.status === 'needs_review' && (
                      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        <AlertTriangle size={12} /> Review required
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">{item.title}</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                    {item.company || 'Unknown company'}{item.location ? ` · ${item.location}` : ''}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 truncate" title={item.resume_name}>
                    Resume: {item.resume_name}
                  </p>
                  {item.artifact_path && (
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate" title={item.artifact_path}>
                      Packet: {item.artifact_path}
                    </p>
                  )}
                  {(item.eligibility_warnings || []).length > 0 && (
                    <p className="text-xs text-amber-700 dark:text-amber-300 mt-2">
                      {item.eligibility_warnings.join(' · ')}
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3 gap-2 shrink-0">
                  <a href={item.application_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700">
                    <ExternalLink size={15} /> Application form
                  </a>
                  <a href={item.resume_pdf_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">
                    <Download size={15} /> Resume PDF
                  </a>
                  <a href={item.resume_editor_url}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">
                    <FilePenLine size={15} /> Review resume
                  </a>
                </div>
              </div>
            </article>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-6 py-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            No form is submitted automatically. Employer questions, CAPTCHAs, attestations, and the final Submit click stay under your control.
          </p>
          <button onClick={acknowledgeAndClose} disabled={closing}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 text-sm font-medium disabled:opacity-60">
            {closing && <Loader2 size={14} className="animate-spin" />}
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
