// UpdateCheck.jsx — the update check result (GET /api/updates). Nothing new must
// produce no line and no toast; a new release or new commits on main produce one
// toast for the owner, once per release or head commit, never for a member.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('../api', () => ({ default: { get: vi.fn() } }))
import api from '../api'
import { updateSummary, useUpdateNotice } from '../UpdateCheck'

const RELEASE = { mode: 'release', repo: 'vesaias/JobNavigator', update_available: true, latest: { version: '3.2' }, url: 'https://x/rel', owner: true }
const COMMITS = { mode: 'commit', repo: 'vesaias/JobNavigator', branch: 'main', update_available: true, behind_by: 5, latest: { commit: 'b'.repeat(40) }, owner: true }

describe('updateSummary', () => {
  it('is null when nothing is new or the check is undecided', () => {
    expect(updateSummary(null)).toBeNull()
    expect(updateSummary({ ...RELEASE, update_available: false })).toBeNull()
    expect(updateSummary({ ...COMMITS, update_available: null })).toBeNull()
  })
  it('names the release or counts the commits', () => {
    expect(updateSummary(RELEASE)).toBe('JobNavigator 3.2 is available')
    expect(updateSummary(COMMITS)).toBe('5 new commits on main')
    expect(updateSummary({ ...COMMITS, behind_by: 1 })).toBe('1 new commit on main')
  })
})

describe('useUpdateNotice', () => {
  beforeEach(() => { localStorage.clear(); api.get.mockReset() })

  it('toasts the owner once per release', async () => {
    api.get.mockResolvedValue({ data: RELEASE })
    const push = vi.fn()
    renderHook(() => useUpdateNotice(push))
    await waitFor(() => expect(push).toHaveBeenCalledTimes(1))
    expect(push.mock.calls[0][0].msg).toContain('JobNavigator 3.2 is available')
    renderHook(() => useUpdateNotice(push))
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
    expect(push).toHaveBeenCalledTimes(1)
  })

  it('does not toast a member or an install with nothing new', async () => {
    for (const data of [{ ...RELEASE, owner: false }, { ...RELEASE, update_available: false }]) {
      api.get.mockResolvedValueOnce({ data })
      const push = vi.fn()
      renderHook(() => useUpdateNotice(push))
      await waitFor(() => expect(api.get).toHaveBeenCalled())
      await Promise.resolve()
      expect(push).not.toHaveBeenCalled()
      api.get.mockClear()
    }
  })
})
