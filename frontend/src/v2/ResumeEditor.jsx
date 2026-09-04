import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import './theme.css'
import { useToasts, ToastStack } from './Toast'
import ConfirmDialog from './ConfirmDialog'
import { useEscape, setFlashToast, fetchRunOutcome, runFailed, runFailureReason, useSettled, NBSP } from './hooks'
import { useTitle } from '../useTitle'
// The résumé-content editors are shared with /v2/persona (a Persona's
// resume_content is the same shape as a Resume's json_data).
import {
  EMPTY, SECTION_ORDER, sectionCounts, makeMutators,
  SectionShell, SectionEditor, BandRule,
} from './ResumeSections'
import { Band, Button, Check, ChoiceCard, ChoiceModal, ChoiceRow, Heading, HeaderRow, Helper, IconButton, Input, Label, Menu, MenuHead, MenuItem, ModalPanel, NavLink, Pill, Rule, ScoreRing, Spinner, Surface, Textarea } from './ui'

// contiguous prefix/suffix word diff → { before, removed, added, after } (matches the design's model)
function wordDiff(a = '', b = '') {
  a = a || ''; b = b || ''
  if (a === b) return null
  const aw = a.split(' '), bw = b.split(' ')
  let p = 0
  while (p < aw.length && p < bw.length && aw[p] === bw[p]) p++
  let sa = aw.length, sb = bw.length
  while (sa > p && sb > p && aw[sa - 1] === bw[sb - 1]) { sa--; sb-- }
  const before = aw.slice(0, p).join(' ')
  return {
    before: before ? before + ' ' : '',
    removed: aw.slice(p, sa).join(' '),
    added: bw.slice(p, sb).join(' '),
    after: sa < aw.length ? ' ' + aw.slice(sa).join(' ') : '',
  }
}
// changes a tailored copy carries vs its base: modified summary/bullets + added (suggested) bullets
function computeChanges(base, copy) {
  if (!base || !copy) return []
  const out = []
  const sd = wordDiff(base.summary, copy.summary)
  if (sd) out.push({ key: 'summary', where: 'Summary', kind: 'modified', path: 'summary', baseText: base.summary || '', ...sd })
  ;(copy.experience || []).forEach((ce, i) => {
    const be = (base.experience || [])[i] || {}
    const bb = be.bullets || [], cb = ce.bullets || []
    cb.forEach((txt, j) => {
      if (j < bb.length) { const d = wordDiff(bb[j], txt); if (d) out.push({ key: `exp${i}b${j}`, where: `Experience · ${ce.company || 'role'} · bullet ${j + 1}`, kind: 'modified', path: `experience.${i}.bullets.${j}`, baseText: bb[j], ...d }) }
      else out.push({ key: `exp${i}nb${j}`, where: `Experience · ${ce.company || 'role'} · new bullet`, kind: 'added', before: '', removed: '', added: txt, after: '', text: txt })
    })
    ;(ce.suggested_bullets || []).forEach((sb, k) => out.push({ key: `exp${i}sb${k}`, where: `Experience · ${ce.company || 'role'} · suggested bullet`, kind: 'suggested', expIdx: i, sbIdx: k, before: '', removed: '', added: sb, after: '', text: sb }))
  })
  const bs = base.skills || {}, cs = copy.skills || {}
  Object.keys(cs).forEach((cat) => {
    if (!(cat in bs)) out.push({ key: `sk:${cat}`, where: `Skills · ${cat}`, kind: 'added', path: `skills.${cat}`, before: '', removed: '', added: String(cs[cat] || ''), after: '', text: String(cs[cat] || '') })
    else { const d = wordDiff(String(bs[cat] || ''), String(cs[cat] || '')); if (d) out.push({ key: `sk:${cat}`, where: `Skills · ${cat}`, kind: 'modified', path: `skills.${cat}`, baseText: String(bs[cat] || ''), ...d }) }
  })
  return out
}
const timeAgo = (s) => {
  if (!s) return ''
  const m = Math.floor((Date.now() - new Date(s).getTime()) / 60000)
  if (m < 1) return 'just now'; if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── MOVED to ResumeSections.jsx ──────────────────────────────────────────────
// Field, BulletText, MicroField, RemoveLink, DashedAdd, EmptyState, MenuHead,
// MenuItem, UPPER and the seven *Editor sections now live there so
// /v2/persona edits resume_content with the identical components. IconBtn,
// AddLink and normUrl were unreferenced and were dropped rather than moved.
// RES-06: "reviewed" was recomputed from the base-vs-copy diff on every render,
// so every change the user *kept* stayed a diff forever and the "one next step"
// CTA could never leave "Review N changes". Record the acknowledgement instead.
// localStorage rather than a json_data marker: it is a per-user UI
// acknowledgement, needs no backend change, no migration and no extra write on
// a screen that already saves continuously. Promote it to json_data later if it
// has to survive a browser change.
const REVIEWED_KEY = 'jobnavigator_v2_resume_reviewed'
const readReviewed = () => { try { const a = JSON.parse(localStorage.getItem(REVIEWED_KEY)); return Array.isArray(a) ? a : [] } catch { return [] } }
const markReviewed = (rid) => { try { localStorage.setItem(REVIEWED_KEY, JSON.stringify([...readReviewed().filter((x) => x !== rid), rid].slice(-300))) } catch { /* ignore */ } }

export default function ResumeEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [data, setData] = useState(null)
  const [templates, setTemplates] = useState([])
  const [template, setTemplate] = useState('')
  const [format, setFormat] = useState('letter')
  const [savedAt, setSavedAt] = useState(null)
  const [saving, setSaving] = useState(false)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [open, setOpen] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem('jobnavigator_v2_resume_sections')); if (Array.isArray(s)) return new Set(s) } catch { /* ignore */ }
    return new Set(['Experience'])
  })
  const [tplOpen, setTplOpen] = useState(false)
  const [fmtOpen, setFmtOpen] = useState(false)
  const [tailorOpen, setTailorOpen] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewed, setReviewed] = useState(false)   // RES-06: tailoring changes acknowledged for this copy
  const [pdfErr, setPdfErr] = useState(false)      // RES-08: last preview render failed
  const [pdfNonce, setPdfNonce] = useState(0)      // RES-08: Retry re-arms the preview effect
  const [baseData, setBaseData] = useState(null)   // parent json_data (for diff + inline marks)
  const [jobData, setJobData] = useState(null)     // the copy's job (cv_scores, status)
  const [tracers, setTracers] = useState([])
  const [coverExists, setCoverExists] = useState(false)
  const [baseCopyCount, setBaseCopyCount] = useState(null)
  const [scoring, setScoring] = useState(false)
  const [headMenu, setHeadMenu] = useState(false)
  const [confirm, setConfirm] = useState(null)   // RES-16: v2 dialog, not window.confirm
  const [jobErr, setJobErr] = useState(false)   // RES-20: the linked job failed to load
  const [parentName, setParentName] = useState(null)   // R2-H-10: the base this copy came from
  const [tailorChain, setTailorChain] = useState('light')   // R2-H-09: 'light' | 'full' | null
  const saveTimer = useRef(null)
  const pdfTimer = useRef(null)
  const pendingRef = useRef([])   // [{baseId, jobId, company, since}]

  const isCopy = doc && !doc.is_base

  // R3-S-03: the ⋯ head menu (base and copy) closed on its backdrop but not on
  // Escape, while every modal reachable from it already used useEscape (RES-15).
  // Safe to register unconditionally: every item in the menu calls
  // setHeadMenu(false) before it opens a modal, so the menu and a modal are never
  // open at once and the two handlers can't race for one keypress.
  useEscape(() => setHeadMenu(false), headMenu)

  const { toasts, push: pushToast, dismiss: dismissToast } = useToasts()

  // Background tailoring: watch the launched run on /monitor/active by its scope
  // key (`{base}:{job|freeform}` — routes_resumes.py:715) and report when it is gone.
  // RES-26: the old watcher only tracked job-linked tailors, and matched on
  // parent_id + job_id — a persona tailor has parent_id null (routes_resumes.py:776)
  // and a freeform one has no job at all, so neither ever reported completion.
  useEffect(() => {
    const iv = setInterval(async () => {
      if (!pendingRef.current.length) return
      let live
      try { const { data } = await api.get('/monitor/active'); live = (data || []).filter((r) => r.job_type === 'tailor_resume').map((r) => r.scope_key) }
      catch { return }
      const done = []
      pendingRef.current = pendingRef.current.filter((p) => {
        if (live.includes(p.scope)) { p.seen = true; return true }
        if (Date.now() - p.since > 120000) return false            // give up after 2m
        if (!p.seen && Date.now() - p.since < 8000) return true    // not started yet ≠ finished
        done.push(p); return false
      })
      if (!done.length) return
      let list = []
      try { const { data } = await api.get('/resumes', { params: { is_base: false } }); list = data || [] } catch {}
      // DS-B-02: the scope leaving /monitor/active only means the run ENDED. It
      // used to be read as "succeeded", so a tailor that raised in the backend
      // arrived as a green ✓ and the user hunted for a copy that never existed
      // — and 'Tailoring finished.' (the copy-not-found branch) is exactly the
      // failure case. Ask the run for its status and let that pick the toast.
      for (const p of done) {
        const since = p.since - 1000
        const mine = list.filter((r) => new Date(r.updated_at).getTime() >= since)
        // a job-linked run is identified by its job; a freeform one by being the
        // newest job-less copy written since the run started
        const hit = p.jobId
          ? mine.find((r) => String(r.job_id) === String(p.jobId))
          : mine.filter((r) => !r.job_id).sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))[0]
        const run = await fetchRunOutcome(p.runId, 'tailor_resume')
        if (runFailed(run)) {
          pushToast({ kind: 'error', msg: `Tailoring failed — ${runFailureReason(run)}` })
          continue
        }
        const msg = p.company ? `Tailored copy for ${p.company} is ready.` : 'Tailored copy from your pasted description is ready.'
        if (hit) pushToast({ kind: 'success', msg, action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${hit.id}`) })
        else if (run) pushToast({ kind: 'success', msg: 'Tailoring finished.', action: 'Résumés ↗', onAction: () => navigate('/v2/resumes') })
        // run unknown and no copy found: say exactly that rather than claim either way
        else pushToast({ kind: 'progress', spin: false, ttl: 6000, msg: 'Tailoring finished, but the copy could not be located.', action: 'Résumés ↗', onAction: () => navigate('/v2/resumes') })
      }
    }, 3000)
    return () => clearInterval(iv)
  }, [pushToast, navigate])

  const runTailor = useCallback(async ({ baseId, jobId, jobDescription, company }) => {
    setTailorOpen(false)
    try {
      const { data: started } = await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: jobId || undefined, job_description: jobDescription || undefined })
      // DS-B-02: the run_id is what lets the watcher read the run's real status
      pendingRef.current.push({ scope: `${baseId}:${jobId || 'freeform'}`, runId: started?.run_id || null, jobId: jobId || null, company: company || null, since: Date.now() })
      // RES-26: the old string interpolated an empty slot where the company goes
      pushToast({ kind: 'progress', msg: company ? `Tailoring for ${company}… runs in the background.` : 'Tailoring from a pasted description… runs in the background.' })
    } catch (e) {
      if (e.response?.status === 409) pushToast({ kind: 'error', msg: 'Already tailoring for that job.' })
      else pushToast({ kind: 'error', msg: e.response?.data?.detail || 'Tailoring failed to start.' })
    }
  }, [pushToast])

  // Re-tailor keeps this copy's job and swaps what it is built from: either run
  // the tailoring LLM against another base, or take a plain copy of that base
  // (no LLM) purely to get a fresh set of tracer links.
  const runRetailor = useCallback(async ({ mode, baseId }) => {
    setTailorOpen(false)
    const company = jobData?.company || 'this job'
    try {
      if (mode === 'copy') {
        const { data } = await api.post('/resumes/copy', { base_resume_id: baseId, job_id: doc.job_id })
        pushToast({ kind: 'success', msg: `Copy created for ${company}.`, action: 'Open ↗', onAction: () => navigate(`/v2/resumes/${data.id}`) })
      } else {
        const { data: started } = await api.post('/resumes/tailor', { base_resume_id: baseId, job_id: doc.job_id })
        pendingRef.current.push({ scope: `${baseId}:${doc.job_id}`, runId: started?.run_id || null, jobId: doc.job_id, company, since: Date.now() })
        pushToast({ kind: 'progress', msg: `Tailoring for ${company}… runs in the background.` })
      }
    } catch (e) {
      if (e.response?.status === 409) pushToast({ kind: 'error', msg: 'Already tailoring for that job.' })
      else pushToast({ kind: 'error', msg: e.response?.data?.detail || 'Could not start.' })
    }
  }, [doc, jobData, pushToast, navigate])

  // RES-28: each dropdown used to own a fixed backdrop, which swallowed every
  // click — so the other trigger could never be reached and its `set*Open(false)`
  // was dead code. Close on any click outside the two pickers instead (each picker
  // stops its own clicks), and let Escape close them. Escape is marked handled so a
  // modal opened over them can't be closed by the same keypress.
  useEffect(() => {
    if (!tplOpen && !fmtOpen) return undefined
    const close = () => { setTplOpen(false); setFmtOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); close() } }
    document.addEventListener('click', close)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', onKey) }
  }, [tplOpen, fmtOpen])

  useEffect(() => { setReviewed(readReviewed().includes(id)) }, [id])   // RES-06

  useEffect(() => {
    let alive = true
    api.get(`/resumes/${id}`).then(({ data: d }) => {
      if (!alive) return
      setDoc(d); setData(d.json_data || EMPTY); setTemplate(d.template || ''); setFormat(d.page_format || 'letter'); setSavedAt(d.updated_at)
    }).catch((e) => {
      // RES-21: a missing/deleted/malformed id used to land on the shelf silently —
      // indistinguishable from pressing "‹ Résumés". The stack unmounts with this
      // screen, so the message is handed to the shelf instead of pushed here.
      setFlashToast({ kind: 'error', msg: e.response?.status === 404 ? 'That résumé no longer exists.' : 'Couldn’t load that résumé.' })
      navigate('/v2/resumes')
    })
    return () => { alive = false }
  }, [id, navigate])

  // DESIGN-LOAD: the preview toolbar's two pickers wait on this list — without it
  // the Template trigger paints the raw template id and renames itself a moment
  // later. The document already gates the whole screen (`!doc` below), so this is
  // the other half of "document + templates have both settled".
  // OPEN-05: converted — the Layout picker has no options without this, and the
  // user is looking at the editor they just opened.
  const { ready: tplReady } = useSettled([
    () => api.get('/resumes/templates').then(({ data }) => setTemplates(data || [])).catch((e) => { console.error(e); pushToast({ kind: 'error', msg: 'Could not load the layouts — the picker is empty.' }) }),
  ])

  // R2-H-09: a job-linked tailor chains a score of the new copy (routes_resumes.py
  // reads `tailor_auto_quick_score` and maps it exactly this way). Nothing in the
  // UI said so, so the second LLM call was invisible — the tailor modals now do.
  useEffect(() => {
    api.get('/settings').then(({ data }) => {
      const v = String(data?.tailor_auto_quick_score ?? 'light').trim().toLowerCase()
      setTailorChain(['off', 'false', 'no', '0'].includes(v) ? null : v === 'full' ? 'full' : 'light')
    }).catch(() => { /* silent: the note falls back to the seeded default */ })
  }, [])

  // the document these context loaders belong to — a response that comes back
  // after the user has moved to another résumé is dropped (what the old `alive`
  // flags in these two effects did)
  const docIdRef = useRef(null)
  docIdRef.current = doc ? String(doc.id) : null

  const changes = useMemo(() => (isCopy && baseData && data ? computeChanges(baseData, data) : []), [isCopy, baseData, data])
  const changedSections = useMemo(() => {
    const s = new Set()
    changes.forEach((c) => { if (c.key === 'summary') s.add('Summary'); else if (c.key.startsWith('exp')) s.add('Experience'); else if (c.key.startsWith('sk:')) s.add('Skills') })
    return s
  }, [changes])

  // copy job context: score/delta, tracers, cover-letter existence
  const loadJobCtx = useCallback(() => {
    if (!doc || doc.is_base || !doc.job_id) return Promise.resolve()
    const mine = String(doc.id)
    return Promise.all([
      api.get(`/jobs/${doc.job_id}`).then(({ data: j }) => { if (docIdRef.current === mine) { setJobData(j); setJobErr(false) } }).catch(() => { if (docIdRef.current === mine) setJobErr(true) }),
      api.get(`/cover-letters`, { params: { job_id: doc.job_id } }).then(({ data }) => { if (docIdRef.current === mine) setCoverExists((data || []).length > 0) }).catch(() => { /* silent: only picks the wording of the cover-letter step */ }),
    ])
  }, [doc])

  // DESIGN-LOAD: everything the context band says about a copy — the fit ring, the
  // "Tailored for …" line, the "based on <base> ↗" link, the status/tracer line and
  // the one next-step button — comes from these four requests. Rendered as they
  // landed, the band wrote "Tailored copy · not scored yet" and then rewrote itself
  // twice. They settle as one, and the band's two line boxes are held meanwhile.
  const { ready: ctxReady } = useSettled([
    // parent base data for the diff/marks (tailored copies only); copy count for a base
    () => {
      if (doc && doc.is_base) {
        const mine = String(doc.id)
        setBaseData(null)
        return api.get('/resumes', { params: { is_base: false } }).then(({ data }) => { if (docIdRef.current === mine) setBaseCopyCount((data || []).filter((r) => String(r.parent_id) === mine).length) }).catch(() => { /* silent: an auxiliary count in the band; absent it simply doesn't render */ })
      }
      if (doc && doc.parent_id) {
        const mine = String(doc.id)
        return api.get(`/resumes/${doc.parent_id}`).then(({ data: p }) => { if (docIdRef.current === mine) { setBaseData(p.json_data || null); setParentName(p.name || null) } }).catch(() => { /* silent: the diff marks and the base name degrade to the name heuristic */ })
      }
      setBaseData(null); setParentName(null)
      return null
    },
    () => {
      if (!doc || doc.is_base) { setJobData(null); setTracers([]); setJobErr(false); return null }
      if (!doc.job_id) { setJobData(null); setJobErr(false) }   // RES-20: no job to load, so no failure to report
      const mine = String(doc.id)
      return Promise.all([
        loadJobCtx(),
        api.get(`/resumes/${id}/tracer-stats`).then(({ data }) => { if (docIdRef.current === mine) setTracers(data || []) }).catch(() => { /* silent: an optional click-count suffix on the band line */ }),
      ])
    },
  ], doc ? String(doc.id) : '')

  // RES-20: a copy tailored from a pasted description has no Job row. The JD it was
  // written against lives on the copy (json_data._tailor_context, routes_resumes.py)
  // and so does its score (json_data._score) — which is what makes it scoreable.
  const freeformJd = ((data && data._tailor_context && data._tailor_context.job_description) || '').trim()
  const jobless = !!doc && !doc.is_base && !doc.job_id

  const scores = useMemo(() => {
    if (doc && !doc.is_base && !doc.job_id) {
      const t = data && data._score && typeof data._score.Tailored === 'number' ? Math.round(data._score.Tailored) : null
      return { tailored: t, base: null, delta: null }
    }
    const cs = jobData?.cv_scores || {}
    const tailored = typeof cs['Tailored'] === 'number' ? Math.round(cs['Tailored']) : null
    const others = Object.entries(cs).filter(([k, v]) => k !== 'Tailored' && typeof v === 'number').map(([, v]) => v)
    const base = others.length ? Math.round(Math.max(...others)) : null
    return { tailored, base, delta: tailored != null && base != null ? tailored - base : null }
  }, [jobData, doc, data])

  const runScore = useCallback(async (depth) => {
    if (!doc?.job_id && !freeformJd) { pushToast({ kind: 'error', msg: 'This copy has no job and no saved description to score against.' }); return }
    setHeadMenu(false); setScoring(true)
    // RES-30: the old poll only asked "is cv_scores.Tailored a number?", so on a
    // re-score the first tick matched the score already on the job and reported the
    // OLD value while the run was still going. Watch the run instead (scope
    // `{job}:resume:{resume}` — routes_resumes.py:1283) and read the score once it
    // is gone; the base is read at that moment too, never captured in this closure.
    const scope = doc.job_id ? `${doc.job_id}:resume:${id}` : `resume:${id}`
    try {
      const { data: started } = await api.post(`/resumes/${id}/score-check`, { depth })
      const runId = started?.run_id || null   // DS-B-02: identifies the run below
      pushToast({ kind: 'progress', msg: `Scoring (${depth}) — runs in the background.` })
      const t0 = Date.now()
      let seen = false
      const iv = setInterval(async () => {
        try {
          if (Date.now() - t0 > 180000) { clearInterval(iv); setScoring(false); return }   // a run that never ends
          const { data: runs } = await api.get('/monitor/active')
          const live = (runs || []).some((r) => r.job_type === 'score_resume' && r.scope_key === scope)
          if (live) { seen = true; return }
          if (!seen && Date.now() - t0 < 8000) return   // not started yet ≠ finished
          clearInterval(iv); setScoring(false)
          // DS-B-02: the run leaving /monitor/active is not "it worked". Read the
          // run's status before the score — a failed re-score leaves the PREVIOUS
          // score sitting on the job, which this poll would have re-announced as a
          // fresh success.
          const run = await fetchRunOutcome(runId, 'score_resume')
          if (runFailed(run)) { pushToast({ kind: 'error', msg: `Scoring failed — ${runFailureReason(run)}` }); return }
          if (!doc.job_id) {
            // the score of a job-less copy lands on the copy itself — merge just that
            // key back so edits made while it ran are not overwritten
            const { data: r } = await api.get(`/resumes/${id}`)
            const sc0 = r?.json_data?._score?.Tailored
            setData((prev) => ({ ...prev, _score: r?.json_data?._score }))
            if (typeof sc0 === 'number') pushToast({ kind: 'success', msg: `Scored: ${Math.round(sc0)}` })
            else pushToast({ kind: 'error', msg: 'Scoring finished without a score — try again.' })
            return
          }
          const { data: j } = await api.get(`/jobs/${doc.job_id}`)
          setJobData(j)
          const cs = j?.cv_scores || {}
          const sc = typeof cs['Tailored'] === 'number' ? Math.round(cs['Tailored']) : null
          const others = Object.entries(cs).filter(([k, v]) => k !== 'Tailored' && typeof v === 'number').map(([, v]) => v)
          const b = others.length ? Math.round(Math.max(...others)) : null
          if (sc == null) pushToast({ kind: 'error', msg: 'Scoring finished without a score — try again.' })
          else pushToast({ kind: 'success', msg: `Scored: ${sc}${b != null ? ` (${sc - b >= 0 ? '+' : ''}${sc - b} vs base)` : ''}` })
        } catch { if (Date.now() - t0 > 90000) { clearInterval(iv); setScoring(false) } }
      }, 3000)
    } catch (e) { setScoring(false); pushToast({ kind: 'error', msg: e.response?.status === 409 ? 'Already scoring this copy.' : (e.response?.data?.detail || 'Scoring failed to start.') }) }
  }, [doc, id, pushToast, freeformJd])

  const markApplied = useCallback(async () => {
    if (!doc?.job_id) return
    setHeadMenu(false)
    try { await api.patch(`/jobs/${doc.job_id}`, { status: 'applied' }); loadJobCtx(); pushToast({ kind: 'success', msg: 'Marked applied.' }) } catch { pushToast({ kind: 'error', msg: 'Could not mark applied.' }) }
  }, [doc, loadJobCtx, pushToast])

  const deleteResume = useCallback(() => {
    setHeadMenu(false)
    setConfirm({
      title: `Delete “${doc.name}”?`,
      body: doc.is_base ? 'Its tailored copies will be removed too.' : undefined,
      label: 'Delete', danger: true,
      onConfirm: async () => {
        setConfirm(null)
        try { await api.delete(`/resumes/${id}`); navigate('/v2/resumes') } catch { pushToast({ kind: 'error', msg: 'Delete failed.' }) }
      },
    })
  }, [doc, id, navigate, pushToast])

  const goCover = () => { setHeadMenu(false); navigate(`/v2/cover-letters?resume=${id}${doc.job_id ? `&job=${doc.job_id}` : ''}`) }

  // the "one next step" stage for a tailored copy
  // RES-20: the Score stage is only offered when there is something to score
  // against — a job, or the description a freeform tailor saved. A copy with
  // neither skips straight to the cover letter and ends there; "Mark applied"
  // needs a job, so it is never the next step without one.
  const stage = useMemo(() => {
    if (!isCopy) return null
    if (changes.length && !reviewed) return { label: `Review ${changes.length} change${changes.length === 1 ? '' : 's'}`, act: () => setReviewOpen(true) }
    const scoreable = !!doc.job_id || !!freeformJd
    if (scoreable && scores.tailored == null) return { label: scoring ? 'Scoring…' : 'Score the result', act: () => runScore('full') }
    if (!coverExists) return { label: '✉ Write cover letter', act: goCover }
    if (!doc.job_id) return { label: 'Ready ✓', act: null, done: true }
    if (jobData?.status !== 'applied') return { label: 'Mark applied', act: markApplied }
    return { label: 'Applied ✓', act: null, done: true }
  }, [isCopy, doc, freeformJd, changes.length, reviewed, scores.tailored, scoring, coverExists, jobData, runScore, markApplied]) // eslint-disable-line

  // debounced persist
  const persist = useCallback((patch) => {
    setSaving(true)
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try { await api.patch(`/resumes/${id}`, patch); setSavedAt(new Date().toISOString()) }
      catch (e) { console.error(e); setSavedAt(null); pushToast({ kind: 'error', msg: `Save failed — your last edit is not stored. ${e.response?.data?.detail || e.message || ''}`.trim() }) }   // RES-01
      setSaving(false)
    }, 500)
  }, [id])
  const onData = useCallback((next) => { setData(next); persist({ json_data: next }) }, [persist])
  const pickTemplate = (t) => { setTemplate(t); setTplOpen(false); persist({ template: t }) }
  const pickFormat = (f) => { setFormat(f); setFmtOpen(false); persist({ page_format: f }) }

  // live PDF preview — one request at a time (abort the in-flight render before the
  // next so overlapping edits don't hammer /pdf or race the tracer-link writer)
  const pdfAbort = useRef(null)
  useEffect(() => {
    if (!doc) return
    clearTimeout(pdfTimer.current)
    pdfTimer.current = setTimeout(async () => {
      if (pdfAbort.current) pdfAbort.current.abort()
      const ac = new AbortController(); pdfAbort.current = ac
      try {
        const r = await api.get(`/resumes/${id}/pdf`, { responseType: 'arraybuffer', params: { template, format }, signal: ac.signal })
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
        setPdfUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return url })
        setPdfErr(false)
      } catch (e) {
        if (e.code === 'ERR_CANCELED' || e.name === 'CanceledError') return
        // RES-08: a failed render used to leave the *previous* PDF on screen with
        // no signal, so a stale preview and a current one looked identical.
        console.error('pdf', e)
        setPdfUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
        setPdfErr(true)
      }
    }, 800)
    return () => clearTimeout(pdfTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, template, format, doc, id, pdfNonce])
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl) }, [pdfUrl])

  // apply the decline-based review: declined modified/added → revert to base; kept
  // suggested bullets → append; then clear all suggested_bullets. One save.
  const applyReview = useCallback((declined) => {
    const d = JSON.parse(JSON.stringify(data || EMPTY))
    changes.forEach((c) => {
      const off = !!declined[c.key]
      if (c.kind === 'modified' && off) {
        const keys = c.path.split('.'); let o = d
        for (let i = 0; i < keys.length - 1; i++) o = o?.[keys[i]]
        if (o) o[keys[keys.length - 1]] = c.baseText
      } else if (c.kind === 'added' && off) {
        // remove the added copy bullet (match by text within its experience)
        d.experience?.forEach((e) => { if (e.bullets) e.bullets = e.bullets.filter((b) => b !== c.text) })
      } else if (c.kind === 'suggested' && !off) {
        const e = d.experience?.[c.expIdx]; if (e) { e.bullets = e.bullets || []; e.bullets.push(c.text) }
      }
    })
    ;(d.experience || []).forEach((e) => { delete e.suggested_bullets })
    onData(d)
    setReviewOpen(false)
    markReviewed(id); setReviewed(true)   // RES-06: the diff survives; the acknowledgement is what advances the stage
    pushToast({ kind: 'success', msg: 'Review applied — declined changes restored to base.' })
  }, [changes, data, id, onData, pushToast])

  // ── json_data mutation (mirrors v1 ResumeContentEditor) ────────────────────
  useTitle(doc?.name)
  const { mutate, setField } = makeMutators(data, onData)
  const toggle = (name) => setOpen((p) => {
    const n = new Set(p); n.has(name) ? n.delete(name) : n.add(name)
    try { localStorage.setItem('jobnavigator_v2_resume_sections', JSON.stringify([...n])) } catch { /* ignore */ }
    return n
  })

  const pdfDownloadUrl = useMemo(() => {
    const base = (api.defaults.baseURL || '').replace(/\/api$/, '')
    return `${base}/api/resumes/${id}/pdf?template=${encodeURIComponent(template)}&format=${encodeURIComponent(format)}`
  }, [id, template, format])

  // DESIGN-LOAD: reserve the chrome's own shape while the document fetch is in
  // flight, instead of a bare "Loading…" that collapses the whole screen to one
  // centred line and then jumps to the real top-bar + two-pane layout once the
  // doc lands. NBSP holds the top bar's line height; the panes need no content
  // to reserve theirs — they already flex to fill what's left.
  if (!doc || !data) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <HeaderRow pad="10px 24px" bg="surface" soft align="center">
          <span style={{ fontSize: 14, lineHeight: '20px' }}>{NBSP}</span>
        </HeaderRow>
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <section style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)' }} />
          <Surface as="section" radius="none" style={{ flex: 1, minWidth: 0 }} />
        </div>
      </div>
    )
  }

  const counts = sectionCounts(data)
  const tplLabel = templates.find((t) => t.id === template)?.name || template || 'Template'

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* top bar */}
      <HeaderRow pad="10px 24px" bg="surface" soft align="center">
        <NavLink onClick={() => navigate('/v2/resumes')} style={{ whiteSpace: 'nowrap' }}>‹ Résumés</NavLink>
        <span style={{ color: 'var(--line)' }}>|</span>
        {/* ui: keep — Tag role (D4d): an uppercase badge with a background and r99, not a Label */}
        <span style={{ fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 'var(--radius-control)', background: isCopy ? 'var(--accent-soft)' : 'var(--surface-2)', color: isCopy ? 'var(--accent)' : 'var(--muted)' }}>{isCopy ? 'tailored' : 'base'}</span>
        {/* R2-S-06: every other v2 screen names itself with an h1; visually this
            is the same span it always was (margin and font reset inline). */}
        <h1 title={doc.name} style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 14, lineHeight: '20px', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 460 }}>{doc.name}</h1>
        <Helper style={{ marginLeft: 'auto' }}>{saving ? 'Saving…' : savedAt ? `saved ${timeAgo(savedAt)} · autosaves` : 'autosaves'}</Helper>
      </HeaderRow>

      {/* sub-band: base vs copy */}
      {isCopy ? (
        <HeaderRow pad="9px 24px" bg="recessed" align="center" style={{ gap: 13 }}>
          {ctxReady && scores.tailored != null && (
            <ScoreRing value={scores.tailored} size="sm" />
          )}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
            {/* DESIGN-LOAD: both lines keep their boxes (18px and the Helper's own)
                while the four context requests are in flight, so the band is its
                final height from the first frame and fills in once. */}
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0, lineHeight: '18px' }}>
              {!ctxReady ? NBSP : <>
              {jobData?.company
                ? <>Tailored for <span style={{ color: 'var(--text)' }}>{jobData.company}{jobData.title ? ` — ${jobData.title}` : ''}</span></>
                : (jobless && freeformJd ? 'Tailored from a pasted description' : 'Tailored copy')}
              {doc.parent_id && (() => {
                // R2-H-10: a freeform copy is named "<base> (tailored)" — no "→" to
                // split on — so the heuristic returned the copy's own name and the
                // link read "based on <copy>". Use the parent's name; keep the
                // split only until that fetch lands.
                const baseName = parentName || ((doc.name || '').includes('→') ? (doc.name || '').split('→')[0].trim() : '') || 'base'
                const dfg = scores.delta == null ? undefined : (scores.delta >= 0 ? 'var(--accent)' : 'var(--warn)')
                return (
                  <>
                    <BandRule />
                    <NavLink onClick={() => navigate(`/v2/resumes/${doc.parent_id}`)} title={`Open the ${baseName} base résumé this was tailored from`} style={{ position: 'relative', top: '1px' }}>
                      {scores.delta != null && <span style={{ color: dfg, fontWeight: 600 }}>{scores.delta >= 0 ? '+' : ''}{scores.delta} </span>}
                      <span style={{ color: 'var(--accent)' }}>based on {baseName} ↗</span>
                    </NavLink>
                  </>
                )
              })()}
              </>}
            </div>
            <Helper style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {/* RES-20: "not scored yet" used to cover three different states — a
                  copy waiting to be scored, one that can never be, and a job whose
                  fetch failed. They read differently now.
                  DESIGN-LOAD: the tracer counts are part of the same settle, so the
                  line no longer grows a " · tracers: …" tail after the fact. */}
              {!ctxReady ? NBSP : <>
              {jobErr ? 'Couldn’t load the linked job.'
                : jobless && !freeformJd ? 'No job or description linked, so this copy can’t be scored.'
                  : (changes.length && !reviewed ? `${changes.length} reviewable change${changes.length === 1 ? '' : 's'}` : scores.tailored == null ? 'not scored yet' : 'ready')}
              {tracers.length > 0 && <> · tracers: {tracers.map((t) => `${t.source_label} ${t.clicks}`).join(' · ')}</>}
              </>}
            </Helper>
          </div>
          {ctxReady && stage && (
            <Button onClick={() => stage.act && stage.act()} disabled={stage.done} title={stage.done ? 'Pipeline complete' : 'The one next step'}>
              {scoring && <Spinner size={11} color="currentColor" />}
              {stage.label}
            </Button>
          )}
          <div style={{ position: 'relative', flex: '0 0 auto' }}>
            <IconButton size={36} on={headMenu} ariaExpanded={headMenu} ariaHaspopup="menu"
              onClick={() => setHeadMenu((v) => !v)} title="More">⋯</IconButton>
            {headMenu && (
              <>
                <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                <Menu ariaLabel="Résumé actions" style={{ position: 'absolute', top: '100%', right: 0, marginTop: 5, zIndex: 45, width: 244 }}>
                  <MenuHead>This copy</MenuHead>
                  <MenuItem icon="✦" hint="adds a copy" onClick={() => { setHeadMenu(false); setTailorOpen(true) }}>Re-tailor…</MenuItem>
                  <MenuItem icon="◎" hint="score only" onClick={() => runScore('light')}>Score again · light</MenuItem>
                  <MenuItem icon="◎" hint="with report" onClick={() => runScore('full')}>Score again · full</MenuItem>
                  {changes.length > 0 && <MenuItem icon="≋" hint={`${changes.length} to review`} onClick={() => { setHeadMenu(false); setReviewOpen(true) }}>Review changes</MenuItem>}
                  <Rule style={{ margin: '4px 8px' }} />
                  <MenuHead>Job</MenuHead>
                  <MenuItem icon="✉" hint="c" onClick={goCover}>Cover letter</MenuItem>
                  {doc.job_id && <MenuItem icon="↗" hint="e" onClick={() => navigate(`/v2/feed?job=${doc.job_id}`)}>Open in feed</MenuItem>}
                  {doc.job_id && <MenuItem icon="✓" hint="a" onClick={markApplied}>Mark applied</MenuItem>}
                  <MenuItem danger icon="✕" onClick={deleteResume}>Delete copy</MenuItem>
                </Menu>
              </>
            )}
          </div>
        </HeaderRow>
      ) : (
        <HeaderRow pad="9px 24px" bg="recessed" align="center" style={{ gap: 13, fontSize: 12.5, color: 'var(--text-2)' }}>
          {/* DESIGN-LOAD: the copy count is part of the context settle — it used to
              push the rest of the line sideways when it landed on its own. The whole
              sentence is withheld until ctxReady (not just the copy-count clause), so
              it paints in one state instead of a bare sentence followed ~100ms later
              by the same sentence with the clause inserted. */}
          <span>{!ctxReady ? NBSP : <>Base résumé · {baseCopyCount != null && <><span style={{ color: 'var(--text)', fontWeight: 500 }}>{baseCopyCount} tailored cop{baseCopyCount === 1 ? 'y' : 'ies'}</span> · </>}editing here changes future tailoring only</>}</span>
          <Button onClick={() => setTailorOpen(true)} style={{ marginLeft: 'auto' }}>✦ Tailor for a job…</Button>
          {/* RES-09: bases get the same ⋯ → Delete as copies (the confirm already warns that copies go too).
              R3-B-06: worded "Delete résumé" here — this document is the base, and deleting it takes every copy with it. */}
          <div style={{ position: 'relative', flex: '0 0 auto', marginLeft: 8 }}>
            <IconButton size={36} on={headMenu} ariaExpanded={headMenu} ariaHaspopup="menu"
              onClick={() => setHeadMenu((v) => !v)} title="More">⋯</IconButton>
            {headMenu && (
              <>
                <div onClick={() => setHeadMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 44 }} />
                <Menu ariaLabel="Résumé actions" style={{ position: 'absolute', top: '100%', right: 0, marginTop: 5, zIndex: 45, width: 244 }}>
                  <MenuHead>This base</MenuHead>
                  <MenuItem icon="✦" hint="adds a copy" onClick={() => { setHeadMenu(false); setTailorOpen(true) }}>Tailor for a job…</MenuItem>
                  <MenuItem danger icon="✕" onClick={deleteResume}>Delete résumé</MenuItem>
                </Menu>
              </>
            )}
          </div>
        </HeaderRow>
      )}

      {/* two-pane */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* left: sections */}
        <section className="v2-scroll" style={{ flex: '0 0 47%', borderRight: '1px solid var(--line)', overflow: 'auto', padding: '14px 20px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {SECTION_ORDER.map((name) => (
            <SectionShell key={name} name={name} count={counts[name]} open={open.has(name)} onToggle={() => toggle(name)}
              meta={changedSections.has(name) ? <span title="Contains unreviewed tailoring changes" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--warn)' }}>● changed by tailoring</span> : null}>
              <SectionEditor name={name} data={data} setField={setField} mutate={mutate} baseData={baseData} onError={(msg) => pushToast({ kind: 'error', msg })}
                onRemoved={(msg, undo) => pushToast({ kind: 'undo', msg, action: 'Undo', onAction: undo })} />
            </SectionShell>
          ))}
        </section>

        {/* right: PDF preview */}
        <Surface as="section" radius="none" style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {/* R2-S-02: wraps rather than overflowing, like the cover-letter
              editor's identical toolbar */}
          <HeaderRow pad="8px 20px" align="center" style={{ flexWrap: 'wrap', rowGap: 6 }}>
            <Label>PDF preview</Label>
            {/* template picker — the container swallows its own clicks so the
                document closer below can't undo the toggle (RES-28) */}
            {/* ui: keep — the two 9px muted ▾ carets below are the PDF-preview toolbar's own paper scale (below Helper's tolerance) */}
            {/* DESIGN-LOAD: both triggers wait for the template list; the row's
                height is the Download link's, so nothing moves when they land */}
            {tplReady && <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
              {/* ui: keep — a 24px PDF-toolbar dropdown trigger (h24 · pad 0 8 · r6 · 11.5); Select's box is 32.
                  D5 note: the cover-letter editor draws the same trigger with `v2-bd v2-ctl` — the two
                  hovers are a logged needs-decision, not a licence to add a third. */}
              <span onClick={() => { setTplOpen((v) => !v); setFmtOpen(false) }} title="Résumé template" className="v2-act" style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 'var(--radius-field)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}><span style={{ color: 'var(--muted)' }}>Template</span><span style={{ color: 'var(--text)' }}>{tplLabel}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span></span>
              {tplOpen && (
                  <Menu role="listbox" ariaLabel="Résumé template" className="v2-scroll" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 5, zIndex: 21, width: 190, maxHeight: 300, overflow: 'auto' }}>
                    {templates.map((t) => <MenuItem key={t.id} role="option" ariaSelected={t.id === template} selected={t.id === template} onClick={() => pickTemplate(t.id)}>{t.name}</MenuItem>)}
                  </Menu>
              )}
            </div>}
            {/* format */}
            {tplReady && <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
              {/* ui: keep — the paper-size twin of the template trigger above */}
              <span onClick={() => { setFmtOpen((v) => !v); setTplOpen(false) }} title="Paper size" className="v2-act" style={{ height: 24, padding: '0 8px', border: '1px solid var(--edge)', borderRadius: 'var(--radius-field)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, cursor: 'pointer' }}><span style={{ color: 'var(--muted)' }}>Paper</span><span style={{ color: 'var(--text)' }}>{format === 'a4' ? 'A4' : 'US Letter'}</span><span style={{ color: 'var(--muted)', fontSize: 9 }}>▾</span></span>
              {fmtOpen && (
                  <Menu role="listbox" ariaLabel="Paper size" style={{ position: 'absolute', top: '100%', left: 0, marginTop: 5, zIndex: 21, width: 130 }}>
                    {[['letter', 'US Letter'], ['a4', 'A4']].map(([v, l]) => <MenuItem key={v} role="option" ariaSelected={v === format} selected={v === format} onClick={() => pickFormat(v)}>{l}</MenuItem>)}
                  </Menu>
              )}
            </div>}
            {/* ui: keep — native <a href target=_blank> download link; Button renders a div and would drop the anchor */}
            <a href={pdfDownloadUrl} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 'auto', flex: '0 0 auto', minWidth: 0, height: 29, padding: '0 15px', borderRadius: 'var(--radius-control)', background: 'var(--accent)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap' }}>↓ Download PDF</a>
          </HeaderRow>
          <Surface radius="none" style={{ flex: 1, minHeight: 0, position: 'relative' }}>
            {pdfUrl && <iframe title="pdf" src={`${pdfUrl}#view=FitH`} style={{ width: '100%', height: '100%', border: 'none' }} />}
            {pdfErr && !pdfUrl && (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 9, color: 'var(--muted)', fontSize: 12.5 }}>
                <span>Preview failed — the PDF could not be rendered.</span>
                <Pill size="sm" onClick={() => setPdfNonce((n) => n + 1)}>Retry</Pill>
              </div>
            )}
          </Surface>
        </Surface>
      </div>

      {tailorOpen && (isCopy
        ? <RetailorModal doc={doc} job={jobData} chain={tailorChain} onClose={() => setTailorOpen(false)} onRun={runRetailor} pushToast={pushToast} />
        : <TailorModal doc={doc} chain={tailorChain} onClose={() => setTailorOpen(false)} onRun={runTailor} pushToast={pushToast} />)}
      {reviewOpen && <ReviewModal changes={changes} onClose={() => setReviewOpen(false)} onApply={applyReview} />}
      {confirm && <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)} />}

      <ToastStack toasts={toasts} onClose={dismissToast} />
    </div>
  )
}

