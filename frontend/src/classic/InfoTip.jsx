import React, { useState, useEffect, useRef } from 'react'
import { Info } from 'lucide-react'

// Click-toggle (i) popover for a page-header explanation — mirrors the Job Feed's
// info button. Closes on outside click.
export default function InfoTip({ title, children, width = 'w-80' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])
  return (
    <div className="relative flex items-center" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        title={title || 'What is this?'}
        className="p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
      >
        <Info size={15} />
      </button>
      {open && (
        <div className={`absolute left-0 top-7 z-50 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-lg p-3 ${width} text-xs text-gray-600 dark:text-gray-300 leading-relaxed`}>
          {title && <div className="font-semibold text-gray-700 dark:text-gray-200 mb-1.5">{title}</div>}
          {children}
        </div>
      )}
    </div>
  )
}
