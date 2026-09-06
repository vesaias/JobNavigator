import React, { useState, useEffect, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Outlet, Navigate, useLocation } from 'react-router-dom'
import { Briefcase, LayoutDashboard, Building2, Search, Settings as SettingsIcon, BarChart3, FileCode2, FileText, User, Mail, ChevronLeft, ChevronRight } from 'lucide-react'
import ClassicJobFeed from './classic/JobFeed'
import ApplicationBoard from './classic/ApplicationBoard'
import CompanyManager from './classic/CompanyManager'
import SearchManager from './classic/SearchManager'
import ClassicSettings from './classic/Settings'
import ClassicStats from './classic/Stats'
import ResumeBuilder from './classic/ResumeBuilder'
import CoverLetterBuilder from './classic/CoverLetterBuilder'
import ClassicPersona from './classic/Persona'
import WhatsNewBanner from './classic/WhatsNewBanner'
import HealthBanner from './classic/HealthBanner'
import LoginModal from './LoginModal'
import WelcomeModal from './WelcomeModal'
import NewUiModal from './NewUiModal'
import Shell from './Shell'
import JobFeed from './screens/JobFeed'
import Resumes from './screens/Resumes'
import ResumeEditor from './screens/ResumeEditor'
import Companies from './screens/Companies'
import Searches from './screens/Searches'
import Applications from './screens/Applications'
import CoverLetters from './screens/CoverLetters'
import CoverLetterEditor from './screens/CoverLetterEditor'
import Settings from './screens/Settings'
import Persona from './screens/Persona'
import Stats from './screens/Stats'
import axios from 'axios'
import { useTheme } from './theme'
import { TitleSync } from './useTitle'

// design-base/ (lab pages) is git-ignored and may not exist on a clone.
// import.meta.glob yields an empty map when it matches nothing, so an absent folder costs the two routes rather than breaking the build.
const LAB_PAGES = import.meta.glob('./design-base/*.jsx')
const labRoute = (name, path) => {
  const load = LAB_PAGES[`./design-base/${name}.jsx`]
  if (!load) return null   // folder (or file) absent — no route, no error
  const Page = lazy(load)
  return <Route path={path} element={<Suspense fallback={null}><Page /></Suspense>} />
}

// Set once the onboarding overlay has been dismissed; its absence is what makes
// a browser profile a "first visit" (R4-T0-02).
const WELCOMED_KEY = 'jobnavigator_welcomed'
// Two keys an older build wrote for the same fact (and the ones the Playwright
// harness seeds). Either one means the tour has already been seen, so neither an
// upgrade nor a test run replays it.
const LEGACY_WELCOMED = ['jobnavigator_v2_welcome_seen', 'jobnavigator_welcome_seen']
const alreadyWelcomed = () => {
  try {
    if (localStorage.getItem(WELCOMED_KEY) === '1') return true
    return LEGACY_WELCOMED.some((k) => localStorage.getItem(k) === 'true')
  } catch { return true }   // storage blocked: never strand someone behind a modal that can't record its own dismissal
}

// The upgrade overlay (NewUiModal). Versioned rather than boolean, so the
// next release can raise its own by bumping the value; anything else — an older
// mark, no mark — means this release has not been announced to this profile yet.
const NEWUI_KEY = 'jobnavigator_newui_seen'
const NEWUI_VERSION = '2.0.0'
// Keys only an EXISTING install can have written. A profile carrying any of them
// (or the welcome mark itself) used JobNavigator before the redesign, which is
// exactly the audience for "here is what moved" — a genuinely fresh profile has
// none of them and gets the first-run tour instead.
const RETURNING_KEYS = ['jobnavigator_api_key', 'jobnavigator_dark_mode', 'jobnavigator_v2_rail']
const isReturningUser = () => {
  try {
    if (alreadyWelcomed()) return true
    return RETURNING_KEYS.some((k) => localStorage.getItem(k) !== null)
  } catch { return false }
}
// Same guard as the tour: storage blocked → no overlay, since the dismissal
// could not be recorded and it would come back on every load.
const newUiPending = () => {
  try { return isReturningUser() && localStorage.getItem(NEWUI_KEY) !== NEWUI_VERSION } catch { return false }
}

// The v1 screens now live under /classic; the root belongs to the redesign.
const NAV_ITEMS = [
  { to: '/classic', icon: Briefcase, label: 'Jobs' },
  { to: '/classic/applications', icon: LayoutDashboard, label: 'Applications' },
  { to: '/classic/companies', icon: Building2, label: 'Companies' },
  { to: '/classic/searches', icon: Search, label: 'Searches' },
  { to: '/classic/resumes', icon: FileText, label: 'Resumes' },
  { to: '/classic/cover-letters', icon: Mail, label: 'Cover Letters' },
  { to: '/classic/persona', icon: User, label: 'Persona' },
  { to: '/classic/settings', icon: SettingsIcon, label: 'Settings' },
  { to: '/classic/stats', icon: BarChart3, label: 'Stats' },
  { to: '/docs', icon: FileCode2, label: 'API Docs', external: true },
]

