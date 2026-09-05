// v2 primitive layer: one component per element role, each rendering that
// role's canonical signature. Screens compose these instead of styling inline.
//
// HOW TO USE
//   import { Button, Pill, Input, Card, Helper } from './ui'
//   <Button onClick={save} busy={saving}>Save</Button>
//   <Pill on={filterOn} size="sm" onClick={toggle}>Remote</Pill>
//
// Every primitive takes `style` (merged last, for *layout* only — margin, flex,
// width, alignment) and `className` (appended after the primitive's own hover
// class). Interactive ones take `onClick`, `title`, `ariaLabel` and are
// keyboard-operable through `kb()`: they are `tabIndex=0`, announce a role, and
// fire on Enter/Space. The focus ring is theme.css's
// `[tabindex="0"]:focus-visible`; fields signal focus by turning their border
// accent (`:focus-visible`), never a ring.
//
// HOW TO ADD A VARIANT: a named entry in the role's size/look map below, with
// semantic tokens only — never an inline exception at a call site.
//
// THE RULE: never inline a colour, radius, shadow, font family or font size in
// a screen. Those live in `theme.css` as semantic tokens (`--btn-primary-bg`,
// `--radius-card`, `--menu-shadow`, `--font-body`, `--t-12-5`, …), each pointing
// at a palette token, so a new theme is a wholesale replacement of the palette
// block and nothing else. Primitives read semantic tokens only, never a palette
// token directly. `tools/stylelint.py` enforces this — theme.css and this file
// are the only two places a literal is allowed.
//
// LINE-HEIGHTS are whole pixels. Fixed-height flex controls carry `v2-ctl`
// (line-height:1); a single line centred in a fixed box renders identically at
// any line-height, so that is pixel-safe.
import React, { useEffect, useRef, useState } from 'react'
import './theme.css'
import { useEscape, useSnapTop } from './hooks'
import { useTheme } from './theme'

// v2 draws its controls as span/div, so none of them would be focusable or
// operable from the keyboard. Spread `kb(fn)` onto such an element. Same
// contract as the copies in ResumeSections.jsx and Settings.jsx — declared
// here rather than imported so `ui.jsx` stays a leaf of the v2 import graph.
export const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

const cx = (...v) => v.filter(Boolean).join(' ')
// `kb()` only when the control can actually act — a disabled control must not be
// a tab stop, and an inert one (a Card with no onClick) is not a button.
//
// A disabled/busy control keeps its ROLE: dropping it along with the click/key
// handlers made a `Parsing…` button read as loose text to a screen reader and
// lost its focus. Keep role and the caller's aria-disabled/aria-busy, drop only
// the interactivity — no handlers, `tabIndex -1` so it stays focusable but leaves the tab order.
const act = (fn, off, role) => (
  fn ? (off ? { role: role || 'button', tabIndex: -1 } : { onClick: fn, ...kb(fn, role) }) : {}
)

// ── theme variables a primitive has to READ, not write ──────────────────────
// `--ring-variant` and `--title-bar` are shape switches, not paint, so they
// can't live on a style object and have to come back out of the cascade.
//
// getComputedStyle result is cached per (theme, appearance, name), not read per
// mount — a Feed page holds fifty rings, so an uncached read forces a reflow
// each render. Read happens in an effect: theme.js stamps <html> synchronously,
// but `.jn-v2` roots take theme/skin as React props, so mid-transition the DOM
// is a commit behind the props.
const VAR_CACHE = new Map()
const readThemeVar = (name) => {
  try {
    const el = document.querySelector('.jn-v2') || document.documentElement
    return getComputedStyle(el).getPropertyValue(name).trim()
  } catch { return '' }
}
function useThemeVar(name, fallback) {
  const look = useTheme()
  const key = `${look.theme}|${look.resolved}|${name}`
  const [val, setVal] = useState(() => VAR_CACHE.get(key))
  useEffect(() => {
    let v = VAR_CACHE.get(key)
    if (v === undefined) { v = readThemeVar(name); VAR_CACHE.set(key, v) }
    setVal(v)
  }, [key, name])
  return val || fallback
}

// ── Spinner ─────────────────────────────────────────────────────────────────
// `color` lets a button spin in its own ink (currentColor) without a second
// token. `weight="bold"` is the 2px band used at larger diameters (e.g. the
// Feed's 28px score ring), where a hairline reads as a different control.
const SPIN_WEIGHT = { bold: '2px' }
export function Spinner({ size = 9, weight, color, style }) {
  return (
    <span className="v2-spin" aria-hidden="true" style={{
      flex: '0 0 auto', display: 'inline-block', width: size, height: size,
      border: `${SPIN_WEIGHT[weight] || '1.5px'} solid ${color || 'var(--spinner-ink)'}`,
      borderTopColor: 'transparent',
      borderRadius: 'var(--radius-control)', ...style,
    }} />
  )
}

// ── Button ──────────────────────────────────────────────────────────────────
const BTN_SIZE = {
  md: { height: 36, fontSize: 'var(--t-13-5)', padding: '0 18px' },
  sm: { height: 33, fontSize: 'var(--t-13)', padding: '0 15px' },
  xs: { height: 28, fontSize: 'var(--t-12-5)', padding: '0 14px' },
}
// `state` is the class the theme's own hover/pressed rules hang on
// (theme.css: `.v2-btn-primary:hover` → --btn-primary-hover-bg, `:active` →
// --btn-primary-pressed-bg + --pressed-shift). Dropped while the button is off:
// a disabled control has no hover.
//
// `ai` is the tailoring button: primary's geometry on the --ai / --ai-ink pair,
// the accent in every theme with no violet of its own.
//
// The DISABLED ink is a two-token read, `var(--disabled-ink, <the button's own
// disabled ink>)`: in the base blocks --disabled-ink is `inherit`, a guaranteed-
// invalid value here, so the fallback (--muted on --line) is taken; a theme that
// sets --disabled-ink for real (e.g. win98) takes over. --disabled-engrave is
// the matching text-shadow. Button keeps this token swap rather than the
// --disabled-opacity dim the other primitives use.
const BTN_LOOK = {
  primary: {
    rest: { background: 'var(--btn-primary-bg)', color: 'var(--btn-primary-ink)' },
    off: { background: 'var(--btn-primary-disabled-bg)', color: 'var(--disabled-ink, var(--btn-primary-disabled-ink))' },
    hover: '', state: 'v2-btn-primary',
  },
  ai: {
    rest: { background: 'var(--ai)', color: 'var(--ai-ink)' },
    off: { background: 'var(--btn-primary-disabled-bg)', color: 'var(--disabled-ink, var(--btn-primary-disabled-ink))' },
    hover: '', state: 'v2-btn-primary',
  },
  danger: {
    rest: { background: 'var(--btn-danger-bg)', color: 'var(--btn-danger-ink)' },
    off: { background: 'var(--btn-primary-disabled-bg)', color: 'var(--disabled-ink, var(--btn-primary-disabled-ink))' },
    hover: '', state: 'v2-btn-danger',
  },
  secondary: {
    rest: { background: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-ink)', border: 'var(--bw-control) solid var(--btn-secondary-border)' },
    off: { background: 'var(--btn-secondary-bg)', color: 'var(--disabled-ink, var(--btn-secondary-disabled-ink))', border: 'var(--bw-control) solid var(--btn-secondary-disabled-border)' },
    hover: 'v2-bdc',
  },
  ghost: {
    rest: { background: 'transparent', color: 'var(--btn-ghost-ink)' },
    off: { background: 'transparent', color: 'var(--disabled-ink, var(--btn-secondary-disabled-ink))' },
    hover: 'v2-hover-accent',
  },
}
// `as="button"` renders a real <button type=…> instead of the div, for a form's
// submit control (LoginModal) where Enter-in-a-field must submit. UA button
// styles are reset first; keeps `tabindex="0"` so theme.css's focus ring still applies.
export function Button({
  variant = 'primary', size = 'md', as, type = 'button', disabled, busy, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup, ariaBusy, children, style, className,
}) {
  const s = BTN_SIZE[size] || BTN_SIZE.md
  const look = BTN_LOOK[variant] || BTN_LOOK.primary
  const off = !!(disabled || busy)
  const native = as === 'button'
  const common = {
    title,
    'aria-label': ariaLabel,
    'aria-expanded': ariaExpanded,
    'aria-haspopup': ariaHaspopup,
    // `busy` is the state a screen reader needs; the prop stays an explicit
    // override for callers that set it themselves.
    'aria-busy': ariaBusy !== undefined ? ariaBusy : (busy || undefined),
    // `v2-raised` is the bevel hook every other control already carries: without
    // it win98 drew a secondary button as one flat stroke and a primary with no
    // border pixel at all, in a skin whose whole idiom is "raised = clickable"
    // (R4-T3-09). Scoped `[data-theme="win98"]` in theme.css — inert elsewhere,
    // and kept on a disabled button too, since a win98 button is still a button.
    className: cx('v2-ctl', 'v2-raised', !off && look.state, !off && look.hover, className),
    style: {
      flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      borderRadius: 'var(--radius-control)', fontFamily: 'var(--font-body)', fontWeight: 'var(--btn-weight)',
      boxShadow: off ? 'none' : 'var(--btn-shadow)', // some themes lift/tint buttons; a disabled one never floats
      whiteSpace: 'nowrap', cursor: off ? 'default' : 'pointer',
      // explicit 1: Button keeps its own disabled token swap rather than the
      // --disabled-opacity dim theme.css applies to [aria-disabled="true"].
      opacity: busy && !disabled ? 0.6 : 1,
      ...(off ? { textShadow: 'var(--disabled-engrave)' } : null), // engraved half of the disabled pair; `none` by default
      ...(native ? { margin: 0, border: 'none', appearance: 'none', WebkitAppearance: 'none' } : null),
      ...s, ...(off ? look.off : look.rest), ...style,
    },
  }
  const body = <>{busy && <Spinner size={12} color="currentColor" />}{children}</>
  if (native) {
    return (
      <button type={type} tabIndex={0} disabled={off} onClick={off ? undefined : onClick} {...common}>
        {body}
      </button>
    )
  }
  return (
    <div {...act(onClick, off)} aria-disabled={off || undefined} {...common}>
      {body}
    </div>
  )
}

// ── Pill ────────────────────────────────────────────────────────────────────
// canonical: on ? accent-soft/accent : surface/text-2 · 1px border · r99,
// hover always `v2-bd` (accent border, no wash). sizes md h31/12.5, sm h26/11.5.
//
// `xs` is the 25px Run/Test row-level pill (Companies, Searches, Stats): h25 /
// pad 0 10 / 11.5 with a tighter 5px gap than the 31px filter pill. Same paint,
// same tokens — a variant rather than a separate component, since every site
// already needs `on` or `disabled`.
const PILL_SIZE = {
  md: { height: 31, fontSize: 'var(--t-12-5)', padding: '0 15px' },
  sm: { height: 26, fontSize: 'var(--t-11-5)', padding: '0 13px' },
  xs: { height: 25, fontSize: 'var(--t-11-5)', padding: '0 10px', gap: 5 },
}
// `hover` names the class the theme's rule hangs on. md/sm use the role's own
// `v2-bd` (accent border); `xs` uses `v2-bdc` (border + ink) — D-13 made that the
// one paint every small row control shares with IconButton 25 and ToolbarTrigger.
//
// `line` opts a pill out of `v2-ctl`'s line-height:1 — needed for the
// hand-drawn 25px pills, which centre their glyph inside an inherited 1.5 line
// box; `line="inherit"` keeps that box instead of re-rounding it.
export function Pill({
  on, size = 'md', disabled, hover, line, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup, ariaBusy, children, style, className,
}) {
  const s = PILL_SIZE[size] || PILL_SIZE.md
  const hoverClass = hover || (size === 'xs' ? 'v2-bdc' : 'v2-bd')
  return (
    <div
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel}
      aria-expanded={ariaExpanded} aria-haspopup={ariaHaspopup} aria-busy={ariaBusy}
      aria-pressed={on === undefined ? undefined : !!on} aria-disabled={disabled || undefined}
      // `v2-raised` is the bevel hook (theme.css --bevel-raised-*), scoped to
      // bevelled skins with `!important` there since the inline border/shadow
      // below would otherwise beat it; a no-op in every other theme.
      className={cx('v2-ctl', 'v2-raised', !disabled && hoverClass, className)}
      style={{
        flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        borderRadius: 'var(--radius-control)', fontFamily: 'var(--font-body)', whiteSpace: 'nowrap',
        background: on ? 'var(--pill-on-bg)' : 'var(--pill-bg)', // same on-trio Segmented/ChoiceCard read
        color: on ? 'var(--pill-on-ink)' : 'var(--pill-ink)',
        border: `var(--bw-control) solid ${on ? 'var(--pill-on-border)' : 'var(--pill-border)'}`,
        boxShadow: 'var(--pill-shadow)',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer',
        ...s, ...(line ? { lineHeight: line } : null), ...style,
      }}>{children}</div>
  )
}

