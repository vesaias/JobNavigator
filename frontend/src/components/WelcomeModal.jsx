import React from 'react'
import { Link } from 'react-router-dom'
import { Building2, Search, Settings as SettingsIcon, FileText, X } from 'lucide-react'

const STEPS = [
  {
    icon: SettingsIcon,
    title: 'Set up AI scoring',
    desc: 'Add your LLM provider and API key (Claude, OpenAI, or Ollama).',
    to: '/settings',
    color: 'text-purple-500',
  },
  {
    icon: FileText,
    title: 'Build your resume + persona',
    desc: 'Edit a base resume and fill out your persona (contact, work auth, etc.) so jobs can be scored against your profile.',
    to: '/resumes',
    color: 'text-green-500',
  },
  {
    icon: Building2,
    title: 'Activate a company',
    desc: 'Enable one of the seeded companies or add your own to start scraping.',
    to: '/companies',
    color: 'text-blue-500',
  },
  {
    icon: Search,
    title: 'Configure a search',
    desc: 'Enable a keyword search or LinkedIn Personal to discover jobs from boards.',
    to: '/searches',
    color: 'text-orange-500',
  },
]

export default function WelcomeModal({ onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-[9998] p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-[480px] max-w-full border border-gray-200 dark:border-gray-700 relative">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="p-6 pb-2">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Welcome to JobNavigator</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Four quick steps to get your job search automated.
          </p>
        </div>

        <ol className="px-6 py-2 space-y-2">
          {STEPS.map((step, i) => {
            const Icon = step.icon
            return (
              <li key={step.to}>
                <Link
                  to={step.to}
                  onClick={onClose}
                  className="flex items-start gap-3 p-3 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-xs font-semibold text-gray-600 dark:text-gray-300">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Icon size={14} className={step.color} />
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{step.title}</span>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{step.desc}</p>
                  </div>
                </Link>
              </li>
            )
          })}
        </ol>

        <div className="px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  )
}
