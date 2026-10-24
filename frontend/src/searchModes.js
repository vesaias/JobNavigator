// Every search mode the dashboard knows, in one place. The backend's table is
// backend/scraper/search_modes.py; backend/tests/test_search_modes.py fails when the two
// differ (keys and order, labels, extension, needsQuery, sources defaults), so change both.
// One mode per line, plain literals: the test reads this file with a regex.
export const SEARCH_MODES = [
  { key: 'keyword', label: 'Keyword (JobSpy)', badge: 'JOBSPY', cls: 'sm-keyword', extension: false, needsQuery: false, sources: ['linkedin', 'indeed', 'zip_recruiter', 'google'] },
  { key: 'levels_fyi', label: 'Levels.fyi', badge: 'LEVELS.FYI', cls: 'sm-levels', extension: false, needsQuery: false, sources: [] },
  { key: 'linkedin_personal', label: 'LinkedIn Personal', badge: 'LINKEDIN PERSONAL', cls: 'sm-lipersonal', extension: false, needsQuery: false, sources: ['recommended', 'top-applicant'] },
  { key: 'jobright', label: 'Jobright.ai', badge: 'JOBRIGHT.AI', cls: 'sm-jobright', extension: false, needsQuery: false, sources: [] },
  { key: 'freehire', label: 'freehire.me', badge: 'FREEHIRE.ME', cls: 'sm-freehire', extension: false, needsQuery: true, sources: [] },
  { key: 'apify', label: 'Apify', badge: 'APIFY', cls: 'sm-apify', extension: false, needsQuery: false, sources: [] },
  { key: 'caribbeanjobs', label: 'CaribbeanJobs.com', badge: 'CARIBBEANJOBS.COM', cls: 'sm-caribbeanjobs', extension: false, needsQuery: true, sources: [] },
  { key: 'trulyremote', label: 'TrulyRemoteWork.com', badge: 'TRULYREMOTEWORK.COM', cls: 'sm-trulyremote', extension: false, needsQuery: false, sources: [] },
  { key: 'creative', label: 'Creative boards', badge: 'CREATIVE', cls: 'sm-creative', extension: false, needsQuery: false, sources: ['behance', 'hollylist', 'wanacreate'] },
  { key: 'linkedin_extension', label: 'LinkedIn Extension', badge: 'EXTENSION', cls: 'sm-extension', extension: true, needsQuery: false, sources: [] },
  { key: 'extension', label: 'Extension', badge: 'EXTENSION', cls: 'sm-extension', extension: true, needsQuery: false, sources: [] },
]

const BY_KEY = Object.fromEntries(SEARCH_MODES.map((m) => [m.key, m]))

export const modeOf = (key) => BY_KEY[key || 'keyword'] || null
// [key, label] for the Mode select: every mode a user can create (not the built-in extension ones).
export const MODE_OPTIONS = SEARCH_MODES.filter((m) => !m.extension).map((m) => [m.key, m.label])
export const isExtensionMode = (key) => !!modeOf(key)?.extension
// Every mode with a scraper has a Test.
export const isTestable = (key) => !!modeOf(key) && !modeOf(key).extension
export const needsQuery = (key) => !!modeOf(key)?.needsQuery
// [badge label, badge class]; an unknown mode shows its own key.
export const modeBadge = (key) => {
  const m = modeOf(key)
  return m ? [m.badge, m.cls] : [String(key || '?').toUpperCase(), 'sm-extension']
}
// `sources` a search gets when it switches to this mode (Apify's first board comes from the API).
export const defaultSources = (key) => [...(modeOf(key)?.sources || [])]