// ── IconButton ──────────────────────────────────────────────────────────────
// 26 = bare glyph button (muted · r99 · 26×26 · 13px · hover v2-hover-accent).
// 36 = bordered "⋯" head button (1px edge on surface, 15px, hover v2-act,
//      accent border + accent-soft when `on`).
// 25 = the same bordered look, sized for the 25px row pill on Companies and
//      Searches; keeps the 13px glyph since 15px reads as a different control
//      at that size.
// `hover` overrides the size's default class, like Pill's; `line` is Pill's
// line-box opt-out for the same reason. The 25 defaults to `v2-bdc`, the small
// row control's shared paint (D-13); the 36 keeps its own `v2-act`.
export function IconButton({
  size = 26, on, disabled, hover, line, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup, children, style, className,
}) {
  const bordered = size === 36 || size === 25
  const look = bordered
    ? {
      fontSize: size === 36 ? 'var(--t-15)' : 'var(--t-13)', color: on ? 'var(--pill-on-ink)' : 'var(--pill-ink)',
      background: on ? 'var(--pill-on-bg)' : 'var(--pill-bg)',
      border: `var(--bw-control) solid ${on ? 'var(--pill-on-border)' : 'var(--pill-border)'}`,
      boxShadow: 'var(--pill-shadow)',
    }
    : { fontSize: 'var(--t-13)', color: 'var(--icon-btn-ink)' }
  return (
    <div
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel || title}
      aria-expanded={ariaExpanded} aria-haspopup={ariaHaspopup}
      aria-pressed={on === undefined ? undefined : !!on} aria-disabled={disabled || undefined}
      // bevel hook goes on the bordered sizes only — the 26 is a bare glyph with
      // no border, so win98 draws it flat instead.
      className={cx('v2-ctl', bordered && 'v2-raised', !disabled && (hover || (size === 25 ? 'v2-bdc' : bordered ? 'v2-act' : 'v2-hover-accent')), className)}
      style={{
        flex: '0 0 auto', width: size, height: size, borderRadius: 'var(--radius-control)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer',
        ...look, ...(line ? { lineHeight: line } : null), ...style,
      }}>{children}</div>
  )
}

// ── Input / Textarea ────────────────────────────────────────────────────────
// canonical field: h32 · 1px --input-border · r6 · 12.5 · bg --input-bg.
// Focus = accent border, no ring (theme.css `input:focus-visible`).
// Fields and `Select` are both 32px so a row pairing the two (Persona's autofill
// grid, Searches' Cell grid, Settings' value rows) lines up. `Textarea` has no
// fixed height — its box is intrinsic to `rows` — so the 32 is expressed as its
// single-line basis: 19px line + 2×5.5px padding + 2×1px border = 32, matching a
// one-line `Input`; `minHeight` equals that intrinsic height (rows·19 + 13).
//
// `invalid` writes `aria-invalid="true"`; theme.css repaints the border with
// --input-border-error and adds --input-ring-error from that attribute alone,
// so Textarea and Select get the state for free.
// `v2-inset` is the bevel hook (theme.css --bevel-inset-*): inert everywhere but
// win98, where a field is sunk instead of outlined; scoped `!important` there
// since the inline border/shadow below would otherwise beat it.
const FIELD = {
  width: '100%', minWidth: 0, border: 'var(--bw-control) solid var(--input-border)',
  borderRadius: 'var(--radius-field)', background: 'var(--input-bg)', color: 'var(--input-ink)',
  boxShadow: 'var(--field-shadow)',
  fontFamily: 'var(--font-body)', fontSize: 'var(--t-12-5)', outline: 'none',
}
// `defaultValue` (instead of `value`) renders the field *uncontrolled* — needed
// by Applications' autosaving notes box, where keystrokes must not round-trip through React state.
export function Input({ value, defaultValue, onChange, placeholder, type = 'text', mono, invalid, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  const bind = defaultValue === undefined ? { value: value ?? '' } : { defaultValue }
  return (
    <input
      type={type} {...bind} placeholder={placeholder} disabled={disabled} readOnly={readOnly}
      aria-invalid={invalid ? 'true' : undefined}
      aria-label={ariaLabel} title={title} className={cx('v2-inset', className)}
      onChange={onChange ? (e) => onChange(e.target.value, e) : undefined}
      style={{ ...FIELD, height: 32, padding: '0 9px', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', opacity: disabled ? 0.6 : 1, ...style }}
      {...rest} />
  )
}
export function Textarea({ value, defaultValue, onChange, placeholder, rows = 3, mono, invalid, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  const bind = defaultValue === undefined ? { value: value ?? '' } : { defaultValue }
  return (
    <textarea
      {...bind} placeholder={placeholder} rows={rows} disabled={disabled} readOnly={readOnly}
      aria-invalid={invalid ? 'true' : undefined}
      aria-label={ariaLabel} title={title} className={cx('v2-inset', className)}
      onChange={onChange ? (e) => onChange(e.target.value, e) : undefined}
      style={{
        ...FIELD, padding: '5.5px 9px', minHeight: rows * 19 + 13, lineHeight: '19px', resize: 'vertical',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', opacity: disabled ? 0.6 : 1, ...style,
      }}
      {...rest} />
  )
}

// ── SearchInput ─────────────────────────────────────────────────────────────
// boxed (Companies toolbar): h32, r99, 1px --input-border on --search-bg, ⌕ inset.
// underline (Cover Letters header): h36, no box, 1px --input-underline beneath.
// Both take the accent on focus from theme.css — no ring either way. The boxed
// variant matches Input/Select's 32px box; the underline variant is a visually
// different control with its own 36.
export function SearchInput({ value, onChange, placeholder = 'Search…', variant = 'boxed', width, invalid, ariaLabel, style, className }) {
  const under = variant === 'underline'
  const field = under
    ? {
      width: '100%', height: 36, padding: '0 13px', border: 'none',
      borderBottom: 'var(--bw-control) solid var(--input-underline)', background: 'transparent',
      color: 'var(--input-ink)', fontFamily: 'var(--font-body)', fontSize: 'var(--t-13)', outline: 'none',
    }
    : {
      width: '100%', height: 32, padding: '0 12px 0 29px', border: 'var(--bw-control) solid var(--input-border)',
      borderRadius: 'var(--radius-control)', background: 'var(--search-bg)', boxShadow: 'var(--field-shadow)',
      color: 'var(--input-ink)', fontFamily: 'var(--font-body)', fontSize: 'var(--t-12)', outline: 'none',
    }
  return (
    // Wrapper needs a real `width`, not just a flex-basis: a flex item's
    // intrinsic contribution is measured from its content, and a bare <input>'s
    // default intrinsic width (~178px) would under-budget the item in a
    // max-content parent (a header's action group), shoving sibling buttons
    // past the header's overflow:hidden edge. `0 1 auto` + minWidth:0 keeps the
    // field, not the button, as the thing that yields.
    <span className={className} style={{ position: 'relative', display: 'flex', alignItems: 'center', minWidth: 0, width: width || 226, flex: '0 1 auto', ...style }}>
      {!under && (
        <span aria-hidden="true" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 'var(--t-12)', color: 'var(--search-glyph)', pointerEvents: 'none' }}>⌕</span>
      )}
      {/* `v2-underline`: theme.css's field-hover rule reads --input-border-hover
          (the boxed field's rest border); this variant rests on --input-underline instead. */}
      <input type="text" value={value ?? ''} placeholder={placeholder} aria-label={ariaLabel || placeholder}
        aria-invalid={invalid ? 'true' : undefined} className={cx('v2-inset', under && 'v2-underline')}
        onChange={onChange ? (e) => onChange(e.target.value, e) : undefined} style={field} />
    </span>
  )
}

// ── Select (trigger + listbox) ──────────────────────────────────────────────
// Same semantics as the Settings dropdown it generalises: a box + caret that
// announces aria-haspopup="listbox"/aria-expanded, and a role="listbox" panel of
// role="option" rows. `options` is [[value, label], …].
export function Select({ value, options = [], onPick, width, mono, placeholder, invalid, ariaLabel, emptyText, disabled, style, className }) {
  const [open, setOpen] = useState(false)
  // Escape closes only this listbox, not a modal it might sit inside. The key
  // listener runs in the *capture* phase since `useEscape` (hooks.js) listens on
  // document in the bubble phase and a parent modal's listener registers well
  // before this popover opens — capture always runs first, and
  // preventDefault+stopPropagation claim the event ahead of it.
  useEffect(() => {
    if (!open) return undefined
    const c = () => setOpen(false)
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
    }
    document.addEventListener('click', c)
    document.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('click', c)
      document.removeEventListener('keydown', onKey, true)
    }
  }, [open])
  const cur = options.find((o) => String(o[0]) === String(value ?? ''))
  const toggle = () => setOpen((v) => !v)
  return (
    <span className={className} onClick={(e) => e.stopPropagation()}
      style={{ position: 'relative', display: 'flex', flex: `0 1 ${width || '220px'}`, minWidth: 0, ...style }}>
      {/* `v2-select-trigger`: the trigger is a div, so `input:hover` in
          theme.css never reaches it. `v2-inset` is the win98 bevel hook, inert elsewhere. */}
      <div {...act(toggle, disabled)} aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-disabled={disabled || undefined}
        aria-invalid={invalid ? 'true' : undefined} className="v2-inset v2-select-trigger"
        style={{
          flex: 1, minWidth: 0, height: 32, padding: '0 10px',
          border: `var(--bw-control) solid ${open ? 'var(--input-border-focus)' : 'var(--input-border)'}`,
          boxShadow: 'var(--field-shadow)',
          // trigger is a field, so it takes --input-bg like Input/Textarea —
          // not --search-bg, which is reserved for SearchInput so a form pairing
          // a Select with an Input doesn't draw two backgrounds for one row.
          borderRadius: 'var(--radius-field)', background: 'var(--input-bg)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 7,
          fontFamily: 'var(--font-body)', fontSize: 'var(--t-12-5)', color: 'var(--input-ink)',
          lineHeight: 1, outline: 'none', opacity: disabled ? 0.6 : 1, cursor: disabled ? 'default' : 'pointer',
        }}>
        <span style={{
          minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          color: cur ? 'var(--input-ink)' : 'var(--input-placeholder)',
          fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)',
          fontSize: mono ? 'var(--t-11-5)' : 'var(--t-12-5)',
        }}>{cur ? cur[1] : (placeholder || 'Select…')}</span>
        <span aria-hidden="true" style={{ flex: '0 0 auto', fontSize: 'var(--t-9)', color: 'var(--icon-btn-ink)' }}>▾</span>
      </div>
      {open && (
        <div className="v2-menu v2-scroll" role="listbox" style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40,
          minWidth: '100%', maxWidth: 420, maxHeight: 320, overflow: 'auto',
          background: 'var(--menu-bg)', border: 'var(--bw-panel) solid var(--menu-border)',
          borderRadius: 'var(--radius-menu)', boxShadow: 'var(--menu-shadow)', padding: 5,
          display: 'flex', flexDirection: 'column', gap: 1,
        }}>
          {options.length === 0 ? (
            <div style={{ padding: '7px 9px', fontSize: 'var(--t-11-5)', lineHeight: '16px', color: 'var(--helper-ink)' }}>
              {emptyText || 'Nothing to pick yet.'}
            </div>
          ) : options.map((o) => {
            const sel = String(o[0]) === String(value ?? '')
            const pick = () => { onPick?.(o[0]); setOpen(false) }
            return (
              <div key={String(o[0])} className="v2-menuitem" {...act(pick, false, 'option')} aria-selected={sel}
                style={{
                  padding: '7px 9px', borderRadius: 'var(--radius-field)', fontSize: 'var(--t-12-5)',
                  cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  color: sel ? 'var(--menu-item-on-ink)' : 'var(--menu-item-ink)',
                  background: sel ? 'var(--menu-item-on-bg)' : 'transparent',
                }}>{o[1]}</div>
            )
          })}
        </div>
      )}
    </span>
  )
}

