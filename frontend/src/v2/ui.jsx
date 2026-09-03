// ─────────────────────────────────────────────────────────────────────────────
// v2 primitive layer  (design pass D3)
//
// WHAT THIS IS
// One component per *role* — the kinds of element the D1 scan found repeated
// across `frontend/src/v2/*.jsx` (see `v2-testing/round-design/scan.md` and
// `D1-D2.md`). Each primitive renders the role's **canonical signature**: the
// dominant signature of that role in the scan, as approved in D1-D2 §"D2
// decision". Swapping a screen's dominant-signature site for the primitive is
// meant to produce zero visual change; every other signature in the role either
// becomes the canonical one (a drift fix, listed in that step's
// `expected-<step>.md`) or a named variant here.
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
// HOW TO ADD A VARIANT
// A variant is a *named* entry in the role's size/look map below — never an
// inline exception at a call site. Add the key, give it semantic tokens only,
// render it on `/v2/ui` (UiGallery.jsx) next to its siblings, and record the
// before → after in the step's `expected-<step>.md` so the style crawl can
// accept the diff.
//
// THE RULE
// **Never inline a colour, radius, shadow, font family or font size in a
// screen.** Those live in `theme.css` as semantic tokens (`--btn-primary-bg`,
// `--radius-card`, `--menu-shadow`, `--font-body`, `--t-12-5`, …), each of which
// points at a palette token, so a new skin is a wholesale replacement of the
// palette block and nothing else. Primitives read semantic tokens only; they
// never read a palette token (`--accent`, `--line`, …) directly. D5's
// `tools/stylelint.py` enforces this — `theme.css` and this file are the only
// two places a literal is allowed.
//
// LINE-HEIGHTS are whole pixels. Fixed-height flex controls carry `v2-ctl`
// (line-height:1) the way the rest of v2 does; a single line centred in a fixed
// box renders identically at any line-height, so that is pixel-safe.
// ─────────────────────────────────────────────────────────────────────────────
import React, { useEffect, useRef, useState } from 'react'
import './theme.css'
import { useEscape, useSnapTop } from './hooks'

// PERS-15 / STAT-22: v2 draws its controls as span/div, so none of them would be
// focusable or operable from the keyboard. Spread `kb(fn)` onto such an element.
// Same contract as the copies in ResumeSections.jsx and Settings.jsx — declared
// here rather than imported so `ui.jsx` stays a leaf of the v2 import graph.
export const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

const cx = (...v) => v.filter(Boolean).join(' ')
// `kb()` only when the control can actually act — a disabled control must not be
// a tab stop, and an inert one (a Card with no onClick) is not a button.
const act = (fn, off, role) => (fn && !off ? { onClick: fn, ...kb(fn, role) } : {})

