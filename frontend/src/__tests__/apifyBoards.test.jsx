// The Apify board list belongs to the backend (GET /searches/apify-boards), so
// a board the frontend has never heard of must still render, default and label.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SearchManager from '../classic/SearchManager'
import { apifySourceLabel, boardLabel } from '../apifyBoards'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
const api = (await import('../api')).default

const BOARDS = [
  { value: 'glassdoor', label: 'Glassdoor', hint: 'Glassdoor hint', actor: 'x/glassdoor' },
  { value: 'indeed', label: 'Indeed', hint: 'Indeed hint', actor: 'misceres/indeed-scraper' },
]

describe('Apify board helpers', () => {
  it('names a board, and an Apify job source, from the backend list', () => {
    expect(boardLabel(BOARDS, 'glassdoor')).toBe('Glassdoor')
    expect(boardLabel(BOARDS, 'monster')).toBe('monster')
    expect(apifySourceLabel(BOARDS, 'apify_indeed')).toBe('Indeed (Apify)')
    expect(apifySourceLabel(BOARDS, 'apify_indeed', ' via Apify')).toBe('Indeed via Apify')
    expect(apifySourceLabel(BOARDS, 'jobspy_indeed')).toBeNull()
    expect(apifySourceLabel([], 'apify_dice')).toBe('dice (Apify)')
  })
})

describe('Apify boards · classic SearchManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation((path) => {
      if (path === '/searches/apify-boards') return Promise.resolve({ data: BOARDS })
      if (path === '/searches/countries') return Promise.resolve({ data: [{ value: 'usa', label: 'United States' }] })
      return Promise.resolve({ data: path === '/health/entities' ? {} : [] })
    })
    api.post.mockResolvedValue({ status: 200, data: {} })
  })

  it('offers every backend board, picks the first by default and saves the choice', async () => {
    render(<SearchManager />)
    fireEvent.click(screen.getByText('New Search'))
    fireEvent.change(screen.getByDisplayValue('Keyword (JobSpy)'), { target: { value: 'apify' } })

    const box = (name) => screen.getByText(name, { selector: 'label' }).querySelector('input')
    await waitFor(() => expect(box('Glassdoor')).toBeTruthy())
    expect(box('Glassdoor').checked).toBe(true)
    expect(box('Indeed').checked).toBe(false)
    expect(screen.getByText(': Glassdoor hint', { exact: false })).toBeTruthy()
    expect(screen.queryByText(': Indeed hint', { exact: false })).toBeNull()   // hints only for ticked boards

    fireEvent.click(box('Indeed'))
    expect(screen.getByText(': Indeed hint', { exact: false })).toBeTruthy()
    fireEvent.click(screen.getByTitle('Save'))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [, payload] = api.post.mock.calls.find(([p]) => p === '/searches')
    expect(payload.search_mode).toBe('apify')
    expect(payload.sources).toEqual(['glassdoor', 'indeed'])
  })
})
