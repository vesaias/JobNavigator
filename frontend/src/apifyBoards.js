// The boards an Apify search can pick. The backend owns the list
// (PRESETS in backend/scraper/sources/apify.py, served by GET /searches/apify-boards),
// so a new board needs no frontend change. One fetch per page load, shared by
// both UIs; a failed fetch is retried on the next mount.
import { useEffect, useState } from 'react'
import api from './api'

let cache = null
let pending = null

const load = () => {
  if (cache) return Promise.resolve(cache)
  pending = pending || api.get('/searches/apify-boards')
    .then(({ data }) => { cache = Array.isArray(data) ? data : []; return cache })
    .catch(() => { pending = null; return [] })
  return pending
}

/** [{ value, label, hint, actor }, ...] in backend order; [] until the fetch lands. */
export function useApifyBoards() {
  const [boards, setBoards] = useState(cache || [])
  useEffect(() => {
    if (!cache) load().then(setBoards)
  }, [])
  return boards
}

/** "indeed" -> "Indeed"; an unknown key comes back as is. */
export const boardLabel = (boards, key) => (boards.find((b) => b.value === key) || {}).label || key

/** Job.source of an Apify job is `apify_<board>`: "apify_indeed" -> "Indeed (Apify)", any other source -> null. */
export const apifySourceLabel = (boards, source, suffix = ' (Apify)') => {
  const s = String(source || '')
  return s.startsWith('apify_') ? `${boardLabel(boards, s.slice(6))}${suffix}` : null
}
