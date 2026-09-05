// The one place the app decides what it looks like. Two independent axes, stored
// per browser (never the DB): appearance (light|dark|system, `jobnavigator_appearance`) and theme (the palette, `jobnavigator_theme`).
//
// default/alt are the two designed themes; tone1-3 ramp toward editorial in OKLab.
// Adding a theme is two palette blocks in theme.css plus one line here — nothing else.
//
// `resolved` is the light|dark actually painted (system follows prefers-color-scheme
// live); `mode` is what the user picked. Every consumer subscribes here so one click moves both shells with no reload.
//
// ATTRIBUTE HOSTS: <html> gets data-appearance/data-theme + .dark from index.html's
// boot script before React mounts, then apply() re-stamps them on every change.
// Each .jn-v2 root mirrors the same two attributes via themeAttrs() — never read localStorage directly in a component.

import { useSyncExternalStore } from 'react'

const APPEARANCE_KEY = 'jobnavigator_appearance'
const THEME_KEY = 'jobnavigator_theme'
const LEGACY_KEY = 'jobnavigator_dark_mode'   // legacy boolean, migrated once
const LEGACY_THEME_KEY = 'jobnavigator_skin'  // old name for THEME_KEY

export const MODES = ['light', 'dark', 'system']
export const THEMES = ['default', 'tone1', 'tone2', 'tone3', 'editorial', 'alt', 'cobalt', 'saas', 'win98']

// Three-state control (Light → Dark → System), so it needs three glyphs.
export const MODE_ICON = { light: '◐', dark: '◑', system: '◒' }
export const MODE_LABEL = { light: 'Light', dark: 'Dark', system: 'System' }
export const MODE_OPTIONS = MODES.map((m) => [m, MODE_LABEL[m]])
export const THEME_LABEL = {
  default: 'Default — warm paper',
  tone1: 'Tone 1 — ¼ toward Editorial',
  tone2: 'Tone 2 — ½ toward Editorial',
  tone3: 'Tone 3 — ¾ toward Editorial',
  editorial: 'Editorial — original board tones',
  alt: 'Alt — cool slate',
  cobalt: 'Cobalt — IBM Plex blue',
  saas: 'SaaS — system neutral',
  win98: 'Win98 — desktop grey',
}
export const THEME_OPTIONS = THEMES.map((s) => [s, THEME_LABEL[s]])

const ls = (fn, fallback) => { try { return fn(window.localStorage) } catch { return fallback } }

// ── storage migration ───────────────────────────────────────────────────────
// jobnavigator_theme now holds the palette (previously jobnavigator_skin); order
// matters — read the old light|dark value out of THEME_KEY before the skin value overwrites it. Must match index.html's boot script step for step.
function migrateKeys(s) {
  const appearance = s.getItem(APPEARANCE_KEY)
  const oldMode = s.getItem(THEME_KEY)
  if (!MODES.includes(appearance) && MODES.includes(oldMode)) s.setItem(APPEARANCE_KEY, oldMode)
  const oldTheme = s.getItem(LEGACY_THEME_KEY)
  if (oldTheme !== null) { s.setItem(THEME_KEY, oldTheme); s.removeItem(LEGACY_THEME_KEY) }
}
ls((s) => migrateKeys(s), null)

// ── read ────────────────────────────────────────────────────────────────────
// Legacy boolean is folded in on first read; setMode() below keeps mirroring it
// so a stale bundle or browser tab still running the old code doesn't flip it back.
function readMode() {
  const raw = ls((s) => s.getItem(APPEARANCE_KEY), null)
  if (MODES.includes(raw)) return raw
  const legacy = ls((s) => s.getItem(LEGACY_KEY), null)
  const migrated = legacy === 'true' ? 'dark' : 'light'
  ls((s) => s.setItem(APPEARANCE_KEY, migrated), null)
  return migrated
}
function readTheme() {
  const raw = ls((s) => s.getItem(THEME_KEY), null)
  return THEMES.includes(raw) ? raw : 'default'
}

const mq = () => {
  try { return window.matchMedia('(prefers-color-scheme: dark)') } catch { return null }
}
export function systemPrefersDark() {
  const m = mq()
  return !!(m && m.matches)
}
export const resolveMode = (mode) => (mode === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : mode)

// ── state ───────────────────────────────────────────────────────────────────
const bootMode = readMode()
let state = { mode: bootMode, theme: readTheme(), resolved: resolveMode(bootMode) }
const listeners = new Set()
const emit = () => { listeners.forEach((l) => l()) }

// <html> is the boot copy of the two attributes plus the classic shell's `.dark`
// class, so v1 agrees with v2 the moment either one changes.
function apply() {
  const d = typeof document !== 'undefined' && document.documentElement
  if (!d) return
  d.setAttribute('data-appearance', state.resolved)
  d.setAttribute('data-theme', state.theme)
  d.classList.toggle('dark', state.resolved === 'dark')
}

function setState(next) {
  const resolved = resolveMode(next.mode ?? state.mode)
  const merged = { mode: state.mode, theme: state.theme, ...next, resolved }
  if (merged.mode === state.mode && merged.theme === state.theme && merged.resolved === state.resolved) return
  state = merged
  apply()
  emit()
}

export function setMode(mode) {
  if (!MODES.includes(mode)) return
  ls((s) => { s.setItem(APPEARANCE_KEY, mode); s.setItem(LEGACY_KEY, String(resolveMode(mode) === 'dark')) }, null)
  setState({ mode })
}
export function setTheme(theme) {
  const s = THEMES.includes(theme) ? theme : 'default'
  ls((st) => st.setItem(THEME_KEY, s), null)
  setState({ theme: s })
}
// Light → Dark → System → Light. The order the Nav Rail spec names.
export function cycleMode() {
  setMode(MODES[(MODES.indexOf(state.mode) + 1) % MODES.length])
}

// ── live sources ────────────────────────────────────────────────────────────
// `system` has to follow the OS while the page is open, and a second tab writing
// the key has to move this one — neither fires a React event on its own.
let wired = false
function wire() {
  if (wired || typeof window === 'undefined') return
  wired = true
  const m = mq()
  const onMedia = () => { if (state.mode === 'system') setState({ mode: 'system' }) }
  if (m?.addEventListener) m.addEventListener('change', onMedia)
  else if (m?.addListener) m.addListener(onMedia)
  window.addEventListener('storage', (e) => {
    if (e.key === APPEARANCE_KEY || e.key === THEME_KEY) setState({ mode: readMode(), theme: readTheme() })
  })
}

function subscribe(l) {
  wire()
  listeners.add(l)
  return () => listeners.delete(l)
}
const getSnapshot = () => state
// SSR/prerender never runs here, but useSyncExternalStore insists on the third
// argument the moment anything server-renders the bundle.
const getServerSnapshot = () => state

/** `{ mode, resolved, theme, setMode, setTheme, cycle }` — the only look-and-feel read a component makes. */
export function useTheme() {
  const s = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  return { mode: s.mode, resolved: s.resolved, theme: s.theme, setMode, setTheme, cycle: cycleMode }
}

/** The two attributes every `.jn-v2` root spreads onto itself. */
export const themeAttrs = (s) => ({ 'data-appearance': s.resolved, 'data-theme': s.theme })

/** Rail tooltip: "Appearance: Dark — click to switch". */
export const appearanceTitle = (mode) => `Appearance: ${MODE_LABEL[mode] || mode} — click to switch`

// The boot script already stamped <html>; re-stamping here costs nothing and
// covers the case where localStorage was unreadable at boot but readable now.
apply()
