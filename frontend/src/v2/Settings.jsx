import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import api from '../api'
import './theme.css'

// ── shared bits ──────────────────────────────────────────────────────────────
const PROVIDERS = [
  ['claude_api', 'Claude API (Anthropic)'],
  ['claude_code', 'Claude Code (Subscription)'],
  ['openai', 'OpenAI'],
  ['ollama', 'Ollama (Local)'],
  ['openrouter', 'OpenRouter'],
]
const PROVIDER_LABEL = Object.fromEntries(PROVIDERS)
// providers whose catalog /api/llm/models can search live
const SEARCHABLE = ['openrouter', 'openai', 'claude_api', 'claude_code']
// providers that need no key
const KEYLESS = ['claude_code', 'ollama', '']

const BOX = {
  height: 32, minWidth: 0, padding: '0 10px', border: '1px solid var(--edge)', borderRadius: 6,
  background: 'var(--surface)', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  gap: 7, fontSize: 12.5, color: 'var(--text)', fontFamily: 'var(--sans)', outline: 'none', lineHeight: 1,
}
const CARET = { fontSize: 9, color: 'var(--muted)', flex: '0 0 auto' }
const MASK = '••••••'

const asList = (v) => (Array.isArray(v) ? v.join('\n') : (v == null ? '' : String(v)))
const asJson = (v) => {
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch { return '' }
}

// A dropdown styled as the design's box + caret.
function Select({ value, options, onPick, width, mono, placeholder }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const c = () => setOpen(false)
    document.addEventListener('click', c)
    return () => document.removeEventListener('click', c)
  }, [open])
  const cur = options.find((o) => String(o[0]) === String(value ?? ''))
  return (
    <span style={{ position: 'relative', display: 'flex', flex: `0 1 ${width || '220px'}`, minWidth: 0 }} onClick={(e) => e.stopPropagation()}>
      <div onClick={() => setOpen((v) => !v)} style={{ ...BOX, flex: 1, cursor: 'pointer', borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
        <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: cur ? 'var(--text)' : 'var(--muted)', fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5 }}>
          {cur ? cur[1] : (placeholder || 'Select…')}
        </span>
        <span style={CARET}>▾</span>
      </div>
      {open && (
        <div className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, minWidth: '100%', maxWidth: 420, maxHeight: 320, overflow: 'auto', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: '0 12px 32px rgba(0,0,0,.16)', padding: 5, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {options.map((o) => (
            <div key={String(o[0])} className="v2-menuitem" onClick={() => { onPick(o[0]); setOpen(false) }}
              style={{ padding: '7px 9px', borderRadius: 6, fontSize: 12.5, cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                color: String(o[0]) === String(value ?? '') ? 'var(--accent)' : 'var(--text-2)',
                background: String(o[0]) === String(value ?? '') ? 'var(--accent-soft)' : 'transparent' }}>{o[1]}</div>
          ))}
        </div>
      )}
    </span>
  )
}

// Free-text box; secrets mask until revealed.
function TextBox({ value, onSave, width, mono, secret, placeholder }) {
  const [shown, setShown] = useState(false)
  const [local, setLocal] = useState(value ?? '')
  useEffect(() => { setLocal(value ?? '') }, [value])
  const masked = secret && !shown
  return (
    <span style={{ ...BOX, flex: `0 1 ${width || '340px'}` }}>
      <input
        value={masked ? MASK : local}
        onChange={(e) => !masked && setLocal(e.target.value)}
        onFocus={() => { if (masked) setShown(true) }}
        onBlur={() => { if (!masked && local !== (value ?? '')) onSave(local) }}
        placeholder={placeholder || ''}
        autoComplete="off"
        style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5, color: 'var(--text)' }} />
      {secret && (
        <span onClick={() => setShown((v) => !v)} style={{ fontSize: 10.5, color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap', flex: '0 0 auto' }}>
          {shown ? 'hide' : 'show'}
        </span>
      )}
    </span>
  )
}

function Toggle({ on, label, onPick }) {
  return (
    <span onClick={onPick} style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', flex: '0 0 auto' }}>
      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{label}</span>
      <span style={{ width: 26, height: 15, borderRadius: 99, background: on ? 'var(--accent)' : 'var(--line-strong)', position: 'relative', flex: '0 0 auto' }}>
        <span style={{ position: 'absolute', top: 2, left: on ? 13 : 2, width: 11, height: 11, borderRadius: 99, background: '#fff', transition: 'left 150ms' }} />
      </span>
    </span>
  )
}