// ── ToolbarTrigger ──────────────────────────────────────────────────────────
// The picker in a toolbar strip: 1px --input-border · r6 (a field's radius and
// border) · 11.5 · a 9px ▾, and no ground — it sits directly on the strip,
// unlike a short Select. Slots: `label` (muted caption), `value` (picked one), a
// caret unless `caret={false}`. `open` swings the border accent like Select's
// trigger, as a named variant since none of the four sites passes it today.
//
// Two sizes, mirroring Pill's: `sm` is the canonical 24 in a PDF-preview toolbar
// (ResumeEditor, CoverLetterEditor); `md` is 32, the field height, for a row that
// pairs the trigger with an Input or Select (Settings' cron presets, D-21).
// Hover is `v2-bdc`, the small row control's shared paint (D-13).
// `line` is Pill's line-box opt-out.
const TRIGGER_SIZE = { sm: { height: 24, padding: '0 8px' }, md: { height: 32, padding: '0 10px' } }
export function ToolbarTrigger({
  label, value, size = 'sm', open, disabled, hover = 'v2-bdc', line, caret = true, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup = 'listbox', children, style, className,
}) {
  const s = TRIGGER_SIZE[size] || TRIGGER_SIZE.sm
  return (
    <span
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel || title}
      aria-expanded={ariaExpanded !== undefined ? ariaExpanded : (open || undefined)}
      aria-haspopup={ariaHaspopup} aria-disabled={disabled || undefined}
      // deliberately NOT `v2-inset`: that hook's hover rule carries `!important`
      // and would beat this control's own `v2-bdc` accent hover.
      className={cx('v2-ctl', !disabled && hover, className)}
      style={{
        ...s, display: 'flex', alignItems: 'center', gap: 6,
        borderRadius: 'var(--radius-field)', fontSize: 'var(--t-11-5)',
        border: `var(--bw-control) solid ${open ? 'var(--input-border-focus)' : 'var(--input-border)'}`,
        boxShadow: 'var(--field-shadow)',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer',
        ...(line ? { lineHeight: line } : null), ...style,
      }}>
      {label != null && <span style={{ color: 'var(--label-ink)' }}>{label}</span>}
      {value != null && <span style={{ color: 'var(--input-ink)' }}>{value}</span>}
      {children}
      {caret && <span aria-hidden="true" style={{ color: 'var(--label-ink)', fontSize: 'var(--t-9)' }}>▾</span>}
    </span>
  )
}

// ── Row ─────────────────────────────────────────────────────────────────────
// canonical: h46 · r7 · pad 0 10 · hover --row-hover · selected = --row-selected.
// Selection is a background wash and nothing else — no left-pad marker bar,
// since that would shift every cell in the picked row.
// `flush` is the named variant for a full-bleed table row (Companies): no side
// padding, so a 7px radius would round the hover fill away from the pane edges.
// Radius only — height, hover, selection and divider stay canonical.
// `...rest` carries the `data-*` hooks a screen already relies on (the Feed keys
// its scroll-into-view and its harness selectors off `data-row={i}`).
export function Row({ selected, divider, flush, onClick, title, ariaLabel, children, style, className, ...rest }) {
  return (
    <div {...rest} {...act(onClick, false, 'button')} title={title} aria-label={ariaLabel} aria-current={selected ? "true" : undefined}
      className={cx('v2-row', className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, height: 46,
        borderRadius: flush ? 0 : 'var(--radius-row)',
        // picked row is a token trio: theme.css's `.v2-row[aria-current="true"]`
        // writes the same three names (needed since the Feed draws its own row).
        background: selected ? 'var(--row-selected)' : 'transparent',
        ...(selected ? { color: 'var(--row-selected-ink)', boxShadow: 'var(--row-selected-edge)' } : null),
        borderBottom: divider ? 'var(--bw-hair) var(--row-line-style) var(--row-line)' : undefined,
        padding: '0 10px',
        // conditional spread, never `cursor: … : undefined` — an undefined key
        // still clears the property, and an inert row needs `cursor` left unset to keep the I-beam.
        ...(onClick ? { cursor: 'pointer' } : null), ...style,
      }}>{children}</div>
  )
}

// ── TableRow ────────────────────────────────────────────────────────────────
// The BODY row of a flat table — TableHead's partner (Companies' test list,
// Stats' schedules/runs/activity, the Feed's requirement table). 32/34/38
// height, divider via --row-line/--row-line-style (win98 gets a dotted
// separator), and no hover at all unless given an `onClick` — a table body is
// read, not picked, and a wash on every line would make the divider the noise.
// `size` pins the row's own type where cells inherit it; left off, the row
// inherits. `align` is the one geometry knob (a wrapped requirement must not
// centre against a one-line verdict).
const TROW_SIZE = {
  sm: { fontSize: 'var(--t-11-5)', lineHeight: '18px' },
  md: { fontSize: 'var(--t-12)', lineHeight: '18px' },
}
export function TableRow({
  height = 34, pad = '0 20px', size, align = 'center', selected, onClick, title, ariaLabel,
  children, style, className, ...rest
}) {
  return (
    <div {...rest} {...act(onClick, false, 'button')} title={title} aria-label={ariaLabel}
      aria-current={selected ? 'true' : undefined}
      className={cx(onClick && 'v2-row', className)}
      style={{
        display: 'flex', alignItems: align, height, padding: pad,
        borderBottom: 'var(--bw-hair) var(--row-line-style) var(--row-line)',
        ...(selected ? { background: 'var(--row-selected)', color: 'var(--row-selected-ink)', boxShadow: 'var(--row-selected-edge)' } : null),
        ...(size ? TROW_SIZE[size] : null),
        ...(onClick ? { cursor: 'pointer' } : null), ...style,
      }}>{children}</div>
  )
}

// ── FooterRow ───────────────────────────────────────────────────────────────
// HeaderRow's mirror: the action bar at the bottom of a modal or drawer, rule
// on TOP. Reads `--divider` — the one name carrying the whole rule (win98's
// `2px groove` can't be spelled as a colour) — where HeaderRow reads a colour
// and writes its own 1px. `soft` is the lighter hairline (WelcomeModal), `bg`
// the same named ground map HeaderRow uses. Does NOT claim `flex: 0 0 auto`
// like HeaderRow — left as a layout decision at the call site.
const FOOT_PAD = { modal: '12px 22px', compact: '11px 22px', wide: '14px 24px 18px' }
export function FooterRow({
  as, variant = 'modal', pad, bg, soft, align = 'center', gap = 9,
  id, children, style, className, ...rest
}) {
  const El = as === 'footer' ? 'footer' : 'div'
  return (
    <El id={id} className={className} {...rest} style={{
      padding: pad || FOOT_PAD[variant] || FOOT_PAD.modal,
      borderTop: soft ? 'var(--bw-hair) solid var(--head-line-soft)' : 'var(--divider)',
      display: 'flex', alignItems: align, gap,
      ...(bg ? { background: HEAD_BG[bg] || HEAD_BG.surface } : null), ...style,
    }}>{children}</El>
  )
}

// ── Card / Band ─────────────────────────────────────────────────────────────
// Card canonical: surface · 1px --card-border · r9 · pad 10 14.
//   `interactive` adds the accent-border + --card-bg-hover wash (v2-act).
// Band is the dashed sibling (same box, dashed --band-border).
// `id` and a forwarded ref are zero-pixel pass-throughs: Stats scrolls two of its
// static cards into view (`schedRef`/`runsCardRef`) and deep-links one by `#runs`.
export const Card = React.forwardRef(function Card(
  { interactive, onClick, id, title, ariaLabel, children, style, className }, ref,
) {
  const live = interactive || !!onClick
  return (
    <div ref={ref} id={id} {...act(onClick, false)} title={title} aria-label={ariaLabel}
      className={cx(live && 'v2-act', className)}
      style={{
        background: 'var(--card-bg)', border: 'var(--bw-panel) solid var(--card-border)',
        borderRadius: 'var(--radius-card)', padding: '10px 14px',
        boxShadow: 'var(--card-shadow)',
        // `cursor` is inherited: setting `default` on a static card pushed the
        // plain arrow through every text node inside it, killing the I-beam on selectable text.
        ...(live ? { cursor: 'pointer' } : null), ...style,
      }}>{children}</div>
  )
})
export function Band({ interactive = true, onClick, title, ariaLabel, children, style, className }) {
  const live = interactive || !!onClick
  return (
    <div {...act(onClick, false)} title={title} aria-label={ariaLabel}
      className={cx(live && 'v2-act', className)}
      style={{
        border: 'var(--bw-panel) dashed var(--band-border)', borderRadius: 'var(--radius-card)',
        padding: '10px 14px', ...(live ? { cursor: 'pointer' } : null), ...style,
      }}>{children}</div>
  )
}

// ── DashedAdd ───────────────────────────────────────────────────────────────
// canonical: accent text · 1px dashed --dashadd-border · r6 · 11.5 · h28.
// `big` is the 32/12/500 variant the résumé sections use for a section-level add.
export function DashedAdd({ big, disabled, onClick, title, ariaLabel, children, style, className }) {
  return (
    <div {...act(onClick, disabled)} title={title} aria-label={ariaLabel} aria-disabled={disabled || undefined}
      className={cx('v2-ctl', !disabled && 'v2-dashadd', className)}
      style={{
        height: big ? 32 : 28, border: '1px dashed var(--dashadd-border)',
        borderRadius: 'var(--radius-field)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        fontFamily: 'var(--font-body)', fontSize: big ? 'var(--t-12)' : 'var(--t-11-5)', fontWeight: big ? 500 : 400,
        color: 'var(--dashadd-ink)', opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer', ...style,
      }}>{children}</div>
  )
}

// ── Menu / MenuItem ─────────────────────────────────────────────────────────
// Menu canonical: surface · 1px --menu-border · r10 · --menu-shadow · pad 5.
// The caller owns positioning (it is usually absolute under a trigger).
export function MenuHead({ children, style }) {
  return (
    <div style={{
      padding: '4px 11px 3px', fontSize: 'var(--t-9-5)', lineHeight: '14px',
      letterSpacing: 'var(--label-tracking)', textTransform: 'var(--label-case)',
      fontWeight: 'var(--label-weight)', color: 'var(--label-ink)', ...style,
    }}>{children}</div>
  )
}
// `role` is a prop because the same box serves an action menu (role="menu") and
// an option picker (role="listbox" — Settings' typeahead, the cover-letter
// template/paper pickers). Positioning is the caller's, passed as `style`.
// `v2-menu` is not decoration — theme.css pins `flex-shrink:0` on every direct
// child, since without it a menu taller than its `maxHeight` (the Feed's
// Company filter with ~1300 rows) shrinks the search field from 32px to 17.
// `onDismiss` mounts the backdrop the Feed's `Drop` has always drawn: a fixed,
// transparent sheet one z-step under the panel, so the click that closes the
// menu is SWALLOWED instead of also firing the row/card underneath it (a Sort
// menu dismissed over a company row used to open that row's drawer — R4-T2A-05).
// The panel's own `style.zIndex` sets the sheet's; `backdropZ` overrides.
export function Menu({ role = 'menu', onDismiss, backdropZ, children, ariaLabel, style, className }) {
  const panel = (
    <div role={role} aria-label={ariaLabel} className={cx('v2-menu', 'v2-raised', className)} style={{
      background: 'var(--menu-bg)', border: 'var(--bw-panel) solid var(--menu-border)',
      borderRadius: 'var(--radius-menu)', boxShadow: 'var(--menu-shadow)', padding: 5,
      display: 'flex', flexDirection: 'column', gap: 1, ...style,
    }}>{children}</div>
  )
  if (!onDismiss) return panel
  const z = typeof style?.zIndex === 'number' ? style.zIndex - 1 : 44
  return (
    <>
      <div aria-hidden="true" onClick={onDismiss} style={{ position: 'fixed', inset: 0, zIndex: backdropZ ?? z }} />
      {panel}
    </>
  )
}
// canonical: text-2 · r6 · 12.5 · pad 7 11 · hover v2-menuitem.
// `danger` → --menu-item-danger-ink + v2-hover-bad, plus a --menu-item-sep rule
// above it; pass `divider={false}` for a danger item that is not the last of its menu.
// `selected` is the picked row of an option menu: --menu-item-on-bg/-on-ink at
// weight 500, the same tint the Select listbox paints.
// `icon` sits in a fixed 16px gutter so every label in a menu starts on one
// axis. `hint` is the trailing shortcut/count; `hintMono` sets it in the mono face.
// `href` renders a real <a> — a menu row that navigates must stay ⌘/middle-
// clickable (Companies' "View jobs in feed", the cover-letter editor's job link).
export function MenuItem({
  icon, hint, hintMono, selected, danger, divider, disabled, href, target, ellipsis,
  role = 'menuitem', onClick, title, ariaLabel, ariaSelected, children, style, className,
}) {
  const sep = divider === undefined ? !!danger : divider
  const common = {
    title,
    'aria-label': ariaLabel,
    'aria-selected': ariaSelected,
    'aria-disabled': disabled || undefined,
    className: cx(!disabled && (danger ? 'v2-hover-bad' : 'v2-menuitem'), className),
    style: {
      display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px',
      borderRadius: 'var(--radius-field)', fontSize: 'var(--t-12-5)',
      color: danger ? 'var(--menu-item-danger-ink)' : selected ? 'var(--menu-item-on-ink)' : 'var(--menu-item-ink)',
      ...(selected ? { background: 'var(--menu-item-on-bg)', fontWeight: 500 } : null),
      ...(sep ? { borderTop: '1px solid var(--menu-item-sep)' } : null),
      opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer', ...style,
    },
  }
  const body = (
    <>
      {icon != null && icon !== false && (
        <span aria-hidden="true" style={{
          flex: '0 0 16px', textAlign: 'center', fontSize: 'var(--t-11)',
          // flex box, not just text-align: also holds filter menus' checkbox (a block, would sit left of centre otherwise)
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          ...(danger ? null : { color: 'var(--label-ink)' }),
        }}>{icon}</span>
      )}
      <span style={{
        minWidth: 0, flex: 1,
        ...(ellipsis ? { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } : null),
      }}>{children}</span>
      {hint != null && hint !== false && hint !== '' && (
        <Helper size="xs" mono={hintMono} style={{ flex: '0 0 auto', ...(selected ? { color: 'inherit' } : null) }}>{hint}</Helper>
      )}
    </>
  )
  if (href) {
    return (
      <a href={href} target={target} rel={target === '_blank' ? 'noreferrer' : undefined}
        role={role} onClick={disabled ? undefined : onClick} {...common}
        style={{ ...common.style, textDecoration: 'none' }}>{body}</a>
    )
  }
  return <div {...act(onClick, disabled, role)} {...common}>{body}</div>
}

