import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Briefcase, LayoutDashboard, Building2, Search, Settings, BarChart3, FileCode2, FileText } from 'lucide-react'
import JobFeed from './components/JobFeed'
import ApplicationBoard from './components/ApplicationBoard'
import CompanyManager from './components/CompanyManager'
import SearchManager from './components/SearchManager'
import SettingsPage from './components/Settings'
import Stats from './components/Stats'
import ResumeBuilder from './components/ResumeBuilder'
import LoginModal from './components/LoginModal'
import WelcomeModal from './components/WelcomeModal'
import axios from 'axios'

const NAV_ITEMS = [
  { to: '/', icon: Briefcase, label: 'Jobs' },
  { to: '/applications', icon: LayoutDashboard, label: 'Applications' },
  { to: '/companies', icon: Building2, label: 'Companies' },
  { to: '/searches', icon: Search, label: 'Searches' },
  { to: '/resumes', icon: FileText, label: 'Resumes' },
  { to: '/settings', icon: Settings, label: 'Settings' },
  { to: '/stats', icon: BarChart3, label: 'Stats' },
  { to: '/docs', icon: FileCode2, label: 'API Docs', external: true },
]

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
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
  // If 401, the user has an invalid or missing key → show login modal.
  useEffect(() => {
    const key = localStorage.getItem('jobnavigator_api_key') || ''
    axios.post('/api/auth/set-session',
      { api_key: key },
      { withCredentials: true }
    ).catch((err) => {
      if (err.response?.status === 401) {
        setShowLogin(true)
      }
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
    // Reload so all data-fetching components refetch with fresh auth
    window.location.reload()
  }

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
        {/* Sidebar */}
        <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} bg-slate-900 text-white flex flex-col transition-all duration-200`}>
          <div className="p-4 flex items-center gap-2 border-b border-slate-700">
            <span className="text-xl">&#128188;</span>
            {sidebarOpen && <span className="font-bold text-lg">JobNavigator</span>}
          </div>
          <nav className="flex-1 py-2">
            {NAV_ITEMS.map(({ to, icon: Icon, label, external }) => (
              external ? (
                <a
                  key={to}
                  href={to}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-4 py-2.5 text-sm transition-colors text-slate-300 hover:bg-slate-800 hover:text-white"
                >
                  <Icon size={18} />
                  {sidebarOpen && label}
                </a>
              ) : (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }`
                  }
                >
                  <Icon size={18} />
                  {sidebarOpen && label}
                </NavLink>
              )
            ))}
          </nav>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="px-4 py-2 text-slate-400 hover:text-white text-xs flex items-center gap-2"
          >
            {darkMode ? '\u2600\uFE0F' : '\uD83C\uDF19'}
            {sidebarOpen && (darkMode ? 'Light Mode' : 'Dark Mode')}
          </button>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-3 text-slate-400 hover:text-white border-t border-slate-700 text-xs"
          >
            {sidebarOpen ? 'Collapse' : '>'}
          </button>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
          <Routes>
            <Route path="/" element={<JobFeed />} />
            <Route path="/applications" element={<ApplicationBoard />} />
            <Route path="/companies" element={<CompanyManager />} />
            <Route path="/searches" element={<SearchManager />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/resumes" element={<ResumeBuilder />} />
            <Route path="/stats" element={<Stats />} />
          </Routes>
        </main>

        {showLogin && <LoginModal onSuccess={handleLoginSuccess} />}
        {showWelcome && !showLogin && (
          <WelcomeModal onClose={() => {
            try { sessionStorage.removeItem('jn:welcome') } catch {}
            setShowWelcome(false)
          }} />
        )}
      </div>
    </BrowserRouter>
  )
}

export default App
