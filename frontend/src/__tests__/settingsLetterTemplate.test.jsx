// Settings › Cover letters: the default template picker lists GET /cover-letters/templates by
// their meta.json names and saves `cover_letter_template`. Empty reads as Garamond Modern.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  authFailure: () => null,
}))
globalThis.__APP_VERSION__ = 'test'
const api = (await import('../api')).default
const { default: Settings } = await import('../screens/Settings')

const OWNER = { id: 'o1', name: 'Jordan', color: '#2f6fed', role: 'owner', has_pin: false }
const BASE = { cover_letter_voice_presets: [], autofill_field_patterns: {}, autofill_option_synonyms: {} }
const TEMPLATES = [
  { id: 'garamond_alt', name: 'Garamond Modern' },
  { id: 'inter', name: 'Inter Modern' },
]

const mockApi = (settings) => {
  api.get.mockImplementation((path) => {
    const data = {
      '/auth/me': { account: OWNER, accounts_count: 1, owner_has_pin: false },
      '/accounts': { accounts: [{ ...OWNER, is_self: true }], max_accounts: 5, self_id: 'o1' },
      '/resumes': [],
      '/cover-letters/templates': TEMPLATES,
      '/settings': { ...BASE, ...settings },
    }[path]
    return Promise.resolve({ data: data ?? {} })
  })
  api.patch.mockResolvedValue({ data: {} })
}

const picker = async () => {
  render(<MemoryRouter initialEntries={['/settings']}><Settings /></MemoryRouter>)
  return waitFor(() => screen.getByLabelText('Default template'))
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('Settings › Cover letters › Default template', () => {
  it('an empty value reads as Garamond Modern', async () => {
    mockApi({ cover_letter_template: '' })
    expect((await picker()).textContent).toContain('Garamond Modern')
  })

  it('lists the templates by name and saves the picked id', async () => {
    mockApi({ cover_letter_template: 'garamond_alt' })
    fireEvent.click(await picker())
    fireEvent.click(await screen.findByRole('option', { name: /Inter Modern/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/settings', { cover_letter_template: 'inter' }))
  })

  it('a stored id this install does not have stays visible', async () => {
    mockApi({ cover_letter_template: 'garamond' })
    expect((await picker()).textContent).toContain('garamond — not on this install')
  })
})
