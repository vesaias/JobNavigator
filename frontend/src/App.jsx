import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Outlet, Navigate } from 'react-router-dom'
import { Briefcase, LayoutDashboard, Building2, Search, Settings, BarChart3, FileCode2, FileText, User, Mail, ChevronLeft, ChevronRight } from 'lucide-react'
import JobFeed from './components/JobFeed'
import ApplicationBoard from './components/ApplicationBoard'
import CompanyManager from './components/CompanyManager'
import SearchManager from './components/SearchManager'
import SettingsPage from './components/Settings'
import Stats from './components/Stats'
import ResumeBuilder from './components/ResumeBuilder'
import CoverLetterBuilder from './components/CoverLetterBuilder'
import Persona from './components/Persona'
import LoginModal from './components/LoginModal'
import WelcomeModal from './components/WelcomeModal'
import WhatsNewBanner from './components/WhatsNewBanner'
import HealthBanner from './components/HealthBanner'
import V2App from './v2/V2App'
import V2JobFeed from './v2/JobFeed'
import V2Resumes from './v2/Resumes'
import V2ResumeEditor from './v2/ResumeEditor'
import V2Companies from './v2/Companies'
import V2Searches from './v2/Searches'
import V2Applications from './v2/Applications'
import V2CoverLetters from './v2/CoverLetters'
import V2CoverLetterEditor from './v2/CoverLetterEditor'
import V2Settings from './v2/Settings'
import V2Persona from './v2/Persona'
import V2Stats from './v2/Stats'
import axios from 'axios'

const NAV_ITEMS = [
  { to: '/', icon: Briefcase, label: 'Jobs' },
  { to: '/applications', icon: LayoutDashboard, label: 'Applications' },
  { to: '/companies', icon: Building2, label: 'Companies' },
  { to: '/searches', icon: Search, label: 'Searches' },
  { to: '/resumes', icon: FileText, label: 'Resumes' },
  { to: '/cover-letters', icon: Mail, label: 'Cover Letters' },
  { to: '/persona', icon: User, label: 'Persona' },
  { to: '/settings', icon: Settings, label: 'Settings' },
  { to: '/stats', icon: BarChart3, label: 'Stats' },
  { to: '/docs', icon: FileCode2, label: 'API Docs', external: true },
]

// Classic shell (sidebar + main). Rendered as a layout route so its child
// routes fill the <Outlet/>. The v2 redesign lives under /v2 with its own shell.
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
              <NavLink key={to} to={to} end={to === '/'}
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
        <NavLink to="/v2/feed" className="flex items-center h-10 whitespace-nowrap text-emerald-300 hover:bg-slate-800 hover:text-emerald-200 text-xs border-t border-slate-700">
          <span className="w-16 flex-shrink-0 flex items-center justify-center text-base">&#129517;</span>
          <span className={`transition-opacity duration-150 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>Try v2 (beta)</span>
        </NavLink>
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
  const [darkMode, setDarkMode] = useState(() => {
    try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false }
  })
  const [showLogin, setShowLogin] = useState(false)
  const [showWelcome, setShowWelcome] = useState(() => {
    try { return sessionStorage.getItem('jn:welcome') === '1' } catch { return false }
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    localStorage.setItem('jobnavigator_dark_mode', String(darkMode))
  }, [darkMode])

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
      <Routes>
        {/* v2 redesign — separate shell, additive, swap to / when complete */}
        <Route path="/v2" element={<V2App />}>
          <Route index element={<Navigate to="feed" replace />} />
          <Route path="feed" element={<V2JobFeed />} />
          <Route path="resumes" element={<V2Resumes />} />
          <Route path="resumes/:id" element={<V2ResumeEditor />} />
          <Route path="companies" element={<V2Companies />} />
          <Route path="searches" element={<V2Searches />} />
          <Route path="applications" element={<V2Applications />} />
          <Route path="cover-letters" element={<V2CoverLetters />} />
          <Route path="cover-letters/:id" element={<V2CoverLetterEditor />} />
          <Route path="settings" element={<V2Settings />} />
          <Route path="persona" element={<V2Persona />} />
          <Route path="stats" element={<V2Stats />} />
        </Route>

        {/* classic shell */}
        <Route element={<ClassicShell darkMode={darkMode} setDarkMode={setDarkMode} />}>
          <Route path="/" element={<JobFeed />} />
          <Route path="/applications" element={<ApplicationBoard />} />
          <Route path="/companies" element={<CompanyManager />} />
          <Route path="/searches" element={<SearchManager />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/resumes" element={<ResumeBuilder />} />
          <Route path="/cover-letters" element={<CoverLetterBuilder />} />
          <Route path="/persona" element={<Persona />} />
          <Route path="/stats" element={<Stats />} />
        </Route>
      </Routes>

      {showLogin && <LoginModal onSuccess={handleLoginSuccess} />}
      {showWelcome && !showLogin && (
        <WelcomeModal onClose={() => {
          try { sessionStorage.removeItem('jn:welcome') } catch {}
          setShowWelcome(false)
        }} />
      )}
    </BrowserRouter>
  )
}

export default App
