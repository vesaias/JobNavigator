// Searches screen: JobSpy source blocks, Test-run errors and the country field.
// Restores the v2 halves of the deleted sourceBlocks / testRunErrors specs and
// re-targets the classic-only country spec at screens/Searches.jsx.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Searches from '../screens/Searches'
import { BLOCKED_BADGE, MODE_BLOCKS, MODE_TERMS, SOURCE_BLOCKS } from '../sourceBlocks'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))
const api = (await import('../api')).default

const ZIP_TEXT = 'the US site redirects this location to a regional ZipRecruiter site, which this scraper does not read: HTTP 307'
const SEARCH = {
  id: 's1', name: 'TPM', search_mode: 'keyword', search_term: 'tpm', location: '',
  country: 'usa', active: true, sources: ['indeed', 'zip_recruiter'],
}
const TEST_RESULT = {
  search_name: 'TPM', duration: 1, raw_count: 1, after_filter: 1,
  source_breakdown: { indeed: 1 }, source_errors: { zip_recruiter: ZIP_TEXT },
  company_breakdown: {}, jobs: [], config: { sources: ['indeed', 'zip_recruiter'] },
}
const COUNTRIES = [{ value: 'usa', label: 'United States' }, { value: 'canada', label: 'Canada' }]

const mockApi = (searches) => {
  api.get.mockImplementation((path) => {
    if (path === '/searches') return Promise.resolve({ data: searches })
    if (path === '/searches/countries') return Promise.resolve({ data: COUNTRIES })
    return Promise.resolve({ data: path === '/health/entities' ? {} : [] })
  })
  api.post.mockImplementation((path) => Promise.resolve(
    path.endsWith('/test') ? { status: 200, data: TEST_RESULT } : { status: 200, data: {} }))
  api.patch.mockResolvedValue({ data: {} })
}

const renderScreen = () => render(<MemoryRouter><Searches /></MemoryRouter>)

describe('Source blocks · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  const chip = (name) => screen.getAllByRole('button').find((b) => b.textContent.includes(name))

  it('flags only ZipRecruiter and Google Jobs, and a flagged board still submits', async () => {
    mockApi([])
    renderScreen()
    fireEvent.click((await screen.findAllByText('+ New search'))[0])
    await waitFor(() => expect(chip('ZipRecruiter')).toBeTruthy())

    expect(within(chip('ZipRecruiter')).queryByText(BLOCKED_BADGE)).not.toBeNull()
    expect(within(chip('Google Jobs')).queryByText(BLOCKED_BADGE)).not.toBeNull()
    expect(within(chip('Indeed')).queryByText(BLOCKED_BADGE)).toBeNull()
    expect(within(chip('LinkedIn')).queryByText(BLOCKED_BADGE)).toBeNull()
    for (const reason of Object.values(SOURCE_BLOCKS)) {
      expect(screen.getByText(reason, { exact: false })).toBeTruthy()
    }

    // Off with the chip, back on with a click on the badge itself.
    fireEvent.click(chip('ZipRecruiter'))
    expect(chip('ZipRecruiter').getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(within(chip('ZipRecruiter')).getByText(BLOCKED_BADGE))
    expect(chip('ZipRecruiter').getAttribute('aria-pressed')).toBe('true')

    fireEvent.change(screen.getByPlaceholderText('e.g. TPM roles — Tier 1'), { target: { value: 'TPM' } })
    fireEvent.click(screen.getByText('Create search'))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    expect(api.post.mock.calls[0][0]).toBe('/searches')
    expect(api.post.mock.calls[0][1].sources).toContain('zip_recruiter')
    expect(api.post.mock.calls[0][1].sources).toContain('google')
  })
})

describe('Test run · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  it('shows a failed board and its text in the Test run result', async () => {
    mockApi([SEARCH])
    renderScreen()
    fireEvent.click(await screen.findByTitle(/^Preview run/))
    expect(await screen.findByText(`failed: ${ZIP_TEXT}`, { exact: false })).toBeTruthy()
    expect(screen.getByText('indeed 1')).toBeTruthy()
  })
})

