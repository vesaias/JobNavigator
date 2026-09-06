import React, { useState } from 'react'
import axios from 'axios'
import { Eye, EyeOff, CheckCircle } from 'lucide-react'

export default function LoginModal({ onSuccess }) {
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [success, setSuccess] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // Use a fresh axios instance to avoid the 401 interceptor firing on this call
      const { data } = await axios.post('/api/auth/set-session',
        { api_key: apiKey },
        { withCredentials: true, headers: { 'Content-Type': 'application/json' } }
      )
      if (data?.ok) {
        localStorage.setItem('jobnavigator_api_key', apiKey)
        sessionStorage.setItem('jn:welcome', '1')
        setSuccess(true)
        setTimeout(() => onSuccess?.(), 700)
      } else {
        setError('Unexpected response from server')
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid API key')
      } else {
        setError('Login failed: ' + (err.message || 'unknown error'))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-md flex items-center justify-center z-[9999]">
      <form
        onSubmit={submit}
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-[380px] border border-gray-200 dark:border-gray-700"
      >
        {success ? (
          <div className="flex flex-col items-center py-6">
            <CheckCircle size={48} className="text-green-500 mb-3" />
            <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">Signed in</div>
            <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">Loading dashboard...</div>
          </div>
        ) : (
          <>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">Sign In</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Enter your dashboard API key. You can change or view it in Settings after signing in.
            </p>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              API Key
            </label>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoFocus
                autoComplete="current-password"
                className="w-full border rounded px-3 py-2 pr-10 text-sm dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600"
              />
              <button
                type="button"
                onClick={() => setShowKey(v => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                tabIndex={-1}
                aria-label={showKey ? 'Hide API key' : 'Show API key'}
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            {error && (
              <div className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="mt-4 w-full bg-blue-600 text-white rounded px-3 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
              If this is your first time running JobNavigator and no API key is configured,
              leave this blank and click Sign In.
            </p>
          </>
        )}
      </form>
    </div>
  )
}
