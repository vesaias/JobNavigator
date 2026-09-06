import React from 'react'
import { Button, FooterRow, Heading, Helper, IconButton, Link, ModalPanel } from './ui'
import { useTheme, themeAttrs } from './theme'
import './theme.css'

// The UPGRADE overlay — the twin of WelcomeModal, for the other kind of arrival.
//
// WelcomeModal is the first-run tour: four setup steps, shown only to a profile
// that has never used JobNavigator (`jobnavigator_welcomed` absent). This one is
// for the person who already has a working install and just had the interface
// replaced under them: nothing to set up, four lines on what moved. App.jsx owns
// the mutual exclusion — the tour wins, and this modal waits for the next visit.
//
// Announcement copy is versioned, not evergreen: the seen-mark carries the
// release it was written for, so the next release can raise a new one by
// bumping the constant in App.jsx rather than by clearing anybody's storage.
export const RELEASE_NOTES_URL = 'https://github.com/vesaias/JobNavigator/blob/main/CHANGELOG.md'

const TITLE_ID = 'jn-newui-title'

const POINTS = [
  'Everything you know, rebuilt: Jobs, Companies, Applications, Résumés, Cover Letters, Persona, Stats, Settings.',
  'Pick a look in Settings › Display: Paper, Green Paper, Stone, V1 Style or Windows 98, light or dark.',
  'Persona import from a résumé or PDF, a cron helper for schedules, Feed shortcuts (press ? in Jobs).',
  'The classic dashboard is still at /classic (Settings › Display) for one more release.',
]

export default function NewUiModal({ onClose }) {
  // mounts outside the v2 shell like the sign-in and welcome overlays, so it
  // brings the theme with it from the shared store
  const look = useTheme()

  return (
    // Same contract as WelcomeModal: scrim click and Escape both close, and the
    // Escape listener is registered in the CAPTURE phase because this overlay
    // mounts above a screen that already claimed the key (R4-E2E-01).
    <ModalPanel width={460} title="Welcome to the new JobNavigator" onClose={onClose} escapeCapture zIndex={9998}
      labelledBy={TITLE_ID}
      scrimProps={{ className: 'jn-v2', ...themeAttrs(look) }}
      scrimStyle={{ padding: 16 }}
      style={{ maxWidth: '100%', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '20px 24px 4px' }}>
        <Heading size={19} id={TITLE_ID}>Welcome to the new JobNavigator</Heading>
        <IconButton title="Close" onClick={onClose} style={{ marginLeft: 'auto' }}>✕</IconButton>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 9, padding: '10px 24px 18px' }}>
        {POINTS.map((point) => (
          <div key={point} style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
            <Helper style={{ flex: '0 0 auto' }}>•</Helper>
            <Helper style={{ textWrap: 'pretty' }}>{point}</Helper>
          </div>
        ))}
      </div>

      <FooterRow pad="12px 24px" soft bg="page">
        <Link href={RELEASE_NOTES_URL} target="_blank">Read the release notes</Link>
        <Button size="xs" onClick={onClose} style={{ marginLeft: 'auto' }}>Got it</Button>
      </FooterRow>
    </ModalPanel>
  )
}