// ── Spinner ─────────────────────────────────────────────────────────────────
// dominant: 1.5px accent · r99 · 9px (9 sites). `color` lets a button spin in
// its own ink (currentColor) without a second token.
// `weight="bold"` is the 2px band: the Feed's 28px score ring is drawn heavy on
// purpose (user decision, D1-D2 §"Decisions during D4"), and a hairline reads as
// a different control at that diameter.
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
// canonical (primary/md): accent bg · accent-ink · r99 · h36 · 13.5/500 · pad 0 18
// variants sm (h33, 13/500, pad 0 15) and xs (h28, 12.5) per D1-D2.
const BTN_SIZE = {
  md: { height: 36, fontSize: 'var(--t-13-5)', padding: '0 18px' },
  sm: { height: 33, fontSize: 'var(--t-13)', padding: '0 15px' },
  xs: { height: 28, fontSize: 'var(--t-12-5)', padding: '0 14px' },
}
const BTN_LOOK = {
  primary: {
    rest: { background: 'var(--btn-primary-bg)', color: 'var(--btn-primary-ink)' },
    off: { background: 'var(--btn-primary-disabled-bg)', color: 'var(--btn-primary-disabled-ink)' },
    hover: '',
  },
  danger: {
    rest: { background: 'var(--btn-danger-bg)', color: 'var(--btn-danger-ink)' },
    off: { background: 'var(--btn-primary-disabled-bg)', color: 'var(--btn-primary-disabled-ink)' },
    hover: '',
  },
  secondary: {
    rest: { background: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-ink)', border: '1px solid var(--btn-secondary-border)' },
    off: { background: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-disabled-ink)', border: '1px solid var(--btn-secondary-disabled-border)' },
    hover: 'v2-bdc',
  },
  ghost: {
    rest: { background: 'transparent', color: 'var(--btn-ghost-ink)' },
    off: { background: 'transparent', color: 'var(--btn-secondary-disabled-ink)' },
    hover: 'v2-hover-accent',
  },
}
// `as="button"` renders a real <button type=…> instead of the div, for the one
// case where the element *is* the semantics: a form's submit control (LoginModal),
// where Enter-in-a-field must submit the form. The UA button styles it would
// otherwise inherit (border, margin, appearance) are reset first, and it keeps
// `tabindex="0"` so theme.css's focus ring still applies — zero-pixel either way.
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
    'aria-busy': ariaBusy,
    className: cx('v2-ctl', !off && look.hover, className),
    style: {
      flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      borderRadius: 'var(--radius-control)', fontFamily: 'var(--font-body)', fontWeight: 500,
      whiteSpace: 'nowrap', cursor: off ? 'default' : 'pointer',
      opacity: busy && !disabled ? 0.6 : 1,
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
const PILL_SIZE = {
  md: { height: 31, fontSize: 'var(--t-12-5)', padding: '0 15px' },
  sm: { height: 26, fontSize: 'var(--t-11-5)', padding: '0 13px' },
}
export function Pill({
  on, size = 'md', disabled, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup, ariaBusy, children, style, className,
}) {
  const s = PILL_SIZE[size] || PILL_SIZE.md
  return (
    <div
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel}
      aria-expanded={ariaExpanded} aria-haspopup={ariaHaspopup} aria-busy={ariaBusy}
      aria-pressed={on === undefined ? undefined : !!on} aria-disabled={disabled || undefined}
      className={cx('v2-ctl', !disabled && 'v2-bd', className)}
      style={{
        flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        borderRadius: 'var(--radius-control)', fontFamily: 'var(--font-body)', whiteSpace: 'nowrap',
        background: on ? 'var(--pill-on-bg)' : 'var(--pill-bg)',
        color: on ? 'var(--pill-on-ink)' : 'var(--pill-ink)',
        border: `1px solid ${on ? 'var(--pill-on-border)' : 'var(--pill-border)'}`,
        opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer',
        ...s, ...style,
      }}>{children}</div>
  )
}

// ── IconButton ──────────────────────────────────────────────────────────────
// 26 = the bare glyph button (muted · r99 · 26×26 · 13px · hover v2-hover-accent,
//      7 sites — the dominant).
// 36 = the bordered "⋯" head button (1px edge on surface, 15px, hover v2-act,
//      accent border + accent-soft when `on`).
export function IconButton({
  size = 26, on, disabled, onClick, title, ariaLabel,
  ariaExpanded, ariaHaspopup, children, style, className,
}) {
  const lg = size === 36
  const look = lg
    ? {
      fontSize: 'var(--t-15)', color: on ? 'var(--pill-on-ink)' : 'var(--pill-ink)',
      background: on ? 'var(--pill-on-bg)' : 'var(--pill-bg)',
      border: `1px solid ${on ? 'var(--pill-on-border)' : 'var(--pill-border)'}`,
    }
    : { fontSize: 'var(--t-13)', color: 'var(--icon-btn-ink)' }
  return (
    <div
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel || title}
      aria-expanded={ariaExpanded} aria-haspopup={ariaHaspopup}
      aria-pressed={on === undefined ? undefined : !!on} aria-disabled={disabled || undefined}
      className={cx('v2-ctl', !disabled && (lg ? 'v2-act' : 'v2-hover-accent'), className)}
      style={{
        flex: '0 0 auto', width: size, height: size, borderRadius: 'var(--radius-control)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer',
        ...look, ...style,
      }}>{children}</div>
  )
}

