// The one place the app decides what it looks like.
//
// Two independent axes, both stored per browser (never in the DB — a skin is a
// preference, not a setting the backend acts on):
//   mode  light | dark | system   → localStorage `jobnavigator_theme`
//   skin  default | tone1 | tone2 | tone3 | editorial | alt
//                                 → localStorage `jobnavigator_skin`
//
// `default` and `alt` are the two designed skins. `editorial` is the palette of
// the DirectionC-Editorial direction board — the one the shipped default
// descends from, before it was lightened — and tone1/tone2/tone3 are the ramp
// between the two: every palette token interpolated in OKLab from default to
// editorial at ¼, ½ and ¾, light and dark separately, on the default's fonts —
// so the six can be looked at side by side on the monitor and the middle of the
// ramp picked by eye. Adding one is still two palette blocks in theme.css plus a
// line here — nothing else.
//
// `system` follows `prefers-color-scheme` live, so a mode is not the same thing
// as the colour that ends up on screen. `resolved` is that colour (light|dark);
// `mode` is what the user picked. Everything that used to read the old boolean
// `jobnavigator_dark_mode` on its own — V2App, ToastLab, UiGallery, LoginModal,
// WelcomeModal and the classic shell in App.jsx — subscribes here instead, so
// one click moves both shells with no reload (SHELL-02, SHELL-06).
//
// ATTRIBUTE HOSTS
//   <html>          data-theme, data-skin, and the classic shell's `.dark` class.
//                   Stamped by the inline boot script in index.html *before*
//                   React mounts, so the page ground is already the right colour
//                   on the first frame (index.html carries the matching
//                   `:root[data-theme]` ground rules), and re-stamped by apply()
//                   on every change.
//   every .jn-v2    the same two attributes, mirrored through React props.
//                   theme.css keeps selecting on the root itself
//                   (`.jn-v2[data-theme="dark"]`, `.jn-v2[data-skin="alt"]`), so
//                   the palette cascade is exactly what it was before this file
//                   existed; <html> is the boot copy, not a second source.
// Use `themeAttrs()` for the props — never read localStorage in a component.

import { useSyncExternalStore } from 'react'

const THEME_KEY = 'jobnavigator_theme'
const SKIN_KEY = 'jobnavigator_skin'
const LEGACY_KEY = 'jobnavigator_dark_mode'   // the pre-D6 boolean, migrated once

export const MODES = ['light', 'dark', 'system']
export const SKINS = ['default', 'tone1', 'tone2', 'tone3', 'editorial', 'alt']

// The rail's ◐ is a three-state control, so it needs three glyphs (Nav Rail spec:
// "cycles Light → Dark → System, tooltip names the current mode").
export const MODE_ICON = { light: '◐', dark: '◑', system: '◒' }
export const MODE_LABEL = { light: 'Light', dark: 'Dark', system: 'System' }
export const MODE_OPTIONS = MODES.map((m) => [m, MODE_LABEL[m]])
export const SKIN_LABEL = {
  default: 'Default — warm paper',
  tone1: 'Tone 1 — ¼ toward Editorial',
  tone2: 'Tone 2 — ½ toward Editorial',
  tone3: 'Tone 3 — ¾ toward Editorial',
  editorial: 'Editorial — original board tones',
  alt: 'Alt — cool slate',
}
export const SKIN_OPTIONS = SKINS.map((s) => [s, SKIN_LABEL[s]])

const ls = (fn, fallback) => { try { return fn(window.localStorage) } catch { return fallback } }

// ── read ────────────────────────────────────────────────────────────────────
// The legacy boolean is folded in on the first read and never consulted again;
// the write below keeps mirroring it so a stale bundle (or a browser tab still
// running the old code) doesn't flip back.
function readMode() {
  const raw = ls((s) => s.getItem(THEME_KEY), null)
  if (MODES.includes(raw)) return raw
  const legacy = ls((s) => s.getItem(LEGACY_KEY), null)
  const migrated = legacy === 'true' ? 'dark' : 'light'
  ls((s) => s.setItem(THEME_KEY, migrated), null)
  return migrated
}
function readSkin() {
  const raw = ls((s) => s.getItem(SKIN_KEY), null)
  return SKINS.includes(raw) ? raw : 'default'
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
let state = { mode: bootMode, skin: readSkin(), resolved: resolveMode(bootMode) }
const listeners = new Set()
const emit = () => { listeners.forEach((l) => l()) }

// <html> is the boot copy of the two attributes plus the classic shell's `.dark`
// class, so v1 agrees with v2 the moment either one changes (SHELL-06).
function apply() {
  const d = typeof document !== 'undefined' && document.documentElement
  if (!d) return
  d.setAttribute('data-theme', state.resolved)
  d.setAttribute('data-skin', state.skin)
  d.classList.toggle('dark', state.resolved === 'dark')
}

function setState(next) {
  const resolved = resolveMode(next.mode ?? state.mode)
  const merged = { mode: state.mode, skin: state.skin, ...next, resolved }
  if (merged.mode === state.mode && merged.skin === state.skin && merged.resolved === state.resolved) return
  state = merged
  apply()
  emit()
}

export function setMode(mode) {
  if (!MODES.includes(mode)) return
  ls((s) => { s.setItem(THEME_KEY, mode); s.setItem(LEGACY_KEY, String(resolveMode(mode) === 'dark')) }, null)
  setState({ mode })
}
export function setSkin(skin) {
  const s = SKINS.includes(skin) ? skin : 'default'
  ls((st) => st.setItem(SKIN_KEY, s), null)
  setState({ skin: s })
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
    if (e.key === THEME_KEY || e.key === SKIN_KEY) setState({ mode: readMode(), skin: readSkin() })
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

/** `{ mode, resolved, skin, setMode, setSkin, cycle }` — the only theme read a component makes. */
export function useTheme() {
  const s = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  return { mode: s.mode, resolved: s.resolved, skin: s.skin, setMode, setSkin, cycle: cycleMode }
}

/** The two attributes every `.jn-v2` root spreads onto itself. */
export const themeAttrs = (s) => ({ 'data-theme': s.resolved, 'data-skin': s.skin })

/** Rail tooltip: "Theme: Dark — click to switch". */
export const themeTitle = (mode) => `Theme: ${MODE_LABEL[mode] || mode} — click to switch`

// The boot script already stamped <html>; re-stamping here costs nothing and
// covers the case where localStorage was unreadable at boot but readable now.
apply()