// `/v2/feed?job=7#x` → `/feed?job=7#x`; bare `/v2` → `/`. Search and hash ride
// along because the query is what the old links actually carried.
function DropV2Prefix() {
  const { pathname, search, hash } = useLocation()
  const rest = pathname.replace(/^\/v2(?=\/|$)/, '')
  return <Navigate to={(rest || '/') + search + hash} replace />
}

// The upgrade overlay belongs to the shell it is ADVERTISING. Under /classic the
// announcement is already on screen as WhatsNewBanner, and raising the modal
// there would be the same release sold twice — worse, its dismissal would spend
// the one showing this profile gets on the interface it is pointing away from.
// So the classic shell renders nothing and marks nothing; the modal is still
// owed, and appears the moment the user is actually in the new UI.
//
// It is a component rather than a check inside App() because `useLocation` needs
// a Router above it and App is the component that renders the BrowserRouter —
// the same reason WelcomeModal reads the location from inside itself.
function NewUiGate({ onClose }) {
  if (useLocation().pathname.startsWith('/classic')) return null
  return <NewUiModal onClose={onClose} />
}

// Rendered as a layout route so its child routes fill the <Outlet/>.
function ClassicShell({ darkMode, setDarkMode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} bg-slate-900 text-white flex flex-col transition-all duration-200 overflow-hidden`}>
        <div className="flex items-center h-14 border-b border-slate-700 whitespace-nowrap">
          <span className="w-16 flex-shrink-0 flex items-center justify-center text-xl">&#128188;</span>
          <span className={`font-bold text-lg transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>JobNavigator</span>
        </div>
        <nav className="flex-1 py-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label, external }) => {
            const inner = (
              <>
                <span className="w-16 flex-shrink-0 flex items-center justify-center"><Icon size={18} /></span>
                <span className={`transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>{label}</span>
              </>
            )
            return external ? (
              <a key={to} href={to} target="_blank" rel="noopener noreferrer"
                className="flex items-center h-10 whitespace-nowrap text-sm transition-colors text-slate-300 hover:bg-slate-800 hover:text-white">
                {inner}
              </a>
            ) : (
              <NavLink key={to} to={to} end={to === '/classic'}
                className={({ isActive }) =>
                  `flex items-center h-10 whitespace-nowrap text-sm transition-colors ${
                    isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`
                }>
                {inner}
              </NavLink>
            )
          })}
        </nav>
        {/* Plain anchor, not a NavLink: leaving the classic shell for the current
            interface is a whole-app move, so let the browser do it. */}
        <a href="/" className="flex items-center h-10 whitespace-nowrap text-emerald-300 hover:bg-slate-800 hover:text-emerald-200 text-xs border-t border-slate-700">
          <span className="w-16 flex-shrink-0 flex items-center justify-center text-base">&#129517;</span>
          <span className={`transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>New UI &#8599;</span>
        </a>
        <button onClick={() => setDarkMode(!darkMode)} className="flex items-center h-10 whitespace-nowrap text-slate-400 hover:text-white text-xs">
          <span className="w-16 flex-shrink-0 flex items-center justify-center text-base">{darkMode ? '☀️' : '🌙'}</span>
          <span className={`transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="flex items-center h-10 whitespace-nowrap text-slate-400 hover:text-white text-xs border-t border-slate-700">
          <span className="w-16 flex-shrink-0 flex items-center justify-center">{sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}</span>
          <span className={`transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Collapse</span>
        </button>
      </aside>

      <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
        <HealthBanner />
        <WhatsNewBanner />
        <Outlet />
      </main>
    </div>
  )
}

function App() {
  // src/theme.js owns light|dark|system and stamps html.dark itself, so
  // flipping the theme from the current rail moves this shell too, with no reload.
  const { resolved, setMode } = useTheme()
  const darkMode = resolved === 'dark'
  const setDarkMode = (v) => setMode(v ? 'dark' : 'light')
  const [showLogin, setShowLogin] = useState(false)
  // Two ways in, one modal. LoginModal writes the session flag on a successful
  // sign-in (the key-set install), but a keyless first run never sees that
  // modal — so a *first visit* with no `jobnavigator_welcomed` mark shows the
  // onboarding too, which is the install it was written for (R4-T0-02).
  const [showWelcome, setShowWelcome] = useState(() => {
    try { if (sessionStorage.getItem('jn:welcome') === '1') return true } catch { /* ignore */ }
    return !alreadyWelcomed()
  })
  // At most one of the two overlays ever shows. The first-run tour wins: a
  // profile that is BOTH new and carrying a legacy key (the harness seeds an API
  // key into an otherwise empty context) is being onboarded, not upgraded — so
  // this stays mounted-but-unrendered and, crucially, unmarked, which is what
  // makes it appear on the visit after the tour was dismissed.
  const [showNewUi, setShowNewUi] = useState(newUiPending)

  // Handle ?cv= query param tracer links — redirect to /cv/{token} on backend
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const cvToken = params.get('cv')
    if (cvToken) {
      window.location.href = '/cv/' + encodeURIComponent(cvToken)
    }
  }, [])

  // On startup, sync localStorage API key to backend session cookie.
  useEffect(() => {
    const key = localStorage.getItem('jobnavigator_api_key') || ''
    axios.post('/api/auth/set-session', { api_key: key }, { withCredentials: true }).catch((err) => {
      if (err.response?.status === 401) setShowLogin(true)
    })
  }, [])

  // Global 401 handler — show login modal when any API call is rejected
  useEffect(() => {
    const handler = () => setShowLogin(true)
    window.addEventListener('jn:unauthorized', handler)
    return () => window.removeEventListener('jn:unauthorized', handler)
  }, [])

  const handleLoginSuccess = () => {
    setShowLogin(false)
    window.location.reload()
  }

  return (
    <BrowserRouter>
      <TitleSync />
      <Routes>
        {/* the app */}
        <Route path="/" element={<Shell />}>
          <Route index element={<Navigate to="feed" replace />} />
          <Route path="feed" element={<JobFeed />} />
          <Route path="resumes" element={<Resumes />} />
          <Route path="resumes/:id" element={<ResumeEditor />} />
          <Route path="companies" element={<Companies />} />
          <Route path="searches" element={<Searches />} />
          <Route path="applications" element={<Applications />} />
          <Route path="cover-letters" element={<CoverLetters />} />
          <Route path="cover-letters/:id" element={<CoverLetterEditor />} />
          <Route path="settings" element={<Settings />} />
          <Route path="persona" element={<Persona />} />
          <Route path="stats" element={<Stats />} />
        </Route>
        {/* labRoute returns null when design-base/ is absent; React skips a null child. */}
        {labRoute('ToastLab', '/toasts')}
        {labRoute('UiGallery', '/ui')}

        {/* the previous interface, kept whole under /classic */}
        <Route path="/classic" element={<ClassicShell darkMode={darkMode} setDarkMode={setDarkMode} />}>
          <Route index element={<ClassicJobFeed />} />
          <Route path="applications" element={<ApplicationBoard />} />
          <Route path="companies" element={<CompanyManager />} />
          <Route path="searches" element={<SearchManager />} />
          <Route path="settings" element={<ClassicSettings />} />
          <Route path="resumes" element={<ResumeBuilder />} />
          <Route path="cover-letters" element={<CoverLetterBuilder />} />
          <Route path="persona" element={<ClassicPersona />} />
          <Route path="stats" element={<ClassicStats />} />
        </Route>

        {/* /v2 was the staging prefix while the redesign was built beside v1;
            every screen it named now lives one level up, so old links (and
            bookmarks, and the harness) land on their twin, query and hash intact. */}
        <Route path="/v2" element={<DropV2Prefix />} />
        <Route path="/v2/*" element={<DropV2Prefix />} />
        {/* Every v1 root path (/applications, /resumes, …) is now the v2 screen of
            the same name — same feature, new UI — and v1 had no path without a
            twin, so nothing else needs a redirect. Anything left over is a typo
            or a dead bookmark: send it to the feed, not a blank shell. */}
        <Route path="*" element={<Navigate to="/feed" replace />} />
      </Routes>

      {showLogin && <LoginModal onSuccess={handleLoginSuccess} />}
      {showWelcome && !showLogin && (
        <WelcomeModal onClose={() => {
          try { sessionStorage.removeItem('jn:welcome') } catch {}
          // durable, so the tour does not come back on the next visit
          try { localStorage.setItem(WELCOMED_KEY, '1') } catch {}
          setShowWelcome(false)
        }} />
      )}
      {showNewUi && !showWelcome && !showLogin && (
        <NewUiGate onClose={() => {
          try { localStorage.setItem(NEWUI_KEY, NEWUI_VERSION) } catch {}
          setShowNewUi(false)
        }} />
      )}
    </BrowserRouter>
  )
}

export default App