// ── SectionHead ─────────────────────────────────────────────────────────────
// canonical: --section-head-ink · 12.5/18px · gap 6 · hover v2-hover-accent, the
// caret first, `aria-expanded` and Enter/Space driven by `open`/`onToggle`.
// The caret glyph is ⌄ / ›.
// Variants:
//   `boxed` — r6 · pad 2 4: a hover target slightly larger than the label (the Feed's report heads).
//   `card`  — the collapsible card header (Persona's autofill groups, résumé
//             sections, cover-letter editor): gap 9, card's own radius, ink
//             inherited from the card. Padding is layout, passed in `style`.
// `caret="end"` puts the glyph last, adjacent to the last child; `caret="pin"`
// pins it to the right edge (`margin-left:auto`); `caret={false}` draws none,
// for a head with its own (the cover-letter editor's rotating SVG chevron).
export function SectionHead({
  open = true, onToggle, count, boxed, card, caret = 'start', hover = 'v2-hover-accent',
  title, ariaLabel, children, style, className,
}) {
  const glyph = onToggle && caret ? (
    // explicit lineHeight:1 pins the caret box to the glyph's own 10px — without
    // it, a baseline-aligned head (ResumeSections) sits the glyph at a
    // font-dependent offset and the head's height shifts between themes.
    <span aria-hidden="true" style={{
      flex: '0 0 auto', fontSize: 'var(--t-10)', lineHeight: 1, color: 'var(--label-ink)',
      ...(caret === 'pin' ? { marginLeft: 'auto' } : null),
    }}>{open ? '⌄' : '›'}</span>
  ) : null
  return (
    <div {...act(onToggle, false)} title={title} aria-label={ariaLabel} aria-expanded={onToggle ? !!open : undefined}
      className={cx(onToggle && hover, className)}
      style={{
        display: 'flex', alignItems: 'center', gap: card ? 9 : 6,
        fontSize: 'var(--t-12-5)', lineHeight: '18px',
        ...(card ? null : { color: 'var(--section-head-ink)' }),
        ...(card ? { borderRadius: 'var(--radius-card)' } : null),
        ...(boxed ? { borderRadius: 'var(--radius-field)', padding: '2px 4px' } : null),
        ...(onToggle ? { cursor: 'pointer' } : null), ...style,
      }}>
      {caret === 'start' && glyph}
      {children}
      {count !== undefined && count !== null && <Helper size="xs" style={{ flex: '0 0 auto' }}>{count}</Helper>}
      {(caret === 'end' || caret === 'pin') && glyph}
    </div>
  )
}

// ── Chip ────────────────────────────────────────────────────────────────────
// the shelf copy chip: --chip-bg · 1px --chip-border · r99 · 11.5 · h26.
// hover (v2-chip) turns the border accent, the ink --chip-ink-hover and adds a
// 2px --chip-ring-hover halo.
// `on` is the picked chip: the same accent-soft fill Pill and Segmented use,
// navy in win98. Written inline from the --chip-on-* trio (a prop, like every
// other on-state here) rather than an `[aria-pressed]` CSS rule.
export function Chip({ on, disabled, onClick, title, ariaLabel, children, style, className }) {
  return (
    <div {...act(onClick, disabled)} title={title} aria-label={ariaLabel} aria-disabled={disabled || undefined}
      aria-pressed={on === undefined ? undefined : !!on}
      className={cx('v2-ctl', 'v2-raised', !disabled && onClick && 'v2-chip', className)}
      style={{
        flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 6,
        height: 26, padding: '0 10px', borderRadius: 'var(--radius-control)',
        background: on ? 'var(--chip-on-bg)' : 'var(--chip-bg)',
        color: on ? 'var(--chip-on-ink)' : 'var(--chip-ink)',
        border: `var(--bw-control) solid ${on ? 'var(--chip-on-border)' : 'var(--chip-border)'}`,
        boxShadow: 'var(--pill-shadow)',
        fontFamily: 'var(--font-body)', fontSize: 'var(--t-11-5)', whiteSpace: 'nowrap',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: onClick && !disabled ? 'pointer' : 'default', ...style,
      }}>{children}</div>
  )
}

// ── Tag / Dot ───────────────────────────────────────────────────────────────
// Tag canonical: r99 · 10px · pad 2 8 · .06em uppercase, tinted by tone.
// `tone="none"` sets no colour: the ATS/search-mode/tier badges are a separate
// hue taxonomy theme.css paints from a `cc-*`/`sm-*` class, and an inline tone
// would beat that class.
const TAG_TONE = {
  none: {},
  neutral: { background: 'var(--tag-neutral-bg)', color: 'var(--tag-neutral-ink)' },
  accent: { background: 'var(--tag-accent-bg)', color: 'var(--tag-accent-ink)' },
  good: { background: 'var(--tag-good-bg)', color: 'var(--tag-good-ink)' },
  warn: { background: 'var(--tag-warn-bg)', color: 'var(--tag-warn-ink)' },
  bad: { background: 'var(--tag-bad-bg)', color: 'var(--tag-bad-ink)' },
}
export function Tag({ tone = 'neutral', title, children, style, className }) {
  return (
    <span title={title} className={className} style={{
      flex: '0 0 auto', display: 'inline-flex', alignItems: 'center',
      borderRadius: 'var(--radius-control)', fontSize: 'var(--t-10)', lineHeight: '15px',
      // Tag is tracked tighter than Label (.06em vs .13em); not one caps scale,
      // so it keeps its own token rather than folding into --label-tracking.
      padding: '2px 8px', letterSpacing: 'var(--tag-tracking)', textTransform: 'var(--label-case)',
      fontWeight: 'var(--label-weight)',
      whiteSpace: 'nowrap', ...(TAG_TONE[tone] || TAG_TONE.neutral), ...style,
    }}>{children}</span>
  )
}
const DOT_TONE = {
  neutral: 'var(--dot-neutral)', accent: 'var(--dot-accent)',
  good: 'var(--dot-good)', warn: 'var(--dot-warn)', bad: 'var(--dot-bad)',
}
export function Dot({ tone = 'neutral', size = 7, title, style, className }) {
  return (
    <span title={title} aria-hidden={title ? undefined : 'true'} role={title ? 'img' : undefined} aria-label={title}
      className={className} style={{
        flex: '0 0 auto', display: 'inline-block', width: size, height: size,
        borderRadius: 'var(--radius-control)', background: DOT_TONE[tone] || DOT_TONE.neutral, ...style,
      }} />
  )
}

// ── GlyphBadge ──────────────────────────────────────────────────────────────
// The round box with ONE glyph in it: the toast's ✓/✕ mark, the sign-in tick,
// the error band's !, the welcome step numeral, the settings "i".
// Four sizes, each with the glyph size its sites already use:
//   15 → 9 · 16 → 9.5 · 22 → 11 · 34 → 16
// `tone="outline"` is the bordered form (the settings "i"); `on` gives it the
// same accent-soft trio a Pill wears. `mono` is the numeral form. `tone="none"`
// paints nothing, for the one caller whose ground is its own (the toast mark, tinted per kind).
const GLYPH_SIZE = { 15: 'var(--t-9)', 16: 'var(--t-9-5)', 22: 'var(--t-11)', 34: 'var(--t-16)' }
const GLYPH_TONE = {
  accent: { background: 'var(--glyph-accent-bg)', color: 'var(--glyph-accent-ink)' },
  bad: { background: 'var(--glyph-bad-bg)', color: 'var(--glyph-bad-ink)' },
  neutral: { background: 'var(--glyph-neutral-bg)', color: 'var(--glyph-neutral-ink)' },
  ai: { background: 'var(--ai)', color: 'var(--ai-ink)' },
  outline: {
    background: 'var(--glyph-bg)', color: 'var(--glyph-ink)',
    border: 'var(--bw-hair) solid var(--glyph-border)',
  },
  none: {},
}
const GLYPH_ON = {
  background: 'var(--glyph-on-bg)', color: 'var(--glyph-on-ink)',
  border: 'var(--bw-hair) solid var(--glyph-on-border)',
}
// `hover` is opt-in and unset by default — not every clickable badge wants one.
// `line` is opt-in too and not cosmetic: a glyph centred in a flex box sits at
// the centre of its own line box, and half-leading rounds differently at
// different line-heights, so forcing `line={1}` everywhere would shift some
// badges by a device pixel. Only the sites that need it pass it.
export function GlyphBadge({
  size = 16, tone = 'accent', on, mono, hover, line, onClick, disabled, title, ariaLabel,
  ariaExpanded, children, style, className,
}) {
  const live = !!onClick
  return (
    <span
      {...act(onClick, disabled, 'button')} title={title}
      aria-label={live ? (ariaLabel || title) : ariaLabel}
      aria-expanded={ariaExpanded} aria-disabled={disabled || undefined}
      aria-hidden={!live && !title && !ariaLabel ? 'true' : undefined}
      className={cx(live && !disabled && hover, className)}
      style={{
        width: size, height: size, borderRadius: 'var(--radius-control)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: GLYPH_SIZE[size] || GLYPH_SIZE[16],
        ...(line ? { lineHeight: line } : null),
        ...(mono ? { fontFamily: 'var(--font-mono)' } : null),
        ...(on ? GLYPH_ON : (GLYPH_TONE[tone] || GLYPH_TONE.accent)),
        ...(live ? { cursor: disabled ? 'default' : 'pointer' } : null), ...style,
      }}>{children}</span>
  )
}

// ── CopyGlyph ───────────────────────────────────────────────────────────────
// The "duplicate / copy to clipboard" mark. It used to be the character ⧉
// (U+29C9), which none of the app's font stacks covers on Linux/Chromium — it
// fell through to .notdef and drew an empty box in five places (R4-T2A-12).
// Drawn instead: two sheets, the back one an L so the front never overlaps a
// line. `currentColor`, so it inherits whatever ink its label uses; the 12px box
// matches the 11px glyph it replaces.
export function CopyGlyph({ size = 12, title, style, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" className={className}
      role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : 'true'}
      style={{ flex: '0 0 auto', display: 'block', ...style }}>
      <path d="M3.5 2.5V0.5h8v8h-2" fill="none" stroke="currentColor" />
      <rect x="0.5" y="3.5" width="8" height="8" fill="none" stroke="currentColor" />
    </svg>
  )
}

