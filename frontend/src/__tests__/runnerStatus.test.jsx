import React from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react'
import RunnerStatus from '../screens/RunnerStatus'
import api from '../api'
vi.mock('../api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const data = (rows) => ({ data: { enabled: true, providers: rows } })

describe('provider container status', () => {
  it('shows progress and inactive providers without implying images were deleted', async () => {
    api.get.mockResolvedValue(data([
      { provider: 'codex_cli', state: 'pulling', downloaded_bytes: 1048576, total_bytes: 2097152 },
      { provider: 'claude_code', state: 'absent', message: 'Not selected in any account' },
    ]))
    render(<RunnerStatus accountId="owner" isOwner />)
    await screen.findByText('Codex · Downloading')
    expect(screen.getByText('1.0 MB / 2.0 MB discovered layers')).toBeTruthy()
    expect(screen.getByText('Claude Code · Inactive')).toBeTruthy()
    expect(screen.getByText(/images and logins are kept/)).toBeTruthy()
  })
  it('lets only the owner retry failed provisioning', async () => {
    api.get.mockResolvedValue(data([{ provider: 'codex_cli', state: 'error', message: 'Download failed' }]))
    api.post.mockResolvedValue({ data: { accepted: true } })
    const r = render(<RunnerStatus accountId="owner" isOwner />)
    fireEvent.click(await screen.findByRole('button', { name: 'Retry container setup' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/llm/runners/retry'))
    r.rerender(<RunnerStatus accountId="member" isOwner={false} />)
    await screen.findByText('Codex · Error')
    expect(screen.queryByRole('button')).toBeNull()
  })
  it('does not apply an old account response after switching accounts', async () => {
    let resolveOld
    api.get.mockImplementationOnce(() => new Promise((r) => { resolveOld = r }))
      .mockResolvedValue(data([{ provider: 'claude_code', state: 'ready' }]))
    const r = render(<RunnerStatus accountId="old" />)
    r.rerender(<RunnerStatus accountId="new" />)
    await screen.findByText('Claude Code · Ready')
    resolveOld(data([{ provider: 'codex_cli', state: 'ready' }]))
    await waitFor(() => expect(screen.queryByText('Codex · Ready')).toBeNull())
  })
  it('explains manual mode', async () => {
    api.get.mockResolvedValue({ data: { enabled: false, providers: [] } })
    render(<RunnerStatus accountId="owner" isOwner />)
    await screen.findByText(/Automatic container management is disabled/)
  })
})