// ── Input / Textarea ────────────────────────────────────────────────────────
// canonical field: h32 · 1px --input-border · r6 · 12.5 · bg --input-bg.
// Focus = accent border, no ring (theme.css `input:focus-visible`).
// D4b shipped h29 and D4b's reconciliation raised the mismatch it left: `Select`
// is h32, so any row that pairs a field with a dropdown (Persona's autofill grid,
// Searches' Cell grid, Settings' value rows) mixed 29 and 32. User decision in
// D1-D2 §"Decisions during D4": **32 px everywhere**. `Textarea` has no fixed
// height — its box is intrinsic to `rows` — so the 32 is expressed as its
// *single-line* basis: 19 px line + 2×5.5 px padding + 2×1 px border = 32, the
// same box a one-line `Input` draws. `minHeight` then equals that intrinsic
// height exactly (rows·19 + 13) instead of being a dead floor.
const FIELD = {
  width: '100%', minWidth: 0, border: '1px solid var(--input-border)',
  borderRadius: 'var(--radius-field)', background: 'var(--input-bg)', color: 'var(--input-ink)',
  fontFamily: 'var(--font-body)', fontSize: 'var(--t-12-5)', outline: 'none',
}
// `defaultValue` (instead of `value`) renders the field *uncontrolled* — the shape
// Applications' autosaving notes box needs, where every keystroke must not round-trip
// through React state. Zero-pixel either way.
export function Input({ value, defaultValue, onChange, placeholder, type = 'text', mono, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  const bind = defaultValue === undefined ? { value: value ?? '' } : { defaultValue }
  return (
    <input
      type={type} {...bind} placeholder={placeholder} disabled={disabled} readOnly={readOnly}
      aria-label={ariaLabel} title={title} className={className}
      onChange={onChange ? (e) => onChange(e.target.value, e) : undefined}
      style={{ ...FIELD, height: 32, padding: '0 9px', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', opacity: disabled ? 0.6 : 1, ...style }}
      {...rest} />
  )
}
export function Textarea({ value, defaultValue, onChange, placeholder, rows = 3, mono, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  const bind = defaultValue === undefined ? { value: value ?? '' } : { defaultValue }
  return (
    <textarea
      {...bind} placeholder={placeholder} rows={rows} disabled={disabled} readOnly={readOnly}
      aria-label={ariaLabel} title={title} className={className}
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
// Both take the accent on focus from theme.css — no ring either way.
// The boxed one is a *box* like Input/Select and moved 30 → 32 with them (D4b
// fix-up); the underline one is a visually different control — no box at all —
// and keeps its own 36.
export function SearchInput({ value, onChange, placeholder = 'Search…', variant = 'boxed', width, ariaLabel, style, className }) {
  const under = variant === 'underline'
  const field = under
    ? {
      width: '100%', height: 36, padding: '0 13px', border: 'none',
      borderBottom: '1px solid var(--input-underline)', background: 'transparent',
      color: 'var(--input-ink)', fontFamily: 'var(--font-body)', fontSize: 'var(--t-13)', outline: 'none',
    }
    : {
      width: '100%', height: 32, padding: '0 12px 0 29px', border: '1px solid var(--input-border)',
      borderRadius: 'var(--radius-control)', background: 'var(--search-bg)',
      color: 'var(--input-ink)', fontFamily: 'var(--font-body)', fontSize: 'var(--t-12)', outline: 'none',
    }
  return (
    <span className={className} style={{ position: 'relative', display: 'flex', alignItems: 'center', minWidth: 0, flex: width ? `0 0 ${width}` : '0 1 226px', ...style }}>
      {!under && (
        <span aria-hidden="true" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 'var(--t-12)', color: 'var(--search-glyph)', pointerEvents: 'none' }}>⌕</span>
      )}
      <input type="text" value={value ?? ''} placeholder={placeholder} aria-label={ariaLabel || placeholder}
        onChange={onChange ? (e) => onChange(e.target.value, e) : undefined} style={field} />
    </span>
  )
}

// ── Select (trigger + listbox) ──────────────────────────────────────────────
// Same semantics as the Settings dropdown it generalises: a box + caret that
// announces aria-haspopup="listbox"/aria-expanded, and a role="listbox" panel of
// role="option" rows. `options` is [[value, label], …].
export function Select({ value, options = [], onPick, width, mono, placeholder, ariaLabel, emptyText, disabled, style, className }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return undefined
    const c = () => setOpen(false)
    document.addEventListener('click', c)
    return () => document.removeEventListener('click', c)
  }, [open])
  const cur = options.find((o) => String(o[0]) === String(value ?? ''))
  const toggle = () => setOpen((v) => !v)
  return (
    <span className={className} onClick={(e) => e.stopPropagation()}
      style={{ position: 'relative', display: 'flex', flex: `0 1 ${width || '220px'}`, minWidth: 0, ...style }}>
      <div {...act(toggle, disabled)} aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-disabled={disabled || undefined}
        style={{
          flex: 1, minWidth: 0, height: 32, padding: '0 10px',
          border: `1px solid ${open ? 'var(--input-border-focus)' : 'var(--input-border)'}`,
          borderRadius: 'var(--radius-field)', background: 'var(--search-bg)',
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
        <div className="v2-scroll" role="listbox" style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40,
          minWidth: '100%', maxWidth: 420, maxHeight: 320, overflow: 'auto',
          background: 'var(--menu-bg)', border: '1px solid var(--menu-border)',
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

// ── Row ─────────────────────────────────────────────────────────────────────
// canonical: h46 · r7 · pad 0 10 · hover --row-hover · selected = --row-selected
// with a 3px --row-selected-mark bar on the left (padding compensates so the
// content does not shift when a row is picked).
// `flush` is the named variant for a **full-bleed table row** (Companies): the
// list has no side padding, so a 7px radius would round the hover fill away from
// the pane edges and leave a notch under the square sticky actions cell. Radius
// only — height, hover, selection and divider are the canonical ones.
// `...rest` carries the `data-*` hooks a screen already relies on (the Feed keys
// its scroll-into-view and its harness selectors off `data-row={i}`).
export function Row({ selected, divider, flush, onClick, title, ariaLabel, children, style, className, ...rest }) {
  return (
    <div {...rest} {...act(onClick, false, 'button')} title={title} aria-label={ariaLabel} aria-current={selected ? "true" : undefined}
      className={cx('v2-row', className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, height: 46,
        borderRadius: flush ? 0 : 'var(--radius-row)',
        background: selected ? 'var(--row-selected)' : 'transparent',
        borderLeft: selected ? '3px solid var(--row-selected-mark)' : undefined,
        borderBottom: divider ? '1px solid var(--row-line)' : undefined,
        padding: selected ? '0 10px 0 7px' : '0 10px',
        // conditional spread, never `cursor: … : undefined`: a present-but-undefined
        // key clears the property (and, where a shorthand set it, half of that
        // shorthand). An inert row leaves `cursor` unset so its text keeps the I-beam.
        ...(onClick ? { cursor: 'pointer' } : null), ...style,
      }}>{children}</div>
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
        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
        borderRadius: 'var(--radius-card)', padding: '10px 14px',
        // `cursor` is inherited: setting `default` on a *static* card pushed the plain
        // arrow down through every text node inside it, so selectable card text lost
        // its I-beam hint. Only an interactive card claims a cursor.
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
        border: '1px dashed var(--band-border)', borderRadius: 'var(--radius-card)',
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
        color: 'var(--dashadd-ink)', opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer', ...style,
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
      letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--label-ink)', ...style,
    }}>{children}</div>
  )
}
// `role` is a prop because the same box serves an action menu (role="menu") and
// an option picker (role="listbox" — Settings' typeahead, the cover-letter
// template/paper pickers). Positioning is the caller's, passed as `style`.
export function Menu({ role = 'menu', children, ariaLabel, style, className }) {
  return (
    <div role={role} aria-label={ariaLabel} className={className} style={{
      background: 'var(--menu-bg)', border: '1px solid var(--menu-border)',
      borderRadius: 'var(--radius-menu)', boxShadow: 'var(--menu-shadow)', padding: 5,
      display: 'flex', flexDirection: 'column', gap: 1, ...style,
    }}>{children}</div>
  )
}
// canonical: text-2 · r6 · 12.5 · pad 7 11 · hover v2-menuitem.
// `danger` → --menu-item-danger-ink + v2-hover-bad, and (matching all three
// danger sites in the scan) a --menu-item-sep rule above it; pass
// `divider={false}` for a danger item that is not the last of its menu.
// `selected` is the picked row of an option menu (sort, template, paper size,
// filter value): --menu-item-on-bg / -on-ink at weight 500 — the same tint the
// Select listbox paints, named once.
// `icon` sits in a fixed 16 px gutter so every label in a menu starts on one
// axis whatever glyph precedes it (the shape every icon menu in v2 already drew
// by hand). `hint` is the trailing shortcut/count; `hintMono` sets it in the
// mono face, the way keyboard hints and counts are written elsewhere.
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
      opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer', ...style,
    },
  }
  const body = (
    <>
      {icon != null && icon !== false && (
        <span aria-hidden="true" style={{
          flex: '0 0 16px', textAlign: 'center', fontSize: 'var(--t-11)',
          // a flex box, not just text-align: the gutter also holds the filter
          // menus' 14/15px checkbox, which is a block and would sit left of centre
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
// The caret glyph is ⌄ / › — the pair every screen in v2 already draws (D3's
// ▾ / ▸ had no call site outside the gallery).
// Variants:
//   `boxed` — r6 · pad 2 4: a hover target slightly larger than the label, the
//             form the Feed's report heads use.
//   `card`  — the collapsible **card header** (Persona's autofill groups, the
//             résumé sections, the cover-letter editor): gap 9, the card's own
//             radius, ink inherited from the card rather than muted. Its padding
//             is layout and is passed in `style`.
// `caret="end"` puts the glyph last, adjacent to the last child (a head that
// reads label → rule → caret); `caret="pin"` puts it last and pins it to the
// right edge (`margin-left:auto`); `caret={false}` draws none, for a head that
// supplies its own (the cover-letter editor's rotating SVG chevron).
// Children render as-is, so a head that is a row of its own — a hairline, a
// count, a status — lays itself out.
export function SectionHead({
  open = true, onToggle, count, boxed, card, caret = 'start', hover = 'v2-hover-accent',
  title, ariaLabel, children, style, className,
}) {
  const glyph = onToggle && caret ? (
    // explicit lineHeight: without one the caret box is the row's 18px line-height,
    // and in a `alignItems:'baseline'` head (ResumeSections' entry heads) a 10px
    // glyph in an 18px box sits at a font-dependent offset from the shared
    // baseline, so the head grew 36→37px under the alt skin. `1` pins the box to
    // the glyph's own 10px; with `center` the content area stays centred, so the
    // glyph does not move in either alignment.
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
export function Chip({ disabled, onClick, title, ariaLabel, children, style, className }) {
  return (
    <div {...act(onClick, disabled)} title={title} aria-label={ariaLabel} aria-disabled={disabled || undefined}
      className={cx('v2-ctl', !disabled && onClick && 'v2-chip', className)}
      style={{
        flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 6,
        height: 26, padding: '0 10px', borderRadius: 'var(--radius-control)',
        background: 'var(--chip-bg)', color: 'var(--chip-ink)', border: '1px solid var(--chip-border)',
        fontFamily: 'var(--font-body)', fontSize: 'var(--t-11-5)', whiteSpace: 'nowrap',
        opacity: disabled ? 0.5 : 1, cursor: onClick && !disabled ? 'pointer' : 'default', ...style,
      }}>{children}</div>
  )
}

// ── Tag / Dot ───────────────────────────────────────────────────────────────
// Tag canonical: r99 · 10px · pad 2 8 · .06em uppercase, tinted by tone.
// `tone="none"` sets no colour at all: the ATS / search-mode / tier badges are a
// separate hue taxonomy that theme.css paints from a `cc-*` / `sm-*` class, and
// an inline tone would beat that class. Everything else about the box is shared.
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
      padding: '2px 8px', letterSpacing: '.06em', textTransform: 'uppercase',
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
// The three row affordances every list editor carries. They were written once in
// `ResumeSections.jsx` (RemoveLink/RemoveX) and hand-copied twice more there and
// once in the cover-letter editor (the ▲▼ pair); D5 moves them here so the role
// has one definition and one hover, and re-exports the two old names from
// `ResumeSections.jsx` so existing imports are untouched.
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
// `upOff` / `downOff` dim an end of the list to 0.35 and take the hover and the
// pointer away — the cover-letter editor's contact rows need that, the résumé's
// never do, and before this both drew their own pair with different hovers.
export function MoveArrows({ onUp, onDown, upOff, downOff, style, className }) {
  const arrow = (fn, off, title, glyph) => (
    <span {...act(fn, off)} title={title} className={off ? undefined : 'v2-navlink'}
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
// on a --scrim-bg scrim. Escape closes (useEscape, RES-15) and the panel is
// pulled back onto the pixel grid (useSnapTop, RES-32).
//
// `as="form"` + `onSubmit` renders the panel as a real <form>, for the sign-in
// overlay where Enter-in-the-field must submit. `scrimProps` carries the two
// attributes the two *global* overlays put on the scrim (`className="jn-v2"` +
// `data-theme`), because they mount outside the v2 shell and have to bring the
// theme with them; `zIndex` is theirs too — they sit above everything, including
// an open modal. A panel with no `onClose` (sign-in: there is nowhere to go) also
// takes no Escape listener, rather than one that swallows the key and does
// nothing.
// `escape={false}` is for a screen that already owns Escape for its whole modal
// set and guards it (Applications and Settings both close every overlay from one
// handler that stands down while a ConfirmDialog is up). A second, unguarded
// listener here would close the modal *under* that confirm.
export function ModalPanel({
  width = 480, as, onSubmit, onClose, escape = true, labelledBy, zIndex = 70,
  children, style, className, scrimStyle, scrimProps,
}) {
  useEscape(onClose, escape && !!onClose)
  const panel = useRef(null)
  useSnapTop(panel)
  const Panel = as === 'form' ? 'form' : 'div'
  return (
    <div onClick={onClose} {...scrimProps} style={{
      position: 'fixed', inset: 0, background: 'var(--scrim-bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex, ...scrimStyle,
    }}>
      <Panel ref={panel} role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        onSubmit={onSubmit} onClick={(e) => e.stopPropagation()} className={className}
        style={{
          width, background: 'var(--modal-bg)', border: '1px solid var(--modal-border)',
          borderRadius: 'var(--radius-modal)', boxShadow: 'var(--modal-shadow)',
          display: 'flex', flexDirection: 'column', minHeight: 0, ...style,
        }}>{children}</Panel>
    </div>
  )
}
// The drawer is positioned against its *pane*, not the viewport, so its scrim is
// absolute too (COMP: the rail stays reachable while a company is open).
export function Drawer({ width = 720, onClose, labelledBy, children, style, className }) {
  useEscape(onClose)
  return (
    <>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'var(--scrim-bg)', zIndex: 29 }} />
      <div role="dialog" aria-modal="true" aria-labelledby={labelledBy} className={className}
        style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width,
          background: 'var(--drawer-bg)', borderLeft: '1px solid var(--drawer-border)',
          boxShadow: 'var(--drawer-shadow)', display: 'flex', flexDirection: 'column', zIndex: 30, ...style,
        }}>{children}</div>
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
// preview strip). It stays a *named prop* rather than an inline `padding` so the
// site still reads as a HeaderRow and D5's lint has one thing to look at.
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
export function HeaderRow({
  as, variant = 'modal', pad, bg, line, soft, strong, height, align = 'flex-start',
  id, children, style, className, ...rest
}) {
  const tone = line || (strong ? 'strong' : soft ? 'soft' : 'line')
  const El = as === 'header' ? 'header' : 'div'
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
      background: 'var(--bg)', color: 'var(--label-ink)',
      fontSize: 'var(--t-9-5)', lineHeight: '14px', letterSpacing: '.11em', textTransform: 'uppercase',
      borderBottom: `1px solid ${soft ? 'var(--head-line-soft)' : 'var(--head-line-strong)'}`,
      ...(top ? { borderTop: '1px solid var(--head-line-soft)' } : null), ...style,
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
// A recessed block: --surface-2 with a radius from the same scale everything
// else uses. `radius="none"` is the full-bleed pane form (the PDF preview
// column), where the block runs edge to edge and has nothing to round.
const SURFACE_RADIUS = {
  none: undefined, field: 'var(--radius-field)', row: 'var(--radius-row)',
  card: 'var(--radius-card)', menu: 'var(--radius-menu)',
}
export function Surface({ as, radius = 'card', pad, children, style, className, ...rest }) {
  const El = as === 'section' ? 'section' : 'div'
  return (
    <El className={className} {...rest} style={{
      background: 'var(--surface-2)', borderRadius: SURFACE_RADIUS[radius],
      ...(pad ? { padding: pad } : null), ...style,
    }}>{children}</El>
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
    letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--label-ink)',
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
// Heading canonical: serif 18 · -.02em · weight 400 (inherited). 19 and 22 are
// the two larger steps.
const HEADING_SIZE = {
  18: { fontSize: 'var(--t-18)', lineHeight: '27px' },
  19: { fontSize: 'var(--t-19)', lineHeight: '26px' },
  22: { fontSize: 'var(--t-22)', lineHeight: '30px' },
}
// `strong` is v2's **second** serif family: the card / column / drawer-section
// title, set heavier (500, or 600 where the design asks for it) and tracked
// tighter than the 400-weight display scale — -.01em up to 16, -.015em from 17.
// D4e left its sites inline because collapsing the two families is a design
// decision; D4f names the family instead of collapsing it (allowed sizes
// **15 · 15.5 · 16 · 17 · 18 · 19**, exactly the sizes already drawn).
// Its line-height is **pinned to a whole pixel per size** (D5, per the user's
// consistency rule in D1-D2 §"Heading strong line-heights"). Left unset these
// titles inherited preflight's 1.5, so 15/15.5/17/19 landed on 22.5/23.25/25.5/28.5
// and every card that holds one measured x.5 — the height Chrome rounds a 1px
// border away from. 19 takes 26 so the two 19s (400- and 500-weight) share a box.
// A card that has to hold a *different* integer height still passes its own
// line-height in `style`, with the reason at the call site: the cover-letter row
// (22) and the Feed's two-line title block (1.15) are the two that do.
const HEADING_STRONG = {
  15: { fontSize: 'var(--t-15)', lineHeight: '22px', letterSpacing: '-.01em' },
  15.5: { fontSize: 'var(--t-15-5)', lineHeight: '23px', letterSpacing: '-.01em' },
  16: { fontSize: 'var(--t-16)', lineHeight: '24px', letterSpacing: '-.01em' },
  17: { fontSize: 'var(--t-17)', lineHeight: '25px', letterSpacing: '-.015em' },
  18: { fontSize: 'var(--t-18)', lineHeight: '27px', letterSpacing: '-.015em' },
  19: { fontSize: 'var(--t-19)', lineHeight: '26px', letterSpacing: '-.015em' },
}
export function Heading({ size, strong, id, title, children, style, className }) {
  const look = strong
    ? { fontWeight: strong === 600 ? 600 : 500, ...(HEADING_STRONG[size ?? 15.5] || HEADING_STRONG[15.5]) }
    : { letterSpacing: '-.02em', ...(HEADING_SIZE[size ?? 18] || HEADING_SIZE[18]) }
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
      margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--t-30)', fontWeight: 400,
      lineHeight: 1, letterSpacing: '-.02em', color: 'var(--heading-ink)', ...style,
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
