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
export function Spinner({ size = 9, color, style }) {
  return (
    <span className="v2-spin" aria-hidden="true" style={{
      flex: '0 0 auto', display: 'inline-block', width: size, height: size,
      border: `1.5px solid ${color || 'var(--spinner-ink)'}`, borderTopColor: 'transparent',
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
export function Button({
  variant = 'primary', size = 'md', disabled, busy, onClick, title, ariaLabel,
  children, style, className,
}) {
  const s = BTN_SIZE[size] || BTN_SIZE.md
  const look = BTN_LOOK[variant] || BTN_LOOK.primary
  const off = !!(disabled || busy)
  return (
    <div
      {...act(onClick, off)} title={title} aria-label={ariaLabel} aria-disabled={off || undefined}
      className={cx('v2-ctl', !off && look.hover, className)}
      style={{
        flex: '0 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        borderRadius: 'var(--radius-control)', fontFamily: 'var(--font-body)', fontWeight: 500,
        whiteSpace: 'nowrap', cursor: off ? 'default' : 'pointer',
        opacity: busy && !disabled ? 0.6 : 1,
        ...s, ...(off ? look.off : look.rest), ...style,
      }}>
      {busy && <Spinner size={12} color="currentColor" />}
      {children}
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
export function Pill({ on, size = 'md', disabled, onClick, title, ariaLabel, children, style, className }) {
  const s = PILL_SIZE[size] || PILL_SIZE.md
  return (
    <div
      {...act(onClick, disabled, 'button')} title={title} aria-label={ariaLabel}
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
export function IconButton({ size = 26, on, disabled, onClick, title, ariaLabel, children, style, className }) {
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
// canonical field: h29 · 1px --input-border · r6 · 12.5 · bg --input-bg.
// Focus = accent border, no ring (theme.css `input:focus-visible`).
const FIELD = {
  width: '100%', minWidth: 0, border: '1px solid var(--input-border)',
  borderRadius: 'var(--radius-field)', background: 'var(--input-bg)', color: 'var(--input-ink)',
  fontFamily: 'var(--font-body)', fontSize: 'var(--t-12-5)', outline: 'none',
}
export function Input({ value, onChange, placeholder, type = 'text', mono, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  return (
    <input
      type={type} value={value ?? ''} placeholder={placeholder} disabled={disabled} readOnly={readOnly}
      aria-label={ariaLabel} title={title} className={className}
      onChange={onChange ? (e) => onChange(e.target.value, e) : undefined}
      style={{ ...FIELD, height: 29, padding: '0 9px', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', opacity: disabled ? 0.6 : 1, ...style }}
      {...rest} />
  )
}
export function Textarea({ value, onChange, placeholder, rows = 3, mono, disabled, readOnly, ariaLabel, title, style, className, ...rest }) {
  return (
    <textarea
      value={value ?? ''} placeholder={placeholder} rows={rows} disabled={disabled} readOnly={readOnly}
      aria-label={ariaLabel} title={title} className={className}
      onChange={onChange ? (e) => onChange(e.target.value, e) : undefined}
      style={{
        ...FIELD, padding: '7px 9px', minHeight: rows * 20, lineHeight: '19px', resize: 'vertical',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', opacity: disabled ? 0.6 : 1, ...style,
      }}
      {...rest} />
  )
}

// ── SearchInput ─────────────────────────────────────────────────────────────
// boxed (Companies toolbar): h30, r99, 1px --input-border on --search-bg, ⌕ inset.
// underline (Cover Letters header): h36, no box, 1px --input-underline beneath.
// Both take the accent on focus from theme.css — no ring either way.
export function SearchInput({ value, onChange, placeholder = 'Search…', variant = 'boxed', width, ariaLabel, style, className }) {
  const under = variant === 'underline'
  const field = under
    ? {
      width: '100%', height: 36, padding: '0 13px', border: 'none',
      borderBottom: '1px solid var(--input-underline)', background: 'transparent',
      color: 'var(--input-ink)', fontFamily: 'var(--font-body)', fontSize: 'var(--t-13)', outline: 'none',
    }
    : {
      width: '100%', height: 30, padding: '0 12px 0 29px', border: '1px solid var(--input-border)',
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
                  color: sel ? 'var(--pill-on-ink)' : 'var(--menu-item-ink)',
                  background: sel ? 'var(--pill-on-bg)' : 'transparent',
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
export function Row({ selected, divider, onClick, title, ariaLabel, children, style, className }) {
  return (
    <div {...act(onClick, false, 'button')} title={title} aria-label={ariaLabel} aria-current={selected ? "true" : undefined}
      className={cx('v2-row', className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, height: 46,
        borderRadius: 'var(--radius-row)',
        background: selected ? 'var(--row-selected)' : 'transparent',
        borderLeft: selected ? '3px solid var(--row-selected-mark)' : undefined,
        borderBottom: divider ? '1px solid var(--row-line)' : undefined,
        padding: selected ? '0 10px 0 7px' : '0 10px',
        cursor: onClick ? 'pointer' : 'default', ...style,
      }}>{children}</div>
  )
}

// ── Card / Band ─────────────────────────────────────────────────────────────
// Card canonical: surface · 1px --card-border · r9 · pad 10 14.
//   `interactive` adds the accent-border + --card-bg-hover wash (v2-act).
// Band is the dashed sibling (same box, dashed --band-border).
export function Card({ interactive, onClick, title, ariaLabel, children, style, className }) {
  const live = interactive || !!onClick
  return (
    <div {...act(onClick, false)} title={title} aria-label={ariaLabel}
      className={cx(live && 'v2-act', className)}
      style={{
        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
        borderRadius: 'var(--radius-card)', padding: '10px 14px',
        cursor: live ? 'pointer' : 'default', ...style,
      }}>{children}</div>
  )
}
export function Band({ interactive = true, onClick, title, ariaLabel, children, style, className }) {
  const live = interactive || !!onClick
  return (
    <div {...act(onClick, false)} title={title} aria-label={ariaLabel}
      className={cx(live && 'v2-act', className)}
      style={{
        border: '1px dashed var(--band-border)', borderRadius: 'var(--radius-card)',
        padding: '10px 14px', cursor: live ? 'pointer' : 'default', ...style,
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
export function Menu({ children, ariaLabel, style, className }) {
  return (
    <div role="menu" aria-label={ariaLabel} className={className} style={{
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
export function MenuItem({ icon, hint, danger, divider, disabled, onClick, title, ariaLabel, children, style, className }) {
  const sep = divider === undefined ? !!danger : divider
  return (
    <div {...act(onClick, disabled, 'menuitem')} title={title} aria-label={ariaLabel} aria-disabled={disabled || undefined}
      className={cx(!disabled && (danger ? 'v2-hover-bad' : 'v2-menuitem'), className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 9, padding: '7px 11px',
        borderRadius: 'var(--radius-field)', fontSize: 'var(--t-12-5)',
        color: danger ? 'var(--menu-item-danger-ink)' : 'var(--menu-item-ink)',
        borderTop: sep ? '1px solid var(--menu-item-sep)' : undefined,
        opacity: disabled ? 0.5 : 1, cursor: disabled ? 'default' : 'pointer', ...style,
      }}>
      {icon && <span aria-hidden="true" style={{ flex: '0 0 auto' }}>{icon}</span>}
      <span style={{ minWidth: 0, flex: 1 }}>{children}</span>
      {hint && <Helper size="xs" style={{ flex: '0 0 auto' }}>{hint}</Helper>}
    </div>
  )
}

// ── SectionHead ─────────────────────────────────────────────────────────────
// canonical: muted · 12.5 · hover v2-hover-accent. Collapsible: the caret and
// aria-expanded are driven by `open`; `boxed` is the padded/rounded variant.
export function SectionHead({ open = true, onToggle, count, boxed, title, ariaLabel, children, style, className }) {
  return (
    <div {...act(onToggle, false)} title={title} aria-label={ariaLabel} aria-expanded={onToggle ? !!open : undefined}
      className={cx(onToggle && 'v2-hover-accent', className)}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 'var(--t-12-5)', lineHeight: '18px', color: 'var(--section-head-ink)',
        borderRadius: boxed ? 'var(--radius-field)' : undefined, padding: boxed ? '2px 4px' : undefined,
        cursor: onToggle ? 'pointer' : 'default', ...style,
      }}>
      {onToggle && <span aria-hidden="true" style={{ flex: '0 0 auto' }}>{open ? '▾' : '▸'}</span>}
      <span style={{ minWidth: 0 }}>{children}</span>
      {count !== undefined && count !== null && <Helper size="xs" style={{ flex: '0 0 auto' }}>{count}</Helper>}
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
const TAG_TONE = {
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
export function Link({ href, target, onClick, title, ariaLabel, children, style, className }) {
  const st = {
    color: 'var(--link-ink)', fontSize: 'var(--t-11-5)', lineHeight: '17px', fontWeight: 500,
    cursor: 'pointer', ...style,
  }
  const cls = cx('v2-hover-accent-text', className)
  if (href) {
    return <a href={href} target={target} rel={target === '_blank' ? 'noreferrer' : undefined} title={title} aria-label={ariaLabel} className={cls} style={st}>{children}</a>
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

// ── ModalPanel / Drawer ─────────────────────────────────────────────────────
// ModalPanel canonical: surface · 1px --modal-border · r12 · --modal-shadow,
// on a --scrim-bg scrim. Escape closes (useEscape, RES-15) and the panel is
// pulled back onto the pixel grid (useSnapTop, RES-32).
export function ModalPanel({ width = 480, onClose, labelledBy, children, style, className, scrimStyle }) {
  useEscape(onClose)
  const panel = useRef(null)
  useSnapTop(panel)
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'var(--scrim-bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 70, ...scrimStyle,
    }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        onClick={(e) => e.stopPropagation()} className={className}
        style={{
          width, background: 'var(--modal-bg)', border: '1px solid var(--modal-border)',
          borderRadius: 'var(--radius-modal)', boxShadow: 'var(--modal-shadow)',
          display: 'flex', flexDirection: 'column', minHeight: 0, ...style,
        }}>{children}</div>
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
// (15 22 12); `soft` swaps the rule for --head-line-soft.
const HEAD_PAD = { modal: '16px 22px 13px', screen: '22px 30px 16px', compact: '15px 22px 12px' }
export function HeaderRow({ variant = 'modal', soft, align = 'flex-start', children, style, className }) {
  return (
    <div className={className} style={{
      flex: '0 0 auto', padding: HEAD_PAD[variant] || HEAD_PAD.modal,
      borderBottom: `1px solid ${soft ? 'var(--head-line-soft)' : 'var(--head-line)'}`,
      display: 'flex', alignItems: align, gap: 12, ...style,
    }}>{children}</div>
  )
}

// ── Label / Helper / Heading / PageTitle ────────────────────────────────────
// Label canonical: muted · 10 · uppercase · .13em. `size="lg"` is the 11px form.
const LABEL_SIZE = {
  md: { fontSize: 'var(--t-10)', lineHeight: '15px' },
  lg: { fontSize: 'var(--t-11)', lineHeight: '16px' },
}
export function Label({ size = 'md', htmlFor, children, style, className }) {
  const st = {
    letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--label-ink)',
    ...(LABEL_SIZE[size] || LABEL_SIZE.md), ...style,
  }
  if (htmlFor) return <label htmlFor={htmlFor} className={className} style={st}>{children}</label>
  return <span className={className} style={st}>{children}</span>
}
// Helper canonical: muted · 11.5/16px. `size="xs"` is the 10.5/16 form.
const HELPER_SIZE = {
  md: { fontSize: 'var(--t-11-5)', lineHeight: '16px' },
  xs: { fontSize: 'var(--t-10-5)', lineHeight: '16px' },
}
export function Helper({ size = 'md', mono, title, children, style, className }) {
  return (
    <span title={title} className={className} style={{
      color: 'var(--helper-ink)', fontFamily: mono ? 'var(--font-mono)' : undefined,
      ...(HELPER_SIZE[size] || HELPER_SIZE.md), ...style,
    }}>{children}</span>
  )
}
// Heading canonical: serif 18 · -.02em. 19 and 22 are the two larger steps.
const HEADING_SIZE = {
  18: { fontSize: 'var(--t-18)', lineHeight: '27px' },
  19: { fontSize: 'var(--t-19)', lineHeight: '26px' },
  22: { fontSize: 'var(--t-22)', lineHeight: '30px' },
}
export function Heading({ size = 18, id, title, children, style, className }) {
  return (
    <span id={id} title={title} className={className} style={{
      fontFamily: 'var(--font-display)', letterSpacing: '-.02em', color: 'var(--heading-ink)',
      ...(HEADING_SIZE[size] || HEADING_SIZE[18]), ...style,
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