describe('Country · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  it('new keyword search shows the Country select, defaults to usa and sends it', async () => {
    mockApi([])
    renderScreen()
    fireEvent.click((await screen.findAllByText('+ New search'))[0])
    expect(await screen.findByLabelText('Country')).toBeTruthy()

    fireEvent.change(screen.getByPlaceholderText('e.g. TPM roles — Tier 1'), { target: { value: 'TPM' } })
    fireEvent.click(screen.getByText('Create search'))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    expect(api.post.mock.calls[0][1].country).toBe('usa')
  })

  it('editing a keyword search lets the country change and sends the new value', async () => {
    mockApi([SEARCH])
    renderScreen()
    fireEvent.click(await screen.findByText('TPM'))
    const trigger = await screen.findByLabelText('Country')
    await waitFor(() => expect(within(trigger).queryByText('United States')).not.toBeNull())
    fireEvent.click(trigger)
    fireEvent.click(await screen.findByRole('option', { name: /Canada/ }))
    fireEvent.click(screen.getByText('Save changes'))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][0]).toBe('/searches/s1')
    expect(api.patch.mock.calls[0][1].country).toBe('canada')
  })

  it('a non-keyword search has no Country field and sends no country', async () => {
    mockApi([{ ...SEARCH, id: 's2', name: 'Levels', search_mode: 'levels_fyi', direct_url: 'https://www.levels.fyi/jobs' }])
    renderScreen()
    fireEvent.click(await screen.findByText('Levels'))
    await screen.findByText('Save changes')
    expect(screen.queryByLabelText('Country')).toBeNull()
    fireEvent.click(screen.getByText('Save changes'))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][1]).not.toHaveProperty('country')
  })
})

describe('CaribbeanJobs · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  const CJ = { ...SEARCH, id: 's3', name: 'Caribbean', search_mode: 'caribbeanjobs', search_term: 'accountant', sources: [] }
  const CF_TEXT = 'CaribbeanJobs is behind a Cloudflare challenge from this network; the scraper cannot pass it (HTTP 403)'

  it('the editor shows the Cloudflare block and the terms notice', async () => {
    mockApi([CJ])
    renderScreen()
    fireEvent.click(await screen.findByText('Caribbean'))
    await screen.findByText('Save changes')
    expect(screen.getByText(MODE_BLOCKS.caribbeanjobs, { exact: false })).toBeTruthy()
    expect(screen.getByText(MODE_TERMS.caribbeanjobs)).toBeTruthy()
  })

  it('a Test that hits the challenge shows the readable error', async () => {
    mockApi([CJ])
    api.post.mockImplementation(() => Promise.resolve({ status: 200, data: { search_name: 'Caribbean', error: CF_TEXT } }))
    renderScreen()
    fireEvent.click(await screen.findByTitle(/^Preview run/))
    expect(await screen.findByText(CF_TEXT)).toBeTruthy()
  })

  it('a Test that sampled the detail pages says so', async () => {
    const note = 'Details sampled: the job pages of the first 20 of 31 jobs that passed the title and company filters were read.'
    mockApi([CJ])
    api.post.mockImplementation(() => Promise.resolve({ status: 200, data: {
      search_name: 'Caribbean', duration: 1, raw_count: 31, after_filter: 31, source_breakdown: { caribbeanjobs: 31 },
      company_breakdown: {}, jobs: [], preview_note: note, config: { mode: 'caribbeanjobs', search_term: 'accountant' },
    } }))
    renderScreen()
    fireEvent.click(await screen.findByTitle(/^Preview run/))
    expect(await screen.findByText(note)).toBeTruthy()
  })
})

