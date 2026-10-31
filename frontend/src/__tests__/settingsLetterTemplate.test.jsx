// Settings › Cover letters: the default template picker lists GET /cover-letters/templates by
// their meta.json names under Same as résumé and Last selected, and saves `cover_letter_template`.
// Empty reads as Same as résumé.
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
      '/resumes/templates': [...TEMPLATES, { id: 'modern', name: 'Modern Professional' }],
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
  it('an empty value reads as Same as résumé', async () => {
    mockApi({ cover_letter_template: '' })
    expect((await picker()).textContent).toContain('Same as résumé')
  })

  it('offers Same as résumé and Last selected above the templates', async () => {
    mockApi({ cover_letter_template: 'same_as_resume' })
    fireEvent.click(await picker())
    const names = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(names.slice(0, 4)).toEqual(['Same as résumé', 'Last selected', 'Garamond Modern', 'Inter Modern'])
    fireEvent.click(screen.getByRole('option', { name: /Last selected/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/settings', { cover_letter_template: 'last_selected' }))
  })

  it('lists the templates by name and saves the picked id', async () => {
    mockApi({ cover_letter_template: 'garamond_alt' })
    fireEvent.click(await picker())
    fireEvent.click(await screen.findByRole('option', { name: /Inter Modern/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/settings', { cover_letter_template: 'inter' }))
  })

  it('a stored id this install does not have stays visible', async () => {
    mockApi({ cover_letter_template: 'removed_template' })
    expect((await picker()).textContent).toContain('removed_template — not on this install')
  })
})

describe('Settings › Résumé & tailoring › Default résumé template', () => {
  const resumePicker = async () => {
    render(<MemoryRouter initialEntries={['/settings']}><Settings /></MemoryRouter>)
    return waitFor(() => screen.getByLabelText('Default résumé template'))
  }

  it('an empty value reads as Last selected', async () => {
    mockApi({ resume_template: '' })
    expect((await resumePicker()).textContent).toContain('Last selected')
  })

  it('offers Last selected above every résumé template, and no Same as résumé', async () => {
    mockApi({ resume_template: 'last_selected' })
    fireEvent.click(await resumePicker())
    const names = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(names).toEqual(['Last selected', 'Garamond Modern', 'Inter Modern', 'Modern Professional'])
    fireEvent.click(screen.getByRole('option', { name: /Modern Professional/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/settings', { resume_template: 'modern' }))
  })
})
