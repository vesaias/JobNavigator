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

// SET-12: every control on this screen is a span/div with onClick, so none of
// them were tabbable and none announced a role. Spread kb(fn) onto such an
// element: it becomes focusable, announces a role, and fires the same handler
// on Enter/Space that the click does. Local copy of the helper in
// ResumeSections.jsx:16-24 — same contract, no cross-screen import.
// The focus ring is theme.css's `[tabindex="0"]:focus-visible`.
const kb = (fn, role = 'button') => ({
  tabIndex: 0,
  role,
  onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

const asList = (v) => (Array.isArray(v) ? v.join('\n') : (v == null ? '' : String(v)))
const asJson = (v) => {
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch { return '' }
}

// A dropdown styled as the design's box + caret.
function Select({ value, options, onPick, width, mono, placeholder, ariaLabel, emptyText }) {
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
      <div onClick={() => setOpen((v) => !v)} {...kb(() => setOpen((v) => !v))} aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open}
        style={{ ...BOX, flex: 1, cursor: 'pointer', borderColor: open ? 'var(--accent)' : 'var(--edge)' }}>
        <span style={{ minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: cur ? 'var(--text)' : 'var(--muted)', fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5 }}>
          {cur ? cur[1] : (placeholder || 'Select…')}
        </span>
        <span style={CARET}>▾</span>
      </div>
      {open && (
        <div className="v2-scroll" role="listbox" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 40, minWidth: '100%', maxWidth: 420, maxHeight: 320, overflow: 'auto', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, boxShadow: 'var(--shadow-menu)', padding: 5, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {/* SET-23: with no options the menu chrome used to open as a bare 12px
              empty box — say why it's empty instead */}
          {options.length === 0 ? (
            <div style={{ padding: '7px 9px', fontSize: 11.5, lineHeight: '16px', color: 'var(--muted)', textWrap: 'pretty' }}>
              {emptyText || 'no models for this provider — add one under Model catalog'}
            </div>
          ) : options.map((o) => (
            <div key={String(o[0])} className="v2-menuitem" onClick={() => { onPick(o[0]); setOpen(false) }}
              {...kb(() => { onPick(o[0]); setOpen(false) }, 'option')} aria-selected={String(o[0]) === String(value ?? '')}
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
// GET /settings returns a set secret as the literal six-bullet MASK string, so
// three things have to be true at once: an *unset* secret must not look set,
// revealing must not leave the mask in the box (typing after it used to PATCH
// "••••••<typed>", and the server only drops an exact mask — that silently
// destroyed the stored secret), and clearing the box must not wipe the secret.
function TextBox({ value, onSave, width, mono, secret, placeholder, ariaLabel, int, cron, onInvalid }) {
  const [shown, setShown] = useState(false)
  const [local, setLocal] = useState(value ?? '')
  useEffect(() => { setLocal(value ?? '') }, [value])
  const isMask = value === MASK
  const masked = secret && !shown && !!value
  const reveal = () => { setShown(true); if (local === MASK) setLocal('') }
  const toggleShown = () => (shown ? setShown(false) : reveal())
  const commit = () => {
    if (masked) return
    if (local === MASK) return                  // untouched mask — nothing to save
    if (local === '' && isMask) return          // emptied but nothing typed — don't wipe the stored secret
    if (local === (value ?? '')) return
    // SET-27: a malformed cron never reaches configure_scheduler() — an empty
    // one is legal (= off), anything else has to be the five standard fields
    if (cron && local.trim() !== '' && local.trim().split(/\s+/).length !== 5) {
      if (onInvalid) onInvalid('Cron needs 5 fields')
      return
    }
    onSave(local)
  }
  return (
    <span style={{ ...BOX, flex: `0 1 ${width || '340px'}` }}>
      <input
        value={masked ? MASK : local}
        // SET-27: the integer rows feed unguarded int() calls in the backend, so
        // keep anything but digits out of the box (empty stays legal)
        onChange={(e) => !masked && setLocal(int ? e.target.value.replace(/[^0-9]/g, '') : e.target.value)}
        onFocus={() => { if (masked) reveal() }}
        onBlur={commit}
        inputMode={int ? 'numeric' : undefined}
        aria-label={ariaLabel}
        placeholder={placeholder || (secret && shown && isMask ? 'type a new value to replace it' : '')}
        autoComplete="off"
        style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: mono ? 'var(--mono)' : 'var(--sans)', fontSize: mono ? 11.5 : 12.5, color: 'var(--text)' }} />
      {secret && !!value && (
        <span onClick={toggleShown} {...kb(toggleShown)} aria-label={`${shown ? 'Hide' : 'Show'} ${ariaLabel || 'value'}`}
          style={{ fontSize: 10.5, lineHeight: '16px', color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap', flex: '0 0 auto' }}>
          {shown ? 'hide' : 'show'}
        </span>
      )}
    </span>
  )
}

function Toggle({ on, label, onPick, ariaLabel }) {
  return (
    <span onClick={onPick} {...kb(onPick, 'switch')} aria-checked={on} aria-label={ariaLabel}
      style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', flex: '0 0 auto' }}>
      <span style={{ fontSize: 11, lineHeight: '16px', color: 'var(--muted)' }}>{label}</span>
      <span style={{ width: 26, height: 15, borderRadius: 99, background: on ? 'var(--accent)' : 'var(--line-strong)', position: 'relative', flex: '0 0 auto' }}>
        {/* SET-14: --knob is white in both themes, which is 2.16:1 on the dark
            theme's light-green track. --surface-2 (user's pick, 2026-09-03) is the ON knob so it reads as a
            surface disc on the accent track in both themes; OFF keeps --knob
            against the neutral track. */}
        <span style={{ position: 'absolute', top: 2, left: on ? 13 : 2, width: 11, height: 11, borderRadius: 99, background: on ? 'var(--surface-2)' : 'var(--knob)', transition: 'left 150ms' }} />
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
  const [loadErr, setLoadErr] = useState(null)   // SET-06: a failed GET /settings
  const [narrow, setNarrow] = useState(false)    // SET-11: stack rows when the pane is tight
  const scrollRef = useRef(null)
  const timers = useRef([])
  const flashTimer = useRef(null)
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
      setLoadErr(null)
    } catch (e) {
      console.error(e)
      setLoadErr(e?.response?.data?.detail || e?.message || 'The server did not answer.')
    }
  }, [])

  // SET-11: the row is label(340) + gap(24) + controls, and the pill + Override
  // toggle on the six LLM rows are both flex:0 0 auto, so below a certain pane
  // width the toggle was simply clipped off the right edge and unreachable.
  // 720px of pane is roughly a 1150px window with the nav rail expanded; below
  // that the label goes above the controls instead of beside them.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width
      if (typeof w === 'number') setNarrow(w < 720)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [!!S])

  useEffect(() => {
    load()
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setResumes(data || [])).catch(() => {})
    api.get('/persona').then(({ data }) => setPersonaAvailable(Object.keys(data?.resume_content || {}).length > 0)).catch(() => {})
    api.get('/linkedin/session').then(({ data }) => setLi(data)).catch(() => {})
  }, [load])

  // one timer, not one per flash: two saves inside 2.2 s used to leave the
  // first flash's timer running, which cleared the second message early
  const flash = (msg, bad = false) => {
    setToast({ msg, bad })
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setToast(null), 2200)
    timers.current.push(flashTimer.current)
  }

  // returns whether the PATCH landed, so callers with side effects of their own
  // (ApiKeyRow writes localStorage + refreshes the session cookie) can bail out
  const save = useCallback(async (key, value) => {
    // SET-06: never PATCH from a pane that never loaded — a blur would write a
    // control's placeholder over the real stored value.
    if (!S) { flash('Settings are not loaded yet', true); return false }
    const prev = S[key]
    setS((p) => ({ ...p, [key]: value }))
    try {
      const { data } = await api.patch('/settings', { [key]: value })
      // SET-27: the row is stored either way, but a failed side effect (the
      // scheduler, the scoring semaphore, the dedup reload) comes back as a
      // warning — a green "Saved" over that reads as if nothing went wrong
      const w = Array.isArray(data?.warnings) ? data.warnings.filter(Boolean) : []
      if (w.length) flash(String(w[0]), true)
      else flash('Saved')
      return true
    } catch (e) {
      console.error(e)
      // SET-08: the optimistic value stayed on screen after a failed PATCH, so
      // the UI disagreed with the server until a reload — put the old one back
      setS((p) => { const n = { ...p }; if (prev === undefined) delete n[key]; else n[key] = prev; return n })
      flash('Could not save — try again', true)
      return false
    }
  }, [S])

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

    // Default voice has to name an id from the presets, so offer exactly those
    // rather than a free-text box you can typo. A stored id that no longer
    // exists is kept as an option so the row doesn't silently read as unset.
    let vp = S.cover_letter_voice_presets
    if (typeof vp === 'string') { try { vp = JSON.parse(vp) } catch { vp = [] } }
    const voiceOpts = (Array.isArray(vp) ? vp : []).filter((v) => v && v.id).map((v) => [v.id, v.label || v.id])
    const curVoice = S.cover_letter_default_voice
    if (curVoice && !voiceOpts.some((o) => o[0] === curVoice)) voiceOpts.push([curVoice, `${curVoice} — not in presets`])

    return [
      ['models', 'AI', 'Models', 'each individual prompt can be run against different model, if needed', [
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
        { kind: 'models', label: 'Model catalog', help: 'Add new or unlisted models and remove your additions.',
          info: 'For models newer than the seeded list. The add search hits the provider’s live catalog for OpenRouter, OpenAI and Claude; Ollama has no catalog — enter the local model name. Removals persist.' },
      ]],
      ['scoring', '', 'Scoring behavior', 'which résumé gets scored, how deep, and when it runs', [
        SEL('Default résumé', 'Used when a company has no résumés of its own selected.', 'default_resume_id', resumeOpts, { w: '260px' }),
        B('Max parallel jobs', 'Extra requests queue — protects the DB pool.', 'scoring_max_concurrent', { mono: true, int: true, w: '135px' }),
        SEL('Default depth', 'Used when neither the company nor the search sets its own.', 'scoring_default_depth',
          [['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '260px', dflt: 'light',
            info: 'Light returns scores + a one-liner (cheap, for high-volume searches). Full adds keyword coverage, requirement mapping and a written report. Companies and Searches can each override this per config.' }),
        SEL('On save action', 'Score a job once you save it on the feed, if yet unscored.', 'on_save_action',
          [['off', "Off — don't score on save"], ['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '260px', dflt: 'off' }),
        SW('Prompt caching', 'Rubric + résumés + schema sent as a cached block — ~10× cheaper input tokens on repeat calls.', 'Disabled — full price per call.', 'prompt_caching_enabled',
          { dflt: true, info: 'Only active when the effective provider is claude_api — no effect with Claude Code, Ollama or OpenRouter. If scoring output ever looks stale after a rubric edit, disable this as a rollback lever, run once, re-enable.' }),
        E('Scoring rubric', 'The instruction block every scoring call starts from.', 'scoring_rubric', { sub: 'placeholders stay literal — replaced at runtime' }),
        E('Light output schema', 'JSON shape for Light runs.', 'scoring_output_light', { sub: 'CV_NAMES_HERE expands to your résumé names' }),
        E('Full output schema', 'JSON shape for Full runs.', 'scoring_output_full', { sub: 'CV_NAMES_HERE expands to your résumé names' }),
      ]],
      ['tailoring', '', 'Tailoring', 'AI-rewritten résumés', [
        E('Résumé tailoring prompt', 'Default: rewrites only bullets that benefit.', 'cv_tailor_prompt', { sub: 'placeholders: {job_description} {resume_json}' }),
        E('Persona tailoring prompt', 'Default: selection from Persona’s richer pool, falls back to the résumé prompt if empty.', 'persona_tailor_prompt', { sub: 'placeholders: {job_description} {persona_json}' }),
        B('Max parallel tailors', 'Tailoring and cover-letter generation share this limit.', 'tailoring_max_concurrent', { mono: true, int: true, w: '135px' }),
        SEL('Auto-score after tailoring', 'Rescores tailored resume when the tailor finishes.', 'tailor_auto_quick_score',
          [['off', "Off — don't score after tailoring"], ['light', 'Light — score only'], ['full', 'Full — score + keywords + report']], { w: '260px', dflt: 'light' }),
      ]],
      ['letters', '', 'Cover letters', 'AI-written based on Persona or résumé', [
        SEL('Default voice', 'The list comes from the voice presets below.', 'cover_letter_default_voice', voiceOpts, { w: '260px' }),
        E('Voice presets', 'Label + prompt per voice, can be expanded.', 'cover_letter_voice_presets', { json: true, sub: 'JSON — id, label, instruction per voice' }),
        E('Cover letter prompt', 'The generation instruction.', 'cover_letter_prompt', { sub: 'placeholders: {voice_instruction} {length_instruction} {job_description}' }),
      ]],
      ['autofill', '', 'Autofill', 'used by the Chrome extension on ATS forms', [
        B('Default answer length', 'Target length for form answers, in characters.', 'autofill_default_length', { mono: true, int: true, w: '135px' }),
        E('Autofill prompt', 'Answers as the candidate, from Persona autofill content only.', 'autofill_prompt', { sub: 'placeholders: {persona} {qa_bank} {company} {position} {question} {max_chars}' }),
        E('Field patterns', 'Maps form-field names to Persona fields.', 'autofill_field_patterns', { json: true, sub: 'JSON — Persona field → name patterns' }),
        E('Option synonyms', 'Normalises dropdown options.', 'autofill_option_synonyms', { json: true, sub: 'JSON — canonical option → synonyms' }),
      ]],
      ['prep', '', 'Interview prep', 'the handover bundle Applications exports for your LLM of choice', [
        E('"What I need from you" section', 'The hardcoded ask appended to the handover.', 'prep_ask', { sub: 'plain text, no placeholders' }),
        SEL('Include by default', 'Sections the handover carries. Ask is always included.', 'prep_include',
          [['resume,posting,notes', 'Résumé · posting · notes'], ['resume,posting', 'Résumé · posting'],
            ['posting,notes', 'Posting · notes'], ['resume', 'Résumé only'], ['posting', 'Posting only']], { w: '260px', dflt: 'resume,posting,notes' }),
      ]],
      ['emailclass', '', 'Email classification', 'reads Gmail replies', [
        SW('LLM classification', 'Replies are auto-classified into interview / rejection / offer and attached to the right application.', 'Disabled — replies only show as raw snippets.', 'email_llm_enabled'),
        B('Confidence threshold', '0–100 — below this, the email is flagged for manual review instead.', 'email_llm_confidence_threshold', { mono: true, int: true, w: '135px' }),
        E('Classification prompt', 'Labels + confidence + application hint.', 'email_llm_prompt', { sub: 'placeholders: {applications} {from} {subject} {body}' }),
        E('Gmail query · subjects', 'Subject terms the Gmail poll searches for.', 'email_gmail_query_subjects', { list: true, sub: 'one term per line · OR-combined in the Gmail query' }),
        E('Gmail query · senders', 'Additional known sender domains check.', 'email_gmail_query_senders', { list: true, sub: 'one domain per line' }),
        E('Gmail query · exclusions', 'Exclusion of newsletters and job-alert spam.', 'email_gmail_query_exclusions', { list: true, sub: 'one term per line · appended as -term' }),
      ]],
      ['scheduler', 'PIPELINE', 'Scheduler', 'intervals in minutes (0 = off) · crons empty = off', [
        B('Scrape all companies', 'Runs every active company scrape on this interval.', 'scrape_interval_minutes', { mono: true, int: true, w: '135px' }),
        B('Email check', 'Polls Gmail for replies to your applications.', 'email_check_interval_minutes', { mono: true, int: true, w: '135px' }),
        B('Cleanup after', 'Days before ignored and skipped job postings are removed.', 'job_archive_after_days', { mono: true, int: true, w: '135px' }),
        B('Auto-reject threshold', 'Days of silence before an application is auto-moved to Rejected.', 'auto_reject_after_days', { mono: true, int: true, w: '135px',
          info: 'Counts from the last activity on the application (stage change, email, note). Auto-rejected applications keep their history and stay in the Stats funnel — nothing is deleted.' }),
        B('Auto-reject · cron', 'Applies the auto-reject threshold.', 'reject_cron', { mono: true, cron: true, w: '135px' }),
		B('DB backup · cron', 'Database snapshot.', 'backup_cron', { mono: true, cron: true, w: '135px' }),
        B('Telegram digest · cron', 'Summary of new high-fit jobs.', 'digest_cron', { mono: true, cron: true, w: '135px' }),
        B('H-1B refresh · cron', 'Re-imports and re-scans the sponsorship dataset.', 'h1b_cron', { mono: true, cron: true, w: '135px' }),
        B('Job cleanup · cron', 'Purges expired postings.', 'cleanup_cron', { mono: true, cron: true, w: '135px' }),        
      ]],
      ['exclude', '', 'Global exclude', 'titles, companies and body phrases dropped before anything else runs', [
        E('Body phrases', 'Exclusion of postings whose description matches any phrase from this list.', 'body_exclusion_phrases', { list: true, sub: 'one phrase per line · case-insensitive' }),
        E('Title exclude', 'Exclusion of the job title matches.', 'title_exclude_global', { list: true, sub: 'one phrase per line · case-insensitive' }),
        E('Company exclude', 'Exclusion of exact company names', 'company_exclude_global', { list: true, sub: 'one company per line · exact match' }),
      ]],
      ['dedup', '', 'Dedup tracking params', "so the same job from two sources isn't saved twice", [
        E('Stripped params', 'Query params removed from job URLs. All utm_* are always stripped.', 'dedup_tracking_params', { list: true, sub: 'one param per line' }),
      ]],
      ['notifications', 'INTEGRATIONS', 'Notifications', 'Telegram bot · digest schedule lives under Scheduler', [
        SW('Telegram', 'High-fit arrivals and the daily digest go to your chat.', 'Off — no push notifications.', 'telegram_enabled'),
        B('Chat ID', 'Your Telegram chat — get it by messaging @userinfobot.', 'telegram_chat_id', { mono: true, w: '135px' }),
        B('Score threshold', 'Only jobs scoring at or above this trigger an instant alert.', 'fit_score_threshold', { mono: true, int: true, w: '135px' }),
        BT('Test', 'Confirms the bot token and chat ID work end to end.', 'Send test message', () => api.post('/telegram/test')),
        { kind: 'button', label: 'Webhook secret', help: 'Optional — alerts and the digest work without a webhook. Validates every Telegram → backend call.',
          btnLabel: 'Rotate', previewBox: '260px',
          preview: S.telegram_webhook_secret === MASK ? 'Set (hidden — rotate to view)' : (S.telegram_webhook_secret ? 'Set' : 'Not set'),
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
          // local failures carry `error`, Telegram's own carry `description`
          const failed = data?.ok === false
          flash(failed ? (data.description || data.error || 'Registration failed') : 'Webhook registered', failed)
        }),
      ]],
      ['tracer', '', 'Tracer links', 'per-application link click tracking', [
        SW('Rewrite links', 'Résumé and letter links route through your domain.', 'Off — documents keep their original links.', 'tracer_links_enabled',
          { info: 'Each application gets its own short link per document link. When a recruiter opens one, the hit lands in Stats against that application.' }),
        B('Base URL', 'Your tracer domain.', 'tracer_links_base_url', { mono: true, w: '260px', placeholder: 'https://yourdomain.com' }),
        SEL('URL style', 'Your domain needs to support selected style.', 'tracer_links_url_style',
          [['path', 'Path + random (/cv/a7x2kp)'], ['param', 'Param + random (?cv=a7x2kp)'],
            ['path_jobid', 'Path + job ID (/cv/142li)'], ['param_jobid', 'Param + job ID (?cv=142li)']], { w: '260px', dflt: 'path' }),
      ]],
      ['jobright', '', 'Jobright.ai', 'credentials for the Jobright search mode', [
        B('Email', 'Your Jobright account.', 'jobright_email', { w: '260px' }),
        B('Password', 'Stored locally.', 'jobright_password', { secret: true, w: '260px' }),
      ]],
      ['linkedin', '', 'LinkedIn', "personal scraping + the extension's separate mock account", [
        B('Personal email', 'Used by LinkedIn Personal collections.', 'linkedin_email', { w: '260px' }),
        B('Personal password', 'Stored locally.', 'linkedin_password', { secret: true, w: '260px' }),
        { kind: 'linkedin', label: 'Session cookie', help: 'The extension import reuses a signed-in cookie. LinkedIn gates the login behind an emailed PIN.' },
        B('Mock account email', 'The extension browses specific jobs with this mock account.', 'linkedin_mock_email', { w: '260px',
          info: 'Capture happens while the extension browses LinkedIn collections. Doing that on a throwaway account means rate limits, CAPTCHAs or bans hit the mock identity — never your real profile.' }),
        B('Mock account password', 'Stored locally only.', 'linkedin_mock_password', { secret: true, w: '260px' }),
      ]],
      ['advanced', 'SYSTEM', 'Advanced', 'escape hatches — most days none of this gets touched', [
        B('Proxy URL', 'Used by scrapes that hit rate limits or geo-blocks. Empty = direct.', 'proxy_url', { mono: true, w: '340px', placeholder: 'socks5://127.0.0.1:9050' }),
        { kind: 'apikey', label: 'Dashboard API key', help: 'Saving refreshes the session cookie so iframes keep working.' },
        BT('DB backup', 'DB snapshot now, outside the cron.', 'Run backup', () => api.post('/db/backup')),
      ]],
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [S, resumes, personaAvailable, trig, li])

  const q = query.trim().toLowerCase()
  const matches = (sec) => !q || sec[2].toLowerCase().includes(q) ||
    sec[4].some((r) => `${r.label} ${r.help || ''}`.toLowerCase().includes(q))
  const visible = sections.filter(matches)

  // SET-06: a failed load used to render an empty pane identical to the loading
  // state, so a hard failure and a hung request were indistinguishable.
  if (!S) return (
    <div style={{ flex: 1, minWidth: 0, background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {loadErr ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '44px 30px' }}>
          <span style={{ fontSize: 13, color: 'var(--bad)' }}>Couldn’t load your settings</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{loadErr}</span>
          <span onClick={() => { setLoadErr(null); load() }} style={{ fontSize: 11.5, color: 'var(--accent)', fontWeight: 500, cursor: 'pointer', paddingTop: 2 }}>Try again</span>
        </div>
      ) : (
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--muted)' }}>
          <span className="v2-spin" style={{ width: 10, height: 10, border: '1.5px solid var(--muted)', borderTopColor: 'transparent', borderRadius: 99 }} />Loading settings…
        </span>
      )}
    </div>
  )

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
              <div onClick={() => jump(id)} {...kb(() => jump(id), 'link')} aria-label={`Jump to ${title}`} className="v2-anchor" style={{ display: 'flex', alignItems: 'center', height: 29, padding: '0 26px 0 29px', fontSize: 12.5, cursor: 'pointer',
                color: active === id && !q ? 'var(--text)' : 'var(--text-2)', fontWeight: active === id && !q ? 600 : 400,
                /* 3px accent + 29px pad keeps the label on the same axis as the 2px version */
                borderLeft: `3px solid ${active === id && !q ? 'var(--accent)' : 'transparent'}` }}>{title}</div>
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
                  <Row key={r.label} r={r} ctx={{ S, val, isOn, save, info, setInfo, ovr, setOvr, trig, runAction, setEditFor, setModelsOpen, modelsFor, li, setLi, flash, defaults, narrow }} />
                ))}
              </div>
            ))}
            {visible.length === 0 && (
              <div style={{ padding: '44px 0', fontSize: 12.5, color: 'var(--muted)' }}>No settings match “{query}”.</div>
            )}

            {/* colophon — API docs lives here now rather than in the nav rail.
                SET-13: --edge as 11px body text is 3.69:1 on --bg (3.95:1 dark),
                under AA; --muted clears it at 5.5:1 / 6.2:1 with the same tone. */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '34px 0 6px', fontSize: 11, lineHeight: '16px', color: 'var(--muted)' }}>
              <span style={{ fontStyle: 'italic' }}>
                <span style={{ color: 'var(--muted)', fontFamily: 'var(--serif)', fontSize: 12, fontStyle: 'normal' }}>JobNavigator</span>&nbsp;v.2.0
              </span>
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 14 }}>
                <a href="/docs" target="_blank" rel="noopener noreferrer" className="v2-hover-accent-text"
                  style={{ color: 'var(--muted)', textDecoration: 'none', cursor: 'pointer' }}>API docs ↗</a>
                <a href="https://github.com/vesaias/JobNavigator" target="_blank" rel="noopener noreferrer" className="v2-hover-accent-text"
                  style={{ color: 'var(--muted)', textDecoration: 'none' }}>github.com/vesaias/JobNavigator ↗</a>
              </span>
            </div>
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
  const { val, isOn, save, info, setInfo, ovr, setOvr, trig, runAction, setEditFor, setModelsOpen, modelsFor, li, setLi, flash, S, narrow } = ctx
  const infoOpen = r.info && info === r.label

  const right = (() => {
    switch (r.kind) {
      case 'box':
        return <TextBox value={val(r.key)} onSave={(v) => save(r.key, v)} width={r.w} mono={r.mono} secret={r.secret} placeholder={r.placeholder}
          ariaLabel={r.label} int={r.int} cron={r.cron} onInvalid={(m) => flash(m, true)} />
      case 'select':
        return <Select value={val(r.key, r.dflt)} options={r.options} onPick={(v) => save(r.key, v)} width={r.w} ariaLabel={r.label} />
      case 'switch': {
        const on = isOn(r.key, r.dflt)
        return <Toggle on={on} label={on ? 'On' : 'Off'} onPick={() => save(r.key, on ? 'false' : 'true')} ariaLabel={r.label} />
      }
      case 'pair': {
        const p = val(r.pKey, 'claude_api')
        return (
          <>
            <Select value={p} options={PROVIDERS} onPick={(v) => save(r.pKey, v)} width="220px" ariaLabel={`${r.label} — provider`} />
            <Select value={val(r.mKey)} options={modelsFor(p)} onPick={(v) => save(r.mKey, v)} width="260px" mono placeholder="pick model…" ariaLabel={`${r.label} — model`} />
          </>
        )
      }
      case 'llm': {
        const on = !!ovr[r.base]
        const p = val(`${r.base}_provider`)
        return (
          <>
            {on && <Select value={p} options={PROVIDERS} onPick={(v) => save(`${r.base}_provider`, v)} width="200px" placeholder="pick provider…" ariaLabel={`${r.label} — provider`} />}
            {on && <Select value={val(`${r.base}_model`)} options={modelsFor(p || val('llm_provider', 'claude_api'))} onPick={(v) => save(`${r.base}_model`, v)} width="260px" mono placeholder="pick model…" ariaLabel={`${r.label} — model`} />}
            {on && p && !KEYLESS.includes(p) && (
              <span title="API key for this override's provider" style={{ display: 'flex', flex: '0 1 150px', minWidth: 0 }}>
                <TextBox value={val(`${r.base}_api_key`)} onSave={(v) => save(`${r.base}_api_key`, v)} width="150px" mono secret ariaLabel={`${r.label} — API key`} />
              </span>
            )}
            {!on && <span style={{ fontSize: 9.5, lineHeight: '14px', letterSpacing: '.06em', textTransform: 'uppercase', padding: '1px 7px', borderRadius: 99, background: 'var(--surface-2)', color: 'var(--muted)', whiteSpace: 'nowrap' }}>inherits Primary</span>}
            <span style={{ marginLeft: 'auto' }}>
              <Toggle on={on} label="Override" ariaLabel={`${r.label} — override the Primary model`} onPick={async () => {
                const next = !on
                setOvr((o) => ({ ...o, [r.base]: next }))
                if (!next) {
                  // SET-08: `ovr` is local state the PATCHes don't own, so if
                  // either clear fails the row has to reopen — otherwise it reads
                  // as "inherits Primary" while the server still holds an override
                  const a = await save(`${r.base}_provider`, '')
                  const b = a && await save(`${r.base}_model`, '')
                  if (!a || !b) setOvr((o) => ({ ...o, [r.base]: true }))
                }
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
            <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{preview || '—'}</span>
            <span onClick={() => setEditFor(r)} {...kb(() => setEditFor(r))} aria-label={`Edit ${r.label}`} className="v2-bdc" style={{ flex: '0 0 auto', height: 26, padding: '0 12px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 11.5, color: 'var(--text-2)', cursor: 'pointer' }}>Edit</span>
          </>
        )
      }
      case 'models':
        return (
          <>
            <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {(() => { let m = S.llm_models_list; if (typeof m === 'string') { try { m = JSON.parse(m) } catch { m = [] } } m = Array.isArray(m) ? m : []
                const c = m.filter((x) => x.custom).length
                return `${m.length} models · ${m.length - c} seeded · ${c} added by you` })()}
            </span>
            <ActionBtn label="Manage…" state="" onClick={() => setModelsOpen(true)} ariaLabel={`${r.label} — manage`} />
          </>
        )
      case 'button':
        return (
          <>
            {/* SET-22: the webhook secret is a value, not a run summary, so the
                design puts it in the same bordered box every other value uses */}
            {r.preview && (r.previewBox
              ? <span style={{ ...BOX, flex: `0 1 ${r.previewBox}`, cursor: 'default' }}>
                  <span style={{ minWidth: 0, fontFamily: 'var(--mono)', fontSize: 11.5, lineHeight: '16px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.preview}</span>
                </span>
              : <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.preview}</span>)}
            <ActionBtn label={r.btnLabel} state={trig[r.label] || ''} onClick={() => runAction(r.label, r.act)} ariaLabel={`${r.label} — ${r.btnLabel}`} />
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
    // SET-11: the label column shrinks rather than holding a hard 340px, and
    // below ~720px of pane it moves above the controls entirely — otherwise the
    // pill + Override toggle on the LLM rows are clipped off the right edge.
    <div style={{ display: 'flex', flexDirection: narrow ? 'column' : 'row', alignItems: narrow ? 'stretch' : 'center', gap: narrow ? 10 : 24, minHeight: 52, padding: '9px 0', borderBottom: '1px solid var(--line-soft)' }}>
      <div style={{ flex: narrow ? '0 0 auto' : '0 1 340px', minWidth: narrow ? 0 : 200, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, lineHeight: '18px', fontWeight: 500 }}>
          {r.label}
          {r.info && (
            <span onClick={() => setInfo(infoOpen ? null : r.label)} {...kb(() => setInfo(infoOpen ? null : r.label))}
              aria-label={`More detail about ${r.label}`} aria-expanded={!!infoOpen} title="More detail"
              style={{ width: 15, height: 15, flex: '0 0 auto', border: `1px solid ${infoOpen ? 'var(--accent)' : 'var(--edge)'}`, background: infoOpen ? 'var(--accent-soft)' : 'var(--surface)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 400, color: infoOpen ? 'var(--accent)' : 'var(--muted)', cursor: 'pointer', fontFamily: 'var(--serif)', fontStyle: 'italic' }}>
              {/* the italic serif 'i' has no descender and slants right, so flex
                  centring leaves its ink high and right of the circle's centre */}
              <span style={{ display: 'block', transform: 'translate(-0.9px, 1.4px)' }}>i</span>
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
      <div style={{ flex: narrow ? '0 0 auto' : 1, minWidth: 0, display: 'flex', alignItems: 'center', flexWrap: narrow ? 'wrap' : 'nowrap', gap: 8 }}>{right}</div>
    </div>
  )
}

function ActionBtn({ label, state, onClick, ariaLabel }) {
  const done = state === 'done'
  return (
    <span onClick={onClick} {...kb(onClick)} aria-label={ariaLabel || label} className="v2-bd v2-ctl" style={{ flex: '0 0 auto', height: 30, padding: '0 14px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, whiteSpace: 'nowrap', cursor: 'pointer',
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
          aria-label="Dashboard API key"
          placeholder={isSet ? 'Set — type a new key to replace it' : 'No key — the dashboard is open'}
          style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)' }} />
        <span onClick={() => setShown((v) => !v)} {...kb(() => setShown((v) => !v))} aria-label={`${shown ? 'Hide' : 'Show'} the dashboard API key`}
          style={{ fontSize: 10.5, lineHeight: '16px', color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap' }}>{shown ? 'hide' : 'show'}</span>
      </span>
      <ActionBtn label="Save key" state="" ariaLabel="Save the dashboard API key" onClick={async () => {
        if (!local.trim()) { flash('Type the new key first', true); return }
        // if the PATCH failed, writing the key locally would lock the dashboard
        // out on the next request — stop before touching localStorage
        const saved = await save('dashboard_api_key', local.trim())
        if (!saved) return
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
            <input value={pin} onChange={(e) => setPin(e.target.value)} placeholder="6-digit PIN" inputMode="numeric" aria-label="LinkedIn sign-in PIN"
              style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)' }} />
          </span>
          <ActionBtn label="Submit PIN" state="" onClick={async () => {
            try {
              const { data } = await api.post('/linkedin/session/pin', { pin })
              if (!data.ok) flash(data.detail || 'Enter the digits from the email', true)
              else { setPin(''); flash('PIN sent') }
            } catch (e) { flash(e?.response?.data?.detail || 'Could not send the PIN', true) }
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
  const pending = useRef(null)   // SET-25: the value the 600ms timer still owes

  const write = (value) => {
    if (spec.list) { onSave(spec.key, value.split('\n').map((x) => x.trim()).filter(Boolean)); setErr(''); return }
    if (spec.json) {
      try { onSave(spec.key, JSON.parse(value)); setErr('') }
      catch { setErr('Not valid JSON — nothing saved yet') }
      return
    }
    onSave(spec.key, value); setErr('')
  }

  const commit = (value) => {
    pending.current = value
    clearTimeout(timer.current)
    timer.current = setTimeout(() => { pending.current = null; write(value) }, 600)
  }

  // SET-25: unmount used to just drop the pending timer, so anything typed in
  // the last 600ms was silently lost even though the footer promises it saves
  // as you type. Every exit runs through close(), which flushes first.
  const flush = () => {
    clearTimeout(timer.current)
    if (pending.current !== null) { const v = pending.current; pending.current = null; write(v) }
  }
  const close = () => { flush(); onClose() }

  const reset = () => {
    // /settings/defaults returns the raw seed *strings*, so a list key arrives
    // as '["a","b"]'. Feeding that to asList() made one line, which committed
    // as a single-element list containing JSON text.
    let d = defaults[spec.key]
    if (d === undefined) { setErr('Defaults are unavailable — nothing was reset'); return }
    if ((spec.list || spec.json) && typeof d === 'string') {
      try { d = JSON.parse(d) } catch { /* not JSON after all — use the raw string */ }
    }
    const t = spec.list ? asList(d) : spec.json ? asJson(d) : String(d ?? '')
    setText(t); commit(t)
  }

  const closeRef = useRef(close)
  const flushRef = useRef(flush)
  closeRef.current = close
  flushRef.current = flush
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeRef.current() }
    document.addEventListener('keydown', onKey)
    // flush, not close, on unmount: close() has already run for every in-modal
    // exit, and this catches an unmount driven from outside the modal
    return () => { document.removeEventListener('keydown', onKey); flushRef.current() }
  }, [])

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--scrim)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={close}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(1020px, 94vw)', maxHeight: 'min(1280px, 92vh)', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>{spec.label}</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{spec.sub || ''}</span>
          <div onClick={close} {...kb(close)} aria-label={`Close ${spec.label}`} className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '16px 22px', minHeight: 0, display: 'flex' }}>
          {/* 1.5x wider and 2x taller than before, capped so it never exceeds the window */}
          <textarea value={text} onChange={(e) => { setText(e.target.value); commit(e.target.value) }} aria-label={spec.label}
            style={{ flex: 1, width: '100%', minHeight: 440, padding: '12px 14px', border: `1px solid ${err ? 'var(--bad)' : 'var(--edge)'}`, borderRadius: 8, background: 'var(--surface)', fontFamily: 'var(--mono)', fontSize: 11.5, lineHeight: '20px', color: 'var(--text)', outline: 'none', resize: 'vertical' }} />
        </div>
        <div style={{ flex: '0 0 auto', padding: '11px 22px', borderTop: '1px solid var(--line)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontSize: 11.5, color: err ? 'var(--bad)' : 'var(--muted)' }}>{err || 'Saves automatically as you type'}</span>
          <div onClick={reset} {...kb(reset)} aria-label={`Reset ${spec.label} to default`} className="v2-bdc" style={{ marginLeft: 'auto', height: 31, padding: '0 13px', border: '1px solid var(--edge)', borderRadius: 99, background: 'var(--surface)', display: 'flex', alignItems: 'center', fontSize: 12, color: 'var(--text-2)', cursor: 'pointer' }}>Reset to default</div>
          <div onClick={close} {...kb(close)} aria-label={`Done editing ${spec.label}`} style={{ height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Done</div>
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

  // SET-16: the design anchors the typeahead under the field as a dropdown with
  // the first row pre-highlighted, the matched substring bolded and an "N of M
  // match" footer — not a plain list stacked above the catalog rows.
  const [hi, setHi] = useState(0)
  const [sugOpen, setSugOpen] = useState(true)
  const { matched, suggestions } = useMemo(() => {
    const t = term.trim().toLowerCase()
    const names = live.map((m) => (typeof m === 'string' ? m : (m.id || m.model || ''))).filter(Boolean)
    const hits = t ? names.filter((n) => n.toLowerCase().includes(t)) : names
    return { matched: hits.length, suggestions: hits.slice(0, 8) }
  }, [live, term])
  useEffect(() => { setHi(0); setSugOpen(true) }, [term])
  const showSug = !!term.trim() && sugOpen && suggestions.length > 0

  // bold every occurrence of the typed term, the way the design draws it
  const mark = (name) => {
    const t = term.trim()
    if (!t) return name
    const parts = []
    const lower = name.toLowerCase(); const lt = t.toLowerCase()
    let i = 0, k = 0
    for (;;) {
      const at = lower.indexOf(lt, i)
      if (at < 0) { parts.push(name.slice(i)); break }
      if (at > i) parts.push(name.slice(i, at))
      parts.push(<b key={k++}>{name.slice(at, at + t.length)}</b>)
      i = at + t.length
    }
    return parts
  }

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
      <div onClick={(e) => e.stopPropagation()} style={{ width: 600, maxHeight: 620, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12, boxShadow: 'var(--shadow-modal)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: '0 0 auto', padding: '15px 22px 12px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-.02em' }}>Model catalog</span>
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>available in every model picker</span>
          <div onClick={onClose} {...kb(onClose)} aria-label="Close the model catalog" className="v2-hover-accent" style={{ marginLeft: 'auto', width: 26, height: 26, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>✕</div>
        </div>
        <div style={{ flex: '0 0 auto', padding: '12px 22px', borderBottom: '1px solid var(--line-soft)', background: 'var(--bg)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Select value={provider} options={PROVIDERS} onPick={setProvider} width="150px" ariaLabel="Catalog provider" emptyText="no providers" />
          <span style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex' }}>
            <span style={{ ...BOX, flex: 1, height: 31 }}>
              <input value={term} onChange={(e) => setTerm(e.target.value)} aria-label="Search the model catalog"
                aria-expanded={showSug} aria-autocomplete="list"
                onKeyDown={(e) => {
                  if (e.key === 'ArrowDown' && showSug) { e.preventDefault(); setHi((i) => (i + 1) % suggestions.length); return }
                  if (e.key === 'ArrowUp' && showSug) { e.preventDefault(); setHi((i) => (i - 1 + suggestions.length) % suggestions.length); return }
                  if (e.key === 'Escape' && showSug) { e.preventDefault(); setSugOpen(false); return }
                  if (e.key === 'Enter') { e.preventDefault(); add(showSug ? suggestions[hi] : undefined) }
                }}
                placeholder={SEARCHABLE.includes(provider)
                  ? (loading ? 'Loading live models…' : `Search ${live.length} live models, or paste any slug…`)
                  : 'Enter the local model name…'}
                style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--text)' }} />
            </span>
            {showSug && (
              <div role="listbox" style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20, marginTop: 4, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, boxShadow: 'var(--shadow-menu)', padding: 4, display: 'flex', flexDirection: 'column' }}>
                {suggestions.map((n, i) => (
                  <div key={n} className={i === hi ? '' : 'v2-menuitem'} role="option" aria-selected={i === hi}
                    onMouseEnter={() => setHi(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => add(n)}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 9px', borderRadius: 5, cursor: 'pointer', background: i === hi ? 'var(--accent-soft)' : 'transparent' }}>
                    <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 11, lineHeight: '16px', color: i === hi ? 'var(--text)' : 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{mark(n)}</span>
                    {i === hi && <span style={{ flex: '0 0 auto', fontSize: 10, lineHeight: '16px', color: 'var(--accent)' }}>↵ to add</span>}
                  </div>
                ))}
                <div style={{ display: 'flex', alignItems: 'center', padding: '5px 9px', borderTop: '1px solid var(--line-soft)', marginTop: 3, fontSize: 10.5, lineHeight: '16px', color: 'var(--muted)' }}>
                  {matched} of {live.length} match · or paste any slug and Add
                </div>
              </div>
            )}
          </span>
          <div onClick={() => add()} {...kb(() => add())} aria-label="Add this model to the catalog" className="v2-ctl" style={{ flex: '0 0 auto', height: 31, padding: '0 15px', borderRadius: 99, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Add</div>
        </div>
        {err && <div style={{ padding: '8px 22px', fontSize: 11.5, color: 'var(--bad)' }}>{err}</div>}
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: '6px 22px 14px' }}>
          {list.map((m) => (
            <div key={`${m.provider}/${m.model}`} style={{ display: 'flex', alignItems: 'center', gap: 10, height: 36, borderBottom: '1px solid var(--line-soft)' }}>
              {/* SET-13: --edge at 10px is under 4.5:1 on --surface in both themes */}
              <span style={{ flex: '0 0 92px', fontFamily: 'var(--mono)', fontSize: 10, lineHeight: '16px', color: 'var(--muted)' }}>{m.provider}</span>
              <span style={{ flex: 1, minWidth: 0, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.model}</span>
              <span style={{ flex: '0 0 auto', fontSize: 10, lineHeight: '16px', color: m.custom ? 'var(--accent)' : 'var(--muted)' }}>{m.custom ? 'added by you' : 'seeded'}</span>
              {/* SET-15: the design turns the border --bad on hover too, not just the glyph */}
              <span onClick={() => remove(m)} {...kb(() => remove(m))} aria-label={`Remove ${m.model} from ${PROVIDER_LABEL[m.provider] || m.provider}`}
                title="Remove — removal persists" className="v2-hover-bad-bdc"
                style={{ width: 22, height: 22, border: '1px solid var(--line)', borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--edge)', cursor: 'pointer', flex: '0 0 auto' }}>×</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
