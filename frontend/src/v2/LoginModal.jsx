import React, { useState } from 'react'
import axios from 'axios'
import './theme.css'

// Sign-in overlay (System Overlays.dc.html · 1). The design draws the resting
// state only; the loading, error and success states are v1's and are kept —
// signing in is the one place the app can strand you with no way forward.
export default function LoginModal({ onSuccess }) {
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [success, setSuccess] = useState(false)
  const dark = (() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // a bare axios instance, so the shared 401 interceptor doesn't fire on this call
      const { data } = await axios.post('/api/auth/set-session',
        { api_key: apiKey },
        { withCredentials: true, headers: { 'Content-Type': 'application/json' } })
      if (data?.ok) {
        localStorage.setItem('jobnavigator_api_key', apiKey)
        sessionStorage.setItem('jn:welcome', '1')
        setSuccess(true)
        setTimeout(() => onSuccess?.(), 700)
      } else {
        setError('Unexpected response from server')
      }
    } catch (err) {
      setError(err.response?.status === 401 ? 'Invalid API key' : `Login failed: ${err.message || 'unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'}
      style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
      <form onSubmit={submit}
        style={{ width: 360, background: 'var(--recessed)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', padding: '26px 26px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {success ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '18px 0' }}>
            <span style={{ width: 34, height: 34, borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, lineHeight: 1 }}>✓</span>
            <span style={{ fontFamily: 'var(--serif)', fontSize: 19, letterSpacing: '-.02em' }}>Signed in</span>
            <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>Loading dashboard…</span>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 23, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '28px' }}>JobNavigator</span>
              <span style={{ fontSize: 12.5, color: 'var(--muted)', lineHeight: 1.5, textWrap: 'pretty' }}>
                Enter your dashboard API key — you can view or change it later in Settings.
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 9.5, lineHeight: '14px', letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--muted)' }}>API key</span>
              <div style={{ height: 36, padding: '0 12px', border: `1px solid ${error ? 'var(--bad)' : 'var(--edge)'}`, borderRadius: 7, background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type={showKey ? 'text' : 'password'}
                  placeholder="jn_live_…" autoFocus autoComplete="current-password"
                  style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text)' }} />
                <span onClick={() => setShowKey((v) => !v)} className="v2-anchor" role="button" tabIndex={-1}
                  aria-label={showKey ? 'Hide API key' : 'Show API key'}
                  style={{ fontSize: 10.5, lineHeight: '14px', color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap' }}>{showKey ? 'hide' : 'show'}</span>
              </div>
              {error && <span style={{ fontSize: 11.5, lineHeight: '16px', color: 'var(--bad)' }}>{error}</span>}
            </div>

            <button type="submit" disabled={loading}
              style={{ height: 38, border: 'none', borderRadius: 99, background: loading ? 'var(--edge)' : 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: 'var(--sans)', fontSize: 13.5, fontWeight: 500, cursor: loading ? 'default' : 'pointer' }}>
              {loading && <span className="v2-spin" style={{ width: 11, height: 11, border: '1.5px solid currentColor', borderTopColor: 'transparent', borderRadius: 99 }} />}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>

            <span style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.55, textWrap: 'pretty' }}>
              First run with no key configured? Leave the field blank and sign in — you’ll set one in Settings › Advanced.
            </span>
          </>
        )}
      </form>
    </div>
  )
}