// ── Check / Radio ───────────────────────────────────────────────────────────
// The tick box and the radio disc (Feed row selector and its "select all shown"
// head cell, Feed's in-menu company checks, Searches' import-rules checks,
// drawer/modal option lists). One indicator, one set of tokens: --check-border
// at rest, the accent trio when on.
// `label` is optional — a bare indicator (a table's select cell) passes none
// and keeps its own `ariaLabel`. `indeterminate` is the "some but not all" tick
// the select-all cell shows over a partial selection.
const BOX_SIZE = { sm: 14, md: 15 }
function Indicator({ round, checked, indeterminate, size }) {
  const px = BOX_SIZE[size] || BOX_SIZE.sm
  const on = checked || indeterminate
  return (
    <span aria-hidden="true" style={{
      flex: `0 0 ${px}px`, width: px, height: px,
      borderRadius: round ? 'var(--radius-control)' : 'var(--radius-inline)',
      border: on ? 'none' : '1px solid var(--check-border)',
      background: on ? 'var(--check-on-bg)' : 'var(--check-bg)',
      color: 'var(--check-on-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 'var(--t-9)', lineHeight: 1,
    }}>{indeterminate ? '\u2013' : checked ? (round ? '\u25cf' : '\u2713') : ''}</span>
  )
}
function Ticker({ round, checked, indeterminate, onChange, label, title, ariaLabel, size = 'sm', disabled, style, className }) {
  const fire = onChange ? () => onChange(!checked) : undefined
  return (
    // A non-interactive indicator (a tick riding in a MenuItem's icon gutter,
    // where the row owns the click) still needs its role — act() hands back an
    // empty object without a handler, and aria-checked on a role-less span is ignored.
    <span role={round ? 'radio' : 'checkbox'} {...act(fire, disabled, round ? 'radio' : 'checkbox')}
      aria-checked={indeterminate && !round ? 'mixed' : !!checked}
      aria-label={ariaLabel || (typeof label === 'string' ? label : undefined)}
      aria-disabled={disabled || undefined} title={title} className={className}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, minWidth: 0,
        fontSize: 'var(--t-12)', color: 'var(--check-label-ink)',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled || !fire ? 'default' : 'pointer', ...style,
      }}>
      <Indicator round={round} checked={checked} indeterminate={indeterminate} size={size} />
      {label ? <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span> : null}
    </span>
  )
}
export function Check(props) { return <Ticker {...props} round={false} /> }
// The radio disc is the same box at --radius-control with a centred fill instead
// of a tick — the tick reads as "one of many", the disc as "one of these".
export function Radio(props) { return <Ticker {...props} round indeterminate={false} /> }

// ── Switch ──────────────────────────────────────────────────────────────────
// Track + sliding knob, the Settings geometry (26x15 track, 11px knob, 2px
// inset). --switch-knob-on is --surface-2 so the knob reads as a surface disc
// on the accent track in light and dark; OFF keeps --knob on a neutral track.
const SWITCH_SIZE = {
  md: { w: 26, h: 15, knob: 11, pad: 2 },
  sm: { w: 22, h: 13, knob: 9, pad: 2 },
}
export function Switch({ on, onChange, label, title, ariaLabel, size = 'md', disabled, style, className }) {
  const z = SWITCH_SIZE[size] || SWITCH_SIZE.md
  const fire = onChange ? () => onChange(!on) : undefined
  return (
    <span {...act(fire, disabled, 'switch')} aria-checked={!!on} aria-disabled={disabled || undefined}
      aria-label={ariaLabel || (typeof label === 'string' ? label : undefined)} title={title} className={className}
      style={{
        display: 'flex', alignItems: 'center', gap: 7, flex: '0 0 auto',
        opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled || !fire ? 'default' : 'pointer', ...style,
      }}>
      {label ? <Helper>{label}</Helper> : null}
      <span aria-hidden="true" style={{
        flex: '0 0 auto', position: 'relative', width: z.w, height: z.h,
        borderRadius: 'var(--radius-control)',
        background: on ? 'var(--switch-track-on)' : 'var(--switch-track-off)',
      }}>
        <span style={{
          position: 'absolute', top: z.pad, left: on ? z.w - z.knob - z.pad : z.pad,
          width: z.knob, height: z.knob, borderRadius: 'var(--radius-control)',
          background: on ? 'var(--switch-knob-on)' : 'var(--switch-knob-off)', transition: 'left 150ms',
        }} />
      </span>
    </span>
  )
}

// ── Segmented ───────────────────────────────────────────────────────────────
// A row of equal-flex cells with exactly one picked: the Applications stage
// stepper and its Log-modal twin, the Cover Letter length picker, Companies'
// depth/tier cells, Searches' auto-scoring Off/Light/Full. `options` is
// [{ value, label, hint, dots, dotColor, tone }].
//   dots      — how many status discs precede the label (Searches: 0/1/2). An
//                absent dot draws nothing at all, since an empty span would
//                still eat a gap and push its label off the cell's centre.
//   dotColor  — a fixed disc colour (the stage stepper's per-stage hue), drawn
//                whether or not the cell is picked.
//   tone      — 'accent' (default) or 'bad' for the picked look, so the
//                stepper's Rejected cell can close in red.
// `variant="inset"` is the framed two-cell toggle (the Feed's Live / Cached
// switch): one border run around the group, borderless cells inside it.
// Keyboard: the group is a radiogroup with a roving tabstop; left/right move and
// pick, Enter/Space picks the focused cell.
const SEG_SIZE = {
  sm: { height: 31, fontSize: 'var(--t-12)' },
  md: { height: 33, fontSize: 'var(--t-12)' },
  lg: { height: 34, fontSize: 'var(--t-12-5)' },
  inset: { height: 22, fontSize: 'var(--t-11)' },
}
const SEG_TONE = {
  accent: { bg: 'var(--seg-on-bg)', ink: 'var(--seg-on-ink)', border: 'var(--seg-on-border)' },
  bad: { bg: 'var(--seg-on-bad-bg)', ink: 'var(--seg-on-bad-ink)', border: 'var(--seg-on-bad-border)' },
}
export function Segmented({
  options = [], value, onChange, size = 'md', variant, gap = 5, grow = true,
  ariaLabel, disabled, style, className,
}) {
  const inset = variant === 'inset'
  const z = SEG_SIZE[inset ? 'inset' : size] || SEG_SIZE.md
  const idx = options.findIndex((o) => o.value === value)
  const move = (step) => {
    if (!options.length || !onChange) return
    const next = options[(Math.max(0, idx) + step + options.length) % options.length]
    if (next) onChange(next.value)
  }
  return (
    <div role="radiogroup" aria-label={ariaLabel} className={className}
      style={{
        display: 'flex', gap: inset ? 2 : gap, minWidth: 0,
        ...(inset ? {
          flex: '0 0 auto', padding: 2, background: 'var(--seg-inset-bg)',
          border: 'var(--bw-control) solid var(--seg-border)', borderRadius: 'var(--radius-control)',
        } : null), ...style,
      }}>
      {options.map((o, i) => {
        const on = o.value === value
        const t = SEG_TONE[o.tone] || SEG_TONE.accent
        const pick = onChange && !disabled ? () => { if (!on) onChange(o.value) } : undefined
        return (
          <div key={String(o.value)} role="radio" aria-checked={on} aria-disabled={disabled || undefined}
            title={o.hint || undefined} tabIndex={disabled ? -1 : ((on || (idx < 0 && i === 0)) ? 0 : -1)}
            // bevel hook rides the bordered cells only — an `inset` cell is
            // borderless inside one shared frame
            className={cx(!inset && 'v2-raised', !inset && !disabled && 'v2-bd')}
            onClick={pick}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); move(1) }
              else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
              else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (pick) pick() }
            }}
            style={{
              flex: grow && !inset ? 1 : '0 0 auto', minWidth: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              height: z.height, padding: inset ? '0 10px' : undefined,
              borderRadius: inset ? 'var(--radius-control)' : 'var(--radius-cell)',
              border: inset ? undefined : `var(--bw-control) solid ${on ? t.border : 'var(--seg-border)'}`,
              background: on ? t.bg : (inset ? 'transparent' : 'var(--seg-bg)'),
              color: on ? t.ink : (inset ? 'var(--seg-inset-ink)' : 'var(--seg-ink)'),
              // the picked cell is the only one a theme may lift (`none` here)
              ...(on && !inset ? { boxShadow: 'var(--seg-on-shadow)' } : null),
              fontFamily: 'var(--font-body)', fontSize: z.fontSize, lineHeight: 1,
              fontWeight: on && !inset ? 600 : 400, whiteSpace: 'nowrap',
              opacity: disabled ? 'var(--disabled-opacity)' : 1, cursor: disabled ? 'default' : 'pointer',
            }}>
            {o.dotColor ? <Dot style={{ background: o.dotColor }} /> : null}
            {o.dots ? Array.from({ length: o.dots }, (_, k) => (
              <Dot key={k} tone={on ? 'accent' : 'neutral'} size={6} style={{ marginRight: k === o.dots - 1 ? 0 : -4 }} />
            )) : null}
            {o.label}
          </div>
        )
      })}
    </div>
  )
}

// ── Meter ───────────────────────────────────────────────────────────────────
// A horizontal fill on a track: the report's criterion bars (1px), its keyword-
// coverage bar (4px) and the Stats funnel's stage bars (22px). `value` is 0-1.
// `tone` is a named fill or a raw `var(--...)` — the funnel colours a bar per
// stage from tokens that are not part of this scale, so it passes one through.
const METER_TONE = {
  accent: 'var(--meter-accent)', good: 'var(--meter-good)',
  warn: 'var(--meter-warn)', bad: 'var(--meter-bad)', neutral: 'var(--meter-neutral)',
}
export function Meter({ value = 0, tone = 'accent', height = 4, track, radius, ariaLabel, title, style, className }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100
  const r = radius || (height >= 12 ? 'var(--radius-mini)' : 'var(--radius-control)')
  const named = METER_TONE[tone]
  const fill = named || tone
  return (
    <div role="meter" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}
      aria-label={ariaLabel} title={title} className={className}
      style={{ height, borderRadius: r, background: track || 'var(--meter-track)', overflow: 'hidden', ...style }}>
      <div style={{ height: '100%', width: `${pct}%`, borderRadius: r, background: fill }} />
    </div>
  )
}

