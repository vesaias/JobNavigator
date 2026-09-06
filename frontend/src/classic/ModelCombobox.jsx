import React, { useState, useEffect, useMemo, useRef } from 'react'

// Google-style autocomplete: a text input with a styled, filtered, scrollable
// dropdown (replaces the native <datalist>, which browsers render as an
// unstyled full-height OS list). Free text is allowed — value is just a string.
export default function ModelCombobox({
  models = [], value, onChange, onEnter, onFocus, loading = false,
  placeholder = 'Search…', maxItems = 60,
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const wrapRef = useRef(null)
  const listRef = useRef(null)

  const q = (value || '').trim().toLowerCase()
  const filtered = useMemo(() => {
    if (!models.length) return []
    const list = q
      ? models.filter(m => m.id.toLowerCase().includes(q) || (m.name || '').toLowerCase().includes(q))
      : models
    return list.slice(0, maxItems)
  }, [models, q, maxItems])

  useEffect(() => { setActive(0) }, [q])

  useEffect(() => {
    const onDocDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
  }, [])

  // keep the highlighted row in view
  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.children[active]
    if (el) el.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const pick = (m) => { onChange(m.id); setOpen(false) }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      if (!open) { setOpen(true); return }
      e.preventDefault(); setActive(a => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault(); setActive(a => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      if (open && filtered[active]) { e.preventDefault(); pick(filtered[active]) }
      else if (onEnter) onEnter()
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const showDropdown = open && (loading || filtered.length > 0 || q.length > 0)

  return (
    <div className="relative flex-1" ref={wrapRef}>
      <input
        type="text"
        value={value}
        onChange={e => { onChange(e.target.value); setOpen(true) }}
        onFocus={() => { setOpen(true); onFocus && onFocus() }}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        className="border rounded px-2 py-1 text-xs w-full dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
      />
      {showDropdown && (
        <div
          ref={listRef}
          className="absolute z-30 left-0 right-0 mt-1 max-h-64 overflow-y-auto rounded-md border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-xl"
        >
          {loading && <div className="px-3 py-2 text-xs text-gray-400">Loading models…</div>}
          {!loading && filtered.map((m, i) => (
            <button
              key={m.id}
              type="button"
              onMouseEnter={() => setActive(i)}
              onMouseDown={e => e.preventDefault()}  /* keep input focus */
              onClick={() => pick(m)}
              className={`w-full text-left px-3 py-1.5 border-b border-gray-100 dark:border-gray-700/50 last:border-0 ${
                i === active ? 'bg-blue-50 dark:bg-gray-700' : ''
              }`}
            >
              <div className="text-xs font-medium text-gray-800 dark:text-gray-100 truncate">{m.id}</div>
              {m.name && m.name !== m.id && (
                <div className="text-[10px] text-gray-400 dark:text-gray-500 truncate">{m.name}</div>
              )}
            </button>
          ))}
          {!loading && filtered.length === 0 && (
            <div className="px-3 py-2 text-xs text-gray-400">No matches — press Add to use “{value}” anyway.</div>
          )}
        </div>
      )}
    </div>
  )
}
