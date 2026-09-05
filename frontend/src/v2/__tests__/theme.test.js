// theme.js — the two appearance axes and, above all, the storage migration.
//
// `migrateKeys()` and `readMode()`'s legacy fold-in run at MODULE LOAD, so every
// migration case has to seed localStorage FIRST and then load a fresh copy of the
// module (vi.resetModules() + dynamic import()). The module also stamps <html> on
// load via apply(), which is how the resulting state is observed here without
// reaching into a private variable: data-appearance is the resolved light|dark,
// data-theme is the palette, and .dark mirrors the classic shell.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const APPEARANCE_KEY = 'jobnavigator_appearance'
const THEME_KEY = 'jobnavigator_theme'
const LEGACY_KEY = 'jobnavigator_dark_mode'
const LEGACY_THEME_KEY = 'jobnavigator_skin'

/** Every key/value currently in localStorage, for "nothing changed" assertions. */
const snap = () => Object.fromEntries(
  Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i))
    .map((k) => [k, localStorage.getItem(k)]),
)

const html = () => document.documentElement
const attrs = () => ({
  appearance: html().getAttribute('data-appearance'),
  theme: html().getAttribute('data-theme'),
  dark: html().classList.contains('dark'),
})

// jsdom ships no matchMedia; the module's mq() swallows that and reports "not
// dark". Install a real one when a test needs `system` to resolve either way.
function mockMatchMedia(matches) {
  const listeners = new Set()
  const mql = {
    matches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_, l) => listeners.add(l),
    removeEventListener: (_, l) => listeners.delete(l),
    addListener: (l) => listeners.add(l),
    removeListener: (l) => listeners.delete(l),
  }
  window.matchMedia = vi.fn(() => mql)
  return mql
}

/** Seed localStorage, drop the module cache, load a fresh theme.js. */
async function load(seed = {}) {
  localStorage.clear()
  for (const [k, v] of Object.entries(seed)) if (v !== undefined) localStorage.setItem(k, v)
  vi.resetModules()
  return import('../theme')
}

beforeEach(() => {
  localStorage.clear()
  html().removeAttribute('data-appearance')
  html().removeAttribute('data-theme')
  html().classList.remove('dark')
  delete window.matchMedia
})
afterEach(() => { delete window.matchMedia })