// ── ScoreRing ───────────────────────────────────────────────────────────────
// The circular fit score: an SVG arc over a --ring-track circle with the numeral
// centred inside it. Geometry is font-independent — the numeral sits in a
// flex-centred box at lineHeight 1, with no baseline nudge, so a theme that
// swaps the display face cannot pull the number off centre (it did, before this
// primitive: the sites each carried a hand-tuned `translateY(1px)`).
// `size` is 'sm' (34px, the report band and the resume editor) or 'md' (44px,
// the Feed row); a number is taken as an explicit box, and every size draws the
// same ring scaled to it (see RING_VB). `value` null renders the unscored state:
// a dashed ring with `label` inside — the label is **"No fit"** at every site, so
// it is the prop's default and no caller overrides it.
// `busy` draws the same ring with an indeterminate arc instead of a value — the
// loading state of a score, in the box the score will land in (the Feed row's own
// 44px Spinner was 6.5px wider than the ring it stood in for).
// `children` ride in the ring's own relative box — that is where the Feed's
// "+N reports" count badge pins itself.
const RING_SIZE = {
  sm: { box: 34, vb: 78, shift: 2, num: 'var(--t-14)', track: 5, letterSpacing: '-.02em', unscored: 'var(--t-7-5)' },  // vb 78 (r 15.26px, stroke 2.18) fits a 34 box without clipping
  md: { box: 44, vb: 88, shift: 1, num: 'var(--t-19)', track: 5, letterSpacing: undefined, unscored: 'var(--t-9-5)' },
}
const RING_TONE = {
  bad: { arc: 'var(--ring-bad-border)', ink: 'var(--ring-bad-ink)', bg: 'var(--ring-bad-bg)' },
  warn: { arc: 'var(--ring-warn-border)', ink: 'var(--ring-warn-ink)', bg: 'var(--ring-warn-bg)' },
  good: { arc: 'var(--ring-good-border)', ink: 'var(--ring-good-ink)', bg: 'var(--ring-good-bg)' },
  accent: { arc: 'var(--ring-accent-border)', ink: 'var(--ring-accent-ink)', bg: 'var(--ring-accent-bg)' },
  neutral: { arc: 'var(--ring-neutral-border)', ink: 'var(--ring-neutral-ink)', bg: 'var(--ring-neutral-bg)' },
}
// the score bands each screen used to re-declare as its own `scoreColor()`
export const scoreTone = (s) => (s == null ? 'neutral' : s >= 70 ? 'good' : s >= 50 ? 'warn' : 'bad')
const RING_R = 35   // the arc radius every ring site drew
// The viewBox is a constant (88, md's), not `2 x box`: a per-size viewBox would
// give a fixed 37.5px outer radius (r 35 + stroke/2) regardless of box, which
// overflows sm's 34px box and gets clipped by the SVG root's UA
// `overflow:hidden`. A constant viewBox makes every size a uniform scale of the
// same drawing, so an explicit numeric `size` scales cleanly too.
const RING_VB = 88
// ── the three non-ring variants ──────────────────────────────────────────────
// A theme may replace the DRAWING, not just its colours: `--ring-variant` names
// one of a closed set and ScoreRing renders it. The ring is the default; the
// other three are alternate score marks —
//   pill   a 40x44 tile, mono numeral over a small "fit" cap (cobalt)
//   bar    a mono numeral over a 32x3 track (saas)
//   ascii  `87 [████████░░]`, the bar filled from Math.round(score/10) (win98)
// Each carries the same three states the ring does: a value, unscored, and busy.
// The tone tokens are shared with the ring (--ring-*-ink); `pill` is the one that
// needs a ground as well, which is what the --sc-* pairs are for.
const SC_KEY = (s) => (s == null ? 'none' : s >= 70 ? 'hi' : s >= 50 ? 'mid' : 'lo')
function ScorePill({ value, busy }) {   // the tile paints from --sc-*, not the ring's ink
  const k = SC_KEY(value)
  return (
    <span style={{
      flex: '0 0 40px', width: 40, height: 44, borderRadius: 'var(--radius-field)',
      background: `var(--sc-${busy ? 'none' : k}-bg)`, color: `var(--sc-${k})`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 'var(--t-14)',
      lineHeight: 1, letterSpacing: '-.01em',
    }}>
      {busy ? <Spinner size={12} /> : (
        <>
          {value == null ? '—' : value}
          <span style={{
            fontFamily: 'var(--font-body)', fontSize: 'var(--t-9)', fontWeight: 600,
            letterSpacing: '.08em', textTransform: 'uppercase', opacity: 0.7, marginTop: 2,
          }}>fit</span>
        </>
      )}
    </span>
  )
}
function ScoreBar({ value, busy, ink }) {
  return (
    <span style={{
      flex: '0 0 40px', width: 40, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 4,
    }}>
      {busy ? <Spinner size={12} /> : (
        <>
          <span style={{
            fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 'var(--t-16)',
            lineHeight: 1, color: ink, fontVariantNumeric: 'tabular-nums',
          }}>{value == null ? '—' : value}</span>
          <Meter value={(value || 0) / 100} tone={ink} height={3} radius="var(--radius-mark)" style={{ width: 32 }} />
        </>
      )}
    </span>
  )
}
function ScoreAscii({ value, busy, ink }) {
  const n = value == null ? 0 : Math.max(0, Math.min(10, Math.round(value / 10)))
  return (
    <span style={{
      flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 2,
      fontFamily: 'var(--font-mono)', lineHeight: 1,
      color: busy ? 'var(--ring-neutral-ink)' : ink,
    }}>
      {busy ? <span style={{ fontSize: 'var(--t-9)' }}>[..........]</span> : (
        <>
          <span style={{ fontSize: 'var(--t-13)', fontWeight: 700 }}>{value == null ? '--' : value}</span>
          <span style={{ fontSize: 'var(--t-9)', letterSpacing: '-.02em' }}>{`[${'█'.repeat(n)}${'░'.repeat(10 - n)}]`}</span>
        </>
      )}
    </span>
  )
}
const SCORE_VARIANT = { pill: ScorePill, bar: ScoreBar, ascii: ScoreAscii }
// `variant` is an override for the gallery, which shows all four side by side;
// every real call site leaves it out and takes the theme's own.
export function ScoreRing({ value, size = 'md', weight, tone, label = 'No fit', busy, variant, title, ariaLabel, children, style, className }) {
  const z = typeof size === 'number' ? { ...RING_SIZE.md, box: size } : (RING_SIZE[size] || RING_SIZE.md)
  const t = RING_TONE[tone || scoreTone(value)] || RING_TONE.neutral
  const themeVariant = useThemeVar('--ring-variant', 'ring')
  const Alt = SCORE_VARIANT[variant || themeVariant]
  const vb = z.vb || RING_VB  // numeric sizes scale md's ring
  const stroke = weight || z.track
  const c = 2 * Math.PI * RING_R
  if (Alt) {
    return (
      <span className={className} title={title} role={ariaLabel ? 'img' : undefined} aria-label={ariaLabel}
        style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', ...style }}>
        <Alt value={value} busy={busy} ink={t.ink} />
        {children}
      </span>
    )
  }
  return (
    <div className={className} title={title} role={ariaLabel ? 'img' : undefined} aria-label={ariaLabel}
      style={{ position: 'relative', boxSizing: 'border-box', flex: `0 0 ${z.box}px`, width: z.box, height: z.box, ...style }}>
      {/* `busy` is the same drawing with an indeterminate quarter-arc spinning on
          the track: a score that is being computed occupies the box the score will
          occupy, at the same diameter and band, so nothing shifts when it lands. */}
      {busy ? (
        <svg className="v2-spin" viewBox={`0 0 ${vb} ${vb}`} style={{ width: z.box, height: z.box, transformOrigin: '50% 50%' }} aria-hidden="true">
          <circle cx={vb / 2} cy={vb / 2} r={RING_R} fill="none" stroke="var(--ring-track)" strokeWidth={stroke} />
          <circle cx={vb / 2} cy={vb / 2} r={RING_R} fill="none" stroke={RING_TONE.accent.arc} strokeWidth={stroke} strokeLinecap="round"
            strokeDasharray={`${(c * 0.25).toFixed(1)} ${c.toFixed(0)}`}
            transform={`rotate(-90 ${vb / 2} ${vb / 2})`} />
        </svg>
      ) : value == null ? (
        <div style={{
          width: '100%', height: '100%', boxSizing: 'border-box', border: '1px dashed var(--ring-neutral-border)',
          borderRadius: 'var(--radius-control)', background: t.bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
          fontFamily: 'var(--font-body)', fontSize: z.unscored, letterSpacing: '.1em',
          textTransform: 'uppercase', color: 'var(--ring-neutral-ink)',
          transform: 'translateY(var(--ring-label-shift, 0px))',
        }}>{label}</div>
      ) : (
        <>
          <svg viewBox={`0 0 ${vb} ${vb}`} style={{ width: z.box, height: z.box }} aria-hidden="true">
            <circle cx={vb / 2} cy={vb / 2} r={RING_R} fill="none" stroke="var(--ring-track)" strokeWidth={stroke} />
            <circle cx={vb / 2} cy={vb / 2} r={RING_R} fill="none" stroke={t.arc} strokeWidth={stroke} strokeLinecap="round"
              strokeDasharray={`${(c * Math.max(0, Math.min(100, value)) / 100).toFixed(1)} ${c.toFixed(0)}`}
              transform={`rotate(-90 ${vb / 2} ${vb / 2})`} />
          </svg>
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            lineHeight: 1, fontFamily: 'var(--font-display)', fontSize: z.num,
            letterSpacing: z.letterSpacing, color: t.ink,
            transform: `translateY(var(--ring-shift-${size === 'sm' ? 'sm' : 'md'}, ${z.shift || 0}px))`,  // optical centre per theme (font metrics differ): tokens in theme.css
          }}>{value}</div>
        </>
      )}
      {children}
    </div>
  )
}

// ── ToastCard ───────────────────────────────────────────────────────────────
// The toast card's box, moved out of Toast.jsx (which keeps the taxonomy, the
// TTL table and the stack). `kind` picks the ground: progress / success / error
// / undo, each a --toast-*-bg / -line / -ink triple.
const TOAST_KIND = {
  progress: { bg: 'var(--toast-progress-bg)', line: 'var(--toast-progress-line)', ink: 'var(--toast-progress-ink)' },
  success: { bg: 'var(--toast-ok-bg)', line: 'var(--toast-ok-line)', ink: 'var(--toast-ok-ink)' },
  error: { bg: 'var(--toast-bad-bg)', line: 'var(--toast-bad-line)', ink: 'var(--toast-bad-ink)' },
  undo: { bg: 'var(--toast-undo-bg)', line: 'var(--toast-undo-line)', ink: 'var(--toast-undo-ink)' },
}
export function ToastCard({ kind = 'progress', children, style, className }) {
  const k = TOAST_KIND[kind] || TOAST_KIND.progress
  return (
    <div className={cx('v2-raised', className)} style={{
      display: 'flex', alignItems: 'center', gap: 10, maxWidth: 380, padding: '10px 13px',
      background: k.bg, border: `var(--bw-panel) solid ${k.line}`, borderRadius: 'var(--radius-card)', color: k.ink,
      boxShadow: 'var(--shadow-toast)', ...style,
    }}>{children}</div>
  )
}

// ── Link / NavLink ──────────────────────────────────────────────────────────
// Link canonical: accent · 11.5 · 500, hover v2-hover-accent-text.
// NavLink is the "‹ back"/section jump: accent · 12, hover washes to
// --navlink-hover-bg with --navlink-hover-ink.
// `rel` overrides the default so an anchor can spell out `noopener noreferrer`
// (Settings' colophon, the Companies test-row ↗) without leaving the primitive.
export function Link({ href, target, rel, onClick, title, ariaLabel, children, style, className }) {
  const st = {
    color: 'var(--link-ink)', fontSize: 'var(--t-11-5)', lineHeight: '17px', fontWeight: 500,
    cursor: 'pointer', ...style,
  }
  const cls = cx('v2-hover-accent-text', className)
  if (href) {
    return <a href={href} target={target} rel={rel || (target === '_blank' ? 'noreferrer' : undefined)} title={title} aria-label={ariaLabel} className={cls} style={st}>{children}</a>
  }
  return <span {...act(onClick, false, 'link')} title={title} aria-label={ariaLabel} className={cls} style={st}>{children}</span>
}
export function NavLink({ pad, onClick, title, ariaLabel, children, style, className }) {
  return (
    <span {...act(onClick, false, 'link')} title={title} aria-label={ariaLabel}
      className={cx('v2-navlink', className)}
      style={{ color: 'var(--navlink-ink)', fontSize: 'var(--t-12)', lineHeight: '18px', padding: pad, cursor: 'pointer', ...style }}>
      {children}
    </span>
  )
}

// ── RemoveLink / RemoveX / MoveArrows ───────────────────────────────────────
// The three row affordances every list editor carries, given one definition and
// one hover here; `ResumeSections.jsx` re-exports the two old names so existing
// imports are untouched.
//
// RemoveLink is the worded form ("Remove role") that closes a card; RemoveX the
// glyph a single row carries. Both are muted at rest and swing to --hover-bad-*
// on hover (`v2-hover-bad` washes the box, `v2-hover-bad-text` the ink).
export const RemoveLink = ({ onClick, children = 'Remove' }) => (
  <span {...act(onClick, false)} className="v2-hover-bad v2-hover-bad-text"
    style={{ fontSize: 'var(--t-11-5)', lineHeight: '17px', color: 'var(--helper-ink)', cursor: 'pointer', whiteSpace: 'nowrap' }}>{children}</span>
)
export const RemoveX = ({ onClick, title = 'Remove', size = 11, lh }) => (
  <span {...act(onClick, false)} title={title} aria-label={title} className="v2-hover-bad v2-hover-bad-text"
    style={{ flex: '0 0 auto', color: 'var(--helper-ink)', fontSize: size, cursor: 'pointer', lineHeight: lh }}>✕</span>
)
// The reorder pair: an 8px ▲▼ column at --helper-ink, each arrow a `v2-navlink`.
// `upOff` / `downOff` dim an end of the list to 0.35 and take the hover and pointer away.
export function MoveArrows({ onUp, onDown, upOff, downOff, style, className }) {
  const arrow = (fn, off, title, glyph) => (
    <span {...act(fn, off)} title={title} aria-disabled={off || undefined} className={off ? undefined : 'v2-navlink'}
      style={{ opacity: off ? 0.35 : 1, cursor: off ? 'default' : 'pointer' }}>{glyph}</span>
  )
  return (
    <span className={className} style={{
      flex: '0 0 auto', display: 'flex', flexDirection: 'column', gap: 1,
      color: 'var(--helper-ink)', fontSize: 8, ...style,
    }}>
      {arrow(onUp, upOff, 'Move up', '▲')}
      {arrow(onDown, downOff, 'Move down', '▼')}
    </span>
  )
}

