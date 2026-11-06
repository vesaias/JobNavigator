import React, { useEffect, useState } from 'react'
import api from '../api'
import { Button, Helper, Label } from '../ui'

const NAMES = { codex_cli: 'Codex', claude_code: 'Claude Code', antigravity_cli: 'Antigravity' }
const PHASES = { unknown: 'Waiting', absent: 'Inactive', pulling: 'Downloading', creating: 'Creating',
  starting: 'Starting', ready: 'Ready', sleeping: 'Sleeping', draining: 'Finishing requests', removing: 'Removing', error: 'Error' }
const mb = (n) => `${(n / 1048576).toFixed(1)} MB`

export default function RunnerStatus({ accountId, isOwner }) {
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  useEffect(() => {
    let active = true, timer
    const abort = new AbortController()
    setSnapshot(null)
    setError('')
    async function poll() {
      try {
        const r = await api.get('/llm/runners', { signal: abort.signal })
        if (active) { setSnapshot(r?.data || null); setError('') }
      } catch {
        if (active) setError('Cannot refresh container status. Check the backend connection.')
      } finally {
        if (active) timer = setTimeout(poll, 2500)
      }
    }
    poll()
    return () => { active = false; abort.abort(); clearTimeout(timer) }
  }, [accountId])

  async function retry() {
    setRetrying(true)
    try { await api.post('/llm/runners/retry'); setError('') }
    catch { setError('Could not request a retry. Check the backend connection.') }
    finally { setRetrying(false) }
  }
  if (!snapshot?.enabled && !error) return snapshot?.enabled === false
    ? <Helper>Automatic container management is disabled. The owner starts providers with Compose profiles.</Helper> : null
  return <div style={{ display: 'grid', gap: 9, width: '100%', minWidth: 0 }}>
    <Helper>Saved selections across all profiles keep their providers running. Unused containers are removed after active requests finish; images and logins are kept.</Helper>
    <div role="status" aria-live="polite" aria-label="Provider containers">
      {(snapshot?.providers || []).map((row) => <div key={row.provider} style={{ display: 'grid', gap: 2, marginBottom: 8 }}>
        <Label>{NAMES[row.provider] || row.provider} · {PHASES[row.state] || 'Waiting'}</Label>
        <Helper>{row.message}</Helper>
        {row.state === 'pulling' && <Helper mono>
          {row.downloaded_bytes ? mb(row.downloaded_bytes) : 'Preparing download'}
          {row.total_bytes > 0 ? ` / ${mb(row.total_bytes)} discovered layers` : ''}
        </Helper>}
      </div>)}
    </div>
    {error && <Helper>{error}</Helper>}
    {isOwner && (error || snapshot?.providers?.some((r) => ['error', 'unknown'].includes(r.state))) &&
      <Button variant="secondary" size="sm" style={{ justifySelf: 'start' }} busy={retrying} onClick={retry}>Retry container setup</Button>}
  </div>
}
