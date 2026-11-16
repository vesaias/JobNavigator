// Update check (backend/update_check.py, GET /api/updates): a newer release, or new
// commits on main, compared with this install. It only reports; it never updates.
// The backend caches the GitHub answer for hours, so reading it on every page load is cheap.
import React, { useEffect, useState } from 'react'
import api from './api'
import { Helper, Link, Pill, Spinner } from './ui'

const SEEN_KEY = 'jobnavigator_update_seen'

// One short line for a result, or null when nothing is new.
export function updateSummary(u) {
  if (!u || !u.update_available) return null
  if (u.mode === 'commit') {
    const n = u.behind_by
    return n ? `${n} new commit${n === 1 ? '' : 's'} on ${u.branch || 'main'}` : `New commits on ${u.branch || 'main'}`
  }
  return u.latest?.version ? `JobNavigator ${u.latest.version} is available` : 'A new release is available'
}

// What the toast remembers, so each new release or head commit is announced once per browser.
const seenId = (u) => `${u.mode}:${u.repo}:${u.latest?.version || u.latest?.commit || ''}`

// Shell: one toast for the owner when an update is available. Members cannot update, so they get none.
export function useUpdateNotice(push) {
  useEffect(() => {
    if (__DEMO__ || !push) return
    let on = true
    api.get('/updates').then(({ data }) => {
      const text = on && data?.owner ? updateSummary(data) : null
      if (!text) return
      let seen = null
      try { seen = localStorage.getItem(SEEN_KEY) } catch {}
      if (seen === seenId(data)) return
      try { localStorage.setItem(SEEN_KEY, seenId(data)) } catch {}
      push({ kind: 'progress', spin: false, ttl: 15000, msg: `${text}. Settings › Updates shows how to update.`,
        ...(data.url ? { action: 'View', onAction: () => window.open(data.url, '_blank', 'noopener,noreferrer') } : null) })
    }).catch(() => { /* no answer: the check is optional, nothing to show */ })
    return () => { on = false }
  }, [push])
}

// Settings › Updates › Status. `mode` and `repo` are passed so a changed setting checks again.
export function UpdateStatusRow({ mode, repo }) {
  const [u, setU] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = (force = false) => {
    setBusy(true)
    return api.get('/updates', { params: force ? { force: true } : undefined })
      .then(({ data }) => setU(data))
      .catch(() => setU({ error: 'request failed', message: 'The update check did not answer.' }))
      .finally(() => setBusy(false))
  }
  useEffect(() => { load() }, [mode, repo])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!u) return <Helper style={{ flex: 1, minWidth: 0 }}>Checking…</Helper>
  const text = updateSummary(u)
  const tone = u.error ? 'var(--warn)' : text ? 'var(--accent)' : 'var(--muted)'
  const checked = u.checked_at ? new Date(u.checked_at).toLocaleString() : null
  return (
    <>
      <Helper style={{ flex: 1, minWidth: 0, color: tone }} title={[u.message, u.error, checked && `Checked ${checked}`].filter(Boolean).join(' · ')}>
        {u.message}
        {u.url && text && <> <Link href={u.url} target="_blank" rel="noopener noreferrer">View ↗</Link></>}
      </Helper>
      {u.owner && u.mode !== 'off' && (
        <Pill onClick={() => !busy && load(true)} ariaLabel="Check for updates now">
          {busy && <Spinner />}{busy ? 'Checking…' : 'Check now'}
        </Pill>
      )}
    </>
  )
}