// ── ModalPanel / Drawer ─────────────────────────────────────────────────────
// ModalPanel canonical: surface · 1px --modal-border · r12 · --modal-shadow,
// on a --scrim-bg scrim. Escape closes (useEscape) and the panel is pulled back
// onto the pixel grid (useSnapTop).
//
// `as="form"` + `onSubmit` renders the panel as a real <form>, for the sign-in
// overlay where Enter-in-the-field must submit. `scrimProps` carries the
// attributes the two global overlays (which mount outside the v2 shell) put on
// the scrim to bring the theme look with them; `zIndex` is theirs too, since
// they sit above everything including an open modal. A panel with no `onClose`
// takes no Escape listener rather than one that swallows the key and does nothing.
// `escape={false}` is for a screen that already owns Escape for its whole modal
// set (Applications and Settings close every overlay from one handler that
// stands down while a ConfirmDialog is up) — a second listener here would close
// the modal under that confirm.
// `titlebar` is the caption a themed window chrome shows, mounted only where
// `--title-bar` is a gradient (win98).
// `escapeCapture` belongs to those same two global overlays: they sit above
// every screen, so they take Escape in the capture phase and keep it, instead of
// losing it to the screen that mounted first (see useEscape).
export function ModalPanel({
  width = 480, as, onSubmit, onClose, escape = true, escapeCapture = false, labelledBy, zIndex = 70, titlebar,
  children, style, className, scrimStyle, scrimProps,
}) {
  useEscape(onClose, escape && !!onClose, escapeCapture)
  const panel = useRef(null)
  useSnapTop(panel)
  const chrome = useTitleBar()
  const Panel = as === 'form' ? 'form' : 'div'
  return (
    <div onClick={onClose} {...scrimProps} style={{
      position: 'fixed', inset: 0, background: 'var(--scrim-bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex, ...scrimStyle,
    }}>
      <Panel ref={panel} role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        onSubmit={onSubmit} onClick={(e) => e.stopPropagation()} className={cx('v2-raised', className)}
        style={{
          width, background: 'var(--modal-bg)', border: 'var(--bw-panel) solid var(--modal-border)',
          borderRadius: 'var(--radius-modal)', boxShadow: 'var(--modal-shadow)',
          display: 'flex', flexDirection: 'column', minHeight: 0, ...style,
        }}>
        {chrome && <HeaderRow variant="titlebar" onClose={onClose}>{titlebar}</HeaderRow>}
        {children}
      </Panel>
    </div>
  )
}
// The drawer is positioned against its pane, not the viewport, so its scrim is
// absolute too (Companies: the rail stays reachable while a company is open).
export function Drawer({ width = 720, onClose, labelledBy, titlebar, children, style, className }) {
  useEscape(onClose)
  const chrome = useTitleBar()
  return (
    <>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'var(--scrim-bg)', zIndex: 29 }} />
      {/* no `v2-raised` here: the drawer's only border is its left edge, and the
          bevel rule writes the `border` shorthand — in a theme where it is inert
          that hands the other three sides `border-color:transparent` for nothing.
          win98's drawer keeps its hard --shadow-drawer offset instead. */}
      <div role="dialog" aria-modal="true" aria-labelledby={labelledBy} className={className}
        style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width,
          background: 'var(--drawer-bg)', borderLeft: 'var(--bw-panel) solid var(--drawer-border)',
          boxShadow: 'var(--drawer-shadow)', display: 'flex', flexDirection: 'column', zIndex: 30, ...style,
        }}>
        {chrome && <HeaderRow variant="titlebar" onClose={onClose}>{titlebar}</HeaderRow>}
        {children}
      </div>
    </>
  )
}

// ── HeaderRow ───────────────────────────────────────────────────────────────
// canonical (modal/drawer header): pad 16 22 13 + --head-line beneath.
// `screen` is the page header (22 30 16), `compact` the tighter modal head
// (15 22 12); `soft` swaps the rule for --head-line-soft, `strong` for
// --head-line-strong.
// `pad` is the escape hatch for the handful of heads whose gutter is set by the
// pane they sit in (a toolbar inset to a list's own 24/30px rails, the PDF
// preview strip). It stays a named prop rather than an inline `padding` so the
// site still reads as a HeaderRow and the stylelint has one thing to look at.
// `id` is a zero-pixel passthrough (the Feed's sticky head is measured by id).
// `bg` is the head's ground for the strips that are painted rather than
// transparent — a sticky pane head on --head-bg, a column strip on --head-bg-page,
// a recessed sub-band on --head-bg-recessed. Named, so a screen never inlines a
// background token of its own.
const HEAD_PAD = { modal: '16px 22px 13px', screen: '22px 30px 16px', compact: '15px 22px 12px' }
const HEAD_BG = { surface: 'var(--head-bg)', page: 'var(--head-bg-page)', recessed: 'var(--head-bg-recessed)' }
// `as="header"` keeps the <header> landmark the five screen heads already are —
// the role is the same box either way, but a screen title deserves its element.
// `line="none"` is the screen head that carries no rule at all (the four list
// screens whose filter bar draws the only line under the title block).
const HEAD_LINE = { line: 'var(--head-line)', soft: 'var(--head-line-soft)', strong: 'var(--head-line-strong)' }
// `--title-bar` is `none` in every theme but win98, where it is the two-stop
// gradient of a Windows caption bar. A panel asks this hook whether the chrome
// exists before it mounts a `variant="titlebar"` head — a question about the
// cascade rather than a style value, since a theme is allowed to change composition here.
export function useTitleBar() {
  const bar = useThemeVar('--title-bar', 'none')
  return !!bar && bar !== 'none'
}
export function HeaderRow({
  as, variant = 'modal', pad, bg, line, soft, strong, height, align = 'flex-start',
  onClose, id, children, style, className, ...rest
}) {
  const tone = line || (strong ? 'strong' : soft ? 'soft' : 'line')
  const El = as === 'header' ? 'header' : 'div'
  // The caption bar: 22px, the caption on the gradient, and the _ □ × group of
  // bevelled glyph boxes pinned right (only × acts — a modal has no minimise or
  // maximise, and a dead control is worse than none, so the other two are inert
  // and hidden from the accessibility tree with the group).
  if (variant === 'titlebar') {
    return (
      <El id={id} className={className} {...rest} style={{
        flex: '0 0 auto', height: 22, padding: '0 3px 0 6px',
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--title-bar)', color: 'var(--title-bar-ink)',
        fontFamily: 'var(--font-body)', fontSize: 'var(--t-12)', fontWeight: 'var(--label-weight)',
        lineHeight: 1, ...style,
      }}>
        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{children}</span>
        <span style={{ marginLeft: 'auto', flex: '0 0 auto', display: 'flex', gap: 2 }}>
          {['_', '□', '×'].map((g) => (
            <span key={g} className="v2-raised"
              {...(g === '×' && onClose ? { ...act(onClose, false), title: 'Close', 'aria-label': 'Close' } : { 'aria-hidden': 'true' })}
              style={{
                width: 16, height: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-ink)',
                fontFamily: 'var(--font-mono)', fontSize: 'var(--t-9)', lineHeight: 1,
                cursor: g === '×' && onClose ? 'pointer' : 'default',
              }}>{g}</span>
          ))}
        </span>
      </El>
    )
  }
  return (
    <El id={id} className={className} {...rest} style={{
      flex: '0 0 auto', padding: pad || HEAD_PAD[variant] || HEAD_PAD.modal,
      ...(tone === 'none' ? null : { borderBottom: `1px solid ${HEAD_LINE[tone] || HEAD_LINE.line}` }),
      display: 'flex', alignItems: align, gap: 12,
      ...(bg ? { background: HEAD_BG[bg] || HEAD_BG.surface } : null),
      ...(height ? { height } : null), ...style,
    }}>{children}</El>
  )
}

// ── TableHead ───────────────────────────────────────────────────────────────
// The column-caption strip above a flat list: --bg ground, --label-ink, 9.5/14px
// uppercase at .11em, a --head-line-strong hairline beneath and the list's own
// side gutter. Height and gutter are the list's, everything type-and-colour is
// the role's. `top` adds the --head-line-soft rule above (the Stats cards, where
// the strip sits between two blocks rather than at the top of a pane).
export function TableHead({ height = 28, pad = '0 22px', soft, top, children, style, className }) {
  return (
    // no `role="row"`: these strips are flex boxes, not rows of a role="table",
    // and an orphan row role is worse than none
    <div className={className} style={{
      flex: '0 0 auto', display: 'flex', alignItems: 'center', height, padding: pad,
      background: 'var(--head-bg-page)', color: 'var(--label-ink)',
      // .11em, between Label's .13 and Tag's .06 — a third value, kept as a third
      // name (--label-tracking-strip) instead of being rounded into --label-tracking
      fontSize: 'var(--t-9-5)', lineHeight: '14px',
      letterSpacing: 'var(--label-tracking-strip)', textTransform: 'var(--label-case)',
      fontWeight: 'var(--label-weight)',
      borderBottom: `var(--bw-hair) solid ${soft ? 'var(--head-line-soft)' : 'var(--head-line-strong)'}`,
      ...(top ? { borderTop: 'var(--bw-hair) solid var(--head-line-soft)' } : null), ...style,
    }}>{children}</div>
  )
}

// ── Rule ────────────────────────────────────────────────────────────────────
// The 1px hairline that is *not* a border on something else: the divider between
// two blocks of a drawer, the filler between a label and its trailing count, the
// vertical tick between two facts in a band. `tone` picks the same two tokens
// every border in v2 uses; `vertical` turns it on its side (`length` = its run).
const RULE_TONE = { soft: 'var(--head-line-soft)', line: 'var(--head-line)', strong: 'var(--head-line-strong)' }
export function Rule({ tone = 'soft', vertical, length, style, className }) {
  return (
    <span aria-hidden="true" className={className} style={{
      display: 'block', background: RULE_TONE[tone] || RULE_TONE.soft,
      ...(vertical ? { flex: '0 0 auto', width: 1, height: length ?? 14 } : { height: 1 }),
      ...style,
    }} />
  )
}

// ── Surface ─────────────────────────────────────────────────────────────────
// A recessed block: the recessed ground with a radius from the same scale
// everything else uses. `radius="none"` is the full-bleed pane form (the PDF
// preview column), where the block runs edge to edge and has nothing to round.
// U-16 / handoff §4.11: it read the PALETTE name --surface-2 directly; the
// semantic name for that ground already existed as --head-bg-recessed (the third
// entry in HeaderRow's ground map) and points at the same palette token, so this
// is a same-value re-point, not a repaint.
const SURFACE_RADIUS = {
  none: undefined, field: 'var(--radius-field)', row: 'var(--radius-row)',
  card: 'var(--radius-card)', menu: 'var(--radius-menu)',
}
export function Surface({ as, radius = 'card', pad, children, style, className, ...rest }) {
  const El = as === 'section' ? 'section' : 'div'
  return (
    <El className={className} {...rest} style={{
      background: 'var(--head-bg-recessed)', borderRadius: SURFACE_RADIUS[radius],
      ...(pad ? { padding: pad } : null), ...style,
    }}>{children}</El>
  )
}

// ── Notice ──────────────────────────────────────────────────────────────────
// The tinted banner with a mark, a body and an action: the company drawer's
// scrape-warning band is the shipped example — a warn/bad/quiet ground with a
// ▲, the message, and "Acknowledge" pinned right.
// `action` is rendered as a direct child, not in a wrapper: the CTA brings its
// own alignment (the acknowledge link tops itself against a two-line body).
const NOTICE_TONE = {
  warn: { background: 'var(--notice-warn-bg)', border: 'var(--notice-warn-border)', mark: 'var(--notice-warn-mark)' },
  bad: { background: 'var(--notice-bad-bg)', border: 'var(--notice-bad-border)', mark: 'var(--notice-bad-mark)' },
  quiet: { background: 'var(--notice-quiet-bg)', border: 'var(--notice-quiet-border)', mark: 'var(--notice-quiet-mark)' },
}
export function Notice({ tone = 'warn', glyph = '▲', action, children, style, className }) {
  const t = NOTICE_TONE[tone] || NOTICE_TONE.warn
  return (
    <div className={className} style={{
      display: 'flex', gap: 9, padding: '11px 13px',
      border: `var(--bw-panel) solid ${t.border}`, background: t.background,
      borderRadius: 'var(--radius-card)', ...style,
    }}>
      {glyph && <span aria-hidden="true" style={{ flex: '0 0 auto', fontSize: 'var(--t-12)', color: t.mark }}>{glyph}</span>}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>{children}</div>
      {action}
    </div>
  )
}