// ── re-tailor (a tailored copy) ──────────────────────────────────────────────
// The job is already decided — we are on that job's résumé. What is open is
// which base to work from, and whether to run the tailoring LLM at all or just
// take an exact copy for a fresh set of tracer links.
function RetailorModal({ doc, job, chain, onClose, onRun, pushToast }) {
  const [mode, setMode] = useState('tailor')
  const [bases, setBases] = useState([])
  const [persona, setPersona] = useState(false)
  const [baseId, setBaseId] = useState(doc.parent_id || 'persona')

  useEffect(() => {
    // OPEN-05: converted — the user opened this modal to pick a source, and an
    // empty list with a disabled button says nothing about why.
    api.get('/resumes', { params: { is_base: true } }).then(({ data }) => setBases(data || [])).catch((e) => { console.error(e); pushToast?.({ kind: 'error', msg: 'Could not load your base résumés — there is nothing to re-tailor from.' }) })
    api.get('/persona').then(({ data }) => setPersona(Object.keys(data?.resume_content || {}).length > 0)).catch((e) => { console.error(e); pushToast?.({ kind: 'error', msg: 'Could not load your Persona — it will not be offered as a source.' }) })
  }, [pushToast])

  // /resumes/copy takes a Resume row; the Persona isn't one, so it can only be
  // tailored from — RES-28: this was a `personaCopyable = false` constant.
  const options = [
    ...(persona ? [{ id: 'persona', name: 'Persona', note: 'your full profile' }] : []),
    ...bases.map((b) => ({ id: String(b.id), name: b.name, note: 'base résumé' })),
  ]
  const disabled = (id) => mode === 'copy' && id === 'persona'
  const canRun = !!baseId && !disabled(baseId)

  const MODES = [
    ['tailor', '✦ Tailor', 'Rewrites bullets against this job description'],
    ['copy', 'Copy', 'Exact copy of the base, with its own tracer links'],
  ]

  return (
    <ChoiceModal
      title="Re-tailor for this job"
      sub={<>{job?.company ? `${job.company}${job.title ? ` — ${job.title}` : ''}` : 'the job this copy is for'} · adds a new copy</>}
      subClamp onClose={onClose}
      note={<>
        <Helper>{mode === 'tailor' ? 'Runs in the background' : 'Instant — no LLM call'}</Helper>
        {mode === 'tailor' && <Helper size="xs" style={{ textWrap: 'pretty' }}>{chainNote(chain)}</Helper>}
      </>}
      action={mode === 'tailor' ? '✦ Re-tailor' : 'Make copy'} actionDisabled={!canRun}
      onAction={() => onRun({ mode, baseId })}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Label>How</Label>
        <div style={{ display: 'flex', gap: 7 }}>
          {MODES.map(([id, label, hint]) => (
            <ChoiceCard key={id} on={mode === id} label={label} hint={hint} title={hint} onClick={() => setMode(id)} />
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Label>From which base</Label>
        {options.map((o) => (
          <ChoiceRow key={o.id} on={String(baseId) === String(o.id)} disabled={disabled(o.id)}
            title={disabled(o.id) ? 'Persona has no résumé row to copy — tailor from it instead' : undefined}
            label={o.name}
            hint={String(doc.parent_id || 'persona') === String(o.id) ? 'current base' : o.note}
            onClick={() => setBaseId(o.id)} />
        ))}
        {options.length === 0 && <Band interactive={false} style={{ padding: 12 }}><Helper>No base résumés yet.</Helper></Band>}
      </div>
    </ChoiceModal>
  )
}

// R2-H-09: the tailor endpoint chains a score of the copy it just made, which is
// a second LLM call the modals never mentioned. One line, read from the setting
// that controls it — the control itself stays in Settings › AI.
const chainNote = (chain) => (chain
  ? `Also scores the copy afterwards at ${chain} depth · 1 more LLM call · change under Settings › AI`
  : 'Scoring after tailoring is off')

// ── tailor modal (job picker + freeform + persona) ───────────────────────────
function TailorModal({ doc, chain, onClose, onRun, pushToast }) {
  const baseId = doc.id
  const [jobs, setJobs] = useState([])
  const [existing, setExisting] = useState(new Set())
  const [q, setQ] = useState('')
  const [pick, setPick] = useState(null)
  const [jd, setJd] = useState('')
  // RES-28: this read `baseId === 'persona'`, which is never true (baseId is the
  // base's own id) — the box simply starts unticked, so say that.
  const [personaBase, setPersonaBase] = useState(false)

  useEffect(() => {
    api.get('/jobs', { params: { status: 'saved,applied,new', sort_by: 'date', limit: 60 } })
      // OPEN-05: converted — this is the modal's own job list; empty with no
      // explanation reads as "you have no saved jobs", which may not be true.
      .then(({ data }) => setJobs((data.jobs || data.items || data || []))).catch((e) => { console.error(e); pushToast?.({ kind: 'error', msg: 'Could not load your jobs — paste a description instead.' }) })
    api.get('/resumes', { params: { is_base: false } })
      .then(({ data }) => setExisting(new Set((data || []).filter((r) => String(r.parent_id) === String(baseId)).map((r) => String(r.job_id))))).catch(() => { /* silent: drives only the “✦ exists” hint on a row */ })
  }, [baseId, pushToast])

  const baseName = (r) => (typeof r === 'string' ? r : r?.name)
  const jobScore = (j) => {
    const cs = j.cv_scores || {}
    for (const k of [doc.name, 'Tailored']) if (typeof cs[k] === 'number') return Math.round(cs[k])
    const nums = Object.values(cs).filter((v) => typeof v === 'number')
    return nums.length ? Math.round(Math.max(...nums)) : null
  }
  const t = q.trim().toLowerCase()
  const list = jobs.filter((j) => !t || `${j.title} ${j.company}`.toLowerCase().includes(t))
    .sort((a, b) => (['saved', 'applied'].includes(b.status) ? 1 : 0) - (['saved', 'applied'].includes(a.status) ? 1 : 0))

  const canRun = !!(pick || jd.trim())
  const chosen = jobs.find((j) => String(j.id) === String(pick))
  const run = () => onRun({ baseId: personaBase ? 'persona' : baseId, jobId: pick, jobDescription: pick ? '' : jd.trim(), company: chosen?.company })

  return (
    // bodyGap 12 (not the shell's 13) is this modal's own spacing, kept so
    // naming the shared shell moved no pixel here.
    <ChoiceModal
      title={<>Tailor {doc.name} for a job</>}
      sub="Changes land automatically — you review and decline afterwards."
      bodyGap={12} onClose={onClose}
      note={<>
        <Helper>Runs in the background</Helper>
        {/* the chain only fires for a job-linked tailor (routes_resumes.py:
            `if chain_depth and job_id`), so a freeform run says nothing */}
        {pick && <Helper size="xs" style={{ textWrap: 'pretty' }}>{chainNote(chain)}</Helper>}
      </>}
      action="✦ Tailor" actionDisabled={!canRun} onAction={run}>
      <Check checked={personaBase} onChange={setPersonaBase} label="Tailor from Persona instead of this base" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Label>Pick a job · saved and scored first</Label>
        <Input value={q} onChange={setQ} placeholder="Search jobs…" ariaLabel="Search jobs" />
        {list.slice(0, 40).map((j) => {
          const sc = jobScore(j), has = existing.has(String(j.id))
          return (
            <ChoiceRow key={j.id} on={String(pick) === String(j.id)}
              label={j.title} sub={<>{j.company} · {j.status}</>}
              onClick={() => { setPick(j.id); setJd('') }}
              trail={<>
                {/* ui: keep — mono-text role (accent ink, not --helper-ink); the step excludes mono ids */}
                {sc != null && <span title="This base's fit on that job" style={{ flex: '0 0 auto', fontFamily: 'var(--mono)', fontSize: 10.5, lineHeight: '16px', color: 'var(--accent)' }}>{sc}</span>}
                {has && <span title="A tailored copy already exists — tailoring again adds another" style={{ flex: '0 0 auto', fontSize: 9, lineHeight: '14px', color: 'var(--warn)' }}>✦ exists</span>}
              </>} />
          )
        })}
        {list.length === 0 && <Band interactive={false} style={{ padding: 12 }}><Helper>No jobs match — paste a description below instead.</Helper></Band>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <Label>…or a freeform job description</Label>
        <Textarea value={jd} onChange={(v) => { setJd(v); if (v.trim()) setPick(null) }} rows={3}
          placeholder="Paste any JD — the copy won't be linked to a feed job" ariaLabel="Freeform job description"
          style={{ borderStyle: 'dashed' }} />
      </div>
    </ChoiceModal>
  )
}

// ── review modal (decline-based) ─────────────────────────────────────────────
function ReviewModal({ changes, onClose, onApply }) {
  const [declined, setDeclined] = useState({})
  const n = Object.values(declined).filter(Boolean).length
  // R3-B-02: two different things were both chipped "applied". A modified summary
  // or bullet is genuinely in json_data (and in the PDF) the moment the tailor
  // finishes; a *suggested* bullet lives in experience[].suggested_bullets, which
  // no resume template renders, and only reaches json_data.bullets when this modal
  // is confirmed (applyReview). Telling the user it "landed automatically" was
  // wrong for exactly the rows that had not landed.
  const nSuggested = changes.filter((c) => c.kind === 'suggested').length
  const nApplied = changes.length - nSuggested
  const liveApplied = changes.filter((c) => c.kind !== 'suggested' && !declined[c.key]).length
  const liveSuggested = changes.filter((c) => c.kind === 'suggested' && !declined[c.key]).length
  return (
    <ModalPanel width="min(920px, 94vw)" onClose={onClose} zIndex={60} style={{ height: 'min(760px, 90vh)', overflow: 'hidden' }}>
        <HeaderRow align="center" style={{ gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Heading>{nSuggested ? 'Tailoring changes' : 'Tailoring changes — already applied'}</Heading>
            <Helper>
              {nSuggested
                ? `${nApplied ? 'Applied changes are already in the document — decline any and the base text comes back. ' : ''}Suggested bullets are not in it yet: they are added when you finish reviewing.`
                : "These landed automatically. Decline any you don't want; the base text comes back."}
            </Helper>
          </div>
          <IconButton onClick={onClose} title="Close" style={{ marginLeft: 'auto' }}>✕</IconButton>
        </HeaderRow>
        <div className="v2-scroll" style={{ flex: 1, overflow: 'auto', padding: '15px 22px', display: 'flex', flexDirection: 'column', gap: 11, minHeight: 0 }}>
          {changes.length === 0 && <div style={{ padding: 20, fontSize: 12.5, color: 'var(--muted)' }}>No tailoring changes to review.</div>}
          {changes.map((c) => {
            const off = !!declined[c.key]
            const pending = c.kind === 'suggested'   // R3-B-02: not in json_data yet
            const live = !off
            const added = c.kind === 'modified' ? (off ? c.removed : c.added) : c.added
            const removed = c.kind === 'modified' ? (off ? c.added : c.removed) : ''
            return (
              <div key={c.key} style={{ border: `1px solid ${!live ? 'var(--line)' : pending ? 'var(--warn-line)' : 'var(--change-soft)'}`, borderRadius: 'var(--radius-card)', padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: 7, background: !live ? 'var(--bg)' : pending ? 'var(--warn-soft)' : 'var(--change-bg)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Label>{c.where}</Label>
                  {/* ui: keep — a state badge whose dashed --warn-line edge marks a
                      suggestion; not a dashed add-line */}
                  <span title={pending ? 'Suggested — not in the document or the PDF yet; added when you finish reviewing' : off ? 'Declined — the base text is restored' : 'Already in the document and in the PDF'}
                    style={{ fontSize: 10, lineHeight: '16px', letterSpacing: '.08em', textTransform: 'uppercase', padding: '1px 7px', borderRadius: 'var(--radius-control)', background: !live ? 'var(--surface-2)' : pending ? 'var(--surface)' : 'var(--accent-soft)', border: `1px ${live && pending ? 'dashed var(--warn-line)' : 'solid transparent'}`, color: !live ? 'var(--muted)' : pending ? 'var(--warn)' : 'var(--accent)', cursor: 'help' }}>{!live ? (pending ? 'dropped' : 'declined') : pending ? 'suggested' : 'applied'}</span>
                  {live && pending && <Helper size="xs">added when you finish reviewing</Helper>}
                  {/* ui: keep — border+ink swing --accent/--warn with the change's state; Pill has no tinted variant */}
                  <div onClick={() => setDeclined((p) => ({ ...p, [c.key]: !p[c.key] }))} style={{ marginLeft: 'auto', height: 24, padding: '0 12px', borderRadius: 'var(--radius-control)', border: `1px solid ${off ? 'var(--accent)' : 'var(--warn)'}`, color: off ? 'var(--accent)' : 'var(--warn)', fontSize: 11, fontWeight: 500, display: 'flex', alignItems: 'center', cursor: 'pointer' }}>{pending ? (off ? 'Keep it' : 'Drop ↩') : (off ? 'Restore change' : 'Decline ↩')}</div>
                </div>
                <span style={{ fontSize: 12.5, lineHeight: '20px', color: 'var(--text-2)' }}>
                  {c.before}
                  {removed && <span style={{ background: 'var(--bad-soft)', textDecoration: 'line-through', opacity: 0.75, borderRadius: 'var(--radius-mark)', padding: '0 3px' }}>{removed}</span>}
                  {/* RES-28: the old `{added || '(base text restored)'}` fallback sat
                      inside `{added && …}` and could never render. */}
                  {/* ui: keep — inline diff highlight on a run of text (r3), not a band */}
                  {added && <span style={{ background: !live ? 'var(--surface-2)' : pending ? 'var(--surface)' : 'var(--change-soft)', border: `1px ${live && pending ? 'dashed var(--warn-line)' : 'solid transparent'}`, borderRadius: 'var(--radius-mark)', padding: '0 3px' }}>{added}</span>}
                  {c.after}
                </span>
              </div>
            )
          })}
        </div>
        {/* ui: keep — a modal *footer* bar: its rule is on top and its ground is
            the recessed tint; HeaderRow draws its rule beneath */}
        <div style={{ padding: '12px 22px', borderTop: '1px solid var(--line)', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', gap: 9 }}>
          {/* R3-B-02: the count line separates what is already in the document from
              what is only proposed, so "Done reviewing" says what it is about to do. */}
          <Helper>{nSuggested
            ? `${liveApplied} applied · ${liveSuggested} suggested — added on Done reviewing${nApplied - liveApplied ? ` · ${nApplied - liveApplied} declined` : ''}`
            : n ? `${n} declined — base text restored · the rest stay` : `All ${changes.length} change${changes.length === 1 ? '' : 's'} live · decline any to restore the base text`}</Helper>
          <Button size="sm" onClick={() => onApply(declined)} style={{ marginLeft: 'auto' }}>Done reviewing</Button>
        </div>
    </ModalPanel>
  )
}
