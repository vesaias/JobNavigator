import React, { useState } from 'react'
import axios from 'axios'
import { Button, Heading, Helper, Label, ModalPanel } from './ui'
import { useTheme, themeAttrs } from './theme'
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
  // this overlay mounts outside the v2 shell, so it carries the theme itself —
  // from the shared store, not a private read of the flag (SHELL-02)
  const theme = useTheme()

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
    // The sign-in overlay mounts outside the v2 shell, so the scrim carries the
    // theme root (`jn-v2` + data-theme) and its own z-index; the panel is a real
    // <form> so Enter in the key field submits. No `onClose`: there is nothing
    // behind this overlay to go back to, so it takes no Escape/scrim dismissal —
    // the same as before.
    <ModalPanel as="form" onSubmit={submit} width={360} zIndex={9999}
      scrimProps={{ className: 'jn-v2', ...themeAttrs(theme) }}
      style={{ padding: '26px 26px 22px', gap: 14 }}>
      {success ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '18px 0' }}>
          {/* ui: keep — success glyph, not a control (no handler, no hover, 34px round badge) */}
          <span style={{ width: 34, height: 34, borderRadius: 'var(--radius-control)', background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, lineHeight: 1 }}>✓</span>
          <Heading size={19}>Signed in</Heading>
          <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>Loading dashboard…</span>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {/* ui: keep — the sign-in wordmark is serif 23/28px; the Heading scale is 18/19/22 */}
            <span style={{ fontFamily: 'var(--serif)', fontSize: 23, fontWeight: 400, letterSpacing: '-.02em', lineHeight: '28px' }}>JobNavigator</span>
            <span style={{ fontSize: 12.5, color: 'var(--muted)', lineHeight: 1.5, textWrap: 'pretty' }}>
              Enter your dashboard API key — you can view or change it later in Settings.
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <Label>API key</Label>
            <div className="v2-fieldwrap" style={{ height: 36, padding: '0 12px', border: `1px solid ${error ? 'var(--bad)' : 'var(--edge)'}`, borderRadius: 'var(--radius-row)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 8 }}>
              {/* ui: keep — the API-key field is a bare input inside a v2-fieldwrap that also
                  holds the show/hide toggle and turns --bad on an error; Input draws its own
                  box, so it cannot render this composite */}
              <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type={showKey ? 'text' : 'password'}
                placeholder="jn_live_…" autoFocus autoComplete="current-password"
                style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text)' }} />
              {/* ui: keep — the show/hide toggle is deliberately out of the tab order (tabIndex -1)
                  beside the key field, and Link is a tab stop with role="link" */}
              <span onClick={() => setShowKey((v) => !v)} className="v2-anchor" role="button" tabIndex={-1}
                aria-label={showKey ? 'Hide API key' : 'Show API key'}
                style={{ fontSize: 10.5, lineHeight: '14px', color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap' }}>{showKey ? 'hide' : 'show'}</span>
            </div>
            {error && <Helper style={{ color: 'var(--bad)' }}>{error}</Helper>}
          </div>

          <Button as="button" type="submit" busy={loading} ariaLabel="Sign in">
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>

          <Helper style={{ textWrap: 'pretty' }}>
            If no API key is set yet, leave this blank and sign in. You can add a key later in Settings › Advanced.
          </Helper>
        </>
      )}
    </ModalPanel>
  )
}