// ── Label / Helper / Heading / PageTitle ────────────────────────────────────
// Label canonical: muted · 10 · uppercase · .13em. `size="lg"` is the 11px form.
const LABEL_SIZE = {
  md: { fontSize: 'var(--t-10)', lineHeight: '15px' },
  lg: { fontSize: 'var(--t-11)', lineHeight: '16px' },
}
export function Label({ size = 'md', htmlFor, title, children, style, className }) {
  const st = {
    letterSpacing: 'var(--label-tracking)', textTransform: 'var(--label-case)',
    fontWeight: 'var(--label-weight)', color: 'var(--label-ink)',
    ...(LABEL_SIZE[size] || LABEL_SIZE.md), ...style,
  }
  if (htmlFor) return <label htmlFor={htmlFor} title={title} className={className} style={st}>{children}</label>
  return <span title={title} className={className} style={st}>{children}</span>
}
// Helper canonical: muted · 11.5/16px. `size="xs"` is the 10.5/16 form.
const HELPER_SIZE = {
  md: { fontSize: 'var(--t-11-5)', lineHeight: '16px' },
  xs: { fontSize: 'var(--t-10-5)', lineHeight: '16px' },
}
// `onClick` makes the sub-line itself the control (Applications' interview slot
// line): it gets `kb()` and the pointer, so a muted line that acts stops being a
// hand-written span. Inert helpers are untouched — no cursor, no tab stop.
export function Helper({ size = 'md', mono, onClick, title, ariaLabel, children, style, className }) {
  return (
    <span {...act(onClick, false)} title={title} aria-label={ariaLabel} className={className} style={{
      color: 'var(--helper-ink)', fontFamily: mono ? 'var(--font-mono)' : undefined,
      ...(HELPER_SIZE[size] || HELPER_SIZE.md),
      ...(onClick ? { cursor: 'pointer' } : null), ...style,
    }}>{children}</span>
  )
}
// ── Mono ────────────────────────────────────────────────────────────────────
// The monospaced RUN — an id, a timestamp, a count, a score numeral. Separate
// from Helper's `mono` since this role takes five inks, not just --helper-ink.
// Sizes are the five stops the sites use; `md` (10.5) is the dominant. `line`
// pins the whole-pixel leading where the run has to sit on a shared baseline
// (a 16px row, an 18px table line); left off, the run inherits.
// `tone` is optional on purpose: three of the sites paint from a score colour
// the caller computes, and they pass it as `style.color` with no tone at all.
const MONO_SIZE = {
  xs: 'var(--t-9-5)', sm: 'var(--t-10)', md: 'var(--t-10-5)',
  lg: 'var(--t-11)', xl: 'var(--t-11-5)',
}
const MONO_LINE = { 14: '14px', 16: '16px', 18: '18px' }
const MONO_TONE = {
  base: 'var(--mono-ink)', muted: 'var(--mono-ink-muted)', faint: 'var(--mono-ink-faint)',
  strong: 'var(--mono-ink-strong)', accent: 'var(--mono-ink-accent)',
}
export function Mono({ size = 'md', tone, line, title, ariaLabel, children, style, className }) {
  return (
    <span title={title} aria-label={ariaLabel} className={className} style={{
      fontFamily: 'var(--font-mono)', fontSize: MONO_SIZE[size] || MONO_SIZE.md,
      ...(tone ? { color: MONO_TONE[tone] || MONO_TONE.base } : null),
      ...(line ? { lineHeight: MONO_LINE[line] || MONO_LINE[16] } : null), ...style,
    }}>{children}</span>
  )
}

// Heading canonical: serif 18 · -.02em · weight 400 (inherited). 19 and 22 are
// the two larger steps.
const HEADING_SIZE = {
  18: { fontSize: 'var(--t-18)', lineHeight: '27px' },
  19: { fontSize: 'var(--t-19)', lineHeight: '26px' },
  22: { fontSize: 'var(--t-22)', lineHeight: '30px' },
}
// `strong` is v2's second serif family: the card/column/drawer-section title,
// set heavier (500, or 600 where asked for) and tracked tighter than the
// 400-weight display scale — -.01em up to 16, -.015em from 17. Allowed sizes
// are 15 · 15.5 · 16 · 17 · 18 · 19, exactly the sizes already drawn.
// Line-height is pinned to a whole pixel per size: left unset these titles
// inherit preflight's 1.5 and land on a .5px height that Chrome rounds a 1px
// border away from. 19 takes 26 so the 400- and 500-weight 19s share a box.
// A card needing a different integer height passes its own line-height in
// `style` (the cover-letter row at 22, the Feed's two-line title block at 1.15).
const HEADING_STRONG = {
  15: { fontSize: 'var(--t-15)', lineHeight: '22px', letterSpacing: '-.01em' },
  15.5: { fontSize: 'var(--t-15-5)', lineHeight: '23px', letterSpacing: '-.01em' },
  16: { fontSize: 'var(--t-16)', lineHeight: '24px', letterSpacing: '-.01em' },
  17: { fontSize: 'var(--t-17)', lineHeight: '25px', letterSpacing: '-.015em' },
  18: { fontSize: 'var(--t-18)', lineHeight: '27px', letterSpacing: '-.015em' },
  19: { fontSize: 'var(--t-19)', lineHeight: '26px', letterSpacing: '-.015em' },
}
export function Heading({ size, strong, id, title, children, style, className }) {
  // `strong` keeps its OWN weight/tracking (500/600 at -.01/-.015em, per size);
  // --title-weight/--display-tracking belong to the 400-weight plain scale only.
  const look = strong
    ? { fontWeight: strong === 600 ? 600 : 500, ...(HEADING_STRONG[size ?? 15.5] || HEADING_STRONG[15.5]) }
    : { fontWeight: 'var(--title-weight)', letterSpacing: 'var(--display-tracking)', ...(HEADING_SIZE[size ?? 18] || HEADING_SIZE[18]) }
  return (
    <span id={id} title={title} className={className} style={{
      fontFamily: 'var(--font-display)', color: 'var(--heading-ink)', ...look, ...style,
    }}>{children}</span>
  )
}
// The one screen title: serif 30/400, line-height 1.
export function PageTitle({ id, children, style, className }) {
  return (
    <h1 id={id} className={className} style={{
      margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--t-30)', fontWeight: 'var(--title-weight)',
      lineHeight: 1, letterSpacing: 'var(--display-tracking)', color: 'var(--heading-ink)', ...style,
    }}>{children}</h1>
  )
}

// ── ShowMore ────────────────────────────────────────────────────────────────
// The client-side pager the résumé shelf, Companies test results and the Stats
// logs share, verbatim.
export function ShowMore({ n, onClick, label, style, className }) {
  return (
    <div className={className} style={{ display: 'flex', justifyContent: 'center', padding: '10px 20px 12px', ...style }}>
      <span {...act(onClick, false)} className="v2-bdc v2-ctl" style={{
        height: 26, padding: '0 13px', border: '1px solid var(--pill-border)',
        borderRadius: 'var(--radius-control)', display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 'var(--t-11-5)', color: 'var(--pill-ink)', cursor: 'pointer',
      }}>{label || `Show ${n} more`}</span>
    </div>
  )
}

// ── ChoiceCard / ChoiceRow / ChoiceModal ────────────────────────────────────
// The "pick one thing, then commit" modal three screens share: the résumé
// editor's Tailor and Re-tailor modals and the Persona's Import. Geometry
// matches the Re-tailor modal — 480 panel · modal head (16/22/13) · body 14/22
// on a 460 cap · footer 12/22 over a --modal-border rule.
//
//   ChoiceCard  — the option cards at the top of the body ("✦ Tailor" vs
//     "Copy", "From a résumé" vs "From a PDF"): a padded cell with a title and
//     a hint, accent-soft when picked. A row of them sits in one flex line.
//   ChoiceRow   — one candidate in the list below (a base résumé, a job): radio
//     disc · name (+ optional sub-line) · trailing hint · `trail` extras.
//   ChoiceModal — the shell: head (title + sub), the scrolling body, and the
//     footer whose left column carries the consequence note ("Runs in the
//     background", the chain-score line, the Persona's replace warning) beside
//     Cancel + the one action.
//
// Both cells are keyboard-operable through act(): Enter/Space picks, and the
// panel's own useEscape (ModalPanel) closes.
export function ChoiceCard({ on, disabled, label, hint, onClick, title, ariaLabel, style, className }) {
  return (
    <div {...act(onClick, disabled, 'radio')} title={title} aria-label={ariaLabel}
      aria-checked={!!on} aria-disabled={disabled || undefined}
      className={cx(!disabled && 'v2-act', className)}
      style={{
        flex: 1, minWidth: 0, padding: '9px 11px',
        border: `1px solid ${on ? 'var(--choice-on-border)' : 'var(--choice-border)'}`,
        background: on ? 'var(--choice-on-bg)' : 'var(--choice-bg)',
        borderRadius: 'var(--radius-cell)', display: 'flex', flexDirection: 'column', gap: 2,
        opacity: disabled ? 0.45 : 1, cursor: disabled ? 'default' : 'pointer', ...style,
      }}>
      <span style={{
        fontSize: 'var(--t-12-5)', lineHeight: '18px', fontWeight: 500,
        color: on ? 'var(--choice-on-ink)' : 'var(--choice-ink)',
      }}>{label}</span>
      {hint != null && hint !== false && hint !== '' && (
        <Helper size="xs" style={{ textWrap: 'pretty' }}>{hint}</Helper>
      )}
    </div>
  )
}
// `children` replaces the label/sub pair for a body that is not two lines of
// text; `trail` is whatever sits right of the hint (a score, an "✦ exists" mark).
export function ChoiceRow({
  on, disabled, label, sub, hint, trail, onClick, title, ariaLabel, children, style, className,
}) {
  return (
    <div {...act(onClick, disabled, 'radio')} title={title} aria-label={ariaLabel}
      aria-checked={!!on} aria-disabled={disabled || undefined}
      className={cx(!disabled && 'v2-act', className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 9, padding: '8px 11px',
        border: `1px solid ${on ? 'var(--choice-on-border)' : 'var(--choice-border)'}`,
        background: on ? 'var(--choice-on-bg)' : 'var(--choice-bg)',
        borderRadius: 'var(--radius-cell)',
        opacity: disabled ? 0.45 : 1, cursor: disabled ? 'default' : 'pointer', ...style,
      }}>
      <span aria-hidden="true" style={{
        flex: '0 0 auto', width: 14, height: 14, borderRadius: 'var(--radius-control)',
        border: `1px solid ${on ? 'var(--choice-on-border)' : 'var(--choice-border)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: 'var(--radius-control)',
          background: on ? 'var(--choice-on-border)' : 'transparent',
        }} />
      </span>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {children === undefined ? (
          <>
            <span style={{
              fontSize: 'var(--t-12-5)', lineHeight: '18px', fontWeight: 500,
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            }}>{label}</span>
            {sub != null && sub !== false && sub !== '' && (
              <Helper size="xs" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</Helper>
            )}
          </>
        ) : children}
      </div>
      {hint != null && hint !== false && hint !== '' && (
        <Helper size="xs" style={{ flex: '0 0 auto' }}>{hint}</Helper>
      )}
      {trail}
    </div>
  )
}
// `bodyGap` is the one dimension the two résumé modals already disagreed on
// (Re-tailor 13, Tailor 12); it stays a prop so naming the shell moves no pixel.
// `note` is the footer's left column — a fragment of Helpers, not a string.
export function ChoiceModal({
  width = 480, title, sub, subClamp, labelledBy, note,
  cancel = 'Cancel', action, actionVariant, actionDisabled, actionBusy, onAction,
  bodyGap = 13, bodyMax = 460, onClose, zIndex = 60, children, style, className,
}) {
  return (
    <ModalPanel width={width} onClose={onClose} zIndex={zIndex} labelledBy={labelledBy}
      className={className} style={{ overflow: 'hidden', ...style }}>
      <HeaderRow align="stretch" style={{ flexDirection: 'column', gap: 3 }}>
        <Heading id={labelledBy}>{title}</Heading>
        {sub != null && sub !== false && (
          <Helper style={subClamp ? { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } : undefined}>{sub}</Helper>
        )}
      </HeaderRow>
      <div className="v2-scroll" style={{
        padding: '14px 22px', display: 'flex', flexDirection: 'column',
        gap: bodyGap, maxHeight: bodyMax, overflow: 'auto',
      }}>{children}</div>
      <div style={{
        padding: '12px 22px', borderTop: '1px solid var(--modal-border)',
        display: 'flex', alignItems: 'center', gap: 9,
      }}>
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>{note}</div>
        <Button variant="secondary" size="sm" onClick={onClose} style={{ marginLeft: 'auto' }}>{cancel}</Button>
        {action != null && action !== false && (
          // a disabled primary is --line on --muted (Button's own `off` look)
          <Button size="sm" variant={actionVariant} busy={actionBusy} disabled={actionDisabled} onClick={onAction}>{action}</Button>
        )}
      </div>
    </ModalPanel>
  )
}