describe('Himalayas and Eluta · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  const HIM = { ...SEARCH, id: 's5', name: 'Remote designers', search_mode: 'himalayas', search_term: 'designer', country: 'canada', direct_url: '', sources: [] }
  const ELU = { ...SEARCH, id: 's6', name: 'Vancouver designers', search_mode: 'eluta', search_term: 'designer', location: 'Vancouver', direct_url: '', sources: [] }

  it('each mode has its badge and summary', async () => {
    mockApi([HIM, ELU])
    renderScreen()
    expect((await screen.findByText('HIMALAYAS')).className).toContain('sm-himalayas')
    expect(screen.getByText('ELUTA').className).toContain('sm-eluta')
    expect(screen.getByText(/“designer” · Remote · canada/)).toBeTruthy()
    expect(screen.getByText(/“designer” · Vancouver/)).toBeTruthy()
  })

  it('the Himalayas editor has Country and no Location or Remote', async () => {
    mockApi([HIM])
    renderScreen()
    fireEvent.click(await screen.findByText('Remote designers'))
    await screen.findByText('Save changes')
    expect(screen.getByText(/Every job is remote/)).toBeTruthy()
    expect(screen.getByLabelText('Country')).toBeTruthy()
    expect(screen.queryByLabelText('Location')).toBeNull()
    expect(screen.queryByLabelText('Remote')).toBeNull()
  })

  it('the Eluta editor has Location, the daily-limit note and no Country', async () => {
    mockApi([ELU])
    renderScreen()
    fireEvent.click(await screen.findByText('Vancouver designers'))
    await screen.findByText('Save changes')
    expect(screen.getByText(/run interval of 1440 minutes/)).toBeTruthy()
    expect(screen.getByLabelText('Location')).toBeTruthy()
    expect(screen.queryByLabelText('Country')).toBeNull()
    expect(screen.queryByText(/Results wanted/)).toBeNull()
  })
})

describe('TrulyRemoteWork · v2 Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  // No term and no URL: the mode reads the whole board.
  const TR = { ...SEARCH, id: 's4', name: 'Remote board', search_mode: 'trulyremote', search_term: '', direct_url: '', results_wanted: 25, sources: [] }

  it('the row shows the olive badge and the per-run summary', async () => {
    mockApi([TR])
    renderScreen()
    const badge = await screen.findByText('TRULYREMOTEWORK.COM')
    expect(badge.className).toContain('sm-trulyremote')
    expect(screen.getByText(/Worldwide remote · max 25 new/)).toBeTruthy()
  })

  it('the editor explains the mode and labels the cap as new jobs per run', async () => {
    mockApi([TR])
    renderScreen()
    fireEvent.click(await screen.findByText('Remote board'))
    await screen.findByText('Save changes')
    expect(screen.getByText(/full corpus of worldwide-remote roles/)).toBeTruthy()
    expect(screen.getByText(/narrow it with the title and company filters below/)).toBeTruthy()
    expect(screen.getByLabelText('New jobs per run · 1–500')).toBeTruthy()
    expect(screen.getByText(/this caps how many new jobs’ pages one run opens/)).toBeTruthy()
    expect(screen.queryByText(/Results wanted/)).toBeNull()
  })

  it('Test runs with no term or URL and shows the worldwide-remote params and the body marker', async () => {
    mockApi([TR])
    api.post.mockImplementation(() => Promise.resolve({ status: 200, data: {
      search_name: 'Remote board', duration: 1, raw_count: 2, after_filter: 2, source_breakdown: { trulyremote: 2 },
      company_breakdown: {}, body_phrase_count: 3, details_sampled: 1, detail_limit: 20,
      jobs: [
        { title: 'Role A', company: 'Acme', url: 'https://trulyremotework.com/jobs/a', source: 'trulyremote', kept: true, location: 'Worldwide' },
        { title: 'Role B', company: 'Acme', url: 'https://trulyremotework.com/jobs/b', source: 'trulyremote', kept: true, location: 'Worldwide', body_checked: false },
      ],
      config: { mode: 'trulyremote', results_wanted: 25 },
    } }))
    renderScreen()
    // Not blocked for a missing term or URL (NEEDS_QUERY): the click reaches the API.
    fireEvent.click(await screen.findByTitle(/^Preview run/))
    await waitFor(() => expect(api.post.mock.calls[0]?.[0]).toBe('/searches/s4/test'))
    expect(await screen.findByText('worldwide remote · 25 new per run')).toBeTruthy()
    expect(screen.getAllByText('posting body text check was skipped')).toHaveLength(1)
  })
})

describe('Direct-link rate · Searches', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  it('names the share of a search’s jobs with a direct link, from five jobs on', async () => {
    mockApi([
      { ...SEARCH, id: 'a', name: 'Many', direct_rate: { direct: 6, total: 9 } },
      { ...SEARCH, id: 'b', name: 'Few', search_term: 'few', direct_rate: { direct: 1, total: 3 } },
    ])
    renderScreen()
    expect(await screen.findByText(/67% direct links/)).toBeTruthy()
    expect(screen.queryByText(/33% direct links/)).toBeNull()
  })
})