// ── storage migration (runs at module load) ─────────────────────────────────
describe('storage migration', () => {
  it('(a) a legacy light|dark value in jobnavigator_theme becomes the appearance', async () => {
    await load({ [THEME_KEY]: 'dark' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
    expect(attrs().appearance).toBe('dark')
    expect(attrs().dark).toBe(true)
    // 'dark' is not a palette name, so the theme falls back rather than painting nothing
    expect(attrs().theme).toBe('default')
  })

  it('(a) the same for "light" and "system"', async () => {
    await load({ [THEME_KEY]: 'light' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    await load({ [THEME_KEY]: 'system' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('system')
    expect(attrs().appearance).toBe('light')      // no matchMedia -> not dark
  })

  it('(b) jobnavigator_skin moves into jobnavigator_theme and is removed', async () => {
    await load({ [LEGACY_THEME_KEY]: 'cobalt' })
    expect(localStorage.getItem(THEME_KEY)).toBe('cobalt')
    expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull()
    expect(attrs().theme).toBe('cobalt')
  })

  it('(b) an unknown skin value still moves, then validates down to default', async () => {
    await load({ [LEGACY_THEME_KEY]: 'chartreuse' })
    expect(localStorage.getItem(THEME_KEY)).toBe('chartreuse')
    expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull()
    expect(attrs().theme).toBe('default')
  })

  it('(c) both at once: appearance is read out BEFORE the skin overwrites the key', async () => {
    await load({ [THEME_KEY]: 'dark', [LEGACY_THEME_KEY]: 'alt' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')   // the old light|dark survived
    expect(localStorage.getItem(THEME_KEY)).toBe('alt')         // the palette took the key
    expect(localStorage.getItem(LEGACY_THEME_KEY)).toBeNull()
    expect(attrs()).toEqual({ appearance: 'dark', theme: 'alt', dark: true })
  })

  it('(d) the legacy jobnavigator_dark_mode boolean is folded in on first read and written back', async () => {
    await load({ [LEGACY_KEY]: 'true' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
    expect(attrs().appearance).toBe('dark')

    await load({ [LEGACY_KEY]: 'false' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    expect(attrs().appearance).toBe('light')
  })

  it('(d) anything other than the string "true" folds in as light', async () => {
    for (const v of ['1', 'TRUE', 'yes', '']) {
      await load({ [LEGACY_KEY]: v })
      expect(localStorage.getItem(APPEARANCE_KEY), v).toBe('light')
    }
  })

  it('(d) an empty store settles on light and persists it', async () => {
    await load({})
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    expect(attrs()).toEqual({ appearance: 'light', theme: 'default', dark: false })
  })

  it('(e) an already-valid appearance is never overwritten by the legacy keys', async () => {
    await load({ [APPEARANCE_KEY]: 'light', [THEME_KEY]: 'dark', [LEGACY_KEY]: 'true' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    expect(attrs().appearance).toBe('light')
  })

  it('(e) an invalid appearance does fall through to the legacy value', async () => {
    await load({ [APPEARANCE_KEY]: 'sepia', [THEME_KEY]: 'dark' })
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
  })

  it('migrating leaves an already-migrated store alone on a second load', async () => {
    await load({ [LEGACY_THEME_KEY]: 'win98', [THEME_KEY]: 'dark' })
    const after = snap()
    vi.resetModules()
    await import('../theme')
    expect(snap()).toEqual(after)
  })
})

// ── readTheme validation ────────────────────────────────────────────────────
describe('theme validation', () => {
  it('keeps every name in THEMES', async () => {
    const { THEMES } = await load({})
    for (const t of THEMES) {
      await load({ [THEME_KEY]: t })
      expect(attrs().theme, t).toBe(t)
    }
  })
  it('falls back to default for an unknown, absent or null stored value', async () => {
    for (const v of ['chartreuse', '', 'null', 'DEFAULT', undefined]) {
      await load(v === undefined ? {} : { [THEME_KEY]: v })
      expect(attrs().theme, String(v)).toBe('default')
    }
  })
})

// ── themeOptions ────────────────────────────────────────────────────────────
describe('themeOptions', () => {
  it('offers exactly the shipped picker for a shipped theme, with no duplicate', async () => {
    const { themeOptions, THEME_PICKER, THEME_LABEL } = await load({})
    for (const t of THEME_PICKER) {
      const opts = themeOptions(t)
      expect(opts, t).toHaveLength(THEME_PICKER.length)
      expect(opts.map((o) => o[0]), t).toEqual(THEME_PICKER)
      expect(new Set(opts.map((o) => o[0])).size, t).toBe(opts.length)
    }
    expect(themeOptions('default')[0]).toEqual(['default', THEME_LABEL.default])
  })
  it('prepends a hidden current theme so the Settings box never reads blank', async () => {
    const { themeOptions, THEME_PICKER, THEME_LABEL, THEMES } = await load({})
    for (const t of THEMES.filter((x) => !THEME_PICKER.includes(x))) {
      const opts = themeOptions(t)
      expect(opts.length, t).toBe(THEME_PICKER.length + 1)
      expect(opts[0], t).toEqual([t, THEME_LABEL[t]])
      expect(opts.slice(1).map((o) => o[0]), t).toEqual(THEME_PICKER)
    }
    expect(themeOptions('alt')[0]).toEqual(['alt', THEME_LABEL.alt])
    expect(themeOptions('tone2')[0]).toEqual(['tone2', THEME_LABEL.tone2])
  })
  it('labels an entirely unknown current value with the value itself', async () => {
    const { themeOptions } = await load({})
    expect(themeOptions('chartreuse')[0]).toEqual(['chartreuse', 'chartreuse'])
  })
  it('THEME_PICKER is a subset of THEMES and every THEMES name has a label', async () => {
    const { THEMES, THEME_PICKER, THEME_LABEL } = await load({})
    for (const t of THEME_PICKER) expect(THEMES, t).toContain(t)
    for (const t of THEMES) expect(typeof THEME_LABEL[t], t).toBe('string')
  })
})

// ── system preference ───────────────────────────────────────────────────────
describe('systemPrefersDark / resolveMode', () => {
  it('reads the media query both ways', async () => {
    mockMatchMedia(true)
    let m = await load({})
    expect(m.systemPrefersDark()).toBe(true)
    expect(m.resolveMode('system')).toBe('dark')

    mockMatchMedia(false)
    m = await load({})
    expect(m.systemPrefersDark()).toBe(false)
    expect(m.resolveMode('system')).toBe('light')
  })
  it('reports light when matchMedia is missing or throws', async () => {
    const m = await load({})                       // jsdom: no window.matchMedia
    expect(m.systemPrefersDark()).toBe(false)
    window.matchMedia = () => { throw new Error('blocked') }
    expect(m.systemPrefersDark()).toBe(false)
    expect(m.resolveMode('system')).toBe('light')
  })
  it('passes an explicit mode straight through', async () => {
    mockMatchMedia(true)
    const { resolveMode } = await load({})
    expect(resolveMode('light')).toBe('light')
    expect(resolveMode('dark')).toBe('dark')
  })
  it('a stored "system" boots dark when the OS is dark', async () => {
    mockMatchMedia(true)
    await load({ [APPEARANCE_KEY]: 'system' })
    expect(attrs()).toEqual({ appearance: 'dark', theme: 'default', dark: true })
  })
})

// ── setters ─────────────────────────────────────────────────────────────────
describe('setMode / setTheme / cycleMode', () => {
  it('setMode writes the key, mirrors the legacy boolean and stamps <html>', async () => {
    const { setMode } = await load({})
    setMode('dark')
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
    expect(localStorage.getItem(LEGACY_KEY)).toBe('true')
    expect(attrs()).toEqual({ appearance: 'dark', theme: 'default', dark: true })

    setMode('light')
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    expect(localStorage.getItem(LEGACY_KEY)).toBe('false')
    expect(attrs().dark).toBe(false)
  })
  it('setMode("system") mirrors the RESOLVED value into the legacy boolean', async () => {
    mockMatchMedia(true)
    const { setMode } = await load({})
    setMode('system')
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('system')
    expect(localStorage.getItem(LEGACY_KEY)).toBe('true')
    expect(attrs().appearance).toBe('dark')
  })
  it('setMode rejects junk without touching storage or the DOM', async () => {
    const { setMode } = await load({})
    setMode('dark')
    const before = snap()
    for (const bad of ['purple', '', null, undefined, 0, 'Dark', ['dark']]) setMode(bad)
    expect(snap()).toEqual(before)
    expect(attrs().appearance).toBe('dark')
  })
  it('setTheme stores a known palette', async () => {
    const { setTheme, THEMES } = await load({})
    for (const t of THEMES) {
      setTheme(t)
      expect(localStorage.getItem(THEME_KEY), t).toBe(t)
      expect(attrs().theme, t).toBe(t)
    }
  })
  it('setTheme coerces junk to default rather than storing it', async () => {
    const { setTheme } = await load({})
    setTheme('cobalt')
    for (const bad of ['chartreuse', '', null, undefined, 42]) {
      setTheme(bad)
      expect(localStorage.getItem(THEME_KEY), String(bad)).toBe('default')
      expect(attrs().theme, String(bad)).toBe('default')
      setTheme('cobalt')
    }
  })
  it('cycleMode runs light -> dark -> system -> light', async () => {
    const { cycleMode } = await load({})           // empty store boots to light
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    cycleMode(); expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
    cycleMode(); expect(localStorage.getItem(APPEARANCE_KEY)).toBe('system')
    cycleMode(); expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
    cycleMode(); expect(localStorage.getItem(APPEARANCE_KEY)).toBe('dark')
  })
  it('cycleMode starts from the stored mode, not from the top', async () => {
    const { cycleMode } = await load({ [APPEARANCE_KEY]: 'system' })
    cycleMode()
    expect(localStorage.getItem(APPEARANCE_KEY)).toBe('light')
  })
})

// ── small exported surface ──────────────────────────────────────────────────
describe('exported constants and helpers', () => {
  it('MODES / MODE_OPTIONS / MODE_LABEL / MODE_ICON line up', async () => {
    const { MODES, MODE_OPTIONS, MODE_LABEL, MODE_ICON } = await load({})
    expect(MODES).toEqual(['light', 'dark', 'system'])
    expect(MODE_OPTIONS).toEqual([['light', 'Light'], ['dark', 'Dark'], ['system', 'System']])
    for (const m of MODES) {
      expect(typeof MODE_LABEL[m], m).toBe('string')
      expect(typeof MODE_ICON[m], m).toBe('string')   // three glyphs for a three-state control
    }
    expect(new Set(Object.values(MODE_ICON)).size).toBe(3)
  })
  it('themeAttrs spreads the two attributes a .jn-v2 root mirrors', async () => {
    const { themeAttrs } = await load({})
    expect(themeAttrs({ resolved: 'dark', theme: 'alt' }))
      .toEqual({ 'data-appearance': 'dark', 'data-theme': 'alt' })
    expect(themeAttrs({ resolved: 'light', theme: 'default', mode: 'system' }))
      .toEqual({ 'data-appearance': 'light', 'data-theme': 'default' })
  })
  it('appearanceTitle names the mode, falling back to the raw value', async () => {
    const { appearanceTitle } = await load({})
    expect(appearanceTitle('dark')).toBe('Appearance: Dark — click to switch')
    expect(appearanceTitle('system')).toBe('Appearance: System — click to switch')
    expect(appearanceTitle('weird')).toBe('Appearance: weird — click to switch')
  })
})

// ── unreadable storage ──────────────────────────────────────────────────────
describe('ls() fallback when localStorage throws', () => {
  const install = () => {
    const throwing = {
      getItem() { throw new Error('SecurityError') },
      setItem() { throw new Error('SecurityError') },
      removeItem() { throw new Error('SecurityError') },
      clear() { throw new Error('SecurityError') },
      key() { throw new Error('SecurityError') },
      get length() { throw new Error('SecurityError') },
    }
    const real = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', { value: throwing, configurable: true })
    return () => (real ? Object.defineProperty(window, 'localStorage', real) : delete window.localStorage)
  }

  it('loads, migrates and boots to the defaults without throwing', async () => {
    const restore = install()
    try {
      vi.resetModules()
      const m = await import('../theme')
      expect(attrs()).toEqual({ appearance: 'light', theme: 'default', dark: false })
      // the setters swallow the write too, and still move the DOM
      expect(() => m.setMode('dark')).not.toThrow()
      expect(attrs().appearance).toBe('dark')
      expect(() => m.setTheme('cobalt')).not.toThrow()
      expect(attrs().theme).toBe('cobalt')
      expect(() => m.cycleMode()).not.toThrow()
    } finally { restore() }
  })
})
