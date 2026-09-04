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
//
// DS-B-01: a disabled/busy control keeps its ROLE, though. Dropping `role` along
// with the click and key handlers left a `Parsing…` button reading to a screen
// reader as loose text rather than a disabled button, and threw away the focus
// that was on it. Keep the role and the caller's `aria-disabled`/`aria-busy`, and
// take away only the interactivity: no handlers, and `tabIndex -1` so it leaves
// the tab order while staying focusable (and focused, if it already was).
const act = (fn, off, role) => (
  fn ? (off ? { role: role || 'button', tabIndex: -1 } : { onClick: fn, ...kb(fn, role) }) : {}
)

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
    // DS-B-01: `busy` is the state a screen reader needs; the prop stays an
    // explicit override for the callers that set it themselves.
    'aria-busy': ariaBusy !== undefined ? ariaBusy : (busy || undefined),
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
    // DS-S-11/DS-S-12: the wrapper carries a real `width`, not just a flex-basis.
    // A flex item's *intrinsic contribution* to its parent is measured from its
    // content, and the content here is a bare <input> whose default intrinsic
    // width is ~178px — so a parent sized to max-content (a header's action
    // group) budgeted 178px for a field that then laid out at its 300px basis
    // and shoved the sibling Button past the header's overflow:hidden edge.
    // With `width` set, the contribution equals the declared width; `0 1 auto`
    // + minWidth:0 keeps the field (never the button) as the thing that yields.
    <span className={className} style={{ position: 'relative', display: 'flex', alignItems: 'center', minWidth: 0, width: width || 226, flex: '0 1 auto', ...style }}>
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
  // DS-S-21/DS-S-32: Escape closes the listbox — and only the listbox, so a
  // Select inside a modal doesn't take the modal down with it. The key listener
  // is registered in the *capture* phase because `useEscape` (hooks.js) listens
  // on document in the bubble phase: a parent modal registers its listener when
  // it mounts, long before this popover opens, so mount order can't be relied on
  // here the way it can for two components that mount together. Capture always
  // runs first; preventDefault + stopPropagation then claim the event, the same
  // swallow the Settings model-catalog typeahead does for its own dropdown.
  // While the listbox is closed nothing is registered, so Escape falls through.
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
      <div {...act(toggle, disabled)} aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-disabled={disabled || undefined}
        style={{
          flex: 1, minWidth: 0, height: 32, padding: '0 10px',
          border: `1px solid ${open ? 'var(--input-border-focus)' : 'var(--input-border)'}`,
          // D-POST-04: the trigger is a *field*, so it takes --input-bg like Input
          // and Textarea. It shipped on --search-bg (= --surface, white) and any
          // form that pairs a Select with an Input — Searches' New/Edit grid,
          // Settings' value rows, Persona's enum fields — drew two backgrounds
          // for one row of controls. --search-bg stays what it says it is: the
          // ground of a *search* box (SearchInput boxed), which is a different
          // control with a different job.
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
// canonical: h46 · r7 · pad 0 10 · hover --row-hover · selected = --row-selected.
// D-POST-07: selection is a **background wash and nothing else**. APPS-20 added a
// 3px --row-selected-mark bar with a compensating left pad; Applications never
// had one (nor does any other row list in v2), and the pad swap shifted every
// cell in the picked row by 3px. The token went with it.
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
        borderBottom: divider ? '1px solid var(--row-line)' : undefined,
        padding: '0 10px',
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
// D-POST-01: `v2-menu` is not decoration — theme.css pins `flex-shrink:0` on
// every direct child. The box is a *column* flex container, so a child's
// declared height is only a flex-basis: once the menu is taller than its
// `maxHeight` (the Feed's Company filter lists ~1300 companies), the browser
// shrinks every shrinkable child to fit, and the in-menu search field collapsed
// from its canonical 32 px to 17. Menu rows are fixed-height by definition; a
// scrolling menu scrolls, it never squashes.
export function Menu({ role = 'menu', children, ariaLabel, style, className }) {
  return (
    <div role={role} aria-label={ariaLabel} className={cx('v2-menu', className)} style={{
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

// ── Check / Radio ───────────────────────────────────────────────────────────
// The tick box and the radio disc that five screens drew by hand (the Feed's row
// selector and its "select all shown" head cell, the Feed's in-menu company
// checks, Searches' import-rules checks, the drawer/modal option lists). One
// indicator, one set of tokens: --check-border at rest, the accent trio when on.
// `label` is optional — a bare indicator (a table's select cell) passes none and
// keeps its own `ariaLabel`. `indeterminate` is the "some but not all" tick the
// select-all cell shows over a partial selection.
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
    // A non-interactive indicator (the tick that rides in a MenuItem's icon
    // gutter, where the row itself owns the click) still needs its role: act()
    // hands back an empty object without a handler, and aria-checked on a
    // role-less span is ignored. Name the role either way, add the tab stop only
    // when there is something to click.
    <span role={round ? 'radio' : 'checkbox'} {...act(fire, disabled, round ? 'radio' : 'checkbox')}
      aria-checked={indeterminate && !round ? 'mixed' : !!checked}
      aria-label={ariaLabel || (typeof label === 'string' ? label : undefined)}
      aria-disabled={disabled || undefined} title={title} className={className}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, minWidth: 0,
        fontSize: 'var(--t-12)', color: 'var(--check-label-ink)',
        opacity: disabled ? 0.5 : 1, cursor: disabled || !fire ? 'default' : 'pointer', ...style,
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
// inset). SET-14: --switch-knob-on is --surface-2 so the knob reads as a surface
// disc on the accent track in both themes; OFF keeps --knob on a neutral track.
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
        opacity: disabled ? 0.5 : 1, cursor: disabled || !fire ? 'default' : 'pointer', ...style,
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
//                *absent* dot draws nothing at all: an empty span would still eat
//                a gap and push its label off the cell's centre, which is exactly
//                what happened to the "Off" cell before this primitive existed.
//   dotColor  — a fixed disc colour (the stage stepper's per-stage hue), drawn
//                whether or not the cell is picked.
//   tone      — 'accent' (default) or 'bad' for the picked look, so the
//                stepper's Rejected cell can close in red without an inline
//                exception.
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
          border: '1px solid var(--seg-border)', borderRadius: 'var(--radius-control)',
        } : null), ...style,
      }}>
      {options.map((o, i) => {
        const on = o.value === value
        const t = SEG_TONE[o.tone] || SEG_TONE.accent
        const pick = onChange && !disabled ? () => { if (!on) onChange(o.value) } : undefined
        return (
          <div key={String(o.value)} role="radio" aria-checked={on} aria-disabled={disabled || undefined}
            title={o.hint || undefined} tabIndex={disabled ? -1 : ((on || (idx < 0 && i === 0)) ? 0 : -1)}
            className={inset || disabled ? undefined : 'v2-bd'}
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
              border: inset ? undefined : `1px solid ${on ? t.border : 'var(--seg-border)'}`,
              background: on ? t.bg : (inset ? 'transparent' : 'var(--seg-bg)'),
              color: on ? t.ink : (inset ? 'var(--seg-inset-ink)' : 'var(--seg-ink)'),
              fontFamily: 'var(--font-body)', fontSize: z.fontSize, lineHeight: 1,
              fontWeight: on && !inset ? 600 : 400, whiteSpace: 'nowrap',
              opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer',
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
// flex-centred box at lineHeight 1, with no baseline nudge, so a skin that
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
  sm: { box: 34, vb: 78, shift: 2, num: 'var(--t-14)', track: 5, letterSpacing: '-.02em', unscored: 'var(--t-7-5)' },  // vb 78: the pre-pass band ring (r 15.26 px, stroke 2.18) — fits a 34 box without clipping
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
// D-POST-16: the viewBox is a **constant**, not `2 x box`. With a per-size
// viewBox, `r=35 + stroke/2` is a *fixed 37.5px* outer radius whatever the box
// is: it fits md's 44px box (37.5 < 44) and overflowed sm's 34px one, where the
// SVG root's UA `overflow:hidden` sliced 1.75px off all four sides — the ring
// rendered as a squircle (measured on the Feed's report band: viewBox 0 0 68 68,
// r 35, stroke 5, svg 34x34). Pinning the viewBox to md's 88 makes every size a
// uniform scale of the same drawing — md is pixel-identical, sm draws a whole
// ring, and an explicit numeric `size` scales too instead of clipping.
const RING_VB = 88
export function ScoreRing({ value, size = 'md', weight, tone, label = 'No fit', busy, title, ariaLabel, children, style, className }) {
  const z = typeof size === 'number' ? { ...RING_SIZE.md, box: size } : (RING_SIZE[size] || RING_SIZE.md)
  const t = RING_TONE[tone || scoreTone(value)] || RING_TONE.neutral
  const vb = z.vb || RING_VB  // numeric sizes scale md's ring
  const stroke = weight || z.track
  const c = 2 * Math.PI * RING_R
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
            transform: `translateY(var(--ring-shift-${size === 'sm' ? 'sm' : 'md'}, ${z.shift || 0}px))`,  // optical centre per skin (font metrics differ): tokens in theme.css
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
    <div className={className} style={{
      display: 'flex', alignItems: 'center', gap: 10, maxWidth: 380, padding: '10px 13px',
      background: k.bg, border: `1px solid ${k.line}`, borderRadius: 'var(--radius-card)', color: k.ink,
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

// ── ChoiceCard / ChoiceRow / ChoiceModal ────────────────────────────────────
// The "pick one thing, then commit" modal three screens draw identically: the
// résumé editor's Tailor and Re-tailor modals and the Persona's Import. The
// shell was copied between the first two and the Persona import used a Menu +
// a picker panel + a ConfirmDialog instead; naming the shape here is what stops
// the three drifting again. The geometry below IS the Re-tailor modal's, to the
// pixel — 480 panel · modal head (16/22/13) · body 14/22 on a 460 cap · footer
// 12/22 over a --modal-border rule.
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
          // RES-17: a disabled primary is --line on --muted (Button's own `off` look)
          <Button size="sm" variant={actionVariant} busy={actionBusy} disabled={actionDisabled} onClick={onAction}>{action}</Button>
        )}
      </div>
    </ModalPanel>
  )
}