// ── main ─────────────────────────────────────────────────────────────────────
export default function Settings() {
  const [S, setS] = useState(null)            // settings map
  const [defaults, setDefaults] = useState({})
  const [resumes, setResumes] = useState([])
  const [personaAvailable, setPersonaAvailable] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState('models')
  const [info, setInfo] = useState(null)      // which row's info panel is open
  const [ovr, setOvr] = useState({})          // which override rows are expanded
  const [trig, setTrig] = useState({})        // action button states
  const [editFor, setEditFor] = useState(null)
  const [modelsOpen, setModelsOpen] = useState(false)
  const [li, setLi] = useState(null)          // linkedin session status
  const [toast, setToast] = useState(null)
  const scrollRef = useRef(null)
  const timers = useRef([])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api.get('/settings'), api.get('/settings/defaults').catch(() => ({ data: {} }))])
      setS(s.data || {}); setDefaults(d.data || {})
      // an override row starts open when it actually has a provider set
      const o = {}
      for (const k of ['scoring_llm', 'llm_fallback', 'cv_tailor_llm', 'cover_letter_llm', 'autofill_llm', 'email_llm']) {
        o[k] = !!(s.data || {})[`${k}_provider`]
      }
      setOvr(o)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => {
    load()
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
    api.get('/linkedin/session').then(({ data }) => setLi(data)).catch(() => {})
  }, [load])

  const flash = (msg, bad = false) => {
    setToast({ msg, bad })
    timers.current.push(setTimeout(() => setToast(null), 2200))
  }

  const save = useCallback(async (key, value) => {
    setS((p) => ({ ...p, [key]: value }))
    try { await api.patch('/settings', { [key]: value }); flash('Saved') }
    catch (e) { console.error(e); flash('Could not save — try again', true) }
  }, [])

  const val = (k, fallback = '') => {
    const v = S?.[k]
    return v === undefined || v === null || v === '' ? fallback : v
  }
  const isOn = (k, dflt = false) => {
    const v = S?.[k]
    if (v === undefined) return dflt
    return v === true || v === 'true'
  }

  // model options for a provider, from llm_models_list
  const modelsList = useMemo(() => {
    let m = S?.llm_models_list
    if (typeof m === 'string') { try { m = JSON.parse(m) } catch { m = [] } }
    return Array.isArray(m) ? m : []
  }, [S])
  const modelsFor = (provider) => {
    const p = provider || 'claude_api'
    const opts = modelsList.filter((m) => m.provider === p).map((m) => [m.model, m.label || m.model])
    return opts
  }

  // ── row builders ──
  const B = (label, help, key, o = {}) => ({ kind: 'box', label, help, key, ...o })
  const SEL = (label, help, key, options, o = {}) => ({ kind: 'select', label, help, key, options, ...o })
  const SW = (label, help, offHelp, key, o = {}) => ({ kind: 'switch', label, help, offHelp, key, ...o })
  const E = (label, help, key, o = {}) => ({ kind: 'edit', label, help, key, ...o })
  const BT = (label, help, btnLabel, act, o = {}) => ({ kind: 'button', label, help, btnLabel, act, ...o })
  const LLM = (label, help, base, o = {}) => ({ kind: 'llm', label, help, base, ...o })

  const runAction = async (id, fn) => {
    if (trig[id]) return
    setTrig((t) => ({ ...t, [id]: 'running' }))
    try {
      await fn()
      setTrig((t) => ({ ...t, [id]: 'done' }))
      timers.current.push(setTimeout(() => setTrig((t) => ({ ...t, [id]: '' })), 2600))
    } catch (e) {
      console.error(e)
      setTrig((t) => ({ ...t, [id]: '' }))
      flash(e?.response?.data?.detail || 'That did not work', true)
    }
  }

  const sections = useMemo(() => {
    if (!S) return []
    const resumeOpts = [['', '(all bases + Persona)'],
      ...(personaAvailable ? [['persona', 'Persona']] : []),
      ...resumes.map((r) => [r.id, r.name])]

    return [
      ['models', 'AI', 'Models', 'one Primary model for everything; override per feature only where it pays', [
        { kind: 'pair', label: 'Primary provider · model', help: 'Every AI feature uses this pair unless overridden below.',
          pKey: 'llm_provider', mKey: 'llm_model',
          info: "Providers: Claude API (Anthropic), Claude Code, OpenAI, Ollama (local), OpenRouter. Picking a provider filters the model dropdown to that provider's models — seeded ones plus any you added under Custom models. OpenRouter reaches every vendor with one key but gets no prompt-cache discount." },
        B('API key', 'Key for the Primary provider API model.', 'llm_api_key', { secret: true, mono: true, w: '340px', hide: () => KEYLESS.includes(val('llm_provider', 'claude_api')) }),
        LLM('Scoring', 'Model that scores new jobs against your résumés.', 'scoring_llm'),
        LLM('Scoring fallback', 'Retries scoring once on error or rate limit — scoring only.', 'llm_fallback',
          { info: 'Fires only when the scoring call errors or hits a rate limit; one retry, then the job is left unscored for the next sweep. Pick a cheap, reliable model from a different provider than the Primary so one outage can’t take both down.' }),
        LLM('Tailoring', 'Model that rewrites résumé bullets for a posting.', 'cv_tailor_llm'),
        LLM('Cover letters', 'Model that drafts letters from résumé + posting + Persona.', 'cover_letter_llm'),
        LLM('Autofill', 'Model that answers application-form questions in the extension.', 'autofill_llm'),
        LLM('Email classification', 'Model that sorts Gmail replies into application events.', 'email_llm'),
        { kind: 'models', label: 'Model catalog', help: 'Add new or unlisted models and remove your additions — changes show up in every model picker.',
          info: 'For models newer than the seeded list. The add search hits the provider’s live catalog for OpenRouter, OpenAI and Claude; Ollama has no catalog — enter the local model name. Removals persist.' },
      ]],
      ['scoring', '', 'Scoring behavior', 'which résumé gets scored, how deep, and when it runs', [
        SEL('Default résumé', 'Used when a company has no résumés of its own selected — the last stop before nothing gets scored. Empty = score against all bases + Persona.', 'default_resume_id', resumeOpts, { w: '260px' }),
        B('Max parallel jobs', 'Extra requests queue — protects the DB pool.', 'scoring_max_concurrent', { mono: true, w: '170px' }),
        SEL('Default depth', 'Used when neither the company nor the search sets its own.', 'scoring_default_depth',
          [['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '340px', dflt: 'light',
            info: 'Light returns scores + a one-liner (cheap, for high-volume searches). Full adds keyword coverage, requirement mapping and a written report. Companies and Searches can each override this per config.' }),
        SEL('On save action', 'Score a job the moment you save it from the feed — only if it has no scores yet.', 'on_save_action',
          [['off', "Off — don't score on save"], ['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '340px', dflt: 'off' }),
        SW('Prompt caching', 'Rubric + résumés + schema sent as a cached block — ~10× cheaper input tokens on repeat calls.', 'Disabled — full price per call.', 'prompt_caching_enabled',
          { dflt: true, info: 'Only active when the effective provider is claude_api — no effect with Claude Code, Ollama or OpenRouter. If scoring output ever looks stale after a rubric edit, disable this as a rollback lever, run once, re-enable.' }),
        E('Scoring rubric', 'The instruction block every scoring call starts from.', 'scoring_rubric', { sub: 'placeholders stay literal — replaced at runtime' }),
        E('Light output schema', 'JSON shape for Light runs.', 'scoring_output_light', { sub: 'CV_NAMES_HERE expands to your résumé names' }),
        E('Full output schema', 'JSON shape for Full runs.', 'scoring_output_full', { sub: 'CV_NAMES_HERE expands to your résumé names' }),
      ]],
      ['tailoring', '', 'Tailoring', 'bullet rewrites — never invents skills or experience', [
        E('Résumé tailoring prompt', 'Rewrites only bullets that benefit; ≤2 new STAR bullets per role.', 'cv_tailor_prompt', { sub: 'placeholders: {job_description} {resume_json}' }),
        E('Persona tailoring prompt', 'Selection from Persona’s richer pool — falls back to the résumé prompt if empty.', 'persona_tailor_prompt', { sub: 'placeholders: {job_description} {persona_json}' }),
        SEL('Auto-score after tailoring', 'Adds a “Tailored: N” entry to the job’s score list when the tailor finishes.', 'tailor_auto_quick_score',
          [['off', "Off — don't score after tailoring"], ['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '340px', dflt: 'light' }),
      ]],
      ['letters', '', 'Cover letters', 'voice presets are injected into the prompt', [
        B('Default voice', 'Preselected in the generate panel; switchable per letter.', 'cover_letter_default_voice', { w: '260px' }),
        E('Voice presets', 'Label + prompt per voice — the Cover Letters screen offers these.', 'cover_letter_voice_presets', { json: true, sub: 'JSON — id, label, instruction per voice' }),
        E('Cover letter prompt', 'The generation instruction.', 'cover_letter_prompt', { sub: 'placeholders: {voice_instruction} {length_instruction} {job_description}' }),
      ]],
      ['autofill', '', 'Autofill', 'used by the extension on ATS forms', [
        B('Default answer length', 'Target length for form answers, in characters.', 'autofill_default_length', { mono: true, w: '170px' }),
        E('Autofill prompt', 'Answers as the candidate, from Persona autofill content only.', 'autofill_prompt', { sub: 'placeholders: {persona} {qa_bank} {company} {position} {question} {max_chars}' }),
        E('Field patterns', 'Maps form-field names to Persona fields.', 'autofill_field_patterns', { json: true, sub: 'JSON — Persona field → name patterns' }),
        E('Option synonyms', 'Normalises dropdown options.', 'autofill_option_synonyms', { json: true, sub: 'JSON — canonical option → synonyms' }),
        SW('Decline self-ID by default', 'Diversity self-ID questions the Persona doesn’t cover auto-select “I prefer not to answer”.', 'Left blank instead.', 'autofill_decline_self_id', { dflt: true }),
      ]],
      ['prep', '', 'Interview prep', 'the handover bundle Applications exports for your LLM of choice', [
        E('What I need from you', 'The closing ask appended to the handover — the four sections above it are assembled from the application.', 'prep_ask', { sub: 'plain text, no placeholders' }),
        SEL('Include by default', 'Sections the handover carries. The role and the closing ask are always included.', 'prep_include',
          [['resume,posting,notes', 'Résumé · posting · notes'], ['resume,posting', 'Résumé · posting'],
            ['posting,notes', 'Posting · notes'], ['resume', 'Résumé only'], ['posting', 'Posting only']], { w: '340px', dflt: 'resume,posting,notes' }),
      ]],
      ['emailclass', '', 'Email classification', 'turns Gmail replies into application events', [
        SW('LLM classification', 'Replies are classified into interview / rejection / offer and attached to the right application.', 'Disabled — replies only show as raw snippets.', 'email_llm_enabled'),
        B('Confidence threshold', '0–100 — below this, the email is flagged for manual review instead.', 'email_llm_confidence_threshold', { mono: true, w: '170px' }),
        E('Classification prompt', 'Labels + confidence + application hint.', 'email_llm_prompt', { sub: 'placeholders: {applications} {from} {subject} {body}' }),
        E('Gmail query · subjects', 'Subject terms the Gmail poll searches for — casts the net for application replies.', 'email_gmail_query_subjects', { list: true, sub: 'one term per line · OR-combined in the Gmail query' }),
        E('Gmail query · senders', 'Sender domains worth checking even without a subject match.', 'email_gmail_query_senders', { list: true, sub: 'one domain per line' }),
        E('Gmail query · exclusions', 'Never classify mail matching these — newsletters and job-alert spam.', 'email_gmail_query_exclusions', { list: true, sub: 'one term per line · appended as -term' }),
      ]],
      ['scheduler', 'PIPELINE', 'Scheduler', 'intervals in minutes (0 = off) · crons are min hour day month dow, empty = off', [
        B('Scrape all companies', 'Runs every active company scrape on this interval.', 'scrape_interval_minutes', { mono: true, w: '170px' }),
        B('Email check', 'Polls Gmail for replies to your applications.', 'email_check_interval_minutes', { mono: true, w: '170px' }),
        B('Cleanup after', 'Days before unsaved postings are purged.', 'job_archive_after_days', { mono: true, w: '170px' }),
        B('Auto-reject after', 'Days of silence before an application is auto-moved to Rejected.', 'auto_reject_after_days', { mono: true, w: '170px',
          info: 'Counts from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in the Stats funnel — nothing is deleted.' }),
        B('DB backup · cron', 'Nightly database snapshot.', 'backup_cron', { mono: true, w: '170px' }),
        B('Telegram digest · cron', 'Morning summary of new high-fit jobs.', 'digest_cron', { mono: true, w: '170px' }),
        B('H-1B refresh · cron', 'Re-imports the sponsorship dataset.', 'h1b_cron', { mono: true, w: '170px' }),
        B('Job cleanup · cron', 'Purges expired postings.', 'cleanup_cron', { mono: true, w: '170px' }),
        B('Auto-reject · cron', 'Applies the auto-reject threshold.', 'reject_cron', { mono: true, w: '170px' }),
        B('Max parallel tailors', 'Tailoring and cover-letter generation share this limit.', 'tailoring_max_concurrent', { mono: true, w: '170px' }),
      ]],
      ['exclude', '', 'Global exclude', 'titles, companies and body phrases dropped before anything else runs', [
        E('Body phrases', 'Postings whose description matches any phrase never enter the feed — every search and scrape.', 'body_exclusion_phrases', { list: true, sub: 'one phrase per line · case-insensitive' }),
        E('Title exclude', 'Dropped when the job title matches — global counterpart of the per-search list.', 'title_exclude_global', { list: true, sub: 'one phrase per line · case-insensitive' }),
        E('Company exclude', 'Exact company names never shown again.', 'company_exclude_global', { list: true, sub: 'one company per line · exact match' }),
      ]],
      ['dedup', '', 'Dedup tracking params', "same job from two sources isn't saved twice", [
        E('Stripped params', 'Query params removed from posting URLs before dedup. All utm_* are always stripped.', 'dedup_tracking_params', { list: true, sub: 'one param per line' }),
      ]],
      ['notifications', 'INTEGRATIONS', 'Notifications', 'Telegram bot · digest schedule lives under Scheduler', [
        SW('Telegram', 'High-fit arrivals and the daily digest go to your chat.', 'Off — no push notifications.', 'telegram_enabled'),
        B('Chat ID', 'Your Telegram chat — get it by messaging @userinfobot.', 'telegram_chat_id', { mono: true, w: '170px' }),
        B('Score threshold', 'Only jobs scoring at or above this trigger an instant alert — everything else waits for the digest.', 'fit_score_threshold', { mono: true, w: '170px' }),
        BT('Test', 'Confirms the bot token and chat ID work end to end.', 'Send test message', () => api.post('/telegram/test')),
        { kind: 'button', label: 'Webhook secret', help: 'Optional — alerts and the digest work without a webhook. Validates every Telegram → backend call.',
          btnLabel: 'Rotate', preview: S.telegram_webhook_secret === MASK ? 'Set (hidden — rotate to view)' : (S.telegram_webhook_secret ? 'Set' : 'Not set'),
          info: 'Telegram sends the secret as X-Telegram-Bot-Api-Secret-Token on every webhook call; mismatched headers return 401. Rotating shows the new secret once — copy it immediately, then re-register the webhook.',
          act: async () => {
            if (!window.confirm('Rotate the webhook secret? You must re-register the webhook afterward.')) return
            const { data } = await api.post('/telegram/rotate-webhook-secret')
            window.prompt('Copy the new secret now — it will not be shown again:', data.webhook_secret || '')
            load()
          } },
        BT('Register webhook', 'Points Telegram at your public URL so inbound bot commands reach the backend.', 'Register…', async () => {
          const url = window.prompt('Public base URL (https://...):')
          if (!url) return
          const { data } = await api.post('/telegram/register-webhook', { public_url: url })
          flash(data?.ok === false ? (data.description || 'Registration failed') : 'Webhook registered')
        }),
      ]],
      ['tracer', '', 'Tracer links', 'per-application open tracking in Stats', [
        SW('Rewrite links', 'Résumé and letter links route through your domain so opens show up per application.', 'Off — documents keep their original links.', 'tracer_links_enabled',
          { info: 'Each application gets its own short link per document link. When a recruiter opens one, the hit lands in Stats against that application.' }),
        B('Base URL', 'Your tracer domain.', 'tracer_links_base_url', { mono: true, w: '260px', placeholder: 'https://yourdomain.com' }),
        SEL('URL style', 'Short = /cv/a7x2kp; job-id = /cv/142li.', 'tracer_links_url_style',
          [['path', 'Path + random (/cv/a7x2kp)'], ['param', 'Param + random (?cv=a7x2kp)'],
            ['path_jobid', 'Path + job ID (/cv/142li)'], ['param_jobid', 'Param + job ID (?cv=142li)']], { w: '260px', dflt: 'path' }),
      ]],
      ['jobright', '', 'Jobright.ai', 'credentials for the Jobright search mode', [
        B('Email', 'Your Jobright account.', 'jobright_email', { w: '260px' }),
        B('Password', 'Stored locally only.', 'jobright_password', { secret: true, w: '260px' }),
      ]],
      ['linkedin', '', 'LinkedIn', "personal scraping + the extension's separate capture identity", [
        B('Personal email', 'Used by LinkedIn Personal collections.', 'linkedin_email', { w: '260px' }),
        B('Personal password', 'Stored locally only.', 'linkedin_password', { secret: true, w: '260px' }),
        { kind: 'linkedin', label: 'Session cookie', help: 'The extension import reuses a signed-in cookie jar. LinkedIn gates the login behind an emailed PIN, so refreshing asks you for the code.' },
        B('Mock account email', 'The extension browses collections as this account, away from your real profile.', 'linkedin_mock_email', { w: '260px',
          info: 'Capture happens while the extension browses LinkedIn collections. Doing that on a throwaway account means rate limits, CAPTCHAs or bans hit the mock identity — never your real profile.' }),
        B('Mock account password', 'Stored locally only.', 'linkedin_mock_password', { secret: true, w: '260px' }),
      ]],
      ['advanced', 'SYSTEM', 'Advanced', 'escape hatches — most days none of this gets touched', [
        B('Proxy URL', 'Used by scrapes that hit rate limits or geo-blocks. Empty = direct.', 'proxy_url', { mono: true, w: '340px', placeholder: 'socks5://127.0.0.1:9050' }),
        { kind: 'apikey', label: 'Dashboard API key', help: 'Saving refreshes the session cookie so iframes and downloads keep working.' },
        BT('DB backup', 'Snapshot now, outside the cron.', 'Run backup', () => api.post('/db/backup')),
        BT('H-1B data', 'Re-import the sponsorship dataset.', 'Refresh now', () => api.post('/h1b/refresh')),
        BT('Job cleanup', 'Purge expired postings now.', 'Run cleanup', () => api.post('/db/cleanup')),
      ]],
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [S, resumes, personaAvailable, trig, li])

  const q = query.trim().toLowerCase()
  const matches = (sec) => !q || sec[2].toLowerCase().includes(q) ||
    sec[4].some((r) => `${r.label} ${r.help || ''}`.toLowerCase().includes(q))
  const visible = sections.filter(matches)

  if (!S) return <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)' }} />

  const jump = (id) => {
    setActive(id); setQuery('')
    const c = scrollRef.current
    const el = c && c.querySelector(`[data-sec="sec-${id}"]`)
    // offsetTop is relative to the nearest positioned ancestor, which isn't the
    // scroller here — measure the delta between the two rects instead
    if (c && el) c.scrollTop += el.getBoundingClientRect().top - c.getBoundingClientRect().top - 4
  }

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ flex: '0 0 auto', padding: '22px 30px 16px', display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 30, fontWeight: 400, letterSpacing: '-.02em', lineHeight: 1 }}>Settings</h1>
          <span style={{ fontSize: 13, lineHeight: '20px', color: toast?.bad ? 'var(--bad)' : (toast ? 'var(--accent)' : 'var(--muted)'), whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', transition: 'color .15s' }}>
            {toast ? toast.msg : 'Saves automatically · everything stays on this machine'}
          </span>
        </div>
        <div style={{ marginLeft: 'auto', flex: '0 0 auto', height: 30, width: 230, padding: '0 12px', border: '1px solid var(--edge)', background: 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ flex: '0 0 auto', fontSize: 11, color: 'var(--muted)' }}>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search settings…"
            style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
        </div>
      </header>

      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* anchor rail */}
        <div className="v2-scroll" style={{ flex: '0 0 216px', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '16px 0 20px' }}>
          {sections.map(([id, group, title]) => (
            <div key={id} style={{ display: 'flex', flexDirection: 'column' }}>
              {group && <div style={{ fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: 'var(--muted)', padding: '14px 26px 6px 30px' }}>{group}</div>}
              <div onClick={() => jump(id)} className="v2-anchor" style={{ display: 'flex', alignItems: 'center', height: 29, padding: '0 26px 0 30px', fontSize: 12.5, cursor: 'pointer',
                color: active === id && !q ? 'var(--text)' : 'var(--text-2)', fontWeight: active === id && !q ? 600 : 400,
                borderLeft: `2px solid ${active === id && !q ? 'var(--accent)' : 'transparent'}` }}>{title}</div>
            </div>
          ))}
        </div>

        {/* rows */}
        <div ref={scrollRef} className="v2-scroll" style={{ flex: 1, minWidth: 0, overflow: 'auto', padding: '0 40px 40px', minHeight: 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', maxWidth: 980 }}>
            {visible.map(([id, , title, sub, rows]) => (
              <div key={id} style={{ display: 'flex', flexDirection: 'column' }}>
                <div data-sec={`sec-${id}`} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '26px 0 4px' }}>
                  {/* integer line-heights: at the inherited 1.5 these are 28.5 and
                      17.25, which puts every row below the header on a half pixel
                      and drops its 1px bottom rule */}
                  <span style={{ fontFamily: 'var(--serif)', fontSize: 19, lineHeight: '26px', fontWeight: 500, letterSpacing: '-.015em' }}>{title}</span>
                  <span style={{ fontSize: 11.5, lineHeight: '26px', color: 'var(--muted)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sub}</span>
                </div>
                {rows.filter((r) => !(r.hide && r.hide())).map((r) => (
                  <Row key={r.label} r={r} ctx={{ S, val, isOn, save, info, setInfo, ovr, setOvr, trig, runAction, setEditFor, setModelsOpen, modelsFor, li, setLi, flash, defaults }} />
                ))}
              </div>
            ))}
            {visible.length === 0 && (
              <div style={{ padding: '44px 0', fontSize: 12.5, color: 'var(--muted)' }}>No settings match “{query}”.</div>
            )}
          </div>
        </div>
      </div>

      {editFor && <EditModal spec={editFor} S={S} defaults={defaults} onSave={save} onClose={() => setEditFor(null)} />}
      {modelsOpen && <ModelsModal S={S} save={save} onClose={() => setModelsOpen(false)} />}
    </div>
  )
}

// ── one settings row ─────────────────────────────────────────────────────────
function Row({ r, ctx }) {
  const { val, isOn, save, info, setInfo, ovr, setOvr, trig, runAction, setEditFor, setModelsOpen, modelsFor, li, setLi, flash, S } = ctx
  const infoOpen = r.info && info === r.label

  const right = (() => {
    switch (r.kind) {
      case 'box':
        return <TextBox value={val(r.key)} onSave={(v) => save(r.key, v)} width={r.w} mono={r.mono} secret={r.secret} placeholder={r.placeholder} />
      case 'select':
        return <Select value={val(r.key, r.dflt)} options={r.options} onPick={(v) => save(r.key, v)} width={r.w} />
      case 'switch': {
        const on = isOn(r.key, r.dflt)
        return <Toggle on={on} label={on ? 'On' : 'Off'} onPick={() => save(r.key, on ? 'false' : 'true')} />
      }
      case 'pair': {
        const p = val(r.pKey, 'claude_api')
        return (
          <>
            <Select value={p} options={PROVIDERS} onPick={(v) => save(r.pKey, v)} width="220px" />
            <Select value={val(r.mKey)} options={modelsFor(p)} onPick={(v) => save(r.mKey, v)} width="260px" mono placeholder="pick model…" />
          </>
        )
      }
      case 'llm': {
        const on = !!ovr[r.base]
        const p = val(`${r.base}_provider`)
        return (
          <>
            {on && <Select value={p} options={PROVIDERS} onPick={(v) => save(`${r.base}_provider`, v)} width="200px" placeholder="pick provider…" />}
            {on && <Select value={val(`${r.base}_model`)} options={modelsFor(p || val('llm_provider', 'claude_api'))} onPick={(v) => save(`${r.base}_model`, v)} width="260px" mono placeholder="pick model…" />}
            {on && p && !KEYLESS.includes(p) && (
              <span title="API key for this override's provider" style={{ display: 'flex', flex: '0 1 150px', minWidth: 0 }}>
                <TextBox value={val(`${r.base}_api_key`)} onSave={(v) => save(`${r.base}_api_key`, v)} width="150px" mono secret />
              </span>
            )}
            {!on && <span style={{ fontSize: 9.5, letterSpacing: '.06em', textTransform: 'uppercase', padding: '1px 7px', borderRadius: 99, background: 'var(--surface-2)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>inherits Primary</span>}
            <span style={{ marginLeft: 'auto' }}>
              <Toggle on={on} label="Override" onPick={() => {
                const next = !on
                setOvr((o) => ({ ...o, [r.base]: next }))
                if (!next) { save(`${r.base}_provider`, ''); save(`${r.base}_model`, '') }
              }} />
            </span>
          </>
        )
      }
      case 'edit': {
        const raw = S[r.key]
        const preview = r.list ? asList(raw).split('\n').filter(Boolean).join(' · ')
          : r.json ? asJson(raw).replace(/\s+/g, ' ')
            : String(raw ?? '')
        return (
          <>
            <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{preview || '—'}</span>
            <span onClick={() => setEditFor(r)} className="v2-bdc" style={{ flex: '0 0 auto', height: 26, padding: '0 12px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer' }}>Edit</span>
          </>
        )
      }
      case 'models':
        return (
          <>
            <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {(() => { let m = S.llm_models_list; if (typeof m === 'string') { try { m = JSON.parse(m) } catch { m = [] } } m = Array.isArray(m) ? m : []
                const c = m.filter((x) => x.custom).length
                return `${m.length} models · ${m.length - c} seeded · ${c} added by you` })()}
            </span>
            <ActionBtn label="Manage…" state="" onClick={() => setModelsOpen(true)} />
          </>
        )
      case 'button':
        return (
          <>
            {r.preview && <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.preview}</span>}
            <ActionBtn label={r.btnLabel} state={trig[r.label] || ''} onClick={() => runAction(r.label, r.act)} />
          </>
        )
      case 'apikey':
        return <ApiKeyRow value={val('dashboard_api_key')} save={save} flash={flash} />
      case 'linkedin':
        return <LinkedInRow li={li} setLi={setLi} flash={flash} />
      default:
        return null
    }
  })()

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24, minHeight: 52, padding: '9px 0', borderBottom: '1px solid var(--line-soft)' }}>
      <div style={{ flex: '0 0 340px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, lineHeight: '18px', fontWeight: 500 }}>
          {r.label}
          {r.info && (
            <span onClick={() => setInfo(infoOpen ? null : r.label)} title="More detail"
              style={{ width: 15, height: 15, flex: '0 0 auto', border: `1px solid ${infoOpen ? 'var(--accent)' : 'var(--edge)'}`, background: infoOpen ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 400, color: infoOpen ? 'var(--accent)' : 'var(--muted)', cursor: 'pointer', fontFamily: 'var(--serif)', fontStyle: 'italic' }}>
              {/* the italic serif 'i' has no descender and slants right, so flex
                  centring leaves its ink high and right of the circle's centre */}
              <span style={{ display: 'block', transform: 'translate(-0.5px, 1.2px)' }}>i</span>
            </span>
          )}
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)', lineHeight: '16px', textWrap: 'pretty' }}>
          {r.kind === 'switch' && !isOn(r.key, r.dflt) && r.offHelp ? r.offHelp : r.help}
        </span>
        {infoOpen && (
          <span style={{ fontSize: 11, lineHeight: '17px', color: 'var(--text-2)', background: 'var(--surface-2)', borderRadius: 7, padding: '8px 10px', marginTop: 5, textWrap: 'pretty' }}>{r.info}</span>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>{right}</div>
    </div>
  )
}

function ActionBtn({ label, state, onClick }) {
  const done = state === 'done'
  return (
    <span onClick={onClick} className="v2-bd v2-ctl" style={{ flex: '0 0 auto', height: 30, padding: '0 14px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, whiteSpace: 'nowrap', cursor: 'pointer',
      border: `1px solid ${done ? 'var(--accent)' : 'var(--edge)'}`, background: done ? 'var(--accent-soft)' : 'var(--surface)', color: done ? 'var(--accent)' : 'var(--text-2)' }}>
      {state === 'running' && <span className="v2-spin" style={{ width: 9, height: 9, border: '1.5px solid var(--accent)', borderTopColor: 'transparent', borderRadius: 99 }} />}
      {state === 'running' ? 'Running…' : done ? 'Done ✓' : label}
    </span>
  )
}

// The v1 page wrote the mask into localStorage when you saved without retyping,
// which locked you out. This only writes a key you actually entered.
function ApiKeyRow({ value, save, flash }) {
  const [local, setLocal] = useState('')
  const [shown, setShown] = useState(false)
  const isSet = value === MASK || (value && value.length > 0)
  return (
    <>
      <span style={{ ...BOX, flex: '0 1 340px' }}>
        <input value={local} onChange={(e) => setLocal(e.target.value)} type={shown ? 'text' : 'password'} autoComplete="off"
          placeholder={isSet ? 'Set — type a new key to replace it' : 'No key — the dashboard is open'}
          style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)' }} />
        <span onClick={() => setShown((v) => !v)} style={{ fontSize: 10.5, color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap' }}>{shown ? 'hide' : 'show'}</span>
      </span>
      <ActionBtn label="Save key" state="" onClick={async () => {
        if (!local.trim()) { flash('Type the new key first', true); return }
        await save('dashboard_api_key', local.trim())
        try { localStorage.setItem('jobnavigator_api_key', local.trim()) } catch {}
        try { await api.post('/auth/set-session', { api_key: local.trim() }) } catch { /* cookie refresh is best effort */ }
        setLocal(''); flash('Key saved')
      }} />
    </>
  )
}

function LinkedInRow({ li, setLi, flash }) {
  const [pin, setPin] = useState('')
  const poll = useRef(null)
  useEffect(() => () => clearInterval(poll.current), [])

  const start = async () => {
    try {
      await api.post('/linkedin/session/refresh')
      clearInterval(poll.current)
      poll.current = setInterval(async () => {
        try {
          const { data } = await api.get('/linkedin/session')
          setLi(data)
          if (!['running', 'awaiting_pin'].includes(data.phase)) clearInterval(poll.current)
        } catch { /* keep polling */ }
      }, 2500)
    } catch (e) { flash(e?.response?.data?.detail || 'Could not start the refresh', true) }
  }

  const phase = li?.phase || 'idle'
  const busy = phase === 'running' || phase === 'awaiting_pin'
  const tone = li?.status === 'ok' ? 'var(--good)' : li?.status === 'stale' ? 'var(--warn)' : 'var(--muted)'

  return (
    <>
      <span style={{ flex: 1, minWidth: 0, fontSize: 11.5, color: tone, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {phase === 'awaiting_pin' ? 'LinkedIn emailed a PIN to the mock account.'
          : phase === 'running' ? (li?.detail || 'Signing in…')
            : (li?.summary || 'Unknown')}
      </span>
      {phase === 'awaiting_pin' && (
        <>
          <span style={{ ...BOX, flex: '0 1 120px' }}>
            <input value={pin} onChange={(e) => setPin(e.target.value)} placeholder="6-digit PIN" inputMode="numeric"
              style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)' }} />
          </span>
          <ActionBtn label="Submit PIN" state="" onClick={async () => {
            const { data } = await api.post('/linkedin/session/pin', { pin })
            if (!data.ok) flash(data.detail || 'Enter the digits from the email', true)
            else { setPin(''); flash('PIN sent') }
          }} />
        </>
      )}
      {phase !== 'awaiting_pin' && <ActionBtn label="Refresh cookie" state={busy ? 'running' : ''} onClick={start} />}
    </>
  )
}

// ── long-text editor ─────────────────────────────────────────────────────────
function EditModal({ spec, S, defaults, onSave, onClose }) {
  const initial = spec.list ? asList(S[spec.key]) : spec.json ? asJson(S[spec.key]) : String(S[spec.key] ?? '')
  const [text, setText] = useState(initial)
  const [err, setErr] = useState('')
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])

  const commit = (value) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      if (spec.list) { onSave(spec.key, value.split('\n').map((x) => x.trim()).filter(Boolean)); setErr(''); return }
      if (spec.json) {
        try { onSave(spec.key, JSON.parse(value)); setErr('') }
        catch { setErr('Not valid JSON — nothing saved yet') }
        return
      }
      onSave(spec.key, value); setErr('')
    }, 600)
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 680, maxHeight: 640, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>{spec.label}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{spec.sub || ''}</span>
          <div onClick={onClose} className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '16px 22px', minHeight: 0 }}>
          <textarea value={text} onChange={(e) => { setText(e.target.value); commit(e.target.value) }}
            style={{ width: '100%', minHeight: 220, padding: '12px 14px', border: `1px solid ${err ? 'var(--bad)' : 'var(--edge)'}`, borderRadius: 8, background: 'var(--surface)', fontFamily: 'var(--mono)', fontSize: 11.5, lineHeight: 1.7, color: 'var(--text)', outline: 'none', resize: 'vertical' }} />
        </div>
        <div style={{ flex: '0 0 auto', padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: err ? 'var(--bad)' : 'var(--muted)' }}>{err || 'Saves automatically as you type'}</span>
          <div onClick={() => {
            const d = defaults[spec.key]
            const t = spec.list ? asList(d) : spec.json ? asJson(d) : String(d ?? '')
            setText(t); commit(t)
          }} className="v2-bdc" style={{ marginLeft: 'auto', height: 31, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Reset to default</div>
          <div onClick={onClose} style={{ height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Done</div>
        </div>
      </div>
    </div>
  )
}

// ── model catalog ────────────────────────────────────────────────────────────
function ModelsModal({ S, save, onClose }) {
  const [provider, setProvider] = useState('openrouter')
  const [term, setTerm] = useState('')
  const [live, setLive] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  let list = S.llm_models_list
  if (typeof list === 'string') { try { list = JSON.parse(list) } catch { list = [] } }
  list = Array.isArray(list) ? list : []

  useEffect(() => {
    if (!SEARCHABLE.includes(provider)) { setLive([]); setErr(''); return }
    let dead = false
    setLoading(true); setErr('')
    api.get('/llm/models', { params: { provider } })
      .then(({ data }) => { if (!dead) setLive(Array.isArray(data) ? data : (data?.models || [])) })
      .catch((e) => { if (!dead) setErr(e?.response?.data?.detail || 'Could not reach the catalog') })
      .finally(() => { if (!dead) setLoading(false) })
    return () => { dead = true }
  }, [provider])

  const suggestions = useMemo(() => {
    const t = term.trim().toLowerCase()
    const names = live.map((m) => (typeof m === 'string' ? m : (m.id || m.model || ''))).filter(Boolean)
    return (t ? names.filter((n) => n.toLowerCase().includes(t)) : names).slice(0, 60)
  }, [live, term])

  const add = (slug) => {
    const model = (slug || term).trim()
    if (!model) return
    if (list.some((m) => m.provider === provider && m.model === model)) { setTerm(''); return }
    save('llm_models_list', [...list, { provider, model, label: `${model} (custom)`, custom: true }])
    setTerm('')
  }
  const remove = (m) => {
    if (!window.confirm(`Remove "${m.model}" from ${PROVIDER_LABEL[m.provider] || m.provider}?`)) return
    save('llm_models_list', list.filter((x) => !(x.provider === m.provider && x.model === m.model)))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 600, maxHeight: 620, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: '0 18px 50px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Model catalog</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>available in every model picker</span>
          <div onClick={onClose} className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div style={{ flex: '0 0 auto', padding: '12px 22px', borderBottom: '1px solid var(--line-soft)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Select value={provider} options={PROVIDERS} onPick={setProvider} width="150px" />
          <span style={{ ...BOX, flex: 1, height: 31 }}>
            <input value={term} onChange={(e) => setTerm(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') add() }}
              placeholder={SEARCHABLE.includes(provider)
                ? (loading ? 'Loading live models…' : `Search ${live.length} live models, or paste any slug…`)
                : 'Enter the local model name…'}
              style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
          </span>
          <div onClick={() => add()} className="v2-ctl" style={{ flex: '0 0 auto', height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Add</div>
        </div>
        {err && <div style={{ padding: '8px 22px', fontSize: 11.5, color: 'var(--bad)' }}>{err}</div>}
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '6px 22px 14px' }}>
          {term && suggestions.length > 0 && (
            <div style={{ padding: '4px 0 8px', display: 'flex', flexDirection: 'column' }}>
              {suggestions.slice(0, 8).map((n) => (
                <div key={n} className="v2-menuitem" onClick={() => add(n)} style={{ padding: '6px 8px', borderRadius: 6, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{n}</div>
              ))}
            </div>
          )}
          {list.map((m) => (
            <div key={`${m.provider}/${m.model}`} style={{ display: 'flex', alignItems: 'center', gap: 10, height: 36, borderBottom: '1px solid var(--line-soft)' }}>
              <span style={{ flex: '0 0 92px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--edge)' }}>{m.provider}</span>
              <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.model}</span>
              <span style={{ flex: '0 0 auto', fontSize: 10, color: m.custom ? 'var(--accent)' : 'var(--edge)' }}>{m.custom ? 'added by you' : 'seeded'}</span>
              <span onClick={() => remove(m)} title="Remove — removal persists" className="v2-hover-bad-text"
                style={{ width: 22, height: 22, border: '1px solid var(--line)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--edge)', cursor: 'pointer', flex: '0 0 auto' }}>×</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
