import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const APP = 'JobNavigator'

// Longest prefix wins, so /v2/resumes/:id falls back to "Résumé" until the
// editor loads and names the actual document.
const ROUTES = [
  ['/v2/feed', 'Jobs'],
  ['/v2/searches', 'Searches'],
  ['/v2/companies', 'Companies'],
  ['/v2/applications', 'Applications'],
  ['/v2/resumes', 'Résumés'],
  ['/v2/cover-letters', 'Cover Letters'],
  ['/v2/persona', 'Persona'],
  ['/v2/stats', 'Stats'],
  ['/v2/settings', 'Settings'],
  ['/v2/toasts', 'Toast lab'],
  ['/applications', 'Applications'],
  ['/companies', 'Companies'],
  ['/searches', 'Searches'],
  ['/resumes', 'Résumés'],
  ['/cover-letters', 'Cover Letters'],
  ['/persona', 'Persona'],
  ['/settings', 'Settings'],
  ['/stats', 'Stats'],
  ['/', 'Jobs'],
]

export const titleFor = (path) => {
  const hit = ROUTES.filter(([p]) => path === p || path.startsWith(p === '/' ? '/#never' : p + '/'))
    .sort((a, b) => b[0].length - a[0].length)[0]
  return hit ? hit[1] : (ROUTES.find(([p]) => p === path) || [])[1]
}

/** Name the tab after the screen. Editors call useTitle() to refine it. */
export function TitleSync() {
  const { pathname } = useLocation()
  useEffect(() => {
    const name = titleFor(pathname)
    document.title = name ? `${name} · ${APP}` : `${APP} Dashboard`
  }, [pathname])
  return null
}

/** Override the route title with the document actually on screen. */
export function useTitle(name) {
  useEffect(() => {
    if (!name) return undefined
    const prev = document.title
    document.title = `${name} · ${APP}`
    return () => { document.title = prev }
  }, [name])
}
